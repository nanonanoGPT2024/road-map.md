---
[⬅️ Module 02: Consistent Hashing & Vector DB](./Module-02-Consistent-Hashing-Sharding-dan-Vector-Databases.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Caching & In-Memory Stores ➡️](../BAB-06-Strategi-Caching-dan-In-Memory-Stores/Module-01-Pola-Caching-dan-Algoritma-Eviksi-LRU-LFU.md)
---

# BAB 05: Evaluasi Pemahaman, Quiz, & Tantangan Arsitektur NoSQL & NewSQL

Selamat! Anda telah menuntaskan seluruh materi **BAB 05: Basis Data Non-Relasional (NoSQL) & NewSQL**. Dokumen ini dirancang untuk mengevaluasi pemahaman konseptual, keahlian analisis arsitektur, dan ketajaman teknis Anda dalam mendesain sistem penyimpanan terdistribusi.

---

## 1. Pertanyaan Konseptual Fundamental (Basic)

1. **Jelaskan batasan fundamental Teorema CAP!** Mengapa dalam arsitektur sistem terdistribusi riil di dunia nyata, pilihan sistem secara praktis adalah antara **AP (Availability + Partition Tolerance)** atau **CP (Consistency + Partition Tolerance)**, dan tidak pernah ada pilihan "CA"?
2. **Apa perbedaan mendasar antara model Wide-Column Store (Apache Cassandra/ScyllaDB) dan Relational Database (RDBMS)?** Mengapa operasi `JOIN` dan pencarian lintas kolom non-partition-key sangat dihindari di Cassandra?
3. **Bagaimana algoritma Gossip Protocol bekerja dalam cluster NoSQL terdistribusi (seperti DynamoDB atau Cassandra)?** Apa fungsi gossip protocol dalam mendeteksi kegagalan node (*Failure Detection*) tanpa adanya *Single Point of Failure* master node?
4. **Mengapa algoritma Modulo Hashing (`hash(key) % N`) dinilai sangat berbahaya untuk cluster cache/storage yang elastis?** Masalah apa yang timbul saat jumlah node bertambah dari $N$ menjadi $N+1$?
5. **Apa yang dimaksud dengan Vector Embeddings dan mengapa Vector Database (seperti Milvus, Pinecone, atau Qdrant) diperlukan untuk aplikasi berbasis Large Language Models (LLM)?** Mengapa RDBMS tradisional lambat dalam melakukan operasi *Nearest Neighbor Search*?

---

## 2. Pertanyaan Analisis & Rekayasa Sistem (Intermediate)

6. **Formula Quorum Konsistensi:**
   Sebuah cluster NoSQL memiliki replication factor $N = 5$.
   - Jika arsitek menetapkan Quorum Tulis $W = 3$ dan Quorum Baca $R = 3$, apakah sistem menjamin pembaca selalu mendapatkan data paling mutakhir (*Strong Consistency*)? Buktikan dengan formula $R + W > N$!
   - Apa yang terjadi pada performa latensi dan ketersediaan sistem jika kita mengubah konfigurasi menjadi $W = 1$ dan $R = 5$?
7. **Virtual Nodes (Vnodes) pada Consistent Hash Ring:**
   Mengapa menempatkan satu token hash per server fisik sering kali menyebabkan ketimpangan beban (*Non-uniform load / Hotspots*)? Bagaimana teknik penempatan 100 hingga 256 virtual nodes per server fisik secara matematis meratakan persebaran partisi data?
8. **PostgreSQL JSONB vs MongoDB Document Store:**
   Kapan seorang insinyur backend sebaiknya tetap menggunakan PostgreSQL dengan tipe kolom `JSONB`, dan pada kondisi terukur seperti apa sistem harus bermigrasi ke MongoDB cluster? Bandingkan dari aspek skalabilitas penulisan, fleksibilitas index, dan kompleksitas operasional!
9. **Mekanisme Anti-Entropy & Hinted Handoff:**
   Jika sebuah node dalam cluster Cassandra mengalami network partition sesaat (down selama 2 menit), bagaimana mekanisme *Hinted Handoff* dan *Read Repair* memastikan konsistensi data tetap pulih (*Eventual Consistency*) saat node tersebut hidup kembali?
10. **NewSQL vs Traditional Sharded MySQL:**
    Bagaimana arsitektur NewSQL (seperti CockroachDB atau Google Spanner) mengatasi kerumitan transaksi terdistribusi (*Distributed Transactions*) lintas shard menggunakan algoritma konsensus Raft/Paxos dan *Multi-Version Concurrency Control (MVCC)*?

---

## 3. Studi Kasus Skenario Produksi (Scenario-Based)

### Skenario A: The Flash-Sale Hotspot Disaster
Sebuah platform marketplace menggunakan MongoDB cluster dengan sharding horizontal untuk menyimpan inventaris produk flash sale. Tim backend memilih `category_id` sebagai Shard Key.
Saat promo flash sale "Elektronik & Gadget" dibuka, 200.000 transaksi per detik menyerbu sistem. Database tiba-tiba mengalami lonjakan CPU hingga 100% pada satu server shard tertentu, sementara 9 shard lainnya hanya menggunakan 3% CPU.
- **Analisis Akar Masalah:** Mengapa pemilihan Shard Key `category_id` menyebabkan bencana *Monolithic Hotspotting*?
- **Solusi Arsitektur:** Bagaimana cara merancang ulang Compound Shard Key atau Hashed Shard Key untuk menyebarkan beban secara proporsional ke seluruh node tanpa mengorbankan performa query range scan?

### Skenario B: Dirty Reads pada Sistem E-Wallet Berbasis AP
Sebuah sistem dompet digital menggunakan database NoSQL dengan model *Eventual Consistency* ($W=1, R=1, N=3$) untuk mencapai latensi transfer super cepat (< 10 ms).
Pengguna A mentransfer uang Rp 500.000 ke Pengguna B melalui Node-1. Satu detik kemudian, Pengguna A membuka aplikasi mobile-nya yang kebetulan terhubung ke Node-3 yang belum menerima sinkronisasi replikasi, sehingga saldo Pengguna A masih menampilkan nominal sebelum transfer. Pengguna A panik dan melakukan transfer ulang.
- **Analisis:** Kegagalan jaminan konsistensi apa yang terjadi di sini?
- **Rekomendasi Teknis:** Bagaimana merancang arsitektur sesi konsistensi (*Read-Your-Own-Writes / Monotonic Read Consistency*) tanpa harus mengorbankan seluruh throughput cluster?

### Skenario C: Lonjakan Latensi Pencarian RAG pada 50 Juta Dokumen
Aplikasi Enterprise AI assistant perbankan menggunakan algoritma pencarian k-NN eksak (*Flat / Brute-force Cosine Similarity*) pada 50.000.000 dokumen SOP perbankan. Seiring bertambahnya data, latensi pencarian melonjak dari 15 ms menjadi 4.800 ms per query.
- **Rekomendasi Algoritma:** Algoritma *Approximate Nearest Neighbor* (ANN) apa (antara **HNSW - Hierarchical Navigable Small World** atau **IVF - Inverted File Index**) yang harus diimplementasikan?
- **Trade-off:** Apa trade-off antara *Recall Accuracy*, penggunaan RAM server, dan latensi *Search Throughput* yang harus dilaporkan kepada tim infrastruktur?

---

## 4. Chapter Challenge: Desain Global Multi-Region NoSQL Telemetry Storage

### Deskripsi Masalah
Perusahaan transportasi otonom (Autonomous Fleet) memiliki 100.000 armada kendaraan yang mengirimkan metrik telemetri (koordinat GPS, kecepatan, temperatur baterai, status sensor lidar) setiap 1 detik.
- Volume data masuk: $100.000 \text{ event/detik} \times 500 \text{ byte} = 50 \text{ MB/detik} \approx 4,32 \text{ Terabyte/hari}$.
- Query utama:
  1. Real-time fleet tracking: "Di mana posisi terakhir kendaraan `VEHICLE-8841`?" (SLA latensi < 10 ms).
  2. Range history scan: "Tampilkan riwayat perjalanan dan telemetri `VEHICLE-8841` pada rentang tanggal 10 Maret 2026 pukul 08:00 sampai 12:00."
  3. Geofencing alert: Deteksi jika kendaraan keluar dari zona operasional.

### Instruksi Pengerjaan
Rancang dokumen arsitektur komprehensif yang memuat:
1. **Pilihan Kategori Database:** Pilih antara Document Store, Wide-Column Time-Series, atau Key-Value Store, serta justifikasi teknisnya.
2. **Desain Kunci Distribusi (Partition Key & Clustering Key):** Rancang skema partisi agar tidak terjadi hotspotting ketika seluruh kendaraan aktif serentak.
3. **Kebijakan Replikasi & Retensi Data (TTL):** Bagaimana menangani data mentah berumur lebih dari 30 hari agar tidak menghabiskan storage disk cluster?
4. **Skema Konsistensi Quorum:** Tentukan parameter $N$, $W$, dan $R$ yang paling optimal untuk karakteristik beban *Write-heavy* (95% tulis, 5% baca).

---

## 5. Knowledge Check & Mastery Checklist

### Saya Harus Memahami:
- [ ] Batasan nyata Teorema CAP dan model PACELC dalam rekayasa sistem terdistribusi.
- [ ] Mekanisme kerja algoritma Consistent Hashing dengan Virtual Nodes dalam mencegah *Cache Avalanche*.
- [ ] Perbedaan model data NoSQL: Document, Key-Value, Wide-Column, Graph, dan Vector.
- [ ] Formula Quorum Consensus ($R + W > N$) dan trade-off latensi vs konsistensi.
- [ ] Prinsip kerja Vector Embeddings, Cosine Similarity, dan indeks HNSW untuk AI/LLM.
- [ ] Batasan arsitektur NewSQL dan bagaimana Spanner/CockroachDB menjaga ACID terdistribusi.

### Saya Tidak Perlu Menghafal:
- Formula aljabar linier perkalian matriks secara manual (cukup pahami konsep dot product dan normalisasi Euclidean).
- Nilai konstanta internal algoritma penyeimbangan pohon LSM (*Compaction Thresholds*).
- Setiap sintaks spesifik per database vendor (fokuslah pada konsep universal partisi, replikasi, dan konsensus).

### Saya Harus Bisa Melakukan:
- [ ] Menghitung persentase disrupsi kunci saat node cluster bertambah/berkurang.
- [ ] Memilih database yang tepat (RDBMS vs NoSQL vs NewSQL vs Vector DB) berdasarkan pola akses query (*Access Patterns*).
- [ ] Mengonfigurasi parameter konsistensi Quorum ($R, W, N$) sesuai prioritas bisnis (*Read-heavy* vs *Write-heavy*).
- [ ] Membangun mesin pencarian kemiripan vektor (*Cosine Similarity Search*) menggunakan Node.js atau bahasa backend lainnya.

---
[⬅️ Module 02: Consistent Hashing & Vector DB](./Module-02-Consistent-Hashing-Sharding-dan-Vector-Databases.md) | [📋 Silabus Induk](../README.md) | [BAB 06: Caching & In-Memory Stores ➡️](../BAB-06-Strategi-Caching-dan-In-Memory-Stores/Module-01-Pola-Caching-dan-Algoritma-Eviksi-LRU-LFU.md)
---
