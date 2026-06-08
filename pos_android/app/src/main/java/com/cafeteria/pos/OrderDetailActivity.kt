package com.cafeteria.pos

import android.content.Context
import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.OrderResponseDto
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.data.StatusUpdateDto
import com.cafeteria.pos.databinding.ActivityOrderDetailBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class OrderDetailActivity : AppCompatActivity() {

    private lateinit var binding: ActivityOrderDetailBinding
    private var orderId: Int = 0
    private var serverUrl = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityOrderDetailBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""

        orderId = intent.getIntExtra("order_id", 0)
        if (orderId == 0) {
            finish()
            return
        }

        binding.toolbar.setNavigationOnClickListener { finish() }

        binding.btnPrepare.setOnClickListener { updateStatus("PREPARANDO") }
        binding.btnReady.setOnClickListener { updateStatus("LISTO_COBRAR") }

        loadOrderDetail()
    }

    private fun loadOrderDetail() {
        binding.progressBar.visibility = View.VISIBLE
        binding.scrollView.visibility = View.GONE
        binding.bottomBar.visibility = View.GONE

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.getOrderById(orderId)

                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    if (response.isSuccessful && response.body() != null) {
                        displayOrder(response.body()!!)
                    } else {
                        Toast.makeText(this@OrderDetailActivity, "Error al cargar pedido", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    Toast.makeText(this@OrderDetailActivity, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun displayOrder(order: OrderResponseDto) {
        binding.scrollView.visibility = View.VISIBLE
        binding.bottomBar.visibility = View.VISIBLE

        binding.toolbar.subtitle = order.time
        binding.tvOrderNumber.text = "Pedido ${order.invoice}"
        binding.tvStatus.text = "Estado: ${order.status}"
        binding.tvServiceType.text = "Servicio: ${if (order.type == "MESA") "MESA ${order.table}" else order.type}"
        binding.tvCustomer.text = "Cliente: ${order.customer ?: "N/A"}"
        binding.tvTotal.text = String.format("$%.2f", order.total)

        binding.llItemsContainer.removeAllViews()
        for (item in order.items) {
            val tv = TextView(this).apply {
                text = "${item.qty}x ${item.name}   -   $String.format(\"%.2f\", item.subtotal)"
                textSize = 15f
                setPadding(0, 8, 0, 8)
                setTextColor(resources.getColor(android.R.color.black, null))
            }
            binding.llItemsContainer.addView(tv)
        }

        // Configure buttons
        binding.btnPrepare.visibility = View.GONE
        binding.btnReady.visibility = View.GONE

        if (order.status == "PENDIENTE") {
            binding.btnPrepare.visibility = View.VISIBLE
        } else if (order.status == "PREPARANDO") {
            binding.btnReady.visibility = View.VISIBLE
        }
    }

    private fun updateStatus(newStatus: String) {
        binding.progressBar.visibility = View.VISIBLE
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = if (newStatus == "LISTO_COBRAR") {
                    api.markReadyForInvoice(orderId)
                } else {
                    api.updateOrderStatus(orderId, StatusUpdateDto(newStatus))
                }

                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    if (response.isSuccessful) {
                        Toast.makeText(this@OrderDetailActivity, "Estado actualizado", Toast.LENGTH_SHORT).show()
                        loadOrderDetail() // Reload to reflect changes
                    } else {
                        Toast.makeText(this@OrderDetailActivity, "Error al actualizar estado", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    Toast.makeText(this@OrderDetailActivity, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
