"""
Router: Toma de Pedidos (Módulo Mesero)
Permite crear pedidos por mesa, para llevar o domicilio SIN facturar.
Los pedidos pasan a la pantalla KDS (comandas) para preparación.
"""
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db
from ..models.operations import Table, Menu, MenuItem, ServiceConfig
from ..models.inventory import Product
from ..models.sales import Sale, SaleDetail

router = APIRouter(prefix="/api/orders", tags=["Toma de Pedidos"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    product_id: int
    quantity: int
    notes: Optional[str] = None


class OrderCreate(BaseModel):
    service_type: str = "MESA"          # MESA | LLEVAR | DOMICILIO
    table_id: Optional[int] = None      # Para MESA
    customer_name: Optional[str] = "CONSUMIDOR FINAL"
    customer_address: Optional[str] = None  # Para DOMICILIO
    notes: Optional[str] = None
    items: List[OrderItem]
    user_id: int = 1
    branch_id: int = 1


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/tables")
def get_tables(db: Session = Depends(get_db)):
    tables = db.query(Table).order_by(Table.number).all()
    return [{"id": t.id, "number": t.number, "zone": t.zone,
             "capacity": t.capacity, "status": t.status} for t in tables]


@router.get("/menus")
def get_active_menus(db: Session = Depends(get_db)):
    menus = db.query(Menu).filter_by(is_active=True).all()
    result = []
    for m in menus:
        items = []
        for mi in m.items:
            if not mi.is_available:
                continue
            prod = db.get(Product, mi.product_id)
            if prod and prod.is_ready_to_sell:
                items.append({
                    "menu_item_id": mi.id,
                    "product_id": prod.id,
                    "name": prod.name,
                    "description": prod.description,
                    "price": float(mi.override_price or prod.sale_price or 0),
                    "category": prod.menu_category,
                    # Imagen: usa la del ítem del menú; si no tiene, usa la del producto
                    "image_url": mi.image_url or prod.image_url,
                    "sku": prod.sku,
                })
        result.append({"id": m.id, "name": m.name, "description": m.description, "items": items})
    return result


@router.post("", status_code=201)
def create_order(data: OrderCreate, db: Session = Depends(get_db)):
    """Crea un pedido y lo envía al KDS. No genera factura todavía."""
    if not data.items:
        raise HTTPException(status_code=400, detail="El pedido está vacío")

    # Calcular recargo domicilio
    surcharge = 0.0
    if data.service_type == "DOMICILIO":
        svc = db.query(ServiceConfig).filter_by(service_type="DOMICILIO", is_active=True).first()
        if svc:
            subtotal = sum(
                float(db.get(Product, i.product_id).sale_price or 0) * i.quantity
                for i in data.items
            )
            pct = subtotal * float(svc.surcharge_percentage) / 100
            surcharge = max(pct, float(svc.base_factor))

    # Calcular IVA desde tax_parameters
    iva_pct = 0.15
    from ..models.sales import TaxParameter
    tax = db.query(TaxParameter).filter_by(is_active=True).first()
    if tax:
        iva_pct = float(tax.rate) / 100

    # Crear la venta como "PEDIDO" (sin factura)
    subtotal = 0.0
    sale_details = []
    for item in data.items:
        prod = db.get(Product, item.product_id)
        if not prod:
            raise HTTPException(status_code=404, detail=f"Producto {item.product_id} no encontrado")
        unit_price = float(prod.sale_price or 0)
        line_total = unit_price * item.quantity
        subtotal += line_total
        sale_details.append(SaleDetail(
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=unit_price,
            subtotal=line_total,
        ))

    subtotal += surcharge
    tax_amount = subtotal * iva_pct
    total = subtotal + tax_amount

    # Número de orden
    from ..models.sales import PaymentMethod
    pm = db.query(PaymentMethod).first()
    order_num = f"ORD-{datetime.utcnow().strftime('%H%M%S')}"

    sale = Sale(
        invoice_number=order_num,
        sale_date=datetime.utcnow(),
        customer_name=data.customer_name or "CONSUMIDOR FINAL",
        customer_id="9999999999999",
        customer_id_type="07",
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        status="PENDIENTE",
        consumption_type=data.service_type,
        table_id=data.table_id,
        branch_id=data.branch_id,
        user_id=data.user_id,
        payment_method_id=pm.id if pm else 1,
        notes=data.notes,
    )
    db.add(sale)
    db.flush()
    for d in sale_details:
        d.sale_id = sale.id
        db.add(d)

    # Marcar mesa como OCUPADA
    if data.table_id:
        t = db.get(Table, data.table_id)
        if t:
            t.status = "OCUPADA"

    db.commit()
    db.refresh(sale)
    return {"order_number": sale.invoice_number, "total": float(total),
            "surcharge": surcharge, "status": "PENDIENTE"}


@router.get("/pending")
def get_pending_orders(db: Session = Depends(get_db)):
    """Lista pedidos pendientes para el KDS (Comandas)."""
    pending = db.query(Sale).filter(Sale.status == "PENDIENTE").order_by(Sale.sale_date).all()
    return _serialize_orders(pending, db)


@router.get("/ready-to-invoice")
def get_ready_to_invoice(db: Session = Depends(get_db)):
    """Lista pedidos listos para facturar (pasados desde el KDS)."""
    ready = db.query(Sale).filter(Sale.status == "LISTO_FACTURAR").order_by(Sale.sale_date).all()
    return _serialize_orders(ready, db)


def _serialize_orders(sales, db: Session) -> list:
    result = []
    for s in sales:
        table = db.get(Table, s.table_id) if s.table_id else None
        details = db.query(SaleDetail).filter_by(sale_id=s.id).all()
        items = []
        for d in details:
            prod = db.get(Product, d.product_id)
            items.append({
                "name": prod.name if prod else "—",
                "qty": int(d.quantity),
                "unit_price": float(d.unit_price or 0),
                "subtotal": float(d.subtotal or 0),
                "image_url": prod.image_url if prod else None,
            })
        result.append({
            "id": s.id,
            "invoice": s.invoice_number,
            "type": s.consumption_type,
            "table": table.number if table else None,
            "table_id": s.table_id,
            "customer": s.customer_name,
            "customer_id_db": getattr(s, "customer_id", None),
            "delivery_address": s.delivery_address,
            "time": s.sale_date.strftime("%H:%M") if s.sale_date else "--:--",
            "items": items,
            "subtotal": float(s.subtotal or 0),
            "tax_amount": float(s.tax_amount or 0),
            "total": float(s.total or 0),
            "notes": s.notes,
            "status": s.status,
        })
    return result


@router.put("/{order_id}/ready-invoice")
def mark_ready_invoice(order_id: int, db: Session = Depends(get_db)):
    """
    KDS: Marca el pedido como LISTO_FACTURAR.
    La comanda queda deshabilitada y el pedido pasa a la cola del POS.
    """
    sale = db.get(Sale, order_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if sale.status not in ("PENDIENTE", "PREPARANDO"):
        raise HTTPException(status_code=400, detail=f"El pedido está en estado '{sale.status}', no se puede cambiar")
    sale.status = "LISTO_FACTURAR"
    db.commit()
    return {"ok": True, "order_id": order_id, "status": "LISTO_FACTURAR",
            "message": "Pedido listo para facturar en el POS"}


@router.put("/{order_id}/complete")
def complete_order(order_id: int, db: Session = Depends(get_db)):
    """Marca el pedido como FACTURADO y libera la mesa."""
    sale = db.get(Sale, order_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    sale.status = "FACTURADO"
    if sale.table_id:
        t = db.get(Table, sale.table_id)
        if t:
            t.status = "LIBRE"
    db.commit()
    return {"message": "Pedido facturado correctamente", "status": "FACTURADO"}
