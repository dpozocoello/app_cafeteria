package com.cafeteria.pos

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import com.cafeteria.pos.adapters.TableAdapter
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.data.TableDto
import com.cafeteria.pos.databinding.ActivityTableSelectorBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class TableSelectorActivity : AppCompatActivity() {

    private lateinit var binding: ActivityTableSelectorBinding
    private lateinit var adapter: TableAdapter
    private var selectedTable: TableDto? = null
    private var currentServiceType: String = "MESA"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityTableSelectorBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.setNavigationOnClickListener {
            finish()
        }

        adapter = TableAdapter { table ->
            selectedTable = table
            updateContinueButton()
        }

        binding.rvTables.layoutManager = GridLayoutManager(this, 3)
        binding.rvTables.adapter = adapter

        // QR Scanner button
        binding.btnScanQr.setOnClickListener {
            val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", "") ?: ""
            val intent = Intent(this, QRScannerActivity::class.java).apply {
                putExtra("server_url", serverUrl)
                putExtra("table_name", selectedTable?.number?.toString() ?: "")
                putExtra("is_pairing", false)
            }
            startActivityForResult(intent, 100)
        }

        // Service type chips
        binding.chipMesa.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                currentServiceType = "MESA"
                binding.tilCustomerAddress.visibility = View.GONE
                binding.rvTables.visibility = View.VISIBLE
                binding.tvTablesLabel.visibility = View.VISIBLE
            }
        }

        binding.chipLlevar.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                currentServiceType = "LLEVAR"
                binding.tilCustomerAddress.visibility = View.GONE
                binding.rvTables.visibility = View.GONE
                binding.tvTablesLabel.visibility = View.GONE
            }
        }

        binding.chipDomicilio.setOnCheckedChangeListener { _, isChecked ->
            if (isChecked) {
                currentServiceType = "DOMICILIO"
                binding.tilCustomerAddress.visibility = View.VISIBLE
                binding.rvTables.visibility = View.GONE
                binding.tvTablesLabel.visibility = View.GONE
            }
        }

        binding.btnContinue.setOnClickListener {
            CartManager.clear()
            CartManager.serviceType = currentServiceType
            CartManager.currentTableId = selectedTable?.id
            
            val name = binding.etCustomerName.text.toString().trim()
            if (name.isNotEmpty()) {
                CartManager.customerName = name
            }
            if (currentServiceType == "DOMICILIO") {
                val address = binding.etCustomerAddress.text.toString().trim()
                CartManager.customerAddress = address
            }

            startActivity(Intent(this, MenuActivity::class.java))
        }

        loadTables()
    }

    private fun updateContinueButton() {
        when (currentServiceType) {
            "MESA" -> {
                if (selectedTable != null) {
                    binding.btnContinue.isEnabled = true
                    binding.btnContinue.text = "CONTINUAR: MESA ${selectedTable!!.number} →"
                } else {
                    binding.btnContinue.isEnabled = false
                    binding.btnContinue.text = "CONTINUAR AL MENÚ →"
                }
            }
            "LLEVAR" -> {
                binding.btnContinue.isEnabled = true
                binding.btnContinue.text = "CONTINUAR: PARA LLEVAR →"
            }
            "DOMICILIO" -> {
                binding.btnContinue.isEnabled = true
                binding.btnContinue.text = "CONTINUAR: A DOMICILIO →"
            }
        }
    }

    private fun loadTables() {
        binding.progressBar.visibility = View.VISIBLE
        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "") ?: return

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.getTables()

                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    if (response.isSuccessful && response.body() != null) {
                        adapter.setTables(response.body()!!)
                    } else {
                        Toast.makeText(this@TableSelectorActivity, "Error al cargar mesas", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    Toast.makeText(this@TableSelectorActivity, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == 100 && resultCode == RESULT_OK) {
            val tableId = data?.getIntExtra("table_id", -1)
            if (tableId != null && tableId != -1) {
                // Buscar la mesa seleccionada y marcarla
                adapter.setSelectedTableId(tableId)
                selectedTable = adapter.getTableById(tableId)
                updateContinueButton()
                Toast.makeText(this, "Mesa $tableId seleccionada", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
