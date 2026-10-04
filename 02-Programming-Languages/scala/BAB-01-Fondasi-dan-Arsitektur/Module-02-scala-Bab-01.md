# Bab 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Scala 3 / JVM Internals)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Principal/Staff Engineer diharapkan mampu:
- **Menganalisis** pemetaan bytecode dari konstruksi bahasa Scala 3 (Traits, Opaque Types, Contextual Abstractions) ke Java Virtual Machine (JVM) bytecode guna mencegah regresi performa pada level instruksi CPU/JIT.
- **Mengevaluasi** jejak alokasi memori (*heap footprint*) dan *escape analysis* pada abstraksi tingkat tinggi (*zero-cost abstractions* vs *boxed primitives*).
- **Merancang** arsitektur *concurrent execution* bebas *deadlock* dan *thread-pool starvation* dengan mengisolasi komputasi asinkron, CPU-bound, dan blocking I/O melalui `ExecutionContext` custom.
- **Mengimplementasikan** pola arsitektur berbasis *Typeclass* menggunakan mekanisme Scala 3 (`given`, `using`, `extension`) yang modular, terisolasi, dan dapat diuji secara deterministik tanpa overhead *runtime reflection*.
- **Mendiagnosis dan Memitigasi** degradasi throughput pada sistem *mission-critical* yang diakibatkan oleh *megamorphic call-sites*, *closure object leak*, dan *unbounded context propagation*.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Fondasi JVM**: Pemahaman siklus hidup classloading, *Garbage Collection* (G1GC/ZGC generational mechanics), *JIT Compilation* (Tiered compilation: C1 client, C2 server compiler), dan *Java Memory Model* (JMM: *happens-before*, *volatile*, *cache coherence*).
- **Fondasi Scala Dasar**: Sintaks Scala 3, pola *Pattern Matching*, rekursi, serta paradigma *Object-Functional Programming* dasar.
- **Concurrency Primitives**: Menguasai konsep dasar Thread, `java.util.concurrent.ForkJoinPool`, `java.util.concurrent.ThreadPoolExecutor`, dan `scala.concurrent.Future`.
- **Tooling**: Terbiasa menggunakan CLI, `sbt` (Scala Build Tool), `javap` (JVM class file disassembler), dan Git.

---

### 3. Concept & Internal Architecture

#### 3.1. Pemetaan Bytecode & Name Mangling pada Scala 3
Scala dieksekusi di atas JVM dengan mengompilasi kode sumber (`.scala`) langsung menjadi Java bytecode standard (`.class`). Namun, karena sistem tipe Scala jauh lebih ekspresif daripada Java, Scala compiler (`scalac` / Dotty) melakukan transformasi struktural yang masif:

1. **Trait Encoding**:
   Sejak Scala 2.12 dan disempurnakan di Scala 3, trait dengan implementasi konkret dikompilasi langsung menjadi Java 8+ *default methods* di antarmuka (interface) JVM jika tidak memiliki state. Jika trait mendefinisikan *field* (`val`), compiler menghasilkan deklarasi getter/setter abstrak di interface dan menginjeksikan field konkret ke dalam *class* yang mengimplementasikan trait tersebut.
   
2. **Name Mangling**:
   Karakter khusus Scala (operator seperti `+:`, `/:`, `==`, `!`) tidak valid pada JVM bytecode identifier level. Compiler melakukan encoding:
   - `+` menjadi `$plus`
   - `:` menjadi `$colon`
   - Private members yang diakses dari inner class/lambda dimangle dengan prefix `$access` atau disambiguasi dengan paket/nama kelas untuk mempertahankan enkapsulasi biner.

```
Scala Source:                    JVM Bytecode Equivalent:
trait MetricsCollector {         public interface MetricsCollector {
  def record(v: Long): Unit        public abstract void record(long v);
  def +:(v: Long): Unit =          public default void $plus$colon(long v) {
    record(v)                        this.record(v);
}                                  }
                                 }
```

#### 3.2. Type Erasure vs Reification
JVM mengeksekusi bytecode menggunakan sistem tipe yang menghapus parameter generik (*type erasure*) warisan Java 1.5. Konstruksi seperti `List[A]` direduksi menjadi `List[Object]` pada level *method signature*. 

```scala
// Scala Level
def processEntities[T](entities: List[T]): Unit = ???

// Bytecode Level (hasil javap -c)
public void processEntities(scala.collection.immutable.List entities);
```

Untuk mengatasinya, Scala menggunakan:
- **`scala.reflect.ClassTag`**: Menyimpan metadata kelas runtime konkret untuk tipe terhapus (hanya tipe kelas tingkat atas, bukan parameter bersarang).
- **`scala.reflect.TypeTest` / `scala.reflect.Typeable`** (Scala 3): Mengizinkan *runtime pattern matching* yang aman tanpa peringatan *unchecked warning* compiler melalui pengujian predikat yang deterministik.

#### 3.3. Zero-Cost Abstraction: `AnyVal` vs Scala 3 `opaque type`
Sebelum Scala 3, pembungkusan nilai primitif (Domain-Driven Design Value Object) menggunakan `extends AnyVal` (*Value Classes*). Akan tetapi, JVM memaksakan alokasi heap (*boxing*) pada situasi:
- Nilai dijadikan argumen koleksi generic (`List[UserId]`).
- Nilai di-cast ke tipe generic atau interface (`Any` / Trait).
- Instansiasi dalam runtime array initialization.

Scala 3 memperkenalkan **Opaque Type Aliases**. *Opaque types* dijamin murni tidak memiliki representasi wrapper di runtime. Kompiler memperlakukan tipe tersebut sebagai tipe independen selama kompilasi, namun menurunkan tipenya secara transparan menjadi *underlying primitive/reference type* di bytecode:

```
+-----------------------------------------------------------+
|                      Kompilasi Scala                      |
|                                                           |
|  opaque type AccountId = Long                             |
|  val id: AccountId = AccountId(1001L)                     |
+-----------------------------------------------------------+
                             |
                             v [Type Erasure Pipeline]
+-----------------------------------------------------------+
|                    Target JVM Bytecode                    |
|                                                           |
|  // Tidak ada class AccountId di runtime!                 |
|  // Zero Allocation. Zero Overhead.                       |
|  long id = 1001L;                                         |
+-----------------------------------------------------------+
```

#### 3.4. Scala 3 Contextual Engine: `given`, `using`, & Context Bounds
Model implicits Scala 2 (`implicit val`, `implicit def`) digantikan oleh sistem contextual abstraction Scala 3 yang berbasis pemisahan intensi logis:
- **Given Instances (`given`)**: Mendefinisikan kanonikalitas dependensi/typeclass instance.
- **Using Clauses (`using`)**: Mendeklarasikan dependensi yang diselesaikan secara otomatis oleh resolusi compiler.

Compiler memproses resolusi konteks melalui langkah deterministic resolution:
1. Pencarian lokal (*Lexical scope*): imports, current block, enclosing class.
2. Pencarian *Implicit Scope*: Companion object dari tipe target, companion object dari parameter tipe typeclass.
3. *Specificity Rules*: Jika ada ambiguitas, compiler memilih instance yang memiliki hierarki subtype lebih spesifik, atau menolak kompilasi jika tingkat ambiguitas identik (*diverging implicits error*).

#### 3.5. Runtime Threading Engine & ExecutionContext Under the Hood
`scala.concurrent.ExecutionContext` mengabstraksikan antarmuka eksekusi tugas paralel ke JVM. Secara default, `ExecutionContext.global` ditenagai oleh `java.util.concurrent.ForkJoinPool`.
- Karakteristik `ForkJoinPool`: Dirancang untuk komputasi paralel *CPU-bound* berdurasi seragam dengan teknik *work-stealing*.
- **Bahaya Blocking**: Ketika pemanggilan I/O sinkron (misal: JDBC, REST client lama) dijalankan di atas `ExecutionContext.global`, thread pekerja *ForkJoinPool* masuk ke status `WAITING`/`TIMED_WAITING`. Jika semua worker thread terblokir, terjadi **ThreadPool Starvation** yang membekukan pemrosesan CPU-bound lain di seluruh aplikasi.

---

### 4. Why & What

| Dimensi | Scala 3 Enterprise Stack | Pendekatan Java Standar |
| :--- | :--- | :--- |
| **Domain Safety** | *Opaque Types* menjamin *Domain-Driven Design (DDD)* type safety tanpa alokasi memori tambahan (*zero runtime cost*). | Mengharuskan pembuatan `record` atau `class` pembungkus yang memicu alokasi heap ekstra, atau primitif telanjang yang rentan *primitive obsession*. |
| **Metaprogramming & Generics**| Typeclass pattern dengan context bounds memberikan *ad-hoc polymorphism* terverifikasi saat kompilasi (*compile-time safety*). | Runtime reflection, runtime annotations, atau dynamic proxies yang rentan meledak saat production runtime. |
| **Concurrency Guarantees** | Pemisahan formal antara komputasi murni dan asynchronous task via *referentially transparent* execution pipelines. | Eksekusi manual via runnable/callable, rentan *race conditions* dan *deadlock* tanpa static verification. |
| **Mechanical Sympathy** | Representasi data functional dikompilasi ke bytecode JVM yang dioptimasi untuk JVM JIT (inlining, devirtualization). | Kompleksitas boilerplate class inheritance hierarkis yang memperlambat JIT inline caching. |

---

### 5. How (Workflow Detail)

Alur kerja berikut mendetailkan siklus hidup kompilasi, verifikasi, hingga eksekusi kode Scala tingkat lanjut dalam production container:

```
[Scala 3 Source (.scala)]
         │
         ▼
[Frontend: Lexing, Parsing & Typechecking (Dotty Namer/Typer)]
         │
         ├─── Validasi Implicit/Given Scope Resolution
         ├─── Enforce Zero-Cost Constraints pada Opaque Types
         └─── Desugaring For-Comprehensions ke flatMap/map/withFilter
         │
         ▼
[Intermediate AST (TASTy - Typed Abstract Syntax Trees)]
         │
         ▼
[Backend: Bytecode Generator (GenBCode)]
         │
         ├─── Name Mangling untuk Simbol Operator
         ├─── Penghapusan Tipe (Type Erasure) & Synthetic Bridges Injection
         └─── Interface Default Method Injection (Traits)
         │
         ▼
[.class File (JVM Bytecode Standard)]
         │
         ▼
[JVM Classloader (Production App Server / K8s Pod)]
         │
         ├─── Bytecode Verification
         ├─── JIT Profiling (Tier 1-3 C1 Compiler: Client)
         └─── C2 High-Optimization Compilation (Devirtualization, Escape Analysis, Inlining)
```

1. **Fase Analisis Sintaks & Tipe**: Source code diperiksa. Pemanggilan `using` dicari pada *companion scope* dan *lexical scope*. Jika terjadi siklus rekursi tak terbatas pada resolusi tipe, compiler memotong proses (*divergence check*).
2. **Serialisasi TASTy**: Scala 3 mengompilasi kode ke representasi TASTy (`.tasty`), mempertahankan struktur tipe penuh sebelum *erasure*. Ini memungkinkan interoperabilitas lintas versi Scala minor secara biner.
3. **GenBCode Phase**: Mentransformasi TASTy menjadi struktur instruksi JVM resmi (`invokevirtual`, `invokestatic`, `invokeinterface`, `invokedynamic`). Lambda Scala dikompilasi menggunakan instruksi `invokedynamic` yang efisien, memanfaatkan `LambdaMetafactory` pada JVM.
4. **JIT Execution**: JVM memprofil eksekusi method. Jika sebuah method bersifat monomorphic (hanya ada satu implementasi konkret), JVM mendevirtualisasi method tersebut dan melakukan *inlining*, meniadakan overhead pemanggilan metode sama sekali.

---

### 6. Analogy & Diagram ASCII

#### 6.1. Analogi: Opaque Types vs Boxed Value Classes
Bayangkan sebuah bandara internasional:
- **Boxed Value Class (`AnyVal` yang bocor alokasi)**: Penumpang (data primitif `Long`) dimasukkan ke dalam mobil limusin VIP terpisah (objek Heap) hanya untuk melewati gerbang tol. Butuh biaya sewa limusin, bahan bakar, dan area parkir (alokasi memori heap, GC overhead).
- **Opaque Type**: Penumpang yang sama hanya diberikan gelang identifikasi khusus di tangannya (verifikasi tipe waktu kompilasi). Saat berjalan melewati gerbang tol (JVM Bytecode), dia tetaplah pejalan kaki biasa tanpa perlu limusin (murni nilai primitif `Long` pada stack/register CPU).

#### 6.2. Arsitektur Threading Execution Isolation
Diagram berikut menunjukkan pola arsitektur mutlak untuk aplikasi enterprise berkinerja tinggi:

```
                           +-------------------------------------+
                           |      HTTP/gRPC Ingress Gateway      |
                           +-------------------------------------+
                                              │
                                              ▼
               +---------------------------------------------------------------+
               |                 ExecutionContext: CPU-BOUND                   |
               |             (ForkJoinPool: Max Threads = Cores)               |
               |                                                               |
               |   - Parsing JSON/Protobuf                                     |
               |   - Enkripsi, Hashing & Validasi State                        |
               |   - Transformasi Bisnis Murni (Domain Logic)                 |
               +---------------------------------------------------------------+
                                 │                           │
                   Dispatch Asinkron           Dispatch Asinkron
                   Non-Blocking via Future     Non-Blocking via Future
                                 │                           │
                                 ▼                           ▼
  +--------------------------------------------+  +----------------------------+
  |        ExecutionContext: BLOCKING-IO       |  |  Non-Blocking EventLoop    |
  |  (ThreadPoolExecutor: Cached/Sized Elastic)|  |  (Netty / RocksDB Engine)  |
  |                                            |  +----------------------------+
  |   - Pemanggilan Database JDBC/RDBMS        |
  |   - Integrasi Legacy SOAP/REST API         |
  |   - Operasi File System Lokal              |
  +--------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Zero-Cost Domain Modeling dengan Opaque Types

```scala
// File: DomainTypes.scala
package enterprise.domain

object Identifiers:
  // Definisi Opaque Type: Di luar objek Identifiers, UserId adalah tipe unik.
  // Di dalam objek ini, UserId adalah identik dengan Long primitif.
  opaque type UserId = Long

  object UserId:
    def apply(value: Long): Either[String, UserId] =
      if value > 0 then Right(value)
      else Left(s"Invalid UserId: $value. Harus bernilai positif.")

    // Unsafe constructor untuk performa maksimal pada trusted internal data parsing
    def unsafeFrom(value: Long): UserId = value

  // Extension method untuk menambahkan kapabilitas tanpa membungkus objek
  extension (uid: UserId)
    def value: Long = uid
    def encodeToHex: String = java.lang.Long.toHexString(uid)

// File: App.scala
import enterprise.domain.Identifiers.UserId

@main def runSimpleExample(): Unit =
  val rawInput = 42L
  UserId(rawInput) match
    case Right(userId) =>
      println(s"User terverifikasi: ${userId.value}, Hex: ${userId.encodeToHex}")
      // val compileError: Long = userId // COMPILER ERROR: Type mismatch!
    case Left(err) => 
      println(s"Error validasi: $err")
```

#### 7.2. Practical Example: Production-Grade Typeclass & Asynchronous Pipeline Isolation

Contoh implementasi pattern typeclass tingkat lanjut yang menangani serialisasi transaksi finansial, dilengkapi pemisahan *thread execution context* ketat.

```scala
package enterprise.architecture

import java.util.concurrent.{Executors, ThreadFactory}
import scala.concurrent.{ExecutionContext, Future, blocking}
import java.util.concurrent.atomic.AtomicInteger

// 1. Thread Pool Isolator: Menghindari Starvation
object EnterpriseExecutors:
  private def createNamedFactory(prefix: String): ThreadFactory = new ThreadFactory:
    private val counter = new AtomicInteger(0)
    override def newThread(r: Runnable): Thread =
      val t = new Thread(r, s"$prefix-worker-${counter.incrementAndGet()}")
      t.setDaemon(true)
      t

  // Pool untuk komputasi cepat (CPU-Bound)
  val cpuBoundContext: ExecutionContext = ExecutionContext.fromExecutor(
    Executors.newFixedThreadPool(
      Runtime.getRuntime.availableProcessors(),
      createNamedFactory("cpu-core")
    )
  )

  // Pool elastis untuk Blocking I/O
  val blockingIoContext: ExecutionContext = ExecutionContext.fromExecutor(
    Executors.newCachedThreadPool(createNamedFactory("io-blocking"))
  )

// 2. Typeclass Definition
trait JsonEncoder[T]:
  def encode(value: T): String

object JsonEncoder:
  // Summoner method
  def apply[T](using ev: JsonEncoder[T]): JsonEncoder[T] = ev

  // Extension syntax provider
  extension [T: JsonEncoder](entity: T)
    def toJson: String = JsonEncoder[T].encode(entity)

// 3. Domain Model
enum TransactionStatus:
  case Pending, Settled, Rejected

case class Transaction(
  id: String,
  amountInCents: Long,
  currency: String,
  status: TransactionStatus
)

// 4. Companion Canonical Given Instances
object Transaction:
  given JsonEncoder[Transaction] with
    def encode(tx: Transaction): String =
      s"""{"id":"${tx.id}","amount":${tx.amountInCents},"currency":"${tx.currency}","status":"${tx.status}"}"""

// 5. Service Layer Menggunakan Dynamic Execution Context Passing
class PaymentAuditService(using ec: ExecutionContext):
  
  def auditTransaction[T: JsonEncoder](transaction: T): Future[Unit] = Future {
    // Berjalan di dalam CPU Context: Operasi encoding
    val jsonPayload = transaction.toJson
    println(s"[${Thread.currentThread().getName}] Encoded: $jsonPayload")
  }

  def persistToLegacyDatabase(payload: String)(using ioEc: ExecutionContext): Future[Boolean] =
    Future {
      // Menandai secara eksplisit kepada JVM/Runtime bahwa operasi ini memblokir thread
      blocking {
        println(s"[${Thread.currentThread().getName}] Menulis ke database I/O...")
        Thread.sleep(150) // Simulasi blocking I/O latency (misal: JDBC)
        true
      }
    }(ioEc)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Ultra-Low Latency Foreign Exchange (FX) Smart Order Routing
- **Perusahaan**: Tier-1 Global Investment Bank.
- **Skala Beban**: 650.000 order routing updates/detik, SLA tail latency $p99.9 < 800\mu s$ (mikrodetik).

#### Masalah Kritis di Lapangan:
Sistem lama berbasis Scala 2.13 mengalami lonjakan latency secara periodik setiap 45 detik (hingga $120ms$). Setelah profiling menggunakan **Async-Profiler** dan analisis *GC Pause log*, ditemukan dua akar masalah:
1. Penggunaan standard case class wrappers (`OrderId`, `CurrencyPair`, `Price`) menghasilkan alokasi jutaan objek kecil berumur pendek di Young Generation heap, memicu GC Minor cycle yang sangat agresif.
2. Logika audit dan konektivitas FIX Protocol (blocking socket I/O) dieksekusi di atas default global thread pool, menyebabkan thread CPU-bound untuk order matching terhambat (*thread starvation*).

#### Solusi Arsitektural:
1. **Migrasi ke Opaque Types**: Seluruh primitive domain wrapper diubah menjadi `opaque type`, mereduksi laju alokasi memori young-gen hingga 78%.
2. **Strict Thread Segregation**: Membagi workload menjadi dua pool terisolasi: pool non-blocking ring buffer (LMAX Disruptor pattern / pure CPU) dan thread pool terspesialisasi I/O socket.
3. **Monomorphic Typeclass Processing**: Mengganti dynamic runtime dispatch serialization dengan inline compile-time typeclasses via Scala 3 `given`/`using`.

#### Hasil Benchmark Pasca Optimasi:
- Young-Gen allocation turun dari $4.2\text{ GB/detik}$ menjadi $890\text{ MB/detik}$.
- Latency $p99.9$ turun stabil dari $120\text{ ms}$ ke $480\ \mu\text{s}$.
- GC Pause per jam berkurang dari 380 kali menjadi 0 (seluruh sisa objek lolos lewat Escape Analysis dan teralokasi langsung di CPU register/stack).

---

### 9. Trade-offs

Menggunakan kapabilitas lanjutan dari sistem tipe dan runtime concurrency Scala menuntut pertimbangan komputasi yang terukur:

| Dimensi | Opaque Types / Inline Methods | Standard Classes / Inheritance |
| :--- | :--- | :--- |
| **Performance** | **Maksimal**. Nol alokasi heap ekstra, branch prediction optimal, CPU cache locality sangat tinggi. | **Rendah-Sedang**. Terdapat pointer indirection overhead dan memory footprint dari header objek JVM ($16\text{ bytes}$ per instance pada 64-bit JVM). |
| **Compilation Time** | **Lebih Lambat**. Kompiler bekerja ekstra menyelesaikan deduplikasi tipe, inlining AST expansion, dan resolusi dependensi konteks. | **Cepat**. Pemetaan inheritance 1-to-1 langsung ke instruksi JVM tanpa ekspansi AST kompleks. |
| **Extensibility** | **Kaku saat runtime**. Sifat tipe terkunci saat kompilasi. Tidak bisa melakukan dynamic class reloading (*hot-swapping*) semudah Java OOP standar. | **Dinamis**. Polimorfisme runtime berbasis virtual method invocation (`invokevirtual`) mendukung dynamic loading. |
| **Debugging Complexity** | **Tinggi**. Stack trace bytecode JVM tidak menampilkan nama opaque type, melainkan primitive type aslinya. Menyulitkan debugging via dump heap murni. | **Rendah**. Stack trace menampilkan nama class pembungkus secara eksplisit. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Mengabaikan Closure Capture Memory Leak
Lambda function yang mengakses state dari class pembungkusnya secara implisit mempertahankan referensi ke seluruh objek pembungkus tersebut:

```scala
class RiskEngine(val largeHistoricalData: Array[Byte]):
  def createFilter(): Long => Boolean =
    // KESALAHAN: Mengakses method/field instance secara implisit 
    // menangkap (captures) referensi `this` (seluruh instance RiskEngine).
    // Akibatnya, largeHistoricalData tidak bisa di-GC selama lambda masih hidup.
    (tradeVolume: Long) => tradeVolume > largeHistoricalData.length

// MITIGASI: Buat closure steril tanpa referensi `this`
class OptimizedRiskEngine(val largeHistoricalData: Array[Byte]):
  def createFilter(): Long => Boolean =
    val threshold = largeHistoricalData.length // Copy nilai primitif keluar
    (tradeVolume: Long) => tradeVolume > threshold // Aman: Hanya menangkap primitif
```

#### 10.2. Megamorphic Call Sites pada Interface Trait
Jika sebuah method trait memiliki lebih dari dua implementasi konkret yang dieksekusi secara bergantian pada call-site yang sama:
- **Gejala**: CPU JIT compiler beralih dari *Monomorphic Inline Caching* (1 tipe target) $\rightarrow$ *Bimorphic* (2 tipe) $\rightarrow$ *Megamorphic* ($>2$ tipe).
- **Dampak**: JIT menonaktifkan *inlining* dan beralih ke dynamic table lookup (`invokeinterface`), menurunkan throughput instruksi CPU hingga 400%.
- **Troubleshooting**: Identifikasi megamorphic calls menggunakan JVM diagnostic tools:
  ```bash
  java -XX:+PrintCompilation -XX:+UnlockDiagnosticVMOptions -XX:+PrintInlining ...
  ```
  Mitigasi dengan menggunakan pola *Sealed Trait* yang diproses via pattern matching bertingkat atau kompilasi bertipe *monomorphic value wrappers*.

#### 10.3. Thread Starvation pada ExecutionContext.global
- **Gejala**: Aplikasi web atau microservice tiba-tiba berhenti merespons permintaan masuk (hang total) padahal utilisasi CPU tercatat rendah ($<10\%$).
- **Akar Masalah**: Penggunaan pemanggilan sinkronus terblokir (`Thread.sleep()`, synchronous HTTP call, JDBC tanpa connection pool non-blocking) di dalam `scala.concurrent.Future` yang memanfaatkan `ExecutionContext.global`.
- **Troubleshooting & Deteksi**:
  Ambil thread dump instan menggunakan CLI:
  ```bash
  jcmd <PID> Thread.print
  ```
  Periksa state dari thread `scala-execution-context-global-*`. Jika mayoritas berstatus `TIMED_WAITING` atau `WAITING` pada `java.util.concurrent.ForkJoinPool.scan`, sistem mengalami starvation.
- **Solusi**: Pindahkan operasi tersebut secara mutlak ke pool dedicated I/O yang menggunakan *Bounded Elastic ThreadPool*.

---

### 11. Best Practices (Production Checklist)

#### Compiler Configuration Flag (.sbt)
Aktifkan proteksi ketat tingkat compiler pada file `build.sbt`:
```scala
scalacOptions ++= Seq(
  "-deprecation",
  "-explain",                  // Penjelasan detail untuk error sistem tipe
  "-feature",
  "-unchecked",
  "-Werror",                   // Mengubah seluruh warning menjadi error fatal
  "-Wunused:all",              // Deteksi import, parameter, dan val yang tidak digunakan
  "-source:future",            // Mempersiapkan kompatibilitas fitur masa depan
  "-Xmacro-settings:materialize-lazy-vals"
)
```

#### Production Architecture Verification Checklist
- [ ] **Type Boundaries**: Semua domain identifiers primitif (misal: ID transaksi, Account ID) wajib dienkapsulasi menggunakan `opaque type` untuk mengeliminasi alokasi heap objek.
- [ ] **Thread Segregation**: `ExecutionContext.global` **DILARANG KERAS** digunakan untuk memproses operasi I/O jaringan, JDBC database, atau file processing.
- [ ] **Recursion Defense**: Seluruh algoritma rekursi wajib dianotasi dengan `@annotation.tailrec` untuk memvalidasi transformasi menjadi loop iterative pada level bytecode dan mencegah `StackOverflowError`.
- [ ] **No Reflection in Hot Paths**: Hindari `scala.reflect` atau Java runtime reflection pada core path. Gunakan Scala 3 *Inline Metaprogramming* atau typeclasses jika diperlukan inspeksi tipe.
- [ ] **Resource Safety**: Gunakan pattern RAII (seperti `scala.util.Using`) atau functional resource management untuk memanipulasi file stream dan koneksi soket agar kebocoran file descriptor JVM dapat dicegah secara deterministik.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun modul engine order matching yang menguji zero-cost abstraction dan mengisolasi thread execution pool secara presisi.

#### Langkah 1: Inisialisasi Struktur Proyek
Buat direktori baru di lingkungan lokal Anda untuk modul ini:
```bash
mkdir -p hands-on/m02/src/main/scala/engine
mkdir -p hands-on/m02/project
```

Buat file konfigurasi build `hands-on/m02/build.sbt`:
```scala
ThisBuild / scalaVersion := "3.3.3"
ThisBuild / version      := "0.1.0-SNAPSHOT"
ThisBuild / organization := "enterprise.arch"

lazy val root = (project in file("."))
  .settings(
    name := "engine-internals-m02",
    scalacOptions ++= Seq(
      "-deprecation",
      "-Xfatal-warnings",
      "-encoding", "UTF-8"
    ),
    libraryDependencies ++= Seq(
      "org.scalameta" %% "munit" % "1.0.0" % Test
    )
  )
```

Buat file plugin `hands-on/m02/project/build.properties`:
```properties
sbt.version=1.9.9
```

#### Langkah 2: Implementasi Domain Zero-Cost Abstraction
Buat file `hands-on/m02/src/main/scala/engine/Domain.scala`:
```scala
package engine

object Domain:
  opaque type Price = Long
  object Price:
    def apply(cents: Long): Either[String, Price] =
      if cents >= 0 then Right(cents) else Left("Price cannot be negative")
    def unsafe(cents: Long): Price = cents

  extension (p: Price)
    def toLong: Long = p
    def +(other: Price): Price = p + other

  opaque type Quantity = Int
  object Quantity:
    def apply(units: Int): Either[String, Quantity] =
      if units > 0 then Right(units) else Left("Quantity must be positive")
    def unsafe(units: Int): Quantity = units

  extension (q: Quantity)
    def toInt: Int = q

  case class Order(
    orderId: String,
    price: Price,
    quantity: Quantity,
    timestamp: Long
  )
```

#### Langkah 3: Implementasi Isolasi Concurrency Engine
Buat file `hands-on/m02/src/main/scala/engine/OrderProcessingEngine.scala`:
```scala
package engine

import scala.concurrent.{ExecutionContext, Future, blocking}
import java.util.concurrent.{Executors, ThreadFactory}
import java.util.concurrent.atomic.AtomicLong
import engine.Domain.*

object OrderProcessingEngine:

  // Isolasi Pool: Thread CPU-bound murni
  val matchingPool: ExecutionContext = ExecutionContext.fromExecutor(
    Executors.newFixedThreadPool(
      Runtime.getRuntime.availableProcessors(),
      new ThreadFactory {
        private val count = new AtomicLong(0)
        def newThread(r: Runnable): Thread =
          val t = new Thread(r, s"matching-core-${count.incrementAndGet()}")
          t.setPriority(Thread.MAX_PRIORITY)
          t
      }
    )
  )

  // Isolasi Pool: Thread Audit/Storage I/O
  val persistencePool: ExecutionContext = ExecutionContext.fromExecutor(
    Executors.newCachedThreadPool(
      new ThreadFactory {
        private val count = new AtomicLong(0)
        def newThread(r: Runnable): Thread =
          new Thread(r, s"persistence-io-${count.incrementAndGet()}")
      }
    )
  )

  def matchOrder(order: Order)(using ec: ExecutionContext): Future[String] = Future {
    // Memproses di CPU matching thread
    val threadName = Thread.currentThread().getName
    s"Order ${order.orderId} executed at Price: ${order.price.toLong} on thread [$threadName]"
  }

  def persistAuditLog(logPayload: String)(using ioEc: ExecutionContext): Future[Unit] = Future {
    blocking {
      // Memproses di IO persistence thread
      val threadName = Thread.currentThread().getName
      println(s"Writing to storage: '$logPayload' on thread [$threadName]")
      Thread.sleep(10) // Emulasi latency I/O
    }
  }(ioEc)
```

#### Langkah 4: Implementasi Main Runner
Buat file `hands-on/m02/src/main/scala/engine/Main.scala`:
```scala
package engine

import engine.Domain.*
import scala.concurrent.Await
import scala.concurrent.duration.*

@main def runEnterpriseApp(): Unit =
  println("Starting Engine...")

  given ExecutionContext = OrderProcessingEngine.matchingPool
  val ioContext = OrderProcessingEngine.persistencePool

  val p = Price.unsafe(15000L)
  val q = Quantity.unsafe(100)
  val order = Order("TX-9901", p, q, System.currentTimeMillis())

  val processFlow = for
    matchResult <- OrderProcessingEngine.matchOrder(order)
    _           <- OrderProcessingEngine.persistAuditLog(matchResult)(using ioContext)
  yield matchResult

  val result = Await.result(processFlow, 5.seconds)
  println(s"Flow completed: $result")
```

#### Langkah 5: Eksekusi dan Verifikasi Bytecode
Jalankan aplikasi dari direktori `hands-on/m02`:
```bash
sbt run
```
Verifikasi bahwa thread yang memproses order adalah `matching-core-*`, sedangkan thread penulisan log adalah `persistence-io-*`.

Selanjutnya, bedah bytecode yang dihasilkan compiler untuk membuktikan *zero-cost abstraction* pada `Price`:
```bash
javap -c target/scala-3.3.3/classes/engine/Domain\$Order.class
```
*Pastikan bahwa tipe field `price` pada class file tersebut adalah `long` primitif dan `quantity` adalah `int` primitif.*

---

### 13. Exercise

#### Level: Easy
1. Modifikasi file `Domain.scala` pada latihan Hands-on untuk menambahkan `opaque type Timestamp = Long`.
2. Sediakan extension method `.formatIso: String` yang mengubah epoch millis ke representasi format waktu ISO-8601 tanpa memicu alokasi class baru selain objek `java.lang.String` hasil format.
3. Tulis unit test untuk memvalidasi bahwa nilai negatif ditolak oleh smart constructor-nya.

#### Level: Medium
1. Buat custom typeclass `FastSerializer[T]` yang memiliki method `def serialize(entity: T): Array[Byte]`.
2. Sediakan instance `FastSerializer` untuk tipe `Domain.Order` yang mengubah data menjadi representasi biner kompak (bukan JSON/teks) menggunakan `java.nio.ByteBuffer` untuk meminimalisasi penggunaan memori.
3. Buktikan melalui test bahwa pemanggilan `.serialize` pada `Order` menggunakan context bound `[T: FastSerializer]` tidak memicu Java reflection.

#### Level: Hard
1. Implementasikan sebuah bounded *In-Memory Asynchronous Job Queue* bebas alokasi dinamis.
2. Gunakan `java.util.concurrent.atomic.AtomicReferenceArray` untuk underlying buffer storage.
3. Queue tersebut harus menerima operasi `offer(item)` dan `poll()` dengan memanfaatkan extension methods berbasis `opaque type JobSlot = Long`.
4. Mekanisme pooling wajib terisolasi dari *global execution context* dan tidak boleh menyebabkan alokasi closure runtime saat mengeksekusi worker loop. Pastikan verifikasi terhindar dari *busy-spinning* yang membakar 100% CPU via back-off strategy terukur.

---

### 14. Challenge

**Skenario**:
Anda ditunjuk sebagai Principal Architect pada startup pembayaran digital yang mengalami degradasi performa akut pada core event ledger mereka saat event peak-sale (11.11).

**Target Arsitektur**:
Rancang dan bangun implementasi arsitektur **Zero-Allocation Multi-Tenant In-Memory Ledger Router** dengan kriteria mutlak:
1. **Zero-Boxing Isolation**: Seluruh identifikasi entitas (TenantId, AccountId, Amount, CurrencyCode) harus berupa `opaque types`. Representasi internal `CurrencyCode` harus berupa `Int` primitif (ISO-4217 numeric code) namun terekspos secara eksternal sebagai type-safe token.
2. **Contextual Implicits Engine**: Rancang hierarki typeclass validation pipeline yang memverifikasi transaksi debit/kredit secara compile-time based routing. Validasi tenant premium dan tenant reguler harus dibedakan secara otomatis menggunakan Scala 3 *Given Resolution Specificity Rules* tanpa *if-else runtime inspection*.
3. **Execution Safety**: Bangun sebuah `DeterministicTaskScheduler` yang menjamin starvation-free execution saat memproses ribuan event masuk secara asinkron. Jika proses mutasi ledger mengalami delay, ia harus mendegradasi ke disk-spill buffer tanpa pernah memblokir thread engine utama.
4. **Verifikasi Teknis**: Sediakan script benchmark atau output `javap -c` yang membuktikan bahwa tidak ada alokasi boxing primitif di dalam inner transaction loop.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda / Konseptual Singkat)
1. **Apa perbedaan mendasar antara `AnyVal` (Value Class) di Scala 2 dan `opaque type` di Scala 3 pada level bytecode JVM?**
   - *Jawaban*: `AnyVal` masih melakukan boxing (mengalokasikan objek baru di heap) ketika digunakan dalam konteks generik, array, atau saat di-cast ke interface/trait. `opaque type` murni dihapus (*erased*) menjadi underlying type primitif/dasarnya pada seluruh skenario bytecode tanpa alokasi wrapper tambahan.

2. **Kapan JVM mengeksekusi method trait sebagai `invokevirtual` dibanding `invokeinterface`?**
   - *Jawaban*: `invokeinterface` digunakan saat runtime reference dideklarasikan sebagai interface/trait. Jika class konkret di-resolve secara final dan monomorphic oleh JIT C2 compiler, instruksi tersebut dapat didevirtualisasi menjadi direct call atau di-inline langsung.

3. **Apa kegunaan anotasi `@annotation.tailrec` pada fungsi rekursif Scala?**
   - *Jawaban*: Memaksa compiler memverifikasi bahwa fungsi tersebut benar-benar *tail-recursive*. Jika ya, compiler mengubahnya menjadi loop iteratif biasa (instruksi `goto`/jump pada bytecode) untuk mencegah penggunaan stack frame berlebih (`StackOverflowError`). Jika bukan tail-recursion, kompilasi akan gagal (*compile error*).

4. **Apa yang terjadi jika kita memanggil blocking I/O di dalam thread pool yang bertipe `ForkJoinPool`?**
   - *Jawaban*: Thread worker akan terblokir pada kernel level. Karena `ForkJoinPool` dirancang untuk komputasi CPU paralel dengan jumlah thread terbatas (biasanya sejumlah CPU core), blocking call yang masif akan mengakibatkan *thread starvation*, membuat tugas-tugas non-blocking lainnya tertunda tanpa dapat diproses.

5. **Apa fungsi dari file biner `.tasty` yang dihasilkan oleh Scala 3 compiler?**
   - *Jawaban*: TASTy (*Typed Abstract Syntax Trees*) menyimpan seluruh informasi struktur kode dan sistem tipe Scala sebelum fase *type erasure*. Ini memungkinkan *cross-version compatibility*, advanced macro inspection, dan dekompilasi tipe secara utuh lintas project dependencies.

#### Bagian 2: Intermediate (Analisis Kasus Singkat)
6. **Perhatikan kode berikut. Apakah kode ini memicu alokasi heap baru saat dipanggil? Jelaskan.**
   ```scala
   opaque type Volume = Double
   object Volume:
     def apply(v: Double): Volume = v
   def calculate(volumes: List[Volume]): Double = volumes.map(v => v).sum
   ```
   - *Jawaban*: Ya. Meskipun `Volume` adalah opaque type yang merepresentasikan `Double`, penggunaannya di dalam `List[Volume]` memicu alokasi karena `List` pada JVM bersifat generic (`List[Object]`). JVM melakukan autoboxing dari `double` primitif menjadi `java.lang.Double` agar dapat masuk ke dalam struktur koleksi generic tersebut.

7. **Mengapa Scala 3 melarang deklarasi `given` dengan tipe kembalian yang sama dan prioritas leksikal yang identik? Apa mekanisme compiler untuk memutus ambiguitas tersebut?**
   - *Jawaban*: Untuk menghindari *ambiguous implicit resolution error*. Kompiler menggunakan *Specificity Rules*: jika salah satu instance adalah subtype dari instance yang lain, compiler akan memilih yang paling spesifik. Jika derajat spesifisitasnya sama persis, kompilasi dihentikan dengan error agar integritas program tetap deterministik.

8. **Bagaimana cara kerja keyword `blocking` dari package `scala.concurrent` saat digunakan di dalam `ExecutionContext.global`?**
   - *Jawaban*: Konstruksi `blocking { ... }` mengirimkan sinyal ke `ForkJoinPool` (jika underlying pool-nya adalah `ForkJoinPool` yang mendukung `ManagedBlocker`). Pool akan secara sementara menginstansiasi worker thread baru (*compensation thread*) untuk menggantikan thread yang sedang terblokir, menjaga level paralelisme CPU tetap optimal.

9. **Mengapa penulisan `def` pada implementasi typeclass instance (`given ... with`) dapat menurunkan throughput aplikasi dibanding penulisan `lazy val` atau `val`?**
   - *Jawaban*: Jika typeclass instance didefinisikan dengan instansiasi objek anonim baru di dalam `def`, setiap kali compiler membutuhkan instance tersebut melalui parameter `using`, JVM akan mengalokasikan objek baru di heap. Menggunakan `val` atau object-based `given` menjamin instansiasi singleton yang dapat dipakai berulang kali (*zero allocation reuse*).

10. **Apa dampak performa dari penggunaan instruksi Java/Scala Reflection (`TypeTag`, `Class.forName()`) di dalam core execution path?**
    - *Jawaban*: Melompati optimasi compiler dan JIT. Operasi refleksi tidak dapat di-inline, memaksa JVM melewati jalur interpretasi yang lambat, bypass CPU cache L1/L2, memicu alokasi array argumen sementara, dan rentan terhadap kegagalan runtime jika terjadi restrukturisasi nama package/class.

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Sebuah microservice analitik memproses stream metrik menggunakan `scala.concurrent.Future`. Di jam sibuk, memory heap stabil di angka $30\%$, utilisasi CPU di angka $15\%$, tetapi antrean HTTP request timeout meledak hingga $80\%$. Analisis thread dump menunjukkan 16 thread dari `ForkJoinPool.commonPool-worker-*` berstatus `WAITING` pada pemanggilan socket driver Elasticsearch. Bagaimana langkah perbaikan arsitektural totalnya?
    - *Solusi Ringkas*: Migrasikan pemanggilan driver Elasticsearch ke I/O dedicated pool menggunakan `ThreadPoolExecutor` bounded elastis. Bungkus blok pemanggilan menggunakan `Future { ... }(ioExecutionContext)`. Gunakan driver Elasticsearch yang asinkron non-blocking (berbasis Netty) alih-alih driver sinkronus untuk melepaskan ketergantungan pada worker thread pool.

12. **Skenario 2**: Dalam sebuah core high-frequency trading platform, Anda mendapati latensi method kalkulasi matriks risiko melonjak saat jumlah aset bertambah dari 2 menjadi 5 variasi implementasi trait `RiskModel`. Profiler menunjukkan method `calculate()` pada trait tersebut berubah status dari *Inlined* menjadi *Megamorphic Virtual Call*. Bagaimana Anda mendesain ulang trait tersebut di Scala 3 agar kembali monomorphic atau dapat di-inline oleh compiler?
    - *Solusi Ringkas*: Hilangkan polimorfisme runtime berbasis subtype inheritance (`trait RiskModel`). Ganti dengan arsitektur berbasis *Typeclass Pattern* dengan parameter tipe statis (`def calculate[M: RiskModel](model: M)`), atau gunakan representasi `enum` bertipe tertutup (ADTs) yang dievaluasi menggunakan `@switch` / exhaustive pattern matching. Hal ini memungkinkan compiler dan JIT memetakan pemanggilan secara direct/table-jump tanpa dynamic interface dispatching.

13. **Skenario 3**: Sebuah backend fintech melaporkan kebocoran memori (*Heap OutOfMemoryError*) bertahap setelah berjalan 3 hari tanpa restart. Heap dump membuktikan adanya retensi jutaan instance `TransactionAuditLogger` yang tertahan di memori. Padahal class tersebut hanya dipanggil sekali pada alur login user melalui closure lambda:
    ```scala
    class TransactionAuditLogger(val bigMetadata: Map[String, String]):
      def log(): Unit = ...
      def registerListener(bus: EventBus): Unit =
        bus.subscribe(event => { log(); println(event.id) })
    ```
    Jelaskan mekanisme kebocoran memori tersebut dan tuliskan baris perbaikannya!
    - *Solusi Ringkas*:
      - *Penyebab*: Lambda `event => { log(); println(event.id) }` menangkap referensi eksplisit ke method `log()`. Pada bytecode level, ini berarti lambda menyimpan pointer langsung ke objek enclosing `this` (`TransactionAuditLogger`), yang pada gilirannya menahan `bigMetadata`. Selama `EventBus` menyimpan listener tersebut, seluruh instance `TransactionAuditLogger` tidak dapat dibersihkan oleh Garbage Collector.
      - *Perbaikan*: Putus referensi `this` dengan mengekstrak dependensi yang murni dibutuhkan ke local value:
        ```scala
        def registerListener(bus: EventBus): Unit =
          // Hanya mereferensikan fungsi/nilai lepas tanpa referensi kelas pembungkus
          val loggerFn: () => Unit = () => this.log() 
          // Atau lebih baik, buat method statis di companion object:
          TransactionAuditLogger.subscribeStatic(bus, this.log)
        ```

---

### 16. Summary

1. **Jembatan Scala-to-Bytecode**: Scala 3 mengeksekusi abstraksi tingkat tinggi di atas JVM melalui transformasi cerdas seperti trait default methods, name mangling, and synthetic bridge methods. Pemahaman terhadap bytecode (`javap`) krusial untuk mencegah degradasi performa pada sistem berskala masif.
2. **Zero-Cost Abstractions**: Penggunaan `opaque type` menggantikan `AnyVal` sebagai solusi pamungkas dalam memodelkan domain yang type-safe tanpa penalti alokasi heap (*zero runtime overhead*).
3. **Contextual Engine Deterministik**: Sistem `given` dan `using` di Scala 3 menyediakan sarana modular untuk *ad-hoc polymorphism* (Typeclass) yang sepenuhnya diselesaikan secara deterministik pada saat kompilasi (*compile-time resolution*).
4. **Isolasi Concurrency Mutlak**: Performa tinggi pada JVM menuntut pemisahan mutlak antara komputasi murni CPU-bound (`ForkJoinPool`) dan blocking I/O bound execution (`Bounded ThreadPoolExecutor`) guna mengeliminasi bencana *thread pool starvation*.
5. **Mechanical Sympathy**: Selalu rancang arsitektur perangkat lunak dengan menghormati karakteristik internal JVM (JIT Inlining, Devirtualization, GC Generation cycles, and CPU Cache line behavior). Hindari closure memory leaks dan megamorphic call sites di hot-paths produksi.