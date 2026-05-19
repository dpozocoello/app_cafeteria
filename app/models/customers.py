"""
Modelos: Customer (clientes de delivery/llevar) y EmailConfig (SMTP + GDPR).
Cumplimiento LOPDP Ecuador / GDPR - Protección de datos personales.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .core import Base


class Customer(Base):
    """
    Cliente registrado en punto de venta (delivery, llevar, mesa especial).
    Datos persistidos de forma resiliente para cumplimiento LOPDP Ecuador.
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Datos de identificación
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Tipo de servicio y datos de entrega
    customer_type: Mapped[str] = mapped_column(String(20), default="LLEVAR")  # MESA | LLEVAR | DOMICILIO
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    delivery_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, unique=True)
    # Formato: DEL-{YYMMDD}-{HHMM}-{NNN}  ej: DEL-260506-1530-001

    # Consentimiento GDPR / LOPDP
    gdpr_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Copia del correo enviado - evidencia de cumplimiento normativo
    consent_email_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Trazabilidad (resiliente en el tiempo)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class EmailConfig(Base):
    """
    Configuración SMTP para envío de correos (consentimiento GDPR, notificaciones).
    Soporta Gmail (smtp.gmail.com:587) y Outlook/Office365 (smtp.office365.com:587).
    """
    __tablename__ = "email_config"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Configuración SMTP
    smtp_host: Mapped[Optional[str]] = mapped_column(String(100), default="smtp.gmail.com")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    smtp_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # app-password
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(100), default="CoffeeApp")
    from_email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Configuración de correo GDPR
    gdpr_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    gdpr_email_subject: Mapped[Optional[str]] = mapped_column(
        String(200),
        default="Autorización para el tratamiento de sus datos personales"
    )
    gdpr_email_body_html: Mapped[Optional[str]] = mapped_column(
        Text,
        default=None  # Se inicializa con plantilla por defecto en el seeder
    )

    # Metadatos
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
