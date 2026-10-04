# BAB 07: Konkurensi, Asinkron, & Actor Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, software engineer diharapkan mampu:
- Menguasai internalisasi memori konkurensi JVM (Java Memory Model), *cache coherence* (MESI protocol), dan fenomena *false sharing* dalam konteks eksekusi runtime Scala 3.
- Mengimplementasikan state machine terdistribusi dan *actor lifecycle* menggunakan **Apache Pekko Typed** (atau Akka Typed) secara *type-safe* tanpa mengorbankan performa throughput.
- Mendesain pipeline pemrosesan data asinkron berbasis **Reactive Streams** dengan mekanisme *dynamic backpressure* untuk memitigasi risiko *OutOfMemoryError* (OOM).
- Menerapkan pola ketahanan sistem tingkat enterprise (*Resilience Patterns*): *Circuit Breaker*, *Bulkhead*, *Supervision Strategy*, dan *Mailbox Bounding*.
- Mengidentifikasi, mengisolasi, dan memecahkan masalah *actor starvation*, *deadlocks*, *mailbox overflow*, serta *context-switching overhead* pada sistem *high-concurrency* skala multi-node.

---

### 2. Prerequisite
Untuk memahami materi ini secara komprehensif, engineer wajib memiliki pemahaman mendalam tentang:
- **Scala Core**: Pemrograman fungsional tingkat lanjut, *Type Classes*, *Contextual Abstractions* (`using`, `given` pada Scala 3), *Pattern Matching*, dan manipulasi tipe ADT (*Algebraic Data Types*).
- **Concurrency Fundamentals**: Thread lifecycle, JVM stack vs heap memory, sinkronisasi primitif (`synchronized`, `volatile`), serta keterbatasan `scala.concurrent.Future`.
- **System Internals**: Dasar arsitektur CPU (L1/L2/L3 cache, NUMA architecture, CPU registers), Context Switching, non-blocking I/O (epoll/kqueue), dan format serialization binary (Protobuf/Avro).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Java Memory Model (JMM), Cache Lines, dan Mechanical Sympathy
Di balik abstraksi Actor dan Thread di Scala, eksekusi kode berjalan di atas virtual machine (JVM) yang dipetakan langsung ke *Operating System Native Threads*. Arsitektur CPU modern menggunakan hirarki memori berjenjang:

```
[Core 0] <---> L1 D-Cache (32KB) <---> L2 Cache (512KB) \
                                                          ---> L3 Shared Cache (16-32MB) <---> Main Memory (RAM)
[Core 1] <---> L1 D-Cache (32KB) <---> L2 Cache (512KB) /
```

1. **Cache Coherency & MESI Protocol**:
   Ketika dua thread pada Core yang berbeda mengakses memory location yang berada pada blok 64-byte yang sama (*Cache Line*), perubahan nilai pada Core 0 akan memaksa invalidasi cache line pada Core 1 melalui protokol bus-snooping (Modified, Exclusive, Shared, Invalid). 
2. **False Sharing**:
   Dua variabel independen yang dimutasi oleh dua thread berbeda berada dalam satu *cache line* 64-byte yang sama. Hal ini memicu *cache line bouncing* antar-core, yang menjatuhkan performa throughput hingga 90%. Penanggulangannya adalah *cache-line padding* atau anotasi `@jdk.internal.vm.annotation.Contended`.
3. **Happens-Before Relationship dalam Akka/Pekko Actor**:
   Pekko Typed menjamin keterurutan memori tanpa lock konvensional:
   $$\text{Processing Message } M_n \implies \text{Happens-Before} \implies \text{Processing Message } M_{n+1}$$
   State internal actor tidak memerlukan keyword `volatile` selama state disimpan dalam variabel lokal yang di-*loop* secara fungsional melalui *behavior transformation* (`Behaviors.receiveMessage` mengembalikan *next Behavior*). Internal actor runtime menyisipkan *memory barrier* (LoadStore/StoreStore fences) saat mengambil pesan baru dari mailbox concurrent queue (berbasis MPSC: *Multi-Producer Single-Consumer*).

#### B. Apache Pekko Typed vs Classic: Type-Safety & ActorRef[T]
Pada Classic Actor model (`akka.actor.Actor`), method `receive` bertipe `PartialFunction[Any, Unit]`. Hal ini rawan terhadap *runtime failure* akibat pengiriman pesan yang salah target. 

**Pekko Typed** mengubah paradigma tersebut:
- `ActorRef[T]`: Mengikat referensi actor secara ketat ke protokol pesan bertipe `T`.
- Actor tidak lagi berwujud class dengan state yang dapat dimutasi sembarangan, melainkan *behavior functions* ($Behavior[T]$):
  $$\text{Behavior}[T] = (\text{Context}[T], T) \to \text{Behavior}[T]$$
- Paradigma ini mengubah state management menjadi transisi state fungsional immutable murni.

#### C. Reactive Streams & Non-Blocking Dynamic Backpressure
Model Actor murni memiliki titik lemah: *unbounded mailbox* dapat menyebabkan OOM, sementara *bounded mailbox* default akan mendrop pesan atau memblokir pengirim (*blocking producer* merusak arsitektur asinkron). Solusinya adalah standar **Reactive Streams**:
- **Publisher** memproduksi data ke **Subscriber**.
- Hubungan divalidasi melalui **Subscription**.
- Backpressure diwujudkan melalui protokol pull berbasis batas atas (*demand-driven*): `Subscription.request(n)`. Publisher *dilarang keras* mengirim lebih dari $n$ elemen yang diminta.

```
+------------+                                      +------------+
| Publisher  |                                      | Subscriber |
+------------+                                      +------------+
      |                 subscribe(Subscriber)              |
      |--------------------------------------------------->|
      |                 onSubscribe(Subscription)          |
      |<---------------------------------------------------|
      |                 request(n)  [Demand Signal]         |
      |<---------------------------------------------------|
      |                 onNext(data_1) ... onNext(data_n)   |
      |--------------------------------------------------->|
```

---

### 4. Why & What

| Dimensi | `scala.concurrent.Future` | Traditional Thread Locks (`ReentrantLock`) | Apache Pekko Typed (Actor) |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Asinkron, Composable, Statik | Sinkron, Blocking, Manual Sync | Asinkron, Message-driven, Non-blocking |
| **Manajemen State** | Stateless / Sulit memutasi state | Stateful via Critical Sections | Isolated State per Actor (Lock-free) |
| **Fail Safety** | Terlokalisasi pada Future flatMap | Crash thread berpotensi deadlock | Let It Crash via *Supervision Strategy* |
| **Skalabilitas** | Terbatas pada satu node JVM | Terbatas pada satu node JVM | Transparan: Single JVM hingga Multi-node Cluster |
| **Backpressure** | Tidak ada bawaan | Manual via `Condition` / Semaphore | Bawaan via Streams / Protocol Ack |

#### Mengapa Tidak Cukup Menggunakan `Future` di Enterprise Core?
1. **State Aggregation Hell**: Mengkoordinasikan shared mutable state antar `Future` membutuhkan `AtomicReference` yang kompleks atau primitives locks yang rawan deadlock.
2. **Ketiadaan Konsep Siklus Hidup**: Anda tidak bisa memantau (*watch*), mematikan secara graceful, atau me-restart `Future` yang gagal di tengah eksekusi.
3. **Fire-and-Forget Loss**: `Future` menuntut thread scheduler segera menjadwalkan runnable; tanpa mailbox, lonjakan beban mendadak (*burst*) akan langsung menguras *heap memory* atau memicu *thread starvation*.

---

### 5. How (Workflow Detail)

Alur kerja pemrosesan pesan dan state transition di Pekko Typed:

```
[Inbound Network / Client]
           │ (Send Command)
           ▼
┌────────────────────────────────────────────────────────┐
│ ActorRef[Command]                                      │
│  │ (Enqueue)                                           │
│  ▼                                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Mailbox (Lock-Free MPSC Linked Queue)              │ │
│ └────────────────────────────────────────────────────┘ │
│  │ (Scheduled Dispatch via Dispatcher/ForkJoinPool)    │
│  ▼                                                     │
│ [Executor Thread]                                      │
│  │                                                     │
│  ├─► State(N) + Command                                │
│  │     │                                               │
│  │     ▼ (Pattern Match Logic)                         │
│  ├─► State Mutation: Returns Behavior[Command]         │
│  │     │                                               │
│  │     ├─► [Persist Event (Event Sourcing)]            │
│  │     ├─► [Emit Outbound Message via ActorRef]        │
│  │     └─► [Transition to State(N+1)]                  │
│  │                                                     │
│  ▼                                                     │
│ (Yield thread execution to next Actor Mailbox)         │
└────────────────────────────────────────────────────────┘
```

1. **Enqueuing**: Pengirim memanggil `actorRef ! message`. Pesan dimasukkan ke dalam lock-free Concurrent Mailbox.
2. **Scheduling**: Mailbox yang beralih status dari *empty* ke *non-empty* mendaftarkan dirinya ke `MessageDispatcher`.
3. **Execution**: `MessageDispatcher` mengalokasikan task ke JVM thread dari thread pool (default: `ForkJoinPool`).
4. **Behavior Evaluation**: Thread membaca batch pesan (sesuai setting `throughput`), mengevaluasi input terhadap `Behavior` saat ini, dan menghasilkan *New Behavior*.
5. **Yielding**: Thread melepaskan aktor tersebut setelah kuota *throughput* terpenuhi agar terhindar dari monopoli core CPU (*fair scheduling*).

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem: Kantor Pos Birokrasi Terisolasi
Bayangkan sebuah kantor yang berisi ribuan juru tulis independen (Actor).
- Masing-masing juru tulis memiliki kotak surat pribadi (*Mailbox*).
- Mereka tidak diizinkan berbicara langsung atau menyentuh meja juru tulis lain (*No Shared State*).
- Setiap juru tulis hanya dapat membaca satu surat dalam satu waktu, memproses instruksi, mengubah catatan pribadinya (*State Transition*), lalu membalas melalui kurir (*Message Passing*).
- Jika seorang juru tulis pingsan karena surat beracun (*Exception*), manajernya (*Supervisor*) memutuskan apakah juru tulis tersebut diberi surat baru, di-reset catatannya, atau diganti juru tulis baru.

#### Diagram Arsitektur Pemrosesan Sistem Pembayaran Terdistribusi

```
                   +------------------------+
                   | HTTP / gRPC Endpoint   |
                   +------------------------+
                               |
                               | (Ask pattern: ActorRef.ask)
                               v
               +--------------------------------+
               |  PaymentOrchestratorActor      |
               |  (Router / Round-Robin Pool)   |
               +--------------------------------+
                               |
         +---------------------+---------------------+
         |                                           |
         v                                           v
+-------------------------------+   +-------------------------------+
|  PaymentProcessorWorker-1     |   |  PaymentProcessorWorker-2     |
|  - State: Idle / Processing   |   |  - State: Idle / Processing   |
|  - CircuitBreaker Protected   |   |  - CircuitBreaker Protected   |
+-------------------------------+   +-------------------------------+
         |                                           |
         | (External API Call via Future)            |
         v                                           v
+-------------------------------+   +-------------------------------+
| Payment Gateway (Stripe/Xendit) |   | Payment Gateway (Stripe/Xendit) |
+-------------------------------+   +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Typed State Machine Actor (Scala 3)
Aktor pengelola koneksi jaringan yang memiliki state: `Disconnected`, `Connecting`, dan `Connected`.

```scala
package enterprise.concurrency.m02

import org.apache.pekko.actor.typed.{ActorRef, Behavior}
import org.apache.pekko.actor.typed.scaladsl.Behaviors

object ConnectionStateMachine:

  // 1. Protocol Definition via ADT
  sealed trait Command
  final case class Connect(ip: String, replyTo: ActorRef[Response]) extends Command
  final case class Disconnect(replyTo: ActorRef[Response]) extends Command
  final case class SendData(payload: Array[Byte], replyTo: ActorRef[Response]) extends Command

  sealed trait Response
  final case object ConnectedAck extends Response
  final case object DisconnectedAck extends Response
  final case class DataSentAck(bytesWritten: Int) extends Response
  final case class ErrorResponse(reason: String) extends Response

  // 2. Initial Behavior (Disconnected State)
  def apply(): Behavior[Command] = disconnected()

  private def disconnected(): Behavior[Command] =
    Behaviors.receive { (context, message) =>
      message match
        case Connect(ip, replyTo) =>
          context.log.info(s"Menghubungkan ke node $ip...")
          // Transisi state fungsional ke state 'connected'
          replyTo ! ConnectedAck
          connected(ip)
        case Disconnect(replyTo) =>
          replyTo ! ErrorResponse("Sudah dalam kondisi disconnected.")
          Behaviors.same
        case SendData(_, replyTo) =>
          replyTo ! ErrorResponse("Gagal: Koneksi belum terbentuk.")
          Behaviors.same
    }

  private def connected(currentIp: String): Behavior[Command] =
    Behaviors.receive { (context, message) =>
      message match
        case SendData(payload, replyTo) =>
          context.log.info(s"Mengirim ${payload.length} bytes ke $currentIp")
          replyTo ! DataSentAck(payload.length)
          Behaviors.same
        case Disconnect(replyTo) =>
          context.log.info(s"Memutus koneksi dari $currentIp")
          replyTo ! DisconnectedAck
          disconnected()
        case Connect(newIp, replyTo) =>
          replyTo ! ErrorResponse(s"Sedang aktif terhubung ke $currentIp. Disconnect terlebih dahulu.")
          Behaviors.same
    }
```

#### B. Practical Example: Resilient Worker dengan Circuit Breaker & Supervision
Implementasi pemrosesan transaksi batch enterprise dengan integrasi Pekko Streams, *Pekko Circuit Breaker*, dan *Supervision Strategy*.

```scala
package enterprise.concurrency.m02

import org.apache.pekko.actor.typed.{ActorSystem, Behavior, SupervisorStrategy}
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import org.apache.pekko.pattern.CircuitBreaker
import scala.concurrent.duration.*
import scala.concurrent.{ExecutionContext, Future}
import scala.util.{Failure, Success}

object ResilientPaymentProcessingEngine:

  sealed trait WorkerCommand
  final case class ProcessTransaction(
      txId: String, 
      amount: BigDecimal, 
      replyTo: org.apache.pekko.actor.typed.ActorRef[TxResult]
  ) extends WorkerCommand

  private final case class InternalExternalCallSuccess(txId: String, replyTo: org.apache.pekko.actor.typed.ActorRef[TxResult]) extends WorkerCommand
  private final case class InternalExternalCallFailure(txId: String, ex: Throwable, replyTo: org.apache.pekko.actor.typed.ActorRef[TxResult]) extends WorkerCommand

  sealed trait TxResult
  final case class TxSuccess(txId: String) extends TxResult
  final case class TxFailed(txId: String, reason: String) extends TxResult

  // External Unreliable Third-Party Service
  class BankGatewayClient(implicit ec: ExecutionContext):
    def executePayment(txId: String, amount: BigDecimal): Future[Unit] =
      Future {
        // Simulasi latensi jaringan dan intermitten failure
        if txId.endsWith("99") then throw new RuntimeException("503 Service Unavailable: Gateway Time-out")
        Thread.sleep(50) // Simulasi I/O
      }

  def workerBehavior(gateway: BankGatewayClient): Behavior[WorkerCommand] =
    Behaviors.setup { context =>
      implicit val ec: ExecutionContext = context.executionContext

      // Setup Pekko Circuit Breaker
      val breaker = new CircuitBreaker(
        scheduler = context.system.scheduler,
        maxFailures = 3,
        callTimeout = 500.millis,
        resetTimeout = 10.seconds
      ).onOpen(context.log.warn("ALERT: Circuit Breaker Gateway Bank TERBUKA! Fail-fast aktif."))
       .onClose(context.log.info("INFO: Circuit Breaker Gateway Bank TERTUTUP normal."))
       .onHalfOpen(context.log.info("INFO: Circuit Breaker Gateway Bank HALF-OPEN. Menguji kesehatan sistem..."))

      Behaviors.receiveMessage {
        case ProcessTransaction(txId, amount, replyTo) =>
          context.log.info(s"Menerima instruksi transaksi: $txId")
          
          val gatewayCall: Future[Unit] = breaker.withCircuitBreaker(gateway.executePayment(txId, amount))
          
          // Map response future kembali ke protokol internal actor secara aman
          context.pipeToSelf(gatewayCall) {
            case Success(_)  => InternalExternalCallSuccess(txId, replyTo)
            case Failure(ex) => InternalExternalCallFailure(txId, ex, replyTo)
          }
          Behaviors.same

        case InternalExternalCallSuccess(txId, replyTo) =>
          context.log.info(s"Transaksi $txId berhasil dibukukan.")
          replyTo ! TxSuccess(txId)
          Behaviors.same

        case InternalExternalCallFailure(txId, ex, replyTo) =>
          context.log.error(s"Transaksi $txId gagal dieksekusi: ${ex.getMessage}")
          replyTo ! TxFailed(txId, ex.getMessage)
          Behaviors.same
      }
    }

  def supervisedWorker(gateway: BankGatewayClient): Behavior[WorkerCommand] =
    Behaviors.supervise(workerBehavior(gateway))
      .onFailure[RuntimeException](SupervisorStrategy.restartWithBackoff(
        minBackoff = 1.second,
        maxBackoff = 30.seconds,
        randomFactor = 0.2
      ))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Real-Time Fraud & Ingestion E-Commerce (100.000 RPS)
Sebuah platform e-commerce multinasional mengalami lonjakan *Black Friday* sebesar 100.000 pesanan per detik (*orders per second*). Sistem lama berbasis thread-per-request blocking (Spring Boot + JDBC) runtuh akibat *Thread Pool Exhaustion* dan lonjakan memory GC footprint hingga 60GB.

#### Solusi Arsitektur
1. **Edge Ingestion**: HTTP request diterima menggunakan Pekko HTTP non-blocking IO loop (epoll-based).
2. **Backpressured Ingestion Pipeline**:
   ```scala
   Source.queue[OrderPlacement](bufferSize = 200000, OverflowStrategy.dropNew)
     .via(OrderValidationFlow)
     .groupedWithin(batchSize = 500, within = 20.millis)
     .mapAsync(parallelism = 16)(bulkInsertToCassandra)
     .to(Sink.ignore)
   ```
3. **Partitioning via Consistent Hashing Router**:
   Order diarahkan ke `FraudDetectorActor` berdasarkan `hash(userId)`. Hal ini menjamin transaksi dari user yang sama selalu dievaluasi secara berurutan (*in-order processing*) oleh actor yang sama tanpa memerlukan global distributed locks (seperti Redis Redlock) yang memicu latensi tinggi.
4. **Hasil**:
   - Throughput stabil pada 115.000 RPS.
   - P99 Latency turun dari 4.200ms ke 68ms.
   - Kebutuhan instans berkurang dari 120 server c5.2xlarge menjadi 18 server.

---

### 9. Trade-offs

| Pendekatan / Pola | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Actor Model (Apache Pekko Typed)** | Isolasi status sempurna, tahan failover (*Let-it-crash*), konkurensi masif tanpa lock. | *Stack trace* sulit dibaca saat terjadi error asinkron; kurva pembelajaran tim tinggi; biaya serialisasi pesan bila multi-node. |
| **Virtual Threads (Project Loom)** | Pemrograman imperatif sederhana; *stack trace* linier konvensional; integrasi legacy mudah. | Tidak menyelesaikan masalah koordinasi mutable state; tetap butuh sinkronisasi/locks; rawan *pinning thread* jika menggunakan `synchronized` jadul. |
| **Pekko Streams (Reactive Streams)** | Proteksi memory total dari OOM melalui dynamic backpressure; pipeline terkomposisi dengan bersih. | Menambah latensi mikro (*allocation overhead* per stage framing); debugging declarative graph streams membutuhkan tools visualisasi khusus. |
| **Circuit Breaker** | Menghentikan kegagalan berantai (*cascading failure*); melindungi dependency downstream. | Request ditolak instan saat state *open* (butuh strategi *fallback* sisi UX); konfigurasi tuning threshold sensitif terhadap false positive. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Menutup Konteks (*Closing over*) State Luar di dalam `Future` pada Actor
**Fatal Anti-pattern**:
```scala
// SALAH BESAR (Race Condition & Memory Visibility Bug)
var internalBalance: BigDecimal = 1000

Behaviors.receiveMessage {
  case Withdraw(amount) =>
    Future {
      // Thread pool luar memutasi variabel actor secara simultan!
      internalBalance -= amount 
    }
    Behaviors.same
}
```
**Perbaikan**: Gunakan `context.pipeToSelf` untuk memasukkan hasil komputasi asynchronous kembali ke mailbox sebagai pesan bertipe aman.

#### 2. Mailbox Starvation akibat Blocking I/O di Default Dispatcher
Menjalankan `Thread.sleep()`, panggilan JDBC sinkron, atau library legacy HTTP blocking di dalam Actor `receive` akan memblokir thread pekerja milik `ForkJoinPool`.
**Solusi**: Isolasi seluruh pemanggilan blocking ke dalam dedicated thread pool (*bulkheading*):
```hocon
blocking-io-dispatcher {
  type = Dispatcher
  executor = "thread-pool-executor"
  thread-pool-executor {
    fixed-pool-size = 32
  }
  throughput = 1
}
```

#### 3. Ask Pattern Memory Leak (Timeout Orphan)
Menggunakan `actorRef.ask(replyTo => Request(replyTo))` tanpa konfigurasi implicit `Timeout` yang ketat akan menumpuk promise callback di heap memory jika target actor mengalami *hung/deadlock*.

---

### 11. Best Practices (Production Checklist)

- [ ] **Protocol Immutability**: Semua pesan command/event actor wajib berupa `case class` murni tanpa data member yang dapat dimutasi (`val`, bukan `var`).
- [ ] **Mailbox Bounding**: Jangan gunakan unbounded mailbox default di enterprise edge. Pasang konfigurasi bounded queue dengan mitigasi drop (*deadletters* atau explicit backpressure).
- [ ] **Dedicated Dispatcher**: Pisahkan CPU-bound actor context dari Blocking I/O context.
- [ ] **No System.exit**: Jangan mematikan JVM saat ada aktor crash; konfigurasikan `SupervisorStrategy.restart`.
- [ ] **Serialization Check**: Pastikan semua pesan yang melintasi network cluster dapat diserialisasi secara efisien (gunakan Protobuf atau Jackson-CBOR; hindari serialisasi Java bawaan).
- [ ] **Graceful Stop Coordinated Shutdown**: Daftarkan clean-up phase saat menerima sinyal `SIGTERM` Kubernetes.

---

### 12. Hands-on Practice

Buatlah proyek berbasis sbt di direktori lokal Anda untuk modul ini:
Lokasi file: `hands-on/m02/`

#### Struktur Proyek:
```text
hands-on/m02/
├── build.sbt
└── src/
    └── main/
        └── scala/
            └── enterprise/
                └── concurrency/
                    └── OrderEngineApp.scala
```

#### `build.sbt`:
```scala
ThisBuild / scalaVersion := "3.3.3"

val PekkoVersion = "1.0.2"

libraryDependencies ++= Seq(
  "org.apache.pekko" %% "pekko-actor-typed" % PekkoVersion,
  "org.apache.pekko" %% "pekko-stream"      % PekkoVersion,
  "ch.qos.logback"    % "logback-classic"    % "1.4.14"
)
```

#### `src/main/scala/enterprise/concurrency/OrderEngineApp.scala`:
```scala
package enterprise.concurrency

import org.apache.pekko.actor.typed.{ActorRef, ActorSystem, Behavior}
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import org.apache.pekko.stream.scaladsl.{Sink, Source}
import scala.concurrent.duration.*

object OrderEngineApp:

  // --- Domain Protocol ---
  sealed trait OrderCommand
  final case class ProcessOrder(orderId: String, amount: Double, replyTo: ActorRef[OrderResponse]) extends OrderCommand

  sealed trait OrderResponse
  final case class OrderAccepted(orderId: String) extends OrderResponse
  final case class OrderRejected(orderId: String, reason: String) extends OrderResponse

  // --- Worker Actor Implementation ---
  object OrderWorker:
    def apply(): Behavior[OrderCommand] = Behaviors.receive { (context, msg) =>
      msg match
        case ProcessOrder(id, amount, replyTo) =>
          if amount > 10000.0 then
            context.log.warn(s"Pencegahan Fraud: Order $id ditolak karena melebihi threshold ($amount)")
            replyTo ! OrderRejected(id, "Limit transaksi terlampaui.")
          else
            context.log.info(s"Order $id lolos validasi sebesar $amount")
            replyTo ! OrderAccepted(id)
          Behaviors.same
    }

  // --- Root Guardian Actor ---
  sealed trait RootCommand
  private final case class WrappedResponse(resp: OrderResponse) extends RootCommand
  private final case object StartStreamTest extends RootCommand

  def rootBehavior(): Behavior[RootCommand] = Behaviors.setup { context =>
    val responseAdapter = context.messageAdapter[OrderResponse](WrappedResponse.apply)
    val worker = context.spawn(OrderWorker(), "DedicatedOrderWorker")

    context.self ! StartStreamTest

    Behaviors.receiveMessage {
      case StartStreamTest =>
        context.log.info("Menginisiasi pipeline Reactive Streams via Pekko Streams...")
        implicit val sys: ActorSystem[Nothing] = context.system

        // Mengalirkan 10 dummy order dengan throttle backpressure
        Source(1 to 10)
          .throttle(2, 500.millis)
          .map { i =>
            val orderAmount = if i == 5 then 15000.0 else i * 1500.0
            ProcessOrder(s"ORD-TXN-$i", orderAmount, responseAdapter)
          }
          .runWith(Sink.foreach(cmd => worker ! cmd))

        Behaviors.same

      case WrappedResponse(OrderAccepted(id)) =>
        context.log.info(s"Root Guardian menerima notifikasi: SUKSES untuk $id")
        Behaviors.same

      case WrappedResponse(OrderRejected(id, reason)) =>
        context.log.warn(s"Root Guardian menerima notifikasi: GAGAL untuk $id, Alasan: $reason")
        Behaviors.same
    }
  }

  def main(args: Array[String]): Unit =
    val system: ActorSystem[RootCommand] = ActorSystem(rootBehavior(), "OrderEnterpriseSystem")
    Thread.sleep(8000)
    system.terminate()
```

#### Jalankan Praktikum:
```bash
cd hands-on/m02/
sbt run
```

---

### 13. Exercise

#### Level: Easy
Implementasikan actor `CounterActor` yang menerima command `Increment(step: Int)`, `Decrement(step: Int)`, dan `GetCount(replyTo: ActorRef[Int])`. Buat actor ini murni fungsional tanpa keyword `var`.

#### Level: Medium
Implementasikan Aktor `RateLimiterActor` bertipe Typed. Aktor ini harus menahan command masuk dalam sebuah antrean internal (`scala.collection.immutable.Queue`) dan hanya mengeksekusinya ke worker target maksimal 5 pesan per detik menggunakan internal scheduler `context.scheduleOnce`.

#### Level: Hard
Buat implementasi kustom *Bounded Non-Blocking Drop-Head Mailbox* menggunakan Java Concurrent primitives (`AtomicReferenceArray` atau ring buffer) yang terintegrasi dengan Apache Pekko Typed, yang menjamin bahwa jika kapasitas antrean penuh ($N = 1000$), pesan tertua yang belum diproses akan di-drop secara atomic dan pesan baru di-enqueue tanpa memblokir thread produsen.

---

### 14. Challenge

**Skenario**: Sistem *Distributed Flash Sale Inventory Management* multi-tenant.
Rancang dan bangun arsitektur stateful actor engine yang memenuhi batasan:
1. Tidak ada overselling: Jika persediaan barang berjumlah 100, tepat 100 pemesan pertama yang memperoleh konfirmasi sukses, sisanya ditolak.
2. Setiap tenant memiliki 1 katalog barang dengan $N$ items.
3. Node sistem berjalan di 3 node cluster virtual terpisah (simulasikan kegagalan jaringan atau node crash di tengah-tengah transaksi).
4. Persyaratan: 
   - Gunakan Pekko Typed Persistence (Event Sourcing) model: State dibangun kembali dari *Command -> Event -> Persist -> Apply*.
   - Pasang circuit breaker saat mengonfirmasi reservasi dompet pembayaran pelanggan downstream.
   - Sediakan skema mitigasi *Split-Brain Resolver* (SBR) secara konseptual dan implementasikan recovery handling ketika worker crash sebelum command sempat membalas replyTo.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Mengapa memutasi variabel privat `var` di dalam closure `Future` pada method actor adalah pelanggaran fatal model konkurensi Actor?
2. Apa perbedaan mendasar antara implementasi Classic Actor (`akka.actor.Actor`) dan Typed Actor (`Behavior[T]`) dalam mendeteksi invalid message?
3. Sebutkan protokol 4 method utama yang menjadi basis dari standard **Reactive Streams**!
4. Jelaskan apa yang dimaksud dengan fenomena *False Sharing* pada L1/L2 Cache CPU dan bagaimana dampaknya pada thread engine di JVM!
5. Apa tugas utama dari parameter `throughput` di dalam konfigurasi Dispatcher Pekko?

#### B. Pertanyaan Intermediate
6. Jelaskan bagaimana prinsip *Happens-Before* dijamin oleh Mailbox Pekko antara pengirim pesan ($M_1$) dan pemrosesan pesan tersebut oleh Actor target tanpa menggunakan lock `synchronized` konvensional!
7. Kapan kita wajib memisahkan dispatcher aktor ke dalam *Dedicated Blocking Dispatcher*? Berikan contoh konkrit API yang berpotensi melumpuhkan default thread pool!
8. Apa kelemahan utama dari Mailbox bertipe *Unbounded* pada sistem yang dipasang di environment Kubernetes container?
9. Jelaskan bagaimana transisi status pada pola ketahanan *Circuit Breaker* (Closed $\to$ Open $\to$ Half-Open) bekerja dan kapan masing-masing state berpindah!
10. Bagaimana `context.messageAdapter` bekerja di Pekko Typed dan mengapa ini dibutuhkan ketika berkomunikasi dengan aktor lain yang memiliki protokol berbeda?

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Sistem Anda menggunakan Pekko Typed dan mengalami lonjakan CPU 100% pada semua core, namun metrik network I/O dan business logic throughput justru anjlok drastis ke level mendekati nol. Profiler menunjukkan jutaan thread switching dan antrean LockSupport.park/unpark. Analisis akar penyebab masalahnya!
12. **Kasus 2**: Sebuah microservice pemrosesan stream analitik membaca data dari Apache Kafka dan menuliskannya ke Elasticsearch. Tiba-tiba memory heap microservice membengkak secara eksponensial hingga terjadi CrashLoopBackOff (OOMKilled). Analisis kegagalan arsitektur dan rancang solusinya dengan Reactive Streams backpressure!
13. **Kasus 3**: Sebuah implementasi Actor menggunakan Ask Pattern (`?` / `ask`) untuk mengontak dependensi eksternal. Di bawah beban produksi yang sangat fluktuatif, terjadi degradasi performa yang parah dan pesan `AskTimeoutException` membanjiri log sistem, padahal downstream service melaporkan metrik response time mereka stabil di angka 30ms. Mengapa ini terjadi dan bagaimana solusinya?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### A. Basic
1. Closure `Future` dieksekusi oleh thread sembarang dari `ExecutionContext`, bukan thread yang sedang mengoperasikan aktor tersebut. Memutasi state `var` dari thread luar melanggar invariant aktor (*single-threaded execution per actor*), menghancurkan konsistensi memori dan memicu kondisi balapan (*race condition*).
2. Classic Actor menerima tipe `Any` (untyped), sehingga compiler tidak dapat mendeteksi apakah suatu command dapat ditangani aktor atau tidak. Typed Actor menggunakan parameter tipe invariant `Behavior[T]`, sehingga salah pengiriman tipe pesan akan memicu compile-time error.
3. `Publisher.subscribe(Subscriber)`, `Subscriber.onSubscribe(Subscription)`, `Subscription.request(n)`, dan `Subscriber.onNext(data)` / `onError` / `onComplete`.
4. *False Sharing* terjadi saat dua thread pada dua CPU Core memodifikasi data independen yang tidak sengaja berada dalam satu baris cache line memori 64-byte yang sama. Hal ini memicu protokol cache coherence (MESI) membatalkan baris cache line tersebut secara konstan (*cache line bouncing*), menghancurkan performa CPU.
5. Menentukan jumlah maksimum pesan yang diproses oleh sebuah aktor dalam satu siklus penjadwalan sebelum melepaskan (*yield*) thread tersebut kepada aktor lain di thread pool yang sama, demi menjaga keadilan antrean (*fairness*).

#### B. Intermediate
6. Mailbox diimplementasikan menggunakan concurrent non-blocking queue berarsitektur MPSC. Akses penulisan pesan oleh thread pengirim membangkitkan volatile-write / release-fence, sedangkan pengambilan pesan oleh dispatcher thread membangkitkan volatile-read / acquire-fence. JMM menjamin bahwa semua aksi sebelum volatile write *happens-before* aksi setelah volatile read.
7. Saat berinteraksi dengan API sinkron/blocking seperti JDBC, I/O filesystem standar, library Java pihak ketiga berbasis blocking socket. Jika dijalankan di default dispatcher, worker thread pool akan habis terblokir dan melumpuhkan pemrosesan seluruh aktor lain di aplikasi.
8. Unbounded Mailbox tidak memiliki limit atas tampungan memori. Jika kecepatan produsen melampaui kemampuan konsumsi aktor, mailbox akan menyedot heap memory hingga JVM terkena `java.lang.OutOfMemoryError: Java heap space` dan Kubernetes membunuh pod tersebut (OOMKilled).
9. **Closed**: Normal, seluruh eksekusi dialirkan ke target. Jika batas error (`maxFailures`) tercapai dalam window waktu tertentu $\to$ pindah ke **Open**. **Open**: Fail-fast, semua eksekusi langsung ditolak tanpa memanggil target. Setelah `resetTimeout` berlalu $\to$ pindah ke **Half-Open**. **Half-Open**: Mengizinkan sejumlah kecil request uji coba lewat; jika berhasil $\to$ pindah ke **Closed**, jika gagal lagi $\to$ kembali ke **Open**.
10. `context.messageAdapter` mentranslasikan respon dari subsistem/aktor luar yang bertipe $U$ menjadi command internal yang bertipe $T$ (sesuai kontrak `Behavior[T]`), sehingga type-safety aktor penampung tetap utuh tanpa harus mengekspos tipe pesan privat ke dunia luar.

#### C. Skenario Kasus Produksi
11. **Akar Masalah**: Kemungkinan besar terjadi *Thread Starvation* atau *False Sharing Ekstrem*, atau konfigurasi `parallelism-factor` yang disetel jauh melampaui jumlah core hardware fisik (misal: ribuan thread pada mesin 4-core). Akibatnya CPU menghabiskan 99% siklusnya untuk context-switching overhead dan CPU instruction cache misses, bukan menjalankan instruksi logika bisnis.
12. **Akar Masalah**: Producer Kafka mengalirkan pesan jauh lebih cepat daripada kapasitas penulisan Elasticsearch, dan pipeline streaming tidak mengimplementasikan dynamic backpressure (atau ada unbounded intermediate buffer yang menyerap jutaan record). 
    **Solusi**: Terapkan Pekko Streams dengan `KafkaConsumer.plainSource` yang diintegrasikan ke sink via `mapAsync` berbatas (*bounded parallelism*). Gunakan `request(n)` non-blocking loop yang menahan commit offset dan membaca record baru HANYA jika buffer penulisan Elasticsearch telah berhasil me-flush batch sebelumnya.
13. **Akar Masalah**: Bottleneck terjadi bukan pada downstream service, melainkan pada kehabisan thread di Dispatcher caller atau antrean mailbox aktor caller itu sendiri. Waktu 30ms downstream ditambah latency antrean mailbox internal yang memanjang (karena starvation) menyebabkan akumulasi total durasi melebihi batas konfigurasi ask timeout (misal: 1000ms), sehingga request kadaluwarsa sebelum sempat diproses. Solusi: Scale up worker actor pool, lakukan isolasi dispatcher, dan optimasi garbage collection allocation.

---

### 16. Summary

1. **Prinsip Isolasi Konkurensi**: Pekko Typed menyediakan proteksi absolut terhadap mutasi state konkuren via encapsulasi functional-behavioral transitions yang berakar kuat pada Java Memory Model.
2. **Mechanical Sympathy**: Performa arsitektur konkurensi tingkat tinggi ditentukan oleh pemahaman level rendah (JMM, false sharing, non-blocking queue MPSC, dan alokasi memory footprints).
3. **Resilience by Design**: Desain enterprise menolak pola pemrograman defensif rapuh; implementasikan prinsip *Let It Crash* via Supervision Strategy yang dikombinasikan dengan pelindung fail-fast terukur seperti *Circuit Breaker* dan *Bulkhead*.
4. **Dynamic Backpressure**: Pemrosesan volume masif wajib mematuhi standar Reactive Streams untuk mengontrol aliran data dari produsen ke konsumen tanpa merusak heap memori sistem.