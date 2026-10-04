# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 02-Programming-Languages / Kotlin
*   **Modul:** Koleksi, Ekstensi & Serialization ├─ Modern Backend & Clean Architecture
*   **Tingkat Kesulitan:** Advanced / Enterprise Backend Architecture
*   **Prasyarat:** Pemahaman mendalam tentang Kotlin OOP, Functional Programming dasar (lambdas, higher-order functions), Coroutines dasar, dan prinsip dasar arsitektur perangkat lunak (Separation of Concerns).
*   **Alokasi Waktu Belajar:** 14 Jam (Teori, Deep Dive Bytecode, dan Hands-On Implementation)
*   **Target Output:** Peserta mampu merancang backend berbasis Clean Architecture yang memanfaatkan pustaka koleksi Kotlin secara optimal (termasuk evaluasi `Sequence` vs `Iterable`), menerapkan *extension functions* sebagai *boundary adapter/mapper*, dan mengintegrasikan `kotlinx.serialization` tanpa refleksi runtime untuk mencapai throughput tinggi dan alokasi memori minimal.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1.  **Menganalisis dan Memilih Tipe Koleksi yang Tepat (Analysis & Evaluation):** Membedakan karakteristik performa `Iterable` vs `Sequence`, serta menerapkan *immutable collections* untuk menjamin integritas *state* domain tanpa mengorbankan alokasi heap garbage collector (GC).
2.  **Mendekonstruksi Ekstensi Kotlin pada Level Bytecode (Technical Comprehension):** Menjelaskan bagaimana ekstensi fungsi dan properti di-generate oleh compiler Kotlin menjadi representasi static JVM bytecode dan memanfaatkannya sebagai *zero-cost boundary mapper*.
3.  **Mengonfigurasi dan Memaksimalkan `kotlinx.serialization` (Application & Architecture):** Mengimplementasikan serialisasi polimorfik non-reflektif berbasis compiler-plugin untuk model data hierarkis pada boundary layer API/Infrastructure.
4.  **Mengintegrasikan Komponen Bahasa ke Prinsip Clean Architecture (Synthesize):** Merancang lapisan Domain, Use Case, dan Interface Adapters dengan memisahkan Data Transfer Objects (DTO), Domain Entities, dan Database Entities secara strik menggunakan *extension mappers*.
5.  **Mencegah dan Memitigasi Kerentanan Arsitektur & Performa (Hardening & Optimization):** Mendeteksi memory leak akibat intermediate collections, mencegah serangan deserialisasi objek, dan mengoptimalkan performa parsing JSON pada backend enterprise.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam backend modern, kode bukan sekadar instruksi yang dieksekusi mesin; kode adalah batasan (*boundaries*) yang memisahkan logika bisnis murni dari detail infrastruktur.

```
+--------------------------------------------------------------------------+
|                        CLEAN ARCHITECTURE CORE                           |
|                                                                          |
|   +--------------------+       Uses        +-------------------------+   |
|   |   Domain Entity    |<------------------|        Use Case         |   |
|   | (Pure Data Classes)|                   | (Functional Validation) |   |
|   +--------------------+                   +-------------------------+   |
|            ^                                            |                |
+------------|--------------------------------------------|----------------+
             | Boundary Crossing                          | Boundary Crossing
             | (Extension Functions as Mappers)           | (Extension Functions)
+------------|--------------------------------------------|----------------+
|            v                                            v                |
|   +--------------------+                   +-------------------------+   |
|   | Infrastructure DTO |                   |    Database Persistence |   |
|   |  (Serializable)    |                   |    (Driver / ORM Model) |   |
|   +--------------------+                   +-------------------------+   |
|                                                                          |
|                   INFRASTRUCTURE & ADAPTERS LAYER                        |
+--------------------------------------------------------------------------+
```

### Paradigma Inti:
1.  **Koleksi Sebagai Aliran Data (Data Flow Pipelines):** Hindari mutasi *in-place* di luar lapisan infrastruktur. Perlakukan data koleksi sebagai aliran immutable. Pahami kapan data harus dievaluasi secara *eager* (transaksi kecil, memori rendah) dan kapan harus secara *lazy* via `Sequence` (stream processing, big payload).
2.  **Ekstensi Sebagai Isolator Batasan (Boundary Decouplers):** Jangan biarkan domain model tercemar oleh anotasi serialisasi JSON framework atau ORM database. Gunakan ekstensi fungsi Kotlin di lapisan luar (*Interface Adapters*) untuk memproyeksikan Entity ke DTO dan sebaliknya. Ekstensi bertindak sebagai perekat *zero-overhead* yang menjaga *Domain Layer* tetap murni (*POKO - Plain Old Kotlin Object*).
3.  **Serialisasi Berbasis Kompilasi vs Refleksi:** Di masa lalu, Java backend mengandalkan refleksi runtime (Jackson, Gson) yang lambat, rakus memori, dan rentan terhadap *deserialization gadget attacks*. Mental model modern Kotlin mengandalkan **Compiler-Generated Serialization** (`kotlinx.serialization`) yang deterministik, statically typed, dan kompatibel secara native dengan GraalVM Native Image.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur aliran data menyeluruh dari HTTP Request JSON mentah hingga tersimpan di basis data melalui Clean Architecture dengan penerapan Koleksi, Ekstensi, dan Serialization:

```
[ HTTP Inbound Request (JSON Payload) ]
                  |
                  v
[ Infrastructure: HTTP Engine / Ktor / Spring WebFlux ]
                  |
                  | (1) kotlinx.serialization via compiler-generated KSerializer
                  v
[ Interface Adapter: Inbound DTO (Data Transfer Object) ]
                  |
                  | (2) Domain Mapping via Kotlin Extension Function: DTO.toDomain()
                  v
[ Application: Use Case / Interactor ]
                  |
                  | (3) Business Logic Execution:
                  |     - Sequence / Flow Transformations
                  |     - Pure Validation on Domain Entities
                  v
[ Domain Layer: Entities & Aggregates (Pure Kotlin, No Framework Annotations) ]
                  |
                  | (4) Persistence Mapping via Extension Function: Entity.toDbRecord()
                  v
[ Interface Adapter: Repository Implementation ]
                  |
                  | (5) Query Generation / Persistence Execution
                  v
[ Infrastructure: Database / Event Broker (PostgreSQL, Kafka, etc.) ]
```

### Siklus Transformasi State:
1. **Raw Byte Stream / String:** Diterima dari soket jaringan.
2. **Untrusted DTO:** Didekode tanpa refleksi runtime oleh `kotlinx.serialization` yang menerapkan validasi skema dasar.
3. **Validated Domain Model:** Diisolasi melalui extension mapper; data yang salah divalidasi menjadi typed errors (`Result<T>`).
4. **Batch Processing Domain Operations:** Koleksi dimanipulasi dengan `Sequence` untuk menghindari alokasi array list sementara di memory heap.
5. **Persistence Object:** Dipetakan kembali menjadi bentuk native basis data via *data-access extensions*.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Bytecode: Extension Function
Kotlin tidak menyuntikkan method secara fisik ke dalam class yang diperluas. Ekstensi fungsi diubah oleh compiler (`kotlinc`) menjadi method `public static final` standar di Java Bytecode dengan receiver type sebagai argumen pertama.

*Kode Kotlin:*
```kotlin
package com.backend.adapter

import com.backend.domain.User

fun User.toDto(): UserResponseDto = UserResponseDto(
    id = this.id.value,
    displayName = "${this.firstName} ${this.lastName}"
)
```

*Dekomposisi Bytecode (Java Equivalent):*
```java
package com.backend.adapter;

import com.backend.domain.User;
import kotlin.jvm.internal.Intrinsics;
import org.jetbrains.annotations.NotNull;

public final class UserMappersKt {
    @NotNull
    public static final UserResponseDto toDto(@NotNull User $this$toDto) {
        Intrinsics.checkNotNullParameter($this$toDto, "$this$toDto");
        String str = $this$toDto.getId().getValue();
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append($this$toDto.getFirstName());
        stringBuilder.append(" ");
        stringBuilder.append($this$toDto.getLastName());
        return new UserResponseDto(str, stringBuilder.toString());
    }
}
```
*Dampak Performa:* Tidak ada alokasi wrapper objek baru. Zero runtime overhead. Pemanggilan bersifat resolusi statis (`invokestatic`), bukan dynamic dispatch (`invokevirtual`), yang sangat mudah di-inline oleh JVM JIT (Just-In-Time) compiler.

### 2. Mekanisme Internal: `kotlinx.serialization`
Pustaka `kotlinx.serialization` tidak menggunakan `java.lang.reflect.*` saat parsing format data.
*   Ketika compiler melihat `@Serializable`, compiler plugin menyuntikkan *nested static class* bernama `$serializer` yang mengimplementasikan antarmuka `KSerializer<T>`.
*   Compiler menghasilkan method `serialize` dan `deserialize` yang memanggil `CompositeEncoder`/`CompositeDecoder` dengan pemetaan *hardcoded index*.
*   *Index-based deserialization loop* membaca stream token dan melakukan switch-case terhadap index atribut secara langsung. Pendekatan ini setara dengan efisiensi parser biner manual hand-crafted, mengeliminasi kebutuhan lookup metadata berbasis runtime reflection.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. `Iterable` vs `Sequence`: Model Evaluasi Memori
*   **Iterable (Eager Evaluation):** Setiap operasi rantai (`map`, `filter`, `take`) membuat alokasi koleksi perantara (*intermediate collection* / ArrayList baru) di JVM Heap.
    $$\text{Total Memory Allocation} = \sum_{k=1}^{n} M_k$$
    di mana $M_k$ adalah ukuran koleksi perantara pada setiap step $k$. Jika Anda memiliki 100.000 elemen dan menjalankan 3 transformasi berturut-turut, Anda membuat minimal 3 ArrayList raksasa yang langsung menjadi sampah GC.
*   **Sequence (Lazy Evaluation):** Menerapkan evaluasi *element-by-element* horizontal melalui `Iterator` stateless/stateful.
    Elemen pertama melewati seluruh pipa transformasi hingga akhir sebelum elemen kedua mulai diproses. 
    $$\text{Intermediate Collections Allocated} = 0$$
    Hanya instansiasi iterator pembungkus (*decorator*) yang dibuat pada fase setup pipa.

```
ITERABLE (Horizontal/Eager):
Input   [E1, E2, E3]
map     -> ArrayList [E1', E2', E3']   (Alokasi Baru!)
filter  -> ArrayList [E1']             (Alokasi Baru!)

SEQUENCE (Vertical/Lazy):
Input   [E1, E2, E3]
E1 ---> map ---> filter ---> Output
E2 ---> map ---> filter (dropped)
E3 ---> map ---> filter (dropped)
```

### 2. Sealed Interfaces & Polymorphic Serialization
Clean Architecture membutuhkan pemisahan state yang jelas, seperti Domain Events atau Status Transaksi. `kotlinx.serialization` menyelesaikan pemetaan tipe heterogen dengan serialisasi polimorfik melalui diskriminator tipe (biasanya key string `"type"` pada payload JSON).

Dengan menggunakan `sealed interface`, seluruh hierarki kelas ditutup pada waktu kompilasi (*closed set*), memungkinkan compiler mendaftarkan seluruh *subclass serializer* secara statis tanpa perlu pemindaian classpath (*classpath scanning*) pada saat startup aplikasi.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah contoh komprehensif yang mendemonstrasikan evaluasi koleksi lazy, ekstensi domain mapper, dan serialisasi JSON polimorfik tanpa refleksi.

```kotlin
package com.backend.core.fundamentals

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.modules.SerializersModule
import kotlinx.serialization.modules.polymorphic
import kotlinx.serialization.modules.subclass
import java.math.BigDecimal
import java.util.UUID

// ==========================================
// 1. DATA CONTRACT (Infrastructure API DTO)
// ==========================================
@Serializable
sealed interface PaymentMethodDto {
    @Serializable
    data class CreditCard(val panMasked: String, val expiryMonth: Int, val expiryYear: Int) : PaymentMethodDto

    @Serializable
    data class BankTransfer(val virtualAccountNumber: String, val bankCode: String) : PaymentMethodDto
}

@Serializable
data class ProcessPaymentRequestDto(
    val transactionId: String,
    val amount: String,
    val currency: String,
    val paymentMethod: PaymentMethodDto
)

// ==========================================
// 2. DOMAIN MODEL (Pure Business Entities)
// ==========================================
@JvmInline
value class TransactionId(val value: UUID)

enum class Currency { USD, EUR, IDR }

data class Money(val amount: BigDecimal, val currency: Currency) {
    init {
        require(amount >= BigDecimal.ZERO) { "Amount cannot be negative" }
    }
}

sealed interface PaymentInstrument {
    data class Card(val maskedNumber: String) : PaymentInstrument
    data class VirtualAccount(val vaNumber: String, val provider: String) : PaymentInstrument
}

data class Transaction(
    val id: TransactionId,
    val money: Money,
    val instrument: PaymentInstrument
)

// ==========================================
// 3. EXTENSION FUNCTIONS AS BOUNDARY MAPPERS
// ==========================================
fun ProcessPaymentRequestDto.toDomain(): Transaction {
    val parsedId = UUID.fromString(this.transactionId)
    val parsedCurrency = Currency.valueOf(this.currency.uppercase())
    val parsedAmount = BigDecimal(this.amount)

    val domainInstrument = when (val method = this.paymentMethod) {
        is PaymentMethodDto.CreditCard -> PaymentInstrument.Card(method.panMasked)
        is PaymentMethodDto.BankTransfer -> PaymentInstrument.VirtualAccount(
            vaNumber = method.virtualAccountNumber,
            provider = method.bankCode
        )
    }

    return Transaction(
        id = TransactionId(parsedId),
        money = Money(parsedAmount, parsedCurrency),
        instrument = domainInstrument
    )
}

// ==========================================
// 4. SEQUENCE PROCESSING ENGINE
// ==========================================
object TransactionStreamProcessor {
    fun filterHighValueTransactions(
        requests: List<ProcessPaymentRequestDto>,
        threshold: BigDecimal
    ): Sequence<Transaction> {
        return requests.asSequence()
            .map { it.toDomain() }
            .filter { it.money.amount >= threshold }
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah telaah teknis mendalam terhadap kode fundamental di atas:

1.  `@Serializable sealed interface PaymentMethodDto`:
    Mendeklarasikan *sealed contract* untuk DTO. Compiler plugin `kotlinx.serialization` akan mengonfigurasi deskriptor polimorfik. Saat dikonversi ke JSON, sebuah field `"type"` akan otomatis disertakan untuk membedakan antara `CreditCard` dan `BankTransfer`.
2.  `@JvmInline value class TransactionId(val value: UUID)`:
    Fitur *type-driven design* Kotlin. Di tingkat kompilasi, tipe ini memiliki identitas yang berbeda dengan UUID biasa (menghindari parameter mix-up bug). Di tingkat JVM Bytecode, tipe ini di-unboxed langsung menjadi objek `UUID` biasa, meniadakan alokasi heap pembungkus (*zero allocation overhead*).
3.  `data class Money(...) { init { require(...) } }`:
    Lapisan domain bertanggung jawab atas kebenaran bisnis (*invariants*). Pengecekan `amount >= BigDecimal.ZERO` menjamin tidak ada instansiasi state domain yang korup. DTO tidak memvalidasi aturan bisnis; Domain lah yang memvalidasinya.
4.  `fun ProcessPaymentRequestDto.toDomain(): Transaction`:
    Fungsi ekstensi ditempatkan di luar class DTO dan Entity. Class DTO tidak tahu keberadaan Domain, dan Domain sama sekali tidak bergantung pada DTO. Ekstensi ini menjembatani batas arsitektur (*architectural boundary*) secara bersih.
5.  `when (val method = this.paymentMethod)`:
    Kompiler mengecek *exhaustiveness* secara komprehensif. Jika sub-tipe baru ditambahkan ke `PaymentMethodDto`, kode ini akan gagal dikompilasi hingga mapper untuk tipe tersebut ditangani, mencegah *silent unhandled cases*.
6.  `requests.asSequence().map { it.toDomain() }.filter { ... }`:
    Memanggil `asSequence()` menangguhkan alokasi memori. Operasi `toDomain()` dan `filter` dieksekusi secara horizontal satu per satu per elemen. Jika aliran data dipotong dengan `.take(1)`, elemen-elemen setelahnya tidak akan pernah dialokasikan ke memori atau dipetakan ke objek domain.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi:
Sebuah perusahaan FinTech berskala internasional mengoperasikan sistem rekonsiliasi pembayaran massal (*Bulk Clearing and Reconciliation Engine*). Sistem ini menerima file rekonsiliasi harian berukuran beberapa gigabyte yang berisi jutaan record transaksi pembayaran dari berbagai mitra payment gateway (Stripe, Xendit, DLocal) dalam format JSON array terkompresi.

### Masalah:
Implementasi warisan (*legacy*) berbasis Spring MVC & Jackson mengalami *OutOfMemoryError* (Java Heap Space) saat memproses file rekonsiliasi berukuran > 500 MB. Analisis memory heap dump menunjukkan:
1.  Jackson memetakan seluruh file JSON ke pohon memori (`JsonNode` object trees) yang sangat besar.
2.  Pipeline pemrosesan menggunakan Kotlin `Iterable` standar (`.map { ... }.filter { ... }`), mengalokasikan jutaan objek sementara yang membebani Garbage Collector (khususnya fase GC Stop-The-World yang melumpuhkan latency).
3.  Model data ORM bercampur aduk dengan model bisnis, menyebabkan entitas domain terikat langsung ke anotasi serialisasi.

### Solusi Desain Bersih:
Membangun ulang modul rekonsiliasi menggunakan:
1.  **Clean Architecture:** Pemisahan ketat antara Batch Ingestion, Application Domain, dan Persistence.
2.  **Streaming Serialization (`kotlinx.serialization`):** Menggunakan decoding streaming berbasis *low-level token parsing* untuk membaca batch transaksi tanpa memuat seluruh array ke RAM.
3.  **Lazy Sequence Processing:** Mengonsumsi record transaksi melalui Kotlin `Sequence` dengan chunking strategy untuk efisiensi CPU dan alokasi memori konstan $O(1)$.
4.  **Zero-Cost Domain Extensions:** Memetakan skema eksternal ke domain murni dengan ekstensi terisolasi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem rekonsiliasi transaksi dengan Clean Architecture fungsional yang siap pakai.

```kotlin
package com.backend.reconciliation

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeToSequence
import java.io.InputStream
import java.math.BigDecimal
import java.time.Instant

// ============================================================================
// LAYER 1: DOMAIN ENTITIES & VALUE OBJECTS (No framework dependencies)
// ============================================================================
enum class ReconciliationStatus { MATCHED, DISCREPANCY_AMOUNT, UNRECOGNIZED_ACCOUNT }

data class ExternalReference(val systemId: String, val externalId: String)

data class ReconciliationRecord(
    val reference: ExternalReference,
    val clearedAmount: BigDecimal,
    val currency: String,
    val executedAt: Instant
)

data class DiscrepancyReport(
    val reference: ExternalReference,
    val status: ReconciliationStatus,
    val differenceAmount: BigDecimal
)

// Ports (Interface Boundary)
interface TransactionLedgerPort {
    fun fetchLedgerAmount(reference: ExternalReference): BigDecimal?
}

interface ReconciliationAuditPort {
    fun recordDiscrepancies(discrepancies: Sequence<DiscrepancyReport>): Long
}

// ============================================================================
// LAYER 2: USE CASE / APPLICATION ENGINE
// ============================================================================
class ReconcileTransactionsUseCase(
    private val ledgerPort: TransactionLedgerPort,
    private val auditPort: ReconciliationAuditPort
) {
    fun execute(recordsStream: Sequence<ReconciliationRecord>): Long {
        val discrepancySequence = recordsStream
            .map { record ->
                val systemAmount = ledgerPort.fetchLedgerAmount(record.reference)
                evaluateDiscrepancy(record, systemAmount)
            }
            .filter { it.status != ReconciliationStatus.MATCHED }

        return auditPort.recordDiscrepancies(discrepancySequence)
    }

    private fun evaluateDiscrepancy(
        record: ReconciliationRecord,
        systemAmount: BigDecimal?
    ): DiscrepancyReport {
        if (systemAmount == null) {
            return DiscrepancyReport(
                reference = record.reference,
                status = ReconciliationStatus.UNRECOGNIZED_ACCOUNT,
                differenceAmount = record.clearedAmount
            )
        }

        val diff = record.clearedAmount.subtract(systemAmount).abs()
        val isMatched = diff.compareTo(BigDecimal("0.001")) <= 0

        return DiscrepancyReport(
            reference = record.reference,
            status = if (isMatched) ReconciliationStatus.MATCHED else ReconciliationStatus.DISCREPANCY_AMOUNT,
            differenceAmount = diff
        )
    }
}

// ============================================================================
// LAYER 3: INTERFACE ADAPTERS (DTOs, Serializers, Extension Mappers)
// ============================================================================
@Serializable
data class GatewayReconciliationItemDto(
    @SerialName("partner_id") val partnerId: String,
    @SerialName("ext_tx_id") val externalTxId: String,
    @SerialName("settled_amount") val amount: String,
    @SerialName("iso_currency") val currency: String,
    @SerialName("timestamp_epoch_ms") val timestampEpochMs: Long
)

// Zero-overhead boundary mapper via Kotlin Extension Function
fun GatewayReconciliationItemDto.toDomain(): ReconciliationRecord {
    return ReconciliationRecord(
        reference = ExternalReference(
            systemId = this.partnerId,
            externalId = this.externalTxId
        ),
        clearedAmount = BigDecimal(this.amount),
        currency = this.currency.uppercase(),
        executedAt = Instant.ofEpochMilli(this.timestampEpochMs)
    )
}

// ============================================================================
// LAYER 4: INFRASTRUCTURE (Streaming Parsers & Ports Mock)
// ============================================================================
class JsonStreamingReconciliationReader(
    private val jsonConfiguration: Json = Json {
        ignoreUnknownKeys = true
        isLenient = false
    }
) {
    @OptIn(ExperimentalSerializationApi::class)
    fun streamFromInputStream(inputStream: InputStream): Sequence<ReconciliationRecord> {
        // decodeToSequence does not load the entire JSON array in-memory;
        // it parses records one-by-one lazily from the stream.
        return jsonConfiguration.decodeToSequence<GatewayReconciliationItemDto>(inputStream)
            .map { it.toDomain() }
    }
}

// ============================================================================
// SYSTEM DEMONSTRATION & VERIFICATION
// ============================================================================
fun main() {
    val rawJsonPayload = """
        [
          {"partner_id": "STRIPE", "ext_tx_id": "ch_1", "settled_amount": "100.50", "iso_currency": "USD", "timestamp_epoch_ms": 1704067200000},
          {"partner_id": "STRIPE", "ext_tx_id": "ch_2", "settled_amount": "500.00", "iso_currency": "USD", "timestamp_epoch_ms": 1704067260000},
          {"partner_id": "XENDIT", "ext_tx_id": "inv_9", "settled_amount": "250.00", "iso_currency": "USD", "timestamp_epoch_ms": 1704067320000}
        ]
    """.trimIndent()

    // 1. Mock Ports
    val mockLedger = object : TransactionLedgerPort {
        override fun fetchLedgerAmount(reference: ExternalReference): BigDecimal? {
            return when (reference.externalId) {
                "ch_1" -> BigDecimal("100.50") // MATCHED
                "ch_2" -> BigDecimal("480.00") // DISCREPANCY
                else -> null                   // UNRECOGNIZED
            }
        }
    }

    val mockAudit = object : ReconciliationAuditPort {
        override fun recordDiscrepancies(discrepancies: Sequence<DiscrepancyReport>): Long {
            var count = 0L
            discrepancies.forEach {
                count++
                println("AUDIT DISCREPANCY DETECTED: Ref=${it.reference.externalId}, Status=${it.status}, Diff=${it.differenceAmount}")
            }
            return count
        }
    }

    // 2. Assemble Architecture Pipeline
    val reader = JsonStreamingReconciliationReader()
    val useCase = ReconcileTransactionsUseCase(mockLedger, mockAudit)

    // 3. Execute lazy stream processing
    val inputStream = rawJsonPayload.byteInputStream()
    val recordSequence = reader.streamFromInputStream(inputStream)
    val discrepanciesLogged = useCase.execute(recordSequence)

    println("Pipeline Processed Successfully. Total Anomaly Count: $discrepanciesLogged")
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

### Matrix Perbandingan: Deserialization Libraries pada Kotlin Backend

| Karakteristik | `kotlinx.serialization` | Jackson (with Kotlin Module) | Moshi |
| :--- | :--- | :--- | :--- |
| **Metode Parsing** | Static Compiler Plugin (Bytecode generated) | Java Reflection & Dynamic Bytecode | Reflection / KSP Code Gen |
| **Startup Overhead** | Hampir Nol ($0$ runtime metadata initialization) | Tinggi (Scan annotation & build type caches) | Rendah (bila memakai CodeGen) |
| **Throughput (TPS)** | Sangat Tinggi (Minimal overhead) | Sedang hingga Tinggi (Jika cache stabil) | Tinggi |
| **Alokasi Heap Memory** | Sangat Rendah | Tinggi (Banyak alokasi wrapper metadata) | Rendah |
| **GraalVM Native Image**| 100% Out-of-the-box (Tanpa file refleksi JSON) | Membutuhkan Konfigurasi Refleksi Manual | Membutuhkan Konfigurasi Refleksi |
| **Fitur Polymorphism** | Strict, statically checked via Sealed types | Sangat Fleksibel via Object Mappings | Fleksibel via PolyAdapter |
| **Ecosystem Spring Boot**| Butuh registrasi custom converter | First-class citizen bawaan | Butuh konfigurasi custom |

### Matrix Operasi Koleksi: `Sequence` vs `Iterable`

| Dimensi | `Iterable` (Eager) | `Sequence` (Lazy) |
| :--- | :--- | :--- |
| **Ukuran Dataset Kecil (<100 elemen)** | **Lebih Cepat:** Overhead instansiasi state machine iterator Sequence lebih besar dari overhead alokasi array kecil. | **Lebih Lambat:** Biaya setup iterator membayangi eksekusi logic. |
| **Ukuran Dataset Besar (>10.000 elemen)** | **Buruk:** Membuat banyak ArrayList penampung, memicu GC pressure masif. | **Sangat Cepat & Efisien:** Memory overhead $O(1)$, aliran berurutan tanpa penampung antara. |
| **Operasi Terminal Pendek (`first`, `take`)**| **Tidak Efisien:** Tetap mengevaluasi seluruh elemen sebelum dipotong. | **Sangat Optimal (Short-circuiting):** Berhenti tepat saat kondisi terminal terpenuhi. |
| **Debugging / Tracing** | Mudah di-inspect via Breakpoint (Array sudah jadi). | Menantang; harus men-trace pemanggilan iterator `hasNext()`/`next()`. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1.  **Multiple Terminal Operations pada `Sequence`:**
    *Edge Case:* `Sequence` tertentu bersifat *single-use* (misalnya yang membaca langsung dari soket `InputStream` via `decodeToSequence`).
    *Pitfall:* Memanggil `.count()` kemudian `.map()` pada sequence yang sama akan memunculkan exception `IllegalStateException: This sequence can be consumed only once`.
    *Solusi:* Hindari iterasi berganda pada sequence eksternal. Jika data harus dibaca berulang kali, lakukan agregasi ke data structure memory yang persisten via `.toList()` secara eksplisit.
2.  **Shadowing pada Extension Functions:**
    Jika sebuah kelas memiliki method member dengan *signature* persis sama dengan ekstensi fungsi yang Anda tulis, **method member selalu menang**.
    ```kotlin
    class Account {
        fun validate(): Boolean = true
    }
    fun Account.validate(): Boolean = false // DEAD CODE: Tidak akan pernah dieksekusi!
    ```
3.  **Inadvertent Serialization Payload Drift:**
    Secara default, jika sebuah entity DTO ditambahkan field tanpa nilai default, `kotlinx.serialization` akan melempar exception `MissingFieldException` saat parsing JSON lama. Selalu definisikan default value pada DTO evolutif:
    ```kotlin
    @Serializable
    data class UserDto(val id: String, val role: String = "GUEST")
    ```
4.  **Sequence Infinite Loops:**
    Operasi lazy seperti `generateSequence(0) { it + 1 }` akan menghasilkan deret tanpa akhir. Menjalankan operasi agregasi seperti `.toList()` atau `.maxOrNull()` tanpa klausa pembatas `.take(n)` akan menyebabkan infinite loop dan CPU core terkunci 100%.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Mencemari Domain Model dengan Serializer Annotations
```kotlin
// BAD: Domain layer terikat framework serialization
import kotlinx.serialization.Serializable

@Serializable // PELANGGARAN CLEAN ARCHITECTURE!
data class Order(val id: String, val total: Double)
```
```kotlin
// GOOD: Domain entity murni. Anotasi hanya ada di Infrastructure DTO
// File: domain/Order.kt
data class Order(val id: OrderId, val total: Money)

// File: infrastructure/OrderDto.kt
@Serializable
data class OrderResponseDto(val id: String, val total: Double)

fun Order.toResponseDto(): OrderResponseDto = 
    OrderResponseDto(this.id.value, this.total.amount.toDouble())
```

### 2. Menggunakan `Sequence` untuk Operasi Sederhana pada List Kecil
```kotlin
// BAD: Over-engineering. Memory footprint iterator lebih besar dari ArrayList(3)
val roles = listOf("ADMIN", "USER", "OPERATOR")
val hasAdmin = roles.asSequence().filter { it.startsWith("A") }.any()

// GOOD: Direct collections operations jauh lebih cepat untuk sub-100 items
val hasAdmin = roles.any { it.startsWith("A") }
```

### 3. Menggunakan Java-style Static Utils Alih-alih Extension Functions
```kotlin
// BAD: Verbose, tidak idiomatik di Kotlin
object OrderMapperUtils {
    fun mapToDomain(dto: OrderDto): Order { ... }
}
val domain = OrderMapperUtils.mapToDomain(dto)

// GOOD: Fluid API syntax, memanfaatkan context scoping
fun OrderDto.toDomain(): Order { ... }
val domain = dto.toDomain()
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Konfigurasi Global `Json` Non-Permisif:**
    Pada backend production, hindari konfigurasi `Json` instan. Bangun singleton instance yang aman dan konsisten di seluruh container dependensi:
    ```kotlin
    val AppJson = Json {
        ignoreUnknownKeys = true      // Mengizinkan backward compatibility bila payload API bertambah field baru
        coerceInputValues = true      // Mengubah null menjadi default value jika tipe non-nullable memiliki default
        encodeDefaults = false        // Jangan kirim field dengan default value ke wire JSON (mengurangi network payload)
        isLenient = false             // Terapkan strict parsing standar RFC-8259
    }
    ```
2.  **Boundary Extension Scoping:**
    Letakkan *extension mapper* pada layer adapter yang membutuhkannya. Jika DTO hanya relevan untuk HTTP boundary, letakkan fungsi ekstensi `dto.toDomain()` di file yang sama dengan DTO atau modul adapter, jangan mengeksposnya ke domain module.
3.  **Terapkan Explicit Types pada Boundary Mappers:**
    Jangan pernah membiarkan return type extension mapper di-inferensi otomatis oleh compiler jika mapper melintasi boundary layer:
    ```kotlin
    // BAD
    fun UserDto.toDomain() = User(id = this.id)

    // GOOD: Jelas dan aman saat refactor
    fun UserDto.toDomain(): User = User(id = UserId(this.id))
    ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Eliminasi Boxing Menggunakan `@JvmInline value class`
Ketika domain layer Anda membungkus ID seperti `class OrderId(val value: String)`, JVM mengalokasikan header objek pointer (16 byte overhead per objek). Ganti dengan `@JvmInline value class`:
```kotlin
@JvmInline
value class AccountNumber(val raw: String)
```
Di level CPU dan heap, `AccountNumber` diubah langsung menjadi referensi primitive/string mentah, mereduksi konsumsi heap hingga puluhan megabyte pada koleksi transaksi skala besar.

### 2. Mengoptimalkan Ukuran Kapasitas Koleksi
Bila operasi pemetaan eager tidak dapat dihindari, pastikan ukuran koleksi awal dialokasikan dengan tepat untuk mencegah array resizing secara bertahap:
```kotlin
// Hindari re-allocation bertahap pada ArrayList internal
val initialCapacity = inputList.size
val targetList = ArrayList<TargetDomain>(initialCapacity)
inputList.mapTo(targetList) { it.toDomain() }
```

### 3. Chunking Sequences untuk Batch Database Insert
Jangan menjalankan batch database update sebesar 100.000 data sekaligus, dan jangan mengeksekusinya satu per satu ($N+1$). Gunakan fungsi `.chunked()` bawaan sequence:
```kotlin
fun saveAllBatched(records: Sequence<ReconciliationRecord>, repo: DatabaseRepo) {
    records
        .chunked(500) // Memecah stream menjadi chunk 500 item
        .forEach { batchList ->
            repo.insertMany(batchList) // Eksekusi batch SQL insert optimal
        }
}
```

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Cegah Mass Assignment Vulnerabilities:**
    Jangan pernah mengekspos domain model langsung ke HTTP input. Penyerang dapat menyuntikkan field yang tidak diinginkan seperti `is_admin: true` atau `balance: 999999`.
    *Mitigasi:*
    DTO hanya boleh memiliki atribut yang secara sah boleh diisi pengguna. Extension mapper yang mengonversi DTO ke Domain Entity harus menetapkan atribut internal secara eksplisit dari konteks server:
    ```kotlin
    fun UserRegistrationDto.toNewDomain(creatorId: UserId): User {
        return User(
            id = UserId.generate(),
            email = this.email,
            role = Role.STANDARD_USER, // HARDCODED, TIDAK BISA DI-INJECT
            createdBy = creatorId
        )
    }
    ```
2.  **Mencegah Regex / Large Payload DoS:**
    Koleksi masif yang tidak dibatasi dapat membuat CPU hung. Terapkan validasi `take()` maksimum pada seluruh sequence yang berasal dari socket stream tak terpercaya:
    ```kotlin
    fun processUntrustedStream(stream: Sequence<PayloadDto>) {
        val safeStream = stream.take(MAX_ALLOWED_RECORDS + 1)
        var count = 0
        safeStream.forEach {
            count++
            if (count > MAX_ALLOWED_RECORDS) {
                throw PayloadTooLargeException("Payload melebihi batas 10.000 items")
            }
            // Lanjutkan eksekusi
        }
    }
    ```
3.  **Strict Deserialization Types (No Arbitrary Typing):**
    Berbeda dari Jackson yang mengizinkan konfigurasi berisiko seperti `enableDefaultTyping()`, `kotlinx.serialization` membatasi deserialisasi polimorfik hanya pada class yang didefinisikan secara eksplisit via `subclass(...)` di modul serialisasi. Jangan pernah mendaftarkan tipe `Any` ke konfigurasi polimorfik.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Saat memproses koleksi dengan `Sequence` yang bersifat lazy, debugging via breakpoint standar IDE bisa membingungkan karena aliran kode melompat-lompat antar elemen.

### 1. Idiom Logging pada Lazy Pipeline via `.onEach()`
Gunakan operasi `.onEach { ... }` untuk menyisipkan observabilitas tanpa memutus chaining atau memaksa evaluasi memori:
```kotlin
import org.slf4j.LoggerFactory

private val logger = LoggerFactory.getLogger("TransactionPipeline")

fun processStreamWithTrace(stream: Sequence<Transaction>): Sequence<Transaction> {
    return stream
        .onEach { tx ->
            logger.debug("Processing tx: id={}, amount={}", tx.id.value, tx.money.amount)
        }
        .filter { it.money.amount > BigDecimal.ZERO }
        .onEach { tx ->
            // Metrics emission (Micrometer / Prometheus)
            MetricsRegistry.counter("tx.processed.count", "currency", tx.money.currency.name).increment()
        }
}
```

### 2. Masking Sensitif Data Menggunakan Custom Extension
Bangun extension logging khusus untuk mencegah bocornya data sensitif (PII/PCI-DSS) ke konsol log:
```kotlin
fun PaymentInstrument.Card.toLogSafe(): String {
    return "Card(masked=${this.maskedNumber.takeLast(4).padStart(16, '*')})"
}

logger.info("Executed payment with instrument: {}", cardInstrument.toLogSafe())
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

| Konsep | Sintaks / Pola | Kapan Digunakan | Keuntungan Utama |
| :--- | :--- | :--- | :--- |
| **Lazy Stream** | `collection.asSequence()` | Pipeline > 1.000 item atau > 2 chaining transform | Mengeliminasi alokasi intermediate collection. |
| **Short-Circuit** | `sequence.take(n).toList()` | Ingin mengambil data terbatas dari dataset masif | Komputasi berhenti tepat saat elemen ke-$n$ terpenuhi. |
| **Boundary Mapper** | `fun Dto.toDomain(): Entity` | Konversi antar architectural layers | Menjaga layer inti (domain) steril dari framework. |
| **Value Inlining** | `@JvmInline value class Id(val v: String)` | Strongly-typed ID / Primitive Wrappers | Zero memory overhead; unboxed di level JVM. |
| **Serialization** | `@Serializable class Dto(...)` | Inbound/Outbound API Payload | Compile-time generation; reflection-free; super cepat. |
| **Polymorphic JSON**| `@Serializable sealed interface EventDto` | Parsing berbagai tipe payload heterogen | Type-safe JSON handling via discriminator key (`"type"`). |
| **Chunking** | `sequence.chunked(size)` | Batch insert database atau API call | Mengurangi overhead network round-trip secara terkontrol. |

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

Uji penguasaan teknis Anda terhadap materi modul ini dengan menjawab soal-soal berikut:

### Kuis Basic (5 Soal)
1. **Bagaimana kompilasi fungsi ekstensi `fun String.sanitize(): String` direpresentasikan pada tingkat JVM bytecode?**
   * A. Sebagai virtual method yang di-inject langsung ke dalam final class `java.lang.String`.
   * B. Sebagai static method publik di kelas utilitas dengan receiver type (`String`) sebagai parameter pertama.
   * C. Melalui mekanisme dynamic proxy reflection.
   * D. Melalui runtime code replacement via JVM Instrumentation API.
2. **Kapan Anda sebaiknya TIDAK menggunakan `Sequence` dan memilih `Iterable` biasa?**
   * A. Saat dataset berukuran lebih dari 1 juta record.
   * B. Saat dataset berukuran kecil (< 50 elemen) dengan chaining pendek.
   * C. Saat memproses file stream berbasis baris.
   * D. Saat ingin melakukan operasi `take()` pada koleksi tak terhingga.
3. **Mengapa `kotlinx.serialization` memiliki performa startup dan memory footprint yang lebih unggul dibandingkan Jackson standar?**
   * A. Karena `kotlinx.serialization` ditulis dalam bahasa C++ via JNI.
   * B. Karena Jackson tidak mendukung bahasa Kotlin sama sekali.
   * C. Karena `kotlinx.serialization` memanfaatkan plugin compiler yang menghasilkan serializer class statis tanpa inspeksi refleksi runtime.
   * D. Karena `kotlinx.serialization` mengompres semua format JSON menjadi binary zip secara otomatis.
4. **Apa tujuan utama menempatkan DTO dan Domain Entity pada kelas yang berbeda dalam Clean Architecture?**
   * A. Agar baris kode proyek bertambah banyak.
   * B. Mengisolasi aturan bisnis (Domain) dari perubahan kontrak eksternal (API/Database).
   * C. Supaya compiler Kotlin dapat melakukan optimasi inline pada method database.
   * D. Agar tidak perlu menggunakan annotation `@Serializable`.
5. **Apa fungsi dari atribut `@SerialName("custom_name")` pada `kotlinx.serialization`?**
   * A. Menentukan nama tabel basis data di Hibernate.
   * B. Memetakan nama key JSON eksternal ke nama properti Kotlin yang berbeda tanpa mengubah kode domain.
   * C. Mencegah properti agar tidak diekspor ke format JSON.
   * D. Menginstruksikan GC untuk menghapus properti dari memori heap.

### Kuis Intermediate (5 Soal)
6. **Perhatikan kode berikut:**
   ```kotlin
   val seq = sequenceOf(1, 2, 3)
       .map { println("M: $it"); it * 2 }
       .filter { println("F: $it"); it > 2 }
   println("Ready")
   val item = seq.first()
   ```
   **Apa output urutan konsol yang benar saat dieksekusi?**
   * A. `M: 1`, `M: 2`, `M: 3`, `F: 2`, `F: 4`, `F: 6`, `Ready`
   * B. `Ready`, `M: 1`, `F: 2`, `M: 2`, `F: 4`
   * C. `Ready`, `M: 1`, `M: 2`, `M: 3`, `F: 2`, `F: 4`
   * D. `Ready`, `F: 2`, `F: 4`, `M: 1`, `M: 2`
7. **Jika class `Customer` memiliki fungsi anggota `fun recalculate(): Unit` dan di file terpisah Anda menulis `fun Customer.recalculate(): Unit`, fungsi manakah yang akan dipanggil saat `customer.recalculate()` dieksekusi?**
   * A. Compiler error karena ambigu (*ambiguous call*).
   * B. Fungsi ekstensi akan menggantikan (*override*) method member.
   * C. Method member selalu menang dan dieksekusi; fungsi ekstensi diabaikan.
   * D. Keduanya akan dieksekusi secara berurutan.
8. **Mengapa deserialisasi polimorfik pada `kotlinx.serialization` mewajibkan penggunaan `sealed class/interface` atau registrasi eksplisit melalui `SerializersModule`?**
   * A. Karena compiler Kotlin tidak mengizinkan pewarisan kelas biasa.
   * B. Untuk membatasi himpunan kelas yang di-serialize/deserialize secara tertutup sehingga deskriptor dapat dibangun tanpa scan reflection yang berisiko pada runtime.
   * C. Agar file biner hasil kompilasi berukuran lebih kecil dari 1 KB.
   * D. Karena JVM melarang deserialisasi JSON polimorfik tanpa interface.
9. **Apa risiko arsitektur jika Anda memanggil `sequence.toList()` di tengah-tengah lapisan domain use case saat memproses file transaksi rekonsiliasi berukuran 2 GB?**
   * A. Seluruh lazy evaluation dibatalkan seketika, dan jutaan record dialokasikan sekaligus ke heap memori, memicu potensi fatal `OutOfMemoryError`.
   * B. Terjadi compile error karena `Sequence` tidak menyediakan fungsi `.toList()`.
   * C. Database akan otomatis terkunci (*deadlock*).
   * D. Komputer client akan terputus dari jaringan HTTP.
10. **Bagaimana `@JvmInline value class` meningkatkan performa backend jika digunakan sebagai representasi Typed ID (misalnya `OrderId`) pada Domain Entities?**
    * A. Menghapus identitas tipe di waktu kompilasi dan runtime.
    * B. Mengonversi tipe objek menjadi pointer native C.
    * C. Menghindari alokasi wrapper object di JVM heap dengan meng-inline nilai aslinya di bytecode, tetapi tetap menyediakan type-safety pada source code.
    * D. Menyimpan data langsung ke L1 cache CPU tanpa melalui RAM.

---

### Kunci Jawaban & Rasional Singkat

1.  **B** — Compiler Kotlin mengubah extension function menjadi `public static final` method standar Java dengan tipe receiver sebagai parameter ke-0/pertama.
2.  **B** — Untuk ukuran elemen sangat kecil, biaya pembuatan state machine decorator iterator pada `Sequence` melampaui biaya alokasi array kecil biasa.
3.  **C** — `kotlinx.serialization` menyuntikkan bytecode statis saat kompilasi via plugin compiler, mengeliminasi inspeksi refleksi runtime yang lambat.
4.  **B** — Pemisahan model menjamin domain logic tidak rusak ketika ada perubahan skema data dari pihak luar/API contract.
5.  **B** — `@SerialName` digunakan untuk memetakan representasi serial string ke penamaan variabel internal.
6.  **B** — `Ready` dicetak pertama karena Sequence bersifat lazy. Saat `.first()` dipanggil, elemen 1 dievaluasi (`M: 1`, `F: 2` -> false), lalu elemen 2 dievaluasi (`M: 2`, `F: 4` -> true, memenuhi syarat, eksekusi selesai).
7.  **C** — Method member selalu diprioritaskan oleh compiler resolusi panggilan daripada extension function jika signaturnya sama identik.
8.  **B** — `kotlinx.serialization` memegang prinsip closed-world assumptions demi efisiensi dan keamanan (mencegah *arbitrary class injection*).
9.  **A** — `.toList()` adalah operasi terminal eager yang memaksa seluruh isi streamSequence dimasukkan ke dalam memori ArrayList saat itu juga.
10. **C** — `@JvmInline` menghapus *object allocation footprint* di JVM heap dan menggantinya dengan nilai primitif/string mentah saat kompilasi ke bytecode.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek:
**Clean Architecture Streaming Currency Exchange Ledger Service**

### Deskripsi Skenario:
Anda ditugaskan merancang modul backend untuk memproses log transaksi multi-mata uang berkecepatan tinggi. Service menerima ribuan event transaksi valuta asing mentah dalam format JSON stream, memfilter transaksi yang tidak valid, mengonversi nilai valuta asing ke IDR (Rupiah) berdasarkan rate harian, mendeteksi anomali fraud, dan menyimpannya ke ledger repository.

### Persyaratan Arsitektural:
1.  **Struktur Modul Clean Architecture:**
    *   `domain`: Berisi entity `LedgerEntry`, value objects `Amount`, `Currency`, dan interface `LedgerRepositoryPort`. **Dilarang keras ada impor library serialisasi atau framework apapun di package ini!**
    *   `usecase`: Berisi interactor `ProcessFxStreamUseCase` yang menerima input `Sequence<RawTransaction>` dan menghasilkan output transaksi valid.
    *   `adapter`: Berisi DTO JSON (`RawTransactionDto`), pustaka serialisasi (`kotlinx.serialization`), dan file ekstensi pemetaan boundary `RawTransactionDto.toDomain()`.
2.  **Batasan Teknis:**
    *   Wajib menggunakan `@JvmInline value class` untuk `AccountId` dan `TransactionId`.
    *   Wajib menggunakan `kotlinx.serialization.json.decodeToSequence` untuk membaca stream data tanpa OOM.
    *   Seluruh pipeline validasi dan konversi mata uang dalam Use Case harus menggunakan operasi chaining `Sequence` lazy (misal: `.filter { ... }.map { ... }.chunked(100)`).
    *   Terapkan sealed interface untuk status transaksi: `TransactionState.Valid`, `TransactionState.FlaggedFraud`, `TransactionState.InvalidRate`.

### Kriteria Kelulusan (Rubrik Evaluasi):
*   [ ] **Decoupling Integrity:** Package `domain` tidak memiliki referensi ke package `kotlinx.serialization.*` atau dependensi I/O.
*   [ ] **Zero OOM:** Mampu memproses input stream simulasi 500.000 JSON lines dengan memori heap JVM dibatasi (`-Xmx64M`) tanpa terjadi `OutOfMemoryError`.
*   [ ] **Type Safety:** Tidak menggunakan tipe data `String` atau `Double` mentah pada domain entity untuk merepresentasikan ID atau uang.
*   [ ] **Boundary Mappers:** Pemetaan data transfer dilakukan secara idiomatik menggunakan Kotlin Extension Functions.