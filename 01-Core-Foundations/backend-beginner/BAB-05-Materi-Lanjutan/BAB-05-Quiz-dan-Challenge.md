# BAB 05: Quiz, Challenge, & Knowledge Check
**Relational Database Management Systems (PostgreSQL)**

---

## 1. Basic Questions (5 Soal Mendalam tentang Konsep Fundamental)

1. **Anatomi dan Jaminan ACID Engine:**
   Jelaskan perbedaan mendasar antara *Consistency* pada level ACID transaksi dengan *Consistency* pada teorema CAP. Bagaimana Write-Ahead Logging (WAL) menjamin prinsip *Durability* dan *Atomicity* ketika terjadi *kernel panic* atau pemutusan daya listrik mendadak (*abrupt power loss*) tepat di tengah operasi `COMMIT`?

2. **Model Konkurensi & Arsitektur Proses PostgreSQL:**
   PostgreSQL menggunakan arsitektur *process-based* (`fork` per koneksi via Postmaster) alih-alih *thread-based* (seperti MySQL InnoDB atau Microsoft SQL Server). 
   - Apa implikasi arsitektural dari model ini terhadap konsumsi memori sistem (*Shared Memory* vs *Process Private Memory*)?
   - Mengapa PostgreSQL sangat rentan mengalami degradasi performa drastis jika aplikasi membuka ratusan koneksi secara langsung tanpa perantara *Connection Pooler* eksternal (misalnya PgBouncer)?

3. **Integritas Referensial dan Semantik Kunci:**
   Secara arsitektur database, bedakan perilaku internal dan implikasi performa antara:
   - `PRIMARY KEY` vs `UNIQUE` constraint yang dikombinasikan dengan kolom `NOT NULL`.
   - Foreign Key dengan aksi referensial `ON DELETE CASCADE` versus `ON DELETE RESTRICT`. Bagaimana PostgreSQL memvalidasi *Foreign Key constraints* di balik layar saat terjadi mutasi data masif, dan mengapa indexing pada *Foreign Key column* menjadi kewajiban teknis yang krusial?

4. **Normalisasi Relasional vs Denormalisasi Pragmatis:**
   Jelaskan tahapan normalisasi dari 1NF hingga 3NF/BCNF menggunakan relasi data pemesanan e-commerce (*Orders*, *Order Items*, *Products*, *Customer Address*). Pada kondisi beban baca (*read-heavy*) dengan konkurensi tinggi, *bottleneck* apa yang ditimbulkan oleh skema 3NF murni, dan teknik kompensasi terukur apa yang disediakan PostgreSQL (misal: *Generated Columns*, *Materialized Views*, atau *Selective Denormalization*) tanpa mengorbankan integritas data secara fatal?

5. **Isolasi Transaksi dan Anomali Baca:**
   PostgreSQL mengimplementasikan standar SQL Isolation Levels menggunakan snapshot engine.
   - Definisikan secara teknis fenomena: *Dirty Read*, *Non-repeatable Read*, *Phantom Read*, dan *Serialization Anomaly*.
   - Mengapa pada isolasi `READ COMMITTED` (standar bawaan PostgreSQL), anomali *Non-repeatable Read* masih diizinkan terjadi? Apa perbedaan mekanisme internal *snapshot generation* antara level `READ COMMITTED` dan `REPEATABLE READ`?

---

## 2. Intermediate Questions (5 Soal Mekanisme Internal & Debugging)

1. **Mekanisme Internal MVCC, Tuple Header, dan Table Bloat:**
   PostgreSQL menerapkan *Multi-Version Concurrency Control* (MVCC) tanpa menggunakan *Undo Logs* bergaya InnoDB.
   - Bagaimana peran metadata kolom tersembunyi `xmin` dan `xmax` pada setiap *row header* (*Heap Tuple*) saat mengevaluasi visibilitas data bagi transaksi lain?
   - Jelaskan siklus hidup tuple saat perintah `UPDATE` dijalankan. Mengapa operasi `UPDATE` dan `DELETE` yang masif dapat menyebabkan *table bloat*, dan apa peran spesifik `VACUUM` serta `autovacuum` daemon dalam membersihkan *dead tuples* dan mencegah *Transaction ID Wraparound*?

2. **Mekanisme B-Tree Index dan Skenario "Index Scans Ignored":**
   Jelaskan struktur internal B-Tree index pada PostgreSQL (Root, Branch, Leaf nodes, dan korelasi pointer `TID` ke *Heap*).
   - Mengapa *query* dengan filter `WHERE column LIKE '%keyword'` atau manipulasi fungsi `WHERE LOWER(email) = 'user@test.com'` memicu mesin perencana kueri (*query planner*) mengabaikan B-Tree index standar dan beralih ke `Seq Scan`?
   - Kapan dan mengapa *query planner* secara sadar memilih `Seq Scan` daripada `Index Scan`, meskipun indeks B-Tree yang valid tersedia pada kolom yang difilter?

3. **Dekonstruksi `EXPLAIN (ANALYZE, BUFFERS)`:**
   Saat menganalisis keluaran kueri lambat, Anda melihat metrik berikut:
   ```text
   ->  Index Scan using idx_users_created_at on users  (cost=0.43..850.20 rows=500 width=64) (actual time=0.082..45.120 rows=500 loops=1)
         Buffers: shared hit=42 read=820 dirtied=12
   ```
   - Bedakan secara detail makna `cost=0.43..850.20` (estimasi) vs `actual time=0.082..45.120` (riil).
   - Apa interpretasi Anda terhadap rasio `shared hit` vs `read` pada blok *Buffers* di atas? Masalah arsitektural apa di subsistem I/O atau konfigurasi memory (`shared_buffers`) yang ditunjukkan oleh pola metrik tersebut?
   - Apa perbedaan mendasar antara `Index Scan`, `Bitmap Index Scan`, dan `Index Only Scan` (serta dependensi `Index Only Scan` terhadap *Visibility Map*)?

4. **Saturasi Memori, `work_mem`, dan Spill-to-Disk:**
   Parameter `work_mem` menentukan batasan memori yang dialokasikan sebelum operasi sorting (`ORDER BY`) atau hash join (`JOIN`, `DISTINCT`) dialihkan (*spill*) ke file sementara (*temp files* di disk).
   - Jika server dialokasikan 64 GB RAM, mengapa mengatur konfigurasi global `work_mem = 4GB` merupakan langkah berisiko tinggi yang dapat memicu *Out-Of-Memory* (OOM) killer membunuh proses PostgreSQL?
   - Bagaimana cara mendeteksi bahwa sebuah kueri mengalami *spill-to-disk* melalui metrik logs atau `EXPLAIN`, dan bagaimana strategi aman mengatur `work_mem` secara dinamis pada level sesi transaksi tertentu?

5. **Lock Escalation, Deadlock Detection, dan Row-Level Locking:**
   PostgreSQL secara eksplisit dirancang agar tidak melakukan *lock escalation* dari row-level lock ke page/table-level lock.
   - Jelaskan algoritma deteksi deadlock yang dijalankan oleh PostgreSQL saat parameter `deadlock_timeout` terlampaui.
   - Analisis skenario berikut: Transaksi 1 menjalankan `SELECT ... FOR UPDATE` pada baris A kemudian mencoba mengunci baris B. Bersamaan dengan itu, Transaksi 2 mengunci baris B dan mencoba mengunci baris A. Apa langkah mitigasi struktural pada level penulisan kode SQL aplikasi untuk mengeliminasi potensi siklus saling tunggu (*deadlock cycle*) semacam ini?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Produksi)

### Skenario A: Insiden Degradasi Performa & Bloat Pasca Batch Job Masif
Sebuah startup logistik menjalankan *cron job* harian yang memperbarui status pengiriman pada tabel `packages` (berisi 45 juta baris). Skrip melakukan `UPDATE packages SET status = 'DELIVERED', updated_at = NOW() WHERE tracking_status = 5;` yang memutasi sekitar 3 juta baris dalam satu batch transaksi tunggal. 
Setelah eksekusi selesai:
1. Latensi kueri baca pada tabel `packages` melonjak dari 15ms menjadi 4.5 detik untuk seluruh pengguna aplikasi.
2. CPU utilization server database PostgreSQL mencapai 100% konstan.
3. Ukuran fisik disk tabel `packages` membengkak dari 12 GB menjadi 28 GB dalam kurun waktu kurang dari 2 jam.

*Pertanyaan Diagnostik:*
1. Dari sudut pandang PostgreSQL MVCC dan I/O *Page Layout*, apa akar penyebab teknis (*root cause*) yang memicu lonjakan latensi baca dan pembengkakan ukuran disk tersebut?
2. Kueri katalog sistem (`pg_stat_user_tables` / `pg_stat_activity`) apa yang pertama kali harus Anda jalankan untuk memverifikasi kondisi kesehatan *vacuuming* dan aktivitas kueri?
3. Rancang protokol remediasi darurat untuk menstabilkan database, serta susun ulang arsitektur eksekusi pembaruan data massal (*batch update*) agar insiden serupa tidak terulang di masa depan tanpa membebani *autovacuum*.

---

### Skenario B: Race Condition dan Double-Spending pada Transaksi Flash Sale
Platform e-commerce meluncurkan *Flash Sale* untuk konsol game edisi terbatas dengan sisa persediaan (*stock*) tepat 5 unit. Saat gerbang penjualan dibuka, masuk 1.200 *concurrent requests* dalam kurun waktu 500 milidetik.
Kode backend yang digunakan oleh tim pengembang adalah sebagai berikut (berjalan di atas level default `READ COMMITTED`):
```sql
-- Step 1: Cek sisa stok
SELECT stock FROM product_inventories WHERE product_id = 999;
-- (Aplikasi memeriksa jika stock > 0 di memory backend)

-- Step 2: Kurangi stok jika valid
UPDATE product_inventories SET stock = stock - 1 WHERE product_id = 999;

-- Step 3: Buat data order
INSERT INTO orders (user_id, product_id, status) VALUES ($user_id, 999, 'PAID');
```
Pasca-penjualan, audit menunjukkan tabel `product_inventories` mencatat `stock = -14` dan terdapat 19 pesanan terbayar yang berhasil masuk ke tabel `orders` (*oversold* 14 unit).

*Pertanyaan Diagnostik:*
1. Uraikan secara kronologis (*interleaved execution timeline*) bagaimana level isolasi `READ COMMITTED` gagal mencegah anomali *race condition* di atas sehingga menghasilkan *negative stock*.
2. Mengapa menambahkan *Check Constraint* (`CHECK (stock >= 0)`) pada skema database adalah langkah pertahanan pertama yang mutlak, dan bagaimana reaksi aplikasi backend jika hanya mengandalkan constraint tersebut tanpa memperbaiki konkurensi?
3. Tuliskan 2 pola solusi teknis yang valid pada level SQL untuk menyelesaikan permasalahan ini:
   - Pola A: Menggunakan *Pessimistic Locking* secara eksplisit.
   - Pola B: Menggunakan operasi atomik tunggal (*Single Atomic Conditional Update*).

---

### Skenario C: Dilema Arsitektur: "Schemaless JSONB" vs "Strict Relational"
Sebuah tim pengembang aplikasi SaaS kesehatan mengalami perdebatan arsitektur internal. Demi alasan kecepatan iterasi (*agility*), tim backend memutuskan untuk menyimpan seluruh data rekam medis pasien (*Patient Medical Records*) ke dalam satu tabel relasional dengan satu kolom berjenis `JSONB`:
```sql
CREATE TABLE patient_records (
    id UUID PRIMARY KEY,
    patient_id UUID NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
Struktur `payload` berisi nested data: keluhan, resep obat (array), riwayat alergi (array), diagnosa dokter (kode ICD-10), dan tagihan asuransi.
Setelah 1 tahun berjalan dengan 8 juta baris data:
- Fitur pelaporan (*reporting*) untuk mencari pasien berdasarkan obat tertentu dan kode ICD-10 memerlukan waktu 35 detik per kueri.
- Terjadi insiden inkonsistensi data parah karena beberapa *service* backend menulis format key JSON yang salah (misal: `"icd_code"` vs `"icd10"` vs `"icd"`), sehingga data menjadi korup secara semantik tanpa validasi engine.

*Pertanyaan Diagnostik:*
1. Bandingkan trade-off performa, konsumsi ruang penyimpanan, dan jaminan integritas antara pendekatan *Document-in-Relational (JSONB)* dengan pendekatan *Normalized Relational Schema* (memecah tabel `diagnoses`, `prescriptions`, dll.) pada PostgreSQL.
2. Jika tim terpaksa mempertahankan format JSONB untuk beberapa atribut yang dinamis, indeks apa (misal: GIN dengan operator class tertentu) yang harus dibuat untuk mempercepat pencarian data di dalam array nested JSON tersebut?
3. Rancang arsitektur skema kompromi (*Hybrid Schema Architecture*) yang mempertahankan integritas data medis inti menggunakan relasional murni, namun tetap memberikan fleksibilitas untuk data custom tambahan menggunakan JSONB, lengkap dengan *validation guardrail* (seperti `JSON Schema Validation` via check constraint).

---

## 4. Chapter Challenge

### Tantangan Praktis: High-Concurrency Ledger & Inventory Engine
Rancang dan implementasikan subsistem inti database untuk sistem pergudangan terdistribusi (*Warehouse Inventory & Transactional Ledger*) menggunakan PostgreSQL murni. Sistem harus menjamin mutasi stok barang tidak pernah mengalami inkonsistensi, memiliki audit trail mutlak (*immutable ledger*), dan tahan terhadap konkurensi tinggi tanpa memicu deadlock atau degradasi performa drastis.

#### Problem:
Sebuah perusahaan logistik sering mengalami inkonsistensi saldo barang antara total stok yang ditampilkan di katalog dengan catatan fisik di gudang. Masalah ini diperparah oleh kueri mutasi yang lambat, penguncian baris yang saling bertabrakan (*deadlock*), serta ketiadaan bukti audit saat terjadi selisih stok barang bernilai tinggi.

#### Requirements:
1. **Schema DDL:**
   - Tabel `products`: Menyimpan informasi katalog barang.
   - Tabel `warehouses`: Menyimpan lokasi gudang penyimpanan.
   - Tabel `inventories`: Menyimpan total stok terkini per `product_id` dan `warehouse_id`. Stok tidak boleh bernilai negatif dalam kondisi apa pun.
   - Tabel `stock_movements` (*Audit Ledger*): Tabel *append-only* (hanya boleh `INSERT`, tidak boleh `UPDATE` atau `DELETE`) yang mencatat setiap delta mutasi stok (masuk, keluar, transfer antar gudang, penyesuaian/adjusment).
2. **Transactional Concurrency Control:**
   - Buat sebuah *Stored Procedure* atau blok fungsi SQL bernama `transfer_stock(p_product_id INT, p_source_wh INT, p_target_wh INT, p_qty INT, p_reference_id TEXT)`.
   - Prosedur harus memindahkan barang dari satu gudang ke gudang lain secara atomik.
   - Wajib menerapkan pengurutan penguncian (*Lock Ordering Strategy*) untuk mencegah insiden *Deadlock*, jika di saat yang bersamaan terjadi transfer balik dengan arah berlawanan (`A -> B` dan `B -> A`).
   - Wajib mencatat mutasi ke tabel `stock_movements` untuk kedua sisi (debit dan kredit) dalam transaksi yang sama.
3. **Optimasi & Indexing:**
   - Rancang strategi indeks yang presisi untuk mempercepat kueri pelaporan: *"Berapa histori mutasi produk X di gudang Y dalam 30 hari terakhir?"*.
   - Buktikan indeks tersebut efektif dan tidak redundan.

#### Constraints:
- Gunakan fitur PostgreSQL 15+.
- Wajib menggunakan deklarasi integritas ketat (`FOREIGN KEY`, `CHECK`, `NOT NULL`, `DEFAULT`).
- Larangan keras menggunakan tipe data `SERIAL` legacy (wajib menggunakan standar SQL: `GENERATED ALWAYS AS IDENTITY`).
- Prosedur transfer harus menolak eksekusi (*abort/rollback*) dengan pesan error yang deskriptif jika stok di gudang asal tidak mencukupi.

#### Expected Output:
1. Skrip SQL lengkap: DDL (`CREATE TABLE`, constraints, indexes).
2. Kode fungsi/prosedur SQL `transfer_stock` dengan implementasi penanganan konkurensi dan pencegahan deadlock.
3. Bukti simulasi:
   - Skenario berhasil mentransfer stok.
   - Skenario gagal karena stok tidak cukup (verifikasi rollback atomik pada tabel ledger).
   - Eksekusi `EXPLAIN (ANALYZE, BUFFERS)` pada kueri histori mutasi stok yang menunjukkan pemanfaatan indeks secara optimal (*Index Scan* atau *Index Only Scan* tanpa *Seq Scan* berlebih).

---

## 5. Knowledge Check & Checklist

Verifikasi pemahaman mandiri sebelum melanjutkan ke bab berikutnya. Berikan tanda centang jika Anda telah menguasai kompetensi di bawah ini.

### Saya harus memahami:
- [ ] Anatomi ACID dan perbedaan jaminan isolasi transaksi pada PostgreSQL (`READ COMMITTED`, `REPEATABLE READ`, `SERIALIZABLE`).
- [ ] Cara kerja MVCC di PostgreSQL: peran `xmin`, `xmax`, *dead tuples*, serta implikasinya terhadap *Heap* dan pemakaian disk.
- [ ] Arsitektur penyimpanan WAL (*Write-Ahead Logging*) dan fungsinya dalam proses *crash recovery* serta replikasi database.
- [ ] Peran dan mekanisme *autovacuum daemon*, cara kerjanya, bahaya *vacuum freeze*, dan strategi penanganan *table/index bloat*.
- [ ] Struktur internal B-Tree index dan perbedaan mendasar antara *Seq Scan*, *Index Scan*, *Bitmap Index Scan*, serta *Index Only Scan*.
- [ ] Dampak arsitektur *process-based* PostgreSQL terhadap batas memori koneksi dan urgensi penggunaan *Connection Pooler* (seperti PgBouncer).
- [ ] Konsep penguncian (*Locking levels*): *Table locks*, *Row locks*, *Pessimistic vs Optimistic Locking*, dan bagaimana deadlock terbentuk serta dianalisis.

### Saya tidak perlu menghafal:
- [ ] Seluruh ratusan parameter konfigurasi file `postgresql.conf` di luar parameter krusial (`shared_buffers`, `work_mem`, `maintenance_work_mem`, `max_connections`, `autovacuum_*`).
- [ ] Format biner internal dari *page header* PostgreSQL (8KB page layout bit-by-bit flags).
- [ ] Kode numerik spesifik untuk semua SQLSTATE error codes (cukup pahami cara membaca kelas error seperti `40P01` untuk deadlock atau `23505` untuk unique violation via manual/dokumentasi).
- [ ] Formula matematika eksak algoritma heuristik *Cost Estimator* yang digunakan oleh *Cost-Based Optimizer* (CBO).

### Saya harus bisa melakukan:
- [ ] Membaca, membedah, dan menginterpretasikan hasil kueri `EXPLAIN (ANALYZE, BUFFERS)` untuk mengidentifikasi bottleneck kueri lambat di lingkungan produksi.
- [ ] Menulis skema database DDL yang tangguh dengan tipe data presisi, aturan penamaan terstandarisasi, dan penegakan integritas data (*Check*, *Unique*, *Foreign Key Constraints*).
- [ ] Merancang skema transaksi SQL yang aman dari *race condition* menggunakan mekanisme penguncian yang tepat (`SELECT ... FOR UPDATE` atau conditional `UPDATE`).
- [ ] Mendiagnosis kueri lambat, menganalisis statistik tabel via tabel katalog (`pg_stat_user_tables`, `pg_stat_activity`), dan menentukan tindakan remediasi indeks yang akurat.
- [ ] Mengatur strategi indexing majemuk (*Composite Index*) dengan urutan kolom yang benar berdasarkan *selectivity* dan operator filter kueri.