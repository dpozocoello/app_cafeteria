"""
Router: Mesas y Configuración de Servicio (Domicilio/Retiro)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.operations import Table, ServiceConfig
from ..schemas import TableCreate, TableUpdate, ServiceConfigUpdate
from decimal import Decimal

router = APIRouter(tags=["Operaciones"])

# ─── MESAS ────────────────────────────────────────────────────────────────────

@router.get("/api/tables")
def list_tables(db: Session = Depends(get_db)):
    return db.query(Table).order_by(Table.number).all()


@router.post("/api/tables", status_code=201)
def create_table(data: TableCreate, db: Session = Depends(get_db)):
    if db.query(Table).filter_by(number=data.number).first():
        raise HTTPException(status_code=400, detail=f"Mesa '{data.number}' ya existe")
    table = Table(number=data.number, capacity=data.capacity, zone=data.zone)
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


@router.put("/api/tables/{table_id}")
def update_table(table_id: int, data: TableUpdate, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    table.number = data.number
    table.capacity = data.capacity
    table.status = data.status
    table.zone = data.zone
    db.commit()
    db.refresh(table)
    return table


@router.delete("/api/tables/{table_id}", status_code=204)
def delete_table(table_id: int, db: Session = Depends(get_db)):
    table = db.get(Table, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    db.delete(table)
    db.commit()


# ─── CONFIGURACIÓN DE SERVICIO (DOMICILIO) ────────────────────────────────────

@router.get("/api/service-config")
def list_service_config(db: Session = Depends(get_db)):
    return db.query(ServiceConfig).all()


@router.put("/api/service-config/{service_type}")
def update_service_config(service_type: str, data: ServiceConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(ServiceConfig).filter_by(service_type=service_type.upper()).first()
    if not config:
        config = ServiceConfig(service_type=service_type.upper())
        db.add(config)
    config.is_active = data.is_active
    config.surcharge_percentage = data.surcharge_percentage
    config.base_factor = data.base_factor
    config.description = data.description
    db.commit()
    db.refresh(config)
    return config


@router.get("/api/service-config/calculate-surcharge")
def calculate_delivery_surcharge(subtotal: float, db: Session = Depends(get_db)):
    """
    Calcula el recargo de domicilio dado un subtotal.
    Fórmula: recargo = max(subtotal × porcentaje/100, factor_base)
    """
    config = db.query(ServiceConfig).filter_by(service_type="DOMICILIO", is_active=True).first()
    if not config:
        return {"surcharge": 0.0, "breakdown": "Servicio a domicilio no configurado"}

    percentage_amount = Decimal(str(subtotal)) * (Decimal(str(config.surcharge_percentage)) / 100)
    surcharge = max(percentage_amount, Decimal(str(config.base_factor)))

    return {
        "surcharge": float(surcharge),
        "breakdown": {
            "subtotal": subtotal,
            "percentage": float(config.surcharge_percentage),
            "percentage_amount": float(percentage_amount),
            "base_factor": float(config.base_factor),
            "applied": "porcentaje" if percentage_amount >= Decimal(str(config.base_factor)) else "factor_base"
        }
    }
