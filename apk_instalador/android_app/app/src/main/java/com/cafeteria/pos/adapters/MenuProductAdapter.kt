package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.bumptech.glide.Glide
import com.cafeteria.pos.R
import com.cafeteria.pos.data.MenuItemDto
import com.cafeteria.pos.data.RetrofitClient

class MenuProductAdapter(
    private val onAdd: (MenuItemDto) -> Unit,
) : RecyclerView.Adapter<MenuProductAdapter.VH>() {

    private val items = mutableListOf<MenuItemDto>()

    fun submitList(newItems: List<MenuItemDto>) {
        items.clear()
        items.addAll(newItems)
        notifyDataSetChanged()
    }

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val ivImage   : ImageView = view.findViewById(R.id.ivProductImage)
        val tvName    : TextView  = view.findViewById(R.id.tvProductName)
        val tvCategory: TextView  = view.findViewById(R.id.tvCategory)
        val tvPrice   : TextView  = view.findViewById(R.id.tvPrice)
        val btnAdd    : View      = view.findViewById(R.id.btnAddToCart)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_menu_product, parent, false)
    )

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.tvName.text     = item.name
        holder.tvCategory.text = item.category ?: ""
        holder.tvPrice.text    = "$%.2f".format(item.price)

        val serverUrl = RetrofitClient.serverUrl(holder.itemView.context)
        val imageUrl  = item.imageUrl?.let { if (it.startsWith("http")) it else "$serverUrl$it" }

        if (!imageUrl.isNullOrBlank()) {
            Glide.with(holder.itemView.context)
                .load(imageUrl)
                .placeholder(R.drawable.ic_restaurant)
                .error(R.drawable.ic_restaurant)
                .centerCrop()
                .into(holder.ivImage)
        } else {
            holder.ivImage.setImageResource(R.drawable.ic_restaurant)
        }

        holder.btnAdd.setOnClickListener { onAdd(item) }
        holder.itemView.setOnClickListener { onAdd(item) }
    }
}
