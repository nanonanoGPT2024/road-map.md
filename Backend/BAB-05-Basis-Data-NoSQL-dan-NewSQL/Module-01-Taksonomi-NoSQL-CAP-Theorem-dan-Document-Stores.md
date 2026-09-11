---
[⬅️ BAB 04 Quiz & Challenge](../BAB-04-RDBMS-dan-SQL-Mastery/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Consistent Hashing & Vector DB ➡️](./Module-02-Consistent-Hashing-Sharding-dan-Vector-Databases.md)
---

# Module 01: Taksonomi NoSQL, Teorema CAP, & Document Stores

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi batasan teknis penskalaan horizontal basis data relasional (*RDBMS scaling limits*) yang memicu lahirnya gerakan **NoSQL**.
- Menguasai **Teorema CAP (Eric Brewer)**: *Consistency*, *Availability*, dan *Partition Tolerance*, serta memahami mengapa dalam jaringan terdistribusi, trade-off mutlak adalah antara **CP** vs **AP**.
- Menganalisis paradigma konsistensi **BASE** (*Basically Available, Soft state, Eventual consistency*) dibandingkan ACID.
- Menguasai 4 taksonomi utama NoSQL: **Key-Value**, **Document**, **Wide-Column**, dan **Graph Databases**.
- Merancang skema data pada **Document Store (MongoDB)**: teknik *Embedding (Denormalized)* vs *Referencing (Normalized)* berdasarkan pola akses baca/tulis aplikasi.

---

## 2. Prerequisite
- Memahami basis data relasional, tabel, dan transaksi ACID (Bab 04).
- Pemahaman struktur data pohon, graf, dan hash map.
- Konsep dasar jaringan terdistribusi (latency, packet loss, network split).

---

## 3. Concept
Selama empat dekade, RDBMS adalah satu-satunya jawaban untuk penyimpanan data. Namun, ledakan era internet global, aplikasi sosial raksasa, dan streaming data melahirkan tantangan yang tidak mampu dijawab oleh RDBMS monolitik:
1. **Volume & Kecepatan Tulis Raksasa (High Write Velocity)**: Jutaan data sensor IoT atau klik pengguna per detik membanjiri disk database.
2. **Skema Data Dinamis (Polymorphic Data)**: Produk e-commerce memiliki atribut yang sangat bervariasi (baju memiliki ukuran dan warna, laptop memiliki RAM dan GPU), yang sulit dipetakan ke dalam skema tabel relasional yang kaku.
3. **Penskalaan Horizontal (Horizontal Scale-out)**: Membagi RDBMS ke ratusan server murah (*sharding*) sangat rumit karena adanya operasi `JOIN` lintas-server dan transaksi terdistribusi (*Two-Phase Commit*).

Gerakan **NoSQL (Not Only SQL)** hadir bukan untuk memusnahkan RDBMS, melainkan melengkapinya dengan menyediakan arsitektur penyimpanan terspesialisasi yang mengorbankan fitur tertentu (seperti relasi tabel atau konsistensi instan) demi mendapatkan **skalabilitas horizontal tak terbatas dan performa tulis ekstrem**.

```
+-----------------------------------------------------------------------------------+
|                            THE CAP THEOREM TRIANGLE                               |
|                                                                                   |
|                                [ CONSISTENCY ]                                    |
|                         (Semua node melihat data identik                          |
|                          pada waktu yang sama)                                    |
|                                  /        \                                       |
|                                 /          \                                      |
|                                /   RDBMS    \                                     |
|                       [ CA ]  / (Postgres /  \                                    |
|                     (Non-Net) \    MySQL)    /                                    |
|                                \            /                                     |
|                                 \          /                                      |
|                                  \        /                                       |
|           [ CP SYSTEM ]           \      /           [ AP SYSTEM ]                |
|      (MongoDB, HBase, Redis)       \    /        (Cassandra, DynamoDB, CouchDB)   |
|     Tolak request jika partisi      \  /        Terima request, konsistensi       |
|     terputus demi data akurat!       \/         menyusul (Eventual Consistency)!  |
|                                      ||                                           |
|       [ PARTITION TOLERANCE ] =============== [ AVAILABILITY ]                    |
|    (Sistem tetap hidup meski kabel       (Setiap request non-failing node         |
|     jaringan antar server putus)          selalu mendapat respons sukses)         |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman Teorema CAP dan NoSQL sangat menentukan keberhasilan arsitektur backend?
1. **Mengeliminasi Ilusi Jaringan Sempurna**: Jaringan kabel serat optik antar datacenter pasti akan putus pada suatu waktu (*Network Partition*). Teorema CAP membuktikan secara matematis bahwa Anda **TIDAK BISA** memiliki sistem yang 100% konsisten sekaligus 100% selalu tersedia saat partisi terjadi.
2. **Kesesuaian Model Data (Polyglot Persistence)**: Menggunakan RDBMS untuk menyimpan jaringan pertemanan media sosial membutuhkan query 8-level `JOIN` yang melumpuhkan server. Menggunakan Graph Database menyelesaikan query yang sama dalam 2 milidetik via penelusuran pointer (*index-free adjacency*).
3. **Skalabilitas Biaya Murah**: Sistem NoSQL didesain untuk berjalan di atas ratusan server komoditas murah (cloud VM biasa) dengan toleransi kegagalan perangkat keras bawaan.

---

## 5. What?

### A. Teorema CAP & Teorema PACELC
- **Consistency (C)**: Setiap operasi pembacaan menerima data penulisan terbaru atau menghasilkan error.
- **Availability (A)**: Setiap request yang masuk ke node yang hidup selalu mendapatkan respons non-error (meskipun bukan data paling mutakhir).
- **Partition Tolerance (P)**: Sistem tetap beroperasi meskipun terjadi pemutusan komunikasi jaringan antar node.

> [!IMPORTANT]
> Karena di dunia nyata kabel jaringan antar server fisik bisa putus kapan saja, **Partition Tolerance ($P$) adalah mutlak**. Oleh karena itu, arsitektur sistem terdistribusi **HANYA DAPAT MEMILIH** antara:
> - **CP (Consistency + Partition Tolerance)**: Saat jaringan terputus, tolak request tulis/baca pada node minoritas agar data tidak menyimpang (Contoh: MongoDB, Google Cloud Spanner, etcd).
> - **AP (Availability + Partition Tolerance)**: Saat jaringan terputus, izinkan semua node tetap melayani tulis dan baca. Data yang berbeda akan disinkronisasikan di kemudian hari (**Eventual Consistency**) (Contoh: Apache Cassandra, AWS DynamoDB, CouchDB).

**Ekstensi PACELC**: Jika ada Partisi ($P$), pilih antara Availability ($A$) atau Consistency ($C$); **Else ($E$)**, saat jaringan normal, pilih antara Latency ($L$) atau Consistency ($C$).

### B. Empat Taksonomi Utama NoSQL

| Kategori | Representasi Data | Keunggulan Utama | Contoh Database | Use Case Ideal |
|---|---|---|---|---|
| **Key-Value** | Pasangan Kunci $\rightarrow$ Nilai biner | Kecepatan $O(1)$, sangat sederhana | Redis, Memcached, AWS DynamoDB | Caching, session management, shopping cart, leaderboard |
| **Document** | Dokumen semi-terstruktur (JSON/BSON) | Fleksibel, mendukung nested array & objek | MongoDB, Couchbase | E-commerce product catalog, CMS, profil pengguna |
| **Wide-Column** | Kolom fleksibel per baris, berbasis LSM-Tree | Throughput tulis jutaan ops/dtk, terdistribusi masif | Apache Cassandra, ScyllaDB, Google Bigtable | Sensor IoT telemetri, log event streaming, time-series |
| **Graph** | Node (Entitas) & Edges (Hubungan berarah) | Penelusuran relasi kompleks tanpa JOIN ($O(1)$) | Neo4j, Amazon Neptune | Deteksi penipuan finansial, social network graphs, recommendation engine |

### C. MongoDB: Embedding vs Referencing
Pada Document Store, bagaimana kita memodelkan relasi?

1. **Embedding (Denormalized)**: Menyimpan child data langsung di dalam satu dokumen induk.
   ```json
   {
     "_id": "usr_101",
     "name": "Budi Santoso",
     "addresses": [
       { "city": "Jakarta", "zip": "10110" },
       { "city": "Bandung", "zip": "40115" }
     ]
   }
   ```
   - **Kapan Digunakan**: Relasi 1:1 atau 1:N terbatas (*bounded*, misal alamat pengguna maksimal 5). Menghasilkan pembacaan super cepat dalam 1 query tunggal.
2. **Referencing (Normalized)**: Menyimpan ID dokumen lain (seperti Foreign Key).
   - **Kapan Digunakan**: Relasi 1:N tanpa batas (*unbounded*, misal 1 produk memiliki 500.000 ulasan) atau relasi N:M. Mencegah dokumen membengkak melampaui batas maksimal BSON MongoDB (16MB per dokumen).

---

## 6. How?

### Query MongoDB: Aggregation Pipeline

Alih-alih perintah SQL `JOIN` dan `GROUP BY`, MongoDB menggunakan konsep pemrosesan pipa bertingkat (**Aggregation Pipeline**):

```javascript
// Menghitung total pendapatan per kategori produk yang statusnya 'COMPLETED'
db.orders.aggregate([
  // Tahap 1: Filter dokumen (seperti WHERE di SQL)
  { $match: { status: "COMPLETED" } },

  // Tahap 2: Pecah array items menjadi dokumen individual
  { $unwind: "$items" },

  // Tahap 3: Kelompokkan dan jumlahkan (seperti GROUP BY & SUM di SQL)
  {
    $group: {
      _id: "$items.category",
      totalRevenue: { $sum: { $multiply: ["$items.price", "$items.quantity"] } },
      totalOrders: { $sum: 1 }
    }
  },

  // Tahap 4: Urutkan pendapatan tertinggi (seperti ORDER BY DESC)
  { $sort: { totalRevenue: -1 } },

  // Tahap 5: Ambil 5 teratas (seperti LIMIT 5)
  { $limit: 5 }
]);
```

---

## 7. Analogy
Bayangkan **Pengorganisasian Dokumen Kantor**:
- **RDBMS (Relasional)**: Lemari berkas dengan sekat-sekat laci kaku yang terkunci rapi. Data identitas di laci A, alamat di laci B, nomor telepon di laci C. Untuk membaca profil lengkap karyawan, sekretaris harus membuka 3 laci berbeda dan mencocokkan nomor induknya (**JOIN Overhead**).
- **Document Store (MongoDB)**: Setiap karyawan memiliki **Satu Map Folder Plastik Transparan**. Semua biodata, daftar ijazah, dan riwayat pekerjaan dimasukkan ke dalam map yang sama (**Embedding**). Saat bos meminta data Budi, sekretaris cukup mengambil 1 map tersebut dalam sekejap.
- **Teorema CAP**: Bayangkan dua cabang kantor bank di Jakarta dan Surabaya yang terhubung lewat telepon. Tiba-tiba kabel telepon terputus (**Network Partition**):
  - Jika nasabah ingin menarik uang di Surabaya, bank harus memilih:
    - **Pilih Konsistensi (CP)**: Tolak penarikan uang di Surabaya karena tidak bisa memverifikasi saldo terkini di server Jakarta. (Uang aman, tapi nasabah komplain bank tutup!).
    - **Pilih Ketersediaan (AP)**: Izinkan nasabah menarik uang di Surabaya berdasarkan catatan offline terakhir. Setelah telepon tersambung kembali, saldo di Jakarta disesuaikan belakangan (**Eventual Consistency**). Risiko: Jika nasabah juga menarik uang di Jakarta pada saat yang sama, saldo bisa jebol!

---

## 8. Diagram: Graph Database vs Relational JOIN

```
+---------------------------------------------------------------------------------+
|                       RELATIONAL JOIN VS GRAPH POINTER                          |
+---------------------------------------------------------------------------------+

1. RDBMS: Mencari "Teman dari Teman" (Friend-of-a-Friend):
   Table Users ---> Table Friends (Scan & Join) ---> Table Friends (Scan & Join)
   Kompleksitas: O(N^2) atau O(N^3) -> Melambat eksponensial seiring bertambahnya baris!

2. GRAPH DATABASE (Neo4j / Index-Free Adjacency):
   (Alice) ---[:FRIEND_OF]---> (Bob) ---[:FRIEND_OF]---> (Charlie)
   Kompleksitas: O(1) per langkah! Node memegang pointer memori fisik langsung ke tetangganya,
   melintasi jutaan relasi dalam hitungan milidetik tanpa tabel junction!
```

---

## 9. Simple Example: Node.js Mongoose Schema with Mixed Strategy

```javascript
const mongoose = require('mongoose');

// Schema E-Commerce Modern: Kombinasi Embedded dan Referenced
const OrderSchema = new mongoose.Schema({
  orderNumber: { type: String, required: true, unique: true },
  
  // Referenced: User ID (Koleksi users terpisah)
  customer: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },

  // Embedded: Snapshot Alamat Pengiriman pada saat transaksi
  // (Jika user pindah rumah di masa depan, alamat pada resi order lama tidak boleh berubah!)
  shippingAddress: {
    street: String,
    city: String,
    postalCode: String
  },

  // Embedded: Daftar Item Belanja (Bounded 1:N)
  items: [
    {
      productId: { type: mongoose.Schema.Types.ObjectId, ref: 'Product' },
      productName: String, // Denormalisasi nama produk untuk performa render cepat
      priceAtPurchase: Number,
      quantity: Number
    }
  ],

  totalAmount: Number,
  createdAt: { type: Date, default: Date.now }
});
```

---

## 10. Practical Example: Eventual Consistency Conflict Resolution (LWW vs CRDT)

Pada sistem AP (seperti Cassandra atau DynamoDB), jika dua node menerima update untuk data yang sama saat jaringan terputus, bagaimana konflik diselesaikan saat jaringan tersambung kembali?
1. **Last-Write-Wins (LWW)**: Menggunakan stempel waktu (*timestamp*) NTP. Update dengan timestamp tertinggi yang menang; update lain dibuang (Risiko: *Clock Drift* dapat menghapus data yang sah).
2. **Conflict-Free Replicated Data Types (CRDT)**: Struktur data matematis yang dirancang agar operasi penggabungan (*merge*) bersifat komutatif dan asosiatif ($A + B = B + A$).
   Contoh: Keranjang belanja e-commerce menggunakan **G-Counter / PN-Counter** sehingga barang yang dimasukkan oleh pengguna di mode offline otomatis tergabung tanpa ada yang hilang saat online kembali.

---

## 11. Real World Example: Migrasi Amazon dari RDBMS ke DynamoDB
Pada masa awal Amazon.com, keranjang belanja (*Shopping Cart*) disimpan di basis data relasional Oracle.
- Masalah: Pada event Black Friday, jutaan transaksi tulis membanjiri tabel keranjang belanja. RDBMS mengalami kemacetan penguncian baris (*lock contention*) dan kegagalan master database.
- Analisis Werner Vogels (CTO Amazon): Operasi keranjang belanja tidak membutuhkan relasi kompleks `JOIN` dan transaksi ACID multi-tabel; yang dibutuhkan hanyalah operasi sederhana: simpan data berdasarkan `customer_id` dan pastikan keranjang **selalu tersedia 100% tanpa pernah error (High Availability)**.
- Solusi: Amazon merancang **Dynamo** (cikal bakal DynamoDB), basis data NoSQL murni berparadigma AP yang mengutamakan *Eventual Consistency*. Hasilnya: Pengalaman checkout belanja Amazon tidak pernah tumbang meskipun jutaan pembeli bertransaksi serentak.

---

## 12. Trade-offs

| Paradigma | Keunggulan Utama | Risiko / Kerugian |
|---|---|---|
| **CP Database (MongoDB)** | Data selalu konsisten, tidak ada data kotor | Node menolak request jika terjadi partisi jaringan (Downtime sesaat) |
| **AP Database (Cassandra)** | Ketersediaan 100%, performa tulis masif tanpa henti | Pembacaan data sesaat bisa mengembalikan data lama (*stale data*) |
| **Document Embedding** | Query baca instan dalam 1 dokumen | Duplikasi data, dokumen membengkak jika data membesar |
| **Document Referencing** | Tidak ada duplikasi, ukuran dokumen ramping | Memerlukan multi-query atau `$lookup` (mirip JOIN) yang lebih lambat |

---

## 13. When To Use
- Gunakan **MongoDB (Document)** untuk platform konten, CMS, katalog produk e-commerce fleksibel, atau profil pengguna.
- Gunakan **Cassandra / ScyllaDB (Wide-Column)** untuk ingest data telemetri berkecepatan tinggi, time-series, metrik server, dan audit logging append-only.
- Gunakan **Neo4j (Graph)** untuk mesin rekomendasi sosial, grafik silsilah, analisis rute logistik, dan sistem pencegahan fraud pencucian uang.
- Gunakan **Redis (Key-Value)** untuk caching, penghitung rate limiting, dan manajemen session token.

---

## 14. When NOT To Use
- **JANGAN** menggunakan NoSQL untuk sistem akuntansi pembukuan ganda (*General Ledger*) yang mewajibkan transaksi multi-tabel atomik ketat tanpa kompromi (gunakan PostgreSQL).
- Jangan memaksakan struktur relasional kompleks di MongoDB dengan membuat puluhan relasi reference `$lookup`; jika data Anda sangat relasional, gunakan RDBMS sejak awal!

---

## 15. Common Mistakes
1. **Mengabaikan Batas 16MB BSON MongoDB**: Menyematkan array tak terbatas (*unbounded array*, seperti komentar artikel atau riwayat chat) di dalam satu dokumen. Ketika dokumen menyentuh 16MB, database melempar fatal error: `Document size limit exceeded`.
2. **Mengasumsikan Eventual Consistency Terjadi Instan**: Menulis data ke Cassandra di Node 1, lalu 1 milidetik kemudian membaca dari Node 2 dan mengira data sudah pasti ada. Replikasi antar datacenter membutuhkan waktu (misal 50-200ms).
3. **Mengabaikan Shard Key yang Tepat**: Memilih shard key dengan kardinalitas rendah (misal: kolom `country`), menyebabkan satu node server menampung 90% data (*Hotspot Shard*) sementara server lain menganggur.

---

## 16. Best Practices
- **Must Have**: Tetapkan aturan pemodelan: gunakan **Embedding** jika data selalu diakses bersamaan dan terikat pada siklus hidup entitas induk; gunakan **Referencing** jika data berdiri sendiri atau jumlahnya tak terbatas.
- **Recommended**: Buat index pada field yang sering menjadi kriteria filter di dalam dokumen MongoDB: `db.orders.createIndex({ "customer": 1, "createdAt": -1 })`.
- **Advanced**: Implementasikan **Change Streams** di MongoDB untuk mendeteksi perubahan data secara real-time dan meneruskannya ke event streaming pipeline (Kafka/RabbitMQ).
- **Avoid**: Menjalankan query tanpa index pada koleksi MongoDB berukuran jutaan dokumen (memicu *COLLSCAN* yang menguras memori).

---

## 17. Troubleshooting Guide
```
Masalah: Query MongoDB sangat lambat dan membebani RAM (WiredTiger Cache Eviction).
Penyebab : Terjadi Collection Scan (COLLSCAN) karena tidak ada index yang cocok dengan query filter.
Diagnosa : db.orders.find({ status: "PENDING" }).explain("executionStats");
           Periksa bagian: "stage": "COLLSCAN" dan "totalDocsExamined" yang sangat tinggi.
Solusi   : Buat index yang sesuai: db.orders.createIndex({ status: 1 });
           Pastikan "stage" berubah menjadi "IXSCAN".

Masalah: Dokumen MongoDB ditolak dengan error "BSONObj size is invalid (16777216 bytes)".
Penyebab : Ukuran dokumen melampaui batas hard limit 16MB akibat array yang bertumbuh tanpa batas (Unbounded Embedding).
Solusi   : Pecah array tersebut ke dalam koleksi terpisah dan gunakan pola Referencing dengan pagination.
```

---

## 18. Exercise
1. Rancang skema MongoDB untuk aplikasi Blog Medium (Entitas: User, Article, Tags, Comments).
2. Tentukan field mana yang di-embed (misal: Tags) dan mana yang di-reference (misal: Comments) beserta alasannya.
3. Tulis query Aggregation Pipeline untuk mencari 3 penulis dengan jumlah total artikel terbanyak.

---

## 19. Challenge
Rancang sistem penyimpanan status inventaris tiket penerbangan global:
1. Evaluasi apakah sistem ini lebih cocok sebagai sistem CP atau AP berdasarkan Teorema CAP, dan jelaskan konsekuensi bisnis jika terjadi partisi jaringan lintas benua.
2. Tunjukkan bagaimana arsitektur hybrid memadukan PostgreSQL untuk konfirmasi pemotongan tiket (ACID mutlak) dan Redis/Cassandra untuk pencarian jadwal penerbangan (*High Availability Search Engine*)!

---

## 20. Summary
Gerakan NoSQL dan pemahaman Teorema CAP membebaskan insinyur backend dari dogma bahwa satu jenis basis data dapat menyelesaikan seluruh permasalahan dunia (*The Myth of the Silver Bullet*). Dengan menguasai karakteristik Document Stores, Key-Value, Wide-Column, dan Graph, Anda memiliki keleluasaan merancang arsitektur penyimpanan *Polyglot Persistence* yang tangguh, efisien, dan dapat diskalakan tanpa batas.

---
[⬅️ BAB 04 Quiz & Challenge](../BAB-04-RDBMS-dan-SQL-Mastery/BAB-04-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: Consistent Hashing & Vector DB ➡️](./Module-02-Consistent-Hashing-Sharding-dan-Vector-Databases.md)
---
