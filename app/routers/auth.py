"""
Router: Autenticación y Gestión de Usuarios
ISO 27001:2022 - A.9 Control de Acceso
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import os

from ..database import get_db
from ..models.core import User, Role, Branch, SecurityPolicy, PasswordHistory, AuditLog
from ..services.auth_service import (
    authenticate_user, hash_password, validate_password_complexity,
    check_password_history, decode_token, log_action
)

router = APIRouter(tags=["Autenticación y Usuarios"])
bearer = HTTPBearer(auto_error=False)


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role_id: int
    branch_id: int
    password: str
    must_change_password: bool = True


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    branch_id: Optional[int] = None
    is_active: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class AdminPasswordReset(BaseModel):
    new_password: str
    must_change_on_next_login: bool = True


class SecurityPolicyUpdate(BaseModel):
    min_password_length: int = 8
    require_uppercase: bool = True
    require_numbers: bool = True
    require_symbols: bool = True
    password_expiry_days: int = 90
    password_history_count: int = 5
    max_failed_attempts: int = 5
    lockout_duration_minutes: int = 30
    session_timeout_minutes: int = 60
    jwt_expiry_minutes: int = 60


# ─── Helper: obtener usuario actual desde JWT ─────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.role or current_user.role.name != "Administrador":
        raise HTTPException(status_code=403, detail="Se requieren permisos de Administrador")
    return current_user


# ─── Autenticación ────────────────────────────────────────────────────────────

@router.post("/api/auth/login")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("User-Agent", "")
    user, error, token = authenticate_user(db, data.username, data.password, ip, ua)
    if not user:
        raise HTTPException(status_code=401, detail=error)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "must_change_password": user.must_change_password,
        }
    }


@router.post("/api/auth/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    log_action(db, current_user.id, "LOGOUT", "User", current_user.id, ip)
    return {"message": "Sesión cerrada correctamente"}


@router.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role.name if current_user.role else None,
        "last_login": current_user.last_login,
        "must_change_password": current_user.must_change_password,
    }


# ─── Cambio de Contraseña ─────────────────────────────────────────────────────

@router.post("/api/auth/change-password")
def change_password(
    request: Request,
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from ..services.auth_service import verify_password
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")

    valid, msg = validate_password_complexity(data.new_password, db)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    if check_password_history(current_user, data.new_password, db):
        raise HTTPException(status_code=400, detail="No puedes reutilizar una contraseña reciente")

    ip = request.client.host if request.client else "unknown"
    # Guardar en historial
    db.add(PasswordHistory(user_id=current_user.id,
                           password_hash=current_user.password_hash,
                           changed_by_ip=ip))
    current_user.password_hash = hash_password(data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.must_change_password = False

    from ..models.core import SecurityPolicy
    policy = db.query(SecurityPolicy).first()
    if policy and policy.password_expiry_days > 0:
        current_user.password_expires_at = datetime.utcnow() + timedelta(days=policy.password_expiry_days)

    log_action(db, current_user.id, "PASSWORD_CHANGE", "User", current_user.id, ip)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}


# ─── CRUD de Usuarios (solo Administrador) ───────────────────────────────────

@router.get("/api/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = db.query(User).all()
    return [{
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "email": u.email,
        "phone": u.phone,
        "role": u.role.name if u.role else None,
        "role_id": u.role_id,
        "branch_id": u.branch_id,
        "branch": u.branch.name if u.branch else None,
        "is_active": u.is_active,
        "is_locked": u.is_locked,
        "failed_login_attempts": u.failed_login_attempts,
        "last_login": u.last_login,
        "must_change_password": u.must_change_password,
        "created_at": u.created_at,
    } for u in users]


@router.post("/api/users", status_code=201)
def create_user(
    request: Request,
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if db.query(User).filter_by(username=data.username).first():
        raise HTTPException(status_code=400, detail=f"Usuario '{data.username}' ya existe")
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(status_code=400, detail=f"Email '{data.email}' ya registrado")

    valid, msg = validate_password_complexity(data.password, db)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Contraseña no cumple política: {msg}")

    policy = db.query(SecurityPolicy).first()
    expires = None
    if policy and policy.password_expiry_days > 0:
        expires = datetime.utcnow() + timedelta(days=policy.password_expiry_days)

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        role_id=data.role_id,
        branch_id=data.branch_id,
        password_hash=hash_password(data.password),
        must_change_password=data.must_change_password,
        password_changed_at=datetime.utcnow(),
        password_expires_at=expires,
        created_by_id=admin.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ip = request.client.host if request.client else "unknown"
    log_action(db, admin.id, "CREATE", "User", user.id, ip,
               new_values={"username": user.username, "role_id": user.role_id})
    return {"id": user.id, "username": user.username, "message": "Usuario creado"}


@router.put("/api/users/{user_id}")
def update_user(
    request: Request,
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    old = {"email": user.email, "role_id": user.role_id, "is_active": user.is_active}
    for field, val in data.model_dump(exclude_none=True).items():
        setattr(user, field, val)
    user.updated_at = datetime.utcnow()
    db.commit()
    ip = request.client.host if request.client else "unknown"
    log_action(db, admin.id, "UPDATE", "User", user_id, ip, old_values=old,
               new_values=data.model_dump(exclude_none=True))
    return {"message": "Usuario actualizado"}


@router.post("/api/users/{user_id}/reset-password")
def admin_reset_password(
    request: Request,
    user_id: int,
    data: AdminPasswordReset,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    valid, msg = validate_password_complexity(data.new_password, db)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Contraseña no cumple política: {msg}")

    ip = request.client.host if request.client else "unknown"
    db.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash, changed_by_ip=ip))
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = data.must_change_on_next_login
    user.password_changed_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    db.commit()
    log_action(db, admin.id, "PASSWORD_RESET", "User", user_id, ip,
               new_values={"reset_by": admin.username})
    return {"message": "Contraseña restablecida"}


@router.post("/api/users/{user_id}/unlock")
def unlock_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_locked = False
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"message": "Cuenta desbloqueada"}


@router.delete("/api/users/{user_id}", status_code=204)
def deactivate_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario")
    # ISO 27001: no eliminar, solo desactivar para conservar la trazabilidad
    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    ip = request.client.host if request.client else "unknown"
    log_action(db, admin.id, "DEACTIVATE", "User", user_id, ip)


# ─── Roles ────────────────────────────────────────────────────────────────────

@router.get("/api/roles")
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()


# ─── Política de Seguridad ───────────────────────────────────────────────────

@router.get("/api/security/policy")
def get_security_policy(db: Session = Depends(get_db)):
    policy = db.query(SecurityPolicy).first()
    if not policy:
        policy = SecurityPolicy()
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


@router.put("/api/security/policy")
def update_security_policy(
    request: Request,
    data: SecurityPolicyUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    policy = db.query(SecurityPolicy).first()
    if not policy:
        policy = SecurityPolicy()
        db.add(policy)
    for field, val in data.model_dump().items():
        setattr(policy, field, val)
    policy.updated_at = datetime.utcnow()
    policy.updated_by_id = admin.id
    db.commit()
    ip = request.client.host if request.client else "unknown"
    log_action(db, admin.id, "UPDATE", "SecurityPolicy", policy.id, ip,
               new_values=data.model_dump())
    return {"message": "Política de seguridad actualizada"}


# ─── Páginas HTML ─────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
def get_login_page():
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "login.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


@router.get("/admin/users", response_class=HTMLResponse)
def get_users_page():
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin_users.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()
