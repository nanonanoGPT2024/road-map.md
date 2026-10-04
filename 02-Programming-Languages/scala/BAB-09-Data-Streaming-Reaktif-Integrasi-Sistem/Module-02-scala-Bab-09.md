# BAB 09: Data Streaming Reaktif & Integrasi Sistem
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur internal spesifikasi *Reactive Streams* dan mekanisme *demand-driven backpressure* pada tingkat protokol transport dan memori runtime JVM.
- **Mengimplementasikan** operator kustom tingkat lanjut (*Custom GraphStage* pada Apache Pekko/Akka Streams dan *Custom Pull Logic* pada FS2) dengan manajemen state internal yang *thread-safe*.
- **Merancang** topologi *stream* terdistribusi yang resilient dengan integrasi Apache Kafka, menerapkan semantik *At-Least-Once* dan *Effectively-Once Processing* via teknik *idempotent sinks*.
- **Mendiagnosis** dan **memitigasi** degradasi performa pada runtime Scala streaming, seperti *thread starvation*, kebocoran *buffer heap*, *backpressure deadlock*, dan GC pauses.
- **Menetapkan** arsitektur *observability* berbasis OpenTelemetry dan Metrik Dropwizard/Micrometer untuk melacak latensi ujung-ke-ujung (*end-to-end latency*) dan saturasi *stage buffer*.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Scala 3 / 2.13 Core**: Pemahaman mendalam tentang *Type System*, *Implicits/Givens*, *Higher-Kinded Types*, dan *Variance*.
- **Bab 09 - Modul 01**: Konsep dasar *Source*, *Flow*, *Sink*, atau *fs2.Stream*, serta pemahaman primitif *Functor/Monad*.
- **Konkurensi & Asinkron**: Model konkurensi berbasis `Future`/`ExecutionContext` dan *Fiber-based Concurrency* (Cats Effect `IO`).
- **Apache Kafka Fundamentals**: Konsep *Partitions*, *Consumer Groups*, *Offsets*, dan *Rebalance Protocols*.

---

### 3. Concept & Internal Architecture

#### 3.1 Spesifikasi Reactive Streams & Protokol Permintaan (Demand-Driven Protocol)
Spesifikasi *Reactive Streams* (diadopsi ke dalam JDK 9 via `java.util.concurrent.Flow`) dirancang untuk memecahkan masalah asimetri kecepatan antara produsen data (*Publisher*) dan konsumen (*Subscriber*). Model *push-only* konvensional menyebabkan risiko *OutOfMemoryError* (OOM) ketika konsumen mengalami degradasi performa, sementara model *pull-only* murni (seperti *iterator*) menimbulkan inefisiensi *blocking I/O*.

Protokol *Reactive Streams* adalah arsitektur hybrid: **Push-based data transfer yang dikendalikan oleh Pull-based demand signaling**.

```
    Subscriber                             Publisher
        |                                      |
        |----------- 1. subscribe() ---------->|
        |<---------- 2. onSubscribe(sub) ------|
        |                                      |
        |----------- 3. request(n) ----------->|  -- Kontrak Backpressure
        |                                      |  (Kapasitas Buffer Hilir)
        |<---------- 4. onNext(data_1) --------|
        |<---------- 5. onNext(data_n) --------|
        |                                      |
        |----------- 6. request(m) ----------->|
        |<---------- 7. onComplete() / --------|
                        onError(throwable)
```

**Kontrak Formal**:
1. Elemen data ditransfer melalui pemanggilan `onNext` secara asinkron dari Publisher ke Subscriber.
2. Publisher **hanya boleh** memanggil `onNext` sebanyak total kumulatif $N$ yang diminta oleh Subscriber melalui `Subscription.request(n)` di mana $n \ge 1$.
3. Jika demand $N = 0$, Publisher wajib menghentikan transfer data, memicu penahanan (*backpressure*) ke arah upstream.

#### 3.2 Eksekusi Model Pekko/Akka Streams: GraphInterpreter & Fusing
Di balik DSL deklaratif Pekko/Akka Streams, graf diproses melalui mekanisme **Graph Fusing**:
- Secara default, beberapa *Stage* linier di-*fuse* ke dalam satu aktor eksekutor tunggal (`GraphInterpreterShell`).
- Tujuannya adalah mengeliminasi overhead *actor message passing* (alokasi memori amplop pesan, context-switching antar-thread) dan menggantinya dengan pemanggilan method langsung (*direct method invocation*) pada thread yang sama.
- Ketika isolasi konkurensi diperlukan (misalnya I/O bound vs CPU bound), boundary asinkron eksplisit (`.async`) memecah graf menjadi beberapa aktor independen yang berkomunikasi melalui *ring buffer* berbasis LMAX Disruptor / bounded queue.

#### 3.3 Eksekusi Model FS2: Pull vs Stream Algebra
Berbeda dari Pekko Streams yang berbasis state machine berbasis Actor, **FS2 (Functional Streams for Scala)** memodelkan stream secara murni fungsional berbasis *Cofree Comonad* dan aljabar `Pull`:
- `fs2.Stream[F, O]` adalah abstraksi tingkat tinggi di atas primitif `fs2.Pull[F, O, R]`.
- `Pull` merepresentasikan komputasi bertahap (*step-wise computation*) yang dapat menarik (*pull*) chunk data dari upstream, memancarkan (*output*) data ke downstream, mengeksekusi efek samping `F`, atau mengembalikan hasil akhir `R`.
- State internal dikelola melalui rekursi murni berbasis tail-call elimination pada JVM yang berjalan di atas Cats Effect *Fiber Runloop*, menghasilkan footprint memori mendekati nol alokasi aktor.

---

### 4. Why & What

| Dimensi | Pendekatan Streaming Naif (Unbounded Futures / List) | Arsitektur Reactive Streaming Enterprise |
| :--- | :--- | :--- |
| **Kontrol Memori** | Unbounded buffering; OOM terjadi jika konsumen melambat. | Bounded memory footprint via propagation demand (`request(n)`). |
| **Resiliensi Kegagalan** | Unhandled exception menghentikan seluruh thread atau aplikasi. | *Supervision Strategies* (Resume, Restart, Stop) dan isolated boundary. |
| **Resource Safety** | Rawan file descriptor leak / unclosed connections saat crash. | Alokasi deterministik via primitives seperti `bracket` / `Resource`. |
| **Throughput & Latency** | Latensi tidak stabil akibat lock contention dan GC spikes. | *Chunking*, batched allocation, dan minimal context-switching overhead. |

---

### 5. How (Workflow Detail)

Alur kerja arsitektur pemrosesan data reaktif enterprise mengimplementasikan loop kendali umpan balik terbalik (*reverse feedback control loop*):

1. **Inisialisasi Graf & Alokasi Resource**: Materializer memvalidasi topologi graf siklik/asiklik, mengalokasikan buffer batas (*bounded circular buffers*), dan mengikat koneksi socket/transporter.
2. **Dynamic Backpressure Signaling**: Sink downstream mengalkulasi kapasitas buffer bebasnya ($B_{free}$) dan memicu sinyal `request(n)` di mana $n \le B_{free}$.
3. **Upstream Ingestion & Chunking**: Source membaca dari subsistem penyimpanan (misal: Apache Kafka) menggunakan batas fetch maksimum yang proporsional terhadap demand hilir. Data dikemas dalam struktur array flat (*Chunk*) untuk meminimalkan *boxing/unboxing*.
4. **Transformasi & Routing Paralel**: Flow mendistribusikan data melalui worker pool berbasis partition hash, memproses transformasi murni secara non-blocking.
5. **Circuit Breaking & Fault Mitigation**: Jika target downstream (Database/API eksternal) mengalami timeout, *Circuit Breaker* mendeteksi ambang kegagalan (*failure threshold*), memutus aliran, dan mengalihkan data ke antrean *Dead Letter Queue* (DLQ) tanpa mengorbankan integritas data utama.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem Pipa Industri
Bayangkan pabrik pengolahan cairan kimia:
- **Source**: Bendungan air bertekanan tinggi (Kafka Broker).
- **Flow**: Pipa dengan katup servo otomatis (Reactive Operators).
- **Sink**: Tangki pencampuran akhir berkapasitas terbatas (Database/Consumer).
- Jika tangki pencampuran penuh, katup pelampung mekanis menolak cairan baru. Tekanan balik hidrolik (*backpressure*) mengalir mundur melalui pipa secara instan hingga katup bendungan utama menutup secara proporsional. Tidak ada air yang tumpah ke lantai pabrik (*No OOM*).

#### Diagram Arsitektur Internal: Pekko Custom GraphStage vs FS2 Pull Engine

```
================================================================================
                    PEKKO STREAMS: GRAPHSTAGE INTERNALS
================================================================================
           +---------------------------------------------------+
           |                 GraphInterpreter                  |
           |                                                   |
Upstream   |    [InHandler]                    [OutHandler]    |   Downstream
  Port  ======> onPush() {                       onPull() {   ======> Port
 (Inlet)   |      val elem = grab(in)              pull(in)    |   (Outlet)
           |      // State manipulation          }             |
           |      push(out, elem)                              |
           |    }                                              |
           +---------------------------------------------------+
                                    |
                            [Shared Array/RingBuffer]
                                    |
================================================================================
                       FS2: PULL / CHUNK RUNLOOP
================================================================================
  Stream[F, O]
       |
  (Decompose)
       v
  Pull[F, O, R]  ==Step==>  Pull.Output(Chunk[O]) ---> Emitted Downstream
       ^                            |
       |                            v
  (Recurse)       <==FlatMap==  Pull.Eval(F[Action])
```

---

### 7. Implementation: Simple vs Practical Example

#### 7.1 Simple Example: Implementasi Custom Rate-Limiting Flow (Scala 3 & Pekko Streams)

Berikut adalah implementasi operator kustom menggunakan `GraphStage` untuk menahan laju aliran data berdasarkan kuota waktu (token bucket sederhana) tanpa memblokir thread.

```scala
package enterprise.streaming.simple

import org.apache.pekko.stream.*
import org.apache.pekko.stream.stage.*
import scala.concurrent.duration.*

final class RateLimiterStage[A](elementsPerSecond: Int) 
    extends GraphStage[FlowShape[A, A]]:

  val in: Inlet[A] = Inlet[A]("RateLimiter.in")
  val out: Outlet[A] = Outlet[A]("RateLimiter.out")

  override val shape: FlowShape[A, A] = FlowShape(in, out)

  override def createLogic(inheritedAttributes: Attributes): GraphStageLogic =
    new TimerGraphStageLogic(shape) with InHandler with OutHandler:
      private val interval: FiniteDuration = (1000.0 / elementsPerSecond).millis
      private var pendingElement: Option[A] = None
      private var isTimerActive: Boolean = false
      private val TimerKey: String = "RateLimiterTimer"

      setHandlers(in, out, this)

      override def onPush(): Unit =
        val elem = grab(in)
        if !isTimerActive then
          push(out, elem)
          isTimerActive = true
          scheduleOnce(TimerKey, interval)
        else
          pendingElement = Some(elem)

      override def onPull(): Unit =
        if !isTimerActive && pendingElement.isDefined then
          val elem = pendingElement.get
          pendingElement = None
          push(out, elem)
          isTimerActive = true
          scheduleOnce(TimerKey, interval)
        else if !hasBeenPulled(in) && pendingElement.isEmpty then
          pull(in)

      override protected def onTimer(timerKey: Any): Unit =
        if timerKey == TimerKey then
          isTimerActive = false
          if pendingElement.isDefined && isAvailable(out) then
            val elem = pendingElement.get
            pendingElement = None
            push(out, elem)
            isTimerActive = true
            scheduleOnce(TimerKey, interval)
          else if isAvailable(out) && !hasBeenPulled(in) then
            pull(in)
```

#### 7.2 Practical Example: Enterprise Ingestion Pipeline dengan Kafka, Circuit Breaker, dan At-Least-Once Semantics (FS2 & Cats Effect 3)

Contoh nyata arsitektur ingestion streaming berskala industri menggunakan **FS2 3.x** dan **fs2-kafka**. Mengimplementasikan pembacaan batch dari Kafka, validasi skema, evaluasi side-effect eksternal dengan Circuit Breaker, pemisahan error ke DLQ, dan *idempotent commit*.

```scala
package enterprise.streaming.production

import cats.effect.*
import cats.syntax.all.*
import fs2.{Chunk, Pipe, Stream}
import fs2.kafka.*
import scala.concurrent.duration.*

// Domain Data Definitions
final case class TransactionEvent(txId: String, accountId: String, amount: BigDecimal, timestamp: Long)
final case class EnrichedEvent(event: TransactionEvent, riskScore: Double)
final case class DeadLetterRecord(rawPayload: String, reason: String, timestamp: Long)

trait RiskScoringClient[F[_]]:
  def evaluateRisk(event: TransactionEvent): F[Double]

object RiskScoringClient:
  def make[F[_]: Async]: F[RiskScoringClient[F]] =
    Async[F].delay:
      new RiskScoringClient[F]:
        override def evaluateRisk(event: TransactionEvent): F[Double] =
          // Simulasi I/O bound HTTP call ke ML scoring engine dengan timeout terikat
          Async[F].sleep(15.millis) *> Async[F].pure(if event.amount > 10000 then 0.85 else 0.12)

object TransactionStreamingEngine:

  private val KafkaBootstrapServers = "localhost:9092"
  private val SourceTopic = "finance.transactions.raw"
  private val DLQTopic = "finance.transactions.dlq"
  private val TargetTopic = "finance.transactions.scored"

  def consumerSettings[F[_]: Async]: ConsumerSettings[F, String, String] =
    ConsumerSettings[F, String, String]
      .withAutoOffsetReset(AutoOffsetReset.Earliest)
      .withBootstrapServers(KafkaBootstrapServers)
      .withGroupId("tx-risk-profiler-v1")
      .withProperty("enable.auto.commit", "false")
      .withProperty("max.poll.records", "1000")

  def producerSettings[F[_]: Async]: ProducerSettings[F, String, String] =
    ProducerSettings[F, String, String]
      .withBootstrapServers(KafkaBootstrapServers)

  // Deserializer murni tanpa throwing exceptions
  def parsePayload(raw: String): Either[String, TransactionEvent] =
    val parts = raw.split(",")
    if parts.length == 4 then
      Either.catchNonFatal {
        TransactionEvent(parts(0).trim, parts(1).trim, BigDecimal(parts(2).trim), parts(3).trim.toLong)
      }.leftMap(_.getMessage)
    else Left(s"Invalid schema format. Expected 4 tokens, got ${parts.length}")

  // Pipeline Processing Utama
  def runPipeline[F[_]: Async](
      riskEngine: RiskScoringClient[F]
  ): Stream[F, Unit] =

    val transactionalConsumer = KafkaConsumer.stream(consumerSettings[F])

    transactionalConsumer.evalTap(_.subscribeTo(SourceTopic)).flatMap { consumer =>
      consumer.stream
        .mapChunks { committableRecords =>
          // Eksekusi parsing batch pada chunk level
          committableRecords.map { record =>
            val parsed = parsePayload(record.record.value)
            (parsed, record)
          }
        }
        .parEvalMap(maxConcurrent = 32) {
          case (Right(tx), record) =>
            // Eksekusi penilaian risiko terlindungi terhadap timeout dan kegagalan
            riskEngine.evaluateRisk(tx)
              .timeout(200.millis)
              .map { score =>
                val enriched = EnrichedEvent(tx, score)
                val outRecord = ProducerRecord(TargetTopic, tx.txId, enriched.toString)
                Right((ProducerRecords.one(outRecord), record.offset))
              }
              .handleErrorWith { err =>
                Async[F].pure {
                  val dlq = DeadLetterRecord(record.record.value, s"Processing Timeout/Failure: ${err.getMessage}", System.currentTimeMillis())
                  val outRecord = ProducerRecord(DLQTopic, record.record.key, dlq.toString)
                  Left((ProducerRecords.one(outRecord), record.offset))
                }
              }

          case (Left(errorReason), record) =>
            Async[F].pure {
              val dlq = DeadLetterRecord(record.record.value, s"Deserialization Error: $errorReason", System.currentTimeMillis())
              val outRecord = ProducerRecord(DLQTopic, record.record.key, dlq.toString)
              Left((ProducerRecords.one(outRecord), record.offset))
            }
        }
        .groupWithin(n = 500, d = 50.millis) // Windowing untuk micro-batch commit
        .evalMap { chunk =>
          val allRecords = chunk.map {
            case Right((prodRecords, _)) => prodRecords
            case Left((dlqRecords, _))  => dlqRecords
          }.toList

          val offsets = CommittableOffsetBatch.fromFoldable(
            chunk.map {
              case Right((_, offset)) => offset
              case Left((_, offset))  => offset
            }
          )

          for
            _ <- KafkaProducer.stream(producerSettings[F]).evalMap(_.produce(ProducerRecords(allRecords))).compile.drain
            _ <- offsets.commit // Commit offsets secara atomic setelah sink terkonfirmasi
          yield ()
        }
    }
```

---

### 8. Real-World Case Study (Enterprise Scale)

#### Skenario: Tier-1 Payment Switch Ingestion Gateway
- **Beban Lalu Lintas**: Puncak transaksi 250.000 events/detik saat event e-commerce nasional.
- **SLA**: Latensi $P_{99} < 40\text{ms}$, Zero Data Loss ($RPO = 0$).

#### Masalah Lapangan
Implementasi awal menggunakan naive Pekko Streams graph dengan `.mapAsync(128)` yang memanggil *downstream distributed database* (ScyllaDB) secara langsung.
Saat klaster database mengalami relokasi partisi disk:
1. Latensi database meningkat dari $2\text{ms}$ ke $120\text{ms}$.
2. Operator `.mapAsync` menahan pesan di dalam internal actor buffer.
3. Thread scheduler kehabisan slot thread eksekusi (*Thread Starvation*), karena context-switching berlebihan akibat unbounded asynchronous fork.
4. Terjadi cascade failure: Kafka Consumer gagal merespons *heartbeat* grup, koordinator Kafka menganggap *node die*, memicu cascading *Consumer Rebalance Storm*.

#### Solusi Arsitektural Produksi
1. **Dynamic Micro-Batching via Flat Buffer**:
   Mengganti pemanggilan per-record `.mapAsync` dengan stage agregator flat vector:
   `Flow.groupedWithin(1000, 10.milliseconds)`.
2. **Backpressure-Aware Circuit Breaker**:
   Menerapkan Circuit Breaker berbasis Exponential Moving Average (EMA). Jika $P_{95}$ latensi downstream melebihi $80\text{ms}$, buffer mengeksekusi *Throttled Mode* dan meredam laju pengambilan data dari Kafka partition socket, bukan menumpuknya di memori.
3. **Pemisahan Thread Pool (Bulkheading)**:
   Mengalokasikan *Dedicated Dispatcher* dengan L1 cache locality untuk serialisasi, dan Dispatcher terpisah berbasis *Virtual Threads / Work-Stealing Pool* untuk I/O socket database.

```
[Kafka Ingress] 
      │ 
      ▼
[Pekko Source: Dedicated Ingress Dispatcher]
      │
      ▼ (In-Memory RingBuffer: max 4096 elements)
[Dynamic Grouping: 1000 items / 10ms]
      │
      ▼
[Circuit Breaker Stage: Latency Tracking via EMA]
      ├── Normal Flow ──> [Batch Upsert: Bulkhead I/O Dispatcher] ──> [ScyllaDB]
      └── Breaker Open ─> [Dynamic Slowdown: request(n) Throttle]
```

Hasil Metrik Produksi:
- Alokasi memori GC berkurang sebesar **62%**.
- Tidak ada crash OOM selama lonjakan 280.000 events/detik.
- Latensi $P_{99}$ stabil pada angka **28.4ms**.

---

### 9. Trade-offs

| Aspek | Pilihan A: Pekko / Akka Streams | Pilihan B: FS2 (Functional Streams) |
| :--- | :--- | :--- |
| **Model Eksekusi** | Actor-backed, Fused GraphInterpreter. | Fiber-backed, Pure functional Pull algebra. |
| **Integrasi Enterprise** | Ekosistem Alpakka yang sangat masif (AWS, GCP, Kafka, MQ). | Ekosistem Typelevel (fs2-kafka, http4s, skunk, doobie). |
| **State Management** | State mutable terenkapsulasi aman di `GraphStageLogic`. | State immutable berbasis `Ref`, `Deferred`, atau recursive `Pull`. |
| **Learning Curve** | Sedang; konsep Graph DSL mudah dipahami secara visual. | Sangat Curam; memerlukan penguasaan mendalam kategori fp & Monad Transformers. |
| **Footprint Memori** | Menengah (overhead alokasi objek GraphStage & Actor internals). | Sangat Ringan (zero-cost chunks & lightweight fibers). |
| **Cost & Profiling** | Profiler thread JVM standar (JProfiler, AsyncProfiler) mudah membaca Actor. | Sulit melacak call-stack trace murni fungsional karena deep fiber nesting. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Thread Starvation Akibat Pemanggilan Blocking I/O di Tengah Stream
*Anti-Pattern*:
```scala
// FATAL: Memblokir compute thread pool runtime streaming!
stream.map { record =>
  val response = apacheHttpClient.execute(new HttpGet(record.url)) // BLOCKING
  response.getStatusLine.getStatusCode
}
```
*Solusi*:
Bungkus I/O yang bersifat blocking secara deterministik menggunakan context boundary yang diisolasi:
```scala
// Solusi FS2: Mengalihkan eksekusi ke blocking pool bawaan Cats Effect
stream.evalMap { record =>
  Sync[F].blocking {
    val response = apacheHttpClient.execute(new HttpGet(record.url))
    response.getStatusLine.getStatusCode
  }
}
```

#### 10.2 Silent Stream Termination
*Gejala*: Stream berhenti memproses data tanpa error log atau stacktrace.
*Penyebab Utama*: Stream dievaluasi dengan `onError` yang menelan exception, atau unhandled exception pada sub-graf bercabang (*Broadcast/Zip*) yang menyebabkan salah satu cabang terminasi dan menggantungkan cabang lainnya (*hang indefinitely*).
*Troubleshooting*:
- Pasang hook global supervision:
  ```scala
  val decider: Supervision.Decider = {
    case e: NonFatal =>
      logger.error("Exception handled by stream supervision decider", e)
      Supervision.Resume
    case fatal =>
      logger.error("FATAL exception encountered. Stopping stream pipeline", fatal)
      Supervision.Stop
  }
  implicit val mat: Materializer = Materializer(system)
  val actorSettings = ActorMaterializerSettings(system).withSupervisionStrategy(decider)
  ```

#### 10.3 Dynamic Demand Deadlock pada Merging Streams
*Gejala*: Aliran terhenti permanen saat menggunakan operator perpaduan seperti `Zip` atau `ZipWith`.
*Penyebab*: Aliran A menghasilkan data jauh lebih cepat daripada Aliran B, dan Aliran B tidak memancarkan data sama sekali karena dependensi mutual resource. Aliran A memblokir buffer hingga batas maksimal, mengunci downstream consumer.
*Solusi*: Gunakan buffer eksplisit dengan opsi drop (*DropHead/DropTail*) jika data parsial dapat dibuang, atau gunakan `mergePrioritized` jika prioritas aliran berbeda.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Explicit Buffer Allocation**: Selalu definisikan ukuran buffer batas (`bounded`) pada setiap asynchronous boundary. Dilarang keras menggunakan unbounded queues di produksi.
2. [ ] **Dispatcher Bulkheading**: Pisahkan thread pool komputasi stream dengan thread pool I/O blocking (JDBC, native libraries).
3. [ ] **Idempotent Sinks**: Rancang operasi penulisan hilir dengan semantik idempotent (misal: *UPSERT* berbasis deterministic hash key) untuk mengatasi duplikasi data akibat replikasi at-least-once.
4. [ ] **End-to-End Tracing Propagation**: Injeksikan W3C TraceContext headers ke dalam metadata Kafka message di setiap transformasi stream.
5. [ ] **Heap Footprint Sizing**: Gunakan Chunk size yang seimbang (misal: 512 - 4096 records per batch). Chunk terlalu kecil meningkatkan overhead allocation JVM; chunk terlalu besar memicu GC pause generasi *Tenured*.
6. [ ] **Safe Resource Finalization**: Pastikan semua koneksi socket, file handles, dan channel jaringan dibungkus menggunakan konstruksi terproteksi (`Stream.bracket`, `Resource`, atau `GraphStage.postStop`).

---

### 12. Hands-on Practice

Implementasikan proyek hands-on production-ready berikut dan letakkan seluruh source code di direktori repository: `hands-on/m02/`.

#### Langkah 1: Setup Dependensi Build (`build.sbt`)
```scala
ThisBuild / scalaVersion := "3.3.3"
ThisBuild / version      := "0.1.0-SNAPSHOT"

lazy val root = (project in file("."))
  .settings(
    name := "reactive-streaming-production",
    libraryDependencies ++= Seq(
      "co.fs2"        %% "fs2-core"         % "3.10.2",
      "co.fs2"        %% "fs2-io"           % "3.10.2",
      "com.github.fd4s" %% "fs2-kafka"      % "3.5.0",
      "org.typelevel" %% "cats-effect"      % "3.5.4",
      "ch.qos.logback" %  "logback-classic" % "1.5.6"
    ),
    scalacOptions ++= Seq(
      "-deprecation",
      "-feature",
      "-Xfatal-warnings"
    )
  )
```

#### Langkah 2: Implementasi Windowed Anomaly Aggregator (`hands-on/m02/AnomalyAggregator.scala`)
Tuliskan implementasi stateful detector yang memproses stream log metrik server dan memancarkan alarm jika latensi rata-rata dalam rentang window 5 detik melebihi threshold $500\text{ms}$.

```scala
package enterprise.streaming.handson

import cats.effect.*
import fs2.{Chunk, Pipe, Stream}
import scala.concurrent.duration.*

final case class MetricPayload(serverId: String, latencyMs: Long, timestamp: Long)
final case class LatencyAlarm(serverId: String, averageLatencyMs: Double, sampleSize: Int, windowEnd: Long)

object AnomalyAggregator extends IOApp.Simple:

  def detectAnomalies(thresholdMs: Double, windowDuration: FiniteDuration): Pipe[IO, MetricPayload, LatencyAlarm] =
    inStream =>
      inStream
        .groupWithin(n = 10000, d = windowDuration)
        .flatMap { (chunk: Chunk[MetricPayload]) =>
          val groupedByServer = chunk.toList.groupBy(_.serverId)
          val alarms = groupedByServer.flatMap { case (serverId, metrics) =>
            val count = metrics.size
            if count > 0 then
              val avg = metrics.map(_.latencyMs).sum.toDouble / count
              if avg > thresholdMs then
                Some(LatencyAlarm(serverId, avg, count, System.currentTimeMillis()))
              else None
            else None
          }
          Stream.emits(alarms.toSeq)
        }

  def mockMetricSource: Stream[IO, MetricPayload] =
    Stream
      .awakeEvery[IO](50.millis)
      .zipWithIndex
      .map { case (_, idx) =>
        val server = if idx % 2 == 0 then "srv-alpha" else "srv-beta"
        val latency = if server == "srv-alpha" && idx > 50 then 650L else 120L
        MetricPayload(server, latency, System.currentTimeMillis())
      }

  override def run: IO[Unit] =
    mockMetricSource
      .through(detectAnomalies(thresholdMs = 500.0, windowDuration = 2.seconds))
      .evalTap { alarm =>
        IO.println(s"[ALERT] High Latency Detected on ${alarm.serverId}! Average: ${alarm.averageLatencyMs}ms across ${alarm.sampleSize} samples.")
      }
      .take(5)
      .compile
      .drain
```

---

### 13. Exercises

#### Level: Easy
Implementasikan ekstensi pipe FS2 bernama `deduplicateConsecutive[F[_], A]` yang menghapus elemen duplikat yang muncul berurutan secara beruntun menggunakan pure recursive `Pull`.
*Signature*:
```scala
def deduplicateConsecutive[F[_], A]: Pipe[F, A, A]
```

#### Level: Medium
Buatlah sebuah *Pekko Streams Custom GraphStage* bernama `DynamicSlidingWindow[A]` yang mengumpulkan elemen ke dalam sliding window dinamis berukuran $N$, namun dapat disesuaikan ukurannya secara dinamis melalui sinyal kontrol dari secondary Inlet `controlIn: Inlet[Int]`.

#### Level: Hard
Rancang dan implementasikan operator FS2 kustom `backpressuredWorkerPool[F[_]: Async, In, Out]` yang mendistribusikan elemen ke worker pool berukuran dinamis yang melakukan *auto-scale* antara rentang $minWorkers$ dan $maxWorkers$ berdasarkan kapasitas pemenuhan downstream demand. Jika downstream mulai mengalami lag (demand $\to 0$), pool worker harus menyusut ke nilai minimum secara deterministik guna menghemat resource CPU dan RAM.

---

### 14. Challenge

**Skenario**:
Anda ditugaskan mendesain sistem ingest data IoT untuk armada kendaraan otonom berskala 100.000 unit. Setiap unit mengirimkan batch sensor berukuran 100KB setiap 100ms melalui protokol WebSocket/TCP.

**Batasan & Tantangan**:
1. Server hanya memiliki memori JVM terbatas sebesar $16\text{ GB}$ Heap.
2. Jaringan internet seluler di lapangan sangat fluktuatif (*cellular jitter*): 30% kendaraan dapat mengalami diskoneksi tiba-tiba, lalu saat terkoneksi kembali, mengirimkan seluruh buffer offline mereka sekaligus (*stampede burst*).
3. Data sensor harus melalui 3 tahap:
   - Validasi integritas checksum SHA-256 (CPU-bound).
   - Spatial indexing ke dalam H3 Geospatial grid (CPU-bound).
   - Penulisan ke Time-Series Storage (I/O bound).

**Tugas Arsitektur**:
Rancang topologi stream lengkap (tuliskan blueprint arsitektur, diagram state, konfigurasi buffering, formula backpressure dynamic throttling, dan strategi penanganan backpressure downstream) untuk mencegah memory saturation pada saat *stampede burst* terjadi, tanpa menjatuhkan koneksi TCP kendaraan yang sedang online stabil.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. Apa peran metode `Subscription.request(n)` pada spesifikasi Reactive Streams?
2. Mengapa unbounded buffer dilarang keras dalam arsitektur streaming produksi?
3. Pada runtime Apache Pekko Streams, apa dampak fungsional dari pemanggilan `.async` di antara dua buah Flow?
4. Apa perbedaan mendasar antara representasi stream `fs2.Stream` dengan `fs2.Pull`?
5. Apa konsekuensi teknis jika implementasi custom `GraphStage` memanggil mutasi variabel state internalnya dari thread lain di luar *GraphStageLogic*?

#### Bagian 2: Intermediate (5 Soal)
6. Bagaimana cara kerja internal *Fusing* pada Akka/Pekko Streams dan mengapa teknik ini meningkatkan performa throughput?
7. Mengapa penanganan error menggunakan `Supervision.Resume` berpotensi berbahaya jika diterapkan pada kegagalan data deserialization yang korup?
8. Bagaimana strategi *At-Least-Once Processing* dipertahankan ketika downstream processing stream dikelompokkan ke dalam micro-batch via `groupedWithin`?
9. Jelaskan perbedaan mendasar mekanisme eksekusi konkurensi antara `.mapAsync(n)` pada Pekko Streams dan `.parEvalMap(n)` pada FS2.
10. Mengapa `fs2.Chunk` digunakan sebagai primitif data transfer daripada langsung memproses satu elemen `A` secara berulang (*single-element emission*)?

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Kasus Memory Leak**: Sebuah pipeline stream Pekko mengalami degradasi heap memory secara eksponensial setelah menambahkan operator `BroadcastHub.sink`. Dari hasil dump heap, teridentifikasi jutaan objek data tertahan di memori. Di manakah kemungkinan letak akar permasalahannya dan bagaimana cara mengatasinya?
12. **Kasus Thread Pool Exhaustion**: Sebuah stream FS2 memproses 10.000 file lokal per detik. Aplikasi tiba-tiba tidak responsif dan metrik HTTP server pada node yang sama mengalami 100% connection timeout. Investigasi menunjukkan thread pool CPU starvation. Bagaimana membedah dan memperbaikinya?
13. **Kasus Kafka Offset Skew**: Pipeline streaming Kafka menggunakan `.parEvalMap(64)` untuk memproses order keuangan. Tiba-tiba salah satu partisi berhenti maju (*stuck*), sementara partisi lain berjalan normal. Tidak ada error log. Apa yang terjadi di layer offset tracking dan bagaimana memperbaikinya?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Bagian 1: Basic
1. Memberikan sinyal kapasitas (*demand*) dari Subscriber ke Publisher secara asinkron, memerintahkan Publisher untuk hanya memancarkan data maksimal sebanyak $n$ elemen berikutnya, mencegah kelebihan beban (*buffer overflow*).
2. Karena jika kapasitas downstream berkurang, memori penampungan (*queue*) akan terus membengkak tanpa batas proporsional terhadap waktu hingga memicu fatal JVM crash: `java.lang.OutOfMemoryError: Java heap space`.
3. Memecah penyatuan graf (*fusing*), memisahkan stage upstream dan downstream ke dalam unit aktor independen yang berkomunikasi melalui bounded buffer berbasis concurrent queue, memungkinkan eksekusi konkuren antar core CPU.
4. `fs2.Stream` merepresentasikan aliran kontinu tingkat tinggi, sedangkan `fs2.Pull` adalah core engine tingkat rendah yang mengendalikan alur komputasi demand, pembacaan step-by-step, dan emisi chunk secara eksplisit.
5. Melanggar kontrak isolasi aktor internal Pekko, menyebabkan *race conditions*, inkonsistensi memori visibilitas, dan dapat memicu deadlock atau state corruption secara acak karena GraphStageLogic **bukan** thread-safe terhadap akses eksternal langsung.

#### Bagian 2: Intermediate
6. Menggabungkan beberapa stage ke dalam loop pemanggilan method langsung (*in-memory loop*) pada satu thread/aktor, memotong overhead alokasi amplop pesan aktor, serialisasi internal, dan context-switching antar core CPU.
7. Jika stream tidak merekam atau mengalihkan offset pesan yang korup tersebut ke DLQ sebelum melanjutkan (`Resume`), consumer akan terus mencoba memproses record yang sama pada saat restart atau offset Kafka akan tertahan/terlewat tanpa jejak audit (*silent data loss*).
8. Commit offset hanya boleh dieksekusi **setelah** seluruh batch dalam jendela micro-batch tersebut berhasil disimpan (*persisted*) secara sukses ke sink tujuan, menggunakan commit offset tertinggi yang aman untuk seluruh partisi terkait.
9. `.mapAsync(n)` pada Pekko menggunakan `Future` yang dijadwalkan pada `ExecutionContext` berbasis thread JVM, sedangkan `.parEvalMap(n)` pada FS2 mengeksekusi efek fungsional di atas Cats Effect *Fibers* (green threads/virtual threads) yang sangat ringan dan non-blocking.
10. Memproses elemen per-satuan memicu alokasi runtime dan context-switching yang sangat tinggi; `Chunk` membungkus array flat untuk memaksimalkan efisiensi memory layout CPU cache (L1/L2 data cache hits) dan mereduksi overhead looping loop runloop monadik.

#### Bagian 3: Skenario Kasus Produksi
11. **Analisis**: `BroadcastHub` mempertahankan *ring buffer* internal yang kecepatannya ditentukan oleh Subscriber **paling lambat** (*slowest consumer*). Jika ada satu subscriber yang macet atau tidak memicu demand, buffer `BroadcastHub` akan menahan elemen untuk semua subscriber hingga buffer limit tercapai atau menumpuk referensi objek di heap.
    **Solusi**: Pasang timeout atau boundary dropping (`buffer(size, OverflowStrategy.dropHead)`) pada setiap consumer yang terhubung ke `BroadcastHub`, atau gunakan kill-switch untuk mematikan consumer yang tidak responsif.
12. **Analisis**: Pembacaan file I/O lokal dieksekusi di dalam thread pool komputasi default (`compute-pool`), mengakibatkan thread worker kehabisan waktu CPU karena terblokir oleh operasi disk blocking kernel read.
    **Solusi**: Alihkan seluruh operasi file stream ke blocking dispatcher khusus menggunakan modul `fs2.io.file.Files` bawaan yang secara otomatis memanfaatkan bounded blocking thread pool khusus Cats Effect.
13. **Analisis**: Operator konkurensi tak berurutan (*unordered concurrency*) memproses pesan dengan durasi bervariasi. Jika ada satu pesan yang mengalami deadlock/loop tanpa timeout di dalam pool worker konkurensi (misal: hanging HTTP call), offset commit tracking tidak dapat memajukan offset karena offset sebelumnya belum selesai, menyebabkan offset checkpointing Kafka terhenti (*offset lock*).
    **Solusi**: Bungkus operasi di dalam `parEvalMap` dengan timeout eksplisit (`.timeout(...)`), dan terapkan `CommittableOffsetBatch` yang memiliki fallback handling jika ada offset yang gagal diproses.

---

### 16. Summary
Arsitektur streaming reaktif modern di Scala (baik menggunakan ekosistem Apache Pekko Streams ataupun Typelevel FS2) menyediakan landasan komputasi terdistribusi yang tangguh melalui penegakan protokol *demand-driven backpressure*. Pemahaman mendalam tentang siklus eksekusi internal (*GraphStages*, *Pull models*, *Fusing*, dan *Chunking*) adalah prasyarat mutlak untuk membangun sistem skala besar yang stabil, hemat alokasi memori heap, dan kebal terhadap degradasi performa akibat lonjakan lalu lintas yang tidak terduga. Penanganan error deterministik, isolasi thread dispatcher, serta integrasi semantik *At-Least-Once* dengan Apache Kafka memastikan integritas data finansial dan misi kritis pada standar kualitas enterprise tertinggi.