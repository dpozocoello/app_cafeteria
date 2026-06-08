package com.cafeteria.pos

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.LoginRequest
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.databinding.ActivityLoginBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private var serverUrl: String = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val prefs = getSharedPreferences("pos_prefs", Context.MODE_PRIVATE)
        serverUrl = prefs.getString("server_url", "") ?: ""

        if (serverUrl.isEmpty()) {
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
            return
        }

        binding.tvServer.text = "Servidor: $serverUrl"

        binding.btnChangeServer.setOnClickListener {
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
        }

        binding.btnLogin.setOnClickListener {
            val user = binding.etUser.text.toString().trim()
            val pass = binding.etPassword.text.toString().trim()

            if (user.isEmpty() || pass.isEmpty()) {
                showError("Debe ingresar usuario y contraseña")
                return@setOnClickListener
            }

            binding.progressBar.visibility = View.VISIBLE
            binding.btnLogin.isEnabled = false
            binding.tvError.visibility = View.GONE

            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val api = RetrofitClient.getClient(serverUrl).create(ApiService::class.java)
                    val response = api.login(LoginRequest(user, pass))

                    withContext(Dispatchers.Main) {
                        binding.progressBar.visibility = View.GONE
                        binding.btnLogin.isEnabled = true

                        if (response.isSuccessful && response.body() != null) {
                            val loginResponse = response.body()!!
                            // Save token
                            prefs.edit().apply {
                                putString("auth_token", loginResponse.access_token)
                                putInt("user_id", loginResponse.user.id)
                                putString("full_name", loginResponse.user.full_name)
                                apply()
                            }
                            RetrofitClient.authToken = loginResponse.access_token

                            Toast.makeText(this@LoginActivity, "Bienvenido ${loginResponse.user.full_name}", Toast.LENGTH_SHORT).show()
                            startActivity(Intent(this@LoginActivity, HomeActivity::class.java))
                            finish()
                        } else {
                            showError("Usuario o contraseña incorrectos")
                        }
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        binding.progressBar.visibility = View.GONE
                        binding.btnLogin.isEnabled = true
                        showError("Error al conectar con el servidor: ${e.message}")
                    }
                }
            }
        }
    }

    private fun showError(msg: String) {
        binding.tvError.text = msg
        binding.tvError.visibility = View.VISIBLE
    }
}
