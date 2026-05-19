"""
AuthService - Servicio de Autenticación y Seguridad
ISO 27001:2022 - Dominio A.9 (Control de Acceso) & A.12.4 (Logging)

Controles implementados:
  A.9.2.4  Gestión de autenticación secreta → bcrypt costo 12
  A.9.4.2  Inicio de sesión seguro → bloqueo por intentos fallidos, JWT
  A.9.4.3  Gestión de contraseñas → complejidad, expiración, historial
  A.12.4.1 Registro de eventos → AuditLog inmutable
"""
import re
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from ..models.core import User, AuditLog, PasswordHistory, SecurityPolicy, Role

# Clave secreta JWT (en producción: leer de .env / HSM)
JWT_SECRET = "coffeeapp-jwt-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"


# ─── Contraseñas ─────────────────────────────────────────────────────────────

def _get_policy(db: Session) -> SecurityPolicy:
    policy = db.query(SecurityPolicy).first()
    if not policy:
        policy = SecurityPolicy()
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def hash_password(plain: str) -> str:
    """Genera hash bcrypt con costo 12 (ISO 27001 - A.9.2.4)."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def validate_password_complexity(plain: str, db: Session) -> Tuple[bool, str]:
    """
    Valida la complejidad de contraseña según la política activa.
    Retorna (es_valida, mensaje_error).
    """
    policy = _get_policy(db)
    errors = []

    if len(plain) < policy.min_password_length:
        errors.append(f"Mínimo {policy.min_password_length} caracteres")
    if policy.require_uppercase and not re.search(r"[A-Z]", plain):
        errors.append("Debe contener al menos una mayúscula")
    if policy.require_numbers and not re.search(r"\d", plain):
        errors.append("Debe contener al menos un número")
    if policy.require_symbols and not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", plain):
        errors.append("Debe contener al menos un símbolo especial (!@#$...)")

    if errors:
        return False, " · ".join(errors)
    return True, ""


def check_password_history(user: User, new_plain: str, db: Session) -> bool:
    """
    Devuelve True si la contraseña ya fue usada (en las últimas N según política).
    ISO 27001 – A.9.4.3: Prevención de reutilización.
    """
    policy = _get_policy(db)
    history = (
        db.query(PasswordHistory)
        .filter_by(user_id=user.id)
        .order_by(PasswordHistory.changed_at.desc())
        .limit(policy.password_history_count)
        .all()
    )
    return any(verify_password(new_plain, h.password_hash) for h in history)


# ─── Autenticación ────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str, role: str, minutes: int = 60) -> str:
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def authenticate_user(
    db: Session,
    username: str,
    password: str,
    ip_address: str = "unknown",
    user_agent: str = ""
) -> Tuple[Optional[User], str, Optional[str]]:
    """
    Autenticar usuario con controles ISO 27001.
    Retorna (user | None, mensaje_error, jwt_token | None)
    """
    user = db.query(User).filter_by(username=username).first()
    policy = _get_policy(db)

    def log_failure(reason: str, uid: Optional[int] = None, uname: Optional[str] = None):
        _write_audit(db, uid, "LOGIN_FAILED", "User", uid or 0, ip_address,
                     user_agent, {"reason": reason}, username_snapshot=uname or username)

    # 1. Usuario no existe
    if not user:
        log_failure("Usuario no encontrado")
        return None, "Credenciales inválidas", None

    # 2. Cuenta inactiva
    if not user.is_active:
        log_failure("Cuenta inactiva", user.id, user.username)
        return None, "Cuenta desactivada. Contacte al administrador.", None

    # 3. Cuenta bloqueada
    if user.is_locked:
        if user.locked_until and datetime.utcnow() < user.locked_until:
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            log_failure(f"Cuenta bloqueada - {remaining} min restantes", user.id, user.username)
            return None, f"Cuenta bloqueada por {remaining} minutos más.", None
        else:
            # Desbloquear automáticamente si expiró
            user.is_locked = False
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()

    # 4. Contraseña incorrecta
    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        user.last_failed_login = datetime.utcnow()

        if user.failed_login_attempts >= policy.max_failed_attempts:
            user.is_locked = True
            user.locked_until = datetime.utcnow() + timedelta(minutes=policy.lockout_duration_minutes)
            user.locked_reason = f"Bloqueo automático: {policy.max_failed_attempts} intentos fallidos"
            db.commit()
            log_failure(f"Cuenta bloqueada por {policy.max_failed_attempts} intentos", user.id, user.username)
            return None, f"Cuenta bloqueada por {policy.lockout_duration_minutes} minutos.", None

        db.commit()
        remaining = policy.max_failed_attempts - user.failed_login_attempts
        log_failure(f"Contraseña incorrecta (intento {user.failed_login_attempts})", user.id, user.username)
        return None, f"Credenciales inválidas. {remaining} intento(s) restante(s).", None

    # 5. Contraseña expirada
    if user.password_expires_at and datetime.utcnow() > user.password_expires_at:
        user.must_change_password = True
        db.commit()

    # 6. Login exitoso
    user.failed_login_attempts = 0
    user.last_login = datetime.utcnow()
    user.last_login_ip = ip_address
    user.is_locked = False
    db.commit()

    role_name = user.role.name if user.role else "Operador"
    token = create_access_token(user.id, user.username, role_name, policy.jwt_expiry_minutes)

    _write_audit(db, user.id, "LOGIN", "User", user.id, ip_address, user_agent,
                 {"result": "success"}, username_snapshot=user.username)

    return user, "", token


# ─── Auditoría ────────────────────────────────────────────────────────────────

def _write_audit(db, user_id, action, entity, entity_id,
                 ip, user_agent, new_values=None, username_snapshot=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        ip_address=ip,
        user_agent=user_agent,
        new_values=new_values,
        username_snapshot=username_snapshot,
    )
    db.add(log)
    db.commit()


def log_action(db: Session, user_id: int, action: str, entity: str,
               entity_id: int = 0, ip: str = "", user_agent: str = "",
               old_values: dict = None, new_values: dict = None):
    """Helper público para registrar acciones desde otros módulos."""
    _write_audit(db, user_id, action, entity, entity_id, ip, user_agent, new_values)
