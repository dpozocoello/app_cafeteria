"""
Router: Repositorio de Imágenes del Menú
=========================================
Gestión del directorio estructurado de imágenes:
  GET  /api/images/catalog                    → catálogo completo (catalog.json)
  GET  /api/images/catalog/{category}         → imágenes de una categoría
  GET  /api/images/product/{sku}              → metadatos de imagen de un SKU
  POST /api/images/product/{product_id}/upload → subir imagen personalizada (reemplaza SVG)
  POST /api/images/regenerate                 → regenerar todos los SVGs placeholder
  DELETE /api/images/product/{sku}            → eliminar imagen personalizada (restaura SVG)
"""
import os
import json
import shutil
import uuid
import subprocess
import sys
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.inventory import Product
from ..models.operations import MenuItem

router = APIRouter(prefix="/api/images", tags=["Repositorio de Imágenes"])

# ── Rutas del sistema de archivos ─────────────────────────────────────────────
_HERE       = os.path.dirname(__file__)
STATIC_DIR  = os.path.normpath(os.path.join(_HERE, "..", "static"))
IMAGES_DIR  = os.path.join(STATIC_DIR, "images")
MENU_DIR    = os.path.join(IMAGES_DIR, "menu")
CATALOG_PATH = os.path.join(IMAGES_DIR, "catalog.json")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "svg"}

CATEGORY_DIRS = {
    "sanduches":        os.path.join(MENU_DIR, "sanduches"),
    "piqueos":          os.path.join(MENU_DIR, "piqueos"),
    "jugos":            os.path.join(MENU_DIR, "jugos"),
    "bebidas_calientes": os.path.join(MENU_DIR, "bebidas_calientes"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_catalog() -> dict:
    if not os.path.exists(CATALOG_PATH):
        raise HTTPException(
            status_code=503,
            detail="Catálogo no encontrado. Ejecuta scripts/generar_imagenes.py primero."
        )
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _write_catalog(catalog: dict) -> None:
    catalog["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)


def _find_product_in_catalog(catalog: dict, sku: str) -> dict | None:
    return next((p for p in catalog["products"] if p["sku"] == sku), None)


def _update_catalog_product(catalog: dict, sku: str, updates: dict) -> None:
    for i, p in enumerate(catalog["products"]):
        if p["sku"] == sku:
            catalog["products"][i].update(updates)
            return


def _dir_listing(directory: str, base_url: str) -> list[dict]:
    """Lista todos los archivos de imagen en un directorio."""
    items = []
    if not os.path.isdir(directory):
        return items
    for fname in sorted(os.listdir(directory)):
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
        if ext in ALLOWED_EXTENSIONS:
            fpath = os.path.join(directory, fname)
            items.append({
                "filename":  fname,
                "url":       f"{base_url}/{fname}",
                "size_bytes": os.path.getsize(fpath),
                "format":    ext,
                "modified":  datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
            })
    return items


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/catalog")
def get_full_catalog():
    """
    Retorna el catálogo completo de imágenes del menú.
    Incluye metadatos de cada producto: URL, categoría, tamaño, tema de color.
    """
    return _read_catalog()


@router.get("/catalog/{category}")
def get_category_catalog(category: str):
    """
    Retorna las imágenes de una categoría específica junto con el
    listado real de archivos en el directorio.
    """
    if category not in CATEGORY_DIRS:
        raise HTTPException(
            status_code=404,
            detail=f"Categoría '{category}' no existe. "
                   f"Válidas: {list(CATEGORY_DIRS.keys())}"
        )
    catalog = _read_catalog()
    cat_info = catalog["categories"].get(category, {})
    products = [p for p in catalog["products"] if p["category"] == category]
    files    = _dir_listing(
        CATEGORY_DIRS[category],
        f"/static/images/menu/{category}"
    )
    return {
        "category":     category,
        "label":        cat_info.get("label", category),
        "product_count": len(products),
        "products":     products,
        "files_on_disk": files,
    }


@router.get("/product/{sku}")
def get_product_image_meta(sku: str, db: Session = Depends(get_db)):
    """
    Retorna los metadatos de imagen de un producto por SKU,
    incluyendo la URL actual guardada en DB.
    """
    catalog = _read_catalog()
    entry   = _find_product_in_catalog(catalog, sku)
    if not entry:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' no está en el catálogo")

    product = db.query(Product).filter_by(sku=sku).first()
    db_image_url = product.image_url if product else None

    return {
        **entry,
        "db_image_url": db_image_url,
        "in_sync": db_image_url == entry["image_url"],
    }


@router.get("/directory")
def list_full_directory():
    """
    Lista completa del directorio de imágenes (todas las categorías).
    Útil para auditoría y sincronización.
    """
    result = {
        "base_path": "app/static/images/menu/",
        "base_url":  "/static/images/menu/",
        "categories": {},
    }
    total_files = 0
    for slug, path in CATEGORY_DIRS.items():
        files = _dir_listing(path, f"/static/images/menu/{slug}")
        result["categories"][slug] = {
            "path":  f"app/static/images/menu/{slug}/",
            "count": len(files),
            "files": files,
        }
        total_files += len(files)
    result["total_files"] = total_files
    return result


@router.post("/product/{product_id}/upload")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Sube una imagen personalizada para un producto.
    Reemplaza la imagen anterior (SVG generado u otro upload previo).
    La imagen queda en el directorio de su categoría y se actualiza el catálogo + DB.
    """
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not product.sku.startswith("FIN-"):
        raise HTTPException(status_code=400, detail="Solo se pueden subir imágenes para productos finales")

    ct = file.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Extensión no permitida. Usa: {ALLOWED_EXTENSIONS}")

    # Determinar categoría desde el catálogo
    catalog = _read_catalog()
    entry   = _find_product_in_catalog(catalog, product.sku)
    if not entry:
        raise HTTPException(status_code=404, detail="SKU no encontrado en el catálogo de imágenes")

    category    = entry["category"]
    category_dir = CATEGORY_DIRS[category]

    # Eliminar imagen anterior si existe y es diferente del placeholder SVG
    old_url = product.image_url or ""
    if old_url:
        old_fname = old_url.rsplit("/", 1)[-1]
        old_path  = os.path.join(category_dir, old_fname)
        if os.path.exists(old_path) and not old_fname.endswith(".svg"):
            os.remove(old_path)

    # Guardar nueva imagen con nombre único
    new_fname = f"{product.sku}_{uuid.uuid4().hex[:8]}.{ext}"
    new_path  = os.path.join(category_dir, new_fname)
    with open(new_path, "wb") as f_out:
        shutil.copyfileobj(file.file, f_out)

    new_url = f"/static/images/menu/{category}/{new_fname}"

    # Actualizar DB
    product.image_url = new_url
    for mi in db.query(MenuItem).filter_by(product_id=product.id).all():
        mi.image_url = new_url
    db.commit()

    # Actualizar catálogo
    _update_catalog_product(catalog, product.sku, {
        "image_url":    new_url,
        "format":       ext,
        "file_size_bytes": os.path.getsize(new_path),
        "custom_upload": True,
        "uploaded_at":  datetime.utcnow().isoformat() + "Z",
    })
    _write_catalog(catalog)

    return {
        "message":    "Imagen subida correctamente",
        "sku":        product.sku,
        "image_url":  new_url,
        "product_id": product_id,
    }


@router.delete("/product/{sku}", status_code=200)
def restore_svg_placeholder(sku: str, db: Session = Depends(get_db)):
    """
    Elimina la imagen personalizada de un producto y restaura el SVG placeholder.
    No elimina el SVG generado automáticamente, solo imágenes subidas por el usuario.
    """
    catalog = _read_catalog()
    entry   = _find_product_in_catalog(catalog, sku)
    if not entry:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' no en catálogo")

    product = db.query(Product).filter_by(sku=sku).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado en DB")

    current_url = product.image_url or ""
    category    = entry["category"]
    svg_url     = f"/static/images/menu/{category}/{sku}.svg"

    # Eliminar imagen personalizada si es distinta del SVG base
    if current_url and not current_url.endswith(f"{sku}.svg"):
        fname = current_url.rsplit("/", 1)[-1]
        fpath = os.path.join(CATEGORY_DIRS[category], fname)
        if os.path.exists(fpath):
            os.remove(fpath)

    # Restaurar URL al SVG placeholder
    product.image_url = svg_url
    for mi in db.query(MenuItem).filter_by(product_id=product.id).all():
        mi.image_url = svg_url
    db.commit()

    _update_catalog_product(catalog, sku, {
        "image_url":     svg_url,
        "format":        "svg+xml",
        "custom_upload": False,
    })
    _write_catalog(catalog)

    return {"message": "Imagen restaurada al SVG placeholder", "sku": sku, "image_url": svg_url}


@router.post("/regenerate")
def regenerate_all_svgs():
    """
    Regenera todos los SVGs placeholder para los productos sin imagen personalizada.
    No sobreescribe imágenes subidas manualmente (custom_upload=True).
    """
    scripts_dir = os.path.normpath(os.path.join(_HERE, "..", "..", "scripts"))
    script_path = os.path.join(scripts_dir, "generar_imagenes.py")

    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail="Script generar_imagenes.py no encontrado")

    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=os.path.normpath(os.path.join(_HERE, "..", "..")),
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Error al regenerar imágenes: {result.stderr[:500]}"
        )

    catalog = _read_catalog()
    return {
        "message":       "SVGs regenerados correctamente",
        "total_images":  catalog.get("total", 0),
        "generated_at":  catalog.get("generated_at"),
        "log_summary":   result.stdout[-400:] if result.stdout else "",
    }
