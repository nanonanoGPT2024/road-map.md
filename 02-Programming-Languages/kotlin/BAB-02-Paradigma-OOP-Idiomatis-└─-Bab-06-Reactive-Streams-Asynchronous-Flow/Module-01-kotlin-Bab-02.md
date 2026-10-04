# KURIKULUM PEMROGRAMAN KOTLIN: TINGKAT LANJUT
## Kategori: 02-Programming-Languages
### Jalur: Paradigma OOP Idiomatis & Pemrograman Asinkron
---

# BAB 06: Reactive Streams & Asynchronous Flow

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Kode Modul** | `KOT-ADV-02-06` |
| **Nama Modul** | Paradigma OOP Idiomatis └─ Bab 06: Reactive Streams & Asynchronous Flow |
| **Kategori** | `02-Programming-Languages` |
| **Tingkat Kesulitan** | Lanjutan / *Advanced* |
| **Prasyarat Pengetahuan** | Kotlin OOP Idiomatis, Coroutines Core (`Job`, `CoroutineScope`, `Dispatcher`), Suspending Functions, Basic Concurrency |
| **Estimasi Waktu Belajar** | 6–8 Jam Intensif |
| **Bahasa & Perkakas** | Kotlin 1.9+, Kotlinx Coroutines Core 1.7+, JDK 17/21, Gradle (Kotlin DSL) |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik memiliki kapabilitas untuk:

1. **Menganalisis Komparatif:** Membedakan model reaktivitas berbasis *Reactive Streams Specification* (RxJava/Reactor) dengan *Suspending Asynchronous Flow* berbasis coroutine native.
2. **Menguasai Mekanisme Internal:** Membedah bagaimana `SafeCollector`, `Continuation-Passing Style (CPS)`, dan invarian *Context Preservation* bekerja di bawah kap mesin JVM.
3. **Mengimplementasikan Arsitektur Stream:** Membangun *Cold Streams* (`Flow`) dan *Hot Streams* (`SharedFlow`, `StateFlow`) yang aman dari *memory leak* dan *coroutine starvation*.
4. **Mengatur Strategi Backpressure:** Mengaplikasikan operator `buffer()`, `conflate()`, dan `collectLatest()` untuk menangani perbedaan kecepatan produsen dan konsumen data.
5. **Mitigasi Anti-Pattern & Exception Transparency:** Menghindari pelanggaran hukum invarian Flow, memastikan isolasi konteks eksekusi (`flowOn`), serta menangani kegagalan sistematis menggunakan `catch` dan `retry`.
6. **Membangun Sistem Reaktif Enterprise:** Merancang pipeline pemrosesan data asinkron berkecepatan tinggi dengan integrasi Reactive Streams interop API.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam dunia pemrograman asinkron berbasis Object-Oriented dan Fungsional:

1. **Koleksi Statis vs Asynchronous Stream:**
   * `List<T>`: Seluruh elemen dievaluasi secara serentak di memori (*synchronous & in-memory*).
   * `Sequence<T>`: Elemen dievaluasi secara bertahap saat diminta (*lazy pull*), namun **memblokir *thread*** jika terjadi operasi I/O.
   * `Flow<T>`: Elemen dievaluasi secara bertahap (*lazy pull/push*) dan **tidak pernah memblokir *thread*** karena beroperasi di atas mekanisme penangguhan (*suspension mechanism*).

2. **Dua Kutub Reaktivitas: RxJava vs Kotlin Flow:**
   * Di dunia ReactiveX (RxJava/Reactor), *backpressure* dicapai melalui protokol negosiasi kompleks (`Subscription.request(n)`). Ini menghasilkan API yang berat (*hundreds of operators*) dan *call-stack trace* yang sulit dilacak.
   * Di Kotlin Flow, konsep *backpressure* terselesaikan secara intrinsik melalui **fungsi penangguhan (*suspending function*)**. Ketika konsumen lambat, pemanggilan `emit()` secara otomatis menangguhkan *coroutine* milik produsen tanpa memblokir thread sistem operasi. Tidak diperlukan antarmuka `request(n)` terpisah.

3. **Mental Model: Cold vs Hot Stream:**
   * **Cold Stream (`Flow`):** Seperti *CD Player*. Aliran data tidak ada hingga ada pendengar yang menekan tombol *play* (`collect()`). Setiap pendengar mendapatkan aliran data dari awal secara independen.
   * **Hot Stream (`SharedFlow` / `StateFlow`):** Seperti *Siaran Radio*. Aliran data terus berjalan terlepas dari apakah ada pendengar atau tidak. Pendengar baru hanya menerima data yang disiarkan sejak mereka mulai mendengarkan (atau sesuai kapasitas *replay cache*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme penangguhan backpressure pada Kotlin Flow:

```
[ Producer Coroutine ]                [ Flow Buffer Boundary ]              [ Consumer Coroutine ]
        │                                        │                                    │
  emit(Data 1) ──── (Direct Call / Channel) ────>│──────── (Suspended Pull) ─────────>│ collect { ... }
        │                                        │                                    │ Processing (100ms)
  emit(Data 2) ───┐                              │                                    │
        │         │                              │                                    │
        │    [Buffer Full]                       │                                    │
        │         │                              │                                    │
        ▼         │                              │                                    │
   (SUSPENDED) ───┘                              │                                    │
   (Thread Lepas)                                │                                    │
        │                                        │                                    │
        │                                        │<────── Selesai Proses Data 1 ──────│
        │                                        │                                    │
        ├────── Resume Coroutine ───────────────>│──────── Kirim Data 2 ─────────────>│ collect { ... }
        │                                        │                                    │ Processing (100ms)
        ▼                                        │                                    │
  emit(Data 3)                                   │                                    │
```

Arsitektur Invarian Context Preservation:

```
+-----------------------------------------------------------------------------------+
| CoroutineScope (Dispatcher.Main)                                                  |
|                                                                                   |
|  myFlow                                                                           |
|    .flowOn(Dispatchers.IO) ───┐                                                   |
|    .collect { item ->         │                                                   |
|       updateUI(item)          │                                                   |
|    }                          │                                                   |
+-------------------------------┼---------------------------------------------------+
                                │
                                ▼
+-----------------------------------------------------------------------------------+
| Upstream Execution (Dispatcher.IO)                                                |
|                                                                                   |
|  flow {                                                                           |
|     // Aman: Berjalan di context Dispatchers.IO                                    |
|     val data = readFromDisk()                                                     |
|     emit(data) // SafeCollector memvalidasi context & menyalurkan ke downstream   |
|  }                                                                                |
+-----------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Interface Dasar Kotlin Flow
Di tingkat terendah, Kotlin Flow didefinisikan secara minimalis oleh dua interface:

```kotlin
public interface Flow<out T> {
    public suspend fun collect(collector: FlowCollector<T>)
}

public fun interface FlowCollector<in T> {
    public suspend fun emit(value: T)
}
```

* `Flow` bersifat kontravarian/kovarian secara idiomatis (`out T`).
* Satu-satunya fungsi adalah `collect`, yang membutuhkan implementasi `FlowCollector`.
* `FlowCollector` adalah *Functional Interface* dengan metode penangguhan tunggal `emit`.

### 2. Mekanisme SafeCollector dan Context Preservation Invariant
Kotlin menegakkan prinsip **Context Preservation**: *Nilai coroutine context dari pemanggil collector TIDAK BOLEH dibocorkan atau diubah secara sepihak oleh produsen di dalam blok builder `flow { ... }`.*

Jika Anda mencoba menulis:
```kotlin
// ERROR RUNTIME KOTLIN!
flow {
    kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
        emit(42) // Akan melempar IllegalStateException
    }
}
```
Mekanisme internal `SafeCollector` memverifikasi `currentCoroutineContext()` terhadap `collectContext`. Jika `SafeCollector` mendeteksi bahwa *Dispatcher* atau *Job* saat `emit()` dipanggil berbeda dengan context saat `collect()` dipanggil (tanpa melalui operator `flowOn`), runtime melempar `IllegalStateException`:

> *"Flow invariant is violated: Emission from another coroutine is detected."*

### 3. Transformasi Continuation-Passing Style (CPS)
Ketika `emit()` dipanggil, Kotlin Compiler mentransformasikannya menjadi panggilan status mesin CPS:
```
emit(value: T, continuation: Continuation<Unit>): Any?
```
Jika downstream sedang sibuk (misalnya terblokir oleh operasi I/O atau perhitungan berat pada consumer), fungsi `emit` mengembalikan konstanta `COROUTINE_SUSPENDED`. Execution thread hulu (*upstream*) dilepaskan kembali ke pool, dan *continuation* disimpan hingga downstream memanggil *resume*.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Cold Streams (`Flow`)
Cold stream bersifat pasif. Blok kode di dalam `flow { ... }` tidak dieksekusi sampai fungsi terminal seperti `collect()`, `first()`, atau `toList()` dipanggil. Setiap pemanggilan terminal operator memicu eksekusi independen baru dari hulu ke hilir.

### 2. Hot Streams: StateFlow vs SharedFlow

| Karakteristik | `StateFlow<T>` | `SharedFlow<T>` |
| :--- | :--- | :--- |
| **Kebutuhan Inisial** | Wajib memiliki *initial value*. | Tidak wajib memiliki *initial value*. |
| **Penyimpanan State** | Menyimpan tepat 1 nilai terakhir (`.value`). | Memiliki kapasitas buffer & replay yang dapat dikonfigurasi (`replayCache`). |
| **Deduplikasi Nilai** | Mengabaikan nilai berulang via `Any.equals()`. | Memancarkan semua event tanpa deduplikasi (konfigurabel). |
| **Tujuan Arsitektur** | Representasi status UI/Domain (*State holder*). | Penyaluran event transien (*Event bus*, notifikasi, klik). |

### 3. Operator Pengendali Aliran (Flow Flattening Operators)
Ketika satu emisi data memicu aliran data sekunder (`Flow<Flow<T>>`), diperlukan strategi *flattening*:

* `flatMapConcat`: Menunggu flow sekunder selesai sepenuhnya sebelum memproses emisi berikutnya dari flow utama (Sekuensial ketat).
* `flatMapMerge`: Menjalankan beberapa flow sekunder secara konkuren hingga batas `concurrency` tertentu.
* `flatMapLatest`: Membatalkan flow sekunder yang sedang berjalan jika flow utama memancarkan nilai baru (sangat umum untuk sistem pencarian/search query).

### 4. Transparansi Eksepsi (Exception Transparency)
Kotlin Flow menjamin bahwa kegagalan hulu (*upstream*) tidak boleh ditelan secara diam-diam. Operator `catch` dirancang hanya menangkap *exception* yang terjadi di **hulu (upstream)** operator tersebut, bukan di **hilir (downstream)**:

```kotlin
flow { emit(doRiskyWork()) } // Upstream
    .catch { e -> emit(FallbackValue) } // Hanya menangkap error dari doRiskyWork()
    .collect { process(it) } // Downstream: Jika throw error di sini, TIDAK ditangkap catch di atas
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi komprehensif yang mendemonstrasikan Cold Flow, Transisi Konteks (`flowOn`), Operator Transformasi, Exception Transparency, dan Konsumsi Data.

```kotlin
package com.architect.reactive.fundamental

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

// 1. Model Domain
data class SensorReading(
    val sensorId: String,
    val valueCelsius: Double,
    val timestampMs: Long
)

// 2. Data Source Simulator (Cold Flow)
class SensorRepository {
    fun fetchRawSensorData(): Flow<Double> = flow {
        val rawValues = listOf(22.5, 23.0, 24.8, 999.0, 25.1) // 999.0 melambangkan error hardware
        for (value in rawValues) {
            delay(100) // Simulasi latency transmisi data
            if (value == 999.0) {
                throw IllegalStateException("Hardware Malfunction: Pembacaan sensor korup!")
            }
            emit(value)
        }
    }.flowOn(Dispatchers.IO) // Menjamin upstream berjalan di Dispatcher IO
}

// 3. Domain Logic Service
class SensorService(private val repository: SensorRepository) {
    fun getSanitizedReadings(): Flow<SensorReading> {
        return repository.fetchRawSensorData()
            .map { raw ->
                // Mengubah raw value menjadi entity model
                SensorReading(
                    sensorId = "TEMP-01",
                    valueCelsius = raw,
                    timestampMs = System.currentTimeMillis()
                )
            }
            .filter { reading ->
                // Menolak anomali temperatur ekstrem
                reading.valueCelsius in -40.0..85.0
            }
            .catch { cause ->
                // Menangani kegagalan upstream secara anggun
                println("[WARN] Deteksi error: ${cause.message}. Mengirim fallback data...")
                emit(SensorReading("TEMP-01-FALLBACK", 0.0, System.currentTimeMillis()))
            }
            .onCompletion { cause ->
                if (cause == null) println("[INFO] Aliran data sensor ditutup normal.")
                else println("[WARN] Aliran data sensor dihentikan karena kegagalan.")
            }
    }
}

// 4. Execution Driver
fun main() = runBlocking {
    val repository = SensorRepository()
    val service = SensorService(repository)

    println("[MAIN] Memulai listening pada sensor stream...")

    // Konsumsi downstream di context pemanggil (main thread)
    service.getSanitizedReadings()
        .collect { reading ->
            println("[CONSUMER] Menerima: $reading di thread: ${Thread.currentThread().name}")
        }

    println("[MAIN] Selesai.")
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi mekanis dari implementasi Seksi 07:

1. **`fun fetchRawSensorData(): Flow<Double> = flow { ... }`**: Menginisialisasi *Cold Flow*. Blok ini ditangguhkan dan belum dieksekusi sampai metode `collect` dipanggil downstream.
2. **`emit(value)`**: Memanggil antarmuka `FlowCollector.emit()`. Jika thread konsumen lambat, baris ini menangguhkan eksekusi loop produsen tanpa memblokir thread `Dispatchers.IO`.
3. **`.flowOn(Dispatchers.IO)`**: Mengubah konteks eksekusi **seluruh operator hulu (upstream)** sebelum operator ini dipanggil. Memastikan loop pembacaan data berjalan di thread pool background.
4. **`.map { raw -> SensorReading(...) }`**: Operator transformasi fungsional. Bersifat inline dan mempertahankan efisiensi alokasi memori.
5. **`.filter { reading -> ... }`**: Mengevaluasi predikat. Jika `false`, pipeline internal memotong evaluasi dan langsung menarik siklus continuation berikutnya.
6. **`.catch { cause -> emit(...) }`**: Mengimplementasikan prinsip *Exception Transparency*. Blok ini mengintersepsi `IllegalStateException` yang dilempar oleh loop produsen dan memancarkan nilai mitigasi (fallback) tanpa merusak kesinambungan program.
7. **`.onCompletion { cause -> ... }`**: Titik observabilitas siklus hidup aliran data, setara dengan blok `finally`. Variabel `cause` bernilai `null` jika stream selesai normal, atau berisi referensi `Throwable` jika terjadi terminasi abnormal tak tertangani.
8. **`.collect { reading -> ... }`**: Operator terminal suspensi. Mengeksekusi seluruh rantai pemrosesan. Dijalankan di thread konteks lokal `runBlocking` (Main thread), membuktikan bahwa `flowOn` sukses mengisolasi thread hulu dari hilir.

---

## SEKSI 09 — STUDI KASUS NYATA (High-Throughput Order Book & Ticker Aggregator)

### Permasalahan Arsitektural
Sebuah sistem bursa perdagangan kripto menerima ribuan update data transaksi (*Order Book Events*) per detik via protokol WebSocket dari bursa eksternal (*producer* cepat). Konsumen aplikasi adalah *Trading Engine* berbasis basis data dan *Realtime UI* (*consumer* lambat).

### Kebutuhan & Kendala
1. Produsen data menghasilkan burst 5.000 event/detik.
2. Konsumen membutuhkan waktu 10ms per transaksi untuk validasi database (maksimal 100 event/detik per worker).
3. Konsumen UI hanya membutuhkan status harga terakhir tanpa perlu memproses setiap tick transaksi intermediate (*conflation*).
4. Data stream dari WebSocket eksternal berbasis antarmuka Java Reactive Streams (`org.reactivestreams.Publisher`).
5. Tidak boleh terjadi `OutOfMemoryError` (OOM) akibat buffer unbounded.

### Solusi Arsitektur
* Menerjemahkan `Publisher<T>` reaktif Java ke dalam Kotlin `Flow<T>` menggunakan pustaka `kotlinx-coroutines-reactive`.
* Mengisolasi jalur pemrosesan order (Audit Ledger) menggunakan `buffer(capacity, onBufferOverflow = BufferOverflow.SUSPEND)`.
* Mengisolasi jalur update visualisasi harga (UI Ticker) menggunakan operator `conflate()`.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```kotlin
package com.architect.reactive.production

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import java.math.BigDecimal
import java.time.Instant

// 1. Kontrak Data
enum class OrderSide { BUY, SELL }

data class MarketTick(
    val symbol: String,
    val price: BigDecimal,
    val volume: Double,
    val timestamp: Instant
)

// 2. Simulasi External High-Frequency Producer
class HighFrequencyTickerSource {
    fun streamTicks(): Flow<MarketTick> = flow {
        var currentPrice = BigDecimal("50000.00")
        var counter = 0L
        while (true) {
            counter++
            val delta = BigDecimal((Math.random() - 0.49).toString()).setScale(2, java.math.RoundingMode.HALF_UP)
            currentPrice = currentPrice.add(delta)
            
            emit(
                MarketTick(
                    symbol = "BTC/USDT",
                    price = currentPrice,
                    volume = Math.random() * 2.0,
                    timestamp = Instant.now()
                )
            )
            // Simulasi emisi data sangat cepat (1000 event per detik)
            delay(1)
        }
    }.flowOn(Dispatchers.IO)
}

// 3. Trading Engine Orchestrator
class TradingEngineOrchestrator(
    private val tickerSource: HighFrequencyTickerSource,
    private val engineScope: CoroutineScope
) {
    // Hot State Flow untuk menampung data pasar terkini (UI consumption)
    private val _latestPriceState = MutableStateFlow<MarketTick?>(null)
    val latestPriceState: StateFlow<MarketTick?> = _latestPriceState.asStateFlow()

    // Shared Flow untuk event critical ledger (Storage consumption)
    private val _criticalAuditEvents = MutableSharedFlow<MarketTick>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val criticalAuditEvents: SharedFlow<MarketTick> = _criticalAuditEvents.asSharedFlow()

    fun startPipeline() {
        val baseStream = tickerSource.streamTicks()
            .shareIn(
                scope = engineScope,
                started = SharingStarted.Eagerly,
                replay = 1
            )

        // Pipeline 1: UI Display Pipeline (Menghindari Lag dengan Conflate)
        engineScope.launch(Dispatchers.Default) {
            baseStream
                .conflate() // Jatuhkan data intermediate jika consumer belum selesai
                .collect { tick ->
                    _latestPriceState.value = tick
                    // Simulasi konsumsi render UI lambat
                    delay(50)
                }
        }

        // Pipeline 2: Ledger Audit Pipeline (Tidak boleh ada data yang hilang)
        engineScope.launch(Dispatchers.IO) {
            baseStream
                .buffer(
                    capacity = 256,
                    onBufferOverflow = BufferOverflow.SUSPEND // Terapkan Backpressure native
                )
                .collect { tick ->
                    persistToAuditLog(tick)
                }
        }
    }

    private suspend fun persistToAuditLog(tick: MarketTick) {
        // Simulasi penulisan IO database yang menelan waktu
        delay(5) 
    }
}

// 4. Driver Verifikasi Sistem
fun main(): Unit = runBlocking {
    val orchestratorScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val source = HighFrequencyTickerSource()
    val orchestrator = TradingEngineOrchestrator(source, orchestratorScope)

    println("[SYSTEM] Menyalakan Pipeline Trading Engine...")
    orchestrator.startPipeline()

    // Observer UI Consumer (Mengambil pembacaan state conflated)
    val uiWatcher = launch {
        orchestrator.latestPriceState
            .filterNotNull()
            .collect { tick ->
                println("[UI MONITOR] Ticker Terkini: ${tick.price} pada ${tick.timestamp} (Thread: ${Thread.currentThread().name})")
            }
    }

    // Biarkan sistem bekerja selama 500 milidetik untuk simulasi
    delay(500)

    println("[SYSTEM] Menghentikan Engine Pipeline...")
    orchestratorScope.cancel()
    uiWatcher.cancel()
    println("[SYSTEM] Berhasil dihentikan dengan aman.")
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Kriteria Evaluasi | Kotlin Coroutines `Flow` | RxJava 3 (`Flowable`) | Project Reactor (`Flux`) | Kotlin `Channel` |
| :--- | :--- | :--- | :--- | :--- |
| **Model Arsitektur** | Suspending Pull/Push | Reactive Streams Push-request(n) | Reactive Streams Push-request(n) | CSP Communication primitive |
| **Footprint Memori** | **Sangat Ringan** (Menggunakan Coroutine Continuation) | Berat (Banyak instansiasi objek operator wrapper) | Berat (Dioptimalkan untuk Spring Framework internal) | Sedang (Membutuhkan internal queue structures) |
| **Mekanisme Backpressure** | Ditangani otomatis oleh `suspend` keyword | Negosiasi numerik eksplisit via `request(n)` | Negosiasi numerik eksplisit via `request(n)` | Menghentikan pengirim via `send()` suspended |
| **Cold vs Hot Stream** | Desain dasar: Cold (`Flow`), Hot via subkelas | Membedakan `Observable`/`Flowable` vs `PublishSubject` | Membedakan `Flux` cold vs `ConnectableFlux` hot | **Hot Stream secara permanen** |
| **Kompatibilitas Multiplatform (KMP)** | **Ya** (Native di JS, iOS, Android, JVM, Linux) | Tidak (Hanya ekosistem JVM) | Tidak (Hanya ekosistem JVM) | **Ya** (Mendukung KMP penuh) |
| **Kurva Pembelajaran** | Landai (Sintaks sekuensial imperatif-fungsional) | Sangat Curam (Ratusan operator khusus) | Sangat Curam (Debugging call-stack buram) | Menengah (Memerlukan pemahaman concurrency CSP) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Context Invariance Violation:**
   Jangan pernah memanggil `emit()` dari dalam *coroutine builder* lokal atau pengubah dispatcher manual di dalam blok `flow { ... }`:
   ```kotlin
   flow {
       // FATAL CRASH: Melempar IllegalStateException saat runtime
       launch(Dispatchers.IO) {
           emit(1)
       }
   }
   ```
   *Solusi:* Gunakan operator `channelFlow { send(1) }` jika pemancaran data dari multiple coroutine konkuren memang mutlak diperlukan.

2. **Downstream Exception Leakage pada Operator `catch`:**
   Operator `.catch` hanya memitigasi kegagalan pada upstream.
   ```kotlin
   flowOf("data")
       .catch { log("Error upstream teratasi") }
       .collect { 
           throw RuntimeException("Crash di consumer downstream!") // TIDAK AKAN tertangkap!
       }
   ```

3. **Perilaku Default `SharedFlow` Tanpa Buffer:**
   Secara default, parameter `extraBufferCapacity` pada `MutableSharedFlow` adalah `0`. Jika ada subscriber lambat dan `BufferOverflow.SUSPEND` diterapkan, pemanggilan `emit()` akan langsung tertahan (*suspend*), yang berpotensi mematikan aliran pemrosesan ke seluruh subscriber lain (*head-of-line blocking*).

4. **Karakteristik Penelanan State pada `StateFlow`:**
   `StateFlow` mengabaikan nilai baru jika nilai tersebut bernilai sama menurut perbandingan structural equality (`equals()`). Jika Anda memancarkan mutasi objek yang sama secara referensial tanpa memproduksi instance baru (*immutable copy*), collector tidak akan pernah bereaksi.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Penggunaan `withContext` di Dalam `flow` Builder
```kotlin
// SALAH: Menyebabkan IllegalStateException
fun loadData(): Flow<Data> = flow {
    withContext(Dispatchers.IO) {
        val res = networkApi.call()
        emit(res)
    }
}

// BENAR: Menggunakan flowOn secara deklaratif
fun loadData(): Flow<Data> = flow {
    val res = networkApi.call()
    emit(res)
}.flowOn(Dispatchers.IO)
```

### Anti-Pattern 2: Menelan `CancellationException`
Dalam ekosistem Coroutines, pembatalan adalah mekanisme kooperatif berbasis pengecualian internal `CancellationException`.
```kotlin
// SALAH: Menghentikan mekanisme pembatalan scope
flow { ... }
    .catch { e ->
        println("Logging general error: $e") // Jika e adalah CancellationException, Flow menolak dibatalkan!
    }

// BENAR: Re-throw jika bertipe CancellationException
flow { ... }
    .catch { cause ->
        if (cause is CancellationException) throw cause
        emit(fallback)
    }
```

### Anti-Pattern 3: Penggunaan `GlobalScope` untuk Membuka Flow
```kotlin
// SALAH: Kebocoran memori (Memory Leak), tidak ada garbage collection otomatis
fun streamOrders() {
    GlobalScope.launch {
        repository.getOrderFlow().collect { ... }
    }
}

// BENAR: Menambatkan pada structured concurrency lifecycle
class OrderViewModel(private val repository: Repository, private val scope: CoroutineScope) {
    fun streamOrders() {
        scope.launch {
            repository.getOrderFlow().collect { ... }
        }
    }
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Prinsip Imutabilitas Publik (Encapsulation of Hot Flows):**
   Ekspos antarmuka *Read-Only* (`StateFlow` / `SharedFlow`) ke publik, dan sembunyikan instansi mutabel (`MutableStateFlow` / `MutableSharedFlow`) di dalam kelas internal.
   ```kotlin
   class AccountBalanceManager {
       private val _balance = MutableStateFlow(BigDecimal.ZERO)
       val balance: StateFlow<BigDecimal> = _balance.asStateFlow()
   }
   ```

2. **Gunakan Operator Konversi yang Tepat:**
   Gunakan `asStateFlow()` atau `asSharedFlow()` daripada melakukan *casting* tipe eksplisit `(it as StateFlow)`. Ini mencegah konsumen hilir memodifikasi nilai state melalui manipulasi tipe.

3. **Lifecycle-Aware Collection:**
   Di lingkungan UI (seperti Android atau Desktop Compose), jangan pernah mengumpulkan data flow tanpa proteksi siklus hidup. Pastikan koleksi dibatalkan ketika komponen UI beralih ke background menggunakan `repeatOnLifecycle` atau integrasi framework setara.

4. **Gunakan `channelFlow` Hanya Jika Benar-Benar Diperlukan:**
   `channelFlow` memiliki alokasi overhead lebih tinggi dibanding `flow` reguler karena mengalokasikan primitive antrean internal `Channel`. Gunakan `channelFlow` hanya bila proses emisi harus dipanggil dari beberapa coroutine independen secara bersamaan.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1. **Manajemen Buffer dan Pemilihan Kebijakan Drop:**
   Sesuaikan kapasitas buffer berdasarkan toleransi data sistem:
   * Data finansial transaksional: `BufferOverflow.SUSPEND` (Kehilangan nol data).
   * Data sensor IoT / UI Visual: `BufferOverflow.DROP_OLDEST` atau `conflate()` (Efisiensi penggunaan RAM maksimum).

2. **Menghindari Dispatcher Switching yang Tidak Perlu:**
   Hindari menumpuk pemanggilan `flowOn` berkali-kali. `flowOn` mengalokasikan channel internal untuk menjembatani coroutine context:
   ```kotlin
   // BURUK: Alokasi 2 channel bridge internal
   flow { emit(fetch()) }
       .flowOn(Dispatchers.IO)
       .map { transform(it) }
       .flowOn(Dispatchers.Default)

   // BAIK: Tentukan downstream dispatcher dari luar jika memungkinkan
   ```

3. **Inlining Execution Operator:**
   Gunakan operator dasar Kotlin seperti `map`, `filter`, dan `transform` karena operator ini dioptimalkan dengan fungsi *inlined suspending*, mengurangi jejak objek penampung (*object wrapper allocation*) pada memori generasi muda JVM (Young Generation Heap).

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Mitigasi Starvation Denial-of-Service:**
   Hindari loop konsumsi tak terbatas (*unbounded*) tanpa titik jeda kooperatif. Selalu sematkan pemanggilan `yield()` atau fungsi suspensi lainnya di dalam komputasi matematis berat di dalam pipeline Flow:
   ```kotlin
   flow {
       while (hasMoreData()) {
           currentCoroutineContext().ensureActive() // Mencegah thread starvation & mematuhi sinyal cancel
           emit(calculateNextDataBlock())
       }
   }
   ```

2. **Bounds Enforcement pada Koleksi Dinamis:**
   Ketika mengalirkan data ke operator terminal `toList()` atau `toSet()`, batasi ukuran stream menggunakan operator `take(MAX_LIMIT)`. Mengonsumsi Infinite Flow menggunakan `toList()` akan langsung memicu `java.lang.OutOfMemoryError: Java heap space`.

3. **Sensitivitas Data Logging:**
   Pastikan tidak mengekspos field rahasia (seperti Token otentikasi, Password, atau PII) dalam blok observasi debugging seperti `onEach { println(it) }`. Terapkan fungsi masking eksplisit.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Pola Logging Terstruktur
Observabilitas pipeline tanpa memodifikasi logika bisnis dapat dicapai secara modular menggunakan ekstensi khusus:

```kotlin
fun <T> Flow<T>.auditLog(pipelineName: String): Flow<T> {
    return this
        .onStart { println("[$pipelineName] Aliran data dimulai...") }
        .onEach { println("[$pipelineName] Emisi data: $it") }
        .onCompletion { cause ->
            if (cause != null) println("[$pipelineName] Terminasi abnormal: ${cause.message}")
            else println("[$pipelineName] Aliran data rampung.")
        }
}
```

### Teknik Debugging Eksekusi Paralel
Untuk membedah alur eksekusi internal Kotlin Flow di unit test, hindari penggunaan `Thread.sleep()`. Gunakan *Test Dispatcher* dari pustaka `kotlinx-coroutines-test`:

```kotlin
@Test
fun testPipelineFlow() = runTest {
    val items = mutableListOf<Int>()
    val flow = flowOf(1, 2, 3).onEach { delay(1000) }

    // Mempercepat virtual time tanpa menunda thread fisik
    launch { flow.toList(items) }
    
    advanceTimeBy(3000)
    assertEquals(listOf(1, 2, 3), items)
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Tabel Komparasi Operator Transformasi Data

| Operator | Karakteristik Utama | Kasus Penggunaan Ideal |
| :--- | :--- | :--- |
| `map` | 1-to-1 transformasi sinkron/suspending | Mengubah representasi model data (DTO -> Entity). |
| `transform` | Arbitrer: dapat memancarkan 0, 1, atau banyak data | Pemrosesan polimorfik atau filter-and-map sekaligus. |
| `filter` | Seleksi data berbasis predikat boolean | Validasi dan eliminasi data invalid. |
| `take(n)` | Mengambil $n$ elemen awal lalu membatalkan aliran | Menghindari infinite stream processing. |
| `debounce(t)` | Menahan emisi sampai ada jeda waktu $t$ | Fitur Search Query UI (mencegah spam request). |
| `conflate` | Melewati emisi intermediate saat consumer sibuk | Render visual data yang bergerak sangat cepat. |
| `flowOn` | Mengalihkan CoroutineContext upstream | Isolasi thread I/O dari Main/UI thread. |

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa yang mendasari perbedaan fundamental sifat Cold Stream (`Flow`) dibanding Hot Stream (`SharedFlow`)?**
   * A. Cold stream hanya berjalan pada background thread, Hot stream pada UI thread.
   * B. Cold stream tidak mengeksekusi komputasi sampai ada operator terminal yang dipanggil; Hot stream aktif secara mandiri.
   * C. Cold stream selalu menyimpan nilai sebelumnya di memori, Hot stream tidak memiliki memori.
   * D. Cold stream hanya dapat menampung tipe data primitif.

2. **Apa yang akan terjadi secara internal jika produsen memanggil `emit()` lebih cepat daripada kemampuan eksekusi fungsi `collect()` tanpa adanya konfigurasi buffer khusus?**
   * A. Terjadi `BufferOverflowException`.
   * B. Konsumen secara otomatis melempar data tertua.
   * C. Coroutine produsen ditangguhkan (*suspended*) sampai downstream siap menerima elemen baru.
   * D. JVM mengalokasikan thread baru secara otomatis untuk menampung emisi.

3. **Operator mana yang harus digunakan untuk memitigasi eksepsi yang dilempar oleh rantai pemrosesan upstream tanpa menghentikan runtime aplikasi?**
   * A. `onCompletion`
   * B. `catch`
   * C. `recover`
   * D. `flowOn`

4. **Kapan invarian Context Preservation dianggap dilanggar dalam Kotlin Flow?**
   * A. Saat memanggil operator `flowOn(Dispatchers.IO)`.
   * B. Saat memanggil `emit()` di dalam blok `withContext(...)` di dalam builder `flow { }`.
   * C. Saat mengonsumsi data flow di dalam scope `runBlocking`.
   * D. Saat nilai yang dipancarkan bernilai `null`.

5. **Manakah dari operator berikut yang bertindak sebagai Operator Terminal?**
   * A. `map`
   * B. `filter`
   * C. `collect`
   * D. `conflate`

---

### Soal Tingkat Menengah (Intermediate)

6. **Mengapa kode berikut memicu kegagalan kompilasi atau runtime invariant error?**
   ```kotlin
   fun test(): Flow<Int> = flow {
       kotlinx.coroutines.launch {
           emit(100)
       }
   }
   ```
   * A. Coroutine builder `launch` tidak diizinkan memiliki tipe balikan `Int`.
   * B. `emit` tidak boleh dipanggil dari konteks *child coroutine* yang berbeda di dalam pembangun `flow`.
   * C. `test()` harus ditandai dengan keyword `suspend`.
   * D. Tipe integer `100` tidak kompatibel dengan context channel.

7. **Pada skenario antarmuka pencarian teks dinamis (search autocomplete), operator flattening apa yang paling tepat digunakan untuk membatalkan proses query jaringan sebelumnya jika user mengetik karakter baru secara cepat?**
   * A. `flatMapConcat`
   * B. `flatMapMerge`
   * C. `flatMapLatest`
   * D. `flattenConcat`

8. **Apa perbedaan struktural utama antara `StateFlow` dan `SharedFlow`?**
   * A. `StateFlow` tidak dapat diobservasi lebih dari satu subscriber.
   * B. `StateFlow` selalu menyimpan nilai state terakhir, memerlukan inisialisasi awal, dan melakukan deduplikasi data berurutan melalui `equals`.
   * C. `SharedFlow` hanya dapat berjalan di atas `Dispatchers.Unconfined`.
   * D. `SharedFlow` tidak mendukung buffer kustom.

9. **Di mana penempatan operator `flowOn` yang benar untuk memindahkan eksekusi operasi `fetchDatabase()` ke background thread tanpa memengaruhi thread konsumen downstream?**
   ```kotlin
   // Skenario:
   flow { emit(fetchDatabase()) } // (1)
       .map { parse(it) }          // (2)
       .flowOn(Dispatchers.IO)     // (3)
       .collect { renderUI(it) }   // (4)
   ```
   * A. Operator `flowOn` pada posisi (3) mengubah eksekusi (1) dan (2) menjadi IO, sementara (4) tetap pada thread pemanggil.
   * B. Operator `flowOn` pada posisi (3) mengubah eksekusi (4) menjadi IO.
   * C. `flowOn` mengubah seluruh pipeline termasuk (4) menjadi IO.
   * D. Posisi `flowOn` tidak berpengaruh pada context manapun.

10. **Bagaimana cara mencegah `StateFlow` memicu pembaruan berulang jika data baru yang di-set memiliki kesamaan referensi struktural dengan data saat ini?**
    * A. Menambahkan pemanggilan `.distinctUntilChanged()` secara eksplisit pada downstream.
    * B. Mengatur `conflate()` sebelum `collect`.
    * C. Tidak perlu melakukan apapun, karena `StateFlow` secara bawaan mengabaikan emisi nilai identik berdasarkan operator pembanding `==`.
    * D. Menggunakan operator `buffer(0)`.

---

### Kunci Jawaban & Rationale Teknis

1. **B**: Cold Stream bersifat pasif dan mengevaluasi hulu secara independen tiap kali dikoleksi, sedangkan Hot Stream independen terhadap keberadaan collector.
2. **C**: Sifat bawaan penangguhan coroutine (*cooperative suspension*) mengunci produsen pada titik `emit()` tanpa memicu error atau konsumsi memori tak terbatas.
3. **B**: Operator `.catch` menangkap throwable hulu dan mengalirkan penanganan kembali ke dalam pipeline via pemancaran alternatif atau terminasi aman.
4. **B**: Pengecekan runtime `SafeCollector` mendeteksi perbedaan coroutine context antara pemancar dan pengumpul, yang melanggar hukum invarian context preservation.
5. **C**: `collect` adalah *suspending function* yang mengaktifkan eksekusi aliran data dan menampung hasilnya; operator lainnya adalah transformator perantara (*intermediate*).
6. **B**: `flow { ... }` builder memberlakukan aturan bahwa seluruh emisi harus terjadi di thread/context pemanggil collector secara deterministik. Untuk konkurensi di produsen, harus menggunakan `channelFlow`.
7. **C**: `flatMapLatest` secara otomatis membatalkan continuation blok pemrosesan yang dipicu nilai sebelumnya segera setelah nilai baru terpancar.
8. **B**: `StateFlow` adalah spesialisasi penampung state: ia selalu memiliki satu nilai definitif awal dan tidak akan memicu downstream jika nilai baru `equals` dengan nilai lama.
9. **A**: `flowOn` hanya memengaruhi eksekusi operator yang berada di posisi **hulu (upstream)** dari deklarasi pemanggilannya. Downstream selalu mengikuti konteks pemanggil `collect`.
10. **C**: `MutableStateFlow` memiliki optimasi internal bawaan yang membandingkan `oldValue == newValue`. Jika benar, pembaruan diabaikan secara otomatis.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Praktikum: Realtime Infrastructure Monitoring & Alert Engine

### Deskripsi Skenario
Rancang dan implementasikan mesin pemantau metrik performa server secara *real-time*. Mesin ini harus membaca data telemetri yang dipancarkan secara terus-menerus oleh beberapa nodus server (CPU, RAM, Network I/O), mendeteksi anomali performa secara cepat, dan mengirimkan notifikasi tanpa membebani thread sistem.

### Spesifikasi Teknis yang Wajib Dipenuhi

1. **Data Model:**
   * Buat class `MetricSnapshot(val node: String, val cpuLoadPercentage: Double, val ramUsagePercentage: Double, val timestamp: Long)`.
2. **Producer Component:**
   * Bangun fungsi `streamMetrics(): Flow<MetricSnapshot>` yang memancarkan data metrik setiap 50 milidetik per nodus dari thread background (`Dispatchers.IO`).
   * Simulasikan lonjakan beban CPU secara acak (*burst anomaly*).
3. **Processing Pipeline:**
   * Ubah data stream menjadi Hot Stream terpusat menggunakan `shareIn` agar dapat dipantau oleh beberapa pengamat sekaligus.
   * Pasang operator `filter` untuk hanya menjaring anomali (misal: CPU > 85.0% atau RAM > 90.0%).
   * Gunakan operator `debounce(300)` untuk mencegah banjir alarm beruntun jika sistem berada dalam status stres berkepanjangan.
4. **Resilience & Safety:**
   * Terapkan penanganan eksepsi menggunakan `catch` jika simulator mengalami kegagalan hardware buatan.
   * Pastikan tidak ada kebocoran context dengan menggunakan `flowOn`.
5. **Consumer Component:**
   * Pipeline Konsumen 1 (Audit Log): Menulis seluruh anomali ke media penyimpanan secara lambat (simulasikan delay 100ms) dengan strategi backpressure `buffer(16, BufferOverflow.DROP_OLDEST)`.
   * Pipeline Konsumen 2 (Console Alert): Menampilkan peringatan kritis ke konsol seketika tanpa delay.

### Kriteria Kelulusan Evaluasi (Checklist)
* [ ] Menggunakan Kotlin DSL gradle dependencies `kotlinx-coroutines-core:1.7+`.
* [ ] Tidak ditemukan pelanggaran `IllegalStateException: Flow invariant is violated`.
* [ ] Berhasil membuktikan penanganan backpressure berjalan: Producer tidak terblokir permanen saat Consumer 1 tertinggal.
* [ ] Mekanisme pembatalan (*cancellation cooperative*) berjalan sempurna saat scope aplikasi ditutup.