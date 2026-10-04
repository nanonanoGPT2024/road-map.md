# KURIKULUM POSTGRESQL ENTERPRISE DBA: BAB 02 - MODUL 02
## Topik: PostgreSQL Architecture Internals, Advanced Implementation & Production Tuning

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis Anatomi Storage Engine:** Membedah struktur internal 8KB Page Layout, Page Header, Item Pointer, dan Tuple Header (`HeapTupleHeaderData`) menggunakan ekstensi tingkat rendah seperti `pageinspect`.
2. **Menguasai Mekanika IPC & Memori:** Menjelaskan dan mengonfigurasi interaksi antara Local Memory (`work_mem`, `maintenance_work_mem`), Shared Memory (`shared_buffers`, `wal_buffers`, Lock Manager), serta Linux Kernel Page Cache.
3. **Mendiagnosis Lifecycle Transaksi & Write Path:** Menelusuri jalur data mutasi dari pemanggilan query, alokasi XID, *Buffer Pinning*, modifikasi tuple, penulisan *Write-Ahead Logging* (WAL) record, hingga persistensi disk via *Fuzzy Checkpointing*.
4. **Mengimplementasikan Strategi Eliminasi Bloat & Vacuuming:** Mengonfigurasi parameter internal *Autovacuum* untuk mencegah *Transaction ID Wraparound Emergency*, mengurangi *Heap & Index Bloat*, serta mengoptimalkan *Visibility Map* dan *Free Space Map*.
5. **Mengisolasi Bottleneck Arsitektur:** Menyelesaikan problem latensi I/O disk, *Buffer Churn*, *Lock Contention*, dan pembunuhan proses oleh Linux *Out-Of-Memory (OOM) Killer* pada sistem transaksi berkecepatan tinggi (high-throughput OLTP).

---

### 2. Prerequisite
Untuk mencerna materi ini secara komprehensif, engineer wajib memahami:
* Konsep dasar sistem operasi Linux: Virtual Memory, Memory Paging (4KB default vs HugePages 2MB/1GB), Dirty Pages, OS Page Cache, serta syscall I/O (`fsync`, `fdatasync`, `O_DIRECT`).
* Konsep relational database management system (RDBMS) dasar: Relational Algebra, ACID attributes, isolasi transaksi ANSI SQL.
* Pengalaman operasional baris perintah Linux (POSIX standard toolset: `gdb`, `strace`, `vmstat`, `iostat`, `perf`).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur internal PostgreSQL didesain berbasis model multi-proses terisolasi (*process-based model*) yang dikoordinasikan melalui *Inter-Process Communication* (IPC) di Shared Memory, berbeda mendasar dari basis multi-threaded seperti MySQL InnoDB atau Oracle.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT REQUEST                                     |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| POSTMASTER DAEMON (Process Manager: port 5432, fork() on new connection)              |
+---------------------------------------------------------------------------------------+
            |
            +--------------------+---------------------+--------------------+
            v                    v                     v                    v
    +---------------+    +---------------+     +---------------+    +---------------+
    | Backend Proc  |    | Backend Proc  |     | Background    |    | Autovacuum    |
    | (Worker 1)    |    | (Worker N)    |     | Writer (bg)   |    | Workers       |
    +---------------+    +---------------+     +---------------+    +---------------+
      | work_mem           | work_mem                  |                    |
      | temp_buffers       | temp_buffers              |                    |
      +---------+----------+---------+                 |                    |
                |                    |                 |                    |
+---------------v--------------------v-----------------v--------------------v-----------+
| POSTGRESQL SHARED MEMORY                                                              |
|  +---------------------------------------------------------------------------------+  |
|  | SHARED BUFFER POOL (shared_buffers)                                             |  |
|  |  +------------------+ +------------------+ +------------------+                 |  |
|  |  | Page 0 (8KB)     | | Page 1 (8KB)     | | Page N (8KB)     |                 |  |
|  |  | [Pin: 1, Ref: 3] | | [Dirty, Ref: 0]  | | [Free]           |                 |  |
|  |  +------------------+ +------------------+ +------------------+                 |  |
|  +---------------------------------------------------------------------------------+  |
|  | WAL BUFFERS (wal_buffers)       | LOCK MANAGER (Heavy/Lightweight Locks)       |  |
|  +---------------------------------+-----------------------------------------------+  |
|  | PROC ARRAY (Active Backends)    | COMMIT LOG (CLOG / pg_xact) CACHE             |  |
+------------------------------------+--------------------------------------------------+
          |                         |                           |
          | Read miss / Sync write  | Checkpoint Flush          | WAL Flush (at Commit)
          v                         v                           v
+---------------------------------------------------------------------------------------+
| LINUX KERNEL PAGE CACHE (Double Buffering Layer)                                      |
+---------------------------------------------------------------------------------------+
                                           |
                                           v [fsync() / fdatasync()]
+---------------------------------------------------------------------------------------+
| STORAGE SUBSYSTEM (Data Files: base/, wal: pg_wal/, clog: pg_xact/)                   |
+---------------------------------------------------------------------------------------+
```

#### 3.1. Struktur Memori: Shared Memory vs Backend Private Memory
PostgreSQL mengalokasikan dua kategori memori fisik:
1. **Shared Memory:** Dialokasikan saat startup instance via `mmap` atau System V shared memory, dibagi ke seluruh backend:
   * **`shared_buffers`:** Cache halaman data (heap dan indeks). Beroperasi dengan unit diskrit 8KB.
   * **`wal_buffers`:** Ring-buffer penyimpan record WAL sebelum di-*flush* ke disk (`pg_wal/`).
   * **Lock Manager:** Struktur *hash-table* pelacak Lightweight Locks (LWLocks) dan Heavyweight Locks.
   * **ProcArray:** State array yang mencatat semua transaksi yang sedang aktif (esensial untuk kalkulasi visibility snapshot).
2. **Backend Private Memory:** Dialokasikan per proses client melalui `malloc()` runtime Linux:
   * **`work_mem`:** Alokasi memori internal untuk operasi Sort, Hash-Join, dan Bitmap Index Scan. Alokasi ini terjadi *per-operasi*, bukan sekadar *per-koneksi*. Satu query kompleks dengan 4 join dapat mengonsumsi $4 \times \text{work\_mem}$.
   * **`maintenance_work_mem`:** Digunakan untuk eksekusi DDL, `VACUUM`, `CREATE INDEX`, dan penambahan Foreign Key.
   * **`temp_buffers`:** Cache khusus tabel sementara (*temporary tables*), tidak melalui shared buffer pool.

#### 3.2. Anatomi Halaman Fisik (The 8KB Page Layout)
Data disk PostgreSQL disimpan dalam file biner segmentasi maksimal 1GB (misal: `16384`, `16384.1`). Setiap file dipecah menjadi blok berukuran 8192 bytes (8KB).

```
+-----------------------------------------------------------------------+
| PageHeaderData (24 bytes)                                             |
| pd_lsn (8B) | pd_checksum (2B) | pd_flags (2B) | pd_lower (2B)       |
| pd_upper (2B) | pd_special (2B) | pd_pagesize_version (2B)            |
+-----------------------------------------------------------------------+
| ItemIdData Array (Line Pointers: lp_off, lp_flags, lp_len) [4 bytes/item]
| [ ItemId 1 ] -> grows downward                                        |
| [ ItemId 2 ]                                                          |
| [ ItemId 3 ]                                                          |
+-----------------------------------------------------------------------+
|                          FREE SPACE AREA                              |
|                          (pd_lower s/d pd_upper)                      |
+-----------------------------------------------------------------------+
|                                  <- grows upward                      |
| [ Tuple 3 Payload + HeapTupleHeaderData (min 23B) ]                   |
| [ Tuple 2 Payload + HeapTupleHeaderData (min 23B) ]                   |
| [ Tuple 1 Payload + HeapTupleHeaderData (min 23B) ]                   |
+-----------------------------------------------------------------------+
| Special Space (Index-specific metadata, misal B-tree opaque; 0 bytes di Heap)
+-----------------------------------------------------------------------+
```

Detail Komponen:
* **`pd_lsn` (Page Log Sequence Number):** Posisi byte absolut LSN pada WAL terakhir yang memodifikasi halaman ini. Digunakan untuk menegakkan aturan ACID melalui mekanisme *Write-Ahead Log Protocol*.
* **`pd_lower`:** Offset penunjuk akhir dari array line pointer.
* **`pd_upper`:** Offset penunjuk awal dari byte tuple data fisik terbawah.
* **Line Pointer (`ItemIdData`):** Pointer 4-byte yang menyimpan status (`LP_UNUSED`, `LP_NORMAL`, `LP_REDIRECT`, `LP_DEAD`), panjang tuple (`lp_len`), dan byte offset ke tuple fisik (`lp_off`). Pemanggilan tuple melalui Tuple Identifier (`TID` atau `ctid`) merepresentasikan kombinasi `(BlockNumber, OffsetNumber)`.

#### 3.3. Anatomi Tuple Header (`HeapTupleHeaderData`)
Setiap baris data memiliki struktur biner minimal 23 bytes sebelum memuat data user sebenarnya:
* **`t_xmin` (4 bytes / 32-bit):** Transaction ID (XID) pembuat tuple (*inserting transaction*).
* **`t_xmax` (4 bytes / 32-bit):** Transaction ID pemusnah tuple (*deleting or updating transaction*). Nilai `0` jika tuple aktif.
* **`t_cid` (4 bytes):** Command Identifier; melacak urutan query dalam satu transaksi yang memanipulasi baris tersebut.
* **`t_infomask` (2 bytes):** Bitmask status tuple (misal: `HEAP_XMIN_COMMITTED`, `HEAP_XMIN_INVALID`, `HEAP_XMAX_COMMITTED`). Status ini mencegah akses berulang ke subsystem CLOG (`pg_xact`).
* **`t_infomask2` (2 bytes):** Menampung jumlah atribut tabel dan bitmask HOT (*Heap-Only Tuples*).
* **`t_hoff` (1 byte):** Header offset menuju data user; mengakomodasi keberadaan *Null Bitmap*.

#### 3.4. Buffer Manager & Clock Sweep Algorithm
PostgreSQL menggunakan varian algoritma replacement cache bernama **Clock Sweep** untuk mengelola eviksi buffer pada `shared_buffers`:
1. Shared buffer direpresentasikan sebagai circular array dengan *victim pointer* (`clock_sweep`).
2. Setiap buffer memiliki nilai **Usage Count** (nilai integer 0 s/d 5) dan **Pin Count** (jumlah backend yang sedang membaca buffer saat ini).
3. Saat buffer dialokasikan/diakses, `usage_count` diinkrementasi (maksimal 5).
4. Ketika ruang kosong dibutuhkan dan victim pointer bergerak:
   * Jika buffer berstatus *Pinned* (Pin Count > 0), lewati buffer.
   * Jika `usage_count > 0`, kurangi nilainya 1 (`usage_count--`), gerakkan pointer ke buffer berikutnya.
   * Jika `usage_count == 0` dan tidak di-pin:
     * Jika statusnya *Clean*, buffer langsung direbut untuk halaman baru.
     * Jika statusnya *Dirty*, backend menambahkan buffer ke dirty write queue, mem-flush ke OS cache, kemudian menggunakannya.

---

### 4. Why & What

#### Mengapa Model Multi-Process (Bukan Multi-Threaded)?
1. **Fault Isolation:** Kegagalan fatal (misal: SIGSEGV akibat bug library C eksternal) hanya membunuh satu proses worker client (`postgres`). Postmaster cukup membersihkan koneksi tersebut dan merestart shared memory via recovery, tanpa menyebabkan *silent memory corruption* pada worker lain.
2. **Keamanan Portabilitas UNIX:** Menghindari kompleksitas pensinkronan thread-safe library pada era awal POSIX.
*Konsekuensi:* Overhead *context switching* proses jauh lebih tinggi dibanding thread kernel; konsumsi memori per koneksi berkisar antara 5MB–20MB. Oleh karena itu, penggunaan connection pooler eksternal (*connection pooler*) seperti **PgBouncer** atau **pgcat** menjadi syarat absolut untuk sistem skala enterprise.

#### Mengapa Append-Only MVCC (Bukan In-Place Update dengan Undo Log)?
* **PostgreSQL:** Menggunakan strategi *Out-of-place Update*. `UPDATE` sebenarnya adalah `INSERT` baris versi baru (tuple baru dengan `xmin` baru) dan penandaan baris lama dengan `xmax` baru. Tidak ada *Undo Log* terpisah.
* **MySQL (InnoDB) / Oracle:** Menggunakan strategi *In-place Update* dengan *Undo Log* terpisah untuk merekonstruksi versi data lama saat isolasi snapshot query membaca data.
* *Trade-off:* 
  * PostgreSQL memiliki write-performance sangat tinggi saat konkurensi ekstrem karena tidak memiliki contention pada alokasi rollback-segment Undo Log.
  * Kelemahannya: Menghasilkan fragmentasi disk (*bloat*), amplifikasi pemakaian storage I/O, serta ketergantungan kritis pada subsistem **Autovacuum** untuk membersihkan *dead tuples*.

---

### 5. How (Workflow Detail)

#### 5.1. Siklus Hidup Eksekusi `UPDATE` (The Write Path)
Berikut urutan deterministik eksekusi mutasi data:

```
[Client] -> UPDATE users SET balance = 500 WHERE id = 10;
   |
   v
[Postmaster / Backend Process]
   |-- 1. Parse, Analyze, Rewrite, Generate Physical Execution Plan.
   |-- 2. Alokasikan Transaction ID (XID) via Lock Manager di Shared Memory.
   |-- 3. Cari Block Halaman target via Shared Buffer Hash Table:
   |      |-- Buffer Hit: Dapatkan Buffer Descriptor ID.
   |      +-- Buffer Miss: Eviksi buffer via Clock Sweep -> Baca block 8KB dari OS Page Cache/Disk.
   |-- 4. Pin Buffer (Pin Count++), dapatkan Exclusive Buffer Content Lock (Exclusive LWLock).
   |-- 5. Evaluasi Tuple (id = 10) membaca HeapTupleHeaderData:
   |      Validasi visibilitas Snapshot -> Set t_xmax = CurrentXID pada Tuple Lama.
   |-- 6. Alokasikan Tuple Baru (balance = 500, t_xmin = CurrentXID, t_xmax = 0):
   |      |-- Jalur Optimasi HOT (Heap-Only Tuple):
   |      |   Jika kolom terindeks TIDAK berubah dan sisa Free Space di block yang SAMA mencukupi:
   |      |   -> Buat Tuple Baru di block yang sama;
   |      |   -> Hubungkan Line Pointer lama ke Line Pointer baru (LP_REDIRECT);
   |      |   -> Lewati modifikasi Index B-Tree sama sekali!
   |      +-- Non-HOT Update:
   |          -> Sisipkan Tuple Baru ke Free Space halaman yang sama atau alokasikan Block baru;
   |          -> Tambahkan entri baru ke seluruh Index terkait (Index Bloat bertambah).
   |-- 7. Bentuk WAL Record di WAL Buffer:
   |      Buat deskripsi perubahan fisik/logis (XLOG record) + Update `pd_lsn` di PageHeaderData.
   |-- 8. Tandai buffer sebagai DIRTY pada Buffer Descriptor.
   |-- 9. Lepas Exclusive LWLock dan turunkan Pin Count (Unpin).
   |
   v
[COMMIT Execution]
   |-- 1. Tulis status transaksi ke Transaction Status Log (CLOG / pg_xact) -> TRANSACTION_STATUS_COMMITTED.
   |-- 2. Perintahkan WAL Writer untuk melakukan issue system call:
   |      write(wal_fd, ...) -> fsync(wal_fd) / fdatasync().
   |-- 3. Setelah bit WAL tersimpan permanen di non-volatile medium:
   |      Kembalikan status "COMMIT SUCCESS" ke Client.
   |      (Halaman data di Shared Buffers MASIH BERSTATUS DIRTY dan BELUM ditulis ke file data!).
```

#### 5.2. Siklus Asinkronus Persistence: Checkpointer vs Background Writer
* **Background Writer (`bgwriter`):** Berjalan berkala secara terus menerus menyusuri Buffer Pool. Menulis sebagian kecil dirty buffer ke kernel cache secara bertahap untuk menjaga agar proses backend selalu menemukan *clean buffer* tanpa perlu melakukan I/O sinkronus saat mengeksekusi query.
* **Checkpointer Process:** Berjalan berdasarkan interval (`checkpoint_timeout`) atau volume WAL (`max_wal_size`).
  1. Membuat checkpoint record di WAL log.
  2. Mengidentifikasi seluruh dirty buffer yang ada di Shared Buffers pada saat checkpoint dimulai.
  3. Menulis dan melakukan `fsync()` pada seluruh dirty buffer tersebut ke disk secara bertahap (diatur oleh parameter `checkpoint_completion_target`).
  4. Memperbarui file control (`pg_control`) dengan Checkpoint Redo LSN terbaru. Setelah titik ini, segmen-segmen WAL lama sebelum Checkpoint LSN aman untuk di-recycle atau dihapus.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Kota & Catatan Notaris
* **Database (Heap Files):** Rak-rak buku tebal permanen di dalam gedung.
* **Shared Buffers:** Meja kerja utama di ruang baca; buku yang sedang dibaca ditaruh di sini.
* **Local Memory (`work_mem`):** Kertas corat-coret pribadi milik masing-masing pengunjung untuk mengurutkan daftar referensi. Setelah selesai, kertas dibuang.
* **WAL Log:** Buku harian berurutan milik Notaris. Sebelum ada halaman buku perpustakaan yang diubah, perubahan harus dicatat di buku harian ini dan divalidasi keabsahannya dengan stempel basah (`fsync`).
* **Checkpointer:** Staf pengarsip yang secara tenang memindahkan catatan-catatan coretan di meja utama ke lembaran buku asli di rak secara terjadwal.
* **Dead Tuples & Vacuum:** Paragraf usang yang dicoret dengan spidol merah. Kertas buku tidak robek, tetapi tempat coretan tersebut tidak bisa dipakai pengunjung baru sebelum "petugas tip-ex" (*Vacuum*) menandai area tersebut sebagai ruang kosong baru (*Free Space Map*).

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Membedah Page Layout & Header Menggunakan `pageinspect`
Instalasi ekstensi untuk melihat representasi biner halaman 8KB:

```sql
CREATE EXTENSION IF NOT EXISTS pageinspect;

-- Buat tabel percobaan
DROP TABLE IF EXISTS accounts;
CREATE TABLE accounts (
    id int,
    owner text,
    balance numeric
);

INSERT INTO accounts VALUES (1, 'Alice', 1000.00);

-- Ambil informasi header halaman block 0
SELECT * FROM page_header(get_raw_page('accounts', 0));
```

*Output Interpretasi Engine:*
```text
    lsn     | checksum | flags | lower | upper | special | pagesize | version | prune_xid 
------------+----------+-------+-------+-------+---------+----------+---------+-----------
 0/017DE2A8 |        0 |     0 |    28 |  8144 |    8192 |     8192 |       4 |         0
```
*Analisis:* `lower = 28` menunjukkan array line pointer (header 24 byte + 1 Line Pointer 4 byte). `upper = 8144` menunjukkan posisi awal tuple fisik pertama dari batas bawah 8192 byte ($8192 - 8144 = 48$ byte untuk payload tuple).

Inspeksi Tuple ItemId & Metadata Header:
```sql
SELECT lp, lp_off, lp_flags, lp_len, t_xmin, t_xmax, t_field3 as t_cid, t_ctid 
FROM heap_page_items(get_raw_page('accounts', 0));
```

*Output:*
```text
 lp | lp_off | lp_flags | lp_len | t_xmin | t_xmax | t_cid | t_ctid 
----+--------+----------+--------+--------+--------+-------+--------
  1 |   8144 |        1 |     44 |    756 |      0 |     0 | (0,1)
```

Lakukan Mutasi (`UPDATE`) dan amati Out-of-place tuple insertion:
```sql
UPDATE accounts SET balance = 1200.00 WHERE id = 1;

SELECT lp, lp_off, lp_flags, lp_len, t_xmin, t_xmax, t_ctid 
FROM heap_page_items(get_raw_page('accounts', 0));
```

*Output:*
```text
 lp | lp_off | lp_flags | lp_len | t_xmin | t_xmax | t_ctid 
----+--------+----------+--------+--------+--------+--------
  1 |   8144 |        1 |     44 |    756 |    757 | (0,2)
  2 |   8096 |        1 |     44 |    757 |      0 | (0,2)
```
*Interpretasi Engine:* Line pointer 1 (`(0,1)`) kini memiliki `t_xmax = 757` dan mengarahkan pointer fisiknya ke `t_ctid = (0,2)`. Baris baru disimpan pada physical offset `8096` dengan `t_xmin = 757`. Baris 1 resmi berstatus **Dead Tuple** jika transaksi 757 telah `COMMIT`.

---

#### 7.2. Practical Example: Deep Lock Contention & Shared Buffer Inspection
Script diagnosa produksi tingkat enterprise untuk melacak *Exclusive Locks* dan utilisasi buffer per-objek tabel:

```sql
-- Analisis status Shared Buffer Cache untuk tabel-tabel utama
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

SELECT 
    c.relname,
    pg_size_pretty(count(*) * 8192) as buffered_size,
    round(100.0 * count(*) / ((SELECT setting FROM pg_settings WHERE name='shared_buffers')::integer), 2) AS buffer_pool_percent,
    round(100.0 * count(*) * 8192 / pg_relation_size(c.oid), 2) as percent_of_relation_buffered,
    round(avg(b.usagecount),2) as avg_usage_count
FROM pg_buffercache b
JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
JOIN pg_database d ON (b.reldatabase = d.oid AND d.datname = current_database())
GROUP BY c.relname, c.oid
ORDER BY count(*) DESC
LIMIT 10;

-- Query Diagnosa Advanced Lock Contention Tree (Blocking vs Blocked)
SELECT
    blocked_locks.pid     AS blocked_pid,
    blocked_activity.usename  AS blocked_user,
    blocking_locks.pid    AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query    AS blocked_statement,
    blocking_activity.query   AS blocking_statement,
    now() - blocked_activity.query_start AS blocked_duration,
    blocked_locks.locktype,
    blocked_locks.mode    AS lock_mode_requested
FROM  pg_catalog.pg_locks         blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks         blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND