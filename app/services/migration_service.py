"""
Servicio de Migración entre Motores de Base de Datos
Permite mover datos de SQLite → PostgreSQL, MySQL y viceversa.
"""
from typing import Optional
from sqlalchemy import create_engine, inspect, text, MetaData, Table
from sqlalchemy.orm import Session
from datetime import datetime


# Tablas a migrar (en orden de dependencias FK)
MIGRATION_ORDER = [
    "companies", "branches", "emission_points", "roles", "security_policies",
    "users", "password_history",
    "products", "recipes", "recipe_lines",
    "menus", "menu_items",
    "tables", "service_configs",
    "expense_categories", "expenses",
    "tax_parameters", "payment_methods",
    "sales", "sale_details", "sale_payments",
    "audit_logs",
]


def build_url(config: dict) -> str:
    engine = config.get("engine", "sqlite").lower()
    if engine == "sqlite":
        return f"sqlite:///{config.get('path', './coffee_app_v2.db')}"
    elif engine == "postgresql":
        u, p = config["user"], config["password"]
        h, port, db = config["host"], config.get("port", 5432), config["database"]
        return f"postgresql://{u}:{p}@{h}:{port}/{db}"
    elif engine == "mysql":
        u, p = config["user"], config["password"]
        h, port, db = config["host"], config.get("port", 3306), config["database"]
        return f"mysql+pymysql://{u}:{p}@{h}:{port}/{db}"
    raise ValueError(f"Motor desconocido: {engine}")


def test_connection(config: dict) -> dict:
    try:
        url = build_url(config)
        extras = {}
        if "sqlite" in url:
            extras["connect_args"] = {"check_same_thread": False}
        eng = create_engine(url, **extras)
        with eng.connect() as conn:
            if "postgresql" in url:
                v = conn.execute(text("SELECT version()")).scalar()
            elif "mysql" in url:
                v = conn.execute(text("SELECT VERSION()")).scalar()
            else:
                v = conn.execute(text("SELECT sqlite_version()")).scalar()
        return {"ok": True, "version": str(v), "engine": config["engine"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def migrate_data(source_config: dict, dest_config: dict,
                 on_progress=None) -> dict:
    """
    Migra todos los datos de la fuente al destino.
    on_progress(table, rows) se llama por cada tabla procesada.
    """
    results = {"tables": {}, "errors": [], "started_at": datetime.utcnow().isoformat()}

    # Conectar fuente
    src_url = build_url(source_config)
    src_extras = {"connect_args": {"check_same_thread": False}} if "sqlite" in src_url else {}
    src_eng = create_engine(src_url, **src_extras)

    # Conectar destino
    dst_url = build_url(dest_config)
    dst_extras = {"connect_args": {"check_same_thread": False}} if "sqlite" in dst_url else {}
    dst_eng = create_engine(dst_url, **dst_extras)

    # Crear tablas en destino usando metadata de la app
    from ..models.core import Base as CoreBase
    from ..models.sales import Sale  # noqa – triggers all models
    from ..models.inventory import Product
    from ..models.operations import Menu
    from ..models.expenses import Expense

    CoreBase.metadata.create_all(bind=dst_eng)

    src_inspector = inspect(src_eng)
    available_tables = src_inspector.get_table_names()

    with src_eng.connect() as src_conn, dst_eng.connect() as dst_conn:
        for table_name in MIGRATION_ORDER:
            if table_name not in available_tables:
                results["tables"][table_name] = {"skipped": True, "reason": "no existe en fuente"}
                continue
            try:
                # Leer todas las filas de la fuente
                rows = src_conn.execute(text(f"SELECT * FROM {table_name}")).mappings().all()
                if not rows:
                    results["tables"][table_name] = {"rows": 0}
                    continue

                # Limpiar destino y reinsertar
                dst_conn.execute(text(f"DELETE FROM {table_name}"))

                # Insertar en lotes de 500
                rows_list = [dict(r) for r in rows]
                meta = MetaData()
                meta.reflect(bind=dst_eng, only=[table_name])
                dst_table = meta.tables[table_name]

                for i in range(0, len(rows_list), 500):
                    batch = rows_list[i:i+500]
                    dst_conn.execute(dst_table.insert(), batch)

                dst_conn.commit()
                results["tables"][table_name] = {"rows": len(rows_list)}
                if on_progress:
                    on_progress(table_name, len(rows_list))

            except Exception as e:
                results["errors"].append({"table": table_name, "error": str(e)})
                results["tables"][table_name] = {"error": str(e)}

    results["finished_at"] = datetime.utcnow().isoformat()
    results["total_tables"] = len([v for v in results["tables"].values() if "rows" in v])
    results["total_rows"] = sum(v.get("rows", 0) for v in results["tables"].values())
    return results
