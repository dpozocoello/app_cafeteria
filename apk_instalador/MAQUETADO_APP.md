# Maquetado — Cafetería POS · Módulo Mesero Android

> Versión 2.0 · Material Design 3 · API 26+ · Kotlin

---

## 1. Sistema de Diseño

### 1.1 Paleta de Colores

| Token              | Hex       | Uso                              |
|--------------------|-----------|----------------------------------|
| `primary`          | `#1a56db` | Botones principales, iconos clave|
| `primary_dark`     | `#1341b0` | Toolbar, status bar              |
| `primary_container`| `#dbeafe` | Chips seleccionados, badges      |
| `secondary`        | `#0e9f6e` | Acciones secundarias, éxito      |
| `background`       | `#f3f4f6` | Fondo general de pantallas       |
| `surface`          | `#ffffff` | Cards, barras, dialogs           |
| `error`            | `#dc2626` | Errores, mesas ocupadas          |
| `warning`          | `#d97706` | Advertencias, mesas reservadas   |
| `text_primary`     | `#111827` | Texto principal                  |
| `text_secondary`   | `#6b7280` | Subtítulos, metadatos            |
| `divider`          | `#e5e7eb` | Líneas divisoras                 |

#### Estados de Pedidos

| Estado              | Color Texto | Color Fondo | Significado          |
|---------------------|-------------|-------------|----------------------|
| `PENDIENTE`         | `#92400e`   | `#fef3c7`   | Recibido, sin iniciar|
| `PREPARANDO`        | `#9a3412`   | `#ffedd5`   | En cocina            |
| `LISTO_FACTURAR`    | `#065f46`   | `#d1fae5`   | Listo para cobrar    |
| `FACTURADO`         | `#374151`   | `#f3f4f6`   | Completado           |

#### Estados de Mesas

| Estado      | Fondo Card  | Texto estado | Acción     |
|-------------|-------------|--------------|------------|
| `LIBRE`     | `#d1fae5`   | `#065f46`    | Seleccionable|
| `OCUPADA`   | `#fee2e2`   | `#991b1b`    | Bloqueada  |
| `RESERVADA` | `#fef3c7`   | `#92400e`    | Bloqueada  |

### 1.2 Tipografía

| Rol              | Tamaño | Estilo    | Uso                      |
|------------------|--------|-----------|--------------------------|
| `headline_large` | 26sp   | Bold      | Nombre app en login      |
| `headline_medium`| 22sp   | Bold      | Títulos de pantalla      |
| `title_large`    | 18sp   | SemiBold  | Números de orden         |
| `title_medium`   | 16sp   | Medium    | Nombres de producto      |
| `body_large`     | 15sp   | Regular   | Contenido principal      |
| `body_medium`    | 13sp   | Regular   | Subtítulos, metadatos    |
| `label_small`    | 11sp   | Medium    | Chips, badges            |

### 1.3 Espaciado y Elevación

- **Padding pantallas:** 16dp
- **Padding cards:** 14–16dp
- **Gap entre cards:** 8dp
- **Elevación cards:** 2dp
- **Elevación toolbar:** 4dp
- **Radius cards:** 12dp
- **Radius chips:** 8dp
- **Radius botones:** 8dp

---

## 2. Arquitectura de Navegación

```
┌──────────────────────────────────────────────────────────┐
│                    FLUJO DE USUARIO                       │
└──────────────────────────────────────────────────────────┘

  [PRIMERA VEZ]
  SetupActivity ──────────────────────────────────────────→ LoginActivity
  (Configurar servidor via URL o QR)

  [SESIÓN EXISTENTE]
  SetupActivity → (URL guardada) ──────────────────────────→ LoginActivity

  LoginActivity ──── (JWT OK) ─────────────────────────────→ HomeActivity
       │
       └── (token inválido) ─── mostrar error

  HomeActivity
       │
       ├── [Nuevo Pedido] ──────────────────────────────────→ TableSelectorActivity
       │                                                            │
       │                                                            │ (tipo + mesa)
       │                                                            ↓
       │                                                      MenuActivity
       │                                                            │
       │                                                    [Carrito Dialog]
       │                                                            │
       │                                                    [Confirmar Pedido]
       │                                                            │
       │                                                  ┌─────────────────┐
       │                                                  │ ✅ Pedido #XXX   │
       │                                                  │ [Nuevo Pedido]  │
       │                                                  │ [Ver Pedidos]   │
       │                                                  └─────────────────┘
       │
       ├── [Mis Pedidos] ───────────────────────────────────→ ActiveOrdersActivity
       │                   (auto-refresh 20s)                       │
       │                                                    [Gestionar Dialog]
       │                                                            │
       │                                              ┌─────────────────────────┐
       │                                              │ ▶ Marcar En Preparación  │
       │                                              │ ✅ Listo para Cobrar      │
       │                                              └─────────────────────────┘
       │
       └── [Cerrar Sesión] ──────────────────────────────────→ LoginActivity
```

---

## 3. Pantallas — Wireframes Detallados

---

### PANTALLA 1: SetupActivity
**Propósito:** Configuración inicial del servidor POS

```
╔═══════════════════════════╗
║                           ║  ← Status bar (primary_dark)
╠═══════════════════════════╣
║                           ║
║                           ║
║          🍽️               ║  ← ic_restaurant 96dp
║                           ║
║      Cafetería POS        ║  ← 26sp Bold primary
║   Sistema de Mesero       ║  ← 14sp text_secondary
║                           ║
║  ╔═══════════════════════╗║
║  ║ 🌐 http://192.168...  ║║  ← TextInputLayout OutlinedBox
║  ╚═══════════════════════╝║     hint: "Dirección del servidor"
║                           ║
║  ┌───────────────────────┐║
║  │       CONECTAR        │║  ← MaterialButton primary 52dp
║  └───────────────────────┘║
║                           ║
║  ───────── o ─────────   ║  ← divider text
║                           ║
║  ┌───────────────────────┐║
║  │  📷  ESCANEAR CÓDIGO  │║  ← Outlined button
║  │       QR/BARRAS       │║
║  └───────────────────────┘║
║                           ║
║  ⏳ Verificando conexión… ║  ← tvStatus (success=green, error=red)
║                           ║
║                           ║
╚═══════════════════════════╝

ESTADOS:
  • Idle:       campo vacío, botones activos
  • Loading:    ProgressBar circular, botones deshabilitados
  • Error:      tvStatus rojo "No se pudo conectar…"
  • Success:    → navega automáticamente a LoginActivity
```

---

### PANTALLA 2: LoginActivity
**Propósito:** Autenticación JWT del usuario mesero

```
╔═══════════════════════════╗
║                           ║
║                           ║
║          🍽️               ║  ← ic_restaurant 80dp
║                           ║
║      Cafetería POS        ║  ← 26sp Bold primary
║      Módulo Mesero        ║  ← 14sp text_secondary
║                           ║
║  ╔═══════════════════════╗║
║  ║ 👤  Usuario            ║║  ← TextInputLayout OutlinedBox
║  ╚═══════════════════════╝║
║                           ║
║  ╔═══════════════════════╗║
║  ║ 🔒  Contraseña     👁  ║║  ← passwordToggleEnabled
║  ╚═══════════════════════╝║
║                           ║
║  ⚠ Credenciales inválidas ║  ← tvError (gone por defecto)
║                           ║
║  ┌───────────────────────┐║
║  │        INGRESAR       │║  ← MaterialButton 52dp
║  └───────────────────────┘║
║                           ║
║       ⏳                  ║  ← ProgressBar (gone por defecto)
║                           ║
║  ─────────────────────── ║
║  Servidor: 192.168.1.100  ║  ← 12sp text_secondary
║  [ Cambiar servidor ]     ║  ← TextButton link
╚═══════════════════════════╝

VALIDACIONES:
  • Usuario y contraseña requeridos
  • Token JWT guardado en SharedPreferences
  • Error 401 → "Usuario o contraseña incorrectos"
  • Sin conexión → "Error al conectar con el servidor"
```

---

### PANTALLA 3: HomeActivity
**Propósito:** Hub principal del mesero

```
╔═══════════════════════════╗
║ ≡  Buenos días, [Nombre]  ║  ← Toolbar primary
║    Cafetería JECA         ║  ← subtitle (branch name)
╠═══════════════════════════╣
║                           ║
║  🟢 Conectado · 192.168.. ║  ← estado conexión chip
║                           ║
║  ╔═══════════════════════╗║
║  ║     🍽️                ║║
║  ║  NUEVO PEDIDO         ║║  ← MaterialCardView clickable
║  ║  Mesa · Llevar ·      ║║     elevation 4dp
║  ║  Domicilio            ║║     cornerRadius 16dp
║  ╚═══════════════════════╝║
║                           ║
║  ╔═══════════════════════╗║
║  ║  📋  ③               ║║  ← badge (número de pedidos activos)
║  ║  MIS PEDIDOS          ║║  ← MaterialCardView outlined
║  ║  ACTIVOS              ║║     strokeColor = primary
║  ║  3 pedidos en curso   ║║
║  ╚═══════════════════════╝║
║                           ║
║                           ║
║                           ║
║                           ║
║  ─────────────────────── ║
║  [ 🚪 Cerrar Sesión ]    ║  ← TextButton text_secondary
╚═══════════════════════════╝

COMPORTAMIENTO:
  • Greeting cambia según hora: Buenos días/tardes/noches
  • Badge de pedidos se actualiza al volver de ActiveOrdersActivity
  • Indicador de conexión verde/rojo según ping al servidor
```

---

### PANTALLA 4: TableSelectorActivity
**Propósito:** Selección del tipo de servicio y mesa (Paso 1 de 2)

```
╔═══════════════════════════╗
║ ←  Nuevo Pedido           ║  ← Toolbar con back
║    Paso 1 de 2            ║  ← subtitle
╠═══════════════════════════╣
║                           ║
║  TIPO DE SERVICIO         ║  ← label 12sp ALLCAPS
║                           ║
║  [  Mesa  ] [Llevar] [Dom]║  ← ChipGroup single-select
║                           ║     (Mesa=default seleccionado)
╠═══════════════════════════╣
║  ╔═══════════════════════╗║
║  ║ 👤 Nombre del cliente  ║║  ← TextInputLayout (opcional)
║  ╚═══════════════════════╝║
║                           ║
║  ╔═══════════════════════╗║  ← solo visible si tipo=DOMICILIO
║  ║ 📍 Dirección de entrega║║
║  ╚═══════════════════════╝║
╠═══════════════════════════╣
║  SELECCIONA UNA MESA      ║  ← solo visible si tipo=MESA
║                           ║
║  ┌──────┐┌──────┐┌──────┐║
║  │  1   ││  2   ││  3   ║  ← RecyclerView GridLayout 3 cols
║  │ 4 p  ││ 4 p  ││ 6 p  ║
║  │ LIBRE││OCUPA ││RESERV║
║  └──────┘└──────┘└──────┘║     LIBRE   = bg #d1fae5 (clickable)
║  ┌──────┐┌──────┐┌──────┐║     OCUPADA = bg #fee2e2 (disabled)
║  │  4   ││  5   ││  6   ║     RESERV  = bg #fef3c7 (disabled)
║  │ 4 p  ││ 4 p  ││ 2 p  ║
║  │ LIBRE││ LIBRE││ LIBRE║     SELECCIONADA = border azul 2dp
║  └──────┘└──────┘└──────┘║
╠═══════════════════════════╣
║  ┌───────────────────────┐║
║  │  CONTINUAR AL MENÚ →  │║  ← disabled hasta selección válida
║  └───────────────────────┘║
╚═══════════════════════════╝

ESTADOS DEL BOTÓN CONTINUAR:
  • MESA sin mesa seleccionada  → disabled
  • MESA con mesa seleccionada  → enabled  "Continuar: Mesa 3 →"
  • LLEVAR                       → enabled  "Continuar: Para Llevar →"
  • DOMICILIO                    → enabled  "Continuar: A Domicilio →"
```

---

### PANTALLA 5: MenuActivity
**Propósito:** Carta de productos y gestión del carrito (Paso 2 de 2)

```
╔═══════════════════════════╗
║ ← Mesa 3 · Para Llevar   ║  ← Toolbar (title = mesa o tipo)
║   Paso 2 de 2             ║  ← subtitle
║                      🛒 ③ ║  ← cart icon con badge count
╠═══════════════════════════╣
║[Desayuno][Almuerzo][Bebida║  ← TabLayout scrollable
║          ][Postres]       ║     un tab por cada menú activo
╠═══════════════════════════╣
║                           ║  ← ProgressBar mientras carga
║  ╔═══════════════════════╗║
║  ║ [img]  Avena con Fruta║║  ← item_menu_product
║  ║  72dp  Caliente y     ║║     ImageView 72dp cornerRadius 8dp
║  ║        nutritiva      ║║     Nombre 15sp bold
║  ║        $2.50      [+] ║║     Desc 12sp text_secondary
║  ╚═══════════════════════╝║     Precio 16sp bold primary
║                           ║     Botón [+] 40dp circular
║  ╔═══════════════════════╗║
║  ║ [img]  Jugo Natural   ║║
║  ║  72dp  Naranja,       ║║
║  ║        limón o mora   ║║
║  ║        $1.75      [+] ║║
║  ╚═══════════════════════╝║
║                           ║
║  ╔═══════════════════════╗║
║  ║ [img]  Sandwich Pollo ║║
║  ║  72dp  Con papas      ║║
║  ║        fritas         ║║
║  ║        $3.50      [+] ║║
║  ╚═══════════════════════╝║
╠═══════════════════════════╣
║  🛒 3 items        $7.75  ║  ← barra inferior con total
║  ┌───────────────────────┐║
║  │    VER CARRITO (3)    │║  ← MaterialButton full width
║  └───────────────────────┘║
╚═══════════════════════════╝

EMPTY STATE (si no hay productos en tab):
  ╔═══════════════════════╗
  ║        🍽️              ║
  ║  No hay productos     ║
  ║  disponibles en       ║
  ║  este menú            ║
  ╚═══════════════════════╝
```

---

### DIALOG: Carrito de Pedido
**Propósito:** Revisión y confirmación del pedido

```
╔═══════════════════════════╗
║   Tu Pedido — Mesa 3      ║  ← AlertDialog title
╠═══════════════════════════╣
║                           ║
║  Avena con Fruta          ║  ← item_cart
║  [-] 1 [+]        $2.50  ║     Name 14sp bold
║                       [🗑]║     qty stepper, subtotal, remove
║  ─────────────────────── ║
║  Jugo Natural             ║
║  [-] 2 [+]        $3.50  ║
║                       [🗑]║
║  ─────────────────────── ║
║  Sandwich de Pollo        ║
║  [-] 1 [+]        $3.50  ║
║                       [🗑]║
║                           ║
║  ╔═══════════════════════╗║
║  ║ 📝 Notas (opcional)   ║║  ← TextInputLayout
║  ╚═══════════════════════╝║
╠═══════════════════════════╣
║  Subtotal:       $ 9.50  ║
║  IVA 15%:        $ 1.43  ║  ← calculado automáticamente
║  ─────────────────────── ║
║  TOTAL:         $ 10.93  ║  ← 18sp bold primary
╠═══════════════════════════╣
║ [Seguir eligiendo]        ║  ← Negative button
║                [CONFIRMAR]║  ← Positive button
╚═══════════════════════════╝

COMPORTAMIENTO:
  • Cambiar qty actualiza subtotales en tiempo real
  • Al llegar a 0 unidades, el ítem se elimina
  • Si carrito vacío → dialog se cierra automáticamente
  • Confirmar → llama POST /api/orders → muestra success dialog
```

---

### PANTALLA 6: ActiveOrdersActivity
**Propósito:** Gestión en tiempo real de todos los pedidos activos

```
╔═══════════════════════════╗
║ ←  Mis Pedidos Activos    ║  ← Toolbar
║    🔄 Auto-refresh: 20s   ║  ← subtitle animado
╠═══════════════════════════╣
║                           ║
║ [Todos][Pendiente][Prep.] ║  ← ChipGroup filter (scroll)
║ [Listo Cobrar][Facturado] ║     count badge en cada chip
║                           ║
╠═══════════════════════════╣
║                           ║  ← SwipeRefreshLayout
║  ╔═══════════════════════╗║
║  ║ ORD-2025-001  12:30  ║║  ← tvOrderNumber + tvTime
║  ║ 🪑 Mesa 3             ║║  ← tvTableType (icon+text)
║  ║ ●  PENDIENTE          ║║  ← status chip AMARILLO
║  ║ ─────────────────── ─║║
║  ║ 2× Avena con Fruta    ║║  ← tvItems (items resumidos)
║  ║ 1× Jugo Natural       ║║     max 2 líneas, ellipsize
║  ║ ─────────────────────║║
║  ║ Total: $9.25  [GESTIONAR]  ← tvTotal + btnAction
║  ╚═══════════════════════╝║     (solo visible si accionable)
║                           ║
║  ╔═══════════════════════╗║
║  ║ ORD-2025-002  12:15  ║║
║  ║ 🛍 Para Llevar        ║║
║  ║ ●  PREPARANDO         ║║  ← status chip NARANJA
║  ║ ─────────────────────║║
║  ║ 1× Sandwich de Pollo  ║║
║  ║ ─────────────────────║║
║  ║ Total: $3.50  [GESTIONAR] ║
║  ╚═══════════════════════╝║
║                           ║
║  ╔═══════════════════════╗║
║  ║ ORD-2025-003  12:00  ║║
║  ║ 🪑 Mesa 1             ║║
║  ║ ●  LISTO COBRAR       ║║  ← status chip VERDE
║  ║ ─────────────────────║║
║  ║ 3× Almuerzo Especial  ║║
║  ║ ─────────────────────║║
║  ║ Total: $18.00         ║║  ← sin botón (ya en caja)
║  ╚═══════════════════════╝║
║                           ║
╠═══════════════════════════╣
║              [ + PEDIDO ] ║  ← ExtendedFAB bottom-right
╚═══════════════════════════╝

EMPTY STATE:
  ╔═══════════════════════╗
  ║        📋              ║
  ║  No hay pedidos        ║
  ║  activos en este       ║
  ║  momento               ║
  ║                        ║
  ║  [CREAR PRIMER PEDIDO] ║
  ╚═══════════════════════╝

DIALOG GESTIONAR:
  ╔═══════════════════════╗
  ║  Pedido ORD-2025-001  ║
  ╠═══════════════════════╣
  ║ ▶ Marcar En Preparación║  ← solo si PENDIENTE
  ║ ✅ Listo para Cobrar   ║  ← si PENDIENTE o PREPARANDO
  ╠═══════════════════════╣
  ║ [  Cancelar  ]         ║
  ╚═══════════════════════╝
```

---

### PANTALLA 7 (NUEVA): OrderDetailActivity
**Propósito:** Vista completa de un pedido individual

```
╔═══════════════════════════╗
║ ←  ORD-2025-001           ║  ← Toolbar con número de orden
║    Mesa 3 · 12:30         ║
╠═══════════════════════════╣
║                           ║
║  ┌─────────────────────┐  ║
║  │  ●  PENDIENTE        │  ║  ← Status chip grande
║  └─────────────────────┘  ║
║                           ║
║  PRODUCTOS                ║  ← sección label
║  ─────────────────────── ║
║  Avena con Fruta          ║
║  2 unidades       $5.00  ║
║  ─────────────────────── ║
║  Jugo Natural             ║
║  1 unidad         $1.75  ║
║  ─────────────────────── ║
║  Sandwich de Pollo        ║
║  1 unidad         $3.50  ║
║  ─────────────────────── ║
║                           ║
║  TOTALES                  ║
║  Subtotal:       $ 9.50  ║
║  IVA 15%:        $ 1.43  ║
║  Total:         $ 10.93  ║
║                           ║
║  INFORMACIÓN              ║
║  Cliente: Juan Pérez      ║
║  Mesero: Ana García       ║
║  Hora: 2025-06-07 12:30  ║
║                           ║
║  NOTAS                    ║
║  Sin cebolla en el sand.  ║
║                           ║
╠═══════════════════════════╣
║  ┌───────────────────────┐║
║  │  ✅ LISTO PARA COBRAR │║  ← acción principal según estado
║  └───────────────────────┘║
╚═══════════════════════════╝
```

---

## 4. Componentes Reutilizables

### 4.1 Status Chip (Pastilla de Estado)
```
┌──────────────────┐
│ ●  PENDIENTE     │  ← dot color + texto ALLCAPS 11sp bold
└──────────────────┘     background semitransparente

Tamaños: chip_small (label) · chip_medium (lista) · chip_large (detalle)
```

### 4.2 Table Card (Card de Mesa)
```
┌────────┐   ┌────────┐   ┌────────┐
│   1    │   │   2    │   │   3    │
│ 4 per. │   │ 4 per. │   │ 6 per. │
│  LIBRE │   │OCUPADA │   │RESERV. │
│ 🟢 bg  │   │ 🔴 bg  │   │ 🟡 bg  │
└────────┘   └────────┘   └────────┘
  clickable    disabled      disabled
  border 2dp   sin borde     sin borde
  primary      error         warning
  (selected)
```

### 4.3 Product Card (Card de Producto)
```
╔══════════════════════════════════════╗
║ [img 72dp] │ Nombre del Producto     ║
║ rounded    │ Categoría · $0.00       ║  ← price bold primary
║            │ Descripción breve...   ║  ← 2 líneas max, ellipsize
║            │                    [+] ║  ← circular button 40dp
╚══════════════════════════════════════╝
  cardElevation=2dp · cornerRadius=12dp
```

### 4.4 Order Card (Card de Pedido)
```
╔══════════════════════════════════════╗
║ ORD-2025-001            12:30 PM    ║  ← número + hora right-aligned
║ 🪑 Mesa 3                           ║  ← icono según tipo
║ ┌──────────────┐                    ║
║ │ ● PENDIENTE  │                    ║  ← status chip
║ └──────────────┘                    ║
║ ─────────────────────────────────── ║
║ 2× Avena con Fruta, 1× Jugo Nat…   ║  ← items resumidos, 2 líneas
║ ─────────────────────────────────── ║
║ Total: $9.25              [GESTIONAR]║  ← botón solo si accionable
╚══════════════════════════════════════╝
```

### 4.5 Cart Item (Ítem en Carrito)
```
╔══════════════════════════════════════╗
║ Avena con Fruta                  🗑  ║  ← nombre + remove button
║ ─────────────────────────────────── ║
║ [-]  2  [+]                  $5.00  ║  ← stepper qty + subtotal
╚══════════════════════════════════════╝
```

---

## 5. Flujos de Usuario Clave

### 5.1 Crear un Pedido de Mesa
```
1. HomeActivity → tap "Nuevo Pedido"
2. TableSelectorActivity:
   a. Chip "Mesa" seleccionado (default)
   b. Tap en mesa disponible (ej. Mesa 3)
   c. Botón cambia a "Continuar: Mesa 3 →"
   d. Tap Continuar
3. MenuActivity (título: "Mesa 3"):
   a. Carga menús y tabs automáticamente
   b. Navegar tabs para explorar categorías
   c. Tap [+] en productos → se agregan al carrito
   d. Badge en toolbar muestra count
   e. Barra inferior muestra total en tiempo real
   f. Tap "Ver Carrito (N)"
4. CartDialog:
   a. Revisar/ajustar cantidades
   b. Tap "Confirmar Pedido"
5. Loading → POST /api/orders
6. SuccessDialog:
   a. "✅ Pedido ORD-2025-045 enviado a cocina"
   b. [Nuevo Pedido] → vuelve a HomeActivity
   c. [Ver Mis Pedidos] → va a ActiveOrdersActivity
```

### 5.2 Actualizar Estado de Pedido
```
1. ActiveOrdersActivity → lista de pedidos activos
2. Tap [GESTIONAR] en pedido PENDIENTE
3. Dialog opciones:
   a. "▶ Marcar En Preparación" → PUT /api/orders/{id}/status {PREPARANDO}
   b. "✅ Listo para Cobrar"    → PUT /api/orders/{id}/ready-invoice
4. Lista se actualiza automáticamente
5. Pedido en LISTO_FACTURAR desaparece del botón Gestionar
   (el cajero de escritorio lo verá en su cola)
```

### 5.3 Pedido Para Llevar / Domicilio
```
1. TableSelectorActivity:
   - Chip "Llevar" → oculta grid de mesas
   - Chip "Domicilio" → oculta grid, muestra campo dirección
   - Nombre cliente (campo opcional)
2. MenuActivity → igual que mesa
3. CartDialog → igual proceso
4. Backend recibe serviceType=LLEVAR/DOMICILIO, tableId=null
```

---

## 6. Especificaciones Técnicas

### 6.1 Configuración Android
| Parámetro       | Valor                        |
|-----------------|------------------------------|
| minSdk          | 26 (Android 8.0 Oreo)        |
| targetSdk       | 34 (Android 14)              |
| compileSdk      | 34                           |
| Gradle Plugin   | 8.2.2                        |
| Kotlin          | 1.9.x                        |
| Material Design | 1.11.0 (Material 3)          |
| Retrofit        | 2.9.0                        |
| OkHttp          | 4.12.0                       |
| Glide           | 4.16.0                       |
| Coroutines      | 1.7.3                        |

### 6.2 Endpoints de la API
| Método | Endpoint                      | Pantalla             |
|--------|-------------------------------|----------------------|
| POST   | /api/auth/login               | LoginActivity        |
| GET    | /api/orders/menus             | MenuActivity         |
| GET    | /api/orders/tables            | TableSelectorActivity|
| POST   | /api/orders                   | MenuActivity (confirm)|
| GET    | /api/orders/active?branch_id= | ActiveOrdersActivity |
| GET    | /api/orders/{id}              | OrderDetailActivity  |
| PUT    | /api/orders/{id}/status       | ActiveOrdersActivity |
| PUT    | /api/orders/{id}/ready-invoice| ActiveOrdersActivity |

### 6.3 Almacenamiento Local (SharedPreferences)
| Clave         | Tipo   | Descripción                    |
|---------------|--------|--------------------------------|
| `server_url`  | String | URL del servidor POS           |
| `auth_token`  | String | JWT Bearer token               |
| `user_id`     | Int    | ID del usuario autenticado     |
| `branch_id`   | Int    | ID de la sucursal              |
| `full_name`   | String | Nombre completo del mesero     |
| `user_role`   | String | Rol: admin/mesero              |

### 6.4 Estructura de Carpetas del Proyecto
```
app/src/main/
├── java/com/cafeteria/pos/
│   ├── data/
│   │   ├── ApiModels.kt        ← DTOs de la API
│   │   ├── ApiService.kt       ← Interface Retrofit
│   │   └── RetrofitClient.kt   ← Singleton + SharedPrefs
│   ├── adapters/
│   │   ├── MenuProductAdapter.kt
│   │   ├── CartAdapter.kt
│   │   ├── OrderAdapter.kt
│   │   └── TableAdapter.kt
│   ├── CartManager.kt          ← Singleton estado carrito
│   ├── SetupActivity.kt
│   ├── LoginActivity.kt
│   ├── HomeActivity.kt
│   ├── TableSelectorActivity.kt
│   ├── MenuActivity.kt
│   ├── ActiveOrdersActivity.kt
│   └── OrderDetailActivity.kt  ← (nueva)
└── res/
    ├── layout/
    │   ├── activity_setup.xml
    │   ├── activity_login.xml
    │   ├── activity_home.xml
    │   ├── activity_table_selector.xml
    │   ├── activity_menu.xml
    │   ├── activity_active_orders.xml
    │   ├── activity_order_detail.xml  ← (nueva)
    │   ├── item_menu_product.xml
    │   ├── item_cart.xml
    │   ├── item_order.xml
    │   ├── item_table.xml
    │   └── dialog_cart.xml
    └── values/
        ├── colors.xml
        ├── strings.xml
        └── themes.xml
```

---

## 7. Consideraciones de UX

1. **Auto-refresh no invasivo**: El indicador de 20s en el subtitle de la toolbar es sutil pero informativo.
2. **Estados vacíos con acción**: Todo empty state tiene un CTA claro para el usuario.
3. **Feedback inmediato**: Toast messages para cada acción (agregar al carrito, cambiar estado).
4. **Progresivo**: La barra de progreso bloquea la UI solo cuando es estrictamente necesario.
5. **Offline graceful**: Si no hay conexión, se muestra error con opción de reintentar.
6. **Confirmación destructiva**: Solo se pide confirmación al marcar "Listo para Cobrar" (acción irreversible).
7. **Persistencia de sesión**: El JWT se mantiene entre sesiones hasta logout explícito.
8. **Orientación**: Diseñado para portrait, con soporte básico landscape.
