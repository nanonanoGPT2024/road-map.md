---
[⬅️ Module 01: Relational Modeling & ACID](./Module-01-Relational-Modeling-ACID-dan-Isolation-Levels.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Quiz & Challenge ➡️](./BAB-04-Quiz-dan-Challenge.md)
---

# Module 02: Indexing Internals (B-Tree), Query Planner, & Table Partitioning

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Menguasai struktur internal **B-Tree Index** ($O(\log N)$): Root page, Branch/Internal nodes, Leaf nodes terhubung ganda (*doubly-linked list*), dan konsep *High Fan-out*.
- Membedakan jenis index khusus di PostgreSQL: **B-Tree**, **Hash**, **GIN (Generalized Inverted Index)** untuk JSONB & Full-Text Search, **GiST**, dan **BRIN (Block Range Index)** untuk time-series raksasa.
- Menerapkan aturan **Leftmost Prefix Rule** pada Composite Indexes dan mengeliminasi *table heap lookup* menggunakan **Covering Index (`INCLUDE` clause)**.
- Menganalisis laporan eksekusi query PostgreSQL via **`EXPLAIN (ANALYZE, BUFFERS)`** dan membedakan *Sequential Scan*, *Index Scan*, *Index Only Scan*, dan *Bitmap Index Scan*.
- Mengimplementasikan **Declarative Table Partitioning** (Range, List, Hash) untuk mengelola tabel multiterabyte dengan fitur **Partition Pruning**.
- Merancang topologi penskalaan database: **Primary-Replica Streaming Replication** dan memitigasi tantangan *Replication Lag*.

---

## 2. Prerequisite
- Memahami relasi tabel RDBMS dan transaksi ACID (Modul 01).
- Pemahaman struktur data pohon (Tree) dan kompleksitas algoritma Big-O ($O(1)$, $O(\log N)$, $O(N)$).
- Pemahaman konsep I/O disk (Block / Page 8KB pada sistem file Linux).

---

## 3. Concept
Dalam basis data relasional tanpa index, menemukan satu baris data di antara 50.000.000 baris data mengharuskan engine membaca seluruh file tabel dari hard disk/SSD blok demi blok (**Full Table Scan / Sequential Scan**). Jika ukuran tabel adalah 20GB, query tersebut akan memakan waktu puluhan detik dan menghabiskan bandwidth I/O storage.

**Index** adalah struktur data terpisah yang disortir secara presisi untuk mempercepat pencarian data:
- Alih-alih memindai $N$ baris ($O(N)$), index B-Tree memotong ruang pencarian secara eksponensial dalam kedalaman pohon $3$ hingga $4$ lompatan pointer ($O(\log N)$).
- Pada tabel 10.000.000 baris, B-Tree hanya membutuhkan **3 kali pembacaan disk page** untuk menemukan baris target dalam waktu **< 1 milidetik**!

```
+-----------------------------------------------------------------------------------+
|                        B-TREE INDEX STRUCTURE (3-LEVEL TREE)                      |
|                                                                                   |
|                           [ ROOT PAGE: Keys 50, 100 ]                             |
|                                  /     |     \                                    |
|             +-------------------+      |      +-------------------+               |
|             v                          v                          v               |
|  [ INTERNAL PAGE: 20, 35 ]   [ INTERNAL PAGE: 65, 80 ]  [ INTERNAL PAGE: 120, 150]|
|       /       |       \           /       |       \          /        |       \   |
|      v        v        v         v        v        v        v         v        v  |
|  [ LEAF ]<->[ LEAF ]<->[ LEAF ]<->[ LEAF ]<->[ LEAF ]<->[ LEAF ]<->[ LEAF ]<->... |
|  (Data Pointers: TID -> Points directly to physical heap disk block & offset!)     |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa pemahaman indexing dan query planning membedakan engineer senior dari pemula?
1. **Pemberantasan Query Lambat (Slow Queries)**: Menambahkan index yang tepat dapat mempercepat query reporting dari 45 detik menjadi 3 milidetik (peningkatan kecepatan 15.000x lipat!).
2. **Menghindari Perangkap Index Mubazir (Index Bloat)**: Setiap index yang ditambahkan memperlambat operasi `INSERT`, `UPDATE`, dan `DELETE`, serta memakan ruang RAM (*Buffer Pool*). Mengetahui cara merancang *Composite Index* yang efisien menghemat puluhan gigabyte memori.
3. **Mencegah Keruntuhan Database Saat Penskalaan**: Mengetahui kapan tabel harus di-partisi (*Partitioning*) mencegah tabel log atau mutasi rekening menjadi terlalu gemuk untuk di-vacuum atau di-backup.

---

## 5. What?

### A. Jenis-Jenis Index di PostgreSQL
- **B-Tree (Default)**: Pohon seimbang untuk operator perbandingan: `=`, `<`, `<=`, `>`, `>=`, `BETWEEN`, `IN`, dan pencarian prefix `LIKE 'abc%'`.
- **Hash Index**: Pencarian kesetaraan murni (`=`) dengan kompleksitas $O(1)$. Tidak mendukung sorting (`ORDER BY`) dan tidak mendukung rentang nilai.
- **GIN (Generalized Inverted Index)**: Mengindeks elemen di dalam dokumen atau koleksi. Sangat cepat untuk mencari key di dalam kolom `JSONB`, elemen di dalam `ARRAY`, dan kata di dalam **Full-Text Search (`tsvector`)**.
- **GiST (Generalized Search Tree)**: Digunakan untuk tipe data geometris/spasial (PostGIS: mencari radius jarak terdekat GPS) dan rentang waktu yang bertumpuk (*overlapping ranges*).
- **BRIN (Block Range Index)**: Dirancang untuk tabel time-series raksasa (miliaran baris) yang disisipkan berurutan (*append-only*). BRIN hanya menyimpan nilai Min/Max per 128 blok disk. Ukuran index BRIN hanya **0.1%** dari ukuran B-Tree (hanya beberapa megabyte untuk tabel ratusan gigabyte!).

### B. The Leftmost Prefix Rule pada Composite Index
Jika Anda membuat Composite Index pada tiga kolom:
```sql
CREATE INDEX idx_orders_status_created_user ON orders (status, created_at, user_id);
```
Aturan **Leftmost Prefix** menyatakan bahwa index ini HANYA dapat digunakan jika query Anda menyertakan kolom paling kiri (*leftmost*) secara berurutan:
- `WHERE status = 'PAID'` $\rightarrow$ **INDEX DIGUNAKAN (Efektif)**
- `WHERE status = 'PAID' AND created_at > '2026-01-01'` $\rightarrow$ **INDEX DIGUNAKAN (Sangat Efektif)**
- `WHERE status = 'PAID' AND user_id = 45` $\rightarrow$ **INDEX DIGUNAKAN (Hanya pada kolom status)**
- `WHERE created_at > '2026-01-01'` $\rightarrow$ **INDEX TIDAK DAPAT DIGUNAKAN! (Full Table Scan!)**
- `WHERE user_id = 45` $\rightarrow$ **INDEX TIDAK DAPAT DIGUNAKAN! (Full Table Scan!)**

### C. Covering Index (`INCLUDE` Clause)
Secara normal, setelah B-Tree menemukan pointer baris (*Tuple ID / TID*), database harus melompat membaca data tabel fisik di Heap disk (*Heap Fetch*) untuk mengambil kolom yang diminta dalam `SELECT`.
Dengan **Covering Index**, kolom tambahan disimpan langsung di leaf node index:
```sql
CREATE INDEX idx_users_email_covering ON users (email) INCLUDE (full_name, phone_number);
```
Query `SELECT full_name, phone_number FROM users WHERE email = 'alex@mail.com';` akan menghasilkan **Index Only Scan** — database **TIDAK PERNAH MENYENTUH TABEL HEAP SAMA SEKALI**! Seluruh data disajikan 100% dari cache memori index.

---

## 6. How?

### Membedah Hasil `EXPLAIN (ANALYZE, BUFFERS)`

Gunakan selalu perintah ini saat melakukan optimasi query:

```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT id, total_amount FROM orders WHERE status = 'PENDING' AND user_id = 8901;
```

*Contoh Output & Interpretasi*:
```text
Index Scan using idx_orders_user_status on orders  (cost=0.43..8.45 rows=1 width=16) (actual time=0.045..0.048 rows=1 loops=1)
  Index Cond: ((user_id = 8901) AND (status = 'PENDING'::text))
  Buffers: shared hit=4
Planning Time: 0.112 ms
Execution Time: 0.071 ms
```

*Metrik Kunci yang Harus Diperiksa*:
1. **Scan Type**:
   - `Seq Scan`: Memindai seluruh tabel (Bahaya jika tabel besar!).
   - `Index Scan`: Mencari di B-Tree lalu membaca baris tabel heap.
   - `Index Only Scan`: Terbaik! Mengambil data langsung dari B-Tree tanpa menyentuh tabel heap.
   - `Bitmap Index Scan`: Menggabungkan dua index berbeda menggunakan operasi boolean AND/OR sebelum membaca disk.
2. **Buffers: shared hit**: Menunjukkan jumlah blok 8KB yang dibaca langsung dari RAM (*Buffer Pool*). `shared read` berarti harus membaca fisik dari SSD (lambat).
3. **Execution Time**: Waktu riil eksekusi di dalam database engine.

---

## 7. Analogy
Bayangkan **Mencari Resep Masakan di Buku Ensiklopedia Kuliner 2.000 Halaman**:
- **Full Table Scan (Tanpa Index)**: Anda membuka buku dari halaman 1, membaca setiap baris sampai halaman 2.000 untuk mencari kata "Soto Ayam". Melelahkan dan memakan waktu 3 jam.
- **B-Tree Index**: Anda membuka halaman indeks di bagian belakang buku. Indeks disusun alfabetis dari A sampai Z. Anda melompat ke huruf S $\rightarrow$ So $\rightarrow$ Soto Ayam $\rightarrow$ tercatat "Halaman 412". Anda langsung membuka halaman 412 dalam 3 detik!
- **Covering Index**: Pada halaman indeks di belakang buku, di samping tulisan "Soto Ayam (Halaman 412)", penerbit buku berbaik hati mencantumkan ringkasan: `[Bahan: Ayam, Kunyit, Soun, Kaldu]`. Jika Anda hanya ingin tahu bahan-bahannya, Anda bahkan tidak perlu repot-repot membalik buku ke halaman 412! Anda mendapatkan jawaban langsung dari indeks.

---

## 8. Diagram: Table Partitioning (Declarative Range Partitioning)

```
+---------------------------------------------------------------------------------+
|               DECLARATIVE TABLE PARTITIONING (RANGE BY YEAR)                    |
+---------------------------------------------------------------------------------+

                          [ PARENT TABLE: orders ]
                          (Logical Schema Container)
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
         v                            v                            v
  [ orders_2024 ]              [ orders_2025 ]              [ orders_2026 ]
  (WHERE created_at            (WHERE created_at            (WHERE created_at
   >= 2024-01-01)               >= 2025-01-01)               >= 2026-01-01)

  QUERY DIEKSEKUSI:
  SELECT * FROM orders WHERE created_at >= '2026-05-01';

  PARTITION PRUNING ENGINE:
  Database Query Planner secara otomatis MENGABAIKAN (PRUNE) tabel 'orders_2024'
  dan 'orders_2025', dan HANYA memindai partisi 'orders_2026'!
  (Menghemat 66% beban I/O disk seketika!)
```

---

## 9. Simple Example: Implementasi Partisi Range di PostgreSQL

```sql
-- 1. Buat Parent Table Partisi
CREATE TABLE audit_logs (
    id BIGSERIAL,
    event_name VARCHAR(64) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (id, created_at) -- Kolom partisi wajib menjadi bagian dari Primary Key
) PARTITION BY RANGE (created_at);

-- 2. Buat Partisi-Partisi Anak per Kuartal
CREATE TABLE audit_logs_q1_2026 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE audit_logs_q2_2026 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- 3. Query dengan Partition Pruning Aktif
EXPLAIN SELECT * FROM audit_logs WHERE created_at = '2026-02-15 10:00:00';
-- Planner HANYA memindai partisi 'audit_logs_q1_2026'!
```

---

## 10. Practical Example: Mengindeks Kolom JSONB Menggunakan GIN Index

Seringkali data atribut produk atau metadata audit disimpan dalam format JSONB yang fleksibel:

```sql
-- Buat index GIN pada kolom metadata JSONB
CREATE INDEX idx_products_metadata_gin ON products USING gin (attributes);

-- Query pencarian cepat menggunakan operator containment (@>)
SELECT id, title, attributes 
FROM products 
WHERE attributes @> '{"color": "black", "storage": "256GB"}';
```
Query containment `@>` di atas akan dieksekusi menggunakan **Bitmap Index Scan** via GIN index dalam waktu < 2ms, alih-alih melakukan unnesting JSON yang sangat lambat!

---

## 11. Real World Example: Migrasi Uber dari PostgreSQL ke Schemaless/MySQL
Pada awal perkembangannya, Uber menyimpan data perjalanan (*trips*) di PostgreSQL.
- Masalah yang dialami: Arsitektur MVCC PostgreSQL menulis versi baris baru (*new tuple*) di disk setiap kali ada `UPDATE`. Tabel perjalanan sering di-update (posisi supir, status tarif, rating).
- Pembaruan baris fisik memaksa database memperbarui **seluruh index sekunder** yang ada pada tabel tersebut (karena index menunjuk ke alamat fisik *Tuple ID*). Fenomena ini memicu *Write Amplification* dan lonjakan I/O SSD yang masif.
- Solusi Uber: Membangun layer penyimpanan terdistribusi *Schemaless* di atas MySQL InnoDB. Di InnoDB, index sekunder menunjuk ke **Primary Key**, bukan alamat fisik tuple, sehingga update baris non-kunci primer tidak memaksa penulisan ulang seluruh index sekunder!

---

## 12. Trade-offs

| Pendekatan | Keuntungan | Kerugian |
|---|---|---|
| **Menambah Banyak Index** | Query `SELECT` spesifik menjadi sub-milidetik | Menurunkan kecepatan `INSERT/UPDATE/DELETE`, membengkakkan ukuran disk & RAM |
| **B-Tree Index** | Sangat serbaguna (equality, range, sorting) | Ukuran index besar pada tabel ratusan juta baris |
| **BRIN Index** | Ukuran index sangat mini (< 1% dari B-Tree) | Hanya efektif untuk data yang tersusun fisik secara terurut (*correlation ~ 1.0*) |
| **Table Partitioning** | Maintenance mudah (bisa `DROP TABLE` partisi lama tanpa `DELETE`), query pruning | Kompleksitas skema, foreign key antar tabel terpartisi memiliki batasan |

---

## 13. When To Use
- Buat index pada kolom yang sering muncul di klausa **`WHERE`**, **`JOIN ON`**, dan **`ORDER BY`**.
- Gunakan **Composite Index** dengan urutan kolom: `(Equality Column, Range Column)`. Letakkan kolom filter kesetaraan (`=`) paling kiri, baru diikuti kolom rentang (`>`, `<`).
- Gunakan **Table Partitioning** jika sebuah tabel bertumbuh melampaui kapasitas RAM server atau berukuran di atas 100GB.

---

## 14. When NOT To Use
- **JANGAN** membuat index pada tabel kecil (di bawah 1.000 baris). Database planner akan memilih *Sequential Scan* karena membaca seluruh tabel dari RAM lebih cepat daripada menelusuri pohon index.
- **JANGAN** membuat index pada kolom dengan **Kardinalitas Rendah** (kolom yang hanya memiliki 2 atau 3 variasi nilai, seperti `is_active` boolean atau `gender`). Index tidak akan digunakan oleh planner karena selektivitasnya buruk (*low selectivity*).
- Hindari fungsi pada kolom index di klausa WHERE (seperti `WHERE LOWER(email) = '...'` atau `WHERE DATE(created_at) = '...'`), karena akan melumpuhkan index standar! Gunakan **Expression/Functional Index** jika mutlak diperlukan.

---

## 15. Common Mistakes
1. **Membuat Index Tunggal Terpisah Alih-alih Composite Index**: Membuat index pada `user_id` dan index terpisah pada `created_at`. Query `WHERE user_id = 5 AND created_at > '...'` akan memaksa planner melakukan Bitmap Index Scan yang lebih lambat dibanding 1 Composite Index `(user_id, created_at)`.
2. **Melanggar Leftmost Prefix Rule**: Membuat index `(A, B, C)` tetapi menulis query `WHERE B = 1 AND C = 2`. Index tidak terpakai sama sekali.
3. **Mengabaikan Dampak `SELECT *`**: Menggunakan `SELECT *` menggagalkan optimasi **Index Only Scan**, memaksa engine melompat ke disk heap untuk membaca seluruh kolom yang tidak ada di index.

---

## 16. Best Practices
- **Must Have**: Buat index secara asinkron di lingkungan produksi tanpa mengunci tabel (*Zero-Downtime Indexing*):
  `CREATE INDEX CONCURRENTLY idx_name ON table (column);`
- **Recommended**: Jalankan `ANALYZE` secara periodik agar statistik planner selalu akurat dalam memprediksi jumlah baris (*cardinality estimation*).
- **Advanced**: Manfaatkan **Partial Index** untuk mengindeks subset data tertentu:
  `CREATE INDEX idx_unprocessed_orders ON orders (created_at) WHERE status = 'PENDING';` (Ukuran index sangat kecil karena mengabaikan jutaan order yang sudah sukses).
- **Avoid**: Menjalankan query dengan pola pencarian wildcard di depan: `LIKE '%keyword'`, karena B-Tree tidak dapat melompat tanpa karakter prefix awal.

---

## 17. Troubleshooting Guide
```
Masalah: Query memiliki index, tetapi EXPLAIN ANALYZE tetap menampilkan "Seq Scan".
Penyebab 1: Tipe data parameter tidak cocok (misal kolom VARCHAR dicari dengan integer WHERE phone = 08123), memicu implicit type casting yang mematikan index.
Penyebab 2: Tabel terlalu kecil sehingga Sequential Scan dinilai lebih murah oleh planner.
Penyebab 3: Nilai yang dicari mencakup lebih dari 20-30% total baris tabel (planner menganggap index lookup tidak efisien).
Solusi   : Cocokkan tipe data secara presisi dan periksa estimasi cost planner.

Masalah: Perintah CREATE INDEX membekukan seluruh aplikasi produksi (Lock timeout).
Penyebab : Perintah 'CREATE INDEX' standar membutuhkan ACCESS EXCLUSIVE lock yang memblokir operasi pembacaan dan penulisan.
Solusi   : Selalu gunakan flag CONCURRENTLY di PostgreSQL: CREATE INDEX CONCURRENTLY ...
```

---

## 18. Exercise
1. Buat tabel `users` dengan 500.000 baris data dummy.
2. Jalankan query pencarian berdasarkan email dan amati hasil `EXPLAIN (ANALYZE, BUFFERS)` sebelum ada index.
3. Buat B-Tree index pada kolom `email` dan bandingkan kembali execution time dan buffers hit-nya.
4. Buat Covering Index yang menyertakan kolom nama dan verifikasi munculnya status `Index Only Scan`.

---

## 19. Challenge
Rancang arsitektur database untuk platform pelacakan GPS armada kendaraan (IoT Fleet Management) yang menerima **50.000 data koordinat per detik**:
1. Rancang skema tabel partisi berbasis waktu (Partition by Range per hari atau per minggu).
2. Tentukan strategi pengindeksan yang optimal antara BRIN vs B-Tree Composite `(vehicle_id, recorded_at)` untuk menghemat ruang disk dan menjaga kecepatan query riwayat perjalanan kendaraan.
3. Tuliskan skrip otomatis pembersihan partisi lama (*Data Retention Policy*) menggunakan perintah `DROP TABLE` partisi tanpa membebani I/O database!

---

## 20. Summary
Index B-Tree, Composite Indexing berdisiplin Leftmost Prefix, pembacaan eksekusi query melalui `EXPLAIN ANALYZE`, dan strategi pemartisian tabel (*Partitioning*) adalah instrumen utama dalam mentransformasi basis data relasional dari sumber kemacetan menjadi mesin komputasi berkecepatan tinggi yang mampu menopang pertumbuhan bisnis hingga skala jutaan transaksi.

---
[⬅️ Module 01: Relational Modeling & ACID](./Module-01-Relational-Modeling-ACID-dan-Isolation-Levels.md) | [📋 Silabus Induk](../README.md) | [BAB 04 Quiz & Challenge ➡️](./BAB-04-Quiz-dan-Challenge.md)
---
