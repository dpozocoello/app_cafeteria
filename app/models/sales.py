from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base

class TaxParameter(Base):
    """
    Parámetros de impuestos (IVA) con vigencia por fechas.
    """
    __tablename__ = "tax_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(5, 2), default=15.0)    # Alias moderno de percentage
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(default=True)

class Sale(Base):
    """
    Cabecera de Venta / Factura SRI Ecuador.
    """
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    emission_point_id: Mapped[Optional[int]] = mapped_column(ForeignKey("emission_points.id"), nullable=True)
    
    # Datos SRI Ecuador
    access_key: Mapped[Optional[str]] = mapped_column(String(49), unique=True) # Clave de acceso SRI
    invoice_number: Mapped[str] = mapped_column(String(17), nullable=False) # 001-001-000000001
    environment: Mapped[int] = mapped_column(default=1) # 1: Pruebas, 2: Producción
    sri_status: Mapped[str] = mapped_column(String(50), default="PENDIENTE") # RECIBIDO, AUTORIZADO, RECHAZADO
    authorization_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Datos Cliente
    customer_name: Mapped[str] = mapped_column(String(150), default="CONSUMIDOR FINAL")
    customer_id_type: Mapped[str] = mapped_column(String(2), default="07") # 05: Cedula, 04: RUC, 07: Consumidor Final
    customer_id: Mapped[str] = mapped_column(String(20), default="9999999999999")
    consumption_type: Mapped[str] = mapped_column(String(20), default="MESA")  # MESA, LLEVAR, DOMICILIO
    table_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tables.id"), nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(String(255))
    delivery_surcharge: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
 
    # Totales
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)        # Subtotal general
    subtotal_0: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    subtotal_tax: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
 
    # Estado del pedido
    status: Mapped[str] = mapped_column(String(30), default="PENDIENTE")        # PENDIENTE, PREPARANDO, ENTREGADO, FACTURADO
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    payment_method_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payment_methods.id"), nullable=True)
 
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    branch: Mapped["Branch"] = relationship(back_populates="sales")
    company: Mapped[Optional["Company"]] = relationship()
    emission_point: Mapped[Optional["EmissionPoint"]] = relationship(back_populates="sales")
    details: Mapped[List["SaleDetail"]] = relationship(back_populates="sale")
    payments: Mapped[List["SalePayment"]] = relationship(back_populates="sale")

class SaleDetail(Base):
    """
    Detalle de ítems vendidos.
    """
    __tablename__ = "sale_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    tax_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(String(255))

    sale: Mapped["Sale"] = relationship(back_populates="details")

class PaymentMethod(Base):
    """
    Catálogo de métodos de pago (Efectivo, Tarjeta, etc).
    """
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sri_code: Mapped[str] = mapped_column(String(2)) # Código SRI (01: Efectivo, 19: Tarjeta, etc)
    is_active: Mapped[bool] = mapped_column(default=True)

class SalePayment(Base):
    """
    Registro de pagos recibidos por venta.
    """
    __tablename__ = "sale_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    payment_method_id: Mapped[int] = mapped_column(ForeignKey("payment_methods.id"))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100)) # Voucher, Transfer ID

    sale: Mapped["Sale"] = relationship(back_populates="payments")
