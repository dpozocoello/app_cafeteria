"""
generar_imagenes.py
===================
Genera imágenes SVG para cada producto del menú JECA y las organiza
en un directorio estructurado por categoría. También produce el
catálogo JSON (image registry) y actualiza la DB.

Estructura de salida:
  app/static/images/
    catalog.json
    menu/
      sanduches/        FIN-SAN-001.svg … FIN-SAN-006.svg
      piqueos/          FIN-PIQ-001.svg … FIN-PIQ-007.svg
      jugos/            FIN-JUG-001.svg … FIN-JUG-004.svg
      bebidas_calientes/ FIN-BEB-001.svg … FIN-BEB-004.svg
"""

import os, sys, json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Importaciones SQLAlchemy (todas necesarias para resolver FK) ───────────────
from app.database import SessionLocal
from app.models.core import Base, Branch, Role, User, SecurityPolicy, Company, EmissionPoint  # noqa
from app.models.sales import Sale, SaleDetail, SalePayment, TaxParameter, PaymentMethod       # noqa
from app.models.inventory import Product, Recipe, Batch, InventoryMovement, MovementType
from app.models.expenses import Expense, ExpenseCategory                                       # noqa
from app.models.operations import Menu, MenuItem, Table, ServiceConfig                         # noqa

# ── Rutas base ─────────────────────────────────────────────────────────────────
STATIC_DIR  = os.path.join(os.path.dirname(__file__), "..", "app", "static")
IMAGES_BASE = os.path.join(STATIC_DIR, "images")
MENU_DIR    = os.path.join(IMAGES_BASE, "menu")

# ── Paleta visual por categoría ────────────────────────────────────────────────
CATEGORY_THEME = {
    "sanduches": {
        "slug":       "sanduches",
        "label":      "Sánduches",
        "grad_a":     "#f59e0b",   # ámbar
        "grad_b":     "#dc2626",   # rojo
        "plate_fill": "rgba(251,191,36,0.12)",
        "plate_stroke":"rgba(251,191,36,0.30)",
        "badge_fill": "#f59e0b",
        "badge_text": "#0f172a",
    },
    "piqueos": {
        "slug":       "piqueos",
        "label":      "Piqueos",
        "grad_a":     "#10b981",   # esmeralda
        "grad_b":     "#0e7490",   # cian oscuro
        "plate_fill": "rgba(16,185,129,0.12)",
        "plate_stroke":"rgba(16,185,129,0.30)",
        "badge_fill": "#10b981",
        "badge_text": "#0f172a",
    },
    "jugos": {
        "slug":       "jugos",
        "label":      "Jugos y Bebidas Naturales",
        "grad_a":     "#06b6d4",   # cian
        "grad_b":     "#7c3aed",   # violeta
        "plate_fill": "rgba(6,182,212,0.12)",
        "plate_stroke":"rgba(6,182,212,0.30)",
        "badge_fill": "#06b6d4",
        "badge_text": "#0f172a",
    },
    "bebidas_calientes": {
        "slug":       "bebidas_calientes",
        "label":      "Bebidas Calientes",
        "grad_a":     "#8b5cf6",   # violeta
        "grad_b":     "#ec4899",   # rosa
        "plate_fill": "rgba(139,92,246,0.12)",
        "plate_stroke":"rgba(139,92,246,0.30)",
        "badge_fill": "#8b5cf6",
        "badge_text": "#f8fafc",
    },
}

# ── Catálogo de productos con metadatos de imagen ─────────────────────────────
PRODUCTS_META = [
    # ── SÁNDUCHES ──────────────────────────────────────────────────────────────
    {
        "sku":      "FIN-SAN-001",
        "name":     "Sanduche de Pollo Mayonesa",
        "short":    "Pollo\nMayonesa",
        "category": "sanduches",
        "price":    "$ 2.75",
        "emoji":    "\U0001f969",   # 🥩 pollo
        "emoji2":   "\U0001f96a",   # 🥪 sánduche (decorativo)
        "tag":      "CLASICO",
    },
    {
        "sku":      "FIN-SAN-002",
        "name":     "Sanduche de Res Desmenuzado",
        "short":    "Res\nDesmenuzado",
        "category": "sanduches",
        "price":    "$ 3.00",
        "emoji":    "\U0001f969",
        "emoji2":   "\U0001f32e",
        "tag":      "SABOR",
    },
    {
        "sku":      "FIN-SAN-003",
        "name":     "Sanduche de Cerdo",
        "short":    "Cerdo\nAsado",
        "category": "sanduches",
        "price":    "$ 3.25",
        "emoji":    "\U0001f416",   # 🐖
        "emoji2":   "\U0001f96a",
        "tag":      "SUCULENTO",
    },
    {
        "sku":      "FIN-SAN-004",
        "name":     "Sanduche de Chorizo Ahumado",
        "short":    "Chorizo\nAhumado",
        "category": "sanduches",
        "price":    "$ 3.75",
        "emoji":    "\U0001f32d",   # 🌭
        "emoji2":   "\U0001f525",
        "tag":      "AHUMADO",
    },
    {
        "sku":      "FIN-SAN-005",
        "name":     "Sanduche Cordon Blue",
        "short":    "Cordon\nBlue",
        "category": "sanduches",
        "price":    "$ 3.50",
        "emoji":    "\U0001f357",   # 🍗
        "emoji2":   "\U0001f9c0",
        "tag":      "GOURMET",
    },
    {
        "sku":      "FIN-SAN-006",
        "name":     "Sanduche de Albondigas",
        "short":    "Albondigas\nde Res",
        "category": "sanduches",
        "price":    "$ 3.50",
        "emoji":    "\U0001f9c6",   # 🧆 (falafel/albóndiga)
        "emoji2":   "\U0001f345",
        "tag":      "ESTRELLA",
    },
    # ── PIQUEOS ────────────────────────────────────────────────────────────────
    {
        "sku":      "FIN-PIQ-001",
        "name":     "Mouse de Camaron",
        "short":    "Mouse de\nCamaron",
        "category": "piqueos",
        "price":    "$ 2.00",
        "emoji":    "\U0001f990",   # 🦐
        "emoji2":   "\U0001f35e",
        "tag":      "ESPECIAL",
    },
    {
        "sku":      "FIN-PIQ-002",
        "name":     "Mote con Chicharron",
        "short":    "Mote con\nChicharron",
        "category": "piqueos",
        "price":    "$ 2.00",
        "emoji":    "\U0001f33d",   # 🌽
        "emoji2":   "\U0001f356",
        "tag":      "TRADICIONAL",
    },
    {
        "sku":      "FIN-PIQ-003",
        "name":     "Pan de Yuca (3u)",
        "short":    "Pan de\nYuca x3",
        "category": "piqueos",
        "price":    "$ 1.25",
        "emoji":    "\U0001f9c0",   # 🧀
        "emoji2":   "\U0001f35e",
        "tag":      "ARTESANAL",
    },
    {
        "sku":      "FIN-PIQ-004",
        "name":     "Pan de Yuca Tocino (3u)",
        "short":    "Pan Yuca\nTocino x3",
        "category": "piqueos",
        "price":    "$ 1.35",
        "emoji":    "\U0001f953",   # 🥓
        "emoji2":   "\U0001f35e",
        "tag":      "PREMIUM",
    },
    {
        "sku":      "FIN-PIQ-005",
        "name":     "Tortilla Maiz Queso (3u)",
        "short":    "Tortilla\nQueso x3",
        "category": "piqueos",
        "price":    "$ 1.50",
        "emoji":    "\U0001f33d",   # 🌽
        "emoji2":   "\U0001f9c0",
        "tag":      "CRUJIENTE",
    },
    {
        "sku":      "FIN-PIQ-006",
        "name":     "Tortilla Maiz Chicharron (3u)",
        "short":    "Tortilla\nChicharron x3",
        "category": "piqueos",
        "price":    "$ 1.50",
        "emoji":    "\U0001f33d",
        "emoji2":   "\U0001f356",
        "tag":      "CRUJIENTE",
    },
    {
        "sku":      "FIN-PIQ-007",
        "name":     "Torta de Choclo",
        "short":    "Torta de\nChoclo",
        "category": "piqueos",
        "price":    "$ 1.50",
        "emoji":    "\U0001f382",   # 🎂
        "emoji2":   "\U0001f33d",
        "tag":      "CASERO",
    },
    # ── JUGOS ─────────────────────────────────────────────────────────────────
    {
        "sku":      "FIN-JUG-001",
        "name":     "Jugo de Naranja",
        "short":    "Jugo de\nNaranja",
        "category": "jugos",
        "price":    "$ 1.00",
        "emoji":    "\U0001f34a",   # 🍊
        "emoji2":   "\U0001f9c3",
        "tag":      "NATURAL",
    },
    {
        "sku":      "FIN-JUG-002",
        "name":     "Jugo Naranja-Zanahoria",
        "short":    "Naranja\nZanahoria",
        "category": "jugos",
        "price":    "$ 1.00",
        "emoji":    "\U0001f955",   # 🥕
        "emoji2":   "\U0001f34a",
        "tag":      "NUTRITIVO",
    },
    {
        "sku":      "FIN-JUG-003",
        "name":     "Jugo Jamaica-Canela",
        "short":    "Jamaica\nCanela",
        "category": "jugos",
        "price":    "$ 0.75",
        "emoji":    "\U0001f338",   # 🌸
        "emoji2":   "\U0001f9ca",
        "tag":      "REFRESCANTE",
    },
    {
        "sku":      "FIN-JUG-004",
        "name":     "Fruta de Temporada",
        "short":    "Fruta de\nTemporada",
        "category": "jugos",
        "price":    "$ 1.00",
        "emoji":    "\U0001f353",   # 🍓
        "emoji2":   "\U0001f34d",
        "tag":      "FRESCO",
    },
    # ── BEBIDAS CALIENTES ─────────────────────────────────────────────────────
    {
        "sku":      "FIN-BEB-001",
        "name":     "Cafe",
        "short":    "Cafe\nNegro",
        "category": "bebidas_calientes",
        "price":    "$ 0.50",
        "emoji":    "☕",        # ☕
        "emoji2":   "\U0001f375",
        "tag":      "CLASICO",
    },
    {
        "sku":      "FIN-BEB-002",
        "name":     "Cappuccino",
        "short":    "Cappuc-\ncino",
        "category": "bebidas_calientes",
        "price":    "$ 2.00",
        "emoji":    "☕",
        "emoji2":   "\U0001f95b",
        "tag":      "ESPECIAL",
    },
    {
        "sku":      "FIN-BEB-003",
        "name":     "Chocolate Caliente",
        "short":    "Chocolate\nCaliente",
        "category": "bebidas_calientes",
        "price":    "$ 2.00",
        "emoji":    "\U0001f36b",   # 🍫
        "emoji2":   "\U0001f95b",
        "tag":      "INDULGENTE",
    },
    {
        "sku":      "FIN-BEB-004",
        "name":     "Agua Aromatica",
        "short":    "Agua\nAromatica",
        "category": "bebidas_calientes",
        "price":    "$ 1.00",
        "emoji":    "\U0001f375",   # 🍵
        "emoji2":   "\U0001f33f",
        "tag":      "NATURAL",
    },
]


def _tspan_lines(text: str, x: int, y_start: int, dy: int = 22,
                 css_class: str = "prod-name") -> str:
    """Convierte texto con \n en tspan SVG multi-línea centrado."""
    lines = text.split("\n")
    # centrar verticalmente: desplazar y_start hacia arriba la mitad
    offset = -((len(lines) - 1) * dy) // 2
    parts = []
    for i, line in enumerate(lines):
        y = y_start + offset + i * dy
        parts.append(f'<tspan x="{x}" y="{y}" class="{css_class}">{line}</tspan>')
    return "\n    ".join(parts)


def render_svg(meta: dict) -> str:
    """Genera el SVG completo para un producto."""
    t   = CATEGORY_THEME[meta["category"]]
    W, H = 400, 300

    # IDs únicos por SKU para evitar colisiones en catálogos inline
    uid = meta["sku"].replace("-", "_")

    name_tspans = _tspan_lines(meta["short"], W // 2, 148, dy=24, css_class="pname")
    tag_text    = meta["tag"]
    price_w     = max(70, len(meta["price"]) * 11)
    price_x     = (W - price_w) // 2

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img"
     aria-label="{meta['name']}">
  <defs>
    <!-- Fondo oscuro -->
    <linearGradient id="bg_{uid}" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#1e293b"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
    <!-- Acento de categoría -->
    <linearGradient id="acc_{uid}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="{t['grad_a']}"/>
      <stop offset="100%" stop-color="{t['grad_b']}"/>
    </linearGradient>
    <!-- Sombra suave del plato -->
    <filter id="shadow_{uid}" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="#000" flood-opacity="0.4"/>
    </filter>
    <!-- Brillo interior del plato -->
    <radialGradient id="plate_{uid}" cx="40%" cy="35%" r="60%">
      <stop offset="0%"   stop-color="rgba(255,255,255,0.18)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0.04)"/>
    </radialGradient>
    <clipPath id="clip_{uid}">
      <rect width="{W}" height="{H}" rx="14"/>
    </clipPath>
    <style>
      .pname  {{ font-family: Outfit, ui-sans-serif, sans-serif; font-size: 17px;
                 font-weight: 700; fill: #f1f5f9; letter-spacing: 0.3px; }}
      .brand  {{ font-family: Outfit, ui-sans-serif, sans-serif; font-size: 10px;
                 fill: #64748b; letter-spacing: 1.5px; }}
      .tag    {{ font-family: Outfit, ui-sans-serif, sans-serif; font-size: 9px;
                 font-weight: 700; fill: {t['badge_text']}; letter-spacing: 2px; }}
      .price  {{ font-family: Outfit, ui-sans-serif, sans-serif; font-size: 15px;
                 font-weight: 800; fill: {t['badge_text']}; }}
      .emoji  {{ font-family: "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",serif; }}
    </style>
  </defs>

  <!-- ░░ Fondo base ░░ -->
  <g clip-path="url(#clip_{uid})">
    <rect width="{W}" height="{H}" fill="url(#bg_{uid})"/>

    <!-- Barra de acento superior (8px) -->
    <rect x="0" y="0" width="{W}" height="8" fill="url(#acc_{uid})"/>

    <!-- Puntos decorativos de fondo -->
    <circle cx="360" cy="60"  r="80" fill="{t['grad_a']}" opacity="0.05"/>
    <circle cx="40"  cy="240" r="60" fill="{t['grad_b']}" opacity="0.05"/>

    <!-- Tag de categoría (chip superior izquierdo) -->
    <rect x="16" y="20" width="72" height="20" rx="10" fill="url(#acc_{uid})" opacity="0.9"/>
    <text x="52" y="34" text-anchor="middle" class="tag">{tag_text}</text>

    <!-- ░░ Plato circular (zona visual central) ░░ -->
    <circle cx="{W//2}" cy="118" r="78"
            fill="{t['plate_fill']}" stroke="{t['plate_stroke']}"
            stroke-width="1.5" filter="url(#shadow_{uid})"/>
    <circle cx="{W//2}" cy="118" r="78" fill="url(#plate_{uid})"/>

    <!-- Emoji principal (grande, centrado en el plato) -->
    <text x="{W//2}" y="138" text-anchor="middle" dominant-baseline="middle"
          class="emoji" font-size="60">{meta['emoji']}</text>

    <!-- ░░ Nombre del producto ░░ -->
    <text text-anchor="middle" class="pname">
    {name_tspans}
    </text>

    <!-- ░░ Precio en badge ░░ -->
    <rect x="{price_x}" y="210" width="{price_w}" height="28" rx="14"
          fill="url(#acc_{uid})"/>
    <text x="{W//2}" y="229" text-anchor="middle" class="price">{meta['price']}</text>

    <!-- ░░ Branding JECA ░░ -->
    <text x="{W//2}" y="288" text-anchor="middle" class="brand">
      JECA · PIQUEOS &amp; CAFETERIA
    </text>

    <!-- Línea separadora inferior -->
    <rect x="40" y="268" width="{W-80}" height="1" fill="url(#acc_{uid})" opacity="0.3"/>
  </g>
</svg>"""
    return svg


def build_catalog_entry(meta: dict, rel_path: str, abs_path: str, size: int) -> dict:
    t = CATEGORY_THEME[meta["category"]]
    return {
        "sku":          meta["sku"],
        "name":         meta["name"],
        "category":     meta["category"],
        "category_label": t["label"],
        "price":        meta["price"],
        "tag":          meta["tag"],
        "image_url":    rel_path,          # URL servible: /static/images/menu/…
        "image_path":   abs_path,          # Ruta FS relativa al proyecto
        "file_size_bytes": size,
        "format":       "svg+xml",
        "theme": {
            "grad_a":     t["grad_a"],
            "grad_b":     t["grad_b"],
            "badge_fill": t["badge_fill"],
        },
    }


def main():
    print("=" * 60)
    print("GENERADOR DE IMAGENES MENU JECA")
    print("=" * 60)

    # ── 1. Crear directorios ───────────────────────────────────────────────────
    for slug in CATEGORY_THEME:
        os.makedirs(os.path.join(MENU_DIR, slug), exist_ok=True)

    # ── 2. Generar SVGs ────────────────────────────────────────────────────────
    catalog_items = []

    for meta in PRODUCTS_META:
        category_dir = os.path.join(MENU_DIR, meta["category"])
        filename     = f"{meta['sku']}.svg"
        abs_path     = os.path.join(category_dir, filename)
        rel_url      = f"/static/images/menu/{meta['category']}/{filename}"
        rel_fs       = f"app/static/images/menu/{meta['category']}/{filename}"

        svg_content = render_svg(meta)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        size = os.path.getsize(abs_path)
        catalog_items.append(build_catalog_entry(meta, rel_url, rel_fs, size))
        print(f"  [OK] {filename}  ({size:,} bytes)  ->  {meta['category']}/")

    # ── 3. Generar catalog.json ────────────────────────────────────────────────
    categories_summary = {}
    for item in catalog_items:
        cat = item["category"]
        if cat not in categories_summary:
            categories_summary[cat] = {
                "slug":  cat,
                "label": item["category_label"],
                "count": 0,
                "items": [],
            }
        categories_summary[cat]["count"] += 1
        categories_summary[cat]["items"].append(item["sku"])

    catalog = {
        "version":      "1.0",
        "app":          "JECA Piqueos & Cafeteria",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total":        len(catalog_items),
        "base_url":     "/static/images/menu",
        "categories":   categories_summary,
        "products":     catalog_items,
    }

    catalog_path = os.path.join(IMAGES_BASE, "catalog.json")
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\n  [OK] catalog.json  ({os.path.getsize(catalog_path):,} bytes)")

    # ── 4. Actualizar image_url en la base de datos ────────────────────────────
    print("\n[DB] Actualizando image_url en productos...")
    db = SessionLocal()
    try:
        updated = 0
        not_found = []
        for item in catalog_items:
            prod = db.query(Product).filter_by(sku=item["sku"]).first()
            if prod:
                prod.image_url = item["image_url"]
                updated += 1
            else:
                not_found.append(item["sku"])

        # Actualizar también menu_items con la misma URL del producto
        for item in catalog_items:
            prod = db.query(Product).filter_by(sku=item["sku"]).first()
            if not prod:
                continue
            for mi in db.query(MenuItem).filter_by(product_id=prod.id).all():
                mi.image_url = item["image_url"]

        db.commit()
        print(f"  [OK] {updated} productos actualizados en DB")
        if not_found:
            print(f"  [!]  SKUs no encontrados en DB: {not_found}")
    except Exception as e:
        db.rollback()
        print(f"  ERROR DB: {e}")
        raise
    finally:
        db.close()

    # ── 5. Resumen ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESUMEN DE IMAGENES GENERADAS")
    print("=" * 60)
    for slug, info in categories_summary.items():
        print(f"  {info['label']:35s}  {info['count']} imagenes")
    print(f"\n  Total SVGs generados  : {len(catalog_items)}")
    print(f"  Catalogo JSON         : app/static/images/catalog.json")
    print(f"  Directorio base       : app/static/images/menu/")
    print()


if __name__ == "__main__":
    main()
