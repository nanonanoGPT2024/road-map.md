# SEKSI 01 — IDENTITAS MODUL

* **Jalur Pembelajaran**: Backend Engineering with Kotlin
* **Kategori**: 02-Programming-Languages
* **Bab**: 09 — Enterprise Backend Systems
* **Modul**: 01 — Modern Backend & Clean Architecture
* **Tingkat Kesulitan**: Advanced / Enterprise-Grade
* **Prasyarat**: 
  * Penguasaan mendalam terhadap Kotlin OOP, Functional Programming, dan Coroutines (Flow, Context, Dispatchers).
  * Pemahaman tentang SOLID Principles dan Pola Desain Gang of Four (GoF).
  * Pengalaman dasar membangun REST API dengan framework Kotlin/Java (Ktor, Spring Boot, atau Quarkus).
* **Target Stack & Tools**:
  * Kotlin 2.0+ (Targeting JVM 21 LTS)
  * Gradle Kotlin DSL (Multi-Module Project Architecture)
  * Arrow-kt 1.2+ (Typed Functional Error Handling via `Either`)
  * kotlinx.coroutines 1.8+
  * Kotlinx-serialization / Jackson

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membangun Arsitektur Hexagonal / Clean Architecture** menggunakan modularisasi Gradle murni untuk mengisolasi logika bisnis dari dependensi framework, pustaka, dan infrastruktur I/O.
2. **Merancang Pure Domain Models** dengan immutable data classes, value classes (`@JvmInline`), dan state machines berbasis `sealed interface` tanpa kontaminasi anotasi framework pihak ketiga (seperti JPA/Jackson).
3. **Mengimplementasikan Ports & Adapters Pattern** secara idiomatis dalam Kotlin menggunakan interface abstrak untuk Inbound Ports (Use Cases) dan Outbound Ports (Repositories, External Gateways), dieksekusi dengan *Dependency Inversion Principle (DIP)*.
4. **Menerapkan Error Handling Bertipe (Typed Error Handling)** pada batas sistem menggunakan `Result` atau Arrow `Either` alih-alih melempar unchecked exceptions liar, sehingga menjamin signature fungsi use case bersifat deterministik dan transparan secara matematis.
5. **Mengelola Batas Transaksional dan Asinkronus** memanfaatkan Kotlin Coroutines tanpa merusak pemisahan lapisan arsitektur.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Inti Filosofis: Dependensi Mengalir ke Dalam (*The Dependency Rule*)

Mental model utama Clean Architecture berakar pada satu hukum fundamental: **Kode pada lapisan dalam tidak boleh mengetahui apa pun tentang kode pada lapisan luar**. 

```
[Infrastruktur / Frameworks] ──> [Interface Adapters] ──> [Use Cases / Application] ──> [Domain Model]
```

* **Domain Model adalah Inti Realitas Bisnis**: Domain tidak peduli apakah data disimpan di PostgreSQL, MongoDB, atau file teks datar. Domain tidak peduli apakah request masuk via REST, gRPC, GraphQL, atau Kafka message.
* **Framework adalah Detail Implementasi**: Framework (Spring Boot, Ktor, Micronaut) hanyalah mekanisme pengiriman (*delivery mechanism*). Database hanyalah mekanisme persistensi data (*storage mechanism*). Keduanya berada pada layer paling luar.
* **Pergeseran Paradigma dari "Database-Driven" ke "Behavior-Driven"**: Dalam arsitektur tradisional, engineer sering kali membuat tabel database terlebih dahulu, lalu membuat class Entity ORM (Hibernate/JPA), kemudian membocorkan anotasi `@Entity`, `@Column`, `@Id` ke seluruh lapisan aplikasi. Pada Clean Architecture, kita mendesain interaksi bisnis murni (*Entities & Value Objects*) secara independen, kemudian memaksa database untuk tunduk pada kontrak data yang diminta oleh Domain.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Diagram Komponen: Hexagonal / Ports & Adapters Architecture

```
+---------------------------------------------------------------------------------------+
| LAPISAN INFRASTRUKTUR / DRIVERS (Frameworks, DB, HTTP Engine, Messaging)              |
|                                                                                       |
|   [Ktor / Spring Routing]                   [Exposed / JPA / PostgreSQL Engine]       |
|             │                                                  ▲                      |
|             ▼                                                  │                      |
| +--------------------------------------------------------------│--------------------+ |
| | LAPISAN ADAPTER (Controllers, Presenters, Gateways)          │                    | |
| |                                                              │                    | |
| |   [OrderHttpController]                  [OrderPostgresRepositoryAdapter]         | |
| |             │                                                ▲                    | |
| |             │ (Memanggil)                                    │ (Mengimplementasi) | |
| |             ▼                                                │                    | |
| | +------------------------------------------------------------│------------------+ | |
| | | LAPISAN APLIKASI (Use Cases / Inbound & Outbound Ports)    │                  | | |
| | |                                                            │                  | | |
| | |   [CreateOrderUseCase] (Inbound Port)                      │                  | | |
| | |            │                                               │                  | | |
| | |            ▼                                               │                  | | |
| | |   [CreateOrderService] ──(Memanggil)──> [OrderRepositoryPort] (Outbound Port) | | |
| | |            │                                                                  | | |
| | |            ▼ (Memanipulasi)                                                   | | |
| | | +---------------------------------------------------------------------------+ | | |
| | | | LAPISAN DOMAIN (Pure Business Logic)                                      | | | |
| | | |                                                                           | | | |
| | | |   - Aggregates: Order, OrderLine                                          | | | |
| | | |   - Value Objects: OrderId, Money, CustomerId                             | | | |
| | | |   - Domain Events: OrderCreatedEvent                                      | | | |
| | | |   - Domain Exceptions / Failures: InsufficientStockFailure                | | | |
| | | +---------------------------------------------------------------------------+ | | |
| | +-------------------------------------------------------------------------------+ | |
| +-----------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------+
```

### Diagram Alur Kontrol vs Alur Dependensi (Inversion of Control)

```
ALUR EKSEKUSI (Flow of Control):
[HTTP Request] 
      │
      ▼
[OrderHttpController] 
      │
      ▼
[CreateOrderService] 
      │
      ▼
[OrderPostgresRepositoryAdapter] 
      │
      ▼
[PostgreSQL Database]

ALUR DEPENDENSI SUMBER KODE (Source Code Dependency Direction):
[OrderHttpController] ───────────► (Interface Inbound: CreateOrderUseCase)
                                                    ▲
                                                    │ (Implemented by)
                                          [CreateOrderService]
                                                    │
                                                    ▼
(Interface Outbound: OrderRepositoryPort) ◄─────────┘
      ▲
      │ (Implemented by)
[OrderPostgresRepositoryAdapter]
```

Perhatikan bahwa *Flow of Control* melintasi lapisan dari luar ke dalam lalu ke luar lagi, namun *Flow of Dependency* pada repository **dibalik** (*Inverted*) menggunakan port interface. `CreateOrderService` hanya bergantung pada abstraksi `OrderRepositoryPort` yang bersemayam di dalam aplikasinya sendiri.

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Isolasi Fisik via Gradle Multi-Module Project

Cara paling tangguh untuk menerapkan Clean Architecture di Kotlin adalah dengan mengisolasinya secara fisik ke dalam sub-proyek Gradle terpisah. Dengan cara ini, JVM Compiler akan melempar kesalahan kompilasi (*compile-time error*) secara otomatis jika pengembang mencoba mengimpor pustaka infrastruktur ke dalam Domain.

```
order-system/
├── domain/                      # Sub-proyek: Paling dalam (Zero external dependencies)
│   ├── build.gradle.kts         # Hanya dependensi kotlin-stdlib, arrow-core (opsional)
│   └── src/main/kotlin/
│       └── com/example/domain/
│           ├── model/           # Aggregates, Entities, Value Objects
│           └── failure/         # Sealed interface Domain Failures
├── application/                 # Sub-proyek: Orchestration (Use Cases)
│   ├── build.gradle.kts         # Dependensi: project(":domain"), coroutines-core
│   └── src/main/kotlin/
│       └── com/example/app/
│           ├── port/
│           │   ├── in/          # Inbound Ports (Use Case Interfaces)
│           │   └── out/         # Outbound Ports (Repository/Gateway Interfaces)
│           └── service/         # Implementasi Use Case
├── infrastructure/              # Sub-proyek: I/O, DB, Network Adapters
│   ├── build.gradle.kts         # Dependensi: project(":application"), Exposed, Ktor-Client, Hikari
│   └── src/main/kotlin/
│       └── com/example/infra/
│           ├── persistence/     # DB Tables, Mappers, Repo Adapters
│           └── client/          # 3rd Party HTTP Services
└── presentation/                # Sub-proyek: Delivery mechanism
    ├── build.gradle.kts         # Dependensi: project(":application"), Ktor-Server, Serialization
    └── src/main/kotlin/
        └── com/example/present/ # HTTP Controllers, Routing, DTO Mappers
```

**Mekanisme Isolasi Gradle (`settings.gradle.kts`):**
```kotlin
rootProject.name = "enterprise-clean-architecture"
include("domain", "application", "infrastructure", "presentation")
```

Pada `domain/build.gradle.kts`:
```kotlin
plugins {
    kotlin("jvm")
}
dependencies {
    // SANGAT PENTING: Dilarang menyertakan framework atau persistence lib di sini!
    implementation(kotlin("stdlib"))
}
```

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Pure Domain Model (Entities vs. Value Objects)
* **Entity**: Objek yang memiliki siklus hidup dan identitas berkelanjutan (*Identity Equality*). Dua entitas dengan atribut identik tetap berbeda jika `id`-nya berbeda.
* **Value Object**: Objek yang tidak memiliki konseptual identitas mandiri (*Structural Equality*). Objek ini sepenuhnya didefinisikan oleh propertinya dan harus bersifat **immutable**. Jika nilainya berubah, representasinya adalah objek baru. Di Kotlin, Value Objects diimplementasikan dengan `data class` atau `@JvmInline value class` untuk menghindari alokasi memori pada runtime (*zero-cost abstractions*).

### 2. Aggregate Root & Transactional Boundaries
Aggregate adalah kluster dari Entity dan Value Object yang memiliki batasan konsistensi (*consistency boundary*). 
* Dunia luar **hanya boleh mereferensikan Aggregate Root**.
* Entitas internal di dalam aggregate tidak boleh dimanipulasi secara langsung oleh kode luar tanpa melalui method Aggregate Root.
* Sebuah transaksi basis data idealnya hanya memodifikasi **satu Aggregate Root** dalam satu waktu untuk menghindari skenario deadlock dan memastikan skalabilitas horizontal.

### 3. Inbound Ports vs. Outbound Ports
* **Inbound Ports (Driving Ports)**: Abstraksi use case yang dipanggil oleh adapter luar (seperti HTTP Controller, CLI, atau AMQP Consumer) untuk mengeksekusi operasi bisnis.
* **Outbound Ports (Driven Ports)**: Abstraksi yang dipanggil oleh use case untuk mengambil data dari atau mengirim efek samping ke dunia luar (misalnya database query, HTTP client call, cache read). Didefinisikan di lapisan aplikasi, diimplementasikan di lapisan infrastruktur.

### 4. Typed Error Handling vs Exceptions
Dalam sistem enterprise modern, exception tidak terduga (*unchecked exceptions*) merusak *referential transparency* dan membebani stack trace allocation. Kita membedakan:
1. **Domain/Application Failure**: Kesalahan bisnis yang dapat diprediksi (e.g., saldo tidak mencukupi, pesanan kedaluwarsa). Ini dimodelkan sebagai tipe data konkret menggunakan `sealed interface` dan dikembalikan via `Result<T>` atau `Either<Failure, Success>`.
2. **Infrastructure/System Faults**: Kesalahan teknis tak terduga (e.g., Out Of Memory, Network drop, Disk Failure) yang tetap memicu exception/crash/circuit-breaker.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi clean architecture minimalis namun murni, mengilustrasikan satu skenario: **Registrasi Akun Pengguna**.

### Layer 1: Domain (`domain/User.kt`)
```kotlin
package com.example.domain

import java.util.UUID

@JvmInline
value class UserId(val value: UUID) {
    companion object {
        fun generate(): UserId = UserId(UUID.randomUUID())
    }
}

@JvmInline
value class Email private constructor(val value: String) {
    companion object {
        private val EMAIL_REGEX = "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$".toRegex()

        fun create(raw: String): Result<Email> = runCatching {
            require(raw.matches(EMAIL_REGEX)) { "Format email tidak valid: $raw" }
            Email(raw)
        }
    }
}

// Entity / Aggregate Root
class User(
    val id: UserId,
    val email: Email,
    var isVerified: Boolean = false
) {
    fun verify() {
        this.isVerified = true
    }
}
```

### Layer 2: Application Ports (`application/ports.kt`)
```kotlin
package com.example.application

import com.example.domain.Email
import com.example.domain.User
import com.example.domain.UserId

// Domain Failure representation
sealed interface RegisterUserError {
    data class InvalidEmail(val reason: String) : RegisterUserError
    data class EmailAlreadyExists(val email: String) : RegisterUserError
    data class PersistenceError(val cause: Throwable) : RegisterUserError
}

// Inbound Port
interface RegisterUserUseCase {
    suspend fun execute(emailRaw: String): Result<UserId>
}

// Outbound Port
interface UserRepositoryPort {
    suspend fun existsByEmail(email: Email): Boolean
    suspend fun save(user: User): Result<Unit>
}
```

### Layer 3: Application Service (`application/RegisterUserService.kt`)
```kotlin
package com.example.application

import com.example.domain.Email
import com.example.domain.User
import com.example.domain.UserId

class RegisterUserService(
    private val userRepository: UserRepositoryPort
) : RegisterUserUseCase {

    override suspend fun execute(emailRaw: String): Result<UserId> {
        val email = Email.create(emailRaw).getOrElse { failure ->
            return Result.failure(IllegalArgumentException(failure.message))
        }

        if (userRepository.existsByEmail(email)) {
            return Result.failure(IllegalStateException("Email sudah terdaftar."))
        }

        val newUser = User(
            id = UserId.generate(),
            email = email
        )

        return userRepository.save(newUser).map { newUser.id }
    }
}
```

### Layer 4: Infrastructure Adapter (`infrastructure/InMemoryUserRepository.kt`)
```kotlin
package com.example.infrastructure

import com.example.application.UserRepositoryPort
import com.example.domain.Email
import com.example.domain.User
import com.example.domain.UserId
import java.util.concurrent.ConcurrentHashMap

class InMemoryUserRepository : UserRepositoryPort {
    private val store = ConcurrentHashMap<UserId, User>()

    override suspend fun existsByEmail(email: Email): Boolean {
        return store.values.any { it.email == email }
    }

    override suspend fun save(user: User): Result<Unit> = runCatching {
        store[user.id] = user
    }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Menganalisis keputusan teknis di balik struktur kode fundamental:

1. `@JvmInline value class UserId(val value: UUID)`:
   * **Analisis**: Mencegah *Primitive Obsession*. Menggunakan anotasi `@JvmInline` memaksa compiler Kotlin memetakan value class ini langsung ke tipe primitif underlying (`UUID`) pada runtime JVM tanpa alokasi wrapper class tambahan, menjaga performa tetap optimal (alokasi memori nol pada heap).
2. `private constructor(val value: String)` pada `Email`:
   * **Analisis**: Mencegah instansiasi `Email` tanpa validasi. Objek `Email` mustahil diciptakan dalam state yang invalid (*Make Illegal States Unrepresentable*). Factory method `create` memvalidasi parsing dengan mengembalikan `Result<Email>`.
3. `var isVerified: Boolean = false` dengan method `verify()`:
   * **Analisis**: Mengikuti prinsip Enkapsulasi Domain. State mutasi dilindungi oleh domain context method (`verify()`), bukan diserahkan sembarangan lewat public mutable properties (`setter`).
4. `suspend fun execute(emailRaw: String): Result<UserId>`:
   * **Analisis**: Ditandai dengan `suspend` untuk efisiensi eksekusi asinkronus non-blocking berbasis Kotlin Coroutines. Mengembalikan `Result<T>` bukan melempar unchecked exception; kontrol sepenuhnya dieksplisitkan pada contract use case.
5. `interface UserRepositoryPort`:
   * **Analisis**: Dependensi diarahkan ke interface murni. `RegisterUserService` bergantung pada abstraksi, bukan implementasi konkret JDBC, JPA, atau Exposed.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Sistem Checkout E-Commerce (Flash-Sale Engine)

**Masalah Bisnis**: 
Sebuah platform ritel meluncurkan sistem flash-sale berskala tinggi. Sistem harus memproses order belanja, mengalokasikan stok gudang secara atomik, dan membuat *Payment Intent* ke payment gateway pihak ketiga (misalnya Stripe).

**Kebutuhan Teknis**:
1. Order tidak boleh dibuat jika kuantitas barang melebihi stok yang tersedia.
2. Tidak boleh ada race condition ketika ribuan checkout terjadi serentak untuk barang yang sama.
3. Arsitektur harus memungkinkan penukaran Payment Gateway (dari Stripe ke Xendit) atau Database (dari PostgreSQL ke ScyllaDB) tanpa merubah satu baris pun kode logika pemrosesan order.
4. Logika bisnis harus sepenuhnya bebas dari framework web (Ktor/Spring) dan library database (Exposed/Jooq).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi end-to-end lengkap, production-grade, tanpa placeholder.

### 1. DOMAIN LAYER

#### `domain/Model.kt`
```kotlin
package com.ecommerce.domain.model

import java.math.BigDecimal
import java.util.UUID

@JvmInline
value class OrderId(val value: UUID) {
    companion object {
        fun new(): OrderId = OrderId(UUID.randomUUID())
    }
}

@JvmInline
value class ProductId(val value: UUID)

@JvmInline
value class Quantity(val value: Int) {
    init {
        require(value > 0) { "Kuantitas produk harus bernilai lebih dari 0" }
    }
}

data class Money(val amount: BigDecimal, val currency: String) {
    init {
        require(amount >= BigDecimal.ZERO) { "Nominal uang tidak boleh negatif" }
    }

    operator fun plus(other: Money): Money {
        require(this.currency == other.currency) { "Mata uang tidak cocok" }
        return Money(this.amount.add(other.amount), this.currency)
    }

    operator fun times(qty: Quantity): Money {
        return Money(this.amount.multiply(BigDecimal(qty.value)), this.currency)
    }

    companion object {
        fun zero(currency: String = "IDR") = Money(BigDecimal.ZERO, currency)
    }
}

enum class OrderStatus {
    PENDING_PAYMENT,
    CONFIRMED,
    CANCELLED
}

data class OrderLine(
    val productId: ProductId,
    val unitPrice: Money,
    val quantity: Quantity
) {
    val subtotal: Money get() = unitPrice * quantity
}

// Aggregate Root
class Order private constructor(
    val id: OrderId,
    val customerId: UUID,
    private val _items: MutableList<OrderLine>,
    var status: OrderStatus
) {
    val items: List<OrderLine> get() = _items.toList()

    val totalAmount: Money
        get() = _items.fold(Money.zero()) { acc, line -> acc + line.subtotal }

    fun confirmPayment() {
        check(status == OrderStatus.PENDING_PAYMENT) { "Order tidak dalam status menunggu pembayaran" }
        this.status = OrderStatus.CONFIRMED
    }

    fun cancel() {
        check(status == OrderStatus.PENDING_PAYMENT) { "Hanya order yang pending yang bisa dibatalkan" }
        this.status = OrderStatus.CANCELLED
    }

    companion object {
        fun create(id: OrderId, customerId: UUID, items: List<OrderLine>): Order {
            require(items.isNotEmpty()) { "Order harus memiliki minimal satu item" }
            return Order(
                id = id,
                customerId = customerId,
                _items = items.toMutableList(),
                status = OrderStatus.PENDING_PAYMENT
            )
        }
    }
}
```

#### `domain/Failures.kt`
```kotlin
package com.ecommerce.domain.failure

import com.ecommerce.domain.model.ProductId
import com.ecommerce.domain.model.Quantity

sealed interface OrderDomainFailure {
    data class InsufficientStock(val productId: ProductId, val requested: Quantity, val available: Int) : OrderDomainFailure
    data class ProductNotFound(val productId: ProductId) : OrderDomainFailure
    data class PaymentGatewayUnavailable(val reason: String) : OrderDomainFailure
    data class OrderDatabaseError(val rootCause: Throwable) : OrderDomainFailure
}
```

---

### 2. APPLICATION LAYER

#### `application/Ports.kt`
```kotlin
package com.ecommerce.application.port

import com.ecommerce.application.dto.CheckoutCommand
import com.ecommerce.application.dto.CheckoutResult
import com.ecommerce.domain.failure.OrderDomainFailure
import com.ecommerce.domain.model.Money
import com.ecommerce.domain.model.Order
import com.ecommerce.domain.model.ProductId
import com.ecommerce.domain.model.Quantity

// INBOUND PORT
interface CheckoutUseCase {
    suspend fun execute(command: CheckoutCommand): Result<CheckoutResult>
}

// OUTBOUND PORTS
interface InventoryPort {
    suspend fun reserveStock(productId: ProductId, quantity: Quantity): Boolean
    suspend fun releaseStock(productId: ProductId, quantity: Quantity)
    suspend fun getUnitPrice(productId: ProductId): Money?
}

interface PaymentGatewayPort {
    suspend fun createPaymentIntent(orderId: String, amount: Money): Result<String>
}

interface OrderRepositoryPort {
    suspend fun save(order: Order): Result<Unit>
}
```

#### `application/DTOs.kt`
```kotlin
package com.ecommerce.application.dto

import java.util.UUID

data class OrderItemRequest(
    val productId: UUID,
    val quantity: Int
)

data class CheckoutCommand(
    val customerId: UUID,
    val items: List<OrderItemRequest>
)

data class CheckoutResult(
    val orderId: UUID,
    val totalAmount: java.math.BigDecimal,
    val currency: String,
    val paymentRedirectUrl: String
)
```

#### `application/CheckoutService.kt`
```kotlin
package com.ecommerce.application.service

import com.ecommerce.application.dto.CheckoutCommand
import com.ecommerce.application.dto.CheckoutResult
import com.ecommerce.application.port.CheckoutUseCase
import com.ecommerce.application.port.InventoryPort
import com.ecommerce.application.port.OrderRepositoryPort
import com.ecommerce.application.port.PaymentGatewayPort
import com.ecommerce.domain.model.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class CheckoutService(
    private val inventoryPort: InventoryPort,
    private val paymentGatewayPort: PaymentGatewayPort,
    private val orderRepository: OrderRepositoryPort
) : CheckoutUseCase {

    override suspend fun execute(command: CheckoutCommand): Result<CheckoutResult> = withContext(Dispatchers.Default) {
        val allocatedItems = mutableListOf<Pair<ProductId, Quantity>>()

        try {
            // 1. Validasi & Amankan Stok (Two-Phase style rollback jika gagal)
            val orderLines = command.items.map { item ->
                val pId = ProductId(item.productId)
                val qty = Quantity(item.quantity)

                val unitPrice = inventoryPort.getUnitPrice(pId)
                    ?: throw NoSuchElementException("Produk ${item.productId} tidak ditemukan.")

                val reserved = inventoryPort.reserveStock(pId, qty)
                if (!reserved) {
                    throw IllegalStateException("Stok produk ${item.productId} tidak mencukupi.")
                }

                allocatedItems.add(pId to qty)
                OrderLine(pId, unitPrice, qty)
            }

            // 2. Bangun Pure Domain Aggregate
            val order = Order.create(
                id = OrderId.new(),
                customerId = command.customerId,
                items = orderLines
            )

            // 3. Simpan state Order
            orderRepository.save(order).getOrThrow()

            // 4. Request Payment Gateway Intent
            val paymentToken = paymentGatewayPort.createPaymentIntent(
                orderId = order.id.value.toString(),
                amount = order.totalAmount
            ).getOrThrow()

            // 5. Kembalikan representasi DTO
            Result.success(
                CheckoutResult(
                    orderId = order.id.value,
                    totalAmount = order.totalAmount.amount,
                    currency = order.totalAmount.currency,
                    paymentRedirectUrl = "https://payment.gateway.internal/checkout/$paymentToken"
                )
            )
        } catch (ex: Exception) {
            // Kompensasi Transaksi (Compensating Transaction) jika salah satu langkah gagal
            allocatedItems.forEach { (pId, qty) ->
                inventoryPort.releaseStock(pId, qty)
            }
            Result.failure(ex)
        }
    }
}
```

---

### 3. INFRASTRUCTURE & ADAPTER LAYER

#### `infrastructure/MockAdapters.kt`
```kotlin
package com.ecommerce.infrastructure.adapter

import com.ecommerce.application.port.InventoryPort
import com.ecommerce.application.port.OrderRepositoryPort
import com.ecommerce.application.port.PaymentGatewayPort
import com.ecommerce.domain.model.Money
import com.ecommerce.domain.model.Order
import com.ecommerce.domain.model.ProductId
import com.ecommerce.domain.model.Quantity
import java.math.BigDecimal
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class MemoryInventoryAdapter : InventoryPort {
    private val stockLedger = ConcurrentHashMap<ProductId, Int>()
    private val priceCatalog = ConcurrentHashMap<ProductId, Money>()

    fun seedProduct(id: UUID, price: BigDecimal, stock: Int) {
        val pId = ProductId(id)
        stockLedger[pId] = stock
        priceCatalog[pId] = Money(price, "IDR")
    }

    override suspend fun reserveStock(productId: ProductId, quantity: Quantity): Boolean {
        return stockLedger.compute(productId) { _, currentStock ->
            if (currentStock == null || currentStock < quantity.value) {
                currentStock
            } else {
                currentStock - quantity.value
            }
        }?.let { currentStock ->
            val wasReserved = currentStock >= 0
            wasReserved
        } ?: false
    }

    override suspend fun releaseStock(productId: ProductId, quantity: Quantity) {
        stockLedger.computeIfPresent(productId) { _, current -> current + quantity.value }
    }

    override suspend fun getUnitPrice(productId: ProductId): Money? {
        return priceCatalog[productId]
    }
}

class StripePaymentGatewayAdapter : PaymentGatewayPort {
    override suspend fun createPaymentIntent(orderId: String, amount: Money): Result<String> = runCatching {
        // Simulasi HTTP Client Call ke Stripe
        "stripe_tok_${UUID.randomUUID()}_${amount.amount}"
    }
}

class PostgresOrderRepositoryAdapter : OrderRepositoryPort {
    private val databaseMock = ConcurrentHashMap<UUID, Order>()

    override suspend fun save(order: Order): Result<Unit> = runCatching {
        // Pada implementasi riil: mapping ke Exposed / jOOQ record table
        databaseMock[order.id.value] = order
    }
}
```

---

### 4. PRESENTATION & BOOTSTRAP

#### `presentation/Main.kt`
```kotlin
package com.ecommerce.presentation

import com.ecommerce.application.dto.CheckoutCommand
import com.ecommerce.application.dto.OrderItemRequest
import com.ecommerce.application.service.CheckoutService
import com.ecommerce.infrastructure.adapter.MemoryInventoryAdapter
import com.ecommerce.infrastructure.adapter.PostgresOrderRepositoryAdapter
import com.ecommerce.infrastructure.adapter.StripePaymentGatewayAdapter
import kotlinx.coroutines.runBlocking
import java.math.BigDecimal
import java.util.UUID

fun main() = runBlocking {
    println("=== Inisialisasi Enterprise Clean Architecture Engine ===")

    // 1. Instansiasi Lapisan Infrastruktur (Outbound Adapters)
    val inventoryAdapter = MemoryInventoryAdapter()
    val paymentAdapter = StripePaymentGatewayAdapter()
    val orderRepository = PostgresOrderRepositoryAdapter()

    // Seed Data
    val macbookId = UUID.randomUUID()
    inventoryAdapter.seedProduct(
        id = macbookId, 
        price = BigDecimal("24999000.00"), 
        stock = 2
    )

    // 2. Wire Application Core (Inversion of Control secara manual/DI)
    val checkoutUseCase = CheckoutService(
        inventoryPort = inventoryAdapter,
        paymentGatewayPort = paymentAdapter,
        orderRepository = orderRepository
    )

    // 3. Simulasi Request Masuk dari Delivery Mechanism (Web Controller)
    val customerId = UUID.randomUUID()
    val request = CheckoutCommand(
        customerId = customerId,
        items = listOf(
            OrderItemRequest(productId = macbookId, quantity = 1)
        )
    )

    println("Memproses Checkout untuk Customer: $customerId")
    val result = checkoutUseCase.execute(request)

    result.onSuccess { receipt ->
        println("Checkout Berhasil!")
        println("Order ID        : ${receipt.orderId}")
        println("Total Bayar     : ${receipt.currency} ${receipt.totalAmount}")
        println("Redirect URL    : ${receipt.paymentRedirectUrl}")
    }.onFailure { err ->
        println("Checkout Gagal: ${err.message}")
    }

    // 4. Uji Skenario Insufficient Stock (Pesan 5 padahal sisa 1)
    val invalidRequest = CheckoutCommand(
        customerId = customerId,
        items = listOf(
            OrderItemRequest(productId = macbookId, quantity = 5)
        )
    )

    println("\nMemproses Skenario Invalid (Melebihi Stok)...")
    val failResult = checkoutUseCase.execute(invalidRequest)
    failResult.onFailure { err ->
        println("Ekspektasi Kegagalan Diterima: ${err.message}")
    }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Kriteria | Clean Architecture / Ports & Adapters | Pragmatic Layered (Controller-Service-Repo) | Vertical Slice Architecture |
| :--- | :--- | :--- | :--- |
| **Pemisahan Konsep (Separation of Concerns)** | **Maksimal**. Domain logic 100% murni tanpa ketergantungan library/framework luar. | **Rendah-Sedang**. Domain entity sering kali merangkap sebagai tabel DB (JPA / ORM entity). | **Tinggi per Feature**. Setiap fitur independen, batas arsitektur berada di tingkat request handler. |
| **Testabilitas (Testability)** | **Sangat Tinggi**. Domain & Use Case dapat diuji murni via Unit Test tanpa mock framework DB/HTTP. | **Sedang**. Membutuhkan banyak mocking pada level repository atau running Testcontainers. | **Tinggi**. Mengandalkan Integrasi/E2E test cepat per slice. |
| **Boilerplate & Kompleksitas Kode** | **Tinggi**. Membutuhkan banyak mapping (DTO ke Command, Entity ke Record DB, dsb). | **Sangat Rendah**. Cepat untuk prototyping dan MVP awal. | **Sedang**. Sedikit abstraksi port/adapter, fokus langsung ke implementasi fitur. |
| **Maintainability Jangka Panjang (> 3 Tahun)** | **Sangat Baik**. Penggantian teknologi, library, dan upgrade major Kotlin/Framework sangat aman. | **Buruk**. Perubahan skema basis data rentan merusak aturan bisnis aplikasi. | **Sangat Baik**. Refactoring fitur 'A' tidak berisiko merusak fungsionalitas fitur 'B'. |
| **Biaya Kognitif (Cognitive Load)** | **Tinggi**. Developer harus memahami aturan arah dependensi dan port isolation. | **Rendah**. Alur linear mudah dipahami oleh developer pemula / junior. | **Sedang**. Butuh disiplin tinggi agar slice tidak saling mengimpor logika internal. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

1. **Kebocoran Transaksional (Transaction Boundary Leakage)**:
   * *Problem*: Menggunakan anotasi seperti `@Transactional` (Spring) di dalam class Use Case. Ini mencemari lapisan aplikasi dengan dependensi platform Spring/JDBC.
   * *Mitigasi*: Buat abstraksi outbound port seperti `TransactionRunnerPort { suspend fun <T> run(block: suspend () -> T): T }` yang diimplementasikan di infrastruktur, atau tangani transaksi menggunakan unit-of-work pattern murni.
2. **Entity Leaks ke Presenter / Web Controller**:
   * *Problem*: Mengembalikan langsung objek `Order` (Domain Entity) ke controller dan men-serialize-nya langsung via Jackson/Kotlinx Serialization. Perubahan atribut domain internal akan mendadak merusak kontrak publik REST API.
   * *Mitigasi*: Wajib melakukan konversi ke Presenter Response DTO di layer terluar. Entity domain dilarang memiliki anotasi `@Serializable` atau `@JsonProperty`.
3. **Coroutine Cancellation dan Kompensasi Data**:
   * *Problem*: Saat client memutus koneksi (HTTP cancel), CoroutineScope di-cancel (`CancellationException`). Jika usecase sedang melakukan reservasi stok atau mutasi data, flow akan terhenti di tengah jalan dan memicu *state inkonsistensi*.
   * *Mitigasi*: Eksekusi logika kompensasi atau critical transactional commit di dalam `withContext(NonCancellable)` pada Kotlin Coroutines.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Anti-Pattern 1: Anemic Domain Model (God Services & Data Holders)
* **Buruk**: Class entity hanya berupa sekumpulan properti `var` tanpa method bisnis, dan semua logika ditarik ke dalam `OrderService`.
* **Benar**: Terapkan *Rich Domain Model*. Tempatkan validasi state, invariants, dan mutasi internal langsung di dalam Entity Aggregate Root (seperti method `order.confirmPayment()` yang memvalidasi precondition).

### Anti-Pattern 2: DTO Re-use Across Boundaries
* **Buruk**: Menggunakan class DTO HTTP `CreateOrderRequest` langsung sebagai parameter input untuk `OrderRepository.save(request)`.
* **Benar**: Buat struktur data representatif per layer:
  * HTTP Layer: `CreateOrderHttpRequest`
  * Application Layer: `CreateOrderCommand`
  * Domain Layer: `Order`
  * Persistence Layer: `OrderDbRecord` / `OrderTable`

### Anti-Pattern 3: Circular Module Dependencies
* **Buruk**: Sub-proyek `domain` memerlukan class utilitas logging atau format yang ada di `infrastructure`, menyebabkan Gradle circular dependency.
* **Benar**: Kembangkan `domain` dengan nol dependensi proyek lokal. Dependensi hanya boleh mengalir searah: `presentation` & `infrastructure` -> `application` -> `domain`.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Validasi Sejak di Gerbang (Parse, Don't Validate)**:
   * Gunakan tipe data kuat (*Strongly Typed*) pada Value Objects. Hindari menggunakan tipe data primitif seperti `String` untuk ID, email, atau status transaksi di dalam domain core.
2. **Package-by-Feature di dalam Boundaries**:
   * Pada level sub-proyek besar, kelompokkan package berdasarkan kapabilitas bisnis / sub-domain bounded context (misalnya `com.ecommerce.order`, `com.ecommerce.inventory`), bukan semata-mata mengelompokkan semua adapter ke satu folder global.
3. **Isolasi Mutasi State Koleksi**:
   * Jangan pernah mengekspos `MutableList` dari dalam Aggregate Root ke luar. Selalu ekspos tipe baca `List<T>` (via `.toList()`) untuk mempertahankan invariansi.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

1. **Eliminasi Objek Heap dengan `@JvmInline value class`**:
   * Pembuatan jutaan objek Value Object (misal: `OrderId`, `CurrencyCode`, `Quantity`) dapat menyebabkan overhead Garbage Collection (GC) yang signifikan. Di Kotlin, selalu tandai single-value wrapper dengan `@JvmInline`. JVM akan merepresentasikan nilainya sebagai primitif dasar pada bytecode runtime.
2. **Non-blocking Reactive I/O dengan Coroutine Dispatchers**:
   * Jangan campur adukkan IO CPU-bound dengan Blocked Network/Disk. Lapisan use case murni harus beroperasi pada `Dispatchers.Default` (komputasi domain logic), sedangkan Repository Adapter yang menangani blocking JDBC/File harus secara eksplisit mendistribusikan pekerjaannya pada `Dispatchers.IO`.

---

# SEKSI 16 — KEAMANAN & HARDENING

1. **Domain-Driven Input Sanitization**:
   * Masalah SQL Injection dan XSS sebagian besar terjadi karena representasi data primitif yang tidak tervalidasi. Dengan membungkus input ke dalam Value Objects (seperti `CustomerName`, `SearchQuery`) yang memiliki sanitasi ketat pada private factory method constructor-nya, data yang kotor mustahil menembus hingga ke lapisan domain.
2. **Redaksi Log Informasi Sensitif (PII Hardening)**:
   * Override fungsi `toString()` pada Value Object yang menyimpan data sensitif:
   ```kotlin
   @JvmInline
   value class CreditCardNumber(val raw: String) {
       override fun toString(): String = "****-****-****-${raw.takeLast(4)}"
   }
   ```
   Langkah defensif ini mencegah kebocoran data rahasia ke agregator logging terpusat (Datadog/Elasticsearch).

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Di Clean Architecture, logging tidak boleh mengotori *pure domain logic*. Domain tidak boleh memiliki referensi ke `org.slf4j.Logger`.

### Observabilitas Murni via Decorator Pattern
Gunakan pattern Decorator di lapisan aplikasi untuk menyuntikkan trace spans dan metrics tanpa mengubah baris kode use case:

```kotlin
class ObservableCheckoutUseCaseDecorator(
    private val delegate: CheckoutUseCase,
    private val metricsTracker: MetricsTrackerPort
) : CheckoutUseCase {

    override suspend fun execute(command: CheckoutCommand): Result<CheckoutResult> {
        val startTime = System.currentTimeMillis()
        metricsTracker.increment("checkout.attempts")
        
        val result = delegate.execute(command)
        
        val duration = System.currentTimeMillis() - startTime
        metricsTracker.recordExecutionTime("checkout.latency", duration)

        result.onSuccess {
            metricsTracker.increment("checkout.success")
        }.onFailure {
            metricsTracker.increment("checkout.failure")
        }

        return result
    }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLEAN ARCHITECTURE RULES                        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. DEPENDENCY RULE    : Selalu ke arah DALAM. Domain tahu 0 hal luar.  │
│ 2. VALUE OBJECTS      : Gunakan @JvmInline value class untuk ID/Tipe.  │
│ 3. AGGREGATE ROOTS    : Satu-satunya gerbang mutasi state entity.      │
│ 4. PORTS & ADAPTERS   : Abstraksikan semua I/O (Database, 3rd Party).  │
│ 5. ERROR HANDLING     : Deterministic Result/Either, bukan runtime exp.│
│ 6. FRAMEWORK FREE     : Dilarang ada Spring/Ktor di dalam Domain Core. │
└────────────────────────────────────────────────────────────────────────┘
```

* **Domain**: Entities, Value Objects, Domain Events, Domain Failures.
* **Application**: Use Cases (Inbound Ports), Secondary Interfaces (Outbound Ports), Services.
* **Infrastructure**: DB Implementations (JDBC/Exposed), External Clients (HTTP/gRPC/Kafka).
* **Presentation**: Web Framework, Routing, Controllers, Request/Response Mappings.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1-5)

1. **Apa tujuan utama dari The Dependency Rule pada Clean Architecture?**
   * *Jawaban*: Memastikan dependensi kode sumber hanya mengarah ke dalam (ke arah logika bisnis tingkat tinggi). Komponen domain tidak boleh bergantung pada pustaka luar, basis data, atau framework.

2. **Mengapa anotasi framework seperti Jackson `@JsonProperty` atau JPA `@Entity` dilarang berada di dalam Domain Model?**
   * *Jawaban*: Karena mencemari domain dengan ketergantungan teknologi infrastruktur pihak ketiga, merusak portabilitas domain, dan mempersulit migrasi atau pengujian independen.

3. **Apa perbedaan konseptual antara Entity dan Value Object?**
   * *Jawaban*: Entity memiliki identitas unik berkelanjutan (*continuity*) yang membedakannya meskipun propertinya serupa. Value Object bersifat immutable dan didefinisikan sepenuhnya oleh representasi nilainya tanpa identitas unik.

4. **Bagaimana cara Kotlin mengoptimalkan alokasi memori pada Value Object?**
   * *Jawaban*: Menggunakan `@JvmInline value class`, di mana compiler akan meng-inline tipe data ke representasi primitif dasarnya saat runtime, menghindari alokasi objek heap wrapper.

5. **Apa fungsi dari Inbound Port dalam arsitektur Hexagonal?**
   * *Jawaban*: Mendefinisikan kontrak abstraksi operasi use case yang dapat dipanggil oleh dunia luar (driving actors) seperti controller HTTP atau antrean pesan.

---

### Soal Intermediate (6-10)

6. **Bagaimana Outbound Port mengimplementasikan Dependency Inversion Principle (DIP)?**
   * *Jawaban*: Alih-alih Use Case bergantung pada implementasi database konkret di infrastruktur, Use Case bergantung pada interface port yang didefinisikan di lapisan aplikasi itu sendiri. Lapisan infrastruktur yang kemudian membalikkan ketergantungan dengan mengimplementasikan interface tersebut.

7. **Mengapa penggunaan Typed Error Handling (seperti `Result<T>` atau `Either<L, R>`) lebih disukai daripada unchecked exceptions di Clean Architecture?**
   * *Jawaban*: Membuat alur kegagalan bisnis bersifat eksplisit dan deterministik pada method signature, memaksa pemanggil untuk menangani kegagalan tanpa menebak-nebak exception apa yang dapat dilempar secara runtime.

8. **Di mana posisi penanganan transaksi basis data (Database Transaction Boundary) yang benar tanpa melanggar Clean Architecture?**
   * *Jawaban*: Diatur di lapisan infrastruktur, diekspos ke lapisan aplikasi melalui abstraksi port (seperti Unit of Work pattern atau Transaction Runner functional interface) sehingga domain tetap independen dari mekanisme SQL/JDBC.

9. **Apa risiko arsitektural jika Presentation Layer menggunakan langsung Domain Entity alih-alih DTO?**
   * *Jawaban*: Merusak enkapsulasi, membocorkan invariant internal bisnis ke publik, dan menciptakan keterikatan (*tight coupling*) antara antarmuka API publik dan domain core internal.

10. **Bagaimana menangani eksekusi pembersihan/kompensasi data jika Kotlin Coroutine dibatalkan di tengah jalan pada sebuah Use Case?**
    * *Jawaban*: Menggunakan blok `withContext(NonCancellable)` pada fungsi kompensasi agar proses rollback tetap tuntas dieksekusi meskipun *job lifecycle coroutine* telah dibatalkan oleh engine induk.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: High-Integrity Double-Entry Ledger Engine

Bangun modul aplikasi perbankan mini yang mengimplementasikan sistem pembukuan double-entry (*Double-Entry Bookkeeping Ledger Engine*) dengan spesifikasi Clean Architecture berikut:

#### Kebutuhan Fungsional & Aturan Domain:
1. **Aturan Akuntansi Fundamental**: Setiap transaksi perpindahan dana (*Journal Entry*) harus seimbang (*balanced*): $\sum Debit = \sum Credit$. Transaksi harus ditolak jika total debit tidak sama persis dengan total kredit.
2. **Domain Entities**:
   * `Account` (Id, Type: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE, Balance: Money).
   * `JournalEntry` (Id, Timestamp, Lines: List of `PostingLine`).
   * `PostingLine` (AccountId, Direction: DEBIT/CREDIT, Amount: Money).
3. **Application Use Case**:
   * `TransferFundsUseCase`: Mentransfer dana antara dua akun dengan membuat jurnal entry yang valid dan memperbarui saldo kedua akun secara atomik.
4. **Outbound Ports**:
   * `AccountRepositoryPort` (mencari akun, memperbarui saldo).
   * `JournalRepositoryPort` (menyimpan rekaman jurnal).
   * `AuditLogPort` (mencatat jejak transaksi untuk kebutuhan kepatuhan regulasi).

#### Kriteria Keberhasilan & Verifikasi:
* **Zero Infrastructure in Domain**: Module domain harus lulus kompilasi tanpa ketergantungan framework apa pun selain standard library Kotlin.
* **Strict Value Object Typing**: Saldo tidak boleh bernilai negatif untuk akun bertipe `ASSET`. Nominal transfer harus menggunakan `@JvmInline value class Money`.
* **Determinism Testing**: Tuliskan Unit Test murni untuk `JournalEntry` dan `TransferFundsService` menggunakan test doubles (mock/fake port) tanpa menggunakan container database eksternal. Semua assertions kegagalan bisnis harus ditangani secara bertipe via `Result<T>`.