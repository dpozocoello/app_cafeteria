package com.cafeteria.pos

import com.cafeteria.pos.data.MenuItemDto

object CartManager {
    // Key: product_id, Value: Pair<MenuItemDto, quantity>
    private val items = mutableMapOf<Int, Pair<MenuItemDto, Int>>()
    var currentTableId: Int? = null
    var serviceType: String = "MESA"
    var customerName: String? = null
    var customerAddress: String? = null

    fun addItem(item: MenuItemDto) {
        val current = items[item.product_id]
        if (current != null) {
            items[item.product_id] = Pair(item, current.second + 1)
        } else {
            items[item.product_id] = Pair(item, 1)
        }
    }

    fun removeItem(productId: Int) {
        val current = items[productId]
        if (current != null) {
            if (current.second > 1) {
                items[productId] = Pair(current.first, current.second - 1)
            } else {
                items.remove(productId)
            }
        }
    }

    fun getItems(): List<Pair<MenuItemDto, Int>> {
        return items.values.toList()
    }

    fun getTotalItems(): Int {
        return items.values.sumOf { it.second }
    }

    fun getSubtotal(): Double {
        return items.values.sumOf { it.first.price * it.second }
    }

    fun getTax(): Double {
        return getSubtotal() * 0.15
    }

    fun getTotal(): Double {
        return getSubtotal() + getTax()
    }

    fun clear() {
        items.clear()
        currentTableId = null
        serviceType = "MESA"
        customerName = null
        customerAddress = null
    }
}
