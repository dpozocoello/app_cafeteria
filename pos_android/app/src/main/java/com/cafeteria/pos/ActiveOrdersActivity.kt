package com.cafeteria.pos

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.cafeteria.pos.adapters.OrderAdapter
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.databinding.ActivityActiveOrdersBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ActiveOrdersActivity : AppCompatActivity() {

    private lateinit var binding: ActivityActiveOrdersBinding
    private lateinit var adapter: OrderAdapter
    private var serverUrl = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityActiveOrdersBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""

        binding.toolbar.setNavigationOnClickListener { finish() }

        adapter = OrderAdapter { order ->
            val intent = Intent(this, OrderDetailActivity::class.java)
            intent.putExtra("order_id", order.id)
            startActivity(intent)
        }
        binding.rvOrders.layoutManager = LinearLayoutManager(this)
        binding.rvOrders.adapter = adapter
    }

    override fun onResume() {
        super.onResume()
        loadOrders()
    }

    private fun loadOrders() {
        binding.progressBar.visibility = View.VISIBLE
        binding.tvEmpty.visibility = View.GONE
        binding.rvOrders.visibility = View.GONE

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.getActiveOrders()

                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    if (response.isSuccessful && response.body() != null) {
                        val orders = response.body()!!
                        if (orders.isEmpty()) {
                            binding.tvEmpty.visibility = View.VISIBLE
                        } else {
                            adapter.setItems(orders)
                            binding.rvOrders.visibility = View.VISIBLE
                        }
                    } else {
                        Toast.makeText(this@ActiveOrdersActivity, "Error al cargar pedidos", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    Toast.makeText(this@ActiveOrdersActivity, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
