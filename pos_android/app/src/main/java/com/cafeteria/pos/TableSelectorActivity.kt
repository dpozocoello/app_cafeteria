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

        binding.cgServiceType.setOnCheckedStateChangeListener { group, checkedIds ->
            if (checkedIds.isEmpty()) {
                binding.chipMesa.isChecked = true
                return@setOnCheckedStateChangeListener
            }
            when (checkedIds[0]) {
                R.id.chipMesa -> {
                    currentServiceType = "MESA"
                    binding.tilCustomerAddress.visibility = View.GONE
                    binding.rvTables.visibility = View.VISIBLE
                    binding.tvTablesLabel.visibility = View.VISIBLE
                }
                R.id.chipLlevar -> {
                    currentServiceType = "LLEVAR"
                    binding.tilCustomerAddress.visibility = View.GONE
                    binding.rvTables.visibility = View.GONE
                    binding.tvTablesLabel.visibility = View.GONE
                }
                R.id.chipDomicilio -> {
                    currentServiceType = "DOMICILIO"
                    binding.tilCustomerAddress.visibility = View.VISIBLE
                    binding.rvTables.visibility = View.GONE
                    binding.tvTablesLabel.visibility = View.GONE
                }
            }
            updateContinueButton()
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
}
