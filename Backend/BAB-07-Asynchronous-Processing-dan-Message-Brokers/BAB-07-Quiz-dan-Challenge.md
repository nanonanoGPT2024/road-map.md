---
[⬅️ Module 02: Idempotent Consumer & Outbox Pattern](./Module-02-Idempotent-Consumers-DLQ-dan-Transactional-Outbox.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Autentikasi, Otorisasi, & Keamanan ➡️](../BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/Module-01-Auth-Session-JWT-OAuth2-OIDC-PKCE.md)
---

# BAB 07: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur Asynchronous Processing & Message Brokers

Selamat! Anda telah menyelesaikan seluruh materi pada **BAB 07: Asynchronous Processing & Message Brokers**. Modul evaluasi ini menguji pemahaman mendalam Anda mengenai arsitektur message broker, teknik mitigasi duplikasi data terdistribusi, serta pola pengiriman event berkeandalan tinggi (*Mission-Critical Event Reliability*).

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan perbedaan mendasar antara filosofi "Smart Broker / Dumb Consumer" (RabbitMQ) dan "Dumb Broker / Smart Consumer" (Apache Kafka)!**
2. **Apa yang dimaksud dengan Consumer Offset di Apache Kafka?** Mengapa penyimpanan offset di sisi broker/consumer memungkinkan consumer memutar ulang (*replay*) data dari masa lalu?
3. **Mengapa penentuan Partition Key sangat krusial di Apache Kafka?** Apa konsekuensi fatal jika sebuah sistem mengirimkan event pembaruan saldo akun tanpa menyertakan partition key?
4. **Apa perbedaan antara jaminan pengiriman At-Least-Once dan Exactly-Once dalam sistem jaringan terdistribusi riil?** Mengapa At-Least-Once yang dipadukan dengan Idempotent Consumer dianggap sebagai standar industri paling andal?
5. **Apa yang dimaksud dengan Poison Pill Message?** Mengapa tanpa Dead Letter Queue (DLQ), sebuah pesan poison pill dapat melumpuhkan seluruh cluster consumer secara permanen (*Crash Loop*)?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Kafka Zero-Copy Disk I/O:**
   Jelaskan bagaimana pemanggilan system call Linux `sendfile()` memungkinkan broker Kafka mengirimkan data dari disk langsung ke antarmuka kartu jaringan (NIC) tanpa melibatkan CPU context switching dan memory copy di JVM heap!
7. **Bencana Dual-Write Problem:**
   Sebuah aplikasi e-commerce menjalankan kode:
   ```javascript
   await db.insertOrder(order);
   await kafkaProducer.send('order-topic', order);
   ```
   Analisis dua skenario kegagalan fatal di mana salah satu operasi berhasil namun operasi lainnya gagal! Bagaimana pola **Transactional Outbox** memecahkan masalah ini?
8. **Skalabilitas Consumer Group vs Partisi:**
   Jika sebuah Kafka Topic memiliki 6 partisi, dan tim infrastruktur men-deploy 10 instance worker container dalam satu Consumer Group yang sama, berapa banyak worker yang aktif memproses data dan berapa banyak worker yang menganggur (*idle*)? Apa yang terjadi jika salah satu worker aktif mengalami crash?
9. **Backpressure & Prefetch Count pada RabbitMQ:**
   Mengapa tidak membatasi nilai `prefetch` pada RabbitMQ consumer dapat memicu bencana *Out-Of-Memory* (OOM) pada container backend saat terjadi lonjakan 100.000 pesan baru?
10. **Exponential Backoff dengan Random Jitter:**
    Tuliskan formula matematis penambahan jitter acak pada algoritma exponential backoff! Masalah sinkronisasi konkurensi apa (*Thundering Herd on Retry*) yang berhasil dihindari dengan pemberian jitter ini?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: Saldo Rekening Terpotong Ganda Akibat Timeout Jaringan
Sebuah layanan dompet digital memproses pembayaran tagihan listrik melalui Kafka consumer. Worker menerima event `PAY_BILL`, berhasil memotong saldo nasabah di database PostgreSQL, namun tepat saat worker mengirimkan commit ACK offset ke broker Kafka, jaringan internet antara worker dan Kafka terputus selama 2 detik.
Broker menganggap worker mati, melakukan rebalance, dan mengirim ulang event `PAY_BILL` yang sama ke worker lain. Worker kedua kembali memotong saldo nasabah untuk kedua kalinya.
- **Analisis:** Mengapa arsitektur ini cacat secara desain?
- **Solusi Arsitektur:** Rancang skema database tabel deduplikasi dan modifikasi kode consumer agar operasi pemotongan saldo bersifat **Idempotent** secara atomik!

### Skenario B: Antrean Macet Akibat Poison Pill Format Tanggal
Sebuah layanan logistik menerima event manifest paket pengiriman via RabbitMQ. Salah satu vendor pihak ketiga mengirim pesan dengan format tanggal yang salah (`"ship_date": "31-02-2026"`).
Fungsi parsing parser worker melempar `InvalidDateFormatException`. Karena error tidak tertangani secara tepat, worker melakukan `nack(requeue: true)`. RabbitMQ langsung mendorong kembali pesan tersebut ke urutan terdepan antrean, memicu crash loop 100x per detik dan menahan 50.000 paket normal lainnya di belakangnya.
- **Identifikasi Masalah:** Mengapa me-requeue pesan cacat secara membabi buta adalah antipattern fatal?
- **Solusi Rekayasa:** Rancang alur penanganan error bertahap: tangkap exception, hitung percobaan retry di message header (`x-retry-count`), dan alihkan ke Dead Letter Queue (DLQ) jika gagal $\ge 3$ kali!

### Skenario C: Outbox Polling vs Change Data Capture (CDC)
Sebuah sistem backend monolitik yang sedang dimigrasikan ke microservices menggunakan pola Transactional Outbox. Tim awalnya menggunakan skrip cron yang menjalankan query:
`SELECT * FROM outbox WHERE status = 'PENDING' LIMIT 500 FOR UPDATE` setiap 1 detik.
Seiring bertambahnya volume transaksi (10.000 transaksi/detik), query polling ini membebani database utama dan menghabiskan resource disk I/O.
- **Rekomendasi Arsitektur:** Jelaskan bagaimana mengganti mekanisme polling dengan mesin **Change Data Capture (CDC)** seperti Debezium yang membaca Write-Ahead Log (WAL) PostgreSQL secara langsung dapat memangkas beban CPU database dan menurunkan latensi streaming event ke sub-detik!

---

## 4. Chapter Challenge: Arsitektur Pemrosesan Transaksi Pembayaran Global

### Deskripsi Masalah
Rancang arsitektur pemrosesan pembayaran asinkron untuk platform SaaS global yang melayani 20.000.000 transaksi per hari:
1. **Producer Side (Payment API):**
   - Menerima request HTTP POST checkout dari aplikasi web/mobile.
   - Wajib mencatat transaksi ke database SQL dan menerbitkan event ke Apache Kafka Topic `payment-transactions` tanpa risiko Dual-Write.
2. **Streaming Pipeline:**
   - Menjamin bahwa seluruh event yang berkaitan dengan `user_id` atau `merchant_id` yang sama diproses secara kronologis dan tidak pernah saling mendahului.
3. **Consumer Side (Settlement & Notification):**
   - Menjamin saldo merchant dikreditkan tepat 1 kali (*Idempotent*).
   - Menangani kegagalan gateway bank eksternal dengan Exponential Backoff + Jitter.
   - Mengisolasi transaksi yang ditolak permanen oleh bank ke dalam Dead Letter Queue lengkap dengan alasan audit log.

### Instruksi Pengerjaan
Buat laporan arsitektur teknis yang memuat:
1. Diagram alur data end-to-end (dari HTTP Client -> API Gateway -> PostgreSQL Outbox -> Debezium CDC -> Kafka Topic -> Consumer Worker -> DLQ).
2. Desain skema tabel database (`payments`, `outbox_events`, `processed_idempotency_keys`).
3. Spesifikasi konfigurasi Kafka Producer (`acks=all`, `idempotence=true`) dan Consumer Group.

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Perbedaan fundamental antara message queue berbasis transient (RabbitMQ) vs append-only commit log (Kafka).
- [ ] Konsep partisi, offset, dan consumer group dalam penskalaan horizontal Kafka.
- [ ] Bahaya fatal dari Dual-Write Problem pada sistem terdistribusi.
- [ ] Prinsip kerja Transactional Outbox Pattern dan Change Data Capture (CDC).
- [ ] Mekanisme Idempotent Consumer menggunakan tabel deduplikasi unik.
- [ ] Fungsi strategis Dead Letter Queue (DLQ) dan mitigasi Poison Pill.

### Saya Tidak Perlu Menghafal:
- Nilai biner dari spesifikasi protokol wire AMQP 0-9-1.
- Seluruh ratusan opsi parameter konfigurasi broker Kafka (`server.properties`).

### Saya Harus Bisa Melakukan:
- [ ] Merancang skema Partition Key yang menjamin keterurutan kronologis data per entitas.
- [ ] Menulis consumer service yang kebal terhadap duplikasi pengiriman pesan.
- [ ] Mengimplementasikan algoritma retry dengan Exponential Backoff dan Random Jitter.
- [ ] Menyiapkan antrean karantina DLQ untuk mengisolasi pesan cacat tanpa menghentikan sistem produksi.

---
[⬅️ Module 02: Idempotent Consumer & Outbox Pattern](./Module-02-Idempotent-Consumers-DLQ-dan-Transactional-Outbox.md) | [📋 Silabus Induk](../README.md) | [BAB 08: Autentikasi, Otorisasi, & Keamanan ➡️](../BAB-08-Autentikasi-Otorisasi-dan-Keamanan-Backend/Module-01-Auth-Session-JWT-OAuth2-OIDC-PKCE.md)
---
