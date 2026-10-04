# BAB 05: Sistem Pengetikan Tingkat Lanjut
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengonstruksi** fondasi formal sistem pengetikan Scala berbasis *Dependent Object Types* (DOT Calculus), termasuk *path-dependent types* dan *structural types*.
- **Mengimplementasikan** abstraksi tingkat lanjut menggunakan *Higher-Kinded Types* (HKT), *Type Lambdas*, dan *Match Types* untuk eliminasi duplikasi kode pada level tipe data (*type-level meta-programming*).
- **Menerapkan** pembatasan tipe (*Generalized Type Constraints*) menggunakan `=:=` dan `<:<` untuk mengontrol ketersediaan metode secara kondisional pada saat kompilasi.
- **Merancang Arsitektur *Tagless Final*** skala enterprise yang modular, independen dari *runtime effect* (ZIO/Cats Effect), dan menjamin *zero-cost abstraction* menggunakan *Opaque Type Aliases*.
- **Mengoptimalkan Kinerja Kompiler** dengan membedah dan memitigasi *diverging implicit expansion*, overhead kompilasi akibat recursive macro/type-level search, serta menangani jebakan *JVM Type Erasure*.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Scala Core**: Pemahaman mendalam tentang OOP dan FP di Scala, *pattern matching*, *trait linearization*, dan *sealed hierarchies*.
- **Scala Contextual Abstractions**: Mekanisme `given`, `using`, `extension methods`, dan *type class pattern* pada Scala 3 (atau `implicit val`/`implicit def` pada Scala 2.13).
- **JVM Bytecode Basics**: Memahami bagaimana JVM mengeksekusi *polymorphism*, *type erasure*, *boxing/unboxing* primitif, dan pemanggilan antarmuka via `invokeinterface`/`invokevirtual`.
- **Kategori Teori Dasar**: Mengetahui konsep *Functor*, *Applicative*, dan *Monad* sebagai abstraksi aljabar komputasi.

---

### 3. Concept & Internal Architecture

Sistem tipe Scala 3 berpijak pada fondasi matematis baru yang disebut **DOT Calculus** (*Dependent Object Types*), menggantikan fondasi ad-hoc Scala 2. Pemahaman terhadap DOT Calculus esensial untuk mengerti bagaimana *path-dependent types*, *type bounds*, dan *intersection/union types* diverifikasi keabsahannya (*soundness*).

```
                      DOT Calculus Foundation
                      
       +--------------------------------------------------+
       |                  Top Type (Any)                  |
       +--------------------------------------------------+
                                |
             +------------------+------------------+
             |                                     |
       Match Types /                         Path-Dependent
       Type Lambdas                          Types (x.Type)
             |                                     |
             +------------------+------------------+
                                |
                   Generalized Type Constraints
                           (=:=, <:<)
                                |
       +--------------------------------------------------+
       |               Bottom Type (Nothing)              |
       +--------------------------------------------------+
```

#### A. DOT Calculus dan Path-Dependent Types
Pada sistem *type-theoretic* konvensional (seperti System $F_{<:}$), tipe dan term dipisahkan secara kaku. Dalam DOT:
1. Setiap entitas adalah objek (`x`, `y`).
2. Objek dapat mengandung *type member* (contoh: `type Out`).
3. Tipe dapat mengacu pada jalur nilai stabil (*stable identifier path*), dinotasikan sebagai `x.Out`.

Jika nilai `x` dan `y` adalah instansiasi berbeda dari sebuah kelas yang memiliki `type Out`, maka `x.Out` dan `y.Out` diperlakukan sebagai **tipe yang sama sekali berbeda dan terisolasi secara kompilasi**, mencegah terjadinya kontaminasi data antar konteks objek yang berbeda.

#### B. Higher-Kinded Types (HKT) & Kind System
Scala mengklasifikasikan tipe data menggunakan *Kind*:
- Tipe dasar seperti `Int`, `String` memiliki kind `*` (Proper Type).
- Tipe pembungkus seperti `List`, `Option` memiliki kind `* -> *` (Type Constructor tingkat satu).
- Abstraksi seperti `Monad[F[_]]` mengonsumsi *type constructor* lain, menjadikannya Higher-Kinded Type dengan kind `(* -> *) -> *`.

Pada fase `Typer` di *compiler frontend*, Scala 3 menggunakan sintaks *Type Lambda* formal:
```scala
// Type lambda: memetakan tipe input T ke tipe terapan F[T, Error]
type Callback[T] = [E] =>> Either[E, T]
```
Kompiler memperlakukan *Type Lambda* sebagai fungsi anonim murni pada level tipe ($T \to Type$), yang direduksi (*normalized*) saat type checking sebelum memasuki tahap eliminasi.

#### C. Lifecycle Tipe pada Kompiler (Phase Architecture)
Kompiler `scalac` memproses tipe tingkat lanjut melalui *pipeline* terstruktur:

1. **Namer**: Mendaftarkan simbol tipe dan *variance flags* (`+`, `-`).
2. **Typer**: Melakukan *type inference*, ekspansi *match types*, verifikasi DOT constraints, serta resolusi `given`/`using`.
3. **PostTyper**: Menormalisasi tipe dan memverifikasi batas eksistensial.
4. **Erasure**: Menghapus (*erase*) semua argumen generik tingkat lanjut menjadi tipe batas atas (*upper bound*, lazimnya `java.lang.Object`).
5. **GenBCode**: Membangun *bytecode* JVM dengan menyisipkan instruksi *checkcast* eksplisit pada batas-batas *type boundary* yang telah diverifikasi aman pada fase *Typer*.

---

### 4. Why & What

| Fitur Tipe | Masalah yang Diselesaikan (Why) | Definisi Teknis (What) | Alternatif Konvensional |
| :--- | :--- | :--- | :--- |
| **Path-Dependent Types** | Menghindari tertukarnya ID atau domain data antar tenant/sesi yang berbeda. | Tipe yang terikat secara leksikal pada *stable reference* suatu objek (`path.Member`). | Primitive ID passing (`Long`, `UUID`) yang rawan *bug* relasi. |
| **Generalized Constraints (`=:=`, `<:<`)** | Mencegah pemanggilan fungsi jika parameter generik belum memenuhi kondisi tertentu. | Bukti tipe tingkat kompilasi (*type evidence*) yang diinjeksi via implisit. | *Runtime exception* (`throw new IllegalStateException()`). |
| **Higher-Kinded Types (HKT)** | Mencegah duplikasi algoritma logika domain antar tipe efek (`IO`, `Task`, `Future`). | Konstruktor tipe yang menerima konstruktor tipe lain sebagai parameter (`F[_]`). | Duplikasi kode (*boilerplate*) untuk setiap monad/wrapper. |
| **Match Types** | Transformasi tipe dinamis yang aman tanpa casting pada *generic programming*. | Tipe dependen yang mereduksi polimorfisme berdasarkan tipe argumennya via *pattern matching*. | *Dynamic reflection* atau `asInstanceOf[T]`. |

---

### 5. How (Workflow Detail)

Alur verifikasi dan resolusi sistem tipe tingkat lanjut pada fase kompilasi:

```
[Source Code]
      │
      ▼
┌──────────────┐
│ Phase: Namer │ ──► Bangun Symbol Table & Hierarki Tipe
└──────────────┘
      │
      ▼
┌──────────────┐      Cek Subtyping: A <:< B?
│ Phase: Typer │ ◄──► Expand Match Types & Type Lambdas
└──────────────┘      Resolusi Bukti Tipe (Type Evidence =:=)
      │
      ▼
┌────────────────┐
│ Phase: Erasure │ ──► Hapus representasi HKT & Dependent Types ke JVM Object
└────────────────┘     Sisipkan runtime Cast berbasis Upper Bounds
      │
      ▼
[JVM Bytecode]
```

Langkah sistematis menerapkan arsitektur berbasis tipe:
1. **Definisikan Domain Model dengan Phantom Types**: Beri tanda status data pada *compile-time* tanpa mengalokasikan memori runtime.
2. **Abstraksikan Efek menggunakan HKT (`F[_]`)**: Bungkus seluruh interaksi I/O dalam *Tagless Final algebra*.
3. **Beri Batasan dengan Type Evidence**: Kunci fungsi kritis menggunakan operator pembatas generik (`ev: A =:= B`).
4. **Bungkus Representasi Mentah dengan Opaque Type**: Sembunyikan tipe primitif di balik tipe domain untuk proteksi kompilasi tanpa alokasi objek tambahan (*zero-allocation wrapper*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Rel kereta vs Jalur Dependen
Bayangkan sebuah pabrik perakitan mobil.
- **Sistem Tipe Biasa**: Ada cetak biru generik untuk `Pintu` dan `Bodi`. Siapa pun bisa memasang pintu truk ke bodi sedan karena sama-sama turunan dari `KomponenMobil`, yang berujung pada malafungsi di jalan raya (*runtime error*).
- **Path-Dependent Types**: Cetak biru terikat pada jalur fisik pabrik: `sedanAssemblyLine.Pintu` hanya sah dipasang ke `sedanAssemblyLine.Bodi`. Memasang `truckAssemblyLine.Pintu` ke `sedanAssemblyLine` akan ditolak secara fisik oleh robot perakitan (*compiler error*).

```
         Path-Dependent Type Safety Guard

      Instansi: assemblyLineA              Instansi: assemblyLineB
 ┌──────────────────────────────┐     ┌──────────────────────────────┐
 │ type Chassis                 │     │ type Chassis                 │
 │ val myChassis: Chassis       │     │ val myChassis: Chassis       │
 └──────────────┬───────────────┘     └──────────────┬───────────────┘
                │                                    │
                ▼                                    ▼
       assemblyLineA.Chassis                assemblyLineB.Chassis
                │                                    │
                └─────────────── X ──────────────────┘
                    COMPILER REJECTS ASSIGNMENT
               (Type Mismatch: A.Chassis != B.Chassis)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Generalized Type Constraints (`=:=`)
Menyediakan fungsionalitas flatten hanya jika koleksi berisi elemen opsional:

```scala
// Definisi kontainer generik
final case class Container[A](value: A):
  // Metode ini HANYA tersedia jika parameter A adalah Option[Sub]
  def flatten[Sub](using ev: A =:= Option[Sub]): Container[Sub] =
    Container(ev(value).getOrElse(throw new NoSuchElementException("Empty option")))

@main def runSimple(): Unit =
  val nested = Container(Option("Enterprise Scala"))
  val flat = nested.flatten // Kompilasi Valid
  println(s"Result: ${flat.value}")

  val nonNested = Container(12345)
  // nonNested.flatten 
  // COMPILER ERROR: Cannot prove that Int =:= Option[Sub].
```

#### B. Practical Example: Zero-Allocation Phantom Typed Order Engine (Tagless Final)

```scala
import scala.concurrent.Future
import scala.concurrent.ExecutionContext.Implicits.global

// --- 1. Opaque Types (Zero-Cost Abstraction pada JVM) ---
object DomainTypes:
  opaque type OrderId = String
  object OrderId:
    def apply(raw: String): OrderId = raw
    extension (id: OrderId) def value: String = id

  opaque type Amount = BigDecimal
  object Amount:
    def apply(raw: BigDecimal): Amount = 
      require(raw > 0, "Amount must be strictly positive")
      raw
    extension (a: Amount) def value: BigDecimal = a

import DomainTypes.*

// --- 2. Phantom Types: Status Pemrosesan Transaksi ---
sealed trait OrderStatus
sealed trait Draft extends OrderStatus
sealed trait Validated extends OrderStatus
sealed trait Paid extends OrderStatus

// State machine pada level kompilasi
final case class Order[S <: OrderStatus](
  id: OrderId,
  amount: Amount,
  signature: Option[String] = None
)

// --- 3. Tagless Final Engine dengan Higher-Kinded Types ---
trait OrderRepository[F[_]]:
  def persist[S <: OrderStatus](order: Order[S]): F[Unit]
  def find(id: OrderId): F[Option[Order[Draft]]]

trait PaymentGateway[F[_]]:
  def processPayment(id: OrderId, amount: Amount): F[String]

// Business Engine yang memanfaatkan Generalized Type Constraints
class OrderProcessor[F[_]](using F: cats.Monad[F], repo: OrderRepository[F], gateway: PaymentGateway[F]):
  import cats.syntax.all.*

  // Validasi: Draft -> Validated
  def validate(order: Order[Draft]): F[Order[Validated]] =
    F.pure(Order[Validated](order.id, order.amount))

  // Bayar: Wajib berstatus Validated. Jika dioper Draft, compiler menolak.
  def pay[S <: OrderStatus](order: Order[S])(using ev: S =:= Validated): F[Order[Paid]] =
    gateway.processPayment(order.id, order.amount).flatMap { txSignature =>
      val paidOrder = Order[Paid](order.id, order.amount, Some(txSignature))
      repo.persist(paidOrder).as(paidOrder)
    }
```

---

### 8. Real World Case Study: Enterprise Core Banking Settlement

#### Konteks Masalah
Bank Sentral membutuhkan mesin *Settlement Engine* berlatensi rendah untuk memproses transaksi antar-partisipan (*clearing*). 
- **Persyaratan Kritis**:
  1. Dana tidak boleh berpindah antar-partisipan jika akun asal dan akun tujuan berasal dari *Ledger Ledger* yang tidak kompatibel (misalnya: *Fiat Settlement* vs *Digital Asset Settlement*).
  2. Alur akuntansi berpasangan (*Double-Entry Bookkeeping*) harus memverifikasi bahwa *debit* dan *credit* seimbang secara kompilasi, bukan hanya melalui *runtime validation*.
  3. Mengurangi *garbage collection* (GC) pauses dengan mencegah alokasi objek pembungkus (*wrapper instances*).

#### Solusi Arsitektural
Menerapkan kombinasi **Path-Dependent Types** (mengisolasi akun ke ledger tertentu) dan **Match Types** (memetakan representasi data ke tipe *primitive storage* yang paling efisien tanpa *boxing*).

```scala
// --- Core Architecture: Path-Dependent Ledger Engine ---

trait LedgerRegistry:
  // Tipe dependen unik untuk setiap instance LedgerRegistry
  type AccountToken
  type Balance
  
  def registerAccount(iban: String): AccountToken
  def getBalance(acc: AccountToken): Balance

class CentralBankSettlementSystem:
  // Pabrik Ledger terisolasi
  def createLedger(jurisdiction: String): LedgerRegistry = new LedgerRegistry {
    opaque type AccountToken = String
    type Balance = Long // Simpan dalam centilong (zero GC overhead)

    def registerAccount(iban: String): AccountToken = s"$jurisdiction:$iban"
    def getBalance(acc: AccountToken): Balance = 100_000_000L // Simulasi DB read
  }

  // Operasi Settlement: Menolak transfer jika kedua akun tidak berasal dari Ledger yang identik
  def settleCrossAccount(ledger: LedgerRegistry)(
    source: ledger.AccountToken,
    target: ledger.AccountToken,
    amount: Long
  ): Either[String, Unit] =
    println(s"Settling $amount between $source and $target on same registry context.")
    Right(())

// --- Match Types: Zero-Boxing Dynamic Representation ---
type PayloadType[Format] = Format match
  case "JSON"   => String
  case "BINARY" => Array[Byte]
  case "PROTO"  => Long // Simpan pointer native memory address

def dispatchMessage[F <: "JSON" | "BINARY" | "PROTO"](format: F, payload: PayloadType[F]): Unit =
  format match
    case "JSON"   => println(s"JSON String length: ${payload.asInstanceOf[String].length}")
    case "BINARY" => println(s"Binary size: ${payload.asInstanceOf[Array[Byte]].length}")
    case "PROTO"  => println(s"Native Memory Address: 0x${payload.asInstanceOf[Long].toHexString}")

// --- Eksekusi Produksi ---
object BankingExecution:
  def main(args: Array[String]): Unit =
    val engine = new CentralBankSettlementSystem()
    val fiatLedger = engine.createLedger("EU-SEPA")
    val cryptoLedger = engine.createLedger("CH-SWISS")

    val accA: fiatLedger.AccountToken = fiatLedger.registerAccount("ACC-001")
    val accB: fiatLedger.AccountToken = fiatLedger.registerAccount("ACC-002")
    val accSwiss: cryptoLedger.AccountToken = cryptoLedger.registerAccount("ACC-999")

    // 1. Kompilasi Valid: Berada pada path ledger yang sama
    engine.settleCrossAccount(fiatLedger)(accA, accB, 5000L)

    // 2. Pelanggaran Jalur: Mencegah cross-ledger mismatch pada saat kompilasi!
    // engine.settleCrossAccount(fiatLedger)(accA, accSwiss, 5000L)
    /*
      COMPILER ERROR:
      Found:    (accSwiss : cryptoLedger.AccountToken)
      Required: fiatLedger.AccountToken
      
      Perbedaan instance objek 'cryptoLedger' vs 'fiatLedger' dideteksi oleh DOT calculus!
    */

    // 3. Match type inference execution
    dispatchMessage("JSON", "{\"status\": \"OK\"}")
    dispatchMessage("BINARY", Array[Byte](0x10, 0x20))
    dispatchMessage("PROTO", 0x7FFFDEADBEEFL)
```

---

### 9. Trade-offs

Menggunakan sistem pengetikan tingkat lanjut memberikan garansi tinggi, namun memerlukan kompensasi teknis tertentu:

| Dimensi | Keuntungan (Advantage) | Biaya Teknis (Overhead / Cost) |
| :--- | :--- | :--- |
| **Performance (Runtime)** | *Near-zero runtime overhead*. Opaque types dan phantom types dieliminasi sepenuhnya saat kompilasi tanpa instansiasi objek baru. | Potensi pemanggilan *checkcast* berulang oleh JVM jika compiler menghasilkan bridge methods untuk invariant types. |
| **Compilation Latency** | Deteksi kesalahan semantik sejak dini sebelum unit test berjalan. | **Waktu kompilasi naik eksponensial** pada implicit tree search yang dalam atau match types dengan cabikan rekursif intensif. |
| **Cognitive Load** | Penegakan kontrak arsitektural yang ketat; *onboarding engineer* baru terlindungi dari membuat logika ilegal. | Tingkat kesulitan rekrutmen tinggi. Pesan kesalahan compiler (*type mismatch errors*) menjadi sangat panjang dan sulit didekomposisi. |
| **Binary Compatibility** | Menghasilkan kode bebas dependensi library refleksi runtime eksternal. | Modifikasi internal tipe pada library dapat merusak *binary backward compatibility* (*ABI break*) bagi downstream dependensi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Diverging Implicit Expansion pada HKT / Type Classes
```scala
// ANTI-PATTERN
trait Serializer[T]
given autoListSerializer[T](using s: Serializer[T]): Serializer[List[T]] = ???
given fallbackSerializer[T]: Serializer[T] = ???

// Jika compiler menemukan ambiguitas atau recursive search tak terbatas:
// ERROR: Diverging implicit search has run out of gas!
```
*Solusi*: Gunakan anotasi `scala.annotation.implicitAmbiguous` atau prioritaskan implicit resolution dengan memisahkan hirarki *base trait* (LowPriorityImplicits pattern).

#### Kesalahan 2: Type Erasure Trap pada Pattern Matching
```scala
// SALAH
def process(payload: Any): Unit = payload match
  case list: List[String] => println("List of Strings") // Unchecked type check warning!
  case list: List[Int]    => println("List of Ints")    // Never reached! Erased to List[_]

// BENAR: Gunakan Typeable / ClassTag / TypeTest
import scala.reflect.TypeTest

inline def processSafe[T](items: List[Any])(using tt: TypeTest[Any, T]): List[T] =
  items.collect { case tt(extracted) => extracted }
```

#### Kesalahan 3: Variance Leakage
Mencoba mengekspos tipe kovarian `+T` pada posisi parameter metode kontravarian:
```scala
// SALAH: Compiler Error: Covariant type T occurs in contravariant position in parameter a
// trait Channel[+T]:
//   def write(a: T): Unit 

// BENAR: Berikan batasan bawah (Lower Bound)
trait Channel[+T]:
  def write[U >: T](a: U): Unit
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Aktifkan Strict Compiler Flags**: Pasang `-Xfatal-warnings`, `-Werror`, `-explain`, dan `-Vtype-diffs` pada `build.sbt` agar compiler membongkar hierarki tipe yang keliru secara visual.
- [ ] **Gunakan Opaque Types menggantikan Value Classes (`extends AnyVal`)**: Menghilangkan alokasi runtime JVM secara deterministik tanpa resiko *unforeseen boxing* pada array atau generic context.
- [ ] **Batasi Rekursi Match Types**: Sertakan kasus terminasi eksplisit pada match types untuk mencegah kompilasi macet (*infinite compilation loop*).
- [ ] **Prioritaskan Hermetic Traits**: Jadikan *trait* bertipe dependen sebagai `sealed` atau `final` untuk mempermudah compiler membuktikan *exhaustiveness checking*.
- [ ] **Minimalkan Exposed Higher-Kinded Types ke API Pengguna Akhir**: Sembunyikan *Tagless Final* (`F[_]`) di balik layer aplikasi atau *facade pattern*; pengguna akhir modul sebaiknya hanya berinteraksi dengan tipe konkret atau domain ADT.

---

### 12. Hands-on Practice

Siapkan struktur direktori pada terminal Anda:

```bash
mkdir -p hands-on/m02/src/main/scala/enterprise/types
mkdir -p hands-on/m02/project
```

#### 1. Buat file `hands-on/m02/build.sbt`:
```scala
scalaVersion := "3.3.3"

name := "advanced-typing-engine"
version := "1.0.0"

scalacOptions ++= Seq(
  "-deprecation",
  "-feature",
  "-unchecked",
  "-Xfatal-warnings",
  "-explain",
  "-Vtype-diffs"
)

libraryDependencies ++= Seq(
  "org.typelevel" %% "cats-core" % "2.10.0"
)
```

#### 2. Buat file `hands-on/m02/src/main/scala/enterprise/types/Pipeline.scala`:
Implementasikan *Type-Safe State Machine* untuk alur audit kepatuhan (*Compliance Engine*):

```scala
package enterprise.types

sealed trait Step
sealed trait Ingestion extends Step
sealed trait Enriched extends Step
sealed trait Sanitized extends Step

// Data Pipeline Envelope
final case class DataRecord[S <: Step, +Payload](val data: Payload):
  def map[NewPayload](f: Payload => NewPayload): DataRecord[S, NewPayload] =
    DataRecord[S, NewPayload](f(data))

object DataPipeline:
  // Operator kompilasi kondisional: Hanya record yang telah berstatus Ingestion yang boleh di-enrich
  def enrich[T](record: DataRecord[Ingestion, T])(metadata: String): DataRecord[Enriched, (T, String)] =
    DataRecord[Enriched, (T, String)]((record.data, metadata))

  // Hanya record yang telah di-enrich yang boleh di-sanitize
  def sanitize[T](record: DataRecord[Enriched, (T, String)]): DataRecord[Sanitized, T] =
    DataRecord[Sanitized, T](record.data._1)

@main def runPipeline(): Unit =
  val raw = DataRecord[Ingestion, String]("RAW_CUSTOMER_PAYLOAD_102")
  val enriched = DataPipeline.enrich(raw)("METADATA_SRC_EU")
  val clean = DataPipeline.sanitize(enriched)

  println(s"Pipeline processed successfully: ${clean.data}")

  // UJI COBA ILLEGAL CALL:
  // DataPipeline.sanitize(raw)
  // Kompiler akan menggagalkan build sebelum tahap pembuatan JAR!
```

Eksekusi proyek melalui terminal:
```bash
cd hands-on/m02
sbt compile
sbt run
```

---

### 13. Exercise

#### Level Easy
Ubah tipe primitif string ID `CustomerId` dan `OrderId` menjadi `opaque type` di dalam sebuah namespace `BankingIdentifiers`. Tulis ekstensi metode untuk memvalidasi bahwa `CustomerId` tidak boleh kosong, dan pastikan instansiasi ilegal memicu kompilasi gagal saat dipertukarkan.

#### Level Medium
Buat sebuah struktur data aljabar `HeterogeneousList` (HList) sederhana menggunakan pasangan rekursif tipe:
```scala
sealed trait HList
final case class HCons[+H, +T <: HList](head: H, tail: T) extends HList
case object HNil extends HList
```
Tulis *Match Type* bernama `Length[L <: HList] <: Int` yang menghitung total elemen di dalam `HList` pada tingkat kompilasi.

#### Level Hard
Rancang modul *Database Connection Pool* menggunakan **Path-Dependent Types** di mana objek `Transaction` terikat langsung secara eksklusif ke instans `DatabaseClient`. Buat metode `commit(tx: client.Transaction)` yang secara mutlak menolak objek transaksi yang dihasilkan dari instans klien basis data lain, tanpa melakukan perbandingan *UUID* atau logika pengkondisian di *runtime*.

---

### 14. Challenge

**Studi Kasus: Zero-Overhead Type-Level Circuit Breaker**

Buat sebuah library *stateful action* mini bernama `TypeSafeCircuitBreaker`. 
- **Persyaratan**:
  1. Circuit breaker harus memiliki 3 keadaan phantom: `Closed`, `Open`, `HalfOpen`.
  2. Eksekusi metode `execute[S <: State](action: => F[A])` hanya diizinkan secara kompilasi saat breaker berada pada status `Closed` atau `HalfOpen`.
  3. Gunakan *generalized type constraints* `=:=` dan *type-level negation* (menggunakan bukti implicit ambiguity trick) sehingga jika dipanggil pada status `Open`, kompilasi gagal dengan pesan error khusus: `"CRITICAL: Cannot execute RPC call while Circuit Breaker is in OPEN state."`
  4. Seluruh transisi status tidak boleh menyebabkan alokasi objek state baru pada JVM Heap (wajib mempertahankan *zero-cost runtime profile*).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa perbedaan mendasar antara `*` (Proper Type) dan `* -> *` (Type Constructor) dalam kind system Scala?
2. Kapan waktu eksekusi validasi untuk *Generalized Type Constraint* `=:=`?
3. Mengapa JVM memerlukan proses *Type Erasure* pada fase akhir kompilasi Scala?
4. Apa manfaat performa dari Scala 3 `opaque type` dibandingkan Scala 2 `extends AnyVal`?
5. Tuliskan notasi *Type Lambda* di Scala 3 untuk mengabaikan parameter tipe pertama dari `Either[A, B]` sehingga dapat diperlakukan sebagai Functor atas tipe `B`!

#### Intermediate (5 Soal)
6. Diberikan deklarasi: `class Box[+A]`. Mengapa metode `def set(a: A): Box[A]` ditolak oleh compiler? Jelaskan secara aturan variansi!
7. Bagaimana *DOT Calculus* menjamin isolasi tipe dependen ketika dua objek memiliki anggota tipe struktural yang identik?
8. Mengapa rekursi tanpa kondisi basis yang jelas pada *Match Types* dapat menyebabkan kompiler `scalac` mengalami `StackOverflowError`?
9. Bagaimana cara kerja internal dari bukti tipe `ev: A =:= B` saat memetakan nilai dari tipe `A` ke tipe `B`?
10. Sebutkan satu skenario di mana *structural typing* (`scala.Selectable`) menghasilkan dampak performa negatif (*performance penalty*) yang signifikan pada runtime!

#### Production Scenarios (3 Soal Kasus)
11. **Kasus 1**: Sistem settlement perbankan Anda mengalami *OutOfMemoryError: Metaspace* secara berkala setelah deployment modul microservice baru yang menggunakan banyak HKT dan macro derivation. Apa akar masalah arsitektural di level bytecode, dan bagaimana mitigasinya?
12. **Kasus 2**: Tim Anda mengeluhkan durasi kompilasi CI/CD melonjak dari 4 menit menjadi 32 menit setelah mengadopsi abstraksi *Tagless Final* dengan banyak layer type class derivation. Pendekatan profiling compiler apa yang harus Anda lakukan untuk menemukan *culprit* pengetikannya?
13. **Kasus 3**: Sebuah antarmuka RPC pihak ketiga mengirimkan data JSON dinamis yang strukturnya berubah tergantung parameter `version: Int`. Bagaimana Anda merancang sistem decoder menggunakan Scala 3 *Match Types* untuk mencegah *runtime cast* saat memetakan payload versi v1 dan v2?

---

### 16. Summary

- **DOT Calculus** adalah jangkar matematis Scala 3 yang merekonsiliasi subtyping dan pemrograman berbasis objek ke dalam model verifikasi tipe dependen yang aman (*type-sound*).
- **Higher-Kinded Types (HKT)** dan **Type Lambdas** memungkinkan penulisan pustaka tingkat tinggi yang terisolasi dari *runtime effect library* konkret melalui pola *Tagless Final*.
- **Generalized Type Constraints (`=:=`, `<:<`)** menyediakan mekanisme pertahanan mutlak di tingkat kompilasi, mengeliminasi cabang logika defensif di level *runtime*.
- **Opaque Types** menghadirkan pemodelan *Domain-Driven Design* (DDD) tingkat lanjut dengan jaminan nol alokasi tambahan di atas JVM heap, memaksimalkan efisiensi *throughput* dan latensi sistem.
- Keunggulan pengetikan tingkat lanjut harus diseimbangkan secara matang dengan memperhatikan waktu kompilasi, kompleksitas *codebase*, serta *maintainability* jangka panjang dalam rekayasa perangkat lunak skala korporasi.