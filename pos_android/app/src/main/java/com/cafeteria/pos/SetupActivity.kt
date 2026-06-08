package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.data.ApiService
import com.cafeteria.pos.data.RetrofitClient
import com.cafeteria.pos.databinding.ActivitySetupBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SetupActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySetupBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySetupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnConnect.setOnClickListener {
            val url = binding.etServerUrl.text.toString()
            if (url.isEmpty()) {
                Toast.makeText(this, "Ingrese la URL del servidor", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            binding.progressBar.visibility = View.VISIBLE
            binding.tvStatus.visibility = View.VISIBLE
            binding.tvStatus.text = "Verificando conexion..."
            binding.btnConnect.isEnabled = false

            CoroutineScope(Dispatchers.IO).launch {
                try {
                    val api = RetrofitClient.getClient(url).create(ApiService::class.java)
                    val response = api.checkConnection()
                    withContext(Dispatchers.Main) {
                        binding.progressBar.visibility = View.GONE
                        binding.btnConnect.isEnabled = true
                        if (response.isSuccessful) {
                            binding.tvStatus.text = "¡Conectado exitosamente!"
                            binding.tvStatus.setTextColor(getColor(android.R.color.holo_green_dark))
                            Toast.makeText(this@SetupActivity, "Servidor detectado", Toast.LENGTH_SHORT).show()
                            
                            val prefs = getSharedPreferences("pos_prefs", android.content.Context.MODE_PRIVATE)
                            prefs.edit().putString("server_url", url).apply()
                            
                            startActivity(Intent(this@SetupActivity, LoginActivity::class.java))
                            finish()
                        } else {
                            binding.tvStatus.text = "Error del servidor: ${response.code()}"
                            binding.tvStatus.setTextColor(getColor(android.R.color.holo_red_dark))
                        }
                    }
                } catch (e: Exception) {
                    withContext(Dispatchers.Main) {
                        binding.progressBar.visibility = View.GONE
                        binding.btnConnect.isEnabled = true
                        binding.tvStatus.text = "Error de conexion: ${e.message}"
                        binding.tvStatus.setTextColor(getColor(android.R.color.holo_red_dark))
                    }
                }
            }
        }
    }
}
