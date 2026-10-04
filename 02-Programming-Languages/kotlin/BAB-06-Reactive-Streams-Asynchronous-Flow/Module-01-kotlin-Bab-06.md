# BAB 06: ASYNCHRONOUS & CONCURRENT PROGRAMMING
## MODULE 01: Reactive Streams & Asynchronous Flow

---

### SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** KOT-ASYNC-0601
* **Jalur Pembelajaran:** Advanced Kotlin Core & Asynchronous Systems
* **Tingkat Kesulitan:** Tingkat Lanjut (Advanced)
* **Prasyarat:** 
  * Pemahaman mendalam tentang Kotlin Coroutines dasar (`suspend`, `CoroutineScope`, `Dispatchers`, `Job`).
  * Konsep konkurensi dasar (Thread safety, Deadlock, Race Condition).
  * Pemahaman umum mengenai paradigma Reactive Programming (Observer Pattern, Push vs Pull).
* **Estimasi Waktu Belajar:** 6 – 8 Jam (Teori, Analisis Source Code, Praktikum Mandiri)
* **Kebutuhan Teknis:** 
  * JDK 17 atau yang lebih baru.
  * Kotlin Compiler / SDK 1.9.20+.
  * Dependensi: `org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0` dan `org.jetbrains.kotlinx:kotlinx-coroutines-reactive:1.8.0`.

---

### SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis (Analyze)** arsitektur internal Kotlin Asynchronous Flow dan mekanismenya dalam mengimplementasikan prinsip Reactive Streams tanpa overhead memori berlebih.
2. **Membedakan (Differentiate)** secara presisi antara model data Cold Streams (`Flow`) dan Hot Streams (`StateFlow`, `SharedFlow`, `Channel`), serta menentukan penggunaannya berdasarkan lifecycle dan kebutuhan sistem.
3. **Mendiagnosis & Mengatasi (Troubleshoot)** masalah *Backpressure* menggunakan mekanisme suspensi Kotlin, serta operator modulasi aliran data (`buffer`, `conflate`, `collectLatest`).
4. **Mengimplementasikan (Implement)** integrasi mulus antara ekosistem Kotlin Coroutines dengan standard Reactive Streams (RxJava3 / Project Reactor) menggunakan layer interoperabilitas `kotlinx-coroutines-reactive`.
5. **Mendesain (Design)** arsitektur pipeline data throughput tinggi yang tahan uji (*fault-tolerant*), aman terhadap konkurensi, dan mematuhi prinsip *Context Preservation* serta *Cancellation Transparency*.

---

### SEKSI 03 — MINDSET & MENTAL MODEL

Dalam pemrograman sinkron tradisional, konsumsi data bersifat **Pull-based** melalui struktur data iterable: pemanggil memegang kendali penuh atas kapan elemen berikutnya diambil (`iterator.next()`), namun thread pemanggil akan diblokir (*blocking*) jika data belum siap secara I/O.

Sebaliknya, arsitektur Reactive Streams tradisional (seperti RxJava atau Project Reactor) mempopulerkan paradigma **Push-based**: produsen memancarkan (*emit*) data segera setelah data tersedia langsung ke konsumen. Masalah mendasar muncul ketika produsen memproduksi data jauh lebih cepat daripada kemampuan pemrosesan konsumen. Untuk mengatasi ini, spesifikasi Reactive Streams memperkenalkan *Backpressure* melalui mekanisme kredit (`Subscription.request(n)`). Konsekuensinya, kompleksitas internal pustaka meningkat secara eksponensial akibat kebutuhan penanganan alokasi buffer thread-safe dan manajemen *state machine* internal.

```
PULL (Iterator)         : Konsumen [Tanya Data] ------> Produsen [Hitung & Kembalikan] (Thread Terblokir)
PUSH (Reactive Streams) : Produsen [Kirim Data!]  ------> Konsumen [Kewalahan! Butuh request(n)]
SUSPENDING PUSH (Flow)  : Produsen [emit()]      -------> Konsumen [Proses...] 
                          (Produsen otomatis TERSUSPENSI hingga Konsumen siap)
```

Kotlin Asynchronous Flow mengintroduksi mental model **Suspending Push-Stream**. Alih-alih mengelola negosiasi kredit *request-n* yang rumit, Kotlin memanfaatkan primitif penangguhan (*suspension*) coroutine:
* Operator `emit()` adalah `suspend fun`.
* Fungsi terminal `collect()` adalah `suspend fun`.

Jika konsumen lambat, fungsi `emit()` pada produsen ditangguhkan (*suspended*) di level Coroutine Continuation tanpa memblokir thread sistem operasi. Backpressure diselesaikan secara intrinsik oleh mekanisme *suspension points* bahasa, menghasilkan kode yang sebersih pemrograman sekuensial sinkron namun sefleksibel dan sekuat arsitektur reaktif non-blocking.

---

### SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme internal pengeksekusian Flow beroperasi secara terpadu melalui *Collector Boundary*, transmisi kontekstual, dan kontrol penangguhan balik (*backpressure suspension*).

```
+-----------------------------------------------------------------------------------------------+
|                                      COROUTINE CONTEXT                                        |
|                                                                                               |
|  [ PRODUCER ENGINE ]                                                                          |
|  flow {                                                                                       |
|     emit(Data) ------+                                                                        |
|  }                   |                                                                        |
+----------------------|------------------------------------------------------------------------+
                       |  (1) suspend emit(value)
                       v
+-----------------------------------------------------------------------------------------------+
|  [ OPERATOR PIPELINE (INTERMEDIARY) ]                                                         |
|                                                                                               |
|  +---------------------------+       Buffer Full?                                             |
|  | buffer(capacity = 2)      | ====> [ SUSPEND PRODUCER ENGINE via Continuation ]             |
|  +---------------------------+                |                                               |
|               |                               | (Resume Producer saat buffer tersedia)        |
|               v                               |                                               |
|  +---------------------------+                |                                               |
|  | flowOn(Dispatchers.IO)    | <--------------+                                               |
|  +---------------------------+                                                                |
|               |                                                                               |
|               | (2) Context Preservation Switch (Channel-based decoupling boundary)           |
+---------------|-------------------------------------------------------------------------------+
                v
+-----------------------------------------------------------------------------------------------+
|  [ CONSUMER TERMINATION ENGINE ]                                                              |
|                                                                                               |
|  collect { item ->           <==== (3) Execution Context (e.g., Dispatchers.Default)          |
|      processConsistently(item)                                                                |
|  }                           ====> (4) Selesai: Mengirim sinyal Resume ke Suspended Operator  |
+-----------------------------------------------------------------------------------------------+
```

Diagram di atas mendemonstrasikan bagaimana data mengalir dari `Producer` melalui operator perantara menuju `Consumer`. Ketika produsen memancarkan data melampaui kapasitas serap konsumen (atau kapasitas buffer perantara), *Continuation* produsen ditangguhkan di titik emisi. Tidak ada alokasi thread yang tertahan menganggur; status eksekusi dibekukan dalam heap memory sebagai objek *Continuation*, lalu dieksekusi kembali secara presisi saat konsumen siap.

---

### SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Untuk memahami keanggunan Kotlin Flow, kita harus meninjau dua antarmuka paling inti dalam pustaka standar `kotlinx.coroutines.flow`:

```kotlin
// Anatomi Inti dari Flow
public interface Flow<out T> {
    public suspend fun collect(collector: FlowCollector<T>)
}

public fun interface FlowCollector<in T> {
    public suspend fun emit(value: T)
}
```

#### 1. Mekanisme "Direct Dispatch" pada Cold Flow
Sebuah *Cold Flow* pada dasarnya bukan antrian data (*queue*), melainkan fungsi lambda tertangguhkan yang dibungkus dalam sebuah antarmuka:
* Ketika Anda mendeklarasikan `val f = flow { emit(1) }`, belum ada alokasi komputasi yang berjalan.
* Ketika Anda memanggil `f.collect { value -> println(value) }`, implementasi runtime Kotlin mengoper *instance* lambda kolektor tersebut langsung ke blok pembangun `flow`.
* Panggilan `emit(1)` pada hakikatnya memanggil body dari lambda `collect` tersebut secara langsung melalui pemanggilan fungsi reguler (dengan mekanisme suspensi jika terjadi delay I/O).
* Keberadaan aliran data ini zero-overhead: tidak melibatkan thread pool tersendiri, lock, maupun antrian internal, kecuali Anda secara eksplisit menambahkan operator perantara seperti `buffer()`.

#### 2. Konvensi Penegakan Konteks (*Context Preservation Rule*)
Kotlin Flow menerapkan aturan mutlak yang disebut **Context Preservation**: konteks coroutine (`CoroutineContext`) dari pemanggil `collect` harus diwarisi dan dihormati oleh blok produsen. 

Secara internal, Kotlin menggunakan kelas pelindung `SafeCollector`. Setiap kali `emit()` dipanggil, runtime memvalidasi `currentCoroutineContext()` terhadap konteks yang direkam saat inisiasi `collect()`:

$$\text{Context}_{\text{emitter}} \equiv \text{Context}_{\text{collector}}$$

Jika terdeteksi bahwa produsen mencoba melakukan emisi dari konteks yang berbeda (misalnya, memanggil `withContext(Dispatchers.IO) { emit(...) }` di dalam blok `flow`), `SafeCollector` seketika melempar `IllegalStateException`. Ini mencegah kesalahan *race conditions* dan kebocoran konteks (*context leakage*). Operator resmi untuk mengubah konteks eksekusi produsen hanyalah `flowOn()`.

---

### SEKSI 06 — DEEP DIVE KONSEP & TEORI

#### 1. Klasifikasi Aliran Data: Cold vs Hot Streams

| Karakteristik | Cold Stream (`Flow`) | Hot Stream (`StateFlow` / `SharedFlow`) | Unbuffered Channel |
| :--- | :--- | :--- | :--- |
| **Eksekusi Produsen** | *On-Demand* (Hanya aktif saat ada pemanggilan `collect`). | *Eager/Independent* (Bisa aktif tanpa observer/kolektor). | Aktif saat coroutine pengirim (*sender*) berjalan. |
| **Penyimpanan State** | Statis/Unicast (Satu produsen untuk satu konsumen). | Multicast/Shared (Bisa banyak *subscriber* sekaligus). | Point-to-point / Unicast (Satu item dikonsumsi satu *receiver*). |
| **Riwayat Data (*Replay*)** | Selalu mengulang seluruh pipeline dari awal untuk setiap kolektor baru. | Dapat diatur (`replay = n`). `StateFlow` selalu menyimpan nilai terakhir (ukuran buffer = 1). | Tidak ada riwayat; data hangus setelah ditarik dari antrian. |
| **Karakteristik Terminasi** | Berhenti otomatis saat blok kode pemancar selesai atau dibatalkan. | Berlangsung tanpa henti (*infinite*) hingga cakupan siklus hidup dibatalkan. | Berhenti saat channel ditutup secara eksplisit via `close()`. |

#### 2. Strategi Mitigasi Backpressure
Ketika laju pemancaran ($R_{emit}$) secara persisten melampaui laju pemrosesan ($R_{process}$), terdapat tiga mekanisme arsitektural yang dapat diaktifkan:

1. **Buffering (`buffer(capacity, onBufferOverflow)`)**:
   Membuka batas konkurensi dengan menyisipkan struktur data `Channel` internal antara produsen dan konsumen. Produsen dapat terus berjalan tanpa menunggu konsumen hingga kapasitas buffer tercapai. Opsi *overflow* mencakup:
   * `BufferOverflow.SUSPEND`: Penangguhan emisi saat buffer penuh.
   * `BufferOverflow.DROP_OLDEST`: Menghapus data terlama di buffer untuk menampung data mutakhir.
   * `BufferOverflow.DROP_LATEST`: Membuang data yang baru saja tiba jika buffer penuh.

2. **Conflation (`conflate()`)**:
   Varian ekstrem dari buffering berkapasitas 1 dengan kebijakan `DROP_OLDEST`. Jika konsumen masih sibuk memproses item sebelumnya, seluruh item antara yang dipancarkan produsen akan dilewati, dan hanya item paling mutakhir (*latest*) yang dikirim ke konsumen.

3. **Collector Cancellation (`collectLatest { ... }`)**:
   Bukan mengabaikan data baru, melainkan **membatalkan** pengeksekusian blok pemrosesan data lama yang sedang berjalan begitu ada data baru yang masuk. Pendekatan ini umum digunakan pada pemrosesan antarmuka grafis atau pencarian dinamis (*search-as-you-type*).

#### 3. Interoperabilitas Reactive Streams Spesifikasi (JSR-314)
Kotlin tidak mengisolasi diri dari ekosistem reaktif JVM. Melalui artefak `kotlinx-coroutines-reactive`, pustaka ini menyediakan jembatan dua arah yang sepenuhnya tunduk pada spesifikasi JSR-314:
* `Publisher<T>.asFlow(): Flow<T>`: Mengonversi sembarang implementasi Reactive Streams (misal `Flux` atau `Flowable`) menjadi Kotlin Flow dengan menerjemahkan sinyal `request(n)` menjadi mekanisme suspensi coroutine secara transparan.
* `Flow<T>.asPublisher(): Publisher<T>`: Mengonversi Kotlin Flow menjadi Reactive Streams `Publisher`, mengekspos aturan kredit backpressure baku ke library pihak ketiga.

---

### SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi komprehensif yang mendemonstrasikan pembuatan Cold Flow, penerapan aturan transmisi konteks (`flowOn`), penanganan error secara deklaratif, serta pengelolaan *backpressure*.

```kotlin
package com.architect.reactive.fundamental

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.IOException

// 1. Data Contract
data class TelemetryPacket(val sensorId: String, val temperature: Double, val timestamp: Long)

// 2. Data Provider Component
object TelemetryEngine {
    fun streamSensorData(sensorId: String, totalPackets: Int): Flow<TelemetryPacket> = flow {
        println("[Producer] Memulai emisi data pada thread: ${Thread.currentThread().name}")
        
        for (sequence in 1..totalPackets) {
            // Simulasi kesalahan I/O pada pembacaan tertentu
            if (sequence == 4) {
                println("[Producer] Menemukan anomali hardware pada sequence $sequence...")
                throw IOException("Hardware sensor failure pada register 0x00F4")
            }

            val packet = TelemetryPacket(
                sensorId = sensorId,
                temperature = 20.0 + (sequence * 1.5),
                timestamp = System.currentTimeMillis()
            )

            println("[Producer] Emit data #${sequence} dari thread: ${Thread.currentThread().name}")
            emit(packet)
            
            // Penangguhan kooperatif produsen
            delay(100) 
        }
    }
    // Mengalihkan konteks upstream (eksekusi flow di atas) ke Thread Pool IO
    .flowOn(Dispatchers.IO)
}

// 3. Execution Entry Point
fun main(): Unit = runBlocking {
    println("[Main] Consumer beroperasi pada thread: ${Thread.currentThread().name}")

    TelemetryEngine.streamSensorData("SENSOR_CORE_01", totalPackets = 5)
        .onStart { 
            println("[Pipeline] Membuka saluran telemetry...") 
        }
        .filter { packet ->
            // Filter: Hanya loloskan data di atas 22.0 derajat Celsius
            packet.temperature > 22.0
        }
        .map { packet ->
            // Transformasi: Konversi ke representasi format log sistem
            "[TRANSFORMED] Sensor: ${packet.sensorId} | Temp: ${packet.temperature}°C"
        }
        .catch { cause ->
            // Error Handling: Menangkap IOException hulu secara graceful
            if (cause is IOException) {
                println("[ErrorHandler] Mengisolasi exception hulu: ${cause.message}")
                emit("[FALLBACK] Menyalakan sensor cadangan otomatis.")
            } else {
                throw cause // Re-throw fatal exceptions
            }
        }
        .onCompletion { cause ->
            if (cause == null) {
                println("[Pipeline] Saluran telemetry berhasil ditutup normal.")
            } else {
                println("[Pipeline] Saluran ditutup karena pembatalan/kegagalan: $cause")
            }
        }
        .collect { finalPayload ->
            // Terminal Operation: Berjalan pada konteks runBlocking (Main Thread)
            println("[Consumer] Data Diterima: $finalPayload | Thread: ${Thread.currentThread().name}")
            // Simulasi konsumen lambat untuk mengamati alur koordinasi
            delay(150)
        }
}
```

---

### SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi fundamental di atas:

* **Baris 11 (`fun streamSensorData(...) = flow { ... }`)**: Menggunakan builder fungsi `flow`. Blok ini mendefinisikan *Cold Flow*. Komputasi di dalamnya dibekukan (*suspended*) dan tidak akan pernah dieksekusi sebelum ada pemanggil terminal (`collect`).
* **Baris 16–18**: Menghadirkan skenario kegagalan deterministik. `IOException` dilempar langsung dari dalam blok pembangun untuk mendemonstrasikan propagasi exception hulu (*upstream*).
* **Baris 27 (`emit(packet)`)**: Memancarkan data secara non-blocking. Jika downstream lambat atau terjadi buffering suspension, pemanggilan ini menangguhkan coroutine produsen tanpa memblokir thread `Dispatchers.IO`.
* **Baris 33 (`.flowOn(Dispatchers.IO)`)**: Titik penentu arsitektur. Mengubah `CoroutineContext` **hanya** untuk operator dan pembangun yang berada di *upstream* (sebelum pemanggilan `flowOn`). Produsen kini dipaksa berjalan pada pool I/O, sementara konsumen downstream tetap berada pada thread asalnya.
* **Baris 42 (`.onStart { ... }`)**: Operator deklaratif yang diinjeksi sesaat sebelum emisi pertama dialirkan. Berguna untuk bootstrapping, alokasi resource, atau logging metadata.
* **Baris 45 (`.filter { ... }`)**: Operator transformasi bertipe perantara (*intermediate operator*). Bersifat *lazy*, mengevaluasi setiap item satu per satu di jalur pemrosesan tanpa mengalokasikan koleksi sementara di memori.
* **Baris 52 (`.catch { cause -> ... }`)**: Mengimplementasikan *Exception Transparency*. Menangkap *exception* yang meluncur secara vertikal dari hulu (*upstream*), namun sengaja **tidak** menangkap exception yang terjadi di blok `collect` downstream. Di sini, fallback data dipancarkan kembali ke stream secara elegan menggunakan `emit()`.
* **Baris 60 (`.onCompletion { cause -> ... }`)**: Menjamin eksekusi logika pembersihan (*cleanup logic*) mirip dengan blok `finally`, membedakan apakah terminasi terjadi secara normal atau akibat terminasi abnormal (*cancellation/error*).
* **Baris 67 (`.collect { ... }`)**: Panggilan fungsi suspensi terminal. Menginisialisasi transmisi, mendaftarkan lambda sebagai implementasi `FlowCollector`, dan menjalankan seluruh pipeline.

---

### SEKSI 09 — STUDI KASUS NYATA

#### Skenario: Pipeline Pemrosesan Pasar Keuangan (Crypto/Stock Order Book Aggregator)
Pada sistem bursa terdesentralisasi berkinerja tinggi, aliran transaksi (*tick stream*) diterima melalui sambungan WebSocket berkecepatan tinggi dengan laju data tak terkontrol (mencapai ribuan transaksi per detik saat volatilitas puncak).

Konsumen internal bertugas untuk:
1. Membaca data tick bursa mentah (*raw JSON stream*).
2. Memvalidasi dan menduplikasi transaksi berdasarkan UUID.
3. Melakukan agregasi metrik volume per interval waktu.
4. Menghindari lonjakan memori (*OOM Crash*) melalui *Backpressure Buffer Management*.
5. Menyimpan ringkasan transaksi ke database relasional/Time-Series yang memiliki latensi disk I/O terikat (*I/O bound constraint*).

Jika menggunakan Cold Flow murni secara langsung, transmisi jaringan WebSocket akan tersendat karena pembacaan socket tertahan oleh lambatnya operasi database. Jika menggunakan Reactive Channel tanpa batas, *Out-of-Memory Exception* akan terjadi seketika. Solusinya adalah mendesain arsitektur berbasis Hot-stream `SharedFlow` dengan buffer terikat (*bounded buffer*) dan strategi pembuangan terukur (*drop policies*).

---

### SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah arsitektur mikro untuk *Financial Trade Engine* menggunakan model Hot-Stream non-blocking:

```kotlin
package com.architect.reactive.production

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import java.math.BigDecimal
import java.util.concurrent.atomic.AtomicLong

// --- CONTRACT & DOMAIN MODELS ---
enum class OrderType { BUY, SELL }

data class TradeTick(
    val transactionId: Long,
    val symbol: String,
    val price: BigDecimal,
    val volume: Double,
    val timestamp: Long
)

// --- PRODUCTION INGESTION SERVICE ---
class MarketDataBroadcaster(
    private val scope: CoroutineScope
) {
    // SharedFlow bertindak sebagai Hot Event-Bus
    private val _rawTickStream = MutableSharedFlow<TradeTick>(
        replay = 0,                                   // Data historis tidak diputar ulang ke subscriber baru
        extraBufferCapacity = 64,                     // Buffer penahan burst-traffic
        onBufferOverflow = BufferOverflow.DROP_OLDEST // Lindungi integritas heap: buang data usang jika lagging
    )
    val rawTickStream: SharedFlow<TradeTick> = _rawTickStream.asSharedFlow()

    fun dispatchSocketEvent(tick: TradeTick) {
        val success = _rawTickStream.tryEmit(tick)
        if (!success) {
            // Log metrik ke sistem observabilitas jika terjadi pembuangan data di buffer hulu
            System.err.println("[Ingestion Warning] Buffer jenuh. Dropping event: ${tick.transactionId}")
        }
    }
}

// --- PERSISTENCE & ANALYTICS PIPELINE ---
class TradeAnalyticsPipeline(
    private val marketBroadcaster: MarketDataBroadcaster,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    private val processedCounter = AtomicLong(0)

    fun initializePipeline(scope: CoroutineScope): Job {
        return marketBroadcaster.rawTickStream
            // 1. Eksekusi filter dan de-duplikasi dasar
            .filter { tick -> tick.volume > 0.05 }
            
            // 2. Transmisi ke buffer internal untuk memisahkan producer rate dari pipeline analysis
            .buffer(capacity = 32, onBufferOverflow = BufferOverflow.SUSPEND)
            
            // 3. Transformasi data I/O bound dialihkan ke I/O Dispatcher
            .flowOn(ioDispatcher)
            
            // 4. Batching / Conflation / Throttling simulation via collectLatest
            // Mengambil aksi terpenting saat terjadi antrian persisten
            .onEach { tick ->
                persistToDatabase(tick)
                val total = processedCounter.incrementAndGet()
                println("[Database] Transaksi tersimpan: ID=${tick.transactionId} | Vol=${tick.volume} | Total=$total")
            }
            .catch { ex ->
                println("[Fatal Error Pipeline] Uncaught exception terdeteksi: ${ex.message}")
                ex.printStackTrace()
            }
            .launchIn(scope) // Menjalankan eksekusi stream terikat pada coroutine lifecycle scope
    }

    private suspend fun persistToDatabase(tick: TradeTick) {
        // Simulasi latensi Disk I/O Database 15ms
        delay(15)
    }
}

// --- SIMULATION HARNESS ---
fun main() = runBlocking {
    val masterScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val broadcaster = MarketDataBroadcaster(masterScope)
    val pipeline = TradeAnalyticsPipeline(broadcaster, Dispatchers.IO)

    // Inisialisasi pipeline konsumen
    val pipelineJob = pipeline.initializePipeline(masterScope)

    println("=== SIMULASI BURST TRAFFIC TICK BURSA DIMULAI ===")
    
    // Produsen: Mensimulasikan data tick masuk dari 3 thread socket secara bersamaan
    val socketProducers = List(3) { producerIndex ->
        masterScope.launch {
            for (i in 1..50) {
                val tick = TradeTick(
                    transactionId = (producerIndex * 1000L) + i,
                    symbol = "BTC/USDT",
                    price = BigDecimal("65000.00"),
                    volume = (i % 5 + 1) * 0.02, // Sebagian akan difilter (< 0.05)
                    timestamp = System.currentTimeMillis()
                )
                broadcaster.dispatchSocketEvent(tick)
                delay(5) // Produksi super cepat (5ms) melampaui kemampuan DB (15ms)
            }
        }
    }

    // Tunggu produsen selesai membanjiri data
    socketProducers.joinAll()
    
    // Berikan ruang buffer terusan untuk menguras antrian secara kooperatif
    delay(1000)

    println("=== MEMATIKAN PIPELINE SECARA GRACEFUL ===")
    pipelineJob.cancelAndJoin()
    masterScope.cancel()
}
```

---

### SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
+--------------------+-----------------------+-----------------------+-----------------------+
| PARAMETER          | KOTLIN FLOW           | RXJAVA 3              | PROJECT REACTOR       |
+--------------------+-----------------------+-----------------------+-----------------------+
| Paradigma Desain   | Coroutine Suspension  | Reactive Streams      | Reactive Streams      |
|                    | (Language Primitive)  | Specification (Spec)  | Specification (Spec)  |
+--------------------+-----------------------+-----------------------+-----------------------+
| Overhead Alokasi   | Sangat Rendah         | Sedang-Tinggi         | Sedang-Tinggi         |
| Memori Heap        | (Zero wrapper object  | (Banyak wrapper State | (Banyak wrapper State |
|                    | pada standard flow)   | & Subscriber)         | & Subscriber)         |
+--------------------+-----------------------+-----------------------+-----------------------+
| Kompleksitas       | Rendah                | Ekstrem               | Ekstrem               |
| Internal (Backpr.) | (Memanfaatkan suspensi| (Permintaan kredit    | (Permintaan kredit    |
|                    | bahasa tingkat native)| request(n) eksplisit) | request(n) eksplisit) |
+--------------------+-----------------------+-----------------------+-----------------------+
| Integrasi Context  | Asli (Native          | Terbatas (Perlu       | Terbatas (Harus via   |
| Tracking           | CoroutineContext)     | ThreadLocal manual)   | Reactor Context API)  |
+--------------------+-----------------------+-----------------------+-----------------------+
| Kurva Pembelajaran | Menengah (Identik     | Sangat Curam          | Sangat Curam          |
| Bagi Developer     | dengan kode sinkron)  | (200+ Operator khusus)| (Ratusan operator)    |
+--------------------+-----------------------+-----------------------+-----------------------+
```

#### Kapan Harus Memilih Kotlin Flow?
1. Seluruh arsitektur backend atau sistem dibangun dengan bahasa Kotlin murni dan Coroutines.
2. Lingkungan dengan keterbatasan alokasi memori ketat (contoh: Android Client, Edge Computing Node, Microservices dengan target footprint kecil).
3. Tim membutuhkan keterbacaan kode tinggi dengan paradigma pemrograman sekuensial terstruktur tanpa terjebak *operator overload*.

#### Kapan Memilih RxJava3 atau Project Reactor?
1. Mengembangkan sistem warisan (*legacy system*) berarsitektur Java murni.
2. Membutuhkan framework yang terintegrasi secara bawaan dengan ekosistem reaktif Java enterprise, seperti Spring WebFlux tingkat rendah yang bergantung penuh pada tipe data `Mono` dan `Flux`.

---

### SEKSI 12 — EDGE CASES & PITFALLS

#### 1. Menelan Pembatalan (*Swallowing CancellationException*)
Salah satu jebakan paling fatal dalam coroutine adalah menangkap `Throwable` atau `Exception` secara luas tanpa melempar kembali (`rethrow`) turunan `CancellationException`.

```kotlin
// BAHAYA: Memutus mekanisme structured concurrency!
flow.catch { e: Throwable -> 
    // Jika 'e' adalah CancellationException, Flow TIDAK AKAN PERNAH BISA DIBATALKAN!
    logger.error("Terjadi error: ${e.message}")
}

// SOLUSI BENAR:
flow.catch { e ->
    if (e is CancellationException) throw e
    logger.error("Aplikasi error sesungguhnya: ${e.message}")
}
```

#### 2. Pelanggaran Emisi Konteks (*Context Emission Violation*)
Mencoba memancarkan data di dalam flow builder menggunakan coroutine context yang dialihkan secara langsung:

```kotlin
// INI AKAN MELEMPAR: IllegalStateException (Flow invariant is violated)
fun leakyFlow(): Flow<Int> = flow {
    withContext(Dispatchers.IO) {
        emit(42) // ILEGAL! SafeCollector memvalidasi konteks pemanggil
    }
}

// SOLUSI BENAR: Gunakan 'flowOn' di luar builder
fun secureFlow(): Flow<Int> = flow {
    emit(42)
}.flowOn(Dispatchers.IO)

// Atau jika membutuhkan emisi multi-thread konkuren, gunakan 'channelFlow':
fun concurrentFlow(): Flow<Int> = channelFlow {
    withContext(Dispatchers.IO) {
        send(42) // VALID: Melalui Channel boundary
    }
}
```

#### 3. State Invalidation pada `StateFlow`
`StateFlow` menggunakan kesetaraan struktural (`equals` / `==`) untuk memeriksa apakah nilai baru berbeda dari nilai sebelumnya sebelum memicu emisi ke kolektor downstream. Jika Anda memutasi properti dari sebuah objek tanpa mengubah referensi atau tanpa menghasilkan instance *copy* baru, `StateFlow` **tidak akan memancarkan pembaruan tersebut**.

```kotlin
data class SystemStatus(var health: String)

val statusFlow = MutableStateFlow(SystemStatus("HEALTHY"))

// BAD PRACTICE:
statusFlow.value.health = "DEGRADED" // DOWNSTREAM TIDAK AKAN TERNODIFIKASI!

// SOLUSI BENAR:
statusFlow.update { it.copy(health = "DEGRADED") } // Menghasilkan referensi instance baru
```

---

### SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

#### Anti-Pattern 1: Menggunakan `flowOn` di Bawah `collect`
* *Penyebab*: Kesalahpahaman bahwa `flowOn` mengontrol thread konsumen.
* *Dampak*: Tidak berdampak apa-apa pada konsumen, atau memicu kebingungan struktural.
* *Perbaikan*: `flowOn` hanya memengaruhi aliran *upstream*. downstream selalu dieksekusi pada `CoroutineContext` di mana `collect` dipanggil.

```kotlin
// SALAH
myFlow.map { ... }.flowOn(Dispatchers.IO).collect { /* Berharap ini jalan di IO */ }

// BENAR
withContext(Dispatchers.IO) {
    myFlow.map { ... }.collect { /* Benar-benar jalan di IO */ }
}
```

#### Anti-Pattern 2: Kebocoran Hot Stream Tak Terhingga (*Infinite Hot Stream Leaks*)
* *Penyebab*: Melakukan observasi terhadap `SharedFlow` pada cakupan Global (`GlobalScope`) tanpa pembatalan eksplisit.
* *Dampak*: Memori bocor (*Memory Leak*) dan konsumsi CPU terus berlangsung di latar belakang.
* *Perbaikan*: Pasang lifecycle stream pada scope terkontrol, atau gunakan operator `takeWhile` / pembatalan Job terstruktur.

#### Anti-Pattern 3: Penggunaan `SharedFlow` Sebagai Event Satu Kali (*One-Time Event Bus*)
* *Penyebab*: Menggunakan `SharedFlow` untuk navigasi UI atau notifikasi alert sekali pakai.
* *Dampak*: Jika subscriber belum aktif saat data dipancarkan, event tersebut hilang selamanya (kecuali `replay >= 1`, yang justru menimbulkan masalah event diproses ganda saat konfigurasi berubah).
* *Perbaikan*: Gunakan `Channel` yang dikonsumsi melalui `receiveAsFlow()` untuk event satu kali (*single-observer pattern*).

---

### SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip Enkapsulasi Mutabilitas (Backing Property Pattern)**: Jangan pernah mengekspos `MutableStateFlow` atau `MutableSharedFlow` secara publik dari layer Service atau Repository. Buka hanya antarmuka read-only:
   ```kotlin
   class AccountBalanceService {
       private val _balance = MutableStateFlow(BigDecimal.ZERO)
       val balance: StateFlow<BigDecimal> = _balance.asStateFlow() // Enkapsulasi aman
   }
   ```

2. **Memaksimalkan Penggunaan Operator Standar**: Jangan membuat logika transformasi data manual menggunakan mutable collection di dalam `collect`. Manfaatkan operator fungsional (`map`, `filter`, `flatMapMerge`, `zip`, `combine`).

3. **Gunakan `transform` untuk Emisi Kompleks**: Jika sebuah transformasi membutuhkan emisi dinamis (0, 1, atau lebih dari 1 item per item masuk), hindari operator nested yang kaku; gunakan operator primitif fleksibel `transform`:
   ```kotlin
   fun Flow<Int>.expandMultiples(): Flow<Int> = transform { value ->
       emit(value)
       emit(value * 2)
   }
   ```

4. **Kepatuhan Terhadap Cancellation**: Pastikan loop komputasi intensif di dalam blok pembangun flow memanggil `ensureActive()` atau `yield()` secara berkala untuk menghormati sinyal pembatalan upstream.

---

### SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1. **Menghindari Redundant Dispatcher Switching**:
   Jangan menumpuk pemanggilan `flowOn` yang tidak perlu. Setiap peralihan konteks (`Dispatchers.Default` -> `Dispatchers.IO`) membutuhkan batas channel dan context switch di level thread kernel OS, yang membawa latensi beberapa mikrodetik.
   
2. **Buffer Capacity Sizing**:
   Gunakan konstanta bawaan `kotlinx.coroutines.channels.Channel.BUFFERED` (default: 64 slot) daripada mengalokasikan angka acak raksasa seperti `buffer(100000)`. Alokasi memori berlebih merusak cache locality CPU dan membebani Garbage Collector.

3. **Zero-Allocation Operators via Inlining**:
   Perhatikan bahwa operator terminal dasar beroperasi secara langsung pada thread pemanggil. Menjaga pipeline tetap linear tanpa buffer perantara memungkinkan compiler mengoptimalkan eksekusi hingga mendekati kecepatan raw for-loop konvensional.

---

### SEKSI 16 — KEAMANAN & HARDENING

1. **Backpressure sebagai Pertahanan Denial of Service (DoS)**:
   Pada endpoint streaming yang menerima data eksternal (contoh: server gRPC streaming atau REST SSE), gunakan selalu pembatasan laju (*rate limiting*) menggunakan operator `debounce` atau `sample` untuk mencegah penyerang mengeksploitasi konsumsi thread server:
   ```kotlin
   fun secureApiPayloadStream(): Flow<Payload> = rawNetworkFlow
       .debounce(250.milliseconds) // Redam flooding serangan payload cepat
       .take(1000)                  // Batas kuota absolut per sesi streaming
   ```

2. **Sanitasi Data di Hulu (Fail-Fast Validation)**:
   Pastikan data eksternal diverifikasi sebelum melintasi batasan modul. Selipkan operator validasi langsung setelah titik penerimaan:
   ```kotlin
   flow.map { payload ->
       require(payload.isValid()) { "Payload terdeteksi korup atau terindikasi injeksi!" }
       payload
   }
   ```

3. **Isolasi Aliran Data Multi-Tenant**:
   Ketika membagikan data broadcast menggunakan `SharedFlow` pada lingkungan multi-tenant, pastikan pengelompokan data diisolasi secara kriptografis atau via filter context sebelum diteruskan ke subscriber downstream guna mencegah kebocoran data antar pengguna (*cross-tenant data leak*).

---

### SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Pipeline asynchronous seringkali sulit dilacak jika hanya bergantung pada stack-trace konvensional. Kotlin menyediakan probe siklus hidup terpadu:

```kotlin
fun <T> Flow<T>.audit(streamTag: String): Flow<T> {
    return this
        .onStart { println("[$streamTag] STREAM DIBUKA pada thread: ${Thread.currentThread().name}") }
        .onEach { item -> println("[$streamTag] EMIT ITEM: $item") }
        .catch { ex -> 
            println("[$streamTag] EXCEPTION TERDETEKSI: ${ex.javaClass.simpleName} - ${ex.message}")
            throw ex // Lempar kembali setelah audit
        }
        .onCompletion { cause ->
            if (cause != null) {
                println("[$streamTag] TERMINASI ERROR: $cause")
            } else {
                println("[$streamTag] TERMINASI NORMAL")
            }
        }
}
```

#### Diagnostic Flag Debug Coroutine
Aktifkan opsi JVM berikut saat fase pengembangan untuk melacak asal muasal coroutine yang membuat Flow:
```bash
-Dkotlinx.coroutines.debug=on
```
Dengan mengaktifkan flag ini, runtime Coroutine akan merekonstruksi jejak alur asynchronous (*enhanced stack trace*), memungkinkan identifikasi akurat titik pembekuan atau penangguhan (*suspended stack trace*) saat terjadi kebuntuan (*deadlock*) pada flow collector.

---

### SEKSI 18 — RINGKASAN & CHEAT SHEET

```
OPERATOR MATRIX CHEAT SHEET:

+--------------------+---------------------------------------------------------------+
| KATEGORI           | OPERATOR & FUNGSI                                             |
+--------------------+---------------------------------------------------------------+
| Pembangun          | • flow { emit(...) }         : Cold flow dasar                |
| (Builders)         | • flowOf(v1, v2)             : Emisi nilai statis             |
|                    | • iterable.asFlow()          : Konversi koleksi               |
|                    | • channelFlow { send(...) }  : Konkurensi multi-coroutine     |
+--------------------+---------------------------------------------------------------+
| Pengendali         | • buffer(n)                  : Penampung buffer berbatas      |
| Backpressure       | • conflate()                 : Ambil item paling mutakhir     |
|                    | • collectLatest { ... }      : Batalkan eksekusi lama jika ada|
|                    |                                data baru yang masuk            |
+--------------------+---------------------------------------------------------------+
| Modifikasi         | • flowOn(Dispatchers)        : Ubah konteks eksekusi upstream  |
| Konteks            |                                                               |
+--------------------+---------------------------------------------------------------+
| Manajemen          | • catch { cause -> ... }     : Isolasi error hulu             |
| Error              | • retry(retries) { ... }     : Coba ulang pipeline            |
|                    | • retryWhen { cause, iter }  : Kondisi logika coba ulang      |
+--------------------+---------------------------------------------------------------+
| Kombinasi          | • zip(other)                 : Pasangkan item secara 1:1      |
| Stream             | • combine(other)             : Re-emit saat salah satu berubah|
|                    | • flatMapLatest { ... }      : Switch ke flow baru & batalkan |
+--------------------+---------------------------------------------------------------+
| Terminal           | • collect()                  : Aktifkan pemrosesan stream     |
| Operations         | • first() / single()         : Ambil data individual          |
|                    | • toList()                   : Materialisasi ke heap memory   |
+--------------------+---------------------------------------------------------------+
```

---

### SEKSI 19 — KUIS EVALUASI PEMAHAMAN

#### Soal Basic (1 - 5)
1. **Mengapa pemanggilan fungsi builder `flow { ... }` tidak memblokir thread pemanggil saat dieksekusi?**
   * *Jawaban:* Karena `Flow` bersifat dingin (*cold*). Builder hanya menginstansiasi objek anonim yang mengimplementasikan antarmuka `Flow`. Tidak ada kode di dalam blok pembangun yang dijalankan sebelum fungsi terminal seperti `collect` dipanggil.
2. **Apa yang mendasari aturan Context Preservation pada Kotlin Flow?**
   * *Jawaban:* Aturan ini menjamin bahwa konteks downstream (pemanggil `collect`) tidak dirusak atau dialihkan secara sembarangan oleh hulu (*upstream*), menjaga keselamatan eksekusi thread-safety, modularitas, dan kepatuhan terhadap prinsip Structured Concurrency.
3. **Bagaimana mekanisme Backpressure diimplementasikan pada Kotlin Flow tanpa menggunakan protokol kredit request(n)?**
   * *Jawaban:* Backpressure diatur langsung melalui primitif penangguhan (*suspension*) coroutine. Karena `emit()` adalah `suspend fun`, produsen ditangguhkan secara otomatis ketika buffer penuh atau konsumen belum selesai mengeksekusi lambda `collect`.
4. **Apa perbedaan mendasar antara `StateFlow` dan `SharedFlow`?**
   * *Jawaban:* `StateFlow` adalah spesialisasi dari `SharedFlow` yang selalu menyimpan satu nilai state terkini (`replay = 1`), wajib memiliki nilai inisial, dan memvalidasi kesetaraan nilai (`equals`) sebelum memancarkan perubahan. `SharedFlow` dapat memiliki replay berukuran berapa saja (termasuk 0) dan tidak memerlukan initial value.
5. **Kapan operator `onCompletion` dieksekusi dengan parameter `cause != null`?**
   * *Jawaban:* Parameter `cause` tidak bernilai `null` apabila stream berhenti karena mengalami kegagalan tak tertangani (*unhandled exception*) atau jika cakupan coroutine (*CoroutineScope*) yang melingkupinya dibatalkan secara eksternal (*cancellation*).

#### Soal Intermediate (6 - 10)
6. **Apa yang akan terjadi jika Anda memanggil `withContext(Dispatchers.Default)` di dalam blok builder `flow { emit(...) }`?**
   * *Jawaban:* Kode akan melempar `IllegalStateException: Flow invariant is violated`. Ini terjadi karena pelindung internal runtime (`SafeCollector`) memvalidasi bahwa emisi dilakukan pada konteks coroutine yang sama dengan kolektor downstream.
7. **Bagaimana cara kerja operator `conflate()` secara internal saat menghadapi konsumen lambat?**
   * *Jawaban:* `conflate()` menyisipkan buffer berkapasitas 1 dengan kebijakan `BufferOverflow.DROP_OLDEST`. Jika konsumen sedang sibuk, emisi baru akan menimpa nilai yang ada di buffer, sehingga konsumen selalu mendapatkan nilai mutakhir dan mengabaikan nilai perantara yang tertinggal.
8. **Jelaskan perbedaan mendasar penggunaan antara `flowOn()` dan `channelFlow()`!**
   * *Jawaban:* `flowOn()` digunakan untuk mengalihkan konteks eksekusi stream sekuensial yang sudah ada di upstream. `channelFlow()` adalah builder yang memadukan coroutine terpisah di dalamnya melalui primitif Channel, memungkinkan pemanggilan emisi konkuren lintas thread atau lintas launch secara aman.
9. **Mengapa operator `catch` tidak mampu menangkap exception yang terjadi di dalam blok pemanggilan terminal `collect { ... }`?**
   * *Jawaban:* Karena operator `catch` mematuhi prinsip *Exception Transparency*: hanya menangkap error yang berasal dari hulu (*upstream*). Blok `collect` adalah terminal downstream. Untuk menangani error di dalam `collect`, digunakan blok `try-catch` konvensional di sekitar pemanggilan tersebut.
10. **Apa implikasi penggunaan parameter `replay = 0` pada `MutableSharedFlow` terhadap subscriber baru yang lambat mendaftar?**
    * *Jawaban:* Subscriber baru tidak akan menerima data apa pun yang dipancarkan sebelum titik pendaftarannya selesai; data masa lalu langsung hangus dan subscriber hanya menerima peristiwa baru yang dipancarkan setelah koneksi terbentuk.

---

### SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

#### Judul Proyek: Real-Time IoT Telemetry Anomaly Detector

#### Spesifikasi Kebutuhan Sistem:
Bangun sebuah aplikasi CLI berbasis Kotlin murni yang bertindak sebagai mesin deteksi anomali pada sensor turbin industri:
1. **Komponen Sensor Producer**:
   * Buat fungsi `generateTurbineMetrics(): Flow<TurbineMetric>` yang memancarkan data setiap 20ms: `TurbineMetric(rpm: Int, pressurePsi: Double, tempCelsius: Double)`.
   * Simulasikan sensor berjalan pada `Dispatchers.IO`.
2. **Mitigasi Tekanan Data (Backpressure Management)**:
   * Konsumen database hanya mampu memproses validasi dengan durasi 80ms per pembacaan.
   * Sisipkan operator buffer adaptif dengan kebijakan pembuangan data usang agar memori sistem tidak melebihi alokasi.
3. **Deteksi Anomali Kompleks**:
   * Buat extension operator `detectAnomalies()` yang memantau rata-rata bergerak (*moving average*) dari 3 metrik terakhir.
   * Pemicu bahaya aktif jika: RPM > 5000 DAN Tekanan > 90 PSI secara simultan.
4. **Graceful Failover System**:
   * Simulasikan *Random Hardware Crash* setiap 50 paket data.
   * Gunakan operator `retryWhen` dengan skema *Exponential Backoff* (coba ulang: 100ms, 200ms, 400ms, maksimal 3x percobaan) sebelum akhirnya mengarahkan aliran data ke `fallbackTelemetryStream()`.
5. **Observabilitas**:
   * Pantau jumlah metrik yang berhasil diproses, jumlah data yang dibuang akibat buffer penuh, dan total anomali yang teridentifikasi menggunakan logging terstruktur.

#### Syarat Penyelesaian (Acceptance Criteria):
* Program dapat dikompilasi tanpa *warning* dan dijalankan secara mandiri via fungsi `main()`.
* Tidak ada satupun *blocking call* seperti `Thread.sleep()` di dalam codebase; seluruh simulasi wajib menggunakan `delay()`.
* Aturan *Context Preservation* dan *Cancellation Transparency* dipatuhi secara absolut.
* Gunakan penanganan structured concurrency yang rapi (`coroutineScope`, `cancelAndJoin`, tanpa `GlobalScope`).