# Bab 08 Module 01: Replication & Streaming Architecture

---

## 01. Identitas Modul
* **Track:** Database Administrator (PostgreSQL DBA)
* **Kategori:** 04-Backend-and-Database
* **Modul:** Bab 08 - Module 01
* **Topik:** Replication & Streaming Architecture
* **Tingkat Kesulitan:** Advanced / Production-Grade
* **Prasyarat:** Pemahaman mendalam tentang Arsitektur PostgreSQL Storage Engine, WAL (Write-Ahead Logging), Checkpointer, IPC, Bash Scripting, dan Networking (TCP/IP).

---

## 02. Learning Objectives
1. Menguasai arsitektur internal physical streaming replication pada PostgreSQL (walsender, walreceiver, startup process).
2. Mengonfigurasi, mengelola, dan mengoptimalkan physical streaming replication baik secara Asynchronous maupun Synchronous (`synchronous_commit` levels).
3. Mengimplementasikan Replication Slots untuk menjamin ketersediaan WAL tanpa memicu disk bloat atau silent disconnection.
4. Menerapkan skema high-availability baseline dengan monitoring lag (byte lag dan time lag) secara presisi menggunakan view internal PostgreSQL.
5. Melakukan failover dan promotion secara deterministik dengan downtime minimal dan integritas data terjamin.

---

## 03. Concept Map Diagram ASCII

```
                    PRIMARY NODE (Read-Write)
      +----------------------------------------------------+
      |  Shared Buffers <---> Checkpointer / Background W. |
      |         |                                          |
      |         v                                          |
      |     WAL Buffers                                    |
      |         |                                          |
      |         v                                          |
      |     WAL Disk (/pg_wal) <====== [Physical Slot]     |
      |         |                             |            |
      |         +---------> walsender Process |            |
      +---------------------------|-----------|------------+
                                  | TCP Link  | (Keeps WAL retention)
                                  v           |
      +---------------------------------------v------------+
      | walreceiver Process                                |
      |         |                                          |
      |         v                                          |
      |  Write / Flush to Standby WAL Disk (/pg_wal)       |
      |         |                                          |
      |         v                                          |
      | Startup Process (Redo Engine)                      |
      |         |                                          |
      |         v                                          |
      |   Shared Buffers (Standby Data Pages)              |
      +----------------------------------------------------+
                   STANDBY NODE (Read-Only)
```

---

## 04. Mengapa Relevan
Dalam arsitektur data modern, ketersediaan tinggi (*High Availability*) dan skalabilitas pembacaan (*Read Scalability*) bukan lagi fitur opsional, melainkan kebutuhan primer enterprise. Mengandalkan satu node database menciptakan *Single Point of Failure* (SPOF). Replikasi fisik streaming (*Physical Streaming Replication*) PostgreSQL mentransmisikan modifikasi data level block (WAL) secara real-time dari primary ke satu atau lebih standby node. Memahami mekanismenya secara presisi membedakan DBA reaktif dari DBA proaktif yang mampu menjamin zero-data-loss (RPO=0) dan recovery cepat (RTO rendah) saat insiden infrastruktur terjadi.

---

## 05. Anatomi Konsep Inti

### 1. Internal Engine: Walsender & Walreceiver
* **`walsender`**: Background worker process pada Primary node yang membaca WAL records dari WAL buffers atau `/pg_wal` disk, lalu mentransmisikannya melalui streaming replication protocol (TCP) ke Standby.
* **`walreceiver`**: Background worker process pada Standby node yang menerima WAL frame dari `walsender`, menulisnya ke storage lokal standby, dan memicu `startup process`.
* **`startup process`**: Engine recovery pada Standby yang mengeksekusi operasi REDO—menerapkan WAL records ke data pages standby secara kontinu.

### 2. Synchronization Levels (`synchronous_commit`)
PostgreSQL menyediakan kontrol granular atas konfirmasi transaksi pada primary relatif terhadap kondisi standby:
* **`off`**: Transaksi di-commit secara logis sebelum WAL di-flush ke disk lokal Primary.
* **`local` / `on` (Async)**: Transaksi di-commit setelah WAL lokal primary di-flush. Standby menerima WAL secara asynchronous.
* **`remote_write`**: Primary menunggu konfirmasi bahwa Standby telah menerima WAL dan menulisnya ke OS cache (belum tentu tersimpan di storage disk standby).
* **`on` (Sync Replication)**: Primary menunggu hingga Standby melakukan *flush* (fsync) WAL ke disk lokalnya.
* **`remote_apply`**: Primary menunggu hingga Standby menerapkan (*apply*) WAL ke shared buffers/data file-nya via startup process. Menjamin read-after-write consistency di Standby.

### 3. Replication Slots
Mekanisme yang menjamin Primary node **tidak akan menghapus atau mendaur ulang** segmen WAL yang belum dikonsumsi dan diakui (*acknowledged*) oleh Standby yang terdaftar. Tanpa replication slot, primary dapat mendaur ulang WAL jika `wal_keep_size` terlampaui, menyebabkan standby crash (*replication broken/WAL segment missing*).

---

## 06. Panduan Implementasi Step-by-Step

### Skenario
* **Primary IP:** `192.168.10.10`
* **Standby IP:** `192.168.10.11`
* **PostgreSQL Version:** 16

### Langkah 1: Konfigurasi Primary Node (`postgresql.conf`)
```ini
# Edit /etc/postgresql/16/main/postgresql.conf
listen_addresses = '*'
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
wal_keep_size = 2048MB
hot_standby = on
archive_mode = on
archive_command = 'test ! -f /mnt/nfs_wal_archive/%f && cp %p /mnt/nfs_wal_archive/%f'
```

### Langkah 2: Autentikasi Jaringan (`pg_hba.conf` pada Primary)
```ini
# Tambahkan baris ini pada /etc/postgresql/16/main/pg_hba.conf
host  replication  replicator_user  192.168.10.11/32  scram-sha-256
```

### Langkah 3: Provisioning User Replikasi & Physical Slot
Jalankan di Primary:
```sql
CREATE ROLE replicator_user WITH REPLICATION LOGIN ENCRYPTED PASSWORD 'SuperSecureReplicationPass123!';
SELECT pg_create_physical_replication_slot('standby_node_1');
```
Reload primary:
```bash
sudo systemctl reload postgresql
```

### Langkah 4: Baseline Clone Data Menggunakan `pg_basebackup` pada Standby Node
Hentikan PostgreSQL di Standby, bersihkan data directory, lalu tarik base backup:
```bash
sudo systemctl stop postgresql
sudo rm -rf /var/lib/postgresql/16/main/*

PGPASSWORD='SuperSecureReplicationPass123!' pg_basebackup \
  -h 192.168.10.10 \
  -p 5432 \
  -U replicator_user \
  -D /var/lib/postgresql/16/main \
  -Fp -Xs -P -R \
  --slot=standby_node_1
```
*Catatan:* Opsi `-R` otomatis men-generate file `standby.signal` dan parameter `primary_conninfo` di `postgresql.auto.conf`.

### Langkah 5: Start Standby & Validasi
```bash
sudo chown -R postgres:postgres /var/lib/postgresql/16/main
sudo chmod 700 /var/lib/postgresql/16/main
sudo systemctl start postgresql
```

---

## 07. Contoh Kasus Sederhana

Verifikasi keselarasan data antara Primary dan Standby secara langsung:

**Pada Primary Node:**
```sql
CREATE TABLE replication_health_check (
    id SERIAL PRIMARY KEY,
    payload TEXT,
    created_at TIMESTAMPTZ DEFAULT clock_timestamp()
);

INSERT INTO replication_health_check (payload) VALUES ('Verification Sync Token 001');
```

**Pada Standby Node (Eksekusi 1 detik kemudian):**
```sql
SELECT * FROM replication_health_check;
```
Hasil: Baris `Verification Sync Token 001` muncul secara instan di Standby.

---

## 08. Implementasi Production-Grade Lengkap Kode

### 1. Hardened Production Configuration: Primary Node
```ini
# /etc/postgresql/16/main/conf.d/99_replication.conf
listen_addresses = '*'
wal_level = replica
max_wal_senders = 16
max_replication_slots = 16
wal_keep_size = 4096MB
track_commit_timestamp = on

# Synchronous Replication Topology (1 Quorum/Priority-based Standby)
synchronous_commit = on
synchronous_standby_names = 'FIRST 1 (standby_node_1, standby_node_2)'

# Network timeout settings
wal_sender_timeout = 10000ms
```

### 2. Standby Node Custom Engine Tuning
```ini
# /etc/postgresql/16/main/conf.d/99_standby_tuning.conf
hot_standby = on
hot_standby_feedback = on
wal_receiver_timeout = 10000ms
wal_receiver_status_interval = 1s
max_standby_streaming_delay = 30000ms
max_standby_archive_delay = 30000ms
```

### 3. Production Initialization & Failover Script (`pg_orchestration.sh`)
```bash
#!/usr/bin/env bash
set -Eeuo pipefail

PRIMARY_HOST="192.168.10.10"
STANDBY_HOST="192.168.10.11"
PG_DATA="/var/lib/postgresql/16/main"
PG_USER="postgres"
REP_USER="replicator_user"
REP_PASS="SuperSecureReplicationPass123!"
SLOT_NAME="standby_node_1"

bootstrap_standby() {
    echo "[+] Bootstrapping Standby Node via pg_basebackup..."
    systemctl stop postgresql || true
    rm -rf "${PG_DATA:?}"/*
    
    export PGPASSWORD="${REP_PASS}"
    pg_basebackup \
        -h "${PRIMARY_HOST}" \
        -p 5432 \
        -U "${REP_USER}" \
        -D "${PG_DATA}" \
        -Fp -Xs -v -P -R \
        --slot="${SLOT_NAME}"
        
    unset PGPASSWORD
    chown -R postgres:postgres "${PG_DATA}"
    chmod 700 "${PG_DATA}"
    systemctl start postgresql
    echo "[+] Standby Node running and synchronized."
}

promote_standby() {
    echo "[!] Executing Controlled Promotion on Standby..."
    sudo -u postgres pg_ctlcluster 16 main promote
    echo "[+] Node successfully promoted to Read-Write Primary."
}

case "${1:-}" in
    bootstrap)
        bootstrap_standby
        ;;
    promote)
        promote_standby
        ;;
    *)
        echo "Usage: $0 {bootstrap|promote}"
        exit 1
        ;;
esac
```

---

## 09. Diagram Alur Kerja ASCII: Synchronous Commit (remote_apply)

```
 Client             Primary Node               Standby Node
   |                     |                          |
   |-- 1. INSERT/UPDATE->|                          |
   |                     |-- 2. Write Local WAL     |
   |                     |-- 3. Transmit WAL Frame->|
   |                     |                          |-- 4. Receive (walreceiver)
   |                     |                          |-- 5. Flush to Disk
   |                     |                          |-- 6. Apply to Engine
   |                     |                          |      (startup process)
   |                     |<-- 7. Acknowledge Apply--|
   |                     |
   |<-- 8. Commit Success|
```

---

## 10. Analisis Trade-offs

| Parameter | Konfigurasi | Keuntungan | Kerugian / Risiko |
| :--- | :--- | :--- | :--- |
| **Replication Mode** | Asynchronous (`synchronous_commit = local`) | Latensi write sangat rendah, primary kebal terhadap degradasi jaringan standby. | Potensi Data Loss (RPO > 0) jika Primary hancur total sebelum WAL terkirim. |
| **Replication Mode** | Synchronous Apply (`remote_apply`) | Zero Data Loss (RPO = 0), Read consistency instan di Standby node. | Latensi Commit meningkat drastis (bergantung pada RTT jaringan dan disk Standby). |
| **Replication Slot** | Enabled | Primary dijamin tidak membuang WAL yang belum dibaca Standby. | Jika Standby mati dalam waktu lama, disk Primary `/pg_wal` bisa penuh 100% dan mematikan instance. |
| **Conflict Control** | `hot_standby_feedback = on` | Mencegah query dibatalkan di Standby akibat vacuum Primary. | Menunda cleanup dead tuples di Primary, berpotensi memicu table bloat di Primary. |

---

## 11. Best Practices & Antipatterns

### Best Practices
1. **Gunakan Replication Slots Terisolasi:** Berikan nama unik untuk masing-masing slot per standby.
2. **Monitoring Disk Space `/pg_wal`:** Pasang alerting strict pada utilisasi disk primary jika replication slot lagging.
3. **Konfigurasi `max_slot_wal_keep_size`:** Tetapkan batas maksimum retensi WAL per slot (misal: `100GB`) untuk mencegah kehabisan storage di Primary jika Standby mengalami *extended outage*.

### Antipatterns
* **Mengandalkan `wal_keep_size` saja tanpa Slots:** Saat traffic lonjakan tinggi terjadi, WAL terbuang sebelum ditarik Standby, memaksa re-basebackup total.
* **Membiarkan Orphaned Slots:** Meninggalkan replication slot yang tidak lagi terhubung ke standby node aktif.
* **Menjalankan Sync Replication dengan Single Standby:** Jika standby mati, primary akan menolak seluruh query DML write/commit (freeze total). Gunakan minimal 2 Standby jika memakai sync replication.

---

## 12. Security Hardening
1. **Prinsip Least Privilege:** User replikasi HANYA boleh memiliki atribut `REPLICATION LOGIN`. Jangan berikan atribut `SUPERUSER`.
2. **Enkripsi Transmisi (TLS/SSL):** Paksa enkripsi pada `pg_hba.conf`:
   ```ini
   hostssl replication replicator_user 192.168.10.11/32 scram-sha-256
   ```
3. **Isolasi Network Interface:** Rute traffic replikasi melalui Dedicated Private Subnet/VLAN non-routable atau VPC Peering tanpa paparan Public IP.

---

## 13. Observabilitas & Debugging

### Dynamic SQL Queries untuk Monitoring Lag

**1. Eksekusi di Primary Node (Monitoring Transmisi, Flush, & Apply Lag):**
```sql
SELECT
    pid,
    application_name,
    client_addr,
    state,
    sync_state,
    sync_priority,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS sent_lag_bytes,
    pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag_bytes,
    pg_wal_lsn_diff(write_lsn, flush_lsn) AS flush_lag_bytes,
    pg_wal_lsn_diff(flush_lsn, replay_lsn) AS replay_lag_bytes,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS total_lag_bytes,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;
```

**2. Eksekusi di Standby Node (Status Penerimaan & Replay Time):**
```sql
SELECT
    pg_is_in_recovery() AS is_standby,
    pg_last_wal_receive_lsn() AS receive_lsn,
    pg_last_wal_replay_lsn() AS replay_lsn,
    pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn()) AS unapplied_bytes,
    now() - pg_last_xact_replay_timestamp() AS replication_delay_interval;
```

---

## 14. Benchmarking & Performance

Untuk mengukur dampak replikasi terhadap throughput transaksi Primary:

```bash
# 1. Jalankan benchmark baseline pada Primary
pgbench -i -s 50 -U postgres -d postgres

# 2. Uji Write IOPS pada synchronous_commit = local (Asynchronous)
pgbench -c 16 -j 4 -T 60 -U postgres -d postgres -M prepared

# 3. Ubah menjadi synchronous_commit = remote_apply, lalu uji ulang
sudo -u postgres psql -c "ALTER SYSTEM SET synchronous_commit = 'remote_apply';"
sudo -u postgres psql -c "SELECT pg_reload_conf();"

pgbench -c 16 -j 4 -T 60 -U postgres -d postgres -M prepared
```
*Analisis:* Catat penurunan Transactions Per Second (TPS) dan kenaikan average latency yang diakibatkan oleh overhead round-trip latency jaringan dan synchronous flush di standby.

---

## 15. Hands-on Lab Mini-Project

### Objective
Membangun cluster 1-Primary dan 1-Standby, memvalidasi failover, lalu memastikan Standby dapat menerima write operations setelah dipromosikan.

```bash
# Skenario Praktik Lokal (2 Instance Port Berbeda: 5432 & 5433)

# 1. Setup Primary (Port 5432)
sudo -u postgres initdb -D /var/lib/postgresql/demo_primary
echo "port = 5432" >> /var/lib/postgresql/demo_primary/postgresql.conf
echo "wal_level = replica" >> /var/lib/postgresql/demo_primary/postgresql.conf
sudo -u postgres pg_ctl -D /var/lib/postgresql/demo_primary -l /tmp/primary.log start

# 2. Buat Role & Slot
psql -p 5432 -U postgres -c "CREATE ROLE rep_user REPLICATION LOGIN PASSWORD 'labpass';"
psql -p 5432 -U postgres -c "SELECT pg_create_physical_replication_slot('lab_slot');"

# 3. Basebackup ke Standby Data Dir (Port 5433)
PGPASSWORD='labpass' pg_basebackup -h 127.0.0.1 -p 5432 -U rep_user -D /var/lib/postgresql/demo_standby -Fp -Xs -R --slot=lab_slot

# 4. Ubah Port Standby ke 5433 & Jalankan
echo "port = 5433" >> /var/lib/postgresql/demo_standby/postgresql.conf
sudo -u postgres pg_ctl -D /var/lib/postgresql/demo_standby -l /tmp/standby.log start

# 5. Uji Failover / Promotion
# Matikan Primary
sudo -u postgres pg_ctl -D /var/lib/postgresql/demo_primary stop -m immediate

# Promosikan Standby
sudo -u postgres pg_ctl -D /var/lib/postgresql/demo_standby promote

# Uji Write pada Node yang Baru Dipromosikan
psql -p 5433 -U postgres -c "CREATE TABLE promo_success (id INT);"
```

---

## 16. Automated Testing & Verification

Script Bash untuk validasi operasional cluster secara otomatis:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

PRIMARY_PORT=5432
STANDBY_PORT=5433
DB_USER="postgres"

echo "[TEST 1] Memeriksa State Standby Node..."
IS_STANDBY=$(psql -p ${STANDBY_PORT} -U ${DB_USER} -tAc "SELECT pg_is_in_recovery();")
if [ "${IS_STANDBY}" != "t" ]; then
    echo "FAILED: Node pada port ${STANDBY_PORT} bukan merupakan Standby!"
    exit 1
fi
echo "PASSED: Standby recovery state is TRUE."

echo "[TEST 2] Menguji Replikasi Data Antar Node..."
psql -p ${PRIMARY_PORT} -U ${DB_USER} -c "CREATE TABLE IF NOT EXISTS repl_test (ts TIMESTAMPTZ);"
psql -p ${PRIMARY_PORT} -U ${DB_USER} -c "TRUNCATE repl_test; INSERT INTO repl_test VALUES (now());"

sleep 1

PRIMARY_COUNT=$(psql -p ${PRIMARY_PORT} -U ${DB_USER} -tAc "SELECT count(*) FROM repl_test;")
STANDBY_COUNT=$(psql -p ${STANDBY_PORT} -U ${DB_USER} -tAc "SELECT count(*) FROM repl_test;")

if [ "${PRIMARY_COUNT}" -eq "${STANDBY_COUNT}" ] && [ "${STANDBY_COUNT}" -eq 1 ]; then
    echo "PASSED: Data ter-replikasi sempurna."
else
    echo "FAILED: Data mismatch! Primary: ${PRIMARY_COUNT}, Standby: ${STANDBY_COUNT}"
    exit 1
fi
```

---

## 17. Troubleshooting Guide

### Masalah 1: "FATAL: could not start WAL streaming: ERROR: replication slot '...' is active for PID ..."
* **Penyebab:** Ada proses `walreceiver` atau koneksi replikasi zombie yang masih mengunci slot tersebut.
* **Solusi:** Matikan koneksi sender yang menggantung di Primary:
  ```sql
  SELECT pg_terminate_backend(pid) FROM pg_stat_replication WHERE application_name = 'standby_node_1';
  ```

### Masalah 2: "FATAL: requested WAL segment has already been removed"
* **Penyebab:** Standby tertinggal terlalu jauh dan slot tidak aktif atau `wal_keep_size` terlampaui.
* **Solusi:**
  1. Jika WAL Archive tersedia: Konfigurasikan `restore_command` pada standby di `postgresql.conf`.
  2. Jika WAL Archive tidak ada: Standby harus di-rebuild ulang dari awal menggunakan `pg_basebackup`.

### Masalah 3: Query pada Standby Dibatalkan ("canceling statement due to conflict with recovery")
* **Penyebab:** Startup process pada Standby perlu menerapkan WAL update/delete terhadap data page yang sedang dibaca oleh user query yang berjalan lama.
* **Solusi:** 
  1. Aktifkan `hot_standby_feedback = on` pada Standby.
  2. Tingkatkan nilai `max_standby_streaming_delay` (misal ke `60s`).

---

## 18. Checklist Produksi

- [ ] `wal_level` diset minimal ke `replica` di Primary.
- [ ] User replikasi menggunakan autentikasi kuat (`scram-sha-256`) dan network dibatasi di `pg_hba.conf`.
- [ ] Physical Replication Slot digunakan untuk setiap standby node.
- [ ] Parameter `max_slot_wal_keep_size` ditentukan untuk mengamankan disk Primary.
- [ ] `hot_standby_feedback = on` aktif jika terdapat read-heavy analytical query di standby.
- [ ] Healthcheck script memantau metrik `pg_stat_replication` dan `total_lag_bytes`.
- [ ] File backup level filesystem (`pg_basebackup`) sudah terverifikasi integritasnya secara berkala.
- [ ] Prosedur Promosi (Failover) dan Reverse Reprovisioning terdokumentasi dan diuji berkala.

---

## 19. Ringkasan Eksekutif
Replikasi fisik streaming PostgreSQL adalah pondasi utama ketahanan infrastruktur database tingkat lanjut. Arsitektur ini mentransmisikan perubahan disk berbasis byte (WAL) via protokol TCP secara berkelanjutan. Konfigurasi `synchronous_commit` menentukan trade-off mutlak antara konsistensi data (RPO=0) dan performa latensi DML. Penggunaan Replication Slots wajib diatur bersama parameter proteksi `max_slot_wal_keep_size` untuk mencegah kegagalan fatal disk capacity. Monitoring kontinu terhadap metrik `write_lag`, `flush_lag`, dan `replay_lag` mutlak diperlukan guna menjamin kesiapan *disaster recovery* setiap saat.

---

## 20. Referensi & Bacaan Lanjutan
* PostgreSQL Documentation: High Availability, Load Balancing, and Replication (Chapter 27).
* PostgreSQL Documentation: Write-Ahead Logging (WAL) & Reliability (Chapter 30).
* PostgreSQL Documentation: Continuous Archiving and Point-in-Time Recovery (PITR).
* PostgreSQL Source Code: `src/backend/replication/walsender.c` & `walreceiver.c`.