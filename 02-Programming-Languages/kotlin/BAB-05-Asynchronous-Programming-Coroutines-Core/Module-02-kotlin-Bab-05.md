# Kurikulum Enterprise: Kotlin Asynchronous Programming (Coroutines Core)
## Bab 05: Asynchronous Programming - Coroutines Core
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer/Senior Backend Engineer diharapkan mampu:
- Membedah transformasi internal compiler Kotlin dari fungsi `suspend` ke *Continuation Passing Style* (CPS) dan *finite state machine* berbasis bytecode JVM.
- Menguasai aljabar dan topologi `CoroutineContext`, manipulasi elemen kombinatorik (`+`), serta resolusi context propagation.
- Mengimplementasikan pola isolasi kegagalan tingkat lanjut menggunakan `SupervisorJob`, `coroutineScope`, dan `supervisorScope` untuk mencegah kaskade terminasi (*cascading failure*).
- Merancang custom dispatchers dan mengoptimalkan thread scheduling menggunakan `CoroutineScheduler` serta `limitedParallelism` untuk mencegah starvation pada thread pool `Dispatchers.Default` dan `Dispatchers.IO`.
- Mengonstruksi pipeline asynchronous enterprise dengan *backpressure handling* menggunakan Channels, Mutex non-blocking, dan `select` expression.
- Mengidentifikasi, mengisolasi, dan memitigasi memory leak, thread starvation, serta penanganan `CancellationException` yang salah pada sistem terdistribusi skala tinggi.

---

### 2. Prerequisite
Sebelum mendalami modul ini, engineer wajib memiliki pemahaman mendalam tentang:
- Memory Model JVM (JMM): *Thread stack vs Heap, happens-before relationship, volatile semantics, CAS (Compare-And-Swap)*.
- Dasar-dasar Concurrency Java: `ExecutorService`, `ForkJoinPool`, `ThreadLocal`, `ReentrantLock`.
- Silabus Modul 01: Sintaks dasar Coroutine (`launch`, `async`), `suspend` function tingkat dasar, dan Dispatcher standar (`Main`, `IO`, `Default`).
- Pengetahuan dekompilasi JVM Bytecode menggunakan `javap` atau IntelliJ Decompiler.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Continuation Passing Style (CPS) & State Machine Internals
Kotlin Coroutines bersifat *stackless*. Artinya, coroutine tidak mengalokasikan call-stack tingkat thread native OS saat ditangguhkan (*suspended*). Compiler Kotlin mentransformasikan setiap fungsi berpenanda `suspend` secara otomatis pada fase kompilasi frontend IR:

1. Modifikasi Signature: Parameter tersembunyi berjenis `kotlin.coroutines.Continuation<T>` ditambahkan di akhir parameter fungsi. Return type asli `T` diganti menjadi `Any?` untuk mengakomodasi return marker khusus: `COROUTINE_SUSPENDED`.
2. Sintesis State Machine: Kelas turunan anonim dari `SuspendLambda` atau `ContinuationImpl` dihasilkan untuk membungkus stack frame lokal sebagai variabel instance (field).
3. Switch-Labeling: Blok kode dipecah ke dalam switch-case statement berbasis integer label. Setiap *suspension point* merepresentasikan satu transisi label.

```
+-------------------------------------------------------------------------+
|                  Suspend Function Bytecode Transformation               |
+-------------------------------------------------------------------------+
| Signature Asli:                                                         |
|   suspend fun fetchAccount(id: String): Account                         |
|                                                                         |
| Signature Terkompilasi (CPS):                                           |
|   fun fetchAccount(id: String, uCont: Continuation<Account>): Any?      |
|                                                                         |
| Return Value:                                                           |
|   - Mengembalikan Account instance (jika selesai sinkron)               |
|   - Mengembalikan Intrinsics.COROUTINE_SUSPENDED (jika async/suspend)  |
+-------------------------------------------------------------------------+
```

Saat sebuah operasi I/O belum selesai, fungsi mengembalikan objek sentinel `COROUTINE_SUSPENDED`. Thread pemanggil dibebaskan kembali ke pool. Ketika data I/O siap (misal via trigger epoll/kqueue pada level Netty), callback native memanggil `Continuation.resumeWith(result)`, menginjeksi eksekusi kembali ke state machine pada label yang tersimpan dengan membawa konteks data hasil.

#### 3.2. Dekonstruksi CoroutineContext: Persistent Indexed Set
Secara arsitektural, `CoroutineContext` adalah struktur data *type-safe heterogeneous persistent map* (diimplementasikan via `CombinedContext`). Elemen context membentuk hierarki biner mirip linked-list terindeks:

- Setiap elemen memiliki `Key<E>`.
- Operasi penjumlahan konteks `ctxA + ctxB` membentuk `CombinedContext(left, element)`. Elemen di sisi kanan menimpa (*override*) elemen di sisi kiri jika memiliki `Key` yang identik.
- Elemen kunci core meliputi:
  - `Job`: Mengontrol lifecycle, state hierarchy, dan pembatalan (*cancellation*).
  - `CoroutineDispatcher`: Menentukan thread/pool eksekusi task (`ContinuationInterceptor`).
  - `CoroutineExceptionHandler`: Boundary penanganan uncaught exception untuk root coroutine.
  - `CoroutineName`: Identifikasi kontekstual untuk tracing dan observability.

```
       CombinedContext
        /           \
   CombinedContext   CoroutineName("OrderService")
     /        \
  Job     Dispatchers.IO
```

#### 3.3. Job Lifecycle State Engine
State transition dari sebuah `Job` diatur secara ketat dengan transisi searah:

```
                                    wait children
+---------+      +----------+      +-------------+      +-----------+
|   New   | ---> |  Active  | ---> | Completing  | ---> | Completed |
+---------+      +----------+      +-------------+      +-----------+
                      |                   |
                      | cancel / fail     | cancel / fail
                      V                   V
                 +----------+      +-------------+
                 |Cancelling| ---> |  Cancelled  |
                 +----------+      +-------------+
                                    wait children
```

- **Active**: Coroutine sedang berjalan atau siap dijadwalkan.
- **Completing**: Kode coroutine telah selesai dieksekusi, namun masih menunggu semua *child coroutines* yang dinaunginya selesai. State ini bersifat internal; dari perspektif publik (`isActive`), coroutine masih dianggap aktif.
- **Cancelling**: Pembatalan dipicu via `cancel()` atau terjadi uncaught exception. Pembatalan ini memicu sinyal interupsi kooperatif ke bawah hierarki.

#### 3.4. Dispatcher Scheduling Engine: CoroutinesScheduler
`Dispatchers.Default` dan `Dispatchers.IO` berbagi pool eksekusi yang sama di balik layar: `CoroutinesScheduler`.
- Menggunakan arsitektur *work-stealing pool*.
- Setiap worker OS thread memiliki `local queue` berukuran 128 micro-tasks (lock-free ring buffer).
- Terdapat satu `global queue` bersama.
- Ketika worker thread kehabisan task di `local queue`, ia akan mencoba mengambil dari `global queue`, lalu mencuri (*steal*) 50% task dari worker thread lain untuk meminimalkan lock contention.
- `Dispatchers.IO` mengizinkan pembuatan thread elastis melampaui batas CPU core (default `max(64, CPU_CORES)`) menggunakan mekanisme *thread offloading* (blocking tasks). Sebaliknya, `Dispatchers.Default` dibatasi ketat sejumlah CPU core (`Runtime.getRuntime().availableProcessors()`).

---

### 4. Why & What

| Paradigma Concurrency | Model Eksekusi | Alokasi Memori Stack | Cost Context Switching | Kontrol Lifecycle |
| :--- | :--- | :--- | :--- | :--- |
| **Java Platform Threads** | 1:1 OS Thread | 1MB default per stack | Tinggi (Kernel context switch) | Terfragmentasi (`Future`, `Thread.interrupt`) |
| **Reactive Streams (Project Reactor / RxJava)** | Event-driven non-blocking | Stackless (Heap allocations chained) | Rendah (Task switches via scheduler) | Kompleks (Operator composition, split context) |
| **Kotlin Coroutines** | M:N (Stackless Coroutine ke OS Threads) | ~200 - 400 bytes per coroutine frame | Sangat Rendah (User-space scheduling via CPS) | Deterministik via Structured Concurrency |

#### Mengapa Perlu Arsitektur Coroutine Tingkat Lanjut?
Penggunaan coroutine yang naif (seperti meluncurkan ribuan `GlobalScope.launch` atau menyatukan `Dispatchers.IO` tanpa limitasi) membawa bencana di sistem produksi:
1. **Unbounded Thread Growth**: Blocking I/O di dalam thread pool yang tidak dibatasi menyebabkan *thread exhaustion*, degradasi latensi p99, dan akhirnya *Out of Memory (OOM)* pada direct memory JVM.
2. **Exception Leaks**: Kegagalan di satu child coroutine dapat secara tidak sengaja meruntuhkan seluruh lifecycle aplikasi jika struktur `Job` tidak diisolasi menggunakan batas pengawasan (*supervision boundary*).
3. **Leaked Background Processing**: Task yang dibatalkan pada HTTP layer (misal: client disconnect) terus berjalan di background, membuang resource komputasi dan IOPS database jika kooperatif cancellation tidak dipatuhi.

---

### 5. How (Workflow Detail)

Alur penundaan (*suspension*) dan pemulihan (*resumption*) coroutine melibatkan orkestrasi 4 komponen utama:

```
[OS Thread / Caller] 
       │ 
       ▼
[1. Invoke suspend fun] ─── Returns COROUTINE_SUSPENDED? ───► [Thread released to pool]
       │                                                               ▲
       │ (Yes, waiting for I/O / Time)                                 │
       ▼                                                               │
[2. Register Async Callback] (e.g. Netty epoll event / epoll worker)   │
       │                                                               │
       ▼ (Event triggers asynchronously)                               │
[3. Continuation.resumeWith(result)]                                   │
       │                                                               │
       ▼                                                               │
[4. Dispatcher.dispatch(context, block)] ──────────────────────────────┘
       │
       ▼ (Acquires available worker thread from queue)
[5. Execute State Machine Step] ──► Reads label & local vars ──► Transitions to next state
```

1. **Invocation**: Coroutine memanggil fungsi suspend (misal: `client.fetch()`).
2. **Interception**: Dispatcher mencegat eksekusi. Jika dispatcher menentukan eksekusi perlu dipindah ke thread pool lain, task dibungkus dalam `DispatchedContinuation` dan dimasukkan ke antrean worker.
3. **Suspension Point Evaluation**: Operasi underlying mengembalikan status non-ready via `COROUTINE_SUSPENDED`. Stack frame fungsi disimpan ke dalam heap instance `ContinuationImpl`. Thread asal dilepaskan kembali ke pool untuk memproses task lain.
4. **Trigger & Resumption**: Sinyal eksternal (misal: interrupt socket buffer TCP) selesai. Callback memanggil `continuation.resumeWith(Result.success(payload))`.
5. **Re-dispatching & State Progression**: Task ditambahkan kembali ke `CoroutinesScheduler`. Worker thread yang tersedia mengambil context, membaca nilai `label` saat ini pada objek `Continuation`, dan menjalankan blok switch berikutnya membawa payload.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pemrosesan Dokumen Kantor Notaris
- **Thread OS**: Staf notaris tetap. Jumlah staf terbatas karena biaya sewa meja dan gaji (overhead kernel stack 1MB).
- **Coroutine**: Berkas perkara individual yang harus dikerjakan. Jumlahnya bisa ratusan ribu, disimpan rapi dalam folder tipis (Continuation pada heap, ~400 bytes).
- **Suspension Point**: Berkas butuh tanda tangan basah klien luar. Staf tidak diam menatap berkas (blocking). Staf meletakkan stiker penanda "Terhenti di Halaman 4" (`label = 4`), menaruh berkas ke rak, dan segera memproses berkas lain.
- **Resumption**: Kurir membawa dokumen yang sudah ditandatangani. Staf yang sedang nganggur (bisa staf yang sama atau berbeda) mengambil berkas tersebut, melihat stiker Halaman 4, dan melanjutkan langsung ke Halaman 5 tanpa mengulang dari awal.

#### Diagram Arsitektur Internal: CoroutinesScheduler & CPS Transformation

```
                                  KOTLIN COMPILER
+──────────────────────────+                  +─────────────────────────────────────+
| suspend fun getProfile() | ───────────────> | class ProfileStateMachine : ... {   |
|   val u = fetchUser()    |                  |   var label = 0                     |
|   val p = fetchPref(u.id)|                  |   var user: User? = null            |
|   return render(u, p)    |                  |   fun invokeSuspend(...) {          |
| }                        |                  |     when(label) {                   |
+──────────────────────────+                  |       0 -> { label=1; fetchUser() } |
                                              |       1 -> { label=2; fetchPref() } |
                                              |       2 -> { render() }             |
                                              |     }                               |
                                              |   }                                 |
                                              | }                                   |
                                              +─────────────────────────────────────+
                                                                 │
                                                      RUNTIME SCHEDULING
                                                                 ▼
                              +─────────────────────────────────────────────────────────+
                              |                   CoroutinesScheduler                   |
                              |                                                         |
                              |   +-------------------------------------------------+   |
                              |   |                  Global Queue                   |   |
                              |   +-------------------------------------------------+   |
                              |                            │                            |
                              |             ┌──────────────┴──────────────┐             |
                              |             ▼                             ▼             |
                              |    +──────────────────+          +──────────────────+   |
                              |    | Worker Thread 01 |          | Worker Thread 02 |   |
                              |    | +--------------+ | Work     | +--------------+ |   |
                              |    | | Local Queue  | |<─Steal──>| | Local Queue  | |   |
                              |    | | (128 tasks)  | |          | | (128 tasks)  | |   |
                              |    | +--------------+ |          | +--------------+ |   |
                              +────+──────────────────+──────────+──────────────────+───+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Manual CPS State Machine (Simulasi Mekanisme Bytecode)
Berikut adalah representasi murni bagaimana compiler mengeksekusi dua *suspension points* tanpa magic `suspend` keyword:

```kotlin
package com.enterprise.coroutines.cps

import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.coroutines.Continuation
import kotlin.coroutines.CoroutineContext
import kotlin.coroutines.EmptyCoroutineContext

// Sentinel value untuk menandakan operasi belum selesai (asynchronous)
val COROUTINE_SUSPENDED = Any()

interface CustomContinuation<in T> {
    val context: CoroutineContext
    fun resumeWith(result: Result<T>)
}

class ManualFetchUserDataStateMachine(
    private val completion: CustomContinuation<String>
) : CustomContinuation<Any?> {

    override val context: CoroutineContext = EmptyCoroutineContext

    // State preservation (mirip stack frame)
    var label: Int = 0
    var userId: String? = null
    var userEmail: String? = null
    var result: Result<Any?>? = null

    fun execute(param: Result<Any?>): Any? {
        this.result = param

        while (true) {
            when (this.label) {
                0 -> {
                    // Cek error dari initial trigger
                    result?.getOrThrow()
                    println("[State 0] Fetching user id...")
                    this.label = 1
                    val res = fetchUserIdAsync(this)
                    if (res === COROUTINE_SUSPENDED) return COROUTINE_SUSPENDED
                    // Jika sinkron, loop berlanjut
                    this.result = Result.success(res)
                }
                1 -> {
                    val uid = result?.getOrThrow() as String
                    this.userId = uid
                    println("[State 1] User id obtained: $uid. Fetching email...")
                    this.label = 2
                    val res = fetchEmailAsync(uid, this)
                    if (res === COROUTINE_SUSPENDED) return COROUTINE_SUSPENDED
                    this.result = Result.success(res)
                }
                2 -> {
                    val email = result?.getOrThrow() as String
                    this.userEmail = email
                    println("[State 2] Email obtained: $email. Completing flow.")
                    val finalResult = "Profile: ID=${this.userId}, Email=${this.userEmail}"
                    completion.resumeWith(Result.success(finalResult))
                    return finalResult
                }
                else -> throw IllegalStateException("Invalid State")
            }
        }
    }

    override fun resumeWith(result: Result<Any?>) {
        this.result = result
        execute(result)
    }

    private fun fetchUserIdAsync(cont: CustomContinuation<String>): Any? {
        val scheduler = Executors.newSingleThreadScheduledExecutor()
        scheduler.schedule({
            cont.resumeWith(Result.success("usr-99481"))
            scheduler.shutdown()
        }, 100, TimeUnit.MILLISECONDS)
        return COROUTINE_SUSPENDED
    }

    private fun fetchEmailAsync(userId: String, cont: CustomContinuation<String>): Any? {
        val scheduler = Executors.newSingleThreadScheduledExecutor()
        scheduler.schedule({
            cont.resumeWith(Result.success("arch@enterprise.internal"))
            scheduler.shutdown()
        }, 100, TimeUnit.MILLISECONDS)
        return COROUTINE_SUSPENDED
    }
}
```

#### 7.2. Practical Example: Resilient Parallel Batch-Processor
Pola produksi untuk melakukan partisi task besar, membatasi paralelisme I/O via `Semaphore`, dan menerapkan *circuit-isolated child supervision*:

```kotlin
package com.enterprise.coroutines.batch

import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.time.Instant
import java.util.concurrent.atomic.AtomicInteger

data class AuditRecord(val id: String, val payload: String)
data class IngestionResult(val id: String, val status: ProcessStatus, val timestamp: Instant)
enum class ProcessStatus { SUCCESS, FAILED_RECOVERABLE, FAILED_FATAL }

class ParallelIngestionEngine(
    private val maxConcurrency: Int = 16,
    private val timeoutPerItemMs: Long = 2000L
) {
    // Semaphore mengontrol backpressure konkurensi independen dari pool size
    private val concurrencyLimiter = Semaphore(maxConcurrency)
    private val processedCounter = AtomicInteger(0)

    suspend fun ingestBatch(
        records: List<AuditRecord>,
        dispatcher: CoroutineDispatcher = Dispatchers.IO
    ): List<IngestionResult> = supervisorScope {
        // supervisorScope mengisolasi kegagalan satu coroutine dari coroutine lainnya
        records.map { record ->
            async(dispatcher) {
                concurrencyLimiter.withPermit {
                    processSingleRecordSafely(record)
                }
            }
        }.awaitAll() // Mengumpulkan seluruh hasil tanpa melempar kegagalan parsial
    }

    private suspend fun processSingleRecordSafely(record: AuditRecord): IngestionResult {
        return try {
            withTimeout(timeoutPerItemMs) {
                // Memastikan coroutine mematuhi pembatalan kooperatif
                currentCoroutineContext().ensureActive()
                persistToStorage(record)
            }
        } catch (te: TimeoutCancellationException) {
            IngestionResult(record.id, ProcessStatus.FAILED_RECOVERABLE, Instant.now())
        } catch (ce: CancellationException) {
            // CancellationException WAJIB di-rethrow agar structured concurrency berfungsi normal
            throw ce
        } catch (e: Exception) {
            // Isolasi business exception
            IngestionResult(record.id, ProcessStatus.FAILED_FATAL, Instant.now())
        }
    }

    private suspend fun persistToStorage(record: AuditRecord): IngestionResult {
        delay(50) // Simulasi latency transmisi jaringan I/O
        processedCounter.incrementAndGet()
        return IngestionResult(record.id, ProcessStatus.SUCCESS, Instant.now())
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Desain Problem
Sebuah Payment Gateway FinTech memproses webhook transaksi inbound sebesar **15.000 transaksi/detik** pada puncak beban (*peak load*). Sistem backend sering mengalami degradasi latensi p99 (>15 detik) dan JVM crash akibat OOM.
*Akar masalah*: Implementasi lama menggunakan unconstrained `GlobalScope.launch(Dispatchers.IO)` untuk setiap webhook yang masuk. Saat downstream payment processor melambat, `Dispatchers.IO` mengembang mencapai 2000+ thread. Hal ini menyebabkan heap memory habis untuk stack thread native dan CPU *thrashing* (context-switch storm).

#### Solusi Arsitektural
Membangun *Backpressure Event Ingestion Engine* berbasis coroutine dengan spesifikasi:
1. Menghilangkan `Dispatchers.IO` unbound thread creation dengan `limitedParallelism`.
2. Menerapkan antrean asinkron berkapasitas tetap (*bounded channel*) dengan strategi `SUSPEND`.
3. Worker group terisolasi di bawah `SupervisorJob`.
4. Graceful shutdown handler yang menguras (*drain*) in-flight message saat aplikasi menerima sinyal `SIGTERM`.

```
[Inbound HTTP Request]
         │
         ▼
[Ingestion Controller] ── (Non-blocking) ──► [Buffered Channel (Capacity: 10,000)]
                                                    │
                 ┌──────────────────────────────────┴──────────────────────────────────┐
                 ▼ (Suspends ingest if full)                                           ▼
      [Worker Pool (Core: 32)]                                              [Worker Pool (Core: 32)]
 (limitedParallelism on Dispatchers.IO)                                (limitedParallelism on Dispatchers.IO)
                 │                                                                     │
                 ▼                                                                     ▼
      [Downstream Processor]                                                [Downstream Processor]
```

#### Implementasi Kode Produksi:

```kotlin
package com.enterprise.coroutines.payments

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import org.slf4j.LoggerFactory
import java.io.Closeable
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong

data class PaymentWebhookEvent(
    val transactionId: String,
    val merchantId: String,
    val amountCents: Long,
    val payloadSignature: String
)

class PaymentIngestionPipeline(
    private val channelCapacity: Int = 10_000,
    private val workerCount: Int = 32
) : Closeable {

    private val log = LoggerFactory.getLogger(javaClass)
    private val isRunning = AtomicBoolean(true)
    private val processedCounter = AtomicLong(0)

    // Isolation Dispatcher: Mencegah saturasi thread pool global IO
    private val ingestionDispatcher = Dispatchers.IO.limitedParallelism(workerCount)

    // Bounded Channel sebagai backpressure buffer penahan lonjakan trafik
    private val eventQueue = Channel<PaymentWebhookEvent>(
        capacity = channelCapacity,
        onBufferOverflow = BufferOverflow.SUSPEND
    )

    // Root scope terisolasi dengan SupervisorJob
    private val pipelineScope = CoroutineScope(
        SupervisorJob() +
        ingestionDispatcher +
        CoroutineName("PaymentPipelineScope")
    )

    init {
        log.info("Initializing $workerCount ingestion background consumers...")
        repeat(workerCount) { workerId ->
            pipelineScope.launch(CoroutineName("PaymentWorker-$workerId")) {
                startConsumerWorker(workerId)
            }
        }
    }

    /**
     * Menerima event dan menangguhkan (suspend) request HTTP jika buffer internal penuh.
     * Tidak memblokir OS thread Tomcat/Netty/Ktor.
     */
    suspend fun acceptEvent(event: PaymentWebhookEvent): Boolean {
        if (!isRunning.get()) {
            throw IllegalStateException("Payment engine is shutting down. Request rejected.")
        }
        return try {
            eventQueue.send(event) // Non-blocking suspend call
            true
        } catch (e: Exception) {
            log.error("Failed to enqueue event: ${event.transactionId}", e)
            false
        }
    }

    private suspend fun startConsumerWorker(workerId: Int) {
        // Mengonsumsi channel secara kontinu sampai di-close
        for (event in eventQueue) {
            try {
                processPaymentTransaction(event)
                processedCounter.incrementAndGet()
            } catch (ce: CancellationException) {
                log.info("Worker $workerId received cancellation. Evacuating.")
                throw ce
            } catch (e: Throwable) {
                log.error("Unhandled error processing transaction ${event.transactionId} on worker $workerId", e)
            }
        }
    }

    private suspend fun processPaymentTransaction(event: PaymentWebhookEvent) {
        // Simulasi dependensi eksternal (Settlement API / Card Networks)
        delay(15) // Suspends, no OS thread consumed
    }

    override fun close() {
        if (!isRunning.compareAndSet(true, false)) return
        log.info("Graceful shutdown initiated. Draining channel buffer...")

        runBlocking {
            // Tutup channel agar tidak ada task baru masuk
            eventQueue.close()

            // Menunggu buffer dikuras maksimal 30 detik
            val shutdownTimeout = withTimeoutOrNull(30_000L) {
                // Tunggu hingga seluruh child coroutine di pipelineScope selesai
                pipelineScope.coroutineContext[Job]?.children?.forEach { it.join() }
            }

            if (shutdownTimeout == null) {
                log.warn("Shutdown timeout reached. Forcing cancellation of active coroutines.")
                pipelineScope.cancel()
            }
        }
        log.info("Pipeline terminated safely. Total processed: ${processedCounter.get()}")
    }
}
```

---

### 9. Trade-offs

| Aspek Arsitektur | Coroutine Approach (State Machine / Virtual Dispatch) | Reactive Streams (Reactor / WebFlux) | Traditional Thread Pool (ExecutorService) |
| :--- | :--- | :--- | :--- |
| **Footprint Memori (Heap/Stack)** | Rendah (~400 bytes/coroutine instance). Efisiensi heap luar biasa. | Moderat. Setiap operator chains membuat banyak short-lived intermediate wrapper. | Sangat Tinggi (~1MB per thread stack reserved pada native JVM memory). |
| **Throughput & Context Switch Latency** | Sangat Tinggi. Pertukaran task ditangani secara internal via user-space continuation queue tanpa trap ke kernel. | Sangat Tinggi. Non-blocking IO loop langsung memanggil callback handler pipeline. | Rendah pada load tinggi akibat lock contention dan cache pollution saat kernel context switch. |
| **Debugging & Stack Tracing** | Intuitif. Stack trace terlihat imperatif/sekuensial. Debugger modern mendukung Coroutine Dump & Variable Inspection. | Sangat Buruk. Callback hell terbungkus monad operator chains. Stack trace terputus (*assembly stack trace overhead*). | Mudah. Standar tooling Java profiling (JFR, Async-profiler, VisualVM) langsung memetakan thread native. |
| **Interoperabilitas Java Legasi** | Memerlukan adapter layer (`Future.asDeferred()`, `suspendCancellableCoroutine`). | Natural untuk ekosistem Java via Reactive Streams Specification compliant API. | Native. Kompatibel secara default dengan seluruh pustaka SDK ekosistem Java. |
| **Cognitive Load & Dev Cost** | Rendah hingga Sedang. Menulis async dengan paradigma imperatif biasa. Wajib paham aturan cancellation. | Sangat Tinggi. Menuntut pemahaman mendalam tentang functional reactive paradigm (`flatMap`, `switchIfEmpty`, dsb). | Sangat Rendah. Paradigma prosedural standar yang dipahami semua level engineer. |

---

### 10. Common Mistakes & Troubleshooting

#### Mistake 1: Menelan (Swallowing) `CancellationException`
*Gejala*: Coroutine mengabaikan pembatalan HTTP request, timeout tidak bekerja, dan background worker menggantung selamanya.
*Anti-pattern*:
```kotlin
// SALAH: Menangkap Throwable atau Exception tanpa melempar kembali CancellationException
try {
    delay(5000)
} catch (e: Exception) { 
    logger.error("Error occurred", e) 
}
```
*Solusi Arsitektural*:
```kotlin
// BENAR: Re-throw CancellationException secara eksplisit
try {
    delay(5000)
} catch (ce: CancellationException) {
    throw ce
} catch (e: Exception) {
    logger.error("Error occurred", e)
}
```

#### Mistake 2: Memanggil Blocking Call di Thread Pool yang Salah
*Gejala*: Aplikasi berhenti merespons, Web server tidak dapat menerima koneksi baru (*starvation* total) padahal utilisasi CPU masih rendah.
*Penyebab*: Menjalankan operasi I/O blocking (JDBC standar, file IO) di dalam `Dispatchers.Default` (yang dialokasikan eksklusif untuk komputasi CPU-bound sejumlah CPU core).
*Solusi*: Bungkus eksekusi blocking I/O secara ketat menggunakan dispatcher khusus atau `Dispatchers.IO.limitedParallelism`:
```kotlin
val dbDispatcher = Dispatchers.IO.limitedParallelism(50) // Dedicated budget
withContext(dbDispatcher) {
    jdbcTemplate.query(...) // Aman dari saturasi thread komputasi
}
```

#### Mistake 3: Salah Meletakkan `CoroutineExceptionHandler` (CEH)
*Gejala*: Aplikasi tetap mengalami fatal crash (*uncaught exception*) meskipun CEH sudah diinisialisasi.
*Akar Masalah*: CEH hanya efektif jika dipasang pada **Root Coroutine** (dibuat via `CoroutineScope.launch`). CEH tidak memiliki efek jika dipasang pada *child coroutine* atau pada builder `async`.
*Solusi*:
```kotlin
// SALAH: CEH pada child coroutine tidak akan pernah menangkap exception
val scope = CoroutineScope(Dispatchers.Default)
scope.launch {
    // Child coroutine memasang CEH -> DIABAIKAN OLEH HIERARKI
    launch(CoroutineExceptionHandler { _, _ -> println("Caught!") }) {
        throw RuntimeException("Boom!") // Menyebabkan crash aplikasi!
    }
}

// BENAR: CEH dipasang pada root context Scope atau root builder
val handler = CoroutineExceptionHandler { _, exception ->
    println("Root caught: ${exception.message}")
}
val rootScope = CoroutineScope(Dispatchers.Default + SupervisorJob() + handler)
rootScope.launch {
    throw RuntimeException("Boom!") // Ditangkap oleh handler dengan benar
}
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Dependency Injection Dispatcher**: Jangan pernah meng-hardcode `Dispatchers.IO` atau `Dispatchers.Default` langsung di dalam layer domain/repository. Inject abstraksi dispatcher untuk mempermudah parallel testing (*testability* menggunakan `StandardTestDispatcher`).
- [ ] **Limit Parallelism on Shared Dispatchers**: Gunakan `Dispatchers.IO.limitedParallelism(n)` untuk membatasi traffic ke downstream external service yang rentan mengalami *overwhelmed*, sekaligus mencegah starvation pada aplikasi lokal.
- [ ] **Always Provide SupervisorJob for Services**: Pastikan Service/Manager level lifecycle menggunakan `SupervisorJob()` agar kegagalan transient pada satu task consumer tidak merusak seluruh sistem (*cascading failure*).
- [ ] **Never Use GlobalScope**: Hindari `GlobalScope`. Gunakan explicit `CoroutineScope` yang terikat pada application lifecycle framework (misal: Spring Bean lifecycle, Ktor Application lifecycle).
- [ ] **Cooperative Cancellation Checkpoints**: Tambahkan pengecekan `ensureActive()` atau `yield()` di dalam loop iterasi komputasi yang intensif untuk menjamin coroutine responsif terhadap sinyal terminasi.
- [ ] **Non-Cancellable Resource Teardown**: Selalu gunakan `withContext(NonCancellable)` di dalam blok `finally` jika blok tersebut mengeksekusi operasi penutupan berbasis suspend function (misal: flushing buffer ke database).

---

### 12. Hands-on Practice

Buatlah direktori praktikum lokal pada struktur path berikut:
`hands-on/m02/`

#### Struktur Proyek:
```text
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── kotlin/
            └── com/enterprise/resilience/
                ├── CircuitState.kt
                └── ResilientTaskExecutor.kt
```

#### Langkah 1: Siapkan `build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm") version "1.9.22"
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
    testImplementation(kotlin("test"))
}

application {
    mainClass.set("com.enterprise.resilience.ResilientTaskExecutorKt")
}
```

#### Langkah 2: Buat State Engine `hands-on/m02/src/main/kotlin/com/enterprise/resilience/CircuitState.kt`
```kotlin
package com.enterprise.resilience

enum class CircuitState { CLOSED, OPEN, HALF_OPEN }
```

#### Langkah 3: Implementasi Executor `hands-on/m02/src/main/kotlin/com/enterprise/resilience/ResilientTaskExecutor.kt`
Ketik kode lengkap di bawah ini:

```kotlin
package com.enterprise.resilience

import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.util.concurrent.atomic.AtomicInteger

class CoroutineCircuitBreaker(
    private val failureThreshold: Int = 3,
    private val resetTimeoutMs: Long = 2000L
) {
    private val mutex = Mutex()
    var state: CircuitState = CircuitState.CLOSED
        private set
    private var failureCount = 0
    private var lastFailureTime = 0L

    suspend fun <T> execute(block: suspend () -> T): T {
        mutex.withLock {
            if (state == CircuitState.OPEN) {
                if (System.currentTimeMillis() - lastFailureTime > resetTimeoutMs) {
                    println("[CircuitBreaker] Timeout expired. Moving to HALF_OPEN state.")
                    state = CircuitState.HALF_OPEN
                } else {
                    throw IllegalStateException("Circuit is OPEN. Fast-failing execution.")
                }
            }
        }

        return try {
            val result = block()
            mutex.withLock {
                if (state == CircuitState.HALF_OPEN) {
                    println("[CircuitBreaker] Success in HALF_OPEN. Resetting to CLOSED.")
                    state = CircuitState.CLOSED
                    failureCount = 0
                }
            }
            result
        } catch (ce: CancellationException) {
            throw ce // Tetap alirkan pembatalan coroutine
        } catch (t: Throwable) {
            mutex.withLock {
                lastFailureTime = System.currentTimeMillis()
                failureCount++
                println("[CircuitBreaker] Failure recorded: ${t.message} (Count: $failureCount)")
                if (failureCount >= failureThreshold || state == CircuitState.HALF_OPEN) {
                    state = CircuitState.OPEN
                    println("[CircuitBreaker] Threshold reached! State changed to OPEN.")
                }
            }
            throw t
        }
    }
}

fun main() = runBlocking {
    val breaker = CoroutineCircuitBreaker(failureThreshold = 2, resetTimeoutMs = 1000L)
    val counter = AtomicInteger(0)

    val unstableService: suspend () -> String = {
        val attempt = counter.incrementAndGet()
        if (attempt in 1..2) {
            throw RuntimeException("Network down (Attempt $attempt)")
        }
        "Service Success Payload (Attempt $attempt)"
    }

    // Melakukan pengujian eksekusi
    repeat(5) { i ->
        try {
            val res = breaker.execute { unstableService() }
            println("Request $i Succeeded: $res")
        } catch (e: Exception) {
            println("Request $i Failed with: ${e.message}")
        }
        delay(300)
    }

    println("\nSleeping for 1.2s to trigger circuit recovery timeout...")
    delay(1200)

    try {
        val res = breaker.execute { unstableService() }
        println("Recovery Request Succeeded: $res")
    } catch (e: Exception) {
        println("Recovery Request Failed with: ${e.message}")
    }
}
```

---

### 13. Exercise

#### Level 1 (Easy):
Implementasikan utility function `executeWithGuaranteedCleanup` yang mengeksekusi operasi suspend berisiko gagal/dibatalkan. Gunakan `withContext(NonCancellable)` pada blok penutupan sumber daya untuk memastikan logging persistensi audit ke database/file selalu tereksekusi tanpa terputus, meskipun coroutine pemanggil di-cancel di tengah jalan.

#### Level 2 (Medium):
Buatlah rate-limiter asinkron tanpa memblokir thread menggunakan `Mutex` dan token-bucket algorithm berbasis coroutine. Rate limiter harus menerima fungsi lambda `suspend () -> T` dan menangguhkan pemanggilan jika kuota token per detik habis, tanpa menggunakan method thread blocking seperti `Thread.sleep()`.

#### Level 3 (Hard):
Rancang *Saga Orchestrator Engine* berbasis structured concurrency. Engine harus mendukung eksekusi multi-step compensation actions:
- Menerima 3 step operasi (`suspend () -> StepResult`).
- Setiap step memiliki kompensasi balik (`suspend () -> Unit`).
- Jika step 3 gagal, engine harus secara otomatis membatalkan step 3, mengeksekusi kompensasi step 2, lalu kompensasi step 1 secara berurutan (*reverse order*) di bawah context `NonCancellable`, serta merekonstruksi audit-trail log kegagalan secara deterministik.

---

### 14. Challenge

**Skenario Kasus Kompleks**: Rancang sebuah *Distributed Change-Data-Capture (CDC) Ingestion Worker* untuk mengonsumsi transaksi keuangan dari cluster event stream (simulasi) dengan toleransi kegagalan ekstrem:

**Kebutuhan Sistem**:
1. Worker memproses event secara streaming menggunakan `Channel` Kotlin dengan kapasitas buffer yang ditentukan.
2. Setiap transaksi harus divalidasi ke 3 service eksternal (Fraud Service, Balance Service, Identity Service) secara paralel menggunakan `async`.
3. Jika Fraud Service merespons dengan indikasi "High Risk", batalkan secara instan evaluasi pada Balance Service dan Identity Service yang sedang berjalan untuk menghemat CPU & IO (Gunakan *cooperative explicit cancellation*).
4. Sediakan mekanisme *Dynamic Backpressure Regulation*: Jika waktu rata-rata pemrosesan melampaui SLA 500ms, turunkan throughput pembacaan event secara otomatis menggunakan dynamic delay rate tanpa menjatuhkan node worker.
5. Saat aplikasi menerima sinyal interupsi runtime shutdown (`Runtime.getRuntime().addShutdownHook`), engine wajib menguras seluruh pesan yang saat itu sudah berada di antrean buffer lokal, menyimpannya ke persistensi cadangan (*evacuation sink*), dan mematikan semua coroutine worker secara aman maksimal dalam waktu 5 detik.

*Kirimkan solusi lengkap dalam bentuk unit test yang memvalidasi kondisi starvation-free, thread safety, dan graceful shutdown invariants.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. Apa arti teknis dari istilah *Stackless Coroutine* pada runtime Kotlin?
   - A. Coroutine tidak menggunakan memori sama sekali di JVM.
   - B. Coroutine tidak mengalokasikan stack frame native thread OS saat ditangguhkan, melainkan menyimpan state machine di Java Heap.
   - C. Coroutine selalu berjalan di atas stack memory milik OS thread utama.
   - D. Fungsi suspend hanya bisa dipanggil di dalam fungsi non-suspend.

2. Konstanta sentinel apa yang dikembalikan oleh state machine internal ketika fungsi suspend belum menyelesaikan operasinya secara sinkron?
   - A. `null`
   - B. `Unit`
   - C. `kotlin.coroutines.intrinsics.COROUTINE_SUSPENDED`
   - D. `CompletableFuture.COMPLETED`

3. Apa perbedaan utama antara `launch` dan `async` builder?
   - A. `launch` mengembalikan `Job` (fire-and-forget), sedangkan `async` mengembalikan `Deferred<T>` yang membawa nilai kembalian melalui method `await()`.
   - B. `async` berjalan di thread pool terpisah, sedangkan `launch` tidak.
   - C. `launch` otomatis menangani exception, sedangkan `async` tidak bisa error.
   - D. `async` tidak mendukung structured concurrency.

4. Manakah elemen context yang berfungsi untuk mencegat (*intercept*) eksekusi continuation dan memindahkannya ke pool thread tertentu?
   - A. `Job`
   - B. `CoroutineName`
   - C. `ContinuationInterceptor` / `CoroutineDispatcher`
   - D. `CoroutineExceptionHandler`

5. Apa yang terjadi jika kode Anda menangkap `CancellationException` dan tidak melemparnya kembali?
   - A. Coroutine langsung berhenti lebih cepat.
   - B. Mekanisme cooperative cancellation terputus; coroutine induk tidak tahu bahwa child telah diminta berhenti, berisiko menyebabkan memory leak dan background task menggantung.
   - C. JVM akan langsung melempar `OutOfMemoryError`.
   - D. Thread OS yang menjalankan coroutine akan mati seketika.

#### Bagian 2: Intermediate (5 Soal)
6. Diberikan kode: `val job = SupervisorJob(); CoroutineScope(Dispatchers.Default + job).launch { launch { throw Exception("Error") } }`. Apa efek exception tersebut pada lifecycle parent scope?
   - A. Seluruh CoroutineScope hancur dan mati permanen.
   - B. Parent scope tetap aktif karena kegagalan ditahan di child level berkat `SupervisorJob`.
   - C. Terjadi dead-lock seketika.
   - D. `job` secara otomatis membatalkan seluruh coroutine lain yang terdaftar sebelum error.

7. Mengapa penggunaan `withContext(Dispatchers.IO)` di dalam loop beriterasi jutaan kali dapat menyebabkan degradasi performa dibanding mendesain loop di luar `withContext`?
   - A. Karena `Dispatchers.IO` tidak mendukung loop.
   - B. Karena setiap transisi `withContext` memicu alokasi frame context switching, interupsi dispatcher, dan pembuatan wrapper continuation baru.
   - C. Karena loop otomatis mengubah coroutine menjadi thread native blocking.
   - D. Karena `withContext` mengunci heap memory secara permanen.

8. Apa perbedaan mendasar antara `Dispatchers.Default` dan `Dispatchers.IO` pada Kotlin Coroutines runtime?
   - A. Keduanya menggunakan thread pool yang terpisah total dan tidak pernah berbagi thread.
   - B. Keduanya didukung oleh `CoroutinesScheduler` yang sama, namun `Dispatchers.Default` dibatasi sejumlah CPU core untuk task CPU-bound, sedangkan `Dispatchers.IO` mengizinkan elastisitas thread tambahan untuk task blocking I/O.
   - C. `Dispatchers.IO` tidak mendukung cooperative cancellation.
   - D. `Dispatchers.Default` hanya dialokasikan untuk operasi GUI/Main thread.

9. Kapan sebuah Job berada dalam state `Completing`?
   - A. Saat `cancel()` dipanggil.
   - B. Saat badan kodenya sendiri telah selesai dieksekusi, namun ia masih menunggu seluruh child coroutines yang dinaunginya menyelesaikan eksekusi mereka.
   - C. Tepat sebelum coroutine mulai dieksekusi oleh dispatcher.
   - D. Ketika terjadi exception yang belum ditangani.

10. Apa kegunaan utama dari method `Dispatchers.IO.limitedParallelism(x)` yang diperkenalkan pada coroutines versi modern?
    - A. Memaksa pembagian thread secara fisik menjadi CPU core baru.
    - B. Membuat dispatcher view baru dengan batasan konkurensi independen tanpa membuat thread pool baru, mencegah saturasi berlebih pada downstream service tertentu.
    - C. Mengubah I/O non-blocking menjadi blocking.
    - D. Menjamin eksekusi berlangsung secara single-threaded eksklusif di main thread.

#### Bagian 3: Production Case Scenarios (3 Soal)
11. **Skenario 1**: Sebuah sistem order service menggunakan `coroutineScope { ... }` untuk mengeksekusi dua operasi paralel: `val p = async { pay() }` dan `val i = async { reserveInventory() }`. Di tengah jalan, method `pay()` melempar exception `PaymentGatewayException`. Apa yang terjadi pada operasi `reserveInventory()`?
    - A. `reserveInventory()` tetap berjalan sampai selesai, mengabaikan kegagalan payment.
    - B. `coroutineScope` segera membatalkan child coroutine lainnya (`reserveInventory()`), membatalkan dirinya sendiri, dan melempar kembali `PaymentGatewayException` ke pemanggil.
    - C. Sistem memasuki infinite loop menunggu hasil dari `reserveInventory()`.
    - D. `PaymentGatewayException` otomatis ditelan dan `p` mengembalikan nilai `null`.

12. **Skenario 2**: Anda mengamati bahwa proses migrasi data batch besar mengalami kebocoran memori (OutOfMemoryError: Direct Buffer Memory) saat membaca dan menulis data ke cloud bucket. Kode menggunakan coroutine dengan peluncuran task tak terbatas: `items.forEach { scope.launch(Dispatchers.IO) { upload(it) } }`. Apa penyebab utama dan perbaikan arsitektural yang paling tepat?
    - A. Kurang memori RAM; tingkatkan heap flag JVM `-Xmx`.
    - B. `Dispatchers.IO` rusak; ganti ke `Dispatchers.Default`.
    - C. Unbounded concurrency; ribuan coroutine berjalan simultan dan membebani network socket buffer native. Gunakan bounded `Channel`, `Semaphore`, atau `limitedParallelism` untuk membatasi task in-flight.
    - D. Coroutine tidak mendukung upload data; ganti ke sequential Java Streams.

13. **Skenario 3**: Sebuah REST endpoint menerima request HTTP, lalu memanggil suspend function `updateUserProfile()`. Saat koneksi HTTP terputus tiba-tiba (client cancel request), server membatalkan coroutine. Namun, Anda mendapati audit-trail database di blok `finally { auditService.logCancel() }` tidak pernah tercatat di database. Mengapa?
    - A. Method `finally` pada Kotlin tidak didukung jika coroutine di-cancel.
    - B. Coroutine yang sudah di-cancel berada dalam state `Cancelling`, sehingga pemanggilan suspend function `auditService.logCancel()` di dalam blok `finally` langsung gagal melempar `CancellationException` berikutnya. Harus dibungkus dengan `withContext(NonCancellable)`.
    - C. Database JDBC otomatis me-rollback connection pool saat client disconnect.
    - D. Structured concurrency otomatis menghapus seluruh data audit log yang belum di-commit.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** - Stackless coroutine tidak mengalokasikan memori stack OS thread per unit eksekusi, melainkan menyimpan frame dan variabel lokal pada object continuation di heap.
2. **C** - `COROUTINE_SUSPENDED` adalah penanda internal runtime bahwa fungsi telah menangguhkan eksekusi dan belum menghasilkan nilai saat itu juga.
3. **A** - `launch` menghasilkan `Job` tanpa membawa nilai return, sementara `async` menghasilkan `Deferred<T>` yang mengizinkan pemanggilan `.await()`.
4. **C** - `ContinuationInterceptor` (yang merupakan basis dari `CoroutineDispatcher`) bertugas mencegat kelanjutan task dan menjadwalkannya ke thread tertentu.
5. **B** - Menelan `CancellationException` merusak contract structured concurrency dan menyebabkan coroutine gagal dihentikan secara kooperatif.

#### Bagian 2: Intermediate
6. **B** - `SupervisorJob` mendefinisikan batas supervisi di mana kegagalan child tidak merambat ke parent maupun ke sibling coroutine lainnya.
7. **B** - Memasuki dan keluar dari context boundary berulang kali di dalam tight loop menciptakan alokasi objek heap dan overhead scheduling task yang signifikan.
8. **B** - Keduanya berjalan di atas scheduler work-stealing pool yang sama, namun `Dispatchers.IO` diizinkan mengalokasikan thread tambahan melebihi core CPU untuk mengakomodasi blocking waiting.
9. **B** - State `Completing` adalah fase internal di mana body coroutine telah selesai, namun ia menangguhkan finalisasi akhir sampai seluruh anak-anaknya selesai bekerja.
10. **B** - `limitedParallelism` membuat logical view scheduler baru untuk mengontrol batas konkurensi secara deterministik tanpa membuat thread pool OS baru.

#### Bagian 3: Production Case Scenarios
11. **B** - Berbeda dengan `supervisorScope`, standard `coroutineScope` mematuhi aturan fail-fast: jika salah satu child melempar exception, scope membatalkan seluruh sibling coroutine yang sedang berjalan.
12. **C** - Membuka koneksi I/O yang tidak terbatas menyebabkan exhaustion pada native memory buffers (epoll/socket channels). Pembatasan concorrency via `Semaphore` atau `limitedParallelism` adalah solusi arsitektural wajib.
13. **B** - Coroutine yang telah dibatalkan tidak dapat memanggil fungsi suspend baru tanpa context `NonCancellable`, karena ia akan langsung melempar `CancellationException` kembali pada suspension point pertama di dalam `finally`.

---

### 16. Summary

1. **State Machine & Bytecode Transformation**: Pemahaman mendalam tentang Continuation Passing Style (CPS) membuktikan bahwa Kotlin Coroutines bukanlah "thread ringan ajaib", melainkan optimasi compiler tingkat tinggi yang merepresentasikan alur sekuensial menjadi serangkaian *callback state machine* di atas Java Heap.
2. **Structured Concurrency Invariants**: Struktur pohon hierarki (`Job` hierarchy) menjamin kepastian siklus hidup, pembatalan terpadu, dan pencegahan *leaked background jobs*. Penggunaan scope boundary (`coroutineScope` vs `supervisorScope`) harus didasarkan pada strategi isolasi error domain.
3. **Hardware & Resource Efficiency**: Melalui arsitektur non-blocking CPS, ribuan operasi konkuren dapat dieksekusi dengan footprint memori sangat minim, asalkan thread boundaries dijaga secara ketat menggunakan isolasi dispatcher (`limitedParallelism`) dan cooperative cancellation dipatuhi tanpa menelan `CancellationException`.