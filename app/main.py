from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from datetime import date, datetime
import hashlib
from .config import _get, save_env_values, BASE_DIR
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .database import get_db, engine
from .models.core import Base, Branch, User, AuditLog, Company, EmissionPoint
from .models.sales import Sale, SaleDetail, SalePayment, TaxParameter
from .models.expenses import Expense, ExpenseCategory
from .models.operations import Menu, MenuItem, Table, ServiceConfig
from .schemas import SaleCreate, SaleResponse, ExpenseCreate
from .services.inventory_service import InventoryService
from .services.sri_service import SRIService
from .services.dashboard_service import DashboardService
from .services.report_service import ReportService
from .routers import inventory as inventory_router
from .routers import recipes as recipes_router
from .routers import menus as menus_router
from .routers import operations as operations_router
from .routers import settings as settings_router
from .routers import auth as auth_router
from .routers import qr as qr_router
from .routers import profiles as profiles_router
from .routers import migration as migration_router
from .routers import orders as orders_router
from .routers import customers as customers_router
from .routers import billing_reports as billing_reports_router
from .routers import images as images_router
from .routers import cash as cash_router
from .routers import accounting as accounting_router
from .routers import banking as banking_router
# Nuevos modelos — necesarios para que Base.metadata los registre
from .models import cash as _cash_models          # noqa: F401
from .models import accounting as _acc_models     # noqa: F401
from .models import banking as _bank_models       # noqa: F401
from .services.accounting_service import AccountingService
from decimal import Decimal
import uuid
from datetime import date
import os

app = FastAPI(title="Sistema POS API - Ecuador SRI", version="2.0")


# ─── Sistema de Control de Licencias y Período de Prueba ──────────────────────

def get_installation_date() -> date:
    """Obtiene la fecha de instalación desde el .env o registra la fecha de hoy si no existe."""
    inst_str = _get("INSTALLATION_DATE", "").strip()
    if not inst_str:
        today_str = date.today().strftime("%Y-%m-%d")
        save_env_values({"INSTALLATION_DATE": today_str})
        return date.today()
    try:
        return datetime.strptime(inst_str, "%Y-%m-%d").date()
    except ValueError:
        today_str = date.today().strftime("%Y-%m-%d")
        save_env_values({"INSTALLATION_DATE": today_str})
        return date.today()

def get_trial_days() -> int:
    """Obtiene los días de prueba configurados en .env. Máximo 30 días, por defecto 15."""
    try:
        days = int(_get("TRIAL_DAYS", "15"))
        if days > 30:
            return 30
        if days < 1:
            return 1
        return days
    except ValueError:
        return 15

def is_system_activated() -> bool:
    """Verifica si el archivo diedcomp existe en la raíz y contiene la firma SHA256 correcta."""
    diedcomp_path = BASE_DIR / "diedcomp"
    if not diedcomp_path.exists():
        return False
    try:
        with open(diedcomp_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        expected = "8c331be7a41aaa926685215b7c5385d8589d2a890a57d6e327036ff735cf0a1a"
        return content == expected
    except Exception:
        return False

@app.middleware("http")
async def check_licensing_middleware(request: Request, call_next):
    """
    Middleware que bloquea el sistema si expiró el trial y no está activado.
    Permite acceso libre a login, activación y archivos estáticos.
    """
    path = request.url.path
    if (
        path.startswith("/static") or
        path.startswith("/api/auth") or
        path == "/login" or
        path == "/activate" or
        path == "/api/activate" or
        path == "/api/license/status"
    ):
        return await call_next(request)
        
    if not is_system_activated():
        inst_date = get_installation_date()
        trial_days = get_trial_days()
        days_elapsed = (date.today() - inst_date).days
        if days_elapsed > trial_days:
            # Trial expiró y no está activado -> Redirigir a activación
            return RedirectResponse(url="/activate")
            
    return await call_next(request)


@app.on_event("startup")
def startup_db_migration():
    """
    Crea/migra esquema de base de datos en cada arranque.
    Incluye tablas de caja, contabilidad y bancos (NIIF Ecuador).
    """
    from sqlalchemy import inspect, text
    from .database import engine, SessionLocal
    from .models.core import Base

    # 1. Crear TODAS las tablas (nuevas y existentes)
    Base.metadata.create_all(bind=engine)

    # 2. Migraciones incrementales — columnas que pueden faltar en DBs existentes
    inspector = inspect(engine)

    def safe_alter(conn, table: str, col: str, definition: str):
        existing = [c["name"] for c in inspector.get_columns(table)]
        if col not in existing:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {definition}"))
                print(f"[MIGRACION] Columna agregada: {table}.{col}")
            except Exception as e:
                print(f"[MIGRACION] {table}.{col}: {e}")

    with engine.begin() as conn:
        # Sales: retenciones y sesión de caja
        safe_alter(conn, "sales", "withholding_number",       "VARCHAR(17)")
        safe_alter(conn, "sales", "withholding_iva",          "NUMERIC(12,2) DEFAULT 0.0")
        safe_alter(conn, "sales", "withholding_renta",        "NUMERIC(12,2) DEFAULT 0.0")
        safe_alter(conn, "sales", "withholding_date",         "DATETIME")
        safe_alter(conn, "sales", "cash_session_id",          "INTEGER")
        safe_alter(conn, "sales", "journal_entry_id",         "INTEGER")
        # Expenses: cuenta contable por categoría
        safe_alter(conn, "expense_categories", "accounting_account_code", "VARCHAR(20)")

    # 3. Seed Plan de Cuentas (solo si tabla vacía)
    db = SessionLocal()
    try:
        AccountingService.seed_chart_of_accounts(db)
    except Exception as e:
        print(f"[CONTABILIDAD] Error al sembrar Plan de Cuentas: {e}")
    finally:
        db.close()

# ─── Archivos estáticos ───────────────────────────────────────────────────────
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

# ─── Registrar Routers ───────────────────────────────────────────────────────
app.include_router(inventory_router.router)
app.include_router(recipes_router.router)
app.include_router(menus_router.router)
app.include_router(operations_router.router)
app.include_router(settings_router.router)
app.include_router(auth_router.router)
app.include_router(qr_router.router)
app.include_router(profiles_router.router)
app.include_router(migration_router.router)
app.include_router(orders_router.router)
app.include_router(customers_router.router)
app.include_router(billing_reports_router.router)
app.include_router(images_router.router)
app.include_router(cash_router.router)
app.include_router(accounting_router.router)
app.include_router(banking_router.router)

@app.get("/api/branches")
def list_branches(db=Depends(get_db)):
    from .models.core import Branch
    return db.query(Branch).all()


@app.get("/admin/settings", response_class=HTMLResponse)
def get_settings_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_settings.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/admin/reports", response_class=HTMLResponse)
def get_reports_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_reports.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/license/status")
def get_license_status():
    """Estado actual del licenciamiento para la pantalla de activación."""
    activated = is_system_activated()
    inst_date = get_installation_date()
    trial_days = get_trial_days()
    days_elapsed = (date.today() - inst_date).days
    days_remaining = max(0, trial_days - days_elapsed)
    return {
        "activated": activated,
        "trial_active": not activated and days_elapsed <= trial_days,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "trial_days": trial_days,
    }


@app.get("/activate", response_class=HTMLResponse)
def get_activation_ui():
    if is_system_activated():
        return RedirectResponse(url="/")
    template_path = os.path.join(os.path.dirname(__file__), "templates", "activate.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


from pydantic import BaseModel

class ActivationRequest(BaseModel):
    key: str

@app.post("/api/activate")
def activate_system(req: ActivationRequest):
    seed = "JessicaAlava$1976"
    entered_key = req.key
    # Calcular hash en memoria
    computed_hash = hashlib.sha256((entered_key + seed).encode()).hexdigest()
    expected_hash = "8c331be7a41aaa926685215b7c5385d8589d2a890a57d6e327036ff735cf0a1a"
    
    if computed_hash == expected_hash:
        # Se escribe únicamente el hash, la clave en texto plano NUNCA se almacena en el disco.
        diedcomp_path = BASE_DIR / "diedcomp"
        try:
            with open(diedcomp_path, "w", encoding="utf-8") as f:
                f.write(computed_hash)
            return {"ok": True, "message": "Sistema activado exitosamente."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error al escribir el archivo de licencia: {e}")
    else:
        raise HTTPException(status_code=400, detail="Clave de activación incorrecta o inválida.")


@app.get("/pos", response_class=HTMLResponse)
def get_pos_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "pos.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/inventory", response_class=HTMLResponse)
def get_inventory_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "inventory.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin/recipes", response_class=HTMLResponse)
def get_admin_recipes_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_recipes.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin/menus", response_class=HTMLResponse)
def get_admin_menus_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_menus.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin/tables", response_class=HTMLResponse)
def get_admin_tables_ui():
    return HTMLResponse(content='<script>window.location="/admin/menus"</script>')

@app.get("/pedidos", response_class=HTMLResponse)
def get_pedidos_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "pedidos.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin/profiles", response_class=HTMLResponse)
def get_profiles_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_profiles.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/admin/migration", response_class=HTMLResponse)
def get_migration_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_migration.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/menu-digital/{menu_id}", response_class=HTMLResponse)
def get_menu_digital(menu_id: int, db: Session = Depends(get_db)):
    """Menú digital para escanear con QR (sin autenticación)."""
    menu = db.get(Menu, menu_id)
    if not menu:
        raise HTTPException(status_code=404, detail="Menú no encontrado")
    template_path = os.path.join(os.path.dirname(__file__), "templates", "menu_digital.html")
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content.replace("{{MENU_ID}}", str(menu_id))

@app.get("/comandas", response_class=HTMLResponse)
def get_comandas_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "comandas.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/caja", response_class=HTMLResponse)
def get_caja_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "caja.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/contabilidad", response_class=HTMLResponse)
def get_contabilidad_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "contabilidad.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/bancos", response_class=HTMLResponse)
def get_bancos_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "bancos.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/comandas/data")
def get_comandas_data(db: Session = Depends(get_db)):
    from .models.sales import Sale, SaleDetail
    from .models.inventory import Product
    
    # Obtenemos las ultimas ventas que no esten entregadas
    sales = db.query(Sale).order_by(Sale.timestamp.desc()).limit(10).all()
    result = []
    for s in sales:
        items = []
        for d in s.details:
            product = db.get(Product, d.product_id)
            items.append({"name": product.name, "qty": int(d.quantity)})
        
        result.append({
            "id": s.id,
            "invoice": s.invoice_number.split("-")[-1],
            "customer": s.customer_name,
            "type": s.consumption_type,
            "time": s.timestamp.strftime("%H:%M"),
            "items": items
        })
    return result

@app.get("/", response_class=HTMLResponse)
def get_dashboard_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/audit", response_class=HTMLResponse)
def get_audit_ui():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "audit.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/audit/")
def get_audit_logs(db: Session = Depends(get_db)):
    from .models.core import AuditLog, User
    logs = db.query(AuditLog, User.username).join(User).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return [{
        "timestamp": log[0].timestamp,
        "username": log[1],
        "action": log[0].action,
        "entity": log[0].entity,
        "entity_id": log[0].entity_id,
        "new_values": log[0].new_values
    } for log in logs]

@app.get("/dashboard/daily")
def get_daily_dashboard(branch_id: int, db: Session = Depends(get_db)):
    today = date.today()
    metrics = DashboardService.get_daily_metrics(db, today, branch_id)
    top_products = DashboardService.get_top_products(db, today)
    
    return {
        "metrics": metrics,
        "top_products": [{"name": p[0], "quantity": p[1]} for p in top_products]
    }

@app.get("/inventory/data")
def get_inventory_data(db: Session = Depends(get_db)):
    from .models.inventory import Product, InventoryMovement
    from .services.inventory_service import InventoryService
    
    products = db.query(Product).all()
    result = []
    for p in products:
        stock = InventoryService.get_current_stock(db, p.id, branch_id=1)
        result.append({
            "sku": p.sku,
            "name": p.name,
            "unit": p.unit,
            "is_ingredient": p.is_ingredient,
            "stock": float(stock)
        })
    return result

@app.get("/recipes/data")
def get_recipes_data(db: Session = Depends(get_db)):
    from .models.inventory import Product, Recipe
    
    recipes = db.query(Recipe).all()
    result = {}
    for r in recipes:
        product_name = db.get(Product, r.product_id).name
        ingredient = db.get(Product, r.ingredient_id)
        if product_name not in result:
            result[product_name] = []
        result[product_name].append({
            "name": ingredient.name,
            "qty": float(r.quantity),
            "unit": ingredient.unit
        })
    return result

@app.get("/reports/daily-close")
def download_daily_close(branch_id: int, db: Session = Depends(get_db)):
    """
    Genera y descarga el reporte en PDF del cierre diario para una sucursal específica.
    
    Obtiene las métricas diarias y los productos más vendidos, y genera un documento PDF
    fluyente para descarga directa del usuario.
    
    :param branch_id: ID de la sucursal
    :param db: Sesión de SQLAlchemy inyectada
    :return: StreamingResponse con el archivo PDF adjunto
    """
    today = date.today()
    metrics = DashboardService.get_daily_metrics(db, today, branch_id)
    top_products_raw = DashboardService.get_top_products(db, today)
    top_products = [{"name": p[0], "quantity": p[1]} for p in top_products_raw]
    
    pdf_buffer = ReportService.generate_daily_close_pdf(metrics, top_products)
    
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=cierre_{today}.pdf"}
    )

@app.post("/sales/", response_model=SaleResponse)
def create_sale(sale_data: SaleCreate, db: Session = Depends(get_db)):
    """
    Registra una nueva venta, calcula impuestos, genera clave SRI y descuenta stock.
    """
    # 1. Validar sucursal y usuario
    branch = db.get(Branch, sale_data.branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
        
    # 1.5 Determinar Punto de Emisión y secuencial
    if sale_data.emission_point_id:
        emission_point = db.get(EmissionPoint, sale_data.emission_point_id)
        if not emission_point or emission_point.branch_id != branch.id:
            raise HTTPException(status_code=404, detail="Emission point not found or doesn't belong to this branch")
    else:
        # Por defecto, usar la primera caja activa de esta sucursal
        emission_point = db.query(EmissionPoint).filter(
            EmissionPoint.branch_id == branch.id,
            EmissionPoint.is_active == True
        ).first()
        if not emission_point:
            raise HTTPException(status_code=404, detail="No active emission point found for this branch")
            
    # Obtener y actualizar secuencial de manera atómica (por transacción)
    sequential_num = emission_point.invoice_sequential
    emission_point.invoice_sequential += 1
    
    invoice_number = f"{branch.sri_establishment_code}-{emission_point.code}-{str(sequential_num).zfill(9)}"
    
    # 2. Calcular totales
    total_subtotal = Decimal(0)
    total_tax = Decimal(0)
    
    # Determinar fecha de la venta (UTC por defecto)
    from datetime import datetime
    sale_date = datetime.utcnow()

    # Obtener IVA vigente según fecha de venta
    tax_param = db.query(TaxParameter).filter(
        TaxParameter.is_active == True,
        TaxParameter.valid_from <= sale_date,
        or_(TaxParameter.valid_until == None, TaxParameter.valid_until >= sale_date)
    ).first()
    tax_multiplier = Decimal(tax_param.percentage / 100) if tax_param else Decimal(0.15)

    sale = Sale(
        branch_id=sale_data.branch_id,
        user_id=sale_data.user_id,
        company_id=branch.company_id,
        emission_point_id=emission_point.id,
        customer_name=sale_data.customer_name,
        customer_id=sale_data.customer_id,
        customer_id_type=sale_data.customer_id_type,
        consumption_type=sale_data.consumption_type,
        table_id=sale_data.table_id,
        delivery_address=sale_data.delivery_address,
        invoice_number=invoice_number,
        environment=branch.company.environment if branch.company else 1,
        sale_date=sale_date,
        withholding_number=sale_data.withholding_number,
        withholding_iva=sale_data.withholding_iva or Decimal(0),
        withholding_renta=sale_data.withholding_renta or Decimal(0),
        withholding_date=sale_date if sale_data.withholding_number else None
    )
    
    db.add(sale)
    db.flush() # flush() permite obtener sale.id sin confirmar la transacción (commit)

    # Procesar detalles de venta e impuestos
    for detail_data in sale_data.details:
        item_total = Decimal(detail_data.quantity) * Decimal(detail_data.unit_price)
        item_tax = item_total * tax_multiplier
        
        detail = SaleDetail(
            sale_id=sale.id,
            product_id=detail_data.product_id,
            quantity=detail_data.quantity,
            unit_price=detail_data.unit_price,
            discount=detail_data.discount,
            tax_percentage=tax_multiplier * 100,
            subtotal=item_total,
            total=item_total + item_tax
        )
        db.add(detail)
        total_subtotal += item_total
        total_tax += item_tax

    sale.subtotal_tax = total_subtotal
    sale.tax_amount = total_tax
    sale.total = total_subtotal + total_tax

    # 3. Registrar Pago
    withholding_total = Decimal(sale.withholding_iva or 0) + Decimal(sale.withholding_renta or 0)
    net_payment_amount = sale.total - withholding_total
    
    if net_payment_amount > 0:
        payment = SalePayment(
            sale_id=sale.id,
            payment_method_id=sale_data.payment_method_id,
            amount=net_payment_amount
        )
        db.add(payment)
        
    if withholding_total > 0:
        from .models.sales import PaymentMethod
        pm_ret = db.query(PaymentMethod).filter(PaymentMethod.name.like("%Reten%")).first()
        if not pm_ret:
            pm_ret = PaymentMethod(name="Retención", sri_code="20")
            db.add(pm_ret)
            db.flush()
        
        ret_payment = SalePayment(
            sale_id=sale.id,
            payment_method_id=pm_ret.id,
            amount=withholding_total,
            reference=sale.withholding_number
        )
        db.add(ret_payment)

    # 4. Generar Clave SRI y XML
    sale.access_key = SRIService.generate_access_key(sale, branch)
    # xml_content = SRIService.create_invoice_xml(sale, branch) # Generación XML SRI

    # 5. Ejecutar descuento de inventario por recetas (BOM / Kárdex)
    InventoryService.process_sale_inventory_deduction(db, sale)

    # 6. Asiento contable automático (NIIF — Ventas)
    try:
        je = AccountingService.create_sale_journal_entry(db, sale)
        if je:
            sale.journal_entry_id = je.id
    except Exception as e:
        print(f"[CONTABILIDAD] Asiento de venta no generado: {e}")

    db.commit()
    db.refresh(sale)
    return sale

@app.post("/expenses/")
def create_expense(expense_data: ExpenseCreate, db: Session = Depends(get_db)):
    """
    Registra un gasto operativo en la sucursal.
    
    Permite el registro manual de egresos relacionados a la operación (servicios, insumos directos, arriendos).
    
    :param expense_data: Datos del gasto validado (ExpenseCreate)
    :param db: Sesión de SQLAlchemy inyectada
    :return: Objeto Expense creado
    """
    expense = Expense(
        category_id=expense_data.category_id,
        branch_id=expense_data.branch_id,
        user_id=expense_data.user_id,
        provider_name=expense_data.provider_name,
        description=expense_data.description,
        amount=expense_data.amount,
        tax_amount=expense_data.tax_amount,
        invoice_reference=expense_data.invoice_reference
    )
    db.add(expense)
    db.flush()

    # Asiento contable automático (NIIF — Gastos)
    try:
        AccountingService.create_expense_journal_entry(db, expense)
    except Exception as e:
        print(f"[CONTABILIDAD] Asiento de gasto no generado: {e}")

    db.commit()
    db.refresh(expense)
    return expense

