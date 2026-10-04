# MODUL PEMBELAJARAN: DATA STREAMING REAKTIF & INTEGRASI SISTEM
**Kategori:** 02-Programming-Languages | **Track:** Scala Enterprise Engineering | **Bab 09 — Modul 01**

---

## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul:** `SCA-09-01`
* **Judul:** Data Streaming Reaktif & Integrasi Sistem (*Reactive Data Streaming & System Integration*)
* **Tingkat Kesulitan:** Tingkat Lanjut (*Advanced*)
* **Estimasi Waktu Penyelesaian:** 6–8 Jam Pembelajaran Mandiri / Praktikum Lab
* **Prasyarat Pengetahuan:**
  * Penguasaan Scala 3 fundamental (OOP, FP, Givens, Pattern Matching).
  * Pemahaman model konkurensi asinkron (`scala.concurrent.Future`, `ExecutionContext`).
  * Pengetahuan dasar message broker (Apache Kafka) dan basis data relasional/NoSQL.
  * Prinsip *The Reactive Manifesto* (Responsive, Resilient, Elastic, Message Driven).
* **Dependencies & Tooling:**
  * Scala: `3.3.3 LTS` (atau versi Scala 3 terbaru)
  * Build Tool: `sbt` v1.9+
  * Core Engine: `org.apache.pekko` %% `pekko-stream` % `1.0.2` & `pekko-stream-kafka` % `1.0.0`
  * JSON Parser: `io.circe` %%% `circe-core` / `circe-generic` / `circe-parser` % `0.14.6`
  * Testing: `org.scalatest` %% `scalatest` % `3.2.18`, `pekko-stream-testkit` % `1.0.2`

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda ditargetkan untuk memiliki kapabilitas profesional berikut:

1. **Menganalisis dan Mengimplementasikan Spesifikasi Reactive Streams:** Menguasai mekanisme protokol *Dynamic Push-Pull Backpressure* pada layer spesifikasi `org.reactivestreams` (Publisher, Subscriber, Subscription, Processor) di dalam JVM.
2. **Merancang Pipeline Topologi Kompleks:** Menyusun topologi pemrosesan stream non-linear (fan-out, fan-in, broadcast, zip, merge-preferred) menggunakan Pekko Streams Graph DSL dengan jaminan *type safety*.
3. **Mengisolasi Domain Kegagalan (Failure Domains):** Menerapkan strategi *supervision decider* (`Restart`, `Resume`, `Stop`) dan mengimplementasikan pola integrasi tangguh (*circuit breaker*, *retry with exponential backoff*, *dead-letter queues*).
4. **Membangun Integrasi Sistem Nir-Blokir (*Non-Blocking*):** Mengintegrasikan *inbound message bus* (Kafka) ke *outbound sinks* (HTTP endpoints, database RDBMS/NoSQL) dengan pengaturan buffer deterministik untuk mencegah insiden `OutOfMemoryError` (OOM).
5. **Mengoptimalkan Kinerja Pemrosesan Stream:** Mengatur batas isolasi konkurensi antarkomponen (*fusing boundaries* via `.async`), mengeliminasi overhead *context switching*, dan mengonfigurasi metrik telemetri streaming.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Batch vs Pull-Push Stream

Pemrosesan data konvensional beroperasi dengan paradigma *Collection-Oriented* (semua elemen dimuat ke memori, diproses per *batch*, lalu diteruskan). Pendekatan ini rentan mengalami kegagalan katastropik saat volume data tak terbatas (*unbounded*) dialirkan ke dalam sistem:

```
[Paradigma Konvensional (Unbounded Buffering)]
Producer (Cepat: 10k msg/s) ---> [ BUFFER (OOM Crash!) ] ---> Consumer (Lambat: 1k msg/s)
```

Data Streaming Reaktif mengubah relasi antar-komponen dari model dorong buta (*naive push*) atau tarik konstan (*polling pull*) menjadi **Protokol Push-Pull Dinamis**:

```
[Paradigma Reactive Streams (Dynamic Push-Pull)]
Producer <--- (1) Request Demand (n=3) <--- Consumer
Producer ---> (2) Push Data Elements (n<=3) ---> Consumer
```

### Mental Model 3-Lapisan Pekko Streams

Pekko Streams memisahkan logika deklarasi dengan eksekusi fisik:
1. **Blueprint / Graph Layer:** Anda mendefinisikan *resep* atau *topologi* data menggunakan struktur tipe data kekal (`Source`, `Flow`, `Sink`, `RunnableGraph`). Pada tahap ini, belum ada alokasi thread, pemanggilan I/O, atau pemrosesan elemen data.
2. **Materializer Layer:** Sub-sistem runtime yang bertugas mengubah blueprint abstrak menjadi aktor-aktor (`ActorRef`) di balik layar, mengalokasikan buffer internal, dan menetapkan koneksi TCP/channel data.
3. **Execution Layer:** Aliran data aktual yang diatur oleh sinyal demand (*backpressure protocol*) dari hulu (*upstream*) ke hilir (*downstream*).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Topologi integrasi sistem reaktif enterprise melibatkan integrasi multi-protokol dengan jalur eksekusi terisolasi:

```
+---------------------------------------------------------------------------------------+
|                                STREAMING RUNTIME ARCHITECTURE                         |
+---------------------------------------------------------------------------------------+

 [ Apache Kafka ] (Upstream External Source)
        |
        | (TCP / Reactive Consumer)
        v
 +---------------+
 | Kafka Source  |  <--- org.apache.pekko.kafka.scaladsl.Consumer
 +---------------+
        |
        | [CommittableMessage[K, V]]
        v
 +---------------+
 |  Parse & Val  |  <--- Json Parser / Schema Validation Flow
 +---------------+
        |
     [Event]
        |
        +-----------------------+  (Graph DSL: Fan-Out / Broadcast)
        |                       |
        v                       v
 +--------------+       +---------------+
 | Fraud Engine |       | Audit History |
 +--------------+       +---------------+
        |                       |
   [EnrichedEvt]                |
        |                       |
        v                       |
 +--------------+               |
 | Risk Filter  |               |
 +--------------+               |
        |                       |
        +-----------------------+  (Graph DSL: Fan-In / Merge)
        |
        v
 +---------------+
 | Batch Committer|  <--- Batched commit offsets to avoid broker overload
 +---------------+
        |
        v
 +---------------+
 | External Sink |  <--- Target Database (RDBMS/Elasticsearch/HTTP Microservice)
 +---------------+
```

### Dynamic Demand Signal Sequence

Alur pengiriman sinyal spesifikasi Reactive Streams:

```
Upstream (Source/Publisher)        Downstream (Sink/Subscriber)
           |                                     |
           | <------- Subscribe(this) ---------- |
           |                                     |
           | -------- onSubscribe(Sub) --------> |
           |                                     |
           | <------- request(n=2) ------------- |  (Sink siap terima 2 elemen)
           |                                     |
           | -------- onNext(elem 1) ----------> |  (Source mengirim elemen 1)
           | -------- onNext(elem 2) ----------> |  (Source mengirim elemen 2)
           |                                     |
           | <------- request(n=1) ------------- |  (Sink meminta 1 elemen tambahan)
           | -------- onNext(elem 3) ----------> |
           |                                     |
           | -------- onComplete() ------------> |  (Aliran data selesai secara normal)
           v                                     v
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Spesifikasi Antarmuka Reactive Streams (`org.reactivestreams`)

Pondasi streaming reaktif bertumpu pada empat antarmuka inti:

```scala
trait Publisher[T]:
  def subscribe(s: Subscriber[? >: T]): Unit

trait Subscriber[T]:
  def onSubscribe(s: Subscription): Unit
  def onNext(t: T): Unit
  def onError(t: Throwable): Unit
  def onComplete(): Unit

trait Subscription:
  def request(n: Long): Unit
  def cancel(): Unit

trait Processor[T, R] extends Subscriber[T] with Publisher[R]
```

* **Aturan Strict Kontrak:**
  * Pemanggilan `request(n)` harus menggunakan argumen $n > 0$. Jika $n \le 0$, Publisher wajib menembakkan `java.lang.IllegalArgumentException` via sinyal `onError`.
  * Sinyal `onError` dan `onComplete` bersifat terminal. Setelah salah satu dipanggil, tidak ada pemanggilan `onNext` yang diizinkan.
  * Pemanggilan metode pada `Subscriber` harus berurutan secara thread-safe (*happens-before relationship*).

### 2. Abstraksi Inti Pekko Streams

Pekko Streams membungkus antarmuka `org.reactivestreams` ke dalam tipe data tingkat tinggi:

* **`Source[Out, Mat]`**: Titik masuk (*inlet* 0, *outlet* 1). Menghasilkan elemen bertipe `Out` dan nilai materialisasi bertipe `Mat`.
* **`Flow[In, Out, Mat]`**: Transformator data (*inlet* 1, *outlet* 1). Menerima `In` dan menghasilkan `Out`.
* **`Sink[In, Mat]`**: Titik akhir (*inlet* 1, *outlet* 0). Menerima data dan memicu konsumsi.
* **`RunnableGraph[Mat]`**: Sirkuit tertutup (*inlet* 0, *outlet* 0) yang siap dialokasikan dan dijalankan melalui materializer.

### 3. Fusing vs Asynchronous Boundaries

Secara default, Pekko Streams menggabungkan (*fuse*) seluruh tahapan (*stages*) ke dalam sebuah *Actor* tunggal demi performa cache CPU mikrodetik. Namun, jika ada tahapan pemrosesan yang lambat atau memblokir thread, tahap tersebut akan memblokir eksekusi tahap lain di dalam thread yang sama.

```
FUSED (Default Single Actor / Thread Context):
[ Source ] ---> [ Flow 1 (CPU Intesif) ] ---> [ Flow 2 (Ringan) ] ---> [ Sink ]

EXPLICIT ASYNC BOUNDARY (.async):
[ Source ] ---> [ Flow 1 ] --- (Thread Boundary / Buffer) ---> [ Flow 2 ] ---> [ Sink ]
                 (Actor 1)                                       (Actor 2)
```

Penyisipan operator `.async` memperkenalkan buffer antrian berbasis ring-buffer (default: 16 elemen) dan memecah siklus hidup stage ke thread terpisah, memungkinkan paralelisasi sejati lintas CPU core.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Matematika dan Mekanika Backpressure

Mekanisme backpressure reaktif menjamin stabilitas bounded memory. Misalkan kapasitas konsumsi sistem hilir didefinisikan sebagai $R_c$ (elemen/detik) dan kapasitas emisi sistem hulu adalah $R_p$ (elemen/detik).
* Dalam sistem streaming non-reaktif: Jika $R_p > R_c$, memori yang dikonsumsi $M(t)$ pada waktu $t$ bertambah sesuai fungsi:
  $$\Delta M(t) = \int_0^t (R_p - R_c) \, dt$$
  Hal ini niscaya berujung pada kehabisan heap memory ($M(t) \ge M_{max} \implies \text{OOM}$).
* Dalam Reactive Streams: Hulu dibatasi secara ketat oleh permintaan terakumulasi:
  $$\sum \text{Pushed} \le \sum \text{Requested}$$
  Jumlah elemen yang melayang di memori dibatasi oleh kapasitas window demand ($\Delta M \le \sum_{i} \text{Buffer}_{stage_i}$).

### 2. Siklus Hidup Materialisasi (*Materialization Lifecycle*)

Pekko Streams mendefinisikan pemisahan antara deskripsi logika graf dengan instansiasi graf runtime:
* **Mat Value Propagation:** Setiap stage dapat mengembalikan sebuah nilai saat materialisasi dijalankan (misalnya representasi kontrol stream, offset tracker, atau `Future[Done]`).
* Kombinator `Keep.left`, `Keep.right`, `Keep.both`, dan `Keep.none` digunakan untuk memilih nilai mana yang ingin dipertahankan saat dua stage dihubungkan:

```scala
val source: Source[Int, Promise[Option[Int]]] = Source.maybe[Int]
val sink: Sink[Int, Future[Int]] = Sink.head[Int]

// Mempertahankan nilai materialisasi dari Sink (Keep.right)
val graph: RunnableGraph[Future[Int]] = source.toMat(sink)(Keep.right)
```

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi pipeline pemrosesan data reaktif menggunakan Pekko Streams dengan konfigurasi isolasi konkurensi, transformasi data, dan backpressure handling eksplisit.

```scala
// build.sbt dependencies:
// libraryDependencies ++= Seq(
//   "org.apache.pekko" %% "pekko-stream" % "1.0.2",
//   "org.apache.pekko" %% "pekko-actor-typed" % "1.0.2"
// )

package com.enterprise.streaming.fundamental

import org.apache.pekko.actor.typed.ActorSystem
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import org.apache.pekko.stream.scaladsl.{Flow, Keep, RunnableGraph, Sink, Source}
import org.apache.pekko.stream.{Attributes, OverflowStrategy}
import org.apache.pekko.Done

import scala.concurrent.{ExecutionContext, Future}
import scala.util.{Failure, Success}

case class RawSensorMetric(deviceId: String, temperature: Double, timestamp: Long)
case class ValidatedMetric(deviceId: String, temperatureKelvin: Double, timestamp: Long)

object FundamentalStreamApp:

  def main(args: Array[String]): Unit =
    // 1. Inisialisasi Actor System & Materializer Context
    implicit val system: ActorSystem[Nothing] = ActorSystem(Behaviors.empty, "StreamFundamentalSystem")
    implicit val ec: ExecutionContext = system.executionContext

    println("=== Inisialisasi Engine Pekko Streams ===")

    // 2. Definisi Source (Unbounded atau Bounded Source)
    val sensorDataSource: Source[RawSensorMetric, ?] = Source(1 to 100)
      .map { index =>
        RawSensorMetric(
          deviceId = s"dev-${index % 5}",
          temperature = 20.0 + (index * 0.5),
          timestamp = System.currentTimeMillis() + index
        )
      }

    // 3. Definisi Flow Pemrosesan & Transformasi Data
    val validationFlow: Flow[RawSensorMetric, ValidatedMetric, ?] = Flow[RawSensorMetric]
      .filter(_.temperature >= -40.0) // Buang noise sensor rusak
      .filter(_.temperature <= 85.0)
      .map { raw =>
        val kelvin = raw.temperature + 273.15
        ValidatedMetric(raw.deviceId, kelvin, raw.timestamp)
      }
      .buffer(size = 8, overflowStrategy = OverflowStrategy.backpressure)

    // 4. Definisi Sink Konsumsi
    val printSink: Sink[ValidatedMetric, Future[Done]] = Sink.foreach[ValidatedMetric] { metric =>
      println(s"[OUTPUT SINK] Thread: ${Thread.currentThread().getName} | Event: $metric")
    }

    // 5. Perakitan Blueprint & Materialisasi
    val pipeline: RunnableGraph[Future[Done]] = sensorDataSource
      .via(validationFlow)
      .async // Memisahkan pipeline pemrosesan ke batas worker thread terisolasi
      .toMat(printSink)(Keep.right)

    // 6. Eksekusi Graph
    val streamCompletion: Future[Done] = pipeline.run()

    // 7. Penanganan Lifecycle Penyelesaian Stream
    streamCompletion.onComplete {
      case Success(Done) =>
        println("=== Stream Berhasil Diselesaikan Tanpa Hambatan ===")
        system.terminate()
      case Failure(exception) =>
        System.err.println(s"CRITICAL: Stream Mengalami Kegagalan Fatal: ${exception.getMessage}")
        system.terminate()
    }
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 20–21:** 
  ```scala
  implicit val system: ActorSystem[Nothing] = ActorSystem(Behaviors.empty, "StreamFundamentalSystem")
  implicit val ec: ExecutionContext = system.executionContext
  ```
  Menyediakan runtime akka/pekko. Di Pekko v1.0+, `ActorSystem` secara implisit bertindak sebagai `Materializer`, menyediakan alokator thread pool, context switching, dan timer scheduler.
* **Baris 26–33:**
  ```scala
  val sensorDataSource: Source[RawSensorMetric, ?] = Source(1 to 100).map(...)
  ```
  Membuat stage `Source` bertipe elemen `RawSensorMetric` dengan auxiliary materialized value yang diabaikan (`?`). Operasi belum menghasilkan elemen hingga stream dimaterialisasi.
* **Baris 36–43:**
  ```scala
  val validationFlow: Flow[RawSensorMetric, ValidatedMetric, ?] = Flow[RawSensorMetric]
    .filter(...).map(...)
    .buffer(size = 8, overflowStrategy = OverflowStrategy.backpressure)
  ```
  Mendefinisikan blueprint komputasi terisolasi. Penambahan `.buffer(..., OverflowStrategy.backpressure)` mengalokasikan circular buffer berukuran 8 slot. Ketika buffer terisi penuh, sinyal `request(n)` ke hulu dihentikan secara otomatis hingga downstream mengosongkan antrian.
* **Baris 46–48:**
  ```scala
  val printSink: Sink[ValidatedMetric, Future[Done]] = Sink.foreach[...]
  ```
  Mendeklarasikan stage terminal. Nilai materialisasinya berupa `Future[Done]`, yang akan selesai (*fulfilled*) saat source kehabisan data dan seluruh downstream stage sukses memproses elemen terakhir.
* **Baris 51–54:**
  ```scala
  val pipeline: RunnableGraph[Future[Done]] = sensorDataSource
    .via(validationFlow)
    .async
    .toMat(printSink)(Keep.right)
  ```
  Menggabungkan komponen secara fungsional. Operator `.async` memperkenalkan boundary asynchronous sehingga `validationFlow` dieksekusi pada actor/thread yang berbeda dari `printSink`. `Keep.right` memastikan bahwa nilai materialisasi yang dipegang oleh `RunnableGraph` adalah milik `printSink` (`Future[Done]`), bukan nilai milik `Source`.
* **Baris 57:**
  ```scala
  val streamCompletion: Future[Done] = pipeline.run()
  ```
  Pemicu materialisasi stream sesungguhnya. Membangkitkan aktor streaming di underlying thread pool dan memulai transfer backpressure demand.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Pipeline Deteksi Anomali Transaksi Finansial

Sebuah lembaga perbankan digital memproses jutaan transaksi pembayaran real-time dari Kafka. Sistem harus memenuhi kriteria non-fungsional berikut:

1. **Volume & Kecepatan:** 50.000 transaksi/detik dengan lonjakan mendadak (*bursts*).
2. **Kebutuhan Isolasi:** Transaksi harus divalidasi ke basis data aturan (*Fraud Rule Engine*) berbasis evaluasi async. Jika lookup lambat, sistem **dilarang keras** memicu OOM (wajib backpressure ke Kafka partition).
3. **Audit Immutability & Branching:** Setiap transaksi valid harus dialirkan secara bercabang (*fan-out*):
   * Jalur 1: Evaluasi skor anomali. Jika skor $> 0.8$, teruskan ke *Alerting Sink*.
   * Jalur 2: Agregasi batch per 100 elemen atau per 500ms untuk bulk audit logging ke storage.
4. **Resiliensi:** Transaksi korup tidak boleh mematikan sistem (*zero downtime tolerance*), melainkan dikarantina ke Dead-Letter-Queue (DLQ).

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut adalah implementasi enterprise Pekko Streams menggunakan Graph DSL untuk skenario transaksi di atas.

```scala
// File: src/main/scala/com/enterprise/streaming/fraud/FraudDetectionPipeline.scala
package com.enterprise.streaming.fraud

import org.apache.pekko.actor.typed.ActorSystem
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import org.apache.pekko.stream.*
import org.apache.pekko.stream.scaladsl.*
import org.apache.pekko.Done

import scala.concurrent.{ExecutionContext, Future}
import scala.concurrent.duration.*
import scala.util.control.NonFatal

// Domain Models
case class PaymentTransaction(
    txnId: String,
    accountId: String,
    amount: BigDecimal,
    currency: String,
    timestamp: Long
)

case class FraudAlert(
    txnId: String,
    accountId: String,
    riskScore: Double,
    reason: String
)

case class AuditBatch(records: Seq[PaymentTransaction])

object FraudDetectionPipeline:

  def main(args: Array[String]): Unit =
    implicit val system: ActorSystem[Nothing] = ActorSystem(Behaviors.empty, "FraudPipelineSystem")
    implicit val ec: ExecutionContext = system.executionContext

    // 1. Decider Strategi Penanganan Error (Resilience Strategy)
    val customDecider: Supervision.Decider = {
      case _: IllegalArgumentException =>
        // Data format cacat, lewati record dan lanjutkan stream
        Supervision.Resume
      case NonFatal(e) =>
        System.err.println(s"[SUPERVISOR] Terjadi kegagalan non-fatal: ${e.getMessage}. Melakukan resume stream.")
        Supervision.Resume
      case fatal =>
        System.err.println(s"[SUPERVISOR FATAL] Mematikan stream akibat error kritis: ${fatal.getMessage}")
        Supervision.Stop
    }

    val actorMaterializerSettings = ActorAttributes.supervisionStrategy(customDecider)

    // 2. Mock Source Transaksi Finansial
    val transactionSource: Source[PaymentTransaction, ?] = Source(1 to 1000).map { i =>
      if i == 13 then
        // Injeksi anomali/poison pill data untuk membuktikan error tolerance
        throw new IllegalArgumentException(s"Payload Corrupted pada transaksi #$i")
      PaymentTransaction(
        txnId = s"TXN-$i",
        accountId = s"ACC-${i % 20}",
        amount = BigDecimal(10 * i),
        currency = "USD",
        timestamp = System.currentTimeMillis()
      )
    }

    // 3. Async Flow: Simulasi Lookup Machine Learning Model Asinkron
    def evaluateRiskAsync(txn: PaymentTransaction): Future[(PaymentTransaction, Double)] =
      Future {
        // Simulasi latensi komputasi I/O
        val calculatedScore = if txn.amount > BigDecimal(5000) then 0.95 else 0.15
        (txn, calculatedScore)
      }

    // 4. Sink Khusus
    val alertSink: Sink[FraudAlert, Future[Done]] = Sink.foreach[FraudAlert] { alert =>
      System.err.println(s"⚠️  [SECURITY ALERT] Rekening: ${alert.accountId} | Skor: ${alert.riskScore} | ID: ${alert.txnId}")
    }

    val auditLogSink: Sink[AuditBatch, Future[Done]] = Sink.foreach[AuditBatch] { batch =>
      println(s"📦 [AUDIT STORAGE] Berhasil menyimpan batch sebesar ${batch.records.size} transaksi.")
    }

    // 5. Graph DSL: Konstruksi Topologi Non-Linear Kompleks
    val complexTopologyGraph = GraphDSL.createGraph(alertSink, auditLogSink)(Keep.both) { implicit builder =>
      (alertOut, auditOut) =>
        import GraphDSL.Implicits.*

        // Inlets & Outlets komponen graf
        val broadcast = builder.add(Broadcast[PaymentTransaction](2))

        // Alur Cabang 1: Evaluasi Fraud
        val riskScoreFlow = Flow[PaymentTransaction]
          .mapAsync(parallelism = 4)(evaluateRiskAsync)
          .collect {
            case (txn, score) if score > 0.80 =>
              FraudAlert(txn.txnId, txn.accountId, score, "High transaction value threshold exceeded")
          }

        // Alur Cabang 2: Agregasi Batch
        val batchingFlow = Flow[PaymentTransaction]
          .groupedWithin(n = 50, d = 250.millis)
          .map(AuditBatch.apply)

        // Koneksi Jalur Aliran Topologi
        // Uplink
        val sourceStage = builder.add(transactionSource)
        
        sourceStage ~> broadcast.in

        // Cabang 1 -> Alert Sink
        broadcast.out(0) ~> riskScoreFlow.async ~> alertOut

        // Cabang 2 -> Audit Log Sink
        broadcast.out(1) ~> batchingFlow.async  ~> auditOut

        ClosedShape
    }

    // 6. Eksekusi Topologi dengan Konfigurasi Decider
    val (alertCompletion, auditCompletion) = RunnableGraph
      .fromGraph(complexTopologyGraph)
      .withAttributes(actorMaterializerSettings)
      .run()

    // 7. Monitor Penyelesaian Stream
    val allCompleted = for
      _ <- alertCompletion
      _ <- auditCompletion
    yield Done

    allCompleted.onComplete { result =>
      println(s"=== Eksekusi Seluruh Pipeline Berakhir: $result ===")
      system.terminate()
    }
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Di ekosistem Scala modern, terdapat dua paradigma utama untuk Data Streaming: **Pekko/Akka Streams** (Berbasis Actor & Reactive Streams Standard) vs **FS2** (Functional Streams for Scala, berbasis Pure Functional IO monad).

| Aspek / Karakteristik | Pekko Streams | FS2 (Cats Effect) | Monix / Project Reactor |
| :--- | :--- | :--- | :--- |
| **Model Fondasi** | Akka/Pekko Actor Model, JVM Thread Scheduler. | Pure FP, Fiber Concurrency (`cats.effect.IO`). | Reactive Streams Spec, Thread Pools / Workers. |
| **Pola Eksekusi Stream** | Graph DSL statis, compile-time topology wiring. | Pull-based lazy streams (mirip list tak terbatas). | Operator chaining mirip Rx / reactive-streams. |
| **Penanganan State** | State diisolasi dalam Aktor / Custom `GraphStageLogic`. | State threading via `Ref`, `Deferred`, `StateT`. | Operator-managed atomics / stateful combinators. |
| **Kinerja / Latensi** | Ekstrem pada throughput tinggi berkat internal fusing. | Efisiensi alokasi memori sangat tinggi via CE3 Fibers. | Unggul dalam *low memory footprint*. |
| **Kurva Pembelajaran** | Moderat (familiar bagi pengguna enterprise/Akka). | Sangat Curam (wajib paham Typelevel stack, Monad, Kleisli). | Rendah hingga moderat (konvensi mirip ReactiveX). |
| **Integrasi Ekosistem** | Kompatibilitas tinggi dengan Alpakka (Kafka, S3, SQS, gRPC). | Kaya integrasi ekosistem Typelevel (Http4s, Skunk, Doobie). | Dominan di Java/Spring, minim integrasi Scala 3 native. |

### Kapan Menggunakan Pekko Streams?
* Proyek enterprise dengan arsitektur Actor yang sudah ada (`pekko-actor-typed`).
* Kebutuhan konektor bawaan tingkat enterprise ke puluhan sistem eksternal (*Alpakka/Pekko Connectors*).
* Topologi streaming kompleks bertipe graf non-siklik (DAG) yang memerlukan isolasi lifecycle visual via Graph DSL.

---

## SEKSI 12 — EDGE CASES & PITFALLS

1. **Deadlock Akibat Kesalahan Desain Topologi Graph (Unbalanced Fan-Out):**
   * *Problem:* Jika stage `Broadcast` menyuplai dua sub-jalur, di mana Jalur A berhenti meminta elemen (misalnya downstream macet atau mengalami internal delay) sementara Jalur B terus meminta data secara cepat.
   * *Mekanisme:* Operator `Broadcast` secara bawaan menerapkan backpressure terendah: ia **tidak akan mengirimkan elemen berikutnya ke siapapun** sampai **seluruh** cabang hilir meminta data baru (`request`). Hal ini menyebabkan Jalur B mengalami *starvation* (kelaparan demand).
   * *Mitigasi:* Tambahkan buffer berkapasitas terukur sebelum consumer yang lambat atau ganti `Broadcast` dengan mekanisme dynamic dropped-buffer (`buffer(n, OverflowStrategy.dropHead)`).

2. **Hilangnya Backpressure Akibat Blocking Calls di Dalam Stage Map:**
   * *Problem:* Memanggil `Thread.sleep()` atau synchronous HTTP/JDBC client di dalam operator `.map(...)`.
   * *Mekanisme:* Tindakan ini membajak thread internal milik actor dispatcher materializer. Seluruh stage lain yang di-fuse pada dispatcher yang sama akan membeku.
   * *Mitigasi:* Selalu bungkus operasi pemblokir ke dalam `scala.concurrent.Future` dan gunakan `.mapAsync(parallelism)` dengan mendedikasikan custom `ExecutionContext` terpisah (*Bulkhead Pattern*).

3. **Silent Stream Termination (Gagal Mematerialisasikan Future Error):**
   * Jika Anda tidak memantau materialized value hilir (misalnya `Keep.none` atau tidak menambahkan hook `onComplete` pada materialized `Future[Done]`), stream yang mati mendadak karena `OutOfMemoryError` atau exception tak tertangani tidak akan memunculkan log error apapun.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Pola Anti-Pattern: Blocking I/O di Thread Pool Streaming

```scala
// SALAH: Mematikan seluruh thread pool materializer
Flow[String].map { url =>
  val response = scala.io.Source.fromURL(url).mkString // BLOCKING I/O!
  response
}

// BENAR: Mengisolasi eksekusi blocking ke thread pool dedicated
val blockingDispatcher = system.dispatchers.lookup(DispatcherSelector.blocking())

Flow[String].mapAsync(parallelism = 8) { url =>
  Future {
    scala.io.Source.fromURL(url).mkString
  }(blockingDispatcher)
}
```

### 2. Pola Anti-Pattern: Buffer Liar Tanpa Strategi Overflow Terukur

```scala
// SALAH: Menggunakan buffer tanpa batas yang membunuh JVM saat traffic spike
Flow[Int].buffer(1000000, OverflowStrategy.fail)

// BENAR: Menentukan batas wajar dengan strategi backpressure atau DLQ drop
Flow[Int].buffer(size = 256, overflowStrategy = OverflowStrategy.backpressure)
```

### 3. Mengabaikan Unhandled Stream Failures

```scala
// SALAH: Menjalankan graph tanpa mengikat output completion
val graph = source.via(flow).to(sink)
graph.run() // Tidak ada cara mengetahui jika stream crash di tengah jalan!

// BENAR: Selalu bind materialized value dan berikan failure handler
val completion: Future[Done] = source.via(flow).toMat(sink)(Keep.right).run()
completion.onComplete {
  case Success(_) => logger.info("Pipeline stopped cleanly.")
  case Failure(ex) => logger.error("Pipeline crashed catastrophically", ex)
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Explicit Stream Boundaries:** Berikan penamaan dispatcher eksplisit dan gunakan `.async` secara selektif hanya di antara tahapan yang memiliki karakteristik CPU-Bound vs I/O-Bound.
2. **Batch Committing pada Message Broker:** Jangan pernah melakukan ack/commit offset per record pada Kafka Source. Gunakan `Committer.flow` atau `groupedWithin(size, time)` untuk mengagregasi ribuan offset commit ke dalam satu transaksi Kafka guna menekan round-trip network.
3. **Idempotency di Sisi Downstream:** Dalam arsitektur streaming reaktif terdistribusi (*at-least-once delivery*), pengiriman duplikat dapat terjadi saat terjadi rebalance. Pastikan data store tujuan (*Sink*) mengimplementasikan mekanisme *upsert* atau deduplikasi berbasis transaction/event ID.
4. **Clean Shutdown Hook:** Selalu pasang *JVM Shutdown Hook* yang memicu sinyal `drainAndShutdown()` pada source eksternal (Kafka/AMQP) agar stream memiliki waktu untuk menyelesaikan in-flight data (*graceful termination*).

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Graph Stage Fusing Control

Secara internal, Pekko Streams mengintegrasikan operator yang berdekatan. Fusing meniadakan alokasi antrian perantara antartahap.
* Lakukan `.async` hanya jika stage sebelum dan sesudahnya memiliki perbedaan latensi kerja lebih dari 5x lipat.
* Hindari menyisipkan `.async` di antara transformasi sederhana berurutan seperti `.map(...).filter(...).map(...)`, karena hal ini meningkatkan overhead *inter-actor message passing*.

### 2. Penyetelan Parameter Concurrency (`mapAsync` vs `mapAsyncUnordered`)

* Jika urutan (*ordering*) elemen tidak mutlak dibutuhkan oleh downstream, prioritaskan penggunaan `mapAsyncUnordered(parallelism)`.
* `mapAsync` wajib mempertahankan urutan. Jika item pertama memerlukan waktu 500ms untuk selesai dan item kedua selesai dalam 10ms, item kedua **terpaksa ditahan di buffer** hingga item pertama selesai, menyebabkan latensi semu (*head-of-line blocking*).

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Backpressure sebagai Pertahanan Denial of Service (DoS):**
   * Reactive stream yang terpasang langsung pada endpoint HTTP (misalnya Pekko HTTP streaming) berfungsi sebagai anti-DoS alami. Saat consumer downstream tidak mampu memproses request body yang sangat besar, transfer rate TCP ditarik ulur menggunakan TCP Zero-Window via backpressure protocol.
2. **Karantina Elemen Beracun (Dead Letter Queue):**
   * Jangan biarkan kesalahan parsing deserialisasi JSON menghentikan aliran utama. Tangkap exception pada boundary deserializer dan arahkan objek bermasalah ke topik DLQ dengan metadata error lengkap.
3. **Redaksi Data Sensitif (PII Scrubbing):**
   * Sebelum data dialirkan ke stage persistensi atau logging audit, pastikan stage transformasi menyamarkan field PII (*credit card number*, *passwords*, *tokens*).

```scala
val piiSanitizationFlow: Flow[PaymentTransaction, PaymentTransaction, ?] =
  Flow[PaymentTransaction].map { txn =>
    val maskedAccount = txn.accountId.replaceAll("(?<=.{4}).(?=.{2})", "*")
    txn.copy(accountId = maskedAccount)
  }
```

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Pekko Streams menyediakan fasilitas introspeksi pipeline bawaan yang aman bagi throughput tinggi tanpa merusak integritas backpressure:

```scala
import org.apache.pekko.stream.Attributes

val observedPipeline = source
  .log("debug-source-step")
  .addAttributes(
    Attributes.createLogLevels(
      onElement = Attributes.LogLevels.Debug,
      onFinish = Attributes.LogLevels.Info,
      onFailure = Attributes.LogLevels.Error
    )
  )
  .via(validationFlow)
  .wireTap(metric => MetricsCollector.increment("processed.records", 1)) // Non-intrusive observation
  .to(sink)
```

* **`wireTap` Stage:** Mengizinkan observasi elemen yang melintas secara pasif. `wireTap` tidak dapat mengubah elemen data dan tidak dapat memblokir aliran utama downstream jika target observasi lambat (*fire-and-forget tapping*).
* **Metrics Ingestion:** Lacak metrik streaming standar via Prometheus/Micrometer:
  * *Elements In / Elements Out* per detik.
  * *Buffer Utilization* (persentase keterisian buffer internal).
  * *Processing Latency* per batch.

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

* **Komponen Inti:**
  * `Source[+Out, +Mat]`: 0 In, 1 Out.
  * `Flow[-In, +Out, +Mat]`: 1 In, 1 Out.
  * `Sink[-In, +Mat]`: 1 In, 0 Out.
  * `RunnableGraph[+Mat]`: Closed graph, siap di-run.
* **Kombinator Materialisasi Utama:**
  * `Keep.left`: Mempertahankan hasil materialisasi stage sebelah kiri.
  * `Keep.right`: Mempertahankan hasil materialisasi stage sebelah kanan.
  * `Keep.both`: Menghasilkan pasangan tuple `(MatLeft, MatRight)`.
* **Strategi Backpressure Buffer:**
  * `OverflowStrategy.backpressure`: Memberikan sinyal ke hulu untuk berhenti mengirim data.
  * `OverflowStrategy.dropHead`: Membuang elemen terlama di buffer untuk menerima elemen baru.
  * `OverflowStrategy.dropTail`: Membuang elemen terbaru di buffer.
  * `OverflowStrategy.fail`: Menghentikan stream dengan error `BufferOverflowException`.
* **Supervision Directives:**
  * `Supervision.Resume`: Mengabaikan elemen yang menyebabkan exception dan melanjutkan ke elemen berikutnya.
  * `Supervision.Restart`: Menghidupkan ulang internal stage state dan melanjutkan stream.
  * `Supervision.Stop`: Menghentikan seluruh stream seketika.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### A. Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara model *Push*, *Pull*, dan *Dynamic Push-Pull* dalam pemrosesan data?**
   * *Jawaban:* Model *Push* mendorong data tanpa mempedulikan kesiapan hilir (risiko OOM). Model *Pull* meminta data satu per satu secara kontinu (dapat memicu *busy-wait* dan inefisiensi latensi). *Dynamic Push-Pull* memungkinkan consumer meminta kapasitas batch tertentu ($N$ demand), dan producer hanya boleh mendorong maksimal $N$ elemen sampai demand baru diterbitkan.

2. **Apa yang dimaksud dengan "Materialization" dalam Pekko Streams?**
   * *Jawaban:* Proses runtime di mana blueprint logis streaming dialokasikan ke resource fisik (Aktor, alokasi memori buffer, thread pool) untuk mulai mengeksekusi aliran data.

3. **Manakah kombinator yang digunakan jika Anda ingin mengambil nilai materialisasi dari sebuah `Sink` yang digabungkan dari sebuah `Source`?**
   * *Jawaban:* `Keep.right`.

4. **Sebutkan empat antarmuka utama yang membentuk spesifikasi JVM Reactive Streams!**
   * *Jawaban:* `Publisher[T]`, `Subscriber[T]`, `Subscription`, dan `Processor[T, R]`.

5. **Apa fungsi utama dari operator `.async` dalam sebuah flow?**
   * *Jawaban:* Memisahkan tahapan pemrosesan sebelum dan sesudahnya ke dalam aktor/thread boundaries yang berbeda, mencegah eksekusi sekuensial pada satu thread tunggal (*fused execution*).

---

### B. Tingkat Menengah (Intermediate)

6. **Apa bahaya dari penggunaan `mapAsync` jika salah satu `Future` tidak pernah menyelesaikan operasinya (*hang*)?**
   * *Jawaban:* Stream akan mengalami kondisi *deadlock* total. Karena `mapAsync` menjaga urutan (*ordering*), elemen-elemen selanjutnya yang sudah selesai dieksekusi akan tertahan di buffer internal menunggu elemen pertama selesai, menghentikan seluruh demand backpressure ke hulu.

7. **Kapan Anda harus memilih `Supervision.Resume` daripada `Supervision.Restart`?**
   * *Jawaban:* Gunakan `Supervision.Resume` jika stage tidak memiliki akumulasi internal state yang korup dan kegagalan hanya bersifat lokal pada satu data buruk (*isolated poison pill*). Gunakan `Supervision.Restart` jika stage memiliki internal state (misal accumulator, session) yang harus di-reset kembali ke nilai awal setelah terjadi error.

8. **Mengapa topologi Graph DSL `Broadcast` rentan memicu bottleneck jika salah satu cabang hilirnya lambat?**
   * *Jawaban:* Karena `Broadcast` menunggu sinyal demand dari seluruh cabang keluaran sebelum menarik elemen baru dari upstream. Cabang yang paling lambat akan mendikte kecepatan pemrosesan seluruh cabang lainnya.

9. **Apa perbedaan perilaku antara `OverflowStrategy.dropHead` dan `OverflowStrategy.dropTail`?**
   * *Jawaban:* `dropHead` membuang elemen tertua di dalam buffer untuk menampung data baru (bagus untuk data telemetri real-time di mana data terkini lebih berharga). `dropTail` mempertahankan data lama dan membuang elemen terbaru yang hendak masuk ke buffer.

10. **Bagaimana backpressure mencegah kebocoran memori (OOM) pada interaksi antara database lambat dan broker pesan cepat?**
    * *Jawaban:* Database sink yang lambat membatasi pengiriman sinyal `request(n)` ke stream. Karena sinyal demand tidak diterbitkan, Kafka consumer source tidak membaca pesan baru dari broker TCP socket buffer, menahan akumulasi data di sisi broker disk cluster, bukan di heap memory aplikasi JVM.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Arsitektur Tantangan: Resilient E-Commerce Event Ingestion Pipeline

Rancang dan bangun sebuah aplikasi executable Scala 3 lengkap berbasis Pekko Streams yang mensimulasikan sistem pemrosesan pesanan (*order processing*) dengan skema berikut:

#### Spesifikasi Domain:
```scala
case class OrderEvent(
  orderId: String, 
  customerId: String, 
  totalAmount: BigDecimal, 
  itemCount: Int, 
  createdAt: Long
)

case class ProcessedInvoice(
  invoiceId: String, 
  orderId: String, 
  taxAmount: BigDecimal, 
  netTotal: BigDecimal
)
```

#### Persyaratan Teknis yang Wajib Dipenuhi:
1. **Source Generation:**
   * Bangun sebuah `Source` yang menembakkan 10.000 `OrderEvent` dengan selang emisi bervariasi secara acak (gunakan timer atau pemetaan range).
   * Sisipkan secara sengaja 1% data korup bertipe `totalAmount <= 0`.
2. **Resilience & Supervision:**
   * Implementasikan `Supervision.Decider` custom: Jika data korup (`totalAmount <= 0`), cetak error log dan lewati elemen via `Resume`. Jika terjadi error tak terduga lainnya, catat exception dan restart stage.
3. **Graph Topologi (GraphDSL):**
   * Terapkan percabangan (*Fan-out* 1 ke 2):
     * **Cabang A (Billing):** Hitung pajak sebesar 11% via `mapAsync(parallelism = 4)`, bungkus menjadi `ProcessedInvoice`, lalu simpan ke sebuah In-Memory Concurrent Storage via `Sink.fold` atau `Sink.foreach`.
     * **Cabang B (VIP Reward Service):** Filter pesanan yang memiliki `totalAmount > 1000`. Agregasikan pesanan VIP tersebut setiap 10 transaksi atau interval 500ms (gunakan `groupedWithin`), lalu cetak alert VIP customer.
4. **Shutdown & Metrik:**
   * Alirkan seluruh pipeline hingga selesai secara utuh. Cetak total durasi waktu eksekusi pipeline dan jumlah total invoice yang berhasil diproses secara presisi tanpa ada elemen data valid yang hilang.

Jalankan pengujian menggunakan `sbt run` dan pastikan JVM keluar (*system exit*) secara elegan dengan status kode `0`.