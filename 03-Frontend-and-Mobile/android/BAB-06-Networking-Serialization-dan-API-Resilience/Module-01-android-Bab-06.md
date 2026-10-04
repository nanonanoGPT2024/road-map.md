# Kurikulum Rekayasa Perangkat Lunak Android Skala Enterprise

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** 03-Frontend-and-Mobile
* **Kategori:** Android Platform Engineering
* **Bab:** 06 — Data Layer, Komunikasi Jaringan, & Offline Architecture
* **Modul:** 01 — Networking, Serialization, & API Resilience
* **Prasyarat Pengetahuan:** Kotlin Coroutines & Asynchronous Flow, Android Architecture Components, Dasar-dasar Protokol HTTP/REST, Prinsip Clean Architecture.
* **Tingkat Kompleksitas:** Advanced / Staff Engineer Level
* **Target Environment:** Android SDK 34 (Upside Down Cake), Min SDK 26, Kotlin 1.9.2x/2.0+, OkHttp 4.12.x, Retrofit 2.11.x, Kotlinx Serialization 1.6.x.

---

## SEKSI 02 — LEARNING OBJECTIVES
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Merancang arsitektur jaringan tingkat produksi yang menerapkan *zero-trust resilience* menggunakan Retrofit, OkHttp, dan Kotlinx Serialization.
2. Membedah siklus hidup *HTTP request/response* dan mengonfigurasi rantai interseptor OkHttp kustom untuk autentikasi adaptif (*token refresh* bebas *race condition*).
3. Mengeliminasi overhead refleksi saat *runtime* dengan mengadopsi deserialisasi berbasis *compile-time code generation* melalui Kotlinx Serialization.
4. Mengimplementasikan mitigasi kegagalan transmisi API melalui pola *Exponential Backoff with Full Jitter*, *Circuit Breaker State Machine*, dan isolasi kegagalan berbasis Coroutines.
5. Menjamin keamanan data saat transit (*data in transit*) dengan menerapkan HTTP Strict Transport Security (HSTS), Public Key Pinning (HPKP via OkHttp CertificatePinner), serta pencegahan kebocoran PII (*Personally Identifiable Information*) pada layer logging.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Mental Model Jaringan: "The Network is a Hostile and Unreliable State Machine"
Dalam komputasi seluler, jaringan tidak boleh diasumsikan sebagai pipa transmisi yang deterministik. Kondisi konektivitas seluler berfluktuasi secara dinamis antara *high-latency/high-bandwidth* (5G sub-6GHz), *high-latency/low-bandwidth* (EDGE/3G di terowongan), hingga kondisi *captive portal* atau *packet black-hole* (koneksi radio aktif, namun tidak ada transfer paket TCP).

```
                      KONEKSI SELULER AKTIF
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
   JARINGAN IDEAL                            JARINGAN NYATA (CHAOS)
┌───────────────────────┐                 ┌─────────────────────────────┐
│ • Latensi rendah (<20ms)│                │ • Radio RRC State Transitions│
│ • Zero Packet Drop    │                 │ • Bufferbloat & Jitter      │
│ • TLS Handshake Mulus │                 │ • Silent TCP Drops (NAT-Drop)│
│ • Payload Deterministik│                │ • Malformed Payloads & 429s │
└───────────────────────┘                 └─────────────────────────────┘
          │                                           │
          ▼                                           ▼
  Asumsi Naif: Fail!                         Model Resilience: Lolos!
```

Engineer harus menggeser paradigma dari:
* *Asumsi Naif:* "Kirim request, tunggu response, parse JSON, render ke UI."
* *Paradigma Skala Produksi:* "Kirim request yang terikat oleh *budgeted timeout*, pantau kemungkinan *transient error*, lindungi server target dengan *circuit breaker*, lakukan dekomposisi data secara efisien tanpa alokasi memori berlebih, dan siapkan mekanisme *fallback* deterministik."

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Rantai Interseptor OkHttp dan Siklus Hidup Eksekusi

```
       [ Client Request ]
               │
               ▼
   ┌───────────────────────┐
   │ Application Interceptor│ <── Logging, Header Global, Auth Injection
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ RetryAndFollowUpInter.│ <── Menangani Redirect & Transient Failure
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ BridgeInterceptor     │ <── Gzip, Content-Type, Keep-Alive Header
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ CacheInterceptor      │ <── HTTP Cache Evaluation (RFC 7234)
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ ConnectInterceptor    │ <── DNS Lookup, TCP Handshake, TLS Handshake
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ Network Interceptor   │ <── Observabilitas Wire-Level, Metric Tracking
   └───────────┬───────────┘
               │
               ▼
   ┌───────────────────────┐
   │ CallServerInterceptor │ <── Tulis byte ke Socket, Baca byte dari Socket
   └───────────┬───────────┘
               │
          [ Wire / TCP ]
```

### 2. Diagram Alur Token Refresh Autentikasi dengan OkHttp Authenticator (Bebas Deadlock/Race Condition)

```
App Thread 1       App Thread 2             OkHttp Client              Auth Server
     │                  │                         │                         │
     │ Request A        │                         │                         │
     ├──────────────────┼────────────────────────>│ GET /api/data           │
     │                  │ Request B               │ Bearer Token_Old        │
     │                  ├────────────────────────>│ GET /api/profile        │
     │                  │                         │ Bearer Token_Old        │
     │                  │                         │                         │
     │                  │                         │────────────────────────>│ (Keduanya 401)
     │                  │                         │<────────────────────────│
     │                  │                         │                         │
     │                  │               [ Mutex.withLock ]                  │
     │                  │               Evaluasi Token Baru                 │
     │                  │                         │                         │
     │                  │                   Thread 1 Lolos:                 │
     │                  │                   POST /auth/refresh              │
     │                  │                         ├────────────────────────>│
     │                  │                         │<────────────────────────│ Token_Baru Didapat!
     │                  │                         │                         │
     │                  │                   Thread 2 Tunggu:                │
     │                  │                   Cek token di storage            │
     │                  │                   (Sudah beda dengan Old)         │
     │                  │                   Pakai Token_Baru langsung!      │
     │                  │                         │                         │
     │                  │                   Retry Req A & B                 │
     │                  │                         ├────────────────────────>│
     │<─────────────────┼─────────────────────────┤ (200 OK Response)       │
     │                  │<────────────────────────┤                         │
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. OkHttp Connection Pool & Socket Multiplexing
OkHttp menggunakan `RealConnectionPool` untuk mengelola soket HTTP/1.1 dan HTTP/2. 
* **HTTP/1.1 Connection Persistence:** Header `Connection: keep-alive` memungkinkan penggunaan kembali soket TCP yang sudah terbuka, memangkas 3-way handshake SYN/ACK (~1-1.5 RTT) dan TLS negotiation (~1-2 RTT). Secara *default*, OkHttp menjaga maksimal 5 koneksi *idle* per host selama 5 menit.
* **HTTP/2 Multiplexing:** OkHttp mengalokasikan satu koneksi TCP tunggal ke host tertentu yang dapat memproses banyak *stream* data secara paralel via frame-frame binari independen. Mekanisme ini mengeliminasi masalah *Head-of-Line (HoL) Blocking* pada level aplikasi (meskipun pada level transport TCP, HoL blocking masih dapat terjadi jika terjadi kehilangan paket IP).

### 2. Kotlinx Serialization vs Gson/Moshi
* **Gson:** Menggunakan Java Reflection secara agresif saat *runtime* (`Field.setAccessible(true)`). Pendekatan ini memicu *boxing/unboxing primitives*, mengacaukan mekanisme *tree-shaking* ProGuard/R8, dan yang paling berbahaya di Kotlin: dapat mengabaikan penegakan null-safety. Properti `val x: String` non-nullable dapat diinjeksi nilai `null` oleh Gson jika server mengembalikan nilai null.
* **Kotlinx Serialization:** Beroperasi murni pada fase kompilasi (`KSP` / Kotlin Compiler Plugin). Plugin menghasilkan kelas `$serializer` turunan dari `KSerializer<T>`. Saat runtime, parser membaca *stream* token menggunakan parser kustom berbasis *state machine* (*visitor pattern*). Eksekusi langsung memanggil konstruktor Kotlin yang sebenarnya, menjaga penegakan `non-nullable` secara ketat dan menggunakan nilai default properti jika field JSON tidak ditemukan.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Resilience Pattern: Exponential Backoff, Jitter, & Circuit Breaker

#### 1. Formulasi Matematika Full Jitter
Percobaan ulang (*retry*) yang menggunakan penundaan eksponensial deterministik ($T = B \times 2^{n}$) memicu fenomena **Thundering Herd Problem**, di mana ratusan ribu klien seluler yang mengalami kegagalan transmisi secara bersamaan akan mengirimkan *retry* serentak pada detik yang sama, membebani backend yang sedang pulih.

Solusinya adalah **Full Jitter**, yang diformulasikan sebagai:
$$T_{\text{sleep}} = \text{random}(0, \min(M, B \times 2^{n}))$$
* Di mana $B$ adalah *base backoff* (misal 1000ms),
* $n$ adalah indeks percobaan ke-$n$,
* $M$ adalah batas atas penundaan (*maximum backoff cap*, misal 30000ms),
* $\text{random}(0, X)$ menghasilkan distribusi acak seragam antara $0$ dan $X$.

#### 2. Arsitektur Circuit Breaker
Circuit Breaker beroperasi sebagai *finite state machine* dengan tiga kondisi:
1. **CLOSED:** Aliran request normal dieksekusi. Jika tingkat kegagalan (*failure rate*) dalam jendela waktu geser tertentu melampaui ambang batas $\tau$ (misal 50% dari 20 request), state beralih ke **OPEN**.
2. **OPEN:** Semua panggilan jaringan langsung digagalkan seketika di sisi klien (*Fast-Fail*) tanpa membuang daya baterai radio seluler untuk melakukan soket koneksi, melempar exception `CircuitOpenException`. Setelah durasi pendinginan $t_{\text{cool}}$ (misal 60 detik) terlampaui, state beralih ke **HALF-OPEN**.
3. **HALF-OPEN:** Sejumlah terbatas request probe diperbolehkan lolos. Jika semua request probe berhasil, sirkuit kembali ke **CLOSED**. Jika satu saja probe gagal, sirkuit kembali ke **OPEN** selama $t_{\text{cool}}$ berikutnya.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi fondasi arsitektur jaringan modular menggunakan Retrofit, OkHttp, dan Kotlinx Serialization.

```kotlin
// File: data/remote/dto/UserResponseDto.kt
package com.enterprise.network.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class UserResponseDto(
    @SerialName("id")
    val id: String,
    @SerialName("email")
    val email: String,
    @SerialName("display_name")
    val displayName: String,
    @SerialName("is_verified")
    val isVerified: Boolean = false // Default fallback jika field absen
)

// File: data/remote/api/UserApiService.kt
package com.enterprise.network.data.remote.api

import com.enterprise.network.data.remote.dto.UserResponseDto
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path

interface UserApiService {
    @GET("v1/users/{id}")
    suspend fun getUserById(
        @Path("id") userId: String
    ): Response<UserResponseDto>
}

// File: di/NetworkFactory.kt
package com.enterprise.network.di

import com.enterprise.network.data.remote.api.UserApiService
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

object NetworkFactory {

    private val jsonConfiguration = Json {
        ignoreUnknownKeys = true // Tahan perubahan schema JSON dari backend
        coerceInputValues = true // Konversi tipe null ke default value jika tersedia
        isLenient = false        // Menegakkan standar ketat RFC-8259
        encodeDefaults = true
    }

    fun provideOkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .writeTimeout(10, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }

    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            .baseUrl("https://api.enterprise.domain.com/")
            .client(okHttpClient)
            .addConverterFactory(jsonConfiguration.asConverterFactory(contentType))
            .build()
    }

    fun provideUserApiService(retrofit: Retrofit): UserApiService {
        return retrofit.create(UserApiService::class.java)
    }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### 1. Konfigurasi `Json` Engine
* `ignoreUnknownKeys = true`: Mencegah `SerializationException` ketika backend menambahkan field baru (misal: fitur baru diluncurkan di server). Mencegah aplikasi mengalami crash jika client versi lama membaca model respons baru.
* `coerceInputValues = true`: Menyelamatkan integritas parsing ketika backend secara keliru mengirim nilai `null` untuk properti primitif non-nullable yang sudah memiliki nilai default pada data class.
* `isLenient = false`: Memastikan parser menolak sintaks JSON malformed (seperti string tanpa kutip ganda atau unescaped characters) guna mencegah celah eksploitasi deserialisasi.

### 2. Timeouts pada `OkHttpClient.Builder`
* `connectTimeout(10, TimeUnit.SECONDS)`: Mengatur durasi maksimum alokasi penentuan rute IP, pembuatan TCP handshake, dan TLS session negotiation. Nilai default 10 detik adalah titik temu optimal antara latensi seluler dan deteksi dini kegagalan koneksi.
* `retryOnConnectionFailure(true)`: Menginstruksikan OkHttp untuk mencoba rute alternatif (IP lain yang dipetakan pada DNS A/AAAA record) jika rute pertama mengalami unreachable host atau kegagalan TCP handshake.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Transaksi Finansial pada Jaringan Fluktuatif
Aplikasi perbankan/fintech skala enterprise menghadapi lonjakan error `401 Unauthorized` serentak saat masa kedaluwarsa JWT access token tercapai (masa aktif 15 menit), bersamaan dengan error `429 Too Many Requests` dan `503 Service Unavailable` akibat beban server yang tinggi saat jam sibuk.

**Kebutuhan Sistem:**
1. Mekanisme auto-refresh access token yang terisolasi secara konkurensi (hanya satu request refresh token yang boleh dieksekusi, sementara request transaksi lainnya mengantre secara non-blocking).
2. Mekanisme retry transien dengan penambahan header idempotensi (`Idempotency-Key`) berbasis UUID v4 agar request POST pembayaran tidak ditagih ganda di sisi backend.
3. Client-side Circuit Breaker untuk menghentikan pengiriman request jika server mengalami penurunan performa (degradasi 5xx di atas ambang batas kritis).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem jaringan tangguh berskala produksi yang memenuhi seluruh kebutuhan di atas:

```kotlin
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
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek Arsitektur | Pilihan A: Retrofit + Kotlinx Serialization | Pilihan B: Retrofit + Gson | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Metode Parsing** | *Compile-time code generation* (KSP) via Visitor Engine. | *Runtime reflection inspection* (`Class.getDeclaredFields`). | Opsi A tidak memiliki overhead inspeksi refleksi saat runtime, menghasilkan inisialisasi cold-start yang terukur jauh lebih cepat. |
| **Null-Safety Guarantees** | Ketat (*Type Safe*). Melempar `SerializationException` jika menerima null pada tipe non-null. | Lemah (*Unsafe*). Mengabaikan Kotlin nullability, menulis null via *unsafe memory allocation*. | Opsi A mencegah `NullPointerException` laten yang kerap terjadi pada layer UI Android akibat backend inkonsisten. |
| **R8/ProGuard Footprint** | Ukuran DEX minimal; aturan ProGuard spesifik per class serializer yang dihasilkan. | Memerlukan *rule* ProGuard ekstensif (`-keepclassmembers`) agar nama field tidak teracak. | Opsi A menghasilkan APK/AAB yang jauh lebih ramping dan aman terhadap proses obfuscation agresif. |
| **Dukungan Tipe Lanjutan** | Mendukung secara native: `Sealed Class Hierarchies`, `Inline Value Classes`. | Memerlukan registrasi `TypeAdapter` kustom yang kompleks dan manual untuk sealed class. | Opsi A sangat ideal untuk memodelkan Domain-Driven Design (DDD) dan `Result` monads. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Connection Leaks akibat Unclosed Response Body
* **Kasus:** Membaca header atau status code dari panggilan interseptor atau eksekusi `newCall(..).execute()` tanpa membaca seluruh stream atau memanggil `response.close()`.
* **Dampak:** Soket TCP dasar tidak dikembalikan ke `ConnectionPool` dan *thread* I/O tetap mengambang di memori native, menyebabkan kebocoran memori OS dan error `java.lang.OutOfMemoryError: Could not allocate JNI Env` atau socket exhaustion.
* **Mitigasi:** Selalu gunakan blok ekstensi `.use { }` dari pustaka standar Kotlin pada setiap objek `Response` atau `ResponseBody`.

### 2. Deadlock Mutex pada Autentikasi Rekursif
* **Kasus:** Instance `OkHttpClient` yang digunakan untuk memanggil endpoint *Refresh Token* memiliki konfigurasi interseptor atau instance `Authenticator` yang sama.
* **Dampak:** Jika endpoint refresh mengembalikan status code 401, klien akan mencoba memanggil `Authenticator` kembali, memicu perulangan tak terbatas dan mengunci `Mutex` secara permanen (*Deadlock*).
* **Mitigasi:** Alokasikan instance `refreshClient` khusus yang murni, terisolasi, tanpa `Authenticator` atau interseptor auth yang melekat.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Penggunaan `runBlocking` Sembarangan pada UI Thread
* **Kesalahan:** Memanggil API Service melalui `runBlocking` di dalam komponen UI (seperti ViewModel init atau Composable function).
* **Solusi:** Selalu delegasikan operasi suspensi jaringan ke `CoroutineDispatcher` berbasis I/O menggunakan `viewModelScope.launch(Dispatchers.IO)`. Pahami bahwa kontrak internal `Authenticator` OkHttp memang berjalan di thread pool latar belakang milik OkHttp, sehingga `runBlocking` pada *Authenticator* aman secara thread UI, namun tetap harus dikelola dengan hati-hati.

### 2. Mengabaikan Parsing Response Body Error
* **Kesalahan:** Hanya menangani blok sukses (`response.isSuccessful`), lalu mengasumsikan kegagalan jaringan melempar `HttpException` secara seragam.
* **Solusi:** Ekstrak dan parse payload error dari `response.errorBody()?.string()` menggunakan serializer terstandarisasi untuk mendapatkan kode error bisnis dari backend.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Nilai Default & `ignoreUnknownKeys`:** Pastikan seluruh DTO respons jaringan memiliki konfigurasi parser yang toleran terhadap perubahan skema JSON dari backend.
2. **Definisikan Nilai Timeout Berdasarkan Konteks:** Pisahkan profil OkHttpClient untuk operasi umum (timeout 10 detik) dan operasi transfer file besar (upload/download multipart: connect 15 detik, read/write 60-120 detik).
3. **Isolasi Layer Domain dari DTO:** Jangan pernah menggunakan model `@Serializable` DTO langsung pada layer UI. Petakan DTO ke Domain Model murni menggunakan ekstensi *mapper function* (`toDomain()`) sebelum data dikirimkan ke ViewModel.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### 1. OkHttp Cache Management (RFC 7234)
Aktifkan disk cache pada OkHttpClient untuk memanfaatkan mekanisme conditional GET (`ETag` dan `If-None-Match`, atau `Last-Modified` dan `If-Modified-Since`):

```kotlin
val cacheSize = 50L * 1024L * 1024L // 50 Megabytes
val cache = Cache(File(context.cacheDir, "http_cache"), cacheSize)

val client = OkHttpClient.Builder()
    .cache(cache)
    .build()
```
Ketika backend merespons dengan status `304 Not Modified`, OkHttp langsung mengambil data dari disk cache lokal tanpa memproses ulang alokasi body melalui jaringan seluler, menghemat transfer data dan konsumsi daya baterai secara drastis.

### 2. Hindari Deserialisasi String Utuh
Hindari membaca seluruh response body ke dalam representasi teks memori (`response.body?.string()`) sebelum mem-parsingnya ke JSON. Pendekatan ini mengalokasikan string berukuran besar di Java Heap yang dapat memicu Garbage Collector bekerja lebih sering. Gunakan adapter streaming berbasis `source()` untuk mem-parsing stream byte langsung ke objek domain.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Certificate Pinning Berbasis SHA-256
Guna menangkal serangan *Man-In-The-Middle* (MITM) yang memanfaatkan sertifikat root CA gadungan yang terinstal pada sistem Android, terapkan `CertificatePinner`:

```kotlin
val certificatePinner = CertificatePinner.Builder()
    .add("api.enterprise.domain.com", "sha256/7HIpactkIAq2Y49orFOOQKurWxmmSFZhBCoQYcRhJ3Y=")
    // Selalu cantumkan minimal satu sertifikat cadangan (Backup Pin)
    .add("api.enterprise.domain.com", "sha256/k2v657xBsOwg11+SZqYQIUpNO7DY8NXD0xYTBl99EjU=")
    .build()

val secureClient = OkHttpClient.Builder()
    .certificatePinner(certificatePinner)
    .build()
```

### 2. Pencegahan Kebocoran Informasi Pribadi (PII Data Redaction)
Jangan biarkan informasi sensitif (nomor kartu kredit, token JWT, password) tercetak pada Logcat sistem. Tulis interseptor kustom atau gunakan `HttpLoggingInterceptor` dengan level yang aman:

```kotlin
val loggingInterceptor = HttpLoggingInterceptor().apply {
    level = if (BuildConfig.DEBUG) {
        HttpLoggingInterceptor.Level.HEADERS
    } else {
        HttpLoggingInterceptor.Level.NONE
    }
    redactHeader("Authorization")
    redactHeader("Cookie")
    redactHeader("X-API-KEY")
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Manfaatkan `EventListener` bawaan OkHttp untuk melacak metrik latensi setiap fase request secara terperinci (DNS, Connect, TLS Handshake, Request, Response):

```kotlin
// File: core/network/telemetry/MetricsEventListener.kt
package com.enterprise.network.core.telemetry

import okhttp3.Call
import okhttp3.EventListener
import java.net.InetAddress
import java.util.concurrent.TimeUnit

class MetricsEventListener : EventListener() {
    private var dnsStartTime: Long = 0
    private var connectStartTime: Long = 0

    override fun dnsStart(call: Call, domainName: String) {
        dnsStartTime = System.nanoTime()
    }

    override fun dnsEnd(call: Call, domainName: String, inetAddressList: List<InetAddress>) {
        val duration = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - dnsStartTime)
        println("TELEMETRY [DNS]: Resolusi $domainName selesai dalam ${duration}ms")
    }

    override fun connectStart(call: Call, inetSocketAddress: java.net.InetSocketAddress, proxy: java.net.Proxy) {
        connectStartTime = System.nanoTime()
    }

    override fun connectEnd(
        call: Call,
        inetSocketAddress: java.net.InetSocketAddress,
        proxy: java.net.Proxy,
        protocol: okhttp3.Protocol?
    ) {
        val duration = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - connectStartTime)
        println("TELEMETRY [CONNECT]: Soket terhubung via $protocol dalam ${duration}ms")
    }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Komponen Inti:**
  * Retrofit menangani pemetaan interface HTTP deklaratif menjadi pemanggilan method type-safe.
  * OkHttp bertindak sebagai execution engine level rendah yang mengelola soket, interseptor, pooling, dan negosiasi protokol.
  * Kotlinx Serialization mengonversi data stream menjadi objek Kotlin secara efisien menggunakan kode yang digenerate saat kompilasi.
* **Prinsip Utama Ketahanan (Resilience):**
  * Selalu terapkan **Full Jitter** saat melakukan retry guna menghindari thundering herd problem.
  * Lindungi aplikasi dan infrastruktur backend dari kegagalan beruntun menggunakan **Circuit Breaker**.
  * Pasang header idempotensi (`Idempotency-Key`) pada operasi mutasi non-idempoten (seperti `POST`).
* **Autentikasi Aman:**
