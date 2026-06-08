package com.cafeteria.pos.data

import com.google.gson.annotations.SerializedName

// Autenticación
data class LoginRequest(
    val username: String,
    val password: String
)

data class UserInfo(
    val id: Int,
    val username: String,
    val full_name: String,
    val role: String?
)

data class LoginResponse(
    val access_token: String,
    val token_type: String,
    val user: UserInfo
)

// Mesas
data class TableDto(
    val id: Int,
    val number: Int,
    val zone: String,
    val capacity: Int,
    val status: String
)

// Menús y Productos
data class MenuItemDto(
    val menu_item_id: Int,
    val product_id: Int,
    val name: String,
    val description: String?,
    val price: Double,
    val category: String?,
    val image_url: String?,
    val sku: String?
)

data class MenuDto(
    val id: Int,
    val name: String,
    val description: String?,
    val items: List<MenuItemDto>
)

// Creación de Pedidos
data class OrderItemCreate(
    val product_id: Int,
    val quantity: Int,
    val notes: String? = null
)

data class OrderCreateDto(
    val service_type: String, // "MESA", "LLEVAR", "DOMICILIO"
    val table_id: Int? = null,
    val customer_name: String? = "CONSUMIDOR FINAL",
    val customer_address: String? = null,
    val notes: String? = null,
    val items: List<OrderItemCreate>,
    val user_id: Int,
    val branch_id: Int = 1
)

data class OrderCreateResponse(
    val order_number: String,
    val total: Double,
    val status: String
)

// Listado de Pedidos Activos
data class OrderItemDto(
    val name: String,
    val qty: Int,
    val unit_price: Double,
    val subtotal: Double,
    val image_url: String?
)

data class OrderResponseDto(
    val id: Int,
    val invoice: String,
    val type: String,
    val table: Int?,
    val table_id: Int?,
    val customer: String?,
    val time: String,
    val items: List<OrderItemDto>,
    val subtotal: Double,
    val tax_amount: Double,
    val total: Double,
    val notes: String?,
    val status: String
)

// Actualizar Estado
data class StatusUpdateDto(
    val status: String
)

data class GenericResponse(
    val ok: Boolean?,
    val message: String?
)
