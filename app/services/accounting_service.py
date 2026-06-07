"""
Servicio Contable — NIIF para PYMES / Ecuador.
Genera asientos automáticos para ventas, gastos y caja.
Produce los estados financieros básicos requeridos por NIIF NIC 1:
  • Balance de Comprobación
  • Estado de Situación Financiera (Balance General)
  • Estado de Resultados Integrales
  • Estado de Flujo de Efectivo (método directo)
"""
from datetime import datetime, date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.accounting import AccountPlan, FiscalPeriod, JournalEntry, JournalEntryLine, ECUADOR_CHART_OF_ACCOUNTS
from ..models.sales import Sale, SalePayment, PaymentMethod
from ..models.expenses import Expense


# ── Códigos de cuentas usados en asientos automáticos ──────────────────────────
ACC_CAJA_GENERAL        = "1.1.01.001"
ACC_TARJETA_LIQUIDAR    = "1.1.01.005"
ACC_IVA_COMPRAS         = "1.1.04.001"
ACC_RETENCIONES_FAVOR   = "1.1.04.002"
ACC_PROVEEDORES         = "2.1.01.001"
ACC_IVA_VENTAS          = "2.1.03.001"
ACC_RETENCIONES_PAGAR   = "2.1.03.002"
ACC_VENTAS_IVA          = "4.1.001"
ACC_VENTAS_0            = "4.1.002"
ACC_DEVOLUCION_VENTAS   = "4.1.005"
ACC_SOBRANTE_CAJA       = "4.2.002"
ACC_OTROS_INGRESOS      = "4.2.003"
ACC_FALTANTE_CAJA       = "5.2.017"
ACC_OTROS_GASTOS        = "5.2.019"

# Métodos de pago que se considera "efectivo" (SRI codes: 01=efectivo, 20=retención)
CASH_SRI_CODES = {"01", "20"}


class AccountingService:

    # ─────────────────────────────────────────────────────────────────────────
    # Seeding del Plan de Cuentas
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def seed_chart_of_accounts(db: Session) -> None:
        """Inserta el Plan de Cuentas Ecuador si la tabla está vacía."""
        if db.query(AccountPlan).count() > 0:
            return

        # Primer pasada: crear todas las cuentas sin parent_id
        code_to_id: dict[str, int] = {}
        for acc in ECUADOR_CHART_OF_ACCOUNTS:
            obj = AccountPlan(
                code=acc["code"],
                name=acc["name"],
                account_type=acc["type"],
                nature=acc["nature"],
                level=acc["level"],
                allows_entries=acc["entries"],
                niif_category=acc.get("niif"),
            )
            db.add(obj)
        db.flush()

        # Indexar codes → IDs después del flush
        for a in db.query(AccountPlan).all():
            code_to_id[a.code] = a.id

        # Segunda pasada: asignar parent_id
        for acc in ECUADOR_CHART_OF_ACCOUNTS:
            parent_code = acc.get("parent")
            if parent_code and parent_code in code_to_id:
                db.query(AccountPlan).filter_by(code=acc["code"]).update(
                    {"parent_id": code_to_id[parent_code]}
                )
        db.commit()

    # ─────────────────────────────────────────────────────────────────────────
    # Períodos fiscales
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_period(db: Session, company_id: int, for_date: datetime) -> Optional[FiscalPeriod]:
        """Devuelve el período mensual abierto para la fecha dada; lo crea si no existe."""
        start = for_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        import calendar
        last_day = calendar.monthrange(for_date.year, for_date.month)[1]
        end = for_date.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)

        period = db.query(FiscalPeriod).filter(
            FiscalPeriod.company_id == company_id,
            FiscalPeriod.start_date == start,
            FiscalPeriod.period_type == "MENSUAL",
        ).first()

        if not period:
            month_names = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                           "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
            period = FiscalPeriod(
                company_id=company_id,
                name=f"{month_names[for_date.month - 1]} {for_date.year}",
                period_type="MENSUAL",
                start_date=start,
                end_date=end,
                status="ABIERTO",
            )
            db.add(period)
            db.flush()
        return period

    # ─────────────────────────────────────────────────────────────────────────
    # Numeración de asientos
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def next_entry_number(db: Session, company_id: int, year: int) -> str:
        last = db.query(func.count(JournalEntry.id)).filter(
            JournalEntry.company_id == company_id,
            func.strftime("%Y", JournalEntry.entry_date) == str(year),
        ).scalar() or 0
        return f"AST-{year}-{str(last + 1).zfill(6)}"

    # ─────────────────────────────────────────────────────────────────────────
    # Lookup de cuentas
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _account(db: Session, code: str) -> AccountPlan:
        acc = db.query(AccountPlan).filter_by(code=code).first()
        if not acc:
            raise ValueError(f"Cuenta contable '{code}' no encontrada en el Plan de Cuentas.")
        return acc

    # ─────────────────────────────────────────────────────────────────────────
    # Asiento automático de VENTA (FACTURADO)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_sale_journal_entry(db: Session, sale: Sale) -> Optional[JournalEntry]:
        """
        Genera el asiento contable automático al facturar una venta:
          Dr. Caja General / Tarjetas por Liquidar   [total]
          Dr. Retenciones en la Fuente a Favor       [withholding]  (si aplica)
            Cr. Ventas (4.1.001 o 4.1.002)           [subtotal]
            Cr. IVA en Ventas (2.1.03.001)           [tax_amount]
        """
        if not sale.company_id:
            return None

        try:
            total      = float(sale.total or 0)
            subtotal   = float(sale.subtotal_tax or sale.subtotal or 0)
            tax        = float(sale.tax_amount or 0)
            wh_iva     = float(sale.withholding_iva or 0)
            wh_renta   = float(sale.withholding_renta or 0)
            withholding = wh_iva + wh_renta

            # Determinar cuenta de cobro: efectivo vs. tarjeta
            payment = db.query(SalePayment).filter_by(sale_id=sale.id).first()
            pm = db.query(PaymentMethod).get(payment.payment_method_id) if payment else None
            is_cash = not pm or pm.sri_code in CASH_SRI_CODES
            debit_code = ACC_CAJA_GENERAL if is_cash else ACC_TARJETA_LIQUIDAR

            # Cuenta de ventas según si hay IVA
            sales_code = ACC_VENTAS_IVA if tax > 0 else ACC_VENTAS_0

            period = AccountingService.get_or_create_period(db, sale.company_id, sale.sale_date or datetime.utcnow())
            number = AccountingService.next_entry_number(db, sale.company_id, (sale.sale_date or datetime.utcnow()).year)

            entry = JournalEntry(
                company_id=sale.company_id,
                period_id=period.id if period else None,
                entry_number=number,
                entry_date=sale.sale_date or datetime.utcnow(),
                description=f"Venta factura {sale.invoice_number} — {sale.customer_name}",
                reference=sale.invoice_number,
                entry_type="VENTA",
                status="APROBADO",
                source_type="Sale",
                source_id=sale.id,
            )
            db.add(entry)
            db.flush()

            lines = []
            # Débito: efectivo/tarjeta por el neto cobrado
            net_collected = total - withholding
            if net_collected > 0:
                lines.append(JournalEntryLine(
                    entry_id=entry.id,
                    account_id=AccountingService._account(db, debit_code).id,
                    description=f"Cobro {'efectivo' if is_cash else 'tarjeta'} factura {sale.invoice_number}",
                    debit=round(net_collected, 2),
                    credit=0.0,
                ))
            # Débito: retenciones recibidas → activo
            if withholding > 0:
                lines.append(JournalEntryLine(
                    entry_id=entry.id,
                    account_id=AccountingService._account(db, ACC_RETENCIONES_FAVOR).id,
                    description=f"Retención {sale.withholding_number or ''}",
                    debit=round(withholding, 2),
                    credit=0.0,
                ))
            # Crédito: ingresos por ventas
            lines.append(JournalEntryLine(
                entry_id=entry.id,
                account_id=AccountingService._account(db, sales_code).id,
                description=f"Venta {sale.invoice_number}",
                debit=0.0,
                credit=round(subtotal, 2),
            ))
            # Crédito: IVA cobrado (pasivo)
            if tax > 0:
                lines.append(JournalEntryLine(
                    entry_id=entry.id,
                    account_id=AccountingService._account(db, ACC_IVA_VENTAS).id,
                    description=f"IVA 15% factura {sale.invoice_number}",
                    debit=0.0,
                    credit=round(tax, 2),
                ))

            for ln in lines:
                db.add(ln)

            total_d = sum(l.debit for l in lines)
            total_c = sum(l.credit for l in lines)
            entry.total_debit = round(total_d, 2)
            entry.total_credit = round(total_c, 2)
            db.flush()
            return entry

        except Exception as e:
            print(f"[CONTABILIDAD] Error en asiento de venta {sale.id}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Asiento automático de GASTO
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_expense_journal_entry(db: Session, expense: Expense) -> Optional[JournalEntry]:
        """
        Asiento automático al registrar un gasto:
          Dr. Cuenta de Gasto (5.2.XXX)            [amount]
          Dr. IVA en Compras (1.1.04.001)          [tax_amount]  (si > 0)
            Cr. Caja General (1.1.01.001)           [amount + tax]  (pago efectivo)
        Para gastos a crédito, usar Proveedores (2.1.01.001).
        """
        if not expense.branch_id:
            return None

        from ..models.core import Branch, Company
        branch = db.get(Branch, expense.branch_id)
        if not branch or not branch.company_id:
            return None
        company_id = branch.company_id

        try:
            # Determinar cuenta de gasto según categoría
            expense_account_code = AccountingService._resolve_expense_account(db, expense)

            amount = float(expense.amount or 0)
            tax    = float(expense.tax_amount or 0)

            period = AccountingService.get_or_create_period(db, company_id, expense.timestamp or datetime.utcnow())
            number = AccountingService.next_entry_number(db, company_id, (expense.timestamp or datetime.utcnow()).year)

            entry = JournalEntry(
                company_id=company_id,
                period_id=period.id if period else None,
                entry_number=number,
                entry_date=expense.timestamp or datetime.utcnow(),
                description=f"Gasto: {expense.description[:80]}",
                reference=expense.invoice_reference or f"GAS-{expense.id}",
                entry_type="GASTO",
                status="APROBADO",
                source_type="Expense",
                source_id=expense.id,
            )
            db.add(entry)
            db.flush()

            lines = []
            # Débito: cuenta de gasto
            lines.append(JournalEntryLine(
                entry_id=entry.id,
                account_id=AccountingService._account(db, expense_account_code).id,
                description=expense.description[:100],
                debit=round(amount, 2),
                credit=0.0,
            ))
            # Débito: IVA en compras (crédito tributario)
            if tax > 0:
                lines.append(JournalEntryLine(
                    entry_id=entry.id,
                    account_id=AccountingService._account(db, ACC_IVA_COMPRAS).id,
                    description="IVA crédito tributario",
                    debit=round(tax, 2),
                    credit=0.0,
                ))
            # Crédito: salida de caja
            lines.append(JournalEntryLine(
                entry_id=entry.id,
                account_id=AccountingService._account(db, ACC_CAJA_GENERAL).id,
                description=f"Pago gasto {expense.provider_name or ''}",
                debit=0.0,
                credit=round(amount + tax, 2),
            ))

            for ln in lines:
                db.add(ln)

            entry.total_debit  = round(sum(l.debit  for l in lines), 2)
            entry.total_credit = round(sum(l.credit for l in lines), 2)
            db.flush()
            return entry

        except Exception as e:
            print(f"[CONTABILIDAD] Error en asiento de gasto {expense.id}: {e}")
            return None

    @staticmethod
    def _resolve_expense_account(db: Session, expense: Expense) -> str:
        """
        Mapea el nombre de la categoría de gasto a su cuenta contable.
        Si la categoría tiene account_code configurado, lo usa; si no, fallback genérico.
        """
        from ..models.expenses import ExpenseCategory
        cat = db.get(ExpenseCategory, expense.category_id)
        if cat and hasattr(cat, "accounting_account_code") and cat.accounting_account_code:
            return cat.accounting_account_code

        # Mapeo por nombre de categoría (insensitive)
        name = (cat.name if cat else "").lower()
        mapping = {
            "arriendo": "5.2.008", "alquiler": "5.2.008",
            "luz": "5.2.009", "agua": "5.2.009", "internet": "5.2.009", "teléfono": "5.2.009",
            "suministro": "5.2.010", "material": "5.2.010",
            "mantenimiento": "5.2.011", "reparación": "5.2.011",
            "publicidad": "5.2.013", "marketing": "5.2.013",
            "transporte": "5.2.014", "movilización": "5.2.014",
            "sueldo": "5.2.001", "salario": "5.2.001",
            "iess": "5.2.003",
        }
        for key, code in mapping.items():
            if key in name:
                return code
        return ACC_OTROS_GASTOS  # 5.2.019 — Otros Gastos

    # ─────────────────────────────────────────────────────────────────────────
    # Asiento de CIERRE DE CAJA (diferencia sobrante/faltante)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def create_cash_close_journal_entry(db: Session, session, company_id: int) -> Optional[JournalEntry]:
        """
        Registra la diferencia de caja al cierre:
          Sobrante → Dr. Caja / Cr. Sobrante de Caja (ingreso)
          Faltante → Dr. Faltante de Caja (gasto) / Cr. Caja
        """
        diff = float(session.difference or 0)
        if abs(diff) < 0.01:
            return None

        try:
            period = AccountingService.get_or_create_period(db, company_id, session.closed_at or datetime.utcnow())
            number = AccountingService.next_entry_number(db, company_id, (session.closed_at or datetime.utcnow()).year)
            is_surplus = diff > 0

            entry = JournalEntry(
                company_id=company_id,
                period_id=period.id if period else None,
                entry_number=number,
                entry_date=session.closed_at or datetime.utcnow(),
                description=f"{'Sobrante' if is_surplus else 'Faltante'} de caja — sesión #{session.id}",
                reference=f"CAJA-{session.id}",
                entry_type="CAJA_CIERRE",
                status="APROBADO",
                source_type="CashSession",
                source_id=session.id,
            )
            db.add(entry)
            db.flush()

            amt = round(abs(diff), 2)
            caja_acc = AccountingService._account(db, ACC_CAJA_GENERAL)

            if is_surplus:
                lines = [
                    JournalEntryLine(entry_id=entry.id, account_id=caja_acc.id,
                                     description="Sobrante de caja", debit=amt, credit=0.0),
                    JournalEntryLine(entry_id=entry.id,
                                     account_id=AccountingService._account(db, ACC_SOBRANTE_CAJA).id,
                                     description="Sobrante de caja", debit=0.0, credit=amt),
                ]
            else:
                lines = [
                    JournalEntryLine(entry_id=entry.id,
                                     account_id=AccountingService._account(db, ACC_FALTANTE_CAJA).id,
                                     description="Faltante de caja", debit=amt, credit=0.0),
                    JournalEntryLine(entry_id=entry.id, account_id=caja_acc.id,
                                     description="Faltante de caja", debit=0.0, credit=amt),
                ]

            for ln in lines:
                db.add(ln)
            entry.total_debit  = amt
            entry.total_credit = amt
            db.flush()
            return entry

        except Exception as e:
            print(f"[CONTABILIDAD] Error en asiento de cierre de caja sesión {session.id}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Estados Financieros
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_trial_balance(db: Session, company_id: int, start_date: date, end_date: date) -> list:
        """
        Balance de Comprobación: saldo deudor y acreedor por cuenta.
        Solo incluye cuentas con movimientos en el período.
        """
        end_dt = datetime.combine(end_date, datetime.max.time())
        start_dt = datetime.combine(start_date, datetime.min.time())

        rows = (
            db.query(
                AccountPlan.code,
                AccountPlan.name,
                AccountPlan.account_type,
                AccountPlan.nature,
                func.sum(JournalEntryLine.debit).label("total_debit"),
                func.sum(JournalEntryLine.credit).label("total_credit"),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == AccountPlan.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
            .filter(
                JournalEntry.company_id == company_id,
                JournalEntry.status != "ANULADO",
                JournalEntry.entry_date >= start_dt,
                JournalEntry.entry_date <= end_dt,
            )
            .group_by(AccountPlan.code, AccountPlan.name, AccountPlan.account_type, AccountPlan.nature)
            .order_by(AccountPlan.code)
            .all()
        )

        result = []
        for r in rows:
            debit  = float(r.total_debit or 0)
            credit = float(r.total_credit or 0)
            balance = debit - credit  # positivo = saldo deudor, negativo = saldo acreedor
            result.append({
                "code": r.code,
                "name": r.name,
                "type": r.account_type,
                "nature": r.nature,
                "total_debit": round(debit, 2),
                "total_credit": round(credit, 2),
                "balance_debit": round(max(balance, 0), 2),
                "balance_credit": round(max(-balance, 0), 2),
            })
        return result

    @staticmethod
    def get_balance_sheet(db: Session, company_id: int, as_of_date: date) -> dict:
        """
        Estado de Situación Financiera (NIIF NIC 1).
        Acumula todos los movimientos históricos hasta la fecha indicada.
        """
        end_dt = datetime.combine(as_of_date, datetime.max.time())

        def account_balance(code_prefix: str) -> float:
            """Saldo neto de todas las cuentas bajo el prefijo dado."""
            rows = (
                db.query(
                    AccountPlan.code,
                    AccountPlan.nature,
                    func.sum(JournalEntryLine.debit).label("d"),
                    func.sum(JournalEntryLine.credit).label("c"),
                )
                .join(JournalEntryLine, JournalEntryLine.account_id == AccountPlan.id)
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
                .filter(
                    JournalEntry.company_id == company_id,
                    JournalEntry.status != "ANULADO",
                    JournalEntry.entry_date <= end_dt,
                    AccountPlan.code.like(f"{code_prefix}%"),
                    AccountPlan.allows_entries == True,
                )
                .group_by(AccountPlan.code, AccountPlan.nature)
                .all()
            )
            total = 0.0
            for r in rows:
                d, c = float(r.d or 0), float(r.c or 0)
                # Naturaleza deudora: saldo = Débito - Crédito
                # Naturaleza acreedora: saldo = Crédito - Débito
                total += (d - c) if r.nature == "DEUDORA" else (c - d)
            return round(total, 2)

        activo_corriente   = account_balance("1.1")
        activo_no_corriente= account_balance("1.2")
        total_activos      = round(activo_corriente + activo_no_corriente, 2)

        pasivo_corriente   = account_balance("2.1")
        pasivo_no_corriente= account_balance("2.2")
        total_pasivos      = round(pasivo_corriente + pasivo_no_corriente, 2)

        capital            = account_balance("3.1")
        reservas           = account_balance("3.2")
        resultados         = account_balance("3.3")
        # Resultado del ejercicio = Ingresos - Gastos del período
        ingresos_total     = account_balance("4")
        gastos_total       = account_balance("5")
        resultado_ejercicio= round(ingresos_total - gastos_total, 2)
        total_patrimonio   = round(capital + reservas + resultados + resultado_ejercicio, 2)

        return {
            "as_of_date": str(as_of_date),
            "activos": {
                "corrientes": activo_corriente,
                "no_corrientes": activo_no_corriente,
                "total": total_activos,
            },
            "pasivos": {
                "corrientes": pasivo_corriente,
                "no_corrientes": pasivo_no_corriente,
                "total": total_pasivos,
            },
            "patrimonio": {
                "capital": capital,
                "reservas": reservas,
                "resultados_acumulados": resultados,
                "resultado_ejercicio": resultado_ejercicio,
                "total": total_patrimonio,
            },
            "total_pasivos_patrimonio": round(total_pasivos + total_patrimonio, 2),
            "balanced": abs(total_activos - (total_pasivos + total_patrimonio)) < 0.05,
        }

    @staticmethod
    def get_income_statement(db: Session, company_id: int, start_date: date, end_date: date) -> dict:
        """
        Estado de Resultados Integrales (NIIF NIC 1).
        Ingresos - Costos - Gastos = Utilidad/Pérdida del Período.
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt   = datetime.combine(end_date, datetime.max.time())

        def group_sum(code_prefix: str) -> float:
            rows = (
                db.query(
                    AccountPlan.nature,
                    func.sum(JournalEntryLine.debit).label("d"),
                    func.sum(JournalEntryLine.credit).label("c"),
                )
                .join(JournalEntryLine, JournalEntryLine.account_id == AccountPlan.id)
                .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
                .filter(
                    JournalEntry.company_id == company_id,
                    JournalEntry.status != "ANULADO",
                    JournalEntry.entry_date >= start_dt,
                    JournalEntry.entry_date <= end_dt,
                    AccountPlan.code.like(f"{code_prefix}%"),
                    AccountPlan.allows_entries == True,
                )
                .group_by(AccountPlan.nature)
                .all()
            )
            total = 0.0
            for r in rows:
                d, c = float(r.d or 0), float(r.c or 0)
                total += (d - c) if r.nature == "DEUDORA" else (c - d)
            return round(total, 2)

        ventas_brutas   = group_sum("4.1")
        otros_ingresos  = group_sum("4.2")
        costo_ventas    = group_sum("5.1")
        gastos_operac   = group_sum("5.2")
        gastos_financ   = group_sum("5.3")

        utilidad_bruta  = round(ventas_brutas - costo_ventas, 2)
        utilidad_operac = round(utilidad_bruta - gastos_operac, 2)
        utilidad_neta   = round(utilidad_operac + otros_ingresos - gastos_financ, 2)

        return {
            "period": f"{start_date} / {end_date}",
            "ventas_brutas": ventas_brutas,
            "costo_ventas": costo_ventas,
            "utilidad_bruta": utilidad_bruta,
            "gastos_operacionales": gastos_operac,
            "utilidad_operacional": utilidad_operac,
            "otros_ingresos": otros_ingresos,
            "gastos_financieros": gastos_financ,
            "utilidad_neta": utilidad_neta,
            "margen_bruto_pct": round((utilidad_bruta / ventas_brutas * 100) if ventas_brutas else 0, 1),
            "margen_neto_pct":  round((utilidad_neta  / ventas_brutas * 100) if ventas_brutas else 0, 1),
        }

    @staticmethod
    def get_cash_flow(db: Session, company_id: int, start_date: date, end_date: date) -> dict:
        """
        Estado de Flujo de Efectivo — método directo (NIC 7).
        Agrupa movimientos de la cuenta Caja General.
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt   = datetime.combine(end_date, datetime.max.time())

        caja_acc = db.query(AccountPlan).filter_by(code=ACC_CAJA_GENERAL).first()
        if not caja_acc:
            return {}

        # Movimientos de Caja por tipo de asiento
        movements = (
            db.query(
                JournalEntry.entry_type,
                func.sum(JournalEntryLine.debit).label("d"),
                func.sum(JournalEntryLine.credit).label("c"),
            )
            .join(JournalEntryLine, JournalEntryLine.entry_id == JournalEntry.id)
            .filter(
                JournalEntry.company_id == company_id,
                JournalEntry.status != "ANULADO",
                JournalEntry.entry_date >= start_dt,
                JournalEntry.entry_date <= end_dt,
                JournalEntryLine.account_id == caja_acc.id,
            )
            .group_by(JournalEntry.entry_type)
            .all()
        )

        actividades = {}
        for m in movements:
            net = float(m.d or 0) - float(m.c or 0)
            actividades[m.entry_type] = round(net, 2)

        cobros_clientes = actividades.get("VENTA", 0)
        pagos_gastos    = actividades.get("GASTO", 0)
        pagos_banco     = actividades.get("BANCO", 0)
        ajustes_caja    = actividades.get("CAJA_CIERRE", 0)
        otros           = sum(v for k, v in actividades.items() if k not in ("VENTA", "GASTO", "BANCO", "CAJA_CIERRE"))

        neto_operacional  = round(cobros_clientes + pagos_gastos + ajustes_caja, 2)
        neto_financiamiento = round(pagos_banco, 2)
        flujo_neto        = round(neto_operacional + neto_financiamiento + otros, 2)

        return {
            "period": f"{start_date} / {end_date}",
            "actividades_operacion": {
                "cobros_clientes": cobros_clientes,
                "pagos_proveedores_gastos": pagos_gastos,
                "ajustes_caja": ajustes_caja,
                "neto": neto_operacional,
            },
            "actividades_financiamiento": {
                "movimientos_banco": pagos_banco,
                "neto": neto_financiamiento,
            },
            "otros": otros,
            "flujo_neto_periodo": flujo_neto,
            "por_tipo": actividades,
        }
