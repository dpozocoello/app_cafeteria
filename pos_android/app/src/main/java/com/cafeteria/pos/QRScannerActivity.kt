package com.cafeteria.pos

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import com.cafeteria.pos.databinding.ActivityQrScannerBinding
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage

class QRScannerActivity : AppCompatActivity() {

    private lateinit var binding: ActivityQrScannerBinding
    private var serverUrl: String = ""
    private var isPairing: Boolean = false

    private val requestPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera() else {
            Toast.makeText(this, "Permiso de cámara requerido", Toast.LENGTH_SHORT).show()
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityQrScannerBinding.inflate(layoutInflater)
        setContentView(binding.root)

        serverUrl = intent.getStringExtra("server_url") ?: ""
        isPairing = intent.getBooleanExtra("is_pairing", false)

        binding.tvInstructions.text = if (isPairing) 
            "Escanee el código QR del POS" 
        else 
            "Apunte al código QR de la mesa"

        when {
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED -> {
                startCamera()
            }
            else -> requestPermission.launch(Manifest.permission.CAMERA)
        }

        binding.btnCancel.setOnClickListener { finish() }
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            bindCameraUseCases(cameraProvider)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun bindCameraUseCases(cameraProvider: ProcessCameraProvider) {
        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(binding.previewView.surfaceProvider)
        }

        val imageAnalysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()

        val barcodeScanner = BarcodeScanning.getClient()

        imageAnalysis.setAnalyzer(ContextCompat.getMainExecutor(this)) { imageProxy ->
            processImageProxy(barcodeScanner, imageProxy)
        }

        val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(this, cameraSelector, preview, imageAnalysis)
        } catch (exc: Exception) {
            Toast.makeText(this, "Error al iniciar cámara: ${exc.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun processImageProxy(barcodeScanner: com.google.mlkit.vision.barcode.BarcodeScanner, imageProxy: ImageProxy) {
        val inputImage = imageProxy.image?.let { InputImage.fromMediaImage(it, imageProxy.imageInfo.rotationDegrees) }
        if (inputImage == null) {
            imageProxy.close()
            return
        }

        barcodeScanner.process(inputImage)
            .addOnSuccessListener { result ->
                if (result.isNotEmpty()) {
                    val rawValue = result[0].rawValue
                    if (!rawValue.isNullOrEmpty()) {
                        handleScannedQr(rawValue)
                    }
                }
                imageProxy.close()
            }
            .addOnFailureListener {
                imageProxy.close()
            }
    }

    private fun handleScannedQr(qrContent: String) {
        if (isPairing) {
            handleDevicePairing(qrContent)
        } else {
            handleTableQr(qrContent)
        }
    }

    private fun handleDevicePairing(qrContent: String) {
        if (qrContent.startsWith(serverUrl) || qrContent.contains("/device/pair")) {
            val pairUrl = if (qrContent.startsWith("http")) qrContent else "$serverUrl/device/pair"
            val intent = Intent(this, DevicePairingActivity::class.java).apply {
                putExtra("pair_url", pairUrl)
            }
            startActivity(intent)
            finish()
        } else {
            Toast.makeText(this, "QR inválido para pareado", Toast.LENGTH_SHORT).show()
        }
    }

    private fun handleTableQr(qrContent: String) {
        val tableId = qrContent.toIntOrNull()
        if (tableId != null) {
            setResult(RESULT_OK, Intent().apply {
                putExtra("table_id", tableId)
            })
            finish()
        } else {
            Toast.makeText(this, "QR inválido: $qrContent", Toast.LENGTH_SHORT).show()
        }
    }
}