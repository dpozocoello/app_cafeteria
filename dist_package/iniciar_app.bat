@echo off
echo ===================================================
echo   Iniciando Sistema POS - Facturacion y Ventas
echo ===================================================

:: Verificar si existe el entorno virtual (opcional)
if exist venv (
    echo [1/3] Activando entorno virtual...
    call venv\Scripts\activate
) else (
    echo [1/3] No se detecto venv, procediendo con python global...
)

:: Inicializar Base de Datos (solo crea tablas y datos base si no existen)
echo [2/3] Verificando Base de Datos y Datos Base...
python scripts/init_db.py

:: Iniciar Servidor FastAPI
echo [3/3] Iniciando Servidor API en http://127.0.0.1:8000
echo.
echo Para ver la documentacion interactiva: http://127.0.0.1:8000/docs
echo Para detener el servidor: Presione Ctrl+C
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause
