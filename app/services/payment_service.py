"""
Servicio de Cobros — Formas de pago vigentes en Ecuador (Tabla 24 SRI).

Responsabilidades:
  • Sembrar / actualizar el catálogo de métodos de pago.
  • Validar los pagos de una venta (pago único o mixto, vuelto, referencias).
  • Registrar transferencias / depósitos / billeteras como movimiento bancario
    en la cuenta destino de la empresa (base para la conciliación NIC 7).
  • Verificar o rechazar transferencias contra el estado de cuenta.
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.sales import PaymentMethod, SalePayment, Sale
from ..models.banking import BankAccount, BankTransaction


# ─── Catálogo de formas de pago (Ecuador) ─────────────────────────────────────
# code, name, sri_code, category, icon, requires_reference, requires_bank_account,
# requires_origin_bank, is_active, description
PAYMENT_METHODS_CATALOG = [
    ("EFECTIVO",          "Efectivo",                          "01", "EFECTIVO",      "💵", False, False, False, True,
     "Pago en billetes y monedas (sin utilización del sistema financiero)."),
    ("TARJETA_DEBITO",    "Tarjeta de Débito",                 "16", "TARJETA",       "💳", True,  False, False, True,
     "Datáfono / POS bancario. Registrar N° de voucher y lote."),
    ("TARJETA_CREDITO",   "Tarjeta de Crédito",                "19", "TARJETA",       "💳", True,  False, False, True,
     "Visa, Mastercard, Diners, Amex, Discover. Corriente o diferido."),
    ("TARJETA_PREPAGO",   "Tarjeta Prepago",                   "18", "TARJETA",       "🎫", True,  False, False, True,
     "Tarjetas prepago / gift cards bancarias."),
    ("TRANSFERENCIA",     "Transferencia Bancaria Directa",    "20", "TRANSFERENCIA", "🏦", True,  True,  True,  True,
     "Transferencia directa (interbancaria SPI o mismo banco) a la cuenta de la empresa."),
    ("DEPOSITO",          "Depósito Bancario",                 "20", "DEPOSITO",      "🧾", True,  True,  False, True,
     "Depósito en ventanilla, agente o corresponsal no bancario."),
    ("BILLETERA_DIGITAL", "Billetera Digital / Pago QR",       "20", "BILLETERA",     "📱", True,  True,  True,  True,
     "DeUna!, Peigo, JEP Móvil, Wallet Produbanco, Banco Guayaquil QR, etc."),
    ("PASARELA",          "Pasarela / Link de Pago",           "19", "PASARELA",      "🌐", True,  False, True,  True,
     "PayPhone, Kushki, Datafast, Nuvei/Paymentez, PlacetoPay, link de pago."),
    ("CHEQUE",            "Cheque",                            "20", "CHEQUE",        "📝", True,  False, True,  True,
     "Cheque a la vista o posfechado. Queda en caja hasta su depósito."),
    ("CREDITO_DIRECTO",   "Crédito Directo (Cuenta por Cobrar)", "20", "CREDITO",     "📒", False, False, False, True,
     "Venta a crédito con plazo; requiere cliente identificado (no Consumidor Final)."),
    ("COMPENSACION",      "Compensación de Deudas",            "15", "COMPENSACION",  "🔁", True,  False, False, False,
     "Cruce de cuentas con un proveedor que también es cliente."),
    ("ENDOSO",            "Endoso de Títulos",                 "21", "ENDOSO",        "📜", True,  False, False, False,
     "Endoso de letras de cambio, pagarés u otros títulos valor."),
    ("DINERO_ELECTRONICO","Dinero Electrónico",                "17", "DINERO_ELECTRONICO", "🪙", True, False, False, False,
     "Código SRI 17 (sistema BCE descontinuado; se mantiene por compatibilidad)."),
    ("RETENCION",         "Retención",                         "20", "RETENCION",     "📄", True,  False, False, True,
     "Uso interno: retenciones en la fuente/IVA recibidas del cliente."),
]

# Categorías y su tratamiento
CASH_CATEGORIES       = {"EFECTIVO"}
CARD_CATEGORIES       = {"TARJETA", "PASARELA"}
BANK_CATEGORIES       = {"TRANSFERENCIA", "DEPOSITO", "BILLETERA", "DINERO_ELECTRONICO"}
VERIFIABLE_CATEGORIES = BANK_CATEGORIES | {"PASARELA", "CHEQUE"}

# Bancos, cooperativas y billeteras más comunes en Ecuador (origen de fondos)
ECUADOR_FINANCIAL_ENTITIES = {
    "Bancos privados": [
        "Banco Pichincha", "Banco Guayaquil", "Produbanco", "Banco del Pacífico",
        "Banco Bolivariano", "Banco Internacional", "Banco del Austro", "Banco de Machala",
        "Banco General Rumiñahui", "Banco de Loja", "Banco Solidario", "Banco ProCredit",
        "Banco Amazonas", "Banco Diners Club", "Banco Codesarrollo", "Banco Capital",
        "Banco Comercial de Manabí", "Banco Litoral", "Banco Coopnacional", "Banco D-MIRO",
        "Banco Finca", "Banco Visionfund", "Banco Delbank", "Citibank Ecuador",
    ],
    "Banca pública": [
        "BanEcuador", "Banco Central del Ecuador", "BIESS", "Corporación Financiera Nacional",
    ],
    "Cooperativas de ahorro y crédito": [
        "Coop. JEP (Juventud Ecuatoriana Progresista)", "Coop. Jardín Azuayo", "Coop. Policía Nacional",
        "Coop. 29 de Octubre", "Coop. Alianza del Valle", "Coop. Cooprogreso", "Coop. Andalucía",
        "Coop. Oscus", "Coop. San Francisco", "Coop. Mushuc Runa", "Coop. Riobamba",
        "Coop. CACPECO", "Coop. Fernando Daquilema", "Coop. Atuntaqui", "Coop. Pablo Muñoz Vega",
        "Coop. Tulcán", "Coop. Chibuleo", "Coop. Ambato", "Coop. Vicentina", "Coop. Erco",
    ],
    "Mutualistas": [
        "Mutualista Pichincha", "Mutualista Azuay", "Mutualista Imbabura", "Mutualista Ambato",
    ],
    "Billeteras / Pasarelas": [
        "DeUna! (Banco Pichincha)", "Peigo", "JEP Móvil", "Wallet Produbanco", "Banco Guayaquil - Pago QR",
        "Bimo", "PayPhone", "Kushki", "Datafast", "Nuvei / Paymentez", "PlacetoPay", "PayPal",
    ],
}

CARD_BRANDS = ["VISA", "MASTERCARD", "DINERS CLUB", "AMERICAN EXPRESS", "DISCOVER", "ALIA", "UNIONPAY", "OTRA"]


def _q(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PaymentService:

    # ─────────────────────────────────────────────────────────────────────────
    # Catálogo
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def seed_payment_methods(db: Session) -> None:
        """
        Inserta o completa el catálogo de formas de pago.
        Respeta los IDs existentes (ej. id=1 Efectivo) emparejando por code o por nombre.
        """
        existing = db.query(PaymentMethod).all()
        legacy_name_map = {
            "efectivo": "EFECTIVO",
            "tarjeta de crédito": "TARJETA_CREDITO",
            "tarjeta de credito": "TARJETA_CREDITO",
            "tarjeta de débito": "TARJETA_DEBITO",
            "tarjeta de debito": "TARJETA_DEBITO",
            "transferencia": "TRANSFERENCIA",
            "retención": "RETENCION",
            "retencion": "RETENCION",
        }
        by_code = {}
        for pm in existing:
            code = pm.code
            if not code:
                code = legacy_name_map.get((pm.name or "").strip().lower())
                if not code and "reten" in (pm.name or "").lower():
                    code = "RETENCION"
            if code and code not in by_code:
                by_code[code] = pm

        for order, row in enumerate(PAYMENT_METHODS_CATALOG, start=1):
            (code, name, sri, category, icon, req_ref, req_bank, req_origin, active, desc) = row
            pm = by_code.get(code)
            if pm is None:
                pm = PaymentMethod(name=name, sri_code=sri, is_active=active)
                db.add(pm)
            else:
                # Conserva el estado activo definido por el usuario si ya tenía metadatos
                if not pm.code:
                    pm.is_active = active if pm.is_active is None else pm.is_active
                pm.name = name
                pm.sri_code = sri
            pm.code = code
            pm.category = category
            pm.icon = icon
            pm.sort_order = order
            pm.requires_reference = req_ref
            pm.requires_bank_account = req_bank
            pm.requires_origin_bank = req_origin
            pm.description = desc
        db.commit()

    @staticmethod
    def serialize_method(pm: PaymentMethod) -> dict:
        return {
            "id": pm.id,
            "code": pm.code,
            "name": pm.name,
            "sri_code": pm.sri_code,
            "category": pm.category,
            "icon": pm.icon,
            "is_active": pm.is_active,
            "sort_order": pm.sort_order,
            "requires_reference": bool(pm.requires_reference),
            "requires_bank_account": bool(pm.requires_bank_account),
            "requires_origin_bank": bool(pm.requires_origin_bank),
            "description": pm.description,
        }

    @staticmethod
    def get_by_code(db: Session, code: str) -> Optional[PaymentMethod]:
        return db.query(PaymentMethod).filter_by(code=code).first()

    # ─────────────────────────────────────────────────────────────────────────
    # Validación y registro de pagos de una venta
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def build_sale_payments(db: Session, sale: Sale, payments_data: list, amount_due: Decimal) -> List[SalePayment]:
        """
        Valida y construye los SalePayment de una venta.

        :param payments_data: lista de SalePaymentCreate (pydantic)
        :param amount_due: total a cobrar (total - retenciones)
        Reglas:
          • Solo el efectivo puede exceder el saldo (se calcula vuelto).
          • La suma de pagos debe cubrir exactamente el total a cobrar.
          • Transferencias / depósitos / billeteras: comprobante obligatorio y no repetido.
          • Crédito directo: no permitido a Consumidor Final.
        """
        from fastapi import HTTPException

        amount_due = _q(amount_due)
        if not payments_data:
            raise HTTPException(status_code=400, detail="Debe registrar al menos una forma de pago.")

        methods = {}
        non_cash_total = Decimal("0")
        cash_total = Decimal("0")
        for p in payments_data:
            pm = db.get(PaymentMethod, p.payment_method_id)
            if not pm or not pm.is_active:
                raise HTTPException(status_code=400, detail=f"Forma de pago {p.payment_method_id} no existe o está inactiva.")
            if pm.category == "RETENCION":
                raise HTTPException(status_code=400, detail="Las retenciones se registran en los campos de retención, no como forma de pago.")
            amt = _q(p.amount)
            if amt <= 0:
                raise HTTPException(status_code=400, detail=f"El monto de '{pm.name}' debe ser mayor a 0.")
            methods[id(p)] = pm
            if pm.category in CASH_CATEGORIES:
                cash_total += amt
            else:
                non_cash_total += amt

        if non_cash_total > amount_due:
            raise HTTPException(
                status_code=400,
                detail=f"Los pagos no efectivo (${non_cash_total}) superan el total a cobrar (${amount_due}). Solo el efectivo admite vuelto.",
            )
        if cash_total + non_cash_total < amount_due:
            raise HTTPException(
                status_code=400,
                detail=f"Pago incompleto: recibido ${cash_total + non_cash_total} de ${amount_due}. Falta ${amount_due - cash_total - non_cash_total}.",
            )

        # Vuelto total (solo sale del efectivo)
        change_total = (cash_total + non_cash_total) - amount_due
        cash_to_apply = cash_total - change_total

        result: List[SalePayment] = []
        seen_refs = set()
        for p in payments_data:
            pm = methods[id(p)]
            amt = _q(p.amount)
            cat = pm.category or ""
            reference = (p.reference or "").strip() or None

            # ── Validaciones por categoría ─────────────────────────────────
            if pm.requires_reference and not reference and cat not in CASH_CATEGORIES:
                label = "N° de cheque" if cat == "CHEQUE" else "N° de comprobante / voucher"
                raise HTTPException(status_code=400, detail=f"{label} obligatorio para '{pm.name}'.")

            bank_account = None
            if cat in BANK_CATEGORIES:
                if p.bank_account_id:
                    bank_account = db.get(BankAccount, p.bank_account_id)
                    if not bank_account or not bank_account.is_active:
                        raise HTTPException(status_code=400, detail="Cuenta bancaria destino no válida o inactiva.")
                elif pm.requires_bank_account and db.query(BankAccount).filter_by(is_active=True).count() > 0:
                    raise HTTPException(status_code=400, detail=f"Seleccione la cuenta bancaria destino para '{pm.name}'.")

                # Evitar reutilizar el mismo comprobante (fraude por captura repetida)
                key = (p.bank_account_id, reference.upper() if reference else None)
                if reference:
                    if key in seen_refs:
                        raise HTTPException(status_code=400, detail=f"Comprobante {reference} repetido en esta venta.")
                    seen_refs.add(key)
                    dup = db.query(SalePayment).join(PaymentMethod).filter(
                        PaymentMethod.category.in_(list(BANK_CATEGORIES)),
                        SalePayment.reference == reference,
                        SalePayment.status != "RECHAZADO",
                    )
                    if p.bank_account_id:
                        dup = dup.filter(SalePayment.bank_account_id == p.bank_account_id)
                    if dup.first():
                        raise HTTPException(
                            status_code=409,
                            detail=f"El comprobante {reference} ya fue registrado en otra venta. Verifique la transferencia.",
                        )

            if pm.requires_origin_bank and not (p.origin_bank or "").strip() and cat in {"TRANSFERENCIA", "CHEQUE"}:
                raise HTTPException(status_code=400, detail=f"Indique el banco de origen para '{pm.name}'.")

            if cat == "CREDITO":
                if (sale.customer_id or "9999999999999") == "9999999999999":
                    raise HTTPException(status_code=400, detail="El crédito directo requiere un cliente identificado (cédula o RUC).")
                if not p.term_days or p.term_days <= 0:
                    raise HTTPException(status_code=400, detail="Indique el plazo en días para el crédito directo.")

            if p.card_last4 and (len(p.card_last4) != 4 or not p.card_last4.isdigit()):
                raise HTTPException(status_code=400, detail="Los últimos 4 dígitos de la tarjeta deben ser numéricos.")

            payment_date = None
            if p.payment_date:
                try:
                    payment_date = datetime.strptime(p.payment_date[:10], "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(status_code=400, detail="Fecha de pago inválida (use AAAA-MM-DD).")

            # ── Efectivo: aplicar vuelto ───────────────────────────────────
            received = None
            change = None
            applied = amt
            if cat in CASH_CATEGORIES:
                received = amt
                applied = min(amt, cash_to_apply) if cash_to_apply > 0 else Decimal("0")
                cash_to_apply -= applied
                change = received - applied
                if applied <= 0:
                    continue  # todo el billete fue vuelto (caso extremo)

            status = "REGISTRADO" if cat in VERIFIABLE_CATEGORIES else "VERIFICADO"

            result.append(SalePayment(
                sale_id=sale.id,
                payment_method_id=pm.id,
                amount=applied,
                reference=reference,
                received_amount=received,
                change_amount=change,
                bank_account_id=bank_account.id if bank_account else None,
                origin_bank=(p.origin_bank or "").strip() or None,
                payer_name=(p.payer_name or "").strip() or None,
                payer_id=(p.payer_id or "").strip() or None,
                payment_date=payment_date,
                card_brand=(p.card_brand or "").strip().upper() or None,
                card_last4=p.card_last4 or None,
                authorization_code=(p.authorization_code or "").strip() or None,
                installments=p.installments or None,
                term_days=p.term_days or None,
                status=status,
                notes=(p.notes or "").strip() or None,
                created_at=datetime.utcnow(),
            ))
        return result

    @staticmethod
    def register_bank_movement(db: Session, sale: Sale, payment: SalePayment) -> Optional[BankTransaction]:
        """
        Registra el ingreso en la cuenta bancaria destino (transferencia, depósito o billetera)
        y actualiza el saldo. Queda NO conciliado hasta la conciliación bancaria.
        """
        if not payment.bank_account_id:
            return None
        pm = db.get(PaymentMethod, payment.payment_method_id)
        if not pm or pm.category not in BANK_CATEGORIES:
            return None
        account = db.get(BankAccount, payment.bank_account_id)
        if not account:
            return None

        amount = float(payment.amount or 0)
        new_balance = round(float(account.current_balance or 0) + amount, 2)
        txn_type = "DEPOSITO" if pm.category == "DEPOSITO" else "TRANSFERENCIA_IN"
        origin = f" desde {payment.origin_bank}" if payment.origin_bank else ""
        payer = f" — {payment.payer_name}" if payment.payer_name else ""
        txn = BankTransaction(
            bank_account_id=account.id,
            transaction_date=payment.payment_date or sale.sale_date or datetime.utcnow(),
            description=f"Cobro {pm.name} factura {sale.invoice_number}{origin}{payer}"[:500],
            reference=payment.reference,
            transaction_type=txn_type,
            amount=round(amount, 2),
            balance_after=new_balance,
            journal_entry_id=getattr(sale, "journal_entry_id", None),
            source="POS",
        )
        db.add(txn)
        account.current_balance = new_balance
        db.flush()
        payment.bank_transaction_id = txn.id
        return txn

    # ─────────────────────────────────────────────────────────────────────────
    # Verificación de transferencias
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def verify_payment(db: Session, payment: SalePayment, user_id: Optional[int], notes: Optional[str] = None) -> SalePayment:
        if payment.status == "RECHAZADO":
            raise ValueError("El pago ya fue rechazado; no puede verificarse.")
        payment.status = "VERIFICADO"
        payment.verified_at = datetime.utcnow()
        payment.verified_by_id = user_id
        if notes:
            payment.notes = (f"{payment.notes} | " if payment.notes else "") + notes[:200]
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def reject_payment(db: Session, payment: SalePayment, user_id: Optional[int], reason: str) -> SalePayment:
        """
        Rechaza un pago no acreditado (ej. comprobante falso o transferencia revertida):
          • Revierte el movimiento bancario (AJUSTE negativo) y el saldo de la cuenta.
          • Reclasifica contablemente el valor a Cuentas por Cobrar Clientes.
        """
        if payment.status == "RECHAZADO":
            raise ValueError("El pago ya está rechazado.")

        sale = db.get(Sale, payment.sale_id)
        if payment.bank_transaction_id:
            original = db.get(BankTransaction, payment.bank_transaction_id)
            account = db.get(BankAccount, original.bank_account_id) if original else None
            if account:
                amount = float(payment.amount or 0)
                new_balance = round(float(account.current_balance or 0) - amount, 2)
                db.add(BankTransaction(
                    bank_account_id=account.id,
                    transaction_date=datetime.utcnow(),
                    description=f"Reverso cobro no acreditado factura {sale.invoice_number if sale else ''}: {reason}"[:500],
                    reference=payment.reference,
                    transaction_type="AJUSTE",
                    amount=-round(amount, 2),
                    balance_after=new_balance,
                    source="POS",
                ))
                account.current_balance = new_balance

        try:
            from .accounting_service import AccountingService
            if sale:
                AccountingService.create_payment_rejection_entry(db, sale, payment, reason)
        except Exception as e:  # el rechazo no debe fallar por contabilidad
            print(f"[CONTABILIDAD] Asiento de reverso no generado: {e}")

        payment.status = "RECHAZADO"
        payment.verified_at = datetime.utcnow()
        payment.verified_by_id = user_id
        payment.notes = (f"{payment.notes} | " if payment.notes else "") + f"RECHAZADO: {reason[:180]}"
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def serialize_payment(db: Session, p: SalePayment) -> dict:
        pm = p.payment_method or db.get(PaymentMethod, p.payment_method_id)
        acc = db.get(BankAccount, p.bank_account_id) if p.bank_account_id else None
        sale = p.sale
        return {
            "id": p.id,
            "sale_id": p.sale_id,
            "invoice_number": sale.invoice_number if sale else None,
            "customer_name": sale.customer_name if sale else None,
            "sale_date": sale.sale_date.isoformat() if sale and sale.sale_date else None,
            "method": pm.name if pm else None,
            "method_code": pm.code if pm else None,
            "category": pm.category if pm else None,
            "sri_code": pm.sri_code if pm else None,
            "amount": float(p.amount or 0),
            "reference": p.reference,
            "received_amount": float(p.received_amount) if p.received_amount is not None else None,
            "change_amount": float(p.change_amount) if p.change_amount is not None else None,
            "bank_account_id": p.bank_account_id,
            "bank_account": f"{acc.bank_name} · {acc.account_number}" if acc else None,
            "origin_bank": p.origin_bank,
            "payer_name": p.payer_name,
            "payer_id": p.payer_id,
            "payment_date": p.payment_date.date().isoformat() if p.payment_date else None,
            "card_brand": p.card_brand,
            "card_last4": p.card_last4,
            "authorization_code": p.authorization_code,
            "installments": p.installments,
            "term_days": p.term_days,
            "status": p.status,
            "verified_at": p.verified_at.isoformat() if p.verified_at else None,
            "notes": p.notes,
        }

