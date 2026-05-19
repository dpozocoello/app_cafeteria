@echo off
title CoffeeApp - Reiniciar Plataforma
color 0A
cls

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║         COFFEEAPP - REINICIO DEL SISTEMA     ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── 1. Detener proceso existente en puerto 8000 ────────────────────────────
echo  [1/4] Deteniendo servidor anterior...
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo       Terminando proceso PID %%p
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo       Listo.

:: ── 2. Verificar que Python y uvicorn estén disponibles ───────────────────
echo.
echo  [2/4] Verificando entorno...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python no encontrado. Asegurese de que Python este en el PATH.
    pause
    exit /b 1
)
echo       Python OK.

:: ── 3. Iniciar el servidor en segundo plano ────────────────────────────────
echo.
echo  [3/4] Iniciando servidor CoffeeApp...
cd /d "C:\applications\app_cafeteria"
start "" /MIN python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

:: ── 4. Esperar y abrir navegador ──────────────────────────────────────────
echo.
echo  [4/4] Esperando que el servidor arranque...
timeout /t 4 /nobreak >nul

:: Verificar que el servidor respondió
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/'); print('OK')" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [AVISO] El servidor puede tardar un poco mas. Abriendo navegador de todas formas...
) else (
    echo       Servidor respondiendo correctamente.
)

:: Abrir navegador
start http://127.0.0.1:8000/

echo.
echo  ══════════════════════════════════════════════
echo   CoffeeApp corriendo en: http://127.0.0.1:8000
echo   Para detener: cierre la ventana del servidor
echo  ══════════════════════════════════════════════
echo.
echo  Presione cualquier tecla para cerrar esta ventana...
pause >nul
