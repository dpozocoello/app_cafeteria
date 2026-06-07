"""
seed_cafeteria_completo.py
=========================================================
Script de reset + carga completa de datos para Cafetería JECA.
Fuente: docs/recetas_cafeteria.md / PROYECTO CAFETERIA.xlsx (hoja FLUJO)

Fases:
  1. Reset: borra productos, recetas, menús, ítems de menú y movimientos de inventario
  2. Insumos: crea los 35 ingredientes con costos reales
  3. Productos finales: 20 ítems del menú JECA
  4. Recetas (BOM): ingredientes × cantidad por cada producto final
  5. Menús: 4 categorías con sus productos asignados
  6. Simulación mensual: stock inicial + 26 días laborables (Mayo 2026) + reposición día 15
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
# Todos los modelos deben importarse para que SQLAlchemy resuelva referencias forward (noqa intencional)
from app.models.core import Base, Branch, Role, User, SecurityPolicy, Company, EmissionPoint  # noqa: F401
from app.models.sales import Sale, SaleDetail, SalePayment, TaxParameter, PaymentMethod      # noqa: F401
from app.models.inventory import Product, Recipe, Batch, InventoryMovement, MovementType
from app.models.expenses import Expense, ExpenseCategory                                      # noqa: F401
from app.models.operations import Menu, MenuItem, Table, ServiceConfig                        # noqa: F401

# ─── Días laborables de Mayo 2026 (Lun-Sab) ───────────────────────────────────
def get_working_days(year: int, month: int) -> list[datetime]:
    days = []
    d = datetime(year, month, 1, 8, 0, 0)
    while d.month == month:
        if d.weekday() < 6:  # 0=Lun .. 5=Sab; 6=Dom excluido
            days.append(d)
        d += timedelta(days=1)
    return days

WORKING_DAYS = get_working_days(2026, 5)  # 26 días laborables en Mayo 2026

# ─── Proyección de ventas diarias (hoja FLUJO) ────────────────────────────────
# SKU_FINAL: unidades vendidas por día
DAILY_SALES = {
    "FIN-SAN-001": 10,  # Pollo Mayonesa
    "FIN-SAN-002": 5,   # Res Desmenuzado
    "FIN-SAN-003": 5,   # Cerdo
    "FIN-SAN-004": 3,   # Chorizo Ahumado
    "FIN-SAN-005": 3,   # Cordon Blue
    "FIN-SAN-006": 3,   # Albóndigas
    "FIN-PIQ-001": 3,   # Mouse Camarón
    "FIN-PIQ-002": 5,   # Mote con Chicharrón
    "FIN-PIQ-003": 10,  # Pan de Yuca 3u
    "FIN-PIQ-004": 10,  # Pan de Yuca Tocino 3u
    "FIN-PIQ-005": 10,  # Tortilla Maíz Queso 3u
    "FIN-PIQ-006": 10,  # Tortilla Maíz Chicharrón 3u
    "FIN-PIQ-007": 5,   # Torta de Choclo
    "FIN-JUG-001": 1,   # Naranja
    "FIN-JUG-002": 1,   # Naranja-Zanahoria
    "FIN-JUG-003": 1,   # Jamaica-Canela
    "FIN-JUG-004": 1,   # Fruta Temporada
    "FIN-BEB-001": 1,   # Café
    "FIN-BEB-002": 1,   # Cappuccino
    "FIN-BEB-003": 1,   # Chocolate Caliente
    "FIN-BEB-004": 1,   # Agua Aromática
}
assert sum(DAILY_SALES.values()) == 90, "Total diario debe ser 90 unidades"

# ─── DEFINICIÓN DE INSUMOS ────────────────────────────────────────────────────
# (sku, name, unit, cost_price, min_stock, description)
INSUMOS = [
    # PANES
    ("INS-PAN-001", "Pan Baguette",           "Unit",  0.3750, 20.0,  "Pan tipo baguette para sánduches"),
    ("INS-PAN-002", "Pan Finas Hierbas",      "Unit",  0.4000, 20.0,  "Pan finas hierbas para sánduches"),
    # PROTEÍNAS AVES
    ("INS-CAR-001", "Pechuga Pollo Deshilachada", "gr", 0.006835, 500.0, "Pechuga cocida y desmenuzada"),
    ("INS-CAR-002", "Pechuga Pollo Filete",   "gr",    0.007051, 300.0, "Filete de pechuga para Cordon Blue"),
    # PROTEÍNAS RES
    ("INS-CAR-003", "Carne Res Suave Aguja",  "gr",    0.013011, 300.0, "Res suave aguja para desmechar"),
    ("INS-CAR-004", "Carne Res Molida 6-7%",  "gr",    0.008860, 300.0, "Carne molida para albóndigas"),
    # PROTEÍNAS CERDO
    ("INS-CAR-005", "Cerdo Lomo",             "gr",    0.012533, 300.0, "Lomo de cerdo"),
    ("INS-CAR-006", "Chorizo Ahumado",        "Unit",  1.5000,   10.0,  "Chorizo ahumado (unidad)"),
    ("INS-CAR-007", "Chancho Chicharrón",     "gr",    0.006779, 1000.0,"Chicharrón de chancho"),
    ("INS-CAR-008", "Grasa Chicharrón",       "gr",    0.004146, 500.0, "Grasa/lonja de chicharrón"),
    # MARISCOS
    ("INS-MAR-001", "Camarón",                "gr",    0.009370, 100.0, "Camarón limpio en gramos"),
    # EMBUTIDOS Y LÁCTEOS
    ("INS-EMB-001", "Tocino",                 "gr",    0.018150, 100.0, "Tocino en gramos"),
    ("INS-LAC-001", "Queso Holandés",         "reb",   0.1500,   20.0,  "Queso holandés (rebanadas)"),
    ("INS-LAC-002", "Jamón Americano",        "reb",   0.062778, 30.0,  "Jamón americano (rebanadas)"),
    ("INS-LAC-003", "Queso Crema",            "gr",    0.007200, 500.0, "Queso crema en gramos"),
    ("INS-LAC-004", "Queso Manaba",           "gr",    0.006763, 500.0, "Queso manabita rallado"),
    ("INS-LAC-005", "Leche Entera",           "ml",    0.001111, 2000.0,"Leche entera en ml"),
    ("INS-LAC-006", "Huevo",                  "Unit",  0.133333, 30.0,  "Huevo entero (unidad)"),
    # VEGETALES Y FRESCOS
    ("INS-VEG-001", "Lechuga Crespa",         "gr",    0.004000, 200.0, "Lechuga crespa en gramos"),
    ("INS-VEG-002", "Tomate Riñón",           "gr",    0.001463, 300.0, "Tomate riñón en gramos"),
    ("INS-VEG-003", "Zanahoria Rallada",      "gr",    0.001471, 500.0, "Zanahoria rallada en gramos"),
    ("INS-VEG-004", "Naranja",                "Unit",  0.100000, 20.0,  "Naranja para jugo"),
    ("INS-VEG-005", "Zanahoria Entera",       "gr",    0.001200, 200.0, "Zanahoria para jugo naranja-zanahoria"),
    ("INS-VEG-006", "Choclo Tierno",          "Unit",  0.307692, 30.0,  "Choclo tierno (unidad equiv.)"),
    ("INS-VEG-007", "Fruta de Temporada",     "Unit",  0.250000, 10.0,  "Frutas varias según temporada"),
    # GRANOS Y HARINAS
    ("INS-GRA-001", "Almidón de Yuca",        "gr",    0.003307, 1000.0,"Almidón de yuca en gramos"),
    ("INS-GRA-002", "Mote Cocido",            "gr",    0.002970, 500.0, "Mote pelado cocido en gramos"),
    ("INS-GRA-003", "Maíz Amarillo Harina",   "gr",    0.001500, 500.0, "Harina de maíz amarillo"),
    # CONDIMENTOS Y VARIOS
    ("INS-CON-001", "Mayonesa Industrial",    "gr",    0.003963, 1000.0,"Mayonesa en balde 3.5kg"),
    ("INS-CON-002", "Aliños Varios",          "uso",   0.050000, 10.0,  "Cilantro, ajo, aliños varios (uso)"),
    ("INS-CON-003", "Condimentos Varios",     "uso",   0.050000, 10.0,  "Paprika, azafrán, sal, pimienta (uso)"),
    ("INS-CON-004", "Margarina",              "gr",    0.007000, 200.0, "Margarina en gramos"),
    ("INS-CON-005", "Azúcar",                "gr",    0.001140, 500.0, "Azúcar en gramos"),
    ("INS-CON-006", "Flores de Jamaica Secas","gr",    0.050000, 100.0, "Jamaica seca para infusión"),
    ("INS-CON-007", "Infusiones Aromáticas",  "uso",   0.050000, 10.0,  "Manzanilla, menta, hierba luisa (uso)"),
    ("INS-CON-008", "Cacao en Polvo",         "gr",    0.020000, 200.0, "Cacao puro en polvo"),
    ("INS-CON-009", "Café Molido",            "gr",    0.015000, 300.0, "Café molido para cappuccino/expresso"),
    ("INS-CON-010", "Gelatina Sin Sabor",     "pkg",   0.355000, 5.0,   "Gelatina sin sabor (paquete)"),
    ("INS-CON-011", "Galletas Club Social",   "pkg",   0.300000, 10.0,  "Paquete galletas Club Social"),
    # EMPAQUES
    ("INS-EMP-001", "Empaque Para Llevar Grande", "Unit", 0.150000, 50.0, "Empaque desechable grande (sánduches)"),
    ("INS-EMP-002", "Empaque Piqueo Pequeño", "Unit",  0.050000, 100.0, "Empaque pequeño para piqueos"),
]

# ─── DEFINICIÓN DE PRODUCTOS FINALES ─────────────────────────────────────────
# (sku, name, unit, sale_price, menu_category, description)
PRODUCTOS_FINALES = [
    # SÁNDUCHES
    ("FIN-SAN-001", "Sánduche de Pollo Mayonesa",     "Unit", 2.75, "Sánduches", "Pollo desmenuzado con mayonesa, lechuga, tomate y zanahoria"),
    ("FIN-SAN-002", "Sánduche de Res Desmenuzado",    "Unit", 3.00, "Sánduches", "Carne de res mechada con aliños, lechuga y tomate"),
    ("FIN-SAN-003", "Sánduche de Cerdo",              "Unit", 3.25, "Sánduches", "Lomo de cerdo asado con lechuga y tomate"),
    ("FIN-SAN-004", "Sánduche de Chorizo Ahumado",    "Unit", 3.75, "Sánduches", "Chorizo ahumado dorado con lechuga y tomate"),
    ("FIN-SAN-005", "Sánduche Cordon Blue",           "Unit", 3.50, "Sánduches", "Pechuga rellena de jamón y queso, empanizada"),
    ("FIN-SAN-006", "Sánduche de Albóndigas",         "Unit", 3.50, "Sánduches", "Albóndigas de res en salsa de tomate con queso"),
    # PIQUEOS
    ("FIN-PIQ-001", "Mouse de Camarón",               "Unit", 2.00, "Piqueos",   "Mousse de camarón con zanahoria y galletas"),
    ("FIN-PIQ-002", "Mote con Chicharrón",            "Unit", 2.00, "Piqueos",   "Mote cocido con chicharrón crujiente"),
    ("FIN-PIQ-003", "Pan de Yuca (3u)",               "Unit", 1.25, "Piqueos",   "3 panes de yuca con queso crema y queso manaba"),
    ("FIN-PIQ-004", "Pan de Yuca con Tocino (3u)",    "Unit", 1.35, "Piqueos",   "3 panes de yuca con queso y trocitos de tocino"),
    ("FIN-PIQ-005", "Tortilla de Maíz con Queso (3u)","Unit", 1.50, "Piqueos",   "3 tortillas de maíz rellenas de queso"),
    ("FIN-PIQ-006", "Tortilla de Maíz con Chicharrón (3u)","Unit",1.50,"Piqueos","3 tortillas de maíz con chicharrón"),
    ("FIN-PIQ-007", "Torta de Choclo",                "Unit", 1.50, "Piqueos",   "Porción de torta de choclo con queso manaba"),
    # JUGOS Y BEBIDAS NATURALES
    ("FIN-JUG-001", "Jugo de Naranja",                "Unit", 1.00, "Jugos y Bebidas Naturales", "Jugo de naranja natural 300ml"),
    ("FIN-JUG-002", "Jugo Naranja-Zanahoria",         "Unit", 1.00, "Jugos y Bebidas Naturales", "Jugo mixto naranja y zanahoria 300ml"),
    ("FIN-JUG-003", "Jugo Jamaica-Canela",            "Unit", 0.75, "Jugos y Bebidas Naturales", "Infusión fría de jamaica con canela 300ml"),
    ("FIN-JUG-004", "Fruta de Temporada",             "Unit", 1.00, "Jugos y Bebidas Naturales", "Copa de fruta o jugo según temporada"),
    # BEBIDAS CALIENTES
    ("FIN-BEB-001", "Café",                           "Unit", 0.50, "Bebidas Calientes", "Café negro 150ml"),
    ("FIN-BEB-002", "Cappuccino",                     "Unit", 2.00, "Bebidas Calientes", "Cappuccino con espuma de leche 200ml"),
    ("FIN-BEB-003", "Chocolate Caliente",             "Unit", 2.00, "Bebidas Calientes", "Chocolate caliente con cacao puro 200ml"),
    ("FIN-BEB-004", "Agua Aromática",                 "Unit", 1.00, "Bebidas Calientes", "Infusión aromática 200ml"),
]

# ─── RECETAS BOM ──────────────────────────────────────────────────────────────
# Formato: "SKU_PRODUCTO_FINAL": [(sku_ingrediente, cantidad), ...]
# Cantidades según hoja 'Sanduches', 'Piqueos' y 'COSTOS' del Excel
RECETAS = {
    # ── SÁNDUCHES ──────────────────────────────────────────────────────────────
    "FIN-SAN-001": [  # Pollo Mayonesa
        ("INS-PAN-001", 1.0),      # 1 pan baguette
        ("INS-CAR-001", 50.0),     # 50g pechuga deshilachada
        ("INS-VEG-001", 5.0),      # 5g lechuga
        ("INS-VEG-002", 10.0),     # 10g tomate riñón
        ("INS-VEG-003", 100.0),    # 100g zanahoria rallada
        ("INS-CON-001", 36.0),     # 36g mayonesa
        ("INS-CON-002", 1.0),      # aliños
        ("INS-CON-003", 1.0),      # condimentos
        ("INS-EMP-001", 1.0),      # empaque
    ],
    "FIN-SAN-002": [  # Res Desmenuzado
        ("INS-PAN-001", 1.0),      # 1 pan baguette
        ("INS-CAR-003", 70.0),     # 70g res suave aguja
        ("INS-VEG-001", 5.0),
        ("INS-VEG-002", 10.0),
        ("INS-CON-001", 36.0),
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-001", 1.0),
    ],
    "FIN-SAN-003": [  # Cerdo
        ("INS-PAN-002", 1.0),      # 1 pan finas hierbas
        ("INS-CAR-005", 75.0),     # 75g cerdo lomo
        ("INS-VEG-001", 5.0),
        ("INS-VEG-002", 10.0),
        ("INS-CON-001", 36.0),
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-001", 1.0),
    ],
    "FIN-SAN-004": [  # Chorizo Ahumado
        ("INS-PAN-002", 1.0),      # 1 pan finas hierbas
        ("INS-CAR-006", 1.0),      # 1 chorizo ahumado
        ("INS-VEG-001", 5.0),
        ("INS-VEG-002", 10.0),
        ("INS-CON-001", 36.0),
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-001", 1.0),
    ],
    "FIN-SAN-005": [  # Cordon Blue
        ("INS-PAN-001", 1.0),      # 1 pan baguette
        ("INS-CAR-002", 150.0),    # 150g pechuga filete
        ("INS-LAC-001", 1.5),      # 1.5 rebanadas queso holandés
        ("INS-LAC-002", 2.0),      # 2 rebanadas jamón americano
        ("INS-VEG-001", 5.0),
        ("INS-VEG-002", 10.0),
        ("INS-CON-001", 36.0),
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-001", 1.0),
    ],
    "FIN-SAN-006": [  # Albóndigas
        ("INS-PAN-002", 1.0),      # 1 pan finas hierbas
        ("INS-CAR-004", 90.0),     # 90g carne molida
        ("INS-LAC-001", 1.5),      # 1.5 rebanadas queso holandés
        ("INS-VEG-001", 5.0),
        ("INS-VEG-002", 10.0),
        ("INS-CON-001", 36.0),
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-001", 1.0),
    ],
    # ── PIQUEOS ────────────────────────────────────────────────────────────────
    "FIN-PIQ-001": [  # Mouse de Camarón
        ("INS-MAR-001", 20.0),     # 20g camarón
        ("INS-VEG-003", 100.0),    # 100g zanahoria rallada
        ("INS-CON-001", 36.0),     # 36g mayonesa
        ("INS-CON-011", 1.0),      # 1 paquete galletas Club Social
        ("INS-CON-010", 0.25),     # 1/4 paquete gelatina sin sabor
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-002": [  # Mote con Chicharrón
        ("INS-GRA-002", 100.0),    # 100g mote cocido
        ("INS-CAR-007", 45.0),     # 45g chancho chicharrón
        ("INS-CAR-008", 75.0),     # 75g grasa chicharrón
        ("INS-CON-002", 1.0),
        ("INS-CON-003", 1.0),
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-003": [  # Pan de Yuca 3u — costos por 3 unidades
        ("INS-GRA-001", 37.5),     # 3 × 12.5g almidón
        ("INS-LAC-006", 0.5),      # 3 × 1/6 huevo = 0.5
        ("INS-LAC-003", 75.0),     # 3 × 25g queso crema
        ("INS-LAC-004", 37.5),     # 3 × 12.5g queso manaba
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-004": [  # Pan de Yuca Tocino 3u
        ("INS-GRA-001", 37.5),
        ("INS-LAC-006", 0.5),
        ("INS-LAC-003", 75.0),
        ("INS-LAC-004", 37.5),
        ("INS-EMB-001", 15.0),     # 3 × 5g tocino
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-005": [  # Tortilla Maíz Queso 3u
        ("INS-GRA-003", 75.0),     # 3 × 25g maíz amarillo
        ("INS-GRA-001", 18.75),    # 3 × 6.25g almidón
        ("INS-LAC-006", 0.5),      # 3 × 1/6 huevo
        ("INS-LAC-003", 75.0),     # 3 × 25g queso crema
        ("INS-LAC-004", 37.5),     # 3 × 12.5g queso manaba
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-006": [  # Tortilla Maíz Chicharrón 3u
        ("INS-GRA-003", 75.0),     # 3 × 25g maíz amarillo
        ("INS-GRA-001", 18.75),    # 3 × 6.25g almidón
        ("INS-LAC-006", 0.5),      # 3 × 1/6 huevo
        ("INS-CAR-007", 270.0),    # 270g chicharrón (por porción de 3u)
        ("INS-EMP-002", 1.0),
    ],
    "FIN-PIQ-007": [  # Torta de Choclo — por porción individual
        ("INS-VEG-006", 5.0),      # 5 choclos equivalentes por porción
        ("INS-CON-004", 20.0),     # 20g margarina
        ("INS-LAC-006", 0.1667),   # 1/6 huevo
        ("INS-LAC-005", 236.6),    # 237ml leche
        ("INS-GRA-003", 8.33),     # 8.3g maíz amarillo
        ("INS-LAC-004", 25.0),     # 25g queso manaba
        ("INS-EMP-002", 1.0),
    ],
    # ── JUGOS Y BEBIDAS NATURALES ──────────────────────────────────────────────
    "FIN-JUG-001": [  # Jugo de Naranja (300ml ≈ 3-4 naranjas)
        ("INS-VEG-004", 3.5),      # 3.5 naranjas
        ("INS-CON-005", 10.0),     # 10g azúcar
        ("INS-EMP-002", 1.0),
    ],
    "FIN-JUG-002": [  # Jugo Naranja-Zanahoria
        ("INS-VEG-004", 2.0),      # 2 naranjas
        ("INS-VEG-005", 80.0),     # 80g zanahoria entera
        ("INS-CON-005", 10.0),
        ("INS-EMP-002", 1.0),
    ],
    "FIN-JUG-003": [  # Jamaica-Canela (300ml → 1/3 de litro preparado)
        ("INS-CON-006", 5.0),      # 5g flores de jamaica
        ("INS-CON-005", 15.0),     # 15g azúcar
        ("INS-EMP-002", 1.0),
    ],
    "FIN-JUG-004": [  # Fruta de Temporada
        ("INS-VEG-007", 1.0),      # 1 unidad fruta temporada
        ("INS-EMP-002", 1.0),
    ],
    # ── BEBIDAS CALIENTES ─────────────────────────────────────────────────────
    "FIN-BEB-001": [  # Café negro 150ml
        ("INS-CON-009", 12.0),     # 12g café molido
        ("INS-CON-005", 5.0),      # 5g azúcar
        ("INS-EMP-002", 1.0),
    ],
    "FIN-BEB-002": [  # Cappuccino 200ml
        ("INS-CON-009", 18.0),     # 18g café molido
        ("INS-LAC-005", 120.0),    # 120ml leche para espumar
        ("INS-CON-005", 10.0),
        ("INS-EMP-002", 1.0),
    ],
    "FIN-BEB-003": [  # Chocolate Caliente 200ml
        ("INS-CON-008", 20.0),     # 20g cacao en polvo
        ("INS-LAC-005", 180.0),    # 180ml leche
        ("INS-CON-005", 15.0),
        ("INS-EMP-002", 1.0),
    ],
    "FIN-BEB-004": [  # Agua Aromática
        ("INS-CON-007", 1.0),      # 1 uso infusión aromática
        ("INS-CON-005", 10.0),
        ("INS-EMP-002", 1.0),
    ],
}

# ─── MENÚS ────────────────────────────────────────────────────────────────────
# (nombre, descripción, [skus de productos en orden])
MENUS_DEF = [
    (
        "Sánduches",
        "Sánduches artesanales con ingredientes frescos",
        ["FIN-SAN-001","FIN-SAN-002","FIN-SAN-003","FIN-SAN-004","FIN-SAN-005","FIN-SAN-006"]
    ),
    (
        "Piqueos",
        "Piqueos y snacks ecuatorianos tradicionales",
        ["FIN-PIQ-001","FIN-PIQ-002","FIN-PIQ-003","FIN-PIQ-004","FIN-PIQ-005","FIN-PIQ-006","FIN-PIQ-007"]
    ),
    (
        "Jugos y Bebidas Naturales",
        "Jugos frescos y bebidas naturales del día",
        ["FIN-JUG-001","FIN-JUG-002","FIN-JUG-003","FIN-JUG-004"]
    ),
    (
        "Bebidas Calientes",
        "Café, cappuccino, chocolate y aguas aromáticas",
        ["FIN-BEB-001","FIN-BEB-002","FIN-BEB-003","FIN-BEB-004"]
    ),
]


# ─── CÁLCULO DE STOCK INICIAL ──────────────────────────────────────────────────
def calcular_consumo_diario(recetas: dict[str, list], ventas: dict[str, int]) -> dict[str, float]:
    """Suma el consumo diario de cada insumo considerando recetas y ventas proyectadas."""
    consumo: dict[str, float] = {}
    for sku_fin, uds in ventas.items():
        for (sku_ins, qty) in recetas.get(sku_fin, []):
            consumo[sku_ins] = consumo.get(sku_ins, 0.0) + qty * uds
    return consumo


def main():
    db = SessionLocal()
    try:
        print("=" * 60)
        print("SEED CAFETERÍA JECA — INICIO")
        print("=" * 60)

        # ──────────────────────────────────────────────────────────────────────
        # FASE 0: Obtener referencias del sistema existente
        # ──────────────────────────────────────────────────────────────────────
        company = db.query(Company).first()
        branch  = db.query(Branch).first()
        admin   = db.query(User).filter_by(username="admin").first()

        if not company or not branch or not admin:
            print("ERROR: Ejecuta primero scripts/init_db.py para crear la empresa y el admin.")
            return

        print(f"  Empresa  : {company.commercial_name}")
        print(f"  Sucursal : {branch.name}")
        print(f"  Admin    : {admin.username}")

        # ──────────────────────────────────────────────────────────────────────
        # FASE 1: RESET — borra datos anteriores de menú/recetas/inventario
        # ──────────────────────────────────────────────────────────────────────
        print("\n[FASE 1] Reset de tablas de menú, recetas e inventario...")

        # Borrar movimientos de inventario (primero para no violar FK)
        deleted_mov = db.query(InventoryMovement).delete()
        print(f"  [OK]InventoryMovement eliminados: {deleted_mov}")

        # Borrar lotes
        deleted_bat = db.query(Batch).delete()
        print(f"  [OK]Batches eliminados: {deleted_bat}")

        # Borrar ítems de menú
        deleted_mi = db.query(MenuItem).delete()
        print(f"  [OK]MenuItems eliminados: {deleted_mi}")

        # Borrar menús
        deleted_m = db.query(Menu).delete()
        print(f"  [OK]Menus eliminados: {deleted_m}")

        # Borrar recetas
        deleted_r = db.query(Recipe).delete()
        print(f"  [OK]Recipes eliminadas: {deleted_r}")

        # Borrar productos (con SKU del seed anterior)
        # Eliminamos todos los que tengan SKU con prefijo INS- o FIN-
        all_products = db.query(Product).all()
        to_delete = [p for p in all_products if p.sku.startswith(("INS-", "FIN-"))]
        for p in to_delete:
            db.delete(p)
        print(f"  [OK]Productos JECA eliminados: {len(to_delete)}")

        # Eliminar también los productos del seed de prueba (INS-001, INS-002, FIN-001)
        for sku in ["INS-001", "INS-002", "FIN-001"]:
            p = db.query(Product).filter_by(sku=sku).first()
            if p:
                db.delete(p)

        db.flush()
        print("  [OK]Reset completado")

        # ──────────────────────────────────────────────────────────────────────
        # FASE 2: INSUMOS
        # ──────────────────────────────────────────────────────────────────────
        print("\n[FASE 2] Creando insumos...")
        insumo_map: dict[str, Product] = {}

        for (sku, name, unit, cost, min_stock, desc) in INSUMOS:
            ins = Product(
                sku=sku,
                name=name,
                unit=unit,
                cost_price=cost,
                sale_price=0.0,
                is_ingredient=True,
                is_ready_to_sell=False,
                min_stock=min_stock,
                description=desc,
                menu_category="Insumos",
                company_id=company.id,
            )
            db.add(ins)
            insumo_map[sku] = ins

        db.flush()
        print(f"  [OK]{len(INSUMOS)} insumos creados")

        # ──────────────────────────────────────────────────────────────────────
        # FASE 3: PRODUCTOS FINALES
        # ──────────────────────────────────────────────────────────────────────
        print("\n[FASE 3] Creando productos finales del menú...")
        producto_map: dict[str, Product] = {}

        for (sku, name, unit, price, cat, desc) in PRODUCTOS_FINALES:
            prod = Product(
                sku=sku,
                name=name,
                unit=unit,
                cost_price=0.0,
                sale_price=price,
                is_ingredient=False,
                is_ready_to_sell=True,
                min_stock=0.0,
                description=desc,
                menu_category=cat,
                company_id=company.id,
            )
            db.add(prod)
            producto_map[sku] = prod

        db.flush()
        print(f"  [OK]{len(PRODUCTOS_FINALES)} productos finales creados")

        # ──────────────────────────────────────────────────────────────────────
        # FASE 4: RECETAS (BOM)
        # ──────────────────────────────────────────────────────────────────────
        print("\n[FASE 4] Creando recetas (BOM)...")
        total_bom_lines = 0

        for sku_fin, ingredientes in RECETAS.items():
            prod = producto_map[sku_fin]
            for (sku_ins, qty) in ingredientes:
                ins = insumo_map[sku_ins]
                db.add(Recipe(
                    product_id=prod.id,
                    ingredient_id=ins.id,
                    quantity=qty,
                ))
                total_bom_lines += 1

        db.flush()
        print(f"  [OK]{total_bom_lines} líneas de receta creadas para {len(RECETAS)} productos")

        # ──────────────────────────────────────────────────────────────────────
        # FASE 5: MENÚS Y MENU_ITEMS
        # ──────────────────────────────────────────────────────────────────────
        print("\n[FASE 5] Creando menús y asignando productos...")

        for (menu_name, menu_desc, skus) in MENUS_DEF:
            menu = Menu(name=menu_name, description=menu_desc, is_active=True)
            db.add(menu)
            db.flush()
            for order, sku in enumerate(skus):
                prod = producto_map[sku]
                db.add(MenuItem(
                    menu_id=menu.id,
                    product_id=prod.id,
                    display_order=order,
                    is_available=True,
                    override_price=None,
                ))
            print(f"  [OK]Menú '{menu_name}': {len(skus)} productos")

        db.flush()

        # ──────────────────────────────────────────────────────────────────────
        # FASE 6: SIMULACIÓN DE INVENTARIO — MAYO 2026
        # ──────────────────────────────────────────────────────────────────────
        print(f"\n[FASE 6] Simulación de inventario ({len(WORKING_DAYS)} días laborables — Mayo 2026)...")

        consumo_diario = calcular_consumo_diario(RECETAS, DAILY_SALES)

        # Stock inicial = consumo diario × días laborables × 1.15 (colchón de seguridad 15%)
        num_dias = len(WORKING_DAYS)
        stock_corriente: dict[str, float] = {}
        for sku_ins, cons_dia in consumo_diario.items():
            stock_corriente[sku_ins] = round(cons_dia * num_dias * 1.15, 4)

        # Asegurar que los insumos sin consumo (ej: rótulos) también tengan stock mínimo
        for sku_ins in insumo_map:
            if sku_ins not in stock_corriente:
                ins = insumo_map[sku_ins]
                stock_corriente[sku_ins] = float(ins.min_stock) * 2

        # ── ENTRADA INICIAL (Día 0 = 2026-04-30 18:00) ────────────────────────
        apertura = datetime(2026, 4, 30, 18, 0, 0)
        mov_apertura = 0
        for sku_ins, cantidad in stock_corriente.items():
            ins = insumo_map[sku_ins]
            db.add(InventoryMovement(
                product_id=ins.id,
                branch_id=branch.id,
                type=MovementType.IN,
                quantity=cantidad,
                unit_cost=float(ins.cost_price),
                balance_after=cantidad,
                reference_type="Apertura",
                reference_id=None,
                user_id=admin.id,
                timestamp=apertura,
                notes="Stock inicial mes Mayo 2026 — lote de apertura",
            ))
            mov_apertura += 1

        db.flush()
        print(f"  [OK]Apertura stock: {mov_apertura} movimientos (2026-04-30)")

        # ── DÍAS LABORABLES: SALIDAS POR VENTAS + REPOSICIÓN DÍA 15 ────────────
        total_salidas = 0
        total_entradas = 0

        for idx, dia in enumerate(WORKING_DAYS):
            # Variación aleatoria determinista: ±10% según día de la semana
            factor = 1.0
            if dia.weekday() == 4:  # Viernes: +10%
                factor = 1.10
            elif dia.weekday() == 5:  # Sábado: +15%
                factor = 1.15
            elif dia.weekday() == 0:  # Lunes: -5%
                factor = 0.95

            hora_cierre = dia.replace(hour=15, minute=0)

            # Salida diaria por consumo de ventas
            for sku_ins, cons_base in consumo_diario.items():
                consumo_dia = round(cons_base * factor, 4)
                stock_corriente[sku_ins] = round(stock_corriente[sku_ins] - consumo_dia, 4)

                ins = insumo_map[sku_ins]
                db.add(InventoryMovement(
                    product_id=ins.id,
                    branch_id=branch.id,
                    type=MovementType.OUT,
                    quantity=-consumo_dia,
                    unit_cost=float(ins.cost_price),
                    balance_after=stock_corriente[sku_ins],
                    reference_type="VentaDiaria",
                    reference_id=idx + 1,
                    user_id=admin.id,
                    timestamp=hora_cierre,
                    notes=f"Consumo ventas {dia.strftime('%Y-%m-%d')} ({int(90*factor)}u vendidas, factor {factor})",
                ))
                total_salidas += 1

            # Reposición a mitad de mes (día 15 de Mayo = índice ≈ 13)
            if dia.day == 15:
                hora_reposicion = dia.replace(hour=9, minute=0)
                # Reabastecer para 15 días adicionales
                for sku_ins, cons_base in consumo_diario.items():
                    reposicion = round(cons_base * 15 * 1.10, 4)
                    stock_corriente[sku_ins] = round(stock_corriente[sku_ins] + reposicion, 4)

                    ins = insumo_map[sku_ins]
                    db.add(InventoryMovement(
                        product_id=ins.id,
                        branch_id=branch.id,
                        type=MovementType.IN,
                        quantity=reposicion,
                        unit_cost=float(ins.cost_price),
                        balance_after=stock_corriente[sku_ins],
                        reference_type="Compra",
                        reference_id=None,
                        user_id=admin.id,
                        timestamp=hora_reposicion,
                        notes="Reposición quincenal — compra a proveedores",
                    ))
                    total_entradas += 1

        # ── AJUSTE DE CIERRE (31 de Mayo 2026) ───────────────────────────────
        cierre = datetime(2026, 5, 31, 17, 0, 0)
        ajuste_total = 0
        for sku_ins, saldo in stock_corriente.items():
            if saldo != 0:
                ins = insumo_map[sku_ins]
                db.add(InventoryMovement(
                    product_id=ins.id,
                    branch_id=branch.id,
                    type=MovementType.ADJUSTMENT,
                    quantity=0.0,
                    unit_cost=float(ins.cost_price),
                    balance_after=round(saldo, 4),
                    reference_type="InventarioFisico",
                    reference_id=None,
                    user_id=admin.id,
                    timestamp=cierre,
                    notes=f"Inventario físico cierre Mayo 2026 — saldo: {saldo:.2f} {ins.unit}",
                ))
                ajuste_total += 1

        db.flush()
        print(f"  [OK]Salidas diarias: {total_salidas} movimientos")
        print(f"  [OK]Entradas reposición: {total_entradas} movimientos")
        print(f"  [OK]Ajuste cierre: {ajuste_total} movimientos")

        # ── BATCH / LOTE FÍSICO POR INSUMO ───────────────────────────────────
        print("\n[FASE 6b] Registrando lotes de inventario...")
        lotes = 0
        for sku_ins, saldo in stock_corriente.items():
            ins = insumo_map[sku_ins]
            db.add(Batch(
                product_id=ins.id,
                batch_number=f"JECA-MAY26-{sku_ins}",
                expiration_date=datetime(2026, 6, 30),
                current_stock=round(max(saldo, 0), 4),
            ))
            lotes += 1

        db.flush()
        print(f"  [OK]{lotes} lotes registrados")

        # ──────────────────────────────────────────────────────────────────────
        # COMMIT FINAL
        # ──────────────────────────────────────────────────────────────────────
        db.commit()

        print("\n" + "=" * 60)
        print("SEED COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print(f"  Insumos creados         : {len(INSUMOS)}")
        print(f"  Productos finales       : {len(PRODUCTOS_FINALES)}")
        print(f"  Líneas de receta (BOM)  : {total_bom_lines}")
        print(f"  Menús creados           : {len(MENUS_DEF)}")
        print(f"  Días laborables simulados: {num_dias} (Mayo 2026)")
        total_movimientos = mov_apertura + total_salidas + total_entradas + ajuste_total
        print(f"  Total movimientos kárdex: {total_movimientos}")
        print(f"  Lotes registrados       : {lotes}")
        print()
        print("  RESUMEN STOCK AL CIERRE (Mayo 2026):")
        for sku_ins in sorted(stock_corriente.keys()):
            ins = insumo_map[sku_ins]
            s = stock_corriente[sku_ins]
            alerta = " [!] BAJO MINIMO" if s < float(ins.min_stock) else ""
            print(f"    {sku_ins:20s} {ins.name:35s}  {s:10.2f} {ins.unit}{alerta}")

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
