# Kurikulum Enterprise Ruby: Arsitektur Web Skala Produksi
**Topik:** Ruby (`02-Programming-Languages`)  
**Bab 09:** Enterprise Web Architecture  
**Modul 02:** Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Membedah Arsitektur Internal Puma Server:** Memahami siklus hidup soket TCP, mekanika Reactor berbasis event multiplexing (`epoll`/`kqueue`), Thread Pool, dan manajemen *pre-forked worker* untuk memaksimalkan throughput pada MRI (*Matz's Ruby Interpreter*).
- **Mendesain dan Mengimplementasikan Rack 3 Pipeline:** Membangun *streaming middleware*, manipulasi *bidirectional I/O*, serta merancang rantai middleware modular yang aman terhadap *thread-safety* dan minim alokasi objek heap.
- **Mengoptimasi Utilisasi Memori & Concurrency:** Menerapkan strategi *Copy-on-Write* (CoW) allocation, integrasi `jemalloc`, modulasi *Garbage Collection compacting*, dan sinkronisasi kapasitas `ActiveRecord::ConnectionPool` terhadap metrik konkurensi Puma.
- **Mengeksekusi Strategi Zero-Downtime Deployment:** Mengkonfigurasi *Phased Restarts* via Unix Domain Sockets, *systemd socket activation*, dan orkestrasi terminasi graceful berbasis penanganan sinyal UNIX (`SIGTERM`, `SIGUSR1`, `SIGUSR2`).
- **Mendeteksi dan Memitigasi Bottleneck Produksi:** Mendiagnosis *thread starvation*, *GVL lock contention*, degradasi saturasi latensi akibat fragmentasi memori, serta mengatasi fenomena *thundering herd* pada lonjakan beban tinggi.

---

## 2. Prerequisites

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Ruby Concurrency & Runtime Internals:** Pemahaman mendalam tentang Ruby Thread, Fiber, Ractor, GVL (*Global VM Lock*), memori heap MRI, dan *Generational Garbage Collection*.
- **Protokol Jaringan & POSIX Low-Level:** Model soket TCP/IP, Unix Domain Sockets, sinyal POSIX (`SIGTERM`, `SIGINT`, `SIGCHLD`, `SIGUSR1/2`), serta I/O multiplexing (`select`, `epoll`).
- **Fondasi Rack & Rails/Sinatra Framework:** Memahami spesifikasi dasar antarmuka Rack (`env` Hash, Array `[status, headers, body]`) dan siklus hidup request-response HTTP standar.

---

## 3. Concept & Internal Architecture

Arsitektur aplikasi web Ruby tingkat enterprise dibangun di atas abstraksi berlapis: Web Server (Reverse Proxy) $\rightarrow$ Application Server (Puma/Falcon) $\rightarrow$ Rack Interface $\rightarrow$ Application Middleware $\rightarrow$ Endpoint Framework (Rails Engine/Hanami/Roda).

### 3.1 Puma Reactor & Threadpool Mechanics

Puma mengadopsi arsitektur *hybrid multi-process multi-threaded model*:
1. **Master Process:** Bertanggung jawab melakukan *binding* pada port TCP atau Unix Domain Socket. Master tidak menangani request HTTP secara langsung, melainkan mengelola *forking* worker processes (`Worker 0..N`) dan meneruskan file descriptor soket listener.
2. **Cluster Worker (Forked Process):** Tiap worker adalah proses sistem operasi terisolasi yang berjalan dengan GVL independen. Mengoptimalkan multi-core CPU dengan memori yang dibagikan pada awalnya menggunakan *Copy-on-Write (CoW)*.
3. **Reactor (Event Loop):** Menggunakan `nio4r` (berbasis `epoll` di Linux atau `kqueue` di BSD/macOS). Reactor memantau file descriptor soket dari klien yang lambat (*slow clients*). Soket hanya diteruskan ke *Thread Pool* setelah HTTP request payload selesai diterima secara penuh (mencegah serangan *Slowloris* dan *thread starvation*).
4. **Thread Pool (Worker Threads):** Kumpulan *worker threads* dinamis (`min_threads` hingga `max_threads`). Satu thread mengambil soket yang sudah siap, menginstansiasi *Rack environment*, mengeksekusi stack middleware, dan menuliskan response kembali ke soket sebelum mengembalikannya ke pool.

```
                    ┌─────────────────────────┐
                    │      Reverse Proxy      │
                    │   (Nginx/Envoy/ALB)     │
                    └────────────┬────────────┘
                                 │ TCP / Unix Domain Socket
                    ┌────────────▼────────────┐
                    │   Puma Master Process   │
                    │  (Signal & Worker Sup.) │
                    └──────┬───────────┬──────┘
             fork()        │           │        fork()
       ┌───────────────────┘           └───────────────────┐
       ▼                                                   ▼
┌─────────────────────────────┐             ┌─────────────────────────────┐
│       Puma Worker 0         │             │       Puma Worker 1         │
│  ┌───────────────────────┐  │             │  ┌───────────────────────┐  │
│  │ Reactor (epoll/kqueue)│  │             │  │ Reactor (epoll/kqueue)│  │
│  └───────────┬───────────┘  │             │  └───────────┬───────────┘  │
│              │ ready fd     │             │              │ ready fd     │
│  ┌───────────▼───────────┐  │             │  ┌───────────▼───────────┐  │
│  │  Thread Pool (1..N)   │  │             │  │  Thread Pool (1..N)   │  │
│  │ ┌──────┐ ┌──────┐     │  │             │  │ ┌──────┐ ┌──────┐     │  │
│  │ │Thr 1 │ │Thr 2 │ ... │  │             │  │ │Thr 1 │ │Thr 2 │ ... │  │
│  │ └──┬───┘ └──┬───┘     │  │             │  │ └──┬───┘ └──┬───┘     │  │
│  └────┼────────┼─────────┘  │             │  └────┼────────┼─────────┘  │
│       │        │            │             │       │        │            │
│  ┌────▼────────▼─────────┐  │             │  ┌────▼────────▼─────────┐  │
│  │  Rack Middleware Stack│  │             │  │  Rack Middleware Stack│  │
│  └───────────────────────┘  │             │  └───────────────────────┘  │
└─────────────────────────────┘             └─────────────────────────────┘
```

### 3.2 Rack 3 Specification & Streaming Abstraction

Pada spesifikasi Rack 3 (`rack 3.x`), kontrak arsitektur dirombak untuk mendukung performa tinggi:
- **Header Mutability:** Rack headers kini menggunakan *lowercase strings* yang *frozen* untuk mencegah modifikasi `in-place` dan mengurangi mutasi memori.
- **Streaming Response:** Array response konvensional digantikan atau dilengkapi dengan objek respons yang merespons metode `#each` (dapat memanggil blok berulang kali untuk *chunked transfer*) atau antarmuka *fiber-based streaming body* (`#call(stream)`), memungkinkan I/O non-blocking nyata di atas server modern.

### 3.3 MRI Memory Mechanics: jemalloc & Compacting GC

Alokator default Linux (`glibc malloc`) mengalokasikan arena memori per-thread yang menyebabkan fragmentasi parah pada aplikasi multi-threaded Ruby, sehingga OS tidak pernah menerima kembali memori yang telah di-*free*. 

Implementasi kelas enterprise mewajibkan:
1. **`jemalloc`:** Menggantikan malloc glibc. Menggunakan alokasi *slab-based memory*, secara drastis mengurangi fragmentasi memori, serta mendukung purging halaman memori yang tidak terpakai kembali ke OS.
2. **Ruby Compacting GC (`GC.compact`):** Merapikan fragmentasi objek pada Ruby Heap. Ketika dipanggil tepat sebelum Puma melakukan `fork` worker di `before_fork`, `GC.compact` memaksimalkan halaman memori CoW yang bersih (*clean pages*), mencegah *dirtying* halaman memori saat worker berjalan.

---

## 4. Why & What

| Dimensi | Pendekatan Monolit Naif / Tradisional | Arsitektur Enterprise Produksi |
| :--- | :--- | :--- |
| **Model Eksekusi** | Single Puma process, alokasi thread statis tanpa tuning GVL. | Puma Clustered Mode, penyesuaian rasio CPU Cores vs I/O-bound threads, Worker Killer terukur. |
| **Alokasi Memori** | Mengandalkan sistem `glibc malloc` standar; memori terus naik (leaking illusion). | Injeksi `jemalloc`, pre-fork compilation, memory compaction (`GC.compact`), worker telemetry. |
| **Deployment** | Hard restart (`kill -9`, start ulang). Terjadi *dropped connections* dan *HTTP 502 Bad Gateway*. | Socket Activation / Phased Restarts (`SIGUSR2`, `SIGUSR1`) dengan *connection draining* dan buffer proxy. |
| **Resource Pool** | Ukuran database pool bernilai statis sembarang, mengakibatkan *ActiveRecord::ConnectionTimeoutError*. | Perhitungan presisi formula DB Pool: $\text{Workers} \times \text{Threads} + \text{Margin Overhead Sistem}$. |
| **I/O Handling** | Synchronous blocking Rack middleware; alokasi heap masif per request. | Asynchronous / streaming Rack 3 body, non-blocking telemetry middleware, thread-safe memory buffers. |

---

## 5. How (Workflow Detail)

Alur eksekusi request pada level kernel dan runtime Ruby:

```
[Client] 
   │ 1. TLS Handshake & HTTP Request
   ▼
[Envoy / Nginx]
   │ 2. Proxying via Stream/Http2 to Local Unix Socket
   ▼
[Puma Master Socket] (Shared file descriptor)
   │ 3. Dispatched via Kernel Epoll
   ▼
[Puma Worker Reactor]
   │ 4. Read HTTP chunks into buffer (Slowloris protection)
   ▼
[Puma Worker Thread Pool]
   │ 5. Acquire Worker Thread from Pool
   │ 6. Construct rack `env` Hash (frozen keys)
   ▼
[Enterprise Rack Middleware Stack]
   │ 7. Request Tracing & Correlation ID Injection
   │ 8. Rate Limiting & Circuit Breaking
   │ 9. Memory Profiling / Allocation Guard
   ▼
[Business Logic / Rails Action]
   │ 10. Execute Query (via ActiveRecord Connection Pool)
   │ 11. Yield Response Stream / Array
   ▼
[Puma Worker Socket Writer]
   │ 12. Flush HTTP/1.1 or HTTP/2 frames to socket
   ▼
[Reverse Proxy] ──> [Client]
```

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem ini seperti **Pusat Logistik Kargo Bandara**:
- **Reverse Proxy (Nginx/Envoy):** Pos gerbang utama bandara yang memverifikasi izin masuk truk dan mengarahkan muatan.
- **Puma Master:** Kepala operasional stasiun kargo yang membagi area hanggar (*worker processes*) dan memantau kesehatan seluruh staf.
- **Puma Reactor:** Meja registrasi kargo yang menahan kiriman barang sampai seluruh dokumen (*full request payload*) lengkap. Kurir pengantar barang lambat tidak diizinkan masuk dan memblokir meja sortir.
- **Puma Worker Threads:** Regu pekerja kargo yang mengambil muatan lengkap, memproses isinya sesuai prosedur operasional standar (*Rack Middleware Chain*), lalu memuat hasil sortir ke truk pengirim.

```
       ================ KERNEL / OS NETWORK LAYER ================
                              [ eth0: TCP 443 ]
                                     │
       ================= APPLICATION SERVER HOST =================
                                     │
                             ┌───────▼───────┐
                             │ Envoy / Nginx │
                             └───────┬───────┘
                                     │ (Unix Domain Socket: /tmp/puma.sock)
            ┌────────────────────────┴────────────────────────┐
            │               Puma Master (PID 1001)            │
            │          Signals: SIGTERM, SIGUSR2, SIGCHLD      │
            └───────────┬─────────────────────────┬───────────┘
     CoW Memory Fork    │                         │ CoW Memory Fork
     ┌──────────────────▼──────┐           ┌──────▼──────────────────┐
     │ Puma Worker 0 (PID 1002)│           │ Puma Worker 1 (PID 1003)│
     │                         │           │                         │
     │ ┌─────────────────────┐ │           │ ┌─────────────────────┐ │
     │ │ Reactor (nio4r loop)│ │           │ │ Reactor (nio4r loop)│ │
     │ └──────────┬──────────┘ │           │ └──────────┬──────────┘ │
     │            │ Queue      │           │            │ Queue      │
     │   ┌────────┴────────┐   │           │   ┌────────┴────────┐   │
     │   │ Worker Threads  │   │           │   │ Worker Threads  │   │
     │   │ [T1]  [T2]  [T3]│   │           │   │ [T1]  [T2]  [T3]│   │
     │   └───┬─────┬─────┬─┘   │           │   └───┬─────┬─────┬─┘   │
     └───────┼─────┼─────┼─────┘           └───────┼─────┼─────┼─────┘
             │     │     │                         │     │     │
     ========▼=====▼=====▼=========================▼=====▼=====▼==========
     RACK MIDDLEWARE PIPELINE (In-Memory Processing)
       │ -> TraceContext Propagation Middleware
       │ -> CircuitBreaker & Adaptive Concurrency Limiter
       │ -> Application Execution Core (Rails / Hanami / Roda)
       ▼ <- Return Streaming Body / Enumerator
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Rack 3 Low-Allocation Streaming App

Contoh implementasi spesifikasi antarmuka Rack 3 streaming body tanpa framework besar.

```ruby
# config.ru
# frozen_string_literal: true

class StreamingApp
  # Kontrak antarmuka Rack 3: call(env) -> [status, headers, body]
  def call(env)
    case env['PATH_INFO']
    when '/healthz'
      [200, { 'content-type' => 'text/plain' }, ['OK']]
    when '/stream'
      headers = {
        'content-type' => 'application/x-ndjson',
        'cache-control' => 'no-cache',
        'x-accel-buffering' => 'no' # Mencegah buffering di Nginx
      }

      # Streaming body yang merespons metode #each (atau #call di Rack 3 stream)
      body = Enumerator.new do |stream|
        10.times do |i|
          stream << %({"event_id": #{i}, "timestamp": "#{Time.now.iso8601}"}\n)
          sleep 0.1 # Simulasi I/O delay
        end
      end

      [200, headers, body]
    else
      [404, { 'content-type' => 'text/plain' }, ['Not Found']]
    end
  end
end

run StreamingApp.new
```

### 7.2 Practical Example: Enterprise Production Configuration & Telemetry Middleware

#### 1. Konfigurasi Puma Skala Produksi (`config/puma.rb`)

```ruby
# config/puma.rb
# frozen_string_literal: true

# 1. Definisi Konkurensi & Arsitektur Mesin
# Hitung worker berdasarkan core CPU fisik (bukan hyperthreaded) untuk CPU-bound load,
# atau scaling rasio 1.5x core jika didominasi I/O latency.
workers Integer(ENV.fetch('WEB_CONCURRENCY') { 4 })

# Puma thread pool per-worker. Ruby MRI memiliki GVL, sehingga rentang ideal 
# untuk beban mixed I/O & database queries berada di antara 3 s.d. 8 threads.
threads_count = Integer(ENV.fetch('RAILS_MAX_THREADS') { 5 })
threads threads_count, threads_count

# 2. Binding Socket & Environment
environment ENV.fetch('RAILS_ENV') { 'production' }

# Bind Unix Domain Socket untuk performa optimal di belakang Nginx/Envoy lokal
# Fallback ke TCP jika running di container orchestrator (e.g., Kubernetes)
if ENV['PUMA_SOCKET_BIND'].present?
  bind "unix://#{ENV['PUMA_SOCKET_BIND']}?umask=0111&backlog=1024"
else
  port Integer(ENV.fetch('PORT') { 3000 })
end

# 3. Manajemen Resource & Pre-fork Optimization
# Memuat seluruh codebase ke Master Process sebelum melakukan fork.
# Menghemat RAM secara signifikan melalui OS Copy-on-Write (CoW).
preload_app!

# Batas waktu eksekusi worker thread sebelum dianggap frozen/hung (watchdog)
worker_timeout 30

# Graceful shutdown timeout (diberikan ke worker untuk menyelesaikan in-flight request)
shutdown_timeout 15

# 4. Lifecycle Hooks & CoW GC Optimization
before_fork do
  # Putuskan koneksi database yang ada di master process sebelum forking
  # untuk mencegah worker berbagi connection socket yang sama.
  ActiveRecord::Base.connection_pool.disconnect! if defined?(ActiveRecord::Base)

  # Optimasi alokasi CoW: Lakukan kompresi heap memory master process
  # Mengeliminasi fragmentasi halaman sebelum worker memicu CoW page dirtying.
  if GC.respond_to?(:compact)
    GC.start(full_mark: true, immediate_sweep: true)
    GC.compact
  end

  PumaWorkerMetrics.init_master_metrics if defined?(PumaWorkerMetrics)
end

on_worker_boot do
  # Inisialisasi ulang koneksi database spesifik untuk tiap worker
  ActiveSupport.on_load(:active_record) do
    ActiveRecord::Base.establish_connection
  end

  # Setup hook metrik worker (PID, thread usage, dll)
  PumaWorkerMetrics.start_telemetry_thread if defined?(PumaWorkerMetrics)
end

on_worker_shutdown do
  # Bersihkan resource eksternal ketika sinyal terminasi diterima worker
  ActiveRecord::Base.connection_pool.disconnect! if defined?(ActiveRecord::Base)
end
```

#### 2. Enterprise Telemetry & Circuit-Breaking Middleware (`lib/middleware/enterprise_gateway.rb`)

```ruby
# lib/middleware/enterprise_gateway.rb
# frozen_string_literal: true

require 'securerandom'
require 'concurrent-ruby'

module Middleware
  class EnterpriseGateway
    CORRELATION_ID_HEADER = 'HTTP_X_CORRELATION_ID'
    OUT_CORRELATION_HEADER = 'x-correlation-id'
    MAX_PENDING_QUEUE = 250

    # In-memory adaptive limiter menggunakan Concurrent::AtomicFixnum
    @in_flight_requests = Concurrent::AtomicFixnum.new(0)

    class << self
      attr_reader :in_flight_requests
    end

    def initialize(app, options = {})
      @app = app
      @max_concurrency = options.fetch(:max_concurrency, 50)
      @circuit_open = Concurrent::AtomicBoolean.new(false)
    end

    def call(env)
      # 1. Edge Ingress Protection: Circuit Breaker / Load Shedding
      if current_load_saturated?
        return [
          503,
          { 
            'content-type' => 'application/json',
            'retry-after' => '5' 
          },
          [%({"error": "Service Unavailable: Worker Load Shedding", "status": 503}\n)]
        ]
      end

      # 2. Context Injection: Distributed Tracing W3C / Correlation ID
      correlation_id = env[CORRELATION_ID_HEADER] || SecureRandom.uuid
      env['action_dispatch.correlation_id'] = correlation_id

      # Track In-flight Request Count
      self.class.in_flight_requests.increment
      start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)

      begin
        # 3. Pipeline Execution
        status, headers, body = @app.call(env)

        # 4. Modifikasi Headers dengan Mutasi Minimal
        headers[OUT_CORRELATION_HEADER] = correlation_id
        
        # Mengembalikan response tuple sesuai kontrak Rack 3
        [status, headers, body]
      ensure
        self.class.in_flight_requests.decrement
        elapsed_time = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
        
        # Telemetry logging sederhana tanpa membebani alokasi
        if elapsed_time > 1.5
          $stderr.puts("[ALERT] High Latency Request: #{env['REQUEST_METHOD']} #{env['PATH_INFO']} took #{elapsed_time.round(4)}s")
        end
      end
    end

    private

    def current_load_saturated?
      self.class.in_flight_requests.value >= @max_concurrency
    end
  end
end
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Gateway Sistem Pembayaran Fintech (15.000 Req/Sec Bursts)

**Latar Belakang:**  
Sebuah platform fintech mengalami *spikes* transaksi saat kampanye kilat (*flash-sale*). Sistem dijalankan di cluster Kubernetes dengan 40 Pod Puma (masing-masing 4 workers, 16 threads). 

**Masalah Kritis yang Terjadi di Produksi:**
1. **Connection Pool Exhaustion:** Terjadi error masif: `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.
2. **Memory Bloat & OOM Kills:** Tiap Pod mengalami lonjakan konsumsi RAM dari 400MB ke 2.5GB dalam waktu 20 menit, memicu *Kubernetes OOMKilled* secara bergantian, menyebabkan *cascading failures*.
3. **Dropped Requests saat Rolling Restart:** Klien menerima ratusan error `502 Bad Gateway` saat deployment versi baru berjalan.

**Investigasi Akar Masalah (*Root Cause Analysis*):**
- **DB Pool Undersized:** Total thread Puma per Pod = $4 \times 16 = 64\text{ threads}$. Ukuran `pool` database di `database.yml` hanya di-set ke default `5`. Akibatnya, 64 thread berebut 5 koneksi database.
- **glibc Fragmentation:** Ruby mengalokasikan dan mendealokasikan jutaan representasi JSON string. Alokator default Linux (`glibc`) memecah memori ke arena terpisah dan tidak pernah mengembalikannya ke OS kernel.
- **Sinyal SIGTERM Tidak Ditangani:** Kubelet mengirim `SIGTERM`, lalu Puma langsung mematikan socket tanpa menunggu penyelesaian in-flight transaksi pembayaran yang sedang berkomunikasi dengan bank partner.

**Solusi & Remediasi Arsitektur:**

1. **Sinkronisasi Kapasitas Database Pool:**
   Formula dinamis diterapkan:
   $$\text{ActiveRecord Pool Size} \ge \text{Puma Max Threads} + \text{Background Threads Margin (e.g., 2)}$$
   Nilai `RAILS_MAX_THREADS` diturunkan dari 16 ke 5 (mengurangi GVL contention), dan DB pool diatur ke 7.

2. **Injeksi `jemalloc`:**
   Menambahkan environment variable pada Docker image:
   ```dockerfile
   ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2
   ENV MALLOC_CONF="dirty_decay_ms:1000,muzzy_decay_ms:1000,narenas:2"
   ```
   *Hasil:* Footprint memori stabil pada 420MB, flat selama 48 jam berturut-turut di bawah beban penuh tanpa OOMKilled.

3. **Graceful Drain Lifecycle pada Kubernetes:**
   Menambahkan `preStop` hook pada pod spec dan konfigurasi Puma shutdown timeout:
   ```yaml
   lifecycle:
     preStop:
       exec:
         command: ["/bin/sh", "-c", "sleep 10"] # Biarkan Ingress mencabut Pod dari endpoint routing
   ```
   Puma diatur dengan `shutdown_timeout 15`. Error `502 Bad Gateway` turun menjadi 0% (*zero dropped connections*).

---

## 9. Trade-offs

| Parameter | Puma Clustered (Worker + Threads) | Falcon / Async (Fiber-Based) | Standalone Single-Process Multi-Thread |
| :--- | :--- | :--- | :--- |
| **Model Concurrency** | Multi-process + Native POSIX Threads | Non-blocking Event Loop + Fibers | Single-process + POSIX Threads |
| **Pemanfaatan Core CPU** | Optimal (1 worker per CPU core, bypass GVL). | Membutuhkan multi-process clustering untuk memanfaatkan multi-core. | Buruk (dibatasi oleh GVL satu proses Ruby). |
| **Footprint Memori** | Menengah-Tinggi (Tergantung CoW efficiency & jumlah worker). | Sangat Rendah (Ribuan fiber dalam 1 proses tunggal). | Paling Rendah (Hanya 1 proses dan thread pool). |
| **Kompatibilitas Gem** | Sangat Tinggi (Mendukung hampir seluruh ekosistem gem Ruby). | Membutuhkan ekosistem I/O non-blocking (`async-*`); gem C-ext pemblokir dapat merusak event loop. | Sangat Tinggi. |
| **Handling Latency Ekstrem** | Dapat mengalami *Thread Starvation* jika pool habis terblokir HTTP eksternal. | Unggul dalam penanganan jutaan koneksi idle/slow WebSockets/SSE. | Cepat mengalami starvation jika terdapat eksekusi I/O lambat. |
| **Kompleksitas Operasional**| Standar industri, tooling APM matang. | Memerlukan pemahaman fiber scheduler dan debugging non-trivial. | Paling sederhana, minim debugging konkurensi antar-proses. |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Thread Starvation Akibat Misalignment Ukuran DB Connection Pool
* **Gejala:** Muncul error `ActiveRecord::ConnectionTimeoutError` beruntun saat request burst, namun utilisasi CPU host sangat rendah (<20%).
* **Penyebab:** Konfigurasi `pool` di `database.yml` lebih kecil dibandingkan `threads` maksimum pada `puma.rb`.
* **Solusi:**
  ```ruby
  # config/database.yml
  production:
    pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 }.to_i + 2 %>
  ```

### 10.2 State Mutation / Race Condition di Middleware
* **Gejala:** Nilai request data tercampur antar user (User A menerima akun info User B).
* **Penyebab:** Menyimpan state transaksi ke dalam *instance variable* pada objek Middleware (Middleware di-instansiasi *sekali* di Rack dan di-share ke semua thread).
* **Anti-Pattern:**
  ```ruby
  # FATAL: Tidak Thread-Safe!
  class BadMiddleware
    def initialize(app) = @app = app
    def call(env)
      @user_id = env['HTTP_X_USER_ID'] # DATA RACE! Tertimpa thread lain!
      @app.call(env)
    end
  end
  ```
* **Solusi:** Simpan state hanya di dalam variabel lokal metode `call` atau lekatkan ke dalam `env`:
  ```ruby
  class SafeMiddleware
    def initialize(app) = @app = app
    def call(env)
      user_id = env['HTTP_X_USER_ID'] # Thread-safe (Lokal stack frame)
      env['app.user_id'] = user_id
      @app.call(env)
    end
  end
  ```

### 10.3 Ghost Socket & Thundering Herd
* **Gejala:** Latensi loncat tinggi sesaat setelah worker baru di-spawn, atau master Puma tidak menerima request baru setelah deploy.
* **Troubleshooting:**
  1. Periksa listen backlog queue melalui `ss -lnt 'sport = :3000'`. Jika `Send-Q` penuh, perbesar backlog TCP:
     ```ruby
     # config/puma.rb
     bind 'tcp://0.0.0.0:3000?backlog=2048'
     ```
  2. Naikkan `somaxconn` pada kernel host:
     ```bash
     sysctl -w net.core.somaxconn=4096
     ```

---

## 11. Best Practices (Production Checklist)

- [ ] **Alokator Memori:** Wajib mengaktifkan `jemalloc` (`LD_PRELOAD`) pada container produksi untuk mitigasi fragmentasi heap glibc.
- [ ] **Preload Application:** Selalu nyalakan `preload_app!` pada `config/puma.rb` untuk memaksimalkan Copy-on-Write (CoW).
- [ ] **Koneksi Database:** Pastikan `disconnect!` dipanggil di `before_fork` dan `establish_connection` dipanggil pada `on_worker_boot`.
- [ ] **Thread-Safety Audit:** Pastikan middleware tidak menyimpan state berbasis instance variables (`@variable`).
- [ ] **Worker Ratio:** Konfigurasi workers sebanyak core CPU fisik container (`nproc`), dan batasi thread pool maksimum antara 3 s.d. 5 per worker untuk meminimalkan GVL context-switching cost.
- [ ] **Reverse Proxy Buffering:** Selalu letakkan reverse proxy (Nginx, Envoy, ALB) di depan Puma untuk memfilter *slow clients* dan menangani negosiasi TLS/HTTP2.
- [ ] **Graceful Termination Timing:** Pastikan Kubernetes pod `terminationGracePeriodSeconds` (misal 30 detik) lebih lama dari `sleep` pada `preStop` hook (misal 5 detik) + `shutdown_timeout` Puma (misal 15 detik).
- [ ] **Memory Compaction:** Lakukan `GC.compact` secara eksplisit pada block `before_fork` di Puma master.

---

## 12. Hands-on Practice

Buatlah direktori praktikum di `hands-on/m02/` untuk menguji performa Puma cluster, jemalloc, dan integrasi streaming middleware.

### Langkah 1: Buat Struktur File
Jalankan di terminal Anda:
```bash
mkdir -p hands-on/m02/lib/middleware
cd hands-on/m02
```

### Langkah 2: Buat File `Gemfile`
```ruby
# hands-on/m02/Gemfile
source 'https://rubygems.org'

gem 'puma', '~> 6.4'
gem 'rack', '~> 3.0'
gem 'concurrent-ruby', '~> 1.2'
```
Instal dependensi:
```bash
bundle install
```

### Langkah 3: Implementasikan Rack Middleware & Entrypoint
Simpan kode berikut sebagai `hands-on/m02/config.ru`:
```ruby
# hands-on/m02/config.ru
# frozen_string_literal: true

require_relative 'lib/middleware/metrics_middleware'

use Middleware::MetricsMiddleware

run lambda { |env|
  case env['PATH_INFO']
  when '/'
    [200, { 'content-type' => 'application/json' }, [%({"message": "Enterprise Ruby Active", "pid": #{Process.pid}}\n)]]
  when '/work'
    # Simulasi CPU-bound load dengan alokasi objek
    data = 10_000.times.map { SecureRandom.hex(64) }
    [200, { 'content-type' => 'text/plain' }, ["Processed #{data.size} items\n"]]
  else
    [404, { 'content-type' => 'text/plain' }, ["Not Found\n"]]
  end
}
```

Simpan file middleware di `hands-on/m02/lib/middleware/metrics_middleware.rb`:
```ruby
# hands-on/m02/lib/middleware/metrics_middleware.rb
# frozen_string_literal: true

module Middleware
  class MetricsMiddleware
    def initialize(app)
      @app = app
    end

    def call(env)
      start = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      status, headers, body = @app.call(env)
      duration = (Process.clock_gettime(Process::CLOCK_MONOTONIC) - start) * 1000

      headers['x-runtime-ms'] = sprintf('%.2f', duration)
      headers['x-worker-pid'] = Process.pid.to_s

      [status, headers, body]
    end
  end
end
```

### Langkah 4: Buat Konfigurasi Server Produksi
Simpan kode berikut sebagai `hands-on/m02/puma.rb`:
```ruby
# hands-on/m02/puma.rb
# frozen_string_literal: true

workers 2
threads 4, 4

port ENV.fetch('PORT') { 8080 }
environment 'production'

preload_app!

before_fork do
  puts "[Master #{Process.pid}] Pre-fork hook running. Compacting heap..."
  GC.compact if GC.respond_to?(:compact)
end

on_worker_boot do
  puts "[Worker #{Process.pid}] Booted and ready to accept connections."
end
```

### Langkah 5: Eksekusi dan Verifikasi Load Testing
1. Jalankan Puma server menggunakan bundle exec:
   ```bash
   bundle exec puma -C puma.rb config.ru
   ```
2. Buka terminal baru dan lakukan load testing menggunakan curl atau ApacheBench (`ab`):
   ```bash
   # Verifikasi respon dan runtime headers
   curl -i http://localhost:8080/
   curl -i http://localhost:8080/work

   # Lakukan benchmark dengan konkurensi tinggi
   ab -n 1000 -c 50 http://localhost:8080/work
   ```
3. Amati log di terminal Puma: Verifikasi bahwa proses worker yang melayani request bergantian sesuai PID masing-masing secara konkuren.

---

## 13. Exercises

### Level Easy
Modifikasi `hands-on/m02/lib/middleware/metrics_middleware.rb` untuk menambahkan header response `x-memory-usage-kb` yang membaca memori RSS proses worker saat ini secara aman menggunakan kelas `Process.getrlimit` atau pembacaan file pseudo `/proc/self/statm` (pada Linux).

### Level Medium
Bangun middleware bernama `AdaptiveConcurrencyLimiter`. Middleware ini harus menghitung latensi *moving average* dari 100 request terakhir. Jika *moving average latency* melebihi batas ambang (misal > 500ms), tolak request baru yang masuk dengan status code HTTP `429 Too Many Requests` hingga rata-rata latensi kembali normal.

### Level Hard
Buat script automasi deployment zero-downtime berbasis Bash/Ruby yang menguji *graceful phased restart* Puma:
1. Mulai server Puma dalam clustered mode binding ke Unix Domain Socket.
2. Jalankan loop pengiriman request tanpa henti (*infinite curl loop*) selama 30 detik.
3. Di tengah-tengah loop request, kirimkan sinyal POSIX `SIGUSR2` diikuti `SIGUSR1` ke Master PID.
4. Validasi bahwa tidak ada satu pun dari ribuan request yang mengembalikan status code selain `200 OK` (0 request dropped / no connection reset).

---

## 14. Challenge

**Studi Kasus: Ultra High-Throughput Audit Telemetry Engine**

Anda ditugaskan merancang *edge ingestion service* berbasis Ruby untuk menerima metrik sensor IoT dengan throughput minimum **30.000 request per detik** pada satu instans mesin 8 Core CPU / 16GB RAM.

**Batasan & Persyaratan:**
1. Maksimum pemakaian RAM aplikasi tidak boleh melampaui **1.2 GB** dalam kondisi apapun (anti-bloat).
2. Request payload adalah JSON berukuran bervariasi (1KB - 10KB) yang harus divalidasi skemanya dan diteruskan ke cluster Kafka / Socket buffer biner.
3. Anda tidak diperkenankan menggunakan framework Rails atau Sinatra secara penuh (gunakan arsitektur berbasis Rack murni atau Falcon/Async).
4. Tidak boleh terjadi *blocking GVL contention* selama proses enkripsi/hashing payload.

**Deliverables yang Diminta:**
1. Desain arsitektur lengkap: Pemilihan Server (Puma vs Falcon), Event model, alokasi memori, dan tuning OS Kernel.
2. Implementasi middleware validasi berkinerja tinggi dengan alokasi heap mendekati nol (*zero-allocation / frozen string buffer*).
3. Rencana penanganan backpressure ketika broker Kafka mengalami *slowdown*.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda / Singkat)
1. **Apa tujuan utama penggunaan `preload_app!` pada file konfigurasi Puma?**
   - A. Menghubungkan database secara otomatis ke seluruh proses anak.
   - B. Memuat kode aplikasi ke master process sebelum `fork()` untuk memanfaatkan Copy-on-Write OS.
   - C. Memastikan thread pool Puma berjalan pada level maksimum sejak inisialisasi.
   - D. Mencegah Rack middleware dieksekusi secara asinkron.
   *(Jawaban: B)*

2. **Mengapa menyimpan state request pada instance variable (`@request_data`) di dalam Rack Middleware dianggap fatal di environment produksi?**
   - A. Karena instance variable tidak dapat dibaca oleh Garbage Collector.
   - B. Karena middleware merupakan singleton/long-lived object yang diakses bersamaan oleh banyak worker thread, memicu race condition.
   - C. Karena Puma secara otomatis menghapus instance variable setelah 10ms.
   - D. Karena Ruby GVL akan melempar exception `FrozenError`.
   *(Jawaban: B)*

3. **Format respons apa yang diwajibkan oleh spesifikasi Rack 3 untuk antarmuka kembalian metode `#call`?**
   - A. Object bertipe `Rack::Response`.
   - B. Array 3 elemen: `[status (Integer), headers (Hash), body (Enumerable/#each/#call)]`.
   - C. JSON string yang valid.
   - D. Stream descriptor `IO`.
   *(Jawaban: B)*

4. **Sinyal POSIX apa yang dikirimkan ke Puma Master untuk memicu Phased Restart pada seluruh worker tanpa memutus listener socket?**
   - A. `SIGKILL`
   - B. `SIGUSR1`
   - C. `SIGUSR2`
   - D. `SIGTERM`
   *(Jawaban: C)*

5. **Apa fungsi dari komponen Reactor pada Puma web server?**
   - A. Menjalankan query SQL secara paralel.
   - B. Mengelola alokasi Garbage Collector secara berkala.
   - C. Menampung dan membuffer koneksi lambat (slow clients) menggunakan event-loop sebelum diserahkan ke thread pool.
   - D. Melakukan enkripsi otomatis pada payload HTTP/2.
   *(Jawaban: C)*

---

### Bagian 2: Intermediate (Analisis Logika)
1. **Bagaimana formula matematis standar industri untuk mengonfigurasi ukuran connection pool database ActiveRecord pada arsitektur Puma Clustered?**  
   *Jawaban:* `ActiveRecord Pool Size >= Puma Max Threads (per worker) + Thread Cadangan/Background System (1-2)`. Pool database berlaku *per-process/worker*, bukan agregat seluruh cluster master.

2. **Mengapa alokator default `glibc malloc` sering kali menyebabkan memori aplikasi Ruby tampak mengalami kebocoran (*memory leak*) pada aplikasi multi-threaded?**  
   *Jawaban:* Glibc mengalokasikan arena memori per-thread. Saat thread Ruby banyak mengalokasikan dan mendealokasikan objek, terjadi fragmentasi internal. Halaman memori pada arena tersebut tidak pernah dikembalikan (*unmapped*) ke kernel OS, sehingga Resident Set Size (RSS) proses terus membesar. Solusinya adalah menggunakan alokator `jemalloc`.

3. **Kapan Anda memilih arsitektur berbasis Fiber (misal: Falcon) dibandingkan model Thread-based Puma?**  
   *Jawaban:* Ketika aplikasi didominasi oleh I/O latency tinggi dengan ribuan koneksi konkuren terbuka secara persisten (seperti WebSockets, SSE, Proxy Ingestion) di mana model thread Puma akan mengalami thread starvation atau kehabisan memori akibat alokasi stack per-native-thread.

4. **Apa implikasi pemanggilan `ActiveRecord::Base.establish_connection` di dalam blok `before_fork` pada konfigurasi Puma?**  
   *Jawaban:* Kesalahan fatal arsitektur. File descriptor koneksi database soket TCP/Unix akan terduplikasi ke seluruh worker process anak hasil forking. Hal ini menyebabkan worker saling berebut membaca/menulis paket jaringan pada soket DB yang sama (*socket corruption / protocol desync*).

5. **Apa fungsi pemanggilan `GC.compact` sebelum Puma melakukan forking worker?**  
   *Jawaban:* `GC.compact` memindahkan objek-objek hidup di heap memori Ruby agar berkumpul rapat di halaman-halaman awal. Ini meminimalkan referensi objek yang tersebar dan memaksimalkan *shared memory* via Copy-on-Write (CoW), sehingga worker anak tidak mengotori (*dirtying*) halaman memori saat eksekusi dimulai.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: Diagnosa Latensi Berulang & GVL Contention
*Kasus:* Pada grafik dashboard observabilitas (DataDog/Prometheus), aplikasi Rails Anda menunjukkan latensi P99 melesat ke 4000ms pada jam sibuk, namun metrik Database Query Time rata-rata hanya 15ms dan utilisasi CPU server adalah 100% pada semua core. Setelah dicek, jumlah Puma thread di-set ke 32 thread per worker dengan 2 worker pada VM 2-Core.
* **Analisis Masalah:** Thread count (32) jauh melampaui kemampuan core fisik (2 core). Akibat Ruby MRI memiliki GVL (*Global VM Lock*), thread-thread tersebut saling berebut waktu eksekusi CPU (*context-switching storm* & *GVL lock contention*). Waktu terbuang sia-sia hanya untuk mengantre giliran eksekusi Ruby VM.
* **Tindakan Remediasi:**
  1. Turunkan jumlah worker thread per proses secara drastis ke angka ideal: 3 s.d. 5 thread.
  2. Naikkan jumlah worker proses menjadi 2 (sesuai jumlah core fisik: 1 worker per core).
  3. Skalakan kapasitas komputasi secara horizontal (*horizontal pod autoscaling*) jika traffic melampaui kapasitas 2 worker.

#### Skenario 2: Graceful Rolling Deploy Connection Reset
*Kasus:* Setiap kali tim DevOps melakukan rilis aplikasi pada cluster Kubernetes, klien API pihak ketiga mengirimkan keluhan bahwa sekitar 0.5% transaksi mereka gagal dengan error `ECONNRESET` atau `HTTP 502 Bad Gateway`.
* **Analisis Masalah:** Kubelet mengirim sinyal `SIGTERM` ke container Puma dan secara paralel memperbarui routing iptables/kube-proxy. Puma langsung memulai proses shutdown, sementara iptables masih merutekan paket baru ke Pod tersebut, atau transaksi aktif terputus sebelum Puma `shutdown_timeout` selesai mengalirkan response.
* **Tindakan Remediasi:**
  1. Pasang `preStop` hook dengan perintah `sleep 5` pada Pod spec untuk memberi waktu bagi Ingress Controller menghapus IP pod dari upstream pool sebelum Puma menerima sinyal.
  2. Atur Puma `shutdown_timeout` ke durasi yang rasional (misal: 15 detik).
  3. Konfigurasi `STOPSIGNAL` pada Dockerfile menjadi `SIGTERM`.

#### Skenario 3: Ledakan Memori Akibat Streaming Tanpa Backpressure
*Kasus:* Sebuah endpoint `/export` menghasilkan file CSV besar (ratusan megabyte) dari database. Saat 5 user menjalankan export bersamaan, penggunaan RAM server melonjak drastis hingga proses Puma di-kill oleh sistem OS (`Out of memory: Kill process`).
* **Analisis Masalah:** Endpoint membaca seluruh baris tabel database ke dalam Ruby Array lalu merender seluruh string CSV ke dalam memori sebelum mengirimkannya ke Rack response.
* **Tindakan Remediasi:**
  1. Ubah arsitektur pengambilan data menggunakan `find_each` atau database cursor (ActiveRecord `find_each(batch_size: 1000)`).
  2. Gunakan antarmuka Rack Streaming response (`Enumerator.new`) agar potongan baris CSV langsung di-*yield* ke Puma socket writer secara bertahap tanpa pernah mengumpulkan seluruh file CSV di dalam Ruby heap.

---

## 16. Summary

1. **Arsitektur Hybrid Puma:** Puma mengombinasikan keunggulan *multi-process* (untuk mendistribusikan beban ke seluruh core CPU dan memotong limitasi GVL) dengan *multi-threading* (untuk efisiensi penanganan latency I/O database dan jaringan).
2. **Reactor Pattern:** Penggunaan `nio4r` pada Reactor Puma mengisolasi proses worker dari ancaman klien lambat (*slow clients*), memastikan thread berharga hanya dialokasikan untuk mengeksekusi request yang siap diproses.
3. **Optimasi Tingkat Rendah:** Pemanfaatan `jemalloc` dan `GC.compact` pada fase `before_fork` merupakan strategi wajib di skala enterprise guna mengendalikan fragmentasi heap memori OS dan menjaga integritas efisiensi *Copy-on-Write*.
4. **Resiliensi Ekosistem Produksi:** Stabilitas sistem berskala masif tidak hanya bergantung pada kode aplikasi, melainkan sinkronisasi presisi antara *Linux Kernel Backlog* $\rightarrow$ *Proxy Ingress Buffer* $\rightarrow$ *Puma Socket Listener* $\rightarrow$ *Rack Pipeline* $\rightarrow$ *Database Connection Pool*.