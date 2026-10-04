# Bab 06 Module 01: Abstraksi Kontekstual & Type Classes

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
|---|---|
| **Jalur Pembelajaran** | Scala Software Engineering & Reactive Architecture |
| **Kategori Kurikulum** | 02-Programming-Languages |
| **Kode Modul** | SCALA-06-01 |
| **Judul Topik** | Abstraksi Kontekstual & Type Classes (Scala 3 Focus) |
| **Tingkat Kompleksitas** | Advanced (Tingkat Lanjut) |
| **Prasyarat Pengetahuan** | - Scala OOP & Functional Fundamentals (Trait, Case Class, Higher-Order Functions)<br>- Parametric Polymorphism (Generics & Variance)<br>- Pengenalan Sistem Tipe Kompilator Scala |
| **Teknologi Target** | Scala 3 (v3.3+ LTS), Dotty Compiler Context System |
| **Estimasi Waktu Baca/Praktek**| 90 Menit |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis dan Membedakan** paradigma *Ad-hoc Polymorphism* berbasis *Type Classes* dengan pewarisan berbasis subtyping (*Subtype Polymorphism*) konvensional dalam konteks *Coupling* dan *Extensibility*.
2. **Menguasai Mekanisme Abstraksi Kontekstual Scala 3** menggunakan sintaksis modern (`given`, `using`, `extension`, dan `context bounds`) sebagai evolusi dari sistem `implicit` Scala 2.
3. **Mengonstruksi Type Classes Komprehensif** yang mencakup definisi *type class interface*, implementasi *type class instance*, dan penyediaan *extension syntax* (ergonomi DSL).
4. **Mendiagnosis Alur Pencarian Kontekstual (Context Resolution Search Tree)** oleh kompilator Dotty guna mengatasi ambiguitas resolusi dan *divergence*.
5. **Mengimplementasikan Pola Desain Berbasis Bukti Tipe (Type-Level Evidence & Contextual Proofs)** untuk menjamin integritas tipe pada waktu kompilasi (*compile-time safety*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Subtyping vs Ad-hoc Polymorphism

Dalam Object-Oriented Programming (OOP) tradisional, fungsionalitas diikat langsung ke data melalui *Subtype Polymorphism* (misalnya: pewarisan `interface` atau `abstract class`). Pola ini menghadirkan masalah mendasar yang dikenal sebagai **The Expression Problem**: menambahkan kapabilitas baru pada tipe data yang sudah ada membutuhkan modifikasi kode sumber asli kelas tersebut.

*Type Class* menawarkan pendekatan **Ad-hoc Polymorphism**. Di sini, kita memisahkan secara ketat:
1. **Representasi Data** (`case class`, `enum`, struktur *plain data*).
2. **Definisi Perilaku/Kontrak** (`trait` tanpa keadaan internal).
3. **Penyediaan Implementasi Konkret** (`given instance` yang berdiri terpisah dari data).

```
Paradigma OOP Klasik (Tight Coupling):
[ Data + Perilaku ] ---> Diikat saat definisi kelas (Inflexible)

Paradigma Type Class (Decoupled & Contextual):
[ Data ]                (Plain Record, tidak tahu apa-apa soal operasi)
   +                    
[ Definisi Kemampuan ]  (Trait Type Class: "Apa yang bisa dilakukan")
   +                    
[ Implementasi Bukti ]  (Given Instance: "Bagaimana tipe X melakukannya")
   =
[ Fungsionalitas ]      (Dihubungkan secara otomatis oleh Kompilator di Call Site)
```

**Mental Model Contextual Abstraction**: Bayangkan kompilator sebagai asisten yang melacak *fakta* atau *bukti* (evidence) yang tersedia di lingkungan pemanggilan (*lexical scope* dan *companion objects*). Saat sebuah fungsi membutuhkan parameter kontekstual (`using`), kompilator tidak menuntut Anda menuliskannya secara manual—kompilator mencarinya di katalog bukti yang absah dan menyuntikkannya ke *call site*.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Proses pencarian dan resolusi parameter kontekstual oleh Dotty/Scala 3 Compiler mengikuti hierarki yang terstruktur. Diagram berikut memvisualisasikan bagaimana kompilator memvalidasi kebutuhan `using`:

```
                       +----------------------------------+
                       | Fungsi Dipanggil: foo(x)[using T]|
                       +----------------------------------+
                                        |
                                        v
                       +----------------------------------+
                       | Periksa Lexical Scope            |
                       | 1. Local definitions (val/given) |
                       | 2. Explicit imports              |
                       | 3. Wildcard imports (.* / .given)|
                       +----------------------------------+
                                        |
                +-----------------------+-----------------------+
                |                                               |
           [Ditemukan]                                   [Tidak Ditemukan]
                |                                               |
                v                                               v
   +--------------------------+                   +--------------------------+
   | Evaluasi Ambiguitas      |                   | Periksa Implicit Scope   |
   | Apakah ada >1 kandidat   |                   | (Companion Objects dari):|
   | dengan spesifisitas sama?|                   | - Tipe T                 |
   +--------------------------+                   | - Parameter Tipe dari T  |
        |              |                          | - Outer Class T          |
     [Ya]            [Tidak]                      +--------------------------+
        |              |                                        |
        v              v                        +---------------+---------------+
+---------------+ +-------------+               |                               |
| COMPILE ERROR | | INJEKSI     |          [Ditemukan]                   [Tidak Ditemukan]
| (Ambiguous)   | | SUKSES      |               |                               |
+---------------+ +-------------+               v                               v
                                   +--------------------------+          +---------------+
                                   | Evaluasi Ambiguitas      |          | COMPILE ERROR |
                                   | Candidat Companion       |          | (No Given     |
                                   +--------------------------+          |  Instance)    |
                                        |              |                 +---------------+
                                      [Ya]           [Tidak]
                                        |              |
                                        v              v
                                 +---------------+ +-------------+
                                 | COMPILE ERROR | | INJEKSI     |
                                 +---------------+ | SUKSES      |
                                                   +-------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Transformasi AST (Abstract Syntax Tree) dan Name Mangling
Di balik layar, Scala 3 mengkompilasi konstruksi kontekstual menjadi representasi fungsional murni di tingkat *bytecode* JVM.

```scala
// Kode Sumber Scala 3
trait Formatter[A]:
  def format(value: A): String

given intFormatter: Formatter[Int] with
  def format(value: Int): String = s"Int: $value"

def printValue[A](value: A)(using f: Formatter[A]): Unit =
  println(f.format(value))
```

Kompilator Dotty mentransformasikannya menjadi bentuk struktural ekuivalen:
- `given intFormatter` diubah menjadi *instansiasi sintetis* atau metode *getter* bertanda unik (mangled name), seperti `given_Formatter_Int` atau `intFormatter`.
- Klausa `using f: Formatter[A]` menjadi parameter metode reguler di tingkat JVM:
  `public <A> void printValue(A value, Formatter<A> f)`.
- Pemanggilan `printValue(42)` diterjemahkan langsung menjadi:
  `printValue(Integer.valueOf(42), this.intFormatter());`.

### 2. Lexical Scope vs Implicit Scope
Kompilator mengaudit dua tingkatan ruang lingkup secara berurutan:
- **Lexical Scope**: Semua instans kontekstual yang dideklarasikan secara lokal, diwarisi dari outer class, atau diimpor secara eksplisit (`import package.given` atau `import package.instanceName`).
- **Implicit/Companion Scope**: Jika lexical scope kosong, pencarian berlanjut ke *companion object* dari:
  - Tipe kelas instans yang dicari (`Formatter`).
  - Parameter tipe yang bersangkutan (misal `User` pada pencarian `Formatter[User]`).

### 3. Skema Resolusi Spesifisitas (Subtyping & Shape Overloading)
Jika ditemukan dua kandidat `given`, kompilator tidak serta-merta melempar galat ambiguitas jika salah satu kandidat memiliki tipe yang **lebih spesifik** menurut aturan subtyping kompilator:
- Tipe `A` lebih spesifik daripada `B` jika subtype `A <: B`.
- Companion object dari turunan lebih diprioritaskan daripada companion object supertype.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Tiga Pilar Utama Type Class
Sebuah Type Class selalu terdiri dari tiga elemen arsitektural:
1. **Interface / Contract**: Trait dengan minimal satu parameter tipe: `trait TC[A] { def action(a: A): B }`.
2. **Instances**: Implementasi konkret untuk tipe tertentu menggunakan `given TC[SpecificType]`.
3. **Syntax / Combinators**: Metode ekstensi (*extension methods*) yang memungkinkan kita memanggil API tersebut menggunakan notasi titik (*dot-notation*): `a.action()`.

### Dekonstruksi Sintaksis: Scala 2 vs Scala 3
Scala 2 menggabungkan terlalu banyak peran ke dalam satu kata kunci `implicit` (konversi tipe implisit, parameter implisit, kelas implisit untuk ekstensi). Scala 3 mendisagregasi konsep ini agar terdefinisi secara semantik:

| Konsep | Sintaksis Scala 2 | Sintaksis Modern Scala 3 |
|---|---|---|
| Definisi Instance | `implicit val / implicit object` | `given ... with` atau `given ... =` |
| Parameter Kontekstual | `def foo(implicit x: Int)` | `def foo(using x: Int)` |
| Extension Methods | `implicit class RichInt(x: Int)` | `extension (x: Int) def ...` |
| Mengimpor Given | `import module._` | `import module.given` atau `import module.{given T}` |
| Konversi Tipe | `implicit def aToB(a: A): B` | `given Conversion[A, B] with` |

### Context Bounds
Sebagai singkatan dari parameter kontekstual tanpa nama, Scala mendukung sintaksis **Context Bound**:
```scala
// Notasi eksplisit using
def serialize[T](data: T)(using serializer: Serializer[T]): Array[Byte] =
  serializer.serialize(data)

// Ekuivalen via Context Bound
def serialize[T: Serializer](data: T): Array[Byte] =
  summon[Serializer[T]].serialize(data)
```
Metode bawaan `summon[T]` mengekstrak instans kontekstual `T` yang aktif dari lingkup eksekusi tanpa memerlukan penamaan parameter secara eksplisit.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Contoh implementasi menyeluruh Type Class matematika sederhana (`Semigroup` & `Monoid`) dengan kombinasi parameter generik rekursif.

```scala
// 1. Definisi Kontrak Type Class
trait Semigroup[A]:
  def combine(x: A, y: A): A

trait Monoid[A] extends Semigroup[A]:
  def empty: A

object Monoid:
  // Aksesor global (Summoner helper)
  def apply[A](using m: Monoid[A]): Monoid[A] = m

// 2. Syntax Enrichment via Extension Methods
object MonoidSyntax:
  extension [A](lhs: A)(using m: Semigroup[A])
    def |+|(rhs: A): A = m.combine(lhs, rhs)

// 3. Penyediaan Given Instances Fundamental
object MonoidInstances:
  given intAdditionMonoid: Monoid[Int] with
    def empty: Int = 0
    def combine(x: Int, y: Int): Int = x + y

  given stringConcatMonoid: Monoid[String] with
    def empty: String = ""
    def combine(x: String, y: String): String = x + y

  // Instans Kondisional / Rekursif: Monoid untuk List[A] membutuhkan Semigroup/Monoid dari A
  given listMonoid[A]: Monoid[List[A]] with
    def empty: List[A] = Nil
    def combine(x: List[A], y: List[A]): List[A] = x ::: y

  // Derivasi Induktif: Monoid untuk Map[K, V] jika V memiliki Monoid
  given mapMonoid[K, V](using vMonoid: Monoid[V]): Monoid[Map[K, V]] with
    def empty: Map[K, V] = Map.empty
    def combine(x: Map[K, V], y: Map[K, V]): Map[K, V] =
      y.foldLeft(x) { case (acc, (key, value)) =>
        val updatedVal = acc.get(key) match
          case Some(existing) => vMonoid.combine(existing, value)
          case None           => value
        acc.updated(key, updatedVal)
      }

// 4. Aplikasi Penggunaan
@main def runFundamentalDemo(): Unit =
  import MonoidInstances.given
  import MonoidSyntax.*

  // Menggunakan generic function dengan Context Bound
  def combineAll[T: Monoid](items: List[T]): T =
    items.foldLeft(Monoid[T].empty)(_ |+| _)

  val intResult = combineAll(List(1, 2, 3, 4))
  val strResult = combineAll(List("Scala ", "3 ", "Contextual ", "Abstractions"))
  
  val map1 = Map("a" -> 10, "b" -> 20)
  val map2 = Map("b" -> 30, "c" -> 40)
  val mapResult = map1 |+| map2

  println(s"Int Combined: $intResult")        // 10
  println(s"String Combined: $strResult")     // Scala 3 Contextual Abstractions
  println(s"Map Combined: $mapResult")       // Map(a -> 10, b -> 50, c -> 40)
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah telaah kritis terhadap komponen esensial pada SEKSI 07:

1. **`trait Monoid[A] extends Semigroup[A]`**: Mengikuti hierarki tipe aljabar murni; setiap `Monoid` harus memenuhi syarat sebagai `Semigroup` (memiliki operasi biner asosiatif), ditambah satu elemen identitas `empty`.
2. **`def apply[A](using m: Monoid[A]): Monoid[A] = m`**: Menggunakan idiom *summoner pattern*. Ini memungkinkan penulisan `Monoid[Int]` yang secara internal dievaluasi menjadi `Monoid.apply[Int](using intAdditionMonoid)`.
3. **`extension [A](lhs: A)(using m: Semigroup[A])`**: Mendeklarasikan bahwa untuk semua tipe `A` yang memiliki instans `Semigroup[A]` di lingkup kontekstual, metode operator biner `|+|(rhs: A)` otomatis tersedia secara transparan pada instance objek `lhs`.
4. **`given listMonoid[A]: Monoid[List[A]] with`**: Menunjukkan implementasi instans generik non-kondisional. Kompilator dapat menginstansiasi `Monoid[List[T]]` untuk sembarang tipe `T`.
5. **`given mapMonoid[K, V](using vMonoid: Monoid[V]): Monoid[Map[K, V]] with`**: Merupakan **Inductive Type Class Derivation**. Resolusi `Monoid[Map[K, V]]` bersifat rekursif; ia hanya absah jika kompilator berhasil menemukan `Monoid[V]` untuk tipe nilai dalam map tersebut.
6. **`def combineAll[T: Monoid](items: List[T]): T`**: Mendemonstrasikan *Context Bound*. Sintaksis ini memerintahkan kompilator untuk secara implisit menyertakan argumen `(using ev: Monoid[T])` dalam tanda tangan metode bytecode.

---

## SEKSI 09 — STUDI KASUS NYATA

### Pipeline Pemrosesan Audit Data & Sanitasi PII (Fintech)
Dalam sistem pemrosesan transaksi perbankan terdistribusi, kita menerima berbagai payload transaksi internal maupun eksternal. Kebutuhan arsitektural:
1. Semua log peristiwa harus mencatat identitas jejak kontekstual (`TraceContext`) secara implisit tanpa mengotori setiap parameter metode bisnis.
2. Semua entitas domain yang memuat informasi data pribadi (Personally Identifiable Information - PII) seperti Nomor Rekening, Nama Nasabah, dan Saldo, harus secara mutlak disanitasi (*masked*) sebelum dicatat ke log audit.
3. Arsitektur harus aman dari kegagalan manusia: jika pengembang lupa mendefinisikan skema sanitasi untuk suatu tipe domain baru, kompilasi harus **gagal** (*fail to compile*), mencegah kebocoran data di fase produksi.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

```scala
package tech.fintech.audit

import java.time.Instant
import java.util.UUID

// --- LINGKUP INFRASTRUKTUR AUDIT KONTEKSTUAL ---
final case class TraceContext(traceId: UUID, correlationId: String, timestamp: Instant)

object ContextProvider:
  // Menyediakan konteks default untuk lingkungan eksekusi
  given currentTraceContext: TraceContext = TraceContext(
    traceId = UUID.randomUUID(),
    correlationId = "CORR-SYS-" + UUID.randomUUID().toString.take(8),
    timestamp = Instant.now()
  )

// --- KONTRAK TYPE CLASS AUDIT DATA (SANITISASI) ---
trait AuditSanitizer[A]:
  def sanitize(data: A): String

object AuditSanitizer:
  def apply[A](using s: AuditSanitizer[A]): AuditSanitizer[A] = s

  // Extension method untuk ergonomi
  extension [A: AuditSanitizer](data: A)
    def toAuditString: String = AuditSanitizer[A].sanitize(data)

  // Primitive Type Instances
  given stringSanitizer: AuditSanitizer[String] with
    def sanitize(data: String): String = data

  given longSanitizer: AuditSanitizer[Long] with
    def sanitize(data: Long): String = data.toString

  given bigDecimalSanitizer: AuditSanitizer[BigDecimal] with
    def sanitize(data: BigDecimal): String = data.setScale(2).toString()

// --- MODEL DOMAIN ENTITAS FINTECH ---
final case class CustomerId(value: String)
final case class AccountNumber(value: String)
final case class SensitiveTransaction(
    txId: String,
    senderAccount: AccountNumber,
    receiverAccount: AccountNumber,
    amount: BigDecimal,
    note: String
)

// --- TYPE CLASS INSTANCES UNTUK DOMAIN ENTITIES ---
object FinancialSanitizerInstances:
  import AuditSanitizer.*

  // Masking nomor rekening: Menampilkan hanya 4 digit terakhir
  given accountSanitizer: AuditSanitizer[AccountNumber] with
    def sanitize(acc: AccountNumber): String =
      val raw = acc.value
      if raw.length <= 4 then "****"
      else s"****-****-${raw.takeRight(4)}"

  // Masking komprehensif transaksi
  given transactionSanitizer(using
      accSanitizer: AuditSanitizer[AccountNumber],
      bdSanitizer: AuditSanitizer[BigDecimal]
  ): AuditSanitizer[SensitiveTransaction] with
    def sanitize(tx: SensitiveTransaction): String =
      s"Transaction[ID=${tx.txId}, " +
      s"Sender=${accSanitizer.sanitize(tx.senderAccount)}, " +
      s"Receiver=${accSanitizer.sanitize(tx.receiverAccount)}, " +
      s"Amount=${bdSanitizer.sanitize(tx.amount)}, Note=CONFIDENTIAL]"

// --- SISTEM AUDIT ENGINE TINGKAT TINGGI ---
object AuditEngine:
  import AuditSanitizer.*

  def logEvent[T: AuditSanitizer](event: T)(using ctx: TraceContext): Unit =
    val sanitizedLog = event.toAuditString
    val logOutput =
      s"{\"timestamp\": \"${ctx.timestamp}\", " +
      s"\"trace_id\": \"${ctx.traceId}\", " +
      s"\"correlation_id\": \"${ctx.correlationId}\", " +
      s"\"payload\": \"$sanitizedLog\"}"
    
    // Output simulasi I/O
    println(s"[SECURE AUDIT PIPELINE] $logOutput")

// --- RUNTIME TESTING & DEMONSTRASI KEAMANAN TIPE ---
@main def runFintechAuditPipeline(): Unit =
  import ContextProvider.given
  import FinancialSanitizerInstances.given
  import AuditSanitizer.*

  val tx = SensitiveTransaction(
    txId = "TXN-90218391",
    senderAccount = AccountNumber("1092837461928374"),
    receiverAccount = AccountNumber("9876543210123456"),
    amount = BigDecimal(15750000.50),
    note = "Pembayaran Layanan Cloud Korporat"
  )

  // Eksekusi Log: traceContext diinjeksi via Context Provider,
  // dan transactionSanitizer diselesaikan oleh kompilator secara otomatis.
  AuditEngine.logEvent(tx)

  // Contoh derivasi koleksi: List otomatis aman diaudit jika elemennya punya instance
  given listSanitizer[A: AuditSanitizer]: AuditSanitizer[List[A]] with
    def sanitize(list: List[A]): String =
      list.map(item => summon[AuditSanitizer[A]].sanitize(item)).mkString("[", ", ", "]")

  val multipleAccounts = List(
    AccountNumber("5555444433332222"),
    AccountNumber("1111222233334444")
  )
  
  AuditEngine.logEvent(multipleAccounts)
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Dimensi Parameter | Subtyping Konvensional (OOP) | Type Classes (Scala 3 Contextual) | Structural / Reflection Typing |
|---|---|---|---|
| **Kopling (Coupling)** | **Ketat**. Tipe data harus mewarisi kontrak pada deklarasi awal. | **Nol / Loose**. Implementasi data dan behavior terpisah independen. | **Nol**. Terikat pada nama metode saat *runtime*. |
| **Ekstensibilitas Data** | Mudah menambah varian data baru (*cases*), sulit menambah operasi baru. | Seimbang. Menambah tipe dan operasi baru sama-sama modular (*Expression Problem Solver*). | Sangat fleksibel, namun tidak aman. |
| **Pemeriksaan Kompiler** | Statis, diperiksa pada level pewarisan hierarki. | Statis, diverifikasi ketat saat pencarian kontekstual (*Context Resolution*). | Sebagian besar lolos ke Runtime (Rawan crash `NoSuchMethodException`). |
| **Overhead Kinerja** | Vtable invocation standar JVM. Sangat cepat. | Relatif cepat. Seringkali inline; dapat menimbulkan alokasi objek `given` jika tidak dioptimasi. | Sangat lambat (*Reflection invocation penalty*). |
| **Retroactive Modeling** | **Mustahil**. Tidak bisa memodifikasi kelas bawaan Java SDK seperti `java.lang.String`. | **Sangat Mudah**. Cukup definisikan `given TC[String]`. | Membutuhkan Dynamic Invocation atau bytecode manipulation. |
| **Kurva Pembelajaran** | Rendah. Dipahami oleh mayoritas programmer pemula. | Moderat hingga Tinggi. Menuntut pemahaman resolusi skop dan algebra tipe. | Moderat, namun debugging sangat sulit. |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Divergent Implicit Expansions (Pencarian Tak Berhingga)
Saat mendefinisikan instans induktif yang saling bergantung secara rekursif, Anda dapat memicu loop kompilator:
```scala
trait Transformer[A]
given loop[A](using t: Transformer[List[A]]): Transformer[A] with {} // DANGEROUS!
// Kompilator akan mencari: Transformer[A] -> Transformer[List[A]] -> Transformer[List[List[A]]] ...
// Hasil: Diverging implicit search limit exceeded.
```
*Aturan*: Selalu kurangi kompleksitas tipe pada parameter `using` dalam pembuatan instans induktif (misal: konstruksi `List[A]` dari `A`, bukan sebaliknya).

### 2. Tabrakan Ruang Lingkup (Scope Shadowing)
Jika terdapat `given` anonim di tingkat *lexical scope* dan Anda mengimpor instans lain dari paket utilitas, kompilator akan memunculkan galat ambiguitas jika tidak ada jalur spesifisitas yang unggul.

### 3. Masalah Tipe `Nothing` dan Inferensi Generik
Jika Anda memanggil fungsi konteks generik tanpa argumen eksplisit:
```scala
def fetchConfig[T](using c: ConfigReader[T]): T = ...
// val res = fetchConfig // Kompilator menyimpulkan T = Nothing!
```
Kompilator akan mencoba mencari `ConfigReader[Nothing]`. Pastikan anotasi tipe selalu dideklarasikan pada *call-site*: `val res = fetchConfig[AppConfig]`.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Polusi Impor Wildcard (`import mypackage.*`)
* *Kesalahan*: Mengira `import mypackage.*` akan mengimpor semua `given instance` di Scala 3.
* *Penyebab*: Di Scala 3, aturan impor diubah demi keamanan. Wildcard `*` **TIDAK** mengimpor `given instance`.
* *Solusi*: Selalu gunakan `import mypackage.given` atau impor spesifik `import mypackage.{given Formatter}`.

```scala
// SALAH (Given tidak terimpor)
import tech.fintech.audit.FinancialSanitizerInstances.*

// BENAR
import tech.fintech.audit.FinancialSanitizerInstances.given
```

### 2. Mendefinisikan Given di Luar Objek atau Package Objek
* *Kesalahan*: Mendeklarasikan `given` sebagai variabel global tanpa pembungkus namespace.
* *Solusi*: Tempatkan `given` di dalam `object`, `class`, atau *companion object* dari tipe data terkait agar kompilator dapat menemukannya via *Implicit Scope* tanpa perlu impor manual.

### 3. Ambiguous Implicits Karena Penggunaan Primitive Monoid
* *Kesalahan*: Mendefinisikan `given intMultMonoid: Monoid[Int]` dan `given intAddMonoid: Monoid[Int]` di cakupan yang sama.
* *Solusi*: Bungkus dengan *Newtype* / *Value Class* atau *Opaque Type*:
```scala
opaque type Sum = Int
opaque type Mult = Int
// Berikan instance terpisah untuk Sum dan Mult
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Gunakan Companion Object Seoptimal Mungkin**: Tempatkan instans kanonikal standar di *companion object* tipe data atau type class tersebut. Ini membebaskan pengguna akhir dari kewajiban melakukan `import module.given`.
2. **Utamakan Context Bound Daripada Klausul Explicit `using`**: Gunakan `def process[T: Codec](data: T)` kecuali Anda membutuhkan manipulasi langsung terhadap variabel instans tersebut di dalam blok implementasi.
3. **Penamaan Instance Eksplisit pada Skala Library**: Meskipun Scala 3 mendukung `given Type with`, selalu beri nama pada instans Anda (`given customTypeInstance: Type with`) saat membangun pustaka untuk mempermudah navigasi IDE, *debugging*, dan *binary compatibility*.
4. **Hindari Konversi Implisit Sembarangan**: Fitur `given Conversion[From, To]` berpotensi menyamarkan pemanggilan logika berat. Gunakan *Extension Methods* daripada mengonversi objek secara siluman.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Evaluasi Alokasi Objek di Heap
Secara *default*, instansiasi `given ClassName with` mendefinisikan objek singleton sintetis. Namun jika `given` didefinisikan menggunakan metode berparameter tipe (generik):
```scala
given listSerializer[A](using s: Serializer[A]): Serializer[List[A]] = ...
```
Kompilator mengonversi ini menjadi metode Java. Setiap kali fungsi dipanggil, metode tersebut dieksekusi dan dapat membuat instans baru objek `Serializer[List[A]]`, yang memicu pemborosan alokasi memori (*GC pressure*) pada throughput tinggi.

### Pola Solusi: `inline given` dan Caching
Scala 3 memperkenalkan fitur inlining lanjutan:
```scala
// 1. Mengurangi pemanggilan virtual via inlining
inline given fastIntSerializer: Serializer[Int] with
  inline def serialize(value: Int): Array[Byte] = 
    java.nio.ByteBuffer.allocate(4).putInt(value).array()

// 2. Simpan instance generik singleton jika tidak memiliki variasi internal
private val dummyListInstance = new Serializer[List[Nothing]]: ...
given cachedListSerializer[A]: Serializer[List[A]] = 
  dummyListInstance.asInstanceOf[Serializer[List[A]]]
```

---

## SEKSI 16 — KEAMANAN & HARDENING

Pemanfaatan Type Class dapat dimaksimalkan sebagai mekanisme verifikasi keamanan berbasis sistem tipe:

```scala
// Segregasi Tingkat Otorisasi Menggunakan Context-Carried Proofs
sealed trait Permission
sealed trait AdminPerm extends Permission
sealed trait ReadOnlyPerm extends Permission

// Phantom type sebagai 'Capability Token'
final class AuthToken[P <: Permission] private()

object SecurityContext:
  // Hanya modul keamanan internal yang dapat menerbitkan token Admin
  private[security] def issueAdminToken(): AuthToken[AdminPerm] = new AuthToken[AdminPerm]()

// API Kritis membutuhkan bukti otorisasi secara mutlak di waktu kompilasi
def purgeDatabase(table: String)(using AuthToken[AdminPerm]): Unit =
  println(s"CRITICAL: Table $table purged.")

// Jika developer mencoba memanggil:
// purgeDatabase("users") -> COMPILE ERROR: No given instance of type AuthToken[AdminPerm] was found.
```
Pendekatan ini menjamin celah keamanan (*unauthorized invocation*) tertangkap sebelum kode dieksekusi di server (*Zero Runtime Risk*).

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Ketika kompilator gagal menemukan instans atau menolak kompilasi akibat ambiguitas, manfaatkan flag kompilator Dotty:

### Parameter Kompilasi Diagnostik:
Tambahkan ke dalam berkas `build.sbt`:
```scala
scalacOptions ++= Seq(
  "-explain",                // Memberikan penjelasan komprehensif saat terjadi error resolusi
  "-Xprint:typer",           // Menampilkan AST pasca ekspansi given/using
  "-Vprint-args",            // Menampilkan bagaimana parameter kontekstual diinjeksi
  "-Ydebug-type-error"       // Debug stack trace kompilator jika terjadi circular resolution
)
```

### Memeriksa Resolusi Implisit Secara Interaktif
Gunakan `scala.compiletime.testing.typeChecks` dalam unit test untuk menguji kegagalan secara deterministik:
```scala
import scala.compiletime.testing.typeChecks

// Memastikan kode berikut GAGAL dikompilasi jika tipe tidak memiliki sanitizer
assert(!typeChecks("""
  case class RawData(x: Int)
  AuditEngine.logEvent(RawData(10))
"""))
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

```scala
// 1. Definisi Type Class Interface
trait Show[A]:
  def show(value: A): String

// 2. Definisi Extension Method (Ergonomi)
object Show:
  def apply[A](using s: Show[A]): Show[A] = s
  extension [A: Show](a: A)
    def display: String = Show[A].show(a)

// 3. Deklarasi Given Instance Sederhana
given Show[Int] with
  def show(v: Int): String = s"Integer: $v"

// 4. Deklarasi Given Instance Kondisional / Induktif
given [A: Show]: Show[List[A]] with
  def show(list: List[A]): String = 
    list.map(_.display).mkString("[", ", ", "]")

// 5. Sintaks Pemanggilan
// Explicit using
def render[A](a: A)(using s: Show[A]): String = s.show(a)

// Context bound (Gaya idiomatik functional programming)
def renderBound[A: Show](a: A): String = a.display

// 6. Mengimpor Given
import MyScope.given          // Impor semua given
import MyScope.{given Show[?]}// Impor spesifik type class
```

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara `import com.example.Instances.*` dan `import com.example.Instances.given` pada Scala 3?**
   * *Jawaban*: Impor wildcard `*` hanya membawa masuk kelas, objek, metode, dan nilai biasa, secara sengaja mengecualikan `given instances` untuk mencegah polusi lingkup. Penggunaan klause `.given` diwajibkan secara eksplisit untuk membuka dan memasukkan instans kontekstual ke dalam lexical scope.

2. **Diberikan fungsi `def serialize[T: JsonEncoder](value: T): String`. Bagaimana cara mengakses instans `JsonEncoder[T]` di dalam tubuh fungsi tersebut tanpa mengubah deklarasi fungsi?**
   * *Jawaban*: Menggunakan metode pembantu kompilator `summon[JsonEncoder[T]]`.

3. **Benar atau Salah: Sebuah `case class` dapat mengimplementasikan Type Class secara langsung melalui mekanisme inheritance (`extends`) tanpa melanggar prinsip Ad-hoc Polymorphism?**
   * *Jawaban*: Salah. Menggabungkan kontrak langsung via `extends` mengembalikan struktur ke *Subtype Polymorphism* (pewarisan konvensional), yang merekatkan kembali data dengan operasinya dan meniadakan keunggulan *retroactive extension*.

4. **Kapan kompilator Dotty akan memeriksa *Companion Scope* dari sebuah tipe parameter?**
   * *Jawaban*: Kompilator memeriksa *Companion Scope* jika dan hanya jika instans kontekstual yang dibutuhkan **tidak ditemukan** di dalam *Lexical Scope* aktif.

5. **Apa fungsi dari kata kunci `extension` dalam arsitektur Type Class di Scala 3?**
   * *Jawaban*: Menyediakan metode pembantu (*syntactic sugar*) yang memperluas fungsionalitas tipe data target dengan sintaks pemanggilan operator/titik (`value.method()`), tanpa perlu memodifikasi kode sumber tipe data tersebut.

---

### Soal Tingkat Menengah (Intermediate)

6. **Diberikan dua buah given instance:**
   ```scala
   given genericFormatter[T]: Formatter[T] = ...
   given intFormatter: Formatter[Int] = ...
   ```
   **Jika sebuah fungsi membutuhkan `Formatter[Int]`, instans mana yang akan dipilih oleh kompilator? Jelaskan alasannya.**
   * *Jawaban*: Kompilator memilih `intFormatter`. Berdasarkan aturan spesifisitas tipe (*type specificity rules*), tipe konkret `Int` dianggap lebih spesifik daripada parameter tipe tak terbatas (unbounded type parameter) `T`. Tidak terjadi ambiguitas.

7. **Bagaimana kompilator Dotty menangani siklus pencarian tak terhingga (*diverging implicit search*) pada given instance rekursif?**
   * *Jawaban*: Kompilator Dotty memiliki batas kedalaman pelacakan tipe (*recursion depth limit*). Jika kompilator mendeteksi bahwa tipe yang dicari terus berkembang dalam ukuran kompleksitas struktural tanpa menemukan basis kasus (misal: `X` -> `List[X]` -> `List[List[X]]`), kompilator akan menghentikan proses dan melempar galat kompilasi `Diverging implicit expansion`.

8. **Mengapa penempatan `given instance` di dalam *Companion Object* dari Type Class itu sendiri dianjurkan untuk default fallbacks?**
   * *Jawaban*: Karena Companion Object termasuk ke dalam *Implicit Scope*. Penempatan di sana memastikan instans tersebut dapat ditemukan secara otomatis oleh kompilator di modul manapun tanpa mengharuskan pengguna menuliskan kode impor eksplisit (`zero-import boilerplate`).

9. **Apa konsekuensi runtime jika kita mendeklarasikan parameter kontekstual berulang-ulang tanpa memanfaatkan `inline` pada volume transaksi ekstrem?**
   * *Jawaban*: Setiap kali method kontekstual non-inline generik dipanggil, JVM berpotensi mengeksekusi metode sintetis yang mengalokasikan wrapper instance baru di heap, menghasilkan overhead alokasi memori berkala dan meningkatkan frekuensi siklus Garbage Collection (GC).

10. **Bagaimana cara mendesain type class yang memvalidasi kesetaraan tipe (*type equality evidence*) antara dua generic type parameter `A` dan `B`?**
    * *Jawaban*: Menggunakan Type Class bawaan standar Scala `=:=` (diakses via `using ev: A =:= B`). Kompilator hanya dapat mensuplai instans ini jika tipe `A` secara statis identik dengan tipe `B`.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Validasi Data Fungsional Terdistribusi (Config Validation Engine)

#### Konteks Masalah
Anda diminta membangun mesin validasi hierarki data konfigurasi aplikasi cloud mikroservis. Sistem konfigurasi memuat tipe primitif dan bersarang (*nested config*) yang dibaca dari environment variable atau format YAML/JSON.

#### Instruksi Pengerjaan

1. **Definisikan Type Class `Validator[A]`**:
   ```scala
   trait Validator[A]:
     def validate(value: A): Either[List[String], Unit]
   ```
2. **Implementasikan Extension Syntax**:
   Bangun sintaks sehingga kita dapat memanggil: `config.validate` secara instan, yang mengembalikan `ValidationResult` (tipe bentukan Anda).
3. **Bangun Instans Validasi Primitif**:
   - `Validator[String]`: Validasi gagal jika string kosong.
   - `Validator[Int]`: Validasi gagal jika integer bernilai negatif (untuk port/memory configuration).
4. **Bangun Derivasi Induktif**:
   - Instans untuk tipe `Option[A]`: Jika `None`, validasi sukses. Jika `Some(v)`, lakukan validasi terhadap `v` menggunakan `Validator[A]`.
   - Instans untuk `List[A]`: Harus memvalidasi seluruh elemen di dalam koleksi dan menggabungkan (*accumulate*) seluruh daftar kesalahan jika ditemukan lebih dari satu elemen yang tidak valid.
5. **Uji Kasus Kompleks**:
   Bangun model hierarki aplikasi:
   ```scala
   case class DatabaseConfig(host: String, port: Int)
   case class ServerConfig(appName: String, dbs: List[DatabaseConfig], timeoutMs: Option[Int])
   ```
   Tuliskan `given Validator[DatabaseConfig]` dan `given Validator[ServerConfig]` yang menyusun validator-validator individual di atas secara kontekstual.
6. **Verifikasi Output**:
   Buat data `ServerConfig` yang memuat nama kosong, port database `-8080`, dan pastikan kompilasi serta penangkapan galat berjalan deterministik, menampilkan seluruh pesan kesalahan secara terakumulasi.