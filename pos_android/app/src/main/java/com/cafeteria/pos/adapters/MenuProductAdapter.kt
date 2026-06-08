package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.data.MenuItemDto
import com.cafeteria.pos.databinding.ItemMenuProductBinding

class MenuProductAdapter(private val onAddClick: (MenuItemDto) -> Unit) : RecyclerView.Adapter<MenuProductAdapter.ViewHolder>() {

    private var items = listOf<MenuItemDto>()

    fun setItems(newItems: List<MenuItemDto>) {
        items = newItems
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemMenuProductBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position])
    }

    override fun getItemCount() = items.size

    inner class ViewHolder(private val binding: ItemMenuProductBinding) : RecyclerView.Adapter.ViewHolder(binding.root) {
        fun bind(item: MenuItemDto) {
            binding.tvProductName.text = item.name
            binding.tvProductDesc.text = item.description ?: ""
            binding.tvProductPrice.text = String.format("$%.2f", item.price)
            
            // Image could be loaded here with Glide/Picasso if available.
            // binding.ivProduct

            binding.btnAdd.setOnClickListener {
                onAddClick(item)
            }
        }
    }
}
