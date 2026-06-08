package com.cafeteria.pos

import android.os.Bundle
import android.view.View
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.cafeteria.pos.adapters.OrderAdapter
import com.cafeteria.pos.data.OrderDto
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.data.StatusUpdate
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ActiveOrdersActivity : AppCompatActivity() {

    private val orders = mutableListOf<OrderDto>()
    private lateinit var orderAdapter: OrderAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_active_orders)

        supportActionBar?.title = "Mis Pedidos Activos"
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val swipeRefresh = findViewById<SwipeRefreshLayout>(R.id.swipeRefresh)
        val rvOrders     = findViewById<RecyclerView>(R.id.rvOrders)
        val tvEmpty      = findViewById<TextView>(R.id.tvEmpty)
        val progressBar  = findViewById<ProgressBar>(R.id.progressBar)

        orderAdapter = OrderAdapter(orders,
            onActionClick = { order -> showActionDialog(order) }
        )
        rvOrders.layoutManager = LinearLayoutManager(this)
        rvOrders.adapter = orderAdapter

        swipeRefresh.setOnRefreshListener {
            loadOrders(null) { swipeRefresh.isRefreshing = false }
        }

        loadOrders(progressBar)

        // Auto-refresh cada 20 segundos
        lifecycleScope.launch {
            while (true) {
                delay(20_000)
                loadOrders(null)
            }
        }
    }

    private fun loadOrders(progressBar: ProgressBar?, onDone: (() -> Unit)? = null) {
        progressBar?.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val branchId = RetrofitClient.branchId(this@ActiveOrdersActivity)
                val resp = RetrofitClient.api(this@ActiveOrdersActivity).getActiveOrders(branchId)
                if (resp.isSuccessful) {
                    val tvEmpty = findViewById<TextView>(R.id.tvEmpty)
                    val fresh = resp.body() ?: emptyList()
                    orders.clear()
                    orders.addAll(fresh)
                    orderAdapter.notifyDataSetChanged()
                    tvEmpty.visibility = if (fresh.isEmpty()) View.VISIBLE else View.GONE
                }
            } catch (_: Exception) {
                Toast.makeText(this@ActiveOrdersActivity, "Error actualizando pedidos", Toast.LENGTH_SHORT).show()
            } finally {
                progressBar?.visibility = View.GONE
                onDone?.invoke()
            }
        }
    }

    private fun showActionDialog(order: OrderDto) {
        val options = mutableListOf<String>()
        val actions = mutableListOf<() -> Unit>()

        when (order.status) {
            "PENDIENTE" -> {
                options.add("▶ Marcar En Preparación")
                actions.add { updateStatus(order.id, "PREPARANDO") }
                options.add("✅ Listo para Cobrar")
                actions.add { markReadyForInvoice(order.id) }
            }
            "PREPARANDO" -> {
                options.add("✅ Listo para Cobrar")
                actions.add { markReadyForInvoice(order.id) }
            }
        }

        if (options.isEmpty()) {
            Toast.makeText(this, "Pedido ${order.status} — sin acciones disponibles", Toast.LENGTH_SHORT).show()
            return
        }

        AlertDialog.Builder(this)
            .setTitle("Pedido ${order.invoice}")
            .setItems(options.toTypedArray()) { _, which -> actions[which]() }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun updateStatus(orderId: Int, newStatus: String) {
        lifecycleScope.launch {
            try {
                val resp = RetrofitClient.api(this@ActiveOrdersActivity)
                    .updateStatus(orderId, StatusUpdate(newStatus))
                if (resp.isSuccessful) {
                    val label = if (newStatus == "PREPARANDO") "en preparación" else newStatus
                    Toast.makeText(this@ActiveOrdersActivity, "Pedido marcado como $label", Toast.LENGTH_SHORT).show()
                    loadOrders(null)
                } else {
                    Toast.makeText(this@ActiveOrdersActivity, "Error al actualizar estado", Toast.LENGTH_SHORT).show()
                }
            } catch (_: Exception) {
                Toast.makeText(this@ActiveOrdersActivity, "Error de conexión", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun markReadyForInvoice(orderId: Int) {
        AlertDialog.Builder(this)
            .setTitle("¿Cerrar Pedido?")
            .setMessage("El pedido pasará a la cola de facturación del cajero. No se podrán agregar más items.")
            .setPositiveButton("Confirmar") { _, _ ->
                lifecycleScope.launch {
                    try {
                        val resp = RetrofitClient.api(this@ActiveOrdersActivity)
                            .markReadyForInvoice(orderId)
                        if (resp.isSuccessful) {
                            Toast.makeText(this@ActiveOrdersActivity,
                                "✅ Pedido enviado a caja para cobro", Toast.LENGTH_LONG).show()
                            loadOrders(null)
                        } else {
                            Toast.makeText(this@ActiveOrdersActivity,
                                "Error: ${resp.code()}", Toast.LENGTH_SHORT).show()
                        }
                    } catch (_: Exception) {
                        Toast.makeText(this@ActiveOrdersActivity, "Error de conexión", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    override fun onSupportNavigateUp(): Boolean { finish(); return true }
}
