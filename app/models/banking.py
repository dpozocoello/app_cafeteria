"""
Módulo Bancario — Cuentas bancarias, movimientos y conciliación bancaria.
NIIF NIC 7: Conciliación entre saldo contable y extracto bancario.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base


class BankAccount(Base):
    """
    Cuenta bancaria de la empresa, vinculada al Plan de Cuentas.
    Cada cuenta bancaria tiene su subcuenta en 1.1.01 (Bancos).
    """
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))

    bank_name: Mapped[str] = mapped_column(String(100))        # "Banco Pichincha", "Produbanco"
    account_number: Mapped[str] = mapped_column(String(50))    # Número de cuenta enmascarado
    account_type: Mapped[str] = mapped_column(String(30))      # CORRIENTE | AHORROS | VIRTUAL

    # Vinculación al Plan de Cuentas (ej: 1.1.01.003 Bancos - Cuentas Corrientes)
    accounting_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("account_plan.id"), nullable=True
    )

    initial_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    current_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)

    currency: Mapped[str] = mapped_column(String(3), default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[List["BankTransaction"]] = relationship(back_populates="account")
    reconciliations: Mapped[List["BankReconciliation"]] = relationship(back_populates="account")


class BankTransaction(Base):
    """
    Movimiento bancario (extracto bancario o registrado manualmente).
    Puede estar vinculado a un asiento contable y a una conciliación.
    """
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"))

    transaction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    value_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Fecha valor del banco

    description: Mapped[str] = mapped_column(String(500))
    reference: Mapped[Optional[str]] = mapped_column(String(100))  # N° de transacción banco

    # DEPOSITO | RETIRO | TRANSFERENCIA_IN | TRANSFERENCIA_OUT | DEBITO_AUTOMATICO |
    # NOTA_CREDITO | NOTA_DEBITO | COMISION | INTERES | AJUSTE
    transaction_type: Mapped[str] = mapped_column(String(30))

    amount: Mapped[float] = mapped_column(Numeric(15, 2))          # + ingreso / - egreso
    balance_after: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    reconciliation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_reconciliations.id"), nullable=True
    )

    # Asiento contable asociado (si se registró automáticamente)
    journal_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )

    source: Mapped[str] = mapped_column(String(20), default="MANUAL")  # MANUAL | IMPORTADO
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["BankAccount"] = relationship(back_populates="transactions")


class BankReconciliation(Base):
    """
    Conciliación Bancaria Mensual (NIC 7 / Control Interno Ecuador).
    Compara el saldo según libros contables con el saldo del extracto bancario.
    El saldo conciliado ajustado debe coincidir en ambos lados.

    Fórmula:
      Saldo Banco + Depósitos en Tránsito - Cheques Pendientes = Saldo Ajustado Banco
      Saldo Libros + Créditos Bancarios - Cargos Bancarios     = Saldo Ajustado Libros
      Diferencia = Saldo Ajustado Banco - Saldo Ajustado Libros (debe ser 0 al conciliar)
    """
    __tablename__ = "bank_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"))

    period_name: Mapped[str] = mapped_column(String(50))          # "Enero 2025"
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Saldos según extracto bancario
    bank_balance_start: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    bank_balance_end: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)

    # Saldos según libros contables
    book_balance_start: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    book_balance_end: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)

    # Partidas de conciliación
    deposits_in_transit: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)  # Depósitos en tránsito
    outstanding_checks: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)   # Cheques no cobrados
    bank_charges_not_in_books: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)  # Cargos banco no registrados
    bank_credits_not_in_books: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)  # Créditos banco no registrados
    errors_in_books: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)      # Errores en libros
    errors_in_bank: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)       # Errores banco

    adjusted_balance: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)    # Saldo conciliado
    difference: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)          # Debe ser 0

    # BORRADOR | FINALIZADA | APROBADA
    status: Mapped[str] = mapped_column(String(20), default="BORRADOR")

    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["BankAccount"] = relationship(back_populates="reconciliations")
    items: Mapped[List["BankReconciliationItem"]] = relationship(back_populates="reconciliation")


class BankReconciliationItem(Base):
    """
    Partida individual de la conciliación bancaria.
    Cada diferencia se clasifica y puede marcarse como resuelta en períodos futuros.
    """
    __tablename__ = "bank_reconciliation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("bank_reconciliations.id"))

    # DEPOSITO_TRANSITO | CHEQUE_PENDIENTE | CARGO_BANCARIO | CREDITO_BANCARIO |
    # ERROR_LIBROS | ERROR_BANCO
    item_type: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Numeric(15, 2))

    transaction_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bank_transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bank_transactions.id"), nullable=True
    )
    is_cleared: Mapped[bool] = mapped_column(Boolean, default=False)  # Saldado en período siguiente

    reconciliation: Mapped["BankReconciliation"] = relationship(back_populates="items")
