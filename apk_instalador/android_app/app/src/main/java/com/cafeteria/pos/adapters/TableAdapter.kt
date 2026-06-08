package com.cafeteria.pos.adapters

import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.cardview.widget.CardView
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.R
import com.cafeteria.pos.data.TableDto

class TableAdapter(
    private val tables: List<TableDto>,
    private val onSelect: (TableDto) -> Unit,
) : RecyclerView.Adapter<TableAdapter.VH>() {

    private var selectedId: Int? = null

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val card      : CardView = view.findViewById(R.id.cardTable)
        val tvNumber  : TextView = view.findViewById(R.id.tvTableNumber)
        val tvCapacity: TextView = view.findViewById(R.id.tvCapacity)
        val tvStatus  : TextView = view.findViewById(R.id.tvTableStatus)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_table, parent, false)
    )

    override fun getItemCount() = tables.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val table = tables[position]

        holder.tvNumber.text   = table.number
        holder.tvCapacity.text = "${table.capacity} personas"
        holder.tvStatus.text   = when (table.status) {
            "LIBRE"     -> "Libre"
            "OCUPADA"   -> "Ocupada"
            "RESERVADA" -> "Reservada"
            else        -> table.status
        }

        val (bgColor, textColor, enabled) = when (table.status) {
            "LIBRE"     -> Triple(Color.parseColor("#dcfce7"), Color.parseColor("#16a34a"), true)
            "OCUPADA"   -> Triple(Color.parseColor("#fee2e2"), Color.parseColor("#dc2626"), false)
            "RESERVADA" -> Triple(Color.parseColor("#fef3c7"), Color.parseColor("#d97706"), false)
            else        -> Triple(Color.parseColor("#f3f4f6"), Color.parseColor("#6b7280"), true)
        }

        holder.card.setCardBackgroundColor(bgColor)
        holder.tvStatus.setTextColor(textColor)
        holder.itemView.isEnabled = enabled
        holder.itemView.alpha = if (enabled) 1f else 0.55f

        // Borde de selección
        if (selectedId == table.id) {
            holder.card.cardElevation = 8f
            holder.card.setCardBackgroundColor(Color.parseColor("#dbeafe"))
        }

        if (enabled) {
            holder.itemView.setOnClickListener {
                val prev = selectedId
                selectedId = table.id
                val prevIdx = tables.indexOfFirst { it.id == prev }
                if (prevIdx >= 0) notifyItemChanged(prevIdx)
                notifyItemChanged(position)
                onSelect(table)
            }
        }
    }
}
