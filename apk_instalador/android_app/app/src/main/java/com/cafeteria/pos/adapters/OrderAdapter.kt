package com.cafeteria.pos.adapters

import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.R
import com.cafeteria.pos.data.OrderDto

class OrderAdapter(
    private val orders: List<OrderDto>,
    private val onActionClick: (OrderDto) -> Unit,
) : RecyclerView.Adapter<OrderAdapter.VH>() {

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvOrderNum  : TextView = view.findViewById(R.id.tvOrderNumber)
        val tvTableType : TextView = view.findViewById(R.id.tvTableType)
        val tvTime      : TextView = view.findViewById(R.id.tvTime)
        val tvItems     : TextView = view.findViewById(R.id.tvItems)
        val tvTotal     : TextView = view.findViewById(R.id.tvTotal)
        val tvStatus    : TextView = view.findViewById(R.id.tvStatus)
        val btnAction   : Button   = view.findViewById(R.id.btnAction)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_order, parent, false)
    )

    override fun getItemCount() = orders.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val order = orders[position]

        holder.tvOrderNum.text  = order.invoice
        holder.tvTime.text      = order.time
        holder.tvTotal.text     = "Total: $%.2f".format(order.total)

        val location = when (order.type) {
            "MESA"      -> "Mesa ${order.table ?: "—"}"
            "LLEVAR"    -> "Para Llevar"
            "DOMICILIO" -> "Domicilio — ${order.customer}"
            else        -> order.type
        }
        holder.tvTableType.text = location

        val itemsSummary = order.items.take(3).joinToString(", ") { "${it.qty}x ${it.name}" }
        val more = if (order.items.size > 3) " +${order.items.size - 3} más" else ""
        holder.tvItems.text = itemsSummary + more

        // Color y texto de estado
        val (statusLabel, statusColor, actionLabel) = when (order.status) {
            "PENDIENTE"      -> Triple("🟡 Pendiente",     Color.parseColor("#d97706"), "Gestionar")
            "PREPARANDO"     -> Triple("🟠 Preparando",    Color.parseColor("#ea580c"), "Gestionar")
            "LISTO_FACTURAR" -> Triple("🟢 Listo p/ cobro",Color.parseColor("#16a34a"), "")
            "FACTURADO"      -> Triple("✅ Facturado",     Color.parseColor("#6b7280"), "")
            else             -> Triple(order.status,        Color.parseColor("#374151"), "")
        }
        holder.tvStatus.text      = statusLabel
        holder.tvStatus.setTextColor(statusColor)

        if (actionLabel.isEmpty()) {
            holder.btnAction.visibility = View.GONE
        } else {
            holder.btnAction.visibility = View.VISIBLE
            holder.btnAction.text = actionLabel
            holder.btnAction.setOnClickListener { onActionClick(order) }
        }
    }
}
