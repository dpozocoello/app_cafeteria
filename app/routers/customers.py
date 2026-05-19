"""
Router: Clientes + Consentimiento GDPR/LOPDP
Gestión de clientes del POS (delivery, llevar) con cumplimiento de protección de datos.
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db
from ..models.customers import Customer, EmailConfig
from ..services.email_service import send_gdpr_email, generate_gdpr_email, DEFAULT_GDPR_TEMPLATE

router = APIRouter(prefix="/api/customers", tags=["Clientes"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    customer_type: str = "LLEVAR"   # MESA | LLEVAR | DOMICILIO
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    customer_type: str
    address: Optional[str]
    delivery_code: Optional[str]
    gdpr_consent: bool
    consent_email_sent: bool
    consent_sent_at: Optional[str]
    created_at: str
    updated_at: Optional[str]


# ─── Helper: generar código delivery ──────────────────────────────────────────

def _generate_delivery_code(db: Session) -> str:
    """Genera código único DEL-{YYMMDD}-{HHMM}-{NNN}."""
    now = datetime.now()
    date_part = now.strftime("%y%m%d")
    time_part = now.strftime("%H%M")
    # Contar cuántos delivery hay hoy
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(Customer).filter(
        Customer.customer_type == "DOMICILIO",
        Customer.created_at >= today_start
    ).count()
    seq = str(count + 1).zfill(3)
    return f"DEL-{date_part}-{time_part}-{seq}"


def _serialize(c: Customer) -> dict:
    return {
        "id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
        "customer_type": c.customer_type, "address": c.address,
        "delivery_code": c.delivery_code,
        "gdpr_consent": c.gdpr_consent,
        "consent_email_sent": c.consent_email_sent,
        "consent_sent_at": c.consent_sent_at.isoformat() if c.consent_sent_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


# ─── Envío GDPR en background ─────────────────────────────────────────────────

def _try_send_gdpr(customer_id: int, db_url: str, base_url: str):
    """Tarea en background: envía correo GDPR si está configurado."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    with Session() as session:
        customer = session.get(Customer, customer_id)
        if not customer or not customer.email:
            return
        cfg = session.query(EmailConfig).first()
        if not cfg or not cfg.gdpr_enabled or not cfg.smtp_user or not cfg.smtp_password:
            return

        html_body = generate_gdpr_email(
            template_html=cfg.gdpr_email_body_html,
            customer_name=customer.name,
            service_type=customer.customer_type,
            delivery_code=customer.delivery_code,
            business_name=cfg.from_name or "CoffeeApp",
            business_email=cfg.from_email or cfg.smtp_user,
            base_url=base_url,
        )

        ok, error = send_gdpr_email(
            smtp_host=cfg.smtp_host,
            smtp_port=cfg.smtp_port,
            smtp_user=cfg.smtp_user,
            smtp_password=cfg.smtp_password,
            smtp_use_tls=cfg.smtp_use_tls,
            from_name=cfg.from_name or "CoffeeApp",
            from_email=cfg.from_email or cfg.smtp_user,
            to_email=customer.email,
            subject=cfg.gdpr_email_subject or "Autorización para el tratamiento de sus datos personales",
            body_html=html_body,
        )

        if ok:
            customer.consent_email_sent = True
            customer.consent_sent_at = datetime.utcnow()
            customer.consent_email_snapshot = html_body  # evidencia normativa
        session.commit()


# ─── Endpoints CRUD ───────────────────────────────────────────────────────────

@router.get("/")
def list_customers(
    customer_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Customer)
    if customer_type:
        q = q.filter(Customer.customer_type == customer_type.upper())
    return [_serialize(c) for c in q.order_by(Customer.created_at.desc()).limit(200).all()]


@router.get("/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return _serialize(c)


@router.post("/", status_code=201)
async def create_or_update_customer(
    data: CustomerCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo cliente o actualiza si ya existe (mismo email).
    Si tiene email y GDPR activo → dispara correo de consentimiento en background.
    El registro es persistente e inmutable a efectos normativos.
    """
    existing = None
    if data.email:
        existing = db.query(Customer).filter(Customer.email == data.email.lower()).first()

    if existing:
        # Actualizar datos pero preservar evidencia de consentimiento enviado
        existing.name = data.name
        existing.phone = data.phone or existing.phone
        existing.customer_type = data.customer_type
        existing.address = data.address or existing.address
        existing.updated_at = datetime.utcnow()
        if data.customer_type == "DOMICILIO" and not existing.delivery_code:
            existing.delivery_code = _generate_delivery_code(db)
        customer = existing
        is_new = False
    else:
        delivery_code = _generate_delivery_code(db) if data.customer_type == "DOMICILIO" else None
        customer = Customer(
            name=data.name,
            email=data.email.lower() if data.email else None,
            phone=data.phone,
            customer_type=data.customer_type,
            address=data.address,
            delivery_code=delivery_code,
        )
        db.add(customer)
        is_new = True

    db.commit()
    db.refresh(customer)

    # Disparar correo GDPR en background si hay email y no se ha enviado aún
    if customer.email and not customer.consent_email_sent:
        from ..database import DATABASE_URL
        base_url = str(request.base_url).rstrip("/")
        background_tasks.add_task(_try_send_gdpr, customer.id, DATABASE_URL, base_url)

    result = _serialize(customer)
    result["is_new"] = is_new
    return result


@router.put("/{customer_id}/gdpr-consent")
def update_gdpr_consent(customer_id: int, consent: bool, db: Session = Depends(get_db)):
    """Actualiza el estado de consentimiento GDPR del cliente."""
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    c.gdpr_consent = consent
    c.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "gdpr_consent": consent}


# ─── Endpoints GDPR (links en el correo) ─────────────────────────────────────

@router.get("/gdpr/accept")
def gdpr_accept(name: str, db: Session = Depends(get_db)):
    """Endpoint llamado desde el link del correo GDPR (aceptar)."""
    c = db.query(Customer).filter(Customer.name == name).order_by(Customer.id.desc()).first()
    if c:
        c.gdpr_consent = True
        c.updated_at = datetime.utcnow()
        db.commit()
    from fastapi.responses import HTMLResponse
    return HTMLResponse("""
    <html><body style="font-family:Arial;text-align:center;padding:60px;background:#0f172a;color:#f8fafc;">
      <div style="max-width:500px;margin:0 auto;background:#1e293b;padding:40px;border-radius:16px;">
        <div style="font-size:3rem">✅</div>
        <h2 style="color:#10b981">Consentimiento registrado</h2>
        <p style="color:#94a3b8">Gracias <strong>""" + name + """</strong>. Su autorización para el
        tratamiento de datos personales ha sido registrada correctamente.</p>
        <p style="color:#64748b;font-size:.85rem">Puede cerrar esta ventana.</p>
      </div>
    </body></html>""")


@router.get("/gdpr/reject")
def gdpr_reject(name: str, db: Session = Depends(get_db)):
    """Endpoint llamado desde el link del correo GDPR (rechazar)."""
    c = db.query(Customer).filter(Customer.name == name).order_by(Customer.id.desc()).first()
    if c:
        c.gdpr_consent = False
        c.updated_at = datetime.utcnow()
        db.commit()
    from fastapi.responses import HTMLResponse
    return HTMLResponse("""
    <html><body style="font-family:Arial;text-align:center;padding:60px;background:#0f172a;color:#f8fafc;">
      <div style="max-width:500px;margin:0 auto;background:#1e293b;padding:40px;border-radius:16px;">
        <div style="font-size:3rem">🔒</div>
        <h2 style="color:#ef4444">Datos no autorizados</h2>
        <p style="color:#94a3b8"><strong>""" + name + """</strong>, su solicitud de NO tratamiento
        de datos ha sido registrada. Sus datos serán eliminados en el plazo legalmente establecido.</p>
        <p style="color:#64748b;font-size:.85rem">Puede cerrar esta ventana.</p>
      </div>
    </body></html>""")
