"""
Módulo Contable — Plan de Cuentas NIIF, Asientos Contables, Períodos Fiscales y Centros de Costo.
Sigue las Normas Internacionales de Información Financiera (NIIF para PYMES)
y el Plan de Cuentas estándar de la Superintendencia de Compañías del Ecuador.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Integer, String, DateTime, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core import Base


class AccountPlan(Base):
    """
    Plan de Cuentas jerárquico (NIIF para PYMES / Supercias Ecuador).
    Estructura: Grupo → Subgrupo → Cuenta → Subcuenta (niveles 1-4).
    Solo las cuentas de nivel 4 (hojas) aceptan asientos directos.
    """
    __tablename__ = "account_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # ej: 1.1.01.001
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # ACTIVO | PASIVO | PATRIMONIO | INGRESO | GASTO
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # DEUDORA (Activos y Gastos: aumentan con Débito)
    # ACREEDORA (Pasivos, Patrimonio, Ingresos: aumentan con Crédito)
    nature: Mapped[str] = mapped_column(String(15), nullable=False)

    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("account_plan.id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)  # 1=grupo, 2=subgrupo, 3=cuenta, 4=subcuenta

    allows_entries: Mapped[bool] = mapped_column(Boolean, default=False)  # True solo en hojas (nivel 4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    niif_category: Mapped[Optional[str]] = mapped_column(String(150))  # Categoría NIIF en estados financieros
    description: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parent: Mapped[Optional["AccountPlan"]] = relationship(
        remote_side="AccountPlan.id", foreign_keys=[parent_id], back_populates="children"
    )
    children: Mapped[List["AccountPlan"]] = relationship(
        back_populates="parent", foreign_keys=[parent_id]
    )
    journal_lines: Mapped[List["JournalEntryLine"]] = relationship(back_populates="account")


class FiscalPeriod(Base):
    """
    Período contable mensual o anual.
    NIIF: estados financieros presentados al menos anualmente (NIC 1).
    """
    __tablename__ = "fiscal_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))

    name: Mapped[str] = mapped_column(String(50))          # "Enero 2025", "Ejercicio 2025"
    period_type: Mapped[str] = mapped_column(String(20), default="MENSUAL")  # MENSUAL | ANUAL
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # ABIERTO → CERRADO → BLOQUEADO (bloqueado no permite reversiones)
    status: Mapped[str] = mapped_column(String(20), default="ABIERTO")
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    journal_entries: Mapped[List["JournalEntry"]] = relationship(back_populates="period")


class JournalEntry(Base):
    """
    Asiento Contable — Libro Diario General.
    NIIF / NIC 1: cada transacción económica queda registrada con igual suma de Débitos y Créditos.
    Los asientos automáticos (ventas, gastos, caja) se generan sin intervención manual.
    """
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    period_id: Mapped[Optional[int]] = mapped_column(ForeignKey("fiscal_periods.id"), nullable=True)

    entry_number: Mapped[str] = mapped_column(String(25))  # AST-2025-000001
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    description: Mapped[str] = mapped_column(String(500))
    reference: Mapped[Optional[str]] = mapped_column(String(150))  # N° factura, comprobante, etc.

    # MANUAL | VENTA | GASTO | CAJA_APERTURA | CAJA_CIERRE | BANCO | NC | AJUSTE | CIERRE_PERIODO
    entry_type: Mapped[str] = mapped_column(String(30), default="MANUAL")

    # BORRADOR | APROBADO | ANULADO
    status: Mapped[str] = mapped_column(String(20), default="APROBADO")

    total_debit: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)
    total_credit: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)

    # Trazabilidad al documento origen (Sale, Expense, CashSession, BankTransaction)
    source_type: Mapped[Optional[str]] = mapped_column(String(50))
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    period: Mapped[Optional["FiscalPeriod"]] = relationship(back_populates="journal_entries")
    lines: Mapped[List["JournalEntryLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


class JournalEntryLine(Base):
    """
    Línea de Asiento Contable — cada línea registra un Débito o Crédito en una cuenta del Plan.
    La suma de débitos debe igualar la suma de créditos en el asiento padre.
    """
    __tablename__ = "journal_entry_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("account_plan.id"))

    description: Mapped[Optional[str]] = mapped_column(String(255))
    debit: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)    # Débito
    credit: Mapped[float] = mapped_column(Numeric(15, 2), default=0.0)   # Crédito

    cost_center_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["AccountPlan"] = relationship(back_populates="journal_lines")


class CostCenter(Base):
    """Centro de costos para asignación contable por área o departamento."""
    __tablename__ = "cost_centers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─── Catálogo del Plan de Cuentas Ecuador (para seeding) ──────────────────────

ECUADOR_CHART_OF_ACCOUNTS = [
    # ── NIVEL 1: Grupos ──────────────────────────────────────────────────────
    {"code": "1",    "name": "ACTIVOS",                         "type": "ACTIVO",     "nature": "DEUDORA",   "level": 1, "entries": False, "parent": None},
    {"code": "2",    "name": "PASIVOS",                         "type": "PASIVO",     "nature": "ACREEDORA", "level": 1, "entries": False, "parent": None},
    {"code": "3",    "name": "PATRIMONIO NETO",                 "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 1, "entries": False, "parent": None},
    {"code": "4",    "name": "INGRESOS",                        "type": "INGRESO",    "nature": "ACREEDORA", "level": 1, "entries": False, "parent": None},
    {"code": "5",    "name": "COSTOS Y GASTOS",                 "type": "GASTO",      "nature": "DEUDORA",   "level": 1, "entries": False, "parent": None},
    # ── NIVEL 2: Subgrupos ───────────────────────────────────────────────────
    {"code": "1.1",  "name": "ACTIVOS CORRIENTES",              "type": "ACTIVO",     "nature": "DEUDORA",   "level": 2, "entries": False, "parent": "1"},
    {"code": "1.2",  "name": "ACTIVOS NO CORRIENTES",           "type": "ACTIVO",     "nature": "DEUDORA",   "level": 2, "entries": False, "parent": "1"},
    {"code": "2.1",  "name": "PASIVOS CORRIENTES",              "type": "PASIVO",     "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "2"},
    {"code": "2.2",  "name": "PASIVOS NO CORRIENTES",           "type": "PASIVO",     "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "2"},
    {"code": "3.1",  "name": "CAPITAL SOCIAL",                  "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "3"},
    {"code": "3.2",  "name": "RESERVAS",                        "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "3"},
    {"code": "3.3",  "name": "RESULTADOS DEL EJERCICIO",        "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "3"},
    {"code": "4.1",  "name": "INGRESOS ORDINARIOS",             "type": "INGRESO",    "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "4"},
    {"code": "4.2",  "name": "OTROS INGRESOS",                  "type": "INGRESO",    "nature": "ACREEDORA", "level": 2, "entries": False, "parent": "4"},
    {"code": "5.1",  "name": "COSTO DE VENTAS",                 "type": "GASTO",      "nature": "DEUDORA",   "level": 2, "entries": False, "parent": "5"},
    {"code": "5.2",  "name": "GASTOS OPERACIONALES",            "type": "GASTO",      "nature": "DEUDORA",   "level": 2, "entries": False, "parent": "5"},
    {"code": "5.3",  "name": "GASTOS FINANCIEROS",              "type": "GASTO",      "nature": "DEUDORA",   "level": 2, "entries": False, "parent": "5"},
    # ── NIVEL 3: Cuentas ─────────────────────────────────────────────────────
    {"code": "1.1.01", "name": "EFECTIVO Y EQUIVALENTES AL EFECTIVO", "type": "ACTIVO", "nature": "DEUDORA", "level": 3, "entries": False, "parent": "1.1", "niif": "Efectivo y equivalentes al efectivo"},
    {"code": "1.1.02", "name": "ACTIVOS FINANCIEROS",                  "type": "ACTIVO", "nature": "DEUDORA", "level": 3, "entries": False, "parent": "1.1", "niif": "Activos financieros"},
    {"code": "1.1.03", "name": "INVENTARIOS",                          "type": "ACTIVO", "nature": "DEUDORA", "level": 3, "entries": False, "parent": "1.1", "niif": "Inventarios"},
    {"code": "1.1.04", "name": "OTROS ACTIVOS CORRIENTES",             "type": "ACTIVO", "nature": "DEUDORA", "level": 3, "entries": False, "parent": "1.1"},
    {"code": "1.2.01", "name": "PROPIEDAD PLANTA Y EQUIPO",            "type": "ACTIVO", "nature": "DEUDORA", "level": 3, "entries": False, "parent": "1.2", "niif": "Propiedades, planta y equipo"},
    {"code": "2.1.01", "name": "CUENTAS Y DOCUMENTOS POR PAGAR",       "type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.1"},
    {"code": "2.1.02", "name": "OBLIGACIONES INSTITUCIONES FINANCIERAS","type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.1"},
    {"code": "2.1.03", "name": "OBLIGACIONES FISCALES",                 "type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.1"},
    {"code": "2.1.04", "name": "OBLIGACIONES CON EMPLEADOS",            "type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.1"},
    {"code": "2.1.05", "name": "OTRAS OBLIGACIONES CORRIENTES",         "type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.1"},
    {"code": "2.2.01", "name": "OBLIGACIONES FINANCIERAS LP",           "type": "PASIVO", "nature": "ACREEDORA", "level": 3, "entries": False, "parent": "2.2"},
    # ── NIVEL 4: Subcuentas (aceptan asientos) ───────────────────────────────
    # Efectivo
    {"code": "1.1.01.001", "name": "Caja General",                             "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.01"},
    {"code": "1.1.01.002", "name": "Caja Chica",                               "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.01"},
    {"code": "1.1.01.003", "name": "Bancos - Cuentas Corrientes",               "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.01"},
    {"code": "1.1.01.004", "name": "Bancos - Cuentas de Ahorros",               "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.01"},
    {"code": "1.1.01.005", "name": "Tarjetas de Crédito/Débito por Liquidar",   "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.01"},
    # Activos Financieros
    {"code": "1.1.02.001", "name": "Cuentas por Cobrar Clientes",              "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.02"},
    {"code": "1.1.02.002", "name": "(-) Provisión Cuentas Incobrables",        "type": "ACTIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "1.1.02"},
    # Inventarios
    {"code": "1.1.03.001", "name": "Inventario Materias Primas",               "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.03"},
    {"code": "1.1.03.002", "name": "Inventario Productos Terminados",          "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.03"},
    # Otros Activos Corrientes
    {"code": "1.1.04.001", "name": "IVA en Compras (Crédito Tributario)",      "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.04"},
    {"code": "1.1.04.002", "name": "Retenciones en la Fuente a Favor",         "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.04"},
    {"code": "1.1.04.003", "name": "Anticipos a Proveedores",                  "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.04"},
    {"code": "1.1.04.004", "name": "Gastos Pagados por Anticipado",            "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.1.04"},
    # Propiedad Planta y Equipo
    {"code": "1.2.01.001", "name": "Muebles y Enseres",                        "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.2.01"},
    {"code": "1.2.01.002", "name": "Equipos de Computación",                   "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.2.01"},
    {"code": "1.2.01.003", "name": "Maquinaria y Equipo de Cocina",            "type": "ACTIVO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "1.2.01"},
    {"code": "1.2.01.004", "name": "(-) Dep. Acum. Muebles y Enseres",        "type": "ACTIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "1.2.01"},
    {"code": "1.2.01.005", "name": "(-) Dep. Acum. Equipos de Computación",   "type": "ACTIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "1.2.01"},
    {"code": "1.2.01.006", "name": "(-) Dep. Acum. Maquinaria y Equipo",      "type": "ACTIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "1.2.01"},
    # Pasivos Corrientes
    {"code": "2.1.01.001", "name": "Proveedores Nacionales",                   "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.01"},
    {"code": "2.1.01.002", "name": "Documentos por Pagar",                     "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.01"},
    {"code": "2.1.02.001", "name": "Préstamos Bancarios Corto Plazo",          "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.02"},
    {"code": "2.1.03.001", "name": "IVA en Ventas (IVA Cobrado)",              "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.03"},
    {"code": "2.1.03.002", "name": "Retenciones en la Fuente por Pagar",       "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.03"},
    {"code": "2.1.03.003", "name": "Impuesto a la Renta por Pagar",            "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.03"},
    {"code": "2.1.04.001", "name": "Sueldos y Salarios por Pagar",             "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.04"},
    {"code": "2.1.04.002", "name": "Aporte Patronal IESS por Pagar (12.15%)", "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.04"},
    {"code": "2.1.04.003", "name": "Aporte Personal IESS por Pagar (9.45%)",  "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.04"},
    {"code": "2.1.04.004", "name": "Beneficios Sociales por Pagar",            "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.04"},
    {"code": "2.1.05.001", "name": "Anticipos de Clientes",                    "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.05"},
    {"code": "2.1.05.002", "name": "Otras Obligaciones Corrientes",            "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.1.05"},
    {"code": "2.2.01.001", "name": "Préstamos Bancarios Largo Plazo",          "type": "PASIVO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "2.2.01"},
    # Patrimonio
    {"code": "3.1.001",    "name": "Capital Social",                            "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "3.1"},
    {"code": "3.2.001",    "name": "Reserva Legal (10% Utilidades)",            "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "3.2"},
    {"code": "3.2.002",    "name": "Reservas Voluntarias",                      "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "3.2"},
    {"code": "3.3.001",    "name": "Resultado del Ejercicio Corriente",         "type": "PATRIMONIO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "3.3"},
    {"code": "3.3.002",    "name": "Utilidades Acumuladas Ejercicios Anteriores","type": "PATRIMONIO","nature": "ACREEDORA", "level": 4, "entries": True, "parent": "3.3"},
    {"code": "3.3.003",    "name": "(-) Pérdidas Acumuladas",                   "type": "PATRIMONIO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "3.3"},
    # Ingresos
    {"code": "4.1.001",    "name": "Ventas de Bienes — Tarifa IVA 15%",         "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.1"},
    {"code": "4.1.002",    "name": "Ventas de Bienes — Tarifa 0%",              "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.1"},
    {"code": "4.1.003",    "name": "Ventas de Servicios",                       "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.1"},
    {"code": "4.1.004",    "name": "(-) Descuentos en Ventas",                  "type": "INGRESO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "4.1"},
    {"code": "4.1.005",    "name": "(-) Devoluciones en Ventas / Notas de Crédito","type": "INGRESO","nature":"DEUDORA",  "level": 4, "entries": True, "parent": "4.1"},
    {"code": "4.2.001",    "name": "Intereses Ganados",                         "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.2"},
    {"code": "4.2.002",    "name": "Sobrante de Caja",                          "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.2"},
    {"code": "4.2.003",    "name": "Otros Ingresos No Operacionales",           "type": "INGRESO", "nature": "ACREEDORA", "level": 4, "entries": True, "parent": "4.2"},
    # Costos
    {"code": "5.1.001",    "name": "Costo de Ventas — Materias Primas Utilizadas","type": "GASTO","nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.1"},
    {"code": "5.1.002",    "name": "Costo de Ventas — Productos para Reventa",  "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.1"},
    # Gastos Operacionales
    {"code": "5.2.001",    "name": "Sueldos y Salarios",                        "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.002",    "name": "Horas Extras y Recargos",                   "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.003",    "name": "Aporte Patronal IESS (12.15%)",             "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.004",    "name": "Fondos de Reserva IESS (8.33%)",            "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.005",    "name": "Décimo Tercer Sueldo",                      "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.006",    "name": "Décimo Cuarto Sueldo",                      "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.007",    "name": "Vacaciones",                                "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.008",    "name": "Arriendos",                                 "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.009",    "name": "Servicios Básicos (Agua, Luz, Internet, Teléfono)","type": "GASTO","nature": "DEUDORA","level": 4,"entries": True,"parent": "5.2"},
    {"code": "5.2.010",    "name": "Suministros y Materiales",                  "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.011",    "name": "Mantenimiento y Reparaciones",              "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.012",    "name": "Depreciaciones",                            "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.013",    "name": "Publicidad y Mercadeo",                     "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.014",    "name": "Transporte y Movilización",                 "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.015",    "name": "Impuestos, Tasas y Contribuciones",         "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.016",    "name": "Seguros",                                   "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.017",    "name": "Faltante de Caja",                          "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.018",    "name": "Gastos de Gestión y Atenciones",            "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    {"code": "5.2.019",    "name": "Otros Gastos Operacionales",                "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.2"},
    # Gastos Financieros
    {"code": "5.3.001",    "name": "Intereses Bancarios Pagados",               "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.3"},
    {"code": "5.3.002",    "name": "Comisiones y Servicios Bancarios",          "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.3"},
    {"code": "5.3.003",    "name": "Otros Gastos Financieros",                  "type": "GASTO", "nature": "DEUDORA",   "level": 4, "entries": True, "parent": "5.3"},
]
