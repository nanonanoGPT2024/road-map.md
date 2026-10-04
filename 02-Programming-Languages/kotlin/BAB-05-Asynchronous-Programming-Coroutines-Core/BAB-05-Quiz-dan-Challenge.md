# BAB 05: Quiz, Challenge, & Knowledge Check
**Asynchronous Programming: Coroutines Core**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Mekanisme Continuation-Passing Style (CPS) dan State Machine:**  
   Jelaskan secara mendalam bagaimana Kotlin Compiler mentransformasi sebuah fungsi yang memiliki modifier `suspend`. Bagaimana compiler mengonversi local variables, titik suspensi (*suspension points*), dan alur kontrol percabangan menjadi sebuah *anonymous class* bertipe `ContinuationImpl` berbasis *state machine* (label switch-case)?

2. **Diferensiasi Thread Blocking vs Coroutine Suspension:**  
   Bedah perbedaan arsitektural level OS dan JVM antara memblokir thread (misal: `Thread.sleep()`) dengan menangguhkan coroutine (misal: `delay()`). Analisis alokasi call stack, register CPU, kernel context switch overhead, serta konsumsi memori heap untuk masing-masing pendekatan ketika mengeksekusi 100.000 unit pekerjaan secara konkuren.

3. **Anatomi dan Komposisi `CoroutineContext`:**  
   `CoroutineContext` diimplementasikan menyerupai struktur data *type-indexed heterogenous map*. Jelaskan peran serta relasi operasional antara `Job`, `CoroutineDispatcher`, `CoroutineExceptionHandler`, dan `CoroutineName`. Bagaimana operator polimorfik `+` bekerja saat terjadi konflik key pada context inheritance antara parent scope dan child scope?

4. **Struktur dan Invarian Structured Concurrency:**  
   Mengapa `GlobalScope` dikategorikan sebagai *code smell* dan anti-pattern dalam arsitektur enterprise? Jelaskan hierarki siklus hidup antara parent `Job` dan child `Job` pada builder standar (`launch` / `async`), khususnya terkait aturan:
   * Kapan parent coroutine berstatus *Completing* vs *Completed*.
   * Perilaku cascading cancellation ke seluruh sub-hierarki ketika salah satu child mengalami unhandled failure.

5. **Karakteristik Thread Pool pada Built-in Dispatchers:**  
   Bandingkan arsitektur internal thread pool dari `Dispatchers.Default` dan `Dispatchers.IO`. Bagaimana mekanika *work-stealing algorithm* pada coroutine scheduler JVM bekerja, dan bagaimana `Dispatchers.IO` mengizinkan elastisitas ukuran pool melewati batasan CPU cores tanpa mendegradasi performa thread pool `Default` yang berbagi underlying scheduler yang sama?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Cooperative Cancellation Mechanics & CPU-Bound Traps:**  
   Perhatikan loop kalkulasi intensif CPU berikut:
   ```kotlin
   val job = scope.launch(Dispatchers.Default) {
       var count = 0
       while (count < Int.MAX_VALUE) {
           computeHeavyHash(count++)
       }
   }
   // di thread lain:
   job.cancel()
   ```
   Mengapa coroutine di atas menolak berhenti (*unresponsive to cancellation*) meskipun `job.cancel()` telah dipanggil? Berikan minimal tiga pendekatan idiomatik berbeda untuk memperbaiki kode tersebut agar cancellation-compliant, dan jelaskan konsekuensi performa dari masing-masing pendekatan (`yield()`, `ensureActive()`, `isActive`).

2. **Mitigasi Anti-Pattern pada Penanganan `CancellationException`:**  
   Apa bahaya teknis dari menangkap `Throwable` atau `Exception` secara umum (`try { ... } catch (e: Exception) { ... }`) di dalam coroutine body tanpa melempar ulang `CancellationException`? Bagaimana siklus hidup coroutine rusak akibat praktik *swallowing exception* ini terhadap Structured Concurrency parent-nya?

3. **Kompleksitas Exception Propagation: `launch` vs `async`:**  
   Jelaskan perbedaan mendasar propagasi pengecualian (*exception propagation*) antara `launch` dan `async`. Mengapa `SupervisorJob` atau `supervisorScope` tidak menyelamatkan aplikasi dari crash jika pengecualian yang tidak tertangkap (*uncaught exception*) terjadi di dalam root `launch` tanpa dipasangi `CoroutineExceptionHandler`?

4. **Penggunaan Aman `NonCancellable` Context:**  
   Ketika coroutine dibatalkan saat sedang mengeksekusi I/O atau transaksi basis data, kita sering kali harus melakukan pembersihan (*cleanup*) di dalam blok `finally`. Mengapa pemanggilan suspend function biasa di dalam blok `finally` dari coroutine yang dibatalkan akan langsung gagal seketika? Jelaskan mekanisme internal `withContext(NonCancellable)` dan sebutkan bahaya jika ada operasi long-running yang tidak sengaja diletakkan di dalam scope tersebut.

5. **ThreadLocal Confinement Breakdown:**  
   Dalam framework berbasis Java/Spring lama, data trace ID (MDC) dan konteks transaksi sering disimpan dalam `ThreadLocal`. Mengapa coroutine yang bermigrasi antar-thread via dispatcher dapat merusak atau membocorkan data `ThreadLocal`? Jelaskan cara kerja `ThreadContextElement` (misalnya melalui `asContextElement()`) untuk mempertahankan sinkronisasi thread state selama proses context switching suspensi coroutine.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Thread Starvation pada Layanan FinTech Skala Besar
* **Konteks:** Sebuah microservice gateway memproses 8.000 RPS. Di bawah beban puncak, latency melonjak dari 15ms menjadi 12.000ms, diikuti kegagalan massal HTTP 504. Analisis thread dump JVM menunjukkan bahwa semua thread pada `CommonPool` dan `Dispatchers.Default` berada pada state `WAITING` atau `TIMED_WAITING`.
* **Investigasi Kode:** Ditemukan implementasi berikut di downstream client:
  ```kotlin
  suspend fun verifyFraudRisk(userId: String): RiskScore = withContext(Dispatchers.Default) {
      // Third-party legacy SDK yang menggunakan blocking OkHttpClient sinkron
      val response = legacySdkClient.executeCallSync(userId) 
      parseResponse(response)
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar masalah (*root cause*) arsitektural mengapa penggunaan `Dispatchers.Default` untuk synchronous blocking I/O memicu kelumpuhan seluruh sistem (termasuk coroutine kalkulasi bisnis murni yang tidak bersalah).
  2. Bagaimana modifikasi arsitektural dispatcher harus diterapkan? Jelaskan batas saturasi safe pool size jika menggunakan `Dispatchers.IO.limitedParallelism(...)`.
  3. Mengapa migrasi ke fully non-blocking asynchronous SDK (seperti Ktor Client berbasis CIO / Netty) lebih superior dibanding sekadar membesarkan ukuran thread pool `Dispatchers.IO`?

### Skenario B: Race Condition dan Data Inconsistency pada Engine Inventaris Flash Sale
* **Konteks:** Sistem flash sale e-commerce mencatat over-selling fatal: 100 unit barang terjual ke 142 pembeli berbeda. Kode sinkronisasi inventaris berjalan di memori lokal instans sebelum dikirim ke Redis:
  ```kotlin
  class InventoryManager {
      var availableStock: Int = 100
      
      suspend fun reserveStock(quantity: Int): Boolean {
          if (availableStock >= quantity) {
              delay(5) // Simulasi I/O validasi credit scoring
              availableStock -= quantity
              return true
          }
          return false
      }
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Mengapa penggunaan primitif sinkronisasi Java klasik seperti `synchronized(lock)` atau `ReentrantLock` di sekitar suspensi `delay(5)` diharamkan dalam coroutine, dan dampak apa yang ditimbulkannya pada thread pool?
  2. Implementasikan refactoring aman menggunakan `kotlinx.coroutines.sync.Mutex`. Tunjukkan di mana letak potensi *deadlock* jika programmer secara ceroboh mengeksekusi cancellation saat mutex terkunci.
  3. Analisis trade-off performa: Kapan kita harus memilih `Mutex`, kapan harus menggunakan `AtomicInteger`, dan kapan harus mendesain arsitektur berbasis *single-threaded actor* / Channel confinement untuk beban konkurensi ekstrem?

### Skenario C: Arsitektur Pipeline Ingest Data IoT & Backpressure Mismatch
* **Konteks:** Layanan ingest data menerima stream telemetri dari 50.000 sensor IoT melalui WebSocket. Data sensor masuk ke coroutine pipeline untuk parsing, validasi enkripsi, agregasi batch, dan penulisan ke database time-series. Database hanya sanggup menangani maksimal 2.000 write ops/detik, sementara sensor menghasilkan lonjakan sesaat (*spike*) hingga 25.000 payloads/detik.
* **Pertanyaan Diagnostik:**
  1. Jika arsitek menggunakan pendekatan naif `payloadScope.launch { processAndPersist(payload) }` untuk setiap paket yang masuk, diskusikan kegagalan memori heap (OutOfMemoryError) dan coroutine context leaking yang tak terhindarkan.
  2. Rancang arsitektur pipeline menggunakan coroutine primitives (`Channel` atau `Flow`) yang menerapkan strategi *backpressure* eksplisit. 
  3. Bandingkan strategi *Buffer Overflow*: `BufferOverflow.SUSPEND`, `BufferOverflow.DROP_OLDEST`, dan `BufferOverflow.DROP_LATEST`. Kapan sistem IoT telemetri harus memilih dropping data daripada menangguhkan koneksi WebSocket ingestion?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Concurrent Bulk Downloader & Processing Engine with Adaptive Rate Limiter

#### Problem Statement
Anda ditugaskan membangun engine inti untuk modul sinkronisasi data perbankan yang harus mengunduh 50.000 payload audit dari legacy core-banking REST API yang tidak stabil, memprosesnya secara matematis, dan mengembalikannya sebagai laporan teragregasi.

#### Technical Requirements
1. **Concurrency Throttling:** Sistem tidak boleh mengeksekusi lebih dari `K` permintaan paralel ke downstream API secara simultan (misal: `K = 50`) untuk menghindari IP blacklisting. Gunakan coroutine primitive non-blocking (hindari thread-blocking sleep/semaphore).
2. **Transient Error Resilience with Exponential Backoff:** Setiap request yang menghasilkan status HTTP 5xx atau network failure harus dicoba ulang otomatis (*retry*) maksimal 3 kali dengan formula backoff eksponensial acak (*jitter*):
   $$\text{Delay} = \text{InitialDelay} \times 2^{\text{attempt}} + \text{jitter}$$
3. **Structured Hierarchy:** Seluruh proses batch harus berjalan di bawah satu parent scope. Jika parent scope dibatalkan (misal: HTTP request gateway klien timeout atau aplikasi menerima sinyal SIGTERM), seluruh sub-unduhan yang sedang berjalan harus dibatalkan seketika tanpa kebocoran resource (*graceful abort*).
4. **Failure Isolation:** Jika satu payload audit gagal secara permanen setelah 3 kali retry, kegagalan tersebut **tidak boleh** mematikan pemrosesan payload audit lainnya (*fault-tolerant execution*). Catat ID yang gagal ke dalam koleksi terpisah.
5. **Memory-Conscious Stream Aggregation:** Jangan menahan 50.000 raw JSON objects mentah di heap memory secara bersamaan. Lakukan streaming/processing secara pipelined sehingga data yang selesai diproses langsung dilepaskan ke Garbage Collector.

#### Constraints
* **Pure Kotlin Coroutines:** Hanya boleh menggunakan library `kotlinx-coroutines-core`. Dilarang menggunakan framework eksternal tingkat tinggi seperti Spring WebFlux, Project Reactor, atau RxJava.
* **Zero Thread Blocking:** Seluruh operasi I/O dan latency simulation wajib non-blocking (`delay`, asynchronous primitives). Thread blocking terdeteksi akan dianggap diskualifikasi.
* **Deterministic Metrics:** Engine harus mengeluarkan data statistik eksekusi: Total Diproses, Total Sukses, Total Gagal Permanen, Total Waktu Eksekusi, dan Peak Memory Usage.

#### Expected Output
* Kode implementasi production-ready dalam format class Kotlin:
  * `class BulkDataEngine(private val concurrencyLimit: Int, ...)`
  * Fungsi suspensi utama: `suspend fun executeSync(ids: List<String>): ExecutionReport`
* Unit test skenario menggunakan `runTest` dari `kotlinx-coroutines-test` yang memverifikasi:
  * Batas konkurensi `K` tidak pernah dilanggar (ukur via *active coroutine counter tracker*).
  * Efektivitas pembatalan cascading saat parent scope di-cancel di tengah eksekusi.
  * Ketahanan terhadap downstream crash parsial.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Transformasi internal compiler dari fungsi `suspend` menjadi *State Machine Continuation Passing Style (CPS)*.
- [ ] Perbedaan fundamental antara thread context-switching (OS level) dan coroutine suspension (Heap/User-space level).
- [ ] Struktur data, komposisi elemen, dan aturan pewarisan (*inheritance*) dalam `CoroutineContext`.
- [ ] Prinsip dan invarian *Structured Concurrency*: relasi parent-child, unhandled exception bubbling, dan completion boundaries.
- [ ] Perbedaan internal pool dan alokasi scheduler antara `Dispatchers.Default`, `Dispatchers.IO`, dan `Dispatchers.Main`.
- [ ] Mekanisme kooperatif pada Coroutine Cancellation dan lifecycle transitions dari sebuah `Job` (`New`, `Active`, `Completing`, `Completed`, `Cancelling`, `Cancelled`).
- [ ] Perilaku penanganan kegagalan pada `SupervisorJob` dan `supervisorScope` versus regular `Job` / `coroutineScope`.
- [ ] Masalah state corruption pada konkurensi coroutine dan strategi penanganannya (`Mutex`, `Atomic`, Thread Confinement).

### Saya tidak perlu menghafal:
- [ ] Nilai numerik bytecode label switch-case yang digenerate oleh Kotlin Compiler untuk suspension states.
- [ ] Implementasi algoritma bitwise masking yang digunakan secara internal oleh JVM Coroutine Scheduler.
- [ ] API signature mendalam dari internal helper classes coroutine (misal: `DispatchedContinuation`, `Symbol`).
- [ ] Konfigurasi default parameter spesifik OS kernel untuk max native thread limits.

### Saya harus bisa melakukan:
- [ ] Melakukan dekompilasi bytecode Kotlin ke Java (*Show Kotlin Bytecode -> Decompile*) untuk menganalisis CPS State Machine dari fungsi `suspend`.
- [ ] Mengidentifikasi dan memperbaiki CPU-intensive code yang tidak merespons cancellation menggunakan `yield()` atau `ensureActive()`.
- [ ] Mengonfigurasi `Dispatchers.IO.limitedParallelism` untuk mencegah insiden thread starvation pada synchronous downstream/legacy drivers.
- [ ] Menerapkan clean cleanup routines pada coroutine yang dibatalkan menggunakan `withContext(NonCancellable)` tanpa memicu memory leak.
- [ ] Mengintegrasikan konteks tracing terdistribusi (MDC/OpenTelemetry) ke dalam CoroutineContext menggunakan `ThreadContextElement`.
- [ ] Menulis deterministic asynchronous unit tests menggunakan `runTest`, `StandardTestDispatcher`, `TestScope`, dan virtual time manipulation (`advanceTimeBy`, `advanceUntilIdle`).