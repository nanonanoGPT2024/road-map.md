# BAB 09: High Availability, Clustering & Partitioning
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur High Availability (HA) berbasis konsensus terdistribusi (Distributed Consensus Store/DCS) menggunakan Patroni, etcd, dan HAProxy/Keepalived dengan toleransi kegagalan otomatis (zero-data-loss failover target).
- Menganalisis siklus hidup Write-Ahead Logging (WAL), mekanisme stream replication internals (walsender, walreceiver, startup process), timeline switch, dan kalkulasi replikasi lag secara presisi berbasis Log Sequence Number (LSN).
- Mengonfigurasi dan mengoptimalkan connection pooling enterprise menggunakan PgBouncer dalam mode *transaction pooling*, lengkap dengan arsitektur split Read/Write traffic routing.
- Mengimplementasikan Declarative Partitioning tingkat lanjut (Range, List, Hash, dan Multi-level Composite Partitioning) serta mengotomatisasi siklus hidup partisi menggunakan ekstensi `pg_partman`.
- Mendiagnosis, memitigasi, dan memulihkan klaster dari insiden kegagalan partisi jaringan, split-brain scenario, replication slot bloat, dan degradasi performa partition pruning.

---

### 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Sistem Operasi**: Administrasi Linux tingkat lanjut (systemd, sysctl, network namespace, POSIX signal handling, I/O schedulers).
- **PostgreSQL Fundamental**: Pemahaman mendalam terkait MVCC, vacuuming, buffer pool (shared buffers), checkpointing, dan physical replication dasar (primary-standby streaming).
- **Jaringan & Keamanan**: Konsep TCP/IP, TLS mutual authentication (mTLS), DNS resolution, load balancing layer 4 vs layer 7, firewall (iptables/nftables).
- **Storage**: Karakteristik NVMe, block storage latency, file system semantics (ext4/xfs), dan dirty page writeback tuning.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Internal Streaming Replication & Timeline Switching
PostgreSQL streaming replication bekerja pada level physical block melalui stream WAL record.

```
+-----------------------------------------------------------------------------------+
| PRIMARY NODE                                                                      |
|  [Backend Client] ---> [Write WAL Buffer] ---> [WAL Writer / Flush to Disk]       |
|                                                       |                           |
|                                                       v                           |
|                                                [WalSender Proc]                   |
+-------------------------------------------------------|---------------------------+
                                                        | TCP Stream (LSN Payloads)
                                                        v
+-------------------------------------------------------|---------------------------+
| STANDBY NODE                                          |                           |
|                                                [WalReceiver Proc]                 |
|                                                       |                           |
|                                                       v                           |
|                                                [Write to WAL Disk]                |
|                                                       |                           |
|                                                       v                           |
|                                                [Startup Proc]                     |
|                                                (Applies redo to Shared Buffers)   |
+-----------------------------------------------------------------------------------+
```

1. **Physical Streaming Engine**:
   - **WalSender**: Thread/proses pada Primary yang membaca WAL langsung dari memory (`WAL buffers`) atau disk (`pg_wal`) dan mengirimkannya melalui koneksi TCP streaming ke Standby.
   - **WalReceiver**: Thread/proses pada Standby yang menerima bytes WAL dari WalSender dan menuliskannya ke storage lokal Standby.
   - **Startup Process**: Proses pada Standby yang membaca WAL lokal yang telah ditulis oleh WalReceiver dan mengeksekusi *redo logic* untuk mengaplikasikannya ke halaman data (`shared_buffers` / disk).

2. **Synchronous Replication & Commit Modes**:
   Parameter `synchronous_commit` menentukan kapan transaksi dianggap berhasil (`COMMIT`) oleh client:
   - `off`: Client menerima ACK segera setelah buffer transaksi di-commit ke RAM Primary (berisiko data loss jika Primary crash instan).
   - `local`: Client menerima ACK setelah WAL di-flush ke disk lokal Primary (`fdatasync`).
   - `remote_write`: Primary menunggu hingga Standby menerima WAL dan menuliskannya ke OS buffer cache Standby (belum tentu sampai ke disk fisik Standby).
   - `on`: Primary menunggu hingga Standby melakukan flush WAL ke disk fisiknya.
   - `remote_apply`: Primary menunggu hingga WAL diaplikasikan oleh *Startup Process* di Standby ke shared memory/disk Standby. Ini menjamin read-your-writes consistency pada query yang diarahkan ke Standby.

3. **Replication Slots & LSN (Log Sequence Number)**:
   LSN adalah integer 64-bit (`uint64`), direpresentasikan sebagai dua angka heksadesimal dipisahkan slash (misal `16/B374D890`), yang menyatakan byte offset absolut di dalam stream WAL sepanjang sejarah database.
   - `pg_create_physical_replication_slot('slot_name')`: Mencegah Primary mendaur ulang (*recycle/remove*) file WAL sebelum Standby yang diasosiasikan dengan slot tersebut mengonfirmasi bahwa LSN tersebut telah diterima (`restart_lsn`). 
   - *Bahaya*: Jika Standby mati dalam waktu lama, Primary akan terus mengumpulkan file WAL di `pg_wal` hingga disk penuh (*disk-full outage*), kecuali dibatasi oleh `max_slot_wal_keep_size`.

4. **Timeline Switch Engine**:
   Ketika Standby dipromosikan menjadi Primary baru, ia menaikkan *Timeline ID* (TLI) sebesar 1 (misal dari Timeline 1 ke Timeline 2).
   - PostgreSQL membuat file history (misal `00000002.history`) yang mencatat titik percabangan LSN (*fork point*).
   - Mekanisme ini mencegah anomali benturan WAL jika primary lama menyala kembali dan mencoba mengirimkan WAL baru di Timeline 1.

#### B. DCS-Driven Clustering (Patroni + etcd)
Patroni menggunakan algoritma konsensus Raft (melalui etcd) untuk mencegah *split-brain* (dua node mengira dirinya adalah Primary):
- Master/Leader lease memiliki nilai TTL (Time-To-Live, misal 10 detik).
- Leader node wajib memperbarui heartbeat (*lease renewal*) setiap interval `loop_wait`.
- Jika Leader gagal memperbarui lease sebelum TTL berakhir (karena OS freeze, network partition, atau OOM crash), node Standby yang memiliki posisi WAL terdepan (`lag` terendah terhadap LSN terakhir di etcd) akan memulai pemilihan Leader baru.
- **Node Fencing (Watchdog)**: Patroni menggunakan Linux kernel watchdog (`/dev/watchdog`) atau STONITH untuk me-reset mesin secara hardware jika Patroni daemon kehilangan komunikasi dengan etcd selama waktu tertentu, mencegah node zombie terus melayani transaksi tulis.

#### C. Declarative Partitioning Internals
PostgreSQL mengimplementasikan partisi deklaratif pada level relasional menggunakan *partition inheritance tree*:
- **Tuple Routing Engine**: Saat eksekusi `INSERT`, relasi root mengevaluasi nilai kolom partisi terhadap constraint boundaries dari child tables, lalu mengarahkan tuple ke child yang sesuai. Hal ini memperkenalkan overhead mikrodetik per baris; oleh karena itu, bulk-loading memerlukan strategi khusus.
- **Partition Pruning Engine**:
  - *Run-time Pruning*: Terjadi saat eksekusi query ketika parameter/prepared statement baru dievaluasi (`ExecInitModifyTable` / execution engine).
  - *Plan-time Pruning*: Optimizer membuang scanning child table sejak tahap pembentukan *query plan* jika klausa `WHERE` mengandung literal constant yang tidak memenuhi constraint partisi.

---

### 4. Why & What

| Pendekatan / Teknologi | What (Definisi & Cara Kerja) | Why (Alasan Penggunaan & Masalah yang Diselesaikan) |
| :--- | :--- | :--- |
| **Patroni vs Classic Warm Standby** | Patroni mengotomatisasi failover menggunakan consensus engine (etcd/Consul), sedangkan Warm Standby mengandalkan intervensi manual atau skrip bash `pg_isready` sederhana. | Menghilangkan *Human Error* dan downtime saat insiden tengah malam; mengeliminasi risiko *split-brain* via distributed locks dan hardware watchdog fencing. |
| **Transaction Pooling vs Session Pooling** | PgBouncer melepaskan koneksi backend PostgreSQL segera setelah transaksi (`COMMIT`/`ROLLBACK`) selesai, bukan menunggu client menutup koneksi TCP. | Mengurangi alokasi memory process PostgreSQL (setiap backend thread memakan 5-10MB RAM). Mengizinkan 10,000+ koneksi aplikasi dengan hanya ~100-200 koneksi riil ke PostgreSQL. |
| **Declarative vs Trigger-based Partitioning** | Partisi deklaratif didukung native oleh query engine PostgreSQL (PostgreSQL 10+), sedangkan trigger-based menggunakan PL/pgSQL function untuk merutekan data. | Deklaratif memungkinkan *partition pruning* dinamis secara native pada optimizer, performa `INSERT`/`COPY` jauh lebih tinggi, dan sintaks DDL yang terstandarisasi. |
| **`pg_partman` vs Cron Table Maintenance** | Ekstensi native untuk otomatisasi pre-creation partisi masa depan dan detasemen partisi kedaluwarsa secara otomatis. | Mencegah runtime crash akibat tuple routing gagal karena child partition belum dibuat oleh tim DBA manual saat pergantian bulan/hari. |

---

### 5. How (Workflow Detail)

#### Workflow Automated Failover dengan Patroni & etcd
1. **Normal State**:
   - Primary Node (Node A) memegang kunci `/service/batman/leader` di etcd cluster dengan TTL 10s.
   - Node A mengirimkan heartbeat setiap 2s untuk me-renew TTL.
   - Standby Node (Node B) streaming data dari Node A via physical replication slot.
   - HAProxy memeriksa endpoint Patroni REST API (`:8008/primary` -> 200 OK untuk Node A; `:8008/standby` -> 200 OK untuk Node B).
2. **Failure Detected**:
   - Node A mengalami kernel panic / network isolation.
   - Heartbeat ke etcd terhenti. Setelah 10 detik, TTL key `/service/batman/leader` hangus (*expired*).
   - Linux Watchdog di Node A mendeteksi Patroni tidak merespons, langsung memicu hard reboot pada Node A.
3. **Leader Election & Failover Execution**:
   - Node B mendeteksi lease leader kosong di etcd.
   - Node B memeriksa apakah ia memenuhi kriteria: LSN harus berada dalam ambang toleransi lag (`maximum_lag_on_failover`).
   - Node B memenangkan balapan penulisan kunci leader di etcd.
   - Patroni di Node B mengeksekusi: `pg_ctl promote`. PostgreSQL beralih ke Timeline baru (TLI + 1).
4. **Traffic Re-routing**:
   - HAProxy health check ke Node A `:8008/primary` menghasilkan connection refused / 503 Service Unavailable.
   - HAProxy health check ke Node B `:8008/primary` menghasilkan status 200 OK.
   - Trafik Write dialihkan ke Node B tanpa downtime sisi aplikasi (hanya koneksi in-flight yang di-reset).

```
   [Application Service]
            |
            v
     [HAProxy L4/L7]
      |            |
      | (Port 5000: Write -> :8008/primary)
      | (Port 5001: Read  -> :8008/standby)
      v            v
+-------------+  +-------------+
|   Node A    |  |   Node B    |
|  (Primary)  |  |  (Standby)  |
|   Patroni   |  |   Patroni   |
|      ^      |  |      ^      |
+------|------+  +------|------+
       |                |
       +-------+--------+
               |
               v
       [etcd Cluster] (Consensus Quorum)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pengadilan dan Dokumen Hukum (Timeline & LSN)
Bayangkan LSN adalah nomor halaman dan baris pada sebuah buku catatan hukum yang sangat panjang (*infinite ledger*). 
- **Physical Replication**: Panitera 2 (Standby) duduk menyalin setiap kata yang ditulis Panitera 1 (Primary) secara real-time.
- **Failover & Timeline**: Jika Panitera 1 pingsan, Pengadilan memutuskan Panitera 2 mengambil alih palu hakim. Namun, alih-alih melanjutkan buku yang sama, Panitera 2 membuka volume baru bertuliskan: *"Volume 2 (Timeline 2) - Dicabangkan dari Volume 1 Halaman 540, Baris 20 (LSN point)"*.
- Jika Panitera 1 siuman dan mencoba menulis lagi di Volume 1, Panitera 2 menolak tulisan itu karena Pengadilan telah mengadopsi Volume 2 secara sah melalui voting juri (etcd consensus).

#### Diagram Dekomposisi Sistem HA & Routing Enterprise

```
                                  [ CLIENT APPS ]
                                         |
                                         v
                         +-------------------------------+
                         |      KEEPALIVED (Virtual IP)  |
                         +-------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
             [ HAProxy Node 01 ]                 [ HAProxy Node 02 ]
             (Port 6432: Read/Write)             (Port 6433: Read-Only)
                       |                                   |
         +-------------+--------------------+              |
         |                                  |              |
         v                                  v              v
+------------------+              +------------------+     |
|   PgBouncer 01   |              |   PgBouncer 02   |     |
| (Transaction Pl) |              | (Transaction Pl) |     |
+------------------+              +------------------+     |
         |                                  |              |
         +-----------------+----------------+              |
                           |                               |
       +-------------------+-------------------------------+
       |                   |
       v                   v
+------------------+ +------------------+ +------------------+
|   PG NODE 01     | |   PG NODE 02     | |   PG NODE 03     |
|   (Leader)       | |   (Sync Standby) | |  (Async Standby) |
| Patroni + etcd   | | Patroni + etcd   | |  Patroni + etcd  |
| Watchdog Active  | | Watchdog Active  | |  Watchdog Active |
+------------------+ +------------------+ +------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Practical Example: Konfigurasi Patroni Produksi (`patroni.yml`)

```yaml
scope: pg-cluster-prod
namespace: /service
name: pg-node-01

etcd3:
  hosts:
    - 10.0.10.11:2379
    - 10.0.10.12:2379
    - 10.0.10.13:2379

restapi:
  listen: 10.0.10.21:8008
  connect_address: 10.0.10.21:8008

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576 # 1MB max lag tolerated
    synchronous_mode: true
    synchronous_mode_strict: false
    postgresql:
      use_pg_rewind: true
      use_slots: true
      parameters:
        shared_buffers: 16GB
        wal_level: replica
        max_wal_size: 16GB
        min_wal_size: 2GB
        checkpoint_completion_target: 0.9
        archive_mode: "on"
        archive_command: "pgbackrest --stanza=prod archive-push %p"
        hot_standby: "on"
        wal_keep_size: 4096MB
        max_replication_slots: 10
        max_connections: 500

  initdb:
    - encoding: UTF8
    - data-checksums

postgresql:
  listen: 10.0.10.21:5432
  connect_address: 10.0.10.21:5432
  data_dir: /var/lib/postgresql/16/main
  bin_dir: /usr/lib/postgresql/16/bin
  pgpass: /var/lib/postgresql/.pgpass
  authentication:
    replication:
      username: replicator
      password: SuperSecureReplicationPassword123!
    superuser:
      username: postgres
      password: MasterDBASecretPassword456!

watchdog:
  mode: automatic
  device: /dev/watchdog
  safety_margin: 5

tags:
  nofailover: false
  noloadbalance: false
  clonefrom: false
  nosync: false
```

#### B. Practical Example: Multi-Level Declarative Partitioning & `pg_partman`

```sql
-- 1. Setup ekstensi di schema khusus
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;

-- 2. Buat Parent Table: Range Partitioning berdasarkan Tanggal Transaksi
CREATE TABLE public.financial_ledgers (
    ledger_id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id INT NOT NULL,
    transaction_date TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payload JSONB,
    PRIMARY KEY (transaction_date, ledger_id, tenant_id)
) PARTITION BY RANGE (transaction_date);

-- 3. Register table ke pg_partman untuk partisi bulanan
-- Otomatis membuat 4 partisi ke depan dan 1 partisi masa lalu
SELECT partman.create_parent(
    p_parent_table => 'public.financial_ledgers',
    p_control => 'transaction_date',
    p_type => 'native',
    p_interval => 'monthly',
    p_premake => 4,
    p_start_partition => (CURRENT_DATE - INTERVAL '1 month')::text
);

-- 4. Verifikasi partisi yang ter-generate otomatis
SELECT inhrelid::regclass AS child_partition,
       pg_get_expr(c.relpartbound, c.oid) AS partition_expression
FROM pg_inherits i
JOIN pg_class c ON i.inhrelid = c.oid
WHERE inhparent = 'public.financial_ledgers'::regclass;

-- 5. Konfigurasi Maintenance Background Runner (Via Cron/pg_partman)
-- Jalankan fungsi ini via pg_cron atau crontab OS setiap hari jam 01:00 AM
-- SELECT partman.run_maintenance(p_analyze => false);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Transaksi Core-Banking 15,000 TPS (Bank Tier-1)
- **Konteks**: Sistem transaksi pembayaran instan nasional memproses rata-rata 8,000 TPS dan *peak* hingga 15,000 TPS. Menggunakan PostgreSQL 15 pada bare-metal server (256 Cores, 1TB RAM, NVMe Array PCIe 4.0).
- **Insiden Kegagalan Sistem**:
  - Pada jam operasional puncak, primary node mengalami *kernel lockup* pada controller NVMe.
  - Skrip automasi failover non-konsensus (lama) mempromosikan standby node B, namun network switch mengalami *flapping*, sehingga primary lama (Node A) hidup kembali 40 detik kemudian.
  - Terjadi **Split-Brain**: Aplikasi pembayaran gateway regional menulis ke Node A, sementara core engine menulis ke Node B. 1,420 transaksi mengalami benturan status saldo yang berbeda (divergent history).
- **Arsitektur Remediasi & Rekayasa Ulang**:
  1. **Migrasi ke Patroni + etcd Quorum**:
     - 3 Node DB bare-metal + 3 etcd node independen sebagai cluster quorum.
     - Implementasi `synchronous_mode: true` dengan `synchronous_commit: on`. Transaksi hanya dianggap sukses jika telah ter-replicate minimal ke salah satu node Standby sinkron.
  2. **Hardware Watchdog Hard-Fencing**:
     - Integrasi `/dev/watchdog` dengan modul IPMI (iLO/iDRAC). Jika Patroni hang lebih dari 10 detik, watchdog hardware mereset server (cut power) secara instan. Node A mustahil memproses data jika terisolasi dari etcd.
  3. **Traffic Splitting PgBouncer**:
     - Memasang PgBouncer lokal di tiap node database (UDS: Unix Domain Socket) untuk menghilangkan overhead koneksi TCP.
     - HAProxy layer membedakan Port 5432 (Write via master endpoint Patroni) dan Port 5433 (Read via replica endpoint).
- **Hasil**: Uji coba *chaos engineering* (pemutusan kabel fisik NIC Primary secara mendadak saat 12,000 TPS berlangsung) menghasilkan:
  - Failover tereksekusi dalam rentang **7.8 detik**.
  - **Zero Data Loss** ($RPO = 0$).
  - Integritas relasional terjaga secara mutlak tanpa inkonsistensi LSN.

---

### 9. Trade-offs

```
                       [Synchronous Replication]
                                  /\
                                 /  \
                                /    \
             Lower Latency <---+------> Strict Data Integrity (RPO=0)
                              /        \
                             /          \
                            /            \
             [Async Mode]  +--------------+  [Strict Sync Apply]
             (High TPS,                       (Sub-millisecond Loss
              Potential Loss)                  Impossible, High Latency)
```

| Dimensi Keputusan | Opsi A | Opsi B | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Commit Durability** | `synchronous_commit = off` | `synchronous_commit = on` | Opsi A menaikkan throughput tulis hingga 300% dan menurunkan disk I/O wait, tetapi insiden crash server mengakibatkan hilangnya beberapa ratus millisecond transaksi terakhir ($RPO > 0$). Opsi B menjamin persistensi disk, tetapi latency commit terikat langsung pada performa fsync storage. |
| **Replication Sync Target** | `synchronous_commit = on` (Standby) | `synchronous_commit = remote_apply` | `remote_apply` menjamin kueri baca di replica langsung mencerminkan data terbaru (*No Replication Lag Anomaly*), namun write latency meningkat drastis karena Primary harus menunggu engine replay Standby selesai memproses WAL. |
| **Partition Granularity** | Daily Partitioning | Monthly Partitioning | Daily membatasi ukuran indeks sehingga muat di RAM (Shared Buffers) dan mempercepat drop data usang, namun menyebabkan katalog PostgreSQL membengkak jika ada ribuan partisi, menurunkan performa Query Planner (*Plan Cache Bloat*). |
| **Connection Pooling** | Session Pooling | Transaction Pooling | Transaction pooling mengizinkan konkurensi ekstrem, tetapi menonaktifkan fitur level-sesi seperti `LISTEN/NOTIFY`, Prepared Statements konvensional (`PREPARE`), dan manipulasi runtime `SET LOCAL` yang persisten. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Replication Slot Bloat yang Mematikan Primary
- **Gejala**: Disk Primary tiba-tiba terisi 100% pada direktori `pg_wal`, database masuk ke mode *read-only emergency*, down total.
- **Root Cause**: Standby node crash atau di-decommission tanpa menghapus physical replication slot-nya di primary. Primary menahan semua WAL sejak LSN terakhir Standby tersebut hidup.
- **Troubleshooting & Fix**:
  ```sql
  -- Identifikasi slot yang bermasalah dan hitung lag bytes-nya
  SELECT slot_name, active, 
         pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS lag_size
  FROM pg_replication_slots
  ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;

  -- Solusi Instan: Hapus slot yang tidak aktif
  SELECT pg_drop_replication_slot('abandoned_standby_slot');
  ```
  *Mitigasi Preventif*: Wajib set `max_slot_wal_keep_size = 64GB` di `postgresql.conf` agar Primary otomatis membatalkan slot daripada disk habis.

#### 2. Generic Query Plan Gagal Menerapkan Dynamic Partition Pruning
- **Gejala**: Query pada tabel partisi berjalan lambat secara tiba-tiba ketika dieksekusi melalui Prepared Statement atau ORM (Hibernate, Prisma, GORM).
- **Root Cause**: Prepared statement PostgreSQL beralih dari *Custom Plan* ke *Generic Plan* pada eksekusi ke-6. Generic plan terkadang mengasumsikan parameter bernilai dinamis sehingga optimizer membatalkan *Plan-Time Pruning* dan beralih ke scan seluruh partisi.
- **Fix**:
  ```sql
  -- Evaluasi apakah pruning berjalan
  EXPLAIN (ANALYZE, BUFFERS) 
  SELECT * FROM financial_ledgers WHERE transaction_date >= '2024-01-01' AND transaction_date < '2024-02-01';
  
  -- Paksa engine menggunakan custom plan jika runtime pruning gagal
  SET plan_cache_mode = force_custom_plan;
  ```

#### 3. PgBouncer Prepared Statement Crash
- **Gejala**: Aplikasi menghasilkan error `ERROR: prepared statement "S_1" does not exist` saat memakai PgBouncer transaction pooling mode.
- **Root Cause**: Driver aplikasi (misal JDBC, node-postgres) membuat prepared statement pada satu server-backend, lalu mengirim instruksi eksekusi statement tersebut ke PgBouncer. PgBouncer merutekannya ke backend PostgreSQL lain yang tidak memiliki metadata query plan tersebut.
- **Fix**: Nonaktifkan prepared statement di level client driver (misal: JDBC set `prepareThreshold=0`), ATAU gunakan PgBouncer versi 1.21+ dengan fitur native `max_prepared_statements = 100`.

---

### 11. Best Practices (Production Checklist)

#### OS & Kernel Parameters (`/etc/sysctl.d/99-postgresql.conf`)
- [ ] `vm.overcommit_memory = 2`: Mencegah OOM-Killer mematikan proses PostgreSQL secara acak.
- [ ] `vm.overcommit_ratio = 80`: Menyetel alokasi virtual memory safe limit.
- [ ] `vm.swappiness = 1`: Mencegah kernel menukar (swap) memori Shared Buffers ke swap disk.
- [ ] `net.core.somaxconn = 4096`: Memperluas antrean TCP connection listen.

#### Database Storage & Engine Settings (`postgresql.conf`)
- [ ] File system menggunakan XFS dengan mount options: `noatime,nodiratime,logbufs=8,logbsize=256k`.
- [ ] Direktori `pg_wal` dipisahkan pada disk array fisik / NVMe terpisah dari `base` data directory.
- [ ] `data_checksums = on`: Wajib aktif sejak `initdb` untuk deteksi *silent data corruption* / *bit rot*.
- [ ] `track_io_timing = on`: Untuk observabilitas latency read/write block storage di `pg_stat_database`.

#### Partition Maintenance
- [ ] Tidak membuat lebih dari 1,000 partisi aktif per tabel induk guna menghindari degradasi memori pada dynamic optimizer.
- [ ] Indeks lokal dibuat seragam pada setiap partisi anak untuk menjamin integritas vacuuming index scan.

---

### 12. Hands-on Practice

Simpan seluruh file instruksi, script, dan konfigurasi ini ke dalam direktori lokal: `hands-on/m02/`.

#### Langkah 1: Siapkan Lingkungan Simulasi Multi-Node
Buat file `hands-on/m02/docker-compose.yml` untuk memetakan arsitektur etcd cluster dan node DB.

```yaml
version: '3.8'

services:
  etcd1:
    image: bitnami/etcd:3.5.11
    environment:
      - ALLOW_NONE_AUTHENTICATION=yes
      - ETCD_ADVERTISE_CLIENT_URLS=http://etcd1:2379
      - ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379
    networks:
      patroni_net:
        ipv4_address: 172.28.0.10

  haproxy:
    image: haproxy:2.8
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    ports:
      - "5000:5000" # Write Endpoint
      - "5001:5001" # Read-Only Endpoint
      - "7000:7000" # Stats
    networks:
      patroni_net:
        ipv4_address: 172.28.0.100

networks:
  patroni_net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

#### Langkah 2: Buat Konfigurasi HAProxy Routing
Simpan file `hands-on/m02/haproxy.cfg`. HAProxy akan melakukan HTTP health check ke REST API Patroni (port 8008) untuk menentukan status peran node.

```haproxy
global
    maxconn 4096

defaults
    log global
    mode tcp
    timeout connect 3s
    timeout client 1h
    timeout server 1h

listen stats
    mode http
    bind *:7000
    stats enable
    stats uri /

frontend pg_write_front
    bind *:5000
    default_backend pg_write_back

backend pg_write_back
    mode tcp
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 3s fall 3 rise 2 on-marked-down shutdown-sessions
    server pg1 172.28.0.21:5432 maxconn 200 check port 8008
    server pg2 172.28.0.22:5432 maxconn 200 check port 8008

frontend pg_read_front
    bind *:5001
    default_backend pg_read_back

backend pg_read_back
    mode tcp
    balance roundrobin
    option httpchk GET /standby
    http-check expect status 200
    default-server inter 3s fall 3 rise 2
    server pg1 172.28.0.21:5432 maxconn 200 check port 8008
    server pg2 172.28.0.22:5432 maxconn 200 check port 8008
```

#### Langkah 3: Skrip Pengujian Latensi Replikasi & Partition Verification
Simpan file `hands-on/m02/verify_ha_and_partition.sh` dan jalankan:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "============================================="
echo "[1] MEMERIKSA STATUS REPLIKASI DARI PRIMARY"
echo "============================================="
psql -h localhost -p 5000 -U postgres -d postgres -c "
SELECT 
    client_addr, 
    application_name, 
    state, 
    sync_state, 
    sync_priority,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS sent_lag_bytes,
    pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag_bytes,
    pg_wal_lsn_diff(write_lsn, flush_lsn) AS flush_lag_bytes,
    pg_wal_lsn_diff(flush_lsn, replay_lsn) AS replay_lag_bytes
FROM pg_stat_replication;
"

echo "============================================="
echo "[2] VALIDASI PARTITION PRUNING EXECUTION PLAN"
echo "============================================="
psql -h localhost -p 5000 -U postgres -d postgres -c "
EXPLAIN ANALYZE
SELECT * FROM financial_ledgers
WHERE transaction_date >= '2026-03-01 00:00:00+00' 
  AND transaction_date < '2026-03-02 00:00:00+00';
"
```

---

### 13. Exercise

#### Level Easy
Buat sebuah tabel partisi declarative `audit_logs` berdasarkan kolom `created_at` (Range Partitioning). Buat secara manual 3 buah partisi untuk bulan Januari, Februari, dan Maret 2026. Lakukan verifikasi bahwa query yang mencari baris pada bulan Februari 2026 hanya memindai (*scan*) tabel partisi bulan Februari saja.

#### Level Medium
Konfigurasikan instance PgBouncer di depan PostgreSQL.
- Set mode: `pool_mode = transaction`.
- Tetapkan batasan `max_client_conn = 1000`, `default_pool_size = 20`, dan `reserve_pool_size = 5`.
- Tulis skrip bash benchmarking menggunakan `pgbench` untuk mensimulasikan 500 klien konkuren selama 60 detik. Analisis metrik koneksi melalui query admin PgBouncer: `SHOW POOLS;` dan `SHOW STATS;`.

#### Level Hard
Rancang skenario failover terencana (*switchover*) pada klaster Patroni tanpa menimbulkan *error disconnect* permanen pada aplikasi:
- Eksekusi switchover menggunakan perintah `patronictl switchover --master <current_primary> --candidate <target_standby>`.
- Amati dan catat transisi Timeline ID di PostgreSQL log file (`0000000X.history`).
- Buktikan bahwa replikasi fisik antara leader baru dan node follower yang tersisa tetap sinkron tanpa perlu melakukan `pg_basebackup` ulang (memanfaatkan `pg_rewind`).

---

### 14. Challenge

**Studi Kasus Arsitektur: "The 100 Terabyte Telemetry Migration Disaster"**

Anda dipekerjakan sebagai Principal Database Architect oleh sebuah perusahaan IoT global. Mereka memiliki satu tabel monolitik PostgreSQL non-partisi bernama `iot_sensor_data` berukuran 120 TB dengan 4 miliar baris yang terus bertambah 50 juta baris per hari. Tabel ini memiliki 4 buah b-tree index.

**Kondisi Kritis Saat Ini**:
1. Vacuuming memakan waktu 4 hari hingga selesai, memicu I/O saturation terus-menerus.
2. Query agregasi waktu sering kali melakukan sequential scan yang berujung timeout.
3. Bisnis mengharuskan sistem beroperasi 24/7. *Downtime maintenance window* yang diizinkan untuk cut-over maksimal **15 menit**.
4. Tidak tersedia ruang disk storage tambahan yang sanggup menampung 100% kloningan tabel (storage tersisa hanya 35 TB).

**Tugas Anda**:
Rancang strategi rekayasa komprehensif untuk memigrasikan tabel ini menjadi **Declarative Partitioning mingguan**. 
Rancangan harus mencakup:
- Strategi fragmentasi data tanpa kehabisan sisa ruang storage 35 TB (*in-place piecemeal backfill*).
- Penanganan physical replication lag ke node Standby selama proses backfill berlangsung agar tidak memicu bloat WAL.
- Penggunaan skrip SQL, background worker, trigger, atau logical replication trick yang menjamin zero data loss dan hanya membutuhkan 15 menit write-lock cut-over.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. Apa fungsi esensial dari file `.history` yang muncul di direktori `pg_wal` setelah sebuah Standby dipromosikan menjadi Primary?
2. Dalam setting `synchronous_commit = remote_write`, kondisi fisik apa yang harus terpenuhi di Standby sebelum Primary mengembalikan status COMMIT OK ke klien?
3. Sebutkan kelemahan utama penggunaan physical replication slot jika tidak dibarengi dengan monitoring disk storage yang ketat!
4. Mengapa kita tidak bisa menjalankan perintah `LISTEN` dan `NOTIFY` jika PgBouncer berjalan di bawah `pool_mode = transaction`?
5. Apa perbedaan fundamental antara *Plan-time partition pruning* dan *Run-time partition pruning*?

#### B. Pertanyaan Intermediate
1. Mengapa algoritma konsensus seperti etcd atau Consul mutlak diperlukan dalam mendesain automated failover PostgreSQL, dibandingkan hanya menggunakan cron skrip checking antar node?
2. Jelaskan bagaimana kernel Linux Watchdog (`/dev/watchdog`) memitigasi anomali *Split-Brain* pada implementasi HA Patroni!
3. Jika Anda memiliki tabel partisi declarative dan Anda mengeksekusi perintah `UPDATE` yang mengubah nilai kolom partisi dari suatu baris hingga melewati batas partisi asalnya, bagaimana PostgreSQL menangani hal tersebut secara internal?
4. Apa kegunaan utilitas `pg_rewind` dan pada kondisi apa `pg_rewind` gagal mengeksekusi tugasnya sehingga membutuhkan basebackup ulang?
5. Bagaimana formula matematis/metode mengekstrak *byte lag* nyata antara Primary dan Standby menggunakan fungsi `pg_wal_lsn_diff`?

#### C. Skenario Kasus Produksi
1. **Skenario 1**: Node Standby Anda tertinggal (lagging) sebesar 500GB dari Primary karena terjadi lonjakan transaksi batch di Primary. Metrik CPU dan RAM Standby normal, namun disk write utilization di Standby mencapai 100% konstan. Parameter apa di level storage dan engine database yang harus diinvestigasi dan di-tuning untuk mempercepat replay proses WAL?
2. **Skenario 2**: Sistem HA Patroni Anda mendadak melakukan failover yang tidak diinginkan (*false-positive failover*) setiap hari tepat pada pukul 03:00 pagi, padahal tidak ada server yang mati. Apa kecurigaan utama Anda terkait beban batch background di level OS/Database dan bagaimana cara membuktikannya via log analysis?
3. **Skenario 3**: Sebuah query `SELECT` join antara tabel transaksi terpartisi bulanan dengan tabel dimensi pengguna (`users`) mendadak melakukan scan ke seluruh partisi masa lalu (10 tahun partisi ter-scan), padahal predikat `WHERE transaction_date >= NOW() - INTERVAL '7 days'` sudah diterapkan. Analisis penyebab kegagalan partition pruning pada execution plan tersebut!

---

### Kunci Jawaban Evaluasi

#### Jawaban Basic
1. **Fungsi file `.history`**: Mencatat histori percabangan Timeline ID (TLI), merekam pada LSN berapa timeline baru terbentuk dan mengapa percabangan terjadi, sehingga server-server PostgreSQL lain memahami silsilah replikasi dan tidak saling menimpa data yang berbeda.
2. **Kondisi `remote_write`**: Primary mengembalikan sukses commit jika Standby telah menerima WAL via network dan menulisnya ke OS buffer Standby (memanggil `write()`), tanpa perlu menunggu sistem operasi Standby melakukan persistensi fisik ke disk (`flush`/`fsync`).
3. **Kelemahan Physical Replication Slot**: Jika Standby node down atau tidak sinkron, Primary akan menahan penghapusan file WAL di direktori `pg_wal` secara permanen. Hal ini dapat menghabiskan seluruh disk storage Primary yang berujung pada disk full crash (DB freeze).
4. **Alasan PgBouncer Transaction Mode menolak `LISTEN/NOTIFY`**: Mekanisme `LISTEN/NOTIFY` mengikat connection socket ke sesi backend spesifik. Pada transaction pooling, server connection dilepaskan ke pool begitu transaksi commit, sehingga notifikasi asinkronus yang dikirim ke backend tersebut tidak dapat diteruskan ke klien asli.
5. **Perbedaan Pruning**: Plan-time pruning terjadi pada fase kompilasi query plan ketika predikat literal/konstan sudah diketahui. Run-time pruning terjadi pada tahap inisialisasi atau eksekusi plan saat klausa filter melibatkan nilai dinamis, ekspresi runtime, atau parameterized queries (`$1`).

#### Jawaban Intermediate
1. **Pentingnya Konsensus (DCS)**: Mencegah *Network Partition Divergence*. Tanpa DCS, jika link jaringan antara Primary dan Standby terputus tapi kedua server tetap hidup, skrip sederhana di Standby akan mengira Primary mati lalu mempromosikan dirinya. Hal ini memicu dua Primary aktif secara simultan (*Split-Brain*). DCS menjamin bahwa hanya node yang memiliki komunikasi quorum (mayoritas $N/2 + 1$) yang berhak memegang lock Leader.
2. **Mitigasi Watchdog**: Patroni secara berkala memperbarui software timer ke kernel watchdog. Jika Patroni freeze (misal network hang atau IO locking) dan gagal memperbarui heartbeat etcd, watchdog tidak menerima sinyal "ping" dalam jangka waktu safety margin. Kernel Watchdog akan langsung mereset mesin di level hardware (mirip tombol hard reset ditekan), mematikan node lama secara paksa sebelum node baru dipromosikan.
3. **Update Kolom Partisi**: Sejak PostgreSQL 11+, tuple routing engine akan memperlakukan operasi tersebut sebagai transaksi atomik: menghapus baris dari child table lama (`DELETE`) dan memasukkan baris baru ke child table target yang sesuai (`INSERT`). Jika foreign key atau unique constraint tidak lengkap di partisi baru, operasi akan gagal (error).
4. **Fungsi `pg_rewind`**: Mengidentifikasi titik divergensi LSN antara klaster lama dan klaster baru, lalu mengunduh blok-blok data yang berubah dari Primary baru untuk disalin ke Primary lama yang tertinggal, sehingga Primary lama bisa langsung menjadi Standby tanpa restore dari basebackup awal. *Gagal jika*: Parameter `wal_log_hints` tidak aktif sejak awal, data checksums off, atau WAL Primary lama telah tertimpa/dihapus sebelum titik percabangan (*divergence point*).
5. **Ekstraksi Byte Lag**:
   ```sql
   SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS bytes_behind
   FROM pg_stat_replication;
   ```
   Fungsi ini mengurangkan representasi numerik 64-bit dari dua LSN, menghasilkan selisih riil dalam satuan byte.

#### Jawaban Kasus Produksi
1. **Analisis Skenario 1**: 
   - Standby I/O bottleneck saat replay biasanya disebabkan oleh operasi disk commit/fsync yang terfragmentasi, pembacaan page dari disk yang tidak ada di RAM, atau `max_parallel_workers` yang kurang.
   - *Solusi & Tuning*: Pastikan `shared_buffers` Standby cukup besar untuk menampung working set. Naikkan `max_parallel_maintenance_workers`. Set parameter storage disk: periksa apakah disk IOPS limit tercapai (misal throttling cloud disk EBS/PD). Matikan `synchronous_commit` khusus pada recovery process jika diizinkan, atau gunakan hardware caching controller berkecepatan tinggi.
2. **Analisis Skenario 2**:
   - Terjadi *False Failover* jam 03:00 pagi biasanya akibat cron job intensif seperti OS backup (`tar`, `rsync`), batch maintenance, atau `pg_dump` besar yang memonopoli storage I/O atau memicu network saturation.
   - Akibat I/O hang, Patroni daemon tidak kebagian CPU timeslice untuk memperbarui lease ke etcd sebelum nilai `ttl` (10s) berakhir.
   - *Validasi*: Periksa `syslog` / `journalctl` jam 03:00 untuk melihat aktivitas kernel I/O wait spike dan OOM events. Naikkan nilai `loop_wait` dan `ttl` di Patroni, prioritaskan Patroni daemon menggunakan `nice -n -20` atau `chrt` (real-time process scheduling), serta jadwalkan job backup agar throttled.
3. **Analisis Skenario 3**:
   - Optimizer gagal melakukan pruning karena penggunaan fungsi volatile atau perbandingan tipe data implisit (*type casting mismatch*).
   - Fungsi `NOW()` dievaluasi sebagai `STABLE` di query planner, namun jika fungsi tersebut dibungkus dalam logic tertentu atau kolom `transaction_date` berformat `DATE` sementara filter berupa `TIMESTAMPTZ`, PostgreSQL akan menyuntikkan casting implicit function di sisi kolom: `WHERE transaction_date::timestamp >= ...`.
   - Hal ini membuat optimizer menganggap predikat tersebut sebagai *expression filter* bukan *range boundary key*, yang melumpuhkan kemampuan *Plan-Time Partition Pruning*. 
   - *Solusi*: Pastikan tipe data predikat sama persis tanpa casting di level kolom, atau pastikan parameter yang dipassing bersifat strictly immutable pada prepared query.

---

### 16. Summary
- **High Availability Modern** pada PostgreSQL tidak boleh bertumpu pada health check manual. Pendekatan standar industri enterprise mewajibkan implementasi state machine berbasis konsensus terdistribusi (Patroni + etcd) dengan node fencing fisik/watchdog untuk mengeliminasi risiko split-brain.
- **Physical Streaming Replication** bekerja pada level LSN dan WAL record. Konfigurasi `synchronous_commit` menentukan posisi kompromi arsitektural antara throughput latensi minimum (mode `off`/`local`) melawan integritas absolut tanpa kehilangan data (mode `on`/`remote_apply`).
- **Connection Pooling Terdistribusi** (PgBouncer) merupakan prasyarat wajib untuk arsitektur PostgreSQL skala besar guna memitigasi connection exhaustion dan memory exhaustion melalui *transaction pooling*, dengan catatan aplikasi harus dirancang kompatibel tanpa state sesi lokal.
- **Declarative Partitioning** dikombinasikan dengan automasi siklus hidup (`pg_partman`) memberikan skalabilitas horizontal untuk memanipulasi dataset ultra-besar (orde Terabyte). Efektivitas performanya bergantung penuh pada keberhasilan optimizer melakukan *Partition Pruning*, yang menuntut keselarasan struktur indeks, akurasi tipe data, dan perancangan predikat kueri yang terstandarisasi.