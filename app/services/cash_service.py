"""
Servicio de Caja — Ciclo de vida completo de sesiones POS.
Apertura, movimientos manuales, cierre con conteo físico y cálculo de diferencias.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from ..models.cash import CashSession, CashTransaction, CashCount
from ..models.sales import Sale, SalePayment, PaymentMethod


# SRI codes considerados "efectivo" para el flujo de caja
_CASH_SRI_CODES = {"01"}


class CashService:

    # ─────────────────────────────────────────────────────────────────────────
    # Consultas de sesión
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_open_session(db: Session, register_id: int) -> Optional[CashSession]:
        return db.query(CashSession).filter_by(
            register_id=register_id, status="ABIERTA"
        ).first()

    @staticmethod
    def get_open_session_by_branch(db: Session, branch_id: int) -> Optional[CashSession]:
        return db.query(CashSession).filter_by(
            branch_id=branch_id, status="ABIERTA"
        ).first()

    # ─────────────────────────────────────────────────────────────────────────
    # Apertura de caja
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def open_session(
        db: Session,
        register_id: int,
        branch_id: int,
        user_id: int,
        opening_amount: float,
        notes: Optional[str] = None,
    ) -> CashSession:
        existing = CashService.get_open_session(db, register_id)
        if existing:
            raise ValueError(f"Ya existe una sesión abierta (#{existing.id}) para esta caja.")

        session = CashSession(
            register_id=register_id,
            branch_id=branch_id,
            opened_by_id=user_id,
            opened_at=datetime.utcnow(),
            status="ABIERTA",
            opening_amount=round(opening_amount, 2),
            notes=notes,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    # ─────────────────────────────────────────────────────────────────────────
    # Movimientos manuales dentro de la sesión
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def add_cash_movement(
        db: Session,
        session_id: int,
        user_id: int,
        transaction_type: str,   # INGRESO | EGRESO | RETIRO | FONDO_CAMBIO
        amount: float,
        description: str,
        reference_id: Optional[int] = None,
        reference_type: Optional[str] = None,
    ) -> CashTransaction:
        session = db.get(CashSession, session_id)
        if not session or session.status != "ABIERTA":
            raise ValueError("Sesión de caja no encontrada o ya cerrada.")

        trx = CashTransaction(
            session_id=session_id,
            user_id=user_id,
            transaction_type=transaction_type,
            amount=round(abs(amount), 2),
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            created_at=datetime.utcnow(),
        )
        db.add(trx)
        db.commit()
        db.refresh(trx)
        return trx

    # ─────────────────────────────────────────────────────────────────────────
    # Resumen en tiempo real
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_session_summary(db: Session, session: CashSession) -> dict:
        """
        Calcula en tiempo real los totales de la sesión:
        ventas, gastos, movimientos manuales y saldo esperado en caja.
        """
        # Ventas de la sesión (por rango de tiempo)
        from ..models.expenses import Expense
        from sqlalchemy import func

        sales = db.query(Sale).filter(
            Sale.branch_id == session.branch_id,
            Sale.status == "FACTURADO",
            Sale.sale_date >= session.opened_at,
        )
        if session.closed_at:
            sales = sales.filter(Sale.sale_date <= session.closed_at)
        sales_list = sales.all()

        total_sales       = sum(float(s.total or 0) for s in sales_list)
        total_sales_cash  = 0.0
        total_sales_card  = 0.0

        for s in sales_list:
            for pay in db.query(SalePayment).filter_by(sale_id=s.id).all():
                pm = db.query(PaymentMethod).get(pay.payment_method_id)
                if pm and pm.sri_code in _CASH_SRI_CODES:
                    total_sales_cash += float(pay.amount or 0)
                else:
                    total_sales_card += float(pay.amount or 0)

        # Gastos en efectivo del período
        expenses_q = db.query(Expense).filter(
            Expense.branch_id == session.branch_id,
            Expense.timestamp >= session.opened_at,
        )
        if session.closed_at:
            expenses_q = expenses_q.filter(Expense.timestamp <= session.closed_at)
        total_expenses = sum(float(e.amount or 0) + float(e.tax_amount or 0) for e in expenses_q.all())

        # Movimientos manuales
        manual_txns = db.query(CashTransaction).filter_by(session_id=session.id).all()
        total_in  = sum(t.amount for t in manual_txns if t.transaction_type in ("INGRESO", "FONDO_CAMBIO"))
        total_out = sum(t.amount for t in manual_txns if t.transaction_type in ("EGRESO", "RETIRO"))

        # Saldo esperado = apertura + ventas efectivo + ingresos manuales - gastos - retiros
        expected = round(
            float(session.opening_amount or 0)
            + total_sales_cash
            + total_in
            - total_expenses
            - total_out,
            2,
        )

        return {
            "session_id": session.id,
            "status": session.status,
            "opened_at": session.opened_at.isoformat(),
            "opening_amount": float(session.opening_amount or 0),
            "total_sales": round(total_sales, 2),
            "total_sales_cash": round(total_sales_cash, 2),
            "total_sales_card": round(total_sales_card, 2),
            "total_expenses": round(total_expenses, 2),
            "total_cash_in": round(total_in, 2),
            "total_cash_out": round(total_out, 2),
            "expected_amount": expected,
            "sale_count": len(sales_list),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Cierre de caja
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def close_session(
        db: Session,
        session_id: int,
        user_id: int,
        declared_amount: float,
        denominations: Optional[list] = None,  # [{denomination, quantity}]
        notes: Optional[str] = None,
        company_id: Optional[int] = None,
    ) -> CashSession:
        session = db.get(CashSession, session_id)
        if not session or session.status != "ABIERTA":
            raise ValueError("Sesión no encontrada o ya cerrada.")

        session.closed_at      = datetime.utcnow()
        session.closed_by_id   = user_id
        session.status         = "CERRADA"
        session.declared_amount = round(declared_amount, 2)
        if notes:
            session.notes = notes

        # Calcular totales
        summary = CashService.get_session_summary(db, session)
        session.total_sales      = summary["total_sales"]
        session.total_sales_cash = summary["total_sales_cash"]
        session.total_sales_card = summary["total_sales_card"]
        session.total_expenses   = summary["total_expenses"]
        session.total_cash_in    = summary["total_cash_in"]
        session.total_cash_out   = summary["total_cash_out"]
        session.expected_amount  = summary["expected_amount"]
        session.difference       = round(declared_amount - summary["expected_amount"], 2)

        # Guardar conteo de denominaciones
        if denominations:
            for d in denominations:
                qty = int(d.get("quantity", 0))
                den = float(d.get("denomination", 0))
                if qty > 0:
                    db.add(CashCount(
                        session_id=session.id,
                        denomination=den,
                        quantity=qty,
                        subtotal=round(den * qty, 2),
                    ))

        db.flush()

        # Asiento contable de diferencia de caja
        if company_id and abs(session.difference) >= 0.01:
            from ..services.accounting_service import AccountingService
            je = AccountingService.create_cash_close_journal_entry(db, session, company_id)
            if je:
                session.closing_journal_entry_id = je.id

        db.commit()
        db.refresh(session)
        return session

    # ─────────────────────────────────────────────────────────────────────────
    # Flujo de caja (histórico entre fechas)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def get_cash_flow_report(db: Session, branch_id: int, start: datetime, end: datetime) -> dict:
        """Reporte de flujo de caja por sesiones entre dos fechas."""
        sessions = db.query(CashSession).filter(
            CashSession.branch_id == branch_id,
            CashSession.opened_at >= start,
            CashSession.opened_at <= end,
        ).order_by(CashSession.opened_at).all()

        rows = []
        for s in sessions:
            rows.append({
                "session_id": s.id,
                "date": s.opened_at.date().isoformat(),
                "status": s.status,
                "opening": float(s.opening_amount or 0),
                "sales_cash": float(s.total_sales_cash or 0),
                "expenses": float(s.total_expenses or 0),
                "cash_in": float(s.total_cash_in or 0),
                "cash_out": float(s.total_cash_out or 0),
                "expected": float(s.expected_amount or 0),
                "declared": float(s.declared_amount or 0),
                "difference": float(s.difference or 0),
            })

        return {
            "branch_id": branch_id,
            "from": start.date().isoformat(),
            "to": end.date().isoformat(),
            "sessions": rows,
            "total_sales_cash": round(sum(r["sales_cash"] for r in rows), 2),
            "total_expenses":   round(sum(r["expenses"] for r in rows), 2),
            "total_difference": round(sum(r["difference"] for r in rows), 2),
        }
