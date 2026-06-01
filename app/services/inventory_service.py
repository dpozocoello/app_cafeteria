from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..models.inventory import Product, Recipe, InventoryMovement, MovementType, Batch
from ..models.sales import Sale, SaleDetail
from datetime import datetime

class InventoryService:
    """
    Servicio de Gestión de Inventario y Kárdex (BOM - Bill of Materials).
    
    Provee las reglas de negocio para:
    1. Calcular el stock actual acumulando movimientos históricos.
    2. Registrar transacciones en el Kárdex de inventario (entradas, salidas y ajustes).
    3. Descontar stock automáticamente tras una venta, aplicando recetas recursivas si existen.
    """

    @staticmethod
    def get_current_stock(db: Session, product_id: int, branch_id: int) -> Decimal:
        """
        Calcula el saldo de existencias actual (stock disponible) de un producto.
        
        Suma algebraicamente las cantidades registradas en todos los movimientos de Kárdex
        para el producto y sucursal especificados. Las salidas ya están persistidas como
        valores negativos, permitiendo una agregación directa por base de datos.
        
        :param db: Sesión de SQLAlchemy activa
        :param product_id: ID del producto (terminado o insumo) a consultar
        :param branch_id: ID de la sucursal de donde se consulta el stock
        :return: Decimal representando el stock actual (0 si no hay movimientos)
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
        Registra un movimiento en el Kárdex físico y actualiza el saldo corriente del producto.
        
        Este método:
        1. Consulta el stock anterior.
        2. Normaliza el signo de la cantidad:
           - Si el tipo de movimiento es 'Salida' (OUT), el valor se almacena como negativo.
           - Si el tipo de movimiento es 'Entrada' (IN), se almacena como positivo.
        3. Calcula el nuevo saldo (`balance_after`) para auditoría rápida e integridad histórica.
        4. Inserta el registro `InventoryMovement` correspondiente.
        
        :param db: Sesión de SQLAlchemy activa
        :param product_id: ID del producto afectado
        :param branch_id: ID de la sucursal del movimiento
        :param user_id: ID del usuario/operador que ejecuta la acción
        :param quantity: Cantidad absoluta a mover (siempre positiva de entrada)
        :param type: Tipo de movimiento (MovementType.IN, MovementType.OUT, MovementType.ADJUSTMENT)
        :param reference_id: ID del documento origen opcional (e.g. ID de la factura de venta)
        :param reference_type: Nombre del modelo origen opcional (e.g. 'Sale', 'Purchase')
        :param notes: Comentario aclaratorio adicional
        :return: Instancia del movimiento creado
        """
        current_balance = InventoryService.get_current_stock(db, product_id, branch_id)
        
        # Garantizar que las salidas se almacenen con signo negativo
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
        Deducción Automática de Inventario (BOM / Recetas).
        
        Por cada ítem presente en la factura de venta:
        1. Comprueba si el producto tiene una receta asociada en la tabla `recipes`.
        2. **Caso A (Con Receta - Insumos)**: Si el producto está compuesto por insumos
           (ej: Capuchino compuesto por leche, café en grano, azúcar):
           - Calcula la cantidad total a descontar por insumo (`cantidad_receta * cantidad_vendida`).
           - Genera un movimiento de salida (OUT) en el Kárdex para cada insumo.
        3. **Caso B (Sin Receta - Venta Directa)**: Si no tiene receta (ej: Botella de agua, galleta empacada):
           - Genera un movimiento de salida (OUT) directo sobre el stock del producto vendido.
           
        :param db: Sesión de SQLAlchemy activa
        :param sale: Entidad de la venta completada
        """
        for detail in sale.details:
            product = db.get(Product, detail.product_id)
            if not product:
                continue

            # Buscar si el producto posee receta (Bill of Materials - BOM)
            recipe_items = db.execute(
                select(Recipe).where(Recipe.product_id == product.id)
            ).scalars().all()

            if recipe_items:
                # Caso A: El producto se descompone en ingredientes individuales
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
                        notes=f"Consumo por receta en venta de {product.name} (Factura {sale.invoice_number})"
                    )
            else:
                # Caso B: El producto se vende y descuenta directamente sin subcomponentes
                InventoryService.register_movement(
                    db=db,
                    product_id=product.id,
                    branch_id=sale.branch_id,
                    user_id=sale.user_id,
                    quantity=Decimal(detail.quantity),
                    type=MovementType.OUT,
                    reference_id=sale.id,
                    reference_type="Sale",
                    notes=f"Venta directa del producto (Factura {sale.invoice_number})"
                )
        
        db.commit()
