package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.adapters.TableAdapter
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.data.TableDto
import com.google.android.material.chip.ChipGroup
import com.google.android.material.chip.Chip
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputLayout
import kotlinx.coroutines.launch

class TableSelectorActivity : AppCompatActivity() {

    private lateinit var tableAdapter: TableAdapter
    private val tables = mutableListOf<TableDto>()
    private var serviceType = "MESA"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_table_selector)

        supportActionBar?.title = "Nuevo Pedido"
        supportActionBar?.subtitle = "Paso 1 de 2"
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val chipGroup        = findViewById<ChipGroup>(R.id.chipGroupServiceType)
        val layoutTables     = findViewById<View>(R.id.layoutTablesSection)
        val rvTables         = findViewById<RecyclerView>(R.id.rvTables)
        val etCustomer       = findViewById<EditText>(R.id.etCustomerName)
        val tilAddress       = findViewById<TextInputLayout>(R.id.tilAddress)
        val etAddress        = findViewById<EditText>(R.id.etAddress)
        val layoutNoTables   = findViewById<View>(R.id.layoutNoTablesNeeded)
        val tvNoTableMsg     = findViewById<TextView>(R.id.tvNoTableMessage)
        val tvNoTableSub     = findViewById<TextView>(R.id.tvNoTableSubtitle)
        val btnContinue      = findViewById<MaterialButton>(R.id.btnContinue)
        val progressBar      = findViewById<ProgressBar>(R.id.progressBar)

        tableAdapter = TableAdapter(tables) { table ->
            CartManager.selectedTable = table
            updateContinueButton(btnContinue)
            Toast.makeText(this, "Mesa ${table.number} seleccionada", Toast.LENGTH_SHORT).show()
        }
        rvTables.layoutManager = GridLayoutManager(this, 3)
        rvTables.adapter = tableAdapter

        chipGroup.setOnCheckedStateChangeListener { _, checkedIds ->
            val id = checkedIds.firstOrNull() ?: return@setOnCheckedStateChangeListener
            serviceType = when (id) {
                R.id.chipMesa      -> "MESA"
                R.id.chipLlevar    -> "LLEVAR"
                R.id.chipDomicilio -> "DOMICILIO"
                else               -> "MESA"
            }
            CartManager.serviceType = serviceType

            val isMesa = serviceType == "MESA"
            val isDomicilio = serviceType == "DOMICILIO"

            layoutTables.visibility = if (isMesa) View.VISIBLE else View.GONE
            rvTables.visibility     = if (isMesa) View.VISIBLE else View.GONE
            layoutNoTables.visibility = if (!isMesa) View.VISIBLE else View.GONE
            tilAddress.visibility   = if (isDomicilio) View.VISIBLE else View.GONE

            when (serviceType) {
                "LLEVAR" -> {
                    tvNoTableMsg.text = "🛍️ Para Llevar"
                    tvNoTableSub.text = "El pedido se entregará en mostrador"
                }
                "DOMICILIO" -> {
                    tvNoTableMsg.text = "🛵 Entrega a Domicilio"
                    tvNoTableSub.text = "Ingresa la dirección de entrega arriba"
                }
            }

            if (!isMesa) CartManager.selectedTable = null
            updateContinueButton(btnContinue)
        }

        btnContinue.setOnClickListener {
            CartManager.customerName = etCustomer.text.toString().trim().ifEmpty { "CONSUMIDOR FINAL" }
            CartManager.customerAddress = etAddress.text.toString().trim()
            startActivity(Intent(this, MenuActivity::class.java))
        }

        loadTables(progressBar)
    }

    private fun loadTables(progressBar: ProgressBar) {
        progressBar.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val resp = RetrofitClient.api(this@TableSelectorActivity).getTables()
                if (resp.isSuccessful) {
                    tables.clear()
                    tables.addAll(resp.body() ?: emptyList())
                    tableAdapter.notifyDataSetChanged()
                }
            } catch (_: Exception) {
                Toast.makeText(this@TableSelectorActivity, "Error cargando mesas", Toast.LENGTH_SHORT).show()
            } finally {
                progressBar.visibility = View.GONE
            }
        }
    }

    private fun updateContinueButton(btn: MaterialButton) {
        val enabled = when (serviceType) {
            "MESA"      -> CartManager.selectedTable != null
            "LLEVAR"    -> true
            "DOMICILIO" -> true
            else        -> false
        }
        btn.isEnabled = enabled
        btn.text = when {
            serviceType == "MESA" && CartManager.selectedTable != null ->
                "Continuar: Mesa ${CartManager.selectedTable!!.number} →"
            serviceType == "LLEVAR" -> "Continuar: Para Llevar →"
            serviceType == "DOMICILIO" -> "Continuar: A Domicilio →"
            else -> "Continuar al Menú →"
        }
    }

    override fun onSupportNavigateUp(): Boolean { finish(); return true }
}
