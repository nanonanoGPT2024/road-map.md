# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (PostgreSQL Architecture & Storage Internals)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Internal Storage Engine**: Membedah struktur fisik `Data Directory`, relasi file OS, arsitektur `Page/Block` 8KB, *item pointers* (`ItemId`), struktur tuple header, padding alignment, dan mekanisme TOAST (*The Oversized-Attribute Storage Technique*).
- **Mengevaluasi Mekanisme MVCC & Concurrency**: Menjelaskan implementasi *Multi-Version Concurrency Control* melalui transaksi snapshot, `XID` (`xmin`, `xmax`), *tuple visibility map*, *commit log* (`pg_xact`), serta mitigasi *Transaction ID Wraparound*.
- **Membedah Aliran Data Write-Ahead Logging (WAL)**: Menganalisis siklus hidup penulisan data dari `shared_buffers`, dirty pages, WAL buffers, pembentukan LSN (*Log Sequence Number*), proses `fsync`, *checkpointer*, dan background writer.
- **Mengoptimasi Autovacuum Engine**: Merumuskan formula ambang batas vacuuming, menganalisis *table bloat*, mengonfigurasi *cost-based vacuum limits*, serta melakukan tuning autovacuum pada tabel dengan *write-rate* tinggi (OLTP/CDC).
- **Mendesain Topologi High Availability & Scaling Enterprise**: Mengarsitekruri replikasi streaming (sinkron/asinkron), physical replication slots, failover berbasis Patroni dengan etcd/consul, connection pooling (PgBouncer), dan strategi horizontal data partitioning (declarative range/list/hash).

---

## 2. Prerequisites

Sebelum mempelajari modul ini, peserta diasumsikan telah menguasai:
1. **Linux Kernel & Storage Subsystem**: Pemahaman `page cache`, `fsync()`, `O_DIRECT`, dirty page writeback, file system semantics (`ext4`/`xfs`), dan manajemen I/O block storage (NVMe/EBS).
2. **Dasar SQL & Relational Modeling**: DDL, DML, transaksi ACID, isolasi transaksi ANSI SQL (`Read Committed`, `Repeatable Read`, `Serializable`), dan relasi index (B-Tree basics).
3. **Sistem Operasi & Konkurensi**: Multi-process model (bukan multi-threaded pada PostgreSQL engine), *inter-process communication* (IPC), POSIX shared memory, spinlocks, LWLock (*Lightweight Lock*), dan regular heavyweight locks.

---

## 3. Concept & Internal Architecture (Mendalam)

Arsitektur PostgreSQL mengandalkan model *Process-per-Connection* berbasis *client-server*. Berbeda dari basis data multi-threaded modern seperti MySQL (InnoDB) atau SQL Server, PostgreSQL melakukan fork proses backend baru untuk setiap sesi koneksi klien yang dikelola oleh proses induk `postmaster`.

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT LAYER                                       |
|               Client Apps (Java, Go, Python, CDC Debezium, Microservices)             |
+---------------------------------------------------------------------------------------+
                                           | (TCP/IP or Unix Socket)
                                           v
+---------------------------------------------------------------------------------------+
|                              CONNECTION & PROCESS LAYER                               |
|   +-------------------------------------------------------------------------------+   |
|   |                        Postmaster (Supervisor Process)                        |   |
|   +-------------------------------------------------------------------------------+   |
|         | forks backend per connection                                                |
|         v                                                                             |
|   +-------------------+  +-------------------+  +-------------------+                 |
|   | Postgres Backend  |  | Postgres Backend  |  | Postgres Backend  |                 |
|   | (Session 1)       |  | (Session 2)       |  | (Session N)       |                 |
|   | - Parser/Analyzer |  | - Parser/Analyzer |  | - Parser/Analyzer |                 |
|   | - Rewriter/Planner|  | - Rewriter/Planner|  | - Rewriter/Planner|                 |
|   | - Executor        |  | - Executor        |  | - Executor        |                 |
|   | - Local Memory    |  | - Local Memory    |  | - Local Memory    |                 |
|   |   (work_mem,      |  |   (work_mem,      |  |   (work_mem,      |                 |
|   |    maintenance_wm)|  |    maintenance_wm)|  |    maintenance_wm)|                 |
|   +-------------------+  +-------------------+  +-------------------+                 |
+---------------------------------------------------------------------------------------+
        |                                                            ^
        | Membaca / Menulis Buffer                                    | Mengakses Snapshot
        v                                                            |
+---------------------------------------------------------------------------------------+
|                                 SHARED MEMORY (SRAM)                                  |
|  +---------------------------------------------------------------------------------+  |
|  | shared_buffers (Array of 8KB Buffer Pages with Buffer Descriptor & Clock-Sweep) |  |
|  +---------------------------------------------------------------------------------+  |
|  | WAL Buffers (Circular ring buffer for XLOG records before disk sync)            |  |
|  +---------------------------------------------------------------------------------+  |
|  | Lock Space (Fast-Path Lock Table, Regular Heavyweight Locks, PROCLOCKs)         |  |
|  +---------------------------------------------------------------------------------+  |
|  | Commit Log / pg_xact Cache (Transaction state: IN_PROGRESS, COMMITTED, ABORTED)  |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
      |               ^                     ^                  |                ^
      | Flush WAL     | Read/Dirty Pages    | Checkpoint Flush | Dirty Flush    | VACUUM
      v               v                     |                  v                |
+---------------------------------------------------------------------------------------+
|                             BACKGROUND AUXILIARY PROCESSES                            |
|  +--------------+  +---------------+  +--------------+  +--------------------------+  |
|  | WAL Writer   |  | Checkpointer  |  |  BgWriter    |  | Autovacuum Launcher      |  |
|  | (Flushes WAL |  | (Sync dirty   |  |  (Proactive  |  | + Autovacuum Workers     |  |
|  |  buffers)    |  |  buffers to   |  |   dirty page |  | (Reclaim dead tuples,    |  |
|  |              |  |  disk pages)  |  |   flusher)   |  |  freeze XIDs, update VM) |  |
|  +--------------+  +---------------+  +--------------+  +--------------------------+  |
|  +---------------------+  +----------------------+  +------------------------------+  |
|  | Archiver Process    |  | Stats Collector      |  | Logical/Physical Replication |  |
|  | (pg_wal -> Cold/S3) |  | (Activity metrics)   |  | Walsender / Walreceiver      |  |
|  +---------------------+  +----------------------+  +------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                                STORAGE SYSTEM (OS DISK)                               |
|  $PGDATA/                                                                             |
|  ├── base/             (Database directories containing physical table/index relfilenode)
|  ├── global/           (Shared global tables like pg_database, pg_authid)             |
|  ├── pg_wal/           (16MB WAL segment files: 000000010000000000000001)             |
|  ├── pg_xact/          (Commit status per transaction: 2 bits per transaction ID)     |
|  └── pg_tblspc/        (Symlinks to external tablespaces)                             |
+---------------------------------------------------------------------------------------+
```

### 3.1. Struktur Page & Tuple Storage (Anatomi 8 Kilobyte)

PostgreSQL mengorganisasi tabel dan indeks menjadi segmen-segmen file berukuran maksimal 1 GB di disk. Setiap relasi terdiri dari kumpulan *Page* berukuran baku 8192 bytes (8 KB).

#### Layout Page Internal (Slotted Page Architecture):
```
+--------------------------------------------------------------------+
| PageHeaderData (24 Bytes)                                          |
|  - pd_lsn (8B)      : LSN dari WAL record terakhir yang modifikasi  |
|  - pd_checksum (2B) : Validasi page integrity                      |
|  - pd_flags (2B)    : Status page (has free lines, all visible)    |
|  - pd_lower (2B)    : Byte offset awal dari free space             |
|  - pd_upper (2B)    : Byte offset akhir dari free space            |
|  - pd_special (2B)  : Offset data khusus index (misal B-Tree page) |
|  - pd_pagesize_version: Versi layout dan page size                 |
+--------------------------------------------------------------------+
| ItemIdData Array (Line Pointers: lp_offset, lp_flags, lp_len)      |
|  - ItemId[0] (4 Bytes) -----------------------+                    |
|  - ItemId[1] (4 Bytes) -----------------+     |                    |
|  - ItemId[2] (4 Bytes) -----------+     |     |                    |
|  ... (Tumbuh ke BAWAH)            |     |     |                    |
+-----------------------------------|-----|-----|--------------------+
|                FREE SPACE AREA    |     |     |                    |
| (Alokasi dinamis menyusut)        |     |     |                    |
+-----------------------------------|-----|-----|--------------------+
|                                   |     |     | (Tumbuh ke ATAS)   |
| Tuple Data 2 <--------------------+     |     |                    |
| +---------------------------------------+     |                    |
| | HeapTupleHeaderData (23 Bytes + NULL Bitmap)|                    |
| | Data Columns (User attributes)              |                    |
| +---------------------------------------------+                    |
| Tuple Data 1 <--------------------------------+                    |
| +---------------------------------------------+                    |
| Tuple Data 0 <-----------------------------------------------------+
+--------------------------------------------------------------------+
| Special Space (Hanya dialokasikan pada index files)                 |
+--------------------------------------------------------------------+
```

- **Line Pointer (ItemId)**: Ukuran 4 bytes. Berfungsi sebagai pointer tidak langsung (*indirect pointer*) dari tuple ID (`ctid = (page_number, item_offset)`). Ini memungkinkan tuple dipadatkan (compacted) di dalam page tanpa mengubah indeks eksternal selama defragmentasi internal page.
- **HeapTupleHeaderData**: Memakan 23 bytes (plus padding alignment menjadi 24 bytes), ditambah sebuah dinamis `Null Bitmap`. Header ini memuat metadata MVCC kritis:
  - `t_xmin`: Transaction ID (XID) pembuat tuple.
  - `t_xmax`: Transaction ID (XID) penghapus/pengubah tuple (0 jika masih aktif).
  - `t_cid`: Command Identifier di dalam satu transaksi.
  - `t_ctid`: Pointer fisik ke tuple terkini (jika tuple telah di-*update*, `t_ctid` menunjuk ke lokasi tuple baru di page yang sama atau page lain).
  - `t_infomask` & `t_infomask2`: Bit flags status commit/abort (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`, `HEAP_UPDATED`, jumlah attributes).

### 3.2. TOAST (The Oversized-Attribute Storage Technique)

PostgreSQL tidak membolehkan ukuran tuple melebihi ukuran satu page (8 KB). Ketika lebar record melampaui ambang batas `TOAST_TUPLE_THRESHOLD` (secara default ~2 KB atau `1/4 * 8192 bytes`), PostgreSQL memicu strategi TOAST:
1. **Compress**: Kolom yang dapat dikompresi (tipe data `text`, `jsonb`, `bytea`, array) dikompresi menggunakan *PGLZ* (algoritma bawaan PostgreSQL) atau *LZ4* (pada PG 14+).
2. **Move Out-of-Line**: Jika setelah dikompresi ukuran tuple masih melebihi batas atau strategi kolom ditentukan, data dipotong-potong menjadi chunk berukuran ~2 KB dan disimpan pada tabel TOAST terpisah (dengan penamaan internal `pg_toast.pg_toast_<relfilenode>`).
3. **Pointer In-Place**: Record di heap tabel utama digantikan dengan referensi TOAST pointer 18-byte yang memuat `toast_relid` dan `chunk_id`.

Strategi storage TOAST per kolom:
- `PLAIN`: Tidak ada kompresi atau out-of-line storage (contoh: `integer`, `boolean`, `uuid`).
- `EXTENDED`: Mencoba kompresi terlebih dahulu; jika masih terlalu besar, dipindahkan out-of-line (default untuk `text`, `bytea`, `jsonb`).
- `EXTERNAL`: Dipindahkan out-of-line tanpa kompresi sama sekali (menghemat CPU bila data sudah terkompresi seperti file image/gzip).
- `MAIN`: Dicoba kompresi in-line; hanya dipindahkan out-of-line jika benar-benar tidak muat dalam page.

### 3.3. Write-Ahead Logging (WAL) & Buffer Pool Lifecycle

Integritas transaksi ACID (khususnya *Durability*) dipertahankan melalui paradigma *Write-Ahead Logging* dengan aturan emas: **WAL record yang mendeskripsikan sebuah mutasi HARUS di-flush ke disk non-volatile (`fsync`) SEBELUM page heap/indeks diizinkan untuk ditulis ke disk.**

Aliran Data Transaksi:
1. Klien mengirim perintah `UPDATE`.
2. Backend mencari page target di `shared_buffers`. Jika tidak ada (*cache miss*), dibaca dari disk OS via `read()` call ke kernel page cache lalu ditaruh di `shared_buffers`.
3. Backend mendapatkan exclusive buffer content lock, memodifikasi page di memory, menandai buffer descriptor sebagai **DIRTY**, dan menghasilkan record WAL di `wal_buffers`.
4. Tuple lama diubah `t_xmax`-nya menjadi XID transaksi aktif; tuple versi baru dibuat dengan `t_xmin` sama dengan XID transaksi aktif.
5. Saat klien mengeksekusi `COMMIT`:
   - Jika `synchronous_commit = on`: Backend memicu proses penulisan isi `wal_buffers` hingga record commit tersebut ke storage (`$PGDATA/pg_wal/`) dan memanggil system call `fsync()`.
   - Transaksi dinyatakan committed ke klien. **PENTING**: Data page di heap masih dirty dan TETAP berada di `shared_buffers`.
6. Pemindahan Dirty Pages ke Disk dilakukan secara asinkron oleh:
   - **BgWriter**: Menelusuri shared buffers secara reguler, menulis *dirty pages* ke OS page cache untuk menjaga ketersediaan buffer kosong bagi backend processes.
   - **Checkpointer**: Melakukan sinkronisasi global berkala. Checkpointer menulis seluruh dirty page saat itu ke disk dan memanggil `sync()`, kemudian mencatat LSN Checkpoint ke file kontrol (`global/pg_control`). Checkpoint adalah titik pemulihan (*recovery point*): WAL records sebelum titik checkpoint aman untuk di-*recycle*.

---

## 4. Why & What

| Komponen | What (Apa Karakteristiknya?) | Why (Mengapa Didesain Demikian & Implikasinya?) |
| :--- | :--- | :--- |
| **Append-Only MVCC** | Operasi `UPDATE` dan `DELETE` tidak menimpa data di tempat (*in-place overwrite*), melainkan menyisipkan (*append*) tuple versi baru dan menandai metadata tuple lama. | Meniadakan *read locks*. Query pembaca (*reader*) tidak pernah memblokir operasi penulisan (*writer*), dan writer tidak pernah memblokir reader. Konsekuensi: Menghasilkan *dead tuples* (bloat) yang membutuhkan pembersihan berkala melalui `VACUUM`. |
| **Fixed 8KB Page** | Unit atomik transfer data antara storage disk dan RAM memory PostgreSQL adalah blok/page berukuran 8192 bytes. | Mengimbangi ukuran transfer block controller storage dan meminimalisir fragmentasi I/O. Membatasi ukuran single row non-TOAST agar pas di memori kerja tanpa dynamic allocation berlebih. |
| **Separate TOAST Table** | Struktur penyimpanan khusus out-of-line untuk kolom berukuran besar (>2KB). | Mencegah polusi heap page tabel utama. Query scanning yang tidak memilih kolom besar tidak perlu memuat megabytes data teks/blob ke dalam `shared_buffers`. |
| **Process-per-Connection** | Setiap koneksi baru di-fork menjadi Linux process mandiri, memisahkan address space secara total. | Isolasi error superior: crash/segfault pada satu backend session tidak akan merusak memory backend session lain. Konsekuensi: Overhead memori tinggi (footprint per koneksi ~2-10 MB), mewajibkan penggunaan external *Connection Pooler* pada beban konkurensi enterprise. |
| **Transaction ID Wraparound** | `XID` adalah integer non-negatif 32-bit (~4.2 miliar transaksi unik). Nilai ini diimplementasikan secara sirkular (*modulo arithmetic*). | Batasan representasi data historis PostgreSQL. Jika sebuah database terus beroperasi melampaui ~2 miliar transaksi tanpa `VACUUM FREEZE`, PostgreSQL akan menghentikan seluruh aktivitas write untuk mencegah data lama tiba-tiba dianggap berada di "masa depan" dan menghilang. |

---

## 5. How (Workflow Detail)

### 5.1. Siklus Hidup Tuple Mutasi & MVCC Visibility

Mari bedah siklus hidup sebuah baris dari operasi `INSERT`, `UPDATE`, hingga `VACUUM`:

```
T1: Transaction XID 1000 INSERT ID 1
    +------------------------------------------------------------------+
    | Page Offset #1                                                   |
    | t_xmin: 1000 | t_xmax: 0 | t_ctid: (0,1) | data: "Alfa"          |
    +------------------------------------------------------------------+

T2: Transaction XID 1005 UPDATE ID 1 -> "Beta"
    Tuple lama ditandai t_xmax, tuple baru dibuat di slot kosong:
    +------------------------------------------------------------------+
    | Page Offset #1 (DEAD to new transactions, LIVE to old snapshot)   |
    | t_xmin: 1000 | t_xmax: 1005 | t_ctid: (0,2) | data: "Alfa"       |
    +------------------------------------------------------------------+
    | Page Offset #2 (LIVE to transaction >= 1005)                      |
    | t_xmin: 1005 | t_xmax: 0    | t_ctid: (0,2) | data: "Beta"       |
    +------------------------------------------------------------------+

T3: Transaction XID 1010 Melakukan SELECT
    Snapshot XID 1010 mengevaluasi Snapshot Engine:
    - Apakah XID 1000 committed? YES.
    - Apakah XID 1005 committed? YES.
    - Pada Offset #1: XMAX adalah 1005 (committed < 1010), maka record #1 TIDAK TERLIHAT (Dead).
    - Pada Offset #2: XMIN adalah 1005 (committed), XMAX adalah 0 (belum dihapus), maka record #2 TERLIHAT.

T4: Autovacuum Engine Berjalan
    1. Scan Visibility Map (VM).
    2. Deteksi bahwa tidak ada active snapshot di seluruh instance dengan XID < 1005.
    3. Offset #1 dinyatakan sebagai Dead Tuple yang dapat dibersihkan.
    4. Line Pointer ItemId #1 diubah statusnya menjadi LP_DEAD (atau digabung pada HOT pruning).
    5. Ruang fisik Offset #1 dialokasikan kembali ke Free Space Page untuk penulisan tuple berikutnya.
```

### 5.2. Mekanisme HOT (Heap-Only Tuples) Optimization
Jika operasi `UPDATE` terjadi dan memenuhi dua syarat:
1. Tidak ada kolom yang diindeks yang dimodifikasi.
2. Tersedia ruang kosong (*free space*) yang cukup pada **PAGE YANG SAMA**.

PostgreSQL menghindari penambahan entry baru pada file B-Tree index!
- Pointer `ItemId` baru dibuat di page yang sama.
- `ItemId` lama diarahkan langsung ke `ItemId` baru via chain link internal page.
- Index B-Tree tetap mengarah ke `ItemId` lama (Root of HOT chain).
- **Dampak performa**: Menghilangkan amplifikasi penulisan indeks (*Index Write Amplification*) secara radikal.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kantor Arsip Perusahaan Multinasional
Bayangkan sistem PostgreSQL sebagai kantor arsip dokumen fisik enterprise:
- **Heap File**: Buku binder besar tempat lembar formulir disimpan. Setiap halaman binder berkapasitas pasti 8 KB.
- **Slotted Page**: Daftar indeks di halaman depan binder mencatat posisi baris formulir ("Formulir A ada di baris bawah lembaran nomor 5"). Anda bisa menggeser isi formulir ke atas atau bawah asalkan nomor baris di halaman depan tetap sama.
- **MVCC & Append-Only**: Pegawai dilarang menggunakan penghapus cair (tipp-ex) atau merobek kertas yang salah! Jika data nasabah berubah, formulir lama dicap: *"Digantikan oleh Dokumen Versi B terhitung stempel jam X"*, dan formulir versi B ditaruh di lembar baru. Reader yang meminta dokumen versi jam lampau tetap bisa membaca formulir asli.
- **TOAST**: Jika nasabah menyerahkan berkas lampiran setebal 100 lembar (dokumen raksasa), arsiparis tidak memasukkannya ke dalam map formulir reguler karena map akan robek. Berkas itu disimpan di gudang penyimpanan terpisah (Tabel TOAST), dan map reguler hanya memuat tanda terima berisi nomor rak gudang tersebut.
- **WAL Buffer & Log**: Petugas arsip menuliskan setiap tindakan di buku catatan ekspedisi (buku jurnal anti-hilang) sebelum menyimpan berkas ke lemari. Jika gedung tiba-tiba padam atau terbakar, arsiparis bisa membangun ulang posisi berkas hanya dengan membaca buku jurnal ekspedisi tersebut dari checkpoint terakhir.
- **Autovacuum**: Petugas kebersihan malam hari yang mengecek formulir-formulir usang yang sudah tidak dibutuhkan oleh auditor mana pun, mencapnya sebagai *batal*, dan mengosongkan ruang binder agar dapat disisipkan kertas baru di masa mendatang.

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: Inspecting Internal Page Structure via `pageinspect`

Untuk memahami bagaimana data 8KB dialokasikan secara riil di memori/disk, kita menggunakan modul extension PostgreSQL bawaan: `pageinspect`.

```sql
-- Mengaktifkan modul inspeksi page low-level
CREATE EXTENSION IF NOT EXISTS pageinspect;

-- Membuat tabel demonstrasi
DROP TABLE IF EXISTS accounts_demo;
CREATE TABLE accounts_demo (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50),
    balance NUMERIC(15, 2)
);

-- Insert satu record
INSERT INTO accounts_demo (username, balance) VALUES ('alex_corporate', 5000000.00);

-- Menginspeksi Header dari Block 0 (Page pertama)
SELECT 
    lsn, 
    checksum, 
    flags, 
    lower, 
    upper, 
    special, 
    pagesize
FROM page_header(get_raw_page('accounts_demo', 0));

-- Menginspeksi Item Pointers dan Tuple Header Metadata
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len, 
    t_xmin, 
    t_xmax, 
    t_field3 as t_cid, 
    t_ctid,
    to_hex(t_infomask) as infomask_hex,
    to_hex(t_infomask2) as infomask2_hex
FROM heap_page_items(get_raw_page('accounts_demo', 0));

-- Melakukan UPDATE in-place secara logika
UPDATE accounts_demo SET balance = 5500000.00 WHERE id = 1;

-- Mengevaluasi perubahan pada Block 0 setelah UPDATE
-- Anda akan melihat DUPLIKASI tuple: tuple lama (lp=1) memiliki t_xmax terisi,
-- tuple baru (lp=2) memiliki t_xmin bernilai sama dengan t_xmax tuple lama!
SELECT 
    lp, 
    lp_off, 
    t_xmin, 
    t_xmax, 
    t_ctid 
FROM heap_page_items(get_raw_page('accounts_demo', 0));
```

### 7.2. Practical Example: Mengukur TOAST Storage & De-anonymizing Table Bloat

Di level enterprise, kita harus bisa mendeteksi seberapa banyak ruang yang dialokasikan ke TOAST versus Main Heap, serta mendeteksi dead tuple bloat menggunakan extension `pgstattuple`.

```sql
CREATE EXTENSION IF NOT EXISTS pgstattuple;

-- Membuat tabel simulasi logging microservices dengan payload JSONB besar
DROP TABLE IF EXISTS service_telemetry;
CREATE TABLE service_telemetry (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(64) NOT NULL,
    trace_payload TEXT,          -- Akan terdorong ke TOAST jika > 2KB
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
) WITH (autovacuum_vacuum_scale_factor = 0.05);

-- Mengatur Storage Strategy secara spesifik pada level kolom
ALTER TABLE service_telemetry ALTER COLUMN trace_payload SET STORAGE EXTENDED;

-- Memasukkan 5,000 data dengan string berukuran 10KB (Memicu TOAST)
INSERT INTO service_telemetry (service_name, trace_payload, metadata)
SELECT 
    'payment-service',
    repeat('CRITICAL_SYSTEM_STATE_DATA_CHUNK_' || md5(random()::text), 300),
    '{"trace_mode": "distributed", "region": "ap-southeast-1"}'::jsonb
FROM generate_series(1, 5000);

-- Query Analisis Ukuran Fisik: Heap vs TOAST vs Index
SELECT 
    c.relname AS entity_name,
    pg_size_pretty(pg_relation_size(c.oid)) AS heap_size,
    pg_size_pretty(pg_total_relation_size(c.oid) - pg_relation_size(c.oid) - pg_indexes_size(c.oid)) AS toast_size,
    pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_footprint
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'service_telemetry';

-- Mengevaluasi dead tuples dan level bloat aktual menggunakan pgstattuple
SELECT 
    table_len,            -- Total physical bytes
    tuple_count,          -- Live tuples count
    tuple_len,            -- Live tuples total bytes
    tuple_percent,        -- Percentage of physical disk for live tuples
    dead_tuple_count,     -- Dead tuples (garbage awaiting vacuum)
    dead_tuple_len,       -- Bytes consumed by dead tuples
    dead_tuple_percent,   -- Percentage of disk consumed by bloat
    free_space,           -- Free space available for re-use
    free_percent
FROM pgstattuple('service_telemetry');
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Critical Transaction ID Wraparound Outage pada Financial Gateway
**Profil Kasus**: Sebuah unicorn payment gateway memproses ~45 juta transaksi per hari (`UPDATE` status settlement berkala). Database beroperasi pada node AWS RDS PostgreSQL 64 vCPU, 256 GB RAM.

**Insiden**: Pada pukul 03:15 WIB, sistem mendadak menolak seluruh operasi penulisan DDL dan DML dengan pesan error kritis:
```
ERROR: database is not accepting commands to avoid wraparound data loss in database "payment_ledger"
HINT: Stop the postmaster and use a standalone backend to run VACUUM in single-user mode.
```
Seluruh gateway payment down total, revenue loss ditaksir mencapai ribuan dolar per menit.

### Root Cause Analysis (RCA):
1. **High Write Velocity**: Database membakar transaction ID secara masif (~2000 XID per detik).
2. **Aggressive Long-Running Analytical Queries**: Sebuah engine BI/ETL internal menjalankan snapshot query analitik read-only yang menggantung (*stale connection*) selama 4 hari dengan isolation level `REPEATABLE READ`.
3. **Autovacuum Stall**: Proses autovacuum PostgreSQL terblokir oleh `OldestXmin` dari snapshot query analitik tersebut. Autovacuum tidak diizinkan membekukan (*freeze*) tuple yang lebih muda dari snapshot terlama yang masih aktif di database.
4. **Distance to Wraparound Terlampaui**: Metrik `age(datfrozenxid)` menembus batas hard-limit 2 miliar transaksi (`autovacuum_freeze_max_age` terlampaui), memicu PostgreSQL masuk ke mode proteksi *read-only emergency shutdown*.

### Recovery & Resolusi Arsitektur Produksi:

#### Langkah Mitigasi Darurat:
1. Mematikan seluruh koneksi aplikasi eksternal untuk menghentikan pembakaran koneksi.
2. Mengidentifikasi dan membunuh paksa sesi query analitik:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
      OR (backend_type = 'client backend' AND now() - xact_start > interval '30 minutes');
   ```
3. Menjalankan VACUUM FREEZE intensif secara manual dengan memanfaatkan CPU maksimum dan temporary bypass cost limits:
   ```sql
   SET maintenance_work_mem = '16GB';
   SET max_parallel_maintenance_workers = 8;
   VACUUM FREEZE VERBOSE ANALYZE payment_transactions;
   ```

#### Tindakan Pencegahan Arsitektur Permanen:
1. **Kill Stale Transactions Secara Otomatis**: Mengaktifkan proteksi parameter timeout pada `postgresql.conf`:
   ```ini
   idle_in_transaction_session_timeout = 60000      # 1 menit
   statement_timeout = 180000                       # 3 menit untuk OLTP
   old_snapshot_threshold = 240                     # 4 jam max snapshot age
   ```
2. **Autovacuum Aggressive Re-tuning**:
   ```ini
   autovacuum_max_workers = 8
   autovacuum_vacuum_cost_limit = 3000              # Default 200 terlalu rendah untuk NVMe
   autovacuum_vacuum_cost_delay = 2                 # Kurangi delay sleep autovacuum
   autovacuum_freeze_max_age = 1000000000           # 1 miliar (freeze lebih agresif)
   ```
3. **Continuous Monitoring Alert**: Menyiapkan query alert Datadog/Prometheus untuk mendeteksi `age(datfrozenxid)` ketika menyentuh angka 500 juta.

---

## 9. Trade-offs

| Parameter Desain / Komponen | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Trade-off Sweet Spot |
| :--- | :--- | :--- | :--- |
| **`synchronous_commit = off`** | Latensi `COMMIT` turun drastis (dari ~5-15ms menjadi sub-milidetik). Throughput *write* melonjak hingga 400-800%. | Berpotensi kehilangan data transaksi terakhir (sepanjang ~3x interval `wal_writer_delay`, default 600ms) saat crash fisik OS/Server mendadak. Integritas database tetap aman (tidak korup). | Gunakan untuk high-frequency logging, metrics, audit traces, IoT ingestion, atau queue tables; **JANGAN** gunakan pada tabel financial ledger. |
| **Agresif `autovacuum_vacuum_cost_limit` (High Cost Limit)** | Membersihkan dead tuples jauh lebih cepat. Mencegah bloat tabel, menghemat storage NVMe, dan mencegah XID Wraparound. | Lonjakan utilisasi I/O disk storage. Autovacuum worker dapat mencuri I/O throughput dari transaksi aplikasi OLTP yang aktif. | Gunakan limit besar (2000-5000) jika menggunakan storage SSD Enterprise / NVMe berkecepatan tinggi; turunkan jika menggunakan standard cloud disk (misal AWS EBS GP2/GP3 burst limit rendah). |
| **Kapasitas `shared_buffers` Sangat Besar (>50% RAM)** | Lebih banyak page di-cache di PostgreSQL buffer pool; pemanfaatan memory direct pointer efisien. | *Double buffering* dengan OS Page Cache. Checkpoint sync menjadi sangat lambat; Linux kernel page cache tidak memiliki ruang cukup untuk buffering write. | Standar industri PostgreSQL: **25% hingga 40%** dari total Physical RAM host. Sisanya dialokasikan untuk OS Page Cache, `work_mem`, dan maintenance processes. |
| **HOT-optimized `fillfactor` (<100%)** | Memberikan ruang cadangan (free space) pada page untuk operasi `UPDATE`. Menghilangkan update pada file index (HOT optimization tercapai). | Ukuran awal tabel membengkak (*amplified storage usage*). Read scan membutuhkan pembacaan page lebih banyak karena densitas record per page menurun. | Atur `fillfactor = 70` s.d. `85` HANYA pada tabel yang mengalami volume operasi `UPDATE` tinggi pada kolom non-indexed. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: Salah Diagnosa Antara "Lock Wait" vs "I/O Stall"
- **Gejala**: Aplikasi mengalami latency spike tinggi. Developer menduga terjadi lock table.
- **Deteksi**: Periksa view internal `pg_stat_activity`.
  ```sql
  SELECT pid, wait_event_type, wait_event, query 
  FROM pg_stat_activity 
  WHERE wait_event_type IS NOT NULL;
  ```
- **Troubleshooting**:
  - Jika `wait_event_type = 'Lock'`: Terjadi deadlock atau contention pada heavyweight locks (row/table lock).
  - Jika `wait_event_type = 'IO'`: Backend menunggu sinkronisasi WAL (`WALWrite`, `WALSync`) atau membaca data dari disk (`DataFileRead`). Solusi: Cek latensi disk, tingkatkan `shared_buffers`, atau ubah setting checkpoint!

### Mistake 2: Checkpoint Spikes Akibat Konfigurasi Default yang Buruk
- **Gejala**: PostgreSQL mengalami "freeze" periodik setiap 5 menit; I/O disk melonjak ke 100% lalu turun drastis.
- **Penyebab**: Default konfigurasi `max_wal_size` terlalu kecil atau `checkpoint_completion_target` diset terlalu rendah (misal 0.5), menyebabkan dirty page dipaksa flush dalam durasi singkat.
- **Troubleshooting & Fix**:
  ```ini
  -- postgresql.conf
  max_wal_size = 16GB
  min_wal_size = 2GB
  checkpoint_timeout = 15min
  checkpoint_completion_target = 0.9 -- Menyebarkan I/O write ke 90% durasi checkpoint window
  ```

### Mistake 3: Membiarkan Table Bloat Parah yang Menghancurkan B-Tree Scan
- **Gejala**: Query `SELECT ... WHERE id = ...` lambat padahal memakai index scan. Disk relation bertambah 5x lipat meski jumlah row konstan.
- **Deteksi**:
  ```sql
  SELECT schemaname, relname, n_dead_tup, n_live_tup, 
         round(n_dead_tup * 100.0 / nullif(n_live_tup + n_dead_tup, 0), 2) AS dead_ratio
  FROM pg_stat_all_tables
  WHERE (n_dead_tup + n_live_tup) > 10000
  ORDER BY dead_ratio DESC;
  ```
- **Solusi**: Gunakan alat pemadatan non-blocking seperti `pg_repack` untuk membangun ulang struktur heap dan B-Tree tanpa exclusive locking (`ACCESS EXCLUSIVE LOCK` dari `VACUUM FULL` akan mengunci tabel dari proses baca dan tulis).

---

## 11. Best Practices (Production Checklist)

1. **Storage Layout & Filesystem**:
   - Gunakan sistem berkas **XFS** atau **ext4** yang dipasang (*mounted*) dengan opsi `noatime`.
   - Pisahkan folder `$PGDATA/pg_wal` ke dedicated volume disk/NVMe terpisah dari direktori base data tabel jika throughput transaksi tulis melampaui 10.000 TPS.
2. **Buffer Pool & Memory Tuning**:
   - `shared_buffers`: 25% dari Total Host RAM (maksimal praktis ~64GB pada bare-metal modern).
   - `work_mem`: Alokasikan secara konservatif (misal 16MB - 64MB). Ingat: `work_mem` dialokasikan *per-node query plan*, bukan per-koneksi. Satu query kompleks dengan 4 join dan sort dapat mengonsumsi 4x nilai `work_mem`.
   - `maintenance_work_mem`: 1GB s.d. 4GB untuk mempercepat proses indexing dan manual vacuuming.
3. **Connection Pooling Architecture**:
   - PostgreSQL engine **tidak boleh terpapar langsung** ke aplikasi berskala besar tanpa pooler.
   - Pasang **PgBouncer** di depan PostgreSQL menggunakan mode `pool_mode = transaction`.
   - Batasi koneksi aktif ke engine PostgreSQL riil maksimal `(2 * Core CPU) + disk spindle count` (biasanya 50 - 200 koneksi fisik backend).
4. **Autovacuum Tuning Baseline**:
   - Pastikan autovacuum menyala (`autovacuum = on`).
   - Ubah `autovacuum_max_workers` menjadi 5-8 worker.
   - Turunkan threshold scale factor untuk tabel besar: `autovacuum_vacuum_scale_factor = 0.05` (5%).

---

## 12. Hands-on Practice

Simpan seluruh file instruksi, script DDL, dan tuning ini pada path: `hands-on/m02/`

### File: `hands-on/m02/01_inspect_internals.sql`
Script SQL untuk mengaudit konfigurasi storage dan memory instance:
```sql
-- Memvalidasi parameter kritis arsitektur storage
SELECT name, setting, unit, context, short_desc 
FROM pg_settings 
WHERE name IN (
    'shared_buffers', 
    'wal_buffers', 
    'checkpoint_completion_target', 
    'max_wal_size', 
    'autovacuum_vacuum_cost_limit',
    'autovacuum_vacuum_cost_delay'
);

-- Query status LSN (Log Sequence Number) saat ini
SELECT 
    pg_current_wal_lsn() AS current_lsn,
    pg_walfile_name(pg_current_wal_lsn()) AS active_wal_file;
```

### File: `hands-on/m02/02_hot_update_simulation.sql`
Script SQL untuk memverifikasi efektivitas teknik HOT (Heap-Only Tuples):
```sql
DROP TABLE IF EXISTS hot_audit_test;
-- Tabel dengan fillfactor 70% untuk menyisakan free-space 30% per page
CREATE TABLE hot_audit_test (
    id INT PRIMARY KEY,
    status_code VARCHAR(20),
    description TEXT
) WITH (fillfactor = 70);

INSERT INTO hot_audit_test (id, status_code, description)
SELECT i, 'INIT', 'Benchmark payload record number ' || i
FROM generate_series(1, 1000) AS i;

-- Reset statistik relasi
SELECT pg_stat_reset();

-- Lakukan UPDATE berulang pada kolom non-indexed
UPDATE hot_audit_test SET status_code = 'IN_FLIGHT' WHERE id <= 500;
UPDATE hot_audit_test SET status_code = 'SUCCESS' WHERE id <= 500;

-- Evaluasi metrik efisiensi HOT
-- Perhatikan rasio n_tup_hot_upd terhadap n_tup_upd
SELECT 
    relname, 
    n_tup_ins, 
    n_tup_upd, 
    n_tup_hot_upd,
    round((n_tup_hot_upd::numeric / nullif(n_tup_upd, 0)::numeric) * 100, 2) AS hot_update_ratio_pct
FROM pg_stat_user_tables 
WHERE relname = 'hot_audit_test';
```

### File: `hands-on/m02/03_production_pgbouncer_setup.ini`
Konfigurasi optimal PgBouncer untuk arsitektur transaksi microservices:
```ini
[databases]
enterprise_core = host=127.0.0.1 port=5432 dbname=enterprise_core auth_user=postgres

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

# Transaction pooling mode guarantees maximum efficiency for microservices
pool_mode = transaction

# Connection limits
max_client_conn = 5000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 5
reserve_pool_timeout = 5

# Performance tuning
server_reset_query = DISCARD ALL
server_check_query = SELECT 1
server_check_delay = 30
max_user_connections = 200
```

---

## 13. Exercises

### Level Easy
1. Jalankan query inspeksi pada instance PostgreSQL Anda untuk mengetahui letak fisik direktori data (`$PGDATA`) dan nama file relfilenode dari tabel `pg_class`.
2. Jelaskan perbedaan mendasar fungsi field `t_xmin` dan `t_xmax` yang terdapat di dalam `HeapTupleHeaderData`!

### Level Medium
1. Buatlah tabel dengan sebuah kolom bertipe `BYTEA`. Masukkan data berukuran 1 KB, 3 KB, dan 50 KB. Gunakan fungsi `pg_relation_size()` dan tabel katalog `pg_class` untuk membuktikan pada ukuran data berapa PostgreSQL mulai mengalokasikan data ke dalam tabel TOAST terpisah.
2. Simulasikan skenario di mana HOT update gagal terjadi (*Zero HOT Updates*) meskipun kolom yang diupdate bukan kolom berindeks. Analisis mengapa kegagalan ini dapat terjadi!

### Level Hard
1. Buatlah SQL script yang memonitor *Tuple Visibility Horizon* secara dinamis. Script harus mengidentifikasi koneksi backend mana di `pg_stat_activity` yang memegang transaksi tertua yang menahan `xmin` horizon seluruh database, menghitung durasi transaksinya, serta mengestimasi volume dead tuples yang terakumulasi selama transaksi tersebut aktif.

---

## 14. Challenges

### Deskripsi Tantangan Kasus Nyata:
Anda ditunjuk sebagai Principal Data Engineer pada platform E-Commerce berskala nasional. Menjelang event Harbolnas 11.11, sistem inventori mengalami lonjakan beban penulisan mutasi stok sebesar 35.000 `UPDATE/detik` pada tabel `inventory_items` (berisi 5 juta SKU produk).

### Kondisi dan Kendala:
1. Setiap SKU memiliki indeks primer `sku_id` dan foreign key index `merchant_id`.
2. Saat simulasi load test, disk IOPS mencapai titik jenuh (100% saturation pada 10.000 IOPS disk pool).
3. Setelah berjalan 15 menit, ukuran tabel membengkak dari 1 GB menjadi 28 GB karena dead tuples gagal dibersihkan secepat laju transaksinya. Query pembacaan stok inventori mulai timeout (> 5 detik).
4. Penambahan kapasitas IOPS storage tidak diizinkan oleh manajemen karena batasan budget infrastruktur cloud.

### Tugas Desain Anda:
1. Rancang arsitektur penyimpanan dan skema mutasi stok baru tanpa mengubah sifat transaksional konsistensi data (Stok tidak boleh minus atau *oversell*).
2. Tentukan parameter konfigurasi level-tabel (storage parameter) dan konfigurasi engine instance (`postgresql.conf`) yang wajib diterapkan untuk memitigasi disk saturation dan bloat tersebut.
3. Berikan analisis justifikasi teknis mengapa rancangan arsitektur baru Anda dapat menurunkan amplifikasi penulisan disk hingga >70%!

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)
1. **Berapa ukuran default dari sebuah data page (block) pada PostgreSQL engine standard?**
   - A. 4 KB
   - B. 8 KB
   - C. 16 KB
   - D. 64 KB
2. **File transaksi WAL (*Write-Ahead Log*) secara default dipecah ke dalam segmen-segmen file berukuran:**
   - A. 8 MB
   - B. 16 MB
   - C. 64 MB
   - D. 1 GB
3. **Informasi mengenai status commit dari suatu transaksi (`COMMITTED`, `ABORTED`, `IN_PROGRESS`) secara internal dicatat di direktori:**
   - A. `pg_wal`
   - B. `pg_stat`
   - C. `pg_xact`
   - D. `base`
4. **Apa yang dilakukan oleh proses `VACUUM` standar (tanpa parameter `FULL`)?**
   - A. Mengembalikan ruang disk OS secara langsung dengan memotong (*truncating*) file tabel.
   - B. Menghapus dead tuples dan menandai ruangnya di internal page agar dapat dipakai kembali oleh tuple baru.
   - C. Menghapus tabel secara permanen.
   - D. Mengunci seluruh tabel dalam mode eksklusif.
5. **Algoritma kompresi data out-of-line TOAST default sebelum PostgreSQL versi 14 adalah:**
   - A. LZ4
   - B. Zstandard (zstd)
   - C. Snappy
   - D. PGLZ

### Bagian 2: Intermediate (5 Pertanyaan)
6. **Kapan kondisi Heap-Only Tuple (HOT) optimization DAPAT diaplikasikan oleh PostgreSQL engine?**
   - A. Setiap kali perintah `INSERT` dieksekusi.
   - B. Ketika perintah `UPDATE` tidak memodifikasi kolom berindeks dan page target masih memiliki free space yang cukup.
   - C. Ketika tabel sama sekali tidak memiliki indeks.
   - D. Saat `autovacuum` dijalankan dengan flag aggressive.
7. **Apa peran utama dari file control `global/pg_control` dalam PostgreSQL?**
   - A. Menyimpan password seluruh pengguna database.
   - B. Menyimpan checkpoint LSN terkini, state cluster (misal: in production, in shutdown), dan integritas pemulihan crash.
   - C. Menyimpan mapping tablespace fisik ke logical drive.
   - D. Mengatur alokasi dynamic shared memory per backend.
8. **Strategi penyimpanan TOAST apakah yang mengizinkan data dipindahkan out-of-line tetapi MENOLAK kompresi data?**
   - A. `PLAIN`
   - B. `EXTENDED`
   - C. `EXTERNAL`
   - D. `MAIN`
9. **Jika parameter `checkpoint_completion_target` diset ke 0.9 pada `checkpoint_timeout = 10min`, artinya:**
   - A. Checkpoint harus selesai dalam waktu 90 detik.
   - B. Checkpoint akan menyebarkan proses I/O write dirty pages selama rentang waktu 9 menit.
   - C. 90% dari RAM `shared_buffers` akan langsung dikosongkan.
   - D. Checkpoint hanya akan dieksekusi jika kapasitas storage terisi 90%.
10. **Berapa batas kapasitas transaksi unik yang dimungkinkan oleh representasi 32-bit Transaction ID sebelum terjadi ancaman Wraparound?**
    - A. ~100 juta transaksi
    - B. ~1 miliar transaksi
    - C. ~2.1 miliar (atau $2^{31}-1$) transaksi
    - D. ~4 triliun transaksi

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)
11. **Skenario A**: Sebuah node cluster PostgreSQL tiba-tiba mengalami lonjakan drastis pada I/O storage write. Metrik monitoring menunjukkan backend processes banyak mengalami wait event `SyncRep`. Apa akar penyebab struktural dari masalah ini?
    - A. Autovacuum crash loop.
    - B. Node replika sinkron (*synchronous standby*) mengalami network latency / lagging, sehingga master backend tertahan menunggu konfirmasi *flush* WAL dari standby sebelum mengembalikan status `COMMIT`.
    - C. Kapasitas memory `shared_buffers` habis.
    - D. Parameter `max_connections` terlampaui.

12. **Skenario B**: Tim DBA menjalankan query `VACUUM FULL` pada tabel transaksi utama sebesar 400 GB di tengah jam kerja operasional untuk mengurangi table bloat. Apa dampak langsung yang tak terhindarkan pada aplikasi produksi?
    - A. Tidak ada dampak karena PostgreSQL mendukung fully-concurrent online operations.
    - B. Seluruh query pembacaan (`SELECT`) dan penulisan (`INSERT`/`UPDATE`/`DELETE`) pada tabel tersebut akan mengalami *hang/blocking* total karena `VACUUM FULL` meminta `ACCESS EXCLUSIVE LOCK`.
    - C. Database otomatis failover ke standby node.
    - D. Seluruh file TOAST pada tabel tersebut akan corrupt.

13. **Skenario C**: Anda mengamati bahwa proses `autovacuum worker` secara konsisten memakan waktu 12 jam untuk menyelesaikan vacuum pada tabel audit sebesar 500 juta baris, dan tidak mampu mengimbangi laju pertumbuhan dead tuples. Penyesuaian konfigurasi spesifik mana yang paling tepat dan terarah untuk mempercepat kinerja pembersihan pada tabel tersebut tanpa mengganggu global instance?
    - A. Menurunkan nilai `shared_buffers` cluster.
    - B. Menjalankan `ALTER TABLE audit_table SET (autovacuum_vacuum_cost_limit = 5000, autovacuum_vacuum_cost_delay = 0);`
    - C. Mengubah storage engine tabel ke file unlogged.
    - D. Mengubah isolasi transaksi aplikasi ke `READ UNCOMMITTED`.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** (8 KB adalah ukuran baku data page default).
2. **B** (Ukuran default WAL segment file adalah 16 MB).
3. **C** (`pg_xact`, sebelumnya dikenal sebagai `pg_clog`, menyimpan status commit transaksi).
4. **B** (Standard vacuum tidak mengecilkan relasi ke OS, melainkan membersihkan page intern agar dapat dipakai ulang).
5. **D** (PGLZ adalah algoritma kompresi internal historis PostgreSQL).

#### Bagian 2: Intermediate
6. **B** (HOT mensyaratkan: tidak ada update kolom terindeks dan ruang page yang sama mencukupi).
7. **B** (`pg_control` adalah single-point-of-truth metadata cluster saat fase bootstrap recovery).
8. **C** (`EXTERNAL` memindahkan data out-of-line tanpa kompresi).
9. **B** (0.9 dari 10 menit = perataan I/O write tersebar selama 9 menit).
10. **C** (Integer 32-bit bertanda memberikan rentang komparasi sirkular ~2.1 miliar transaksi).

#### Bagian 3: Skenario Kasus Produksi
11. **B** (`SyncRep` mengindikasikan master menunggu replika synchronous merespons penulisan WAL).
12. **B** (`VACUUM FULL` mengambil lock paling restriktif `ACCESS EXCLUSIVE`, memblokir pembaca maupun penulis).
13. **B** (Menyesuaikan parameter cost-limit dan delay langsung pada level tabel target memberikan alokasi throughput I/O maksimal kepada worker yang menangani tabel tersebut).

---

## 16. Summary

1. **Storage Atomicity**: PostgreSQL menstrukturkan seluruh data dalam unit Page 8 KB berbasis *Slotted-Page Architecture*, di mana *Item Pointers* (`ItemId`) memetakan baris secara indirek ke dalam array tuple untuk menyerap variasi panjang record dan memfasilitasi defragmentasi in-page.
2. **MVCC Architecture**: Implementasi MVCC PostgreSQL adalah *append-only*. Mutasi update tidak meng-overwrite blok, melainkan membuat tuple baru. Keuntungan tanpa lock pembaca dibayar dengan timbulnya *dead tuples* yang mewajibkan maintenance berkala via Engine Autovacuum.
3. **Durability via WAL**: ACID Durability dipelihara melalui penulisan transaksi berurutan ke WAL sebelum dirty pages di-flush dari `shared_buffers`. Siklus checkpointing mendistribusikan beban penulisan dirty pages ke storage secara periodik tanpa memblokir backend client.
4. **Enterprise Scaling Rule**: Skalabilitas PostgreSQL pada throughput ekstrem bersandar pada tiga pilar utama:
   - Penggunaan connection pooler eksternal berkinerja tinggi (seperti PgBouncer) dalam mode transaksi.
   - Pemanfaatan HOT optimization (`fillfactor` terukur) untuk mengeliminasi Write Amplification pada B-Tree.
   - Re-tuning autovacuum secara agresif guna menangkal table bloat serta bencana sistemik *Transaction ID Wraparound*.