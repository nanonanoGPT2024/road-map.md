# BAB 03 MODULE 01: Functional Programming & Lambdas

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Pembelajaran**: Pemrograman Terapan Kotlin & JVM
*   **Kategori**: 02-Programming-Languages
*   **Kode Modul**: KOT-03-01
*   **Topik**: Functional Programming & Lambdas
*   **Prasyarat**: Pemahaman mendasar sintaks Kotlin (Control Flow, Class, Interface, Type System, Null Safety).
*   **Estimasi Waktu Pengerjaan**: 180 Menit

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Membedah Mekanisme First-Class Functions**: Memahami implementasi internal tipe fungsi (`Function0`, `Function1`, ..., `FunctionN`) pada level JVM bytecode.
2.  **Menguasai Semantik Lambdas & Closures**: Menganalisis implikasi alokasi heap saat penangkapan variabel (*variable capturing*) dan siklus hidup objek ref wrapper.
3.  **Mengoperasikan Higher-Order Functions (HOF)**: Merancang dan memanfaatkan fungsi yang menerima dan mengembalikan fungsi secara aman dan ergonomis.
4.  **Mendominasi Modifikator Eksekusi**: Mengevaluasi kebutuhan penggunaan kata kunci `inline`, `noinline`, dan `crossinline`, serta dampaknya pada ukuran bytecode dan performa runtime.
5.  **Membangun Domain-Specific Languages (DSL)**: Mengimplementasikan *Function Literals with Receiver* (`T.() -> Unit`) untuk struktur data deklaratif yang ekspresif.
6.  **Mitigasi Overhead Alokasi**: Mendiagnosis dan mengeliminasi *escape analysis penalties* yang disebabkan oleh instansiasi objek anonim dari lambda pada loop performa tinggi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma Imperatif berbasis Object-Oriented Programming (OOP), state dan mutasi didistribusikan ke dalam objek-objek diskret. Pola pikir yang digunakan adalah *bagaimana sesuatu dieksekusi secara langkah demi langkah* melalui manipulasi status internal:

$$\text{Input} \longrightarrow [\text{Mutasi Objek / State Mutabel}] \longrightarrow \text{Output}$$

Pada Functional Programming (FP) di Kotlin, mental model bergeser ke **transformasi data deterministik melalui fungsi murni (*pure functions*)**:

$$\text{Data}_0 \xrightarrow{f_1} \text{Data}_1 \xrightarrow{f_2} \text{Data}_2 \xrightarrow{f_3} \dots \xrightarrow{f_n} \text{Data}_n$$

Fungsi diperlakukan sebagai nilai kelas satu (*first-class citizens*). Artinya, sebuah fungsi dapat:
*   Disimpan di dalam variabel.
*   Diteruskan sebagai argumen ke fungsi lain.
*   Dikembalikan sebagai nilai dari sebuah fungsi.

### Metafora Pipeline Industri
Bayangkan alur pemrosesan data sebagai instalasi pipa pemurnian cairan:
*   **Data Immutable**: Air mentah yang mengalir tanpa pernah dimodifikasi di tempat asal.
*   **Higher-Order Functions**: Katup dan adaptor fisik pada jalur pipa.
*   **Lambdas**: Filter spesifik atau katalis kimia cair yang dipasang ke dalam katup untuk melakukan reaksi kimia terisolasi tanpa mencemari sistem penampung luar.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Mekanisme eksekusi lambda di Kotlin bergantung pada ada tidaknya modifikator `inline`. Diagram berikut membandingkan jalur eksekusi antara Non-Inline Lambda (mengalokasikan objek turunan `kotlin.jvm.functions.FunctionN`) versus Inline Lambda (menyisipkan bytecode langsung ke *call site*).

```
+-----------------------------------------------------------------------------------+
|                            CALL SITE (KODE KLIEN)                                 |
+-----------------------------------------------------------------------------------+
                                      |
                    Apakah target fungsi memiliki 'inline'?
                                     / \
                                    /   \
                             TIDAK /     \ YA
                                  /       \
+------------------------------------+   +------------------------------------------+
|      NON-INLINE EXECUTION          |   |            INLINE EXECUTION              |
+------------------------------------+   +------------------------------------------+
| 1. Instansiasi Objek Anonymous     |   | 1. Tidak ada instansiasi objek fungsi.   |
|    `new Function1() { ... }`       |   |                                          |
| 2. Pindahkan referensi ke Heap     |   | 2. Compiler menyalin bytecode tubuh      |
| 3. Tangkap variabel luar via       |   |    fungsi target & lambda langsung ke    |
|    Ref Objects (Ref$ObjectRef)     |   |    dalam call site.                      |
| 4. Invoke interface method:        |   | 3. Tidak ada penambahan stack frame      |
|    `invoke(param)`                 |   |    baru dari pemanggilan method invoke.  |
| 5. Pressure pada Garbage Collector |   | 4. Memungkinkan Non-Local Return via    |
|                                    |   |    perintah `return` langsung.           |
+------------------------------------+   +------------------------------------------+
                  |                                           |
                  v                                           v
+------------------------------------+   +------------------------------------------+
|         JVM HEAP & METHOD AREA     |   |          JVM EXECUTION THREAD            |
|   [Function Instance Allocation]   |   |        [Direct Inlined Bytecode]         |
+------------------------------------+   +------------------------------------------+
```

Alur alokasi memori pada Closure yang menangkap variabel mutabel:

```
[Call Site Stack Frame]
  |
  +--> [local variable: counter] ---> Menunjuk ke Object Wrapper di Heap
                                                  |
                                                  v
                                      +-----------------------+
                                      |   Ref$IntRef (Heap)   |
                                      +-----------------------+
                                      | element: <current_val>|
                                      +-----------------------+
                                                  ^
                                                  |
  +--> [Lambda Object (Heap)] --------------------+
       Menggenggam referensi Ref$IntRef
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Tipe Data Fungsi & JVM Interop
Kotlin mendefinisikan antarmuka fungsional di runtime package `kotlin.jvm.functions.*`. Terdapat antarmuka mulai dari `Function0<R>` hingga `Function22<P1, ..., P22, R>`.

```kotlin
// Kode Kotlin
val transform: (String) -> Int = { it.length }
```

Diterjemahkan oleh compiler Kotlin menjadi representasi bytecode setara Java:

```java
// Representasi internal terkompilasi
public final class ExampleKt {
    private static final Function1<String, Integer> transform = 
        new Function1<String, Integer>() {
            @Override
            public Integer invoke(String it) {
                Intrinsics.checkNotNullParameter(it, "it");
                return it.length();
            }
        };
}
```

Jika fungsi memerlukan lebih dari 22 parameter, Kotlin beralih ke antarmuka generik `FunctionN<R>`.

### 2. Variable Capturing & Object Wrappers
Ketika lambda membaca atau memodifikasi variabel dari lingkup eksternal (*outer scope*), variabel tersebut "ditangkap" (*captured*).
*   Jika variabel bersifat **immutable** (`val`), nilainya disalin langsung ke dalam *field* instance `Function`.
*   Jika variabel bersifat **mutable** (`var`), compiler membungkusnya ke dalam instance referensi, misalnya `kotlin.jvm.internal.Ref.IntRef` atau `Ref.ObjectRef<T>`.

```kotlin
var accumulator = 0
val increment = { accumulator += 1 }
```

Secara bytecode, operasi ini setara dengan:

```java
final Ref.IntRef accumulator = new Ref.IntRef();
accumulator.element = 0;
Function0 increment = (Function0)(new Function0() {
    public Object invoke() {
        accumulator.element++;
        return Unit.INSTANCE;
    }
});
```
Hal ini memperkenalkan alokasi heap ganda: satu untuk objek lambda dan satu untuk objek `Ref.IntRef`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Higher-Order Functions (HOF)
Higher-Order Function adalah fungsi yang memenuhi setidaknya satu kriteria:
1. Menerima fungsi lain sebagai parameter.
2. Mengembalikan fungsi sebagai hasil eksekusi.

```kotlin
fun <T, R> Sequence<T>.map(transform: (T) -> R): Sequence<R>
```

### Modifikator Inlining: `inline`, `noinline`, `crossinline`

#### A. `inline`
Memerintahkan compiler untuk mengganti pemanggilan fungsi dan lambda argumennya langsung dengan kode aslinya di setiap call site. Ini meniadakan alokasi heap untuk objek fungsi dan mengizinkan *non-local returns*.

```kotlin
inline fun executeOperation(operation: () -> Unit) {
    operation()
}
```

#### B. `noinline`
Ketika sebuah fungsi di-`inline`, semua parameter fungsi di dalamnya secara default ikut ter-inline. Jika salah satu parameter lambda perlu disimpan ke variabel, diteruskan ke fungsi non-inline lain, atau dieksekusi secara lazy, gunakan modifikator `noinline`.

```kotlin
inline fun processTransaction(
    action: () -> Unit,
    noinline fallback: () -> Unit // Tetap berupa objek Function instance
) {
    action()
    saveToHistory(fallback) // Legal karena noinline
}
```

#### C. `crossinline`
Mencegah *non-local returns* pada inline lambda yang dieksekusi dalam konteks eksekusi lain (misalnya di dalam `Runnable`, Coroutine builder, atau local object).

```kotlin
inline fun executeAsync(crossinline task: () -> Unit) {
    val runnable = Runnable {
        task() // Memerlukan crossinline agar 'return' non-local dari task ditolak compiler
    }
    Thread(runnable).start()
}
```

### Function Literals with Receiver
Konsep ini menambahkan konteks objek target (`Receiver`) ke dalam fungsi lambda, memungkinkan akses terhadap properti dan method dari receiver tersebut tanpa kualifikasi eksplisit.

```kotlin
// Format: ReceiverType.(ParamType) -> ReturnType
val buildString: StringBuilder.() -> Unit = {
    append("Data ") // 'this' merujuk ke StringBuilder
    append(100)
}
```
Ini merupakan landasan pembentukan Type-Safe Builders dan DSL pada Kotlin (seperti skrip Gradle Kotlin DSL dan Ktor).

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi bertahap dari pemanfaatan lambda, closure, inline, hingga lambda with receiver:

```kotlin
package com.architect.functional

// Model Data Domain
data class Metric(val id: String, val value: Double, val active: Boolean)

// =========================================================================
// 1. First-Class Functions & Function Types
// =========================================================================
typealias MetricPredicate = (Metric) -> Boolean
typealias MetricTransformer = (Metric) -> String

val isActivePredicate: MetricPredicate = { metric -> metric.active }

// =========================================================================
// 2. Higher-Order Functions & Inline Engine
// =========================================================================
inline fun processMetrics(
    metrics: List<Metric>,
    predicate: MetricPredicate,
    noinline telemetrySink: ((String) -> Unit)? = null,
    transform: MetricTransformer
): List<String> {
    val results = mutableListOf<String>()
    
    for (metric in metrics) {
        if (predicate(metric)) {
            val transformed = transform(metric)
            results.add(transformed)
            telemetrySink?.invoke("Processed: ${metric.id}")
        }
    }
    return results
}

// =========================================================================
// 3. DSL Construction dengan Lambda with Receiver
// =========================================================================
class PipelineConfig {
    var enableLogging: Boolean = false
    var threshold: Double = 0.0
    private val filters = mutableListOf<(Metric) -> Boolean>()

    fun filter(condition: (Metric) -> Boolean) {
        filters.add(condition)
    }

    fun buildFilter(): (Metric) -> Boolean = { metric ->
        metric.value >= threshold && filters.all { it(metric) }
    }
}

fun pipeline(init: PipelineConfig.() -> Unit): (Metric) -> Boolean {
    val config = PipelineConfig()
    config.init() // Menjalankan lambda dengan context PipelineConfig
    return config.buildFilter()
}

// =========================================================================
// Main Runner
// =========================================================================
fun main() {
    val metricStream = listOf(
        Metric("cpu.load", 85.5, true),
        Metric("mem.used", 42.0, false),
        Metric("disk.io", 99.2, true)
    )

    // Penggunaan DSL
    val customFilter = pipeline {
        threshold = 50.0
        enableLogging = true
        filter { it.id.startsWith("cpu") || it.id.startsWith("disk") }
    }

    // Trailing Lambda Syntax & Higher-Order Functions
    val report = processMetrics(
        metrics = metricStream,
        predicate = customFilter,
        telemetrySink = { log -> println("[TELEMETRY] $log") }
    ) { metric ->
        "Metric Alert: [${metric.id}] breaches threshold with value ${metric.value}"
    }

    report.forEach { println(it) }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah dekonstruksi teknis dari kode implementasi pada Seksi 07:

1.  `typealias MetricPredicate = (Metric) -> Boolean`: Memberikan abstraksi semantik terhadap tipe fungsi yang menerima `Metric` dan mengembalikan `Boolean`. Memperjelas dokumentasi tipe tanpa overhead runtime.
2.  `val isActivePredicate: MetricPredicate = { metric -> metric.active }`: Menginstansiasi fungsi lambda anonim ke dalam variabel lokal. Tipe parameter divalidasi oleh compiler.
3.  `inline fun processMetrics(...)`: Menandai seluruh fungsi untuk disalin langsung ke call site guna mencegah alokasi memori objek fungsi.
4.  `noinline telemetrySink: ((String) -> Unit)? = null`: Menginstruksikan compiler agar parameter `telemetrySink` **tidak** di-inline, sehingga nilainya dapat berupa objek nullable yang diteruskan secara dinamis ke fungsi runtime tanpa memaksa inlining masif di call site.
5.  `for (metric in metrics)`: Loop standar yang saat digabung dengan `inline` dieksekusi secara flat tanpa pemanggilan invoke polimorfik.
6.  `class PipelineConfig { ... }`: State holder untuk membangun DSL berbasis receiver.
7.  `fun pipeline(init: PipelineConfig.() -> Unit)`: Menerima *lambda with receiver*. Variabel `init` bertindak sebagai method ekstensi internal terhadap instance `PipelineConfig`.
8.  `config.init()`: Mengeksekusi blok kode lambda yang disuplai oleh pengguna di dalam konteks instance `PipelineConfig` (mengaktifkan *scope receiver*).
9.  `processMetrics(...) { metric -> ... }`: Trailing lambda syntax. Parameter lambda terakhir diekstraksi ke luar kurung lengkung pemanggilan fungsi untuk sintaksis yang ergonomis.

---

## SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Konteks Kasus
Sebuah platform High-Throughput Financial Payment Gateway menangani $15.000$ transaksi per detik (TPS). Setiap transaksi harus melewati serangkaian rantai *middleware* penanganan:
1. Validasi Sanitasi Data.
2. Evaluasi Kecurangan (*Fraud Detection Filter*).
3. Penyesuaian Nilai Pajak Regional (*Tax Calculation Strategy*).
4. Pencatatan Audit Trail.

### Permasalahan
Implementasi berorientasi objek murni menggunakan Chain of Responsibility Pattern tradisional menghasilkan alokasi ribuan objek per detik untuk *handler node*, yang membebani Garbage Collector (GC) dan memicu fenomena *Stop-The-World* (STW) latency spikes.

### Solusi Fungsional
Merancang **Zero-Allocation Middleware Pipeline Engine** menggunakan Kotlin Functional Programming:
*   Pipeline dibangun secara deklaratif via DSL.
*   Eksekusi transformasi dibungkus menggunakan Higher-Order Functions berkecepatan tinggi.
*   Penggunaan `inline` pada loop evaluasi kritis memangkas alokasi objek per request hingga nol (*zero-overhead abstraction*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```kotlin
package com.payment.gateway.pipeline

import java.math.BigDecimal
import java.time.Instant

// Model Entitas Domain
data class Transaction(
    val id: String,
    val merchantId: String,
    val amount: BigDecimal,
    val currency: String,
    val timestamp: Instant,
    val metadata: Map<String, String> = emptyMap()
)

sealed class PipelineResult {
    data class Success(val transaction: Transaction) : PipelineResult()
    data class Rejected(val reason: String, val transaction: Transaction) : PipelineResult()
}

// Tipe Alias untuk Middleware Function
typealias Middleware = (Transaction) -> MiddlewareDecision

sealed class MiddlewareDecision {
    data class Proceed(val transaction: Transaction) : MiddlewareDecision()
    data class Abort(val reason: String) : MiddlewareDecision()
}

// DSL Builder untuk Komposisi Middleware
class PaymentPipelineBuilder {
    private val middlewares = mutableListOf<Middleware>()

    fun sanitize(action: (Transaction) -> Transaction) {
        middlewares.add { tx -> 
            MiddlewareDecision.Proceed(action(tx)) 
        }
    }

    fun verify(predicate: (Transaction) -> Boolean, rejectionReason: String) {
        middlewares.add { tx ->
            if (predicate(tx)) {
                MiddlewareDecision.Proceed(tx)
            } else {
                MiddlewareDecision.Abort(rejectionReason)
            }
        }
    }

    fun build(): PaymentPipeline = PaymentPipeline(middlewares.toList())
}

// Eksekutor Pipeline
class PaymentPipeline(private val middlewares: List<Middleware>) {
    
    // Inline loop engine untuk mengeksekusi pipeline berantai
    inline fun execute(
        initialTransaction: Transaction,
        onAbort: (String, Transaction) -> Unit
    ): PipelineResult {
        var currentTx = initialTransaction

        for (i in middlewares.indices) {
            val decision = middlewares[i](currentTx)
            when (decision) {
                is MiddlewareDecision.Proceed -> {
                    currentTx = decision.transaction
                }
                is MiddlewareDecision.Abort -> {
                    onAbort(decision.reason, currentTx)
                    return PipelineResult.Rejected(decision.reason, currentTx)
                }
            }
        }

        return PipelineResult.Success(currentTx)
    }
}

// Factory Function Menggunakan Function Literals with Receiver
fun configurePipeline(builderAction: PaymentPipelineBuilder.() -> Unit): PaymentPipeline {
    val builder = PaymentPipelineBuilder()
    builder.builderAction()
    return builder.build()
}

// =========================================================================
// Eksekusi Produksi
// =========================================================================
fun main() {
    // 1. Inisialisasi Pipeline Deklaratif
    val gatewayPipeline = configurePipeline {
        // Step 1: Sanitasi
        sanitize { tx ->
            tx.copy(merchantId = tx.merchantId.trim().uppercase())
        }

        // Step 2: Fraud Check
        verify(
            predicate = { tx -> tx.amount < BigDecimal("50000.00") },
            rejectionReason = "ERR_FRAUD_LIMIT_EXCEEDED"
        )

        // Step 3: Currency Validation
        verify(
            predicate = { tx -> tx.currency in setOf("USD", "EUR", "IDR") },
            rejectionReason = "ERR_UNSUPPORTED_CURRENCY"
        )
    }

    // 2. Simulasi Transaksi Masuk
    val incomingTx = Transaction(
        id = "TX-998811",
        merchantId = "  merch_stripe_887   ",
        amount = BigDecimal("12500.00"),
        currency = "IDR",
        timestamp = Instant.now()
    )

    // 3. Eksekusi
    val result = gatewayPipeline.execute(
        initialTransaction = incomingTx,
        onAbort = { reason, tx ->
            System.err.println("[AUDIT REJECTED] Tx: ${tx.id} dropped due to: $reason")
        }
    )

    when (result) {
        is PipelineResult.Success -> {
            println("[PROCESSED] Tx ${result.transaction.id} Clean Merchant: ${result.transaction.merchantId}")
        }
        is PipelineResult.Rejected -> {
            println("[FAILED] Transaction validation failed.")
        }
    }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Parameter | Inline Functions | Regular Functions / Lambdas | Object-Oriented Interfaces (SAM) |
| :--- | :--- | :--- | :--- |
| **Alokasi Heap** | **Nol**. Bytecode disalin langsung. | **Tinggi**. Objek `FunctionN` dibuat jika lambda menangkap *state*. | **Sedang-Tinggi**. Memerlukan instansiasi kelas anonim/konkret. |
| **Ukuran Bytecode** | Dapat **membengkak (*code bloat*)** jika fungsi besar di-inline berkali-kali. | **Konstan**. Bytecode terpusat di satu fungsi. | **Konstan**. Struktur kode terisolasi pada file `.class` terpisah. |
| **Dukungan Return** | Mendukung **Non-local returns** (bisa keluar langsung dari fungsi pemanggil). | Hanya mendukung **local return** (`return@label`). | Hanya mendukung return dari method antarmuka tersebut. |
| **Akses Private API** | **Dibatasi**. Tidak dapat mengakses member `private` dari scope tempat fungsi berada. | **Penuh**. Memiliki akses penuh terhadap private scope kelas pemilik. | **Penuh**. Terikat pada aturan visibilitas encapsulation Java/Kotlin. |
| **Kecepatan Profiling** | Sulit di-trace pada stack trace debugger karena tidak ada call boundary. | Jelas terbaca dalam stack trace JVM (`Function1.invoke`). | Sangat jelas di stack trace JVM sesuai struktur kelas. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Capturing Variable Mutation Pitfall
Saat lambda berjalan di multithreaded context dan menangkap mutable variable lokal, kondisi *race condition* tersembunyi dapat terjadi tanpa peringatan compiler.

```kotlin
// BAHAYA
var counter = 0
val threadPool = java.util.concurrent.Executors.newFixedThreadPool(4)
repeat(1000) {
    threadPool.execute {
        counter++ // Menangkap Ref.IntRef yang tidak thread-safe!
    }
}
```
**Mitigasi**: Gunakan `AtomicInteger` atau hindari *mutation inside closures*.

### 2. Accidental Capture of Outer Class Reference
Jika lambda di dalam class mereferensikan variabel instance atau method dari kelas tersebut, seluruh instance kelas luar akan ditangkap secara implisit:

```kotlin
class HeavyRepository {
    private val largePayload = ByteArray(1024 * 1024 * 64) // 64 MB

    fun provideWorker(): () -> Unit {
        // Pitfall: Mengakses method lokal implicitly captures 'this'
        return { logExecution() } 
    }

    private fun logExecution() = println("Executed")
}
```
**Dampak**: Menahan `HeavyRepository` dari proses Garbage Collection, memicu kebocoran memori (*Memory Leak*).

### 3. Non-Local Returns Breaking Finally Blocks Abruptly
Penggunaan kata kunci `return` di dalam inline lambda akan langsung melompat keluar dari fungsi luar (*enclosing function*), bukan hanya lambdanya:

```kotlin
inline fun runTransaction(block: () -> Unit) {
    println("Begin Transaction")
    block()
    println("Commit Transaction") // Baris ini TIDAK DIEKSEKUSI jika terjadi non-local return
}

fun execute() {
    runTransaction {
        println("Performing Task...")
        return // Non-local return: keluar langsung dari execute()
    }
}
```

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Over-Inlining Large Functions
```kotlin
// SALAH: Fungsi inline memiliki 200 baris logika kompleks
inline fun computeComplexMatrix(crossinline op: () -> Unit) {
    // 200 baris kode...
}
```
*Mengapa Salah*: Setiap pemanggilan akan menduplikasi 200 baris bytecode tersebut. Jika dipanggil di 50 tempat berbeda, terjadi pembengkakan memori program (*code size explosion*) yang merusak instruksi cache CPU (*I-Cache*).
*Koreksi*: Pisahkan inlining hanya pada delegasi lambdanya, delegasikan logika internal ke fungsi privat non-inline.

### 2. Mengabaikan Overhead Alokasi di Hot Loop
```kotlin
// SALAH
fun processBatch(items: List<Int>) {
    items.forEach { item ->
        // Membuat closure baru yang menangkap item jika diteruskan ke HOF non-inline
        registerCallback { print(item) }
    }
}
```
*Koreksi*: Pertahankan callback statis atau gunakan konstruksi data yang tidak melakukan alokasi closure berulang di jalur panas (*hot path*).

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Typealias untuk Fungsional Signature**: Definisikan peran fungsi secara deskriptif (`typealias PaymentHandler = (Payment) -> Result`) daripada menuliskan tipe mentah berulang kali.
2.  **Tempatkan Lambda di Parameter Terakhir**: Selalu posisikan parameter tipe fungsi di urutan terakhir pada deklarasi fungsi agar call site dapat memanfaatkan *trailing lambda syntax*.
3.  **Terapkan Aturan Inline Secara Konsisten**:
    *   Gunakan `inline` **hanya** jika fungsi menerima argumen bertipe fungsi.
    *   Jangan gunakan `inline` pada fungsi biasa tanpa argumen fungsi (compiler Kotlin akan mengeluarkan peringatan performa).
4.  **Immutabilitas Default**: Rancang fungsional pipeline agar menerima dan menghasilkan data *immutable* (`data class` dengan properti `val`).
5.  **Gunakan Sequence untuk Chain Fungsional Panjang**: Ketika melakukan chaining operasi koleksi (`map`, `filter`, `take`) pada dataset besar (>1000 item), gunakan `.asSequence()` untuk menghindari instansiasi list perantara di setiap step.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Evaluasi Alokasi Memori: Lambda Biasa vs Inline

Perhatikan pengujian dekompilasi bytecode ini:

```kotlin
// NON-INLINE HOF
fun calculateStandard(op: () -> Int): Int = op()

// INLINE HOF
inline fun calculateOptimized(op: () -> Int): Int = op()
```

Saat dipanggil:
```kotlin
fun bench() {
    val a = calculateStandard { 40 + 2 }
    val b = calculateOptimized { 40 + 2 }
}
```

Mekanisme Bytecode (Representasi Javap):
*   `calculateStandard`: Menghasilkan instruksi:
    ```bytecode
    GETSTATIC ExampleKt$bench$1.INSTANCE : LExampleKt$bench$1;
    CHECKCAST kotlin/jvm/functions/Function0
    INVOKESTATIC ExampleKt.calculateStandard (Lkotlin/jvm/functions/Function0;)I
    ```
    *(Memerlukan pemanggilan antarmuka polimorfik via `INVOKEINTERFACE`)*.
*   `calculateOptimized`: Diringkas langsung menjadi:
    ```bytecode
    BIPUSH 42
    ISTORE 1
    ```
    *(Zero overhead: Compiler melakukan kalkulasi konstanta dan meniadakan method call boundary)*.

### Profiling Garbage Collection
Pada perulangan $10.000.000$ iterasi:
*   Non-inline capturing lambda menghasilkan $\sim 240\text{ MB}$ alokasi heap dari objek `Function` sementara, memicu GC Minor berulang kali.
*   Inline function mempertahankan metrik alokasi heap di angka **$0\text{ bytes}$**.

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Pencegahan Resource Leak Melalui Lambdas**: Pastikan lambda yang menangkap *AutoCloseable* dibungkus dengan idiomatis via `.use { ... }` untuk memastikan pembebasan *file descriptor* atau koneksi basis data saat terjadi runtime failure di dalam block lambda:
    ```kotlin
    inline fun <T : AutoCloseable, R> T.use(block: (T) -> R): R
    ```
2.  **Isolasi Konteks Receiver**: Saat mendesain Type-Safe Builder DSL, gunakan anotasi `@DslMarker` untuk mencegah pencemaran scope implisit yang dapat memicu eksekusi method receiver luar tanpa disengaja.

```kotlin
@DslMarker
annotation class PipelineDsl

@PipelineDsl
class SecurePipelineBuilder { ... }
```

3.  **Boundary Exception Handling**: Jangan biarkan Higher-Order Function membiarkan exception lolos tanpa pembersihan context keamanan (seperti clearing tokens dari memori):
    ```kotlin
    inline fun withSecurityContext(token: SecurityToken, block: () -> Unit) {
        try {
            SecurityContextHolder.set(token)
            block()
        } finally {
            SecurityContextHolder.clear() // Mencegah Token Hijacking via ThreadLocal leak
        }
    }
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging lambda memerlukan pendekatan khusus akibat karakteristik runtime anonimnya:

### 1. Stack Trace Sanitization
Di Java runtime, lambda non-inline muncul sebagai `ExampleKt$main$1.invoke(Unknown Source)`.
Untuk mempermudah observabilitas, berikan nama kontekstual pada fungsi lambda menggunakan *Method References* alih-alih anonymous block:

```kotlin
// Stack trace ambigu:
metrics.filter { it.value > 10 } 

// Stack trace eksplisit: ClassName::validationMethodName
metrics.filter(::isThresholdExceeded)
```

### 2. Breakpoint Traps
Di IntelliJ IDEA / Android Studio:
*   Gunakan fitur **Method Breakpoint** spesifik pada deklarasi lambda line.
*   Pilih opsi hit breakpoint pada **Lambda Only** vs **Line Only** saat breakpoint berada di satu baris yang sama dengan pemanggilan HOF:

```
[Breakpoint: Stop here only inside the lambda, not when entering map()]
metrics.map { it.amount * 2 }
```

### 3. Bytecode Inlining Stack Frames
Jika fungsi di-inline, informasi frame stack call-nya hilang dari JVM backtrace. Kotlin menyematkan tabel baris `SMAP` (Source Map) pada file `.class` untuk membantu debugger memetakan kembali baris bytecode inlined ke baris asli di file sumber Kotlin.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```kotlin
// Sintaks Lambda Ringkas
val noArg: () -> Unit = { println("Ping") }
val withArgs: (Int, Int) -> Int = { x, y -> x + y }
val singleArgShorthand: (String) -> Int = { it.length }

// Function Literal with Receiver
val dslBlock: StringBuilder.() -> Unit = { append("OK") }

// Modifikator Inlining Matrix
inline fun fullInline(a: () -> Unit) { a() }
inline fun selectiveInline(a: () -> Unit, noinline b: () -> Unit) { a(); b() }
inline fun asyncInline(crossinline c: () -> Unit) { Thread { c() }.start() }

// Non-Local Returns
inline fun inlineEnclosing() {
    fullInline {
        return // Keluar dari inlineEnclosing()
    }
}

fun nonInlineEnclosing() {
    listOf(1, 2).forEach {
        if (it == 1) return@forEach // Local return (lanjut ke iterasi berikutnya)
    }
}
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Level Dasar (Basic)

1.  **Apa perbedaan mendasar antara anonymous function dan lambda expression di Kotlin dalam hal return statement?**
    *   *Jawaban*: Lambda expression tanpa modifikasi label mengeksekusi *non-local return* jika berada di inline function (keluar dari enclosing function), sedangkan anonymous function berperilaku layaknya fungsi biasa: statement `return` hanya keluar dari lingkup anonymous function itu sendiri.
2.  **Kapan compiler Kotlin menginstansiasi objek baru untuk sebuah lambda pada runtime JVM?**
    *   *Jawaban*: Ketika fungsi tersebut tidak berstatus `inline` dan lambda tersebut menangkap variabel dari scope luarnya (*closure capturing*).
3.  **Apa yang dimaksud dengan kata kunci `it` pada deklarasi lambda?**
    *   *Jawaban*: `it` adalah penamaan implisit yang disediakan compiler secara otomatis untuk lambda yang hanya memiliki tepat satu parameter masukan.
4.  **Mengapa fungsi lambda `() -> Unit` tetap menghasilkan return value di level JVM?**
    *   *Jawaban*: Di level JVM, fungsi tersebut mengembalikan singleton instance `kotlin.Unit.INSTANCE` untuk memenuhi kontrak generic `FunctionN<R>`.
5.  **Dapatkah parameter bertipe lambda disimpan ke dalam variabel lokal di dalam fungsi yang di-inline tanpa modifikator?**
    *   *Jawaban*: Tidak. Parameter inline lambda harus dieksekusi langsung atau diteruskan ke inline parameter lain. Jika ingin menyimpannya ke variabel, parameter tersebut harus diberi modifikator `noinline`.

---

### Level Menengah (Intermediate)

6.  **Jelaskan skenario di mana penggunaan kata kunci `inline` justru memperburuk performa aplikasi.**
    *   *Jawaban*: Ketika fungsi yang diberi modifikator `inline` memiliki tubuh kode yang sangat panjang dan dipanggil di banyak lokasi pada aplikasi. Ini mengakibatkan code bloat di bytecode, meningkatkan footprint memori aplikasi, dan merusak performa CPU instruction cache.
7.  **Apa tujuan penggunaan modifikator `crossinline` pada parameter fungsi higher-order?**
    *   *Jawaban*: Mencegah lambda melakukan *non-local return* saat lambda tersebut harus dieksekusi di dalam konteks eksekusi lain (seperti objek Runnable atau nested higher-order function yang tidak inline), menjaga integritas runtime stack control flow.
8.  **Bagaimana Kotlin mengizinkan mutasi variabel primitif lokal (misalnya `var sum = 0`) di dalam closure?**
    *   *Jawaban*: Compiler secara transparan mengubah variabel lokal tersebut menjadi referensi objek pembungkus di heap (misalnya `Ref.IntRef`), di mana field publik `element` di dalamnya dimutasi oleh closure.
9.  **Jelaskan mekanisme kerja `@DslMarker` dalam membatasi akses scope receiver pada nested lambda builders.**
    *   *Jawaban*: `@DslMarker` membuat marker anotasi yang melarang akses implisit ke anggota receiver terluar jika dua receiver dari grup domain marker yang sama berada dalam tingkat nest yang bertumpuk. Pemanggilan ke receiver luar harus dilakukan dengan `this@OuterScope` eksplisit.
10. **Apa perbedaan evaluasi performa antara `list.map {}.filter {}` vs `list.asSequence().map {}.filter {}.toList()`?**
    *   *Jawaban*: Operasi pada `List` bersifat *eager*, menghasilkan koleksi intermediate baru di memori pada setiap pemanggilan method chain. Sedangkan `Sequence` dievaluasi secara *lazy*, memproses elemen satu per satu melewati seluruh pipeline pemrosesan tanpa mengalokasikan koleksi perantara di setiap tahap.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Instruksi Praktikum
Rancanglah sebuah **Event-Driven Audit Logging Engine** berkinerja tinggi yang mengadopsi prinsip functional programming murni.

### Spesifikasi Teknis:
1.  **State Representation**: Buat domain model immutable `AuditEvent(val eventId: String, val payload: String, val level: LogLevel, val timestamp: Long)`.
2.  **DSL Builder**: Buat DSL bernama `auditProcessor { ... }` menggunakan *Lambda with Receiver* yang memungkinkan pengguna meregistrasi *custom filter* dan *sink output* (misal: ConsoleSink, FileSink).
3.  **Higher-Order Inlined Filter**: Implementasikan fungsi filter inline yang mengeksekusi transformasi event tanpa alokasi memori objek runtime.
4.  **Error Handling Strategy**: Gunakan functional type `Result<T>` untuk membungkus keberhasilan penanganan event, memastikan tidak ada raw unhandled exceptions yang menghentikan pipeline.

### Target Eksekusi Uji
*   Mampu memproses batch minimal $100.000$ mock event secara asinkron tanpa memicu alokasi heap berlebih pada objek wrapper middleware.
*   Cegah non-local return dari lambda filter menggunakan modifikator `crossinline` jika pemrosesan diserahkan ke thread pool worker.
*   Validasi stack trace melalui profiler JVM (seperti VisualVM atau IntelliJ Profiler) untuk memverifikasi inlining bytecode.