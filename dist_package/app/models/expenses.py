from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base

class ExpenseCategory(Base):
    """
    Categorías de gastos (Servicios, Arriendo, Suministros, etc).
    """
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))

class Expense(Base):
    """
    Registro de gastos operativos.
    """
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_categories.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    provider_name: Mapped[Optional[str]] = mapped_column(String(150))
    provider_ruc: Mapped[Optional[str]] = mapped_column(String(13))
    
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    
    invoice_reference: Mapped[Optional[str]] = mapped_column(String(50)) # Nro de factura del proveedor
    evidence_url: Mapped[Optional[str]] = mapped_column(String(255)) # Link a foto del comprobante
    
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    date_on_invoice: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
