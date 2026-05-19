"""
Router: Configuración del Sistema (Apariencia + BD)
Endpoints para leer y escribir el archivo .env desde el Panel Admin.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import shutil
import os
from ..config import get_theme, save_env_values, get_engine_type, refresh_theme, BASE_DIR

router = APIRouter(prefix="/api/settings", tags=["Configuración"])

# ─── Schemas ──────────────────────────────────────────────────────────────────

class ThemeUpdate(BaseModel):
    brand_name:     Optional[str] = None
    brand_tagline:  Optional[str] = None
    font_family:    Optional[str] = None
    color_bg:       Optional[str] = None
    color_sidebar:  Optional[str] = None
    color_card:     Optional[str] = None
    color_accent:   Optional[str] = None
    color_text:     Optional[str] = None
    color_muted:    Optional[str] = None
    color_success:  Optional[str] = None
    color_danger:   Optional[str] = None
    color_info:     Optional[str] = None


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
def get_theme_settings():
    return get_theme()


@router.put("/theme")
def update_theme(data: ThemeUpdate):
    updates = {k.upper(): v for k, v in data.model_dump(exclude_none=True).items()}
    # Formatear claves: color_bg → COLOR_BG, brand_name → BRAND_NAME
    save_env_values(updates)
    return {"ok": True, "message": "Tema actualizado. Recarga el navegador para ver los cambios."}


@router.get("/css")
def get_dynamic_css():
    """Genera el CSS con las variables del .env actual."""
    theme = get_theme()
    css = f"""
/* CoffeeApp - CSS Dinámico generado desde /api/settings/css */
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
        "sqlite_path": _get("SQLITE_PATH", "./coffee_app_v2.db"),
        "pg_host":     _get("PG_HOST", "localhost"),
        "pg_port":     _get("PG_PORT", "5432"),
        "pg_database": _get("PG_DATABASE", "coffeeapp"),
        "pg_user":     _get("PG_USER", "postgres"),
        "my_host":     _get("MYSQL_HOST", "localhost"),
        "my_port":     _get("MYSQL_PORT", "3306"),
        "my_database": _get("MYSQL_DATABASE", "coffeeapp"),
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
            path = data.sqlite_path or "./coffee_app_v2.db"
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
        fname = data.from_name or (cfg.from_name if cfg else "CoffeeApp")
        femail = data.from_email or (cfg.from_email if cfg else user)

        if not user or not pwd:
            return {"ok": False, "error": "Ingrese usuario y contraseña/app-password"}

        ok, error = send_gdpr_email(
            smtp_host=host, smtp_port=port, smtp_user=user, smtp_password=pwd,
            smtp_use_tls=tls, from_name=fname, from_email=femail,
            to_email=user,  # Enviar al mismo remitente como prueba
            subject="[CoffeeApp] Prueba de conexión SMTP ✅",
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

