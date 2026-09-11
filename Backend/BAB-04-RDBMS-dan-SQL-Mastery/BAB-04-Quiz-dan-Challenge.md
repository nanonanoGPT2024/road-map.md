---
[⬅️ Module 02: Indexing Internals & Query Planner](./Module-02-Indexing-Internals-BTree-Query-Planner-Partitioning.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Module 01: Taksonomi NoSQL & CAP Theorem ➡️](../BAB-05-Basis-Data-NoSQL-dan-NewSQL/Module-01-Taksonomi-NoSQL-CAP-Theorem-dan-Document-Stores.md)
---

# BAB 04: Basis Data Relasional (RDBMS) & SQL Mastery — Quiz & Chapter Challenge

Dokumen ini berisi pengujian pemahaman konseptual, analisis skenario transaksi perbankan riil, serta tantangan implementasi sistematis untuk BAB 04.

---

## Bagian 1: Quiz Konseptual Dasar (5 Soal)

### Soal 1
Mengapa Primary Key bertipe **UUIDv4 (Random)** dapat menurunkan performa penulisan (*insert throughput*) secara signifikan pada tabel berukuran puluhan juta baris dengan B-Tree index?
- A. UUIDv4 tidak didukung oleh database PostgreSQL.
- B. Nilai acak UUIDv4 menyebabkan penyisipan terjadi di posisi acak pada leaf page B-Tree, memicu pemecahan halaman (*B-Tree page splits*) yang masif dan fragmentasi index di disk.
- C. UUIDv4 menggunakan terlalu banyak port jaringan TCP.
- D. UUIDv4 otomatis menghapus data foreign key.

### Soal 2
Dalam jaminan transaksi ACID, mekanisme internal apakah yang digunakan oleh database modern (seperti PostgreSQL dan MySQL) untuk memastikan **Atomicity** dan **Durability** saat terjadi mati lampu mendadak?
- A. Docker volume snapshot.
- B. Write-Ahead Logging (WAL / Redo Log), di mana seluruh perubahan dicatat ke log append-only di disk sebelum data di halaman memori dimodifikasi.
- C. Menghapus tabel data yang korup secara otomatis.
- D. Membatasi ukuran RAM maksimal 4GB.

### Soal 3
Anomali konkurensi di mana Transaksi A membaca baris data yang telah dimodifikasi oleh Transaksi B yang **belum melakukan COMMIT** disebut:
- A. Phantom Read
- B. Non-Repeatable Read
- C. Dirty Read
- D. Serialization Failure

### Soal 4
Berdasarkan aturan **Leftmost Prefix Rule**, jika sebuah tabel memiliki Composite Index `idx_a_b_c ON (col_a, col_b, col_c)`, query dengan klausa WHERE manakah yang **TIDAK AKAN** menggunakan index tersebut?
- A. `WHERE col_a = 10 AND col_b = 20`
- B. `WHERE col_a = 10`
- C. `WHERE col_b = 20 AND col_c = 30`
- D. `WHERE col_a = 10 AND col_c = 30`

### Soal 5
Apa keuntungan utama dari **Covering Index** (`CREATE INDEX ... INCLUDE (...)`) pada eksekusi query PostgreSQL?
- A. Menghilangkan kebutuhan relasi Foreign Key.
- B. Memungkinkan database menyajikan data query secara murni via **Index Only Scan** tanpa perlu membaca halaman tabel fisik di Heap disk (*Zero Heap Fetches*).
- C. Mengompresi file gambar PNG secara otomatis.
- D. Membuat tabel menjadi tidak bisa di-update.

---

## Bagian 2: Quiz Skenario & Troubleshooting Tingkat Menengah (5 Soal)

### Soal 6
Sebuah platform flash sale mengalami insiden di mana 50 pengguna berhasil membeli 1 unit barang terakhir secara bersamaan, sehingga stok barang menjadi minus 49.
Strategi penguncian transaksi SQL manakah yang paling tepat untuk mencegah masalah over-selling ini di level database?
- A. `SELECT stock FROM products WHERE id = 1;` (tanpa lock).
- B. `SELECT stock FROM products WHERE id = 1 FOR UPDATE;` (Pessimistic Row Lock di dalam blok transaksi).
- C. Mengubah tipe data kolom stock menjadi VARCHAR.
- D. Menurunkan level isolasi ke Read Uncommitted.

### Soal 7
Laporan query `EXPLAIN (ANALYZE, BUFFERS)` menunjukkan:
`Seq Scan on orders (cost=0.00..184500.00 rows=500000 width=32) (actual time=0.050..1250.400 ms)`
Padahal kolom yang difilter sudah memiliki B-Tree index. Apa kemungkinan penyebab query planner memilih *Sequential Scan* alih-alih *Index Scan*?
- A. Operator WHERE menggunakan parameter yang mencakup lebih dari 30% total baris tabel (selektivitas rendah), sehingga planner menilai membaca sekuensial disk lebih murah dibanding melompat-lompat via index.
- B. Hard disk SSD mengalami bad sector.
- C. Database belum di-restart selama 30 hari.
- D. Port PostgreSQL 5432 kehabisan soket.

### Soal 8
Tabel mutasi audit bank `account_audit_logs` bertambah 50.000.000 baris setiap bulan (berukuran 150GB per bulan). Query pelaporan bulanan mulai lambat dan proses backup memakan waktu 8 jam.
Fitur arsitektur RDBMS manakah yang harus diimplementasikan untuk membagi tabel raksasa tersebut ke dalam partisi-partisi anak per bulan secara deklaratif?
- A. B-Tree Clustering
- B. Declarative Table Partitioning (Partition by Range berdasarkan kolom `created_at`).
- C. Menghapus index Primary Key.
- D. Mengubah format database menjadi SQLite.

### Soal 9
Dua transaksi di backend saling menunggu satu sama lain: Transaksi 1 mengunci Akun A dan menunggu Akun B, sedangkan Transaksi 2 mengunci Akun B dan menunggu Akun A.
PostgreSQL melempar error: `ERROR: deadlock detected (SQLSTATE 40P01)`.
Bagaimana cara terbaik merekayasa kode backend untuk mengeliminasi potensi deadlock semacam ini secara permanen?
- A. Menghapus transaksi ACID.
- B. Memastikan seluruh kode aplikasi mengunci baris data dengan urutan ID yang selalu konsisten dan deterministik (contoh: `ORDER BY id ASC FOR UPDATE`).
- C. Memperpanjang waktu `statement_timeout` menjadi 1 jam.
- D. Menggunakan koneksi database tanpa password.

### Soal 10
Pada arsitektur penskalaan database Primary-Replica, pengguna mengeluhkan bahwa sesaat setelah mengedit foto profil dan menekan tombol simpan, halaman profil yang di-refresh masih menampilkan foto profil lama. Beberapa detik kemudian foto baru baru muncul.
Fenomena apakah ini dan bagaimana mitigasi arsitektur di sisi backend?
- A. Memory leak pada browser; mitigasi: hapus cache browser.
- B. **Replication Lag** pada Read Replica asinkron; mitigasi: terapkan pola *Read-Your-Own-Writes Consistency* (arahkan query baca profil ke Primary database selama beberapa detik setelah aksi mutasi tulis).
- C. B-Tree index terbalik urutannya.
- D. Deadlock pada tabel foto.

---

## Bagian 3: Skenario Kasus Arsitektur Tingkat Lanjut (3 Soal)

### Skenario 1: Rekayasa Buku Besar Perbankan (Double-Entry Bookkeeping)
Rancang arsitektur data buku besar mutasi rekening bank berskala enterprise:
1. Skema tabel tidak boleh menggunakan `UPDATE balance` langsung (Anti-Pattern mutasi saldo di tempat).
2. Terapkan prinsip *Append-Only Immutable Ledger* (`journal_entries` dan `account_balances`).
3. Bagaimana Anda menggunakan level isolasi transaksi dan constraint SQL untuk menjamin bahwa saldo rekening tidak pernah bernilai negatif dan total saldo seluruh nasabah di bank selalu seimbang (*Zero-Sum Ledger*)?

### Skenario 2: Strategi Zero-Downtime Indexing pada Tabel 100 Juta Baris
Tabel `transactions` produksi Anda memiliki 100.000.000 baris data aktif (ukuran 80GB) yang melayani 2.000 transaksi per detik. Anda diminta menambahkan Composite Index baru `(merchant_id, status, transaction_date)`.
Jelaskan:
- Mengapa perintah `CREATE INDEX` standar akan melumpuhkan seluruh operasional bisnis Anda (*Access Exclusive Lock*).
- Bagaimana Anda mengeksekusi pembuatan index secara aman menggunakan `CREATE INDEX CONCURRENTLY` di PostgreSQL.
- Apa yang harus dilakukan jika proses pembuatan concurrent index tersebut gagal di tengah jalan (*INVALID index state*).

### Skenario 3: Optimistic vs Pessimistic Locking pada Sistem Ticketing Konser
Sebuah konser musik menyediakan 50.000 tiket yang diperebutkan oleh 500.000 pengguna dalam waktu 10 menit (rasio perebutan 10:1).
Bandingkan trade-off mendalam antara:
- Pendekatan A: Pessimistic Locking (`SELECT FOR UPDATE`).
- Pendekatan B: Optimistic Concurrency Control (OCC dengan nomor `version`).
Evaluasi keduanya dalam hal beban koneksi database, throughput transaksi per detik, dan tingkat kegagalan (*retry storm*), lalu berikan rekomendasi arsitektur terbaik!

---

## Bagian 4: Chapter Challenge — Building a High-Throughput Financial Ledger Engine

### Deskripsi Tantangan
Anda diminta membangun mesin transaksi finansial yang tahan banting di Node.js/Go dengan PostgreSQL:
1. **Skema & Integritas Data**:
   - Buat tabel `accounts` (id UUID, balance NUMERIC(15,2), version INT, created_at).
   - Buat tabel `ledger_entries` (id BIGSERIAL, tx_id UUID, account_id UUID, amount NUMERIC(15,2), direction VARCHAR(2)).
   - Pasang constraint `CHECK (balance >= 0)`.
2. **Transaksi Transfer Dana Atomik**:
   - Implementasikan fungsi transfer dana yang mengeksekusi pemotongan saldo pengirim, penambahan saldo penerima, dan pencatatan 2 baris ledger entry dalam 1 transaksi ACID tunggal.
   - Terapkan pengurutan ID deterministik untuk mencegah Deadlock.
3. **Benchmarking Konkurensi**:
   - Jalankan uji konkurensi simultan (100 worker mentransfer uang secara acak antar 10 akun).
   - Buktikan bahwa setelah 10.000 transaksi selesai dieksekusi, **total jumlah uang di seluruh cluster akun tetap bernilai sama persis dengan saldo awal**!

---

## Bagian 5: Knowledge Check & Checklist

### Saya Harus Memahami:
- [ ] Keunggulan dan kelemahan BigSerial vs UUIDv4 vs UUIDv7/ULID.
- [ ] Empat pilar ACID (Atomicity, Consistency, Isolation, Durability).
- [ ] Empat anomali konkurensi: Dirty Read, Non-Repeatable Read, Phantom Read, Serialization Anomaly.
- [ ] Empat tingkat isolasi transaksi ANSI SQL dan implementasi MVCC PostgreSQL.
- [ ] Perbedaan Optimistic Locking (OCC) vs Pessimistic Locking (`FOR UPDATE`).
- [ ] Struktur internal B-Tree Index (Root, Branch, Leaf).
- [ ] Penerapan Leftmost Prefix Rule pada Composite Index.
- [ ] Cara membaca metrik scan type dan buffers pada `EXPLAIN (ANALYZE, BUFFERS)`.
- [ ] Konsep Partition Pruning pada Declarative Table Partitioning.

### Saya Tidak Perlu Menghafal:
- [ ] Algoritma internal B-Tree page split balancing pada level source code C PostgreSQL.
- [ ] Nilai konstanta cost default engine (`seq_page_cost = 1.0`, `random_page_cost = 4.0`).

### Saya Harus Bisa Melakukan:
- [ ] Menulis transaksi transfer saldo atomik yang kebal terhadap race condition dan deadlock.
- [ ] Mengoptimalkan query lambat menggunakan Composite Index dan Covering Index (`INCLUDE`).
- [ ] Mengidentifikasi bottleneck query menggunakan `EXPLAIN ANALYZE`.
- [ ] Merancang skema tabel partisi berbasis rentang waktu (Range Partitioning).
- [ ] Mengatasi masalah Replication Lag pada arsitektur database Primary-Replica.

---
[⬅️ Module 02: Indexing Internals & Query Planner](./Module-02-Indexing-Internals-BTree-Query-Planner-Partitioning.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Module 01: Taksonomi NoSQL & CAP Theorem ➡️](../BAB-05-Basis-Data-NoSQL-dan-NewSQL/Module-01-Taksonomi-NoSQL-CAP-Theorem-dan-Document-Stores.md)
---
