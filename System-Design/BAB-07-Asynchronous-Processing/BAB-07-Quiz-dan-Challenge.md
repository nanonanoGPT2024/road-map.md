# BAB 07 — Evaluasi, Quiz, & Chapter Challenge
## Asynchronous Processing, Message Brokers, & Streaming

---

## 🎯 Ringkasan Bab

Dalam Bab ini, kita telah mendalami arsitektur sistem asinkron berskala tinggi:
1. **Message Queues vs Event Streaming**: Membedakan arsitektur destruktif (RabbitMQ) vs persisten append-only log (Apache Kafka), partisi, offset, dan multi-consumer replay.
2. **Delivery Guarantees & Resilience**: Mengapa di dunia nyata sistem terdistribusi mengadopsi *At-Least-Once*, bagaimana mencegah *double billing* dengan *Idempotency Key*, serta mengisolasi *poison pill* dengan *Dead Letter Queue (DLQ)*.
3. **CQRS & Event Sourcing**: Memisahkan write model dan read model, menyimpan fakta domain masa lalu sebagai audit trail abadi, snapshotting, dan mitigasi eventual consistency.

---

## 🧠 Knowledge Check

### Saya Harus Memahami:
- [ ] Mengapa Kafka mampu mencapai jutaan throughput/detik (Sequential Disk I/O, Page Cache, Zero-Copy OS transfer `sendfile`).
- [ ] Perbedaan perilaku konsumsi data: RabbitMQ menghapus pesan setelah ACK, sedangkan Kafka mempertahankan pesan di disk sesuai retensi waktu.
- [ ] Mengapa "Exactly-Once Physical Delivery" adalah kemustahilan di jaringan terdistribusi tanpa deduplikasi di level aplikasi (*At-Least-Once + Idempotency*).
- [ ] Peran Dead Letter Queue (DLQ) dalam mencegah *infinite crash loop* atau *queue blockage*.
- [ ] Bagaimana CQRS menyelesaikan masalah perbedaan skala baca (query) dan tulis (command).

### Saya Tidak Perlu Menghafal:
- Format biner internal dari protokol AMQP framing atau format file index `.index` / `.timeindex` Kafka di disk.
- Semua konfigurasi parameter tuning tingkat rendah JVM di Apache Kafka (`num.replica.fetchers`, `unclean.leader.election.enable`).

### Saya Harus Bisa Melakukan:
- [ ] Memilih antara RabbitMQ vs Kafka berdasarkan kebutuhan bisnis (Task Queue vs Event Backbone).
- [ ] Merancang tabel deduplikasi / skema Idempotency Key untuk API transaksi.
- [ ] Mengimplementasikan pola Snapshotting untuk Aggregate Event Sourcing.

---

## ❓ Quiz Evaluasi

### Bagian A: Pertanyaan Konseptual Fundamental (5 Soal)
1. **Apa perbedaan mendasar antara model "Smart Broker, Dumb Consumer" (RabbitMQ) dan "Dumb Broker, Smart Consumer" (Kafka)?**
2. **Jika sebuah Consumer di Kafka membaca dari Topic dengan 4 partisi, berapa jumlah maksimum instance Consumer dalam satu Consumer Group yang dapat bekerja secara paralel?**
3. **Mengapa pesan duplikat seringkali terjadi pada sistem yang mengklaim menggunakan At-Least-Once Delivery?**
4. **Apa yang dimaksud dengan Poison Pill dalam konteks message queue consumer?**
5. **Dalam Event Sourcing, mengapa event yang sudah tercatat di Event Store tidak boleh diubah (immutable)?**

### Bagian B: Analisis & Intermediate (5 Soal)
6. **Sebuah sistem e-commerce ingin mengirim notifikasi WhatsApp, membuat faktur pajak PDF, dan memperbarui analitik saat checkout terjadi. Manakah yang lebih cocok: RabbitMQ Fanout Exchange atau Kafka Topic? Jelaskan alasannya.**
7. **Mengapa penambahan indeks `UNIQUE` pada kolom `idempotency_key` di database relasional merupakan cara paling andal untuk menjamin idempotency transaksi?**
8. **Jelaskan risiko dari "Immediate Retry Loop" tanpa exponential backoff ketika sebuah downstream database mengalami lonjakan beban tinggi.**
9. **Bagaimana Snapshotting mencegah degradasi performa pada sistem Event Sourcing yang memiliki akun dengan jutaan riwayat mutasi?**
10. **Apa yang dimaksud dengan "Read-Your-Own-Writes Consistency" dan bagaimana cara mengatasinya pada arsitektur CQRS dengan Read Model yang terdenormalisasi?**

### Bagian C: Scenario-Based System Architecture (3 Soal)
11. **Skenario 1: Flash Sale E-Commerce dengan 100.000 Pesanan per Menit**  
   Database SQL utama Anda akan kolaps jika menerima 100.000 `INSERT` per menit secara langsung.
   - Rancang arsitektur buffer perpesanan (Ingestion Queue, Worker Group, Database Batch Writer).
   - Bagaimana strategi Anda menangani jika pembayaran pengguna sukses tetapi stok barang fisik di gudang tiba-tiba habis (Saga Compensating Transaction)?

12. **Skenario 2: Fraud Detection Pipeline di Bank Digital**  
   Tim data science ingin mendeteksi pola transaksi mencurigakan secara real-time dari jutaan kartu debit, dan mereka sering memperbarui model AI mereka.
   - Mengapa Apache Kafka lebih unggul dibandingkan RabbitMQ untuk skenario ini?
   - Bagaimana tim dapat mem-validasi model AI baru mereka terhadap transaksi 14 hari yang lalu tanpa mengganggu sistem production?

13. **Skenario 3: Core Ledger Dompet Digital (E-Wallet)**  
   Regulator keuangan mewajibkan audit trail yang tidak dapat dimanipulasi sama sekali untuk seluruh saldo pengguna.
   - Rancang skema Event Sourcing (Domain Events, Event Store, Snapshot Store, dan Account Summary View).
   - Tunjukkan bagaimana Anda melakukan rekonsiliasi jika terjadi perbedaan saldo antara Read View dan Event Store.

---

## 🏆 Chapter Challenge: Resilient Multi-Stage Order Processing Engine

### Problem Statement
Rancang arsitektur asinkron untuk sistem pemrosesan pesanan logistik skala nasional:
- Tahap 1: `OrderPlaced`
- Tahap 2: `PaymentAuthorized` (Bisa timeout / gagal)
- Tahap 3: `WarehouseItemReserved`
- Tahap 4: `CourierDispatched`

### Requirements:
1. **Zero Data Loss**: Tidak boleh ada pesanan yang hilang di tengah jalan meski ada server yang mati mendadak.
2. **Idempotent Handlers**: Setiap worker harus tahan terhadap retry pengiriman pesan hingga 5 kali tanpa menduplikasi pesanan kurir atau menduplikasi pemotongan stok.
3. **Automated DLQ & Alerting**: Jika API kurir pihak ketiga sedang maintenance dan mengembalikan status HTTP 503 berulang kali, pesan harus masuk ke DLQ dengan notifikasi PagerDuty ke tim on-call.
4. **Auditability**: Pelanggan dan customer service dapat melihat riwayat status pesanan dari awal hingga akhir dengan timeline kronologis lengkap.
