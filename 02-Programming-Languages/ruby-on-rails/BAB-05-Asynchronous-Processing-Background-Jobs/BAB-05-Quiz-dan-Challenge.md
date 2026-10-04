# BAB 05: Quiz, Challenge, & Knowledge Check
**Asynchronous Processing & Background Jobs**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **ActiveJob Serialization & GlobalID Lifecycles**  
   Ketika Anda mengirimkan instance model ActiveRecord ke dalam antrean (misalnya, `ProcessInvoiceJob.perform_later(order)`), jelaskan mekanisme serialisasi dan deserialisasi yang dilakukan oleh ActiveJob menggunakan GlobalID. Mengapa passing objek ActiveRecord secara langsung berpotensi memicu error `ActiveRecord::RecordNotFound` di worker, dan bagaimana urutan eksekusi lifecycle ActiveRecord mempengaruhinya?

2. **At-Least-Once Delivery vs. Exactly-Once Processing**  
   Hampir semua message broker dan job queue engine pada Ruby on Rails (Sidekiq, Solid Queue, RabbitMQ) hanya menjamin semantik pengiriman *At-Least-Once*, bukan *Exactly-Once*. Jelaskan mengapa batasan teoritis jaringan ini ada, dan apa konsekuensinya terhadap perancangan bisnis logika pada sebuah *Job worker*?

3. **ActiveRecord Transactions vs. Asynchronous Enqueueing**  
   Mengapa mengeksekusi `perform_later` di dalam blok callback `after_save` atau `after_create` dianggap sebagai sebuah *anti-pattern* berbahaya pada aplikasi Rails konkurensi tinggi? Analisis perbedaan eksekusi antara `after_save`, `after_commit`, dan penggunaan opsi `enqueue_after_transaction_commit` pada Rails 7.2+.

4. **Karakteristik Arsitektural: Sidekiq (Redis) vs. Solid Queue (RDBMS)**  
   Bandingkan arsitektur dasar dan model konkurensi antara Sidekiq (berbasis Redis dengan multithreading Ruby) dan Solid Queue (berbasis RDBMS menggunakan `FOR UPDATE SKIP LOCKED`). Dari sudut pandang penggunaan memori, persistensi data, throughput, dan overhead koneksi database, kapan Anda harus memilih salah satu dari keduanya?

5. **Anatomi dan Bahaya Default Retry Mechanism**  
   Secara default, ActiveJob dan Sidekiq menerapkan mekanisme *exponential backoff retry* ketika terjadi uncaught exception. Jelaskan bahaya sistemik yang dapat ditimbulkan oleh default retry ini terhadap sistem eksternal (misalnya payment gateway pihak ketiga atau API rate-limited), dan bagaimana strategi mitigasi standard industri untuk mengatasinya?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Memory Bloat & Fragmentation pada Ruby MRI Worker**  
   Sidekiq worker Anda yang berjalan di Kubernetes/Linux mengalami pertumbuhan memori tanpa henti (Memory Bloat) hingga memicu status *OOMKilled*, padahal alokasi memori tidak bocor secara permanen (Memory Leak). Jelaskan bagaimana alokator default glibc berinteraksi dengan multi-threading MRI Ruby dan garbage collector (GC), serta bagaimana implementasi `jemalloc` dan tuning variabel environment Ruby mengatasi anomali ini.

2. **Redis Out-Of-Memory (OOM) via Sidekiq Payload Bloat**  
   Sebuah sistem mengalami crash total pada cluster Redis karena utilisasi memori mencapai 100%. Setelah diaudit, ditemukan jutaan antrean job yang gagal dieksekusi tertahan di *Retry Set* dan *Dead Set*, ditambah adanya engineer yang mengirimkan payload berupa *huge hash* / *raw JSON string* sebesar puluhan megabyte ke dalam argumen job. Jelaskan bagaimana Anda mendiagnosis masalah ini via Redis CLI (`SCAN`, `DEBUG OBJECT`, atau `MEMORY USAGE`), dan apa langkah remediasinya tanpa mematikan Redis produksi?

3. **Graceful Shutdown, Deployment, dan Sinyal OS (SIGTERM vs SIGKILL)**  
   Ketika proses deploy Kubernetes atau rolling restart server dijalankan, orkestrator mengirimkan sinyal `SIGTERM` ke worker Sidekiq atau Solid Queue. Jelaskan siklus hidup penanganan sinyal tersebut di dalam worker runtime: apa yang terjadi pada thread yang sedang aktif mengeksekusi I/O blocking, bagaimana batas waktu timeout (`--timeout`) dikelola, dan apa yang menyebabkan sebuah job mengalami *silent duplication* jika proses dipaksa berhenti dengan `SIGKILL`?

4. **Pessimistic Locking & Distributed Deadlocks di Latar Belakang**  
   Dua background worker yang berbeda berjalan secara paralel dan keduanya memproses baris database yang sama:
   * Worker A mengeksekusi: `User.lock.find(1)` lalu mengupdate `Account.lock.find(10)`
   * Worker B mengeksekusi: `Account.lock.find(10)` lalu mengupdate `User.lock.find(1)`  
   Jelaskan secara mendalam bagaimana Postgres/MySQL mendeteksi kondisi *deadlock* ini, status transaksi yang akan dibatalkan, dan bagaimana pola penulisan kode transaksi background job harus distandarisasi untuk mencegah dependensi siklik tersebut.

5. **Connection Pool Starvation pada Database Worker**  
   Sebuah instance Sidekiq dikonfigurasi dengan flag *concurrency* sebesar 25 thread (`-c 25`). Namun, nilai `pool` pada `config/database.yml` diset default ke angka 5. Jelaskan gejala teknis yang akan dialami oleh worker saat beban antrean tinggi, error apa yang akan terlempar di log Rails, dan bagaimana formula matematis yang tepat untuk menghitung kebutuhan koneksi database pada arsitektur hybrid (Puma web server + Background workers)?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: The Black Friday Thundering Herd & Redis Eviction Disaster
Aplikasi e-commerce skala enterprise sedang menghadapi event *Flash Sale*. Dalam kurun waktu 5 menit, terdapat 500.000 transaksi yang masuk. Sistem secara instan melempar job pengiriman notifikasi, kalkulasi poin loyalti, dan update analitik ke Redis queue melalui ActiveJob. 
Tiba-tiba, performa aplikasi web ambruk (Puma worker pool saturasi), latency Redis melesat dari 0.8ms ke 8.5 detik, dan konfigurasi `maxmemory-policy` pada Redis yang diatur ke `allkeys-lru` mulai menghapus key session user dan cache aplikasi secara acak untuk menampung payload job yang meluap.

* **Pertanyaan Diagnostik:**
  1. Bagaimana Anda menghentikan kaskade kegagalan ini secara darurat (*emergency triage*) tanpa kehilangan data pesanan pelanggan yang belum diproses?
  2. Dari sisi arsitektur Redis dan queue topology, sebutkan 3 kegagalan desain mendasar pada kasus di atas dan bagaimana restrukturisasinya (misalnya: isolasi Redis instance, queue throttling, priority queue segmentation)?

---

### Skenario B: Double Billing Race Condition & Network Partisi
Aplikasi FinTech Anda memproses penagihan langganan otomatis menggunakan `ChargeSubscriptionJob`. Salah satu pengguna mengalami tagihan ganda (*double charge*) pada kartu kreditnya sebanyak 3 kali dalam interval 15 menit. 
Investigasi log menunjukkan urutan berikut:
1. Worker mengeksekusi panggilan HTTP API ke gateway Stripe.
2. Stripe sukses mendebit kartu, namun sebelum merespons dengan HTTP 200, terjadi lonjakan *packet loss* di jaringan cloud provider yang menyebabkan `Net::ReadTimeout` pada worker Rails.
3. Job gagal dengan exception uncaught `Net::ReadTimeout`.
4. Mekanisme retry otomatis ActiveJob mengeksekusi ulang job tersebut 2 menit kemudian dengan payload yang sama persis.

* **Pertanyaan Diagnostik:**
  1. Identifikasi kelemahan mendasar dalam implementasi bisnis logika pada `ChargeSubscriptionJob` tersebut.
  2. Rancang solusi arsitektur pengamanan transaksi menggunakan kombinasi **Idempotency Keys**, state machine transitions pada database lokal, dan penanganan timeout pihak ketiga yang menjamin dana pengguna tidak akan pernah terdebit dua kali.

---

### Skenario C: Migrasi Arsitektur Monolith ke Solid Queue (Rails 8 Modernization)
Tim engineering Anda berencana mengeliminasi dependensi Redis dari infrastruktur backend mereka dan beralih sepenuhnya ke **Solid Queue** (Rails 8 stack default) yang berjalan di atas database PostgreSQL engine yang sama dengan database utama. 
Sistem saat ini memproses rata-rata 1.500 job per detik pada jam sibuk, dengan durasi job bervariasi antara 50ms (eksekusi cepat) hingga 120 detik (laporan analitik berat).

* **Pertanyaan Diagnostik:**
  1. Analisis dampak operasional dari pola polling dan *Write-Heavy Load* yang akan ditimbulkan oleh Solid Queue terhadap Write-Ahead Logging (WAL), IOPS storage, dan autovacuum worker pada cluster database PostgreSQL utama Anda.
  2. Apakah Anda merekomendasikan Solid Queue berbagi database yang sama (*single database*) dengan data transaksional, ataukah harus dipisahkan menggunakan fitur *multiple databases* Rails? Berikan justifikasi teknis mendalam mengenai trade-off skalabilitas, backup snapshot, dan risiko kegagalan sistemik (*blast radius*).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Throughput Webhook Ingestion Engine with Transactional Outbox & Circuit Breaker

#### Problem Statement:
Aplikasi Anda menerima jutaan payload webhook per hari dari mitra pembayaran global. Jika webhook langsung diproses secara sinkron, Puma worker akan hang dan memicu downtime. Namun, jika langsung dilempar ke background worker reguler menggunakan ActiveJob standar, kegagalan database lokal atau kegagalan transient worker akan menyebabkan webhook hilang atau dieksekusi ganda tanpa ada jejak audit yang patuh regulasi keuangan.

#### Requirements:
1. **Pola Transactional Outbox (Zero Job Loss Guarantee):**
   * Controller hanya bertugas memvalidasi signature webhook, lalu menyimpan *raw payload* ke tabel `webhook_events` dengan state `pending` dalam satu transaksi ACID lokal, kemudian merespons API caller dengan status `202 Accepted` di bawah 30 milidetik.
   * Buat mekanisme background worker terjadwal yang membaca status `pending`, mengunci data dengan aman secara konkuren (gunakan PostgreSQL `FOR UPDATE SKIP LOCKED`), lalu mendelegasikan pemrosesan ke job spesifik.
2. **Robust Idempotency Guard:**
   * Implementasikan module concern idempotensi yang menggunakan key unik (kombinasi `event_id` penyedia webhook + hash payload).
   * Gunakan mekanisme locking berbasis Redis atomic (atau DB advisory lock) untuk mencegah dua worker memproses event yang sama secara konkuren jika terjadi delivery duplikat dari webhook provider.
3. **Resilience & Dead-Letter Triage:**
   * Jika pemrosesan payload gagal karena error non-transient (misal: JSON rusak atau data korup), jangan lakukan retry tanpa batas. Tandai event sebagai `failed`, catat exception stack trace secara komprehensif, dan pindahkan ke mekanisme Dead-Letter Queue (DLQ) internal untuk inspeksi tim support.
   * Terapkan exponential backoff dengan jitter untuk menangani error transient (misal: lock timeout atau network blip).

#### Constraints:
* Tidak boleh menggunakan gem berbayar (seperti Sidekiq Pro/Enterprise).
* Semua operasi background processing harus kompatibel dengan ActiveJob abstraction standard (Rails 7.1+ atau 8.x).
* Beban eksekusi tidak boleh memblokir thread pool utama dan harus aman terhadap deployment rolling restart (*Zero Data Loss during deployment*).

#### Expected Output:
1. Skema migrasi database untuk tabel `webhook_events` (termasuk index strategis untuk polling konkurensi).
2. Kode controller endpoint webhook yang optimal.
3. File worker ActiveJob lengkap dengan concern idempotensi, exception handling, dan mutasi state yang aman.
4. RSpec test suite yang menguji skenario balapan (Race Condition): dua worker mencoba memproses event ID yang sama di milidetik yang sama, dan hanya SATU yang berhasil mengeksekusi payload.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Siklus hidup serialisasi dan deserialisasi GlobalID pada parameter ActiveJob.
- [ ] Perbedaan fundamental antara konkurensi berbasis Thread (Sidekiq) vs Process/Thread di atas polling RDBMS (Solid Queue).
- [ ] Mengapa database transaksi (`after_save` vs `after_commit`) menjadi sumber utama bug `ActiveRecord::RecordNotFound` pada worker.
- [ ] Model pengiriman pesan *At-Least-Once Delivery* dan kewajiban merancang job yang bersifat *Idempotent*.
- [ ] Cara kerja exponential backoff dan penambahan *jitter* untuk mencegah fenomena *Thundering Herd Problem*.
- [ ] Bahaya Memory Bloat di Ruby MRI, cara kerja alokator C (glibc), dan peran implementasi `jemalloc`.
- [ ] Mekanisme graceful shutdown menggunakan sinyal OS (`SIGTERM`, `SIGINT`, `SIGKILL`) serta implikasi parameter `-t` (timeout).
- [ ] Trade-off antara memisahkan instance Redis/DB khusus antrean job versus menyatukannya dengan storage utama.

### Saya tidak perlu menghafal:
- [ ] Seluruh flag CLI konfigurasi internal Sidekiq atau Solid Queue (cukup pahami fungsi parameter kritis seperti `-c concurrency`, `-q queue_name`, dan `-t timeout`).
- [ ] Formula eksak matematis dari algoritma penentuan interval backoff bawaan Rails (cukup pahami konsep pertumbuhan waktu tunggu eksponensial).
- [ ] Struktur byte internal protokol Redis RESP (cukup ketahui kompleksitas waktu $O(1)$ vs $O(N)$ dari perintah yang dieksekusi).

### Saya harus bisa melakukan:
- [ ] Mengonfigurasi connection pool database Rails agar selaras dengan total thread konkurensi worker Sidekiq/Solid Queue.
- [ ] Mengimplementasikan *Idempotency Guard* menggunakan database constraints, lock atomically, atau advisory locks pada job kritikal.
- [ ] Membedah antrean job yang bermasalah di level produksi menggunakan command line interface (CLI) atau Rails console tanpa mengakibatkan degradasi performa I/O.
- [ ] Memisahkan antrean (*queues*) berdasarkan prioritas bisnis (`critical`, `default`, `low`) dan mengalokasikan resource worker secara terisolasi.
- [ ] Menulis unit test dan integrasi test komprehensif menggunakan RSpec untuk menguji apakah background job diantrekan dengan argumen yang benar dan tereksekusi secara idempotensial.