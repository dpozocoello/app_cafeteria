package com.cafeteria.pos.data

import android.content.Context
import android.content.SharedPreferences
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {

    private const val PREFS = "cafeteria_prefs"
    private const val KEY_URL   = "server_url"
    private const val KEY_TOKEN = "auth_token"
    const val KEY_USER_ID   = "user_id"
    const val KEY_BRANCH_ID = "branch_id"
    const val KEY_FULL_NAME = "full_name"
    const val KEY_ROLE      = "user_role"

    private var _api: ApiService? = null
    private var _baseUrl: String = ""

    fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun serverUrl(ctx: Context): String = prefs(ctx).getString(KEY_URL, "") ?: ""
    fun token(ctx: Context): String     = prefs(ctx).getString(KEY_TOKEN, "") ?: ""
    fun userId(ctx: Context): Int       = prefs(ctx).getInt(KEY_USER_ID, 1)
    fun branchId(ctx: Context): Int     = prefs(ctx).getInt(KEY_BRANCH_ID, 1)
    fun fullName(ctx: Context): String  = prefs(ctx).getString(KEY_FULL_NAME, "Mesero") ?: "Mesero"
    fun userRole(ctx: Context): String  = prefs(ctx).getString(KEY_ROLE, "mesero") ?: "mesero"

    fun saveSession(ctx: Context, token: String, userId: Int, branchId: Int, fullName: String, role: String) {
        prefs(ctx).edit()
            .putString(KEY_TOKEN, token)
            .putInt(KEY_USER_ID, userId)
            .putInt(KEY_BRANCH_ID, branchId)
            .putString(KEY_FULL_NAME, fullName)
            .putString(KEY_ROLE, role)
            .apply()
    }

    fun clearSession(ctx: Context) {
        prefs(ctx).edit()
            .remove(KEY_TOKEN)
            .remove(KEY_USER_ID)
            .remove(KEY_BRANCH_ID)
            .remove(KEY_FULL_NAME)
            .remove(KEY_ROLE)
            .apply()
    }

    fun isLoggedIn(ctx: Context) = token(ctx).isNotEmpty()

    fun api(ctx: Context): ApiService {
        val url = serverUrl(ctx).trimEnd('/') + "/"
        if (_api == null || url != _baseUrl) {
            _baseUrl = url
            _api = buildRetrofit(ctx, url).create(ApiService::class.java)
        }
        return _api!!
    }

    private fun buildRetrofit(ctx: Context, baseUrl: String): Retrofit {
        val logging = HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC }

        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .addInterceptor(logging)
            .addInterceptor { chain ->
                val tok = token(ctx)
                val req = if (tok.isNotEmpty()) {
                    chain.request().newBuilder()
                        .addHeader("Authorization", "Bearer $tok")
                        .build()
                } else chain.request()
                chain.proceed(req)
            }
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
}
