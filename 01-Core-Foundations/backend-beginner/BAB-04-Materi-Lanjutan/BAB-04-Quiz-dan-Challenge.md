# BAB 04: Quiz, Challenge, & Knowledge Check
**Runtime Backend & Concurrency Model**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Komparasi Primitif Eksekusi (OS Threads vs Green Threads/Goroutines)
Jelaskan perbedaan fundamental antara Kernel/OS Thread dengan User-space/Green Thread (seperti Goroutine di Go atau Virtual Thread di Java 21) ditinjau dari tiga parameter kritis:
1. Alokasi dan manajemen *stack memory* (inisialisasi awal vs ekspansi dinamis).
2. Mekanisme dan *cost* dari *context switching* (interupsi CPU, transisi *ring privilege* kernel vs *user-space cooperativeness*).
3. Batas konkurensi teoritis dan praktis pada mesin dengan spesifikasi RAM 4 GB.

### Soal 1.2: Anatomi Single-Threaded Event Loop vs Multi-Threaded Thread-per-Request
Node.js menggunakan model *single-threaded event loop* (didukung `libuv`), sedangkan server tradisional berbasis Servlet (seperti Apache Tomcat standar) mengadopsi model *thread-per-request*.
1. Mengapa model *single-threaded event loop* dapat menangani ratusan ribu koneksi I/O simultan jauh lebih hemat memori dibanding *thread-per-request*?
2. Apa kegagalan struktural terbesar yang terjadi pada *single-threaded event loop* saat dihadapkan pada tugas *CPU-bound* murni (misal: *cryptographic hashing* atau kalkulasi matriks), dan bagaimana arsitektur modern mengatasinya?

### Soal 1.3: Mekanisme Global Interpreter Lock (GIL)
Bahasa pemrograman seperti CPython dan MRI Ruby memiliki *Global Interpreter Lock* (GIL).
1. Apa alasan historis dan arsitektural implementasi GIL pada level *memory management* (terkait *reference counting*)?
2. Buktikan secara teknis mengapa menambahkan thread CPU-bound pada CPython di atas mesin multi-core justru dapat memperlambat total waktu eksekusi dibandingkan program *single-thread*, padahal CPU memiliki *core* cadangan yang menganggur.

### Soal 1.4: Spektrum I/O: Blocking, Non-Blocking, Synchronous, dan Asynchronous
Berdasarkan model I/O POSIX:
1. Bedakan secara presisi antara I/O *Synchronous Non-Blocking* (menggunakan *polling*) dengan I/O *Asynchronous* murni (*demultiplexing* via Linux `epoll` / macOS `kqueue` / Windows `IOCP`).
2. Di manakah posisi abstraksi arsitektur *Reactor Pattern* dan *Proactor Pattern* dalam menangani *I/O multiplexing* tersebut?

### Soal 1.5: Isolasi Memori: Process vs Thread vs Coroutine
1. Gambarkan peta alokasi memori (Code, Data/BSS, Heap, Stack) saat sistem operasi melakukan *forking process* baru dibandingkan saat sebuah proses melakukan *spawn thread* baru.
2. Apa konsekuensi arsitektural penggunaan memori bersama (*shared memory*) pada model *multi-threading* terhadap kebutuhan sinkronisasi, dan mengapa model *coroutine/event loop* secara inheren terbebas dari *hardware-level memory tearing* namun tetap rentan terhadap *application-level race condition*?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Kegagalan Event Loop Starvation
Perhatikan pseudocode backend berbasis Event Loop (Node.js/Python Asyncio) berikut:

```javascript
app.post("/process-data", async (req, res) => {
  const payload = req.body; // Array berisi 5.000.000 data numerik
  const sorted = payload.sort((a, b) => b - a);
  const result = complexMathematicalProjection(sorted);
  return res.json({ status: "done", result });
});
```

1. Jelaskan apa yang terjadi pada *microtask queue*, *macrotask/timer queue*, dan *I/O poll phase* selama fungsi `payload.sort()` dan `complexMathematicalProjection()` berjalan.
2. Apa dampak langsung eksekusi endpoint ini terhadap *health check* probe `/healthz` yang berjalan di rute terpisah dan diakses oleh Kubernetes Liveness Probe setiap 5 detik?
3. Rancang strategi perbaikan non-reaktif: bagaimana membagi beban komputasi tersebut agar tidak memblokir siklus Event Loop tanpa memindahkan eksekusi keluar dari runtime utama (misal: teknik *chunking/yielding* atau `worker_threads`).

### Soal 2.2: Deep Dive Go Scheduler (Model M:N / GMP)
Dalam Go Runtime, terdapat abstraksi GMP (*Goroutine, Machine/OS Thread, Processor*).
1. Jelaskan alur yang ditempuh runtime ketika sebuah Goroutine ($G$) mengeksekusi operasi sistem sinkron yang memblokir (*blocking system call*, misal: `os.Open` membaca disk lokal). Apa yang dilakukan oleh thread OS ($M$), Processor ($P$), dan Goroutine lain yang antre di *Local Run Queue* (LRQ)?
2. Bagaimana mekanisme *work stealing* dan *network poller* bekerja saat Goroutine menghadapi I/O jaringan berbasis socket dibanding I/O file disk?
3. Sejak Go 1.14, scheduler mendukung *asynchronous non-cooperative preemption*. Bagaimana sinyal OS (`SIGURG`) dimanfaatkan untuk mencegah sebuah Goroutine yang menjalankan *tight loop* (misal: `for {}`) memonopoli satu thread OS selamanya?

### Soal 2.3: Anatomi Data Race di Level CPU Assembly
Sebuah backend multi-threaded memiliki operasi sederhana: `counter++`.
1. Bedakan operasi tersebut menjadi instruksi level mesin (Assembly) x86/ARM (Read, Modify, Write).
2. Jelaskan fenomena CPU *Cache Coherency* (protokol MESI) dan *CPU instruction reordering* yang dapat menghasilkan nilai akhir salah jika operasi tersebut diakses bersamaan oleh dua thread berbeda tanpa proteksi.
3. Kapan Anda harus memilih `Atomic Operations` (Compare-And-Swap/CAS) dibanding `Mutual Exclusion (Mutex)`, dan apa penalti performa (CPU *cycles* / *bus lock*) dari masing-masing pendekatan?

### Soal 2.4: Fenomena Thread Pool Exhaustion & Cascading Failure
Sebuah microservice Java berbasis Spring Boot (Tomcat default pool: 200 thread) memanggil *downstream service* B yang mengalami peningkatan latensi dari 50ms menjadi 5000ms akibat masalah database, dengan trafik masuk konstan 100 RPS.
1. Hitung menggunakan *Little's Law* ($L = \lambda \times W$) kapan tepatnya thread pool habis total (*exhausted*).
2. Mengapa métrik penggunaan CPU pada service ini justru mendekati 0-5% saat sistem berhenti menerima *traffic* dan menghasilkan `HTTP 503` / koneksi di-*drop*?
3. Bagaimana isolasi bulkhead, *circuit breaker*, dan transisi ke arsitektur non-blocking atau Java Virtual Threads (Project Loom) memitigasi problem ini secara fundamental?

### Soal 2.5: Debugging Deadlock Menggunakan Thread Dump
Diberikan kutipan parsial dari *thread dump* Java berikut:

```text
Found one Java-level deadlock:
=============================
"OrderProcessing-Thread-1":
  waiting to lock monitor 0x00007f8a3400a120 (object 0x000000076ab21000, a com.engine.InventoryService),
  which is held by "InventoryUpdate-Thread-2"
"InventoryUpdate-Thread-2":
  waiting to lock monitor 0x00007f8a3400b340 (object 0x000000076ab21048, a com.engine.OrderService),
  which is held by "OrderProcessing-Thread-1"
```

1. Sebutkan dan jelaskan 4 kondisi *Coffman* yang wajib terpenuhi agar deadlock di atas dapat terjadi.
2. Apa prinsip *Lock Ordering* / *Resource Hierarchy*, dan bagaimana cara merefaktor kode di atas untuk menjamin kondisi deadlock tersebut mustahil terjadi secara matematis?
3. Bagaimana cara mengidentifikasi deadlock semacam ini pada runtime tanpa JVM dump native (misal di Go menggunakan `pprof` trace atau di Node.js via V8 CPU Profiler)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Kasus Insiden & Bottleneck Skala Besar
**Arsitektur:**
Payment Gateway Webhook Consumer dibangun menggunakan Node.js (v20 LTS), memproses webhook dari bank mitra dengan beban 8.000 req/sec saat gajian. Tiap *request* melakukan validasi signature HMAC-SHA256, verifikasi status di Redis, menulis audit log ke filesystem lokal (`fs.appendFile`), dan mengirim event ke Kafka.

**Gejala Masalah:**
Pada jam puncak, latensi melonjak dari 15ms ke 12.000ms. CPU server (16 Core) hanya terpakai 12% secara agregat (1 Core 100%, Core lainnya < 5%). Pod Kubernetes dinyatakan tidak sehat oleh *liveness probe* dan mulai di-*restart* berulang kali secara *cascading*.

**Pertanyaan Diagnostik:**
1. Mengapa satu Core mencapai 100% sementara 15 Core lainnya menganggur? Jelaskan peran Node.js Event Loop utama dalam kalkulasi HMAC kriptografi dan I/O parsing JSON.
2. Node.js menggunakan *libuv thread pool* (default: 4 thread) untuk operasi disk (`fs`) dan resolusi DNS. Jelaskan bagaimana `fs.appendFile` intensif dan resolusi DNS broker Kafka dapat memacetkan *thread pool* tersebut (*thread starvation*) sehingga mempengaruhi operasi lain.
3. Rancang arsitektur perbaikan menyeluruh: optimasi konfigurasi Node.js (`UV_THREADPOOL_SIZE`, clustering via PM2/Kubernetes pod autoscaling), isolasi CPU-bound tasks, dan mitigasi blocking I/O pada filesystem.

---

### Skenario B: Kasus Kegagalan Data Integrity & Race Condition
**Arsitektur:**
Sebuah platform penjualan tiket Flash Sale mengimplementasikan engine pemesanan di Golang. Saldo kuota tiket disimpan di memori lokal server aplikasi untuk mempercepat response sebelum disinkronkan ke PostgreSQL. Setiap *request* pemesanan memanggil goroutine baru untuk memverifikasi ketersediaan dan mengurangi kuota:

```go
func (s *TicketServer) HandleBooking(w http.ResponseWriter, r *http.Request) {
    go func() {
        if s.availableQuota > 0 {
            // Simulasi proses validasi user & anti-fraud
            time.Sleep(50 * time.Millisecond) 
            s.availableQuota-- 
            s.saveBookingToDB(r.Context(), s.availableQuota)
            w.WriteHeader(http.StatusOK)
        } else {
            w.WriteHeader(http.StatusBadRequest)
        }
    }()
}
```

**Gejala Masalah:**
Saat flash sale berlangsung, kuota riil tiket hanya 1.000 lembar. Namun, data di database menunjukkan 1.482 tiket berhasil diterbitkan (*overselling 48.2%*). Selain itu, sesekali server mengalami *panic crash* tak terduga dengan log yang menunjukkan korupsi *internal memory state*.

**Pertanyaan Diagnostik:**
1. Bedah secara detail dua kegagalan struktural kode di atas:
   - Terjadinya *Data Race* pada `s.availableQuota`.
   - Masalah konkurensi HTTP response writer `w` di dalam goroutine yang tidak disinkronkan (*concurrent write* ke HTTP pipe yang sudah ditutup oleh runner HTTP server utama).
2. Mengapa penggunaan `time.Sleep` secara masif memperparah probabilitas *overselling* hingga puluhan persen?
3. Tuliskan refaktor arsitektur kode menggunakan salah satu dari dua pendekatan berikut secara idiomatik di Go:
   - Pendekatan sinkronisasi memori: `sync.Mutex` atau operasi `sync/atomic`.
   - Pendekatan message passing: Komunikasi melalui antrean Go Channel (*Actor/Worker model* tanpa *shared state*).
4. Bagaimana Anda menjalankan deteksi otomatis terhadap kode berbahaya ini pada *Continuous Integration* (CI) pipeline?

---

### Skenario C: Kasus Arsitektur & Trade-Off Teknologi
**Konteks:**
Anda adalah Principal Architect yang diminta menentukan platform runtime backend untuk sistem *Telemetry Data Ingestion* IoT. Sistem harus menerima koneksi persisten WebSocket dari 1.000.000 sensor cerdas secara konkuren. Masing-masing sensor mengirim payload telemetri sebesar 256 byte setiap 30 detik. Kebutuhan komputasi per pesan sangat rendah (hanya deserialisasi dan parsing, lalu *flush* ke antrean distributed stream), namun konektivitas socket harus *idle* secara persisten di memori.

**Opsi Kandidat:**
1. **Python Asyncio (FastAPI/Uvicorn)**
2. **Node.js (Fastify/ws)**
3. **Go (Goroutines + Native Netpoll)**
4. **Java 21 (Spring Boot 3 + Virtual Threads / Project Loom)**

**Pertanyaan Analisis Komparatif:**
1. **Memory Footprint Scaling:** Analisis kebutuhan RAM dasar untuk menahan 1.000.000 *idle connections* pada masing-masing opsi (pertimbangkan ukuran stack per-koneksi, context socket struct OS, dan overhead runtime). Runtime mana yang akan gagal (OOM) paling pertama pada server dengan RAM 64 GB?
2. **Garbage Collection (GC) Pressure:** Sistem ini menghasilkan alokasi objek kecil secara terus-menerus dalam volume masif (jutaan pesan per detik total). Bandingkan karakteristik jeda *Stop-The-World (STW)* antara Go GC, Java ZGC/Shenandoah, dan V8 GC (Node.js). Mana yang memberikan konsistensi latensi (p99) paling stabil di bawah 10ms?
3. **Keputusan Akhir & Justifikasi:** Berikan rekomendasi arsitektur runtime terpilih beserta justifikasi trade-off (kemudahan rekrutmen engineer, efisiensi resource infrastructure cloud, kestabilan runtime, dan durasi pengembangan).

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Performance Concurrent Ingestion Engine dengan Backpressure**

### Deskripsi Masalah
Banyak aplikasi backend hancur bukan karena lambat memproses I/O, melainkan karena ketiadaan mekanisme *concurrency control* dan *backpressure*. Ketika beban data datang lebih cepat daripada kemampuan sistem mengeksekusinya, runtime akan mengalokasikan task tanpa batas ke memori (unbounded queue) hingga memicu *Out Of Memory* (OOM) crash atau degradasi latensi yang eksponensial.

Anda ditugaskan membangun sebuah *Concurrent Processing Engine* mandiri (menggunakan Go, Node.js, atau Java/Kotlin murni tanpa framework web berat) yang mampu memproses *stream of tasks* dengan batas sumber daya ketat.

### Requirements & Spesifikasi
1. **Task Model:**
   - Input: Stream yang menghasilkan 100.000 data task tiruan.
   - Karakteristik Task: Campuran antara 80% *Simulated Network Latency* (sleep acak 20-50ms) dan 20% *CPU Hashing Operation* (komputasi SHA-256 berulang untuk menstimulasi kerja core prosesor).
2. **Bounded Concurrency:**
   - Engine wajib membatasi batas eksekusi konkurensi paralel maksimal $N$ worker secara persis (misal: $N = 50$).
   - Tidak boleh menggunakan *unbounded queue*. Antrean penampung task (*job buffer queue*) dibatasi maksimal $M$ elemen (misal: $M = 500$).
3. **Dynamic Backpressure & Rejection Strategy:**
   - Jika *buffer queue* penuh, sistem harus menerapkan strategi backpressure: menolak task baru dengan error status (*Fail Fast*) atau menahan task generator sampai buffer memiliki kapasitas (*Rate Throttling*).
4. **Graceful Shutdown & Drain:**
   - Sistem harus menangani OS Signal (`SIGINT`/`SIGTERM`).
   - Saat sinyal diterima: berhenti menerima task baru, selesaikan seluruh task yang sudah berada di dalam antrean sampai habis (draining), cetak ringkasan eksekusi, lalu terminate secara bersih tanpa kebocoran thread/goroutine.
5. **Observability Metrics (Cetak berkala tiap 1 detik):**
   - Active Workers count.
   - Tasks completed vs rejected.
   - Current memory RSS (Resident Set Size).
   - Latency Percentile (P50, P95, P99).

### Constraints
- Dilarang menggunakan pustaka antrean eksternal (seperti Redis, RabbitMQ, Kafka) atau concurrent utility tingkat tinggi pihak ketiga (e.g., BullMQ, RxJava). 
- Wajib menggunakan primitif bawaan runtime:
  - **Go:** Channels, WaitGroup, Context, sync primitives.
  - **Node.js:** Worker Threads, Streams, EventEmitter, Promises (hindari starvation pada event loop).
  - **Java:** `ExecutorService`, `ArrayBlockingQueue`, `AtomicInteger`, atau Virtual Threads + `Semaphore`.

### Expected Output
Eksekusi CLI aplikasi menampilkan metrik streaming real-time yang stabil di terminal. Ketika diuji dengan pengiriman task agresif, sistem tidak mengalami lonjakan memori tak terkendali (flat memory footprint), berhasil membatasi utilisasi worker, dan saat ditekan `Ctrl+C` mampu menyelesaikan task tersisa lalu keluar dengan kode status `0`.

---

## 5. Knowledge Check & Checklist

Gunakan checklist ini untuk menguji kesiapan arsitektural Anda sebelum melangkah ke bab implementasi protokol jaringan dan database engine.

### Saya harus memahami:
- [ ] Perbedaan presisi antara *Concurrency* (struktur/desain penanganan banyak hal) dan *Parallelism* (eksekusi simultan di multi-core hardware).
- [ ] Siklus hidup dan fase-fase internal Event Loop (Timers, Pending Callbacks, Poll, Check, Close) serta perbedaan *Microtasks* (Promise) vs *Macrotasks* (setTimeout/I/O).
- [ ] Model threading sistem operasi (1:1), green threading murni (M:1), dan hybrid/multiplexed scheduling (M:N).
- [ ] Mengapa *blocking I/O call* pada arsitektur berbasis Event Loop menghancurkan *throughput* keseluruhan aplikasi.
- [ ] Alasan hardware arsitektur modern (x86/ARM) memerlukan *Memory Barrier / volatile semantics* untuk visibilitas data lintas-thread.
- [ ] Cara kerja Garbage Collector dalam membersihkan memori heap pada lingkungan multi-thread dan implikasinya terhadap *p99 latency spikes*.
- [ ] Definisi dan kondisi terjadinya *Race Condition*, *Deadlock*, *Livelock*, dan *Thread Starvation*.

### Saya tidak perlu menghafal:
- [ ] Seluruh nama fungsi internal C++ pengatur low-level scheduling di engine V8 atau libuv.
- [ ] Nomor interupsi spesifik pada sistem operasi POSIX atau instruksi bytecode assembly CPU secara mendalam di luar instruksi atomic dasar.
- [ ] Sintaks mikro API pihak ketiga yang membungkus concurrency helper; fokuslah pada pemahaman primitif bawaan bahasa.

### Saya harus bisa melakukan:
- [ ] Melakukan profiling konsumsi CPU dan memory leak pada aplikasi yang berjalan menggunakan profiler native (`pprof` di Go, `--inspect` / Chrome DevTools di Node.js, `VisualVM` / `JProfiler` di Java).
- [ ] Menganalisis *thread dump* / *stack trace* untuk menemukan titik pasti terjadinya *deadlock* atau thread penahan lock terlama.
- [ ] Mengimplementasikan pola konkurensi esensial: *Worker Pool Pattern*, *Fan-out/Fan-in*, *Publish-Subscribe in-memory*, dan *Rate Limiter Token Bucket*.
- [ ] Memilih secara objektif teknologi runtime (Node.js vs Go vs Java vs Python) berdasarkan profil beban kerja sistem (*I/O-heavy* vs *CPU-heavy* vs *High Memory Concurrency*).
- [ ] Membaca kode backend dan secara instan mendeteksi potensi *shared state mutation* yang tidak aman terhadap akses paralel.