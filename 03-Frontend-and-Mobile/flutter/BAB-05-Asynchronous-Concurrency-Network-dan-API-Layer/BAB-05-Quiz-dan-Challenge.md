# BAB 05: Quiz, Challenge, & Knowledge Check
**Asynchronous Concurrency, Network & API Layer**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Dinamika Dart Event Loop & Prioritas Antrean**
   Jelaskan secara mendalam bagaimana Dart Runtime mengeksekusi *Event Queue* dan *Microtask Queue*. Apa implikasi teknis jika sebuah fungsi rekursif atau proses komputasi terjadwal terus-menerus menambahkan tugas ke dalam *Microtask Queue*, dan bagaimana hal tersebut secara spesifik memengaruhi rendering frame pada Flutter engine (Vsync pipeline)?

2. **Lifecycle dan Model Eksekusi: Future vs Stream**
   Bandingkan model komputasi `Future` dan `Stream` dari sudut pandang *memory allocation*, *laziness*, dan *lifecycle handling*. Pada skenario apa `StreamController.broadcast()` menghasilkan kebocoran memori (*memory leak*) atau *backpressure issue* jika dibandingkan dengan *single-subscription Stream* standar?

3. **Isolate Architecture: Shared-Memory vs Actor-like Concurrency**
   Dart menggunakan model konkurensi berbasis *Isolate* tanpa *shared-state multithreading*. Jelaskan arsitektur internal Isolate, bagaimana data ditransfer antar-Isolate via `SendPort`/`ReceivePort` (analisis perbedaan antara *deep copying* vs *zero-copy memory transfer* pada pointer berukuran besar via `TransferableTypedData`), dan mengapa Isolate tidak dapat mengakses global state Isolate lain secara langsung.

4. **Eksekusi Pipeline Interceptor pada Dio / Network Client**
   Dalam arsitektur *client-server* modern, bagaimana rantai eksekusi (*interceptor chain*) bekerja pada fase `onRequest`, `onResponse`, dan `onError`? Jelaskan bagaimana mekanisme bubbling error terjadi jika sebuah interceptor melempar exception baru pada fase `onError`, dan apa perbedaannya dengan me-resolve request menggunakan `handler.resolve()`.

5. **Biaya Komputasi Deserialisasi JSON di Main Thread**
   Mengapa eksekusi `jsonDecode()` terhadap payload JSON berukuran besar (misalnya: >5MB) di dalam *Main Isolate* menyebabkan UI jank/frame drop, meskipun pemanggilan HTTP-nya dibungkus dengan `async`/`await`? Jelaskan mengapa `async` bukan berarti *parallel execution*.

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Resolusi Race Condition pada Token Refresh (Simultaneous 401 Unauthorized)**
   Bayangkan sebuah aplikasi meluncurkan 6 request HTTP secara paralel saat *access token* kedaluwarsa. Keenam request tersebut menerima status HTTP 401 secara bersamaan. Jika tidak dimitigasi, aplikasi akan mengeksekusi 6 mutasi refresh token paralel yang memicu pembatalan sesi (*refresh token rotation reuse detection*). Rancang solusi deterministik menggunakan `QueuedInterceptor` (atau mekanisme locking/completer) untuk memastikan hanya ada **satu** request refresh token yang berjalan, sementara 5 request lainnya ditahan (*suspended*) dan diulang kembali (*retried*) menggunakan token baru.

2. **Debugging Memory Leak pada StreamSubscription di Flutter Lifecycle**
   Diberikan potongan kode di mana sebuah `StatefulWidget` melakukan `stream.listen()` di `initState()` tetapi tidak meng-cancel subscription tersebut di `dispose()`.
   * Apa yang terjadi pada instance `State` dan objek-objek di dalam closure listener tersebut di heap memory?
   * Bagaimana Dart Garbage Collector (Generational GC: Young Space vs Old Space) memperlakukan objek ini?
   * Tunjukkan pola implementasi kanonik untuk membersihkan atau mentransformasi lifecycle stream secara aman.

3. **Limitasi Isolate Boundary dan Serialization Constraint**
   Ketika menggunakan `compute()` atau `Isolate.spawn()`, developer sering menemui runtime error: `Invalid argument(s): Illegal argument in isolate message`. Sebutkan tipe-tipe data atau objek apa saja yang secara strictly **dilarang** dikirim melintasi Isolate boundary di Dart, jelaskan akar penyebab arsitekturalnya, dan bagaimana strategi mengatasinya saat memproses objek bisnis kompleks.

4. **Graceful Cancellation dengan CancelToken**
   Pada arsitektur pencarian real-time (*type-ahead search*), user mengetik kueri baru sebelum respons kueri sebelumnya selesai diterima. Jika hanya mengandalkan operator `debounce` tanpa melakukan pembatalan pada level HTTP socket (*TCP socket teardown* via `CancelToken`), apa dampak negatifnya terhadap *network bandwidth*, *server load*, dan *battery consumption*? Bagaimana alur eksekusi `CancelToken` membatalkan *in-flight connection* di level engine?

5. **Edge Cases pada Implementasi SSL/TLS Pinning**
   Anda mengonfigurasi *Certificate Public Key Pinning* (SPKI) menggunakan `SecurityContext` kustom pada level `HttpClientAdapter`. Jelaskan skenario kegagalan fatal yang dapat terjadi saat masa berlaku sertifikat server habis (*expired*) atau tim DevOps melakukan *emergency certificate rotation*. Bagaimana Anda mendesain arsitektur *network layer* yang aman dari serangan Man-In-The-Middle (MITM) namun tetap memiliki strategi *fail-safe* / *zero-downtime* saat rotasi sertifikat?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Catastrophic Frame Drop pada Infinite Scroll Feed
* **Kasus**: Sebuah aplikasi e-commerce skala besar menampilkan *infinite feed* dengan data dinamis. Ketika pengguna melakukan *fast-scrolling*, aplikasi mengalami penurunan frame drastis dari 120 FPS ke 18 FPS (*severe jank*). Profiling via DevTools CPU Profiler menunjukkan bahwa 80% waktu Main Isolate habis di thread Dart VM untuk eksekusi fungsi `jsonDecode` dan parsing model `freezed` dari respons API sebesar 8 MB per pagination page.
* **Pertanyaan Diagnostik**:
  1. Bagaimana Anda merestrukturisasi alur data dari penerimaan respons raw bytes (dari network layer) hingga menjadi immutable model class tanpa memblokir UI thread sedikit pun?
  2. Tentukan trade-off antara penggunaan `Isolate.run()` per-request pagination vs membuat satu *Long-Running Background Worker Isolate* dengan persistent `ReceivePort`/`SendPort`! Kapan overhead pembuatan isolate baru mengeliminasi keuntungan performanya?

### Skenario B: Race Condition Sinkronisasi Cache Lokal & Server
* **Kasus**: Pengguna membuka aplikasi perbankan dalam kondisi koneksi *intermittent* (sinyal fluktuatif 3G/Edge). Aplikasi menerapkan *offline-first pattern*: saat transfer berhasil diinput, state balance langsung dimutasi secara optimistik di database lokal (Isar/Drift), lalu request mutasi dikirim ke server. Namun, server lambat merespons (high latency ~8 detik). Di detik ke-3, user melakukan *pull-to-refresh*, yang memicu query balance ke server via endpoint GET `/balance`. Respons GET `/balance` tiba lebih dulu di detik ke-5 dengan data lama (sebelum transfer), sedangkan respons POST `/transfer` baru sukses di detik ke-8. Hal ini membuat saldo pengguna di UI melonjak mundur (glitch).
* **Pertanyaan Diagnostik**:
  1. Identifikasi kegagalan integritas konkurensi pada arsitektur di atas.
  2. Rancang arsitektur sinkronisasi mutasi dan query yang deterministik (misalnya menggunakan *Optimistic Locking*, *Monotonic Versioning*, atau *Command Query Responsibility Segregation (CQRS) with Outbox Pattern*) pada level client untuk mencegah data lama menimpa state optimistik yang masih berstatus pending.

### Skenario C: Arsitektur Resilient Network Polling vs SSE vs WebSocket
* **Kasus**: Sistem logistik mengharuskan aplikasi driver mengirim lokasi real-time setiap 3 detik sekaligus menerima update pesanan baru secara real-time. Infrastruktur eksisting menggunakan HTTP Polling konvensional, yang menyebabkan: (1) battery drain parah pada device driver, (2) beban CPU server melonjak akibat overhead TLS handshake berulang, dan (3) latensi notifikasi pesanan tidak dapat diprediksi. Tim engineer berdebat antara mengganti seluruh layer menggunakan mTLS gRPC over HTTP/2, WebSocket duplex connection, atau Server-Sent Events (SSE) dikombinasikan dengan POST endpoint.
* **Pertanyaan Diagnostik**:
  1. Evaluasi arsitektur mana yang paling optimal untuk kebutuhan telemetri dua arah (driver upload koordinat GPS, server push order) dengan mempertimbangkan kendala: kondisi sinyal sering terputus (*reconnection storm*), efisiensi konsumsi baterai, dan ukuran payload!
  2. Buat mitigasi arsitektur untuk *connection drop* dan *offline buffering* ketika driver melewati terowongan/area blank spot selama 2 menit.

---

## 4. Chapter Challenge

### Tantangan Praktis: Enterprise-Grade Resilient HTTP Client Engine
Buat sebuah modul *Networking Core* menggunakan `dio` yang mengabstraksi seluruh kompleksitas komunikasi API enterprise.

#### Problem
Banyak aplikasi Flutter crash atau menghasilkan UX buruk karena tidak menangani network instability: token refresh gagal secara serentak, payload besar membuat freeze tampilan, koneksi timeout tidak diulang secara cerdas, dan tidak ada proteksi terhadap retry yang berlebihan.

#### Requirements
1. **Isolated Deserialization**: Buat transformer atau worker pool kustom sehingga seluruh proses deserialisasi string JSON -> Dart Model selalu dipindahkan dari Main Isolate menggunakan `Isolate.run()` atau persistent worker isolate jika payload > 50KB.
2. **Deterministic Token Rotation Interceptor**:
   * Implementasikan interceptor yang menangani HTTP 401.
   * Gunakan antrean berbasis Dart `Completer` atau locking queue untuk menahan semua request paralel saat satu request me-refresh token via API `/auth/refresh`.
   * Jika refresh token gagal (misal: refresh token expired), abort semua antrean request, bersihkan session lokal, dan pancarkan state event `UnauthenticatedException` ke global stream.
3. **Resilient Retry Engine dengan Exponential Backoff & Jitter**:
   * Request yang gagal karena network error / socket exception / HTTP 5xx harus secara otomatis di-retry maksimal 3 kali.
   * Gunakan formula *Exponential Backoff with Full Jitter* untuk mencegah *thundering herd problem*.
   * Request dengan method non-idempotent (misalnya POST/PATCH) **tidak boleh** di-retry secara otomatis kecuali secara eksplisit ditandai aman via `Options.extra`.
4. **Unified Error Handling Abstraction**:
   * Bungkus semua output networking ke dalam tipe fungsional Result monad (e.g., `Result<T, NetworkFailure>`) tanpa pernah melempar unhandled raw exception ke presentation layer.

#### Constraints
* **Thread Safety**: Tidak boleh ada state race condition pada shared refresh token process.
* **Zero UI Jank**: Parsing mock payload JSON array 20.000 records tidak boleh mendegradasi render time frame UI di atas 16ms (60 FPS) / 8ms (120 FPS).
* **Code Cleanliness**: Terapkan arsitektur modular yang decoupled dari UI framework (pure Dart core logic).

#### Expected Output
* File arsitektur inti:
  * `network_client.dart` (Inisialisasi Dio, adapter, dan client interface)
  * `token_refresh_interceptor.dart` (Concurrency-safe lock mechanism)
  * `retry_interceptor.dart` (Backoff with jitter logic)
  * `isolate_transformer.dart` (Background JSON parsing)
  * `network_result.dart` (Functional failure/success wrapper)
* Test suite (`test/network_test.dart`) yang memverifikasi bahwa 5 request paralel 401 hanya memicu 1 call ke endpoint refresh, dan kelimanya sukses diulang dengan access token baru.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus kerja Dart Event Loop: perbedaan fundamental antara Microtask Queue dan Event Queue beserta urutan prioritasnya.
- [ ] Karakteristik Isolate: memory boundary, biaya overhead pembuatan Isolate, komunikasi via Port, dan `TransferableTypedData`.
- [ ] Perbedaan model eksekusi `Future` (single completion) dan `Stream` (continuous sequence), serta semantik *cold* vs *hot/broadcast* stream.
- [ ] Mekanisme kerja HTTP Interceptor chain: modifikasi request, transformasi response, dan penanganan interceptor errors.
- [ ] Mengapa `async/await` bersifat non-blocking I/O tetapi tetap berjalan di single-thread Main Isolate.
- [ ] Algoritma retry resilience: perbedaan antara fixed retry, linear backoff, dan exponential backoff with full jitter.
- [ ] Prinsip keamanan komunikasi mobile: Man-in-the-Middle (MITM), SSL Pinning (Certificate & Public Key Hash), dan Certificate Transparency.

### Saya tidak perlu menghafal:
- [ ] Setiap kode status HTTP numerik yang jarang digunakan (cukup kuasai blok 2xx, 3xx, 4xx, 5xx umum).
- [ ] Syntax konfigurasi detail OpenSSL command line untuk ekstrak SHA256 public key (cukup simpan di runbook/cheatsheet CI/CD).
- [ ] Seluruh parameter opsional konfigurasi low-level `dart:io` `SecurityContext`.

### Saya harus bisa melakukan:
- [ ] Melakukan profiling frame drops via Flutter DevTools CPU Profiler dan mengidentifikasi bottleneck eksekusi kode sinkron di Main Thread.
- [ ] Menulis arsitektur *concurrent-safe refresh token* interceptor tanpa menghasilkan deadlock atau duplicate refresh calls.
- [ ] Memindahkan proses parsing data berukuran besar ke background worker menggunakan Isolate API tanpa memutus lifecycle aplikasi.
- [ ] Mengimplementasikan pembatalan HTTP request (*cancellation token*) secara tepat pada saat perpindahan halaman atau perubahan user input.
- [ ] Menerapkan *centralized error handling* yang memetakan error platform/network (DioException, SocketException, TimeoutException) ke domain-level failure yang informatif.