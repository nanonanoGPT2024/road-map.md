# BAB 07 MODULE 01: KONKURENSI ASINKRON & ACTOR ARCHITECTURE

---

## SEKSI 01 — IDENTITAS MODUL

| Parameter | Spesifikasi |
| :--- | :--- |
| **Jalur Kurikulum** | 02-Programming-Languages / Scala Architecture Track |
| **Nomor Modul** | Bab 07, Modul 01 |
| **Topik Inti** | Konkurensi Asinkron, Non-blocking I/O, Future Monad, & Actor Model (Apache Pekko / Akka Typed) |
| **Tingkat Kesulitan** | Tingkat Lanjut (Advanced) |
| **Prasyarat Pengetahuan** | Scala 3 Core Syntax, Functional Programming (Monad, Functor), Pemrograman Threading Java Dasar (JMM) |
| **Target Ekosistem** | Scala 3.3+ LTS, Apache Pekko 1.0+ (atau Akka Typed 2.8+), Java 17/21 LTS |
| **Estimasi Waktu Belajar** | 6 - 8 Jam Intensif |

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, arsitek sistem dan insinyur perangkat lunak diharapkan mampu:

1. **Menganalisis dan Membedakan Paradigma Konkurensi**: Membedakan model konkurensi berbasis *Shared-Memory Multi-Threading* (dengan lock/mutex) terhadap model *Share-Nothing Message-Passing* (Actor Model) dan *Monadic Composition* (`scala.concurrent.Future`).
2. **Membangun Pipeline Non-Blocking Berbasis `Future`**: Mengimplementasikan orkestrasi asinkron end-to-end dengan kombinator monadic (`flatMap`, `map`, `traverse`, `sequence`, `recoverWith`) tanpa pernah memblokir thread eksekusi OS (`Thread.sleep`, `Await.result`).
3. **Mengonfigurasi dan Mengisolasi `ExecutionContext`**: Menerapkan arsitektur *Bulkheading* thread pool dengan memisahkan *CPU-bound execution context* (ForkJoinPool) dari *Blocking/IO-bound thread pool* secara presisi.
4. **Merancang Komponen Terdistribusi dengan Actor Model**: Mengkonstruksi aktor bertipe (*Typed Actors*) menggunakan Apache Pekko/Akka Typed yang mempertahankan *encapsulated mutable state* secara thread-safe tanpa menggunakan primitif sinkronisasi tingkat rendah.
5. **Menerapkan Pola Komunikasi Actor Lanjut**: Membangun interaksi berbasis *Fire-and-Forget* (`tell` / `!`) dan *Request-Response* (`ask` / `?`) menggunakan safe-narrowing response wrappers.
6. **Menerapkan Pola Ketahanan "Let It Crash"**: Mengonfigurasi pohon supervisi hierarkis (*Supervision Strategy: Resume, Restart, Stop*) untuk mencapai sifat *self-healing* dalam sistem berdaya tahan tinggi.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam paradigma pemrograman tradisional (Java klasik, C++), konkurensi dibangun di atas *Shared-Memory Architecture*. Dua atau lebih thread mengakses lokasi memori heap yang sama secara simultan. Untuk mencegah korupsi data (*data corruption*), kita dipaksa memasang barikade: `synchronized`, `ReentrantLock`, `volatile`, atau `Atomic*` wrapper. 

Mental model shared-memory memiliki cacat fundamental saat skala sistem membesar:
* **Deadlock & Livelock**: Urutan perolehan lock yang tidak konsisten melumpuhkan sistem.
* **Race Conditions**: Kesalahan tipis pada visibilitas memori (Java Memory Model) memunculkan bug yang tidak deterministik dan sangat sulit di-reproduksi.
* **Pencemaran Konkurensi**: Kebutuhan sinkronisasi menyebar ke seluruh lapisan kode, merusak modularitas domain.

```
PARADIGMA 1: SHARED-MEMORY (Tradisional)
[ Thread 1 ] ──┐
               ├──> [ Mutex / Lock ] ──> [ Shared Mutable State ] (Bottleneck & Deadlock prone)
[ Thread 2 ] ──┘

PARADIGMA 2: SHARE-NOTHING ACTOR MODEL (Modern Scala)
[ Actor 1 ] ──(Message Envelope)──> [ Mailbox ] ──> [ Actor 2 (State terisolasi) ]
                                                            │
                                              Dieksekusi secara sequensial
                                              tanpa butuh lock!
```

### Mental Model Pergeseran Paradigma
1. **Dunia sebagai Jaringan Pos (Actor Model)**: Bayangkan setiap Actor adalah seorang pekerja di sebuah bilik tertutup yang hanya memiliki satu kotak surat (*Mailbox*). Tidak ada yang boleh masuk ke bilik tersebut atau menyentuh meja kerjanya (*State*). Orang luar hanya bisa mengirim surat (*Immutable Message*). Sang pekerja membaca surat satu per satu dari kotak suratnya secara berurutan (*Single-Threaded Illusion*), memperbarui catatannya sendiri, dan bila perlu mengirim surat balasan ke kotak surat pekerja lain. Karena tidak ada dua pekerja yang menyentuh meja kerja yang sama, **tidak ada kemungkinan terjadinya race condition atau deadlock memori**.
2. **Dunia sebagai Jalur Perakitan Asinkron (`Future`)**: Bayangkan `Future[T]` bukan sebagai hasil nilai instan, melainkan sebuah kontrak janji (*placeholder*) untuk nilai yang sedang dirakit di jalur lain. Alih-alih menunggu pekerja selesai merakit komponen (memblokir thread), Anda mendefinisikan instruksi: *"Ketika komponen X selesai, otomatis pasang ke komponen Y, lalu kirim ke pelanggan Z."*

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Siklus Hidup Eksekusi `scala.concurrent.Future`

```
      Thread Pemanggil (Caller)
                │
                ├── 1. Inisiasi Future { compute() }
                │      │
                │      ▼
      ┌───────────────────────────────────┐
      │  ExecutionContext (ForkJoinPool)  │
      │  ┌─────────────────────────────┐  │
      │  │ Work-Stealing Queue         │  │
      │  │ [ Task A ] [ Task B ]       │  │
      │  └──────────────┬──────────────┘  │
      │                 │                 │
      │                 ▼                 │
      │      [ Worker Thread K ]          │
      │       Eksekusi Asinkron           │
      └─────────────────┬─────────────────┘
                        │
       2. Komputasi Selesai (Success / Failure)
                        │
                        ▼
           Promise-Completer Pipeline
                        │
      ┌─────────────────┴─────────────────┐
      ▼                                   ▼
 [ OnSuccess / map ]             [ OnFailure / recover ]
 (Dieksekusi asinkron)           (Dieksekusi asinkron)
```

### 2. Anatomi Internal Actor System (Typed)

```
[ Sender Actor / External Client ]
                 │
                 │ 1. Kirim Pesan: ref.tell(Message) / ref ! Message
                 ▼
    ┌─────────────────────────┐
    │     ActorRef[Command]   │  (Penunjuk lokasi logis - Thread-safe)
    └────────────┬────────────┘
                 │
                 │ 2. Masukkan ke Antrean
                 ▼
    ┌─────────────────────────┐
    │     Mailbox (MPSC)      │  (Multi-Producer Single-Consumer Queue)
    │  [Msg 1][Msg 2][Msg 3]  │
    └────────────┬────────────┘
                 │
                 │ 3. Dispatcher menjadwalkan eksekusi
                 ▼
    ┌─────────────────────────┐
    │    MessageDispatcher    │  (Berbasis ExecutionContext / ThreadPool)
    └────────────┬────────────┘
                 │
                 │ 4. Menugaskan Worker Thread untuk memproses batch pesan
                 ▼
    ┌────────────────────────────────────────────────────────┐
    │  Actor Instance (Stateful Context)                     │
    │  ┌──────────────────────────────────────────────────┐  │
    │  │ Private Mutable State: var count = 0             │  │
    │  │                                                  │  │
    │  │ Behavioral Message Handler:                      │  │
    │  │ (State, Message) => Behavior[Message]            │  │
    │  └──────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────┘
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dekonstruksi `scala.concurrent.Future`
Sebuah `Future[T]` di Scala secara fundamental adalah antarmuka *read-only* terhadap nilai yang belum tentu ada saat ini. Pasangan komplementernya yang memegang kendali penulisan (*write-side*) adalah `scala.concurrent.Promise[T]`.

* **Mekanisme State Transition**:
  `Future` beroperasi sebagai *State Machine* atomik dengan 3 keadaan:
  1. `Incomplete`: Nilai belum selesai dikomputasi. Menampung *Callback List* internal.
  2. `Success(value: T)`: Komputasi berhasil diselesaikan.
  3. `Failure(cause: Throwable)`: Komputasi gagal/melempar exception.

  Transisi dari `Incomplete` ke `Success` atau `Failure` dilakukan satu kali saja via instruksi `AtomicReference.compareAndSet` di level JVM. Begitu selesai, statusnya tidak dapat diubah (*immutable*).

* **Callback Registration & Memory Visibility**:
  Saat Anda memanggil `future.map(f)`, sebuah callback baru didaftarkan ke daftar callback internal. Jika `Future` masih berstatus `Incomplete`, callback disimpan dalam rantai memori tertaut (*linked list*). Ketika `Promise.complete()` dipanggil, thread eksekutor membalik daftar tersebut dan mengirimkan pekerjaan eksekusi fungsi `f` ke `ExecutionContext`. Hal ini memberikan jaminan *Happens-Before* sesuai Java Memory Model (JMM): semua modifikasi yang terjadi sebelum penulisan nilai ke `Promise` dijamin terbaca oleh thread yang mengeksekusi callback.

### 2. Dekonstruksi Actor Engine (Apache Pekko / Akka)
Aktor bukan thread OS. Satu instans JVM mampu menjalankan **jutaan aktor** secara simultan di atas kumpulan thread yang sangat kecil (misal: 8 thread pada CPU 8-core).

* **Mailbox Engine**:
  Mailbox umumnya diimplementasikan menggunakan algoritma *Concurrent Linked Queue* jenis **MPSC** (*Multi-Producer Single-Consumer*). Setiap thread/aktor dapat memasukkan pesan ke ujung antrean, namun hanya ada satu thread worker pada satu waktu yang diizinkan mengonsumsi pesan dari kepala antrean.
* **ActorCell / Actor Context**:
  Merupakan inti eksekusi aktor. `ActorRef` hanyalah pembungkus tipis (*handle*) yang mengarah ke `ActorCell`. `ActorCell` mengelola status aktor, referensi mailbox, dan status supervisi.
* **Throughput & Thread Sharing**:
  Saat dispatcher mengeksekusi aktor, sebuah thread dialokasikan untuk menguras maksimal sejumlah pesan tertentu dari mailbox (dikenal sebagai konfigurasi `throughput`, default: 5-30 pesan). Setelah kuota pesan selesai diproses, thread dilepaskan kembali ke pool, dan aktor lain dijadwalkan. Mekanisme ini mencegah fenomena *starvation* (satu aktor memonopoli thread pool).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Monadic Concurrency dengan `Future`
`Future` di Scala mematuhi hukum Monad: memiliki unit/pure constructor (`Future.successful`) dan operasi binding (`flatMap`).

```scala
// Representasi konseptual
trait Future[+T] {
  def map[S](f: T => S)(implicit ec: ExecutionContext): Future[S]
  def flatMap[S](f: T => Future[S])(implicit ec: ExecutionContext): Future[S]
}
```

Penggunaan `for-comprehension` di atas `Future` mendesugarisasikan kode asinkron menjadi rantai `flatMap` dan `map`, memberikan gaya sintaksis imperatif sekuensial namun dieksekusi secara murni non-blocking:

```scala
val totalBalance: Future[BigDecimal] = for {
  user     <- fetchUser(userId)        // Future[User]
  accounts <- fetchAccounts(user.id)   // Future[List[Account]]
  balances <- calculateTotal(accounts) // Future[BigDecimal]
} yield balances
```

### 2. Aksioma Teori Actor Model (Carl Hewitt, Gul Agha)
Actor Model dipublikasikan oleh Carl Hewitt pada 1973. Sebuah aktor didefinisikan sebagai entitas komputasi mandiri. Ketika menerima sebuah pesan, sebuah aktor HANYA dapat melakukan kombinasi dari 3 operasi berikut:
1. **Mengirim sejumlah pesan terbatas (*finite*) ke aktor lain** yang alamatnya ia miliki.
2. **Membuat sejumlah aktor baru (*finite*)** di bawah naungannya.
3. **Menentukan perilaku (*behavior*) baru** yang akan digunakan untuk memproses pesan berikutnya.

### 3. Akka / Pekko Typed: Mengamankan Tipe Pesan
Pada model Actor klasik (`Untyped Actor`), fungsi penerima didefinisikan sebagai:
`def receive: Receive = { case msg: Any => ... }`
Ini rentan kesalahan karena kompilator tidak dapat memverifikasi apakah tipe pesan yang dikirim didukung oleh aktor penerima.

Di **Pekko/Akka Typed**, aktor diparameterisasi dengan tipe pesan:
`Behavior[Command]` di mana aktor hanya menerima pesan turunan dari ADT (*Algebraic Data Type*) `Command`.

```scala
sealed trait BankCommand
case class Deposit(amount: BigDecimal, replyTo: ActorRef[Receipt]) extends BankCommand
case class Withdraw(amount: BigDecimal, replyTo: ActorRef[Receipt]) extends BankCommand
```
Jika Anda mencoba mengirim string atau objek tipe lain ke `ActorRef[BankCommand]`, **kode akan gagal dikompilasi**.

### 4. Filosofi Desain: "Let It Crash" & Pohon Supervisi
Dalam sistem konkuren berskala besar, menangani seluruh kemungkinan kegagalan menggunakan blok `try/catch` lokal menciptakan kode yang rapuh (*defensive programming*).

Prinsip Actor Model memisahkan:
* **Komputasi Normal**: Dijalankan oleh aktor pekerja (*Worker Actor*).
* **Penanganan Kegagalan**: Dijalankan oleh aktor pengawas (*Supervisor Actor*).

Jika terjadi fatal exception (misal: NPE, DatabaseConnectionLost), aktor pekerja membiarkan dirinya melempar *crash*. Pengawas yang berada satu tingkat di atas pohon hierarki menangkap sinyal kegagalan tersebut dan mengambil keputusan deterministik:
* `Restart`: Membuat ulang instans state aktor dari awal (default).
* `Resume`: Mengabaikan pesan yang menyebabkan error dan melanjutkan konsumsi pesan berikutnya.
* `Stop`: Mematikan aktor secara permanen.
* `Escalate`: Melempar error ke supervisor yang lebih tinggi lagi.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL (STEP-BY-STEP)

Pada contoh ini, kita mendemonstrasikan dua pilar konkurensi Scala:
1. Orkestrasi Monadic Asinkron menggunakan `Future`.
2. Pembuatan Typed Actor Stateful murni menggunakan Apache Pekko / Akka Typed DSL.

```scala
// build.sbt dependencies:
// libraryDependencies += "org.apache.pekko" %% "pekko-actor-typed" % "1.0.2"

package com.architecture.concurrency

import org.apache.pekko.actor.typed.{ActorRef, ActorSystem, Behavior}
import org.apache.pekko.actor.typed.scaladsl.Behaviors
import scala.concurrent.{ExecutionContext, Future}
import scala.util.{Failure, Success}

// =========================================================================
// BAGIAN 1: ASYNCHRONOUS NON-BLOCKING FUTURE PIPELINE
// =========================================================================

object AsyncPipelineDemo {
  // Gunakan ExecutionContext global bawaan untuk CPU-bound tasks
  import scala.concurrent.ExecutionContext.Implicits.global

  case class RawTelemetry(deviceId: String, payload: String)
  case class ValidatedTelemetry(deviceId: String, metricValue: Double)

  def fetchTelemetry(deviceId: String): Future[RawTelemetry] = Future {
    // Mensimulasikan non-blocking fetch
    RawTelemetry(deviceId, "42.85")
  }

  def parseAndValidate(raw: RawTelemetry): Future[ValidatedTelemetry] = Future {
    val value = raw.payload.toDouble
    if (value < 0.0) throw new IllegalArgumentException("Metrik negatif invalid")
    ValidatedTelemetry(raw.deviceId, value)
  }

  def persistTelemetry(data: ValidatedTelemetry): Future[Long] = Future {
    // Mensimulasikan penulisan ke storage (asinkron)
    1001L // Mengembalikan ID entri
  }

  def runPipeline(deviceId: String): Future[Long] = {
    // Komposisi monadic murni
    for {
      raw       <- fetchTelemetry(deviceId)
      validated <- parseAndValidate(raw)
      savedId   <- persistTelemetry(validated)
    } yield savedId
  }
}

// =========================================================================
// BAGIAN 2: TYPED ACTOR MODEL (STATE ENCAPSULATION & MESSAGE PASSING)
// =========================================================================

object TypedActorCounterDemo {

  // 1. Definisikan Protokol Komunikasi (ADT Command)
  sealed trait CounterCommand
  final case class Increment(step: Int) extends CounterCommand
  final case class Decrement(step: Int) extends CounterCommand
  final case class GetValue(replyTo: ActorRef[CounterValue]) extends CounterCommand

  // Protokol Respons
  final case class CounterValue(current: Int)

  // 2. Definisikan Behavior Aktor secara Fungsional (State Passing)
  def apply(currentCount: Int = 0): Behavior[CounterCommand] = Behaviors.receive { (context, message) =>
    message match {
      case Increment(step) =>
        context.log.info(s"Menaikkan nilai sebesar $step dari $currentCount")
        // Transisi ke behavior baru dengan state ter-update (Immutability murni)
        apply(currentCount + step)

      case Decrement(step) =>
        context.log.info(s"Menurunkan nilai sebesar $step dari $currentCount")
        apply(currentCount - step)

      case GetValue(replyTo) =>
        context.log.info(s"Membaca nilai terkini: $currentCount")
        // Kirim nilai kembali ke aktor pengirim (Tell Pattern)
        replyTo ! CounterValue(currentCount)
        // State tidak berubah
        Behaviors.same
    }
  }
}

// =========================================================================
// BAGIAN 3: TITIK MASUK UTAMA (INTEGRASI & EKSEKUSI)
// =========================================================================

object MainRunner extends App {
  import scala.concurrent.ExecutionContext.Implicits.global

  println("=== Menjalankan Future Pipeline ===")
  AsyncPipelineDemo.runPipeline("DEV-TX-99").onComplete {
    case Success(recordId) => println(s"[Future] Sukses memproses record ID: $recordId")
    case Failure(ex)       => println(s"[Future] Terjadi error: ${ex.getMessage}")
  }

  println("\n=== Memulai Typed Actor System ===")
  
  // Aktor guardian pengontrol alur demo
  val guardianBehavior: Behavior[Void] = Behaviors.setup { context =>
    // Spawn aktor counter
    val counterRef: ActorRef[TypedActorCounterDemo.CounterCommand] = 
      context.spawn(TypedActorCounterDemo(0), "counter-worker")

    // Spawn aktor respons observer
    val responseAdapter: ActorRef[TypedActorCounterDemo.CounterValue] = 
      context.spawn(Behaviors.receiveMessage { value =>
        context.log.info(s"[Observer] Nilai akhir diterima dari aktor: ${value.current}")
        Behaviors.same
      }, "response-observer")

    // Interaksi Tell (!)
    counterRef ! TypedActorCounterDemo.Increment(10)
    counterRef ! TypedActorCounterDemo.Increment(5)
    counterRef ! TypedActorCounterDemo.Decrement(3)
    counterRef ! TypedActorCounterDemo.GetValue(responseAdapter)

    Behaviors.empty
  }

  // Inisialisasi ActorSystem
  val system = ActorSystem[Void](guardianBehavior, "ProductionSystem")

  // Izinkan thread bekerja sebelum terminasi demo
  Thread.sleep(1500)
  system.terminate()
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Bagian 1: Pipeline Monadic Future
* **Baris 24-27 (`def fetchTelemetry`)**: Blok `Future { ... }` menyematkan tugas eksekusi ke `ExecutionContext`. Alih-alih mengembalikan `RawTelemetry` secara tersinkronisasi, metode ini langsung melepas thread pemanggil dan mengembalikan instans `Future[RawTelemetry]` berstatus `Incomplete`.
* **Baris 38-44 (`runPipeline`)**: For-comprehension ini dikompilasi menjadi pemanggilan terantai:
  ```scala
  fetchTelemetry(deviceId).flatMap(raw => 
    parseAndValidate(raw).flatMap(validated => 
      persistTelemetry(validated)
    )
  )
  ```
  Jika salah satu tahapan melempar exception (misal: `IllegalArgumentException` pada `parseAndValidate`), evaluasi rantai monad langsung dihentikan (*short-circuit*), dan `Future` akhir berstatus `Failure`, melewati eksekusi `persistTelemetry`.

### Analisis Bagian 2: Typed Actor State Machine
* **Baris 53-59 (`CounterCommand` ADT)**: Menggunakan pola `sealed trait`. Hal ini memastikan bahwa `counterRef` bertipe `ActorRef[CounterCommand]` memiliki batas tipe (*type boundary*) yang ketat. Kompiler memblokir pengiriman pesan apa pun selain `Increment`, `Decrement`, atau `GetValue`.
* **Baris 56 (`GetValue(replyTo: ActorRef[CounterValue])`)**: Pola Request-Response bertipe. Pesan menyertakan saluran balasan (*reply channel*) bertipe eksplisit `ActorRef[CounterValue]`. Hal ini menghilangkan ketergantungan pada mekanisme untyped `sender()`.
* **Baris 62 (`def apply(currentCount: Int = 0): Behavior[...]`)**: Pendekatan **Functional State Machine**. Kita tidak mendeklarasikan variabel mutable (`var count = 0`). Sebaliknya, status aktor disimpan sebagai argumen fungsi immutabel.
* **Baris 67 (`apply(currentCount + step)`)**: Alih-alih melakukan mutasi *in-place*, aktor mengembalikan behavior baru dengan state ter-update untuk memproses pesan berikutnya. Inilah implementasi murni dari hukum Actor Hewitt: *Determine the behavior to be used for the next message*.
* **Baris 75 (`replyTo ! CounterValue(currentCount)`)**: Operator `!` (dibaca: *tell*) mengirimkan pesan secara asinkron tanpa memblokir thread eksekusi aktor.

### Analisis Bagian 3: Guardian & Lifecycle
* **Baris 91 (`context.spawn(...)`)**: Pembuatan aktor anak (*child actor*) di bawah naungan root guardian. Di Pekko/Akka Typed, aktor tidak lagi dibuat secara global melalui `system.actorOf`, melainkan selalu secara hierarkis melalui `ActorContext`.

---

## SEKSI 09 — STUDI KASUS NYATA

### Skenario Produksi: Resilient Payment Gateway & Order Orchestrator
Sebuah platform E-Commerce berskala tinggi memproses ribuan transaksi per detik. Setiap pesanan (*Order*) harus melewati proses:
1. Validasi inventaris secara lokal (CPU-bound / In-Memory cache).
2. Pemotongan saldo melalui API Payment Gateway Eksternal pihak ketiga (Operasi I/O lambat, tidak stabil, sering terjadi latensi tinggi atau timeout).
3. Transisi state pesanan: `Pending` -> `Processing` -> `Paid` atau `PaymentFailed`.
4. Jika Payment Gateway gagal sementara (*transient error*), sistem harus melakukan mekanisme *exponential backoff retry* secara non-blocking tanpa menahan thread pemrosesan pesanan lain.

### Arsitektur Solusi
* **OrderProcessorActor**: Mengelola *lifecycle state* pesanan individual. Menggunakan typed message.
* **ExternalPaymentService**: Layanan yang membungkus pemanggilan jaringan ke Payment Gateway dalam `Future` dengan *Dedicated Blocking I/O Execution Context* untuk menghindari *thread starvation* pada Actor Dispatcher.
* **Pola Ask (`?`) dengan Supervision Strategy**: Menghubungkan aktor pesanan dengan supervisor yang secara otomatis menangani kegagalan infrastruktur.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap tingkat produksi dalam Scala 3 dan Apache Pekko Typed:

```scala
package com.architecture.concurrency.production

import org.apache.pekko.actor.typed.{ActorRef, ActorSystem, Behavior, SupervisorStrategy}
import org.apache.pekko.actor.typed.scaladsl.{ActorContext, Behaviors}
import org.apache.pekko.util.Timeout
import java.util.concurrent.Executors
import scala.concurrent.{ExecutionContext, Future}
import scala.concurrent.duration.*
import scala.util.{Failure, Success}

// =========================================================================
// 1. DOMAIN MODELS & TYPED PROTOCOLS
// =========================================================================

case class OrderId(value: String) extends AnyVal
case class Money(amount: BigDecimal, currency: String)

sealed trait PaymentResult
case class PaymentSuccess(transactionId: String) extends PaymentResult
case class PaymentDeclined(reason: String) extends PaymentResult

// Protokol Komunikasi Order Actor
sealed trait OrderCommand
final case class InitializeOrder(id: OrderId, total: Money, replyTo: ActorRef[OrderEvent]) extends OrderCommand
private final case class WrappedPaymentResponse(result: PaymentResult) extends OrderCommand
private final case class PaymentFailedTechnical(cause: Throwable) extends OrderCommand

// Protokol Event Output
sealed trait OrderEvent
case class OrderCompleted(orderId: OrderId, txId: String) extends OrderEvent
case class OrderFailed(orderId: OrderId, reason: String) extends OrderEvent

// =========================================================================
// 2. ISOLATED BLOCKING INFRASTRUCTURE LAYER
// =========================================================================

object PaymentGatewayClient {
  // BULKHEADING: Thread pool terisolasi khusus untuk operasi blocking HTTP I/O
  // Mencegah kelaparan thread pada ForkJoinPool milik Actor System utama!
  private val blockingThreadPool = Executors.newFixedThreadPool(16)
  implicit val blockingIoEc: ExecutionContext = ExecutionContext.fromExecutor(blockingThreadPool)

  def executePayment(orderId: OrderId, money: Money): Future[PaymentResult] = Future {
    // Simulasi panggilan jaringan HTTP blocking ke Payment Provider pihak ke-3
    if (money.amount <= 0) {
      PaymentDeclined("Jumlah pembayaran tidak valid.")
    } else if (orderId.value.contains("SIMULATE_IO_CRASH")) {
      throw new java.net.ConnectException("Koneksi gateway eksternal terputus (503 Service Unavailable)")
    } else {
      // Sukses
      PaymentSuccess(s"TX-${java.util.UUID.randomUUID().toString.take(8).toUpperCase}")
    }
  }
}

// =========================================================================
// 3. CORE ORDER ACTOR FSM (FINITE STATE MACHINE)
// =========================================================================

object OrderProcessorActor {

  // Initial State
  def apply(): Behavior[OrderCommand] = waitingForInit()

  private def waitingForInit(): Behavior[OrderCommand] =
    Behaviors.receive { (context, message) =>
      message match {
        case InitializeOrder(id, total, replyTo) =>
          context.log.info(s"[Order: ${id.value}] Memulai proses pesanan senilai ${total.currency} ${total.amount}")
          
          // Memanggil layanan asinkron via dedicated IO EC dan memetakan hasilnya kembali ke diri sendiri
          // Pola: Context.pipeToSelf menjamin respons Future masuk secara thread-safe ke Mailbox aktor
          implicit val ec: ExecutionContext = context.system.executionContext
          
          context.pipeToSelf(PaymentGatewayClient.executePayment(id, total)) {
            case Success(result) => WrappedPaymentResponse(result)
            case Failure(ex)     => PaymentFailedTechnical(ex)
          }

          // Transisi ke State Processing
          processingState(id, replyTo)

        case other =>
          context.log.warn(s"Pesan tidak valid di status uninitialized: $other")
          Behaviors.unhandled
      }
    }

  private def processingState(orderId: OrderId, customerChannel: ActorRef[OrderEvent]): Behavior[OrderCommand] =
    Behaviors.receive { (context, message) =>
      message match {
        case WrappedPaymentResponse(PaymentSuccess(txId)) =>
          context.log.info(s"[Order: ${orderId.value}] Pembayaran SUKSES via TX: $txId")
          customerChannel ! OrderCompleted(orderId, txId)
          Behaviors.stopped // Hentikan siklus hidup aktor pesanan setelah selesai

        case WrappedPaymentResponse(PaymentDeclined(reason)) =>
          context.log.warn(s"[Order: ${orderId.value}] Pembayaran DITOLAK. Alasan: $reason")
          customerChannel ! OrderFailed(orderId, reason)
          Behaviors.stopped

        case PaymentFailedTechnical(cause) =>
          context.log.error(s"[Order: ${orderId.value}] Kesalahan fatal komunikasi gateway: ${cause.getMessage}")
          customerChannel ! OrderFailed(orderId, "Infrastruktur Gateway Mengalami Gangguan")
          // Membiarkan aktor crash untuk di-handle pohon supervisi jika diperlukan, atau stop secara aman
          Behaviors.stopped

        case InitializeOrder(id, _, _) =>
          context.log.warn(s"[Order: ${id.value}] Duplicate Initialize Order diabaikan. Status: IN_PROGRESS.")
          Behaviors.same
      }
    }
}

// =========================================================================
// 4. SUPERVISED RESILIENT ORCHESTRATOR
// =========================================================================

object OrderSystemSupervisor {
  sealed trait SupervisorCommand
  case class ProcessOrder(id: OrderId, total: Money, replyTo: ActorRef[OrderEvent]) extends SupervisorCommand

  def apply(): Behavior[SupervisorCommand] = Behaviors.setup { context =>
    Behaviors.receiveMessage {
      case ProcessOrder(id, total, replyTo) =>
        // Terapkan Supervision Strategy: Restart on RuntimeException with Backoff
        val supervisedBehavior = Behaviors.supervise(OrderProcessorActor())
          .onFailure[RuntimeException](SupervisorStrategy.restartWithBackoff(minBackoff = 200.millis, maxBackoff = 2.seconds, randomFactor = 0.2))

        // Spawn child actor per pesanan (Pola ephemeral worker)
        val childRef = context.spawn(supervisedBehavior, s"order-worker-${id.value}")
        childRef ! InitializeOrder(id, total, replyTo)
        
        Behaviors.same
    }
  }
}

// =========================================================================
// 5. APPLICATION RUNNER
// =========================================================================

object ProductionECommerceApp extends App {
  val rootGuardian: Behavior[Void] = Behaviors.setup { context =>
    val supervisor = context.spawn(OrderSystemSupervisor(), "OrderSupervisor")

    // Event Listener Probe
    val eventProbe = context.spawn(Behaviors.receiveMessage[OrderEvent] {
      case OrderCompleted(id, txId) =>
        context.log.info(s">> NOTIFIKASI KLIEN: Order ${id.value} SELESAI. Ref: $txId")
        Behaviors.same
      case OrderFailed(id, reason) =>
        context.log.error(s">> NOTIFIKASI KLIEN: Order ${id.value} GAGAL! Detail: $reason")
        Behaviors.same
    }, "EventProbeListener")

    // 1. Eksekusi Order Normal
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("ORD-SUCCESS-001"), Money(150000.0, "IDR"), eventProbe)

    // 2. Eksekusi Order Ditolak
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("ORD-DECLINED-002"), Money(-5000.0, "IDR"), eventProbe)

    // 3. Eksekusi Order Network Error
    supervisor ! OrderSystemSupervisor.ProcessOrder(OrderId("SIMULATE_IO_CRASH_003"), Money(250000.0, "IDR"), eventProbe)

    Behaviors.empty
  }

  val system = ActorSystem[Void](rootGuardian, "ECommerceSystem")
  
  // Cleanup hook
  scala.sys.addShutdownHook {
    system.terminate()
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Arsitek perangkat lunak wajib memilih paradigma konkurensi berdasarkan profil beban kerja, bukan preferensi sintaksis semata.

| Karakteristik | Threads / Locks Klasik (Java JMM) | Monadic Concurrency (`scala.concurrent.Future`) | Typed Actor Model (Apache Pekko / Akka) | Functional Effects (ZIO / Cats Effect) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Abstraksi** | Shared mutable state dengan locks | Dataflow transformatif linear | Entity-based share-nothing message-passing | Pure functional declarative data structures |
| **Footprint Memori** | Berat (~1MB per Thread stack OS) | Sangat Ringan (Objek Heap sementara) | Ultra Ringan (~300 bytes per Actor instance) | Ultra Ringan (Green fiber ~100-500 bytes) |
| **Manajemen State** | Manual via Mutex/Atomic (Error-prone) | Tidak disarankan untuk mutable state | **Sangat Baik**: Terisolasi mutlak per aktor | **Sangat Baik**: Ref/STM murni fungsional |
| **Penanganan Kegagalan** | UncaughtExceptionHandler per thread | Rantai error recovery (`recover`, `recoverWith`) | **Hierarchical Supervision** ("Let it Crash") | Explicit Typed Error Channel (`ZIO[R, E, A]`) |
| **Distribusi Jaringan** | Tidak Mendukung (Hanya 1 JVM) | Terbatas pada RPC individual | **Bawaan** (Akka Cluster / Pekko Remote) | Membutuhkan layer protokol tambahan |
| **Sifat Eksekusi** | Preemptive | Asynchronous Non-blocking | Asynchronous Event-driven | Cooperative Multitasking / Non-blocking |
| **Kurva Pembelajaran** | Sedang (namun debugging sangat rumit) | Rendah (Mudah dipelajari) | Tinggi (Butuh pergeseran mental arsitektur) | Sangat Tinggi (Perlu penguasaan Monad/Category Theory) |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. Mailbox Overflow & Memory Starvation (OOM)
* **Kasus**: Secara default, mailbox aktor menggunakan `UnboundedMailbox`. Jika laju produksi pesan (*producer rate*) melebihi kapasitas konsumsi aktor (*consumer throughput*), jutaan pesan menumpuk di heap JVM.
* **Dampak**: `java.lang.OutOfMemoryError: Java heap space`, melumpuhkan seluruh instans server.
* **Mitigasi**: Selalu gunakan antrean terbatas (*Bounded Mailbox*) di sistem produksi dengan kebijakan *drop-newest*, *drop-oldest*, atau mekanisme *Reactive Streams Backpressure*.

### 2. Blocking Calls di Dalam Lingkungan Aktor atau Future
* **Kasus**: Memanggil JDBC query sinkron, `Thread.sleep()`, atau pemanggilan HTTP client tanpa asynchronous support langsung di dalam callback `Future` default atau handler `Behaviors.receive`.
* **Dampak**: Benang eksekusi (*worker thread*) pada `ForkJoinPool` akan terhenti (parkir). Akibatnya terjadi fenomena **Thread Starvation**, di mana seluruh aktor dan future lain dalam sistem tidak mendapatkan alokasi CPU untuk memproses tugas komputasi mereka.

### 3. Penutupan Variabel yang Mengubah State (*Closing Over Mutable State*)
* **Kasus**: Mengakses variabel mutable luar (`var`) di dalam blok `Future` atau di dalam callback aktor asinkron.
* **Dampak**: Terjadinya *data race condition* laten karena dua thread berbeda membaca dan menulis variabel referensi yang sama di luar kendali isolasi pesan Actor.

### 4. Deadlock pada Ask Pattern (`?`)
* **Kasus**: Aktor A melakukan `ask` ke Aktor B dengan timeout tak terhingga (`Duration.Inf`), sementara Aktor B membutuhkan respons dari Aktor A untuk menyelesaikan tugasnya.
* **Dampak**: Kebuntuan permanen (*deadlock*) dan memori bocor karena Promise internal ask pattern tidak pernah diselesaikan (*settled*).

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Menggunakan `Await.result` di Kode Produksi
Menghentikan thread secara paksa demi mengubah `Future[T]` menjadi nilai sinkron `T`.

```scala
// ❌ ANTI-PATTERN: Menghancurkan performa konkurensi non-blocking
val futureResult: Future[String] = fetchRemoteData()
val data: String = Await.result(futureResult, 5.seconds) // Thread OS TERBLOKIR di sini!

// PASANGKAN DENGAN KODE BERIKUT:
// ✅ IDIOMATIK: Meneruskan rantai secara asinkron
fetchRemoteData().map { data =>
  processData(data)
}
```

### Kesalahan 2: Menggunakan `ExecutionContext.Implicits.global` untuk Operasi I/O Blocking
Mengalokasikan tugas komputasi CPU dan pemblokiran disk/jaringan ke satu pool yang sama.

```scala
// ❌ ANTI-PATTERN: Memblokir default pool
import scala.concurrent.ExecutionContext.Implicits.global

def readLargeFile(): Future[String] = Future {
  scala.io.Source.fromFile("/var/log/huge.log").mkString // Blocking I/O menguras worker CPU!
}

// PASANGKAN DENGAN KODE BERIKUT:
// ✅ IDIOMATIK: Pisahkan pool I/O menggunakan Bulkheading pattern
val blockingIoPool: ExecutionContext = ExecutionContext.fromExecutor(
  Executors.newFixedThreadPool(32)
)

def readLargeFileOptimized(): Future[String] = Future {
  scala.io.Source.fromFile("/var/log/huge.log").mkString
}(blockingIoPool)
```

### Kesalahan 3: Membocorkan Mutable State ke Dalam Future Callback di Aktor
Mengakses state internal aktor dari dalam lambda `Future.onComplete` atau `Future.map`.

```scala
// ❌ ANTI-PATTERN: Race condition berbahaya pada state aktor!
class FragileActorBehavior {
  var internalCount = 0

  def onMessage(context: ActorContext[Command]): Behavior[Command] = {
    Behaviors.receiveMessage { _ =>
      someAsyncService.fetch().onComplete {
        case Success(v) => 
          internalCount += 1 // Thread eksternal memodifikasi internal state aktor secara liar!
        case Failure(_) => ()
      }(context.executionContext)
      Behaviors.same
    }
  }
}

// PASANGKAN DENGAN KODE BERIKUT:
// ✅ IDIOMATIK: Gunakan pipeToSelf untuk memasukkan respons ke Mailbox
Behaviors.receive { (context, message) =>
  context.pipeToSelf(someAsyncService.fetch()) {
    case Success(v) => InternalUpdateSuccess(v)
    case Failure(e) => InternalUpdateFailure(e)
  }
  Behaviors.same
}
```

### Kesalahan 4: Mengirimkan Objek Mutable Melalui Pesan Aktor
Mengirim objek yang field-nya dapat diubah (`var` atau koleksi mutable).

```scala
// ❌ ANTI-PATTERN: Thread penerima dan pengirim berbagi pointer yang sama!
case class MutatingPayload(var status: String, items: scala.collection.mutable.ListBuffer[String])

// PASANGKAN DENGAN KODE BERIKUT:
// ✅ IDIOMATIK: Pastikan seluruh struktur data pesan adalah murni Immutable
case class ImmutablePayload(status: String, items: Vector[String])
```

### Kesalahan 5: Ask Pattern Tanpa Penanganan Timeout yang Presisi
Menggunakan nilai timeout acak dan membiarkan timeout melempar failure tanpa fallback.

```scala
// ❌ ANTI-PATTERN: Ask tanpa timeout atau fallback yang jelas
implicit val timeout: Timeout = Timeout(60.seconds) // Terlalu lama!
val response: Future[Reply] = actorRef.ask(ref => Query(ref))

// PASANGKAN DENGAN KODE BERIKUT:
// ✅ IDIOMATIK: Timeout rasional dengan graceful fallback recovery
implicit val timeout: Timeout = Timeout(2.seconds)
val resilientResponse: Future[Reply] = actorRef.ask(ref => Query(ref)).recover {
  case _: TimeoutException => CachedOrFallbackReply
}
```

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Protocol Definition via Typed ADTs**: Definisikan seluruh interaksi pesan aktor menggunakan `sealed trait` atau `enum` (di Scala 3). Letakkan protokol ini tepat di dalam *companion object* dari aktor yang bersangkutan.
2. **Actor Immutability via Pure Functions**: Hindari penggunaan `var` di dalam body aktor jika memungkinkan. Gunakan parameter method `Behavior` rekursif untuk menyimpan state transisional.
3. **Actor Ephemerality (Per-Request Actor Pattern)**: Jangan ragu membuat aktor sementara (*short-lived actors*) yang hanya bertugas menyelesaikan satu transaksi kompleks (misal: agregasi dari 5 API eksternal) dan segera melakukan `Behaviors.stopped` setelah selesai.
4. **Boundary Isolation via Adapters**: Gunakan `context.messageAdapter` untuk menerjemahkan pesan balasan dari aktor eksternal yang memiliki domain berbeda ke dalam tipe pesan yang dipahami oleh domain internal aktor Anda.
5. **Backpressure First**: Selalu asumsikan aktor penerima memiliki batas kemampuan. Jika memproses stream data tinggi, gunakan abstraksi **Pekko Streams** / **Reactive Streams** di atas Actor layer dasar.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Menala ExecutionContext (ForkJoinPool)
Secara default, Scala `ExecutionContext.Implicits.global` menginisialisasi `ForkJoinPool` dengan batas paralelisme setara dengan jumlah core logis mesin (`Runtime.getRuntime.availableProcessors()`).

Untuk tugas CPU-bound:
$$\text{Jumlah Thread Optimal} = N_{\text{CPU}}$$

Untuk tugas I/O-bound (Blocking):
$$\text{Jumlah Thread Optimal} = N_{\text{CPU}} \times \left(1 + \frac{W}{C}\right)$$
Di mana $\frac{W}{C}$ adalah rasio waktu tunggu (*Wait time*) terhadap waktu komputasi (*Compute time*). Jika panggilan HTTP menunggu jaringan selama 90ms dan memproses data selama 10ms, rasio adalah 9. Pada sistem 8 core: $8 \times (1 + 9) = 80$ threads.

### 2. Konfigurasi Pekko Dispatcher Throughput
Di dalam konfigurasi produksi (`application.conf`), lakukan penalaan throughput dispatcher:

```hocon
blocking-io-dispatcher {
  type = Dispatcher
  executor = "thread-pool-executor"
  thread-pool-executor {
    fixed-pool-size = 64
  }
  throughput = 1
}

default-fork-join-dispatcher {
  type = Dispatcher
  executor = "fork-join-executor"
  fork-join-executor {
    parallelism-min = 8
    parallelism-factor = 1.0
    parallelism-max = 64
  }
  # Tingkatkan throughput jika aktor memiliki pesan komputasi ringan
  throughput = 30
}
```

### 3. Mengurangi Alokasi Garbage Collector
* Gunakan Scala 3 `opaque type` atau `extends AnyVal` untuk ID numerik/string agar tidak terjadi *boxing* alokasi objek heap berlebih.
* Hindari penutupan lambda (*closure capture*) yang tidak perlu di jalur panas (*hot path*) pemrosesan pesan.

---

## SEKSI 16 — KEAMANAN & HARDENING

### 1. Antisipasi Mailbox Exhaustion (DoS)
Jika penyerang mengirimkan ribuan request secara simultan ke endpoint HTTP yang memicu pengiriman pesan ke aktor, memori JVM dapat habis seketika.
* **Hardening**: Definisikan konfigurasi bounded mailbox pada aktor pintu gerbang (*entry point*):

```hocon
bounded-mailbox {
  mailbox-type = "org.apache.pekko.dispatch.NonBlockingBoundedMailbox"
  mailbox-capacity = 5000
}
```
Ketika antrean penuh, pesan baru otomatis dialihkan ke `DeadLetters` tanpa menumbangkan memori server.

### 2. Keamanan Serialisasi Pesan (Pekko Remote / Distributed System)
* **Kerentanan**: Penggunaan serialisasi Java bawaan (*Java Serialization*) merupakan sumber kerentanan keamanan tertinggi di ekosistem JVM (*Remote Code Execution - RCE* melalui deserialisasi gadget).
* **Solusi Hardening**:
  Matikan Java Serialization secara permanen di `application.conf`:
  ```hocon
  pekko.actor.allow-java-serialization = off
  pekko.actor.warn-about-java-serializer-usage = on
  ```
  Gunakan **Protocol Buffers (Protobuf)** atau **Jackson/Circe JSON Serializer** bertipe dengan *whitelist manifest* ketat untuk seluruh pesan yang melintasi jaringan.

---

## SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

### 1. Tracing Terdistribusi & MDC (Mapped Diagnostic Context)
Dalam sistem Actor asinkron, thread berganti-ganti secara liar. Standar stack trace tidak lagi berguna untuk melacak jejak request pengguna.

* **Solusi**: Integrasikan Correlation ID menggunakan Pekko MDC Logging:

```scala
val supervisedBehavior = Behaviors.withMdc[OrderCommand](
  staticMdc = Map("system.layer" -> "core-engine"),
  mdcForMessage = (msg: OrderCommand) => Map("tx.id" -> java.util.UUID.randomUUID().toString)
) {
  OrderProcessorActor()
}
```

### 2. Memantau Dead Letters
Setiap pesan yang dikirimkan ke aktor yang sudah mati atau ter-drop dari bounded mailbox akan berakhir di saluran khusus: `DeadLetter`. Memonitor stream ini adalah kunci utama mendeteksi kebocoran logika arsitektur.

```scala
val deadLetterSubscriber: ActorRef[org.apache.pekko.actor.DeadLetter] = 
  context.spawn(Behaviors.receiveMessage { dl =>
    context.log.warn(s"[DeadLetter Terdeteksi] Pesan: ${dl.message} dari ${dl.sender} ke ${dl.recipient}")
    Behaviors.same
  }, "DeadLetterMonitor")

context.system.eventStream.tell(
  org.apache.pekko.actor.typed.eventstream.EventStream.Subscribe(deadLetterSubscriber)
)
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

### Perbandingan Cepat Pola Desain Konkurensi

| Use Case | Pendekatan Terbaik | Contoh Pola |
| :--- | :--- | :--- |
| Transformasi data non-blocking independen | `scala.concurrent.Future` | `futureA.zip(futureB).map(...)` |
| Operasi I/O Sinkron/Blocking | Dedicated `ExecutionContext` | `Future { jdbcCall() }(blockingIoEc)` |
| Komponen dengan status privat (*stateful*) | Typed Actor (`Behavior[T]`) | `Behaviors.receiveMessage { ... }` |
| Komunikasi 1-arah (Performa maksimum) | Tell Pattern | `actorRef ! Command` |
| Komunikasi butuh jawaban (*Request-Response*) | Ask Pattern | `actorRef.ask(ref => Cmd(ref))` |
| Integrasi Future ke dalam Actor | Thread-Safe Ingestion | `context.pipeToSelf(future)(toMsg)` |

### Syntax Cheat Sheet Pekko / Akka Typed
* **Membuat Behavior Statis**: `Behaviors.receiveMessage[Command] { msg => ... Behaviors.same }`
* **Membuat Behavior Stateful (FP)**: 
  ```scala
  def active(state: Int): Behavior[Command] = Behaviors.receiveMessage {
    case Next => active(state + 1)
  }
  ```
* **Supervisi**: `Behaviors.supervise(behavior).onFailure[Exception](SupervisorStrategy.restart)`
* **Pemberhentian Diri**: `Behaviors.stopped`

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Dasar (Basic)

1. **Apa perbedaan mendasar antara model thread bawaan JVM dan Actor Model dalam hal proteksi state?**
   * A. Actor Model menggunakan distributed database lock, thread JVM menggunakan memory lock.
   * B. Actor Model mengisolasi state sepenuhnya di dalam mailbox dan memproses pesan berurutan sehingga tidak butuh lock, sedangkan Thread JVM berbagi akses heap memory secara bersamaan dan memerlukan lock.
   * C. Thread JVM lebih cepat karena tidak ada antrean pesan, sedangkan Actor Model tidak mendukung eksekusi paralel.
   * D. Actor Model hanya dapat berjalan di satu core CPU secara single-threaded.

2. **Apa yang terjadi secara internal jika Anda memanggil `Await.result(future, 10.seconds)`?**
   * A. Future dipaksa selesai seketika dengan mengeksekusi komputasi pada thread pemanggil.
   * B. Thread pemanggil dialihkan statusnya menjadi *BLOCKED/WAITING* dan tidak dapat melakukan pekerjaan lain hingga Future selesai atau waktu timeout habis.
   * C. Kompilator mengubah kode menjadi pemanggilan asinkron non-blocking otomatis.
   * D. Thread pemanggil langsung melempar `TimeoutException` tanpa menunggu.

3. **Mengapa `Future.sequence` sangat krusial dalam orkestrasi asinkron di Scala?**
   * A. Untuk mengubah `List[Future[A]]` menjadi `Future[List[A]]` secara non-blocking.
   * B. Untuk memastikan Future dieksekusi secara sekuensial satu per satu di thread yang sama.
   * C. Untuk membatalkan seluruh Future jika ada satu Future yang lambat.
   * D. Untuk mengurutkan elemen list berdasarkan waktu eksekusi.

4. **Dalam Typed Actor, apakah diizinkan bagi Thread eksternal untuk mengakses nilai field variabel aktor secara langsung?**
   * A. Diizinkan asalkan field tersebut diberi anotasi `@volatile`.
   * B. Diizinkan jika menggunakan refleksi Java.
   * C. Tidak dapat dilakukan karena `ActorRef` tidak mengekspos instans class aktor internal, melainkan hanya saluran pengiriman pesan.
   * D. Diizinkan selama aktor berada dalam satu node JVM yang sama.

5. **Apa fungsi utama dari `SupervisorStrategy.restart` pada aktor anak yang mengalami fatal exception?**
   * A. Mematikan ActorSystem secara keseluruhan demi keamanan.
   * B. Mengabaikan error dan memproses pesan berikutnya menggunakan state yang sama saat crash terjadi.
   * C. Membuat ulang instans state aktor dari state awal yang bersih tanpa mengorbankan pesan lain yang belum diproses di Mailbox.
   * D. Meneruskan exception ke thread pool utama JVM.

---

### Soal Tingkat Menengah (Intermediate)

6. **Perhatikan cuplikan kode berikut:**
   ```scala
   val f1 = Future { Thread.sleep(2000); 10 }
   val f2 = Future { Thread.sleep(2000); 20 }
   val result = for {
     a <- f1
     b <- f2
   } yield a + b
   ```
   **Berapa estimasi total waktu eksekusi kode di atas jika pool memiliki thread mencukupi?**
   * A. 4 detik karena for-comprehension mengeksekusi Future secara sekuensial.
   * B. 2 detik karena inisiasi `f1` dan `f2` dilakukan di luar for-comprehension sehingga keduanya berjalan secara paralel sebelum di-kombinasikan.
   * C. 0 detik karena komputasi langsung diabaikan.
   * D. Mengalami kompilasi error karena `Thread.sleep` tidak diizinkan di dalam Future.

7. **Apa bahaya terbesar memanggil `context.pipeToSelf` dibandingkan langsung mendaftarkan callback `future.onComplete` di dalam aktor?**
   * A. `context.pipeToSelf` tidak thread-safe.
   * B. `future.onComplete` justru berbahaya karena mengeksekusi closure di thread eksternal yang dapat mengakses dan merusak state aktor secara konkuren, sedangkan `pipeToSelf` mengubah hasil menjadi pesan yang masuk secara aman ke Mailbox aktor.
   * C. `context.pipeToSelf` memakan memori 10x lipat lebih besar.
   * D. Tidak ada perbedaan sama sekali di level JVM.

8. **Jika throughput dispatcher sebuah Actor di-set ke nilai 1, apa implikasi performanya?**
   * A. Sistem akan crash karena throughput minimum adalah 10.
   * B. Aktor hanya akan memproses 1 pesan sebelum thread-nya dilepas kembali ke pool, menghasilkan *fairness* pembagian thread yang sangat merata antar aktor, namun memiliki overhead *context switching* yang lebih tinggi.
   * C. Mailbox aktor hanya dapat menampung tepat 1 pesan.
   * D. Seluruh ActorSystem dipaksa berjalan di 1 thread OS saja.

9. **Manakah dari strategi berikut yang paling aman untuk mencegah degradasi performa (*thread starvation*) pada ActorSystem ketika integrasi dengan database relasional (JDBC) sinkron harus dilakukan?**
   * A. Menambahkan keyword `synchronized` di seluruh method pemanggilan database.
   * B. Membungkus panggilan JDBC dalam `Future` yang menggunakan thread pool khusus (*Dedicated ThreadPoolExecutor/Dispatcher*) yang terisolasi dari pool utama ActorSystem.
   * C. Menaikkan nilai timeout transaksi database menjadi tak hingga.
   * D. Memanggil JDBC secara langsung di dalam method `receiveMessage` aktor utama.

10. **Bagaimana pola "Ask" (`?`) Typed Actor mencegah memory leak jika aktor target tidak pernah merespons pesan?**
    * A. Ask pattern tidak dapat mencegah memory leak secara otomatis.
    * B. Melalui parameter implisit/eksplisit `Timeout`; sistem mendaftarkan scheduler timer yang secara otomatis menggagalkan Promise internal dengan `TimeoutException` saat batas waktu tercapai.
    * C. Dengan mematikan aktor pemanggil secara paksa.
    * D. Dengan menghapus pesan dari mailbox aktor penerima.

---

### Kunci Jawaban & Pembahasan

1. **Jawaban: B**. Prinsip utama Actor Model adalah *share nothing*. Komunikasi dilakukan via *message passing* ke mailbox aktor yang diproses secara berurutan (*single-threaded execution illusion*), menghapus kebutuhan akan lock.
2. **Jawaban: B**. `Await.result` adalah anti-pattern sinkron yang memarkir thread pemanggil secara preemptive hingga batas waktu durasi tercapai, menyia-nyiakan alokasi sumber daya CPU thread pool.
3. **Jawaban: A**. `Future.sequence` mengubah struktur tipe koleksi `F[Future[T]]` menjadi `Future[F[T]]` secara non-blocking menggunakan rekursi monadic atau `Promise`.
4. **Jawaban: C**. Arsitektur Typed Actor membungkus instance class di balik `ActorRef[T]`. Tidak ada method accessor langsung yang terbuka ke publik; interaksi mutlak harus melalui pengiriman pesan envelope.
5. **Jawaban: C**. Kebijakan restart membersihkan error state yang korup, menginisialisasi ulang aktor ke state fresh, namun membiarkan mailbox yang tersisa tetap utuh untuk dilanjutkan pemrosesannya.
6. **Jawaban: B**. Variabel `f1` dan `f2` dievaluasi saat baris deklarasi dijalankan (*eager evaluation*), sehingga kedua future telah berjalan secara simultan pada background pool. For-comprehension hanya menyatukan hasilnya (sekitar 2 detik total).
7. **Jawaban: B**. Mengeksekusi mutasi atau pemanggilan di dalam `onComplete` secara langsung melanggar batas isolasi memori thread aktor karena callback tersebut dieksekusi oleh thread pool non-deterministik. `pipeToSelf` adalah satu-satunya mekanisme aman untuk mengubah Future result menjadi command resmi aktor.
8. **Jawaban: B**. Nilai throughput mengatur batas batching pengurasan antrean mailbox sebelum dispatcher menyerahkan worker thread ke aktor berikutnya di pool. Nilai 1 memberikan derajat *fairness* maksimal dengan trade-off biaya pertukaran thread context.
9. **Jawaban: B**. Arsitektur Bulkheading memisahkan eksekutor thread. Jika 64 worker thread pada I/O pool terblokir menunggu response JDBC, `ForkJoinPool` utama milik Actor System tetap berputar lancar tanpa hambatan sedikit pun.
10. **Jawaban: B**. Setiap kali Ask pattern dipanggil, sebuah objek `Promise` sementara dibuat dan dihubungkan ke `HashedWheelTimer` / `Scheduler`. Jika aktor target bungkam hingga batas durasi terlewati, scheduler melengkapi promise dengan status failure untuk mereklamasi resource memori.

---

## SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Proyek: "Asynchronous IoT Telemetry Ingestion Hub"

### Spesifikasi Teknis:
Bangun sistem backend berkinerja tinggi menggunakan **Scala 3** dan **Apache Pekko Typed** untuk mencerna metrik sensor suhu dari ribuan perangkat IoT dengan kriteria:

1. **Protocol Definition**:
   * Definisikan pesan IoT: `RecordTemperature(deviceId: String, value: Double, timestamp: Long)`.
   * Definisikan pesan kueri: `GetDeviceStatistics(deviceId: String, replyTo: ActorRef[DeviceStats])`.
   * Definisikan data event respons: `DeviceStats(deviceId: String, totalReadings: Int, averageTemp: Double)`.

2. **Hierarki Aktor**:
   * **DeviceGroupManager (Supervisor)**: Mengelola child actors secara dinamis. Jika pesan untuk `deviceId` tertentu pertama kali masuk, spawn aktor anak baru bertipe `DeviceTrackerActor`.
   * **DeviceTrackerActor (Worker)**: Menyimpan state akumulasi pembacaan suhu perangkat tersebut (menggunakan FP functional-state tanpa `var`).
   * Terapkan batas toleransi: Jika suhu membaca nilai di atas 100.0 derajat Celsius, simulasikan kegagalan transien (`SensorOverheatException`) dan terapkan **Restart Supervision Strategy** yang menjaga metrik terakhir tetap utuh atau me-reset state secara aman.

3. **Integrasi Asinkron & Pipeline**:
   * Buat service `AlertNotificationService` yang memiliki fungsi `sendEmergencyAlert(deviceId: String): Future[Boolean]`.
   * Jika suhu rata-rata melebihi 75.0 derajat, gunakan `context.pipeToSelf` untuk memanggil fungsi alert tersebut secara asinkron tanpa memblokir thread aktor.

4. **Validasi & Pengujian**:
   * Buat test suite atau runnable script yang mengalirkan 10.000 pesan data pembacaan sensor acak secara konkuren menggunakan `Future.traverse`.
   * Validasi bahwa tidak ada memory starvation dan seluruh query `GetDeviceStatistics` mengembalikan rata-rata statistik yang tepat secara deterministik.