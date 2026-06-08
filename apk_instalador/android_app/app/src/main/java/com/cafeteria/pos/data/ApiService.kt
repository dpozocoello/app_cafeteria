package com.cafeteria.pos.data

import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    // Auth
    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequest): Response<LoginResponse>

    // Menús activos para toma de pedidos
    @GET("api/orders/menus")
    suspend fun getMenus(): Response<List<MenuDto>>

    // Mesas disponibles
    @GET("api/orders/tables")
    suspend fun getTables(): Response<List<TableDto>>

    // Crear pedido
    @POST("api/orders")
    suspend fun createOrder(@Body body: OrderCreate): Response<OrderCreateResponse>

    // Pedidos activos de la sucursal
    @GET("api/orders/active")
    suspend fun getActiveOrders(@Query("branch_id") branchId: Int): Response<List<OrderDto>>

    // Detalle de un pedido
    @GET("api/orders/{id}")
    suspend fun getOrder(@Path("id") id: Int): Response<OrderDto>

    // Actualizar estado (PENDIENTE → PREPARANDO → LISTO_FACTURAR)
    @PUT("api/orders/{id}/status")
    suspend fun updateStatus(
        @Path("id") id: Int,
        @Body body: StatusUpdate,
    ): Response<GenericResponse>

    // Marcar listo para facturar (shortcut)
    @PUT("api/orders/{id}/ready-invoice")
    suspend fun markReadyForInvoice(@Path("id") id: Int): Response<GenericResponse>
}
