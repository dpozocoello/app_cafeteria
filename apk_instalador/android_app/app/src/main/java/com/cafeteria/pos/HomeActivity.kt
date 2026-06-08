package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView
import androidx.lifecycle.lifecycleScope
import com.cafeteria.pos.data.RetrofitClient
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.launch
import java.util.Calendar

class HomeActivity : AppCompatActivity() {

    private lateinit var tvOrderBadge: TextView
    private lateinit var tvActiveOrdersCount: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!RetrofitClient.isLoggedIn(this)) {
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_home)

        val tvWelcome         = findViewById<TextView>(R.id.tvWelcome)
        val tvServer          = findViewById<TextView>(R.id.tvServer)
        val tvServerAddress   = findViewById<TextView>(R.id.tvServerAddress)
        val tvUserRole        = findViewById<TextView>(R.id.tvUserRole)
        val cardNewOrder      = findViewById<CardView>(R.id.cardNewOrder)
        val cardMyOrders      = findViewById<CardView>(R.id.cardMyOrders)
        val btnLogout         = findViewById<MaterialButton>(R.id.btnLogout)
        tvOrderBadge          = findViewById(R.id.tvOrderBadge)
        tvActiveOrdersCount   = findViewById(R.id.tvActiveOrdersCount)

        val name = RetrofitClient.fullName(this).ifEmpty { "Mesero" }
        val greeting = when (Calendar.getInstance().get(Calendar.HOUR_OF_DAY)) {
            in 5..11  -> "Buenos días"
            in 12..17 -> "Buenas tardes"
            else      -> "Buenas noches"
        }
        tvWelcome.text = "$greeting, $name"

        val serverUrl = RetrofitClient.serverUrl(this)
        tvServer.text = serverUrl.removePrefix("http://").removePrefix("https://")
        tvServerAddress.text = serverUrl.removePrefix("http://").removePrefix("https://")
        tvUserRole.text = RetrofitClient.userRole(this).replaceFirstChar { it.uppercase() }

        cardNewOrder.setOnClickListener {
            CartManager.clear()
            startActivity(Intent(this, TableSelectorActivity::class.java))
        }

        cardMyOrders.setOnClickListener {
            startActivity(Intent(this, ActiveOrdersActivity::class.java))
        }

        btnLogout.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Cerrar Sesión")
                .setMessage("¿Desea cerrar su sesión actual?")
                .setPositiveButton("Cerrar Sesión") { _, _ ->
                    RetrofitClient.clearSession(this)
                    startActivity(Intent(this, LoginActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                    finish()
                }
                .setNegativeButton("Cancelar", null)
                .show()
        }
    }

    override fun onResume() {
        super.onResume()
        loadActiveOrderCount()
    }

    private fun loadActiveOrderCount() {
        lifecycleScope.launch {
            try {
                val branchId = RetrofitClient.branchId(this@HomeActivity)
                val resp = RetrofitClient.api(this@HomeActivity).getActiveOrders(branchId)
                if (resp.isSuccessful) {
                    val count = resp.body()?.filter {
                        it.status in listOf("PENDIENTE", "PREPARANDO", "LISTO_FACTURAR")
                    }?.size ?: 0
                    if (count > 0) {
                        tvOrderBadge.visibility = View.VISIBLE
                        tvOrderBadge.text = count.toString()
                        tvActiveOrdersCount.text = "$count pedido${if (count != 1) "s" else ""} en curso"
                    } else {
                        tvOrderBadge.visibility = View.GONE
                        tvActiveOrdersCount.text = "Sin pedidos activos ahora"
                    }
                }
            } catch (_: Exception) {
                tvActiveOrdersCount.text = "Ver estado en tiempo real"
            }
        }
    }
}
