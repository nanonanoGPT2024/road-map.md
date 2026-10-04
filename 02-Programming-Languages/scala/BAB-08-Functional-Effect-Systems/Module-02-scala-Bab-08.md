# BAB 08: Functional Effect Systems
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Runtime & Threading Engine:** Menguraikan arsitektur internal run-loop fiber (Cats Effect 3 `IOFiber` dan ZIO 2 `FiberRuntime`), *cooperative multithreading*, algoritma *work-stealing pool*, serta implikasinya terhadap garbage collection (GC) dan cache locality CPU (L1/L2/L3).
2. **Menguasai Semantik Pembatalan & Resource Safety:** Mengimplementasikan pola alokasi sumber daya aman (*bracket pattern*, `Resource`, `Scope`) serta mengendalikan fase pembatalan (*cooperative cancellation*, *masked regions*, dan *polling*) untuk mencegah kebocoran koneksi atau korupsi state transaksi.
3. **Membangun Primitif Konkurensi Lanjutan:** Merekayasa struktur data konkurensi non-blocking tingkat tinggi berbasis atomic references (`Ref`), sinkronisasi thread murni (`Deferred`, `Promise`), koordinasi multi-fiber (`Semaphore`, `CountDownLatch`), dan *Software Transactional Memory* (STM).
4. **Mendesain Arsitektur Produksi Skala Enterprise:** Merancang pipeline streaming data berbasis efek (*backpressured streams*) yang terintegrasi dengan *Circuit Breaker*, *Distributed Tracing* (OpenTelemetry), dan *Rate Limiter* adaptif untuk beban throughput tinggi (>50.000 ops/detik).
5. **Melakukan Diagnostik, Profiling & Troubleshooting:** Mengidentifikasi dan memitigasi thread starvation, *async boundary misuse*, kebocoran memori fiber, dan *unbounded queue explosion* menggunakan JDK Flight Recorder (JFR) dan dump metrik runtime.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:

* **Scala 3 Fundamentals:** Metaprogramming dasar, *contextual abstractions* (`given`, `using`), extension methods, dan *opaque types*.
* **Functional Programming Primitives:** Kategori Monad, Functor, Applicative, MonadError, serta konsep *referential transparency* dan substitusi ekspresi.
* **Basic Functional Effects:** Memahami bab sebelumnya (Module 01) mengenai tipe data dasar `IO[A]` / `ZIO[R, E, A]`, pergeseran eksekusi dari evaluasi langsung (*eager*) ke deskripsi program (*lazy blueprint*).
* **JVM Concurrency:** Memori model JVM (JMM), instruksi hardware CAS (*Compare-And-Swap*), status thread OS vs thread virtual, dan *cost of context switching*.
* **Environment Tooling:**
  * Scala: `3.3.3 LTS` atau lebih baru
  * SBT: `1.9.9` atau lebih baru
  * JDK: GraalVM Enterprise / Eclipse Temurin `JDK 21 LTS` (mendukung JVM Flag analisis canggih)
  * Library Target: Cats Effect `3.5.4`, FS2 `3.10.2`, Cats `2.10.0` (opsional: ZIO `2.0.21`)

---

### 3. Concept & Internal Architecture

Sistem *functional effect* modern (Cats Effect 3 dan ZIO 2) bertindak sebagai runtime komputasi konkuren di atas JVM, memisahkan logika aplikasi murni dari detail alokasi thread OS melalui abstraksi **Fiber (Green Thread / Virtual Thread Fungsional)**.

```
+-------------------------------------------------------------------------------+
|                             KODE APLIKASI (IO/ZIO)                            |
|             Deskripsi deklaratif murni (Functional Composition Tree)          |
+-------------------------------------------------------------------------------+
                                        | (FlatMap / Async Boundary)
                                        v
+-------------------------------------------------------------------------------+
|                            RUNTIME ENGINE (IOFiber)                           |
|  +-------------------------+  +---------------------------------------------+  |
|  | Run-Loop State Machine  |  | Cancellation & Finalization Stack            |  |
|  | - Evaluasi byte-code    |  | - Masked regions (uncancelable)             |  |
|  | - Object unboxing       |  | - Unmasked polling triggers                 |  |
|  | - Auto-yielding counter |  | - LIFO Finalizer execution                  |  |
|  +-------------------------+  +---------------------------------------------+  |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                        WORK-STEALING THREAD POOL (WSTP)                       |
|                                                                               |
|  Worker Thread 1              Worker Thread 2              Worker Thread N    |
|  +-------------------------+  +-------------------------+  +----------------+ |
|  | Local FIFO/LIFO Deque   |  | Local FIFO/LIFO Deque   |  | Local Deque    | |
|  | [FiberA][FiberB]        |  | [FiberC]                |  | (Empty)        | |
|  +-------------------------+  +-------------------------+  +----------------+ |
|               ^                            ^                       |          |
|               |                            | Steal                 | Steal    |
|               +----------------------------+-----------------------+          |
|                                                                               |
|  +--------------------------------------------------------------------------+ |
|  | Global Overflow/Blocking Queue (Polled periodically via epoch ticks)    | |
|  +--------------------------------------------------------------------------+ |
+-------------------------------------------------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                             OPERATING SYSTEM THREADS                          |
|                  Kernel Threads (pthreads) / Hardware SMT Cores               |
+-------------------------------------------------------------------------------+
```

#### 3.1. Struktur IOFiber dan Run-Loop Engine

Sebuah Fiber bukan thread kernel OS. Fiber adalah objek Java biasa yang diinstansiasi di Heap (berukuran rata-rata ~150 byte saat idle) yang menyimpan status eksekusi.

1. **The Run-Loop:** Jantung dari runtime adalah *while loop* berkecepatan tinggi yang terus melakukan iterasi pada rantai transformasi monadik (`flatMap`, `map`, `handleErrorWith`). Run-loop mengonsumsi alur program tanpa membengkakkan call-stack native JVM via teknik *trampolining*.
2. **Auto-Yielding (Fair Scheduling):** Untuk mencegah satu fiber memonopoli CPU (*starvation*), runtime menyertakan generator batch counter (secara default di CE3 bernilai 1024 iterasi). Setelah 1024 `flatMap` dieksekusi secara berurutan, fiber secara otomatis memanggil mekanisme internal `cede`. Fiber akan menyerahkan thread yang digunakannya, memarkir dirinya ke antrean lokal, dan memberi giliran pada fiber lain.
3. **Suspension & Resumption:** Saat fiber menunggu operasi I/O asinkron (misalnya soket TCP non-blocking via Netty/Epoll), fiber tersebut mencopot referensi dirinya dari run-loop (*suspended*) dan mendaftarkan sebuah *callback*. Thread kernel bebas mengeksekusi fiber lain. Saat I/O tuntas, callback memasukkan kembali fiber yang terjeda ke dalam work-stealing deque.

#### 3.2. Work-Stealing Runtime Internals

Work-Stealing Thread Pool (WSTP) Cats Effect 3 dirancang khusus untuk meminimalkan lock contention pada throughput tinggi:

* **Struktur Deque Lokal (Local Queue):** Setiap worker thread mengelola ring-buffer lokal berkapasitas tetap (misal, 256 slot) yang diakses tanpa lock oleh worker pemilik (*single-producer, single-consumer* logic untuk push/pop head).
* **Work Stealing Mechanism:** Jika worker thread kehabisan task pada deque lokalnya, ia bertindak sebagai *thief* (pencuri). Ia memilih worker acak lain (*victim*) dan mengambil setengah dari antrean fiber milik victim dari ujung ekor (*tail*) menggunakan instruksi Atomic CAS.
* **Cache Line Padding:** Struktur internal antrean menyertakan *padding* 64 byte guna menghindari fenomena *false sharing* di CPU L1 Cache antar core prosesor.

#### 3.3. Structured Concurrency & Cancellation Mechanics

Cancellation pada functional effect bersifat **cooperative** (kooperatif), bukan preemptive thread killing (`Thread.stop()` yang berbahaya). 

* **Cancelation Token:** Pembatalan menandai atomik state fiber menjadi `Canceled`. Run-loop memeriksa flag ini pada titik suspensi asinkron atau saat evaluasi `cede`.
* **Masking (`uncancelable`):** Wilayah eksekusi dapat diproteksi dari interupsi menggunakan `IO.uncancelable`. Ini krusial ketika mengalokasikan resources, seperti membuka koneksi DB dan mendaftarkannya ke connection pool.
* **Polling:** Di dalam blok uncancelable, fungsi `poll` dapat digunakan untuk membuka kembali interupsi secara selektif pada bagian kode yang aman untuk dibatalkan (misalnya saat menunggu transmisi payload jaringan).

---

### 4. Why & What

#### Mengapa Tidak Menggunakan Java Virtual Threads (Project Loom) Saja?
Dengan hadirnya Java 21 Virtual Threads, muncul pertanyaan: *Apakah kita masih membutuhkan functional effect systems seperti Cats Effect atau ZIO?*

| Parameter | Project Loom (Virtual Threads) | Functional Effect Systems (CE3 / ZIO 2) |
| :--- | :--- | :--- |
| **Model Paradigma** | Imperatif, berbasis *thread blocking* ilusi | Deklaratif, referentially transparent, berbasis ekspresi |
| **Resource Safety** | Mengandalkan `try-finally` imperatif (rawan human error) | Tipe data `Resource` / `Scope` menjamin finalisasi bahkan saat OOM/interupsi mendadak |
| **Cancellation** | Menggunakan `Thread.interrupt()` bawaan Java yang rapuh dan sering diabaikan pihak ketiga | Interupsi deterministik kooperatif; menjamin pembersihan pohon relasi fiber (*structured*) |
| **Context Propagation**| `ScopedValue` / `ThreadLocal` (rawan memory leak) | FiberRef / ZEnvironment bertipe statis (*compile-time safe*) |
| **Tracing & Testing** | Non-deterministik, mengandalkan mocking thread manual | `TestControl` runtime memungkinkan manipulasi waktu (*virtual time travel*) instan |

Loom menyelesaikan problem thread scalability pada level OS, namun **tidak menyelesaikan** problem kebenaran konkurensi (*structured concurrency, resource leakage, composability, and error channels*). Functional effect systems beroperasi pada level abstraksi yang lebih tinggi.

---

### 5. How (Workflow detail)

Implementasi alur eksekusi asinkron dan terproteksi mengikuti siklus berikut:

1. **Fiber Allocation:** Eksekusi diinisialisasi melalui pemanggilan runtime `unsafeRunSync` atau `IOApp.run`. Runtime mengemas ekspresi root ke dalam `IOFiber`.
2. **Scheduling:** Fiber dimasukkan ke deque lokal salah satu thread komputasi aktif.
3. **Execution & Run-Loop:**
   * Run-loop membaca instruksi berikutnya.
   * Jika tipe instruksi adalah `FlatMap`, stack modifikasi diperbarui.
   * Jika counter batch menyentuh batas (1024), runtime mengeksekusi *cooperative yield* (`cede`).
4. **Entering Critical Sections:**
   * Aplikasi masuk ke blok `IO.uncancelable`.
   * Flag cancellation internal dimatikan sementara untuk thread ini.
   * Resource diakuisisi (misal: handle file, koneksi socket).
   * Alur dialihkan ke mode terproteksi, lalu registrasi finalizer (release logic) dipush ke stack finalizer fiber.
5. **Interrupt Triggered:**
   * Jika fiber anak menerima sinyal `.cancel`, runtime memeriksa status `uncancelable`.
   * Jika sedang di-mask, status cancel di-buffer.
   * Begitu eksekusi keluar dari mask atau menyentuh `poll`, run-loop segera menghentikan rantai evaluasi normal dan secara deterministik menjalankan seluruh finalizer dari stack secara terbalik (LIFO - *Last In First Out*).

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional Ultra-Modern
* **OS Kernel Threads:** Landasan pacu (*Runway*) berukuran besar dan jumlahnya terbatas (misal 16 landasan pacu sesuai core CPU). Membangun landasan baru sangat mahal.
* **Fibers:** Pesawat-pesawat nirawak (*drone/light aircraft*) super ringan berjumlah jutaan.
* **Run-Loop Scheduler (Air Traffic Control):** Mengatur pesawat mana yang boleh lepas landas di landasan mana. Jika satu drone terbang terlalu lama, ia diperintahkan berputar sejenak (*yielding*) agar drone lain mendapat jatah landing.
* **Resource Leaks Prevention:** Jika sebuah drone kehabisan bahan bakar di udara (mengalami `Cancel`), ATC secara otomatis mengaktifkan parasut darurat (`Finalizer`) agar drone mendarat mulus di hanggar dan suku cadangnya langsung masuk inventaris kembali tanpa membakar hanggar tersebut.

#### Diagram: Work-Stealing Algorithm Internal Mechanics

```
 [ WORKER 1 (Core 1) ]             [ WORKER 2 (Core 2) ]
 +---------------------+           +---------------------+
 | Current: Fiber-101  |           | Current: Fiber-204  |
 +---------------------+           +---------------------+
 | LOCAL DEQUE (Fixed) |           | LOCAL DEQUE (Fixed) |
 | Top -> [Fiber-102]  |           |                     |
 |        [Fiber-103]  |           | (EMPTY)             |
 |        [Fiber-104]  |           |                     |
 | Tail-> [Fiber-105]  |           +---------------------+
 +---------------------+                      |
           ^                                  | 1. Worker 2 kehabisan kerjaan.
           |                                  | 2. Menjadi Thief.
           +======= CAS STEAL HALF ===========+ 3. Mencuri Fiber-104 & Fiber-105
                   (Dari ujung Tail)             secara non-blocking!
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Demonstrasi Uncancelable & Masking Semantics (Scala 3 + Cats Effect 3)

```scala
// file: SimpleCancellationMasking.scala
package com.enterprise.effects.simple

import cats.effect.{IO, IOApp, ExitCode}
import scala.concurrent.duration.*

object SimpleCancellationMasking extends IOApp.Simple:

  def acquireResource(id: String): IO[Unit] =
    IO.println(s"[ACQUIRE] Membuka resource: $id").void

  def releaseResource(id: String): IO[Unit] =
    IO.println(s"[RELEASE] Menutup resource secara aman: $id").void

  def simulateHeavyTask: IO[Unit] =
    IO.println("[TASK] Sedang memproses data penting...") >>
      IO.sleep(3.seconds) >>
      IO.println("[TASK] Pemrosesan selesai.")

  val criticalLifecycle: IO[Unit] =
    IO.uncancelable { poll =>
      for
        _ <- acquireResource("Database-Conn-01")
        // poll memungkinkan pembatalan HANYA terjadi di dalam blok IO.sleep/heavy task
        _ <- poll(simulateHeavyTask).onCancel(
               IO.println("[WARN] Deteksi pembatalan pada saat heavy task!")
             )
        _ <- releaseResource("Database-Conn-01")
      yield ()
    }

  val run: IO[Unit] =
    for
      fiber <- criticalLifecycle.start
      _     <- IO.sleep(1.second) // Biarkan berjalan sejenak
      _     <- IO.println("[MAIN] Mengirim interupsi cancel ke worker fiber...")
      _     <- fiber.cancel
      _     <- fiber.join // Pastikan menunggu cleanup tuntas
      _     <- IO.println("[MAIN] Alur program selesai secara deterministik.")
    yield ()
```

#### 7.2. Practical Example: Implementasi Non-Blocking Async Connection Pool Menggunakan `Ref` dan `Deferred`

Contoh ini menunjukkan pembuatan primitif konkurensi kelas produksi tanpa menggunakan library pool eksternal. Murni menggunakan kontrol fiber, atomik, dan sinkronisasi fungsional.

```scala
// file: NonBlockingResourcePool.scala
package com.enterprise.effects.practical

import cats.effect.*
import cats.effect.std.Supervisor
import cats.syntax.all.*
import scala.collection.immutable.Queue

trait ManagedConnection:
  def query(sql: String): IO[String]
  def close(): IO[Unit]

final class MockDatabaseConnection(val id: Int) extends ManagedConnection:
  override def query(sql: String): IO[String] =
    IO.sleep(scala.concurrent.duration.DurationInt(50).millis) *> 
      IO.pure(s"Query [$sql] sukses dieksekusi oleh worker conn #$id")

  override def close(): IO[Unit] = 
    IO.println(s"[PHYSICAL CLOSED] Koneksi #$id ditutup.")

sealed trait PoolState
object PoolState:
  case class Active(
    available: Queue[ManagedConnection], 
    waiting: Queue[Deferred[IO, ManagedConnection]]
  ) extends PoolState
  case object Closed extends PoolState

final class BoundedConnectionPool private (
  state: Ref[IO, PoolState],
  maxSize: Int
):

  def acquire: IO[ManagedConnection] =
    Deferred[IO, ManagedConnection].flatMap { promise =>
      state.modify {
        case PoolState.Closed =>
          (PoolState.Closed, IO.raiseError[ManagedConnection](new IllegalStateException("Pool sudah ditutup!")))
        
        case PoolState.Active(available, waiting) =>
          available.dequeueOption match
            case Some((conn, remaining)) =>
              (PoolState.Active(remaining, waiting), IO.pure(conn))
            case None =>
              // Tidak ada koneksi siap pakai, pemanggil harus suspend secara non-blocking
              (PoolState.Active(Queue.empty, waiting.enqueue(promise)), promise.get)
      }.flatten
    }

  def release(conn: ManagedConnection): IO[Unit] =
    state.modify {
      case PoolState.Closed =>
        // Jika pool sudah ditutup, koneksi yang dikembalikan langsung dihancurkan
        (PoolState.Closed, conn.close())
      
      case PoolState.Active(available, waiting) =>
        waiting.dequeueOption match
          case Some((earliestWaitingConsumer, remainingWaiters)) =>
            // Berikan koneksi langsung ke fiber yang paling awal menunggu (FIFO)
            (PoolState.Active(available, remainingWaiters), earliestWaitingConsumer.complete(conn).void)
          case None =>
            // Tidak ada yang menunggu, kembalikan ke antrean sedia
            (PoolState.Active(available.enqueue(conn), Queue.empty), IO.unit)
    }.flatten

  def use[A](f: ManagedConnection => IO[A]): IO[A] =
    Resource.make(acquire)(release).use(f)

  def shutdown(): IO[Unit] =
    state.modify {
      case PoolState.Closed => (PoolState.Closed, IO.unit)
      case PoolState.Active(available, waiting) =>
        val drainWaiters = waiting.toList.traverse(_.complete(null).void)
        val closeConnections = available.toList.traverse(_.close()).void
        (PoolState.Closed, drainWaiters *> closeConnections)
    }.flatten

object BoundedConnectionPool:
  def create(size: Int): Resource[IO, BoundedConnectionPool] =
    val initConnections = (1 to size).toList.traverse(id => IO.pure(new MockDatabaseConnection(id)))
    Resource.make {
      for
        conns <- initConnections
        ref   <- Ref.of[IO, PoolState](PoolState.Active(Queue.from(conns), Queue.empty))
      yield new BoundedConnectionPool(ref, size)
    }(_.shutdown())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Real-Time Payment Ingestion & Circuit-Breaking Settlement Engine
Sebuah payment switch gateway memproses order settlement dengan SLA ketat (maksimal p99 < 80ms). Layanan ini harus menangani lonjakan transaksi (bursting), menerapkan *Adaptive Rate Limiting*, serta *Circuit Breaking* secara non-blocking murni dengan proteksi backpressure.

```scala
// file: EnterprisePaymentIngestion.scala
package com.enterprise.effects.casestudy

import cats.effect.*
import cats.effect.std.{Queue, Supervisor}
import cats.syntax.all.*
import java.time.Instant
import scala.concurrent.duration.*

case class PaymentCommand(id: String, amountUsd: BigDecimal, merchantId: String)
case class SettlementResult(paymentId: String, status: String, processedAt: Instant)

sealed trait CircuitState
object CircuitState:
  case object Closed extends CircuitState
  case class Open(openedAt: Long) extends CircuitState
  case object HalfOpen extends CircuitState

final class EffectfulCircuitBreaker(
  state: Ref[IO, CircuitState],
  failureCount: Ref[IO, Int],
  threshold: Int,
  resetTimeout: FiniteDuration
):
  def protect[A](action: IO[A]): IO[A] =
    Clock[IO].realTime.map(_.toMillis).flatMap { now =>
      state.get.flatMap {
        case CircuitState.Open(openedAt) if (now - openedAt) > resetTimeout.toMillis =>
          state.set(CircuitState.HalfOpen) *> executeAction(action, isTrial = true)
        case CircuitState.Open(_) =>
          IO.raiseError(new RuntimeException("CIRCUIT_BREAKER_OPEN: Service down. Permintaan ditolak langsung."))
        case _ =>
          executeAction(action, isTrial = false)
      }
    }

  private def executeAction[A](action: IO[A], isTrial: Boolean): IO[A] =
    action.attempt.flatMap {
      case Right(success) =>
        failureCount.set(0) *> state.set(CircuitState.Closed).as(success)
      case Left(error) =>
        failureCount.updateAndGet(_ + 1).flatMap { count =>
          if (count >= threshold || isTrial)
            Clock[IO].realTime.map(_.toMillis).flatMap(now => state.set(CircuitState.Open(now))) *> IO.raiseError(error)
          else
            IO.raiseError(error)
        }
    }

object EffectfulCircuitBreaker:
  def create(threshold: Int, timeout: FiniteDuration): IO[EffectfulCircuitBreaker] =
    for
      s <- Ref.of[IO, CircuitState](CircuitState.Closed)
      f <- Ref.of[IO, Int](0)
    yield new EffectfulCircuitBreaker(s, f, threshold, timeout)

final class PaymentPipeline(
  inboundQueue: Queue[IO, PaymentCommand],
  outboundQueue: Queue[IO, SettlementResult],
  breaker: EffectfulCircuitBreaker
):
  private def callThirdPartyBankApi(cmd: PaymentCommand): IO[SettlementResult] =
    IO.sleep(40.millis) *> {
      if (cmd.id.endsWith("99")) // Simulasi kegagalan acak untuk testing resiliency
        IO.raiseError(new RuntimeException(s"Jaringan bank time-out untuk ID: ${cmd.id}"))
      else
        IO.pure(SettlementResult(cmd.id, "SUCCESS", Instant.now()))
    }

  def startWorker(workerId: Int): IO[Unit] =
    val processSingleItem: IO[Unit] =
      inboundQueue.take.flatMap { command =>
        val execution = breaker.protect(callThirdPartyBankApi(command))
          .handleErrorWith { err =>
            IO.println(s"[WORKER $workerId][FALLBACK] Pembayaran ${command.id} gagal: ${err.getMessage}") *>
              IO.pure(SettlementResult(command.id, "REJECTED_BY_CIRCUIT", Instant.now()))
          }

        execution.flatMap(outboundQueue.offer).void
      }

    processSingleItem.foreverM

object EnterprisePaymentApp extends IOApp.Simple:
  val run: IO[Unit] =
    Supervisor[IO].use { supervisor =>
      for
        inbound  <- Queue.bounded[IO, PaymentCommand](10000)
        outbound <- Queue.bounded[IO, SettlementResult](10000)
        breaker  <- EffectfulCircuitBreaker.create(threshold = 5, resetTimeout = 2.seconds)
        pipeline = new PaymentPipeline(inbound, outbound, breaker)

        // Spawn 8 worker fibers (concurrency pool)
        _ <- (1 to 8).toList.traverse { id =>
          supervisor.supervise(pipeline.startWorker(id))
        }

        // Simulasikan Ingestion Stream (Producer)
        producerFiber <- (1 to 200).toList.traverse { idx =>
          val cmd = PaymentCommand(s"TX-$idx", BigDecimal(100.0), "MERC-88")
          inbound.offer(cmd)
        }.start

        // Monitor Outbound Result
        consumerFiber <- (1 to 200).toList.traverse { _ =>
          outbound.take.flatMap { res =>
            IO.println(s"[SETTLEMENT] Result: ${res.paymentId} -> ${res.status}")
          }
        }.start

        _ <- producerFiber.join
        _ <- consumerFiber.join
        _ <- IO.println("[SYSTEM] Seluruh transaksi ingestion berhasil dieksekusi secara terisolasi.")
      yield ()
    }
```

---

### 9. Trade-offs

| Dimensi | Pendekatan Pure Functional Effect (Cats Effect/ZIO) | Pendekatan Imperatif / Future / Loom Direct |
| :--- | :--- | :--- |
| **Performance Overhead** | Sedikit penalti alokasi objek monadic wrapper di JVM Eden Space (~5-8% vs direct byte manipulation). | Zero monadic wrapper overhead. Hampir mendekati performa raw bare-metal threads. |
| **Latency & Jitter** | Ekstrem konsisten pada tail latency (p99/p99.9). Algoritma WSTP mencegah monopolasi thread runtime oleh rogue task. | Jitter tak terprediksi jika developer membungkus operasi blocking di dalam thread pool komputasi umum. |
| **Debuggability** | Membutuhkan tracing stack runtime khusus (Async Stack Trace/Trace capture) karena native JVM stack trace terpotong trampolining. | Native JVM Thread Dump langsung memperlihatkan alur baris kode secara linear (kompatibel langsung dengan APM lawas). |
| **Cognitive Load** | Curam. Developer wajib menguasai type system tingkat lanjut, variance, aljabar kategori, dan pemisahan murni deskripsi vs eksekusi. | Sangat rendah. Mental model sekuensial prosedural klasik yang biasa dipelajari sejak awal kuliah ilmu komputer. |
| **Memory Footprint** | Sangat kecil (Fibers: ratusan byte). Jutaan fiber dapat berjalan simultan dalam heap 2GB tanpa takut stack-overflow. | OS Thread: ~1MB memory overhead per thread (1.000 thread memakan ~1GB virtual RAM). Loom memangkas ini, tapi tetap bergantung GC heap. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Blocking The Compute Pool
* **Kesalahan Fatal:** Menjalankan blocking JDBC call atau file synchronous reading langsung di dalam thread pool komputasi default menggunakan `IO(...)`.
  ```scala
  // ERROR FATAL: Menghabiskan Worker Thread pool!
  def readBlockingData: IO[String] = IO {
    Thread.sleep(5000) // Menghentikan core work-stealing thread!
    "Data"
  }
  ```
* **Diagnostik:** WSTP mengalami starvation. Metrik throughput anjlok ke 0, fiber lain yang siap jalan tidak terlayani. Analisis thread dump di VisualVM / JConsole menunjukkan semua worker state: `TIMED_WAITING` di `Thread.sleep`.
* **Solusi Perbaikan:** Selalu gunakan `IO.blocking` atau `IO.interruptible` untuk memindahkan eksekusi secara otomatis ke dedicated unbounded blocking pool.
  ```scala
  def readBlockingDataSafe: IO[String] = IO.blocking {
    Thread.sleep(5000) // Dipindahkan ke pool khusus IO
    "Data"
  }
  ```

#### 2. Swallowing Cancellation Token
* **Kesalahan Fatal:** Mengabaikan cancellation token saat membuat async boundary kustom.
  ```scala
  // ANTI-PATTERN: Resource leak jika fiber dibatalkan
  IO.async_[Unit] { cb =>
    val listener = registerCallback(res => cb(Right(res)))
    // Tidak ada mekanisme unregister! Jika dicancel, listener menggantung di memori!
  }
  ```
* **Solusi Perbaikan:** Gunakan bentuk `IO.async` penuh yang mengembalikan token pembersihan (`Some(IO[Unit])`):
  ```scala
  IO.async[Unit] { cb =>
    IO {
      val listener = registerCallback(res => cb(Right(res)))
      Some(IO(listener.unregister())) // Callback pembersihan deterministik
    }
  }
  ```

#### 3. Fiber Leaks via Unsupervised `.start`
* **Kesalahan Fatal:** Menggunakan `io.start` liar tanpa penampung hierarki (*unstructured concurrency*).
* **Solusi Perbaikan:** Wajib gunakan `cats.effect.std.Supervisor` yang mengikat siklus hidup fiber anak ke *parent resource context*. Jika supervisor dihentikan, seluruh fiber anak dipaksa berhenti.

---

### 11. Best Practices (Production Checklist)

- [ ] **Thread Pool Separation:** Pastikan pemisahan mutlak antara:
  - *Compute Pool* (Default CPU-bound, ukuran: `Runtime.getRuntime.availableProcessors()`).
  - *Blocking Pool* (I/O legacy disk/JDBC, elastis tak terbatas via `IO.blocking`).
- [ ] **Deterministic Cleanups:** Jangan pernah mengalokasikan koneksi/file handle di luar `Resource` atau blok `uncancelable`.
- [ ] **Avoid Unbounded Buffers:** Semua struktur `Queue` di memori harus bounded (dibatasi ukurannya) untuk mencegah *OutOfMemoryError* akibat slow consumers.
- [ ] **Context Shifting Boundaries:** Pastikan third-party callback-based async integrations (AWS SDK v2, Kafka Producer, Netty) selalu membungkus callback dengan alur resuming fiber yang aman.
- [ ] **Tracing & Mappings:** Aktifkan tracing runtime Cats Effect pada level staging untuk debugging mendalam melalui JVM parameter:
  `-Dcats.effect.tracing.mode=full -Dcats.effect.tracing.buffer.size=64`. (Nonaktifkan di produksi super high-throughput jika overhead memory footprint melampaui 10%).

---

### 12. Hands-on Practice

Buatlah proyek mandiri pada workspace Anda dengan mengikuti struktur instruksi direktori berikut:

#### 1. Struktur Direktori
```text
hands-on/m02/
├── build.sbt
├── project
│   └── build.properties
└── src
    └── main
        └── scala
            └── com
                └── enterprise
                    └── telemetry
                        ├── Main.scala
                        ├── TelemetryEngine.scala
                        └── MetricsStorage.scala
```

#### 2. File: `hands-on/m02/project/build.properties`
```properties
sbt.version=1.9.9
```

#### 3. File: `hands-on/m02/build.sbt`
```scala
scalaVersion := "3.3.3"

name := "effect-system-production-telemetry"
version := "1.0.0"

libraryDependencies ++= Seq(
  "org.typelevel" %% "cats-effect" % "3.5.4",
  "org.typelevel" %% "cats-effect-kernel" % "3.5.4",
  "org.typelevel" %% "cats-effect-std" % "3.5.4"
)

scalacOptions ++= Seq(
  "-deprecation",
  "-encoding", "UTF-8",
  "-feature",
  "-unchecked",
  "-language:strictEquality"
)
```

#### 4. File: `hands-on/m02/src/main/scala/com/enterprise/telemetry/MetricsStorage.scala`
```scala
package com.enterprise.telemetry

import cats.effect.{IO, Ref}

trait MetricsStorage:
  def record(metricName: String, value: Double): IO[Unit]
  def getSummary: IO[Map[String, Double]]

object MetricsStorage:
  def inMemory: IO[MetricsStorage] =
    Ref.of[IO, Map[String, Double]](Map.empty).map { ref =>
      new MetricsStorage:
        override def record(metricName: String, value: Double): IO[Unit] =
          ref.update(current => current.updated(metricName, current.getOrElse(metricName, 0.0) + value))

        override def getSummary: IO[Map[String, Double]] =
          ref.get
    }
```

#### 5. File: `hands-on/m02/src/main/scala/com/enterprise/telemetry/TelemetryEngine.scala`
```scala
package com.enterprise.telemetry

import cats.effect.*
import cats.effect.std.Queue
import cats.syntax.all.*
import scala.concurrent.duration.*

case class MetricEvent(name: String, value: Double)

class TelemetryEngine(
  inboundQueue: Queue[IO, MetricEvent],
  storage: MetricsStorage
):
  def processBatches(batchSize: Int, flushInterval: FiniteDuration): IO[Unit] =
    def takeBatch(accumulated: List[MetricEvent]): IO[List[MetricEvent]] =
      if accumulated.size >= batchSize then IO.pure(accumulated)
      else
        inboundQueue.tryTake.flatMap {
          case Some(event) => takeBatch(event :: accumulated)
          case None => IO.pure(accumulated)
        }

    val runBatchFlush: IO[Unit] =
      for
        _       <- IO.sleep(flushInterval)
        items   <- takeBatch(Nil)
        _       <- items.traverse(event => storage.record(event.name, event.value))
        _       <- IO.whenA(items.nonEmpty)(IO.println(s"[ENGINE] Berhasil mem-flush ${items.size} metrik ke storage."))
      yield ()

    runBatchFlush.foreverM
```

#### 6. File: `hands-on/m02/src/main/scala/com/enterprise/telemetry/Main.scala`
```scala
package com.enterprise.telemetry

import cats.effect.*
import cats.effect.std.{Queue, Supervisor}
import cats.syntax.all.*
import scala.concurrent.duration.*

object Main extends IOApp.Simple:
  val run: IO[Unit] =
    Supervisor[IO].use { supervisor =>
      for
        queue   <- Queue.bounded[IO, MetricEvent](1000)
        storage <- MetricsStorage.inMemory
        engine  = new TelemetryEngine(queue, storage)

        // Spawn background worker engine
        _ <- supervisor.supervise(engine.processBatches(batchSize = 10, flushInterval = 200.millis))

        // Spawn mock client generator
        producer = (id: Int) =>
          (1 to 25).toList.traverse { seq =>
            IO.sleep(30.millis) *>
              queue.offer(MetricEvent("cpu_utilization", 1.5))
          }

        _ <- IO.println("[INIT] Menjalankan generator event...")
        _ <- (1 to 2).toList.traverse(id => supervisor.supervise(producer(id)))

        // Biarkan pipeline bekerja selama 2 detik
        _ <- IO.sleep(2.seconds)

        summary <- storage.getSummary
        _ <- IO.println(s"[RESULT] Summary Hasil Agregasi Metrics: $summary")
        _ <- IO.println("[SHUTDOWN] Mematikan aplikasi.")
      yield ()
    }
```

---

### 13. Exercise

#### Level 1 (Easy): Fiber Join and Cancel Race
* **Instruksi:** Buatlah program yang menjalankan dua fiber independen yang merepresentasikan komputasi paralel. Fiber A membutuhkan waktu 500 milidetik, sedangkan Fiber B membutuhkan waktu 1200 milidetik.
* **Persyaratan:**
  1. Jalankan kedua fiber secara konkruen menggunakan `.start`.
  2. Tunggu fiber yang selesai paling pertama.
  3. Batalkan fiber yang kalah (*loser*) secara eksplisit tanpa kebocoran thread.
  4. Cetak output fiber yang menang.

#### Level 2 (Medium): Priority-Based Non-Blocking Semaphore
* **Instruksi:** Kembangkan primitif kontrol akses konkruensi bernama `PriorityResourceGate`.
* **Persyaratan:**
  1. Hanya mengizinkan maksimal `N` fiber mengakses blok kode bersamaan.
  2. Fiber yang mengantre memiliki tingkat prioritas: `HIGH` atau `LOW`.
  3. Jika slot tersedia dan terdapat antrean, izin akses wajib diberikan kepada fiber berprioritas `HIGH` terlebih dahulu daripada `LOW`, meskipun `LOW` telah mengantre lebih lama.
  4. Seluruh sinkronisasi wajib non-blocking murni (menggunakan `Ref` dan `Deferred`).

#### Level 3 (Hard): Distributed Saga Pattern Orchestrator (In-Memory)
* **Instruksi:** Bangun orchestrator transaksi terdistribusi multi-langkah menggunakan prinsip Functional Effect.
* **Persyaratan:**
  1. Setiap transaksi terdiri atas minimal 3 tahap: `ReserveInventory`, `DebitWallet`, `CreateShippingLabel`.
  2. Tiap langkah memiliki fungsi `forward: IO[Unit]` dan fungsi `compensate: IO[Unit]`.
  3. Jalankan tahap-tahap tersebut secara linear.
  4. Jika tahap ke-3 (`CreateShippingLabel`) gagal/melemparkan exception, orchestrator wajib mengeksekusi kompensasi dari tahap ke-2 dan ke-1 dengan urutan terbalik secara atomik, aman dari pembatalan (`uncancelable`), serta mencatat log audit kompensasi kegagalan.

---

### 14. Challenge

Rancang dan bangun arsitektur **Adaptive Token Bucket Rate Limiter with Leaky Bucket Drain for DDoS Protection** tingkat enterprise tanpa menggunakan library eksternal selain Cats Effect.

#### Spesifikasi Arsitektur:
1. **Dynamic Burst Sizing:** Rate limiter harus mengizinkan *burst capacity* hingga 1000 request per detik, namun laju reguler rata-rata ditahan pada 200 request per detik.
2. **Deterministic Time-Decay:** Perhitungan pengurangan token harus berbasis aljabar delta waktu (`Clock[IO].monotonic`), bukan menggunakan thread loop polling berulang-ulang, demi efisiensi CPU 0% saat sistem idle.
3. **Multi-Tenant State:** Setiap penyewa (*Tenant ID*) memiliki limiternya masing-masing. State disimpan dalam sharded non-blocking structure.
4. **Eviction Policy:** Tenant yang tidak aktif selama lebih dari 5 menit harus dibersihkan secara otomatis dari heap (*garbage collected*) untuk mencegah memori membengkak tak terkendali.
5. **Chaos Verification:** Rancang skenario pengujian dengan konkurensi 10.000 request bersamaan dari 50 tenant acak, buktikan tidak ada race condition pada token bucket counter, dan semua thread aman dari starvation.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan mendasar antara mengeksekusi blocking call di dalam `IO(...)` versus di dalam `IO.blocking(...)` pada Cats Effect 3?
2. Mengapa sebuah fiber di Cats Effect 3 dikatakan beroperasi secara *cooperative multithreading*, bukan *preemptive*?
3. Apa peran dari fungsi `poll` di dalam parameter lambda `IO.uncancelable(poll => ...)`?
4. Apa fungsi dari primitif konkurensi `Deferred[IO, A]` dan apa perbedaannya dengan variabel `Promise` standar di package `scala.concurrent`?
5. Mengapa Work-Stealing Pool mencuri task dari ujung ekor (*tail*) deque lokal worker lain, bukan dari ujung kepala (*head*)?

#### 5 Pertanyaan Intermediate
6. Jelaskan bagaimana `IOFiber` menangani rekursi eksekusi tak terbatas tanpa memicu `java.lang.StackOverflowError` pada call stack thread JVM!
7. Jika sebuah fiber dibatalkan saat sedang mengeksekusi ekspresi `IO.blocking`, apakah thread native JVM yang sedang diblokir tersebut langsung terhenti seketika? Jelaskan mekanisme internalnya!
8. Apa yang membedakan `Ref[IO, A]` dari variabel primitif bertipe `@volatile var` pada Java/Scala imperatif?
9. Bagaimana cara kerja internal metode `.parTraverse` dalam membagi beban kerja ke seluruh worker thread, dan apa hubungannya dengan semantik *error short-circuiting*?
10. Jelaskan apa yang terjadi jika Anda memanggil `.start` pada sebuah IO tanpa pernah memanggil `.join` atau mengikatnya pada sebuah `Supervisor`!

#### 3 Skenario Kasus Produksi
11. **Skenario Memory Leak:** Sistem backend e-commerce Anda mengalami `OutOfMemoryError: Java heap space` di cluster Kubernetes saat traffic memuncak. Setelah melakukan inspeksi heap dump, Anda menemukan jutaan instance `cats.effect.IOFiber` yang mereferensikan closure finalizer. Komponen manakah yang paling dicurigai menyebabkan hal ini, dan bagaimana cara memvalidasinya?
12. **Skenario Thread Starvation:** Metrik latency API Anda melonjak dari 15ms ke 10 detik. CPU utilization berada pada level 15% (sangat rendah). Seluruh worker thread di pool komputasi berada dalam status `WAITING` pada pemanggilan lock socket dari driver database legacy. Mengapa algoritma work-stealing tidak mampu menyelamatkan latency sistem dalam kondisi ini?
13. **Skenario Zombie Transaction:** Sebuah microservice pembukuan keuangan menerima sinyal pembatalan timeout dari upstream client saat menulis debit saldo ke database. Walaupun transaksi DB terisolasi, entri audit log lokal tetap terkirim ke broker Kafka. Identifikasi celah logika konkruensi pada masking block yang menyebabkan state data menjadi tidak konsisten!

---

#### Kunci Jawaban & Panduan Solusi Quiz

1. **Basic:** `IO(...)` mengeksekusi kode langsung pada WSTP (Worker Thread) komputasi CPU. Jika terjadi blocking, thread WSTP terhenti, memicu starvation bagi fiber lain. `IO.blocking(...)` memindahkan eksekusi lambda ke elastis dedicated blocking pool, menjaga worker pool CPU tetap bebas melayani run-loop.
2. **Basic:** Fiber tidak dipaksa berhenti oleh OS interrupt tick. Fiber secara sukarela menyerahkan kontrol (*yield*) ke runtime saat menyentuh *batch boundary* (default 1024 flatMaps) melalui mekanisme `cede`, atau saat menunggu async callback.
3. **Basic:** `poll` menciptakan lubang (*escape hatch*) di dalam zona `uncancelable`. Bagian kode di dalam `poll(...)` diizinkan untuk diinterupsi oleh sinyal pembatalan, sementara kode di luar `poll` di blok yang sama tetap kebal terhadap interupsi.
4. **Basic:** `Deferred` bersifat murni fungsional, immutable secara referensial, murni non-blocking (fiber yang menunggu `get` akan di-suspend tanpa memakan resource thread), dan hanya dapat diisi nilainya tepat satu kali (`complete`).
5. **Basic:** Untuk meminimalkan lock contention. Worker pemilik mengakses ujung *head* dequenya secara eksklusif (LIFO/FIFO), sehingga pencuri (*thief*) yang mengambil dari ujung *tail* (ujung berlawanan) dapat melakukan operasi pencurian menggunakan CAS tanpa mengganggu aktivitas eksekusi lokal pada sebagian besar waktu.
6. **Intermediate:** Melalui teknik *monadic trampolining*. Run-loop mengalihkan eksekusi rekursif dari native JVM stack frames menjadi representasi data objek di Heap (seperti struktur *continuation stack*). Stack frame native JVM tetap datar konstan (*O(1) stack space*).
7. **Intermediate:** Tidak langsung terhenti seketika. Thread OS tidak bisa dihentikan paksa tanpa bahaya korupsi state internal JVM. Runtime hanya menandai fiber sebagai canceled dan jika menggunakan `IO.interruptible`, runtime akan memicu `Thread.currentThread().interrupt()`. Jika native library mengabaikan flag interrupt Java, thread tersebut akan terus berjalan hingga eksekusi I/O native tuntas.
8. **Intermediate:** `Ref[IO, A]` membungkus `AtomicReference` JVM namun menyediakan manipulasi state fungsional murni yang terintegrasi penuh ke dalam monad `IO`. Perubahan state bersifat atomic, composable via combinator seperti `modify`, `updateAndGet`, serta menjamin konsistensi linieritas tanpa side-effect langsung.
9. **Intermediate:** `.parTraverse` memecah koleksi data, membungkus setiap elemen ke dalam fiber independen yang di-fork ke WSTP. Jika salah satu fiber gagal (*fails with exception*), Applicative/MonadError semantik secara otomatis memicu pembatalan (*cancels*) ke seluruh fiber anak lainnya yang masih berjalan (*short-circuit*).
10. **Intermediate:** Terjadi fenomena *unstructured concurrency*. Fiber menjadi yatim (*orphaned/daemon-like*). Jika parent fiber mati atau gagal, fiber anak tetap meluncur di background. Hal ini menyebabkan kebocoran memori (leak) dan *uncontrolled side-effects* yang sangat sulit dilacak.
11. **Skenario Produksi 1:** Masalah ada pada pola registrasi resource atau listener yang terus menumpuk di memori (misalnya pemanggilan rekursif uncancelable yang menumpuk finalizer stack, atau antrean streaming tanpa backpressure). Validasi: Periksa objek `cats.effect.IOFiber` di heap dump via Eclipse Memory Analyzer (MAT), telusuri field `finalizers` stack untuk melihat closure apa yang menahan objek heap.
12. **Skenario Produksi 2:** Driver database legacy tersebut memanggil blocking socket secara langsung di dalam pool komputasi CPU (tidak dibungkus `IO.blocking`). Seluruh worker thread inti dari WSTP terblokir menanti respon soket, sehingga kapasitas CPU starvation. WSTP tidak dapat mencuri task karena semua worker sama-sama membeku menunggu sinyal I/O jaringan.
13. **Skenario Produksi 3:** Blok penulisan Kafka tidak di-mask dengan benar, atau sebaliknya ditaruh di luar transaksi atomik DB tanpa koordinasi two-phase commit / transactional outbox pattern. Saat pembatalan terjadi di antara dua pemanggilan tersebut, cancellation membatalkan langkah berikutnya tanpa membatalkan efek yang telah terlanjur di-emit ke Kafka.

---

### 16. Summary

* Functional Effect Systems merevolusi komputasi konkruensi di JVM dengan mentransformasikan side-effects menjadi nilai murni deklaratif (*referentially transparent blueprints*).
* Arsitektur **Cats Effect 3 / ZIO 2** mengandalkan **IOFiber run-loop** dengan algoritma **Work-Stealing Thread Pool** yang memberikan efisiensi utilisasi CPU tingkat tinggi, ketahanan terhadap thread starvation, dan footprint memori yang jauh lebih ringan daripada model satu-thread-per-request konvensional.
* Keamanan konkruensi tingkat lanjut menuntut pemahaman mutlak mengenai batas isolasi runtime: memisahkan thread pool komputasi murni dari thread blocking, mengendalikan interupsi kooperatif melalui kombinasi `IO.uncancelable` dan `poll`, serta mengelola lifecycle lifecycle IO secara deterministik menggunakan primitif `Resource` dan `Supervisor`.
* Dalam lingkungan produksi, penggunaan functional effects menyediakan pondasi arsitektur tangguh (*resilient*) yang mampu menahan beban burst melalui backpressure terintegrasi, circuit breaking murni, dan pengujian deterministik via runtime virtual time travel.