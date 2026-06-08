package com.cafeteria.pos.data

import com.google.gson.annotations.SerializedName

// ── Auth ──────────────────────────────────────────────────────────────────────

data class LoginRequest(val username: String, val password: String)

data class LoginResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("token_type")   val tokenType: String,
    @SerializedName("user_id")      val userId: Int? = null,
    @SerializedName("branch_id")    val branchId: Int? = null,
    @SerializedName("full_name")    val fullName: String? = null,
    val role: String? = null,
)

// ── Menús ─────────────────────────────────────────────────────────────────────

data class MenuItemDto(
    @SerializedName("menu_item_id") val menuItemId: Int,
    @SerializedName("product_id")   val productId: Int,
    val name: String,
    val description: String?,
    val price: Double,
    val category: String?,
    @SerializedName("image_url")    val imageUrl: String?,
    val sku: String,
)

data class MenuDto(
    val id: Int,
    val name: String,
    val description: String?,
    val items: List<MenuItemDto>,
)

// ── Mesas ─────────────────────────────────────────────────────────────────────

data class TableDto(
    val id: Int,
    val number: String,
    val capacity: Int,
    val status: String,   // LIBRE | OCUPADA | RESERVADA
    val zone: String?,
)

// ── Pedidos ───────────────────────────────────────────────────────────────────

data class OrderItemCreate(
    @SerializedName("product_id") val productId: Int,
    val quantity: Int,
    val notes: String? = null,
)

data class OrderCreate(
    @SerializedName("service_type")   val serviceType: String,
    @SerializedName("table_id")       val tableId: Int?,
    @SerializedName("customer_name")  val customerName: String,
    @SerializedName("customer_address") val customerAddress: String? = null,
    val items: List<OrderItemCreate>,
    @SerializedName("user_id")   val userId: Int,
    @SerializedName("branch_id") val branchId: Int,
    val notes: String? = null,
)

data class OrderCreateResponse(
    @SerializedName("order_number") val orderNumber: String,
    val total: Double,
    val surcharge: Double = 0.0,
    val status: String,
)

data class OrderItemDetail(
    val name: String,
    val qty: Int,
    @SerializedName("unit_price") val unitPrice: Double,
    val subtotal: Double,
    @SerializedName("image_url") val imageUrl: String? = null,
)

data class OrderDto(
    val id: Int,
    val invoice: String,
    val type: String,         // MESA | LLEVAR | DOMICILIO
    val table: String?,
    @SerializedName("table_id") val tableId: Int?,
    val customer: String,
    val time: String,
    val items: List<OrderItemDetail>,
    val subtotal: Double,
    @SerializedName("tax_amount") val taxAmount: Double,
    val total: Double,
    val notes: String?,
    val status: String,       // PENDIENTE | PREPARANDO | LISTO_FACTURAR | FACTURADO
)

data class StatusUpdate(val status: String)

data class GenericResponse(val ok: Boolean, val message: String? = null)
