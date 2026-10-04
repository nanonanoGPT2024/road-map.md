# BAB 04: Quiz, Challenge, & Knowledge Check
**Sistem Koleksi Scala & Evaluasi**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Evaluasi — Strict, Lazy, dan View
Jelaskan perbedaan mendasar pada level eksekusi runtime dan alokasi memori antara `scala.collection.immutable.List`, `scala.collection.View`, dan `scala.collection.immutable.LazyList`. Kapan transformasi seperti `.map(f).filter(g)` menghasilkan struktur data perantara (*intermediate collection*), kapan hanya membentuk *thunk/computation graph*, dan bagaimana implikasinya terhadap alokasi heap saat memproses 10 juta elemen?

### Soal 1.2: Immutability dan Structural Sharing
Bagaimana `scala.collection.immutable.List` (singly-linked list) dan `scala.collection.immutable.Vector` (32-way Hash Array Mapped Trie / bit-mapped trie) mencapai efisiensi mutasi semu (*pseudo-mutation*) melalui *structural sharing*? Jelaskan mengapa operasi `x :: xs` berjalan dalam kompleksitas $O(1)$ tanpa menyalin elemen yang ada, sementara `xs :+ x` pada `List` berjalan dalam $O(N)$ dan mengharuskan duplikasi seluruh node sebelum elemen baru disematkan.

### Soal 1.3: Evolusi Hirarki Koleksi Scala 2.13+ dan Pola Factory
Pada Scala 2.13, arsitektur koleksi dirombak total dari model Scala 2.8 (`CanBuildFrom`). Jelaskan mengapa `CanBuildFrom` didepresiasi dan digantikan oleh `Factory` serta `BuildFrom[-From, -A, +C]`. Bagaimana hierarki baru berbasis `IterableOps` berhasil memisahkan implementasi operasi algoritma koleksi dari representasi konkretnya tanpa kehilangan informasi tipe statis (*static return-type preservation*)?

### Soal 1.4: Primitive Boxing, Memory Footprint, dan Cache Locality
Bandingkan layout memori JVM antara `Array[Double]`, `scala.collection.immutable.ArraySeq[Double]`, dan `scala.collection.immutable.Vector[Double]`. Jelaskan fenomena *autoboxing* (`java.lang.Double`), overhead *object header* (8–16 bytes), dan pointer indirection. Bagaimana trade-off ini berdampak langsung pada *CPU L1/L2 cache locality* saat melakukan operasi reduksi numerik intensif?

### Soal 1.5: Tail Recursion, Stack Safety, dan Semantik `foldLeft` vs `foldRight`
Mengapa implementasi `foldRight` pada struktur data linear strictly-evaluated seperti `List` rentan terhadap `StackOverflowError` untuk input berukuran besar, sedangkan `foldLeft` dijamin stack-safe? Tunjukkan bagaimana compiler Scala mengoptimasi `foldLeft` menjadi bytecode *loop* prosedural (`goto`), dan jelaskan kondisi di mana `foldRight` tetap aman digunakan (misalnya pada `LazyList` atau dengan pembungkusan monadik/trampolining).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Memory Leak Analisis: Head Retention pada `LazyList`
Diberikan cuplikan kode layanan agregasi data streaming berikut:

```scala
class EventProcessor {
  val events: LazyList[Event] = StreamProducer.infiniteEvents()

  def processPrefix(n: Int): Unit = {
    val sample = events.take(n).toList
    MetricsPublisher.publish(sample)
  }
}
```

Jelaskan mengapa instansiasi `EventProcessor` yang berjalan di dalam long-running actor atau singleton thread akan memicu `java.lang.OutOfMemoryError: Java heap space` seiring berjalannya waktu, meskipun `take(n)` hanya mengambil subset kecil. Identifikasi mekanisme *head retention* dan memoization pada `LazyList` yang bertanggung jawab atas kegagalan ini, lalu perbaiki kode tersebut agar beroperasi dalam konsumsi memori konstan ($O(1)$ space complexity).

### Soal 2.2: Degradasi HAMT dan Dampak Buruk `hashCode`
Koleksi `immutable.HashMap` dan `immutable.HashSet` di Scala mengandalkan struktur data *Hash Array Mapped Trie* (HAMT) dengan *branching factor* 32. 
1. Bagaimana representasi bitmap integer 32-bit mengeliminasi array pointer kosong (*sparse arrays*) melalui instruksi CPU `Integer.bitCount`?
2. Apa yang terjadi pada arsitektur internal HAMT ketika ribuan objek domain kustom yang memiliki implementasi `hashCode` buruk (misalnya: mengembalikan konstanta atau nilai modulo rendah) dimasukkan ke dalam `HashMap`? Diskusikan transisi node, degradasi kompleksitas pencarian dari $O(\log_{32} N)$ ke $O(N)$, dan implikasinya terhadap GC traversal.

### Soal 2.3: Stateful Iterator Exhaustion dan Side-Effect Traps
Perhatikan skenario transformasi data pipeline berikut:

```scala
def processBatches(iter: Iterator[DataChunk]): ProcessingResult = {
  val validated = iter.filter(_.isValid)
  val totalVolume = validated.map(_.volume).sum
  val anomalies = validated.filter(_.isAnomaly).toList

  ProcessingResult(totalVolume, anomalies)
}
```

Mengapa kode di atas menghasilkan bug logika laten (*silent bug*) di mana `anomalies` selalu bernilai `Nil` atau `totalVolume` bernilai tidak akurat? Jelaskan status internal (`knownSize`, pointer traversal) dari `scala.collection.Iterator`, mengapa iterator bersifat *single-pass*, dan rancang arsitektur solusinya tanpa harus menduplikasi seluruh dataset ke memori (`toList`).

### Soal 2.4: Integrasi Koleksi Kustom Menggunakan `BuildFrom`
Anda sedang membangun tipe koleksi performa-tinggi berorientasi sistem moneter: `FixedSizeBuffer[A]`. 
Rancang kerangka kode integrasi (*integration boilerplate*) menggunakan `BuildFrom` atau `Factory` di Scala 2.13+ sehingga pemanggilan operasi transformasi standar seperti:

```scala
val buffer: FixedSizeBuffer[Int] = ...
val doubled = buffer.map(_ * 2) // Tetap mengembalikan FixedSizeBuffer[Int]
val stringified = buffer.map(_.toString) // Mengembalikan FixedSizeBuffer[String]
```

dapat dikompilasi secara sah dengan inferensi tipe yang tepat tanpa melakukan *downcasting* tidak aman (`asInstanceOf`).

### Soal 2.5: Thread-Safety Anti-Pattern pada Parallel Collections
Banyak developer bermigrasi dari `collection.map(...)` ke `collection.par.map(...)` (`scala-parallel-collections`) dengan asumsi akselerasi linear tanpa efek samping.
1. Jelaskan bahaya *thread starvation* ketika `scala.collection.parallel` mengeksekusi blocking I/O (misalnya: pemanggilan database atau HTTP client) di dalam shared default `ForkJoinPool.commonPool`.
2. Jelaskan skenario *data race* fatal ketika lambdanya memutasi objek eksternal non-thread-safe (seperti `mutable.StringBuilder` atau `java.text.SimpleDateFormat`). Apa pemisahan domain yang benar antara Parallel Collections (CPU-bound) dan Reactive Streams / Asynchronous Effects (IO-bound)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM pada Pipeline Migrasi Database Skala Besar
* **Konteks:** Sebuah microservice bertugas memigrasi 50 juta log transaksi harian dari PostgreSQL ke Apache Cassandra. Service tersebut mengalami fatal failure: `java.lang.OutOfMemoryError: GC overhead limit exceeded` setiap 15 menit setelah dijalankan.
* **Investigasi Awal:** Cuplikan alur logika yang ditemukan oleh SRE pada codebase:
  ```scala
  def migrateBatch(startDate: Instant, endDate: Instant): Unit = {
    val records = queryAll(startDate, endDate) // Mengembalikan List[Transaction]
    val transformed = records
      .filter(_.status == "SUCCESS")
      .map(sanitizeData)
      .groupBy(_.merchantId)
    
    transformed.foreach { case (merchantId, txs) => 
      cassandraRepository.saveGroup(merchantId, txs) 
    }
  }
  ```
* **Heap Dump Analysis:** 85% alokasi heap dikuasai oleh `scala.collection.immutable.$colon$colon` (List nodes) dan jutaan objek referensi `Tuple2` serta struktur intermediate `HashMap`.
* **Pertanyaan Diagnostik:**
  1. Identifikasi setidaknya 3 titik cacat arsitektur dalam penggunaan koleksi Scala pada kode di atas yang memicu ledakan objek di Generational Garbage Collector (Young Gen / Tenured Gen).
  2. Rancang ulang arsitektur pemrosesan tersebut menggunakan kombinasi lazy constructs (`Iterator`, `View`, atau custom batched streaming) yang menjamin batas alokasi memori *flat* konstan (maksimum buffer $\le 5.000$ entitas dalam satu waktu), tanpa memotong alur logic `groupBy` merchantId secara sembarangan.

---

### Skenario B: Race Condition dan Memory Corruption pada Concurrency Cache In-Memory
* **Konteks:** Sebuah edge router API performa tinggi menggunakan in-memory cache lokal untuk otorisasi API Token. Route handler berjalan di atas Akka/Pekko HTTP dengan ribuan request per detik secara asinkron (`Future`).
* **Implementasi Kode:**
  ```scala
  class TokenSessionRegistry {
    // Menggunakan mutable collection standar untuk optimasi write speed
    private val sessions: mutable.Map[String, SessionData] = mutable.Map.empty

    def authenticate(token: String): Future[Option[SessionData]] = Future {
      sessions.get(token)
    }

    def updateSession(token: String, data: SessionData): Future[Unit] = Future {
      sessions.put(token, data)
    }
  }
  ```
* **Gejala di Lapangan:** Server sesekali mengalami CPU 100% pada satu core secara permanen, thread mengalami *infinite loop*, dan beberapa request mengalami silent truncation (sesi token yang valid tiba-tiba bernilai `None`).
* **Pertanyaan Diagnostik:**
  1. Bedah secara mendalam bagaimana struktur internal hash table pada `scala.collection.mutable.Map` (yang tidak thread-safe) mengalami kerusakan struktur linked-bucket selama proses *rehashing/resizing* ketika thread ganda melakukan mutasi konkruen (`put`). Mengapa ini menghasilkan siklus tertutup (*infinite pointer loop*)?
  2. Bandingkan 3 strategi remediasi arsitektur berikut dari segi latensi, thread-safety, dan overhead konkurensi:
     * Menggunakan `java.util.concurrent.ConcurrentHashMap` yang dibungkus Scala collection decorator.
     * Menggunakan `scala.collection.concurrent.TrieMap` (Ctrie - lock-free concurrent hash array mapped trie).
     * Menggunakan `scala.collection.immutable.Map` yang disimpan di dalam `java.util.concurrent.atomic.AtomicReference` dengan skema CAS (*Compare-And-Swap*). Kapan opsi ini justru menjadi bencana performa (*cas-retry storm*)?

---

### Skenario C: Bottleneck Serialisasi & Latensi Ekstrem pada Komputasi Terdistribusi
* **Konteks:** Sistem *real-time feature engineering* untuk deteksi fraud memproses jutaan vektor fitur numerik per detik. Vektor ini dikirimkan antar node cluster komputasi melalui jaringan privat.
* **Spesifikasi:** Setiap feature vector terdiri dari 256 nilai floating point berpresisi ganda (`Double`).
* **Kondisi Eksisting:**
  ```scala
  case class FeaturePayload(
    transactionId: String,
    features: List[Double] // Ukuran selalu 256 elemen
  )
  ```
* **Masalah:** Jaringan mengalami saturasi bandwidth (I/O saturation), dan pause time Garbage Collection di receiver node meningkat tajam, mengakibatkan pelanggaran batas SLA P99 (latensi melonjak dari 5ms ke 120ms).
* **Pertanyaan Diagnostik:**
  1. Hitung perkiraan memori byte-level teoretis dari satu instans `FeaturePayload` di atas pada 64-bit JVM dengan compressed OOPs aktif vs ukuran payload mentah yang sebenarnya dibutuhkan (256 * 8 bytes = 2048 bytes). Tunjukkan rincian pemborosan memori akibat boxing `java.lang.Double` dan node traversal `List`.
  2. Tentukan arsitektur struktur data pengganti terbaik:
     * Mengapa `Array[Double]` atau `IArray[Double]` (Scala 3) jauh lebih superior dibandingkan `Vector[Double]` atau `List[Double]` dalam skenario serialisasi biner dan cache line prefetching?
     * Bagaimana cara mempertahankan prinsip *immutability guarantees* pada level API tanpa harus membayar biaya overhead konversi/defensive copying saat data melintasi boundary layer?

---

## 4. Chapter Challenge

### Tantangan Praktis: Implementasi High-Throughput Non-Allocating Circular RingBuffer dengan Zero-Copy Immutable Windowing

#### Problem Statement
Dalam sistem pemrosesan sinyal finansial berlatensi rendah (*ultra-low latency trading metric*), Anda diwajibkan menghitung metrik statistik bergerak (*moving window statistics*, e.g., moving average, rolling variance) dari aliran kuotasi harga saham (*tick stream*). 

Implementasi berbasis koleksi standar Scala seperti `queue.enqueue(x).dequeue` atau `vector.tail :+ x` menghasilkan alokasi objek baru pada heap di setiap pergerakan jendela, yang memicu tekanan GC (*Garbage Collection pressure*) dan *jitter* latensi yang tidak dapat ditoleransi pada level microsecond.

#### Requirements
1. **Zero Heap Allocation pada Steady State:** Bangun kelas koleksi kustom bernama `FastRingBuffer[T: ClassTag](val capacity: Int)`. Setelah buffer diinisialisasi hingga kapasitas penuh, operasi `append(element: T): Unit` tidak boleh menghasilkan alokasi objek heap baru sama sekali (verifikasi zero object allocation).
2. **Koleksi Native Interop:** Kelas harus mengimplementasikan/meng-extend `scala.collection.Iterable[T]` sehingga dapat dievaluasi menggunakan standard library functions (`foreach`, `foldLeft`, `iterator`, dll.).
3. **Zero-Copy Immutable View (Windowing):** Implementasikan metode `.snapshotView: collection.IndexedSeq[T]` yang mengembalikan *immutable logical view* dari buffer saat ini (dari elemen tertua ke elemen terbaru) tanpa menduplikasi backing array. Mutasi berikutnya pada `FastRingBuffer` tidak boleh merusak integritas traversal snapshot yang sudah diterbitkan (gunakan skema *copy-on-write* selektif atau *generation tagging*).
4. **Fast Indexing:** Akses elemen logis via `.apply(index: Int)` pada view harus diselesaikan dalam waktu deterministik $O(1)$ dengan pemetaan indeks fisik yang efisien (gunakan operasi bitwise mask jika kapasitas diatur ke pangkat dua / *power-of-two capacity*).

#### Constraints
* Bahasa: Scala 2.13.x atau Scala 3.x murni.
* Dilarang menggunakan library pihak ketiga (hanya Scala standard library & JVM runtime primitives).
* Backing store internal wajib menggunakan unboxed flat structure: `Array[T]`.
* Bersifat stack-safe dan *allocation-free* untuk traversal intensif.

#### Expected Output
1. File implementasi: `FastRingBuffer.scala` yang memuat logika struktur data, pointer head/tail management, modul bitmask indexing, dan implementasi kustom `AbstractIterator[T]`.
2. Unit tests + Allocation Test: Bukti pengujian menggunakan assertion dasar yang memvalidasi integritas elemen siklik (*circular wrap-around logic*) dan verifikasi bahwa iterator melintasi data dari urutan kronologis yang benar (*oldest-to-newest*).

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman Anda terhadap arsitektur koleksi Scala sebelum melangkah ke bab berikutnya.

### Saya harus memahami:
- [ ] Arsitektur internal dan trade-off kompleksitas waktu ($O(1)$, $O(\log_{32} N)$, $O(N)$) untuk `List`, `Vector`, `ArraySeq`, `Queue`, `Set`, dan `Map` pada Scala standard library.
- [ ] Perbedaan fundamental antara evaluasi *Strict* (`StrictCollection`), *Non-strict Memoized* (`LazyList`), dan *Non-strict Non-memoized* (`View`, `Iterator`).
- [ ] Mengapa `Vector` mengadopsi 32-way branching tree (Radix Tree) dan bagaimana algoritma *bit-shifting* (`index >>> 5`, mask `0x1f`) mempercepat traversal level internal.
- [ ] Mekanisme kerja `Structural Sharing` pada manipulasi struktur data immutable dan bagaimana compiler/runtime mengelola referensi pointer.
- [ ] Dampak arsitektur JVM terhadap koleksi: Object Headers, Compressed OOPs, Alignment Padding, Reference Indirection, dan Garbage Collection footprint.
- [ ] Cara kerja hierarki koleksi Scala 2.13+: Pemisahan `Iterable` vs `IterableOps`, peran `Factory[-A, +C]`, dan penyelesaian type-transformation via `BuildFrom`.
- [ ] Masalah-masalah konkurensi fatal: Iterasi konkruen pada `mutable` map, thread starvation pada Parallel Collections, dan mekanika Lock-Free CAS pada `TrieMap`.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama method mikro pada hierarki internal `IterableOps` (misalnya: variasi internal `to...` methods selama memahami cara kerjanya via contract interface).
- [ ] Bit-level implementation detail yang detail dari algoritma HAMT resize logic pada library Scala secara verbatim.
- [ ] Implementasi internal method `cbf` (CanBuildFrom) legacy dari Scala 2.12 ke bawah, selain memahami alasan fundamental arsitektur tersebut dihapus.

### Saya harus bisa melakukan:
- [ ] Menulis transformasi pipeline data skala besar menggunakan `View` atau `Iterator` untuk menjaga konsumsi heap memori tetap konstan $O(1)$.
- [ ] Mendiagnosis dan mengeliminasi bug *head-retention memory leak* yang disebabkan oleh pemakaian `LazyList` / `Stream` yang salah.
- [ ] Mengonversi kode koleksi mutabel berbasis thread-unsafe ke bentuk thread-safe idiomatik (menggunakan `TrieMap`, immutable snapshots, atau immutable messaging) di lingkungan multithreading.
- [ ] Mengukur footprint memori koleksi secara akurat menggunakan profiling tools (JOL - Java Object Layout, VisualVM, atau YourKit).
- [ ] Membangun custom collection kelas enterprise yang mematuhi konvensi idiomatik Scala, lengkap dengan custom Builder dan Factory implementation.