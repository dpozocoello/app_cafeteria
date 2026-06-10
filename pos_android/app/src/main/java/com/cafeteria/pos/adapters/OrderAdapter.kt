package com.cafeteria.pos.adapters

import android.graphics.Color
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.data.OrderResponseDto
import com.cafeteria.pos.databinding.ItemOrderBinding

class OrderAdapter(private val onClick: (OrderResponseDto) -> Unit) : RecyclerView.Adapter<OrderAdapter.ViewHolder>() {

    private var items = listOf<OrderResponseDto>()

    fun setItems(newItems: List<OrderResponseDto>) {
        items = newItems
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemOrderBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(items[position])
    }

    override fun getItemCount() = items.size

    inner class ViewHolder(private val binding: ItemOrderBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(order: OrderResponseDto) {
            binding.tvOrderNumber.text = order.invoice
            binding.tvTime.text = order.time
            binding.tvServiceType.text = if (order.type == "MESA") "MESA ${order.table}" else order.type
            binding.tvCustomer.text = order.customer
            binding.tvTotal.text = String.format("$%.2f", order.total)

            binding.chipStatus.text = order.status
            when (order.status) {
                "PENDIENTE" -> {
                    binding.chipStatus.setChipBackgroundColorResource(android.R.color.holo_orange_light)
                    binding.chipStatus.setTextColor(Color.WHITE)
                }
                "PREPARANDO" -> {
                    binding.chipStatus.setChipBackgroundColorResource(android.R.color.holo_blue_light)
                    binding.chipStatus.setTextColor(Color.WHITE)
                }
                "LISTO_COBRAR" -> {
                    binding.chipStatus.setChipBackgroundColorResource(android.R.color.holo_green_light)
                    binding.chipStatus.setTextColor(Color.WHITE)
                }
                else -> {
                    binding.chipStatus.setChipBackgroundColorResource(android.R.color.darker_gray)
                    binding.chipStatus.setTextColor(Color.WHITE)
                }
            }

            binding.root.setOnClickListener {
                onClick(order)
            }
        }
    }
}
