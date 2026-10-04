# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Reactive Streams & Asynchronous Flow — Kategori: 02-Programming-Languages (Kotlin)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda ditargetkan untuk mampu:
1. **Menganalisis dan Membedah Internal Execution Engine Kotlin Flow**: Memahami mekanisme kerja `SafeCollector`, invarian konteks (*context preservation*), suspensi kooperatif, serta alokasi memori pada struktur internal `SharedFlow` dan `StateFlow`.
2. **Merancang Custom Flow Operators yang Production-Grade**: Mengembangkan operator kustom berbasis stream transformation yang mematuhi kontrak reaktif, menangani pembatalan secara deterministik, dan bebas dari *thread hijacking*.
3. **Menguasai Strategi Manajemen Backpressure**: Mengimplementasikan buffer adaptif, *conflation*, *windowing*, dan *sampling* untuk beban *high-throughput* tanpa risiko `OutOfMemoryError` (OOM).
4. **Membangun Arsitektur Streaming Reaktif Terdistribusi**: Mengintegrasikan Kotlin Flow dengan ekosistem enterprise seperti Apache Kafka, RSocket, dan Spring WebFlux dengan prinsip *Structured Concurrency*.
5. **Menjalankan Profiling & Diagnostics Aliran Asinkron**: Mendeteksi *goroutine/coroutine leaks*, kebocoran *buffer slot*, serta mengaudit latensi antar-operator menggunakan metrics dan tracing.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Kotlin Coroutines Core**: Lifecycle coroutine, `Job`, `CoroutineScope`, `Continuation Passing Style` (CPS), serta manipulasi `CoroutineContext`.
* **Dasar Kotlin Flow (Module 01)**: Konsep dasar cold flow (`flow { ... }`), operator standar (`map`, `filter`, `take`), dan basic terminal operator (`collect`, `first`).
* **Java Concurrency & Memory Model (JMM)**: Volatile semantics, Compare-And-Swap (CAS), *thread allocation*, dan *memory barrier*.
* **Dasar Reactive Streams Specification**: Publisher, Subscriber, Subscription, dan kontrak backpressure standar (Reactive Streams 1.0 specification).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi SafeCollector dan Context Preservation Invariant

Kotlin Flow mempertahankan sebuah invarian fundamental: **Context Preservation**. Invarian ini menjamin bahwa emisi elemen dari sebuah Flow harus dieksekusi di dalam `CoroutineContext` milik `Collector` (pemanggil fungsi `collect`), bukan di dalam konteks emitor.

```
       +-------------------------------------------------------+
       |                  collectContext                       |
       |  (e.g., Dispatchers.Main + CoroutineExceptionHandler) |
       +---------------------------+---------------------------+
                                   ^
                                   | (Must Match via checkContext)
                                   v
       +-------------------------------------------------------+
       |                  emissionContext                      |
       |             (Current CoroutineContext)                |
       +-------------------------------------------------------+
```

Jika seorang developer mencoba mengalihkan context di dalam blok builder menggunakan `withContext(Dispatchers.IO)` lalu memanggil `emit()`, Flow runtime akan melempar exception:
`IllegalStateException: Flow invariant is violated: Emission from another coroutine is detected...`

Secara internal, invarian ini ditegakkan oleh `SafeCollector`:
1. `SafeCollector` membungkus target `FlowCollector` downstream.
2. Ketika `emit(value)` dipanggil, runtime memanggil metode `checkContext(currentContext, emissionContext)`.
3. `SafeCollector` membandingkan `currentCoroutineContext()` dengan `collectContext` awal.
4. Jika terdapat elemen konteks yang bertentangan (misalnya `ContinuationInterceptor` atau `Job` yang berbeda), emisi ditolak secara langsung sebelum data sempat dialirkan.

Satu-satunya cara yang valid untuk mengubah konteks eksekusi hulu (*upstream*) adalah melalui operator `flowOn(context)`, yang secara arsitektural memisahkan emitor dan kolektor menggunakan internal buffer dan channel bridge.

### 3.2 ChannelFlow Operator Engine & Suspension Bridge

Operator transisi konteks seperti `flowOn`, `buffer`, dan `flatMapMerge` tidak menggunakan `flow { ... }` biasa, melainkan mengompilasi eksekusi ke dalam turunan `ChannelFlow`.

```
[ Upstream Producer ] 
        |  (runs in upstreamContext via produceCoroutines)
        v
[ SafeCollector ] 
        | 
        v
[ Channel.send() ]  <--- Channel Buffer (Rendezvous / ArrayChannel)
        |
        +---- Coroutine Boundary (Channel Flow Bridge) ----+
                                                           |
                                                [ Channel.receive() ]
                                                           |
                                                           v
                                                [ Downstream Collector ]
                                                   (runs in collectContext)
```

1. **Upstream Isolation**: `ChannelFlow` mengeksekusi producer di dalam coroutine independen menggunakan builder internal `produce(upstreamContext)`.
2. **Backpressure Decoupling**: Downstream dan upstream berjalan di atas dua loop coroutine terpisah yang disambungkan oleh buffer `Channel`.
3. **Suspension Handshake**: Ketika buffer penuh, emisi `upstream` tersuspensi secara kooperatif melalui primitive `Channel.send(T)`. Saat downstream memproses data via `Channel.receive()`, sinyal unpark memulihkan eksekusi producer.

### 3.3 StateFlow & SharedFlow Memory Architecture

`SharedFlowImpl` dan `StateFlowImpl` dibangun di atas arsitektur *lock-free allocation* menggunakan optimasi array sirkular (*ring buffer*) dan *slot allocation*:

```
SharedFlowImpl
 ├── buffer: Array<Any?>? (Head-Tail Ring Buffer)
 ├── slots: Array<SharedFlowSlot?>? (Array of Active Subscribers)
 ├── minCollectorIndex: Long (Lowest read cursor among all active collectors)
 ├── replayIndex: Long (Oldest value preserved for new subscribers)
 └── bufferSize / maxBufferCapacity
```

* **Slot Allocation Pattern**: Setiap kali `collect` dipanggil pada `SharedFlow`, runtime mengalokasikan atau mengambil kembali objek `SharedFlowSlot` dari array `slots` menggunakan loop CAS.
* **Non-blocking Replay**: Ketika subscriber baru terhubung, ia membaca nilai historis langsung dari ring buffer internal mulai dari `replayIndex` tanpa menghentikan producer.
* **Fast-Path vs Slow-Path**: Jika `extraBufferCapacity == 0` dan strategi buffer adalah `SUSPEND`, emisi downstream yang lambat akan memaksa producer mengalokasikan node suspensi (`Emitter`) dan menunda eksekusi sampai subscriber paling lambat memajukan indeks bacanya (*slowest subscriber barrier*).

---

## 4. Why & What

### Mengapa Memilih Kotlin Flow Dibandingkan Reactive Framework Klasik?

| Dimensi Arsitektural | Kotlin Flow | RxJava 3 / Project Reactor |
| :--- | :--- | :--- |
| **Model Eksekusi** | Coroutine Suspensions (Direct, non-blocking) | Monadic Composition (`flatMap`, chained callbacks) |
| **Tracing & Debugging** | Native Call Stack (Stack trace menyerupai sync code) | Deep Asynchronous Call Stack (Perlu hook assembler khusus) |
| **Context Propagation** | Otomatis via `CoroutineContext` (ThreadLocal safe) | Manual passing via Reactor `SubscriberContext` |
| **Null Safety** | Built-in Language Level Type System | Memerlukan Wrapper seperti `Optional<T>` atau sentinel |
| **Footprint Memori** | Ringan (Hanya state machine continuation) | Berat (Banyak instansiasi operator subscriber/subscription) |
| **Standar Industri** | Standar resmi Kotlin & Jetpack Android | Standar de-facto Java legacy/enterprise Spring 5 |

### Kapan Menggunakan Flow, SharedFlow, dan StateFlow?

1. **Cold Flow (`Flow<T>`)**:
   * *Use Case*: Operasi *on-demand*, komputasi independen tiap kolektor (misal: query database Room/Exposed, panggilan API HTTP tunggal, stream pembacaan file I/O).
   * *Sifat*: Mengulang eksekusi dari awal untuk setiap pemanggil `collect()`.

2. **SharedFlow (`SharedFlow<T>`)**:
   * *Use Case*: Event broadcasting sistem (misal: event klik UI, pub/sub notifikasi WebSocket terpusat, telemetry log stream).
   * *Sifat*: *Hot stream*, banyak subscriber berbagi satu stream peristiwa, mendukung cache replay dan strategi *drop buffer*.

3. **StateFlow (`StateFlow<T>`)**:
   * *Use Case*: Penyimpanan representasi *state* sistem yang selalu memiliki nilai awal dan hanya mempertahankan nilai terbaru (misal: Application Configuration State, ViewState pada MVVM/MVI).
   * *Sifat*: Spesialisasi dari `SharedFlow` dengan kapasitas buffer 1, deduplikasi otomatis via `Any.equals()`, dan sifat konvergen ke representasi data terkini (*conflated*).

---

## 5. How (Workflow Detail)

Berikut adalah workflow perancangan pipeline data reaktif performa tinggi dari hulu ke hilir:

```
[ External Source: Kafka / Sockets ]
                │
                ▼
1. INGESTION (Reactive Bridge)
   - Konversi Stream I/O ke Flow via callbackFlow {}
   - Pasang awaitClose {} untuk clean teardown resource
                │
                ▼
2. BOUNDARY ISOLATION
   - Terapkan .flowOn(Dispatchers.IO)
   - Cegah perembesan context thread upstream ke business logic
                │
                ▼
3. BACKPRESSURE MITIGATION
   - Injeksi .buffer(capacity, BufferOverflow.DROP_OLDEST)
   - Gunakan windowing / batching / debouncing
                │
                ▼
4. BUSINESS TRANSFORMATION
   - Eksekusi custom context-preserving operator
   - Concurrent mapping via flatMapMerge / transformLatest
                │
                ▼
5. ERROR BOUNDARY & RECOVERY
   - Tangkap transient fault dengan .retryWhen { cause, attempt -> ... }
   - Terminal catch block untuk isolasi failure
                │
                ▼
6. BROADCAST / CONSUMPTION
   - Distribusikan via .shareIn() / .stateIn() jika multi-consumer
   - Terminal collection di dalam supervisor CoroutineScope
```

---

## 6. Analogy & Diagram ASCII

### Analogi Jalur Pipa Air Pintar (Smart Plumbing Pipeline)

* **Cold Flow**: Seperti instalasi keran air kamar mandi. Air tidak mengalir dari tandon sampai seseorang secara eksplisit memutar kran (`collect`). Setiap kran yang dibuka memicu aliran air terpisah.
* **Hot SharedFlow**: Seperti stasiun siaran radio FM komersial. Siaran terus memancar tanpa peduli apakah ada pesawat radio yang menyala. Jika radio dinyalakan terlambat, lagu yang sudah lewat tidak bisa didengar kembali (kecuali ada memori perekam / *replay buffer*).
* **SafeCollector**: Seperti katup pengaman tekanan (*pressure regulator*) yang dipasang wajib pada pipa. Jika ada teknisi yang mencoba menyuntikkan zat kimia dari pipa bertekanan berbeda tanpa adaptor isolasi (`flowOn`), katup langsung menutup total dan membunyikan alarm sistem (`IllegalStateException`).

### Diagram Arsitektur Internal: SafeCollector & Context Enforcement

```
+-----------------------------------------------------------------------------------+
| CoroutineScope: [ Dispatchers.Default + JobA ] (Collect Execution Site)          |
|                                                                                   |
|  myFlow.collect { value ->                                                       |
|     // Collect Logic                                                              |
|  }                                                                                |
+-----------------------------------------+-----------------------------------------+
                                          | invokes
                                          v
+-----------------------------------------------------------------------------------+
| SafeCollector Wrapper                                                             |
|                                                                                   |
|  fun emit(value: T) {                                                             |
|      val currentContext = currentCoroutineContext()                               |
|      checkContext(currentContext) // Memvalidasi currentContext == collectContext |
|      if (violates) throw IllegalStateException()                                  |
|      downstream.emit(value)                                                       |
|  }                                                                                |
+-----------------------------------------+-----------------------------------------+
                                          ^
                                          | Suspended Emit Call
+-----------------------------------------+-----------------------------------------+
| flow { ... } Body                                                                |
|                                                                                   |
|  // VALID:                                                                        |
|  emit(data) // Berjalan di context collectContext                                 |
|                                                                                   |
|  // INVALID (MELEMPAR EXCEPTION):                                                 |
|  withContext(Dispatchers.IO) {                                                    |
|      emit(data) // Mengubah ContinuationInterceptor secara ilegal!                |
|  }                                                                                |
+-----------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Membangun Custom Operator yang Mematuhi Context Preservation

Contoh berikut menunjukkan cara membuat custom operator transformatif yang mengukur durasi antar-elemen (delta latency) tanpa melanggar kontrak internal `Flow`.

```kotlin
package com.enterprise.flow.operators

import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import kotlin.system.measureTimeMillis

data class TimedSample<T>(val payload: T, val latencyMs: Long)

/**
 * Custom operator: Menghitung delta latensi pemrosesan upstream ke downstream.
 * Mematuhi invarian kontekstual tanpa manipulasi context ilegal.
 */
fun <T> Flow<T>.measureInterval(): Flow<TimedSample<T>> = flow {
    var lastTimestamp = System.currentTimeMillis()
    
    // Invarian collector terjaga karena emisi dieksekusi di context pemanggil
    collect { value ->
        val currentTimestamp = System.currentTimeMillis()
        val interval = currentTimestamp - lastTimestamp
        lastTimestamp = currentTimestamp
        
        emit(TimedSample(payload = value, latencyMs = interval))
    }
}

fun main() = runBlocking {
    val sourceFlow = flow {
        emit("Packet-1")
        delay(150)
        emit("Packet-2")
        delay(300)
        emit("Packet-3")
    }

    sourceFlow
        .measureInterval()
        .collect { sample ->
            println("Received: ${sample.payload} | Interval: ${sample.latencyMs}ms | Thread: ${Thread.currentThread().name}")
        }
}
```

### 7.2 Practical Example: High-Throughput Sliding-Window Micro-Batcher

Dalam sistem ingestion transaksi keuangan, memproses data satu per satu menimbulkan overhead database commit yang masif. Di bawah ini adalah operator *time-and-count sliding batcher* yang thread-safe, non-leaking, dan mengimplementasikan mekanisme *flush* otomatis saat stream selesai.

```kotlin
package com.enterprise.flow.operators

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.flow.*
import java.util.concurrent.atomic.AtomicInteger

/**
 * Operator yang mengelompokkan elemen ke dalam chunk List<T> berdasarkan
 * ukuran batch maksimum atau rentang waktu maksimum (timeout).
 */
fun <T> Flow<T>.chunkedByTimeoutAndSize(
    maxBatchSize: Int,
    timeoutMs: Long
): Flow<List<T>> = channelFlow {
    require(maxBatchSize > 0) { "maxBatchSize must be greater than 0" }
    require(timeoutMs > 0) { "timeoutMs must be greater than 0" }

    val upstreamChannel = Channel<T>(Channel.BUFFERED)
    
    // Coroutine upstream collector
    launch {
        try {
            collect { item ->
                upstreamChannel.send(item)
            }
        } finally {
            upstreamChannel.close()
        }
    }

    val currentBatch = mutableListOf<T>()
    var deadline = System.currentTimeMillis() + timeoutMs

    while (isActive) {
        val remainingTime = deadline - System.currentTimeMillis()
        
        if (remainingTime <= 0) {
            // Flush karena window waktu habis
            if (currentBatch.isNotEmpty()) {
                send(currentBatch.toList())
                currentBatch.clear()
            }
            deadline = System.currentTimeMillis() + timeoutMs
            continue
        }

        // Tunggu data berikutnya dengan timeout non-blocking
        val result = withTimeoutOrNull(remainingTime) {
            upstreamChannel.receiveCatching()
        }

        if (result == null) {
            // Timeout tercapai
            if (currentBatch.isNotEmpty()) {
                send(currentBatch.toList())
                currentBatch.clear()
            }
            deadline = System.currentTimeMillis() + timeoutMs
        } else if (result.isClosed) {
            // Stream hulu telah selesai, flush sisa buffer jika ada
            if (currentBatch.isNotEmpty()) {
                send(currentBatch.toList())
                currentBatch.clear()
            }
            break
        } else {
            // Elemen valid diterima
            val item = result.getOrThrow()
            currentBatch.add(item)
            if (currentBatch.size >= maxBatchSize) {
                send(currentBatch.toList())
                currentBatch.clear()
                deadline = System.currentTimeMillis() + timeoutMs
            }
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Desain Distributed IoT Telemetry Ingestion Gateway

**Konteks Masalah**: Sebuah perusahaan Smart Grid mengelola 500.000 smart meter yang mengirimkan status konsumsi daya setiap 500 milidetik via TCP/WebSocket. Pipeline harus melakukan:
1. Parsing packet mentah pada worker pools terisolasi.
2. Deduplikasi sinyal identik menggunakan state windowing.
3. *Backpressure protection*: Jika database downstream mengalami penurunan performa (latensi write naik), sistem tidak boleh kehabisan memori (*OOM*); sistem harus beralih ke strategi penjatuhan metriks yang cerdas (*selective drops*).
4. Menyediakan stream broadcast real-time untuk audit alerting room.

```
[ 500k Smart Meters ]
        │  (TCP / WS Connection Pool)
        ▼
[ Network Gateway: callbackFlow ] 
        │  Dispatcher: Dispatchers.IO
        ▼
[ Ingestion Pipe: .flowOn(IO) ]
        │
        ▼
[ Conflation & Buffering Boundary ]
  .buffer(capacity = 5000, BufferOverflow.DROP_OLDEST)
        │
        ▼
[ Business Deduplication: distinctUntilChanged() ]
        │
        ▼
[ Distributed Fan-Out via SharedFlow ]
        ├─── Collector A: TimescaleDB Bulk Batch Writer (Storage)
        └─── Collector B: Anomaly Detection Engine (Alerting)
```

```kotlin
package com.enterprise.telemetry

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.*
import java.util.concurrent.ConcurrentHashMap

data class MeterReading(
    val meterId: String,
    val voltage: Double,
    val currentAmp: Double,
    val timestamp: Long
)

interface NetworkTransportListener {
    fun onData(reading: MeterReading)
    fun onError(t: Throwable)
    fun onClosed()
}

interface SocketClient {
    fun registerListener(listener: NetworkTransportListener)
    fun disconnect()
}

class TelemetryIngestionPipeline(
    private val socketClient: SocketClient,
    private val scope: CoroutineScope
) {
    // Shared Broadcast Stream: Single Producer, Multiple Downstream Consumers
    private val _telemetryBroadcast = MutableSharedFlow<MeterReading>(
        replay = 0,
        extraBufferCapacity = 10_000,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val telemetryBroadcast: SharedFlow<MeterReading> = _telemetryBroadcast.asSharedFlow()

    fun startPipeline() {
        // Step 1: Wrap callback API into cold flow
        val networkFlow: Flow<MeterReading> = callbackFlow {
            val listener = object : NetworkTransportListener {
                override fun onData(reading: MeterReading) {
                    trySend(reading).onFailure {
                        // Log backpressure drop pada batas network input
                    }
                }

                override fun onError(t: Throwable) {
                    cancel(CancellationException("Transport layer error", t))
                }

                override fun onClosed() {
                    channel.close()
                }
            }

            socketClient.registerListener(listener)

            awaitClose {
                socketClient.disconnect()
            }
        }

        // Step 2 & 3: Run pipeline with bounded buffer and context offloading
        scope.launch {
            networkFlow
                .flowOn(Dispatchers.IO) // I/O parsing boundary
                .filter { it.voltage > 0.0 } // Sanity check
                .catch { cause -> 
                    // Recovery boundary dari transport failure
                    emitFallbackMetric(cause)
                }
                .collect { validatedMetric ->
                    _telemetryBroadcast.emit(validatedMetric)
                }
        }
    }

    private fun emitFallbackMetric(t: Throwable) {
        println("Log critical error pipeline: ${t.message}")
    }
}
```

---

## 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Kerugian & Batasan | Mitigasi / Rekomendasi |
| :--- | :--- | :--- | :--- |
| **`buffer(capacity = UNLIMITED)`** | Mencegah suspensi producer; throughput ingestion maksimal. | Potensi fatal `OutOfMemoryError` jika downstream macet dalam periode lama. | **Dilarang keras di produksi** tanpa bounded guard di layer infrastructure. |
| **`conflate()`** (Atau `buffer(1, DROP_OLDEST)`) | Konsumsi memori sangat rendah ($O(1)$), subscriber selalu memproses data paling update. | Kehilangan data historis (*lossy stream*). Tidak cocok untuk financial ledger/transaksi. | Gunakan hanya untuk metriks, telemetry visualisasi UI, atau tracking lokasi GPS. |
| **`flatMapMerge` vs `flatMapConcat`** | `flatMapMerge` menawarkan konkurensi tinggi antar child-flows secara paralel. | Urutan emisi acak (*non-deterministic order*) dan konsumsi resource worker membengkak. | Batasi parameter `concurrency` secara eksplisit (e.g., `concurrency = 16`). |
| **`SharedFlow` Replay Cache Besar** | Consumer baru langsung mendapatkan konteks lampau yang lengkap. | Mengunci objek lama di Garbage Collection heap, meningkatkan bahaya GC Pause. | Pertahankan ukuran `replay` sekecil mungkin ($\le 5$), gunakan bounded cache eksplisit. |

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: Melanggar Context Preservation via `withContext`
```kotlin
// ERROR CODE: AKAN MELEMPAR ILLEGALSTATEEXCEPTION
fun fetchUserData(): Flow<User> = flow {
    withContext(Dispatchers.IO) {
        val user = api.getUser()
        emit(user) // CRASH: Emission from another coroutine!
    }
}

// PERBAIKAN ARSITEKTURAL YANG BENAR:
fun fetchUserData(): Flow<User> = flow {
    val user = api.getUser() // Suspends cooperatively
    emit(user)
}.flowOn(Dispatchers.IO) // Mengalihkan context eksekusi upstream secara sah
```

### Anti-Pattern 2: Swallowing Exception Menggunakan `catch` Tanpa Re-throwing Coroutine Cancellation
```kotlin
// BAHAYA: Pembatalan Coroutine Diinterupsi
myFlow
    .catch { throwable ->
        // Jika throwable adalah CancellationException, Anda merusak Structured Concurrency!
        println("Handled error: $throwable")
    }
    .collect()

// POLA RECOVERY PRODUKSI YANG BENAR:
myFlow
    .catch { cause ->
        if (cause is CancellationException) throw cause
        logger.error("Domain failure detected", cause)
        emit(FallbackObject)
    }
    .collect()
```

### Anti-Pattern 3: SharedFlow "Silent Hanging" Akibat Unbounded Suspension
```kotlin
// MASALAH: Producer terhenti selamanya jika salah satu kolektor lambat
val events = MutableSharedFlow<Event>(extraBufferCapacity = 0) // Default: SUSPEND

// SOLUSI PRODUKSI: Tentukan kebijakan Buffer Overflow
val safeEvents = MutableSharedFlow<Event>(
    replay = 1,
    extraBufferCapacity = 64,
    onBufferOverflow = BufferOverflow.DROP_OLDEST
)
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Context Preservation Compliance**: Semua emisi dari blok `flow { ... }` bebas dari wrapping `withContext` langsung. Operator `flowOn` digunakan eksklusif untuk isolasi thread pool.
- [ ] **Cancellation Propagation**: Setiap custom flow builder berbasis callback memanfaatkan `awaitClose` untuk melepaskan resource native/network listener secara deterministik.
- [ ] **Bounded Backpressure**: Tidak ada stream tak berhingga (*infinite stream*) yang menggunakan operator `buffer()` tanpa batas ukuran kapasitas (`Channel.UNLIMITED`).
- [ ] **Structural Isolation di Error Handling**: Operator `catch` diletakkan strategis sebelum operator pemrosesan tertentu untuk mengisolasi kegagalan parsing dari downstream failure.
- [ ] **SharedFlow Slot Management**: Menghindari alokasi `MutableSharedFlow` publik; selalu ekspos sebagai *read-only* interface via `.asSharedFlow()` atau `.asStateFlow()`.
- [ ] **Testability Harness**: Semua pipeline Flow dapat diuji secara deterministik menggunakan *virtual time testing framework* (`runTest` dan library `Turbine`).

---

## 12. Hands-on Practice

Struktur direktori praktikum yang harus Anda siapkan:
```text
hands-on/m02/
├── build.gradle.kts
└── src
    ├── main
    │   └── kotlin
    │       └── com
    │           └── enterprise
    │               └── flow
    │                   ├── AuditEvent.kt
    │                   └── ResilientEventStream.kt
    └── test
        └── kotlin
            └── com
                └── enterprise
                    └── flow
                        └── ResilientEventStreamTest.kt
```

### 12.1 Konfigurasi Dependensi: `build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm") version "1.9.22"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
    testImplementation("app.cash.turbine:turbine:1.0.0")
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}
```

### 12.2 Model dan Core Logic: `AuditEvent.kt` & `ResilientEventStream.kt`

```kotlin
// src/main/kotlin/com/enterprise/flow/AuditEvent.kt
package com.enterprise.flow

data class AuditEvent(
    val traceId: String,
    val payload: String,
    val timestamp: Long = System.currentTimeMillis()
)
```

```kotlin
// src/main/kotlin/com/enterprise/flow/ResilientEventStream.kt
package com.enterprise.flow

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*

class ResilientEventStream(
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO
) {
    private val _eventHub = MutableSharedFlow<AuditEvent>(
        replay = 0,
        extraBufferCapacity = 128,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val eventHub: SharedFlow<AuditEvent> = _eventHub.asSharedFlow()

    suspend fun publish(event: AuditEvent): Boolean {
        return _eventHub.emit(event).let { true }
    }

    /**
     * Memproses aliran audit event dengan retry mechanism, 
     * deduplikasi, serta context offloading.
     */
    fun processPipeline(source: Flow<AuditEvent>): Flow<String> {
        return source
            .flowOn(ioDispatcher)
            .distinctUntilChanged { old, new -> old.traceId == new.traceId }
            .retryWhen { cause, attempt ->
                if (cause is IllegalArgumentException && attempt < 3) {
                    emit(AuditEvent("SYSTEM-RETRY", "Retrying..."))
                    true
                } else {
                    false
                }
            }
            .map { event ->
                "PROCESSED: [${event.traceId}] - ${event.payload.uppercase()}"
            }
            .catch { cause ->
                emit("ERROR-FALLBACK: ${cause.message}")
            }
    }
}
```

### 12.3 Unit Testing & Assertions: `ResilientEventStreamTest.kt`

```kotlin
// src/test/kotlin/com/enterprise/flow/ResilientEventStreamTest.kt
package com.enterprise.flow

import app.cash.turbine.test
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(ExperimentalCoroutinesApi::class)
class ResilientEventStreamTest {

    @Test
    fun `pipeline should process and deduplicate continuous traceIds`() = runTest {
        val testDispatcher = StandardTestDispatcher(testScheduler)
        val streamService = ResilientEventStream(ioDispatcher = testDispatcher)

        val input = flowOf(
            AuditEvent(traceId = "TR-1", payload = "create-order"),
            AuditEvent(traceId = "TR-1", payload = "duplicate-order"), // Harus dibuang
            AuditEvent(traceId = "TR-2", payload = "pay-order")
        )

        streamService.processPipeline(input).test {
            assertEquals("PROCESSED: [TR-1] - CREATE-ORDER", awaitItem())
            assertEquals("PROCESSED: [TR-2] - PAY-ORDER", awaitItem())
            awaitComplete()
        }
    }

    @Test
    fun `pipeline should handle errors gracefully and output fallback`() = runTest {
        val testDispatcher = StandardTestDispatcher(testScheduler)
        val streamService = ResilientEventStream(ioDispatcher = testDispatcher)

        val faultyFlow = flow {
            emit(AuditEvent(traceId = "TR-1", payload = "normal-event"))
            throw RuntimeException("Database unreachable")
        }

        faultyFlow.let { streamService.processPipeline(it) }.test {
            assertEquals("PROCESSED: [TR-1] - NORMAL-EVENT", awaitItem())
            assertEquals("ERROR-FALLBACK: Database unreachable", awaitItem())
            awaitComplete()
        }
    }
}
```

---

## 13. Exercise

### Tingkat: Easy
Buat custom extension function `Flow<T>.throttleFirst(windowDurationMs: Long): Flow<T>`. Operator ini harus memancarkan elemen pertama yang tiba, lalu membuang semua elemen yang masuk selama durasi jendela waktu tersebut sebelum mengizinkan elemen berikutnya lewat.

### Tingkat: Medium
Rancang operator `Flow<T>.dynamicBatch(predicate: (List<T>, T) -> Boolean): Flow<List<T>>`. Operator ini mengumpulkan elemen ke dalam batch dan melakukan evaluasi apakah elemen baru (`T`) masih boleh digabungkan ke `List<T>` yang sedang aktif atau harus memicu pemotongan batch baru, tanpa menggunakan primitive blocking.

### Tingkat: Hard
Kembangkan komponen `PriorityMessageBus<T : Prioritized>`. Komponen ini harus:
1. Menerima message dari berbagai coroutine secara bersamaan.
2. Menggunakan Kotlin Flow internal untuk mengalirkan elemen ke satu consumer.
3. Menjamin jika terjadi kongesti (*backpressure*), pesan dengan prioritas lebih rendah (`Priority.LOW`) ditumpuk atau dijatuhkan terlebih dahulu dibanding pesan (`Priority.HIGH`), tanpa melanggar struktur suspensi coroutine.

---

## 14. Challenge

**Studi Kasus: Adaptive Windowed OutboxCDC Engine**

Anda ditugaskan mendesain mesin *Change Data Capture* (CDC) in-memory untuk membaca log perubahan database. Spesifikasi tantangan:
1. Buat stream Flow yang membaca *event changelog* secara terus menerus.
2. Jika kecepatan downstream normal, kemas data dalam batch per 100 elemen atau per 50 milidetik.
3. **Adaptive Backpressure Control**: Pantau waktu eksekusi proses downstream. Jika downstream memerlukan waktu lebih dari 500 milidetik untuk memproses batch terakhir, mesin CDC hulu harus secara dinamis memperbesar ukuran batch hingga 1000 elemen dan menaikkan waktu tampung hingga 2000 milidetik untuk memaksimalkan bulk write efficiency.
4. Jika downstream kembali normal (latensi pemrosesan $< 100$ milidetik), sistem harus secara bertahap kembali (*ramp-down*) ke parameter normal secara otomatis.
5. Sistem harus zero memory-leak dan tidak boleh menggunakan locking primitive (`ReentrantLock` dilarang, hanya coroutine primitive, atomics, atau Channel flows).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Cepat)

**Q1:** Mengapa kode di bawah melempar `IllegalStateException: Flow invariant is violated`?
```kotlin
fun test(): Flow<Int> = flow {
    withContext(Dispatchers.Default) {
        emit(42)
    }
}
```
*A.* Karena `emit` tidak dapat dipanggil dari dalam blok lambda.  
*B.* Karena `withContext` mengubah `ContinuationInterceptor` konteks koleksi downstream secara ilegal.  
*C.* Karena `Dispatchers.Default` tidak mendukung suspend functions.  
*D.* Karena Flow tidak mengizinkan tipe data primitif `Int`.  
*(Jawaban: **B**. Internal `SafeCollector` memverifikasi kesetaraan context secara tegas).*

**Q2:** Operator manakah yang mengalihkan konteks eksekusi operasi hulu (*upstream*) secara sah tanpa melanggar invarian konteks?  
*(Jawaban: **`flowOn`**).*

**Q3:** Apa perbedaan fungsional utama antara `StateFlow` dan `SharedFlow` yang dikonfigurasi dengan `replay = 1`?  
*(Jawaban: `StateFlow` selalu memiliki nilai awal, memfilter emisi duplikat menggunakan `equals()` (*conflation*), sedangkan `SharedFlow` dapat dimulai tanpa nilai awal dan mengizinkan emisi nilai berturut-turut yang identik).*

**Q4:** Apa yang terjadi jika buffer `MutableSharedFlow` penuh dan parameter `onBufferOverflow` disetel ke `BufferOverflow.SUSPEND`?  
*(Jawaban: Pemanggil fungsi `emit()` akan tersuspensi (*suspend*) hingga semua subscriber lambat memajukan cursor konsumsi mereka atau buffer memiliki ruang kosong).*

**Q5:** Kapan fungsi pembersih pada blok `awaitClose { ... }` di dalam `callbackFlow` akan dipanggil?  
*(Jawaban: Dipanggil ketika downstream consumer membatalkan coroutine pengumpulan (*cancellation*), stream ditutup secara eksplisit via `channel.close()`, atau terjadi kegagalan/exception di dalam flow pipeline).*

---

### Bagian 2: Intermediate (Arsitektur & Troubleshooting)

**Q6:** Apa kelemahan arsitektur dari penggabungan multi-stream menggunakan operator `flatMapMerge` tanpa argumen `concurrency` pada sistem backend berlatensi tinggi?  
*(Jawaban: Secara default, `concurrency` bernilai `DEFAULT_CONCURRENCY` (16). Jika setiap child flow mengeksekusi operasi blocking/I/O lambat tanpa batasan, hal ini dapat memicu konsumsi coroutine yang tidak terkontrol atau kelaparan thread (*thread starvation*) pada dispatcher bersama).*

**Q7:** Jelaskan alokasi memori internal `SharedFlowSlot` pada saat terjadi peningkatan (*spike*) jumlah subscriber sementara!  
*(Jawaban: `SharedFlow` mengalokasikan slot subscriber pada array sirkular internal. Saat subscriber bertambah, ukuran array digandakan jika penuh. Saat subscriber selesai/dibatalkan, slot ditandai sebagai bebas (*free*) untuk di-reuse oleh subscriber baru guna menghindari churn alokasi GC, tetapi kapasitas array dasar tidak menyusut secara agresif).*

**Q8:** Bagaimana cara menghentikan aliran data dari infinite cold flow secara aman tanpa menyebabkan kebocoran memori coroutine?  
*(Jawaban: Batalkan `Job` dari `CoroutineScope` pengumpul data, atau gunakan operator pembatas berbasis pembatalan kooperatif seperti `take(n)`, `takeWhile { ... }`, atau `first()` yang melemparkan `AbortFlowException` internal untuk menghentikan pengumpulan).*

**Q9:** Mengapa operator `flow.catch { ... }` tidak mampu menangkap exception yang terjadi di dalam blok terminal operator `collect { ... }` hilir?  
*(Jawaban: Karena operator `catch` hanya bertindak transparan menangani pengecualian yang terjadi di sisi **upstream** (di atas deklarasi `catch`). Kegagalan downstream harus ditangani dengan membungkus blok `collect` menggunakan `try-catch` biasa).*

**Q10:** Bagaimana cara mengonversi `Flow<T>` menjadi `StateFlow<T>` di dalam arsitektur ViewModel/Presenter, dan sebutkan parameter siklus hidup yang krusial!  
*(Jawaban: Menggunakan operator `stateIn(scope, started, initialValue)`. Parameter krusial adalah `started` (misalnya `SharingStarted.WhileSubscribed(5000)`), yang menonaktifkan pengumpulan upstream 5 detik setelah subscriber terakhir terputus untuk menghemat bandwidth).*

---

### Bagian 3: Production Case Scenarios

**Skenario 1:** Sistem agregasi harga saham menerima 100.000 kutipan (*price updates*) per detik melalui socket feed. Layanan antarmuka pengguna hanya mampu memperbarui tampilan grafis pada kecepatan 60 fps (sekitar 16ms sekali). Jika downstream dipaksa mengonsumsi setiap data, memori meledak (*heap exhaustion*). Arsitektur operator apa yang wajib diimplementasikan pada edge layer ingestion ini?  
*(Solusi Analisis: Gunakan operator `conflate()` atau `buffer(capacity = 1, onBufferOverflow = BufferOverflow.DROP_OLDEST)`. Operator ini memutus backpressure suspensif dengan membuang harga perantara yang belum sempat diproses oleh UI dan hanya mempertahankan quote harga paling mutakhir untuk setiap tick render).*

**Skenario 2:** Sebuah microservice mengonsumsi stream partisi Apache Kafka, melakukan de-serialisasi data payload, lalu mengeksekusi write batch ke Cassandra. Terdeteksi terjadi "Memory Spike" bertahap hingga JVM mengalami Crash Loop. Hasil heap dump menunjukkan jutaan instansiasi continuation object tertahan pada internal queue. Di manakah letak kebocoran arsitektur ini?  
*(Solusi Analisis: Kegagalan tersebut disebabkan oleh penggunaan `buffer(UNLIMITED)` atau producer `callbackFlow` yang memanggil `trySend()` tanpa penanganan fallback ketika channel penuh, digabungkan dengan downstream Cassandra sink yang tersuspensi lama tanpa timeout. Solusinya adalah menetapkan batas tegas kapasitas buffer (misal `capacity = 500`), menerapkan batching operator bertarget timeout, dan memastikan dispatcher Cassandra dibatasi kapasitas antreannya).*

**Skenario 3:** Tim Anda mengembangkan pipeline distributed tracing. Mereka menaruh `MDC.put("traceId", id)` di awal `flow { ... }`. Namun, saat log dipanggil di dalam operator intermediate seperti `filter` setelah `flowOn(Dispatchers.IO)`, `traceId` tersebut hilang atau berubah menjadi milik request lain. Mengapa hal ini terjadi dan bagaimana solusinya?  
*(Solusi Analisis: MDC berbasis `ThreadLocal`. Operator `flowOn` memindahkan eksekusi upstream dan downstream ke thread yang berbeda dari pool coroutine. Solusinya adalah memanfaatkan integrasi CoroutineContext Element resmi seperti `MDCContext()` dari library `kotlinx-coroutines-slf4j` yang menduplikasi dan memulihkan thread-local map setiap kali terjadi context-switch pada coroutine).*

---

## 16. Summary

1. **Context Preservation Invariant**: Pondasi utama integritas Kotlin Flow adalah penegakan bahwa emisi data tidak boleh mencemari konteks kolektor downstream, diverifikasi secara dinamis oleh `SafeCollector`.
2. **Channel-Flow Hybrid**: Pemisahan konteks (`flowOn`) dan buffering adaptif (`buffer`) diimplementasikan di atas engine Channel coroutine dengan tetap mengekspos API stream fungsional yang deklaratif kepada developer.
3. **Hot Streams Mechanics**: `SharedFlow` dan `StateFlow` menyediakan broadcasting multi-subscriber berkinerja tinggi berbasis memory ring-buffer tanpa locking overhead, ideal untuk event bus dan state management.
4. **Resilience & Production Safety**: Manajemen aliran data enterprise menuntut mitigasi backpressure eksplisit (`conflate`, `DROP_OLDEST`), penanganan error yang mematuhi kooperatif cancellation, serta observabilitas penuh terhadap thread context dan garbage collection foot-print.