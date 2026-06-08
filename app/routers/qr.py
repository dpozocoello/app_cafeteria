"""
Router: QR Codes por Mesa, Menú y Configuración de Servidor
La URL del servidor se detecta automáticamente de la red local.
"""
import io
import base64
import socket
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.operations import Table, Menu

router = APIRouter(prefix="/api/qr", tags=["Códigos QR"])


def _get_server_url(request: Request) -> str:
    """
    Detecta la IP real del servidor en la red local.
    Prioridad: X-Forwarded-Host → Host header → IP de socket de red.
    Siempre usa el puerto del servidor activo.
    """
    # Intentar obtener host del header (incluye puerto si no es 80/443)
    host_header = request.headers.get("host", "")
    if host_header and not host_header.startswith("127.0.0.1") and not host_header.startswith("localhost"):
        return f"http://{host_header}"

    # Detectar IP real de la interfaz de red (no loopback)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    port = request.url.port or 8000
    return f"http://{local_ip}:{port}"


def _make_qr(data: str, box_size: int = 10) -> bytes:
    """Genera PNG del QR en bytes."""
    import qrcode
    qr = qrcode.QRCode(
        version=1, box_size=box_size, border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#020617", back_color="#fbbf24")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/table/{table_id}.png")
def qr_table(table_id: int, request: Request, db: Session = Depends(get_db)):
    """QR que apunta al módulo de pedidos filtrado por mesa."""
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    base = _get_server_url(request)
    url = f"{base}/pedidos?mesa={table.number}&tid={table_id}"
    return Response(content=_make_qr(url), media_type="image/png")


@router.get("/menu/{menu_id}.png")
def qr_menu(menu_id: int, request: Request, db: Session = Depends(get_db)):
    """QR que apunta al menú digital."""
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    base = _get_server_url(request)
    url = f"{base}/menu-digital/{menu_id}"
    return Response(content=_make_qr(url), media_type="image/png")


@router.get("/table/{table_id}/page", response_class=HTMLResponse)
def qr_table_page(table_id: int, request: Request, db: Session = Depends(get_db)):
    """Página para imprimir el QR de una mesa."""
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    base = _get_server_url(request)
    url = f"{base}/pedidos?mesa={table.number}&tid={table_id}"
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
        <p>{table.zone or 'Zona General'} &middot; Capacidad: {table.capacity} personas</p>
        <p style="font-size:.75rem;margin-top:.5rem">{url}</p>
    </div>
    <button onclick="window.print()" style="background:#fbbf24;color:#000;border:none;padding:.8rem 2rem;border-radius:10px;font-weight:700;cursor:pointer;margin-top:1rem">Imprimir</button>
    </body></html>"""


@router.get("/server-config.png")
def qr_server_config(request: Request):
    """
    QR con la URL real del servidor para que dispositivos de la red local
    accedan al flujo de pareado seguro (/device/pair).
    """
    base = _get_server_url(request)
    url = f"{base}/device/pair"
    return Response(content=_make_qr(url), media_type="image/png")


@router.get("/server-config/page", response_class=HTMLResponse)
def server_config_page(request: Request):
    """
    Página imprimible para configurar dispositivos Android/tablet.
    Muestra el QR de pareado con la IP real del servidor en la red local.
    """
    base = _get_server_url(request)
    pair_url = f"{base}/device/pair"
    devices_url = f"{base}/admin/devices"
    qr_b64 = base64.b64encode(_make_qr(pair_url, box_size=12)).decode()

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <style>
        body{{font-family:'Outfit',sans-serif;background:#020617;color:#f8fafc;
              display:flex;align-items:center;justify-content:center;
              min-height:100vh;flex-direction:column;gap:1rem;padding:1rem}}
        .card{{background:#0f172a;border:2px solid #fbbf24;border-radius:1.5rem;
               padding:2rem;text-align:center;max-width:400px;width:100%}}
        h2{{color:#fbbf24;margin-bottom:.25rem;font-size:1.2rem}}
        .subtitle{{color:#94a3b8;font-size:.85rem;margin-bottom:1rem}}
        img{{border-radius:1rem;width:240px;margin:.75rem 0}}
        .url{{font-family:monospace;background:#1e293b;padding:.5rem 1rem;
              border-radius:8px;color:#fbbf24;word-break:break-all;
              font-size:.82rem;margin:.5rem 0}}
        .step{{display:flex;align-items:flex-start;gap:.6rem;text-align:left;
               background:#1e293b;border-radius:.6rem;padding:.6rem .8rem;
               margin:.3rem 0;font-size:.82rem;color:#94a3b8}}
        .step strong{{color:#f8fafc;display:block;margin-bottom:.1rem}}
        .badge{{display:inline-block;background:#fbbf24;color:#020617;
                border-radius:9999px;width:20px;height:20px;font-weight:700;
                font-size:.75rem;line-height:20px;flex-shrink:0;text-align:center}}
        .admin-link{{color:#fbbf24;font-size:.8rem;margin-top:.75rem;
                     text-decoration:none;border:1px solid #fbbf24;
                     padding:.35rem .9rem;border-radius:8px;display:inline-block}}
        .admin-link:hover{{background:rgba(251,191,36,.12)}}
        @media print{{button{{display:none}}}}
    </style></head><body>
    <div class="card">
        <h2>Conectar Dispositivo al POS</h2>
        <p class="subtitle">Escanea el QR desde el tablet o teléfono del mesero</p>
        <img src="data:image/png;base64,{qr_b64}" alt="QR Pareado">
        <div class="url">{pair_url}</div>

        <div style="margin-top:1rem;text-align:left">
          <div class="step"><span class="badge">1</span>
            <div><strong>Escanear QR</strong>Abre la cámara del dispositivo y escanea este código.</div></div>
          <div class="step"><span class="badge">2</span>
            <div><strong>Registrar nombre</strong>Ingresa el nombre del dispositivo (ej: "Tablet Mesero 2").</div></div>
          <div class="step"><span class="badge">3</span>
            <div><strong>Aprobar desde el admin</strong>El administrador aprueba el dispositivo en el panel.</div></div>
          <div class="step"><span class="badge">4</span>
            <div><strong>Listo</strong>El dispositivo accede automáticamente al sistema de pedidos.</div></div>
        </div>

        <a class="admin-link" href="{devices_url}" target="_blank">Panel de Dispositivos</a>
    </div>
    <button onclick="window.print()"
            style="background:#fbbf24;color:#000;border:none;padding:.8rem 2rem;
                   border-radius:10px;font-weight:700;cursor:pointer;margin-top:1rem">
      Imprimir instrucciones
    </button>
    </body></html>"""
