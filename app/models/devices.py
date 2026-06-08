"""
Modelo: DeviceSession
Registra y gestiona los dispositivos autorizados para acceder al módulo
de pedidos desde la red local (tablets, teléfonos de meseros).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core import Base

if TYPE_CHECKING:
    from .core import User


class DeviceSession(Base):
    """
    Cada registro representa un dispositivo físico (tablet/teléfono)
    que ha solicitado acceso a /pedidos mediante el flujo QR.

    Flujo de aprobación:
      1. Dispositivo escanea QR → POST /device/pair → estado PENDIENTE
      2. Admin revisa lista → PUT /api/devices/{id}/approve
      3. Dispositivo refresca /device/pair → recibe cookie segura
      4. Cookie se valida en cada request a /pedidos
    """
    __tablename__ = "device_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identidad del dispositivo
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128))
    # Tipo de rol: "mesero" → /pedidos  |  "caja" → /pos
    device_type: Mapped[str] = mapped_column(String(20), default="mesero", nullable=False)

    # Red
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))

    # Estado
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auditoría
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Trazabilidad
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    approved_by: Mapped[Optional[User]] = relationship(
        "User", foreign_keys=[approved_by_id]
    )
