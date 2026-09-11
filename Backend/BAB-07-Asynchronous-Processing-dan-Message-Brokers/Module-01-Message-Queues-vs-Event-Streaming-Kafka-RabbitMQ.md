---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Strategi-Caching-dan-In-Memory-Stores/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Idempotent Consumer & Outbox Pattern ➡️](./Module-02-Idempotent-Consumers-DLQ-dan-Transactional-Outbox.md)
---

# Module 01: Message Queues vs Event Streaming (RabbitMQ vs Apache Kafka)

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Membedakan paradigma pemrosesan asinkron: **Message Queuing (Smart Broker / Dumb Consumer)** vs **Event Streaming (Dumb Broker / Smart Consumer)**.
- Menguasai arsitektur **RabbitMQ (AMQP 0-9-1)**: Exchange types (Direct, Fanout, Topic, Headers), Bindings, dan Queues.
- Menguasai arsitektur **Apache Kafka**: Distributed Commit Log, Partisi (*Partitions*), Replikasi (*ISR - In-Sync Replicas*), dan *Consumer Groups*.
- Memahami strategi penentuan kunci partisi (*Partition Key*) dan jaminan keterurutan pesan (*Message Ordering Guarantee*).
- Menangani fenomena penumpukan beban (*Backpressure*) dan mekanisme *Prefetch Count* pada consumer backend.

---

## 2. Prerequisite
- Memahami arsitektur komunikasi sinkron HTTP/REST dan gRPC (BAB 03).
- Konsep dasar konkurensi, thread pools, dan asynchronous event loop (BAB 02).
- Pemahaman operasi storage disk sekuensial vs random I/O (BAB 04).

---

## 3. Concept
Dalam arsitektur backend tradisional berbasis sinkron (HTTP/REST), service pemanggil (*Caller*) harus memblokir thread eksekusinya sampai service penerima (*Callee*) selesai memproses pekerjaan dan mengirim respon.

Jika service tujuan lambat, sedang restart, atau mengalami lonjakan beban, seluruh sistem pemanggil akan kehabisan thread dan tumbang bersama (*Cascading Failure*).

Pemrosesan asinkron melalui **Message Broker** memutus kopling temporal (*Temporal Decoupling*) antara pengirim dan penerima data:
- Pengirim (**Producer**) cukup meletakkan pesan ke dalam perantara (*Broker*) dalam waktu 1-2 ms lalu langsung melanjutkan pekerjaannya.
- Penerima (**Consumer**) mengambil dan memproses pesan dari broker sesuai dengan kapasitas komputasinya sendiri (*Pull-based* atau *Controlled Push*).

---

## 4. Why?
Tanpa Message Broker:
1. **Tight Coupling:** Jika service email atau payment gateway pihak ketiga down selama 10 menit, alur registrasi atau checkout pengguna di website Anda akan gagal total.
2. **Tidak Ada Buffer Lonjakan Trafik (*Load Leveling*):** Jika sistem Anda diserbu 100.000 order dalam 5 menit, worker database langsung crash karena tidak ada antrean penyangga yang meratakan debit pekerjaan.
3. **Kehilangan Data Saat Service Crash:** Request HTTP yang sedang berada di tengah pemrosesan dalam memori pod akan musnah seketika jika container pod di-kill oleh Kubernetes OOM.
4. **Kesulitan Broadcast Multi-Sistem:** Jika aksi "User Checkout" harus memicu 6 aksi lanjutan (kirim invoice email, potong stok gudang, update point loyalty, notifikasi mobile, analytics data warehouse, dan audit log), memanggil 6 API HTTP sekuensial akan membuat response time checkout melonjak hingga 5 detik!

---

## 5. What? (Komparasi RabbitMQ vs Apache Kafka)

Dua raksasa teknologi asinkron ini memiliki filosofi desain arsitektur yang bertolak belakang:

| Aspek Arsitektur | RabbitMQ (Message Queue) | Apache Kafka (Event Streaming) |
|---|---|---|
| **Model Paradigma** | Smart Broker, Dumb Consumer | Dumb Broker, Smart Consumer |
| **Penyimpanan Data** | Pesan **dihapus** dari queue segera setelah di-acknowledge oleh consumer | Pesan **disimpan permanen** dalam append-only commit log di disk (berdasarkan waktu retensi / ukuran) |
| **Model Konsumsi** | Broker mendorong (*Push*) pesan ke consumer | Consumer menarik (*Pull*) pesan berdasarkan *Offset* |
| **Replayability (Putar Ulang)**| Tidak bisa. Pesan yang sudah dikonsumsi hilang selamanya | **Sangat Bisa**. Consumer dapat memundurkan offset ke masa lalu untuk memproses ulang data |
| **Routing Fleksibilitas** | Sangat Kaya (Topic wildcard, Headers, Fanout) | Terbatas (Pesan dialirkan langsung ke Topic dan Partisi) |
| **Throughput Skala** | ~20.000 - 50.000 pesan / detik / node | **Jutaan** pesan / detik / cluster berkat *Zero-Copy Disk I/O* (`sendfile`) |
| **Jaminan Keterurutan** | Per-queue (namun bisa rusak jika ada multi-worker konkuren atau pesan di-NACK/requeue) | **Terjamin secara absolut** di dalam partisi yang sama |

---

## 6. How? (Mekanisme Kerja Internal)

### A. RabbitMQ Exchange Routing Flow
```
[ Producer ] ──Pesan + Routing Key ("order.created")──▶ [ Exchange (Topic) ]
                                                            │         │
                   ┌────────────────────────────────────────┘         └─────────────────────────┐
                   │ Binding: "order.*"                                                         │ Binding: "*.created"
                   ▼                                                                            ▼
          [ Queue: OrderService ]                                                      [ Queue: NotificationService ]
                   │                                                                            │
                   ▼                                                                            ▼
          [ Worker Consumer 1 ]                                                        [ Worker Consumer 2 ]
```
1. Producer tidak pernah mengirim pesan langsung ke Queue. Producer mengirim ke **Exchange**.
2. Exchange memeriksa **Routing Key** dan aturan **Binding** untuk menduplikasi pesan ke queue yang berhak.
3. Consumer menerima pesan. Jika selesai, consumer mengirimkan **ACK** (*Acknowledgment*). Broker kemudian menghapus pesan tersebut dari RAM/disk.

### B. Apache Kafka Distributed Partitioned Log Flow
```
Topic: "user-clicks" (3 Partisi Terdistribusi)
┌────────────────────────────────────────────────────────┐
│ Partition 0: [msg 0][msg 1][msg 2][msg 3] ◄── Consumer A (Group 1, Offset: 3)
├────────────────────────────────────────────────────────┤
│ Partition 1: [msg 0][msg 1][msg 2]       ◄── Consumer B (Group 1, Offset: 2)
├────────────────────────────────────────────────────────┤
│ Partition 2: [msg 0][msg 1][msg 2][msg 3] ◄── Consumer C (Group 1, Offset: 1)
└────────────────────────────────────────────────────────┘
```
1. Topic dibagi menjadi beberapa **Partisi** yang tersebar di node-node broker (*Storage Sharding*).
2. Setiap pesan baru ditempelkan di ujung akhir partisi (**Append-Only**) dengan nomor urut yang disebut **Offset**.
3. **Consumer Group:** Jika sebuah Consumer Group memiliki 3 worker dan topic memiliki 3 partisi, setiap worker mendapatkan tepat 1 partisi secara eksklusif.
4. **Jaminan Keterurutan:** Semua pesan dengan **Partition Key** yang sama (misal: `user_id: 8841`) dijamin masuk ke partisi yang persis sama, menjamin urutan event pengguna tersebut diproses secara sekuensial!

---

## 7. Analogy
- **RabbitMQ ibarat Kantor Pos Konvensional:** Petugas pos menerima surat, menyortirnya ke kotak pos penerima. Segera setelah penerima mengambil surat dari kotak pos dan menandatangani tanda terima, kantor pos menghancurkan catatan fisik surat tersebut. Surat tidak bisa diminta lagi.
- **Apache Kafka ibarat Buku Besar Transaksi (Ledger / Cassette Tape):** Setiap peristiwa direkam permanen pada gulungan pita rekaman sekuensial. Setiap pendengar memegang bookmark (*Offset*) masing-masing. Pendengar A bisa membaca halaman 100, sementara Pendengar B memundurkan kaset ke menit pertama untuk mendengarkan ulang lagu dari awal tanpa memengaruhi pendengar lainnya.

---

## 8. Diagram: Apache Kafka Zero-Copy Network Transfer

Mengapa Kafka mampu memproses jutaan pesan per detik dari disk?

```
PENDEKATAN TRADISIONAL (4 Context Switches + 4 Memory Copies):
[Disk] ──1. Read──▶ [Kernel OS PageCache] ──2. Copy──▶ [App JVM Memory]
                                                              │
[NIC Buffer Network] ◄──4. Copy── [Kernel Socket Buffer] ◄──3. Write──┘

KAFKA ZERO-COPY MENGGUNAKAN 'sendfile()' SYSTEM CALL (2 Context Switches, 0 CPU Copy):
[Disk File] ──1. DMA Read──▶ [Kernel OS PageCache] ──2. DMA Transfer (NIC)──▶ [Network]
```
Kafka tidak memuat payload pesan ke memori aplikasi JVM pengguna! Kafka memanfaatkan kernel Linux untuk menyalurkan data langsung dari PageCache disk ke antarmuka kartu jaringan (*Network Interface Card* / NIC) secara murni di level hardware (**Zero-Copy**).

---

## 9. Simple Example: RabbitMQ Producer & Consumer (Node.js amqplib pattern)

```javascript
// Producer: Mengirim pesan ke antrean task
async function sendTask(channel, queueName, taskPayload) {
  await channel.assertQueue(queueName, { durable: true }); // Queue bertahan walau broker restart
  const message = Buffer.from(JSON.stringify(taskPayload));
  channel.sendToQueue(queueName, message, { persistent: true }); // Pesan disimpan ke disk
  console.log(`[x] Sent: ${taskPayload.taskId}`);
}

// Consumer: Mengambil pesan dengan manual acknowledgment
async function consumeTasks(channel, queueName) {
  await channel.assertQueue(queueName, { durable: true });
  channel.prefetch(1); // Backpressure: hanya ambil 1 pesan dalam satu waktu per worker

  channel.consume(queueName, async (msg) => {
    if (msg !== null) {
      const task = JSON.parse(msg.content.toString());
      console.log(`[v] Processing: ${task.taskId}`);
      
      try {
        await processTaskLogic(task);
        channel.ack(msg); // Sukses: Hapus pesan dari antrean
      } catch (err) {
        console.error(`[!] Error: ${err.message}`);
        channel.nack(msg, false, true); // Gagal: Masukkan kembali ke antrean (requeue)
      }
    }
  });
}
```

---

## 10. Practical Example: Kafka Partition Key Strategy untuk Menjaga Urutan

```javascript
// Mengirim event dengan Partition Key konsisten
async function publishOrderEvent(kafkaProducer, orderId, customerId, eventType, payload) {
  await kafkaProducer.send({
    topic: 'order-lifecycle-events',
    messages: [
      {
        // PENTING: Menggunakan orderId sebagai Partition Key!
        // Menjamin event: ORDER_CREATED, PAYMENT_SUCCESS, ORDER_SHIPPED
        // untuk orderId yang sama SELALU masuk ke partisi yang persis sama.
        key: String(orderId),
        value: JSON.stringify({
          eventType,
          customerId,
          payload,
          timestamp: Date.now()
        }),
        headers: {
          'correlation-id': crypto.randomUUID(),
          'source-service': 'checkout-api'
        }
      }
    ]
  });
}
```

---

## 11. Real World Example: Arsitektur Pemrosesan Order Ridesharing (Gojek / Grab)

Ketika seorang penumpang menekan tombol "Pesan Ojek Online":
1. **API Gateway** mengirim pesan ke Kafka Topic `ride-booking-requests` dengan partition key `geohash-jakarta-selatan`.
2. **Matching Engine Consumer:** 10 worker consumer membaca partisi area geografis masing-masing, menghitung driver terdekat dalam radius 2 km, dan mengirim tawaran order ke aplikasi mobile driver via WebSocket.
3. **Audit & Analytics Consumer:** Di saat yang sama, Consumer Group data warehouse membaca stream yang sama persis untuk melacak titik hotspot pesanan dan mengkalkulasi algoritma *Surge Pricing* secara real-time menggunakan Apache Flink.
4. Karena Kafka menyimpan event selama 7 hari, jika tim Data Science merilis algoritma matching baru, mereka dapat memutar ulang (*replay*) seluruh 10 juta order minggu lalu untuk menguji akurasi model AI mereka terhadap data riil tanpa mengganggu server produksi!

---

## 12. Trade-offs

| Aspek Pertimbangan | RabbitMQ | Apache Kafka |
|---|---|---|
| **Kompleksitas Operasional** | Menengah (Erlang runtime, clustering relatif mudah) | Tinggi (Butuh Apache ZooKeeper atau KRaft metadata quorum) |
| **Karakteristik Workload** | Kompleks routing, tugas individual, background jobs | Aliran data masif berkelanjutan (*Big Data Streaming, Metrics, Log Aggregation*) |
| **Skalabilitas Konsumsi** | Mudah menambah worker pada queue yang sama | Dibatasi oleh **Jumlah Partisi**! (Jika ada 5 partisi, maksimal hanya 5 worker aktif dalam 1 consumer group) |
| **Konsumsi Memori Broker** | Membengkak jika antrean menumpuk jutaan pesan yang belum di-ACK | Sangat stabil dan konstan karena data disimpan langsung di filesystem OS |

---

## 13. When To Use

### Gunakan RabbitMQ Jika:
- Anda membutuhkan antrean tugas latar belakang (*Background Job Queue*) dengan routing kompleks (misal: kirim ke departemen keuangan jika header `currency=USD`).
- Beban kerja berupa instruksi kerja spesifik yang harus dituntaskan oleh satu worker independen (*Worker Queue*).
- Anda membutuhkan fitur prioritas pesan (*Priority Queues*).

### Gunakan Apache Kafka Jika:
- Throughput data sangat masif (ratusan ribu hingga jutaan event per detik).
- Sistem Anda membutuhkan arsitektur **Event Sourcing** di mana riwayat status sistem direkonstruksi dari rangkaian event di masa lalu.
- Beberapa departemen atau microservices yang berbeda perlu membaca dan memproses aliran data mentah yang sama secara independen (*Pub/Sub Fanout* skala besar).
- Anda membutuhkan jaminan keterurutan data mutlak per entitas pengguna/akun.

---

## 14. When NOT To Use
- **Untuk Komunikasi Sinkron Permintaan-Tanggapan (Request-Response UI):** Menghubungkan form login pengguna dengan backend autentikasi via message queue hanya akan menambah latensi dan kompleksitas yang tidak perlu. Gunakan HTTP/gRPC.
- **RabbitMQ untuk Data Warehouse / Long-term Storage:** Menyimpan antrean 500 juta pesan di RabbitMQ akan memicu memori broker kolaps (*High Watermark Alarm*) dan menghentikan seluruh producer.
- **Kafka untuk Sistem dengan Skala Kecil & Kebutuhan Antrean Sederhana:** Menjalankan cluster Kafka multi-broker lengkap dengan KRaft hanya untuk mengirim 100 email selamat datang per hari adalah contoh nyata *Overengineering*.

---

## 15. Common Mistakes
1. **Auto-Ack Enabled:** Mengaktifkan parameter `noAck: true` di RabbitMQ. Pesan langsung dihapus dari broker sebelum worker selesai memprosesnya. Jika worker mati saat komputasi, data musnah selamanya!
2. **Lupa Partition Key di Kafka:** Mengirim pesan tanpa key ke Kafka Topic. Kafka akan menggunakan *Round-Robin* partitioner, menyebabkan event `ORDER_CREATED` masuk ke Partisi 1 dan `ORDER_CANCELLED` masuk ke Partisi 2, sehingga worker memproses pembatalan sebelum pembuatan order!
3. **Mengabaikan Backpressure & Prefetch Count:** Membiarkan RabbitMQ mendorong (*push*) 50.000 pesan ke dalam memori RAM satu instance worker, membuat proses Node.js/JVM worker tersebut langsung crash kehabisan heap memori (*Out Of Memory*).
4. **Jumlah Partisi Lebih Sedikit dari Jumlah Worker:** Menjalankan 20 container worker dalam satu Consumer Group untuk Kafka Topic yang hanya memiliki 4 partisi. Sebanyak 16 worker akan menganggur (*idle*) selamanya!

---

## 16. Best Practices

### Must Have
- Selalu gunakan **Manual Acknowledgment (`ack`)** setelah seluruh transaksi (database/efek samping) berhasil dikomit.
- Konfigurasi **Prefetch Count** (biasanya bernilai 1 hingga 50 tergantung bobot pekerjaan) pada setiap consumer RabbitMQ.
- Gunakan pengidentifikasi unik entitas (seperti `user_id`, `device_id`, atau `account_id`) sebagai **Partition Key** di Kafka untuk menjamin urutan kronologis.

### Recommended
- Beri label metadata pesan (*Message Headers*) dengan `correlation_id` dan `timestamp` untuk memudahkan penelusuran terdistribusi (*Distributed Tracing* via OpenTelemetry).
- Rancang payload pesan agar sebisa mungkin bersifat *Self-Contained* (memuat data esensial yang dibutuhkan tanpa memaksa consumer melakukan query balik ke database producer).

### Advanced
- Konfigurasi Kafka Producer dengan jaminan durabilitas tinggi: `acks=all`, `min.insync.replicas=2`, dan aktifkan `enable.idempotence=true` untuk mencegah duplikasi pesan saat retry jaringan.

---

## 17. Troubleshooting

| Gejala Masalah | Indikasi Akar Masalah | Langkah Investigasi | Tindakan Perbaikan |
|---|---|---|---|
| **Consumer Lag Membengkak di Kafka** | Kecepatan pemrosesan worker lebih lambat dari laju data masuk producer | Cek metrik `kafka_consumergroup_lag` di Prometheus | Tingkatkan efisiensi kode worker, naikkan jumlah partisi & tambah worker di consumer group |
| **RabbitMQ Unacked Messages Menumpuk** | Worker tidak pernah memanggil `channel.ack()` (terjebak exception atau hang) | Periksa kolom `Unacked` pada RabbitMQ Web Management UI | Audit try-catch block worker, pastikan ada timeout dan panggil `nack` saat error |
| **Pesan Teracak Urutannya di Consumer** | Mengonsumsi Kafka topic dengan multi-thread tanpa pembagian per partisi | Periksa log timestamp pesan yang diproses worker | Pastikan satu partisi Kafka hanya dikonsumsi oleh satu thread worker sekuensial |

---

## 18. Exercise
1. Tulis simulator in-memory berbasis Node.js yang memodelkan Kafka Topic dengan 3 Partisi dan Consumer Group dengan 3 Worker.
2. Kirim 20 pesan dengan 4 variasi Partition Key (`user-1`, `user-2`, `user-3`, `user-4`).
3. Buktikan bahwa pesan untuk `user-1` selalu konsisten mendarat di partisi yang sama dan diproses secara sekuensial berurutan.

---

## 19. Challenge
Rancang arsitektur pipeline streaming data untuk mendeteksi transaksi penipuan (*Real-Time Credit Card Fraud Detection*):
- 10.000 transaksi kartu kredit per detik dialirkan ke Kafka Topic `card-transactions`.
- Deteksi transaksi anomali jika kartu yang sama digunakan di dua negara berbeda dalam kurun waktu kurang dari 15 menit (*Impossible Travel Velocity*).
- Bagaimana Anda menentukan Partition Key, ukuran jendela waktu (*Sliding Time Window*), dan state store in-memory untuk melakukan deteksi ini dalam latensi $< 50 \text{ ms}$?

---

## 20. Summary
Message Broker adalah urat nadi arsitektur backend modern yang memungkinkan skalabilitas tak terbatas melalui pelepasan kopling waktu (*Temporal Decoupling*). Baik memilih kelincahan routing pintar RabbitMQ maupun kedigdayaan append-only log Apache Kafka, seorang insinyur backend harus memahami implikasi keterurutan data, pembagian partisi, dan penanganan backpressure agar sistem tetap tangguh di bawah terjangan jutaan transaksi simultan.

---
[⬅️ BAB 06 Quiz & Challenge](../BAB-06-Strategi-Caching-dan-In-Memory-Stores/BAB-06-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Idempotent Consumer & Outbox Pattern ➡️](./Module-02-Idempotent-Consumers-DLQ-dan-Transactional-Outbox.md)
---
