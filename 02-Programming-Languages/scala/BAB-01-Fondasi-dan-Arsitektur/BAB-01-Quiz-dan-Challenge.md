# BAB 01: Quiz, Challenge, & Knowledge Check
**Fondasi Bahasa & Ekosistem Scala**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Unified Type System & JVM Primitive Mapping
Scala mengimplementasikan hierarki tipe terpadu (*Unified Type System*) di mana seluruh tipe diturunkan dari `scala.Any`. Jelaskan arsitektur pemisahan antara `scala.AnyVal` dan `scala.AnyRef`. Bagaimana kompilator Scala (`scalac`) memetakan subtipe `AnyVal` (seperti `Int`, `Double`, `Boolean`) ke dalam representasi JVM bytecode ketika dieksekusi, dan dalam skenario apa proses *auto-boxing* ke tipe referensi `java.lang.Integer` secara tak terhindarkan terjadi?

### Soal 1.2: Semantik Evaluasi (`val` vs `lazy val` vs `def` vs `var`)
Bandingkan semantik evaluasi, alokasi memori, dan siklus hidup (*lifecycle*) dari `val`, `lazy val`, `def`, dan `var`. Jelaskan secara spesifik bagaimana kompilator mentransformasikan deklarasi `lazy val` di balik layar untuk memastikan evaluasi *thread-safe* tunggal (thread-safety guarantees), serta jelaskan overhead komputasi/memori apa yang diperkenalkan oleh mekanisme bitmap locking tersebut.

### Soal 1.3: Expression-Oriented Programming & Referential Transparency
Scala adalah bahasa pemrograman berbasis ekspresi (*expression-oriented*), di mana konstruksi seperti `if-else`, blok `{ ... }`, `try-catch-finally`, dan `match` selalu menghasilkan nilai balik. Analisis mengapa paradigma ini secara fundamental mereduksi *side-effects* dibandingkan paradigma berbasis statement imperatif, dan jelaskan hubungannya dengan konsep *Referential Transparency* serta pemeliharaan *local reasoning* dalam codebase berskala besar.

### Soal 1.4: Peran Bottom Types (`Nothing` dan `Null`)
Dalam sistem tipe Scala, `scala.Nothing` berada di hierarki paling bawah dari seluruh tipe (subtipe dari semua `AnyVal` dan `AnyRef`), sedangkan `scala.Null` adalah subtipe dari seluruh `AnyRef`.
1. Mengapa `Nothing` secara matematis (type theory) diperlukan untuk merepresentasikan ekspresi yang tidak pernah selesai dievaluasi (seperti pelemparan *exception* atau *infinite loop*)?
2. Bagaimana inferensi tipe memanfaatkan `Nothing` dalam koleksi kosong yang immutable seperti `List[Nothing]` (`Nil`) agar dapat diperlakukan sebagai `List[T]` untuk tipe `T` apa pun secara *covariant*?

### Soal 1.5: Ekosistem, Pipeline Kompilasi, dan TASTy
Jelaskan alur kompilasi Scala dari kode sumber (`.scala`) hingga eksekusi runtime di atas JVM. Khusus pada Scala 3, diskusikan peran format intermediat **TASTy** (*Typed Abstract Syntax Trees for Yielding*). Bagaimana keberadaan TASTy menyelesaikan tantangan historis ketidakcocokan biner (*binary incompatibility*) antar minor compiler release dan memfasilitasi interoperabilitas backward/forward compatibility antara Scala 2.13 dan Scala 3?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Deadlock pada `lazy val` Circular Initialization
Perhatikan potongan kode berikut:
```scala
object ServiceA {
  lazy val dependency: String = ServiceB.value
}

object ServiceB {
  lazy val value: String = ServiceA.dependency
}
```
Jika dua thread berbeda mengakses `ServiceA.dependency` dan `ServiceB.value` secara konkuren pada cold startup:
1. Bedah mekanisme sinkronisasi bytecode (`monitorenter`/`monitorexit` atau bitmap lock) yang di-generate oleh `scalac`.
2. Jelaskan urutan transisi *state* yang menyebabkan JVM mengalami *deadlock* permanen tanpa melemparkan eksepsi, dan bagaimana Anda mendeteksinya melalui JVM thread dump (`jstack`).

### Soal 2.2: Memory Footprint Optimization: `AnyVal` vs Scala 3 `opaque type`
Anda merancang identitas domain untuk transaksi finansial performa tinggi:
* Pendekatan Scala 2: `case class AccountId(value: Long) extends AnyVal`
* Pendekatan Scala 3: `opaque type AccountId = Long`

Bandingkan kedua pendekatan tersebut dari perspektif alokasi heap di runtime JVM. Identifikasi minimal 3 skenario teknis di mana `extends AnyVal` gagal mempertahankan sifat primitifnya dan terpaksa melakukan alokasi instansiasi objek (*boxing penalty*), serta jelaskan mengapa `opaque type` sepenuhnya kebal terhadap alokasi runtime tersebut.

### Soal 2.3: Overhead Reflektif pada Structural Typing
Ketika seorang *engineer* mendefinisikan interface berbasis duck-typing:
```scala
type Closable = { def close(): Unit }
def cleanUp(resource: Closable): Unit = resource.close()
```
Jelaskan dampak performa dari eksekusi `resource.close()` di level JVM bytecode jika dijalankan tanpa compiler plugin khusus. Mengapa Java Reflection API (`java.lang.reflect.Method.invoke`) terlibat, bagaimana dampaknya terhadap *JIT inline caching*, dan bagaimana pendekatan Scala 3 `scala.Selectable` mengatasi tantangan ini secara terstruktur?

### Soal 2.4: Tail Call Elimination (`@tailrec`) Failure Analysis
Perhatikan method rekursif berikut:
```scala
import scala.annotation.tailrec

object MathUtils {
  // @tailrec -> Kompilator akan menolak jika di-uncomment
  def calculate(n: Long, acc: Long): Long = {
    if (n <= 0) acc
    else {
      val next = calculate(n - 1, acc + n)
      println(s"Step: $n")
      next
    }
  }
}
```
1. Mengapa kompilator `scalac` gagal mentransformasikan method di atas menjadi loop linear berbasis jump instruction bytecode (`goto`), sehingga anotasi `@tailrec` menghasilkan compilation error?
2. Bagaimana struktur frame pada JVM call-stack saat rekursi berjalan hingga level kedalaman $100.000$, dan bagaimana merefaktorisasi algoritma tersebut agar strictly *tail-recursive* tanpa mengubah output logging?

### Soal 2.5: Bytecode Inspection & Forwarding Methods pada Scala `object`
Ketika Anda mengompilasi sebuah `object DatabaseConnection`, `scalac` menghasilkan dua file kelas: `DatabaseConnection.class` dan `DatabaseConnection$.class`.
1. Jelaskan arsitektur pola Singleton yang diimplementasikan oleh kompilator melalui representasi field `MODULE$` dan kelas pendamping statis tersebut.
2. Apa implikasi dari keberadaan *static forwarder methods* terhadap interoperabilitas kode Java yang memanggil singleton Scala?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Investigasi GC Pressure & Allocation Spike pada High-Throughput Pipeline
* **Konteks:** Sebuah microservice ingest telemetri IoT memproses 250.000 pesan/detik menggunakan Akka Streams / Pekko. Service mengalami degradasi latensi p99 dari 4ms menjadi 450ms. Profiling via Java Flight Recorder (JFR) dan async-profiler menunjukkan JVM Young Generation GC berjalan setiap 800ms dan 70% memori dialokasikan oleh objek pembungkus tuple `scala.Tuple2` dan boxing primitif.
* **Investigasi Codebase:** Ditemukan implementasi parsial pipeline filter:
  ```scala
  // Dipanggil 250.000 kali per detik di dalam stream flow
  def processMetric(rawId: Long, value: Double): Option[(Long, Double)] = {
    if (value > 0.0) Some((rawId, value))
    else None
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Analisis alokasi objek apa saja yang terjadi di heap untuk setiap pemanggilan fungsi yang sukses (`Some`, `Tuple2`, `Double` boxing)? Hitung estimasi objek yang dialokasikan per detik.
  2. Rancang strategi refaktorisasi arsitektur tipe data ini untuk memangkas alokasi heap menjadi nol (*zero-allocation in hot path*), dengan mempertimbangkan teknik representasi data primitif terpadu, `opaque types`, atau sentinel primitives tanpa mengorbankan type safety.

---

### Skenario B: Monorepo Microservices Cold-Boot Hanging di Kubernetes
* **Konteks:** Saat dilakukan rolling update deployment pada kluster Kubernetes, seluruh pod microservice baru mengalami status `CrashLoopBackOff` akibat gagal merespons *readiness probe* (HTTP 503 / timeout). Microservice tersebut menggunakan arsitektur modular yang menggabungkan konfigurasi via *dependency injection* manual berbasis Scala `object` dan `lazy val`.
* **Stack Trace Dump:** Thread dump dari salah satu pod yang hanging menunjukkan status berikut:
  ```text
  "main" #1 prio=5 os_prio=0 tid=0x00007f9c8400a000 nid=0x1bf0 waiting for monitor entry [0x00007f9c8bfbe000]
     java.lang.Thread.State: BLOCKED (on object monitor)
     at com.infra.config.AppConfig$.metricsService$lzycompute(AppConfig.scala:42)
     - waiting to lock <0x00000007159bc8a8> (a java.lang.Object)
     at com.infra.config.MetricsService$.<init>(MetricsService.scala:12)
     ...
  "async-init-thread-1" #18 prio=5 os_prio=0 tid=0x00007f9c84112000 nid=0x1bf5 waiting for monitor entry [0x00007f9c792f8000]
     java.lang.Thread.State: BLOCKED (on object monitor)
     at com.infra.config.MetricsService$.appConfig$lzycompute(MetricsService.scala:15)
     - waiting to lock <0x00000007159bc950> (a java.lang.Object)
     at com.infra.config.AppConfig$.<init>(AppConfig.scala:35)
     ...
  ```
* **Pertanyaan Diagnostik:**
  1. Identifikasi *root cause* dari kebuntuan status container tersebut berdasarkan interdependensi siklis (*circular dependency*) antar-object initialization.
  2. Mengapa JVM initialization locks menyebabkan insiden ini baru muncul secara nondeterministik saat microservice dijalankan dengan *parallel thread pool initialization*, tetapi lolos unit test lokal?
  3. Berikan arsitektur refaktorisasi konkret untuk dependency wiring startup yang deterministik, non-blocking, dan thread-safe.

---

### Skenario C: Cross-Version Migration & Binary Compatibility Degradation
* **Konteks:** Perusahaan enterprise memutuskan untuk memigrasikan fondasi codebase inti perbankan dari Scala 2.13.12 ke Scala 3.3 LTS. Repository sistem menggunakan `sbt` multi-module dengan 40 sub-proyek. Tim mengalami *dependency hell*: library internal `security-crypto-lib` (hanya tersedia biner dalam artefak `_2.13`) bergantung pada runtime reflection lama dan library pihak ketiga yang belum mendukung Scala 3.
* **Permasalahan:** Saat module Scala 3 mengonsumsi dependensi `_2.13` via `libraryDependencies += ("com.bank" %% "security-crypto-lib" % "1.4.0").cross(CrossVersion.for3Use2_13)`, build berhasil tetapi runtime melemparkan eksepsi `NoSuchMethodError` dan `LinkageError` saat mengeksekusi class yang memuat Scala 2 macro dan serialization logic.
* **Pertanyaan Diagnostik:**
  1. Apa batasan teknis interoperabilitas biner antara Scala 3 dan Scala 2.13? Mengapa fitur seperti Scala 2 Macros dan compiler-generated specialized classes tidak dapat dieksekusi secara transparan oleh runtime Scala 3?
  2. Rancang rencana mitigasi arsitektural multi-fase (*migration plan*) untuk monorepo tersebut: bagaimana memisahkan batas domain (*domain boundary*), pemanfaatan `-Xsource:3` pada fase transisi, serta isolasi API boundary library lama agar migrasi dapat berjalan inkremental tanpa menghentikan deployment production.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance In-Memory Ledger Kernel
Anda ditugaskan merancang fondasi arsitektur *core ledger* perbankan yang harus mampu memproses jutaan entri transaksi per detik pada single node JVM dengan aturan: **Zero-Allocation Execution Path**, **Absolute Type-Safety**, dan **Strictly Pure Expressions**.

#### Requirements:
1. **Domain Abstraction (Zero-Allocation):**
   * Definisikan tipe untuk `AccountId`, `TransactionId`, dan `Amount` (dalam centang/cents bernilai positif).
   * Pada Scala 3, implementasikan menggunakan `opaque type` (atau `extends AnyVal` jika menggunakan Scala 2.13). Pastikan tidak terjadi alokasi memori heap saat tipe domain dioperasikan dalam perhitungan matematika atau divalidasi.
2. **Safe Algebraic State Machine:**
   * Modelkan status rekening (`Active`, `Frozen`, `Closed`) dan jenis mutasi (`Credit`, `Debit`) menggunakan Scala *Algebraic Data Types* (ADT) berbasis Sealed Trait/Class atau Scala 3 `enum`.
   * Seluruh penanganan mutasi rekening harus menggunakan *pattern matching* komprehensif tanpa partial functions.
3. **Core Transaction Processor:**
   * Buat method eksekusi batch mutasi rekening yang memproses list of transactions.
   * Wajib memanfaatkan tail recursion (`@tailrec`) murni. Penggunaan konstruksi `var`, `while`, loop imperatif, atau mutasi koleksi dilarang keras.
   * Kegagalan (misalnya saldo tidak mencukupi atau akun `Frozen`) tidak boleh melemparkan Java Exception (`throw new ...`), melainkan harus dikembalikan dalam bentuk ekspresi berbasis ADT error kustom yang efisien.
4. **Bytecode Verification:**
   * Siapkan script atau langkah verifikasi menggunakan `javap -c -p` untuk membuktikan bahwa pemrosesan saldo tidak memanggil helper class boxing (`java.lang.Long.valueOf(...)`) pada hot-path.

#### Constraints:
* Scala Versi: 3.3 LTS (atau 2.13.x LTS).
* External Dependencies: Murni `scala-library` standar (tanpa framework/library eksternal seperti Cats, ZIO, atau Akka).
* Memory Limit: Eksekusi batch 1.000.000 mutasi validasi tidak boleh menaikkan heap usage sebesar alokasi objek pembungkus (hanya boleh menyimpan data mutasi final).

#### Expected Output:
1. File kode sumber lengkap (`LedgerKernel.scala`) yang memuat seluruh definisi tipe, domain, dan fungsi pemrosesan.
2. Ekstrak log output `javap` yang menunjukkan bahwa instruksi matematika `Amount` diterjemahkan secara langsung menjadi instruksi bytecode primitif level rendah (`ladd`, `lsub`, `lcmp`).
3. Unit test mandiri yang mengeksekusi skenario mutasi, membuktikan eksekusi tail-recursive aman terhadap stack overflow dengan kedalaman $500.000$ transaksi.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur hierarki sistem tipe Scala: relasi antara `Any`, `AnyVal`, `AnyRef`, `Null`, dan `Nothing`.
- [ ] Representasi memori dan semantik evaluasi dari `val` (eager), `lazy val` (deferred & synchronized), `def` (by-name evaluation per-call), dan `var` (mutable pointer).
- [ ] Prinsip *Expression-Oriented Programming* dan implementasinya pada alur kontrol program.
- [ ] Mekanisme pemetaan kode Scala ke Java Virtual Machine (JVM) bytecode melalui `scalac`.
- [ ] Peran dan arsitektur file metadata **TASTy** pada ekosistem Scala 3.
- [ ] Optimasi rekursi ekor (*Tail Call Optimization/TCO*) melalui anotasi `@tailrec` dan batasan restriksinya pada bytecode.
- [ ] Penyebab teknis terjadinya deadlock inisialisasi pada `lazy val` dan static `object` dalam kondisi konkuren.
- [ ] Perbedaan esensial mekanisme internal optimasi antara Value Classes (`AnyVal`) dan Scala 3 `opaque type`.

### Saya tidak perlu menghafal:
- [ ] Detail penamaan variabel internal compiler yang digenerasi secara otomatis (seperti penamaan bitmap field `bitmap$0`).
- [ ] Seluruh nomor opcode instruksi mesin JVM (misal kode numerik heksadesimal dari `invokevirtual` atau `monitorenter`).
- [ ] Seluruh opsi flag kompilasi *scalac* yang usang (*deprecated flags*). Cukup memahami flag penting yang mengendalikan optimasi dan peringatan kompatibilitas (seperti `-Xlint`, `-deprecation`, `-Xsource:3`).

### Saya harus bisa melakukan:
- [ ] Memeriksa struktur bytecode hasil kompilasi Scala menggunakan perintah `javap -c -p` untuk mendeteksi alokasi boxing tersembunyi.
- [ ] Mengidentifikasi dan memecahkan (*debug*) bottleneck garbage collection yang diakibatkan oleh alokasi objek temporer pada hot-path stream/loop.
- [ ] Merefaktorisasi algoritma rekursif arbitrer menjadi bentuk *strictly tail-recursive* yang diverifikasi oleh kompilator.
- [ ] Mendesain domain logic yang *type-safe* menggunakan ADT tanpa mengorbankan performa eksekusi memori.
- [ ] Menganalisis thread dump JVM (`jstack`) untuk mengisolasi deadlocks yang bersumber dari circular dependency initialization pada singleton `object` atau `lazy val`.
- [ ] Menulis konfigurasi build multi-proyek pada `sbt` yang mampu memvalidasi cross-compilation atau migrasi biner antar-versi Scala.