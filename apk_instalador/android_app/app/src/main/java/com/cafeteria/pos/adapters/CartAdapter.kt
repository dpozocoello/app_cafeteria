package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.CartItem
import com.cafeteria.pos.R

class CartAdapter(
    private val items: List<CartItem>,
    private val onIncrement: (Int) -> Unit,
    private val onDecrement: (Int) -> Unit,
    private val onRemove:    (Int) -> Unit,
) : RecyclerView.Adapter<CartAdapter.VH>() {

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvName    : TextView    = view.findViewById(R.id.tvCartItemName)
        val tvPrice   : TextView    = view.findViewById(R.id.tvCartItemPrice)
        val tvQty     : TextView    = view.findViewById(R.id.tvCartQty)
        val btnMinus  : ImageButton = view.findViewById(R.id.btnMinus)
        val btnPlus   : ImageButton = view.findViewById(R.id.btnPlus)
        val btnRemove : ImageButton = view.findViewById(R.id.btnRemoveItem)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_cart, parent, false)
    )

    override fun getItemCount() = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.tvName.text  = item.name
        holder.tvPrice.text = "$%.2f".format(item.price * item.quantity)
        holder.tvQty.text   = item.quantity.toString()

        holder.btnMinus.setOnClickListener  { onDecrement(item.menuItemId); notifyItemChanged(position) }
        holder.btnPlus.setOnClickListener   { onIncrement(item.menuItemId); notifyItemChanged(position) }
        holder.btnRemove.setOnClickListener { onRemove(item.menuItemId); notifyDataSetChanged() }
    }
}
