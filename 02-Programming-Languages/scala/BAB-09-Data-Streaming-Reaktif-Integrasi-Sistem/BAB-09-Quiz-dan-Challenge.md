# BAB 09: Quiz, Challenge, & Knowledge Check
**Data Streaming Reaktif & Integrasi Sistem**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Spesifikasi Reactive Streams & Kontrak Backpressure Dinamis:**
   Jelaskan secara presisi arsitektural bagaimana 4 antarmuka utama Reactive Streams (`Publisher[T]`, `Subscriber[T]`, `Subscription`, dan `Processor[T1, T2]`) mencegah *consumer saturation*. Mengapa pemanggilan `Subscription.request(n)` secara mutlak membalik kendali (*inversion of control*) dari model *pure-push* tradisional menjadi model *dynamic push-pull hybrid*? Apa konsekuensi fatal pada alokasi heap jika sebuah implementasi `Publisher` mengabaikan batas nilai $n$ tersebut?

2. **Perbedaan Paradigma Eksekusi: Akka/Pekko Streams vs Functional Streams (FS2 / ZIO Streams):**
   Bandingkan arsitektur eksekusi internal antara model berbasis *Actor/GraphStage materialization* (Akka/Pekko Streams) dengan model *purely functional pull-based stream* (FS2 yang didukung Cats Effect atau ZIO Streams). Bagaimana keduanya merepresentasikan siklus hidup (*lifecycle*), alokasi thread (*runtime scheduling*), dan penanganan *resource acquisition/release* (misal: penutupan koneksi TCP atau *file descriptor*)?

3. **Semantik Konkurensi Operator Asinkron:**
   Jelaskan perbedaan mendasar antara operator `mapAsync` dan `mapAsyncUnordered` pada eksekusi stream reaktif (khususnya di Pekko Streams) atau `parEvalMap` vs `parEvalMapUnordered` (pada FS2). Bagaimana *internal buffering* bekerja untuk mempertahankan urutan elemen pada varian *ordered*, dan apa implikasi langsungnya terhadap penggunaan memori serta latensi sistem jika terjadi *head-of-line blocking* pada salah satu *Future/IO* yang lambat?

4. **Siklus Hidup Stream, Propagasi Sinyal, dan Teardown:**
   Uraikan aliran propagasi sinyal pada saat terjadi:
   - Pembatalan dari downstream (*downstream cancellation* via `cancel()`).
   - Sinyal terminasi normal dari upstream (*completion signal* via `onComplete()`).
   - Sinyal kegagalan (*error signal* via `onError(t)`).  
   Mengapa spesifikasi Reactive Streams mewajibkan bahwa setelah `onError` atau `onComplete` dipancarkan, tidak boleh ada sinyal lain yang dikirimkan, dan bagaimana status `Subscription` dijamin terisolasi dari *memory leak*?

5. **Supervisi Stream vs Terminasi Fatal:**
   Dalam arsitektur streaming reaktif di Scala, bedakan antara penanganan error lokal berbasis *supervision strategy* (misalnya: `Resume`, `Restart`, `Stop` pada Akka/Pekko Streams atau *combinator* `recover`/`handleErrorWith` pada FS2/ZIO) dengan kegagalan fatal tingkat stream (*stream abortion*). Kapan sebuah error harus menyebabkan seluruh *materialized stream* mati, dan kapan stream harus terus berjalan menggunakan fallback pattern?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Inspeksi JVM & Analisis Asynchronous Boundary (`.async`):**
   Secara default, tahapan-tahapan operator dalam sebuah graph stream (misalnya Pekko Streams) dapat dioptimalkan melalui *operator fusion* yang berjalan pada *single actor/thread context*. Kapan Anda secara eksplisit harus menyisipkan `.async` boundary? Bagaimana mekanisme *ring buffer* (ukuran default internal buffer) beroperasi di antara dua boundary asinkron, dan mengapa salah menempatkan boundary dapat memicu degradasi performa akibat *excessive context-switching*?

2. **Dilema Kafka Consumer Rebalance & Backpressure Stall:**
   Saat mengintegrasikan Kafka consumer reaktif (seperti Alpakka Kafka / FS2-Kafka), laju konsumsi pesan dikendalikan oleh backpressure downstream. Jika downstream mengalami penundaan parah (misal: menunggu batch write ke basis data yang lambat), thread polling Kafka berisiko melampaui `max.poll.interval.ms`. Jelaskan secara teknis bagaimana insiden *consumer group rebalancing loop* (livelock) dapat terjadi dalam kondisi ini dan bagaimana konfigurasi `max.poll.records`, pemisahan commit offset, atau *commit-within-flow* mengatasi masalah tersebut.

3. **Deadlock Topologi Siklik pada GraphDSL:**
   Pada topologi stream yang kompleks yang memiliki jalur *feedback loop* (aliran data memutar balik ke operator hulu melalui merge stage), jelaskan skenario di mana *deadlock* backpressure dapat terjadi. Mengapa keberadaan buffer eksplisit dengan kapasitas tertentu mutlak diwajibkan dalam siklus feedback, dan bagaimana Anda mendeteksi kondisi kebuntuan (*pipeline freezing*) ini menggunakan JMX thread dump atau streaming metrics?

4. **Thread Starvation Akibat Blocking I/O dalam Stream Stage:**
   Diberikan potongan kode di mana seorang engineer mengeksekusi panggilan JDBC/blocking HTTP Client secara langsung di dalam blok `.map(x => blockingCall(x))` tanpa dispatcher terpisah. Jelaskan bagaimana hal ini merusak *thread pool execution context* (misalnya `default-dispatcher` pada Akka atau *compute pool* pada Cats Effect). Tunjukkan bagaimana merancang isolasi pool menggunakan custom dispatcher/thread pool terdedikasi (`blocking-dispatcher` atau `IO.blocking`).

5. **Semantik Offset Commit: At-Most-Once, At-Least-Once, dan Tantangan Effectively-Once:**
   Jelaskan implementasi alur data streaming yang menjamin semantik *at-least-once processing*. Mengapa commit offset ke message broker hanya boleh dilakukan *setelah* downstream sink berhasil merespons (*ack*)? Apa yang terjadi jika offset di-commit secara asynchronous dalam batching terpisah (`commitBatchWithin`), dan arsitektur idempoten apa yang wajib diterapkan pada sisi consumer untuk menangani redelivery pasca *node crash*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden OOM pada Pipeline Ingesti Black Friday
Sebuah platform e-commerce skala besar di JVM/Scala memproses lonjakan transaksi *flash sale* melalui pipeline streaming:
`Kafka Source -> Ingestion Flow -> Enrichment Flow (REST call ke Inventory API via third-party SDK) -> Elasticsearch Sink`.

Saat beban memuncak (50.000 msg/detik):
- Utilisasi heap melonjak drastis hingga memicu `java.lang.OutOfMemoryError: Java heap space`.
- Analisis heap dump (HPROF) menunjukkan 85% memori terisi oleh jutaan instance objek internal `PendingRequest` milik client HTTP pihak ketiga yang dipanggil di dalam tahapan *enrichment*.
- Konfigurasi stream menggunakan operator custom `GraphStage` yang membungkus *asynchronous callback* dari Java SDK non-reaktif.

**Pertanyaan Diagnostik & Solusi:**
1. Apa akar penyebab kerusakan rantai backpressure pada integrasi SDK non-reaktif tersebut?
2. Bagaimana Anda mendesain ulang integrasi SDK third-party tersebut menggunakan primitives backpressure (misalnya implementasi backpressured custom `GraphStage` atau pemanfaatan `Source.queue` / `AsyncCallback` dengan semantik `offer` yang menangani rejection)?
3. Tunjukkan arsitektur mitigasi *overflow* jika downstream downstream API memang memiliki batasan *rate limit* fisik (misalnya: *drop*, *sliding buffer*, atau *exponential backoff throttle*).

---

### Skenario B: Dual-Write Inconsistency & Race Condition pada Change-Data-Capture (CDC)
Sebuah arsitektur streaming perbankan mengonsumsi event mutasi rekening dari Debezium/Kafka:
`CDC Kafka Source -> Validation -> Balance Aggregator -> [Dual Target: Cassandra DB + Fraud Detection WebSocket]`.

Masalah yang muncul di produksi:
- Selama lonjakan traffic, beberapa event mutasi terdeteksi masuk ke Cassandra, namun WebSocket *Fraud Detection* menerima urutan mutasi yang terbalik (*out-of-order execution*).
- Setelah diselidiki, engineer menggunakan operator branching `.alsoTo` dan menambahkan `.mapAsync(concurrency = 8)` pada masing-masing cabang untuk meningkatkan throughput penulisan.
- Ketika salah satu database node mengalami transient timeout, Cassandra sink gagal menulis sebagian data, sementara offset Kafka telah terlanjur ter-commit karena WebSocket branch sukses mengirimkan data.

**Pertanyaan Diagnostik & Solusi:**
1. Mengapa kombinasi branching (`alsoTo` / broadcast) dan *uncontrolled async concurrency* pada stream CDC merusak jaminan linearitas data (*per-account ordering*)?
2. Bagaimana memulihkan relasi konsistensi antara dua sink yang berbeda kecepatan tanpa memicu *split-brain* status commit Kafka?
3. Rancang strategi pengelompokan event (*substream partitioning* via `groupBy` berdasarkan `accountId`) yang menjaga urutan strik transaksi per entitas, sembari tetap mengeksekusi akun-akun lain secara paralel.

---

### Skenario C: Migrasi Arsitektur Streaming: Pekko Streams vs FS2
Divisi infrastruktur perusahaan telekomunikasi memproses 10 Gbps log jaringan real-time. Pipeline lama berbasis Pekko Streams menghadapi masalah kompleksitas pemeliharaan akibat penumpukan *mutable state* di dalam custom `GraphStage` dan kebutuhan *dynamic topology reconfiguration* saat runtime (menambah/mengurangi filtering rule jaringan secara dinamis tanpa me-restart pipeline). Sebagian tim mengusulkan rewrite menggunakan **FS2 (Functional Streams for Scala)** dengan Cats Effect.

**Pertanyaan Diagnostik & Solusi:**
1. Tinjau secara mendalam kelebihan dan trade-off arsitektural antara model Pekko Streams (Actor-backed, graph-based optimization, enterprise tooling) vs FS2 (Pure FP, pull-based, interkoneksi tinggi dengan *typelevel ecosystem*, fiber-based concurrency) untuk use-case data throughput raksasa.
2. Bagaimana FS2 menyelesaikan masalah *dynamic reconfiguration* (misalnya menggunakan `fs2.concurrent.SignallingRef` atau `fs2.concurrent.Channel`) secara elegan dibandingkan dynamic stream manipulation pada Pekko Streams (`KillSwitches`, dynamic merge hub)?
3. Apa potensi *performance penalty* (alokasi objek, GC pressure) dari model pure FP functional streaming pada beban saturasi bandwidth tinggi, dan strategi tuning JVM apa yang esensial untuk menguranginya?

---

## 4. Chapter Challenge

### Tantangan Praktis: "Resilient Financial Audit & Fraud Stream Engine"

#### Problem Statement
Anda diminta membangun mesin pemrosesan streaming transaksi real-time (*Financial Audit Pipeline*) berdaya tahan tinggi menggunakan Scala (disarankan menggunakan **Pekko Streams** atau **FS2**). Engine ini harus memproses aliran transaksi mentah, memvalidasi dan mendeteksi anomali, melakukan audit logging terenkripsi ke database/storage secara batch, serta menjamin tidak ada data yang hilang atau corrupt saat terjadi pemadaman sistem (*system outage*).

#### Architectural Requirements
1. **Source & Partitioning:**
   - Konsumsi mock stream transaksi: `case class Transaction(txId: String, accountId: String, amount: BigDecimal, timestamp: Long)`.
   - Laju data input minimum 10.000 events/detik.
   - Partisi stream berdasarkan `accountId` sehingga urutan transaksi per akun terjamin 100% konsisten (*strict ordering*), namun pemrosesan antar-akun berbeda dilakukan secara konkuren.

2. **Stateful Fraud Window Detection:**
   - Gunakan windowing (misal: sliding window 5 detik atau stateful scanning).
   - Deteksi pola *Rapid Withdrawal*: Jika sebuah `accountId` melakukan lebih dari 3 kali transaksi dengan `amount > 5000` dalam rentang waktu 5 detik, pancarkan alert `case class FraudAlert(accountId: String, txIds: List[String], reason: String)` ke downstream alert channel secara instan.

3. **External Rate-Limited Enrichment:**
   - Lakukan pengkayaan data status reputasi rekening ke layanan mock eksternal (`lookupReputation(accountId: String): Future[ReputationScore]`).
   - Mock service ini rapuh: memiliki *rate limit* ketat (maksimal 500 request/detik) dan dapat mengalami *transient error* (HTTP 503).
   - Terapkan mekanisme backpressure teratur, retry terisolasi (*exponential backoff* dengan *jitter*), dan *circuit breaker* agar stream utama tidak crash ketika mock service mengalami downtime.

4. **Batched & Resilient Sink (Transactional Semantics):**
   - Lakukan agregasi batching audit log: kumpulkan data hingga 500 transaksi ATAU waktu mencapai rentang 200 ms (mana yang terpenuhi lebih dulu).
   - Simulasikan batch write ke storage: jika batch write gagal, lakukan recovery dan jangan biarkan status pemrosesan di-commit.
   - Terapkan integrasi offset handling tiruan (mock offset commit) yang hanya dieksekusi secara asinkron setelah batch write storage berhasil dipersistensi secara atomik (*at-least-once guarantee*).

5. **Graceful Shutdown & Signal Handling:**
   - Tangani JVM SIGINT/SIGTERM (Coordinated Shutdown).
   - Saat sinyal terminasi diterima, upstream harus berhenti menerima event baru, seluruh in-flight buffers harus dialirkan sampai tuntas ke sink (*drain*), batch terakhir wajib dipersistensikan, dan semua resource eksternal ditutup secara bersih tanpa memicu data loss.

#### Constraints
- Wajib ditulis dalam **Scala 2.13 atau Scala 3**.
- Dilarang keras menggunakan panggilan blocking (`Thread.sleep`, `Await.result`) di dalam alur stream.
- Zero data loss: matikan proses secara paksa via simulation crash dan buktikan via assertion test bahwa tidak ada transaksi yang hilang atau tercatat ganda tanpa audit trail.

#### Expected Deliverables
- **Pipeline Implementation:** File source code Scala (`AuditStreamingEngine.scala`) yang mengimplementasikan seluruh topologi.
- **Resilience Test Suite:** File test (ScalaTest / MUnit) yang menyimulasikan:
  1. *Upstream pressure test* (laju data melebihi kapasitas downstream).
  2. *Transient network failure* pada enricher service yang memvalidasi circuit breaker & retry.
  3. *Graceful shutdown test* yang memverifikasi pengosongan in-flight buffer secara bersih.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal dan spesifikasi kontrak 4 antarmuka Reactive Streams (`Publisher`, `Subscriber`, `Subscription`, `Processor`).
- [ ] Bagaimana sinyal *demand* dinamis (`Subscription.request(n)`) mengendalikan penggunaan memori dan mencegah buffer overflow secara deterministik.
- [ ] Mekanisme *Operator Fusion* vs *Asynchronous Boundaries* (`.async`) serta dampaknya pada latency, throughput, dan thread context switching.
- [ ] Perbedaan eksekusi antara *Actor-backed GraphStages* (Pekko/Akka) dan *Functional Pull/Fiber-based Streaming* (FS2/ZIO).
- [ ] Perbedaan semantik konkurensi: *Ordered* vs *Unordered processing* (`mapAsync` vs `mapAsyncUnordered`) dan trade-off konsumsi memorinya.
- [ ] Mekanisme deteksi kegagalan, pembatalan downstream (*cancellation propagation*), dan pembersihan resource berbasis *bracket/Resource pattern*.
- [ ] Titik kritis integrasi broker data (misal: Apache Kafka) yang memicu *consumer group rebalance* akibat downstream backpressure stall.
- [ ] Semantik penjaminan pengiriman pesan: *At-most-once*, *At-least-once*, dan *Idempotent effectively-once processing*.

### Saya tidak perlu menghafal:
- [ ] Seluruh variasi nama operator spesifik yang jarang digunakan pada DSL (misalnya: variasi langka dari operator filtering internal framework) — cukup pahami konsep transformasinya.
- [ ] Nilai default angka kapasitas buffer internal dari masing-masing framework streaming (misal: 16 untuk Akka Streams, 64 untuk ZIO) — nilai ini selalu dapat dikonfigurasi via `application.conf` atau runtime argument.
- [ ] Tanda tangan method byte-code internal dari runtime interpreter stream; fokuslah pada semantic behavior level API dan model konkurennya.

### Saya harus bisa melakukan:
- [ ] Membangun custom stream stage / operator yang mematuhi hukum backpressure (tidak memanggil *push* tanpa ada *demand* aktif).
- [ ] Mengonfigurasi strategi supervisi dan pemulihan error stream secara presisi menggunakan combinator `recover`, `restart`, atau custom decision logic.
- [ ] Mengintegrasikan blocking legacy code / JDBC ke dalam non-blocking stream pipeline secara aman dengan isolasi *custom execution context / dedicated thread pool*.
- [ ] Mendiagnosis dan mengurai insiden *pipeline deadlock* atau memory leak yang dipicu oleh buffer tak terbatas (*unbounded buffers*) menggunakan Java Flight Recorder (JFR) dan JVM Heap Dump.
- [ ] Menerapkan pipeline stream branching dan merging yang aman tanpa memicu race condition, out-of-order execution, atau state corruption.
- [ ] Menulis test suite komprehensif untuk pipeline reaktif menggunakan utilitas streaming test-kit (`TestSubscriber`, `TestPublisher`, atau FS2 test runtime).