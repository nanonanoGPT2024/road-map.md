# BAB 06: Abstraksi Kontekstual & Type Classes
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis (C4)** mekanisme internal desugaring kompiler Scala 3 pada konstruksi `given`, `using`, dan `extension` hingga ke representasi Java Bytecode.
- **Mengevaluasi (C5)** trade-off performa antara alokasi runtime, boxing primitif, dan biaya kompilasi (*compile-time implicit search depth*) pada arsitektur berbasis Type Class.
- **Merancang (C6)** sistem tipe terdistribusi enterprise-grade menggunakan Tagless Final Pattern yang dikombinasikan dengan Context Functions (`?=>`), Type Class Derivation (`Mirror`), dan Type Class Coherence yang ketat.
- **Mengidentifikasi dan Memitigasi (C4/C5)** masalah kritis pada skala produksi seperti *diverging implicit expansion*, *ambiguous givens*, dan kebocoran memori akibat siklus referensi kontekstual.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- Konsep dasar Scala 3: Immutability, Pattern Matching, Case Classes, Enums.
- Bab 06 Module 01: Sintaks dasar `given`, klausa `using`, `summon[...]`, dan Extension Methods.
- Pemahaman solid tentang Higher-Kinded Types (HKT) seperti `F[_]` dan subtyping vs parametric polymorphism.
- Pemahaman dasar JVM: Call stack, heap allocation, class loading, dan Java Bytecode level dasar (`invokevirtual`, `invokestatic`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Kompilasi: Desugaring Scala 3 ke JVM Bytecode
Scala 3 merombak total fondasi resolusi implisit Scala 2 yang bertumpu pada satu kata kunci `implicit`. Pada Scala 3, pemisahan dilakukan secara semantik antara intensi data kontekstual (`given`/`using`) dan konversi tipe kontekstual.

Perhatikan deklarasi berikut:
```scala
trait JsonEncoder[A]:
  def encode(value: A): String

given intEncoder: JsonEncoder[Int] with
  def encode(value: Int): String = value.toString

def serialize[A](value: A)(using encoder: JsonEncoder[A]): String =
  encoder.encode(value)
```

Di balik layar, Scala 3 Compiler (Dotty) melakukan desugaring menjadi struktur ekuivalen berikut sebelum memasuki fase penulisan bytecode:
1. `given intEncoder: JsonEncoder[Int]` diubah menjadi kelas anonim atau singleton objek yang mengimplementasikan `JsonEncoder[Int]`, dilengkapi dengan accessor method statis atau member terkompilasi:
   ```scala
   final class anon$1 extends JsonEncoder[Int] {
     def encode(value: Int): String = java.lang.String.valueOf(value)
   }
   final def intEncoder: JsonEncoder[Int] = new anon$1() // Atau singleton cache
   ```
2. Parameter `(using encoder: JsonEncoder[A])` didegradasi menjadi parameter argumen eksplisit standar:
   ```scala
   def serialize[A](value: A, encoder: JsonEncoder[A]): String =
     encoder.encode(value)
   ```
3. Pemanggilan `serialize(42)` diubah menjadi `serialize[Int](42, intEncoder)`.
4. JVM memprosesnya sebagai invocations standar (`INVOKEVIRTUAL` / `INVOKEINTERFACE`). Tidak ada overhead *reflection* pada runtime.

```
+--------------------------------------------------------------------+
|                         SCALA 3 SOURCE CODE                        |
|   given stringEncoder: JsonEncoder[String] ...                     |
|   def write[A: JsonEncoder](v: A): String                          |
+--------------------------------------------------------------------+
                                 |
                     [Typer & Desugar Phase]
                                 v
+--------------------------------------------------------------------+
|                      INTERMEDIATE TASTY AST                        |
|   val given_JsonEncoder_String: JsonEncoder[String] = ...          |
|   def write[A](v: A)(using x$1: JsonEncoder[A]): String            |
+--------------------------------------------------------------------+
                                 |
                      [Erasure & GenBCode]
                                 v
+--------------------------------------------------------------------+
|                           JVM BYTECODE                             |
|   INVOKESTATIC Module$.given_JsonEncoder_String()LJsonEncoder;    |
|   INVOKEVIRTUAL Module$.write(Ljava/lang/Object;LJsonEncoder;)     |
+--------------------------------------------------------------------+
```

#### 3.2. Algoritma Pencarian Implisit (Implicit Scope Search)
Kompiler mencari instans `given` melalui fase terurut:
1. **Current Lexical Scope**: Identifiers lokal, enclosing class/object, imported givens (`import p.given`, `import p._`).
2. **Implicit Scope of Type Arguments**: Companion object dari tipe target `A`, companion object dari Type Class `JsonEncoder`, dan companion object dari supertype atau enclosing types jika ada.

Jika terdapat lebih dari satu kandidat yang cocok pada level prioritas yang sama, Dotty menerapkan *Specificity Rule*:
- Subtipe lebih spesifik dari supertipe.
- Metode/ekspresi tanpa konversi lebih spesifik dari yang memerlukan konversi.
- Jika ambiguitas tidak dapat diurai, proses kompilasi dihentikan dengan error `Ambiguous Given Instances`.

#### 3.3. Zero-Cost Abstraction via `inline given`
Instansiasi Type Class tradisional menyebabkan alokasi heap untuk objek wrapper. Scala 3 menyediakan `inline given` untuk mengeliminasi instansiasi runtime:
```scala
trait IdentityCheck[A]:
  def isSame(x: A, y: A): Boolean

inline given IdentityCheck[Long] with
  inline def isSame(x: Long, y: Long): Boolean = x == y
```
Dengan memanfaatkan `inline`, Dotty menyisipkan instruksi perbandingan primitif (`lcmp` + jump) langsung pada call site, sepenuhnya meniadakan alokasi heap untuk objek Type Class dan *vtable indirection*.

---

### 4. Why & What

| Dimensi | Subtype Polymorphism (OOP Tradisional) | Ad-Hoc Polymorphism (Type Classes) |
| :--- | :--- | :--- |
| **Binding Time** | Runtime dispatch via vtable. | Resolusi compile-time via implicit evidence insertion. |
| **Extensibility** | Closed: Tidak bisa menambah supertype ke class third-party (`java.time.Instant`, `java.lang.String`). | Open: Menambahkan kapabilitas ke tipe apa pun tanpa memodifikasi kode sumber tipe tersebut. |
| **Object Pollution**| Objek membawa semua metode di dalamnya (God Object anti-pattern). | Pemisahan murni antara struktur data (Data/State) dan perilaku (Behavior). |
| **Binary Size & Heap**| Overhead objek relatif kecil, namun desain hierarki kaku. | Membutuhkan passing argumen sintetis (dapat di-inline untuk meniadakan overhead). |
| **Type Safety** | Sering membutuhkan upcasting/downcasting (`asInstanceOf`) saat menangani tipe homogen/heterogen. | Mempertahankan tipe presisi (*full type preservation*) tanpa pengecekan tipe runtime. |

---

### 5. How (Workflow Detail)

Alur kerja implementasi Type Class pada level arsitektur produksi:

```
[1. Definisi Trait Type Class] (Mendefinisikan contract fungsional murni)
               |
               v
[2. Sediakan Companion Default Instances] (Coherent Scope: fallback level dasar)
               |
               v
[3. Ekspos API Kontekstual & Extension Syntax] (Injeksi DSL ke domain type)
               |
               v
[4. Bangun Derivation Engine] (Compile-time code generation via scala.deriving.Mirror)
               |
               v
[5. Inject Contextual Dependencies di Boundary Produksi] (Main / Akka / Http4s Layer)
```

1. **Definisikan Trait**: Pastikan invariant matematis atau operasional terdokumentasi (e.g., Semigroup associativity).
2. **Sediakan Coherent Instances**: Letakkan instans standar di Companion Object dari trait tersebut guna mencegah import manual yang redundan.
3. **Ekspos Extension Methods**: Pasang *syntax sugar* menggunakan blok `extension` pada Type Class.
4. **Implementasikan Derivasi Otomatis**: Hindari boilerplate repetitif dengan `derives` untuk tipe komposit (*product* & *sum types*).
5. **Konsumsi via Bounds / Using Clauses**: Gunakan Context Bounds (`[A: TypeClass]`) untuk kode deklaratif, atau `(using tc: TypeClass[A])` jika instans perlu diakses secara langsung.

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem kelistrikan internasional:
- **Tipe Data (`A`)** adalah perangkat elektronik lokal (colokan laptop tipe UK, US, atau Schuko EU). Anda tidak dapat membongkar sirkuit internal laptop untuk mengubah bentuk colokannya secara dinamis.
- **Type Class (`PowerAdapter[A]`)** adalah cetak biru adaptor konversi ke soket universal.
- **`given` Instance** adalah adaptor fisik yang disediakan oleh hotel secara otomatis di laci meja Anda.
- **`using` Clause** adalah stopkontak dinding hotel yang mensyaratkan: *"Anda hanya boleh mencolokkan laptop jika ada adaptor kompatibel yang terverifikasi."*

```
               [ Call Site: compile(Device) ]
                              |
        Does Device natively fit International Socket? NO!
                              |
             [ Compiler Implicit Resolution Scope ]
                              |
    +-------------------------+-------------------------+
    |                                                   |
[Search Lexical Scope]                      [Search Companion Scope]
Looking for:                                Looking for:
`given PowerAdapter[Device]`                `PowerAdapter.derived`
    |                                                   |
    +-------------------------+-------------------------+
                              |
                   FOUND: Valid Adapter
                              |
            [ Desugared Bytecode Generation ]
           compile(Device, given_PowerAdapter)
                              |
               ==> Safe Execution on JVM <==
```

---

### 7. Practical Implementation Code

#### 7.1. Definisi & Desain Low-Allocation Type Class
Berikut adalah sistem serialisasi biner *high-throughput* zero-allocation untuk streaming pipeline:

```scala
package enterprise.core.serialization

import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets
import scala.deriving.Mirror
import scala.compiletime.{erasedValue, summonInline}

// 1. Core Type Class Definition
trait BinarySerializer[A]:
  def byteSize(value: A): Int
  def serialize(value: A, buffer: ByteBuffer): Unit

object BinarySerializer:
  // Accessor helper
  inline def apply[A](using serializer: BinarySerializer[A]): BinarySerializer[A] = serializer

  // Primitives Instances (Coherent Scope)
  given intSerializer: BinarySerializer[Int] with
    inline def byteSize(value: Int): Int = java.lang.Integer.BYTES
    inline def serialize(value: Int, buffer: ByteBuffer): Unit = 
      buffer.putInt(value)

  given longSerializer: BinarySerializer[Long] with
    inline def byteSize(value: Long): Int = java.lang.Long.BYTES
    inline def serialize(value: Long, buffer: ByteBuffer): Unit = 
      buffer.putLong(value)

  given stringSerializer: BinarySerializer[String] with
    def byteSize(value: String): Int = 
      val bytes = value.getBytes(StandardCharsets.UTF_8)
      java.lang.Integer.BYTES + bytes.length
      
    def serialize(value: String, buffer: ByteBuffer): Unit = 
      val bytes = value.getBytes(StandardCharsets.UTF_8)
      buffer.putInt(bytes.length)
      buffer.put(bytes)

  // 2. Syntax Enrichment via Extensions
  extension [A](value: A)(using serializer: BinarySerializer[A])
    def toBinary: Array[Byte] =
      val totalSize = serializer.byteSize(value)
      val buffer = ByteBuffer.allocate(totalSize)
      serializer.serialize(value, buffer)
      buffer.array()

  // 3. Compile-time Derivation for Product Types (Case Classes)
  inline def summonAll[T <: Tuple]: List[BinarySerializer[?]] =
    inline erasedValue[T] match
      case _: EmptyTuple => Nil
      case _: (t *: ts)  => summonInline[BinarySerializer[t]] :: summonAll[ts]

  inline given derived[A](using m: Mirror.ProductOf[A]): BinarySerializer[A] =
    val elemSerializers = summonAll[m.MirroredElemTypes]
    new BinarySerializer[A]:
      def byteSize(value: A): Int =
        val product = value.asInstanceOf[Product]
        var i = 0
        var total = 0
        while i < product.productArity do
          val elem = product.productElement(i)
          val serializer = elemSerializers(i).asInstanceOf[BinarySerializer[Any]]
          total += serializer.byteSize(elem)
          i += 1
        total

      def serialize(value: A, buffer: ByteBuffer): Unit =
        val product = value.asInstanceOf[Product]
        var i = 0
        while i < product.productArity do
          val elem = product.productElement(i)
          val serializer = elemSerializers(i).asInstanceOf[BinarySerializer[Any]]
          serializer.serialize(elem, buffer)
          i += 1
```

---

### 8. Real-World Case Study: Enterprise Distributed Ledger Event Pipeline

#### Skenario
Sebuah platform Core Banking menangani event audit keuangan. Persyaratan non-fungsional:
- Mengisolasi Tenant ID dan Security Context secara implisit (mencegah *argument drilling*).
- Menjamin validasi kepatuhan (*compliance rule*) pada saat kompilasi.
- Logging terstruktur otomatis yang memperhitungkan PII (*Personally Identifiable Information*) Redaction.

#### Arsitektur Solusi
Menggabungkan **Tagless Final**, **Context Functions (`?=>`)**, dan **Contextual Type Classes**.

```scala
package enterprise.banking.ledger

import java.time.Instant
import java.util.UUID

// --- Domain Models ---
case class AuditContext(traceId: UUID, tenantId: String, timestamp: Instant)
case class TransactionPayload(sourceAccount: String, targetAccount: String, amountInCents: Long)

// --- PII Redaction Type Class ---
trait Redactable[A]:
  def sanitize(value: A): String

object Redactable:
  given Redactable[String] with
    def sanitize(value: String): String = 
      if value.length <= 4 then "****" 
      else s"***${value.takeRight(4)}"

  given Redactable[TransactionPayload] with
    def sanitize(v: TransactionPayload)(using strRedactor: Redactable[String]): String =
      s"TransactionPayload(source=${strRedactor.sanitize(v.sourceAccount)}, target=${strRedactor.sanitize(v.targetAccount)}, amount=${v.amountInCents})"

// --- Contextual Functional Pipeline via Context Functions ---
type Audited[A] = AuditContext ?=> A

trait LedgerAuditService[F[_]]:
  def recordEvent(eventName: String, payload: TransactionPayload): Audited[F[Unit]]

// Implementation for Production Engine
class ProductionLedgerService extends LedgerAuditService[Either[Throwable, *]]:
  override def recordEvent(eventName: String, payload: TransactionPayload): Audited[Either[Throwable, Unit]] =
    val ctx = summon[AuditContext]
    val redactor = summon[Redactable[TransactionPayload]]
    
    // Structured Safe Ledger Log Payload
    val logOutput = 
      s"""|{"event": "$eventName",
          | "trace_id": "${ctx.traceId}",
          | "tenant_id": "${ctx.tenantId}",
          | "timestamp": "${ctx.timestamp}",
          | "data": ${redactor.sanitize(payload)}}""".stripMargin.replaceAll("\n", "")

    // Simulasi penulisan ke Kafka audit topic
    Right(println(s"[KAFKA PRODUCE: audit-topic] => $logOutput"))

// --- Execution Harness ---
object EnterpriseRunner:
  def main(args: Array[String]): Unit =
    val service = new ProductionLedgerService()
    
    // Security Context diinject secara murni di layer boundary
    given currentContext: AuditContext = AuditContext(
      traceId = UUID.randomUUID(),
      tenantId = "TENANT-ID-BANK-CORP-492",
      timestamp = Instant.now()
    )

    val payload = TransactionPayload(
      sourceAccount = "ACC-ID-992384112",
      targetAccount = "ACC-ID-551239912",
      amountInCents = 150_000_000L
    )

    // Call site bersih dari drilling parameter context
    val result = service.recordEvent("INTER_BANK_TRANSFER", payload)
    
    result match
      case Right(_) => println("[INFO] Event audit berhasil diamankan.")
      case Left(err) => System.err.println(s"[ERROR] Gagal audit: ${err.getMessage}")
```

---

### 9. Trade-Offs & Analisis Mendalam

| Pilihan Desain | Keuntungan | Biaya / Kerugian |
| :--- | :--- | :--- |
| **Monolithic Instances vs Micro Type Classes** | Micro type classes (e.g., `Eq`, `Show`) mematuhi *Single Responsibility Principle*. | Penurunan performa kompilasi karena pohon resolusi implisit menjadi jauh lebih dalam (*deep search tree*). |
| **`derives` (Compile-time Mirroring)** | Menghilangkan kebutuhan penulisan puluhan baris boilerplate instansiasi manual per DTO. | Menambah waktu proses fase kompilasi Makro/Typer; kegagalan resolusi tipe turunan menghasilkan compiler trace yang panjang. |
| **Orphan Instances** | Memungkinkan mendefinisikan instans Type Class untuk tipe pihak ketiga di modul kita sendiri. | **Merusak Type Class Coherence**. Potensi runtime mismatch atau duplikasi tak terprediksi jika dependensi lain melakukan hal serupa. |
| **Context Functions (`?=>`)** | Mengeliminasi *parameter drilling* (menghindari passing token, correlation ID, atau context di 10 layer fungsi). | Berpotensi membingungkan pembaca kode junior jika digunakan berlebihan; stack trace error runtime menyembunyikan injeksi parameter. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Diverging Implicit Expansion
- **Gejala**: Kompilasi gagal dengan pesan `diverging implicit expansion for type ... starting at given instance ...`
- **Penyebab**: Definisi siklis rekursif tanpa basis terminasi atau parameter bertipe sama yang saling membutuhkan.
- **Solusi**: Pastikan ada terminating base-case untuk tipe primitif/akar dan batasi kedalaman derivasi menggunakan type annotation eksplisit.

#### 10.2. Instance Ambiguity Karena Multipel Impor
- **Gejala**: `Found 2 matches: ... both match type JsonEncoder[User]`
- **Penyebab**: Instans dideklarasikan di dua objek utilitas berbeda dan keduanya diimpor dengan `import package._`.
- **Solusi**: Pindahkan instans default ke Companion Object dari `User` atau `JsonEncoder`. Companion object tidak memerlukan impor eksplisit dan berada pada level spesifisitas yang sama secara teratur.

#### 10.3. Alokasi Objek Primitif Tersembunyi (Autoboxing)
- **Gejala**: Alokasi GC melonjak saat serialisasi jutaan item primitif.
- **Penyebab**: Tipe generik `[A]` pada Type Class memaksa JVM melakukan autoboxing pada `Int`, `Double`, atau `Long`.
- **Solusi**: Gunakan `inline given` dikombinasikan dengan direct specialization atau tangani tipe primitif secara eksplisit sebelum delegasi ke generik.

---

### 11. Best Practices (Production Checklist)

- [ ] **Coherence Enforcement**: Jangan pernah mendefinisikan *orphan instance* kecuali benar-benar terpaksa di layer integrasi root (`AppMain`).
- [ ] **Companion-First Strategy**: Letakkan instans standar selalu di Companion Object dari Type Class atau Companion Object dari tipe data.
- [ ] **Gunakan Context Bounds**: Prioritaskan `def process[A: OrderValidator](item: A)` dibandingkan `def process[A](item: A)(using OrderValidator[A])` kecuali instans perlu diakses secara langsung.
- [ ] **Hindari Implicit Conversions**: Gunakan `extension` methods, bukan `Conversion[From, To]` yang tidak aman dan merusak keterbacaan kode.
- [ ] **Minimalkan Search Scope Global**: Hindari penggunaan `import my.instances.given` di cakupan file global (package level). Batasi pada lexical block terkecil.
- [ ] **Dokumentasikan Hukum Aljabar (Laws)**: Sertakan automated test berbasis property (`scalacheck`) untuk memastikan instans Type Class mematuhi hukum aljabar (contoh: Monoid Identity & Associativity).

---

### 12. Hands-on Practice

Siapkan struktur folder berikut pada mesin Anda:
```bash
mkdir -p hands-on/m02/src/main/scala
cd hands-on/m02
```

Buat file konfigurasi `build.sbt`:
```scala
scalaVersion := "3.3.3"
name := "contextual-abstractions-deepdive"
version := "1.0.0"

libraryDependencies ++= Seq(
  "org.scalameta" %% "munit" % "1.0.0" % Test
)
```

Buat implementasi produksi di `src/main/scala/Validator.scala`:
```scala
package hands.on.m02

// 1. Core Type Class
trait Validator[A]:
  def validate(value: A): Either[String, Unit]

// 2. Syntax Companion
object Validator:
  inline def apply[A](using v: Validator[A]): Validator[A] = v

  // Coherent default instances
  given stringNonEmpty: Validator[String] with
    def validate(value: String): Either[String, Unit] =
      if value.nonEmpty then Right(()) else Left("String tidak boleh kosong.")

  given positiveInt: Validator[Int] with
    def validate(value: Int): Either[String, Unit] =
      if value > 0 then Right(()) else Left("Angka harus positif (> 0).")

  // Extension Syntax
  extension [A](value: A)(using v: Validator[A])
    def checkValid: Either[String, Unit] = v.validate(value)

// 3. Execution Verification
object MainApp:
  import Validator.{*, given}

  def main(args: Array[String]): Unit =
    println("--- Testing Contextual Type Class ---")
    val email = "engineering@enterprise.com"
    val balance = 1000

    println(s"Email valid: ${email.checkValid}")
    println(s"Balance valid: ${balance.checkValid}")

    val invalidBalance = -5
    println(s"Negative Balance valid: ${invalidBalance.checkValid}")
```

Jalankan program melalui terminal:
```bash
sbt run
```

---

### 13. Exercises

#### Level: Easy
Implementasikan Type Class `CsvFormatter[A]` yang mengubah tipe data menjadi baris CSV (`String`). Sediakan instans untuk `Int`, `String`, dan tuple `(String, Double)`.
- **Target**: Kode harus mengizinkan sintaks `"John".toCsv` dan `( "Item", 45.0 ).toCsv`.

#### Level: Medium
Rancang Type Class `Mergeable[A]` yang memiliki metode `merge(left: A, right: A): A`.
- Buat instans untuk `Map[K, V]` di mana jika key bertabrakan, nilainya di-*merge* menggunakan instans `Mergeable[V]` dari tipe value tersebut (Recursive Type Class Resolution).

#### Level: Hard
Bangun Type Class `DeepDiff[A]` yang membandingkan dua objek bertipe `A` dan mengembalikan struktur data berikut:
```scala
enum DiffResult:
  case Identical
  case Modified(fields: Map[String, (Any, Any)])
```
- Manfaatkan `scala.deriving.Mirror.ProductOf` untuk mendekomposisi Case Class secara otomatis tanpa alokasi library eksternal (Jackson/Circe).

---

### 14. Challenge

**Skenario**: Anda adalah Principal Platform Architect pada bursa efek kripto. Sistem menangani ratusan ribu `OrderEvent` per detik.
**Tugas**: Rancang modul *zero-allocation schema-validation framework* menggunakan Scala 3:
1. Tidak boleh ada alokasi objek heap tambahan pada jalur validasi data bertipe numerik primitif (`Price` dalam `Long`, `Quantity` dalam `Long`). Gunakan `inline given` dan `AnyVal` / `opaque type`.
2. Validasi harus gagal di level **compile-time** jika sebuah domain model belum memiliki instans `SecurityClearanceValidator[A]`.
3. Buat sebuah sistem kontekstual di mana setiap event yang divalidasi mewajibkan adanya `LatencyBudget` token yang berkurang secara otomatis setiap kali melintasi pipeline validasi berikutnya.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara kata kunci `implicit` di Scala 2 dengan `given` / `using` di Scala 3 dari perspektif keterbacaan kode?
2. Bagaimana cara mengakses instans `given` secara eksplisit di dalam blok fungsi tanpa memberi nama variabel pada klausa `using`?
3. Di mana kompiler Scala pertama kali mencari instans Type Class sebelum memeriksa Companion Object dari tipe data yang bersangkutan?
4. Mengapa kita tidak disarankan melakukan `import myinstances._` secara global untuk mengimpor `given` instances?
5. Apa peran dari kata kunci `derives` pada deklarasi sebuah `case class`?

#### 5 Pertanyaan Intermediate
6. Bagaimana cara kerja `scala.compiletime.summonInline` dan apa bedanya dengan fungsi `summon` standar?
7. Jelaskan apa yang dimaksud dengan *Type Class Coherence* dan mengapa instans `orphan` dapat mengancam stabilitas sistem enterprise!
8. Apa efek penurunan performa (*performance penalty*) yang bisa terjadi jika parameter generik Type Class `[A]` digunakan langsung untuk memanipulasi tipe data JVM primitif?
9. Bagaimana representasi JVM bytecode dari sebuah *Context Function* `type Executable[A] = ExecutionContext ?=> A`?
10. Bagaimana aturan kompilasi (*Specificity Rules*) Dotty dalam menentukan pemenang ketika terdapat dua buah instans `given` yang sama-sama cocok (*compatible*)?

#### 3 Skenario Kasus Produksi
11. **Skenario A**: Tim Anda mendapati bahwa waktu kompilasi (*build time*) pada project mikroservis melonjak dari 40 detik menjadi 8 menit setelah mengadopsi auto-derivation berbasis Type Class ke seluruh domain DTO. Investigasi langkah per langkah dan opsi arsitektur apa yang harus diambil untuk menurunkan build time tersebut?
12. **Skenario B**: Di sistem pembayaran, sebuah class `TransactionPayload` memiliki dua buah instans `given JsonEncoder[TransactionPayload]` yang berbeda: satu untuk format internal bank (lengkap dengan data sensitif) dan satu untuk public webhook client (ter-masking). Instans publik secara tidak sengaja terpakai di logging internal. Bagaimana Anda mendesain ulang arsitektur tipe tersebut agar *compiler* mencegah tertukarnya instans tanpa bergantung pada ketelitian penamaan import manual?
13. **Skenario C**: Sebuah modul analitik berkinerja tinggi mengalami lonjakan *GC pause* hingga 500ms secara berkala. Profiling memori menggunakan Java Flight Recorder (JFR) menunjukkan jutaan alokasi objek Type Class anonim per detik pada method pipeline utama. Solusi arsitektural apa di Scala 3 yang dapat melenyapkan alokasi tersebut tanpa mengubah logika bisnis?

---

### 16. Summary

- **Ad-Hoc Polymorphism**: Scala 3 menyempurnakan Type Class pattern melalui `given` dan `using`, menghapus ambiguitas semantik dari paradigma `implicit` lama.
- **Bytecode Reality**: Tidak ada keajaiban magis di runtime JVM; kompiler mendesugar Type Classes menjadi passing parameter reguler dan static singleton instantiation.
- **Coherence & Safety**: Menjaga instans tetap berada pada *companion scope* adalah prinsip fundamental dalam mencegah bug runtime dan konflik kompilasi antar-dependensi.
- **Advanced Inlining**: Dengan memanfaatkan `inline given` dan `Context Functions`, arsitek perangkat lunak dapat merancang API domain enterprise yang bebas alokasi heap (*zero runtime overhead*) namun tetap memiliki level abstraksi dan keamanan tipe yang sangat tinggi.