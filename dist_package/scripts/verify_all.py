import sys, os
sys.path.insert(0, '.')

print("=== Verificación del sistema ===")

from app.routers import menus, qr
print("[OK] menus router")
print("[OK] qr router")

fonts = [f for f in os.listdir('app/static/fonts') if f.endswith('.woff2')]
print(f"[OK] Fuentes locales: {fonts}")

os.makedirs('app/static/dishes', exist_ok=True)
print("[OK] Directorio dishes listo")

import app.main as m
print(f"[OK] main.py: {len(m.app.routes)} rutas registradas")
print("=== Todo OK ===")
