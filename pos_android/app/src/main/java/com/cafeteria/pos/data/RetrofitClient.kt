package com.cafeteria.pos.data

import okhttp3.Interceptor
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private var retrofit: Retrofit? = null
    var authToken: String? = null

    fun getClient(baseUrl: String): Retrofit {
        var formattedUrl = baseUrl
        if (!formattedUrl.endsWith("/")) {
            formattedUrl += "/"
        }
        
        val interceptor = Interceptor { chain ->
            val requestBuilder = chain.request().newBuilder()
            authToken?.let {
                requestBuilder.addHeader("Authorization", "Bearer $it")
            }
            chain.proceed(requestBuilder.build())
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(interceptor)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .build()

        retrofit = Retrofit.Builder()
            .baseUrl(formattedUrl)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            
        return retrofit!!
    }
}
