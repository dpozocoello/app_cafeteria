package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.cafeteria.pos.adapters.CartAdapter
import com.cafeteria.pos.adapters.MenuProductAdapter
import com.cafeteria.pos.data.OrderCreate
import com.cafeteria.pos.data.OrderItemCreate
import com.cafeteria.pos.data.RetrofitClient
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.launch

class MenuActivity : AppCompatActivity() {

    private val allMenus = mutableListOf<com.cafeteria.pos.data.MenuDto>()
    private lateinit var productAdapter: MenuProductAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_menu)

        val title = when (CartManager.serviceType) {
            "MESA"      -> "Mesa ${CartManager.selectedTable?.number ?: "—"}"
            "LLEVAR"    -> "Para Llevar"
            "DOMICILIO" -> "Domicilio"
            else        -> "Nuevo Pedido"
        }
        supportActionBar?.title = title
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val tabLayout   = findViewById<TabLayout>(R.id.tabMenus)
        val rvProducts  = findViewById<RecyclerView>(R.id.rvProducts)
        val btnCart     = findViewById<Button>(R.id.btnCart)
        val tvCartCount = findViewById<TextView>(R.id.tvCartCount)
        val progressBar = findViewById<ProgressBar>(R.id.progressBar)
        val tvEmpty     = findViewById<TextView>(R.id.tvEmpty)

        productAdapter = MenuProductAdapter { menuItem ->
            CartManager.addItem(menuItem)
            updateCartButton(btnCart, tvCartCount)
            Toast.makeText(this, "${menuItem.name} agregado", Toast.LENGTH_SHORT).show()
        }
        rvProducts.layoutManager = LinearLayoutManager(this)
        rvProducts.adapter = productAdapter

        btnCart.setOnClickListener { showCartDialog() }

        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                val menu = allMenus.getOrNull(tab.position) ?: return
                productAdapter.submitList(menu.items)
                tvEmpty.visibility = if (menu.items.isEmpty()) View.VISIBLE else View.GONE
            }
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })

        updateCartButton(btnCart, tvCartCount)
        loadMenus(tabLayout, progressBar, tvEmpty)
    }

    private fun loadMenus(tabs: TabLayout, progressBar: ProgressBar, tvEmpty: TextView) {
        progressBar.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val resp = RetrofitClient.api(this@MenuActivity).getMenus()
                if (resp.isSuccessful) {
                    allMenus.clear()
                    allMenus.addAll(resp.body()?.filter { it.items.isNotEmpty() } ?: emptyList())
                    tabs.removeAllTabs()
                    allMenus.forEach { tabs.addTab(tabs.newTab().setText(it.name)) }
                    if (allMenus.isNotEmpty()) {
                        productAdapter.submitList(allMenus[0].items)
                        tvEmpty.visibility = View.GONE
                    } else {
                        tvEmpty.visibility = View.VISIBLE
                        tvEmpty.text = "No hay menús activos disponibles"
                    }
                }
            } catch (_: Exception) {
                tvEmpty.visibility = View.VISIBLE
                tvEmpty.text = "Error cargando el menú. Verifique la conexión."
            } finally {
                progressBar.visibility = View.GONE
            }
        }
    }

    private fun updateCartButton(btn: Button, badge: TextView) {
        val count = CartManager.totalItems()
        val total = CartManager.totalPrice()
        btn.text = if (count == 0) "Ver Carrito" else "Ver Carrito ($count) — \$%.2f".format(total)
        badge.visibility = if (count > 0) View.VISIBLE else View.GONE
        badge.text = count.toString()
    }

    private fun showCartDialog() {
        if (CartManager.items.isEmpty()) {
            Toast.makeText(this, "El carrito está vacío", Toast.LENGTH_SHORT).show()
            return
        }

        val dialogView = layoutInflater.inflate(R.layout.dialog_cart, null)
        val rvCart     = dialogView.findViewById<RecyclerView>(R.id.rvCartItems)
        val tvTotal    = dialogView.findViewById<TextView>(R.id.tvCartTotal)
        val progressBar= dialogView.findViewById<ProgressBar>(R.id.cartProgress)

        val cartAdapter = CartAdapter(
            CartManager.items,
            onIncrement = { id -> CartManager.increment(id); updateCartSummary(rvCart, tvTotal) },
            onDecrement = { id -> CartManager.decrement(id); updateCartSummary(rvCart, tvTotal) },
            onRemove    = { id -> CartManager.removeItem(id); updateCartSummary(rvCart, tvTotal) },
        )
        rvCart.layoutManager = LinearLayoutManager(this)
        rvCart.adapter = cartAdapter

        updateCartSummary(rvCart, tvTotal)

        AlertDialog.Builder(this)
            .setTitle("Tu Pedido")
            .setView(dialogView)
            .setPositiveButton("Confirmar Pedido") { _, _ -> confirmOrder(progressBar) }
            .setNegativeButton("Seguir eligiendo", null)
            .show()
    }

    private fun updateCartSummary(rv: RecyclerView, tvTotal: TextView) {
        rv.adapter?.notifyDataSetChanged()
        tvTotal.text = "Total: \$%.2f".format(CartManager.totalPrice())
    }

    private fun confirmOrder(progressBar: ProgressBar) {
        if (CartManager.items.isEmpty()) {
            Toast.makeText(this, "Agrega productos antes de confirmar", Toast.LENGTH_SHORT).show()
            return
        }

        val orderCreate = OrderCreate(
            serviceType     = CartManager.serviceType,
            tableId         = CartManager.selectedTable?.id,
            customerName    = CartManager.customerName,
            customerAddress = CartManager.customerAddress.ifEmpty { null },
            items           = CartManager.items.map {
                OrderItemCreate(productId = it.productId, quantity = it.quantity, notes = it.notes.ifEmpty { null })
            },
            userId   = RetrofitClient.userId(this),
            branchId = RetrofitClient.branchId(this),
        )

        progressBar?.visibility = View.VISIBLE
        lifecycleScope.launch {
            try {
                val resp = RetrofitClient.api(this@MenuActivity).createOrder(orderCreate)
                if (resp.isSuccessful) {
                    val result = resp.body()!!
                    CartManager.clear()
                    AlertDialog.Builder(this@MenuActivity)
                        .setTitle("✅ Pedido Confirmado")
                        .setMessage("Pedido ${result.orderNumber} enviado a cocina.\nTotal: \$%.2f".format(result.total))
                        .setPositiveButton("Nuevo Pedido") { _, _ ->
                            startActivity(Intent(this@MenuActivity, HomeActivity::class.java)
                                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
                        }
                        .setNegativeButton("Ver Mis Pedidos") { _, _ ->
                            startActivity(Intent(this@MenuActivity, ActiveOrdersActivity::class.java))
                            finish()
                        }
                        .setCancelable(false)
                        .show()
                } else {
                    Toast.makeText(this@MenuActivity, "Error al crear pedido: ${resp.code()}", Toast.LENGTH_LONG).show()
                }
            } catch (_: Exception) {
                Toast.makeText(this@MenuActivity, "Error de conexión al confirmar", Toast.LENGTH_LONG).show()
            } finally {
                progressBar?.visibility = View.GONE
            }
        }
    }

    override fun onSupportNavigateUp(): Boolean { finish(); return true }
}
