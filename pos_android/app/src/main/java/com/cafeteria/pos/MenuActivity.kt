package com.cafeteria.pos

import android.app.Dialog
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.cafeteria.pos.adapters.CartAdapter
import com.cafeteria.pos.adapters.MenuProductAdapter
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.MenuDto
import com.cafeteria.pos.data.OrderCreateDto
import com.cafeteria.pos.data.OrderItemCreate
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.databinding.ActivityMenuBinding
import com.cafeteria.pos.databinding.DialogCartBinding
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MenuActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMenuBinding
    private lateinit var adapter: MenuProductAdapter
    private var allMenus = listOf<MenuDto>()
    private var serverUrl = ""
    private var userId = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMenuBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""
        userId = prefs.getInt("user_id", 0)

        // Setup Toolbar Text
        binding.toolbar.setNavigationOnClickListener { finish() }
        val serviceText = when(CartManager.serviceType) {
            "MESA" -> "Mesa ${CartManager.currentTableId ?: "?"}"
            "LLEVAR" -> "Para Llevar"
            "DOMICILIO" -> "A Domicilio"
            else -> ""
        }
        binding.toolbar.title = serviceText

        adapter = MenuProductAdapter { item ->
            CartManager.addItem(item)
            updateCartBar()
            Toast.makeText(this, "${item.name} agregado", Toast.LENGTH_SHORT).show()
        }
        binding.rvProducts.layoutManager = LinearLayoutManager(this)
        binding.rvProducts.adapter = adapter

        binding.tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                val menu = allMenus.find { it.name == tab?.text }
                if (menu != null) {
                    adapter.setItems(menu.items)
                }
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) {}
        })

        binding.btnViewCart.setOnClickListener {
            showCartDialog()
        }

        updateCartBar()
        loadMenus()
    }

    private fun updateCartBar() {
        val count = CartManager.getTotalItems()
        val total = CartManager.getTotal()
        
        binding.tvCartSummary.text = "🛒 $count items        $${String.format("%.2f", total)}"
        binding.btnViewCart.text = "VER CARRITO ($count)"
        binding.bottomBar.visibility = if (count > 0) View.VISIBLE else View.GONE
    }

    private fun loadMenus() {
        binding.progressBar.visibility = View.VISIBLE
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.getMenus()

                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    if (response.isSuccessful && response.body() != null) {
                        allMenus = response.body()!!
                        for (menu in allMenus) {
                            binding.tabLayout.addTab(binding.tabLayout.newTab().setText(menu.name))
                        }
                        if (allMenus.isNotEmpty()) {
                            adapter.setItems(allMenus.first().items)
                        }
                    } else {
                        Toast.makeText(this@MenuActivity, "Error al cargar menús", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.progressBar.visibility = View.GONE
                    Toast.makeText(this@MenuActivity, "Error: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showCartDialog() {
        val dialog = Dialog(this, android.R.style.Theme_DeviceDefault_Light_NoActionBar_Fullscreen)
        val dialogBinding = DialogCartBinding.inflate(layoutInflater)
        dialog.setContentView(dialogBinding.root)

        val cartAdapter = CartAdapter(
            onIncrease = { item ->
                CartManager.addItem(item)
                dialogBinding.rvCartItems.adapter?.notifyDataSetChanged()
                updateDialogTotals(dialogBinding)
                updateCartBar()
            },
            onDecrease = { productId ->
                CartManager.removeItem(productId)
                dialogBinding.rvCartItems.adapter?.notifyDataSetChanged()
                updateDialogTotals(dialogBinding)
                updateCartBar()
                if (CartManager.getTotalItems() == 0) dialog.dismiss()
            }
        )

        dialogBinding.rvCartItems.layoutManager = LinearLayoutManager(this)
        dialogBinding.rvCartItems.adapter = cartAdapter
        cartAdapter.setItems(CartManager.getItems())

        updateDialogTotals(dialogBinding)

        dialogBinding.dialogToolbar.setNavigationOnClickListener {
            dialog.dismiss()
        }

        dialogBinding.btnSubmitOrder.setOnClickListener {
            val notes = dialogBinding.etOrderNotes.text.toString().trim()
            submitOrder(notes, dialog)
        }

        dialog.show()
    }

    private fun updateDialogTotals(binding: DialogCartBinding) {
        binding.tvSubtotal.text = String.format("$%.2f", CartManager.getSubtotal())
        binding.tvTax.text = String.format("$%.2f", CartManager.getTax())
        binding.tvTotal.text = String.format("$%.2f", CartManager.getTotal())
    }

    private fun submitOrder(notes: String, dialog: Dialog) {
        val orderItems = CartManager.getItems().map {
            OrderItemCreate(product_id = it.first.product_id, quantity = it.second, notes = null)
        }

        val order = OrderCreateDto(
            service_type = CartManager.serviceType,
            table_id = CartManager.currentTableId,
            customer_name = CartManager.customerName ?: "CONSUMIDOR FINAL",
            customer_address = CartManager.customerAddress,
            notes = if (notes.isNotEmpty()) notes else null,
            items = orderItems,
            user_id = userId
        )

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                val response = api.createOrder(order)

                withContext(Dispatchers.Main) {
                    if (response.isSuccessful) {
                        Toast.makeText(this@MenuActivity, "Pedido enviado exitosamente", Toast.LENGTH_LONG).show()
                        CartManager.clear()
                        dialog.dismiss()
                        // Go back to Home
                        val intent = Intent(this@MenuActivity, HomeActivity::class.java)
                        intent.flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK
                        startActivity(intent)
                        finish()
                    } else {
                        Toast.makeText(this@MenuActivity, "Error al enviar: ${response.code()}", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MenuActivity, "Excepción: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
