# Kurikulum: PostgreSQL Database Administrator (PostgreSQL-DBA)
## Kategori: 04-Backend-and-Database
### Bab 07: Security, Backup & Recovery
#### Module 01: Enterprise Security Hardening, Backup Strategies, and Disaster Recovery

---

### 01: Identitas Modul
* **Mata Pelajaran:** PostgreSQL Database Administration & Engineering
* **Kode Modul:** PG-DBA-07-01
* **Tingkat Kesulitan:** Advanced / Enterprise Grade
* **Prasyarat:** PostgreSQL Architecture, Linux System Administration, Networking & TLS/SSL Basics, Storage Engine & WAL Internals
* **Target Audience:** Principal Database Administrators, Lead Backend Engineers, Site Reliability Engineers (SRE), Cloud Infrastructure Architects
* **Estimasi Waktu Penyelesaian:** 12 - 16 Jam (Teori, Lab, Pengujian Bencana)

---

### 02: Learning Objectives
Setelah menyelesaikan modul ini, peserta mampu:
1. **Mengonfigurasi Arsitektur Autentikasi dan Otorisasi Berlapis:** Mengimplementasikan SCRAM-SHA-256, TLS v1.3 cryptographic hardening, Client Certificate Authentication (mTLS), Role-Based Access Control (RBAC), dan Row-Level Security (RLS) dengan zero-trust principle.
2. **Membangun Strategi Backup Zero-Data-Loss:** Merancang dan mengoperasikan Continuous Archiving Write-Ahead Logging (WAL) bersama Physical Base Backups (menggunakan `pg_basebackup` dan `pgBackRest`) serta Logical Backups (`pg_dump`/`pg_restore`) terisolasi.
3. **Mengeksekusi Point-in-Time Recovery (PITR):** Memulihkan kluster database ke microsecond timestamp spesifik atau Transaction ID (XID) target saat terjadi kegagalan sistem katastropik atau *human error*.
4. **Menerapkan Enkripsi Enterprise & Auditing:** Mengonfigurasi Transparent Data Encryption (TDE) / Data-at-Rest Encryption via LUKS/dm-crypt, Column-level encryption via `pgcrypto`, serta comprehensive compliance auditing menggunakan ekstensi `pgaudit`.
5. **Mengotomatisasi Disaster Recovery (DR) Validation:** Mengembangkan pipeline Continuous Integration untuk validasi integritas backup secara berkala dan mengukur Recovery Time Objective (RTO) serta Recovery Point Objective (RPO) aktual.

---

### 03: Concept Map Diagram ASCII

```
                                +-------------------------------------------------------+
                                |      PostgreSQL Enterprise Security & Reliability     |
                                +-------------------------------------------------------+
                                                           |
         +-------------------------------------------------+-------------------------------------------------+
         |                                                 |                                                 |
         v                                                 v                                                 v
+------------------+                             +--------------------+                            +--------------------+
| Layer 1: Access  |                             |  Layer 2: Engine   |                            |  Layer 3: Storage  |
|   & Encryption   |                             |   & Audit Trail    |                            |  Backup & Restore  |
+------------------+                             +--------------------+                            +--------------------+
  |                                                |                                                 |
  +--> mTLS (TLS 1.3)                              +--> RBAC Matrix                                  +--> Logical Backup
  |    (Client & Server Certs)                     |    (LEAST PRIVILEGE)                            |    (pg_dump / Parallel)
  |                                                |                                                 |
  +--> SCRAM-SHA-256 Auth                          +--> Row Level Security (RLS)                     +--> Physical Backup
  |    (pg_hba.conf Hardening)                     |    (Tenant Isolation)                           |    (pg_basebackup)
  |                                                |                                                 |
  +--> Host Level (Firewall/VPC)                   +--> PGAudit Logging                              +--> Continuous Archiving
  |    (Network Isolation)                         |    (DDL, READ, WRITE, MISC)                     |    (WAL Archiving)
  |                                                |                                                 |
  +--> Column Crypto (pgcrypto)                    +--> System Parameter Hardening                   +--> Point-In-Time Recovery
       (Sensitive Payload Encryption)                   (Connection / Memory Limit)                       (Target Time / Target XID)
```

---

### 04: Mengapa Relevan
Dalam lingkungan industri perbankan, teknologi finansial, layanan kesehatan, dan enterprise SaaS skala global, basis data adalah aset paling bernilai sekaligus target utama ancaman siber dan bencana infrastruktur. Kegagalan konfigurasi keamanan (*misconfiguration*) seperti penggunaan autentikasi `md5` yang sudah usang, eksposur port 5432 ke internet publik, atau pemberian izin `SUPERUSER` secara serampangan dapat memicu kebocoran data berskala masif (data breach).

Di sisi lain, *backup tanpa uji pemulihan berkala bukanlah backup, melainkan ilusi.* Kehilangan data akibat *ransomware*, kerusakan disk (*silent data corruption*), atau kesalahan eksekusi perintah `DROP DATABASE` oleh operator dapat melumpuhkan operasional bisnis jika Recovery Point Objective (RPO = batas toleransi kehilangan data) dan Recovery Time Objective (RTO = batas toleransi durasi downtime) tidak dipenuhi. 

Modul ini membekali DBA untuk menerapkan standar keamanan setara CIS (Center for Internet Security) PostgreSQL Benchmark dan arsitektur Disaster Recovery berkinerja tinggi tanpa kompromi performa.

---

### 05: Anatomi Konsep Inti

```
+---------------------------------------------------------------------------------------------------------+
|                                    ANATOMI POSTGRESQL WAL DAN PITR                                      |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|  [Shared Buffers (RAM)] === Flush Buffer ===> [WAL Buffer] === wal_writer / commit ===> [WAL Segment]  |
|                                                                                                |        |
|                                                                                         archive_command |
|                                                                                                v        |
|  [Base Backup File (pg_basebackup)] ................................................> [WAL Storage Repo]|
|             |                                                                                  |        |
|             v (Restore Base Backup)                                                            v        |
|  [PGDATA Directory Baru] <=== Replay WAL Logs (pg_wal) <========================= [restore_command]     |
|             |                                                                                           |
|             +---> Stop Replay at 'recovery_target_time' = 2023-10-25 14:30:00.000000+00                 |
|             |                                                                                           |
|             v                                                                                           |
|  [Cluster Consistent State: Point of Recovery Reached]                                                  |
+---------------------------------------------------------------------------------------------------------+
```

1. **Host-Based Authentication (`pg_hba.conf`):** Mengatur filter deklaratif dari IP, Database, User, dan Metode Otentikasi. Penanganan keamanan wajib menggunakan `scram-sha-256` untuk mencegah serangan *credential interception* dan *rainbow table attacks*.
2. **Role-Based Access Control (RBAC):** Menetapkan struktur relasi izin (*permissions*) tanpa mengandalkan akun *superuser*. Berlandaskan prinsip *least privilege*, hak akses didelegasikan secara terisolasi (`CONNECT`, `USAGE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`).
3. **Row-Level Security (RLS):** Kebijakan keamanan berbasis baris yang menyaring baris data secara deterministik pada level engine basis data sebelum query mengembalikan data ke aplikasi klien.
4. **Physical vs Logical Backup:**
   * *Logical (`pg_dump`):* Mengekspor representasi DDL/DML teks atau biner format kustom. Bersifat fleksibel lintas versi mayor, namun lambat pada volume data besar (TeraByte/PetaByte).
   * *Physical (`pg_basebackup`, `pgBackRest`):* Menggandakan *block-level binary* dari `$PGDATA` bersama stream WAL yang relevan. Sangat cepat, konsisten secara transaksi, dan wajib digunakan sebagai landasan PITR.
5. **Write-Ahead Logging (WAL) & Continuous Archiving:** Setiap transaksi diskrit dicatat ke WAL sebelum data blok ditulis ke storage. Memadukan Base Backup dengan arsip WAL memungkinkan rekonstruksi keadaan data ke titik waktu manapun secara deterministik.
6. **Data Auditing (`pgaudit`):** Audit trail tingkat tinggi untuk merekam eksekusi instruksi SQL spesifik ke log engine demi kepatuhan regulasi (SOC2, PCI-DSS, HIPAA, GDPR).

---

### 06: Panduan Implementasi Step-by-Step

#### Langkah 1: Implementasi Network Isolation & TLS 1.3
1. Buat Private Certificate Authority (CA) dan pasang sertifikat server yang ditandatangani.
2. Edit `postgresql.conf`:
```ini
ssl = on
ssl_ca_file = '/etc/ssl/certs/pg-root-ca.crt'
ssl_cert_file = '/var/lib/postgresql/data/server.crt'
ssl_key_file = '/var/lib/postgresql/data/server.key'
ssl_ciphers = 'TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256'
ssl_min_protocol_version = 'TLSv1.3'
```
3. Ubah permission file private key:
```bash
chmod 0600 /var/lib/postgresql/data/server.key
chown postgres:postgres /var/lib/postgresql/data/server.key
```

#### Langkah 2: Konfigurasi Otentikasi `pg_hba.conf` (Zero-Trust)
Kunci akses hanya melalui enkripsi TLS dengan verifikasi SCRAM-SHA-256:
```text
# TYPE  DATABASE        USER            ADDRESS                 METHOD
# "local" is for Unix domain socket connections only
local   all             postgres                                peer
local   all             all                                     scram-sha-256

# Reject unencrypted IPv4/IPv6 connections
hostnossl all           all             0.0.0.0/0               reject
hostnossl all           all             ::/0                    reject

# Allow only TLS with SCRAM-SHA-256 from trusted application subnet
hostssl all             app_user        10.200.10.0/24          scram-sha-256
hostssl replication     replicator      10.200.10.50/32         scram-sha-256
hostssl all             all             all                     reject
```

#### Langkah 3: Konfigurasi Parameter Backup & WAL Archiving
Edit `postgresql.conf` untuk mengaktifkan archiving:
```ini
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /mnt/pg_wal_archive/%f && cp %p /mnt/pg_wal_archive/%f'
archive_timeout = 300 # Memaksa rotasi WAL setiap 5 menit jika traffic rendah
```
*Reload* konfigurasi PostgreSQL:
```bash
pg_ctl -D /var/lib/postgresql/data reload
```

---

### 07: Contoh Kasus Sederhana

Skenario: Membatasi teknisi finance (`finance_analyst`) hanya dapat melihat transaksi dari divisi mereka sendiri menggunakan *Row-Level Security (RLS)*.

```sql
-- 1. Buat Tabel Data Finansial
CREATE TABLE enterprise_ledger (
    ledger_id BIGSERIAL PRIMARY KEY,
    department_code VARCHAR(16) NOT NULL,
    transaction_amount NUMERIC(15,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Aktifkan RLS pada Tabel
ALTER TABLE enterprise_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE enterprise_ledger FORCE ROW LEVEL SECURITY;

-- 3. Buat Role dan Assign Permission
CREATE ROLE finance_analyst WITH LOGIN PASSWORD 'SecureSecretPass987!';
GRANT CONNECT ON DATABASE production_db TO finance_analyst;
GRANT USAGE ON SCHEMA public TO finance_analyst;
GRANT SELECT, INSERT ON enterprise_ledger TO finance_analyst;

-- 4. Buat Kebijakan Keamanan (Security Policy)
CREATE POLICY ledger_dept_isolation_policy ON enterprise_ledger
    AS RESTRICTIVE
    FOR ALL
    TO finance_analyst
    USING (department_code = current_setting('request.jwt.claim.dept', true));

-- 5. Pengujian Simulasi Konteks User
-- Masukkan Data Uji sebagai Administrator
INSERT INTO enterprise_ledger (department_code, transaction_amount, description)
VALUES 
('FIN-CORP', 1500000.00, 'Dividen Q3'),
('HR-OPS', 450000.00, 'Payroll System License');

-- Jalankan Query dengan Context Switch
SET ROLE finance_analyst;
SET request.jwt.claim.dept = 'FIN-CORP';

-- Hanya menampilkan record 'FIN-CORP'
SELECT * FROM enterprise_ledger;

-- Reset Context
RESET ROLE;
```

---

### 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah arsitektur keamanan dan otomasi *Point-in-Time Recovery* end-to-end.

#### Bagian A: Arsitektur RBAC & PGAudit Configuration
```sql
-- Dijalankan oleh Superuser
BEGIN;

-- 1. Konfigurasi PGAudit Ekstensi
CREATE EXTENSION IF NOT EXISTS pgaudit;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Struktur Role Terisolasi
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

CREATE ROLE dba_admin NOINHERIT;
CREATE ROLE app_readwrite NOINHERIT;
CREATE ROLE app_readonly NOINHERIT;

-- Role Aplikasi Spesifik
CREATE ROLE svc_ecommerce_app WITH LOGIN PASSWORD 'ComplexGeneratedPassword#2026' 
    IN ROLE app_readwrite
    VALID UNTIL '2027-01-01';

CREATE SCHEMA ecom AUTHORIZATION dba_admin;
GRANT USAGE ON SCHEMA ecom TO app_readwrite, app_readonly;

-- Berikan Hak Granular
ALTER DEFAULT PRIVILEGES FOR ROLE dba_admin IN SCHEMA ecom 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_readwrite;

ALTER DEFAULT PRIVILEGES FOR ROLE dba_admin IN SCHEMA ecom 
    GRANT SELECT ON TABLES TO app_readonly;

-- 3. Tabel Data Sensitif dengan Data-at-Rest Column Hashing/Encryption
CREATE TABLE ecom.customer_vault (
    vault_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id BIGINT NOT NULL,
    raw_ssn_encrypted BYTEA NOT NULL,
    card_fingerprint VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

GRANT SELECT, INSERT, UPDATE ON ecom.customer_vault TO app_readwrite;

COMMIT;
```

#### Bagian B: Skrip Automasi Physical Backup Enterprise Menggunakan `pg_basebackup`
Simpan sebagai `/usr/local/bin/pg_backup_cluster.sh`:
```bash
#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_PARENT_DIR="/mnt/backups/postgresql"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TARGET_DIR="${BACKUP_PARENT_DIR}/base_${TIMESTAMP}"
WAL_ARCHIVE_DIR="/mnt/pg_wal_archive"
LOG_FILE="/var/log/pg_backup.log"
RETENTION_DAYS=7

exec >> >(tee -a "${LOG_FILE}") 2>&1

echo "[$(date --iso-8601=seconds)] INFO: Starting Physical Base Backup..."

# Pastikan folder ada
mkdir -p "${TARGET_DIR}"

# Eksekusi Base Backup dengan Checkpoint Spread dan WAL Streaming
pg_basebackup \
    --host=127.0.0.1 \
    --port=5432 \
    --username=replicator \
    --format=tar \
    --wal-method=stream \
    --checkpoint=fast \
    --label="full_backup_${TIMESTAMP}" \
    --gzip \
    --compress=6 \
    --target-gpdir="${TARGET_DIR}" \
    --verbose \
    --progress

echo "[$(date --iso-8601=seconds)] INFO: Base backup completed successfully at ${TARGET_DIR}"

# Hapus backup yang lebih lama dari retensi
echo "[$(date --iso-8601=seconds)] INFO: Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_PARENT_DIR}" -maxdepth 1 -type d -name "base_*" -mtime +${RETENTION_DAYS} -exec rm -rf {} +

# Bersihkan WAL yang sudah tidak dibutuhkan
pg_archivecleanup "${WAL_ARCHIVE_DIR}" "$(ls -1tr ${WAL_ARCHIVE_DIR} | tail -n 1)"

echo "[$(date --iso-8601=seconds)] INFO: Backup and retention execution completed."
```

#### Bagian C: Prosedur Eksekusi Point-In-Time Recovery (PITR)
Skrip demonstrasi pemulihan server ketika terjadi kesalahan fatal (`DROP TABLE`) pada `2026-03-30 10:15:00 UTC`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

PGDATA="/var/lib/postgresql/16/main"
BACKUP_ARCHIVE="/mnt/backups/postgresql/base_20260330_000001/base.tar.gz"
WAL_BACKUP_ARCHIVE="/mnt/backups/postgresql/base_20260330_000001/pg_wal.tar.gz"
RESTORE_TARGET_TIME="2026-03-30 10:14:59.000000+00"
WAL_SOURCE="/mnt/pg_wal_archive"

echo "=== EMERGENCY PITR EXECUTION INITIALIZED ==="

# 1. Hentikan Service PostgreSQL
systemctl stop postgresql

# 2. Amankan sisa WAL aktif yang belum sempat terarsip (jika PGDATA storage masih bisa diakses)
mkdir -p /mnt/emergency_wal_save
cp -r "${PGDATA}/pg_wal"/* /mnt/emergency_wal_save/ || true

# 3. Kosongkan folder PGDATA yang rusak
rm -rf "${PGDATA:?}"/*

# 4. Ekstrak Base Backup
echo "Extracting base backup..."
tar -xzvf "${BACKUP_ARCHIVE}" -C "${PGDATA}"
if [ -f "${WAL_BACKUP_ARCHIVE}" ]; then
    mkdir -p "${PGDATA}/pg_wal"
    tar -xzvf "${WAL_BACKUP_ARCHIVE}" -C "${PGDATA}/pg_wal"
fi

# 5. Buat File Sinyal Pemulihan dan recovery.signal
touch "${PGDATA}/recovery.signal"

# 6. Tulis Konfigurasi Pemulihan ke postgresql.auto.conf
cat <<EOF >> "${PGDATA}/postgresql.auto.conf"
restore_command = 'cp ${WAL_SOURCE}/%f %p'
recovery_target_time = '${RESTORE_TARGET_TIME}'
recovery_target_action = 'promote'
EOF

# 7. Pastikan Permission Benar
chown -R postgres:postgres "${PGDATA}"
chmod 0700 "${PGDATA}"

# 8. Start Service untuk Memulai Replay WAL
echo "Starting PostgreSQL in recovery mode..."
systemctl start postgresql

echo "PostgreSQL is replaying WAL logs up to target time: ${RESTORE_TARGET_TIME}"
echo "Pantau log sistem: tail -f /var/log/postgresql/postgresql-16-main.log"
```

---

### 09: Diagram Alur Kerja Point-in-Time Recovery (PITR)

```
[BENCANA DATABASE TERJADI (Contoh: Accidental DROP TABLE)]
                    |
                    v
    [Hentikan Service Engine Database (systemctl stop)]
                    |
                    v
    [Amankan Active WAL Log Terakhir dari $PGDATA/pg_wal]
                    |
                    v
    [Wipe Out Broken $PGDATA & Ekstrak Terakhir Base Backup]
                    |
                    v
    [Generate File: $PGDATA/recovery.signal]
                    |
                    v
    [Injeksi Konfigurasi restore_command & recovery_target_time]
                    |
                    v
    [Nyalakan Database Engine (systemctl start)]
                    |
                    v
+-------------------------------------------------------------+
| ENGINE MEMASUKI MODE RECOVERY SECARA OTOMATIS               |
| 1. Membaca Base Backup Checkpoint                           |
| 2. Replay Arsip WAL via restore_command                     |
| 3. Verifikasi Log Timestamp vs recovery_target_time        |
| 4. Menghentikan Replay Tepat Sebelum Titik Kesalahan       |
| 5. Eksekusi 'recovery_target_action' (PROMOTE TO PRIMARY)   |
| 6. Menghapus recovery.signal                                |
+-------------------------------------------------------------+
                    |
                    v
[DATABASE SIAP: KONSISTEN & LAYANAN PULIH KEMBALI]
```

---

### 10: Analisis Trade-offs

| Pendekatan / Fitur | Keuntungan Utama | Trade-offs & Kekurangan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Physical Backup (`pg_basebackup`/`pgBackRest`)** | Kecepatan *snapshot* luar biasa, menjamin *byte-for-byte consistency*, fondasi utama PITR. | Memerlukan ruang disk besar, tidak bisa lintas platform OS / arsitektur CPU / versi mayor PG. | Standar mutlak untuk Production DBA & DR Strategy. |
| **Logical Backup (`pg_dump`)** | Fleksibel, granular (bisa per table/schema), hasil dump bisa di-edit (SQL format), lintas versi mayor. | Restorasi lambat untuk basis data berukuran > 500GB, berdampak I/O berat selama ekstraksi data. | Upgrade versi mayor, dev/staging seeding, isolasi tabel tertentu. |
| **Row Level Security (RLS)** | Keamanan native engine tanpa bergantung logic di aplikasi, memangkas risiko *data leakage*. | Penurunan performa query (*execution plan overhead*), query planner tidak bisa mengoptimasi filter secara bebas. | Multi-tenant SaaS, sistem perbankan, kepatuhan HIPAA/GDPR. |
| **Column Encryption (`pgcrypto`)** | Data dienkripsi sebelum ditulis ke disk (aman jika disk/dump dicuri). | Beban CPU tinggi saat enkripsi/dekripsi, query filtering tidak dapat menggunakan Index B-Tree konvensional. | Data ultra-sensitif (SSN, KTP, Nomor Kartu Kredit, Data Rekam Medis). |
| **PGAudit Extension** | Jejak audit kepatuhan regulasi sangat mendalam, detail query terekam jelas. | Ukuran file log membengkak drastis (Disk I/O pressure), biaya storage log audit meningkat. | Institusi finansial, kepatuhan PCI-DSS Level 1, sistem bersertifikasi ISO 27001. |

---

### 11: Best Practices & Antipatterns

#### Best Practices
* **Prinsip Least Privilege:** Selalu buat user dengan `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`. Gunakan skema terdedikasi per mikroservis.
* **Isolasi Arsip WAL Terpisah:** Simpan arsip WAL (`archive_command`) pada storage backend yang berbeda fisik atau cloud storage (misal: AWS S3/GCP Cloud Storage melalui tools seperti `pgBackRest` / `Wal-G`).
* **Enkripsi File Konfigurasi & TLS 1.3:** Selalu wajibkan enkripsi transit client-to-server dan server-to-replica.
* **Test Restore Terjadwal:** Jalankan otomasi yang secara berkala men-download backup, melakukan pemulihan di VM terisolasi, dan menjalankan *data integrity test*.
* **Gunakan Connection Pooler:** Pasang PgBouncer di depan instance dengan TLS client termination untuk mencegah DoS akibat koneksi tak terbatas.

#### Antipatterns yang Harus Dihindari
* **Menyimpan Password secara Plaintext di Script:** Menggunakan skrip bash dengan password database hardcoded (Gunakan file `.pgpass` dengan izin `0600` atau *HashiCorp Vault*).
* **Menggunakan Autentikasi `trust` atau `md5`:** Mengonfigurasi `pg_hba.conf` dengan metode `trust` pada subnet non-loopback atau memakai `md5` yang rentan terhadap *hash collision*.
* **Backup Hanya Berupa Logical Dump (`pg_dump`) Sekali Sehari:** Jika database rusak pada pukul 23:59, data selama 23 jam 59 menit hilang (RPO 24 jam).
* **Menyimpan Backup di Disk yang Sama dengan `$PGDATA`:** Kerusakan controller disk atau volume corrupt akan memusnahkan data operasional sekaligus file backup-nya.
* **Mengabaikan File Sinyal Recovery:** Memulai ulang engine database tanpa membersihkan konfigurasi pemulihan lama yang menyebabkan *split-brain* atau *endless recovery loop*.

---

### 12: Security Hardening

#### A. Center for Internet Security (CIS) Benchmark Checklist
Terapkan parameter berikut pada `postgresql.conf` untuk memenuhi standard audit:

```ini
# Enkripsi Password Terkuat
password_encryption = scram-sha-256

# Nonaktifkan Dynamic Shared Memory tak terotorisasi
dynamic_shared_memory_type = posix

# Batasi Hak Eksekusi Log
log_file_mode = 0600
log_directory = '/var/log/postgresql'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'

# Logging & Audit Configuration
logging_collector = on
log_connections = on
log_disconnections = on
log_duration = off
log_hostname = off
log_line_prefix = '%m [%p] %q%u@%d '
log_statement = 'ddl'
log_timezone = 'UTC'

# PGAudit Integration Configuration
pgaudit.log = 'write, ddl, role, misc'
pgaudit.log_catalog = off
pgaudit.log_level = 'log'
pgaudit.log_parameter = on
pgaudit.log_relation = on
pgaudit.log_statement_once = off

# Mencegah Connection Exhaustion Attack (DoS)
max_connections = 200
superuser_reserved_connections = 5
```

#### B. Storage Level Hardening (Linux LUKS)
Pastikan partisi filesystem PostgreSQL dienkripsi pada layer sistem operasi jika TDE native engine tidak tersedia:
```bash
# Setup Disk Enkripsi LUKS
cryptsetup luksFormat --type luks2 --cipher aes-xts-plain64 --key-size 512 --hash sha512 /dev/nvme0n1p2
cryptsetup open /dev/nvme0n1p2 pg_encrypted_data
mkfs.ext4 -m 0 /dev/mapper/pg_encrypted_data
mount /dev/mapper/pg_encrypted_data /var/lib/postgresql/data
```

---

### 13: Observabilitas & Debugging

#### Script Query Pemantau Status Backup & WAL Archiving
Eksekusi query berikut untuk memonitor apakah proses continuous archiving berjalan tanpa lag:

```sql
SELECT
    archived_count,
    last_archived_wal,
    last_archived_time,
    failed_count,
    last_failed_wal,
    last_failed_time,
    CAST(EXTRACT(EPOCH FROM (clock_timestamp() - last_archived_time)) AS INTEGER) AS archive_lag_seconds
FROM pg_stat_archiver;
```

#### Query Audit Verifikasi Hak Akses User
```sql
SELECT 
    grantee, 
    table_schema, 
    table_name, 
    privilege_type 
FROM information_schema.role_table_grants 
WHERE grantee NOT IN ('postgres', 'PUBLIC')
ORDER BY grantee, table_name;
```

#### Log Analysis untuk PGAudit
Pantau log audit sistem dari shell:
```bash
tail -f /var/log/postgresql/postgresql.log | grep "AUDIT:"
# Format Keluaran:
# 2026-03-30 11:20:00.123 UTC [4520] app_user@production_db AUDIT: SESSION,1,1,DDL,ALTER TABLE,TABLE,ecom.orders,ALTER TABLE ecom.orders ADD COLUMN status VARCHAR(20),<not logged>
```

---

### 14: Benchmarking & Performance

Proses backup dan audit logging menghasilkan beban I/O serta komputasi. Lakukan benchmarking untuk mengukur *overhead* tersebut.

#### 1. Baseline Benchmark menggunakan `pgbench`
Inisialisasi dataset skala 100 (~1.6 GB):
```bash
pgbench -i -s 100 -U postgres production_db
```

#### 2. Jalankan Pengujian Beban Read-Write Standar
```bash
pgbench -c 20 -j 4 -T 120 -U postgres production_db > baseline_bench.txt
```

#### 3. Jalankan Pengujian Beban Bersamaan dengan Base Backup
```bash
# Terminal 1: Eksekusi Base Backup dengan WAL Streaming
pg_basebackup -h 127.0.0.1 -U replicator -D /tmp/bench_backup -Fp -Xs -c fast

# Terminal 2: Eksekusi Pengujian Beban secara Simultan
pgbench -c 20 -j 4 -T 120 -U postgres production_db > concurrent_backup_bench.txt
```

#### 4. Metrik Evaluasi Komparasi
Hitung selisih metrik dari kedua file output:
* **Throughput (Transactions Per Second / TPS):** Toleransi degradasi TPS selama *full physical backup* tidak boleh melebihi **15-20%**. Gunakan parameter `--checkpoint=spread` untuk meratakan I/O checkpoint.
* **Latency (95th Percentile):** Waktu respon latensi query tidak boleh melompat lebih dari 2.5x rata-rata baseline normal.

---

### 15: Hands-on Lab Mini-Project

#### Judul Mini-Project: "Simulasi Serangan Bencana Katastropik dan Rekonstruksi PITR"

#### Skenario Lab:
1. Administrator membuat transaksi finansial penting.
2. Operator secara tidak sengaja menghapus tabel keuangan vital pada pukul tertentu.
3. Transaksi baru yang sah masuk setelah tabel terhapus (skenario partisi).
4. Tugas: Bangkitkan *Secondary Node Disaster Recovery* dan pulihkan database ke kondisi 1 detik tepat sebelum eksekusi `DROP TABLE`.

#### Instruksi Kerja:

1. **Inisialisasi Tabel & Data Awal:**
```sql
CREATE DATABASE banking_db;
\c banking_db;

CREATE TABLE customer_balances (
    account_number VARCHAR(20) PRIMARY KEY,
    holder_name TEXT NOT NULL,
    balance NUMERIC(15,2) NOT NULL
);

INSERT INTO customer_balances VALUES 
('ACC-001', 'Satoshi Nakamoto', 50000000.00),
('ACC-002', 'Ada Lovelace', 75000000.00);

-- Ambil Timestamp 1 (Valid)
SELECT current_timestamp AS timestamp_valid;
```

2. **Simulasi Human Error (Bencana):**
```sql
-- Tunggu beberapa detik, lalu simulasikan disaster:
SELECT pg_sleep(5);
DROP TABLE customer_balances;

-- Ambil Timestamp 2 (Disaster Point)
SELECT current_timestamp AS timestamp_disaster;
```

3. **Langkah Pemulihan:**
   * Ambil *timestamp_valid* dari langkah 1.
   * Ikuti skrip shell pemulihan pada **Seksi 08: Bagian C**.
   * Tetapkan `recovery_target_time = '<TIMESTAMP_VALID_DARI_LANGKAH_1>'`.
   * Nyalakan PostgreSQL, verifikasi tabel `customer_balances` berhasil kembali dengan saldo utuh.

---

### 16: Automated Testing & Verification

Gunakan Python test suite berikut untuk memvalidasi konfigurasi keamanan, konektivitas TLS 1.3, dan integritas isolasi RLS secara otomatis:

```python
#!/usr/bin/env python3
"""
PostgreSQL Security and Integrity Verification Suite
Requirements: psycopg2-binary, pytest
"""

import psycopg2
import pytest

DB_PARAMS = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "production_db",
    "user": "postgres",
    "password": "MasterSecurePassword2026!"
}

def test_tls_connection_enforced():
    """Memastikan koneksi database wajib menggunakan TLS 1.3."""
    conn = psycopg2.connect(**DB_PARAMS, sslmode='require')
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM pg_stat_ssl WHERE pid = pg_backend_pid();")
    ssl_version = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert ssl_version == "TLSv1.3", f"Expected TLSv1.3, but got {ssl_version}"

def test_scram_sha_256_active():
    """Memastikan enkripsi password menggunakan SCRAM-SHA-256."""
    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()
    cursor.execute("SHOW password_encryption;")
    encryption_type = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert encryption_type == "scram-sha-256", f"Weak encryption: {encryption_type}"

def test_pgaudit_installed():
    """Memastikan PGAudit telah aktif pada sistem."""
    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()
    cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'pgaudit';")
    ext = cursor.fetchone()
    cursor.close()
    conn.close()
    assert ext is not None, "PGAudit extension is not loaded!"

def test_wal_archiving_status():
    """Memastikan tidak ada backlog kegagalan pada proses continuous archiving WAL."""
    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()
    cursor.execute("SELECT failed_count FROM pg_stat_archiver;")
    failed_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert failed_count == 0, f"Critical: WAL archiver reported {failed_count} failures!"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
```

---

### 17: Troubleshooting Guide

| Gejala Masalah | Investigasi Root Cause | Solusi Resolusi |
| :--- | :--- | :--- |
| `FATAL: no pg_hba.conf entry for host ... SSL off` | Klien mencoba menyambung tanpa SSL/TLS atau entri `hostssl` di `pg_hba.conf` memblokir subnet klien.