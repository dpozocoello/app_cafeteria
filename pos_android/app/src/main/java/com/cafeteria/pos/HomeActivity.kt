package com.cafeteria.pos

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.databinding.ActivityHomeBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class HomeActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHomeBinding
    private var serverUrl: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityHomeBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""
        val fullName = prefs.getString("full_name", "Mesero") ?: "Mesero"

        binding.toolbar.title = "Hola, $fullName"

        binding.cardNewOrder.setOnClickListener {
            startActivity(Intent(this, TableSelectorActivity::class.java))
        }

        binding.cardActiveOrders.setOnClickListener {
            startActivity(Intent(this, ActiveOrdersActivity::class.java))
        }

        binding.btnLogout.setOnClickListener {
            prefs.edit().remove("auth_token").remove("user_id").remove("full_name").apply()
            RetrofitClient.authToken = null
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
        }
    }

    override fun onResume() {
        super.onResume()
        loadActiveOrdersCount()
    }

    private fun loadActiveOrdersCount() {
        if (serverUrl.isEmpty() || RetrofitClient.authToken == null) return

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.getActiveOrders()

                withContext(Dispatchers.Main) {
                    if (response.isSuccessful && response.body() != null) {
                        val activeOrders = response.body()!!
                        binding.tvActiveCount.text = activeOrders.size.toString()
                        binding.tvOrdersDesc.text = "${activeOrders.size} pedidos en curso"
                        binding.chipStatus.text = "Conectado"
                        binding.chipStatus.setTextColor(getColor(android.R.color.holo_green_dark))
                    } else {
                        binding.chipStatus.text = "Error de sincronización"
                        binding.chipStatus.setTextColor(getColor(android.R.color.holo_red_dark))
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.chipStatus.text = "Desconectado"
                    binding.chipStatus.setTextColor(getColor(android.R.color.holo_red_dark))
                }
            }
        }
    }
}
