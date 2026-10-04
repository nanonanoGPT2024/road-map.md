# Module 02: Delivery Guarantees, Idempotency, & Dead Letter Queue (DLQ)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Membedakan tiga tingkatan delivery guarantee: *At-Most-Once*, *At-Least-Once*, dan *Exactly-Once*.
- Memahami mengapa duplikasi pesan tidak dapat dihindari pada sistem terdistribusi akibat network failure (*Two Generals' Problem*).
- Mengimplementasikan pola penanganan duplikasi dengan **Idempotency Key** dan **Deduplication Store**.
- Merancang strategi penanganan pesan gagal bayar / rusak (*Poison Pill*) menggunakan **Dead Letter Queue (DLQ)** dan Exponential Backoff.

## 2. Prerequisite
- Memahami konsep Producer, Message Broker, dan Consumer dari Module 01.
- Memahami konsep transaksi basis data (ACID) dan unique constraint.

## 3. Concept
Dalam jaringan terdistribusi, komunikasi jaringan tidak pernah 100% andal (*Networks are unreliable*). Saat Consumer memproses pesan dan mengirim `ACK` ke broker, paket ACK tersebut bisa hilang di tengah jalan akibat packet drop atau koneksi putus. Broker berasumsi Consumer mati, lalu mengirim ulang pesan yang sama ke Consumer lain.

Oleh karena itu, sistem perpesanan skala besar di dunia nyata **hampir selalu beroperasi pada mode *At-Least-Once Delivery***. Karena pesan dapat tiba lebih dari sekali, tanggung jawab untuk mencegah eksekusi ganda dialihkan ke Consumer melalui desain **Idempotent Consumer**. Jika suatu pesan gagal berulang kali karena data rusak (*poison pill*), pesan harus dialihkan ke **Dead Letter Queue (DLQ)** agar antrian utama tidak macet.

## 4. Why?
- **Mencegah Double Charge**: Bayangkan jika notifikasi pembayaran e-commerce dikirim 2 kali karena timeout ACK. Tanpa idempotency, saldo kartu kredit pelanggan akan dipotong dua kali!
- **Mencegah Antrian Macet (Queue Stalling)**: Jika sebuah pesan memiliki format JSON yang salah (*corrupted*), worker akan crash berulang kali (*infinite crash loop*). Seluruh antrian di belakangnya akan tertahan.

## 5. What?
### 3 Tingkatan Delivery Guarantees:
1. **At-Most-Once (Maksimal Satu Kali)**:
   - Pesan dikirim tanpa retry. Jika terjadi kegagalan jaringan atau crash, pesan hilang.
   - Keuntungan: Sangat cepat, nol duplikasi.
   - Kerugian: Terjadi *data loss*.
   - Use case: Metrik CPU/RAM per detik, clickstream telemetry yang toleran terhadap kehilangan data.

2. **At-Least-Once (Minimal Satu Kali)**:
   - Pesan di-retry terus sampai ACK diterima.
   - Keuntungan: Menjamin tidak ada pesan yang hilang (*zero data loss*).
   - Kerugian: **Pesan duplikat pasti akan terjadi**.
   - Use case: Transaksi keuangan, order processing, email notifications (dengan idempotent handler).

3. **Exactly-Once (Tepat Satu Kali)**:
   - Secara fisik mustahil dicapai murni di level jaringan fisik (Two Generals' Problem).
   - Namun, dapat dicapai secara efektif melalui kombinasi:
     $$\text{Exactly-Once} = \text{At-Least-Once Delivery} + \text{Idempotent Processing}$$
   - Apache Kafka menyediakan transaksi end-to-end Producer-to-Topic (`enable.idempotence=true` + transactional API).

### Dead Letter Queue (DLQ)
Antrian sekunder tempat menampung pesan yang gagal diproses setelah mencapai ambang batas retry maksimum (*max retry attempts*). Pesan di DLQ diisolasi untuk diinspeksi secara manual atau diperbaiki oleh tim engineer tanpa mengganggu traffic antrian utama.

## 6. How?
### Mekanisme Idempotency Key (Deduplication Pattern)
1. Producer menyertakan atribut `Idempotency-Key` (misal UUID acak: `evt_9a8b7c6d`) pada setiap pesan.
2. Saat Consumer menerima pesan, Consumer melakukan transaksi atomik:
   - Periksa ke cache / table deduplikasi: `SELECT status FROM processed_events WHERE idempotency_key = 'evt_9a8b7c6d'`.
   - Jika sudah ada: Abaikan proses bisnis, langsung kirim `ACK` ke broker (karena pesan ini adalah duplikat).
   - Jika belum ada: Jalankan proses bisnis, lalu simpan key ke database dalam satu transaksi ACID:
     `INSERT INTO processed_events (idempotency_key, processed_at) VALUES ('evt_9a8b7c6d', NOW())`.
   - Kirim `ACK` ke broker.

### Siklus Penanganan Kegagalan & DLQ
```text
[Main Queue] ──> [Consumer Worker] ──(Error / Exception)──> [Retry Queue w/ Backoff]
                        │                                          │ (Retry count > 3)
                        │ (Sukses)                                 ▼
                        ▼                                  [Dead Letter Queue (DLQ)]
                  [Processed / ACK]                                │
                                                                   ▼
                                                          [Alert Ops & Triage]
```

## 7. Analogy
- **At-Most-Once**: Melempar surat kabar dari mobil yang melaju. Jika jatuh ke selokan, koran hilang dan pelempar tidak peduli.
- **At-Least-Once**: Tukang kurir yang mengetuk pintu sampai pemilik rumah keluar. Jika pemilik rumah menerima barang tapi angin membuat pintu tertutup sebelum tanda tangan, kurir mengetuk lagi dan menyerahkan barang yang sama untuk kedua kalinya.
- **Idempotency**: Pemilik rumah memiliki daftar nomor resi di pintu. Saat kurir kedua datang membawa barang dengan nomor resi yang sama, pemilik berkata: *"Saya sudah terima barang ini 5 menit lalu, terima kasih!"* lalu menandatangani tanda terima tanpa mengambil barang dobel.
- **DLQ**: Kotak sampah karantina di kantor pos untuk paket dengan alamat palsu atau label robek yang tidak bisa diantar, agar tidak menghalangi pengantaran paket-paket lain.

## 8. Diagram

```text
PRODUCER                          BROKER                           CONSUMER
   │                                │                                 │
   ├── 1. Send Msg (Key: K1) ──────>│                                 │
   │                                ├── 2. Deliver Msg (Key: K1) ────>│
   │                                │                                 ├── 3. Cek DB: K1 sudah ada?
   │                                │                                 │      (Belum -> Simpan K1)
   │                                │                                 ├── 4. Potong Saldo Rp 50.000
   │                                │<── 5. Kirim ACK ────────────────┤
   │                                │    (Jaringan Putus / Dropped!)  │
   │                                x                                 │
   │                                │                                 │
   │                                ├── 6. Redeliver Msg (Key: K1) ──>│
   │                                │      (Broker mengira worker mati)│
   │                                │                                 ├── 7. Cek DB: K1 sudah ada?
   │                                │                                 │      (SUDAH ADA! Duplicate!)
   │                                │                                 ├── 8. Skip Potong Saldo!
   │                                │<── 9. Kirim Ulang ACK ──────────┤
   │                                │    (Ack Diterima -> Selesai)    │
```

## 9. Simple Example
Operasi yang secara alami Idempoten vs Non-Idempoten:
- **Non-Idempoten**: `UPDATE accounts SET balance = balance - 50000 WHERE user_id = 1;` (Jika dijalankan 3x, saldo berkurang 150.000!).
- **Idempoten Secara Alami**: `UPDATE accounts SET balance = 100000 WHERE user_id = 1;` (Dijalankan 1x atau 10x, saldo tetap 100.000).
- **Idempoten Menggunakan Ledger Transaksi**:
  `INSERT INTO wallet_transactions (idempotency_key, user_id, amount) VALUES ('trx_01', 1, -50000);`  
  Kolom `idempotency_key` memiliki indeks `UNIQUE`. Eksekusi kedua akan melempar `DuplicateKeyException` dan langsung diabaikan dengan aman!

## 10. Practical Example: Stripe Payment Webhooks
Stripe API menyertakan header `Stripe-Signature` dan field `id` unik pada setiap webhook (misal: `evt_1MvXYZ2eZvKYlo2C01234567`). Stripe menjamin *At-Least-Once Delivery* dan akan me-retry pengiriman webhook hingga 3 hari jika server Anda merespons status selain 2xx. Setiap backend engineer wajib menyimpan `evt_id` di database untuk mencegah aktivasi langganan akun berulang kali.

## 11. Real World Example
- **PayPal & VISA**: Menggunakan strict transactional idempotency key pada setiap HTTP payment authorization API untuk mencegah duplikasi pembayaran saat aplikasi kasir mengalami timeout.
- **AWS SQS & SNS**: Menyediakan fitur FIFO Queue dengan *Content-Based Deduplication* (hash SHA-256 dari payload pesan dalam rolling interval 5 menit).

## 12. Trade-offs

| Pendekatan | Kelebihan | Kekurangan | Kompleksitas |
|---|---|---|---|
| **At-Most-Once** | Latensi terendah, resource broker minimal | Resiko kehilangan data (*data loss*) | Rendah |
| **At-Least-Once (Naif)** | Menjamin data tidak hilang | Data korup/duplikat jika consumer tidak idempoten | Sedang |
| **At-Least-Once + Idempotency** | Konsistensi data mutlak (*Zero Loss, Zero Duplicate Impact*) | Overhead storage untuk deduplication store (Redis/DB) | Menengah - Tinggi |
| **Pure 2-Phase Commit (2PC)** | Konsistensi ACID terdistribusi lintas sistem | Latensi sangat tinggi, rentan blocking (*single point of bottleneck*) | Sangat Tinggi |

## 13. When To Use Idempotency & DLQ
- Setiap sistem yang memproses transaksi finansial, inventori gudang, atau mutasi state penting.
- Setiap consumer message broker di mana kegagalan sementara (*transient error*) seperti database timeout dapat terjadi.
- Integrasi pihak ketiga (*Third-party API Webhooks*).

## 14. When NOT To Use DLQ
- Metrik real-time sensor IoT berfrekuensi tinggi (misal: suhu mesin setiap 100 milidetik). Jika 1 data rusak, buang saja (*drop*), karena data 100ms berikutnya akan segera tiba.

## 15. Common Mistakes
1. **Mengabaikan ACK saat terjadi error**: Membiarkan pesan tidak di-ACK tanpa mekanisme retry/DLQ menyebabkan antrian broker membengkak tak terbatas.
2. **Immediate Retry Loop (Thundering Herd)**: Jika database downstream sedang down, me-retry pesan seketika itu juga tanpa backoff (*exponential backoff + jitter*) akan membunuh database yang sedang berusaha pulih.
3. **Idempotency Store tanpa TTL**: Menyimpan ID transaksi selamanya di Redis tanpa masa kedaluwarsa (*expiry/TTL*) akan menghabiskan memori RAM. Cukup simpan idempotency key selama rentang retensi retry broker (misal 24 jam - 7 hari).

## 16. Best Practices
- **Exponential Backoff dengan Jitter**: Waktu tunggu retry pertama 1 detik, kedua 2 detik, ketiga 4 detik, plus random noise (jitter) 100-500ms.
- **Batasi Maksimum Retry (Max Retry Count)**: Misal maksimal 3 atau 5 kali. Jika tetap gagal, pindahkan ke DLQ.
- **DLQ Monitoring & Alerting**: Buat alerting Prometheus jika antrian DLQ berisi lebih dari 0 pesan, karena ini menandakan bug kode atau anomali data di production!

## 17. Troubleshooting
- **Masalah: Worker crash berulang kali saat memproses pesan tertentu**.
  - *Diagnosa*: Pesan adalah *Poison Pill* (misal payload JSON memiliki syntax error atau field bernilai `null` tak terduga).
  - *Solusi*: Pasang blok `try-catch` di tingkat tertinggi consumer. Jika terjadi unrecoverable validation error, jangan di-retry, langsung lempar ke DLQ dan kirim ACK ke antrian utama.

## 18. Hands-on Practice
Mari kita jalankan simulasi komprehensif penanganan duplikasi pesan (Idempotency Key) dan penanganan poison pill (Retry + Dead Letter Queue) di `hands-on/m02/idempotency_dlq_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Rancang skema tabel SQL untuk `idempotency_records` yang mampu menangani status *IN_PROGRESS*, *SUCCESS*, dan *FAILED* untuk mencegah race condition dua worker yang memproses pesan duplikat di milidetik yang sama.
- **Challenge**: Buat arsitektur reprocessing DLQ otomatis di mana setelah bug kode diperbaiki dan di-deploy, pesan dari DLQ dapat dipompa kembali (*re-drive*) ke antrian utama secara aman.

## 20. Summary
Tidak ada sistem jaringan terdistribusi yang dapat menjamin pengiriman tepat satu kali secara fisik. Fondasi sistem terdistribusi yang kokoh dibangun atas prinsip **At-Least-Once Delivery yang dipadukan dengan Idempotent Consumer**. Untuk kegagalan permanen, **Dead Letter Queue (DLQ)** memastikan isolasi kegagalan sehingga sistem tetap berjalan stabil.
