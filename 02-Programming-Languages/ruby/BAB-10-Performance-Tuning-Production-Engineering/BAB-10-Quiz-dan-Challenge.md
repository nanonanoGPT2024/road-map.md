# BAB 10: Quiz, Challenge, & Knowledge Check
**Performance Tuning & Production Engineering**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

### Soal 1.1: Mekanisme Global VM Lock (GVL) dan Karakteristik Workload
Jelaskan secara mendalam bagaimana Global VM Lock (GVL) di MRI (CRuby) mengatur eksekusi *native threads* pada level sistem operasi. Mengapa aplikasi Ruby yang bersifat *I/O-bound* tetap mendapatkan peningkatan *throughput* yang signifikan dengan utilisasi *multi-threading*, sementara aplikasi *CPU-bound* justru mengalami degradasi performa (*negative scaling*) saat menggunakan thread pool berukuran besar?

### Soal 1.2: Siklus Hidup Generational Garbage Collection (RGenGC)
MRI mengimplementasikan *Generational Garbage Collection* (RGenGC) sejak Ruby 2.1 untuk memitigasi overhead *full mark-and-sweep*. Jelaskan konsep *weak generational hypothesis* dalam konteks alokasi memori Ruby. Bagaimana MRI membedakan *young generation* dan *old generation*, serta bagaimana mekanisme *Write Barrier* memastikan integritas referensi dari *old generation* ke *young generation* tanpa harus memindai seluruh *heap* pada setiap *minor GC*?

### Soal 1.3: Fragmentasi Memori dan Alokator: `glibc malloc` vs `jemalloc`
Mengapa arsitektur alokasi slot memori Ruby (RVALUE slots dalam Heap Pages) sangat rentan terhadap fenomena *memory fragmentation* dan *memory bloat* ketika dikompilasi dengan alokator default Linux (`glibc malloc`)? Jelaskan mekanisme teknis bagaimana alokator alternatif seperti `jemalloc` (melalui teknik *size classes* dan *thread-specific arenas*) dapat mereduksi *Resident Set Size* (RSS) pada proses Ruby jangka panjang di lingkungan produksi.

### Soal 1.4: Copy-on-Write (CoW) Friendliness pada Arsitektur Pre-Fork
Server web Ruby enterprise (seperti Puma dalam *clustered mode* atau Unicorn) mengandalkan *system call* `fork(2)` untuk menduplikasi *master process* menjadi beberapa *worker processes*. Jelaskan bagaimana prinsip *Copy-on-Write* (CoW) menghemat penggunaan RAM sistem. Identifikasi dua faktor internal dalam runtime Ruby (misalnya: *GC compaction*, *object slot dirtying*, atau pembaruan *internal counters*) yang dapat memecah (*break*) CoW pages dan memicu *memory amplification* pasca-fork.

### Soal 1.5: Non-blocking I/O: Fiber Scheduler vs Multi-Threading
Ruby 3 memperkenalkan *Fiber Scheduler* interface (sebagaimana diimplementasikan oleh gem `async`). Bandingkan arsitektur konkurensi berbasis *Fiber Scheduler* dengan model *OS-thread pool* konvensional. Tinjau dari aspek *context switching overhead*, jejak memori (*call stack size*), dan penanganan *blocking system calls* (seperti `read`, `write`, dan `epoll/kqueue`).

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

### Soal 2.1: Analisis Retained Objects via Heap Dump
Saat melakukan investigasi kebocoran memori menggunakan `ObjectSpace.dump_all`, Anda menemukan jutaan object dengan struktur data `T_STRING` dan `T_DATA` yang tertahan di *old generation*. Bagaimana Anda melacak jalur referensi (*retainer tree*) dari *live objects* tersebut hingga ke *root object*? Jelaskan risiko menyematkan objek ke dalam *global variables*, *class-level instance variables*, atau *long-lived closures/lambdas*.

### Soal 2.2: Tuning Konfigurasi Ruby GC di Lingkungan Container (Kubernetes)
Dalam container Kubernetes dengan batas memori ketat (`resources.limits.memory = 2Gi`), sebuah aplikasi Ruby sering mengalami OOMKilled (*Exit Code 137*). Jelaskan fungsi dari *environment variables* berikut dan bagaimana Anda mengonfigurasinya untuk menyeimbangkan antara *latency throughput* dan pembersihan agresif memori:
- `RUBY_GC_HEAP_GROWTH_FACTOR`
- `RUBY_GC_HEAP_INIT_SLOTS`
- `RUBY_GC_MALLOC_LIMIT`
- `RUBY_GC_MALLOC_LIMIT_GROWTH_FACTOR`
- `MALLOC_ARENA_MAX`

### Soal 2.3: Profiling Under Load: Sampling Profiler vs Tracing Profiler
Bandingkan metodologi kerja *sampling profiler* (seperti `StackProf` dengan mode `:wall` / `:cpu` atau `rbspy`) dengan *tracing profiler* (seperti `ruby-prof`). Mengapa penggunaan *tracing profiler* dilarang keras di lingkungan produksi berlatensi rendah? Dalam skenario apa metrik `:wall time` menghasilkan kesimpulan diagnosa yang bertolak belakang dengan `:cpu time` pada analisis bottleneck endpoint API?

### Soal 2.4: Compaction Algorithm (`GC.compact`) dan Ekstensi C
Ruby menyediakan kapabilitas manual dan otomatis *heap compaction* (`GC.compact`) berbasis algoritma LISP 2 dua lintasan (*two-pass*). Jelaskan risiko *dangling pointer* atau *segmentation fault* ketika fitur ini diaktifkan pada aplikasi yang menggunakan *C-extensions* pihak ketiga. Bagaimana makro Ruby C API seperti `RB_GC_GUARD`, `rb_gc_register_address`, dan konsep *pinned objects* berinteraksi dengan proses relokasi memori ini?

### Soal 2.5: Thread-Safety Edge Case pada Dynamic Method Definition & Constant Loading
Perhatikan kode multithreaded yang mengeksekusi *lazy initialization* berikut:
```ruby
class PaymentGatewayResolver
  def self.client_for(provider)
    @clients ||= {}
    @clients[provider] ||= "Adapters::#{provider.to_s.camelize}".constantize.new
  end
end
```
Bedah secara mendalam minimal dua masalah konkuren fatal (*race condition* dan *VM execution deadlocks/autoloading issues*) yang dapat terjadi pada kode di atas jika diakses secara paralel oleh ratusan thread Puma dalam produksi, serta berikan refactoring solutif yang berstandar *zero-lock overhead* atau *thread-safe*.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: P99 Latency Degradation & Memory Cascade pasca Traffic Surge
Sebuah platform microservice Ruby-on-Rails yang berjalan di atas cluster Puma Clustered (4 workers, 16 threads per worker) melayani transaksi *flash sale*. Saat load mencapai 15.000 RPS, metrik APM menunjukkan:
- CPU utilization per host berada pada angka wajar (40-50%).
- P50 latency tetap stabil di 45ms, namun P99 latency melonjak dari 120ms menjadi 9.500ms.
- RSS memory melonjak secara eksponensial di seluruh worker node hingga memicu *worker kill & restart* berulang kali dari Puma Master process.
- Database query execution time dilaporkan normal (<10ms).

#### Pertanyaan Diagnostik:
1. Formulasikan hipotesis teknis: Mengapa P99 hancur sementara P50 dan CPU tetap stabil? Analisis peran *Thread Pool Saturation*, *I/O wait*, dan *GC Stop-The-World (STW) pauses* dalam fenomena ini.
2. Langkah instrumental spesifik apa yang harus Anda suntikkan ke dalam runtime untuk memverifikasi apakah GC STW pause yang memblokir request thread?
3. Jika profiling mengidentifikasi adanya serialisasi payload JSON berukuran besar di middleware layer yang mengalokasikan jutaan *ephemeral string objects*, langkah mitigasi arsitektur apa yang wajib dieksekusi secara instan dan jangka panjang?

---

### Skenario B: Silent Financial Data Drift akibat Race Condition & Connection Pool Starvation
Sebuah sistem backend pembayaran memproses webhook transaksi dari payment provider menggunakan Sidekiq (concurrency: 25 thread per worker). Arsitektur worker memvalidasi idempotensi dan memperbarui saldo akun pengguna:
```ruby
class WebhookProcessorWorker
  include Sidekiq::Job
  sidekiq_options retry: 3

  def perform(account_id, amount_cents, transaction_id)
    ActiveRecord::Base.transaction do
      return if Transaction.exists?(external_id: transaction_id)

      account = Account.find(account_id)
      account.balance_cents += amount_cents
      account.save!

      Transaction.create!(external_id: transaction_id, account: account, amount_cents: amount_cents)
    end
  end
end
```
Dalam produksi ditemukan kejanggalan:
1. Ditemukan saldo akhir (*balance*) yang *drift* (kurang dari akumulasi transaksi asli) saat 2 webhook untuk `account_id` yang sama masuk pada milidetik yang identik.
2. Di saat transaksi memuncak, muncul exception `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.

#### Pertanyaan Diagnostik:
1. Bedah kelemahan mekanisme proteksi konkurensi di atas pada level isolasi database dan level thread Ruby. Mengapa `exists?` dan `save!` gagal mencegah *Lost Update Anomaly*?
2. Hitung korelasi matematis antara Sidekiq concurrency, `RAILS_MAX_THREADS`, database connection pool sizing (`pool:` di `database.yml`), dan batas kapasitas connection Postgres backend.
3. Tuliskan ulang (*refactor*) method `perform` di atas menggunakan mitigasi konkurensi tingkat rendah (pilih antara *Pessimistic Locking / SELECT FOR UPDATE* atau *Optimistic Locking with retry / Atomic DB Counter*) lengkap dengan penanganan idempotensi tanpa celah *race condition*.

---

### Skenario C: Trade-off Arsitektur Monolith: Puma (OS-Threaded) vs Falcon (Async-Fiber)
Perusahaan Anda memiliki arsitektur monolitik yang menangani dua jenis domain trafik utama:
1. **Core Banking API**: Melakukan kalkulasi kriptografi finansial intensif, validasi relasional kompleks, dan interaksi I/O database SQL rendah latency.
2. **Realtime Notification Engine**: Menahan ribuan koneksi HTTP SSE (Server-Sent Events) dan Webhook streaming yang pasif menunggu event dari message broker (99% waktu eksekusi adalah I/O wait).

Manajemen berencana melakukan standarisasi global server web: seluruh sistem dipaksa migrasi ke **Falcon** (berbasis Ruby Fibers / Async engine) untuk memotong biaya server.

#### Pertanyaan Diagnostik:
1. Lakukan audit arsitektural komprehensif: Jelaskan konsekuensi performa jika Core Banking API (dengan dependensi gem C-extensions native yang memanggil blocking I/O dan CPU intensive routine) dipindahkan ke Falcon.
2. Apa yang terjadi pada *Fiber event-loop* Falcon jika sebuah thread atau fiber memanggil gem yang mengeksekusi C library yang tidak *fiber-aware* (misalnya driver database native atau gem kriptografi non-blocking)?
3. Rancang arsitektur deployment hibrida yang optimal: Bagaimana Anda membagi beban kerja kedua domain tersebut, instansiasi server runtime apa yang harus dipilih untuk masing-masing domain, dan bagaimana strategi routing di level reverse-proxy/load-balancer (misal: NGINX / Envoy)?

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Zero-Allocation Event Pipeline Engine

#### Problem Statement
Anda ditugaskan mendesain sebuah komponen *core telemetry ingestor* berbentuk Rack Middleware / Ruby Engine independen yang bertugas memproses *event streams* berformat JSON line melalui HTTP POST `/telemetry`. Komponen ini harus sanggup melayani throughput **5.000 RPS per container instance** dengan alokasi memori mendekati **zero-allocation** pada jalur kritis (*hot path*), mencegah latensi tail P99 di atas 20ms akibat GC pausing.

#### Requirements
1. **Zero/Low Allocation Parsing**: Hindari pembuatan objek *ephemeral string* atau *hash parsing* berulang pada setiap request. Gunakan streaming parser atau *in-place buffer recycling*.
2. **Buffer Ring Queue (Thread-Safe)**: Implementasikan *lock-free* atau *low-overhead circular ring buffer* berbasis Array Ruby murni atau thread-safe queue berkapasitas tetap (bounded buffer) untuk menyerap data event tanpa memicu realokasi array.
3. **Flush Worker Daemon**: Jalankan background worker berbasis *Dedicated OS Thread* yang melakukan *batch flushing* data dari buffer ke mock storage (misal: penulisan chunked binary/compressed output) setiap 500ms atau ketika buffer mencapai 80% kapasitas.
4. **Graceful Shutdown Subsystem**: Ketika menerima sinyal OS `SIGTERM` / `SIGINT`, sistem harus:
   - Menghentikan penerimaan request baru via Rack (mengembalikan HTTP 503).
   - Memproses seluruh sisa event yang masih tertinggal di dalam Ring Buffer sampai bersih (*drain buffer*).
   - Menutup koneksi/file descriptor target secara aman dalam toleransi waktu *grace period* (maksimal 5 detik) tanpa kehilangan 1 data pun (*zero data loss*).
5. **Observability Hook**: Ekspos metrik internal real-time tanpa APM berbayar melalui endpoint `/metrics`:
   - Alokasi memori via `GC.stat` (khususnya `:total_allocated_objects`, `:major_gc_count`, `:minor_gc_count`).
   - Kapasitas buffer saat ini (*fill rate*).
   - Total events processed vs dropped.

#### Constraints
- Runtime: MRI Ruby 3.2+ (Wajib kompatibel dengan GVL semantics).
- Library: Dilarang menggunakan Rails/ActiveSupport. Hanya diperbolehkan menggunakan Ruby Standard Library murni dan gem `rack` sebagai interface interface interface HTTP.
- Memory: RSS container tidak boleh naik lebih dari 15MB setelah dibombardir 500.000 request benchmark via tools seperti `wrk` atau `k6`.

#### Expected Output
1. File implementasi mandiri (misal: `telemetry_engine.rb`) yang berisi:
   - Kelas `TelemetryEngine::RingBuffer` (bounded, concurrent-safe).
   - Kelas `TelemetryEngine::CollectorMiddleware` (Rack middleware).
   - Kelas `TelemetryEngine::Flusher` (Background processing, thread control).
2. Skrip pengujian benchmarking mandiri yang membuktikan performa GC:
   - Menghitung delta alokasi objek (`GC.stat(:total_allocated_objects)`) sebelum dan sesudah 50.000 eksekusi simulasi request.
   - Output log verifikasi mekanisme *Graceful Drain* saat `Process.kill("TERM", ...)` di-trigger.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur internal Ruby VM (YARV) dan implikasi Global VM Lock (GVL) terhadap eksekusi paralel multi-core.
- [ ] Siklus hidup memori Ruby: Struktur RVALUE, Heap Pages, Empty/Free/Eden Pages, serta proses Sweep vs Compact.
- [ ] Perbedaan fundamental antara Minor GC (young generation) dan Major GC (full mark & sweep) serta pemicunya (`malloc_limit` vs `oldmalloc_limit`).
- [ ] Mengapa alokasi memori `T_STRING` pendek (di bawah 23 bytes) masuk ke dalam *embedded string* (tanpa alokasi heap C terpisah) sedangkan string panjang mengalokasikan memori via `malloc`.
- [ ] Karakteristik *Copy-on-Write (CoW)* dan bagaimana tindakan kompilasi/pemuatan kode (*eager loading*) di Puma Master memaksimalkan efisiensi CoW.
- [ ] Mekanisme deteksi bottleneck: Membedakan issue I/O wait, Database Lock Contention, GVL Contention, dan GC Pauses pada grafik APM.
- [ ] Batasan dan arsitektur konkurensi Ruby modern: Ractor (Share-nothing actor model), Fiber Scheduler (Async evented), dan Native OS Threads.

### Saya tidak perlu menghafal:
- [ ] Kode sumber C-level internal dari fungsi alokator YARV (`vm_eval.c` atau `gc.c`).
- [ ] Nilai byte heksadesimal dari flag internal object flags (`FL_PROMOTED`, `FL_FREEZE`, dll).
- [ ] Seluruh daftar konfigurasi variabel *environment* `RUBY_GC_*` di luar variabel inti tuning heap dan malloc.
- [ ] Sintaks mikro implementasi library parsing format data pihak ketiga secara mendetail.

### Saya harus bisa melakukan:
- [ ] Menghubungkan profiler CPU sampling (`StackProf` / `rbspy`) pada proses Ruby produksi yang sedang berjalan tanpa mematikan instance (*zero-downtime diagnostic*).
- [ ] Membaca, menganalisis, dan menemukan akar masalah kebocoran memori dari artefak file *Heap Dump* (`dump_all`).
- [ ] Mengganti alokator memori standar Linux sistem dengan `LD_PRELOAD=/usr/lib/libjemalloc.so` di dalam Dockerfile produksi dan menguji dampaknya terhadap RSS.
- [ ] Menghitung dan mengonfigurasi rasio yang tepat antara Puma workers, Puma threads, dan Database Connection Pool pada cluster Kubernetes berdasar CPU/Memory quota.
- [ ] Melakukan refactoring kode Ruby pada *hot-path* dari pendekatan alokasi objek tinggi (*idiomatic chaining* seperti `.map.filter.reject`) menjadi *zero-allocation mutation/in-place routines*.
- [ ] Mengimplementasikan *graceful degradation* dan *graceful shutdown signal handlers* (`SIGTERM`/`SIGQUIT`) pada service berbasis background jobs maupun web processes.