package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.cardview.widget.CardView
import androidx.core.content.ContextCompat
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
        val ctx   = holder.itemView.context
        val isSelected = selectedId == table.id

        holder.tvNumber.text   = table.number
        holder.tvCapacity.text = "${table.capacity} pers."
        holder.tvStatus.text   = when (table.status) {
            "LIBRE"     -> "Libre"
            "OCUPADA"   -> "Ocupada"
            "RESERVADA" -> "Reservada"
            else        -> table.status
        }

        data class TableColors(val bg: Int, val text: Int, val enabled: Boolean)

        val colors = if (isSelected) {
            TableColors(
                bg = ContextCompat.getColor(ctx, R.color.table_selected_bg),
                text = ContextCompat.getColor(ctx, R.color.primary),
                enabled = true
            )
        } else {
            when (table.status) {
                "LIBRE"     -> TableColors(
                    bg = ContextCompat.getColor(ctx, R.color.table_free_bg),
                    text = ContextCompat.getColor(ctx, R.color.table_free_text),
                    enabled = true
                )
                "OCUPADA"   -> TableColors(
                    bg = ContextCompat.getColor(ctx, R.color.table_occupied_bg),
                    text = ContextCompat.getColor(ctx, R.color.table_occupied_text),
                    enabled = false
                )
                "RESERVADA" -> TableColors(
                    bg = ContextCompat.getColor(ctx, R.color.table_reserved_bg),
                    text = ContextCompat.getColor(ctx, R.color.table_reserved_text),
                    enabled = false
                )
                else -> TableColors(
                    bg = ContextCompat.getColor(ctx, R.color.background),
                    text = ContextCompat.getColor(ctx, R.color.text_secondary),
                    enabled = true
                )
            }
        }

        holder.card.setCardBackgroundColor(colors.bg)
        holder.tvStatus.setTextColor(colors.text)
        holder.tvNumber.setTextColor(colors.text)
        holder.card.cardElevation = if (isSelected) 6f else 2f
        holder.itemView.isEnabled = colors.enabled
        holder.itemView.alpha = if (colors.enabled) 1f else 0.5f

        if (colors.enabled) {
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
