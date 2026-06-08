package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.data.MenuItemDto
import com.cafeteria.pos.databinding.ItemCartBinding

class CartAdapter(
    private val onIncrease: (MenuItemDto) -> Unit,
    private val onDecrease: (Int) -> Unit
) : RecyclerView.Adapter<CartAdapter.ViewHolder>() {

    private var items = listOf<Pair<MenuItemDto, Int>>()

    fun setItems(newItems: List<Pair<MenuItemDto, Int>>) {
        items = newItems
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemCartBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position])
    }

    override fun getItemCount() = items.size

    inner class ViewHolder(private val binding: ItemCartBinding) : RecyclerView.Adapter.ViewHolder(binding.root) {
        fun bind(pair: Pair<MenuItemDto, Int>) {
            val (item, qty) = pair
            binding.tvProductName.text = item.name
            binding.tvProductPrice.text = String.format("$%.2f", item.price)
            binding.tvQty.text = qty.toString()
            binding.tvSubtotal.text = String.format("$%.2f", item.price * qty)

            binding.btnPlus.setOnClickListener {
                onIncrease(item)
            }
            binding.btnMinus.setOnClickListener {
                onDecrease(item.product_id)
            }
        }
    }
}
