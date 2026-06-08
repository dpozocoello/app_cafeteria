package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.data.RetrofitClient

class HomeActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (!RetrofitClient.isLoggedIn(this)) {
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        setContentView(R.layout.activity_home)

        val tvWelcome    = findViewById<TextView>(R.id.tvWelcome)
        val tvServer     = findViewById<TextView>(R.id.tvServer)
        val btnNewOrder  = findViewById<Button>(R.id.btnNewOrder)
        val btnMyOrders  = findViewById<Button>(R.id.btnMyOrders)
        val btnLogout    = findViewById<Button>(R.id.btnLogout)

        tvWelcome.text = "Bienvenido, ${RetrofitClient.fullName(this)}"
        tvServer.text  = RetrofitClient.serverUrl(this)

        btnNewOrder.setOnClickListener {
            CartManager.clear()
            startActivity(Intent(this, TableSelectorActivity::class.java))
        }

        btnMyOrders.setOnClickListener {
            startActivity(Intent(this, ActiveOrdersActivity::class.java))
        }

        btnLogout.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Cerrar Sesión")
                .setMessage("¿Desea cerrar su sesión?")
                .setPositiveButton("Sí") { _, _ ->
                    RetrofitClient.clearSession(this)
                    startActivity(Intent(this, LoginActivity::class.java))
                    finish()
                }
                .setNegativeButton("Cancelar", null)
                .show()
        }
    }

    // Actualizar badge de pedidos activos al volver
    override fun onResume() {
        super.onResume()
        // Podría cargar el conteo de pedidos aquí para mostrarlo en el botón
    }
}
