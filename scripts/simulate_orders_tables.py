import sys
import os
import random
from datetime import datetime
from decimal import Decimal

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models.core import User, Branch, Company, EmissionPoint
from app.models.operations import Table
from app.models.sales import Sale, SaleDetail, PaymentMethod
from app.models.inventory import Product, Recipe, InventoryMovement
from app.services.inventory_service import InventoryService

def main():
    db = SessionLocal()
    try:
        print("=== SIMULADOR DE PEDIDOS Y MESAS ===")
        
        # 1. Obtener configuraciones básicas
        company = db.query(Company).first()
        branch = db.query(Branch).first()
        admin = db.query(User).filter_by(username="admin").first()
        emission_point = db.query(EmissionPoint).first()
        payment_method = db.query(PaymentMethod).first()

        if not (company and branch and admin and emission_point):
            print("Error: Faltan datos básicos. ¿Corriste init_db.py y seed_cafeteria_completo.py?")
            return

        if not payment_method:
            payment_method = PaymentMethod(name="Efectivo", sri_code="01", is_active=True)
            db.add(payment_method)
            db.flush()

        # 2. Crear mesas si no existen
        table_names = ["Mesa 1", "Mesa 2", "Terraza 1", "Barra"]
        tables = []
        for t_name in table_names:
            t = db.query(Table).filter_by(number=t_name).first()
            if not t:
                t = Table(number=t_name, capacity=4, status="LIBRE", zone="Principal")
                db.add(t)
            tables.append(t)
        db.flush()
        print(f"[OK] {len(tables)} mesas preparadas.")

        # 3. Obtener productos vendibles
        products = db.query(Product).filter_by(is_ready_to_sell=True).all()
        if not products:
            print("Error: No hay productos listos para vender.")
            return
        
        # 4. Simulación: Mesa 1 y Terraza 1 son ocupadas y piden productos
        print("\n--- Iniciando Simulación de Pedidos ---")
        
        sim_tables = [tables[0], tables[2]] # Mesa 1 y Terraza 1
        sales_created = []

        for table in sim_tables:
            table.status = "OCUPADA"
            
            # Crear Sale (Cabecera)
            new_sale = Sale(
                branch_id=branch.id,
                user_id=admin.id,
                company_id=company.id,
                emission_point_id=emission_point.id,
                invoice_number=f"001-001-{random.randint(100000, 999999)}",
                status="PREPARANDO",
                customer_name="CONSUMIDOR FINAL",
                consumption_type="MESA",
                table_id=table.id,
                total=0.0
            )
            db.add(new_sale)
            db.flush()
            
            # Añadir 2 a 4 productos al azar
            num_items = random.randint(2, 4)
            chosen_products = random.sample(products, num_items)
            
            total_sale = 0.0
            for prod in chosen_products:
                qty = random.randint(1, 3)
                subtotal = float(prod.sale_price) * qty
                total_sale += subtotal
                
                detail = SaleDetail(
                    sale_id=new_sale.id,
                    product_id=prod.id,
                    quantity=qty,
                    unit_price=float(prod.sale_price),
                    total=subtotal
                )
                db.add(detail)
            
            new_sale.total = total_sale
            new_sale.subtotal = total_sale
            sales_created.append((table, new_sale))
            db.flush()
            
            print(f"[PEDIDO] {table.number} - Creada orden por ${total_sale:.2f} con {num_items} productos.")
        
        db.commit()

        # 5. Facturar las órdenes y deducir inventario
        print("\n--- Facturando Órdenes y Deduciendo Inventario ---")
        for table, sale in sales_created:
            # Facturar
            sale.status = "FACTURADO"
            sale.payment_method_id = payment_method.id
            sale.sri_status = "AUTORIZADO"
            sale.access_key = f"1234567890123456789012345678901234567890{sale.id:09d}" # Mock clave
            
            # Liberar mesa
            table.status = "LIBRE"
            
            # Llamar al servicio de inventario para BOM
            print(f"Facturando {sale.invoice_number} de {table.number}...")
            InventoryService.process_sale_inventory_deduction(db, sale)
            
            # Verificar movimientos de inventario asociados a esta venta
            movs = db.query(InventoryMovement).filter_by(reference_id=sale.id, reference_type="Sale").all()
            print(f"  -> Generados {len(movs)} movimientos de inventario (Kárdex) por los ingredientes/productos.")
            
            print(f"[OK] {table.number} facturada y liberada. Inventario deducido.")
            
        print("\n=== SIMULACIÓN EXITOSA ===")
        
    except Exception as e:
        db.rollback()
        print(f"ERROR DURANTE SIMULACIÓN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
