"""
Router: QR Codes por Mesa y por Menú
Genera imágenes QR en base64 para facilitar el pedido desde la mesa.
"""
import io
import base64
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.operations import Table, Menu

router = APIRouter(prefix="/api/qr", tags=["Códigos QR"])


def _make_qr(data: str, box_size: int = 10) -> bytes:
    """Genera PNG del QR en bytes."""
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=box_size, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#020617", back_color="#fbbf24")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/table/{table_id}.png")
def qr_table(table_id: int, db: Session = Depends(get_db)):
    """QR que apunta al módulo de pedidos filtrado por mesa."""
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    url = f"http://127.0.0.1:8000/pedidos?mesa={table.number}&tid={table_id}"
    return Response(content=_make_qr(url), media_type="image/png")


@router.get("/menu/{menu_id}.png")
def qr_menu(menu_id: int, db: Session = Depends(get_db)):
    """QR que apunta al menú digital."""
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    url = f"http://127.0.0.1:8000/menu-digital/{menu_id}"
    return Response(content=_make_qr(url), media_type="image/png")


@router.get("/table/{table_id}/page", response_class=HTMLResponse)
def qr_table_page(table_id: int, db: Session = Depends(get_db)):
    """Página para imprimir el QR de una mesa."""
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    url = f"http://127.0.0.1:8000/pedidos?mesa={table.number}&tid={table_id}"
    qr_b64 = base64.b64encode(_make_qr(url, box_size=12)).decode()
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
        body{{font-family:'Outfit',sans-serif;background:#020617;color:#f8fafc;display:flex;align-items:center;justify-content:center;min-height:100vh;flex-direction:column;gap:1rem}}
        .card{{background:#0f172a;border:2px solid #fbbf24;border-radius:1.5rem;padding:2rem;text-align:center;max-width:300px}}
        h2{{color:#fbbf24;margin-bottom:.5rem}}
        img{{border-radius:1rem;width:220px;margin:1rem 0}}
        p{{color:#94a3b8;font-size:.9rem}}
        .mesa{{font-size:3rem;font-weight:700;color:#fbbf24}}
    </style></head><body>
    <div class="card">
        <div class="mesa">Mesa {table.number}</div>
        <h2>Escanea para pedir</h2>
        <img src="data:image/png;base64,{qr_b64}" alt="QR Mesa {table.number}">
        <p>{table.zone or 'Zona General'} · Capacidad: {table.capacity} personas</p>
        <p style="font-size:.75rem;margin-top:.5rem">🔗 {url}</p>
    </div>
    <button onclick="window.print()" style="background:#fbbf24;color:#000;border:none;padding:.8rem 2rem;border-radius:10px;font-weight:700;cursor:pointer;margin-top:1rem">🖨️ Imprimir</button>
    </body></html>"""
