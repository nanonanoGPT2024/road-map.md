---
[⬅️ Module 01: RabbitMQ vs Apache Kafka](./Module-01-Message-Queues-vs-Event-Streaming-Kafka-RabbitMQ.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---

# Module 02: Idempotent Consumers, Dead Letter Queues (DLQ), & Transactional Outbox

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi 3 level jaminan pengiriman pesan: **At-Most-Once**, **At-Least-Once**, dan **Effectively-Once** dalam realitas jaringan terdistribusi.
- Merancang **Idempotent Consumer** yang kebal terhadap duplikasi pengiriman pesan menggunakan tabel dedup (*Deduplication Store*) dan *Natural Idempotency Keys*.
- Menangani pesan beracun (*Poison Pill Messages*) menggunakan **Dead Letter Queue (DLQ)** dan strategi retry bertahap (**Exponential Backoff with Jitter**).
- Memahami bahaya fatal **Dual-Write Problem** (menulis ke database dan mempublikasikan pesan ke broker secara terpisah).
- Mengimplementasikan pola arsitektur **Transactional Outbox** menggunakan transaksi lokal ACID database dan **Change Data Capture (CDC)** via Debezium / Kafka Connect.

---

## 2. Prerequisite
- Memahami konsep dasar Message Queues & Partisi Kafka (Modul 01).
- Memahami transaksi database ACID dan tingkatan isolasi (BAB 04).
- Pemahaman status idempotensi HTTP (BAB 03).

---

## 3. Concept
Dalam sistem terdistribusi riil di mana jaringan fisik tidak pernah 100% andal (*The Fallacies of Distributed Computing*):
Setiap pesan yang dikirim melalui message broker dapat mengalami kegagalan jaringan pada saat pengiriman ACK. Akibatnya, broker menganggap pesan belum diproses dan mengirimkannya kembali (**Duplicate Delivery**).

Sebuah sistem backend tidak boleh berasumsi pesan hanya akan diterima tepat satu kali. Standar industri menetapkan bahwa jaminan broker terkuat adalah **At-Least-Once Delivery** (Pesan dijamin sampai minimal 1 kali, namun bisa lebih dari 1 kali).

Oleh karena itu, tanggung jawab menjamin keamanan data transaksi berada di tangan **Consumer Backend** melalui prinsip **Idempotensi**:
Operasi pemrosesan pesan harus menghasilkan dampak status bisnis yang identik, baik dieksekusi 1 kali maupun diulang 10 kali.

---

## 4. Why?
Tanpa penanganan Idempotency, DLQ, dan Transactional Outbox:
1. **Double Charging / Saldo Terpotong Dua Kali:** Consumer pembayaran menerima duplikat pesan `PROCESS_PAYMENT` karena *network blip* saat worker mengirim ACK, menyebabkan rekening nasabah didebit dua kali.
2. **Infinite Crash Loop (Poison Pill):** Pesan dengan format JSON rusak atau nilai tak terduga menyebabkan worker throw uncaught exception. Worker me-requeue pesan, crash lagi, me-requeue lagi, hingga seluruh CPU cluster 100% terkunci dalam loop kegagalan.
3. **Inkonsistensi Dual-Write Fatal:** Aplikasi menyimpan pesanan baru ke tabel `orders` database SQL, namun sebelum perintah `kafka.send()` selesai, server mati lampu atau pod mati. Pesanan tersimpan di database, tetapi event tidak pernah terkirim ke sistem gudang dan pengiriman (*Ghost Order*). Sebaliknya, jika event terkirim namun commit SQL gagal, gudang mengirim barang yang tidak pernah dibayar!

---

## 5. What? (Pola-Pola Kunci Keandalan Asinkron)

### A. Idempotent Consumer Pattern
Mekanisme di mana consumer memeriksa apakah pengenal unik pesan (*Event ID / Correlation ID*) sudah pernah berhasil diproses sebelum menjalankan logika bisnis.

### B. Dead Letter Queue (DLQ)
Antrean khusus (*Isolasi Karantina*) tempat menampung pesan-pesan yang berulang kali gagal diproses setelah melampaui batas percobaan maksimum (*Max Retries*). Pesan di DLQ tidak menghambat antrean utama dan dapat diinvestigasi atau di-replay secara manual oleh engineer.

### C. Transactional Outbox Pattern
Pola arsitektur untuk memecahkan masalah Dual-Write:
Aplikasi **tidak pernah** memanggil broker secara langsung di tengah transaksi bisnis! Sebagai gantinya, event disimpan ke dalam tabel lokal khusus bernama `outbox` di database yang sama dalam **satu transaksi ACID lokal yang atomik**.

---

## 6. How? (Arsitektur Transactional Outbox & CDC)

```
[ Backend Application ]
         │
         ▼
[ Local ACID Transaction ]
 ├── 1. INSERT INTO orders (id, user_id, amount) VALUES ('ORD-101', ...);
 └── 2. INSERT INTO outbox_events (event_id, aggregate_type, payload) VALUES ('EVT-88', 'Order', '{...}');
 └── COMMIT; (Keduanya sukses bersama atau gagal bersama!)
         │
         ▼
[ Transaction Log / Write-Ahead Log (WAL) Database ]
         │
         ▼ (Change Data Capture / Debezium Engine)
[ Kafka Connect / CDC Debezium ]
         │
         ▼ (Stream Event ke Broker)
[ Apache Kafka Topic: 'order-events' ]
         │
         ▼
[ Downstream Consumer Services (Warehouse, Shipping, Billing) ]
```
1. Backend hanya berinteraksi dengan satu database primer.
2. Order dan Event Outbox disimpan dalam transaksi atomik lokal yang dijamin oleh mesin ACID RDBMS.
3. Tool **Change Data Capture (CDC)** (seperti Debezium) membaca file transaction log/WAL Postgres/MySQL secara asinkron dan mempublikasikan record outbox ke Kafka dengan latensi sub-detik.

---

## 7. Analogy
Bayangkan Anda memesan barang di toko fisik:
- **Dual-Write Problem:** Anda menyerahkan uang ke kasir, lalu kasir harus menelpon gudang via telepon radio. Jika baterai radio tiba-tiba mati saat kasir baru selesai menyimpan uang di laci, gudang tidak pernah tahu Anda sudah bayar.
- **Transactional Outbox:** Kasir tidak menelpon radio. Kasir menaruh uang di laci kasir sekaligus mencetak struk karbon kedua ke dalam nampan "Antrean Gudang" di meja kasir. Keduanya berada di meja yang sama. Seorang kurir khusus (CDC) bertugas mengambil struk dari nampan setiap beberapa detik untuk diserahkan ke gudang. Struk tidak akan pernah tertinggal.

---

## 8. Diagram: Alur Eksekusi Idempotent Consumer dengan Dead Letter Queue (DLQ)

```
[ Pesan Masuk dari Broker ] (event_id: 'EVT-001', order_id: 'ORD-99')
            │
            ▼
{ Cek Tabel 'processed_events' }
            │
    ┌───────┴───────┐
 (Sudah Ada?)     (Belum Ada)
    │               │
    ▼ (Duplikat)     ▼
[ Kirim ACK Langsung ] ──▶ [ Eksekusi Logika Bisnis (Debit Saldo) ]
(Abaikan Pemrosesan)               │
                           ┌───────┴───────┐
                        (Sukses)        (Gagal / Error)
                           │               │
                           ▼               ▼
           [ INSERT processed_events ]  [ Hitung Retry Counter ]
           [ Kirim ACK ke Broker ]         │
                                   ┌───────┴───────┐
                               (Retry < Max)   (Retry >= Max)
                                   │               │
                                   ▼               ▼
                        [ Exponential Backoff ] [ Kirim ke DLQ ]
                        [ Requeue / Wait ]      [ Kirim ACK ke Main Queue ]
```

---

## 9. Simple Example: Retry dengan Exponential Backoff & Jitter

```javascript
async function executeWithRetry(operation, maxRetries = 3, baseDelayMs = 100) {
  let attempt = 0;
  while (true) {
    try {
      return await operation();
    } catch (err) {
      attempt++;
      if (attempt > maxRetries) {
        throw new Error(`Exceeded max retries (${maxRetries}). Cause: ${err.message}`);
      }

      // Formula Exponential Backoff + Random Jitter
      // Delay = base * 2^(attempt-1) + random(0..50ms)
      const exponentialDelay = baseDelayMs * Math.pow(2, attempt - 1);
      const jitter = Math.random() * 50;
      const totalDelay = exponentialDelay + jitter;

      console.warn(`[Retry #${attempt}] Gagal: ${err.message}. Menunggu ${totalDelay.toFixed(0)} ms...`);
      await new Promise(r => setTimeout(r, totalDelay));
    }
  }
}
```

---

## 10. Practical Example: Implementasi Idempotent Consumer Service

```javascript
class PaymentConsumerService {
  constructor(dbClient) {
    this.db = dbClient;
  }

  async handlePaymentEvent(message) {
    const { eventId, orderId, amount, customerId } = message;

    // Membuka database transaction
    const client = await this.db.connect();
    try {
      await client.query('BEGIN');

      // 1. Cek Idempotensi: Coba insert ke tabel dedup
      // Menggunakan ON CONFLICT DO NOTHING untuk atomic uniqueness
      const dedupResult = await client.query(
        `INSERT INTO processed_events (event_id, event_type, created_at)
         VALUES ($1, 'PAYMENT_PROCESSED', NOW())
         ON CONFLICT (event_id) DO NOTHING`,
        [eventId]
      );

      // Jika baris tidak ter-insert, berarti event ID ini sudah pernah diproses sebelumnya!
      if (dedupResult.rowCount === 0) {
        console.log(`[IDEMPOTENT SKIP] Event ${eventId} sudah pernah diproses. Melewati...`);
        await client.query('ROLLBACK');
        return { status: 'DUPLICATE_IGNORED' };
      }

      // 2. Eksekusi Logika Bisnis (Debit Rekening)
      await client.query(
        'UPDATE accounts SET balance = balance - $1 WHERE customer_id = $2',
        [amount, customerId]
      );

      await client.query(
        'UPDATE orders SET payment_status = $1 WHERE id = $2',
        ['PAID', orderId]
      );

      // 3. Commit Transaksi
      await client.query('COMMIT');
      console.log(`[SUCCESS] Pembayaran order ${orderId} berhasil diproses.`);
      return { status: 'SUCCESS' };

    } catch (err) {
      await client.query('ROLLBACK');
      throw err; // Lempar error agar ditangani oleh mekanisme Retry/DLQ
    } finally {
      client.release();
    }
  }
}
```

---

## 11. Real World Example: Migrasi Monolith ke Microservices di Industri Fintech

Sebuah bank digital memisahkan service Core Banking (RDBMS) dari Notifikasi dan Fraud Detection:
1. Saat nasabah mentransfer dana, transaksi SQL memotong saldo di database Oracle dan secara atomik menulis event ke tabel `TRANSACTION_OUTBOX`.
2. Kluster Debezium CDC membaca redo-log Oracle dan mempublikasikan event transfer ke Kafka Topic `financial.transactions.v1`.
3. Tiga consumer independen menerima event tersebut:
   - **Fraud Detection Engine:** Menghitung skor anomali dalam 5 ms.
   - **Notification Service:** Mengirim push notification ke smartphone nasabah. Jika gateway WhatsApp down, pesan dialihkan ke DLQ untuk dievaluasi ulang tanpa mengganggu alur transfer.
   - **Data Lake Sync:** Memuat data ke BigQuery untuk pelaporan audit regulator.

Hasil: Integritas saldo perbankan 100% terjaga tanpa pernah ada saldo terpotong dua kali atau event transfer yang hilang.

---

## 12. Trade-offs

| Pendekatan Integrasi | Keandalan Data | Kompleksitas Arsitektur | Dampak Latensi | Risiko Terburuk |
|---|---|---|---|---|
| **Direct Dual-Write (DB + Kafka)** | Sangat Buruk (Sering Inkonsisten) | Sangat Sederhana | Sangat Cepat | Ghost Records / Kehilangan Event permanen |
| **Two-Phase Commit (2PC / XA)** | Kuat (ACID Terdistribusi) | Ekstrem | Lambat (Locking lama lintas node) | Koordinator mati memicu *Blocking Deadlock* global |
| **Transactional Outbox + Polling Worker** | Tinggi | Menengah | Sedang (Polling interval 1-3 detik) | Beban query polling periodik ke database |
| **Transactional Outbox + CDC (Debezium)**| Ekstrem (Standar Emas Industri) | Tinggi (Butuh Kafka Connect + Debezium) | Sub-detik (~10-50 ms) | Kompleksitas operasional pemeliharaan CDC cluster |

---

## 13. When To Use
- **Setiap Consumer yang Melakukan Operasi Finansial atau State Mutation:** Pengurangan stok inventaris, pemotongan kuota, pengiriman uang, atau perubahan status pesanan.
- **Sistem Microservices Berbasis Event-Driven:** Wajib menggunakan Transactional Outbox di setiap service yang menjadi penerbit event (*Producer*).
- **Integrasi dengan Vendor Pihak Ketiga (Third-Party APIs):** Mengirim webhook, SMS, atau email yang rentan terhadap timeout jaringan, memerlukan DLQ dan Exponential Backoff.

---

## 14. When NOT To Use
- **Data Metrik & Telemetri Sensor IoT yang Boleh Hilang (Ephemeral):** Mengirim metrik penggunaan CPU setiap detik tidak membutuhkan Transactional Outbox atau DLQ. Jika satu paket metrik hilang di jaringan, metrik detik berikutnya akan menggantikannya (*At-Most-Once is sufficient*).
- **Operasi yang Murni Read-Only (Idempotent by Nature):** Permintaan query GET atau logging analitik yang tidak mengubah status bisnis dapat mengabaikan tabel dedup kompleks.

---

## 15. Common Mistakes
1. **Idempotency Key Berbasis Waktu / Non-Deterministik:** Menggunakan `timestamp` atau `randomUUID()` yang baru dibuat di consumer sebagai kunci dedup. Kunci dedup harus berasal dari **atribut unik entitas asal** (misal: `order_id` atau `payment_ref_no`).
2. **Re-Queue Pesan Beracun Selamanya:** Mengirim pesan yang gagal diparse kembali ke queue tanpa batas (*infinite retry*). Queue akan macet dan seluruh throughput pemrosesan terhenti.
3. **Mengabaikan Idempotensi pada Sisi Producer:** Mengirim payload tanpa menyertakan `idempotency_key` di header pesan, menyulitkan downstream consumer untuk melakukan deduplikasi.
4. **Menghapus Record Outbox Sebelum Terkirim:** Menghapus event outbox menggunakan trigger DB alih-alih membiarkan CDC menandai offset log.

---

## 16. Best Practices

### Must Have
- Desain seluruh consumer agar bersifat **Idempotent**. Jangan pernah berasumsi broker hanya mengirim pesan 1 kali.
- Konfigurasi batasan retry maksimum (misal: `max_retries = 3`), dan segera alihkan pesan yang terus gagal ke **Dead Letter Queue (DLQ)**.
- Gunakan transaksi ACID lokal untuk menulis entitas bisnis bersamaan dengan record outbox.

### Recommended
- Sertakan **Random Jitter** pada algoritma Exponential Backoff untuk mencegah fenomena sinkronisasi retry massal (*Thundering Herd on Retry*).
- Berikan alert monitoring pada metrik `dlq_messages_total`. Adanya pesan di DLQ menandakan bug kode atau anomali data yang butuh perhatian developer.

### Advanced
- Buat automated CLI atau tool admin dashboard untuk melakukan **DLQ Replay** (mengirimkan kembali pesan yang sudah diperbaiki dari DLQ ke antrean produksi utama).

---

## 17. Troubleshooting

| Masalah | Kemungkinan Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Pesan Terus Menerus Masuk DLQ** | Perubahan skema JSON (*Schema Drift*) atau bug parsing kode | Inspeksi payload pesan di DLQ, cek stack trace error consumer | Perbarui skema data consumer, deploy hotfix, lalu jalankan DLQ replay |
| **Tabel Outbox Membengkak Menjadi Jutaan Baris** | CDC Debezium mati atau skrip polling outbox berhenti berjalan | Cek status Kafka Connect connector (`GET /connectors/outbox-connector/status`) | Nyalakan kembali connector CDC, buat job cron pembersihan (*purging*) baris outbox lama |
| **Data Ganda Muncul di Database** | Kegagalan isolasi transaksi dedup atau lupa menambahkan constraint `UNIQUE` | Periksa skema tabel `processed_events`, pastikan kolom `event_id` memiliki `PRIMARY KEY` | Tambahkan indeks unik dan gunakan klausul `ON CONFLICT DO NOTHING` |

---

## 18. Exercise
1. Rancang skrip Node.js yang memproses antrean pesan pesanan e-commerce dengan simulator kegagalan acak (30% kegagalan jaringan).
2. Terapkan mekanisme retry bertahap (Exponential Backoff: 100ms, 200ms, 400ms).
3. Jika pesan gagal setelah 3 percobaan, alihkan pesan tersebut ke dalam antrean DLQ.
4. Simulasikan pengiriman duplikat dari pesan yang sama dan buktikan tabel dedup mencegah eksekusi ganda.

---

## 19. Challenge
Rancang arsitektur **Financial Ledger Core Banking** yang memproses 500.000 transaksi pembayaran per hari:
1. Rancang skema database tabel `accounts`, `journal_entries`, `deduplication_keys`, dan `transaction_outbox`.
2. Jelaskan bagaimana arsitektur Anda menjamin konsistensi mutlak: tidak ada uang yang hilang, tidak ada uang yang tercipta dari ketiadaan, dan setiap kegagalan jaringan dapat di-recovery secara otomatis tanpa intervensi manual!

---

## 20. Summary
Dalam arsitektur terdistribusi modern, kegagalan jaringan dan duplikasi pengiriman pesan adalah kepastian statistik. Dengan menerapkan Idempotent Consumers, mengisolasi kegagalan fatal ke Dead Letter Queue, dan menghapuskan masalah Dual-Write melalui Transactional Outbox Pattern, sistem backend Anda akan mencapai tingkat ketahanan dan reliabilitas standar industri perbankan global.

---
[⬅️ Module 01: RabbitMQ vs Apache Kafka](./Module-01-Message-Queues-vs-Event-Streaming-Kafka-RabbitMQ.md) | [📋 Silabus Induk](../README.md) | [BAB 07 Quiz & Challenge ➡️](./BAB-07-Quiz-dan-Challenge.md)
---
