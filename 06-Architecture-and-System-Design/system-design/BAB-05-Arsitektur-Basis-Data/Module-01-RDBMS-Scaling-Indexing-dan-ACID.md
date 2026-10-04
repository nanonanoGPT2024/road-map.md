# MODULE 01: RDBMS Scaling — B-Tree Indexing, Query Optimization, & ACID

## 1. Learning Objective
Setelah menyelesaikan module ini, Anda mampu:
1. Menjelaskan cara kerja struktur data **B-Tree & B+Tree Index** dan mengapa B+Tree menjadi pilihan standar engine database relasional (PostgreSQL & MySQL InnoDB).
2. Membedakan secara presisi antara **Clustered Index** dan **Non-Clustered (Secondary) Index**.
3. Menganalisis cara kerja **Query Planner / Execution Engine** menggunakan perintah `EXPLAIN ANALYZE` (Index Scan vs Seq Scan).
4. Menjelaskan 4 pilar **ACID (Atomicity, Consistency, Isolation, Durability)** dan 4 tingkat **Transaction Isolation Levels** (Read Uncommitted, Read Committed, Repeatable Read, Serializable).
5. Menjalankan benchmark langsung perbandingan kecepatan pencarian dengan Index ($O(\log N)$) vs Full Table Scan ($O(N)$) pada 100.000 records.

---

## 2. Prerequisite
- Telah menyelesaikan [BAB 04: Caching Terdistribusi & Strategi Optimasi Data](../BAB-04-Caching-Terdistribusi/).
- Memahami dasar SQL (DDL, DML, Primary Key, Foreign Key).

---

## 3. Concept
Sebuah Relational Database Management System (RDBMS) menyimpan data dalam tabel terstruktur dengan baris (*rows*) dan kolom (*columns*). Ketika ukuran tabel membesar dari 1.000 baris menjadi **100 juta baris**, pembacaan query tanpa index akan memaksa mesin database membaca setiap blok penyimpanan di disk satu per satu dari awal sampai akhir (**Full Table Scan / Sequential Scan**).

**Database Indexing** adalah struktur data tambahan yang dibuat secara terpisah di disk dan memori yang memungkinkan mesin database menemukan baris yang cocok dalam waktu logaritmik ($O(\log N)$) tanpa harus memindai seluruh isi tabel.

---

## 4. Why? (Mengapa Indexing Menjadi Kunci Pertama Skalabilitas Database?)

### Menghindari "I/O Disk Death Spiral"
Sebuah query SQL sederhana:
```sql
SELECT * FROM users WHERE email = 'andi@example.com';
```
- **Tanpa Index:** Database harus membaca seluruh 100 juta baris dari disk ke RAM. Dengan ukuran tabel 20 GB, satu query ini membutuhkan waktu **12 hingga 30 detik** dan menyedot 100% throughput disk I/O. Jika ada 10 pengguna yang melakukan query bersamaan, database langsung crash!
- **Dengan B+Tree Index:** Database hanya menelusuri 3 hingga 4 lompatan node pohon B+Tree (hanya membaca ~16 Kilobyte data). Query selesai dalam **0.8 milidetik**!

---

## 5. What? (Struktur B+Tree & Anatomi Index)

### A. Mengapa B+Tree, Bukan Binary Search Tree (BST)?
Dalam RAM, Balanced Binary Search Tree (seperti Red-Black Tree atau AVL) sangat efisien. Namun di **Disk Storage**, setiap lompatan pointer berarti satu kali operasi *Disk Seek* mekanis/elektris yang lambat.
- B+Tree adalah pohon yang memiliki banyak cabang (*high fan-out*), di mana satu node mampu menampung ratusan hingga ribuan kunci.
- Ketinggian pohon (*tree height*) B+Tree untuk 100 juta baris data biasanya **hanya 3 atau 4 tingkat**!
- Seluruh pointer data asli disimpan di level daun paling bawah (*Leaf Nodes*), dan daun-daun ini saling terhubung dalam sebuah *Linked List* dua arah yang membuat query pencarian rentang (*Range Query: `WHERE age BETWEEN 20 AND 30`*) menjadi ultra-cepat!

```text
                     [ STRUKTUR B+TREE INDEX ]
                     
                         [  100  |  200  ]  <-- Root Node (Tingkat 1)
                        /        |        \
                       /         |         \
           [ 30 | 60 ]      [ 130 | 170 ]   [ 230 | 270 ]  <-- Intermediate (Tingkat 2)
           /    |    \      /     |     \   /     |     \
          ▼     ▼     ▼    ▼      ▼      ▼ ▼      ▼      ▼
       [10..] [40..] [70..] ─── Linked List Daun ───▶ [ Data Rows Pointer ]
```

---

### B. Clustered Index vs Non-Clustered (Secondary) Index

```text
[ CLUSTERED INDEX ]
- Data baris fisik tabel diurutkan persis mengikuti urutan index ini.
- Hanya boleh ada 1 Clustered Index per tabel (biasanya Primary Key).
- Daun B+Tree langsung berisi seluruh kolom data baris (Row Data).

[ NON-CLUSTERED / SECONDARY INDEX ]
- Struktur B+Tree terpisah (misal index pada kolom 'email' atau 'created_at').
- Daun B+Tree TIDAK berisi seluruh kolom, melainkan hanya berisi (Kunci Index + Pointer/Primary Key).
- Jika query meminta kolom yang tidak ada di index, terjadi "Table Lookup" (Bookmark Lookup) ke Clustered Index.
```

---

## 6. How? (ACID & Transaction Isolation Levels)

### 4 Pilar ACID:
1. **Atomicity:** Semua operasi dalam satu transaksi sukses seluruhnya, atau dibatalkan total (*All or Nothing / Rollback*).
2. **Consistency:** Transaksi membawa database dari satu kondisi valid ke kondisi valid berikutnya (aturan schema, foreign key, dan check constraint tidak boleh dilanggar).
3. **Isolation:** Transaksi yang berjalan konkuren tidak boleh saling mengganggu atau melihat status transaksi lain yang belum commit.
4. **Durability:** Begitu transaksi di-commit, datanya permanen tersimpan di disk (melalui *Write-Ahead Logging / WAL*) dan tidak akan hilang meskipun listrik server padam sedetik kemudian.

---

### 4 Tingkat Transaction Isolation (ANSI SQL)

| Isolation Level | Dirty Read | Non-Repeatable Read | Phantom Read | Performa / Throughput |
|---|---|---|---|---|
| **Read Uncommitted** | BISA TERJADI | BISA TERJADI | BISA TERJADI | Paling Cepat (No Lock) |
| **Read Committed** (Default Postgres) | DICEGAH | BISA TERJADI | BISA TERJADI | Sangat Cepat & Aman |
| **Repeatable Read** (Default MySQL) | DICEGAH | DICEGAH | BISA TERJADI* | Menengah (MVCC Snapshot) |
| **Serializable** | DICEGAH | DICEGAH | DICEGAH | Paling Lambat (Strict Lock / Abort) |

- **Dirty Read:** Transaksi A membaca data yang sedang diubah oleh Transaksi B yang belum di-commit.
- **Non-Repeatable Read:** Transaksi A membaca baris data, lalu Transaksi B mengubah baris tersebut. Transaksi A membaca ulang dan mendapatkan nilai yang berbeda.
- **Phantom Read:** Transaksi A melakukan query range (`WHERE age > 20`), Transaksi B meng-insert baris baru dengan `age = 25`. Transaksi A membaca ulang dan menemukan baris "hantu" baru.

---

## 7. Analogy: Indeks Buku Ensiklopedia
- **Full Table Scan:** Anda mencari topik "Sejarah Komputer" di buku ensiklopedia tebal 2.000 halaman. Anda membuka dan membaca halaman 1, halaman 2, hingga halaman 2.000 secara berurutan sampai menemukan kata tersebut.
- **B+Tree Secondary Index:** Anda membuka halaman paling belakang buku (bagian "Indeks Kata"). Huruf "S" -> "Sejarah Komputer" -> Tertulis: *Lihat Halaman 412*. Anda langsung melompat membuka halaman 412 dalam hitungan detik!

---

## 8. Diagram: Alur Eksekusi Query Planner (`EXPLAIN ANALYZE`)

```text
[ Query Masuk: SELECT name, email FROM users WHERE email = 'andi@mail.com' ]
                                  │
                                  ▼
                     [ SQL Query Optimizer ]
                                  │
      ┌───────────────────────────┴───────────────────────────┐
      ▼ (Ada Index pada 'email'?)                             ▼ (Tidak Ada Index?)
[ Index Scan / B+Tree Traverse ]                      [ Sequential Table Scan ]
- Lompatan Node B+Tree: 3 Page Reads                  - Membaca 100.000 Pages dari Disk
- Waktu: 0.5 ms                                       - Waktu: 15.000 ms
      │                                                       │
      └───────────────────────────┬───────────────────────────┘
                                  ▼
                         [ Kembalikan Baris ]
```

---

## 9. Simple Example: Composite Index & Leftmost Prefix Rule
Jika Anda sering melakukan query:
```sql
SELECT * FROM orders WHERE user_id = 101 AND status = 'COMPLETED';
```
Buatlah **Composite Index (Multi-Kolom)**:
```sql
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

> **Aturan Wajib (Leftmost Prefix Rule):**  
> Index `(user_id, status)` dapat digunakan untuk:
> 1. `WHERE user_id = 101 AND status = 'PAID'` (Bisa!)
> 2. `WHERE user_id = 101` (Bisa!)  
> Tetapi **TIDAK BISA** digunakan untuk query yang HANYA mencari:
> 3. `WHERE status = 'PAID'` (Gagal! Database terpaksa melakukan Full Table Scan karena kolom sebelah kiri `user_id` tidak disertakan).

---

## 10. Practical Code Example
Lihat demonstrasi perbedaan performa drastis antara Sequential Scan vs B-Tree Index lookup pada:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m01/btree_indexing_benchmark.js`

---

## 11. Real World Example: Migrasi Uber dari Postgres ke MySQL & B-Tree Locking
- **Kasus Uber (2016):** Uber memindahkan backend dari PostgreSQL ke MySQL (InnoDB). Salah satu alasan utamanya berkaitan dengan arsitektur secondary index:
  - Pada PostgreSQL, pembaruan baris (*UPDATE*) pada tabel yang memiliki 12 secondary index memaksa PostgreSQL memperbarui seluruh 12 struktur B+Tree tersebut di disk jika pembaruan berpindah halaman (*Write Amplification*).
  - Pada MySQL InnoDB, Secondary Index hanya menyimpan kunci Primary Key. Selama Primary Key tidak berubah, update kolom non-indexed tidak perlu menyentuh secondary index.

---

## 12. Trade-offs (Menambah Index: Keuntungan vs Biaya)

| Parameter | Tanpa Index Tambahan | Memiliki Banyak Index (10+ Index) |
|---|---|---|
| **Kecepatan Baca (SELECT)** | Sangat Lambat pada tabel besar | Sangat Cepat ($O(\log N)$) |
| **Kecepatan Tulis (INSERT/UPDATE/DELETE)** | Sangat Cepat (langsung tulis ke akhir file) | **Lambat!** (Wajib update 10 pohon B+Tree serentak) |
| **Konsumsi Penyimpanan Disk** | Minimal | **Bengkak!** (Ukuran file index seringkali > ukuran tabel asli) |
| **Pemanfaatan Memory Buffer Pool** | Boros (harus memuat seluruh tabel) | Efisien (hanya memuat halaman index yang relevan) |

---

## 13. When To Use What
- **Buatlah Index pada:**
  1. Kolom yang sering muncul di klausa `WHERE`, `JOIN ON`, dan `ORDER BY`.
  2. Kolom yang memiliki selektivitas tinggi (kardinalitas tinggi, seperti `email`, `user_id`, `uuid`).
- **Gunakan Covering Index:** Jika query hanya membutuhkan kolom yang semuanya sudah ada di dalam index (`SELECT id, status FROM ...`), database tidak perlu membaca tabel fisik sama sekali (*Index Only Scan*).

---

## 14. When NOT To Use Index
- **Jangan buat index pada kolom berkardinalitas sangat rendah:** Kolom seperti `gender` (pria/wanita) atau `is_active` (true/false). Memasang index pada kolom dengan variasi nilai hanya 2 tidak akan digunakan oleh Query Optimizer karena Full Table Scan dinilai lebih murah daripada menelusuri B+Tree!
- **Jangan buat index pada tabel kecil (< 1.000 baris):** Membaca seluruh tabel kecil dari RAM jauh lebih cepat daripada overhead menelusuri B-Tree.

---

## 15. Common Mistakes
1. **Menggunakan Fungsi pada Kolom Indexed:**
   ```sql
   -- BURUK: Index pada 'created_at' TIDAK AKAN DIGUNAKAN!
   SELECT * FROM orders WHERE DATE(created_at) = '2026-09-11';

   -- BENAR: Menggunakan perbandingan range langsung
   SELECT * FROM orders WHERE created_at >= '2026-09-11 00:00:00' AND created_at < '2026-09-12 00:00:00';
   ```
2. **Over-Indexing:** Menambahkan index pada setiap kolom tabel karena takut query lambat. Ini membuat operasi `INSERT` dan batch import menjadi lambat seperti siput.
3. **Pencarian Wildcard di Awal String (`LIKE '%keyword'`):** B+Tree diurutkan dari karakter pertama. Pencarian berawalan tanda persen `%` memaksa database melakukan Full Scan!

---

## 16. Best Practices

- **Must Have:**
  - Pasang Primary Key integer berurutan (seperti `BIGINT GENERATED ALWAYS AS IDENTITY` atau `UUIDv7`) untuk menjaga clustered index tidak terfragmentasi.
  - Selalu jalankan `EXPLAIN ANALYZE` sebelum merilis query baru ke produksi.
- **Recommended:**
  - Gunakan **Partial Index** di PostgreSQL jika Anda hanya sering memfilter subset data:
    `CREATE INDEX idx_unprocessed_orders ON orders(id) WHERE status = 'PENDING';`
- **Advanced:**
  - Lakukan tuning parameter database: `shared_buffers` (25% dari total RAM), `effective_cache_size` (50-75% RAM), dan `work_mem` untuk query sorting kompleks.
- **Avoid / Overengineering:**
  - Mengubah transaction isolation level ke `Serializable` untuk seluruh query aplikasi. Ini akan memicu gelombang *Serialization Failure Error (40001)* dan transaksi gagal massal.

---

## 17. Troubleshooting Guide
```text
Gejala: Query SELECT lambat padahal sudah ada index pada kolom tersebut.
-----------------------------------------------------------------------
Penyebab:
1. Implicit Type Conversion: Kolom varchar dicari menggunakan angka integer (WHERE phone = 0812345, bukan '0812345').
2. Outdated Database Statistics: Optimizer salah memperkirakan jumlah baris karena autovacuum/analyze belum berjalan.

Solusi:
- Pastikan tipe data parameter cocok dengan tipe data kolom schema.
- Jalankan pembaruan statistik tabel:
  PostgreSQL: ANALYZE users;
  MySQL: ANALYZE TABLE users;
```

---

## 18. Hands-on Lab: Benchmark B-Tree Search vs Full Table Scan

File lab sudah disiapkan di:
`System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m01/btree_indexing_benchmark.js`

### Jalankan Uji Coba:
Buka terminal dan jalankan:
```bash
node System-Design/BAB-05-Arsitektur-Basis-Data/hands-on/m01/btree_indexing_benchmark.js
```

### Yang Ditampilkan Script Ini:
1. Mengisi memori dengan **100.000 data pengguna**.
2. Melakukan pencarian menggunakan **Full Table Scan ($O(N)$)**: Menghitung total iterasi pemindaian dan durasi waktu.
3. Melakukan pencarian yang sama menggunakan **Binary Search / B-Tree Index ($O(\log N)$)**.
4. Menampilkan perbandingan rasio kecepatan komparatif.

---

## 19. Exercises (Latihan)

### Level 1 (Easy):
Sebutkan 4 karakteristik utama dari transaksi **ACID** dan jelaskan secara singkat arti dari *Durability*!

### Level 2 (Medium):
Sebuah tabel memiliki composite index `CREATE INDEX idx_users ON users(country, city, age);`.  
Tentukan dari 4 query berikut, mana saja yang **BISA** memanfaatkan index tersebut dan mana yang **GAGAL** (terpaksa Full Table Scan):
1. `WHERE country = 'ID' AND city = 'Jakarta' AND age = 25`
2. `WHERE country = 'ID' AND age = 25`
3. `WHERE city = 'Jakarta'`
4. `WHERE country = 'ID' AND city = 'Surabaya'`

### Level 3 (Hard):
Jelaskan fenomena anomali **Non-Repeatable Read** dan **Phantom Read**! Mengapa tingkat isolasi *Repeatable Read* pada PostgreSQL (yang menggunakan teknologi Multi-Version Concurrency Control / MVCC) secara otomatis mampu mencegah Phantom Read tanpa memerlukan row locking tradisional?

---

## 20. Summary & Knowledge Check
- [ ] Memahami struktur data B+Tree dan alasan keunggulannya pada disk storage.
- [ ] Membedakan Clustered Index vs Secondary Index.
- [ ] Menguasai aturan *Leftmost Prefix* pada composite index.
- [ ] Memahami 4 pilar ACID dan 4 tingkatan Transaction Isolation.
- [ ] Mampu membaca output analisis query `EXPLAIN ANALYZE`.
