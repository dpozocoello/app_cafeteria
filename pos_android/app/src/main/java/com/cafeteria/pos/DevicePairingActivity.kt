package com.cafeteria.pos

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.cafeteria.pos.databinding.ActivityDevicePairingBinding

class DevicePairingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityDevicePairingBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDevicePairingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val pairUrl = intent.getStringExtra("pair_url") ?: ""
        binding.btnOpenPairPage.setOnClickListener {
            val intent = Intent(this, LoginActivity::class.java)
            startActivity(intent)
        }

        binding.btnCancel.setOnClickListener {
            finish()
        }
    }
}