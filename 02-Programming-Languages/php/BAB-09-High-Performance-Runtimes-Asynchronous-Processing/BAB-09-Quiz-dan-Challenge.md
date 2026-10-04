# BAB 09: Quiz, Challenge, & Knowledge Check
**High-Performance Runtimes & Asynchronous Processing**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Paradigma Shared-Nothing vs. Persistent In-Memory Runtime
Jelaskan perbedaan mendasar antara siklus hidup (*lifecycle*) eksekusi PHP-FPM berbasis *shared-nothing architecture* dengan *long-running persistent runtimes* (seperti RoadRunner, FrankenPHP, atau Swoole). Analisis bagaimana alokasi Zend Engine memory heap, inisialisasi *superglobals*, dan proses *bootstrapping framework* (misalnya Service Container) dipengaruhi oleh transisi dari model *ephemeral* ke model *persistent*.

### Soal 1.2: Anatomi dan Primitif PHP 8.1+ Fibers
PHP 8.1 memperkenalkan *Fibers* sebagai mekanisme *concurrency* bawaan. Mengapa Fiber diklasifikasikan sebagai *stackful asymmetric coroutine* berorientasi primitif *low-level*, dan bukan *asynchronous runtime engine* yang berdiri sendiri? Jelaskan relasi antara eksekusi `Fiber::suspend()` dan `Fiber::resume()` terhadap kontrol *call stack* pada Zend VM.

### Soal 1.3: Event-Driven Architecture & Non-Blocking I/O
Uraikan mekanisme kerja *Event Loop* (berbasis abstraction library seperti `libuv`, `libev`, atau native *system call* `epoll`/`kqueue`) dalam menangani operasi I/O di PHP. Bagaimana *stream wrapper* non-blocking dan event multiplexing mencegah worker thread/process mengalami *blocking state* saat menunggu respon jaringan atau I/O disk?

### Soal 1.4: Fenomena State Pollution dalam Persistent Worker
Definisikan apa yang dimaksud dengan *state pollution* (pencemaran state) dalam konteks long-running PHP runtime. Berikan penjelasan mengapa penggunaan properti `static`, instansiasi *Singleton* tanpa mekanisme pembersihan (*resetter*), dan mutasi variabel global dapat memicu *critical bug* kebocoran data antar-permintaan (*cross-request data leakage*) dan *memory leak*.

### Soal 1.5: Concurrency vs. Parallelism dalam Konteks Zend Engine
Zend Engine secara tradisional didesain untuk eksekusi *single-threaded* per konteks eksekusi. Jelaskan perbedaan teknis antara *concurrency* (seperti yang dicapai melalui Coroutine/Event Loop) dan *parallelism* (seperti yang dicapai melalui ekstensi `parallel` atau model *multi-worker process*). Mengapa coroutine tidak serta-merta memanfaatkan multi-core CPU secara simultan untuk komputasi CPU-bound?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Context Switching & Coroutine Scheduler Mechanics
Pada engine seperti Swoole atau framework berbasis Revolt (PHP Fibers), bagaimana *Scheduler* menentukan kapan suatu coroutine harus di-*yield* dan coroutine lain di-*resume*? Jelaskan risiko terjadinya *starvation* (kelaparan proses) jika developer mengeksekusi fungsi CPU-bound yang intensif (seperti enkripsi atau parsing JSON gigantis) di tengah-tengah alur kerja coroutine, serta bagaimana strategi mitigasinya.

### Soal 2.2: Koneksi Database, Interleaving, dan Coroutine-Safe Connection Pool
Mengapa satu instansi `PDO` atau MySQL client bawaan PHP tidak boleh dibagikan (*shared*) secara paralel ke lebih dari satu coroutine yang berjalan secara *concurrent*? Uraikan konsekuensi *packet interleaving* pada protokol layer transport database dan jelaskan arsitektur internal dari *Coroutine-Safe Connection Pool* (mekanisme `acquire`, `release`, `idle timeout`, dan *channel queue*).

### Soal 2.3: Zend Memory Manager (ZMM) & Deteksi Memory Leak Sistemik
Pada aplikasi PHP-FPM, memory leak minor sering kali tertutupi oleh pembersihan total pada fase `RSHUTDOWN`. Namun, pada persistent runtime, memory leak berakibat fatal. Jelaskan mengapa pemanggilan `gc_collect_cycles()` sering kali gagal mereklamasi memori yang bocor pada persistent worker. Bagaimana Anda mendeteksi dan mengisolasi akumulasi referensi sirkular (*circular reference leaks*) serta alokasi native C-extension menggunakan profiling tool (seperti Valgrind, Xdebug Memory Trace, atau Blackfire)?

### Soal 2.4: FrankenPHP CGO Bridge & Worker Lifecycle
FrankenPHP memanfaatkan integrasi Caddy (ditulis dalam Go) dan PHP core melalui CGO. Analisis bagaimana thread Go berkomunikasi dengan thread Zend Engine. Bagaimana penanganan *crash* (seperti `fatal error`, `segfault`, atau pemanggilan fungsi `exit()`/`die()`) diisolasi agar tidak meruntuhkan (*teardown*) keseluruhan HTTP server Caddy?

### Soal 2.5: Zero-Downtime Deployment & Graceful Worker Recycling
Dalam arsitektur *Master-Worker* (seperti RoadRunner atau Master Process Swoole), jelaskan mekanisme pertukaran sinyal POSIX (`SIGTERM`, `SIGHUP`, `SIGUSR1`, `SIGUSR2`) untuk memfasilitasi *graceful reload*. Bagaimana process manager memastikan *in-flight requests* selesai diproses secara tuntas tanpa menerima koneksi baru sebelum worker lama di-destruksi dan worker baru di-*spawn*?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Degradation & Out-of-Memory (OOM) Killer di Layanan Transaksi Tinggi
* **Konteks:** Sebuah microservice transaksi keuangan memproses 3.500 req/sec menggunakan RoadRunner dengan 16 worker PHP. Pada saat peluncuran, latensi p99 berada di angka 12ms. Namun, setelah berjalan tanpa henti selama 10 jam di lingkungan produksi, terjadi degradasi performa bertahap: latensi p99 melonjak hingga 1.800ms, CPU usage konstan di angka 100%, dan Linux kernel OOM-killer secara periodik membunuh proses worker.
* **Gejala Tambahan:** Log monitoring menunjukkan penggunaan memori worker meningkat linear sebesar 4MB per 10.000 transaksi. Mekanisme `max_requests` belum dikonfigurasi pada RoadRunner.
* **Pertanyaan Diagnostik:**
  1. Identifikasi 3 kemungkinan sumber kebocoran memori pada level framework/aplikasi yang resisten terhadap Garbage Collector PHP di model persistent worker.
  2. Mengapa latensi melonjak tajam seiring meningkatnya penggunaan memori sebelum proses akhirnya dibunuh oleh OOM Killer? (Hubungkan dengan mekanisme *GC cycle collection runs* dan alokasi ZMM heap).
  3. Rancang rencana remediasi arsitektur dan operasional, mencakup konfigurasi RoadRunner, *profiling strategy*, dan implementasi interface resetter pada IoC container.

---

### Skenario B: Cross-Session Data Corruption pada Concurrent Checkout Flash Sale
* **Konteks:** Platform e-commerce berskala regional menggunakan Swoole Coroutine HTTP Server untuk menangani lonjakan *traffic* Flash Sale. Pada saat traffic mencapai 20.000 req/sec, tim QA dan Customer Service melaporkan keluhan aneh dari pelanggan:
  * Pelanggan A berhasil checkout, namun alamat pengiriman dan nama di invoice tercetak atas nama Pelanggan B.
  * Terdapat beberapa transaksi di mana saldo dompet digital pelanggan terpotong dua kali untuk satu ID pesanan yang sama.
* **Cuplikan Kode Aplikasi:**
  ```php
  class CheckoutService {
      private static ?CustomerContext $currentCustomer = null;
      private PDO $db; // Diinjeksikan sebagai Shared Service via Singleton Container

      public function handleCheckout(array $payload): void {
          self::$currentCustomer = new CustomerContext($payload['customer_id'], $payload['address']);
          
          // Non-blocking I/O via Coroutine
          $balance = $this->fetchBalance(self::$currentCustomer->getId());
          
          if ($balance >= $payload['amount']) {
              // Yield execution ke I/O lain
              $this->deductBalance(self::$currentCustomer->getId(), $payload['amount']);
              $this->createOrder(self::$currentCustomer);
          }
      }
  }
  ```
* **Pertanyaan Diagnostik:**
  1. Bedah secara detail dua sumber cacat fatal (*fatal architectural flaws*) pada kode di atas yang memicu *race condition* dan *cross-session data corruption* saat dieksekusi di bawah *concurrent coroutine runtime*.
  2. Jelaskan urutan eksekusi (*interleaved execution timeline*) yang memungkinkan mutasi variabel `self::$currentCustomer` ditimpa oleh Request B saat Request A sedang menunggu respons I/O dari `fetchBalance()`.
  3. Tuliskan refaktor arsitektur kelas ini agar *strictly stateless*, aman terhadap eksekusi paralel/konkuren, dan terisolasi per siklus *request scope*.

---

### Skenario C: Trade-off Migrasi Monolit Legasi ke FrankenPHP Worker Mode
* **Konteks:** Tim Engineering perusahaan logistik enterprise berencana memigrasikan monolit Laravel berukuran besar yang berjalan di atas PHP-FPM klasik (120 node server) ke FrankenPHP *Worker Mode* demi memangkas biaya infrastruktur AWS sebesar 50% dan menekan latensi *cold-start bootstrapping*. Namun, basis kode tersebut telah berumur 7 tahun, memiliki lebih dari 400 package dependensi pihak ketiga via Composer, dan sarat dengan penggunaan global helpers, facade calls, dan stateful custom cache driver.
* **Pertanyaan Diagnostik:**
  1. Lakukan *architectural risk assessment*: Apa saja potensi *breaking failure* paling kritis yang dapat merusak integritas data monolit ini ketika dipindahkan ke *Worker Mode*?
  2. Jika perusahaan tidak memiliki waktu untuk merefaktor seluruh 400 dependensi Composer, strategi isolasi, *blacklisting*, atau *sandbox boundary* apa yang harus diterapkan pada FrankenPHP agar sistem tetap stabil?
  3. Buat matriks keputusan (Decision Matrix) komparatif antara: (a) Tetap di PHP-FPM teroptimasi (OPcache Preloading + JIT), (b) FrankenPHP Worker Mode, dan (c) RoadRunner. Tentukan opsi paling rasional untuk kasus ini berdasarkan metrik *maintainability*, *fault tolerance*, dan *operational complexity*.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Async Webhook Ingestion Engine & Coroutine-Safe Storage Pipeline

#### Deskripsi Masalah
Perusahaan payment gateway Anda menerima lonjakan *webhook callback* notifikasi transaksi hingga 10.000 req/sec dari berbagai institusi perbankan. Setiap webhook harus divalidasi keabsahan signature kriptografisnya, diperiksa idempotensinya via storage layer, dicatat ke log audit database, dan dikirimkan ke downstream queue. Implementasi lama berbasis PHP-FPM mengalami kegagalan massal (*504 Gateway Timeout* dan kehabisan *FPM child processes*) karena dependensi *upstream network I/O* yang memiliki latensi bervariasi antara 50ms hingga 800ms.

#### Spesifikasi Kebutuhan & Fungsionalitas
1. **Runtime Framework:** Gunakan persistent async runtime pilihan Anda (Swoole, OpenSwoole, FrankenPHP Worker Mode, atau AMPHP/Revolt v1.x).
2. **Stateless HTTP Ingestion:** Buat HTTP Endpoint `/webhook/ingest` yang mampu menerima HTTP POST JSON payload secara asinkron tanpa memblokir thread/worker lain.
3. **Async Signature Verification:** Simulasikan validasi signature kriptografi non-blocking atau asynchronous I/O remote call (misal: verifikasi public-key perbankan eksternal via async HTTP client dengan batas timeout 300ms).
4. **Coroutine-Safe Persistence Pool:** 
   * Implementasikan atau konfigurasikan *Connection Pool* untuk persistence layer (misalnya database PostgreSQL/MySQL atau in-memory Redis).
   * Connection pool harus memiliki konfigurasi batas minimum koneksi (*idle*), batas maksimum (*capacity*), penanganan antrean (*wait queue*) saat pool penuh, dan *heartbeat check* koneksi stale.
5. **Memory Leak Prevention & Worker Watchdog:**
   * Terapkan mekanik *Context Cleanup* terstandarisasi untuk menjamin tidak ada residu data transaksi per request.
   * Rancang *Memory Threshold Watchdog* di dalam aplikasi: jika penggunaan memori worker melampaui batas ambang tertentu (misal: 128MB), trigger mekanisme *graceful worker self-retirement/recycling* setelah memproses request yang sedang aktif.

#### Batasan Teknis (Constraints)
* **Zero Shared Global State:** Dilarang keras menggunakan superglobals (`$_POST`, `$_GET`, `$_SESSION`, dll.) atau static property mutable tanpa abstraksi thread-safe.
* **Strict Non-blocking:** Tidak boleh ada pemanggilan native library yang bersifat blocking I/O (seperti `file_get_contents()` ke URL, `sleep()`, atau query `PDO` standar tanpa coroutine pooling/wrapping).
* **Defensive Resilience:** Sistem harus dapat bertahan jika downstream database mengalami kelambatan (*slow query* spike) tanpa menyebabkan memori server jebol (*circuit breaking* atau *backpressure* sederhana).

#### Output yang Diharapkan
1. **Arsitektur Diagram & Alur:** Penjelasan tekstual atau diagram alir siklus hidup request dari socket listening hingga storage persistence.
2. **Source Code Terpadu:**
   * Definisi Entry Point Runtime Server.
   * Modul Implementasi Coroutine-safe Connection Pool.
   * Handler Request Pipeline (Signature Verification -> State Isolation -> Storage Write -> Response).
   * Modul Worker Lifecycle Watchdog & Memory Monitoring.
3. **Analisis Benchmark & Stress-Test Simulation Plan:**
   * Metodologi pengujian konkurensi (misal: menggunakan tool seperti `wrk`, `k6`, atau `vegeta`).
   * Parameter profiling untuk membuktikan ketiadaan memory leak selama pemrosesan 500.000 requests.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi siklus hidup PHP-FPM vs. Long-running persistent worker (RoadRunner, FrankenPHP, Swoole).
- [ ] Perbedaan fundamental arsitektur stackful coroutine (PHP Fibers) dibanding event loop callbacks/promises.
- [ ] Risiko fatal mutable static state, memory fragmentation, dan Zend Memory Manager (ZMM) leaks pada persistent runtime.
- [ ] Mekanisme kerja epoll/kqueue multiplexing dan abstraksi non-blocking stream wrappers di PHP.
- [ ] Mengapa database driver konvensional (Blocking PDO) memerlukan Connection Pool khusus atau async driver dalam lingkungan coroutine.
- [ ] Protokol komunikasi process manager (Master-Worker model) via UNIX Domain Sockets, CGO, atau Standard I/O (Goridge).
- [ ] Pola pemisahan request context (*Request Scope vs Application Scope*) dalam Dependency Injection Container modern.
- [ ] Cara kerja Zero-Downtime Deployment dan Graceful Worker Termination melalui sinyal sistem POSIX.

### Saya tidak perlu menghafal:
- [ ] Implementasi internal C source code dari libuv atau Zend Engine fiber context switching primitives.
- [ ] Nilai integer numerik dari seluruh sinyal POSIX kernel Linux (cukup memahami fungsi `SIGTERM`, `SIGKILL`, `SIGUSR1`, dll).
- [ ] Konfigurasi byte-level flag low-level socket programming di C header files.
- [ ] Rincian sintaksis spesifik seluruh library async komunitas yang usang (cukup pahami standar modern berbasis Fibers/Revolt dan engine dominan).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan men-debug aplikasi PHP yang mengalami memory leak menggunakan profiling tools (misalnya Xdebug trace memory, `memory_get_usage(true)`, atau Blackfire).
- [ ] Mengonfigurasi dan mengoperasikan FrankenPHP atau RoadRunner di depan framework modern (Laravel/Symfony) dengan Worker Mode aktif.
- [ ] Mengimplementasikan *resetter interface* kustom untuk membersihkan service container antar-request demi mencegah *state pollution*.
- [ ] Merancang dan mengeksekusi arsitektur async non-blocking task/pipeline menggunakan PHP Fibers atau Coroutines tanpa merusak isolasi data transaksi.
- [ ] Mengonfigurasi parameter worker concurrency, auto-reload policies, dan memory limits secara presisi pada lingkungan produksi Linux container (Docker/K8s).