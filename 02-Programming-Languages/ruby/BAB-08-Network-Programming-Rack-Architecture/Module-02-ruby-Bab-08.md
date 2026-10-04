# BAB 08: Network Programming & Rack Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** arsitektur I/O non-blocking di Ruby runtime (MRI), termasuk interaksi antara Fiber Scheduler, `IO.select`, dan manipulasi File Descriptor OS level.
- **Mengimplementasikan** protokol streaming data real-time menggunakan spesifikasi Rack 3 (`rack.hijack` dan Streaming Body) tanpa memblokir thread pool.
- **Mendesain** arsitektur web server konkurensi tinggi berbasis Puma Cluster Mode dengan kalkulasi metrik *worker-to-thread ratio* yang presisi terhadap CPU Core dan memori.
- **Mendiagnosis** dan memitigasi kegagalan jaringan level rendah, seperti *socket exhaustion*, *file descriptor leaks*, *head-of-line blocking*, dan *backpressure saturation*.
- **Membangun** pipeline middleware Rack kelas enterprise dengan fault-tolerance, connection draining, dan metrik telemetri berbasis Prometheus.

---

### 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- Dasar-dasar socket programming Ruby (`TCPSocket`, `TCPServer`, `Socket::Constants`).
- Konsep dasar spesifikasi Rack interface (`call(env)` mengembalikan `[status, headers, body]`).
- Model konkurensi Ruby: Thread, Fiber, Ractor, dan Global VM Lock (GVL / GIL).
- Pengetahuan protokol HTTP/1.1 (Chunked Transfer Encoding, Keep-Alive, HTTP Pipelining).

---

### 3. Concept & Internal Architecture

#### A. Ruby I/O Engine & Non-Blocking Primitives
Ruby MRI (CRuby) membungkus system calls sistem operasi (`epoll` di Linux, `kqueue` di BSD/macOS) melalui abstraksi POSIX. Pada mode sinkron/blocking, operasi socket (`read`, `write`, `accept`) akan melepaskan GVL agar thread Ruby lain dapat dieksekusi, namun thread pengirim tetap tertahan (blocked) di level kernel kernel wait queue.

```
+-------------------------------------------------------------+
| Ruby Virtual Machine (MRI)                                 |
|                                                             |
|  [ Fiber 1 ]    [ Fiber 2 ]   ...   [ Thread Pool Worker ]  |
|       \              /                        |             |
|    +--------------------+                     |             |
|    |  Fiber Scheduler   |                     |             |
|    +--------------------+                     |             |
|              | (read_nonblock / wait_readable)|             |
+--------------|--------------------------------|-------------+
               v                                v
+-------------------------------------------------------------+
| CRuby I/O Layer (io.c)                                      |
|    - IO#wait_readable / IO#wait_writable                    |
|    - rb_thread_wait_fd() / GVL Release Check                |
+-------------------------------------------------------------+
               |                                |
               v (epoll_ctl / kqueue EV_SET)    v (read / write)
+-------------------------------------------------------------+
| Linux / Unix Kernel                                         |
|    - Socket Receive/Send Buffers                            |
|    - epoll / kqueue Event Loop Engine                       |
+-------------------------------------------------------------+
```

Pada mode non-blocking (`read_nonblock`, `write_nonblock` dengan parameter `exception: false`), Ruby menginstruksikan kernel melalui flag `O_NONBLOCK`. Ketika buffer kosong/penuh, kernel segera merespons dengan status errno `EWOULDBLOCK` atau `EAGAIN`. Ruby menangkapnya menjadi simbol `:wait_readable` atau `:wait_writable`.

Sejak Ruby 3.0, hadir **Fiber Scheduler** (interface non-blocking I/O transparan). Ketika `Fiber.schedule` digunakan bersama scheduler gem (seperti `async`), pemanggilan method I/O standar seperti `socket.read` secara otomatis diintersepsi dan didelegasikan ke event reactor (menggunakan gem `nio4r` yang mengabstraksi `libev`), membebaskan thread OS tanpa mengubah sintaks synchronous Ruby.

#### B. Rack Hijack Specification Architecture
Spesifikasi Rack 2 & 3 mendefinisikan mekanisme bypass daur hidup request-response standar via **Rack Hijack**.

Terdapat dua tipe hijack:
1. **Partial Hijack (`rack.hijack`)**: Diberikan oleh server di dalam headers response. Server mereturn respons HTTP status dan headers dasar, kemudian objek I/O diserahkan kepada callable (Proc) untuk mengontrol transmisi streaming data (misalnya SSE atau Chunked Transfer).
2. **Full Hijack (`rack.hijack_io`)**: Objek socket mentah (`IO` stream) diekstrak secara penuh dari hash `env`. Middleware atau aplikasi mengambil alih parsing protokol (koneksi di-upgrade dari HTTP ke WebSocket atau custom TCP protocol). Tanggung jawab closing socket berpindah sepenuhnya ke aplikasi; web server melepaskan tracking socket tersebut.

#### C. Puma Server Internals
Arsitektur internal Puma terdiri atas:
- **Reactor Loop**: Menggunakan `nio4r` untuk memonitor ribuan open client sockets secara multiplexing tanpa mengalokasikan OS Thread. Sockets yang masih menunggu data (misal: client lambat / *Slowloris*) ditahan di Reactor.
- **Thread Pool**: Sekumpulan thread pekerja (`Puma::ThreadPool`). Begitu request payload selesai dibaca secara lengkap oleh Reactor, socket di-dispatch ke queue Thread Pool untuk dieksekusi oleh pipeline Rack middleware dan framework (Rails/Sinatra).
- **Cluster Mode (Master-Worker)**: Master process me-listen Unix/TCP socket, memanggil `fork()` untuk membuat sejumlah worker process independen. Memanfaatkan copy-on-write (CoW) memory kernel Linux.

---

### 4. Why & What

| Dimensi | Pendekatan Thread-per-Request Tradisional | Pendekatan Rack Streaming / Hijack + Event Reactor |
| :--- | :--- | :--- |
| **Karakteristik Thread** | 1 client = 1 OS/Ruby Thread konstan. | 1 Thread melayani ratusan socket I/O wait. |
| **Batas Skalabilitas** | ~100–500 koneksi per worker process (dibatasi memory stack thread). | 10.000–50.000 koneksi aktif per worker node. |
| **Kasus Penggunaan Utama** | REST API standar pendek (< 100ms processing). | SSE, Long Polling, Real-time Telemetry, WebSocket. |
| **Konsumsi Memori** | Tinggi (2–8 MB stack per thread + metadata VM). | Rendah (~10–50 KB per idle state socket). |
| **Dampak I/O Lambat** | *Thread starvation*; pool habis, request baru mengalami timeout (HTTP 504). | Terisolasi di Reactor buffer; worker pool tetap melayani request lain. |

---

### 5. How: Workflow Detail

```
Client (Browser/Curl)            Puma Master/Reactor               Puma Worker Thread            Rack App / Hijack Engine
         |                                |                               |                               |
         |----- HTTP GET /stream -------->|                               |                               |
         |      (SYN, TCP Handshake)      |                               |                               |
         |                                |-- Push to Reactor Watcher --->|                               |
         |                                |  (Socket status: wait_read)   |                               |
         |<----- TCP ACK -----------------|                               |                               |
         |                                |                               |                               |
         |-- Request Body Finished ------>|                               |                               |
         |                                |-- Dispatch to Work Queue ---->|                               |
         |                                |                               |-- Execute Middleware Chain -->|
         |                                |                               |-- Call Rack App ------------->|
         |                                |                               |    Returns: [200,             |
         |                                |                               |             {'rack.hijack'=>p}|
         |                                |                               |             nil]              |
         |                                |                               |<-- Intercept Rack Hijack -----|
         |                                |                               |                               |
         |                                |                               |-- Call Proc.call(io_stream) ->|
         |                                |                               |   (Thread released or loops   |
         |                                |                               |    via Fiber/Background IO)   |
         |                                |                               |                               |
         |<===== Chunk 1 (HTTP/1.1 200 OK)================================|                               |
         |<===== Chunk 2 (Data: {...}) ===================================|                               |
         |       ...                      |                               |                               |
         |<===== FIN (Close Stream) ======================================|                               |
```

1. **Client Connection Phase**: Klien menginisiasi koneksi TCP. Master process menerima koneksi via `accept_nonblock` dan mendaftarkan socket descriptor ke Reactor epoll instance.
2. **Buffer Accumulation**: Reactor membaca chunk byte data header HTTP non-blocking sampai termination marker `\r\n\r\n` terdeteksi.
3. **Dispatching**: Request dipaketkan menjadi hash `env` Rack, dimasukkan ke queue milik worker thread pool.
4. **Execution & Hijack Triggering**: Thread pool mengeksekusi middleware. Aplikasi merespons dengan header partial hijack `'rack.hijack' => lambda { |io| ... }`.
5. **Streaming Transfer**: Socket stream dilepaskan dari siklus synchronous Rack response lifecycle. Aplikasi langsung menulis chunked protocol packets ke I/O buffer.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Cepat Saji (Streaming & Hijack)
Bayangkan kasir (Puma Reactor) menerima pesanan. 
- Pada sistem biasa: Pelanggan memesan makanan siap saji. Kasir menyerahkan tiket pesanan ke satu koki (Worker Thread). Koki memasak sampai selesai, menyerahkan ke kasir, lalu melayani pesanan berikutnya.
- Pada sistem streaming/hijack (misal *Free-flow Beverage Counter*): Pelanggan ingin minum kopi yang terus diisi ulang (*streaming*). Koki tidak menunggu pelanggan meminum kopi tersebut setetes demi setetes. Koki mengalihkan (*hijack*) pelanggan langsung ke dispenser otomatis (*dedicated streaming IO handler*). Koki dapat segera memasak burger untuk pelanggan berikutnya, sementara dispenser terus mengalirkan air ke cangkir pelanggan tanpa menyita waktu si koki.

```
PUMA PROCESS ARCHITECTURE:
=============================================================================
+---------------------------------------------------------------------------+
| Puma Master Process (PID 10001)                                           |
|   Listen: 0.0.0.0:9292 (Shared Socket FD 7)                               |
+---------------------------------------------------------------------------+
       |                                           |
       | fork()                                    | fork()
       v                                           v
+-----------------------------+             +-----------------------------+
| Worker 0 (PID 10002)        |             | Worker 1 (PID 10003)        |
|  +------------------------+ |             |  +------------------------+ |
|  | Reactor (epoll loop)   | |             |  | Reactor (epoll loop)   | |
|  | Monitors Sockets 12,14 | |             |  | Monitors Sockets 18,21 | |
|  +------------------------+ |             |  +------------------------+ |
|              |              |             |              |              |
|  +------------------------+ |             |  +------------------------+ |
|  | ThreadPool (Threads:5) | |             |  | ThreadPool (Threads:5) | |
|  | [T1] [T2] [T3] [T4] [T5] |             |  | [T1] [T2] [T3] [T4] [T5] |
|  +------------------------+ |             |  +------------------------+ |
|              |              |             |              |              |
|  +------------------------+ |             |  +------------------------+ |
|  | Rack Middleware Stack  | |             |  | Rack Middleware Stack  | |
|  | App logic / Hijack     | |             |  | App logic / Hijack     | |
|  +------------------------+ |             |  +------------------------+ |
+-----------------------------+             +-----------------------------+
=============================================================================
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Menggunakan Non-blocking IO Primitive Langsung
Contoh dasar bagaimana Ruby menangani socket I/O non-blocking menggunakan `IO.select` tanpa mengunci proses:

```ruby
# non_blocking_socket_primitive.rb
require 'socket'

server = Socket.new(:INET, :STREAM, 0)
sockaddr = Socket.pack_sockaddr_in(9001, '127.0.0.1')
server.setsockopt(:SOCKET, :SO_REUSEADDR, true)
server.bind(sockaddr)
server.listen(128)

puts "Server non-blocking berjalan di 127.0.0.1:9001..."

connections = [server]

loop do
  # Multiplexing I/O menggunakan select OS call
  readable, writable, errored = IO.select(connections, nil, connections, 2.0)

  if readable.nil?
    puts "[HEARTBEAT] Idle... menunggu koneksi/data."
    next
  end

  readable.each do |io|
    if io == server
      begin
        client_socket, client_addr = server.accept_nonblock
        puts "[ACCEPT] Klien terhubung dari #{client_addr.ip_unpack.join(':')}"
        connections << client_socket
      rescue IO::WaitReadable
        # Spurious wakeup handling
        next
      end
    else
      begin
        buffer = io.read_nonblock(4096)
        if buffer.empty?
          puts "[CLOSE] Klien menutup koneksi."
          connections.delete(io)
          io.close
        else
          puts "[RECV] Data diterima: #{buffer.strip}"
          io.write_nonblock("ECHO: #{buffer}")
        end
      rescue IO::WaitReadable
        # Data belum siap di kernel buffer, lanjutkan siklus
        next
      rescue EOFError, Errno::ECONNRESET
        puts "[DISCONNECT] Klien memutus koneksi."
        connections.delete(io)
        io.close
      end
    end
  end

  errored.each do |io|
    puts "[ERROR] Socket error pada IO: #{io}"
    connections.delete(io)
    io.close rescue nil
  end
end
```

#### Practical Example: Rack 3 Server-Sent Events (SSE) Streaming Middleware Berbasis Rack Hijack
Implementasi middleware tingkat produksi untuk streaming event data finansial secara real-time dengan proteksi backpressure dan heartbeat generator.

```ruby
# lib/middlewares/financial_event_stream.rb
# frozen_string_literal: true

require 'json'
require 'logger'

module Enterprise
  module Middleware
    class FinancialEventStream
      STREAM_PATH = '/api/v1/stream/market-data'

      def initialize(app, logger: Logger.new($stdout))
        @app = app
        @logger = logger
      end

      def call(env)
        # Delegasikan jika bukan path yang dituju
        return @app.call(env) unless env['PATH_INFO'] == STREAM_PATH

        # Verifikasi kapabilitas server terhadap spesifikasi Rack Hijack
        unless env['rack.hijack']
          return [
            501,
            { 'content-type' => 'application/json' },
            [{ error: 'Rack Server does not support rack.hijack' }.to_json]
          ]
        end

        # Request partial hijack dari web server
        # Mengembalikan status 200, Content-Type SSE, dan callable di 'rack.hijack'
        headers = {
          'content-type' => 'text/event-stream',
          'cache-control' => 'no-cache, no-transform',
          'connection' => 'keep-alive',
          'x-accel-buffering' => 'no' # Mencegah buffering di Nginx proxy
        }

        [
          200,
          headers,
          proc do |stream|
            handle_streaming(stream)
          end
        ]
      end

      private

      def handle_streaming(stream)
        @logger.info("SSE Stream dibuka: Thread #{Thread.current.object_id}")
        
        # Konfigurasi socket menjadi unbuffered dan pastikan write non-blocking
        io = stream.respond_to?(:to_io) ? stream.to_io : stream
        io.binmode
        io.sync = true

        # Channel pub-sub simulasi lokal
        queue = Thread::Queue.new
        consumer_thread = Thread.new do
          loop do
            # Simulasi incoming tick market
            sleep rand(0.5..1.5)
            queue.push({ symbol: 'BBCA', price: rand(9800..10200), timestamp: Time.now.to_f })
          end
        end

        last_heartbeat = Time.now.to_i

        loop do
          now = Time.now.to_i

          # Kirim Heartbeat setiap 10 detik agar intermediate NAT gateway tidak memutus koneksi
          if now - last_heartbeat >= 10
            write_chunk(io, ": ping\n\n")
            last_heartbeat = now
          end

          # Ambil data dari queue tanpa blocking tak terhingga
          unless queue.empty?
            payload = queue.pop(true) rescue nil
            if payload
              event_data = "event: quote\ndata: #{payload.to_json}\n\n"
              write_chunk(io, event_data)
            end
          end

          # Mencegah CPU Spin: yield control sejenak
          sleep 0.1
        end
      rescue Errno::EPIPE, Errno::ECONNRESET, IOError => e
        @logger.warn("SSE Client terputus: #{e.class} - #{e.message}")
      ensure
        consumer_thread.kill if consumer_thread&.alive?
        io.close rescue nil
        @logger.info("SSE Stream ditutup secara rapi (Resource Cleaned).")
      end

      def write_chunk(io, data)
        # Menulis dengan safe non-blocking write primitive dan timeout check
        remaining = data.byteslice(0..-1)
        
        while remaining.bytesize > 0
          begin
            written = io.write_nonblock(remaining, exception: false)
            case written
            when :wait_writable
              # Backpressure: kernel send buffer penuh, tunggu hingga socket writable
              unless IO.select(nil, [io], nil, 5.0)
                raise Errno::ETIMEDOUT, "Client socket buffer overflow (Slow Client)"
              end
            else
              remaining = remaining.byteslice(written..-1)
            end
          end
        end
      end
    end
  end
end
```

---

### 8. Real World Case Study: High-Throughput Financial Stream Gateway

#### Problem Background
Sebuah platform fintech *wealth management* memiliki 45.000 concurrent mobile apps yang mendengarkan pergerakan harga instrumen reksadana dan obligasi via HTTP Server-Sent Events (SSE). 

Sebelumnya, sistem menggunakan konfigurasi Rails standar pada Puma:
- 16 VM instances (c5.2xlarge - 8 vCPU, 16 GB RAM).
- Setup Puma: 4 Worker Processes, 16 Threads per worker (Total: 64 Threads per instance).
- Maksimum concurrent threads platform: 16 instances * 64 threads = **1.024 concurrent connections**.
- **Gejala Krisis**: Ketika 45.000 user login saat jam pembukaan bursa (09:00 WIB), seluruh Puma thread pool habis dalam 1.2 detik karena terpakai untuk mempertahankan streaming SSE loop. Akibatnya, request REST API reguler (Login, Order, Payment) mengalami HTTP 504 Gateway Timeout secara masif. Utilisasi CPU server hanya 4%, namun thread starvation mencapai 100%.

#### Solution Architecture
Perombakan dilakukan dengan memisahkan gateway SSE dari Rails monolitis:
1. **Rack Pure Service**: Mengganti pipeline Rails dengan standalone Rack application ringan yang dirancang khusus untuk SSE streaming menggunakan Rack Hijack.
2. **Event Reactor Engine (Falcon / Fiber Scheduler)**:
   - Alih-alih thread-per-client, arsitektur diubah menggunakan Ruby 3 Fiber Scheduler (`Async::HTTP`).
   - 1 Worker process dapat menangani 15.000 persistent sockets non-blocking menggunakan hanya 1 OS Thread via `epoll`.
3. **Puma Tuning untuk Service Pendukung**:
   - Jika tetap menggunakan Puma: Konfigurasi Puma dipasangkan dengan Nginx sebagai dynamic buffer unloader, dan SSE ditransfer ke Puma instances terisolasi dengan ratio thread yang disesuaikan.

#### Production Configuration Implementation
Berikut file konfigurasi deployment Puma cluster dan standalone stream runner yang digunakan:

```ruby
# config/puma.rb
# Production-ready Puma configuration for Streaming Cluster

threads_count = ENV.fetch('PUMA_THREADS', 5).to_i
threads threads_count, threads_count

workers ENV.fetch('PUMA_WORKERS', 4).to_i

# Bind ke Unix Domain Socket untuk performa maksimum di belakang Reverse Proxy Nginx
bind "unix://#{File.expand_path('../../tmp/sockets/puma.sock', __FILE__)}?backlog=4096"
environment ENV.fetch('RACK_ENV', 'production')

# Mengaktifkan low-latency non-blocking read buffering
queue_requests true

# Master process tuning
prune_bundler
preload_app!

# Zero-downtime rolling restart orchestration
tag 'enterprise-streaming-gateway'

before_fork do
  # Matikan koneksi database/Redis warisan master process sebelum fork
  # Mencegah connection leak dan double-free file descriptor
  defined?(ActiveRecord::Base) && ActiveRecord::Base.connection.disconnect!
end

on_worker_boot do
  # Re-establish pool koneksi di setiap worker child process
  defined?(ActiveRecord::Base) && ActiveRecord::Base.establish_connection
end
```

#### Results & Metric Verification
- **Kapasitas Konkurensi**: Dari 1.024 concurrent connections melonjak menjadi **60.000 concurrent active connections** pada cluster VM yang sama.
- **Utilisasi Memori**: Penggunaan memori turun drastis dari 14 GB menjadi 2.1 GB per instance karena penghapusan ribuan OS thread stack footprint.
- **REST Latency**: P99 Latency transaksi order kembali stabil di angka **18 ms** (sebelumnya berosilasi di angka > 15.000 ms akibat antrean worker starvation).

---

### 9. Trade-offs

```
CONCURRENCY MODEL COMPARISON:
=============================================================================
Thread-per-Request (Puma Default)
[Worker Thread] <==== Tightly Bound (1:1) ====> [Client Socket]
- Memori: ~2MB per koneksi
- Kompleksitas: Sangat Rendah
- Limitasi: Skalabilitas thread OS terbatas (< 2000 per mesin)

Rack Hijack + Background Thread
[Rack Worker] -> Hijack -> [Spawn Background Thread] <===> [Client Socket]
- Memori: Sedang (Stack thread background bertambah)
- Kompleksitas: Menengah (Perlu error handling manual & connection leak prevention)
- Limitasi: Masih bergantung pada batasan Thread scheduler MRI

Fiber Scheduler Engine (Ruby 3 Async)
[1 OS Thread / Worker]
   ├── [Fiber 1] <---> [Client Socket A] (epoll event loop)
   ├── [Fiber 2] <---> [Client Socket B]
   └── [Fiber N] <---> [Client Socket N]
- Memori: Sangat Rendah (~4KB-10KB per fiber)
- Kompleksitas: Tinggi (Semua gem dependensi harus 100% thread-safe & non-blocking)
=============================================================================
```

- **Performa & Throughput**: Hijack + Reactor memberikan throughput I/O luar biasa. Namun, jika ada kode CPU-bound yang tidak sengaja dieksekusi di dalam thread hijack, seluruh fiber/event loop di thread tersebut akan mengalami *freeze* (Head-of-Line Blocking).
- **Latency Distribution**: Rata-rata latency (P50) menurun drastis, tetapi tail latency (P99.9) dapat melonjak jika mekanisme I/O throttling/backpressure tidak diimplementasikan dengan presisi.
- **Operational Cost**: Infrastruktur menjadi jauh lebih ramping (penghematan biaya compute AWS/GCP mencapai 60-80%), namun biaya *engineering maintenance* meningkat karena debugging state asynchronous membutuhkan keahlian diagnosis core dump dan socket tracing level rendah.

---

### 10. Common Mistakes & Troubleshooting

#### 1. File Descriptor Leak via Unclosed Hijacked Sockets
- **Kesalahan**: Menggunakan partial hijack tetapi lupa mengeksekusi `stream.close` di dalam block `ensure`. Web server mengasumsikan I/O dikontrol aplikasi, sehingga tidak pernah menutup file descriptor tersebut.
- **Dampak**: Kernel panic / OS limits `Errno::EMFILE: Too many open files`.
- **Mitigasi**: Selalu gunakan idiom `begin ... ensure io.close end` serta set timeout socket SO_RCVTIMEO / SO_SNDTIMEO.

#### 2. Slowloris Vulnerability & Backpressure Ignorance
- **Kesalahan**: Menggunakan streaming non-blocking write `io.write_nonblock(data)` tanpa mengecek return value `:wait_writable`.
- **Dampak**: Jika client mengalami network throttle (misal: koneksi 2G/Edge), buffer lokal kernel pengirim akan meluap, memicu silent data loss atau exception `Errno::EWOULDBLOCK` yang tidak tertangani dan langsung mematikan thread.
- **Mitigasi**: Lakukan drain looping menggunakan `IO.select(nil, [io], nil, timeout)` ketika `:wait_writable` dilempar oleh runtime.

#### 3. Puma Worker Memory Bloat (Copy-on-Write Invalidation)
- **Kesalahan**: Mengalokasikan array/hash konfigurasi besar setelah fase `before_fork` atau secara lazy di request pertama.
- **Dampak**: Linux kernel OS menembakkan page fault dan memisahkan halaman memori fisik (Copy-on-Write fragmentation). Memori shared turun dari 85% menjadi 10%, memicu OOM (Out Of Memory) Killer.
- **Mitigasi**: Pastikan seluruh static cache dan pre-loading konstanta selesai dieksekusi di fase master initialization sebelum `fork_worker` dijalankan.

---

### 11. Best Practices (Production Checklist)

- [ ] **Kernel Limits Tuning**: Pastikan limit OS `ulimit -n` diset minimal `65535` untuk open files pada user yang menjalankan Puma.
- [ ] **TCP Socket Backlog Optimization**: Set kernel parameter `net.core.somaxconn = 4096` dan `net.ipv4.tcp_max_syn_backlog = 8192` pada host OS.
- [ ] **Proper Rack Hijack Checking**: Selalu cek ketersediaan `env['rack.hijack']` sebelum melakukan delegasi IO streaming untuk mencegah crash di lingkungan test (seperti `Rack::MockRequest`).
- [ ] **TCP Keepalive Enforcing**: Set opsi TCP socket `SO_KEEPALIVE`, `TCP_KEEPIDLE = 60`, `TCP_KEEPINTVL = 10`, `TCP_KEEPCNT = 3` pada streaming socket untuk mendeteksi client yang putus secara diam-diam (*half-open connections*).
- [ ] **Nginx Reverse Proxy Buffer Isolation**: Nonaktifkan buffering Nginx (`proxy_buffering off;`) khusus untuk endpoint SSE/streaming data agar respons tidak di-batch oleh reverse proxy.
- [ ] **Structured Graceful Termination**: Tangkap sinyal `SIGTERM` dan lakukan connection draining (hentikan penerimaan client baru, kirim termination frame ke client aktif, dan tunggu toleransi 15-30 detik sebelum `SIGKILL`).

---

### 12. Hands-on Practice

Buat seluruh file berikut di dalam folder workspace: `hands-on/m02/`

#### Step 1: Inisialisasi Environment
Buat file dependency `hands-on/m02/Gemfile`:
```ruby
source 'https://rubygems.org'

gem 'puma', '~> 6.4'
gem 'rack', '~> 3.0'
```
Jalankan di terminal:
```bash
bundle install
```

#### Step 2: Implementasi Custom Streaming Web Server
Buat file `hands-on/m02/app.ru`:
```ruby
# hands-on/m02/app.ru
# frozen_string_literal: true

require 'json'

class ProductionStreamingApp
  def call(env)
    case env['PATH_INFO']
    when '/health'
      [200, { 'content-type' => 'application/json' }, [{ status: 'healthy' }.to_json]]
      
    when '/telemetry'
      # Menggunakan Rack 3 Spec Response Streaming (Body responding to #each)
      # Memanfaatkan non-blocking hijack-compatible streaming interface
      headers = {
        'content-type' => 'text/event-stream',
        'cache-control' => 'no-cache',
        'connection' => 'keep-alive'
      }

      body = Enumerator.new do |streamer|
        10.times do |i|
          payload = { metric_id: i, load: rand(10..95), ts: Time.now.to_i }
          streamer << "data: #{payload.to_json}\n\n"
          sleep 0.5
        end
        streamer << "event: close\ndata: end of stream\n\n"
      end

      [200, headers, body]

    when '/hijack-raw'
      # Pure Rack Hijack 3.0 Implementation
      unless env['rack.hijack']
        return [500, {}, ['Hijack capability not available']]
      end

      [
        200,
        { 'content-type' => 'text/plain' },
        proc do |stream|
          io = stream.respond_to?(:to_io) ? stream.to_io : stream
          begin
            io.write("RAW SOCKET STREAMING INITIATED\r\n")
            5.times do |n|
              io.write("CHUNK #{n}: #{Time.now}\r\n")
              io.flush
              sleep 0.2
            end
          ensure
            io.close
          end
        end
      ]
    else
      [404, { 'content-type' => 'text/plain' }, ['Endpoint Not Found']]
    end
  end
end

run ProductionStreamingApp.new
```

#### Step 3: Deployment Testing & Verification
Jalankan server menggunakan Puma Cluster Mode:
```bash
bundle exec puma -w 2 -t 4:4 -b tcp://127.0.0.1:9292 app.ru
```

Buka terminal kedua dan uji streaming endpoint:
```bash
curl -N -v http://127.0.0.1:9292/telemetry
```
Verifikasi output mengalir secara bertahap tanpa terminasi koneksi di awal.

---

### 13. Exercises

#### Level Easy
Ubah method handler `/health` di file `app.ru` agar merespons dengan header custom `X-Worker-PID` yang mengembalikan `Process.pid` worker saat ini. Uji dengan 10 request berturut-turut via `curl` untuk mengamati pergantian PID yang menandakan load balancing cluster Puma bekerja.

#### Level Medium
Buat sebuah Rack Middleware `TrafficShedder` di `hands-on/m02/traffic_shedder.rb`. 
Middleware ini harus:
1. Memonitor queue depth atau concurrent connection counter internal.
2. Jika concurrent streaming request sedang aktif melebihi batas (misal: 5 connection), langsung tolak request ke `/telemetry` dengan response HTTP `503 Service Unavailable` dan header `Retry-After: 30`, tanpa menyentuh core application.

#### Level Hard
Kembangkan custom TCP reverse-proxy script di Ruby (`proxy.rb`) menggunakan Socket non-blocking API (`IO.select`). Script ini harus menerima request di port 8080 dan mem-forward request tersebut ke backend Puma (`127.0.0.1:9292`). Proxy wajib menangani streaming data bolak-balik tanpa memblokir transfer data jika salah satu endpoint (client atau server) lambat dalam membaca buffer.

---

### 14. Challenge

Anda ditugaskan mendesain sistem **Real-time Log Aggregation & Multiplexing Service** di Ruby untuk memantau cluster Kubernetes. 
**Persyaratan Arsitektur:**
1. Server harus mengonsumsi data log mentah dari ratusan microservice melalui 1 socket TCP intake non-blocking (port 5140).
2. Di saat yang sama, aplikasi Rack (Puma) mengekspos endpoint SSE `/admin/logs/tail?service=auth` di mana browser operator DevOps dapat streaming log dari service tertentu yang telah difilter secara real-time.
3. Gunakan in-memory pub/sub berbasis Ruby Queue dan Thread-safe registry.
4. **Target Stres**: Sistem tidak boleh mengonsumsi lebih dari 150 MB RAM ketika menerima throughput 10.000 log events per detik dan 500 koneksi SSE concurrent. Pastikan disconnection mendadak dari operator browser tidak menyebabkan crash pada TCP intake loop (hindari `EPIPE` unhandled exceptions).

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi dari flag `exception: false` pada pemanggilan socket method `IO#read_nonblock` di Ruby modern?
   - A. Menonaktifkan runtime garbage collection.
   - B. Mengembalikan simbol seperti `:wait_readable` alih-alih melempar exception `IO::WaitReadable`.
   - C. Memaksa socket berpindah ke mode synchronous blocking.
   - D. Menutup koneksi secara otomatis jika terjadi error network.

2. Di lingkungan web server berbasis Rack 3, apa nilai return yang valid dari method `call(env)`?
   - A. Objek string utuh yang mewakili respon HTTP.
   - B. Hash JSON yang berisi status code dan body.
   - C. Array 3 elemen: `[status, headers, body]`.
   - D. Integer status code saja.

3. Apa keuntungan utama menggunakan Unix Domain Socket dibandingkan TCP socket pada koneksi lokal antara Nginx dan Puma?
   - A. Unix domain socket mendukung enkripsi SSL native tanpa sertifikat.
   - B. Menghilangkan overhead protokol TCP/IP stack (routing, checksum, port allocation) dan beroperasi langsung via kernel buffers.
   - C. Unix domain socket tidak membutuhkan alokasi File Descriptor.
   - D. Unix domain socket secara otomatis mencegah memory leaks.

4. Apa dampak Global VM Lock (GVL) di MRI terhadap operasi Socket IO blocking standar?
   - A. GVL menghentikan seluruh thread lain sampai socket I/O blocking selesai sepenuhnya.
   - B. GVL dilepas (released) sementara selama system call I/O blocking berlangsung di level kernel, memungkinkan thread Ruby lain dieksekusi.
   - C. GVL mematikan proses jika operasi I/O memakan waktu > 5 detik.
   - D. Operasi socket I/O tidak pernah dipengaruhi oleh GVL.

5. Header HTTP apa yang wajib dikirimkan oleh server untuk mencegah Nginx melakukan buffer terhadap payload Server-Sent Events (SSE)?
   - A. `X-Frame-Options: DENY`
   - B. `X-Accel-Buffering: no`
   - C. `Transfer-Encoding: identity`
   - D. `Content-Encoding: gzip`

#### B. Pertanyaan Intermediate
6. Mengapa penggunaan `Thread.new` tanpa batasan di dalam Rack Partial Hijack berisiko tinggi mematikan server produksi?
   - A. Karena thread background tidak bisa mengakses variabel global.
   - B. Menyebabkan thread leak tak terkontrol yang menghabiskan memori VM dan memicu context switching overhead tinggi saat ribuan client terhubung.
   - C. Ruby MRI otomatis mematikan program jika total thread melebihi 100.
   - D. Thread baru akan langsung bentrok dengan socket descriptor milik Puma reactor.

7. Perhatikan potongan kode berikut:
   ```ruby
   stream = env['rack.hijack'].call
   ```
   Apa perbedaan antara pemanggilan hijack di atas (Full Hijack) dibandingkan partial hijack via headers array?
   - A. Tidak ada perbedaan fungsional.
   - B. Full hijack mengambil alih raw IO stream sebelum header HTTP dikirim oleh server; Partial hijack memungkinkan server mengirim status dan headers standar sebelum IO diserahkan ke Proc.
   - C. Full hijack hanya dapat digunakan untuk protokol HTTPS.
   - D. Partial hijack mematikan keep-alive connection secara sepihak.

8. Apa peran fungsi `prune_bundler` dalam konfigurasi `puma.rb`?
   - A. Menghapus gem yang tidak terpakai dari hard drive server.
   - B. Me-reload environment Bundler saat restart bertahap agar dependensi baru dapat dimuat tanpa menghentikan master process seutuhnya.
   - C. Mengurangi footprint memori worker sebesar 50%.
   - D. Mengunci versi Ruby agar tidak diubah oleh user lokal.

9. Ketika membaca dari non-blocking socket menggunakan `read_nonblock`, kernel mengembalikan status `EAGAIN` / `EWOULDBLOCK`. Apa langkah mitigasi teknis yang benar di Ruby?
   - A. Segera tutup socket dan log sebagai client error.
   - B. Lakukan loop `while true` tanpa jeda untuk terus membaca.
   - C. Gunakan `IO.select([socket], nil, nil, timeout)` untuk menidurkan thread sampai file descriptor siap dibaca oleh OS.
   - D. Lempar exception `RuntimeError` ke level middleware terluar.

10. Mengapa metode `preload_app!` di konfigurasi Puma sangat penting untuk penghematan konsumsi RAM pada Linux?
    - A. Memaksa seluruh class dimuat ke dalam CPU L3 Cache.
    - B. Memanfaatkan Copy-on-Write (CoW) memory sharing antara master process dan seluruh worker processes turunan.
    - C. Mengaktifkan garbage collection bertipe generational secara paksa.
    - D. Membagi memori RAM secara fisik di level hypervisor.

#### C. Skenario Kasus Produksi
11. **Skenario 1**: Server streaming SSE Anda mengalami lonjakan connection drop pada klien mobile setiap tepat 60 detik, meskipun server tidak mengirimkan instruksi penutupan koneksi dan utilisasi server rendah. Analisis penyebab paling mungkin di layer infrastruktur dan bagaimana memperbaikinya via Rack stream logic.
12. **Skenario 2**: Setelah merilis update middleware streaming, metrik server menunjukkan jumlah thread stabil, namun load average dan IO Wait server perlahan naik hingga 100%, disertai peringatan `Errno::EMFILE` pada log Puma. Diagnosa apa yang sedang terjadi di sistem dan di mana letak bug-nya.
13. **Skenario 3**: Sebuah worker Puma di cluster produksi tiba-tiba mengalami unresponsive (tidak membalas ping master) saat melayani streaming data berukuran gigabyte via socket non-blocking. Hasil thread dump menunjukkan worker stuck di baris `write_nonblock`. Jelaskan fenomena apa ini dan berikan arsitektur penanganan write backpressure yang presisi.

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Kunci Jawaban Bagian A
1. **B** — Flag `exception: false` mencegah alokasi objek Exception overhead di heap CRuby dan mengembalikan simbol error (`:wait_readable`/`:wait_writable`).
2. **C** — Standar spesifikasi Rack (Rack SPEC) menetapkan bahwa respons aplikasi harus berupa array 3 elemen: `[status_code, headers_hash, body_enumerable]`.
3. **B** — Unix Domain Socket menghindari overhead overhead IP packet generation, checksumming, routing loop, dan pembatasan ephemeral port OS.
4. **B** — Di Ruby MRI, macro `rb_thread_call_without_gvl` membungkus pemanggilan I/O blocking sehingga thread Ruby lain tetap bisa dieksekusi secara konkuren.
5. **B** — Nginx memegang buffer streaming secara default; header `X-Accel-Buffering: no` menginstruksikan Nginx untuk segera meneruskan chunk ke browser secara real-time.

#### Kunci Jawaban Bagian B
6. **B** — Membuat unconstrained OS thread via `Thread.new` untuk setiap streaming client akan mengakibatkan OOM dan context switching penalty yang melumpuhkan CPU scheduler.
7. **B** — Full Hijack membajak socket mentah dari awal koneksi (umum untuk WebSocket handshake), sementara Partial Hijack membiarkan server mengirim headers HTTP valid sebelum kontrol stream diserahkan.
8. **B** — `prune_bundler` memutus referensi gem runtime master process sehingga worker baru dapat me-load Gemfile versi anyar saat proses zero-downtime rolling restart (phased restart).
9. **C** — Memadukan `IO.select` saat mendeteksi status pending mencegah fenomena CPU spinning (100% core usage yang sia-sia).
10. **B** — `preload_app!` memuat source code di master process sebelum pemanggilan `fork()`. Halaman memori OS yang tidak diubah akan di-share bersama di antara workers via fitur Copy-on-Write (CoW).

#### Solusi Skenario Produksi
11. **Analisis Skenario 1**: 
    - *Akar Masalah*: Adanya perantara jaringan (Load Balancer AWS ALB, Nginx Proxy, atau firewall seluler) yang memberlakukan *idle timeout* (standar biasanya 60 detik). Karena SSE berjalan searah dan server tidak mengirimkan data jika pasar sepi, perantara menganggap koneksi TCP telah mati (*dead connection*) dan mengirimkan TCP FIN / RST.
    - *Solusi*: Implementasikan SSE Keep-Alive Heartbeat. Modifikasi stream handler untuk secara periodik (misal tiap 15 detik) mengirimkan komentar kosong SSE seperti `: heartbeat\n\n`. Ini menjaga state connection tetap aktif di NAT table gateway tanpa mempengaruhi parser event pada client.
12. **Analisis Skenario 2**:
    - *Akar Masalah*: Terjadi *File Descriptor (FD) Leak*. Kode middleware Anda membuka socket, pipe, atau file IO baru pada setiap request stream, namun saat client memutus koneksi (misal: user menutup aplikasi), blok penutupan resource tidak dieksekusi karena hilangnya block `ensure` atau exception `Errno::ECONNRESET` / `IOError` tidak ditangani.
    - *Solusi*: Pastikan wrapping socket handler selalu memiliki klausa `ensure { socket.close rescue nil }`. Gunakan command `lsof -p <puma_pid>` di server untuk memverifikasi socket descriptor yang menggantung bertipe `CLOSE_WAIT`.
13. **Analisis Skenario 3**:
    - *Akar Masalah*: *Socket Write Saturation / Unhandled Backpressure*. Klien membaca data lebih lambat dari kecepatan server memproduksi data (*Slow Consumer*). Socket kernel send-buffer menjadi penuh. `write_nonblock` mengembalikan `:wait_writable`, namun jika dimasukkan ke loop tanpa `IO.select` dengan timeout, worker process akan terjebak dalam tight CPU spin, atau jika diabaikan, akan terjadi data corruption.
    - *Solusi*: Implementasikan backpressure flow control. Tangkap nilai kembalian `write_nonblock`. Jika mengembalikan `:wait_writable`, panggil `IO.select(nil, [io], nil, timeout_threshold)`. Jika timeout terlampaui (misal 10 detik socket tidak writable), putuskan koneksi client tersebut secara paksa demi melindungi stabilitas resource server.

---

### 16. Summary

1. **Non-Blocking I/O Primitives**: Pemrograman jaringan tingkat lanjut di Ruby mengandalkan interaksi langsung antara socket API non-blocking (`read_nonblock`, `write_nonblock`) dengan OS multiplexing primitives (`IO.select`, `epoll`, `kqueue`).
2. **Rack 3 Streaming & Hijack**: Arsitektur Rack modern memberikan fleksibilitas penuh melalui spesifikasi streaming body dan Rack Hijack API (`rack.hijack`), memungkinkan implementasi protokol streaming berkinerja tinggi seperti Server-Sent Events dan WebSockets tanpa terikat pada siklus hidup synchronous request-response.
3. **Puma Enterprise Optimization**: Skalabilitas Puma di lingkungan produksi bergantung pada pemisahan tugas antara Reactor (menangani slow I/O non-blocking) dan Thread Pool (eksekusi CPU-bound/business logic), serta pemanfaatan Cluster Mode CoW memory dengan konfigurasi `preload_app!`.
4. **Resilience & Production Hardening**: Membangun backend real-time yang tangguh menuntut penanganan mendalam terhadap fenomena level rendah sistem operasi: proteksi send-buffer backpressure, mitigasi file descriptor leak menggunakan idiom `ensure`, pengiriman TCP heartbeat, dan penyesuaian parameter kernel OS.