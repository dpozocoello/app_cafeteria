from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


# ─── Inventario ───────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    unit: str
    menu_category: Optional[str] = None
    cost_price: Decimal = Decimal(0)
    sale_price: Decimal = Decimal(0)
    is_ready_to_sell: bool = True
    is_ingredient: bool = False
    min_stock: Decimal = Decimal(0)


class ProductUpdate(ProductCreate):
    pass


# ─── Recetas ──────────────────────────────────────────────────────────────────

class RecipeLineCreate(BaseModel):
    ingredient_id: int
    quantity: Decimal


class RecipeCreate(BaseModel):
    product_id: int
    ingredients: List[RecipeLineCreate]


# ─── Menús ────────────────────────────────────────────────────────────────────

class MenuCreate(BaseModel):
    name: str
    description: Optional[str] = None
    product_ids: List[int] = []


class MenuUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    product_ids: List[int] = []


# ─── Mesas ────────────────────────────────────────────────────────────────────

class TableCreate(BaseModel):
    number: str
    capacity: int = 4
    zone: Optional[str] = None


class TableUpdate(BaseModel):
    number: str
    capacity: int
    status: str
    zone: Optional[str] = None


# ─── Configuración de Servicio ────────────────────────────────────────────────

class ServiceConfigUpdate(BaseModel):
    service_type: str
    is_active: bool
    surcharge_percentage: Decimal
    base_factor: Decimal
    description: Optional[str] = None


# ─── Ventas (actualizado) ─────────────────────────────────────────────────────

class SaleDetailCreate(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal(0)


class SaleCreate(BaseModel):
    customer_name: str = "CONSUMIDOR FINAL"
    customer_id: str = "9999999999999"
    customer_id_type: str = "07"
    details: List[SaleDetailCreate]
    payment_method_id: int
    branch_id: int
    user_id: int
    emission_point_id: Optional[int] = None
    consumption_type: str = "MESA"   # MESA | LLEVAR | DOMICILIO
    table_id: Optional[int] = None
    delivery_address: Optional[str] = None
    # Retenciones
    withholding_number: Optional[str] = None
    withholding_iva: Optional[Decimal] = Decimal(0)
    withholding_renta: Optional[Decimal] = Decimal(0)


class SaleResponse(BaseModel):
    id: int
    access_key: Optional[str]
    invoice_number: str
    total: Decimal
    delivery_surcharge: Decimal
    sri_status: str

    class Config:
        from_attributes = True


class CreditNoteCreate(BaseModel):
    sale_id: int
    reason: str
    emission_point_id: int


class CreditNoteResponse(BaseModel):
    id: int
    credit_note_number: str
    access_key: str
    reason: str
    sri_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    category_id: int
    branch_id: int
    user_id: int
    provider_name: str
    description: str
    amount: Decimal
    tax_amount: Decimal = Decimal(0)
    invoice_reference: Optional[str] = None
