# Bab 10: Asynchronous Processing & Background Architecture
## Modul 01: Arsitektur Eksekusi Asinkron: Active Job Abstraction, Adapter Engines (Solid Queue vs. Sidekiq), dan Concurrency Runtime

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Menganalisis arsitektur internal abstraksi `ActiveJob::Base` dan siklus serialisasi argumen berbasis `GlobalID`.
- Mengimplementasikan pola asinkron nir-blokir (*non-blocking*) pada siklus HTTP request-response dengan menjamin *data consistency* melalui integrasi *database transaction boundaries*.
- Mengevaluasi perbandingan mekanika konkurensi antara *Redis-backed multi-threaded workers* (Sidekiq) dan *RDBMS-backed queue tables* menggunakan semantik `FOR UPDATE SKIP LOCKED` (Solid Queue).
- Mengonfigurasi parameter *connection pool*, *worker concurrency*, alokasi memori runtime (jemalloc), dan mitigasi konkurensi *race condition* pada pemrosesan *job* skala produksi.
- Mendesain alur kerja pemrosesan latar belakang yang menerapkan prinsip *idempotency* dan penanganan kegagalan bertingkat (*exponential backoff with jitter*).

---

### 2. Prerequisite
Sebelum mempelajari modul ini, Anda wajib menguasai:
- Model konkurensi Puma web server (MRI Ruby GVL, proses *clustered*, dan *multi-threading*).
- Mekanisme transaksi database relasional ACID, *lock modes*, dan isolasi transaksi PostgreSQL/MySQL.
- Konfigurasi `ActiveRecord::Base.connection_pool` dan implikasinya terhadap *thread exhaustion*.
- Sintaksis Ruby modern (Ruby 3.x), khususnya *block handling*, *pattern matching*, dan penanganan *exception*.

---

### 3. Concept
Secara arsitektural, pemrosesan web berbasis HTTP pada Rails berjalan di atas model *synchronous request-response*. Server Puma menerima koneksi, mendedikasikan satu thread dari *worker process* untuk mengeksekusi request, dan menahan socket koneksi klien hingga *response payload* dikirimkan secara tuntas. 

Jika sebuah alur kerja membutuhkan komputasi berat, transmisi jaringan ke vendor pihak ketiga (misalnya *payment gateway* atau SMTP), atau mutasi batch data besar, pengeksekusian secara langsung (*in-band*) dalam siklus request akan mendegradasi *throughput* server secara eksponensial. Hal ini menyebabkan fenomena *worker starvation*, di mana seluruh thread Puma habis terpakai hanya untuk menunggu latensi I/O eksternal, sehingga request baru yang masuk tertahan di *kernel socket backlog* (*request queuing latency spike*).

```
[In-band Execution (Anti-Pattern)]
Client ---> [ Puma Thread ] ===(DB Queries)===> [External API (2s)] ---> Response (2100ms)
               ^
               Thread terkunci selama 2100ms!

[Out-of-band Execution (Active Job Pipeline)]
Client ---> [ Puma Thread ] --- Enqueue Job ---> [ Storage/Queue Engine ] ---> Response (15ms)
                                                       |
                                                       v
                                            [ Background Worker Thread ]
                                            ===(Eksekusi Async API/IO)===
```

Active Job hadir sebagai *unified abstraction layer* di dalam framework Rails untuk mendistribusikan beban kerja tersebut ke luar dari siklus HTTP (*out-of-band*). Arsitektur internal Active Job beroperasi melalui tiga komponen inti:
1. **Serialization Layer (GlobalID):** Mengubah objek ActiveRecord kompleks menjadi URI kanonikal string portabel (`gid://app/Model/id`) sehingga payload job berukuran kecil dan terbebas dari *stale memory state*.
2. **Adapter Engine Layer:** Menerjemahkan antarmuka standar Active Job ke dalam format spesifik backend eksekutor (Solid Queue, Sidekiq, Delayed Job, AWS SQS).
3. **Execution Context:** Menjalankan deserialisasi data, menyiapkan context database, menginjeksi middleware (seperti `CurrentAttributes`), dan mengeksekusi method `#perform` di dalam thread terpisah.

---

### 4. Why
Mengapa arsitektur pemrosesan asinkron sangat kritikal dalam sistem berskala produksi?

1. **Mempertahankan Latensi p99 HTTP API:** Pengguna menuntut *latency budget* rendah (< 200 milidetik). Memindahkan pekerjaan I/O lambat (pembuatan PDF, pengiriman email, analitik data) menjamin Puma thread segera kembali ke *pool* untuk melayani klien lain.
2. **Resiliensi terhadap Kegagalan Dependensi Eksternal:** Layanan pihak ketiga kerap mengalami *downtime*, *network blip*, atau *rate limiting*. Dengan mengeksekusi transaksi secara asinkron, sistem internal dapat menjadwalkan ulang eksekusi (*retry mechanism*) tanpa memicu HTTP 500 error ke sisi klien.
3. **Load Leveling / Traffic Smoothing:** Pada saat *flash sale* atau *batch processing*, antrean *job* bertindak sebagai *buffer*. Sistem memproses antrean sesuai kapasitas komputasi yang tersedia tanpa merusak database utama akibat beban kerja yang masuk bersamaan secara masif (*thundering herd problem*).

---

### 5. What
Komponen-komponen utama dalam arsitektur Active Job dan ekosistem pemrosesan antrean latar belakang meliputi:

- **`ActiveJob::Base`**: Kelas dasar yang menyediakan antarmuka pemanggilan (`perform_later`, `perform_now`), manajemen callback (`before_perform`, `around_enqueue`), konfigurasi retry, dan mapping antrean.
- **GlobalID (`URI-based identification`)**: Mekanisme representasi objek database menjadi string URI universal. Saat argumen model diteruskan ke `perform_later`, Rails tidak melakukan serialisasi seluruh atribut objek ke memori, melainkan hanya menyimpan string referensi GlobalID.
- **Queue Adapter**: *Bridge* yang mengimplementasikan metode `#enqueue` dan `#enqueue_at`. Rails menyediakan adapter bawaan seperti `:solid_queue`, `:sidekiq`, `:test`, dan `:inline`.
- **Solid Queue Engine**: Engine berbasis database relasional (PostgreSQL, MySQL, SQLite) yang menggunakan fitur `FOR UPDATE SKIP LOCKED`. Engine ini meniadakan kebutuhan kluster Redis terpisah untuk beban kerja menengah ke atas, dengan memanfaatkan tabel `solid_queue_jobs`, `solid_queue_scheduled_executions`, dan `solid_queue_ready_executions`.
- **Sidekiq Engine**: Engine berbasis Redis yang memanfaatkan struktur data *Redis Lists* dan *Sorted Sets*. Sidekiq menggunakan model konkurensi murni multi-threaded di Ruby, memiliki latensi *polling* sub-milidetik, dan *throughput* tinggi.

---

### 6. How
Alur kerja komprehensif dari inisiasi job hingga penyelesaian eksekusi:

```
+---------------------------------------------------------------------------------------+
| SIKLUS PENGIRIMAN (ENQUEUE LIFECYCLE)                                                 |
|                                                                                       |
|  1. Controller/Model                                                                  |
|     PaymentJob.perform_later(order)                                                   |
|             |                                                                         |
|             v                                                                         |
|  2. ActiveJob::Arguments.serialize                                                   |
|     Order object diubah menjadi "gid://app/Order/42"                                  |
|             |                                                                         |
|             v                                                                         |
|  3. Adapter Serialized Payload Serialization                                          |
|     JSON Payload: { "job_class": "PaymentJob", "arguments": [...], "job_id": "uuid" }  |
|             |                                                                         |
|             v                                                                         |
|  4. Database Transaction Boundary Enforcement                                        |
|     Penyimpanan job ke Redis/RDBMS HARUS ditunda hingga transaksi commit.              |
+------------------------------------------+--------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| SIKLUS EKSEKUSI (WORKER LIFECYCLE)                                                    |
|                                                                                       |
|  5. Engine Poller / Fetcher                                                           |
|     - Sidekiq: BRPOP dari Redis List.                                                 |
|     - Solid Queue: SELECT ... FOR UPDATE SKIP LOCKED dari DB Ready Table.             |
|             |                                                                         |
|             v                                                                         |
|  6. Deserialization & Thread Assignment                                               |
|     Payload di-parse -> GlobalID diterjemahkan via `GlobalID::Locator.locate`         |
|     (SELECT * FROM orders WHERE id = 42).                                             |
|             |                                                                         |
|             v                                                                         |
|  7. Execution Context Activation                                                      |
|     Eksekusi Callback -> `#perform` dipanggil di dalam Thread terdedikasi.            |
|             |                                                                         |
|             v                                                                         |
|  8. Completion / Failure Recovery                                                     |
|     - Sukses: Ack payload / Hapus data dari antrean.                                  |
|     - Exception: Tangkap error -> Evaluasi `retry_on` -> Jadwalkan ulang / DLQ.       |
+---------------------------------------------------------------------------------------+
```

1. **Serialisasi:** Saat `perform_later` dieksekusi, argumen divalidasi. Primitive types (String, Integer, Hash) dipertahankan, sedangkan instance `ActiveRecord::Base` diserialisasi menjadi GlobalID string.
2. **Enqueue Buffer:** Payload JSON lengkap dibuat dan dikirim ke adapter terpilih.
3. **Commit Synchronization:** Job tidak boleh diambil oleh worker sebelum transaksi database yang melingkupinya berhasil di-*commit*. Jika worker mengeksekusi job sebelum data tersimpan secara fisik di database, worker akan memicu `ActiveRecord::RecordNotFound`.
4. **Fetching via Concurrency Control:** Worker engine mengambil job dari antrean. Pada Solid Queue, query menggunakan klausa `SKIP LOCKED` untuk memastikan thread worker lain tidak terblokir oleh baris yang sedang diproses.
5. **Deserialisasi dan Pengeksekusian:** Engine mengonstruksi ulang *environment*, mengambil data model terbaru dari database menggunakan GlobalID, menginjeksi context, dan mengeksekusi blok kode `#perform`.

---

### 7. Analogy
Bayangkan sebuah restoran bintang lima dengan sistem pelayanan terintegrasi:

- **Puma Web Worker = Pramusaji (Waiter):** Tugas utamanya adalah menyapa pelanggan, mencatat pesanan, dan menyerahkan tagihan. Jika pramusaji tersebut harus memasak steik sendiri ke dapur (I/O lambat / sinkron), meja-meja pelanggan baru tidak akan pernah terlayani, dan antrean di pintu masuk restoran akan meluap.
- **Active Job Payload = Kertas Tiket Pesanan:** Pramusaji menulis tiket pesanan dengan format baku. Alih-alih membawa bahan mentah daging dari gudang (objek ActiveRecord penuh di memori), pramusaji hanya menulis nomor kode identifikasi daging di lemari pendingin: `"gid://freezer/WagyuA5/Rack-12"` (GlobalID).
- **Queue Engine (Solid Queue / Sidekiq) = Rak Tiket Pemesanan di Dapur:** Tempat tiket pesanan ditancapkan secara teratur. Rak ini menjaga agar tiket tidak basah dan terurut secara kronologis.
- **Background Worker Threads = Tim Koki (Chefs):** Koki mengambil satu tiket dari rak dapur. Jika koki lain sedang mengambil tiket nomor 5, koki berikutnya langsung melompat mengambil tiket nomor 6 tanpa bertabrakan (*SKIP LOCKED*). Koki lalu mengambil daging di kulkas berdasarkan referensi ID di tiket, memasaknya, dan menandai tiket tersebut telah selesai diproses.

---

### 8. Diagram

```
+---------------------------------------------------------------------------------------+
|                                    RUBY ON RAILS APP                                  |
|                                                                                       |
|   +-----------------------+                    +----------------------------------+   |
|   |   Puma Web Server     |                    |    Active Job Abstraction        |   |
|   |  (Puma Thread Pool)   |                    |                                  |   |
|   |                       |                    |  - Argument Serialization        |   |
|   |  POST /api/v1/orders  |                    |  - GlobalID Translation          |   |
|   |          |            |                    |  - Retry Configuration           |   |
|   +----------|------------+                    +----------------------------------+   |
|              |                                                  |                     |
|              +---------> Order.transaction do                   |                     |
|                            order.save!                          v                     |
|                            OrderNotificationJob.perform_later(order)                 |
|                          end                                    |                     |
+-----------------------------------------------------------------|---------------------+
                                                                  |
                                      +---------------------------+---------------------+
                                      |                                                 |
                   Adapter Selection: Solid Queue                      Adapter Selection: Sidekiq
                                      |                                                 |
                                      v                                                 v
                     +---------------------------------+               +---------------------------------+
                     |   PostgreSQL / MySQL RDBMS      |               |          Redis Server           |
                     |                                 |               |                                 |
                     |  TABLE solid_queue_jobs         |               |  LPUSH "queue:default"          |
                     |  TABLE solid_queue_ready_execs  |               |  ZADD  "queue:scheduled"        |
                     +---------------------------------+               +---------------------------------+
                                      |                                                 |
                                      v                                                 v
                     +---------------------------------+               +---------------------------------+
                     |    Solid Queue Dispatcher       |               |        Sidekiq Worker Process   |
                     |                                 |               |                                 |
                     |  SELECT ... FROM ...            |               |  Thread 1  Thread 2  Thread N   |
                     |  FOR UPDATE SKIP LOCKED         |               |  (BRPOP loop on Redis Engine)   |
                     +---------------------------------+               +---------------------------------+
                                      |                                                 |
                                      +-----------------------+-------------------------+
                                                              |
                                                              v
                                              +---------------------------------+
                                              |    Worker Execution Sandbox     |
                                              |                                 |
                                              | 1. GlobalID::Locator.locate     |
                                              | 2. ActiveRecord Connection Pool |
                                              | 3. PaymentJob#perform           |
                                              | 4. External Vendor API Call     |
                                              +---------------------------------+
```

---

### 9. Simple Example
Implementasi dasar Active Job dengan konfigurasi retry otomatis berbasis eksponensial backoff:

```ruby
# app/jobs/welcome_email_job.rb
class WelcomeEmailJob < ApplicationJob
  queue_as :mailers

  # Konfigurasi penanganan error: retry 3 kali dengan interval bertingkat
  retry_on Net::SMTPServerBusy, wait: :polynomially_longer, attempts: 3
  
  # Buang job jika data user telah dihapus sebelum job sempat dieksekusi
  discard_on ActiveJob::DeserializationError

  def perform(user)
    # user diteruskan sebagai instance ActiveRecord, 
    # namun diserialisasikan ke antrean sebagai GlobalID string
    UserMailer.welcome(user).deliver_now
  end
end
```

Pemanggilan dari controller:

```ruby
# app/controllers/users_controller.rb
class UsersController < ApplicationController
  def create
    @user = User.new(user_params)
    
    if @user.save
      # Job di-enqueue ke queue adapter terpilih
      WelcomeEmailJob.perform_later(@user)
      render json: @user, status: :created
    else
      render json: @user.errors, status: :unprocessable_entity
    end
  end
end
```

---

### 10. Practical Example
Berikut adalah implementasi sistem pemrosesan mutasi pembayaran (*payment webhook processing*) berstandar industri dengan jaminan idempotensi, penanganan *out-of-order execution*, *distributed locking*, serta integrasi *transactional commit*.

#### 1. Setup Job Class dengan Idempotensi & Logging Kontekstual

```ruby
# app/jobs/process_payment_webhook_job.rb
# frozen_string_literal: true

class ProcessPaymentWebhookJob < ApplicationJob
  queue_as :critical_payments

  # Konfigurasi toleransi kegagalan jaringan eksternal
  retry_on Faraday::TimeoutError, 
           Faraday::ConnectionFailed, 
           wait: ->(executions) { (executions**4) + 15 + rand(10) }, # Exponential with jitter
           attempts: 5

  # Discard data jika signature webhook tidak valid atau payload rusak permanen
  discard_on ArgumentError, JSON::ParserError do |job, error|
    Rails.logger.error("[ProcessPaymentWebhookJob] Permanent failure for Job: #{job.job_id}. Reason: #{error.message}")
  end

  def perform(webhook_payload_id)
    payload_record = WebhookPayload.find_by(id: webhook_payload_id)
    return unless payload_record
    return if payload_record.processed?

    # Menjaga konkurensi antar-thread/worker dengan Redis Mutex / Database Lock
    # Mencegah eksekusi ganda jika webhook dikirimkan dua kali dalam rentang milidetik yang sama
    payload_record.with_lock("FOR UPDATE NOWAIT") do
      if payload_record.processed?
        Rails.logger.info("[ProcessPaymentWebhookJob] Payload ID #{webhook_payload_id} already marked as processed.")
        return
      end

      parse_and_reconcile_transaction(payload_record)
    end
  rescue ActiveRecord::LockWaitTimeout
    # Jika terbentur lock, coba lagi job beberapa detik kemudian
    retry_job wait: 5.seconds
  end

  private

  def parse_and_reconcile_transaction(payload_record)
    raw_event = payload_record.data
    external_tx_id = raw_event.fetch("transaction_id")
    amount = raw_event.fetch("amount_cents")
    status = raw_event.fetch("status")

    ActiveRecord::Base.transaction do
      order = Order.lock.find_by!(external_reference_id: external_tx_id)

      # Idempotency check pada level State Machine entitas bisnis
      if order.payment_completed?
        payload_record.update!(status: :ignored, processed_at: Time.current)
        return
      end

      case status
      when "settled"
        order.mark_as_paid!(paid_amount: amount)
        payload_record.update!(status: :processed, processed_at: Time.current)
        
        # Enqueue downstream job dengan relasi transactional
        CustomerInvoiceJob.perform_later(order.id)
      when "failed"
        order.mark_as_failed!(reason: raw_event["failure_reason"])
        payload_record.update!(status: :failed, processed_at: Time.current)
      else
        raise ArgumentError, "Status webhook tidak dikenal: #{status}"
      end
    end
  end
end
```

#### 2. Setup Safe Enqueueing pada Controller via Transactional Callbacks

```ruby
# app/controllers/api/v1/webhooks_controller.rb
# frozen_string_literal: true

module Api
  module V1
    class WebhooksController < ApplicationController
      skip_before_action :verify_authenticity_token

      def receive
        payload_record = nil

        ActiveRecord::Base.transaction do
          payload_record = WebhookPayload.create!(
            provider: "stripe",
            data: params.to_unsafe_h,
            status: :pending
          )
        end

        # KRITIKAL: Enqueue WAJIB dilakukan SETELAH transaksi basis data berhasil commit secara absolut.
        # Jika enqueue dipanggil di dalam blok transaksi di atas, 
        # worker berpotensi mengeksekusi job sebelum transaksi PostgreSQL commit (Race Condition).
        ProcessPaymentWebhookJob.perform_later(payload_record.id)

        head :accepted
      rescue ActiveRecord::RecordInvalid => e
        render json: { error: e.message }, status: :unprocessable_entity
      end
    end
  end
end
```

#### 3. Database Migration untuk Mendukung State Tracking

```ruby
# db/migrate/20260330000001_create_webhook_payloads.rb
class CreateWebhookPayloads < ActiveRecord::Migration[7.2]
  def change
    create_table :webhook_payloads, id: :uuid do |t|
      t.string :provider, null: false
      t.jsonb :data, null: false, default: {}
      t.string :status, null: false, default: "pending"
      t.datetime :processed_at
      t.timestamps
    end

    add_index :webhook_payloads, :status
    add_index :webhook_payloads, :created_at
  end
end
```

---

### 11. Real World Example
**Skenario:** E-commerce Enterprise memproses event jutaan pesanan per jam saat *Flash Sale Global*.

**Arsitektur & Konfigurasi:**
Sistem menggunakan *Sidekiq Enterprise* dengan Redis Cluster terdedikasi untuk antrean dengan *high throughput*, dan *Solid Queue* pada kluster PostgreSQL terisolasi untuk job finansial yang mewajibkan keandalan ACID.

Pada skala ini, masalah utama yang dihadapi meliputi:
1. **Memory Fragmentation & Bloat:** Runtime MRI Ruby menggunakan `glibc malloc` standar yang menyebabkan fragmentasi memori ekstrem pada worker saat memproses payload string berukuran besar.
2. **Database Connection Pool Exhaustion:** Terjadi ketika konkurensi worker Sidekiq melampaui jumlah koneksi database yang tersedia di `config/database.yml`.

**Solusi Arsitektur Produksi:**
- Mengganti memory allocator runtime Ruby pada kontainer Docker dengan `jemalloc`.
- Menyesuaikan kalkulasi pool database secara matematis:
  $$\text{DB Pool per Container} = \text{Sidekiq Concurrency} + \text{Reserved System Connections (2-5)}$$
- Memisahkan worker ke dalam beberapa dedicated queues: `:critical`, `:default`, `:low`.

```bash
# Dockerfile snippet untuk optimasi memory allocator di worker
FROM ruby:3.3.0-slim

RUN apt-get update && apt-get install -y libjemalloc2 && rm -rf /var/lib/apt/lists/*
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2

WORKDIR /app
COPY . .
```

Konfigurasi file `config/sidekiq.yml`:
```yaml
# config/sidekiq.yml
:concurrency: 10 # 10 threads per worker process
:queues:
  - [critical_payments, 6] # Bobot prioritas antrean tinggi
  - [default, 3]
  - [mailers, 1]
:timeout: 25 # Toleransi detik saat graceful shutdown sebelum worker di-kill (SIGKILL)
```

File konfigurasi connection database (`config/database.yml`):
```yaml
production:
  adapter: postgresql
  encoding: unicode
  # Concurrency (10) + Reserve (5) = 15 connection pool minimum per worker instance
  pool: <%= ENV.fetch("RAILS_MAX_THREADS", 10).to_i + 5 %>
  url: <%= ENV['DATABASE_URL'] %>
```

---

### 12. Trade-offs
Memilih engine backend queueing membutuhkan pertimbangan arsitektural yang matang:

| Dimensi Evaluasi | Solid Queue (RDBMS-backed) | Sidekiq (Redis-backed) |
| :--- | :--- | :--- |
| **Infrastruktur** | **Sederhana:** Memanfaatkan database yang sudah ada (PostgreSQL/MySQL). Tanpa dependensi service baru. | **Menengah/Kompleks:** Memerlukan kluster Redis khusus dengan persistensi data yang dipelihara (*RDB/AOF*). |
| **Data Durability (Daya Tahan)** | **Sangat Tinggi (ACID):** Transaksional dan tersimpan di disk. Minim risiko *data loss* saat crash server. | **Tergantung Konfigurasi:** Jika Redis diset *pure in-memory*, crash node tanpa snapshotting dapat menghilangkan data. |
| **Throughput & Latensi** | **Menengah:** Terikat performa I/O database dan IOPS disk. Kurang optimal untuk > 10.000 job/detik. | **Sangat Tinggi:** Latensi in-memory tingkat mikrodetik. Mampu memproses puluhan ribu job/detik secara efisien. |
| **Beban Basis Data** | **Tinggi:** Worker melakukan polling query berkala (`FOR UPDATE SKIP LOCKED`) yang membebani IOPS database utama. | **Nol pada DB Utama:** Seluruh operasi antrean dan polling dieksekusi di Redis, membebaskan IOPS database. |
| **Kompleksitas Operasional** | **Rendah:** Backup terpadu mengikuti jadwal database utama aplikasi. | **Tinggi:** Perlu monitoring Redis memory fragmentation ratio, eviction policy, dan replication failover. |

---

### 13. When To Use
Gunakan arsitektur asinkron Active Job jika aplikasi Anda:
- Mengirimkan email, notifikasi push via FCM/APNS, atau komunikasi SMS.
- Berinteraksi dengan third-party HTTP API yang latensinya berada di luar kendali SLA infrastruktur Anda sendiri.
- Melakukan manipulasi gambar, transcoding audio/video, atau pembuatan laporan berformat XLSX/PDF.
- Menjalankan sinkronisasi data batch, data warehousing ingest, atau pengindeksan Elasticsearch/OpenSearch.
- Memproses event Webhook berfrekuensi tinggi dari platform lain (misal: Stripe, Midtrans, GitHub).

---

### 14. When NOT To Use
Hindari memindahkan eksekusi ke background job pada kondisi berikut:
- **Kebutuhan Respon Atomik Sinkron Langsung:** Operasi di mana klien API membutuhkan respons komputasi secara *real-time* sebelum mengeksekusi instruksi selanjutnya (misalnya: kalkulasi otentikasi JWT atau query pencarian autocomplete instan).
- **Proses Sangat Sepele (Sub-milidetik):** Meng-enqueue mutasi string sederhana atau komputasi aritmatika kecil menghasilkan *overhead* serialisasi JSON dan I/O jaringan yang justru jauh lebih mahal daripada mengeksekusinya secara inline di Puma thread.
- **Komunikasi Internal Transaksi Database Terikat:** Ketika langkah eksekusi selanjutnya membutuhkan konsistensi data yang berada dalam satu scope commit lokal yang sama.

---

### 15. Common Mistakes

#### 1. Enqueue di dalam blok transaksi sebelum commit (*Transactional Race Condition*)
```ruby
# SALAH BESAR
ActiveRecord::Base.transaction do
  order = Order.create!(order_params)
  # Worker Sidekiq dapat mengambil job ini SEBELUM blok transaksi melakukan COMMIT.
  # Akibatnya: Worker melempar ActiveRecord::RecordNotFound!
  OrderProcessingJob.perform_later(order.id)
end

# BENAR: Gunakan callback commit atau enqueue di luar blok
ActiveRecord::Base.transaction do
  order = Order.create!(order_params)
end
OrderProcessingJob.perform_later(order.id)

# ATAU: Manfaatkan lifecycle callback bawaan Rails
class Order < ApplicationRecord
  after_create_commit :enqueue_processing

  private

  def enqueue_processing
    OrderProcessingJob.perform_later(self)
  end
end
```

#### 2. Melakukan serialisasi seluruh instance objek ActiveRecord yang besar
```ruby
# SALAH
# Melewatkan objek dengan relasi yang memuat cache queries besar akan membebani queue payload
OrderProcessingJob.perform_later(order_with_thousands_of_items)

# BENAR
# Lewatkan ID saja atau biarkan GlobalID bekerja pada level root model
OrderProcessingJob.perform_later(order.id)
```

#### 3. Mengabaikan sifat Idempotensi pada Worker
Banyak engineer berasumsi sebuah background job hanya akan dipanggil tepat satu kali (*exactly-once*). Dalam sistem terdistribusi, prinsip pengiriman yang dijamin hanyalah *at-least-once*. Kegagalan jaringan dapat memicu worker memproses ulang job yang sama. Jika kode Anda tidak memiliki mekanisme pertahanan terhadap eksekusi ganda, pemotongan saldo atau pengiriman email dapat terulang.

---

### 16. Best Practices (Production Checklist)
- [ ] **Desain Job yang Idempotent:** Pastikan pemanggilan ulang `#perform` dengan argumen yang sama berkali-kali tidak akan merusak konsistensi data.
- [ ] **Gunakan `after_commit` hooks:** Jangan pernah meng-enqueue job dari dalam callback `after_save` atau `after_create`. Selalu gunakan `after_create_commit` atau `after_update_commit`.
- [ ] **Kalkulasi Pool Database yang Tepat:** Pastikan `database.yml` memiliki `pool` minimal sama dengan `(Sidekiq Concurrency + 2)`.
- [ ] **Pasang Jemalloc:** Konfigurasikan library `libjemalloc` pada Ruby Docker image untuk mencegah memory leak dan memory fragmentation di worker background.
- [ ] **Pisahkan Antrean Berdasarkan Prioritas:** Minimal bagi antrean menjadi tiga segmen: `:critical` (pembayaran, SMS OTP), `:default` (proses umum), dan `:low` (analitik, log archiving).
- [ ] **Gunakan Error Tracking & Dead Letter Queues (DLQ):** Pastikan Sentry/Bugsnag/Rollbar terpasang di worker untuk merekam job yang masuk ke antrean *dead/exhausted*.
- [ ] **Batas Timeout Operasi Eksternal:** Selalu tetapkan `open_timeout` dan `read_timeout` eksplisit pada setiap HTTP client library (Faraday/Net::HTTP) di dalam job agar thread worker tidak terblokir permanen.

---

### 17. Troubleshooting

#### Masalah 1: `ActiveRecord::ConnectionTimeoutError`
- **Gejala:** Worker log dipenuhi error `could not obtain a connection from the pool within 5.000 seconds`.
- **Akar Masalah:** Nilai `:concurrency:` worker engine (misal Sidekiq diset 25 thread) melampaui setelan `pool:` pada `config/database.yml` (misal pool bernilai 5).
- **Solusi:** Naikkan setelan pool di database.yml mengikuti atau melampaui jumlah total concurrency thread yang dijalankan pada proses worker tersebut.

#### Masalah 2: `ActiveJob::DeserializationError`
- **Gejala:** Job gagal seketika dengan error `Error while trying to deserialize arguments: Couldn't find Model with 'id'=X`.
- **Akar Masalah:** Record database telah dihapus di server sebelum worker sempat mengeksekusi job terkait, atau job dieksekusi sebelum transaksi pembuatan commit (*race condition*).
- **Solusi:** Tangani kasus tersebut dengan `discard_on ActiveJob::DeserializationError` jika kehilangan record tersebut merupakan perilaku yang diharapkan (misal data draft dibatalkan oleh pengguna).

#### Masalah 3: Memory Worker Naik Terus Menerus (*Unbounded Memory Bloat*)
- **Gejala:** Proses worker Sidekiq / Solid Queue mengonsumsi RAM hingga beberapa gigabyte lalu terkena OOM (*Out Of Memory Killer*) oleh sistem operasi.
- **Akar Masalah:** Query database menghasilkan puluhan ribu objek ActiveRecord sekaligus ke memori tanpa batasan (`Order.all` alih-alih `find_each`), ditambah alokator `glibc` yang enggan mengembalikan sisa fragmentasi memori ke kernel.
- **Solusi:** 
  1. Refactor kode menggunakan batch processing (`find_each(batch_size: 500)`).
  2. Inject library `LD_PRELOAD=/usr/lib/libjemalloc.so.2`.
  3. Konfigurasi `sidekiq-ent` atau utility seperti `puma_worker_killer` / memory limit watchdog untuk melakukan restart otomatis pada worker thread process saat mencapai batas memori tertentu.

---

### 18. Exercise
Buatlah sebuah implementasi Active Job bernama `AuditLogExportJob` dengan ketentuan teknis sebagai berikut:

1. Job menerima dua argumen: `user_id` (Integer) dan `target_date_range` (Hash berisi string tanggal `start_date` dan `end_date`).
2. Job mengeksekusi proses kompilasi data audit log menjadi string CSV.
3. Job harus mengimplementasikan proteksi retry:
   - Jika terjadi error `StorageService::UploadFailed`, lakukan retry sebanyak 3 kali dengan penundaan eksponensial.
   - Jika record user tidak ditemukan, batalkan job seketika (*discard*).
4. Pastikan job berjalan di antrean terpisah bernama `:exports`.

#### Template Kode Awal:
```ruby
# app/jobs/audit_log_export_job.rb
class AuditLogExportJob < ApplicationJob
  queue_as :exports

  # TODO: Tulis konfigurasi retry_on dan discard_on di sini

  def perform(user_id, target_date_range)
    # TODO: Lengkapi logika penanganan data di sini
  end
end
```

#### Solusi Pengujian / Verifikasi:
```ruby
# test/jobs/audit_log_export_job_test.rb
require "test_helper"

class AuditLogExportJobTest < ActiveJob::TestCase
  test "job masuk ke antrean exports" do
    assert_enqueued_with(job: AuditLogExportJob, queue: "exports") do
      AuditLogExportJob.perform_later(1, { start_date: "2026-01-01", end_date: "2026-01-31" })
    end
  end

  test "job membuang error ketika user tidak ditemukan" do
    assert_nothing_raised do
      perform_enqueued_jobs do
        AuditLogExportJob.perform_later(999_999, { start_date: "2026-01-01", end_date: "2026-01-31" })
      end
    end
  end
end
```

---

### 19. Challenge
Implementasikan mekanisme **"Dynamic Rate-Limiting Active Job Dispatcher"** untuk integrasi WhatsApp/SMS Notification Engine tanpa menggunakan gem tambahan.

**Kebutuhan Sistem:**
1. Provider API pihak ketiga menetapkan *hard limit* transaksi: maksimum 5 request per detik per API Key.
2. Jika server aplikasi Anda mengeksekusi 100 job notifikasi secara paralel, 95 job di antaranya tidak boleh memicu HTTP 429 (*Too Many Requests*) dari pihak vendor.
3. Rancang sebuah arsitektur job menggunakan kombinasi Redis atomic keys (`INCR`, `EXPIRE`) atau isolasi skema tabel Solid Queue yang mampu mengatur ritme eksekusi (`reschedule / retry_job`) secara otomatis saat kapasitas token detik berjalan telah terlampaui.
4. Buat benchmark sederhana yang membuktikan bahwa pemanggilan 50 notifikasi instan terdistribusi secara tertib selama durasi minimal 10 detik penuh.

---

### 20. Summary
- Pemrosesan asinkron via Active Job memisahkan siklus eksekusi I/O berat dari Puma web server demi menjaga batas latensi HTTP API p99 tetap optimal.
- `ActiveJob` bertindak sebagai layer abstraksi; backend eksekusi diserahkan kepada adapter engines seperti **Solid Queue** (RDBMS-based, terintegrasi kuat dengan DB ACID) atau **Sidekiq** (Redis-based, konkurensi ultra-cepat, throughput sangat tinggi).
- Mekanisme **GlobalID** menjaga ukuran payload job tetap ramping dengan menserialisasi model ActiveRecord menjadi representasi string URI kanonikal.
- Seluruh enqueue job yang bersumber dari perubahan entitas model wajib disinkronisasikan menggunakan callback **`after_commit`** guna menghindari anomali *race condition* di mana worker mengeksekusi job sebelum data tersimpan di database.
- Skalabilitas pemrosesan latar belakang tingkat lanjut bertumpu pada pengelolaan konkurensi multi-threading yang aman, penyesuaian alokasi *database connection pool*, penggunaan *memory allocator* jemalloc, serta jaminan *idempotency* di setiap unit job.