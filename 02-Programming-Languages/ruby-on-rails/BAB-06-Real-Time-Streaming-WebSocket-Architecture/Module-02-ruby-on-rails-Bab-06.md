# BAB 06: Real-Time Streaming & WebSocket Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
* Membedah arsitektur internal Rails Action Cable, mencakup mekanisme *Rack socket hijacking* (`rack.hijack`), event loop berbasis `nio4r`, dan model konkurensi Ruby.
* Mengidentifikasi limitasi native Action Cable pada skala masif (*C10K/C100K problem*) dalam hal *memory footprint* dan konsumsi *thread*.
* Mengimplementasikan arsitektur real-time terdistribusi performa tinggi menggunakan AnyCable (AnyCable-Go + Rails gRPC worker) dan Solid Cable.
* Merancang sistem autentikasi WebSocket enterprise-grade berbasis Token/JWT dan session, termasuk mekanisme proteksi Cross-Site WebSocket Hijacking (CSWSH).
* Mengonfigurasi layer perantara (*reverse proxy*, Redis Cluster/Sentinel, pub/sub sharding) dan menerapkan monitoring metrik kritis (*active connections, broadcast latency, churn rate*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
* Model konkurensi Ruby: Thread, Fiber, GVL (*Global VM Lock*), serta pustaka `Concurrent::Ruby`.
* Protokol WebSockets (RFC 6455): Handshake via HTTP/1.1 `Upgrade`, framing, mask, opcodes, dan *heartbeat* (Ping/Pong).
* Fondasi spesifikasi Rack, khususnya *Rack hijack specification* (Environment: `rack.hijack` dan `rack.hijack_io`).
* Pengoperasian Redis: Struktur data pub/sub, Redis Sentinel, dan Redis Cluster.
* Arsitektur Action Cable dasar: `ApplicationCable::Connection` dan `ApplicationCable::Channel`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Raw Socket Hijacking (`rack.hijack`)
Web server Rack konvensional (seperti Puma) memproses request HTTP secara sinkron atau semi-asinkron menggunakan thread pool. Untuk mempertahankan koneksi WebSocket yang *long-lived* tanpa memblokir worker HTTP, Rails Action Cable memanfaatkan API Rack 1.5+ Full Hijacking.

1. Klien mengirim request HTTP upgrade:
   ```http
   GET /cable HTTP/1.1
   Host: api.enterprise.domain
   Upgrade: websocket
   Connection: Upgrade
   Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
   Sec-WebSocket-Version: 13
   ```
2. Action Cable menyuntikkan middleware yang membaca atribut `rack.hijack?` bernilai `true`.
3. Action Cable memanggil `env['rack.hijack'].call`. Web server melepaskan kontrol soket TCP dari siklus hidup HTTP normal dan menyerahkan objek `IO` mentah via `env['rack.hijack_io']`.
4. Kontrol I/O kini sepenuhnya berada di bawah kendali *Action Cable Connection engine*.

```
Client             Puma HTTP Worker          Action Cable Engine (nio4r)
  |                       |                              |
  |--- HTTP Upgrade ----->|                              |
  |                        -- rack.hijack.call --------->|
  |                       |<-- returns IO socket --------|
  |                       | [Thread returned to Pool]    |
  |<== 101 Switching =====|                              |
  |    Protocols          |                              |
  |                                                      |
  |<============== Full-Duplex WebSocket ===============>|
```

#### B. Event Loop dan Concurrency Engine (`nio4r` & `Concurrent::Ruby`)
Action Cable tidak menggunakan 1 thread per koneksi OS secara penuh untuk pembacaan I/O. Sebagai gantinya, Action Cable memanfaatkan `nio4r` (*New I/O for Ruby*), yang membungkus *system call* multiplexing I/O berperforma tinggi:
* `epoll` pada Linux
* `kqueue` pada macOS/BSD

Arsitektur konkurensi native Action Cable terbagi menjadi dua layer:
1. **I/O Reactor Loop (nio4r):** Sebuah thread tunggal (atau thread pool kecil) memonitor ribuan soket TCP untuk ketersediaan data baca (*read readiness*). Ketika klien mengirimkan frame WebSocket, reactor membaca payload dari buffer soket.
2. **Worker Pool (`Concurrent::ThreadPoolExecutor`):** Data yang telah di-dekode dari frame didelegasikan ke thread pool Action Cable (`config.action_cable.worker_pool_size`, default: 4 hingga 16). Logika Ruby pada level Channel (`receive`, `subscribed`, RPC methods) dieksekusi di dalam thread pool ini.

#### C. Keterbatasan Native Action Cable & Solusi AnyCable
Meskipun menggunakan `nio4r`, native Action Cable memiliki limitasi mendasar pada level Ruby Runtime:
* **Memory Footprint per Koneksi:** Ruby runtime membutuhkan 30–50 KB alokasi memori per representasi objek koneksi. Pada skala 100.000 Concurrent Connected Users (CCU), native Action Cable memakan 3 GB hingga 5 GB memori murni hanya untuk idle state, ditambah overhead garbage collection (GC pause).
* **GVL Contention:** Saat volume broadcast tinggi, serialisasi JSON dan deserialisasi frame WebSocket memicu saturasi CPU pada thread Ruby tunggal akibat GVL.

**Arsitektur AnyCable:**
AnyCable memisahkan *Connection Handling* dari *Business Logic Execution*:
* **AnyCable-Go (Ingress Layer):** Ditulis dalam Go, mengelola terminasi TLS/WebSocket, state koneksi, ping/pong, dan framing. Mengonsumsi memori sangat rendah (~2-5 KB per koneksi).
* **Rails AnyCable RPC Server:** Rails menjalankan gRPC service internal. AnyCable-Go hanya memanggil Rails via gRPC untuk event siklus hidup: `Connect`, `Subscribe`, `PerformAction`, dan `Disconnect`.
* **Redis/NATS Broadcast:** Ketika Rails mengeksekusi `ActionCable.server.broadcast`, pesan dipublikasikan ke Redis/NATS, dibaca langsung oleh AnyCable-Go, lalu di-multiplexing secara konkuren ke jutaan soket klien tanpa melibatkan Ruby runtime.

---

### 4. Why & What

| Dimensi | Native Action Cable (Redis Adapter) | AnyCable Enterprise | Solid Cable (Rails 8) |
| :--- | :--- | :--- | :--- |
| **Bahasa Pengelola Soket** | Ruby (CRuby via `nio4r`) | Go (`anycable-go`) | Ruby (CRuby via Puma/Engine) |
| **Konsumsi Memori / 10K CCU** | ~500 MB – 1.2 GB | ~30 MB – 60 MB | ~500 MB – 1.2 GB |
| **Mekanisme Pub/Sub** | Redis Pub/Sub Engine | Redis / NATS / Memory | PostgreSQL / MySQL (Polling via Index) |
| **Overhead GC Ruby** | Tinggi saat high churn rate | Nol untuk traffic WebSocket | Sedang hingga Tinggi |
| **Kebutuhan Infrastruktur** | Redis Instance mandiri | Node `anycable-go` + Rails gRPC | DB Relasional yang sudah ada |
| **Rekomendasi Skala** | < 10.000 CCU, arsitektur monolit | > 10.000 hingga 1.000.000+ CCU | Skala kecil-menengah, no-Redis setup |

---

### 5. How (Workflow Detail)

#### Siklus Hidup Koneksi dan Transmisi Data (AnyCable Model)

```
[Client]                [AnyCable-Go]              [Rails gRPC Worker]          [Redis PubSub]
   |                          |                            |                          |
   |--- WSS Handshake ------->|                            |                          |
   |    (Headers, Cookies)    |--- gRPC: Connect() ------->|                          |
   |                          |<-- Success, Session/ID ----|                          |
   |<-- 101 Switching Protocols|                           |                          |
   |                          |                            |                          |
   |--- Subscribe Channel --->|--- gRPC: Subscribe() ----->|                          |
   |                          |<-- Stream Accepted --------|                          |
   |                          |                            |                          |
   |                          |                    (Event Triggered)                  |
   |                          |                    Rails.broadcast() ---------------->|
   |                          |<------------------ Redis Subscription Stream --------|
   |<-- WS Frame Broadcast ---|                            |                          |
   |                          |                            |                          |
   |--- Disconnect ----------->|--- gRPC: Disconnect() ---->|                          |
```

1. **Handshake & Auth:** Klien menginisiasi koneksi WSS. Reverse proxy (Envoy/Nginx) memvalidasi SSL dan meneruskan koneksi ke AnyCable-Go.
2. **RPC Connect:** AnyCable-Go mengekstrak request headers/cookies, lalu memanggil method gRPC `Connect` ke pool Rails RPC Worker.
3. **Session Verification:** Rails memvalidasi token JWT / session terenkripsi di dalam `ApplicationCable::Connection`. Jika valid, Rails mengembalikan status sukses beserta identifiers (misal: `user_id`).
4. **Channel Subscription:** Klien mengirim frame JSON: `{"command": "subscribe", "identifier": "{\"channel\":\"OrderBookChannel\",\"market\":\"BTC_USDT\"}"}`. AnyCable-Go meneruskan ke gRPC `Command`.
5. **Subscription Authorization:** Rails memvalidasi hak akses subscribe. Jika diizinkan, Rails mendaftarkan stream name internal (`order_book_BTC_USDT`) ke AnyCable-Go.
6. **Broadcasting Engine:** Backend worker memicu `ActionCable.server.broadcast("order_book_BTC_USDT", { price: 65420.50 })`. Pesan masuk ke Redis Channel.
7. **Direct Distribution:** AnyCable-Go yang men-subscribe Redis channel tersebut langsung mengkloning frame dan mengirimkannya ke seluruh klien lokal yang terdaftar pada stream tersebut.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Resepsionis Hotel vs Ruang Konferensi Terpusat

* **Native Action Cable:** Seperti menyewa satu kamar hotel untuk setiap tamu bersama satu staf Ruby pribadi. Meskipun staf sedang diam (idle) saat tamu tidur, ia tetap menempati ruang, memakan jatah logistik, dan harus melapor secara berkala ke manajer operasional utama (GVL), menyebabkan kemacetan lorong hotel.
* **AnyCable:** Tamu berkumpul di aula raksasa yang dikelola oleh tim penjaga pintu berkemampuan tinggi (AnyCable-Go). Mereka hanya memeriksa kartu identitas tamu ke manajer kantor (Rails via gRPC) saat tamu pertama kali masuk atau meminta layanan khusus. Distribusi pengumuman ke seluruh aula dilakukan langsung oleh mikrofon pengeras suara tanpa melibatkan staf kantor sama sekali.

#### Diagram Topologi Produksi Multi-Node

```
                                  [ Internet (Clients) ]
                                            |
                                            v
                                  [ Cloudflare / AWS ALB ]
                                  (WSS / SSL Termination)
                                            |
                     +----------------------+----------------------+
                     |                                             |
                     v                                             v
          [ anycable-go Node 01 ]                       [ anycable-go Node 02 ]
          (Port: 8080, CCU: 50k)                        (Port: 8080, CCU: 50k)
             |                 \                               /                 |
             | gRPC             \ Redis Sub                   / Redis Sub        | gRPC
             v                   \                           /                   v
  +--------------------+          +-------------------------+          +--------------------+
  | Rails RPC Pods     |          |  Redis Sentinel Cluster |          | Rails RPC Pods     |
  | (Deployment K8s)   |          |  (Stream / PubSub Hub)  |          | (Deployment K8s)   |
  +--------------------+          +-------------------------+          +--------------------+
             |                                 ^
             +--- ActionCable.broadcast() -----+
```

---

### 7. Simple Example & Practical Example

#### A. Konfigurasi Dasar: Connection Hijack & Token-based Authentication

```ruby
# app/channels/application_cable/connection.rb
module ApplicationCable
  class Connection < ActionCable::Connection::Base
    identified_by :current_user, :connection_uuid

    def connect
      self.connection_uuid = SecureRandom.uuid
      self.current_user = find_verified_user
      logger.add_tags "ActionCable", "User:#{current_user.id}", "Conn:#{connection_uuid}"
    end

    private

    def find_verified_user
      # Ekstraksi token dari Query String atau Header Authorization
      token = request.query_parameters[:token] || request.headers["Sec-WebSocket-Protocol"]
      
      if token.present? && (payload = JsonWebToken.verify(token))
        if (user = User.find_by(id: payload["sub"]))
          user
        else
          reject_unauthorized_connection
        end
      else
        reject_unauthorized_connection
      end
    end
  end
end
```

#### B. Practical Enterprise Implementation: High-Throughput Order Book Channel

Implementasi channel dengan mitigasi *stream flooding*, validasi izin granular, dan pelaporan telemetri.

```ruby
# app/channels/order_book_channel.rb
class OrderBookChannel < ApplicationCable::Channel
  # Hook saat klien subscribe ke channel
  def subscribed
    market_symbol = params[:market]&.upcase
    
    if valid_market?(market_symbol)
      # Membatasi subscription unik per koneksi untuk menghemat tracking internal
      stop_all_streams
      
      stream_name = "order_book:#{market_symbol}"
      stream_from stream_name, ->(message) { 
        # Low-level hook filter sebelum payload dikirim ke soket
        process_outgoing_payload(message)
      }
      
      track_subscription_metrics(market_symbol)
    else
      reject
    end
  end

  # RPC invocation dari client: {"action": "place_micro_order", "data": {...}}
  def place_micro_order(data)
    rate_limit_key = "ws_rate:#{current_user.id}"
    current_requests = REDIS_POOL.with { |r| r.incr(rate_limit_key) }
    REDIS_POOL.with { |r| r.expire(rate_limit_key, 1) } if current_requests == 1

    if current_requests > 20
      transmit({ error: "Rate limit exceeded (Max 20 req/sec)", status: 429 })
      return
    end

    OrderProcessingJob.perform_later(
      user_id: current_user.id,
      market: params[:market],
      payload: data.slice("side", "price", "amount")
    )
  end

  def unsubscribed
    stop_all_streams
  end

  private

  def valid_market?(symbol)
    MarketRegistry.active_markets.include?(symbol)
  end

  def process_outgoing_payload(raw_json)
    # Lakukan sanitasi payload bila diperlukan
    raw_json
  end

  def track_subscription_metrics(market)
    ActiveSupport::Notifications.instrument("action_cable.subscribe", market: market, user_id: current_user.id)
  end
end
```

Konfigurasi adapter AnyCable pada Rails:

```yaml
# config/cable.yml
default: &default
  adapter: anycable

development:
  <<: *default

test:
  adapter: test

production:
  <<: *default
  # AnyCable menggunakan Redis broadcaster bawaan
  redis_url: <%= ENV.fetch("REDIS_CABLE_URL") { "redis://127.0.0.1:6379/1" } %>
  redis_sentinels: <%= ENV["REDIS_SENTINELS"] %>
  channel_prefix: enterprise_ws_prod
```

```ruby
# config/initializers/anycable.rb
AnyCable.configure do |config|
  # Port RPC internal tempat Rails mendengarkan gRPC request dari anycable-go
  config.rpc_host = "0.0.0.0:50051"
  config.redis_url = ENV.fetch("REDIS_CABLE_URL") { "redis://127.0.0.1:6379/1" }
  config.log_level = :info
  
  # Pool size untuk Rails gRPC execution threads
  config.rpc_pool_size = ENV.fetch("RAILS_MAX_THREADS") { 30 }.to_i
end
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
Platform Financial Cryptoc面向 (FinTech) Global mengalami kendala saat *traffic spike* terjadi. Sistem lama menggunakan monolit Rails dengan native Action Cable (didukung 40 pod Puma, 5 pod Redis Sentinel Pub/Sub).

#### Problem
* **Kapasitas Terbatas:** Saat volume pasar meledak, CCU melonjak hingga 250.000 koneksi simultan.
* **Out of Memory (OOM):** Setiap pod Puma menghabiskan memori hingga 4 GB dalam 15 menit (rata-rata 16 KB - 40 KB per koneksi idle + leak di garbage collector). Pod sering di-kill oleh Kubernetes OOMKilled.
* **Latency Degradation:** Broadcast data transaksi (*trade execution stream*) mengalami delay hingga 4.8 detik karena Redis Single-Threaded Pub/Sub saturasi dan Ruby GVL ter-choke saat serialization.

#### Rekayasa Solusi
1. **Pemisahan Layer (Decoupling):** Arsitektur dipindahkan ke AnyCable Enterprise.
2. **Cluster AnyCable-Go:** 6 node `anycable-go` (4 vCPU, 8 GB RAM) dipasang di balik AWS Network Load Balancer (NLB) level L4.
3. **Backend gRPC RPC Pool:** 12 pod Rails RPC Worker khusus (2 vCPU, 2 GB RAM) menangani event `Connect`, `Subscribe`, dan `Disconnect`.
4. **Redis Sharding:** Distribusi pub/sub channel menggunakan Redis cluster ter-sharding berdasarkan hash ring pasar (`market_symbol`).

#### Hasil Pengujian & Produksi
* **Memory Drop:** Konsumsi memori per koneksi anjlok dari ~35 KB menjadi 2.4 KB pada AnyCable-Go. Total memori cluster untuk 250.000 CCU berkurang dari ~8.7 GB (Ruby runtime) menjadi < 700 MB (Go runtime).
* **Latency Drop:** *End-to-end broadcast latency* berkurang drastis dari 4.800 ms menjadi **14 ms** (p99) pada beban 15.000 broadcast messages/detik.
* **Resource Optimization:** Pengurangan beban CPU Puma sebesar 78%, membebaskan resource worker untuk HTTP API standar.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keuntungan | Biaya & Konsekuensi Negatif |
| :--- | :--- | :--- |
| **Native Action Cable + Redis** | * Setup zero-dependency selain Redis.<br>* Menggunakan kode Ruby murni.<br>* Integrasi native dengan ActiveJob dan Hotwire/Turbo. | * Konsumsi memori masif pada skala besar.<br>* Scaling horizontal terikat pada ukuran worker Puma.<br>* Ancaman GC pause memicu koneksi drop massal. |
| **AnyCable + Go Ingress** | * Skalabilitas tinggi (100k+ CCU per node).<br>* Efisiensi memori (Go green threads/goroutines).<br>* Rails worker sepenuhnya terisolasi dari idle connection overhead. | * Kompleksitas operasional: Mengelola daemon AnyCable-Go terpisah.<br>* Debugging membutuhkan trace lintas protokol (HTTP -> gRPC -> WS).<br>* Fitur connection hijacking mentah terbatas di Go boundary. |
| **Server-Sent Events (SSE)** | * Berjalan di atas HTTP standar (HTTP/2 multiplexing).<br>* Sangat ringan, tidak membutuhkan stateful WebSocket proxy.<br>* Otomatis reconnect via browser native API. | * Komunikasi satu arah (Server-to-Client saja).<br>* Tidak mendukung transfer data biner seefisien WS frame.<br>* Batasan koneksi per domain pada HTTP/1.1 (jika HTTP/2 gagal dinegosiasikan). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Database Query di Dalam Loop `receive` / `subscribed`
* **Gejala:** Seluruh WebSocket worker berhenti merespons, latensi HTTP melonjak, database connection pool exhaustion (`ActiveRecord::ConnectionTimeoutError`).
* **Root Cause:** Melakukan query berat sinkronus (seperti `User.find`, `order.recalculate!`) di dalam Channel action. Karena thread pool terbatas, thread cepat habis terblokir oleh I/O Database.
* **Solusi:** Hanya baca state ter-cache (Redis) di level channel. Delegasikan komputasi berat ke Background Worker (Sidekiq):
  ```ruby
  def receive(data)
    OrderDispatchJob.perform_later(current_user.id, data["payload"])
  end
  ```

#### Kesalahan 2: Tidak Mengonfigurasi Proxy Read/Write Timeouts
* **Gejala:** Koneksi WebSocket terputus persis setiap 60 detik secara massal (*abrupt disconnects*), memicu *reconnection storm*.
* **Root Cause:** Nginx atau AWS ALB memiliki timeout default `proxy_read_timeout 60s`. Jika tidak ada frame yang dikirim dalam jendela tersebut, proxy menganggap soket hang dan mengirim RST packet.
* **Solusi:** Sinkronisasikan heartbeat interval di Action Cable dengan timeout reverse proxy:
  ```nginx
  # /etc/nginx/conf.d/websocket.conf
  proxy_read_timeout 3600s;
  proxy_send_timeout 3600s;
  ```
  ```ruby
  # config/initializers/action_cable.rb
  ActionCable.server.config.ping_interval = 15 # default 3 detik
  ```

#### Kesalahan 3: Missing Backpressure Controls pada Broadcast Stream
* **Gejala:** Memory node Go atau Ruby melonjak tinggi saat subscriber berada pada jaringan lambat (Slow Consumer Problem).
* **Solusi:** Dropping packets atau implementasi sliding window buffer daripada mengantrekan (*queuing*) pesan tanpa batas di memory buffer soket:
  ```ruby
  # Hanya broadcast update delta terakhir, bukan full dump berulang
  ActionCable.server.broadcast("market_updates", {
    type: "delta",
    t: Time.current.to_i,
    data: compressed_diff
  })
  ```

---

### 11. Best Practices (Production Checklist)

* [ ] **WSS Strict Enforcement:** Blokir seluruh unencrypted `ws://` traffic. Pastikan TLS 1.3 diaktifkan di load balancer.
* [ ] **Proteksi CSWSH (Cross-Site WebSocket Hijacking):** Batasi origins secara ketat di environment produksi:
  ```ruby
  # config/environments/production.rb
  config.action_cable.allowed_request_origins = [
    'https://enterprise.domain',
    /https:\/\/.*\.enterprise\.domain/
  ]
  ```
* [ ] **Redis Connection Pooling:** Pastikan ukuran pool Redis setidaknya sama dengan `(worker_pool_size + 1) * number_of_processes`:
  ```yaml
  # config/cable.yml
  production:
    adapter: redis
    url: <%= ENV['REDIS_URL'] %>
    pool: <%= ENV.fetch("RAILS_MAX_THREADS", 5).to_i * 2 %>
  ```
* [ ] **TCP Keepalive & Buffer Tuning:** Atur level kernel OS pada server WebSocket:
  ```bash
  sysctl -w net.ipv4.tcp_keepalive_time=300
  sysctl -w net.ipv4.tcp_keepalive_intvl=15
  sysctl -w net.ipv4.tcp_keepalive_probes=5
  sysctl -w net.core.somaxconn=32768
  ```
* [ ] **Graceful Disconnect Recovery:** Sediakan *exponential backoff + jitter* pada JavaScript client reconnect logic untuk mencegah *Thundering Herd* saat instance WebSocket di-deploy ulang.

---

### 12. Hands-on Practice

Simpan seluruh file praktik ini di bawah direktori `hands-on/m02/`.

#### Langkah 1: Siapkan Struktur Direktori & Konfigurasi Lingkungan
Pastikan Docker dan Docker Compose tersedia di sistem Anda.

```bash
mkdir -p hands-on/m02/config hands-on/m02/app/channels hands-on/m02/app/jobs
cd hands-on/m02
```

#### Langkah 2: Buat `docker-compose.yml` untuk Stack AnyCable
Buat file `hands-on/m02/docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  anycable-go:
    image: anycable/anycable-go:v1.4
    ports:
      - "8080:8080"
    environment:
      ANYCABLE_HOST: "0.0.0.0"
      ANYCABLE_PORT: "8080"
      ANYCABLE_RPC_HOST: "rails-rpc:50051"
      ANYCABLE_REDIS_URL: "redis://redis:6379/0"
      ANYCABLE_METRICS_HTTP: "/metrics"
      ANYCABLE_METRICS_PORT: "2112"
    depends_on:
      - redis
      - rails-rpc

  rails-rpc:
    build: .
    command: bundle exec anycable
    environment:
      RAILS_ENV: development
      REDIS_URL: "redis://redis:6379/0"
      ANYCABLE_RPC_HOST: "0.0.0.0:50051"
    volumes:
      - .:/app
    depends_on:
      - redis
```

#### Langkah 3: Definisikan `Dockerfile` dan `Gemfile`
Buat file `hands-on/m02/Gemfile`:

```ruby
source 'https://rubygems.org'

gem 'rails', '~> 7.1.0'
gem 'anycable-rails', '~> 1.4'
gem 'redis', '~> 5.0'
gem 'jwt'
gem 'puma'
```

Buat file `hands-on/m02/Dockerfile`:

```dockerfile
FROM ruby:3.2-alpine

RUN apk add --no-cache build-base tzdata

WORKDIR /app

COPY Gemfile /app/
RUN bundle install

COPY . /app

EXPOSE 50051
```

#### Langkah 4: Buat Implementasi Channel & Connection
Buat file `hands-on/m02/app/channels/telemetry_channel.rb`:

```ruby
class TelemetryChannel < ApplicationCable::Channel
  def subscribed
    device_id = params[:device_id]
    if device_id.present?
      stream_from "telemetry:#{device_id}"
      logger.info "[Telemetry] Device Subscribed: #{device_id}"
    else
      reject
    end
  end

  def submit_ping(data)
    # Echo kembali dengan server timestamp
    transmit({
      event: "pong",
      client_timestamp: data["timestamp"],
      server_timestamp: Process.clock_gettime(Process::CLOCK_REALTIME, :millisecond)
    })
  end

  def unsubscribed
    stop_all_streams
  end
end
```

#### Langkah 5: Eksekusi dan Verifikasi Koneksi
Jalankan stack:
```bash
docker compose up --build -d
```

Uji koneksi WebSocket menggunakan klien CLI (misalnya `wscat`):
```bash
# Connect ke anycable-go di port 8080
wscat -c "ws://localhost:8080/cable"
```

Kirim payload subscription:
```json
{"command":"subscribe","identifier":"{\"channel\":\"TelemetryChannel\",\"device_id\":\"DEV-1099\"}"}
```

Kirim event telemetry:
```json
{"command":"message","identifier":"{\"channel\":\"TelemetryChannel\",\"device_id\":\"DEV-1099\"}","data":"{\"action\":\"submit_ping\",\"timestamp\":1710000000}"}
```

Periksa respon JSON yang dipancarkan secara instan oleh AnyCable melalui interkoneksi gRPC Rails!

---

### 13. Exercise

#### Level: Easy
Implementasikan *Heartbeat Echo* di level Channel. Buat channel bernama `HeartbeatChannel` dengan method `ping`. Server harus merespons dengan payload JSON yang memuat waktu saat ini (`Time.now.to_f`) dan payload yang dikirim klien secara persis. Batasi ukuran payload maksimum 256 bytes.

#### Level: Medium
Rancang skema autentikasi berbasis *Signed Cookies* untuk Action Cable tanpa menggunakan plain JWT. Sistem harus membaca cookie terenkripsi Rails (`cookies.encrypted[:enterprise_session_id]`), mengambil session dari Redis store, dan menolak koneksi (`reject_unauthorized_connection`) jika session expired atau token IP mismatch.

#### Level: Hard
Terapkan arsitektur *Broadcast Sharding* multi-Redis. Buat custom broadcaster class (`DistributedBroadcaster`) yang memilih koneksi Redis secara deterministik berdasarkan algoritma *Consistent Hashing* dari nama `stream_name`. Hal ini dilakukan guna mencegah bottleneck pada satu instance Redis Pub/Sub utama ketika volume pesan melebihi 50.000 messages/detik.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Sebuah platform analitik IoT memantau 500.000 traktor industri yang mengirimkan telemetri status mesin setiap 2 detik. Setiap traktor memiliki dashboard monitoring web yang diakses oleh operator armada.
Arsitektur Anda harus:
1. Menangani 500.000 koneksi WebSocket konkuren dengan alokasi resource komputasi sekecil mungkin.
2. Mencegah *Slow Consumer Problem*: Jika koneksi dashboard browser operator lambat (misal koneksi seluler 3G), server dilarang menimbun pesan di RAM (wajib drop packet secara anggun dan hanya menyajikan frame terbaru).
3. Mengakomodasi skenario *Rolling Deploy*: Deploy service backend tidak boleh memutuskan lebih dari 5% total CCU per detik untuk menghindari *reconnection storm* yang dapat melumpuhkan gateway API.

**Tugas Anda:**
Tuliskan cetak biru desain sistem lengkap yang mencakup:
* Arsitektur cluster (AnyCable-Go, gRPC, Redis Pub/Sub, Envoy Load Balancer).
* Modifikasi kode Ruby Channel dan strategi *backpressure discarding*.
* Strategi migrasi dan script/konfigurasi graceful draining pada Kubernetes (Grace Period, Readiness Probe, dan PreStop Hook).

*(Selesaikan tantangan ini secara mandiri sebagai tolok ukur kesiapan Anda di level Principal Engineer).*

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa fungsi dari environment variable `rack.hijack` dalam konteks penanganan WebSocket di Rails?
2. Mengapa AnyCable-Go dapat menangani koneksi jauh lebih banyak dibandingkan Action Cable native dengan jumlah RAM yang sama?
3. Apa perbedaan mendasar antara `stream_from` dan `stream_for` pada Action Cable Channel?
4. Apa yang menyebabkan kerentanan Cross-Site WebSocket Hijacking (CSWSH), dan bagaimana cara Rails mencegahnya secara default?
5. Di thread manakah kode logika Ruby pada method `ApplicationCable::Channel#receive` dieksekusi dalam Action Cable native?

#### Intermediate (5 Soal)
1. Bagaimana cara kerja `nio4r` dalam menyatukan model multiplexing I/O OS (`epoll`/`kqueue`) dengan thread pool `Concurrent::Ruby`?
2. Mengapa Redis Pub/Sub standar tidak ideal untuk audit trail data real-time, dan teknologi apa yang seharusnya menjadi layer persistensinya?
3. Jelaskan dampak buruk memanggil database transaction (`ActiveRecord::Base.transaction`) yang panjang di dalam event `ApplicationCable::Connection#connect`.
4. Bagaimana AnyCable-Go mengetahui bahwa suatu pesan Redis harus diteruskan ke klien A, tetapi tidak ke klien B?
5. Mengapa arsitektur WebSocket real-time membutuhkan konfigurasi khusus pada layer L7 reverse proxy terkait HTTP Keep-Alive dan Buffer Timeout?

#### Scenario-Based Production (3 Soal)
1. **Skenario A:** Setelah melakukan rilis patch security, pod AnyCable-Go Anda me-restart 3 node sekaligus. Tiba-tiba CPU Rails RPC worker melonjak hingga 100% dan pod AnyCable-Go gagal melewati fase health check. Analisis fenomena apa yang sedang terjadi dan bagaimana solusi preventifnya!
2. **Skenario B:** Database PostgreSQL Anda mencapai limit `max_connections` (1000 koneksi). Setelah diinvestigasi, tidak ada lonjakan request HTTP, melainkan terdapat 10.000 subscriber baru pada WebSocket channel aplikasi. Di mana letak kesalahan arsitektur konfigurasi ActiveRecord pool Anda?
3. **Skenario C:** Pengguna mengeluhkan dashboard mereka "membeku" (tidak menerima update real-time) setelah berpindah dari jaringan Wi-Fi ke hotspot seluler, meskipun status UI menunjukkan WebSocket "Connected". Mengapa ini terjadi dan bagaimana mekanisme recovery yang harus dibangun di level protokol?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Jawaban Basic
1. `rack.hijack` mentransfer kepemilikan underlying TCP socket dari siklus hidup Puma HTTP request pool ke Action Cable engine secara langsung, membiarkan koneksi tetap terbuka tanpa menahan thread HTTP worker.
2. AnyCable-Go ditulis dalam Go yang menggunakan *goroutines* (overhead per koneksi ~2-4 KB) dan tidak memiliki batasan GVL atau alokasi object memory Ruby yang berat (~30-50 KB per koneksi).
3. `stream_from` menerima parameter string arbitrary (misal: `"global_notifications"`), sedangkan `stream_for` mengabstraksi penamaan stream berdasarkan objek model ActiveRecord tertentu (misal: `stream_for current_user` menghasilkan stream string khusus objek tersebut).
4. CSWSH terjadi ketika attacker memicu koneksi WebSocket dari website berbahaya menggunakan browser cookie korban yang valid. Rails mencegahnya dengan memvalidasi header `Origin` via konfigurasi `config.action_cable.allowed_request_origins`.
5. Kode dieksekusi di dalam thread pool Action Cable (`ActionCable::Server::Configuration#worker_pool_size`), bukan di thread I/O reactor nio4r.

#### Jawaban Intermediate
1. `nio4r` mendaftarkan file descriptor (FD) soket ke OS multiplexer (`epoll`). Thread reactor akan tertidur sampai ada event I/O siap dibaca. Saat data tiba, reactor mengambil buffer lalu melemparkan tugas eksekusi logika channel ke pool worker `Concurrent::ThreadPoolExecutor` untuk dieksekusi secara independen.
2. Redis Pub/Sub bersifat *fire-and-forget*; pesan yang dikirim saat subscriber offline atau mengalami lag network langsung hilang tanpa ada recovery buffer. Persistensi audit trail membutuhkan Redis Streams, Apache Kafka, atau database transactional.
3. Transaksi DB yang panjang menahan koneksi connection pool database secara sia-sia saat proses handshake koneksi berlangsung, yang seketika menghabiskan ActiveRecord connection pool jika banyak klien terhubung bersamaan.
4. Rails memberi tahu AnyCable-Go nama stream string saat subscription disetujui melalui gRPC response. AnyCable-Go memelihara internal hash map antara nama stream dengan client session ID lokal.
5. Reverse proxy default mematikan koneksi yang tidak mentransfer data HTTP dalam batas waktu tertentu (biasanya 60s). L7 proxy butuh bypass proxy buffering (`proxy_buffering off`) dan update timeout untuk mencegah terputusnya pipa data stateful duplex.

#### Jawaban Scenario-Based Production
1. **Analisis Masalah:** Terjadi *Thundering Herd Problem* (Connect Storm). Ratusan ribu klien melakukan reconnect secara bersamaan, membanjiri pool Rails RPC worker dengan pemanggilan gRPC `Connect` secara masif, melumpuhkan CPU Ruby.
   **Solusi:** Terapkan reconnection delay dengan jitter di client-side SDK. Tambahkan layer caching session auth di AnyCable-Go (fitur JWT authentication langsung di Go tanpa RPC ke Rails).
2. **Analisis Masalah:** Konfigurasi channel atau hook connection Anda melakukan query ActiveRecord secara implisit, padahal `pool` di `database.yml` diatur terlalu besar per pod, atau pod RPC worker mengalokasikan koneksi DB per worker thread tanpa melepaskannya kembali (`connection_pool.with_connection`).
   **Solusi:** Bungkus eksekusi query dalam Channel menggunakan `ActiveRecord::Base.connection_pool.with_connection { ... }` untuk memastikan koneksi dikembalikan ke pool segera setelah pembacaan selesai, atau hindari query DB langsung pada lifecycle connection dengan menaruh metadata ke dalam token.
3. **Analisis Masalah:** Terjadi *Half-Open Connection* (Blackhole). IP berubah saat transisi Wi-Fi ke seluler, namun FIN/RST packet tidak pernah terkirim ke server. Soket TCP di sisi OS tetap menganggap dirinya terhubung padahal route fisik sudah putus.
   **Solusi:** Implementasikan mekanisme Ping/Pong Heartbeat aktif di level aplikasi (bukan hanya TCP keepalive). Jika klien tidak menerima Ping/Pong frame dari server dalam interval waktu $X$ detik, klien secara agresif harus memutus paksa soket (`socket.close()`) dan menginisiasi koneksi baru.

---

### 16. Summary

* Action Cable mengabstraksi penanganan real-time di Rails menggunakan Rack socket hijacking (`rack.hijack`) dan reactor I/O non-blocking (`nio4r`), namun terbatasi oleh konsumsi memori dan model konkurensi Ruby saat menangani puluhan ribu koneksi.
* AnyCable adalah standar industri untuk menjalankan WebSocket Rails pada skala enterprise: memindahkan layer terminasi koneksi yang stateful dan memory-heavy ke binary Go (`anycable-go`), sementara Rails RPC worker tetap mempertahankan kontrol penuh atas business logic dan autentikasi.
* Keberhasilan arsitektur real-time skala besar bergantung pada isolasi database dari connection lifecycle, penanganan Slow Consumer problem, mitigasi Thundering Herd saat pemulihan koneksi, dan kepatuhan terhadap proteksi CSWSH.