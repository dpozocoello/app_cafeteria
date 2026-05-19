"""
Router: Menús CRUD
Endpoints para gestión completa de menús, imágenes de platos y QR codes.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.operations import Menu, MenuItem
from ..models.inventory import Product
from ..schemas import MenuCreate, MenuUpdate
import os, shutil, uuid

router = APIRouter(prefix="/api/menus", tags=["Menús"])

# Directorio donde se guardan las imágenes de platos
DISHES_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "dishes")
os.makedirs(DISHES_DIR, exist_ok=True)


def _serialize_menu(menu: Menu, db: Session) -> dict:
    items = []
    for item in menu.items:
        product = db.get(Product, item.product_id)
        if product:
            # La imagen se obtiene del ítem (si tiene) o del producto (fallback)
            image_url = item.image_url or product.image_url
            items.append({
                "item_id": item.id,
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "category": product.menu_category,
                "price": float(item.override_price or product.sale_price or 0),
                "image_url": image_url,
                "product_image_url": product.image_url,  # imagen del producto
                "is_available": item.is_available,
                "display_order": item.display_order,
            })
    return {
        "id": menu.id,
        "name": menu.name,
        "description": menu.description,
        "is_active": menu.is_active,
        "items": items,
    }


@router.get("/")
def list_menus(db: Session = Depends(get_db)):
    menus = db.query(Menu).all()
    return [_serialize_menu(m, db) for m in menus]


@router.get("/{menu_id}")
def get_menu(menu_id: int, db: Session = Depends(get_db)):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    return _serialize_menu(menu, db)


@router.post("/", status_code=201)
def create_menu(data: MenuCreate, db: Session = Depends(get_db)):
    menu = Menu(name=data.name, description=data.description)
    db.add(menu)
    db.flush()
    for pid in data.product_ids:
        db.add(MenuItem(menu_id=menu.id, product_id=pid))
    db.commit()
    db.refresh(menu)
    return _serialize_menu(menu, db)


@router.put("/{menu_id}")
def update_menu(menu_id: int, data: MenuUpdate, db: Session = Depends(get_db)):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    menu.name = data.name
    menu.description = data.description
    menu.is_active = data.is_active
    # Reemplazar items conservando imágenes existentes
    existing = {mi.product_id: mi for mi in db.query(MenuItem).filter_by(menu_id=menu_id).all()}
    db.query(MenuItem).filter_by(menu_id=menu_id).delete()
    for pid in data.product_ids:
        old = existing.get(pid)
        db.add(MenuItem(
            menu_id=menu_id, product_id=pid,
            image_url=old.image_url if old else None,
            is_available=old.is_available if old else True,
            display_order=old.display_order if old else 0,
        ))
    db.commit()
    db.refresh(menu)
    return _serialize_menu(menu, db)


@router.delete("/{menu_id}", status_code=204)
def delete_menu(menu_id: int, db: Session = Depends(get_db)):
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    db.delete(menu)
    db.commit()


# ─── Imagen de plato por MenuItem ────────────────────────────────────────────

@router.post("/items/{item_id}/image")
async def upload_item_image(item_id: int, file: UploadFile = File(...),
                            db: Session = Depends(get_db)):
    """Sube la imagen del plato y la asocia al ítem del menú."""
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    # Validar tipo
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    fname = f"dish_{item_id}_{uuid.uuid4().hex[:8]}.{ext}"
    path = os.path.join(DISHES_DIR, fname)

    # Eliminar imagen anterior
    if item.image_url:
        old_fname = item.image_url.rsplit("/", 1)[-1]
        old_path = os.path.join(DISHES_DIR, old_fname)
        if os.path.exists(old_path):
            os.remove(old_path)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    item.image_url = f"/static/dishes/{fname}"
    db.commit()
    return {"image_url": item.image_url}


@router.delete("/items/{item_id}/image", status_code=204)
def delete_item_image(item_id: int, db: Session = Depends(get_db)):
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    if item.image_url:
        fname = item.image_url.rsplit("/", 1)[-1]
        path = os.path.join(DISHES_DIR, fname)
        if os.path.exists(path):
            os.remove(path)
        item.image_url = None
        db.commit()


@router.put("/items/{item_id}/availability")
def toggle_item_availability(item_id: int, db: Session = Depends(get_db)):
    """Alterna disponibilidad del ítem (agotado/disponible)."""
    item = db.get(MenuItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")
    item.is_available = not item.is_available
    db.commit()
    return {"is_available": item.is_available}


# ─── QR Code por menú ────────────────────────────────────────────────────────

@router.get("/{menu_id}/qr.png")
def menu_qr(menu_id: int, db: Session = Depends(get_db)):
    """Genera el QR del menú digital."""
    from ..routers.qr import _make_qr
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    url = f"http://127.0.0.1:8000/menu-digital/{menu_id}"
    return Response(content=_make_qr(url), media_type="image/png")
