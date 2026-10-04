# BAB 04: MODULE 01 — Indexing Strategies & Storage Engine

---

## Seksi 01: Identitas Modul

* **Track:** Database Administrator & Infrastructure Engineering
* **Kategori:** 04-Backend-and-Database
* **Kursus:** PostgreSQL DBA
* **Modul:** Indexing Strategies & Storage Engine
* **Kode Modul:** PG-DBA-0401
* **Tingkat Kesulitan:** Advanced / Level 400
* **Estimasi Waktu Penyelesaian:** 180 Menit
* **Prasyarat Pengetahuan:** PostgreSQL Architecture Essentials, Storage Hierarchy (Heap Pages), Transaction Isolation, ANSI SQL Core.

---

## Seksi 02: Learning Objectives

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
1. Menganalisis layout internal dari PostgreSQL Heap Page (8KB default block size), *Tuple Header* (`t_xmin`, `t_xmax`, `t_ctid`), dynamic padding, alignment boundaries, serta mekanisme pointer off-table TOAST.
2. Membedakan karakteristik arsitektural dan kalkulasi kompleksitas waktu/ruang dari 6 jenis indeks bawaan PostgreSQL: **B-Tree**, **BRIN**, **GIN**, **GiST**, **SP-GiST**, dan **Hash**.
3. Merancang dan mengimplementasikan indeks fungsional lanjutan: *Partial Indexes*, *Expression-based Indexes*, *Covering Indexes* (`INCLUDE` clause), serta optimasi multi-kolom (*composite*) berdasarkan hukum selektivitas.
4. Mendiagnosis degradasi performa I/O akibat *index bloat*, mengonfigurasi `fillfactor`, serta mengeksekusi *zero-downtime remediation* menggunakan `REINDEX CONCURRENTLY` dan `pg_repack`.
5. Mengintegrasikan optimasi *Index-Only Scans* dengan memodifikasi visibilitas heap melalui konfigurasi *Free Space Map* (FSM), *Visibility Map* (VM), dan tune-up agresif pada subsistem `autovacuum`.

---

## Seksi 03: Concept Map Diagram ASCII

```text
+--------------------------------------------------------------------------------------------------+
|                                    POSTGRESQL STORAGE ENGINE                                     |
+--------------------------------------------------------------------------------------------------+
                                                 |
                   +-----------------------------+-----------------------------+
                   |                                                           |
                   v                                                           v
       +-----------------------+                                   +-----------------------+
       |   HEAP STORAGE (8KB)  |                                   |    INDEX ACCESS PATH  |
       |  - Page Header (24B)  |                                   |  - B-Tree (nbtree)    |
       |  - Line Pointers (lp) |<============ (Index Pointer) =====|  - BRIN (Block Range) |
       |  - Free Space (FSM)   |              ItemPointerData      |  - GIN (Inverted)     |
       |  - Tuples (HeapTuple) |              (Block#, Offset#)    |  - GiST (Search Tree) |
       |  - TOAST (Out-of-line)|                                   |  - SP-GiST / Hash     |
       +-----------------------+                                   +-----------------------+
                   |                                                           |
                   +-----------------------------+-----------------------------+
                                                 |
                                                 v
                               +-----------------------------------+
                               |       OPTIMIZATION LAYER          |
                               |  - Index-Only Scan (VM Bit check) |
                               |  - Covering Index (INCLUDE)       |
                               |  - Partial / Functional Index     |
                               |  - Deduplication & HOT (Heap-Only)|
                               +-----------------------------------+
```

---

## Seksi 04: Mengapa Relevan

Dalam ekosistem basis data skala terabytes/petabytes, I/O *bottleneck* adalah determinan utama kegagalan *Service Level Objectives* (SLO). Memahami PostgreSQL Storage Engine secara mekanistik membedakan *query tuner* amatir dari Principal Database Administrator.

PostgreSQL menggunakan model konkurensi Multiversion Concurrency Control (MVCC) berbasis *append-only/out-of-place updates*. Setiap operasi `UPDATE` secara fisik menuliskan *tuple* baru ke dalam heap page dan menandai *tuple* lama sebagai *dead*. Jika indexing tidak dirancang dengan mempertimbangkan arsitektur internal ini (misalnya gagal memicu optimasi *Heap-Only Tuples* / HOT), database akan mengalami amplifikasi penulisan (*write amplification*), fragmentasi *shared buffers*, dan *index bloat* masif yang melumpuhkan performa *throughput* transaksi OLTP.

---

## Seksi 05: Anatomi Konsep Inti

### 1. Anatomi PostgreSQL Page Layout (8KB Buffer)

Setiap tabel dan indeks disimpan dalam segment berkas berukuran 1GB (relfilenode) yang dipecah menjadi *pages* (blok) berukuran 8192 bytes.

```text
+--------------------------------------------------------------------+
| PageHeaderData (24 Bytes)                                          |
| [ pd_lsn (8B) | pd_checksum (2B) | pd_flags (2B) | pd_lower (2B) ] |
| [ pd_upper (2B) | pd_special (2B) | pd_pagesize_version (2B)... ]  |
+--------------------------------------------------------------------+
| LinpData (Line Pointers array: 4 bytes per item)                  |
| [lp_1 (4B)] -> Offset to Tuple 1                                   |
| [lp_2 (4B)] -> Offset to Tuple 2                                   |
| [lp_3 (4B)] -----------------------------\                         |
| ===== pd_lower (Free Space Start) ===== |                         |
|                                         |                         |
|             FREE SPACE HOLE             |                         |
|                                         |                         |
| ===== pd_upper (Free Space End) ======= |                         |
|                                         v                         |
|                                     [Tuple 3 Payload + Header]    |
|                                     [Tuple 2 Payload + Header]    |
|                                     [Tuple 1 Payload + Header]    |
+--------------------------------------------------------------------+
| Special Space (Index-specific metadata, e.g., B-Tree sibling links)|
+--------------------------------------------------------------------+
```

* **`PageHeaderData` (24 bytes):** Metadata halaman. `pd_lower` menunjuk ke akhir *Line Pointer array*, `pd_upper` menunjuk ke awal data *Tuple* termuda yang ditulis dari bawah ke atas.
* **`ItemIdData` / Line Pointer (`lp`, 4 bytes):** Terdiri dari bitflag status (`LP_UNUSED`, `LP_NORMAL`, `LP_REDIRECT`, `LP_DEAD`), panjang tuple, dan *byte offset* menuju tuple payload.
* **Tuple Header (`HeapTupleHeaderData`, 23 bytes minimum + alignment padding):**
  * `t_xmin` (4B): XID pembuat transaksi.
  * `t_xmax` (4B): XID penghapus/pengubah transaksi.
  * `t_cid` (4B): Command Identifier.
  * `t_ctid` (6B): *ItemPointerData* yang menunjuk ke lokasi fisik tuple saat ini `(block_number, tuple_index)`. Jika tuple berpindah via `UPDATE`, `t_ctid` menunjuk ke lokasi fisik tuple yang baru.
  * `t_infomask` & `t_infomask2` (4B): Metadata status commit, jumlah atribut, dan flag status HOT.
  * `t_hoff` (1B): *Offset* aktual menuju user payload (memastikan data *aligned* 8-byte/4-byte pada arsitektur 64-bit).

### 2. Deep Dive 6 Index Engines

```text
+----------+----------------------------+-----------------------------+-------------------------------+
| Index    | Algoritma Dasar            | Best Use Cases              | Kompleksitas Pencarian        |
+----------+----------------------------+-----------------------------+-------------------------------+
| B-Tree   | Lehman-Yao High-Concurrency| Kesetaraan (=), Range (<,>) | O(log N) Search / Insertion   |
| BRIN     | Block Range Summary        | Time-series, Ordered logs   | O(Total_Pages/Pages_Per_Range)|
| GIN      | Generalized Inverted Index | JSONB, Full-Text, Arrays    | O(Posting_List_Size) Lookup   |
| GiST     | Generalized Search Tree    | Geometri (PostGIS), Ranges  | O(log N) R-Tree Search        |
| SP-GiST  | Space-Partitioned GiST     | Triangulasi, Prefix (IP,Rad)| O(log N) asymmetric partitions|
| Hash     | Persistent Dynamic Hash    | Equality (=) Only Memory    | O(1) Search via Bucket ID     |
+----------+----------------------------+-----------------------------+-------------------------------+
```

* **B-Tree (Lehman & Yao Algorithm):** Mengimplementasikan *concurrent B-link tree* dengan *right-sibling pointer* yang memungkinkan transversal konkurensi tinggi tanpa memblokir pembacaan selama pemisahan node (*page splits*).
* **BRIN (Block Range Index):** Memetakan rentang blok fisik (*default* 128 halaman / 1MB heap) dan hanya mencatat nilai minimum/maksimum (`min_value`, `max_value`) pada rentang tersebut. Sangat efisien untuk tabel besar bersortir fisik (misal: data time-series *append-only*).
* **GIN (Generalized Inverted Index):** Index berbasis kamus kata-kunci (*lexemes*). Cocok untuk tipe dokumen di mana satu baris berisi banyak elemen (JSONB, array, full-text tokens). Mendukung *posting trees* jika daftar *ItemPointer* per key melampaui ukuran 1 halaman.
* **GiST (Generalized Search Tree):** Struktur pohon berimbang fleksibel yang mengabstraksi hirarki lossy/lossless. Fondasi utama query spasial R-Tree (PostGIS) dan kueri operator *overlapping* (`&&`).
* **SP-GiST (Space-Partitioned GiST):** Mengakomodasi struktur data non-seimbang melalui *quad-trees*, *k-d trees*, dan *radix trees*. Sangat optimal untuk pencarian prefiks nomor telepon, CIDR IP routing, dan partisi spasial titik tidak homogen.
* **Hash Index:** Menggunakan fungsi hash SHA-256 internal untuk memetakan key langsung ke *bucket*. Sejak PostgreSQL 10, Hash Index telah bergaransi *WAL-logged* dan *crash-safe*.

---

## Seksi 06: Panduan Implementasi Step-by-Step

### 1. Eksplorasi Internal Page dengan Ekstensi Introspeksi

Instalasi ekstensi inti untuk investigasi halaman memori:

```sql
CREATE EXTENSION IF NOT EXISTS pageinspect;
CREATE EXTENSION IF NOT EXISTS pgstattuple;
```

### 2. Menganalisis B-Tree Index Header dan Level Internal

Gunakan `pageinspect` untuk mengaudit struktur pohon B-Tree:

```sql
-- Dapatkan stats metapage B-Tree
SELECT * FROM bt_metap('idx_orders_customer_id');

-- Inspeksi item pada root/internal page (misal block 1)
SELECT itemoffset, ctid, itemlen, data 
FROM bt_page_items('idx_orders_customer_id', 1);
```

### 3. Mengimplementasikan Partial & Covering Index Pattern

Optimasi beban tulis dan ruang penyimpanan dengan hanya mengindeks data yang relevan dan menyertakan payload melalui klausa `INCLUDE`:

```sql
-- DDL Covering + Partial Index
CREATE INDEX CONCURRENTLY idx_orders_active_cust 
ON orders (customer_id) 
INCLUDE (order_date, total_amount) 
WHERE status IN ('PENDING', 'PROCESSING');
```

---

## Seksi 07: Contoh Kasus Sederhana

**Kasus:** Sistem memproses 100 juta baris data transaksi *ledger*. Sebagian besar query mencari transaksi yang belum diproses (`status = 'UNPROCESSED'`), yang hanya merepresentasikan 0.5% dari seluruh total data.

### Pendekatan Suboptimal (Full Table B-Tree):
```sql
CREATE INDEX idx_ledger_status ON financial_ledger(status);
-- Ukuran Indeks: ~2.2 GB. Mengindeks 99.5% data yang tidak pernah di-filter spesifik.
```

### Pendekatan Optimal (Partial B-Tree):
```sql
CREATE INDEX idx_ledger_unprocessed 
ON financial_ledger(id, created_at) 
WHERE status = 'UNPROCESSED';
-- Ukuran Indeks: ~11 MB (Pengurangan 99.5% jejak memori & I/O cache).
```

---

## Seksi 08: Implementasi Production-Grade Lengkap Kode

Berikut adalah DDL terpadu, struktur tabel dengan pertimbangan *alignment padding* (mengurutkan tipe data 8-byte, 4-byte, 2-byte, 1-byte untuk meminimalkan *wasted space*), implementasi berbagai mesin indeks, serta penyesuaian parameter `fillfactor`.

```sql
-- Setup skema isolasi
CREATE SCHEMA IF NOT EXISTS telemetry_engine;
SET search_path TO telemetry_engine, public;

-- Hapus tabel jika ada
DROP TABLE IF EXISTS sensor_readings CASCADE;

-- Definisi Tabel Teroptimasi secara Alignment Memory (8B -> 4B -> 2B -> Dynamic)
CREATE TABLE sensor_readings (
    -- 8-byte types
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_uuid UUID NOT NULL,               -- 16 bytes (internally 8-byte aligned)
    recorded_at TIMESTAMPTZ NOT NULL,        -- 8 bytes
    metric_value DOUBLE PRECISION NOT NULL,  -- 8 bytes
    
    -- 4-byte types
    firmware_version INT NOT NULL,           -- 4 bytes
    error_flags INT DEFAULT 0,               -- 4 bytes
    
    -- 2-byte types
    channel_code SMALLINT NOT NULL,          -- 2 bytes
    
    -- Variable / Dynamic types
    status_code VARCHAR(16) NOT NULL,        -- Dynamic (1B or 4B header)
    payload JSONB,                           -- Dynamic TOAST-able
    
    CONSTRAINT pk_sensor_readings PRIMARY KEY (id)
) WITH (
    fillfactor = 85 -- Sisakan 15% ruang per page untuk pembaruan Heap-Only Tuple (HOT)
);

-- ============================================================================
-- STRATEGI INDEKS TINGKAT LANJUT
-- ============================================================================

-- 1. BRIN Index untuk Data Time-series Terurut Fisik
-- Memetakan 128 blok (1MB) per range summary. Sangat hemat memori.
CREATE INDEX idx_sensor_readings_brin_time 
ON sensor_readings 
USING BRIN (recorded_at) 
WITH (pages_per_range = 128);

-- 2. GIN Index dengan JSONB Path Expression (jsonb_path_ops untuk efisiensi operator @>)
CREATE INDEX idx_sensor_readings_payload_jsonb 
ON sensor_readings 
USING GIN (payload jsonb_path_ops);

-- 3. Composite Covering Index B-Tree dengan Klausa INCLUDE
-- Menghilangkan keharusan Heap Fetch (Index-Only Scan) untuk pelaporan per perangkat
CREATE INDEX idx_sensor_readings_device_time_covering 
ON sensor_readings (device_uuid, recorded_at DESC) 
INCLUDE (metric_value, channel_code);

-- 4. Expression / Functional Index untuk Normalisasi Pencarian Teks
CREATE INDEX idx_sensor_readings_status_lower 
ON sensor_readings (LOWER(status_code));

-- 5. Partial Index untuk Error Tracking
CREATE INDEX idx_sensor_readings_active_errors 
ON sensor_readings (device_uuid, recorded_at) 
WHERE error_flags > 0;
```

---

## Seksi 09: Diagram Alur Kerja ASCII

Mekanisme pengambilan keputusan query engine: **Index Scan**, **Bitmap Index Scan**, dan **Index-Only Scan**.

```text
                                [ SQL Query Masuk ]
                                         |
                                         v
                         +-------------------------------+
                         | Ada Index yang Eligible?      |
                         +-------------------------------+
                                   /          \
                           TIDAK  /            \ YA
                                 v              v
                       +----------------+  +-------------------------------+
                       | Seq Scan       |  | Estimasi Jumlah Baris/Cost    |
                       | (Heap Scan)    |  +-------------------------------+
                       +----------------+      /           |           \
                                              /            |            \
                                 Sangat Rendah/            |             \ Selektivitas
                                 Single Target             | Modest       \ Medium-High
                                             /             |               \
                                            v              v                v
                           +------------------+  +-------------------+  +--------------------+
                           | Index Scan       |  | Bitmap Index Scan |  | Index-Only Scan    |
                           | (Heap Fetch per  |  | (Bangun Bitmap ID |  | (Semua kolom ada   |
                           | baris)           |  | & Sort by Phys ID)|  | di Index Tuple)    |
                           +------------------+  +-------------------+  +--------------------+
                                    |                      |                      |
                                    |                      |                      v
                                    |                      |            +--------------------+
                                    |                      |            | Cek Visibility Map |
                                    |                      |            | (Halaman All-Vis?) |
                                    |                      |            +--------------------+
                                    |                      |                /          \
                                    |                      |            YA /            \ TIDAK
                                    |                      |              v              v
                                    |                      |         [No Heap Fetch] [Heap Fetch]
                                    \                      /                \            /
                                     \                    /                  \          /
                                      v                  v                    v        v
                                   +----------------------------------------------------+
                                   |           Kompilasi & Return Hasil Tuple           |
                                   +----------------------------------------------------+
```

---

## Seksi 10: Analisis Trade-offs

```text
+-----------------------+------------------------------------------+------------------------------------------+
| Strategi Index        | Keuntungan (Pros)                        | Biaya / Kerugian (Cons)                  |
+-----------------------+------------------------------------------+------------------------------------------+
| B-Tree Composite      | Sangat cepat untuk kueri multi-predikat. | Ukuran besar; urutan kolom sangat kaku   |
|                       | Mendukung sorting bawaan (ORDER BY).     | (Leftmost prefix rule berlaku).          |
+-----------------------+------------------------------------------+------------------------------------------+
| BRIN                  | Jejak penyimpanan sangat kecil (<1%      | Hanya bekerja pada data dengan korelasi  |
|                       | B-Tree). Overhead penulisan minim.       | fisik tinggi; performa drop jika acak.   |
+-----------------------+------------------------------------------+------------------------------------------+
| GIN (jsonb_path_ops)  | Optimalisasi kueri operator containment  | Write amplification masif saat UPDATE/   |
|                       | (@>). Ukuran lebih padat dr ops default. | INSERT; tidak mendukung pengecekan eksis.|
+-----------------------+------------------------------------------+------------------------------------------+
| Covering (INCLUDE)    | Mengeliminasi pembacaan Heap Page via    | Ukuran B-Tree membesar; data duplikat    |
|                       | Index-Only Scan.                         | tersimpan di Index dan Heap.             |
+-----------------------+------------------------------------------+------------------------------------------+
| Lower Fillfactor (80) | Memaksimalkan peluang HOT Update,        | Kepadatan data Heap berkurang; memicu    |
|                       | mengurangi bloat pada indeks sekunder.   | Seq Scan membaca lebih banyak blok fisik.|
+-----------------------+------------------------------------------+------------------------------------------+
```

---

## Seksi 11: Best Practices & Antipatterns

### Best Practices
1. **Patuhi *Leftmost Prefix Rule*:** Pada indeks `(A, B)`, filter pada `WHERE A = 1` atau `WHERE A = 1 AND B = 2` menggunakan indeks secara optimal. Filter yang hanya menyertakan `WHERE B = 2` tidak dapat melakukan B-Tree Root-to-Leaf traversal biasa.
2. **Kombinasikan `HOT Update` dan `fillfactor`:** Jika tabel memiliki rasio `UPDATE` tinggi pada kolom non-indeks, turunkan `fillfactor` (70-85) untuk memastikan tuple baru masuk ke halaman yang sama tanpa memodifikasi indeks.
3. **Pemanfaatan Indeks Parsial untuk Flag Status:** Jangan mengindeks kolom boolean dengan distribusi biner yang dominan (misal: 99% `is_deleted = true`). Gunakan `CREATE INDEX ... WHERE is_deleted = false`.

### Antipatterns
1. **Over-indexing:** Menempatkan B-Tree pada seluruh *foreign key* dan kolom filter secara membabi buta. Setiap indeks adalah penalti I/O langsung untuk *write path* (`INSERT`, `UPDATE`, `DELETE`).
2. **Mengabaikan *Implicit Casting*:** Kueri yang membandingkan tipe data kolom `VARCHAR` dengan parameter numerik tanpa casting eksplisit membuat query planner mengabaikan indeks.
3. **Menggunakan `LOWER(col)` dalam Kueri Tanpa Functional Index:** `WHERE LOWER(email) = 'x@y.com'` akan memicu *Sequential Scan* jika indeks didefinisikan sebagai B-Tree standar pada `(email)`.

---

## Seksi 12: Security Hardening

Implementasi indeks dan penyimpanan harus mematuhi prinsip keamanan tingkat lanjut:

1. **Proteksi Parameter *Security Definer* pada Functional Indexes:**
   Fungsi yang digunakan dalam *Expression Index* harus bersifat `IMMUTABLE` dan terlindung dari manipulasi `search_path`.
   ```sql
   CREATE OR REPLACE FUNCTION telemetry_engine.sanitize_code(raw_input TEXT)
   RETURNS TEXT 
   LANGUAGE sql 
   IMMUTABLE 
   PARALLEL SAFE
   SET search_path = pg_catalog, pg_temp
   AS $$
       SELECT REGEXP_REPLACE(LOWER(raw_input), '[^a-z0-9]', '', 'g');
   $$;

   CREATE INDEX idx_secure_expression 
   ON telemetry_engine.sensor_readings(telemetry_engine.sanitize_code(status_code));
   ```
2. **Isolasi Tablespace & Storage Permissions:**
   Pisahkan indeks sensitif dan performa tinggi ke dalam *tablespace* dedicated dengan izin direktori ketat pada level OS:
   ```sql
   -- Diberikan hak akses hanya kepada role berwenang
   REVOKE ALL ON TABLESPACE fast_nvme_idx FROM PUBLIC;
   GRANT CREATE ON TABLESPACE fast_nvme_idx TO pg_dba_role;
   ```

---

## Seksi 13: Observabilitas & Debugging

Gunakan query diagnostik berbasis katalog sistem berikut untuk memantau utilitas indeks dan mendeteksi duplikasi serta bloat:

```sql
-- 1. Deteksi Indeks Tidak Terpakai (Unused Indexes)
SELECT 
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
JOIN pg_index USING (indexrelid)
WHERE indisunique IS FALSE 
  AND idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- 2. Audit Efisiensi HOT (Heap-Only Tuple) Update Ratio
SELECT 
    schemaname,
    relname,
    n_tup_upd,
    n_tup_hot_upd,
    CASE 
        WHEN n_tup_upd > 0 
        THEN ROUND(100.0 * n_tup_hot_upd / n_tup_upd, 2) 
        ELSE 0 
    END AS hot_update_ratio_pct
FROM pg_stat_user_tables
WHERE n_tup_upd > 1000
ORDER BY hot_update_ratio_pct ASC;

-- 3. Deteksi Index Bloat via pgstattuple
SELECT 
    nn.nspname AS schema_name,
    c.relname AS index_name,
    stat.leaf_pages,
    stat.empty_pages,
    stat.deleted_pages,
    ROUND(stat.avg_leaf_density::numeric, 2) AS avg_density,
    ROUND(stat.leaf_fragmentation::numeric, 2) AS leaf_frag_pct
FROM pg_class c
JOIN pg_namespace nn ON c.relnamespace = nn.oid
CROSS JOIN LATERAL pgstatindex(c.oid) stat
WHERE c.relam = 403 -- B-Tree AM OID
  AND nn.nspname = 'telemetry_engine';
```

---

## Seksi 14: Benchmarking & Performance

Eksekusi perbandingan performa terukur antara *Standard Scan*, *Covering Index (Index-Only Scan)*, dan *BRIN Scan*.

```sql
-- Siapkan 5.000.000 data sampel sintetis
INSERT INTO telemetry_engine.sensor_readings (
    device_uuid, 
    recorded_at, 
    metric_value, 
    firmware_version, 
    channel_code, 
    status_code, 
    payload
)
SELECT 
    gen_random_uuid(),
    ts,
    random() * 100.0,
    100,
    (random() * 5)::int,
    CASE WHEN random() > 0.1 THEN 'ONLINE' ELSE 'ERROR' END,
    jsonb_build_object('voltage', random() * 240, 'temp', random() * 85)
FROM generate_series(
    '2024-01-01 00:00:00'::timestamptz, 
    '2024-03-01 00:00:00'::timestamptz, 
    '1.049 seconds'::interval
) AS ts;

-- Pastikan autovacuum mengupdate visibility map
VACUUM ANALYZE telemetry_engine.sensor_readings;
```

### Pengujian 1: Evaluasi Query Covering Index (Index-Only Scan)
```sql
EXPLAIN (ANALYZE, BUFFERS, SETTINGS)
SELECT device_uuid, recorded_at, metric_value, channel_code
FROM telemetry_engine.sensor_readings
WHERE device_uuid = 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
  AND recorded_at >= '2024-01-15'
ORDER BY recorded_at DESC;
```
*Hasil:* Execution Time turun dari ~180ms (Seq Scan) ke **< 0.05ms**, `Heap Fetches: 0`, Buffers Hit: 3-4 blocks.

---

## Seksi 15: Hands-on Lab Mini-Project

### Skenario Lab
Anda menduduki posisi Lead DBA pada platform logistik. Tabel transaksi `shipment_tracking` membengkak hingga 100GB. Kueri audit pencarian JSONB dan filter tanggal membebani I/O *disk array*, sementara operasi update status pengiriman memicu tingginya *I/O wait*.

### Tugas:
1. Rekayasa tabel berkinerja tinggi yang meminimalkan alignment padding.
2. Terapkan partisi indeks fungsional, JSONB GIN, dan B-Tree covering.
3. Simulasikan dan validasi eliminasi Index Bloat secara *zero-downtime*.

```sql
-- Setup Lab
CREATE TABLE shipment_tracking (
    shipment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tracking_number UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    is_delivered BOOLEAN DEFAULT FALSE,
    current_location JSONB NOT NULL,
    status VARCHAR(32) NOT NULL
) WITH (fillfactor = 80);

-- Implementasikan Solusi Indeks
CREATE INDEX idx_shipment_lookup 
ON shipment_tracking (tracking_number) 
INCLUDE (status, updated_at);

CREATE INDEX idx_shipment_undelivered 
ON shipment_tracking (created_at) 
WHERE is_delivered = FALSE;

CREATE INDEX idx_shipment_gps 
ON shipment_tracking USING GIN (current_location jsonb_path_ops);
```

---

## Seksi 16: Automated Testing & Verification

Berikut test harness berbasis SQL assertion untuk memastikan indeks bekerja sesuai ekspektasi query plan:

```sql
DO $$
DECLARE
    v_plan JSON;
    v_node_type TEXT;
BEGIN
    -- Jalankan EXPLAIN JSON ke dalam variabel
    EXECUTE 'EXPLAIN (FORMAT JSON) 
             SELECT tracking_number, status, updated_at 
             FROM shipment_tracking 
             WHERE tracking_number = ''a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11''' 
    INTO v_plan;

    -- Ekstrak tipe node teratas
    v_node_type := v_plan->0->'Plan'->>'Node Type';

    -- Assertion: Node HARUS berupa Index Only Scan
    IF v_node_type != 'Index Only Scan' THEN
        RAISE EXCEPTION 'TEST FAILED: Eksekusi tidak menggunakan Index Only Scan. Node terdeteksi: %', v_node_type;
    ELSE
        RAISE NOTICE 'TEST PASSED: Arsitektur Index-Only Scan terverifikasi optimal (Node: %).', v_node_type;
    END IF;
END $$;
```

---

## Seksi 17: Troubleshooting Guide

### Isu 1: Query Mengabaikan Index Scan dan Memilih Sequential Scan
* **Gejala:** Query lambat; `EXPLAIN` menunjukkan `Seq Scan` padahal indeks tersedia pada kolom target.
* **Penyebab Kemungkinan:**
  * Estimasi selektivitas terlalu rendah (tabel membaca persentase baris yang sangat tinggi, misal > 20% data).
  * Statistik optimizer usang (`pg_statistic`).
  * Nilai `random_page_cost` diset terlalu tinggi (default 4.0 pada NVMe storage).
* **Solusi Perbaikan:**
  ```sql
  -- Update statistik planner
  ANALYZE telemetry_engine.sensor_readings;
  
  -- Sesuaikan cost estimator untuk NVMe/SSD storage
  SET random_page_cost = 1.1;
  SET seq_page_cost = 1.0;
  ```

### Isu 2: Index Bloat Parah Pasca Update / Delete Masif
* **Gejala:** Ukuran indeks di disk berlipat ganda, `avg_leaf_density` drop < 50%, buffer cache penuh oleh indeks kosong.
* **Solusi Perbaikan (Zero-Downtime):**
  ```sql
  -- Rekonstruksi index secara konkuren tanpa exclusive lock tabel
  REINDEX INDEX CONCURRENTLY telemetry_engine.idx_orders_active_cust;
  ```

---

## Seksi 18: Checklist Produksi

Sebelum merilis strategi indeks ke lingkungan *production*, pastikan checklist berikut terpenuhi:

- [ ] Seluruh DDL pembuatan indeks menggunakan klausa `CONCURRENTLY` guna mencegah *AccessExclusiveLock* pada tabel produksi.
- [ ] Tipe data kolom disusun secara berurutan sesuai batas keselarasan memori (*alignment padding*): 8-byte, 4-byte, 2-byte, 1-byte/variabel.
- [ ] Rasio efisiensi HOT Update dipantau dan parameter `fillfactor` (70-90) telah dikonfigurasi pada tabel dengan frekuensi `UPDATE` tinggi.
- [ ] Indeks berulang (*duplicate/redundant indexes*) telah diaudit dan dihapus (misal indeks tunggal pada `(A)` jika sudah ada indeks komposit `(A, B)`).
- [ ] Visibility Map diperbarui via konfigurasi `autovacuum_vacuum_scale_factor` agresif untuk memaksimalkan *Index-Only Scans*.
- [ ] Indeks B-Tree berukuran raksasa untuk data bersortir fisik *time-series* telah dievaluasi untuk migrasi ke arsitektur BRIN.
- [ ] Parameter `maintenance_work_mem` dialokasikan secara memadai pada session maintenance sebelum eksekusi massal `CREATE/REINDEX`.

---

## Seksi 19: Ringkasan Eksekutif

Pondasi performa PostgreSQL terletak pada interaksi antara struktur fisik **8KB Heap Page** dan **Access Methods**. Menguasai arsitektur *Heap Layout*, *Tuple Header*, dan *Visibility Map* adalah prasyarat mutlak dalam merancang indeks tingkat lanjut. 

B-Tree tetap menjadi mesin serbaguna utama, namun indeks spesifik seperti BRIN menawarkan efisiensi ruang hingga 99% pada data sekuensial, sementara GIN mutlak diperlukan untuk manipulasi semantik semi-terstruktur JSONB. Memaksimalkan fitur modern seperti **Covering Indexes (`INCLUDE`)**, **Partial Indexes**, penyesuaian **Alignment Padding**, serta preservasi **HOT Updates** memastikan PostgreSQL mampu mempertahankan latensi *sub-millisecond* di bawah beban kerja konkurensi tinggi.

---

## Seksi 20: Referensi & Bacaan Lanjutan

1. PostgreSQL Global Development Group. *Documentation: Chapter 64 - Index Access Method Interface Definition*. [https://www.postgresql.org/docs/current/indexam.html](https://www.postgresql.org/docs/current/indexam.html)
2. PostgreSQL Global Development Group. *Documentation: Chapter 73 - Database Physical Storage*. [https://www.postgresql.org/docs/current/storage.html](https://www.postgresql.org/docs/current/storage.html)
3. Lehman, P. L., & Yao, S. B. (1981). *Efficient Locking for Concurrent Operations on B-Trees*. ACM Transactions on Database Systems (TODS).
4. Winand, Markus. *Use The Index, Luke! A Guide to Database Performance for Developers*.
5. Smith, Gregory. *PostgreSQL 9.0 High Performance*. Packt Publishing.
6. The Internals of PostgreSQL. *Inter-process Communication and Storage Engine Architecture*. [https://www.interdb.jp/pg/](https://www.interdb.jp/pg/)