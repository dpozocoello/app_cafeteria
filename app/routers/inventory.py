"""
Router: Inventario CRUD
Endpoints para gestión completa de productos e insumos, incluye upload de imagen.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.inventory import Product
from ..schemas import ProductCreate, ProductUpdate
import os, shutil, uuid

router = APIRouter(prefix="/api/products", tags=["Inventario"])

DISHES_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "dishes")
os.makedirs(DISHES_DIR, exist_ok=True)


def _serialize(p: Product) -> dict:
    return {
        "id": p.id, "sku": p.sku, "name": p.name,
        "description": p.description, "unit": p.unit,
        "menu_category": p.menu_category,
        "cost_price": float(p.cost_price or 0),
        "sale_price": float(p.sale_price or 0),
        "is_ready_to_sell": p.is_ready_to_sell,
        "is_ingredient": p.is_ingredient,
        "min_stock": float(p.min_stock or 0),
        "image_url": p.image_url,
        "created_at": str(p.created_at),
    }


@router.get("/")
def list_products(db: Session = Depends(get_db)):
    return [_serialize(p) for p in db.query(Product).all()]


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return _serialize(p)


@router.post("/", status_code=201)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    if db.query(Product).filter_by(sku=data.sku).first():
        raise HTTPException(status_code=400, detail=f"SKU '{data.sku}' ya existe")
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return _serialize(product)


@router.put("/{product_id}")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for field, value in data.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return _serialize(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    db.delete(product)
    db.commit()


# ─── Imagen del producto/plato ────────────────────────────────────────────────

@router.post("/{product_id}/image")
async def upload_product_image(product_id: int, file: UploadFile = File(...),
                               db: Session = Depends(get_db)):
    """Sube o reemplaza la imagen de un producto."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes (jpg, png, webp)")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    fname = f"product_{product_id}_{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join(DISHES_DIR, fname)

    # Borrar imagen anterior si existe
    if product.image_url:
        old_fname = product.image_url.rsplit("/", 1)[-1]
        old_path = os.path.join(DISHES_DIR, old_fname)
        if os.path.exists(old_path):
            os.remove(old_path)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    product.image_url = f"/static/dishes/{fname}"
    db.commit()
    return {"image_url": product.image_url, "product_id": product_id}


@router.delete("/{product_id}/image", status_code=204)
def delete_product_image(product_id: int, db: Session = Depends(get_db)):
    """Elimina la imagen de un producto."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if product.image_url:
        fname = product.image_url.rsplit("/", 1)[-1]
        path = os.path.join(DISHES_DIR, fname)
        if os.path.exists(path):
            os.remove(path)
        product.image_url = None
        db.commit()
