# SEKSI 01 — IDENTITAS MODUL

* **Kategori Kurikulum:** 02-Programming-Languages
* **Jalur Pembelajaran:** Ruby on Rails Core & Advanced Architectures
* **Bab:** 06 — Advanced Concurrency, Real-Time Systems & Distributed Rails
* **Modul:** 01 — Real-Time Streaming & WebSocket Architecture
* **Tingkat Kesulitan:** Advanced
* **Prasyarat:**
  * Penguasaan mendalam mengenai HTTP/1.1 dan HTTP/2 Lifecycle.
  * Pemahaman arsitektur Rack, Rack Environment, dan Middleware pipeline.
  * Pemahaman model konkurensi Ruby (Thread, Fiber, GVL/GIL).
  * Penguasaan Active Record callbacks dan asynchronous job processing (Sidekiq/Solid Queue).
* **Target Stack:** Ruby 3.3+, Rails 7.1/8.0, Action Cable, Solid Cable / Redis Pub/Sub, Turbo Streams, Puma.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1. **Menganalisis Mekanisme Socket Hijacking:** Menguraikan proses transisi koneksi HTTP standar menjadi protokol dupleks penuh (*full-duplex*) berstatus persisten melalui *Rack socket hijacking* dan *event loop abstraction* di Rails.
2. **Merancang Topologi Pub/Sub Berskala Besar:** Mengonfigurasi dan mengoperasikan *Action Cable subscription adapters* (khususnya Redis dan Solid Cable) guna menyalurkan aliran data real-time dengan latensi rendah pada beban konkurensi tinggi.
3. **Mengeliminasi Concurrency Bottlenecks:** Mengidentifikasi dan memitigasi isu kritis seperti *ActiveRecord connection pool exhaustion*, memori bocor (*memory leaks*) pada koneksi berumur panjang, dan fenomena *thundering herd* saat re-koneksi massal.
4. **Menerapkan Pertahanan Keamanan WebSocket:** Membangun lapisan otentikasi, otorisasi kanal, mitigasi *Cross-Site WebSocket Hijacking* (CSWSH), serta *rate limiting* berbasis kanal.
5. **Mengintegrasikan Turbo Streams over WebSockets:** Membangun aplikasi web reaktif modern tanpa overhead Single Page Application (SPA), memanfaatkan Turbo Streams terintegrasi langsung dengan Action Cable.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dalam web development tradisional berbasis HTTP, model mental yang digunakan adalah **"Request-Response / Pull Architecture"**:
* Klien mengirim request, server merespons, koneksi TCP ditutup (atau di-*keep-alive* dalam status idle).
* Klien adalah inisiator tunggal; server bersifat pasif dan *stateless*.

```
Model HTTP Tradisional (Stateless Pull):
Client -----[ HTTP Request ]-----> Server (Alokasi Thread/DB)
Client <----[ HTTP Response ]----- Server (Koneksi Selesai/Tutup)
```

Dalam **"Real-Time Streaming & WebSocket Architecture"**, model mental bergeser menjadi **"Persistent Stateful Conduit & Push Architecture"**:
* Server dan Klien membangun koneksi persisten dua arah (*full-duplex*).
* Server memegang referensi soket klien yang terbuka dan dapat mengirim data kapan saja tanpa menunggu permintaan (*unsolicited push*).
* Koneksi tidak lagi murah secara memori; ratusan ribu koneksi TCP yang menggantung (*hanging sockets*) harus dikelola secara non-blocking (*I/O multiplexing*) agar tidak menguras thread pool server.

```
Model WebSocket (Stateful Event-Driven Push):
Client -----[ HTTP 101 Switching Protocols ]-----> Server
Client <=====[ Persistent Bidirectional Conduit ]=====> Server
                 (Broadcasting via Pub/Sub)
```

### Analogi Sistem
* **HTTP Biasa:** Pengiriman surat pos fisik. Anda mengirim formulir, menunggu surat balasan, lalu interaksi selesai.
* **HTTP Polling:** Anda menelepon resepsionis setiap 3 detik bertanya, *"Apakah ada surat untuk saya?"*. Sangat boros daya, bandwidth, dan waktu.
* **WebSocket:** Anda memasang interkom kabel langsung dari meja Anda ke ruang kontrol. Kanal selalu terbuka; informasi disampaikan secara instan saat data tersedia di ruang kontrol.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Arsitektur Action Cable di Ruby on Rails memadukan web server multi-threaded (Puma) dengan layer abstraction asynchronous berbasis gem `nio4r` (*New I/O for Ruby*) dan message broker (Redis atau Database via PostgreSQL/Solid Cable).

```
+-----------------------------------------------------------------------------+
|                                KLIENT / BROWSER                             |
|  (Turbo Stream Client / Action Cable JS: createConsumer() -> Subscription)  |
+-----------------------------------------------------------------------------+
                                       |
                     WebSocket Handshake (HTTP Upgrade 101)
                                       v
+-----------------------------------------------------------------------------+
|                                PUMA WEB SERVER                              |
|                                                                             |
|  [Rack Environment] -> rack.hijack -> Puma Worker Thread mengoper kontrol  |
|                                        soket mentah ke Action Cable         |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                             ACTION CABLE ENGINE                             |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  | Event Loop (nio4r / Async / Concurrent Ruby ThreadPool)               |  |
|  | Memantau ribuan soket TCP non-blocking via OS kqueue / epoll           |  |
|  +-----------------------------------------------------------------------+  |
|                                      |                                      |
|                                      v                                      |
|  +-----------------------------------------------------------------------+  |
|  | Connection Instance (ApplicationCable::Connection)                    |  |
|  | - Otentikasi (Cookies, Devise, Session, Warden)                        |  |
|  | - Channel Subscriptions Registry                                     |  |
|  +-----------------------------------------------------------------------+  |
|                                      |                                      |
|                                      v                                      |
|  +-----------------------------------------------------------------------+  |
|  | Channels (e.g., LiveAuctionChannel, NotificationsChannel)             |  |
|  | - Subscribed / Unsubscribed lifecycle hooks                           |  |
|  | - Action Routing (method calls dari client message)                   |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
                                       ^
                                       | Subscribe / Broadcast
                                       v
+-----------------------------------------------------------------------------+
|                          PUB/SUB ADAPTER LAYER                              |
|                                                                             |
|       +------------------------------------+--------------------------+      |
|       |                                    |                          |      |
|       v                                    v                          v      |
|  [Redis Adapter]                  [Solid Cable (DB)]          [AnyCable RPC] |
|  - Engine: Redis Engine           - Engine: PostgreSQL/MySQL   - Engine: Go  |
|  - Pattern: REDIS SUBSCRIBE       - Pattern: Polling/Notify   - Scalability: |
|    / PUBLISH                        Streams via Arel             100k+ Conns |
+-----------------------------------------------------------------------------+
                                       ^
                                       | ActionCable.server.broadcast(...)
                                       |
+-----------------------------------------------------------------------------+
|                       ASYNCHRONOUS WORKER / RAILS APP                       |
|           (Sidekiq / Solid Queue / Active Record Lifecycle Hooks)           |
+-----------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. The Upgrade Handshake & Rack Hijacking
Koneksi WebSocket dimulai sebagai permintaan HTTP standar:
```http
GET /cable HTTP/1.1
Host: api.production.internal
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
```

Rails mengeksekusi request ini melalui middleware stack hingga mencapai Action Cable Engine. Di sini, Action Cable memanfaatkan spesifikasi **Rack Socket Hijacking (khususnya full hijacking)**:
* Server memeriksa variabel `env['rack.hijack']`.
* Action Cable memanggil `env['rack.hijack'].call`. Objek soket I/O mentah (`IO` object) diambil alih langsung dari Puma.
* Puma melepaskan tanggung jawab atas penanganan daur hidup request tersebut. Thread HTTP Puma tidak ditahan (*released back to pool*), dan soket mentah diserahkan ke *Action Cable Client Connection Manager*.
* Server merespons dengan HTTP Status `101 Switching Protocols`.

### 2. Event Loop & Multiplexing (`nio4r`)
Mengalokasikan satu thread OS untuk setiap soket WebSocket yang diam (*idle*) akan membuat memori server habis dalam sekejap (1.000 thread ≈ 1-2 GB overhead stack frame). Rails memecahkan ini menggunakan gem `nio4r`:
* `nio4r` membungkus syscall kernel performa tinggi: `epoll` di Linux atau `kqueue` di BSD/macOS.
* Satu thread tunggal (atau thread pool kecil pada Action Cable Engine) dapat memantau status ribuan deskriptor file (*file descriptors*) soket.
* Hanya ketika sebuah frame data tiba di salah satu soket, thread *worker pool* Action Cable dialokasikan untuk membaca buffer, mem-parsing frame WebSocket, dan mengeksekusi method channel yang bersangkutan.

### 3. Pub/Sub Multiplexing Architecture
Action Cable memungkinkan satu koneksi fisik WebSocket membawa banyak langganan data (*logical channels*). Proses ini disebut **multiplexing**.
* Klien membuat satu koneksi fisik TCP ke `/cable`.
* Di atas koneksi ini, klien mengirim instruksi JSON: `{"command":"subscribe","identifier":"{\"channel\":\"ChatChannel\",\"room\":\"1\"}"}`.
* Connection manager memetakan request tersebut ke instance `ChatChannel` yang bersesuaian tanpa membuka port koneksi jaringan baru.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Frame Framing Protocol (RFC 6455)
Data yang lewat di atas WebSocket tidak menggunakan chunk HTTP, melainkan frame biner spesifik:
* **FIN Bit (1 bit):** Mengindikasikan apakah ini fragmen akhir dari suatu pesan.
* **Opcode (4 bit):** Menentukan interpretasi payload (misal: `0x1` untuk teks, `0x2` untuk biner, `0x8` untuk *connection close*, `0x9` untuk *ping*, `0xA` untuk *pong*).
* **Masking Key (32 bit):** Semua frame yang dikirim dari klien ke server **wajib** di-masking untuk mencegah *cache poisoning* pada proxy transitif. Server bertugas melakukan unmasking payload bit demi bit menggunakan XOR cipher.

### 2. Action Cable vs Server-Sent Events (SSE)
| Parameter | WebSocket (Action Cable) | Server-Sent Events (SSE / `ActionController::Live`) |
| :--- | :--- | :--- |
| **Arah Komunikasi** | Full-Duplex (Dua arah simultan) | Simplex (Satu arah: Server ke Klien saja) |
| **Protokol** | Protokol WS/WSS independen (berbasis TCP) | HTTP murni (`text/event-stream`) |
| **Dukungan Firewall/Proxy**| Dapat terblokir oleh proxy korporat ketat | Berjalan lancar melalui HTTP/HTTPS standar |
| **Multiplexing** | Native melalui abstraksi Rails Channels | Perlu koneksi HTTP terpisah (kecuali via HTTP/2) |
| **Overhead Klien** | Membutuhkan implementasi client state | Native di browser via API `EventSource` |
| **Resource Footprint** | Menengah-Tinggi (Membutuhkan Worker Event Pool) | Ringan jika di atas HTTP/2 multi-stream |

### 3. State Management & Thread Isolation
Di dalam Controller HTTP tradisional Rails, siklus hidup objek berumur sangat pendek: request masuk, instance controller dibuat, aksi dipanggil, response dikembalikan, GC (Garbage Collector) membersihkan memori.

Dalam Action Cable:
* Objek `ApplicationCable::Connection` hidup selama soket terbuka (bisa berjam-jam atau berhari-hari).
* Objek `Channel` hidup selama user ter-subscribe.
* **PERINGATAN:** Menyimpan state di variabel instance (`@variable`) pada channel berisiko membocorkan state atau menyebabkan *concurrency race condition* jika channel instance menangani multiple frames tanpa sinkronisasi mutex yang ketat. Semua dependensi data harus diambil secara deklaratif atau disimpan pada datastore eksternal (misal: Redis / Solid Cache).

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental end-to-end Action Cable tanpa boilerplate eksternal.

### 1. Konfigurasi Koneksi (`app/channels/application_cable/connection.rb`)
```ruby
module ApplicationCable
  class Connection < ActionCable::Connection::Base
    identified_by :current_user

    def connect
      self.current_user = find_verified_user
      logger.add_tags "ActionCable", "User #{current_user.id}"
    end

    protected

    def find_verified_user
      # Mengambil token terenkripsi dari cookie sesi atau Authorization Header
      if (verified_user = User.find_by(id: cookies.encrypted[:user_id]))
        verified_user
      else
        reject_unauthorized_connection
      end
    end
  end
end
```

### 2. Definisi Channel (`app/channels/system_metric_channel.rb`)
```ruby
class SystemMetricChannel < ApplicationCable::Channel
  def subscribed
    # Memvalidasi izin user sebelum streaming
    if current_user.admin?
      stream_from "system_metrics_channel"
    else
      reject
    end
  end

  def unsubscribed
    # Pembersihan state atau logging saat klien diskonek
    stop_all_streams
  end

  def ping(data)
    # Merespons pesan yang dipicu dari browser klien
    received_timestamp = data.fetch("timestamp")
    transmit({ status: "pong", echo: received_timestamp, server_time: Time.current.to_f })
  end
end
```

### 3. Sisi Klien: JavaScript Native Subscriptions (`app/javascript/channels/system_metric.js`)
```javascript
import { createConsumer } from "@rails/actioncable"

const consumer = createConsumer() // Otomatis terhubung ke default /cable URL

const metricSubscription = consumer.subscriptions.create("SystemMetricChannel", {
  connected() {
    console.log("[WS] Terkoneksi ke SystemMetricChannel");
    this.sendPing();
  },

  disconnected() {
    console.warn("[WS] Sambungan terputus dari SystemMetricChannel");
  },

  received(data) {
    console.log("[WS] Payload diterima dari server:", data);
    const metricContainer = document.getElementById("metrics-display");
    if (metricContainer) {
      metricContainer.innerText = JSON.stringify(data);
    }
  },

  sendPing() {
    // Memanggil aksi public 'ping' pada server Channel
    this.perform("ping", { timestamp: Date.now() });
  }
});
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

Membedah implementasi fundamental di Seksi 07:

### Pada `ApplicationCable::Connection`:
* `identified_by :current_user`: Mendefinisikan *identifier* utama koneksi. Menginstruksikan Action Cable untuk menghasilkan accessor dan menautkan instance koneksi ini ke identifier tersebut. Jika koneksi di-disconnect di kemudian hari, Anda bisa memanggil `ActionCable.server.disconnect(current_user: user)`.
* `self.current_user = find_verified_user`: Titik krusial verifikasi identitas. Jika nil, eksekusi beralih ke:
* `reject_unauthorized_connection`: Menghentikan proses handshake. Server akan segera mengembalikan status HTTP `404 Forbidden` atau langsung menutup socket, memutus upaya koneksi ilegal sebelum memori substansial dialokasikan.
* `cookies.encrypted[:user_id]`: Mengakses cookie secure Rails. Berbeda dengan HTTP controller standar, Action Cable connection tidak memiliki akses langsung ke objek `session` Rails secara utuh pada semua environment tanpa konfigurasi khusus; membaca signed/encrypted cookie adalah mekanisme paling deterministik.

### Pada `SystemMetricChannel`:
* `stream_from "system_metrics_channel"`: Menghubungkan channel internal ini dengan pub/sub broker topic bernama `"system_metrics_channel"`. Setiap kali method broadcast dipanggil pada topic ini di manapun dalam infrastruktur Rails, frame JSON akan didistribusikan ke browser klien ini.
* `reject`: Jika current_user bukan admin, eksekusi pemanggilan ditolak. Klien menerima notifikasi penolakan subscription via protokol internal Action Cable.
* `stop_all_streams`: Menghapus registrasi subscription dari worker pub/sub adapter guna mencegah broadcast dikirim ke soket yang sedang ditutup.
* `transmit(data)`: Mengirim payload **langsung dan privat** hanya ke subscriber pemanggil saat ini (*point-to-point simplex*), tanpa melalui Redis Pub/Sub broadcast global. Berbeda dengan `ActionCable.server.broadcast` yang bersifat global/fanout.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Financial Ticker & Live Order Book Engine
Sebuah platform pertukaran aset keuangan berbasis Rails mengalami degradasi performa akut saat volume transaksi melonjak:
* **Beban Sistem:** 45.000 user memantau instrumen finansial (*order book*) yang sama secara simultan.
* **Gejala Masalah:**
  1. Puma worker thread kehabisan resource (*Thread Starvation*) karena proses broadcast dilakukan di dalam thread siklus HTTP order creation.
  2. Latensi melonjak dari < 50ms menjadi > 4 detik (*Lagging ticks*).
  3. PostgreSQL connection pool kolaps karena ratusan channel mencoba melakukan query `Order.last(10)` secara independen saat ada tick data masuk.
* **Akar Masalah:** Model broadcast naif, di mana komputasi rendering HTML dilakukan berulang kali per klien, digabungkan dengan blocking Redis publish pada thread pemrosesan transaksi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Solusi arsitektur produksi:
1. Pisahkan pemrosesan broadcast ke asynchronous worker yang mem-batch order update.
2. Render payload JSON satu kali, sebarkan ke stream terisolasi.
3. Manfaatkan Turbo Streams via WebSocket untuk efisiensi rendering di browser DOM tanpa JSON parsing manual di JavaScript.

### 1. Definisi Concurrency Config (`config/cable.yml`)
```yaml
production:
  adapter: redis
  url: <%= ENV.fetch("REDIS_CABLE_URL") { "redis://localhost:6379/1" } %>
  channel_prefix: financial_exchange_production
```

### 2. Channel Terisolasi Berdasarkan Market Symbol (`app/channels/order_book_channel.rb`)
```ruby
class OrderBookChannel < ApplicationCable::Channel
  def subscribed
    symbol = params[:market_symbol].to_s.upcase
    
    if valid_market_symbol?(symbol)
      stream_from "order_book:#{symbol}"
    else
      reject
    end
  end

  def unsubscribed
    stop_all_streams
  end

  private

  def valid_market_symbol?(symbol)
    %w[BTC-USD ETH-USD SOL-USD].include?(symbol)
  end
end
```

### 3. Aggregated Broadcast Worker (`app/jobs/order_book_broadcast_job.rb`)
Mencegah *broadcast storming* dengan membatasi frekuensi siaran data agregat (Throttling/Debouncing Pattern):

```ruby
class OrderBookBroadcastJob < ApplicationJob
  queue_as :realtime_broadcasting
  
  # Pastikan background job tidak menumpuk di worker queue
  discard_on ActiveJob::DeserializationError

  def perform(market_symbol)
    # Mengambil aggregated state dari Redis Cache (Memory-to-Memory, NO DB QUERY)
    cache_key = "market_data:#{market_symbol}:snapshot"
    snapshot = Rails.cache.fetch(cache_key, expires_in: 5.seconds) do
      fetch_order_book_snapshot(market_symbol)
    end

    # Render Turbo Stream fragment sekali saja untuk semua client
    rendered_stream = ApplicationController.render(
      turbo_stream: Turbo::StreamsTagBuilder.new(ActionView::Base.empty).replace(
        "order_book_#{market_symbol.downcase}",
        partial: "markets/order_book_table",
        locals: { order_book: snapshot }
      )
    )

    # Sebarkan ke seluruh subscriber yang terhubung ke symbol ini
    ActionCable.server.broadcast("order_book:#{market_symbol}", rendered_stream)
  end

  private

  def fetch_order_book_snapshot(symbol)
    # Query database yang dioptimasi via Read-Replica
    Order.where(symbol: symbol)
         .order(created_at: :desc)
         .limit(25)
         .pluck(:id, :price, :amount, :order_type, :created_at)
  end
end
```

### 4. Client Side Menggunakan Hotwire Turbo Streams (`app/views/markets/show.html.erb`)
```html
<div class="market-container">
  <h1>Live Market: <%= @market_symbol %></h1>
  
  <!-- Membuka WebSocket subscription secara deklaratif melalui Turbo Rails -->
  <%= turbo_stream_from "order_book:#{@market_symbol}", channel: OrderBookChannel %>

  <!-- Wadah ini akan diupdate otomatis oleh Turbo Stream tanpa custom JS -->
  <div id="order_book_<%= @market_symbol.downcase %>">
    <%= render partial: "markets/order_book_table", locals: { order_book: @initial_snapshot } %>
  </div>
</div>
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

```
          Real-Time Architectural Approaches (Trade-Off Triangle)
          
                              LATENSI MINIMAL
                                    /\
                                   /  \
                                  /    \
                                 /  WS  \  (Action Cable / AnyCable)
                                / (Duplex)\
                               /     *     \
                              /             \
                             / SSE           \
                            / (Simplex)       \
                           /                   \
   RESOURCE EFFICIENCY    /---------------------\   COMPATIBILITY &
   (Low Memory & Conns)                             SIMPLICITY (Short Polling)
```

| Kriteria | Standard Action Cable (Puma + Redis) | AnyCable (Go Service + Rails RPC) | Server-Sent Events (SSE via `ActionController::Live`) | Long / Short Polling |
| :--- | :--- | :--- | :--- | :--- |
| **Max Concurrent Sockets** | ~2.000 - 5.000 per Puma node (GVL/Memory bound) | 100.000+ per AnyCable node (Go Goroutines) | Menengah-Tinggi (Tergantung HTTP/2 multiplexing) | Sangat Rendah (Menghabiskan HTTP request pool) |
| **Konsumsi Memori** | Tinggi (~30-50MB per 1000 koneksi) | Sangat Rendah (~2-5MB per 1000 koneksi) | Rendah jika di-stream via I/O murni | Minimal di app, Tinggi di DB |
| **Kompleksitas Operasional** | Rendah (Bawaan Rails, hanya butuh Redis) | Menengah-Tinggi (Butuh Go daemon terpisah & gRPC) | Rendah (Hanya controller Rails biasa) | Paling Rendah (Endpoint standar REST) |
| **Dukungan Dua Arah** | Ya (Full Duplex) | Ya (Full Duplex) | Tidak (Server ke Klien saja) | Pseudo (Lewat request baru berkala) |
| **Use Case Terbaik** | Aplikasi standar dengan <10k concurrent users | Enterprise apps, platform trading, high concurrency | Dashboard analitik internal, sistem notifikasi | Fallback legacy atau koneksi amat jarang |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The ActiveRecord Connection Pool Exhaustion
Jika Anda melakukan panggilan database di dalam channel:
```ruby
# PERANGKAP MAUT
def receive(data)
  user = User.find(data["user_id"]) # Mengambil 1 koneksi pool DB
  user.update!(last_seen: Time.current)
  # Koneksi database ini BISA tertahan jika event loop lambat melepasnya!
end
```
* **Dampak:** Jumlah thread Action Cable default dapat melebihi ukuran `pool:` pada `database.yml`. Sistem akan melempar error `ActiveRecord::ConnectionTimeoutError`.
* **Solusi:** Jalankan operasi database di dalam block eksplisit:
```ruby
def receive(data)
  ActiveRecord::Base.connection_pool.with_connection do
    user = User.find(data["user_id"])
    user.update!(last_seen: Time.current)
  end # Koneksi dikembalikan ke pool seketika block berakhir
end
```

### 2. Thundering Herd Problem saat Deploy / Restart
Ketika server Action Cable di-restart, seluruh 50.000 klien serentak terputus. Klien browser bawaan akan langsung mencoba menyambung ulang (*reconnect*) serempak.
* **Dampak:** CPU load server melonjak drastis ke 100%, autentikasi database down, server crash sebelum koneksi stabil.
* **Mitigasi:** Terapkan **Exponential Backoff dengan Jitter** di sisi Klien. Klien Rails bawaan telah menyertakan mekanisme jitter ini secara otomatis, namun pastikan load balancer (ALB/Nginx) disiapkan untuk menangani lonjakan handshake rate per detik (*rate limit TCP SYN*).

### 3. Load Balancer Timeout (Silent Socket Dropping)
Proxy modern (AWS ALB, Cloudflare, Nginx) secara default menutup koneksi TCP idle yang tidak memiliki transmisi data selama 60 detik.
* **Gejala:** Klien mengira masih terkoneksi, server menganggap klien hilang, socket berstatus *zombie*.
* **Solusi:** Action Cable memancarkan frame **Ping** secara periodik (standar: setiap 3 detik) untuk menjaga koneksi tetap hidup (*keep-alive frame*). Pastikan timeout proxy diset lebih besar dari interval ping Rails:
```nginx
# Konfigurasi Nginx
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;
```

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Melakukan Heavy Computation Langsung di Dalam Channel Method
```ruby
# KESALAHAN FATAL
class ReportChannel < ApplicationCable::Channel
  def generate_csv_report(data)
    # Thread Action Cable Engine terblokir memproses jutaan baris CSV!
    # Ribuan websocket message klien lain akan mengalami lag masif!
    csv = HeavyReporter.generate_giant_csv(data)
    transmit({ report: csv })
  end
end
```
**Perbaikan:** Offload seluruh proses komputasi ke background job (Sidekiq/Solid Queue):
```ruby
# CARA YANG BENAR
class ReportChannel < ApplicationCable::Channel
  def generate_csv_report(data)
    ReportGenerationJob.perform_later(current_user.id, data)
    transmit({ status: "processing", message: "Laporan sedang diproses di background." })
  end
end
```

### 2. Memanggil Broadcast di Dalam Database Transaction
```ruby
# KESALAHAN FATAL
ActiveRecord::Base.transaction do
  order = Order.create!(order_params)
  # Data belum ter-commit di DB!
  ActionCable.server.broadcast("orders", { id: order.id }) 
  raise ActiveRecord::Rollback # Broadcast sudah terlanjur terkirim ke klien!
end
```
**Perbaikan:** Manfaatkan callback `after_commit`:
```ruby
# CARA YANG BENAR
class Order < ApplicationRecord
  after_commit :broadcast_order_created, on: :create

  private

  def broadcast_order_created
    OrderBroadcastJob.perform_later(self.id)
  end
end
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Kanal Bersifat Semantik & Granular:** Jangan menumpuk semua jenis data ke satu channel raksasa `"global_channel"`. Bagilah channel berdasarkan konteks domain: `UserNotificationsChannel`, `InventoryStreamChannel`.
2. **Kirim Payload Minimal:** Jangan menyiarkan seluruh objek Active Record yang di-serialize dengan seluruh atribut database. Kirimkan hanya entitas minimal yang berubah atau kirim representasi HTML fragment (Turbo Streams).
3. **Standarisasi Penggunaan Solid Cable (Rails 8+):** Untuk aplikasi skala kecil hingga menengah yang tidak ingin mengelola kluster Redis terpisah, gunakan `Solid Cable`. Solid Cable memanfaatkan PostgreSQL / SQLite table dengan polling engine yang dioptimasi via thread background mandiri.
4. **Decouple WebSocket Server pada Infrastruktur Berskala Besar:** Pada traffic tinggi, pisahkan node server Puma untuk web/HTTP dengan node server Puma khusus yang hanya menangani WebSocket (`cable` server).

```bash
# Instance HTTP Normal
bundle exec puma -C config/puma.rb

# Instance Khusus WebSocket Cable (cable/config.ru)
bundle exec puma -p 28080 cable/config.ru
```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### 1. Puma Worker & Thread Configuration Tuning
Untuk server khusus Action Cable, rasio thread terhadap worker harus berbeda drastis dengan server web biasa. Karena I/O multiplexing:

```ruby
# config/puma_cable.rb
workers 2
# Action Cable membutuhkan pool thread lebih tinggi untuk menangani concurrent I/O dispatch
threads_count = ENV.fetch("RAILS_MAX_THREADS") { 32 }
threads threads_count, threads_count

port ENV.fetch("PORT") { 28080 }
environment ENV.fetch("RAILS_ENV") { "production" }
```

### 2. Redis Connection Pooling & Multiplexing
Di dalam `config/cable.yml`, konfigurasikan ukuran pool Redis secara eksplisit agar seimbang dengan Puma threads:

```yaml
production:
  adapter: redis
  url: <%= ENV.fetch("REDIS_CABLE_URL") %>
  channel_prefix: app_production
  # Pastikan connection pool mencukupi
  pool: 50
```

### 3. Mengurangi Overhead Objek Alokasi (Garbage Collection Pressure)
Di balik layar, Action Cable mengonversi data ke JSON string via `ActiveSupport::JSON`. Dalam volume siaran tinggi (misal: 10.000 siaran/detik):
* Gunakan fast JSON serializers seperti `oj` (`gem 'oj'`) untuk memangkas alokasi memory heap sebesar 40%.
* Aktifkan pre-serialization: jika menyiarkan payload yang sama ke 5.000 subscriber yang tersebar di kanal berbeda, serialize string JSON **satu kali saja**, lalu broadcast raw string tersebut.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Mitigasi Cross-Site WebSocket Hijacking (CSWSH)
WebSocket handshake tidak dilindungi secara native oleh browser via *Same-Origin Policy* (SOP). Skrip berbahaya dari situs `attacker.com` dapat membuka koneksi WebSocket langsung ke `your-bank.com/cable` menggunakan kredensial cookie user yang aktif.

Rails secara default memverifikasi origin header. Jangan pernah mendisable fitur ini di produksi:
```ruby
# config/environments/production.rb
# JANGAN PERNAH: config.action_cable.disable_request_forgery_protection = true

# LAKUKAN INI:
config.action_cable.allowed_request_origins = [
  "https://platform.bank-app.com",
  /https:\/\/.*\.bank-app\.com/
]
```

### 2. Channel Authorization Scoping
Jangan biarkan user menentukan ID langganan mereka tanpa verifikasi kepemilikan di method `subscribed`:

```ruby
class PrivateInvoiceChannel < ApplicationCable::Channel
  def subscribed
    invoice = Invoice.find_by(id: params[:invoice_id])
    
    # VALIDASI KETAT
    if invoice && invoice.user_id == current_user.id
      stream_for invoice # Menggunakan scoped namespacing otomatis
    else
      reject
    end
  end
end
```

### 3. Rate Limiting Inbound WebSocket Frames
WebSocket tidak melewati Rack Attack middleware biasa setelah handshake selesai. Lindungi method Action Cable dari abuse/spam:

```ruby
class ChatRoomChannel < ApplicationCable::Channel
  def speak(data)
    rate_key = "rate_limit:cable:#{current_user.id}"
    current_count = Rails.cache.increment(rate_key, 1, expires_in: 1.minute)

    if current_count > 60
      transmit({ error: "Rate limit exceeded. Maksimal 60 pesan per menit." })
      return
    end

    Message.create!(content: data["message"], user: current_user)
  end
end
```

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Action Cable terintegrasi penuh dengan event notification system Rails (`ActiveSupport::Notifications`).

### 1. Setup Subscription Tracing (`config/initializers/action_cable_metrics.rb`)
```ruby
ActiveSupport::Notifications.subscribe("transmit.action_cable") do |name, start, finish, id, payload|
  duration = (finish - start) * 1000 # dalam milidetik
  channel = payload[:channel_class]
  
  if duration > 100.0 # Log transmisi yang lambat
    Rails.logger.warn("[ActionCable Slow Transmit] Channel: #{channel} - Latensi: #{duration.round(2)}ms")
  end
end

ActiveSupport::Notifications.subscribe("broadcast.action_cable") do |name, start, finish, id, payload|
  broadcasting = payload[:broadcasting]
  coder = payload[:coder]
  StatsD.increment("action_cable.broadcasts", tags: ["stream:#{broadcasting}"])
end
```

### 2. Structured Debugging & Logging
Sesuaikan konfigurasi logger Action Cable di level Connection:

```ruby
module ApplicationCable
  class Connection < ActionCable::Connection::Base
    identified_by :current_user

    def connect
      self.current_user = find_verified_user
      # Tambahkan tag UUID connection untuk penelusuran log terdistribusi
      logger.add_tags(
        "ActionCable",
        "User:#{current_user.id}",
        "ConnID:#{SecureRandom.hex(4)}"
      )
      logger.info "WebSocket Handshake Terverifikasi."
    end
  end
end
```

### 3. Menginspeksi Status Connection via Rails Console
```ruby
# Memeriksa jumlah thread subscriber yang sedang berjalan pada adapter
ActionCable.server.pubsub.send(:redis_connection).info

# Melakukan broadcast uji coba langsung dari console
ActionCable.server.broadcast("order_book:BTC-USD", { test: "ping" })
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

### Action Cable DSL Reference
* `identified_by :attr`: Mendefinisikan ID koneksi (biasanya `current_user`).
* `reject_unauthorized_connection`: Membatalkan WebSocket upgrade handshake pada layer koneksi.
* `stream_from "topic_name"`: Subscribe ke pub/sub stream string mentah.
* `stream_for model_instance`: Subscribe ke stream scoped khusus model (Format: `model_name:model_id`).
* `stop_all_streams`: Menghapus semua subscription socket tersebut.
* `transmit(hash)`: Mengirim payload langsung ke klien pemilik channel saat ini.
* `ActionCable.server.broadcast("topic", payload)`: Menyiarkan payload global ke seluruh server yang mendengarkan topic tersebut.
* `Model.broadcast_replace_to(...)`: Helper Rails Turbo Stream untuk merender dan menyiarkan perubahan fragment DOM ke target stream.

### File Configuration Locations
* `config/cable.yml`: Pengaturan adapter (async, redis, solid_cable, test).
* `app/channels/application_cable/connection.rb`: Autentikasi dan identifikasi soket awal.
* `app/channels/application_cable/channel.rb`: Base channel class untuk logic reusable.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Tingkat Basic

1. **Apa fungsi utama dari pemanggilan `reject_unauthorized_connection` di `ApplicationCable::Connection`?**
   * A. Menolak pesan chat yang dikirim oleh klien.
   * B. Menghentikan proses handshake WebSocket dan menolak koneksi sebelum dialokasikan.
   * C. Menghapus koneksi dari Redis database.
   * D. Merestart Puma worker.
   * *Jawaban:* **B**. Metode ini segera membatalkan handshake HTTP Upgrade, mencegah klien yang tidak terotentikasi membuka soket TCP persisten.

2. **Protokol status HTTP manakah yang menandakan peralihan protokol berhasil dari HTTP ke WebSocket?**
   * A. 200 OK
   * B. 301 Moved Permanently
   * C. 101 Switching Protocols
   * D. 426 Upgrade Required
   * *Jawaban:* **C**. HTTP status 101 Switching Protocols adalah konfirmasi standar dari server bahwa koneksi ditingkatkan ke layer WebSocket via header `Upgrade: websocket`.

3. **Di lingkungan production, mengapa adapter `async` pada `config/cable.yml` TIDAK boleh digunakan pada arsitektur multi-server?**
   * A. Karena adapter async menyebabkan memory leak pada Ruby.
   * B. Karena adapter async hanya berjalan di dalam memory proses Puma lokal, sehingga broadcast dari server A tidak akan pernah sampai ke klien yang tersambung di server B.
   * C. Karena adapter async tidak mendukung SSL/TLS.
   * D. Karena adapter async dibatasi hanya untuk 10 koneksi.
   * *Jawaban:* **B**. Adapter `async` beroperasi secara in-memory dalam proses Ruby tunggal. Sistem multi-server atau multi-process Puma membutuhkan broker eksternal (seperti Redis atau Solid Cable) agar event dapat disebarkan secara terpusat (*fan-out*).

4. **Apa perbedaan antara `transmit` dan `ActionCable.server.broadcast` di dalam sebuah Channel?**
   * A. `transmit` mengirim data hanya ke klien pemilik channel tersebut, sedangkan `broadcast` menyiarkan data ke seluruh subscriber topik di semua proses.
   * B. `transmit` menggunakan format biner, sedangkan `broadcast` menggunakan JSON.
   * C. `transmit` bersifat asynchronous, sedangkan `broadcast` synchronous.
   * D. Tidak ada perbedaan, keduanya alias.
   * *Jawaban:* **A**. `transmit` bersifat point-to-point menuju soket spesifik pemanggil aksi, sedangkan `broadcast` mempublikasikan pesan ke adapter Pub/Sub untuk di-fanout ke semua klien yang terdaftar.

5. **Apa fungsi dari bit masking pada frame WebSocket dari klien ke server berdasarkan RFC 6455?**
   * A. Mengompresi payload frame.
   * B. Mencegah serangan *cache poisoning* pada intermediate proxy yang berpotensi salah menginterpretasikan payload WebSocket sebagai request HTTP.
   * C. Mengenkripsi payload dari serangan Man-in-the-Middle tanpa butuh SSL.
   * D. Memvalidasi token JWT pengguna.
   * *Jawaban:* **B**. Masking key 32-bit mencegah intermediate cache menyimpan frame payload berbahaya yang dapat dieksploitasi untuk merusak stream HTTP proxy lain.

---

### Soal Tingkat Intermediate

6. **Mengapa pemanggilan method blocking Active Record yang lambat di dalam action Channel dapat mendegradasi performa Action Cable secara drastis?**
   * A. Karena Active Record mengunci GIL secara permanen.
   * B. Karena Action Cable worker pool memiliki kapasitas thread yang terbatas untuk mengeksekusi frame; jika tertahan operasi I/O DB, eksekusi frame klien lain akan mengantre dan menaikkan latensi.
   * C. Karena Action Cable tidak mendukung database SQL.
   * D. Karena koneksi WebSocket akan otomatis terputus jika query berjalan lebih dari 10 milidetik.
   * *Jawaban:* **B**. Thread pool Action Cable ditugaskan untuk mengeksekusi pesan masuk secara cepat. Operasi lambat/blocking di channel menghabiskan thread pool, memicu kemacetan (*starvation*) pemrosesan pesan untuk seluruh koneksi lainnya.

7. **Perhatikan kode berikut. Apa risiko tersembunyi yang ada?**
   ```ruby
   class ChatChannel < ApplicationCable::Channel
     def subscribed
       @chat_room = ChatRoom.find(params[:room_id])
       stream_for @chat_room
     end

     def post_message(data)
       @chat_room.messages.create!(content: data["body"], user: current_user)
     end
   end
   ```
   * A. Objek `@chat_room` dapat berubah status atau menjadi *stale* karena channel instance bertahan lama, dan tidak aman terhadap *cross-thread access* jika framework mengoptimasi reuse instance.
   * B. Sintaks `stream_for` salah.
   * C. `params[:room_id]` tidak bisa dibaca di method `subscribed`.
   * D. `post_message` tidak bisa menerima argumen.
   * *Jawaban:* **A**. Menyimpan instance Active Record pada state instance channel (`@chat_room`) berbahaya jika koneksi hidup dalam hitungan hari. Data DB dapat berubah, terhapus, atau memicu memory leak karena memegang referensi objek AR terlalu lama. Sebaiknya query ulang atau delegasikan ke background job/service object.

8. **Bagaimana mekanisme Rack Socket Hijacking (`rack.hijack`) bekerja di level arsitektur Puma dan Action Cable?**
   * A. Puma mengabaikan request dan melempar error 500.
   * B. Action Cable mengambil alih IO stream mentah dari Puma web server, memutus daur hidup request-response Puma standar, lalu mendaftarkan file descriptor soket tersebut ke event loop `nio4r`.
   * C. Puma membuat thread baru khusus untuk setiap frame WebSocket.
   * D. Soket dialihkan langsung dari OS kernel ke background worker tanpa melewati web server.
   * *Jawaban:* **B**. Rack Hijack memungkinkan aplikasi mengambil alih stream IO soket secara penuh dari web server, membebaskan server dari keharusan mereturn standard Rack response array `[status, headers, body]`.

9. **Ketika merancang broadcast pada aplikasi bertraffic sangat tinggi, mengapa pendekatan Turbo Streams over WebSocket lebih diutamakan daripada mengirim JSON mentah yang diproses frontend JavaScript?**
   * A. Turbo Streams selalu lebih cepat dari JSON serializer murni dalam satuan milidetik CPU.
   * B. Turbo Streams menghilangkan kompleksitas *client-side state management* dan parsing DOM manual di browser dengan mengirimkan fragment HTML yang dieksekusi secara deklaratif.
   * C. Turbo Streams tidak membutuhkan koneksi TCP.
   * D. WebSocket tidak mendukung format JSON.
   * *Jawaban:* **B**. Turbo Streams memungkinkan server menjadi Single Source of Truth; server merender template partial HTML secara efisien sekali via fragment cache, lalu Turbo di browser secara instan mengganti/menambahkan node DOM tanpa boilerplate routing dan rendering JSON di client framework.

10. **Apa strategi paling efektif untuk menangani 'Thundering Herd Problem' pada server WebSocket saat infrastruktur Rails melakukan rolling deployment?**
    * A. Mematikan fitur reconnect pada JavaScript client.
    * B. Mengalokasikan 100 Puma worker tambahan secara temporer.
    * C. Menerapkan rekoneksi dengan algoritma Exponential Backoff ditambah random Jitter pada client, serta membatasi rate limit TCP handshake di level Load Balancer.
    * D. Mengganti protokol WebSocket dengan Long Polling permanen.
    * *Jawaban:* **C**. Exponential backoff dengan jitter menyebarkan upaya re-koneksi klien secara acak seiring waktu, memecah lonjakan koneksi serempak yang berpotensi merubuhkan load balancer dan pool autentikasi aplikasi Rails.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Mini Project: Real-Time Multi-Tenant Incident War Room

Bangun sistem pemantauan insiden produksi (*Production Incident War Room*) dengan spesifikasi teknis tingkat lanjut berikut:

#### 1. Persyaratan Fungsional
1. **Live Incident Metrics Gauge:** Sebuah halaman dashboard menampilkan meteran real-time metrik CPU & Error Rate. Nilai ini di-push oleh server setiap 2 detik menggunakan background scheduler.
2. **War Room Chat & Action Logs:** Ruang chat terenkripsi per insiden di mana engineer dapat bertukar pesan real-time. Ketika sebuah action diambil (misal: tombol "Rollback Deployment" diklik), action tersebut memicu siaran event ke seluruh engineer di room tersebut tanpa me-refresh halaman.
3. **Presence Indicators:** Tampilkan avatar engineer yang saat ini sedang aktif membuka halaman War Room tersebut (Online/Offline status).

#### 2. Kriteria Teknis Wajib
* **Backend:** Ruby on Rails 7.1+ / 8.0, Action Cable, Solid Cable atau Redis adapter.
* **Frontend:** Hotwire (Turbo Streams over WebSockets) + Stimulus JS untuk state visual.
* **Zero DB Saturation:** Operasi push metrik tidak boleh melakukan eksekusi query agregasi langsung ke DB utama di thread Action Cable; gunakan cache atau aggregate table.
* **Security Scoping:** Pastikan otorisasi channel ketat: Klien dari Tenant A tidak boleh dapat menyadap atau meng-inject frame ke War Room Tenant B (`IncidentWarRoomChannel`).
* **Resilience:** Buat custom Stimulus controller yang menangani status indikator diskoneksi: Jika koneksi internet terputus, tampilkan banner merah *"Mencoba menyambung ulang..."* dengan visualisasi status ping.

#### 3. Skenario Pengujian Beban
Gunakan script Ruby sederhana berbasis gem `faye-websocket` atau alat bantu benchmark WebSocket (misal: `k6` atau `tsung`) untuk membuka minimal 500 koneksi simultan ke War Room tersebut, dan lakukan observasi terhadap:
* Konsumsi RAM server Puma.
* Utilisasi connection pool database.
* Latensi penerimaan frame saat sebuah event dibroadcast.