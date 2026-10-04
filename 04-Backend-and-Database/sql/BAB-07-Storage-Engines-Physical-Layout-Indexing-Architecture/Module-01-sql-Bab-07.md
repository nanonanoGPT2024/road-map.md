# Modul 07.01: Storage Engines, Physical Layout, & Indexing Architecture

---

## 01. IDENTITAS MODUL

*   **Track:** `Backend & Database Engineering`
*   **Kategori:** `04-Backend-and-Database`
*   **Topik:** `SQL Core Architecture & Internals`
*   **Modul:** `07.01 - Storage Engines, Physical Layout, & Indexing Architecture`
*   **Tingkat Kesulitan:** `Advanced / Principal Level`
*   **Estimasi Waktu Baca:** `45 Menit`
*   **Engine Fokus:** `PostgreSQL (Heap, TOAST, B-Tree, GiST, GIN, BRIN)` & `MySQL/InnoDB (Clustered Index, Redo/Undo Log, Doublewrite Buffer)`

---

## 02. LEARNING OBJECTIVES

1.  **Mendekonstruksi Physical Page Layout:** Menganalisis alokasi byte-level pada disk page/block (8KB PostgreSQL vs 16KB InnoDB), termasuk *page header*, *item pointers*, *tuple/row headers*, dan mekanika offset alignment.
2.  **Mengevaluasi Storage Engine Paradigms:** Membedakan arsitektur *Heap-organized table* (PostgreSQL) vs *Index-organized/Clustered table* (MySQL InnoDB), serta mekanika *Free Space Map (FSM)*, *Visibility Map (VM)*, dan *TOAST/Off-page Storage*.
3.  **Membedah Struktur Data Indexing:** Menganalisis cara kerja internal dari B+Tree (termasuk *page split*, *fillfactor*, dan *root-to-leaf traversal*), Hash Index, Generalized Inverted Index (GIN), Generalized Search Tree (GiST), dan Block Range Index (BRIN).
4.  **Mengoperasikan Low-Level Inspection:** Melakukan inspeksi fisik file data dan index page secara langsung menggunakan tools native seperti `pageinspect`, `pg_waldump`, `innodb_ruby`, dan hexdump engine.
5.  **Merancang Layout Fisik untuk Throughput Maksimal:** Mengonfigurasi parameter *fillfactor*, *table partitioning alignment*, dan strategi indexing gabungan guna meminimalkan I/O amplification, I/O wait, dan write amplification.

---

## 03. CONCEPT MAP DIAGRAM ASCII

```
+---------------------------------------------------------------------------------------------------+
|                                  PHYSICAL STORAGE ENGINE ARCHITECTURE                             |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    |                                                           |
                    v                                                           v
+---------------------------------------+                   +---------------------------------------+
|         PostgreSQL HEAP ENGINE        |                   |          MySQL INNODB ENGINE          |
+---------------------------------------+                   +---------------------------------------+
| * Unordered Tuples via CTID (Page,Slot)|                  | * Clustered Index (Primary Key B+Tree)|
| * Page Size: Default 8KB              |                   | * Page Size: Default 16KB             |
| * MVCC: In-page Row Versions (xmin/max)|                  | * MVCC: Undo Logs & Rollback Pointers |
| * Off-page: TOAST (>2KB Compression)  |                   | * Off-page: Overflow/BLOB Pages (>8KB)|
| * Auxiliary: FSM, VM, WAL             |                   | * Auxiliary: Doublewrite Buffer, Redo |
+---------------------------------------+                   +---------------------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                    ACCESS METHODS & INDEX LAYOUT                                  |
+---------------------------------------------------------------------------------------------------+
|  [B+Tree]           [GIN (Inverted)]       [GiST (Tree-based)]   [BRIN (Range)]   [Hash Index]    |
|  - Balanced Search  - Fulltext / JSONB     - Spatial / Geometric - Monotonic IDs  - O(1) Equality |
|  - Leaf Linked List - Multi-key to Heap    - Hierarchical Data   - Min/Max Pages  - Bucket/Chains |
|  - Clustered (PK)   - Posting List/Tree    - R-Tree properties   - Small Footprint- No Range Scan |
+---------------------------------------------------------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                     HARDWARE & OS INTERFACE LAYER                                 |
+---------------------------------------------------------------------------------------------------+
|  File System Page (4KB) <---> OS Buffer Cache <---> Direct I/O / O_DIRECT <---> NVMe Block Layer |
+---------------------------------------------------------------------------------------------------+
```

---

## 04. MENGAPA RELEVAN

Memahami layer logis SQL (seperti relasi, filter, dan join) saja tidak cukup ketika sistem database mencapai skala gigabyte-per-detik atau terabyte data aktif. Perbedaan antara kueri berdurasi 2 milidetik vs 20 detik sering kali ditentukan oleh layout fisik data di atas disk block dan bagaimana pointer index traversing dijalankan.

### Implikasi Engineering:
*   **I/O Amplification Mitigation:** Mengambil satu kolom berukuran 4 byte dari baris tanpa index terarah dapat memaksa pembacaan 8KB data page dari NVMe ke memori. Mengabaikan physical layout berujung pada exhaust resource I/O bandwidth.
*   **Write Amplification & Bloat:** Pada engine berbasis Heap (PostgreSQL), setiap mutasi `UPDATE` menghasilkan baris versi baru (tuple insertion). Tanpa pemahaman HOT (*Heap-Only Tuples*), modifikasi data akan menyebabkan page fragmentation masif dan keharusan reorganisasi B-Tree index berulang kali.
*   **Hardware Alignment:** Pemilihan storage engine menentukan bagaimana thread mengeksekusi fsync, flush buffer pool, dan mengontrol alignment block boundary file system (4KB) dengan block boundary database (8KB/16KB), yang secara signifikan menentukan rasio Write-Checkpointed Throughput.

---

## 05. ANATOMI KONSEP INTI

### 1. PostgreSQL 8KB Page Anatomy (Heap Layout)

Setiap relasi (tabel) pada PostgreSQL disimpan dalam file segment 1GB (bila lebih, dipecah menjadi `.1`, `.2`, dst.) yang tersusun atas page berukuran default 8192 bytes.

```
+-----------------------------------------------------------------------+
| PageHeaderData (24 bytes)                                             |
|  - pd_lsn (8B)    : LSN WAL pointer untuk write sequence tracking     |
|  - pd_checksum(2B): Verifikasi integritas page                        |
|  - pd_flags (2B)  : Status page (misal: PD_HAS_FREE_LINES)            |
|  - pd_lower (2B)  : Byte offset batas akhir Item Pointer (Line Pointer)|
|  - pd_upper (2B)  : Byte offset batas awal Unallocated Raw Tuples     |
|  - pd_special (2B): Offset untuk index-specific data                  |
+-----------------------------------------------------------------------+
| ItemIdData Array (Line Pointers) [lp_off(15b), lp_flags(2b), lp_len(15b)]
|  [Item Pointer 1 (4 bytes)] -> Menunjuk ke Tuple 1 di bagian bawah     |
|  [Item Pointer 2 (4 bytes)] -> Menunjuk ke Tuple 2                    |
|  [Item Pointer 3 (4 bytes)]                                           |
+-----------------------------------------------------------------------+
|                        <=== FREE SPACE HOLE ===>                      |
| (pd_lower bergerak turun ke bawah, pd_upper bergerak naik ke atas)    |
+-----------------------------------------------------------------------+
| Tuple 3 Data (HeapTupleHeader + Raw Bytes)                           |
+-----------------------------------------------------------------------+
| Tuple 2 Data                                                          |
+-----------------------------------------------------------------------+
| Tuple 1 Data                                                          |
+-----------------------------------------------------------------------+
| Special Space (Hanya digunakan pada tipe index tertentu, mis: B-tree) |
+-----------------------------------------------------------------------+
```

*   **Tuple Header (HeapTupleHeaderData - 23 bytes):**
    *   `t_xmin`: Transaction ID pembuat tuple.
    *   `t_xmax`: Transaction ID penghapus/updater tuple (0 jika aktif).
    *   `t_cid`: Command Identifier di dalam transaksi.
    *   `t_ctid`: Item pointer `(block_number, offset)` yang menunjuk ke lokasi fisik baris ini (atau versi terbaru baris ini jika telah ter-update).
    *   `t_infomask`: Bitmask status commit/abort transaksi (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_INVALID`, dll).
    *   `t_hoff`: User data offset (header padding alignment).

### 2. MySQL InnoDB 16KB Page Anatomy (Clustered Index Layout)

InnoDB mengimplementasikan arsitektur *Index-Organized Tables* (IOT). Tabel secara fisik **adalah** Primary Key B+Tree itu sendiri.

```
+-----------------------------------------------------------------------+
| FIL Header (38 bytes)                                                 |
|  - FIL_PAGE_SPACE_OR_CHKSUM, FIL_PAGE_OFFSET (Page No), Page Types    |
|  - FIL_PAGE_PREV, FIL_PAGE_NEXT (Pointer Double-Linked List B+Tree)   |
+-----------------------------------------------------------------------+
| Page Header (56 bytes)                                                |
|  - PAGE_N_DIR_SLOTS, PAGE_HEAP_TOP, PAGE_N_RECS, PAGE_LAST_INSERT     |
+-----------------------------------------------------------------------+
| Infimum & Supremum Records (26 bytes)                                 |
|  - Boundary virtual minimum dan maximum records di dalam page         |
+-----------------------------------------------------------------------+
| User Records (Clustered Index Rows)                                   |
|  - Compact Record Header (5 bytes: delete_mark, next_record_offset)    |
|  - System Hidden Columns: DB_TRX_ID (6B), DB_ROLL_PTR (7B)            |
|  - Primary Key Columns + Payload User Columns (inline atau pointer)   |
+-----------------------------------------------------------------------+
| Free Space (Unallocated bytes)                                        |
+-----------------------------------------------------------------------+
| Page Directory (Sparse slot array, tiap slot menunjuk per 4-8 record) |
+-----------------------------------------------------------------------+
| FIL Trailer (8 bytes - Checksum validation & LSN tracking)            |
+-----------------------------------------------------------------------+
```

### 3. Komparasi Arsitektur Indexing

| Aspek | B+Tree | GIN (Generalized Inverted) | GiST (Search Tree) | BRIN (Block Range Index) |
| :--- | :--- | :--- | :--- | :--- |
| **Pola Akses Ideal** | Kesetaraan (`=`) & Rentang (`<`, `BETWEEN`) | Array containment, Fulltext, JSONB key search | Geometri (GIS), Rentang waktu overlapping | Data terurut fisik secara alami (Append-only/Timestamp) |
| **Struktur Internal** | Balanced multi-way search tree berurutan | Posting list / B-Tree of B-Trees mapping keys to heap-pointers | Balanced tree of predicates/bounding boxes | Rangkuman metadata min/max per blok (mis. 128 blok) |
| **Write Overhead** | Sedang (Node splits, WAL lock) | Sangat Tinggi (Banyak index entry per 1 baris JSON/Array) | Tinggi (Komputasi bounding-box & penyesuaian parent) | Sangat Rendah (Update min/max saat block batas terlewati) |
| **Ukuran Index** | Standar (Proporsional terhadap baris) | Besar hingga Sangat Besar | Sedang | Sangat Kecil (Kilobytes vs Gigabytes) |

---

## 06. PANDUAN IMPLEMENTASI STEP-BY-STEP

Berikut adalah konfigurasi, inspeksi byte, dan setup layout index PostgreSQL menggunakan extension internal `pageinspect`.

### Step 1: Aktivasi Extensi Page Inspection

Masuk ke instance PostgreSQL dengan hak akses superuser:

```sql
CREATE EXTENSION IF NOT EXISTS pageinspect;
CREATE EXTENSION IF NOT EXISTS pgstattuple;
```

### Step 2: Buat Tabel Khusus Uji Coba Layout Fisik

Kita tentukan `fillfactor` sebesar 70% untuk memberikan ruang cadangan (headroom) bagi update in-place (Heap-Only Tuples - HOT).

```sql
DROP TABLE IF EXISTS storage_test;

CREATE TABLE storage_test (
    id SERIAL PRIMARY KEY,
    identifier UUID NOT NULL,
    payload TEXT,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
) WITH (fillfactor = 70);

-- Insert 1000 baris sintetis
INSERT INTO storage_test (identifier, payload, created_at)
SELECT 
    gen_random_uuid(),
    'Payload data block segment: ' || repeat('A', 150),
    clock_timestamp()
FROM generate_series(1, 1000);
```

### Step 3: Inspeksi Level Block/Page Header

Mari telusuri Block 0 (Page pertama) dari tabel tersebut:

```sql
SELECT 
    lsn, 
    checksum, 
    flags, 
    lower, 
    upper, 
    special, 
    pagesize
FROM page_header(get_raw_page('storage_test', 0));
```

### Step 4: Inspeksi Individual Item Pointer (Line Pointer) & Tuple Header

```sql
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len,
    t_xmin, 
    t_xmax, 
    t_ctid, 
    t_data
FROM heap_page_items(get_raw_page('storage_test', 0))
LIMIT 5;
```

*Penjelasan:*
*   `lp`: Index line pointer (1, 2, 3...)
*   `lp_off`: Lokasi byte offset absolut dari awal page menuju data tuple.
*   `lp_flags`: `1` (Used/Normal), `2` (HOT Redirect), `0` (Unused).
*   `t_ctid`: Koordinat fisik baris: `(0, 1)` berarti block 0 slot 1.

---

## 07. CONTOH KASUS SEDERHANA

### Pembuktian Heap-Only Tuple (HOT) Optimization

Ketika sebuah baris diupdate di PostgreSQL, bila kolom yang diupdate tidak memiliki index dan page memiliki *free space* yang cukup, database menghindari pembuatan index pointer baru di B-Tree root. Baris baru disimpan di page yang sama, dan line pointer lama langsung menunjuk ke line pointer baru (*HOT Chain*).

```sql
-- 1. Cek koordinat awal record ID = 1
SELECT ctid, id, payload FROM storage_test WHERE id = 1;
-- Output ctid: (0, 1)

-- 2. Update kolom non-indexed
UPDATE storage_test 
SET payload = 'Updated Payload without changing index' 
WHERE id = 1;

-- 3. Cek kembali koordinat ctid
SELECT ctid, id, payload FROM storage_test WHERE id = 1;
-- Output ctid sekarang: (0, N) di mana N adalah slot baru di block 0

-- 4. Verifikasi Line Pointer Chaining melalui pageinspect
SELECT lp, lp_off, lp_flags, lp_len, t_ctid 
FROM heap_page_items(get_raw_page('storage_test', 0))
WHERE lp IN (1, (SELECT substring(ctid::text from '\d+,(\d+)')::int FROM storage_test WHERE id = 1));
```

*Hasil Pengamatan:* `lp=1` sekarang memiliki `lp_flags=2` (Redirect) yang menunjuk ke slot tuple hasil update, tanpa memicu overhead modifikasi pada index B-tree primer.

---

## 08. IMPLEMENTASI PRODUCTION-GRADE LENGKAP KODE

Berikut adalah skrip DDL/DML lengkap yang mengimplementasikan arsitektur partisi berorientasi waktu, layout index multi-metode (B-Tree, GIN, BRIN), pengontrolan TOAST storage, dan script monitoring bloat fisik.

```sql
-- ============================================================================
-- SCRIPT PRODUKSI: ADVANCED STORAGE & PHYSICAL LAYOUT ARCHITECTURE
-- Engine Target: PostgreSQL 14+
-- ============================================================================

BEGIN;

-- 1. Setup Skema Khusus
CREATE SCHEMA IF NOT EXISTS telemetry_engine;
SET search_path TO telemetry_engine, public;

-- 2. Master Table dengan Partisi Range
CREATE TABLE device_telemetry (
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_uuid UUID NOT NULL,
    device_type VARCHAR(32) NOT NULL,
    metadata JSONB,
    sensor_readings JSONB,
    recorded_at TIMESTAMPTZ NOT NULL,
    large_diagnostic_log TEXT,
    PRIMARY KEY (recorded_at, reading_id)
) PARTITION BY RANGE (recorded_at);

-- 3. Konfigurasi Physical Storage Attribute (TOAST Strategy Optimization)
-- Opsi: PLAIN (no toast/compression), EXTENDED (compress & out of line), 
-- EXTERNAL (out of line, no compress), MAIN (compress inline preferred)
ALTER TABLE device_telemetry 
    ALTER COLUMN large_diagnostic_log SET STORAGE EXTENDED;

ALTER TABLE device_telemetry 
    ALTER COLUMN metadata SET STORAGE MAIN;

-- 4. Pembuatan Partisi Bulanan dengan Fillfactor Optimal
-- Fillfactor 85 memberikan ruang 15% untuk in-place MVCC update tanpa fragmentasi block
CREATE TABLE telemetry_y2026m01 PARTITION OF device_telemetry
    FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00')
    WITH (fillfactor = 85, autovacuum_vacuum_scale_factor = 0.05);

CREATE TABLE telemetry_y2026m02 PARTITION OF device_telemetry
    FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00')
    WITH (fillfactor = 85, autovacuum_vacuum_scale_factor = 0.05);

-- 5. Penerapan Multi-Paradigm Physical Indexing

-- A. B-Tree Clustered Index Candidate (Forward/Backward Traversal)
CREATE INDEX idx_telemetry_2026m01_dev_time 
ON telemetry_y2026m01 USING btree (device_uuid, recorded_at DESC);

-- B. GIN Index (Generalized Inverted Index) dengan Fastupdate untuk Ingestion JSONB
-- Menggunakan jsonb_path_ops untuk efisiensi ruang disk (hanya simpan hash of key-value paths)
CREATE INDEX idx_telemetry_2026m01_sensor_gin 
ON telemetry_y2026m01 USING gin (sensor_readings jsonb_path_ops)
WITH (fastupdate = on, gin_pending_list_limit = '4MB');

-- C. BRIN Index (Block Range Index) untuk Data Append-Only Monotonik
-- Rentang 64 physical blocks (512KB) per satu indexing summary
CREATE INDEX idx_telemetry_2026m01_brin_time 
ON telemetry_y2026m01 USING brin (recorded_at) 
WITH (pages_per_range = 64);

COMMIT;

-- ============================================================================
-- 6. Store Procedure: Diagnostic Tool untuk Page Fragmentation & Physical Bloat
-- ============================================================================

CREATE OR REPLACE FUNCTION get_table_physical_bloat(p_target_table TEXT)
RETURNS TABLE (
    table_name TEXT,
    total_size TEXT,
    table_size TEXT,
    index_size TEXT,
    toast_size TEXT,
    live_tuple_ratio NUMERIC,
    dead_tuple_ratio NUMERIC,
    free_space_bytes BIGINT
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p_target_table AS table_name,
        pg_size_pretty(pg_total_relation_size(p_target_table::regclass)) AS total_size,
        pg_size_pretty(pg_relation_size(p_target_table::regclass, 'main')) AS table_size,
        pg_size_pretty(pg_indexes_size(p_target_table::regclass)) AS index_size,
        pg_size_pretty(pg_relation_size(p_target_table::regclass, 'toast')) AS toast_size,
        ROUND((st.tuple_percent)::numeric, 2) AS live_tuple_ratio,
        ROUND((st.dead_tuple_percent)::numeric, 2) AS dead_tuple_ratio,
        st.free_space AS free_space_bytes
    FROM pgstattuple(p_target_table) AS st;
END;
$$;
```

---

## 09. DIAGRAM ALUR KERJA ASCII

### B+Tree Root-to-Leaf Traversal & Page Split Mechanics

```
                         +-----------------------------------+
                         |         ROOT PAGE (Level 2)       |
                         |  [Key: 100]  |  [Key: 200]        |
                         |  Ptr: Page 1 |  Ptr: Page 2       |
                         +-----------------------------------+
                                   /             \
                   +--------------+               +--------------+
                   |                                             |
                   v                                             v
    +-----------------------------+               +-----------------------------+
    |    INTERNAL PAGE (Level 1)  |               |    INTERNAL PAGE (Level 1)  |
    |  [Key: 30]   | [Key: 70]    |               |  [Key: 130]  | [Key: 170]   |
    |  Ptr: P_L1   | Ptr: P_L2    |               |  Ptr: P_L3   | Ptr: P_L4    |
    +-----------------------------+               +-----------------------------+
             /           \                                /           \
            /             \                              /             \
           v               v                            v               v
    +-------------+ +-------------+              +-------------+ +-------------+
    | LEAF PAGE 1 | | LEAF PAGE 2 | <==D-Link==> | LEAF PAGE 3 | | LEAF PAGE 4 |
    | [K:10 -> Ptr]| | [K:40 -> Ptr]|              | [K:110->Ptr]| | [K:180->Ptr]|
    | [K:20 -> Ptr]| | [K:50 -> Ptr]|              | [K:120->Ptr]| | [K:190->Ptr]|
    +-------------+ +-------------+              +-------------+ +-------------+
           |
           | (Insert K:25 on Full Leaf Page 1 -> Triggers Page Split)
           v
    +-------------------------------------------------------------------------+
    | PAGE SPLIT PROCESS:                                                     |
    | 1. Allocate new Page 1B.                                                |
    | 2. Pindahkan 50% data Leaf 1 ke Leaf 1B.                                |
    | 3. Pasang tuple K:25 ke slot yang sesuai.                               |
    | 4. Update pointer Double-Linked List: Leaf 1 <-> Leaf 1B <-> Leaf 2.     |
    | 5. Eskskalasikan kunci pemisah (Separator Key) ke Internal Page Level 1.|
    +-------------------------------------------------------------------------+
```

---

## 10. ANALISIS TRADE-OFFS

### Clustered Index (InnoDB) vs Heap Organization (PostgreSQL)

```
+-----------------------------------------------------------------------------------+
| DIMENSI              | HEAP ENGINE (PostgreSQL)     | CLUSTERED ENGINE (InnoDB)   |
+-----------------------------------------------------------------------------------+
| Primary Key Lookup   | Butuh 2 Langkah:             | 1 Langkah Langsung:         |
|                      | B-Tree Search -> CTID Lookup | B-Tree Search langsung      |
|                      | ke Block Heap.               | menemukan seluruh Payload.  |
+-----------------------------------------------------------------------------------+
| Secondary Index Cost | Ringan: Secondary index      | Berat: Secondary index      |
|                      | menunjuk langsung ke (Page,  | menyimpan salinan PK.       |
|                      | Offset) CTID pada Heap.      | Terjadi "Double B-Tree Seek"|
+-----------------------------------------------------------------------------------+
| Write / Insert Speed | Sangat Cepat: Baris cukup    | Lebih Lambat: Harus mencari |
|                      | diletakkan di free page mana | posisi leaf node yang sesuai|
|                      | saja yang tersedia (FSM).    | dengan urutan PK B-Tree.    |
+-----------------------------------------------------------------------------------+
| Tuple Update Impact  | Menghasilkan baris baru      | Update in-place pada page   |
|                      | (MVCC Bloat), perlu VACUUM   | yang sama via Undo Log,     |
|                      | kecuali tertolong HOT.       | tanpa mengubah physical PK. |
+-----------------------------------------------------------------------------------+
| Storage Density      | Rendah (Overhead Header 23B  | Tinggi (Header kompak 5B,   |
|                      | + dead tuples fragmentation) | fragmentasi mitigated PK)   |
+-----------------------------------------------------------------------------------+
```

---

## 11. BEST PRACTICES & ANTIPATTERNS

### Best Practices
1.  **Alignment Padding Awareness:** Rancang skema SQL berurutan dari tipe data berukuran byte terbesar ke terkecil (`BIGINT`, `TIMESTAMPTZ` -> 8 bytes; `INT` -> 4 bytes; `SMALLINT` -> 2 bytes; `BOOLEAN` -> 1 byte). Ini mencegah CPU compiler alignment padding membuang byte kosong di disk.
2.  **Explicit Fillfactor Configuration:** Atur `fillfactor = 75-85` untuk tabel dengan rate `UPDATE` sangat tinggi. Ruang kosong 15-25% memungkinkan terjadinya HOT update dan mengeliminasi write amplification pada secondary index.
3.  **Use BRIN for Append-Only Time-Series:** Gunakan BRIN index pada tabel time-series masif. BRIN hanya memakan space fraksi 0.05% dari ukuran tabel asli dibandingkan B-Tree yang dapat memakan 20-40% dari total size relasi.

### Antipatterns
1.  **Indiscriminate Indexing of High Cardinality JSONB via Standard GIN:** Melakukan indexing GIN default (`jsonb_ops`) pada kolom JSON berukuran besar dengan variabilitas key tak terbatas. Gunakan `jsonb_path_ops` atau buat expression index pada path spesifik: `CREATE INDEX idx_sp ON tbl ((json_col->>'key'));`.
2.  **Using Random UUIDv4 as Primary Key on Clustered Index (InnoDB):** Menyebabkan fragmentasi page B-Tree ekstrem dan random disk I/O konstan akibat *page split* tak terkendali di sembarang leaf. Gunakan sequential UUID (UUIDv7) atau auto-incrementing identity.
3.  **Ignoring Index Page Fillfactor on Massive Bulk Updates:** Membiarkan fillfactor index 100% pada index yang sering mengalami split, yang memaksa alokasi page baru di segment disk yang tidak contiguous.

---

## 12. SECURITY HARDENING

1.  **Data-at-Rest Encryption Page-Level Alignment:** Ketika menggunakan TDE (*Transparent Data Encryption*) atau filesystem-level encryption (seperti LUKS), pastikan *cipher block chaining* (CBC) atau XTS cipher suite disesuaikan dengan 4KB filesystem sector alignment guna menghindari *misaligned I/O performance penalty*.
2.  **Secure TOAST Out-of-Line Isolation:** Jika menyimpan sensitive encrypted tokens di table, ubah storage strategy menjadi `SET STORAGE EXTERNAL` untuk mematikan kompresi. Teknik kompresi data terenkripsi membuka celah *side-channel attacks* (seperti CRIME/BREACH variants) melalui panjang ukuran payload terkompresi.
3.  **Zeroing Free Space / Anti-Forensic Scrubbing:** Pada PostgreSQL, dead tuple masih berada di physical disk block sampai ditimpa oleh vacuum/insert baru. Untuk level keamanan ketat (PCI-DSS/HIPAA), gunakan modul ekstensi `pgcrypto` untuk cryptographic shredding atau aktifkan disk page zeroing mechanism.

---

## 13. OBSERVABILITAS & DEBUGGING

### Script Diagnostik: Membongkar B-Tree Internal Metadata via SQL

```sql
-- Dapatkan statistik struktur halaman Leaf & Internal dari index B-Tree
SELECT 
    level,
    leaf_pages,
    internal_pages,
    empty_pages,
    deleted_pages,
    avg_leaf_density
FROM bt_page_stats('idx_telemetry_2026m01_dev_time', 1);

-- Trace Root Page Stats & Depth Level
SELECT 
    root_blkno,
    level,
    fastroot,
    fastlevel
FROM bt_metap('idx_telemetry_2026m01_dev_time');

-- Dapatkan perbandingan ukuran index vs main table
SELECT 
    c.relname AS object_name,
    c.relkind AS object_type,
    pg_size_pretty(pg_relation_size(c.oid)) AS physical_size,
    reltuples AS approximate_rows
FROM pg_class c
WHERE c.relname LIKE '%telemetry%'
ORDER BY pg_relation_size(c.oid) DESC;
```

---

## 14. BENCHMARKING & PERFORMANCE

Metodologi pengujian dampak `fillfactor` terhadap throughput mutasi database melalui `pgbench`.

### 1. Inisialisasi Skenario Uji

Buat skrip pengujian kustom `hot_benchmark.sql`:
```sql
\set id random(1, 100000)
UPDATE storage_test_bench 
SET counter = counter + 1 
WHERE id = :id;
```

### 2. Jalankan Pengujian Baseline vs Optimized

```bash
# Tabel Baseline: Fillfactor = 100 (Default)
psql -d benchmark_db -c "CREATE TABLE storage_test_bench (id INT PRIMARY KEY, counter INT, payload TEXT) WITH (fillfactor=100);"
psql -d benchmark_db -c "INSERT INTO storage_test_bench SELECT g, 0, repeat('X', 200) FROM generate_series(1, 100000) g;"
psql -d benchmark_db -c "CREATE INDEX idx_bench_counter ON storage_test_bench(counter);"

# Benchmark Baseline Run
pgbench -c 16 -j 4 -T 60 -f hot_benchmark.sql benchmark_db > result_fillfactor_100.log

# Tabel Optimized: Fillfactor = 75 (HOT-friendly)
psql -d benchmark_db -c "DROP TABLE storage_test_bench;"
psql -d benchmark_db -c "CREATE TABLE storage_test_bench (id INT PRIMARY KEY, counter INT, payload TEXT) WITH (fillfactor=75);"
psql -d benchmark_db -c "INSERT INTO storage_test_bench SELECT g, 0, repeat('X', 200) FROM generate_series(1, 100000) g;"
psql -d benchmark_db -c "CREATE INDEX idx_bench_counter ON storage_test_bench(counter);"

# Benchmark Optimized Run
pgbench -c 16 -j 4 -T 60 -f hot_benchmark.sql benchmark_db > result_fillfactor_75.log
```

### Hasil Metrik Performa (Data Representatif)

| Metrik | Fillfactor = 100 | Fillfactor = 75 | Delta Efisiensi |
| :--- | :--- | :--- | :--- |
| **Throughput (TPS)** | 3,420 TPS | 8,950 TPS | **+161.6% (2.6x)** |
| **Write Amplification (WAL Generated)**| 4.2 GB / min | 1.1 GB / min | **-73.8%** |
| **Buffer Cache Hit Ratio** | 89.2% | 99.4% | **+10.2%** |
| **Index Page Splits Count** | 43,120 events | 110 events | **-99.7%** |

---

## 15. HANDS-ON LAB MINI-PROJECT

### Judul: Membangun Storage Layout Analitik Berkinerja Tinggi pada PostgreSQL

### Objektif:
Membuat arsitektur fisik tabel yang mampu menampung 500.000 log event dengan efisiensi disk size di bawah 60MB (dibandingkan struktur unoptimized yang memakan ~250MB), sambil mempertahankan query scan sub-5ms.

### Instruksi Lab:

```sql
-- 1. Setup Skema Unoptimized (Control Group)
CREATE TABLE logs_unoptimized (
    id UUID,
    severity VARCHAR(10),
    service_name VARCHAR(100),
    data JSONB,
    created_at TIMESTAMPTZ
);

-- Buat Index Konvensional B-Tree di Semua Kolom
CREATE INDEX idx_unopt_id ON logs_unoptimized(id);
CREATE INDEX idx_unopt_created ON logs_unoptimized(created_at);
CREATE INDEX idx_unopt_data ON logs_unoptimized USING gin(data);

-- 2. Setup Skema Optimized (Physical Architecture Applied)
CREATE TABLE logs_optimized (
    created_at TIMESTAMPTZ NOT NULL,
    id UUID NOT NULL,
    service_name VARCHAR(64) NOT NULL,
    severity VARCHAR(8) NOT NULL,
    data JSONB NOT NULL
) WITH (fillfactor = 90);

-- Terapkan Structural BRIN & Path-Ops GIN
CREATE INDEX idx_opt_created_brin ON logs_optimized USING brin(created_at) WITH (pages_per_range = 32);
CREATE INDEX idx_opt_data_path ON logs_optimized USING gin(data jsonb_path_ops);

-- 3. Populate Dataset (500,000 Rows)
INSERT INTO logs_unoptimized
SELECT 
    gen_random_uuid(),
    (ARRAY['INFO', 'WARN', 'ERROR', 'FATAL'])[floor(random()*4)+1],
    'payment-service-cluster-node-' || (floor(random()*10)+1)::text,
    jsonb_build_object('user_id', floor(random()*1000000), 'ip', '192.168.1.1', 'action', 'AUTH_ATTEMPT'),
    ts
FROM generate_series(
    '2026-01-01 00:00:00'::timestamptz, 
    '2026-01-06 19:46:39'::timestamptz, 
    '1 second'::interval
) AS ts;

-- Copy exact data ke tabel optimized
INSERT INTO logs_optimized SELECT created_at, id, service_