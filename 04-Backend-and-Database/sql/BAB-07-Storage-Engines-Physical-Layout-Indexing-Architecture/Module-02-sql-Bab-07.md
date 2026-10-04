# BAB 07: Storage Engines, Physical Layout, & Indexing Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Layout Fisik Storage Engine:** Membedah struktur internal halaman data (*slotted-page architecture*), *tuple headers*, dan *free space management* pada engine berbasis disk (InnoDB MySQL dan Heap PostgreSQL) hingga tingkat byte.
2. **Memahami Lifecycle & Concurrency Internal:** Menguasai mekanisme *Page Latching* (*latch crabbing/coupling*), propagasi *Log Sequence Number* (LSN), *Write-Ahead Logging* (WAL), serta dampaknya terhadap *dirty page flushing* dan *crash recovery*.
3. **Mendiagnosis & Mengeliminasi I/O Amplification:** Menghitung dan memitigasi *Write Amplification* (WA) dan *Read Amplification* (RA) akibat *page splits*, fragmentasi indeks, dan ketidaksesuaian ukuran *block storage*.
4. **Menerapkan Struktur Indeks Lanjutan:** Mendesain, mengonfigurasi, dan mengoptimalkan tipe indeks non-B-Tree (*Block Range Indexes* [BRIN], *Generalized Inverted Indexes* [GIN], dan *Log-Structured Merge-Trees* [LSM]) untuk beban kerja OLTP/OLAP berskala terabyte/petabyte.
5. **Mengoptimalkan MVCC di Tingkat Storage:** Merekayasa sistem agar memaksimalkan pemanfaatan *Heap-Only Tuples* (HOT) di PostgreSQL dan meminimalkan saturasi *Undo Log Rollback Segments* di MySQL.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib memahami:
* Konsep dasar struktur data pohon (B-Tree, B+ Tree) dan kompleksitas algoritmik ($O(\log N)$ vs $O(1)$).
* Konsep dasar sistem operasi: POSIX system calls (`read`, `write`, `fsync`, `fdatasync`, `O_DIRECT`), OS Page Cache, dan arsitektur block I/O (LBA, sector size 512e vs 4Kn).
* Pemahaman fundamental mengenai transaksi ACID dan isolasi transaksi ANSI SQL.
* Familiaritas dengan Linux CLI dan inspeksi sistem (*tooling* seperti `iostat`, `perf`, `strace`).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Fisik Slotted-Page Architecture
Mayoritas engine relasional berbasis *page* (misalnya PostgreSQL dengan blok default 8 KB, InnoDB dengan page default 16 KB) mengimplementasikan variasi dari **Slotted-Page Architecture**. Desain ini menyelesaikan problem penempatan tuple yang memiliki panjang variabel (*variable-length records*) tanpa memicu fragmentasi internal yang destruktif.

```
+-----------------------------------------------------------------------+
| PAGE HEADER (LSN, Checksum, Flags, Free Space Pointers)              |
+-----------------------------------------------------------------------+
| Line Pointer 1 (Offset, Len) | Line Pointer 2 | Line Pointer 3 ...    |
+------------------------------+----------------+-----------------------+
|                      ======> FREE SPACE <======                       |
+-----------------------------------------------------------------------+
| ... Tuple 3 Data             | Tuple 2 Data   | Tuple 1 Data          |
+-----------------------------------------------------------------------+
| SPECIAL SPACE (Khusus Indeks: B-Tree sibling pointers, dsb.)          |
+-----------------------------------------------------------------------+
```

##### Komponen Utama Slotted-Page (Standar PostgreSQL/InnoDB):
1. **Page Header:** Metadata halaman. Menyimpan LSN (Log Sequence Number) dari modifikasi terakhir, *checksum*, offset awal *free space*, offset akhir *free space*, serta bit flags (misal: apakah halaman penuh, *leaf node*, atau *root node*).
2. **Line Pointers / Slot Array:** Array pointer berukuran tetap (misal: 4 byte per pointer pada PostgreSQL) yang tumbuh ke arah **bawah** (*downward*). Setiap slot menyimpan offset absolut ke data tuple fisik serta panjang record dan bit status (misal: `LP_NORMAL`, `LP_REDIRECT`, `LP_DEAD`).
3. **Free Space:** Ruang kosong kontinu di tengah-tengah halaman. Fragmentasi dicegah karena ruang kosong selalu dikonsolidasikan di antara array pointer dan payload tuple.
4. **Tuple/Record Storage:** Data baris fisik aktual yang dialokasikan dari **bawah ke atas** (*upward*, dari akhir halaman menuju awal).
5. **Special Space:** Terletak di bagian paling akhir halaman, digunakan oleh metode akses indeks tertentu (seperti B-Tree) untuk menyimpan pointer graf saudara (*left/right sibling leaf pointers* untuk *range scan*).

#### 3.2. Perbandingan Layout Fisik: PostgreSQL Heap vs. MySQL InnoDB

| Parameter Arsitektur | PostgreSQL Heap Page (8 KB) | MySQL InnoDB Page (16 KB) |
| :--- | :--- | :--- |
| **Primary Organization** | Heap tak berurut (*unordered heap*), indeks eksternal menunjuk ke Tuple ID (`ctid`). | *Clustered Index* (Index-Organized Table). Data **adalah** daun B+ Tree dari Primary Key. |
| **Pencarian Tuple** | Line pointer mengarah langsung ke offset byte payload. | Melalui *Page Directory* (sparse index per 4-8 record) untuk binary search di dalam halaman. |
| **MVCC Implementation** | Tuple Header (`t_xmin`, `t_xmax`, `t_cid`, `t_ctid`) berada langsung di dalam baris heap. | Minimalis pada baris: `DB_TRX_ID` (6 byte), `DB_ROLL_PTR` (7 byte) menunjuk ke *Undo Log*. |
| **Write Amplification (Update)** | Tinggi jika mengupdate kolom terindeks: memicu pembuatan tuple baru di blok heap + entri baru di **semua** indeks. | Rendah untuk secondary index: record diupdate di tempat (*in-place*) atau via Undo Log; pointer secondary index tidak berubah jika PK tetap. |
| **Garbage Collection** | `VACUUM` / Autovacuum async membersihkan dead tuples dan memadatkan slot. | Background `Purge Threads` mereklamasi Undo Log segments dan membersihkan *delete-marked records*. |

#### 3.3. Write Path & LSN Subsystem
Setiap mutasi data harus mengikuti aturan baku **Write-Ahead Logging (WAL)**: Perubahan pada struktur data fisik (in-memory buffer) tidak boleh ditulis ke media persisten sebelum perubahan logis tersebut dipersistensikan ke media penyimpanan sekuler non-volatil.

```
[User Transaction]
       |
       v
1. Request Update Record
       |
       v
2. Acquire Exclusive Latch (X-Latch) on Target Page in Buffer Pool
       |
       v
3. Generate Redo Log Record (Assign New LSN)
       |
       v
4. Write Redo Log Record to WAL/Log Buffer
       |
       v
5. Mutate In-Memory Page (Update Tuple + Update Page LSN = New LSN)
       |
       v
6. Release Page X-Latch
       |
       v
7. WAL Buffer Flushed to Disk via fsync() (COMMIT)
       |
       +---------------------------------------------+
       | (Asynchronous Background Thread)            |
       v                                             v
8. Doublewrite Buffer Write (InnoDB)          OS Page Cache / Direct I/O
       |                                             |
       v                                             v
9. Data File Storage (*.ibd / Base Tables)    Data File Storage
```

* **LSN (Log Sequence Number):** Integer 64-bit monotonik naik yang merepresentasikan posisi offset byte di dalam log stream. Setiap halaman memiliki field `PAGE_LSN`. Saat *recovery*, jika `Record_LSN <= Page_LSN`, mesin melewati record tersebut (*idempotency* tercapai).
* **Doublewrite Buffer (InnoDB):** Menghindari fenomena **Torn Page** (kerusakan halaman akibat crash OS/hardware saat menulis blok 16 KB ke drive dengan ukuran sektor fisik 4 KB atau 512 byte). Data ditulis secara berurutan (*sequential I/O*) ke Doublewrite Buffer terlebih dahulu sebelum ditulis ke lokasi offset file aktual (*random I/O*).

#### 3.4. B+ Tree Mechanics: Page Splits, Merges, dan Concurrency
Struktur B+ Tree menjaga keseimbangan secara ketat (*strict balance*): semua daun (*leaf nodes*) berada pada kedalaman yang persis sama.

##### Perhitungan Fanout dan Depth:
Kapasitas penyimpanan B+ Tree dihitung dengan:
$$\text{Fanout} (F) = \frac{\text{Page Size} - \text{Header Overhead}}{\text{Key Size} + \text{Pointer Size}}$$
$$\text{Total Records Capacity} \approx F^{\text{Depth}}$$

*Jika page size = 16 KB, ukuran key (BIGINT) + pointer = 8 + 6 = 14 byte, estimasi overhead = 200 byte:*
$$F \approx \frac{16184}{14} \approx 1156$$
* Pohon dengan $\text{Depth} = 3$ dapat menampung:
  $$1156^3 \approx 1.54 \times 10^9 \text{ records (1,54 Miliar Baris)}$$

##### Anatomi Page Split (50-50 vs. Sequential Split):
* **Random Insertion Split (50-50):** Ketika halaman penuh, sistem mengalokasikan halaman baru, memindahkan 50% record ke halaman baru, dan menyisipkan separator key ke parent node. Hal ini memicu efisiensi ruang turun menjadi rata-rata $\approx 67\%$ (fragmentasi internal).
* **Sequential Append Optimization:** Jika engine mendeteksi pola penulisan monotonik naik (*auto-increment* atau ULID), engine tidak membagi 50-50, melainkan menyisakan halaman lama dalam kondisi 100% penuh dan membuat halaman baru hanya untuk data baru.

##### Concurrency Control: Latch Crabbing / Coupling:
Untuk menelusuri pohon dari Root ke Leaf tanpa memblokir pembaca (*reader*) lain secara global, engine menggunakan protokol **Latch Crabbing**:
1. Latch parent node (Read Latch).
2. Temukan pointer child node.
3. Latch child node (Read Latch).
4. Jika child node aman (tidak membutuhkan split/merge), **lepaskan latch parent node**.
5. Ulangi hingga mencapai target leaf node.

---

### 4. Why & What

#### Mengapa Memahami Arsitektur Fisik Sangat Krusial?
Pada beban transaksi enterprise (skala puluhan ribu hingga ratusan ribu IOPS), database tidak dibatasi oleh siklus CPU, melainkan oleh **I/O Bottlenecks, Lock/Latch Contention, dan Memory Allocation Thrashing**. 

Ketika database developer tidak memahami layout fisik:
1. **UUIDv4 sebagai Clustered Key:** Memaksa penulisan acak (*random writes*) ke disk, memicu *continuous page splits*, merusak integritas *buffer pool*, dan meningkatkan *write amplification* hingga lebih dari 1000%.
2. **Table & Index Bloat (PostgreSQL):** Ketidaktahuan tentang arsitektur MVCC menyebabkan dead tuple menumpuk, memperbesar ukuran tabel hingga 10x lipat dari data riil, merusak performa *sequential scan*, dan melumpuhkan kapasitas RAM.
3. **Checkpoint Spikes:** Kegagalan mengonfigurasi ukuran WAL buffer dan dirty page flushing memicu I/O *freezing* berkala yang merusak Service Level Objective (SLO) latensi p99.

#### Apa yang Dipecahkan oleh Arsitektur Tingkat Lanjut Ini?
* **PostgreSQL HOT (Heap-Only Tuples):** Menghilangkan overhead pembaruan indeks saat operasi `UPDATE` terjadi, selama field yang diubah bukan anggota indeks dan halaman asal masih memiliki *free space*.
* **BRIN (Block Range Index):** Memampatkan ukuran indeks dari gigabyte menjadi kilobyte untuk data berukuran masif yang tersusun secara natural (seperti data deret waktu/timeseries log).
* **GIN (Generalized Inverted Index):** Memfasilitasi indexing multivariat untuk dokumen JSONB, Full-Text Search, dan array dengan kecepatan querying tinggi menggunakan struktur *posting lists* internal.

---

### 5. How (Workflow Detail)

#### Workflow: PostgreSQL HOT (Heap-Only Tuple) Update
PostgreSQL mengimplementasikan optimasi HOT untuk menghindari penulisan ulang ke semua secondary index saat baris di-*update*.

```
[UPDATE Query Executed]
          |
          v
[1. Lock Target Heap Page in Buffer Cache]
          |
          v
[2. Apakah kolom indeks berubah?]
   ├── YA  ──> [Bypass HOT] -> Alokasikan tuple baru, buat entri di SEMUA indeks
   └── TIDAK ──> Lanjut ke langkah 3
          |
          v
[3. Apakah ada Free Space di halaman yang SAMA?]
   ├── TIDAK ──> [Bypass HOT] -> Buat tuple di halaman baru, update pointer indeks
   └── YA    ──> Lanjut ke langkah 4
          |
          v
[4. Tulis Tuple Baru di Halaman yang Sama]
          |
          v
[5. Set Header Old Tuple: Flag Heap_Tuple_Updated, Forwarding Pointer (t_ctid) -> Tuple Baru]
          |
          v
[6. Set Header New Tuple: Flag Heap_Tuple_Heap_Only]
          |
          v
[7. Selesai: Index Root Pointer tetap menunjuk ke Old Tuple Line Pointer. 
     Traversal index langsung mengikuti rantai (chain) di dalam page yang sama!]
```

*Dampak:* Mengurangi I/O indeks hingga 90% pada beban update intensif dan memangkas laju pertumbuhan bloat secara signifikan.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan dengan Lemari Kartu Indeks
Bayangkan sistem storage seperti perpustakaan klasik:
* **Data File (Heap/Tablespace):** Rak-rak buku raksasa. Buku disimpan di slot tertentu (Page).
* **B+ Tree Index:** Lemari kartu katalog sistematis. Kartu diatur menurut abjad pengarang.
* **Secondary Index Lookup (PostgreSQL):** Anda memeriksa kartu katalog $\to$ kartu menyebutkan "Buku ada di Rak 4, Baris 2" ($ctid$) $\to$ Anda berjalan ke Rak 4, Baris 2 untuk mengambil buku.
* **Secondary Index Lookup (MySQL InnoDB):** Kartu katalog sekunder tidak menyebutkan nomor rak fisik, melainkan hanya menyebutkan Nomor Induk Siswa/NIS (Primary Key). Anda mencari di katalog NIS $\to$ baru menemukan buku. (Dua kali traversal jika tidak *covering*).
* **Page Split:** Rak buku nomor 4 sudah padat total. Anda terpaksa membeli satu rak baru, memindahkan setengah buku dari rak 4 ke rak baru, lalu menulis ulang semua penanda rak di ruang kontrol.

#### Diagram: Perbandingan Resolusi Pointer Tuple
```
PostgreSQL: Secondary Index Lookup
[Index Leaf Page] ──────(ctid: Page 102, Slot 4)───────> [Heap Data Page 102]
                                                          +-------------------+
                                                          | Slot 4: Offset 400|
                                                          | ...               |
                                                          | Byte 400: [TUPLE] |
                                                          +-------------------+

MySQL InnoDB: Secondary Index Lookup
[Sec. Index Leaf] ──────(PK Value: 50442)─────────────> [Clustered Index Root]
                                                                  |
                                                           (B+ Tree Traversal)
                                                                  v
                                                        [Clustered Index Leaf]
                                                        +---------------------+
                                                        | PK: 50442           |
                                                        | Trx_ID, Roll_Ptr    |
                                                        | Full Columns Payload|
                                                        +---------------------+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Membedah Page Layout PostgreSQL dengan `pageinspect`
Kita akan memeriksa isi biner internal dari sebuah page menggunakan modul ekstensi resmi PostgreSQL `pageinspect`.

```sql
-- 1. Setup Ekstensi dan Skema Uji
CREATE EXTENSION IF NOT EXISTS pageinspect;

DROP TABLE IF EXISTS storage_lab;
CREATE TABLE storage_lab (
    id SERIAL PRIMARY KEY,
    payload TEXT
);

-- Matikan autovacuum sementara untuk keperluan inspeksi deterministik
ALTER TABLE storage_lab SET (autovacuum_enabled = false);

-- Sisipkan 3 baris data
INSERT INTO storage_lab (payload) VALUES 
('ENGINEERING_DATA_ALPHA'),
('ENGINEERING_DATA_BETA'),
('ENGINEERING_DATA_GAMMA');

-- 2. Inspeksi Page Header dari Blok Pertama (Block 0)
SELECT 
    lsn, 
    checksum, 
    flags, 
    lower, -- Offset akhir dari line pointer array (arah pertumbuhan ke bawah)
    upper, -- Offset awal dari tuple storage terendah (arah pertumbuhan ke atas)
    special, 
    pagesize
FROM page_header(get_raw_page('storage_lab', 0));
```

*Output yang Dihasilkan:*
```text
      lsn      | checksum | flags | lower | upper | special | pagesize 
---------------+----------+-------+-------+-------+---------+----------
 0/1A2B3C4D    |        0 |     0 |    36 |  8048 |    8192 |     8192
```
*Analisis:* Ukuran page adalah 8192 byte. Header berukuran 24 byte. Ditambah 3 pointer slot baris ($3 \times 4 \text{ byte} = 12 \text{ byte}$), maka `lower` berada pada offset $24 + 12 = 36$. Ruang data terendah (`upper`) berada di 8048. *Free space* yang tersisa di halaman ini adalah $8048 - 36 = 8012 \text{ byte}$.

```sql
-- 3. Inspeksi Line Pointer dan Tuple Items di dalam Page 0
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    lp_len, 
    t_xmin, 
    t_xmax, 
    t_ctid, 
    t_data 
FROM heap_page_items(get_raw_page('storage_lab', 0));
```

#### 7.2. Practical Example: Implementasi Indeks BRIN vs B-Tree pada Data Append-Only Skala Besar
Indeks B-Tree tradisional pada data berukuran puluhan juta baris membutuhkan ruang disk yang masif dan seringkali melebihi kapasitas RAM. Kita bandingkan dengan BRIN (*Block Range Index*).

```sql
-- 1. Inisialisasi Tabel Sensor Timeseries
DROP TABLE IF EXISTS telemetry_events;
CREATE TABLE telemetry_events (
    event_id BIGSERIAL,
    created_at TIMESTAMPTZ NOT NULL,
    device_id INT NOT NULL,
    temperature NUMERIC(5,2),
    payload JSONB
);

-- Matikan autovacuum untuk eksperimen
ALTER TABLE telemetry_events SET (autovacuum_enabled = false);

-- 2. Generate 5.000.000 Baris Data Terurut Berdasarkan Waktu
INSERT INTO telemetry_events (created_at, device_id, temperature, payload)
SELECT 
    ts,
    (random() * 1000)::INT,
    (random() * 50)::NUMERIC(5,2),
    jsonb_build_object('status', 'OK', 'cycle', g)
FROM 
    generate_series(
        '2024-01-01 00:00:00'::TIMESTAMPTZ, 
        '2024-06-01 00:00:00'::TIMESTAMPTZ, 
        '2.628 seconds'::interval
    ) AS ts,
    generate_series(1, 1) AS g;

-- 3. Evaluasi Perbandingan Ukuran Indeks
-- A. Pembuatan B-Tree Index Tradisional
CREATE INDEX idx_telemetry_btree_created_at ON telemetry_events (created_at);

-- B. Pembuatan BRIN Index dengan konfigurasi pages_per_range
CREATE INDEX idx_telemetry_brin_created_at ON telemetry_events USING brin (created_at) 
WITH (pages_per_range = 128);

-- C. Query komparasi konsumsi storage
SELECT 
    c.relname AS index_name,
    pg_size_pretty(pg_relation_size(c.oid)) AS index_size,
    am.amname AS index_type
FROM pg_class c
JOIN pg_am am ON c.relam = am.oid
WHERE c.relname IN ('idx_telemetry_btree_created_at', 'idx_telemetry_brin_created_at');
```

*Hasil Ukuran Fisik pada Disk:*
```text
          index_name           | index_size | index_type 
-------------------------------+------------+------------
 idx_telemetry_btree_created_at| 107 MB     | btree
 idx_telemetry_brin_created_at | 48 kB      | brin
```
*Interpretasi Teknis:* Ukuran indeks BRIN **>2.000 kali lebih kecil** daripada B-Tree. BRIN hanya menyimpan agregat nilai `(min_value, max_value)` untuk setiap 128 block range ($128 \times 8\text{ KB} = 1\text{ MB}$ data), sehingga seluruh struktur indeks dapat disimpan secara permanen di CPU L3 Cache atau RAM berukuran minimal.

---

### 8. Real World Case Study (Enterprise Scale)

#### Lingkungan Sistem & Masalah
* **Platform:** Core Payment Gateway Ledger.
* **Volume:** 120.000 transaksi pembayaran per detik (*peak write load*).
* **Storage Engine:** MySQL 8.0 Enterprise (InnoDB), NVMe SSD, AWS `io2.blockExpress` (64.000 Provisioned IOPS).
* **Gejala:** Latensi penulisan p99 melonjak secara acak dari 2 ms menjadi 450 ms setiap 15-20 menit. Selama lonjakan latensi, throughput transaksi anjlok drastis (*sawtooth latency pattern*), memicu antrean timeout di reverse-proxy Envoy.

#### Investigasi Arsitektural
1. **Analisis I/O Metrics:** Menggunakan `iostat -xz 1` mengindikasikan lonjakan nilai `%util` mencapai 100% dan nilai `w_await` melonjak tajam secara bersamaan.
2. **Inspeksi InnoDB Internals:**
   ```sql
   SHOW ENGINE INNODB STATUS\G
   ```
   Ditemukan metrik krusial:
   * *Log sequence number* bergerak jauh lebih cepat dibandingkan *Log flushed up to*.
   * Metrik buffer pool: *Pages flushed up to* tertinggal puluhan gigabyte.
   * Muncul status: `History list length` terus naik dan thread log writer tertahan pada event: `Adaptive Flush: Checkpoint age is close to max checkpoint capacity`.
3. **Analisis Primary Key:**
   Tabel transaksi menggunakan Primary Key bertipe binary/string dengan isi **UUIDv4 standar (Random)**:
   ```sql
   CREATE TABLE transactions (
       transaction_id VARCHAR(36) PRIMARY KEY, -- Terdistribusi acak (UUIDv4)
       created_at TIMESTAMP,
       ...
   );
   ```

#### Root Cause (Akar Masalah)
1. **Extreme B-Tree Page Splits:** Karena UUIDv4 terdistribusi acak di seluruh ruang heksadesimal, setiap operasi `INSERT` harus memodifikasi halaman data secara acak di seluruh pohon setebal 4 level. Ini menyebabkan halaman buffer pool terus menerus berstatus dirty secara acak.
2. **Buffer Pool Thrashing & Low Working Set Hit:** Halaman yang diubah tidak terkumpul secara sekuensial. Cache hit ratio anjlok menjadi 42%. Engine terpaksa mengevikasi halaman dirty ke disk untuk memuat halaman baru secara konstan.
3. **Synchronous Checkpoint Crash Barrier:** WAL (Redo Log) berukuran default terlalu kecil (2x 1 GB). Karena dirty page belum selesai di-flush secara asinkron (*adaptive flush* kalah cepat melawan random writes), ruang sirkular Redo Log habis. InnoDB seketika mengeksekusi **Sharp/Furious Flushing** (checkpointing sinkron darurat). Engine memblokir semua operasi DML hingga disk selesai menulis puluhan ribu dirty pages acak.

#### Solusi Arsitektural & Hasil Implementasi
1. **Migrasi Primary Key ke UUIDv7 (Monotonik Terurut Waktu):** Mengganti UUIDv4 dengan format yang mengombinasikan *Unix timestamp (millisecond)* pada 48 bit pertama dan entropy acak pada bit sisanya.
2. **Penyesuaian Kapasitas Redo Log:**
   Menaikkan ukuran kapasitas total redo log menjadi 64 GB:
   ```ini
   innodb_redo_log_capacity = 68719476736 # 64 GB (MySQL >= 8.0.30)
   innodb_log_buffer_size = 67108864      # 64 MB
   ```
3. **Tuning Page Flush Mechanics:**
   ```ini
   innodb_io_capacity = 20000
   innodb_io_capacity_max = 40000
   innodb_page_cleaners = 8
   innodb_flush_neighbors = 0 # Wajib 0 untuk NVMe Storage (random write overhead rendah)
   ```

#### Hasil Metrik Pasca-Remediasi
* Lonjakan latensi p99 lenyap: Nilai p99 stabil pada **1.8 ms - 2.4 ms**.
* Page splits tereduksi hingga **89%**.
* Buffer pool hit ratio naik drastis dari 42% menjadi **97.8%**.
* *Write Amplification Factor* (WAF) disk turun dari $14.2\times$ menjadi $1.6\times$.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter Desain | Pilihan Arsitektural | Keuntungan (*Pros*) | Kerugian / Biaya (*Cons*) | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- | :--- |
| **Durabilitas WAL** | `innodb_flush_log_at_trx_commit = 1`<br>PostgreSQL: `synchronous_commit = on` | **Zero RPO guarantee:** Tidak ada kehilangan data jika sistem mati mendadak (*crash-safe*). | Latensi transaksi tinggi; throughput dibatasi batas IOPS `fsync` per detik. | Transaksi perbankan, saldo dompet digital, order placement. |
| | `innodb_flush_log_at_trx_commit = 2`<br>PostgreSQL: `synchronous_commit = off` | Throughput penulisan naik $5\times - 10\times$; memangkas pemanggilan `fsync` sinkron. | Potensi kehilangan data hingga rentang interval flush (biasanya 1-2 detik) saat OS crash. | Audit logs, pelacakan event analitik, IoT ingestion. |
| **Index Structure** | **B+ Tree Index** | Pencarian titik (*point query*) dan *range query* kecil sangat cepat ($O(\log N)$). | Ukuran memori besar, write amplification tinggi pada penulisan acak (*page splits*). | Akses data operasional OLTP harian, data referensi/entitas. |
| | **BRIN (Block Range Index)** | Jejak footprint indeks mikroskopik (hemat RAM & Disk hingga 99%); penulisan cepat. | Kecepatan $O(\log N)$ hilang; query membaca 1 rentang blok data penuh (*lossy index*). Memerlukan data tersusun rapi. | Data log deret waktu yang bersifat strictly append-only. |
| **Fillfactor Tuning** | **Fillfactor Rendah (misal: 70-80%)** | Menyediakan *headroom* free space di page: memicu PostgreSQL HOT update dan mencegah B-Tree page splits. | Konsumsi disk dan buffer pool bertambah 20-30% lebih boros (*spatial bloat*). | Tabel dengan rasio `UPDATE` yang sangat tinggi pada record aktif. |
| | **Fillfactor Tinggi (misal: 100%)** | Densitas data maksimal; utilisasi memory cache optimal untuk query `SELECT`. | Setiap `UPDATE` atau `INSERT` di tengah rentang memicu page split dan alokasi blok baru. | Tabel read-only, katalog referensi, sistem data warehouse/arsip. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal Penggunaan UUID Non-Sekuensial pada Clustered Index
* **Anti-Pattern:** Menggunakan `UUID()` standar (RFC 4122 v4) sebagai Primary Key pada MySQL InnoDB.
* **Gejala:** Nilai *Throughput Write* turun drastis seiring dengan bertambahnya volume baris ($> 10.000.000$ baris). Disk I/O utilisasi menyentuh 100% meskipun utilisasi CPU rendah.
* **Solusi Perbaikan:** Gunakan UUIDv7 atau translasikan ke integer bit sequential:
  ```sql
  -- MySQL 8.0: Konversi UUID v1 menjadi terurut secara temporal
  CREATE TABLE secure_orders (
      order_id BINARY(16) NOT NULL,
      payload JSON,
      PRIMARY KEY (order_id)
  );
  -- Gunakan fungsi UUID_TO_BIN(UUID(), 1) -> Argumen kedua (1) menukar bit waktu
  INSERT INTO secure_orders VALUES (UUID_TO_BIN(UUID(), 1), '{"item": "Server"}');
  ```

#### 2. PostgreSQL Vacuum Starvation & Transaction ID (XID) Wraparound
* **Gejala:** Tabel membengkak (*bloat*) masif, performa query menurun tajam, dan log database memunculkan peringatan kritis:
  `WARNING: oldest xmin is far in the past ... database will shut down`.
* **Penyebab:** Adanya transaksi *long-running* yang menggantung (`IDLE IN TRANSACTION`), atau transaksi analitik read-only berdurasi puluhan jam yang menahan threshold `xmin`. Akibatnya, `VACUUM` tidak dapat membersihkan dead tuples yang berada di atas nilai `xmin` tersebut.
* **Troubleshooting Steps:**
  ```sql
  -- 1. Deteksi Transaksi Menggantung Penghalang Vacuum
  SELECT 
      pid, 
      now() - xact_start AS duration, 
      state, 
      backend_xid, 
      backend_xmin, 
      query 
  FROM pg_stat_activity 
  WHERE backend_xmin IS NOT NULL OR backend_xid IS NOT NULL
  ORDER BY duration DESC;

  -- 2. Eliminasi Koneksi Penyebab (Termination)
  SELECT pg_terminate_backend(<PID_PENGGANGGU>);
  ```

#### 3. Index Bloat pada PostgreSQL GIN (JSONB / Full-Text)
* **Penyebab:** PostgreSQL GIN menggunakan struktur buffer sementara `fastupdate = on` secara default untuk menampung insert cepat. Jika laju modifikasi terlalu agresif, pemadatan (*cleanup*) dari buffer ke posting tree tertinggal.
* **Troubleshooting:**
  ```sql
  -- Paksa proses pemadatan GIN pending list secara eksplisit
  SELECT gin_clean_pending_list('nama_index_gin');
  
  -- Atau matikan fastupdate untuk tabel berintensitas write konstan tinggi
  ALTER INDEX nama_index_gin SET (fastupdate = off);
  ```

---

### 11. Best Practices (Production Checklist)

#### Storage Subsystem & OS Alignment
- [ ] Nonaktifkan **Transparent Huge Pages (THP)** pada Linux OS host database:
  ```bash
  echo never > /sys/kernel/mm/transparent_hugepage/enabled
  echo never > /sys/kernel/mm/transparent_hugepage/defrag
  ```
- [ ] Atur Linux I/O Scheduler ke `none` (NVMe SSD) atau `mq-deadline`:
  ```bash
  echo none > /sys/block/nvme0n1/queue/scheduler
  ```
- [ ] Atur nilai Linux Kernel Swappiness ke level minimal (`vm.swappiness = 1` atau `10`).

#### Engine Parameter Tuning (InnoDB)
- [ ] Set `innodb_page_size = 16384` (16 KB) untuk general OLTP, atau `8192` (8 KB) jika bekerja pada beban write intensif yang seragam dengan ukuran OS page clustering.
- [ ] Pastikan ukuran `innodb_buffer_pool_size` mencakup 70% - 80% dari total RAM fisik pada dedicated host.
- [ ] Atur `innodb_flush_method = O_DIRECT` untuk membypass overhead double buffering pada Linux Page Cache.

#### Engine Parameter Tuning (PostgreSQL)
- [ ] Sesuaikan `shared_buffers` di angka 25% dari total RAM sistem (sisanya direservasi untuk OS page cache).
- [ ] Konfigurasi `checkpoint_completion_target = 0.9` dan `max_wal_size = 32GB` hingga `64GB` guna mencegah I/O spikes berkala.
- [ ] Gunakan `wal_compression = on` (lz4 atau zstd) untuk menghemat bandwidth I/O pada WAL subsystem.
- [ ] Atur parameter `fillfactor` pada tabel yang sering diupdate ke angka `85` guna mengizinkan mekanisme HOT update beroperasi.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Skenario Lab
Anda akan membedah physical layout dari tabel database, mensimulasikan terjadinya *Page Split*, dan mengamati terjadinya *Heap-Only Tuple (HOT)* vs Non-HOT update di PostgreSQL menggunakan utilitas biner internal.

#### Struktur Direktori
```text
hands-on/m02/
├── 01_init_environment.sql
├── 02_inspect_hot_updates.sql
├── 03_simulate_page_split.sql
└── docker-compose.yml
```

#### Langkah-langkah Praktikum

##### File: `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'
services:
  pg-engine:
    image: postgres:16-alpine
    container_name: pg_storage_engine_deepdive
    environment:
      POSTGRES_DB: engine_db
      POSTGRES_USER: root
      POSTGRES_PASSWORD: secretpassword
    ports:
      - "5432:5432"
    volumes:
      - ./data:/var/lib/postgresql/data
```

##### File: `hands-on/m02/01_init_environment.sql`
```sql
-- Jalankan: psql -h localhost -U root -d engine_db -f 01_init_environment.sql
CREATE EXTENSION IF NOT EXISTS pageinspect;

-- Matikan autovacuum agar inspeksi slot page tidak diubah secara background
CREATE TABLE accounts (
    account_id INT PRIMARY KEY,
    owner_name VARCHAR(64),
    balance NUMERIC(12,2),
    extra_padding CHAR(200) -- Menambah ukuran tuple untuk mempercepat saturasi page
) WITH (autovacuum_enabled = false, fillfactor = 70);

-- Isi akun awal
INSERT INTO accounts (account_id, owner_name, balance, extra_padding)
SELECT 
    i, 
    'Account Holder ' || i, 
    1000.00, 
    'X'
FROM generate_series(1, 25) AS i;
```

##### File: `hands-on/m02/02_inspect_hot_updates.sql`
```sql
-- Inspeksi awal block 0
SELECT lp, lp_off, lp_flags, lp_len, t_ctid 
FROM heap_page_items(get_raw_page('accounts', 0))
WHERE lp <= 5;

-- Lakukan UPDATE pada kolom non-indeks (balance) pada row account_id = 1
UPDATE accounts SET balance = balance + 500 WHERE account_id = 1;

-- Periksa kembali block 0: Amati apakah HOT Update bekerja!
-- Jika HOT bekerja: Tuple baru dibuat di block 0, dan t_ctid baris lama mengarah ke slot baru.
SELECT 
    lp, 
    lp_off, 
    lp_flags, 
    t_xmin, 
    t_xmax, 
    t_ctid, 
    CASE 
        WHEN (t_infomask & 16384) > 0 THEN 'HEAP_ONLY_TUPLE'
        WHEN (t_infomask & 8192) > 0 THEN 'HEAP_UPDATED'
        ELSE 'NORMAL'
    END AS hot_status
FROM heap_page_items(get_raw_page('accounts', 0))
WHERE lp IN (1, 26);
```

##### File: `hands-on/m02/03_simulate_page_split.sql`
```sql
-- Simulasi Page Split B-Tree
CREATE TABLE btree_split_experiment (
    id UUID PRIMARY KEY,
    payload TEXT
);

-- Masukkan 1000 UUID acak secara sekaligus untuk memicu split multi-halaman
INSERT INTO btree_split_experiment (id, payload)
SELECT gen_random_uuid(), 'Load test fragmentation' 
FROM generate_series(1, 1000);

-- Periksa metadata halaman B-Tree root dan leaf menggunakan pageinspect
SELECT * FROM bt_metap('btree_split_experiment_pkey');

-- Periksa status salah satu leaf page (level = 0)
SELECT 
    itemoffset, 
    ctid, 
    itemlen 
FROM bt_page_items('btree_split_experiment_pkey', 1) 
LIMIT 10;
```

---

### 13. Exercise

#### Level: Easy
1. **Identifikasi Slotted-Page:** Diberikan sebuah page data PostgreSQL berukuran 8192 byte. Nilai pada page header menunjukkan: `lower = 120`, `upper = 6400`. Hitung:
   * Berapa total ruang sisa (*free space*) yang tersedia untuk dialokasikan pada halaman tersebut?
   * Berapa jumlah pointer tuple (*line pointers*) yang terdaftar pada header jika ukuran per slot pointer adalah 4 byte dan ukuran header dasar adalah 24 byte?
2. **Kriteria Kelulusan:** Menunjukkan langkah aritmatika yang tepat sesuai rumus *slotted-page architecture*.

#### Level: Medium
1. **Analisis HOT Chain:** Sebuah tabel memiliki secondary index pada kolom `status`. Sebuah query menjalankan:
   ```sql
   UPDATE orders SET status = 'PROCESSING' WHERE id = 999;
   ```
   Meskipun nilai `fillfactor` diset ke 50 dan halaman target memiliki banyak free space, jelaskan secara arsitektural mengapa optimasi PostgreSQL HOT **gagal** terjadi pada transaksi tersebut!
2. **Kriteria Kelulusan:** Menjelaskan secara presisi aturan dependensi indeks sekunder terhadap tuple header pointers dan implikasinya terhadap write amplification.

#### Level: Hard
1. **Investigasi Latensi LSN Lagging:** Pada platform MySQL 8.0 berbeban write tinggi, analis sistem mendapati metrik:
   * `Innodb_os_log_pending_fsyncs` bernilai > 200 konstan.
   * Nilai Latensi DML melonjak hingga detik (*stalling*).
   * Kapasitas IOPS disk NVMe baru terpakai 30%.
   
   Identifikasi 2 bottleneck konfigurasi internal yang menyebabkan IOPS drive tidak terutilisasi maksimal dan susun konfigurasi perbaikannya.
2. **Kriteria Kelulusan:** Analisis mencakup relasi antara `innodb_log_buffer_size`, sistem *thread concurrency flushing*, alokasi group commit log, serta implementasi `O_DIRECT`.

---

### 14. Challenge

#### Skenario Tantangan Produksi
Anda direkrut sebagai *Lead Database Architect* oleh sebuah perusahaan sekuritas kripto global. Sistem memproses buku pesanan (*Order Matching Engine*) yang menghasilkan data audit log terkompresi sebesar **15 TB per hari**. 

#### Batasan Sistem & Persyaratan Teknis:
1. **Kapasitas Ingestion:** 250.000 events/detik (rata-rata), dengan lonjakan puncak hingga 600.000 events/detik.
2. **Performa Query:** Query pencarian rentang waktu (*audit review*) untuk interval 15 menit tertentu harus diselesaikan dalam waktu kurang dari 500 milidetik.
3. **Keterbatasan Anggaran Hardware:** Biaya storage bulanan harus dipangkas 60%. Anda dilarang menggunakan klaster B-Tree tradisional pada kolom `created_at` karena volume B-Tree index saja memakan 3.5 TB storage SSD NVMe berbiaya mahal per hari.
4. Data harus tetap dapat diakses menggunakan syntax ANSI SQL standar (kompatibel dengan ekosistem relational PostgreSQL).

#### Tugas Arsitektur:
Rancang arsitektur storage fisik menyeluruh yang mencakup:
* Skema partisi tabel data dan konfigurasi engine storage fisik.
* Pilihan strategi indeks yang mampu memecahkan trade-off ruang penyimpanan vs performa query 500 ms.
* Konfigurasi parameter WAL/Flushing kernel dan database engine untuk menahan write spike 600.000 ops/detik tanpa memicu torn pages atau crash barrier starvation.
* Penjelasan rinci tentang *write amplification ratio* dari arsitektur yang Anda rekomendasikan.

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Mengapa sistem slotted-page memisahkan penempatan line pointer (slot) dengan data tuple aktual?
   * A. Agar CPU dapat mengeksekusi kompresi lz4 secara paralel.
   * B. Untuk mencegah terjadinya fragmentasi eksternal saat record dengan panjang variabel diubah atau dihapus.
   * C. Karena sistem operasi Linux tidak mendukung pembacaan block berukuran lebih dari 4 KB.
   * D. Untuk mengizinkan Secondary Index membaca data tanpa melewati Page Header.

2. Pada arsitektur MySQL InnoDB, data dari baris-baris tabel fisik disimpan secara internal pada struktur:
   * A. Heap Table yang tersebar acak di dalam file `.ibd`.
   * B. Daun (*Leaf Nodes*) dari Clustered Index (B+ Tree) berbasis Primary Key.
   * C. Redo Log file secara siklikal.
   * D. Memory Buffer Pool secara volatil tanpa persistensi halaman.

3. Apa fungsi struktural utama dari **LSN (Log Sequence Number)** yang dicatat pada setiap header halaman storage?
   * A. Sebagai primary key internal default bagi database.
   * B. Menghitung jumlah user yang sedang mengakses page tersebut secara bersamaan.
   * C. Menjamin idempotensi crash recovery dengan memastikan mutasi WAL tidak diaplikasikan ulang pada page yang sudah ter-update.
   * D. Mengatur alokasi shared memory cache bagi thread worker.

4. Berapakah ukuran default blok halaman fisik (*page size*) pada sistem basis data PostgreSQL?
   * A. 4 KB
   * B. 8 KB
   * C. 16 KB
   * D. 64 KB

5. Apa perbedaan fundamental antara Page Latch dan Table/Row Lock?
   * A. Latch melindungi integritas struktur data in-memory jangka pendek (mikrodetik); Lock melindungi integritas data transaksional logis jangka panjang.
   * B. Lock dialokasikan di CPU cache, sedangkan Latch dialokasikan pada disk NVMe.
   * C. Latch hanya berlaku untuk InnoDB, sedangkan Lock hanya berlaku untuk PostgreSQL.
   * D. Tidak ada perbedaan; keduanya adalah istilah yang sama untuk mengontrol ACID.

#### 5 Pertanyaan Intermediate
6. Mengapa operasi `UPDATE` pada PostgreSQL jauh lebih berpotensi memicu *Write Amplification* tinggi dibandingkan operasi serupa pada MySQL InnoDB?
   * A. PostgreSQL tidak memiliki fasilitas Write-Ahead Logging (WAL).
   * B. PostgreSQL membuat versi tuple baru secara utuh di heap storage dan wajib memperbarui seluruh pointer secondary index jika optimasi HOT tidak terpenuhi.
   * C. InnoDB tidak pernah menulis modifikasi data ke disk secara langsung.
   * D. PostgreSQL selalu mengunci seluruh tabel (*exclusive table lock*) pada setiap mutasi `UPDATE`.

7. Mekanisme **Doublewrite Buffer** pada MySQL InnoDB diimplementasikan secara khusus untuk menanggulangi problem:
   * A. B+ Tree Page Split yang terjadi pada secondary index.
   * B. Deadlock antar dua transaksi yang mengeksekusi operasi bersamaan.
   * C. *Torn Pages* (kerusakan penulisan separuh blok akibat crash hardware/listrik terputus).
   * D. Penumpukan record usang di dalam Undo Log rollback segment.

8. Dalam protokol penelusuran indeks pohon konruen (**Latch Crabbing**), kapan sebuah Read Latch pada Parent Node dilepaskan oleh traversal thread?
   * A. Setelah seluruh transaksi selesai dan statusnya berstatus `COMMITTED`.
   * B. Segera setelah thread berhasil memperoleh latch pada Child Node yang dituju dan Child Node dipastikan aman.
   * C. Latch parent tidak pernah dilepas hingga proses query SQL selesai mengeksekusi statement.
   * D. Ketika data berhasil dibaca dari disk ke dalam OS page cache.

9. Apa trade-off struktural utama yang harus dibayar saat Anda menurunkan nilai parameter `fillfactor` pada PostgreSQL (misalnya dari 100 ke 70)?
   * A. Database akan melarang pembuatan indeks B-Tree baru pada tabel tersebut.
   * B. Densitas data per page berkurang, menyebabkan tabel memakan disk lebih besar dan menurunkan efisiensi memory cache saat membaca data sekuensial.
   * C. Transaksi penulisan data baru menjadi lambat hingga 300%.
   * D. Mengakibatkan hilangnya jaminan durabilitas ACID saat database mengalami crash.

10. Manakah skenario di bawah ini yang **paling tepat** untuk memanfaatkan tipe indeks **BRIN (Block Range Index)**?
    * A. Tabel pelanggan (*customer*) dengan ID yang dihasilkan secara acak melalui fungsi UUIDv4.
    * B. Tabel inventaris gudang yang sering mengalami update status pada sembarang baris secara acak.
    * C. Kolom audit log timestamp pada tabel deret waktu raksasa yang datanya ditulis secara sekuensial (*monotonically increasing*).
    * D. Kolom data JSONB kompleks yang membutuhkan pencarian key-value multivariat dinamis.

#### 3 Skenario Kasus Produksi
11. **Skenario Kasus 1:** Sebuah database OLTP berskala besar menggunakan PostgreSQL tiba-tiba mengalami degradasi performa I/O parah. Query `SELECT` berbasis index scan yang biasanya memakan waktu 2 ms membengkak menjadi 450 ms. Setelah diinspeksi, ukuran relasi tabel fisik membengkak dari 10 GB menjadi 85 GB, padahal jumlah record aktual relatif statis di angka 5.000.000 baris. Tim infra mendapati sebuah transaksi `pg_dump` replikasi analitik berjalan di background dan telah berstatus `idle in transaction` selama 36 jam. 
    **Pertanyaan Kasus:** Jelaskan korelasi langsung antara transaksi analitik tersebut dengan pembengkakan ukuran fisik tabel (bloat) dan penurunan performa index scan!

12. **Skenario Kasus 2:** Sebuah sistem e-commerce mencatat transaksi ke tabel MySQL 8.0 InnoDB dengan spesifikasi disk SSD berkecepatan 30.000 IOPS. Selama flash sale, aplikasi mencatat lonjakan thread penulisan hingga 200 koneksi bersamaan. Parameter `innodb_flush_log_at_trx_commit` diset ke 1. Database Engineer mengamati bahwa utilisasi IOPS storage hanya mencapai 1.200 IOPS (sangat jauh di bawah limit hardware), namun latensi `COMMIT` aplikasi melonjak hingga 80 ms per transaksi. 
    **Pertanyaan Kasus:** Mengapa IOPS hardware tidak terutilisasi penuh dan fenomena konkurensi apa di tingkat physical write path yang menjadi akar penyebab lonjakan latensi ini?

13. **Skenario Kasus 3:** Startup fintech mengimplementasikan arsitektur database terdistribusi dan memutuskan untuk mengganti tipe Primary Key dari auto-increment `BIGINT` menjadi `UUIDv4` pada seluruh tabel relational MySQL InnoDB mereka dengan alasan keamanan enumerasi ID. Dua bulan setelah rilis produksi dengan volume data melampaui 100 juta transaksi, biaya cloud storage melonjak 4x lipat dan throughput penulisan anjlok hingga tersisa 15% dari baseline awal. 
    **Pertanyaan Kasus:** Analisis kegagalan teknis ini dari kacamata arsitektur B+ Tree clustered index, physical page balance, dan buffer pool lifecycle!

---

### Kunci Jawaban & Pembahasan Quiz

#### Jawaban Pertanyaan Basic
1. **B** — Slotted page memisahkan array pointer dari baris data fisik agar mesin dapat memadatkan dan menggeser data tuple di dalam halaman tanpa perlu mengubah alamat pointer slot eksternal yang dirujuk oleh indeks.
2. **B** — Di InnoDB, struktur data fisik utama tabel adalah Clustered Index itu sendiri (B+ Tree), di mana daun terdalam berisi seluruh payload baris data.
3. **C** — LSN menjamin sifat idempotensi: jika sistem pulih dari crash, mesin memeriksa apakah halaman fisik sudah memiliki LSN yang sama atau lebih besar dari perubahan WAL; jika ya, modifikasi dilewati sehingga tidak terjadi double-write corruption.
4. **B** — PostgreSQL menggunakan ukuran blok default sebesar 8192 byte (8 KB).
5. **A** — Latch adalah primitif sinkronisasi memori tingkat rendah yang dipegang sesaat tanpa deteksi deadlock untuk melindungi data structure in-memory; Lock adalah primitif database logis yang dipegang selama durasi siklus hidup transaksi ACID.

#### Jawaban Pertanyaan Intermediate
6. **B** — Model MVCC PostgreSQL menulis tuple utuh versi baru ke heap table. Jika kolom yang diubah terdaftar pada secondary index, semua secondary index wajib menambahkan entri pointer baru ke ctid baru tersebut, menghasilkan write amplification masif jika HOT update tidak aktif.
7. **C** — Doublewrite Buffer menulis halaman 16 KB ke ruang penyimpanan bersebelahan (*contiguous*) terlebih dahulu sebelum menulisnya ke data file utama guna memulihkan kerusakan jika OS mengalami crash saat penulisan separuh blok disk (512 byte / 4 KB).
8. **B** — Traversal hanya melepaskan read latch parent setelah memastikan child node berikutnya berhasil di-latch dan berada dalam kondisi valid/aman (*lock coupling*), sehingga mencegah race condition pemisahan halaman oleh thread lain.
9. **B** — Menyisakan ruang kosong sengaja menurunkan kepadatan record per blok. Akibatnya, pemindaian sekuensial (*full scan*) harus membaca lebih banyak halaman fisik dari disk ke memori buffer.
10. **C** — BRIN dirancang secara eksklusif untuk data fisik yang terurut secara alami di disk (seperti append-only log timestamp), di mana rentang ribuan blok dapat diringkas hanya dengan nilai batas minimum dan maksimum.

#### Pembahasan Skenario Kasus Produksi
11. **Pembahasan Kasus 1:**
    Transaksi analitik yang menggantung menahan nilai horizon batas transaksi terlama (`oldest xmin`). Sesuai aturan MVCC PostgreSQL, proses pembersihan otomatis (*Autovacuum*) dilarang keras menghapus atau membersihkan dead tuples yang memiliki nilai transaksi lebih baru dari `oldest xmin` tersebut, karena data lama tersebut masih harus terlihat (*visible*) oleh transaksi analitik yang aktif. Akibatnya, seluruh dead tuples dari jutaan operasi DML harian menumpuk di dalam halaman heap (*table bloat*). Indeks B-Tree ikut membesar (*index bloat*) karena harus menyimpan pointer ke baris-baris mati tersebut. Saat index scan dijalankan, CPU dan buffer pool terpaksa memuat ribuan page biner usang dari storage, merusak rasio cache-hit dan memicu I/O latency ratusan milidetik.

12. **Pembahasan Kasus 2:**
    Penyebab utamanya adalah **Synchronous fsync Latency Bottleneck** pada thread commit log. Dengan `innodb_flush_log_at_trx_commit = 1`, setiap kali transaksi memanggil commit, thread sistem operasi mengeksekusi syscall blocking `fsync()` untuk memaksakan pemindahan log dari WAL buffer ke disk. Meskipun NVMe memiliki bandwidth paralel tinggi (30.000 IOPS untuk operasi multi-threaded I/O acak), operasi `fsync` sinkron individual dibatasi oleh latensi putaran hardware (*roundtrip write latency* $\approx 0.8\text{ ms} - 1\text{ ms}$ per pemanggilan). Jika mekanisme *Group Commit* database tidak dikonfigurasi optimal, transaksi tidak sempat digabungkan ke dalam satu pemanggilan flush bersamaan. Thread worker akhirnya mengantre di mutex lock log flushing engine, menghasilkan utilisasi IOPS rendah namun latensi penulisan sangat tinggi.

13. **Pembahasan Kasus 3:**
    UUIDv4 terdistribusi secara probabilistik seragam di seluruh ruang angka 128-bit secara acak. Pada Clustered Index InnoDB, letak fisik data di disk ditentukan mutlak oleh nilai Primary Key ini. Akibatnya:
    * **Page Split Masif & Fragmentasi Internal:** Record baru disisipkan secara acak di tengah-tengah halaman B+ Tree yang sudah padat, memaksa InnoDB membelah halaman (50-50 split). Rata-rata ruang terisi per halaman turun menjadi $\approx 50\% - 60\%$, melipatgandakan kebutuhan ukuran file storage fisik di disk.
    * **Buffer Pool Thrashing:** Penulisan acak mengharuskan InnoDB memuat halaman acak dari disk ke dalam RAM untuk setiap `INSERT`. Ini menendang halaman data aktif dari buffer pool, menjatuhkan cache hit ratio mendekati 0%.
    * **Write Amplification Ekstrem:** Memodifikasi record kecil berukuran 200 byte memaksa sistem menulis ulang keseluruhan halaman 16 KB ke doublewrite buffer dan data files, membakar throughput sistem I/O storage.

---

### 16. Summary

1. **Slotted-Page Mechanics:** Memisahkan line pointer array dengan payload data record fisik guna mendukung mutable variable-length tuples tanpa fragmentasi memori eksternal.
2. **Primary Storage Paradigms:** MySQL InnoDB menstrukturkan seluruh tabel sebagai B+ Tree tunggal (Clustered Index), sedangkan PostgreSQL menggunakan Append-Only Unordered Heap dengan indeks sekunder berbasis pointer fisik (`ctid`).
3. **Optimasi MVCC Storage:** Mekanisme Heap-Only Tuples (HOT) pada PostgreSQL dan Undo Log Pointers pada InnoDB merupakan benteng utama untuk mencegah amplifikasi penulisan dan fragmentasi indeks sekunder pada beban operasi update intensif.
4. **Specialized Indexing Engines:** Pemilihan tipe indeks harus mencerminkan pola distribusi fisik data:
   * **B+ Tree:** Standar emas untuk titik (*point*) dan jangkauan (*small range*) pada data OLTP transaksional.
   * **BRIN:** Solusi berdensitas tinggi untuk data deret waktu berskala multi-terabyte yang tersusun secara monotonik.
   * **GIN:** Fondasi untuk pencarian tipe data komposit (JSONB, Full-Text, Array).
5. **Physical Hardware Co-Design:** Performa basis data enterprise ditentukan oleh keselarasan antara storage engine configuration (block size, WAL flush policies, LSN tracking, fillfactors) dengan karakteristik hardware modern (NVMe sector boundaries, O_DIRECT capabilities, OS memory management).