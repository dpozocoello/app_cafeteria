"""
Router Bancario — Cuentas bancarias, movimientos y conciliación bancaria NIC 7.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.banking import BankAccount, BankTransaction, BankReconciliation, BankReconciliationItem

router = APIRouter(prefix="/api/bancos", tags=["Bancos"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class BankAccountCreate(BaseModel):
    company_id: int
    bank_name: str
    account_number: str
    account_type: str           # CORRIENTE | AHORROS | VIRTUAL
    initial_balance: float = 0.0
    accounting_account_id: Optional[int] = None
    notes: Optional[str] = None


class BankTransactionCreate(BaseModel):
    bank_account_id: int
    transaction_date: str       # YYYY-MM-DD
    description: str
    reference: Optional[str] = None
    transaction_type: str       # DEPOSITO | RETIRO | TRANSFERENCIA_IN | TRANSFERENCIA_OUT | COMISION | INTERES
    amount: float               # + ingreso / – egreso
    source: str = "MANUAL"


class ReconciliationCreate(BaseModel):
    bank_account_id: int
    period_name: str            # "Enero 2025"
    period_start: str           # YYYY-MM-DD
    period_end: str
    bank_balance_start: float
    bank_balance_end: float
    book_balance_start: float
    book_balance_end: float
    notes: Optional[str] = None
    created_by_id: Optional[int] = None


class ReconciliationItemCreate(BaseModel):
    item_type: str              # DEPOSITO_TRANSITO | CHEQUE_PENDIENTE | CARGO_BANCARIO | CREDITO_BANCARIO
    description: str
    amount: float
    transaction_date: Optional[str] = None
    bank_transaction_id: Optional[int] = None


# ─── Cuentas Bancarias ────────────────────────────────────────────────────────

@router.get("/accounts")
def list_bank_accounts(company_id: int, db: Session = Depends(get_db)):
    accounts = db.query(BankAccount).filter_by(company_id=company_id, is_active=True).all()
    return [_serialize_account(a) for a in accounts]


@router.post("/accounts", status_code=201)
def create_bank_account(data: BankAccountCreate, db: Session = Depends(get_db)):
    account = BankAccount(
        company_id=data.company_id,
        bank_name=data.bank_name,
        account_number=data.account_number,
        account_type=data.account_type,
        initial_balance=round(data.initial_balance, 2),
        current_balance=round(data.initial_balance, 2),
        accounting_account_id=data.accounting_account_id,
        notes=data.notes,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


@router.put("/accounts/{account_id}")
def update_bank_account(account_id: int, data: BankAccountCreate, db: Session = Depends(get_db)):
    account = db.get(BankAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")
    account.bank_name = data.bank_name
    account.account_number = data.account_number
    account.account_type = data.account_type
    account.accounting_account_id = data.accounting_account_id
    account.notes = data.notes
    db.commit()
    return _serialize_account(account)


def _serialize_account(a: BankAccount) -> dict:
    return {
        "id": a.id,
        "bank_name": a.bank_name,
        "account_number": a.account_number,
        "account_type": a.account_type,
        "initial_balance": float(a.initial_balance or 0),
        "current_balance": float(a.current_balance or 0),
        "accounting_account_id": a.accounting_account_id,
        "currency": a.currency,
        "is_active": a.is_active,
    }


# ─── Movimientos Bancarios ────────────────────────────────────────────────────

@router.get("/accounts/{account_id}/transactions")
def list_bank_transactions(
    account_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    reconciled: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(BankTransaction).filter_by(bank_account_id=account_id)
    if start:
        q = q.filter(BankTransaction.transaction_date >= datetime.strptime(start, "%Y-%m-%d"))
    if end:
        q = q.filter(BankTransaction.transaction_date <= datetime.strptime(end, "%Y-%m-%d").replace(hour=23, minute=59))
    if reconciled is not None:
        q = q.filter_by(is_reconciled=reconciled)
    txns = q.order_by(BankTransaction.transaction_date.desc()).all()
    return [_serialize_txn(t) for t in txns]


@router.post("/transactions", status_code=201)
def create_bank_transaction(data: BankTransactionCreate, db: Session = Depends(get_db)):
    account = db.get(BankAccount, data.bank_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta bancaria no encontrada")

    txn_date = datetime.strptime(data.transaction_date, "%Y-%m-%d")
    new_balance = round(float(account.current_balance or 0) + data.amount, 2)

    txn = BankTransaction(
        bank_account_id=data.bank_account_id,
        transaction_date=txn_date,
        description=data.description,
        reference=data.reference,
        transaction_type=data.transaction_type,
        amount=round(data.amount, 2),
        balance_after=new_balance,
        source=data.source,
    )
    db.add(txn)

    # Actualizar saldo de la cuenta
    account.current_balance = new_balance
    db.commit()
    db.refresh(txn)
    return _serialize_txn(txn)


@router.put("/transactions/{txn_id}/reconcile")
def mark_reconciled(txn_id: int, reconciliation_id: int, db: Session = Depends(get_db)):
    txn = db.get(BankTransaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    txn.is_reconciled = True
    txn.reconciliation_id = reconciliation_id
    db.commit()
    return {"ok": True, "transaction_id": txn_id, "reconciled": True}


def _serialize_txn(t: BankTransaction) -> dict:
    return {
        "id": t.id,
        "date": t.transaction_date.date().isoformat(),
        "description": t.description,
        "reference": t.reference,
        "type": t.transaction_type,
        "amount": float(t.amount),
        "balance_after": float(t.balance_after or 0),
        "is_reconciled": t.is_reconciled,
        "source": t.source,
    }


# ─── Conciliación Bancaria ────────────────────────────────────────────────────

@router.get("/reconciliations")
def list_reconciliations(bank_account_id: int, db: Session = Depends(get_db)):
    recs = (
        db.query(BankReconciliation)
        .filter_by(bank_account_id=bank_account_id)
        .order_by(BankReconciliation.period_end.desc())
        .all()
    )
    return [_serialize_rec(r) for r in recs]


@router.post("/reconciliations", status_code=201)
def create_reconciliation(data: ReconciliationCreate, db: Session = Depends(get_db)):
    """
    Inicia una conciliación bancaria para el período indicado.
    Las partidas se agregan luego con POST /reconciliations/{id}/items.
    El saldo conciliado se recalcula automáticamente.
    """
    rec = BankReconciliation(
        bank_account_id=data.bank_account_id,
        period_name=data.period_name,
        period_start=datetime.strptime(data.period_start, "%Y-%m-%d"),
        period_end=datetime.strptime(data.period_end, "%Y-%m-%d").replace(hour=23, minute=59),
        bank_balance_start=round(data.bank_balance_start, 2),
        bank_balance_end=round(data.bank_balance_end, 2),
        book_balance_start=round(data.book_balance_start, 2),
        book_balance_end=round(data.book_balance_end, 2),
        status="BORRADOR",
        notes=data.notes,
        created_by_id=data.created_by_id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _serialize_rec(rec)


@router.get("/reconciliations/{rec_id}")
def get_reconciliation(rec_id: int, db: Session = Depends(get_db)):
    rec = db.get(BankReconciliation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")
    items = db.query(BankReconciliationItem).filter_by(reconciliation_id=rec_id).all()
    result = _serialize_rec(rec)
    result["items"] = [_serialize_item(i) for i in items]
    return result


@router.post("/reconciliations/{rec_id}/items", status_code=201)
def add_reconciliation_item(rec_id: int, data: ReconciliationItemCreate, db: Session = Depends(get_db)):
    rec = db.get(BankReconciliation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")
    if rec.status == "APROBADA":
        raise HTTPException(status_code=400, detail="No se pueden agregar partidas a una conciliación aprobada")

    item = BankReconciliationItem(
        reconciliation_id=rec_id,
        item_type=data.item_type,
        description=data.description,
        amount=round(data.amount, 2),
        transaction_date=datetime.strptime(data.transaction_date, "%Y-%m-%d") if data.transaction_date else None,
        bank_transaction_id=data.bank_transaction_id,
    )
    db.add(item)
    db.flush()

    # Recalcular saldo conciliado
    _recalculate_reconciliation(db, rec)
    db.commit()
    return _serialize_item(item)


@router.delete("/reconciliations/{rec_id}/items/{item_id}")
def remove_reconciliation_item(rec_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.get(BankReconciliationItem, item_id)
    if not item or item.reconciliation_id != rec_id:
        raise HTTPException(status_code=404, detail="Partida no encontrada")
    rec = db.get(BankReconciliation, rec_id)
    db.delete(item)
    db.flush()
    _recalculate_reconciliation(db, rec)
    db.commit()
    return {"ok": True}


@router.put("/reconciliations/{rec_id}/finalize")
def finalize_reconciliation(rec_id: int, approved_by_id: Optional[int] = None, db: Session = Depends(get_db)):
    rec = db.get(BankReconciliation, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Conciliación no encontrada")
    if abs(rec.difference) > 0.05:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede aprobar: diferencia de ${rec.difference:.2f}. Debe ser cero para aprobar."
        )
    rec.status = "APROBADA"
    rec.approved_by_id = approved_by_id
    db.commit()
    return {"ok": True, "rec_id": rec_id, "status": "APROBADA", "adjusted_balance": float(rec.adjusted_balance)}


def _recalculate_reconciliation(db: Session, rec: BankReconciliation):
    """
    Fórmula de conciliación bancaria:
      Saldo Banco  + Depósitos en Tránsito − Cheques Pendientes   = Saldo Ajustado Banco
      Saldo Libros + Créditos Banco no registrados − Cargos banco = Saldo Ajustado Libros
      Diferencia debe ser 0 al conciliar.
    """
    items = db.query(BankReconciliationItem).filter_by(reconciliation_id=rec.id).all()

    dep_transit    = sum(i.amount for i in items if i.item_type == "DEPOSITO_TRANSITO")
    checks_pending = sum(i.amount for i in items if i.item_type == "CHEQUE_PENDIENTE")
    bank_charges   = sum(i.amount for i in items if i.item_type == "CARGO_BANCARIO")
    bank_credits   = sum(i.amount for i in items if i.item_type == "CREDITO_BANCARIO")
    errors_books   = sum(i.amount for i in items if i.item_type == "ERROR_LIBROS")
    errors_bank    = sum(i.amount for i in items if i.item_type == "ERROR_BANCO")

    adj_bank  = float(rec.bank_balance_end)  + dep_transit - checks_pending + errors_bank
    adj_books = float(rec.book_balance_end)  + bank_credits - bank_charges  + errors_books

    rec.deposits_in_transit     = round(dep_transit, 2)
    rec.outstanding_checks      = round(checks_pending, 2)
    rec.bank_charges_not_in_books = round(bank_charges, 2)
    rec.bank_credits_not_in_books = round(bank_credits, 2)
    rec.errors_in_books         = round(errors_books, 2)
    rec.errors_in_bank          = round(errors_bank, 2)
    rec.adjusted_balance        = round(adj_bank, 2)
    rec.difference              = round(adj_bank - adj_books, 2)


def _serialize_rec(r: BankReconciliation) -> dict:
    return {
        "id": r.id,
        "bank_account_id": r.bank_account_id,
        "period_name": r.period_name,
        "period_start": r.period_start.date().isoformat(),
        "period_end": r.period_end.date().isoformat(),
        "bank_balance_end": float(r.bank_balance_end),
        "book_balance_end": float(r.book_balance_end),
        "deposits_in_transit": float(r.deposits_in_transit or 0),
        "outstanding_checks": float(r.outstanding_checks or 0),
        "bank_charges": float(r.bank_charges_not_in_books or 0),
        "bank_credits": float(r.bank_credits_not_in_books or 0),
        "adjusted_balance": float(r.adjusted_balance or 0),
        "difference": float(r.difference or 0),
        "status": r.status,
        "is_balanced": abs(float(r.difference or 0)) <= 0.05,
    }


def _serialize_item(i: BankReconciliationItem) -> dict:
    return {
        "id": i.id,
        "type": i.item_type,
        "description": i.description,
        "amount": float(i.amount),
        "date": i.transaction_date.date().isoformat() if i.transaction_date else None,
        "is_cleared": i.is_cleared,
    }
