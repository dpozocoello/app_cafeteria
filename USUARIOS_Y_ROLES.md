# Listado de Usuarios, Roles y Credenciales del Sistema

Este documento contiene la relación de usuarios, credenciales de acceso predeterminadas y roles configurados en la plataforma POS de Cafetería.

---

## 1. Credenciales de Acceso

| ID | Usuario (`username`) | Contraseña Inicial | Nombre Completo | Correo Electrónico | Rol | Estado |
| :---: | :--- | :--- | :--- | :--- | :---: | :---: |
| **1** | `admin` | `admin123$` | Administrador del Sistema | `admin@pos.com` | **Administrador** | Activo ✅ |
| **2** | `mesero1` | `Mesero1#2026` | Carlos Mendoza | `mesero1@cafeteria.com` | **Mesero** | Activo ✅ |
| **3** | `mesero2` | `Mesero2#2026` | Ana Lopez | `mesero2@cafeteria.com` | **Mesero** | Activo ✅ |

> [!NOTE]
> Las contraseñas están almacenadas en la base de datos con cifrado robusto **bcrypt** (costo=12) de acuerdo con las normativas ISO 27001.

---

## 2. Catálogo de Roles y Privilegios

| ID | Rol | Descripción | Permisos Asignados |
| :---: | :--- | :--- | :--- |
| **1** | **Administrador** | Acceso total al sistema, reportería fiscal, gestión de usuarios y parámetros globales. | • Ventas: ✅<br>• Inventario: ✅<br>• Recetas: ✅<br>• Menús: ✅<br>• Gastos: ✅<br>• Usuarios: ✅<br>• Reportes: ✅<br>• Configuración: ✅ |
| **2** | **Control** | Supervisión de operación diaria, inventario, recetas y ventas. | • Ventas: ✅<br>• Inventario: ✅<br>• Recetas: ✅<br>• Menús: ✅<br>• Gastos: ✅<br>• Usuarios: ❌<br>• Reportes: ✅<br>• Configuración: ❌ |
| **3** | **Soporte** | Asistencia técnica y resolución de incidentes en facturación y caja. | • Ventas: ✅<br>• Inventario: ❌<br>• Recetas: ❌<br>• Menús: ❌<br>• Gastos: ❌<br>• Usuarios: ❌<br>• Reportes: ❌<br>• Configuración: ❌ |
| **4** | **Mesero** | Toma de pedidos por mesa y despacho en comanda digital (KDS / Móvil). | Rol operativo asignado para terminales portátiles y aplicación de meseros. |

---

## 3. Matriz de Acceso por Módulos y Funcionalidades

| Módulo / Funcionalidad | Administrador | Control | Soporte | Mesero |
| :--- | :---: | :---: | :---: | :---: |
| **Punto de Venta (POS Facturación)** | ✅ | ✅ | ✅ | ❌ |
| **Toma de Pedidos (Mesero / Móvil)** | ✅ | ✅ | ❌ | ✅ |
| **Cocina / Comandas (KDS)** | ✅ | ✅ | ✅ | ✅ (Solo vista) |
| **Control de Caja (Apertura / Arqueo / Cierre)** | ✅ | ✅ | ❌ | ❌ |
| **Inventario y Kárdex** | ✅ | ✅ | ❌ | ❌ |
| **Recetas e Insumos** | ✅ | ✅ | ❌ | ❌ |
| **Menús y Precios** | ✅ | ✅ | ❌ | ❌ |
| **Bancos y Conciliación NIC 7** | ✅ | ❌ | ❌ | ❌ |
| **Contabilidad NIIF y Asientos** | ✅ | ❌ | ❌ | ❌ |
| **Gestión de Usuarios y Perfiles** | ✅ | ❌ | ❌ | ❌ |
| **Configuración General y Parámetros SRI** | ✅ | ❌ | ❌ | ❌ |

---

## 4. URLs de Acceso Rápido

- **Login / Inicio de Sesión:** [http://127.0.0.1:8000/login](http://127.0.0.1:8000/login)
- **Punto de Venta / Facturación (POS):** [http://127.0.0.1:8000/pos](http://127.0.0.1:8000/pos)
- **Toma de Pedidos (Meseros):** [http://127.0.0.1:8000/pedidos](http://127.0.0.1:8000/pedidos)
- **Pantalla de Cocina / Comandas (KDS):** [http://127.0.0.1:8000/comandas](http://127.0.0.1:8000/comandas)
- **Control de Caja:** [http://127.0.0.1:8000/caja](http://127.0.0.1:8000/caja)
- **Gestión de Usuarios y Perfiles:** [http://127.0.0.1:8000/admin/profiles](http://127.0.0.1:8000/admin/profiles)
