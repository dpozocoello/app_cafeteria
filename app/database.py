from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import get_database_url, get_engine_type

def build_engine():
    url = get_database_url()
    engine_type = get_engine_type()
    kwargs = {}
    if engine_type == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)

engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
DATABASE_URL = get_database_url()  # Disponible para tareas en background

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
