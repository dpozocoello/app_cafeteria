from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Branch(Base):
    """Sucursal / establecimiento. Código SRI Ecuador."""
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(255))
    sri_establishment_code: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[List["User"]] = relationship(back_populates="branch")
    sales: Mapped[List["Sale"]] = relationship(back_populates="branch")


class Role(Base):
    """
    Roles RBAC del sistema.
    ISO 27001 – A.9.2.2: Aprovisionamiento de acceso por roles.
    """
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    # Permisos granulares (JSON): {"ventas": True, "inventario": True, ...}
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    users: Mapped[List["User"]] = relationship(back_populates="role")


class User(Base):
    """
    Usuarios del sistema.
    ISO 27001 controles aplicados:
      - A.9.2.1: Registro y baja controlada
      - A.9.2.4: Gestión de autenticación secreta (bcrypt)
      - A.9.4.3: Política de contraseñas (complejidad, expiración)
      - A.9.4.2: Bloqueo por intentos fallidos
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))

    # ── Estado de cuenta ──────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)   # Bloqueo temporal
    locked_reason: Mapped[Optional[str]] = mapped_column(String(255))

    # ── Seguridad de contraseña (A.9.4.3) ────────────────────────────────────
    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Expiración configurable

    # ── Trazabilidad (A.12.4.1) ───────────────────────────────────────────────
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45))
    last_failed_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    role: Mapped["Role"] = relationship(back_populates="users")
    branch: Mapped["Branch"] = relationship(back_populates="users")
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user", foreign_keys="AuditLog.user_id")
    password_history: Mapped[List["PasswordHistory"]] = relationship(back_populates="user")


class PasswordHistory(Base):
    """
    Historial de contraseñas para prevenir reutilización.
    ISO 27001 – A.9.4.3: El sistema debe recordar las últimas N contraseñas.
    """
    __tablename__ = "password_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    changed_by_ip: Mapped[Optional[str]] = mapped_column(String(45))

    user: Mapped["User"] = relationship(back_populates="password_history")


class SecurityPolicy(Base):
    """
    Política de seguridad configurable por administrador.
    ISO 27001 – A.9.4.3 & A.9.2.4.
    Almacena una única fila de configuración global.
    """
    __tablename__ = "security_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Contraseñas
    min_password_length: Mapped[int] = mapped_column(SmallInteger, default=8)
    require_uppercase: Mapped[bool] = mapped_column(Boolean, default=True)
    require_numbers: Mapped[bool] = mapped_column(Boolean, default=True)
    require_symbols: Mapped[bool] = mapped_column(Boolean, default=True)
    password_expiry_days: Mapped[int] = mapped_column(SmallInteger, default=90)   # 0 = sin expiración
    password_history_count: Mapped[int] = mapped_column(SmallInteger, default=5)  # Recordar últimas N

    # Bloqueo de cuenta
    max_failed_attempts: Mapped[int] = mapped_column(SmallInteger, default=5)
    lockout_duration_minutes: Mapped[int] = mapped_column(SmallInteger, default=30)

    # Sesión
    session_timeout_minutes: Mapped[int] = mapped_column(SmallInteger, default=60)
    jwt_expiry_minutes: Mapped[int] = mapped_column(SmallInteger, default=60)

    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base):
    """
    Registro de auditoría inmutable.
    ISO 27001 – A.12.4.1: Los eventos deben ser registrados y protegidos.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))   # None para eventos del sistema
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    action: Mapped[str] = mapped_column(String(50))  # LOGIN, LOGIN_FAILED, CREATE, UPDATE, DELETE, LOGOUT
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))
    # Campo username para conservar la traza si el usuario es eliminado
    username_snapshot: Mapped[Optional[str]] = mapped_column(String(50))

    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs", foreign_keys=[user_id])
