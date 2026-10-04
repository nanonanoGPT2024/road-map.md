# Bab 01 Module 01: Pengenalan Scala, Arsitektur JVM, Interop, Immutability, & Desain Type-System

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis (C4)** model eksekusi Scala di atas Java Virtual Machine (JVM), termasuk representasi *bytecode*, *class loading*, dan implikasi *type erasure*.
*   **Mengevaluasi (C5)** trade-off arsitektural antara mutabilitas imperatif vs *immutability-by-default* dalam konteks konkurensi data throughput tinggi.
*   **Mengimplementasikan (C3)** hierarki *Unified Type System* Scala 3 (`Any`, `AnyVal`, `AnyRef`, `Null`, `Nothing`) tanpa mengorbankan integritas *type safety*.
*   **Mendiagnosis (C4)** overhead performa terkait *primitive boxing/unboxing* dan mengatasinya menggunakan fitur *zero-cost abstraction* seperti `opaque types`.
*   **Mengintegrasikan (C3)** interoperabilitas dua arah antara Java dan Scala secara aman tanpa menimbulkan kebocoran referensi bernilai `null`.

---

### 2. Conceptual Architecture / Background
Scala (*Scalable Language*) dirancang oleh Martin Odersky sebagai sintesis teoritis dan praktis antara dua paradigma komputasi: **Object-Oriented Programming (OOP)** murni dan **Functional Programming (FP)** tingkat lanjut. 

Di ekosistem JVM tradisional (seperti Java 8 ke bawah), pemisahan antara tipe primitif (`int`, `boolean`) dan tipe referensi (`java.lang.Object`) menciptakan dualisme tipe data. Scala menghilangkan dualitas ini dengan memperkenalkan *Unified Type System*, di mana setiap entitas adalah objek konseptual, namun dikompilasi menjadi primitif JVM berkinerja tinggi saat memungkinkan.

```
                  ┌────────────────────────┐
                  │       scala.Any        │
                  └───────────┬────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
   ┌─────────────────┐                 ┌─────────────────┐
   │  scala.AnyVal   │                 │  scala.AnyRef   │
   │ (Value Classes) │                 │(java.lang.Object│
   └────────┬────────┘                 └────────┬────────┘
            │                                   │
   ┌────────┴────────┐                 ┌────────┴────────┐
   │ Double, Float,  │                 │ List, String,   │
   │ Long, Int, Char,│                 │ User-defined    │
   │ Short, Byte,    │                 │ Classes         │
   │ Boolean, Unit   │                 └────────┬────────┘
   └────────┬────────┘                          │
            │                          ┌────────┴────────┐
            │                          │   scala.Null    │
            │                          └────────┬────────┘
            │                                   │
            └─────────────────┬─────────────────┘
                              ▼
                     ┌─────────────────┐
                     │  scala.Nothing  │
                     └─────────────────┘
```

Landasan filosofis Scala didasarkan pada *immutability-by-default* dan *expression-oriented programming*. Berbeda dari bahasa sekuensial prosedural, hampir setiap konstruksi sintaksis di Scala menghasilkan nilai (*expression*) alih-alih hanya mengeksekusi efek samping (*statement*).

---

### 3. Why It Matters
Dalam lanskap rekayasa perangkat lunak modern:
1.  **Sistem Terdistribusi Skala Masif**: Mesin analitik data modern (Apache Spark, Apache Flink) dan framework reaktif (*Akka/Apache Pekko*, *ZIO*, *Cats Effect*) mengandalkan Scala karena sifat deterministik dari *immutability*. *Shared-state concurrency* yang memicu *data race* pada Java dieliminasi di tingkat desain data model Scala.
2.  **Kerapatan Ekspresi dan Reduksi Boilerplate**: Scala memangkas *ceremony code* Java hingga 60-70% tanpa mengorbankan performa *static typing*.
3.  **Investasi Infrastruktur JVM**: Anda mempertahankan akses ke ekosistem pustaka JVM (Netty, Kafka Driver, Spring Context) dengan performa eksekusi JIT (*Just-In-Time Compiler*) HotSpot, namun memprogramnya menggunakan sistem tipe yang jauh lebih ekspresif (mirip Haskell/ML).

---

### 4. What It Is
Scala 3 adalah bahasa pemrograman *statically typed* tingkat lanjut yang berjalan di atas JVM, JavaScript (Scala.js), dan Native binary (Scala Native via LLVM). Modul ini berfokus pada Scala 3 di atas JVM.

Karakteristik fundamental:
*   **Expression-Oriented**: Blok kode dievaluasi ke nilai akhir. Tidak ada pemisahan kaku antara instruksi kondisional dan penugasan variabel.
*   **Unified Type System**: Struktur hierarkis tunggal berakar pada `scala.Any` dan berujung pada *bottom type* `scala.Nothing`.
*   **Seamless JVM Interoperability**: Scala mengompilasi kode sumber (`.scala`) langsung menjadi Java Bytecode (`.class`) standar, memungkinkan konsumsi *library* Java langsung tanpa *wrapper overhead*.
*   **TASTy-Based Architecture**: Scala 3 memperkenalkan TASTy (*Typed Abstract Syntax Trees*), format perantara serialisasi pohon sintaks yang memungkinkan kompatibilitas biner mendalam (*forward/backward binary compatibility*) melintasi versi minor compiler.

---

### 5. How It Works
Siklus hidup kode Scala melibatkan tahapan berikut:

```
[Source .scala] 
       │
       ▼
 [Dotty Frontend] ──> Parse & Type Check
       │
       ▼
[TASTy Generation] ──> High-Level AST Serialized (.tasty)
       │
       ▼
 [Dotty Backend]  ──> Bytecode Generation (JVM-compliant .class)
       │
       ▼
 [JVM Execution]  ──> ClassLoader -> JIT (C1/C2) Engine
```

#### 5.1. Kompilasi dan Representasi Bytecode
Ketika Anda menulis konstruksi Scala:
```scala
val x: Int = 42
```
Compiler Scala memetakannya secara internal:
1.  Pada level bahasa, `x` adalah instance dari `scala.Int` yang memiliki metode seperti `+`, `-`, `toHexString`.
2.  Saat kompilasi ke JVM bytecode, backend compiler menerjemahkannya ke primitif `int` mentah (instruksi bytecode: `BIPUSH 42` atau `ICONST_42`).
3.  Jika tipe tersebut masuk ke dalam struktur data generik (misal: `List[Int]`), compiler secara otomatis melakukan *boxing* ke `java.lang.Integer` via `java.lang.Integer.valueOf(int)` akibat limitasi *type erasure* JVM.

#### 5.2. Bottom Types: `Null` dan `Nothing`
*   `scala.Null`: Subtipe langsung dari semua tipe referensi (`scala.AnyRef`). Satu-satunya instansinya adalah `null`. `Null` tidak kompatibel dengan `scala.AnyVal`.
*   `scala.Nothing`: Subtipe dari *semua* tipe data di Scala (baik `AnyVal` maupun `AnyRef`). Tidak ada nilai yang pernah berjenis `scala.Nothing`. Tipe ini digunakan sebagai penanda komputasi abnormal (seperti ekspresi yang selalu melempar exception atau *infinite loop*).

---

### 6. Architecture / Flow Diagram

Berikut adalah alur eksekusi saat program Scala dijalankan hingga ke tingkat struktur memori JVM:

```
+------------------------------------------------------------------------------------+
|                                    JVM Runtime                                     |
|                                                                                    |
|  +-----------------------------+                  +-----------------------------+  |
|  |       Thread Stack          |                  |          Heap Space         |  |
|  +-----------------------------+                  +-----------------------------+  |
|  | [Stack Frame: main]         |                  |                             |  |
|  |                             |                  |                             |  |
|  | 1. Primitive:               |                  |                             |  |
|  |    val a: Int = 100         |                  |                             |  |
|  |    (Native 32-bit int)      |                  |                             |  |
|  |                             |                  |                             |  |
|  | 2. Reference Pointer:       |                  |                             |  |
|  |    val msg: String ─────────┼─────────────────>│ String Object Header (12B)  |  |
|  |    (64-bit reference)       |                  | Payload: "System Online"    |  |
|  |                             |                  |                             |  |
|  | 3. Generic Boxed Value:     |                  |                             |  |
|  |    val list: List[Int] ─────┼─────────────────>│ List Node (NonEmptyList)    |  |
|  |                             |                  |  ├─ head: java.lang.Integer │  |
|  |                             |                  |  │        (Heap Boxed)      |  |
|  |                             |                  |  └─ tail: List Node         |  |
|  +-----------------------------+                  +-----------------------------+  |
|                                                                                    |
+------------------------------------------------------------------------------------+
```

---

### 7. Core Syntax & Constructs

#### 7.1. Val vs Var
*   `val` mendefinisikan nilai imutabel (*read-only reference*). Setelah diinisialisasi, referensi tidak dapat diubah (mirip `final` pada Java).
*   `var` mendefinisikan variabel mutabel (*reassignable reference*).

```scala
val immutableBinding: Double = 3.14159 // Tidak dapat di-reassign
var mutableBinding: Int = 100
mutableBinding = 101                  // Sah, namun tidak dianjurkan di FP idiomatik
```

#### 7.2. Expression-Oriented Nature
Di Scala, `if-else` bukan statement kendali alur melainkan ekspresi yang menghasilkan nilai:

```scala
val isProduction: Boolean = true
val connectionTimeout: Int = if isProduction then 5000 else 1000
```

Blok kode di dalam kurung kurawal `{}` mengevaluasi baris terakhirnya sebagai nilai kembalian:

```scala
val calculatedBudget: Long = {
  val baseSalary = 50_000_000L
  val operationalBonus = 12_500_000L
  val taxDeduction = 7_500_000L
  baseSalary + operationalBonus - taxDeduction // Return value implisit
}
```

#### 7.3. Primitive Equivalent Types
Tabel pemetaan tipe fundamental Scala ke JVM primitives:

| Scala Type | Java Bytecode Equivalent | Ukuran Memori | Default JVM Boxing Class |
| :--- | :--- | :--- | :--- |
| `scala.Boolean` | `boolean` | 1 byte (diinterpretasikan int di stack) | `java.lang.Boolean` |
| `scala.Byte` | `byte` | 1 byte | `java.lang.Byte` |
| `scala.Char` | `char` | 2 bytes (UTF-16) | `java.lang.Character` |
| `scala.Short` | `short` | 2 bytes | `java.lang.Short` |
| `scala.Int` | `int` | 4 bytes | `java.lang.Integer` |
| `scala.Long` | `long` | 8 bytes | `java.lang.Long` |
| `scala.Float` | `float` | 4 bytes | `java.lang.Float` |
| `scala.Double` | `double` | 8 bytes | `java.lang.Double` |
| `scala.Unit` | `void` | 0 bytes (konseptual) | `scala.runtime.BoxedUnit` |

---

### 8. Minimal Reproducible Example
Berikut adalah berkas sumber mandiri yang dapat langsung dikompilasi dan dijalankan menggunakan `scala-cli`.

Simpan kode di bawah sebagai `Bootstrap.scala`:

```scala
//> using scala 3.3.3

package com.enterprise.foundations

object Bootstrap:
  // Definisi opaque type: Zero-cost abstraction untuk mencegah primitive obsession
  opaque type AccountId = Long
  object AccountId:
    def apply(value: Long): AccountId = 
      require(value > 0, "AccountId harus berupa bilangan bulat positif")
      value

  extension (id: AccountId)
    def value: Long = id

  def computeMetric(factor: Int): Either[String, Double] =
    if factor < 0 then
      Left("Faktor tidak boleh bernilai negatif")
    else
      // Blok ekspresi murni
      val calculated = {
        val base = 100.0
        val multiplier = factor * 1.5
        base + multiplier
      }
      Right(calculated)

  def main(args: Array[String]): Unit =
    println("[SYSTEM] Menginisialisasi Scala Core Runtime...")

    val rawId = 1000192837L
    val accountId = AccountId(rawId)
    
    // Demonstrasi Expression-Oriented matching
    val metricStatus = computeMetric(5) match
      case Right(score) => s"Perhitungan Sukses: Score = $score"
      case Left(error)  => s"Kegagalan Perhitungan: $error"

    println(s"Akun Terdaftar: ${accountId.value}")
    println(s"Status Metrik  : $metricStatus")
```

Jalankan via terminal:
```bash
scala-cli run Bootstrap.scala
```

---

### 9. Real-World Implementation
Kasus Produksi: Modul pemrosesan mutasi finansial berkecepatan tinggi dengan verifikasi invarian status akun dan integrasi Java Timestamp.

```scala
//> using scala 3.3.3

package com.enterprise.banking.ledger

import java.time.Instant
import scala.annotation.targetName

// Value class murni untuk meminimalkan alokasi heap via AnyVal
final case class Currency private (code: String) extends AnyVal

object Currency:
  def create(raw: String): Either[String, Currency] =
    if raw != null && raw.matches("^[A-Z]{3}$") then Right(new Currency(raw))
    else Left(s"Format mata uang invalid: '$raw'. Harus 3 digit uppercase (ISO-4217).")

final case class Balance(amount: BigDecimal, currency: Currency):
  @targetName("add")
  def +(other: Balance): Either[String, Balance] =
    if this.currency == other.currency then
      Right(Balance(this.amount + other.amount, this.currency))
    else
      Left(s"Mismatch transaksi mata uang: ${this.currency.code} vs ${other.currency.code}")

enum TransactionType:
  case Credit, Debit

final case class LedgerEntry(
  id: Long,
  transactionType: TransactionType,
  balanceChange: Balance,
  timestamp: Instant // Interop langsung dengan Java 8 Time API
)

object LedgerProcessor:
  def applyTransaction(
    currentBalance: Balance, 
    entry: LedgerEntry
  ): Either[String, Balance] =
    entry.transactionType match
      case TransactionType.Credit =>
        currentBalance + entry.balanceChange
      case TransactionType.Debit =>
        if currentBalance.amount >= entry.balanceChange.amount then
          currentBalance + Balance(-entry.balanceChange.amount, entry.balanceChange.currency)
        else
          Left(s"Insufficient funds: Current ${currentBalance.amount}, required ${entry.balanceChange.amount}")

object ProductionApp:
  def main(args: Array[String]): Unit =
    val setupResult = for
      idr       <- Currency.create("IDR")
      initBal   =  Balance(BigDecimal("10000000.00"), idr)
      debitVal  =  Balance(BigDecimal("2500000.00"), idr)
      ledger    =  LedgerEntry(1L, TransactionType.Debit, debitVal, Instant.now())
      finalBal  <- LedgerProcessor.applyTransaction(initBal, ledger)
    yield finalBal

    setupResult match
      case Right(balance) =>
        println(s"[AUDIT] Berhasil memproses mutasi buku besar. Saldo sisa: ${balance.amount} ${balance.currency.code}")
      case Left(error) =>
        println(s"[FATAL] Transaksi ditolak oleh engine: $error")
```

---

### 10. Edge Cases, Hazards & Pitfalls

#### 10.1. Kebocoran `null` dari Ekosistem Java
Saat berinteraksi dengan API Java eksternal, JVM dapat mengembalikan pointer `null`. Scala tidak melakukan auto-wrap ke `Option`.
```scala
// BAHAYA: Mengakses API Java secara langsung
val rawEnv: String = System.getProperty("NON_EXISTING_KEY")
// rawEnv secara runtime adalah null!
val len = rawEnv.length // Menghasilkan java.lang.NullPointerException (NPE)

// SOLUSI: Bungkus segera dengan Option
val safeEnv: Option[String] = Option(System.getProperty("NON_EXISTING_KEY"))
```

#### 10.2. Hidden Boxing Overhead pada Collections
Struktur data generic JVM tidak mendukung primitif.
```scala
// Array asli JVM menggunakan int[] murni (tanpa alokasi object per elemen)
val primitiveArray: Array[Int] = Array(1, 2, 3) 

// List berbasis pointer reference, setiap 'Int' dibungkus menjadi java.lang.Integer
val boxedList: List[Int] = List(1, 2, 3) 
```
Jika Anda memproses miliaran data dengan `List[Int]`, beban Garbage Collector (GC) melonjak drastis karena *boxing*.

#### 10.3. Equality Pitfall (`==` vs `eq`)
*   `==` di Scala secara otomatis memanggil `.equals()` yang *null-safe*.
*   `eq` membandingkan identitas referensi memori (*reference equality*, setara dengan `==` pada Java untuk tipe referensi).

```scala
val a = new String("DATA")
val b = new String("DATA")

println(a == b) // true (structural equality)
println(a eq b) // false (different heap memory addresses)
```

---

### 11. Performance Considerations
1.  **Gunakan Opaque Types daripada Wrapper Classes**:
    Hindari alokasi objek hanya untuk memberi label tipe domain.
    ```scala
    // Menghasilkan alokasi heap baru untuk setiap UserID
    case class UserId(value: Long) 

    // Zero memory overhead, di-compile murni menjadi primitif long di bytecode
    opaque type UserId = Long 
    ```
2.  **Manfaatkan `@tailrec` untuk Loop Rekursif**:
    Scala mengompilasi fungsi *tail-recursive* menjadi instruksi *loop jump* JVM reguler (`GOTO`), mencegah pemborosan *stack frame* dan eliminasi risiko `StackOverflowError`.
3.  **Hindari Konversi Implisit Koleksi Besar**:
    Operasi seperti `.map().filter().map()` pada immutable collections membuat struktur perantara baru di memori Heap pada setiap chaining step. Gunakan `.view` untuk evaluasi *lazy*:
    ```scala
    val result = largeList.view.map(f).filter(g).toList
    ```

---

### 12. Memory & Resource Model
*   **Representasi Stack Frame**: Tipe turunan `AnyVal` lokal disimpan langsung pada frame eksekusi thread stack tanpa alokasi di heap, selama tidak dilakukan *upcasting* ke `Any` atau koleksi generik.
*   **Struktur Heap Object**: Setiap turunan `AnyRef` mengonsumsi *Object Header* JVM (biasanya 12 bytes: 8 bytes Mark Word + 4 bytes Compressed OOPs pada arsitektur 64-bit JVM) ditambah *padding* alignment kelipatan 8 bytes.
*   **Structural Sharing**: Immutability pada Scala tidak berarti menyalin seluruh data saat terjadi perubahan. Koleksi data imutabel seperti `scala.collection.immutable.List` menggunakan mekanisme *structural sharing* di memori:

```
List B: val b = 0 :: a
[Node: 0] ──> [Node: 1] ──> [Node: 2] ──> Nil
                 ▲
List A: val a ───┘
```
Penambahan node baru hanya mengalokasikan 1 node pointer ke struktur data lama tanpa mereplikasi node 1 dan 2.

---

### 13. Tooling & Ecosystem

| Komponen | Standar Industri | Fungsi Teknis |
| :--- | :--- | :--- |
| **Compiler** | `scalac` (Dotty 3.x) | Mengubah representasi kode Scala menjadi TASTy dan JVM Bytecode. |
| **Runner / Scripting** | `scala-cli` | Prototipe cepat, *packaging*, *dependency resolution* tanpa *build tool* masif. |
| **Build Tool** | `sbt` (Scala Build Tool) | Multi-module compilation, dependency graph resolution, packaging JAR/fat-JAR. |
| **Alternative Build** | `Mill` | Tool build berbasis JVM modern dengan model eksekusi strongly-typed. |
| **Language Server** | `Metals` | Menyediakan autocompletion, refactoring, code navigation via LSP protocol. |
| **Code Formatter** | `Scalafmt` | Enforcer konsistensi penulisan indentation-based Scala 3. |

Konfigurasi minimal `build.sbt`:
```scala
ThisBuild / scalaVersion := "3.3.3"
ThisBuild / organization := "com.enterprise"

lazy val root = (project in file("."))
  .settings(
    name := "core-engine",
    scalacOptions ++= Seq(
      "-deprecation",
      "-feature",
      "-unchecked",
      "-Xfatal-warnings"
    )
  )
```

---

### 14. Anti-Patterns & Code Smells

#### Anti-Pattern: Primitive Obsession & Imperative Mutation
```scala
// BURUK: Menggunakan var mutabel dan tipe primitif tanpa validasi domain
class TransactionProcessor {
  var status: String = "PENDING"
  var totalAmount: Double = 0.0

  def process(amt: Double): Unit = {
    if (amt > 0) {
      totalAmount = totalAmount + amt
      status = "COMPLETED"
    } else {
      status = "FAILED"
    }
  }
}
```

#### Refactoring Idiomatik: State Encapsulation via Immutability
```scala
// BAIK: Tipe data tertutup, status eksplisit via Enum, referensi imutabel
enum TxStatus:
  case Pending, Completed, Failed

final case class AccountState(balance: BigDecimal, status: TxStatus)

object AccountState:
  def update(current: AccountState, delta: BigDecimal): AccountState =
    if delta > 0 then
      current.copy(
        balance = current.balance + delta, 
        status = TxStatus.Completed
      )
    else
      current.copy(status = TxStatus.Failed)
```

---

### 15. Security Implications
1.  **Java Serialization Hijacking**: Hindari pewarisan `java.io.Serializable` pada struktur data Scala tanpa validasi deserialisasi ketat. Penyerang dapat menyisipkan *gadget chain* via serial payload.
2.  **String Interpolation Injection**: Penggunaan string interpolator kustom untuk SQL query atau Command Injection:
    ```scala
    // RENTAN: Jika query dibangun menggunakan interpolasi raw s"..."
    val maliciousInput = "'; DROP TABLE users; --"
    val query = s"SELECT * FROM accounts WHERE id = '$maliciousInput'"

    // AMAN: Gunakan library database dengan type-level prepared statements (misal: Doobie/Slick)
    // sql"SELECT * FROM accounts WHERE id = $maliciousInput".query[Account]
    ```
3.  **Pattern Matching Exhaustiveness**: Kegagalan memastikan matching meng-cover semua subclass (`sealed trait` atau `enum`) dapat menimbulkan `scala.MatchError` pada runtime, membuka celah *Denial of Service* (DoS) melalui unhandled crash.

---

### 16. Testing Strategies

Gunakan kerangka pengujian modern seperti **MUnit**:

```scala
//> using test.dep org.scalameta::munit::1.0.0

package com.enterprise.banking.ledger

class LedgerProcessorSuite extends munit.FunSuite:

  val idr = Currency.create("IDR").getOrElse(fail("Setup currency gagal"))

  test("applyTransaction: mutasi debit valid harus memotong saldo dengan tepat") {
    val initialBalance = Balance(BigDecimal("500000.00"), idr)
    val debitEntry = LedgerEntry(
      id = 101L,
      transactionType = TransactionType.Debit,
      balanceChange = Balance(BigDecimal("200000.00"), idr),
      timestamp = java.time.Instant.EPOCH
    )

    val result = LedgerProcessor.applyTransaction(initialBalance, debitEntry)
    val expected = Right(Balance(BigDecimal("300000.00"), idr))

    assertEquals(result, expected)
  }

  test("applyTransaction: harus menggagalkan transaksi jika saldo tidak mencukupi") {
    val initialBalance = Balance(BigDecimal("100000.00"), idr)
    val excessiveDebit = LedgerEntry(
      id = 102L,
      transactionType = TransactionType.Debit,
      balanceChange = Balance(BigDecimal("200000.00"), idr),
      timestamp = java.time.Instant.EPOCH
    )

    val result = LedgerProcessor.applyTransaction(initialBalance, excessiveDebit)
    assert(result.isLeft, "Eksekusi harus menghasilkan Left (Error)")
  }
```

Jalankan pengujian:
```bash
scala-cli test Bootstrap.scala LedgerProcessorSuite.scala
```

---

### 17. Trade-offs & Comparisons

| Parameter | Scala 3 | Java 21+ | Kotlin |
| :--- | :--- | :--- | :--- |
| **Type System** | Advanced (Path-dependent, Union, Intersection, Opaque types) | Baseline OOP (Nominal, Generics with Wildcards, Records) | Pragmatic OOP/FP (Nullable types, Reified generics) |
| **Immutability** | Default pada seluruh koleksi standar (`scala.collection.immutable`) | Manual (`final`, `Collections.unmodifiableList`) | Pragmatic (`val` vs `var`, read-only interfaces) |
| **Compilation Speed** | Relatif lambat (fase inferensi tipe kompleks & macro Dotty) | Sangat Cepat (compiler minim transformasi tipe) | Cepat hingga Moderat |
| **Null Safety** | Built-in via `Option` & Explicit Nulls flag (`-Yexplicit-nulls`) | Parsial via JSpecify annotations / `Optional` | Built-in via syntax `T?` vs `T` |
| **Runtime Overhead** | Zero hingga Medium (tergantung pemanfaatan Boxing/AnyVal) | Zero (Native runtime standard) | Rendah (mirip dengan Java bytecode) |

---

### 18. Troubleshooting & Debugging Guide

#### Isu 1: Compile-Time Type Mismatch
*   **Pesan Error**: `Found: AnyVal, Required: Double`
*   **Penyebab**: Percabangan `if-else` atau `match` mengembalikan tipe data yang tidak seragam (misal cabang `then` mengembalikan `Double`, sedangkan cabang `else` mengembalikan `Unit` akibat tidak adanya ekspresi penutup).
*   **Solusi**: Pastikan seluruh jalur evaluasi mengembalikan tipe yang selaras:
    ```scala
    // ERROR: cabang 'else' implisit menghasilkan Unit
    val result = if condition then 42.0 

    // FIX: eksplisitkan nilai fallback
    val result = if condition then 42.0 else 0.0
    ```

#### Isu 2: `java.lang.ClassCastException` akibat Type Erasure
*   **Pesan Error**: `java.lang.ClassCastException: class java.lang.String cannot be cast to class java.lang.Integer`
*   **Penyebab**: JVM menghapus parameter tipe generik saat *runtime*. Pencocokan pola koleksi generic seperti `case list: List[Int]` tidak dapat memverifikasi isi elemen list pada runtime.
*   **Solusi**: Hindari *type pattern matching* pada generic parameter langsung, gunakan `TypeTest` atau validasi elemen manual:
    ```scala
    // HINDARI (Memunculkan peringatan compile: unchecked type pattern)
    obj match
      case l: List[Int] => ...

    // SOLUSI: Gunakan TypeTag / TypeTest terdefinisi atau validasi per elemen
    ```

---

### 19. Enterprise Context & Scalability
1.  **Monorepo Compilation Cost**: Sistem enterprise dengan ratusan modul Scala dapat mengalami degradasi waktu kompilasi (*build bottleneck*). Strategi penanganannya mencakup:
    *   Penggunaan **Bloop** (*build server*) untuk kompilasi inkremental paralel.
    *   Mengisolasi API layer menggunakan interface stabil guna membatasi kompilasi berulang akibat perubahan implementasi.
2.  **Binary Compatibility via TASTy**: Tidak seperti Scala 2 di mana minor version upgrades (misal 2.12 ke 2.13) memutus kompatibilitas biner (*binary incompatibility*), format TASTy pada Scala 3 memungkinkan library yang dikompilasi pada Scala 3.1 dikonsumsi secara stabil oleh project berbasis Scala 3.3.
3.  **High-Concurrency Backends**: Dalam arsitektur *event-driven* (Kafka consumers, FinTech payment switches), penggunaan model data imutabel Scala menjamin bahwa memori dapat dibaca bersamaan oleh ribuan thread virtual tanpa *mutex lock synchronization*, secara drastis menaikkan skala throughput transaksi per node server.

---

### 20. Wrap-Up & Next Steps

#### Rangkuman Konsep
Modul ini telah membedah pondasi arsitektural Scala 3:
*   Bagaimana *Unified Type System* mengonsolidasikan primitif dan objek referensi di bawah hierarki `scala.Any`.
*   Eksekusi berbasis ekspresi (*Expression-Oriented*) yang meminimalisir mutabilitas state.
*   Peta kompilasi dari kode sumber `.scala`, pohon sintaks TASTy, hingga eksekusi bytecode murni di atas JVM.

#### Hands-On Challenge
Konversikan kode imperatif Java berikut ke dalam Scala 3 yang murni idiomatik (tanpa `var`, tanpa `null`, memanfaatkan *pattern matching*, *immutable case classes*, dan penanganan kegagalan dengan `Either`):

```java
// Java Imperatif Legacy
public class OrderValidator {
    public static String processOrder(String orderId, double price, int quantity) {
        if (orderId == null || orderId.trim().isEmpty()) {
            return "ERROR: Invalid ID";
        }
        if (price <= 0.0 || quantity <= 0) {
            return "ERROR: Invalid Amount";
        }
        double total = price * quantity;
        if (total > 1000000.0) {
            return "REJECTED: High risk order";
        }
        return "SUCCESS: Total = " + total;
    }
}
```

#### Pratinjau Modul Berikutnya
Pada **Bab 01 Module 02**, kita akan mendalami:
*   *Control Structures* tingkat lanjut di Scala 3.
*   Mekanisme *Pattern Matching* komprehensif (*Guards*, *Extractor Objects* via `unapply`).
*   Dekonstruksi struktur data kompleks dengan performa setara instruksi *jump table* JVM.