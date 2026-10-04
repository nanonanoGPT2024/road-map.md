# BAB 09: Quiz, Challenge, & Knowledge Check
**Enterprise Web Architecture**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Spesifikasi Antarmuka Rack dan Streaming API**  
   Jelaskan secara mendalam kontrak antarmuka *Rack specification* (`call(env) -> [status, headers, body]`). Bagaimana mekanisme internal Rack membedakan antara *enumerable body* standar dengan *streaming/hijack body* (khususnya `rack.hijack`), dan apa konsekuensi siklus hidup thread/koneksi socket saat kontrol diserahkan dari web server ke aplikasi Ruby?

2. **Model Konkurensi Puma Clustered vs Falcon (Fiber-based)**  
   Bandingkan arsitektur eksekusi *Puma in Clustered Mode* (kombinasi worker processes berbasis `fork()` dan multi-threaded pool) dengan *Falcon* yang memanfaatkan Ruby 3 Fiber Scheduler dan protokol non-blocking I/O. Jelaskan implikasi kedua arsitektur ini terhadap batasan *Global VM Lock* (GVL) pada pemrosesan workload CPU-bound versus I/O-bound.

3. **Korelasi ActiveRecord Connection Pool dan Threading Puma**  
   Bagaimana formula matematis penentuan ukuran `pool` pada `database.yml` dalam kaitannya dengan jumlah Puma `workers`, Puma `max_threads`, dan connection pooler eksternal seperti PgBouncer (Transaction Pooling mode)? Mengapa ketidakcocokan konfigurasi ini dapat memicu `ActiveRecord::ConnectionTimeoutError` meskipun utilisasi CPU database masih sangat rendah?

4. **Mekanisme Russian Doll Caching dan Fragment Invalidation**  
   Jelaskan topologi dan siklus hidup komputasi pada *Russian Doll Caching*. Bagaimana relasi `touch: true` pada model ActiveRecord mengalirkan pembaruan timestamp `updated_at` ke entitas induk? Analisis kelemahan struktural dari pendekatan ini ketika terjadi *mass update* (ribuan record ter-update bersamaan) terhadap *cache churn* di Redis/Memcached.

5. **Transaksionalitas Database dan Enqueueing Background Job**  
   Mengapa mengeksekusi operasi `perform_async` / `perform_later` di dalam blok database transaction (`ActiveRecord::Base.transaction`) dikategorikan sebagai *anti-pattern* kritis di sistem enterprise? Analisis kondisi balapan (*race condition*) yang terjadi antara kecepatan replikasi/komit database dengan pembacaan data oleh worker Sidekiq, serta strategi mitigasi native Rails (`after_commit` hook / transactional outbox pattern).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Degradasi Linux Copy-on-Write (CoW) dan Garbage Collection**  
   Dalam Puma clustered mode yang menggunakan `preload_app!`, memori induk di-*fork* ke *child processes*. Namun, seiring berjalannya waktu, metrik *Private Dirty RSS* pada setiap worker meningkat drastis dan CoW benefit tereduksi hingga mendekati 0%. Jelaskan secara mekanistik bagaimana internal Ruby Garbage Collector (Object Header, RVALUE flags, Generational GC write barrier, dan Compaction) memodifikasi page memory dan merusak efisiensi CoW.

2. **Alokator Memori: glibc malloc vs jemalloc dalam Ruby Enterprise**  
   Jelaskan fenomena *memory fragmentation* pada runtime MRI Ruby di lingkungan Linux ketika menggunakan alokator bawaan `glibc`. Mengapa pengalihan ke `jemalloc` (melalui dynamic linking `LD_PRELOAD`) secara signifikan menstabilkan alokasi memori jangka panjang? Parameter konfigurasi `MALLOC_ARENA_MAX` apa yang kritis jika sistem terpaksa menggunakan `glibc` di bawah Puma multi-threaded?

3. **ActiveRecord Pool Starvation vs Deadlock Diagnostik**  
   Sebuah aplikasi mengalami lonjakan *tail latency* (p99) yang berujung pada error `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`. Namun, metrik pg_stat_activity menunjukkan koneksi aktif ke PostgreSQL masih berada di bawah `max_connections`. Bagaimana alur diagnostik sistematis menggunakan `Thread.list`, `ActiveRecord::Base.connection_pool.stat`, dan thread backtrace dump untuk mengidentifikasi apakah root cause merupakan *connection leak*, thread yang terjebak pada I/O blocking eksternal, atau *distributed deadlock*?

4. **Anatomi Distributed Lock dengan Redlock dan Resiko Split-Brain**  
   Implementasi distributed lock pada Redis sering kali menggunakan pattern `SET resource_name my_random_value NX PX 30000`. Jelaskan kelemahan algoritma ini di lingkungan multi-threaded yang mengalami Garbage Collection Stop-The-World (STW) pause atau OS process swapping yang panjang. Bagaimana Redlock mengatasi hal ini dan mengapa *fencing tokens* (seperti yang diusulkan oleh Martin Kleppmann) mutlak dibutuhkan untuk menjamin keamanan mutlak pada level database storage?

5. **Fiber Scheduler Blocking C-Extensions Boundary**  
   Saat mengadopsi Ruby 3 Fiber-based server (Falcon) untuk arsitektur I/O non-blocking, library native C-extension tertentu (seperti beberapa legacy database driver atau enkripsi kustom) dapat melumpuhkan seluruh *event loop*. Jelaskan mekanisme internal mengapa kernel thread sistem operasi dapat terblokir jika C-extension tidak mengimplementasikan `rb_thread_call_without_gvl` atau tidak memanfaatkan Hook Fiber Scheduler (`rb_fiber_scheduler_*`), serta bagaimana dampaknya terhadap ribuan *concurrent fibers* lainnya dalam proses yang sama.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Worker Saturation & Cascading Failure pada Flash Sale
Pada puncak kampanye *Flash Sale*, aplikasi e-commerce berbasis Rails + Puma (16 instances, masing-masing 4 worker processes, 5 thread per worker) mengalami kegagalan beruntun. Nginx *ingress controller* mulai merespons dengan HTTP 502 Bad Gateway dan HTTP 504 Gateway Timeout. 
*   **Investigasi Awal**:
    *   CPU node aplikasi berada pada angka 25% (relatif idle).
    *   PostgreSQL CPU berada pada angka 30%.
    *   Puma queue depth pada socket backlog melonjak drastis hingga kapasitas maksimal.
    *   Metrik APM menunjukkan waktu respons pada endpoint eksternal Payment Gateway pihak ketiga melonjak dari 150ms menjadi 12.000ms.
*   **Pertanyaan Diagnostik & Solusi**:
    1. Uraikan fenomena *thread exhaustion* yang terjadi pada Puma cluster akibat latency spike dari dependensi eksternal downstream.
    2. Rancang strategi arsitektural komprehensif untuk mencegah kegagalan sistem total dengan mengombinasikan *Circuit Breaker pattern*, isolasi *Bulkhead*, dan penyesuaian parameter *low-level socket backlog* / *reverse proxy timeouts*.

### Skenario B: Dual-Write Inconsistency & Replica Lag Desynchronization
Arsitektur transaksi finansial menggunakan pola *read-write splitting* (ActiveRecord membaca dari RDS Read Replicas dan menulis ke Primary) serta Redis sebagai L2-cache layer untuk saldo dompet digital.
*   **Insiden**:
    *   Pengguna melakukan *top-up* saldo via API. Database master mencatat penambahan saldo secara valid.
    *   Segera setelah menerima respons `HTTP 200 OK`, frontend memanggil API `GET /balance` secara otomatis.
    *   Pengguna mendapati saldo lamanya masih muncul. Upaya checkout berikutnya gagal karena validasi saldo tidak mencukupi, memicu pembatalan massal.
    *   Metrik CloudWatch menunjukkan `ReplicaLag` PostgreSQL berfluktuasi antara 800ms hingga 2500ms akibat vacuum activity yang intensif.
*   **Pertanyaan Diagnostik & Solusi**:
    1. Analisis kegagalan konsistensi data dari perspektif teorema CAP / model konsistensi (Eventual Consistency vs Read-Your-Own-Writes).
    2. Rancang blueprint arsitektur teknis di level middleware Ruby/Rails untuk menjamin *Read-After-Write Consistency* tanpa mematikan arsitektur Read-Replica, termasuk teknik penanganan sinkronisasi cache Redis yang resisten terhadap *race condition* invalidasi.

### Skenario C: Sidekiq Out-Of-Memory (OOM) Meltdown & Poison Pill Epidemic
Sistem background processing memproses rata-rata 15.000 jobs/detik menggunakan Sidekiq Enterprise. Karena adanya upgrade skema database mikroservis billing downstream, endpoint webhook billing mati selama 45 menit.
*   **Insiden**:
    *   Queue `billing_sync` membengkak dari normal 500 jobs menjadi 40.000.000 jobs di Redis.
    *   Memory footprint Redis melonjak hingga menyentuh batas `maxmemory`, memicu *OOM command rejected*.
    *   Ketika endpoint billing downstream hidup kembali, seluruh Sidekiq worker instance mengalami *OOMKilled* secara berulang dalam siklus 60 detik setelah boot up.
    *   Log menunjukkan jutaan *retry jobs* dieksekusi secara masif dan terdapat sejumlah job dengan payload korup (*poison pills*) yang memicu *unhandled segmentation fault* di level worker C-parser.
*   **Pertanyaan Diagnostik & Solusi**:
    1. Mengapa payload serialization yang terlalu besar di Redis mempercepat kejatuhan cluster Sidekiq, dan bagaimana mekanisme backpressure yang ideal?
    2. Rancang rencana pemulihan darurat (*incident recovery plan*) langkah-demi-langkah untuk membersihkan/mengisolasi poison pills, menerapkan *rate limiting/concurrency throttle*, serta memulihkan pemrosesan antrean tanpa membuat down sistem dependensi sekunder.

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Performance Resilient Reverse-Proxy Engine Middleware
**Problem Statement:**  
Sebagai Principal Engineer, Anda diminta membangun sebuah Rack Engine Middleware kelas enterprise yang berfungsi sebagai *API Resiliency Gateway* untuk melindungi core service dari cascading failures ketika berkomunikasi dengan downstream services yang tidak stabil. Solusi ini harus dibuat *murni* menggunakan primitive concurrency Ruby standard library tanpa bergantung pada gem pihak ketiga (seperti `resilience4j` wrapper atau `stoplight`).

**Requirements:**
1. **Thread-Safe Circuit Breaker Core**:
   *   Mengimplementasikan finite state machine: `CLOSED`, `OPEN`, dan `HALF-OPEN`.
   *   Transisi ke `OPEN` jika rasio kegagalan (error count) melampaui batas *threshold* (misal: 50% dari 20 request terakhir gagal, atau 5 error beruntun).
   *   Transisi dari `OPEN` ke `HALF-OPEN` setelah `sleep_window` (misal: 10 detik).
   *   Gunakan struktur data thread-safe berbasis ring-buffer atau atomik (manfaatkan `Concurrent::AtomicReference` atau thread-safe primitives via native `Mutex`).
2. **Token-Bucket Rate Limiter**:
   *   Rate limiter per client-IP menggunakan algoritma Token Bucket yang thread-safe.
   *   Token diisi ulang (*refilled*) secara matematis berdasarkan delta waktu akses tanpa menggunakan background thread terpisah.
   *   Jika bucket kosong, kembalikan response Rack `HTTP 429 Too Many Requests` disertai header `Retry-After`.
3. **Execution Guard & Bulkhead (Concurrency Limiter)**:
   *   Batas konkurensi request simultan maksimum ke downstream (misal: max 10 konkurensi per worker). Jika limit terlampaui, request harus segera ditolak dengan `HTTP 503 Service Unavailable` atau fallback execution.
4. **Metrics & Telemetry Hook**:
   *   Middleware harus mencatat metrics (*circuit state*, *token count*, *active executions*) secara *lock-free* atau dengan *critical section* seminimal mungkin agar tidak menambah latency pada p99 > 2ms.

**Constraints:**
*   Hanya boleh menggunakan Ruby 3.2+ core/stdlib (Boleh menggunakan `Monitor`, `Mutex`, `Thread::Queue`).
*   Tidak boleh menimbulkan memory leak: Pastikan data IP-bucket lama yang tidak aktif dibersihkan (*eviction mechanism*).
*   Kompatibel dengan Puma Clustered + Multi-threaded (harus *process-safe* jika memori terisolasi, dan *thread-safe* di dalam proses).

**Expected Output:**
*   Satu file executable mandiri `resilience_gateway.rb` yang menyertakan implementasi middleware, mock downstream target, dan skrip *concurrency stress-test* menggunakan minimal 20 thread paralel yang membuktikan:
    1. Rate limit bekerja saat dihujani request.
    2. Circuit Breaker trip ke status `OPEN` saat downstream melempar error, dan memblokir request berikutnya tanpa menyentuh downstream sama sekali.
    3. Transisi ke `HALF-OPEN` dan recovery kembali ke `CLOSED` ketika downstream stabil.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Rack environment dictionary dan spesifikasi I/O streaming/hijacking.
- [ ] Perbedaan fundamental model proses/thread Puma vs Fiber concurrency model Falcon di bawah pengaruh GVL Ruby.
- [ ] Dampak Ruby GC (Mark, Sweep, Compact, Generational Write-barriers) terhadap Linux Copy-on-Write pada arsitektur web server prefork.
- [ ] Alasan jemalloc lebih unggul dalam mengatasi memory fragmentation dibandingkan glibc malloc pada aplikasi Ruby berskala besar.
- [ ] Rumus sizing ActiveRecord Connection Pool sehubungan dengan Puma Worker, Puma Threads, dan database pooler (PgBouncer).
- [ ] Arsitektur multi-layer caching (HTTP Cache-Control, Edge/CDN, Russian Doll Cache, Key-Value Invalidation via Redis).
- [ ] Konsekuensi transactional boundaries terhadap asynchronous job dispatching (Race condition antara commit vs async worker execution).
- [ ] Teorema CAP dan teknik mitigasi *Replica Lag* untuk mencapai konsistensi *Read-Your-Own-Writes*.
- [ ] Pola resiliensi distributed systems: Circuit Breaker, Bulkhead Isolation, Token-Bucket Rate Limiting, dan Idempotent Consumer.

### Saya tidak perlu menghafal:
- [ ] Seluruh hash key standar dalam `Rack::MockRequest.env_for` (cukup pahami key fundamental seperti `REQUEST_METHOD`, `PATH_INFO`, `rack.input`).
- [ ] Syntax baris-per-baris konfigurasi low-level `jemalloc` tuning flags (cukup pahami `narenas`, `dirty_decay_ms`, dan cara mendeteksi utilisasinya).
- [ ] Implementasi algoritma Redlock matematis secara detail hingga formula quorum vote (cukup pahami trade-off split-brain, drift time, dan pentingnya fencing token).
- [ ] Setiap method internal pada C-code Ruby VM yang menangani Fiber Scheduler (cukup pahami konsep non-blocking system call wrapper dan cara mendeteksi uncooperative C-extensions).

### Saya harus bisa melakukan:
- [ ] Menganalisis dan memperbaiki insiden *Connection Pool Exhaustion* di environment production di bawah beban konkurensi tinggi.
- [ ] Mengonfigurasi Puma server secara optimal (worker count, thread min/max, phased-restart vs hot-restart) menyesuaikan core CPU dan profil memori server.
- [ ] Melakukan profiling dan debugging kebocoran memori (memory leak) dan bloating pada worker Ruby menggunakan tools seperti `derailed_benchmarks`, `memory_profiler`, atau `rbtrace`.
- [ ] Mengimplementasikan *Idempotent Background Jobs* menggunakan database uniqueness constraints atau distributed lock tokens.
- [ ] Merancang arsitektur failover database dan routing koneksi read/write secara dinamis menggunakan fitur native ActiveRecord multi-db switching.
- [ ] Mengisolasi downstream service dependencies yang lambat menggunakan timeout berlapis (*read timeout*, *open timeout*) dan circuit breaker patterns.