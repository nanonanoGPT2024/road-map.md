# Bab 08: Background Processing & Asynchronous Architecture
## Module 01: Active Job Deep Dive, GlobalID, & Sidekiq Architecture

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Menganalisis siklus hidup eksekusi *background job* dari fase inisiasi HTTP hingga proses konsumsi oleh *worker threads*.
- Mengonfigurasi dan mengoptimalkan integrasi antara Active Job framework dan Sidekiq sebagai *high-throughput execution engine*.
- Mengimplementasikan mekanisme serialisasi dan deserialisasi objek Active Record menggunakan protokol GlobalID secara aman dan bebas dari *stale data*.
- Merancang arsitektur pekerjaan asinkron yang *fault-tolerant*, idempoten, dan tahan terhadap *concurrency race conditions*.
- Memitigasi masalah performa kritis seperti *exhaustion* koneksi basis data, kebocoran memori pada worker proses, dan Redis *queue bloating*.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
- **Active Record Lifecycle & Callbacks**: Pemahaman mendalam tentang transaksi basis data (`after_commit` vs `after_save`).
- **Ruby Concurrency Basics**: Model thread MRI (CRuby), Global VM Lock (GVL), dan karakteristik I/O-bound vs CPU-bound execution.
- **Redis Fundamentals**: Struktur data primitif Redis (Strings, Lists, Sorted Sets, Hashes) dan mekanisme *blocking commands* (`BRPOP`, `ZADD`).
- **HTTP Request-Response Lifecycle**: Batas toleransi latensi gateway (misal: Cloudflare 100s timeout, Heroku 30s timeout) dan mitigasi *Puma thread starvation*.

---

### 3. Concept
Secara arsitektural, web server berbasis Ruby (seperti Puma) mengalokasikan satu thread untuk memproses satu siklus HTTP *request-response*. Operasi I/O lambat (seperti integrasi API pihak ketiga, pembuatan dokumen PDF, pemrosesan citra, atau pengiriman email transaksional) yang dieksekusi secara sinkron di dalam siklus ini akan menahan (*block*) alokasi thread tersebut, mengakibatkan degradasi *throughput* sistem secara dramatis.

Active Job hadir sebagai lapisan abstraksi (*abstraction layer*) standar di dalam Ruby on Rails yang memisahkan definisi pekerjaan logis (*job specification*) dari infrastruktur eksekusi (*queueing backend*). 

```
+-----------------------------------------------------------------------+
|                             Rails Web Tier                            |
|  Controller/Model ---> ActiveJob::Base.perform_later(resource)        |
+-----------------------------------+-----------------------------------+
                                    | (1. Serialize via GlobalID)
                                    v
+-----------------------------------------------------------------------+
|                    Active Job Queue Adapter (Sidekiq)                 |
|  Sidekiq Client ---> JSON Payload Generation                          |
+-----------------------------------+-----------------------------------+
                                    | (2. LPUSH / ZADD)
                                    v
+-----------------------------------------------------------------------+
|                              Redis Storage                            |
|  - Queues: "default", "critical" (Lists)                              |
|  - Scheduled / Retry Sets (Sorted Sets)                               |
+-----------------------------------+-----------------------------------+
                                    | (3. BRPOP / Polling)
                                    v
+-----------------------------------------------------------------------+
|                          Sidekiq Worker Cluster                       |
|  Thread Pool ---> (4. Fetch & Deserialize GlobalID) ---> Execute Code |
+-----------------------------------------------------------------------+
```

Pondasi arsitektur internal dari sistem ini berakar pada tiga pilar:
1. **GlobalID Abstraction**: Active Job tidak menyimpan representasi objek Ruby memory mentah ke broker pesan. Alih-alih melakukan serialisasi biner (seperti `Marshal.dump` yang rawan terhadap kerentanan keamanan RCE dan dependensi status memori), Active Job mengonversi instance Active Record menjadi URI GlobalID (`gid://app-name/ModelName/id`). Ketika worker memproses job, URI ini dideserialisasi via `GlobalID::Locator.locate(gid)` langsung dari basis data.
2. **Adapter Pattern**: Active Job menyediakan API seragam (`perform_later`, `retry_on`, `discard_on`) yang mentranslasikan parameter menjadi representasi JSON terstandarisasi sebelum didelegasikan ke *adapter* pihak ketiga (Sidekiq, Solid Queue, Resque).
3. **Multithreaded Execution Engine (Sidekiq)**: Berbeda dari Resque (berbasis *forking process*), Sidekiq menggunakan arsitektur *multithreaded actor model* di atas satu atau beberapa proses Ruby. Sidekiq menggunakan koneksi Redis persisten untuk menarik *payload* secara atomik menggunakan perintah blocking `BRPOP`.

---

### 4. Why
Menjalankan operasi berat di luar siklus HTTP adalah mandatori dalam rekayasa perangkat lunak skala produksi:
- **Preventing Request Starvation**: Jika Puma dialokasikan 5 worker dengan 5 thread masing-masing (total 25 thread), dan 25 pengguna memicu pengunduhan laporan sinkron yang memakan waktu 4 detik, maka seluruh pool koneksi aplikasi lumpuh secara total. Setiap request baru yang masuk akan tertahan pada soket TCP (*backlog queue*) hingga akhirnya memicu galat `504 Gateway Timeout`.
- **Fault Tolerance & Resilience**: Panggilan jaringan ke eksternal API bersifat tidak deterministik (*flaky*). Eksekusi di background memungkinkan implementasi strategi pemulihan mandiri (*self-healing*) menggunakan *exponential backoff* dan *jitter* tanpa melibatkan pengguna akhir dalam skenario kegagalan.
- **Resource Decoupling & Independent Scaling**: Web tier (CPU-light, network-bound) dan worker tier (CPU-heavy atau memory-intensive) dapat di-scale secara terpisah (*asymmetric horizontal scaling*) berdasarkan beban masing-masing metrik (Web berdasarkan RPS/latensi, Worker berdasarkan *Queue Latency*).

---

### 5. What
Komponen inti dalam ekosistem Active Job dan Sidekiq meliputi:

- **`ActiveJob::Base`**: Kelas dasar yang menyediakan antarmuka terpadu untuk pendefinisian tugas, callback lifecycle (`before_perform`, `after_perform`), dan deklarasi toleransi kegagalan (`retry_on`, `discard_on`).
- **GlobalID (`URI: GlobalID`)**: Komponen penserialisasi yang mengubah instance model menjadi URI yang bersifat *portable*, *app-scoped*, dan *time-insensitive*.
- **Queue Adapter**: Penghubung antara Rails Active Job API dengan API spesifik broker backend (misal: `config.active_job.queue_adapter = :sidekiq`).
- **Sidekiq Client**: Modul Ruby yang berjalan di dalam proses web Rails, bertugas memvalidasi argumen, melakukan serialisasi JSON, dan mengeksekusi operasi `LPUSH` ke queue Redis yang sesuai.
- **Sidekiq Server**: Proses daemon independen yang memelihara *thread pool* pekerja, menarik payload dari Redis, menginisialisasi lingkungan Rails, mengeksekusi logika bisnis, dan menangani kegagalan eksekusi.
- **Redis Queues & Sorted Sets**:
  - `queue:<name>`: List data structure yang menyimpan pekerjaan siap eksekusi (FIFO).
  - `schedule`: Sorted Set berisikan pekerjaan masa depan (`wait: 5.minutes`) dengan skor berupa UNIX timestamp.
  - `retry`: Sorted Set untuk pekerjaan gagal yang dijadwalkan ulang secara otomatis.
  - `dead`: Set khusus untuk pekerjaan yang melampaui batas percobaan maksimum (*Dead Letter Queue*).

---

### 6. How
Berikut adalah alur eksekusi internal dari pemanggilan `perform_later` hingga penyelesaian tugas:

```
[Rails Controller]
       |
       | 1. MyJob.perform_later(order)
       v
[ActiveJob Engine]
       |
       | 2. Serialisasi: order -> "gid://app/Order/42"
       | 3. Konstruksi Hash Job Envelope (UUID, Class, Queue, Args)
       v
[Sidekiq Adapter]
       |
       | 4. Konversi ke Sidekiq JSON format
       v
[(Redis Instance)] <-------------------\
       |                               |
       | 5. LPUSH queue:default {json} | 6. BRPOP queue:default
       v                               |
[Sidekiq Server Thread] ---------------/
       |
       | 7. Deserialisasi JSON Payload
       | 8. GlobalID::Locator.locate("gid://app/Order/42") -> Eksekusi SQL SELECT
       | 9. Instansiasi Job Class & Invokasi perform(order)
       v
[Database Execution & API External Call]
```

1. **Pemanggilan Job**: Kode aplikasi mengeksekusi `InvoiceProcessingJob.perform_later(order)`.
2. **Serialisasi GlobalID**: Active Job memindai array argumen. Saat menemukan objek `ActiveRecord::Base`, modul `ActiveJob::Arguments` mengonversinya menjadi format hash: `{"_aj_globalid" => "gid://billing/Order/42"}`.
3. **Sidekiq Enqueueing**: Sidekiq Client menerima payload hash, membungkusnya dengan metadata Sidekiq (JID, enkripsi, waktu enqueue), mengonversinya ke representasi string JSON murni via `JSON.dump`, dan mengirimkan instruksi atomik `LPUSH queue:high_priority <payload>` ke Redis.
4. **Penyimpanan Redis**: Payload berada di memori Redis dalam antrean list atau ditambahkan ke sorted set `schedule` via `ZADD` jika parameter `wait` disertakan.
5. **Worker Polling (De-queueing)**: Thread di dalam proses Sidekiq Server menjalankan loop tak terbatas (*infinite loop*) yang memanggil `BRPOP queue:high_priority queue:default 2`. Redis memblokir koneksi hingga elemen tersedia atau timeout tercapai.
6. **Eksekusi & Lokalisasi Status**:
   - Thread menerima payload JSON dan melakukan `JSON.parse`.
   - Engine Active Job mendeserialisasi argumen: memanggil `GlobalID::Locator.locate("gid://billing/Order/42")`, yang menerbitkan query `SELECT * FROM orders WHERE id = 42 LIMIT 1`.
   - Menginisiasi rantai callback (`around_perform`, `before_perform`).
   - Mengeksekusi metode `perform(order)`.
7. **Pembersihan atau Penjadwalan Ulang**: Jika terjadi pengecualian (*unhandled exception*), Sidekiq mengintersepsi error tersebut, menghitung interval *exponential backoff*, dan memindahkan payload ke Sorted Set `retry` via `ZADD` dengan skor UNIX timestamp masa depan.

---

### 7. Analogy
Bayangkan operasional sebuah restoran cepat saji:
- **Pendekatan Sinkron**: Kasir menerima pesanan burger mentah dari pelanggan, berjalan ke dapur, menyalakan kompor, memanggang daging selama 10 menit, merakit burger, dan menyerahkannya ke pelanggan. Selama 10 menit tersebut, kasir tidak dapat melayani antrean pelanggan lain. Seluruh antrean tertahan (*starvation*).
- **Pendekatan Asinkron (Active Job & Sidekiq)**:
  - Pelanggan memesan burger.
  - Kasir mencetak tiket pesanan dengan nomor identifikasi unik, misalnya **Order ID #42** (*GlobalID*), lalu menyerahkan tiket tersebut ke dapur (*Redis Queue*) dan memberikan struk penomoran ke pelanggan. Pelanggan segera meninggalkan meja kasir (*HTTP 200 OK / Accepted*). Kasir langsung melayani orang berikutnya dalam hitungan detik.
  - Di dapur, terdapat 4 koki (*Sidekiq Worker Threads*) yang terus-menerus mengambil tiket teratas dari meja pemesanan (*BRPOP*).
  - Koki membaca tiket "Order ID #42", mengambil nampan bahan baku yang sesuai (*GlobalID::Locator*), merakit pesanan, dan menyelesaikannya.
  - Jika kompor dapur gasnya habis (*External API failure*), koki tidak membuang tiket tersebut; koki menjadwalkan ulang tiket ke papan tunda (*Retry Set*) untuk dikerjakan kembali 5 menit kemudian.

---

### 8. Diagram
Struktur aliran data konkurensi antara Web Process, Redis Datastore, dan Sidekiq Worker Pool:

```
+----------------------------------------------------------------------------------------+
|                                    APPLICATION HOST                                    |
|                                                                                        |
|  +-----------------------------------+        +-------------------------------------+  |
|  |     Puma Web Process (PID 101)    |        |    Sidekiq Worker Process (PID 201) |  |
|  |                                   |        |                                     |  |
|  |  [Thread 1] (HTTP Worker)         |        |  Thread Pool Manager (Size: 5)      |  |
|  |       |                           |        |   |-- Worker Thread #1 (idle)       |  |
|  |   Controller Action               |        |   |-- Worker Thread #2 (processing) |  |
|  |       |                           |        |   |-- Worker Thread #3 (processing) |  |
|  |   ActiveJob.perform_later         |        |   |-- Worker Thread #4 (idle)       |  |
|  |       |                           |        |   \-- Worker Thread #5 (idle)       |  |
|  |   Sidekiq::Client.push            |        |                                     |  |
|  +-------+---------------------------+        +------------------^------------------+  |
|          | (TCP / Redis Protocol)                                | (TCP BRPOP)         |
+----------|-------------------------------------------------------|---------------------+
           |                                                       |
           v                                                       |
+------------------------------------------------------------------+---------------------+
|                                    REDIS CLUSTER                                       |
|                                                                                        |
|  +--------------------+   +-----------------------+   +-----------------------------+  |
|  |  List: "critical"  |   |  List: "default"      |   |  Sorted Set: "retry"        |  |
|  |  [ {job}, {job} ]  |   |  [ {job}, {job}, .. ] |   |  (Score: Timestamp, {job})  |  |
|  +--------------------+   +-----------------------+   +-----------------------------+  |
+----------------------------------------------------------------------------------------+
```

---

### 9. Simple Example
Implementasi job minimalis menggunakan Active Job dengan queue adapter Sidekiq:

```ruby
# Gemfile
gem "sidekiq"

# config/application.rb
module CoreBanking
  class Application < Rails::Application
    config.active_job.queue_adapter = :sidekiq
  end
end

# app/jobs/audit_log_job.rb
class AuditLogJob < ApplicationJob
  queue_as :low_priority

  def perform(action_name, user_id, timestamp)
    Rails.logger.info("AUDIT: [#{timestamp}] User #{user_id} performed #{action_name}")
    # Simpan ke storage append-only atau service audit eksternal
  end
end

# Trigger pemanggilan di Controller
class SessionsController < ApplicationController
  def destroy
    AuditLogJob.perform_later("LOGOUT", current_user.id, Time.current.to_iso8601)
    reset_session
    redirect_to root_path, notice: "Berhasil keluar sistem."
  end
end
```

---

### 10. Practical Example
Sistem pembuatan dan pengiriman faktur transaksi (*Invoice Processing*) berstatus kritis, dengan implementasi *idempotency keys*, sanitasi error, *exponential backoff*, dan isolasi transaksi basis data:

```ruby
# app/models/invoice.rb
class Invoice < ApplicationRecord
  belongs_to :account
  
  enum status: { pending: 0, processing: 1, finalized: 2, failed: 3 }

  # Menjamin job hanya di-enqueue SETELAH data benar-benar tersimpan di DB engine
  after_commit :enqueue_generation, on: :create

  private

  def enqueue_generation
    InvoiceGenerationJob.set(queue: :invoicing).perform_later(self)
  end
end

# app/jobs/invoice_generation_job.rb
class InvoiceGenerationJob < ApplicationJob
  queue_as :invoicing

  # Penanganan transient errors dengan exponential backoff dan full jitter
  retry_on Net::OpenTimeout, Net::ReadTimeout, 
           wait: :polynomially_longer, 
           attempts: 5

  # Discard job secara permanen jika record terhapus dari basis data sebelum dieksekusi
  discard_on ActiveJob::DeserializationError do |job, error|
    Rails.logger.warn("Job #{job.job_id} dibatalkan: Data entitas telah dihapus permanen. Detil: #{error.message}")
  end

  # Membatasi kegagalan spesifik yang tidak mungkin pulih dengan retry (Client Error)
  discard_on ThirdPartyBilling::InvalidAccountStateError do |job, error|
    # Alerting ke On-Call Engineer via APM / Error Tracker
    Bugsnag.notify(error) { |report| report.add_tab(:job_context, job.arguments) }
  end

  def perform(invoice)
    # 1. Idempotency Guard: Hindari re-running untuk job yang sudah sukses/sedang diproses
    return if invoice.finalized?

    invoice.with_lock do
      return if invoice.finalized?
      invoice.update!(status: :processing)
    end

    # 2. Operasi I/O Lambat: Panggilan API External Gateway
    pdf_blob = DocumentRendererEngine.generate_pdf_for(invoice)
    
    # 3. Interaksi Storage Cloud (misal: S3 via Active Storage)
    invoice.document.attach(
      io: StringIO.new(pdf_blob),
      filename: "invoice_#{invoice.secure_token}.pdf",
      content_type: "application/pdf"
    )

    # 4. Finalisasi Mutasi State
    invoice.update!(status: :finalized, processed_at: Time.current)

    # 5. Memicu Job Turunan
    CustomerNotificationJob.perform_later(invoice.account_id, invoice.id)
  end
end
```

Konfigurasi concurrency pool worker Sidekiq dan queue weighting:

```yaml
# config/sidekiq.yml
:concurrency: <%= ENV.fetch("RAILS_MAX_THREADS", 5) %>
:queues:
  - [invoicing, 3]      # Strict priority weighting
  - [default, 2]
  - [low_priority, 1]
:timeout: 25            # Graceful shutdown wait time (detik)
```

---

### 11. Real World Example
**Studi Kasus: Sistem Webhook Ingestion Skala Besar pada E-Commerce Marketplace (Level Bukalapak/Shopify)**

*Konteks*: 
Platform memproses webhook dari 50+ payment provider dan ekspedisi logistik secara simultan. Saat musim festival belanja (11.11 / 12.12), lonjakan request masuk mencapai 35.000 requests/second pada Web API layer.

*Tantangan*:
Eksekusi verifikasi webhook mencakup perhitungan signature kriptografis, mutasi stok, dan validasi transaksi basis data. Jika dilakukan sinkron di Puma:
- Thread Puma habis dalam 3 detik pertama lonjakan.
- Redis mengalami lonjakan memori tak terkontrol (*Out of Memory / OOM*) karena controller mengirimkan objek payload JSON berukuran besar (rata-rata 150KB per payload) langsung ke Redis via `perform_later(large_json_payload)`.

*Solusi Arsitektur*:
1. **Thin Payload Architecture**: API Gateway langsung menyimpan raw payload JSON ke object storage (S3/GCS) berlatensi sangat rendah atau cache temporal Redis yang ter-isolasi, kemudian hanya mem-passing ID referensi kunci (`webhook_event_id`) melalui Active Job:
   ```ruby
   # Clean, Thin Argument Passing
   WebhookDispatcherJob.perform_later(webhook_event.id)
   ```
2. **Dedicated Queue Segregation**: 
   Pemisahan queue menjadi `:critical_payment`, `:webhooks_standard`, dan `:bulk_reconciliation`.
3. **Idempotency Matrix**:
   Implementasi Redis Distributed Lock (via `Redlock` algorithm) di level `perform` untuk mencegah dua webhook dari satu provider mengeksekusi mutasi pesanan secara konkruen:
   ```ruby
   def perform(webhook_event_id)
     event = WebhookEvent.find(webhook_event_id)
     lock_key = "lock:webhook:#{event.idempotency_key}"

     # Dapatkan lock selama 30 detik untuk eksekusi atomik
     REDIS_CLIENT.with do |conn|
       acquired = conn.set(lock_key, true, nx: true, ex: 30)
       return unless acquired # Abaikan jika duplikat sedang berjalan

       begin
         WebhookProcessor.process(event)
       ensure
         conn.del(lock_key)
       end
     end
   end
   ```

*Hasil Metrik*:
- Web server latensi rata-rata p99 konstan berada di batas 45ms.
- Memory footprint pada Redis queue cluster terpangkas hingga 85%.
- Kehilangan data (*data loss*) bernilai 0% meskipun server internal payment provider mengalami gangguan latensi intermiten hingga 12 jam, ditangani secara otomatis oleh *Sidekiq Retry Engine*.

---

### 12. Trade-offs

| Aspek | Active Job + Sidekiq | Synchronous In-Memory Execution | Solid Queue / GoodJob (RDBMS Based) |
| :--- | :--- | :--- | :--- |
| **Throughput & Speed** | Ekstrem Tinggi (Jalur Redis di RAM murni, jutaan job/menit). | Sangat Rendah (Menghambat siklus loop I/O HTTP web). | Moderat ke Tinggi (Dibatasi oleh IOPS dan batas koneksi DB). |
| **Infrastruktur & Cost** | Tambahan biaya operasional (Wajib memelihara cluster Redis). | Nol biaya tambahan infrastruktur. | Hemat (Memakai PostgreSQL/MySQL yang telah tersedia). |
| **Kompleksitas Debugging**| Tinggi (Membutuhkan distributed tracing, APM, dan logging korelasi ID). | Rendah (Stack trace langsung muncul di console request). | Menengah (Riwayat tugas tersimpan di tabel DB relational). |
| **Konsistensi State** | Menghadapi masalah *Eventual Consistency* dan latensi replikasi. | *Immediate Consistency* (ACID terpenuhi dalam 1 request). | Mendekati *Immediate Consistency* via DB transaksi native. |
| **Resilience & Recovery**| Sangat Tinggi (Sistem auto-retry cerdas, Dead Letter Queue). | Nol (Pengecualian error mematikan alur kerja pengguna). | Sangat Tinggi (Mendukung transaksi state transaksional ACID). |

---

### 13. When To Use
Implementasikan pola Active Job + Sidekiq jika Anda menghadapi kondisi berikut:
- Operasi memakan durasi di atas ambang batas 250ms (ekspor CSV/Excel, rendering berkas PDF).
- Berkomunikasi melalui jaringan publik ke API pihak ketiga (Payment Gateway, Webhook dispatch, SMS/Email provider).
- Operasi batch processing dengan throughput intensif (misal: sinkronisasi massal katalog produk malam hari).
- Pemicuan tugas berkala (*cron/scheduler*) yang harus memiliki mekanisme pemantauan status terpusat.
- Tugas yang membutuhkan eksekusi terdistribusi lintas node server independen.

---

### 14. When NOT To Use
Hindari delegasi ke Active Job dalam skenario berikut:
- **Operasi Ultra-Cepat & In-Memory**: Menghitung string sederhana, enkripsi hash pendek di mana overhead serialisasi, transmisi TCP ke Redis, dan deserialisasi justru memakan waktu lebih banyak daripada kalkulasi itu sendiri (Overhead latency ~5-15ms).
- **Kebutuhan Real-Time Synchronous Response**: Alur di mana klien membutuhkan hasil kalkulasi data secara langsung dalam payload respons JSON HTTP (Gunakan arsitektur synchronous service object yang teroptimasi query-nya).
- **Workflow Antar-Mikroservis Skala Besar**: Jika Anda membutuhkan orkestrasi pesan antar-bahasa pemrograman lintas domain, gunakan message broker enterprise seperti Apache Kafka atau RabbitMQ via AMQP/STOMP protokol, bukan Active Job yang didesain secara dominan untuk ekosistem Rails.

---

### 15. Common Mistakes
1. **Mengirim Objek Active Record yang Belum Dikomit (Race Condition)**:
   ```ruby
   # SALAH (ANTI-PATTERN FATAL)
   def create
     @user = User.create(user_params)
     # Jika worker mengeksekusi job sebelum DB commit selesai: ActiveRecord::RecordNotFound!
     WelcomeEmailJob.perform_later(@user) 
   end

   # BENAR
   def create
     @user = User.new(user_params)
     if @user.save
       # Gunakan callback after_commit di model ATAU panggil eksplisit:
       ActiveRecord::Base.connection.after_commit do
         WelcomeEmailJob.perform_later(@user)
       end
     end
   end
   ```
2. **Menyimpan State Besar / Objek Kompleks di Argumen Job**:
   ```ruby
   # SALAH: Redis memory bloating, argumen tersimpan selamanya di DB retry log
   SendReportJob.perform_later(large_raw_csv_string, User.all.to_a)

   # BENAR: Kirim metadata pointer / ID
   SendReportJob.perform_later(report_id)
   ```
3. **Mengabaikan Karakteristik Non-Idempoten saat Retry**:
   Jika sebuah job mengalami *network timeout* saat memanggil Stripe API, proses pemotongan kartu kredit mungkin sebenarnya telah berhasil di server Stripe. Jika job mencoba ulang dari awal (*blind retry*), akun pengguna akan terdebit ganda (*double charge*). Job *wajib* menyertakan Idempotency Token pada setiap integrasi external.
4. **Pool Koneksi Basis Data Worker yang Tidak Seimbang**:
   Konfigurasi `database.yml` memiliki `pool: 5`, namun Sidekiq dikonfigurasi dengan thread `:concurrency: 25`. Ketika seluruh 25 worker thread aktif menjalankan query, 20 thread akan terlempar dengan galat: `ActiveRecord::ConnectionTimeoutError`.

---

### 16. Best Practices
Daftar periksa kesiapan produksi (*Production-ready checklist*):

- [ ] **Sinkronisasi DB Pool & Sidekiq Threads**: Pastikan `RAILS_MAX_THREADS` pada `database.yml` bernilai minimal sama dengan jumlah `:concurrency:` Sidekiq ditambah batas toleransi (contoh: 2 thread cadangan).
- [ ] **Passing Argument Menggunakan GlobalID**: Hindari manipulasi custom string/hash serialization jika model didukung Active Record. Lewatkan instance model murni agar GlobalID menangani abstraksi deserialisasi secara aman.
- [ ] **Implementasi Queue Latency Monitoring**: Pantau metrik waktu tunggu antrean (*Queue Latency*), bukan hanya jumlah antrean (*Queue Size*). 10.000 job dengan waktu eksekusi 1ms jauh lebih aman daripada 10 job dengan latensi antrean 3 jam.
- [ ] **Gunakan `retry_on` dengan Batas Terukur**: Selalu batasi `attempts:` maksimum dan gunakan `wait: :exponentially_longer` untuk meredam pemborosan siklus CPU.
- [ ] **Set Batas Timeout Eksekusi**: Cegah worker thread tergantung (*hanging*) selamanya akibat socket timeout yang tidak terkonfigurasi pada client HTTP dengan membungkus operasi menggunakan `Timeout.timeout` atau konfigurasi library HTTP (`open_timeout`, `read_timeout`).

---

### 17. Troubleshooting

#### Skenario 1: `ActiveJob::DeserializationError: Error while trying to deserialize arguments`
- **Penyebab**: Job di-enqueue dengan objek model, namun sebelum worker mengeksekusi job, record tersebut telah dihapus secara fisik (`DELETE`) dari basis data oleh proses lain atau pengguna.
- **Solusi**: Tambahkan penanganan discard terstruktur pada level job:
  ```ruby
  class SafeExecutionJob < ApplicationJob
    discard_on ActiveJob::DeserializationError do |job, error|
      Rails.logger.warn("Record hilang pada job #{job.class.name} dengan ID: #{job.job_id}")
    end
  end
  ```

#### Skenario 2: Sidekiq Process Mengalami Memory Leak
- **Penyebab**: Instansiasi objek berukuran masif (misal: `User.all` dipanggil ke memori) yang tidak dapat dibersihkan oleh Ruby Garbage Collector (terfragmentasi di memori heap), atau log logger global menyimpan data array tanpa batas.
- **Solusi**:
  1. Gunakan `find_each(batch_size: 1000)` untuk membaca record dalam bentuk chunk.
  2. Implementasikan gem `jemalloc` pada base image Docker Ruby Anda untuk mengurangi fragmentasi memori.
  3. Konfigurasi `sidekiq-ent` memory killer atau pasang container restart policy jika RSS memory melampaui ambang batas maksimum (misal: 1GB).

#### Skenario 3: Redis `OOM command not allowed when used memory > 'maxmemory'`
- **Penyebab**: Retensi *dead-letter queue* terakumulasi jutaan item, atau ukuran payload job terlalu besar akibat serialization file/data mentah ke argumen.
- **Solusi**:
  1. Bersihkan Dead Set: `Sidekiq::DeadSet.new.clear`.
  2. Atur policy eviction Redis: `maxmemory-policy noeviction` (jangan pernah gunakan `volatile-lru` untuk backend Sidekiq karena dapat menghapus antrean pekerjaan yang belum diproses secara acak).
  3. Pindahkan file payload ke cloud storage (S3), pass semata-mata pre-signed URL atau database identifier.

---

### 18. Exercise
**Implementasikan Job Notifikasi Pengiriman Pesanan dengan Validasi Transaksi**

1. Buat migration untuk menambahkan kolom `shipped_at:datetime` dan `tracking_code:string` pada model `Order`.
2. Buat job bernama `OrderShipmentDispatcherJob` pada antrean `:shipments`.
3. Job harus:
   - Menerima argumen objek `Order`.
   - Mengambil data resi pengiriman dari stub API ekspedisi luar.
   - Mengupdate model `Order` secara atomic.
   - Mengirim email pemberitahuan ke konsumen via Action Mailer (`OrderMailer.shipped_email(order).deliver_later`).
4. Pastikan job aman dari *race conditions* dan *deadlock*.

**Panduan Solusi Struktur Minimum**:
```ruby
class OrderShipmentDispatcherJob < ApplicationJob
  queue_as :shipments

  retry_on LogisticsGateway::TimeoutError, wait: :exponentially_longer, attempts: 3
  discard_on ActiveRecord::RecordNotFound

  def perform(order)
    return if order.shipped_at.present?

    tracking_info = LogisticsGateway.create_waybill(order_id: order.id)

    Order.transaction do
      order.lock!
      order.update!(
        tracking_code: tracking_info.tracking_number,
        shipped_at: Time.current
      )
    end

    OrderMailer.shipped_email(order).deliver_later
  end
end
```

---

### 19. Challenge
**Rancang Sistem Export CSV Multi-Tenant dengan Concurrency Throttling**

*Spesifikasi Arsitektur*:
Anda bertugas merancang subsistem export data historis transaksi ribuan toko multi-tenant pada aplikasi SaaS.
1. **Constraint 1 (Adil Antar Pengguna - Fair Usage)**: Satu tenant (toko besar) yang meminta 100 antrean export tidak boleh memonopoli seluruh thread worker. Tenant lain yang hanya meminta 1 export harus dapat dieksekusi secara instan tanpa menunggu 100 job milik tenant besar selesai (*Queue starvation prevention*).
2. **Constraint 2 (Memory Bound)**: Ekspor transaksi dengan rentang 1.000.000 row data tidak boleh menaikkan footprint memori proses worker lebih dari 150MB. Gunakan teknik streaming I/O langsung ke storage (misal: S3 Multipart Upload).
3. **Constraint 3 (Distributed Concurrency Limit)**: Setiap tenant hanya diizinkan mengeksekusi maksimal **2 job ekspor simultan** secara bersamaan. Sisanya harus tetap berada di antrean antre (*throttled*).

*Kriteria Keberhasilan Penilaian*:
- Penggunaan custom Sidekiq middleware atau pemanfaatan `sidekiq-limit_fetch` / Redis counters.
- Query database bebas dari potensi alokasi array penuh (wajib memakai `in_batches` atau Active Record streaming API).
- Penggunaan locking terdistribusi yang aman tanpa memicu *deadlock* saat worker mengalami terminasi mendadak (*SIGKILL* / *SIGTERM*).

---

### 20. Summary
- **Active Job** berfungsi sebagai *unified abstraction layer* di level framework Rails, sedangkan **Sidekiq** bertindak sebagai *high-performance, multi-threaded execution engine* yang memanfaatkan persistensi struktur data Redis.
- **GlobalID** menyelesaikan masalah dependensi objek in-memory dengan mentranslasikan instance database menjadi skema URI deterministik, mereduksi risiko keamanan dan memory bloating pada message broker.
- Pemisahan siklus hidup HTTP dan background worker adalah strategi mutlak untuk mempertahankan latensi web di ambang sub-detik dan melindungi Puma thread pool dari *starvation*.
- Dalam merancang job untuk lingkungan produksi, prinsip **Idempotency** (tugas dapat diulang berkali-kali tanpa menghasilkan mutasi data ganda) dan penanganan transaksi basis data yang tepat (`after_commit`) merupakan dua fondasi penting untuk mencegah anomali data dan *race conditions*.