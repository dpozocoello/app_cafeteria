package com.cafeteria.pos.adapters

import android.graphics.Color
import android.view.LayoutInflater
import android.view.ViewGroup
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.R
import com.cafeteria.pos.data.TableDto
import com.cafeteria.pos.databinding.ItemTableBinding
import com.google.android.material.card.MaterialCardView

class TableAdapter(private val onTableSelected: (TableDto?) -> Unit) : RecyclerView.Adapter<TableAdapter.ViewHolder>() {

    private var tables = listOf<TableDto>()
    private var selectedPosition = -1

    fun setTables(newTables: List<TableDto>) {
        tables = newTables
        selectedPosition = -1
        notifyDataSetChanged()
    }

    fun setSelectedTableId(tableId: Int) {
        val pos = tables.indexOfFirst { it.id == tableId }
        if (pos != -1) {
            val prevSelected = selectedPosition
            selectedPosition = pos
            if (prevSelected != -1) notifyItemChanged(prevSelected)
            notifyItemChanged(selectedPosition)
            onTableSelected(tables[selectedPosition])
        }
    }

    fun getTableById(tableId: Int): TableDto? {
        return tables.find { it.id == tableId }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemTableBinding.inflate(LayoutInflater.from(parent.context), parent, false)
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val table = tables[position]
        holder.bind(table, position == selectedPosition)
    }

    override fun getItemCount() = tables.size

    inner class ViewHolder(private val binding: ItemTableBinding) : RecyclerView.ViewHolder(binding.root) {
        fun bind(table: TableDto, isSelected: Boolean) {
            binding.tvTableNumber.text = table.number.toString()
            binding.tvCapacity.text = "${table.capacity} p"
            binding.tvStatus.text = table.status

            val card = binding.root as MaterialCardView
            val context = binding.root.context

            when (table.status.uppercase()) {
                "LIBRE" -> {
                    binding.layoutContainer.setBackgroundColor(Color.parseColor("#d1fae5"))
                    binding.tvTableNumber.setTextColor(Color.parseColor("#065f46"))
                    binding.tvCapacity.setTextColor(Color.parseColor("#065f46"))
                    binding.tvStatus.setTextColor(Color.parseColor("#065f46"))
                    
                    card.isClickable = true
                    card.setOnClickListener {
                        val prevSelected = selectedPosition
                        selectedPosition = bindingAdapterPosition
                        notifyItemChanged(prevSelected)
                        notifyItemChanged(selectedPosition)
                        onTableSelected(table)
                    }

                    if (isSelected) {
                        card.strokeWidth = 6
                        card.strokeColor = Color.parseColor("#1a56db")
                    } else {
                        card.strokeWidth = 0
                    }
                }
                "OCUPADA" -> {
                    binding.layoutContainer.setBackgroundColor(Color.parseColor("#fee2e2"))
                    binding.tvTableNumber.setTextColor(Color.parseColor("#991b1b"))
                    binding.tvCapacity.setTextColor(Color.parseColor("#991b1b"))
                    binding.tvStatus.setTextColor(Color.parseColor("#991b1b"))
                    card.isClickable = false
                    card.strokeWidth = 0
                }
                else -> { // Reservada etc
                    binding.layoutContainer.setBackgroundColor(Color.parseColor("#fef3c7"))
                    binding.tvTableNumber.setTextColor(Color.parseColor("#92400e"))
                    binding.tvCapacity.setTextColor(Color.parseColor("#92400e"))
                    binding.tvStatus.setTextColor(Color.parseColor("#92400e"))
                    card.isClickable = false
                    card.strokeWidth = 0
                }
            }
        }
    }
}
