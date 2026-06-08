package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.cafeteria.pos.data.LoginRequest
import com.cafeteria.pos.data.RetrofitClient
import kotlinx.coroutines.launch

class LoginActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Si ya hay sesión activa, ir directo al home
        if (RetrofitClient.isLoggedIn(this)) {
            startHome()
            return
        }

        setContentView(R.layout.activity_login)

        val etUser   = findViewById<EditText>(R.id.etUsername)
        val etPass   = findViewById<EditText>(R.id.etPassword)
        val btnLogin = findViewById<Button>(R.id.btnLogin)
        val tvError  = findViewById<TextView>(R.id.tvError)
        val progress = findViewById<ProgressBar>(R.id.progressBar)
        val tvSetup  = findViewById<TextView>(R.id.tvChangeServer)

        tvSetup.setOnClickListener {
            RetrofitClient.prefs(this).edit().remove("server_url").apply()
            startActivity(Intent(this, SetupActivity::class.java)
                .putExtra(SetupActivity.EXTRA_FORCE, true))
            finish()
        }

        btnLogin.setOnClickListener {
            val user = etUser.text.toString().trim()
            val pass = etPass.text.toString()
            if (user.isEmpty() || pass.isEmpty()) {
                tvError.text = "Ingrese usuario y contraseña"
                tvError.visibility = View.VISIBLE
                return@setOnClickListener
            }
            tvError.visibility = View.GONE
            progress.visibility = View.VISIBLE
            btnLogin.isEnabled = false

            lifecycleScope.launch {
                try {
                    val resp = RetrofitClient.api(this@LoginActivity)
                        .login(LoginRequest(user, pass))
                    if (resp.isSuccessful) {
                        val body = resp.body()!!
                        RetrofitClient.saveSession(
                            this@LoginActivity,
                            token    = body.accessToken,
                            userId   = body.userId ?: 1,
                            branchId = body.branchId ?: 1,
                            fullName = body.fullName ?: user,
                            role     = body.role ?: "",
                        )
                        startHome()
                    } else {
                        showError("Usuario o contraseña incorrectos")
                    }
                } catch (e: Exception) {
                    showError("Sin conexión al servidor. Verifique la red.")
                } finally {
                    progress.visibility = View.GONE
                    btnLogin.isEnabled = true
                }
            }
        }
    }

    private fun showError(msg: String) {
        val tv = findViewById<TextView>(R.id.tvError)
        tv.text = msg
        tv.visibility = View.VISIBLE
    }

    private fun startHome() {
        startActivity(Intent(this, HomeActivity::class.java))
        finish()
    }
}
