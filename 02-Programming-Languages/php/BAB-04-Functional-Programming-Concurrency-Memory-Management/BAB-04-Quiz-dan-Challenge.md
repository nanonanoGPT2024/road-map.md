# BAB 04: Quiz, Challenge, & Knowledge Check
**Functional Programming, Concurrency & Memory Management**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Immutability & Side Effects pada Zend VM**
   Jelaskan bagaimana konsep *pure function* dan *immutability* diterapkan dalam PHP modern (PHP 8.1+ dengan `readonly class` dan *first-class callable syntax*). Bagaimana Zend Engine menangani mutasi state pada object *readonly* di level runtime, dan apa implikasi arsitekturalnya terhadap pencegahan *side-effects* pada aplikasi terdistribusi?

2. **Mekanisme Generator vs Eager Loading Array**
   Bandingkan secara arsitektural penggunaan *Array Collection* konvensional dengan *Generator* (`yield` / `yield from`). Bagaimana Zend VM menyusun *call frame* dan menahan pointer eksekusi saat sebuah Generator disuspensi? Jelaskan mengapa penggunaan Generator menghasilkan efisiensi memori $O(1)$ dibandingkan $O(N)$ pada array.

3. **Model Konkurensi: Fibers vs Threads vs Processes**
   Uraikan perbedaan mendasar antara:
   - *Cooperative Multitasking* menggunakan `Fiber` (PHP 8.1+),
   - *Preemptive Multithreading* via ekstensi `parallel`,
   - *Multi-Processing* via `pcntl_fork`.
   
   Kapan eksekusi context-switching dilakukan oleh kernel OS, kapan diatur oleh engine runtime PHP, dan bagaimana batasan *isolated memory space* berlaku pada masing-masing model?

4. **Copy-on-Write (COW) & Manipulasi Struktur `zval`**
   Jelaskan secara mendalam siklus hidup struktur `zval` saat sebuah variabel array dioperasikan. Bagaimana mekanisme *Copy-on-Write* (COW) bekerja melalui `refcount`, kapan tepatnya alokasi memori fisik baru (*memory duplication*) dipicu, dan bagaimana pemanggilan variabel via referensi (`&$var`) justru dapat merusak efisiensi optimasi COW?

5. **Cycle Collection Mechanism pada Garbage Collector**
   PHP menggunakan sistem *reference counting* otomatis, namun sistem ini gagal membebaskan memori ketika terjadi *circular reference*. Jelaskan algoritma *Concurrent Cycle Collection* (algoritma berbasis pewarnaan: *purple, grey, black, white*) yang digunakan PHP GC. Kapan *root buffer* terpicu, dan bagaimana siklus tersebut akhirnya didealokasi oleh engine?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Memory Leaks pada Long-Running Process & Scope Retention**
   Pada aplikasi berbasis *worker loop* (seperti RoadRunner, Swoole, atau Laravel Horizon), jelaskan bagaimana *Closure* yang meng-capture variabel lokal melalui `use ($var)` atau referensi implisit terhadap `$this` dapat menyebabkan kebocoran memori progresif (*slow memory leaks*). Bagaimana cara mendeteksi dan mencegah *dangling reference* tersebut?

2. **Fiber Suspend/Resume Mechanics & Exception Handling**
   Analisislah skenario di mana sebuah `Fiber` disuspensi (`Fiber::suspend()`) saat memegang resource stream/socket terbuka, kemudian runtime melemparkan exception dari context eksekusi utama sebelum Fiber tersebut sempat di-*resume*. Bagaimana Zend Engine menangani pembersihan resource tersebut? Tuliskan skema proteksi yang wajib diterapkan agar tidak terjadi kebocoran file descriptor.

3. **Analisis Profiling Memori Tingkat Rendah**
   Sebuah daemon PHP mengalami lonjakan alokasi memori hingga memicu *OOM (Out Of Memory)* dari kernel Linux (OOM Killer). Namun, metrik `memory_get_usage(false)` menunjukkan penggunaan yang stabil, sementara `memory_get_usage(true)` dan metrik RSS (Resident Set Size) OS terus meningkat. Apa yang sebenarnya terjadi di level *Zend Memory Manager* (ZendMM) dan *system allocator* (`glibc malloc/jemalloc`), serta bagaimana strategi mitigasi fragmentasi memori ini?

4. **Race Condition dalam Async/Cooperative Runtime**
   Meskipun Fiber berjalan secara *single-threaded* dan *cooperative*, sebuah aplikasi async tetap rentan terhadap *race condition* tingkat aplikasi (*logical race conditions*). Berikan satu contoh konkret bagaimana operasi I/O asinkron yang diselingi `suspend()` dapat merusak integritas state bersama (*shared state* / *in-memory cache*), dan bagaimana strategi sinkronisasinya tanpa menggunakan *kernel-level mutex*.

5. **Currying, High-Order Functions, dan Call-Stack Overhead**
   Ketika menerapkan paradigma *pure functional programming* ekstrem di PHP (menggunakan deep currying, komposisi fungsi rekursif, dan pembungkus monad), apa dampak langsungnya terhadap *call stack depth*, Zend VM opcode execution overhead, dan alokasi `zend_execute_data`? Kapan batas aman penggunaan paradigma ini sebelum mencapai `zend.max_execution_timers` atau stack overflow?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Memory Leak & Cyclic Reference pada Data Ingestion Pipeline
* **Konteks:** Sistem streaming ingest memproses 500.000 event log per jam menggunakan worker PHP long-running via CLI. Setiap pesan didekode menjadi object graph kompleks (Event -> Metadata -> User Context -> Event). Worker menggunakan framework ORM/Serializer untuk rekonstruksi model.
* **Gejala:** Worker berjalan lancar selama 20 menit pertama, kemudian kecepatan pemrosesan anjlok drastis (throughput turun 80%), dan konsumsi memori merangkak naik sebesar 15 MB/menit hingga proses mati terbunuh oleh OOM Killer. Pemanggilan `gc_collect_cycles()` manual secara periodik menyebabkan *CPU spike 100%* selama 2-3 detik dan memicu bottleneck latensi.
* **Pertanyaan Diagnostik:**
  1. Identifikasi akar penyebab anjloknya throughput sebelum worker mati: mengapa intervensi GC manual memicu latensi tinggi seiring membesarnya ukuran root buffer?
  2. Bagaimana Anda merancang ulang arsitektur struktur data event tersebut agar bersifat *transient* dan ramah terhadap *Zend Memory Manager*, tanpa mengorbankan integritas data?
  3. Perintah profiling atau ekstensi apa (`php-memprof`, `xdebug`, atau native Zend engine hooks) yang akan Anda injeksikan untuk menemukan pointer referensi spesifik yang gagal didealokasi?

---

### Skenario B: Race Condition & State Leak pada Runtime HTTP Asinkron (RoadRunner/Swoole)
* **Konteks:** Tim backend memigrasikan microservice pembayaran dari PHP-FPM konvensional ke arsitektur persistent memory runtime (Octane / Swoole) untuk mengejar target latensi di bawah 10ms.
* **Gejala:** Pada beban traffic 3.000 RPS, terjadi anomali fatal: Pengguna A menerima konfirmasi pesanan milik Pengguna B secara acak, dan token otentikasi antar-request saling tertukar. Hasil audit finansial mendapati adanya mutasi saldo ganda (*double-crediting*) pada beberapa akun secara non-deterministik.
* **Pertanyaan Diagnostik:**
  1. Bedah secara mekanistis bagaimana arsitektur *persistent memory process* (di mana lifecycle worker melayani ribuan HTTP request berturut-turut) mengekspos variabel statis (*static properties*), Singleton services, atau global scope ke dalam risiko *state pollution*.
  2. Jelaskan urutan eksekusi (*interleaving execution trace*) yang menyebabkan data Pengguna A tertukar dengan Pengguna B pada tingkat async event loop.
  3. Buat rancangan mekanisme *Context Isolation / Reset Engine* untuk menjamin bahwa seluruh dependency tree, request-scoped instances, dan transient state dibersihkan sepenuhnya saat transisi antar-request tanpa me-restart worker process.

---

### Skenario C: Architectural Trade-Off: Mass External API Aggregation
* **Konteks:** Anda diminta mendesain sistem integrasi yang harus memanggil 50 REST API pihak ketiga secara independen untuk setiap 1 request transaksi yang masuk. SLA waktu respons transaksi maksimal adalah 800ms. Rata-rata latensi masing-masing pihak ketiga adalah 250-400ms.
* **Dilema:** 
  - Arsitektur synchronous cURL multi-process konvensional (PHP-FPM) menguras pool worker secara instan dan memicu connection starvation.
  - Opsi 1: Menggunakan *Fiber-based asynchronous framework* (misal: Revolt Event Loop / Amphp / ReactPHP) dalam single runtime.
  - Opsi 2: Menggunakan *Multi-threading model* via ekstensi `parallel`.
  - Opsi 3: Memecah tugas ke Message Broker (RabbitMQ/Kafka) dengan pool worker background terdistribusi.
* **Pertanyaan Diagnostik:**
  1. Evaluasi Opsi 1 vs Opsi 2 dari aspek: overhead memori per thread/fiber, kemudahan debugging (*stack traces*), dan efisiensi penanganan I/O socket blocking.
  2. Mengapa Opsi 3 mungkin melanggar SLA batas waktu 800ms secara deterministik untuk komunikasi synchronous request-response klien?
  3. Rumuskan arsitektur optimal yang memadukan non-blocking concurrent I/O dengan mekanisme *fail-fast timeout / circuit breaker*, serta jelaskan estimasi konsumsi memori sistem saat melayani 500 transaksi per detik secara konkuren.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Concurrent Async Metrics Aggregator & Streaming Engine

#### Problem Statement
Anda ditugaskan membangun engine inti *Metrics Aggregator* mandiri (CLI-based) tanpa dependensi framework besar. Engine ini harus menerima puluhan ribu data metrik time-series mentah dari file stream atau socket, memprosesnya secara fungsional (filtering, transforming, aggregating), dan mengirimkannya ke remote endpoint tiruan secara konkuren dengan batas penggunaan memori yang sangat ketat.

#### Requirements
1. **Functional Pipeline Core:**
   - Gunakan pendekatan fungsional murni (*higher-order functions*, pipeline closure) untuk memproses event.
   - Tidak boleh ada mutasi variabel luar di dalam tahapan pipeline; gunakan struktur data immutable.
   - Implementasikan *custom pipeline operator* atau chaining pattern untuk operasi: `sanitize -> filter outliers -> aggregate by metric_id -> compute running average`.

2. **Memory Constraint & Generator Streaming:**
   - Input data disimulasikan dari file log/payload berukuran minimal 2 GB (atau stream data infinite).
   - Seluruh pemrosesan stream **WAJIB** memanfaatkan Generator (`yield`) dengan sistem *backpressure* sederhana.
   - Konsumsi memori fisik (*peak usage*) aplikasi **TIDAK BOLEH** melebihi **16 MB** selama seluruh siklus eksekusi berlangsung.

3. **Concurrency Engine with Fibers:**
   - Implementasikan *concurrency scheduler* sederhana berbasis `Fiber` native (PHP 8.1+) untuk mensimulasikan dispatch batch data teragregasi ke 5 remote endpoint berbeda secara asinkron/non-blocking.
   - Tidak boleh menggunakan framework async pihak ketiga (seperti Guzzle Async, Swoole, atau Amp); buat *event-loop-like cooperative scheduler* minimalis sendiri menggunakan `stream_select()` atau native Fiber state orchestration.

4. **Resource & Lifecycle Safety:**
   - Terapkan penanganan lifecycle memori eksplisit: pastikan tidak ada kebocoran memori pada loop agregasi.
   - Sediakan diagnostic hook internal yang mencetak metrik: `memory_get_usage()`, `memory_get_peak_usage()`, dan jumlah fiber aktif ke output konsol setiap interval 1.000 pesan.

#### Constraints
* Versi PHP: **PHP 8.2 atau lebih tinggi**.
* Tidak diperbolehkan menginstal ekstensi C eksternal (murni native PHP runtime).
* Skrip harus menangani sinyal OS (`SIGINT`, `SIGTERM`) menggunakan `pcntl_signal` agar dapat *gracefully shutdown*, menguras buffer yang tersisa, dan mencetak status pembersihan memori terakhir.

#### Expected Output
* File arsitektur terstruktur (dapat berupa satu script eksekusi utuh atau class terpisah).
* Log konsol real-time yang menunjukkan stream processing berjalan tanpa jeda, alokasi memori datar (*flatline*) di bawah 16 MB, serta transisi state Fiber (*Suspended*, *Running*, *Terminated*) yang konsisten.
* Penjelasan singkat (analisis kompleksitas waktu dan ruang) mengapa solusi yang dibuat kebal terhadap *memory fragmentation* dan *circular reference leaks*.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Anatomi struktur data internal `zval` (value, u1/type_info, u2) dan flag optimasi engine (IS_ARRAY, IS_INTERNED_STRING, IS_REFERENCE).
- [ ] Alur kerja *Copy-on-Write* (COW) dan titik kritis alokasi memori fisik baru saat pemisahan array (*buffer duplication*).
- [ ] Cara kerja *Zend Cycle Collection* (Zend GC), status warna node (*black, grey, white, purple*), dan alasan pemanggilan `gc_collect_cycles()` yang salah justru membunuh performa.
- [ ] Perbedaan deterministik antara arsitektur I/O Blocking vs Non-Blocking I/O serta implikasinya terhadap event loop.
- [ ] Siklus hidup `Fiber` di PHP 8.1+: perbedaan state `CREATED`, `SUSPENDED`, `RUNNING`, dan `TERMINATED`.
- [ ] Mengapa *Shared-Nothing Architecture* pada PHP-FPM melindungi developer dari masalah konkurensi umum, dan mengapa paradigma tersebut hilang saat beralih ke persistent runtime seperti Swoole/RoadRunner.
- [ ] Konsep fungsional murni: *referential transparency*, *currying*, *partial application*, dan *monadic error handling*.

### Saya tidak perlu menghafal:
- [ ] Alamat memori spesifik atau representasi biner flag struct C pada Zend source code (`zend_types.h`).
- [ ] Angka pasti ambang batas alokasi buffer default OS untuk operasi `stream_select()`.
- [ ] Parameter konfigurasi micro-tuning low-level Linux Kernel network socket (misal: `tcp_wmem`, `SO_RCVBUF`) di luar interaksinya dengan stream context PHP.

### Saya harus bisa melakukan:
- [ ] Melakukan profiling dan isolasi kebocoran memori (*memory leak analysis*) pada daemon PHP long-running menggunakan tools analitik (seperti `php-memprof` atau memory dump inspect).
- [ ] Menulis pipeline streaming berkinerja tinggi menggunakan *Generators* (`yield` / `yield from`) yang menjaga kestabilan alokasi memori pada ukuran konstan $O(1)$.
- [ ] Membangun abstraction layer berbasis `Fiber` untuk mengonversi alur async non-blocking menjadi gaya kode sinkron (*synchronous-looking code*).
- [ ] Mengaudit kode dari potensi *state pollution* dan *cross-request data leaks* pada runtime HTTP persisten.
- [ ] Menerapkan mekanisme mitigasi konkurensi (seperti *distributed lock*, *CAS/Compare-And-Swap*, atau *fiber-safe queuing*) untuk menjaga konsistensi transaksi data.