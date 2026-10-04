# Kurikulum Rekayasa Perangkat Lunak Enterprise: Kotlin Backend
## BAB 09: Modern Backend Clean Architecture
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, *Senior Backend Engineer* diharapkan mampu:
1. **Mengonstruksi Core Domain Murni**: Merancang *Aggregate Roots*, *Entities*, *Value Objects*, dan *Domain Events* menggunakan idiomatik Kotlin tingkat lanjut (`sealed interface`, `@JvmInline value class`, *smart casts*, dan *immutability guarantees*) tanpa dependensi *framework* atau pustaka eksternal pihak ketiga.
2. **Mengisolasi Batasan Arsitektural (*Architectural Boundaries*)**: Mengimplementasikan *Ports and Adapters* (Hexagonal Architecture) secara presisi menggunakan Gradle *multi-module* untuk menjamin *Dependency Inversion Principle* (DIP) berjalan di tingkat *compile-time*.
3. **Mencegah Kebocoran Infrastruktur (*Anti-Corruption Layer*)**: Membangun *persistence* dan *transport adapters* yang memetakan model database/API ke model domain murni tanpa mencemari aturan bisnis dengan anotasi ORM (seperti JPA/Hibernate) atau serializer (Jackson/Kotlinx Serialization).
4. **Menerapkan *Transactional Outbox Pattern***: Mengintegrasikan mutasi status domain dan penerbitan *Domain Event* secara atomik berbasis database transaksi ACID untuk menjamin *eventual consistency* nir-data-hilang (*at-least-once delivery*).
5. **Menegakkan Integritas Arsitektur secara Otomatis**: Mengembangkan *ArchUnit-Kotlin test suites* dalam *pipeline CI/CD* untuk memvalidasi arah dependensi kode secara deterministik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* **Kotlin Core & Type System**: Varians (*in/out*), generic constraints, extension functions, inline/value classes, dan idiomatik functional programming (`fold`, `flatMap`, `runCatching`).
* **Kotlin Coroutines**: Structured concurrency, asynchronous flow, dan context propagation (`CoroutineContext`).
* **Prinsip DDD Taktis**: Entity identity, Value Object equality, Aggregate boundary, dan Domain Invariants.
* **Database & Transaksi**: Isolasi transaksi (READ COMMITTED vs REPEATABLE READ), optimistik locking via versioning, dan engine relational database (PostgreSQL 14+).
* **Build System**: Gradle Kotlin DSL (`build.gradle.kts`) dengan arsitektur multi-module.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi arsitektur bersih (*Clean Architecture / Hexagonal / Ports & Adapters*) pada ekosistem enterprise Kotlin menuntut isolasi total antara logika bisnis (*business rules*) dan detail implementasi (*I/O, database, messaging, web frameworks*).

```
+-----------------------------------------------------------------------------------+
| INFRASTRUCTURE LAYER (Secondary / Driven Adapters)                                |
|  - PostgreSQL R2DBC / Exposed / jOOQ Adapters                                     |
|  - Kafka / RabbitMQ Event Publishers                                              |
|  - Redis Cache & Outbox Poller/CDC Adapters                                       |
+-----------------------------------------------------------------------------------+
                                         │  (Implements)
                                         ▼
+-----------------------------------------------------------------------------------+
| APPLICATION LAYER (Use Cases / Inbound & Outbound Ports)                          |
|  - Input Ports (Command/Query Interfaces)                                         |
|  - Output Ports (SPI: Repository Interfaces, Notification Interfaces)             |
|  - Application Services / Command Handlers (Orchestration)                        |
+-----------------------------------------------------------------------------------+
                                         │  (Depends on)
                                         ▼
+-----------------------------------------------------------------------------------+
| DOMAIN LAYER (Pure Kotlin Core - Zero Framework Dependencies)                     |
|  - Aggregate Roots (Lifecycle & Invariant Management)                             |
|  - Entities (Identity-based Lifecycle)                                            |
|  - Value Objects (Immutable Attributes with Invariants, @JvmInline)               |
|  - Domain Events (Sealed Interfaces)                                              |
|  - Domain Exceptions (Semantic Failures)                                          |
+-----------------------------------------------------------------------------------+
                                         ▲
                                         │  (Invokes)
+-----------------------------------------------------------------------------------+
| PRESENTATION LAYER (Primary / Driving Adapters)                                   |
|  - Ktor Routing / Spring WebFlux Handlers                                         |
|  - gRPC Services / Async Message Consumers                                        |
+-----------------------------------------------------------------------------------+
```

#### Komponen Kunci Domain Engine

1. **Pure Domain Model (`:domain`)**:
   - Berisi kelas POJO murni (*Plain Old Kotlin Objects*).
   - Menggunakan `@JvmInline value class` untuk *strongly typed identifiers* (mencegah *primitive obsession*) tanpa alokasi objek heap tambahan saat runtime JVM menginlinenya ke tipe primitif dasar.
   - Menggunakan `sealed interface` untuk memodelkan *Algebraic Data Types* (ADT), seperti status mesin transaksi dan *domain events*. Pola ini memaksa penanganan exhaustiveness check (`when` branch) di level kompilasi.

2. **Inbound & Outbound Ports (`:application`)**:
   - **Inbound Port**: Interface yang mendefinisikan *use case* yang dapat dipanggil oleh *Primary/Driving Adapters* (misalnya: `PlaceOrderUseCase`).
   - **Outbound Port**: Interface *Service Provider Interface* (SPI) yang mendefinisikan kebutuhan domain terhadap infrastruktur (misalnya: `OrderRepository`, `EventPublisherPort`). Domain mendikte kontrak; infrastruktur tunduk pada kontrak tersebut.

3. **Anti-Corruption Layer (ACL) (`:infrastructure`)**:
   - Lapisan isolasi data. Entitas database (misal: jOOQ Record, Exposed Table, JPA Entity) atau payload JSON eksternal dilarang keras masuk ke `:domain` atau `:application`.
   - ACL bertindak sebagai penerjemah (*bidirectional mapper*) antara representasi persistensi dan model domain.

4. **Transactional Outbox Engine**:
   - Daripada menerbitkan *domain event* langsung ke broker pesan secara sinkron di dalam thread bisnis (yang berisiko memicu *dual-write failure*), *domain event* diserialisasi ke dalam tabel `outbox` database relasional dalam satu transaksi basis data yang sama dengan mutasi status agregat.
   - *Worker asynchronous* (via Coroutine poller atau Change Data Capture seperti Debezium) membaca tabel outbox dan meneruskannya ke Kafka.

---

### 4. Why & What

| Dimensi | Anemic Domain & Fat Controller (Tradisional) | Hexagonal Clean Architecture (Modern Kotlin) |
| :--- | :--- | :--- |
| **Kopling Framework** | Model domain bergantung pada anotasi `@Entity`, `@Table`, `@JsonProperty`. Upgrade framework berisiko merusak logika bisnis. | Core domain adalah Kotlin murni (`stdlib`). Bebas independen dari Spring, Micronaut, atau Ktor. |
| **Proteksi Invarian** | Entitas memiliki getter/setter publik (*anemic*). Validasi tersebar di berbagai layer service. | Seluruh mutasi divalidasi di dalam Aggregate Root/Value Object. Objek mustahil berada dalam *invalid state*. |
| **Testability** | Pengujian unit membutuhkan *mocking engine* kompleks atau database container untuk memvalidasi *business rules*. | Unit test domain murni berjalan instan (dalam hitungan milidetik) tanpa *reflection*, *mocking container*, atau *Spring context*. |
| **Konsistensi Transaksional**| Sering terjadi *dual-write problem* (DB update sukses, tetapi Kafka publish gagal). | Transaksi ACID tunggal mencakup mutasi state agregat dan *outbox recording*. |

---

### 5. How (Workflow Detail)

Alur eksekusi sebuah *write-operation* pada Clean Architecture terisolasi:

```
[Inbound Request (JSON)]
           │
           ▼
[Presentation Adapter] ──(Validasi Sintaks HTTP)──> Mengonversi ke Command DTO
           │
           ▼
[Application Service]  ──(Memanggil Inbound Port)
           │
           ├─ 1. Memanggil Outbound Port (Repository) untuk me-load data historis
           │
[Infrastructure Adapter (Persistence)] ──> Mengambil state mentah dari DB
           │                                 │
           │                                 ▼
           │                     Mengeksekusi ACL Mapper
           │                                 │
           ▼                                 ▼
[Application Service]  <── Mengembalikan instans Aggregate Root Murni
           │
           ├─ 2. Mengeksekusi Invariant Logic pada Aggregate Root:
           │     `order.confirmPayment(paymentReference)`
           │
           ├─ 3. Aggregate Root memvalidasi status internal, mengubah state,
           │     dan mencatat `OrderPaymentConfirmedDomainEvent` ke koleksi internal
           │
           ├─ 4. Memanggil Outbound Port (Repository.save(order))
           │
[Infrastructure Adapter (Persistence)] 
           │
           ├─ 5. Memulai Database Transaction (ACID)
           ├─ 6. Mapping domain state -> DB record; simpan entitas
           ├─ 7. Mapping domain events -> Outbox record; simpan outbox record
           └─ 8. Commit Transaction
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Kelistrikan Internasional
Bayangkan Domain Core Anda adalah sebuah perangkat elektronik berdaya tinggi yang dirancang menggunakan sirkuit presisi (aturan bisnis). Perangkat ini membutuhkan daya dan data input/output standar internasional. 
- *Ports* adalah lubang soket standar universal pada perangkat Anda.
- *Adapters* adalah adaptor konverter colokan fisik. Jika Anda berada di Inggris, Anda menggunakan adaptor Type G (Spring Web / PostgreSQL). Jika Anda pindah ke Jepang, Anda mengganti adaptor ke Type A (gRPC / DynamoDB) tanpa membongkar atau menyolder ulang sirkuit internal perangkat elektronik Anda.

#### Diagram Interaksi Runtime Komponen

```
+-----------------------------------------------------------------------------------+
| PRIMARY ADAPTER                                                                   |
| OrderKtorController                                                               |
|   │                                                                               |
|   │ Command: ConfirmOrderPayment(orderId, txnId)                                  |
|   ▼                                                                               |
| +-------------------------------------------------------------------------------+ |
| | APPLICATION LAYER                                                             | |
| | OrderApplicationService : ConfirmOrderPaymentUseCase (Inbound Port)           | |
| |                                                                               | |
| |   1. order = orderRepository.findById(command.orderId)                        | |
| |   2. order.confirmPayment(command.paymentRef) <──[INVARIANT ASSERTION]        | |
| |   3. orderRepository.save(order)                                              | |
| |        │                                                                      | |
| +--------┼────────────────────────────────────────────────────────────────------+ |
|          │                                                                        |
|          ▼                                                                        |
| +-------------------------------------------------------------------------------+ |
| | SECONDARY ADAPTER                                                             | |
| | OrderPostgreSqlRepository : OrderRepository (Outbound Port)                   | |
| |   │                                                                           | |
| |   ├──> BEGIN TRANSACTION                                                      | |
| |   ├──> INSERT INTO orders ... ON CONFLICT DO UPDATE                           | |
| |   ├──> INSERT INTO transactional_outbox (id, payload, event_type, status) ... | |
| |   └──> COMMIT TRANSACTION                                                     | |
| +-------------------------------------------------------------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Value Objects & Invariant Protection

```kotlin
package com.enterprise.domain.common

import java.math.BigDecimal
import java.util.Currency

@JvmInline
value class CurrencyCode private constructor(val value: String) {
    companion object {
        private val ISO_CURRENCIES = Currency.getAvailableCurrencies().map { it.currencyCode }.toSet()

        fun of(code: String): CurrencyCode {
            val normalized = code.trim().uppercase()
            require(normalized in ISO_CURRENCIES) { "Mata uang tidak valid: $code" }
            return CurrencyCode(normalized)
        }
    }
}

data class Money(
    val amount: BigDecimal,
    val currency: CurrencyCode
) {
    init {
        require(amount >= BigDecimal.ZERO) { "Nilai moneter tidak boleh bernilai negatif: $amount" }
        require(amount.scale() <= 4) { "Skala pecahan desimal maksimum adalah 4 digit" }
    }

    operator fun plus(other: Money): Money {
        require(this.currency == other.currency) { 
            "Mismatch mata uang: ${this.currency.value} vs ${other.currency.value}" 
        }
        return Money(this.amount.add(other.amount), this.currency)
    }
}
```

---

#### Practical Example: Production-Grade Aggregate & Outbox Repository Implementation

Struktur implementasi di bawah ini mencerminkan sistem pemrosesan pesanan enterprise dengan proteksi invarian ketat, *Zero-Framework Domain Core*, dan *Transactional Outbox Pattern*.

##### 1. Domain Layer: Core Entities, Value Objects, Events
```kotlin
package com.enterprise.domain.order

import com.enterprise.domain.common.Money
import java.time.Instant
import java.util.UUID

@JvmInline
value class OrderId(val value: UUID) {
    companion object {
        fun generate(): OrderId = OrderId(UUID.randomUUID())
        fun fromString(raw: String): OrderId = OrderId(UUID.fromString(raw))
    }
}

@JvmInline
value class CustomerId(val value: UUID)

sealed interface OrderStatus {
    data object PendingPayment : OrderStatus
    data object Paid : OrderStatus
    data object Shipped : OrderStatus
    data class Cancelled(val reason: String) : OrderStatus
}

sealed interface OrderDomainEvent {
    val eventId: UUID
    val aggregateId: OrderId
    val occurredOn: Instant

    data class OrderCreated(
        override val eventId: UUID = UUID.randomUUID(),
        override val aggregateId: OrderId,
        val totalAmount: Money,
        override val occurredOn: Instant = Instant.now()
    ) : OrderDomainEvent

    data class OrderPaid(
        override val eventId: UUID = UUID.randomUUID(),
        override val aggregateId: OrderId,
        val paymentReference: String,
        override val occurredOn: Instant = Instant.now()
    ) : OrderDomainEvent
}

// Aggregate Root
class Order private constructor(
    val id: OrderId,
    val customerId: CustomerId,
    val totalAmount: Money,
    var status: OrderStatus,
    val version: Long
) {
    private val _domainEvents = mutableListOf<OrderDomainEvent>()
    val domainEvents: List<OrderDomainEvent> get() = _domainEvents.toList()

    fun clearEvents() {
        _domainEvents.clear()
    }

    fun markAsPaid(paymentReference: String) {
        check(status is OrderStatus.PendingPayment) {
            "Gagal memproses pembayaran. Transisi tidak valid dari status: $status"
        }
        require(paymentReference.isNotBlank()) { "Referensi pembayaran tidak boleh kosong" }

        this.status = OrderStatus.Paid
        _domainEvents.add(
            OrderDomainEvent.OrderPaid(
                aggregateId = this.id,
                paymentReference = paymentReference
            )
        )
    }

    companion object {
        fun create(id: OrderId, customerId: CustomerId, totalAmount: Money): Order {
            val order = Order(
                id = id,
                customerId = customerId,
                totalAmount = totalAmount,
                status = OrderStatus.PendingPayment,
                version = 0L
            )
            order._domainEvents.add(
                OrderDomainEvent.OrderCreated(
                    aggregateId = id,
                    totalAmount = totalAmount
                )
            )
            return order
        }

        fun rehydrate(
            id: OrderId,
            customerId: CustomerId,
            totalAmount: Money,
            status: OrderStatus,
            version: Long
        ): Order = Order(id, customerId, totalAmount, status, version)
    }
}
```

##### 2. Application Layer: Ports & Use Cases
```kotlin
package com.enterprise.application.order.port.out

import com.enterprise.domain.order.Order
import com.enterprise.domain.order.OrderId

interface OrderRepositoryPort {
    suspend fun findById(id: OrderId): Order?
    suspend fun save(order: Order)
}
```

```kotlin
package com.enterprise.application.order.usecase

import com.enterprise.application.order.port.out.OrderRepositoryPort
import com.enterprise.domain.order.OrderId

data class ConfirmPaymentCommand(
    val orderId: String,
    val paymentReference: String
)

interface ConfirmPaymentUseCase {
    suspend fun execute(command: ConfirmPaymentCommand)
}

class ConfirmPaymentService(
    private val orderRepository: OrderRepositoryPort
) : ConfirmPaymentUseCase {

    override suspend fun execute(command: ConfirmPaymentCommand) {
        val orderId = OrderId.fromString(command.orderId)
        val order = orderRepository.findById(orderId)
            ?: throw NoSuchElementException("Order dengan ID $orderId tidak ditemukan")

        // Memanggil Domain Invariant
        order.markAsPaid(command.paymentReference)

        // Persistensi mutasi dan Outbox Events secara atomik
        orderRepository.save(order)
    }
}
```

##### 3. Infrastructure Layer: ACL & Transactional Outbox Storage
```kotlin
package com.enterprise.infrastructure.persistence

import com.enterprise.application.order.port.out.OrderRepositoryPort
import com.enterprise.domain.common.CurrencyCode
import com.enterprise.domain.common.Money
import com.enterprise.domain.order.*
import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString
import kotlinx.serialization.Serializable
import java.sql.Connection
import java.util.UUID
import javax.sql.DataSource

@Serializable
private data class OutboxPayload(
    val eventId: String,
    val eventType: String,
    val aggregateId: String,
    val payloadJson: String
)

class PostgresOrderRepository(
    private val dataSource: DataSource
) : OrderRepositoryPort {

    override suspend fun findById(id: OrderId): Order? {
        val sql = """
            SELECT id, customer_id, total_amount, currency, status, version 
            FROM orders 
            WHERE id = ?
        """.trimIndent()

        dataSource.connection.use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setObject(1, id.value)
                val rs = stmt.executeQuery()
                if (!rs.next()) return null

                val statusStr = rs.getString("status")
                val status = when (statusStr) {
                    "PENDING_PAYMENT" -> OrderStatus.PendingPayment
                    "PAID" -> OrderStatus.Paid
                    "SHIPPED" -> OrderStatus.Shipped
                    else -> OrderStatus.Cancelled("Unknown")
                }

                return Order.rehydrate(
                    id = OrderId(rs.getObject("id", UUID::class.java)),
                    customerId = CustomerId(rs.getObject("customer_id", UUID::class.java)),
                    totalAmount = Money(rs.getBigDecimal("total_amount"), CurrencyCode.of(rs.getString("currency"))),
                    status = status,
                    version = rs.getLong("version")
                )
            }
        }
    }

    override suspend fun save(order: Order) {
        dataSource.connection.use { conn ->
            val initialAutoCommit = conn.autoCommit
            conn.autoCommit = false // Memulai Transaksi ACID Atomik
            try {
                upsertOrder(conn, order)
                saveOutboxEvents(conn, order.domainEvents)
                conn.commit()
                order.clearEvents()
            } catch (ex: Exception) {
                conn.rollback()
                throw ex
            } finally {
                conn.autoCommit = initialAutoCommit
            }
        }
    }

    private fun upsertOrder(conn: Connection, order: Order) {
        val sql = """
            INSERT INTO orders (id, customer_id, total_amount, currency, status, version)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                version = orders.version + 1
            WHERE orders.version = ?
        """.trimIndent()

        val statusString = when (order.status) {
            is OrderStatus.PendingPayment -> "PENDING_PAYMENT"
            is OrderStatus.Paid -> "PAID"
            is OrderStatus.Shipped -> "SHIPPED"
            is OrderStatus.Cancelled -> "CANCELLED"
        }

        conn.prepareStatement(sql).use { stmt ->
            stmt.setObject(1, order.id.value)
            stmt.setObject(2, order.customerId.value)
            stmt.setBigDecimal(3, order.totalAmount.amount)
            stmt.setString(4, order.totalAmount.currency.value)
            stmt.setString(5, statusString)
            stmt.setLong(6, order.version + 1)
            stmt.setLong(7, order.version)

            val affected = stmt.executeUpdate()
            if (affected == 0 && order.version != 0L) {
                throw IllegalStateException("Optimistic Lock Violation saat menyimpan Order: ${order.id.value}")
            }
        }
    }

    private fun saveOutboxEvents(conn: Connection, events: List<OrderDomainEvent>) {
        if (events.isEmpty()) return

        val sql = """
            INSERT INTO transactional_outbox (id, aggregate_type, aggregate_id, event_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?::jsonb, ?)
        """.trimIndent()

        conn.prepareStatement(sql).use { stmt ->
            for (event in events) {
                stmt.setObject(1, event.eventId)
                stmt.setString(2, "ORDER")
                stmt.setString(3, event.aggregateId.value.toString())
                stmt.setString(4, event::class.simpleName)
                
                // Representasi data JSON
                val jsonPayload = when (event) {
                    is OrderDomainEvent.OrderCreated -> 
                        """{"amount": "${event.totalAmount.amount}", "currency": "${event.totalAmount.currency.value}"}"""
                    is OrderDomainEvent.OrderPaid -> 
                        """{"paymentRef": "${event.paymentReference}"}"""
                }
                stmt.setString(5, jsonPayload)
                stmt.setObject(6, java.sql.Timestamp.from(event.occurredOn))
                stmt.addBatch()
            }
            stmt.executeBatch()
        }
    }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem: Core Banking Ledger System (Fintech)
Sebuah bank digital memproses jutaan mutasi rekening (*double-entry bookkeeping*) per hari. Kegagalan umum pada arsitektur monolitik mereka sebelumnya mencakup:
1. Deadlock akibat penguncian database tingkat baris yang terlalu lama saat menghitung saldo.
2. Ketidaksesuaian ledger: akun terdebit, tetapi event mutasi gagal terkirim ke platform analisis kepatuhan anti-pencucian uang (*AML engine*).

#### Solusi Arsitektur
1. **Core Domain Immutability**:
   - Saldo rekening tidak pernah di-*update* secara *in-place*. Mutasi rekening dimodelkan sebagai deretan `JournalEntry` (*Append-Only Ledger Aggregate*).
   - Invarian mutlak: Saldo tidak boleh negatif (`balance >= 0`) dan total Debit harus tepat seimbang dengan total Kredit (`SUM(Debit) == SUM(Kredit)`).

2. **Performa & Outbox CDC**:
   - Menghilangkan *polling query* (`SELECT ... FOR UPDATE`) pada tabel outbox yang menciptakan disk I/O contention.
   - Mengimplementasikan **Debezium CDC (Change Data Capture)** yang langsung membaca *Write-Ahead Log (WAL)* PostgreSQL dari tabel `transactional_outbox` dan mengalirkannya ke Apache Kafka dengan latensi sub-detik (< 100ms) tanpa membebani pool koneksi database aplikasi.

3. **Domain Event Partition Key**:
   - Partisi Kafka menggunakan `AccountId` sebagai routing key. Seluruh mutasi untuk akun yang sama dijamin diproses secara sekuensial tanpa *race conditions* oleh *downstream consumers*.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya & Konsekuensi Negatif | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Strict Clean Arch (Pemisahan Module)** | Modul domain terisolasi mutlak; bebas dari polusi dependensi pihak ketiga; kompilasi cepat per modul. | Penambahan file *boilerplate* (DTO, Command, Domain Model, DB Entity, Mappers). | Buat generator scaffolding (KSP atau live templates IDE); automasi ACL mapping. |
| **Transactional Outbox via CDC** | Jaminan konsistensi data 100% (*zero data-loss*), pelepasan beban query dari aplikasi ke engine engine WAL. | Kerumitan operasional tinggi: ketergantungan pada Debezium, Kafka Connect, dan konfigurasi log replikasi PostgreSQL. | Untuk beban menengah (< 2.000 TPS), gunakan Coroutine Poller outbox berkala sebelum beralih ke Debezium. |
| **Value Classes (`@JvmInline`)**| *Type safety* tanpa alokasi objek heap JVM (menurunkan *GC pressure*). | Terjadi *autoboxing* implisit ketika dilewatkan ke generic parameter atau koleksi interface (`List<OrderId>`). | Gunakan primitif pada *internal processing high-throughput loops* jika profiling profiler menunjukkan *high allocation*. |
| **Optimistic Locking pada Aggregate** | Mencegah bottleneck penguncian database terdistribusi; throughput baca-tulis tinggi. | Permintaan akan gagal (*OptimisticLockException*) jika tingkat benturan konkuren (*contention*) tinggi. | Terapkan *exponential backoff retry* pada layer Application Service. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Memasang Anotasi Framework pada Domain Entities
```kotlin
// SALAH: Anotasi ORM mengikat siklus hidup domain ke engine Hibernate/Jackson
@Entity
@Table(name = "accounts")
data class Account(
    @Id val id: UUID,
    @JsonProperty("customer_name") var name: String // Rusak! Model domain dicemari framework JSON
)

// BENAR: Core domain murni
class Account(
    val id: AccountId,
    val owner: AccountOwner
) {
    // Bisnis invarian...
}
```

#### Kesalahan 2: Menggunakan Mutasi Objek Koleksi Secara Terbuka (*Encapsulation Leak*)
```kotlin
// SALAH: List publik dapat diakses dan dimutasi dari luar Aggregate
class Cart(val items: MutableList<CartItem>)

// Pihak luar bisa langsung memotong invarian:
cart.items.clear() // Invarian diskon atau limit terlewati!

// BENAR: Lindungi koleksi di balik antarmuka read-only
class Cart private constructor(private val _items: MutableList<CartItem>) {
    val items: List<CartItem> get() = _items.toList() // Defensive copy atau List read-only

    fun addItem(item: CartItem) {
        check(_items.size < 50) { "Maksimal item dalam keranjang adalah 50" }
        _items.add(item)
    }
}
```

#### Kesalahan 3: Boxing Implisit pada `@JvmInline Value Class`
Jika Anda memasukkan value class ke dalam polymorphic generic type, Kotlin JVM akan membungkusnya (*boxing*) ke objek heap, menghilangkan optimasi memori:
```kotlin
fun <T> process(value: T) { ... }
val id = OrderId(UUID.randomUUID())
process(id) // Terjadi Boxing! Objek dialokasikan di Heap.

// Troubleshooting: Pertahankan concrete signature di hot-path
fun processOrderId(id: OrderId) { ... } // Zero Allocation (Unboxed)
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Dependency Enforcement**: Modul `:domain` **TIDAK BOLEH** memiliki dependensi Gradle selain `kotlin-stdlib`.
- [ ] **Explicit Aggregate Boundary**: Aggregate Root bertanggung jawab penuh terhadap *seluruh* siklus hidup dan konsistensi entitas internal di bawahnya.
- [ ] **No Public Setters**: Seluruh mutasi status Aggregate harus berupa metode fungsional eksplisit yang mencerminkan *Ubiquitous Language* (misal: `order.cancel(reason)`, bukan `order.setStatus("CANCEL")`).
- [ ] **Optimistic Locking**: Setiap Aggregate Root wajib memelihara field `version: Long` untuk menangani modifikasi paralel di database.
- [ ] **ArchUnit Automation**: Jalankan pengujian Arsitektur untuk memastikan lapisan Presentation tidak langsung menyentuh Domain secara ilegal.

#### Validasi Arsitektur Otomatis dengan ArchUnit:
```kotlin
package com.enterprise.architecture

import com.tngtech.archunit.core.importer.ClassFileImporter
import com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes
import com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses
import org.junit.jupiter.api.Test

class ArchitectureGuardTest {

    private val importedClasses = ClassFileImporter().importPackages("com.enterprise")

    @Test
    fun `domain layer must not depend on application or infrastructure`() {
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat().resideInAnyPackage("..application..", "..infrastructure..", "..presentation..")
            .check(importedClasses)
    }

    @Test
    fun `domain layer must be free from external framework annotations`() {
        classes()
            .that().resideInAPackage("..domain..")
            .should().onlyDependOnClassesThat().resideInAnyPackage("com.enterprise.domain..", "java..", "kotlin..")
            .check(importedClasses)
    }
}
```

---

### 12. Hands-on Practice

Buat dan simpan struktur proyek berikut di `hands-on/m02/`:

```
hands-on/m02/
├── build.gradle.kts
├── settings.gradle.kts
├── domain/
│   ├── build.gradle.kts
│   └── src/main/kotlin/com/enterprise/domain/
│       ├── model/Account.kt
│       └── event/AccountEvents.kt
├── application/
│   ├── build.gradle.kts
│   └── src/main/kotlin/com/enterprise/application/
│       └── port/
│           ├── in/TransferFundsUseCase.kt
│           └── out/AccountRepositoryPort.kt
└── infrastructure/
    ├── build.gradle.kts
    └── src/main/kotlin/com/enterprise/infrastructure/
        └── persistence/InMemoryAccountRepository.kt
```

#### File: `settings.gradle.kts`
```kotlin
rootProject.name = "clean-architecture-production"
include("domain", "application", "infrastructure")
```

#### File: `domain/build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm")
}

dependencies {
    // HANYA STDLIB! Tidak ada dependensi database, json, atau framework
    implementation(kotlin("stdlib"))
}
```

#### File: `application/build.gradle.kts`
```kotlin
plugins {
    kotlin("jvm")
}

dependencies {
    implementation(project(":domain"))
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
}
```

#### File: `domain/src/main/kotlin/com/enterprise/domain/model/Account.kt`
```kotlin
package com.enterprise.domain.model

import com.enterprise.domain.event.AccountDebitedDomainEvent
import com.enterprise.domain.event.DomainEvent
import java.math.BigDecimal
import java.util.UUID

@JvmInline
value class AccountId(val value: UUID)

class Account(
    val id: AccountId,
    private var balance: BigDecimal,
    val version: Long = 0L
) {
    private val _events = mutableListOf<DomainEvent>()
    val events: List<DomainEvent> get() = _events.toList()

    val currentBalance: BigDecimal get() = balance

    fun debit(amount: BigDecimal) {
        require(amount > BigDecimal.ZERO) { "Nominal debit harus bernilai positif" }
        check(balance >= amount) { "Saldo akun tidak mencukupi untuk didebit: Tersedia $balance, Diminta $amount" }

        this.balance = this.balance.subtract(amount)
        _events.add(AccountDebitedDomainEvent(accountId = this.id, debitedAmount = amount))
    }

    fun credit(amount: BigDecimal) {
        require(amount > BigDecimal.ZERO) { "Nominal kredit harus bernilai positif" }
        this.balance = this.balance.add(amount)
    }

    fun clearEvents() {
        _events.clear()
    }
}
```

#### File: `domain/src/main/kotlin/com/enterprise/domain/event/AccountEvents.kt`
```kotlin
package com.enterprise.domain.event

import com.enterprise.domain.model.AccountId
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

sealed interface DomainEvent {
    val eventId: UUID
    val timestamp: Instant
}

data class AccountDebitedDomainEvent(
    override val eventId: UUID = UUID.randomUUID(),
    override val timestamp: Instant = Instant.now(),
    val accountId: AccountId,
    val debitedAmount: BigDecimal
) : DomainEvent
```

---

### 13. Exercise

#### Level Easy
Implementasikan Value Object `EmailAddress` pada layer domain:
- Validasi format email menggunakan regex standar RFC-5322.
- Normalisasi string (lowercase & trim) secara internal.
- Cegah alokasi objek heap menggunakan `@JvmInline value class`.

#### Level Medium
Buat Inbound Port dan Service Application `TransferFundsService` yang menangani operasi pengiriman dana antar 2 akun:
- Buka repository untuk memuat akun sumber dan akun tujuan.
- Lakukan debit pada akun asal dan kredit pada akun target secara atomik.
- Tangani kegagalan `InsufficientFundsException` tanpa menyimpan perubahan parsial.

#### Level Hard
Rancang unit pengujian berbasis State Transition Test pada Aggregate `Subscription`:
- State: `TRIAL`, `ACTIVE`, `SUSPENDED`, `TERMINATED`.
- Aturan Invarian: Transisi hanya diizinkan dari `TRIAL -> ACTIVE`, `ACTIVE -> SUSPENDED`, `SUSPENDED -> ACTIVE`, dan semua status dapat menuju `TERMINATED`. Jika dicoba transisi dari `TERMINATED -> ACTIVE`, sistem wajib melempar exception spesifik domain: `InvalidSubscriptionStateTransitionException`.
- Pastikan setiap transisi memicu domain event yang sesuai dengan metadata tanggal eksekusi yang akurat.

---

### 14. Challenge

**Studi Kasus Sistem Resepsi Multi-Payment Concurrency**  
Sebuah platform checkout tiket konser berskala tinggi menghadapi masalah *flash sale race condition*. 

**Spesifikasi Persyaratan Teknis:**
1. Desain *Aggregate Root* `TicketInventory` yang mengamankan alokasi kursi (misal: 100 kursi tersisa).
2. Tulis implementasi Outbound Adapter menggunakan PostgreSQL dan SQL murni yang menerapkan mekanisme **Optimistic Concurrency Control (OCC)** menggunakan klausa `WHERE version = :expectedVersion`.
3. Skenario: Ketika 50 coroutine konkuren mencoba memesan tiket yang sama secara bersamaan, aggregate harus menjamin kuota tidak pernah oversold (melebihi batas total).
4. Buat penanganan di Application Service dengan strategi **Exponential Backoff and Jitter Retry** untuk mencoba kembali transaksi yang gagal akibat tabrakan versi OCC maksimal 3 kali sebelum mengembalikan kegagalan ke klien.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa modul `:domain` sama sekali tidak boleh bergantung pada pustaka JSON serializer seperti Jackson atau Gson?
2. Bagaimana representasi JVM dari sebuah `@JvmInline value class OrderId(val value: UUID)` ketika dieksekusi di runtime?
3. Sebutkan perbedaan esensial antara sebuah *Entity* dan sebuah *Value Object* dalam domain modeling!
4. Apa peran utama dari sebuah *Inbound Port* pada arsitektur Ports & Adapters?
5. Mengapa Aggregate Root harus menjadi satu-satunya titik masuk (*single gateway*) untuk memodifikasi entitas-entitas di dalam batas agregatnya?

#### B. Pertanyaan Intermediate
6. Bagaimana cara mencegah terjadinya *dual-write problem* ketika sebuah use-case harus mengubah data di PostgreSQL sekaligus menerbitkan event ke Apache Kafka?
7. Mengapa penggunaan JPA/Hibernate secara bawaan sering kali bertentangan dengan prinsip-prinsip DDD murni?
8. Bagaimana implementasi *exhaustiveness checking* Kotlin pada `sealed interface` membantu mencegah bug saat menambahkan tipe status domain baru?
9. Jelaskan perbedaan mendasar antara *Domain Exception* (aturan bisnis) dan *Infrastructure Exception* (I/O)! Di mana keduanya harus dipetakan?
10. Kapan sebuah *Value Class* Kotlin dipaksa mengalami proses *boxing* (alokasi objek ke memori heap) oleh JVM?

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Seorang teknisi junior menginjeksi antarmuka `Spring Data JPA Repository` langsung ke dalam *Domain Entity* agar entitas tersebut dapat memanggil `.save()` secara mandiri (*Active Record Pattern*). Mengapa arsitektur ini cacat fatal pada sistem skala enterprise?
12. **Skenario 2**: Sistem perbankan Anda menggunakan Transactional Outbox dengan pendekatan polling periodik (`SELECT * FROM outbox WHERE status = 'PENDING' LIMIT 100 FOR UPDATE SKIP LOCKED`). Ketika transaksi mencapai 10.000 TPS, CPU PostgreSQL melonjak ke 99%. Bagaimana Anda mendesain ulang arsitektur outbox tersebut untuk mengatasi *bottleneck* I/O?
13. **Skenario 3**: Sebuah Aggregate `Order` memiliki daftar `items: List<OrderItem>`. Seorang pengembang membuat REST controller yang langsung menerima DTO HTTP dan memanggil `order.items.add(newItem)` melalui getter. Mengapa hal ini merusak integritas domain, dan bagaimana cara memblokir celah ini secara permanen di kode Kotlin?

---

### Kunci & Jawaban Quiz

#### Jawaban Basic
1. Modul domain harus independen dari framework/pustaka pihak ketiga agar logika bisnis inti tidak terikat pada format serialisasi atau perubahan versi pustaka. Format representasi JSON adalah detail infrastruktur (Presentation/Transport), bukan logika bisnis inti.
2. Pada tingkat bytecode JVM, *value class* dibuka bungkusnya (*unboxed*) menjadi tipe internalnya (dalam hal ini `java.util.UUID`). Tidak ada instansiasi objek pembungkus baru, sehingga menghemat konsumsi memori heap dan alokasi GC.
3. *Entity* didefinisikan oleh identitas uniknya yang konsisten sepanjang waktu (meskipun atributnya berubah), sedangkan *Value Object* didefinisikan secara mutlak oleh kesetaraan nilai atributnya (*structural equality*), bersifat *immutable*, dan tidak memiliki identitas terpisah.
4. *Inbound Port* (Use Case interface) mendefinisikan kontrak operasi bisnis abstrak yang tersedia untuk dipanggil oleh Primary Adapters (REST, gRPC, CLI) tanpa Primary Adapter mengetahui detail implementasi orkestrasi di Application Layer.
5. Untuk menjamin penegakan invarian bisnis secara konsisten. Jika pihak luar dapat memanipulasi sub-entitas internal secara langsung, batas agregat kehilangan kendali atas integritas status sistemnya.

#### Jawaban Intermediate
6. Dengan menggunakan **Transactional Outbox Pattern**: status agregat dan data event domain disimpan ke dalam database yang sama di dalam satu transaksi ACID lokal tunggal. Event kemudian dibaca secara asinkron dari outbox untuk dikirim ke Kafka.
7. JPA membutuhkan konstruktor tanpa argumen (*no-arg constructor*), visibilitas non-final, setters atau *field reflection*, serta sering mengaburkan batasan agregat melalui pemuatan relasi otomatis (*lazy loading proxy*), yang merusak prinsip invariansi dan immutability DDD.
8. Kompiler Kotlin mewajibkan ekspresi `when` yang mengevaluasi `sealed interface` menangani seluruh kemungkinan subtipe. Jika ada subtipe baru ditambahkan ke `sealed interface`, kode yang belum menangani status tersebut akan langsung gagal kompilasi (*compile-time error*).
9. *Domain Exception* merepresentasikan pelanggaran invarian bisnis logis (misal: `InsufficientBalanceException`) dan tidak boleh mengandung status teknis I/O. *Infrastructure Exception* merepresentasikan kegagalan teknis (misal: `SQLException`, `TimeoutException`). Infrastructure Exception harus ditangkap di adapter dan dipetakan sebelum menembus domain, sedangkan Domain Exception diterjemahkan menjadi kode status representasi (misal: HTTP 422/400) di Primary Adapter.
10. Saat *value class* digunakan sebagai tipe generik (misal: `List<OrderId>`), saat di-cast ke interface yang diimplementasikannya, atau saat dilewatkan ke fungsi yang menerima tipe polimorfik `Any`.

#### Jawaban Skenario Kasus Produksi
11. Menghancurkan *Separation of Concerns* dan prinsip *Inversion of Control*. Entitas menjadi terikat secara permanen pada Spring Data dan JPA, mustahil dilakukan *unit testing* murni tanpa *mocking container DB*, dan merusak batas transaksional yang seharusnya diorkestrasi oleh Application Layer.
12. Ganti pendekatan *polling-based outbox* dengan **Change Data Capture (CDC)** menggunakan engine seperti **Debezium**. Debezium membaca mutasi data langsung dari PostgreSQL Write-Ahead Log (WAL) di level file/disk stream tanpa mengeksekusi query SQL polling pada tabel, membebaskan CPU database dari beban penguncian `FOR UPDATE SKIP LOCKED`.
13. Masalah: Mengizinkan perubahan status internal agregat secara eksternal tanpa validasi batasan invarian (misalnya: melebihi kuota pesanan, kalkulasi ulang total harga).  
    Solusi: 
    - Ubah field internal menjadi privat: `private val _items = mutableListOf<OrderItem>()`.
    - Ekspos sebagai koleksi read-only: `val items: List<OrderItem> get() = _items.toList()`.
    - Wajibkan penambahan item hanya melalui metode agregat: `fun addItem(product: Product, quantity: Int) { /* validasi invarian */ _items.add(...) }`.

---

### 16. Summary

Implementasi lanjutan dari Modern Backend Clean Architecture pada ekosistem enterprise Kotlin menuntut isolasi radikal antara domain core dan detail teknis eksternal. Dengan memanfaatkan fitur-fitur mutakhir bahasa Kotlin—seperti *sealed interfaces* untuk pemodelan status dan event berbasis ADT, `@JvmInline value classes` untuk keamanan tipe dengan efisiensi alokasi memori tinggi, serta Coroutines untuk pemrosesan I/O non-blocking—arsitektur sistem backend dapat mempertahankan integritas data yang kokoh, memiliki performa skalabilitas tinggi, bebas dari degradasi keterikatan framework (*framework agnostic*), dan dapat diuji secara deterministik di lingkungan produksi enterprise.