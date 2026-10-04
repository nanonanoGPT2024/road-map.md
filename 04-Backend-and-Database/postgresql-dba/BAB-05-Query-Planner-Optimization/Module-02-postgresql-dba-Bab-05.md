# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: PostgreSQL Query Planner & Cost-Based Optimizer (CBO)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Principal Database Architect / Lead Production DBA diharapkan mampu:
- Membedah dan mengonfigurasi Cost-Based Optimizer (CBO) PostgreSQL pada level internal (*Cost Constants*, *Path Generation*, *Dynamic Programming Search*, dan *Genetic Query Optimization/GEQO*).
- Mengeliminasi anomali estimasi kardinalitas (*cardinality misestimation*) melalui implementasi *Extended Statistics* multivariate (`ndistinct`, `dependencies`, `mcv`).
- Mendiagnosis degradasi performa pada strategi join (*Nested Loop*, *Hash Join*, *Merge Join*) serta mengendalikan perilaku *work_mem spilling* ke disk secara deterministik.
- Mengontrol *plan stability* tanpa mengorbankan portabilitas engine, mengevaluasi *Just-In-Time (JIT) compilation*, dan mendeteksi regresi eksekusi query secara terotomasi pada sistem berskala *high-throughput OLTP* dan *near-real-time analytical processing*.

---

## 2. Prerequisite

- Pemahaman mendalam tentang arsitektur storage engine PostgreSQL (Heap Pages, Slotted Pages, WAL, Shared Buffers, MVCC snapshot isolation).
- Penguasaan dasar perintah `EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)`.
- Pengalaman mengelola instance PostgreSQL produksi (v13 ke atas, direkomendasikan v15/v16) dengan beban minimal 5.000 TPS.
- Pemahaman dasar C/Sytem Architecture terkait komparasi memori vs I/O latency (DRAM vs NVMe/SATA SSD vs HDD transfer cost).

---

## 3. Concept & Internal Architecture (Mendalam)

Proses perencanaan query di PostgreSQL ditangani oleh *Cost-Based Optimizer* (CBO). CBO bertugas mengonversi *Abstract Syntax Tree (AST)* yang telah divalidasi oleh *Rewriter* menjadi *Execution Plan* pohon operator (*Plan Nodes*) dengan total kalkulasi biaya (*estimated total cost*) terendah.

```
       Query String
            │
            ▼
    ┌───────────────┐
    │    Parser     │ ──> Parse Tree
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │   Rewriter    │ ──> Query Tree (Views, RLS diterapkan)
    └───────────────┘
            │
            ▼
┌───────────────────────┐
│   Planner/Optimizer   │
│ ┌───────────────────┐ │
│ │ Path Generation   │ │ ──> RelOptInfo, Path Nodes
│ └───────────────────┘ │
│ ┌───────────────────┐ │
│ │ Cost Calculation  │ │ ──> CPU + I/O cost computation
│ └───────────────────┘ │
│ ┌───────────────────┐ │
│ │ DP / GEQO Search  │ │ ──> Pemilihan Path Termurah (Cheapest Path)
│ └───────────────────┘ │
└───────────────────────┘
            │
            ▼
    ┌───────────────┐
    │ Plan Tree     │ ──> Plan Nodes (SeqScan, HashJoin, Sort, dll.)
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │   Executor    │ ──> Dynamic Execution (Demand-driven Iterator Pattern)
    └───────────────┘
```

### 3.1. Internal Data Structures: `RelOptInfo` dan `Path`

Selama fase perencanaan:
1. Engine memecah relasi menjadi struktur `RelOptInfo` (`src/include/nodes/pathnodes.h`), yang merepresentasikan base relations, join relations, atau subqueries.
2. Setiap `RelOptInfo` memiliki daftar alternatif akses data yang disebut `Path` (misalnya `IndexPath`, `SeqPath`, `BitmapHeapPath`).
3. Algoritma optimasi join membangun pohon permutasi join via *Dynamic Programming* standard (metode `standard_join_search`). Jika jumlah relasi yang di-join melebihi parameter `geqo_threshold` (default: 12), engine beralih menggunakan *Genetic Query Optimizer* (`GEQO`) guna mencegah *combinatorial explosion* $O(N!)$ pada konsumsi memori dan CPU planner.

### 3.2. CBO Formulae: CPU vs I/O Cost Model

Biaya ($C$) diukur dalam satuan arbitrer di mana $1.0$ didefinisikan sebagai `seq_page_cost` (satu kali pembacaan sequential disk block). Rumus dasar estimasi biaya sekuensial adalah:

$$\text{Cost}_{\text{SeqScan}} = (N_{\text{pages}} \times \text{seq\_page\_cost}) + (N_{\text{tuples}} \times \text{cpu\_tuple\_cost}) + (N_{\text{tuples}} \times N_{\text{operators}} \times \text{cpu\_operator\_cost})$$

Untuk operasi Random I/O (seperti B-Tree Index traversal):

$$\text{Cost}_{\text{IndexScan}} = \text{Cost}_{\text{IndexTree}} + (N_{\text{est\_pages}} \times \text{random\_page\_cost}) + (N_{\text{est\_tuples}} \times \text{cpu\_index\_tuple\_cost}) + \dots$$

Secara internal, rasio efisiensi caching ditentukan oleh `effective_cache_size`, yang mempengaruhi pertimbangan engine apakah suatu page berada di OS Page Cache/Shared Buffers atau harus dijemput dari physical disk block.

### 3.3. Join Execution & Memory Spilling Internals

PostgreSQL mengimplementasikan 3 strategi join utama:
- **Nested Loop Join**: Kompleksitas $O(M \times N)$ tanpa indeks, mendekati $O(M \log N)$ dengan indeks inner. Ideal jika relasi luar (*outer*) sangat kecil dan relasi dalam (*inner*) terindeks secara tepat.
- **Merge Join**: Kompleksitas $O(M \log M + N \log N)$ untuk sorting, dilanjutkan dengan merge $O(M + N)$. Membutuhkan kedua relasi terurut berdasarkan *join keys*.
- **Hash Join**: Bekerja dalam dua fase:
  1. *Build Phase*: Membaca relasi inner, menghitung nilai hash key, lalu membangun *in-memory hash table*.
  2. *Probe Phase*: Membaca relasi outer, menghitung hash key, dan mencari kecocokan pada hash table.

Jika ukuran *hash table* melebihi batas alokasi memori runtime (`work_mem`), engine PostgreSQL membagi proses hash join menjadi multi-batching menggunakan disk:
- Batch dibagi menjadi $2^k$ batch (*Batches: $2^n$*).
- Tuple di-hash ke dalam partisi bucket disk sementara (*spill to disk via BufFile*). Ini menyebabkan lonjakan drastis pada I/O disk dan latency, karena data harus ditulis lalu dibaca kembali secara berulang dari temporary files.

### 3.4. JIT (Just-In-Time) Compilation

PostgreSQL mengintegrasikan LLVM untuk mengompilasi ekspresi SQL kompleks (misalnya evaluasi klausa `WHERE`, target list tuple, serta *inlined* aggregate operations) langsung menjadi kode mesin native:
- **JIT Expression Evaluation**: Mengeliminasi overhead interpretasi function pointer generic PostgreSQL per-tuple.
- **JIT Deforming**: Mengompilasi kode spesifik untuk mengubah format tuple mentah disk (On-disk tuple) menjadi memori internal (Datums).
- **Trade-off**: Waktu inisiasi JIT (*JIT generation time*) bernilai cukup mahal ( puluhan hingga ratusan millisecond). Apabila query berjalan cepat (OLTP tipikal < 5ms), eksekusi JIT justru menyebabkan degradasi performa catastrophic jika parameter `jit_above_cost` disetel terlalu rendah.

---

## 4. Why & What

### Mengapa CBO Mengambil Keputusan yang Salah?

CBO PostgreSQL adalah peramal deterministik yang sangat bergantung pada **Statistik Distribusi Data**. CBO akan menghasilkan eksekusi yang lambat jika terjadi:
1. **Penyimpangan Prediksi Korelasi Antar-Kolom**: Secara default, PostgreSQL mengasumsikan bahwa setiap predikat pada klausa `WHERE` bersifat independen secara statistik ($P(A \cap B) = P(A) \times P(B)$). Jika terdapat korelasi fungsional (misal: `make = 'Audi'` dan `model = 'R8'`), CBO akan melakukan *under-estimation* secara eksponensial. Akibatnya: CBO memilih *Nested Loop* alih-alih *Hash Join*, yang menyebabkan degradasi waktu eksekusi dari beberapa milidetik menjadi puluhan menit.
2. **Statistik Usang (*Stale Statistics*)**: Frekuensi pembaruan auto-vacuum/analyze tidak sebanding dengan laju write/update tuple pada tabel dengan partisi masif.
3. **Out-of-Memory Spilling**: Nilai `work_mem` terlalu konservatif, memaksa planner beralih menggunakan multi-batch hash join atau disk sort.
4. **Kalibrasi Hardware Default yang Tidak Realistis**: Parameter `random_page_cost = 4.0` (asumsi spinning HDD lama) membuat CBO menghindari pembacaan indeks pada NVMe SSD modern, di mana cost acak mendekati `1.1`.

---

## 5. How (Workflow Detail)

Alur kerja troubleshooting dan optimalisasi query plan tingkat lanjut:

```
Identifikasi Slow Query (pg_stat_statements)
  │
  ├─> Jalankan EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)
  │     │
  │     ├─> Periksa: Actual Rows vs Estimated Rows
  │     │     ├─> Melenceng > 10x-100x? 
  │     │     │     ├─> Multi-column correlation? ──> Buat CREATE STATISTICS
  │     │     │     └─> Data skewed/unbalanced? ────> Naikkan default_statistics_target
  │     │     │
  │     │     └─> Periksa: Spilling Memory
  │     │           ├─> Sort Method: external merge Disk? ──> Tingkatkan work_mem (Sesi/Query level)
  │     │           └─> Hash Batches > 1? ─────────────────> Tingkatkan work_mem
  │     │
  │     ├─> Periksa: JIT Timing vs Total Runtime
  │     │     └─> JIT generation time > 20% runtime? ───────> SET jit = off;
  │     │
  │     └─> Periksa: Hardware Misalignment
  │           └─> SSD tetapi SeqScan dipaksakan? ────────────> Set random_page_cost = 1.1
  │
  └─> Validasi Plan Stability (pg_stat_plans / pg_hint_plan jika darurat)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Logistik Pergudangan Modern

Bayangkan query planner sebagai seorang Manajer Logistik Gudang:
- **Table** adalah lorong gudang.
- **Index** adalah katalog referensi cepat (nomor rak).
- **Sequential Scan**: Manajer menyuruh pekerja berjalan dari ujung lorong ke ujung lain, memeriksa setiap kotak satu per satu. Efisien jika 80% barang di lorong itu harus diambil.
- **Index Scan**: Pekerja membuka katalog, menemukan 3 lokasi kotak yang tepat, lalu berjalan langsung mengambilnya. Sangat cepat jika barang yang dicari sedikit. Namun jika barangnya banyak, bolak-balik mengambil barang via lokasi acak akan membuang waktu (Random I/O penalty).
- **Multi-Batch Hash Join Spill**: Meja sortir pekerja (yaitu `work_mem`) terlalu kecil. Daripada menyelesaikan sortir sekaligus di atas meja (RAM), pekerja terpaksa membagi barang ke dalam kardus-kardus sementara, menyimpannya di lantai luar (Disk), lalu mengambil dan menyortirnya kembali satu per satu.

### Diagram: In-Memory Hash Join vs Disk Spilling Hash Join

```
========================= IN-MEMORY HASH JOIN =========================
Hash Keys ──> [ Hash Function ] ──> [ RAM: Hash Table (work_mem) ]
                                             │
Outer Tuples ────────────────────────────────┴──> Match Found (Fast Pipeline)

======================== MULTI-BATCH DISK SPILL =======================
Hash Keys ──> [ Hash Function ]
                    │
            ┌───────┴───────┐
            │ Hash Table    │ (work_mem Penuh!)
            └───────┬───────┘
                    ▼
          [ Spill to Disk: Temp File Batch 1 ]
          [ Spill to Disk: Temp File Batch 2 ]  <── Heavy Disk I/O!
          [ Spill to Disk: Temp File Batch N ]
                    ▲
Outer Tuples ───────┴──> Loop over each Batch file sequentially
```

---

## 7. Simple Example & Practical Example

### 7.1. Setup Skema & Masalah Korelasi Data

```sql
-- Setup tabel simulasi e-commerce order
CREATE TABLE customer_orders (
    order_id BIGSERIAL PRIMARY KEY,
    country_code VARCHAR(3) NOT NULL,
    shipping_provider VARCHAR(50) NOT NULL,
    order_status VARCHAR(20) NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

-- Mengisi data dengan korelasi kuat antara country_code dan shipping_provider
-- ID (Indonesia) selalu menggunakan 'JNE-EXPRESS' (95%)
INSERT INTO customer_orders (country_code, shipping_provider, order_status, total_amount, created_at)
SELECT 
    'ID',
    CASE WHEN random() < 0.95 THEN 'JNE-EXPRESS' ELSE 'DHL' END,
    CASE WHEN random() < 0.10 THEN 'PENDING' ELSE 'COMPLETED' END,
    (random() * 1000)::numeric(12,2),
    NOW() - (random() * interval '30 days')
FROM generate_series(1, 1000000);

-- Tambahkan data acak dari negara lain
INSERT INTO customer_orders (country_code, shipping_provider, order_status, total_amount, created_at)
SELECT 
    'US',
    CASE WHEN random() < 0.90 THEN 'FEDEX' ELSE 'USPS' END,
    'COMPLETED',
    (random() * 1000)::numeric(12,2),
    NOW() - (random() * interval '30 days')
FROM generate_series(1, 500000);

CREATE INDEX idx_orders_composite ON customer_orders (country_code, shipping_provider);
ANALYZE customer_orders;
```

### 7.2. Deteksi Cardinality Under-Estimation

```sql
-- Analisis query dengan filtering pada dua kolom berkorelasi
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) 
FROM customer_orders 
WHERE country_code = 'ID' AND shipping_provider = 'JNE-EXPRESS';
```

*Output Planner Default:*
```
Aggregate  (cost=18520.10..18520.11 rows=1 width=8) (actual time=95.123..95.124 rows=1 loops=1)
  Buffers: shared hit=4821
  ->  Bitmap Heap Scan on customer_orders  (cost=12015.30..17000.00 rows=608000 width=0) (actual time=35.120..82.450 rows=950000 loops=1)
        Recheck Cond: ((country_code)::text = 'ID'::text AND (shipping_provider)::text = 'JNE-EXPRESS'::text)
        ...
```
*Catatan Analisis*: Perhatikan `rows=608000` (prediksi) vs `rows=950000` (aktual). Planner menghitung:
$$P(\text{country} = \text{'ID'}) \times P(\text{shipping} = \text{'JNE'}) \approx 0.66 \times 0.63 = 0.416 \implies 624.000\text{ rows}$$
Asumsi independensi ini salah karena di Indonesia, penggunaan JNE mencapai 95%.

### 7.3. Penerapan Solusi Lanjutan: Extended Statistics

```sql
-- 1. Buat Extended Statistics multivariate untuk mengukur dependensi fungsional & MCV (Most Common Values)
CREATE STATISTICS stats_orders_country_provider 
ON country_code, shipping_provider 
FROM customer_orders;

-- 2. Update statistik tabel
ANALYZE customer_orders;

-- 3. Cek katalog metadata statistik internal
SELECT 
    stxname, 
    stxkeys, 
    stxkind 
FROM pg_statistic_ext 
WHERE stxname = 'stats_orders_country_provider';

-- 4. Jalankan kembali query explain
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) 
FROM customer_orders 
WHERE country_code = 'ID' AND shipping_provider = 'JNE-EXPRESS';
```
*Hasil pasca-extended statistics:*
Perkiraan `rows=949880` vs aktual `rows=950000`. Akurasi estimasi melonjak hingga >99.9%, yang mencegah planner memilih nested loop scan saat tabel ini di-join dengan tabel invoice atau settlement downstream.

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Insiden Produksi
- **Platform**: Core Banking Ledger System (Fintech Tier-1).
- **Volume Data**: Tabel `ledger_entries` (180 juta rows), `accounts` (10 juta rows).
- **Gejala**: Pukul 09:00 WIB (awal jam bursa), endpoint API `/v1/settlement/reconcile` mengalami kenaikan latency dari p99 = 250ms menjadi p99 = 45 detik. CPU load database master melonjak ke 98%.

### Root Cause Analysis (RCA)
1. Tim DBA mengeksekusi `EXPLAIN (ANALYZE, BUFFERS)` pada query rekonsiliasi yang lambat:
```sql
SELECT l.account_id, SUM(l.amount), a.account_tier 
FROM ledger_entries l
JOIN accounts a ON l.account_id = a.account_id
WHERE l.entry_date = CURRENT_DATE 
  AND a.status = 'ACTIVE'
GROUP BY l.account_id, a.account_tier;
```
2. Dari log query plan ditemukan:
```
->  Hash Join  (cost=450212.00..1203021.00 rows=1500000 width=45) (actual time=8120.12..43120.50 rows=1480000 loops=1)
      Hash Cond: (l.account_id = a.account_id)
      Buffers: shared hit=42102 read=120311, temp written=98210 read=98210
      ->  Seq Scan on ledger_entries l ...
      ->  Hash  (cost=150000.00..150000.00 rows=8000000 width=16) (actual time=6100.20..6100.20 rows=8000000 loops=1)
            Buckets: 1048576  Batches: 32  Memory Usage: 16385kB
```
3. **Analisis Masalah**:
   - `Batches: 32` membuktikan telah terjadi *Memory Spilling*.
   - Nilai default sistem `work_mem = 4MB` sangat tidak memadai untuk menampung Hash Table dari 8 juta accounts (`Memory Usage` hanya dialokasikan ~16MB lalu sisanya tumpah ke `temp written=98210` blok buffer ke disk IOPS).
   - Ditambah lagi, SSD IOPS tersaturasi 100% karena puluhan koneksi konkuren melakukan *disk-spill* secara bersamaan.

### Solusi Arsitektural & Eksekusi

JANGAN menaikkan `work_mem` secara global pada level `postgresql.conf`! Jika `max_connections = 1000` dan `work_mem = 512MB`, database rentan terkena Linux OOM-Killer ($1000 \times 512\text{MB} = 512\text{GB}$ potensial alokasi).

Terapkan alokasi dinamis berbasis role atau level sesi:
```sql
-- 1. Ubah konfigurasi khusus untuk role background batch reconciliation
ALTER ROLE reconciliation_worker SET work_mem = '512MB';

-- 2. Terapkan settings cost hardware realistis untuk arsitektur Storage NVMe Enterprise
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET seq_page_cost = 1.0;
ALTER SYSTEM SET effective_io_concurrency = 200;

-- 3. Reload konfigurasi engine tanpa downtime
SELECT pg_reload_conf();

-- 4. Buat covering composite index untuk mengeliminasi hash join table accounts
CREATE INDEX CONCURRENTLY idx_accounts_active_covering 
ON accounts (account_id) 
INCLUDE (account_tier) 
WHERE status = 'ACTIVE';
```

### Hasil Pasca Mitigasi:
- `Batches: 1` (In-memory Hash Table, 0 blocks written to temporary files).
- Query latency p99 turun drastis dari 45 detik menjadi **180 millisecond**.
- Database CPU load stabil di 22%.

---

## 9. Trade-offs

| Parameter / Arsitektur | Keuntungan | Biaya / Konsekuensi Negatif | Skenario Rekomendasi |
| :--- | :--- | :--- | :--- |
| **Tinggi `work_mem`** | Mencegah hash & sort spill ke disk; mempercepat join kompleks & grouping. | Risiko tinggi terkena *OOM-Killer* jika konkurensi query meningkat drastis. | Atur per sesi / user batch jobs, bukan global. |
| **`random_page_cost = 1.1`** | Memaksa planner menggunakan Index Scan pada arsitektur SSD/NVMe modern. | Planner enggan melakukan Parallel Seq Scan pada batch extraction berskala masif. | Lingkungan cloud modern dengan IOPS storage terdedikasi. |
| **Extended Statistics** | Meningkatkan akurasi estimasi pada kueri multivariat dan composite joins. | Memperlambat durasi runtime `ANALYZE` dan konsumsi storage katalog meningkat. | Kolom dengan relasi fungsional tinggi di tabel berukuran > 10M rows. |
| **JIT Compilation Enabled** | Optimasi CPU intensif pada pelaporan/analytical query yang berlangsung lama. | Menambah overhead latensi 50-200ms untuk inisialisasi query OLTP cepat. | Nonaktifkan (`jit = off`) untuk sistem perbankan / OLTP murni. |
| **`default_statistics_target` (Tinggi, misal 500-1000)** | Histogram distribusi data jauh lebih akurat; menekan kesalahan kardinalitas. | Durasi eksekusi maintenance `VACUUM ANALYZE` membengkak signifikan. | Data warehouse / reporting read-heavy tables. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Fatal 1: Blind Global `work_mem` Increase
- **Anti-Pattern**: Menetapkan `work_mem = '2GB'` di `postgresql.conf` dengan `max_connections = 500`.
- **Dampak**: Satu query dengan 4 hash nodes dan 2 sort nodes akan mengalokasikan $6 \times 2\text{GB} = 12\text{GB}$ memori virtual. Beberapa concurrent request akan memicu OOM Killer dan mematikan daemon PostgreSQL (`SIGKILL`).
- **Solusi**: Gunakan formula:
  $$\text{Safe Global work\_mem} \approx \frac{\text{Tersedia RAM} - \text{shared\_buffers}}{(\text{max\_connections} \times \text{Rata-rata Active Joins per Query} \times 1.5)}$$

### Kesalahan Fatal 2: Mengabaikan JIT Overhead pada OLTP
- **Anti-Pattern**: Membiarkan parameter default PostgreSQL 12+ (`jit = on`, `jit_above_cost = 100000`).
- **Dampak**: Query dengan cost 105000 memakan waktu 80ms untuk parsing dan JIT LLVM compilation, padahal eksekusi murninya hanya 5ms.
- **Deteksi**:
```
JIT:
  Functions: 8
  Options: Inlining true, Optimization true, Expressions true, Deforming true
  Timing: Generation 3.210 ms, Inlining 25.402 ms, Optimization 45.102 ms, Emission 18.201 ms, Total 91.915 ms
Execution Time: 96.220 ms
```
- **Solusi**: Matikan JIT untuk sistem OLTP berlatensi rendah:
```sql
ALTER SYSTEM SET jit = off;
SELECT pg_reload_conf();
```

---

## 11. Best Practices (Production Checklist)

- [ ] **Hardware Alignment**:
  - `random_page_cost` diatur ke `1.1` - `1.2` untuk NVMe / EBS gp3 / io2.
  - `effective_io_concurrency` diatur antara `200` hingga `1000` (bergantung storage pool depth).
- [ ] **Memory Tuning**:
  - `work_mem` global tetap konservatif (`16MB` - `64MB`).
  - Dedicated worker/analytics user diberikan alokasi memori dinamis (`SET work_mem = '1GB'`).
- [ ] **Statistics Management**:
  - Tabel dengan korelasi tinggi dikonfigurasi menggunakan `CREATE STATISTICS (dependencies, ndistinct, mcv)`.
  - Naikkan target statistik spesifik kolom (bukan global): `ALTER TABLE tbl ALTER COLUMN col SET STATISTICS 500;`.
- [ ] **Monitoring Plan Health**:
  - Pasang extension `pg_stat_statements` untuk mendeteksi *high standard deviation time* yang mengindikasikan ketidakstabilan execution plan.
  - Aktifkan `log_min_duration_statement` dan log buffers (`log_parameter_max_length_on_first_error`).

---

## 12. Hands-on Practice

Simpan seluruh file praktikum pada direktori: `hands-on/m02/`

### File: `hands-on/m02/01_reproduce_spill.sql`
```sql
-- Eksperimen pembuktian Memory Spill Hash Join ke Disk
BEGIN;
CREATE SCHEMA IF NOT EXISTS lab_cbo;
SET search_path TO lab_cbo, public;

DROP TABLE IF EXISTS large_fact CASCADE;
DROP TABLE IF EXISTS small_dim CASCADE;

CREATE TABLE small_dim AS
SELECT 
    id AS dim_id, 
    'Category ' || (id % 100) AS category,
    md5(random()::text) AS description
FROM generate_series(1, 50000) id;

CREATE TABLE large_fact AS
SELECT 
    id AS fact_id,
    (random() * 49999 + 1)::int AS dim_id,
    random() * 1000 AS transaction_value,
    clock_timestamp() AS recorded_at
FROM generate_series(1, 1000000) id;

CREATE INDEX idx_dim_id ON small_dim(dim_id);
CREATE INDEX idx_fact_dim_id ON large_fact(dim_id);
ANALYZE small_dim;
ANALYZE large_fact;

-- Skenario A: work_mem rendah (Disk Spill Terjadi)
SET work_mem = '1MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT d.category, AVG(f.transaction_value)
FROM large_fact f
JOIN small_dim d ON f.dim_id = d.dim_id
GROUP BY d.category;

-- Skenario B: work_mem terkalibrasi (In-Memory Processing)
SET work_mem = '64MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT d.category, AVG(f.transaction_value)
FROM large_fact f
JOIN small_dim d ON f.dim_id = d.dim_id
GROUP BY d.category;

COMMIT;
```

### File: `hands-on/m02/02_multivariate_stats.sql`
```sql
-- Eksperimen pembuktian Extended Statistics
BEGIN;
CREATE SCHEMA IF NOT EXISTS lab_cbo;
SET search_path TO lab_cbo, public;

DROP TABLE IF EXISTS correlated_geo CASCADE;

CREATE TABLE correlated_geo (
    id SERIAL PRIMARY KEY,
    province_id INT,
    city_id INT,
    postal_code INT,
    metric_val NUMERIC
);

-- City_id strictly berkorelasi dengan province_id
INSERT INTO correlated_geo (province_id, city_id, postal_code, metric_val)
SELECT 
    p AS province_id,
    (p * 10) + (random() * 3)::int AS city_id,
    (p * 1000) + (random() * 50)::int AS postal_code,
    random() * 100
FROM generate_series(1, 100) p,
     generate_series(1, 10000) row_count;

ANALYZE correlated_geo;

-- Benchmark SEBELUM Extended Statistics
EXPLAIN (ANALYZE, TIMING FALSE)
SELECT * FROM correlated_geo 
WHERE province_id = 5 AND city_id = 51;

-- Penerapan Extended Stats
CREATE STATISTICS stat_geo_hierarchy ON province_id, city_id FROM correlated_geo;
ANALYZE correlated_geo;

-- Benchmark SESUDAH Extended Statistics
EXPLAIN (ANALYZE, TIMING FALSE)
SELECT * FROM correlated_geo 
WHERE province_id = 5 AND city_id = 51;

COMMIT;
```

---

## 13. Exercise

### Level Easy
Terdapat query sorting yang menghasilkan output `Sort Method: external merge Disk: 15320kB`. Ubah parameter level transaksi/sesi untuk query tersebut agar sorting berlangsung secara in-memory menggunakan `quicksort` tanpa mengubah `postgresql.conf` global.

### Level Medium
Sebuah tabel partisi berbasis waktu `events_partitioned` memiliki 12 partisi bulanan. Saat menjalankan query dengan predikat `WHERE event_timestamp >= '2023-05-01' AND event_timestamp < '2023-06-01'`, periksa rencana query. Jika CBO tetap melakukan scan pada semua partisi, telusuri parameter apa yang salah konfigurasi (`enable_partition_pruning`, immutable functions, atau type mismatch casting) dan buat script perbaikannya.

### Level Hard
Diberikan query laporan agregasi kompleks yang menggabungkan 14 tabel (`orders`, `line_items`, `customers`, `warehouses`, `suppliers`, dsb).
1. Amati bagaimana waktu yang dibutuhkan oleh tahap `Planning Time` melesat melebihi `Execution Time`.
2. Lakukan tuning bertingkat menggunakan modifikasi `join_collapse_limit`, `from_collapse_limit`, dan `geqo_threshold`.
3. Analisis pada titik ambang batas berapa Genetic Algorithm (GEQO) menghasilkan query plan sub-optimal jika dibandingkan dengan Dynamic Programming Exhaustive Search. Tuliskan metodologi pembuktian matematisnya berbasis cost.

---

## 14. Challenge

Rancang arsitektur sistem otomatis mitigasi regresi kueri (*Automated Query Plan Regression Detection Engine*) untuk klaster PostgreSQL enterprise (Zero Third-Party Commercial Tool):
1. **Mekanisme Deteksi**: Buat script background worker (menggunakan Python atau bash daemon) yang membaca ringkasan data dari `pg_stat_statements` untuk mengisolasi query yang memiliki deviasi performa drastis:
   $$\frac{\text{stddev\_exec\_time}}{\text{mean\_exec\_time}} > 3.0 \quad \text{dengan} \quad \text{calls} > 5000$$
2. **Karantina Otomatis**: Jika query regresi terdeteksi akibat perubahan cardinality estimasi yang mendadak, bagaimana prosedur automated schema fix dieksekusi secara atomik (misal: trigger `ANALYZE` terisolasi atau inject extended statistics secara dinamis)?
3. **Guardrails**: Rancang limitasi fail-safe agar skrip mitigasi otomatis tersebut tidak memicu starvation pada lock catalog database (`AccessExclusiveLock` vs `ShareUpdateExclusiveLock`).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (5 Pertanyaan)
1. Apa arti unit dasar angka pada estimasi `cost=100.50..250.80` dalam output `EXPLAIN` PostgreSQL?
2. Parameter konfigurasi manakah yang menentukan biaya eksekusi untuk satu kali pembacaan buffer page dari disk yang bersifat acak (non-sequential)?
3. Mengapa eksekusi `ANALYZE` pada PostgreSQL tidak mengunci operasi pembacaan (`SELECT`) dan penulisan (`INSERT`/`UPDATE`) pada tabel?
4. Apa perbedaan mendasar antara representasi node `Hash Join` vs `Merge Join` dalam hal persyaratan urutan data input?
5. Mengapa penggunaan JIT compilation justru menurunkan throughput performa pada query transaksi microservice OLTP standar?

### Bagian B: Intermediate (5 Pertanyaan)
1. Mengapa keberadaan index B-Tree tidak menjamin CBO akan selalu memilih `Index Scan`, dan pada kondisi apa CBO justru lebih memprioritaskan `Bitmap Heap Scan` atau `Seq Scan`?
2. Bagaimana mekanisme internal PostgreSQL membedakan eksekusi `Compile-time Partition Pruning` dengan `Run-time Partition Pruning`?
3. Apa perbedaan tipe statistik `dependencies` dan `mcv` pada fitur multivariate `CREATE STATISTICS`?
4. Mengapa setting `work_mem` dialokasikan per-*operation node* dan bukan per-koneksi client? Sebutkan dampaknya terhadap query dengan banyak join dan sort!
5. Bagaimana korelasi antara parameter `effective_cache_size` dengan keputusan CBO dalam memilih akses index scan? Apakah parameter tersebut mengalokasikan memori nyata di RAM?

### Bagian C: Skenario Kasus Produksi (3 Pertanyaan)

#### Kasus 1: Anomali Parameter Sniffing pada Prepared Statement
Aplikasi backend Golang menggunakan database pooler dengan `PREPARE statement`. Eksekusi query pertama hingga kelima berlangsung cepat (2ms), namun pada eksekusi keenam dan seterusnya latensi mendadak melonjak menjadi 1500ms.
- **Pertanyaan**: Jelaskan fenomena internal apa yang terjadi pada PostgreSQL planner (*Custom Plan* vs *Generic Plan*) dan parameter apa yang harus dimodifikasi untuk menstabilkan performa!

#### Kasus 2: Insiden Hash Join OOM Spilling
Pada dashboard monitoring Prometheus/Grafana, metrik Disk I/O Write meningkat tajam secara berkala setiap jam 12 malam, bersamaan dengan melonjaknya latency query settlement. Setelah diperiksa melalui `EXPLAIN (BUFFERS)`, query tersebut memuat informasi: `Buckets: 65536 Batches: 128 Memory Usage: 32768kB`.
- **Pertanyaan**: Jelaskan arti metrik `Batches: 128` tersebut, apa dampak fisik ke storage tier, dan berikan panduan kalkulasi matematis alokasi `work_mem` baru agar eksekusi tuntas pada `Batches: 1`!

#### Kasus 3: Data Skewness Akibat Soft Deletes
Sebuah tabel `tickets` memiliki 50 juta baris di mana kolom `is_deleted` bernilai `true` sebanyak 99.8% dan `false` sebanyak 0.2%. Query pemrosesan data aktif selalu memfilter `WHERE is_deleted = false`. Terjadi degradasi di mana planner selalu memilih `Seq Scan` dan mengabaikan index yang ada pada kolom `is_deleted`.
- **Pertanyaan**: Mengapa default histogram CBO gagal menangani skewness ekstrem seperti ini, dan bagaimana solusi arsitektural pengindeksan yang paling efisien (hemat storage dan zero misestimation)?

---

## 16. Summary

- **Cost-Based Optimizer (CBO)** PostgreSQL adalah mesin kalkulasi matematika probabilistik yang bekerja atas dasar konstanta biaya CPU dan I/O, serta katalog statistik distribusi tuple.
- **Kelemahan Inheren Asumsi Independensi**: CBO secara default mengasumsikan antar-kolom tidak berkorelasi. Untuk data dunia nyata yang berelasi erat, DBA wajib mengimplementasikan **Extended Statistics** guna menghindari kesalahan estimasi kardinalitas yang berujung pada pemilihan join plan yang lambat.
- **Join Strategy & Resource Scaling**:
  - `Nested Loop`: Efisien untuk skenario baris outer sedikit dan inner terindeks.
  - `Hash Join`: Efisien untuk dataset besar tanpa urutan, namun sensitif terhadap batasan `work_mem`. Terjadinya disk-spill (`Batches > 1`) adalah penyebab umum tingginya I/O wait pada database storage.
  - `Merge Join`: Efisien jika dataset masif telah terurut sebelumnya oleh index B-Tree.
- **Modern Hardware Alignment**: Nilai default historis PostgreSQL (seperti `random_page_cost = 4.0`) tidak dirancang untuk NVMe SSD. DBA modern harus merekalibrasi cost parameters agar planner dapat memaksimalkan performa query.
- **Plan Stability vs JIT**: Hindari mengaktifkan JIT pada sistem transaksi high-throughput berlatensi rendah (<10ms). Gunakan tools monitoring telemetri query execution time deviasi (`pg_stat_statements`) sebagai strategi proaktif mendeteksi regresi performa sebelum berdampak luas pada sistem produksi.