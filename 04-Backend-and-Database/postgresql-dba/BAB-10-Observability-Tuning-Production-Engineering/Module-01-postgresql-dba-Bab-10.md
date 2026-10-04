# Kurikulum: PostgreSQL Database Administrator (PostgreSQL-DBA)
## Kategori: 04-Backend-and-Database
### Bab 10: Observability, Tuning & Production Engineering
#### Module 01: Core Observability, Linux Kernel Tuning, and Query Performance Engineering

---

### 01: Identitas Modul
* **Track:** Database Engineering & Systems Infrastructure
* **Target Audience:** Principal DBA, Production Engineers, Staff Backend Engineers, SRE
* **Prerequisites:** Arsitektur Internal PostgreSQL (Storage Engine, WAL, MVCC), Pemahaman Linux OS Internals (VFS, IPC, Virtual Memory Subsystems), SQL DDL/DML Tingkat Lanjut.
* **Tingkat Kesulitan:** Advanced / L5-L6 Engineering Level
* **Durasi Estimasi:** 180 Menit Pembelajaran Teknis Mendalam & Hands-on Lab

---

### 02: Learning Objectives
Setelah menyelesaikan modul ini, engineer memiliki kompetensi terverifikasi untuk:
1. Mengonfigurasi subsistem instrumentasi internal PostgreSQL (`pg_stat_statements`, Wait Events engine, Cumulative Statistics System) dengan overhead CPU `< 1.5%`.
2. Mendiagnosis dan mengeliminasi hardware-software impedance mismatch melalui tuning kernel Linux (Dirty Memory Pages, Transparent Huge Pages, NUMA balancing, I/O Schedulers).
3. Menganalisis execution plans kompleks (`EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)`) untuk mengidentifikasi degradasi performa akibat disk spills, cache evictions, dan lock contentions.
4. Membangun infrastruktur observabilitas end-to-end berbasis open-source metrics exporter, structured logging, dan active-session tracing.
5. Mengeksekusi optimasi buffer pool (`shared_buffers`) dan query execution memory (`work_mem`) berbasis empirical profiling matematis.

---

### 03: Concept Map Diagram ASCII
```
+----------------------------------------------------------------------------------------------------+
|                                    LINUX OPERATING SYSTEM LAYER                                    |
|  +--------------------+  +-------------------------+  +----------------------+  +---------------+  |
|  | NUMA Policy Engine |  | VM Dirty Memory Pages   |  | I/O Scheduler (MQ)   |  | THP Disabled  |  |
|  | (numactl --interl) |  | (dirty_ratio / flusher) |  | (none / mq-deadline) |  | (madvise)     |  |
+--+---------+----------+--+------------+------------+--+----------+-----------+--+-------+-------+--+
             |                          |                          |                      |
+------------v--------------------------v--------------------------v----------------------v----------+
|                                    POSTGRESQL INSTANCE ENGINE                                      |
|  +-----------------------------------------------------------------------------------------------+  |
|  | Shared Memory (shared_buffers) <---> Background Writer <---> Checkpointer <---> WAL Engine    |  |
|  +-----------------------------------------------------------------------------------------------+  |
|                                                |                                                    |
|                   +----------------------------+----------------------------+                       |
|                   |                                                         |                       |
|  +----------------v-----------------+                     +-----------------v--------------------+  |
|  |   Work Memory Subsystems         |                     | Instrumentation Engine               |  |
|  |   - work_mem (Sort/Hash/Bitmap)  |                     | - pg_stat_statements                 |  |
|  |   - maintenance_work_mem         |                     | - pg_stat_activity (Wait Events)     |  |
|  |   - autovacuum_work_mem          |                     | - pg_statio_user_tables (Disk IO)    |  |
|  +----------------------------------+                     +--------------------------------------+  |
+------------------------------------------------+---------------------------------------------------+
                                                 |
+------------------------------------------------v---------------------------------------------------+
|                                 MONITORING & CONTROL PLANE                                         |
|  +-----------------------------+  +-------------------------------+  +--------------------------+  |
|  | Prometheus PostgresExporter |  | Grafana PostgreSQL Dashboard  |  | pgBadger Log Diagnostics |  |
|  +-----------------------------+  +-------------------------------+  +--------------------------+  |
+----------------------------------------------------------------------------------------------------+
```

---

### 04: Mengapa Relevan
Dalam skala produksi enterprise (OLTP throughput tinggi, concurrent active sessions > 1000, dataset terabyte/petabyte), degradasi performa jarang disebabkan oleh satu query tunggal yang lambat. Sebaliknya, bottleneck terjadi karena gesekan multidimensi antara PostgreSQL core engine dan kernel OS:
* **Disk I/O Choke:** Kegagalan mengonfigurasi `vm.dirty_background_ratio` menyebabkan Linux kernel memblokir I/O PostgreSQL untuk melakukan flush synchronously, mengakibatkan I/O spike dan micro-stalls.
* **Memory Sub-allocation Waste:** Nilai `work_mem` yang terlalu rendah memicu eksekusi disk spill pada disk-based hash joins/external sorts, sedangkan nilai yang terlalu tinggi memicu Linux Out-Of-Memory (OOM) Killer mematikan PostgreSQL Postmaster.
* **Invisible Latency:** Ketidakmampuan menganalisis PostgreSQL *Wait Events* (`WaitEventSet`) membuat SRE berasumsi latency disebabkan CPU, padahal transaksi terhenti pada `LWLock:BufferContent` atau `Lock:relation`.

---

### 05: Anatomi Konsep Inti

#### 1. Linux Kernel Tuning Primitives
* **Transparent Huge Pages (THP):** Harus di-disable (`never` atau `madvise`). Alokasi 2MB page dinamis pada THP memicu *memory compaction latency* yang memblokir proses alokasi memori backend worker.
* **Dirty Page Ratio:** Mengontrol kapan kernel background threads (`kworker`) mulai melakukan flush buffer OS ke disk.
  * `vm.dirty_background_ratio = 5`: Mulai background async write ke disk saat 5% memory kotor.
  * `vm.dirty_ratio = 10`: Paksa proses yang melakukan write untuk synchronous write ke disk jika memory kotor mencapai 10%.
* **Swappiness:** `vm.swappiness = 1` atau `10`. Mencegah OS memindahkan page memori aktif PostgreSQL dari RAM ke swap file, sambil tetap menyediakan safety-valve jika terjadi tekanan alokasi ekstrem.

#### 2. PostgreSQL Memory Subsystem Mathematics
* **`shared_buffers`:** Idealnya diset ke 25%–40% dari total RAM fisik sistem untuk sistem non-Windows. Sisanya dialokasikan untuk OS Page Cache guna mendukung double-buffering architecture PostgreSQL.
* **`work_mem` formula estimasi:**
$$\text{Max Allocatable Memory} = \text{shared\_buffers} + \text{maintenance\_work\_mem} + (\text{max\_connections} \times \text{work\_mem} \times \text{avg\_concurrent\_operations})$$

#### 3. Wait Events Architecture
PostgreSQL membagi siklus hidup query execution ke dalam beberapa status wait:
* **CPU/Compute:** Query sedang aktif dieksekusi oleh core CPU.
* **IO Wait (`IO:*`):** Proses menunggu transfer data disk (e.g., `DataFileRead`, `WALWrite`).
* **Lock Wait (`Lock:*`):** Transaksi terhambat oleh Heavyweight Locks (table/row lock level).
* **LWLocks (`LWLock:*`):** Lightweight locks pada internal shared data structures (e.g., `BufferContent`, `WALInsertionLock`).

---

### 06: Panduan Implementasi Step-by-Step

#### Step 1: Linux Kernel Configuration
Terapkan parameter kernel sistem melalui `/etc/sysctl.d/99-postgresql.conf`:
```bash
sudo bash -c 'cat << EOF > /etc/sysctl.d/99-postgresql.conf
# Virtual Memory Tuning
vm.swappiness = 10
vm.dirty_background_ratio = 3
vm.dirty_ratio = 10
vm.overcommit_memory = 2
vm.overcommit_ratio = 80

# Network & Socket Buffers for High-Concurrency
net.core.somaxconn = 4096
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216

# File Descriptors
fs.file-max = 2097152
EOF'

sudo sysctl -p /etc/sysctl.d/99-postgresql.conf
```

Nonaktifkan THP melalui `systemd unit`:
```bash
sudo bash -c 'cat << EOF > /etc/systemd/system/disable-thp.service
[Unit]
Description=Disable Transparent Huge Pages (THP)
DefaultDependencies=no
After=sysinit.target local-fs.target
Before=mongod.service postgresql.service

[Service]
Type=oneshot
ExecStart=/bin/sh -c "echo never > /sys/kernel/mm/transparent_hugepage/enabled && echo never > /sys/kernel/mm/transparent_hugepage/defrag"

[Install]
WantedBy=basic.target
EOF'

sudo systemctl daemon-reload
sudo systemctl enable --now disable-thp.service
```

#### Step 2: Konfigurasi PostgreSQL Instrumentation (`postgresql.conf`)
Tambahkan parameter telemetry berikut ke dalam `postgresql.conf`:
```ini
# Shared Library Preloading
shared_preload_libraries = 'pg_stat_statements,pg_stat_kcache'

# pg_stat_statements Config
pg_stat_statements.max = 10000
pg_stat_statements.track = all
pg_stat_statements.track_utility = off
pg_stat_statements.save = on

# Enhanced Logging Engine
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_min_duration_statement = 250 # Log query running >= 250ms
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 0               # Log any temp file creation (disk spills)
log_autovacuum_min_duration = 500 # Log autovacuum runs taking > 500ms
log_line_prefix = '%m [%p] %q%u@%d client=%h app=%a tx=%x '
```

Muat ulang service PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

### 07: Contoh Kasus Sederhana
Mengidentifikasi Top 3 Query yang mendominasi utilisasi shared buffer cache dan eksekusi disk spill menggunakan view `pg_stat_statements`.

```sql
-- Inisialisasi Ekstensi
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Analisis Query Paling Boros Resource
SELECT 
    queryid,
    substring(query, 1, 50) AS query_snippet,
    calls,
    round(total_exec_time::numeric, 2) AS total_time_ms,
    round(mean_exec_time::numeric, 2) AS mean_time_ms,
    shared_blks_hit,
    shared_blks_read,
    temp_blks_written, -- Indikator disk spill (work_mem exhaustion)
    round((shared_blks_hit::numeric / NULLIF(shared_blks_hit + shared_blks_read, 0)) * 100, 2) AS cache_hit_pct
FROM 
    pg_stat_statements
ORDER BY 
    total_exec_time DESC
LIMIT 3;
```

---

### 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah implementasi automated active monitoring system berbasis function yang mengekstrak wait events dan blocking tree transactions secara real-time.

```sql
-- DDL & Diagnostics Script: Active Lock Contention & Worker State Monitor
CREATE SCHEMA IF NOT EXISTS dba_diagnostics;

CREATE OR REPLACE VIEW dba_diagnostics.v_live_workload_health AS
WITH session_waits AS (
    SELECT 
        pid,
        usename,
        datname,
        client_addr,
        application_name,
        state,
        wait_event_type,
        wait_event,
        query,
        EXTRACT(EPOCH FROM (clock_timestamp() - state_change)) AS state_age_seconds,
        EXTRACT(EPOCH FROM (clock_timestamp() - query_start)) AS query_age_seconds
    FROM pg_stat_activity
    WHERE pid <> pg_backend_pid()
),
blocking_chains AS (
    SELECT 
        blocked_locks.pid     AS blocked_pid,
        blocking_locks.pid    AS blocking_pid
    FROM  pg_catalog.pg_locks blocked_locks
    JOIN pg_catalog.pg_locks blocking_locks 
        ON blocking_locks.locktype = blocked_locks.locktype
        AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
        AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
        AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
        AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
        AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
        AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
        AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
        AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
        AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
