"""
Router: Migración entre Bases de Datos
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import os

from ..services.migration_service import test_connection, migrate_data

router = APIRouter(prefix="/api/migration", tags=["Migración de BD"])


class DbConfig(BaseModel):
    engine: str = "sqlite"
    path: Optional[str] = "./pos_app.db"      # SQLite
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    database: Optional[str] = "pos_app"
    user: Optional[str] = None
    password: Optional[str] = None


class MigrationRequest(BaseModel):
    source: DbConfig
    destination: DbConfig


@router.post("/test-source")
def test_source(config: DbConfig):
    return test_connection(config.model_dump(exclude_none=True))


@router.post("/test-destination")
def test_destination(config: DbConfig):
    return test_connection(config.model_dump(exclude_none=True))


@router.post("/start")
def start_migration(req: MigrationRequest):
    """Ejecuta la migración completa de source → destination."""
    # Validar conexiones
    src_test = test_connection(req.source.model_dump(exclude_none=True))
    if not src_test["ok"]:
        raise HTTPException(status_code=400, detail=f"Error en fuente: {src_test['error']}")

    dst_test = test_connection(req.destination.model_dump(exclude_none=True))
    if not dst_test["ok"]:
        raise HTTPException(status_code=400, detail=f"Error en destino: {dst_test['error']}")

    result = migrate_data(
        req.source.model_dump(exclude_none=True),
        req.destination.model_dump(exclude_none=True)
    )
    return result


@router.get("/page", response_class=HTMLResponse)
def get_migration_page():
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin_migration.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()
