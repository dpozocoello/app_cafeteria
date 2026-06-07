"""
Router Contable — Plan de cuentas, asientos, períodos y estados financieros NIIF.
"""
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.accounting import AccountPlan, FiscalPeriod, JournalEntry, JournalEntryLine
from ..services.accounting_service import AccountingService

router = APIRouter(prefix="/api/contabilidad", tags=["Contabilidad"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class JournalLineIn(BaseModel):
    account_id: int
    description: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0


class JournalEntryIn(BaseModel):
    company_id: int
    entry_date: str              # YYYY-MM-DD
    description: str
    reference: Optional[str] = None
    entry_type: str = "MANUAL"
    lines: List[JournalLineIn]


class PeriodCreate(BaseModel):
    company_id: int
    name: str
    period_type: str = "MENSUAL"
    start_date: str   # YYYY-MM-DD
    end_date: str


# ─── Plan de Cuentas ──────────────────────────────────────────────────────────

@router.get("/accounts")
def list_accounts(
    account_type: Optional[str] = None,
    entries_only: bool = False,
    db: Session = Depends(get_db),
):
    """Devuelve el Plan de Cuentas completo o filtrado."""
    q = db.query(AccountPlan).filter_by(is_active=True)
    if account_type:
        q = q.filter_by(account_type=account_type)
    if entries_only:
        q = q.filter_by(allows_entries=True)
    accounts = q.order_by(AccountPlan.code).all()
    return [
        {
            "id": a.id,
            "code": a.code,
            "name": a.name,
            "type": a.account_type,
            "nature": a.nature,
            "level": a.level,
            "allows_entries": a.allows_entries,
            "parent_id": a.parent_id,
            "niif_category": a.niif_category,
        }
        for a in accounts
    ]


@router.get("/accounts/{account_id}/balance")
def account_balance(
    account_id: int,
    start: str,   # YYYY-MM-DD
    end: str,
    db: Session = Depends(get_db),
):
    """Saldo de una cuenta en un período."""
    from sqlalchemy import func
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    account  = db.get(AccountPlan, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    row = (
        db.query(
            func.sum(JournalEntryLine.debit).label("d"),
            func.sum(JournalEntryLine.credit).label("c"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            JournalEntry.status != "ANULADO",
            JournalEntry.entry_date >= start_dt,
            JournalEntry.entry_date <= end_dt,
            JournalEntryLine.account_id == account_id,
        )
        .first()
    )
    d = float(row.d or 0)
    c = float(row.c or 0)
    balance = (d - c) if account.nature == "DEUDORA" else (c - d)
    return {
        "account_id": account_id,
        "code": account.code,
        "name": account.name,
        "nature": account.nature,
        "total_debit": round(d, 2),
        "total_credit": round(c, 2),
        "balance": round(balance, 2),
    }


# ─── Períodos Fiscales ────────────────────────────────────────────────────────

@router.get("/periods")
def list_periods(company_id: int, db: Session = Depends(get_db)):
    periods = (
        db.query(FiscalPeriod)
        .filter_by(company_id=company_id)
        .order_by(FiscalPeriod.start_date.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "type": p.period_type,
            "start": p.start_date.date().isoformat(),
            "end": p.end_date.date().isoformat(),
            "status": p.status,
        }
        for p in periods
    ]


@router.post("/periods", status_code=201)
def create_period(data: PeriodCreate, db: Session = Depends(get_db)):
    period = FiscalPeriod(
        company_id=data.company_id,
        name=data.name,
        period_type=data.period_type,
        start_date=datetime.strptime(data.start_date, "%Y-%m-%d"),
        end_date=datetime.strptime(data.end_date,   "%Y-%m-%d").replace(hour=23, minute=59, second=59),
        status="ABIERTO",
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return {"id": period.id, "name": period.name, "status": period.status}


@router.put("/periods/{period_id}/close")
def close_period(period_id: int, user_id: int, db: Session = Depends(get_db)):
    period = db.get(FiscalPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Período no encontrado")
    if period.status == "CERRADO":
        raise HTTPException(status_code=400, detail="El período ya está cerrado")
    period.status = "CERRADO"
    period.closed_at = datetime.utcnow()
    period.closed_by_id = user_id
    db.commit()
    return {"ok": True, "period_id": period_id, "status": "CERRADO"}


# ─── Asientos Contables ───────────────────────────────────────────────────────

@router.get("/journal")
def list_journal_entries(
    company_id: int,
    period_id: Optional[int] = None,
    entry_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(JournalEntry).filter_by(company_id=company_id, status="APROBADO")
    if period_id:
        q = q.filter_by(period_id=period_id)
    if entry_type:
        q = q.filter_by(entry_type=entry_type)
    total = q.count()
    entries = q.order_by(JournalEntry.entry_date.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": e.id,
                "number": e.entry_number,
                "date": e.entry_date.date().isoformat(),
                "description": e.description,
                "reference": e.reference,
                "type": e.entry_type,
                "debit": float(e.total_debit),
                "credit": float(e.total_credit),
                "source_type": e.source_type,
                "source_id": e.source_id,
            }
            for e in entries
        ],
    }


@router.get("/journal/{entry_id}")
def get_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    lines = db.query(JournalEntryLine).filter_by(entry_id=entry_id).all()
    return {
        "id": entry.id,
        "number": entry.entry_number,
        "date": entry.entry_date.date().isoformat(),
        "description": entry.description,
        "reference": entry.reference,
        "type": entry.entry_type,
        "status": entry.status,
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "lines": [
            {
                "id": l.id,
                "account_id": l.account_id,
                "account_code": l.account.code if l.account else "",
                "account_name": l.account.name if l.account else "",
                "description": l.description,
                "debit": float(l.debit),
                "credit": float(l.credit),
            }
            for l in lines
        ],
    }


@router.post("/journal", status_code=201)
def create_journal_entry(data: JournalEntryIn, db: Session = Depends(get_db)):
    """Crea un asiento manual. Valida que débitos = créditos."""
    total_d = sum(l.debit  for l in data.lines)
    total_c = sum(l.credit for l in data.lines)
    if abs(total_d - total_c) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Asiento descuadrado: Débitos={total_d:.2f} ≠ Créditos={total_c:.2f}"
        )

    entry_date = datetime.strptime(data.entry_date, "%Y-%m-%d")
    period = AccountingService.get_or_create_period(db, data.company_id, entry_date)
    number = AccountingService.next_entry_number(db, data.company_id, entry_date.year)

    entry = JournalEntry(
        company_id=data.company_id,
        period_id=period.id if period else None,
        entry_number=number,
        entry_date=entry_date,
        description=data.description,
        reference=data.reference,
        entry_type=data.entry_type,
        status="APROBADO",
        total_debit=round(total_d, 2),
        total_credit=round(total_c, 2),
    )
    db.add(entry)
    db.flush()

    for ln in data.lines:
        acc = db.get(AccountPlan, ln.account_id)
        if not acc or not acc.allows_entries:
            raise HTTPException(
                status_code=400,
                detail=f"La cuenta ID={ln.account_id} no existe o no acepta asientos directos"
            )
        db.add(JournalEntryLine(
            entry_id=entry.id,
            account_id=ln.account_id,
            description=ln.description,
            debit=round(ln.debit, 2),
            credit=round(ln.credit, 2),
        ))

    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "number": entry.entry_number, "ok": True}


@router.put("/journal/{entry_id}/annul")
def annul_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Asiento no encontrado")
    if entry.entry_type != "MANUAL":
        raise HTTPException(status_code=400, detail="Solo se pueden anular asientos manuales")
    entry.status = "ANULADO"
    db.commit()
    return {"ok": True, "entry_id": entry_id, "status": "ANULADO"}


# ─── Estados Financieros ──────────────────────────────────────────────────────

@router.get("/reports/trial-balance")
def trial_balance(
    company_id: int,
    start: str,   # YYYY-MM-DD
    end: str,
    db: Session = Depends(get_db),
):
    """Balance de Comprobación para el período indicado."""
    try:
        start_d = date.fromisoformat(start)
        end_d   = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas. Formato: YYYY-MM-DD")
    return AccountingService.get_trial_balance(db, company_id, start_d, end_d)


@router.get("/reports/balance-sheet")
def balance_sheet(
    company_id: int,
    as_of: str,   # YYYY-MM-DD
    db: Session = Depends(get_db),
):
    """Estado de Situación Financiera (Balance General) NIIF."""
    try:
        as_of_d = date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Formato: YYYY-MM-DD")
    return AccountingService.get_balance_sheet(db, company_id, as_of_d)


@router.get("/reports/income-statement")
def income_statement(
    company_id: int,
    start: str,
    end: str,
    db: Session = Depends(get_db),
):
    """Estado de Resultados Integrales NIIF."""
    try:
        start_d = date.fromisoformat(start)
        end_d   = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas. Formato: YYYY-MM-DD")
    return AccountingService.get_income_statement(db, company_id, start_d, end_d)


@router.get("/reports/cash-flow")
def cash_flow_statement(
    company_id: int,
    start: str,
    end: str,
    db: Session = Depends(get_db),
):
    """Estado de Flujo de Efectivo — método directo (NIC 7)."""
    try:
        start_d = date.fromisoformat(start)
        end_d   = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fechas inválidas. Formato: YYYY-MM-DD")
    return AccountingService.get_cash_flow(db, company_id, start_d, end_d)


# ─── Libro Mayor por cuenta ───────────────────────────────────────────────────

@router.get("/ledger/{account_code}")
def general_ledger(
    account_code: str,
    company_id: int,
    start: str,
    end: str,
    db: Session = Depends(get_db),
):
    """Mayor General: todos los movimientos de una cuenta en el período."""
    from sqlalchemy import func
    account = db.query(AccountPlan).filter_by(code=account_code).first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Cuenta '{account_code}' no encontrada")

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt   = datetime.strptime(end,   "%Y-%m-%d").replace(hour=23, minute=59, second=59)

    lines = (
        db.query(JournalEntryLine, JournalEntry)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.entry_id)
        .filter(
            JournalEntry.company_id == company_id,
            JournalEntry.status != "ANULADO",
            JournalEntry.entry_date >= start_dt,
            JournalEntry.entry_date <= end_dt,
            JournalEntryLine.account_id == account.id,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id)
        .all()
    )

    running_balance = 0.0
    rows = []
    for ln, entry in lines:
        d = float(ln.debit or 0)
        c = float(ln.credit or 0)
        if account.nature == "DEUDORA":
            running_balance += d - c
        else:
            running_balance += c - d
        rows.append({
            "date": entry.entry_date.date().isoformat(),
            "entry_number": entry.entry_number,
            "description": ln.description or entry.description,
            "reference": entry.reference,
            "debit": round(d, 2),
            "credit": round(c, 2),
            "balance": round(running_balance, 2),
        })

    return {
        "account_code": account_code,
        "account_name": account.name,
        "nature": account.nature,
        "period": f"{start} / {end}",
        "movements": rows,
        "final_balance": round(running_balance, 2),
    }
