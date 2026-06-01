from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import shutil
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database import get_db
from ..config import get_theme, save_env_values, get_engine_type, refresh_theme, BASE_DIR

router = APIRouter(prefix="/api/settings", tags=["Configuración"])

# ─── Schemas ──────────────────────────────────────────────────────────────────

class ThemeUpdate(BaseModel):
    brand_name:        Optional[str] = None
    brand_tagline:     Optional[str] = None
    font_family:       Optional[str] = None
    color_bg:          Optional[str] = None
    color_sidebar:     Optional[str] = None
    color_card:        Optional[str] = None
    color_accent:      Optional[str] = None
    color_text:        Optional[str] = None
    color_muted:       Optional[str] = None
    color_success:     Optional[str] = None
    color_danger:      Optional[str] = None
    color_info:        Optional[str] = None
    brand_personality: Optional[str] = None
    brand_visuals:     Optional[str] = None
    brand_packaging:   Optional[str] = None
    brand_tone:        Optional[str] = None
    brand_channels:    Optional[str] = None
    # Campos Fiscales
    ruc:                   Optional[str] = None
    business_name:         Optional[str] = None
    address:               Optional[str] = None
    phone:                 Optional[str] = None
    obligado_contabilidad: Optional[bool] = None
    environment:           Optional[int] = None


class DatabaseConfig(BaseModel):
    engine:       str = "sqlite"
    sqlite_path:  Optional[str] = None
    pg_host:      Optional[str] = None
    pg_port:      Optional[str] = None
    pg_database:  Optional[str] = None
    pg_user:      Optional[str] = None
    pg_password:  Optional[str] = None
    my_host:      Optional[str] = None
    my_port:      Optional[str] = None
    my_database:  Optional[str] = None
    my_user:      Optional[str] = None
    my_password:  Optional[str] = None


# ─── Endpoints de Tema ────────────────────────────────────────────────────────

@router.get("/theme")
def get_theme_settings(db: Session = Depends(get_db)):
    from ..models.core import Company
    company = db.query(Company).filter(Company.is_active == True).first()
    if not company:
        return get_theme()  # Fallback a valores por defecto del archivo config
    return {
        "brand_name": company.commercial_name,
        "brand_tagline": company.brand_tone or "Sistema de Gestión",
        "font_family": company.font_family or "Outfit",
        "color_bg": company.color_bg or "#020617",
        "color_sidebar": company.color_sidebar or "#0f172a",
        "color_card": company.color_card or "rgba(30,41,59,0.5)",
        "color_accent": company.color_accent or "#fbbf24",
        "color_text": company.color_text or "#f8fafc",
        "color_muted": company.color_muted or "#94a3b8",
        "color_success": company.color_success or "#10b981",
        "color_danger": company.color_danger or "#ef4444",
        "brand_personality": company.brand_personality or "",
        "brand_visuals": company.brand_visuals or "",
        "brand_packaging": company.brand_packaging or "",
        "brand_tone": company.brand_tone or "",
        "brand_channels": company.brand_channels or "",
        # Datos fiscales
        "ruc": company.ruc,
        "business_name": company.business_name,
        "address": company.address,
        "phone": company.phone,
        "obligado_contabilidad": company.obligado_contabilidad,
        "environment": company.environment,
        "logo_path": company.logo_path or "/static/logo.png"
    }


@router.put("/theme")
def update_theme(data: ThemeUpdate, db: Session = Depends(get_db)):
    from ..models.core import Company
    company = db.query(Company).filter(Company.is_active == True).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
        
    if data.brand_name is not None:
        company.commercial_name = data.brand_name
    if data.brand_personality is not None:
        company.brand_personality = data.brand_personality
    if data.brand_visuals is not None:
        company.brand_visuals = data.brand_visuals
    if data.brand_packaging is not None:
        company.brand_packaging = data.brand_packaging
    if data.brand_tone is not None:
        company.brand_tone = data.brand_tone
    if data.brand_channels is not None:
        company.brand_channels = data.brand_channels
    if data.font_family is not None:
        company.font_family = data.font_family
    if data.color_bg is not None:
        company.color_bg = data.color_bg
    if data.color_sidebar is not None:
        company.color_sidebar = data.color_sidebar
    if data.color_card is not None:
        company.color_card = data.color_card
    if data.color_accent is not None:
        company.color_accent = data.color_accent
    if data.color_text is not None:
        company.color_text = data.color_text
    if data.color_muted is not None:
        company.color_muted = data.color_muted
    if data.color_success is not None:
        company.color_success = data.color_success
    if data.color_danger is not None:
        company.color_danger = data.color_danger
    # Fiscales
    if data.ruc is not None:
        company.ruc = data.ruc
    if data.business_name is not None:
        company.business_name = data.business_name
    if data.address is not None:
        company.address = data.address
    if data.phone is not None:
        company.phone = data.phone
    if data.obligado_contabilidad is not None:
        company.obligado_contabilidad = data.obligado_contabilidad
    if data.environment is not None:
        company.environment = data.environment

    db.commit()
    db.refresh(company)
    return {"ok": True, "message": "Parámetros actualizados correctamente."}


@router.get("/css")
def get_dynamic_css(db: Session = Depends(get_db)):
    """Genera el CSS con las variables del .env actual o base de datos."""
    from ..models.core import Company
    company = db.query(Company).filter(Company.is_active == True).first()
    theme = {
        "font_family": company.font_family if company else "Outfit",
        "color_bg": company.color_bg if company else "#020617",
        "color_sidebar": company.color_sidebar if company else "#0f172a",
        "color_card": company.color_card if company else "rgba(30,41,59,0.5)",
        "color_accent": company.color_accent if company else "#fbbf24",
        "color_text": company.color_text if company else "#f8fafc",
        "color_muted": company.color_muted if company else "#94a3b8",
        "color_success": company.color_success if company else "#10b981",
        "color_danger": company.color_danger if company else "#ef4444",
    }
    css = f"""
/* Sistema POS - CSS Dinámico generado desde /api/settings/css */
:root {{
    --color-bg:       {theme['color_bg']};
    --color-sidebar:  {theme['color_sidebar']};
    --color-card:     {theme['color_card']};
    --color-accent:   {theme['color_accent']};
    --color-text:     {theme['color_text']};
    --color-muted:    {theme['color_muted']};
    --color-success:  {theme['color_success']};
    --color-danger:   {theme['color_danger']};
    --font-family:    '{theme['font_family']}', sans-serif;
}}
"""
    from fastapi.responses import Response
    return Response(content=css, media_type="text/css")


# ─── Endpoints de Base de Datos ───────────────────────────────────────────────

@router.get("/database")
def get_database_config():
    """Retorna la configuración actual de BD (sin contraseñas)."""
    from ..config import _get
    return {
        "engine":      _get("DB_ENGINE", "sqlite"),
        "sqlite_path": _get("SQLITE_PATH", "./pos_app.db"),
        "pg_host":     _get("PG_HOST", "localhost"),
        "pg_port":     _get("PG_PORT", "5432"),
        "pg_database": _get("PG_DATABASE", "pos_app"),
        "pg_user":     _get("PG_USER", "postgres"),
        "my_host":     _get("MYSQL_HOST", "localhost"),
        "my_port":     _get("MYSQL_PORT", "3306"),
        "my_database": _get("MYSQL_DATABASE", "pos_app"),
        "my_user":     _get("MYSQL_USER", "root"),
    }


@router.put("/database")
def update_database_config(data: DatabaseConfig):
    updates = {"DB_ENGINE": data.engine.lower()}
    if data.sqlite_path:  updates["SQLITE_PATH"]      = data.sqlite_path
    if data.pg_host:      updates["PG_HOST"]          = data.pg_host
    if data.pg_port:      updates["PG_PORT"]          = data.pg_port
    if data.pg_database:  updates["PG_DATABASE"]      = data.pg_database
    if data.pg_user:      updates["PG_USER"]          = data.pg_user
    if data.pg_password:  updates["PG_PASSWORD"]      = data.pg_password
    if data.my_host:      updates["MYSQL_HOST"]       = data.my_host
    if data.my_port:      updates["MYSQL_PORT"]       = data.my_port
    if data.my_database:  updates["MYSQL_DATABASE"]   = data.my_database
    if data.my_user:      updates["MYSQL_USER"]       = data.my_user
    if data.my_password:  updates["MYSQL_PASSWORD"]   = data.my_password
    save_env_values(updates)
    return {"ok": True, "message": "Configuración de BD guardada. Reinicia el servidor."}


@router.post("/database/test")
def test_database_connection(data: DatabaseConfig):
    """Prueba la conexión con los parámetros enviados."""
    try:
        from sqlalchemy import create_engine, text

        if data.engine.lower() == "postgresql":
            url = f"postgresql://{data.pg_user}:{data.pg_password}@{data.pg_host}:{data.pg_port}/{data.pg_database}"
        elif data.engine.lower() == "mysql":
            url = f"mysql+pymysql://{data.my_user}:{data.my_password}@{data.my_host}:{data.my_port}/{data.my_database}"
        else:
            path = data.sqlite_path or "./pos_app.db"
            url = f"sqlite:///{path}"

        test_engine = create_engine(url, connect_args={"check_same_thread": False} if "sqlite" in url else {})
        with test_engine.connect() as conn:
            if "postgresql" in url:
                result = conn.execute(text("SELECT version()")).scalar()
            elif "mysql" in url:
                result = conn.execute(text("SELECT VERSION()")).scalar()
            else:
                result = conn.execute(text("SELECT sqlite_version()")).scalar()

        return {"ok": True, "engine": data.engine, "version": str(result)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─── Endpoint Logo ────────────────────────────────────────────────────────────

@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    static_dir = os.path.join(BASE_DIR, "app", "static")
    os.makedirs(static_dir, exist_ok=True)
    dest = os.path.join(static_dir, "logo.png")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"ok": True, "message": "Logo actualizado."}


# ─── Configuración de Correo SMTP ─────────────────────────────────────────────

class EmailConfigUpdate(BaseModel):
    smtp_host:           Optional[str] = None
    smtp_port:           Optional[int] = None
    smtp_user:           Optional[str] = None
    smtp_password:       Optional[str] = None   # app-password Gmail / Outlook
    smtp_use_tls:        Optional[bool] = None
    from_name:           Optional[str] = None
    from_email:          Optional[str] = None
    gdpr_enabled:        Optional[bool] = None
    gdpr_email_subject:  Optional[str] = None
    gdpr_email_body_html: Optional[str] = None


@router.get("/email")
def get_email_config(db=None):
    """Retorna la configuración SMTP actual (sin contraseña)."""
    from ..database import get_db
    from ..models.customers import EmailConfig
    from fastapi import Depends
    from sqlalchemy.orm import Session
    import inspect

    # Obtener sesión manualmente
    gen = get_db()
    session: Session = next(gen)
    try:
        cfg = session.query(EmailConfig).first()
        if not cfg:
            return {}
        return {
            "smtp_host": cfg.smtp_host,
            "smtp_port": cfg.smtp_port,
            "smtp_user": cfg.smtp_user,
            "smtp_password_set": bool(cfg.smtp_password),  # No devolver la contraseña
            "smtp_use_tls": cfg.smtp_use_tls,
            "from_name": cfg.from_name,
            "from_email": cfg.from_email,
            "gdpr_enabled": cfg.gdpr_enabled,
            "gdpr_email_subject": cfg.gdpr_email_subject,
            "gdpr_email_body_html": cfg.gdpr_email_body_html,
            "last_test_at": cfg.last_test_at.isoformat() if cfg.last_test_at else None,
            "last_test_ok": cfg.last_test_ok,
        }
    finally:
        try: next(gen)
        except StopIteration: pass


@router.put("/email")
def update_email_config(data: EmailConfigUpdate):
    """Actualiza la configuración SMTP/GDPR."""
    from ..database import get_db
    from ..models.customers import EmailConfig
    from datetime import datetime
    gen = get_db()
    session = next(gen)
    try:
        cfg = session.query(EmailConfig).first()
        if not cfg:
            from ..models.customers import EmailConfig as EC
            cfg = EC(id=1)
            session.add(cfg)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(cfg, field, value)
        cfg.updated_at = datetime.utcnow()
        session.commit()
        return {"ok": True, "message": "Configuración de correo actualizada."}
    finally:
        try: next(gen)
        except StopIteration: pass


@router.post("/email/test")
def test_email_config(data: EmailConfigUpdate):
    """Prueba la conexión SMTP enviando un correo de prueba al propio remitente."""
    from ..services.email_service import send_gdpr_email
    from ..database import get_db
    from ..models.customers import EmailConfig
    from datetime import datetime
    gen = get_db()
    session = next(gen)
    try:
        cfg = session.query(EmailConfig).first()
        # Usar valores del request o los guardados
        host = data.smtp_host or (cfg.smtp_host if cfg else "smtp.gmail.com")
        port = data.smtp_port or (cfg.smtp_port if cfg else 587)
        user = data.smtp_user or (cfg.smtp_user if cfg else "")
        pwd  = data.smtp_password or (cfg.smtp_password if cfg else "")
        tls  = data.smtp_use_tls if data.smtp_use_tls is not None else (cfg.smtp_use_tls if cfg else True)
        fname = data.from_name or (cfg.from_name if cfg else "Sistema POS")
        femail = data.from_email or (cfg.from_email if cfg else user)

        if not user or not pwd:
            return {"ok": False, "error": "Ingrese usuario y contraseña/app-password"}

        ok, error = send_gdpr_email(
            smtp_host=host, smtp_port=port, smtp_user=user, smtp_password=pwd,
            smtp_use_tls=tls, from_name=fname, from_email=femail,
            to_email=user,  # Enviar al mismo remitente como prueba
            subject="[Sistema POS] Prueba de conexión SMTP ✅",
            body_html=f"<h2>✅ Conexión SMTP funcionando correctamente</h2><p>Servidor: {host}:{port}<br>Usuario: {user}</p>",
        )
        if cfg:
            cfg.last_test_at = datetime.utcnow()
            cfg.last_test_ok = ok
            session.commit()
        if ok:
            return {"ok": True, "message": f"✅ Correo de prueba enviado a {user}"}
        return {"ok": False, "error": error}
    finally:
        try: next(gen)
        except StopIteration: pass


# ─── Endpoints de Impuestos (IVA) y Puntos de Emisión ───────────────────────

class TaxPeriodCreate(BaseModel):
    name: str
    percentage: float
    valid_from: str  # YYYY-MM-DD
    valid_until: Optional[str] = None  # YYYY-MM-DD
    is_active: bool = True

class EmissionPointCreate(BaseModel):
    branch_id: int
    code: str
    name: str
    invoice_sequential: int = 1

class EmissionPointUpdate(BaseModel):
    name: Optional[str] = None
    invoice_sequential: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/taxes/active")
def get_active_tax(db: Session = Depends(get_db)):
    from ..models.sales import TaxParameter
    from datetime import datetime
    now = datetime.utcnow()
    tax = db.query(TaxParameter).filter(
        TaxParameter.is_active == True,
        TaxParameter.valid_from <= now,
        or_(TaxParameter.valid_until == None, TaxParameter.valid_until >= now)
    ).first()
    rate = float(tax.percentage) if tax else 15.0
    return {"rate": rate, "name": tax.name if tax else "IVA 15%"}


@router.get("/taxes/periods")
def list_tax_periods(db: Session = Depends(get_db)):
    from ..models.sales import TaxParameter
    taxes = db.query(TaxParameter).order_by(TaxParameter.valid_from.desc()).all()
    return [{
        "id": t.id,
        "name": t.name,
        "percentage": float(t.percentage),
        "valid_from": t.valid_from.strftime("%Y-%m-%d"),
        "valid_until": t.valid_until.strftime("%Y-%m-%d") if t.valid_until else None,
        "is_active": t.is_active
    } for t in taxes]


@router.post("/taxes")
def create_tax_period(data: TaxPeriodCreate, db: Session = Depends(get_db)):
    from ..models.sales import TaxParameter
    from datetime import datetime
    
    try:
        valid_from_dt = datetime.strptime(data.valid_from, "%Y-%m-%d")
        valid_until_dt = datetime.strptime(data.valid_until, "%Y-%m-%d") if data.valid_until else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
    tax = TaxParameter(
        name=data.name,
        percentage=data.percentage,
        rate=data.percentage,
        valid_from=valid_from_dt,
        valid_until=valid_until_dt,
        is_active=data.is_active
    )
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return {"ok": True, "id": tax.id}


@router.put("/taxes/{tax_id}")
def update_tax_period(tax_id: int, is_active: bool, db: Session = Depends(get_db)):
    from ..models.sales import TaxParameter
    tax = db.get(TaxParameter, tax_id)
    if not tax:
        raise HTTPException(status_code=404, detail="Período tributario no encontrado")
    tax.is_active = is_active
    db.commit()
    return {"ok": True}


@router.get("/emission-points")
def list_emission_points(db: Session = Depends(get_db)):
    from ..models.core import EmissionPoint
    points = db.query(EmissionPoint).all()
    return [{
        "id": ep.id,
        "branch_id": ep.branch_id,
        "branch_name": ep.branch.name if ep.branch else "Sin Sucursal",
        "code": ep.code,
        "name": ep.name,
        "invoice_sequential": ep.invoice_sequential,
        "is_active": ep.is_active
    } for ep in points]


@router.post("/emission-points")
def create_emission_point(data: EmissionPointCreate, db: Session = Depends(get_db)):
    from ..models.core import EmissionPoint, Branch
    branch = db.get(Branch, data.branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        
    dup = db.query(EmissionPoint).filter(
        EmissionPoint.branch_id == data.branch_id,
        EmissionPoint.code == data.code
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="Ya existe un punto de emisión con este código en la sucursal")
        
    ep = EmissionPoint(
        branch_id=data.branch_id,
        code=data.code,
        name=data.name,
        invoice_sequential=data.invoice_sequential
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return {"ok": True, "id": ep.id}


@router.put("/emission-points/{ep_id}")
def update_emission_point(ep_id: int, data: EmissionPointUpdate, db: Session = Depends(get_db)):
    from ..models.core import EmissionPoint
    ep = db.get(EmissionPoint, ep_id)
    if not ep:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado")
    if data.name is not None:
        ep.name = data.name
    if data.invoice_sequential is not None:
        ep.invoice_sequential = data.invoice_sequential
    if data.is_active is not None:
        ep.is_active = data.is_active
    db.commit()
    return {"ok": True}

