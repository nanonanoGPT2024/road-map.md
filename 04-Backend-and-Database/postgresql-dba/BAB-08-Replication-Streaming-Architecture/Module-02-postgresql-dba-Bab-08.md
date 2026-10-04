# BAB 08: Replication & Streaming Architecture
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Menguasai arsitektur internal PostgreSQL physical streaming replication, termasuk mekanisme kerja sub-proses `walsender`, `walreceiver`, `startup process`, serta struktur sinkronisasi di *shared memory*.
- Mengonfigurasi dan memvalidasi level sinkronisasi (`synchronous_commit = off | local | remote_write | on | remote_apply`) serta merancang quorum-based synchronous replication untuk eliminasi *single point of failure* (SPOF).
- Mengimplementasikan topologi *Cascading Replication* bertingkat guna memitigasi beban jaringan dan I/O pada Primary Node di lingkungan multi-region.
- Mengelola siklus hidup *Physical Replication Slots*, mengisolasi risiko ledakan disk akibat *abandoned slots* dengan parameter proteksi modern (`max_slot_wal_keep_size`), serta mengeliminasi replikasi lag.
- Menangani *query cancellation conflicts* pada Read Replica menggunakan tuning presisi pada `hot_standby_feedback`, `max_standby_streaming_delay`, dan snapshot isolation.
- Merancang arsitektur High Availability (HA) dan Disaster Recovery (DR) kelas enterprise dengan metrik Recovery Point Objective (RPO) = 0 dan Recovery Time Objective (RTO) < 30 detik.

---

### 2. Prerequisite
Untuk memahami modul ini secara komprehensif, peserta wajib menguasai:
- **Module 01 Bab 08**: Konsep dasar Write-Ahead Logging (WAL), Log Sequence Number (LSN), dan replikasi asinkron dasar.
- **Arsitektur Memori PostgreSQL**: Pemahaman mendalam terkait *Shared Buffers*, *WAL Buffers*, dan *Checkpointer*.
- **Sistem Operasi & Jaringan Linux**: TCP/IP socket buffer tuning (`SO_KEEPALIVE`, `TCP_NODELAY`), manajemen disk volume (LVM/ZFS), dan izin file sistem POSIX.
- **SQL & Administrasi Database**: Eksekusi perintah administratif via `psql` dan pembacaan *system catalog/views* (`pg_stat_replication`, `pg_stat_wal_receiver`).

---

### 3. Concept & Internal Architecture

#### 3.1 Siklus Hidup dan Interaksi Sub-Proses Replikasi
Arsitektur *Physical Streaming Replication* bekerja dengan mereplikasi mutasi biner halaman data (*byte-by-byte physical page modifications*) dari Primary ke Standby melalui aliran WAL records.

```
+---------------------------------------------------------------------------------------------------+
| PRIMARY NODE                                                                                      |
|                                                                                                   |
|  [Client Backend]                                                                                 |
|         │                                                                                         |
|         │ (1) Write WAL Record                                                                    |
|         ▼                                                                                         |
|  [WAL Buffers] ──(XLogFlush)──► [pg_wal Disk]                                                     |
|         │                                                                                         |
|         │ (2) Read Memory / Disk                                                                  |
|         ▼                                                                                         |
|   [walsender] ────(SyncRepQueue Wait)◄───┐                                                        |
+─────────┬────────────────────────────────┼────────────────────────────────────────────────────────+
          │ TCP Stream                     │ LSN Feedback Packets                                   
          │ (WAL Pages)                    │ (Write, Flush, Apply LSN)                              
          ▼                                │                                                        
+──────────────────────────────────────────┼────────────────────────────────────────────────────────+
| STANDBY NODE                             │                                                        |
|                                          │                                                        |
|  [walreceiver] ──(3) Write to OS Buffer  │                                                        |
|         │                                │                                                        |
|         ├──► [pg_wal Disk] ──────────────┘                                                        |
|         │                                                                                         |
|         │ (4) Signal Startup Process via Shared Memory                                            |
|         ▼                                                                                         |
|  [Startup Process] ──(5) Apply/Redo Pages──► [Shared Buffers] ──► [Data Files Disk]               |
|         ▲                                                                                         |
|         │ Checks Snapshot Conflicts                                                               |
|  [Read-Only Query]                                                                                |
+---------------------------------------------------------------------------------------------------+
```

1. **Client Backend & XLogInsert/Flush**: Setiap transaksi DML/DDL menghasilkan record WAL pada *WAL Buffers*. Saat transaksi melakukan `COMMIT`, backend mengeksekusi `XLogFlush()`, memaksa kernel memindahkan data dari buffer ke storage fisik (`pg_wal`).
2. **Sub-proses `walsender`**:
   - Di-*fork* oleh postmaster pada node Primary untuk setiap koneksi Standby.
   - Membaca record WAL secara langsung dari *WAL Buffers* (jika masih berada di memori) atau dari disk `pg_wal` (jika proses transmisi tertinggal).
   - Mengirimkan paket data WAL melalui soket TCP menggunakan protokol PostgreSQL Streaming Replication.
3. **Sub-proses `walreceiver`**:
   - Dijalankan oleh Standby node untuk menginisiasi dan menjaga koneksi streaming ke `walsender` pada Primary.
   - Menerima chunk WAL dan menulisnya ke disk WAL Standby (`write`), kemudian melakukan sinkronisasi ke disk melalui fsync (`flush`).
   - Secara berkala mengirimkan paket status (*feedback packet*) ke Primary, melaporkan tiga posisi penting:
     - `received/write LSN`: Titik data sudah ditulis ke OS page cache standby.
     - `flushed LSN`: Titik data sudah persisten secara fisik di disk standby.
     - `applied LSN`: Titik data sudah dibaca dan diterapkan oleh *startup process* ke data files.
4. **Sub-proses `Startup Process`**:
   - Berjalan pada Standby node sebagai entitas mesin *Redo Recovery*.
   - Membaca data yang telah di-*flush* oleh `walreceiver` dan menerapkannya ke *Shared Buffers* serta berkas relasi (`base/`).
   - Bertanggung jawab memvalidasi bahwa blok data yang dimutasi tidak mengalami konflik dengan transaksi baca lokal (*Hot Standby*).

#### 3.2 Synchronous Commit State Machine & LSN Tracking
Parameter `synchronous_commit` mengontrol level persistensi data sebelum primary mengembalikan status konfirmasi `COMMIT` sukses ke client.

| Level | Kapan Client Mendapatkan Konfirmasi Commit? | Proteksi Kegagalan | Latensi Commit |
| :--- | :--- | :--- | :--- |
| `off` | Sebelum WAL di-flush ke disk lokal Primary (asinkron total). | Data loss jika Primary crash seketika. | Terendah (< 0.1ms). |
| `local` | Setelah WAL di-flush ke disk lokal Primary (`XLogFlush()`). | Aman dari crash Primary; Standby asinkron. | Rendah (Disk I/O lokal). |
| `remote_write` | Setelah Standby menerima WAL dan menulisnya ke OS kernel cache (belum tentu fsync). | Aman jika OS Standby tetap hidup saat Primary mati. | Sedang (Jaringan + Write OS). |
| `on` | Setelah Standby menulis dan melakukan `fsync` WAL ke disk fisiknya. | Nol data loss (RPO=0) saat Primary crash mendadak. | Tinggi (Jaringan + fsync Standby). |
| `remote_apply` | Setelah Standby selesai menerapkan WAL record ke data buffer (*Startup Process* selesai me-replay). | Zero Lag Read (Read-after-write consistency di Standby menjamin data langsung terlihat). | Tertinggi (Jaringan + fsync + Replay CPU/IO). |

Pada level `on` dan `remote_apply`, backend di node Primary akan mendaftarkan dirinya ke dalam antrean tunggu memori (*SyncRepQueue*) dan menunda pengiriman paket respon TCP `CommandComplete ('COMMIT')` ke client sampai thread `walsender` memicu sinyal bahwa `flushed LSN` atau `applied LSN` dari Standby telah melampaui posisi LSN commit backend tersebut.

#### 3.3 Anatomi Physical Replication Slots
Replication slot menggaransi bahwa Primary Node **tidak akan mendaur ulang atau menghapus berkas WAL segmen apa pun** dari direktori `pg_wal` sebelum Standby yang diasosiasikan dengan slot tersebut mengonfirmasi bahwa segmen tersebut telah berhasil diterima.
- **Mekanisme**: Setiap slot menyimpan nilai `restart_lsn`. Nilai ini merepresentasikan LSN tertua yang masih dibutuhkan oleh Standby.
- **Checkpointer Guard**: Saat proses `Checkpointer` berjalan di Primary untuk merotasi WAL file (`checkpoint_completion_target`), checkpointer mengevaluasi nilai minimum dari seluruh `restart_lsn` di `pg_replication_slots`. Checkpointer dilarang menghapus segmen di bawah nilai LSN tersebut.
- **Risiko Kegagalan Fatal**: Jika Standby node mati dalam durasi lama atau koneksi jaringan terputus, Primary akan terus mengumpulkan berkas WAL di `pg_wal` hingga disk penuh 100%, yang mengakibatkan Primary mengalami *Panic Crash* dan menolak transaksi tulis baru.

---

### 4. Why & What

| Dimensi | Pendekatan Tradisional (Naive Async Replication) | Pendekatan Advanced (Synchronous, Slots, Cascading) |
| :--- | :--- | :--- |
| **Konsistensi Data (RPO)** | Bersifat probabilistik. RPO bervariasi dari beberapa ratus milidetik hingga jam tergantung beban jaringan. | RPO terukur secara deterministik. Dapat disetel hingga mutlak 0 (`synchronous_commit = on` atau `remote_apply`). |
| **Resistensi Beban Primary** | Skala linier degradasi. Setiap standby node baru menambah beban CPU `walsender` dan I/O transfer dari Primary. | Optimal via *Cascading Replication*. Primary hanya mentransmisikan WAL ke 1-2 hub node, lalu didistribusikan ke leaf nodes. |
| **Manajemen Retensi WAL** | Berbasis tebakan (`wal_keep_size`). Jika burst transaksi melebihi kapasitas kalkulasi, standby putus permanen. | Terjamin via *Replication Slots* dipadukan dengan fail-safe `max_slot_wal_keep_size` untuk mitigasi Out-of-Disk. |
| **Read Scalability** | Query analytical panjang sering kali dibatalkan secara agresif (*recovery conflict*) atau menahan replay WAL. | Dikelola presisi via `hot_standby_feedback` dan alokasi *query routing* berbasis LSN watermark. |

---

### 5. How (Workflow Detail)

#### Fase 1: Transmisi WAL & Komitmen Transaksi
1. Client mengeksekusi `COMMIT`.
2. Backend Primary menulis record commit ke *WAL Buffers* dan memanggil `XLogFlush()` untuk memastikan persistensi lokal.
3. Sub-proses `walsender` mendeteksi data baru di buffer/disk, membungkus WAL records ke dalam frame replikasi, dan memompanya ke soket jaringan TCP.
4. Di sisi Standby, sub-proses `walreceiver` membaca socket buffer, mengeksekusi sistem pemanggilan `write()` ke disk chunk Standby, dan mengeksekusi `fdatasync()`/`fsync()`.
5. `walreceiver` menyusun paket umpan balik (*Feedback Packet*), menyematkan posisi LSN terakhir yang di-write, di-flush, dan di-apply, lalu mengirimkannya kembali ke Primary.
6. `walsender` pada Primary mengekstrak paket tersebut, memvalidasi target LSN, dan membangunkan (*wake up*) proses Client Backend yang terkunci di `SyncRepQueue`.
7. Client Backend melepaskan lock dan mengirim pesan `'COMMIT 200 OK'` ke aplikasi.

#### Fase 2: Redo Engine & Handling Recovery Conflict
1. *Startup process* pada Standby membaca berkas WAL yang baru di-flush secara sekuensial.
2. Jika record WAL memerlukan perubahan pada suatu page data (misal: membersihkan baris tuple mati via vacuum, atau mengubah struktur B-Tree index):
   - Standby memeriksa apakah ada transaksi baca (`SELECT`) lokal yang sedang memegang lock atau snapshot yang melihat tuple/page tersebut.
   - Jika ada konflik dan `hot_standby_feedback = off`, Standby menahan apply proses hingga `max_standby_streaming_delay` tercapai.
   - Jika timeout terlampaui, backend yang menjalankan `SELECT` tersebut dihentikan paksa (*terminating connection due to conflict with recovery*).
3. Jika `hot_standby_feedback = on`, Standby secara periodik mengirimkan nilai `xmin` (transaksi tertua yang sedang aktif di standby) ke Primary. Primary menolak melakukan *vacuuming* pada tuple yang masih dibutuhkan oleh standby tersebut, mencegah timbulnya konflik semenjak awal.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Redaksi Surat Kabar Multinasional
- **Primary Node** adalah Kantor Pusat Redaksi di Jakarta. Wartawan menulis artikel (data transaksi) ke Buku Induk Cetak (WAL Buffer & Local Disk).
- **Standby Async** adalah Agen di Bandung. Jakarta mengirim naskah jika sempat; agen menerima dan mencetak koran kapan pun mereka bisa. Jika Jakarta terbakar, naskah 10 menit terakhir mungkin belum sampai di Bandung (Data Loss).
- **Standby Sync (`remote_apply`)** adalah Percetakan Mitra Utama. Percetakan di Jakarta tidak boleh mempublikasikan headline ke publik (Client) sebelum percetakan mitra menyatakan bahwa koran edisi tersebut sudah selesai dicetak di mesin mereka dan siap dibaca oleh pelanggan (Zero Data Loss, Zero Latency Read).
- **Cascading Replication** adalah Sistem Distributor Wilayah. Kantor Jakarta hanya mengirim 1 master copy ke Kantor Distribusi Surabaya. Lalu Surabaya membagikannya ke Malang, Banyuwangi, dan Denpasar. Jakarta hemat ongkos kirim (Primary CPU & Bandwidth terpelihara).

#### Diagram Detail: Arsitektur Multi-Tier & Quorum

```
                                  [PRIMARY] (DC-Jakarta)
                            wal_level = replica
                            synchronous_standby_names = 'ANY 1 (standby_sync_01, standby_sync_02)'
                                     │
           ┌─────────────────────────┴────────────────────────┐
           │ Synchronous Stream (TCP)                         │ Synchronous Stream (TCP)
           ▼                                                  ▼
   [STANDBY_SYNC_01]                                  [STANDBY_SYNC_02]
   (Zone-A Jakarta)                                   (Zone-B Jakarta)
   hot_standby = on                                   hot_standby = on
   sync_priority: Quorum Member 1                     sync_priority: Quorum Member 2
   (Fast Failover Target)                             (Fast Failover Target)
           │
           │ Cascading Stream (Asynchronous)
           │ Primary-like workload removed from Jakarta Primary
           ▼
   [STANDBY_RELAY_01] (DC-Singapore)
   hot_standby = on
   wal_level = replica
           │
           ├──────────────────────────────────────────────────┐
           │ Async Cascade                                    │ Async Cascade
           ▼                                                  ▼
   [STANDBY_READ_01] (SG Analytics)                   [STANDBY_READ_02] (SG Read-Pool)
   hot_standby_feedback = on                          hot_standby_feedback = off
                                                      max_standby_streaming_delay = 30s
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Dynamic Replication Status Check
Query operasional tingkat lanjut untuk memeriksa status latensi presisi hingga hitungan byte, microsecond, dan LSN gap langsung dari Primary:

```sql
SELECT
    client_addr AS client_ip,
    application_name,
    state,
    sync_state,
    sync_priority,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS bytes_pending_send,
    pg_wal_lsn_diff(sent_lsn, write_lsn) AS bytes_pending_write,
    pg_wal_lsn_diff(write_lsn, flush_lsn) AS bytes_pending_flush,
    pg_wal_lsn_diff(flush_lsn, replay_lsn) AS bytes_pending_replay,
    ROUND(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1024 / 1024, 2) AS total_lag_mb,
    reply_time AS last_feedback_timestamp
FROM pg_stat_replication;
```

#### 7.2 Practical Example: Enterprise Production Configuration Setup

##### Langkah 1: Konfigurasi Primary Node (`postgresql.conf`)
Menjamin performa, isolasi slot, dan toleransi kegagalan synchronous berbasis quorum.

```ini
# --- NETWORK & CONNECTIONS ---
listen_addresses = '*'
max_connections = 300
wal_level = replica
archive_mode = on
archive_command = '/usr/bin/pgbackrest --stanza=prod-cluster archive-push %p'

# --- REPLICATION CORE ---
max_wal_senders = 15
max_replication_slots = 10
wal_keep_size = 8192MB                # Fallback safety buffer (8GB)
max_slot_wal_keep_size = 65536MB      # Hard Cap (64GB) slot WAL retention!

# --- SYNCHRONOUS REPLICATION TOPOLOGY ---
# ANY 1 bermakna Quorum: jika salah satu dari standby 1 atau 2 merespons, commit dilepas.
synchronous_standby_names = 'ANY 1 (standby_dc_a, standby_dc_b)'
synchronous_commit = on

# --- TCP/IP PERFORMANCE & DEAD CONNECTION ELIMINATION ---
tcp_keepalives_idle = 10
tcp_keepalives_interval = 5
tcp_keepalives_count = 3
wal_sender_timeout = 60s
```

##### Langkah 2: Otorisasi Akses (`pg_hba.conf`)
Otorisasi berbasis CIDR spesifik menggunakan hashing password `scram-sha-256`.

```text
# TYPE  DATABASE        USER            ADDRESS                 METHOD
host    replication     replicator      10.240.10.11/32         scram-sha-256
host    replication     replicator      10.240.10.12/32         scram-sha-256
host    replication     replicator      10.240.20.15/32         scram-sha-256
```

##### Langkah 3: Konfigurasi Standby Node Pengirim Sinkron (`postgresql.conf`)
Node: `standby_dc_a` (IP: 10.240.10.11)

```ini
# Identitas Node untuk Quorum Primary
primary_conninfo = 'host=10.240.10.10 port=5432 user=replicator password=SuperSecurePassword application_name=standby_dc_a connect_timeout=10 keepalives=1 keepalives_idle=10 keepalives_interval=5 keepalives_count=3'
primary_slot_name = 'slot_standby_dc_a'

hot_standby = on
hot_standby_feedback = on

# Proteksi benturan replikasi vs query analytical lokal
max_standby_archive_delay = 60s
max_standby_streaming_delay = 60s
wal_receiver_status_interval = 1s
wal_receiver_timeout = 60s
```

##### Langkah 4: Pembuatan Slot Secara Eksplisit pada Primary
Eksekusi di Primary sebelum memulai *basebackup* Standby:

```sql
-- Dibuat sebagai Physical Slot
SELECT pg_create_physical_replication_slot(
    slot_name := 'slot_standby_dc_a', 
    immediately_reserve := true
);

SELECT pg_create_physical_replication_slot(
    slot_name := 'slot_standby_dc_b', 
    immediately_reserve := true
);
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Transaksi Finansial Cross-Region (Fintech Tier-1)
- **Karakteristik Beban**: 25,000 Payment TPS, 99th percentile write latency SLA < 15ms.
- **Topologi**:
  - DC-1 (Production Primary): Jakarta.
  - DC-2 (Synchronous Mirror): Cikarang (Jarak 45km, round-trip latency jaringan ~1.2ms).
  - DC-3 (DR Async Site & BI Reporting): Singapura (Jarak ~1000km, round-trip latency ~22ms).

```
   DC-1 (Jakarta Primary) ───────── Sync (ANY 1) ─────────► DC-2 (Cikarang Standby)
           │                                                        │
           │                                                        │ Asynchronous
           │                                                        │ (Cascade Layer)
           │                                                        ▼
           └──────────────── (Direct Async WAN Ditinggalkan) ──► DC-3 (Singapura Cascade Hub)
                                                                    │
                                                                    ├─► Read Replica Analytics
                                                                    └─► Read Replica Core ML
```

#### Masalah yang Dihadapi:
1. Awalnya, Primary di Jakarta streaming langsung ke Cikarang dan Singapura.
2. Latensi WAN Jakarta-Singapura yang fluktuatif menyebabkan thread `walsender` ke Singapura sering mengalami *TCP buffer bloat*, menghabiskan memori Primary.
3. Query agregasi harian analitik di Singapura sering memicu `terminating connection due to conflict with recovery` pada Standby node lokal.
4. Saat `hot_standby_feedback = on` diaktifkan di Singapura, **Table Bloat masif** terjadi di Primary Jakarta karena VACUUM menolak membersihkan dead tuples yang sedang diakses analitik berdurasi 3 jam di Singapura.

#### Solusi Arsitektural Enterprise:
1. **Penerapan Cascading Replication**:
   - Primary Jakarta memutus hubungan langsung dengan Singapura.
   - Standby Cikarang (DC-2) dijadikan cascade distributor. DC-2 menarik data dari DC-1 secara sinkron, lalu DC-2 mengekspos streaming secara asinkron ke DC-3 Singapura.
   - Hasil: Beban CPU dan I/O Primary Jakarta turun 30%, degradasi jaringan internasional terisolasi di DC-2.
2. **Isolasi Conflict dan Table Bloat**:
   - Mematikan `hot_standby_feedback = off` pada Standby Analitik di Singapura.
   - Mengalokasikan Standby Analitik khusus dengan konfigurasi:
     ```ini
     max_standby_streaming_delay = 4h
     ```
   - Replay WAL diizinkan tertunda selama analytical job berjalan, mengorbankan replikasi lag (RPO read) demi kestabilan primary dan keberhasilan query berat tanpa memicu table bloat di DC-1.

---

### 9. Trade-offs

```
                       [CONSISTENCY: Sync Replication (remote_apply)]
                                      /\
                                     /  \
                                    /    \
                                   /      \
                                  /        \
                                 /          \
                                /            \
  [AVAILABILITY: Async Multi-AZ] ------------ [PERFORMANCE: Sync Commit OFF]
```

| Pendekatan / Parameter | Keuntungan Utama | Kerugian / Risiko Tersembunyi |
| :--- | :--- | :--- |
| `synchronous_commit = remote_apply` | - Zero-lag reads pada Read Replica.<br>- Jaminan absolut konsistensi data read-after-write. | - Latensi commit write melambung drastis (menunggu Standby apply WAL ke disk data).<br>- Throughput write drop hingga 60-80%. |
| `synchronous_standby_names = 'FIRST 1'` | - Deterministik urutan prioritas failover node. | - Jika node urutan pertama freeze jaringan, seluruh cluster write terblokir (stalled) hingga deteksi timeout selesai. |
| `synchronous_standby_names = 'ANY 1'` | - Ketahanan ketersediaan tinggi: transaksi sukses jika salah satu standby merespons. | - Standby yang berada di urutan lebih lambat akan mengalami drift lag secara bertahap. |
| `hot_standby_feedback = on` | - Mencegah *query cancellation* akibat benturan recovery di Read Replica. | - **Paling Bahaya**: Mencegah proses VACUUM di node Primary. Mengakibatkan *Table Bloat* fatal jika replica menjalankan query durasi panjang. |
| `Replication Slots (Uncapped)` | - Standby tidak akan pernah tertinggal hingga putus replikasi (*WAL segment missing*). | - Jika standby down, direktori `pg_wal` Primary akan membengkak tak terbatas hingga storage penuh dan Primary crash. |

---

### 10. Common Mistakes & Troubleshooting

#### Kasus Fatal 1: Out-of-Disk Akibat Abandoned Replication Slot
- **Gejala**: Storage disk direktori database 100% penuh. PostgreSQL crash mendadak dengan log: `PANIC: could not write to file "pg_wal/...": No space left on device`.
- **Root Cause**: Suatu aplikasi data pipeline atau standby dev node mendaftarkan replication slot, lalu node tersebut dimatikan secara permanen tanpa menghapus slot di Primary. Checkpointer dilarang mendaur ulang WAL files.
- **Deteksi**:
  ```sql
  SELECT 
      slot_name, 
      active, 
      pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_bytes
  FROM pg_replication_slots
  ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC;
  ```
- **Remediasi Darurat**:
  1. Hapus slot yang tidak aktif (*abandoned*):
     ```sql
     SELECT pg_drop_replication_slot('abandoned_slot_name');
     ```
  2. Lindungi cluster untuk masa depan di file `postgresql.conf`:
     ```ini
     # Paksa batalkan proteksi slot jika WAL retained melampaui batas toleransi storage
     max_slot_wal_keep_size = 32768MB # Max 32GB
     ```

#### Kasus Fatal 2: Primary Hanging Total Saat Standby Down
- **Gejala**: Aplikasi mendadak tidak dapat melakukan mutasi data (INSERT/UPDATE/DELETE hang selamanya). Read query di Primary tetap berjalan normal.
- **Root Cause**: Administrator menyetel `synchronous_commit = on` dengan `synchronous_standby_names = 'standby_node_1'` (tunggal tanpa quorum), dan `standby_node_1` mati atau crash OS-nya.
- **Remediasi**:
  1. **Aksi Darurat**: Ubah sementara konfigurasi di Primary tanpa restart:
     ```sql
     ALTER SYSTEM SET synchronous_standby_names TO '';
     SELECT pg_reload_conf();
     ```
  2. Seluruh backend yang menggantung di `SyncRepQueue` akan seketika terlepas dan transaksi committed.
  3. **Pencegahan**: Selalu gunakan arsitektur Quorum minimal `ANY 1 (node1, node2)`.

#### Kasus Fatal 3: ERROR: canceling statement due to conflict with recovery
- **Gejala**: Aplikasi baca yang terhubung ke Read Replica menerima error kode `40001` atau `57014`.
- **Root Cause**: Primary membersihkan tuple mati yang dihapus/di-update sebelumnya via AutoVacuum. WAL penghapusan tersebut dikirim ke Standby dan harus diterapkan seketika oleh *Startup Process*, memutus transaksi di standby yang sedang membaca tuple tersebut.
- **Remediasi Bertingkat**:
  1. Tingkatkan toleransi delay:
     ```ini
     max_standby_streaming_delay = 300s # Default hanya 30s
     ```
  2. Jika query bersifat real-time kritis, aktifkan `hot_standby_feedback = on` pada standby (dengan audit ketat terhadap table bloat di primary).

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Configuration Audit
- [ ] `wal_level` disetel ke `replica` atau `logical` (jangan biarkan `minimal`).
- [ ] Direct I/O dan buffering dioptimalkan: `wal_buffers = 64MB` (atau -1 untuk alokasi dinamis).
- [ ] Proteksi batas atas retensi slot WAL: `max_slot_wal_keep_size` disetel secara proporsional terhadap partisi disk storage `pg_wal` (contoh: maksimal 60% dari free space disk).
- [ ] Metrik timeout protektif: `wal_sender_timeout = 60s` dan `wal_receiver_timeout = 60s`.
- [ ] Tuning TCP keepalive level socket PostgreSQL untuk deteksi dini pemutusan link WAN:
  - `tcp_keepalives_idle = 10`
  - `tcp_keepalives_interval = 5`
  - `tcp_keepalives_count = 3`

#### Monitoring & Health Checks Rutin
- [ ] Monitoring metrik `pg_stat_replication.replay_lag` berbasis ambang batas (Threshold Alarm: Warning jika > 5 Detik, Critical jika > 30 Detik).
- [ ] Monitoring `pg_replication_slots.active`: Jika `active = false` lebih dari 15 menit, sistem notifikasi PagerDuty harus otomatis menyala.
- [ ] Monitoring ketersediaan ruang penyimpanan partisi `pg_wal` secara terpisah dari partisi direktori data utama (`base/`).

---

### 12. Hands-on Practice

Buat skenario lab multi-node di mesin lokal menggunakan PostgreSQL 16+ pada path `hands-on/m02/`. Praktik ini mensimulasikan setup 1 Primary dan 2 Standby (1 Quorum Sync Standby, 1 Cascaded Read Replica).

```
hands-on/m02/
├── config/
│   ├── primary.conf
│   ├── standby1.conf
│   └── standby2_cascade.conf
├── scripts/
│   ├── 01_init_primary.sh
│   ├── 02_setup_standby1.sh
│   ├── 03_setup_cascade_standby2.sh
│   └── 04_simulate_failure_and_verify.sh
└── cleanup.sh
```

#### Langkah 1: `hands-on/m02/scripts/01_init_primary.sh`
Inisialisasi cluster Primary dan jalankan di port 5432.

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(pwd)/hands-on/m02"
PRIMARY_DATA="${BASE_DIR}/data/primary"

echo "=== [1/4] Menginisialisasi Primary Node ==="
rm -rf "${PRIMARY_DATA}"
mkdir -p "${PRIMARY_DATA}"

initdb -D "${PRIMARY_DATA}" -A scram-sha-256 -U postgres

# Setup Konfigurasi Primary
cat <<EOF >> "${PRIMARY_DATA}/postgresql.conf"
port = 5432
listen_addresses = '127.0.0.1'
wal_level = replica
max_wal_senders = 10
max_replication_slots = 10
synchronous_commit = on
synchronous_standby_names = 'ANY 1 (standby_01, standby_02)'
max_slot_wal_keep_size = 5120MB
hot_standby = on
EOF

cat <<EOF >> "${PRIMARY_DATA}/pg_hba.conf"
host replication replicator 127.0.0.1/32 scram-sha-256
EOF

pg_ctl -D "${PRIMARY_DATA}" -l "${BASE_DIR}/primary.log" start

# Buat User Replikasi & Slot
psql -h 127.0.0.1 -p 5432 -U postgres -c "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'SecretKey123!';"
psql -h 127.0.0.1 -p 5432 -U postgres -c "SELECT pg_create_physical_replication_slot('slot_standby_01');"
psql -h 127.0.0.1 -p 5432 -U postgres -c "SELECT pg_create_physical_replication_slot('slot_standby_02');"

echo "=== Primary Node Sukses Dikonfigurasi di Port 5432 ==="
```

#### Langkah 2: `hands-on/m02/scripts/02_setup_standby1.sh`
Clone data dari Primary via `pg_basebackup` dan jalankan Standby 1 di port 5433 (Synchronous Target).

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(pwd)/hands-on/m02"
STANDBY1_DATA="${BASE_DIR}/data/standby1"

echo "=== [2/4] Setup Standby 1 via pg_basebackup ==="
rm -rf "${STANDBY1_DATA}"
mkdir -p "${STANDBY1_DATA}"

PGPASSWORD='SecretKey123!' pg_basebackup \
    -h 127.0.0.1 \
    -p 5432 \
    -U replicator \
    -D "${STANDBY1_DATA}" \
    -Fp -Xs -R \
    --slot=slot_standby_01

cat <<EOF >> "${STANDBY1_DATA}/postgresql.conf"
port = 5433
primary_conninfo = 'host=127.0.0.1 port=5432 user=replicator password=SecretKey123! application_name=standby_01'
primary_slot_name = 'slot_standby_01'
hot_standby = on
hot_standby_feedback = on
EOF

pg_ctl -D "${STANDBY1_DATA}" -l "${BASE_DIR}/standby1.log" start
echo "=== Standby 1 Node Sukses Dijalankan di Port 5433 ==="
```

#### Langkah 3: `hands-on/m02/scripts/03_setup_cascade_standby2.sh`
Clone dari Standby 1 (bukan Primary) untuk membuktikan arsitektur *Cascading Replication* di port 5434.

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(pwd)/hands-on/m02"
STANDBY2_DATA="${BASE_DIR}/data/standby2"

echo "=== [3/4] Setup Standby 2 (Cascading dari Standby 1) ==="
rm -rf "${STANDBY2_DATA}"
mkdir -p "${STANDBY2_DATA}"

# Dapatkan snapshot basebackup dari Standby 1
PGPASSWORD='SecretKey123!' pg_basebackup \
    -h 127.0.0.1 \
    -p 5433 \
    -U replicator \
    -D "${STANDBY2_DATA}" \
    -Fp -Xs -R

cat <<EOF >> "${STANDBY2_DATA}/postgresql.conf"
port = 5434
# Arahkan koneksi upstream BUKAN ke Primary 5432, melainkan ke Standby 1 di Port 5433!
primary_conninfo = 'host=127.0.0.1 port=5433 user=replicator password=SecretKey123! application_name=standby_02'
hot_standby = on
hot_standby_feedback = off
max_standby_streaming_delay = 30s
EOF

pg_ctl -D "${STANDBY2_DATA}" -l "${BASE_DIR}/standby2.log" start
echo "=== Standby 2 Node (Cascade) Sukses Dijalankan di Port 5434 ==="
```

#### Langkah 4: `hands-on/m02/scripts/04_simulate_failure_and_verify.sh`
Pengujian validasi sinkronisasi, cascade flow, dan pengujian durabilitas.

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== [4/4] Verifikasi Arsitektur Replikasi ==="

echo "1. Memeriksa status replikasi di Primary (Port 5432):"
psql -h 127.0.0.1 -p 5432 -U postgres -c "
SELECT application_name, state, sync_state, sync_priority 
FROM pg_stat_replication;"

echo "2. Memeriksa status upstream di Standby 1 (Port 5433):"
psql -h 127.0.0.1 -p 5433 -U postgres -c "
SELECT status, receive_start_lsn, latest_end_lsn 
FROM pg_stat_wal_receiver;"

echo "3. Melakukan Mutasi Transaksi di Primary:"
psql -h 127.0.0.1 -p 5432 -U postgres -c "
CREATE TABLE IF NOT EXISTS replication_audit (
    id serial primary key, 
    created_at timestamptz default now(), 
    payload text
);
INSERT INTO replication_audit(payload) VALUES ('Transaction Verified Multi-Tier');"

sleep 2

echo "4. Membaca Data di Standby 2 (Cascade Leaf Node di Port 5434):"
psql -h 127.0.0.1 -p 5434 -U postgres -c "SELECT * FROM replication_audit;"

echo "=== Validasi Sukses: Transaksi Terbaca di Leaf Node Cascading ==="
```

#### Langkah 5: `hands-on/m02/cleanup.sh`
Hentikan seluruh instance dan bersihkan disk.

```bash
#!/usr/bin/env bash
BASE_DIR="$(pwd)/hands-on/m02"

echo "Menghentikan seluruh node database..."
pg_ctl -D "${BASE_DIR}/data/standby2" stop -m immediate || true
pg_ctl -D "${BASE_DIR}/data/standby1" stop -m immediate || true
pg_ctl -D "${BASE_DIR}/data/primary" stop -m immediate || true

rm -rf "${BASE_DIR}/data" "${BASE_DIR}"/*.log
echo "Lab Environment dibersihkan."
```

---

### 13. Exercise

#### Level Easy
- **Tugas**: Hubungkan aplikasi ke Primary, lakukan query status pada `pg_stat_replication`. Ambil output kolom `sync_state`.
- **Target**: Membedakan status `async`, `sync`, dan `potential` ketika parameter `synchronous_standby_names = 'FIRST 1 (standby_01, standby_02)'` diterapkan.
- **Kriteria Evaluasi**: Menjelaskan alasan mengapa `standby_02` berstatus `potential`.

#### Level Medium
- **Tugas**: Simulasikan skenario *Query Cancellation Conflict*.
  1. Jalankan `SELECT pg_sleep(30);` di Standby Node pada tabel `users`.
  2. Secara bersamaan di Primary Node, jalankan perintah `VACUUM FULL users;` atau `TRUNCATE TABLE users;`.
- **Target**: Analisis error yang muncul di Standby log. 
- **Kriteria Evaluasi**: Buktikan error `ERROR: canceling statement due to conflict with recovery` muncul ketika `max_standby_streaming_delay` tercapai, dan mitigasi dengan parameter konfigurasi yang tepat.

#### Level Hard
- **Tugas**: Setup zero-downtime switchover secara manual tanpa bantuan orchestrator otomatis (seperti Patroni):
  1. Hentikan trafik write ke Primary.
  2. Pastikan `flush_lsn` Primary sama persis dengan `replay_lsn` Standby 1.
  3. Promosikan Standby 1 menjadi Primary baru (`pg_ctl promote`).
  4. Manfaatkan utilitas `pg_rewind` untuk merekonfigurasi mantan Primary lama agar dapat hidup kembali sebagai Standby baru yang menginduk ke Primary baru tanpa melakukan `pg_basebackup` ulang.
- **Kriteria Evaluasi**: Timeline LSN histori berhasil berpindah (*timeline switchover* tercatat di log) dan sinkronisasi dua arah sukses tanpa redownload direktori data.

---

### 14. Challenge

#### Skenario Kasus: Split-Brain Survival & Disaster Recovery di Multi-Cloud Fintech
Sebuah core payment gateway beroperasi di dua cloud provider: **AWS (Region Singapore)** sebagai Active Core, dan **GCP (Region Jakarta)** sebagai Disaster Recovery Site. 

```
  AWS (Singapore - Primary) ── WAN Latency 28ms ──► GCP (Jakarta - Cascaded DR)
```

**Kondisi Krisis Operasional**:
1. Terjadi degradasi rute kabel bawah laut inter-cloud yang menyebabkan latency lonjak dari 28ms menjadi 850ms, dengan packet loss 12%.
2. Primary di AWS tetap menerima trafik write intensif 8,000 TPS.
3. Node standby di GCP mengalami *lagging* hingga 180 GB dalam 20 menit.
4. Tim infrastructure AWS mengumumkan akan mematikan Availability Zone Primary di Singapura dalam waktu 15 menit ke depan karena insiden pendingin datacenter (Thermal Runway).

**Tantangan Arsitektur**:
Rancang strategi tertulis langkah demi langkah (Runbook Operasional Arsitek DBA) yang mencakup:
1. **Pencegahan Data Loss**: Bagaimana Anda meminimalkan atau mencapai RPO=0 pada situasi koneksi jaringan yang mengalami packet loss 12% dan latency tinggi? Apakah Anda akan memindahkan mode synchronous replication ke GCP di tengah krisis? Hitung konsekuensi latensi transaksi aplikasi di AWS jika mode synchronous dipaksakan.
2. **Mitigasi Disk Failure**: Bagaimana mencegah disk partisi `pg_wal` Primary di AWS tidak meledak (out of space) akibat slot replikasi DR GCP yang tertahan, tanpa memutus replikasi secara permanen?
3. **Graceful Failover Plan**: Urutan perintah exact CLI / query SQL untuk melakukan transisi promosi GCP menjadi Primary baru dengan data integrity validation, memastikan tidak ada phantom writes di node lama ketika koneksi inter-cloud pulih kembali (*Split-Brain Immunity*).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian A: Basic Knowledge
1. **Sub-proses apa di sisi PostgreSQL Standby yang bertugas menerima aliran WAL langsung dari soket TCP Primary?**
   - A. `walsender`
   - B. `startup process`
   - C. `walreceiver`
   - D. `checkpointer`

2. **Nilai konfigurasi `synchronous_commit` manakah yang menjamin transaksi hanya akan mengembalikan sukses jika data telah di-*replay* ke file data Standby?**
   - A. `on`
   - B. `remote_write`
   - C. `local`
   - D. `remote_apply`

3. **Apa fungsi utama dari utilitas `pg_create_physical_replication_slot`?**
   - A. Membuat partisi tabel baru khusus data replikasi.
   - B. Memastikan Primary tidak membuang berkas WAL yang belum dikonfirmasi oleh Standby.
   - C. Mempercepat bandwidth kartu antarmuka jaringan (NIC).
   - D. Melakukan enkripsi end-to-end pada aliran data WAL.

4. **Kapan Standby Node berhak membaca query transaksi (`SELECT`) dalam mode Hot Standby?**
   - A. Hanya jika parameter `hot_standby = on` aktif.
   - B. Kapan saja tanpa syarat.
   - C. Hanya jika node Primary dimatikan.
   - D. Jika koneksi diubah ke mode single-user mode.

5. **Di mana berkas mutasi LSN status terakhir disimpan di node Standby saat terjadi crash recovery?**
   - A. Di dalam file `pg_hba.conf`.
   - B. Di dalam *Control File* (`global/pg_control`).
   - C. Di dalam temporary cache RAM.
   - D. Di dalam direktori `base/1/`.

---

#### Bagian B: Intermediate Conceptual
6. **Apa dampak langsung terhadap node Primary jika parameter `hot_standby_feedback = on` diaktifkan pada Read Replica yang mengeksekusi analytical reporting query berdurasi 5 jam?**
   - A. Standby node akan mengalami crash kehabisan RAM.
   - B. Primary akan menolak transaksi commit baru.
   - C. AutoVacuum di Primary dicegah membersihkan dead tuples pada baris data yang dibaca Standby, memicu Table Bloat masif di Primary.
   - D. Primary otomatis menurunkan replikasi menjadi mode asinkron.

7. **Diberikan konfigurasi: `synchronous_standby_names = 'ANY 2 (st_a, st_b, st_c)'`. Apa yang terjadi jika node `st_b` dan `st_c` mengalami crash bersamaan?**
   - A. Transaksi mutasi di Primary tetap berjalan lancar karena `st_a` masih aktif.
   - B. Transaksi mutasi (`COMMIT`) di Primary akan *hang* (tertahan di SyncRepQueue) menunggu minimal satu standby tambahan pulih.
   - C. Primary otomatis mengubah modenya menjadi read-only.
   - D. Primary membatalkan transaksi yang sedang berjalan (*Rollback* otomatis).

8. **Mengapa *Cascading Replication* sangat disarankan pada skenario di mana perusahaan memiliki lebih dari 10 Read Replica yang tersebar di multi-region?**
   - A. Mengurangi beban duplikasi enkripsi SSL pada node Primary.
   - B. Menghilangkan kebutuhan berkas WAL di leaf standby nodes.
   - C. Menghindari CPU dan Network I/O Saturation pada Primary Node karena Primary cukup mentransmisikan WAL ke 1 atau 2 intermediary node.
   - D. Mengubah engine PostgreSQL menjadi database bertipe multi-master.

9. **Parameter safety net modern apa yang wajib dikonfigurasi guna mencegah physical replication slot memakan disk space `pg_wal` tanpa batas jika standby mati total?**
   - A. `wal_keep_size`
   - B. `max_slot_wal_keep_size`
   - C. `checkpoint_completion_target`
   - D. `archive_timeout`

10. **Apa perbedaan teknis mendasar antara `write_lsn` dan `flush_lsn` pada output view `pg_stat_replication`?**
    - A. `write_lsn` berada di disk storage; `flush_lsn` berada di kartu memori server.
    - B. `write_lsn` berarti data sudah ditulis ke OS page cache Standby; `flush_lsn` berarti data telah dipaksa persisten ke storage Standby melalui instruksi `fsync`.
    - C. `write_lsn` adalah data transaksi yang di-rollback; `flush_lsn` adalah data commit.
    - D. Keduanya memiliki fungsi yang identik tanpa ada perbedaan teknis.

---

#### Bagian C: Production Scenarios & Troubleshooting
11. **Skenario Kasus 1**:
    Sebuah aplikasi *flash sale* e-commerce menggunakan konfigurasi `synchronous_commit = on`. Saat flash sale dimulai, transaksi drop drastis dari 10,000 TPS menjadi 800 TPS. Tidak ada CPU bottleneck atau lock contention di database Primary. Setelah diperiksa via `pg_stat_activity`, 90% backend thread berada pada event wait: `SyncRep`.
    
    *Pertanyaan*: Apa analisa akar masalah Anda dan tindakan mitigasi darurat tercepat tanpa mengorbankan durabilitas node Primary?

12. **Skenario Kasus 2**:
    Tim DBA memantau bahwa volume disk `/var/lib/postgresql/data/pg_wal` pada Primary naik drastis menyisakan sisa 5% disk free space. Query ke `pg_replication_slots` menunjukkan ada 1 slot tidak aktif bernama `debezium_cdc_slot` dengan nilai `retained_bytes` mencapai 450 GB. 
    
    *Pertanyaan*: Jelaskan dampak jika Anda langsung mengeksekusi `pg_drop_replication_slot()` terhadap downstream consumer (aplikasi CDC/Standby) dan langkah mitigasi pembersihan berkas WAL darurat setelah slot di-drop!

13. **Skenario Kasus 3**:
    Standby Node Anda sering mengalami *lagging* signifikan pada jam sibuk. Hasil inspeksi menunjukkan CPU Standby berada pada utilisasi 100% pada satu core tunggal yang menjalankan *Startup Process*, sementara ratusan client sedang mengeksekusi analytical read query di Standby tersebut.
    
    *Pertanyaan*: Mengapa proses replikasi Standby (Startup Process) mengalami perlambatan saat menerapkan WAL records, dan strategi konfigurasi apa yang dapat Anda terapkan pada arsitektur transaksi di Primary maupun Standby untuk menyelesaikannya?

---

### Kunci Jawaban Quiz

#### Bagian A & B
1. **C** (`walreceiver`)
2. **D** (`remote_apply`)
3. **B** (Memastikan Primary tidak mendaur ulang berkas WAL sebelum di-acknowledge Standby)
4. **A** (`hot_standby = on`)
5. **B** (Control File: `global/pg_control`)
6. **C** (Table Bloat masif akibat terhalangnya pembersihan dead tuples oleh VACUUM)
7. **B** (Commit Primary *hang* karena konfigurasi mewajibkan kuorum 2 node: ANY 2)
8. **C** (Menghindari CPU & Network I/O Saturation pada Primary Node)
9. **B** (`max_slot_wal_keep_size`)
10. **B** (`write_lsn` di level OS kernel buffer, `flush_lsn` persisten fisik via fsync)

#### Bagian C (Pedoman Penilaian Arsitektural)
11. **Analisa Skenario 1**:
    - **Akar Masalah**: Latensi round-trip jaringan (RTT) antara Primary dan Standby node atau bottleneck I/O `fsync` disk di sisi Standby Node. Pada `synchronous_commit = on`, throughput mutasi Primary terikat (*network/disk latency bound*) oleh performa Standby.
    - **Mitigasi Cepat**: Ubah transaksi non-finansial menjadi `synchronous_commit = local` di level session atau user (`ALTER USER app_non_critical SET synchronous_commit = local;`), atau pindahkan quorum menjadi konfigurasi dengan standby yang memiliki network latency paling rendah.
12. **Analisa Skenario 2**:
    - **Dampak Downstream**: Aplikasi CDC (Debezium) akan putus permanen dan melempar error fatal karena posisi LSN bacaannya hilang. Jika dihidupkan kembali, CDC harus melakukan full-table snapshot ulang dari nol.
    - **Mitigasi**: Eksekusi `SELECT pg_drop_replication_slot('debezium_cdc_slot');`. Segera trigger `CHECKPOINT;` di Primary secara manual agar checkpoint process mengevaluasi ulang sisa kebutuhan LSN dan secara agresif merotasi serta menghapus segmen WAL yang basi di direktori `pg_wal`.
13. **Analisa Skenario 3**:
    - **Akar Masalah**: *Startup Process* pada PostgreSQL bersifat single-threaded dalam menerapkan WAL redo logs. Jika transaksi di Primary melakukan modifikasi halaman data masif (seperti batch update ratusan ribu baris) atau terbentur lock snapshot oleh analytical query di standby, single-thread ini menjadi bottleneck.
    - **Mitigasi**: Pecah transaksi batch besar di Primary menjadi batch-batch kecil (misal: 1,000 baris per commit). Pisahkan Standby untuk pelaporan analitik berat dari Standby yang ditujukan untuk High-Availability Failover. Pastikan I/O disk subsystem Standby (IOPS) setara dengan node Primary.

---

### 16. Summary

Implementasi *PostgreSQL Physical Streaming Replication* tingkat produksi menuntut keseimbangan antara durabilitas data, reliabilitas ketersediaan sistem, dan overhead performa aplikasi.

```
       Write Latency  ◄─────────────────────────────►  Durability & Isolation
  (sync_commit = off)                                 (sync_commit = remote_apply)
  High Throughput                                     Zero Data Loss (RPO=0)
  Risk: Data Loss on Crash                            Latency Overhead: Network + Redo
```

Poin-poin arsitektur utama yang harus dikuasai oleh Lead PostgreSQL DBA:
1. **LSN Stream Pipeline**: Transaksi berpindah dari `WAL Buffers` Primary $\rightarrow$ `pg_wal` Storage $\rightarrow$ `walsender` $\rightarrow$ Jaringan TCP $\rightarrow$ `walreceiver` $\rightarrow$ OS Cache Standby (`write_lsn`) $\rightarrow$ Disk Standby (`flush_lsn`) $\rightarrow$ Startup Process Replay (`replay_lsn`).
2. **Quorum Synchronous Architecture**: Desain zero-data-loss modern wajib mengimplementasikan pola quorum (contoh: `ANY 1 (node_a, node_b)`) daripada pola sekuensial absolut (`FIRST 1`) guna memitigasi risiko cluster write-lock total saat satu replica mengalami kegagalan.
3. **Cascading Strategy**: Beban replikasi untuk analitik, backup (`pg_dump`/`pgbackrest`), dan read-pool multi-region harus didelegasikan menggunakan *Cascading Replication* agar resource compute dan network Primary terfokus melayani write workload.
4. **Proteksi Storage Slot Mutlak**: Jangan pernah mengaktifkan *Physical Replication Slots* di lingkungan produksi tanpa menyertakan pengaman batas atas `max_slot_wal_keep_size`. Ketiadaan parameter ini adalah penyebab nomor satu insiden out-of-disk failure pada arsitektur basis data PostgreSQL global.