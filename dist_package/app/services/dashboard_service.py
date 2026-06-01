from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from ..models.sales import Sale, SaleDetail
from ..models.inventory import InventoryMovement, Product, MovementType
from ..models.expenses import Expense
from datetime import datetime, date

class DashboardService:
    @staticmethod
    def get_daily_metrics(db: Session, target_date: date, branch_id: int):
        """
        Calcula los KPIs principales del dia para una sucursal.
        """
        # 1. Ventas e Impuestos
        sales_data = db.query(
            func.sum(Sale.total).label("total_sales"),
            func.sum(Sale.tax_amount).label("total_tax"),
            func.count(Sale.id).label("transaction_count")
        ).filter(
            and_(
                func.date(Sale.timestamp) == target_date,
                Sale.branch_id == branch_id
            )
        ).first()

        # 2. Gastos del día
        expenses_total = db.query(func.sum(Expense.amount)).filter(
            and_(
                func.date(Expense.timestamp) == target_date,
                Expense.branch_id == branch_id
            )
        ).scalar() or 0

        # 3. Costo de Ventas (COGS) a traves de movimientos de inventario
        # Sumamos el costo de los movimientos tipo OUT relacionados a ventas
        cogs_total = db.query(func.sum(InventoryMovement.quantity * InventoryMovement.unit_cost)).filter(
            and_(
                func.date(InventoryMovement.timestamp) == target_date,
                InventoryMovement.branch_id == branch_id,
                InventoryMovement.type == MovementType.OUT,
                InventoryMovement.reference_type == "Sale"
            )
        ).scalar() or 0
        
        # Como quantity es negativa en OUT, lo convertimos a positivo
        cogs_total = abs(cogs_total)

        total_sales = sales_data.total_sales or 0
        total_tax = sales_data.total_tax or 0
        net_sales = total_sales - total_tax
        estimated_profit = net_sales - cogs_total - expenses_total

        return {
            "date": target_date,
            "brute_sales": round(total_sales, 2),
            "net_sales": round(net_sales, 2),
            "tax_collected": round(total_tax, 2),
            "expenses": round(expenses_total, 2),
            "cogs": round(cogs_total, 2),
            "estimated_profit": round(estimated_profit, 2),
            "transaction_count": sales_data.transaction_count
        }

    @staticmethod
    def get_top_products(db: Session, target_date: date, limit: int = 5):
        """
        Retorna los productos mas vendidos en el dia.
        """
        return db.query(
            Product.name,
            func.sum(SaleDetail.quantity).label("total_qty")
        ).join(SaleDetail).join(Sale).filter(
            func.date(Sale.timestamp) == target_date
        ).group_by(Product.name).order_by(func.sum(SaleDetail.quantity).desc()).limit(limit).all()
