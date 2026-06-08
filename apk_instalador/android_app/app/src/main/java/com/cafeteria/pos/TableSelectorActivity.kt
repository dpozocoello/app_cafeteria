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
import kotlinx.coroutines.launch

class TableSelectorActivity : AppCompatActivity() {

    private lateinit var tableAdapter: TableAdapter
    private val tables = mutableListOf<TableDto>()
    private var serviceType = "MESA"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_table_selector)

        supportActionBar?.title = "Seleccionar Mesa"
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val rgService    = findViewById<RadioGroup>(R.id.rgServiceType)
        val tvTablesLabel= findViewById<TextView>(R.id.tvTablesLabel)
        val rvTables     = findViewById<RecyclerView>(R.id.rvTables)
        val etCustomer   = findViewById<EditText>(R.id.etCustomerName)
        val etAddress    = findViewById<EditText>(R.id.etAddress)
        val layoutAddress= findViewById<View>(R.id.layoutAddress)
        val btnContinue  = findViewById<Button>(R.id.btnContinue)
        val progressBar  = findViewById<ProgressBar>(R.id.progressBar)

        tableAdapter = TableAdapter(tables) { table ->
            CartManager.selectedTable = table
            updateContinueButton(btnContinue)
            // Feedback visual
            Toast.makeText(this, "Mesa ${table.number} seleccionada", Toast.LENGTH_SHORT).show()
        }

        rvTables.layoutManager = GridLayoutManager(this, 3)
        rvTables.adapter = tableAdapter

        // Control de tipo de servicio
        rgService.setOnCheckedChangeListener { _, checkedId ->
            serviceType = when (checkedId) {
                R.id.rbMesa      -> "MESA"
                R.id.rbLlevar    -> "LLEVAR"
                R.id.rbDomicilio -> "DOMICILIO"
                else             -> "MESA"
            }
            CartManager.serviceType = serviceType
            tvTablesLabel.visibility = if (serviceType == "MESA") View.VISIBLE else View.GONE
            rvTables.visibility      = if (serviceType == "MESA") View.VISIBLE else View.GONE
            layoutAddress.visibility = if (serviceType == "DOMICILIO") View.VISIBLE else View.GONE
            if (serviceType != "MESA") CartManager.selectedTable = null
            updateContinueButton(btnContinue)
        }

        btnContinue.setOnClickListener {
            CartManager.customerName    = etCustomer.text.toString().trim().ifEmpty { "CONSUMIDOR FINAL" }
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

    private fun updateContinueButton(btn: Button) {
        btn.isEnabled = when (serviceType) {
            "MESA"      -> CartManager.selectedTable != null
            "LLEVAR"    -> true
            "DOMICILIO" -> true
            else        -> false
        }
    }

    override fun onSupportNavigateUp(): Boolean { finish(); return true }
}
