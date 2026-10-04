# BAB 08: Quiz, Challenge, & Knowledge Check
**Functional Effect Systems (Cats Effect & ZIO)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Prinsip *Programs as Values* dan *Referential Transparency*
Dalam paradigma pemrograman fungsional murni, ekspresi `val a = println("hello")` melanggar *Referential Transparency* (RT), sedangkan `val b = IO(println("hello"))` (Cats Effect) atau `val c = ZIO.succeed(println("hello"))` mempertahankan RT.
* **Pertanyaan:** Jelaskan secara matematis dan operasional mengapa substitusi `(a, a)` menghasilkan perilaku yang berbeda secara komputasi dibandingkan substitusi `(b, b)`! Bagaimana konsep pemisahan antara *deskripsi komputasi* (*effect declaration*) dan *eksekusi komputasi* (*effect interpretation*) mendasari stabilitas sistem terdistribusi?

### Soal 1.2: Anatomi dan Mekanisme *Green Threads* (Fibers)
Baik Cats Effect 3 maupun ZIO 2 mengabstraksi *OS-level thread* menjadi unit komputasi ringan yang disebut *Fiber*.
* **Pertanyaan:** Jelaskan perbedaan fundamental antara Fiber dan OS Thread dalam hal:
  1. Alokasi memori (*heap footprint* vs *call stack* tetap),
  2. Mekanisme *context switching* dan implikasinya terhadap *CPU cache invalidation*,
  3. Model *scheduling* (mengapa model *work-stealing pool* dipilih secara universal untuk runtime fiber).

### Soal 1.3: Semantik Manajemen Sumber Daya (*Safe Finalization*)
Operasi I/O rentan terhadap kebocoran sumber daya (*resource leaks*) saat terjadi *interruption* atau *unhandled errors*.
* **Pertanyaan:** Bandingkan bagaimana `cats.effect.Resource` (Cats Effect) dan `ZIO.acquireReleaseWith` / `Scope` (ZIO) menjamin eksekusi *finalizer* (pelepasan sumber daya). Mengapa blok `try-finally` standar Java tidak memadai untuk menangani pembatalan komputasi asinkron (*asynchronous cancellation*) pada tingkat Fiber?

### Soal 1.4: *Structured Concurrency* vs *Unstructured Concurrency*
*Unstructured concurrency* (misalnya penggunaan `scala.concurrent.Future` atau `java.lang.Thread`) kerap memicu fenomena *orphan processes*.
* **Pertanyaan:** Definisikan prinsip *Structured Concurrency*. Jelaskan bagaimana struktur *parent-child hierarchy* pada ZIO atau pengikatan *lifecycle* berbasis combinator (`parTraverse`, `race`) pada Cats Effect menjamin bahwa tidak ada Fiber anak yang tetap hidup (*leaked*) saat Fiber induk mengalami kegagalan (*failure*) atau dibatalkan (*cancellation*).

### Soal 1.5: Dualitas Model Error: Expected Errors vs Defect
ZIO secara eksplisit membedakan error melalui tipe `ZIO[R, E, A]`, sementara Cats Effect menggunakan tipe `IO[A]` yang secara implisit mengasumsikan error bertipe `Throwable` (setara dengan `IO[Throwable, A]`).
* **Pertanyaan:** Jelaskan konsep *Bifunctor Error Model* pada ZIO (perbedaan antara *Failure/Expected Error* kanal `E` dan *Defect/Die*). Apa konsekuensi arsitektural dari keputusan Cats Effect yang mempertahankan `IO[A]` terunifikasi terhadap penanganan *typed errors* dan integrasi dengan paradigma *Tagless Final*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis *Thread Starvation* pada Compute Pool
Perhatikan cuplikan kode Cats Effect 3 berikut yang dieksekusi di bawah beban produksi 10.000 request per detik:
```scala
def fetchUserData(id: UserId): IO[UserData] = IO {
  // JDBC Call sinkron dan memblokir thread
  val connection = dataSource.getConnection()
  val statement = connection.prepareStatement("SELECT * FROM users WHERE id = ?")
  statement.setString(1, id.value)
  val rs = statement.executeQuery()
  parseResultSet(rs)
}
```
* **Pertanyaan:** Mengapa kode di atas menyebabkan degradasi latensi total (*cascading failure*) pada seluruh aplikasi, termasuk pada endpoint yang tidak mengakses database? Bedakan secara teknis penanganan masalah ini menggunakan `IO.blocking` vs `IO.interruptible` pada Cats Effect (atau `ZIO.attemptBlocking` vs `ZIO.attemptBlockingInterrupt` pada ZIO), serta jelaskan peran alokasi thread pool internal (*compute pool* vs *blocking pool*).

### Soal 2.2: Mekanisme *Cooperative Yielding* dan *Fairness*
Sebuah Fiber menjalankan komputasi matematika intensif CPU tanpa melakukan operasi I/O:
```scala
def computePrimes(n: Long): IO[List[Long]] = ... // Pure CPU-bound tight loop
```
* **Pertanyaan:** Bagaimana runtime engine Cats Effect 3 dan ZIO 2 mendeteksi Fiber yang memonopoli thread (*starvation of other fibers*)? Jelaskan mekanisme *instruction counter / fuel limit* (*auto-yielding*) dan kapan seorang engineer harus secara manual menyisipkan `IO.cede` atau `ZIO.yieldNow`.

### Soal 2.3: Operasi *Masking* dan *Cancellation Semantics*
Pada Cats Effect, penanganan *cancellation* tingkat lanjut melibatkan tipe `Poll[IO]` dan combinator `IO.uncancelable`:
```scala
def transferBalance(from: Account, to: Account, amount: BigDecimal): IO[Unit] =
  IO.uncancelable { poll =>
    for {
      _ <- deduct(from, amount)
      _ <- poll(verifyFraud(from)).onCancel(refund(from, amount))
      _ <- credit(to, amount)
    } yield ()
  }
```
* **Pertanyaan:** Bedah eksekusi kode di atas! Apa fungsi primitif *masking* di sini? Apa yang terjadi jika Fiber dibatalkan saat mengeksekusi `deduct`, saat mengeksekusi `verifyFraud`, dan saat mengeksekusi `credit`? Apa ancaman fatal jika `poll` disalahgunakan di dalam blok `uncancelable`?

### Soal 2.4: *State Corruption* dan Batasan Abstraksi `Ref`
Dua buah Fiber mengeksekusi mutasi state bersama (*shared state*) menggunakan `cats.effect.Ref` atau `zio.Ref`:
```scala
// Kode Anti-Pattern
for {
  current <- balanceRef.get
  _       <- if (current >= amount) balanceRef.set(current - amount) 
             else IO.raiseError(new Exception("Insufficient balance"))
} yield ()
```
* **Pertanyaan:** Tunjukkan secara presisi titik kegagalan (*race condition*) dari cuplikan kode di atas dalam lingkungan konkuren tinggi! Mengapa `Ref.get` yang diikuti `Ref.set` melanggar hukum *linearizability*? Tuliskan solusi atomik yang benar menggunakan `modify` atau `updateAndGet`, dan jelaskan mekanisme *Compare-And-Swap* (CAS) yang mendasarinya.

### Soal 2.5: Deteksi dan Investigasi *Fiber Leaks*
Aplikasi berbasis ZIO 2 mengalami lonjakan memori (*OOM Heap Dump*) setelah beroperasi selama 48 jam. Analisis memori menunjukkan jutaan instans `zio.internal.FiberRuntime` tertahan di heap.
* **Pertanyaan:** Pola kode konkuren apa yang paling lazim menciptakan *leaked/zombie fibers*? Bagaimana metodologi pelacakan menggunakan *Fiber Dumps* (`ZIO.dumpScope` atau tooling runtime Cats Effect), dan bagaimana arsitektur penanganan *interruption* yang salah (misalnya, menelan error `InterruptedException` atau penggunaan combinator `.fork` yang tidak di-scope) dapat melumpuhkan siklus hidup Fiber?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Krisis Thread Exhaustion pada Gateway Transaksi Finansial
* **Konteks:** Sistem API Gateway backend berbasis Cats Effect 3 dan Http4s memproses rata-rata 15.000 transaksi pembayaran per detik. Sistem menggunakan Postgres melalui Doobie/HikariCP.
* **Gejala:** Saat terjadi lonjakan latensi di sisi database (karena *table lock* sementara), seluruh instans API Gateway berhenti merespons health check `/healthz`. Kubernetes liveness probe gagal, memicu *rolling restart* massal yang berujung pada status *CrashLoopBackOff*. Metrik JVM menunjukkan CPU utilization turun mendekati 5%, namun active OS threads mencapai batas OS limit (32.768 threads).
* **Hasil Diagnostik Awal:** Ditemukan bahwa integrasi logging eksternal dan HTTP call ke payment provider pihak ketiga menggunakan library Apache HttpClient (berbasis synchronous blocking IO) yang dipanggil langsung di dalam rantai `for-comprehension` tanpa `IO.blocking`.
* **Pertanyaan Diagnostik:**
  1. Jelaskan rantai kausalitas (*causal chain*) bagaimana kombinasi database latency spike dan *unbounded synchronous blocking calls* mematikan seluruh pool Cats Effect (`IORuntime.global`)!
  2. Rancang strategi perbaikan arsitektur thread pool secara komprehensif, mencakup isolasi HikariCP connection pool, mitigasi HTTP client blocking pool, dan pengaturan batas aman (*thread ceiling*) untuk mencegah saturasi level kernel.
  3. Bagaimana Anda memastikan endpoint `/healthz` tetap responsif meskipun seluruh sistem downstream mengalami outage total?

### Skenario B: Race Condition dan Deadlock pada Distributed Lock Manager
* **Konteks:** Sebuah sistem alokasi kursi konser berbasis ZIO 2 mengelola inventaris tiket menggunakan state in-memory yang disinkronisasi melalui kombinasi `Ref` dan `Promise` (ZIO Promise).
* **Gejala:** Di bawah beban 50.000 request bersamaan untuk 100 kursi yang sama, beberapa pengguna dilaporkan berhasil melakukan pembayaran untuk kursi yang identik (*double-booking*). Selain itu, sekitar 10% request mengalami *infinite hang* (tidak pernah timeout, memakan resource koneksi HTTP ingress hingga habis).
* **Potongan Kode Bermasalah:**
  ```scala
  case class SeatReservation(isLocked: Ref[Boolean], awaitPayment: Promise[Nothing, Boolean])
  
  def reserveSeat(seat: SeatReservation, userId: UserId): ZIO[Any, ReservationError, Unit] = {
    for {
      locked <- seat.isLocked.get
      _      <- if (!locked) {
                  seat.isLocked.set(true) *>
                  seat.awaitPayment.await.timeout(5.minutes).flatMap {
                    case Some(true)  => finalizeBooking(userId)
                    case _           => seat.isLocked.set(false)
                  }
                } else {
                  ZIO.fail(SeatAlreadyReserved)
                }
    } yield ()
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Bedah secara mendalam dua cacat desain fatal pada kode di atas: mengapa *double-booking* tetap terjadi, dan apa penyebab pasti terjadinya kondisi *fiber deadlock / permanent hanging*?
  2. Rekonstruksi implementasi di atas menggunakan koordinasi konkurensi fungsional yang benar. Gunakan struktur data konkuren yang aman (`Ref.modify`, `Deferred`/`Promise`, atau STM - *Software Transactional Memory*) dengan jaminan *zero double-booking* dan penanganan timeout/cancellation yang mengembalikan state kursi ke posisi awal secara deterministik.

### Skenario C: Migrasi Arsitektur Monolitik: Cats Effect 3 vs ZIO 2
* **Konteks:** Organisasi perbankan digital skala besar berencana memodernisasi *Core Banking Ledger* mereka dari arsitektur Akka Classic/Imperative Scala 2.13 ke arsitektur *Pure Functional Asynchronous* pada Scala 3.
* **Trade-off Sistem:**
  * Tim A mengusulkan **Cats Effect 3 + Tagless Final (`F[_]`) + fs2 + http4s**.
  * Tim B mengusulkan **ZIO 2 + Layered Architecture (`ZLayer`) + ZIO Streams + zio-http**.
* **Karakteristik Beban Kerja:** 
  * Transaksi ledger keuangan dengan audit ketat,
  * Latensi p99 harus < 15ms,
  * Tim rekayasa terdiri dari 40 engineer dengan latar belakang dominan OOP/Java Enterprise dan 5 engineer Functional Programming tingkat lanjut.
* **Pertanyaan Diagnostik:**
  1. Evaluasi kedua pendekatan ditinjau dari:
     * *Ergonomics & Learning Curve* bagi tim dengan latar belakang OOP,
     * *Compile-time overhead* (analisis *macro expansion*, type resolution cost dari Tagless Final vs ZIO Environment),
     * Kemudahan melakukan *Dependency Injection* dan pengujian modular (*unit/integration test mocking*).
  2. Bandingkan bagaimana kedua stack menangani *distributed tracing* (OpenTelemetry context propagation) di seluruh boundary Fiber asinkron. Manakah sistem yang menyediakan isolasi konteks eksekusi (*fiber-local state*) yang lebih minim alokasi heap dan tahan terhadap *interruption leak*?
  3. Berikan rekomendasi arsitektural final yang definitif (pilih salah satu atau model hibrida terjustifikasi), lengkap dengan rencana mitigasi risiko untuk stack yang Anda pilih.

---

## 4. Chapter Challenge

### Tantangan Praktis: Membangun Resilient Multi-Tenant Token Bucket Rate-Limiter Engine

#### Problem
Anda diminta untuk mengimplementasikan sebuah mesin *Rate Limiter* konkuren multi-tenant berbasis algoritma *Token Bucket* dengan fungsionalitas *Leaky-Bucket burst handling* tanpa menggunakan locking berbasis OS (`synchronized`, `ReentrantLock`, `Semaphore` java murni). Mesin ini harus menjamin keamanan konkuren penuh (*thread-safe* & *fiber-safe*), hemat alokasi heap, serta mendukung pembatalan Fiber secara mulus.

#### Requirements
1. **State Management Tanpa Lock:**
   * Gunakan `cats.effect.Ref` atau `zio.Ref` untuk mengelola state bucket setiap *tenant*.
   * State harus mencakup: `tokensAvailable: Double`, `lastRefillTimestamp: Long`.
2. **Dynamic Refill Algorithm:**
   * Pengisian token tidak boleh menggunakan background thread/fiber terpisah per tenant (untuk mencegah OOM jutaan tenant). Refill harus dihitung secara *lazy* dan deterministik berdasarkan delta waktu saat request masuk via `Ref.modify`.
3. **Throttling & Backpressure:**
   * Jika token tidak mencukupi, fungsi `acquire(tenantId: TenantId, tokens: Int)` tidak langsung gagal, melainkan menangguhkan Fiber (*semantic blocking/sleep*) sesuai waktu tunggu yang diperlukan untuk regenerasi token, maksimal hingga batas `maxWaitTime`.
   * Jika waktu tunggu melampaui `maxWaitTime`, batalkan penangguhan dan fail-fast dengan error `RateLimitExceededException`.
4. **Interruption & Cancellation Safety:**
   * Jika Fiber pemanggil dibatalkan saat sedang menunggu token dalam antrean (*suspended*), sistem harus membersihkan state antrean internal tanpa merusak integritas perhitungan token tenant.
5. **Observability Hook:**
   * Emisikan metrik status rate limit secara non-blocking menggunakan channel fungsional murni (`cats.effect.std.Queue` atau `zio.Queue`).

#### Constraints
* **Pure Functional Code:** Nol penggunaan mutable state (`var`), nol interaksi langsung dengan thread fisik (`Thread.sleep`), nol unsafe execution (`unsafeRunSync` dilarang keras di dalam domain logic).
* **Stack:** Pilihlah salah satu secara konsisten: **Cats Effect 3** atau **ZIO 2**. Dilarang mencampur dependensi keduanya dalam implementasi ini.
* **Scala Version:** Scala 3 (disarankan) atau Scala 2.13.

#### Expected Output
* Kode modular yang mencakup:
  1. Definisi model data (`TenantId`, `RateLimitConfig`, `RateLimiterState`).
  2. Trait antarmuka `RateLimiter[F[_]]` (jika Cats Effect) atau antarmuka `RateLimiter` berbasis ZIO.
  3. Implementasi engine konkret.
  4. Test suite komprehensif (menggunakan *Cats Effect Testkit* atau *ZIO Test*) yang membuktikan:
     * Akurasi token refill matematika.
     * Zero-leak pada Fiber cancellation.
     * Eksekusi konkuren paralel 1.000 Fiber bersaing mengambil token dari tenant yang sama.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Makna filosofis dan matematis dari *Programs as Values* serta perbedaannya dengan *Eager Execution* (`Future`).
- [ ] Siklus hidup Fiber (*Suspended*, *Running*, *Done*, *Interrupted/Canceled*) pada runtime Cats Effect 3 dan ZIO 2.
- [ ] Mengapa *Thread Starvation* terjadi dan bagaimana mekanisme *work-stealing scheduler* bekerja di balik layar.
- [ ] Perbedaan fundamental antara `IO.blocking` (isolasi blocking call) dan `IO.interruptible` (blocking call dengan sinyal interupsi thread OS).
- [ ] Aturan operasi *Masking* (`IO.uncancelable`, `ZIO.uninterruptible`) dan peranan `poll` dalam mencegah *uninterruptible deadlocks*.
- [ ] Teori konkurensi atomik: Cara kerja *Compare-And-Swap* (CAS) pada `Ref` dan batas penggunaannya sebelum beralih ke STM (*Software Transactional Memory*).
- [ ] Mekanisme propagasi error dan interupsi pada *Structured Concurrency* (interupsi kaskade pada *parent-child failure*).
- [ ] Implikasi performa alokasi closure pada monadic chain (`flatMap`) berbanding optimasi runtime (*instruction unrolling*).

### Saya tidak perlu menghafal:
- [ ] Kode heksadesimal atau implementasi internal bit-shifting dari fiber execution flags di level kernel CE/ZIO runtime.
- [ ] Seluruh signature method spesifik dari combinator eksperimental Cats Effect / ZIO yang jarang digunakan di level arsitektur core.
- [ ] Sintaks mikro-library wrapper pihak ketiga yang membungkus Java NIO selama memahami kontrak asinkron dasarnya.

### Saya harus bisa melakukan:
- [ ] Mendiagnosis insiden *thread starvation* dari pembacaan visual *JVM Thread Dump* dan *Fiber Dump*.
- [ ] Menulis modul I/O berbasis integrasi library legacy Java tanpa mencemari pool eksekusi komputasi utama.
- [ ] Mengimplementasikan *safe acquisition & release* untuk koneksi database, file descriptor, dan socket jaringan menggunakan `Resource` atau `Scope`.
- [ ] Mengabstraksi stateful concurrency menggunakan kombinasi murni `Ref`, `Deferred`/`Promise`, dan `Queue`.
- [ ] Mendesain arsitektur aplikasi backend end-to-end yang bersih dari `unsafeRunSync` kecuali pada boundary tunggal `IOApp` / `ZIOAppDefault`.
- [ ] Menulis integration test konkuren non-deterministik menggunakan manipulasi waktu virtual (*TestClock*).