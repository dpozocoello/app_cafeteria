package com.cafeteria.pos.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {
    @GET("/api/license/status")
    suspend fun checkConnection(): Response<Any>

    @POST("/api/auth/login")
    suspend fun login(@Body request: LoginRequest): Response<LoginResponse>

    @GET("/api/orders/tables")
    suspend fun getTables(): Response<List<TableDto>>

    @GET("/api/orders/menus")
    suspend fun getMenus(): Response<List<MenuDto>>

    @POST("/api/orders")
    suspend fun createOrder(@Body order: OrderCreateDto): Response<OrderCreateResponse>

    @GET("/api/orders/active")
    suspend fun getActiveOrders(@Query("branch_id") branchId: Int = 1): Response<List<OrderResponseDto>>

    @GET("/api/orders/{id}")
    suspend fun getOrderById(@Path("id") orderId: Int): Response<OrderResponseDto>

    @PUT("/api/orders/{id}/status")
    suspend fun updateOrderStatus(
        @Path("id") orderId: Int,
        @Body status: StatusUpdateDto
    ): Response<GenericResponse>

    @PUT("/api/orders/{id}/ready-invoice")
    suspend fun markReadyForInvoice(@Path("id") orderId: Int): Response<GenericResponse>
}
