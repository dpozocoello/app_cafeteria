"""
Módulo de Caja — Gestión de sesiones POS, apertura/cierre, movimientos y conteo físico.
Auditado bajo NIIF: cada sesión es trazable con diferencias registradas contablemente.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base


class CashRegister(Base):
    """Caja física / terminal POS asociado a un punto de emisión."""
    __tablename__ = "cash_registers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)      # "Caja Principal", "Caja 2"
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    emission_point_id: Mapped[Optional[int]] = mapped_column(ForeignKey("emission_points.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[List["CashSession"]] = relationship(back_populates="register")


class CashSession(Base):
    """
    Sesión de caja (turno de trabajo).
    Registra apertura, movimientos y cierre con comparación física vs. sistema.
    Cada sesión genera asientos contables automáticos al cerrar.
    """
    __tablename__ = "cash_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    register_id: Mapped[int] = mapped_column(ForeignKey("cash_registers.id"))
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))

    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="ABIERTA")  # ABIERTA | CERRADA | ANULADA

    # ── Montos declarados y calculados ───────────────────────────────────────
    opening_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)  # Fondo inicial declarado
    expected_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0) # Calculado por sistema al cierre
    declared_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0) # Contado físicamente
    difference: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)      # declared - expected

    # ── Totales del turno (calculados al cerrar) ──────────────────────────────
    total_sales: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    total_sales_cash: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)  # Ventas en efectivo
    total_sales_card: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)  # Ventas con tarjeta/transferencia
    total_expenses: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)    # Gastos pagados en efectivo
    total_cash_in: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)     # Ingresos manuales
    total_cash_out: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)    # Retiros manuales

    # Referencia al asiento contable de cierre (generado automáticamente)
    closing_journal_entry_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text)

    register: Mapped["CashRegister"] = relationship(back_populates="sessions")
    transactions: Mapped[List["CashTransaction"]] = relationship(back_populates="session")
    count_denominations: Mapped[List["CashCount"]] = relationship(back_populates="session")


class CashTransaction(Base):
    """
    Movimiento manual de efectivo dentro de una sesión.
    Las ventas e ítems se registran vía Sale; esto cubre fondos de cambio, retiros y ajustes.
    """
    __tablename__ = "cash_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # INGRESO | EGRESO | RETIRO | FONDO_CAMBIO | AJUSTE_SOBRANTE | AJUSTE_FALTANTE
    transaction_type: Mapped[str] = mapped_column(String(30))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)   # Siempre positivo; el tipo define signo
    description: Mapped[str] = mapped_column(String(255))

    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Sale | Expense

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CashSession"] = relationship(back_populates="transactions")


class CashCount(Base):
    """
    Conteo físico de billetes y monedas en el cierre de caja.
    Permite auditoría de denominaciones USD (Ecuador).
    """
    __tablename__ = "cash_counts"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("cash_sessions.id"))

    denomination: Mapped[float] = mapped_column(Numeric(10, 2))  # 0.01, 0.05, 0.10, 0.25, 0.50, 1, 5, 10, 20, 50, 100
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)  # denomination * quantity

    session: Mapped["CashSession"] = relationship(back_populates="count_denominations")
