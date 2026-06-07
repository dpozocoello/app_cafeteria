"""
Router de Caja — Gestión de sesiones POS, apertura/cierre y flujo de caja.
Endpoints auditables bajo NIIF / control interno Ecuador.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.cash import CashRegister, CashSession, CashTransaction
from ..services.cash_service import CashService

router = APIRouter(prefix="/api/caja", tags=["Caja"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OpenSessionRequest(BaseModel):
    register_id: int
    branch_id: int
    user_id: int
    opening_amount: float
    notes: Optional[str] = None


class CashMovementRequest(BaseModel):
    session_id: int
    user_id: int
    transaction_type: str   # INGRESO | EGRESO | RETIRO | FONDO_CAMBIO
    amount: float
    description: str


class DenominationCount(BaseModel):
    denomination: float
    quantity: int


class CloseSessionRequest(BaseModel):
    session_id: int
    user_id: int
    declared_amount: float
    denominations: Optional[List[DenominationCount]] = None
    notes: Optional[str] = None
    company_id: Optional[int] = None


class RegisterCreate(BaseModel):
    name: str
    branch_id: int
    emission_point_id: Optional[int] = None


# ─── Cajas registradoras ──────────────────────────────────────────────────────

@router.get("/registers")
def list_registers(branch_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(CashRegister).filter_by(is_active=True)
    if branch_id:
        q = q.filter_by(branch_id=branch_id)
    regs = q.all()
    return [{"id": r.id, "name": r.name, "branch_id": r.branch_id,
             "emission_point_id": r.emission_point_id} for r in regs]


@router.post("/registers", status_code=201)
def create_register(data: RegisterCreate, db: Session = Depends(get_db)):
    reg = CashRegister(
        name=data.name,
        branch_id=data.branch_id,
        emission_point_id=data.emission_point_id,
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return {"id": reg.id, "name": reg.name}


# ─── Estado de sesión actual ──────────────────────────────────────────────────

@router.get("/session/current")
def get_current_session(branch_id: int, db: Session = Depends(get_db)):
    """Devuelve la sesión abierta de la sucursal con su resumen en tiempo real."""
    session = CashService.get_open_session_by_branch(db, branch_id)
    if not session:
        return {"open": False, "session": None}
    summary = CashService.get_session_summary(db, session)
    return {"open": True, "session": summary}


# ─── Apertura ─────────────────────────────────────────────────────────────────

@router.post("/session/open", status_code=201)
def open_session(data: OpenSessionRequest, db: Session = Depends(get_db)):
    try:
        session = CashService.open_session(
            db,
            register_id=data.register_id,
            branch_id=data.branch_id,
            user_id=data.user_id,
            opening_amount=data.opening_amount,
            notes=data.notes,
        )
        return {
            "ok": True,
            "session_id": session.id,
            "opened_at": session.opened_at.isoformat(),
            "opening_amount": float(session.opening_amount),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Movimiento manual de efectivo ────────────────────────────────────────────

@router.post("/session/movement")
def add_movement(data: CashMovementRequest, db: Session = Depends(get_db)):
    valid_types = {"INGRESO", "EGRESO", "RETIRO", "FONDO_CAMBIO"}
    if data.transaction_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Use: {valid_types}")
    try:
        trx = CashService.add_cash_movement(
            db,
            session_id=data.session_id,
            user_id=data.user_id,
            transaction_type=data.transaction_type,
            amount=data.amount,
            description=data.description,
        )
        return {"ok": True, "transaction_id": trx.id, "amount": float(trx.amount)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Resumen de sesión ────────────────────────────────────────────────────────

@router.get("/session/{session_id}/summary")
def session_summary(session_id: int, db: Session = Depends(get_db)):
    session = db.get(CashSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return CashService.get_session_summary(db, session)


@router.get("/session/{session_id}/movements")
def session_movements(session_id: int, db: Session = Depends(get_db)):
    from ..models.core import User
    txns = db.query(CashTransaction).filter_by(session_id=session_id).order_by(
        CashTransaction.created_at
    ).all()
    return [
        {
            "id": t.id,
            "type": t.transaction_type,
            "amount": float(t.amount),
            "description": t.description,
            "at": t.created_at.isoformat(),
        }
        for t in txns
    ]


# ─── Cierre de caja ───────────────────────────────────────────────────────────

@router.post("/session/close")
def close_session(data: CloseSessionRequest, db: Session = Depends(get_db)):
    try:
        session = CashService.close_session(
            db,
            session_id=data.session_id,
            user_id=data.user_id,
            declared_amount=data.declared_amount,
            denominations=[d.dict() for d in (data.denominations or [])],
            notes=data.notes,
            company_id=data.company_id,
        )
        status = "CUADRADA" if abs(session.difference) < 0.01 else (
            "SOBRANTE" if session.difference > 0 else "FALTANTE"
        )
        return {
            "ok": True,
            "session_id": session.id,
            "expected_amount": float(session.expected_amount),
            "declared_amount": float(session.declared_amount),
            "difference": float(session.difference),
            "difference_status": status,
            "closed_at": session.closed_at.isoformat(),
            "journal_entry_id": session.closing_journal_entry_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Historial de sesiones ────────────────────────────────────────────────────

@router.get("/sessions/history")
def sessions_history(branch_id: int, limit: int = 30, db: Session = Depends(get_db)):
    sessions = (
        db.query(CashSession)
        .filter_by(branch_id=branch_id)
        .order_by(CashSession.opened_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "date": s.opened_at.date().isoformat(),
            "status": s.status,
            "opening": float(s.opening_amount or 0),
            "expected": float(s.expected_amount or 0),
            "declared": float(s.declared_amount or 0),
            "difference": float(s.difference or 0),
            "total_sales": float(s.total_sales or 0),
            "opened_at": s.opened_at.isoformat(),
            "closed_at": s.closed_at.isoformat() if s.closed_at else None,
        }
        for s in sessions
    ]


# ─── Reporte de flujo de caja ─────────────────────────────────────────────────

@router.get("/flow-report")
def cash_flow_report(
    branch_id: int,
    start: str,   # YYYY-MM-DD
    end: str,
    db: Session = Depends(get_db),
):
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt   = datetime.strptime(end,   "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
    return CashService.get_cash_flow_report(db, branch_id, start_dt, end_dt)
