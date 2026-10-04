# BAB 07: Quiz, Challenge, & Knowledge Check
**Konkurensi Asinkron & Actor Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Semantik Deklaratif `Future` vs. Model Komputasi Reaktif Actor
Jelaskan perbedaan fundamental dalam model eksekusi, retensi memori, dan paradigma *message dispatch* antara abstraksi `scala.concurrent.Future` dengan model Pekko/Akka *Actor*. Kapan komputasi asinkron cukup dimodelkan menggunakan komposisi monadik `Future` (`flatMap`/`for-comprehension`), dan pada ambang kompleksitas arsitektur apa sistem *wajib* beralih ke stateful *Actor Model*?

### Soal 1.2: Anatomi dan Risiko `ExecutionContext.global`
Bagaimana JVM mengelola eksekusi tugas di dalam `scala.concurrent.ExecutionContext.global` yang didukung oleh `ForkJoinPool` bawaan? Analisis dampak struktural terhadap *throughput* sistem jika seorang teknisi mengeksekusi operasi *blocking* I/O (seperti pemanggilan JDBC sinkron atau `Thread.sleep`) langsung di dalam `Future` yang terikat pada *context* global ini.

### Soal 1.3: Enkapsulasi State dan Jaminan *Happens-Before* pada Actor
Dalam model memori Java (JMM), akses konkuren terhadap state mutable memerlukan sinkronisasi (`volatile`, `synchronized`, atau CAS). Bagaimana Pekko/Akka Actor menjamin *thread-safety* terhadap *internal state* (variabel privat di dalam `Behavior`) tanpa mengharuskan developer menulis primitif *locking* manual? Jelaskan hubungannya dengan aturan *happens-before* pada pemrosesan antrean pesan (*Mailbox*).

### Soal 1.4: Pergeseran Paradigma: Akka/Pekko Classic (`ActorRef`) vs. Typed (`ActorRef[T]`)
Analisis kelemahan struktural pada Akka Classic yang bertumpu pada `receive: PartialFunction[Any, Unit]`, khususnya terkait *type-safety at compile-time*, kegagalan *dead-letter* saat *refactoring*, dan pengujian unit. Bagaimana Akka/Pekko Typed memitigasi masalah ini secara deterministik melalui `Behavior[T]` dan parameterisasi tipe ketat?

### Soal 1.5: Dualitas Primitif `Future` dan `Promise`
Secara arsitektural, `Future` merepresentasikan *read-only handle* ke nilai yang belum tentu selesai, sementara `Promise` merepresentasikan *write-once single-assignment container*. Jelaskan mekanisme internal bagaimana `Promise` menyelesaikan (*complete*) suatu `Future`. Apa konsekuensi runtime jika method `.success()` atau `.failure()` dipanggil lebih dari satu kali pada instans `Promise` yang sama?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis *Deadlock* pada *ForkJoinPool Worker Thread Starvation*
Diberikan cuplikan kode di mana 100 `Future` konkuren masing-masing menjalankan:
```scala
val f = Future {
  val nested = Future { doCompute() }
  Await.result(nested, 5.seconds)
}
```
Jika `ForkJoinPool` diinisialisasi dengan paralelisme sebesar 4 thread (sesuai core CPU), jelaskan secara mekanistik urutan kegagalan (*cascade failure*) yang memicu *thread starvation deadlock*. Mengapa konstruksi `scala.concurrent.blocking { ... }` mampu mencegah anomali ini, dan bagaimana `ManagedBlocker` menginstruksikan pool untuk melakukan kompensasi thread?

### Soal 2.2: Petaka *Leaking Actor State* Melalui Callback `Future`
Perhatikan anti-pattern fatal berikut di dalam sebuah Actor:
```scala
case class UpdateMetrics(value: Long)
class InsecureActor extends AbstractBehavior[UpdateMetrics] {
  private var internalCounter: Long = 0L

  override def onMessage(msg: UpdateMetrics): Behavior[UpdateMetrics] = {
    externalAsyncService.fetchFactor().foreach { factor =>
      // Mengakses dan memodifikasi state internal aktor di dalam callback Future!
      this.internalCounter += (msg.value * factor)
    }(context.executionContext)
    this
  }
}
```
Jelaskan mengapa kode di atas melanggar jaminan *Actor Encapsulation* dan memicu *silent data corruption* / *race condition*. Bagaimana solusi definitif menggunakan pattern `context.pipeToSelf` pada Akka/Pekko Typed untuk mengembalikan hasil `Future` ke dalam *Mailbox* aktor?

### Soal 2.3: Overhead GC dan Degradasi Performa pada *Ask Pattern* (`?`) Skala Masif
Penggunaan operator *Ask* (`actorRef ? RequestMessage`) mengembalikan sebuah `Future[Response]`. Bedah siklus hidup *Ask Pattern* di level internal:
1. Alokasi apa saja yang terjadi di heap untuk setiap pemanggilan *ask* (termasuk *temporary internal actor* dan *cancellation timer*)?
2. Apa ancaman sistemik terhadap Garbage Collector (khususnya Young Generation churn) ketika *Ask Pattern* digunakan sebagai komunikasi default antar 100.000 requests/detik, dibandingkan dengan *Tell Pattern* (`!`) berbasis asinkron murni?

### Soal 2.4: *Mailbox Overflow* dan Bahaya *Unbounded Mailbox*
Secara default, implementasi *Mailbox* di banyak sistem aktor menggunakan *unbounded queue* (`ConcurrentLinkedQueue`).
1. Jika laju kedatangan pesan (*producer rate*) secara konstan melebihi kapasitas eksekusi pesan oleh satu aktor (*consumer rate*), apa fase degradasi sistem sebelum terjadinya `OutOfMemoryError: Java heap space`?
2. Bagaimana perbandingan karakteristik mitigasi antara menggunakan *Bounded Mailbox* dengan strategi *Drop-Head* vs *Drop-Tail* vs *Dead-Letter Backpressure*?

### Soal 2.5: Isolasi Kerusakan melalui *Bulkheading Dispatcher*
Sebuah sistem terdistribusi memproses integrasi REST pihak ketiga yang lambat dan pemrosesan komputasi memori lokal berkecepatan tinggi. Keduanya berjalan pada *ActorSystem* yang sama.
Bagaimana Anda mengonfigurasi *dedicated dispatcher* (HOCON configuration) untuk mengisolasi aktor I/O lambat tersebut agar tidak mencemari *default dispatcher*? Tuliskan konfigurasi minimal thread-pool executor-nya dan bagaimana cara aktor menautkan dirinya ke dispatcher tersebut.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden *Thread Starvation Cascade* pada Payment Engine
* **Konteks:** Sebuah microservice Scala berbasis Akka-HTTP menangani lonjakan transaksi pembayaran saat *Flash Sale* (15.000 RPS). Di tengah lonjakan, layanan pihak ketiga (Payment Gateway) mengalami degradasi, menyebabkan latensi HTTP client meningkat dari 200 milidetik menjadi 15 detik.
* **Gejala:** 
  1. Utilisasi CPU drop dari 85% ke 4%, namun memori tetap stabil.
  2. Latensi HTTP p99 melonjak hingga mencapai nilai batas HTTP request timeout (60 detik).
  3. Metrik pool menunjukkan seluruh worker thread berstatus `WAITING` atau `TIMED_WAITING`. Service berhenti merespons *health check endpoint* (`/healthz`), memicu orkestrator Kubernetes me-restart container secara berulang (*crash loop*).
* **Pertanyaan Diagnostik:**
  1. Bagaimana korelasi antara degradasi dependensi eksternal dengan kolapsnya *thread pool* lokal jika integrasi HTTP menggunakan library blocking atau thread context yang salah?
  2. Langkah arsitektur spesifik apa yang harus diterapkan untuk memisahkan thread pool, mengonfigurasi *Circuit Breaker*, dan menetapkan timeout kaskade guna menstabilkan sistem?

### Skenario B: Silent State Corruption pada Distributed Trading System
* **Konteks:** Sistem *Order Matching Engine* frekuensi tinggi ditulis menggunakan Akka Typed. Setiap instans `OrderBookActor` mengelola *bid/ask queue* lokal dalam memori.
* **Gejala:** Laporan rekonsiliasi akhir hari menunjukkan inkonsistensi saldo sebesar miliaran rupiah. Tidak ditemukan satupun log error, exception, atau crash sistem. Pemeriksaan dump memori menunjukkan bahwa nilai `totalMatchedVolume` bernilai lebih rendah daripada agregasi transaksi riil yang tercatat di database persistence layer.
* **Pertanyaan Diagnostik:**
  1. Dari perspektif mutasi state internal aktor dan pemanggilan asinkron database via event-sourcing, di mana potensi celah masuknya *race condition* jika ada developer yang memutasi memori secara non-deterministik?
  2. Jika aktor memanfaatkan `Behaviors.receive` yang mengeksekusi I/O ke database secara paralel via `Future` dan memperbarui state tanpa menunggu konfirmasi persistence, bagaimana cara merefaktornya menggunakan pola state machine murni (`Behavior.same` yang mengembalikan state baru) dan Pekko/Akka Persistence (Event Sourcing) yang строго *linear*?

### Skenario C: Krisis *Split-Brain* dan Partisi Jaringan pada Stateful Cluster Sharding
* **Konteks:** Sistem perbankan mendistribusikan `AccountActor` menggunakan *Akka Cluster Sharding* di 12 node Kubernetes multi-zone. Terjadi gangguan jaringan serat optik antar Availability Zone (AZ-1 dan AZ-2) selama 45 detik (*network partition*).
* **Gejala:** 
  1. Kedua grup node di AZ-1 dan AZ-2 saling mendeteksi *unreachable* via *heartbeat failure detector* Phi Accrual.
  2. Klaster terbelah menjadi dua sub-klaster independen. Node di kedua sisi sama-sama mempromosikan diri menjadi *Leader* untuk shard yang sama.
  3. Klien di AZ-1 dan AZ-2 melakukan *withdrawal* konkuren pada aktor `AccountActor("ACC-999")` yang sama, menghasilkan *double-spending* masif.
* **Pertanyaan Diagnostik:**
  1. Apa akar kelemahan konfigurasi klaster yang membiarkan partisi jaringan menghasilkan pembentukan *quorum* ganda (*Split-Brain*)?
  2. Jelaskan mekanisme kerja *Split Brain Resolver* (SBR) dengan strategi *Keep Referee* atau *Lease-Based (via etcd/Kubernetes Lease)*. Bagaimana SBR secara matematis dan deterministik mengeksekusi *node fencing* (*downing/suicide*) pada sisi partisi yang tidak valid?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Fault-Tolerant Dynamic Rate-Limiter Engine

#### Problem Statement
Anda ditugaskan merancang *core engine* untuk API Rate-Limiter & Telemetry Ingestion berskala enterprise menggunakan **Scala 2.13 / 3** dan **Pekko/Akka Typed**. Sistem harus mampu memproses jutaan event metrik per detik, menerapkan pembatasan kuota dinamis (*Sliding-Window Algorithm*) per *tenant API Key*, dan memastikan ketahanan mutlak: *downstream persistence failure* tidak boleh merusak memori atau memblokir thread ingest utama.

#### Requirements
1. **Typed Architecture:**
   * Bangun hierarki protokol pesan yang *strictly typed* (`RateLimiterCommand`, `TelemetryCommand`, dll.).
   * Gunakan pattern `Behaviors.setup` dan manipulasi state via *functional parameter switching* (tanpa variabel `var` di luar struktur behavior).
2. **Dedicated Dispatcher & Non-Blocking Isolation:**
   * Pisahkan eksekusi parsing payload dan I/O sinkron ke persistence menggunakan dispatcher terisolasi (*dedicated thread pool*). Dispatcher aktor utama harus tetap bebas dari blocking.
3. **Sliding Window Rate-Limiter Actor:**
   * Setiap tenant direpresentasikan oleh satu aktor independen (atau dikelola via *Actor Sharding context* konseptual).
   * Menerapkan validasi kuota: misal, maks 1.000 request per jendela geser 10 detik. Jika melebihi batas, tolak pesan dengan status `RateLimitExceeded`.
4. **Fault Tolerance & Supervision:**
   * Jika subsistem persistensi internal melemparkan `DatabaseTransientException`, aktor harus di-*restart* dengan strategi *exponential backoff supervisor* (`Behaviors.supervise(...).onFailure(...)`).
   * Jika kegagalan adalah `CorruptedPayloadException`, pesan dibuang (*resume / drop*) dan dicatat tanpa me-restart aktor.
5. **No Leaking State:**
   * Komunikasi asinkron ke database atau service eksternal wajib menggunakan pattern `context.pipeToSelf`. Dilarang keras memutasi state dari dalam callback `onComplete`/`map` `Future`.

#### Constraints
* **Zero Mutable State Shared:** Dilarang menggunakan `var` global, `AtomicReference`, `ConcurrentHashMap`, atau primitive lock (`synchronized`).
* **Zero Await:** Penggunaan `Await.result` atau `Await.ready` dalam baris kode produksi adalah pelanggaran langsung (*instant failure*).
* **Deterministic Backpressure:** Aktor harus mendeteksi jika antrean internalnya melebihi threshold tertentu dan mulai merespons dengan status `Degraded/Backpressure`.

#### Expected Output
1. File konfigurasi HOCON `application.conf` yang mendefinisikan *custom-blocking-dispatcher* dan parameter klaster/aktor dasar.
2. Implementasi kode lengkap:
   * Deklarasi hierarki protokol (ADTs via `sealed trait`).
   * Implementasi aktor Rate Limiter dan Telemetry Worker.
   * Strategi supervisi dan *pipeToSelf* integration.
3. Driver pengujian (*test harness*) yang menyimulasikan 50.000 request konkuren untuk membuktikan:
   * Kuota tenant terpotong secara akurat tanpa *race condition*.
   * Thread starvation tidak terjadi meski database disimulasikan memiliki latensi tinggi (misal `Thread.sleep` 2 detik pada worker terisolasi).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Jaminan *happens-before* pada JVM Memory Model yang dihasilkan oleh pengiriman dan pemrosesan pesan dalam *Actor Mailbox*.
- [ ] Dampak perbedaan antara `ForkJoinPool` (work-stealing, compute-optimized) dan `ThreadPoolExecutor` (fixed/cached, I/O-optimized) terhadap throughput Scala `Future`.
- [ ] Mekanisme isolasi thread menggunakan HOCON *dedicated dispatchers* untuk mitigasi *blocking operations*.
- [ ] Anatomi kebocoran memori (*memory leak*) pada *Ask Pattern* dan mitigasinya menggunakan timeout eksplisit serta `pipeToSelf`.
- [ ] Semantik toleransi kesalahan *Let-It-Crash* dan hierarki *Supervision Strategy* (`Restart`, `Resume`, `Stop`) di Akka/Pekko Typed.
- [ ] Problem partisi jaringan (*Split-Brain*) pada sistem aktor terdistribusi dan cara kerja *Split-Brain Resolver* (SBR) berbasis *Quorum/Lease*.

### Saya tidak perlu menghafal:
- [ ] Nilai numerik konfigurasi default HOCON (misalnya: parameter internal Akka seperti default *heartbeat interval* atau nilai tepat *phi-threshold* pada accrual detector).
- [ ] Seluruh varian method legacy pada Akka Classic API (`sender()`, `context.become()`, `UntypedActor`).
- [ ] Detail internal implementasi bytecode Scala compiler dalam mentranslasikan `for-comprehension` menjadi rantai `flatMap`/`map`/`withFilter`.

### Saya harus bisa melakukan:
- [ ] Menulis pipeline asinkron yang aman menggunakan komposisi monadik `Future` tanpa pernah memanggil `Await.result`.
- [ ] Merancang protokol pesan aktor yang *type-safe* menggunakan ADT (`sealed trait` dan `final case class`) pada Pekko/Akka Typed.
- [ ] Mengintegrasikan hasil komputasi `Future` ke dalam stateful actor secara deterministik menggunakan `context.pipeToSelf`.
- [ ] Mendiagnosis dan menyelesaikan masalah *thread pool starvation* di lingkungan produksi dengan memanfaatkan thread dump analysis (`jstack`) dan konfigurasi bulkheading.
- [ ] Mengimplementasikan *Supervision Strategy* dengan konfigurasi *exponential backoff* dan penanganan tipe error kustom pada sistem berbasis aktor.