"""
Script de empaquetado para distribución del Sistema POS.

Crea dist_package/ con una copia limpia del proyecto y genera dist_package.zip.
Excluye: __pycache__, .git, base de datos SQLite, diedcomp, archivos temporales.

Uso:
    python scripts/build_package.py
"""

import shutil
import zipfile
from pathlib import Path

# ─── Configuración ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "dist_package"
OUTPUT_ZIP = ROOT / "dist_package.zip"

# Carpetas y archivos a incluir (rutas relativas a ROOT)
INCLUDE_DIRS = [
    "app",
    "scripts",
]

INCLUDE_FILES = [
    "requirements.txt",
    ".env.example",
    "iniciar_app.bat",
    "reiniciar.bat",
    "MANUAL_DESPLIEGUE.md",
]

# Patrones a excluir en cualquier nivel de la ruta
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".git",
    ".env",
    "diedcomp",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.pyc",
    "*.pyo",
    "*.log",
    "dist_package",
    "dist_package.zip",
    ".DS_Store",
    "Thumbs.db",
]

# ─── Helpers ───────────────────────────────────────────────────────────────────

def should_exclude(path: Path) -> bool:
    for part in path.parts:
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*"):
                if part.endswith(pattern[1:]):
                    return True
            elif part == pattern:
                return True
    return False


def copy_tree(src: Path, dst: Path):
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if should_exclude(rel) or should_exclude(item.relative_to(ROOT)):
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def zip_directory(source: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in source.rglob("*"):
            if item.is_file():
                arcname = item.relative_to(source.parent)
                zf.write(item, arcname)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  SISTEMA POS — Generador de Paquete de Distribución")
    print("=" * 60)

    # Limpiar salida previa
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print(f"[+] Carpeta existente eliminada: {OUTPUT_DIR.name}/")
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()
        print(f"[+] ZIP existente eliminado: {OUTPUT_ZIP.name}")

    OUTPUT_DIR.mkdir(parents=True)
    print(f"[+] Carpeta de salida creada: {OUTPUT_DIR.name}/\n")

    # Copiar carpetas
    for dir_name in INCLUDE_DIRS:
        src = ROOT / dir_name
        if not src.exists():
            print(f"[!] Carpeta no encontrada, omitida: {dir_name}/")
            continue
        dst = OUTPUT_DIR / dir_name
        copy_tree(src, dst)
        print(f"[✓] Carpeta copiada: {dir_name}/")

    # Copiar archivos raíz
    for file_name in INCLUDE_FILES:
        src = ROOT / file_name
        if not src.exists():
            print(f"[!] Archivo no encontrado, omitido: {file_name}")
            continue
        shutil.copy2(src, OUTPUT_DIR / file_name)
        print(f"[✓] Archivo copiado: {file_name}")

    # Generar ZIP
    print("\n[~] Generando ZIP...")
    zip_directory(OUTPUT_DIR, OUTPUT_ZIP)

    # Estadísticas
    zip_size_kb = OUTPUT_ZIP.stat().st_size / 1024
    file_count = sum(1 for _ in OUTPUT_DIR.rglob("*") if _.is_file())

    print(f"\n{'=' * 60}")
    print(f"  Paquete generado exitosamente")
    print(f"  Archivos incluidos : {file_count}")
    print(f"  Tamaño ZIP         : {zip_size_kb:.1f} KB")
    print(f"  Ubicación          : {OUTPUT_ZIP}")
    print("=" * 60)


if __name__ == "__main__":
    main()
