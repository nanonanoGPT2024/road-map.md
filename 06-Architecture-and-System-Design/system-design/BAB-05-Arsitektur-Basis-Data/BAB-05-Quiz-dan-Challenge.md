# EVALUASI BAB 05: Arsitektur Basis Data & Skalabilitas Data

Dokumen evaluasi ini berisi ringkasan materi, kuis pemahaman, dan tantangan perancangan arsitektur basis data skala besar untuk menguji kesiapan Anda sebelum masuk ke **BAB 06: Protokol Komunikasi & Antar Layanan**.

---

## 📌 Chapter Summary (Rangkuman BAB 05)

Sepanjang BAB 05, Anda telah mempelajari strategi penskalaan lapisan basis data dari single-instance hingga multi-shard cluster:
1. **Module 01 (RDBMS Scaling, Indexing, & ACID):**
   - Struktur B+Tree Index dan keunggulannya pada disk IO.
   - Clustered Index (data fisik) vs Non-Clustered / Secondary Index (pointer lookup).
   - 4 Pilar ACID dan 4 tingkat Transaction Isolation Levels (Dirty Read, Non-Repeatable Read, Phantom Read).
   - Aturan *Leftmost Prefix* pada composite index.
2. **Module 02 (Database Replication & Failover):**
   - Read Scaling menggunakan Read Replicas (men-scale operasi SELECT, bukan INSERT/UPDATE).
   - Komparasi Synchronous, Asynchronous, dan Semi-Synchronous replication.
   - Dampak Replication Lag dan mitigasi *Read-Your-Own-Writes Inconsistency* via Session Consistency Router.
   - Manajemen Failover, RTO, RPO, dan pencegahan Split-Brain via Consensus Quorum (Patroni).
3. **Module 03 (Database Partitioning & Sharding):**
   - Vertical Partitioning (memecah kolom) vs Horizontal Sharding (memecah baris).
   - Strategi Range-Based, Hash-Based, dan Directory-Based Sharding.
   - Pencegahan Hot Shards dan penanganan Cross-Shard Joins.
   - Peran algoritma ID unik terdistribusi (Twitter Snowflake / UUIDv7).
4. **Module 04 (NoSQL Databases & Paradigma BASE):**
   - 4 Kategori NoSQL: Key-Value, Document, Wide-Column, dan Graph.
   - Paradigma BASE (Basically Available, Soft State, Eventual Consistency).
   - Prinsip *Query-Driven Data Modeling* dan denormalisasi data untuk menghindari Join terdistribusi.
   - Pola arsitektur *Polyglot Persistence* modern.

---

## 📝 BAB 05 QUIZ (Uji Pemahaman)

### Bagian A: Soal Fundamental (Basic)
1. Mengapa B+Tree lebih disukai sebagai struktur index database disk dibandingkan Binary Search Tree (BST)?
2. Apa yang dimaksud dengan *Clustered Index* dan mengapa sebuah tabel hanya boleh memiliki 1 Clustered Index?
3. Mengapa menambahkan 5 Read Replicas tidak akan membantu aplikasi yang mengalami bottleneck pada operasi penulisan (*Write-Heavy*)?
4. Apa perbedaan antara *Vertical Partitioning* dan *Horizontal Partitioning (Sharding)*?
5. Sebutkan 4 kategori database NoSQL dan berikan satu contoh software untuk masing-masing kategori!

### Bagian B: Soal Menengah (Intermediate)
6. Sebuah tabel memiliki composite index pada `(user_id, status, created_at)`. Mengapa query `WHERE status = 'PAID'` tidak bisa menggunakan index tersebut (*Full Table Scan*)?
7. Jelaskan fenomena anomali **Read-Your-Own-Writes Inconsistency** pada replikasi asinkron, dan bagaimana pola **Session Consistency** memecahkannya!
8. Apa kelemahan fatal dari **Range-Based Sharding** ketika diaplikasikan pada tabel yang Primary Key-nya berupa auto-increment integer yang bertambah berurutan?
9. Mengapa operasi SQL `JOIN` antar-tabel menjadi sangat mahal atau hampir mustahil dilakukan secara efisien setelah database di-shard ke 10 server fisik yang berbeda?
10. Jelaskan perbedaan filosofis antara pendekatan pemodelan data **Entity-Driven (RDBMS)** vs **Query-Driven (NoSQL seperti Cassandra/DynamoDB)**!

### Bagian C: Scenario-Based Questions (Studi Kasus Arsitektur)
11. **Skenario 1 (Kasus Saldo Finansial vs Denormalisasi):**  
    Seorang junior engineer menyarankan untuk memindahkan database transaksi perbankan e-wallet ke MongoDB dan menduplikasi saldo pengguna ke dalam setiap baris dokumen riwayat transfer demi performa baca yang cepat. Analisis bahaya arsitektural dari usulan ini terhadap garansi ACID dan integritas moneter perusahaan!
12. **Skenario 2 (Hot Shard Toko Selebriti di E-Commerce):**  
    Sebuah platform e-commerce melakukan sharding pada tabel pesanan (*orders*) menggunakan `merchant_id` sebagai Sharding Key. Salah satu merchant adalah Toko Official Brand ternama yang menghasilkan 40% dari total seluruh transaksi platform saat peluncuran produk baru. Shard tempat toko tersebut berada mengalami CPU 100% dan down. Rancang 2 solusi arsitektur untuk memitigasi *Celebrity / Hotspot Problem* ini!
13. **Skenario 3 (Replication Lag Melumpuhkan Checkout):**  
    Saat promo gajian, Replication Lag antara Primary PostgreSQL dan 4 Read Replicas melonjak dari 10 ms menjadi 45 detik. Pengguna yang baru saja menekan tombol bayar dan mengurangi saldo diarahkan ke replica untuk melihat halaman invoice. Halaman invoice menyatakan transaksi gagal karena saldo belum terpotong. Jelaskan di mana letak kegagalan routing query ini dan bagaimana arsitektur database router yang benar!

---

## 🏆 CHAPTER CHALLENGE: Merancang Arsitektur Polyglot Persistence Gojek / Uber

### Misi Arsitek:
Rancang arsitektur penyimpanan data terpadu (*Polyglot Persistence Tier*) untuk platform ride-hailing skala besar yang melayani **200.000 perjalanan per jam**:

### Syarat & Batasan Desain:
1. **Transaksi Perjalanan & Pembayaran Dompet Digital:**  
   Pilih jenis database yang menjamin kepatuhan ACID mutlak, pencegahan *double-spending*, dan pencatatan audit finansial.
2. **Riwayat Pelacakan Koordinat GPS Driver (High Velocity Time-Series):**  
   Pilih jenis database yang mampu menelan 50.000 titik koordinat GPS per detik tanpa locking.
3. **Katalog Menu Makanan (Gofood / UberEats):**  
   Pilih jenis database yang fleksibel menangani varian menu makanan yang dinamis (opsi pedas, topping, ukuran porsi) tanpa skema kaku.
4. **Pencarian Lokasi & Geocoding:**  
   Pilih teknologi database / search engine yang optimal untuk pencarian radius lokasi terdekat (*Geospatial indexing*).
5. **Session Driver & Customer:**  
   Pilih datastore in-memory untuk caching token autentikasi dan status ketersediaan driver secara real-time.

---

## ✅ Knowledge Checklist BAB 05

- [ ] Memahami cara kerja B+Tree Index dan trade-off penambahan index pada operasi write.
- [ ] Menguasai 4 tingkatan Transaction Isolation (Read Committed, Repeatable Read, Serializable).
- [ ] Memahami batasan Read Replicas dan cara mitigasi Replication Lag.
- [ ] Menguasai teknik Sharding (Range vs Hash) dan pemilihan Sharding Key yang aman dari Hotspots.
- [ ] Memahami konsekuensi Scatter-Gather Query dan hilangnya Relational Joins.
- [ ] Menguasai 4 kategori NoSQL dan paradigma BASE (Eventual Consistency).
- [ ] Mampu merancang arsitektur Polyglot Persistence yang menggabungkan SQL dan NoSQL.
