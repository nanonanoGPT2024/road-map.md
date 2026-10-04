# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Pemrograman Berorientasi Objek Lanjutan — Scala Enterprise Engineering**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
- Menguasai algoritma **Trait Linearization** pada runtime Scala dan JVM untuk mengeliminasi *diamond problem* secara deterministik.
- Mengimplementasikan dependensi antarmuka tingkat lanjut menggunakan **Self-Type Annotations** versus **Subtyping Inheritance**, serta memahami mitigasi anti-pattern seperti *Cake Pattern* monolitik.
- Menganalisis dan menerapkan **Advanced Variance Annotations** (Covariance `+T`, Contravariance `-T`, dan Invariance `T`) yang dipadukan dengan *Lower & Upper Type Bounds* untuk membangun struktur domain model dan koleksi type-safe.
- Mengoptimalkan alokasi memori heap JVM melalui **Value Classes (`extends AnyVal`)** dan **Universal Traits** untuk menghindari overhead boxing pada domain berkecepatan tinggi.
- Membedakan use-case arsitektural antara **Abstract Type Members** dan **Parametric Polymorphism (Generics)** dalam domain-driven design skala besar.
- Mengonfigurasi dan memvalidasi arsitektur modular berorientasi objek yang siap dideploy pada kluster terdistribusi throughput tinggi.

---

## 2. Prerequisite
Untuk memahami materi ini secara komprehensif, engineer harus menguasai:
- Sintaksis dasar Scala (Scala 2.13/3) termasuk `case class`, `trait`, `object`, dan `pattern matching`.
- Arsitektur JVM: Model alokasi memori (Heap, Stack, Metaspace), garbage collection baseline, dan representasi *bytecode* class file.
- Konsep dasar OOP: Enkapsulasi, Polymorphism, Subtyping, dan Dynamic Method Dispatching.
- Pengetahuan kerja mengenai SBT (*Scala Build Tool*) dan manajemen dependensi enterprise.

---

## 3. Concept & Internal Architecture

### 3.1. Algoritma Trait Linearization (C3-Variant di Scala)
Scala menyelesaikan persoalan *multiple inheritance* dan ambiguitas pemanggilan `super` menggunakan aturan **Linearization Deterministic**. Urutan eksekusi method tidak ditentukan secara hierarki pohon biner biasa, melainkan melalui *topological sorting* terarah dari kanan ke kiri (*right-to-left, depth-first with duplicate elimination except the last occurrence*).

Secara formal, linearisasi $L(C)$ untuk kelas $C$ dengan deklarasi `class C extends B with T1 with T2 ... with Tn` didefinisikan sebagai:
$$L(C) = C \mathbin{::} \left( L(T_n) \mathrel{\vec{+}} L(T_{n-1}) \mathrel{\vec{+}} \dots \mathrel{\vec{+}} L(T_1) \mathrel{\vec{+}} L(B) \right)$$

Operasi $\vec{+}$ adalah penggabungan (*concatenation*) yang mempertahankan elemen unik, di mana elemen yang duplikat pada sisi kiri dihapus jika sudah ada di sisi kanan hierarki resolusi (hanya instance terakhir yang dipertahankan).

Di tingkat JVM, compiler Scala (`scalac`) tidak memetakan multiple traits langsung menjadi multiple inheritance Java class (karena JVM melarang multiple class inheritance). Scala mengompilasi trait menjadi:
1. Interface JVM yang berisi deklarasi method abstrak (dan default method di Java 8+).
2. `$class` static forwarder (pada Scala versi lawas) atau *JVM interface default methods* (pada Scala 2.12+) yang melakukan dispatching terarah ke pemanggilan resolusi `super`.

### 3.2. Self-Type Annotations vs Subtyping
Self-type (`this: SomeType =>`) membatasi trait agar hanya dapat di-mix in ke dalam class yang juga mengimplementasikan atau mengekstensi `SomeType`. 

Perbedaan fundamental strukturalnya:
- **Subtyping (`trait A extends B`)**: Menghasilkan hubungan *is-a* yang ketat. `A` mewarisi seluruh antarmuka publik dan implementasi internal `B`. Siklus hierarki (`trait A extends B` dan `trait B extends A`) dilarang keras oleh compiler (*cyclic inheritance graph error*).
- **Self-Type (`trait A { this: B => }`)**: Menyatakan dependensi *requires-a*. `A` mengasumsikan ketersediaan fungsionalitas `B` pada runtime, tanpa menjadikan `A` subkelas langsung dari `B` dalam hierarki interface murni saat deklarasi. Hal ini memungkinkan pemodelan siklus ketergantungan antarmuka secara aman untuk keperluan dependency injection (*read: structural assembly*).

### 3.3. Representasi Memori: Value Classes (`AnyVal`) & Universal Traits
Pada arsitektur sistem enterprise, pembungkusan tipe primitif (seperti `Long` untuk `AccountId` atau `OrderId`) sering kali memicu overhead GC masif akibat alokasi jutaan objek kecil pada memori heap.

```
Standard Wrapper:
[ JVM Object Header (12 or 16 bytes) ] + [ Primitive Long Payload (8 bytes) ] + [ Alignment Padding ]
Total: 24 bytes per instance!

Value Class (extends AnyVal):
[ Primitive Long Payload (8 bytes) langsung di stack / register ] (Zero Allocation)
```

Compiler Scala mentransformasikan instance Value Class menjadi tipe primitif murninya pada level JVM bytecode selama tidak terjadi *boxing triggers*:
- Objek tidak diperlakukan sebagai runtime type lain (misalnya disimpan di dalam koleksi generik `List[AccountId]` tanpa spesialisasi, atau di-cast ke tipe `Any`).
- Objek tidak digunakan dalam ekspresi runtime type testing (`isInstanceOf`).
- Objek tidak diinisialisasi dalam array primitif tanpa pembungkus yang kompatibel.

Universal Trait adalah trait yang meng-extend `Any`. Trait ini hanya boleh memiliki method `def` (tanpa `val`, tanpa inisialisasi state) dan hanya dapat di-extend oleh `AnyVal`.

---

## 4. Why & What

| Paradigma / Fitur | What (Definisi Teknis) | Why (Tujuan Arsitektural & Masalah yang Diselesaikan) |
| :--- | :--- | :--- |
| **Linearization** | Mekanisme flattening graph inheritance menjadi urutan terurut tunggal. | Menghilangkan *Diamond Problem*, memungkinkan modular mixin composition dan decorator pattern dinamis tanpa *boilerplate*. |
| **Self-Types** | Anotasi penyempitan konteks `this` tanpa subtyping inheritance eksplisit. | Menyediakan *compile-time dependency safety*, modularisasi modul domain tanpa framework refleksi runtime (misal: Spring/Guice). |
| **Value Classes** | Kelas domain yang mewarisi `AnyVal` dengan tepat satu field publik. | Mengeliminasi *Heap Allocation footprint*, memitigasi GC Pause pada microservices throughput jutaan TPS. |
| **Abstract Types** | Anggota tipe abstrak (`type Output`) yang dideklarasikan di dalam trait. | Menyederhanakan penulisan API ketika relasi antar-tipe kompleks, mencegah *Type Parameter Explosion* (`Service[Req, Res, Ctx, Err]`). |

---

## 5. How (Workflow Detail)

Berikut adalah alur resolusi dependensi dan eksekusi kompilasi Scala OO Lanjutan:

```
[ Deklarasi Trait / Class ]
           │
           ▼
[ AST Phase & Type Checking ] ──> Validasi Self-Type Constraints
           │                     (Gagal jika host class tidak memenuhi type bound)
           ▼
[ Linearization Resolution ] ───> Hitung urutan C3-order dari kanan ke kiri
           │                     Transformasikan pemanggilan 'super' menjadi
           │                     direct invocation ke trait tetangga
           ▼
[ Erasure & Unboxing Pass ] ───> Evaluasi Value Classes (AnyVal)
           │                     Hapus wrapper jika tidak terjadi boxing context
           ▼
[ JVM Bytecode Generation ] ───> Output: Java Interfaces (default methods) &
                                 Specialized Primitives
```

Secara operasional:
1. Compiler memetakan mixin trait ke representasi internal linear.
2. Setiap `super.method()` dihubungkan bukan ke parent langsung secara struktural, melainkan ke node berikutnya dalam daftar hasil linearisasi (*Right-to-Left*).
3. Compiler memvalidasi kontrak Self-Type: Apakah class akhir (`final class App`) memuaskan gabungan seluruh type yang disyaratkan? Jika tidak, proses kompilasi dihentikan (*Compile-time assertion*).
4. Khusus untuk tipe turunan `AnyVal`, compiler memverifikasi struktur memori: Jika method yang dipanggil tidak membutuhkan referensi object heap, compiler me-rewrite pemanggilan method tersebut menjadi static method call Java yang memproses tipe primitif murni.

---

## 6. Analogy & Diagram ASCII

### Analogi: Jalur Perakitan Pabrik Otomotif (Linearization)
Bayangkan perakitan sasis mobil. Trait dasar adalah `Chassis`. Berbagai stasiun perakitan (`RustProofing`, `PaintLayer`, `ClearCoat`) bertindak sebagai trait yang menambahkan lapisan perlindungan.

Jika stasiun bekerja secara paralel tak terkontrol, cat bisa diaplikasikan sebelum pelapisan anti-karat. Dengan **Linearization**, Scala menjamin urutan instalasi lapisan berjalan satu arah berurutan secara terprediksi:

```
Hierarki Kode:
class SportsCar extends Chassis with RustProofing with PaintLayer with ClearCoat

Resolusi Linearization (Stack Eksekusi dari Kiri ke Kanan):
[SportsCar] -> [ClearCoat] -> [PaintLayer] -> [RustProofing] -> [Chassis] -> [AnyRef] -> [Any]

Visualisasi Resolusi Eksekusi Super():
      
         +--------------------------------------------------------+
         |                       SportsCar                        |
         +--------------------------------------------------------+
                                     │ super.apply()
                                     ▼
         +--------------------------------------------------------+
         |                       ClearCoat                        |
         +--------------------------------------------------------+
                                     │ super.apply()
                                     ▼
         +--------------------------------------------------------+
         |                       PaintLayer                       |
         +--------------------------------------------------------+
                                     │ super.apply()
                                     ▼
         +--------------------------------------------------------+
         |                      RustProofing                      |
         +--------------------------------------------------------+
                                     │ super.apply()
                                     ▼
         +--------------------------------------------------------+
         |                        Chassis                         |
         +--------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Trait Linearization & Stackable Modifications

Contoh dasar berikut mendemonstrasikan bagaimana Scala menyelesaikan konflik resolusi method melalui stacking urutan deklarasi `with`.

```scala
package com.enterprise.scalalab.basic

sealed trait Logger {
  def log(message: String): String = s"Base: $message"
}

trait TimestampLogger extends Logger {
  override def log(message: String): String = {
    super.log(s"[${System.currentTimeMillis()}] $message")
  }
}

trait UpperCaseLogger extends Logger {
  override def log(message: String): String = {
    super.log(message.toUpperCase)
  }
}

// Service A: Timestamp diaplikasikan lebih dulu atau Uppercase lebih dulu?
// Linearization: ServiceA -> UpperCaseLogger -> TimestampLogger -> Logger -> AnyRef -> Any
final class ServiceA extends Logger with TimestampLogger with UpperCaseLogger {
  def process(data: String): String = log(data)
}

// Linearization: ServiceB -> TimestampLogger -> UpperCaseLogger -> Logger -> AnyRef -> Any
final class ServiceB extends Logger with UpperCaseLogger with TimestampLogger {
  def process(data: String): String = log(data)
}

object LinearizationDemo extends App {
  val sA = new ServiceA
  println(s"ServiceA Output: ${sA.process("order payload")}")
  // Evaluasi ServiceA:
  // 1. UpperCaseLogger mengubah "order payload" -> "ORDER PAYLOAD"
  // 2. TimestampLogger menerima "ORDER PAYLOAD" dan menambahkan timestamp
  // 3. Logger dasar menerima string final

  val sB = new ServiceB
  println(s"ServiceB Output: ${sB.process("order payload")}")
  // Evaluasi ServiceB:
  // 1. TimestampLogger menambahkan timestamp ke "order payload"
  // 2. UpperCaseLogger mengubah seluruh teks (termasuk timestamp) menjadi UPPERCASE
}
```

### 7.2. Practical Example: Zero-Allocation Type Safety & Self-Type Registry

Implementasi domain model pembayaran finansial dengan proteksi Type-Level, Value Class unboxed, dan modular injection berbasis Self-Type.

```scala
package com.enterprise.scalalab.advanced

import java.time.Instant
import java.util.UUID

// --- VALUE CLASSES (Zero Allocation Types) ---
final class AccountId(val underlying: UUID) extends AnyVal
final class TransactionId(val underlying: String) extends AnyVal
final class MonetaryAmount(val cents: Long) extends AnyVal {
  def +(that: MonetaryAmount): MonetaryAmount = new MonetaryAmount(this.cents + that.cents)
  def isPositive: Boolean = cents > 0
}

// Domain Model
case class LedgerEntry(
  txId: TransactionId,
  source: AccountId,
  destination: AccountId,
  amount: MonetaryAmount,
  timestamp: Instant
)

// --- ABSTRACT TYPES VS GENERICS UNTUK REPOSITORY ---
trait StorageEngine {
  type RecordKey
  type RecordValue
  
  def put(key: RecordKey, value: RecordValue): Boolean
  def get(key: RecordKey): Option[RecordValue]
}

final class LedgerStorageEngine extends StorageEngine {
  type RecordKey   = TransactionId
  type RecordValue = LedgerEntry

  private val memoryStore = scala.collection.concurrent.TrieMap.empty[String, LedgerEntry]

  override def put(key: TransactionId, value: LedgerEntry): Boolean = {
    memoryStore.put(key.underlying, value).isEmpty
  }

  override def get(key: TransactionId): Option[LedgerEntry] = {
    memoryStore.get(key.underlying)
  }
}

// --- SELF-TYPE SUBSYSTEMS ARCHITECTURE ---
trait SystemMetricsComponent {
  def recordMetric(name: String, value: Double): Unit
}

trait ConsoleMetricsComponent extends SystemMetricsComponent {
  override def recordMetric(name: String, value: Double): Unit = {
    println(s"[METRIC] $name -> $value")
  }
}

// PaymentEngine mewajibkan dependency SystemMetricsComponent TANPA meng-extend nya
trait PaymentProcessorComponent {
  this: SystemMetricsComponent => // Self-type: Menuntut metrics layer tersedia saat instansiasi

  def processPayment(
    source: AccountId, 
    destination: AccountId, 
    amount: MonetaryAmount,
    storage: StorageEngine { type RecordKey = TransactionId; type RecordValue = LedgerEntry }
  ): Either[String, TransactionId] = {
    if (!amount.isPositive) {
      recordMetric("payment.failure.invalid_amount", 1.0)
      Left("Amount must be strictly positive")
    } else {
      val txId = new TransactionId(UUID.randomUUID().toString)
      val entry = LedgerEntry(txId, source, destination, amount, Instant.now())
      
      storage.put(txId, entry)
      recordMetric("payment.success", amount.cents.toDouble / 100.0)
      Right(txId)
    }
  }
}

// Rakitan Komponen Tingkat Tinggi (Enterprise Assembly)
final class PaymentApplicationRegistry 
  extends PaymentProcessorComponent 
  with ConsoleMetricsComponent

object ProductionRunner extends App {
  val storage = new LedgerStorageEngine
  val app = new PaymentApplicationRegistry
  
  val srcAcc = new AccountId(UUID.randomUUID())
  val dstAcc = new AccountId(UUID.randomUUID())
  val fund   = new MonetaryAmount(2500000) // Rp 25.000,00

  app.processPayment(srcAcc, dstAcc, fund, storage) match {
    case Right(txId) => 
      println(s"Transaksi sukses disimpan. ID: ${txId.underlying}")
      println(s"Audit readback: ${storage.get(txId)}")
    case Left(err) => 
      System.err.println(s"Transaksi ditolak: $err")
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Desain Audit Logging Interceptor pada Core-Banking Engine

#### Konteks & Problem
Sebuah sistem core banking memproses 50.000 transaksi pembayaran per detik (TPS). Persyaratan kepatuhan regulasi finansial mewajibkan:
1. Seluruh transaksi wajib melewati rantai validasi berlapis: Validasi Fraud, Validasi Limit Saldo, Enkripsi Hardware Security Module (HSM), dan Audit Log Immutability.
2. Setiap layer interceptor harus dapat diuji secara terisolasi tanpa framework mocking yang lambat.
3. Alokasi memori tidak boleh memicu siklus Stop-the-World (STW) GC melebihi 10 milidetik.
4. Rantai interceptor harus bersifat *pluggable* sesuai regulasi yurisdiksi negara penerima transaksi.

#### Solusi Arsitektural Menggunakan Stackable Traits & Value Classes
Kita merancang pipeline eksekusi berbasis *Stackable Trait Pattern* dengan tipe data primitif terbungkus Value Classes untuk menjamin nol alokasi heap saat validasi state berjalan.

```scala
package com.enterprise.banking.engine

import java.time.Instant

// Domain primitives zero-overhead
final class AccountId(val value: Long) extends AnyVal
final class Amount(val rawCents: Long) extends AnyVal
final class Currency(val isoCode: String) extends AnyVal

case class PaymentCommand(
  source: AccountId,
  destination: AccountId,
  amount: Amount,
  currency: Currency,
  timestamp: Instant
)

sealed trait PaymentResult
case class Authorized(authCode: String) extends PaymentResult
case class Rejected(reason: String) extends PaymentResult

// Interface Dasar Eksekusi
trait PaymentService {
  def execute(command: PaymentCommand): PaymentResult
}

// Implementasi Base Layer (Core Target)
class CorePaymentService extends PaymentService {
  override def execute(command: PaymentCommand): PaymentResult = {
    // Simulasi delegasi ke Ledger Database Engine
    Authorized(s"AUTH-${command.source.value}-${System.nanoTime()}")
  }
}

// Stackable Layer 1: Audit Logger
trait AuditLoggingInterceptor extends PaymentService {
  abstract override def execute(command: PaymentCommand): PaymentResult = {
    val startTime = System.nanoTime()
    val result = super.execute(command)
    val latencyNs = System.nanoTime() - startTime
    
    println(s"[AUDIT] Acc: ${command.source.value} | Amount: ${command.amount.rawCents} | Result: $result | Latency: ${latencyNs}ns")
    result
  }
}

// Stackable Layer 2: Fraud Detection Interceptor
trait FraudDetectionInterceptor extends PaymentService {
  private val MaxThresholdCents = 1_000_000_000L // 10 Juta Rupiah/Sen

  abstract override def execute(command: PaymentCommand): PaymentResult = {
    if (command.amount.rawCents > MaxThresholdCents) {
      Rejected(s"Fraud Alert: Amount ${command.amount.rawCents} exceeds hard limit.")
    } else {
      super.execute(command)
    }
  }
}

// Stackable Layer 3: Dynamic Rate Limiter
trait RateLimiterInterceptor extends PaymentService {
  // Lock-free atomic tracker simulasi
  private val requestCount = new java.util.concurrent.atomic.AtomicLong(0)

  abstract override def execute(command: PaymentCommand): PaymentResult = {
    if (requestCount.incrementAndGet() > 100_000) {
      Rejected("Too Many Requests: Velocity limit exceeded.")
    } else {
      super.execute(command)
    }
  }
}

// Factory Perakitan Sesuai Profil Regulasi Enterprise
object BankingEngineApp extends App {
  // Pipeline Perakitan: Request masuk melalui RateLimiter -> Fraud -> Audit -> Core
  // Urutan Linearization: EnterprisePipeline -> RateLimiter -> Fraud -> Audit -> CorePaymentService
  val pipeline = new CorePaymentService 
    with AuditLoggingInterceptor 
    with FraudDetectionInterceptor 
    with RateLimiterInterceptor

  val validCmd = PaymentCommand(
    source = new AccountId(8800112233L),
    destination = new AccountId(9911223344L),
    amount = new Amount(50000000L),
    currency = new Currency("IDR"),
    timestamp = Instant.now()
  )

  val fraudCmd = PaymentCommand(
    source = new AccountId(8800112233L),
    destination = new AccountId(9911223344L),
    amount = new Amount(5_000_000_000L), // Triggers fraud
    currency = new Currency("IDR"),
    timestamp = Instant.now()
  )

  println("--- Processing Valid Command ---")
  println(pipeline.execute(validCmd))

  println("\n--- Processing Fraudulent Command ---")
  println(pipeline.execute(fraudCmd))
}
```

---

## 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons & Costs*) | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- |
| **Stackable Traits (Linearization)** | Sangat deklaratif, performa invocasi setara direct JVM virtual call tanpa alokasi wrapper objek runtime. | Urutan deklarasi `with` menentukan perilaku (`tight order coupling`). Sulit diubah secara dinamis saat runtime tanpa re-instansiasi. | Pipeline interceptor deterministik, validasi internal domain, logging layer. |
| **Self-Types Dependency Injection** | Kompilasi memverifikasi dependensi sepenuhnya. Tidak ada framework overhead (Spring/Guice reflection). | Kompilasi bisa melambat drastis jika dependensi membentuk hierarki raksasa (*Cake Pattern explosion*). | Pembangunan modul subsystem berskala menengah pada aplikasi monolit monorepo. |
| **Value Classes (`AnyVal`)** | Menghemat konsumsi memori Heap secara drastis, mengurangi frekuensi Major/Minor GC pause. | Boxing tersembunyi (*implicit boxing*) terjadi bila di-pass ke generic collection atau dynamic cast, membatalkan optimasi. | ID primitif (`UserId`, `AccountId`), satuan moneter, wrapper scalar tanpa state mutable. |
| **Structural Types (`type X = { def a: Int }`)** | Sangat fleksibel memproses tipe yang tidak memiliki hierarchy parent yang sama (*ad-hoc duck typing*). | Menggunakan **Java Reflection** secara default di JVM runtime. Performa turun drastis (hingga 100x lebih lambat). | Dilarang keras pada *hot path* enterprise. Hanya boleh dipakai untuk deserialisasi ad-hoc atau testing. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1. Kesalahan 1: Unintentional Boxing pada Value Classes
**Masalah**: Developer membuat Value Class dengan harapan zero-allocation, tetapi menyimpannya ke dalam `List[T]` generik tanpa pertimbangan.
```scala
final class Meter(val value: Double) extends AnyVal

// RUNTIME BUG / PERFORMANCE LEAK:
val measurements: List[Meter] = List(new Meter(1.5), new Meter(2.0))
// List[T] di Scala mengasumsikan T adalah reference object (AnyRef). 
// JVM terpaksa mengalokasikan instance Meter pada heap untuk setiap elemen!
```
**Troubleshooting**: Gunakan array primitif murni (`Array[Double]`) atau pustaka *specialized collections* jika bekerja dengan jutaan metrik numerik. Verifikasi output bytecode menggunakan alat decompiler:
```bash
javap -c target/scala-2.13/classes/com/enterprise/MyClass.class
```
Cari instruksi JVM `INVOKEVIRTUAL ...valueOf` atau pembentukan instance objek `NEW com/enterprise/Meter`.

### 10.2. Kesalahan 2: Ambiguous Mixin Initialisation Order (NPE Saat Startup)
**Masalah**: Mengakses abstract `val` di dalam body trait sebelum kelas konkret sempat menginisialisasinya.
```scala
trait ConfigProvider {
  val timeoutSeconds: Int
  val milliMultiplier: Int = 1000
  // BUG: timeoutSeconds bernilai 0 default JVM saat trait diinisialisasi sebelum subclass val siap!
  val timeoutMillis: Int = timeoutSeconds * milliMultiplier 
}

class ApiClient extends ConfigProvider {
  override val timeoutSeconds: Int = 5 // Diinisialisasi SETELAH trait constructor selesai
}

// ApiClient.timeoutMillis menghasilkan nilai 0, bukan 5000!
```
**Troubleshooting**:
Gunakan `lazy val` atau `def` pada trait konfigurasi, atau terapkan `early definitions` / construct parameters (Scala 3 `trait` parameters):
```scala
trait SafeConfigProvider {
  def timeoutSeconds: Int
  val milliMultiplier: Int = 1000
  lazy val timeoutMillis: Int = timeoutSeconds * milliMultiplier
}
```

### 10.3. Kesalahan 3: Diamond Inheritance Shadowing
**Masalah**: Menganggap urutan deklarasi `class A extends B with C` sama dengan `class A extends C with B`.
**Troubleshooting**: Terapkan compiler flag berikut pada `build.sbt` untuk memunculkan warning linierisasi:
```scala
scalacOptions ++= Seq(
  "-Wconf:cat=lint-byname-implicit:w",
  "-Xlint:adapted-args",
  "-Xlint:inaccessible"
)
```

---

## 11. Best Practices (Production Checklist)

1. [ ] **Hapus Structural Typing Berbasis Refleksi**: Hindari sintaksis `def handle(target: { def close(): Unit })` di *critical path*. Gunakan Typeclasses atau Trait eksplisit.
2. [ ] **Gunakan `extends AnyVal` Secara Ketat**: Pastikan kelas pembungkus primitif hanya memiliki `def` internal, satu field tunggal `val`, dan tidak mengimplementasikan method yang men-trigger boxing.
3. [ ] **Self-Type Bukan Pewarisan State**: Gunakan Self-type semata-mata untuk injeksi kontrak antarmuka, bukan untuk membagi state mutable global.
4. [ ] **Pemberian Modifier `sealed` pada Root Hierarchy**: Seluruh basis trait domain tertutup harus ditandai `sealed` untuk memicu exhaustiveness check pada pattern matching oleh compiler.
5. [ ] **Penerapan Variance Bounds yang Tepat**: Selalu ikuti prinsip PECS (*Producer Extends, Consumer Super*). Gunakan Covariance `+T` hanya pada tipe data read-only/immutable (Producer), dan Contravariance `-T` pada consumer method/callback.
6. [ ] **Inisialisasi Field Trait dengan `lazy val`**: Hindari Null Pointer Exception saat evaluasi hirarki linearization dengan memprioritaskan `lazy val` untuk nilai terkomputasi kompleks.

---

## 12. Hands-on Practice

Struktur direktori praktikum yang harus disiapkan:
```
hands-on/m02/
├── build.sbt
└── src/
    └── main/
        └── scala/
            └── com/
                └── enterprise/
                    └── advanced_oop/
                        ├── EngineModels.scala
                        ├── InterceptorPipeline.scala
                        └── Runner.scala
```

### Langkah 1: Buat file konfigurasi `build.sbt`
```scala
name := "advanced-oop-production"
version := "1.0.0"
scalaVersion := "2.13.12"

scalacOptions ++= Seq(
  "-deprecation",
  "-feature",
  "-unchecked",
  "-Xlint",
  "-opt:l:inline",
  "-opt-inline-from:com.enterprise.advanced_oop.**"
)
```

### Langkah 2: Definisikan Model Teroptimasi (`EngineModels.scala`)
```scala
package com.enterprise.advanced_oop

import java.util.UUID

final class TenantId(val value: UUID) extends AnyVal
final class Payload(val content: String) extends AnyVal

case class ExecutionContext(
  traceId: String,
  tenant: TenantId,
  isPrivileged: Boolean
)

sealed trait PipelineResponse
case class Success(output: String) extends PipelineResponse
case class AccessDenied(reason: String) extends PipelineResponse
```

### Langkah 3: Bangun Interceptor Stackable Pipeline (`InterceptorPipeline.scala`)
```scala
package com.enterprise.advanced_oop

trait RequestDispatcher {
  def dispatch(ctx: ExecutionContext, payload: Payload): PipelineResponse
}

class RootDispatcher extends RequestDispatcher {
  override def dispatch(ctx: ExecutionContext, payload: Payload): PipelineResponse = {
    Success(s"Executed trace [${ctx.traceId}] with payload: ${payload.content}")
  }
}

trait SecurityFilter extends RequestDispatcher {
  abstract override def dispatch(ctx: ExecutionContext, payload: Payload): PipelineResponse = {
    if (!ctx.isPrivileged) {
      AccessDenied(s"Tenant ${ctx.tenant.value} does not have elevated execution privilege.")
    } else {
      super.dispatch(ctx, payload)
    }
  }
}

trait LatencyMetricsFilter extends RequestDispatcher {
  abstract override def dispatch(ctx: ExecutionContext, payload: Payload): PipelineResponse = {
    val t1 = System.nanoTime()
    try {
      super.dispatch(ctx, payload)
    } finally {
      val t2 = System.nanoTime()
      println(s"[PERF] Trace ${ctx.traceId} execution latency: ${t2 - t1} ns")
    }
  }
}
```

### Langkah 4: Buat Runner dan Buktikan Urutan Linearization (`Runner.scala`)
```scala
package com.enterprise.advanced_oop

import java.util.UUID

object Runner extends App {
  // Susun pipeline
  val pipeline = new RootDispatcher with SecurityFilter with LatencyMetricsFilter
  
  val tenant = new TenantId(UUID.randomUUID())
  
  val nonPrivCtx = ExecutionContext("trace-001", tenant, isPrivileged = false)
  val privCtx    = ExecutionContext("trace-002", tenant, isPrivileged = true)
  val payload    = new Payload("UPDATE_SYSTEM_CONFIGURATION")

  println("=== Menjalankan Unprivileged Context ===")
  val res1 = pipeline.dispatch(nonPrivCtx, payload)
  println(s"Hasil 1: $res1\n")

  println("=== Menjalankan Privileged Context ===")
  val res2 = pipeline.dispatch(privCtx, payload)
  println(s"Hasil 2: $res2")
}
```

Uji langsung melalui terminal:
```bash
cd hands-on/m02
sbt run
```

---

## 13. Exercise

### Level Easy
Diberikan trait-trait berikut:
```scala
trait A { def ping: String = "A" }
trait B extends A { override def ping: String = "B -> " + super.ping }
trait C extends A { override def ping: String = "C -> " + super.ping }
trait D extends B with C
trait E extends C with B
```
1. Tuliskan urutan linearisasi formal $L(D)$ dan $L(E)$.
2. Tanpa mengeksekusi di komputer, tentukan string output pemanggilan `(new D).ping` dan `(new E).ping`.

### Level Medium
Kembangkan sebuah sistem penyimpanan berbasis Memory Cache dengan Abstract Type Members:
1. Deklarasikan trait `CacheSystem` dengan dua abstract types: `type CacheKey` dan `type CacheValue`.
2. Sediakan method `def insert(k: CacheKey, v: CacheValue): Unit` dan `def fetch(k: CacheKey): Option[CacheValue]`.
3. Buat implementasi konkret `RedisStyleCache` di mana `CacheKey` terikat ke `String` dan `CacheValue` terikat ke tipe data `Array[Byte]`. Pastikan penulisan aman dari type erasure!

### Level Hard
Buat trait decorator `CircuitBreakerInterceptor` yang dapat di-stack ke dalam trait dasar `ExternalRpcCaller`:
1. Rancang sedemikian rupa sehingga jika eksekusi `super.invoke()` melempar Exception sebanyak 3 kali berturut-turut, pemanggilan ke-4 akan langsung mengembalikan nilai fallback tanpa memanggil `super.invoke()`.
2. Seluruh implementasi harus thread-safe tanpa menggunakan keyword `synchronized` primitif (gunakan *AtomicReference* atau *AtomicInteger*).
3. Gunakan Value Class untuk membungkus `CallTimeoutMs` dan `FailureThreshold` demi meminimalkan alokasi heap saat pemanggilan frekuensi tinggi.

---

## 14. Challenge

### Arsitektur High-Throughput Matching Engine dengan Trait-Composition
Rancang subsistem inti dari sebuah platform limit order book (Matching Engine) finansial dengan spesifikasi arsitektur:
1. **Zero Allocation**: Gunakan `AnyVal` untuk seluruh identitas: `OrderId`, `Price`, `Quantity`, dan `InstrumentId`.
2. **Flexible Fee Rules Linearization**: Buat komponen stackable modification untuk menghitung potongan biaya (*fee schedule*):
   - `MakerDiscount`: Memotong fee sebesar 0.05% jika order bersifat passive.
   - `VolumeRebate`: Memberikan rabat fee jika pengguna memiliki total trading volume 30 hari > $10M.
   - `RegulatoryTax`: Menambahkan pajak transaksi pemerintah sebesar 0.1% di layer terluar.
3. **Penyusunan Dependensi**: Gunakan **Self-Type Annotations** untuk memisahkan komponen `MatchingCore`, `OrderAuditJournal`, dan `RiskManager`.
4. **Tantangan Mutlak**: Sistem tidak boleh menggunakan pustaka eksternal (murni Scala standard library), harus thread-safe, dan urutan pemotongan fee harus ditentukan secara statik pada level kompilasi melalui *trait linearization* terbalik.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic
1. Apa kompleksitas waktu penyelesaian linearisasi C3 di Scala pada struktur pohon pewarisan mixin tunggal?
2. Kapan sebuah kelas yang mewarisi `AnyVal` secara otomatis dipaksa (*boxed*) menjadi objek referensi di Java Heap?
3. Sebutkan perbedaan utama antara deklarasi `trait A extends B` dengan `trait A { this: B => }`!
4. Mengapa kita tidak bisa mendeklarasikan `val` biasa di dalam *Universal Trait*?
5. Apa kegunaan keyword `abstract override` pada method di dalam sebuah trait?

### 5 Pertanyaan Intermediate
6. Jelaskan apa yang terjadi di tingkat Java Virtual Machine ketika dua buah trait memiliki method implementasi konkret dengan signature yang persis sama, kemudian di-extend oleh satu class secara bersamaan!
7. Bagaimana compiler Scala menjamin pemanggilan `super` pada *Stackable Trait Pattern* tidak memicu loop rekursif tanpa akhir?
8. Mengapa `trait` di Scala 2.12+ memanfaatkan fitur Java 8 Default Interface Methods daripada mengompilasi file `$class.class` pembantu seperti pada Scala 2.11?
9. Bagaimana cara kerja Type Erasure terhadap `Abstract Type Members` jika dibandingkan dengan `Generics Type Parameters` saat runtime JVM?
10. Diberikan kode `class HeavyId(val id: Long) extends AnyVal`. Jika kita melakukan pemanggilan `val arr = Array.fill(1000)(new HeavyId(42L))`, apakah alokasi heap terjadi untuk 1000 objek individual? Jelaskan mekanismenya!

### 3 Skenario Kasus Produksi
11. **Kasus Memori Leak / OOM**:
    Sebuah aplikasi *streaming telemetry* yang memproses 500.000 metrik per detik mengalami `java.lang.OutOfMemoryError: Java heap space` setelah 2 jam berjalan. Padahal, tim engineer sudah membungkus data point ke dalam Value Class `case class MetricPoint(timestamp: Long, value: Double) extends AnyVal`. Saat heap dump dianalisis, ditemukan jutaan objek `MetricPoint` tergeletak di memory. Telusuri titik kegagalan (*root cause*) arsitektural yang menyebabkan Value Class tersebut tetap di-boxing oleh JVM!
12. **Kasus Deadlock / Race Condition Linearization**:
    Sebuah sistem microservice enterprise mengintegrasikan dua trait stackable: `DistributedLockingInterceptor` dan `DatabaseTransactionInterceptor`. Saat urutan mixin dideklarasikan sebagai `with DistributedLockingInterceptor with DatabaseTransactionInterceptor`, throughput database normal. Namun ketika seorang engineer junior mengubah urutannya menjadi `with DatabaseTransactionInterceptor with DistributedLockingInterceptor`, terjadi fenomena *connection pool exhaustion* dan *thread starvation*. Mengapa urutan linearisasi trait dapat merusak stabilitas transaksi database secara katastropik?
13. **Kasus Compile-Time Explosion**:
    Sebuah proyek core perbankan monolitik mengimplementasikan *Cake Pattern* skala raksasa dengan ratusan trait komponen yang saling bergantung via *Self-Type Annotations*. Waktu kompilasi SBT melonjak dari 4 menit menjadi 55 menit, dan compiler sering melempar `java.lang.StackOverflowError` saat fase typechecking. Berikan diagnosa arsitektur mengapa hal ini terjadi pada compiler Scala, dan bagaimana cetak biru refaktorisasi bertahap untuk beralih ke pola desain modular modern tanpa mengorbankan type safety!

---

## 16. Summary

- **Trait Linearization** adalah algoritma deterministik yang meratakan *graph inheritance* multi-dimensi menjadi struktur linier tunggal (*Right-to-Left*), menyelesaikan *diamond problem*, dan menjadi fondasi dari *Stackable Trait Pattern*.
- **Self-Type Annotations** (`this: SubSystem =>`) menyediakan pemisahan antarmuka dependensi tingkat tinggi tanpa memaksakan relasi subtyping langsung, memvalidasi perakitan arsitektur langsung di fase kompilasi.
- **Value Classes (`extends AnyVal`)** adalah instrumen utama optimasi performa memori di JVM. Fitur ini membungkus representasi primitif secara type-safe pada level kode sumber tanpa membayar biaya alokasi objek heap di level runtime, selama terbebas dari jebakan *boxing triggers*.
- Penguasaan konsep OOP tingkat lanjut ini membedakan software engineering Scala amatir dari arsitektur enterprise berskala besar yang siap menangani jutaan transaksi konkuren dengan stabilitas dan efisiensi resource maksimum.