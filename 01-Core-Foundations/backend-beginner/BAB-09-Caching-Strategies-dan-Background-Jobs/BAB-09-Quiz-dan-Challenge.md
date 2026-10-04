# BAB 09: Quiz, Challenge, & Knowledge Check
**Caching Strategies & Background Job Basics**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Trade-off Pola Caching (Cache-Aside vs. Write-Through vs. Write-Back):**  
   Jelaskan perbedaan mendasar antara ketiga pola caching tersebut dalam konteks latensi tulis (*write latency*), konsistensi data (*data consistency*), dan risiko kehilangan data (*data loss risk*). Kapan sebuah sistem backend pemula mutlak harus menghindari pola *Write-Back*?

2. **In-Memory Cache (Redis) vs. In-Process Cache (Local Memory):**  
   Bandingkan penggunaan *local in-memory cache* (misal: Go `sync.Map`, Node.js object/memory, atau Java Guava/Caffeine) dengan *distributed external cache* seperti Redis. Apa implikasinya terhadap *cache consistency* ketika aplikasi Anda di-*scale-out* menjadi 5 instance pod horizontal di balik sebuah Load Balancer?

3. **Limitasi Arsitektur Synchronous Request-Response:**  
   Mengapa mengeksekusi operasi I/O-heavy (seperti *image resizing*, *PDF invoice generation*, atau pengiriman email transaksional via vendor pihak ketiga) secara sinkron di dalam siklus HTTP request-response merupakan *anti-pattern* kritis? Analisis dampaknya terhadap ketersediaan *connection pool*, *worker thread exhaustion*, dan *client timeout*.

4. **Anatomi dan Siklus Hidup Antrean Pesan (Message Queue Lifecycle):**  
   Jelaskan peran masing-masing komponen: *Producer*, *Message Broker/Task Queue*, *Consumer/Worker*, dan mekanisme *Acknowledgement* (`ACK` vs. `NACK`/`REJECT`). Apa yang terjadi pada pesan di antrean jika sebuah worker mengalami *kernel panic* atau *out-of-memory* (OOM) tepat di tengah proses eksekusi sebelum mengirimkan `ACK`?

5. **Kebijakan Penggusuran (*Cache Eviction Policy*) dan TTL:**  
   Jelaskan perbedaan mekanistik antara algoritma penggusuran data *Least Recently Used* (LRU) dan *Least Frequently Used* (LFU). Mengapa menetapkan *Time-To-Live* (TTL) wajib diimplementasikan bahkan ketika kapasitas RAM server Redis Anda masih tersisa 80%?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mitigasi Fenomena *Cache Stampede* (*Thundering Herd*):**  
   Saat sebuah *key* cache bernilai tinggi (misal: data katalog beranda) kedaluwarsa secara tiba-tiba di tengah lonjakan trafik (10.000 QPS), ribuan request akan serentak mengalami *cache miss* dan membebani database utama. Jelaskan dua strategi mitigasi teknis untuk masalah ini:
   - Penggunaan *Distributed Mutex Locking* (misal: Redis `SETNX`).
   - Pendekatan *Probabilistic Early Expiration* (algoritma XFetch).

2. **Diferensiasi Kegagalan: *Cache Penetration* vs. *Cache Avalanche*:**  
   Bedakan mekanisme terjadinya *Cache Penetration* dan *Cache Avalanche*. Bagaimana Anda mengimplementasikan penanganan teknis untuk masing-masing masalah tersebut menggunakan:
   - *Bloom Filter* atau *Null Value Caching* (untuk Penetration).
   - *TTL Jittering* / *Randomized TTL* (untuk Avalanche).

3. **Masalah Dual-Write dan Urutan Invalidasi Cache:**  
   Ketika ada operasi pembaruan data di database, terdapat dua pendekatan invalidasi cache:
   - *Opsi 1:* Update Database terlebih dahulu, lalu Delete Cache.
   - *Opsi 2:* Delete Cache terlebih dahulu, lalu Update Database.  
   Analisis skenario *race condition* yang dapat menyebabkan data basi (*stale data*) tersimpan permanen di cache pada kedua opsi tersebut jika ada *concurrent read-write*. Mengapa *Opsi 1* lebih disukai dalam arsitektur Cache-Aside?

4. **Semantik Pengiriman (*Delivery Semantics*) dan Idempotensi Worker:**  
   Mayoritas sistem antrean task (RabbitMQ, SQS, Redis Streams, BullMQ) secara praktis menjamin semantik *At-Least-Once Delivery*, bukan *Exactly-Once Delivery*. 
   - Mengapa *network partition* membuat *Exactly-Once* hampir mustahil dicapai secara murni?
   - Bagaimana Anda mendesain mekanisme idempotensi pada consumer yang mengeksekusi pemotongan saldo pengguna menggunakan *Idempotency Key* dan *Unique Constraint* di database?

5. **Penanganan *Poison Pill Message* dan Desain Dead Letter Queue (DLQ):**  
   Sebuah worker crash berulang kali karena mendapati payload JSON yang korup atau bernilai null pada *field* wajib. Tanpa mitigasi, pesan ini akan terus di-*requeue*, memicu *infinite retry loop* yang memakan CPU worker hingga 100%. Rancang strategi penanganan menggunakan *Max Retry Threshold*, *Exponential Backoff*, dan *Dead Letter Queue* (DLQ), serta sebutkan prosedur operasional saat DLQ mulai terisi.

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: *Database Meltdown Akibat Flash Sale Cache Invalidation*
Pada platform *e-commerce*, produk unggulan diskon 90% diakses oleh 50.000 pengguna secara bersamaan. Tim engineering memutuskan untuk meng-update stok produk tersebut di database lalu menghapus (*evict*) cache produk terkait di Redis setiap kali terjadi transaksi. Akibatnya, pada detik pertama flash sale dimulai, CPU Database RDS PostgreSQL langsung melonjak ke 100%, terjadi ribuan *deadlock* dan koneksi database habis (*connection exhaustion*), sehingga seluruh aplikasi tumbang (*total outage*).
- **Pertanyaan Diagnostik:**
  1. Identifikasi *anti-pattern* mendasar dari strategi invalidasi cache di atas saat diterapkan pada beban transaksi tinggi.
  2. Rancang arsitektur revisi untuk menangani sinkronisasi read-write stok barang yang aman dari *database stampede* namun tetap mencegah *overselling* (menjual barang melebihi stok fisik).

### Skenario B: *Double-Debit Akibat Asynchronous Worker Timeout & Auto-Retry*
Aplikasi perbankan digital memiliki background worker untuk memproses transfer dana antar-bank via payment gateway pihak ketiga. Karena latensi jaringan pihak ketiga melonjak dari 500ms menjadi 15 detik, antrean sistem (misal: BullMQ/Sidekiq) menganggap job telah *timed-out* (batas ambang 10 detik), menandainya sebagai *failed*, dan secara otomatis me-requeue job ke worker lain. Hasil akhirnya: saldo nasabah terpotong dua kali untuk satu ID transaksi.
- **Pertanyaan Diagnostik:**
  1. Di layer mana kegagalan arsitektur ini terjadi: transport network, worker state machine, atau database transaction logic?
  2. Rancang solusi arsitektur yang mengombinasikan *distributed lock*, *state-checking (Two-Phase Commit atau status polling)*, dan *idempotency table* untuk menjamin dana tidak akan pernah terdebit dua kali meski job di-*retry* berkali-kali.

### Skenario C: *Trade-Off Teknologi Antrean: Redis List/Streams vs. RabbitMQ vs. Apache Kafka*
Startup logistik yang sedang tumbuh pesat ingin membangun sistem pelacakan armada (*driver location updates*) sekaligus sistem notifikasi order (Push Notification, WhatsApp, SMS). Mereka memiliki resource infrastruktur dan DevOps yang terbatas. Tim junior mengusulkan langsung mengadopsi Apache Kafka cluster untuk semua kebutuhan ini.
- **Pertanyaan Diagnostik:**
  1. Berikan kritik arsitektural terhadap usulan penggunaan Kafka untuk use-case di atas pada tim dengan resource terbatas.
  2. Buat matriks evaluasi trade-off (kompleksitas, retensi pesan, throughput, konkurensi consumer) dan tentukan kombinasi teknologi yang paling rasional untuk sistem pelacakan armada versus sistem notifikasi order mereka.

---

## 4. Chapter Challenge

**Tantangan Praktis: High-Throughput E-Commerce Flash Sale & Async Invoicing Pipeline**

### Problem Statement
Anda diminta merancang subsistem untuk modul *Flash Sale* dan penerbitan *Invoice/Kwitansi PDF*. Endpoint detail produk menerima beban pembacaan masif (*up to* 10.000 RPS). Ketika pesanan berhasil dibuat, sistem harus memproses pembuatan file PDF invoice, mengunggahnya ke Object Storage (S3), dan mengirimkan email konfirmasi ke pembeli tanpa memperlambat latensi response pembuatan order (harus kembali di bawah 150ms).

### Requirements
1. **Cache Layer Implementation:**
   - Implementasikan pola *Cache-Aside* untuk endpoint `GET /api/v1/products/{id}`.
   - Wajib menambahkan mekanisme proteksi terhadap *Cache Avalanche* (menggunakan *jitter*) dan *Cache Stampede* (menggunakan *single-flight request* atau *mutex locking*).
   - Data yang tidak ditemukan di DB harus diproteksi dari *Cache Penetration*.
2. **Asynchronous Background Processing:**
   - Endpoint `POST /api/v1/orders` memvalidasi stok, membuat record order di DB, lalu mengirimkan payload pekerjaan ke sebuah Task Queue (misal: Redis Streams, BullMQ, atau Celery). Endpoint harus langsung merespons ke client tanpa menunggu proses invoice selesai.
   - Worker memproses antrean: men-generate PDF secara asynchronous, melakukan upload ke storage (bisa di-mock), lalu mengirim notifikasi.
   - Wajib ada implementasi semantik *exponential backoff retry* (maksimal 3 kali retry) dan pengalihan ke *Dead Letter Queue* (DLQ) jika proses gagal permanen.
3. **Worker Idempotency:**
   - Eksekusi worker invoice tidak boleh menghasilkan duplikasi file jika pesan diproses ulang akibat *network blip*.

### Constraints
- Larangan memanggil fungsi pembuatan PDF atau pengiriman email secara sinkron di thread HTTP request.
- Beban database utama saat *cache warm* tidak boleh melebihi 2% dari total request pembacaan produk.
- Bebas menggunakan bahasa pemrograman backend backend-agnostik (Node.js, Go, Python, Java). Tidak diperbolehkan menggunakan external managed framework otomatis tanpa memperlihatkan logic antrean dan locking dasarnya.

### Expected Output
1. **Arsitektur Sequence Diagram:** Menggambarkan aliran data antara Client, API Server, Cache, Primary Database, Queue Broker, Worker, dan Storage.
2. **Kode Sumber Terstruktur:**
   - Modul helper cache yang meng-enkapsulasi get, set, mutex locking, dan jitter TTL.
   - Modul Producer (HTTP Handler) yang ringan dan non-blocking.
   - Modul Consumer/Worker dengan error handling, retry backoff logic, dan mekanisme DLQ.
3. **Dokumentasi Uji Verifikasi:**
   - Simulasi log saat cache expired di bawah beban multithread (membuktikan database hanya terkena 1 query).
   - Simulasi log saat worker mengalami error transient (menunjukkan rentang waktu retry backoff) dan error fatal (menunjukkan data masuk ke DLQ).

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Perbedaan fundamental dan trade-off antara Cache-Aside, Write-Through, dan Write-Back.
- [ ] Dampak perbedaan kecepatan I/O antara Redis memory access (sub-millisecond) dan Database disk access (millisecond).
- [ ] Tiga anomali besar caching: Cache Stampede, Cache Penetration, dan Cache Avalanche beserta penangkal bakunya.
- [ ] Mengapa Cache Invalidation dianggap sebagai salah satu dari dua masalah paling sulit dalam Computer Science (*Dual-Write problem*).
- [ ] Prinsip pemisahan beban komputasi sinkron (*fast path*) dan asinkron (*slow path* via Background Job).
- [ ] Karakteristik *At-Least-Once Delivery* dan kewajiban merancang Consumer yang *Idempotent*.
- [ ] Siklus hidup job antrean: Enqueue $\to$ Processing $\to$ Ack/Nack $\to$ Retry Backoff $\to$ Dead Letter Queue (DLQ).

### Saya tidak perlu menghafal:
- [ ] Formula matematis algoritma kompresi memori jemalloc di Redis internal.
- [ ] Konfigurasi low-level wire-protocol packet frames dari protokol AMQP atau Kafka binary protocol.
- [ ] Parameter konfigurasi tuning kernel Linux untuk OS memory swapping Redis (`vm.overcommit_memory`) di luar kebutuhan implementasi dasar.
- [ ] Seluruh command line syntax CLI dari Redis (misal: argumen spesifik dari script Lua `EVAL` kompleks) cukup memahami perintah dasar `GET`, `SET`, `SETNX`, `DEL`, `EXPIRE`.

### Saya harus bisa melakukan:
- [ ] Mengimplementasikan pola Cache-Aside yang tangguh dari nol dengan fallback query ke database.
- [ ] Mengaplikasikan *Jitter* (variasi random) pada TTL cache untuk mencegah kegagalan massal serentak.
- [ ] Memisahkan tugas berat dari controller HTTP ke dalam message broker menggunakan library task queue.
- [ ] Mengonfigurasi worker antrean dengan kebijakan *Exponential Backoff* dan menangani kegagalan permanen ke *Dead Letter Queue*.
- [ ] Menerapkan mekanisme Idempotency Key berbasis Redis lock atau Database Unique Constraint untuk mencegah duplikasi pemrosesan data di background worker.