# Kurikulum Enterprise Kotlin: Modul 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Fokus:** Transisi Paradigma OOP Idiomatis Lanjutan menuju Asynchronous Flow & Reactive Streams

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Principal Engineer/Architect diharapkan mampu:
*   **Mendesain Domain Core Bebas Alokasi (Zero/Low Allocation):** Menerapkan *value classes* (`@JvmInline`), *sealed interfaces*, dan *declaration-site variance* (`in`/`out`) untuk memodelkan Domain-Driven Design (DDD) yang *type-safe* secara ketat di tingkat *bytecode*.
*   **Menguasai Dekonstruksi Bytecode Kotlin:** Menganalisis hasil dekompilasi JVM bytecode terkait *class delegation*, *continuation-passing style* (CPS), dan *synthetic method generation* guna memprediksi *performance overhead* dan *memory footprint*.
*   **Mengorkestrasi Asynchronous Pipeline Tingkat Enterprise:** Membangun *streaming pipeline* reaktif berkecepatan tinggi menggunakan Kotlin Asynchronous `Flow`, `SharedFlow`, dan `StateFlow` dengan penanganan *backpressure* deterministik.
*   **Menerapkan Invariant Context Preservation:** Mengisolasi *execution context* secara aman menggunakan operator `flowOn` tanpa melanggar batasan konkurensi terstruktur (*structured concurrency*).
*   **Mendeteksi & Memitigasi Regresi Produksi:** Mendiagnosis *coroutine starvation*, *unintended object boxing*, *memory leaks* pada *hot streams*, dan anomali *thread scheduling* pada JVM runtime.

---

## 2. Prerequisites

*   **JVM Internals:** Pemahaman mendalam tentang JVM Memory Model (Stack, Heap, Metaspace), JIT Compilation, Safepoints, dan eksekusi Bytecode.
*   **Konkurensi Dasar:** Familiaritas dengan POSIX threads, Java Memory Model (`volatile`, atomics, synchronized blocks), dan non-blocking I/O (NIO).
*   **Kotlin Core:** Penguasaan fungsi dasar coroutine (`launch`, `async`, `suspendCoroutineUninterceptedOrReturn`), extension functions, dan lambda dengan receiver.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Idiomatic OOP: Bytecode-Level Anatomy

#### A. Sealed Interfaces vs Sealed Classes (JVM Representation)
Kotlin mengompilasi `sealed hierarchy` menjadi pola *restricted inheritance*. 

*   **Java 15+ Target:** Kotlin compiler (mulai versi 1.5+) memetakan `sealed interface` langsung ke atribut bytecode `PermittedSubclasses` pada Java Virtual Machine.
*   **Java 8 Target:** Compiler menghasilkan konstruktor *package-private* sintetis (`Synthetic`) atau konstruktor dengan argumen penanda `DefaultConstructorMarker` bertipe private, mencegah instansiasi dari luar kompilasi unit.

```kotlin
// Source Kotlin
sealed interface DomainEvent
@JvmInline value class OrderId(val raw: String)
data class OrderCreated(val id: OrderId) : DomainEvent
```

*Dekompilasi Representasi Bytecode (Konseptual Java Equivalent):*
```java
// Bytecode Java representation
public interface DomainEvent {
    // Pada Java 17+: PermittedSubclasses: OrderCreated.class
}

public final class OrderCreated implements DomainEvent {
    private final String id; // Type unboxed di boundary tertentu

    public OrderCreated(String id) {
        this.id = id;
    }
    public final String getId() { return this.id; }
    // equals, hashCode, toString otomatis dibuat compiler
}
```

#### B. `@JvmInline value class` Internals
Value class dirancang untuk menghilangkan alokasi heap dengan merepresentasikan tipe domain yang kuat (*strongly typed*) secara langsung sebagai tipe primitif atau referensi objek dasarnya di stack frame.

*   **Name Mangling:** Untuk mencegah konflik overload fungsi yang menerima tipe pembungkus vs tipe dasar, compiler Kotlin menerapkan teknik *name mangling*. Fungsi `fun process(id: OrderId)` akan dikompilasi menjadi `process-xxxx(String id)`.
*   **Unintended Boxing Triggers:** Boxing ke heap terjadi jika:
    1.  Value class digunakan sebagai argumen bertipe generik: `List<OrderId>`.
    2.  Value class di-cast ke tipe interface: `val event: DomainEvent = OrderCreated(OrderId("123"))`.
    3.  Value class digunakan sebagai tipe nullable: `OrderId?`.

#### C. Class & Property Delegation (`by`)
Pola delegasi *first-class* (`class ServiceImpl : Service by delegate`) mengeliminasi boilerplate *decorator pattern*. Di tingkat bytecode, compiler menginisialisasi *synthetic field* privat yang merujuk pada objek target dan menghasilkan *forwarding methods* yang memanggil instruksi `INVOKEINTERFACE` atau `INVOKEVIRTUAL` secara langsung tanpa refleksi.

Pada *Property Delegation*, instansiasi `KProperty<*>` dibuat via objek static metadata untuk mengeksekusi metode `getValue` dan `setValue`.

---

### 3.2 Kotlin Asynchronous Flow Architecture

Berbeda dengan Reactive Streams klasik (Project Reactor / RxJava) yang berbasis pada model *callback-driven* dan state machine internal yang kompleks dengan ratusan alokasi operator, Kotlin `Flow` dibangun langsung di atas arsitektur **Coroutines Continuations**.

#### A. The Continuation-Passing Style (CPS) State Machine
Setiap *suspending function* dan operator Flow diubah oleh compiler Kotlin menjadi sebuah state machine yang mengimplementasikan antarmuka `Continuation<T>`.

```
                    ┌────────────────────────────────────────┐
                    │          Caller (CoroutineScope)       │
                    └───────────────────┬────────────────────┘
                                        │ invoke
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │            FlowCollector.emit(value)                │
             │           (Suspension Point: State 0)               │
             └──────────────────────────┬──────────────────────────┘
                                        │ Suspend / Resume
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │             Transformations (map/filter)            │
             │           (Suspension Point: State 1)               │
             └──────────────────────────┬──────────────────────────┘
                                        │
                                        ▼
             ┌─────────────────────────────────────────────────────┐
             │                 Terminal Operator                   │
             │                  (Completion/State n)               │
             └─────────────────────────────────────────────────────┘
```

#### B. Cold Flow vs Hot Flow Internals
*   **Cold Flow (`flow { ... }`):** Mengimplementasikan antarmuka fungsional `Flow<T>` murni yang hanya memiliki satu fungsi: `suspend fun collect(collector: FlowCollector<T>)`. Kode di dalam blok *producer* tidak akan dieksekusi sebelum ada pemanggilan `collect()`. Setiap pemanggilan `collect()` mengeksekusi pipeline baru dari awal di thread pemanggil (kecuali ada dispatching eksplisit).
*   **Hot Streams (`SharedFlow` & `StateFlow`):** Mengabaikan status keberadaan *subscriber*. Nilai diproduksi tanpa menunggu pemanggilan `collect()`.
    *   `SharedFlowImpl`: Menggunakan *ring buffer* berbasis array melingkar (`Object[]`). Pengiriman data (*emit*) menggunakan lock non-blocking (`synchronized(this)` minimal/fast-path) untuk memanipulasi pointer `head`, `tail`, dan array slot `subscribers`.
    *   `StateFlowImpl`: Merupakan spesialisasi berkinerja tinggi dari `SharedFlow` dengan buffer tetap berukuran 1 (`replay = 1`) yang menggunakan instruksi `AtomicReference` compare-and-swap (CAS) untuk menjamin pembaruan nilai selalu *conflated* (hanya nilai terbaru yang dipertahankan).

#### C. Context Preservation & Exception Transparency
Arsitektur Flow memaksakan dua hukum fundamental:
1.  **Context Preservation Invariant:** Eksekusi emit dari Flow WAJIB dilakukan dalam `CoroutineContext` yang sama dengan pemanggil `collect()`. Emisi dari `withContext(Dispatchers.IO)` di dalam blok pembangun flow dilarang secara desain dan akan melempar `IllegalStateException` melalui `SafeCollector`. Untuk mengubah thread eksekusi hulu (*upstream*), pengembang wajib menggunakan operator `flowOn`.
2.  **Exception Transparency:** Eksekusi hulu tidak boleh menangkap (*swallow*) kegagalan yang terjadi di hilir (*downstream*). Blok `catch` pada Flow hanya menangani exception yang mengalir dari operator di atasnya.

---

## 4. Why & What

| Dimensi | OOP Klasik (Java/Legacy Style) | Idiomatic Reactive (RxJava / Reactor) | Idiomatic Kotlin (Coroutines + Flow) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Thread-per-request / Blocking I/O | Non-blocking / Callback Chains | Direct-style Sequential Suspending / Flow |
| **Abstraksi Tipe** | Open Classes, Mutabilitas Tinggi, Nullability rawan | Disposable, Observable, Single, Completable | Value Classes, Sealed Hierarchies, Null-Safety |
| **Alokasi Heap** | Tinggi (Wrapper objects, Defensive copies) | Sangat Tinggi (Pipeline wrappers, Subscriber nodes) | Sangat Rendah (Unboxed values, State Machine reuse) |
| **Backpressure** | Queue berbasis blocking (Thread starvation) | Spesifikasi Reactive Streams (Request `n`) | Penangguhan Alami (*Suspension-based Backpressure*) |
| **Debugging** | Stack trace linier, mudah diinspeksi | Stack trace terputus, butuh hook khusus | Coroutine Debugger, Preserved Stack-traces |

*   **Mengapa Menggunakan Arsitektur Ini?** Sistem terdistribusi modern membutuhkan *throughput* tinggi tanpa mengorbankan stabilitas memori. Kotlin Flow memadukan keunggulan paradigma deklaratif reaktif dengan keterbacaan kode sekuensial prosedural, meminimalkan *thread-context-switch cost* melalui *lightweight cooperative multitasking*.

---

## 5. How (Workflow Detail)

Arsitektur produksi mengalirkan data mentah dari jaringan melalui serangkaian transformasi tipe aman, validasi domain, hingga persistensi:

```
[Inbound Network Stream (gRPC/Kafka/Socket)]
                     │
                     ▼
       [Raw Ingestion / Deserialization]
                     │  (Flow.map / Byte to Domain Event)
                     ▼
        [Domain Invariant Validation]
                     │  (Value Classes & Sealed Hierarchy)
                     ▼
         [Backpressure Boundary]
                     │  (buffer(Channel.BUFFERED) / conflate)
                     ▼
          [Upstream Offloading]
                     │  (flowOn(Dispatchers.Default))
                     ▼
       [State Synchronization / Fan-out]
                     │  (shareIn / stateIn)
                     ▼
[Persistence / Outbound RPC Layer (Collector)]
```

1.  **Ingestion:** Data mentah masuk melalui stream asinkron (misalnya driver database R2DBC atau Kafka consumer).
2.  **Transformation & Typing:** Parsing payload ke tipe primitif, lalu dibungkus menggunakan *value classes* zero-allocation untuk mencegah kesalahan pertukaran parameter.
3.  **Boundary & Dispatching:** Menggunakan `flowOn` untuk memastikan transformasi CPU-bound tidak memblokir dispatcher I/O atau Main UI thread.
4.  **Buffering Strategy:** Mengatur strategi degradasi jika emisi downstream lebih lambat daripada laju upstream via operator `buffer()`, `conflate()`, atau penolakan eksplisit (`onBufferOverflow = BufferOverflow.DROP_OLDEST`).
5.  **State Materialization:** Aliran dingin (*cold*) dielevasi ke status panas (*hot*) via `stateIn` untuk konsumsi multi-komponen tanpa trigger eksekusi ganda.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Perpipaan Hidraulik Cerdas dengan Katup Pneumatik

*   **OOP Tradisional:** Seperti kurir fisik yang membawa satu kotak dokumen. Jika dokumen bertambah banyak, Anda harus menambah kurir baru (Thread baru), yang akhirnya menyebabkan kemacetan total di lorong kantor (OS Thread Exhaustion).
*   **Kotlin Flow:** Sistem perpipaan hidraulik otomatis.
    *   **Cold Flow:** Pipa yang katup utamanya belum dibuka. Air (data) tidak mengalir sampai penampung akhir memasang keran dan memutarnya (`collect`).
    *   **Backpressure Suspended:** Jika penampung akhir penuh, tekanan balik (*backpressure*) secara mekanis menahan katup hulu agar berhenti memompa secara instan, tanpa menumpahkan air ke lantai (tanpa *OutOfMemoryError*).
    *   **Value Classes:** Dokumen yang dicap menggunakan stensil transparan langsung di atas kertas tanpa perlu dimasukkan ke dalam map tebal (tanpa alokasi wrapper di memori heap).

### Diagram Alur Konkurensi & Memory Barrier

```
Coroutines Context Preservation Boundary
┌────────────────────────────────────────────────────────────────────────┐
│ Producer Context: Dispatchers.IO                                       │
│                                                                        │
│  flow {                                                                │
│      emit(OrderId("TX-001")) ──► [SafeCollector]                       │
│  }.flowOn(Dispatchers.IO)                  │ Context check & dispatch │
└────────────────────────────────────────────┼───────────────────────────┘
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Buffer & Suspension Queue: Channel (Capacity = 64, DROP_OLDEST/SUSPEND)│
└────────────────────────────────────────────┬───────────────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Downstream Consumer Context: Dispatchers.Default                       │
│                                                                        │
│  pipeline.collect { orderId ->                                         │
│      executeDomainLogic(orderId)                                       │
│  }                                                                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Type Variance, Delegation, dan Cold Flow

Contoh ini mendemonstrasikan kombinasi *declaration-site variance*, *property delegation*, dan *suspension mechanics*.

```kotlin
package com.enterprise.core.simple

import kotlin.properties.ReadOnlyProperty
import kotlin.reflect.KProperty
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking

// 1. Declaration-site variance: Covariant Source
interface EventSource<out T> {
    fun produce(): T
}

// 2. Custom Property Delegate untuk Audit Log
class AuditLoggingDelegate<T>(private val initialValue: T) : ReadOnlyProperty<Any?, T> {
    override fun getValue(thisRef: Any?, property: KProperty<*>): T {
        println("[AUDIT LOG] Akses properti '${property.name}' pada ${thisRef?.javaClass?.simpleName}")
        return initialValue
    }
}

// 3. Simple Suspended Cold Flow
fun generateEvents(): Flow<String> = flow {
    for (i in 1..3) {
        kotlinx.coroutines.delay(10) // Non-blocking delay
        emit("Event-$i")
    }
}

fun main() = runBlocking {
    val systemVersion: String by AuditLoggingDelegate("v2.1.0-ENTERPRISE")
    println("Booting System: $systemVersion")

    val eventFlow = generateEvents()
    println("Flow didefinisikan, emisi belum berjalan...")
    
    eventFlow.collect { value ->
        println("Consumed: $value")
    }
}
```

### 7.2 Practical Example: Enterprise Reactive Transaction Engine

Implementasi pipeline finansial modular dengan domain berbasis Sealed Interfaces, zero-allocation Value Classes, state-handling non-blocking, serta isolasi dispatcher berstandar industri.

```kotlin
package com.enterprise.finance.engine

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.*
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

// ==========================================
// 1. DOMAIN LAYER (Zero-Allocation Modeling)
// ==========================================

@JvmInline
value class AccountId(val value: String) {
    init {
        require(value.isNotBlank()) { "AccountId tidak boleh kosong" }
    }
}

@JvmInline
value class TransactionId(val value: UUID)

sealed interface FinancialEvent {
    val transactionId: TransactionId
    val timestamp: Instant

    data class AuthorizationRequested(
        override val transactionId: TransactionId,
        val accountId: AccountId,
        val amount: BigDecimal,
        override val timestamp: Instant = Instant.now()
    ) : FinancialEvent

    data class SettlementCompleted(
        override val transactionId: TransactionId,
        val executionFee: BigDecimal,
        override val timestamp: Instant = Instant.now()
    ) : FinancialEvent

    data class TransactionFailed(
        override val transactionId: TransactionId,
        val reason: String,
        override val timestamp: Instant = Instant.now()
    ) : FinancialEvent
}

// ==========================================
// 2. INFRASTRUCTURE & METRICS ABSTRACTION
// ==========================================

interface TelemetryRegistry {
    fun recordLatency(operation: String, durationMs: Long)
    fun incrementCounter(metric: String)
}

class ProductionTelemetry : TelemetryRegistry {
    override fun recordLatency(operation: String, durationMs: Long) {
        // Output format disesuaikan dengan parsing log metrics OpenTelemetry/Prometheus
        println("[METRIC:LATENCY] $operation: ${durationMs}ms [Thread: ${Thread.currentThread().name}]")
    }

    override fun incrementCounter(metric: String) {
        println("[METRIC:COUNT] $metric++")
    }
}

// ==========================================
// 3. ENGINE IMPLEMENTATION
// ==========================================

class ReactiveTransactionEngine(
    private val telemetry: TelemetryRegistry,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
    private val computeDispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    // Inbound buffer: Menangani lonjakan traffic dengan menjatuhkan pesan terlama jika subscriber lambat
    private val _eventBus = MutableSharedFlow<FinancialEvent>(
        replay = 0,
        extraBufferCapacity = 1024,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    val eventBus: SharedFlow<FinancialEvent> = _eventBus.asSharedFlow()

    suspend fun publish(event: FinancialEvent) {
        val success = _eventBus.tryEmit(event)
        if (!success) {
            _eventBus.emit(event) // Suspend fallback jika buffer jenuh
        }
        telemetry.incrementCounter("events.published")
    }

    // High-performance streaming pipeline
    fun processAuthorizations(): Flow<FinancialEvent> {
        return eventBus
            .filterIsInstance<FinancialEvent.AuthorizationRequested>()
            .map { auth ->
                // Pindah ke context komputasi untuk enkripsi / validasi matematika intensif
                withContext(computeDispatcher) {
                    validateBusinessRules(auth)
                }
            }
            .flowOn(computeDispatcher) // Hulu berjalan pada Worker threads
            .map { event ->
                // Eksekusi I/O: Ledger mutation ke persistence layer
                persistToLedger(event)
            }
            .flowOn(ioDispatcher) // Operasi persistensi dialihkan ke I/O threads
            .catch { ex ->
                telemetry.incrementCounter("pipeline.errors")
                emit(
                    FinancialEvent.TransactionFailed(
                        transactionId = TransactionId(UUID.randomUUID()),
                        reason = "Pipeline crash: ${ex.message}"
                    )
                )
            }
    }

    private fun validateBusinessRules(auth: FinancialEvent.AuthorizationRequested): FinancialEvent {
        val start = System.currentTimeMillis()
        return try {
            if (auth.amount <= BigDecimal.ZERO) {
                FinancialEvent.TransactionFailed(auth.transactionId, "Nilai transaksi tidak valid")
            } else if (auth.amount > BigDecimal("1000000.00")) {
                FinancialEvent.TransactionFailed(auth.transactionId, "Melampaui batas batas AML")
            } else {
                // Return event baru untuk downstream
                FinancialEvent.SettlementCompleted(
                    transactionId = auth.transactionId,
                    executionFee = auth.amount.multiply(BigDecimal("0.001"))
                )
            }
        } finally {
            telemetry.recordLatency("business_rule_validation", System.currentTimeMillis() - start)
        }
    }

    private suspend fun persistToLedger(event: FinancialEvent): FinancialEvent {
        val start = System.currentTimeMillis()
        return withContext(ioDispatcher) {
            delay(50) // Simulasi I/O non-blocking (R2DBC/gRPC)
            telemetry.recordLatency("ledger_persistence", System.currentTimeMillis() - start)
            event
        }
    }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Produksi: Engine Rekonsiliasi Real-Time Transaksi Finansial (High Throughput FinTech)

*   **Konteks Masalah:** Sistem Core Banking mengalami lonjakan transaksi *peak-season* sebesar 45.000 transaksi/detik. Sistem lama berbasis Spring WebMVC (blocking) dan Java ThreadPoolExecutor mengalami *exhaustion* pada pool thread (2000 OS threads aktif), menyebabkan *high garbage collector latency* (Stop-The-World mencapai 4.2 detik) dan *Out of Memory Error* (OOM) pada container Kubernetes.
*   **Spesifikasi Kegagalan:** JVM heap penuh diakibatkan oleh antrean `LinkedBlockingQueue` yang membengkakkan memori saat downstream payment switch eksternal mengalami penurunan performa (*downstream degradation*).

### Arsitektur Solusi Baru (Kotlin Flow Native)

```
[Kafka Inbound: 45k tx/s]
          │
          ▼
[Ktor Consumer / Flow Pipeline]
          │
          ├──► .buffer(capacity = 5000, onBufferOverflow = SUSPEND) 
          │    (Menerapkan backpressure instan ke Kafka partition consumer)
          │
          ├──► .flowOn(Dispatchers.Default) 
          │    (Validasi signature kriptografi SHA-256 tanpa alokasi object heap)
          │
          ├──► .conflate() atau .transformLatest() 
          │    (Khusus telemetry ticker)
          │
          └──► .retryWhen { cause, attempt -> 
                   attempt < 3 && cause is TransientNetworkException 
               }
```

### Hasil Metrik Produksi (Sebelum vs Sesudah Refactoring)

| Metrik | Arsitektur Lama (Java Threads) | Arsitektur Baru (Kotlin Flow Engine) | Dampak Bisnis |
| :--- | :--- | :--- | :--- |
| **P99.9 Latency** | 3.850 ms | 115 ms | Pengurangan waktu tunggu transaksi sebesar ~97% |
| **Footprint Memori** | 16 GB Heap (Jenuh) | 2.5 GB Heap (Stabil) | Penghematan node AWS EKS sebesar 65% |
| **Throughput Max** | 12.000 TPS (Saturasi) | 68.000 TPS | Mampu menahan beban puncak Black Friday tanpa scaling manual |
| **GC Pause Time** | Rata-rata 1.200 ms | < 15 ms (ZGC) | Mengeliminasi timeout transaksi pada jaringan perbankan |

---

## 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Kerugian | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **`@JvmInline value class`** | Meniadakan alokasi memori heap; performa setara primitif murni; *type safety* kuat. | Terkena *boxing* otomatis jika masuk ke koleksi generic (`List<T>`) atau polimorfisme interface. | Identifier domain (`AccountId`, `CurrencyCode`), wrapper metrik unit. Hindari pada hierarki polimorfik luas. |
| **Class Delegation (`by`)** | Menggantikan *fragile base inheritance* dengan komposisi; memangkas ribuan baris boilerplate delegasi. | Mengorbankan polimorfisme batin (*self-reference problem*); objek target tidak tahu wrapper luarnya. | Implementasi interface dekorator, caching wrapper, interface adapter. |
| **Cold Flow (`Flow<T>`)** | Hemat sumber daya; eksekusi bersifat *lazy*; *context preservation* dijamin oleh compiler runtime. | Tidak cocok untuk model *pub-sub* banyak subscriber sekaligus (*one-to-many broadcasting*). | Data pipelines, query database, file reader, streaming REST/gRPC responses. |
| **Hot Flow (`SharedFlow`)** | Mendukung multi-subscriber (*fan-out*); *configurable buffer overflow strategies*; *lifecycle-independent*. | Memori heap dapat bocor jika subscriber pasif menahan antrean buffer tanpa strategi overflow yang tepat. | Central Event Bus, WebSocket broadcast, notifikasi push sistem. |
| **`conflate()` Operator** | Mencegah *slow downstream bottleneck*; hanya data terbaru yang diproses. | Mengorbankan data perantara (terjadi *data dropping*); tidak boleh digunakan untuk transaksi mutlak. | Metrik harga saham, tracking lokasi GPS, status rendering UI. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Melanggar Context Preservation Invariant dalam Flow Engine
*   **Gejala:** Pipeline melempar `IllegalStateException: Flow invariant is violated: Emission from another coroutine is detected.`
*   **Root Cause:** Menggunakan `withContext(Dispatchers.IO)` secara langsung di dalam builder `flow { ... }` untuk mengeksekusi `emit()`.

```kotlin
// BAD: Menyebabkan Crash di Runtime
fun fetchOrders(): Flow<Order> = flow {
    withContext(Dispatchers.IO) {
        val orders = api.getOrders()
        orders.forEach { emit(it) } // CRASH! Melanggar SafeCollector invariant
    }
}

// FIXED: Gunakan flowOn untuk mengubah context upstream
fun fetchOrders(): Flow<Order> = flow {
    val orders = api.getOrders()
    orders.forEach { emit(it) }
}.flowOn(Dispatchers.IO) // Emitter berjalan di IO, Collector tetap di caller context
```

### Mistake 2: Emisi Berkelanjutan pada `SharedFlow` Menyebabkan Coroutine Hang (Deadlock)
*   **Gejala:** Sistem berhenti memproses event secara acak (*deadlock* parsial). Stack trace menunjukkan coroutine menggantung (*suspended*) pada pemanggilan `MutableSharedFlow.emit()`.
*   **Root Cause:** `MutableSharedFlow` default menggunakan konfigurasi `extraBufferCapacity = 0` dan `onBufferOverflow = BufferOverflow.SUSPEND`. Jika salah satu subscriber lambat, pemanggilan `emit()` akan ditangguhkan selamanya.

```kotlin
// BAD: Default configuration rentan starvation jika subscriber lambat
val eventBus = MutableSharedFlow<Event>() 

// FIXED: Sediakan kapasitas buffer eksplisit dan tentukan strategi mitigasi degradasi
val eventBus = MutableSharedFlow<Event>(
    replay = 0,
    extraBufferCapacity = 512,
    onBufferOverflow = BufferOverflow.DROP_OLDEST // Mengutamakan throughput sistem
)
```

### Mistake 3: Unintended Boxing pada Value Classes di Pipeline Kritis
*   **Gejala:** Lonjakan alokasi memori GC secara misterius pada micro-benchmark padahal sudah menggunakan `value class`.
*   **Root Cause:** Melewatkan `value class` ke antarmuka generic atau memanggil method via casting interface.

```kotlin
@JvmInline value class Latency(val ms: Long) : Comparable<Latency> {
    override fun compareTo(other: Latency): Int = this.ms.compareTo(other.ms)
}

// BAD: Terjadi boxing ke java.lang.Object karena masuk ke generic List
val latencies: List<Any> = listOf(Latency(100L), Latency(200L)) 

// FIXED: Gunakan primitive array langsung atau specialized collection jika di hot-path
val rawLatencies = LongArray(2) { (it + 1) * 100L }
```

---

## 11. Best Practices (Production Checklist)

*   [ ] **Dispatcher Encapsulation:** Jangan pernah melakukan *hardcode* `Dispatchers.IO` atau `Dispatchers.Default` di dalam service logic internal; selalu suntikkan (*inject*) `CoroutineDispatcher` via constructor injection untuk memungkinkan unit-testing paralel deterministik.
*   [ ] **Sealed Domain Completeness:** Gunakan ekspresi `when` sebagai *statement* atau *expression* komprehensif tanpa cabang `else` untuk memanfaatkan *exhaustiveness checking* compiler pada `sealed interfaces`.
*   [ ] **Flow Terminal Safety:** Pastikan setiap *cold flow* yang dibuat dari koneksi jaringan atau I/O dibungkus dengan operator `catch` sebelum dikonsumsi di boundary layer, mencegah unhandled exceptions mematikan `CoroutineScope` induk.
*   [ ] **Avoid GlobalScope:** Larang mutlak penggunaan `GlobalScope`. Gunakan `CoroutineScope` yang terikat pada siklus hidup komponen aplikasi (`lifecycleScope`, `viewModelScope`, atau custom injected scope yang ditutup via `scope.cancel()` saat teardown).
*   [ ] **Testing Flow Invariants:** Gunakan pustaka **Turbine** (`app.cash.turbine:turbine`) untuk memverifikasi emisi event atomik daripada menggunakan `delay()` buatan dalam *unit tests*.
*   [ ] **Backpressure Stress Validation:** Uji semua *pipeline* reaktif menggunakan pengujian beban buatan (*stress testing*) dengan rasio latensi produsen:konsumen minimal 1:100.

---

## 12. Hands-on Practice

Buat dan jalankan pipeline reaktif dengan langkah-langkah berikut di folder direktori kerja: `hands-on/m02/`.

### Struktur Direktori
```text
hands-on/m02/
├── build.gradle.kts
├── settings.gradle.kts
└── src
    ├── main
    │   └── kotlin
    │       └── com
    │           └── enterprise
    │               └── pipeline
    │                   ├── Domain.kt
    │                   └── PipelineApp.kt
    └── test
        └── kotlin
            └── com
                └── enterprise
                    └── pipeline
                        └── PipelineTest.kt
```

### Langkah 1: Konfigurasi Build Script (`hands-on/m02/build.gradle.kts`)
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
    testImplementation("app.cash.turbine:turbine:1.0.0")
    testImplementation(kotlin("test"))
}

application {
    mainClass.set("com.enterprise.pipeline.PipelineAppKt")
}

tasks.test {
    useJUnitPlatform()
}
```

### Langkah 2: Domain Model & Pipeline (`hands-on/m02/src/main/kotlin/com/enterprise/pipeline/Domain.kt`)
```kotlin
package com.enterprise.pipeline

import kotlinx.coroutines.flow.*
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers

@JvmInline
value class MeterId(val id: String)

@JvmInline
value class ReadingValue(val value: Double)

sealed interface TelemetryRecord {
    val meterId: MeterId

    data class ValidRecord(
        override val meterId: MeterId,
        val reading: ReadingValue,
        val timestamp: Long
    ) : TelemetryRecord

    data class CorruptedRecord(
        override val meterId: MeterId,
        val rawPayload: String
    ) : TelemetryRecord
}

class TelemetryTransformer(
    private val computeDispatcher: CoroutineDispatcher = Dispatchers.Default
) {
    fun parseStream(rawStream: Flow<String>): Flow<TelemetryRecord> = rawStream
        .map { payload ->
            val parts = payload.split(";")
            if (parts.size == 3) {
                val id = MeterId(parts[0])
                val value = parts[1].toDoubleOrNull()
                val ts = parts[2].toLongOrNull()
                if (value != null && ts != null) {
                    TelemetryRecord.ValidRecord(id, ReadingValue(value), ts)
                } else {
                    TelemetryRecord.CorruptedRecord(id, payload)
                }
            } else {
                TelemetryRecord.CorruptedRecord(MeterId("UNKNOWN"), payload)
            }
        }
        .flowOn(computeDispatcher)
}
```

### Langkah 3: Main Application Entry Point (`hands-on/m02/src/main/kotlin/com/enterprise/pipeline/PipelineApp.kt`)
```kotlin
package com.enterprise.pipeline

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

fun main(): Unit = runBlocking {
    val transformer = TelemetryTransformer()
    
    val incomingStream = flow {
        emit("MTR-01;124.50;1700000000")
        emit("MTR-02;INVALID;1700000001")
        emit("MTR-03;999.82;1700000002")
    }

    println("Memulai konsumsi telemetry pipeline...")
    
    transformer.parseStream(incomingStream)
        .collect { record ->
            when (record) {
                is TelemetryRecord.ValidRecord -> {
                    println("[VALID] Meter: ${record.meterId.id}, Value: ${record.reading.value}")
                }
                is TelemetryRecord.CorruptedRecord -> {
                    System.err.println("[CORRUPT] Meter: ${record.meterId.id}, Payload: ${record.rawPayload}")
                }
            }
        }
    println("Pipeline streaming selesai.")
}
```

### Langkah 4: Automated Verification via Turbine (`hands-on/m02/src/test/kotlin/com/enterprise/pipeline/PipelineTest.kt`)
```kotlin
package com.enterprise.pipeline

import app.cash.turbine.test
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

class PipelineTest {

    @Test
    fun `verifikasi parsing valid dan corrupted record deterministik`() = runTest {
        val testDispatcher = StandardTestDispatcher(testScheduler)
        val transformer = TelemetryTransformer(computeDispatcher = testDispatcher)

        val rawInput = flowOf(
            "M-1;42.0;1000",
            "BAD_LINE"
        )

        transformer.parseStream(rawInput).test {
            // Emisi pertama harus ValidRecord
            val item1 = awaitItem()
            assertIs<TelemetryRecord.ValidRecord>(item1)
            assertEquals("M-1", item1.meterId.id)
            assertEquals(42.0, item1.reading.value)

            // Emisi kedua harus CorruptedRecord
            val item2 = awaitItem()
            assertIs<TelemetryRecord.CorruptedRecord>(item2)
            assertEquals("UNKNOWN", item2.meterId.id)

            awaitComplete()
        }
    }
}
```

### Langkah Eksekusi CLI
```bash
# Pindah ke direktori hands-on
cd hands-on/m02/

# Jalankan pengujian unit berbasis Coroutine Test
./gradlew test

# Jalankan aplikasi pipeline
./gradlew run
```

---

## 13. Exercises

### Level: Easy
Implementasikan kelas delegasi kustom bernama `ThreadSafeVolatileDelegate<T>` menggunakan JVM `@Volatile` internal modifier di atas tipe generik tanpa menggunakan keyword `synchronized`. Verifikasi bahwa nilai yang diperbarui oleh satu thread langsung terbaca oleh thread lain.

### Level: Medium
Rancang sebuah `EventBus` terdistribusi lokal menggunakan `SharedFlow` dengan dukungan *variance*:
*   Konsumen dapat berlangganan kelas induk: `fun <T : DomainEvent> subscribe(eventType: Class<T>): Flow<T>`.
*   Gunakan operator `filterIsInstance` untuk menyaring tipe yang relevan secara efisien tanpa kehilangan metadata tipe di runtime.

### Level: Hard
Buat operator ekstensi Flow kustom:
```kotlin
fun <T> Flow<T>.throttleFirst(windowDurationMs: Long): Flow<T>
```
*Syarat Operasional:*
1.  Wajib memancarkan item pertama yang ditemui.
2.  Mengabaikan (*drop*) semua emisi berikutnya selama jendela waktu `windowDurationMs`.
3.  Tidak boleh menggunakan alokasi coroutine liar (`GlobalScope.launch`).
4.  Wajib mematuhi hukum context preservation dan exception transparency.

---

## 14. Challenge

### Real-Time Financial Order-Book Arbitrage Aggregator Engine
Sebuah crypto-exchange enterprise membutuhkan mesin agregasi *order-book* mikro yang mengonsumsi koneksi WebSocket simultan dari 3 bursa terdesentralisasi berbeda (misalnya: Binance, Coinbase, Kraken).

**Batasan & Persyaratan Sistem:**
1.  **Strict Zero-Allocation Hot Path:** Identifier pasangan mata uang (`CurrencyPair`), ID Transaksi, dan Harga desimal harus dibungkus dengan `@JvmInline value class` untuk menjamin zero-boxing saat proses kalkulasi harga spread.
2.  **State Machine:** Rancang status order book menggunakan `StateFlow` terkonsolidasi dengan `Sealed Interface` yang memetakan status: `Syncing`, `OptimalSpreadFound(val spread: Spread)`, dan `ArbitrageExhausted`.
3.  **Backpressure Resilience:** Jika downstream order-executing engine mengalami keterlambatan (*lag*), pipeline tidak boleh menjatuhkan koneksi WebSocket jaringan; gunakan mekanisme penanganan buffer hybrid (`DROP_OLDEST` untuk paket snapshot harga, tetapi `SUSPEND` untuk paket eksekusi transaksi legal).
4.  **Failure Isolation:** Kegagalan koneksi atau error parsing pada salah satu bursa tidak boleh membatalkan *coroutine scope* bursa yang lain (*Supervised structured concurrency*).

---

## 15. Quiz Evaluasi Pemahaman

### Evaluasi Pemahaman Dasar (Basic)

1.  **Mengapa `@JvmInline value class` yang membungkus tipe primitif `Long` dapat mengalami alokasi memori heap (*boxing*)?**
    *   *Jawaban:* Boxing terjadi jika value class di-pass ke dalam fungsi yang menerima generic parameter (`<T>`), di-cast ke sebuah antarmuka (`interface`), atau dideklarasikan sebagai tipe nullable (`MyValueClass?`). Pada kondisi tersebut, runtime JVM membutuhkan representasi referensi berbasis `java.lang.Object`.

2.  **Apa perbedaan mendasar antara `class Car : Vehicle by engine` dengan inheritance konvensional `class Car : Engine()`?**
    *   *Jawaban:* Class delegation menggunakan pola komposisi di mana compiler membuat forwarding methods ke objek `engine` internal. Ini mematuhi prinsip *Composition over Inheritance*, mencegah masalah *fragile base class*, dan menyembunyikan implementasi internal yang tidak ingin diekspos oleh superclass.

3.  **Apa yang terjadi jika kita memanggil method `emit()` pada Cold `Flow` tanpa memanggil method terminal operator seperti `collect()`?**
    *   *Jawaban:* Tidak terjadi apa-apa. Kode di dalam blok pembangun cold flow (`flow { ... }`) bersifat malas (*lazy*) dan tidak akan dieksekusi sampai sebuah terminal collector memicu pemanggilan antarmuka `Flow.collect(collector)`.

4.  **Mengapa pemanggilan `withContext(Dispatchers.IO)` dilarang di dalam blok pembangun `flow { ... }` saat mengeksekusi `emit()`?**
    *   *Jawaban:* Karena melanggar hukum *Context Preservation Invariant*. Flow Collector menuntut emisi data terjadi di dalam `CoroutineContext` yang sama dengan pemanggil `collect`. Mengubah context saat emit dapat memicu masalah konkurensi tak terprediksi di hilir.

5.  **Kapan sebaiknya kita menggunakan `StateFlow` dibandingkan `SharedFlow`?**
    *   *Jawaban:* `StateFlow` digunakan ketika kita hanya membutuhkan status terkini (*current state*) yang bersifat tunggal, idempotent, dan conflated (misalnya UI state, read model snapshot). `SharedFlow` digunakan ketika kita memproses serangkaian event atau sinyal diskrit (*event-driven stream*) yang membutuhkan konfigurasi replay atau penanganan buffer overflow.

---

### Evaluasi Pemahaman Menengah (Intermediate)

6.  **Bagaimana mekanisme internal JVM dalam mengeksekusi Kotlin `suspend fun` tanpa membuat thread OS baru?**
    *   *Jawaban:* Compiler mentransformasi fungsi penangguhan menjadi *State Machine* melalui *Continuation-Passing Style* (CPS). Sebuah argumen tersembunyi `Continuation<T>` disuntikkan ke dalam fungsi. Saat eksekusi mencapai titik penangguhan (*suspension point*), status eksekusi lokal (register/variabel lokal) disimpan ke dalam objek state machine, dan fungsi kembali (*return*) dengan token penanda `COROUTINE_SUSPENDED`. Dispatcher kemudian bebas menggunakan thread yang sama untuk tugas lain hingga panggilan callback asinkron memanggil `continuation.resumeWith()`.

7.  **Jelaskan konsep *Declaration-site variance* menggunakan keyword `out` dan `in` pada Kotlin dan bandingkan dengan *Use-site variance* (Wildcards) di Java!**
    *   *Jawaban:* Di Java, variansi ditentukan saat tipe digunakan (*Use-site*), misalnya `List<? extends Number>`. Kotlin memungkinkan variansi ditentukan langsung saat interface didefinisikan (*Declaration-site*). `out T` (*Covariant*) berarti tipe hanya dapat diproduksi/dikembalikan dari antarmuka (setara dengan `? extends T`), sedangkan `in T` (*Contravariant*) berarti tipe hanya dapat dikonsumsi sebagai argumen fungsi (setara dengan `? super T`).

8.  **Apa perbedaan mendasar cara kerja operator `conflate()` dan `buffer(Channel.CONFLATED)`?**
    *   *Jawaban:* Keduanya memiliki semantik perilaku yang identik. Operator `conflate()` adalah jalan pintas sintaksis (*syntactic sugar*) untuk memanggil `buffer(capacity = 0, onBufferOverflow = BufferOverflow.DROP_OLDEST)` atau menggunakan kapasitas antrean `Channel.CONFLATED`, di mana downstream yang lambat hanya akan mendapatkan item terbaru yang di-emit oleh upstream, mengabaikan (*dropping*) emisi perantara.

9.  **Mengapa operator `SharedFlow.collect()` tidak pernah menyelesaikan eksekusinya secara normal (*never completes*)?**
    *   *Jawaban:* Karena `SharedFlow` adalah *Hot Stream* yang merepresentasikan aliran data yang berpotensi terus aktif tanpa akhir (*infinite stream*). Berbeda dengan *Cold Flow* yang selesai ketika blok pembangunnya mengakhiri eksekusi, `SharedFlow` dirancang untuk tetap membuka koneksi langganan guna menunggu emisi event masa depan, sehingga pemanggil coroutine akan tersuspensi permanen kecuali scope-nya dibatalkan secara eksplisit.

10. **Bagaimana cara kerja operator `flowOn` dalam mengisolasi thread upstream tanpa memengaruhi downstream?**
    *   *Jawaban:* Operator `flowOn` memasang boundary berbasis *Channel* di dalam pipeline. Segmen upstream dieksekusi di coroutine baru yang terikat pada `CoroutineDispatcher` yang ditentukan oleh `flowOn`, lalu hasilnya dikirim melalui Channel internal non-blocking ke coroutine downstream yang berjalan pada context awal pemanggil `collect()`.

---

### Skenario Kasus Produksi (Production Scenarios)

11. **Skenario 1 (Memory Leak pada Event Streaming):**
    Sebuah aplikasi microservice backend menggunakan singleton `MutableSharedFlow` sebagai message bus internal aplikasi. Setelah 4 hari beroperasi di Kubernetes, pod mengalami OOM (*Out Of Memory*). Analisis heap dump menunjukkan terdapat jutaan objek `Emitter` dan `AbstractCoroutine` yang tertahan di memori.
    *   **Identifikasi Masalah:** Ada *subscriber* pasif atau lambat yang diluncurkan menggunakan `CoroutineScope` jangka panjang tanpa strategi overflow buffer (`extraBufferCapacity = 0` dan default `BufferOverflow.SUSPEND`). Akibatnya, seluruh alur emisi menumpuk objek penangguhan di heap.
    *   **Solusi Desain:** Ubah konfigurasi buffer `SharedFlow` dengan batas ukuran eksplisit (`extraBufferCapacity`) dan pasang strategi degradasi `BufferOverflow.DROP_OLDEST`. Pastikan siklus hidup coroutine subscriber terikat secara ketat pada siklus hidup request/sesi, bukan aplikasi global.

12. **Skenario 2 (Pipeline Stalling pada High-CPU Load):**
    Sebuah pipeline Flow membaca pesan dari AWS SQS, melakukan enkripsi data (komputasi CPU berat), dan menyimpan hasilnya ke database PostgreSQL via R2DBC. Ketika traffic naik, konsumsi pesan SQS melambat secara drastis meskipun kapasitas CPU instance masih 40%.
    *   **Identifikasi Masalah:** Seluruh pipeline (I/O SQS, komputasi enkripsi, dan DB Write) berjalan pada satu dispatcher yang sama, yaitu `Dispatchers.IO`. Ketika task enkripsi yang intensif komputasi mengeksekusi thread I/O, terjadi thread-scheduling contention yang mengganggu thread worker I/O.
    *   **Solusi Desain:** Pisahkan arsitektur thread menggunakan batas context yang jelas:
        ```kotlin
        sqsFlow
            .map { decrypt(it) }.flowOn(Dispatchers.Default) // Isolasi komputasi enkripsi ke Thread Pool CPU
            .map { persistToDb(it) }.flowOn(Dispatchers.IO) // Isolasi database I/O ke Thread Pool blocking/NIO
        ```

13. **Skenario 3 (Lost Updates pada State Synchronization UI/Client):**
    Aplikasi memproses perubahan state akun perbankan melalui `StateFlow`. Pada pengujian integrasi beban tinggi (1000 mutasi/detik per akun), saldo akhir yang tercatat pada subscriber klien tidak konsisten dengan riwayat database, meskipun tidak ada error yang terlempar.
    *   **Identifikasi Masalah:** `StateFlow` secara desain bersifat *conflated*. Jika nilai `value` diperbarui lebih cepat daripada kemampuan subscriber mengonsumsinya, perubahan nilai perantara (*intermediate states*) akan dilewati (*dropped*) demi efisiensi render. `StateFlow` hanya menjamin pengiriman nilai *terbaru*, bukan seluruh jejak riwayat mutasi.
    *   **Solusi Desain:** Ganti `StateFlow` dengan `SharedFlow` yang dikonfigurasi dengan kapasitas buffer mencukupi atau gunakan channel berbasis event `Channel<AccountMutation>(Channel.UNLIMITED)` untuk menjamin bahwa setiap mutasi finansial diproses tanpa ada yang hilang (*guaranteed delivery*).

---

## 16. Summary

*   **Penyatuan Paradigma:** Kotlin berhasil menyatukan paradigma Object-Oriented yang kuat (*type-safe, strictly-typed*) dengan paradigma Asynchronous Reaktif melalui optimalisasi tingkat compiler bytecode JVM.
*   **Efisiensi Memori Tingkat Lanjut:** Penggunaan `@JvmInline value class` dan `sealed interfaces` menghilangkan *garbage collection overhead* yang biasa ditemukan pada arsitektur DDD klasik, mentransformasikan kode ekspresif tingkat tinggi menjadi instruksi primitif efisien pada JVM.
*   **Suspension-Driven Reactive Streams:** Berbeda dengan Reactive Streams generasi lama yang membutuhkan penanganan callback yang kompleks, Kotlin `Flow` memanfaatkan *Continuation-Passing Style* (CPS) untuk menghadirkan backpressure non-blocking secara alami, hemat sumber daya, dan aman terhadap context execution.
*   **Fondasi Kesiapan Produksi:** Skalabilitas enterprise menuntut disiplin dalam memisahkan dispatching layer (`flowOn`), memilih tipe stream yang tepat (`Cold Flow` vs `StateFlow` vs `SharedFlow`), serta mitigasi memory leak melalui pembatasan buffer buffer overflow yang teruji secara komprehensif.