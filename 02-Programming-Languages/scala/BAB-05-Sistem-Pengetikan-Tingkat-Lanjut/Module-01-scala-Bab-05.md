# Bab 05 Module 01: Sistem Pengetikan Tingkat Lanjut (Advanced Type Systems)

---

## SEKSI 01 — IDENTITAS MODUL

*   **Kurikulum:** Pemrograman Scala Tingkat Lanjut (Scala 3 Engine)
*   **Kategori:** 02-Programming-Languages
*   **Bab:** 05 — Advanced Type System & Metaprogramming
*   **Modul:** 01 — Sistem Pengetikan Tingkat Lanjut
*   **Prasyarat:** Pemahaman mendalam mengenai Scala OOP Dasar, Functional Programming (Monads, Functors), Generics dasar (`T`), Pattern Matching, serta Contextual Abstractions (`given`, `using`).
*   **Target Audience:** Senior Software Engineer, Distributed Systems Engineer, Compiler/Language Enthusiast, dan Backend Architect.
*   **Perkiraan Durasi:** 120 Menit (Teori Mendalam) + 180 Menit (Implementasi Hands-On).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik mampu:
1.  **Mendekomposisi dan Mengonstruksi Higher-Kinded Types (HKT):** Mengabstraksikan struktur kontainer komputasional melampaui *proper types* (`* -> *`).
2.  **Menerapkan Variance dan Bounds Lanjutan:** Mengendalikan subtyping melalui kovarians (`+T`), kontravarians (`-T`), serta batasan tipe atas (*upper* `<:`), bawah (*lower* `>:`), dan konteks (*context bounds* `: F`).
3.  **Memanfaatkan Path-Dependent Types dan Generalized Type Constraints:** Mendesain dependensi kontraktual antar-objek dan menegakkan bukti formal kesamaan tipe (`=:=`, `<:<`).
4.  **Merancang Match Types dan Type-Level Computation:** Menjalankan manipulasi dan reduksi tipe komputasional pada fase kompilasi menggunakan mesin reduksi tipe Scala 3.
5.  **Membangun Pola Desain Type-Safe Berbasis Bukti Matematis:** Mengimplementasikan *Phantom Types* dan *Type-Level State Machine* untuk memvalidasi transisi state sistem terdistribusi tanpa runtime overhead.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam sistem pengetikan dasar, tipe data dipandang semata-mata sebagai klasifikasi ukuran memori runtime (contoh: `Int` adalah 32-bit integer, `String` adalah pointer heap). 

Dalam **Sistem Pengetikan Tingkat Lanjut (Advanced Type Systems)**, mental model harus bergeser:
> **"Tipe adalah Proposisi Logis, dan Eksekusi Program Kompiler adalah Pembuktian Teorema (Isomorfisme Curry-Howard)."**

```
+-----------------------------------------------------------+
|                      MENTAL SHIFT                         |
+-----------------------------+-----------------------------+
| PARADIGMA RUNTIME-CENTRIC   | PARADIGMA TYPE-LEVEL        |
+-----------------------------+-----------------------------+
| Mengecek error saat runtime | Mengeliminasi status error  |
| via validasi `if-else`      | dari kemungkinan kompilasi  |
+-----------------------------+-----------------------------+
| Tipe sebagai cetak biru     | Tipe sebagai parameter data |
| struktur objek memori       | komputasi bagi kompilator   |
+-----------------------------+-----------------------------+
| Data dimanipulasi oleh CPU  | Tipe ditransformasi oleh    |
| (Register/ALU)              | Mesin Reduksi Tipe Dotty    |
+-----------------------------+-----------------------------+
```

Anda bukan lagi hanya menulis instruksi mesin; Anda sedang merancang **sistem kendala (*constraint system*)** di mana kompiler Scala (`scalac`) bertindak sebagai *automated theorem prover*. Jika arsitektur tipe Anda terbukti valid secara matematis pada saat kompilasi, Anda mendapatkan garansi mutlak bahwa kegagalan kelas tertentu (seperti deserialisasi yang tidak cocok, eksekusi state transaksi ilegal, atau regresi mutasi data) tidak akan pernah terjadi pada fase runtime.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Proses reduksi tipe, verifikasi varians, dan substitusi tipe Scala 3 (Dotty Compiler Pipeline):

```
                     Source Code (.scala)
                              |
                              v
                 +--------------------------+
                 |       Parser (AST)       |
                 +--------------------------+
                              |
                              v
                 +--------------------------+
                 |          Typer           |
                 |  - Menentukan Jenis Tipe |
                 |  - Inferensi Tipe        |
                 +--------------------------+
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
+--------------------------+      +--------------------------+
|  Match Type Normalizer   |      | Subtyping & Bounds Check |
| - Unfold Recursive Types |      | - Lower/Upper (<:, >:)   |
| - Evaluate Patterns      |      | - Variance (+, -) Rules  |
| - Resolusi Type Lambdas  |      | - Path-Dependent Check   |
+--------------------------+      +--------------------------+
             |                                 |
             +----------------+----------------+
                              |
                              v
                 +--------------------------+
                 | Erasure & Transformation |
                 |  (Tipe Abstrak Dihapus   |
                 |   Menjadi JVM Bounds)    |
                 +--------------------------+
                              |
                              v
                     JVM Bytecode (.class)
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Higher-Kinded Types (HKT) dan Type Constructors
Tipe memiliki "derajat" (*kind*). 
*   *Proper Type* (Level 0, dilambangkan `*`): Tipe yang dapat langsung diinstansiasi menjadi nilai runtime (misal: `Int`, `String`).
*   *First-Order Type Constructor* (Level 1, dilambangkan `* -> *`): Tipe yang membutuhkan satu argumen *proper type* untuk menghasilkan *proper type* lain (misal: `List[_]`, `Option[_]`).
*   *Higher-Kinded Type* (Level 2+, misal: `(* -> *) -> *`): Konstruktor tipe yang menerima konstruktor tipe lain sebagai parameternya (misal: `Functor[F[_]]`).

### 2. Variance (Subtyping Rigor)
Variance mendikte bagaimana hubungan subtipe antara komponen memengaruhi hubungan subtipe antara kontainer pembungkusnya:
*   **Kovarian (`+T`):** Jika `Sub <: Super`, maka `Container[Sub] <: Container[Super]`. Karakteristik: Tipe hanya boleh berada di posisi output (*Producer / Return type*).
*   **Kontravarian (`-T`):** Jika `Sub <: Super`, maka `Container[Super] <: Container[Sub]`. Karakteristik: Tipe hanya boleh berada di posisi input (*Consumer / Parameter type*).
*   **Invarian (`T`):** Tidak ada hubungan subtyping antara `Container[Sub]` dan `Container[Super]`. Karakteristik: Tipe muncul pada posisi input sekaligus output.

### 3. Path-Dependent Types
Pada Scala, tipe dapat berakar pada sebuah instance nilai (*value instance*). Jika didefinisikan sebuah kelas `outer.Inner`, maka tipe `val a: Outer` dan `val b: Outer` menghasilkan dua tipe inner independen: `a.Inner` bukanlah `b.Inner`. Hubungan ini dipertahankan secara ketat oleh typer kompilator.

### 4. Type Erasure pada JVM
Mesin Virtual Java (JVM) tidak memiliki konsep native mengenai generics atau higher-kinded types. Semua parameter tipe diabstraksikan via proses **Type Erasure**.
*   `List[Int]` dan `List[String]` keduanya menjadi `List` mentah (*raw type*) di level bytecode.
*   Batas atas (*upper bound*) menjadi representasi bytecode (misal: `[T <: CharSequence]` di-erase menjadi `CharSequence`, sedangkan `[T]` tanpa bound di-erase menjadi `Object`).
*   Oleh karena itu, operasi seperti `o.isInstanceOf[F[A]]` dilarang oleh compiler tanpa manifest runtime atau `TypeTest`/`Typeable`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Higher-Kinded Types & Type Lambdas
Pada Scala 2, mendefinisikan transformasi tipe parsial memerlukan trik "Type Projection" (`({type L[A] = Map[String, A]})#L`). Di Scala 3, Type Lambdas didukung secara native menggunakan sintaks fungsional `[X] =>> ...`.

```scala
// Type constructor menerima satu parameter tipe
type ListOf[X] = List[X]

// Type Lambda: Mengubah tipe aritas-2 (Map[K, V]) menjadi aritas-1
type StringMap = [V] =>> Map[String, V]
```

### Match Types
Scala 3 memperkenalkan kalkulus reduksi tipe secara deklaratif langsung pada level tipe:

```scala
type Elem[X] = X match
  case String      => Char
  case Array[t]    => t
  case Iterable[t] => t
  case AnyVal      => X
```
Kompiler Dotty akan mengevaluasi dependensi ini selama kompilasi. Jika argumen input diketahui secara konkrit pada saat pemanggilan, tipe output otomatis tereduksi secara identik tanpa kebutuhan boxing maupun casting runtime.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah kode dasar komprehensif yang mendemonstrasikan:
1. Higher-Kinded Type abstraction (`Functor`).
2. Type Lambda.
3. Path-Dependent Type.
4. Match Type dengan pembuktian tipe.

```scala
// File: AdvancedTypeFundamentals.scala
package advanced.types

// 1. Higher-Kinded Type Definition
trait Functor[F[_]]:
  def map[A, B](fa: F[A])(f: A => B): F[B]

object Functor:
  // Instansiasi Functor untuk List
  given Functor[List] with
    def map[A, B](fa: List[A])(f: A => B): List[B] = fa.map(f)

  // Instansiasi Functor untuk Map dengan Type Lambda: [X] =>> Map[Key, X]
  given [K]: Functor[[X] =>> Map[K, X]] with
    def map[A, B](fa: Map[K, A])(f: A => B): Map[K, B] =
      fa.view.mapValues(f).toMap

// 2. Path-Dependent Types
class KeyManager:
  trait Key:
    def id: String
  class DatabaseKey(val id: String) extends Key
  class ApiKey(val id: String) extends Key

  def spawnKey(raw: String): DatabaseKey = new DatabaseKey(raw)
  def verifyKey(key: this.Key): Boolean = key.id.nonEmpty

// 3. Match Types (Type-Level Reduction)
type Flatten[T] = T match
  case List[List[sub]] => List[sub]
  case List[sub]       => List[sub]
  case Option[Option[sub]] => Option[sub]
  case _               => T

object MatchTypeDemo:
  def smartUnbox[T](item: T): Flatten[T] = item match
    case l: List[?] =>
      l.flatMap {
        case inner: List[?] => inner
        case other => List(other)
      }.asInstanceOf[Flatten[T]]
    case opt: Option[?] =>
      opt.flatMap {
        case inner: Option[?] => inner
        case other => Some(other)
      }.asInstanceOf[Flatten[T]]
    case other => other.asInstanceOf[Flatten[T]]
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah analisis mendalam terhadap kode pada SEKSI 07:

*   **`trait Functor[F[_]]`**: Mendefinisikan HKT. Argumen `F[_]` menandakan bahwa `F` adalah konstruktor tipe yang membutuhkan 1 tipe generik (misal: `Option`, `List`). Ia bukan *proper type*.
*   **`given [K]: Functor[[X] =>> Map[K, X]] with`**: Menggunakan *Type Lambda*. Kompiler mengunci parameter pertama `Map` ke `K`, menyisakan `X` sebagai parameter bebas. Struktur baru ini memiliki *kind* `* -> *`, sehingga memenuhi kriteria `F[_]`.
*   **`def verifyKey(key: this.Key): Boolean`**: Path-dependent typing. Tipe `this.Key` terikat secara lokal pada instans `KeyManager` pemanggil. Dua instans berbeda, `km1` dan `km2`, memiliki tipe `km1.Key` dan `km2.Key` yang inkompatibel secara biner pada level kompilasi.
*   **`type Flatten[T] = T match ...`**: Pendefinisian Match Type. Pola diuraikan dari atas ke bawah:
    *   Jika `T` adalah `List[List[sub]]`, tipe direduksi menjadi `List[sub]`.
    *   Kompiler mengekstrak tipe `sub` melalui inferensi pola tipe (*existential binding*).
*   **`.asInstanceOf[Flatten[T]]`**: Dibutuhkan pada batas implementasi metode runtime karena *type erasure* menghapus informasi tipe generik internal, tetapi output pemanggil publik dijamin 100% type-safe oleh tanda tangan metode.

---

## SEKSI 09 — STUDI KASUS NYATA: PIPELINE SETTLEMENT FINTECH

Dalam ekosistem pemrosesan transaksi perbankan berisiko tinggi, terdapat aturan ketat:
1. Sebuah transaksi settlement **hanya boleh** dieksekusi jika telah melalui tahapan verifikasi berurutan: `Initialized` $\rightarrow$ `RiskAssessed` $\rightarrow$ `Authorized`.
2. Mata uang (*Currency*) harus divalidasi pada level tipe untuk mencegah kecelakaan komputasi beda valuta asing (FX) tanpa konversi resmi.
3. Alur audit harus mengembalikan laporan rekonsiliasi yang formatnya ditentukan oleh *tipe instrumen pembayaran* (seperti `SEPA`, `SWIFT`, atau `InternalLedger`) pada saat kompilasi tanpa dynamic reflection.

Kegagalan menerapkan aturan di atas pada fase kompilasi membuka celah bug runtime fatal: transaksi settlement dapat terpicu tanpa mitigasi risiko, berujung pada kerugian finansial.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Di bawah ini adalah implementasi sistem settlement FinTech berskala produksi menggunakan kombinasi **Phantom Types**, **Path-Dependent State Tokens**, **Match Types**, dan **Generalized Type Constraints**.

```scala
// File: SettlementEngine.scala
package fintech.settlement

import scala.annotation.implicitNotFound

// --- 1. PHANTOM TYPES UNTUK STATE TRANSAKSI ---
sealed trait SettlementState
sealed trait Initialized  extends SettlementState
sealed trait RiskAssessed extends SettlementState
sealed trait Authorized   extends SettlementState

// --- 2. TYPED CURRENCIES & TOKENS ---
sealed trait Currency
sealed trait IDR extends Currency
sealed trait USD extends Currency

final case class Money[C <: Currency](amount: BigDecimal)

// --- 3. METRICS MAPPING VIA MATCH TYPE ---
sealed trait SettlementRail
trait LocalRTGS extends SettlementRail
trait CrossBorderSWIFT extends SettlementRail

type RailReport[R <: SettlementRail] = R match
  case LocalRTGS          => FastSettlementReceipt
  case CrossBorderSWIFT   => SwiftClearingReport

final case class FastSettlementReceipt(refId: String, clearingWindowMs: Long)
final case class SwiftClearingReport(refId: String, intermediaryBic: String, chargesBorneBy: String)

// --- 4. ENGINE DENGAN PHANTOM TYPING & COMPILE-TIME GUARDS ---
final class Transaction[C <: Currency, S <: SettlementState] private (
  val id: String,
  val amount: Money[C],
  val auditLog: Vector[String]
):
  // Helper internal untuk transisi state tanpa alokasi payload baru
  private[settlement] def transition[NextState <: SettlementState](logMessage: String): Transaction[C, NextState] =
    new Transaction[C, NextState](this.id, this.amount, this.auditLog :+ logMessage)

object Transaction:
  // Entry point: Transaksi hanya bisa dibuat dalam status Initialized
  def initiate[C <: Currency](id: String, amount: Money[C]): Transaction[C, Initialized] =
    new Transaction[C, Initialized](id, amount, Vector(s"Transaction $id initiated."))

// Service pemrosesan state
object SettlementWorkflow:

  // Batasan hanya dapat dipanggil jika state = Initialized
  def assessRisk[C <: Currency](tx: Transaction[C, Initialized])(using
    ev: tx.type <:< Transaction[C, Initialized]
  ): Transaction[C, RiskAssessed] =
    println(s"Evaluating credit & AML risk for TX: ${tx.id}")
    tx.transition[RiskAssessed]("AML Risk Assessed: PASSED")

  // Batasan hanya dapat dipanggil jika state = RiskAssessed
  def authorize[C <: Currency](tx: Transaction[C, RiskAssessed]): Transaction[C, Authorized] =
    println(s"Securing cryptographic signatures for TX: ${tx.id}")
    tx.transition[Authorized]("Transaction Authorized by Signers")

  // Eksekusi settlement: Mengembalikan tipe spesifik berdasarkan Rail secara kompilatif
  def executeSettlement[C <: Currency, R <: SettlementRail](
    tx: Transaction[C, Authorized],
    rail: R
  ): RailReport[R] =
    println(s"Executing irrevocable settlement on TX: ${tx.id}")
    rail match
      case _: LocalRTGS =>
        FastSettlementReceipt(tx.id, clearingWindowMs = 250L).asInstanceOf[RailReport[R]]
      case _: CrossBorderSWIFT =>
        SwiftClearingReport(tx.id, intermediaryBic = "DEUTDEDDFXX", chargesBorneBy = "OUR").asInstanceOf[RailReport[R]]

// --- 5. EKSEKUSI RUNTIME DENGAN VALIDASI KOMPILASI ---
@main def runSettlementSystem(): Unit =
  val txInitial = Transaction.initiate[IDR]("TX-90210", Money[IDR](BigDecimal(50_000_000_000L)))
  
  // Transisi State yang Valid
  val txRiskChecked = SettlementWorkflow.assessRisk(txInitial)
  val txAuthorized  = SettlementWorkflow.authorize(txRiskChecked)
  
  // Settlement via LocalRTGS menghasilkan FastSettlementReceipt
  val localRail: LocalRTGS = new LocalRTGS {}
  val localReceipt: FastSettlementReceipt = SettlementWorkflow.executeSettlement(txAuthorized, localRail)
  println(s"Settlement Succeeded: RTGS Reference=${localReceipt.refId}, Window=${localReceipt.clearingWindowMs}ms")

  // Settlement via SWIFT menghasilkan SwiftClearingReport
  val swiftRail: CrossBorderSWIFT = new CrossBorderSWIFT {}
  val swiftReceipt: SwiftClearingReport = SettlementWorkflow.executeSettlement(txAuthorized, swiftRail)
  println(s"Settlement Succeeded: SWIFT Ref=${swiftReceipt.refId}, Intermediary=${swiftReceipt.intermediaryBic}")

  // =========================================================================
  // NEGATIVE COMPILE TESTS (Uncomment untuk membuktikan penolakan kompilator)
  // =========================================================================
  
  // ERROR 1: Mencoba authorize langsung dari Initialized (melompati RiskAssessed)
  // SettlementWorkflow.authorize(txInitial)
  // COMPILER ERROR: Type mismatch. Required: Transaction[IDR, RiskAssessed], Found: Transaction[IDR, Initialized]

  // ERROR 2: Mencoba mengeksekusi settlement pada state yang belum di-otorisasi
  // SettlementWorkflow.executeSettlement(txRiskChecked, localRail)
  // COMPILER ERROR: Type mismatch. Required: Transaction[C, Authorized], Found: Transaction[IDR, RiskAssessed]
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Menggunakan sistem pengetikan tingkat lanjut menuntut pertukaran arsitektural yang terukur:

```
+----------------------------+-----------------------------+-------------------------------+
| METRIK                     | SIMPLE RUNTIME VALIDATION   | ADVANCED TYPE CONSTRAINTS     |
+----------------------------+-----------------------------+-------------------------------+
| Waktu Kompilasi            | Cepat (~1x)                 | Signifikan lebih lama (~2-4x) |
| Readability Developer Baru | Sangat Rendah Kurva Belajar | Kurva Belajar Curam (Abstract)|
| Runtime Memory Overhead    | Sedang (Alokasi Validator)  | Sangat Nol (Zero Cost Abstr.) |
| Verifikasi State           | Probabilistik (Unit Testing)| Deterministik (Formal Proof)  |
| Debugging Failure          | Stack Trace Runtime         | Penolakan Kompiler (Compile)  |
+----------------------------+-----------------------------+-------------------------------+
```

### HKT vs Monomorphic vs Tagless Final

1.  **Monomorphic Execution (`Future[A]`, `IO[A]` eksplisit):**
    *   *Kelebihan:* Penelusuran trace kode sangat mudah dibaca; penanganan error gamblang.
    *   *Kekurangan:* Sulit di-mock dalam testing tanpa overhead jaringan aktual; keterikatan kuat pada satu runtime engine.
2.  **Higher-Kinded Polymorphism / Tagless Final (`F[_]`):**
    *   *Kelebihan:* Logika bisnis sepenuhnya agnostik terhadap runtime (`IO`, `Task`, `Id` untuk testing).
    *   *Kekurangan:* Pesan error compiler menjadi kompleks; membebani developer junior; waktu kompilasi bertambah drastis.
3.  **Match Types vs Subtyping Hierarchies:**
    *   *Match Types:* Menghindari kebutuhan polimorfisme dinamis (virtual method table lookup) pada level hierarki data ad-hoc. Namun, jika rekursi tipe terlalu dalam, kompilator dapat kehabisan stack (*type-level stack overflow*).

---

## SEKSI 12 — EDGE CASES & PITFALLS

1.  **Siklus Rekursi Tak Terbatas pada Match Types:**
    ```scala
    type InfiniteLoop[T] = T match
      case Int => InfiniteLoop[Int]
    
    // def crash(x: InfiniteLoop[Int]): Unit
    // Scalac Error: Recursion limit exceeded in match type reduction!
    ```
    *Mitigasi:* Selalu tentukan *base case* yang pasti terjangkau atau manfaatkan batas kedalaman rekursi menggunakan properti `-Xmax-inlines`.

2.  **Subtyping Contravariance Escape:**
    Varians bekerja berlawanan arah pada parameter input fungsi:
    ```scala
    trait Consumer[-T]:
      def consume(x: T): Unit
    
    // Secara matematis: jika Dog <: Animal, maka Consumer[Animal] <: Consumer[Dog]
    // Pitfall: Memberikan Consumer[Dog] di mana Consumer[Animal] diharapkan akan memicu compile error!
    ```

3.  **Erasure Collision:**
    Dua method dengan higher-kinded types dapat ter-erase menjadi signature JVM yang identik:
    ```scala
    def process(data: List[Int]): Unit = ()
    def process(data: List[String]): Unit = ()
    // Compiler Error: Double definition: have the same type after erasure: process(data: List): Unit
    ```
    *Solusi:* Gunakan *dummy implicits* (`using DummyImplicit`) atau Scala 3 `targetName` annotation.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Pelanggaran Posisi Varians (Variance Position Violations)
```scala
// SALAH: Tipe kovarian +A berada di posisi parameter (kontravarian)
trait BadQueue[+A]:
  def enqueue(item: A): BadQueue[A] // Compile Error: covariant type A occurs in contravariant position!

// BENAR: Menggunakan Lower Type Bound untuk melebarkan batas tipe
trait GoodQueue[+A]:
  def enqueue[B >: A](item: B): GoodQueue[B]
```

### 2. Mengabaikan Nilai Unsoundness pada Cast Match Types
```scala
// SALAH: Asumsi salah bahwa casting pasti tervalidasi pada runtime
def unsafeGet[T](v: Any): Flatten[T] = v.asInstanceOf[Flatten[T]] 
// Ini lolos kompilasi tetapi menghasilkan ClassCastException tak terlacak di kedalaman pipeline!

// BENAR: Pasangkan dengan scala.reflect.TypeTest atau pattern matching struktural nyata.
```

### 3. Over-Engineering Tanpa Keperluan Polimorfisme
Banyak engineer membungkus seluruh service dengan HKT `F[_]` padahal aplikasi hanya menggunakan arsitektur monolitik berbasis `Future` atau Cats Effect `IO`. Jangan gunakan HKT jika fleksibilitas efek komputasi jamak tidak diwajibkan oleh arsitektur sistem.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Anotasi Tipe Publik Eksplisit:**
    Jangan pernah membiarkan kompiler menginferensikan tipe publik dari fungsi yang menggunakan Match Types atau Higher-Kinded Types:
    ```scala
    // WAJIB: Anotasi publik jelas
    def reconcile[R <: SettlementRail](rail: R): RailReport[R] = ...
    ```
2.  **Desain Phantom Types Menggunakan Opaque Type Aliases atau Sealed Traits Kosong:**
    Pastikan *phantom traits* tidak dapat diinstansiasi secara bebas untuk menjaga integritas pembuktian:
    ```scala
    sealed trait ValidatedState extends Any
    // Hindari membuat case class untuk phantom type karena menghabiskan alokasi memori.
    ```
3.  **Gunakan Context Bounds untuk Keterbacaan HKT:**
    Daripada menulis `(using ev: Functor[F])`, gunakan syntax context bounds yang lebih ringkas:
    ```scala
    def traverseData[F[_]: Functor, A, B](fa: F[A])(f: A => B): F[B] =
      summon[Functor[F]].map(fa)(f)
    ```

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Zero-Cost Abstractions via Opaque Types
Gunakan Scala 3 `opaque type` alih-alih wrapper `AnyVal` untuk membungkus tipe primitif. `AnyVal` masih dapat mengalami boxing dalam skenario generik, array, atau pattern matching.

```scala
// Zero allocation overhead, murni diverifikasi saat kompilasi
object CoreBankingTypes:
  opaque type AccountId = String
  object AccountId:
    def apply(raw: String): AccountId = raw
  
  extension (id: AccountId)
    def value: String = id

// Di bytecode: 'AccountId' sepenuhnya adalah 'java.lang.String'. 
// 0 byte alokasi tambahan di Heap.
```

### Pemangkasan Beban Kompiler (`scalac` Tuning)
Type-level programming meningkatkan beban memori kompiler secara substansial.
Tambahkan flags berikut pada file `build.sbt` enterprise Anda:
```scala
scalacOptions ++= Seq(
  "-Xmax-inlines:64",          // Membatasi ekspansi match type/inline yang berlebihan
  "-Vprofile",                 // Profiling konsumsi memori dan fase kompilasi typechecker
  "-explain"                   // Menyediakan deskripsi mendalam jika terjadi constraint mismatch
)
```

---

## SEKSI 16 — KEAMANAN & HARDENING

1.  **Immutability Boundary:**
    Cegah kebocoran state konstruksi model dengan membatasi konstruktor utama (`private constructor`) pada data classes yang dilindungi oleh *Phantom Types*. Hanya *Smart Constructors* yang boleh mendistribusikan token status valid.
2.  **Mencegah Compile-Time Denial of Service (DoS):**
    Hindari rekursi tak berujung pada level tipe yang dapat dieksploitasi dalam library publik:
    ```scala
    // Proteksi dengan akkumulator batas kedalaman (Peano Numbers atau Literal Ints)
    type SafeRecurse[Depth <: Int, Data] = Depth match
      case 0 => Data
      case _ => SafeRecurse[scala.compiletime.ops.int.- [Depth, 1], List[Data]]
    ```
3.  **Eliminasi Kebocoran Data Sensitif via Bounds:**
    Terapkan Generalized Type Constraints untuk mencegah tipe kredensial bocor ke logger serialisasi:
    ```scala
    trait Loggable[T]
    
    // Gagalkan kompilasi jika tipe data mengandung kredensial
    def secureLog[T](data: T)(using Loggable[T], T =:!= PlainPassword): Unit = ...
    ```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Debugging tipe data tingkat lanjut tidak dapat mengandalkan runtime breakpoints. Anda harus menginspeksi kerja *Typer* secara langsung:

### 1. Memeriksa Hasil Reduksi Tipe Kompiler
Gunakan modul `scala.compiletime`:
```scala
import scala.compiletime.erasedValue

transparent inline def inspectType[T]: Unit =
  println(s"Reduced Type: ${scala.compiletime.error(erasedValue[T].toString)}")
```

### 2. Membedah Type Search Failures dengan Flags
Jalankan kompilasi menggunakan opsi diagnosa:
```bash
sbt "compile -explain -Vimplicits"
```
Flag `-explain` akan membongkar kegagalan pembuktian tipe dan subtyping mismatch menjadi diagram representatif yang menjelaskan mengapa tipe `A` tidak dapat disubstitusi sebagai `B`.

### 3. Menguji Penolakan Kompilasi (Compile-Time Testing)
Gunakan `compiletime.testing.typeChecks` untuk memastikan compiler menolak kode invalid dalam suite unit test Anda:
```scala
import scala.compiletime.testing.typeChecks

test("Pipeline must reject skipping risk assessment at compile-time") {
  val invalidCode = "SettlementWorkflow.authorize(Transaction.initiate(\"1\", Money[IDR](100)))"
  assert(!typeChecks(invalidCode))
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```
+------------------------------------+-----------------------------------------------------+
| SINTAKS / KONSEP                   | DESKRIPSI & KEGUNAAN                                |
+------------------------------------+-----------------------------------------------------+
| `F[_]`                             | Higher-Kinded Type: Konstruktor tipe aritas 1        |
| `[X] =>> Map[String, X]`           | Type Lambda: Menyesuaikan aritas tipe tanpa boiler   |
| `+T` (Kovarian)                    | Mengizinkan subtipe; aman untuk posisi output       |
| `-T` (Kontravarian)                | Membalikkan subtipe; aman untuk posisi input        |
| `A <: B`                           | Upper Bound: A harus berupa subtipe dari B          |
| `A >: B`                           | Lower Bound: A harus berupa supertipe dari B        |
| `x.type`                           | Singleton Type: Tipe yang mewakili satu nilai ini   |
| `instance.Inner`                   | Path-Dependent Type: Terikat unik pada instance     |
| `type T = X match { case ... }`    | Match Type: Evaluasi tipe deklaratif pada compile   |
| `A =:= B`                          | Type Equality Proof: Membuktikan tipe A identik B   |
| `A <:< B`                          | Subtyping Proof: Membuktikan relasi subtipe A <: B  |
+------------------------------------+-----------------------------------------------------+
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Dasar (Basic)
1. **Mengapa `trait Collection[+A] { def add(elem: A): Collection[A] }` ditolak oleh kompiler?**
   * *Jawaban:* Karena `+A` adalah kovarian (hanya boleh pada posisi output/return), sedangkan parameter fungsi `elem: A` berada pada posisi kontravarian (input). Pelanggaran ini dapat merusak keamanan sistem tipe jika instance di-cast ke supertipe.
2. **Apa yang dimaksud dengan proper type? Berikan dua contohnya.**
   * *Jawaban:* Proper type adalah tipe berderajat nol (`*`) yang dapat diinstansiasi menjadi nilai konkret di memori runtime. Contoh: `Int`, `String`.
3. **Bagaimana JVM mengeksekusi HKT seperti `F[A]` setelah fase kompilasi selesai?**
   * *Jawaban:* JVM melakukan *type erasure*, menghapus parameter tipe dan menggantinya dengan bound teratasnya (umumnya `Object`), kemudian menyisipkan runtime cast otomatis di level bytecode.
4. **Apa bedanya sintaks `[X] =>> (X, X)` dengan tuple biasa `(X, X)`?**
   * *Jawaban:* `[X] =>> (X, X)` adalah *Type Lambda* (fungsi anonim di level tipe yang menerima tipe `X` dan mengembalikan tipe tuple), sedangkan `(X, X)` adalah instansiasi tipe konkret dari tipe tuple itu sendiri jika `X` telah diketahui.
5. **Apa fungsi dari type equality constraint `A =:= B`?**
   * *Jawaban:* Mengharuskan dan membuktikan secara formal pada fase kompilasi bahwa tipe generik `A` dan tipe `B` adalah tipe yang persis identik, bukan sekadar memiliki relasi pewarisan.

### Bagian B: Menengah/Tingkat Lanjut (Intermediate)
6. **Perhatikan kode berikut: `val m1 = new KeyManager; val m2 = new KeyManager; val k: m1.Key = m2.spawnKey("abc")`. Apa yang terjadi saat kompilasi? Jelaskan alasannya.**
   * *Jawaban:* Terjadi compile error (*type mismatch*). Tipe `m1.Key` dan `m2.Key` adalah *Path-Dependent Types* yang berbeda secara strictly bound pada instans masing-masing nilai runtime (`m1` vs `m2`).
7. **Bagaimana Match Types mengatasi limitasi pattern matching berbasis subtyping biasa?**
   * *Jawaban:* Match Types mereduksi tipe output secara komputasional selama fase kompilasi tanpa perlu alokasi polimorfik dinamis, vtable dispatch, atau boxing runtime.
8. **Kapan Anda harus menggunakan Opaque Types daripada Value Classes (`extends AnyVal`)?**
   * *Jawaban:* Gunakan Opaque Types ketika menginginkan jaminan 0 alokasi heap secara absolut pada level memori, karena `AnyVal` sering kali tetap mengalami alokasi objek runtime (boxing) dalam skenario generik, collection, atau array.
9. **Mengapa lower bound `[B >: A]` menyelesaikan masalah kompilasi pada `Queue[+A]` saat menambahkan elemen baru?**
   * *Jawaban:* Karena lower bound memperluas jangkauan kontravarian: alih-alih memaksa parameter menerima subtipe (yang dilarang pada tipe kovarian), metode diizinkan menerima supertipe dari `A`, mengembalikan kontainer dengan tipe umum `Queue[B]` yang valid secara matematis.
10. **Apa dampak performa dari penggunaan rekursi Match Type yang sangat dalam pada aplikasi skala besar?**
    * *Jawaban:* Memperlambat waktu eksekusi kompilasi secara eksponensial (*long compilation time*), meningkatkan konsumsi memori heap mesin kompilator, dan berisiko memicu *compiler stack overflow* jika melebihi ambang inline default.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Type-Safe SQL Query Builder DSL

**Tujuan:**
Rancang sebuah embedded DSL (*Domain Specific Language*) di Scala 3 yang menggunakan **Phantom Types** dan **Dependent Typing** untuk mencegah kesalahan query SQL pada saat kompilasi:

#### Spesifikasi Fungsional:
1.  **State Management Query:**
    Sebuah kueri harus memiliki tahapan pembentukan yang kaku:
    *   `From` $\rightarrow$ `Where` (Opsional) $\rightarrow$ `Select` $\rightarrow$ `Build`.
    *   Pemanggilan metode `.select()` **dilarang keras** dilakukan sebelum metode `.from()` dideklarasikan.
    *   Metode `.build()` hanya dapat dipanggil jika kueri telah memiliki proyeksi kolom via `.select()`.
2.  **Schema Consistency Guard:**
    *   Tentukan skema tabel user via structural / case types (misal: `User(id: Long, name: String, age: Int)`).
    *   Jika developer mereferensikan kolom yang tidak ada pada tabel di klausa `.where()` atau `.select()`, kompilasi harus digagalkan dengan pesan error eksplisit.
3.  **Compile-Time Return Type Inference:**
    *   Jika query melakukan `select` terhadap satu kolom (misal: `name: String`), kembalian `.build().execute()` harus bertipe `List[String]`.
    *   Jika memilih dua kolom (misal: `name: String`, `age: Int`), tipe kembalian harus otomatis tereduksi menjadi `List[(String, Int)]` via Match Types.

#### Template Awal:
```scala
package dsl.sql

sealed trait QueryState
sealed trait NoTable   extends QueryState
sealed trait HasTable  extends QueryState
sealed trait Projected extends QueryState

// Terapkan implementasi builder Anda di sini...
```

**Kriteria Keberhasilan Praktikum:**
*   File dapat dikompilasi bersih menggunakan perintah `scalac -source:future`.
*   Semua skenario pengujian kompilasi negatif (kueri ilegal) gagal dikompilasi dengan benar.
*   Program menghasilkan output string SQL yang valid tanpa ada kebocoran alokasi overhead runtime yang tidak perlu.