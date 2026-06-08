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
            "DOMICILIO" -> "A Domicilio"
            else        -> "Nuevo Pedido"
        }
        supportActionBar?.title = title
        supportActionBar?.subtitle = "Paso 2 de 2"
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val tabLayout      = findViewById<TabLayout>(R.id.tabMenus)
        val rvProducts     = findViewById<RecyclerView>(R.id.rvProducts)
        val btnCart        = findViewById<Button>(R.id.btnCart)
        val tvCartCount    = findViewById<TextView>(R.id.tvCartCount)
        val tvCartSubtotal = findViewById<TextView>(R.id.tvCartSubtotal)
        val tvCartItemCount= findViewById<TextView>(R.id.tvCartItemCount)
        val layoutSummary  = findViewById<View>(R.id.layoutCartSummary)
        val progressBar    = findViewById<ProgressBar>(R.id.progressBar)
        val layoutEmpty    = findViewById<View>(R.id.layoutEmpty)
        val tvEmpty        = layoutEmpty.findViewById<TextView>(R.id.tvEmpty)

        productAdapter = MenuProductAdapter { menuItem ->
            CartManager.addItem(menuItem)
            updateCartButton(btnCart, tvCartCount, tvCartSubtotal, tvCartItemCount, layoutSummary)
            Toast.makeText(this, "${menuItem.name} agregado al carrito", Toast.LENGTH_SHORT).show()
        }
        rvProducts.layoutManager = LinearLayoutManager(this)
        rvProducts.adapter = productAdapter

        btnCart.setOnClickListener { showCartDialog() }

        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                val menu = allMenus.getOrNull(tab.position) ?: return
                productAdapter.submitList(menu.items)
                val isEmpty = menu.items.isEmpty()
                layoutEmpty.visibility = if (isEmpty) View.VISIBLE else View.GONE
                rvProducts.visibility  = if (isEmpty) View.GONE else View.VISIBLE
            }
            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })

        updateCartButton(btnCart, tvCartCount, tvCartSubtotal, tvCartItemCount, layoutSummary)
        loadMenus(tabLayout, progressBar, layoutEmpty, tvEmpty)
    }

    private fun loadMenus(tabs: TabLayout, progressBar: ProgressBar, layoutEmpty: View, tvEmpty: TextView) {
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
                        layoutEmpty.visibility = View.GONE
                    } else {
                        layoutEmpty.visibility = View.VISIBLE
                        tvEmpty.text = "No hay menús activos disponibles"
                    }
                }
            } catch (_: Exception) {
                layoutEmpty.visibility = View.VISIBLE
                tvEmpty.text = "Error cargando el menú. Verifique la conexión."
            } finally {
                progressBar.visibility = View.GONE
            }
        }
    }

    private fun updateCartButton(
        btn: Button, badge: TextView,
        tvSubtotal: TextView, tvItemCount: TextView,
        layoutSummary: View
    ) {
        val count = CartManager.totalItems()
        val total = CartManager.totalPrice()
        val tax   = total * 0.15
        btn.text = if (count == 0) "Ver Carrito" else "Ver Carrito ($count ítems)"
        badge.visibility = if (count > 0) View.VISIBLE else View.GONE
        badge.text = count.toString()
        layoutSummary.visibility = if (count > 0) View.VISIBLE else View.GONE
        tvSubtotal.text = "$%.2f".format(total + tax)
        tvItemCount.text = count.toString()
    }

    private fun showCartDialog() {
        if (CartManager.items.isEmpty()) {
            Toast.makeText(this, "El carrito está vacío", Toast.LENGTH_SHORT).show()
            return
        }

        val dialogView  = layoutInflater.inflate(R.layout.dialog_cart, null)
        val rvCart      = dialogView.findViewById<RecyclerView>(R.id.rvCartItems)
        val tvTotal     = dialogView.findViewById<TextView>(R.id.tvCartTotal)
        val tvSubtotal  = dialogView.findViewById<TextView>(R.id.tvSubtotal)
        val tvTax       = dialogView.findViewById<TextView>(R.id.tvTaxAmount)
        val etNotes     = dialogView.findViewById<android.widget.EditText>(R.id.etOrderNotes)
        val progressBar = dialogView.findViewById<ProgressBar>(R.id.cartProgress)

        val cartAdapter = CartAdapter(
            CartManager.items,
            onIncrement = { id -> CartManager.increment(id); updateCartSummary(rvCart, tvSubtotal, tvTax, tvTotal) },
            onDecrement = { id -> CartManager.decrement(id); updateCartSummary(rvCart, tvSubtotal, tvTax, tvTotal) },
            onRemove    = { id -> CartManager.removeItem(id); updateCartSummary(rvCart, tvSubtotal, tvTax, tvTotal) },
        )
        rvCart.layoutManager = LinearLayoutManager(this)
        rvCart.adapter = cartAdapter

        updateCartSummary(rvCart, tvSubtotal, tvTax, tvTotal)

        val tableName = when (CartManager.serviceType) {
            "MESA"      -> "Mesa ${CartManager.selectedTable?.number ?: "—"}"
            "LLEVAR"    -> "Para Llevar"
            "DOMICILIO" -> "A Domicilio"
            else        -> "Pedido"
        }

        AlertDialog.Builder(this)
            .setTitle("Tu Pedido — $tableName")
            .setView(dialogView)
            .setPositiveButton("Confirmar Pedido") { _, _ ->
                CartManager.customerAddress = etNotes.text.toString().trim().ifEmpty { CartManager.customerAddress }
                confirmOrder(progressBar)
            }
            .setNegativeButton("Seguir eligiendo", null)
            .show()
    }

    private fun updateCartSummary(
        rv: RecyclerView, tvSubtotal: TextView,
        tvTax: TextView, tvTotal: TextView
    ) {
        rv.adapter?.notifyDataSetChanged()
        val subtotal = CartManager.totalPrice()
        val tax = subtotal * 0.15
        tvSubtotal.text = "$%.2f".format(subtotal)
        tvTax.text      = "$%.2f".format(tax)
        tvTotal.text    = "$%.2f".format(subtotal + tax)
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
