from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, Integer, ForeignKey, Numeric, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base


class Menu(Base):
    """
    Agrupación de productos para diferentes momentos del día o tipo de servicio.
    Ej: 'Desayunos', 'Almuerzos Tarde', 'Menú Express'.
    """
    __tablename__ = "menus"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[List["MenuItem"]] = relationship(back_populates="menu", cascade="all, delete-orphan")


class MenuItem(Base):
    """
    Tabla puente Menu <-> Product. Permite precio especial por menú e imagen del plato.
    """
    __tablename__ = "menu_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("menus.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    override_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    image_url: Mapped[Optional[str]] = mapped_column(String(500))       # Imagen del plato
    display_order: Mapped[int] = mapped_column(Integer, default=0)      # Orden en el menú
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)   # Disponible hoy

    menu: Mapped["Menu"] = relationship(back_populates="items")


class Table(Base):
    """
    Mesas del establecimiento. Permite asociar pedidos a una mesa física.
    """
    __tablename__ = "tables"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # "1", "2", "T-VIP"
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[str] = mapped_column(String(20), default="LIBRE")  # LIBRE, OCUPADA, RESERVADA
    zone: Mapped[Optional[str]] = mapped_column(String(50))  # Interior, Terraza, Barra


class ServiceConfig(Base):
    """
    Configuración global de servicios: domicilio, retiro, impuestos especiales.
    """
    __tablename__ = "service_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_type: Mapped[str] = mapped_column(String(30), unique=True)  # DOMICILIO, RETIRO, MESA
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    surcharge_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)  # Ej: 10.0 (10%)
    base_factor: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)       # Ej: 1.50 USD mínimo
    description: Mapped[Optional[str]] = mapped_column(String(255))
