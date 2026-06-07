package com.cafeteria.pos

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.*
import android.widget.ProgressBar
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val serverUrl = savedUrl()
        if (serverUrl.isEmpty()) {
            openSetup(force = false)
            return
        }

        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)

        configureWebView()
        webView.loadUrl("$serverUrl/pedidos")
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(true)
            builtInZoomControls = false
            displayZoomControls = false
            // Necesario para que las peticiones HTTP locales funcionen en Android 9+
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }

        // Persistir cookies (JWT de sesión)
        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(webView, true)
        }

        webView.webViewClient = object : WebViewClient() {

            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                // Inyectar CSS para mejorar experiencia en pantalla pequeña
                webView.evaluateJavascript(
                    """
                    (function() {
                        var meta = document.querySelector('meta[name=viewport]');
                        if (!meta) {
                            meta = document.createElement('meta');
                            meta.name = 'viewport';
                            document.head.appendChild(meta);
                        }
                        meta.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0';
                    })();
                    """.trimIndent(),
                    null
                )
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    progressBar.visibility = View.GONE
                    val url = savedUrl()
                    view?.loadData(buildErrorHtml(url), "text/html; charset=utf-8", "UTF-8")
                }
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progressBar.progress = newProgress
                progressBar.visibility = if (newProgress < 100) View.VISIBLE else View.GONE
            }
        }
    }

    private fun buildErrorHtml(serverUrl: String) = """
        <!DOCTYPE html>
        <html><head>
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
          body{font-family:sans-serif;text-align:center;padding:40px 24px;background:#f8f9fa}
          h2{color:#dc3545}
          p{color:#6c757d;font-size:15px;margin:12px 0}
          .url{background:#e9ecef;padding:8px 16px;border-radius:8px;font-size:13px;word-break:break-all}
          button{margin-top:24px;padding:14px 32px;font-size:16px;background:#0d6efd;color:white;
                 border:none;border-radius:8px;cursor:pointer}
          button:hover{background:#0b5ed7}
        </style></head>
        <body>
          <h2>Sin conexión</h2>
          <p>No se pudo conectar al servidor:</p>
          <div class="url">$serverUrl</div>
          <p>Verifique que el servidor esté encendido<br>y el dispositivo en la misma red WiFi.</p>
          <button onclick="location.reload()">Reintentar</button>
        </body></html>
    """.trimIndent()

    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_reload -> {
            if (::webView.isInitialized) webView.reload()
            true
        }
        R.id.action_settings -> {
            AlertDialog.Builder(this)
                .setTitle("Cambiar servidor")
                .setMessage("¿Desea configurar un servidor diferente?")
                .setPositiveButton("Sí") { _, _ -> openSetup(force = true) }
                .setNegativeButton("Cancelar", null)
                .show()
            true
        }
        else -> super.onOptionsItemSelected(item)
    }

    private fun openSetup(force: Boolean) {
        startActivity(
            Intent(this, SetupActivity::class.java)
                .putExtra(SetupActivity.EXTRA_FORCE, force)
        )
        finish()
    }

    private fun savedUrl(): String =
        getSharedPreferences(SetupActivity.PREFS, Context.MODE_PRIVATE)
            .getString(SetupActivity.KEY_URL, "") ?: ""
}
