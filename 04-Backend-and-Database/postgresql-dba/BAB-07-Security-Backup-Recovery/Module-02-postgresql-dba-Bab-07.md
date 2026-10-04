# BAB 07: Security, Backup, and Recovery
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Mengimplementasikan Arsitektur Backup Fisik Tingkat Lanjut**: Menguasai arsitektur Continuous Archiving, Block-Level Incremental Backup, dan Synthetic Full Backup menggunakan tool standar industri (*pgBackRest*).
- **Mengeksekusi Disaster Recovery Presisi Tinggi**: Melakukan *Point-In-Time Recovery* (PITR) hingga level LSN (*Log Sequence Number*) dan pemulihan percabangan *timeline* pasca-insiden korupsi data atau *operator error*.
- **Mendesain Arsitektur Keamanan Bertingkat (*Defense-in-Depth*)**: Mengonfigurasi enkripsi transport (mTLS/SSL verify-full), *Row-Level Security* (RLS) multi-tenant, autentikasi SCRAM-SHA-256, serta audit trail terstruktur menggunakan ekstensi `pgaudit`.
- **Mengoptimalkan Trade-off RPO/RTO**: Menyeimbangkan *Recovery Point Objective* (RPO) mendekati nol detik dan *Recovery Time Objective* (RTO) dalam hitungan menit tanpa mendegradasi performa I/O write pada node produksi.
- **Mengotomatisasi Validasi & Pengujian Backup**: Membangun pipeline continuous recovery verification untuk memastikan integritas backup tanpa downtime.

---

### 2. Prerequisite

Peserta wajib memiliki pemahaman mendalam tentang:
- Arsitektur internal PostgreSQL: Memori (`shared_buffers`, `wal_buffers`), proses latar belakang (`checkpointer`, `walwriter`, `archiver`), dan struktur on-disk PostgreSQL data directory ($PGDATA).
- Operasi dasar Write-Ahead Logging (WAL) dan siklus Checkpoint.
- Administrasi sistem Linux tingkat lanjut: POSIX permissions, systemd, Block storage I/O, serta jaringan TCP/IP.
- Dasar bahasa SQL dan administrasi DDL/DCL PostgreSQL.

---

### 3. Concept & Internal Architecture

#### 3.1. Anatomi dan Lifecycle Write-Ahead Log (WAL) dalam Konteks Recovery
PostgreSQL menjamin durabilitas transaksi (ACID) melalui mekanisme Write-Ahead Logging. Setiap modifikasi data page di `shared_buffers` dicatat terlebih dahulu ke dalam `wal_buffers` sebagai record WAL sebelum dirty page tersebut di-flush ke disk oleh *checkpointer* atau *bgwriter*.

```
   Transaksi DML
         │
         ▼
┌─────────────────┐       Commit Transaction
│   wal_buffers   ├──────────────────────────────┐
└────────┬────────┘                              │
         │ walwriter / synchronous flush         ▼
         ▼                              ┌──────────────────┐
┌─────────────────┐                     │ ACK Client       │
│  pg_wal (Disk)  │                     └──────────────────┘
└────────┬────────┘
         │ Archive Command / Streaming
         ▼
┌─────────────────────────┐
│ Backup Repository (NFS/ │
│ S3 / Dedicated Storage) │
└─────────────────────────┘
```

Setiap record WAL memiliki identitas unik berupa **64-bit integer** yang disebut **Log Sequence Number (LSN)**. LSN merepresentasikan offset byte absolut dalam stream transaksi database secara keseluruhan. Struktur internal LSN: `X/YYYYYYYY` (misal: `16/B375D8F0`), di mana angka pertama adalah nomor file logik dan angka kedua adalah offset byte dalam file tersebut.

Pada skenario Disaster Recovery:
1. **Base Backup** menyediakan snapshot konsisten dari physical data files ($PGDATA) pada titik awal backup (`pg_start_backup()`).
2. Snapshot fisik tersebut berada dalam keadaan *inconsistent/dirty* saat proses copy berlangsung.
3. Database mencapai kondisi *consistent* hanya jika seluruh WAL dari rentang backup (`BACKUP_START_LSN` hingga `BACKUP_STOP_LSN`) di-replay sepenuhnya (*Redo Loop*).

#### 3.2. Timeline ID dan Timeline Branching
Ketika database melakukan recovery hingga target tertentu dan dipromosikan menjadi read-write cluster baru, PostgreSQL membuat **Timeline ID baru**. Timeline mencegah cluster menimpa stream WAL yang ada jika terjadi divergensi data.

```
Timeline 1: ───[LSN A]───[LSN B (Target PITR)]───[LSN C (Drop Table Fatal)]
                                 │
                                 └── (Promote / New Timeline)
Timeline 2:                      └───[LSN B+1]───[LSN D (Data Baru)]
```

Setiap pergantian timeline menghasilkan file riwayat `.history` (misal: `00000002.history`) yang mencatat titik percabangan (*switch point* LSN). Tanpa pemahaman timeline, sistem backup enterprise akan gagal melakukan replay WAL saat transisi failover HA terjadi.

#### 3.3. Block-Level Incremental Backup vs Logical Dump
- **Logical Backup (`pg_dump`)**: Melakukan freeze data melalui snapshot transaction, mengekspor skema dan row ke bentuk SQL/Custom Dump. Kelemahan: I/O tinggi, memakan resource CPU untuk dekonstruksi/rekonstruksi data, tidak menangkap WAL, dan RTO tidak realistis untuk skala multi-terabyte (> 1 TB).
- **Physical Backup (`pgBackRest` / `pg_basebackup`)**: Menyalin block raw data sebesar 8KB langsung dari disk. `pgBackRest` melangkah lebih jauh dengan membaca page checksums dan membandingkannya per block (bukan per file) terhadap backup sebelumnya. Ini memungkinkan pembuatan **Block-Level Incremental Backup** yang secara drastis memangkas bandwidth, disk usage, dan RTO.

#### 3.4. Row-Level Security (RLS) & Query Engine Rewrite
Secara internal, ketika RLS diaktifkan (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`), PostgreSQL *Query Optimizer / Rewriter* mengintersepsi Parse Tree dari query pengguna. Engine menyuntikkan ekspresi Boolean keamanan (*security quals*) secara implisit ke dalam `WHERE` clause:

$$\text{Query Akhir} = \text{Query Asli} \land (\text{Security Policy Expression})$$

Operasi ini dieksekusi dengan overhead minim pada CPU selama policy expression didukung oleh index yang relevan.

---

### 4. Why & What

| Fitur / Komponen | Apa Itu? | Mengapa Dibutuhkan di Skala Enterprise? |
| :--- | :--- | :--- |
| **Continuous Archiving** | Streaming file WAL (16MB chunks) ke storage terisolasi sesaat setelah file tertutup. | Menjamin zero-data-loss (RPO $\approx$ 0) tanpa perlu menunggu backup harian berjalan. |
| **PITR (Point-In-Time Recovery)** | Mekanisme memutar ulang transaksi database hingga titik waktu/LSN mikrodetik tertentu. | Menyelamatkan data dari skenario human error (contoh: `TRUNCATE TABLE` tanpa klausa filter pada jam sibuk). |
| **pgBackRest** | Backup engine modular berkinerja tinggi yang mendukung multi-repo, parallel compression, dan async archiving. | Mengatasi limitasi single-threaded `pg_basebackup`; mendukung offloading backup ke storage S3/GCS secara native. |
| **pgAudit** | Ekstensi auditing yang mencatat eksekusi query spesifik langsung dari parser layer. | Memenuhi standar kepatuhan regulasi finansial (PCI-DSS, ISO 27001, SOC 2) dengan membedakan DDL, read, dan write operations. |
| **mTLS & SCRAM-SHA-256** | Otentikasi dua arah menggunakan sertifikat X.509 dan hashing password berbasis cryptographic salt & iterations. | Mencegah Man-In-The-Middle (MITM) attack dan brute-force hash dumping dari memory dump. |

---

### 5. How (Workflow Detail)

#### 5.1. Alur Transaksi Backup & Continuous Archiving
```
[PostgreSQL Primary Engine]
  │
  ├─ 1. Modifikasi Data Page (LSN bertambah)
  ├─ 2. WAL Segment terisi penuh (16MB)
  ├─ 3. Archiver Process memanggil archive_command / pgBackRest
  │      │
  │      ▼
  │   [pgBackRest Local Engine]
  │      │
  │      ├─ 4. Parallel Compression (lz4/zstd)
  │      ├─ 5. Verifikasi Checksum Block
  │      └─ 6. Push async ke Storage Repository (S3/MinIO)
  │
  ▼
[PostgreSQL Archive Repository]
```

#### 5.2. Alur Eksekusi Point-In-Time Recovery (PITR)
```
[Stop PostgreSQL Cluster]
  │
  ▼
[Hapus / Isolasi $PGDATA yang Rusak]
  │
  ▼
[pgBackRest Restore (Target: specific timestamp/LSN)]
  │ ├─ Tarik Full/Differential/Incremental Backup terdekat
  │ └─ Restorasi block file data ke $PGDATA
  │
  ▼
[Generate File `recovery.signal` di root $PGDATA]
  │
  ▼
[Set Konfigurasi Recovery di postgresql.conf]
  │ ├─ restore_command = 'pgbackrest --stanza=prod archive-get %f "%p"'
  │ ├─ recovery_target_time = '2024-03-30 14:25:00.000000+07'
  │ └─ recovery_target_action = 'promote' (atau 'pause')
  │
  ▼
[Start PostgreSQL Cluster]
  │ ├─ Membaca recovery.signal
  │ ├─ Replay Base Backup
  │ ├─ Fetch WAL bertahap via restore_command
  │ ├─ Replay LSN hingga target tercapai
  │ ├─ Create New Timeline (.history file ditulis)
  │ └─ Hapus recovery.signal
  │
  ▼
[PostgreSQL Read-Write Ready pada Timeline Baru]
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Black Box Penerbangan & Time Travel
- **Base Backup** adalah foto menyeluruh dari kondisi pesawat sebelum lepas landas.
- **WAL Files** adalah rekaman audio dan instrumen (*Black Box*) yang mencatat setiap milidetik pergerakan kemudi dan tombol.
- **PITR** adalah mesin pemutar waktu. Jika pesawat mengalami anomali pada pukul 14:30:15, kita menyetel ulang pesawat ke foto awal pukul 08:00, lalu memutar ulang rekaman instrumen secara tepat hingga pukul 14:30:14, lalu mengambil alih kendali di jalur baru tanpa insiden tersebut.

#### Diagram Topologi: Enterprise Backup & Security Perimeter
```
               +---------------------------------------------------+
               |             DMZ / Application Network             |
               +---------------------------------------------------+
                                         │
                                         │ mTLS (TLS 1.3)
                                         │ SCRAM-SHA-256 Auth
                                         ▼
+---------------------------------------------------------------------------------+
| Data Tier (Hardened Network)                                                    |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | PostgreSQL Primary Node                                                 |   |
|   |                                                                         |   |
|   |  +--------------------+   RLS Policies  +----------------------------+  |   |
|   |  | In-Memory Engine   | --------------> | Disk Engine ($PGDATA)      |  |   |
|   |  | (Shared Buffers)   |                 | (Page Checksums Enabled)   |  |   |
|   |  +--------------------+                 +----------------------------+  |   |
|   |            │                                           │                |   |
|   |            │ Write Changes                             │ Read Raw Data  |   |
|   |            ▼                                           ▼                |   |
|   |  +--------------------+                 +----------------------------+  |   |
|   |  | WAL Writer Buffer  |                 | pgBackRest Agent Process   |  |   |
|   |  | (pg_wal directory) |                 | (Multi-Threaded / Zstandard|  |   |
|   |  +--------------------+                 +----------------------------+  |   |
|   |            │                                           │                |   |
|   |            │ pgBackRest archive-push                   │                |   |
|   |            └───────────────────────┐   ┌───────────────┘                |   |
|   +------------------------------------│───│--------------------------------+   |
+----------------------------------------│───│------------------------------------+
                                         │   │
                                         │   │ TLS Streaming
                                         ▼   ▼
+---------------------------------------------------------------------------------+
| Dedicated Storage Repository Tier (S3 API / MinIO / Air-Gapped Appliance)       |
|                                                                                 |
|  +-------------------------------------+   +---------------------------------+  |
|  | /archive/stanza/ (WAL Segments)     |   | /backup/stanza/ (Full, Diff,    |  |
|  | [00000001000000A100000045.zst...]   |   |  Incr Manifests & Data Blocks)  |  |
|  +-------------------------------------+   +---------------------------------+  |
+---------------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Native Continuous Archiving Setup
Konfigurasi dasar bawaan PostgreSQL tanpa tool pihak ketiga.

`postgresql.conf`:
```ini
# Basic WAL Archiving Setup
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /mnt/backup/wal/%f && cp %p /mnt/backup/wal/%f'
```

#### 7.2. Practical Example: Enterprise-Grade Implementation

##### A. Hardening Autentikasi dan Transport Layer (`pg_hba.conf`)
Menolak koneksi plain text, mewajibkan sertifikat klien (mTLS) dan enkripsi SCRAM-SHA-256.

```conf
# TYPE  DATABASE        USER            ADDRESS                 METHOD
# Internal replication channel via TLS
hostssl replication     repuser         10.200.10.0/24          scram-sha-256 clientcert=verify-full

# Enterprise Application connections with strict mTLS
hostssl production_db   app_tenant      10.200.20.0/24          scram-sha-256 clientcert=verify-full

# Deny all fallback
host    all             all             0.0.0.0/0               reject
```

##### B. Arsitektur Audit Berbasis Ekstensi (`postgresql.conf` / `pgaudit`)
```ini
# Logging and Audit Hardening
shared_preload_libraries = 'pgaudit'

# Auditing Configuration
pgaudit.log = 'ddl, write, role'
pgaudit.log_catalog = off
pgaudit.log_parameter = on
pgaudit.log_relation = on
pgaudit.log_statement_once = off

# Enforce SCRAM and TLS
password_encryption = scram-sha-256
ssl = on
ssl_cert_file = '/etc/ssl/postgresql/server.crt'
ssl_key_file = '/etc/ssl/postgresql/server.key'
ssl_ca_file = '/etc/ssl/postgresql/root-ca.crt'
ssl_ciphers = 'HIGH:!aNULL:!MD5:!3DES:!CAMELLIA:!SRP:!PSK'
ssl_min_protocol_version = 'TLSv1.3'
```

##### C. Konfigurasi `pgBackRest` Produksi (`/etc/pgbackrest/pgbackrest.conf`)
Konfigurasi multi-core, deduplikasi, dan direct push ke S3 bucket.

```ini
[global]
repo1-type=s3
repo1-s3-endpoint=s3.ap-southeast-1.amazonaws.com
repo1-s3-bucket=enterprise-pg-backup-prod
repo1-s3-region=ap-southeast-1
repo1-s3-key=ENV_ACCESS_KEY_PG
repo1-s3-key-secret=ENV_SECRET_KEY_PG
repo1-path=/pgbackrest-repo
repo1-retention-full=4
repo1-retention-diff=14
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=K3y-Sup3r-S3cur3-Str0ng-P@ssw0rd!
process-max=8
log-level-console=info
log-level-file=detail
start-fast=y
compress-type=zst
compress-level=6

[prod-stanza]
pg1-path=/var/lib/postgresql/16/main
pg1-user=postgres
```

Integrasikan ke `postgresql.conf`:
```ini
archive_mode = on
archive_command = 'pgbackrest --stanza=prod-stanza archive-push %p'
```

##### D. Row-Level Security (Multi-Tenant Isolation)
Implementasi isolasi data tenant berbasis *Session Variable* aplikasi:

```sql
-- 1. Setup Table Schema
CREATE TABLE core_ledger (
    ledger_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(32) NOT NULL,
    account_number VARCHAR(64) NOT NULL,
    balance NUMERIC(18, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

-- Indexing tenant_id is mandatory to eliminate RLS sequential scan degradation
CREATE INDEX idx_ledger_tenant_id ON core_ledger (tenant_id);

-- 2. Enable RLS on Table
ALTER TABLE core_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE core_ledger FORCE ROW LEVEL SECURITY; -- Also enforce for table owners

-- 3. Create Tenant Isolation Policy
CREATE POLICY tenant_isolation_policy ON core_ledger
    AS RESTRICTIVE
    FOR ALL
    TO app_tenant
    USING (tenant_id = current_setting('app.current_tenant', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true));

-- 4. Testing Execution Flow
SET ROLE app_tenant;

-- Simulation: Tenant 001 Context
SET LOCAL app.current_tenant = 'TENANT_001';
INSERT INTO core_ledger (tenant_id, account_number, balance) 
VALUES ('TENANT_001', 'ACC-9988', 5000000.0000);

-- Query execution (Engine only sees records matching the predicate)
SELECT * FROM core_ledger;

-- Simulation: Unauthorized access attempt to another tenant (Returns 0 rows)
SET LOCAL app.current_tenant = 'TENANT_002';
SELECT * FROM core_ledger;

-- Attempting illegitimate write will throw an exception
INSERT INTO core_ledger (tenant_id, account_number, balance) 
VALUES ('TENANT_001', 'ACC-HAX', 1000.0000);
-- ERROR: new row violates row-level security policy for table "core_ledger"
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Pemulihan Bencana Platform FinTech Core Payment
- **Konteks**: Platform pemrosesan transaksi keuangan dengan beban transaksi $15.000\text{ write TPS}$ pada jam sibuk.
- **Masalah/Insiden**: Bug pada microservice melepaskan batch script migrasi yang mengeksekusi instruksi:
  ```sql
  UPDATE account_balances SET balance = 0 WHERE is_active = true;
  ```
  Insiden terjadi pada pukul `2024-02-14 03:15:22.451 UTC`.
  Cluster database berukuran $4.8\text{ TB}$. Tim DBA tidak bisa menggunakan snapshot disk storage biasa karena snapshot terakhir diambil pukul `00:00:00` (terancam data loss 3 jam lebih, melanggar SLA RPO yang ditentukan maskimal 5 menit).

#### Strategi Resolusi Menggunakan Continuous Archiving & Target LSN PITR:
1. **Identifikasi Precise Replay Point**:
   Tim DBA menganalisis log audit database menggunakan `pgAudit` untuk mendapatkan LSN tepat sesaat sebelum instruksi `UPDATE` merusak data:
   - Ditemukan LSN update rusak: `284/C991E040`
   - Ditetapkan recovery stop LSN: `284/C991E038`
2. **Provisioning Isolated Recovery Instance**:
   Tidak melakukan recovery di node aktif untuk mencegah over-write stream replikasi yang ada.
3. **Eksekusi Pemulihan Paralel dengan `pgBackRest`**:
   ```bash
   pgbackrest --stanza=prod-stanza \
     --type=immediate \
     --target="2024-02-14 03:15:22.000000+00" \
     --target-action=pause \
     --delta \
     --process-max=16 \
     restore
   ```
4. **Verifikasi Konsistensi dalam State Paused**:
   Database di-start, PostgreSQL menjalankan recovery loop hingga titik pause. DBA melakukan query validasi read-only pada port non-standar:
   ```sql
   SELECT count(*) FROM account_balances WHERE balance = 0; -- Data masih aman
   SELECT pg_is_wal_replay_paused(); -- Returns true
   ```
5. **Promosi Timeline**:
   DBA mengeksekusi `SELECT pg_wal_replay_resume();` untuk mempromosikan cluster ke Timeline ID baru.
6. **Hasil Akhir**:
   - **RPO Aktual**: 0 transaksi hilang (zero data loss).
   - **RTO Aktual**: 22 menit (berkat pemanfaatan 16 parallel threads block-level delta restore pada NVMe storage).

---

### 9. Trade-offs

```
                  Backup Storage Cost
                          ▲
                          │     ● Full Backup Tiap Jam
                          │
                          │        ● Differential Backup Harian
                          │
                          │           ● Incremental + Continuous WAL
                          │
                          └────────────────────────────────► Restore Latency (RTO)
                           (Cepat / Rendah)
```

| Pendekatan / Fitur | Keuntungan | Biaya / Trade-off |
| :--- | :--- | :--- |
| **Synthetic Full Backup (`pgBackRest`)** | Mengurangi beban CPU/IO di host database primer; backup full dibentuk langsung di remote storage. | Membutuhkan dependensi compute/storage repository yang terpisah dan terkelola. |
| **Synchronous WAL Archiving** | Jaminan zero RPO; jika node mati, tidak ada segment WAL yang tertinggal di disk lokal. | Meningkatkan latency commit transaksi aplikasi jika storage repository mengalami bottleneck I/O. |
| **Row-Level Security (RLS)** | Keamanan multi-tenant native terpusat; mencegah kebocoran data terlepas dari kompleksitas SQL aplikasi. | Mengurangi optimasi query; optimizer tidak dapat menggunakan visual query graph flattening secara bebas; potensi performa turun jika index tenant tidak optimal. |
| **pgAudit Verbose Level (`all`)** | Traceability penuh terhadap semua operasi read/write database. | Volume log membengkak drastis (dapat mencapai puluhan GB/hari), potensi I/O saturation pada disk log. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario 1: `archive_command` Gagal dan Disk `pg_wal` Penuh (Cluster Hang)
- **Gejala**: PostgreSQL mendadak berhenti melayani transaksi write (`PANIC: could not locate a valid checkpoint record` atau read-only). Disk `pg_wal` 100% full.
- **Penyebab**: Perintah `archive_command` mengembalikan exit code non-zero (misal: koneksi network ke S3 putus atau storage penuh). PostgreSQL menolak menghapus WAL lokal sebelum berhasil diarsipkan demi menjaga reliabilitas durabilitas data.
- **Tindakan Troubleshooting**:
  1. JANGAN PERNAH menghapus file di dalam direktori `pg_wal` menggunakan perintah `rm` secara manual. Hal ini merusak kesinambungan LSN dan dapat menyebabkan database crash permanen.
  2. Alihkan sementara `archive_command` ke dummy zero exit code via query engine jika terdesak (Hanya jika risiko data loss WAL tersebut dapat diterima):
     ```sql
     ALTER SYSTEM SET archive_command = '/bin/true';
     SELECT pg_reload_conf();
     ```
  3. Berikan ruang sementara dengan membesarkan disk secara dinamis (*volume expansion* pada LVM/Cloud EBS) atau memindahkan temporary log non-database.
  4. Perbaiki network pipe, lalu kembalikan konfigurasi backup asli.

#### Skenario 2: Timeline Divergence Pasca-Unplanned Failover
- **Gejala**: Node Standby yang dipromosikan menolak membaca WAL lama dari node primary sebelumnya, menghasilkan error:
  `FATAL: requested timeline 2 is not a child of database runtime timeline 1`
- **Penyebab**: Node di-promote secara prematur sementara node lama masih menerima transaksi (terjadi *Split-Brain*).
- **Tindakan Troubleshooting**:
  1. Identifikasi LSN terakhir yang valid di `.history` file.
  2. Gunakan utility `pg_rewind` untuk menarik dan merevisi block yang berbeda dari target timeline tanpa perlu melakukan full base restore:
     ```bash
     pg_rewind --target-pgdata=$PGDATA --source-server='host=new_primary port=5432 user=postgres'
     ```

#### Skenario 3: RLS Policy Bypassed Secara Tidak Sengaja
- **Gejala**: User tenant masih bisa membaca data milik tenant lain.
- **Penyebab**: User aplikasi memiliki atribut `SUPERUSER` atau `BYPASSRLS` di konfigurasi database role, atau tabel belum di-set `FORCE ROW LEVEL SECURITY` saat diakses oleh pemilik tabel (*table owner*).
- **Tindakan Troubleshooting**:
  ```sql
  -- Audit role permissions
  SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'app_tenant';
  -- Cabut hak istimewa
  ALTER ROLE app_tenant NOSUPERUSER NOBYPASSRLS;
  -- Paksa RLS untuk table owner
  ALTER TABLE core_ledger FORCE ROW LEVEL SECURITY;
  ```

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Configuration
- [ ] **Nyalakan Page Checksums**: Wajib menyalakan parameter `data_checksums = on` saat `initdb` untuk mendeteksi silent data corruption pada tingkat block storage.
- [ ] **Dedicated WAL Disk**: Pisahkan partisi mount point untuk data `$PGDATA` dan `$PGDATA/pg_wal` pada disk NVMe fisik yang berbeda untuk meminimalkan I/O contention.
- [ ] **Gunakan SCRAM-SHA-256**: Tinggalkan `md5`. Set `password_encryption = scram-sha-256`.

#### Runtime Disaster Recovery
- [ ] **Multi-Repository pgBackRest**: Simpan satu copy backup di jaringan lokal yang sama (Fast RTO) dan replicate secara paralel ke Object Storage / S3 Region berbeda (Disaster Recovery).
- [ ] **Set Archive Timeout**: Atur `archive_timeout = 300` (5 menit) agar server dengan traffic rendah tetap mengalirkan data WAL secara periodik ke repository (membatasi window RPO).
- [ ] **Continuous Restoration Validation Drill**: Bangun cronjob/automation pipeline mingguan yang menarik data backup pgBackRest ke VM temporary terisolasi, me-restore secara penuh, memvalidasi checksum tabel, lalu mematikan VM kembali.

#### System Level Hardening
```ini
# /etc/sysctl.d/99-postgresql.conf
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
vm.overcommit_memory = 2
vm.overcommit_ratio = 80
```

---

### 12. Hands-on Practice

Simpan seluruh file konfigurasi dan skrip berikut di direktori target: `hands-on/m02/`

```bash
mkdir -p hands-on/m02/config hands-on/m02/scripts
```

#### Langkah 1: Setup Konfigurasi Lab Standar Produksi
Simpan file ini di: `hands-on/m02/config/postgresql.conf`

```ini
listen_addresses = '*'
port = 5432
wal_level = replica
data_checksums = on
max_wal_senders = 10
archive_mode = on
archive_command = 'pgbackrest --stanza=demo-stanza archive-push %p'
shared_preload_libraries = 'pgaudit'
pgaudit.log = 'all'
```

#### Langkah 2: Setup Konfigurasi Engine pgBackRest
Simpan file ini di: `hands-on/m02/config/pgbackrest.conf`

```ini
[global]
repo1-path=/tmp/pgbackrest-repo
process-max=2
log-level-console=info
start-fast=y

[demo-stanza]
pg1-path=/var/lib/postgresql/data
```

#### Langkah 3: Skrip Otomasi Deployment Lab
Simpan file ini di: `hands-on/m02/scripts/setup_lab.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> Inisialisasi Repository Backup..."
mkdir -p /tmp/pgbackrest-repo
chmod 700 /tmp/pgbackrest-repo

echo "==> Mendaftarkan Stanza ke pgBackRest..."
pgbackrest --stanza=demo-stanza stanza-create

echo "==> Memvalidasi Konfigurasi Stanza..."
pgbackrest --stanza=demo-stanza check

echo "==> Menjalankan Full Base Backup Pertama..."
pgbackrest --stanza=demo-stanza --type=full backup

echo "==> Cluster Siap Digunakan untuk Eksperimen."
```

#### Langkah 4: Skrip Simulasi Bencana dan PITR
Simpan file ini di: `hands-on/m02/scripts/pitr_simulation.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Tulis Transaksi Normal
psql -U postgres -d postgres -c "CREATE TABLE mission_critical (id int, val text, created_at timestamptz);"
psql -U postgres -d postgres -c "INSERT INTO mission_critical VALUES (1, 'Kondisi Awal Aman', now());"

sleep 2
TARGET_RECOVERY_TIME=$(psql -U postgres -d postgres -At -c "SELECT clock_timestamp();")
echo "==> TIMESTAMP TITIK TARGET RECOVERY: ${TARGET_RECOVERY_TIME}"
sleep 2

# 2. Simulasi Bencana (Human Error Truncate)
echo "==> MENSIMULASIKAN CRASH: TRUNCATE Table dieksekusi!"
psql -U postgres -d postgres -c "TRUNCATE TABLE mission_critical;"
psql -U postgres -d postgres -c "INSERT INTO mission_critical VALUES (2, 'Data Korup / Tidak Diinginkan', now());"

# Paksa rotasi WAL agar ter-push ke repo
psql -U postgres -d postgres -c "SELECT pg_switch_wal();"
sleep 2

# 3. Shutdown Service
echo "==> Mematikan Database..."
pg_ctl -D /var/lib/postgresql/data -m fast stop

# 4. Eksekusi PITR Menggunakan Delta Restore
echo "==> Menjalankan pgBackRest PITR..."
pgbackrest --stanza=demo-stanza \
  --delta \
  --type=time \
  "--target=${TARGET_RECOVERY_TIME}" \
  --target-action=promote \
  restore

# 5. Start Ulang Database
echo "==> Menyalakan kembali PostgreSQL pasca PITR..."
pg_ctl -D /var/lib/postgresql/data start

# 6. Validasi Data
echo "==> Menampilkan Kondisi Data Pasca Recovery (Harus berisi row ID 1):"
psql -U postgres -d postgres -c "SELECT * FROM mission_critical;"
```

Pastikan executable permission disetel:
```bash
chmod +x hands-on/m02/scripts/*.sh
```

---

### 13. Exercise

#### Level: Easy
1. Aktifkan konfigurasi `archive_mode = on` menggunakan PostgreSQL running instance lokal.
2. Tulis sebuah bash command sederhana pada `archive_command` yang memindahkan WAL segment ke direktori `/opt/wal_cold_storage/` dan memvalidasi bahwa file yang terkirim tidak dalam kondisi korup (cek non-empty bytes).
3. Verifikasi status archiving menggunakan system view `pg_stat_archiver`.

#### Level: Medium
1. Rancang arsitektur Row-Level Security (RLS) untuk sistem Human Resource:
   - Skema: `employees (id, department_id, full_name, salary)`
   - Role `hr_staff` hanya dapat melihat dan memodifikasi data gaji (*salary*) dari divisi mereka sendiri berdasarkan session variable `app.user_department`.
   - Role `auditor` dapat melihat semua data *tanpa terkecuali*, tetapi akses dibatasi strictly **read-only**.
2. Uji policy tersebut dan sertakan bukti query execution plan (`EXPLAIN ANALYZE`).

#### Level: Hard
1. Buat skenario disaster recovery tingkat lanjut:
   - Jalankan continuous load injection ke dalam database lokal menggunakan utility `pgbench`.
   - Di tengah proses write, jalankan full backup asynchronous menggunakan `pgBackRest`.
   - Simulasikan *Power Loss* (hard termination via `kill -9` pada process ID postgres cluster).
   - Simulasikan kerusakan fisik pada block storage dengan meng-overwrite sektor awal salah satu file tabel di direktori base:
     `dd if=/dev/urandom of=/var/lib/postgresql/data/base/<db_id>/<table_relfilenode> bs=8k count=5 conv=notrunc`
   - Pulihkan node tersebut ke kondisi operasional konsisten dengan meminimalisasi RPO tanpa melakukan drop cluster secara penuh (manfaatkan delta-restore per file block).

---

### 14. Challenge

**Skenario**:
Anda adalah Lead Database Architect di sebuah perusahaan unicorn logistik multi-nasional. Sistem database Anda terdiri atas Primary Node dan dua Synchronous Standby Node dengan volume data $12\text{ TB}$. 

Terjadi insiden ganda (*Cascade Catastrophic Event*):
1. Pukul 09:12:00: Sebuah software supply chain disusupi malware ransomware yang mulai mengenkripsi storage primary secara perlahan pada block-level.
2. Pukul 09:14:30: Monitoring node mendeteksi IO fail dan secara otomatis menjalankan script failover otomatis (*Split-Brain*) yang mempromosikan Standby-1 ke Timeline 2. Namun, Standby-1 ternyata telah mereplikasi sebagian block data yang terenkripsi sebelum isolasi jaringan terjadi.
3. Repositori backup remote Anda (S3) menerima push WAL dari primary hingga pukul 09:13:00, dan menerima push WAL dari Standby-1 (Timeline 2) sejak pukul 09:15:00.

**Tugas**:
Rancang dokumen rancang bangun arsitektur pemulihan (*Disaster Recovery Playbook*) yang komprehensif tanpa solusi instan:
- Bagaimana algoritma Anda untuk mengevaluasi pada Timeline berapa dan pada LSN ke berapa titik data bersih terakhir berada?
- Bagaimana Anda menangani fragmentasi Timeline yang saling tumpang tindih (*divergent branches*) pada repositori S3?
- Tentukan metode validasi block level integrity untuk memastikan tidak ada single block terenkripsi yang ikut di-replay ke cluster baru.
- Susun topologi jaringan dan arsitektur pengamanan koneksi mTLS/RLS baru agar setelah recovery, vektor serangan awal tidak dapat menginjeksi transaksi perusak kembali.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic (5 Pertanyaan)
1. Apa peran file `recovery.signal` dalam proses start-up PostgreSQL?
   - A. Menandakan database harus berjalan dalam safe-mode tanpa koneksi TCP.
   - B. Menginstruksikan database engine untuk memasuki mode Redo Archive Recovery dan membaca instruksi recovery.
   - C. Mengunci direktori `$PGDATA` agar tidak bisa dihapus oleh sistem operasi.
   - D. Menyalakan engine auto-vacuum secara paksa saat startup.
   *(Jawaban: B — `recovery.signal` memberi tahu instance engine untuk tidak membuka write engine secara langsung melainkan mengeksekusi sequence archive replay).*

2. Berapa ukuran default dari satu segment file Write-Ahead Log (WAL) pada PostgreSQL standar?
   - A. 8 Kilobytes
   - B. 64 Megabytes
   - C. 16 Megabytes
   - D. 1 Gigabyte
   *(Jawaban: C — Default WAL segment file size adalah 16MB, dikonfigurasi saat proses kompilasi atau initdb via parameter `--wal-segsize`).*

3. Parameter apa yang HARUS dinyalakan agar perintah PITR berhenti tepat sebelum transaksi yang bermasalah diaplikasikan?
   - A. `recovery_target_inclusive = off`
   - B. `pause_at_recovery_target = off`
   - C. `wal_level = minimal`
   - D. `hot_standby = off`
   *(Jawaban: A — Parameter `recovery_target_inclusive = false/off` membuat database berhenti persis sebelum target LSN/waktu yang ditentukan).*

4. Mengapa logical dump (`pg_dump`) BUKAN strategi yang memadai untuk implementasi Point-In-Time Recovery (PITR)?
   - A. Karena `pg_dump` hanya menghasilkan data terenkripsi.
   - B. Karena `pg_dump` tidak menangkap stream LSN WAL transaksi, melainkan hanya export snapshot satu kali.
   - C. Karena `pg_dump` tidak dapat mengekspor indeks database.
   - D. Karena `pg_dump` membutuhkan node PostgreSQL dalam status offline saat proses berlangsung.
   *(Jawaban: B — PITR bergantung pada kelanjutan stream physical write block dalam WAL, hal yang tidak disediakan oleh snapshot logical dump).*

5. Perintah apa yang digunakan untuk memaksa rotasi file WAL aktif ke file segment baru di PostgreSQL?
   - A. `SELECT pg_rotate_logfile();`
   - B. `SELECT pg_switch_wal();`
   - C. `SELECT pg_flush_wal();`
   - D. `SELECT pg_checkpoint();`
   *(Jawaban: B — `pg_switch_wal()` menutup segmen WAL aktif saat ini dan langsung membuka segmen berikutnya, memaksa eksekusi arsir).*

---

#### Bagian B: Intermediate (5 Pertanyaan)
1. Pada kondisi apa sebuah `archive_command` dianggap sukses oleh proses archiver PostgreSQL?
   - A. Ketika output dari script mencetak string 'SUCCESS'.
   - B. Ketika proses eksternal mengembalikan exit status code 0 (`EXIT_SUCCESS`).
   - C. Ketika file tujuan memiliki permission 777 di tingkat sistem operasi.
   - D. Ketika database standby mengirimkan acknowledgment sinyal TLS.
   *(Jawaban: B — Sistem POSIX exit code bernilai 0 adalah satu-satunya indikator bagi arsitektur background process PostgreSQL bahwa file berhasil terkirim).*

2. Perhatikan policy RLS berikut:
   ```sql
   CREATE POLICY p1 ON contracts FOR SELECT USING (department = 'Legal');
   CREATE POLICY p2 ON contracts FOR SELECT USING (is_public = true);
   ```
   Bagaimana query rewriter PostgreSQL mengevaluasi kedua policy tersebut jika diaplikasikan ke user non-superuser?
   - A. Evaluasi dilakukan berurutan dengan logika `p1 AND p2` (Restriktif).
   - B. Evaluasi dilakukan dengan logika `p1 OR p2` (Permisif secara default).
   - C. PostgreSQL melempar syntax error saat startup karena tidak boleh ada dua policy `SELECT` pada satu tabel.
   - D. Hanya policy yang pertama kali dibuat (`p1`) yang dijalankan.
   *(Jawaban: B — Secara default, multiple policies pada command yang sama bersifat `PERMISSIVE` dan digabungkan menggunakan operator Boolean `OR` kecuali dinyatakan eksplisit sebagai `AS RESTRICTIVE`).*

3. Apa keuntungan fundamental menggunakan tool backup block-level incremental seperti `pgBackRest` dibanding native `pg_basebackup`?
   - A. `pgBackRest` tidak memerlukan instalasi di host database.
   - B. `pgBackRest` hanya menyalin block data 8KB yang mengalami perubahan checksum sejak backup terakhir, memangkas storage dan waktu proses secara eksponensial.
   - C. `pgBackRest` secara otomatis memperbaiki schema database yang tidak normal.
   - D. `pgBackRest` mengonversi table storage engine ke columnar storage.
   *(Jawaban: B — Pendekatan Page Checksum delta scanning memungkinkan pengiriman fraksi block termodifikasi saja tanpa transfer full image).*

4. Kapan sebuah `.history` file dibentuk dalam direktori `pg_wal`?
   - A. Setiap kali perintah `pg_dump` selesai dijalankan.
   - B. Saat proses recovery mencapai target, base backup dipromosikan, dan Timeline ID baru diciptakan.
   - C. Saat auto-vacuum daemon selesai melakukan vacuum freeze pada system catalog.
   - D. Saat memory buffer PostgreSQL di-flush secara penuh ke disk saat shut down.
   *(Jawaban: B — `.history` file berfungsi memetakan silsilah percabangan Timeline ID baru beserta LSN switch-point-nya).*

5. Dalam konfigurasi audit keamanan dengan `pgaudit`, flag apa yang paling tepat disetel untuk memonitor perubahan struktur skema (seperti `DROP TABLE` atau `ALTER ROLE`) tanpa memenuhi log dengan query analitik `SELECT`?
   - A. `pgaudit.log = 'read'`
   - B. `pgaudit.log = 'all'`
   - C. `pgaudit.log = 'ddl, role'`
   - D. `pgaudit.log = 'misc'`
   *(Jawaban: C — Kombinasi kelas `ddl` mencatat statement Data Definition Language dan `role` melacak statement yang berhubungan dengan privileges/identitas).*

---

#### Bagian C: Kasus Produksi Riil (3 Skenario)
1. **Kasus 1**: Pada cluster produksi berukuran $8\text{ TB}$, partisi `/var/log` dan `/var/lib/postgresql` terisolasi dengan benar. Namun, proses `archive_command` tertahan karena storage destination mengalami throttling API limit. Parameter `wal_keep_size` tidak disetel (menggunakan default). Apa risiko arsitektural yang dihadapi cluster jika dibiarkan selama 12 jam, dan mitigasi darurat apa yang harus diambil tanpa mematikan PostgreSQL?
   - **Analisis & Rationale Jawaban**:
     - *Risiko*: PostgreSQL akan terus mempertahankan semua segment file WAL di dalam path `pg_wal` karena belum berhasil diarsipkan. Hal ini akan menyebabkan partisi disk utama mengalami kehabisan kapasitas (*Disk Space Exhaustion*). Jika disk 100% full, PostgreSQL akan mengalami **Immediate Emergency Panic Shutdown**, menolak start-up berikutnya sampai ada free disk space.
     - *Mitigasi Darurat*:
       1. Secara temporer arahkan target arsir ke storage lokal lain yang memiliki ruang bebas menggunakan perintah non-restart:
          ```sql
          ALTER SYSTEM SET archive_command = 'cp %p /mnt/extra_disk/temporary_wal/%f';
          SELECT pg_reload_conf();
          ```
       2. Lakukan flushing WAL antrean tersebut dari disk `pg_wal`.
       3. Setelah throttling storage utama mereda, sync WAL lokal cadangan ke remote repository via tool batching terpisah (`aws s3 sync`), lalu kembalikan parameter `archive_command` asli.

2. **Kasus 2**: Sebuah instansi pemerintah mewajibkan penerapan enkripsi mTLS dan otentikasi SCRAM-SHA-256 pada seluruh pool koneksi backend. Aplikasi microservice dibangun menggunakan Golang dan terhubung melalui PgBouncer (connection pooler) ke PostgreSQL Database Engine. Setelah menerapkan baris:
   `hostssl all all 0.0.0.0/0 scram-sha-256 clientcert=verify-full`
   pada `pg_hba.conf` database, seluruh koneksi microservice ditolak dengan pesan error: `SSL error: certificate verify failed`.
   Jelaskan di tier mana kegagalan arsitektur ini terjadi dan langkah apa yang harus diambil.
   - **Analisis & Rationale Jawaban**:
     - *Akar Masalah*: Mode arsitektur PgBouncer dapat bertindak sebagai *Intermediate Proxy*. Jika PgBouncer tidak dikonfigurasi untuk meneruskan atau menyediakan client certificate miliknya sendiri ke PostgreSQL Primary Node, konfigurasi `clientcert=verify-full` di level engine database akan menolak koneksi karena menganggap PgBouncer tidak menyertakan sertifikat valid yang ditandatangani oleh Root CA tepercaya.
     - *Solusi*:
       1. Konfigurasikan PgBouncer untuk menggunakan client certificate saat berkomunikasi dengan server backend PostgreSQL via parameter `server_ssl_mode = verify-full`, `server_ssl_cert = /path/to/pgbouncer-client.crt`, dan `server_ssl_key = /path/to/pgbouncer-client.key`.
       2. Daftarkan Common Name (CN) dari sertifikat PgBouncer tersebut ke dalam user mapping database (`pg_ident.conf`) agar lolos validasi otentikasi database primary.

3. **Kasus 3**: Anda diminta melakukan audit forensik pada cluster database PostgreSQL setelah dugaan kebocoran data (*data exfiltration*) oleh pihak internal. Saat memeriksa tabel `sensitive_records`, Anda menemukan bahwa tabel tersebut dilindungi oleh policy RLS yang membatasi hak baca berdasarkan IP dan ID Pengguna. Namun, data tetap bocor melalui eksekusi fungsi database yang dibuat oleh developer setahun yang lalu.
   Analisis bagaimana kebocoran ini secara teknis dapat terjadi pada tingkat engine PostgreSQL.
   - **Analisis & Rationale Jawaban**:
     - *Vektor Kerentanan*: Keberadaan fungsi dengan klausul **`SECURITY DEFINER`**. 
     - *Mekanisme Eksploitasi*: Secara default, function di PostgreSQL berjalan dengan hak akses pemanggilnya (*invoker*). Namun, jika fungsi dideklarasikan dengan `SECURITY DEFINER`, fungsi tersebut dieksekusi menggunakan privilese dari **pembuat fungsi (owner)**. Jika pembuat fungsi adalah user superuser atau role yang memiliki atribut `BYPASSRLS`, maka seluruh mekanisme Row-Level Security yang aktif pada tabel terkait akan dilewati (*bypassed*) sepenuhnya di dalam eksekusi fungsi tersebut.
     - *Remediasi*: Audit seluruh function menggunakan query:
       ```sql
       SELECT proname, prosecdef, proowner::regrole FROM pg_proc WHERE prosecdef = true;
       ```
       Ubah fungsi tersebut menjadi `SECURITY INVOKER`, atau isolasi `search_path` dan pastikan fungsi tersebut tidak dimiliki oleh Superuser.

---

### 16. Summary

Implementasi disaster recovery dan security tingkat enterprise pada PostgreSQL tidak dapat disandarkan pada konfigurasi out-of-the-box maupun backup logical ad-hoc. 
1. **Continuous Archiving dan PITR** adalah fondasi utama dalam menjamin durabilitas transaksi data (RPO $\approx 0$) dan ketersediaan sistem (RTO hitungan menit) melalui tracking LSN yang granular.
2. Penggunaan engine modern seperti **pgBackRest** menjawab tantangan skalabilitas physical snapshot melalui pemanfaatan transfer data multithreaded, kompresi asinkron, dan arsitektur *block-level incremental / synthetic full backup*.
3. Keamanan data pada ekosistem enterprise harus mengadopsi pendekatan holistik: melindungi jalur transmisi dengan **mTLS**, mengunci otentikasi melalui hashing **SCRAM-SHA-256**, menegakkan pemisahan domain data multi-tenant secara matematis menggunakan **Row-Level Security (RLS)**, serta merekam seluruh interaksi DDL/DML melalui **pgAudit** demi auditabilitas regulasi global.
4. Nilai reliabilitas sebuah sistem backup tidak ditentukan dari seberapa sukses proses pencadangannya berjalan, melainkan dari **seberapa teruji, terukur, dan terotomasinya proses restorasi (*Restoration Drill*)** saat bencana skala penuh terjadi.