# SEKSI 01 — IDENTITAS MODUL

* **Mata Pelajaran / Jalur Keahlian:** Ruby on Rails Core Architecture (`02-Programming-Languages`)
* **Nomor & Nama Modul:** Bab 05 Module 01 — Asynchronous Processing & Background Jobs
* **Level Kemahiran:** Advanced / Production-Grade
* **Prasyarat Pengetahuan:** 
  * Arsitektur Threading & Process Model Ruby (GVL, MRI concurrency).
  * Siklus Hidup Request-Response Rack/Rails dan Puma Web Server.
  * Dasar-dasar Active Record (Transactions, Callbacks, Connection Pooling).
  * Struktur data in-memory Redis (Strings, Lists, Sorted Sets, Hashes).
* **Estimasi Waktu Penyelesaian:** 120–180 Menit

---

# SEKSI 02 — LEARNING OBJECTIVES

1. **Menganalisis dan Memilih Engine Background Job:** Mengidentifikasi karakteristik performa, batas konkurensi, dan trade-off operasional antara *Redis-backed* (Sidekiq) dan *Database-backed* (Solid Queue/GoodJob).
2. **Menguasai Mekanisme Serialisasi Active Job:** Menjelaskan alur internal GlobalID dalam mengubah objek Active Record menjadi payload JSON serializable dan merekonstruksinya secara aman di layer worker.
3. **Mengimplementasikan Idempotensi Tingkat Produksi:** Merancang job yang tahan terhadap kegagalan jaringan, pengulangan eksekusi (*at-least-once delivery*), dan *poison pills* menggunakan *idempotency keys* berbasis distributed lock (Redis/DB).
4. **Mengeliminasi Race Condition Transaksional:** Mengidentifikasi dan memitigasi bahaya *database transaction boundary issues* dengan memanfaatkan *lifecycle callback* `after_commit`.
5. **Mengoptimalkan Alokasi Sumber Daya:** Menghitung dan mengonfigurasi rasio *Database Connection Pool* terhadap konkurensi Puma thread dan Sidekiq concurrency secara presisi untuk menghindari *connection starvation*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Siklus hidup HTTP web standar bersifat *synchronous*: koneksi dibuka, thread Puma dialokasikan, query database dijalankan, payload dirender, dan response dikirim sebelum thread dilepaskan kembali ke *pool*. Batas waktu toleransi manusia berada pada kisaran 200–500 milidetik. Segala operasi yang melibatkan I/O eksternal (SMTP, API pihak ketiga, agregasi data masif, *image processing*) tidak boleh dieksekusi di dalam thread HTTP web.

```
Synchronous (Anti-Pattern untuk Long-Running Tasks):
Client ----[ HTTP Request ]---> Puma Thread ----[ Call Stripe API (2.4s) ]----> Puma Thread Freezes
Client <---[ HTTP 200 OK ]------ (Total latency: 2.5s) ----------------------- Bottleneck!

Asynchronous (Decoupled Mental Model):
Client ----[ HTTP Request ]---> Puma Thread ----[ Enqueue Job to Queue (3ms) ]
Client <---[ HTTP 202 Accepted ] Puma Thread Free
                                      |
                             Queue Storage (Redis/DB)
                                      |
Worker Process (Sidekiq) <------- Pull Job ----- (Runs in background, decoupled)
```

Mental model yang harus ditanamkan:
* **The Web Layer is an Ingestion Layer:** Tanggung jawab server web hanyalah memvalidasi payload, mencatat intensi ke media persistensi, mengantrekan (*enqueue*) pesan, dan segera membalas klien.
* **Workers are Disconnected Consumers:** Worker berjalan pada proses sistem operasi yang terpisah, thread yang berbeda, bahkan sering kali pada server fisik/mesin virtual yang terisolasi total dari server web. Jangan pernah mengasumsikan *state* in-memory dari web server terbawa ke worker.
* **At-Least-Once Delivery Reality:** Tidak ada jaminan jaringan yang memastikan sebuah job hanya dieksekusi tepat satu kali. Asumsikan setiap background job bisa dijalankan dua atau tiga kali akibat timeout jaringan atau restart proses worker.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Alur eksekusi job asynchronous dari Rails Web Layer hingga Worker Process melewati beberapa lapisan boundary:

```
+-----------------------------------------------------------------------------+
|                               RAILS WEB PROCESS                             |
|                                                                             |
|  [ Controller ]                                                             |
|         |                                                                   |
|         v                                                                   |
|  Order.create! ---> [ Model Callback ]                                      |
|                            | (after_commit)                                 |
|                            v                                                |
|                 OrderProcessingJob.perform_later(order)                     |
|                            |                                                |
|                            v                                                |
|                 [ ActiveJob Engine ]                                        |
|                 (Serializes via GlobalID: gid://app/Order/42)               |
+----------------------------|------------------------------------------------+
                             |
                             v Push (LPUSH / ZADD)
+-----------------------------------------------------------------------------+
|                           PERSISTENT QUEUE (REDIS)                          |
|                                                                             |
|   queue:default        [ { "class": "Sidekiq::Job", "args": [...] } ]       |
|   schedule (SortedSet) [ (timestamp_epoch, { "class": "...", ... }) ]       |
+----------------------------|------------------------------------------------+
                             |
                             | Pop (BRPOP) / Poll
                             v
+-----------------------------------------------------------------------------+
|                          SIDEKIQ WORKER PROCESS                             |
|                                                                             |
|   [ Fetcher Thread ]                                                        |
|           |                                                                 |
|           v                                                                 |
|   [ Sidekiq Thread Pool ] (e.g., Concurrency = 10)                          |
|           |                                                                 |
|           v                                                                 |
|   ActiveJob Adapter Deserialization (GlobalID.find -> Order.find(42))       |
|           |                                                                 |
|           +---> Success: Acknowledge & terminate execution                  |
|           |                                                                 |
|           +---> Transient Error: Push to 'retry' Sorted Set (Exponential)   |
|           |                                                                 |
|           +---> Fatal/Max Retries: Move to DeadSet (Dead Letter Queue)      |
+-----------------------------------------------------------------------------+
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Active Job Serialization & GlobalID
Ketika memanggil `perform_later(record)`, Active Job tidak menduplikasi seluruh *in-memory object* ke dalam antrean. Rails menggunakan URI standar bernama **GlobalID**.

Objek `order = Order.find(42)` diserialisasi menjadi string:
`gid://production-app/Order/42`

Struktur payload JSON internal yang dikirim ke Redis:
```json
{
  "job_class": "OrderProcessingJob",
  "job_id": "4b68eef0-8339-44d5-8eb0-bbfa11438dd8",
  "provider_job_id": null,
  "queue_name": "critical",
  "priority": null,
  "arguments": [
    {
      "_aj_globalid": "gid://production-app/Order/42"
    }
  ],
  "executions": 0,
  "exception_executions": {},
  "locale": "en",
  "timezone": "UTC",
  "enqueued_at": "2026-03-31T08:12:00.123456Z"
}
```

### 2. Mekanisme Antrean Redis pada Sidekiq
Sidekiq memetakan antrean menggunakan struktur data primitif Redis:
* **Immediate Jobs (`queue:name`):** Menggunakan Redis **List**. Server web memanggil `LPUSH queue:default <payload>`, dan worker Sidekiq menunggu pesan baru menggunakan perintah blocking `BRPOP queue:default <timeout>` yang efisien tanpa *busy-waiting*.
* **Scheduled / Retry Jobs (`schedule` / `retry`):** Menggunakan Redis **Sorted Set (ZSET)**. Nilai *score* adalah epoch timestamp UNIX (`time.now.to_f + delay`). Thread internal Sidekiq, yaitu `Scheduled::Poller`, secara berkala (default ~5-15 detik) mengeksekusi query:
  ```redis
  ZRANGEBYSCORE retry -inf <current_timestamp> LIMIT 0 100
  ```
  Item yang waktunya telah tiba akan dipindahkan secara atomik dari ZSET ke target List (`LPUSH queue:default`) via Lua script.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI

### 1. Ruby Concurrency, GVL, dan Worker Footprint
Sidekiq menggunakan multithreading berbasis library `Concurrent::Ruby` di atas satu proses Ruby VM. Namun, MRI Ruby memiliki **GVL (Global VM Lock)**:
* Hanya satu thread Ruby yang dapat mengeksekusi bytecode Ruby pada satu waktu.
* GVL **dilepaskan** saat thread melakukan I/O blocking (misalnya: query database via Postgres adapter, HTTP call ke gateway eksternal, pembacaan file dari disk, dan `sleep`).
* Oleh karena itu, background worker sangat diuntungkan oleh threading jika tugasnya didominasi *I/O-bound*. Sebaliknya, jika job melakukan tugas *CPU-bound* (kompresi video, kalkulasi kriptografi murni), peningkatan konkurensi thread tidak meningkatkan *throughput*, melainkan hanya memicu context switching overhead.

### 2. At-Least-Once Delivery & Idempotency
Dalam arsitektur terdistribusi, terdapat tiga model pengiriman:
1. *At-most-once*: Pesan dikirim sekali, jika gagal, hilang selamanya.
2. *Exactly-once*: Secara matematis hampir mustahil dicapai di level protokol transport tanpa koordinasi two-phase commit yang memakan latensi masif.
3. *At-least-once*: Pendekatan standar Sidekiq/ActiveJob. Jika worker crash sesaat setelah mengeksekusi job tetapi sebelum memproses acknowledgement ke antrean, Redis/Sidekiq akan menjadwalkan ulang job tersebut.

**Konsekuensi Logis:** Seluruh kode background job **wajib idempotent**.
$$\forall x, \quad f(f(x)) = f(x)$$
Mengeksekusi job yang sama sebanyak 1 kali atau 100 kali harus menghasilkan *state* akhir sistem yang sama persis tanpa efek samping tambahan (seperti penagihan ganda pada kartu kredit).

### 3. Backoff Strategy (Exponential Backoff & Jitter)
Jika API pihak ketiga *down*, membanjiri mereka dengan retry setiap detik akan memperburuk situasi (*thundering herd problem*). Formula default Sidekiq menggunakan eksponensial ditambah angka acak (*jitter*):
$$\text{delay} = (\text{retry\_count}^4) + 15 + (\text{rand}(30) \times (\text{retry\_count} + 1))$$

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah konfigurasi dan implementasi dasar background job menggunakan Rails Active Job dengan adapter Sidekiq.

### 1. Gemfile Setup
```ruby
# Gemfile
gem "sidekiq", "~> 7.2"
gem "redis", "~> 5.1"
```

### 2. Konfigurasi Adapter Rails
```ruby
# config/application.rb
module CoreApplication
  class Application < Rails::Application
    # Mengarahkan layer Active Job untuk mengeksekusi antrean via Sidekiq
    config.active_job.queue_adapter = :sidekiq
  end
end
```

### 3. Konfigurasi Client & Server Sidekiq
```ruby
# config/initializers/sidekiq.rb
Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0") }
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0") }
end
```

### 4. Definisi Job Dasar
```ruby
# app/jobs/welcome_notification_job.rb
class WelcomeNotificationJob < ApplicationJob
  queue_as :default

  # Batasan maksimal percobaan otomatis
  retry_on Net::OpenTimeout, Timeout::Error, wait: :exponentially_longer, attempts: 5
  discard_on ActiveRecord::RecordNotFound

  def perform(user_id)
    user = User.find(user_id)
    UserMailer.welcome(user).deliver_now
  end
end
```

### 5. Enqueue dari Controller / Model
```ruby
# app/models/user.rb
class User < ApplicationRecord
  after_commit :send_welcome_email, on: :create

  private

  def send_welcome_email
    # Enqueue payload ke Redis via ActiveJob
    WelcomeNotificationJob.perform_later(self.id)
  end
end
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis File `app/jobs/welcome_notification_job.rb`:

* `class WelcomeNotificationJob < ApplicationJob`
  * Mewarisi sifat dasar `ActiveJob::Base` yang mengabstraksi komunikasi antrean, logging terpadu, dan manajemen error.
* `queue_as :default`
  * Menentukan partisi antrean (*queue*) di Redis tempat job ini disimpan. Sidekiq dapat diatur untuk memprioritaskan antrean tertentu dibanding antrean ini.
* `retry_on Net::OpenTimeout, Timeout::Error, wait: :exponentially_longer, attempts: 5`
  * Deklarasi penanganan error tingkat abstraksi Rails. Jika blok `perform` melempar `Net::OpenTimeout`, eksekusi dihentikan tanpa membunuh worker thread. Rails menjadwalkan ulang job tersebut ke dalam ZSET Redis dengan kalkulasi jeda eksponensial sebanyak maksimal 5 kali.
* `discard_on ActiveRecord::RecordNotFound`
  * Mencegah *poison pill*. Jika sebuah record dihapus sebelum job dieksekusi, job tidak akan diulang terus-menerus hingga masuk ke Dead Letter Queue, melainkan langsung dibuang secara terkendali.
* `def perform(user_id)`
  * Entry point eksekusi logic saat worker thread mengambil job dari antrean.
* `user = User.find(user_id)`
  * Rekonstruksi model menggunakan primitive ID, bukan mengoper objek `User` utuh ke dalam parameter enqueue.
* `UserMailer.welcome(user).deliver_now`
  * Mengirim email secara synchronous di dalam context worker thread (karena pemanggilan worker itu sendiri sudah bersifat asynchronous terhadap web server).

### Analisis File `app/models/user.rb`:

* `after_commit :send_welcome_email, on: :create`
  * Menggunakan callback `after_commit`, **bukan** `after_create`. Ini menjamin transaksi basis data PostgreSQL/MySQL telah di-*commit* ke disk sepenuhnya sebelum pesan di-push ke Redis.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario:
Sistem E-Commerce memproses transaksi Flash Sale massal. Ketika checkout selesai:
1. Invoice PDF berukuran besar (15–30 MB) harus di-generate.
2. Webhook notifikasi pembayaran harus dikirim ke sistem ERP inventori pihak ketiga yang memiliki rate limit ketat: **maksimal 5 request per detik** (HTTP 429 jika melebihi batas).
3. Dana pelanggan harus dicatat, dan email invoice dikirimkan.

### Masalah yang Sering Terjadi:
* Server web mengalami bottleneck jika PDF di-generate di thread web.
* API eksternal ERP memblokir IP server Rails karena terkena *rate limit throttling*.
* Jika server worker restart di tengah-tengah pembuatan PDF dan pengiriman webhook, terjadi pengiriman tagihan duplikat ke pelanggan (*double charging/notification*).

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON CODE

Solusi menyeluruh menggunakan Sidekiq Native Worker, Redis Distributed Token Bucket/Locking, Idempotency tracking, dan error handling khusus.

```ruby
# app/services/redis_rate_limiter.rb
class RedisRateLimiter
  def self.throttle!(key, limit: 5, period: 1)
    redis = Sidekiq.redis { |conn| conn }
    current_time = Time.now.to_f
    clear_before = current_time - period

    # Algoritma Sliding Window Menggunakan Redis ZSET
    result = redis.multi do |multi|
      multi.zremrangebyscore(key, "-inf", clear_before)
      multi.zcard(key)
      multi.zadd(key, current_time, "#{current_time}-#{SecureRandom.hex(4)}")
      multi.expire(key, period + 1)
    end

    current_requests = result[1]
    if current_requests >= limit
      raise RateLimitExceededError, "Rate limit exceeded for key: #{key}"
    end
  end
end

class RateLimitExceededError < StandardError; end
```

```ruby
# app/workers/process_order_checkout_worker.rb
class ProcessOrderCheckoutWorker
  include Sidekiq::Job

  # Konfigurasi spesifik Sidekiq
  sidekiq_options queue: :critical, 
                  retry: 5, 
                  backtrace: true

  # Custom backoff logic
  sidekiq_retry_in do |count, exception|
    case exception
    when RateLimitExceededError
      # Tunggu 2 detik secara linear jika terbentur rate limit
      2 + (count * 2)
    else
      # Eksponensial default untuk transient network errors
      (count ** 4) + 15
    end
  end

  def perform(order_id, idempotency_key)
    # 1. Database Lock & Idempotency Check
    order = Order.find(order_id)
    
    # Memastikan tidak terjadi double execution
    return if already_processed?(idempotency_key)

    # 2. Redis Distributed Rate Limiting untuk eksternal API
    RedisRateLimiter.throttle!("erp_api_rate_limit", limit: 5, period: 1)

    # 3. Transaksi Internal untuk Eksekusi dan Audit Trail
    ActiveRecord::Base.transaction do
      # Set status pemrosesan
      order.lock! # Pessimistic locking baris database
      return if order.processed?

      # Generasi Invoice PDF (I/O & CPU intensif)
      pdf_url = InvoiceGeneratorService.new(order).generate_and_upload!

      # Integrasi Third Party (ERP Sync)
      ErpSyncService.new(order, pdf_url).broadcast!

      # Update status Order dan simpan Idempotency Key
      order.update!(
        status: :processed,
        invoice_url: pdf_url,
        processed_at: Time.current
      )

      # Mark idempotency key sebagai selesai dengan TTL 24 jam
      mark_processed(idempotency_key)
    end

    # 4. Enqueue follow-up job untuk notifikasi email
    SendInvoiceEmailWorker.perform_async(order.id)

  rescue RateLimitExceededError => e
    # Log warning dan trigger retry mekanisme Sidekiq
    Sidekiq.logger.warn("Throttled by external ERP for Order ##{order_id}. Retrying... Err: #{e.message}")
    raise e
  rescue ActiveRecord::RecordNotFound => e
    Sidekiq.logger.error("Non-recoverable error: Order ##{order_id} not found. Aborting job.")
    # Tidak me-raise ulang error agar job tidak di-retry (poison pill prevention)
  end

  private

  def already_processed?(key)
    Sidekiq.redis { |r| r.exists?("idempotency:#{key}") }
  end

  def mark_processed(key)
    Sidekiq.redis { |r| r.set("idempotency:#{key}", "COMPLETED", ex: 86_400) }
  end
end
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN

Memilih arsitektur background job memerlukan pemahaman komparatif menyeluruh:

| Fitur / Parameter | **Sidekiq (Redis-backed)** | **Solid Queue (Database-backed)** | **GoodJob (Postgres-only)** |
| :--- | :--- | :--- | :--- |
| **Penyimpanan State** | Redis (RAM / In-Memory) | Relational DB (MySQL, Postgres via ACID)| Relational DB (Postgres via LISTEN/NOTIFY) |
| **Throughput / Latency** | Ekstrem Tinggi (Up to 10k+ ops/sec) | Sedang - Tinggi (Terbatas pada I/O disk DB)| Tinggi untuk PG ecosystem |
| **Konsumsi Memori** | Membutuhkan RAM tambahan untuk server Redis | Membebaskan RAM, memanfaatkan DB pool | Terintegrasi dengan DB pool |
| **Transaction Boundary Safety** | Rentan Race Condition jika salah callback | Mendukung *Transactional Outbox Pattern* | Mendukung *Transactional Outbox Pattern* |
| **Kompleksitas Operasional** | Menambah 1 infrastruktur dependensi (Redis cluster)| Nol dependensi tambahan selain DB | Nol dependensi tambahan selain DB |
| **Lisensi / Fitur Pro** | Dual License (Fitur lanjutan butuh Sidekiq Pro/Enterprise) | 100% Open Source (Official Rails 8 stack)| 100% Open Source |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The "RecordNotFound" Race Condition
* **Gejala:** Job gagal dieksekusi dengan error `ActiveRecord::RecordNotFound` sesaat setelah objek dibuat di controller.
* **Akar Masalah:** Developer memanggil `perform_later` di dalam blok `after_create` atau `after_save`. Callback ini berjalan **di dalam blok transaksi SQL** sebelum perintah `COMMIT` selesai dikirim ke database engine. Worker di thread lain membaca Redis lebih cepat daripada durasi database engine menulis transaksi ke disk.

```ruby
# ANTI-PATTERN:
class Order < ApplicationRecord
  after_create :process_order # Transaction masih OPEN di DB

  def process_order
    OrderProcessingJob.perform_later(self.id) # Worker langsung fetch, DB belum commit -> 404!
  end
end

# BEST PRACTICE:
class Order < ApplicationRecord
  after_commit :process_order, on: :create # Transaction sudah COMMIT
  
  def process_order
    OrderProcessingJob.perform_later(self.id)
  end
end
```

### 2. Redis Out-Of-Memory (OOM) Melalui Poison Pills
* **Gejala:** Redis crash dan crashloop, seluruh web app mati.
* **Akar Masalah:** Terdapat antrean ribuan job yang melempar exception fatal secara berulang-ulang tanpa konfigurasi limit retry. Setiap retry menambahkan backtrace stack trace yang besar ke struktur data Redis.
* **Mitigasi:** Batasi batas *retry* maksimum (misal: 3–5 kali) dan gunakan Redis eviction policy `noeviction` untuk menjaga konsistensi job data, serta monitor parameter Redis `used_memory`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Mengirim Objek Kompleks / State Penuh sebagai Argumen
```ruby
# SALAH BESAR (Memori bengkak, Stale Data, JSON Serialization Overload):
OrderProcessingJob.perform_later(current_user, @order, invoice_presenter)

# BENAR (Kirim referensi ID primitif):
OrderProcessingJob.perform_later(current_user.id, @order.id)
```
*Mengapa?* Argumen disimpan sebagai string JSON di Redis. Jika Anda mengirim objek yang memiliki referensi siklik atau instance variable yang besar, ukuran payload membesar dari puluhan byte menjadi megabyte. Terlebih lagi, data yang dibaca di worker adalah salinan usang (*stale*) jika ada update lain di DB saat job masih mengantre.

### Kesalahan Fatal 2: Mutasi Global State di Multithreaded Worker
```ruby
# SALAH (Thread Safety Hazard!):
class ReportWorker
  include Sidekiq::Job

  def perform(report_id)
    Time.zone = "Jakarta" # Mengubah global Time.zone untuk SELURUH thread di worker process!
    # generate report
  end
end

# BENAR:
class ReportWorker
  include Sidekiq::Job

  def perform(report_id)
    Time.use_zone("Jakarta") do
      # Thread-safe context switching
    end
  end
end
```

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **Desain Queue Berbasis Prioritas Dinamis:**
   Jangan melempar semua job ke dalam antrean `default`. Pisahkan antrean berdasarkan SLA (*Service Level Agreement*):
   * `critical` (Kirim SMS OTP, Proses Pembayaran)
   * `default` (Sync inventori, kirim welcome email)
   * `low` / `bulk` (Export CSV data tahunan, cleanup log)

   Konfigurasi bobot worker di `config/sidekiq.yml`:
   ```yaml
   :queues:
     - [critical, 5]
     - [default, 3]
     - [low, 1]
   ```

2. **Always Pass Primitive Arguments:**
   Batasi argumen hanya pada `Integer`, `String`, atau `Boolean`.

3. **Gunakan Connection Timeout yang Konservatif:**
   Setiap network call di background job wajib memiliki parameter `timeout` yang agresif:
   ```ruby
   Faraday.new(url: "https://api.erp.com") do |f|
     f.options.open_timeout = 2 # detik
     f.options.timeout = 5      # detik
   end
   ```

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI SUMBER DAYA

### Perhitungan Matematis Database Connection Pool
Kesalahan paling umum yang menyebabkan worker mengalami crash:
`ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`.

Sebuah proses Sidekiq menjalankan *N* konkurensi thread. Masing-masing thread memerlukan setidaknya 1 koneksi database saat mengakses Active Record.

Formula konfigurasi connection pool:
$$\text{Pool Size} \ge \text{Sidekiq Concurrency} + \text{Internal Sidekiq Headroom (2–5)}$$

**Implementasi:**
Di file `config/database.yml`:
```yaml
production:
  adapter: postgresql
  encoding: unicode
  pool: <%= ENV.fetch("RAILS_MAX_THREADS", 5).to_i %>
```

File konfigurasi `config/sidekiq.yml`:
```yaml
concurrency: <%= ENV.fetch("SIDEKIQ_CONCURRENCY", 10).to_i %>
```

Pastikan environment variable pada kontainer/mesin Sidekiq diset:
```bash
RAILS_MAX_THREADS=15
SIDEKIQ_CONCURRENCY=10
```
Jika `SIDEKIQ_CONCURRENCY = 10` dan `RAILS_MAX_THREADS = 5`, aplikasi dipastikan mengalami dead lock koneksi basis data.

---

# SEKSI 16 — KEAMANAN & HARDENING

### 1. Pengamanan Sidekiq Web UI Dashboard
Sidekiq menyediakan dashboard sinatra engine yang sangat powerful untuk mematikan job, membersihkan queue, atau me-retry job secara manual. Dashboard ini tidak boleh terbuka ke publik.

```ruby
# config/routes.rb
require "sidekiq/web"

Rails.application.routes.draw do
  # Proteksi menggunakan Custom Rack Basic Auth atau Devise Admin Constraints
  authenticate :user, ->(u) { u.admin? } do
    mount Sidekiq::Web => "/sidekiq-admin-console"
  end
end
```

### 2. Sanitasi Parameter PII / Credentials
Jangan pernah memasukkan nomor kartu kredit, CVV, token autentikasi, atau password di dalam argumen job. Payload argumen job tersimpan mentah (*plain text*) di memori Redis dan log sistem. Jika Redis terekspos, seluruh kredensial tersebut bocor. Masukkan token atau kredensial ke dalam Vault/Credentials store dan kirimkan referensi identifikatornya saja ke job.

---

# SEKSI 17 — OBSERVABILITAS, LOGGING & DEBUGGING

Untuk melacak siklus hidup job melintasi distributed boundary, integrasikan OpenTelemetry context atau Request ID tracing ke dalam metadata logging job:

```ruby
# config/initializers/sidekiq_logging.rb
Sidekiq.configure_server do |config|
  config.logger = ActiveSupport::TaggedLogging.new(Logger.new($stdout))
  
  # Inject Correlation ID ke dalam format log
  config.server_middleware do |chain|
    chain.add Class.new {
      def call(worker, job, queue)
        Sidekiq::Logging.with_context("JobClass=#{job['class']} JID=#{job['jid']}") do
          yield
        end
      end
    }
  end
end
```

### Memeriksa DeadSet (Dead Letter Queue) via Konsol Rails:
Jika job melebihi batas percobaan retry dan masuk ke dalam `DeadSet`, lakukan inspeksi secara terprogram via `rails console`:

```ruby
# Menghitung jumlah total job yang mati
dead_set = Sidekiq::DeadSet.new
puts "Total dead jobs: #{dead_set.size}"

# Inspeksi alasan kegagalan dari job terakhir
last_failed_job = dead_set.first
puts "Error Class: #{last_failed_job['error_class']}"
puts "Error Message: #{last_failed_job['error_message']}"
puts "Payload Args: #{last_failed_job.args}"

# Me-retry satu job spesifik secara manual
last_failed_job.retry

# Menghapus seluruh job gagal tanpa retry
dead_set.clear
```

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

```ruby
# 1. Enqueue Job Sekarang
MyWorker.perform_async(arg1, arg2)               # Native Sidekiq
MyJob.perform_later(arg1, arg2)                  # Active Job standard

# 2. Enqueue Job Terjadwal (Delayed)
MyWorker.perform_in(3.hours, arg1)               # Sidekiq
MyJob.set(wait: 3.hours).perform_later(arg1)     # Active Job

# 3. Penjadwalan pada Waktu Spesifik
MyWorker.perform_at(Date.tomorrow.midnight, id)  # Sidekiq
MyJob.set(wait_until: Date.tomorrow.midnight).perform_later(id)

# 4. Filter Transaksi Database
after_commit :enqueue_job, on: :create           # WAJIB gunakan after_commit

# 5. Konfigurasi Threading Rule of Thumb
DB_POOL >= SIDEKIQ_CONCURRENCY + 2
```

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal Basic (1–5):
1. **Mengapa pemanggilan `MyJob.perform_later(Order.last)` berpotensi menimbulkan data *stale* dibanding `MyJob.perform_later(Order.last.id)`?**
   * *Jawaban:* Karena jika objek diserialisasi via dump state biasa (non-GlobalID), perubahan atribut yang terjadi di database antara waktu enqueue dan eksekusi worker tidak akan ter-update pada instance yang berjalan di worker. Menggunakan ID memaksa worker melakukan query kondisi teranyar saat eksekusi dimulai.

2. **Perintah Redis apa yang digunakan Sidekiq untuk mengambil job dari antrean secara non-busy waiting?**
   * *Jawaban:* Perintah `BRPOP` (*Blocking Right Pop*).

3. **Apa fungsi dari callback `after_commit` dalam konteks penanganan background job?**
   * *Jawaban:* Memastikan transaksi ACID basis data telah di-commit secara permanen ke disk storage sebelum pesan didorong ke antrean worker, menghindari race condition `ActiveRecord::RecordNotFound`.

4. **Apa yang dimaksud dengan GlobalID di Ruby on Rails?**
   * *Jawaban:* Skema URI terstandarisasi (`gid://app/Model/id`) yang memungkinkan Active Job mengubah objek model Active Record menjadi string identifier universal saat serialisasi dan merekonstruksinya kembali saat deserialisasi.

5. **Apa efek samping jika konkurensi Sidekiq diset ke 20, namun `pool` di database.yml diset ke 5?**
   * *Jawaban:* Akan terjadi `ActiveRecord::ConnectionTimeoutError` ketika lebih dari 5 thread mencoba mengakses database secara bersamaan, menyebabkan job gagal secara massal (*connection starvation*).

### Soal Intermediate (6–10):
6. **Jelaskan perbedaan mendasar penanganan Scheduled Jobs antara Redis List dan Redis Sorted Set (ZSET) pada Sidekiq!**
   * *Jawaban:* Redis List hanya mendukung manipulasi FIFO/LIFO tanpa urutan berbasis waktu. Sidekiq menggunakan Sorted Set (ZSET) untuk penjadwalan masa depan, di mana Unix Epoch Timestamp menjadi *score*-nya. Poller thread secara berkala mengevaluasi ZSET dengan `ZRANGEBYSCORE` untuk mengambil item yang nilainya $\le$ waktu saat ini.

7. **Kapan Anda sebaiknya memilih Solid Queue (DB-backed) dibanding Sidekiq (Redis-backed)?**
   * *Jawaban:* Solid Queue ideal jika arsitektur ditargetkan memiliki kompleksitas operasional rendah (tanpa server Redis tambahan), butuh fitur transactional outbox murni (job dan mutasi data dicatat dalam satu transaksi ACID DB yang sama), dan beban traffic throughput belum mencapai level puluhan ribu job per detik.

8. **Mengapa kita tidak boleh membungkus API call eksternal tanpa timeout di dalam background worker?**
   * *Jawaban:* Koneksi socket HTTP tanpa batas waktu (timeout) dapat menggantung (*hung*) tanpa batas akhir. Jika sejumlah thread worker tertahan pada I/O blocking ini, seluruh thread pool worker akan habis terpakai (*worker starvation*), menghentikan seluruh pemrosesan antrean sistem.

9. **Bagaimana cara mencegah "Double Spending" atau eksekusi ganda jika Sidekiq me-retry job yang gagal di tengah proses?**
   * *Jawaban:* Mengimplementasikan *Idempotency Check* menggunakan token unik di level database (misal: atomic unique constraint / conditional update) atau Redis lock, sehingga pemrosesan berikutnya mendeteksi bahwa mutasi state telah terjadi dan langsung melewati eksekusi.

10. **Apa yang terjadi pada job jika proses Sidekiq menerima sinyal `SIGTERM` (misalnya saat proses deploy ke Heroku/Kubernetes)?**
    * *Jawaban:* Sidekiq memasuki fase *quiet* (berhenti mengambil job baru via `BRPOP`), memberikan waktu toleransi (biasanya default 25 detik) bagi thread yang sedang berjalan untuk menyelesaikan tugasnya. Jika tidak selesai dalam batas waktu toleransi, Sidekiq akan mengirim sinyal `SIGKILL`, mengembalikan (*push back*) job yang belum tuntas ke antrean Redis untuk dijalankan ulang nantinya.

---

# SEKSI 20 — TANTANGAN MANDIRI & MINI PROJECT PRAKTIKUM

### Judul Praktikum:
**Membangun Resilient Batch CSV Importer dengan Dynamic Rate Limiting & Distributed Locking**

### Deskripsi Skenario:
Anda ditugaskan membangun pipeline import data pengguna dari file CSV berukuran 500 MB (berisi ~500.000 baris data). File ini diunggah melalui antarmuka web admin.

### Persyaratan Arsitektural & Fungsional:
1. **Dilarang Memproses Seluruh CSV dalam Satu Job:**
   * Buat sebuah `CsvDispatcherJob` yang membaca file baris demi baris menggunakan `File.foreach` (Stream processing untuk menghemat memori).
   * Pecah (*chunk*) file menjadi batch berukuran 1.000 baris.
   * Dispatch masing-masing batch menjadi job terpisah: `ImportUserBatchJob`.
2. **Mutual Exclusion (Distributed Lock):**
   * Pastikan tidak ada 2 proses import yang memproses file yang sama secara bersamaan menggunakan lock Redis berbasis lease time.
3. **Transient Failure & Throttling Simulation:**
   * Di dalam `ImportUserBatchJob`, lakukan enkripsi payload dan insert ke database menggunakan `insert_all` (bulk insertion) untuk efisiensi.
   * Simulasikan bahwa layanan eksternal pembuat avatar identitas memiliki limit 10 request per detik; gunakan Redis Sliding Window rate-limiter dari modul ini.
4. **Failure Recovery:**
   * Jika batch gagal pada baris ke-500, konfigurasi mekanisme penanganan sedemikian rupa sehingga ketika job di-retry, data 499 baris pertama tidak terduplikasi (Gunakan Postgres `ON CONFLICT DO NOTHING`).

### Kriteria Keberhasilan Eksekusi:
* Penggunaan RAM Rails Web App tidak melebihi 150 MB saat file diunggah dan dibaca.
* Dashboard Sidekiq menunjukkan distribusi pemrosesan antrean yang merata tanpa thread starvation.
* Sengaja matikan proses Sidekiq di tengah proses import menggunakan `kill -9 <PID>`, jalankan kembali worker, dan buktikan seluruh data dari 500.000 baris CSV tetap terimpor secara konsisten tanpa ada data duplikat atau data yang hilang.