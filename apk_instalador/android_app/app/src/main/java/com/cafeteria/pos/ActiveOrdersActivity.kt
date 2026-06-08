package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
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
import com.google.android.material.chip.Chip
import com.google.android.material.chip.ChipGroup
import com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ActiveOrdersActivity : AppCompatActivity() {

    private val allOrders   = mutableListOf<OrderDto>()
    private val shownOrders = mutableListOf<OrderDto>()
    private lateinit var orderAdapter: OrderAdapter
    private var activeFilter = "TODOS"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_active_orders)

        supportActionBar?.title = "Mis Pedidos Activos"
        supportActionBar?.subtitle = "Auto-actualización cada 20s"
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val chipGroup       = findViewById<ChipGroup>(R.id.chipGroupFilter)
        val swipeRefresh    = findViewById<SwipeRefreshLayout>(R.id.swipeRefresh)
        val rvOrders        = findViewById<RecyclerView>(R.id.rvOrders)
        val layoutEmpty     = findViewById<View>(R.id.layoutEmpty)
        val btnFirstOrder   = layoutEmpty.findViewById<View>(R.id.btnCreateFirstOrder)
        val fabNewOrder     = findViewById<ExtendedFloatingActionButton>(R.id.fabNewOrder)

        orderAdapter = OrderAdapter(shownOrders,
            onActionClick = { order -> showActionDialog(order) }
        )
        rvOrders.layoutManager = LinearLayoutManager(this)
        rvOrders.adapter = orderAdapter

        // Filtro por estado
        chipGroup.setOnCheckedStateChangeListener { _, checkedIds ->
            val id = checkedIds.firstOrNull() ?: return@setOnCheckedStateChangeListener
            activeFilter = when (id) {
                R.id.chipAll      -> "TODOS"
                R.id.chipPending  -> "PENDIENTE"
                R.id.chipPreparing-> "PREPARANDO"
                R.id.chipReady    -> "LISTO_FACTURAR"
                else              -> "TODOS"
            }
            applyFilter(layoutEmpty, rvOrders)
        }

        swipeRefresh.setOnRefreshListener {
            loadOrders { swipeRefresh.isRefreshing = false }
        }

        btnFirstOrder?.setOnClickListener { navigateToNewOrder() }
        fabNewOrder.setOnClickListener { navigateToNewOrder() }

        loadOrders()

        // Auto-refresh cada 20 segundos
        lifecycleScope.launch {
            while (true) {
                delay(20_000)
                loadOrders()
            }
        }
    }

    private fun navigateToNewOrder() {
        CartManager.clear()
        startActivity(Intent(this, TableSelectorActivity::class.java))
    }

    private fun loadOrders(onDone: (() -> Unit)? = null) {
        lifecycleScope.launch {
            try {
                val branchId = RetrofitClient.branchId(this@ActiveOrdersActivity)
                val resp = RetrofitClient.api(this@ActiveOrdersActivity).getActiveOrders(branchId)
                if (resp.isSuccessful) {
                    val fresh = resp.body() ?: emptyList()
                    allOrders.clear()
                    allOrders.addAll(fresh)
                    applyFilter(
                        findViewById(R.id.layoutEmpty),
                        findViewById(R.id.rvOrders)
                    )
                    updateChipBadges()
                }
            } catch (_: Exception) {
                Toast.makeText(this@ActiveOrdersActivity, "Error actualizando pedidos", Toast.LENGTH_SHORT).show()
            } finally {
                onDone?.invoke()
            }
        }
    }

    private fun applyFilter(layoutEmpty: View, rvOrders: RecyclerView) {
        shownOrders.clear()
        shownOrders.addAll(
            if (activeFilter == "TODOS") allOrders
            else allOrders.filter { it.status == activeFilter }
        )
        orderAdapter.notifyDataSetChanged()
        val isEmpty = shownOrders.isEmpty()
        layoutEmpty.visibility = if (isEmpty) View.VISIBLE else View.GONE
        rvOrders.visibility    = if (isEmpty) View.GONE  else View.VISIBLE
    }

    private fun updateChipBadges() {
        val pending  = allOrders.count { it.status == "PENDIENTE" }
        val preparing= allOrders.count { it.status == "PREPARANDO" }
        val ready    = allOrders.count { it.status == "LISTO_FACTURAR" }

        fun setChipText(id: Int, label: String, count: Int) {
            val chip = findViewById<Chip>(id) ?: return
            chip.text = if (count > 0) "$label ($count)" else label
        }
        setChipText(R.id.chipPending,   "Pendientes",  pending)
        setChipText(R.id.chipPreparing, "Preparando",  preparing)
        setChipText(R.id.chipReady,     "Listos",      ready)
    }

    private fun showActionDialog(order: OrderDto) {
        val options = mutableListOf<String>()
        val actions = mutableListOf<() -> Unit>()

        when (order.status) {
            "PENDIENTE" -> {
                options.add("▶  Marcar En Preparación")
                actions.add { updateStatus(order.id, "PREPARANDO") }
                options.add("✅  Listo para Cobrar")
                actions.add { markReadyForInvoice(order.id) }
            }
            "PREPARANDO" -> {
                options.add("✅  Listo para Cobrar")
                actions.add { markReadyForInvoice(order.id) }
            }
        }

        if (options.isEmpty()) {
            Toast.makeText(this, "Pedido ${order.status} — sin acciones disponibles", Toast.LENGTH_SHORT).show()
            return
        }

        AlertDialog.Builder(this)
            .setTitle("Pedido ${order.invoice}")
            .setMessage("Mesa/Tipo: ${order.table ?: order.type}")
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
                    Toast.makeText(this@ActiveOrdersActivity, "✓ Pedido marcado como $label", Toast.LENGTH_SHORT).show()
                    loadOrders()
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
            .setTitle("¿Enviar a Caja?")
            .setMessage("El pedido pasará a la cola de facturación. No podrás agregar más ítems.")
            .setPositiveButton("Confirmar") { _, _ ->
                lifecycleScope.launch {
                    try {
                        val resp = RetrofitClient.api(this@ActiveOrdersActivity)
                            .markReadyForInvoice(orderId)
                        if (resp.isSuccessful) {
                            Toast.makeText(this@ActiveOrdersActivity,
                                "✅ Pedido enviado a caja para cobro", Toast.LENGTH_LONG).show()
                            loadOrders()
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
