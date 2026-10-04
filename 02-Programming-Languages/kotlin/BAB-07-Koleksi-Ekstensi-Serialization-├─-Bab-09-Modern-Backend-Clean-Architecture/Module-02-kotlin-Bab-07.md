# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: Koleksi, Ekstensi, Serialization & Jembatan Clean Architecture Modern**

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis dekompilasi bytecode JVM dari implementasi `kotlin.collections.*` untuk membedakan overhead alokasi memori antara eager evaluation (`Iterable`) dan lazy evaluation (`Sequence`).
- Menguasai semantik resolusi ekstensi (*static dispatch*, *extension receiver* vs *dispatch receiver*, serta *inline extension functions*) guna membangun domain DSL yang aman tanpa penalti alokasi objek lambda.
- Membedah arsitektur internal `kotlinx.serialization` (kompilator plugin AST synthesis, `KSerializer<T>`, `SerialDescriptor`, *streaming encoders/decoders*) dan membandingkannya secara analitis terhadap mekanisme *reflection-based* (Jackson/Gson).
- Mengimplementasikan *custom serializer* non-trivial yang menangani tipe data pihak ketiga, transformasi skema dinamis, dan deserialisasi polimorfik tanpa *reflection overhead*.
- Merancang batas arsitektur (*architectural boundaries*) berbasis *Clean Architecture* menggunakan kombinasi `@JvmInline value class`, *extension mappers*, dan *immutable domain models* untuk mencegah *domain primitive obsession* dan kebocoran DTO ke lapisan inti.

---

## 2. Prerequisites

Sebelum mempelajari materi ini, Anda wajib memiliki pemahaman mendalam mengenai:
1. **Model Memori JVM**: Manajemen heap, *young/old generation*, *Garbage Collection mechanics* (G1/ZGC), serta alokasi frame stack.
2. **Bytecode JVM Fundamental**: Pemahaman tentang instruksi bytecode dasar seperti `INVOKESTATIC`, `INVOKEVIRTUAL`, `CHECKCAST`, dan representasi metadata kelas.
3. **Kotlin Intermediate**: *Generics* (varian: `in`, `out`, *type projections*, *reified types*), fungsi *higher-order*, dan *scope functions*.
4. **Prinsip Clean Architecture**: Pemisahan lapisan *Enterprise Business Rules*, *Application Business Rules*, *Interface Adapters*, dan *Frameworks & Drivers*.

---

## 3. Concept & Internal Architecture

### 3.1. Koleksi: Read-Only Interfaces vs Mutable, Platform Types, & Bridging ke JVM

Kotlin tidak mengimplementasikan struktur data koleksi baru dari nol di level runtime JVM. Kotlin menggunakan pendekatan **compiler-level type mapping** terhadap Java Collections Framework (`java.util.*`).

```
                    kotlin.collections.Iterable<out T>
                                   ▲
                                   │ (Compiled directly to)
                                   ▼
                          java.lang.Iterable<T>
                                   ▲
                                   │
                    kotlin.collections.Collection<out T>
                                   ▲
                                   │
              ┌────────────────────┴────────────────────┐
              │                                         │
kotlin.collections.List<out T>           kotlin.collections.MutableList<T>
              │                                         │
              └────────────────────┬────────────────────┘
                                   │ (Physical Bytecode Target)
                                   ▼
                           java.util.List<T>
```

#### Kompilasi Type Mapping
Secara fisik di bytecode, `kotlin.collections.List` dan `kotlin.collections.MutableList` dikompilasi menjadi tipe JVM yang sama: `java.util.List`. 
- **Read-Only Interface**: Imutabilitas pada `List<T>` dijamin pada tingkat analisis statis (*compile-time*) oleh kompilator Kotlin. Kompilator menolak pemanggilan mutasi seperti `.add()` atau `.remove()`.
- **Platform Bridging & Type Erasure**: Saat berinteroperasi dengan Java, batasan ini dapat ditembus jika kode Java memutasi list tersebut, atau jika dilakukan *unsafe cast* via `(list as java.util.List<T>).add(...)`. Di tingkat JVM, referensi objek yang mendasarinya sering kali berupa `java.util.ArrayList`.

#### Alokasi Memori: Eager `Iterable` vs Lazy `Sequence`

```
--- EAGER PIPELINE (Iterable) ---
Input [10,000 items]
  │
  ▼  .filter { ... }  ──> Alokasi ArrayList baru #1 (misal: 5,000 items)
Intermediate List 1
  │
  ▼  .map { ... }     ──> Alokasi ArrayList baru #2 (5,000 items)
Intermediate List 2
  │
  ▼  .take(10)        ──> Alokasi ArrayList baru #3 (10 items)
Final Result

--- LAZY PIPELINE (Sequence) ---
Input [10,000 items]
  │
  ▼  .asSequence().filter { ... }.map { ... }.take(10)
  │  (Zero collection allocation; 1 Sequence object + Iterator wrapper)
  ▼
Element #1 ──> Filter (Pass) ──> Map ──> Sink
Element #2 ──> Filter (Fail)
... (Berhenti tepat saat 10 item terpenuhi - Short-Circuiting)
```

Pada rantai evaluasi `Iterable`, setiap pemanggilan fungsi transformatif (`filter`, `map`) mengalokasikan koleksi sementara (`java.util.ArrayList`) baru di Heap memori. Jika koleksi berukuran $N = 1.000.000$ elemen, tiga tahapan transformasi akan memicu alokasi jutaan objek transien yang memicu siklus *Stop-the-World Minor GC*.

Sebaliknya, `Sequence` beroperasi secara lazy menggunakan pola *pull-based iterator pipeline*:
1. Transformasi tidak memproses data secara agregat, melainkan membungkus `Iterator` sebelumnya dalam instance `Sequence` baru (`FilteringSequence`, `TransformingSequence`).
2. Evaluasi terjadi secara *horizontal* per elemen saat *terminal operator* (misal `.toList()`, `.first()`) dipanggil.
3. Fitur *short-circuiting* (misal via `.take(n)`) menghentikan proses evaluasi tepat saat kriteria terpenuhi, tanpa perlu mengevaluasi sisa koleksi.

### 3.2. Ekstensi: Static Resolution, Bytecode Desugaring, & Dispatch Receiver

Extension function di Kotlin bukan merupakan modifikasi struktural terhadap kelas target (tidak ada bytecode injection ke dalam kelas target).

Misalkan kita mendeklarasikan fungsi ekstensi berikut:
```kotlin
package com.enterprise.engine

fun String.maskSensitive(visibleChars: Int): String {
    if (this.length <= visibleChars) return this
    return "*".repeat(this.length - visibleChars) + this.takeLast(visibleChars)
}
```

Kompilator Kotlin melakukan *desugaring* terhadap fungsi di atas menjadi metode statis Java biasa:
```java
package com.enterprise.engine;

public final class StringExtensionsKt {
    @org.jetbrains.annotations.NotNull
    public static final String maskSensitive(@org.jetbrains.annotations.NotNull String $this$maskSensitive, int visibleChars) {
        kotlin.jvm.internal.Intrinsics.checkNotNullParameter($this$maskSensitive, "$this$maskSensitive");
        if ($this$maskSensitive.length() <= visibleChars) {
            return $this$maskSensitive;
        }
        // desugared masking implementation
        return ...;
    }
}
```

#### Mekanisme Dispatching
1. **Static Dispatch**: Resolusi pemanggilan fungsi ekstensi dilakukan berdasarkan tipe statis deklarasi variabel saat *compile-time*, bukan tipe runtime dinamis (*dynamic dispatch*). Jika sebuah kelas dasar dan kelas turunannya memiliki ekstensi dengan signature yang identik, ekstensi yang dieksekusi ditentukan oleh tipe statis referensi variabel.
2. **Dispatch Receiver vs Extension Receiver**: 
   - *Extension Receiver*: Tipe yang diperluas fungsinya (menjadi argumen pertama metode statis).
   - *Dispatch Receiver*: Instance dari kelas tempat ekstensi tersebut dideklarasikan (jika fungsi dideklarasikan di dalam kelas lain).

### 3.3. Arsitektur kotlinx.serialization: Metadata Kompilasi & Streaming Pipeline

Berbeda dengan Jackson atau Gson yang mengandalkan Java Reflection (`java.lang.reflect.*`) dan pembacaan metadata kelas pada saat runtime secara dinamis, `kotlinx.serialization` mengadopsi mekanisme **Compile-Time Code Generation via Kotlin Compiler Plugin**.

```
Source Code (.kt)
   │  (@Serializable class TransactionPayload)
   ▼
Kotlin Compiler + kotlinx.serialization Plugin
   │
   ├─► Generate synthetic companion class / serializer:
   │     TransactionPayload$$serializer : KSerializer<TransactionPayload>
   │     - get descriptor(): SerialDescriptor
   │     - serialize(Encoder, TransactionPayload)
   │     - deserialize(Decoder): TransactionPayload
   ▼
Bytecode Output (.class)
   │
Runtime Execution
   ▼
Decoder (e.g. JsonDecoder) ──Streaming Reads (No Reflection)──► Domain Object
```

#### Struktur Internal Utama
1. **`SerialDescriptor`**: Menyimpan representasi skema tipe data: nama elemen, *nullability*, anotasi, indeks field, dan kind tipe data (`PrimitiveKind`, `StructureKind.CLASS`, `PolymorphicKind`).
2. **`KSerializer<T>`**: Antarmuka inti yang memiliki dua fungsi murni:
   - `fun serialize(encoder: Encoder, value: T)`
   - `fun deserialize(decoder: Decoder): T`
3. **Low-level Streaming API (`CompositeEncoder` / `CompositeDecoder`)**: Mengiterasi field satu per satu berdasarkan indeks numerik tanpa alokasi intermediate dictionary atau tree structure (kecuali saat menggunakan representasi AST seperti `JsonElement`).

---

## 4. Why & What

| Pendekatan / Teknologi | Alasan Digunakan (Why) | Karakteristik Teknis (What) |
| :--- | :--- | :--- |
| **`Sequence` over `Iterable` (Data Skala Besar)** | Menghilangkan alokasi koleksi intermediet; mengurangi alokasi memori heap secara drastis pada data berukuran > 10.000 elemen atau pemrosesan streaming bertahap. | Pipeline transformasi lazy berbasis *Iterator pulling*, mendukung *short-circuit evaluation*. |
| **`kotlinx.serialization` over `Jackson`** | Eksekusi deterministik bebas dari penalti performa inspeksi refleksi JVM; mendukung target GraalVM Native Image tanpa konfigurasi refleksi runtime yang rapuh. | Serializer dihasilkan secara sintesis saat kompilasi (`$$serializer`); IO streaming berbasis index decoding. |
| **`@JvmInline value class` (Clean Architecture)** | Menghindari *primitive obsession* tanpa beban alokasi objek heap wrapper (*zero-cost domain abstractions*). | Tipe dibungkus saat kompilasi, namun di-*inline* menjadi tipe primitif aslinya pada level JVM bytecode. |
| **Extension Functions as Boundary Mappers** | Memisahkan model persistensi / DTO dari aturan domain inti secara tegas, menjaga *Domain Layer* tetap murni dari dependensi framework. | Fungsi statis yang menjembatani transformasi tipe antar lapisan tanpa polusi inheritance. |

---

## 5. How: Architectural Workflow Pipeline

Diagram alir berikut mengilustrasikan alur pemrosesan transaksi berkinerja tinggi dari lapisan jaringan (*Transport DTO*) hingga ke persistensi domain, memanfaatkan komponen arsitektur yang dibahas:

```
[ HTTP/Messaging Ingress ]
           │ Raw JSON Stream
           ▼
[ kotlinx.serialization Engine ]
           │ Low-allocation parsing via KSerializer<TransactionRequestDTO>
           ▼
[ Transport DTO Layer ] (Framework Boundary)
           │
           │ Execution of Domain Mapper Extension:
           │ fun TransactionRequestDTO.toDomainEntity(): Transaction
           ▼
[ Domain Model Layer ] (Core Business Rules)
           │ Validasi via Value Classes (AccountId, Currency, Money)
           │ No framework annotations, fully isolated
           ▼
[ Domain Stream Processor ]
           │ asSequence() pipeline
           │ - Transaction Fraud Check
           │ - Ledger Entry Splitting
           ▼
[ Persistence Outbound Adapter ]
           │ Extension Mapper: fun LedgerEntry.toRecord(): JooqRecord
           ▼
[ Database/Event Stream Egress ]
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Konveyor Pabrik (Lazy Sequence) vs Gudang Transit (Eager Iterable)

**Eager Iterable**: 
Setiap kali satu tahapan kerja selesai (misal: pembersihan bahan), seluruh 100.000 produk dipindahkan ke dalam *gudang sementara* (alokasi memori baru). Tahapan berikutnya mengambil dari gudang tersebut, memproses semuanya, lalu menyimpannya di *gudang sementara kedua*. Gudang penuh sesak, dan truk sampah (*Garbage Collector*) harus bolak-balik membersihkan gudang transit yang tidak terpakai lagi.

**Lazy Sequence**:
Menggunakan satu jalur konveyor berkelanjutan. Satu produk berjalan dari pembersihan langsung ke perakitan, pengecatan, hingga selesai. Jika hanya dibutuhkan 10 produk pertama, tombol stop ditekan setelah produk ke-10 selesai. Tidak ada gudang transit sementara yang dibangun.

```
Eager Processing (Iterable):
[Elemen 1..N] ──► [Step 1: Filter] ──► ALOKASI HEAP BARU (Ukuran K)
                                              │
                                              ▼
                                       [Step 2: Map] ──► ALOKASI HEAP BARU (Ukuran K)
                                                               │
                                                               ▼
                                                        [Hasil Akhir]

Lazy Processing (Sequence):
[Elemen 1] ──► [Filter] ──► [Map] ──► Hasil 1
[Elemen 2] ──► [Filter: Skip!]
[Elemen 3] ──► [Filter] ──► [Map] ──► Hasil 2
  ... Pipeline beroperasi per item; memori intermediate = O(1)
```

---

## 7. Simple & Practical Implementation

### 7.1. Simple Example: Resolusi Statis Ekstensi & Inlining

Berikut adalah contoh yang memperlihatkan bagaimana resolusi statis bekerja dan bagaimana inlining menghilangkan overhead alokasi objek lambda.

```kotlin
package com.enterprise.sandbox

open class BaseNotification
class UrgentNotification : BaseNotification()

// Static Extension Declarations
fun BaseNotification.resolveChannel(): String = "STANDARD_EMAIL"
fun UrgentNotification.resolveChannel(): String = "HIGH_PRIORITY_SMS"

// Inline Extension Function with Lambda to prevent Function allocation
inline fun <T : BaseNotification> T.processWithAudit(auditAction: (T) -> Unit): T {
    auditAction(this)
    return this
}

fun main() {
    val notification: BaseNotification = UrgentNotification()
    
    // Perhatikan: Karena target resolusi bersifat STATIS, tipe deklarasi variabel
    // (BaseNotification) yang menang, BUKAN tipe runtime (UrgentNotification).
    println(notification.resolveChannel()) // Output: STANDARD_EMAIL

    // Zero-allocation invocation via inline
    notification.processWithAudit { item ->
        println("Auditing notification: ${item.resolveChannel()}")
    }
}
```

### 7.2. Practical Example: Serialization & Domain Pipeline

Implementasi DTO, serialisasi kustom untuk tipe ISO-8601 `Instant`, transformasi domain berbasis *Value Class*, dan pemrosesan lazy batching.

```kotlin
package com.enterprise.pipeline

import kotlinx.serialization.*
import kotlinx.serialization.descriptors.*
import kotlinx.serialization.encoding.*
import kotlinx.serialization.json.*
import java.math.BigDecimal
import java.time.Instant

// ============================================================================
// 1. SERIALIZATION INFRASTRUCTURE: Custom Serializer for java.time.Instant
// ============================================================================
object InstantEpochMillisSerializer : KSerializer<Instant> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("java.time.Instant", PrimitiveKind.LONG)

    override fun serialize(encoder: Encoder, value: Instant) {
        encoder.encodeLong(value.toEpochMilli())
    }

    override fun deserialize(decoder: Decoder): Instant {
        val epochMilli = decoder.decodeLong()
        return Instant.ofEpochMilli(epochMilli)
    }
}

// ============================================================================
// 2. TRANSPORT LAYER: DTOs with kotlinx.serialization annotations
// ============================================================================
@Serializable
data class TransactionDTO(
    @SerialName("txn_id") val transactionId: String,
    @SerialName("acc_id") val accountId: String,
    @SerialName("amount_raw") val amount: String,
    @SerialName("currency_code") val currency: String,
    @Serializable(with = InstantEpochMillisSerializer::class)
    @SerialName("timestamp_ms") val timestamp: Instant
)

// ============================================================================
// 3. DOMAIN LAYER: Pure Business Entities & Zero-Cost Value Classes
// ============================================================================
@JvmInline
value class TransactionId(val value: String) {
    init {
        require(value.isNotBlank()) { "TransactionId cannot be blank" }
    }
}

@JvmInline
value class AccountId(val value: String) {
    init {
        require(value.startsWith("ACC-")) { "AccountId must start with 'ACC-'" }
    }
}

data class Money(val amount: BigDecimal, val currency: String)

data class DomainTransaction(
    val id: TransactionId,
    val accountId: AccountId,
    val value: Money,
    val timestamp: Instant
)

// ============================================================================
// 4. MAPPER EXTENSIONS: Bridging Transport DTO to Domain Layer
// ============================================================================
fun TransactionDTO.toDomain(): Result<DomainTransaction> = runCatching {
    DomainTransaction(
        id = TransactionId(this.transactionId),
        accountId = AccountId(this.accountId),
        value = Money(BigDecimal(this.amount), this.currency),
        timestamp = this.timestamp
    )
}

// ============================================================================
// 5. PIPELINE SERVICE: Lazy Execution Engine using Sequences
// ============================================================================
class TransactionPipelineService(private val json: Json) {

    fun processStream(rawPayloads: List<String>): List<DomainTransaction> {
        return rawPayloads.asSequence()
            .map { rawJson -> json.decodeFromString<TransactionDTO>(rawJson) }
            .map { dto -> dto.toDomain() }
            .filter { result -> result.isSuccess }
            .map { result -> result.getOrThrow() }
            .filter { domainTxn -> domainTxn.value.amount > BigDecimal.ZERO }
            .take(500) // Short-circuiting: Hanya memproses hingga 500 transaksi valid
            .toList()
    }
}
```

---

## 8. Real-World Case Study: Enterprise Financial Ledger Engine

### Arsitektur Konteks
Sistem *Payment Settlement Gateway* memproses feed jutaan rekonsiliasi transaksi per batch dari berbagai mitra perbankan. Sistem tidak boleh mengalami lonjakan *latency* akibat GC pauses (alokasi memori seminimal mungkin), harus menolak data cacat pada batas terluar arsitektur, dan memetakan model heterogen mitra ke dalam satu model ledger terpadu.

```
       JSON Ingress Stream (Raw Partner Data)
                         │
                         ▼
        [ PartnerPayloadDecoder (Dynamic) ]
                         │
       Zero-Reflection Streaming Deserializer
                         │
                         ▼
           Sequence Pipeline Iterator
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
Validation Stage (Contract)         Dynamic Mapping
- @JvmInline Type Boundary         - Extension Mappers
- Instant normalizer               - Functional enrichment
        │                                 │
        └────────────────┬────────────────┘
                         ▼
             Filtered Immutable Ledger
                         │
                         ▼
      Persistence Writer (Low GC Footprint)
```

```kotlin
package com.enterprise.ledger

import kotlinx.serialization.*
import kotlinx.serialization.json.*
import java.math.BigDecimal
import java.time.Instant

// ============================================================================
// CONTRACT LAYER: Dynamic Ingress Format via kotlinx.serialization
// ============================================================================
@Serializable
sealed interface ExternalSettlementFeed {
    @Serializable
    @SerialName("BANK_ALPHA")
    data class AlphaSettlement(
        val ref: String,
        val sourceAccount: String,
        val gross: Double,
        val epochSeconds: Long
    ) : ExternalSettlementFeed

    @Serializable
    @SerialName("BANK_BETA")
    data class BetaSettlement(
        val uuid: String,
        val accountIdentifier: String,
        val creditAmount: String,
        val currency: String,
        val timestampIso: String
    ) : ExternalSettlementFeed
}

// ============================================================================
// DOMAIN CORE LAYER: Clean Architecture Aggregate
// ============================================================================
@JvmInline
value class LedgerEntryId(val value: String)

@JvmInline
value class AccountNumber(val value: String)

enum class LedgerDirection { DEBIT, CREDIT }

data class LedgerEntry(
    val entryId: LedgerEntryId,
    val targetAccount: AccountNumber,
    val amount: BigDecimal,
    val direction: LedgerDirection,
    val settledAt: Instant
)

// ============================================================================
// BOUNDARY EXTENSIONS: Anti-Corruption Layer (ACL)
// ============================================================================
fun ExternalSettlementFeed.AlphaSettlement.toLedgerDomain(): LedgerEntry {
    return LedgerEntry(
        entryId = LedgerEntryId("ALPHA_${this.ref}"),
        targetAccount = AccountNumber(this.sourceAccount),
        amount = BigDecimal.valueOf(this.gross),
        direction = LedgerDirection.CREDIT,
        settledAt = Instant.ofEpochSecond(this.epochSeconds)
    )
}

fun ExternalSettlementFeed.BetaSettlement.toLedgerDomain(): LedgerEntry {
    return LedgerEntry(
        entryId = LedgerEntryId("BETA_${this.uuid}"),
        targetAccount = AccountNumber(this.accountIdentifier),
        amount = BigDecimal(this.creditAmount),
        direction = LedgerDirection.CREDIT,
        settledAt = Instant.parse(this.timestampIso)
    )
}

fun ExternalSettlementFeed.toDomain(): LedgerEntry = when (this) {
    is ExternalSettlementFeed.AlphaSettlement -> this.toLedgerDomain()
    is ExternalSettlementFeed.BetaSettlement -> this.toLedgerDomain()
}

// ============================================================================
// CORE PROCESSING ENGINE: Memory-efficient Sequence Execution
// ============================================================================
class SettlementReconciliationEngine {
    private val jsonConfiguration = Json {
        ignoreUnknownKeys = true
        isLenient = false
        classDiscriminator = "partner_type" // Polymorphic discriminator
    }

    fun processSettlementFile(rawInputLines: Sequence<String>): Sequence<LedgerEntry> {
        return rawInputLines
            .filter { line -> line.isNotBlank() }
            .mapNotNull { line ->
                runCatching {
                    jsonConfiguration.decodeFromString<ExternalSettlementFeed>(line)
                }.getOrNull() // Mengisolasi kegagalan parsing agar pipeline tidak terputus
            }
            .map { feed -> feed.toDomain() }
            .filter { entry -> entry.amount > BigDecimal.ZERO }
    }
}
```

---

## 9. Trade-Offs

Menerapkan pola di atas menghadirkan trade-off rekayasa sistem yang wajib diperhitungkan:

| Parameter | `kotlin.collections.Sequence` | Eager `kotlin.collections.List` |
| :--- | :--- | :--- |
| **Throughput (Ukuran Data Kecil < 100)** | **Lebih Lambat**. State-machine iterasi lazily membawa overhead *megamorphic method call*. | **Lebih Cepat**. Sederhana, array copy primitif langsung dioptimalkan oleh JIT compiler. |
| **Throughput (Ukuran Data Besar > 50.000)** | **Sangat Cepat**. Tidak ada pembuatan koleksi perantara yang mengotori heap. | **Menurun Drastis**. Tercekik oleh overhead GC minor yang berulang kali berjalan. |
| **Alokasi Memori** | $O(1)$ intermediate complexity relative to total input. | $O(N)$ intermediate complexity per rantai transformasi. |
| **Kemudahan Debugging** | Sulit di-trace dengan standard breakpoint; memerlukan stack trace lazy iterator traversal. | Mudah di-trace; state koleksi di setiap tahap dapat langsung diinspeksi. |

| Aspek | `kotlinx.serialization` | Reflection-Based (Jackson / Gson) |
| :--- | :--- | :--- |
| **Waktu Kompilasi (Build Time)** | Lebih tinggi; compiler plugin menyintesis bytecode kelas pendamping. | Cepat; tidak ada generasi kode sintesis saat kompilasi. |
| **Startup / Latency Awal** | Rendah (Zero-cold-start reflection cost). Ideal untuk Function-as-a-Service / GraalVM. | Tinggi; harus membangun metadata cache introspeksi runtime reflection saat cold start. |
| **Fleksibilitas Skema Ekstrim** | Kaku; struktur polimorfik dan *unknown keys* harus dideklarasikan secara eksplisit. | Sangat fleksibel; tipe arbitrary (`Map<String, Object>`) ditangani secara dinamis saat runtime. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Perangkap Evaluasi Ganda pada Sequence (Multiple Enumeration)
*Masalah*: Mengonsumsi `Sequence` lebih dari satu kali.
```kotlin
// ERROR SCENARIO
val sequence = fileReader.lineSequence().map { parse(it) }
val total = sequence.count() // Terminal operator dipanggil
val items = sequence.toList() // ILLEGALSTATEEXCEPTION! Sequence has already been consumed.
```
*Solusi*: Jika hasil evaluasi lazy perlu diakses berulang kali, simpan hasil terminal ke dalam koleksi definitif, atau buat factory lambda yang mengembalikan instance sequence baru.

### 2. Mutasi Akses Terselubung Melalui Platform Types
*Masalah*: Read-only list dikonversi secara tidak aman ke `java.util.List` yang dapat dimutasi.
```kotlin
fun processData(readOnlyList: List<String>) {
    // Unsafe Cast yang lolos kompilasi namun merusak thread-safety runtime
    val dangerousCast = readOnlyList as java.util.List<String>
    dangerousCast.clear() // Mutation succeeds or throws UnsupportedOperationException depending on backend backing list
}
```
*Solusi*: Gunakan defensive copy (`readOnlyList.toMutableList()`) atau gunakan pustaka struktur data persisten murni (*immutable persistent collections*) seperti `kotlinx.collections.immutable`.

### 3. Missing Polymorphic Subclass Registration
*Masalah*: `kotlinx.serialization` melempar `SerializationException: Serializer for class 'Child' is not found` saat mendeserialisasi sealed interface yang dideklarasikan lintas modul.
*Solusi*: Daftarkan subclass secara eksplisit melalui `SerializersModule`:
```kotlin
val customModule = SerializersModule {
    polymorphic(BaseContract::class) {
        subclass(AlphaContract::class)
        subclass(BetaContract::class)
    }
}
val json = Json { serializersModule = customModule }
```

### 4. Overhead Lambda Capturing pada Extension Functions
*Masalah*: Menulis ekstensi higher-order function tanpa kata kunci `inline`.
*Dampak*: Kompilator mengalokasikan instance baru kelas `FunctionN` pada heap di setiap kali fungsi dipanggil dalam loop.
*Solusi*: Tambahkan kata kunci `inline` pada fungsi ekstensi yang menerima argumen lambda eksekusi tunggal.

---

## 11. Best Practices (Production Checklist)

1. [ ] **Gunakan Sequences Secara Proporsional**: Gunakan `.asSequence()` HANYA jika data berukuran besar (> 10.000 item), memiliki pipeline rantai manipulasi lebih dari 2 tahapan, atau menggunakan operasi pemotong rantai (`take`, `find`).
2. [ ] **Inline Higher-Order Extensions**: Selalu tandai extension function yang menerima receiver lambda sebagai `inline`, kecuali jika lambda tersebut perlu disimpan sebagai variabel atau dipassing ke konteks asynchronous non-inlined (`crossinline`).
3. [ ] **Isolasi DTO dan Domain**: Jangan pernah menggunakan model `@Serializable` langsung sebagai entitas bisnis pada Core Domain layer. Selalu buat DTO terpisah dan gunakan extension mappers (`toDomain()`, `toDTO()`).
4. [ ] **Gunakan `@JvmInline` untuk Identitas**: Bungkus identifier primitif (ID, Email, Nomor Rekening, Kode Mata Uang) menggunakan `@JvmInline value class` untuk menjamin keamanan tipe tanpa overhead alokasi memori heap.
5. [ ] **Singleton Configuration untuk Serializer**: Instansiasi engine `Json { ... }` sebagai singleton kelas layanan atau inject melalui DI framework (Koin/Spring). Jangan membuat instance `Json` baru di setiap pemanggilan transaksi parsing karena inisialisasi modul serialisasi memicu alokasi cache internal.

---

## 12. Hands-on Practice

Buatlah implementasi lengkap sebuah micro-engine untuk memfilter, memetakan, dan memvalidasi log transaksi keuangan.

### Struktur Proyek
```
hands-on/m02/
├── build.gradle.kts
└── src/
    └── main/
        └── kotlin/
            └── com/enterprise/handson/
                ├── Application.kt
                ├── domain/
                │   └── Model.kt
                ├── dto/
                │   └── AuditLogDTO.kt
                └── service/
                    └── AuditLogProcessor.kt
```

### Langkah 1: Siapkan `build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm") version "1.9.22"
    kotlin("plugin.serialization") version "1.9.22"
    application
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    testImplementation(kotlin("test"))
}

application {
    mainClass.set("com.enterprise.handson.ApplicationKt")
}
```

### Langkah 2: Buat Model DTO (`src/main/kotlin/com/enterprise/handson/dto/AuditLogDTO.kt`)
```kotlin
package com.enterprise.handson.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AuditLogDTO(
    @SerialName("trace_id") val traceId: String,
    @SerialName("actor") val actorId: String,
    @SerialName("event_type") val eventType: String,
    @SerialName("status_code") val statusCode: Int,
    @SerialName("created_at_epoch") val createdAtEpoch: Long
)
```

### Langkah 3: Buat Domain Model (`src/main/kotlin/com/enterprise/handson/domain/Model.kt`)
```kotlin
package com.enterprise.handson.domain

import java.time.Instant

@JvmInline
value class TraceId(val value: String) {
    init {
        require(value.isNotEmpty()) { "TraceId cannot be empty" }
    }
}

@JvmInline
value class ActorId(val value: String)

enum class AuditSeverity { CRITICAL, WARNING, INFO }

data class SecurityAuditEvent(
    val traceId: TraceId,
    val actor: ActorId,
    val action: String,
    val severity: AuditSeverity,
    val timestamp: Instant
)
```

### Langkah 4: Buat Service dan Mapper (`src/main/kotlin/com/enterprise/handson/service/AuditLogProcessor.kt`)
```kotlin
package com.enterprise.handson.service

import com.enterprise.handson.domain.*
import com.enterprise.handson.dto.AuditLogDTO
import kotlinx.serialization.json.Json
import java.time.Instant

// Boundary Mapper Extension
fun AuditLogDTO.toDomain(): SecurityAuditEvent {
    val severity = when {
        this.statusCode >= 500 -> AuditSeverity.CRITICAL
        this.statusCode in 400..499 -> AuditSeverity.WARNING
        else -> AuditSeverity.INFO
    }
    return SecurityAuditEvent(
        traceId = TraceId(this.traceId),
        actor = ActorId(this.actorId),
        action = this.eventType,
        severity = severity,
        timestamp = Instant.ofEpochMilli(this.createdAtEpoch)
    )
}

class AuditLogProcessor(private val json: Json) {

    fun processRawLogs(rawLogs: Sequence<String>): Sequence<SecurityAuditEvent> {
        return rawLogs
            .filter { it.isNotBlank() }
            .map { json.decodeFromString<AuditLogDTO>(it) }
            .map { it.toDomain() }
            .filter { it.severity == AuditSeverity.CRITICAL }
    }
}
```

### Langkah 5: Entry Point Eksekusi (`src/main/kotlin/com/enterprise/handson/Application.kt`)
```kotlin
package com.enterprise.handson

import com.enterprise.handson.service.AuditLogProcessor
import kotlinx.serialization.json.Json

fun main() {
    val samplePayloads = listOf(
        """{"trace_id":"TRC-001","actor":"admin","event_type":"DB_DROP","status_code":500,"created_at_epoch":1700000000000}""",
        """{"trace_id":"TRC-002","actor":"user1","event_type":"LOGIN_ATTEMPT","status_code":200,"created_at_epoch":1700000001000}""",
        """{"trace_id":"TRC-003","actor":"guest","event_type":"UNAUTHORIZED_ACCESS","status_code":403,"created_at_epoch":1700000002000}""",
        """{"trace_id":"TRC-004","actor":"system","event_type":"OOM_KILLED","status_code":503,"created_at_epoch":1700000003000}"""
    )

    val json = Json { ignoreUnknownKeys = true }
    val processor = AuditLogProcessor(json)

    println("=== STARTING LOW-ALLOCATION AUDIT LOG PROCESSING ===")
    
    // Lazy streaming traversal
    processor.processRawLogs(samplePayloads.asSequence())
        .forEach { criticalEvent ->
            println("ALERT [${criticalEvent.severity}]: Trace=${criticalEvent.traceId.value}, Action=${criticalEvent.action}")
        }
}
```

---

## 13. Exercises

### Level Easy
Tulis sebuah fungsi ekstensi `fun List<Int>.secondOrNull(): Int?` yang mengembalikan elemen kedua dari list tanpa menyebabkan `IndexOutOfBoundsException` dan tanpa memicu alokasi sub-list baru.

### Level Medium
Diberikan payload JSON transaksi dengan format tanggal variatif: terkadang dikirim dalam format epoch millisecond integer (`1700000000000`), terkadang dikirim dalam format ISO-8601 string (`"2023-11-14T22:13:20Z"`). Buatlah sebuah implementasi `KSerializer<Instant>` kustom menggunakan `kotlinx.serialization` yang mampu menangani kedua variasi input JSON tersebut secara transparan.

### Level Hard
Rancang sebuah library ekstensi fungsional `chunkedBy(predicate: (T, T) -> Boolean): Sequence<List<T>>` terhadap `Sequence<T>`. 
- Operator ini harus mengelompokkan elemen yang berurutan selama relasi antar elemen ke-$i$ dan ke-$(i+1)$ memenuhi predikat evaluasi.
- Seluruh evaluasi WAJIB beroperasi secara lazy ($O(1)$ memory allocation overhead di luar list penampung chunk yang sedang aktif dievaluasi).
- Tuliskan implementasi state-machine `Iterator` kustom menggunakan `sequence { ... }` builder atau `AbstractIterator`.

---

## 14. Challenge: High-Frequency Market Feed Ingestion Engine

### Deskripsi Masalah
Sebuah platform trading kripto enterprise menerima feed log orderbook terkompresi dengan volume 100.000 events/detik. Format data stream masuk berupa *line-delimited dynamic JSON*. 

### Spesifikasi Teknis yang Harus Dipenuhi:
1. **Zero Intermediate Collection Allocation**: Implementasikan pipeline parser stream yang membaca payload mentah baris per baris secara lazy via `Sequence`.
2. **Polymorphic Ingestion Without Runtime Reflection**: Parse payload ke dalam hierarki `OrderBookEvent` (`Snapshot`, `Delta`, `Heartbeat`) menggunakan `kotlinx.serialization` berbasis polymorphic discriminator.
3. **Strict Clean Architecture Boundary**:
   - Model parsing DTO tidak boleh bocor ke luar engine adapter.
   - Core Domain dilarang memiliki anotasi `@Serializable` apa pun.
   - Semua entitas domain wajib menggunakan `@JvmInline value class` untuk tipe `Price` (berbasis `Long` fixed-point decimal scaling $\times 10^8$), `OrderId`, dan `MarketSymbol`.
4. **Resilience & Fault Isolation**: Jika terdapat satu baris pesan JSON yang malformed (struktur rusak), pipeline Sequence TIDAK BOLEH gagal total (*fail-fast* secara parsial); baris korup harus dibelokkan ke *quarantine channel* (dead-letter sequence) tanpa menghentikan pemrosesan stream.

---

## 15. Evaluasi Pemahaman

### 15.1. Pertanyaan Basic (5 Soal)

1. **Jelaskan perbedaan mendasar antara `kotlin.collections.List` dan `java.util.List` pada saat kompilasi versus runtime JVM.**
   <details><summary>Jawaban</summary>`kotlin.collections.List` adalah abstraksi compile-time Kotlin yang menyediakan kontrak read-only interface (tanpa metode mutasi seperti `.add()`). Namun, pada tingkat JVM runtime bytecode, keduanya dipetakan ke interface yang sama (`java.util.List`). Imutabilitas ini ditegakkan oleh compiler Kotlin, bukan oleh modifikasi JVM runtime.</details>

2. **Apa yang dihasilkan oleh compiler Kotlin di level bytecode ketika Anda mendeklarasikan fungsi ekstensi `fun String.reverseWords(): String`?**
   <details><summary>Jawaban</summary>Compiler menghasilkan public static final method di dalam kelas berkas ekstensi (misal `FileNameKt.class`), di mana receiver tipe (`String`) dijadikan sebagai parameter pertama method: `public static final String reverseWords(String $this$reverseWords)`.</details>

3. **Mengapa `Sequence` lebih hemat memori daripada `Iterable` untuk rantai transformasi bertingkat?**
   <details><summary>Jawaban</summary>Karena Sequence mengevaluasi elemen secara vertikal satu per satu (lazy pull-based), sehingga tidak membuat koleksi perantara (intermediate ArrayList) di setiap tahapan transformasi (`map`, `filter`), tidak seperti `Iterable` yang mengevaluasi seluruh koleksi secara horizontal dan mengalokasikan koleksi penampung baru di setiap operasi.</details>

4. **Bagaimana `kotlinx.serialization` bekerja tanpa menggunakan refleksi runtime (`java.lang.reflect.*`)?**
   <details><summary>Jawaban</summary>Plugin kompilator Kotlin menyintesis kelas companion serializer (`$$serializer`) secara otomatis saat proses build. Kelas ini mengimplementasikan `KSerializer<T>` dengan kode statis yang membaca dan menulis field langsung melalui streaming index decoder/encoder.</details>

5. **Apa fungsi utama dari anotasi `@JvmInline` pada sebuah `value class`?**
   <details><summary>Jawaban</summary>Menginstruksikan kompilator untuk membongkar (*unwrap*) objek pembungkus (*wrapper*) tersebut di level bytecode dan merepresentasikannya langsung sebagai nilai primitif dasarnya jika memungkinkan, sehingga meniadakan alokasi heap untuk wrapper tersebut.</details>

---

### 15.2. Pertanyaan Intermediate (5 Soal)

6. **Diberikan kode berikut: Jika kelas `Parent` memiliki subclass `Child`, dan keduanya memiliki fungsi ekstensi dengan nama yang sama `fun Parent.name() = "P"` dan `fun Child.name() = "C"`. Apa yang dicetak oleh `val obj: Parent = Child(); println(obj.name())`? Jelaskan alasannya.**
   <details><summary>Jawaban</summary>Mencetak "P". Resolusi fungsi ekstensi bersifat statis (static dispatch). Pilihan metode statis yang dieksekusi ditentukan pada saat compile-time berdasarkan tipe deklarasi variabel (`Parent`), bukan tipe objek runtime (`Child`).</details>

7. **Mengapa penambahan kata kunci `inline` sangat disarankan pada extension function yang menerima higher-order function (lambda) sebagai parameter? Kapan inline justru sebaiknya dihindari?**
   <details><summary>Jawaban</summary>`inline` menyalin bytecode instruksi lambda langsung ke titik pemanggilan, menghilangkan alokasi heap untuk objek instansi `FunctionN`. Inline harus dihindari jika isi body fungsi ekstensi sangat panjang (dapat menyebabkan bytecode code bloat) atau jika lambda harus disimpan dalam variabel/dieksekusi secara asynchronous di luar konteks pemanggilan saat itu.</details>

8. **Bagaimana cara menangani evolusi skema (misalnya field baru yang ditambahkan di masa depan) pada `kotlinx.serialization` agar tidak memicu deserialization exception?**
   <details><summary>Jawaban</summary>Gunakan konfigurasi `Json { ignoreUnknownKeys = true }` pada instance engine, dan pastikan field baru pada DTO kelas memiliki nilai default (`val newField: String = "default"`).</details>

9. **Apa bahaya dari melakukan operasi terminal bertingkat seperti `.toList().asSequence().map { ... }.toList()` pada data pipeline?**
   <details><summary>Jawaban</summary>Operasi tersebut merusak keuntungan lazy-evaluation. Pemanggilan `.toList()` pertama memaksa seluruh sequence sebelumnya dievaluasi secara instan dan mengalokasikan koleksi utuh di memori heap, membuat penggunaan sequence di awal menjadi sia-sia dan menambah beban memori.</details>

10. **Bagaimana arsitektur Clean Architecture memandang penggunaan anotasi `@Serializable` di dalam Core Domain Entity?**
    <details><summary>Jawaban</summary>Ini merupakan pelanggaran prinsip pemisahan dependensi (Dependency Rule). Core Domain Entity harus bebas dari dependensi framework/library pihak ketiga. Anotasi serialisasi hanya boleh ada pada Transport DTO di Interface Adapters Layer. Hubungan ke Domain Entity dijembatani melalui Domain Extension Mappers.</details>

---

### 15.3. Skenario Kasus Produksi (3 Kasus)

11. **Skenario GC Thrashing:**
    Aplikasi microservice analitik Anda mengalami lonjakan Stop-The-World (STW) GC pause setiap 10 menit saat memproses batch 500.000 entri log metrik. Setelah dianalisis menggunakan profiler, ditemukan bahwa terdapat alokasi jutaan objek `ArrayList` berumur pendek yang berasal dari pipeline rantai: `logs.filter { ... }.map { ... }.map { ... }.filter { ... }`.
    *Pertanyaan*: Solusi arsitektural apa yang paling efisien, dan bagaimana implementasinya tanpa mengubah logika bisnis?
    <details><summary>Jawaban</summary>Konversi rantai koleksi tersebut menjadi Sequence dengan menyisipkan `.asSequence()` di awal pipeline input dan memanggil `.toList()` hanya di akhir rantai agregasi. Hal ini menghapus semua pembuatan `ArrayList` intermediet, sehingga memangkas alokasi objek transien hingga mendekati 0 dan meniadakan siklus minor GC thrashing.</details>

12. **Skenario Polymorphic Payload Failure:**
    Layanan Event Gateway Anda menerima event dari Apache Kafka dengan berbagai format event pembayaran: `CreditCardPayment`, `BankTransfer`, dan `CryptoPayment`. Layanan menggunakan `kotlinx.serialization` dengan sealed class. Tiba-tiba di produksi, sistem gagal memproses transaksi dengan error: `Serializer not found for class CryptoPayment`.
    *Pertanyaan*: Apa kemungkinan akar masalahnya, dan bagaimana arsitektur serialisasi polimorfik diverifikasi secara deterministik?
    <details><summary>Jawaban</summary>Akar masalah: Kelas `CryptoPayment` mungkin tidak dideklarasikan dalam file yang sama dengan sealed parent, dideklarasikan di modul Gradle terpisah, atau lupa didaftarkan pada `SerializersModule` runtime. Solusi: Daftarkan subclass secara eksplisit melalui `SerializersModule { polymorphic(...) { subclass(...) } }` saat mengonfigurasi instance `Json`, atau pastikan seluruh subclass disegel di bawah `sealed interface` yang sama.</details>

13. **Skenario Heap Exhaustion akibat Value Class Unboxing Failure:**
    Sebuah aplikasi trading performa tinggi mendefinisikan `Price` sebagai `@JvmInline value class Price(val raw: Long)`. Namun, saat ditest profiling, jutaan objek instance `Price` tetap teralokasi di heap, menyebabkan degradasi performa mirip tipe objek referensi reguler.
    *Pertanyaan*: Mengapa JVM tetap mengalokasikan objek wrapper untuk sebuah value class?
    <details><summary>Jawaban</summary>JVM melakukan *boxing* terhadap value class jika value class tersebut:
1. Digunakan dalam konteks generic (misal `List<Price>`), karena generic JVM berbasis referensi tipe `Object`.
2. Di-cast ke interface yang diimplementasikannya.
3. Dioperasikan sebagai nullable type (`Price?`).
Solusi: Gunakan primitive array langsung (misal `LongArray`) untuk penampungan massal, atau hindari nullable generic boxing pada pipeline komputasi kritikal.</details>

---

## 16. Summary

1. **Abstraksi Koleksi Kotlin**: Kotlin tidak menciptakan koleksi fisik baru pada JVM, melainkan menerapkan sistem tipe kompilator cerdas (*read-only vs mutable*) di atas Java Collections Framework.
2. **Karakteristik Evaluasi**: `Iterable` mengevaluasi data secara eager (horizontal evaluation) dengan alokasi penampung intermediate di setiap tahap; sebaliknya, `Sequence` mengevaluasi data secara lazy (vertical evaluation) dengan footprint alokasi memori intermediet $O(1)$.
3. **Ekstensi di Tingkat Mesin**: Extension functions dikompilasi menjadi Java static methods biasa. Resolusi ekstensi bersifat statis (*compile-time dispatch*), bukan dinamis. Gunakan `inline` untuk memangkas overhead alokasi objek higher-order function.
4. **Keunggulan `kotlinx.serialization`**: Meniadakan kebutuhan refleksi runtime JVM yang lambat melalui pembuatan kode streaming serializer secara otomatis saat fase kompilasi (compiler plugin), menjadikannya pilihan ideal untuk arsitektur cloud-native modern dan GraalVM.
5. **Jembatan Clean Architecture**: Terapkan isolasi murni antara Transport DTO (`@Serializable`) dan Domain Core Entity via Extension Mappers. Manfaatkan `@JvmInline value class` untuk menghadirkan sistem domain yang kaya tipe (*type-safe domain primitives*) dengan efisiensi performa setara tipe primitif JVM.