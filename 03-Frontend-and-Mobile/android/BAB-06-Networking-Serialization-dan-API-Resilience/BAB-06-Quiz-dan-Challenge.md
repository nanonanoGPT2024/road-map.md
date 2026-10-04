# BAB 06: Quiz, Challenge, & Knowledge Check
**Networking, Serialization, & API Resilience**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Arsitektur Interceptor Chain pada OkHttp:**
   Jelaskan secara mendalam alur eksekusi `RealInterceptorChain` pada OkHttp. Apa perbedaan fundamental antara **Application Interceptors** (`addInterceptor`) dan **Network Interceptors** (`addNetworkInterceptor`) dalam kaitannya dengan kompresi data (*transparent GZIP*), *caching layer*, *redirects/retries*, dan observabilitas HTTP header asli?

2. **Paradigma Serialization (Reflection vs. Code Generation vs. Compiler Plugin):**
   Bandingkan Gson, Moshi (dengan KSP), dan Kotlinx Serialization dalam memproses payload JSON ke model Kotlin. Mengapa pendekatan *reflection-based* (seperti Gson standar) dapat merusak jaminan *null-safety* dan nilai *default parameter* pada Kotlin `data class`, serta bagaimana pendekatan *compiler-plugin* (Kotlinx Serialization) memecahkan masalah ini tanpa *runtime overhead*?

3. **Mekanisme HTTP Connection Pooling:**
   Bagaimana implementasi `ConnectionPool` pada OkHttp bekerja dalam mengelola reuse koneksi TCP menggunakan HTTP/1.1 `Keep-Alive` dan HTTP/2 multiplexing? Parameter apa saja yang menentukan siklus hidup soket (idle timeout, max idle connections), dan apa dampak salah konfigurasi connection pool terhadap latensi dan konsumsi baterai perangkat mobile?

4. **Dinamika Retrofit Under-the-Hood & Kotlin Coroutines:**
   Bagaimana Retrofit menggunakan `java.lang.reflect.Proxy` (`Proxy.newProxyInstance`) untuk mentransformasikan interface Kotlin menjadi eksekusi jaringan konkret? Jelaskan bagaimana Retrofit secara internal mengekstrak `Continuation` dari fungsi `suspend` dan menjembataninya dengan asynchronous `Call.enqueue()` milik OkHttp.

5. **Semantik HTTP Method, Idempotensi, dan Safety:**
   Jelaskan definisi *safe* dan *idempotent* methods menurut RFC 7231 (HTTP/1.1 Semantics). Mengapa operasi retry otomatis pada level jaringan (*network-level retry*) boleh diterapkan pada `GET` dan `PUT`, tetapi sangat berbahaya jika diterapkan secara membabi-buta pada `POST` dan `PATCH` tanpa implementasi *Idempotency-Key*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Thundering Herd Problem pada Token Refresh Concurrency:**
   Ketika akses token (JWT) kedaluwarsa dan 10 *network request* berjalan secara paralel dan menerima HTTP 401 Unauthorized secara bersamaan, bagaimana Anda mendesain mekanisme re-autentikasi menggunakan OkHttp `Authenticator` atau `Interceptor` agar *refresh token request* hanya dieksekusi tepat **satu kali**, sementara 9 request lainnya mengantre secara aman (*thread-safe*) tanpa memicu pembatalan sesi (*session invalidation*)?

2. **Propagasi Pembatalan Coroutine ke Soket Jaringan:**
   Ketika sebuah `Job` Coroutine yang menjalankan pemanggilan Retrofit `suspend` di-*cancel* (misalnya pengguna menekan tombol *Back* dan `viewModelScope` dibatalkan), apa yang terjadi pada layer OkHttp `Call` dan soket TCP di baliknya? Kapan soket ditutup secara paksa (`socket.close()`), dan bagaimana perilaku ini berbeda antara HTTP/1.1 dan HTTP/2 stream?

3. **Certificate & Public Key Pinning (HPKP/SPKI) Resilience:**
   Bagaimana cara mengonfigurasi `CertificatePinner` di OkHttp menggunakan SHA-256 hash dari *Subject Public Key Info* (SPKI)? Mengapa pinning terhadap Leaf Certificate memiliki risiko tinggi membuat aplikasi "bricked" (tidak bisa dibuka) saat sertifikat kedaluwarsa atau di-revoke, dan bagaimana strategi *backup pins* dan *graceful fallback* harus diimplementasikan?

4. **Streaming Payloads & Memory Leak Prevention:**
   Mengapa mengeksekusi `response.body()?.string()` pada endpoint yang mengunduh file besar atau data berukuran puluhan megabyte langsung menyebabkan `OutOfMemoryError` (OOM)? Tunjukkan bagaimana Anda mengonsumsi data tersebut secara reaktif menggunakan `ResponseBody.byteStream()` / Okio `BufferedSource` yang dialirkan ke Kotlin `Flow<ByteArray>` untuk menjaga *heap memory footprint* tetap konstan di bawah ambang batas kritis.

5. **Resilient JSON Deserialization & Polymorphism:**
   Backend mengubah schema API: sebuah field yang sebelumnya mengembalikan array of string `["A", "B"]` tiba-tiba mengembalikan objek polimorfik, atau terdapat nilai `enum` baru yang belum didefinisikan pada client. Bagaimana Anda mengonfigurasi Kotlinx Serialization / Moshi untuk:
   - Mengabaikan key yang tidak dikenal (*ignore unknown keys*).
   - Menangani *unknown enum* tanpa melempar `SerializationException`.
   - Menggunakan *custom fallback deserializer* untuk mencegah crash global pada satu layar.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Thread Starvation & Socket Leakage pada Flash Sale
Sebuah aplikasi e-commerce enterprise mengalami lonjakan metrik crash rate akibat `SocketTimeoutException` dan `OutOfMemoryError: pthread_create failed` saat event flash sale berlangsung. 
Setelah dilakukan investigasi APM (Application Performance Monitoring), ditemukan bahwa tim developer membuat instance `OkHttpClient` baru di dalam repository layer setiap kali sebuah request dipanggil (`OkHttpClient().newBuilder()...build()`), dan beberapa response body tidak ditutup (`close()`) ketika HTTP status code bernilai selain 200 (misalnya pada error 4xx/5xx).

**Pertanyaan Diagnostik:**
1. Jelaskan secara teknis mengapa pembuatan `OkHttpClient` per-request memicu *thread starvation* dan melumpuhkan sistem alokasi soket OS Android!
2. Mengapa tidak memanggil `response.close()` atau tidak mengonsumsi `response.body()` secara tuntas dapat menyebabkan *connection leak* pada `ConnectionPool`?
3. Rancang arsitektur singleton OkHttp Client berbasis Dagger/Hilt yang memfasilitasi kebutuhan konfigurasi dinamis (misal: timeout berbeda untuk file upload vs data fetching) tanpa menduplikasi thread pool dan connection pool!

---

### Skenario B: Race Condition & Token Replay pada Dual-Engine Authenticator
Aplikasi mobile perbankan menggunakan arsitektur modular multi-module. Tim mendesain sistem otentikasi di mana sesi diamankan dengan access token berumur pendek (5 menit) dan refresh token berumur panjang (30 hari). 
Ketika koneksi tidak stabil, terjadi kondisi di mana endpoint transaksi finansial mengalami timeout lokal (client-side 30s timeout), namun backend berhasil memproses transaksi dan telah menginvalidasi token lama. Saat client mencoba me-refresh token via OkHttp `Authenticator`, respons dari server menyatakan refresh token sudah terpakai (*Token Reuse Detected*), memicu *auto-logout* dan membatalkan transaksi yang sebenarnya sudah berhasil di sisi database perbankan.

**Pertanyaan Diagnostik:**
1. Di mana letak kelemahan desentralisasi state otentikasi pada kasus di atas?
2. Bagaimana cara mengimplementasikan *state machine* otentikasi terpusat menggunakan Kotlin `Mutex` dan token store reaktif untuk memastikan hanya ada satu alur pertukaran token yang aktif pada satu waktu?
3. Bagaimana mekanisme *Idempotency-Key* berbasis UUID yang dikombinasikan dengan interceptor dapat mencegah duplikasi transaksi finansial saat terjadi timeout di level socket read?

---

### Skenario C: Trade-off Arsitektur Offline-First Sync & Resilience Engine
Anda adalah Lead Architect untuk aplikasi sistem logistik lapangan yang digunakan oleh kurir di area terpencil dengan sinyal 2G/EDGE atau *zero connectivity*. Kurir melakukan update status paket, memindai barcode, dan mengunggah tanda tangan penerima secara offline.
Manajemen menuntut sistem memiliki:
- *Zero data loss* saat koneksi terputus.
- Tidak terjadi *battery drain* akibat retry loop yang agresif.
- Konsistensi data antara database lokal (Room) dan remote database ketika perangkat kembali online.

**Pertanyaan Diagnostik:**
1. Evaluasi trade-off antara menggunakan **HTTP-level Caching (OkHttp Cache-Control)** versus **Database-backed Offline-First (Room as Single Source of Truth + WorkManager)** untuk kasus ini. Mengapa HTTP Cache saja tidak cukup?
2. Rancang strategi mitigasi *network flapping* (koneksi terputus-sambung dengan cepat) menggunakan algoritma **Exponential Backoff dengan Full Jitter**. Berikan rumus matematika dan alasan implementasi jitter!
3. Jika kurir A mengupdate status paket menjadi "DELIVERED" secara offline pada jam 10:00, dan kurir B (via dispatch central) mengupdate status menjadi "RESCHEDULED" pada jam 10:05 online, bagaimana strategi *Conflict Resolution* (Last-Write-Wins vs Vector Clocks/Version Stamping) harus diterapkan pada layer sinkronisasi?

---

## 4. Chapter Challenge

### Tantangan Praktis: Production-Grade Resilient Network Core Engine

#### Problem:
Sebagian besar networking layer pada aplikasi Android dibuat secara naif: token refresh menyebabkan crash race-condition, retry logic membombardir server yang sedang down (*cascading failure*), error handling tersebar acak di Presenter/ViewModel tanpa standardisasi, dan schema breaking pada backend memicu NPE atau serialization crash.

#### Requirements:
Anda diminta membangun sebuah modul networking terisolasi (`:core:network`) yang siap digunakan pada level enterprise dengan spesifikasi:
1. **Thread-Safe Authenticator:** Implementasikan `okhttp3.Authenticator` yang menangani HTTP 401. Gunakan Kotlin `Mutex` untuk sinkronisasi pemanggilan refresh token. Jika refresh berhasil, request yang gagal harus di-*replay* dengan token baru. Jika refresh gagal (misal refresh token expired), sistem harus memancarkan event `SessionExpired` via `SharedFlow` global.
2. **Exponential Backoff with Full Jitter Interceptor:** Buat custom `Interceptor` yang menangani HTTP 5xx dan `IOException`. Implementasikan algoritma retry bertingkat (maksimal 3x) dengan formula:
   $$\text{Sleep} = \text{random}(0, \min(M, B \times 2^A))$$
   *(di mana $M$ = max backoff, $B$ = base backoff, $A$ = retry attempt).*
3. **Robust Sealed Result Flow:** Bangun Retrofit `CallAdapterFactory` kustom yang membungkus semua return type endpoint menjadi `NetworkResult<T>`:
   ```kotlin
   sealed interface NetworkResult<out T> {
       data class Success<T>(val data: T, val statusCode: Int) : NetworkResult<T>
       data class HttpError(val code: Int, val errorBody: String?) : NetworkResult<Nothing>
       data class NetworkFailure(val throwable: Throwable) : NetworkResult<Nothing> // Timeout, DNS, No Internet
       data class SerializationError(val throwable: Throwable) : NetworkResult<Nothing>
   }
   ```
4. **Crash-Proof Serialization:** Konfigurasikan Kotlinx Serialization engine dengan toleransi:
   - Mengabaikan field yang tidak diketahui (`ignoreUnknownKeys = true`).
   - Memberikan nilai default jika field bernilai null padahal di Kotlin non-nullable (`coerceInputValues = true`).

#### Constraints:
- Dilarang keras menggunakan library retry pihak ketiga (seperti RxJava retry/Resilience4j). Gunakan pure OkHttp, Retrofit, dan Kotlin Coroutines.
- Memory leak free: semua stream data harus ditutup secara eksplisit.
- Client timeout harus dikonfigurasi secara ketat: Connect Timeout (10s), Read Timeout (15s), Write Timeout (15s).

#### Expected Output:
1. Kode sumber Kotlin untuk:
   - `TokenAuthenticator.kt` (lengkap dengan `Mutex` lock).
   - `ExponentialBackoffInterceptor.kt`.
   - `NetworkResultCallAdapterFactory.kt` (beserta delegasi `Call<T>`).
2. Blueprint setup dependency injection untuk `OkHttpClient` dan `Retrofit`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan lifecycle, scope, dan context antara Application Interceptor vs Network Interceptor pada OkHttp.
- [ ] Dampak alokasi memori dan reflection lookup antara Gson, Moshi KSP, dan Kotlinx Serialization.
- [ ] Alur kerja TCP 3-Way Handshake, TLS Handshake, dan bagaimana HTTP/2 Multiplexing mengurangi latensi koneksi.
- [ ] Mekanisme internal `CallAdapter.Factory` dan `Converter.Factory` pada Retrofit.
- [ ] Mengapa `OkHttpClient` harus dikonfigurasi sebagai Singleton dan bahaya menduplikasi instance-nya.
- [ ] Perbedaan semantik kegagalan: Transport/Protocol Error (`IOException`), HTTP API Error (4xx, 5xx), dan Parsing Error (`SerializationException`).
- [ ] Cara kerja `Authenticator` OkHttp dan responsibilitasnya terhadap infinite loop prevention (header check/retry counter).
- [ ] Logika isolasi eksekusi non-blocking I/O pada Coroutine menggunakan `Dispatchers.IO`.

### Saya tidak perlu menghafal:
- [ ] Seluruh format ASN.1 struktur byte dari X.509 Certificate (cukup pahami cara ekstraksi SHA-256 fingerprint).
- [ ] Sintaks exact byte buffer manipulasi Okio tingkat rendah (cukup kuasai `BufferedSource` dan `BufferedSink` API standar).
- [ ] Detail implementasi algoritma GZIP compression header (OkHttp menanganinya secara transparan via `BridgeInterceptor`).
- [ ] String template regex untuk parsing HTTP headers secara manual.

### Saya harus bisa melakukan:
- [ ] Menulis custom OkHttp Interceptor untuk injeksi auth header, logging terenkripsi, dynamic base URL routing, dan custom metrics APM.
- [ ] Mengonfigurasi Retrofit untuk mengembalikan tipe data custom (`NetworkResult<T>` atau Kotlin `Result<T>`) menggunakan custom `CallAdapter`.
- [ ] Mencegah thundering herd problem saat multi-threading token refresh menggunakan Kotlin Coroutines `Mutex`.
- [ ] Menganalisis network traffic dump menggunakan HTTP logging inspector (Chucker / Charles / Wireshark) untuk menemukan memory leak atau socket leak.
- [ ] Mengimplementasikan Public Key Pinning menggunakan `CertificatePinner` dengan backup pin yang aman dari bricking aplikasi.
- [ ] Menulis custom Serializer/Deserializer pada Kotlinx Serialization untuk memetakan JSON yang tidak standar (*malformed* atau polimorfik) ke strongly-typed data class.
- [ ] Menangani pemutusan koneksi yang elegan (*graceful degradation*) dan strategi retry berbasis Exponential Backoff with Jitter.