import sys
import os
from datetime import datetime, timedelta

# Agregar el directorio raíz al path para importar el módulo app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, SessionLocal
# Importar TODOS los modelos para que SQLAlchemy resuelva las referencias entre clases
from app.models.core import Base, Branch, Role, User, SecurityPolicy, PasswordHistory, Company, EmissionPoint
from app.models.sales import Sale, SaleDetail, SalePayment, TaxParameter, PaymentMethod
from app.models.inventory import Product, Recipe
from app.models.expenses import Expense, ExpenseCategory
from app.models.operations import Menu, MenuItem, Table, ServiceConfig

def init_db():
    # Crear tablas
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 1. Crear Roles
        roles = [
            Role(name="Administrador", description="Acceso total al sistema"),
            Role(name="Control", description="Operación diaria, inventario y ventas"),
            Role(name="Soporte", description="Resolución de problemas técnico-operativos")
        ]
        for r in roles:
            if not db.query(Role).filter_by(name=r.name).first():
                db.add(r)
        
        # 1.5 Crear Empresa Modelo
        company = db.query(Company).filter_by(ruc="1790011001001").first()
        if not company:
            company = Company(
                ruc="1790011001001",
                business_name="Empresa Modelo S.A.",
                commercial_name="Sistema POS",
                address="Av. Principal y Secundaria",
                phone="+593 2 2999 999",
                obligado_contabilidad=True,
                environment=1,
                brand_personality="Joven, orgulloso, directo, auténtico, viral",
                brand_visuals="Icono estilizado pan de yuca, tipografía fuerte, fotografía de producto",
                brand_packaging="Funda Ziploc con logo impreso, sticker circular negro/amarillo, QR de Instagram",
                brand_tone="Pan de yuca como lo hacía la abuela. Ahora con entrega a domicilio.",
                brand_channels="Instagram, TikTok, apps de delivery, markets modernos, ferias gastronómicas",
                font_family="Outfit",
                color_bg="#020617",
                color_sidebar="#0f172a",
                color_card="rgba(30,41,59,0.5)",
                color_accent="#fbbf24",
                color_text="#f8fafc",
                color_muted="#94a3b8",
                color_success="#10b981",
                color_danger="#ef4444"
            )
            db.add(company)
            db.flush()

        # 2. Crear Sucursal de Prueba
        branch = db.query(Branch).filter_by(sri_establishment_code="001").first()
        if not branch:
            branch = Branch(
                name="Sucursal Principal",
                address="Av. Principal y Secundaria",
                sri_establishment_code="001",
                company_id=company.id
            )
            db.add(branch)
            db.flush() # Para obtener el ID

        # 2.1 Crear Punto de Emisión por Defecto
        emission_point = db.query(EmissionPoint).filter_by(branch_id=branch.id, code="001").first()
        if not emission_point:
            emission_point = EmissionPoint(
                branch_id=branch.id,
                code="001",
                name="Caja Principal",
                invoice_sequential=1
            )
            db.add(emission_point)
            db.flush()

        # 2.5. Roles con permisos granulares RBAC
        perms_admin = {"ventas": True, "inventario": True, "recetas": True, "menus": True, "gastos": True, "usuarios": True, "reportes": True, "config": True}
        perms_control = {"ventas": True, "inventario": True, "recetas": True, "menus": True, "gastos": True, "usuarios": False, "reportes": True, "config": False}
        perms_soporte = {"ventas": True, "inventario": False, "recetas": False, "menus": False, "gastos": False, "usuarios": False, "reportes": False, "config": False}
        role_admin   = db.query(Role).filter_by(name="Administrador").first()
        role_control = db.query(Role).filter_by(name="Control").first()
        role_soporte = db.query(Role).filter_by(name="Soporte").first()
        if role_admin:   role_admin.permissions   = perms_admin
        if role_control: role_control.permissions = perms_control
        if role_soporte: role_soporte.permissions = perms_soporte
        db.flush()

        # 3. Usuario Administrador con contraseña bcrypt (ISO 27001 A.9.2.4)
        import bcrypt
        from datetime import timedelta
        if not db.query(User).filter_by(username="admin").first():
            admin_role = db.query(Role).filter_by(name="Administrador").first()
            raw_pass = "admin123$"
            hashed = bcrypt.hashpw(raw_pass.encode(), bcrypt.gensalt(rounds=12)).decode()
            admin_user = User(
                username="admin",
                email="admin@pos.com",
                password_hash=hashed,
                full_name="Administrador del Sistema",
                phone="+593 99 999 9999",
                role_id=admin_role.id,
                branch_id=branch.id,
                company_id=company.id,
                is_active=True,
                is_locked=False,
                must_change_password=False,  # El admin inicial no necesita cambio
                password_changed_at=datetime.utcnow(),
            )
            db.add(admin_user)
            print("[SEGURIDAD] Usuario 'admin' creado con hash bcrypt (costo=12)")

        # 3.1 Política de Seguridad por defecto (ISO 27001)
        if not db.query(SecurityPolicy).first():
            db.add(SecurityPolicy(
                min_password_length=8,
                require_uppercase=True,
                require_numbers=True,
                require_symbols=True,
                password_expiry_days=90,
                password_history_count=5,
                max_failed_attempts=5,
                lockout_duration_minutes=30,
                session_timeout_minutes=60,
                jwt_expiry_minutes=60,
            ))
            print("[SEGURIDAD] Política ISO 27001 inicializada")

        # 4. Configurar IVA Vigente (Ecuador 15%)
        tax = db.query(TaxParameter).filter_by(name="IVA 15%").first()
        if not tax:
            tax = TaxParameter(
                name="IVA 15%",
                percentage=15.00,
                valid_from=datetime.utcnow() - timedelta(days=30),
                is_active=True
            )
            db.add(tax)

        # 5. Métodos de Pago SRI
        payments = [
            PaymentMethod(name="Efectivo", sri_code="01"),
            PaymentMethod(name="Tarjeta de Crédito", sri_code="19"),
            PaymentMethod(name="Transferencia", sri_code="20")
        ]
        for p in payments:
            if not db.query(PaymentMethod).filter_by(sri_code=p.sri_code).first():
                db.add(p)

        # 5.1 Categorías de Gastos
        exp_categories = [
            ExpenseCategory(name="Servicios Básicos", description="Luz, Agua, Teléfono, Internet"),
            ExpenseCategory(name="Arriendo", description="Pago de local"),
            ExpenseCategory(name="Suministros", description="Limpieza, Papelería"),
            ExpenseCategory(name="Mantenimiento", description="Reparación de máquinas"),
            ExpenseCategory(name="Otros", description="Gastos varios")
        ]
        for ec in exp_categories:
            if not db.query(ExpenseCategory).filter_by(name=ec.name).first():
                db.add(ec)

        # 6. Productos e Insumos de Prueba
        # Insumos
        if not db.query(Product).filter_by(sku="INS-001").first():
            cafe = Product(sku="INS-001", name="Café en Grano (Kg)", unit="gr", is_ingredient=True, cost_price=0.015, company_id=company.id)
            db.add(cafe)
        
        if not db.query(Product).filter_by(sku="INS-002").first():
            leche = Product(sku="INS-002", name="Leche Entera (L)", unit="ml", is_ingredient=True, cost_price=0.001, menu_category="Insumos", company_id=company.id)
            db.add(leche)
        
        # Productos Finales
        capuchino = db.query(Product).filter_by(sku="FIN-001").first()
        if not capuchino:
            capuchino = Product(sku="FIN-001", name="Producto Modelo", unit="Unit", is_ready_to_sell=True, sale_price=3.50, menu_category="Principal", company_id=company.id)
            db.add(capuchino)
        
        db.flush()

        # 7. Receta para Capuchino
        if capuchino:
            cafe = db.query(Product).filter_by(sku="INS-001").first()
            leche = db.query(Product).filter_by(sku="INS-002").first()
            
            if not db.query(Recipe).filter_by(product_id=capuchino.id).first():
                recipe_items = [
                    Recipe(product_id=capuchino.id, ingredient_id=cafe.id, quantity=18.0), # 18g café
                    Recipe(product_id=capuchino.id, ingredient_id=leche.id, quantity=200.0) # 200ml leche
                ]
                db.add_all(recipe_items)

        # 8. Mesas de Prueba
        for num in ["1", "2", "3", "4", "5"]:
            if not db.query(Table).filter_by(number=num).first():
                db.add(Table(number=num, capacity=4, zone="Interior"))
        if not db.query(Table).filter_by(number="B1").first():
            db.add(Table(number="B1", capacity=2, zone="Barra"))
        if not db.query(Table).filter_by(number="T1").first():
            db.add(Table(number="T1", capacity=6, zone="Terraza"))

        # 9. Configuración de Domicilio (10% mínimo $1.50)
        if not db.query(ServiceConfig).filter_by(service_type="DOMICILIO").first():
            db.add(ServiceConfig(
                service_type="DOMICILIO", is_active=True,
                surcharge_percentage=10.0, base_factor=1.50,
                description="Servicio a domicilio - sector urbano"
            ))

        # 10. Menú base
        if not db.query(Menu).filter_by(name="Principal").first():
            menu = Menu(name="Principal", description="Platos y bebidas", is_active=True)
            db.add(menu)

        db.commit()
        print("Base de datos inicializada con éxito.")
        
    except Exception as e:
        db.rollback()
        print(f"Error al inicializar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
