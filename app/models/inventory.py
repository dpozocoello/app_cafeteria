from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Enum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base
import enum

class MovementType(enum.Enum):
    IN = "Entrada"          # Compras, Devoluciones de clientes
    OUT = "Salida"         # Ventas, Devoluciones a proveedores
    ADJUSTMENT = "Ajuste"   # Mermas, Inventario físico

class Product(Base):
    """
    Catálogo de productos (terminados e insumos).
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    unit: Mapped[str] = mapped_column(String(20)) # Kg, L, Unit, gr, ml
    menu_category: Mapped[Optional[str]] = mapped_column(String(50)) # Desayunos, Platos Principales, etc.
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    
    cost_price: Mapped[float] = mapped_column(Numeric(12, 4), default=0.0) # Costo promedio
    sale_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    is_ready_to_sell: Mapped[bool] = mapped_column(Boolean, default=True)
    is_ingredient: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    min_stock: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relaciones
    batches: Mapped[List["Batch"]] = relationship(back_populates="product")
    recipe_ingredients: Mapped[List["Recipe"]] = relationship(
        primaryjoin="Product.id==Recipe.product_id",
        back_populates="product"
    )
    movements: Mapped[List["InventoryMovement"]] = relationship(back_populates="product")

class Recipe(Base):
    """
    Bill of Materials (BOM). Define los insumos de un producto terminado.
    Ej: 1 Capuchino = 18g Café + 200ml Leche.
    """
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id")) # Producto final
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("products.id")) # Insumo
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    
    product: Mapped["Product"] = relationship("Product", foreign_keys=[product_id], back_populates="recipe_ingredients")
    ingredient: Mapped["Product"] = relationship("Product", foreign_keys=[ingredient_id])

class Batch(Base):
    """
    Control de lotes y fechas de caducidad.
    """
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    batch_number: Mapped[str] = mapped_column(String(50))
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_stock: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    product: Mapped["Product"] = relationship(back_populates="batches")

class InventoryMovement(Base):
    """
    Kárdex: Trazabilidad total de movimientos de inventario.
    """
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    
    type: Mapped[MovementType] = mapped_column(Enum(MovementType))
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4))
    
    # Stock después del movimiento para auditoría rápida
    balance_after: Mapped[float] = mapped_column(Numeric(12, 2))
    
    reference_id: Mapped[Optional[int]] = mapped_column(Integer) # ID de Venta, Compra o Ajuste
    reference_type: Mapped[Optional[str]] = mapped_column(String(50)) # 'Sale', 'Purchase'
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    product: Mapped["Product"] = relationship(back_populates="movements")
