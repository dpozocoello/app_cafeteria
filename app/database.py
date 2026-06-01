"""
Configuración de la Base de Datos con SQLAlchemy.

Este módulo gestiona la inicialización de motores de base de datos (SQLite, PostgreSQL, MySQL)
y expone una función generadora de sesiones para su inyección de dependencias en FastAPI.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from .config import get_database_url, get_engine_type

def build_engine():
    """
    Construye y retorna el motor de SQLAlchemy (Engine) basado en la configuración activa.
    
    Admite motores SQLite (desarrollo), PostgreSQL y MySQL (producción). Si se detecta
    SQLite, habilita argumentos de conexión específicos para evitar conflictos de hilos.
    
    :return: Instancia de sqlalchemy.engine.Engine
    """
    url = get_database_url()
    engine_type = get_engine_type()
    kwargs = {}
    if engine_type == "sqlite":
        # SQLite requiere check_same_thread=False para permitir que múltiples
        # hilos de FastAPI accedan al mismo archivo de base de datos de manera concurrente.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)

# Motor centralizado de conexión
engine = build_engine()

# Creador de sesiones SQLAlchemy preconfigurado
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# URL expuesta para scripts externos o tareas asíncronas en segundo plano
DATABASE_URL = get_database_url()

def get_db() -> Generator[Session, None, None]:
    """
    Generador de sesión de base de datos (Database Session Lifecycle Generator).
    
    Diseñado para usarse como una dependencia de FastAPI (Depends(get_db)).
    Asegura que cada solicitud HTTP obtenga una sesión limpia de base de datos
    y garantiza el cierre de la sesión de manera segura una vez procesada la petición.
    
    :yield: Session - Sesión activa de SQLAlchemy
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

