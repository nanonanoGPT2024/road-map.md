# BAB 03: Fondasi Pemrograman Fungsional
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi, mengukur, dan mengeliminasi limitasi stack runtime JVM melalui teknik **Tail Call Optimization (`@tailrec`)** dan **Trampolining** untuk algoritma rekursif arbitrer tak terbatas (*infinite/deep recursion*).
- Merancang domain bisnis kompleks bebas *runtime failure* menggunakan **Algebraic Data Types (ADTs)**, **Generalized Algebraic Data Types (GADTs)**, serta membuktikan kebenaran struktur kode via *Exhaustive Pattern Matching* di tingkat compiler.
- Membedah transformasi internal compiler Scala terhadap **For-Comprehension Desugaring** (`map`, `flatMap`, `withFilter`, `foreach`) untuk mengoptimalkan alokasi objek pada *hot-path*.
- Mengimplementasikan pola arsitektur **Type Classes** di Scala 3 (`trait`, `given`, `using`) sebagai alternatif *ad-hoc polymorphism* yang lebih *type-safe* dan decoupled dibandingkan pewarisan OOP klasik (*subtyping*).
- Mengaudit dan mengoptimasi *garbage collection overhead* yang diakibatkan oleh *monadic chaining*, alokasi closure, dan boxing tipe primitif pada sistem throughput tinggi.

---

### 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- Sintaks dasar Scala 3 (deklarasi `val`, `def`, `case class`, `trait`, blok ekspresi).
- Pemahaman mendalam terkait **JVM Memory Model** (Heap vs. Call Stack Frame, Metaspace, GC Young/Old Gen).
- Modul 01: Prinsip dasar Immutability, Pure Functions, dan First-Class Functions.
- Konsep dasar struktur data: Linked List, Trees, dan Graph Traversal.
- SBT (Scala Build Tool) untuk menjalankan unit test dan *bytecode inspection* (`javap`).

---

### 3. Concept & Internal Architecture

#### A. Mekanisme Bytecode Rekursi & Limitasi Call Stack JVM
JVM mengalokasikan memori *Call Stack* berukuran tetap (default biasanya 1024 KB via flag `-Xss`) untuk setiap thread. Setiap pemanggilan fungsi menghasilkan *Stack Frame* baru yang menyimpan:
- *Local variable array*
- *Operand stack*
- *Frame data* (resolusi runtime pool, method return address)

Jika pemanggilan rekursif melebihi kapasitas kedalaman frame, JVM melemparkan `java.lang.StackOverflowError`. 

```
+-------------------------------------------------------------+
| JVM Call Stack (Thread-1) - Non-Tail-Recursive Execution     |
| [Frame 3: factorial(1)] -> Membutuhkan Frame 2              |
| [Frame 2: factorial(2)] -> Membutuhkan Frame 1              |
| [Frame 1: factorial(3)] -> Menunggu hasil child frame       |
| ... Alokasi linear: O(N) memory overhead -> StackOverflow   |
+-------------------------------------------------------------+
```

Scala menyelesaikan masalah ini melalui anotasi `@tailrec`. Compiler Scala memverifikasi apakah *self-invocation* berada di posisi eksekusi paling akhir (*tail position*). Jika ya, compiler mendesugar pemanggilan rekursif menjadi instruksi iteratif linear (`goto` / loop jumps) di level JVM bytecode (`ILOAD`, `IFLE`, `GOTO`), mereduksi *memory footprint* call stack dari $O(N)$ menjadi $O(1)$.

Jika fungsi rekursif bersifat mutual (fungsi `A` memanggil `B`, dan `B` memanggil `A`) atau non-tail branch rekursif ganda (seperti tree traversal), `@tailrec` gagal. Solusi tingkat enterprise adalah **Trampolining**: memindahkan eksekusi dari JVM Call Stack ke Heap Memory dengan memodelkan langkah komputasi sebagai *Free Monad* sederhana atau tipe data tertunda (*suspended computation*).

#### B. Dekonstruksi Bytecode For-Comprehension
For-comprehension di Scala bukanlah konstruksi native JVM, melainkan *syntactic sugar* tingkat tinggi yang diekspansi (*desugared*) oleh Scala parser/typer sebelum kompilasi bytecode:

```scala
// Kode Asal
for {
  x <- optA
  y <- optB if y > 0
} yield x + y

// Hasil Desugaring oleh Compiler
optA.flatMap(x => 
  optB.withFilter(y => y > 0).map(y => x + y)
)
```

Implikasi internal:
1. `withFilter` menghindari alokasi intermediate collection secara langsung dengan membuat wrapper lazy evaluatif.
2. Setiap `flatMap` dan `map` menginstansiasi closure baru (`scala.runtime.AbstractFunction1`), yang dapat memicu alokasi heap jika closure tersebut menangkap variabel lingkungan (*capturing closure*). Di hot-path, instansiasi ini memicu GC Young Gen pressure.

#### C. Algebraic Data Types (ADTs) & Bytecode Exhaustiveness
Scala 3 menyatukan pemodelan ADT melalui konstruksi `enum` atau `sealed trait`.
- **Sum Types** ($A + B$): Diskriminasi tipe diskrit (pilihan mutlak antara $A$ atau $B$).
- **Product Types** ($A \times B$): Komposisi data (berisi $A$ DAN $B$ sekaligus, e.g., `case class`).

Compiler mengeksekusi analisis kelengkapan (*exhaustiveness check*) melalui flow-typing pada fase tipe. Di level bytecode, `match` diekspansi menjadi salah satu dari dua instruksi:
- `tableswitch`: Digunakan saat target pencocokan berupa indeks konstan berurutan padat ($O(1)$ jump).
- `lookupswitch`: Digunakan untuk nilai integer/hash yang renggang ($O(\log N)$ binary search di level bytecode).
- Rantai `instanceof` bertingkat untuk matching tipe objek sembarang.

```
       [AST Analysis: Pattern Matching]
                      |
        +-------------+-------------+
        |                           |
  [Type Check]                 [Bytecode Optimization]
        |                           |
  Deteksi Unhandled            Apakah target nilai integer/enum?
  Permutasi ADT                     /              \
        |                         (Ya)             (Tidak)
  Compile Error / Warning          /                 \
  jika tidak exhaustif     [tableswitch]        [Chained instanceof /
                           [lookupswitch]        ClassCastException trap]
```

---

### 4. Why & What

| Paradigma / Konstruksi | Mengapa Diperlukan di Arsitektur Enterprise? | Apa Karakteristik Internalnya? |
| :--- | :--- | :--- |
| **Tail-Call Optimization** | Mencegah crash sistem fatal (`StackOverflowError`) pada pipeline stream/rekursif data tak berhingga tanpa mengorbankan declarative purity. | Transformasi compile-time dari rekursi AST menjadi jump instruction bytecode iteratif. Zero stack frame overhead. |
| **Trampoline Monad** | Mengeksekusi rekursi mutual dan graph traversal dalam skala jutaan node tanpa limitasi JVM Call Stack. | Komputasi ditangguhkan (*suspended*) di Heap Memory; runtime mengevaluasinya melalui driver loop tunggal. |
| **Algebraic Data Types (ADTs)** | Menjamin *Make Illegal States Unrepresentable*. Memusnahkan bug `NullPointerException` dan `UndefinedStateException`. | Penegakan exhaustive matching pada compile-time via `sealed trait` atau `enum` Scala 3. |
| **Type Classes** | Menghindari kerapuhan *classical inheritance* (anti-*fragile base class problem*); memisahkan definisi data dari kapabilitas operasionalnya. | Resolusi implisit/kontekstual berbasis tipe statis melalui `given` dan `using`. |

---

### 5. How (Workflow Detail)

```
[Domain Requirements: Immutable State Transitions]
                      |
                      v
    +------------------------------------+
    | 1. Model Domain via ADT (Scala 3)  |
    |    (enum / sealed trait)           |
    +------------------------------------+
                      |
                      v
    +------------------------------------+
    | 2. Implement Pure Business Logic   |
    |    - Tailrec jika linear           |
    |    - Trampoline jika non-linear    |
    |    - For-comprehension chaining    |
    +------------------------------------+
                      |
                      v
    +------------------------------------+
    | 3. Abstract Behavior via           |
    |    Type Classes (given/using)      |
    +------------------------------------+
                      |
                      v
    +------------------------------------+
    | 4. Verification & Optimization     |
    |    - scalac: -Xlint / -Werror      |
    |    - javap: Verifikasi loop jump   |
    |    - Profiling: Escape analysis    |
    +------------------------------------+
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: JVM Call Stack vs. Trampoline Loop
- **JVM Call Stack Standar**: Seperti tumpukan baki kafetaria. Setiap pemanggilan fungsi menumpuk satu baki di atasnya. Jika Anda menumpuk 50.000 baki, tumpukan roboh karena langit-langit (Stack Limit) terlalu rendah.
- **Trampoline (Heap Loop)**: Anda hanya memiliki satu baki di atas meja. Setiap fungsi mengembalikan *secarik kertas instruksi* tentang apa yang harus dimasak berikutnya. Driver loop utama membaca kertas tersebut, mengeksekusi instruksi, membuang kertas lama, dan mengambil instruksi berikutnya. Tumpukan baki tidak pernah bertambah; yang digunakan adalah laci penyimpanan restoran (Heap Space) yang masif.

```
--- TRADISIONAL CALL STACK RECURSION ---
Stack Limit -------------------------------------------- (CRASH: StackOverflow)
[ Frame 4: process(step4) ]
[ Frame 3: process(step3) ]
[ Frame 2: process(step2) ]
[ Frame 1: process(step1) ]
--------------------------------------------------------

--- TRAMPOLINING VIA HEAP DRIVER LOOP ---
Call Stack (Tetap tipis)
+-----------------------+
|  Trampoline Run Loop  | <--- Frame stack tidak pernah bertambah
+-----------------------+
            ^
            |  Evaluasi & Ganti Objek
            v
Heap Space (Dikelola oleh GC, Skala Gigabytes)
[ FlatMap(Step1, Next) ] -> [ FlatMap(Step2, Next) ] -> [ Done(Result) ]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: `@tailrec` vs. Trampoline untuk Mutual Recursion
Berikut adalah implementasi komparatif mutual recursion tanpa risiko stack overflow.

```scala
package enterprise.fp.basics

import scala.annotation.tailrec

// 1. GAGAL: Mutual recursion ini tidak bisa dioptimasi oleh @tailrec
// Definisikan Trampoline ADT untuk eliminasi Call Stack
sealed trait Trampoline[+A] {
  @tailrec
  final def run: A = this match {
    case Trampoline.Done(v)       => v
    case Trampoline.More(k)       => k().run
    case Trampoline.FlatMap(sub, f) => sub match {
      case Trampoline.Done(v2)        => f(v2).run
      case Trampoline.More(k2)        => k2().flatMap(f).run
      case Trampoline.FlatMap(sub2, g) => sub2.flatMap(x => g(x).flatMap(f)).run
    }
  }

  def flatMap[B](f: A => Trampoline[B]): Trampoline[B] = Trampoline.FlatMap(this, f)
  def map[B](f: A => B): Trampoline[B] = flatMap(x => Trampoline.Done(f(x)))
}

object Trampoline {
  case class Done[+A](value: A) extends Trampoline[A]
  case class More[+A](k: () => Trampoline[A]) extends Trampoline[A]
  case class FlatMap[A, +B](sub: Trampoline[A], f: A => Trampoline[B]) extends Trampoline[B]
}

// Simulasi Mutual Recursion aman hingga 1.000.000 iterasi
object MutualRecursionSafe {
  def isEven(n: Int): Trampoline[Boolean] =
    if (n == 0) Trampoline.Done(true)
    else Trampoline.More(() => isOdd(n - 1))

  def isOdd(n: Int): Trampoline[Boolean] =
    if (n == 0) Trampoline.Done(false)
    else Trampoline.More(() => isEven(n - 1))
}
```

#### B. Practical Example: Monadic Pipeline & Type Classes di Scala 3

```scala
package enterprise.fp.order

import java.util.UUID
import java.time.Instant

// Domain ADT
enum PaymentMethod:
  case CreditCard(token: String)
  case BankTransfer(iban: String)
  case CryptoWallet(address: String)

enum OrderState:
  case Created(orderId: UUID, items: List[String], amount: BigDecimal)
  case Validated(orderId: UUID, items: List[String], amount: BigDecimal, method: PaymentMethod)
  case Paid(orderId: UUID, amount: BigDecimal, txHash: String, at: Instant)
  case Rejected(orderId: UUID, reason: String)

// Type Class: Serialisasi Telemetri
trait AuditLog[A]:
  def log(value: A): String

object AuditLog:
  def apply[A](using instance: AuditLog[A]): AuditLog[A] = instance

  given AuditLog[OrderState] with
    def log(state: OrderState): String = state match
      case OrderState.Created(id, items, amt) => 
        s"[AUDIT] Order Created: $id | Items: ${items.size} | Total: $$amt"
      case OrderState.Validated(id, _, amt, method) => 
        s"[AUDIT] Order Validated: $id | Target: $amt | Via: $method"
      case OrderState.Paid(id, amt, tx, at) => 
        s"[AUDIT] Order Finalized: $id | Captured: $amt | Tx: $tx at $at"
      case OrderState.Rejected(id, reason) => 
        s"[AUDIT] Order Failed: $id | Rejection Reason: $reason"

// Domain Processing via Functional Composition
object OrderEngine:
  type DomainResult[A] = Either[String, A]

  def validateOrder(state: OrderState.Created, method: PaymentMethod): DomainResult[OrderState.Validated] =
    if (state.amount <= 0) Left(s"Invalid order amount: ${state.amount}")
    else if (state.items.isEmpty) Left("Cannot process order without line items")
    else Right(OrderState.Validated(state.orderId, state.items, state.amount, method))

  def authorizePayment(state: OrderState.Validated): DomainResult[OrderState.Paid] =
    state.method match
      case PaymentMethod.CreditCard(token) if token.isBlank => 
        Left("Invalid payment token")
      case _ => 
        Right(OrderState.Paid(state.orderId, state.amount, UUID.randomUUID().toString, Instant.now()))

  // For-comprehension composition
  def process(created: OrderState.Created, method: PaymentMethod)(using audit: AuditLog[OrderState]): DomainResult[OrderState.Paid] =
    for {
      _         <- Right(println(audit.log(created)))
      validated <- validateOrder(created, method)
      _         <- Right(println(audit.log(validated)))
      paid      <- authorizePayment(validated)
      _         <- Right(println(audit.log(paid)))
    } yield paid
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Sistem *High-Throughput Distributed Financial Reconciliation Ledger*. Sistem wajib memproses stream rekonsiliasi hingga $50.000.000$ transaksi per hari. Data transaksi yang masuk sering kali mengalami kerusakan format, duplikasi status, atau dependency tree yang sangat dalam (misal: rantai transaksi reversal, refund, chargeback bersarang).

#### Masalah Produksi
Versi legacy menggunakan rekursi standar untuk menelusuri rantai reversal transaksi. Saat terjadi *loop circular dispute* atau rantai reversal dengan kedalaman $> 8.000$ transaksi, terjadi `StackOverflowError` yang memicu *thread termination* pada Akka Actor System, mengakibatkan kegagalan bulk batch processing senilai jutaan dolar.

#### Solusi Fungsional Terapan
1. **Trampolined State Machine**: Menghilangkan mutasi state in-place dan mengganti tree traversal berbasis call stack dengan `Trampoline` ADT berbasis Heap.
2. **Exhaustive Domain ADT**: Memodelkan status transaksi secara rigid agar *unhandled states* mustahil lolos dari kompilasi.
3. **Zero-Allocation Error Aggregation**: Memanfaatkan `Either` monad terstruktur tanpa *runtime exception throw*.

```scala
package enterprise.reconciliation

import scala.annotation.tailrec

// Model Ledger State
enum TxType:
  case Debit, Credit, Fee, Reversal

case class Transaction(
  id: Long,
  parentId: Option[Long],
  amount: Long, // Menggunakan sen/cents untuk presisi
  txType: TxType
)

enum ReconcileError:
  case MissingParentTransaction(id: Long, parentId: Long)
  case CircularReferenceDetected(id: Long)
  case ArithmeticOverflow(id: Long)

// Trampoline Engine untuk Traversing Audit Trail
sealed trait RecEval[+A] {
  @tailrec
  final def run: A = this match {
    case RecEval.Done(a) => a
    case RecEval.Cont(thunk) => thunk().run
  }
}
object RecEval {
  case class Done[+A](value: A) extends RecEval[A]
  case class Cont[+A](thunk: () => RecEval[A]) extends RecEval[A]
}

final class LedgerReconciliationService(storage: Map[Long, Transaction]) {

  def calculateChainNet(rootId: Long): Either[ReconcileError, Long] = {
    
    def loop(
      currentId: Long, 
      visited: Set[Long], 
      accumulated: Long
    ): RecEval[Either[ReconcileError, Long]] = {
      if (visited.contains(currentId)) {
        RecEval.Done(Left(ReconcileError.CircularReferenceDetected(currentId)))
      } else {
        storage.get(currentId) match {
          case None => 
            RecEval.Done(Left(ReconcileError.MissingParentTransaction(currentId, 0L)))
          case Some(tx) =>
            val newVisited = visited + currentId
            val netDelta = tx.txType match {
              case TxType.Credit   => tx.amount
              case TxType.Debit    => -tx.amount
              case TxType.Fee      => -tx.amount
              case TxType.Reversal => -tx.amount
            }
            val nextTotal = accumulated + netDelta

            tx.parentId match {
              case None => 
                RecEval.Done(Right(nextTotal))
              case Some(pId) => 
                RecEval.Cont(() => loop(pId, newVisited, nextTotal))
            }
        }
      }
    }

    loop(rootId, Set.empty, 0L).run
  }
}
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Trade-off | Solusi Mitigasi |
| :--- | :--- | :--- | :--- |
| **`@tailrec` Optimization** | - Alokasi memory stack $O(1)$<br>- Performa setara loop C (`goto`) | - Hanya mendukung pemanggilan linear tunggal.<br>- Tidak mendukung mutual recursion. | Gunakan trampolining jika struktur algoritma bukan tail-call linear. |
| **Heap-allocated Trampoline** | - Mencegah `StackOverflowError` secara mutlak.<br>- Mampu mengevaluasi kedalaman rekursi tak berhingga. | - Overhead alokasi objek (`More`, `FlatMap`) di JVM Heap.<br>- GC Young Gen pressure meningkat drastis. | Gunakan *Object Pooling* atau representasi berbasis array datar (*Flattened array loop*) untuk hot-path ultra ekstrem. |
| **Monadic Chaining (`Either`, `Option`)** | - Kode deklaratif, bebas `null`, bebas side-effect exception.<br>- Traceable error handling. | - Biaya instansiasi wrapper (`Right`/`Left`, `Some`/`None`).<br>- Alokasi closure anonim di bytecode. | Terapkan Scala 3 `opaque type` atau library zero-allocation monadic primitives untuk skenario *low-latency high-frequency trading*. |
| **Megamorphic Pattern Matching** | - Type-safety terjamin via exhaustive verification saat build. | - Rantai branch `instanceof` yang panjang dapat merusak CPU branch predictor. | Optimalkan urutan matching: letakkan branch yang paling sering dieksekusi di posisi paling atas; manfaatkan integer IDs untuk `tableswitch`. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Kesalahan: Mengasumsikan Fungsi Bersifat Tail-Recursive Padahal Bukan
```scala
// ANTI-PATTERN: Tampak seperti tailrec, tapi eksekusi penambahan (+) terjadi SETELAH rekursi selesai
def sumList(list: List[Int]): Int = list match {
  case Nil => 0
  case head :: tail => head + sumList(tail) // JVM harus mempertahankan head di stack frame!
}
```
**Troubleshooting:**
Tambahkan anotasi `@tailrec`. Compiler Scala akan langsung melempar compile error:
`Cannot rewrite recursive call: it is not in tail position`.
Perbaikan:
```scala
@tailrec
def sumList(list: List[Int], acc: Int = 0): Int = list match {
  case Nil => acc
  case head :: tail => sumList(tail, acc + head) // Tail position
}
```

#### B. Kesalahan: Closure Leak pada Pattern Matching Guard
```scala
// ANTI-PATTERN: Guard condition yang mengeksekusi referensi mutable luar
var threshold = 100
orders.map {
  case Order(id, amount) if amount > threshold => // Data race dan non-referentially transparent!
    ...
}
```
**Troubleshooting:**
Gunakan fungsi murni tanpa capturing outer mutable scope. Selalu terapkan `-Xlint:infer-any` dan `-Werror` pada `scalacOptions` untuk memastikan tidak ada implicit promotion tipe yang tidak diinginkan.

#### C. Kesalahan: Megamorphic Call Site Degeneration pada Interface Polimorfik
Saat memanggil type class implementations yang memiliki $> 2$ concrete classes pada satu call-site loop, JVM JIT compiler mengubah optimasi dari *Bimorphic Inlining* menjadi *Megamorphic Inlining*. Hal ini menyebabkan *virtual method dispatch table lookups* (vtable lookup) berjalan lambat.
**Troubleshooting:** Gunakan *specialized Monomorphic loops* atau berikan petunjuk *inline* di Scala 3 menggunakan keyword `inline def`.

---

### 11. Best Practices (Production Checklist)

- [ ] **SBT Compiler Flags**: Selalu aktifkan flag berikut di `build.sbt`:
  ```scala
  scalacOptions ++= Seq(
    "-deprecation",
    "-feature",
    "-unchecked",
    "-Werror",
    "-Xfatal-warnings"
  )
  ```
- [ ] **Anotasi Rekursi Wajib**: Jangan pernah menulis method rekursi mandiri tanpa anotasi `@scala.annotation.tailrec`.
- [ ] **Exhaustiveness Guarantee**: Semua domain data ADT wajib diisolasi menggunakan `sealed trait` atau `enum` Scala 3; jangan biarkan *base class* terbuka (`open`) tanpa alasan yang valid.
- [ ] **Hindari Implicit Conversion Liar**: Gunakan mekanisme baru Scala 3 (`given` / `using`) secara eksplisit. Jangan melakukan `import scala.language.implicitConversions` secara global.
- [ ] **Gunakan `inline` di Hot-Path**: Tandai helper functional kecil atau type class accessor dengan `inline` guna memotong alokasi stack frame dan overhead closure.

---

### 12. Hands-on Practice

Buatlah proyek SBT dari terminal untuk membedah desugaring dan eksekusi ADT tailrec secara mendalam.

#### Struktur Direktori
```
hands-on/m02/
├── build.sbt
└── src/
    ├── main/
    │   └── scala/
    │       └── enterprise/
    │           └── engine/
    │               ├── CoreEngine.scala
    │               └── Main.scala
    └── test/
        └── scala/
            └── enterprise/
                └── engine/
                    └── CoreEngineSpec.scala
```

#### File: `hands-on/m02/build.sbt`
```scala
scalaVersion := "3.3.3"

name := "fp-advanced-foundations"
version := "1.0.0"

scalacOptions ++= Seq(
  "-deprecation",
  "-explain",
  "-Werror"
)

libraryDependencies ++= Seq(
  "org.scalameta" %% "munit" % "1.0.0" % Test
)
```

#### File: `hands-on/m02/src/main/scala/enterprise/engine/CoreEngine.scala`
```scala
package enterprise.engine

import scala.annotation.tailrec

object CoreEngine {

  // Sealed ADT
  sealed trait ComputeTask[+A]
  object ComputeTask {
    case class ComputeDone[A](result: A) extends ComputeTask[A]
    case class ComputeStep[A](next: () => ComputeTask[A]) extends ComputeTask[A]
  }

  // Trampoline Evaluator
  @tailrec
  def runComputation[A](task: ComputeTask[A]): A = task match {
    case ComputeTask.ComputeDone(res) => res
    case ComputeTask.ComputeStep(thunk) => runComputation(thunk())
  }

  // Deep recursive generator
  def buildDeepCalculation(depth: Int, acc: BigInt = 0): ComputeTask[BigInt] = {
    if (depth <= 0) ComputeTask.ComputeDone(acc)
    else ComputeTask.ComputeStep(() => buildDeepCalculation(depth - 1, acc + depth))
  }
}
```

#### File: `hands-on/m02/src/main/scala/enterprise/engine/Main.scala`
```scala
package enterprise.engine

object Main {
  def main(args: Array[String]): Unit = {
    println("=== Deep Stack Trampoline Runner ===")
    val largeDepth = 500000 // Jauh melampaui limit JVM stack (default ~10000)
    val task = CoreEngine.buildDeepCalculation(largeDepth)
    val result = CoreEngine.runComputation(task)
    println(s"Berhasil menghitung kedalaman $largeDepth tanpa StackOverflowError!")
    println(s"Hasil Akhir: $result")
  }
}
```

#### Langkah Eksekusi & Inspeksi Bytecode:
1. Buka terminal di `hands-on/m02/`.
2. Jalankan evaluasi via SBT:
   ```bash
   sbt run
   ```
3. Lakukan inspeksi bytecode compiled class untuk memverifikasi instruksi `goto`:
   ```bash
   javap -c target/scala-3.3.3/classes/enterprise/engine/CoreEngine$.class
   ```
   *Perhatikan label `tableswitch` atau loop branching `goto` pada method `runComputation`!*

---

### 13. Exercise

#### Level: Easy
1. **Target**: Mengubah rekursi non-tail menjadi pure `@tailrec`.
2. **Soal**: Diberikan fungsi rekursif pembalik elemen string list:
   ```scala
   def reverseList(l: List[String]): List[String] = l match {
     case Nil => Nil
     case x :: xs => reverseList(xs) :+ x // Alokasi O(N) stack & operator :+ yang lambat
   }
   ```
   Refaktorkan fungsi tersebut agar memenuhi anotasi `@tailrec` dan memiliki kompleksitas waktu $O(N)$ linear tanpa menggunakan operator `:+`.

#### Level: Medium
1. **Target**: For-Comprehension & Desugaring Engine.
2. **Soal**: Buat struktur data ADT `Result[+E, +A]` (mirip `Either`) buatan Anda sendiri dengan sub-tipe `Success[A]` dan `Failure[E]`. Implementasikan method `map`, `flatMap`, dan `withFilter`. Pastikan tipe tersebut dapat dikomposisikan secara native menggunakan sintaks Scala `for-comprehension` lengkap dengan pengujian filter guard `if`.

#### Level: Hard
1. **Target**: Church-Encoded List Trampoline Evaluation.
2. **Soal**: Implementasikan binary tree traversal (in-order, pre-order, post-order) untuk tree dengan kedalaman $100.000$ level yang tidak seimbang (*skewed binary tree*). Algoritma tidak boleh menggunakan loop `while` mutable, tidak boleh menggunakan list intermediate heap besar, dan harus murni disusun dengan menggabungkan custom `Trampoline` ADT yang menjamin pemrosesan selesai di bawah 2 detik tanpa JVM stack expansion.

---

### 14. Challenge

#### Skenario Kasus Kompleks: Dynamic State-Machine Expression AST Parser
Sebuah gateway sistem IoT enterprise menerima untaian string aturan logika dynamic assertion dari ribuan sensor pabrik. Aturan tersebut dikompilasi menjadi Abstract Syntax Tree (AST):

```scala
enum Expr:
  case Constant(v: Double)
  case Variable(name: String)
  case Add(lhs: Expr, rhs: Expr)
  case Sub(lhs: Expr, rhs: Expr)
  case Mul(lhs: Expr, rhs: Expr)
  case Div(lhs: Expr, rhs: Expr)
  case Condition(predicate: Expr, ifTrue: Expr, ifFalse: Expr)
```

**Tuntutan Masalah:**
1. Rantai ekspresi dapat memiliki kedalaman bersarang (*nesting*) hingga ratusan ribu level hasil kompilasi script rule visual pihak ketiga.
2. Operator pembagian (`Div`) berpotensi memicu pembagian dengan nol.
3. Variabel lingkungan dipasok lewat konteks `Map[String, Double]`.
4. Evaluator ekspresi AST Anda harus:
   - Berjalan murni fungsional (*referentially transparent*).
   - Memiliki proteksi dari `StackOverflowError` secara mutlak melalui teknik Trampoline / Heap-based evaluation.
   - Mengembalikan custom ADT penanganan kesalahan: `EvalError.DivisionByZero` atau `EvalError.MissingVariable(name)`.
   - Mengimplementasikan Type Class `Render[Expr]` yang mencetak representasi infix string matematis yang bersih tanpa tanda kurung yang tidak perlu.
   - **Constraint**: Dilarang menggunakan library eksternal (Cats, ZIO, etc.). Semua fondasi harus dibangun dari native Scala 3 murni.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. **Kondisi manakah yang mutlak diperlukan agar Scala compiler dapat mengaplikasikan tail-call elimination via anotasi `@tailrec`?**
   - A. Method harus berukuran di bawah 35 bytes bytecode.
   - B. Pemanggilan ke fungsi itu sendiri harus menjadi operasi terakhir yang dievaluasi sebelum fungsi me-return nilai.
   - C. Fungsi tidak boleh menerima argumen bertipe generic.
   - D. Method harus dideklarasikan sebagai `private[this]` di dalam class mutable.
   *Jawaban:* **B**. Compiler hanya dapat mengubah rekursi menjadi jump loop jika hasil dari pemanggilan rekursif langsung di-return tanpa ada operasi lain (seperti operasi aritmatika tambahan).

2. **Apa peran utama dari `withFilter` dalam konteks desugaring for-comprehension?**
   - A. Menjalankan filter secara paralel di thread pool terpisah.
   - B. Menghilangkan elemen null secara otomatis dari memori.
   - C. Menerapkan evaluasi predikat secara malas (*lazy*) guna menghindari alokasi intermediate collection baru.
   - D. Mengubah return type dari sequence menjadi singleton monad.
   *Jawaban:* **C**. Berbeda dengan `filter` biasa yang langsung menghasilkan collection baru di Heap, `withFilter` membuat view pembungkus yang memfilter elemen *on-the-fly* pada mapping berikutnya.

3. **Manakah pernyataan yang BENAR mengenai ADT bertipe Sum Type di Scala 3?**
   - A. Didefinisikan menggunakan `case class` tunggal yang memiliki banyak parameter fields.
   - B. Hanya merepresentasikan hubungan komposisi AND secara matematis.
   - C. Dapat direpresentasikan secara ringkas menggunakan konstruksi `enum` atau `sealed trait`.
   - D. Wajib ditandai dengan flag `@volatile`.
   *Jawaban:* **C**. Sum Type melambangkan disjoint-union (OR logic) yang secara native dipetakan menggunakan `enum` atau `sealed trait` dengan sub-class terbatas.

4. **Instruksi bytecode JVM apa yang biasanya dihasilkan oleh Scala compiler saat mengoptimasi fungsi beranotasi `@tailrec`?**
   - A. `invokevirtual`
   - B. `invokedynamic`
   - C. `goto` / conditional jump instructions
   - D. `athrow`
   *Jawaban:* **C**. Rekursi dieliminasi dari call stack dan ditransformasi menjadi loop lokal berbasis instruksi jump seperti `goto`, `ifeq`, atau `if_icmpgt`.

5. **Mengapa `sealed trait` memicu warning/error pada statement pattern match jika ada branch yang tidak terdefinisi?**
   - A. Karena compiler dapat melacak seluruh sub-tipe langsung di unit kompilasi (file) yang sama.
   - B. Karena JVM Runtime selalu memverifikasi byte boundaries saat startup.
   - C. Karena trait sealed otomatis menginjeksi method reflection `getClass`.
   - D. Karena tipe sealed hanya diizinkan memiliki tepat dua turunan class.
   *Jawaban:* **A**. Keyword `sealed` mengunci inheritance hanya di dalam satu file sumber, memungkinkan compiler mengevaluasi exhaustiveness secara tertutup dan deterministik.

#### Intermediate (5 Soal)
6. **Pada for-comprehension berikut, transformasi bytecode manakah yang tepat dieksekusi?**
   ```scala
   for {
     a <- listA
     b <- listB
   } yield a + b
   ```
   - A. `listA.map(a => listB.flatMap(b => a + b))`
   - B. `listA.flatMap(a => listB.map(b => a + b))`
   - C. `listA.zip(listB).map { case (a, b) => a + b }`
   - D. `listA.foreach(a => listB.foreach(b => a + b))`
   *Jawaban:* **B**. Generator awal yang diikuti oleh generator kedua selalu didesugar menjadi `flatMap` terluar dengan `map` pada generator terdalam yang membawa klausa `yield`.

7. **Mengapa Trampoline ADT mampu mencegah `StackOverflowError` pada algoritma rekursi mutual, sementara `@tailrec` gagal?**
   - A. Trampoline mengalokasikan frame call stack berukuran 64-bit yang lebih besar secara native.
   - B. Trampoline menangguhkan (*suspends*) evaluasi fungsi ke dalam Heap memory dan mengeksekusinya dalam loop datar linear.
   - C. Trampoline mematikan deteksi stack trace di JVM bytecode via unsafe native access.
   - D. Trampoline memanfaatkan compiler plugin C++ native interface (JNI).
   *Jawaban:* **B**. Trampoline mengubah alokasi eksekusi dari JVM Execution Call Stack yang terbatas ukurannya ke JVM Managed Heap yang jauh lebih longgar, dievaluasi melalui single runner loop.

8. **Perhatikan kode berikut. Apa risiko performa utama di hot-path JVM execution?**
   ```scala
   def calculate(values: List[Int], factor: Int): List[Int] = {
     values.map(_ * factor)
   }
   ```
   - A. Terjadi thread deadlock pada pool shared ForkJoin.
   - B. `factor` ditangkap oleh closure anonim (*capturing lambda*), memicu instansiasi objek `Function1` baru di heap setiap kali method dipanggil, serta boxing primitif `Int` ke `java.lang.Integer`.
   - C. Terjadi class-loading lockup di Metaspace.
   - D. Tipe data `List[Int]` akan otomatis diubah menjadi `Array[Object]` tak berhingga.
   *Jawaban:* **B**. Penangkapan variabel lingkungan (`factor`) mencegah compiler memakai singleton lambda instance, memaksa alokasi closure object di Heap, disertai biaya boxing/unboxing antara primitif JVM dan tipe generik Scala `List`.

9. **Apa perbedaan struktural mendasar antara Type Classes di Scala 3 dibanding Interface Subtyping berbasis OOP klasik?**
   - A. Subtyping OOP diverifikasi di runtime; Type Classes diverifikasi melalui dynamic proxy.
   - B. Type Classes memisahkan tipe data secara ortogonal dari fungsi/kemampuannya, mendukung *retroactive modeling* tanpa modifikasi kode asal.
   - C. Type Classes selalu menghasilkan alokasi memori yang lebih besar dibandingkan concrete object OOP.
   - D. Subtyping OOP menjamin kebenaran penanganan null, sedangkan Type Classes tidak.
   *Jawaban:* **B**. Pola Type Class mendukung *ad-hoc polymorphism* yang memungkinkan kita menambahkan kapabilitas baru pada pustaka/tipe data pihak ketiga tanpa mengubah class hierarkinya secara internal.

10. **Kapan implementasi pattern matching pada objek menghasilkan bytecode `tableswitch` dibanding `instanceof` sequence?**
    - A. Ketika mencocokkan string teks dengan panjang identik.
    - B. Ketika target pencocokan berupa integer berurutan atau Scala enum tags yang padat nilainya.
    - C. Ketika class yang dicocokkan memiliki anotasi `@unchecked`.
    - D. Ketika pencocokan melibatkan generic type extraction via Typeable runtime mirror.
    *Jawaban:* **B**. `tableswitch` diinstruksikan oleh compiler jika kunci pencocokan merupakan deret bilangan bulat konstan yang padat, menghasilkan lompatan instruksi berkecepatan konstan $O(1)$.

#### Production Scenarios (3 Soal)
11. **Skenario Kasus 1**: Sistem audit log perbankan yang mengandalkan pattern matching ADT bersarang mengalami lonjakan CPU latency spike saat throughput mencapai puncaknya. Profiling CPU via async-profiler mengindikasikan hotspot berada di blok evaluasi ADT:
    ```scala
    event match {
      case LogA(...) => ...
      case LogB(...) => ...
      // 40+ case classes turunan sealed trait
    }
    ```
    Langkah mitigasi arsitektur fungsional apakah yang paling tepat untuk menstabilkan CPU utilization?
    - A. Mengganti semua `case class` menjadi `java.lang.Object` dan melakukan casting manual via `asInstanceOf`.
    - B. Mengubah ADT menjadi integer-based discriminated tag (`enum` dengan constant ID indexing) agar compiler mentranslasikannya menjadi instruksi `tableswitch`, serta menyusun urutan branch matching berdasarkan metrik distribusi frekuensi traffic tertinggi.
    - C. Membungkus blok `match` di dalam `Future.successful` agar diproses asynchronous di thread lain.
    - D. Menghapus anotasi `sealed` pada base trait untuk mematikan compiler exhaustiveness checks.
    *Jawaban:* **B**. Rantai pencocokan tipe 40+ sub-class menghasilkan cascading `instanceof` jumps yang merusak *branch prediction buffer* CPU. Mengubahnya ke enum ordinal/integer-tagged indexing memungkinkan konversi ke `tableswitch` ($O(1)$ jump table).

12. **Skenario Kasus 2**: Pipeline batch data processing mengalami `OutOfMemoryError: Java heap space` setelah migrasi dari rekursi primitif ke library berbasis Trampoline kustom. Tim Anda mendeteksi bahwa jutaan objek `Trampoline.FlatMap` dan `More` mengotori Young Gen JVM memory. Bagaimanakah perbaikan arsitektur yang paling seimbang antara memory efficiency dan FP purity?
    - A. Memperbesar `-Xss` (Call Stack) menjadi 512MB dan kembali menggunakan rekursi tanpa mitigasi.
    - B. Mengubah strategi evaluasi menjadi hybrid: gunakan `@tailrec` linear berbasis *accumulator* dengan collection primitive array lokal di layer terdalam, dan batasi penggunaan Heap Trampoline hanya untuk pemanggilan batas layer modul non-tail (*coarse-grained boundaries*).
    - C. Mengganti JVM dengan runtime Node.js via Scala.js.
    - D. Memaksa pemanggilan `System.gc()` setiap 100 iterasi trampoline.
    *Jawaban:* **B**. Trampoline memiliki overhead alokasi pointer di heap. Pada layer eksekusi intensif mikro (hot loop), akumulator linear murni `@tailrec` jauh lebih superior karena menghasilkan zero allocation (reusing primitive frames di stack register JVM).

13. **Skenario Kasus 3**: Seorang software engineer menulis pipeline verifikasi pesanan menggunakan nested for-comprehension yang memuat 8 langkah monadic:
    ```scala
    for {
      step1 <- doStep1()
      step2 <- doStep2(step1)
      ...
      step8 <- doStep8(step7)
    } yield step8
    ```
    Meskipun kode bersih dan bekerja benar, profiling menunjukkan ribuan objek `Function1` dialokasikan secara berulang-ulang pada jalur transaksi ultra-low latency (SLA sub-millisecond). Solusi refaktorisasi arsitektur fungsional tingkat lanjut apakah yang wajib diambil?
    - A. Tulis ulang alur komputasi menggunakan `inline def` dengan macro expansion desugaring, atau ubah wrapper monadic menjadi zero-cost abstractions via `opaque types` untuk mengeliminasi instansiasi wrapper di JVM heap.
    - B. Ubah semua method menjadi `throw Exception` klasik agar tidak membutuhkan monadic return type.
    - C. Gunakan `Thread.sleep` untuk memberi waktu JVM garbage collector membersihkan closure.
    - D. Nonaktifkan JIT compilation dengan flag `-Xint`.
    *Jawaban:* **A**. Kombinasi `inline` methods dan Scala 3 `opaque types` memungkinkan compiler menghapus seluruh abstraction boundaries saat kompilasi, merekayasa bytecode agar beroperasi langsung pada tipe nilai dasar primitif tanpa alokasi heap wrapper sama sekali.

---

### 16. Summary

1. **Eliminasi Call Stack**: Anotasi `@tailrec` mengubah rekursi fungsi mandiri menjadi instruksi loop linear jump (`goto`) pada level bytecode JVM, menjamin penggunaan call stack $O(1)$.
2. **Trampoline Resilience**: Rekursi non-tail, mutual, dan AST graph traversal berskala masif dapat diselesaikan secara deterministik tanpa `StackOverflowError` dengan memindahkan komputasi tunda (*suspended thunks*) ke Heap Memory menggunakan pola Trampoline Monad.
3. **Mekanisme Desugaring**: For-Comprehension adalah *syntactic layer* yang ditransformasikan menjadi komposisi `flatMap`, `map`, dan `withFilter`. Memahami ekspansi internal ini sangat penting guna mengaudit performa dan alokasi closure di sistem throughput tinggi.
4. **ADT & Exhaustiveness**: Model data domain enterprise dibangun kokoh melalui Sum & Product Types (`enum` / `case class`). Garansi exhaustiveness compiler memusnahkan potensi runtime exception akibat data state yang tidak tertangani.
5. **Decoupled Architecture via Type Classes**: Pola Type Class di Scala 3 (`trait`, `given`, `using`) memisahkan representasi data dari perilakunya, menyediakan platform polimorfisme yang fleksibel, aman secara statis (*type-safe*), dan mudah diuji (*testable*).