# Manual de Despliegue — YUQUI Sistema de Cafetería

**Versión:** 2.0  
**Plataforma:** Windows 10/11 · Ubuntu 20.04+

---

## Tabla de Contenidos

1. [Requisitos Previos](#1-requisitos-previos)
2. [Instalación en Windows](#2-instalación-en-windows)
3. [Instalación en Ubuntu / Linux](#3-instalación-en-ubuntu--linux)
4. [Configuración del Archivo .env](#4-configuración-del-archivo-env)
5. [Sistema de Licenciamiento](#5-sistema-de-licenciamiento)
6. [Operaciones Comunes](#6-operaciones-comunes)
7. [Solución de Problemas](#7-solución-de-problemas)

---

## 1. Requisitos Previos

| Componente | Versión mínima | Notas |
|---|---|---|
| Python | 3.10+ | Descargar desde python.org |
| pip | 22+ | Incluido con Python 3.10+ |
| RAM | 512 MB | 1 GB recomendado |
| Disco | 200 MB libres | + espacio para base de datos |

---

## 2. Instalación en Windows

### 2.1 Instalar Python

1. Descarga Python 3.10+ desde [python.org/downloads](https://python.org/downloads)
2. Ejecuta el instalador y **marca** la opción `Add Python to PATH`
3. Verifica la instalación abriendo PowerShell:
   ```powershell
   python --version
   pip --version
   ```

### 2.2 Descomprimir el paquete

1. Extrae `dist_package.zip` en la ubicación deseada, por ejemplo:
   ```
   C:\aplicaciones\yuqui\
   ```
2. Abre PowerShell en esa carpeta (clic derecho → *Abrir en Terminal*).

### 2.3 Crear entorno virtual e instalar dependencias

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell bloquea la ejecución de scripts, ejecuta antes:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 2.4 Configurar el archivo .env

```powershell
copy .env.example .env
notepad .env
```

Ajusta como mínimo `DB_ENGINE`, `SQLITE_PATH`, `BRAND_NAME` y `BRAND_TAGLINE`.  
Ver sección [4. Configuración del archivo .env](#4-configuración-del-archivo-env).

### 2.5 Iniciar la aplicación

Doble clic en **`iniciar_app.bat`**, o desde PowerShell:

```powershell
.\iniciar_app.bat
```

El script activa el entorno virtual, lanza Uvicorn en el puerto configurado y abre el navegador en `http://127.0.0.1:8000`.

### 2.6 Reiniciar la aplicación

```powershell
.\reiniciar.bat
```

### 2.7 Configurar inicio automático con Windows (opcional)

1. Abre el **Programador de tareas** (`taskschd.msc`).
2. Crea una tarea básica:
   - **Desencadenador:** Al iniciar sesión (o al iniciar el sistema)
   - **Acción:** Iniciar un programa → ruta completa a `iniciar_app.bat`
3. En *Condiciones*, desmarca *Iniciar la tarea solo si el equipo está conectado a corriente*.

### 2.8 Firewall de Windows

Si necesitas acceso desde otros equipos de la red local:

```powershell
# Ejecutar como Administrador
New-NetFirewallRule -DisplayName "YUQUI App" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Cambia el `APP_HOST` en `.env` de `127.0.0.1` a `0.0.0.0`.

---

## 3. Instalación en Ubuntu / Linux

### 3.1 Instalar dependencias del sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv python3-pip git unzip
```

### 3.2 Descomprimir el paquete

```bash
mkdir -p /opt/yuqui
unzip dist_package.zip -d /opt/yuqui
cd /opt/yuqui
```

### 3.3 Crear entorno virtual e instalar dependencias

```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.4 Configurar el archivo .env

```bash
cp .env.example .env
nano .env
```

### 3.5 Probar la aplicación manualmente

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Accede desde el navegador a `http://<IP_DEL_SERVIDOR>:8000`.

### 3.6 Configurar como servicio Systemd

Crea el archivo de servicio:

```bash
sudo nano /etc/systemd/system/coffeeapp.service
```

Contenido del archivo:

```ini
[Unit]
Description=YUQUI Cafeteria App
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/yuqui
EnvironmentFile=/opt/yuqui/.env
ExecStart=/opt/yuqui/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Habilitar e iniciar el servicio:

```bash
sudo systemctl daemon-reload
sudo systemctl enable coffeeapp
sudo systemctl start coffeeapp
sudo systemctl status coffeeapp
```

### 3.7 Ver logs en tiempo real

```bash
sudo journalctl -u coffeeapp -f
```

### 3.8 Firewall (UFW)

```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

### 3.9 Proxy inverso con Nginx (recomendado para producción)

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/yuqui
```

Contenido:

```nginx
server {
    listen 80;
    server_name tu_dominio.com;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/yuqui /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4. Configuración del Archivo .env

Copia `.env.example` como `.env` y ajusta las variables según tu entorno.

### Variables principales

```dotenv
# Base de datos
DB_ENGINE=sqlite           # sqlite | postgresql | mysql
SQLITE_PATH=./coffee_app_v2.db

# Identidad gráfica
BRAND_NAME=YUQUI - Piqueos & Cafeteria
BRAND_TAGLINE=Ecuatoriano de verdad

# Puerto de la aplicación
APP_PORT=8000
APP_HOST=127.0.0.1         # Cambiar a 0.0.0.0 para acceso en red

# Licenciamiento y período de prueba
TRIAL_DAYS=15              # Días de prueba (1–30). Valores >30 se limitan a 30.
INSTALLATION_DATE=         # Se registra automáticamente en el primer arranque.
                           # Formato YYYY-MM-DD. No modificar manualmente.
```

### Variables de base de datos PostgreSQL

```dotenv
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=coffeeapp
PG_USER=postgres
PG_PASSWORD=TU_CONTRASEÑA_SEGURA
```

---

## 5. Sistema de Licenciamiento

### 5.1 Período de prueba

- Al primer arranque, el sistema registra automáticamente `INSTALLATION_DATE` en `.env`.
- `TRIAL_DAYS` controla el período (por defecto **15 días**, máximo **30 días**).
- Durante el período de prueba el sistema opera con acceso completo.

### 5.2 Activación con clave de licencia

Cuando el período de prueba expira (o en cualquier momento), el sistema muestra la pantalla de activación en `/activate`.

1. Ingresa la clave de licencia comercial en el campo correspondiente.
2. El backend valida la clave **en memoria** — la clave en texto plano **nunca se guarda en disco**.
3. Si la clave es válida, el sistema escribe el hash de activación en el archivo `diedcomp` y desbloquea el acceso.

### 5.3 Archivo diedcomp

El archivo `diedcomp` en la raíz del proyecto contiene el hash SHA-256 de activación. Es el único registro persistente del estado de licencia. No debe ser modificado ni eliminado manualmente; si se corrompe, el sistema requerirá reactivación.

### 5.4 Flujo de estados

```
Primer arranque
    └── Registra INSTALLATION_DATE
        ├── Días transcurridos ≤ TRIAL_DAYS  → Acceso total (modo Trial)
        └── Días transcurridos > TRIAL_DAYS
              ├── diedcomp válido             → Acceso total (Activado)
              └── diedcomp ausente/inválido   → Redirige a /activate
```

---

## 6. Operaciones Comunes

### Cambiar puerto de la aplicación

Edita `.env`:
```dotenv
APP_PORT=8080
```
Reinicia la aplicación.

### Migrar de SQLite a PostgreSQL

1. Instala el driver:
   ```bash
   pip install psycopg2-binary
   ```
2. Crea la base de datos en PostgreSQL.
3. Actualiza `.env`:
   ```dotenv
   DB_ENGINE=postgresql
   PG_HOST=localhost
   PG_DATABASE=coffeeapp
   PG_USER=postgres
   PG_PASSWORD=secreto
   ```
4. Reinicia la aplicación — las tablas se crean automáticamente.

### Hacer respaldo de la base de datos SQLite

```powershell
# Windows
copy coffee_app_v2.db "backup\coffee_app_v2_%date:~-4,4%%date:~-7,2%%date:~-10,2%.db"
```

```bash
# Linux
cp coffee_app_v2.db "backup/coffee_app_v2_$(date +%Y%m%d).db"
```

---

## 7. Solución de Problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError` | Entorno virtual no activo | Activa el entorno con `venv\Scripts\activate` (Win) o `source venv/bin/activate` (Linux) |
| Puerto 8000 ocupado | Otro proceso usa el puerto | Cambia `APP_PORT` en `.env` o detén el proceso: `netstat -ano \| findstr 8000` (Win) |
| El sistema redirige siempre a `/activate` | `diedcomp` ausente y trial expirado | Ingresa la clave de licencia en `/activate` |
| `OperationalError: no such table` | Base de datos no inicializada | Reinicia la app; las tablas se crean al arrancar |
| Pantalla en blanco en el navegador | Archivos estáticos no encontrados | Verifica que la carpeta `app/static/` exista y que `APP_HOST` sea accesible |
| Servicio systemd no inicia | Error en `.env` o permisos | Revisa `journalctl -u coffeeapp -n 50 --no-pager` |
