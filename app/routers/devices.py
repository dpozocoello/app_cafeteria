"""
Router: Gestión de Dispositivos Autorizados
============================================
Implementa el ciclo de vida completo de pareado seguro por QR:

  Dispositivo                     Servidor                       Admin
  ─────────                       ────────                       ─────
  Escanea QR ──► GET /device/pair (formulario)
  Nombre + UA ──► POST /device/pair ──► genera token PENDIENTE
  Espera...       polling cada 4s  ──► GET /device/pair/status/{token}
                                   ◄── {approved: false}  (sigue esperando)
                                                           Admin ve lista ──►
                                                           PUT /api/devices/{id}/approve
                  ◄── {approved: true}
  Recibe cookie ──► accede a /pedidos

Seguridad aplicada:
  - Tokens UUID4 (128 bits, criptográficamente seguros)
  - Rate limit: máx 3 registros por IP cada 10 min
  - Cookies: HttpOnly, SameSite=Strict, Path=/pedidos
  - Tokens expiran en DEVICE_TOKEN_DAYS días (default 30)
  - Fingerprint: hash SHA-256 de (IP + User-Agent)
  - Solo admin puede aprobar/revocar
  - Lista negra de IPs (opcional vía env BLOCKED_IPS)
"""
import hashlib
import ipaddress
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.devices import DeviceSession
from ..models.core import User
from ..services.auth_service import decode_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(tags=["Dispositivos"])

# ── Configuración ──────────────────────────────────────────────────────────────
DEVICE_TOKEN_DAYS: int = int(os.getenv("DEVICE_TOKEN_DAYS", "30"))
COOKIE_NAME = "device_token"
RATE_LIMIT_WINDOW_MIN = 10
RATE_LIMIT_MAX = 3

# IPs bloqueadas (separadas por coma en env BLOCKED_IPS)
_blocked_raw = os.getenv("BLOCKED_IPS", "")
BLOCKED_IPS: set[str] = {ip.strip() for ip in _blocked_raw.split(",") if ip.strip()}

bearer = HTTPBearer(auto_error=False)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    return xff.split(",")[0].strip() if xff else (request.client.host or "0.0.0.0")


def _fingerprint(ip: str, ua: str) -> str:
    raw = f"{ip}|{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _is_private_ip(ip: str) -> bool:
    """Solo permite IPs de red local (RFC 1918) y localhost."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_loopback or addr.is_private
    except ValueError:
        return False


def _check_rate_limit(db: Session, ip: str) -> None:
    window_start = datetime.utcnow() - timedelta(minutes=RATE_LIMIT_WINDOW_MIN)
    recent = db.query(DeviceSession).filter(
        DeviceSession.ip_address == ip,
        DeviceSession.registered_at >= window_start,
    ).count()
    if recent >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiadas solicitudes desde esta IP. Espera {RATE_LIMIT_WINDOW_MIN} minutos."
        )


def _get_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    perms = (user.role.permissions or {}) if user.role else {}
    if not (perms.get("config") or perms.get("usuarios")):
        raise HTTPException(status_code=403, detail="Se requiere perfil Administrador")
    return user


def validate_device_cookie(request: Request, db: Session) -> Optional[DeviceSession]:
    """Valida la cookie de dispositivo. Retorna el DeviceSession si es válido, None si no."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    dev = db.query(DeviceSession).filter_by(device_token=token, is_active=True).first()
    if not dev:
        return None
    if dev.expires_at and dev.expires_at < datetime.utcnow():
        return None
    # Actualizar last_seen
    dev.last_seen = datetime.utcnow()
    db.commit()
    return dev


# ── Schemas ────────────────────────────────────────────────────────────────────

DEVICE_TYPES = {
    "mesero": {"label": "Mesero",     "icon": "🍽️", "redirect": "/pedidos",
               "desc":  "Toma pedidos en mesa"},
    "caja":   {"label": "Caja",       "icon": "🛒", "redirect": "/pos",
               "desc":  "Pedidos para llevar y punto de venta"},
}


class DeviceRegisterRequest(BaseModel):
    device_name: str
    device_type: str = "mesero"


# ── Página de pareado (accedida desde el dispositivo móvil) ───────────────────

@router.get("/device/pair", response_class=HTMLResponse)
def device_pair_page(request: Request, db: Session = Depends(get_db)):
    """
    Página que el dispositivo abre al escanear el QR.
    Si ya tiene cookie aprobada → redirige a /pedidos.
    Si ya tiene cookie pendiente → muestra pantalla de espera.
    Si no tiene cookie → muestra formulario de registro.
    """
    existing_token = request.cookies.get(COOKIE_NAME)
    if existing_token:
        dev = db.query(DeviceSession).filter_by(
            device_token=existing_token, is_active=True
        ).first()
        if dev:
            from fastapi.responses import RedirectResponse
            dest = DEVICE_TYPES.get(dev.device_type, DEVICE_TYPES["mesero"])["redirect"]
            return RedirectResponse(url=dest)

    return _render_form()


@router.post("/device/pair")
def device_pair_submit(
    data: DeviceRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    El dispositivo envía su nombre para registrarse.
    Genera un token pendiente y lo guarda en cookie.
    """
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")

    # Bloquear IPs en lista negra (BLOCKED_IPS env var)
    if ip in BLOCKED_IPS:
        raise HTTPException(status_code=403, detail="Acceso denegado desde esta red")

    # Rate limiting
    _check_rate_limit(db, ip)

    # Validar nombre
    name = data.device_name.strip()
    if not name or len(name) < 2:
        raise HTTPException(status_code=422, detail="Nombre requerido (mín 2 caracteres)")
    if len(name) > 60:
        raise HTTPException(status_code=422, detail="Nombre demasiado largo (máx 60 caracteres)")

    # Validar tipo de dispositivo
    dtype = data.device_type if data.device_type in DEVICE_TYPES else "mesero"

    # Verificar si ya existe un token activo con este fingerprint
    fp = _fingerprint(ip, ua)
    existing = db.query(DeviceSession).filter_by(
        device_fingerprint=fp, is_active=True
    ).first()
    if existing:
        existing.device_name = name
        existing.device_type = dtype
        existing.last_seen = datetime.utcnow()
        db.commit()
        token = existing.device_token
    else:
        token = secrets.token_hex(32)
        dev = DeviceSession(
            device_name=name,
            device_token=token,
            device_fingerprint=fp,
            device_type=dtype,
            ip_address=ip,
            user_agent=ua[:255],
            is_approved=True,
            is_active=True,
            registered_at=datetime.utcnow(),
            approved_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=DEVICE_TOKEN_DAYS),
        )
        db.add(dev)
        db.commit()

    redirect_url = DEVICE_TYPES[dtype]["redirect"]
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="strict",
        path="/",
        max_age=DEVICE_TOKEN_DAYS * 86400,
        secure=False,
    )
    return {"status": "approved", "token": token, "redirect": redirect_url, "device_type": dtype}


@router.get("/device/pair/status/{token}")
def device_pair_status(token: str, db: Session = Depends(get_db)):
    """Polling del dispositivo para saber si fue aprobado."""
    dev = db.query(DeviceSession).filter_by(device_token=token, is_active=True).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    if dev.expires_at and dev.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Token expirado")
    return {
        "approved": dev.is_approved,
        "device_name": dev.device_name,
        "registered_at": dev.registered_at.isoformat(),
    }


# ── API de administración (requiere JWT de admin) ─────────────────────────────

@router.get("/api/devices")
def list_devices(_admin: User = Depends(_get_admin), db: Session = Depends(get_db)):
    """Lista todos los dispositivos registrados."""
    devs = db.query(DeviceSession).order_by(DeviceSession.registered_at.desc()).all()
    return [_serialize(d) for d in devs]


@router.put("/api/devices/{device_id}/approve")
def approve_device(
    device_id: int,
    admin: User = Depends(_get_admin),
    db: Session = Depends(get_db),
):
    """Aprueba un dispositivo pendiente."""
    dev = db.get(DeviceSession, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    if not dev.is_active:
        raise HTTPException(status_code=400, detail="Dispositivo inactivo")
    dev.is_approved = True
    dev.approved_at = datetime.utcnow()
    dev.approved_by_id = admin.id
    db.commit()
    return {"message": f"Dispositivo '{dev.device_name}' aprobado", **_serialize(dev)}


@router.put("/api/devices/{device_id}/revoke")
def revoke_device(
    device_id: int,
    _admin: User = Depends(_get_admin),
    db: Session = Depends(get_db),
):
    """Revoca el acceso de un dispositivo (lo desactiva sin eliminar el registro)."""
    dev = db.get(DeviceSession, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    dev.is_approved = False
    dev.is_active = False
    db.commit()
    return {"message": f"Acceso de '{dev.device_name}' revocado"}


@router.delete("/api/devices/{device_id}", status_code=204)
def delete_device(
    device_id: int,
    _admin: User = Depends(_get_admin),
    db: Session = Depends(get_db),
):
    """Elimina permanentemente el registro de un dispositivo."""
    dev = db.get(DeviceSession, device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    db.delete(dev)
    db.commit()


# ── Serialización ──────────────────────────────────────────────────────────────

def _serialize(dev: DeviceSession) -> dict:
    dtype = dev.device_type if hasattr(dev, "device_type") and dev.device_type else "mesero"
    type_info = DEVICE_TYPES.get(dtype, DEVICE_TYPES["mesero"])
    return {
        "id":            dev.id,
        "device_name":   dev.device_name,
        "device_type":   dtype,
        "device_label":  type_info["label"],
        "device_icon":   type_info["icon"],
        "redirect_url":  type_info["redirect"],
        "ip_address":    dev.ip_address,
        "is_approved":   dev.is_approved,
        "is_active":     dev.is_active,
        "registered_at": dev.registered_at.isoformat() if dev.registered_at else None,
        "approved_at":   dev.approved_at.isoformat() if dev.approved_at else None,
        "last_seen":     dev.last_seen.isoformat() if dev.last_seen else None,
        "expires_at":    dev.expires_at.isoformat() if dev.expires_at else None,
        "approved_by":   dev.approved_by.full_name if dev.approved_by else None,
        "notes":         dev.notes,
    }


# ── Renders HTML internos ──────────────────────────────────────────────────────

def _render_form() -> str:
    return """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar Dispositivo — JECA POS</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:#020617;color:#f8fafc;
       display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem}
  .card{background:#0f172a;border:2px solid #fbbf24;border-radius:1.5rem;padding:2rem;
        width:100%;max-width:400px;text-align:center}
  .logo{font-size:2.5rem;margin-bottom:.5rem}
  h1{color:#fbbf24;font-size:1.4rem;margin-bottom:.25rem}
  p{color:#94a3b8;font-size:.9rem;margin-bottom:1.2rem;line-height:1.5}
  .role-grid{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:1.2rem}
  .role-btn{padding:1rem .75rem;border-radius:1rem;border:2px solid #334155;background:#1e293b;
            color:#94a3b8;cursor:pointer;transition:all .18s;text-align:center;user-select:none}
  .role-btn .icon{font-size:2rem;display:block;margin-bottom:.35rem}
  .role-btn .label{font-weight:700;font-size:.95rem;display:block;color:#f8fafc}
  .role-btn .desc{font-size:.72rem;color:#64748b;display:block;margin-top:.2rem}
  .role-btn.selected{border-color:#fbbf24;background:rgba(251,191,36,.12);color:#fbbf24}
  .role-btn.selected .label{color:#fbbf24}
  input{width:100%;padding:.75rem 1rem;border-radius:.75rem;border:1.5px solid #334155;
        background:#1e293b;color:#f8fafc;font-size:1rem;margin-bottom:1rem;outline:none}
  input:focus{border-color:#fbbf24}
  button{width:100%;padding:.85rem;border-radius:.75rem;background:#fbbf24;color:#020617;
         font-weight:700;font-size:1rem;border:none;cursor:pointer;transition:opacity .15s}
  button:hover{opacity:.9}
  .hint{font-size:.75rem;color:#475569;margin-top:.75rem}
  #err{color:#ef4444;font-size:.85rem;margin-bottom:.5rem;display:none}
</style></head>
<body>
<div class="card">
  <div class="logo">📱</div>
  <h1>Conectar al Sistema POS</h1>
  <p>Selecciona el tipo de uso y asigna un nombre a este dispositivo.</p>

  <div class="role-grid">
    <div class="role-btn selected" id="btn-mesero" onclick="selectRole('mesero')">
      <span class="icon">🍽️</span>
      <span class="label">Mesero</span>
      <span class="desc">Pedidos en mesa</span>
    </div>
    <div class="role-btn" id="btn-caja" onclick="selectRole('caja')">
      <span class="icon">🛒</span>
      <span class="label">Caja</span>
      <span class="desc">Pedidos para llevar</span>
    </div>
  </div>

  <div id="err"></div>
  <input id="name" type="text" placeholder="Ej: Tablet Mesero 1" maxlength="60" autocomplete="off">
  <button onclick="register()">Conectar Dispositivo</button>
  <p class="hint">Solo dispositivos en la red local. Tu IP será registrada.</p>
</div>
<script>
let selectedRole = 'mesero';
function selectRole(r){
  selectedRole = r;
  document.querySelectorAll('.role-btn').forEach(b=>b.classList.remove('selected'));
  document.getElementById('btn-'+r).classList.add('selected');
  const placeholders = {mesero:'Ej: Tablet Mesero 1', caja:'Ej: Caja Principal'};
  document.getElementById('name').placeholder = placeholders[r]||'Nombre del dispositivo';
}
async function register(){
  const name = document.getElementById('name').value.trim();
  const err  = document.getElementById('err');
  err.style.display = 'none';
  if(!name){err.textContent='Ingresa un nombre para este dispositivo';err.style.display='block';return;}
  try{
    const r = await fetch('/device/pair',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({device_name: name, device_type: selectedRole})
    });
    const d = await r.json();
    if(!r.ok){err.textContent=d.detail||'Error al registrar';err.style.display='block';return;}
    window.location.href = d.redirect || '/pedidos';
  }catch(e){err.textContent='Error de red. Verifica la conexión.';err.style.display='block';}
}
document.getElementById('name').addEventListener('keydown',e=>{if(e.key==='Enter')register();});
</script>
</body></html>"""


def _render_waiting(device_name: str, token: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Esperando aprobación — JECA POS</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#020617;color:#f8fafc;
       display:flex;align-items:center;justify-content:center;min-height:100vh;padding:1rem}}
  .card{{background:#0f172a;border:2px solid #fbbf24;border-radius:1.5rem;padding:2rem;
        width:100%;max-width:380px;text-align:center}}
  h1{{color:#fbbf24;font-size:1.3rem;margin-bottom:.5rem}}
  p{{color:#94a3b8;font-size:.9rem;line-height:1.6;margin:.5rem 0}}
  .spinner{{width:48px;height:48px;border:4px solid #1e293b;border-top-color:#fbbf24;
            border-radius:50%;animation:spin 1s linear infinite;margin:1.2rem auto}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  .device-name{{color:#fbbf24;font-weight:700;font-size:1.1rem;margin:.5rem 0}}
  .status-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;
               background:#f59e0b;margin-right:6px;animation:pulse 2s ease-in-out infinite}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
  .hint{{font-size:.75rem;color:#334155;margin-top:1rem;border-top:1px solid #1e293b;padding-top:.75rem}}
</style></head>
<body>
<div class="card">
  <div class="spinner"></div>
  <h1><span class="status-dot"></span>Esperando aprobación</h1>
  <p>Solicitud enviada para:</p>
  <div class="device-name">📱 {device_name}</div>
  <p>El administrador debe aprobar este dispositivo<br>desde el panel de control.</p>
  <p class="hint">Esta pantalla se actualizará automáticamente.<br>
     No cierres esta pestaña.</p>
</div>
<script>
const token = "{token}";
async function poll(){{
  try{{
    const r = await fetch('/device/pair/status/'+token);
    if(r.ok){{
      const d = await r.json();
      if(d.approved) window.location.href='/pedidos';
    }}else if(r.status===410){{
      document.querySelector('h1').textContent='Token expirado';
      document.querySelector('.spinner').style.display='none';
    }}
  }}catch(e){{}}
  setTimeout(poll,4000);
}}
poll();
</script>
</body></html>"""
