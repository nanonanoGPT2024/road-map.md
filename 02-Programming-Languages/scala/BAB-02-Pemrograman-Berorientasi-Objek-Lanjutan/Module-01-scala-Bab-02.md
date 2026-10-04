# SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** 02-Programming-Languages
* **Bahasa Pemrograman:** Scala (Fokus: Scala 3.x, kompatibel konseptual dengan Scala 2.13)
* **Bab 02:** Object-Oriented Programming Paradigms
* **Modul 01:** Pemrograman Berorientasi Objek Lanjutan (Advanced Object-Oriented Programming)
* **Tingkat Kesulitan:** Advanced / Lanjutan
* **Prasyarat Pengetahuan:** 
  * Sintaks dasar Scala (deklarasi `val`, `var`, `def`, `class`, `object`).
  * Dasar OOP (Inheritance, Polymorphism, Encapsulation).
  * Pemahaman dasar kompilasi JVM (*bytecode*, *classloader*, *virtual method table / vtable*).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. **Menganalisis Mekanisme Linearization:** Menghitung urutan resolusi *method dispatch* secara deterministik pada pewarisan berganda (*multiple mixin composition*) menggunakan algoritma linearisasi Scala.
2. **Menguasai Pola Ekstensi Terkontrol:** Menerapkan kata kunci `open`, `sealed`, dan `abstract` pada hierarki kelas untuk mencegah kebocoran abstraksi (*leaky abstractions*) dan menjaga invariant arsitektural.
3. **Mengimplementasikan Stackable Modifications Pattern:** Merancang komponen perangkat lunak modular dengan mendekorasi perilaku *trait* secara dinamis tanpa melanggar prinsip *Single Responsibility*.
4. **Mengevaluasi Dependency Injection Melalui Self-Type Annotations:** Mengidentifikasi perbedaan mendasar antara *subtyping* konvensional dengan *self-type annotations* (`this: Dep =>`), serta menganalisis dampaknya terhadap *loose coupling*.
5. **Membedah Representasi Bytecode JVM:** Menginspeksi bagaimana Scala mengompilasi *traits*, *default methods*, dan *field initializers* ke dalam instruksi JVM seperti `invokeinterface` dan `invokevirtual`.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Dari Hirarki Kaku Menuju Komposisi Ortogonal

Pada paradigma OOP tradisional berbasis Java atau C++, inheritance sering kali dipandang sebagai relasi taksonomi biologis: *Cat IS-A Mammal IS-A Animal*. Pendekatan ini rentan terhadap masalah kerapuhan kelas dasar (*Fragile Base Class Problem*) dan ambiguitas pewarisan ganda (*The Diamond Problem*).

```
   TRADISIONAL (IS-A)                SCALA MIXIN (CAN-DO / HAS-BEHAVIOR)
   
     +-----------+                        +---------------+
     |  Animal   |                        |  Core Entity  |
     +-----+-----+                        +-------+-------+
           |                                      |  with Stackable Trait A
     +-----+-----+                                |  with Stackable Trait B
     |  Mammal   |                                v
     +-----+-----+                    +-----------------------+
           |                          | Composed Deterministic|
     +-----+-----+                    |      Linear State     |
     |    Cat    |                    +-----------------------+
     +-----------+
  (Rigid & Coupled)                     (Orthogonal & Composable)
```

Dalam Scala Lanjutan, mental model yang harus diadopsi adalah:
* **Kelas adalah Agen Eksekusi, Trait adalah Modifikasi Ortopedi:** Trait bukan sekadar antarmuka (*interface*); trait adalah unit modular pembawa perilaku dan *state* yang dapat ditumpuk (*stackable*).
* **Linearisasi vs Pohon Pewarisan:** Scala tidak menyelesaikan konflik metode pewarisan ganda melalui pemilihan acak atau penolakan kompilasi, melainkan dengan meratakan struktur pohon pewarisan menjadi satu garis lurus (*linear hierarchy*) yang terurut dari kanan ke kiri (*right-to-left, bottom-to-top*).
* **Kontrak Struktural via Self-Type:** Self-type annotation tidak menyatakan "Saya turunan dari X", melainkan "Saya menolak untuk diinstansiasi kecuali lingkungan runtime menjamin kehadiran X". Ini memisahkan *interface inheritance* dari *composition requirement*.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### Resolusi Linearitas Algoritmik (Diamond Problem Resolution)

Berikut adalah visualisasi resolusi *Diamond Inheritance* pada Scala:

```
        +---------+
        |  Base   |
        +----+----+
             |
      +------+------+
      |             |
+-----+-----+ +-----+-----+
|  LoggerA  | |  LoggerB  |
+-----+-----+ +-----+-----+
      |             |
      +------+------+
             |
      +------+------+
      | AppService  |
      +-------------+
```

### Diagram Linearization Process

Urutan evaluasi linearisasi dihitung dengan algoritma:
$$\mathcal{L}(C) = C \mathbin{::} \mathcal{L}(T_n) \mathrel{\vec{+}} \dots \mathrel{\vec{+}} \mathcal{L}(T_1) \mathrel{\vec{+}} \mathcal{L}(S)$$
di mana $\vec{+}$ adalah operator *right-leaning merge* (elemen di sebelah kanan mempertahankan prioritas relatifnya, elemen duplikat di kiri dibuang).

```
[Definisi: class AppService extends Base with LoggerA with LoggerB]

Step 1: L(Base)       = [Base, AnyRef, Any]
Step 2: L(LoggerA)    = [LoggerA] -> L(Base) 
                      = [LoggerA, Base, AnyRef, Any]
Step 3: L(LoggerB)    = [LoggerB] -> L(Base) 
                      = [LoggerB, Base, AnyRef, Any]

Merge Algorithm:
L(AppService) = [AppService] + [LoggerB, Base, AnyRef, Any]
                             + [LoggerA, Base, AnyRef, Any]
                             + [Base, AnyRef, Any]

Proses Penghapusan Duplikat (Kiri Dibuang jika ada di Kanan):
AppService -> LoggerB -> LoggerA -> Base -> AnyRef -> Any

Eksekusi 'super' Berjalan Dari Kiri ke Kanan:
[AppService] ===(super)===> [LoggerB] ===(super)===> [LoggerA] ===(super)===> [Base]
```

### Siklus Eksekusi Runtime Stackable Traits

```
+-------------------------------------------------------------------------+
| Client Invocation: service.process(data)                                |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [AppService] Memulai proses interceptor                                 |
| -> super.process(data) dipanggil                                        |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [LoggerB] Menerima delegasi via Linearization Resolving                 |
| -> Mengeksekusi pre-processing B                                        |
| -> super.process(data) dipanggil                                        |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [LoggerA] Menerima delegasi via Linearization Resolving                 |
| -> Mengeksekusi pre-processing A                                        |
| -> super.process(data) dipanggil                                        |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [Base] Root Execution Engine                                            |
| -> Mengembalikan payload hasil komputasi                                |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [LoggerA] Menjalankan post-processing A (Return intercept)              |
+-------------------------------------------------------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------+
| [LoggerB] Menjalankan post-processing B (Return intercept)              |
+-------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi Trait pada JVM

Mulai dari Java 8+, JVM mendukung *default methods* pada *interface*. Scala memanfaatkan fitur ini secara intensif:
* **Scala 2.12+ / Scala 3:** Trait tanpa state (*fieldless trait*) dikompilasi secara langsung menjadi native Java `interface` dengan *default method*.
* **Stateful Traits:** Trait yang memiliki field `val` atau `var` tetap dimodelkan sebagai *interface* di JVM, namun inisialisasi state dialokasikan pada kelas konkret yang mengimplementasikan trait tersebut. Kelas pengadopsi membuat field privat aktual dan mengaksesnya melalui *getter/setter method* yang disintesis oleh `scalac`.

### 2. Inisialisasi State & Constructor Order

Urutan eksekusi konstruktor ketika sebuah kelas mewarisi hierarki kompleks:
1. Konstruktor superclass paling atas (`AnyRef` / `Object`) dipanggil terlebih dahulu.
2. Trait dievaluasi dari kiri ke kanan.
3. Di dalam setiap trait, konstruktor induk dievaluasi sebelum trait itu sendiri.
4. Jika suatu trait sudah diinisialisasi, trait tersebut **tidak akan** diinisialisasi ulang (idempoten).
5. Konstruktor kelas konkret dieksekusi paling akhir.

### 3. Vtable vs Interface Dispatch

Ketika memanggil metode melalui hierarki kelas vs trait:
* **Invokevirtual:** Digunakan untuk pemanggilan metode konkret pada hirarki kelas reguler melalui tabel *vtable*. Kompleksitas konstan $O(1)$ dereferensi pointer.
* **Invokeinterface:** Digunakan untuk memanggil metode trait. JVM menggunakan *Inline Caching* (Monomorphic, Bimorphic, Megamorphic Call Sites) untuk mengoptimasi performa tabel antarmuka (*itable*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Linearization Formal

Algoritma linierisasi $\mathcal{L}(C)$ untuk kelas $C$ dengan deklarasi `class C extends $C_1$ with $C_2$ ... with $C_n$` didefinisikan secara rekursif:

$$\mathcal{L}(C) = [C] + (\mathcal{L}(C_n) \vec{+} \mathcal{L}(C_{n-1}) \vec{+} \dots \vec{+} \mathcal{L}(C_1))$$

Operasi penggabungan $\vec{+}$ (*right-concatenation without duplicates*) menjamin bahwa:
1. Subtipe selalu muncul sebelum supertipenya.
2. Urutan deklarasi pada klausul `with` menentukan prioritas: trait yang dinyatakan paling kanan dieksekusi terlebih dahulu saat pemanggilan `super`.

### Self-Type vs Subtyping

Terdapat perbedaan arsitektural mendasar antara:
* **Subtyping (`trait A extends B`):** Hubungan erat (is-a). `A` mewarisi seluruh anggota `B`, dan antarmuka publik `B` menjadi bagian eksplisit dari kontrak publik `A`.
* **Self-Type (`trait A { this: B => }`):** Hubungan dependensi modular (*requires*). `A` tidak mengekspos metode `B` kepada pengguna luar secara otomatis tanpa komparasi tipe, namun implementasi internal `A` bebas mengasumsikan kehadiran `B`.

### Pembatasan Ekstensi: `open`, `sealed`, dan `final` di Scala 3

Untuk mencegah masalah arsitektural akibat subtyping liar:
* `final class`: Melarang sepenuhnya segala bentuk subtyping.
* `sealed class/trait`: Hanya mengizinkan subtyping di dalam berkas (*source file*) yang sama. Membantu compiler melakukan *exhaustiveness check* saat pattern matching.
* `open class`: Penanda eksplisit bahwa kelas ini secara sengaja dirancang untuk diekstensi di luar berkas modul. Jika sebuah kelas tidak ditandai `open`, compiler Scala 3 akan memunculkan *warning* (atau *error* di bawah konfigurasi *strict*) bila kelas tersebut di-extend di berkas lain.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode yang mendemonstrasikan Trait Linearization, Stackable Modification, dan Self-Type:

```scala
// File: FundamentalOOP.scala
package com.architect.advanced.oop

// 1. Base abstraction
abstract class DataWriter:
  def write(payload: String): String

// 2. Concrete core engine
class DiskWriter extends DataWriter:
  override def write(payload: String): String =
    s"[DISK_WRITE] Commit: '$payload'"

// 3. Stackable trait A: Trimming
trait SanitizingWriter extends DataWriter:
  abstract override def write(payload: String): String =
    val sanitized = payload.trim
    super.write(sanitized)

// 4. Stackable trait B: Hashing
trait HashingWriter extends DataWriter:
  abstract override def write(payload: String): String =
    val hashed = s"SHA256(${payload.hashCode.toHexString})::$payload"
    super.write(hashed)

// 5. Context dependency via Self-Type
trait AuditContext:
  def getCurrentOperator: String

trait AuditingWriter extends DataWriter:
  this: AuditContext => // Self-type requirement

  abstract override def write(payload: String): String =
    val operator = this.getCurrentOperator
    val loggedPayload = s"[OPERATOR:$operator] -> $payload"
    super.write(loggedPayload)

// 6. Test Driver
@main def runFundamentalDemo(): Unit =
  // Komposisi 1: SanitizingWriter dulu, kemudian HashingWriter
  val pipelineA = new DiskWriter with HashingWriter with SanitizingWriter
  val resultA = pipelineA.write("   Payload Data A   ")
  println(s"Result A: $resultA")

  // Komposisi 2: HashingWriter dulu, kemudian SanitizingWriter
  val pipelineB = new DiskWriter with SanitizingWriter with HashingWriter
  val resultB = pipelineB.write("   Payload Data B   ")
  println(s"Result B: $resultB")

  // Komposisi 3: Menggunakan Self-type
  val pipelineC = new DiskWriter 
    with SanitizingWriter 
    with AuditingWriter 
    with AuditContext:
      override def getCurrentOperator: String = "admin-sys-01"

  val resultC = pipelineC.write("   Critical Security Data   ")
  println(s"Result C: $resultC")
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membongkar aspek teknis dari kode SEKSI 07:

1. **`abstract override def write(payload: String): String`**
   * Penggunaan modifier kombinasi `abstract override` hanya legal di dalam *trait*. 
   * Ini memberi sinyal kepada compiler bahwa metode memanggil `super.write(...)`, padahal super-metode konkretnya belum terikat (*unbound*) pada tahap deklarasi trait ini. Ikatan konkret baru diselesaikan saat proses *mixin composition* di kelas akhir.

2. **`this: AuditContext =>`**
   * Sintaks *self-type annotation*.
   * Menginstruksikan Scala Type Checker bahwa trait `AuditingWriter` tidak boleh diinstansiasi (`new AuditingWriter`) tanpa adanya implementor dari `AuditContext`.
   * Di dalam body trait, referensi `this` diperluas tipenya menjadi `AuditingWriter & AuditContext`.

3. **Inversi Urutan Pipeline A vs Pipeline B:**
   * Di **Pipeline A** (`DiskWriter with HashingWriter with SanitizingWriter`):
     * Linearization: `SanitizingWriter -> HashingWriter -> DiskWriter -> DataWriter`
     * Alur Eksekusi: Data masuk ke `SanitizingWriter.write` (payload di-trim) $\to$ diteruskan ke `HashingWriter.write` (menghasilkan hash dari data bersih) $\to$ ditulis oleh `DiskWriter`.
   * Di **Pipeline B** (`DiskWriter with SanitizingWriter with HashingWriter`):
     * Linearization: `HashingWriter -> SanitizingWriter -> DiskWriter -> DataWriter`
     * Alur Eksekusi: Data masuk ke `HashingWriter.write` (menghasilkan hash dari string mentah yang masih ada spasinya) $\to$ diteruskan ke `SanitizingWriter.write` $\to$ ditulis oleh `DiskWriter`.

---

# SEKSI 09 — STUDI KASUS NYATA (Real-World Production Scenario)

### Arsitektur Sistem: Distributed High-Throughput Financial Ledger

Sebuah platform pembayaran memproses transaksi multi-mata uang (*ledger transaction processing*). Setiap transaksi harus melewati rantai pemrosesan:
1. **Verifikasi Saldo & Anti-Fraud** (Pre-check).
2. **Rate Limiting Engine** (Proteksi DOS).
3. **Audit Trail Immutability** (Pencatatan kriptografis).
4. **Idempotency Guard** (Mencegah double-spending).

Masalah jika menggunakan pewarisan tunggal:
* *Class explosion*: `AuditedRateLimitedLedgerEngine`, `IdempotentAuditedLedgerEngine`, dll.

Solusi:
Menggunakan **Dynamic Stackable Trait Pattern** yang dipadukan dengan **Self-Type Dependencies** untuk konfigurasi dinamis berbasis tenant/lingkungan tanpa *runtime overhead* dari refleksi framework DI eksternal.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```scala
// File: LedgerEngineProduction.scala
package com.fintech.ledger.advanced

import java.time.Instant
import java.util.UUID
import scala.collection.concurrent.TrieMap

// ==========================================
// 1. MODEL DOMAIN & KONTRAK DASAR
// ==========================================

case class Transaction(
  id: UUID,
  accountId: String,
  amount: BigDecimal,
  currency: String,
  timestamp: Instant
)

enum EngineStatus:
  case Success(txId: UUID, ledgerOffset: Long)
  case Rejected(reason: String)

abstract class BaseLedgerEngine:
  def process(tx: Transaction): EngineStatus

// ==========================================
// 2. CONTEXT DEPENDENCIES (VIA SELF-TYPES)
// ==========================================

trait MetricsService:
  def incrementCounter(metricName: String): Unit
  def recordLatency(operation: String, durationNanos: Long): Unit

trait ClockService:
  def now(): Instant

// ==========================================
// 3. CORE CONCRETE IMPLEMENTATION
// ==========================================

open class CoreLedgerEngine(private var sequenceTracker: Long = 0L) extends BaseLedgerEngine:
  private val stateStorage = TrieMap[UUID, Transaction]()

  override def process(tx: Transaction): EngineStatus =
    // Mutasi state terkontrol
    synchronized {
      sequenceTracker += 1
      stateStorage.put(tx.id, tx)
      EngineStatus.Success(tx.id, sequenceTracker)
    }

// ==========================================
// 4. STACKABLE INTERCEPTORS (TRAITS)
// ==========================================

// Trait 1: Idempotency Protection
trait IdempotencyGuard extends BaseLedgerEngine:
  private val processedTransactions = TrieMap[UUID, EngineStatus]()

  abstract override def process(tx: Transaction): EngineStatus =
    processedTransactions.get(tx.id) match
      case Some(cachedResult) =>
        cachedResult
      case None =>
        val result = super.process(tx)
        processedTransactions.put(tx.id, result)
        result

// Trait 2: Telemetry & Metrics (Membutuhkan MetricsService & ClockService)
trait TelemetryInterceptor extends BaseLedgerEngine:
  this: MetricsService & ClockService =>

  abstract override def process(tx: Transaction): EngineStatus =
    val start = System.nanoTime()
    try
      val status = super.process(tx)
      status match
        case EngineStatus.Success(_, _) => 
          incrementCounter("ledger.transactions.success")
        case EngineStatus.Rejected(_) => 
          incrementCounter("ledger.transactions.rejected")
      status
    finally
      val duration = System.nanoTime() - start
      recordLatency("ledger.process.duration", duration)

// Trait 3: Financial Invariant Validator
trait InvariantValidator extends BaseLedgerEngine:
  abstract override def process(tx: Transaction): EngineStatus =
    if tx.amount <= BigDecimal(0) then
      EngineStatus.Rejected(s"Validation Violation: Amount ${tx.amount} must be positive.")
    else if tx.currency.length != 3 then
      EngineStatus.Rejected(s"Validation Violation: Currency ${tx.currency} is invalid ISO code.")
    else
      super.process(tx)

// ==========================================
// 5. PRODUCTION ASSEMBLY (COMPOSITION ROOT)
// ==========================================

class ProductionLedgerEngine extends CoreLedgerEngine
  with InvariantValidator
  with IdempotencyGuard
  with TelemetryInterceptor
  with MetricsService
  with ClockService:

  // Implementasi Context Dependencies
  override def incrementCounter(metricName: String): Unit =
    println(s"[METRICS-METRIC-INC] Name: $metricName")

  override def recordLatency(operation: String, durationNanos: Long): Unit =
    println(s"[METRICS-LATENCY] Op: $operation, Time: ${durationNanos / 1_000_000.0} ms")

  override def now(): Instant = Instant.now()

// ==========================================
// 6. TESTING EXECUTION ENGINE
// ==========================================

@main def runLedgerPipeline(): Unit =
  val engine = new ProductionLedgerEngine()

  val validTx = Transaction(
    id = UUID.randomUUID(),
    accountId = "acc-9901-usd",
    amount = BigDecimal("1500.50"),
    currency = "USD",
    timestamp = Instant.now()
  )

  val invalidTx = Transaction(
    id = UUID.randomUUID(),
    accountId = "acc-9902-eur",
    amount = BigDecimal("-20.00"),
    currency = "EUR",
    timestamp = Instant.now()
  )

  println("=== TEST 1: Transaksi Normal ===")
  val result1 = engine.process(validTx)
  println(s"Hasil 1: $result1\n")

  println("=== TEST 2: Transaksi Idempotent (Mengulang TX 1) ===")
  val result2 = engine.process(validTx)
  println(s"Hasil 2: $result2 (Harus identik dan tidak menambah sequence)\n")

  println("=== TEST 3: Transaksi Pelanggaran Invariant ===")
  val result3 = engine.process(invalidTx)
  println(s"Hasil 3: $result3\n")
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Karakteristik | Subtyping Biasa (`extends C`) | Stackable Traits Mixin | Self-Type Annotation (`this: T =>`) | Tagless Final / Pure FP |
| :--- | :--- | :--- | :--- | :--- |
| **Kopling Tipe** | Sangat Erat (*High Coupling*) | Menengah (*Modular Behavior*) | Rendah (*Contract-only Dependency*) | Sangat Rendah (*Decoupled via Monad*) |
| **Konflik Nama** | Error kompilasi / Penimpaan kaku | Selesai via Linearization Deterministic | Diselesaikan pada saat Mixin | Selesai via Typeclass Resolution |
| **Overhead Runtime**| Minimal (vtable dereference) | Sangat Rendah (*itable dispatch inline-cached*) | Nol (*pure compile-time check*) | Ringan (*Higher-Kinded Types boxing/unboxing*) |
| **Fleksibilitas Desain**| Kaku (*Monolithic Tree*) | Sangat Tinggi (*Composability*) | Tinggi (*Decoupled Composition*) | Paling Fleksibel (*Abstract Interpretation*) |
| **Debugging Complexity**| Mudah dipahami | Butuh menelusuri linearitas stack | Mudah di-trace secara statis | Rumit (Stack trace terbungkus Monad)|

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Inisialisasi Field pada Trait (The Order-of-Initialization Null Trap)

```scala
trait BaseConfig:
  val rawUrl: String
  val parsedHost: String = rawUrl.stripPrefix("https://") // HATI-HATI!

class ProductionConfig extends BaseConfig:
  val rawUrl: String = "https://internal.api.domain"

// Eksekusi:
// new ProductionConfig().parsedHost menghasilkan NullPointerException!
```
*Penyebab:* Konstruktor `BaseConfig` dievaluasi **sebelum** konstruktor `ProductionConfig` menginisialisasi `rawUrl`. Pada saat `parsedHost` dievaluasi, `rawUrl` masih bernilai `null`.

*Solusi Scala 3:* Gunakan `trait parameter` atau `lazy val`:
```scala
trait BaseConfigSafe(val rawUrl: String):
  val parsedHost: String = rawUrl.stripPrefix("https://")
```

### 2. Diamond Linearization Unexpected Short-Circuit

Jika salah satu interceptor di tengah rantai linierisasi lupa atau sengaja tidak memanggil `super.method()`, pemanggilan metode untuk semua trait di sebelah kiri dari linierisasi akan terputus secara diam-diam (*short-circuit*). Selalu dokumentasikan secara eksplisit apakah suatu trait memiliki sifat memutus aliran atau wajib memanggil `super`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan Subtyping Biasa untuk Dependency Injection
```scala
// ANTI-PATTERN: Memaksa inheritance murni untuk dependensi
trait UserRepository
class UserService extends UserRepository // SALAH: Service BUKAN Repository
```
*Solusi:*
```scala
// BENAR: Gunakan Self-type
class UserService:
  this: UserRepository =>
```

### Kesalahan 2: Mengasumsikan `super` Mengarah Langsung ke Parent Class Statis
```scala
trait FastValidator extends Engine:
  override def execute(): Unit = 
    super.execute() // KESALAHAN PIKIR: Mengira ini selalu memanggil Engine.execute()
```
*Penjelasan:* Dalam Scala, `super` bersifat dinamis bergantung pada urutan *mixin*. `super` di `FastValidator` bisa saja memanggil trait lain yang digabungkan bersamanya saat instansiasi, bukan kelas `Engine` langsung.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Parameterized Traits (Scala 3):** Di Scala 3, *trait* dapat menerima parameter konstruktor secara langsung. Hindari abstraksi *field* kosong (`val x: String`) jika tujuannya hanya untuk inisialisasi konfigurasi.
2. **Definisikan `open` Secara Eksplisit:** Tandai kelas dengan `open class` hanya jika kelas tersebut memang sengaja dirancang untuk diturunkan di package lain. Jika tidak, pertahankan kelas sebagai `final` atau biarkan default tanpa modifikasi untuk enkapsulasi hierarki modul.
3. **Posisikan Mutasi State di Level Leaf Class:** Hindari menyimpan variabel mutable (`var`) di dalam trait yang dirancang untuk *stackable mixin*. Menggabungkan beberapa stateful traits yang melakukan mutasi secara independen membuka celah race condition.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Megamorphic Dispatch Elimination
JVM secara dinamis mengoptimalkan *call site* melalui HotSpot compiler:
* **Monomorphic Call:** Target metode hanya 1 tipe implementasi. JVM melakukan *inlining* penuh.
* **Megamorphic Call:** Terdapat $\ge 3$ tipe berbeda di pemanggilan titik yang sama. JVM harus melakukan pencarian tabel *itable* secara penuh pada setiap eksekusi, memakan siklus CPU.

*Strategi:* Jika Anda membutuhkan performa ultra-low-latency (seperti pemrosesan bursa finansial):
* Jadikan pipeline engine akhir berstatus `final class`. Ini memungkinkan JIT compiler melakukan devirtualisasi dan inline chaining dari semua panggilan `super`.

```scala
// JIT Compiler dapat meng-inline seluruh chain method menjadi satu blok instruksi native
final class HighThroughputEngine extends CoreLedgerEngine 
  with InvariantValidator 
  with IdempotencyGuard
```

---

# SEKSI 16 — KEAMANAN & HARDENING

### Mencegah Subversion of Authority melalui Class Hijacking

Di Java/Scala, jika sebuah class tidak diproteksi, penyerang internal dapat membuat subkelas yang memotong (*bypass*) mekanisme keamanan:

```scala
// RENTAN: Kelas otentikasi dapat di-override
open class AuthenticationModule:
  def verifyToken(token: String): Boolean = 
    // Kriptografi validasi rumit
    true

// Serangan: Memotong proses autentikasi
class MaliciousAuth extends AuthenticationModule:
  override def verifyToken(token: String): Boolean = true // BYPASS!
```

### Pengerasan Arsitektur (Hardened Pattern):
1. Buat metode inti berstatus `final`.
2. Gunakan `sealed` untuk membatasi turunan hanya pada domain yang diaudit.

```scala
sealed abstract class HardenedSecurityContext:
  // Metode ini disegel secara final, menjamin logika keamanan tidak dapat dimanipulasi
  final def enforcePolicy(user: String, claims: List[String]): Boolean =
    claims.contains("ADMIN") && auditInternal(user)

  protected def auditInternal(user: String): Boolean
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### Menelusuri Urutan Linearitas Menggunakan Scala Reflection API

Untuk mendiagnosis urutan eksekusi metode linierisasi yang rumit pada sistem runtime:

```scala
import scala.reflect.Selectable.reflectiveSelectable

object LinearizationDebugger:
  def printHierarchy(clazz: Class[?]): Unit =
    println(s"=== Inspecting Linearization Tree for: ${clazz.getName} ===")
    val interfaces = clazz.getInterfaces
    val superclass = clazz.getSuperclass

    println(s"Direct Superclass: ${if superclass != null then superclass.getName else "None"}")
    println("Implemented Interfaces (JVM Level):")
    interfaces.foreach(i => println(s"  -> ${i.getName}"))

// Penggunaan pada Unit Test atau Diagnosa Startup
// LinearizationDebugger.printHierarchy(classOf[ProductionLedgerEngine])
```

Format Log Terstruktur untuk Stackable Mixins:
```json
{
  "@timestamp": "2026-03-31T23:59:59.999Z",
  "logger": "com.fintech.ledger.advanced.TelemetryInterceptor",
  "level": "INFO",
  "message": "Stack trace invocation node completed",
  "context": {
    "engine_node": "TelemetryInterceptor",
    "next_in_linearization": "IdempotencyGuard",
    "tx_id": "8488e1a8-c2dd-4e56-8367-27b2e88a0860",
    "latency_ns": 450210
  }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Linearization Order:** Subkelas $\to$ Trait Terkanan $\to$ Trait Kiri $\to$ Base Class $\to$ AnyRef $\to$ Any.
* **`abstract override`:** Wajib digunakan jika trait memanggil `super` pada metode abstract untuk mengaktifkan *stackable modifications*.
* **Self-Type (`this: X =>`):** Menolak instansiasi trait tanpa penyertaan `X`. Menjaga dependensi internal tetap terisolasi tanpa mencemari API publik turunan langsung.
* **Trait Fields Trap:** Hindari mendeklarasikan `val` pada trait yang bergantung pada abstract `val` kelas anak; gunakan `lazy val` atau Scala 3 *trait parameters*.
* **`open` modifier:** Wajib dituliskan pada Scala 3 jika kelas dimaksudkan untuk diwarisi di luar source file asalnya.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)
1. Kapan modifier `abstract override` wajib digunakan dalam kode Scala?
2. Bagaimana representasi sebuah *trait* tanpa field di level bytecode JVM pada arsitektur Scala modern?
3. Apa kegunaan utama modifier `open` pada deklarasi kelas di Scala 3?
4. Apa yang membedakan relasi subtyping (`trait A extends B`) dengan relasi self-type (`trait A { this: B => }`)?
5. Diberikan deklarasi: `class Service extends Base with TraitA with TraitB`. Trait manakah yang metode `write()`-nya pertama kali menerima kontrol pemanggilan ketika `Service.write()` dieksekusi?

### Soal Tingkat Menengah (Intermediate)
6. Mengapa inisialisasi abstract `val` di dalam trait dapat memicu timbulnya `NullPointerException` pada saat konstruktor kelas anak dijalankan?
7. Hitung urutan linearisasi deterministik dari kelas `FinalNode` berikut:
   ```scala
   trait Root
   trait BranchA extends Root
   trait BranchB extends Root
   trait DecoratorA extends BranchA
   class BaseNode extends BranchB
   class FinalNode extends BaseNode with DecoratorA
   ```
8. Bagaimana pengaruh pemanggilan metode trait yang berstatus megamorphic terhadap performa throughput di level HotSpot execution engine?
9. Bagaimana cara kerja kata kunci `sealed` dalam membantu compiler Scala menghasilkan *exhaustiveness warning* pada ekspresi pattern matching?
10. Jika dalam sebuah Stackable Trait modifikasi berantai salah satu trait tidak mengeksekusi `super.method()`, apa dampak runtime yang terjadi pada eksekusi trait-trait sebelumnya dalam hierarki linierisasi?

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: High-Reliability Event Processing Pipeline

Bangunlah sebuah micro-framework pemrosesan event (*Event Sourcing Pipeline*) dengan ketentuan arsitektur berikut:

#### Persyaratan Fungsional:
1. **Model Inti:**
   * Buat case class `Event(id: Long, aggregateId: String, payload: String, version: Int)`.
   * Definisikan basis processor: `abstract class EventProcessor` yang memiliki fungsi `def handle(event: Event): Either[String, Event]`.
2. **Kebutuhan Stackable Traits:**
   * `PayloadDecryptionInterceptor`: Mendekripsi payload (misal: simulasi Base64 decode) sebelum diproses ke layer berikutnya.
   * `VersionCheckInterceptor`: Menolak event jika `event.version <= 0`.
   * `AuditJournalInterceptor`: Membutuhkan self-type `JournalStorageEngine` untuk mencatat metadata event secara permanen ke storage.
3. **Kebutuhan Desain Teknis:**
   * Gunakan Scala 3 idiom secara penuh.
   * Implementasikan dependency `JournalStorageEngine` menggunakan Self-Type Annotation (bukan pewarisan langsung).
   * Rakit pipeline engine konkret bertanda `final class ProductionEventPipeline` yang mengomposisikan semua interceptor di atas.
4. **Verifikasi Kasus Uji:**
   * Tulis test driver untuk membuktikan bahwa urutan interceptor berjalan secara deterministik:
     1. Pengecekan versi dilakukan paling awal.
     2. Dekripsi muatan dilakukan setelah versi tervalidasi.
     3. Logging journal dieksekusi secara simetris saat event masuk dan keluar.
     4. Komponen mengembalikan `Either.Left` secara elegan jika terjadi error di salah satu interceptor tanpa merusak seluruh thread pemrosesan.