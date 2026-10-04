# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 10: Observability, Tuning, & Production Engineering**  
**Kategori: 04-Backend-and-Database (PostgreSQL Enterprise DBA)**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Engine Metrics**: Mengidentifikasi bottleneck throughput dan latensi mikro menggunakan arsitektur wait event, internal shared memory stats, dan view diagnostic PostgreSQL (`pg_stat_activity`, `pg_stat_database`, `pg_statio_*`).
- **Mendesain Checkpoint & Memory Architecture**: Mengonfigurasi subsistem `shared_buffers`, `work_mem`, background writer, dan checkpointer untuk memitigasi *checkpoint spikes* dan *write amplification* pada beban kerja I/O tinggi.
- **Mengimplementasikan Observability Pipeline End-to-End**: Membangun arsitektur telemetri produksi menggunakan `pg_stat_statements`, Prometheus `postgres_exporter`, eBPF runtime profiling, dan alerting berbasis Service Level Objectives (SLO).
- **Mendiagnosis Concurrency Contention & Lock Trees**: Mengurai kaskade heavyweight locking, row-level locks, tuple pinning, dan fast-path lock exhaustion dalam kondisi beban kerja transaksi tinggi (>15.000 TPS).
- **Menjalankan Systematic Production Tuning**: Mengombinasikan tuning kernel OS Linux (I/O scheduler, dirty page throttling, transparent huge pages) dengan parameter PostgreSQL untuk mencapai latensi p99 < 15ms.

---

## 2. Prerequisites
Sebelum mempelajari modul ini, Anda harus memahami:
- Arsitektur proses PostgreSQL (`postmaster`, `backend`, `checkpointer`, `walwriter`, `autovacuum launcher`).
- Konsep dasar MVCC (Multi-Version Concurrency Control), snapshot isolation, dan format tuple header (`xmin`, `xmax`, `cmin`, `cmax`, `t_ctid`).
- Konsep Write-Ahead Logging (WAL), LSN (Log Sequence Number), dan mekanisme durability ACID.
- Akses administratif ke sistem operasi Linux (akses `root` atau `sudo`), sistem CLI, dan kemampuan menjalankan perintah SQL tingkat lanjut via `psql`.

---

## 3. Concept & Internal Architecture

Observabilitas dan penyetelan performa PostgreSQL tingkat enterprise memerlukan pemahaman mendalam tentang siklus hidup halaman memori (buffer pages), interaksi kernel I/O, dan subsistem penguncian internal.

### 3.1 Buffer Manager, Clock Sweep, dan Dirty Page Lifecycle

PostgreSQL menggunakan subsistem buffer pool mandiri yang dialokasikan di shared memory (`shared_buffers`) dan tidak langsung menulis perubahan ke disk saat transaksi di-*commit*. Durabilitas dijamin melalui penulisan synchronous ke Write-Ahead Log (WAL).

Halaman memori memiliki siklus hidup sebagai berikut:
1. **Pemuatan Halaman**: Backend memeriksa apakah blok data (8 KB) berada di `shared_buffers` menggunakan Hash Table pemetaan relasi/fork/blok. Jika tidak ditemukan (*cache miss*), backend mencari slot kosong atau mengorbankan halaman yang ada menggunakan algoritma **Clock Sweep** (varian dari Second-Chance FIFO / pseudo-LRU).
2. **Clock Sweep Mechanics**: Jarum penunjuk menyusuri deskriptor buffer. Setiap buffer memiliki *usage counter* (rentang 0–5) dan pin count. Jika counter > 0, counter didekremen dan jarum berpindah. Jika counter = 0 dan tidak sedang di-pin, buffer tersebut dipilih untuk digantikan (eviction candidate).
3. **Dirty Buffer Modification**: Ketika query memodifikasi data (UPDATE/INSERT), buffer ditandai sebagai *dirty* (`BM_DIRTY`). Backend tidak menulis dirty buffer langsung ke disk penyimpanan tabel melainkan hanya menulis WAL record terkait ke WAL buffer, lalu memanggil `XLogFlush()`.
4. **Flushing ke Kernel Cache**: Dirty buffers ditulis ke subsistem I/O disk oleh dua proses asinkron yang berbeda:
   - **Background Writer (`bgwriter`)**: Berjalan kontinu dengan siklus kecil (`bgwriter_delay`), membersihkan sejumlah kecil dirty pages di depan jarum Clock Sweep agar backend tidak mengalami latensi sinkron (*backend writes*) saat membutuhkan buffer bersih.
   - **Checkpointer**: Berjalan periodik (`checkpoint_timeout` atau volume `max_wal_size`). Checkpointer mengambil snapshot dari seluruh dirty buffers pada titik waktu tertentu, mengurutkannya berdasarkan physical block offset untuk meminimalkan I/O seek, dan menulisnya ke OS page cache, diakhiri dengan pemanggilan sistem `fsync()` pada semua file relasi terkait.

### 3.2 Arsitektur Wait Events Engine

PostgreSQL menyediakan instrumentasi diagnostik real-time melalui subsistem Wait Events pada view `pg_stat_activity`. Ketika backend tidak dapat melanjutkan eksekusi CPU, proses tersebut masuk ke status *wait* yang dikategorikan ke dalam:

- **LWLock (Lightweight Lock)**: Mekanisme sinkronisasi inter-process berkecepatan tinggi yang melindungi struktur data internal di shared memory (misal: `BufferContent`, `WALWriteLock`, `lock_manager`).
- **Lock (Heavyweight Lock / Relation Lock)**: Kunci level SQL yang mengatur akses konkuren terhadap objek database (misal: `AccessExclusiveLock`, `RowExclusiveLock`). Memiliki deteksi deadlock internal via *deadlock detector*.
- **BufferPin**: Backend menunggu proses lain melepaskan pin eksklusif pada shared buffer spesifik sebelum dapat menginspeksi atau menggeser tuple.
- **IO**: Backend terblokir menunggu penyelesaian operasi I/O subsistem penyimpanan (misal: `DataFileRead`, `DataFileWrite`, `WALSync`).
- **Activity / Client**: Backend menunggu event loop internal (idle) atau sedang menunggu paket query dari klien melalui network socket (`ClientRead`).

```
                +-------------------------------------------------------+
                |                  POSTGRES BACKEND                     |
                |  (Executes Query: Parse -> Plan -> Execute)          |
                +-------------------------------------------------------+
                        |                                   |
           Need Data    |                                   | Write WAL
          From Cache    v                                   v
+-----------------------------------+             +---------------------+
|          BUFFER MANAGER           |             |     WAL BUFFER      |
|  +-----------------------------+  |             +---------------------+
|  |       shared_buffers        |  |                        |
|  |  [Page 1][Page 2][Page 3]... |  |                        | XLogFlush()
|  +-----------------------------+  |                        v
|         ^               |         |             +---------------------+
|         | Clock         | Dirty   |             |   WAL Disk Files    |
|         | Sweep         | Pages   |             |    (pg_wal/...)     |
+---------|---------------|---------+             +---------------------+
          |               |                                  |
          |               +----------------+                 |
          |                                |                 |
          v                                v                 |
+-------------------+            +--------------------+      |
| BACKGROUND WRITER |            |    CHECKPOINTER    |      |
| Writes small batches           | Flushes all dirty  |      |
| to keep clean buffers          | buffers via fsync  |      |
+-------------------+            +--------------------+      |
          |                                |                 |
          +---------------+----------------+                 |
                          |                                  |
                          v                                  v
         +----------------------------------+       +------------------+
         |     Linux OS Page Cache          |       | Physical Storage |
         |   (Subject to kernel dirty ratio)| ----> |  (NVMe / SSD)    |
         +----------------------------------+       +------------------+
```

### 3.3 Dynamic Shared Memory & Stats Architecture

Sejak PostgreSQL 13 ke atas, subsistem statistik kumulatif dipindahkan dari *UDP-based Stats Collector process* ke **Shared Memory Engine**. Arsitektur baru ini meniadakan packet-drop bottleneck pada workload ber-TPS tinggi, memungkinkan pembacaan metrik zero-copy langsung dari memory slab, dan menyediakan data konsisten untuk monitoring agent eksternal.

---

## 4. Why & What

### Mengapa Perlu Deep-Dive Observability & Tuning?
Konfigurasi default PostgreSQL dirancang agar dapat berjalan di lingkungan minimal (kompatibel dengan sistem berkapasitas RAM 512 MB). Jika dijalankan di server enterprise (misal: 64 vCPU, 256 GB RAM, NVMe SAN) tanpa tuning:
- PostgreSQL hanya menggunakan `shared_buffers = 128MB` dan `work_mem = 4MB`.
- Query analitik atau batch write akan memicu tumpahan disk temporary (`work_mem spill to disk`), menurunkan performa hingga 100x lipat.
- Checkpointer default akan melakukan *checkpoint spikes*, membanjiri bus I/O storage dengan operasi penulisan sinkron masif setiap beberapa menit, mengakibatkan latensi p99 melonjak secara periodik.

### Apa yang Harus Diobservasi dan Dikonfigurasi?
1. **Telemetry Capture**: Mengukur latensi pada granularitas statement (`pg_stat_statements`) dan wait states (`pg_stat_activity`).
2. **Buffer Hit Ratio vs. OS Cache**: Memastikan 99% OLTP read dilayani oleh RAM tanpa round-trip NVMe.
3. **Dirty Page Smoothing**: Menyeimbangkan parameter kernel Linux (`dirty_background_ratio`, `dirty_ratio`) dengan parameter engine (`checkpoint_completion_target`, `max_wal_size`, `bgwriter_lru_maxpages`).
4. **Lock Contention**: Memantau antrean lock sebelum kaskade connection pool exhaustion melumpuhkan aplikasi.

---

## 5. How: Workflow Detail

Implementasi sistem observabilitas dan tuning produksi dijalankan melalui siklus rekayasa sistematis berikut:

```
[ Tahap 1: Kernel & Storage Setup ]
                |
                v
[ Tahap 2: Memory & Engine Sizing Tuning ]
                |
                v
[ Tahap 3: Checkpoint & WAL I/O Smoothing ]
                |
                v
[ Tahap 4: Instrumentasi Observability (pg_stat_statements, Exporter) ]
                |
                v
[ Tahap 5: Lock Contention Profiling & Query Optimization ]
```

### Langkah 1: Penyetelan Kernel Linux Target Engine
Sebelum database dikonfigurasi, sistem operasi host harus dioptimalkan untuk meminimalkan latency context-switching dan I/O stall.

### Langkah 2: Formula Sizing Memori PostgreSQL
1. **`shared_buffers`**: Dialokasikan sebesar 25% hingga 40% dari total RAM sistem. Mengalokasikan lebih dari 40% sering kali kontraproduktif karena menyebabkan double-buffering overhead antara engine dan Linux Page Cache.
2. **`work_mem`**: Alokasi per-operasi (bukan per-koneksi). Satu query kompleks dapat memiliki multi-node Sort dan Hash Join, menggunakan $N \times \text{work\_mem}$.
   $$\text{Max Work Mem Allocation} = \frac{\text{Total Available RAM} - \text{shared\_buffers}}{\text{max\_connections} \times 2 \text{ to } 3}$$
3. **`maintenance_work_mem`**: Dialokasikan besar (misal 2GB–4GB) untuk mempercepat proses VACUUM, CREATE INDEX, dan ALTER TABLE.

### Langkah 3: Menghilangkan Checkpoint Spikes
- Setel `checkpoint_completion_target = 0.9`. Ini memaksa checkpointer meratakan (throttle) penulisan dirty buffer sepanjang 90% durasi `checkpoint_timeout`.
- Perbesar `max_wal_size` (misal 32GB–64GB) untuk mencegah checkpoint berbasis volume WAL terjadi terlalu sering.

---

## 6. Analogy & Diagram ASCII

### Analogi: Dapur Restoran Bintang Lima
- **Shared Buffers**: Meja kerja utama koki. Bahan makanan (pages) yang sering diolah ditaruh di sini agar cepat diambil.
- **Clock Sweep**: Asisten koki yang berkeliling memeriksa meja. Jika piring bumbu sudah lama tidak disentuh (counter = 0), piring tersebut dipindahkan ke rak cuci untuk memberi ruang piring baru.
- **Backend Writer**: Petugas kebersihan yang secara santai dan konstan mencuci beberapa piring kotor setiap menit, sehingga koki selalu punya piring bersih tanpa harus berhenti memasak.
- **Checkpointer**: Supervisor yang datang tiap 30 menit, memerintahkan pembersihan total dan pencatatan inventaris ke buku besar. Jika supervisor tidak meratakan pekerjaannya (completion target rendah), seluruh operasional dapur berhenti total selama pembersihan mendadak.
- **WAL Engine**: Perekam suara koki. Setiap pesanan dan langkah dicatat instan di pita kaset (sequential write cepat) sebelum masakan selesai diolah. Jika dapur terbakar (crash), supervisor cukup mendengarkan rekaman kaset untuk merekonstruksi pesanan terakhir.

### Diagram: Alur Deteksi Bottleneck Wait Event

```
                    Query Latency Meningkat
                               |
                               v
               Cek pg_stat_activity (wait_event_type)
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
[ WaitType: IO ]       [ WaitType: Lock ]      [ WaitType: LWLock ]
       |                       |                       |
       v                       v                       v
Event: DataFileRead    Event: relation         Event: WALWriteLock /
Event: DataFileWrite   Event: tuple            BufferContent
       |                       |                       |
       v                       v                       v
- Cek Buffer Miss       - Identifikasi Lock     - Cek WAL disk I/O
- Naikkan RAM/Buffers     Tree / Blocking PID     bandwidth
- Cek Kernel IOPS       - Cek unindexed FK      - Cek buffer pool
- Tuning Autovacuum     - Review TX scope         contention (hot spots)
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Mengaktifkan Telemetri `pg_stat_statements`

Tambahkan ke `postgresql.conf`:
```ini
# Shared Library Preloading (memerlukan restart server)
shared_preload_libraries = 'pg_stat_statements'

# Parameter Instrumentasi
pg_stat_statements.max = 10000
pg_stat_statements.track = top
pg_stat_statements.track_utility = off
pg_stat_statements.save = on
```

Registrasikan ekstensi via `psql`:
```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Menemukan 5 query teratas berdasarkan konsumsi total waktu eksekusi
SELECT 
    queryid,
    substring(query, 1, 60) AS query_snippet,
    calls,
    round(total_exec_time::numeric, 2) AS total_time_ms,
    round(mean_exec_time::numeric, 2) AS mean_time_ms,
    round((100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0))::numeric, 2) AS hit_percent
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 5;
```

### 7.2 Practical Example: Enterprise Observability Stack & Contention Detector

Skrip SQL berikut menyediakan instrumentasi lengkap untuk mendeteksi *Lock Queues*, *Lock Trees*, dan dependensi transaksional yang menyebabkan thread pile-up.

```sql
-- View: enterprise_lock_tree_monitor
-- Menampilkan rantai pemblokiran transaksi hingga ke root blocker
CREATE OR REPLACE VIEW enterprise_lock_tree_monitor AS
WITH RECURSIVE lock_graph AS (
    -- Anchor member: Dapatkan sesi yang diblokir langsung oleh sesi lain
    SELECT 
        blocked_locks.pid AS blocked_pid,
        blocking_locks.pid AS blocking_pid,
        blocked_activity.usename AS blocked_user,
        blocking_activity.usename AS blocking_user,
        blocked_activity.query AS blocked_statement,
        blocking_activity.query AS current_statement_in_blocking_process,
        blocked_activity.wait_event AS blocked_wait_event,
        blocked_activity.wait_event_type AS blocked_wait_event_type,
        now() - blocked_activity.query_start AS blocked_duration,
        ARRAY[blocked_locks.pid, blocking_locks.pid] AS lock_path
    FROM pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
    JOIN pg_catalog.pg_locks blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked