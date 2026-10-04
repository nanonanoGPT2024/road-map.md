# Bab 08: Query Optimizer, Execution Plans & Performance Profiling
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. Membedah arsitektur internal Cost-Based Optimizer (CBO), termasuk eksplorasi ruang status (*join permutation space*), evaluasi kalkulasi biaya (*cost estimation formula*), serta mekanisme *cardinality estimation* berbasis statistik dan histogram.
2. Menganalisis dan mendiagnosis *execution plan* secara komprehensif menggunakan metrik I/O tingkat rendah (*shared buffers*, *temp disk spills*, *WAL usage*, dan *JIT compilation overhead*).
3. Mengidentifikasi kelemahan runtime pada algoritma join fisik (*Nested Loop*, *Hash Join*, *Merge Join*) serta mengevaluasi strategi mitigasi skenario *skewness data*.
4. Merancang arsitektur telemetri performa kueri menggunakan `pg_stat_statements`, *extended statistics*, dan *plan stability management* guna mencegah regresi kueri pada lingkungan produksi multi-terabyte berkonkurensi tinggi.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
* Fundamental SQL DDL/DML dan arsitektur database relasional (ACID, MVCC, transaction isolation).
* Konsep dasar struktur data indeks: B-Tree, Hash, GiST/SP-GiST, dan GIN.
* Pemahaman fundamental mengenai parsing query SQL, pemetaan relasi logis (*Abstract Syntax Tree*), dan pembacaan *Execution Plan* dasar (`EXPLAIN`).
* Pemahaman sistem operasi terkait paging memori kernel, I/O buffers, disk page reads (random vs. sequential access), serta sistem *concurrency* threading/process.

---

### 3. Concept & Internal Architecture

Proses optimasi kueri pada Relational Database Management System (RDBMS) enterprise modern (seperti PostgreSQL dan MySQL 8+) bekerja dengan mentransformasikan representasi deklaratif SQL menjadi representasi prosedural paling efisien.

```
+-----------------------------------------------------------------------------+
|                          DATABASE ENGINE PIPELINE                           |
+-----------------------------------------------------------------------------+
 SQL Query Text 
       │
       ▼
 [ SQL Parser ] ────> AST (Abstract Syntax Tree)
       │
       ▼
 [ Analyzer/Catalog ] ───> Query Tree (Semantic Analysis & Type Checking)
       │
       ▼
 [ Rewriter Engine ] ───> Rewritten Query Tree (View Expansion & Rule System)
       │
       ▼
 [ Cost-Based Optimizer (CBO) ]
    ├─ Path Generator (Scan, Join, Aggregation Paths)
    ├─ Statistics Engine (pg_statistic, Histograms, MCV, Extended Stats)
    ├─ Equivalence Classes & Pathkeys (Ordering tracking)
    └─ Cost Estimator (cpu_tuple_cost, seq_page_cost, random_page_cost)
       │
       ▼
  Selected Execution Plan (Physical Plan Node Tree)
       │
       ▼
 [ Execution Engine (Volcano Iterator / Vectorized / JIT) ]
       │
       ▼
  Storage Engine (Buffer Pool / Heap / Indexes / OS Page Cache)
```

#### A. Mesin Estimasi Biaya (Cost Estimation Mechanics)
Formula matematis biaya total ($C_{total}$) pada CBO ditentukan oleh penjumlahan biaya startup ($C_{start}$) dan biaya run ($C_{run}$):

$$C_{total} = C_{start} + C_{run}$$

Di mana biaya pemrosesan fisik mencakup kombinasi I/O disk dan konsumsi CPU:

$$Cost = (N_{pages\_seq} \times \text{seq\_page\_cost}) + (N_{pages\_rnd} \times \text{random\_page\_cost}) + (N_{tuples} \times \text{cpu\_tuple\_cost}) + (N_{operators} \times \text{cpu\_operator\_cost})$$

Nilai default tipikal pada PostgreSQL:
* `seq_page_cost` = $1.0$ (baseline sequential read)
* `random_page_cost` = $4.0$ (HDD legacy) atau $1.1$ - $1.5$ (NVMe SSD enterprise)
* `cpu_tuple_cost` = $0.01$ (biaya pemrosesan satu baris di memori)
* `cpu_index_tuple_cost` = $0.005$ (biaya evaluasi entri indeks)
* `cpu_operator_cost` = $0.0025$ (biaya evaluasi fungsi/operator WHERE clause)

#### B. Anatomi Histogram dan Extended Statistics
CBO sangat bergantung pada katalog data statistik (`pg_statistic` di PostgreSQL, `mysql.innodb_table_stats` di MySQL). Komponen inti estimasi selektivitas meliputi:
1. **Most Common Values (MCV) & Frequencies (MCF):** Menangani nilai data diskrit yang mendominasi tabel.
2. **Equi-depth Histograms:** Membagi rentang nilai data menjadi bin dengan jumlah tuple yang sama per bin.
3. **Correlation:** Menilai korelasi fisik urutan baris di heap disk terhadap urutan logis nilai kolom. Semakin dekat nilainya ke $+1.0$ atau $-1.0$, semakin murah biaya *Index Scan* dibandingkan *Bitmap Index Scan*.
4. **Multivariate Dependencies & Cross-Column Correlation:** Masalah klasik *attribute value independence* terjadi saat klausa WHERE memfilter dua kolom yang saling bergantung (contoh: `country = 'ID' AND city = 'Jakarta'`). Formula independensi naif menghitung:

$$P(A \cap B) = P(A) \times P(B)$$

Hal ini menyebabkan *underestimation* kardinalitas yang drastis. Penanggulangannya adalah mengimplementasikan **Extended Statistics** (storable via `CREATE STATISTICS`), yang menghitung $N$-distinct multikolom dan koefisien dependensi fungsional nyata.

#### C. Join Permutation Space & Algoritma Heuristik
Untuk $N$ relasi yang di-join, jumlah kemungkinan urutan join bertumbuh secara faktorial/eksponensial:

$$\frac{(2N - 2)!}{(N - 1)!}$$

1. **Dynamic Programming (Bottom-Up Search):** Digunakan ketika $N \le \text{geqo\_threshold}$ (default PostgreSQL: 12 tabel). Menjamin ditemukannya *globally optimal plan*.
2. **Genetic Query Optimizer (GEQO):** Diterapkan ketika $N > \text{geqo\_threshold}$. Menggunakan algoritma stokastik genetika untuk menukar kromosom (order relasi) guna mencegah kehabisan memori (*out-of-memory*) dan latensi optimasi yang tidak terhingga saat kompilasi kueri.

#### D. Physical Join Operators
1. **Nested Loop Join:**
   * Outer loop iterasi setiap baris, inner loop mencari kecocokan.
   * Efisien jika: Outer set sangat kecil ($\le 100$ baris) dan inner set memiliki B-Tree Index lookup ($O(\log N)$).
2. **Hash Join:**
   * Fase 1 (*Build*): Membaca seluruh baris inner relation dan memetakan ke Hash Table di memori (`work_mem`).
   * Fase 2 (*Probe*): Membaca outer relation baris per baris dan memindai hash table untuk mencari *hash match*.
   * Membengkak menjadi *Multi-batch Hash Join* (spill ke disk) jika ukuran hash table melampaui `work_mem`.
3. **Merge Join:**
   * Memerlukan kedua set input sudah terurut berdasarkan join key (baik dari Index Scan atau operator Sort eksplisit).
   * Kompleksitas $O(M + N)$ skenario skalar, efisien untuk dataset raksasa di mana hash table tidak muat di RAM.

---

### 4. Why & What

| Dimensi | Pendekatan Reaktif / Naif | Pendekatan Enterprise Berbasis Execution Profiling |
| :--- | :--- | :--- |
| **Penyelesaian Masalah** | Menambahkan indeks B-tree secara acak setiap kueri lambat dilaporkan. | Membaca trace eksekusi mendalam (buffer reads, memory spills, selektivitas). |
| **Penanganan Skala** | Bergantung pada asumsi default engine database tanpa penyesuaian hardware. | Tuning parameter CBO berbasis latensi disk nyata (SSD/NVMe vs HDD) dan I/O path. |
| **Korelasi Data** | Membiarkan optimizer salah menduga kardinalitas kolom berelasi. | Mengaktifkan Extended Statistics untuk mempertahankan akurasi estimasi cardinality. |
| **Manajemen Memori** | Mengandalkan nilai `work_mem` default global yang memicu disk spill masif. | Segmentasi alokasi memori dinamis per-sesi/per-kueri dan pemantauan `HashJoin` batching. |
| **Stabilitas Eksekusi** | Rentan terhadap bencana *Plan Regression* pasca vacuum atau load data masif. | Memetakan dan mengunci stabilitas plan (*Plan Baselines*, plan fingerprinting). |

Kegagalan memahami CBO di tingkat internal berujung pada malapetaka operasional: kueri analitik yang biasanya berjalan 50 milidetik dapat mendadak beralih dari *Hash Join* ke *Nested Loop with Sequential Scan*, menguras seluruh I/O IOPS database, memicu *connection pool exhaustion*, dan melumpuhkan sistem produksi secara kaskade.

---

### 5. How (Workflow Detail)

Alur kerja audit, profiling, dan remediasi eksekusi kueri di skala enterprise diilustrasikan dalam langkah berikut:

```
[ IDENTIFIKASI ]
      │  Query tercatat lambat di pg_stat_statements (high mean_exec_time / high temp_blks)
      ▼
[ PROFILING ]
      │  Jalankan: EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL) <QUERY>
      ▼
[ EVALUASI KARDINALITAS ]
      │  Bandingkan `rows=X` (estimasi) vs `actual rows=Y` (kenyataan)
      ├─ Selisih > 10x? ───> [ STALE STATS / CORRELATION ISSUE ]
      │                            │
      │                            ├──> Jalankan ANALYZE target_table
      │                            └──> Buat Extended Statistics (CREATE STATISTICS)
      ▼
[ ANALISIS BUFFER & RESOURCE ]
      │  Hitung: Shared Hit vs Shared Read (Buffer Cache Hit Ratio)
      │  Deteksi: "Disk: spilled to disk" atau "Batches: > 1" pada Hash Join / Sort
      ├─ Terjadi disk spill? ───> [ MEMORY INSUFFICIENCY ]
      │                            │
      │                            └──> Tingkatkan work_mem pada tingkat sesi/transaksi
      ▼
[ EVALUASI STRUKTURAL ACCESS PATH ]
      │  Apakah terjadi Seq Scan pada tabel multi-juta baris?
      │  Apakah operator Nested Loop memproses jutaan baris loop?
      ├─ Salah operator? ───> [ INDEXING & TUNING ]
      │                            │
      │                            ├──> Buat Index komposit (filter + join keys)
      │                            ├──> Evaluasi parameter cost (random_page_cost)
      │                            └──> Tulis ulang klausa non-sargable
      ▼
[ VERIFIKASI AKHIR ]
         Jalankan kembali profiling; pastikan 0 temp disk blocks dan eksekusi sub-second.
```

---

### 6. Analogy & Diagram ASCII

Bayangkan Anda adalah seorang manajer logistik distribusi barang yang harus mencari 100 paket pesanan dari gudang penyimpanan berisi 10.000.000 barang.

*   **Sequential Scan:** Anda berjalan menyusuri setiap lorong rak gudang dari nomor 1 sampai 10.000.000 secara linier. Sangat lambat jika Anda hanya mencari 2 paket, tetapi efisien jika Anda harus mengambil 8.000.000 paket sekaligus.
*   **Index Scan:** Anda melihat buku katalog (B-Tree Index) untuk mengetahui lokasi persis rak barang, lalu Anda berjalan bolak-balik mengambil barang tersebut secara acak. Sangat cepat jika mengambil 5 paket, namun sangat melelahkan (tinggi *Random I/O*) jika harus mengambil 3.000.000 paket.
*   **Bitmap Index Scan:** Anda memeriksa buku katalog, mencatat semua nomor rak pada selembar kertas, mengurutkan nomor rak tersebut dari terkecil ke terbesar, lalu berjalan satu arah di gudang menyusuri rak yang telah ditandai saja.
*   **Hash Join vs Spill to Disk:** Anda membawa meja lipat (`work_mem`) untuk mencocokkan data. Jika barangnya sedikit, semua ditaruh di meja dalam satu waktu (*Single-Batch Hash Join*). Jika mejanya kekecilan, Anda harus membagi barang menjadi beberapa kloter, menaruh sisa barang di lantai/gudang transit (*Spill to Temporary File on Disk*), lalu bolak-balik membersihkan meja berulang kali.

```
       WORK_MEM CUKUP (Optimal)            WORK_MEM KURANG (Spill to Disk)
    +-----------------------------+     +-----------------------------+
    |         RAM BUFFER          |     |         RAM BUFFER          |
    |  +-----------------------+  |     |  +-----------------------+  |
    |  | Hash Table (Batch 1)  |  |     |  | Hash Table (Batch 1)  |  |
    |  | 100% Data Muat di RAM |  |     |  | Sebagian Data Saja    |  |
    |  +-----------------------+  |     |  +-----------------------+  |
    +-----------------------------+     +--------------┬--------------+
                  │                                    │ Batches: 4
                  │ Fast In-Memory                     ▼ Spilled to Disk
                  ▼ Lookup              +-----------------------------+
             [ Result ]                 |     TEMPORARY DISK FILE     |
                                        | (High Latency SSD/HDD I/O)  |
                                        +-----------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Basic Plan Inspection
Mengeksekusi analisis plan standar pada PostgreSQL:

```sql
-- Query sederhana dengan explain standar
EXPLAIN ANALYZE 
SELECT customer_id, SUM(total_amount)
FROM orders
WHERE created_at >= '2023-01-01' 
GROUP BY customer_id;
```

#### B. Enterprise Production Profiling (Lanjutan)
Menggunakan opsi lengkap untuk membedah I/O, Buffer, Spills, dan Engine Costing:

```sql
-- Konfigurasi debug level untuk profiling lokal
SET track_io_timing = ON;

EXPLAIN (
    ANALYZE,    -- Menjalankan kueri nyata dan menampilkan waktu runtime aktual
    BUFFERS,    -- Menampilkan hitungan page buffer (shared hit, read, dirtied, written)
    TIMING,     -- Menampilkan engine node startup dan total execution time
    COSTS,      -- Menampilkan estimasi biaya planner minimum/maksimum
    VERBOSE,    -- Menampilkan target list kolom, engine alias, dan internal stats
    WAL,        -- Menampilkan statistik penggunaan Write-Ahead Logging
    SETTINGS    -- Menampilkan konfigurasi parameter optimizer non-default
)
SELECT 
    c.country_code,
    o.fulfillment_status,
    COUNT(o.order_id) AS total_orders,
    SUM(o.total_amount) AS aggregate_spend,
    AVG(p.payment_processing_ms) AS avg_payment_latency
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
LEFT JOIN payments p ON o.order_id = p.order_id
WHERE c.is_enterprise = TRUE
  AND o.created_at >= TIMESTAMPTZ '2024-01-01 00:00:00 UTC'
  AND o.created_at <  TIMESTAMPTZ '2024-04-01 00:00:00 UTC'
GROUP BY c.country_code, o.fulfillment_status
ORDER BY aggregate_spend DESC;

RESET track_io_timing;
```

**Membaca Output Eksekusi Buffers:**
```text
GroupAggregate  (cost=14205.12..14250.45 rows=245 width=48) (actual time=142.120..148.330 rows=18 loops=1)
  Output: c.country_code, o.fulfillment_status, count(o.order_id), sum(o.total_amount), avg(p.payment_processing_ms)
  Group Key: c.country_code, o.fulfillment_status
  Buffers: shared hit=8420 read=1240, temp read=340 written=345
  ->  Sort  (cost=14205.12..14212.18 rows=2824 width=40) (actual time=141.980..143.110 rows=2824 loops=1)
        Sort Key: c.country_code, o.fulfillment_status
        Sort Method: external merge  Disk: 2760kB  <--- PERINGATAN: DISK SPILL!
        Buffers: shared hit=8420 read=1240, temp read=340 written=345
        ->  Hash Join  (cost=4321.00..14041.50 rows=2824 width=40) (actual time=45.100..132.800 rows=2824 loops=1)
...
```

*Analisis:* `Sort Method: external merge Disk: 2760kB` menandakan `work_mem` tidak cukup untuk menampung data sort di RAM, sehingga engine menulis data sementara ke piringan disk (`temp read=340 written=345`). Solusi: naikkan alokasi `work_mem` untuk sesi tersebut.

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
* Sistem: Core Payment Engine pada Financial Technology.
* Skala Data: 400 Juta Baris Transaksi (`transactions`), bertambah 1,5 juta baris per hari.
* Database: Dedicated PostgreSQL 15, 64 vCPU, 256 GB RAM, High-Performance NVMe SSD Storage (IOPS 80,000).

#### Masalah: Latensi P99 Melompat dari 35ms ke 14 Detik
Query API reporting berkala mendadak menyebabkan CPU load server melonjak hingga 100%.

```sql
-- Query Masalah
SELECT 
    t.merchant_id,
    COUNT(t.id) as tx_count,
    SUM(t.settlement_amount) as total_settled
FROM transactions t
WHERE t.merchant_category = 'DIGITAL_SERVICES'
  AND t.status = 'SETTLED'
  AND t.created_at >= '2024-03-01' 
  AND t.created_at < '2024-03-02'
GROUP BY t.merchant_id;
```

#### Investigasi Execution Plan
Hasil `EXPLAIN (ANALYZE, BUFFERS)` mengungkap akar masalah:

```text
Bitmap Heap Scan on transactions t  (cost=1540.20..894500.12 rows=145 actual time=85.200..13824.110 rows=4850000 loops=1)
  Recheck Cond: ((created_at >= '2024-03-01'::timestamptz) AND (created_at < '2024-03-02'::timestamptz))
  Filter: ((merchant_category = 'DIGITAL_SERVICES'::text) AND (status = 'SETTLED'::text))
  Rows Removed by Filter: 12100000
  Buffers: shared hit=42100 read=684300
  ->  Bitmap Index Scan on idx_transactions_created_at  (cost=0.00..1540.10 rows=210000 actual time=62.400..62.400 rows=16950000 loops=1)
        Index Cond: ((created_at >= '2024-03-01'::timestamptz) AND (created_at < '2024-03-02'::timestamptz))
```

#### Identifikasi Kegagalan CBO
1. **Underestimation Kardinalitas:** Optimizer memproyeksikan `rows=145`, padahal data aktual adalah `rows=4,850,000` (error kalkulasi selektivitas sebesar ~33,400x).
2. **Korelasi Kolom Tidak Terdeteksi:** Kategori `DIGITAL_SERVICES` mayoritas langsung berstatus `SETTLED` secara instan dibanding kategori industri lain. Optimizer berasumsi kedua kondisi bersifat independen.
3. **Penyebab Biaya I/O Meledak:** Karena optimizer menduga baris yang lolos hanya 145 baris, ia memilih memindai indeks rentang tanggal tunggal (`idx_transactions_created_at`), lalu memfilter di level memori heap. Akibatnya, engine harus membaca 684.300 blok dari NVMe storage (`shared read=684300` setara dengan ~5.3 GB data kotor dibaca sia-sia hanya untuk membuang 12 juta baris).

#### Remediasi Arsitektur Produksi

*Langkah 1: Membuat Extended Multi-Column Statistics*
```sql
-- Mencegah independensi asumsif CBO pada kombinasi status dan kategori
CREATE STATISTICS stats_transactions_category_status 
ON merchant_category, status FROM transactions;

ANALYZE transactions;
```

*Langkah 2: Menyesuaikan Indeks Komposit Berbasis Skenario (Covering Index)*
Membuat Partial Index yang disesuaikan dengan pola akses transaksi stabil:
```sql
CREATE INDEX CONCURRENTLY idx_transactions_settled_digital_date
ON transactions (created_at, merchant_id, settlement_amount)
WHERE status = 'SETTLED' AND merchant_category = 'DIGITAL_SERVICES';
```

#### Hasil Eksekusi Pasca Mitigasi:
Plan beralih menggunakan **Index Only Scan**:
```text
GroupAggregate  (cost=125.40..342.10 rows=4820000 actual time=12.200..32.400 rows=4850000 loops=1)
  Buffers: shared hit=42150 read=12
  ->  Index Only Scan using idx_transactions_settled_digital_date on transactions t
        Index Cond: ((created_at >= '2024-03-01'::timestamptz) AND (created_at < '2024-03-02'::timestamptz))
```
*   Latensi eksekusi kueri anjlok dari **14 Detik** menjadi **32 Milidetik**.
*   Physical I/O Read terpangkas sebesar **99.99%** (`read=12` blok vs sebelumnya `read=684300` blok).

---

### 9. Trade-offs

```
                  PENYESUAIAN PENGATURAN PLANNER
                               
          Aggressive In-Memory                 Conservative
          (Tinggi work_mem,                   (Default work_mem,
           random_page_cost=1.1)              random_page_cost=4.0)
         ┌─────────────────────────┐         ┌─────────────────────────┐
         │ + Menghindari disk spill│         │ + Aman dari OOM Killer  │
 LATENCY │ + Memilih Index/Hash    │         │ + Stabil pada beban     │
         │ - Risiko OOM tinggi saat│         │   konkurensi ekstrem    │
         │   lonjakan koneksi      │         │ - Latensi query tinggi  │
         │   bersamaan             │         │   karena sering I/O disk│
         └─────────────────────────┘         └─────────────────────────┘
```

| Parameter/Keputusan | Keuntungan | Kerugian / Konsekuensi Negatif | Biaya Skalabilitas |
| :--- | :--- | :--- | :--- |
| **Peningkatan Ekstrem `work_mem`** | Mencegah hash join dan sorting menumpahkan data ke disk (external spill); menekan latensi kueri kompleks. | `work_mem` dialokasikan per node per kueri. Kueri dengan 5 node join dapat mengalokasikan $5 \times \text{work\_mem}$ per koneksi. Berisiko memicu kernel *OOM Killer*. | Skalabilitas konkurensi menurun tajam jika connection pool meluap. |
| **Menurunkan `random_page_cost` ($\approx 1.1$)** | Memaksa planner menggunakan indeks secara agresif, sangat ideal untuk enterprise storage NVMe modern. | Jika segmentasi data terfragmentasi berat di disk, planner dapat memilih index traversal yang justru lebih lambat dari linear scan. | Mengharuskan maintenance defragmentasi heap secara periodik. |
| **Extended Statistics Multikolom** | Mengeliminasi kesalahan estimasi selektivitas secara presisi; menghasilkan plan optimal. | Memperpanjang waktu eksekusi proses background `ANALYZE` dan meningkatkan ukuran penyimpanan katalog database. | Penurunan throughput penulisan pada tabel ber-turnover tinggi jika sampling stats terlalu granular. |
| **Mengaktifkan JIT Compilation (`jit=on`)** | Mempercepat CPU-bound queries yang melakukan evaluasi ekspresi dan agregasi jutaan baris. | Memperkenalkan startup overhead kompilasi (5-30ms). Sangat destruktif untuk kueri OLTP berlatensi rendah (< 2ms). | Menghabiskan resource CPU jika kueri pendek tidak sengaja memicu JIT. |

---

### 10. Common Mistakes & Troubleshooting

#### Skenario Kesalahan Riil

##### 1. Predikat Non-Sargable yang Mematikan Optimasi Indeks
*Gejala:* Kueri tetap menjalankan `Seq Scan` meski indeks B-tree sudah dibuat pada kolom yang dicari.
*Penyebab:* Penggunaan fungsi modifikasi pada kolom di dalam klausa `WHERE`.
```sql
-- BURUK (Non-Sargable): Kolom dibungkus fungsi; optimizer tidak dapat melintasi B-Tree
SELECT id, user_id FROM audit_logs WHERE DATE(created_at) = '2024-03-01';

-- BENAR (Sargable): Rentang literal terisolasi murni pada nilai parameter
SELECT id, user_id FROM audit_logs 
WHERE created_at >= '2024-03-01 00:00:00' 
  AND created_at <  '2024-03-02 00:00:00';
```

##### 2. Implicit Data Type Mismatch (Type Coercion)
*Gejala:* Kolom indeks varchar diabaikan saat filter perbandingan.
*Penyebab:* Mengirimkan literal angka ke kolom teks memicu fungsi konversi implisit:
```sql
-- BURUK: phone_number bertipe VARCHAR, dikirimkan integer numerik
SELECT * FROM users WHERE phone_number = 0811223344;
-- Optimizer mengubah internal AST menjadi: WHERE phone_number::bigint = 811223344; (Index Scan Batal!)

-- BENAR: Tipe data parameter sinkron dengan tipe data kolom
SELECT * FROM users WHERE phone_number = '0811223344';
```

##### 3. Outdated Table Statistics Pasca Operasi Data Masif
*Gejala:* Pasca proses *batch insertion* 10 juta baris data baru, performa query agregasi langsung drop drastis.
*Troubleshooting Runbook:*
```sql
-- Periksa kapan autovacuum/autoanalyze terakhir berjalan
SELECT 
    schemaname, 
    relname, 
    last_vacuum, 
    last_autovacuum, 
    last_analyze, 
    last_autoanalyze,
    n_dead_tup,
    n_live_tup
FROM pg_stat_user_tables
WHERE relname = 'transactions';

-- Paksa update sampling statistik segera
ANALYZE VERBOSE transactions;
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Query Validation
- [ ] Jalankan `EXPLAIN (ANALYZE, BUFFERS)` pada data staging berukuran representatif ($\ge 20\%$ volume data produksi).
- [ ] Validasi selisih kardinalitas: Pastikan nilai `rows=X` (estimasi) tidak menyimpang lebih dari $3\times$ lipat dari `actual rows=Y`.
- [ ] Pastikan tidak ada operator `Sort Method: external merge Disk` atau `HashBatch: Spilled to disk`.
- [ ] Pastikan perbandingan tipe data di klausa `WHERE` dan `JOIN` memiliki kompatibilitas identik (*strict type matching*).

#### Engine Tuning for NVMe/Cloud Database Instances
- [ ] Setel parameter `random_page_cost` antara `1.1` hingga `1.25` jika menggunakan EBS gp3, io2, atau Local NVMe SSD.
- [ ] Turunkan `seq_page_cost` ke `1.0` sebagai pembanding.
- [ ] Tetapkan `effective_io_concurrency = 200` (untuk SSD) guna mengizinkan pre-fetching asynchronous page buffer.
- [ ] Setel `work_mem` secara proporsional. Hindari penetapan global yang agresif:
  $$\text{work\_mem global} \le \frac{\text{Total RAM} \times 0.25}{\text{max\_connections} \times \text{avg\_concurrent\_joins}}$$

#### Runtime Production Monitoring
- [ ] Aktifkan modul ekstensi `pg_stat_statements`.
- [ ] Setel logging query lambat secara aman: `log_min_duration_statement = '250ms'`.
- [ ] Pantau kueri dengan rasio I/O disk tinggi:
```sql
SELECT 
    queryid,
    substr(query, 1, 60) AS query_sample,
    calls,
    mean_exec_time,
    (shared_blks_read::float / NULLIF(shared_blks_hit + shared_blks_read, 0)) * 100 AS disk_read_percentage
FROM pg_stat_statements
ORDER BY mean_exec_time DESC 
LIMIT 10;
```

---

### 12. Hands-on Practice

Buat dan simpan script implementasi berikut di: `hands-on/m02/deep_dive_profiling.sql`

```sql
-- ============================================================================
-- SCRIPT LATIHAN MANDIRI: Query Profiling, Execution Diagnostics & Extended Stats
-- File: hands-on/m02/deep_dive_profiling.sql
-- ============================================================================

BEGIN;

-- 1. Setup Sandbox Schema
CREATE SCHEMA IF NOT EXISTS lab_optimization;
SET search_path TO lab_optimization, public;

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;

-- 2. Setup DDL Struktur Relasi
CREATE TABLE products (
    product_id BIGSERIAL PRIMARY KEY,
    sku VARCHAR(64) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL,
    price NUMERIC(12, 2) NOT NULL
);

CREATE TABLE orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_tier VARCHAR(16) NOT NULL,
    order_status VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL
);

CREATE TABLE order_items (
    item_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(product_id),
    quantity INT NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL
);

-- 3. Injeksi Dataset Sintetis Berskala (Memperlihatkan Karakteristik CBO)
-- Injeksi 1.000 Produk
INSERT INTO products (sku, category, price)
SELECT 
    'SKU-' || seq || '-' || md5(seq::text),
    (ARRAY['ELECTRONICS', 'CLOTHING', 'HOME', 'BOOKS', 'TOYS'])[1 + (seq % 5)],
    (random() * 500 + 10)::numeric(12,2)
FROM generate_series(1, 1000) AS seq;

-- Injeksi 100.000 Orders dengan Korelasi Terselubung (Skewed Distribution)
-- Asumsi: Pelanggan 'PLATINUM' hampir selalu memiliki status 'COMPLETED'
INSERT INTO orders (customer_tier, order_status, created_at, total_amount)
SELECT 
    CASE 
        WHEN random() < 0.85 THEN 'PLATINUM'
        ELSE 'STANDARD'
    END AS tier,
    CASE 
        WHEN random() < 0.80 THEN 'COMPLETED'
        ELSE 'CANCELLED'
    END AS status,
    NOW() - (random() * interval '90 days'),
    0
FROM generate_series(1, 100000) AS seq;

-- Injeksi 300.000 Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT 
    1 + (random() * 99999)::bigint,
    1 + (random() * 999)::bigint,
    (random() * 5 + 1)::int,
    (random() * 100 + 5)::numeric(12,2)
FROM generate_series(1, 300000) AS seq;

-- Update Agregat Total Amount pada Parent Order
UPDATE orders o
SET total_amount = sub.calculated_total
FROM (
    SELECT order_id, SUM(quantity * unit_price) AS calculated_total
    FROM order_items
    GROUP BY order_id
) sub
WHERE o.order_id = sub.order_id;

-- Analisis Awal Tanpa Indeks Tambahan
ANALYZE products;
ANALYZE orders;
ANALYZE order_items;

COMMIT;

-- ============================================================================
-- EKSEKUSI DIAGNOSTIK
-- ============================================================================

-- Tes Skenario A: Deteksi Underestimation Kardinalitas Akibat Kolom Berelasi
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    customer_tier, 
    order_status, 
    COUNT(*) AS total_records
FROM orders
WHERE customer_tier = 'PLATINUM' AND order_status = 'COMPLETED'
GROUP BY customer_tier, order_status;

-- Solusi Masalah A: Membuat Extended Statistics
CREATE STATISTICS stats_orders_tier_status ON customer_tier, order_status FROM orders;
ANALYZE orders;

-- Verifikasi Ulang Perbaikan Estimasi Planner
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    customer_tier, 
    order_status, 
    COUNT(*) AS total_records
FROM orders
WHERE customer_tier = 'PLATINUM' AND order_status = 'COMPLETED'
GROUP BY customer_tier, order_status;

-- Tes Skenario B: Simulasi Memori Spill (work_mem disengaja rendah)
SET work_mem = '64kB';

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    p.category,
    SUM(oi.quantity * oi.unit_price) AS category_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.created_at >= NOW() - INTERVAL '30 days'
GROUP BY p.category
ORDER BY category_revenue DESC;

-- Remediasi Skenario B: Optimasi Memori dan Akses Indeks Komposit
RESET work_mem;
SET work_mem = '64MB';

CREATE INDEX idx_orders_created_at ON orders(created_at) INCLUDE (order_id);
CREATE INDEX idx_order_items_order_product ON order_items(order_id, product_id) INCLUDE (quantity, unit_price);

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    p.category,
    SUM(oi.quantity * oi.unit_price) AS category_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.created_at >= NOW() - INTERVAL '30 days'
GROUP BY p.category
ORDER BY category_revenue DESC;
```

---

### 13. Exercise

#### Level Easy
Kueri berikut memicu `Seq Scan` pada tabel `users` (1.000.000 baris) meski indeks telah dibuat pada kolom `email`:
```sql
CREATE INDEX idx_users_email ON users(email);
-- Query:
SELECT id, full_name FROM users WHERE LOWER(email) = 'john.doe@enterprise.com';
```
*Tugas:*
1. Jelaskan mengapa optimizer menolak menggunakan indeks `idx_users_email`.
2. Tuliskan modifikasi instruksi DDL pembuatan index yang tepat (*Functional Expression Index*) agar query menggunakan `Index Scan`.

#### Level Medium
Diberikan execution plan node berikut:
```text
->  Hash Join  (cost=1250.00..89000.00 rows=4000 width=32) (actual time=24.10..1890.30 rows=510000 loops=1)
      Hash Cond: (orders.customer_id = customers.id)
      Buffers: shared hit=4100 read=12800, temp written=12400 read=12400
```
*Tugas:*
1. Identifikasi dua masalah utama performa dari pembacaan log engine di atas.
2. Tuliskan urutan langkah teknis (konfigurasi atau kueri DDL/DML) untuk mengubah proses hash join tersebut agar berjalan *in-memory* sepenuhnya tanpa *disk spill*.

#### Level Hard
Sebuah kueri analitik melakukan `JOIN` pada 4 tabel raksasa: `ledger`, `accounts`, `branches`, dan `currencies`. 
Kueri memfilter transaksi pada tanggal tertentu di mana cabang beroperasi di zona waktu spesifik. 
Meskipun autovacuum aktif, optimizer selalu memilih urutan join yang keliru (memulai probe dari tabel `ledger` sebesar 200 juta baris menggunakan *Nested Loop*), yang mengakibatkan runtime kueri melampaui 120 detik.
*Tugas:*
1. Rancang arsitektur telemetri untuk membedah akar permasalahan selektivitas dan ekuivalensi kelas dari plan tersebut.
2. Formulasikan kombinasi manipulasi parameter CBO (`join_collapse_limit`, `from_collapse_limit`), penggunaan *Common Table Expressions* berstatus `MATERIALIZED`, atau implementasi *Extended Statistics* dependensi fungsional silang antar-tabel tanpa memodifikasi arsitektur physical sharding data.

---

### 14. Challenge

Anda adalah Principal Database Reliability Engineer pada platform *Ticketing Flash Sale*. 
Tabel `ticket_reservations` memiliki 50 juta baris dengan arsitektur indeks berikut:
*   Primary Key: `id` (BIGINT)
*   Index 1: `(event_id, status)`
*   Index 2: `(user_id)`
*   Index 3: `(created_at)`

Tepat pada jam 00:00 (event penjualan konser akbar dimulai), 20.000 worker backend serentak mengeksekusi kueri berikut secara konkuren:

```sql
SELECT id, reservation_token
FROM ticket_reservations
WHERE event_id = 9942
  AND status = 'PENDING'
  AND created_at <= NOW() - INTERVAL '10 minutes'
ORDER BY id ASC
FOR UPDATE SKIP LOCKED
LIMIT 50;
```

**Skenario Bencana:**
Dalam 30 detik pertama, latensi p99 database meroket dari 5ms ke 45 detik. CPU Database menyentuh 100%. Buffer hit ratio turun ke 40%. 
Saat dicek melalui runtime profiling, optimizer secara mendadak mengabaikan Indeks gabungan `(event_id, status)` dan justru beralih melakukan:
`Index Scan Backward using ticket_reservations_pkey on ticket_reservations` dengan status filter memory `Rows Removed by Filter: 12.000.000`.

**Tantangan Arsitektur:**
1. Bedah secara mekanis: Mengapa CBO memilih `Index Scan Backward` pada Primary Key dan memfilter jutaan baris di memori daripada menggunakan indeks gabungan spesifik event?
2. Bagaimana interaksi antara klausa `ORDER BY id ASC LIMIT 50` dan heuristic cost engine mempengaruhi kesalahan pengambilan keputusan planner?
3. Rancang arsitektur perbaikan menyeluruh (mencakup indexing strategy, penulisan kueri, parameter optimizer tuning, dan locking pattern) untuk memastikan pemrosesan antrean *SKIP LOCKED* ini tuntas dengan latensi di bawah 10ms secara konsisten pada beban konkurensi puncak, tanpa memicu table locking cascade.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan Pilihan Ganda)

1. Komponen optimizer manakah yang bertanggung jawab menghitung estimasi jumlah baris (*cardinality*) yang dihasilkan oleh suatu node eksekusi?
   * A. Parser
   * B. Rewriter Engine
   * C. Statistics Engine / Estimator
   * D. Volcano Iterator Executor

2. Parameter PostgreSQL apa yang merepresentasikan biaya relatif untuk membaca satu halaman disk (8KB page) secara acak (*random access*)?
   * A. `seq_page_cost`
   * B. `random_page_cost`
   * C. `cpu_tuple_cost`
   * D. `effective_cache_size`

3. Dalam pembacaan output `EXPLAIN (ANALYZE, BUFFERS)`, metrik manakah yang mengindikasikan blok data dibaca langsung dari memori RAM (database buffer pool) dan bukan dari physical storage?
   * A. `shared read`
   * B. `shared hit`
   * C. `shared dirtied`
   * D. `temp written`

4. Algoritma join fisik mana yang **wajib** memerlukan kedua set input data dalam kondisi terurut (*sorted*) berdasarkan join key?
   * A. Nested Loop Join
   * B. Hash Join
   * C. Merge Join
   * D. Broadcast Join

5. Apa dampak langsung memanggil fungsi SQL (contoh: `UPPER(customer_name) = 'ALICE'`) pada kolom yang memiliki B-Tree standard index?
   * A. Kueri gagal (*syntax error*).
   * B. B-Tree index tetap digunakan secara optimal.
   * C. Optimizer beralih ke Sequential Scan (non-sargable predicate).
   * D. Database otomatis membuat functional index temporer di RAM.

---

#### Bagian 2: Intermediate (5 Pertanyaan Pilihan Ganda)

1. Mengapa kompilasi Just-In-Time (`JIT`) bawaan PostgreSQL terkadang menyebabkan degradasi performa pada sistem transaksi OLTP?
   * A. JIT mengunci tabel secara eksklusif (*AccessExclusiveLock*).
   * B. Waktu overhead kompilasi kode native LLVM ($10 - 50\text{ ms}$) melampaui total waktu eksekusi kueri OLTP itu sendiri ($< 5\text{ ms}$).
   * C. JIT menonaktifkan penggunaan indeks B-tree secara paksa.
   * D. JIT memaksa seluruh alokasi memori beralih ke disk storage.

2. Kapan CBO PostgreSQL memutuskan untuk beralih dari algoritma *Dynamic Programming Join Search* ke *Genetic Query Optimizer (GEQO)*?
   * A. Ketika kapasitas memori RAM server tersisa di bawah 10%.
   * B. Ketika jumlah relasi/tabel yang di-join melampaui nilai ambang batas `geqo_threshold` (default: 12 tabel).
   * C. Ketika kueri mengandung klausa recursive CTE.
   * D. Ketika kueri dijalankan di dalam read-only transaction.

3. Apa implikasi struktural jika pada output `EXPLAIN` tertera informasi: `Sort Method: external merge Disk: 45000kB`?
   * A. Kapasitas harddisk database telah penuh 100%.
   * B. Ukuran memori `work_mem` tidak cukup menampung operasi sort, sehingga engine menumpahkan data sementara ke disk.
   * C. Indeks rusak (*corrupted*) dan memerlukan proses `REINDEX`.
   * D. Parameter `shared_buffers` terlalu besar dibanding ukuran RAM fisik.

4. Masalah estimasi apa yang dipecahkan oleh fitur **Extended Statistics** (`CREATE STATISTICS ... ON (col_a, col_b)`)?
   * A. Mencegah kueri mengalami deadlock.
   * B. Mengatasi kesalahan perhitungan selektivitas CBO yang mengasumsikan kolom-kolom independen secara murni (*Attribute Value Independence assumption*).
   * C. Menghapus kebutuhan maintenance `VACUUM ANALYZE`.
   * D. Mengompresi penyimpanan tabel fisik di level disk.

5. Jika nilai korelasi (*correlation*) pada `pg_stats` mendekati angka `+1.0`, tindakan optimasi apa yang paling diuntungkan?
   * A. Optimizer akan memprioritaskan *Index Scan* biasa daripada *Bitmap Index Scan*, karena lokasi baris fisik di heap terurut linier mengikuti indeks.
   * B. Optimizer akan selalu memilih *Sequential Scan*.
   * C. Engine akan otomatis mengaktifkan kompresi ZSTD.
   * D. Optimizer menonaktifkan caching buffer untuk tabel tersebut.

---

#### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan Esai/Pilihan Ganda Mendalam)

1. **Skenario Kasus A:**
   Aplikasi e-commerce Anda memiliki tabel `invoices` (50 juta baris). Kueri filter status invoice berikut menghasilkan execution plan:
   `Bitmap Heap Scan on invoices ... (cost=450.00..12000.00 rows=5 actual time=12.00..4500.00 rows=850000 loops=1)`.
   Terlihat deviasi estimasi yang brutal (`rows=5` vs `actual rows=850000`). Manakah langkah diagnosis pertama yang paling tepat secara teknis arsitektur?
   * A. Naikkan parameter `max_connections` pada konfigurasi sistem.
   * B. Periksa parameter sampling `default_statistics_target` dan jalankan `ANALYZE invoices` untuk memperbarui distribusi histogram data yang timpang (*skewed*).
   * C. Lakukan drop dan rebuild Primary Key pada tabel `invoices`.
   * D. Nonaktifkan CBO dengan mengubah setting engine ke Rule-Based Optimizer.

2. **Skenario Kasus B:**
   Sebuah kueri analitik menggabungkan tabel `customers` (10.000 baris) dan `orders` (100.000.000 baris). Output execution plan menunjukkan operator **Nested Loop Join** digunakan, menghasilkan eksekusi selama 45 menit.
   Mengapa optimizer memilih *Nested Loop Join* alih-alih *Hash Join* yang jauh lebih cepat untuk volume tersebut?
   * A. Karena CBO salah mengestimasi jumlah baris pada tabel `customers` sebagai 1 baris (underestimation), sehingga ia mengasumsikan biaya outer loop sangat murah.
   * B. Karena parameter `work_mem` diatur ke nilai 100 GB.
   * C. Karena kedua tabel memiliki foreign key yang valid.
   * D. Karena tabel `orders` terlalu kecil untuk membentuk hash table.

3. **Skenario Kasus C:**
   Pada sistem transaksi perbankan dengan konkurensi tinggi (5.000 TPS), administrator database menaikkan setting global `work_mem` dari `4MB` menjadi `1GB` untuk mempercepat satu query laporan berkala yang lambat akibat disk spill. Apa konsekuensi stabilitas yang membayangi sistem tersebut?
   * A. Kueri laporan menjadi lambat karena alokasi memori berlebih.
   * B. Potensi crash server akibat Out-Of-Memory (OOM) Killer sistem operasi, karena alokasi `work_mem` dikalikan per-operator-join per-koneksi aktif yang dapat menghabiskan RAM secara instan saat beban transaksi puncak.
   * C. CPU utilisasi otomatis turun menjadi 0%.
   * D. Database langsung beralih ke read-only mode secara permanen.

---

### Kunci Jawaban Evaluasi

#### Bagian 1: Basic
1. **C** - Statistics Engine / Estimator menggunakan metadata katalog (`pg_statistic`, dsb.) untuk memprediksi kardinalitas baris.
2. **B** - `random_page_cost` memodelkan estimasi biaya akses I/O acak ke disk storage.
3. **B** - `shared hit` menandakan page telah berada di buffer pool RAM database.
4. **C** - Merge Join mensyaratkan kedua aliran data terurut secara identik pada join keys.
5. **C** - Membungkus kolom dengan fungsi membuat predikat non-sargable dan membatalkan B-Tree Index traversal standar.

#### Bagian 2: Intermediate
1. **B** - Waktu startup overhead kompilasi JIT (LLVM) justru lebih besar daripada eksekusi kueri operasional OLTP sederhana.
2. **B** - `geqo_threshold` adalah batas penentu kapan engine beralih dari algoritma deterministic DP ke heuristic genetic search.
3. **B** - `external merge Disk` menunjukkan memori `work_mem` habis, sehingga sisa komparasi sort ditumpahkan ke storage file sementara (*spill to disk*).
4. **B** - Extended statistics secara eksplisit menghitung dependensi multikolom dan frekuensi bersama, meruntuhkan asumsi independensi naif.
5. **A** - Nilai korelasi mendekati 1.0 berarti urutan fisik baris data di storage sama persis dengan urutan daun indeks, membuat index scan sangat murah karena minim page jump.

#### Bagian 3: Skenario Kasus Produksi
1. **B** - Deviasi tajam dari 5 baris estimasi ke 850.000 baris riil menandakan statistik histogram katalog stale atau target sampling terlalu rendah untuk menangkap distribusi data yang ekstrem (*skewness*).
2. **A** - Nested loop secara default dipilih CBO jika outer relation diyakini berkardinalitas sangat kecil (misal 1 baris), sebab biaya inisialisasinya dianggap lebih murah daripada membangun hash table.
3. **B** - `work_mem` bukan batas shared memory, melainkan alokasi independen per node join per koneksi. Pada beban 5.000 TPS, setting 1GB dapat mengonsumsi ratusan gigabyte RAM dalam hitungan milidetik dan memicu OOM Killer menembak proses database.

---

### 16. Summary

1. **Arsitektur Cost-Based Optimizer:** CBO tidak menebak secara intuitif; ia adalah mesin komputasi matematis terstruktur yang memproyeksikan biaya I/O dan CPU berdasarkan statistik sampling metadata (`pg_statistic`). Kualitas rencana eksekusi berbanding lurus dengan keakuratan estimasi kardinalitas.
2. **Pembedahan Execution Plan Komprehensif:** Pembacaan `EXPLAIN` tingkat enterprise mewajibkan evaluasi metrik buffers (`shared hit` vs `read`), identifikasi *temporary disk spills* (`Sort Method: external merge` / `Hash Batches > 1`), serta verifikasi deviasi rasio `actual rows` terhadap `estimated rows`.
3. **Penyelarasan Algoritma Join:** Nested Loop Join efisien untuk set baris mini dengan index probe; Hash Join mendominasi throughput join volume besar tanpa urutan; sedangkan Merge Join adalah raja pemrosesan dataset terurut berskala raksasa.
4. **Mitigasi Masalah Statistika Multivariat:** Asumsi independensi atribut sering melumpuhkan akurasi CBO pada sistem produksi. Implementasi *Extended Statistics* dan penataan parameter cost berbasis perangkat keras modern (seperti NVMe SSD) merupakan pilar stabilitas performa database enterprise berlatensi rendah.