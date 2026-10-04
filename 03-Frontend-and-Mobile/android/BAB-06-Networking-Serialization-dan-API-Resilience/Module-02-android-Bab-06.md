# BAB 06: Networking, Serialization, dan API Resilience
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonstruksi arsitektur *networking pipeline* berbasis OkHttp dan Retrofit yang *thread-safe*, modular, dan tahan terhadap *race conditions* saat menangani *token refresh* bersamaan (*concurrent 401 handling*).
- Merancang dan mengimplementasikan *custom* `CallAdapterFactory` untuk membungkus respons HTTP ke dalam tipe monadik domain/arsitektur (`NetworkResult<T>`) guna mengeliminasi penanganan *try-catch* redundan di lapisan *repository*.
- Menerapkan serialisasi data kompleks menggunakan `kotlinx.serialization`, mencakup *polymorphic serialization*, *custom type serializers*, dan *performance tuning* untuk alokasi memori minimum.
- Mengembangkan strategi *API Resilience* komprehensif pada lapisan klien: *Exponential Backoff with Full Jitter*, *Client-Side Circuit Breaker*, *ETag-based conditional requests*, serta *Idempotency-Key propagation*.
- Mengisolasi lapisan *network* dari lapisan presentasi melalui arsitektur multi-layer yang siap diuji (*unit testable*) menggunakan `MockWebServer` tanpa ketergantungan *network runtime*.

---

### 2. Prerequisite

Untuk mendapatkan hasil optimal dari modul ini, Anda wajib menguasai:
- **Kotlin Concurrency**: Pemahaman mendalam tentang Kotlin Coroutines (`CoroutineScope`, `Dispatchers.IO`), `Flow`, `Mutex`, serta *structured concurrency*.
- **Dasar HTTP/1.1 & HTTP/2**: Pengetahuan tentang siklus hidup *TCP handshake*, *TLS handshake*, *multiplexing*, *header semantics*, dan kode status HTTP (2xx, 3xx, 4xx, 5xx).
- **Dasar Retrofit & OkHttp**: Pemahaman dasar tentang cara membuat instance `Retrofit.Builder()`, antarmuka API, dan registrasi `Interceptor` sederhana.
- **Dependency Injection**: Kemampuan menggunakan Google Hilt atau Koin untuk mengelola *lifecycle* dan *scoping* dari *singleton network clients*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Engine OkHttp: Interceptor Chain & HTTP Codec
OkHttp memproses permintaan jaringan menggunakan pola desain *Chain of Responsibility*. Ketika sebuah panggilan dieksekusi (`Call.execute()` atau `Call.enqueue()`), permintaan tersebut diproses melalui urutan interseptor bawaan (*built-in*) dan interseptor kustom.

```
Request -> [Application Interceptors] -> [RetryAndFollowUpInterceptor] 
        -> [BridgeInterceptor] -> [CacheInterceptor] 
        -> [ConnectInterceptor] -> [Network Interceptors] 
        -> [CallServerInterceptor] -> Wire (Socket)
```

1. **Application Interceptors**: Dijalankan paling awal. Interceptor ini tidak peduli dengan pengalihan (*redirect*) atau percobaan ulang (*retry*). Mereka mengeksekusi *transformasi bisnis*, seperti penyuntikan *header* autentikasi global atau pencatatan metrik (*telemetry*).
2. **RetryAndFollowUpInterceptor**: Membuka koneksi ulang terhadap kegagalan jaringan yang dapat dipulihkan atau memproses respons pengalihan (3xx).
3. **BridgeInterceptor**: Mengubah model data domain tingkat aplikasi menjadi representasi standar HTTP (menambahkan `Host`, `User-Agent`, `Accept-Encoding: gzip`, `Connection: Keep-Alive`), dan mengembalikan representasi terkompresi menjadi representasi data normal.
4. **CacheInterceptor**: Mengimplementasikan *RFC 7234*. Memeriksa apakah respons dapat dilayani dari memori/disk cache lokal tanpa mengakses jaringan, serta memvalidasi status *stale-while-revalidate*.
5. **ConnectInterceptor**: Membuka *TCP/TLS socket connection* ke server target atau mengambil koneksi aktif dari `ConnectionPool`. Di sinilah *handshake HTTP/2 multiplexing* terjadi.
6. **Network Interceptors**: Dijalankan tepat sebelum data dikirim ke soket. Berguna untuk memantau data aktual di jaringan (*network traffic logging* setelah kompresi atau pra-enkripsi).
7. **CallServerInterceptor**: Menulis *request stream* (melalui Okio `BufferedSink`) ke soket dan membaca *response stream* (`BufferedSource`).

#### 3.2. Lifecycle Mutex-Locking pada OkHttp Authenticator
Masalah kritis pada aplikasi skala enterprise adalah *Concurrent 401 Unauthorized*. Ketika pengguna melakukan navigasi ke dasbor yang memicu 5 panggilan API paralel secara bersamaan dan masa berlaku *Access Token* telah habis, server akan merespons kelima panggilan tersebut dengan status `401 Unauthorized`.

Jika implementasi *token refresh* dilakukan secara naif:
- Aplikasi akan menembak *endpoint* `/refresh-token` sebanyak 5 kali secara paralel.
- Server yang menerapkan *Refresh Token Rotation* (RTR) akan menganggap token kedua dan seterusnya sebagai *token reuse attack*, membatalkan seluruh sesi, dan memaksa pengguna keluar (*logout*).

Untuk mencegah hal ini, arsitektur *network layer* enterprise harus mengisolasi proses rotasi token menggunakan mekanisme penguncian (*locking*) berbasis sinkronisasi atau `Mutex` asinkron.

```
Request A (401) ----\
Request B (401) -----+-> [OkHttp Authenticator] -> [Mutex.withLock] 
Request C (401) ----/          |
                               +-> Check if Token already refreshed by previous thread?
                                     |-- YES -> Retry request with New Token
                                     \-- NO  -> Call /refresh-token -> Save DB -> Retry
```

#### 3.3. Retrofit Call Adapter Internals
Secara *default*, Retrofit memetakan tipe kembalian fungsi *suspend* langsung ke objek model (contoh: `suspend fun getUser(): User`). Jika respons bernilai non-2xx, Retrofit melempar `HttpException`. Ini memaksa lapisan data/repositori untuk menuliskan blok `try-catch` berulang kali.

Dengan membuat `CallAdapter.Factory` kustom, kita menyuntikkan *interceptor* di tingkat Retrofit yang mengonversi `retrofit2.Call<R>` menjadi representasi fungsional seperti `NetworkResult<R>`, yang merangkum status `Success`, `HttpError`, atau `NetworkFailure`.

---

### 4. Why & What

| Pendekatan Konvensional | Pendekatan Enterprise Modern |
|---|---|
| Menggunakan `try-catch` di seluruh lapisan ViewModel/Repository untuk menangani `IOException` dan `HttpException`. | Menggunakan `CallAdapterFactory` kustom yang membungkus respons HTTP langsung ke tipe monadik `NetworkResult<T>` secara terpusat. |
| Melakukan panggilan *refresh token* langsung di dalam `Interceptor` tanpa mekanisme sinkronisasi. | Menggunakan `okhttp3.Authenticator` yang dilindungi oleh penguncian konkuren (*thread-safe locking*) untuk mencegah redundansi regenerasi token. |
| Bergantung pada Gson dengan *reflection runtime*. | Menggunakan `kotlinx.serialization` berbasis *compile-time code generation* yang lebih cepat, aman terhadap *nullability*, dan mendukung *sealed class polymorphism*. |
| Melakukan *polling* ulang secara agresif saat jaringan gagal. | Menerapkan algoritma *Exponential Backoff with Full Jitter* dan *Client-Side Circuit Breaker* untuk mencegah *Thundering Herd Problem*. |
| Selalu mengambil payload penuh dari server. | Mengoptimalkan *bandwidth* dan latensi dengan *Conditional Requests* menggunakan header `ETag` (`If-None-Match`). |

---

### 5. How (Workflow Detail)

1. **Inisialisasi OkHttpClient**:
   - Daftarkan `ConnectionPool` dengan alokasi koneksi *idle* yang optimal.
   - Daftarkan `HttpLoggingInterceptor` (hanya aktif pada varian *Debug*).
   - Daftarkan `AuthInterceptor` untuk menyematkan *Access Token* pada setiap permintaan.
   - Daftarkan `TokenAuthenticator` (mengimplementasikan `okhttp3.Authenticator`) untuk menangani kode status 401 dan melakukan rotasi token menggunakan sinkronisasi kritis.
   - Konfigurasi `Cache` lokal berbasis disk untuk mendukung *HTTP conditional caching*.

2. **Inisialisasi Retrofit**:
   - Daftarkan `ConverterFactory` berbasis `kotlinx.serialization.json.Json` dengan konfigurasi *strict* atau *lenient* yang terukur (`ignoreUnknownKeys = true`, `coerceInputValues = true`).
   - Daftarkan `NetworkResultCallAdapterFactory` kustom sebelum konverter bawaan Retrofit.

3. **Eksekusi dan Transformasi**:
   - Ketika repositori memanggil fungsi API, Retrofit mendelegasikan eksekusi ke `NetworkResultCallAdapter`.
   - Jika panggilan menghasilkan error 401, OkHttp memblokir *thread* lain yang gagal, meregenerasi token satu kali, dan mengulang (*replay*) kembali seluruh antrean permintaan yang tertunda menggunakan token baru.
   - `CallAdapter` menangkap setiap kegagalan I/O atau *parsing error*, lalu membungkus hasilnya ke dalam instance `NetworkResult.Failure` yang aman tanpa melempar *unhandled exception*.

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah bandara internasional:
- **OkHttp Client**: Landasan pacu dan sistem navigasi bandara.
- **Application Interceptors**: Petugas imigrasi dan pemeriksaan bea cukai pertama di pintu masuk bandara.
- **ConnectionPool**: Area parkir pesawat (*hangar*). Alih-alih membuat pesawat baru (buka soket TCP) setiap ada penumpang, pesawat yang sudah mendarat dipakai kembali jika tujuannya sama.
- **Authenticator (401 Handler)**: Petugas perpanjangan visa darurat. Jika visa Anda habis saat ingin terbang, Anda diarahkan ke loket khusus. Jika 10 orang dari rombongan Anda memiliki masalah visa yang sama, hanya ketua rombongan yang mengurus pembaruan, sementara yang lain menunggu di ruang tunggu berpagar (*Mutex*). Begitu selesai, seluruh rombongan melanjutkan penerbangan.

```
       [ Client Request ]
               |
               v
      +------------------+
      | AuthInterceptor  | -> Menyisipkan Authorization: Bearer <Token>
      +------------------+
               |
               v
      +------------------+
      | OkHttp Engine    | -> Buka Soket / Gunakan Ulang dari ConnectionPool
      +------------------+
               |
     [ Server Memvalidasi ]
       /                \
   (200 OK)         (401 Unauthorized)
      |                     |
      |                     v
      |            +-----------------------+
      |            |  TokenAuthenticator   |
      |            +-----------------------+
      |                     |
      |            [ Acquire Critical Lock ]
      |                     |
      |            Token Baru Valid di DB/Cache?
      |              /                     \
      |            (Ya)                    (Tidak)
      |             |                         |
      |             |          [ Tembak /api/v1/auth/refresh ]
      |             |                         |
      |             |          Simpan token baru ke storage
      |             \                         /
      |              -> Ulangi request asli <-
      |                 dengan Bearer token baru
      v
[ Return Data ke CallAdapter ]
      |
      v
[ Emit NetworkResult ke Repository ]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Definisi Monad `NetworkResult` dan Custom `CallAdapterFactory`

Berikut adalah implementasi *thread-safe* `NetworkResult` dan integrasinya dengan Retrofit.

```kotlin
// File: network/NetworkResult.kt
package com.enterprise.network

import java.io.IOException

sealed interface NetworkResult<out T> {
    data class Success<T>(val data: T, val statusCode: Int) : NetworkResult<T>
    sealed interface Failure : NetworkResult<Nothing> {
        data class HttpError(val code: Int, val message: String, val errorBody: String?) : Failure
        data class NetworkError(val throwable: IOException) : Failure
        data class SerializationError(val throwable: Throwable) : Failure
        data class UnexpectedError(val throwable: Throwable) : Failure
    }
}

// Inline extension functions untuk penanganan fungsional
inline fun <T> NetworkResult<T>.onSuccess(action: (value: T) -> Unit): NetworkResult<T> {
    if (this is NetworkResult.Success) action(data)
    return this
}

inline fun <T> NetworkResult<T>.onFailure(action: (failure: NetworkResult.Failure) -> Unit): NetworkResult<T> {
    if (this is NetworkResult.Failure) action(this)
    return this
}
```

```kotlin
// File: network/retrofit/NetworkResultCall.kt
package com.enterprise.network.retrofit

import com.enterprise.network.NetworkResult
import kotlinx.serialization.SerializationException
import okhttp3.Request
import okio.Timeout
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.io.IOException

internal class NetworkResultCall<T : Any>(
    private val delegate: Call<T>
) : Call<NetworkResult<T>> {

    override fun enqueue(callback: Callback<NetworkResult<T>>) {
        delegate.enqueue(object : Callback<T> {
            override fun onResponse(call: Call<T>, response: Response<T>) {
                val networkResult = if (response.isSuccessful) {
                    val body = response.body()
                    if (body != null) {
                        NetworkResult.Success(body, response.code())
                    } else if (response.code() == 204 || (response.code() in 200..299 && call.request().method == "HEAD")) {
                        @Suppress("UNCHECKED_CAST")
                        NetworkResult.Success(Unit as T, response.code())
                    } else {
                        NetworkResult.Failure.UnexpectedError(
                            IllegalStateException("Response body was null for code: ${response.code()}")
                        )
                    }
                } else {
                    val rawErrorBody = response.errorBody()?.string()
                    NetworkResult.Failure.HttpError(
                        code = response.code(),
                        message = response.message(),
                        errorBody = rawErrorBody
                    )
                }
                callback.onResponse(this@NetworkResultCall, Response.success(networkResult))
            }

            override fun onFailure(call: Call<T>, t: Throwable) {
                val networkResult = when (t) {
                    is IOException -> NetworkResult.Failure.NetworkError(t)
                    is SerializationException -> NetworkResult.Failure.SerializationError(t)
                    else -> NetworkResult.Failure.UnexpectedError(t)
                }
                // Tetap kirimkan Response.success agar tidak melempar unchecked crash ke CoroutineContext
                callback.onResponse(this@NetworkResultCall, Response.success(networkResult))
            }
        })
    }

    override fun execute(): Response<NetworkResult<T>> = 
        throw UnsupportedOperationException("NetworkResultCall hanya mendukung eksekusi asynchronous!")

    override fun clone(): Call<NetworkResult<T>> = NetworkResultCall(delegate.clone())
    override fun isExecuted(): Boolean = delegate.isExecuted
    override fun cancel() = delegate.cancel()
    override fun isCanceled(): Boolean = delegate.isCanceled
    override fun request(): Request = delegate.request()
    override fun timeout(): Timeout = delegate.timeout()
}
```

```kotlin
// File: network/retrofit/NetworkResultCallAdapterFactory.kt
package com.enterprise.network.retrofit

import com.enterprise.network.NetworkResult
import retrofit2.Call
import retrofit2.CallAdapter
import retrofit2.Retrofit
import java.lang.reflect.ParameterizedType
import java.lang.reflect.Type

class NetworkResultCallAdapterFactory private constructor() : CallAdapter.Factory() {

    override fun get(
        returnType: Type,
        annotations: Array<out Annotation>,
        retrofit: Retrofit
    ): CallAdapter<*, *>? {
        if (getRawType(returnType) != Call::class.java) {
            return null
        }
        check(returnType is ParameterizedType) {
            "Tipe return harus berupa Call<NetworkResult<Foo>> atau Call<NetworkResult<out Foo>>"
        }

        val responseType = getParameterUpperBound(0, returnType)
        if (getRawType(responseType) != NetworkResult::class.java) {
            return null
        }
        check(responseType is ParameterizedType) {
            "Response type harus parameterized, misal: NetworkResult<UserData>"
        }

        val successBodyType = getParameterUpperBound(0, responseType)
        return NetworkResultCallAdapter<Any>(successBodyType)
    }

    private class NetworkResultCallAdapter<R : Any>(
        private val responseType: Type
    ) : CallAdapter<R, Call<NetworkResult<R>>> {
        override fun responseType(): Type = responseType
        override fun adapt(call: Call<R>): Call<NetworkResult<R>> = NetworkResultCall(call)
    }

    companion object {
        fun create(): NetworkResultCallAdapterFactory = NetworkResultCallAdapterFactory()
    }
}
```

#### 7.2. Implementasi OkHttp Token Authenticator dengan Concurrency Shield

```kotlin
// File: network/auth/TokenAuthenticator.kt
package com.enterprise.network.auth

import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

class TokenAuthenticator(
    private val tokenStorage: TokenStorage,
    private val authService: AuthRetrofitService
) : Authenticator {

    private val lock = ReentrantLock()

    override fun authenticate(route: Route?, response: Response): Request? {
        // Ambil header authorization saat ini dari request yang gagal
        val originalAuthHeader = response.request.header("Authorization")
        val currentAccessToken = "Bearer ${tokenStorage.getAccessToken()}"

        // Hindari loop tak berujung jika request yang gagal memang sudah menggunakan token terbaru
        if (response.responseCount >= 3) {
            tokenStorage.clearSession()
            return null // Menyerah, trigger logout di UI
        }

        val updatedToken: String? = lock.withLock {
            val freshToken = tokenStorage.getAccessToken()
            // Validasi Double-Check: Apakah token sudah diperbarui oleh thread lain yang lebih dulu masuk?
            if (originalAuthHeader != null && "Bearer $freshToken" != originalAuthHeader) {
                // Token sudah diperbarui, gunakan langsung tanpa panggil API refresh lagi
                freshToken
            } else {
                // Token masih stale, panggil endpoint refresh token secara synchronous
                executeTokenRefresh()
            }
        }

        return if (!updatedToken.isNullOrBlank()) {
            response.request.newBuilder()
                .header("Authorization", "Bearer $updatedToken")
                .build()
        } else {
            null
        }
    }

    private fun executeTokenRefresh(): String? {
        val refreshToken = tokenStorage.getRefreshToken() ?: return null
        return try {
            // Gunakan runBlocking terkontrol di sini karena Authenticator berjalan pada Thread Pool OkHttp (bukan Main Thread)
            val refreshCall = runBlocking {
                authService.refreshSession(RefreshTokenRequest(refreshToken))
            }
            when (refreshCall) {
                is com.enterprise.network.NetworkResult.Success -> {
                    val newAuthData = refreshCall.data
                    tokenStorage.saveTokens(newAuthData.accessToken, newAuthData.refreshToken)
                    newAuthData.accessToken
                }
                is com.enterprise.network.NetworkResult.Failure -> {
                    tokenStorage.clearSession()
                    null
                }
            }
        } catch (e: Exception) {
            tokenStorage.clearSession()
            null
        }
    }

    private val Response.responseCount: Int
        get() {
            var result = 1
            var prior = priorResponse
            while (prior != null) {
                result++
                prior = prior.priorResponse
            }
            return result
        }
}
```

#### 7.3. Serialisasi Polimorfik dengan Kotlinx Serialization

```kotlin
// File: network/model/TransactionEvent.kt
package com.enterprise.network.model

import kotlinx.serialization.Polymorphic
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.modules.SerializersModule
import kotlinx.serialization.modules.polymorphic
import kotlinx.serialization.modules.subclass

@Serializable
sealed interface TransactionEvent {
    val transactionId: String
    val timestampMs: Long

    @Serializable
    @SerialName("PAYMENT")
    data class Payment(
        override val transactionId: String,
        override val timestampMs: Long,
        val amount: Double,
        val merchantId: String
    ) : TransactionEvent

    @Serializable
    @SerialName("TRANSFER")
    data class Transfer(
        override val transactionId: String,
        override val timestampMs: Long,
        val recipientAccountNumber: String,
        val bankCode: String
    ) : TransactionEvent

    @Serializable
    @SerialName("QRIS_REFUND")
    data class Refund(
        override val transactionId: String,
        override val timestampMs: Long,
        val originalRrn: String,
        val reason: String
    ) : TransactionEvent
}

val transactionJsonModule = SerializersModule {
    polymorphic(TransactionEvent::class) {
        subclass(TransactionEvent.Payment::class)
        subclass(TransactionEvent.Transfer::class)
        subclass(TransactionEvent.Refund::class)
    }
}

val networkJson = Json {
    ignoreUnknownKeys = true
    isLenient = false
    encodeDefaults = true
    serializersModule = transactionJsonModule
    classDiscriminator = "event_type" // Memetakan tag polymorphism pada JSON
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Latar Belakang Masalah
Sebuah platform perbankan digital skala nasional mengalami *spike* kegagalan transaksi (*Error 504 Gateway Timeout* dan lonjakan status *401 Session Expired*) ketika jutaan pengguna mengakses sistem selama periode promosi tanggal kembar (*Flash Sale Payday*).

#### Investigasi Telemetri
1. **Badai Token Refresh**: Token autentikasi pengguna memiliki *Time-To-Live* (TTL) 15 menit. Pada puncak transaksi, ribuan klien melakukan panggilan paralel ke REST API. Ketika token kedaluwarsa, 6-8 permintaan paralel dari masing-masing klien menembak endpoint `/v1/auth/refresh` secara serentak. Server OAuth mengalami kegagalan *cascading* (*CPU throttling* 100%) akibat verifikasi kriptografi JWT dan pembacaan Redis yang berlebihan.
2. **Ketiadaan Idempotensi**: Permintaan *debit account* yang mengalami kegagalan jaringan sementara (*TCP dropped mid-stream*) dikirim ulang secara manual oleh nasabah. Akibat ketiadaan *Idempotency-Key* di level HTTP header, server memotong saldo nasabah dua kali (*Double Charge*).

#### Solusi Rekayasa
1. Mengimplementasikan `TokenAuthenticator` dengan `ReentrantLock` di OkHttp klien untuk menahan seluruh permintaan lokal hingga panggilan *refresh* tunggal selesai.
2. Menyematkan *Client-Generated Idempotency Key* (`UUIDv4`) menggunakan `Interceptor` khusus pada setiap request mutasi HTTP (`POST`, `PUT`, `PATCH`).
3. Menerapkan strategi *Conditional Requests* menggunakan header `If-None-Match` (ETag) pada API katalog transaksi untuk menghemat 70% kuota *bandwidth* unduhan dan memangkas waktu respons dari 850ms menjadi 42ms (*304 Not Modified*).

```kotlin
// File: network/interceptor/IdempotencyInterceptor.kt
package com.enterprise.network.interceptor

import okhttp3.Interceptor
import okhttp3.Response
import java.util.UUID

class IdempotencyInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        // Terapkan Idempotency-Key hanya untuk method yang memodifikasi state
        if (originalRequest.method in listOf("POST", "PUT", "PATCH")) {
            val existingKey = originalRequest.header("X-Idempotency-Key")
            if (existingKey.isNullOrBlank()) {
                val newRequest = originalRequest.newBuilder()
                    .header("X-Idempotency-Key", UUID.randomUUID().toString())
                    .build()
                return chain.proceed(newRequest)
            }
        }
        
        return chain.proceed(originalRequest)
    }
}
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | Pendekatan | Keuntungan | Kerugian |
|---|---|---|---|
| **Call Processing** | Monadic `NetworkResult` via Custom Adapter | Menjamin keamanan tipe compile-time; menghapus risiko `unhandled exceptions` di Presenter/ViewModel. | Menambah kompleksitas *reflection metadata* saat inisialisasi awal Retrofit (~5-10ms pada *cold start*). |
| **Token Refresh** | In-Memory `ReentrantLock` Authenticator | Mengurangi beban server otentikasi hingga 80-90% saat token *expired*; mencegah akun terblokir akibat RTR. | Memblokir thread worker OkHttp jika pemanggilan *refresh* memakan waktu lama (*blocking I/O*). |
| **Serialization** | `kotlinx.serialization` (Compile-time) | Zero-reflection, jejak memori kecil, ukuran biner APK ramping, parsing 2-3x lebih cepat dibanding Gson. | Penulisan *custom dynamic serializer* lebih berbelit dibanding runtime serializer seperti Jackson/Moshi. |
| **Resilience** | Aggressive Exponential Backoff | Mengurangi resiko *Denial of Service* sekunder (*self-inflicted DoS*) terhadap backend yang sedang memulihkan diri. | Latensi persepsi pengguna (*perceived latency*) meningkat saat terjadi fluktuasi koneksi. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Mengonsumsi Response Body Dua Kali
*Kesalahan*: Memanggil `response.body()?.string()` di dalam custom Interceptor untuk logging, kemudian membiarkan request berlanjut.
```kotlin
// ANTI-PATTERN: Crash "IllegalStateException: closed"
val rawJson = response.body?.string()
Log.d("API", rawJson)
return response // Response body sudah tertutup dan di-drain oleh Okio!
```
*Solusi*: Gunakan utilitas buffer `peekBody()` dari OkHttp untuk membaca isi payload tanpa menghabiskan (*draining*) *stream source*.
```kotlin
// BENAR: Membaca snapshot data tanpa menutup stream
val peekedBody = response.peekBody(1024 * 1024) // Batasi 1MB
Log.d("API", peekedBody.string())
return response
```

#### 10.2. Penggunaan Dispatchers.Main dalam Token Authenticator
*Kesalahan*: Melakukan operasi disk atau network di dalam `Authenticator.authenticate()` menggunakan context main thread, memicu ANR (*Application Not Responding*).
*Solusi*: `Authenticator.authenticate()` dieksekusi secara asinkron pada thread pool milik OkHttp. Tetap eksekusi secara tersinkronisasi murni atau gunakan `runBlocking(Dispatchers.IO)` secara ketat tanpa melompat ke thread UI.

#### 10.3. Runtime Polymorphism Crash pada Proguard/R8
*Kesalahan*: Saat mode *R8/Proguard minification* aktif di rilis produksi, nama class pada `@SerialName` atau nama field JSON diobfuskasi, menyebabkan `SerializationException: Polymorphic serializer was not found`.
*Solusi*: Pastikan aturan *ProGuard* menyertakan pengecualian terhadap tipe data model dan anotasi `kotlinx.serialization`:
```proguard
# proguard-rules.pro
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.SerializationCoreKt
-keepclassmembers class * {
    @kotlinx.serialization.Serializable <fields>;
}
-keepclasseswithmembers class * {
    @kotlinx.serialization.Serializable companion <fields>;
}
-keepnames class kotlinx.serialization.Polymorphic
```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Connection Pooling**: Terapkan konfigurasi pool koneksi HTTP yang realistis untuk membatasi konsumsi resource perangkat.
   ```kotlin
   ConnectionPool(maxIdleConnections = 5, keepAliveDuration = 30, TimeUnit.SECONDS)
   ```
2. [ ] **Timeout Budgeting**: Tetapkan batasan *Timeout* secara granular:
   - `connectTimeout`: 10-15 detik
   - `readTimeout`: 15-30 detik
   - `writeTimeout`: 15 detik
3. [ ] **Payload Sanitization**: Pastikan `HttpLoggingInterceptor` dinonaktifkan di *production flavor* atau gunakan custom logging yang menyamarkan informasi sensitif (*PII - Personally Identifiable Information*) seperti password, nomor CVV, dan PIN kartu kredit.
4. [ ] **DNS Fallback Over HTTPS (DoH)**: Integrasikan DNS over HTTPS (misalnya Cloudflare/Google DoH) pada OkHttp Client untuk mencegah serangan *DNS Hijacking/Spoofing* oleh ISP nakal.
5. [ ] **Strict TLS Version**: Batasi koneksi soket agar hanya mengizinkan TLS v1.2 dan TLS v1.3 menggunakan `ConnectionSpec.RESTRICTED_TLS`.

---

### 12. Hands-on Practice

Buatlah implementasi praktikum di dalam repositori proyek Anda pada direktori `hands-on/m02/`.

#### Langkah 1: Struktur Folder
```text
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── java/
            └── com/enterprise/network/
                ├── api/
                │   └── SecureBankApi.kt
                ├── client/
                │   └── NetworkModule.kt
                └── resilience/
                    └── ExponentialBackoffRetry.kt
```

#### Langkah 2: Dependensi Gradle (`build.gradle.kts`)
```kotlin
plugins {
    kotlin("jvm")
    kotlin("plugin.serialization") version "1.9.22"
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    implementation("com.jakewharton.retrofit:retrofit2-kotlinx-serialization-converter:1.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
    
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
    testImplementation("junit:junit:4.13.2")
}
```

#### Langkah 3: Implementasi Exponential Backoff Retry dengan Jitter
```kotlin
// File: hands-on/m02/src/main/java/com/enterprise/network/resilience/ExponentialBackoffRetry.kt
package com.enterprise.network.resilience

import kotlinx.coroutines.delay
import java.io.IOException
import kotlin.math.min
import kotlin.math.pow
import kotlin.random.Random

suspend fun <T> retryWithExponentialBackoff(
    maxRetries: Int = 3,
    initialDelayMs: Long = 1000L,
    maxDelayMs: Long = 10000L,
    factor: Double = 2.0,
    block: suspend () -> T
): T {
    var currentDelay = initialDelayMs
    repeat(maxRetries - 1) { attempt ->
        try {
            return block()
        } catch (e: IOException) {
            // Full Jitter Formula: Sleep = rand(0, min(maxDelay, base * factor ^ attempt))
            val calculatedDelay = (initialDelayMs * factor.pow(attempt.toDouble())).toLong()
            val cappedDelay = min(maxDelayMs, calculatedDelay)
            val jitteredDelay = Random.nextLong(0, cappedDelay + 1)
            
            delay(jitteredDelay)
        }
    }
    return block() // Percobaan terakhir tanpa menangkap exception
}
```

---

### 13. Exercise

#### Level: Easy
1. Modifikasi `IdempotencyInterceptor` pada bagian 8 agar mengabaikan penambahan header `X-Idempotency-Key` jika terdapat anotasi khusus Retrofit `@SkipIdempotency` pada method API.
2. Buat unit test sederhana menggunakan `MockWebServer` untuk memverifikasi bahwa header `Authorization` disematkan secara benar pada HTTP request oleh interceptor.

#### Level: Medium
1. Implementasikan `ClientCircuitBreaker` yang menghentikan panggilan jaringan secara otomatis (*Open State*) selama 30 detik apabila persentase kegagalan HTTP 5xx melebihi ambang batas 50% dalam jendela 20 permintaan terakhir.
2. Tambahkan parser kustom berbasis `kotlinx.serialization` yang mampu menangani format tanggal heterogen (misalnya UNIX epoch integer dan ISO-8601 string) ke dalam satu tipe data Kotlin `java.time.Instant`.

#### Level: Hard
1. Rancang dan buat implementasi *Offline-First Stale-While-Revalidate Engine* menggunakan kombinasi OkHttp `Cache`, *Database Caching Room*, dan Kotlin `Flow`. Mesin ini harus:
   - Menghasilkan emisi data dari basis data lokal secara instan.
   - Melakukan *conditional request* menggunakan ETag ke server jaringan secara bersamaan.
   - Memperbarui database lokal dan memancarkan data terbaru ke UI jika server mengembalikan kode *200 OK*.
   - Menghentikan pemrosesan dan mempertahankan cache yang ada jika server mengembalikan kode status *304 Not Modified*.

---

### 14. Challenge

**Skenario**: Anda adalah Principal Android Architect di sebuah bank digital unicorn. Aplikasi Anda melayani sistem pembayaran kasir (POS/Merchant) yang sering kali beroperasi di daerah dengan penetrasi sinyal 3G tidak stabil, dengan *packet-loss* tinggi dan latensi TCP mencapai > 3.000 ms.

**Tugas Arsitektur**:
Rancang spesifikasi arsitektur *Offline Mutation Sync Engine* yang tangguh tanpa menimbulkan resiko transaksi ganda.

**Batasan & Persyaratan**:
1. Seluruh transaksi *offline* wajib diantrekan secara persisten di memori aman (*Encrypted SQLite*).
2. Mekanisme pengiriman antrean harus menggunakan *worker engine* yang berjalan di latar belakang, memproses data secara berurutan (*FIFO* per merchant) untuk mencegah pelanggaran integritas data.
3. Klien harus menggunakan *Cryptographic Hash-Chaining* (setiap transaksi menyertakan tanda tangan SHA-256 dari hash transaksi sebelumnya) untuk membuktikan integritas urutan pengiriman saat sinkronisasi ulang ke server.
4. Tuliskan dokumen desain arsitektur, diagram aliran status koneksi, dan cetak biru kelas-kelas Kotlin utama yang akan mengorkestrasi logika ini!

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Apa perbedaan fungsional utama antara Application Interceptor dan Network Interceptor pada OkHttp?**
   - A. Network Interceptor dapat memanipulasi URL, Application Interceptor tidak bisa.
   - B. Application Interceptor dieksekusi hanya sekali per panggilan, sedangkan Network Interceptor dapat dieksekusi berkali-kali jika terjadi retry/redirect.
   - C. Application Interceptor hanya berjalan di latar belakang melalui background thread.
   - D. Network Interceptor menangani enkripsi SSL secara otomatis.
   *Kunci*: B

2. **Mengapa pemanggilan `response.body()?.string()` dilarang dilakukan lebih dari satu kali pada OkHttp?**
   - A. Karena data JSON akan dikompresi ulang.
   - B. Karena OkHttp otomatis mengubah tipe datanya menjadi ByteString permanen.
   - C. Karena *stream source* soket Okio dikonsumsi habis (*consumed*) dan ditutup setelah pembacaan pertama.
   - D. Karena akan memicu crash OutOfMemoryError (OOM) secara instan di Dalvik/ART.
   *Kunci*: C

3. **Status HTTP manakah yang memicu callback pada `okhttp3.Authenticator`?**
   - A. 403 Forbidden
   - B. 401 Unauthorized
   - C. 502 Bad Gateway
   - D. 301 Moved Permanently
   *Kunci*: B

4. **Bagaimana cara kerja compiler plugin `kotlinx.serialization` dibanding pustaka Gson?**
   - A. Melakukan pembacaan tipe data runtime menggunakan Java Reflection.
   - B. Mengonversi JSON langsung menjadi Bytecode C++ via NDK.
   - C. Menghasilkan (*generating*) serializer statis saat fase kompilasi kode Kotlin.
   - D. Memerlukan deklarasi schema XML terpisah.
   *Kunci*: C

5. **Apa kegunaan dari menyematkan header `If-None-Match` pada request HTTP GET?**
   - A. Menghapus sesi autentikasi pengguna secara paksa.
   - B. Meminta server memvalidasi nilai hash ETag klien; server mengembalikan 304 jika data tidak berubah.
   - C. Mengompres ukuran data transfer menjadi format Brotli.
   - D. Membuka koneksi multiplexing HTTP/2 baru.
   *Kunci*: B

#### Intermediate Level (5 Soal)
6. **Apa tujuan penambahan komponen *Full Jitter* pada algoritma Exponential Backoff saat menghubungi server yang mengalami gangguan?**
   - A. Menjaga paket data tetap sinkron dengan urutan TCP ACK.
   - B. Mengacak delay untuk mencegah gelombang request yang berulang secara sinkron (*Thundering Herd Problem*).
   - C. Mempercepat koneksi internet klien secara otomatis.
   - D. Menurunkan konsumsi daya baterai hingga 0%.
   *Kunci*: B

7. **Pada situasi konkurensi tinggi, mengapa kita harus menggunakan `ReentrantLock` atau `Mutex` di dalam implementasi custom `TokenAuthenticator`?**
   - A. Untuk mencegah beberapa thread UI menggambar layar secara bersamaan.
   - B. Untuk memastikan hanya satu panggilan *refresh token* yang dikirimkan ke server otentikasi saat banyak request paralel menerima status 401.
   - C. Karena OkHttp mewajibkan seluruh interceptor bertipe synchronized.
   - D. Agar garbage collector tidak membersihkan token dari RAM.
   *Kunci*: B

8. **Jika backend Anda menggunakan format respons error kustom berformat JSON saat merespons HTTP 422, di mana Anda bisa mengekstrak pesan tersebut saat menggunakan Retrofit?**
   - A. Mengakses `response.body()`
   - B. Mengakses `response.errorBody()?.string()`
   - C. Mengakses `response.headers()`
   - D. Mengakses `response.raw().cacheResponse`
   *Kunci*: B

9. **Apa keuntungan arsitektural dari membungkus respons Retrofit ke dalam tipe monad `NetworkResult<T>` kustom melalui `CallAdapterFactory`?**
   - A. Meningkatkan kecepatan rendering UI di Jetpack Compose.
   - B. Menghilangkan ketergantungan pada pustaka OkHttp secara keseluruhan.
   - C. Memusatkan pemetaan error jaringan secara deklaratif dan mencegah pelemparan *uncaught exception* ke layer Presenter.
   - D. Memaksa server merespons data dalam bentuk Protocol Buffers (Protobuf).
   *Kunci*: C

10. **Bagaimana `@SerialName` pada `kotlinx.serialization` membantu memitigasi isu saat *code obfuscation* R8 diaktifkan?**
    - A. Mempercepat deserialisasi dengan menggunakan lookup byte array biner.
    - B. Memetakan properti JSON secara eksplisit dengan literal string statis, sehingga aman meskipun nama variabel diubah oleh pengacak nama kelas R8.
    - C. Mencegah file APK dibongkar dengan teknik reverse engineering.
    - D. Mengonversi format JSON menjadi tipe model XML secara dinamis.
    *Kunci*: B

#### Production Case Scenarios (3 Soal)
11. **Skenario Kasus 1**: Aplikasi e-commerce Anda mengalami lonjakan insiden *Double Deduction* (saldo dompet terpotong dua kali) ketika pengguna bertransaksi di jaringan kereta bawah tanah yang sinyalnya sering terputus-putus. Klien telah menerapkan mekanisme *auto-retry* 3 kali saat terjadi `SocketTimeoutException`. Berdasarkan analisis arsitektur jaringan, di mana letak kelemahan fatal sistem dan bagaimana solusi teknis enterprise untuk mengatasinya?
    - A. Timeout klien terlalu cepat; solusinya tingkatkan timeout menjadi 120 detik.
    - B. Permintaan *retry* tidak membawa pengenal unik transaksi; solusinya sematkan `X-Idempotency-Key` (UUID) pada setiap mutasi, dan pastikan backend menerapkan verifikasi kunci tersebut secara atomik sebelum eksekusi pembayaran.
    - C. Retrofit tidak mendukung retry; ubah ke library HttpURLConnection native.
    - D. Nonaktifkan fungsi pemotongan saldo saat koneksi berada di bawah sinyal 4G.
    *Kunci*: B

12. **Skenario Kasus 2**: Pengguna melaporkan bahwa setelah aplikasi berjalan di latar belakang selama beberapa jam, setiap aksi klik pertama yang membutuhkan koneksi data selalu mengalami kegagalan (*IOException: Connection reset by peer*), namun jika diklik kedua kali aksi tersebut berhasil. Apa akar masalah pada tingkat *Connection Pooling* OkHttp dan bagaimana cara memperbaikinya?
    - A. Server menutup koneksi idle lebih cepat daripada durasi `keepAliveDuration` pada klien; solusinya sesuaikan `keepAliveDuration` pada `ConnectionPool` klien agar lebih pendek daripada nilai *timeout keep-alive* milik firewall/server backend.
    - B. RAM Android membersihkan memori heap Retrofit; solusinya jadikan Retrofit sebagai Foreground Service.
    - C. Sistem operasi Android memblokir semua soket TCP secara sepihak; solusinya gunakan protokol polling SMS.
    - D. OkHttp client mengalami kebocoran memori (leak); solusinya buat instance `OkHttpClient` baru pada setiap pemanggilan method API.
    *Kunci*: A

13. **Skenario Kasus 3**: Audit keamanan sistem perbankan menemukan bahwa token otorisasi (`Bearer <token>`) tetap terkirim saat aplikasi dialihkan (*redirected*) oleh pihak ketiga ke domain eksternal berbahaya. Di interceptor layer manakah kebocoran ini seharusnya dicegah dan bagaimana mitigasinya?
    - A. Pada `CallServerInterceptor`; ganti port SSL menjadi 8080.
    - B. Pada `AuthInterceptor` (Application Layer); validasi URL target (`request.url.host`) sebelum menyematkan header `Authorization` untuk memastikan request hanya dikirim ke *whitelisted origin domain*.
    - C. Masalah ini tidak dapat dicegah di sisi klien; biarkan server menangani hal ini.
    - D. Hapus header autentikasi dari semua request dan gunakan URL parameter saja.
    *Kunci*: B

---

### 16. Summary

Membangun arsitektur *networking* Android tingkat produksi menuntut pemahaman mendalam di luar sekadar konsumsi API menggunakan Retrofit dasar. Kunci dari sistem jaringan mobile yang tangguh meliputi:
1. **Chain of Responsibility**: Memanfaatkan rantai interseptor OkHttp untuk menyuntikkan kebutuhan lintas sektoral (*cross-cutting concerns*) secara bersih dan terisolasi.
2. **Resilient Concurrency**: Menangani kondisi kegagalan autentikasi 401 massal menggunakan proteksi *thread-safe locking* (`ReentrantLock` / `Mutex`) untuk menjaga integritas sesi pengguna tanpa membebani infrastruktur server otentikasi.
3. **Monadic Functional Handling**: Mengonversi pengecualian runtime (*runtime exceptions*) menjadi tipe data monad yang aman (`NetworkResult<T>`) menggunakan kustomisasi `CallAdapterFactory`, yang menyederhanakan arsitektur repositori dan membersihkan *presentation layer* dari penanganan error boilerplate.
4. **Resilience Strategies**: Mencegah kegagalan kaskade (*cascading failure*) dan inkonsistensi data dengan mengombinasikan *Idempotency Keys*, *Conditional Caching* berbasis ETag, serta algoritma pemulihan *Exponential Backoff with Full Jitter*.