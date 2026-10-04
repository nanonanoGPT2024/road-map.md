# Kurikulum Enterprise: Kotlin Engine & System Architecture
## BAB 01: Fondasi dan Arsitektur
### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer memiliki kapabilitas tingkat enterprise untuk:
*   Menganalisis dan mengoptimalkan pipeline kompilasi Kotlin 2.0 (K2 Compiler: FIR dan IR Backend) serta dampaknya terhadap JVM bytecode.
*   Mengimplementasikan sistem tipe lanjutan (*advanced type system*) berbasis *declaration-site variance* (`out`/`in`), *type projections*, dan *star-projections* tanpa kompromi pada *type-safety* dan performa *runtime*.
*   Meniadakan *heap allocation overhead* dan *GC pressure* pada *high-throughput system* menggunakan *inline value classes* (`@JvmInline value class`) serta memahami *de-sugaring* internalnya.
*   Merancang API domain yang deklaratif menggunakan *Kotlin Contracts* untuk memandu *smart-casting engine* dan menjamin kepatuhan *state invariant*.
*   Mendiagnosis serta mengeliminasi *performance penalty* akibat *autoboxing*, *reflection metadata overhead*, dan *synthetic accessor generation* pada JVM target.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, engineer wajib menguasai:
*   **Fondasi Sintaksis Kotlin & JVM Basics**: Class, interface, inheritance, basic generics, object allocation, stack vs. heap memory model.
*   **Java Memory Model (JMM)**: Prinsip dasar *Garbage Collection* (ZGC/G1GC), *memory barriers*, dan *thread visibility*.
*   **CLI & Tooling**: Pemahaman eksekusi `javap -c -v` (bytecode inspection), Gradle build life-cycle, dan Kotlin 2.0 CLI compiler (`kotlinc`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Pipeline Kompilasi Kotlin 2.0 (K2 Engine)

Arsitektur compiler Kotlin 2.0 menggantikan frontend lama (FE 1.0 yang berbasis AST dan semantic analysis ganda via PSI) dengan arsitektur baru berbasis **FIR (Frontend Intermediate Representation)**.

```
[Kotlin Source Code (.kt)]
           │
           ▼
[Lexing & Parsing] ────────► [PSI (Program Structure Interface)]
                                     │
                                     ▼
                      [FIR (Frontend Intermediate Representation)]
                                     │
                                     ├─► Resolution & Type Inference
                                     ├─► Kotlin Contracts Checker
                                     └─► Control Flow Analysis (CFA)
                                     │
                                     ▼
                      [IR (Kotlin Intermediate Representation)]
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
       [JVM IR]                  [JS IR]                 [Native IR]
            │
  [JVM Bytecode Generator]
            │
            ▼
[Class Files & Metadata (.class)]
```

1.  **Frontend (FIR)**: Menghasilkan representasi data semantik yang berorientasi pada compiler AST ringkas. FIR melakukan *type inference* berbasis constraint solvers terbaru, memastikan kecepatan kompilasi naik hingga 200% dibanding FE 1.0.
2.  **Contracts & Control Flow Analysis (CFA)**: Terintegrasi langsung di layer FIR. Kompilator membuktikan validitas post-kondisi dan eksekusi blok (`callsInPlace`) sebelum menurunkan struktur ke IR.
3.  **Backend (IR)**: Transformasi pohon FIR menjadi Kotlin Intermediate Representation (IR). Di tahap ini, fitur spesifik Kotlin (seperti `inline value class`, *default arguments*, *coroutines transformation*, dan *properties*) di-*lower* (ditransformasikan menjadi struktur primitif).
4.  **Bytecode Generation**: JVM backend menerjemahkan JVM IR langsung ke Java bytecode standard (termasuk instruksi Java 8/11/17/21 seperti `invokedynamic`).

#### 3.2 Advanced Generics: Variance & Type Lattice

Sistem tipe Kotlin adalah *semi-lattice* dengan tipe teratas `Any?` dan tipe terbawah `Nothing`.

```
                  Any?  <--- [Supertype dari semua tipe, nullable]
                 /    \
               Any     Nullable Types (String?, Int?, etc.)
              /   \      /
        String     Int  /
              \    /   /
             Nothing? /
                │    /
             Nothing   <--- [Subtype dari semua tipe non-null, unhabited]
```

*   **Declaration-Site Variance**: Mengatasi keterbatasan Java *wildcards* (`? extends T`, `? super T`) dengan mendeklarasikannya langsung pada definisi tipe interface/class:
    *   `out T` (*Covariant*): Memproduksi data. Subtyping dipertahankan: `Producer<Derived>` adalah subtype dari `Producer<Base>`. Tipe `T` hanya boleh berada di posisi output (*return type*).
    *   `in T` (*Contravariant*): Mengonsumsi data. Subtyping dibalik: `Consumer<Base>` adalah subtype dari `Consumer<Derived>`. Tipe `T` hanya boleh berada di posisi input (*parameter type*).
*   **Invariant**: Default generic `Container<T>`. Tidak ada hubungan subtyping antara `Container<Derived>` dan `Container<Base>`.

#### 3.3 Anatomi Memory `@JvmInline value class`

Secara default, abstraksi domain (seperti `class UserId(val value: UUID)`) memaksa alokasi objek terpisah di *heap*, menimbulkan *object header overhead* (12-16 byte), *padding*, serta referensi dereferencing (pointer chasing).

`@JvmInline value class` memecahkan masalah ini dengan meratakan struktur data ke tipe dasarnya (*unboxed*) selama runtime:
*   Jika disimpan dalam variabel lokal atau dipassing ke fungsi yang menerima tipe *inline class* secara spesifik, compiler menggantinya secara langsung dengan *primitive/underlying reference type* di level bytecode (zero-allocation).
*   **Name Mangling**: Untuk mencegah tabrakan *signature method* pada level bytecode (karena tipe asli di-unwrap menjadi tipe yang sama), Kotlin menambahkan *hash suffix* pada nama method:
    *   Kotlin: `fun process(id: OrderId)`
    *   Bytecode JVM: `public final void process-mZ3uKQE(String id)`
*   **Boxing Triggers**: Boxing ke heap tetap terjadi jika *value class* di-cast ke interface yang diimplementasikannya, disimpan di Generic Container tak terspesifikasi (`List<OrderId>`), atau diperlakukan sebagai nullable (`OrderId?`).

#### 3.4 Kotlin Contracts Engine

*Kotlin Contracts* menyediakan mekanisme formal bagi developer untuk memberitahukan compiler mengenai properti eksekusi method yang tidak dapat disimpulkan secara otomatis oleh *static analyzer*:
1.  **Returns / ReturnsNotNull**: Menggaransi nilai kembalian mengimplikasikan kondisi ekspresi boolean tertentu bernilai *true* (misal: jika method mengembalikan `true`, maka argumen dijamin non-null $\rightarrow$ memicu *smart-cast*).
2.  **CallsInPlace**: Menggaransi berapa kali *higher-order function parameter* (lambda) dieksekusi selama pemanggilan method (`InvocationKind.EXACTLY_ONCE`, `AT_LEAST_ONCE`, `AT_MOST_ONCE`). Ini memungkinkan inisialisasi variabel `val` lokal di dalam lambda.

---

### 4. Why & What

| Fitur | What (Apa Mekanismenya) | Why (Alasan Rekayasa / Masalah yang Diselesaikan) |
| :--- | :--- | :--- |
| **K2 IR Architecture** | Transformasi pipeline kompilasi menggunakan representasi FIR dan IR terkonsolidasi. | Menghilangkan duplikasi logika antar platform (JVM, JS, Native), mempercepat *build time*, dan memungkinkan plugin compiler (*compiler plugins* seperti Compose, Serialization) beroperasi stabil. |
| **Declaration-Site Variance** | Penandaan varians (`in`/`out`) pada definisi tipe, bukan di setiap pemanggilan (*use-site*). | Mengeliminasi redundansi *wildcards* Java yang rentan kesalahan (`List<? extends Number>`), menghasilkan *clean domain interfaces* tanpa kompromi *type safety*. |
| **Value Classes (`@JvmInline`)** | Wrapper bertipe kuat yang diratakan (*unboxed*) saat kompilasi. | Mengatasi dilema antara *Domain-Driven Design* (menghindari Primitive Obsession) dan *SLA Latency*. Memberikan *type safety* tanpa beban Garbage Collection (*Zero Heap Allocation*). |
| **Kotlin Contracts** | DSL level compiler untuk menyuntikkan post-condition constraints. | Menghilangkan assertion boilerplate, menghindari unsafe casting (`as T`), dan membuat custom utility functions memiliki kemampuan *smart-casting* setara operator bawaan compiler. |

---

### 5. How (Workflow Detail)

Alur kerja eksekusi optimasi memori dan validasi tipe di compiler:

```
[Inisiasi Definisi Value Class & Functions]
                   │
                   ▼
  [Analisis Kontrak FIR (CallsInPlace / Returns)]
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
[Kontrak Valid?]             [Kontrak Tidak Valid]
    │                             │
    │ Ya                          └─► [Compile Error: Contract Violation]
    ▼
[Cek Penggunaan Generic: Declaration & Use-site Variance]
    │
    ├─► Validasi: out types hanya diekspos sebagai Producer
    └─► Validasi: in types hanya diekspos sebagai Consumer
    │
    ▼
[K2 Lowering Phase: IR Transformation]
    │
    ├─► Unboxing Value Classes (menjadi primitive/underlying type)
    ├─► Mangling nama fungsi yang menerima parameter Value Class
    └─► Desugaring Contracts ke bytecode checks standar
    │
    ▼
[Bytecode Emission (JVM Bytecode)]
    │
    ├─► Memastikan instruksi INVOKEVIRTUAL/INVOKESTATIC sesuai mangled name
    └─► Eliminasi boxing jika tidak ada polymorphism/generics casting
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengemasan dan Labeling Bandara (Value Class vs Heap Object)

*   **Standar Object (Heap Object)**: Anda mengirim sebuah baut kecil, tetapi harus dimasukkan ke dalam boks berukuran 10x10 cm, dilapisi bubble wrap tebal, diberi barcode, dan dimasukkan ke manifes bagasi kargo. Biaya handling (GC) tinggi, ruang kargo penuh sesak.
*   **Value Class (Unboxed)**: Anda cukup mengantongi baut tersebut di saku kemeja Anda. Tidak ada kardus, tidak ada manifes tambahan. Anda membawa baut secara langsung, tetapi sistem keamanan bandara (Compiler) tetap mencatat bahwa baut itu legal dan milik Anda.

```
MEMORI HEAP (Java Standard Wrapper):
┌────────────────────────────────────────────────────────┐
│ Heap Object: OrderId                                   │
│  - Mark Word (8 bytes)                                 │
│  - Klass Pointer (4-8 bytes)                           │
│  - Padding & Alignment (4 bytes)                       │
│  - Primitive Value Ref ────────► [ "ORD-991204" String]│
└────────────────────────────────────────────────────────┘
Total: ~24 - 32 bytes per instance overhead

MEMORI STACK DENGAN @JvmInline value class:
┌────────────────────────────────────────────────────────┐
│ JVM Stack Frame (Execution Thread)                     │
│  - Local Variable Slot 1: [ "ORD-991204" Ref ]         │
│    (Tidak ada alokasi wrapper object di heap!)         │
└────────────────────────────────────────────────────────┘
Overhead: 0 bytes.
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Variance & Contracts

```kotlin
package com.enterprise.foundations

import kotlin.contracts.ExperimentalContracts
import kotlin.contracts.contract

// 1. Declaration-site Variance
interface ReadOnlyRepository<out T> {
    fun findById(id: String): T? // Valid: T di posisi 'out'
    // fun save(item: T)         // COMPILE ERROR: Type parameter T is declared as 'out' but occurs in 'in' position
}

// 2. Kotlin Contracts Implementation
@OptIn(ExperimentalContracts::class)
fun requireValidToken(token: String?): Boolean {
    contract {
        returns(true) implies (token != null)
    }
    return !token.isNullOrBlank() && token.startsWith("ey")
}

fun authenticate(token: String?) {
    if (requireValidToken(token)) {
        // Compiler melakukan smart-cast otomatis dari String? ke String
        println("Token length: ${token.length}") 
    }
}
```

#### 7.2 Practical Example: High-Throughput Matching Engine Type Architecture

Sistem Order Matching Engine finansial tanpa alokasi heap berlebih menggunakan *Value Classes*, *Strict Variances*, dan *Contracts*.

```kotlin
package com.enterprise.engine

import java.util.UUID
import kotlin.contracts.ExperimentalContracts
import kotlin.contracts.contract
import kotlin.contracts.InvocationKind

// Domain Primitives dengan Zero Allocation
@JvmInline
value class InstrumentId(val raw: String) {
    init {
        require(raw.isNotBlank()) { "InstrumentId must not be blank" }
    }
}

@JvmInline
value class ExecutionPrice(val scaledValue: Long) {
    // scaledValue menyimpan harga dengan 4 desimal (e.g. 100.50 -> 1005000L)
    companion object {
        private const val SCALE = 10_000L
        fun fromDouble(value: Double): ExecutionPrice = ExecutionPrice((value * SCALE).toLong())
    }
    fun toDouble(): Double = scaledValue.toDouble() / SCALE
}

// Hierarchy State Order
sealed interface OrderState
object Pending : OrderState()
object Executed : OrderState()
data class Rejected(val reason: String) : OrderState()

// Covariant Container Interface
interface ReadOnlyOrder<out S : OrderState> {
    val id: UUID
    val instrument: InstrumentId
    val price: ExecutionPrice
    val state: S
}

data class Order<S : OrderState>(
    override val id: UUID,
    override val instrument: InstrumentId,
    override val price: ExecutionPrice,
    override val state: S
) : ReadOnlyOrder<S>

// Enterprise Contract-driven Transaction Engine
@OptIn(ExperimentalContracts::class)
inline fun <T, R> runAtomicTransaction(resource: T, block: (T) -> R): R {
    contract {
        callsInPlace(block, InvocationKind.EXACTLY_ONCE)
    }
    // Setup context, tracing, synchronization
    val startTime = System.nanoTime()
    try {
        return block(resource)
    } finally {
        val duration = System.nanoTime() - startTime
        // Emisi telemetry tanpa garbage creation
        println("Transaction finished in ${duration}ns")
    }
}

// Validator dengan Custom Contract Smart Cast
@OptIn(ExperimentalContracts::class)
fun validatePreTradeInvariants(order: ReadOnlyOrder<OrderState>): Boolean {
    contract {
        returns(true) implies (order.state is Pending)
    }
    return order.state is Pending && order.price.scaledValue > 0L
}

// Core Engine Executor
class MatchingEngineCore {
    fun processOrder(order: ReadOnlyOrder<OrderState>) {
        if (validatePreTradeInvariants(order)) {
            // Compiler secara otomatis memvalidasi order.state bertipe Pending
            executeOrderInternal(order as ReadOnlyOrder<Pending>)
        } else {
            throw IllegalArgumentException("Order ${order.id} is invalid for execution")
        }
    }

    private fun executeOrderInternal(order: ReadOnlyOrder<Pending>) {
        val result: Order<Executed>
        
        // Membuktikan kontrak EXACTLY_ONCE: compiler mengizinkan inisialisasi val
        runAtomicTransaction(order) { validOrder ->
            println("Processing trade for ${validOrder.instrument.raw} at ${validOrder.price.toDouble()}")
            result = Order(
                id = validOrder.id,
                instrument = validOrder.instrument,
                price = validOrder.price,
                state = Executed
            )
        }

        // Variabel 'result' dijamin telah diinisialisasi oleh compiler
        println("Completed Order: ${result.id} -> State: ${result.state}")
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Core Banking Payment Gateway memproses rata-rata 35.000 TPS (*Transactions Per Second*) dengan peak hingga 70.000 TPS. Tim SRE mendeteksi lonjakan latency P99 dari 8ms naik menjadi 180ms setiap selang 45 detik.

#### Analisis Akar Masalah (Root Cause Analysis)
1.  **Heap Profiling**: Menggunakan Async-profiler dan JFR (Java Flight Recorder), ditemukan bahwa 42% dari total alokasi memori dihasilkan oleh pembuatan *wrapper objects*: `AccountId`, `CurrencyCode`, dan `TransactionAmount`.
2.  **GC Pause**: Lonjakan P99 berkorelasi langsung dengan *Stop-The-World (STW)* phase pada Garbage Collector (G1GC) yang tertekan oleh jutaan objek berumur pendek (*short-lived wrapper objects* pada Eden space).
3.  **Reflection Bottleneck**: Serialisasi entity menggunakan *runtime reflection* berbasis `KClass.members` yang mengunci metaspace cache.

```
Kondisi Sebelum Optimasi:
[35,000 TPS] ──► [Alokasi 105,000 Wrapper/detik] ──► [Eden Space Cepat Penuh]
                                                               │
                                                               ▼
[Latency P99 Spike: 180ms] ◄── [STW Young GC Spike] ◄── [GC Pressure Tinggi]
```

#### Solusi Rekayasa
1.  **Refactoring ke `@JvmInline value class`**:
    Mengubah seluruh entity identifier dan value types finansial menjadi `value class`. Mengubah method internals agar menggunakan raw-type unboxing.
2.  **Eliminasi Boxing pada Koleksi**:
    Koleksi generic seperti `List<AccountId>` memaksa terjadinya autoboxing ke heap. Diganti dengan custom primitive primitive arrays atau array flat layout `LongArray` yang dibungkus dalam *high-performance off-heap / inline buffer interface*.
3.  **Implementasi Kotlin Contracts**:
    Mengganti defensive-checking framework yang melempar exception berbasis runtime dengan kompilasi kontrak statis, memangkas eksekusi branch prediction miss pada CPU.

#### Hasil Metrik Produksi

```
+-----------------------------------+--------------------+--------------------+
| Metrik Produksi                   | Sebelum Optimasi   | Pasca Optimasi     |
+-----------------------------------+--------------------+--------------------+
| Eden Memory Allocation Rate       | 4.2 GB / detik     | 1.1 GB / detik     |
| P99 Latency                       | 180 ms             | 6.2 ms             |
| CPU Utilization (STW GC Time)     | 18.5% total CPU    | 1.2% total CPU     |
| Max Throughput Capable            | 42,000 TPS         | 88,000 TPS         |
+-----------------------------------+--------------------+--------------------+
```

---

### 9. Trade-offs

| Pendekatan / Fitur | Keuntungan | Biaya / Konsekuensi (Trade-off) | Rekomendasi Penggunaan |
| :--- | :--- | :--- | :--- |
| **`@JvmInline value class`** | Meniadakan overhead heap (zero-allocation), ramah CPU L1/L2 cache, tipe aman. | Memaksa *name mangling* di bytecode (sulit dipanggil dari Java legacy). Boxed secara diam-diam bila dilempar ke interface polymorphic atau tipe nullable. | Sangat disarankan untuk Domain IDs, Nilai Finansial, dan Typed Unit metrics. Hindari pemakaian jika interface polymorphism sering dipanggil. |
| **Kotlin Contracts** | Smart cast akurat, code coverage clean, zero runtime penalty (hilang pasca kompilasi). | Fitur masih bertatus `@ExperimentalContracts`. Syntax ketat dan compiler tidak dapat memverifikasi isi logika eksekusi contracts (developer menanggung risiko *false promise*). | Utility functions level framework/platform core. Jangan digunakan untuk validation logic bisnis yang dinamis. |
| **Declaration-Site Variance (`in`/`out`)** | Konsistensi API tinggi, tidak perlu mengulang `? extends` pada ratusan *call-site*. | Sangat kaku. Begitu tipe didefinisikan sebagai `out`, tipe tersebut tidak dapat menerima data sebagai parameter fungsi tanpa cast tak aman (`@UnsafeVariance`). | Ideal untuk Read-Only DTOs, Event Sourcing streaming interfaces, dan Service Repositories. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Silent Boxing pada Inline Value Classes

**Kesalahan Fatal**: Mengabaikan boxing implisit yang memicu alokasi heap tak terduga.

```kotlin
interface Identifiable

@JvmInline
value class AccountId(val id: Long) : Identifiable

fun process(account: Identifiable) { /* ... */ }

fun execute() {
    val accId = AccountId(12345L)
    process(accId) // MEMICU ALLOCATION! Boxing terjadi karena konversi ke Interface
    
    val list: List<AccountId> = listOf(accId) // MEMICU ALLOCATION! Boxing terjadi karena Generic Type Erasure
}
```

*Troubleshooting*: Periksa bytecode menggunakan CLI:
```bash
javap -c -p AccountIdKt.class
```
Cari instruksi JVM: `NEW com/enterprise/AccountId` atau `INVOKESTATIC com/enterprise/AccountId.box-impl`. Jika instruksi tersebut muncul di *hot path*, ubah parameter fungsi dari Interface ke tipe konkret, atau manfaatkan Generic type parameter yang spesifik.

#### 10.2 Kontrak Palsu (Broken Contract Invariant)

**Kesalahan Fatal**: Menyatakan kontrak yang tidak sinkron dengan implementasi sebenarnya. Ini merusak *soundness* kompilator dan menghasilkan `NullPointerException` atau `ClassCastException` di runtime.

```kotlin
@OptIn(ExperimentalContracts::class)
fun brokenCheck(data: Any?): Boolean {
    contract {
        returns(true) implies (data is String)
    }
    // Bug implementasi: Logika tidak konsisten dengan kontrak yang dideklarasikan
    return data != null // Jika data bertipe Int, fungsi mengembalikan true!
}

fun main() {
    val num: Any? = 100
    if (brokenCheck(num)) {
        // Kotlin Compiler berasumsi 'num' adalah String berdasarkan kontrak palsu
        val str = num as String // RUNTIME EXCEPTION: ClassCastException (Integer cannot be cast to String)
    }
}
```

*Mitigasi*: Buat Unit Test ekstensif untuk setiap fungsi yang memiliki kontrak. Uji cabang branch positif dan negatif.

#### 10.3 Pelanggaran Variance menggunakan `@UnsafeVariance` Tanpa Immutability Guarantees

```kotlin
// BAHAYA: Mengizinkan mutasi pada objek covariant
class CovariantBuffer<out T>(private val items: MutableList<@UnsafeVariance T>) {
    fun addItem(item: @UnsafeVariance T) { // Mengelabui compiler
        items.add(item)
    }
}
```
*Solusi*: `@UnsafeVariance` hanya boleh digunakan pada operasi pembacaan murni atau pembandingan yang terbukti secara matematis aman (seperti `contains` atau `indexOf` pada `List<out E>`).

---

### 11. Best Practices (Production Checklist)

*   [ ] **Strict Value Class Usage**: Gunakan `@JvmInline value class` untuk seluruh ID domain entity (contoh: `TenantId`, `UserId`, `TransactionId`). Hindari Primitive Obsession.
*   [ ] **Prevent Accidental Boxing**: Pastikan method pada *hot path* menerima tipe *value class* secara langsung, bukan melalui polymorphism interface atau raw `Any`.
*   [ ] **K2 Compiler Readiness**: Tambahkan flag compiler `-Xjdk-release=21` dan `-progressive` untuk mengaktifkan pipeline K2 FIR dengan analitik tipe paling ketat.
*   [ ] **ABI Stability for Mangled Functions**: Jika Kotlin module dikonsumsi oleh Java consumer, sertakan anotasi `@JvmName` pada method publik yang menerima *value class* agar Java dapat mengaksesnya tanpa nama hashing buatan compiler.
*   [ ] **Contract Auditing**: Batasi penulisan custom `kotlin.contracts` hanya pada library/infrastruktur internal yang telah diaudit oleh Principal Engineer.
*   [ ] **Explicit Variance Propagation**: Deklarasikan variance pada layer teratas (interface abstraksi) menggunakan `out` (bila purely immutable producer) atau `in` (bila consumer).
*   [ ] **Bytecode Verification in CI/CD**: Jalankan task otomatisasi (seperti bytecode assertion tests) untuk memastikan tidak ada alokasi `box-impl` pada package *hot path/performance-critical*.

---

### 12. Hands-on Practice

Implementasikan project mini engine di direktori: `hands-on/m02/`

#### Struktur Folder
```
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── kotlin/
            └── com/
                └── enterprise/
                    └── advanced/
                        ├── Model.kt
                        ├── Pipeline.kt
                        └── Application.kt
```

#### Langkah 1: Siapkan `build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm") version "2.0.0"
    application
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

kotlin {
    jvmToolchain(21)
    compilerOptions {
        freeCompilerArgs.addAll("-Xcontext-receivers", "-opt-in=kotlin.contracts.ExperimentalContracts")
    }
}

application {
    mainClass.set("com.enterprise.advanced.ApplicationKt")
}
```

#### Langkah 2: Buat Data Model Bebas Alokasi (`src/main/kotlin/.../Model.kt`)
```kotlin
package com.enterprise.advanced

@JvmInline
value class TraceId(val id: String) {
    init {
        require(id.length >= 8) { "Invalid TraceId" }
    }
}

@JvmInline
value class Nanoseconds(val value: Long)

sealed interface TelemetryState
object Captured : TelemetryState()
object Enriched : TelemetryState()

data class TelemetryEvent<out S : TelemetryState>(
    val traceId: TraceId,
    val timestamp: Nanoseconds,
    val state: S,
    val payload: Map<String, String>
)
```

#### Langkah 3: Rancang Pipeline Engine dengan Contracts (`src/main/kotlin/.../Pipeline.kt`)
```kotlin
package com.enterprise.advanced

import kotlin.contracts.ExperimentalContracts
import kotlin.contracts.contract
import kotlin.contracts.InvocationKind

object EventPipelineValidator {
    @OptIn(ExperimentalContracts::class)
    fun isReadyForEnrichment(event: TelemetryEvent<TelemetryState>): Boolean {
        contract {
            returns(true) implies (event.state is Captured)
        }
        return event.state is Captured && event.payload.isNotEmpty()
    }
}

@OptIn(ExperimentalContracts::class)
inline fun <T> measureThroughput(block: () -> T): T {
    contract {
        callsInPlace(block, InvocationKind.EXACTLY_ONCE)
    }
    val start = System.nanoTime()
    return try {
        block()
    } finally {
        println("Execution completed in ${System.nanoTime() - start} ns")
    }
}
```

#### Langkah 4: Tulis Main Driver (`src/main/kotlin/.../Application.kt`)
```kotlin
package com.enterprise.advanced

fun main() {
    val initialEvent: TelemetryEvent<TelemetryState> = TelemetryEvent(
        traceId = TraceId("trace-prod-0099"),
        timestamp = Nanoseconds(System.nanoTime()),
        state = Captured,
        payload = mapOf("event" to "ORDER_PROCESSED")
    )

    measureThroughput {
        if (EventPipelineValidator.isReadyForEnrichment(initialEvent)) {
            // Smart cast membuktikan initialEvent.state adalah Captured
            val enriched = TelemetryEvent(
                traceId = initialEvent.traceId,
                timestamp = initialEvent.timestamp,
                state = Enriched,
                payload = initialEvent.payload + mapOf("enriched_by" to "node-eu-1")
            )
            println("Event successfully advanced to: ${enriched.state}")
        }
    }
}
```

#### Langkah 5: Kompilasi dan Inspeksi Bytecode
Eksekusi dari terminal:
```bash
gradle build
javap -c -v build/classes/kotlin/main/com/enterprise/advanced/ModelKt.class
```
Verifikasi bahwa tidak ada alokasi object untuk `TraceId` pada local variable stack.

---

### 13. Exercise

#### Level Easy
Buat sebuah value class `@JvmInline value class Port(val value: Int)` dengan batasan range `1..65535` pada blok `init`. Buat fungsi `isPrivilegedPort(port: Port): Boolean` yang mengecek apakah port bernilai `< 1024`.
*Kriteria Sukses*: Kompilasi bersih, melempar `IllegalArgumentException` saat port bernilai 0 atau 70000, dan inspeksi javap menunjukkan fungsi menerima tipe primitif `int`.

#### Level Medium
Definisikan interface `Transformation<in Input, out Output>`. Buat implementasi yang menerima tipe `String` (sebagai input contravariant) dan mengembalikan tipe `Int` (sebagai output covariant).
*Kriteria Sukses*: Verifikasi subtyping rules: Objek `Transformation<CharSequence, Int>` dapat di-assign ke variabel bertipe `Transformation<String, Number>`.

#### Level Hard
Rancang custom contract method `validateSession(session: Session?): Boolean`.
Method ini harus:
1.  Menghasilkan contract: jika return `true`, maka `session != null`.
2.  Menerima parameter lambda `onValidationSuccess: () -> Unit` dengan kontrak `callsInPlace(InvocationKind.AT_MOST_ONCE)`.
*Kriteria Sukses*: Kode pemanggil dapat mendefinisikan variabel lokal `val token: String` di luar fungsi, menginisialisasinya di dalam lambda tersebut tanpa compile error "val cannot be reassigned".

---

### 14. Challenge

**Skenario**:
Anda adalah Principal Architect di sebuah hedge fund. Perusahaan sedang membangun *in-memory cache* untuk limit checking yang melayani jutaan request limit per detik.

**Tantangan**:
Rancang sebuah Typed Memory Buffer bernama `FlatRingBuffer<T>` yang memenuhi syarat ketat:
1.  Menyimpan hingga 1.000.000 entity bertipe value class tanpa menimbulkan alokasi objek heap baru saat operasi `push` dan `poll`.
2.  Menggunakan *declaration-site variance* untuk membagi akses API buffer menjadi dua view: `WriteRingBuffer<in T>` dan `ReadRingBuffer<out T>`.
3.  Menyediakan method sinkronisasi dengan *Kotlin Contracts* yang memastikan memory barriers dieksekusi tepat satu kali (`InvocationKind.EXACTLY_ONCE`).
4.  Buktikan nol boxing: Siapkan assertions file atau memory measurement test yang membuktikan `Runtime.getRuntime().freeMemory()` tidak terdegradasi secara dinamis saat 100.000 cycle write/read dijalankan pada Ring Buffer.

---

### 15. Quiz Evaluasi Pemahaman

#### Soal Basic
1.  Apa yang membedakan representasi FIR (Frontend Intermediate Representation) pada compiler K2 dari PSI (Program Structure Interface) pada compiler lama?
2.  Mengapa `out T` pada Kotlin setara dengan `? extends T` pada Java generics?
3.  Kapan sebuah `@JvmInline value class` terpaksa dialokasikan (boxed) ke memori heap oleh JVM?
4.  Apa kegunaan dari tipe `Nothing` dalam sistem tipe Kotlin, dan apa perbedaannya secara fundamental dengan `Unit`?
5.  Apa fungsi utama dari `callsInPlace` pada Kotlin Contracts?

#### Soal Intermediate
6.  Mengapa kompilator Kotlin melakukan *name mangling* pada fungsi publik yang menggunakan *value class* sebagai parameternya?
7.  Diberikan interface `Producer<out T>`. Mengapa fungsi `fun consume(item: T)` di dalam interface tersebut ditolak oleh compiler?
8.  Bagaimana cara mengatasi situasi di mana Anda harus menerima parameter `T` pada interface covariant (`out T`) semata-mata untuk komparasi kesetaraan?
9.  Jelaskan mengapa kode berikut menghasilkan compile error pada baris penugasan `x`:
    ```kotlin
    val list: MutableList<out Number> = ArrayList<Int>()
    list.add(10) // Error
    ```
10. Apakah Kotlin Contracts diproses dan dievaluasi saat *runtime* atau saat *compile time*? Jelaskan dampaknya terhadap performa aplikasi.

#### Skenario Kasus Produksi
11. **Kasus 1**: Sistem settlement kripto mengalami peningkatan latency P99 drastis. Profiler menunjukkan jutaan panggilan ke `BoxedUnit.box()`. Kode Anda banyak menggunakan higher-order functions generic dengan return value `Unit`. Bagaimana Anda merestrukturisasi tipe generic tersebut untuk mencegah alokasi objek singleton boxing ini?
12. **Kasus 2**: Anda membuat microservice baru yang menggunakan Value Class untuk entitas `CustomerId(val value: UUID)`. Saat service dipanggil oleh client berbasis Java legacy melalui Spring Cloud OpenFeign, tim consumer komplain bahwa endpoint melempar error `NoSuchMethodError: findCustomer(Ljava/lang/String;)`. Apa penyebab teknis di tingkat bytecode dan bagaimana Anda mengatasinya di Kotlin?
13. **Kasus 3**: Seorang software engineer di tim Anda membuat utility validation:
    ```kotlin
    @OptIn(ExperimentalContracts::class)
    fun ensureActive(user: User?): Boolean {
        contract {
            returns(true) implies (user != null)
        }
        return user != null && user.status == Status.ACTIVE
    }
    ```
    Namun, di unit test, jika objek `user` dikirim dengan `status = Status.SUSPENDED`, method melempar NullPointerException di baris lanjutan kode pemanggil setelah percabangan `if (!ensureActive(user))`. Identifikasi kesalahan penulisan implikasi kontrak logic ini.

---

### 16. Summary

1.  **Arsitektur Compiler Modern**: Pipeline Kotlin 2.0 (K2) menyatukan analisis tipe semantik pada FIR dan lowering pada IR Backend, menghasilkan kompilasi yang deterministik, lebih cepat, dan minim alokasi perantara.
2.  **Advanced Generics**: Menggunakan *declaration-site variance* (`out`/`in`) membuat arsitektur domain lebih elegan, memecahkan masalah subtyping invariant tanpa perlu menuliskan Java-style wildcards berulang di setiap layer bisnis.
3.  **Zero-Allocation Primitives**: Melalui `@JvmInline value class`, Kotlin enterprise architecture mampu meniadakan kompromi antara *Domain-Driven Design* (kaya representasi tipe) dan *Extreme Low Latency Performance* (minim GC overhead). Waspadai pemicu silent boxing (polymorphism dan generic erasure).
4.  **Static Logic Encoding dengan Contracts**: Kotlin Contracts menghubungkan batas antara logika kode runtime developer dengan *type checker inference* pada compiler, memungkinkan pembuktian keabsahan alur kontrol (`callsInPlace`) dan nullability invariants (`smart casts`) tanpa runtime overhead.