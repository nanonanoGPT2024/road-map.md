# Module 01: Message Queues vs Event Streaming (RabbitMQ vs Apache Kafka)

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mengidentifikasi perbedaan arsitektur fundamental antara *Message Queue (Smart Broker, Dumb Consumer)* seperti RabbitMQ dan *Event Streaming / Distributed Append-Only Log (Dumb Broker, Smart Consumer)* seperti Apache Kafka.
- Memahami konsep antrian point-to-point, routing keys, exchange types, partition offsets, consumer groups, dan retention policy.
- Memilih teknologi asinkron yang tepat berdasarkan pola akses data: task distribution vs high-throughput real-time stream processing.

## 2. Prerequisite
- Memahami dasar komunikasi asinkron vs sinkron (HTTP/REST).
- Konsep dasar concurrency, producer, consumer, dan worker pool.

## 3. Concept
Dalam sistem terdistribusi, komunikasi sinkron (misal: Service A memanggil Service B via HTTP dan menunggu response) menciptakan kopling ketat (*tight coupling*). Jika Service B lambat atau down, Service A akan ikut terhambat (*cascading failure*).

Sistem perpesanan asinkron memisahkan (*decouples*) pengirim (*Producer*) dan penerima (*Consumer*) secara temporal (waktu) dan spasial (lokasi). Ada dua paradigma utama:
1. **Message Queue (RabbitMQ / ActiveMQ / AWS SQS)**: Pesan dikirim ke broker, didistribusikan ke worker, dan **dihapus segera setelah dikonsumsi dan di-acknowledge**. Fokus pada *task execution* dan *complex routing*.
2. **Event Streaming / Distributed Commit Log (Apache Kafka / Apache Pulsar / AWS Kinesis)**: Pesan disimpan sebagai log terurut (*append-only log*) yang **persisten di disk** berdasarkan retensi waktu (misal: 7 hari). Konsumen melacak posisinya sendiri (*offset*). Banyak kelompok konsumen independen dapat membaca ulang (*replay*) data yang sama tanpa menghapus pesan.

## 4. Why?
Tanpa message broker:
- **Tightly Coupled**: Producer harus mengetahui alamat IP dan status kesehatan Consumer.
- **Traffic Spikes Crash Backend**: Flash sale dengan 10.000 pesanan/detik akan langsung menenggelamkan Database dan Payment Service jika dikirim secara sinkron.
- **No Data Replay**: Jika bug terjadi pada consumer saat memproses data transaksi kemarin, data hilang atau sulit diproses ulang jika tidak disimpan terpisah.

## 5. What?
- **Broker (RabbitMQ)**: Bertindak sebagai perantara cerdas (*Smart Broker*). Memiliki *Exchanges* (Direct, Fanout, Topic, Headers) yang merutekan pesan ke antrian (*Queues*) berdasarkan *Routing Key*. Begitu konsumen mengirim pesan `ack`, pesan dihapus dari queue.
- **Distributed Log (Kafka)**: Broker bertindak sebagai tempat penyimpanan log sekuensial (*Dumb Broker*). Topik dibagi menjadi beberapa *Partisi* (*Partitions*). Setiap partisi adalah berkas terurut yang tidak dapat diubah (*immutable append-only*). Konsumen melacak progres mereka sendiri melalui penanda indeks yang disebut `Offset`.

## 6. How?
### Arsitektur RabbitMQ (AMQP Model)
1. Producer mengirim pesan ke **Exchange**.
2. Exchange mengevaluasi binding dan routing key untuk menyalurkan pesan ke **Queue** yang cocok.
3. Consumer berlangganan ke Queue. Worker menarik (*pull*) atau menerima (*push*) pesan.
4. Setelah diproses, worker mengirim `ack`. Broker menghapus pesan dari antrian.

### Arsitektur Apache Kafka
1. Producer mem-publish pesan ke **Topic**.
2. Pesan di-route ke **Partition** tertentu berdasarkan hash dari `Partition Key` (atau round-robin jika key null).
3. Pesan ditulis ke disk secara sekuensial (O(1) sequential I/O write) dan diberi nomor urut unik (`Offset`).
4. **Consumer Group** membaca partisi. Satu partisi hanya dikonsumsi oleh satu consumer instance di dalam group yang sama, menjamin keterurutan data (*ordering guarantee*) per partisi.
5. Konsumen menyimpan offset terakhir yang berhasil dibaca.

## 7. Analogy
- **RabbitMQ = Kantor Pos / Delivery Service**: Kurir mengantarkan paket ke kotak surat Anda. Begitu Anda mengambil paket dan menandatangani bukti terima (*ack*), kurir mencatat tugas selesai dan paket tidak ada lagi di gudang kantor pos.
- **Kafka = Papan Pengumuman / Koran Berseri / Buku Besar Abadi**: Berita ditulis di papan pengumuman umum dan tetap terpampang selama 7 hari. Siapa saja (Departemen Keuangan, Departemen Pemasaran, Departemen Audit) dapat datang membaca dari berita nomor 1 sampai berita nomor 100 kapan saja sesuai kecepatan masing-masing, membaca ulang (*replay*), tanpa menghapus tulisan di papan.

## 8. Diagram

```text
================ RABBITMQ: MESSAGE QUEUE (SMART BROKER) ================
 [Producer] ──> [Exchange] ─(Routing Key)─> [Queue] ──> [Worker 1] (ack -> Hapus)
                                                    └──> [Worker 2]

================ APACHE KAFKA: DISTRIBUTED LOG (DUMB BROKER) ============
                                ┌── Partition 0: [0][1][2][3][4][5] ──> Consumer A (Offset: 5)
 [Producer] ──> [Topic: Orders] ├── Partition 1: [0][1][2][3]       ──> Consumer B (Offset: 3)
                                └── Partition 2: [0][1][2][3][4]    ──> Consumer C (Offset: 4)
                                (Log disimpan di disk, Consumer Group B bisa replay dari Offset 0)
```

## 9. Simple Example
Perbandingan deklarasi konseptual:
- **RabbitMQ**: "Kirimkan tugas `generate_pdf` untuk invoice #123 ke antrian `pdf_queue`. Satu worker ambil, selesaikan, lalu hapus."
- **Kafka**: "Kirimkan event `InvoiceCreated { id: 123, amount: 50000 }` ke topik `invoices`. Payment Service baca, Email Service baca, Data Analytics Warehouse baca, semuanya membaca event yang persis sama."

## 10. Practical Example: Event Replay
Di Apache Kafka, jika tim Fraud Detection merilis algoritma machine learning baru hari ini, mereka tidak perlu menunggu data baru terkumpul. Mereka cukup membuat consumer group baru:
`group.id = fraud-detector-v2` dan mengatur `auto.offset.reset = earliest`. Kafka akan mem-play ulang seluruh transaksi 30 hari terakhir dari Offset 0 dengan kecepatan kilat! Pada RabbitMQ, hal ini mustahil kecuali sistem menyimpan duplikat manual di database luar.

## 11. Real World Example
- **Uber**: Menggunakan Apache Kafka untuk memproses triliunan event lokasi GPS pengemudi per hari. Stream data ini dikonsumsi serempak oleh sistem peta real-time, sistem penghitung tarif dinamis (*surge pricing*), dan sistem deteksi kecelakaan secara independen.
- **Tokopedia / Shopee**: Menggunakan RabbitMQ untuk background processing notifikasi push, SMS OTP, dan antrian pembuatan label resi pengiriman kurir.

## 12. Trade-offs

| Parameter | RabbitMQ | Apache Kafka |
|---|---|---|
| **Paradigma** | Smart Broker / Dumb Consumer | Dumb Broker / Smart Consumer |
| **Model Distribusi** | Queue (Pesan dihapus setelah dibaca) | Append-Only Log (Pesan disimpan sesuai retensi) |
| **Throughput** | ~20.000 - 50.000 pesan/detik | > 1.000.000 pesan/detik (Sequential Disk I/O) |
| **Routing Kapabilitas**| Sangat fleksibel (Topic, Fanout, Direct, Headers) | Sederhana (Hanya berdasarkan Topic & Partition Key) |
| **Ordering Guarantee**| FIFO per queue, tapi rusak jika worker konkruen n-ack | Strict Total Order **per partisi** |
| **Replay Message** | Tidak didukung (harus backup eksternal) | Didukung penuh (geser Offset ke masa lalu) |
| **Backpressure** | Broker memory bisa membengkak jika unacked queue membesar | Sangat aman (Consumer pull sesuai kemampuannya) |

## 13. When To Use RabbitMQ
- Butuh sistem perpesanan dengan pola routing kompleks (misal: rute pesan berdasarkan regex routing key).
- Antrian tugas background pekerjaan (*Worker Pool / Job Queue*) seperti export file Excel, resizing foto, pengiriman email.
- Prioritas pesan (*Priority Queues*) didukung secara native.
- Skala sistem berada di kisaran puluhan ribu pesan/detik.

## 14. When To Use Apache Kafka
- High-throughput ingestion (ratusan ribu hingga jutaan event per detik, misal log server, IoT metrics, clickstream).
- Event Sourcing & Event-Driven Architecture di mana multiple downstream services membutuhkan salinan event yang sama.
- Data Analytics pipeline (mengalirkan data ke Snowflake, BigQuery, Elasticsearch).
- Kebutuhan untuk me-replay data lama saat microservice baru ditambahkan atau saat terjadi insiden pemulihan bug.

## 15. Common Mistakes
1. **Menggunakan Kafka sebagai Task Queue dengan status dinamis**: Kafka tidak dirancang untuk meng-update status pesan individu (misal mengubah pesan #45 dari 'pending' ke 'completed'). Partisi Kafka bersifat immutable!
2. **RabbitMQ Memory OOM karena antrian menumpuk**: Jika worker mati dan jutaan pesan menumpuk di memory RabbitMQ, broker akan melakukan page to disk dan performa terjun bebas.
3. **Jumlah Partisi Kafka terlalu sedikit**: Skalabilitas consumer group Kafka dibatasi oleh jumlah partisi. Jika sebuah topik hanya memiliki 3 partisi, maka menambahkan 10 consumer instance tidak akan menaikkan throughput karena 7 consumer akan menganggur!

## 16. Best Practices
- **RabbitMQ**: Selalu definisikan `x-max-length` atau `TTL` pada queue, gunakan `prefetch_count` (misal 10-50) agar broker tidak membanjiri satu worker yang sedang sibuk.
- **Kafka**: Tentukan Partition Key dengan hati-hati untuk mencegah data skew (hot partition). Tentukan jumlah partisi di awal berdasarkan estimasi target throughput konsumen maksimum.

## 17. Troubleshooting
- **Masalah: Consumer Kafka lambat dan terjadi Rebalance terus-menerus (*Rebalance Storm*)**.
  - *Sebab*: Pemrosesan pesan di consumer melebihi `max.poll.interval.ms`, sehingga Kafka mengira consumer sudah mati dan memicu repartitioning.
  - *Solusi*: Naikkan timeout interval atau perkecil `max.poll.records`, atau oper pemrosesan komputasi berat ke worker pool internal sebelum commit offset.

## 18. Hands-on Practice
Mari kita buktikan secara empiris perbedaan arsitektur Queue (pesan dihapus saat di-ack) vs Event Log (pesan persisten dan offset dapat di-replay) melalui simulasi Node.js murni di direktori `hands-on/m01/queue_vs_stream.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung berapa jumlah partisi Kafka yang dibutuhkan jika producer menghasilkan traffic 60 MB/detik dan setiap consumer instance hanya mampu memproses 10 MB/detik. (Jawaban: Minimal 6 partisi).
- **Challenge**: Rancang arsitektur data pipeline untuk e-commerce saat event `CheckoutCompleted` terjadi: Inventory, Shipping, Billing, dan Rekomendasi ML harus menerima event tersebut. Pilih antara RabbitMQ Fanout vs Kafka Topic dan diskusikan trade-off-nya.

## 20. Summary
RabbitMQ unggul untuk pemrosesan tugas berbasis antrian individual dengan routing yang canggih (*transient task queue*). Sebaliknya, Apache Kafka adalah fondasi *real-time event streaming* berbasis immutable log terdistribusi yang memberikan ketahanan, skalabilitas ekstrem, dan kapabilitas *replayability*.
