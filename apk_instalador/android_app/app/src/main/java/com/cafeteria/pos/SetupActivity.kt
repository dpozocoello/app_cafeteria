package com.cafeteria.pos

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanIntentResult
import com.journeyapps.barcodescanner.ScanOptions
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

class SetupActivity : AppCompatActivity() {

    companion object {
        const val EXTRA_FORCE = "force_setup"
        const val PREFS = "cafeteria_prefs"
        const val KEY_URL = "server_url"
    }

    private val barcodeLauncher = registerForActivityResult(ScanContract()) { result: ScanIntentResult ->
        if (result.contents != null) {
            val scanned = result.contents.trim().trimEnd('/')
            findViewById<EditText>(R.id.etServerUrl).setText(scanned)
            tryConnect(scanned)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val savedUrl = prefs().getString(KEY_URL, "") ?: ""
        val force = intent.getBooleanExtra(EXTRA_FORCE, false)

        // Si ya hay URL guardada y no se forza reconfiguración, ir directo al POS
        if (savedUrl.isNotEmpty() && !force) {
            launchMain()
            return
        }

        setContentView(R.layout.activity_setup)

        val etUrl = findViewById<EditText>(R.id.etServerUrl)
        val btnConnect = findViewById<Button>(R.id.btnConnect)
        val btnScan = findViewById<Button>(R.id.btnScanQR)

        if (savedUrl.isNotEmpty()) {
            etUrl.setText(savedUrl)
        }

        btnConnect.setOnClickListener {
            val url = etUrl.text.toString().trim().trimEnd('/')
            if (url.isEmpty()) {
                setStatus("Ingrese la dirección del servidor", error = true)
                return@setOnClickListener
            }
            tryConnect(url)
        }

        btnScan.setOnClickListener {
            barcodeLauncher.launch(
                ScanOptions().apply {
                    setPrompt("Escanee el QR del servidor POS")
                    setBeepEnabled(true)
                    setOrientationLocked(false)
                }
            )
        }
    }

    private fun tryConnect(url: String) {
        setStatus("Verificando conexión…", error = false)
        setLoading(true)

        val handler = Handler(Looper.getMainLooper())
        Executors.newSingleThreadExecutor().execute {
            val ok = pingServer("$url/api/orders/menus")
            handler.post {
                setLoading(false)
                if (ok) {
                    prefs().edit().putString(KEY_URL, url).apply()
                    launchMain()
                } else {
                    setStatus(
                        "No se pudo conectar. Verifique que el servidor esté activo y en la misma red WiFi.",
                        error = true
                    )
                }
            }
        }
    }

    private fun pingServer(urlStr: String): Boolean {
        return try {
            val conn = URL(urlStr).openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.requestMethod = "GET"
            val code = conn.responseCode
            conn.disconnect()
            code in 200..299
        } catch (_: Exception) {
            false
        }
    }

    private fun setStatus(msg: String, error: Boolean) {
        val tv = findViewById<TextView>(R.id.tvStatus)
        tv.text = msg
        tv.setTextColor(
            if (error) getColor(R.color.error) else getColor(R.color.success)
        )
    }

    private fun setLoading(loading: Boolean) {
        findViewById<ProgressBar>(R.id.progressBar).visibility =
            if (loading) View.VISIBLE else View.GONE
        findViewById<Button>(R.id.btnConnect).isEnabled = !loading
        findViewById<Button>(R.id.btnScanQR).isEnabled = !loading
    }

    private fun launchMain() {
        startActivity(Intent(this, LoginActivity::class.java))
        finish()
    }

    private fun prefs() = getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
