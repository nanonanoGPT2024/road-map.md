# SEKSI 01 — IDENTITAS MODUL

*   **Domain:** Software Engineering & Functional Programming Architecture
*   **Track:** Scala Advanced Backend Engineering
*   **Kategori:** 02-Programming-Languages
*   **Bab 08:** Advanced Concurrency & Functional Runtimes
*   **Modul 01:** Functional Effect Systems
*   **Prasyarat:** Scala 3 Fundamentals, Higher-Kinded Types, Type Classes, Monads & Monad Transformers, Basic Concurrency (`scala.concurrent.Future`)
*   **Estimasi Waktu Belajar:** 6 – 8 Jam
*   **Target Stack:** Scala 3.3 LTS, Cats Effect 3.5+, ZIO 2.0+

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1.  **Mendefinisikan dan Membuktikan Transparansi Referensial (*Referential Transparency*):** Menguraikan secara matematis perbedaan antara evaluasi berbasis efek samping (*side-effects*) dan evaluasi berbasis substitusi (*equational reasoning*) menggunakan tipe `IO`.
2.  **Merancang dan Mengimplementasikan Runtime Loop Miniatur:** Membangun *monadic effect data type* dari nol lengkap dengan ADT (*Algebraic Data Type*) representasi komputasi dan *trampolined run-loop* untuk mencegah *stack overflow*.
3.  **Menguasai Paradigma *Programs as Values*:** Memisahkan secara ketat tahap deklarasi komputasi (*effect description*) dari tahap eksekusi runtime (*effect interpretation*).
4.  **Mengoperasikan Konkurensi Berbasis Fiber (*Green Threads*):** Mengelola siklus hidup Fiber, proses *fork/join*, *cancellation tokens*, dan *structured concurrency* pada Cats Effect 3 / ZIO 2.
5.  **Menerapkan Pola Alokasi Sumber Daya Deterministik:** Memanfaatkan tipe `Resource` (atau `ZIO.acquireRelease`) untuk menjamin pelepasan *file descriptor*, koneksi jaringan, dan thread-pool dalam kondisi gagal maupun dibatalkan (*cancellation*).
6.  **Mengoptimalkan dan Melakukan Profiling Sistem Efek:** Menghindari *thread starvation* melalui pemisahan komputasi CPU (*compute pool*) dan pemblokiran I/O (*blocking pool*), serta menganalisis jejak serat (*fiber dump*).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Pergeseran Paradigma: Eksekusi Langsung vs. Blueprint Komputasi

Dalam paradigma imperatif serta pustaka standar lama seperti `scala.concurrent.Future`, memanggil sebuah metode akan **seketika memicu eksekusi** pada thread pool global. 

```scala
// Future: Running immediately (Not referentially transparent)
val future1 = Future(println("Executing!")) 
val future2 = future1
// Hasil: Teks hanya dicetak SATU KALI. Nilai terikat pada hasil komputasi yang sudah berjalan.
```

Dalam sistem efek fungsional (*Functional Effect System*), sebuah nilai efek bukanlah komputasi yang sedang berjalan, melainkan **deskripsi komputasi (blueprint)**.

```scala
// IO: A pure value describing what to do
val effect1 = IO(println("Executing!"))
val effect2 = effect1 >> effect1
// Hasil: Teks belum dicetak sama sekali hingga runtime mengevaluasinya.
// Ketika dijalankan, efek dieksekusi DUA KALI secara independen.
```

```
Mental Model: "Resep Makanan vs. Memasak Makanan"
+--------------------------------------------------------------+
| Blueprint (IO[A])                                            |
|   - Sebuah struktur data murni (Immutable Data Structure).   |
|   - Boleh disalin, dikombinasikan, di-pass ke mana saja.    |
|   - Bebas efek samping hingga tiba di "End of the World".   |
+--------------------------------------------------------------+
                               |
                        [ interpreted by ]
                               v
+--------------------------------------------------------------+
| Runtime Engine (Cats Effect Runtime / ZIO Engine)            |
|   - Mengubah deskripsi menjadi aksi nyata.                   |
|   - Menjalankan instruksi di atas Fiber.                     |
|   - Mengatur Work-Stealing, Scheduler, & Resource Safety.    |
+--------------------------------------------------------------+
```

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di balik layar, runtime sistem efek fungsional mengevaluasi sebuah struktur pohon (*Abstract Syntax Tree* / ADT) menggunakan algoritma berbasis *trampolined loop* yang dijadwalkan ke dalam *work-stealing thread pool*.

```
   [ Deklarasi Program (Pure AST) ]
                  |
     IO.delay(openSocket())
       .flatMap(readData)
       .timeout(5.seconds)
                  |
   ========================================================================
   [ Boundary: App.run / unsafeRunSync / Cats Effect Runtime Engine ]
   ========================================================================
                  |
                  v
       +-----------------------+
       |   FIBER SCHEDULER     | <---------------------+
       | (Cooperative Multi)   |                       |
       +-----------------------+                       |
                  |                                    | (Re-enqueued)
                  | Creates                            |
                  v                                    |
            +------------+                             |
            | Fiber #104 |                             |
            +------------+                             |
                  |                                    |
         Runs on Worker Thread                         |
                  |                                    |
                  v                                    |
   +-------------------------------+                   |
   | Worker-Stealing Thread Pool   |                   |
   |                               |                   |
   |  Thread-1: [F-104] [F-105]    |                   |
   |  Thread-2: [F-106]            |                   |
   |  Thread-3: (Empty) -> Steals! |                   |
   +-------------------------------+                   |
                  |                                    |
         Yield / Async Boundary                        |
                  |                                    |
                  v                                    |
      +------------------------+                       |
      | External Async Event / |-----------------------+
      | Non-blocking I/O Event |
      +------------------------+
```

### Siklus Hidup Eksekusi Fiber

```
 [Created] ---> [Runnable] ---> [Running on Worker]
                  ^                     |
                  |               (IO.cede / I/O wait)
                  |                     v
                  +--------------- [Suspended]
                                        |
                                   (Cancelled)
                                        v
                                 [Finalizing] ---> [Terminated]
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sebuah *Effect Type* (misal `IO[A]`) diimplementasikan secara internal sebagai **Generalized Algebraic Data Type (GADT)**. Runtime hanyalah sebuah perulangan besar (`runLoop`) yang membaca node ADT tersebut satu per satu tanpa menghabiskan stack memori JVM (*stack-safe*).

```
                      +------------------+
                      |     IO[+A]       | (Sealed Trait)
                      +------------------+
                               ^
      +------------------------+-----------------------+
      |                        |                       |
+--------------+        +---------------+      +----------------+
|   Pure[A]    |        |   Delay[A]    |      |  FlatMap[E, A] |
| (Nilai eager |        | (Thunk lazy:  |      | (Komposisi     |
| tanpa efek)  |        |  () => A)     |      |  dua efek)     |
+--------------+        +---------------+      +----------------+
                                                       |
                                            +--------------------+
                                            |   Async[A]         |
                                            | (Register callback |
                                            |  non-blocking)     |
                                            +--------------------+
```

### Mekanisme Internal Trampoline Run-Loop

Ketika Anda melakukan rantai pemanggilan `flatMap` ribuan kali:
1. JVM biasanya mengalokasikan satu *stack frame* per pemanggilan fungsi, yang berujung pada `java.lang.StackOverflowError`.
2. Sistem efek mengubah rekursi fungsi menjadi iterasi heap (`while (current != null)`).
3. Status eksekusi disimpan di dalam objek pointer pada memori Heap, membebaskan Stack JVM untuk terus digunakan kembali (*trampolining*).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Transparansi Referensial (Referential Transparency)
Sebuah ekspresi $E$ dikatakan transparan secara referensial jika seluruh kemunculan $E$ dapat digantikan dengan nilai evaluasinya $V$ tanpa mengubah perilaku program sama sekali.

*   `scala.concurrent.Future` **melanggar** transparansi referensial karena ia bersifat *memoized* dan terikat dengan waktu pembuatan (*time-dependent evaluation*).
*   `cats.effect.IO` **mematuhi** transparansi referensial karena ia membungkus efek samping ke dalam fungsi murni berparameter hampa `() => A`.

### 2. Fibers: Lightweight Logical Threads
Fiber adalah abstraksi konkurensi di level runtime (sering disebut *green threads*):
*   **Ukuran Alokasi:** Thread sistem operasi (OS thread) memakan $\sim 1\text{ MB}$ memori stack secara default. Fiber hanya memakan beberapa ratus byte data pada heap.
*   **Context Switching:** Pergantian konteks OS thread melibatkan instruksi kernel CPU (*ring 0 context switch*). Pergantian konteks Fiber murni dilakukan di dalam level JVM tanpa *system call*.
*   **Kapasitas Konkurensi:** Satu node JVM dapat menampung jutaan Fiber secara bersamaan, tetapi akan mengalami degradasi performa atau kehabisan memori jika menjalankan lebih dari beberapa ribu OS thread.

### 3. Cooperative Multi-tasking & Auto-yielding
Fiber bekerja secara kooperatif. Runtime Cats Effect dan ZIO menyisipkan *counter* pada loop evaluasi flatMap. Setelah mengeksekusi sejumlah operasi monadic berturut-turut (misal 1024 flatMap pada Cats Effect), runtime secara otomatis menyisipkan batas asinkron (*cooperative yield* / `IO.cede`). Hal ini mencegah satu fiber memonopoli worker thread CPU (*fair scheduling*).

### 4. Cancellation & Structured Concurrency
Pembatalan (*cancellation*) dalam sistem efek bersifat deterministik:
*   Jika sebuah fiber induk dibatalkan, semua fiber turunannya yang di-fork harus dihentikan secara otomatis (*no orphan fibers*).
*   Operasi pembatalan memicu *finalizer* (pembersihan resource) yang telah didaftarkan.
*   Tahap pembersihan dapat dilindungi dari pembatalan sekunder menggunakan fungsi `IO.uncancelable`.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut implementasi sistem efek mandiri (*from-scratch*) untuk memahami anatomi internal `IO`, dilanjutkan implementasi menggunakan **Cats Effect 3**.

### Langkah 1: Membangun Engine Mini-IO dari Nol

```scala
// File: MiniIO.scala
package advanced.effects

sealed trait MiniIO[+A] {
  def flatMap[B](f: A => MiniIO[B]): MiniIO[B] = MiniIO.FlatMap(this, f)
  def map[B](f: A => B): MiniIO[B] = flatMap(a => MiniIO.Pure(f(a)))

  // Menjalankan efek secara aman tanpa menghabiskan stack JVM (Trampolined)
  def unsafeRunSync(): A = {
    var current: MiniIO[Any] = this
    val stack = collection.mutable.Stack[Any => MiniIO[Any]]()

    while (current != null) {
      current match {
        case MiniIO.Pure(value) =>
          if (stack.isEmpty) return value.asInstanceOf[A]
          else {
            val cont = stack.pop()
            current = cont(value)
          }

        case MiniIO.Delay(thunk) =>
          val evaluated = thunk()
          if (stack.isEmpty) return evaluated.asInstanceOf[A]
          else {
            val cont = stack.pop()
            current = cont(evaluated)
          }

        case MiniIO.FlatMap(source, f) =>
          stack.push(f.asInstanceOf[Any => MiniIO[Any]])
          current = source
      }
    }
    throw new IllegalStateException("Run-loop terminated invalidly")
  }
}

object MiniIO {
  final case class Pure[+A](value: A) extends MiniIO[A]
  final case class Delay[+A](thunk: () => A) extends MiniIO[A]
  final case class FlatMap[A, +B](sub: MiniIO[A], f: A => MiniIO[B]) extends MiniIO[B]

  def apply[A](thunk: => A): MiniIO[A] = Delay(() => thunk)
  def pure[A](value: A): MiniIO[A] = Pure(value)
}
```

### Langkah 2: Menggunakan Cats Effect 3 Resmi

Tambahkan dependensi pada `build.sbt`:
```scala
libraryDependencies += "org.typelevel" %% "cats-effect" % "3.5.4"
```

```scala
// File: CatsEffectBasics.scala
package advanced.effects

import cats.effect.{IO, IOApp, ExitCode}
import scala.concurrent.duration._

object CatsEffectBasics extends IOApp {

  def compute(id: Int): IO[Int] = IO {
    println(s"[Compute-$id] Running on thread: ${Thread.currentThread().getName}")
    id * 42
  }

  override def run(args: List[String]): IO[ExitCode] = {
    val program: IO[Unit] = for {
      _        <- IO.println("=== Memulai Program Efek Fungsional ===")
      // Fork eksekusi ke fiber terpisah
      fiber1   <- (IO.sleep(500.millis) >> compute(1)).start
      fiber2   <- (IO.sleep(200.millis) >> compute(2)).start
      // Menunggu hasil kedua fiber (Structured Concurrency via join)
      outcome1 <- fiber1.join
      outcome2 <- fiber2.join
      _        <- IO.println(s"Hasil Fiber 1: $outcome1 | Fiber 2: $outcome2")
      _        <- IO.println("=== Program Selesai Secara Deterministik ===")
    } yield ()

    program.as(ExitCode.Success)
  }
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis Implementasi `MiniIO` (Langkah 1)

*   `sealed trait MiniIO[+A]`: Deklarasi ADT yang bersifat *covariant*. Memastikan seluruh implementasi tertutup di dalam file yang sama.
*   `final case class Pure[+A](value: A)`: Representasi nilai eager yang sudah dihitung, bebas dari efek samping.
*   `final case class Delay[+A](thunk: () => A)`: Membungkus kode yang memiliki efek samping ke dalam lambda *by-name*. Penundaan evaluasi (*lazy execution*) terjadi di sini.
*   `final case class FlatMap[A, +B](...)`: Menyimpan dependensi sekuensial antara komputasi pertama dan fungsi pembuat komputasi berikutnya.
*   `val stack = collection.mutable.Stack[...]`: Memindahkan alokasi *stack frames* dari Call Stack JVM ke Heap memory. Ini adalah esensi mekanika *trampolining*.
*   `while (current != null)`: Loop tunggal iteratif yang mengekstrak komputasi lapis demi lapis tanpa menyebabkan `StackOverflowError`.

### Analisis Cats Effect 3 (Langkah 2)

*   `object CatsEffectBasics extends IOApp`: Entry-point aplikasi murni. Menghilangkan kebutuhan method `main` konvensional dan menangani inisialisasi thread pool secara otomatis.
*   `IO.println(...)`: Membungkus `System.out.println` ke dalam `IO[Unit]`. Eksekusi ditunda sampai runtime engine mengevaluasinya.
*   `(IO.sleep(...) >> compute(1)).start`: Operator `>>` merangkai efek secara berurutan (*sequencing*). Pemanggilan method `.start` adalah instruksi eksplisit kepada scheduler untuk menduplikasi (*fork*) eksekusi ke dalam Fiber baru yang berjalan asinkron.
*   `fiber1.join`: Mengembalikan `IO[Outcome[IO, Throwable, A]]`. Tidak memblokir thread fisik, melainkan menangguhkan (*suspends*) Fiber pemanggil sampai Fiber target selesai atau dibatalkan.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Resilient Webhook Dispatcher Engine

Dalam arsitektur *event-driven* berskala besar, sistem Anda harus mengirimkan ribuan event webhook ke server pihak ketiga secara paralel.

**Tantangan Teknis:**
1.  **Ledakan Thread (Resource Exhaustion):** Penggunaan `Future` biasa akan menghabiskan OS thread JVM secara instan saat server pihak ketiga mengalami *high latency*.
2.  **Koneksi Bocor (Connection Leaks):** Koneksi HTTP harus ditutup secara deterministik, baik saat pengiriman sukses, server tujuan error, maupun ketika proses lokal dibatalkan (*cancelled*).
3.  **Lonjakan Beban (Rate Limiting & Backpressure):** Tidak boleh membebani server tujuan melebihi kuota konkurensi yang disepakati.

**Solusi Menggunakan Effect System:**
*   Gunakan Fiber untuk mengirim ribuan request secara bersamaan dengan alokasi memori minimal.
*   Gunakan `cats.effect.std.Semaphore` untuk *rate limiting* / konkurensi terkontrol.
*   Gunakan `cats.effect.Resource` untuk menjamin soket/koneksi dilepas secara deterministik.
*   Gunakan mekanisme pembatalan (*cancellation*) dan batas waktu (*timeout*) bawaan `IO`.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Berikut implementasi lengkap *Resilient Webhook Dispatcher* menggunakan Cats Effect 3.

```scala
// File: WebhookDispatcher.scala
package advanced.effects.production

import cats.effect._
import cats.effect.std.Semaphore
import cats.syntax.all._
import scala.concurrent.duration._

// 1. Domain Entities
final case class WebhookPayload(id: String, targetUrl: String, body: String)
final case class DispatchResult(id: String, statusCode: Int, durationMs: Long)

// 2. Resource Abstraction: HTTP Client Simulator
trait HttpClient {
  def post(url: String, data: String): IO[Int]
}

object HttpClient {
  // Mengalokasikan client sebagai cats.effect.Resource
  def makeResource(poolName: String): Resource[IO, HttpClient] = {
    val acquire = IO.println(s"[Pool-$poolName] Inisialisasi TCP Socket Pool...") >>
      IO.pure(new HttpClient {
        override def post(url: String, data: String): IO[Int] = {
          for {
            _ <- IO.sleep(100.millis) // Simulasi Network Round-Trip
            _ <- IO.raiseWhen(url.contains("malicious"))(new RuntimeException("Connection refused"))
          } yield 200
        }
      })

    val release: HttpClient => IO[Unit] = _ =>
      IO.println(s"[Pool-$poolName] Menutup seluruh koneksi TCP dan membersihkan memori.")

    Resource.make(acquire)(release)
  }
}

// 3. Dispatcher Service
class WebhookDispatcher private (client: HttpClient, concurrencyLimiter: Semaphore[IO]) {

  def dispatch(payload: WebhookPayload): IO[DispatchResult] = {
    val executeWithMetric = for {
      start  <- IO.realTime
      status <- client.post(payload.targetUrl, payload.body)
      end    <- IO.realTime
      dur     = (end - start).toMillis
    } yield DispatchResult(payload.id, status, dur)

    // Bungkus operasi dengan Concurrency Control (Semaphore) dan Timeout Protection
    concurrencyLimiter.permit.use { _ =>
      executeWithMetric
        .timeout(3.seconds)
        .handleErrorWith { error =>
          IO.println(s"[ERROR] Dispatching Webhook ID ${payload.id} gagal: ${error.getMessage}") >>
            IO.pure(DispatchResult(payload.id, 500, 0L))
        }
    }
  }

  def dispatchBatch(payloads: List[WebhookPayload]): IO[List[DispatchResult]] = {
    // Mengeksekusi seluruh pengiriman webhook secara paralel di atas Fiber terpisah
    payloads.parTraverse(dispatch)
  }
}

object WebhookDispatcher {
  def make(client: HttpClient, maxConcurrentRequests: Long): IO[WebhookDispatcher] =
    Semaphore[IO](maxConcurrentRequests).map(sem => new WebhookDispatcher(client, sem))
}

// 4. Production Application Entry Point
object WebhookApplication extends IOApp.Simple {

  val payloads: List[WebhookPayload] = (1 to 20).toList.map { i =>
    val target = if (i == 13) "http://malicious-node.internal" else s"http://api.partner-$i.com/webhook"
    WebhookPayload(s"evt-$i", target, s"""{"event": "invoice.paid", "seq": $i}""")
  }

  override def run: IO[Unit] = {
    val appResource = for {
      client     <- HttpClient.makeResource("Production-Gateway")
      dispatcher <- Resource.eval(WebhookDispatcher.make(client, maxConcurrentRequests = 5))
    } yield dispatcher

    appResource.use { dispatcher =>
      for {
        _       <- IO.println("--- MEMULAI PENGIRIMAN DISPATCH SECARA PARALEL ---")
        results <- dispatcher.dispatchBatch(payloads)
        _       <- IO.println(s"--- SELESAI. Total Berhasil Diproses: ${results.length} item ---")
        _       <- results.traverse(r => IO.println(s"Result: [${r.id}] Status: ${r.statusCode} Time: ${r.durationMs}ms"))
      } yield ()
    }
  }
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

| Kriteria / Metrik | Scala `Future` | Cats Effect 3 / ZIO 2 | Java 21 Virtual Threads (Loom) | Akka / Pekko Actors |
| :--- | :--- | :--- | :--- | :--- |
| **Model Evaluasi** | Eager (Langsung jalan) | Lazy (Program as a Value) | Eager (Blocking imperative) | Message-driven asynchronous |
| **Referential Transparency** | Tidak | **Ya, Penuh** | Tidak | Tidak |
| **Footprint Memori per Unit**| $\sim 1\text{ MB}$ (OS Thread bound)| $\sim 200\text{ bytes}$ (Fiber) | $\sim 1\text{ KB}$ (Continuation) | $\sim 300\text{ bytes}$ (Actor cell) |
| **Resource Safety** | Manual / `try-finally` | Terjamin (`Resource`/`Scope`)| Manual / `AutoCloseable` | Lifecycle Hooks (`postStop`) |
| **Cancellation Safety** | Hampir tidak mungkin | Terjamin secara native | Thread interrupt (Parsial) | Stop PoisonPill / Terdistribusi |
| **Kurva Belajar (Learning)** | Sangat Rendah | Tinggi (Perlu disiplin FP) | Sangat Rendah | Sedang hingga Tinggi |
| **Ecosystem Maturity** | Standard JVM | Sangat luas (Typelevel/ZIO) | Masih berkembang | Sangat matang |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Memblokir Compute Thread Pool (*Thread Starvation*)
**Problem:** Menjalankan instruksi sinkron yang memblokir I/O (seperti `Thread.sleep` atau JDBC standar) langsung di dalam `IO.apply` akan menahan *worker thread* pada *Compute Pool*. Jika seluruh worker terblokir, scheduler tidak bisa memproses Fiber lain.

```scala
// PITFALL: Memblokir compute threadpool
IO(Thread.sleep(5000)) 

// SOLUSI: Beri tahu runtime untuk mengalihkan ke Blocking Thread Pool
IO.blocking(Thread.sleep(5000))
// ATAU gunakan penundaan non-blocking murni:
IO.sleep(5.seconds)
```

### 2. Kebocoran Fiber (*Fiber Leakage*)
**Problem:** Memanggil `effect.start` tanpa pernah menggabungkannya (`join`) atau membatalkannya (`cancel`). Jika Fiber tersebut menjalankan loop tak terbatas, ia akan terus hidup di memory heap, mengonsumsi CPU cycle secara diam-diam.

```scala
// PITFALL: Fire-and-forget tanpa kendali
def pollForever: IO[Unit] = IO.println("Ping") >> IO.sleep(1.second) >> pollForever

val leak = for {
  _ <- pollForever.start // Mengambang tanpa referensi pembatalan
} yield ()

// SOLUSI: Lindungi siklus hidup dengan cats.effect.std.Supervisor
```

### 3. Masking Cancellation pada Region Kritis
**Problem:** Menggunakan `IO.uncancelable` tanpa membuka kembali titik pembatalan (*poll boundary*) pada operasi yang berlangsung lama, menyebabkan aplikasi macet total saat menerima sinyal *graceful shutdown* (`SIGTERM`).

```scala
// SOLUSI: Buka poll boundary secara hati-hati
IO.uncancelable { poll =>
  for {
    res <- acquireResource
    // Bagian komputasi ini boleh dibatalkan:
    data <- poll(res.downloadLargePayload).onCancel(res.cleanup)
    _    <- res.persist(data)
  } yield ()
}
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan 1: Memanggil `unsafeRunSync` di Dalam Logika Bisnis
*Praktek Buruk:* Membocorkan runtime execution engine ke dalam domain layer.
```scala
// ERROR: Mengorbankan sifat murni efek
def getUser(id: String): User = {
  database.fetchUser(id).unsafeRunSync() // HANCUR: Menghilangkan referential transparency!
}
```
*Solusi:* Pertahankan tipe pengembalian `IO[User]` hingga mencapai batas aplikasi (`IOApp.run`). Biarkan framework yang menjalankan evaluasi di titik akhir program (*End of the World*).

---

### Kesalahan 2: Menggunakan Konstruksi Non-Idempotent di Luar `IO.delay`
*Praktek Buruk:* Mengevaluasi kode mutabel sebelum dibungkus ke dalam `IO`.
```scala
// ERROR: Nilai dievaluasi saat runtime menginisialisasi baris, bukan saat efek dipanggil
val currentTime = System.currentTimeMillis() // Eager!
val effect = IO(println(s"Time: $currentTime")) 
```
*Solusi:* Bungkus seluruh ekspresi di dalam blok `IO(...)`:
```scala
// BENAR: Waktu dievaluasi tepat saat efek dijalankan
val effect = IO.realTimeInstant.flatMap(now => IO.println(s"Time: $now"))
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Gunakan Tagless Final atau Explicit IO:** Untuk aplikasi skala besar, pisahkan definisi antarmuka domain menggunakan abstraksi *Higher-Kinded Type* (`F[_]`) dengan type classes seperti `Async[F]`, `Sync[F]`, atau gunakan secara langsung `IO` pada tingkat *Service Implementation* untuk kesederhanaan arsitektur (*Direct IO Style*).
2.  **Karantina Operasi Berbahaya dengan `Resource`:** Hindari pola `try / finally` imperatif. Semua koneksi jaringan, pembacaan file stream, dan lock mutabel wajib direpresentasikan sebagai `cats.effect.Resource`.
3.  **Tentukan Strict Timeouts:** Jangan biarkan pemanggilan remote jaringan menggantung tanpa timeout. Bungkus semua I/O eksternal dengan `.timeout(durasi)` atau `.timeoutTo(durasi, fallbackEffect)`.
4.  **Konfigurasi Thread Pool Compute Sesuai CPU Cores:** Biarkan runtime Cats Effect secara otomatis mengatur jumlah worker compute pool setara dengan `Runtime.getRuntime.availableProcessors()`. Hindari mengubah ukuran compute pool tanpa metrik profiler yang valid.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Eliminasi Alokasi Berlebih pada FlatMap Chains
Ketika melakukan operasi batch ribuan item, jangan gunakan rekursi monadic naif. Gunakan metode `fs2.Stream` atau operator kombinatorik bawaan seperti `IO.parTraverseN` untuk membatasi derajat konkurensi tanpa membebani heap JVM dengan jutaan objek `IO.FlatMap`.

```scala
// Batasi derajat konkurensi (bounded concurrency)
import cats.syntax.all._

val items = (1 to 100000).toList
// Memproses maksimal 32 fiber berjalan paralel bersamaan
items.parTraverseN(32)(processItem)
```

### 2. Tuning Garbage Collection untuk Work-Stealing Pool
Runtime Cats Effect menghasilkan banyak objek berumur pendek (*short-lived allocations*) pada heap JVM (seperti node flatmap dan continuation frames).
*   Gunakan JVM garbage collector modern: **ZGC** atau **Shenandoah GC** untuk memangkas *GC pause times* hingga di bawah 1 milidetik:
    ```bash
    -XX:+UseZGC -XX:+ZGenerational
    ```

---

# SEKSI 16 — KEAMANAN & HARDENING

1.  **Pencegahan Resource Exhaustion (DoS Protection):** 
    Sistem efek memungkinkan implementasi *backpressure* deterministik. Batasi *unbounded queues* menggunakan `cats.effect.std.Queue.bounded[IO, Request](capacity)`. Ketika antrean penuh, fiber yang bertindak sebagai produsen akan ditangguhkan secara otomatis (*suspended*), mencegah aplikasi mengalami `OutOfMemoryError`.
2.  **Sensitivitas Token & Kredensial:**
    Deskripsi efek fungsional menyimpan objek di heap dalam waktu yang lebih terstruktur. Hindari menaruh *raw secret token* di dalam pesan exception atau logging context:
    ```scala
    // Amankan jejak string dengan menyamarkan variabel
    case class ApiKey(private val raw: String) {
      override def toString: String = "ApiKey(REDACTED)"
    }
    ```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Sistem berbasis Fiber tidak dapat didebug menggunakan stack trace tradisional JVM karena thread fisik berpindah-pindah. Cats Effect menyediakan mekanisme *Tracing* bawaan:

### 1. Mengaktifkan Fiber Tracing
Tambahkan flag JVM untuk mengaktifkan pelacakan eksekusi serat secara mendalam:
```bash
-Dcats.effect.tracing.mode=full
-Dcats.effect.tracing.buffer.size=64
```

### 2. Menghasilkan Fiber Dump
Sama halnya dengan *Thread Dump*, runtime Cats Effect memungkinkan pengambilan *Fiber Dump* saat aplikasi sedang berjalan untuk memeriksa potensi *deadlock* atau *hung tasks*:

```scala
import cats.effect.std.Supervisor
import cats.effect.tracing.FiberMonitor

// Melakukan logging informasi seluruh fiber yang sedang berjalan
IOApp.runtime.fiberMonitor.foreach { monitor =>
  monitor.liveFiberSnapshot().foreach { snapshot =>
    println(s"FIBER STATUS: ${snapshot.status} - CREATED AT: ${snapshot.origin}")
  }
}
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Aljabar & Combinator Utama Cats Effect 3

```scala
import cats.effect.IO
import scala.concurrent.duration._

// 1. Instansiasi & Boundaries
IO.pure(42)                  // Evaluasi nilai eager (murni tanpa efek)
IO(println("Lazy"))          // Evaluasi synchronous effect (Compute Pool)
IO.blocking(readSyncFile())  // Evaluasi blocking I/O (Blocking Pool)
IO.async_(cb => register(cb))// Integrasi asynchronous callback library eksternal

// 2. Concurrency Primitives
ioA.start                    // Fork IO ke dalam Fiber independen
fiber.join                   // Tunggu sampai Fiber selesai (Non-blocking)
fiber.cancel                 // Batalkan eksekusi Fiber secara deterministik
(ioA, ioB).parTupled         // Jalankan kedua IO paralel, kembalikan hasil tuple (A, B)
(ioA, ioB).parMapN(_ + _)    // Jalankan paralel, kombinasikan hasil komputasi
ioA.race(ioB)                // Balapan: ambil yang tercepat, batalkan yang lambat

// 3. Control Flow & Fault Tolerance
ioA.timeout(5.seconds)       // Batasi durasi, lempar TimeoutException jika lewat
ioA.retry(RetryPolicies...)  // Retry policy pattern
ioA.uncancelable             // Proteksi blok kritis dari pembatalan eksternal
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Bagian A: Pilihan Ganda (Basic)

**Soal 1:** Mengapa kode `val f = Future(println("A")); val p = for { _ <- f; _ <- f } yield ()` hanya mencetak teks "A" satu kali?
*   A. Karena `Future` memiliki bug konkurensi di runtime JVM.
*   B. Karena `Future` memoize hasil komputasi dan langsung mengeksekusinya secara eager saat dideklarasikan, melanggar referential transparency.
*   C. Karena for-comprehension pada Scala selalu mengeliminasi baris duplikat.
*   D. Karena thread pool Scala memblokir pemanggilan fungsi `println`.

**Soal 2:** Apa perbedaan utama antara alokasi OS Thread konvensional dengan Fiber pada sistem efek?
*   A. OS Thread berjalan di dalam heap JVM, sedangkan Fiber berjalan di memory stack CPU.
*   B. Fiber dikelola oleh kernel sistem operasi, sedangkan Thread dikelola oleh compiler.
*   C. Fiber dialokasikan di memory heap dengan ukuran beberapa ratus byte tanpa alokasi OS stack frame terpisah.
*   D. Tidak ada perbedaan, Fiber hanyalah nama alias (type alias) untuk `java.lang.Thread`.

**Soal 3:** Kapan sebaiknya Anda menggunakan konstruktor `IO.blocking(...)` alih-alih `IO(...)` biasa?
*   A. Ketika Anda ingin menjalankan kode matematika murni secepat mungkin.
*   B. Ketika memanggil operasi I/O yang bersifat blocking secara sinkron (seperti JDBC klasik atau operasi disk lawas) agar tidak menguras thread pada Compute Pool.
*   C. Ketika Anda ingin Fiber tidak dapat dibatalkan (*uncancelable*).
*   D. Ketika Anda ingin memaksa eksekusi berjalan di thread UI.

**Soal 4:** Tipe data apa yang dirancang oleh Typelevel Cats Effect untuk menjamin alokasi dan pelepasan resource secara deterministik (*bracket pattern*)?
*   A. `scala.util.Using`
*   B. `cats.effect.IO.Sync`
*   C. `cats.effect.Resource`
*   D. `java.lang.AutoCloseable`

**Soal 5:** Apa yang terjadi jika Fiber induk (*parent*) dibatalkan, sementara ia memiliki beberapa Fiber anak (*children*) yang dihasilkan melalui struktur konkurensi terstruktur (*structured concurrency*)?
*   A. Fiber anak akan terus berjalan tanpa batas (*orphan process*).
*   B. Seluruh JVM runtime akan otomatis melakukan `System.exit(1)`.
*   C. Runtime secara otomatis menyebarkan sinyal pembatalan ke seluruh Fiber anak dan menjalankan finalizer pembersihan masing-masing.
*   D. Runtime melempar `NullPointerException`.

---

### Bagian B: Analisis Kasus & Tracing Kode (Intermediate)

**Soal 6:** Analisis cuplikan kode berikut. Apakah kode ini aman terhadap kebocoran stack (*stack-safe*)? Jelaskan mekanismenya!
```scala
def countdown(n: Long): IO[Unit] = {
  if (n <= 0) IO.println("Done")
  else IO.println(s"Tick: $n") >> countdown(n - 1)
}
```

**Soal 7:** Perhatikan kode di bawah ini. Apakah baris pembersihan database pasti dieksekusi jika request HTTP terputus di tengah jalan akibat *timeout*?
```scala
val queryWithCleanup = for {
  _ <- db.openConnection()
  _ <- db.runLongQuery().timeout(2.seconds)
  _ <- db.closeConnection()
} yield ()
```
Identifikasi kelemahannya dan tuliskan perbaikannya menggunakan `cats.effect.Resource`!

**Soal 8:** Apa implikasi penggunaan operator `IO.race` terhadap efek yang kalah dalam balapan? Bagaimana runtime menangani efek yang kalah tersebut?

**Soal 9:** Mengapa pemanggilan `IO.sleep(1.minute)` tidak mengonsumsi daya komputasi CPU dan tidak menahan thread fisik JVM selama 1 menit tersebut? Jelaskan arsitektur penjadwalannya!

**Soal 10:** Telusuri keluaran dari program berikut dan jelaskan urutan eksekusinya:
```scala
val task = for {
  ref <- Ref.of[IO, Int](0)
  _   <- ref.update(_ + 1)
  v1  <- ref.get
  fib <- (ref.update(_ + 10) >> ref.get).start
  v2  <- ref.get
  v3  <- fib.joinWithNever
} yield (v1, v2, v3)
```

---

### Kunci Jawaban & Rubrik Penilaian

**Jawaban Bagian A:**
1.  **B** — `Future` mengevaluasi ekspresi secara eager dan me-memoize hasilnya, sehingga panggilan kedua hanya membaca memori *cached*, melanggar transparansi referensial.
2.  **C** — Fiber berukuran sangat ringan ($\sim 200\text{ bytes}$) pada memori Heap dan dijadwalkan secara logis oleh runtime, bukan oleh OS kernel.
3.  **B** — Operasi blocking sinkron harus dialihkan ke *dedicated blocking pool* agar *work-stealing compute pool* tidak mengalami saturasi (*thread starvation*).
4.  **C** — `Resource` mengabstraksikan pola acquire, use, dan release secara deterministik dan aman terhadap pembatalan (*cancellation-safe*).
5.  **C** — *Structured concurrency* menjamin hierarki eksekusi pohon serat; pembatalan induk otomatis merambat ke bawah dan memicu finalizer anak.

**Jawaban Bagian B:**
6.  **Aman (Stack-safe).** Rantai komputasi tidak dieksekusi langsung pada *call stack* JVM, melainkan diubah menjadi struktur node data `FlatMap` pada heap yang dievaluasi secara iteratif oleh run-loop *trampoline* milik Cats Effect.
7.  **Tidak Pasti Terkeskusi.** Jika `db.runLongQuery()` melampaui 2 detik, exception timeout dilempar seketika, sehingga baris ketiga `db.closeConnection()` dilewati dan koneksi bocor (*leaked*). Perbaikannya:
    ```scala
    Resource.make(db.openConnection())(_ => db.closeConnection())
      .use(conn => conn.runLongQuery().timeout(2.seconds))
    ```
8.  Efek yang kalah dalam `IO.race` akan **dibatalkan secara otomatis** oleh runtime melalui pengiriman sinyal interupsi Fiber (*cancellation token*) serta eksekusi *finalizer* pembersihan resource efek tersebut jika ada.
9.  `IO.sleep` tidak memanggil `Thread.sleep`. Ia mendaftarkan *callback trigger* pada penjadwal internal berbasis `ScheduledExecutorService` JVM (berbasis roda waktu/*hashed wheel timer*), lalu **menangguhkan (*suspends*)** Fiber dan melepaskan worker thread CPU untuk mengerjakan tugas lain sampai alarm waktu berbunyi.
10. Nilai `v1` adalah `1`. Nilai `v2` kemungkinan besar masih bernilai `1` (atau bergantung pada pergantian thread instan, tetapi umumnya `1` karena fiber baru saja di-fork). Fiber yang di-fork menambahkan 10. `joinWithNever` menangguhkan fiber utama sampai fiber target selesai dan mengembalikan hasilnya, sehingga `v3` dipastikan bernilai `11`.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Resilient Distributed File Ingestion Pipeline

Bangunlah aplikasi ingestion pipeline tingkat produksi menggunakan **Scala 3** dan **Cats Effect 3** yang mampu memproses ratusan file secara paralel dengan spesifikasi berikut:

#### Persyaratan Fungsional:
1.  **Bounded Worker Ingestion:** Baca direktori sumber yang berisi 50 file `.json` dummy.
2.  **Parallel Processing with Concurrency Cap:** Proses transformasi file secara paralel menggunakan fiber, tetapi batasi **maksimal hanya 4 file** yang diproses dalam satu waktu (manfaatkan `Semaphore` atau `parTraverseN`).
3.  **Resource Safety (Bracket Handling):** Setiap kali file dibaca, buat representasi `Resource` yang membuka file stream dan menjamin penutupan file handle (`java.io.InputStream.close()`), terlepas dari apakah proses parsing JSON sukses, melempar exception, atau terkena batasan waktu.
4.  **Resilience & Circuit Breaking:** Simulasikan bahwa proses validasi file dapat mengalami kegagalan acak (*flaky network* / bad format). Terapkan strategi *exponential backoff retry* (maksimal 3 kali percobaan) untuk setiap file yang gagal.
5.  **Graceful Shutdown Hook:** Tambahkan penanganan interupsi sinyal OS (`Ctrl+C`). Jika pengguna menghentikan aplikasi di tengah proses ingestion, aplikasi harus menunggu fiber yang sedang memproses data untuk menyelesaikan baris terakhirnya atau melepaskan file lock secara bersih sebelum JVM mati.

#### Kriteria Keberhasilan:
*   Aplikasi tidak mengalami kebocoran memori heap saat dijalankan dengan parameter JVM `-Xmx64M`.
*   Tidak ditemukan pesan log file descriptor leak.
*   Seluruh error tertangani secara fungsional tanpa memicu uncaught JVM exception stack trace liar.