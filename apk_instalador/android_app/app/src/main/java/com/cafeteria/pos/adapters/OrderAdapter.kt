package com.cafeteria.pos.adapters

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.R
import com.cafeteria.pos.data.OrderDto
import com.google.android.material.button.MaterialButton

class OrderAdapter(
    private val orders: List<OrderDto>,
    private val onActionClick: (OrderDto) -> Unit,
) : RecyclerView.Adapter<OrderAdapter.VH>() {

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvOrderNum   : TextView      = view.findViewById(R.id.tvOrderNumber)
        val tvTableType  : TextView      = view.findViewById(R.id.tvTableType)
        val tvTime       : TextView      = view.findViewById(R.id.tvTime)
        val tvItems      : TextView      = view.findViewById(R.id.tvItems)
        val tvTotal      : TextView      = view.findViewById(R.id.tvTotal)
        val tvStatus     : TextView      = view.findViewById(R.id.tvStatus)
        val statusDot    : View          = view.findViewById(R.id.statusDot)
        val layoutChip   : View          = view.findViewById(R.id.layoutStatusChip)
        val btnAction    : MaterialButton= view.findViewById(R.id.btnAction)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int) = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_order, parent, false)
    )

    override fun getItemCount() = orders.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val order = orders[position]
        val ctx   = holder.itemView.context

        holder.tvOrderNum.text = order.invoice
        holder.tvTime.text     = order.time.take(5) // HH:mm
        holder.tvTotal.text    = "Total: $%.2f".format(order.total)

        val location = when (order.type) {
            "MESA"      -> "🪑 Mesa ${order.table ?: "—"}"
            "LLEVAR"    -> "🛍 Para Llevar"
            "DOMICILIO" -> "🛵 Domicilio"
            else        -> order.type
        }
        holder.tvTableType.text = location

        val itemsSummary = order.items.take(3).joinToString("  •  ") { "${it.qty}× ${it.name}" }
        val more = if (order.items.size > 3) "\n+${order.items.size - 3} más" else ""
        holder.tvItems.text = itemsSummary + more

        // Colores del chip de estado desde recursos
        data class StatusStyle(
            val label: String,
            val textColor: Int,
            val bgColor: Int,
            val dotColor: Int,
        )

        val style = when (order.status) {
            "PENDIENTE" -> StatusStyle(
                "PENDIENTE",
                ContextCompat.getColor(ctx, R.color.status_pending_text),
                ContextCompat.getColor(ctx, R.color.status_pending_bg),
                ContextCompat.getColor(ctx, R.color.status_pending_dot),
            )
            "PREPARANDO" -> StatusStyle(
                "PREPARANDO",
                ContextCompat.getColor(ctx, R.color.status_preparing_text),
                ContextCompat.getColor(ctx, R.color.status_preparing_bg),
                ContextCompat.getColor(ctx, R.color.status_preparing_dot),
            )
            "LISTO_FACTURAR" -> StatusStyle(
                "LISTO PARA COBRAR",
                ContextCompat.getColor(ctx, R.color.status_ready_text),
                ContextCompat.getColor(ctx, R.color.status_ready_bg),
                ContextCompat.getColor(ctx, R.color.status_ready_dot),
            )
            "FACTURADO" -> StatusStyle(
                "FACTURADO",
                ContextCompat.getColor(ctx, R.color.status_invoiced_text),
                ContextCompat.getColor(ctx, R.color.status_invoiced_bg),
                ContextCompat.getColor(ctx, R.color.status_invoiced_dot),
            )
            else -> StatusStyle(
                order.status,
                ContextCompat.getColor(ctx, R.color.text_secondary),
                ContextCompat.getColor(ctx, R.color.background),
                ContextCompat.getColor(ctx, R.color.text_hint),
            )
        }

        holder.tvStatus.text = style.label
        holder.tvStatus.setTextColor(style.textColor)
        holder.layoutChip.setBackgroundColor(style.bgColor)
        holder.statusDot.setBackgroundColor(style.dotColor)

        val actionable = order.status in listOf("PENDIENTE", "PREPARANDO")
        holder.btnAction.visibility = if (actionable) View.VISIBLE else View.GONE
        if (actionable) {
            holder.btnAction.setOnClickListener { onActionClick(order) }
        }

        holder.itemView.setOnClickListener { onActionClick(order) }
    }
}
