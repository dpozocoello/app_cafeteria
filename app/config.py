"""
Módulo de configuración central de Sistema POS.
Lee el archivo .env y construye la URL de base de datos apropiada.
"""
import os
from pathlib import Path
from functools import lru_cache

BASE_DIR = Path(__file__).parent.parent  # Raíz del proyecto

# Carga manual del .env (sin dependencia de python-dotenv)
def _load_env():
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return {}
    values = {}
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values

_env = _load_env()

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, _env.get(key, default))


# ─── Base de Datos ────────────────────────────────────────────────────────────

def get_database_url() -> str:
    engine = _get("DB_ENGINE", "sqlite").lower()

    if engine == "postgresql":
        return (
            f"postgresql://{_get('PG_USER','postgres')}:{_get('PG_PASSWORD','secret')}"
            f"@{_get('PG_HOST','localhost')}:{_get('PG_PORT','5432')}"
            f"/{_get('PG_DATABASE','pos_app')}"
        )
    elif engine == "mysql":
        return (
            f"mysql+pymysql://{_get('MYSQL_USER','root')}:{_get('MYSQL_PASSWORD','secret')}"
            f"@{_get('MYSQL_HOST','localhost')}:{_get('MYSQL_PORT','3306')}"
            f"/{_get('MYSQL_DATABASE','pos_app')}"
        )
    else:  # sqlite (default)
        sqlite_path = _get("SQLITE_PATH", "./pos_app.db")
        return f"sqlite:///{sqlite_path}"


def get_engine_type() -> str:
    return _get("DB_ENGINE", "sqlite").lower()


# ─── Identidad Gráfica (Design Tokens) ────────────────────────────────────────

@lru_cache(maxsize=1)
def get_theme() -> dict:
    return {
        "brand_name":   _get("BRAND_NAME", "Sistema POS"),
        "brand_tagline": _get("BRAND_TAGLINE", "Sistema de Gestión"),
        "font_family":  _get("FONT_FAMILY", "Outfit"),
        "color_bg":     _get("COLOR_BG", "#020617"),
        "color_sidebar": _get("COLOR_SIDEBAR", "#0f172a"),
        "color_card":   _get("COLOR_CARD", "rgba(30,41,59,0.5)"),
        "color_accent": _get("COLOR_ACCENT", "#fbbf24"),
        "color_text":   _get("COLOR_TEXT", "#f8fafc"),
        "color_muted":  _get("COLOR_MUTED", "#94a3b8"),
        "color_success": _get("COLOR_SUCCESS", "#10b981"),
        "color_danger": _get("COLOR_DANGER", "#ef4444"),
        "brand_personality": _get("BRAND_PERSONALITY", "Joven, orgulloso, directo, auténtico, viral"),
        "brand_visuals":     _get("BRAND_VISUALS", "Icono estilizado pan de yuca, tipografía fuerte, fotografía de producto"),
        "brand_packaging":   _get("BRAND_PACKAGING", "Funda Ziploc con logo impreso, sticker circular negro/amarillo, QR de Instagram"),
        "brand_tone":        _get("BRAND_TONE", "Pan de yuca como lo hacía la abuela. Ahora con entrega a domicilio."),
        "brand_channels":    _get("BRAND_CHANNELS", "Instagram, TikTok, apps de delivery, markets modernos, ferias gastronómicas"),
    }


def refresh_theme():
    """Invalida el caché de tema para releer el .env."""
    get_theme.cache_clear()
    global _env
    _env = _load_env()


def save_env_values(updates: dict):
    """Escribe/actualiza valores en el archivo .env."""
    env_file = BASE_DIR / ".env"
    existing = {}
    lines = []

    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, _, _ = stripped.partition("=")
                    existing[key.strip()] = len(lines)
                lines.append(line.rstrip())

    for key, value in updates.items():
        if key in existing:
            lines[existing[key]] = f"{key}={value}"
        else:
            lines.append(f"{key}={value}")

    with open(env_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    refresh_theme()
