# BAB 04: Aggregations, Grouping & Dimensional Analysis
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis Internal Execution Engine:** Memahami alur kerja fisik query planner saat mengeksekusi agregasi (`HashAggregate` vs `GroupAggregate`) serta alokasi memori internal (`work_mem`, temp file spills).
- **Menguasai Dimensional Analysis Kompleks:** Mengimplementasikan operasi multi-dimensi menggunakan `GROUPING SETS`, `ROLLUP`, dan `CUBE` untuk analitik data warehousing tingkat lanjut.
- **Mengoptimalkan Window Function Framing:** Merancang window framing presisi (`ROWS`, `RANGE`, `GROUPS`) dengan bounded/unbounded bounds guna menghindari memory overhead dan degradasi I/O.
- **Memecahkan Masalah Pola Temporal & Urutan:** Mengonstruksi query analitik untuk menyelesaikan problem industri seperti *Gaps and Islands*, *Sessionization*, dan *Running Totals* dalam throughput tinggi.
- **Mendesain Arsitektur Data Berkelanjutan:** Mengintegrasikan teknik agregasi tingkat lanjut dengan strategi partisi, materialisasi, dan indeks covering untuk beban kerja OLAP dan hybrid HTAP.

---

### 2. Prerequisites
Sebelum mendalami modul ini, Anda wajib menguasai:
- Sintaks dasar SQL (`SELECT`, `WHERE`, `JOIN`, `GROUP BY`, `HAVING`).
- Pemahaman dasar fungsi agregat standar (`SUM`, `AVG`, `COUNT`, `MIN`, `MAX`).
- Konsep dasar Relational Database Management System (RDBMS) architecture (Buffer Pool, WAL, B-Tree Index).
- Pemahaman eksekusi query dasar melalui `EXPLAIN` (Seq Scan, Index Scan).

---

### 3. Concept & Internal Architecture

Eksekusi agregasi dan dimensional analysis pada basis data relasional enterprise (seperti PostgreSQL, MySQL 8.0+, Oracle, SQL Server) melibatkan kalkulasi matematis berbasis partisi data fisik di memori. 

```
                                  +-----------------------+
                                  | Incoming Tuple Stream |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
         [ Unsorted / High Cardinality ]                     [ Pre-Sorted / Indexed ]
                     |                                                 |
                     v                                                 v
           +--------------------+                            +--------------------+
           |   HashAggregate    |                            |   GroupAggregate   |
           +---------+----------+                            +---------+----------+
                     |                                                 |
        +------------+------------+                                    |
        |                         |                                    |
(Fit in work_mem)        (Exceeds work_mem)                            |
        |                         |                                    |
        v                         v                                    v
   [ In-Memory ]          [ Hash Spills to ]                  [ Streaming State ]
   [ Hash Table]          [ Temp Disk Files]                  [ One-Pass Engine ]
        |                         |                                    |
        +------------+------------+                                    |
                     |                                                 |
                     +------------------------+------------------------+
                                              |
                                              v
                                  +-----------------------+
                                  |    WindowAgg Engine   |
                                  |  (Frame Buffer Eval)  |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |  Final Output Stream  |
                                  +-----------------------+
```

#### A. Mekanisme Eksekusi Agregasi Fisik
Ketika klausa `GROUP BY` dievaluasi, query optimizer memilih satu dari dua strategi eksekusi utama:

1. **`HashAggregate`**
   - **Mekanisme:** Engine membaca baris data, menghasilkan hash key dari kolom-kolom `GROUP BY`, dan menyimpan nilai akumulator dalam In-Memory Hash Table.
   - **Karakteristik Memori:** Membutuhkan memori sebesar jumlah grup unik dikali ukuran state akumulator. Diatur oleh parameter alokasi seperti `work_mem` (PostgreSQL) atau `hash_area_size` (Oracle).
   - **Spill Behavior:** Jika ukuran hash table melebihi kuota memori, database mempartisi bucket hash ke disk (*temp files/spill to tempdb*), memicu I/O serialization dan deserialization yang menurunkan performa secara drastis.

2. **`GroupAggregate`**
   - **Mekanisme:** Engine mengharapkan stream data masukan yang telah terurut berdasarkan kunci pengelompokan (baik didapat melalui `Index Scan` atau operator `Sort` eksplisit sebelumnya). Engine membaca baris satu per satu (*streaming*), mengakumulasi nilai, dan langsung memancarkan (*emit*) hasil saat terjadi transisi nilai kunci grup.
   - **Karakteristik Memori:** Sangat hemat memori ($O(1)$ relatif terhadap total data) karena hanya mempertahankan state akumulasi untuk satu grup aktif dalam satu waktu.

#### B. Internal Operator Windowing (`WindowAgg`)
Window functions tidak mengonsolidasi baris menjadi satu output tunggal; sebaliknya, baris mempertahankan identitas individualnya sambil mengakses nilai baris di sekitarnya.
- **Partitioning Phase:** Engine mempartisi data (serupa dengan GroupAggregate, data diurutkan berdasarkan `PARTITION BY` + `ORDER BY`).
- **Framing Buffer:** Database membentuk frame window (`ROWS`, `RANGE`, atau `GROUPS`).
  - `ROWS`: Menghitung offset fisik baris secara diskrit. Sangat cepat karena evaluasi didasarkan pada *pointer arithmetic*.
  - `RANGE`: Mengevaluasi offset secara logis berdasarkan nilai data pada klausa `ORDER BY`. Memerlukan pembandingan nilai actual data, berpotensi membaca peers (nilai duplikat) hingga akhir partisi.
  - `GROUPS`: Menghitung grup dari nilai baris duplikat sebagai unit tunggal offset.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Subqueries/Self-Joins) | Pendekatan Modern (Window & Multi-Dim SQL) |
| :--- | :--- | :--- |
| **Kompleksitas Algoritmik** | Cenderung $O(N^2)$ akibat self-join pada dataset besar untuk mencari perbandingan nilai masa lalu/berjalan. | $O(N \log N)$ untuk tahap sorting, dilanjutkan dengan $O(N)$ scanning pipeline. |
| **I/O & Buffer Hit** | Membaca tabel yang sama berulang kali (Multiple Table Scans). | Single Pass Scan atau memanfaatkan materialisasi partisi lokal. |
| **Keterbacaan Kode** | Ratusan baris SQL dengan nested inline views yang rentan *bug* maintainability. | Deklaratif, ekspresif, dan modular menggunakan Window Specification (`WINDOW w AS (...)`). |
| **Eksekusi Analitik Multi-Level** | Membutuhkan operasi `UNION ALL` antar level agregasi (cth: harian, bulanan, total). | Satu pass komputasi dengan `GROUPING SETS`, `ROLLUP`, atau `CUBE`. |

---

### 5. How (Workflow Detail)

Alur kerja perancangan analitik data enterprise:
1. **Analisis Pola Data (Cardinality & Distribution):** Identifikasi kardinalitas kolom agregasi. Kardinalitas rendah-menengah cocok untuk `HashAggregate`; kardinalitas sangat tinggi dengan volume gigabyte/terabyte memerlukan skema sorting via B-Tree index untuk memicu `GroupAggregate`.
2. **Definisi Window Frame yang Ketat:** Hindari penggunaan frame implisit default. Gunakan `ROWS BETWEEN ...` secara eksplisit guna mencegah pembacaan data berlebih pada spool buffer.
3. **Optimasi Pipeline Windowing Menggunakan Klausa WINDOW:** Satukan deklarasi frame identik untuk menghindari multiple operator `Sort` dalam execution plan yang sama.
4. **Validasi Execution Plan:** Periksa via `EXPLAIN (ANALYZE, BUFFERS)` untuk memastikan tidak terjadi disk spill (`Batches: > 1` atau `Disk: > 0 kB`).

---

### 6. Analogy & Diagram ASCII

Bayangkan konveyor perakitan pabrik:

```
[ Traditional Self-Join (O(N^2)) ]
Item A1 ---> Scan seluruh keranjang untuk cari pembanding ---> Emit
Item A2 ---> Scan ulang seluruh keranjang dari awal!    ---> Emit (Sangat Boros)

[ WindowAgg Streaming Engine (O(N)) ]
Data terurut masuk ke konveyor:
               Window Frame Buffer [Current - 1, Current, Current + 1]
                       +-------------------+
Items In Stream =====> | [A0] -> [A1] -> ? | =====> Accumulator Output
                       +-------------------+
Saat A2 masuk, A0 dibuang dari buffer, geser pointer satu langkah ke depan.
```

Pada multi-dimensional aggregations (`ROLLUP`):
```
Data: Region, Store, Product

Level 3 (Detail)  : [Region, Store, Product] -> Agregasi level terbawah
Level 2 (Subtotal): [Region, Store]          -> Collapse dimensi Product
Level 1 (Subtotal): [Region]                 -> Collapse dimensi Store
Level 0 (Grand)   : []                       -> Total Keseluruhan
Semua dieksekusi dalam satu stream scanning data tree.
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Perbedaan Framing `ROWS` vs `RANGE`
Perhatikan bagaimana penulisan frame memengaruhi akumulasi saat ada nilai duplikat pada order key:

```sql
-- DDL & Data Dummy
CREATE TABLE sales_mock (
    day_id INT,
    amount NUMERIC
);

INSERT INTO sales_mock (day_id, amount) VALUES 
(1, 100), 
(2, 200), 
(2, 300), -- Duplicate day_id
(3, 400);

-- Query Perbandingan Frame
SELECT 
    day_id, 
    amount,
    -- Default implicit frame (RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    SUM(amount) OVER (ORDER BY day_id) AS running_range_default,
    -- Explicit streaming row frame
    SUM(amount) OVER (ORDER BY day_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_rows_explicit
FROM sales_mock;
```

**Output:**
```
 day_id | amount | running_range_default | running_rows_explicit 
--------+--------+-----------------------+-----------------------
      1 |    100 |                   100 |                   100
      2 |    200 |                   600 |                   300  <-- RANGE menjumlahkan peer day_id=2 sekaligus!
      2 |    300 |                   600 |                   600
      3 |    400 |                  1000 |                  1000
```

#### Practical Example: Advanced Multi-Dimensional Reporting
Contoh query analitik performa penjualan lintas dimensi (*Store*, *Category*) dengan perhitungan grand total dan subtotal terintegrasi, filter agregat modular, dan penanda level hierarki data:

```sql
SELECT 
    COALESCE(store_id, 'ALL STORES') AS store_id,
    COALESCE(category, 'ALL CATEGORIES') AS category,
    GROUPING(store_id, category) AS aggregation_level,
    SUM(sales_amount) AS total_revenue,
    COUNT(transaction_id) AS total_transactions,
    -- Menggunakan FILTER aggregate clause (ANSI SQL Standard)
    SUM(sales_amount) FILTER (WHERE payment_method = 'CREDIT_CARD') AS cc_revenue,
    ROUND(
        AVG(sales_amount), 2
    ) AS avg_basket_size
FROM retail_transactions
WHERE transaction_time >= '2026-01-01' AND transaction_time < '2026-02-01'
GROUP BY CUBE(store_id, category)
ORDER BY GROUPING(store_id, category), store_id, category;
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Real-Time Fraud & Anomaly Detection Pipeline di FinTech Ledger
*Platform pembayaran digital dengan throughput 15.000 transaksi per detik (TPS). Arsitektur memerlukan deteksi anomali velocity (lonjakan transaksi abnormal dalam jangka waktu sempit) dan identifikasi sequence transaksi tanpa gap (pola testing bot).*

##### Masalah:
Query analitik pelaporan sering mengalami *timeout* saat memeriksa *moving velocity average* dan mendeteksi selisih transaksi per akun dalam jendela waktu bergerak (sliding window 1 jam).

##### Skema & Optimasi Indeks:
```sql
CREATE TABLE account_ledger (
    ledger_id BIGINT GENERATED ALWAYS AS IDENTITY,
    account_id UUID NOT NULL,
    transaction_time TIMESTAMPTZ NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT pk_account_ledger PRIMARY KEY (ledger_id)
);

-- B-Tree Composite Index untuk memicu WindowAgg / GroupAggregate murni
-- Index layout sengaja diurutkan agar database membaca sequential stream tanpa sorting di memori
CREATE INDEX idx_ledger_fraud_analysis 
ON account_ledger (account_id, transaction_time ASC) 
INCLUDE (amount);
```

##### Query Deteksi Anomali Kompleks (Windowing Multi-Metrik):
```sql
WITH enriched_transactions AS (
    SELECT 
        ledger_id,
        account_id,
        transaction_time,
        amount,
        -- Menghitung gap waktu dengan transaksi sebelumnya (Lagging detection)
        EXTRACT(EPOCH FROM (transaction_time - LAG(transaction_time) OVER w)) AS seconds_since_last_tx,
        -- Running average 5 transaksi terakhir untuk melihat lonjakan drastis (Dynamic Row Window)
        AVG(amount) OVER (
            w ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ) AS avg_amount_prior_5,
        -- Total velocity pengeluaran dalam frame waktu fleksibel
        SUM(amount) OVER (
            w RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
        ) AS rolling_hourly_spend,
        -- Deteksi urutan transaksi berulang (Identifikasi Robot/DDoS pattern)
        ROW_NUMBER() OVER w AS sequence_in_partition
    FROM account_ledger
    WHERE status = 'SUCCESS'
    WINDOW w AS (
        PARTITION BY account_id 
        ORDER BY transaction_time ASC
    )
)
SELECT 
    ledger_id,
    account_id,
    transaction_time,
    amount,
    avg_amount_prior_5,
    rolling_hourly_spend,
    CASE 
        WHEN seconds_since_last_tx < 2.0 AND amount > (3 * COALESCE(avg_amount_prior_5, amount)) 
            THEN 'FLAG_RAPID_SPIKE'
        WHEN rolling_hourly_spend > 50000000 
            THEN 'FLAG_VELOCITY_LIMIT_EXCEEDED'
        ELSE 'NORMAL'
    END AS risk_score
FROM enriched_transactions
WHERE transaction_time >= NOW() - INTERVAL '6 hours';
```

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Biaya / Konsekuensi | Skenario Terbaik |
| :--- | :--- | :--- | :--- |
| **`HashAggregate`** | Tidak memerlukan data terurut sebelumnya; eksekusi cepat untuk dataset dengan agregasi kardinalitas rendah-menengah. | Memori intensif; terjadi crash/degradasi latency masif saat *spill to disk*. | Agregasi acak, dimensi rendah (cth: Status Code, Gender). |
| **`GroupAggregate` (via Index)** | Beban memori sangat rendah ($O(1)$ state); pipeline streaming langsung memproses stream baris pertama. | Memerlukan indeks B-Tree yang tepat; memperlambat write throughput (overhead write index). | Data time-series, log audit keuangan dengan index `(entity_id, timestamp)`. |
| **Window Frame `ROWS`** | Performa sangat tinggi; penelusuran frame langsung menggunakan indeks fisik baris. | Mengabaikan nilai *ties* (duplikat), berpotensi memotong baris data pada titik potong yang sama secara arbitrer. | Running totals terurut ketat, moving simple average berdasar counter. |
| **Window Frame `RANGE`** | Memperhitungkan kesetaraan nilai analitik (*ties handling*); mendukung interval temporal natif. | Memory-buffering intensif; tidak dapat dioptimalkan dengan ringkasan bitwise pada engine tertentu. | Agregasi finansial berbasis kalender/waktu, valuasi interval waktu nyata. |
| **`CUBE` / `ROLLUP`** | Menghasilkan laporan analitik multi-level dalam satu query pass. | Pertumbuhan baris output eksponensial ($2^N$ untuk CUBE); berisiko Out-Of-Memory (OOM) jika $N$ besar. | Data warehousing, aggregasi reporting offline, kubus OLAP berdimensi $\le 5$. |

---

### 10. Common Mistakes & Troubleshooting

#### A. Mengabaikan Unbounded Frame Implisit
*Kesalahan:* Menulis `SUM(val) OVER (ORDER BY ts)` dan mengasumsikan database menghitung secara streaming `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.
*Dampak:* RDBMS mengasumsikan standar ANSI: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Database terpaksa melakukan lookup peer-group baris per baris. Jika ada banyak nilai timestamp sama, engine menahan buffer di memori, menyebabkan I/O spill dan performa drop drastis dari sub-detik ke puluhan detik.
*Solusi:* Tuliskan frame bounded secara eksplisit: `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.

#### B. Memory Spilling pada Execution Plan
*Gejala:* Query berjalan lambat. `EXPLAIN ANALYZE` menunjukkan:
```text
HashAggregate (cost=... rows=... width=...)
  Batches: 5  Memory Usage: 4097kB  Disk Usage: 18432kB
```
*Diagnostik & Troubleshooting:*
1. Periksa nilai session setting:
   ```sql
   SHOW work_mem;
   ```
2. Alokasikan memori lokal yang memadai secara terukur khusus pada query/session analitik:
   ```sql
   SET LOCAL work_mem = '64MB';
   ```
3. Alternatif permanen: Buat covering index pada kolom `GROUP BY` agar planner beralih dari `HashAggregate` ke `GroupAggregate`.

---

### 11. Best Practices (Production Checklist)

- [ ] **Eksplisitkan Deklarasi Frame:** Jangan pernah meninggalkan klausa window dengan klausa `ORDER BY` tanpa mendefinisikan frame `ROWS` atau `RANGE`.
- [ ] **Gunakan Kolom Kardinalitas Tertinggi di Urutan Pertama Indeks:** Pasang B-Tree index yang mencerminkan pola agregasi partisi (`PARTITION BY high_cardinality, ORDER BY time`).
- [ ] **Minimalisir Operator Sort Ganda:** Jika menggunakan beberapa window function, usahakan memiliki partisi dan urutan yang identik dengan memanfaatkan klausul `WINDOW w AS (...)` terpusat.
- [ ] **Batasi Jumlah Dimensi pada CUBE:** Jangan mengeksekusi operator `CUBE` dengan lebih dari 5 kolom secara dinamis; pecah menjadi batch atau gunakan pipeline ELT berbasis dbt/Materialized Views.
- [ ] **Terapkan Conditional Aggregation secara Native:** Ganti konstruksi lama `SUM(CASE WHEN ... THEN 1 ELSE 0 END)` dengan standar ANSI `COUNT(*) FILTER (WHERE ...)`. Filter agregat dieksekusi langsung pada level accumulator C-engine tanpa evaluasi percabangan ekspresi baris penuh.

---

### 12. Hands-on Practice

Buat skrip pengujian performa mandiri untuk disimpan pada folder `hands-on/m02/deep_dive_aggregation.sql`:

```sql
-- hands-on/m02/deep_dive_aggregation.sql

-- 1. Setup Sandbox Schema
DROP TABLE IF EXISTS sensor_telemetry;
CREATE TABLE sensor_telemetry (
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_id INT NOT NULL,
    metric_type VARCHAR(16) NOT NULL,
    reading_val DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL
);

-- 2. Populate 500,000 baris data simulasi
INSERT INTO sensor_telemetry (device_id, metric_type, reading_val, recorded_at)
SELECT 
    (random() * 50 + 1)::INT,
    CASE (random() * 2)::INT 
        WHEN 0 THEN 'TEMPERATURE' 
        WHEN 1 THEN 'PRESSURE' 
        ELSE 'HUMIDITY' 
    END,
    random() * 100.0,
    NOW() - (g || ' seconds')::INTERVAL
FROM generate_series(1, 500000) AS g;

-- 3. Analisis Profil Plan Tanpa Indeks (Default HashAggregate / External Sort)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    device_id,
    metric_type,
    AVG(reading_val) AS avg_reading,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY reading_val) AS p95_reading
FROM sensor_telemetry
GROUP BY CUBE(device_id, metric_type);

-- 4. Optimasi: Buat Index Covering
CREATE INDEX idx_telemetry_stream 
ON sensor_telemetry (device_id, metric_type) 
INCLUDE (reading_val);

-- 5. Eksekusi Analitik Jendela Bergerak (Window Frame Bounded vs Default)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    device_id,
    recorded_at,
    reading_val,
    -- Memaksa penggunaan buffer rows diskrit
    AVG(reading_val) OVER (
        PARTITION BY device_id, metric_type 
        ORDER BY recorded_at 
        ROWS BETWEEN 10 PRECEDING AND CURRENT ROW
    ) AS rolling_avg_bounded
FROM sensor_telemetry;
```

---

### 13. Exercises

#### Level Easy
Diberikan tabel `employee_salaries (emp_id INT, department_id INT, salary NUMERIC)`. Tuliskan query untuk menampilkan data: `emp_id`, `department_id`, `salary`, serta nilai gaji tertinggi di masing-masing departemen tanpa menggunakan nested subquery.

#### Level Medium
Diberikan tabel `user_logins (user_id INT, login_time TIMESTAMPTZ)`. Tuliskan query untuk mengidentifikasi selisih waktu (dalam satuan detik) antara login saat ini dengan login sebelumnya untuk setiap pengguna. Tandai baris pertama dengan nilai 0.

#### Level Hard (Gaps and Islands Problem)
Diberikan tabel `server_status_logs (log_id BIGINT, server_id INT, status VARCHAR(10), checked_at TIMESTAMPTZ)`. Server melaporkan status 'ONLINE' atau 'OFFLINE' secara berkala.
*Tugas:* Tuliskan query SQL performan untuk mengonsolidasikan log menjadi rentang periode status stabil (islands of stability). Output harus berisi: `server_id`, `status`, `start_time`, `end_time`, dan `status_duration`.

---

### 14. Challenges

#### Arsitektur Skema & Komputasi Funnel Konversi Real-Time
Sebuah e-commerce enterprise memproses data stream aktivitas pengunjung ke dalam tabel:
```sql
event_stream (
    event_id UUID, 
    session_id UUID, 
    user_id UUID, 
    action_type VARCHAR(32), -- 'VIEW_ITEM', 'ADD_TO_CART', 'CHECKOUT', 'PAYMENT'
    event_timestamp TIMESTAMPTZ
)
```
*Tantangan Desain:*
1. Bangun query analitik sessionization yang membagi data menjadi sesi pengguna baru jika tidak ada aktivitas selama lebih dari 30 menit tanpa membuat tabel sementara.
2. Tentukan konversi langkah demi langkah per sesi: apakah sesi tersebut berhasil menembus alur lengkap (`VIEW_ITEM` $\to$ `ADD_TO_CART` $\to$ `CHECKOUT` $\to$ `PAYMENT`) dalam urutan waktu yang konsisten.
3. Query harus mampu berjalan di atas partisi harian (100+ juta baris) dengan response time di bawah 3 detik tanpa memicu memory spill ke disk. Rancang indeks, window clause, dan grouping yang paling optimal.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1. Apa perbedaan mendasar antara implementasi `GroupAggregate` dan `HashAggregate` di tingkat fisik memori database?
2. Mengapa klausa `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` secara komputasi lebih efisien dibandingkan frame default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`?
3. Apa fungsi dari klausa `GROUPING()` ketika dipadukan dengan ekspresi `CUBE` atau `ROLLUP`?
4. Kapan sebaiknya Anda menggunakan sintaks modern `AGG_FUNC(...) FILTER (WHERE ...)` alih-alih `AGG_FUNC(CASE WHEN ... THEN ... END)`?
5. Apakah window function dapat digunakan langsung di dalam klausa `WHERE`? Jelaskan landasan logis evaluasi urutan fase SQL (logical query processing phase).

#### Pertanyaan Intermediate
6. Jika `work_mem` dialokasikan sebesar 16MB pada PostgreSQL, dan sebuah query menjalankan `HashAggregate` dengan estimasi hash table sebesar 45MB, apa langkah mitigasi internal yang diambil oleh query engine?
7. Bagaimana cara engine RDBMS menangani frame `RANGE` ketika kolom `ORDER BY` mengandung nilai non-deterministik atau tie berulang?
8. Dalam dimensional reporting, berapa jumlah grouping set yang dihasilkan oleh instruksi `GROUP BY CUBE(branch, department, role)`? Tuliskan kombinasinya.
9. Jelaskan perbedaan performa antara mengeksekusi 3 window function dengan spesifikasi `OVER (PARTITION BY A ORDER BY B)` yang seragam dibandingkan dengan spesifikasi partisi dan order yang acak pada query yang sama.
10. Bagaimana window function `DENSE_RANK()` menangani baris dengan nilai order yang sama jika dibandingkan dengan `RANK()` dan `ROW_NUMBER()`?

#### Skenario Kasus Produksi
11. **Skenario Disk Spilling:**
    Database analitik Anda mengalami latency spike parah pada jam sibuk. Saat memeriksa execution plan via `EXPLAIN (ANALYZE)`, ditemukan step: `WindowAgg (cost=... rows=... batches=18, disk_spill=240MB)`. Indeks pada tabel saat ini adalah `CREATE INDEX idx_a ON logs (created_at);`. Modifikasi struktural apa (baik setting database maupun arsitektur indeks) yang harus dieksekusi untuk meredam latency tersebut ke 0 spill?
12. **Skenario Skewed Data Distribution:**
    Sebuah tabel transaksi merchant memiliki beberapa merchant raksasa dengan jutaan transaksi harian, sementara ribuan merchant kecil hanya memiliki belasan transaksi. Saat dieksekusi `PARTITION BY merchant_id` untuk perhitungan running balance, pipeline query bottleneck pada beberapa worker thread. Pendekatan arsitektural apa yang dapat diterapkan pada level SQL dan partitioning untuk menyeimbangkan beban kalkulasi?
13. **Skenario High-Throughput Aggregations (OLAP vs OLTP Concurrency):**
    Sistem Anda diharuskan menyajikan laporan dashboard real-time yang memuat kalkulasi moving average dan agregasi dimensional lintas 30 hari terakhir. Jika query dijalankan langsung ke master node OLTP, CPU usage langsung menyentuh 95%. Strategi arsitektural apa (Read Replicas, Materialized Views dengan Incremental Refresh, atau TimescaleDB/ClickHouse foreign data wrapper) yang paling tepat diterapkan, serta bagaimana desain query sinkronisasinya?

---

### 16. Summary

- **Algoritma Agregasi Fisik:** Pengetahuan mendalam mengenai `HashAggregate` (kardinalitas rendah, berbasis in-memory hash table) versus `GroupAggregate` (kardinalitas tinggi, streaming, butuh sorted input/indeks) adalah kunci optimasi performa backend skala enterprise.
- **Window Framing Presisi:** Selalu gunakan frame bounded diskrit (`ROWS`) saat kalkulasi sekuensial berjalan. Default implicit `RANGE` frame dapat memicu memory buffering masif akibat evaluasi peers secara logis.
- **Dimensi Analitik Mutakhir:** Hindari pola purba penggabungan subquery berulang menggunakan `UNION ALL`. Manfaatkan `GROUPING SETS`, `ROLLUP`, dan `CUBE` yang diproses secara *single pass scan* untuk efisiensi komputasi maksimal.
- **Memory & Spilling Safeguards:** Monitor ketat metrik disk spill via `EXPLAIN ANALYZE`. Kurangi disk I/O dengan menyelaraskan B-Tree covering index pada partisi window dan menyetel alokasi query memory (`work_mem`) secara terukur.