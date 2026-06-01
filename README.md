# Sistema POS - Sistema de Gestión y Facturación Electrónica

Sistema POS es un sistema moderno e intuitivo de punto de venta (POS) y facturación para negocios y restaurantes, integrado con los requerimientos tributarios del **Servicio de Rentas Internas (SRI) de Ecuador** (XML de comprobantes v1.1.0) y diseñado bajo altos estándares de seguridad (controles **ISO 27001**) y protección de datos (**LOPDP Ecuador / GDPR**).

## 🚀 Inicio Rápido

### Requisitos Previos
- Python 3.10 o superior instalado.
- Base de datos SQLite (incluida por defecto para desarrollo) o Postgres/MySQL instalada.

### Instalación en Entorno Local
1. Instalar las dependencias de Python:
   ```bash
   pip install -r requirements.txt
   ```
2. Configurar las variables de entorno:
   - Copia `.env.example` a `.env` y edita los parámetros según tu entorno local (Base de datos, tokens de marca, tipografía).
3. Levantar la aplicación:
   - Haz doble clic en `iniciar_app.bat` o ejecuta:
     ```bash
     uvicorn app.main:app --reload --port 8000
     ```
   - Abre tu navegador en [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## 📖 Documentación del Proyecto

Para desarrolladores y técnicos que deseen comprender el diseño del sistema, extender las tablas de la base de datos o agregar nuevos endpoints, disponemos de una guía detallada en el archivo:

👉 **[DOCUMENTACION_TECNICA.md](DOCUMENTACION_TECNICA.md)**

### Contenidos de la Documentación Técnica:
- **Diagrama de Componentes**: Arquitectura física y capas de software.
- **Diagrama de Módulos**: Estructura de carpetas y dependencias de importación.
- **Diagrama de Casos de Uso**: Actores y flujos de negocio de la cafetería.
- **Modelo Entidad-Relación (ERD)**: Tablas, claves primarias/foráneas y cardinalidad en Mermaid.
- **Detalle de Algoritmos**: Generación de Claves SRI de 49 dígitos, cálculo de Módulo 11 y Kárdex automatizado por recetas (BOM).
- **Guía de Onboarding**: Paso a paso de cómo extender el código (agregar endpoints, routers y tablas).