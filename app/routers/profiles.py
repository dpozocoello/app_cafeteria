"""
Router: Perfiles y Roles RBAC
Gestión completa de roles con permisos granulares para una cafetería.
Incluye roles predefinidos para el negocio.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models.core import Role, User, AuditLog
from ..services.auth_service import log_action

router = APIRouter(prefix="/api/roles", tags=["Perfiles y Roles"])


# ─── Roles predefinidos para una Cafetería ────────────────────────────────────
COFFEE_SHOP_PROFILES = [
    {
        "name": "Administrador",
        "description": "Acceso total al sistema. Control de usuarios, configuración, reportes y operación.",
        "permissions": {
            "dashboard": True, "ventas": True, "inventario": True, "recetas": True,
            "menus": True, "gastos": True, "usuarios": True, "reportes": True,
            "config": True, "auditoria": True, "pedidos": True, "comandas": True,
            "migracion": True
        }
    },
    {
        "name": "Gerente de Turno",
        "description": "Supervisión operativa. Ve reportes, aprueba descuentos y gestiona el turno.",
        "permissions": {
            "dashboard": True, "ventas": True, "inventario": True, "recetas": True,
            "menus": True, "gastos": True, "usuarios": False, "reportes": True,
            "config": False, "auditoria": True, "pedidos": True, "comandas": True,
            "migracion": False
        }
    },
    {
        "name": "Barista/Cajero",
        "description": "Operación de caja y preparación. Acceso a POS, pedidos y comandas.",
        "permissions": {
            "dashboard": True, "ventas": True, "inventario": False, "recetas": True,
            "menus": False, "gastos": False, "usuarios": False, "reportes": False,
            "config": False, "auditoria": False, "pedidos": True, "comandas": True,
            "migracion": False
        }
    },
    {
        "name": "Mesero",
        "description": "Toma de pedidos en mesa. Acceso al módulo de pedidos y comandas.",
        "permissions": {
            "dashboard": False, "ventas": False, "inventario": False, "recetas": False,
            "menus": False, "gastos": False, "usuarios": False, "reportes": False,
            "config": False, "auditoria": False, "pedidos": True, "comandas": True,
            "migracion": False
        }
    },
    {
        "name": "Cocinero",
        "description": "Visualización de comandas y recetas. Solo puede ver los pedidos en cocina.",
        "permissions": {
            "dashboard": False, "ventas": False, "inventario": True, "recetas": True,
            "menus": False, "gastos": False, "usuarios": False, "reportes": False,
            "config": False, "auditoria": False, "pedidos": False, "comandas": True,
            "migracion": False
        }
    },
    {
        "name": "Auditor",
        "description": "Solo lectura. Acceso a reportes, auditoría y dashboard sin modificar datos.",
        "permissions": {
            "dashboard": True, "ventas": False, "inventario": False, "recetas": False,
            "menus": False, "gastos": False, "usuarios": False, "reportes": True,
            "config": False, "auditoria": True, "pedidos": False, "comandas": False,
            "migracion": False
        }
    },
]


# ─── Schemas ──────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: dict = {}


class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[dict] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
def list_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    result = []
    for r in roles:
        user_count = db.query(User).filter_by(role_id=r.id, is_active=True).count()
        result.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permissions": r.permissions or {},
            "active_users": user_count,
        })
    return result


@router.get("/templates")
def get_profile_templates():
    """Retorna los perfiles predefinidos para un negocio de cafetería."""
    return COFFEE_SHOP_PROFILES


@router.post("", status_code=201)
def create_role(data: RoleCreate, db: Session = Depends(get_db)):
    if db.query(Role).filter_by(name=data.name).first():
        raise HTTPException(status_code=400, detail=f"El rol '{data.name}' ya existe")
    role = Role(name=data.name, description=data.description, permissions=data.permissions)
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"id": role.id, "name": role.name, "message": "Rol creado"}


@router.put("/{role_id}")
def update_role(role_id: int, data: RoleUpdate, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions
    db.commit()
    return {"message": "Rol actualizado"}


@router.delete("/{role_id}", status_code=204)
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
    if db.query(User).filter_by(role_id=role_id).count() > 0:
        raise HTTPException(status_code=400, detail="No se puede eliminar: hay usuarios asignados a este rol")
    db.delete(role)
    db.commit()


@router.post("/initialize-coffee-shop")
def initialize_coffee_shop_profiles(db: Session = Depends(get_db)):
    """Inicializa o actualiza todos los perfiles predefinidos para cafetería."""
    created, updated = 0, 0
    for profile in COFFEE_SHOP_PROFILES:
        existing = db.query(Role).filter_by(name=profile["name"]).first()
        if existing:
            existing.description = profile["description"]
            existing.permissions  = profile["permissions"]
            updated += 1
        else:
            db.add(Role(name=profile["name"], description=profile["description"],
                        permissions=profile["permissions"]))
            created += 1
    db.commit()
    return {"message": f"Perfiles inicializados: {created} creados, {updated} actualizados"}
