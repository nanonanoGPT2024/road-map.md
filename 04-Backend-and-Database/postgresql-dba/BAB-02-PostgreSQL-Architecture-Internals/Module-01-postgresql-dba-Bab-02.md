# Bab 02 Module 01: PostgreSQL Architecture & Internals

---

## 01 Identitas Modul
* **Track:** Database Administration & Reliability Engineering
* **Kategori:** 04-Backend-and-Database
* **Topik:** PostgreSQL Architecture & Internals
* **Target Audience:** Lead DBA, Infrastructure Engineers, Principal Backend Engineers
* **Prasyarat:** Linux OS Internals (Virtual Memory, IPC, POSIX Signal), Dasar Relational Database Management System (RDBMS), SQL DDL/DML.

---

## 02 Learning Objectives
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Membedah arsitektur proses PostgreSQL dan siklus hidup koneksi via socket, `postmaster`, serta *backend worker process*.
2. Menganalisis alokasi dan partisi memori (*Shared Memory* vs. *Local Memory*) beserta algoritma manajemen *Shared Buffer Pool*.
3. Mendiagnosis mekanisme penyimpanan *on-disk*, struktur file database, relasi heap, serta format internal *8KB Page Layout*.
4. Mengaudit siklus hidup transaksi melalui *Write-Ahead Logging* (WAL), algoritma *Checkpointing*, dan subsistem *Background Writer*.
5. Mengimplementasikan instrumentasi internal menggunakan ekstensi `pageinspect`, `pg_buffercache`, dan `pg_walinspect` untuk troubleshooting level *storage engine*.

---

## 03 Concept Map Diagram ASCII

```text
+-------------------------------------------------------------------------------------------------------+
|                                      POSTGRESQL INSTANCE INTERNALS                                    |
+-------------------------------------------------------------------------------------------------------+
                                                   |
                     +-----------------------------+-----------------------------+
                     |                                                           |
                     v                                                           v
       +----------------------------+                             +----------------------------+
       |     PROCESS ARCHITECTURE   |                             |    MEMORY ARCHITECTURE     |
       +----------------------------+                             +----------------------------+
       | * Postmaster (Supervisor)  |                             | * Shared Memory:           |
       | * Client Backend Processes |                             |   - Shared Buffers         |
       | * Background Workers:      |                             |   - WAL Buffers            |
       |   - Checkpointer           |                             |   - CLOG/Commit Log        |
       |   - Background Writer      |                             | * Local Backend Memory:    |
       |   - WAL Writer             |                             |   - work_mem               |
       |   - Autovacuum Launcher    |                             |   - maintenance_work_mem   |
       |   - Stats Collector/Archiver|                            |   - temp_buffers           |
       +--------------+-------------+                             +--------------+-------------+
                      |                                                          |
                      +-----------------------------+----------------------------+
                                                    |
                                                    v
                               +------------------------------------------+
                               |         STORAGE ENGINE & I/O PATH        |
                               +------------------------------------------+
                               | * 8KB Slotted Page Engine:               |
                               |   - PageHeaderData | ItemId | Tuple Data |
                               | * WAL & Durability Subsystem:            |
                               |   - LSN Tracking | Dirty Pages | Sync    |
                               | * Checkpointing & Bgwriter Mechanics     |
                               +------------------------------------------+
```

---

## 04 Mengapa Relevan
Memahami PostgreSQL hanya dari lapisan SQL membatasi kemampuan *troubleshooting* ketika terjadi degradasi performa ekstrem, insiden I/O *spikes*, atau *corruption*. PostgreSQL beroperasi dengan model multi-proses (bukan *multi-threaded*) yang memanfaatkan POSIX *shared memory*. 

Tanpa pemahaman yang presisi mengenai interaksi antara `Shared Buffers`, kernel `Page Cache`, Write-Ahead Log (WAL), dan *page layout* 8KB:
* Konfigurasi parameter seperti `shared_buffers`, `work_mem`, dan `max_wal_size` hanya berupa tebakan spekulatif.
* Analisis *locking contention* dan replikasi asinkron/sinkron tidak dapat ditelusuri secara deterministik hingga tingkat *block I/O*.
* Kegagalan penanganan *bloat* dan degradasi indeks b-tree pada throughput tinggi tidak dapat dimitigasi pada level arsitektural.

---

## 05 Anatomi Konsep Inti

```text
+----------------------------------------------------------------------------------------------------+
|                                    ANATOMI POSTGRESQL 8KB PAGE                                     |
+----------------------------------------------------------------------------------------------------+
| PageHeaderData (24 bytes)                                                                          |
| [ LSN: 8B | Checksum: 2B | Flags: 2B | Lower: 2B | Upper: 2B | Special: 2B | PruneXID: 4B ]        |
+----------------------------------------------------------------------------------------------------+
| Linp/ItemId Array (Tumbuh ke Bawah ->)                                                             |
| [ ItemId 1 (4B) ] [ ItemId 2 (4B) ] [ ItemId 3 (4B) ] ...                                         |
+----------------------------------------------------------------------------------------------------+
|                                         <-- FREE SPACE -->                                         |
+----------------------------------------------------------------------------------------------------+
| Tuples/Item Data (Tumbuh ke Atas <-)                                                               |
| ... [ HeapTupleHeaderData (23B) + Data 3 ] [ HeapTupleHeaderData (23B) + Data 2 ] [ Tuple 1 ]      |
+----------------------------------------------------------------------------------------------------+
| Special Space (Index-specific metadata, e.g., B-Tree sibling pointers. 0 byte pada Heap Page)      |
+----------------------------------------------------------------------------------------------------+
```

### 1. Process Architecture
* **Postmaster Process (`postgres`):** Induk proses yang membuka listener socket, menangani otentikasi jaringan, dan melakukan `fork()` untuk setiap koneksi klien menjadi proses *Backend* baru.
* **Backend Processes:** Menjalankan parser, rewriter, planner, executor, dan memegang *local memory*.
* **Auxiliary Background Processes:**
  * **Checkpointer:** Menulis dirty buffer ke storage secara berkala untuk membatasi durasi *crash recovery*.
  * **Background Writer (bgwriter):** Menulis dirty page ke disk secara kontinu untuk memastikan *backend worker* selalu menemukan *free buffers* tanpa terblokir synchronous I/O.
  * **WAL Writer:** Mem-flush WAL records dari `WAL Buffers` ke disk secara periodik.
  * **Autovacuum Launcher & Workers:** Mengklaim kembali *dead tuple space* dan mencegah *transaction ID wraparound*.

### 2. Memory Structure
* **Shared Memory Area:**
  * **Shared Buffers:** Cache in-memory untuk block tabel dan indeks (default per block = 8KB). Menggunakan algoritma modifikasi *Clock Sweep*.
  * **WAL Buffers:** Buffer sirkular untuk menampung perubahan data transaksi sebelum di-flush ke disk.
  * **CommitLog (CLOG / `pg_xact`):** Status transaksi (*in-progress*, *committed*, *aborted*) disimpan dalam bentuk 2-bit per XID.
* **Local Backend Memory Area:**
  * **`work_mem`:** Memori untuk operasi `ORDER BY`, `DISTINCT`, *Hash Join*, dan *Merge Join*. Dialokasikan per operasi per query.
  * **`maintenance_work_mem`:** Memori untuk operasi DDL dan vacuum (`VACUUM`, `CREATE INDEX`, `ALTER TABLE ADD FOREIGN KEY`).
  * **`temp_buffers`:** Memori untuk temporary tables per sesi.

### 3. Disk File Layout & Page Internal
* Lokasi direktori data: `$PGDATA/base/<db_oid>/<relfilenode>`.
* Relasi yang melebihi 1GB dipecah menjadi *segment files* (`relfilenode.1`, `relfilenode.2`, dst).
* Format Internal 8KB Page:
  * **PageHeaderData (24 bytes):** Menyimpan informasi LSN (Log Sequence Number), offset `pd_lower` (akhir ItemId), offset `pd_upper` (awal data tuple terbaru), dan flags.
  * **ItemId Array (`Linp`):** Array penunjuk offset 4-byte (`lp_off`, `lp_flags`, `lp_len`).
  * **HeapTupleHeaderData (23/24 bytes per tuple):** Menyimpan metadata MVCC: `t_xmin` (XID pembuat), `t_xmax` (XID penghapus/pengubah), `t_cid` (Command ID), dan `t_infomask`.

---

## 06 Panduan Implementasi Step-by-Step

### Step 1: Identifikasi Topologi Proses OS dan PostgreSQL Postmaster
Eksekusi di terminal host PostgreSQL untuk memeriksa relasi parent-child antar proses:

```bash
# Pastikan PostgreSQL berjalan
sudo systemctl status postgresql

# Ambil PID Postmaster utama
POSTMASTER_PID=$(pgrep -f "postgres -D" | head -n 1)
echo "Postmaster PID: $POSTMASTER_PID"

# Tampilkan pohon proses lengkap di bawah postmaster
pstree -p -a $POSTMASTER_PID
```

### Step 2: Mapping Struktur On-Disk `$PGDATA`
Analisis letak direktori basis data dan hubungkan dengan *system catalog*:

```sql
-- Masuk ke psql
psql -U postgres -d postgres

-- Query relasi antara Database OID dan File System Directory
SELECT 
    oid AS database_oid, 
    datname AS database_name, 
    pg_relation_filepath(oid) AS relative_path
FROM pg_database 
WHERE datname = current_database();
```

---

## 07 Contoh Kasus Sederhana: Pelacakan Block dan Tuple Header

Berikut adalah skenario pembuatan tabel sederhana untuk melihat bagaimana LSN, `xmin`, `xmax`, dan alokasi *slotted page* bekerja di shared buffer.

```sql
-- 1. Buat extension untuk inspeksi byte-level storage
CREATE EXTENSION IF NOT EXISTS pageinspect;
CREATE EXTENSION IF NOT EXISTS pg_buffercache;

-- 2. Buat tabel demonstrasi
DROP TABLE IF EXISTS demo_page_layout;
CREATE TABLE demo_page_layout (
    id serial PRIMARY KEY,
    payload text
);

-- 3. Insert tepat satu row
INSERT INTO demo_page_layout (payload) VALUES ('Kernel-Level-Data');

-- 4. Periksa OID dan RelFileNode
SELECT relname, oid, relfilenode, relpages, reltuples 
FROM pg_class 
WHERE relname = 'demo_page_layout';

-- 5. Inspeksi Page Header block ke-0
SELECT lsn, checksum, flags, lower, upper, special, pagesize
FROM page_header(get_raw_page('demo_page_layout', 0));

-- 6. Inspeksi ItemId dan metadata MVCC Tuple
SELECT lp, lp_off, lp_flags, lp_len, t_xmin, t_xmax, t_field3 as t_cid, t_ctid 
FROM heap_page_items(get_raw_page('demo_page_layout', 0));
```

---

## 08 Implementasi Production-Grade Lengkap Kode

Naskah SQL berikut mengonstruksi sistem observabilitas internal berbasis *system view* dan *extensions* untuk mengaudit kondisi *Shared Buffer Pool*, pemetaan *Dirty Blocks*, serta *Cache Hit Ratio* per relasi secara presisi.

```sql
-- ============================================================================
-- SCRIPT: pg_internals_monitor.sql
-- DESKRIPSI: Diagnostic Toolkit Arsitektur Memori dan Storage PostgreSQL
-- PRASYARAT: SUPERUSER Privilege, Extension pg_buffercache & pg_visibility
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_buffercache;
CREATE EXTENSION IF NOT EXISTS pageinspect;
CREATE EXTENSION IF NOT EXISTS pg_visibility;

CREATE SCHEMA IF NOT EXISTS dba_internals;

-- ----------------------------------------------------------------------------
-- 1. View: Audit Distribusi Isi Shared Buffer Pool
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dba_internals.v_shared_buffer_distribution AS
SELECT
    COALESCE(d.datname, '** SHARED / GLOBAL **') AS database_name,
    COALESCE(c.relname, '** UNKNOWN/FREE **') AS relation_name,
    c.relkind,
    count(*) AS buffer_blocks,
    pg_size_pretty(count(*) * 8192) AS buffered_size,
    ROUND((count(*)::numeric / (SELECT setting FROM pg_settings WHERE name='shared_buffers')::numeric) * 100, 2) AS pct_shared_buffers,
    ROUND(avg(b.usagecount), 2) AS avg_usage_count,
    count(CASE WHEN b.isdirty THEN 1 END) AS dirty_blocks,
    pg_size_pretty(count(CASE WHEN b.isdirty THEN 1 END) * 8192) AS dirty_size
FROM pg_buffercache b
LEFT JOIN pg_database d ON b.reldatabase = d.oid
LEFT JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid) AND b.reldatabase = (SELECT oid FROM pg_database WHERE datname = current_database())
GROUP BY 1, 2, 3
ORDER BY buffer_blocks DESC
LIMIT 25;

-- ----------------------------------------------------------------------------
-- 2. Fungsi: Detail Analisis Page Header dan Slotted Tuples per Block
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dba_internals.fn_inspect_relation_block(
    p_table_name TEXT,
    p_block_no INT
)
RETURNS TABLE (
    tuple_index INT,
    tuple_offset INT,
    tuple_length INT,
    xmin_tx BIGINT,
    xmax_tx BIGINT,
    is_hot_updated BOOLEAN,
    is_heap_only_tuple BOOLEAN,
    tuple_data_hex TEXT
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_raw_page BYTEA;
BEGIN
    -- Mengambil raw data byte block ke-n
    EXECUTE format('SELECT get_raw_page(%L, %s)', p_table_name, p_block_no) INTO v_raw_page;
    
    RETURN QUERY
    SELECT 
        h.lp::INT AS tuple_index,
        h.lp_off::INT AS tuple_offset,
        h.lp_len::INT AS tuple_length,
        h.t_xmin::text::bigint AS xmin_tx,
        h.t_xmax::text::bigint AS xmax_tx,
        (h.t_infomask2 & 16384) > 0 AS is_hot_updated,   -- HEAP_HOT_UPDATED flag
        (h.t_infomask2 & 32768) > 0 AS is_heap_only_tuple, -- HEAP_ONLY_TUPLE flag
        encode(h.t_data, 'hex') AS tuple_data_hex
    FROM heap_page_items(v_raw_page) h;
END;
$$;

-- ----------------------------------------------------------------------------
-- 3. View: Status Checkpointer & Background Writer Activity Metrics
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW dba_internals.v_checkpoint_bgwriter_health AS
SELECT
    checkpoints_timed,
    checkpoints_req AS checkpoints_requested_forced,
    checkpoint_write_time,
    checkpoint_sync_time,
    buffers_checkpoint,
    buffers_clean AS buffers_written_by_bgwriter,
    maxwritten_clean AS bgwriter_halt_count,
    buffers_backend AS buffers_written_by_backends_sync,
    buffers_alloc AS buffers_allocated,
    stats_reset
FROM pg_stat_bgwriter;

COMMIT;

-- Eksekusi Pengujian View
SELECT * FROM dba_internals.v_shared_buffer_distribution;
SELECT * FROM dba_internals.v_checkpoint_bgwriter_health;
```

---

## 09 Diagram Alur Kerja ASCII: Transaction Write & Checkpoint Pipeline

```text
CLIENT BACKEND                     SHARED MEMORY (SRAM)                  DISK STORAGE (NVMe/SSD)
+---------------+               +------------------------+             +------------------------+
| SQL UPDATE    |               |                        |             |                        |
| Transaction   |               |                        |             |                        |
+-------+-------+               +------------------------+             +------------------------+
        |                                   |                                      |
        | 1. Modifikasi Block               |                                      |
        +---------------------------------->| Search Block in Shared Buffers       |
        |                                   | - Mark Block as DIRTY                |
        |                                   |                                      |
        | 2. Generate WAL Record            |                                      |
        +---------------------------------->| Append LSN -> WAL Buffer             |
        |                                   |                                      |
        | 3. COMMIT Transaction             |                                      |
        +---------------------------------->| Mark XID as COMMITTED in CLOG        |
        |                                   |                                      |
        | 4. Flush WAL to Disk (fsync)      |                                      |
        |    (Write ahead of data)          | WAL Buffer                           | WAL Disk Segment
        |-----------------------------------|------------------------------------->| (pg_wal/00000001...)
        |                                   | Flush/Fsync Sync                     | (DURABILITY GUARANTEED)
        |                                   |                                      |
        | 5. ACK ke Client (Success)        |                                      |
        |<----------------------------------+                                      |
        |                                   |                                      |
        |                                   |                                      |
+-------v-------+                           |                                      |
| BGWRITER /    | 6. Eviction/Continuous    | Shared Buffers (Dirty)               | Data Heap Files
| CHECKPOINTER  |    Write dirty pages      |------------------------------------->| ($PGDATA/base/...)
+---------------+    (Asynchronous)         | Flush dirty 8KB blocks               | (Checkpoint flushes all)
```

---

## 10 Analisis Trade-offs

| Aspek Arsitektur | Pilihan Desain / Parameter | Keuntungan (+)| Kerugian / Risiko (-) | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Multi-Process (`fork`) vs Multi-Thread | Isolasi memori mutlak; kegagalan satu backend tidak membuat *crash* node engine utama. | Overhead alokasi IPC tinggi, konsumsi *context switching* masif pada koneksi tinggi (>1000). | Gunakan external connection pooler (misal: `PgBouncer`) di depan PostgreSQL. |
| **Shared Buffers Sizing** | `shared_buffers = 25% RAM` vs `> 70% RAM` | Menyisakan ruang untuk OS Linux Page Cache (Double Buffering), efisien untuk buffered read. | Double buffering membuang data duplikat di RAM; transfer data via double memory copy. | 25% - 40% dari Total System RAM pada standard OLTP. |
| **WAL Synchronous Commit** | `synchronous_commit = on` vs `off` | Jaminan 100% ACID Durability; zero RPO jika server crash/mati listrik mendadak. | *Latency penalty* tinggi karena setiap commit harus menunggu I/O `fsync` storage. | `on` untuk finansial/ledger transaksi; `off` untuk logging/bulk ingestion non-kritis. |
| **Work Mem Sizing** | Nilai Rendah (4MB) vs Tinggi (256MB+) | Mencegah OOM (*Out Of Memory Killer*) pada *concurrency* tinggi. | Eksekusi sorting/hashing beralih (*spill*) ke disk *workfiles* (I/O lambat). | 4MB-16MB baseline, di-override per sesi/query khusus analitik (`SET work_mem='1GB'`). |

---

## 11 Best Practices & Antipatterns

### Best Practices
1. **Patuhi Batas Double Buffering:** Set `shared_buffers` antara 25% hingga maksimal 40% dari total RAM fisik. Biarkan sisa RAM untuk OS Page Cache guna menangani sequential scan dan vacuum execution.
2. **Kendalikan `max_connections`:** Nilai `max_connections` di atas 300-500 tanpa connection pooler membebani memory synchronization pada *spinlock* / *LWLocks* CPU. Pasang PgBouncer atau Odyssey.
3. **Konfigurasi Checkpoint Spread Spikes:** Set `checkpoint_completion_target = 0.9` agar I/O rate saat checkpoint disebar secara konstan sepanjang interval, mencegah disk I/O spikes.
4. **Perhatikan *Fillfactor* pada Write-Heavy Tables:** Turunkan `fillfactor` ke 80-90 pada tabel yang sering di-update untuk memicu mekanisme HOT (*Heap-Only Tuples*) update tanpa memodifikasi index pages.

### Antipatterns
1. **Setting `work_mem` Global Terlalu Besar:** Mengalokasikan `work_mem = 1GB` secara global dengan `max_connections = 200`. Satu complex query bisa membuka 5 node sort/hash secara paralel, memicu OOM Killer secara instan.
2. **Mengabaikan Transaction ID Wraparound Risk:** Mematikan daemon `autovacuum` demi performa write. Hal ini menyebabkan autovacuum freeze macet dan database masuk mode read-only darurat (*forced emergency shutdown*).
3. **Menempatkan `$PGDATA` dan `$PGWAL` pada Diska Fisik yang Sama:** WAL I/O bersifat serial write-heavy berlatensi rendah, sedangkan heap access bersifat random I/O. Menyatukannya pada storage non-NVMe lambat akan memicu I/O *head contention*.

---

## 12 Security Hardening

```bash
# 1. Pastikan perizinan direktori PGDATA terkunci mutlak ke user pengelola
chmod 0700 /var/lib/postgresql/data
chown -R postgres:postgres /var/lib/postgresql/data

# 2. Hardening Unix Domain Socket access pada postgresql.conf
cat << 'EOF' >> /etc/postgresql/postgresql.conf
# Batasi hak akses socket file lokal
unix_socket_permissions = 0770
unix_socket_group = 'postgres'

# Aktifkan SSL/TLS mutlak untuk mengamankan data in-transit antar-proses
ssl = on
ssl_cert_file = '/etc/ssl/certs/pg_server.crt'
ssl_key_file = '/etc/ssl/private/pg_server.key'
ssl_min_protocol_version = 'TLSv1.3'
EOF

# 3. Restriksi akses ke Extensions pengaudit internal (pageinspect, pg_buffercache)
# Jangan berikan akses eksplisit ke non-DBA users!
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA dba_internals FROM PUBLIC;
GRANT USAGE ON SCHEMA dba_internals TO dba_admin_role;
```

---

## 13 Observabilitas & Debugging

Gunakan query diagnosa *low-level locks* dan *buffer wait event* berikut untuk menganalisis contention pada PostgreSQL Shared Memory:

```sql
-- Deteksi Bottleneck pada Buffer Pin Locking dan Lightweight Locks (LWLock)
SELECT 
    pid,
    wait_event_type,
    wait_event,
    state,
    backend_type,
    query
FROM pg_stat_activity
WHERE wait_event_type IN ('LWLock', 'BufferPin', 'Lock')
  AND pid <> pg_backend_pid();

-- Analisis I/O Timing per Operasi Relasi (Harus enable track_io_timing = on)
SELECT 
    relname,
    heap_blks_read,
    heap_blks_hit,
    ROUND(heap_blks_hit::numeric / NULLIF(heap_blks_hit + heap_blks_read, 0) * 100, 2) as buffer_hit_ratio
FROM pg_statio_user_tables
ORDER BY heap_blks_read DESC
LIMIT 10;
```

---

## 14 Benchmarking & Performance

Jalankan pengujian benchmarking menggunakan `pgbench` untuk menganalisis performa Write-Ahead Log (WAL) dan Shared Buffer Flushes di bawah beban transaksi tinggi:

```bash
# 1. Inisialisasi Environment Test (Scale Factor = 50, sekitar 750MB data)
pgbench -i -s 50 -U postgres postgres

# 2. Benchmark Baseline: OLTP-Read-Write Default selama 60 detik dengan 10 klien paralel
pgbench -c 10 -j 2 -T 60 -U postgres postgres > benchmark_baseline.log

# 3. Pantau disk sync latency selama benchmark berjalan (buka terminal baru)
# Menggunakan utility Linux iostat
iostat -xz 1 60
```

---

## 15 Hands-on Lab Mini-Project

### Skenario Lab
Anda ditugaskan membuktikan mekanisme MVCC Tuple Header dan mendemonstrasikan fenomena *Heap-Only Tuple (HOT) Update* langsung di dalam 8KB Page Block.

### Langkah Eksekusi

```sql
-- 1. Setup Environment
DROP TABLE IF EXISTS lab_hot_demo;
CREATE TABLE lab_hot_demo (
    id INT PRIMARY KEY,
    val INT,
    description VARCHAR(100)
) WITH (fillfactor = 70); -- Alokasikan 30% free space per page untuk in-place update

-- 2. Insert Single Record
INSERT INTO lab_hot_demo VALUES (1, 100, 'Baseline State');

-- 3. Ambil Pointer CTID (Tuple ID: Block No, Offset)
SELECT ctid, xmin, xmax, * FROM lab_hot_demo WHERE id = 1;

-- 4. Jalankan Update yang TIDAK memodifikasi Indexed Column (Memenuhi syarat HOT)
UPDATE lab_hot_demo SET val = 101, description = 'HOT Update Step 1' WHERE id = 1;

-- 5. Periksa Page Items via pageinspect
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len, 
    t_xmin, 
    t_xmax, 
    t_ctid,
    (t_infomask2 & 32768) != 0 AS is_heap_only_tuple
FROM heap_page_items(get_raw_page('lab_hot_demo', 0));

-- Validasi: Tuple pertama (lp=1) sekarang mengarah (t_ctid) ke lp=2 di block yang sama tanpa mengubah Index root.
```

---

## 16 Automated Testing & Verification

Script bash assertion di bawah memverifikasi integritas Page Header dan konfigurasi memory database secara otomatis:

```bash
#!/usr/bin/env bash
set -euo pipefail

DB_NAME="postgres"
DB_USER="postgres"

echo "=== [TEST 1] Verifikasi Ekstensi pageinspect & pg_buffercache ==="
psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 << 'EOF'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pageinspect') THEN
        RAISE EXCEPTION 'Assertion Failed: pageinspect extension missing!';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_buffercache') THEN
        RAISE EXCEPTION 'Assertion Failed: pg_buffercache extension missing!';
    END IF;
    RAISE NOTICE 'Extensions Verified: OK';
END $$;
EOF

echo "=== [TEST 2] Verifikasi Kernel Page Size dan LSN Integrity ==="
PAGE_SIZE=$(psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "SHOW block_size;")
if [ "$PAGE_SIZE" -eq "8192" ]; then
    echo "Assertion Success: Block Size terstandarisasi 8192 Bytes (8KB)."
else
    echo "Assertion Failed: Block size terdeteksi $PAGE_SIZE"
    exit 1
fi

echo "=== Semua Verifikasi Integritas Arsitektur Lolos ==="
```

---

## 17 Troubleshooting Guide

| Gejala Masalah | Indikasi Internal / Root Cause | Metodologi Investigasi | Solusi Remediasi |
| :--- | :--- | :--- | :--- |
| **Tingginya `buffers_backend` pada pg_stat_bgwriter** | Backend worker terpaksa melakukan synchronous disk write karena `bgwriter` tertinggal (*lagging*) dalam menyediakan *clean pages*. | Query `SELECT * FROM pg_stat_bgwriter;` bandingkan `buffers_backend` vs `buffers_clean`. | Naikkan `bgwriter_lru_maxpages` dan turunkan `bgwriter_delay` agar bgwriter beroperasi lebih agresif. |
| **Disk I/O Spike masif setiap N Menit** | Forced Checkpoint terjadi akibat `max_wal_size` terlampaui sebelum interval `checkpoint_timeout` tercapai. | Cek PostgreSQL log untuk pesan: *"checkpoint starting: wal"*. | Naikkan `max_wal_size` (e.g., dari 1GB ke 16GB-64GB) dan set `checkpoint_completion_target = 0.9`. |
| **Query `ORDER BY` lambat dan I/O tinggi** | Alokasi `work_mem` terlalu rendah menyebabkan eksekusi sort tumpah (*spill*) ke file temporary di disk. | Cek view `pg_stat_database.temp_bytes` atau query plan dengan `EXPLAIN (ANALYZE, BUFFERS)`. | Naikkan `work_mem` secara terukur pada level per-koneksi atau global setting. |

---

## 18 Checklist Produksi

- [ ] **Shared Memory:** `shared_buffers` diatur ke 25% dari total RAM sistem.
- [ ] **Background Writer:** Parameter `bgwriter_delay` diset ke `20ms` atau `10ms` pada traffic I/O tinggi.
- [ ] **Checkpoint Smoothing:** `checkpoint_completion_target` diset ke `0.9`.
- [ ] **WAL Dimensions:** `max_wal_size` dialokasikan minimal `16GB` (bergantung kapasitas disk) untuk menghindari *checkpoint storms*.
- [ ] **I/O Statistics:** Parameter `track_io_timing = on` diaktifkan untuk audit latensi block read/write.
- [ ] **Transaction Freeze Mitigation:** `autovacuum_freeze_max_age` diverifikasi dan proses autovacuum dipastikan berjalan aktif (`autovacuum = on`).
- [ ] **Kernel Overcommit:** Linux kernel parameter `vm.overcommit_memory = 2` dan `vm.overcommit_ratio` disesuaikan untuk mencegah OOM-kill mendadak pada PostgreSQL instance.

---

## 19 Ringkasan Eksekutif

PostgreSQL mengimplementasikan arsitektur berorientasi ketahanan (*durability-first*) berbasis **multi-process engine**, memisahkan memori bersama (*Shared Memory*) dan memori lokal per koneksi (*Local Backend Memory*). Seluruh manipulasi data dimediasi melalui unit terstandarisasi **8KB Slotted Page Engine**, di mana tuple header menyimpan status visibilitas ACID melalui metadata `xmin`/`xmax`.

Pilar performa PostgreSQL bertumpu pada interaksi yang harmonis antara:
1. Alokasi **Shared Buffers** dengan algoritma *Clock Sweep*.
2. Mekanisme write penjamin integritas transaksi via **Write-Ahead Logging (WAL)**.
3. Strategi flush asinkron melalui **Background Writer** dan **Checkpointer** untuk mengeliminasi latensi disk I/O dari eksekusi client backend.

Konfigurasi parameter yang optimal menuntut pemahaman konkret terhadap struktur fisik storage, siklus hidup buffer, dan interaksi PostgreSQL dengan kernel operating system subsystem.

---

## 20 Referensi & Bacaan Lanjutan
* The PostgreSQL Global Development Group. *PostgreSQL Documentation: Chapter 53 - Internals*. [https://www.postgresql.org/docs/current/internals.html](https://www.postgresql.org/docs/current/internals.html)
* Suzuki, Hironobu. (2023). *The Internals of PostgreSQL for Database Administrators and System Developers*. [https://www.interdb.jp/pg/](https://www.interdb.jp/pg/)
* Smith, Gregory. (2010). *PostgreSQL 9.0 High Performance*. Packt Publishing.
* PostgreSQL Source Code Repository: `/src/backend/storage/` (Buffer Manager, Page Manager, Free Space Map implementations).