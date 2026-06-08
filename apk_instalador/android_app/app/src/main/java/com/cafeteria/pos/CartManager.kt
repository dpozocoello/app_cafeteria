package com.cafeteria.pos

import com.cafeteria.pos.data.MenuItemDto
import com.cafeteria.pos.data.TableDto

data class CartItem(
    val menuItemId: Int,
    val productId: Int,
    val name: String,
    val price: Double,
    val imageUrl: String?,
    var quantity: Int,
    var notes: String = "",
)

object CartManager {

    val items = mutableListOf<CartItem>()
    var selectedTable: TableDto? = null
    var serviceType: String = "MESA"
    var customerName: String = "CONSUMIDOR FINAL"
    var customerAddress: String = ""

    fun addItem(menuItem: MenuItemDto) {
        val existing = items.find { it.menuItemId == menuItem.menuItemId }
        if (existing != null) existing.quantity++
        else items.add(CartItem(
            menuItemId = menuItem.menuItemId,
            productId  = menuItem.productId,
            name       = menuItem.name,
            price      = menuItem.price,
            imageUrl   = menuItem.imageUrl,
            quantity   = 1,
        ))
    }

    fun removeItem(menuItemId: Int) { items.removeAll { it.menuItemId == menuItemId } }

    fun increment(menuItemId: Int) {
        val item = items.find { it.menuItemId == menuItemId } ?: return
        item.quantity++
    }

    fun decrement(menuItemId: Int) {
        val item = items.find { it.menuItemId == menuItemId } ?: return
        if (item.quantity > 1) item.quantity-- else removeItem(menuItemId)
    }

    fun totalItems(): Int = items.sumOf { it.quantity }

    fun totalPrice(): Double = items.sumOf { it.price * it.quantity }

    fun clear() {
        items.clear()
        selectedTable = null
        serviceType = "MESA"
        customerName = "CONSUMIDOR FINAL"
        customerAddress = ""
    }
}
