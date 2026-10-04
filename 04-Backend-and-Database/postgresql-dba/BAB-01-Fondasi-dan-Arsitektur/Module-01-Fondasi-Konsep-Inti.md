# Module 01: Arsitektur Proses, Memori, dan Penyimpanan PostgreSQL

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi dan memetakan interaksi antara *Postmaster process*, *Backend processes*, dan *Background worker processes*.
- Menganalisis alokasi dan struktur memori PostgreSQL, memisahkan peruntukan *Shared Memory* dan *Local Memory (Backend Private Memory)*.
- Mengkalkulasi formula batas aman konsumsi memori untuk mencegah insiden *Out-Of-Memory* (OOM) Killer pada tingkat sistem operasi.
- Menjelaskan siklus hidup mutasi data (dirty buffers) dari memori ke *Write-Ahead Log* (WAL) dan *Data Files*.
- Mendiagnosis status kesehatan arsitektur instans database menggunakan instrospeksi internal PostgreSQL (`pg_stat_*`) dan utilitas OS Linux.

---

### 2. Core Concept
PostgreSQL mengadopsi model **Client-Server Process-based Architecture** (bukan *thread-based* seperti MySQL atau Microsoft SQL Server). Setiap koneksi klien yang disetujui akan diisolasi ke dalam satu proses sistem operasi independen yang disebut **Backend Process** (atau `postgres worker`). 

Komunikasi antarproses (*Inter-Process Communication* / IPC) dan sinkronisasi status cluster dilakukan melalui segmen memori terpusat yang disebut **Shared Memory Area**. PostgreSQL mengandalkan kolaborasi erat antara arsitektur memorinya dan subsistem I/O kernel Linux (terutama *Linux Page Cache*) untuk mencapai konkurensi tinggi, integritas data transaksional (ACID), dan efisiensi baca/tulis tanpa menerapkan abstraksi *direct I/O* penuh secara mandiri.

---

### 3. Why It Matters
Bagi seorang Database Administrator (DBA), memahami arsitektur internal PostgreSQL bukan sekadar wawasan teoritis, melainkan landasan mitigasi risiko produksi:
- **Pencegahan OOM Killer:** Jika alokasi *Local Memory* (seperti `work_mem`) tidak dibatasi dengan memperhitungkan `max_connections`, lonjakan beban kerja (*spikes*) konkurensi tinggi akan memicu Linux OOM Killer untuk menembak proses *Postmaster*, meruntuhkan seluruh instance secara mendadak.
- **Penyetelan I/O & Checkpoint:** Mengetahui cara kerja *Checkpointer* dan *Background Writer* mencegah fenomena *I/O spikes* yang melumpuhkan latensi transaksi pada aplikasi berskala besar.
- **Efisiensi Sumber Daya:** Memahami mekanisme *Double Buffering* (PostgreSQL Shared Buffers + Linux Page Cache) mencegah pemborosan alokasi RAM yang berlebihan dan degradasi *cache hit ratio*.

---

### 4. What: Komponen Arsitektur Utama

Arsitektur PostgreSQL terbagi menjadi 3 pilar: **Processes**, **Memory**, dan **Disk Storage**.

```
+---------------------------------------------------------------------------------------+
|                                    POSTGRESQL INSTANCE                                |
|                                                                                       |
|  +------------------------- SHARED MEMORY -----------------------------------------+  |
|  | +--------------------+ +--------------------+ +-------------------------------+ |  |
|  | |   Shared Buffers   | |     WAL Buffers    | |       Lock / Predicate /      | |  |
|  | |   (Data/Index)     | |                    | |     ProcArray Data Structures | |  |
|  | +--------------------+ +--------------------+ +-------------------------------+ |  |
|  +---------------------------------------------------------------------------------+  |
|          ^                        ^                                   ^               |
|          |                        |                                   |               |
|  +-------v------------------------v-----------------------------------v------------+  |
|  | BACKGROUND PROCESSES                                                            |  |
|  | [Checkpointer]   [BGWriter]   [WAL Writer]   [Autovacuum Launcher]   [Archiver] |  |
|  +---------------------------------------------------------------------------------+  |
|                                                                                       |
|  +-- POSTMASTER (PID 1 of PG) -----------------------------------------------------+  |
|  |   Mendengarkan port, fork backend, menangani crash recovery cluster             |  |
|  +---------------------------------------------------------------------------------+  |
|          | forks                                                                      |
|          v                                                                            |
|  +-- BACKEND PROCESSES (Per Client Connection) ------------------------------------+  |
|  | Backend Process 1               Backend Process 2                               |  |
|  | +-- LOCAL MEMORY ------------+  +-- LOCAL MEMORY ------------+                  |  |
|  | | work_mem                   |  | work_mem                   |                  |  |
|  | | maintenance_work_mem       |  | maintenance_work_mem       |                  |  |
|  | | temp_buffers               |  | temp_buffers               |                  |  |
|  | +----------------------------+  +----------------------------+                  |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                      I/O Sycalls
                                           |
+------------------------------------------v--------------------------------------------+
| LINUX OS LEVEL                                                                        |
| +-----------------------------------------------------------------------------------+ |
| |                                 Page Cache                                        | |
| +-----------------------------------------------------------------------------------+ |
|                                          | fsync()                                    |
| +----------------------------------------v------------------------------------------+ |
| | PHYSICAL DISK STORAGE                                                             | |
| |  base/ (Tables/Indexes)   pg_wal/ (WAL Segments)   global/ (System Catalogs)       | |
| +-----------------------------------------------------------------------------------+ |
+---------------------------------------------------------------------------------------+
```

#### A. Komponen Proses (Processes)
1. **Postmaster (Postgres Supervisor):** Proses root yang pertama kali berjalan. Bertugas mengalokasikan *shared memory*, meluncurkan *background processes*, mendengarkan port jaringan (`5432`), memverifikasi otentikasi koneksi baru, dan melakukan fungsi `fork()` untuk membuat backend process baru per sesi.
2. **Backend Process:** Melayani query dari satu sesi klien tertentu. Bertanggung jawab memparsing, merencanakan (*parse, rewrite, plan*), dan mengeksekusi query.
3. **Checkpointer:** Secara berkala melakukan *flush* (mengeluarkan dan menulis) seluruh *dirty pages* dari `shared_buffers` ke disk, lalu menandai posisi aman tersebut di WAL checkpoint record.
4. **Background Writer (bgwriter):** Bekerja secara terus-menerus dalam skala kecil untuk mencicil penulisan *dirty pages* ke disk secara asinkron agar *Backend Process* tidak kehabisan *clean buffers* saat memerlukan blok memori baru.
5. **WAL Writer:** Menulis data dari buffer WAL (`WAL Buffers`) ke storage fisik secara berkala, meminimalkan latensi pemanggilan `fsync` saat transaksi commit.
6. **Autovacuum Launcher & Workers:** Mengotomatiskan proses pembersihan *dead tuples* (akibat UPDATE/DELETE MVCC) dan memperbarui metadata statistik tabel guna mencegah *table bloat* dan menjaga akurasi Query Planner.
7. **Stats Collector:** Mengumpulkan metrik operasional (jumlah akses tabel, scan indeks, I/O blok) yang kemudian ditampilkan pada *system views* (`pg_stat_*`).

#### B. Komponen Memori (Memory Structures)
1. **Shared Memory Area (Dikonfigurasi statis saat startup):**
   - **Shared Buffers:** Cache internal PostgreSQL untuk halaman tabel dan indeks (default blok ukuran 8KB).
   - **WAL Buffers:** Buffer sirkular untuk menampung perubahan transaksi sebelum disinkronkan ke file WAL di storage.
   - **Lock Space:** Tabel hash internal yang menyimpan informasi *heavyweight locks*, *lightweight locks (LWLocks)*, dan status sinkronisasi transaksi (`pg_xact`).
2. **Local Memory (Dialokasikan dinamis per Backend Process):**
   - **work_mem:** Memori yang dialokasikan untuk operasi komputasi data: sorting (`ORDER BY`), hash-join, merge-join, dan agregasi hash. **Catatan penting:** Satu query kompleks dapat mengalokasikan beberapa slot `work_mem` secara paralel.
   - **maintenance_work_mem:** Memori untuk operasi DDL dan pemeliharaan besar, seperti `VACUUM`, `CREATE INDEX`, dan penambahan *foreign key*.
   - **temp_buffers:** Buffer khusus untuk menampung tabel sementara (*temporary tables*) lokal per sesi.

---

### 5. How: Alur Kerja Mutasi Data (Lifecycle of a Write)
Bagaimana komponen-komponen ini berinteraksi saat sebuah mutasi data (`INSERT`/`UPDATE`/`DELETE`) terjadi:

1. **Client Execution:** Klien mengirimkan kueri `UPDATE data SET balance = balance - 100 WHERE id = 1;`.
2. **Backend Processing:** Backend Process memeriksa `shared_buffers` untuk mencari halaman (Page 8KB) yang memuat baris data bersangkutan.
   - Jika *Cache Miss*: Halaman dibaca dari OS disk/Page Cache ke dalam `shared_buffers`.
3. **WAL Logging (Write-Ahead):** Sebelum halaman data di memori dimodifikasi, backend menulis catatan perubahan ke `wal_buffers`. PostgreSQL menerapkan aturan mutlak: **WAL harus ditulis ke disk sebelum dirty page bersangkutan diperbolehkan menyentuh storage fisik.**
4. **Buffer Mutation:** Halaman di `shared_buffers` diubah di level memori dan statusnya ditandai sebagai **Dirty Page**.
5. **Commit & Sync:** Klien mengirim `COMMIT`. WAL Writer / Backend memaksa catatan WAL pada `wal_buffers` masuk ke file disk fisik via `fsync()`. Status transaksi sukses dikembalikan ke klien, meskipun *dirty data page* belum ditulis ke file tabel utama.
6. **Flushing to Disk:** Melalui mekanisme Checkpoint atau Background Writer, *dirty page* yang ada di `shared_buffers` didorong ke Linux Page Cache, lalu disinkronkan ke file tabel di direktori `base/` via `fsync()`.

---

### 6. Architecture Diagram: Siklus Aliran Data & Memori

```
 [CLIENT]
    | 
 1. | SQL Update Query
    v
+-------------------------------------------------------------------------------------+
| [BACKEND PROCESS]                                                                  |
|   | 2. Cari / Tarik halaman ke memory                                              |
|   v                                                                                 |
| +------------------------- SHARED MEMORY -----------------------------------------+ |
| |                                                                                 | |
| |      +------------------------+                +-------------------------+      | |
| |  3.  |      WAL Buffers       |            4.  |     Shared Buffers      |      | |
| | +--->| [Tulis delta WAL log]  |                | [Ubah jadi Dirty Page]  |<--+  | |
| | |    +------------------------+                +-------------------------+   |  | |
| | |                 |                                         |                |  | |
| +-|-----------------|-----------------------------------------|----------------|--+ |
|   |                 |                                         |                |    |
|   | 5. COMMIT       | 5b. fsync WAL                           | 6. Checkpoint/ |    |
|   |    Sync         v                                         |    BGWriter    |    |
|   +-----------+ pg_wal/                                       v    Flush       |    |
|               | (Disk)                                   OS Page Cache         |    |
|                                                               |                |    |
|                                                               v fsync          |    |
|                                                          base/<db_id>/<rel_id> |    |
|                                                          (Data File on Disk)   |    |
+-------------------------------------------------------------------------------------+
```

---

### 7. Simple Example: Inspeksi Proses dan Memori dari Shell & SQL

Verifikasi proses OS yang sedang berjalan untuk cluster PostgreSQL:

```bash
# Menampilkan tree process Postmaster dan seluruh background workers
ps -ef --forest | grep postgres
```
*Output Tipikal:*
```text
postgres  12401      1  0 08:00 ?  00:00:01 /usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main
postgres  12403  12401  0 08:00 ?  00:00:00  \_ postgres: checkpointer 
postgres  12404  12401  0 08:00 ?  00:00:00  \_ postgres: background writer 
postgres  12405  12401  0 08:00 ?  00:00:00  \_ postgres: walwriter 
postgres  12406  12401  0 08:00 ?  00:00:00  \_ postgres: autovacuum launcher 
postgres  12407  12401  0 08:00 ?  00:00:00  \_ postgres: logical replication launcher 
postgres  12550  12401  0 08:15 ?  00:00:00  \_ postgres: app_user production_db 10.0.1.50(44321) idle
```

Kueri konfigurasi memori saat ini melalui terminal `psql`:

```sql
SELECT name, setting, unit, context 
FROM pg_settings 
WHERE name IN ('shared_buffers', 'work_mem', 'maintenance_work_mem', 'max_connections');
```
*Output Tipikal:*
```text
          name          | setting | unit |  context   
------------------------+---------+------+------------
 maintenance_work_mem   | 65536   | kB   | user
 max_connections        | 100     |      | postmaster
 shared_buffers         | 16384   | 8kB  | postmaster
 work_mem               | 4096    | kB   | user
(4 rows)
```
*Catatan:* `context = postmaster` menandakan perubahan parameter ini membutuhkan *restart* layanan total, sedangkan `user` dapat diubah pada level sesi secara dinamis.

---

### 8. Practical Production Example: Formula & Script Sizing Memori PostgreSQL

Sebuah server database bare-metal memiliki spesifikasi:
- **Total RAM:** 64 GB
- **Beban Kerja:** OLTP Campuran
- **Target max_connections:** 200 koneksi langsung

#### Script Perhitungan dan Konfigurasi Baseline (`setup_memory.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Definisi Parameter Berdasarkan Kapasitas Fisik Server
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_RAM_MB=$((TOTAL_RAM_KB / 1024))
TOTAL_RAM_GB=$((TOTAL_RAM_MB / 1024))

echo "Total Terdeteksi Sistem RAM: ${TOTAL_RAM_GB} GB"

# Aturan umum OLTP: 
# shared_buffers = 25% dari Total RAM
# effective_cache_size = 75% dari Total RAM
SHARED_BUFFERS="$((TOTAL_RAM_MB / 4))MB"
EFFECTIVE_CACHE_SIZE="$(( (TOTAL_RAM_MB * 3) / 4 ))MB"
MAINTENANCE_WORK_MEM="2048MB"

# Alokasi batas aman work_mem:
# Asumsi: Max 200 koneksi, rata-rata 2 operasi sort/hash aktif paralel per koneksi.
# Formula Sederhana: (Total RAM - Shared Buffers) * 0.5 / (max_connections * 2)
# = (64GB - 16GB) * 0.5 / (200 * 2) = 24GB / 400 = ~60MB
WORK_MEM="64MB"

cat <<EOF > /etc/postgresql/16/main/conf.d/01_memory.conf
# --- Konfigurasi Memori Teroptimasi ---
shared_buffers = ${SHARED_BUFFERS}
effective_cache_size = ${EFFECTIVE_CACHE_SIZE}
work_mem = ${WORK_MEM}
maintenance_work_mem = ${MAINTENANCE_WORK_MEM}
max_connections = 200

# Konfigurasi Huge Pages untuk proteksi Page Table overhead pada buffer besar
huge_pages = try
EOF

echo "Konfigurasi berhasil disimpan di /etc/postgresql/16/main/conf.d/01_memory.conf"
```

---

### 9. Trade-offs & Alternatives

| Desain Arsitektur | Keunggulan | Kekurangan / Trade-off |
| :--- | :--- | :--- |
| **Process-based (PostgreSQL)** | Isolasi memori sempurna. Jika satu backend *crash* akibat memory corruption atau segmentation fault, proses backend lain tidak terganggu dan sistem operasi dapat membersihkan *dangling resources* secara otomatis. | *Overhead* pembuatan proses relatif mahal (membutuhkan implementasi Connection Pooler eksternal seperti PgBouncer) dan konsumsi memori per koneksi lebih tinggi dibanding thread. |
| **Thread-based (MySQL InnoDB, MS SQL)** | Pembuatan dan terminasi koneksi sangat ringan. Komunikasi thread menggunakan memori lokal yang sama tanpa kompleksitas segmen IPC OS tingkat rendah. | Satu thread mengalami crash pada tingkat unhandled memory exception berpotensi meruntuhkan (*segmentation fault*) seluruh proses database secara serentak. |
| **Tinggi Shared Buffers (>40% RAM)** | Data tables tersimpan secara internal di memori PostgreSQL, mengurangi frekuensi *system calls* baca ke kernel Linux. | Mengurangi alokasi *Linux Page Cache*. Mengakibatkan fenomena *Double Buffering* yang tidak efisien dan memperlambat proses *checkpoint write-back*. |

---

### 10. Best Practices
1. **Penerapan Connection Pooler:** Jangan pernah mengekspos PostgreSQL langsung ke ratusan klien dinamis tanpa perantara *Connection Pooler* (misalnya PgBouncer atau pgcat) dalam mode *transaction pooling*.
2. **Kendalikan `shared_buffers`:** Untuk server Linux, alokasikan `shared_buffers` antara 25% hingga maksimal 40% dari total RAM fisik. Biarkan sisa kapasitas RAM digunakan oleh Linux Kernel sebagai *Page Cache*.
3. **Konfigurasi Linux Memory Subsystem:** Set `vm.overcommit_memory = 2` dan kalibrasi `vm.overcommit_ratio` pada skenario beban tinggi untuk memastikan kernel Linux tidak secara agresif mengizinkan overcommit yang memicu OOM Killer.
4. **Aktifkan Linux Huge Pages:** Saat alokasi `shared_buffers` melebihi 16 GB, aktifkan konfigurasi `vm.nr_hugepages` di tingkat Linux dan `huge_pages = on` di PostgreSQL untuk meminimalkan beban Translation Lookaside Buffer (TLB).

---

### 11. Edge Cases & Failure Modes

#### Kegagalan: OOM Killer Membunuh Postmaster Process
- **Mekanisme Insiden:** PostgreSQL Backend meminta memori lokal melampaui sisa RAM fisik bebas. Sistem Operasi Linux mendeteksi kondisi ketiadaan memori (`Out of Memory`) dan mengeksekusi OOM Killer.
- **Dampak Kritis:** OOM Killer memilih terminasi salah satu proses Postgres (Backend atau Postmaster). Jika Backend dibunuh mendadak saat memegang referensi ke *shared memory lock*, **Postmaster akan mematikan seluruh instans database seketika**, memutuskan semua koneksi aktif, lalu memulai siklus *Crash Recovery* (memutar ulang catatan WAL) secara otomatis sebelum sistem siap dibuka kembali.
- **Solusi Pencegahan:** Kalibrasi batas `work_mem` serendah mungkin secara global, lalu atur pengecualian skala tinggi hanya secara lokal pada kueri batch tertentu via:
  ```sql
  SET LOCAL work_mem = '1GB';
  ANALYZE verbose;
  ```

---

### 12. Verification & Testing

Cara memverifikasi apakah kueri Anda meluap (*spill*) dari alokasi memori kerja ke penyimpanan disk:

```sql
-- 1. Buat tabel uji data
CREATE TABLE IF NOT EXISTS test_mem AS 
SELECT generate_series(1, 500000) AS id, md5(random()::text) AS payload;

-- 2. Turunkan work_mem hanya untuk sesi ini
SET work_mem = '1MB';

-- 3. Eksekusi analisis eksekusi dengan informasi Buffer dan IO
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM test_mem ORDER BY payload;
```

**Analisis Output:**
```text
Sort  (cost=65148.85..66398.85 rows=500000 width=37) (actual time=235.122..289.431 rows=500000 loops=1)
  Sort Key: payload
  Sort Method: external merge  Disk: 24784kB    <--- SPILLED TO DISK!
  Buffers: shared hit=4215, temp read=3102 written=3105
...
```
*Interpretasi:* `Sort Method: external merge  Disk: 24784kB` mengonfirmasi bahwa alokasi `work_mem = 1MB` tidak memadai. PostgreSQL terpaksa menulis berkas komputasi sementara (*temporary sort files*) ke disk, yang menurunkan performa eksekusi query hingga beberapa kali lipat.

---

### 13. Anti-Patterns

#### 1. Menentukan `max_connections = 5000` untuk Menghindari Eror Koneksi
*Alasan Salah:* Administrator beranggapan menaikkan parameter ini menyelesaikan kendala `FATAL: sorry, too many clients already`.
*Konsekuensi Nyata:* PostgreSQL mengalokasikan array struktur proses dan lock tabel di memori bersama berdasarkan `max_connections`. 5.000 backend process akan berebut siklus CPU via *context switching*, memicu *cache thrashing*, dan mempercepat terjadinya tabrakan saturasi RAM.
*Solusi:* Batasi `max_connections` (misal 100-300) dan terapkan PgBouncer di layer arsitektur depan.

#### 2. Menyamakan Ukuran `shared_buffers` dengan 80% RAM (Standar Konfigurasi Database Lain)
*Alasan Salah:* Meniru parameter sizing sistem basis data lain yang menggunakan I/O bypass langsung.
*Konsekuensi Nyata:* PostgreSQL sangat bergantung pada *Linux Page Cache* untuk melakukan operasi *checkpoint writing* dan sinkronisasi blok data. `shared_buffers` yang terlalu masif mengakibatkan data tersimpan ganda (*Double Buffering*) dan menimbulkan jeda *freeze* I/O panjang saat checkpoint terjadi.

---

### 14. Production Failure Scenario (Post-Mortem)

#### Ringkasan Kasus
- **Waktu Insiden:** Pukul 02.15 WIB.
- **Severity:** P1 (Cluster Production Down).
- **Gejala:** Seluruh koneksi ke master database terputus seketika. Log aplikasi menunjukkan pesan: `FATAL: the database system is in recovery mode`.

#### Timeline & Investigasi
1. **02:14:50** - Kueri batch pelaporan bulanan dijalankan via aplikasi internal oleh 8 worker paralel.
2. **02:15:02** - Linux `dmesg` mencatat:
   ```text
   Out of memory: Kill process 23412 (postgres) score 851 or sacrifice child
   Killed process 23412 (postgres) total-vm:4231456kB, anon-rss:2134500kB
   ```
3. **02:15:03** - Postmaster mendeteksi hilangnya PID backend process 23412 tanpa sinyal terminasi standar:
   ```text
   LOG: server process (PID 23412) was terminated by signal 9: Killed
   LOG: terminating any other active server processes
   WARNING: terminating connection because of crash of another server process
   ```
4. **02:15:05** - Postmaster mengunci akses klien dan memulai *WAL redo recovery* untuk mengembalikan konsistensi shared memory yang terkorupsi akibat terminasi paksa.
5. **02:19:30** - Sistem selesai melakukan *WAL replay* dan kembali berstatus `ready to accept connections`. Total *downtime*: 4 menit 27 detik.

#### Root Cause
Parameter `work_mem` sebelumnya diubah secara global pada `postgresql.conf` menjadi `512MB`. Kueri analitik pelaporan mengeksekusi 6 operasi *Sort* dan *Hash Join* paralel per proses, menyerap alokasi memori:
$$\text{Konsumsi} = 8 \text{ proses} \times 6 \text{ operator} \times 512\text{ MB} \approx 24\text{ GB}$$
Hal ini seketika menguras sisa kapasitas memori server dan memicu OOM Killer pada sistem operasi.

#### Tindakan Remediasi
1. Menurunkan nilai global `work_mem` kembali ke `16MB`.
2. Menerapkan skrip `set_local_work_mem` hanya pada sesi kueri pelaporan analitik.
3. Melakukan proteksi nilai `oom_score_adj` untuk proses Postmaster:
   ```bash
   echo -1000 > /proc/$(head -1 /var/lib/postgresql/16/main/postmaster.pid)/oom_score_adj
   ```

---

### 15. Security Considerations
1. **Proteksi Izin File Direktori Data (`$PGDATA`):** File fisik PostgreSQL berisi data transaksi mentah (*raw data blocks*). Pastikan sistem operasi membatasi perizinan folder cluster secara ketat ke level `0700` (`drwx------`) dengan kepemilikan mutlak user `postgres`.
2. **Shared Memory Segment Security:** Di lingkungan sistem operasi bertingkat (*multi-tenant*), cegah *unprivileged users* mengakses segmen POSIX Shared Memory yang digunakan PostgreSQL dengan mengunci akses ke `/dev/shm`.
3. **Injeksi Shared Preload Libraries:** Parameter `shared_preload_libraries` mengeksekusi *binary objects* C ke ruang memori PostgreSQL saat start. Pastikan hak akses berkas `postgresql.conf` bersifat *read-only* bagi selain superuser untuk mencegah injeksi pustaka C berbahaya.

---

### 16. Maintenance & Monitoring

Metrik penting arsitektur memori dan proses yang wajib dipantau:

#### Cache Hit Ratio (Ideal > 99% untuk sistem OLTP)
```sql
SELECT 
  sum(heap_blks_read) as heap_read,
  sum(heap_blks_hit)  as heap_hit,
  (sum(heap_blks_hit)::float / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100)::numeric(5,2) as cache_hit_ratio
FROM pg_statio_user_tables;
```

#### Pemantauan Checkpoint & Tekanan Background Writer
```sql
SELECT 
  checkpoints_timed, 
  checkpoints_req, 
  checkpoint_write_time, 
  checkpoint_sync_time,
  buffers_checkpoint,
  buffers_clean,
  buffers_backend
FROM pg_stat_bgwriter;
```
*Evaluasi DBA:* Jika `checkpoints_req` (checkpoint paksa akibat WAL penuh) lebih tinggi dibanding `checkpoints_timed` (checkpoint berkala terjadwal), tingkatkan parameter `max_wal_size` untuk meredam lonjakan I/O sistem.

---

### 17. Performance Tuning Guide: Parameter Kunci

1. **`shared_buffers`:**
   - Rekomendasi: `0.25 * Total RAM` (untuk RAM server $\le 64\text{ GB}$).
   - Catatan: Menetapkan nilai di atas 40% RAM jarang memberikan peningkatan signifikan akibat mekanisme pembacaan ganda OS Cache.
2. **`work_mem`:**
   - Rekomendasi Awal: Antara `16MB` - `64MB`.
   - Formula Konservatif:
     $$\text{work\_mem} \le \frac{\text{Total RAM} - \text{shared\_buffers}}{\text{max\_connections} \times 2}$$
3. **`maintenance_work_mem`:**
   - Rekomendasi: `1GB` hingga `2GB` pada server produksi dengan RAM besar.
   - Fungsi: Mempercepat penyelesaian indeks saat migrasi skema dan eksekusi autovacuum.
4. **`wal_buffers`:**
   - Rekomendasi: Set ke `-1` (otomatis disetel PostgreSQL sebesar 1/32 dari `shared_buffers`, maksimal `16MB`), yang umumnya optimal untuk mayoritas beban kerja OLTP.

---

### 18. Hands-On Exercises

#### Lab 1: Profiling Konsumsi Memori Kueri
1. Buka sesi kueri menggunakan `psql`.
2. Jalankan perintah `EXPLAIN ANALYZE` terhadap tabel besar menggunakan variasi `work_mem` dari `64kB` hingga `64MB`.
3. Catat titik di mana *Sort Method* beralih dari `external merge Disk` menjadi `quicksort Memory`.

#### Lab 2: Observasi Sinyal Crash Recovery
1. Buat cluster uji lokal (non-produksi).
2. Temukan PID dari Checkpointer process menggunakan query:
   ```sql
   SELECT pid, backend_type FROM pg_stat_activity WHERE backend_type = 'checkpointer';
   ```
3. Eksekusi `kill -9 <PID>` pada shell terminal.
4. Periksa berkas log PostgreSQL (`log/postgresql-*.log`) untuk mengamati bagaimana Postmaster mendeteksi kegagalan tersebut dan merestart seluruh proses backend demi menjaga integritas memori.

---

### 19. Frequently Asked Questions (FAQ)

**Q: Mengapa PostgreSQL tidak mengalokasikan 80% RAM untuk `shared_buffers` seperti database Oracle atau SQL Server?**  
*A:* PostgreSQL tidak menggunakan *Direct I/O* (O_DIRECT) secara default. PostgreSQL menulis data ke *Linux Page Cache* terlebih dahulu sebelum disinkronkan ke disk dengan `fsync()`. Jika alokasi `shared_buffers` terlalu besar, kapasitas memori untuk Page Cache kernel akan terhimpit, menyebabkan degradasi performa I/O secara masif saat terjadi *checkpoint flushing*.

**Q: Kapan `work_mem` dilepaskan (free) dari memori?**  
*A:* Alokasi `work_mem` dilepaskan segera setelah operator kueri (seperti satu langkah urutan atau simpul hash join) selesai dieksekusi. Memori ini tidak ditahan sepanjang durasi total koneksi.

**Q: Apakah menaikkan `max_connections` berdampak negatif jika koneksi-koneksi tersebut berada dalam status IDLE?**  
*A:* Ya. Setiap backend process yang menangani koneksi (meskipun idle) mengonsumsi memori virtual dan riil sistem operasi (~2MB hingga ~10MB) serta harus terus dilibatkan dalam pemeriksaan lock array oleh *Checkpointer* dan *Autovacuum*.

---

### 20. References & Documentation
- Dokumentasi Resmi PostgreSQL: [Chapter 53. Server Setup and Operation - Memory Management](https://www.postgresql.org/docs/current/kernel-resources.html)
- PostgreSQL Source Code: `src/backend/storage/buffer/bufmgr.c` (Implementasi Buffer Manager)
- PostgreSQL Wiki: [Tuning Your PostgreSQL Server](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
- Kernel.org: [Linux Virtual Memory Overcommit Documentation](https://www.kernel.org/doc/Documentation/vm/overcommit-accounting)