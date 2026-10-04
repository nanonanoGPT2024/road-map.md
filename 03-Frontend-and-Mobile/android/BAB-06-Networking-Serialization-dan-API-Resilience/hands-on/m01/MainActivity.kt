// File: core/network/resilience/CircuitBreaker.kt
package com.enterprise.network.core.resilience

import java.io.IOException
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

class CircuitBreakerOpenException(message: String) : IOException(message)

class CircuitBreaker(
    private val failureThreshold: Int = 5,
    private val resetTimeoutMillis: Long = 30_000L
) {
    enum class State { CLOSED, OPEN, HALF_OPEN }

    private val state = AtomicReference(State.CLOSED)
    private val failureCount = AtomicInteger(0)
    private val lastStateChangeTimestamp = AtomicLong(System.currentTimeMillis())

    fun canExecute(): Boolean {
        val currentState = state.get()
        val now = System.currentTimeMillis()

        return when (currentState) {
            State.CLOSED -> true
            State.OPEN -> {
                if (now - lastStateChangeTimestamp.get() >= resetTimeoutMillis) {
                    if (state.compareAndSet(State.OPEN, State.HALF_OPEN)) {
                        lastStateChangeTimestamp.set(now)
                        true
                    } else {
                        false
                    }
                } else {
                    false
                }
            }
            State.HALF_OPEN -> true
        }
    }

    fun recordSuccess() {
        failureCount.set(0)
        state.set(State.CLOSED)
    }

    fun recordFailure() {
        val failures = failureCount.incrementAndGet()
        val now = System.currentTimeMillis()
        if (failures >= failureThreshold || state.get() == State.HALF_OPEN) {
            state.set(State.OPEN)
            lastStateChangeTimestamp.set(now)
        }
    }
}

// File: core/network/token/TokenStorage.kt
package com.enterprise.network.core.token

interface TokenStorage {
    fun getAccessToken(): String?
    fun getRefreshToken(): String?
    fun updateTokens(accessToken: String, refreshToken: String)
    fun clearTokens()
}

// File: core/network/interceptor/ResilienceInterceptor.kt
package com.enterprise.network.core.interceptor

import com.enterprise.network.core.resilience.CircuitBreaker
import com.enterprise.network.core.resilience.CircuitBreakerOpenException
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import java.io.IOException
import java.util.UUID
import kotlin.math.min
import kotlin.random.Random

class ResilienceInterceptor(
    private val circuitBreaker: CircuitBreaker,
    private val maxRetries: Int = 3,
    private val baseDelayMillis: Long = 500L,
    private val maxDelayMillis: Long = 4000L
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        if (!circuitBreaker.canExecute()) {
            throw CircuitBreakerOpenException("Circuit Breaker dalam status OPEN. Menghentikan request.")
        }

        val originalRequest = chain.request()
        val requestWithIdempotency = attachIdempotencyKey(originalRequest)

        var attempts = 0
        var lastException: IOException? = null

        while (attempts <= maxRetries) {
            try {
                val response = chain.proceed(requestWithIdempotency)

                if (response.isSuccessful) {
                    circuitBreaker.recordSuccess()
                    return response
                }

                if (isTransientServerError(response.code)) {
                    circuitBreaker.recordFailure()
                    response.close() // Penting: Jangan biarkan connection leak
                    if (attempts == maxRetries) return response
                } else {
                    // Non-transient error (400, 404, dll) langsung return tanpa retry
                    return response
                }
            } catch (e: IOException) {
                lastException = e
                circuitBreaker.recordFailure()
                if (attempts == maxRetries) throw e
            }

            attempts++
            applyFullJitter(attempts)
        }

        throw lastException ?: IOException("Gagal mengeksekusi request akibat kegagalan transien tak terduga")
    }

    private fun attachIdempotencyKey(request: Request): Request {
        return if (request.method.equals("POST", ignoreCase = true) && 
            request.header("Idempotency-Key") == null) {
            request.newBuilder()
                .header("Idempotency-Key", UUID.randomUUID().toString())
                .build()
        } else {
            request
        }
    }

    private fun isTransientServerError(code: Int): Boolean {
        return code == 429 || code in 500..599
    }

    private fun applyFullJitter(attempt: Int) {
        val exponentialDelay = baseDelayMillis * (1L shl attempt)
        val ceiling = min(maxDelayMillis, exponentialDelay)
        val calculatedSleep = Random.nextLong(0, ceiling + 1)
        try {
            Thread.sleep(calculatedSleep)
        } catch (ignored: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }
}

// File: core/network/authenticator/TokenAuthenticator.kt
package com.enterprise.network.core.authenticator

import com.enterprise.network.core.token.TokenStorage
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.Authenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import org.json.JSONObject

class TokenAuthenticator(
    private val tokenStorage: TokenStorage,
    private val refreshClient: OkHttpClient, // Client terisolasi tanpa interseptor auth rekursif
    private val refreshUrl: String
) : Authenticator {

    private val refreshMutex = Mutex()

    override fun authenticate(route: Route?, response: Response): Request? {
        // Cegah perulangan tak terbatas jika refresh token itu sendiri ditolak (401 berulang)
        if (responseCount(response) >= 3) {
            return null
        }

        val existingTokenAtRequest = response.request.header("Authorization")
            ?.removePrefix("Bearer ")
            ?.trim()

        return runBlocking {
            refreshMutex.withLock {
                val currentTokenInStorage = tokenStorage.getAccessToken()

                // Skenario: Request lain sudah berhasil me-refresh token saat thread ini mengantre
                if (currentTokenInStorage != null && currentTokenInStorage != existingTokenAtRequest) {
                    return@withLock response.request.newBuilder()
                        .header("Authorization", "Bearer $currentTokenInStorage")
                        .build()
                }

                val currentRefreshToken = tokenStorage.getRefreshToken() ?: run {
                    tokenStorage.clearTokens()
                    return@withLock null
                }

                // Eksekusi pembaruan token
                val newAccessToken = performTokenRefresh(currentRefreshToken)
                if (newAccessToken != null) {
                    response.request.newBuilder()
                        .header("Authorization", "Bearer $newAccessToken")
                        .build()
                } else {
                    tokenStorage.clearTokens()
                    null
                }
            }
        }
    }

    private fun performTokenRefresh(refreshToken: String): String? {
        val requestBody = okhttp3.RequestBody.create(
            okhttp3.MediaType.parse("application/json"),
            "{\"refresh_token\":\"$refreshToken\"}"
        )

        val refreshRequest = Request.Builder()
            .url(refreshUrl)
            .post(requestBody)
            .build()

        return try {
            refreshClient.newCall(refreshRequest).execute().use { res ->
                if (res.isSuccessful) {
                    val rawBody = res.body?.string() ?: return null
                    val json = JSONObject(rawBody)
                    val newAccess = json.getString("access_token")
                    val newRefresh = json.optString("refresh_token", refreshToken)
                    tokenStorage.updateTokens(newAccess, newRefresh)
                    newAccess
                } else {
                    null
                }
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
