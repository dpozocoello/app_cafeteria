"""
Router de Pagos y Cobros — Ecuador (SRI Tabla 24)
Endpoints para:
  • Catálogo de formas de pago configurables
  • Listado de entidades financieras de Ecuador (Bancos, Cooperativas, Billeteras)
  • Cuentas bancarias de la empresa disponibles para recibir transferencias/depósitos
  • Consulta y trazabilidad de cobros
  • Verificación y rechazo de transferencias/depósitos contra extracto bancario
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.sales import PaymentMethod, SalePayment, Sale
from ..models.banking import BankAccount
from ..services.payment_service import (
    PaymentService,
    ECUADOR_FINANCIAL_ENTITIES,
    CARD_BRANDS,
    BANK_CATEGORIES,
)

router = APIRouter(prefix="/api/payments", tags=["Cobros y Medios de Pago"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class PaymentMethodUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    requires_reference: Optional[bool] = None
    requires_bank_account: Optional[bool] = None
    requires_origin_bank: Optional[bool] = None
    description: Optional[str] = None
    icon: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    user_id: Optional[int] = 1
    notes: Optional[str] = None


class RejectPaymentRequest(BaseModel):
    user_id: Optional[int] = 1
    reason: str


# ─── Catálogo y Configuración de Medios de Pago ───────────────────────────────

@router.get("/methods")
def list_payment_methods(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Retorna el catálogo completo de formas de pago según normativa SRI Ecuador.
    """
    q = db.query(PaymentMethod)
    if active_only:
        q = q.filter(PaymentMethod.is_active == True)
    methods = q.order_by(PaymentMethod.sort_order, PaymentMethod.id).all()

    # Si la base está vacía o no tiene metadatos sembrados, sembramos automáticamente
    if not methods or not any(m.category for m in methods):
        PaymentService.seed_payment_methods(db)
        q = db.query(PaymentMethod)
        if active_only:
            q = q.filter(PaymentMethod.is_active == True)
        methods = q.order_by(PaymentMethod.sort_order, PaymentMethod.id).all()

    return [PaymentService.serialize_method(m) for m in methods]


@router.put("/methods/{method_id}")
def update_payment_method(
    method_id: int,
    data: PaymentMethodUpdate,
    db: Session = Depends(get_db)
):
    """
    Permite activar/desactivar un medio de pago o actualizar sus requerimientos.
    """
    pm = db.get(PaymentMethod, method_id)
    if not pm:
        raise HTTPException(status_code=404, detail="Medio de pago no encontrado")

    if data.name is not None:
        pm.name = data.name
    if data.is_active is not None:
        pm.is_active = data.is_active
    if data.requires_reference is not None:
        pm.requires_reference = data.requires_reference
    if data.requires_bank_account is not None:
        pm.requires_bank_account = data.requires_bank_account
    if data.requires_origin_bank is not None:
        pm.requires_origin_bank = data.requires_origin_bank
    if data.description is not None:
        pm.description = data.description
    if data.icon is not None:
        pm.icon = data.icon

    db.commit()
    return PaymentService.serialize_method(pm)


@router.post("/methods/seed")
def seed_methods(db: Session = Depends(get_db)):
    """Sincroniza el catálogo predeterminado de Ecuador."""
    PaymentService.seed_payment_methods(db)
    return {"ok": True, "message": "Catálogo de formas de pago sincronizado exitosamente"}


# ─── Datos de Ayuda para Cobro (Bancos Ecuador, Marcas, Cuentas) ───────────────

@router.get("/ecuador-entities")
def get_ecuador_financial_entities():
    """
    Retorna la lista de bancos, cooperativas, mutualistas y billeteras digitales
    más usadas en Ecuador para autocompletar el banco/entidad de origen en transferencias.
    """
    return {
        "groups": ECUADOR_FINANCIAL_ENTITIES,
        "card_brands": CARD_BRANDS
    }


@router.get("/company-bank-accounts")
def get_company_bank_accounts(
    company_id: int = 1,
    db: Session = Depends(get_db)
):
    """
    Retorna las cuentas bancarias activas de la empresa disponibles para recibir
    transferencias, depósitos y cobros por billetera móvil (DeUna, etc.).
    """
    accounts = db.query(BankAccount).filter_by(
        company_id=company_id,
        is_active=True
    ).order_by(BankAccount.bank_name).all()

    return [{
        "id": a.id,
        "bank_name": a.bank_name,
        "account_number": a.account_number,
        "account_type": a.account_type,
        "currency": a.currency,
        "current_balance": float(a.current_balance or 0),
        "label": f"{a.bank_name} - {a.account_type.capitalize()} ({a.account_number})"
    } for a in accounts]


# ─── Auditoría y Verificación de Transferencias / Depósitos ───────────────────

@router.get("/history")
def list_payments_history(
    category: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Lista el historial de cobros recibidos con filtros por categoría (TRANSFERENCIA, DEPOSITO, BILLETERA, etc.),
    estado de verificación y rango de fechas.
    """
    q = db.query(SalePayment).join(Sale).join(PaymentMethod)

    if category:
        q = q.filter(PaymentMethod.category == category)
    if status:
        q = q.filter(SalePayment.status == status)
    if start_date:
        s_dt = datetime.strptime(start_date, "%Y-%m-%d")
        q = q.filter(Sale.sale_date >= s_dt)
    if end_date:
        e_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        q = q.filter(Sale.sale_date <= e_dt)

    payments = q.order_by(SalePayment.id.desc()).limit(limit).all()
    return [PaymentService.serialize_payment(db, p) for p in payments]


@router.get("/pending-verification")
def list_pending_verification(db: Session = Depends(get_db)):
    """
    Lista transferencias, depósitos, billeteras y cheques pendientes de confirmación bancaria.
    """
    payments = db.query(SalePayment).join(PaymentMethod).filter(
        SalePayment.status == "REGISTRADO",
        PaymentMethod.category.in_(list(BANK_CATEGORIES) + ["PASARELA", "CHEQUE"])
    ).order_by(SalePayment.id.desc()).all()

    return [PaymentService.serialize_payment(db, p) for p in payments]


@router.put("/{payment_id}/verify")
def verify_payment_endpoint(
    payment_id: int,
    data: VerifyPaymentRequest,
    db: Session = Depends(get_db)
):
    """
    Confirma que la transferencia/depósito se acreditó en la cuenta bancaria.
    """
    payment = db.get(SalePayment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Registro de pago no encontrado")
    try:
        updated = PaymentService.verify_payment(db, payment, data.user_id, data.notes)
        return {"ok": True, "message": "Pago verificado exitosamente", "payment": PaymentService.serialize_payment(db, updated)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{payment_id}/reject")
def reject_payment_endpoint(
    payment_id: int,
    data: RejectPaymentRequest,
    db: Session = Depends(get_db)
):
    """
    Rechaza una transferencia no acreditada o falsa.
    Revierte el saldo bancario si existía y genera el asiento contable reclasificando a CxC Clientes.
    """
    payment = db.get(SalePayment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Registro de pago no encontrado")
    try:
        updated = PaymentService.reject_payment(db, payment, data.user_id, data.reason)
        return {"ok": True, "message": "Pago rechazado y saldo revertido", "payment": PaymentService.serialize_payment(db, updated)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

