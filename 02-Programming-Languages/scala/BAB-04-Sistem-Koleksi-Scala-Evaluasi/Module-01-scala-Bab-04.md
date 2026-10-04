# Bab 04 Module 01: Sistem Koleksi Scala & Evaluasi

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** Rekayasa Perangkat Lunak Backend Skala Besar
*   **Domain Teknis:** `02-Programming-Languages`
*   **Topik Utama:** Sistem Koleksi Scala & Evaluasi (*Scala Collections Framework & Evaluation Strategies*)
*   **Target Kompatibilitas:** Scala 3.3+ (LTS) & Scala 2.13+ (Pasca-Arsitektur *Strawman*)
*   **Prasyarat Konseptual:** Sistem Tipe Dasar Scala, Pemrograman Fungsional Murni (*Pure Functions*, *Immutability*), Rekursi Terminal (*Tail Recursion*), dan Mekanisme *Call-by-Name*.

---

## SEKSI 02 — LEARNING OBJECTIVES

1.  **Membedah Arsitektur Koleksi Scala 2.13/3.x:** Memahami hierarki tipe inti (`Iterable`, `Seq`, `Set`, `Map`) serta pemisahan tegas antara paket `scala.collection.immutable` dan `scala.collection.mutable`.
2.  **Menganalisis Struktur Data Persisten (*Persistent Data Structures*):** Menguasai cara kerja internal *Cons-cell Linked List*, *Radix-32 Bitmapped Vector Trie*, dan *Hash Array Mapped Trie* (HAMT) dalam konteks pembagian struktural (*structural sharing*).
3.  **Menguasai Paradigma Evaluasi:** Membedakan secara mekanis antara evaluasi ketat (*Strict/Eager*), evaluasi malas dengan memoisasi (*LazyList*), evaluasi penangguhan tanpa memoisasi (*View*), dan traversal berbasis mutasi (*Iterator*).
4.  **Mencegah Kebocoran Memori Fungsional:** Mengidentifikasi dan memitigasi bahaya *LazyList memory leak* akibat referensi kepala yang tertahan (*head retention*).
5.  **Optimasi Pipeline Transformasi Data:** Mendesain pemrosesan koleksi multi-tahap tanpa alokasi objek perantara (*zero-intermediate allocation*) menggunakan abstraksi *View* dan operasi fusi (*fusion*).

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma fungsional murni, koleksi bukanlah blok memori kontinu yang diubah di tempat (*in-place mutation*), melainkan grafik simpul-simpul data persisten yang merepresentasikan nilai (*value*) matematis yang tidak berubah (*immutable*).

```
   MENTAL MODEL: STRUCTURAL SHARING

   State A (List(2, 3)):           [ 2 ] -> [ 3 ] -> Nil
                                     ^
                                     |
   State B (1 :: State A): [ 1 ] -----+
   (Tanpa menyalin simpul 2 dan 3 ke blok memori baru)
```

Ketika Anda menambahkan elemen ke dalam sebuah koleksi *immutable*, Scala tidak menyalin seluruh struktur data. Scala mengaplikasikan teknik *Structural Sharing* (Pembagian Struktural), di mana struktur data baru mengacu pada simpul-simpul lama yang masih valid.

Mengenai strategi evaluasi, pandanglah transformasi data sebagai salah satu dari dua instrumen berikut:
1.  **Materialized Transformation (Strict):** Perubahan wujud seketika. Setiap pemanggilan fungsi seperti `map` atau `filter` mengalokasikan koleksi baru secara penuh di memori heap JVM.
2.  **Suspended Computation (Lazy / View):** Perumusan resep instruksi. Data tidak diproses sampai ada operasi terminal (seperti `fold`, `sum`, atau `foreach`) yang secara eksplisit memicu aliran data melewati saluran (*pipeline*) transformasi satu per satu elemen.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Hierarki koleksi Scala dirancang ulang secara fundamental pada Scala 2.13 untuk merampingkan hierarki pewarisan, mengeliminasi kompleksitas `CanBuildFrom`, dan menyediakan pondasi tipe yang kuat melalui `Factory` dan `BuildFrom`.

### Hierarki Tipe Koleksi Utama (`scala.collection`)

```
                           +------------------+
                           |   Iterable[+A]   |
                           +--------+---------+
                                    |
          +-------------------------+-------------------------+
          |                         |                         |
+---------v--------+       +--------v-------+        +--------v-------+
|      Seq[+A]     |       |     Set[A]     |        |   Map[K, +V]   |
+----+--------+----+       +----------------+        +----------------+
     |        |
     |   +----+-----------------------------+
     |   |                                  |
+----v---v---------+               +--------v-------+
|  LinearSeq[+A]   |               | IndexedSeq[+A] |
| (e.g., List)     |               | (e.g., Vector) |
+------------------+               +----------------+
```

### Alur Eksekusi: Strict Pipeline vs Lazy/View Pipeline

```
STRICT PIPELINE:
List(1, 2, 3) 
   --map(+1)-->   List(2, 3, 4) [Alokasi Heap 1] 
   --filter(even)--> List(2, 4) [Alokasi Heap 2] 
   --take(1)-->   List(2)       [Alokasi Heap 3]

VIEW PIPELINE (FUSION):
List(1, 2, 3).view 
   --map(+1)-----> 
   --filter(even)->  [View Representation: Komposisi Fungsi Iterasi]
   --take(1)----->
   --to(List)----> Evaluasi On-Demand per elemen:
                   Elemen 1 -> map(2) -> filter(true) -> take(simpan) -> Stop!
                   Elemen 2 & 3 tidak pernah dievaluasi! Alokasi Heap: Minimal.
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. `List[+A]`: Cons-Cell Linked List
`scala.collection.immutable.List` diimplementasikan secara struktural sebagai rantai simpul *singly-linked list* yang diakhiri oleh objek *singleton* `Nil`.
*   **Anatomi Kelas:** Terdiri dari dua varian tipe: `::[A](head: A, next: List[A])` dan `Nil`.
*   **Karakteristik:** Operasi prepending (`elem :: list`) adalah $\mathcal{O}(1)$ karena simpul baru dialokasikan dengan menunjuk simpul *head* lama sebagai *next*-nya. Operasi pengaksesan indeks acak (`list(n)`) bernilai $\mathcal{O}(n)$ karena mesin harus melintasi pointer referensi dari simpul awal secara sekuensial.

### 2. `Vector[+A]`: Radix-32 Bitmapped Vector Trie
`scala.collection.immutable.Vector` dirancang untuk menyeimbangkan performa *random access* dan *functional update*.
*   **Struktur Internal:** Merupakan pohon dengan tingkat percabangan (*branching factor*) sebesar 32. Setiap simpul internal dapat memiliki hingga 32 anak.
*   **Kedalaman Pohon:** Untuk menampung $2^{31}-1$ elemen (kapasitas maksimum integer JVM), kedalaman maksimum pohon hanya setinggi $\lceil 32 / 5 \rceil = 7$ level tingkat.
*   **Algoritma Pencarian Indeks:** 
    Bitwise masking digunakan secara intensif. Nilai indeks integer (32-bit) dibagi ke dalam blok-blok sebesar 5-bit:
    $$\text{Level Index} = (i \gg (5 \times \text{level})) \mathrel{\&} 0x1F$$
    Pencarian dan pembaruan elemen membutuhkan waktu $\mathcal{O}(\log_{32} N)$, yang secara praktis (*effectively constant*) setara dengan $\le 7$ lompatan pointer memori.

### 3. `LazyList[+A]`: Evaluasi Tertunda dengan Memoisasi Terbuka
Menggantikan `Stream` yang sudah usang (*deprecated*), `LazyList` mengimplementasikan komputasi malas di mana elemen kepala (*head*) dan elemen ekor (*tail*) keduanya dievaluasi secara *lazy*.
*   **Struktur Internal:** Simpul `LazyList` dibungkus oleh evaluasi *lazy val*. Ketika *tail* diakses pertama kali, ekspresi *call-by-name* dievaluasi dan hasilnya disimpan (*memoized*) di dalam memori heap.
*   **Bahaya Head Retention:** Jika pointer ke elemen kepala dari `LazyList` yang tak berhingga disimpan dalam variabel jangka panjang (misalnya variabel `val` lokal yang masih aktif), seluruh elemen yang telah dievaluasi tidak dapat dibersihkan oleh Garbage Collector (GC), memicu `java.lang.OutOfMemoryError: Java heap space`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### Strictness, Laziness, dan Statelessness

Dalam arsitektur runtime Scala, strategi evaluasi menentukan kapan ekspresi komputasi diubah menjadi representasi konkret dalam memori.

| Tipe Koleksi | Evaluasi Elemen | Memoisasi Hasil | Konsumsi Memori | Karakteristik Akses |
| :--- | :--- | :--- | :--- | :--- |
| **`List` / `Vector`** | Strict (Eager) | Penuh (Instan) | $\mathcal{O}(N)$ | Berulang (*Reusable*), Akses Paralel Aman |
| **`LazyList`** | Lazy (On-Demand) | Ya (Tersimpan) | $\mathcal{O}(N)$ seiring traversi | Berulang (*Reusable*), Berisiko GC Leak |
| **`View`** | Lazy (On-Demand) | Tidak (Tanpa Cache) | $\mathcal{O}(1)$ | Berulang (*Reusable*), Re-komputasi per loop |
| **`Iterator`** | Lazy (On-Demand) | Tidak (Tanpa Cache) | $\mathcal{O}(1)$ | **Sekali Pakai (*Single-Use*)**, Mutasi State Kursor |

### Mekanisme Builder Pattern & Factory

Pada arsitektur koleksi modern, setiap tipe koleksi terikat pada implementasi `scala.collection.mutable.Builder[A, To]`. Sebuah builder mengakumulasi elemen secara imperatif dan mutabel di dalam ruang memori privat yang terlindungi, lalu mengembalikan representasi *immutable* instan saat memanggil `.result()`.

```scala
// Representasi arsitektur tipe konseptual Builder
trait Builder[-A, +To] {
  def addOne(elem: A): this.type
  def clear(): Unit
  def result(): To
}
```

Hal ini menjamin bahwa isolasi mutasi internal terlindungi rapat dari dunia luar, memberikan efisiensi komputasi bare-metal JVM tanpa merusak kontrak matematis immutabilitas.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi komparasi fundamental antara eksekusi *Strict*, *View*, *LazyList*, dan penanganan *Iterator* menggunakan Scala 3.

```scala
package com.architect.collections

import scala.annotation.tailrec

object FundamentalCollectionsDemo:

  def main(args: Array[String]): Unit =
    println("=== 1. STRICT EVALUATION DEMO ===")
    demonstrateStrictEvaluation()

    println("\n=== 2. VIEW EVALUATION (NO MEMOIZATION) DEMO ===")
    demonstrateViewEvaluation()

    println("\n=== 3. LAZYLIST EVALUATION (WITH MEMOIZATION) DEMO ===")
    demonstrateLazyListEvaluation()

    println("\n=== 4. ITERATOR CONSUMPTION (SINGLE USE) DEMO ===")
    demonstrateIteratorConsumption()

  // 1. Strict: Seluruh transformasi dieksekusi secara instan per level
  def demonstrateStrictEvaluation(): Unit =
    val numbers = List(1, 2, 3, 4, 5)
    val result = numbers
      .map { x =>
        println(s"Strict Map: $x")
        x * 2
      }
      .filter { x =>
        println(s"Strict Filter: $x")
        x > 4
      }
    println(s"Strict Result: $result")

  // 2. View: Evaluasi ditunda dan difusi, tanpa mengalokasikan koleksi sementara
  def demonstrateViewEvaluation(): Unit =
    val numbers = List(1, 2, 3, 4, 5)
    val viewPipeline = numbers.view
      .map { x =>
        println(s"View Map: $x")
        x * 2
      }
      .filter { x =>
        println(s"View Filter: $x")
        x > 4
      }

    println("View pipeline dikonstruksi (belum dievaluasi)...")
    println(s"Mengambil elemen pertama: ${viewPipeline.headOption}")
    println("Melakukan traversal kedua (komputasi diulang):")
    viewPipeline.foreach(x => println(s"Elemen: $x"))

  // 3. LazyList: Evaluasi ditunda dengan memoisasi (caching) otomatis
  def demonstrateLazyListEvaluation(): Unit =
    def generateStream(n: Int): LazyList[Int] =
      println(s"Membuat node LazyList untuk: $n")
      n #:: generateStream(n + 1)

    val stream = generateStream(1)
    println("LazyList diinisialisasi...")
    println(s"Akses elemen indeks 0: ${stream.head}")
    println(s"Akses elemen indeks 2: ${stream(2)}")
    println("Akses kembali indeks 2 (memoisasi aktif, tanpa re-evaluasi):")
    println(s"Akses ulang elemen indeks 2: ${stream(2)}")

  // 4. Iterator: Penunjuk kursor mutabel, habis setelah dikonsumsi
  def demonstrateIteratorConsumption(): Unit =
    val iterator = Iterator(10, 20, 30)
    println(s"Ketersediaan pertama: ${iterator.hasNext}")
    while iterator.hasNext do
      println(s"Konsumsi nilai: ${iterator.next()}")

    println(s"Ketersediaan kedua: ${iterator.hasNext}")
    if !iterator.hasNext then
      println("Peringatan: Iterator telah habis dan tidak dapat digunakan kembali.")
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

Berikut adalah telaah teknis mendalam terhadap kode pada **SEKSI 07**:

1.  **Baris 24–33 (`demonstrateStrictEvaluation`)**:
    *   `numbers.map(...)`: Seluruh 5 elemen `List` diproses langsung. Pesan `"Strict Map: ..."` dicetak 5 kali berturut-turut, menghasilkan struktur `List(2, 4, 6, 8, 10)` di heap.
    *   `.filter(...)`: Berjalan pada koleksi temporer baru hasil pemetaan, mengevaluasi kondisi dan membuang elemen yang tidak sesuai. Pendekatan ini menghasilkan alokasi perantara (*intermediate allocation overhead*).
2.  **Baris 36–48 (`demonstrateViewEvaluation`)**:
    *   `numbers.view`: Membungkus `List` ke dalam tipe `scala.collection.View`.
    *   `.map(...)` dan `.filter(...)`: Tidak mengeksekusi lambda secara instan, melainkan menggabungkannya ke dalam objek `View.Filter` dan `View.Map`.
    *   `viewPipeline.headOption`: Memicu traversal evaluasi minimum. Elemen `1` di-*map* menjadi `2`, lolos ke *filter* (gagal). Elemen `2` di-*map* menjadi `4`, *filter* (gagal). Elemen `3` di-*map* menjadi `6`, lolos *filter* (berhasil). Evaluasi dihentikan seketika tanpa menyentuh elemen `4` dan `5`.
    *   `viewPipeline.foreach(...)`: Mengulang seluruh proses komputasi dari awal karena `View` tidak menyimpan jejak hasil kalkulasi (tanpa *memoization*).
3.  **Baris 51–62 (`demonstrateLazyListEvaluation`)**:
    *   `n #:: generateStream(n + 1)`: Operator cons khusus `#::` memetakan parameter kedua secara *call-by-name* (`=> LazyList[A]`).
    *   `stream(2)`: Melintasi simpul indeks 0, 1, dan 2. Evaluasi dijalankan dan disimpan di dalam field internal `val`.
    *   Akses kedua ke `stream(2)`: Nilai dikembalikan langsung dari memori tanpa memicu pencetakan string `"Membuat node LazyList untuk: ..."`, membuktikan bahwa efek samping memoisasi bekerja.
4.  **Baris 65–73 (`demonstrateIteratorConsumption`)**:
    *   `iterator.next()`: Mengubah status internal (*internal pointer state*) pada level bytecode JVM.
    *   Ketika kursor menyentuh indeks akhir, iterator menjadi kosong secara permanen. Penggunaan kembali iterator yang telah habis akan memicu `java.util.NoSuchElementException`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Pipeline Agregasi Audit Transaksi Finansial Real-Time

**Konteks Arsitektur:** 
Sebuah platform perbankan digital menerima jutaan rekaman log transaksi audit per hari yang diekspor dalam format terkompresi berukuran gigabyte. Sistem memiliki batasan memori JVM Heap sebesar **512 MB**, namun harus mampu melakukan:
1.  Ingesti dan *parsing* data transaksi dari sumber tak berhingga atau berkas masif.
2.  Validasi anomali transaksi (misal: penipuan berbasis deteksi lonjakan frekuensi dan volume).
3.  Agregasi jendela geser (*sliding window*) untuk menghitung rasio deviasi rata-rata pengeluaran.
4.  Terminasi dini ketika ambang batas risiko kritis terlampaui.

**Masalah:** 
Jika data dibaca menggunakan `List` atau koleksi *strict* lainnya, JVM akan mengalami kegagalan fatal `OutOfMemoryError` dalam hitungan detik. Jika menggunakan rekursi tanpa fusi, waktu komputasi akan terbuang pada proses *Garbage Collection Pause* yang panjang.

**Solusi Arsitektural:** 
Membangun *Data Flow Engine* berbasis `LazyList` yang dipadukan dengan transformasi transformasi parsial `View` dan akumulasi state lokal via `Vector` berukuran terbatas (*bounded buffer*).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi sistem pemrosesan transaksi berkinerja tinggi, aman secara alokasi heap, dan mendukung terminasi dini:

```scala
package com.architect.finance

import java.time.Instant
import scala.annotation.tailrec

// Model domain transaksi immutable
final case class Transaction(
    id: String,
    accountId: String,
    amount: BigDecimal,
    timestamp: Instant,
    isSuspicious: Boolean
)

final case class AuditMetrics(
    totalProcessed: Long,
    flaggedCount: Long,
    totalVolume: BigDecimal,
    peakAnomalyAmount: BigDecimal
)

object FinancialAuditEngine:

  // Generator data stream tak berhingga (mensimulasikan antrean broker Kafka / storage)
  def infiniteTransactionFeed(initialId: Long): LazyList[Transaction] =
    val current = Transaction(
      id = s"TXN-$initialId",
      accountId = s"ACC-${initialId % 100}",
      amount = BigDecimal((initialId * 37 % 5000) + 10),
      timestamp = Instant.now(),
      isSuspicious = (initialId % 13 == 0) // Pola anomali periodik
    )
    current #:: infiniteTransactionFeed(initialId + 1)

  /**
   * Pipeline Analisis:
   * Menggunakan evaluasi bertahap untuk membatasi footprint memori.
   */
  def runAuditPipeline(
      dataSource: LazyList[Transaction],
      maxScanDepth: Int,
      riskThreshold: BigDecimal
  ): Either[String, AuditMetrics] =
    
    // Tahap 1: Batasi kedalaman evaluasi agar tidak meluap ke batas infinite
    val boundedStream = dataSource.take(maxScanDepth)

    // Tahap 2: Transformasi melalui View guna fusi operasi tanpa alokasi intermediat
    val processedView = boundedStream.view
      .filter(_.amount > 50) // Eliminasi transaksi mikro
      .map { txn =>
        if txn.amount > 4500 then txn.copy(isSuspicious = true)
        else txn
      }

    // Tahap 3: Traversal analitik dengan rekursi ekor (Strict Aggregator)
    @tailrec
    def aggregateLoop(
        remaining: Iterator[Transaction],
        acc: AuditMetrics
    ): Either[String, AuditMetrics] =
      if !remaining.hasNext then Right(acc)
      else
        val txn = remaining.next()
        
        // Pemutusan sirkuit darurat (Circuit Breaker Pattern)
        if txn.isSuspicious && txn.amount >= riskThreshold then
          Left(s"CRITICAL RISK BREACH: Terdeteksi transaksi berbahaya ID ${txn.id} sebesar ${txn.amount}")
        else
          val updatedAcc = acc.copy(
            totalProcessed = acc.totalProcessed + 1,
            flaggedCount = if txn.isSuspicious then acc.flaggedCount + 1 else acc.flaggedCount,
            totalVolume = acc.totalVolume + txn.amount,
            peakAnomalyAmount = if txn.isSuspicious && txn.amount > acc.peakAnomalyAmount then txn.amount else acc.peakAnomalyAmount
          )
          aggregateLoop(remaining, updatedAcc)

    val initialMetrics = AuditMetrics(
      totalProcessed = 0L,
      flaggedCount = 0L,
      totalVolume = BigDecimal(0),
      peakAnomalyAmount = BigDecimal(0)
    )

    // Konversi view ke iterator untuk konsumsi single-pass yang aman dari GC Head Retention
    aggregateLoop(processedView.iterator, initialMetrics)

  def main(args: Array[String]): Unit =
    println("Menginisialisasi Engine Audit Finansial...")
    val streamSource = infiniteTransactionFeed(1000L)

    // Kasus 1: Eksekusi normal tanpa memicu circuit breaker
    println("\nEksekusi Skenario 1: Parameter Normal")
    val result1 = runAuditPipeline(streamSource, maxScanDepth = 1000, riskThreshold = 6000)
    result1 match
      case Right(metrics) =>
        println(s"Audit Sukses:")
        println(s" - Transaksi Diproses : ${metrics.totalProcessed}")
        println(s" - Transaksi Flagged  : ${metrics.flaggedCount}")
        println(s" - Total Volume       : Rp ${metrics.totalVolume}")
        println(s" - Puncak Anomali     : Rp ${metrics.peakAnomalyAmount}")
      case Left(error) =>
        println(s"Kegagalan Sistem: $error")

    // Kasus 2: Memicu terminasi dini dengan nilai risk threshold rendah
    println("\nEksekusi Skenario 2: Parameter Risiko Ketat (Early Termination)")
    val result2 = runAuditPipeline(streamSource, maxScanDepth = 1000, riskThreshold = 4600)
    result2 match
      case Right(_)    => println("Audit tidak terduga sukses.")
      case Left(alert) => println(s"Sinyal Interupsi Berhasil Dipicu: $alert")
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih tipe koleksi yang salah adalah sumber utama degradasi performa pada sistem skala besar. Tabel berikut menyajikan analisis komparasi komprehensif struktur data Scala:

| Karakteristik | `List[A]` | `Vector[A]` | `ArraySeq[A]` | `LazyList[A]` | `View[A]` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Penyimpanan Memori** | Simpul Terhubung (*Singly-linked*) | 32-way Branching Trie | Flat Java Array (Continuous) | Simpul Tertunda (*Memoized Thunk*) | Tidak Ada (*Algorithmic Pipeline*) |
| **Operasi `head`** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ (*Amortized*) | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ (Evaluasi 1x) | Bergantung sumber asli |
| **Operasi `append` (`:+`)** | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ (*Amortized*) | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ (Konstruksi) |
| **Operasi `prepend` (`+:` / `::`)** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ (*Amortized*) | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ (Konstruksi) |
| **Akses Indeks Acak (`apply(i)`)** | $\mathcal{O}(n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ | Bergantung sumber asli |
| **Pembaruan Elemen Fungsional** | $\mathcal{O}(n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | Tidak Tersedia |
| **Alokasi Heap Perantara** | Tinggi per transformasi | Rendah-Sedang | Rendah (Khusus primitif) | Tinggi per evaluasi baru | **Nol / Dekat Nol** |
| **Penggunaan Kembali (*Reusability*)** | Ya (Immutable) | Ya (Immutable) | Ya (Immutable) | Ya (Tersimpan di heap) | Ya (Dihitung ulang) |

### Kapan Menggunakan Apa?
*   Gunakan **`Vector`** sebagai tipe urutan (*sequence*) baku (*default*) untuk keperluan komputasi umum.
*   Gunakan **`List`** hanya jika algoritma Anda murni menggunakan pola destrukturisasi rekursif *head/tail* dan operasi *prepending*. Hindari `List` untuk akses indeks acak dan `length`.
*   Gunakan **`ArraySeq`** jika Anda membutuhkan performa *cache-locality* bare-metal JVM setara array murni namun tetap membutuhkan semantik *immutable*.
*   Gunakan **`View`** ketika Anda merangkai lebih dari dua transformasi fungsional berturut-turut (misal: `.map.filter.map`) pada koleksi besar guna mengeliminasi alokasi objek perantara.
*   Gunakan **`LazyList`** jika Anda memodelkan deret matematika atau *event stream* tak berhingga (*infinite*) yang harus disimpan untuk penelusuran berulang.

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "LazyList Head Retention" Leak
Salah satu jebakan paling destruktif pada Scala adalah menahan pointer kepala dari `LazyList`.

```scala
// BAHAYA FATAL:
val stream = LazyList.from(1)
def processStream(): Unit =
  // Objek 'stream' dipegang di dalam closure/lingkup lokal yang tidak dibersihkan.
  // Semakin jauh kita membaca, semakin banyak node terisi memori di heap!
  val millionth = stream(10000000) 
  println(millionth)
```
*Solusi Arsitektural:* Jangan pernah menyimpan instance `LazyList` tak berhingga dalam field *stateful* atau variabel lokal jangka panjang jika akan diakses secara mendalam. Masukkan pemanggilan fungsi langsung ke dalam *pipeline*: `LazyList.from(1).drop(10000000).head`.

### 2. StackOverflowError pada Operasi Traversal Non-Tail-Recursive
Koleksi seperti `List` tidak dapat menampung jutaan elemen jika Anda memprosesnya menggunakan rekursi biasa tanpa anotasi `@tailrec`.

```scala
// BAHAYA: Mengonsumsi frame call-stack thread
def dangerousSum(list: List[Int]): Int = list match
  case Nil => 0
  case x :: xs => x + dangerousSum(xs) // Bukan tail-call! Operasi penambahan ditunda di stack.
```

### 3. Operasi Efek Samping Berulang pada View
Karena `View` mengevaluasi ulang seluruh pipa instruksi setiap kali dipanggil, meletakkan fungsi non-deterministik atau memiliki efek samping (*side-effecting logic*) di dalam `.view.map(...)` akan memicu eksekusi ganda yang membingungkan.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan `collection.size == 0` atau `collection.length == 0`
*   **Masalah:** Pada struktur data `List` atau koleksi evaluasi tertunda, `.length` memaksa mesin melintasi seluruh elemen dari ujung ke ujung hanya untuk mengetahui apakah koleksi tersebut kosong. Untuk koleksi dengan 10 juta elemen, ini adalah pemborosan waktu $\mathcal{O}(n)$. Untuk `LazyList` tak terhingga, ini memicu *infinite loop*.
*   **Koreksi:** Gunakan selalu `collection.isEmpty` atau `collection.nonEmpty` ($\mathcal{O}(1)$).

```scala
// BURUK
if list.length == 0 then doSomething()

// BENAR
if list.isEmpty then doSomething()
```

### Kesalahan 2: Menggunakan Akses Indeks Acak pada `List` di Dalam Loop
*   **Masalah:** Mengakses elemen `list(i)` di dalam perulangan menghasilkan kompleksitas kuadratik $\mathcal{O}(n^2)$.
*   **Koreksi:** Gunakan `Vector` jika memerlukan akses indeks langsung, atau gunakan *pattern matching* / destrukturisasi langsung.

```scala
// BURUK: Kompleksitas O(n^2)
val list = List.range(0, 100000)
for i <- 0 until list.length do
  val item = list(i) // Melintasi 'i' simpul dari awal setiap kali loop berjalan!

// BENAR: Menggunakan Vector O(n log32 n) atau Linear Traversal O(n)
val vec = Vector.range(0, 100000)
for i <- 0 until vec.length do
  val item = vec(i)
```

### Kesalahan 3: Berasumsi Bahwa `LazyList` Bebas Efek Samping Traversal
*   **Masalah:** Pemanggilan `lazyList.tail` mengevaluasi elemen kedua seketika. Evaluasi hanya tertunda pada isi dari ekor tersebut, bukan instansiasi simpul pembungkusnya.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutability by Default:** Selalu impor `scala.collection.immutable` (yang secara default sudah tersedia tanpa perlu diimpor). Impor `scala.collection.mutable` hanya pada cakupan lokal (*local method scope*) tertutup untuk optimasi kinerja internal.
2.  **Target Abstraction Level:** Menerima tipe koleksi paling abstrak pada parameter fungsi (`Iterable[A]` atau `Seq[A]`), namun mengembalikan tipe yang paling konkret (`Vector[A]`, `List[A]`) agar pemanggil fungsi mendapatkan kepastian performa dan semantik.
3.  **Pattern Matching daripada `head` dan `tail` Terbuka:** Hindari memanggil `.head` dan `.tail` secara eksplisit karena dapat melempar exception `NoSuchElementException` pada koleksi kosong. Gunakan *pattern matching*.

```scala
// Standar Industri: Ekstraksi Aman melalui Pattern Matching
def extractFirstTwo[A](seq: Seq[A]): Option[(A, A)] = seq match
  case first +: second +: _ => Some((first, second))
  case _                    => None
```

4.  **Terapkan Strict Boundaries pada Lazy Streams:** Selalu bungkus generator tak berhingga menggunakan operator pembatas seperti `.take(n)`, `.takeWhile(predicate)`, atau ubah ke *bounded Iterator*.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Optimasi 1: Ukur Kapasitas Builder Terlebih Dahulu (*Size Hinting*)
Ketika membangun koleksi dari sumber eksternal menggunakan `Builder`, JVM akan terus menerus mengalokasi ulang array internal jika ukurannya melampaui ambang batas default. Gunakan `sizeHint` untuk mereduksi beban GC.

```scala
import scala.collection.mutable.ArraySeq

def buildOptimizedCollection(size: Int): ArraySeq[Int] =
  val builder = ArraySeq.newBuilder[Int]
  builder.sizeHint(size) // Mengalokasikan array backing secara presisi sekali di awal!
  var i = 0
  while i < size do
    builder += i
    i += 1
  builder.result()
```

### Optimasi 2: Mencegah Auto-Boxing pada Koleksi Primitif
Secara arsitektur JVM, tipe generik Scala `List[Int]` akan membungkus nilai integer primitif ke dalam objek `java.lang.Integer` (*Boxing*). Ini meningkatkan footprint memori dari 4 byte menjadi 16-24 byte per integer.
*Solusi:* Untuk pemrosesan numerik performa tinggi, gunakan `Array[Int]` atau `scala.collection.immutable.ArraySeq.ofInt` yang langsung memetakan nilai ke array primitif JVM (`int[]`).

```scala
// Benchmark footprint:
// List[Int](1000000)      => ~24 MB memori heap
// Array[Int](1000000)     => ~4 MB memori heap kontinu
```

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Serangan Denial of Service (DoS) melalui Hash Collision
Implementasi standar `scala.collection.immutable.HashMap` dan `HashSet` menggunakan fungsi hash internal yang cepat. Namun, jika input berasal dari payload publik yang tidak divalidasi (misalnya: kunci JSON dari klien REST), penyerang dapat merekayasa string yang memiliki nilai hashcode identik (*hash collision attack*).
*Hardening:* Validasi panjang karakter kunci dan terapkan batas maksimum ukuran payload sebelum parsing ke dalam `Map`.

### 2. Thread Safety dan Safe Publication
Semua koleksi `immutable` di Scala bersifat aman terhadap pembacaan konkuren lintas *thread* (*thread-safe*) tanpa memerlukan blok `synchronized`. Simpul memori mereka bersifat *deeply frozen*. Namun, pastikan referensi objek itu sendiri dipertukarkan menggunakan deklarasi `volatile` atau struktur atomik (`java.util.concurrent.atomic.AtomicReference`) jika Anda memperbarui penunjuk variabel.

### 3. Perlindungan terhadap Infinite Stream DOS
Jangan mengekspos endpoint atau API internal yang menerima `LazyList` tanpa batas kedalaman (*unbounded recursion barrier*). Gunakan interceptor untuk memotong aliran data secara paksa jika konsumsi CPU atau alokasi elemen melebihi ambang batas SLA.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Proses penelusuran (*debugging*) transformasi fungsional pada koleksi yang lazy sering kali membingungkan karena urutan eksekusi tidak linear.

### Menggunakan Tap / Wiretapping untuk Debugging Pipeline

Operator `.tapEach` memungkinkan inspeksi elemen di tengah-tengah saluran pipa transformasi tanpa mengubah kondisi data atau menghentikan rantai fungsi.

```scala
val pipeline = List(1, 2, 3, 4, 5).view
  .map(_ * 10)
  .tapEach(item => println(s"[METRICS/AUDIT] Nilai pasca-map: $item"))
  .filter(_ > 25)
  .tapEach(item => println(s"[METRICS/AUDIT] Lolos filter: $item"))
  .to(Vector)
```

### Metrik Eksekusi Pipeline

Untuk mengukur dampak latensi dan throughput dari pipeline koleksi fungsional secara transparan, kita dapat membungkus *iterator* dengan pencatat waktu operasional:

```scala
def instrumentedIterator[A](tag: String, underlying: Iterator[A]): Iterator[A] =
  new Iterator[A]:
    private var counter = 0L
    def hasNext: Boolean = 
      val hasMore = underlying.hasNext
      if !hasMore then println(s"[TELEMETRY] Pipeline '$tag' selesai. Total elemen: $counter")
      hasMore

    def next(): A =
      counter += 1
      val start = System.nanoTime()
      val elem = underlying.next()
      val duration = System.nanoTime() - start
      if counter % 100000 == 0 then
        println(s"[TELEMETRY] Pipeline '$tag' memproses elemen ke-$counter dalam $duration ns")
      elem
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Karakteristik Kompleksitas Waktu Operasi Inti

| Struktur | Head | Tail | Prepend (`+:`) | Append (`:+`) | Lookup (`apply`) | Random Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`List`** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |
| **`Vector`** | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(\log_{32} n)$ | $\mathcal{O}(\log_{32} n)$ |
| **`ArraySeq`** | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ |
| **`Queue`** | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(1)$ | $\mathcal{O}(n)$ | $\mathcal{O}(n)$ |

*(Catatan: $\mathcal{O}(\log_{32} n)$ secara praktis sering disebut sebagai *Effectively $\mathcal{O}(1)$*).*

### Aturan Emas Pemilihan Koleksi:
1.  **Apakah Anda butuh akses acak berbasis indeks numerik?** $\rightarrow$ Gunakan **`Vector`**.
2.  **Apakah Anda melakukan operasi LIFO (Stack) atau rekursi terminal berbasis Cons?** $\rightarrow$ Gunakan **`List`**.
3.  **Apakah Anda perlu efisiensi memori tingkat tinggi untuk tipe primitif tanpa mutasi?** $\rightarrow$ Gunakan **`ArraySeq`**.
4.  **Apakah Anda merangkai banyak filter dan pemetaan?** $\rightarrow$ Konversi sementara ke **`.view`**, lalu simpan kembali dengan **`.to(Vector)`**.
5.  **Apakah ukuran data melebihi batas memori heap?** $\rightarrow$ Gunakan **`Iterator`** (untuk proses imperatif single-pass) atau **`LazyList`** (untuk fungsional multi-pass terkontrol).

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1.  **Pertanyaan:** Mengapa menambahkan elemen di awal (*prepending*) sebuah `List` bersifat $\mathcal{O}(1)$, sedangkan menambahkan elemen di akhir (*appending*) bersifat $\mathcal{O}(n)$?
    *   *Jawaban:* `List` adalah *singly-linked list*. Simpul baru cukup menunjuk pointer *head* lama sebagai *next*-nya tanpa mengubah simpul lain ($\mathcal{O}(1)$). Untuk menambahkan di akhir, rantai pointer dari simpul pertama hingga terakhir harus disusuri seluruhnya untuk membuat salinan baru simpul-simpul tersebut yang berujung pada simpul baru ($\mathcal{O}(n)$).
2.  **Pertanyaan:** Apa perbedaan fundamental antara `scala.collection.immutable.View` dan `scala.collection.immutable.LazyList`?
    *   *Jawaban:* Keduanya menunda evaluasi secara malas. Namun, `LazyList` melakukan *memoisasi* (menyimpan hasil komputasi di heap sehingga evaluasi kedua tidak mengulang fungsi), sedangkan `View` tidak melakukan memoisasi (komputasi selalu diulang dari awal setiap kali elemen-elemennya diakses kembali).
3.  **Pertanyaan:** Mengapa kita tidak boleh menggunakan method `iterator` lebih dari satu kali?
    *   *Jawaban:* Karena `Iterator` bersifat stateful dan berbasis mutasi pointer kursor internal. Ketika kursor telah mencapai elemen terakhir (`hasNext == false`), iterator telah habis dan tidak dapat dikembalikan ke posisi awal.
4.  **Pertanyaan:** Operasi manakah yang lebih efisien untuk memeriksa apakah sebuah koleksi kosong: `seq.length == 0` atau `seq.isEmpty`? Mengapa?
    *   *Jawaban:* `seq.isEmpty` jauh lebih efisien ($\mathcal{O}(1)$) karena hanya perlu memeriksa eksistensi simpul pertama. Sebaliknya, `seq.length == 0` pada struktur data seperti `List` atau `LazyList` harus menghitung seluruh simpul hingga elemen terakhir ($\mathcal{O}(n)$) sebelum membandingkannya dengan 0.
5.  **Pertanyaan:** Apa yang dimaksud dengan konsep *Structural Sharing* pada koleksi *immutable*?
    *   *Jawaban:* Mekanisme di mana versi baru dari koleksi menggunakan kembali (*shares*) referensi ke simpul-simpul internal dari koleksi lama yang tidak terpengaruh oleh operasi mutasi, sehingga menghemat konsumsi alokasi memori heap dan mempercepat performa pembuatan instance baru.

### Soal Tingkat Menengah (Intermediate)

6.  **Pertanyaan:** Perhatikan kode berikut:
    ```scala
    val stream = LazyList.from(1)
    val filtered = stream.filter(_ % 2 == 0)
    println(filtered.head)
    ```
    Berapa banyak simpul yang dievaluasi saat baris `println(filtered.head)` dieksekusi?
    *   *Jawaban:* Tepat 2 simpul dievaluasi: Elemen 1 dievaluasi oleh `filter` dan ditolak (`1 % 2 != 0`), kemudian elemen 2 dievaluasi, diterima (`2 % 2 == 0`), ditetapkan sebagai `head` dari `filtered`, dan evaluasi langsung berhenti seketika.
7.  **Pertanyaan:** Bagaimana arsitektur pohon Radix-32 pada `Vector` menjamin akses elemen acak yang cepat?
    *   *Jawaban:* Tingkat percabangan 32 membuat kedalaman pohon sangat dangkal (maksimal 7 tingkat untuk seluruh jangkauan signed 32-bit Integer JVM). Indeks dicari menggunakan operasi *bitwise shift* dan masking ($5$-bit per level) yang dijalankan langsung pada register CPU, menghasilkan waktu akses efektif $\mathcal{O}(1)$.
8.  **Pertanyaan:** Jelaskan mekanisme terjadinya kebocoran memori (*Memory Leak*) yang disebabkan oleh fenomena *Head Retention* pada `LazyList`!
    *   *Jawaban:* Terjadi ketika sebuah referensi ke simpul kepala (`head`) dari `LazyList` yang berukuran sangat besar atau tak berhingga tetap tertahan di variabel yang aktif di memori. Seiring traversi berjalan, simpul-simpul berikutnya yang telah dievaluasi akan termemoisasi dan membentuk rantai referensi kuat (*strong reference chain*) ke belakang, mencegah Garbage Collector membebaskan simpul-simpul tersebut dari memori heap.
9.  **Pertanyaan:** Mengapa Scala 2.13 mendesain ulang sistem koleksi dengan membuang pola arsitektur `CanBuildFrom`?
    *   *Jawaban:* `CanBuildFrom` memanfaatkan pencarian *implicit* kompleks yang menghasilkan pesan galat kompilasi yang sulit dipahami (*cryptic compiler errors*) dan membebani compiler. Penggantinya, `BuildFrom` dan `Factory`, menyederhanakan hierarki tipe, mempermudah perluasan koleksi kustom, dan mempercepat waktu kompilasi kode.
10. **Pertanyaan:** Dalam skenario pemrosesan data apa penggunaan `ArraySeq` secara tegas lebih dipilih dibandingkan `Vector`?
    *   *Jawaban:* Ketika data yang disimpan bertipe primitif (seperti `Int`, `Double`, `Long`), berukuran tetap, dan menuntut performa tinggi dengan *spatial memory locality* tinggi (menghindari penelusuran pointer pohon trie dan memanfaatkan CPU L1/L2 cache prefetching).

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: In-Memory Sliding-Window Financial Risk Aggregator

#### Deskripsi
Anda ditugaskan merancang modul mesin analisis risiko perbankan frekuensi tinggi (*High-Frequency Trading Risk Core*). Modul ini harus mampu memproses aliran masif transaksi *out-of-order* dan menghitung metrik statistik bergerak secara real-time tanpa kehabisan memori.

#### Spesifikasi Fungsional:
1.  **Domain Event:**
    ```scala
    final case class MarketTick(
        symbol: String,
        price: Double,
        volume: Long,
        timestampEpochMs: Long
    )
    ```
2.  **Kebutuhan Pipeline:**
    *   Buat generator `LazyList` tak terbatas yang mensimulasikan emisi `MarketTick` acak untuk 3 simbol saham ("BBCA", "BBRI", "TLKM").
    *   Bangun fungsi transformasi berbasis `View` yang menyaring tick dengan volume $\le 0$.
    *   Implementasikan algoritma jendela geser (*sliding window*) berukuran $K$ elemen (misal: 100 elemen terakhir) untuk setiap simbol secara independen.
    *   Gunakan struktur data persisten `scala.collection.immutable.Queue` atau `Vector` sebagai *internal ring buffer* jendela geser.
    *   Hitung *Volume Weighted Average Price* (VWAP) untuk setiap jendela geser:
        $$\text{VWAP} = \frac{\sum (\text{Price} \times \text{Volume})}{\sum \text{Volume}}$$
    *   Pasang *Circuit Breaker*: Jika dalam satu jendela geser nilai VWAP berfluktuasi lebih dari 15% dari harga tick penutupan sebelumnya, cetak pesan peringatan kritis dan terminasi pemrosesan tanpa menyebabkan `StackOverflowError`.

#### Batasan Teknis:
*   Maksimal JVM Heap yang dialokasikan: `-Xmx128m`.
*   Tidak boleh ada kebocoran memori heap selama eksekusi pemrosesan minimal 500.000 iterasi.
*   Seluruh state akumulasi agregasi wajib menggunakan koleksi *immutable* dan metode rekursi ekor murni (`@tailrec`).

#### Langkah Pengerjaan:
1.  Buka terminal dan buat direktori proyek baru berbasis sbt atau Scala CLI.
2.  Tuliskan struktur model domain dan fungsionalitas generator data stream.
3.  Implementasikan logika akumulator ring buffer jendela geser menggunakan `Queue`.
4.  Lakukan uji ketahanan alokasi memori menggunakan profiler JVM (seperti VisualVM atau JConsole) untuk memverifikasi grafik memori berada pada pola *sawtooth* yang stabil tanpa tren kebocoran (*leak trend*).
5.  Validasi terminasi sirkuit dan pastikan integritas matematis penghitungan metrik VWAP terbukti akurat.