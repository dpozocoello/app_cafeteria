from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..models.inventory import Product, Recipe, InventoryMovement, MovementType, Batch
from ..models.sales import Sale, SaleDetail
from datetime import datetime

class InventoryService:
    @staticmethod
    def get_current_stock(db: Session, product_id: int, branch_id: int) -> Decimal:
        """
        Calcula el stock actual de un producto en una sucursal sumando/restando movimientos.
        """
        result = db.execute(
            select(func.sum(
                InventoryMovement.quantity
            )).where(
                InventoryMovement.product_id == product_id,
                InventoryMovement.branch_id == branch_id
            )
        ).scalar()
        return Decimal(result or 0)

    @staticmethod
    def register_movement(
        db: Session,
        product_id: int,
        branch_id: int,
        user_id: int,
        quantity: Decimal,
        type: MovementType,
        reference_id: int = None,
        reference_type: str = None,
        notes: str = None
    ) -> InventoryMovement:
        """
        Registra un movimiento en el Kárdex y calcula el nuevo balance.
        """
        current_balance = InventoryService.get_current_stock(db, product_id, branch_id)
        
        # Si es salida o ajuste negativo, la cantidad debe ser negativa para la suma
        qty_to_store = quantity
        if type in [MovementType.OUT] and quantity > 0:
            qty_to_store = -quantity
        
        new_balance = current_balance + qty_to_store

        movement = InventoryMovement(
            product_id=product_id,
            branch_id=branch_id,
            user_id=user_id,
            type=type,
            quantity=qty_to_store,
            balance_after=new_balance,
            reference_id=reference_id,
            reference_type=reference_type,
            notes=notes,
            timestamp=datetime.utcnow()
        )
        
        db.add(movement)
        return movement

    @staticmethod
    def process_sale_inventory_deduction(db: Session, sale: Sale):
        """
        Lógica automática: Por cada ítem vendido, verifica si tiene receta.
        Si tiene receta, descuenta los ingredientes.
        Si no, descuenta el producto directamente.
        """
        for detail in sale.details:
            product = db.get(Product, detail.product_id)
            if not product:
                continue

            # Buscar si el producto tiene una receta (BOM)
            recipe_items = db.execute(
                select(Recipe).where(Recipe.product_id == product.id)
            ).scalars().all()

            if recipe_items:
                # Caso A: El producto se compone de ingredientes (ej: Capuchino)
                for item in recipe_items:
                    total_qty_to_deduct = Decimal(item.quantity) * Decimal(detail.quantity)
                    InventoryService.register_movement(
                        db=db,
                        product_id=item.ingredient_id,
                        branch_id=sale.branch_id,
                        user_id=sale.user_id,
                        quantity=total_qty_to_deduct,
                        type=MovementType.OUT,
                        reference_id=sale.id,
                        reference_type="Sale",
                        notes=f"Consumo por venta de {product.name} (Factura {sale.invoice_number})"
                    )
            else:
                # Caso B: El producto se vende directamente (ej: Galleta, Botella de Agua)
                InventoryService.register_movement(
                    db=db,
                    product_id=product.id,
                    branch_id=sale.branch_id,
                    user_id=sale.user_id,
                    quantity=Decimal(detail.quantity),
                    type=MovementType.OUT,
                    reference_id=sale.id,
                    reference_type="Sale",
                    notes=f"Venta directa (Factura {sale.invoice_number})"
                )
        
        db.commit()
