# BAB 09: Quiz, Challenge, & Knowledge Check
**Modern Backend & Clean Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **The Dependency Rule & Modularity Encasement**  
   Dalam paradigma *Clean Architecture*, *Dependency Rule* menegaskan bahwa dependensi kode sumber hanya boleh mengarah ke dalam (menuju *enterprise business rules* / *entities*). Bagaimana Anda mengimplementasikan aturan ini secara ketat pada proyek Kotlin multi-modul di Gradle? Jelaskan bagaimana *visibility modifiers* Kotlin (`internal`, `public`, `private`) dan konfigurasi dependensi Gradle (`api` vs `implementation`) digunakan bersamaan untuk mencegah kebocoran implementasi detail (*frameworks/drivers*) ke layer *domain*.

2. **Domain Invariants & Kotlin Value Classes**  
   Domain-Driven Design (DDD) menuntut agar *Value Objects* tidak pernah berada dalam status tidak valid (*always-valid state*). Analisis efisiensi memori dan kekuatan penegakan tipe data (*type safety*) dari Kotlin `value class` (inline classes) dengan blok `init` validasi dibandingkan pembuatan wrapper class biasa (`data class`) pada layer Domain. Apa batasan runtime dari `value class` saat berinteraksi dengan framework serialisasi (misalnya Jackson atau kotlinx.serialization) atau ORM?

3. **Concurrency Execution Model: Thread-per-Request vs Cooperative Multitasking**  
   Bandingkan model eksekusi *Thread-per-request* tradisional (seperti pada Spring MVC klasik dengan Tomcat) dengan arsitektur asinkronus non-blocking berbasis Kotlin Coroutines (seperti pada Ktor atau Spring WebFlux). Jelaskan implikasi arsitekturalnya terhadap pemanfaatan CPU registers, heap allocations, memory footprint per-koneksi, dan fenomena *context switching* di level OS kernel versus runtime JVM.

4. **Inversion of Control (IoC): Reflection vs Compile-Time DI**  
   Bandingkan pendekatan Dependency Injection berbasis refleksi runtime (Spring IoC) dengan pendekatan compile-time / code-generation / service-locator pragmatis (Koin, Dagger 2, atau Kotlin-Inject) di backend Kotlin. Dari perspektif Clean Architecture, performa startup time (Cold Start pada Container/Serverless), dan konsumsi memori JVM, apa trade-off arsitektural yang harus diperhitungkan sebelum menentukan tools DI tersebut?

5. **Ports and Adapters (Hexagonal Architecture) Boundary Enforcement**  
   Dalam arsitektur *Ports and Adapters*, bedakan secara teknis antara *Driving (Primary) Port* dan *Driven (Secondary) Port*. Tuliskan analogi konkret pemetaannya dalam bahasa Kotlin: di mana antarmuka (*interface*) didefinisikan, layer mana yang memiliki interface tersebut, dan layer mana yang mengimplementasikannya jika sistem Anda berinteraksi dengan Apache Kafka dan PostgreSQL?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Dispatchers.IO Starvation & Coroutine Boundary Leakage**  
   Sebuah sistem Ktor memproses request HTTP menggunakan Coroutine. Di dalam sebuah *Use Case*, seorang engineer memanggil library pihak ketiga yang memblokir thread (blocking synchronous SDK). Jika panggilan ini dijalankan langsung di bawah context pemanggil tanpa *context shifting*, jelaskan skenario terburuk degradasi sistem yang dapat terjadi pada worker pool Ktor. Bagaimana cara memitigasi blocking call tersebut menggunakan `withContext(Dispatchers.IO)` atau custom dispatcher dengan `limitedParallelism`, dan mengapa kita tidak boleh mengekspos `Dispatchers` secara hardcoded di dalam layer Domain?

2. **JPA Entity vs Kotlin Idiomatic Class Pitfalls**  
   Mengapa penggunaan Kotlin `data class` untuk JPA/Hibernate `@Entity` dianggap sebagai anti-pattern teknis? Analisis secara mendalam isu-isu yang timbul terkait:
   - Mekanisme pembuatan `equals()` dan `hashCode()` bawaan `data class` saat entitas belum memiliki ID persistensi (transient state).
   - Masalah pemanggilan `toString()` terhadap relasi bi-directional *lazy-loaded* (circular dependency & `LazyInitializationException`).
   - Kebutuhan Hibernate terhadap *no-arg constructor* dan non-final class (`all-open` dan `no-arg` compiler plugins).

3. **Functional Error Handling vs Exceptional Flow**  
   Clean Architecture menentang penggunaan `throw Exception` untuk mengendalikan alur logika bisnis normal (misalnya `UserNotFoundException` atau `InsufficientBalanceException`) karena merusak referential transparency dan mahal secara komputasi (*stack trace generation*). Jelaskan bagaimana pola Functional Error Handling menggunakan tipe data aljabar seperti `Arrow-kt` (`Either<DomainError, Success>`) atau Kotlin `Result` diimplementasikan secara elegan di layer Application/Use Case hingga ditransformasikan menjadi HTTP status code di layer Adapter.

4. **Context Propagation Loss: ThreadLocal vs CoroutineContext**  
   Banyak enterprise logging framework (Logback/SLF4J) mengandalkan `MDC` (Mapped Diagnostic Context) yang berbasis `ThreadLocal` untuk distributed tracing (Trace ID/Span ID). Ketika eksekusi beralih antar-thread melalui coroutine *suspension point*, data `MDC` kerap hilang secara acak. Jelaskan mekanisme runtime JVM di balik kegagalan ini dan bagaimana mengatasinya menggunakan `MDCContext` dari modul `kotlinx-coroutines-slf4j` atau kustom `ThreadContextElement`.

5. **Exposed ORM vs Functional Database Transactions**  
   Saat menggunakan JetBrains Exposed (Kotlin SQL library) dalam gaya Clean Architecture:
   ```kotlin
   // Di dalam UseCase layer:
   transaction {
       userRepository.updateBalance(userId, amount)
       auditLogRepository.logAction("UPDATE_BALANCE", userId)
       externalPaymentClient.charge(amount) // HTTP Call
   }
   ```
   Identifikasi dua pelanggaran arsitektur dan kegagalan konkurensi fatal dalam kode di atas. Bagaimana Anda merefaktor struktur tersebut agar pemanggilan remote I/O terisolasi dari database transaction boundary dan *connection pool exhaustion* dapat dicegah?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Pool Collapse Akibat Unbounded Concurrency Spike
Sistem pembayaran backend Anda berbasis Ktor 2.x berjalan di atas JVM (JDK 21) dengan konfigurasi container 2 vCPU dan 2 GB RAM. Sistem menangani lonjakan dari 500 RPS menjadi 12.000 RPS dalam 30 detik saat kampanye flash sale.  
**Gejala:** Latensi p99 meroket dari 45ms ke 18.000ms. CPU usage melonjak hingga 100%, dan pod Kubernetes mulai terbunuh akibat *Liveness Probe Failure*, bukan *OOMKilled*. Heap memory masih tersisa 40%. Profiling menunjukkan ribuan coroutine berada dalam status `Active` dan tertahan di fungsi HTTP client (Ktor CIO client) yang memanggil upstream banking vendor.

- **Pertanyaan Diagnostik:**
  1. Analisis akar penyebab sistem mengalami *cooperative multitasking saturation*. Mengapa CPU mencapai 100% jika sebagian besar coroutine sedang menunggu I/O dari upstream?
  2. Bagaimana Anda merancang arsitektur proteksi beban (*load-shedding*, *concurrency limiter/bulkhead* via `Semaphore`, dan timeout cascade) di layer *Infrastructure Adapter* untuk menstabilkan aplikasi tanpa menambah alokasi resource pod?

---

### Skenario B: Race Condition & Double-Spend pada High-Concurrency Aggregate
Sistem Dompet Digital (*Digital Wallet*) mencatat saldo pengguna. Dua transaksi debit simultan sebesar Rp 700.000 masuk pada milidetik yang sama untuk akun dengan saldo Rp 1.000.000.  
**Gejala:** Kedua transaksi berhasil disetujui, menyebabkan saldo akhir menjadi minus Rp 400.000, melanggar *Domain Invariant* utama bahwa saldo tidak boleh di bawah nol. Audit log menunjukkan kedua transaksi membaca saldo awal Rp 1.000.000 secara bersamaan sebelum salah satu menuliskan mutasi.

- **Pertanyaan Diagnostik:**
  1. Identifikasi pada layer mana (*Domain*, *Use Case*, atau *Persistence Adapter*) kegagalan integritas ini terjadi, dan mengapa validasi `if (wallet.balance >= amount)` di dalam Domain Entity gagal melindungi invarian tersebut pada lingkungan terdistribusi/multi-threaded.
  2. Bandingkan dan implementasikan solusi berbasis kode Kotlin:
     - Pendekatan **Optimistic Locking** (menggunakan version column dan auto-retry policy dengan coroutines).
     - Pendekatan **Pessimistic Locking** (`SELECT FOR UPDATE` via Exposed/JPA).
     Apa konsekuensi performa (throughput vs latency) dari masing-masing pendekatan pada akun *hotspot* (misalnya akun *merchant* penerima ribuan transaksi per menit)?

---

### Skenario C: Boundary Degradation & N+1 Query Cascade pada Modular Monolith
Tim Anda memigrasikan monolitik legacy Spring Boot ke arsitektur *Clean Modular Monolith*. Terdapat dua modul: `OrderModule` dan `InventoryModule`.  
**Gejala:** Fitur checkout mengalami degradasi performa drastis. Ditemukan bahwa untuk menampilkan detail pesanan beserta status inventaris barang, `OrderAdapter` memanggil method internal `InventoryService.checkStock()` di dalam loop Kotlin `orders.map { ... }`. Lebih buruk lagi, class `Order` di domain layer secara langsung mengimpor class `InventoryItem` dari modul inventaris karena dependensi internal belum dikunci dengan benar.

- **Pertanyaan Diagnostik:**
  1. Bagaimana pelanggaran batas *Bounded Context* ini merusak arsitektur sistem dan menyebabkan kueri database N+1 melintasi batas domain?
  2. Rancang refaktorisasi arsitektur Clean Architecture murni: Tentukan kontrak (Ports), isolasi DTO/Value Object yang harus dibuat di masing-masing modul, serta bagaimana Anda mengoptimasi eksekusi pengambilan data batch tanpa melanggar prinsip *independent deployability/modularity*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Idempotent Payment Processor Engine
**Problem Statement:**  
Dalam sistem transaksi modern, jaringan tidak dapat diandalkan (*networks are inherently unreliable*). Klien sering mengirimkan request berulang (retry) akibat timeout jaringan, memicu risiko eksekusi ganda (*double charge*). Anda diminta merancang core engine dari modul pembayaran (*Payment Processing Module*) yang menjamin **Exactly-Once Business Semantics** menggunakan Clean Architecture murni dengan Kotlin.

**Requirements:**
1. **Purity of Layers (Clean Architecture):**
   - **Domain Layer:** Berisi aggregate `Payment`, value objects (`Money`, `PaymentId`, `IdempotencyKey`), domain events (`PaymentSettled`, `PaymentFailed`), dan custom business rules (invarian). Modul ini harus murni Kotlin (`kotlin-stdlib` saja, **zero external framework dependencies**).
   - **Application (Use Case) Layer:** Mengatur orchestration: validasi keunikan idempotensi, mutasi aggregate, eksekusi pembayaran via *Payment Gateway Port*, dan persistensi hasil secara atomik via *Persistence Port*.
   - **Infrastructure Layer:** Implementasi konkret dari adapter: In-memory/RDBMS repository menggunakan transaction boundary, fake external payment gateway client dengan simulasi latency acak (200-500ms).
2. **Concurrency & Thread Safety:**
   - Gunakan Kotlin Coroutines & Structured Concurrency.
   - Implementasikan *Concurrent Idempotency Handling*: Jika 2 request dengan `IdempotencyKey` yang sama masuk pada saat yang sama (paralel), request pertama harus memproses transaksi, dan request kedua harus menunggu proses pertama selesai (atau gagal) lalu mengembalikan status yang sama persis tanpa menduplikasi pemanggilan gateway.
3. **Robust Error Handling:**
   - Wajib menggunakan functional pattern (tipe data `Result<T>` atau `Either<PaymentError, T>`).
   - Jangan pernah melempar *unhandled exception* ke pemanggil di luar layer adapter.

**Constraints:**
- Bahasa: Kotlin 1.9+ / 2.x.
- Threading: Wajib menggunakan Coroutines (`Mutex` / non-blocking primitives diperbolehkan).
- Larangan: Dilarang menggunakan Hibernate/Spring Annotation di domain layer (`@Component`, `@Entity`, dll).

**Expected Output:**
- Kode Kotlin terstruktur yang mendemonstrasikan pemisahan layer secara eksplisit (dapat berupa satu file yang dipartisi namespace/interface dengan jelas atau representasi modul terpisah).
- Unit test / Verification script menggunakan coroutines (`runTest`) yang mendemonstrasikan:
  - 10 coroutine paralel mencoba mengeksekusi request dengan `IdempotencyKey` yang sama secara bersamaan.
  - Gateway eksternal hanya dipanggil tepat 1 kali.
  - Seluruh 10 coroutine menerima status pembayaran sukses yang identik.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Aturan mutlak *Dependency Rule* dan bagaimana arsitektur berevolusi dari N-Tier klasik menuju Ports & Adapters (Hexagonal) / Clean Architecture.
- [ ] Dampak runtime dari `value class` terhadap eliminasi *heap allocation* dan bagaimana compiler melakukan *name-mangling* untuk menjamin tipe data aman.
- [ ] Perbedaan fundamental antara *cooperative multitasking* Coroutines pada single thread/small pool vs *preemptive multitasking* OS Thread pools.
- [ ] Mengapa Domain Layer harus sepenuhnya bebas dari anotasi library/framework eksternal (Jackson, JPA, Spring Framework).
- [ ] Mekanisme functional error handling menggunakan Algebraic Data Types (ADT) / Sealing (`sealed class` / `sealed interface`) dibandingkan throwing unchecked runtime exceptions.
- [ ] Keterbatasan Kotlin Coroutines saat berhadapan dengan *ThreadLocal variables* dan cara melakukan bridge konteks (MDC context propagation).
- [ ] Konsep Transaction Boundary: mengapa distributed call / remote HTTP request tidak boleh berada di dalam blok transaksi database database.

### Saya tidak perlu menghafal:
- [ ] Seluruh method bawaan framework Ktor Routing DSL atau anotasi Spring Boot Controller.
- [ ] Syntax konfigurasi SQL Dialect spesifik untuk setiap database engine pada Exposed atau jOOQ.
- [ ] Internal bytecode mapping dari Kotlin coroutine compiler state machine (`Continuation` switch-tables).

### Saya harus bisa melakukan:
- [ ] Memisahkan modularitas proyek Kotlin menggunakan Gradle Multi-project builds (`:core:domain`, `:core:usecase`, `:infra:persistence`, `:infra:web`).
- [ ] Mengimplementasikan *Domain Invariants* yang ketat menggunakan Kotlin `sealed interface`, `require()` blocks, dan `value class`.
- [ ] Membungkus legacy blocking code (I/O) ke dalam Coroutine safe environment menggunakan `withContext` dan custom `limitedParallelism` dispatcher.
- [ ] Mendiagnosis dan memperbaiki *race condition* pada pembaruan data inventaris/saldo menggunakan Optimistic Locking dengan retries atau Pessimistic Locking.
- [ ] Menulis unit test murni untuk layer Domain dan Application tanpa perlu me-load Context Framework / Spring Context / Embedded Database, dengan memanfaatkan mock/fake ports sederhana berbasis interface Kotlin.