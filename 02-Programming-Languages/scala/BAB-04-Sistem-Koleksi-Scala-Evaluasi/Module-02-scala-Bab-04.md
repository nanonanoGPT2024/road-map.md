# BAB 04: Sistem Koleksi Scala & Evaluasi
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menganalisis dan membongkar arsitektur internal dari sistem koleksi Scala 2.13/3 (HAMT, Bitmapped Vector Trie Radix-32, dan `ArraySeq`).
- Menguasai semantik evaluasi: Strict (*Eager*), Non-Strict (*Lazy*), serta perbandingan mendalam antara `LazyList`, `View`, dan `Iterator`.
- Mengeliminasi *space leak* (kebocoran memori akibat *head retention*) pada struktur data berbasis *lazy evaluation*.
- Mengimplementasikan pola transformasi *zero-allocation* dan mutasi terkontrol (*transient/builder patterns*) guna meminimalkan *Garbage Collection* (GC) *pressure* pada throughput tinggi.
- Merancang koleksi kustom (*custom immutable collections*) yang terintegrasi secara modular dengan `Factory` dan `BuildFrom`.
- Melakukan profil memori JVM, *cache-locality analysis*, dan *benchmarking* latensi mikrodetik pada sistem pemrosesan data terdistribusi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
- Hirarki dasar koleksi Scala (`Iterable`, `Seq`, `Set`, `Map`).
- Mekanisme Polimorfisme Tipe Tingkat Lanjut (*Typeclasses*, *Higher-Kinded Types* dasar).
- Model Memori JVM: Heap vs Stack, *Object Headers*, *Pointer Compression* (Oops), dan siklus hidup generasi GC (G1/ZGC).
- Imutabilitas struktural dan konsep *structural sharing*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Arsitektur Internal Bitmapped Vector Trie (Radix-32)
`scala.collection.immutable.Vector` adalah struktur data *general-purpose* standar dengan kompleksitas akses, *append*, dan *update* mendekati konstan ($O(\log_{32} N)$). 

```
Level 0 (Root)               [ Pointer 0 | Pointer 1 | ... | Pointer 31 ]
                                    |
Level 1                 +-----------+
                        v
              [ Pointer 0 | ... | Pointer 31 ]
                    |
Level 2             +-----------------------+
                                            v
                                 [ Data 0 | Data 1 | ... | Data 31 ]
```

- **Branching Factor ($M = 32$):** Setiap *node* internal memuat larik (*array*) dengan kapasitas maksimal 32 referensi.
- **Bit-Shifting Indexing:** Untuk menemukan elemen pada indeks $i$, algoritma menggunakan pergeseran bit (*bit shifting*) 5-bit ($2^5 = 32$):
  $$\text{Level-Offset} = (i \gg (5 \times \text{level})) \ \& \ 0x1F$$
- **Structural Sharing:** Saat melakukan modifikasi elemen melalui `.updated(index, value)`, Scala tidak menyalin seluruh struktur melainkan menduplikasi *path* dari *root* menuju daun target (*path copying*). Maksimal hanya $\lceil\log_{32} N\rceil$ *node* yang dialokasikan ulang, sementara cabang lainnya digunakan bersama (*shared reference*).

#### B. Hash Array Mapped Trie (HAMT)
Digunakan pada `immutable.HashMap` dan `immutable.HashSet`.
- Tidak seperti *hash table* berbasis *bucket-chaining* yang menderita saat *resizing*, HAMT mengonversi nilai *hash code* 32-bit menjadi pohon trie berkedalaman maksimal 7 tingkat ($6 \times 5\text{ bit} + 1 \times 2\text{ bit}$).
- HAMT mengoptimalkan konsumsi memori via kompresi larik menggunakan *bit population count* (`Integer.bitCount`). Larik internal tidak berukuran 32 elemen penuh, melainkan hanya dialokasikan sebesar jumlah elemen yang benar-benar ada. Nilai *bitmap* 32-bit menentukan pemetaan indeks logis ke indeks fisik:
  $$\text{Physical Index} = \text{bitCount}(\text{mask} \ \& \ ((1 \ll \text{chunk}) - 1))$$

#### C. Taksonomi Evaluasi: Strict, View, Iterator, dan LazyList

| Karakteristik | `Strict` (`List`, `Vector`) | `View` | `Iterator` | `LazyList` |
| :--- | :--- | :--- | :--- | :--- |
| **Waktu Evaluasi** | Instan (*eager*) | Ditunda (*on-demand*) | Ditunda (*on-demand*) | Ditunda (*on-demand*) |
| **Memoization** | Seluruh data di memori | Tanpa memoisasi | Tanpa memoisasi | Memoize elemen terevaluasi |
| **Status (*State*)** | *Immutable* | *Immutable / Stateless* | *Stateful* (sekali pakai) | *Immutable* |
| **Penggunaan Ulang**| Aman | Aman (evaluasi ulang) | Tidak bisa (habis dikonsumsi) | Aman |
| **Konsumsi Memori** | $O(N)$ langsung | $O(1)$ overhead | $O(1)$ overhead | $O(N)$ progresif |

- **`View`:** Representasi penundaan transformasi (*lazy pipeline*). Setiap pemanggilan `.map` atau `.filter` hanya menyusun fungsi komparator/transformasi baru tanpa mengeksekusinya. Data dievaluasi setiap kali ada operasi terminal seperti `.fold`, `.foreach`, atau `.toVector`.
- **`Iterator`:** Abstraksi transversal berbasis pointer mutabel primitif via metode `hasNext` dan `next()`. Sangat hemat alokasi memori tetapi tidak aman terhadap *concurrency* dan tidak dapat dibaca berulang.
- **`LazyList`:** Menggantikan `Stream` lama sejak Scala 2.13. Karakteristik utamanya adalah *lazy tail* dan *lazy head*. Berbahaya terhadap kebocoran memori jika *head* dipegang oleh referensi persisten (*Head Retention Space Leak*).

---

### 4. Why & What

- **Mengapa Redesign Koleksi Scala 2.13 Dibutuhkan?**
  Implementasi koleksi Scala lama (2.8 - 2.12) berbasis *CanBuildFrom* sangat kompleks pada level *type system*, menghasilkan ukuran *bytecode* yang masif, pesan kesalahan kompilasi yang sulit dipahami, dan *overhead polymorphic dispatch* yang membebani JIT compiler. Redesign 2.13 memotong lapisan abstraksi berlebih, memisahkan hirarki *strict* dan *lazy*, serta menyederhanakan mekanisme transformasi menggunakan trait `BuildFrom` dan `Factory`.
- **Apa itu `ArraySeq`?**
  `ArraySeq` adalah koleksi *immutable sequence* yang membungkus *array* primitif/referensi Java secara langsung. Ini memberikan performa lokalitas memori (*CPU cache lines*) mendekati *raw array* dengan garansi imutabilitas, menghindari *boxing* ketika menggunakan varian terspesialisasi (seperti `ArraySeq.ofInt`).

---

### 5. How (Workflow Detail)

Alur pengeksekusian evaluasi koleksi Scala dari kompilasi ke JVM runtime:

```
[Scala Source Code]
        |
        v
[Pipeline Assembly: coll.view.filter(...).map(...)]
        |
        +--> Membungkus koleksi dalam view transformer
        |
[Terminal Operation: .to(ArraySeq)]
        |
        v
[Factory Resolution: ArraySeq.evidence / BuildFrom]
        |
        v
[Builder Allocation: mutable.ArrayBuilder]
        |
        v
[Single-Pass Loop: while(iter.hasNext) { evaluate -> builder += res }]
        |
        v
[Wrapping: ArraySeq.unsafeWrapArray(builder.result)] (Zero Copy)
```

1. **Transformasi Lazy:** Ketika operasi intermediat dipanggil di atas `.view`, Scala mengembalikan instance turunan `View` (misalnya `View.Filter`, `View.Map`). Tidak ada alokasi buffer intermediat.
2. **Materialisasi Melalui Builder:** Saat memanggil operasi terminal, sistem mencari implicit `Factory` yang sesuai dengan tipe data target.
3. **Optimasi Ukuran Eksak:** Jika ukuran koleksi sumber diketahui (*known size* via `knownSize`), builder akan mengalokasikan array penampung akhir secara presisi dalam satu kali alokasi (tanpa re-alokasi amortisasi).
4. **Finalisasi Imutabilitas:** Larik primitif/referensi diubah menjadi koleksi imutabel tanpa menyalin ulang memory array (*zero-copy wrap* melalui metode internal `unsafeWrapArray`).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Jalur Perakitan Pabrik (Strict vs View vs LazyList)

- **Strict Collection (`Vector` / `List`):** Setiap stasiun perakitan menyelesaikan semua 10.000 mobil sebelum mengirimkannya ke stasiun berikutnya. Gudang penyimpanan antara stasiun 1 dan 2 harus menampung 10.000 unit barang setengah jadi (Konsumsi memori tinggi).
- **View:** Jalur pipa mekanis tanpa gudang. Stasiun perakitan mobil hanya mengambil satu komponen, memprosesnya melalui stasiun 1, 2, dan 3 secara instan langsung ke truk muatan. Jika Anda butuh truk kedua, seluruh pabrik harus memproduksi dari nol lagi.
- **LazyList:** Mirip dengan `View`, tetapi setiap mobil yang selesai melewati stasiun langsung didokumentasikan dan diparkir permanen di garasi. Mobil tidak pernah dibuat dua kali, tetapi jika garasi tidak pernah dikosongkan, pabrik kehabisan ruang lahan (*Out Of Memory*).

#### Diagram Transisi Evaluasi dan Memory Footprint

```
STRICT: coll.filter(F).map(M)
Memory: [ [Input Data: N] ] ---> [Intermediate Buffer: M] ---> [Final Result: M]
Allocations: 2 Array Objects (High GC Pressure)

VIEW: coll.view.filter(F).map(M).to(Vector)
Memory: [ [Input Data: N] ] ----------------------------------> [Final Result: M]
             (No intermediate array; Pipeline fused in CPU registers)
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menghentikan Head-Retention Space Leak pada `LazyList`

```scala
package com.enterprise.collections.eval

object LazyListSpaceLeakAnalysis {

  // KASUS BURUK: Space Leak via Head Retention
  // Objek menahan pointer ke kepala LazyList, mencegah GC membersihkan elemen yang telah dilewati.
  class LeakyPipeline {
    val infiniteNumbers: LazyList[BigInt] = {
      def loop(n: BigInt): LazyList[BigInt] = n #:: loop(n + 1)
      loop(0)
    }

    def processBatch(limit: Int): BigInt = {
      // infiniteNumbers tetap memegang pointer ke elemen 0
      infiniteNumbers.take(limit).foldLeft(BigInt(0))(_ + _)
    }
  }

  // KASUS BENAR: Zero-Retention Tail Evaluation
  class SafePipeline {
    // Definisi dibuat sebagai method bertipe def (bukan val)
    def infiniteNumbers(start: BigInt = 0): LazyList[BigInt] = {
      def loop(n: BigInt): LazyList[BigInt] = n #:: loop(n + 1)
      loop(start)
    }

    def processBatch(limit: Int): BigInt = {
      // Referensi lokal yang dapat dikonsumsi GC saat eksekusi berlangsung
      infiniteNumbers().take(limit).foldLeft(BigInt(0))(_ + _)
    }
  }

  def main(args: Array[String]): Unit = {
    val safe = new SafePipeline
    println(s"Result: ${safe.processBatch(1000000)}")
  }
}
```

#### Practical Example: High-Performance Zero-Allocation Custom Processing Pipeline

Implementasi pipeline agregasi log throughput tinggi menggunakan `ArraySeq`, `View`, dan mutasi transien internal yang aman secara fungsional.

```scala
package com.enterprise.collections.pipeline

import scala.collection.immutable.ArraySeq
import scala.collection.mutable

final case class AuditLog(
    timestamp: Long,
    userId: Long,
    serviceId: Short,
    payloadSize: Int,
    isError: Boolean
)

object AuditLogAggregator {

  // Metrik terdistribusi yang padat memori (Cache-line friendly)
  final case class ServiceMetrics(
      totalEvents: Long,
      totalPayload: Long,
      errorCount: Long
  )

  /**
   * Pemrosesan skala enterprise: Mengeliminasi alokasi objek per-record menggunakan View.
   * Tidak ada alokasi intermediat selama filtering dan map aggregation.
   */
  def aggregateMetricsByService(
      logs: ArraySeq[AuditLog]
  ): Map[Short, ServiceMetrics] = {
    // Menggunakan mutasi transien internal yang terlokalisasi (Pure from the outside)
    val accumulator = mutable.Map.empty[Short, (Long, Long, Long)]

    // Pipeline evaluasi lazy: Tanpa alokasi intermediate sequence
    logs.view
      .filter(log => log.payloadSize > 0)
      .foreach { log =>
        val current = accumulator.getOrElse(log.serviceId, (0L, 0L, 0L))
        val errorInc = if (log.isError) 1L else 0L
        accumulator.update(
          log.serviceId,
          (
            current._1 + 1L,
            current._2 + log.payloadSize.toLong,
            current._3 + errorInc
          )
        )
      }

    // Freeze data ke immutable collection secara efisien
    accumulator.view.mapValues { case (count, payload, errors) =>
      ServiceMetrics(count, payload, errors)
    }.toMap
  }
}
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Pada arsitektur mesin pencocokan order (*Order Matching Engine*) di industri *fintech*, sistem menerima lonjakan 500.000 transaksi limit order per detik.

#### Masalah Utama
Sistem mengalami lonjakan jeda *Stop-The-World* (STW) GC pada generasi G1GC hingga 850ms, mengakibatkan penalti SLA latensi p99.9. Analisis *heap dump* menunjukkan alokasi sementara jutaan objek turunan `scala.collection.immutable.$colon$colon` (`List`) dan *boxed primitive tuples* akibat operasi `.filter(...).map(...)` standar pada batch data pesanan.

#### Solusi Arsitektural
1. Migrasi dari struktur linked-list (`List`) ke `ArraySeq.ofRef` dan struktur non-boxing `ArraySeq.ofInt` untuk ID numerik.
2. Mengganti evaluasi intermediat *eager* dengan `.view` terpaut batasan alokasi builder kustom berbasis `ArrayBuilder`.
3. Memanfaatkan `BuildFrom` eksplisit untuk mentransformasi secara paralel ke memory buffer yang telah dialokasikan sebelumnya (*pre-allocated fixed-size ring buffers*).

#### Kode Implementasi Solusi Produksi

```scala
package com.enterprise.trading.engine

import scala.collection.immutable.ArraySeq
import scala.collection.mutable.ArrayBuilder

final case class Order(
    orderId: Long,
    priceCents: Long,
    quantity: Int,
    side: Byte // 0 = Buy, 1 = Sell
)

object UltraLowLatencyEngine {

  /**
   * Ekstraksi Volume Beli bernilai tinggi secara zero-intermediate-allocation.
   * Menghindari boxing primitif dan intermediate node collections.
   */
  def computeHighValueBuyQuantities(
      orders: ArraySeq[Order],
      thresholdPriceCents: Long
  ): ArraySeq[Int] = {
    // ArrayBuilder terhindar dari boxing overhead primitif
    val builder = ArrayBuilder.make[Int]()
    
    // Prediksi kapasitas builder jika memungkinkan untuk mencegah amortized array-copy
    val maxPotentialSize = orders.knownSize
    if (maxPotentialSize > 0) {
      builder.sizeHint(maxPotentialSize)
    }

    // Menggunakan iterator/while teroptimasi JIT
    val iter = orders.iterator
    while (iter.hasNext) {
      val order = iter.next()
      if (order.side == 0 && order.priceCents >= thresholdPriceCents) {
        builder += order.quantity
      }
    }

    // Wrap array primitif native ke immutable ArraySeq secara O(1) tanpa memori kloning
    builder.result()
  }
}
```

#### Hasil Metrik Produksi
- **Alokasi Heap:** Menurun sebesar 82% per batch transaksi.
- **Frekuensi G1 Young-Gen Collection:** Menurun dari 12 kali/menit menjadi 1 kali/menit.
- **Latensi p99.9:** Terpangkas dari 850 milidetik menjadi 1.2 milidetik.

---

### 9. Trade-offs (Analisis Komparatif Arsitektur)

```
                 PERFORMANCE SPECTRUM Koleksi Scala
Low Latency / Zero Alloc                        High Structural Sharing
<--------------------------------------------------------------------->
ArraySeq (Native Array)        Vector (Radix-32)             List (Linked)
- Cache Line Optimized        - Balanced Speed              - O(1) Prepend only
- Poor random structural      - High Memory Overhead        - Poor CPU cache locality
  updates (O(N) copy)           (Branching Nodes)           - High GC reference chasing
```

| Kriteria | `ArraySeq` | `Vector` (Radix-32) | `List` | `LazyList` |
| :--- | :--- | :--- | :--- | :--- |
| **Locality of Reference** | Sangat Tinggi (L1/L2 cache hit) | Sedang (Terkendala *pointer chasing*) | Buruk (*Scatter pointers*) | Buruk |
| **Random Access Cost** | $O(1)$ Native | $O(\log_{32} N)$ (~Konstan) | $O(N)$ Traversal | $O(N)$ Traversal |
| **Append Cost** | $O(N)$ Full Array Copy | Amortized $O(1)$ | $O(N)$ | Amortized $O(1)$ |
| **Prepend Cost** | $O(N)$ Full Array Copy | Amortized $O(1)$ | $O(1)$ | $O(1)$ |
| **Update in Place (Immut.)** | $O(N)$ Full Array Copy | $O(\log_{32} N)$ Path Copying | $O(N)$ | Tidak disarankan |
| **Memory Overhead per Data** | ~0 Bytes (Hanya Array Object Header)| Ekstra *internal nodes* (~1.5x - 2x) | 24-32 Bytes per cell | Sangat Tinggi (Thunks + Memo) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Space Leak akibat *Head Retention* pada `LazyList`
- **Gejala:** Memory leak lambat namun pasti (*Out of Memory Error: Java Heap Space*) pada thread/service berumur panjang.
- **Penyebab:** Menyimpan instansiasi `LazyList` pada variabel referensi persisten (`val` di dalam `Singleton Object` atau `Class`). Saat elemen dikonsumsi menggunakan `.tail`, node kepala tidak dapat direklamasi GC karena pointer awal masih eksis.
- **Solusi:** Gunakan pemanggilan `def` atau segera batasi jangkauan lokal dari referensi `LazyList`.

#### 2. Konversi Antara Java dan Scala Tanpa Mempertimbangkan Salinan
- **Gejala:** Penurunan throughput drastis saat memanggil *interop method* eksternal Java (`List` $\leftrightarrow$ `java.util.List`).
- **Penyebab:** Menggunakan `scala.jdk.CollectionConverters._` dengan struktur `List` Scala yang memicu *deep-traversal cloning* menjadi `ArrayList`.
- **Solusi:** Gunakan `ArraySeq` bersama Java interop untuk memungkinkan konversi *direct array view* jika memungkinkan, atau minimalkan konversi di batas terluar (*boundary layers*).

#### 3. Evaluasi Ganda pada Traversal `View`
- **Gejala:** Performa lebih lambat secara signifikan setelah mengubah `.toVector` menjadi `.view`.
- **Penyebab:** `View` **tidak** menyimpan hasil komputasi (*stateless non-memoizing*). Jika Anda memanggil `val v = coll.view.map(expensiveCalculation)` lalu mengakses `v.take(10)` dan kemudian `v.take(20)`, fungsi kalkulasi akan dijalankan dua kali untuk 10 elemen pertama!
- **Solusi:** Selalu materialisasi `View` ke koleksi *strict* (`.to(Vector)`) jika hasilnya akan dibaca lebih dari satu kali.

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan `Vector` sebagai Default Seq Imutabel:** Pilih `Vector` ketimbang `List` kecuali jika pola akses didominasi mutlak oleh operasi *pure prepend* ($O(1)$) dan *head deconstruction*.
- [ ] **Gunakan `ArraySeq` untuk Read-Heavy / Data Terstruktur:** Saat data dikonstruksi sekali lalu dibaca berkali-kali tanpa modifikasi, gunakan `ArraySeq` untuk memanfaatkan CPU L1/L2 data cache.
- [ ] **Gunakan `View` untuk Rangkaian Transformasi:** Rantai operasi intermediat (`filter`, `map`, `collect`, `drop`) yang terdiri lebih dari 2 tahapan wajib diawali dengan `.view` dan diakhiri dengan tipe data konkret target untuk memusnahkan alokasi buffer temporer.
- [ ] **Hindari Primitive Boxing Menggunakan Spesialisasi Koleksi:** Untuk data numerik berskala besar (jutaan elemen), gunakan representasi `Array[T]` mentah atau `ArraySeq` terspesialisasi, hindari `List[Int]` atau `Map[Long, Long]` yang menghasilkan *boxed wrapper objects*.
- [ ] **Verifikasi KnownSize pada Custom Collection Pipeline:** Selalu manfaatkan metode `knownSize` saat membuat alokasi builder target guna mengeliminasi operasi *array doubling/resizing* internal pada JVM.

---

### 12. Hands-on Practice

Buat dan simpan struktur berkas berikut di:  
`hands-on/m02/src/main/scala/com/enterprise/collections/CustomFastBuffer.scala`

#### Langkah Praktikum:
1. Mengembangkan arsitektur koleksi *custom append-only chunked buffer* yang mengeliminasi re-alokasi array kontinu besar dengan memecahnya ke blok tetap (*chunk-based allocation*).
2. Mengintegrasikan koleksi tersebut ke dalam sistem `Factory` Scala standar.

```scala
package com.enterprise.collections

import scala.collection.Factory
import scala.collection.mutable.Builder
import scala.reflect.ClassTag

/**
 * Custom Chunked Collection: Mencegah alokasi continuous memory raksasa 
 * pada JVM yang memicu fragmentasi heap.
 */
final class ChunkedBuffer[A: ClassTag] private (
    private val chunks: Array[Array[A]],
    val length: Int,
    private val chunkSize: Int
) extends Iterable[A] {

  override def iterator: Iterator[A] = new Iterator[A] {
    private var currentIndex = 0

    override def hasNext: Boolean = currentIndex < length

    override def next(): A = {
      if (!hasNext) throw new NoSuchElementException("Iterator habis")
      val chunkIdx = currentIndex / chunkSize
      val elementIdx = currentIndex % chunkSize
      val elem = chunks(chunkIdx)(elementIdx)
      currentIndex += 1
      elem
    }
  }

  override def knownSize: Int = length
}

object ChunkedBuffer {
  private val DefaultChunkSize = 1024

  def newBuilder[A: ClassTag](chunkSize: Int = DefaultChunkSize): Builder[A, ChunkedBuffer[A]] =
    new Builder[A, ChunkedBuffer[A]] {
      private val masterChunks = scala.collection.mutable.ArrayBuffer[Array[A]]()
      private var currentChunk = new Array[A](chunkSize)
      private var currentOffset = 0
      private var totalElements = 0

      override def addOne(elem: A): this.type = {
        if (currentOffset >= chunkSize) {
          masterChunks += currentChunk
          currentChunk = new Array[A](chunkSize)
          currentOffset = 0
        }
        currentChunk(currentOffset) = elem
        currentOffset += 1
        totalElements += 1
        this
      }

      override def clear(): Unit = {
        masterChunks.clear()
        currentChunk = new Array[A](chunkSize)
        currentOffset = 0
        totalElements = 0
      }

      override def result(): ChunkedBuffer[A] = {
        if (currentOffset > 0) {
          val trimmedLastChunk = new Array[A](currentOffset)
          System.arraycopy(currentChunk, 0, trimmedLastChunk, 0, currentOffset)
          masterChunks += trimmedLastChunk
        }
        new ChunkedBuffer[A](masterChunks.toArray, totalElements, chunkSize)
      }
    }

  implicit def canBuildFrom[A: ClassTag]: Factory[A, ChunkedBuffer[A]] =
    new Factory[A, ChunkedBuffer[A]] {
      override def fromSpecific(it: IterableOnce[A]): ChunkedBuffer[A] = {
        val b = newBuilder[A]()
        b ++= it
        b.result()
      }
      override def newBuilder: Builder[A, ChunkedBuffer[A]] = ChunkedBuffer.newBuilder[A]()
    }
}
```

---

### 13. Exercise

#### Level Easy
Tuliskan sebuah fungsi `def evaluateLazyPipeline(input: LazyList[Int]): (Int, LazyList[Int])` yang mengevaluasi elemen pertama secara aman tanpa memicu evaluasi penuh elemen-elemen selanjutnya, dan mengembalikan tuple berisi elemen pertama serta ekor (*tail*) yang belum terevaluasi.

#### Level Medium
Diberikan sebuah koleksi besar `orders: ArraySeq[(Long, Double)]` yang merepresentasikan `(OrderId, Amount)`. Buatlah transformasi menggunakan `.view` yang memvalidasi `Amount > 0.0`, menambahkan PPN 11%, membuang transaksi di bawah 100.0, lalu mengumpulkannya kembali ke dalam struktur `ArraySeq[Double]` tanpa memicu alokasi memori untuk koleksi penampung temporer di antara pemanggilan fungsi.

#### Level Hard
Rancang sebuah custom `Builder` Scala yang membungkus *Direct Byte Buffer* (Off-Heap via `java.nio.ByteBuffer`) yang mengimplementasikan `Builder[Long, ArraySeq[Long]]`. Builder ini harus mengumpulkan data angka long ke *off-heap memory* terlebih dahulu guna menghindari GC generational pressure selama batch ingest, dan hanya memindahkan ke *heap* melalui representasi `ArraySeq` saat metode `result()` dipanggil.

---

### 14. Challenge

**Skenario Tantangan:**  
Sebuah platform streaming real-time IoT menerima telemetri dari 10.000 turbin angin. Setiap sensor mengirimkan ribuan paket per detik berupa `SensorReading(sensorId: Int, timestamp: Long, value: Double)`. Anda diminta mendesain modul pemroses *sliding window* berbasis evaluasi lazy (`WindowedAggregator`) tanpa kerangka kerja eksternal (murni pustaka standar Scala):

1. Modul harus mampu menerima *infinite stream* data berbasis `LazyList`.
2. Anda harus mengimplementasikan fungsi sliding window kustom:  
   `def slidingStats(stream: LazyList[SensorReading], windowSize: Int, slideStep: Int): LazyList[TurbinSummary]`
3. **Batas Ketat:** Pemrosesan harus bebas dari masalah *Head Retention*. Ruang memori heap JVM harus konstan ($O(\text{windowSize})$) meskipun dialiri triliunan pembacaan data. Jika sistem didiamkan berjalan selama 24 jam dengan batas memori JVM `-Xmx64m`, sistem dilarang mengalami `OutOfMemoryError`. Buktikan solusi arsitektural Anda aman dari kebocoran memori berbasis siklus referensi thunk memoization.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Konseptual Dasar
1. Berapakah batas *branching factor* standar dari struktur internal `scala.collection.immutable.Vector` pada Scala 2.13/3, dan mengapa angka tersebut dipilih?
2. Mengapa operasi penambahan elemen `+:` atau `:+` pada `Vector` diklasifikasikan sebagai $O(1)$ amortized padahal memerlukan *path copying*?
3. Jelaskan perbedaan mendasar antara `scala.collection.View` dan `scala.collection.Iterator` dalam konteks penanganan *state* dan transversal berulang!
4. Apa yang menyebabkan `scala.collection.immutable.Stream` digantikan oleh `LazyList` pada Scala versi 2.13?
5. Mengapa tipe `ArraySeq` lebih disukai dibanding `Vector` untuk dataset terstruktur berukuran masif yang jarang dimodifikasi secara struktural?

#### B. Pertanyaan Konseptual Intermediate
6. Bagaimana struktur internal HAMT (`HashMap`) mencegah overhead array kosong 32-slot pada setiap node yang hanya memiliki 1 atau 2 anak elemen?
7. Diberikan kode berikut:  
   `val pipeline = coll.view.filter(f).map(g)`  
   Kapan fungsi `f` dan `g` dieksekusi oleh runtime JVM?
8. Bagaimana implementasi `knownSize` pada sistem koleksi Scala mengoptimalkan alokasi memori pada fase kompilasi/eksekusi builder?
9. Apa bahaya utama menulis kode seperti ini di scope singleton object?  
   `val numbers: LazyList[Int] = LazyList.from(1)`
10. Mengapa `ArraySeq.unsafeWrapArray` dinamakan *unsafe*, dan jaminan apa yang harus dijaga pengembang saat menggunakannya dalam arsitektur zero-copy?

#### C. Skenario Analisis Kasus Produksi
11. **Skenario 1:** Sebuah layanan mikro mendadak membeku (*unresponsive*) tanpa pesan galat di konsol logs. Saat dianalisis dengan `jstack`, terlihat thread engine terjebak dalam GC loop terus menerus. Analisis heap dump menunjukkan terdapat 4 GB instance bertipe `scala.collection.immutable.LazyList$$anon$1`. Apa investigasi pertama Anda, dan bagian kode mana yang kemungkinan besar memegang referensi ke head node?
12. **Skenario 2:** Tim performa melaporkan bahwa latensi service pemrosesan batch turun drastis setelah mengganti `Vector` menjadi `List` di seluruh sistem model entitas karena anggapan bahwa `List` lebih cepat untuk `head` dan `tail`. Tunjukkan secara arsitektural mengapa keputusan ini salah besar untuk server modern multi-core!
13. **Skenario 3:** Anda mendeteksi alokasi memori yang melonjak drastis saat memanggil:  
    `coll.map(_.toDouble).toArray`  
    Padahal `coll` adalah `ArraySeq[Int]` berukuran 50.000.000 elemen. Tunjukkan titik kegagalan alokasi dan bagaimana restrukturisasi kodenya agar berjalan dengan alokasi *zero-boxing*!

---

### 16. Summary

Sistem koleksi Scala modern (2.13+) merupakan perpaduan antara kemurnian fungsional (*functional purity*), keamanan referensial (*referential transparency*), dan efisiensi level mesin. Pengembang sistem enterprise harus memahami secara mendalam struktur internal koleksi data:

1. **Pemilihan Struktur Data yang Presisi:** Gunakan `ArraySeq` untuk keunggulan lokalitas cache perangkat keras dan akses acak zero-overhead; gunakan `Vector` untuk struktur data serbaguna dengan kebutuhan pembaruan struktural imutabel seimbang ($O(\log_{32} N)$); dan batasi penggunaan `List` hanya untuk algoritma rekursif struktural berbasis *head/tail*.
2. **Karakteristik Evaluasi:** Jangan rancang sistem performa tinggi dengan *eager chaining*. Manfaatkan `View` untuk menggabungkan (*fusion*) rantai komputasi tanpa alokasi perantara.
3. **Waspadai Memoisasi:** Bedakan secara mutlak antara `LazyList` (dengan *memoization*, rawan space leak) dan `View` (tanpa *memoization*, aman terhadap heap retainment namun melakukan evaluasi ulang).
4. **Pola Produksi Berperforma Ekstrem:** Minimalkan pemakaian memori dan tekanan GC pada sistem terdistribusi dengan memadukan *mutasi internal terlokalisasi* (`mutable.Builder`), pemanfaatan `sizeHint`, dan pembekuan akhir imutabel berbasis *structural sharing* atau *zero-copy array wrapping*.