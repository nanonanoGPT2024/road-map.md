# BAB 05: Asynchronous Processing & Background Jobs
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan memiliki kompetensi tingkat lanjut untuk:
- Menganalisis dan mengoptimalkan arsitektur *asynchronous runtime* pada Ruby on Rails (Sidekiq enterprise stack dan Rails 8 Solid Queue).
- Memecahkan masalah konkurensi, memory leaks, dan saturasi koneksi basis data pada sistem terdistribusi skala tinggi.
- Mengimplementasikan pola idempotensi mutlak (*absolute idempotency*) dan *distributed locking* untuk mencegah *race condition* dan *double-spend*.
- Mengonfigurasi *resource isolation*, partisi antrean (*queue partitioning*), dan strategi mitigasi kegagalan (*dead-letter queues*, *exponential backoff with jitter*, *circuit breaker*).
- Mengintegrasikan instrumentasi observabilitas komprehensif (*OpenTelemetry distributed tracing*, *Prometheus metrics*, dan *structured logging*).

---

### 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Ruby Concurrency Model**: Pemahaman mendalam mengenai MRI Global VM Lock (GVL), POSIX threads, IO-bound vs CPU-bound execution, dan Copy-on-Write (CoW).
- **ActiveJob & Redis Fundamentals**: Siklus hidup dasar `ActiveJob::Base`, tipe data Redis (`LIST`, `ZSET`, `HASH`), serta mekanisme *polling* dan *blocking pops* (`BRPOP`, `BLMOVE`).
- **Database Transaction Isolation**: Mekanisme `READ COMMITTED`, `REPEATABLE READ`, MVCC, dan *row-level locking* (`FOR UPDATE SKIP LOCKED`).
- **Containerization & Networking**: Container networking, alokasi memori Linux (Resident Set Size vs Virtual Memory), serta penanganan POSIX signals (`SIGTERM`, `SIGTSTP`, `SIGKILL`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Mekanisme Antrean: Redis List/Zset vs Database `SKIP LOCKED`

Di ekosistem modern Ruby on Rails, terdapat dua pendekatan utama dalam implementasi antrean:

1. **Redis-backed (Sidekiq Core)**:
   - **Antrean Siap (Ready Queue)**: Disimpan sebagai Redis `LIST`. Ketika job di-*enqueue*, Rails melakukan serialisasi payload JSON dan menjalankan `LPUSH queue:<name> <payload>`.
   - **Eksekusi Worker**: Worker thread menjalankan perintah atomik `BRPOP` atau `BLMOVE` (pada Redis modern) dari daftar antrean. `BLMOVE` memindahkan referensi job ke *processing list* secara atomik untuk mencegah kehilangan data jika worker mati mendadak (*crash*).
   - **Antrean Terjadwal & Retry**: Disimpan dalam Redis `ZSET` (`schedule` dan `retry`). Nilai *score* adalah Unix timestamp milidetik kapan job boleh dijalankan. Thread terjadwal (`Sidekiq::Scheduled::Poller`) melakukan evaluasi berkala menggunakan `ZRANGEBYSCORE` dan memindahkannya ke `LIST` aktif via transaksi atomik Redis (menggunakan skrip Lua).

2. **Database-backed (Solid Queue - Rails 8 Standard)**:
   - Menghilangkan dependensi Redis dengan memanfaatkan indeks modern PostgreSQL/MySQL.
   - Menggunakan tabel relasional (`solid_queue_ready_executions`) dan klausa `SELECT ... FOR UPDATE SKIP LOCKED`.
   - Thread worker mengunci baris data berikutnya yang belum diproses secara atomik tanpa memblokir thread worker lain. Jika worker mati, job yang terkunci secara otomatis kembali tersedia segera setelah transaksi basis data di-*rollback* atau terputus (*connection teardown*).

```
[ ActiveJob Client ] 
       │
       ├─► (Serialization via GlobalID) 
       │
       ▼
[ Storage Engine ]
  ├─► [ Redis: ZSET (Scheduled) ] ──(Poller / Lua)──► [ Redis: LIST (Ready) ]
  │                                                           │
  │                                                        BLMOVE
  │                                                           ▼
  └─► [ DB: Solid Queue (SKIP LOCKED) ] ──────────────► [ Worker Threads ]
```

#### B. ActiveJob Serialization & GlobalID

Rails mengabstraksi objek kompleks menggunakan **GlobalID**. Jika Anda mempassing instance ActiveRecord ke job:
```ruby
OrderFinalizerJob.perform_later(order)
```
Rails tidak mendokumentasikan state memori objek tersebut ke antrean, melainkan melakukan serialisasi representasi URI:
```json
{
  "job_class": "OrderFinalizerJob",
  "job_id": "8c45f470-36ba-4fef-92e1-80775a2ad0ee",
  "queue_name": "critical",
  "arguments": [
    {
      "_aj_globalid": "gid://enterprise-app/Order/10492"
    }
  ]
}
```
Saat deserialisasi pada sisi worker, ActiveJob memanggil `GlobalID::Locator.locate(gid)`. 
*Implikasi Arsitektural*: State objek tidak dibekukan pada saat *enqueue*. Jika baris basis data diubah atau dihapus oleh transaksi lain sebelum worker mengeksekusi job, worker akan mengambil state terbaru dari basis data atau memicu exception `ActiveJob::DeserializationError`.

#### C. Memory Lifecycle, Thread Pool & Database Connection Pooling

Sidekiq mengeksekusi multiple threads di dalam satu proses Ruby tunggal (menggunakan `Concurrent::ThreadPoolExecutor`). Hal ini memunculkan tantangan kritikal pada alokasi sumber daya:

1. **Ukuran Pool Basis Data**:
   Formula alokasi connection pool `ActiveRecord` pada worker:
   $$\text{ActiveRecord Pool Size} \ge \text{Sidekiq Concurrency (Threads)} + \text{Internal Reserved Connections (Opsional: 1-2)}$$
   Jika konfigurasi `database.yml` menetapkan `pool: 5` sementara Sidekiq berjalan dengan `concurrency: 20`, thread ke-6 yang membutuhkan akses IO ke basis data akan mengalami timeout (`ActiveRecord::ConnectionTimeoutError`).

2. **Memory Fragmentation & Jemalloc**:
   Ruby MRI menggunakan glibc allocator standar yang rentan terhadap fragmentasi memori heap jangka panjang pada arsitektur multi-thread intensif. Alokasi dan dealokasi jutaan string/hash payload job menyebabkan RSS (Resident Set Size) proses membengkak (*memory bloat*).
   *Solusi Produksi*: Mengganti allocator sistem dengan **jemalloc** via `LD_PRELOAD`:
   ```bash
   export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.2
   export MALLOC_CONF="dirty_decay_ms:1000,narenas:2,background_thread:true"
   ```

3. **POSIX Signals & Graceful Termination**:
   - `SIGTSTP`: Menginstruksikan Sidekiq untuk berhenti mengambil job baru dari antrean (status *quieting*). Digunakan saat memulai deployment.
   - `SIGTERM`: Menginstruksikan worker untuk menyelesaikan job yang sedang berjalan dalam batas batas waktu tertentu (`-t timeout`, default 25 detik). Jika batas waktu terlampaui, job diputus paksa dan dikembalikan ke antrean via mekanisme requeueing.
   - `SIGKILL`: Terminasi paksa oleh OS/Kubernetes (jika `SIGTERM` melebihi `terminationGracePeriodSeconds`).

---

### 4. Why & What

| Dimensi | Pendekatan Naif (Development) | Pendekatan Enterprise (Production-Grade) |
| :--- | :--- | :--- |
| **Idempotensi** | Mengasumsikan eksekusi tepat satu kali (*exactly-once*). | Mengasumsikan eksekusi minimal satu kali (*at-least-once*); proteksi via *distributed locking* dan *unique payload keys*. |
| **Koneksi Database** | Mengabaikan limit pool; satu koneksi global dibagi rata. | Perhitungan matematis ketat per proses worker; monitoring utilisasi checkout pool. |
| **Memory Management** | Mengabaikan fragmentasi; me-restart worker via cron jika kehabisan RAM. | Integrasi Jemalloc; isolasi thread; deteksi kebocoran memori dengan batasan degradasi terkontrol. |
| **Error Handling** | Mengandalkan retry otomatis default tanpa isolasi poison-pill. | *Dead Letter Queues* (DLQ), *Exponential Backoff with Jitter*, dan Circuit Breaker pattern. |
| **Observability** | Hanya logging teks standar ke STDOUT. | Tracing terdistribusi OpenTelemetry dengan propagasi trace ID melewati batas asynchronous. |

---

### 5. How (Workflow Detail)

Siklus hidup job enterprise dari inisiasi hingga terminasi:

```
[ Web Request Context ]
  │
  ├─ 1. DB Transaction Dimulai
  ├─ 2. Penulisan State Entitas
  ├─ 3. Enqueue via `after_commit` Callback (Mencegah Race Condition)
  └─ 4. DB Commit Sukses
         │
         ▼
[ Ingestion Layer (Redis / Solid Queue) ]
  │
  ├─ 5. Simpan JSON Payload + OpenTelemetry Context Metadata
  └─ 6. Notifikasi Antrean Siap (LIST push / Table index update)
         │
         ▼
[ Worker Node Execution ]
  │
  ├─ 7. Thread Worker Menarik Payload (BLMOVE / FOR UPDATE SKIP LOCKED)
  ├─ 8. Deserialisasi Argumen (GlobalID resolution dari DB)
  ├─ 9. Akusisi Distributed Mutex Lock (Mencegah Duplikasi)
  ├─ 10. Eksekusi Unit of Work dalam Sandbox Transaction
  │      ├─ SUKSES: Release Lock ➔ Tandai Selesai ➔ Emisi Metrik
  │      └─ GAGAL: Tangkap Exception ➔ Evaluasi Retry Strategy
  │           ├─ Retry Eligible: Masukkan ke ZSET dengan Backoff Jitter
  │           └─ Max Retries Exceeded: Pindahkan ke Dead-Letter Queue (DLQ)
  └─ 11. Bersihkan State Thread (Connection Pool Checkin, Clear MDC context)
```

---

### 6. Analogy & Diagram ASCII

Bayangkan sistem penanganan bagasi otomatis di bandara internasional:
- **Web App**: Petugas check-in yang mencetak boarding pass dan menempelkan tag barcode RFID pada koper (GlobalID). Petugas tidak membawa koper ke landasan pacu; ia meletakkannya di ban berjalan.
- **Queue Engine**: Ban berjalan terisolasi dengan sensor optik (Redis/Solid Queue). Jika jalur A penuh, koper dialihkan ke holding area (ZSET scheduled).
- **Worker Process**: Truk kontainer bagasi yang membawa beberapa staf penangan bagasi (Threads). Truk ini membutuhkan bahan bakar khusus (Database Connection Pool). Jika ada 10 staf tetapi hanya tersedia 3 pasang sarung tangan khusus (koneksi DB), 7 staf lainnya menganggur dan menghambat operasi.
- **Idempotency Key**: Pengecekan barcode sebelum koper masuk palka pesawat. Jika koper identik sudah masuk palka sebelumnya, koper duplikat langsung dialihkan ke ruang pemeriksaan tanpa dimuat ulang.

```
       [ WEB CONTAINER ]                    [ INFRASTRUCTURE LAYER ]
┌──────────────────────────────┐          ┌───────────────────────────┐
│ Puma Thread #1               │          │ Redis Engine              │
│  │                           │          │                           │
│  ├─ ActiveRecord Save (Order)│          │ ┌───────────────────────┐ │
│  └─ Enqueue Job ─────────────┼─────────►│ │ List: queue:payments  │ │
│     (after_commit)           │          │ └──────────┬────────────┘ │
└──────────────────────────────┘          └────────────┼──────────────┘
                                                       │ BLMOVE
                                                       ▼
[ SIDEKIQ WORKER PROCESS (PID: 40102, Allocator: Jemalloc) ]
┌─────────────────────────────────────────────────────────────────────┐
│ Thread Pool (Concurrency = 5)                                       │
│                                                                     │
│ ┌──────────────────────────┐    Acquire Lock    ┌─────────────────┐ │
│ │ Worker Thread #1         ├───────────────────►│ Redis Redlock   │ │
│ │  ├─ GlobalID Deserializer│                    │ (TTL: 30s)      │ │
│ │  ├─ DB Checkout (Pool: 5)│                    └─────────────────┘ │
│ │  ├─ Business Logic       │                             ▲          │
│ │  └─ DB Checkin           │                             │          │
│ └──────────────────────────┘                             │          │
│ ┌──────────────────────────┐                             │          │
│ │ Worker Thread #2         ├─────────────────────────────┘          │
│ │  └─ Blocked on Mutex...  │                                        │
│ └──────────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Fundamental Idiomatic ActiveJob

Contoh sederhana ini menunjukkan deklarasi job standar dengan penanganan retry mendasar bawaan ActiveJob.

```ruby
# app/jobs/simple_notification_job.rb
class SimpleNotificationJob < ApplicationJob
  queue_as :default

  # Konfigurasi retry eksponensial dengan jitter bawaan Rails
  retry_on Net::OpenTimeout, Timeout::Error, attempts: 5, wait: :exponentially_longer
  discard_on ActiveJob::DeserializationError

  def perform(user_id, message)
    user = User.find(user_id)
    NotificationService.send_push(user: user, message: message)
  end
end
```

#### B. Practical Example: Enterprise-Grade Order Settlement Job

Contoh produksi berikut mengintegrasikan:
- Distributed locking via Redis (Redlock pattern).
- Observabilitas terdistribusi (Trace propagation via OpenTelemetry).
- Penanganan koneksi database yang aman.
- Mekanisme idempotensi berbasis Redis cache key.
- Custom exponential backoff dengan jitter.

```ruby
# app/jobs/settle_order_job.rb
# frozen_string_literal: true

require "securerandom"

class SettleOrderJob < ApplicationJob
  queue_as :critical

  # Isolasi failure domain: Jangan retry jika data mendasar rusak
  discard_on ArgumentError, ActiveJob::DeserializationError

  # Retry kustom untuk kegagalan transien (Jaringan / HTTP Gateway)
  retry_on PaymentGateway::NetworkError, attempts: 5, wait: ->(executions) {
    # Full Jitter Strategy: Exponential + Random Component
    # Formula: sleep = min(cap, base * 2 ** executions) * rand
    base = 2
    factor = base**executions
    jitter = rand(0.5..1.5)
    [300, (factor * jitter).round].min
  }

  # Definisikan lifecycle hook untuk audit tracing
  around_perform do |job, block|
    trace_id = job.arguments.last.is_a?(Hash) ? job.arguments.last[:trace_id] : nil
    SemanticLogger.tagged(trace_id: trace_id || SecureRandom.uuid) do
      Rails.logger.info("Memulai eksekusi #{job.class.name} [ID: #{job.job_id}]")
      start_time = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      
      block.call
      
      duration = Process.clock_gettime(Process::CLOCK_MONOTONIC) - start_time
      Rails.logger.info("Selesai eksekusi #{job.class.name} dalam #{duration.round(4)}s")
    end
  end

  def perform(order_id, idempotency_key, metadata = {})
    @idempotency_key = idempotency_key
    
    # 1. Akuisisi Distributed Lock
    lock_key = "locks:settle_order:#{order_id}"
    lock_acquired = acquire_distributed_lock(lock_key, ttl_seconds: 45)

    unless lock_acquired
      Rails.logger.warn("Gagal mendapatkan lock untuk #{lock_key}. Menunda eksekusi...")
      # Re-enqueue dengan delay kecil agar tidak memicu throttling ekstrim
      self.class.set(wait: 3.seconds).perform_later(order_id, idempotency_key, metadata)
      return
    end

    begin
      # 2. Idempotency Check: Pastikan transaksi belum pernah diselesaikan
      if settlement_already_processed?(idempotency_key)
        Rails.logger.info("Idempotency match: Order #{order_id} sudah diproses. Eksekusi dilewati.")
        return
      end

      # 3. Transaksi Bisnis Utama
      Order.transaction do
        order = Order.lock("FOR UPDATE").find(order_id)

        if order.settled?
          Rails.logger.warn("Order #{order_id} berada pada state settled tapi settlement key belum terdaftar.")
          register_settlement(idempotency_key, order.id)
          return
        end

        # Eksekusi via Payment Gateway
        gateway_response = PaymentGateway::Client.charge(
          amount: order.total_cents,
          currency: order.currency,
          idempotency_token: idempotency_key
        )

        order.update!(
          status: :settled,
          settled_at: Time.current,
          gateway_reference: gateway_response.transaction_id
        )

        # 4. Registrasi Idempotency Marker (TTL 7 hari)
        register_settlement(idempotency_key, order.id)
      end
    ensure
      release_distributed_lock(lock_key)
    end
  end

  private

  def redis_client
    @redis_client ||= Redis.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/1"))
  end

  def acquire_distributed_lock(key, ttl_seconds:)
    # Menggunakan SET resource value NX PX (Atomic distributed lock)
    @lock_token = SecureRandom.hex(16)
    redis_client.set(key, @lock_token, nx: true, ex: ttl_seconds)
  end

  def release_distributed_lock(key)
    # Gunakan skrip Lua untuk memastikan pelepasan lock yang atomik (hanya hapus jika token cocok)
    lua_script = <<~LUA
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    LUA

    redis_client.eval(lua_script, keys: [key], argv: [@lock_token])
  rescue StandardError => e
    Rails.logger.error("Gagal melepaskan lock untuk #{key}: #{e.message}")
  end

  def settlement_already_processed?(key)
    redis_client.exists?("idempotency:settlement:#{key}")
  end

  def register_settlement(key, order_id)
    redis_client.set("idempotency:settlement:#{key}", order_id, ex: 7.days.to_i)
  end
end
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Perusahaan**: E-commerce Unicorn Tier-1 di Asia Tenggara.
- **Event**: Flash Sale 11.11.
- **Skala Trafik**: 85.000 job per detik pada peak time.
- **Tumpukan Teknologi**: Sidekiq Pro, AWS ElastiCache Redis Cluster (Multi-AZ), 120 Pods Worker Kubernetes (Ruby MRI 3.3).

#### Problem Breakdown: Incident Cascading Failure
Pada menit ke-3 flash sale, latensi processing melonjak dari 150ms menjadi 42 detik. Antrean menumpuk hingga 4.200.000 job dalam waktu 10 menit.
1. **Analisis Akar Masalah (Root Cause)**:
   - Beberapa developer menggunakan callback `after_save :enqueue_fulfillment` alih-alih `after_commit`. Worker thread membaca record database yang belum selesai di-commit oleh web thread, memicu ribuan exception `ActiveRecord::RecordNotFound`.
   - Exception yang membludak memicu *retry storm*. Sidekiq memindahkan jutaan job ke antrean `retry`, membebani CPU Redis hingga 100% akibat eksekusi skrip evaluasi `ZREMRANGEBYSCORE`.
   - Pool koneksi basis data worker saturasi: Worker memegang koneksi DB sembari menunggu respons lambat dari Payment Gateway eksternal (3-5 detik), mengakibatkan thread worker lain mengalami kelaparan koneksi (*connection starvation*).

#### Solusi Arsitektural Terpadu
1. **Queue Isolation & Priority Partitioning**:
   Memecah satu antrean raksasa menjadi kluster independen:
   - `queue:critical` (Settlement & Payment Callback) -> Bobot alokasi thread 60%
   - `queue:mailers` (Email & Push Notification) -> Bobot alokasi thread 10%
   - `queue:webhooks` (Integrasi Logistik Pihak Ketiga) -> Bobot alokasi thread 30%
2. **Perbaikan Transaksional**:
   Standardisasi strict penggunaan `after_commit` untuk pemanggilan job:
   ```ruby
   # Pola Benar
   after_commit :enqueue_fulfillment, on: :create
   ```
3. **Penyelarasan Timeout dan Isolasi IO**:
   Menurunkan HTTP client timeout ke payment gateway dari 10 detik ke 1.5 detik dengan *circuit breaker* (memutus permintaan jika 50 error berturut-turut tercapai).
4. **Penerapan Dynamic Backpressure Control**:
   Worker secara otomatis memperlambat ingestion jika memory Redis menyentuh 80% capacity atau database query queue time melebihi 200ms.

---

### 9. Trade-offs

| Dimensi Arsitektural | Pendekatan A | Pendekatan B | Analisis Komparasi |
| :--- | :--- | :--- | :--- |
| **Backend Broker** | **Redis (Sidekiq)** | **Postgres/MySQL (Solid Queue)** | Redis unggul dalam latensi throughput ekstrem (>50k ops/sec) dan memory throughput, namun membutuhkan infrastruktur terpisah dan mitigasi kehilangan data memori (AOF/RDB). Solid Queue memotong biaya operasional infra secara signifikan dan menjamin ACID, tetapi meningkatkan *write-amplification* dan bloat pada WAL/Primary DB. |
| **Model Eksekusi** | **Multi-Threading (Sidekiq)** | **Multi-Processing (Resque/GoodJob Worker)** | Multi-threading hemat RAM via memory sharing, tetapi rentan terhadap GVL lockouts untuk tugas CPU-bound dan thread safety bugs. Multi-processing mengisolasi memori total antar proses secara absolut, namun konsumsi RAM membengkak 4x - 8x lipat. |
| **Penyimpanan State Idempotency** | **Redis Key-Value Cache** | **Database Unique Constraints** | Redis KV menawarkan performa cek O(1) non-blocking tanpa overhead I/O disk, namun berisiko inkonsistensi jika Redis mengalami eviksi data (*LRU Eviction*). DB Unique Constraints memberikan konsistensi ACID 100%, tetapi membebani indeks relasional B-Tree pada scale besar. |
| **Tingkat Retensi Job** | **Persist All Execution Logs** | **Prune on Completion (Default)** | Menyimpan seluruh log eksekusi memungkinkan auditabilitas dan debugging menyeluruh, tetapi membebani storage secara eksponensial. Menghapus state job yang selesai secara langsung menjaga overhead sistem tetap minimal. |

---

### 10. Common Mistakes & Troubleshooting

#### Antipattern 1: Enqueue di dalam Transaksi Database Aktif
*Kesalahan*:
```ruby
ActiveRecord::Base.transaction do
  order = Order.create!(order_params)
  # BUG: Job diambil worker sebelum transaksi di DB selesai di-commit!
  ProcessPaymentJob.perform_later(order.id)
end
```
*Dampak*: Worker melempar error `ActiveRecord::RecordNotFound` karena job dieksekusi lebih cepat daripada proses commit transaksi web app ke disk database.
*Solusi*: Gunakan callback `after_commit` atau passing job hanya setelah blok transaksi sukses:
```ruby
order = nil
ActiveRecord::Base.transaction do
  order = Order.create!(order_params)
end
ProcessPaymentJob.perform_later(order.id)
```

#### Antipattern 2: Thread-Safety Violation via Class-Level Variables
*Kesalahan*:
```ruby
class ReportGeneratorJob < ApplicationJob
  def perform(report_id)
    # BUG CRITICAL: Variabel class diekspos ke seluruh thread di dalam worker process yang sama!
    @@current_report = Report.find(report_id)
    generate_pdf!
  end
end
```
*Dampak*: Race condition data corruption. Data user A bercampur dengan data user B secara acak saat dieksekusi bersamaan.
*Solusi*: Gunakan local variables, instance variables, atau thread-safe storage (`Concurrent::ThreadLocalVar`).

#### Antipattern 3: Parameter Object yang Sangat Besar (Mega-Payloads)
*Kesalahan*:
```ruby
# BUG: Mengirimkan raw CSV base64 string 15MB ke dalam payload job
ImportCsvJob.perform_later(csv_data_string)
```
*Dampak*: Saturasi memori Redis, peningkatan latensi serialisasi JSON, dan pembengkakan heap Ruby yang memicu GC pause masif.
*Solusi*: Simpan file di object storage (S3/GCS), pass URI/Key referensinya ke dalam job.

#### Panduan Troubleshooting Operasional
1. **Indikator**: *High Redis Memory Usage & Worker Starvation*
   - Cek antrean: `Sidekiq::Queue.new.size` dan `Sidekiq::RetrySet.new.size`.
   - Analisis memory: Jalankan `redis-cli --bigkeys` untuk mendeteksi key payload monster.
2. **Indikator**: `ActiveRecord::ConnectionTimeoutError: could not obtain a connection from the pool within 5.000 seconds`
   - Buka `config/database.yml`.
   - Pastikan alokasi pool: `pool: <%= ENV.fetch("RAILS_MAX_THREADS", 5).to_i + 2 %>`.
   - Cari blok kode yang melakukan leak koneksi (misal eksekusi multi-thread manual di dalam job tanpa membungkus dengan `ActiveRecord::Base.connection_pool.with_connection`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Gunakan Jemalloc**: Inject Jemalloc pada Dockerfile/App Runner untuk meminimalisir fragmentasi alokasi memory heap Ruby.
- [ ] **Alokasikan Connection Pool Sesuai Rumus**: Formula: `DB Pool Size >= Sidekiq Concurrency + 2`.
- [ ] **Passing ID, Bukan Object Utuh**: Mengandalkan `GlobalID` serialization untuk memastikan data konsisten dari database pada saat eksekusi worker.
- [ ] **Konfigurasi Maximum Memory Policy pada Redis**: Set `maxmemory-policy noeviction` untuk Redis Job Queue guna mencegah hilangnya job secara diam-diam (*silent drop*).
- [ ] **Terapkan Absolute Idempotency**: Setiap job yang mengubah state keuangan atau inventaris harus memiliki *Distributed Lock* dan *Idempotency Check*.
- [ ] **Implementasikan Dead Letter Queue (DLQ)**: Arahkan job yang gagal setelah batas maksimal retry ke dead-letter queue khusus untuk diinspeksi manual tanpa menghentikan antrean utama.
- [ ] **Setup Posix Signal Handling**: Konfigurasi Kubernetes Pod `terminationGracePeriodSeconds` minimal 30 detik untuk memberikan waktu Sidekiq memproses `SIGTERM` dengan aman.
- [ ] **Terapkan Healthcheck Worker**: Sediakan probe liveness yang memonitor detak jantung (*heartbeat*) proses worker ke Redis.

---

### 12. Hands-on Practice

Implementasikan environment background processing tingkat produksi menggunakan Sidekiq, Redis, dan Idempotency Middleware. Simpan seluruh file di bawah direktori `hands-on/m02/`.

#### Langkah 1: Inisialisasi Konfigurasi Sidekiq Tingkat Lanjut
Buat file `hands-on/m02/config/sidekiq.yml`:
```yaml
# hands-on/m02/config/sidekiq.yml
:concurrency: <%= ENV.fetch("SIDEKIQ_CONCURRENCY", 10) %>
:timeout: 25
:queues:
  - [critical, 6]
  - [default, 3]
  - [low_priority, 1]

:max_retries: 5
```

#### Langkah 2: Buat Idempotency Server Middleware
Buat file `hands-on/m02/app/middleware/sidekiq_server_idempotency.rb`:
```ruby
# hands-on/m02/app/middleware/sidekiq_server_idempotency.rb
# frozen_string_literal: true

module Middleware
  class SidekiqServerIdempotency
    def call(worker, job, queue)
      # Ambil idempotency key dari argumen jika ada
      idempotency_key = extract_idempotency_key(job["args"])
      
      if idempotency_key
        redis = Redis.new(url: ENV.fetch("REDIS_URL", "redis://localhost:6379/1"))
        lock_key = "job_lock:#{worker.class.name}:#{idempotency_key}"
        
        # Coba pasang lock selama eksekusi (TTL 60 detik)
        acquired = redis.set(lock_key, job["jid"], nx: true, ex: 60)
        
        unless acquired
          existing_jid = redis.get(lock_key)
          # Jika job yang sama sedang berjalan, skip eksekusi duplikat
          Sidekiq.logger.warn("Pencegahan eksekusi duplikat: #{job['class']} [JID: #{job['jid']}]. Sedang diproses oleh JID: #{existing_jid}")
          return false
        end

        begin
          yield
        ensure
          redis.del(lock_key)
        end
      else
        yield
      end
    end

    private

    def extract_idempotency_key(args)
      args.each do |arg|
        return arg["idempotency_key"] if arg.is_a?(Hash) && arg.key?("idempotency_key")
      end
      nil
    end
  end
end
```

#### Langkah 3: Registrasi Middleware pada Initializer
Buat file `hands-on/m02/config/initializers/sidekiq.rb`:
```ruby
# hands-on/m02/config/initializers/sidekiq.rb
require_relative "../../app/middleware/sidekiq_server_idempotency"

Sidekiq.configure_server do |config|
  config.redis = { url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0") }
  
  # Daftarkan middleware
  config.server_middleware do |chain|
    chain.add Middleware::SidekiqServerIdempotency
  end
end

Sidekiq.configure_client do |config|
  config.redis = { url: ENV.fetch("REDIS_URL", "redis://localhost:6379/0") }
end
```

#### Langkah 4: Buat Job Transaksional Berdaya Tahan Tinggi
Buat file `hands-on/m02/app/jobs/inventory_deduction_job.rb`:
```ruby
# hands-on/m02/app/jobs/inventory_deduction_job.rb
class InventoryDeductionJob < ApplicationJob
  queue_as :critical

  retry_on Timeout::Error, attempts: 3, wait: :exponentially_longer

  def perform(item_id, quantity, options = {})
    idempotency_key = options[:idempotency_key]
    
    ActiveRecord::Base.connection_pool.with_connection do
      Item.transaction do
        item = Item.lock("FOR UPDATE").find(item_id)
        
        # Validasi stok
        if item.available_stock < quantity
          raise "StockInsufficient: Stok item #{item_id} tidak mencukupi."
        end

        item.decrement!(:available_stock, quantity)
        Rails.logger.info("Sukses memotong #{quantity} unit untuk item #{item_id}. Sisa: #{item.available_stock}")
      end
    end
  end
end
```

---

### 13. Exercise

Kerjakan tiga latihan berikut dengan tingkat kesulitan bertingkat:

#### Easy
- **Tugas**: Buat custom job `UserWelcomeNotificationJob` yang mengirim email via API pihak ketiga.
- **Kriteria Validasi**: Terapkan penanganan exception jika email tujuan invalid (`ArgumentError`), job tidak boleh di-retry dan langsung di-discard tanpa memunculkan failed metrics di Sidekiq.

#### Medium
- **Tugas**: Implementasikan circuit breaker pattern manual di dalam job `CurrencyExchangeRateSyncJob` yang melakukan scraping ke API publik eksternal yang tidak stabil.
- **Kriteria Validasi**: Jika pemanggilan gagal 3 kali berturut-turut, tandai state circuit breaker pada Redis sebagai `:open` selama 5 menit. Jika ada job yang terpanggil pada masa `:open`, gagalkan atau tunda eksekusi seketika (*fail-fast*) tanpa membuka koneksi HTTP baru.

#### Hard
- **Tugas**: Bangun sistem deduplikasi dinamis pada level antrean (`Sidekiq Unique Arguments`).
- **Kriteria Validasi**: Cegah job identik (misal: `GenerateMonthlyInvoiceJob(company_id: 42)`) masuk ke antrean jika job dengan `company_id` yang sama sudah ada di antrean `default`, antrean `scheduled`, atau sedang diproses oleh worker lain. Gunakan Redis primitives (`SETNX`, `EXPIRE`) tanpa menggunakan gem pihak ketiga.

---

### 14. Challenge

#### Skenario Kasus Kompleks: "The Global Reconciliation Engine"

Sebuah bank digital multi-nasional memproses jutaan transaksi mikro setiap hari. Pada setiap akhir siklus harian (pukul 23:59:00 UTC), sistem harus menjalankan rekonsiliasi data dari 3 gateway eksternal (Visa, Mastercard, Bank Sentral) dan mencocokkannya dengan buku besar (*ledger*) internal di basis data relasional utama.

**Spesifikasi Tantangan**:
1. **Volumetrik**: 15.000.000 record harus divalidasi dalam waktu maksimal 45 menit.
2. **Keterbatasan Sumber Daya**: Basis data utama hanya mampu melayani maksimal 60 koneksi simultan dari cluster worker background job untuk mencegah penurunan performa transaksi core banking.
3. **Persyaratan Toleransi Bencana (*Disaster Recovery*)**:
   - Jika node worker mati mendadak di tengah rekonsiliasi batch (misal: Kubernetes evicted node karena OOM), sistem harus dapat melanjutkan proses dari batch parsial yang belum selesai tanpa melakukan rekonsiliasi ulang record yang telah valid.
   - Tidak boleh ada data yang terhitung ganda (*zero tolerance on balance divergence*).
   - Seluruh siklus eksekusi harus memancarkan metrik *throughput-per-second* dan *discrepancy-count* via statsd/Prometheus exporter secara *thread-safe*.

**Deliverable**:
Rancang arsitektur sistem worker lengkap menggunakan kombinasi:
- Sharding / Batch Slicing Pattern.
- Two-phase state acknowledgement.
- Redis-backed checkpointing.
- Penanganan connection pool throttling.
(Sertakan diagram arsitektur komponen, konfigurasi pool database, dan pseudocode / implementasi Rails Job lengkap yang memproteksi integritas rekonsiliasi).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)

1. Apa bahaya utama melakukan serialisasi objek utuh `ActiveRecord` ke dalam antrean background job dibandingkan hanya mengoper ID-nya?
   - A. Ukuran Redis payload menjadi lebih kecil.
   - B. Terjadi inkonsistensi state jika data di DB berubah sebelum job dieksekusi, serta membebani antrean.
   - C. GlobalID secara otomatis menghapus database record.
   - D. Menurunkan alokasi pool koneksi database.

2. Klausa SQL apa yang digunakan oleh Solid Queue pada PostgreSQL/MySQL untuk mencegah dua worker mengunci dan mengeksekusi job yang sama secara bersamaan?
   - A. `LOCK TABLE READ ONLY`
   - B. `SELECT ... FOR UPDATE SKIP LOCKED`
   - C. `SELECT ... WHERE processed = false`
   - D. `TRUNCATE TABLE READY_EXECUTIONS`

3. Mengapa konfigurasi `after_commit` lebih direkomendasikan daripada `after_save` saat melakukan enqueue background job?
   - A. `after_commit` berjalan lebih cepat daripada `after_save`.
   - B. `after_save` tidak memiliki akses ke instance variables.
   - C. `after_commit` menjamin data sudah permanen tersimpan di database sebelum worker mencoba membacanya.
   - D. `after_save` hanya berjalan pada operasi update, bukan insert.

4. Sinyal POSIX apa yang dikirimkan ke proses Sidekiq untuk memerintahkannya berhenti mengambil job baru dari antrean (tahap awal *graceful shutdown*)?
   - A. `SIGKILL`
   - B. `SIGINT`
   - C. `SIGTSTP`
   - D. `SIGHUP`

5. Apa fungsi utama penggunaan memory allocator `jemalloc` pada proses background worker Ruby?
   - A. Meningkatkan kecepatan clock rate CPU.
   - B. Menghilangkan kebutuhan akan Global VM Lock (GVL).
   - C. Mengurangi fragmentasi memori heap jangka panjang dan memory bloat pada worker multi-thread.
   - D. Melakukan enkripsi otomatis pada payload Redis.

#### Intermediate (5 Soal)

6. Sebuah instance Sidekiq dikonfigurasi dengan `concurrency: 25`. Pada `database.yml`, nilai `pool` disetel ke `10`. Apa yang akan terjadi jika 20 job dijalankan serentak dan seluruhnya mengakses database?
   - A. Sidekiq secara otomatis mematikan 15 thread sisanya.
   - B. 10 thread pertama berjalan sukses, sedangkan 10 thread berikutnya melempar `ActiveRecord::ConnectionTimeoutError` setelah menunggu timeout.
   - C. Database PostgreSQL akan crash karena overload.
   - D. Rails secara dinamis memperbesar pool size ke 25 pada runtime.

7. Mengapa penambahan komponen *Jitter* sangat krusial dalam algoritma *Exponential Backoff* retry pada sistem terdistribusi skala besar?
   - A. Agar waktu tunggu retry menjadi lebih singkat secara konsisten.
   - B. Menghindari fenomena *Thundering Herd* di mana ribuan worker me-retry koneksi ke layanan yang sama pada detik yang persis bersamaan.
   - C. Untuk menghitung selisih pembagian payload JSON secara dinamis.
   - D. Memastikan memori redis segera dibebaskan sebelum job dieksekusi.

8. Apa implikasi teknis dari penerapan `discard_on ActiveJob::DeserializationError` pada sebuah Job?
   - A. Job akan terus di-retry tanpa batas waktu sampai record ditemukan.
   - B. Job akan langsung dibuang secara senyap jika record ActiveRecord yang dirujuk oleh GlobalID telah dihapus dari database.
   - C. Worker akan me-restart dirinya sendiri untuk memuat ulang cache memori.
   - D. Record di database akan di-rollback ke state sebelum transaksi terjadi.

9. Manakah skrip Redis di bawah ini yang menjamin pelepasan *Distributed Lock* secara atomik hanya jika pemegang kunci adalah pemilik aslinya?
   - A. `redis.del("lock_key")`
   - B. `redis.get("lock_key") == token ? redis.del("lock_key") : nil`
   - C. Skrip Lua yang mengevaluasi `if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end`
   - D. `redis.set("lock_key", token, xx: true)`

10. Apa kegunaan utama dari *Tracing Context Propagation* (misalnya menggunakan OpenTelemetry) pada pemanggilan background job?
    - A. Mempercepat serialisasi JSON payload pada Redis.
    - B. Meneruskan metadata trace ID dan span ID dari HTTP Web Request ke Worker Background Job agar visualisasi tracing dapat terhubung *end-to-end*.
    - C. Menggandakan data job ke multiple cluster region secara paralel.
    - D. Menghindari kebutuhan akan logging manual di STDOUT.

#### Production Scenario (3 Soal)

11. **Skenario Kasus 1**: Pada deployment baru, sebuah tim menambahkan job `SendDailyDigestEmailJob` yang memproses 500.000 subscriber pada pukul 08:00 pagi ke antrean `default`. Akibatnya, job verifikasi pembayaran instan via SMS OTP yang juga berada di antrean `default` tertunda hingga 45 menit. Tindakan mitigasi arsitektur apa yang paling tepat dan permanen?
    - A. Menambah memori server Redis menjadi 2x lipat.
    - B. Memisahkan antrean menjadi `critical` (untuk OTP) dan `bulk` (untuk email digest), lalu mengatur prioritas pembobotan antrean pada worker Sidekiq (`sidekiq -q critical,6 -q bulk,1`).
    - C. Mengubah queue backend dari Redis ke SQLite.
    - D. Memaksa `SendDailyDigestEmailJob` dieksekusi secara sinkronus di dalam controller thread.

12. **Skenario Kasus 2**: Sistem Worker Kubernetes Anda menerima sinyal `SIGTERM` saat proses rolling deployment. Namun, beberapa job berdurasi panjang (membutuhkan waktu 50 detik) terpotong paksa di tengah jalan pada detik ke-30, meninggalkan data status order yang menggantung (*orphan processing state*). Konfigurasi apa yang harus diperbaiki?
    - A. Menurunkan timeout Sidekiq (`-t`) menjadi 5 detik.
    - B. Menyesuaikan `terminationGracePeriodSeconds` pada manifest Kubernetes menjadi lebih besar (misal 65 detik) dan memastikan konfigurasi timeout Sidekiq (`-t 60`) selaras dengan batas toleransi tersebut.
    - C. Menghapus readiness probe dari konfigurasi pod Kubernetes.
    - D. Mengubah strategi deployment dari `RollingUpdate` menjadi `Recreate`.

13. **Skenario Kasus 3**: Worker mengalami lonjakan alokasi memori yang masif (RSS terus merangkak naik dari 300MB hingga 4GB dalam 2 jam), hingga akhirnya dimatikan secara paksa oleh Linux OOM Killer. Saat profiling, ditemukan bahwa sebuah job membaca jutaan baris data sekaligus menggunakan `User.all.each`. Bagaimana refactor kode yang benar secara kaidah arsitektur enterprise?
    - A. Mengganti `User.all.each` dengan `User.find_each(batch_size: 1000)` untuk melakukan streaming record dalam batch kecil dan membebaskan alokasi memori secara bertahap.
    - B. Menggunakan `User.all.to_a.each` agar seluruh data dimuat langsung ke CPU cache.
    - C. Memperbesar ukuran swap file pada Linux worker node.
    - D. Menjalankan garbage collection manual `GC.start` pada setiap iterasi baris per baris.

---

### Kunci Jawaban Quiz

1. **B** - Serialisasi seluruh object membekukan state kadaluarsa dan memperbesar ukuran payload antrean secara signifikan.
2. **B** - `FOR UPDATE SKIP LOCKED` memungkinkan multiple worker mengambil baris yang belum dikunci secara konkuren tanpa saling memblokir.
3. **C** - Menghindari race condition `RecordNotFound` akibat worker membaca record sebelum database selesai melakukan commit transaksi disk.
4. **C** - `SIGTSTP` memberi instruksi kepada worker untuk *quieting* (berhenti menarik job baru).
5. **C** - Jemalloc mengoptimalkan fragmentasi alokasi chunk memory pada sistem multi-thread intensif di Ruby MRI.
6. **B** - Terjadi saturasi pool. Thread ke-11 dan seterusnya akan terblokir menunggu koneksi bebas hingga batas timeout tercapai lalu crash.
7. **B** - Jitter memecah sinkronisasi retry serempak yang berisiko menumbangkan sistem yang baru saja pulih.
8. **B** - Mencegah failed queue dipenuhi oleh error usang dari record yang memang sengaja telah dihapus dari basis data.
9. **C** - Skrip Lua berjalan atomik di Redis, memastikan kunci hanya dihapus jika token identifikasi kepemilikannya cocok.
10. **B** - Memungkinkan monitoring visibilitas penuh alur eksekusi lintas batas proses (Web Request -> Network Queue -> Worker Execution).
11. **B** - Partisi antrean (*Queue Isolation*) dengan pembobotan prioritas mencegah *head-of-line blocking* dari batch job terhadap job kritis.
12. **B** - Kubernetes mematikan pod secara paksa dengan `SIGKILL` jika eksekusi melebihi batas `terminationGracePeriodSeconds`, sehingga alokasi waktu shutdown harus diselaraskan.
13. **A** - `find_each` mengeksekusi kueri ber-batch menggunakan limit/offset cursor (berbasis ID primary key), menjaga footprint RAM tetap datar dan konstan terlepas dari total jumlah baris data.

---

### 16. Summary

Arsitektur *asynchronous processing* pada tingkat enterprise menuntut pergeseran paradigma dari sekadar "memindahkan komputasi lambat ke background" menuju **rekayasa sistem terdistribusi yang tangguh (*resilient distributed systems*)**. 

Poin-poin arsitektural fundamental yang harus dikuasai:
1. **Model Konkurensi & Alokasi Sumber Daya**: Penyelarasan mutlak antara *worker thread count*, *ActiveRecord database connection pool*, dan pemanfaatan *Jemalloc* untuk mencegah kelaparan koneksi (*starvation*) serta fragmentasi memori (*bloat*).
2. **Integritas Transaksional**: Pemanfaatan konvensi `after_commit` untuk mencegah race conditions saat enqueue, dipadukan dengan *Absolute Idempotency* (Distributed Locks + Idempotency Tokens) guna mengatasi semantik eksekusi *at-least-once*.
3. **Queue Topology & Failure Isolation**: Pemisahan antrean kritis dari batch/low-priority jobs untuk menghindari *head-of-line blocking*, didukung oleh strategi penanganan kegagalan cerdas (*Exponential Backoff with Full Jitter*, *Dead Letter Queues*, dan *Circuit Breakers*).
4. **Observabilitas Holistik**: Propagasi konteks tracing terdistribusi (OpenTelemetry) dan monitoring metrik antrean secara real-time guna mendeteksi degradasi performa sebelum berdampak langsung pada pengguna akhir.