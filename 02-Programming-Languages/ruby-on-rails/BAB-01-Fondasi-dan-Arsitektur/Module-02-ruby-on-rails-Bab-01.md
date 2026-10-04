# Kurikulum Rekayasa Perangkat Lunak Enterprise
## Topik: Ruby on Rails (`02-Programming-Languages`)
### BAB 01: Fondasi dan Arsitektur
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, *Principal/Lead Engineer* diharapkan mampu:
- Mengurai secara komprehensif alur internal *booting* Rails, siklus hidup *Rack environment*, hingga pemrosesan I/O pada *application server* Puma.
- Mendiagnosis dan mengeliminasi *concurrency bottleneck*, *memory bloat*, serta implikasi *Global VM Lock* (GVL) pada MRI (*Matz's Ruby Interpreter*).
- Merancang arsitektur aplikasi Rails berbasis *multi-threaded* dan *multi-process* dengan konfigurasi *connection pooling*, *ActiveSupport Executor*, dan *Reloader* yang deterministik.
- Mengimplementasikan *custom middleware*, *zero-downtime deployment hooks*, serta optimasi alokasi memori melalui *jemalloc*.

---

### 2. Prerequisite
- Pemahaman mendalam tentang Ruby Object Model (metaprogramming, ancestor chain, eigenclass).
- Pengalaman mengelola infrastruktur Linux (POSIX threads, memory management, fork-exec model, signal handling: `SIGTERM`, `SIGUSR2`, `SIGKILL`).
- Penguasaan protokol HTTP/1.1 & HTTP/2 serta implementasi dasar MVC pada framework web.
- Menguasai dasar-dasar relasional database (PostgreSQL connection lifecycle, pool exhaustion, transaction isolation levels).

---

### 3. Concept & Internal Architecture

#### 3.1 The Rack Protocol & Middleware Stack
Rails dibangun di atas antarmuka Rack. Secara formal, aplikasi Rack adalah objek Ruby apa pun yang merespons pesan `.call(env)` dan mengembalikan struktur data *3-element array*:
$$\text{Response} = [\text{status\_code: Integer}, \text{headers: Hash}, \text{body: Enumerable}]$$

Dalam Rails, `Rails.application` itu sendiri merupakan aplikasi Rack level teratas. Permintaan HTTP melewati tumpukan (*stack*) middleware berurutan yang dibangun menggunakan pola desain *Chain of Responsibility*. 

```
Client HTTP Request
       │
       ▼
 [Reverse Proxy: Nginx / ALB]
       │
       ▼
 [Puma Server (Reactor -> Thread Pool)]
       │
       ▼
 [Rack Middleware Stack]
   ├─ ActionDispatch::HostAuthorization
   ├─ Rack::Sendfile
   ├─ ActionDispatch::Static
   ├─ ActionDispatch::Executor ───► (Wraps execution in Rails Executor)
   ├─ ActiveSupport::Cache::Strategy::LocalCache
   ├─ Rack::Runtime
   ├─ ActionDispatch::RequestId
   ├─ ActionDispatch::RemoteIp
   ├─ Rails::Rack::Logger
   ├─ ActionDispatch::ShowExceptions
   ├─ ActionDispatch::DebugExceptions
   ├─ ActionDispatch::Callbacks
   ├─ ActiveRecord::Migration::CheckPending
   └─ Rack::Head / Rack::ConditionalGet
       │
       ▼
 [ActionDispatch::Routing::RouteSet]
       │
       ▼
 [Controller Invocation: ActionController::Metal / Base]
```

#### 3.2 Puma Internals: Reactor, Worker, and Thread Pool
Puma menggunakan arsitektur *hybrid multi-process* dan *multi-threaded* (sering disebut *Clustered Mode*):
1. **Master Process**: Mengikat soket TCP/UNIX domain, mendengarkan sinyal OS, dan mengelola *child worker processes* menggunakan sistem `fork()`.
2. **Workers (Processes)**: Terisolasi dalam ruang memori terpisah, memanfaatkan *Copy-on-Write* (CoW) dari kernel Linux untuk efisiensi RAM saat *preloading* aplikasi (`preload_app!`).
3. **Reactor**: Menggunakan mekanisme *evented I/O* OS-spesifik (`epoll` di Linux, `kqueue` di BSD/macOS) untuk menahan koneksi *slow client* tanpa memblokir thread kerja utama.
4. **Thread Pool**: Setiap worker memiliki sebuah thread pool elastis (didefinisikan oleh `RAILS_MIN_THREADS` dan `RAILS_MAX_THREADS`). Worker mengambil koneksi HTTP yang telah selesai dibaca oleh reactor dan mengeksekusinya via Rack stack.

#### 3.3 Ruby MRI Concurrency, GVL, dan Rails Executor
Ruby MRI memiliki *Global VM Lock* (GVL). GVL memastikan bahwa hanya ada satu *native thread* yang mengeksekusi instruksi bytecode Ruby pada saat yang sama.
- **I/O Bound**: Saat thread melakukan panggilan I/O (akses database PostgreSQL, panggilan Redis, membaca file), thread tersebut melepaskan (*releases*) GVL. Thread lain dalam worker yang sama dapat mengeksekusi instruksi CPU.
- **CPU Bound**: Thread komputasi berat akan memonopoli GVL, menyebabkan *latency spike* pada thread paralel di worker yang sama.

Rails mengelola konkurensi melalui **`ActiveSupport::Executor`** dan **`ActiveSupport::Reloader`**. Executor bertanggung jawab atas:
- Manajemen siklus hidup thread-local storage (`CurrentAttributes`).
- Pengembalian otomatis koneksi database ke `ActiveRecord::ConnectionAdapters::ConnectionPool`.
- Mengaktifkan dan menonaktifkan *query cache*.

---

### 4. Why & What

| Dimensi | Penjelasan Teknis | Dampak pada Sistem Enterprise |
| :--- | :--- | :--- |
| **Why Puma Clustered Mode?** | Menggabungkan paralelisasi CPU antar *core* via multi-process dengan efisiensi memori I/O non-blocking via multi-threading. | Memaksimalkan *throughput* per node tanpa terkena degradasi throughput akibat saturasi GVL pada single-core. |
| **Why ActiveSupport::Executor?** | Mengisolasi *state* request dan menjamin *resource cleanup* (koneksi database, cache context). | Mencegah *connection leak* pada database pool dan memotong kebocoran memori antar request concurrent. |
| **What is Jemalloc?** | Alternatif *general-purpose allocator* dari FreeBSD yang dirancang untuk mencegah fragmentasi memori. | Mengurangi konsumsi memori Rails (memory bloat) hingga 25%–40% di lingkungan multi-threaded Linux (glibc ptmalloc issue). |

---

### 5. How (Workflow Detail)

```
                    Siklus Hidup Eksekusi Request
                    
 1. Socket Accept       Puma OS-level socket listener menerima TCP SYN.
        │
 2. Puma Reactor        Membaca HTTP payload (headers/body) secara non-blocking.
        │
 3. Thread Handoff      Request lengkap dimasukkan ke Thread Pool Queue Puma.
        │
 4. Rails Executor      ActiveSupport::Executor.wrap membungkus thread context:
        │               - Menginisialisasi Thread-Local (CurrentAttributes).
        │               - Mengaktifkan ActiveRecord Query Cache.
        │
 5. Middleware Stack    Array middleware dipanggil secara rekursif (.call).
        │
 6. Route Match         RouteSet mencocokkan URI & HTTP Verb -> Controller#Action.
        │
 7. DB Check-out        ActiveRecord meminjam koneksi dari pool (thread-safe checkout).
        │
 8. Action Execution    Logika domain dijalankan; views/JSON diserialisasi.
        │
 9. DB Check-in         Koneksi DB dikembalikan/dilepaskan ke Pool.
        │
10. Executor Complete   Membersihkan thread-local variables dan local caches.
        │
11. Client Flush        Response dialirkan kembali ke client socket.
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sebuah restoran skala besar:
- **Puma Master Process**: Manajer operasional restoran yang membuka pintu gedung dan mengawasi dapur.
- **Worker Process (Fork)**: Dapur independen. Masing-masing memiliki perlengkapan masak sendiri (ruang memori sendiri). Jika satu dapur kebakaran (segfault/crash), dapur lain tetap beroperasi normal.
- **Puma Reactor**: Pelayan depan yang menyambut tamu dan mencatat seluruh pesanan sampai selesai sebelum pesanan tersebut diserahkan ke koki.
- **Thread Pool (Koki)**: Koki di dalam setiap dapur. Koki dapat bergantian memasak saat panci sedang mendidih (I/O wait), tetapi jika satu koki sedang mencincang daging secara intensif (CPU bound/GVL lock), talenan hanya bisa dipakai satu koki pada satu waktu.
- **ActiveSupport::Executor**: Asisten dapur yang membersihkan talenan, mengembalikan pisau ke rak penyimpanan, dan membuang sisa makanan setelah tiap piring disajikan.

```
+-------------------------------------------------------------------------+
|                          PUMA MASTER PROCESS                            |
|  [Socket: 0.0.0.0:3000]                                                 |
+--------------------+--------------------------------+-------------------+
                     | fork()                         | fork()
                     ▼                                ▼
       +---------------------------+    +---------------------------+
       |     WORKER PROCESS 0      |    |     WORKER PROCESS 1      |
       |  (Memory: CoW baseline)   |    |  (Memory: CoW baseline)   |
       |                           |    |                           |
       |  +---------------------+  |    |  +---------------------+  |
       |  |    Puma Reactor     |  |    |  |    Puma Reactor     |  |
       |  | (epoll/kqueue loop) |  |    |  | (epoll/kqueue loop) |  |
       |  +----------+----------+  |    |  +----------+----------+  |
       |             |             |    |             |             |
       |  +----------v----------+  |    |  +----------v----------+  |
       |  |  Queue (Threadpool) |  |    |  |  Queue (Threadpool) |  |
       |  +---+------+------+---+  |    |  +---+------+------+---+  |
       |      |      |      |      |    |      |      |      |      |
       |    Thread Thread Thread   |    |    Thread Thread Thread   |
       |     [1]    [2]    [3]     |    |     [1]    [2]    [3]     |
       |      |      |      |      |    |      |      |      |      |
       |   +--v------v------v--+   |    |   +--v------v------v--+   |
       |   |  Rails Executor   |   |    |   |  Rails Executor   |   |
       |   |  (Middleware)     |   |    |   |  (Middleware)     |   |
       |   +-------------------+   |    |   +-------------------+   |
       +---------------------------+    +---------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Pure Rack Middleware & Puma Inspection
File: `config.ru`
Mendemonstrasikan pipeline Rack dasar, manipulasi header, dan integrasi response:

```ruby
# config.ru
# frozen_string_literal: true

require 'rack'
require 'json'

# Custom middleware untuk mengukur execution latency pada tingkatan Rack
class RuntimeDiagnosticsMiddleware
  def initialize(app)
    @app = app
  end

  def call(env)
    start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    
    # Delegasi ke layer berikutnya
    status, headers, response = @app.call(env)
    
    duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
    headers['X-Runtime-Microseconds'] = (duration * 1_000_000).to_i.to_s
    headers['X-Puma-Worker'] = Process.pid.to_s

    [status, headers, response]
  end
end

class HealthApp
  def self.call(env)
    payload = {
      status: 'UP',
      ruby_version: RUBY_VERSION,
      thread_id: Thread.current.object_id,
      process_id: Process.pid
    }

    [
      200,
      { 'Content-Type' => 'application/json' },
      [payload.to_json]
    ]
  end
end

use Rack::Deflater
use RuntimeDiagnosticsMiddleware
run HealthApp
```

#### 7.2 Practical Example: Enterprise Production-Ready Configuration & Middleware

##### File: `config/puma.rb`
Konfigurasi Puma Clustered mode untuk lingkungan produksi berbasis containerized Linux:

```ruby
# frozen_string_literal: true

# Jumlah worker setara dengan vCPU cores (biasanya 1 worker per physical/virtual core)
workers_count = Integer(ENV.fetch('WEB_CONCURRENCY', 2))
threads_count = Integer(ENV.fetch('RAILS_MAX_THREADS', 5))

threads threads_count, threads_count

if workers_count > 1
  workers workers_count
  
  # Forking worker setelah seluruh kode Rails dimuat ke RAM untuk memaksimalkan Copy-On-Write
  preload_app!

  before_fork do
    # Disconnect database master connection pool sebelum fork untuk mencegah socket sharing
    ActiveRecord::Base.connection_handler.clear_all_connections!(:all) if defined?(ActiveRecord::Base)
  end

  on_worker_boot do
    # Buat pool koneksi database baru khusus untuk child process ini
    ActiveRecord::Base.establish_connection if defined?(ActiveRecord::Base)
  end
end

# Mengikat listener socket
port ENV.fetch('PORT', 3000)
environment ENV.fetch('RAILS_ENV', 'production')

# Puma shutdown & kill timeout configuration
worker_timeout 60
tag 'enterprise-rails-api'
```

##### File: `app/middleware/enterprise_context_middleware.rb`
Middleware untuk injeksi konteks pelacakan (*distributed tracing*), mitigasi timeout I/O, serta manajemen siklus hidup thread yang aman:

```ruby
# frozen_string_literal: true

module Enterprise
  class ContextMiddleware
    CORRELATION_HEADER = 'HTTP_X_CORRELATION_ID'

    def initialize(app)
      @app = app
    end

    def call(env)
      # Memanfaatkan Rails Executor untuk menjamin wrap kontekstual
      Rails.application.executor.wrap do
        correlation_id = env[CORRELATION_HEADER] || SecureRandom.uuid
        
        # Simpan konteks pada CurrentAttributes (Aman dalam batas Executor)
        CurrentContext.correlation_id = correlation_id
        CurrentContext.request_start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

        status, headers, response = @app.call(env)

        headers['X-Correlation-ID'] = correlation_id
        [status, headers, response]
      end
    end
  end
end
```

##### File: `app/models/current_context.rb`
Penggunaan `ActiveSupport::CurrentAttributes` dengan penanganan memori yang aman:

```ruby
# frozen_string_literal: true

class CurrentContext < ActiveSupport::CurrentAttributes
  attribute :correlation_id, :request_start_time

  # Mencegah memory retention jika digunakan di luar konteks request biasa
  resets do
    # Callback pembersihan eksplisit
  end
end
```

---

### 8. Real World Case Study: High-Throughput Payment Ingestion Pipeline

#### Background
Sebuah payment gateway memproses ~4.000 *inbound webhook requests/detik* dari berbagai bank integrasi. Sistem berjalan pada AWS ECS Fargate menggunakan image Rails 7 berbasis MRI Ruby.

#### Problem
Sistem mengalami lonjakan respons time (*p99 latency* melonjak dari 45ms ke 3.200ms) dan kemunculan galat:
`ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.
Analisis metrik menunjukkan CPU hanya berada pada utilisasi 35%, namun konsumsi memori terus meningkat (memory bloat) hingga menyentuh OOM (*Out Of Memory Killer*), memicu *rolling restart* terus-menerus.

#### Diagnosis & Root Cause
1. **Puma Threads vs DB Pool Mismatch**: `RAILS_MAX_THREADS` dikonfigurasi ke 16, tetapi PostgreSQL pool size (`pool:`) pada `database.yml` diatur ke nilai default 5. Ketika terjadi lonjakan I/O, thread 6 hingga 16 mengantre untuk koneksi database, menyebabkan deadlock lokal dan timeout.
2. **Glibc Memory Fragmentation**: Alokator default Linux (`glibc ptmalloc`) menahan arena memori yang terfragmentasi saat Puma mengalokasikan string berukuran masif (payload webhook JSON 5MB+). Memori virtual tidak dikembalikan ke OS.
3. **GVL Contention**: Penguraian JSON webhook dilakukan secara synchronous pada main thread controller tanpa schema streaming.

#### Resolution Architecture
1. **Sinkronisasi Kapasitas Pool DB**:
   $$\text{DB Pool Size} \ge \text{RAILS\_MAX\_THREADS} + \text{Background Threads}$$
   Dikonfigurasi `pool: <%= ENV.fetch("RAILS_MAX_THREADS", 5) %>` dengan buffer koneksi 2 untuk instrumentation.
2. **Jemalloc Injection**:
   Menambahkan dynamic linking `libjemalloc2` ke dalam *Dockerfile*:
   ```dockerfile
   RUN apt-get update && apt-get install -y libjemalloc2
   ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2
   ENV MALLOC_CONF="dirty_decay_ms:1000,muzzy_decay_ms:1000"
   ```
3. **Puma Offloading via Rack Raw Input Parsing**:
   Memisahkan webhook ingestion controller menjadi minimal Rack endpoints (`ActionController::API`), memvalidasi signature secara streaming, dan mendelegasikan parsing JSON kompleks ke background jobs via Redis:

```ruby
# app/controllers/api/v1/webhooks_controller.rb
module Api
  module V1
    class WebhooksController < ActionController::API
      def receive
        # Fast extraction tanpa memicu objek JSON besar di controller
        payload_string = request.raw_post
        signature = request.headers['X-Signature']

        unless WebhookSecurity.verify(payload_string, signature)
          return render json: { error: 'Invalid Signature' }, status: :unauthorized
        end

        # Enqueue payload mentah ke queue Sidekiq (dieksekusi asinkron)
        IngestWebhookJob.perform_async(payload_string, CurrentContext.correlation_id)

        # Segera kembalikan 202 Accepted dalam rentang < 8ms
        head :accepted
      end
    end
  end
end
```

#### Results
- **P99 Latency**: Turun stabil dari 3.200ms ke 12ms.
- **Memory Footprint**: Konsumsi baseline RAM per container flat di 450MB tanpa kebocoran (*leak/bloat eliminated*).
- **Zero Connection Errors**: Beban throughput database pool stabil dengan *zero checkout wait times*.

---

### 9. Trade-offs

| Pendekatan / Keputusan | Keuntungan | Biaya / Konsekuensi (*Trade-off*) |
| :--- | :--- | :--- |
| **High Thread Count (`RAILS_MAX_THREADS` > 16)** | Mengakomodasi operasi I/O tunggu tinggi (banyak external calls) pada footprint instance kecil. | Risiko *GVL contention* melonjak saat eksekusi Ruby code; membutuhkan *connection pool* database yang masif ke server Postgres; potensi *context switching overhead*. |
| **High Worker Count (Multi-process fokus)** | Isolasi memori sempurna; *GVL isolation* absolut (performa komputasi CPU paralel optimal). | Penggunaan baseline memori sangat tinggi (setiap worker mengonsumsi memori sendiri meskipun ada Copy-on-Write). |
| **Puma `preload_app!` Enabled** | Mempercepat *worker boot time*; menghemat RAM via OS Copy-on-Write sharing. | Tidak bisa menggunakan fitur Puma *Phased Restart* (`pumactl phased-restart`); deployment wajib *zero-downtime rolling restart*. |
| **Jemalloc Deployment** | Mengurangi fragmentasi memori (*heap fragmentation*) dan mengembalikan RAM ke kernel lebih agresif. | Kompleksitas *build image* bertambah; debugging memory issue menjadi lebih rumit karena membutuhkan tooling profiling jemalloc spesifik. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1 Database Connection Pool Starvation
- **Gejala**: Kemunculan error `ActiveRecord::ConnectionTimeoutError`.
- **Penyebab**: `RAILS_MAX_THREADS` lebih besar daripada nilai `pool:` di `config/database.yml`.
- **Solusi**: Pastikan rumus `pool = Integer(ENV['RAILS_MAX_THREADS'] || 5)` terpenuhi di semua environment produksi.

#### 10.2 Thread-Unsafe State Sharing via Class Variables
- **Kode Bermasalah**:
  ```ruby
  class MetricsCollector
    @@counters = {} # Thread-unsafe! Dishare di seluruh thread dalam satu worker.

    def self.increment(key)
      @@counters[key] ||= 0
      @@counters[key] += 1 # Rentan Race Condition / Data Loss
    end
  end
  ```
- **Solusi**: Gunakan thread-safe data structures (`Concurrent::Map` dari gem `concurrent-ruby`) atau `ActiveSupport::CurrentAttributes` untuk variabel per-request:
  ```ruby
  require 'concurrent-ruby'

  class MetricsCollector
    @counters = Concurrent::Map.new(0)

    def self.increment(key)
      @counters.compute(key) { |val| (val || 0) + 1 }
    end
  end
  ```

#### 10.3 Manual Thread Spawning Without Executor Wrapper
- **Kode Bermasalah**:
  ```ruby
  def async_audit_log(event)
    Thread.new do
      AuditLog.create!(data: event) # MEMORY & CONNECTION LEAK!
    end
  end
  ```
- **Penyebab**: Koneksi database yang diambil oleh `AuditLog` di thread manual tidak akan pernah dikembalikan ke pool secara otomatis, memicu pool exhaustion.
- **Solusi**: Bungkus setiap eksekusi thread manual dengan Rails Executor:
  ```ruby
  def async_audit_log(event)
    Thread.new do
      Rails.application.executor.wrap do
        AuditLog.create!(data: event)
      end
    end
  end
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Memory Allocator**: Wajib menggunakan `jemalloc` sebagai alokator bawaan container produksi.
2. [ ] **Pool Equation**: Pastikan `DB Pool Size >= RAILS_MAX_THREADS`.
3. [ ] **Preload App**: Pastikan `preload_app!` diaktifkan di `config/puma.rb` pada container multi-core.
4. [ ] **Timeout Boundaries**: Atur `Rack::Timeout` (service timeout: 15–25s) lebih rendah dibanding reverse-proxy/load balancer timeout (30–60s) dan Puma `worker_timeout`.
5. [ ] **No Class Variable Mutations**: Jangan pernah menulis ke *class variables* (`@@var`) atau *class instance variables* (`@var` di class level) di dalam alur request-response.
6. [ ] **Connection Disconnect on Fork**: Pastikan memutus koneksi database master di `before_fork` dan melakukan re-establish di `on_worker_boot`.
7. [ ] **Graceful Shutdown**: Tangani `SIGTERM` dengan benar; berikan grace period minimal 30 detik pada orchestration platform (Kubernetes `terminationGracePeriodSeconds`) sebelum mengirim `SIGKILL`.

---

### 12. Hands-on Practice

Buat dan jalankan modul praktikum ini di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Struktur Minimal
```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

#### Langkah 2: Buat `Gemfile`
```ruby
# hands-on/m02/Gemfile
source 'https://rubygems.org'

ruby '>= 3.2.0'

gem 'rails', '~> 7.1.0'
gem 'puma', '~> 6.4'
gem 'pg', '~> 1.5'
gem 'concurrent-ruby', '~> 1.2'
```

Jalankan instalasi:
```bash
bundle install
```

#### Langkah 3: Konfigurasi Puma Clustered Profiler
Buat file `hands-on/m02/puma_server.rb`:
```ruby
# hands-on/m02/puma_server.rb
require 'rack'
require 'rack/handler/puma'

class DiagnosticApp
  def self.call(env)
    # Simulasi I/O wait terkelola
    sleep(0.05) 
    
    body = {
      pid: Process.pid,
      thread: Thread.current.object_id,
      ruby_concurrency: "GVL Active"
    }.to_s

    [200, { 'Content-Type' => 'text/plain', 'Content-Length' => body.bytesize.to_s }, [body]]
  end
end

Rack::Handler::Puma.run(
  DiagnosticApp,
  Port: 9292,
  Threads: '4:4',
  Workers: 2,
  Preload: true
)
```

#### Langkah 4: Eksekusi Profiling Sederhana
Jalankan server:
```bash
bundle exec ruby puma_server.rb
```
Buka terminal lain dan jalankan inspeksi konkurensi (menggunakan `curl` paralel):
```bash
for i in {1..8}; do curl -s http://localhost:9292 & done; wait
```
*Perhatikan variasi respons PID dan Thread Object ID yang mencerminkan isolasi proses dan pool thread.*

---

### 13. Exercise

#### Level Easy
Ubah middleware Rack dasar pada seksi 7.1 untuk menyuntikkan response header kustom `X-Server-Time` yang berisi epoch timestamp presisi milidetik.
*Kriteria Sukses*: Header `X-Server-Time` terverifikasi via `curl -I`.

#### Level Medium
Buat sebuah Rack Middleware yang mendeteksi request payload yang berukuran lebih besar dari 2 MB. Jika ditemukan, batalkan eksekusi pipeline dan langsung kembalikan status `413 Payload Too Large` dalam format JSON tanpa membebani memori ActionController.
*Kriteria Sukses*: Request dengan payload besar langsung di-short-circuit di layer Rack sebelum alokasi controller terjadi.

#### Level Hard
Rancang modul thread pool kustom menggunakan `Concurrent::ThreadPoolExecutor` di dalam Rails. Modul ini bertugas menjalankan proses analitik audit. Modul harus:
1. Menjamin thread-safety.
2. Menggunakan `ActiveSupport::Executor.wrap` untuk mengeksekusi blok kode.
3. Menangani skenario di mana pool queue penuh (*rejection policy*) dengan mengeksekusi log fallback secara sinkron tanpa melempar unhandled exception ke client.
*Kriteria Sukses*: Uji dengan beban stress testing; tidak ada kebocoran koneksi database (`ActiveRecord::ConnectionTimeoutError`) dan memory usage tetap stabil.

---

### 14. Challenge

**Skenario**:
Platform Anda memproses sistem streaming laporan finansial dengan response body yang tidak terbatas (Server-Sent Events / SSE atau CSV chunk streaming 10GB). Penggunaan memory Rails membengkak drastis saat prosesor streaming berjalan bersamaan dengan traffic biasa pada Puma.

**Tantangan Arsitektur**:
1. Buat mekanisme streaming yang mengalirkan response data langsung dari PostgreSQL (`find_each` dengan *cursor fetch*) ke klien secara *chunked transfer encoding* melalui Rack response body `Enumerable`.
2. Pastikan proses streaming ini tidak memblokir Puma worker thread secara berkepanjangan tanpa pelepasan GVL.
3. Cegah memory buffering di layer middleware (seperti `Rack::Deflater` atau buffering proxy).
4. Pastikan koneksi database ditutup secara deterministik saat klien memutuskan koneksi HTTP secara sepihak di tengah proses streaming (*client disconnect handling* via `Rack::Chunked` socket interruption).

*Deliverable*: Berikan rancangan arsitektur, konfigurasi Puma, dan implementasi Controller Action/Rack Body yang menyelesaikan limitasi di atas tanpa crash atau resource leak.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Questions
1. **Apa yang mendefinisikan sebuah aplikasi Rack yang valid menurut spesifikasi standar?**
   - *Jawaban*: Objek apa pun yang merespons metode `.call(env)` dengan menerima satu argumen Hash lingkungan dan mengembalikan array tiga elemen: `[status (Integer), headers (Hash), body (Enumerable)]`.
2. **Apa fungsi utama dari parameter `preload_app!` pada `config/puma.rb`?**
   - *Jawaban*: Memuat seluruh kode aplikasi Rails ke dalam Master process sebelum membuat child worker (`fork`), memungkinkan kernel OS menerapkan *Copy-on-Write* (CoW) untuk menghemat alokasi memori antar proses.
3. **Mengapa Rails memerlukan `ActiveSupport::Executor` saat menjalankan thread baru secara manual?**
   - *Jawaban*: Untuk mengelola daur hidup konteks eksekusi aplikasi, memastikan koneksi database dikembalikan ke pool secara otomatis, mereset Thread-Local attributes, dan membersihkan query cache saat eksekusi thread selesai.
4. **Apa perbedaan mendasar antara Puma Single Mode dan Puma Clustered Mode?**
   - *Jawaban*: Single Mode hanya menjalankan satu proses dengan satu atau banyak thread (bagus untuk resource kecil/kontainer single core), sedangkan Clustered Mode menjalankan satu Master Process yang mengelola banyak Worker Process independen via `fork()`.
5. **Apa fungsi dari perintah Linux `LD_PRELOAD` terkait dengan `jemalloc` pada container Rails?**
   - *Jawaban*: Menginstruksikan dynamic linker sistem operasi untuk memuat pustaka alokasi memori `jemalloc` menggantikan default alokator `glibc ptmalloc`, guna menghindari fragmentasi memori (*heap memory bloat*).

#### Intermediate Questions
1. **Bagaimana cara kerja penanganan konkurensi Ruby MRI pada request yang sifatnya Network I/O Bound di bawah server Puma?**
   - *Jawaban*: Meskipun ada GVL (Global VM Lock), Ruby MRI melepaskan GVL secara otomatis saat menunggu I/O operasi sistem (seperti response SQL atau HTTP request). Akibatnya, thread lain dalam pool Puma yang sama dapat langsung dieksekusi oleh interpreter tanpa menunggu proses I/O thread pertama selesai.
2. **Apa dampak yang terjadi jika nilai `RAILS_MAX_THREADS` diatur ke 10, tetapi konfigurasi `pool` di `database.yml` diatur ke 5?**
   - *Jawaban*: Jika terdapat lebih dari 5 request concurrent pada worker tersebut yang membutuhkan akses database, thread ke-6 hingga ke-10 akan mengalami starvation saat mencoba melakukan *check-out* koneksi dari pool. Jika antrean melebihi `checkout_timeout` (default 5 detik), Rails akan melempar `ActiveRecord::ConnectionTimeoutError`.
3. **Mengapa modifikasi Class Instance Variable (`@variable` pada level class) berbahaya di lingkungan produksi Puma?**
   - *Jawaban*: Karena di lingkungan multi-threaded Puma, seluruh thread di dalam satu worker process berbagi ruang memori yang sama. Modifikasi class instance variable menciptakan *race condition* karena operasi tersebut tidak atomik dan state dapat tertimpa antar thread secara inkonsisten.
4. **Apa fungsi dari middleware `ActionDispatch::ShowExceptions` dibanding `ActionDispatch::DebugExceptions`?**
   - *Jawaban*: `ActionDispatch::DebugExceptions` bertugas menangkap error dan merender halaman stack trace teknis untuk keperluan debugging (aktif di development). Sedangkan `ActionDispatch::ShowExceptions` mengonversi exception menjadi response HTTP rescue yang semestinya (seperti halaman error 500/404 via `exceptions_app`) untuk pengguna akhir.
5. **Bagaimana Puma Reactor membantu menangani skenario "Slowloris" attack atau slow clients?**
   - *Jawaban*: Reactor Puma menggunakan evented I/O non-blocking (`epoll`/`kqueue`). Reactor menahan koneksi lambat dan mengumpulkan header serta body HTTP secara parsial tanpa menggunakan thread kerja dari thread pool. Thread kerja hanya dialokasikan setelah payload request diterima lengkap oleh Reactor.

#### Skenario Kasus Produksi
1. **Skenario 1**: Sebuah aplikasi Rails mengalami lonjakan alokasi memori secara bertahap setiap kali worker beroperasi (*gradual memory climb*). Setelah worker mengonsumsi 1.5GB RAM, Puma Worker Killer me-restart worker tersebut, menimbulkan *latency spikes*. Namun, memori di lingkungan staging dengan volume trafik rendah tidak pernah naik.
   - *Analisis & Aksi*: Kemungkinan besar terjadi fragmentasi heap pada `glibc` yang dikombinasikan dengan alokasi objek JSON masif atau retain object pada thread-local variable/class variable. Langkah penyelesaian: (1) Pasang `jemalloc` via `LD_PRELOAD`, (2) Audit codebase dari penggunaan `Thread.current[:var]` yang tidak dibersihkan, ganti dengan `CurrentAttributes`, (3) Batasi alokasi payload besar menggunakan pagination ketat atau stream processing.
2. **Skenario 2**: Sistem microservice Rails memanggil REST API pihak ketiga di dalam controller action. Tiba-tiba waktu respons p99 seluruh sistem meningkat drastis, dan request yang tidak berhubungan dengan integrasi pihak ketiga ikut mengalami *slowdown*. CPU usage sangat rendah.
   - *Analisis & Aksi*: Panggilan HTTP eksternal tersebut memblokir Puma thread dan tidak memiliki limitasi *read timeout* yang agresif. Meskipun GVL dilepas saat I/O, seluruh thread pool akhirnya habis terpakai (*exhausted*) hanya untuk menunggu respons jaringan external API tersebut. Solusi: Konfigurasikan explicit timeout (misal: 2-3 detik) pada HTTP client (`Net::HTTP`, `Faraday`), dan pindahkan integrasi API lambat ke antrean background job asinkron (Sidekiq) alih-alih di web request cycle.
3. **Skenario 3**: Saat melakukan deployment container baru di Kubernetes, sejumlah transaksi checkout pelanggan gagal dengan error `502 Bad Gateway` selama masa pergantian pod berlangsung, padahal aplikasi menerapkan rolling update.
   - *Analisis & Aksi*: Pod menerima sinyal `SIGKILL` sebelum Puma selesai memproses in-flight requests, atau Pod dihapus dari Service endpoints setelah proses Puma dimatikan (race condition antara iptables deregistrasi dan termination). Solusi: Tambahkan `preStop` hook dengan perintah `sleep 5` pada pod lifecycle untuk memastikan Service endpoint berhenti mengarahkan traffic baru ke pod tersebut sebelum Puma menerima sinyal `SIGTERM`, serta konfigurasikan `terminationGracePeriodSeconds` yang cukup panjang bagi Puma untuk menyelesaikan drain request.

---

### 16. Summary
- Arsitektur web Rails bertumpu pada spesifikasi protokol Rack yang dieksekusi secara linier melalui middleware stack sebelum mencapai routing layer.
- Server Puma memadukan *process isolation* (Clustered Workers via `fork()`) untuk paralelisasi CPU lintas-core dengan *threading model* di tiap worker untuk efisiensi I/O.
- Walaupun Ruby MRI memiliki batasan Global VM Lock (GVL), thread Rails tetap efisien untuk beban aplikasi modern yang mayoritas bertumpu pada Network/Database I/O, asalkan alokasi resource seimbang.
- Parameter konfigurasi `RAILS_MAX_THREADS`, database connection pool, alokator memori `jemalloc`, dan batas isolasi `Rails.application.executor` adalah pilar penentu stabilitas, efisiensi memori, dan performa throughput aplikasi enterprise di lingkungan produksi.