# BAB 05: Advanced Window Functions & Analytical SQL
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Menganalisis Internal Engine Execution Plan**: Membedah node eksekusi analitis (`WindowAgg`, `Sort`, `Materialize`) pada PostgreSQL/distributed SQL engine dan mengidentifikasi bottleneck resource CPU vs Memory.
2. **Mengoptimalkan Frame Specification Tingkat Lanjut**: Menguasai semantik dan implikasi performa dari `ROWS`, `RANGE`, dan `GROUPS`, serta clause `EXCLUDE` (`CURRENT ROW`, `GROUP`, `TIES`, `NO OTHERS`).
3. **Mencegah Disk Spill & Memory Exhaustion**: Mengonfigurasi parameter engine (`work_mem`, `temp_tablespaces`) untuk mencegah tumpahan spool data ke disk (`external merge disk`) pada volume data multi-juta baris.
4. **Mendesain Indeks Komposit Optimal untuk Windowing**: Menerapkan strategi *Index-Only Scan* untuk query analitis menggunakan pola `(Partition Keys, Order Keys INCLUDE Payload)`.
5. **Mengimplementasikan Pola Analitikal Kompleks**: Membangun algoritma analitik *rolling retention*, *gap-and-island detection*, deteksi anomali penipuan (fraud velocity), dan rekonsiliasi buku besar multi-mata uang (*ledger reconciliation*) dengan latensi rendah.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
* Dasar Window Functions: Sintaks `OVER (PARTITION BY ... ORDER BY ...)` dan fungsi dasar (`ROW_NUMBER()`, `RANK()`, `DENSE_RANK()`, `LEAD()`, `LAG()`).
* Arsitektur RDBMS Dasar: Konsep Buffer Pool, Shared Buffers, WAL, dan Cost-Based Optimizer (CBO).
* Eksekusi Query Dasar: Membaca output mendasar dari `EXPLAIN` dan `EXPLAIN ANALYZE` (Seq Scan, Index Scan, Hash Aggregate).
* Tipe Data Temporal & Numerik Presisi: Karakteristik `TIMESTAMPTZ`, `INTERVAL`, dan `NUMERIC(p, s)`.

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Window Execution Engine: Pipeline Lifecycle
Di dalam RDBMS modern (seperti PostgreSQL, CockroachDB, MySQL 8+, atau Snowflake), window function dieksekusi setelah evaluasi klausa `FROM`, `WHERE`, `GROUP BY`, dan `HAVING`, namun sebelum klausa `DISTINCT`, `ORDER BY` terluar, dan `LIMIT`.

```
[FROM & JOIN] -> [WHERE] -> [GROUP BY] -> [HAVING] -> [WINDOW FUNCTIONS (WindowAgg)] -> [DISTINCT] -> [ORDER BY] -> [LIMIT]
```

Ketika query mengandung ekspresi analitis, Query Optimizer menyuntikkan node `WindowAgg` ke dalam pohon rencana eksekusi (*execution plan*). Node ini bergantung secara absolut pada data yang masuk dalam keadaan terurut sesuai dengan definisi `PARTITION BY` dan `ORDER BY` pada klausul window.

```
       +-------------------------------------------------------+
       |                      WindowAgg                        |
       |  - Membaca baris dari spool / sorted subplan           |
       |  - Menghitung agregasi frame / offset function        |
       +-------------------------------------------------------+
                                  ^
                                  | Terurut (Partition + Order Keys)
       +-------------------------------------------------------+
       |             Sort / Incremental Sort Node              |
       |  - Mengurutkan stream berdasarkan PARTITION + ORDER   |
       |  - Menggunakan work_mem (Quicksort) / Spill (Disk)    |
       +-------------------------------------------------------+
                                  ^
                                  | Baris Data Mentah
       +-------------------------------------------------------+
       |               Scan Node (Index/Seq/Bitmap)            |
       +-------------------------------------------------------+
```

#### B. Anatomi Spooling Buffer & Window Framing Mechanics
Node `WindowAgg` menggunakan *Window Spool* (in-memory tuplestore) untuk mengelola baris-baris dalam partisi aktif. Mekanisme framing menentukan bagaimana spool buffer dibaca dan dibersihkan:

1. **`ROWS`**: Bekerja pada batas baris fisik (*physical offsets*).
   * Engine cukup memajukan pointer baris absolut.
   * Sangat hemat CPU dan alokasi memori karena evaluasi tidak memerlukan pengecekan nilai duplikat (*peers*).
2. **`RANGE`**: Bekerja pada batas nilai logis (*logical value offsets*).
   * Jika klausa default digunakan: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, engine **harus membaca ke depan (look-ahead)** untuk menemukan semua baris "peer" yang memiliki nilai identik pada kolom `ORDER BY`.
   * **Bahaya Performa**: Engine tidak dapat memancarkan (*emit*) hasil untuk baris saat ini sampai ia membaca baris berikutnya yang memiliki nilai berbeda. Hal ini memicu akumulasi buffer besar pada data dengan kardinalitas rendah.
3. **`GROUPS`**: Bekerja pada kelompok baris peer nilai logis (*logical peer group offsets*).
   * Menghitung offset berdasarkan grup nilai unik, bukan jumlah baris fisik.

```
Konfigurasi Frame: RANGE vs ROWS vs GROUPS (Nilai Order Key: [10, 10, 10, 20, 30])

Baris Ke-:    1      2      3      4      5
Nilai:       [10]   [10]   [10]   [20]   [30]
              ^
              Posisi Evaluasi Saat Ini (Row 1)

1. ROWS 1 PRECEDING AND CURRENT ROW:
   Frame mengevaluasi: [Row 1] saja (karena tidak ada baris 0).
   Pada Row 2: Frame mengevaluasi: [Row 1, Row 2].

2. RANGE CURRENT ROW:
   Frame mengevaluasi seluruh peer logis: [Row 1, Row 2, Row 3].
   Engine wajib membaca hingga baris ke-3 sebelum menghasilkan kalkulasi untuk baris ke-1!

3. GROUPS 1 PRECEDING AND CURRENT ROW (pada Row 4):
   Frame mengevaluasi grup nilai '10' dan grup nilai '20': [Row 1, Row 2, Row 3, Row 4].
```

#### C. Memory Spill (work_mem exhaustion)
Jika ukuran data dalam satu partisi atau ukuran baris yang perlu diurutkan melebihi batas `work_mem` PostgreSQL:
1. `Sort Node` berubah metode dari `quicksort` (in-memory) menjadi `external merge Disk`.
2. Tuplestore pada `WindowAgg` terpaksa melakukan serialisasi tuple ke `temp_tablespaces` di storage (disk I/O).
3. Query mengalami degradasi throughput masif hingga mencapai 10x-50x lebih lambat akibat context switching kernel dan latensi storage.

---

### 4. Why & What

#### Mengapa SQL Window Functions Tingkat Lanjut Dibutuhkan?
Pada sistem skala enterprise, kebutuhan analisis data tidak lagi sesederhana agregasi global (`SUM() GROUP BY`). Masalah operasional nyata meliputi:
* Menghitung saldo berjalan (*running balance*) per rekening dari puluhan juta entri ledger tanpa mengunci baris (*lock-free*).
* Menghitung moving average dengan frame waktu dinamis (misal: "30 menit ke belakang", bukan sekadar "30 baris ke belakang") untuk mendeteksi lonjakan volume transaksi API.
* Menganalisis *user retention* bertingkat menggunakan algoritma *gap-and-island* tanpa menggunakan *procedural cursor* (PL/pgSQL) yang lambat.

#### Kelemahan Pendekatan Tradisional (Self-Join & Correlated Subqueries):
* **Kompleksitas Asimptotik**: Self-join untuk rolling metrics umumnya memiliki kompleksitas waktu $\mathcal{O}(N^2)$.
* **Beban I/O Ganda**: Correlated subquery mengeksekusi scanning berulang kali untuk setiap baris di tabel luar.
* **Window Functions Modern**: Mengurangi kompleksitas menjadi $\mathcal{O}(N \log N)$ (akibat sorting) atau $\mathcal{O}(N)$ (jika data sudah diindeks secara terurut), dengan single-pass scan.

---

### 5. How (Workflow Detail Eksekusi)

Berikut adalah tahapan teknis internal engine saat memproses query analitis:

```
[Query Engine Parser/Planner]
              |
              v
[Cek Indeks Komposit] ---> Cocok? (Index Scan: Data sudah terurut)
              |                       |
              | Tidak                 +---> Langsung ke WindowAgg
              v                                    |
[Eksekusi Sort Node]                               |
  - Alokasikan work_mem                            |
  - Partisi & Urutkan Tuple                        |
              |                                    |
              +------------------------------------+
              v
[WindowAgg Processing Node]
  1. Inisialisasi Partisi Baru (Reset accumulator / register)
  2. Buka Tuplestore Spool Buffer
  3. Evaluasi Framing (ROWS / RANGE / GROUPS):
     - Geser batas Frame Head (Preceding)
     - Geser batas Frame Tail (Following)
  4. Eksekusi Agregasi Frame / Offset Engine
  5. Kirim Hasil ke Parent Node / Client
  6. Baris terakhir di partisi? 
     - Ya: Hancurkan Spool Buffer, loop ke partisi berikutnya.
     - Tidak: Baca tuple baris berikutnya.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Operator Inspeksi Ban Berjalan
Bayangkan sebuah ban berjalan di pabrik perakitan:
* **Tabel Basis Data**: Tumpukan paket di gudang.
* **`PARTITION BY`**: Memilah paket ke beberapa ban berjalan berbeda berdasarkan jenis produk (misal: Elektronik, Pakaian).
* **`ORDER BY`**: Mengatur urutan paket pada ban berjalan berdasarkan stempel waktu pembuatan.
* **`Window Frame (ROWS/RANGE)`**: Kaca pembesar fleksibel yang dipegang oleh seorang operator:
  * `ROWS 2 PRECEDING AND CURRENT ROW`: Operator hanya melihat paket yang berada tepat di bawah tangannya dan 2 paket tepat sebelum dia.
  * `RANGE BETWEEN INTERVAL '1 HOUR' PRECEDING AND CURRENT ROW`: Operator harus melihat semua paket yang diproduksi dalam interval 1 jam terakhir, berapapun jumlah fisiknya di atas ban berjalan.

```
       ALIRAN DATA PARTISI (ORDER BY timestamp ASC) ---> Menuju Arah Keluar
       ========================================================================
       [Paket 1]   [Paket 2]   [Paket 3]   [Paket 4]   [Paket 5]   [Paket 6]
         08:00       08:15       08:20       08:20       08:50       09:10
       ========================================================================
                                             ^
                                             |
                                  POSISI EVALUASI SAAT INI (Row 4)

       [---------------- FRAME: ROWS 2 PRECEDING AND CURRENT ROW ---------------]
                   Paket 2, Paket 3, Paket 4 (Tepat 3 Baris Fisik)

       [-------- FRAME: RANGE BETWEEN '30 MIN' PRECEDING AND CURRENT ROW -------]
                   Paket 2 (08:15), Paket 3 (08:20), Paket 4 (08:20)
                   (Paket 1 dikecualikan karena 08:00 < 08:20 - 30 menit)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Perbedaan Fundamental `ROWS` vs `RANGE`
Skrip berikut mendemonstrasikan kesalahan umum perhitungan rolling sum akibat nilai timestamp/order key duplikat:

```sql
-- Setup tabel demonstrasi
CREATE TEMPORARY TABLE sales_stream (
    id INT,
    sold_at DATE,
    amount NUMERIC(10,2)
);

INSERT INTO sales_stream (id, sold_at, amount) VALUES
(1, '2026-03-01', 100.00),
(2, '2026-03-02', 150.00),
(3, '2026-03-02', 200.00), -- Tanggal kembar (Peer Rows)
(4, '2026-03-03', 300.00);

-- Bandingkan hasil kumulatif
SELECT 
    id, 
    sold_at, 
    amount,
    -- Kasus 1: Default Implisit (RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
    SUM(amount) OVER (
        ORDER BY sold_at
    ) AS balance_range_default,
    -- Kasus 2: Eksplisit ROWS (Deterministic per physical row)
    SUM(amount) OVER (
        ORDER BY sold_at 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS balance_rows_explicit
FROM sales_stream;
```

**Output:**
```
 id |  sold_at   | amount | balance_range_default | balance_rows_explicit 
----+------------+--------+-----------------------+-----------------------
  1 | 2026-03-01 | 100.00 |                100.00 |                100.00
  2 | 2026-03-02 | 150.00 |                450.00 |                250.00  <-- BEDA!
  3 | 2026-03-02 | 200.00 |                450.00 |                450.00  <-- BEDA!
  4 | 2026-03-03 | 300.00 |                750.00 |                750.00
```
*Analisis Hasil:* Pada `balance_range_default`, baris id 2 melonjak menjadi 450.00 karena engine menganggap id 2 dan 3 adalah peer logis (tanggal sama), sehingga agregasi menyertakan nilai keduanya sekaligus!

#### B. Practical Example: Named Window & Klausa EXCLUDE
Penggunaan klausul `WINDOW` yang dapat digunakan ulang (*reusable*) dan klausa `EXCLUDE` (PostgreSQL 11+) untuk moving average tanpa menyertakan outlier transaksi saat ini.

```sql
SELECT 
    id,
    sold_at,
    amount,
    -- Moving average 2 baris sebelum dan 2 baris sesudah, TANPA menghitung baris saat ini
    AVG(amount) OVER w_surrounding AS moving_avg_peer_only,
    -- Total absolut partisi menggunakan named window yang sama
    COUNT(*) OVER w_partition_wide AS total_tx_in_month
FROM sales_stream
WINDOW 
    w_partition_wide AS (PARTITION BY DATE_TRUNC('month', sold_at)),
    w_surrounding AS (
        w_partition_wide 
        ORDER BY sold_at, id
        ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING 
        EXCLUDE CURRENT ROW
    );
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Skenario: Core-Banking High-Velocity Fraud Detection & Ledger Reconciliation
Sebuah bank digital memproses puluhan juta transaksi per hari. Arsitek data diwajibkan membangun query pipeline analitis harian untuk:
1. **Rekonsiliasi Saldo Buku Besar (*Ledger Running Balance*)**: Menghitung saldo berjalan secara kronologis presisi mikrodetik untuk setiap rekening.
2. **Fraud Detection Velocity Burst**: Menandai transaksi yang terjadi dalam jendela 5 menit terakhir dengan total penarikan melebihi 300% dari rata-rata penarikan per jam selama 24 jam terakhir.

#### Schema DDL & Data Distribution:
```sql
CREATE TABLE core_banking_ledger (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY,
    account_id UUID NOT NULL,
    transaction_time TIMESTAMPTZ NOT NULL,
    transaction_type VARCHAR(16) NOT NULL, -- 'DEBIT', 'CREDIT'
    amount NUMERIC(14, 4) NOT NULL,
    PRIMARY KEY (account_id, transaction_time, entry_id)
);

-- Indeks komposit performa tinggi untuk mengeliminasi sort step
CREATE INDEX idx_ledger_perf_analytics 
ON core_banking_ledger (account_id, transaction_time ASC) 
INCLUDE (amount, transaction_type);
```

#### Analytical Query:
```sql
WITH normalized_ledger AS (
    SELECT 
        entry_id,
        account_id,
        transaction_time,
        transaction_type,
        amount,
        CASE 
            WHEN transaction_type = 'CREDIT' THEN amount 
            ELSE -amount 
        END AS signed_amount
    FROM core_banking_ledger
),
ledger_with_rolling_metrics AS (
    SELECT 
        entry_id,
        account_id,
        transaction_time,
        transaction_type,
        amount,
        signed_amount,
        -- 1. Rekonsiliasi Saldo Akurat (ROWS untuk determinisme mutlak)
        SUM(signed_amount) OVER (
            PARTITION BY account_id 
            ORDER BY transaction_time ASC, entry_id ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS current_account_balance,
        
        -- 2. Fraud Velocity: Total penarikan dalam sliding window 5 menit terakhir
        SUM(CASE WHEN transaction_type = 'DEBIT' THEN amount ELSE 0 END) OVER (
            PARTITION BY account_id 
            ORDER BY transaction_time ASC
            RANGE BETWEEN INTERVAL '5 minutes' PRECEDING AND CURRENT ROW
        ) AS debit_sum_last_5min,
        
        -- 3. Fraud Baseline: Rata-rata penarikan per jam selama 24 jam terakhir
        AVG(CASE WHEN transaction_type = 'DEBIT' THEN amount ELSE 0 END) OVER (
            PARTITION BY account_id 
            ORDER BY transaction_time ASC
            RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND INTERVAL '5 minutes' PRECEDING
        ) AS debit_baseline_avg_24h
    FROM normalized_ledger
)
SELECT 
    entry_id,
    account_id,
    transaction_time,
    transaction_type,
    amount,
    current_account_balance,
    debit_sum_last_5min,
    ROUND(debit_baseline_avg_24h, 2) AS baseline_avg,
    CASE 
        WHEN transaction_type = 'DEBIT' 
             AND debit_sum_last_5min > 10000000 -- threshold nominal Rp 10 Juta
             AND debit_sum_last_5min > (COALESCE(debit_baseline_avg_24h, 0) * 3) 
        THEN TRUE 
        ELSE FALSE 
    END AS is_suspicious_velocity_burst
FROM ledger_with_rolling_metrics
WHERE transaction_time >= NOW() - INTERVAL '7 days';
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Parameter | ROWS Window Framing | RANGE Window Framing | Correlated Subquery / Self-Join |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Waktu** | $\mathcal{O}(N \log N)$ (Unindexed) / $\mathcal{O}(N)$ (Indexed) | $\mathcal{O}(N \log N)$ (Unindexed) / $\mathcal{O}(N)$ (Indexed) | $\mathcal{O}(N^2)$ |
| **Konsumsi Memori** | Sangat Rendah (Pointer sliding konstan). | Moderat - Sangat Tinggi (Harus menahan peer rows di spool). | Ekstrem (Beban Hash Join/Nested Loops). |
| **Kebutuhan I/O Disk** | Rendah (Bila `work_mem` mencukupi untuk sort). | Tinggi jika peer group mendominasi partisi dan tumpah ke disk. | Sangat Tinggi (Membaca ulang halaman buffer berulang kali). |
| **Determinisme Hasil** | **Tinggi**: Setiap baris dievaluasi strictly per physical sequence. | **Kondisional**: Baris dengan nilai `ORDER BY` identik akan berbagi hasil sama. | Bergantung pada klausa `ON` dan sorting unik. |
| **Dukungan Index Scan** | Sepenuhnya dapat memanfaatkan B-Tree composite index. | Sepenuhnya dapat memanfaatkan B-Tree composite index. | Terbatas (Nested loop lookup overhead). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Lupa Menuliskan Frame Definition (Silent Performance Killer)
* **Pola Salah**: Menulis `SUM(amount) OVER (PARTITION BY user_id ORDER BY created_at)` dan mengira perilakunya sama dengan `ROWS`.
* **Gejala Produksi**: Query memakan I/O sangat tinggi, memory spool membengkak, dan hasil perhitungan duplikat pada timestamp yang sama.
* **Solusi**: Selalu nyatakan `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` secara eksplisit jika Anda tidak secara spesifik membutuhkan agregasi peer group logis.

#### Kesalahan 2: Disk Spill pada Node Sort (`work_mem` Under-allocation)
* **Identifikasi**: Jalankan `EXPLAIN (ANALYZE, BUFFERS)`:
  ```text
  Sort (cost=... rows=... width=...) (actual time=... rows=... loops=1)
    Sort Key: account_id, transaction_time
    Sort Method: external merge  Disk: 458752kB  <-- BENCANA: Menulis 450MB ke Disk!
    Buffers: shared hit=1254 read=3421, temp written=57344
  ```
* **Solusi Perbaikan**:
  1. Tingkatkan sementara `work_mem` untuk sesi batch analitikal:
     ```sql
     SET work_mem = '512MB';
     ```
  2. Sediakan Indeks Komposit yang mencakup urutan sort:
     ```sql
     CREATE INDEX idx_account_tx_sorted ON transactions (account_id, transaction_time);
     ```
     Jika indeks ini ada, engine akan mengganti node `Sort` dengan `Index Scan` berbiaya nol untuk pengurutan.

#### Kesalahan 3: Partisi Mengandung Skew Ekstrem (Partition Skew)
* **Masalah**: Melakukan `PARTITION BY tenant_id`, di mana satu tenant memiliki 80% dari total 100 juta baris data.
* **Gejala**: Satu thread CPU bekerja 100% sendirian sementara thread lain telah selesai (pada engine terdistribusi / parallel query).
* **Solusi**: Tambahkan sub-partisi logis atau ubah framing analitik menjadi bounded frame (misal: `ROWS BETWEEN 1000 PRECEDING AND CURRENT ROW`) untuk membatasi ukuran buffer tuplestore in-memory.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Eksplisitkan Framing**: Jangan pernah biarkan SQL parser menggunakan frame implisit pada agregasi dengan `ORDER BY`. Tuliskan secara tegas `ROWS BETWEEN ...` atau `RANGE BETWEEN ...`.
2. [ ] **Verifikasi Execution Plan Bebas dari Node Sort**: Pastikan pada query throughput tinggi, output `EXPLAIN` menampilkan `WindowAgg` langsung di atas `Index Scan` atau `Incremental Sort`, bukan `Sort Method: external merge`.
3. [ ] **Composite Index Ordering**: Urutan kolom pada indeks harus mengikuti hierarki analitik:
   `CREATE INDEX ON tabel (kolom_partition_1, kolom_partition_2, kolom_order_1 ASC, kolom_order_2 ASC) INCLUDE (kolom_payload)`.
4. [ ] **Hindari Window Functions Ganda dengan Partisi Berbeda**: Query yang memiliki:
   `OVER (PARTITION BY A ORDER BY B)` dan `OVER (PARTITION BY C ORDER BY D)` dalam satu SELECT statement akan memaksa engine melakukan **dua kali pengurutan ulang data lengkap** di memori. Usahakan menyamakan partisi atau pisahkan tahapannya menggunakan CTE.
5. [ ] **Batasi Proyeksi Window Function Sebelum Pagination**: Jangan mengeksekusi perhitungan window pada seluruh tabel jika Anda hanya membutuhkan halaman pertama:
   Gunakan subquery berpaginasi atau materialized state jika data berskala miliaran baris.

---

### 12. Hands-on Practice

Simpan seluruh skrip eksekusi ini di: `hands-on/m02/window_perf_lab.sql`

#### Langkah 1: Persiapan Environment & Dummy Data Skala Besar
```sql
-- Buat schema isolasi
CREATE SCHEMA IF NOT EXISTS lab_analytical_sql;
SET search_path TO lab_analytical_sql;

-- Drop tabel jika ada
DROP TABLE IF EXISTS high_volume_events;

-- Buat tabel event streaming
CREATE TABLE high_volume_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_id INT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    metric_value NUMERIC(8,2) NOT NULL
);

-- Generate 500,000 baris data sintetis terdistribusi
INSERT INTO high_volume_events (device_id, recorded_at, metric_value)
SELECT 
    (random() * 100)::INT + 1 AS device_id,
    NOW() - (g || ' seconds')::INTERVAL AS recorded_at,
    (random() * 1000)::NUMERIC(8,2) AS metric_value
FROM generate_series(1, 500000) AS g;

-- Analisis statistik tabel
ANALYZE high_volume_events;
```

#### Langkah 2: Benchmarking & Analisis Explain Plan (Kondisi Tanpa Indeks)
```sql
-- Paksa alokasi memori kecil untuk mendemonstrasikan disk spill
SET work_mem = '4MB';

-- Uji eksekusi query default (RANGE framing)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT 
    device_id,
    recorded_at,
    metric_value,
    AVG(metric_value) OVER (
        PARTITION BY device_id 
        ORDER BY recorded_at
    ) AS rolling_avg
FROM high_volume_events;
```
*Amati keberadaan: `Sort Method: external merge Disk` dan waktu eksekusi.*

#### Langkah 3: Optimasi Framing (Ubah ke ROWS)
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT 
    device_id,
    recorded_at,
    metric_value,
    AVG(metric_value) OVER (
        PARTITION BY device_id 
        ORDER BY recorded_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS rolling_avg
FROM high_volume_events;
```

#### Langkah 4: Optimasi Fisik Skala Enterprise (Index Acceleration)
```sql
-- Buat covering composite index yang sempurna
CREATE INDEX idx_device_events_covering 
ON high_volume_events (device_id ASC, recorded_at ASC) 
INCLUDE (metric_value);

-- Kembalikan work_mem ke nilai wajar
RESET work_mem;

-- Eksekusi ulang query dan periksa execution plan
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT 
    device_id,
    recorded_at,
    metric_value,
    AVG(metric_value) OVER (
        PARTITION BY device_id 
        ORDER BY recorded_at
        ROWS BETWEEN 50 PRECEDING AND CURRENT ROW
    ) AS moving_avg_50
FROM high_volume_events;
```
*Amati perubahannya: Node `Sort` hilang sepenuhnya, digantikan oleh `Index Only Scan` dengan waktu eksekusi yang turun drastis.*

---

### 13. Exercise

#### Level: Easy
Diberikan tabel `employee_salaries (emp_id INT, department_id INT, salary NUMERIC)`. Tulis query untuk menampilkan seluruh kolom, ditambah kolom `diff_from_highest` yang menghitung selisih gaji karyawan saat ini dengan gaji tertinggi di departemennya masing-masing, tanpa menggunakan subquery `MAX()` atau `GROUP BY`.
*Petunjuk: Gunakan `FIRST_VALUE()` atau `MAX() OVER (...)`.*

#### Level: Medium
Diberikan tabel `user_logins (user_id INT, login_time TIMESTAMPTZ)`. Tulis query untuk mendeteksi sesi *churn*. Hitung interval durasi waktu (dalam detik) antara login saat ini dengan login sebelumnya untuk masing-masing user. Jika itu adalah login pertama user tersebut, isi dengan `0`. Batasi komputasi hanya membaca 1 baris sebelumnya secara deterministik fisik.
*Petunjuk: Gunakan `LAG()` dengan default parameter.*

#### Level: Hard
Diberikan data fluktuasi sensor IoT `sensor_readings (sensor_id INT, read_at TIMESTAMPTZ, temperature NUMERIC)`. Terkadang koneksi jaringan bermasalah sehingga nilai sensor menghasilkan pembacaan `NULL`. Tulis query untuk menghasilkan metrik `imputed_temperature` di mana setiap ada nilai `NULL`, nilai tersebut otomatis diisi oleh nilai valid non-NULL terakhir sebelum data tersebut terjadi (*forward-fill pattern*), secara strictly chronological.
*Petunjuk: Pelajari perilaku `LAG() ... IGNORE NULLS` (standar ANSI / PostgreSQL 17+) atau teknik `COUNT(temperature) OVER (...)` grouping window trick.*

---

### 14. Challenge

#### Deskripsi Skenario:
Anda adalah Principal Database Engineer di platform e-Commerce global. Terdapat sistem promosi berbasis "Streak Belanja Harian". Anda diberikan tabel audit transaksi:
`user_orders (order_id BIGINT, user_id UUID, order_date DATE, total_amount NUMERIC)`

Setiap user dapat memiliki **lebih dari satu order dalam satu tanggal yang sama**.

#### Target Implementasi:
Selesaikan permasalahan **Gap-and-Island** murni dengan Analytical Window SQL:
1. Hitung seluruh periode streak belanja (hari berurutan di mana pengguna melakukan minimal 1 pembelian).
2. Tentukan `streak_start_date`, `streak_end_date`, dan `consecutive_days_count` untuk setiap user.
3. Hanya tampilkan pulau belanja (*islands*) yang memiliki durasi minimal **3 hari berturut-turut**.
4. **Batasan Skalabilitas**: Solusi Anda tidak boleh menggunakan `RECURSIVE CTE` dan tidak boleh melakukan self-join `user_orders` terhadap dirinya sendiri. Query harus dapat menyelesaikan 10 juta baris dalam hitungan detik menggunakan single-pass parsing memanfaatkan diferensiasi dua ranking function (`ROW_NUMBER()` / `DENSE_RANK()`).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Kapan klausul Window Functions dieksekusi dalam siklus query relational database standar?
   A. Bersamaan dengan klausul `WHERE`
   B. Sebelum evaluasi `GROUP BY`
   C. Setelah `GROUP BY` dan `HAVING`, tetapi sebelum `ORDER BY` terluar dan `DISTINCT`
   D. Paling terakhir setelah `LIMIT`

2. Apa frame default dari sebuah window function ketika Anda menulis `OVER (ORDER BY transaction_date)` tanpa mendeklarasikan frame secara eksplisit?
   A. `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`
   B. `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`
   C. `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`
   D. `GROUPS BETWEEN 1 PRECEDING AND CURRENT ROW`

3. Apa perbedaan fundamental eksekusi antara framing `ROWS` dan `RANGE`?
   A. `ROWS` bekerja berdasarkan batas nilai logis, sedangkan `RANGE` berdasarkan baris fisik.
   B. `ROWS` mengevaluasi baris fisik independen, sedangkan `RANGE` mengevaluasi peer group dari nilai pengurutan yang identik.
   C. `ROWS` tidak dapat diurutkan secara `DESC`.
   D. `RANGE` tidak mendukung agregasi numerik seperti `SUM()`.

4. Jika output `EXPLAIN ANALYZE` menunjukkan `Sort Method: external merge Disk`, langkah perbaikan pertama yang paling efektif dari sisi konfigurasi memori sesi PostgreSQL adalah...
   A. Menurunkan nilai `shared_buffers`
   B. Menaikkan nilai `work_mem`
   C. Menonaktifkan `enable_seqscan`
   D. Menghapus indeks pada tabel

5. Manakah dari fungsi window berikut yang selalu bernilai deterministik tanpa memerlukan klausa `ORDER BY`?
   A. `ROW_NUMBER()`
   B. `RANK()`
   C. `LEAD()`
   D. `COUNT(*) OVER (PARTITION BY ...)`

---

#### Bagian 2: Intermediate (Analisis Singkat)
6. Mengapa query yang memiliki dua ekspresi window: `OVER (PARTITION BY department_id ORDER BY hire_date)` dan `OVER (PARTITION BY role_id ORDER BY salary)` menghasilkan eksekusi yang lambat pada tabel berukuran besar?
7. Apa fungsi dari klausa `EXCLUDE TIES` dalam frame specification window function?
8. Bagaimana composite index `(client_id, created_at) INCLUDE (amount)` dapat mengoptimalkan query window function `SUM(amount) OVER (PARTITION BY client_id ORDER BY created_at ROWS UNBOUNDED PRECEDING)`? Jelaskan tahapan node query planner yang berhasil dieliminasi!
9. Mengapa penggunaan fungsi `NTH_VALUE(column, n)` sering kali membutuhkan frame eksplisit `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` agar menghasilkan data yang konsisten di semua baris partisi?
10. Sebutkan risiko kegagalan sistem produksi jika query analitik memproses partisi data yang sangat besar (*partition skew*) dengan frame `RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '30 days' FOLLOWING`!

---

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario A (Fintech Out-of-Memory Crash)**:
   Sebuah worker background menghasilkan OOM (Out Of Memory) crash setiap kali menjalankan batch rekonsiliasi bulanan. Query menggunakan:
   ```sql
   SELECT user_id, txn_time, SUM(val) OVER (PARTITION BY user_id ORDER BY txn_time) FROM raw_txns;
   ```
   Tabel memiliki 50 juta transaksi, dan sebagian besar transaksi terkonsentrasi pada beberapa user akun agregator perusahaan. Identifikasi dua akar masalah struktural pada query tersebut dan berikan solusinya!

12. **Skenario B (Audit Anomali Data Ranking)**:
   Sistem leaderboard turnamen game online menampilkan bug: dua pemain dengan skor sama-sama 1000 poin terdaftar di baris berbeda, namun peringkat pemain ketiga melompat dari peringkat 1 langsung ke peringkat 3. Namun, sistem klaim reward mereka mengharapkan peringkat berurutan tanpa jeda angka: `1, 1, 2`. Fungsi ranking apa yang salah dipilih, dan apa fungsi yang seharusnya digunakan? Berikan demonstrasi sintaksnya!

13. **Skenario C (High Latency Index Tuning)**:
   Perhatikan rencana eksekusi berikut:
   ```text
   WindowAgg (cost=125430.22..145630.22 rows=1000000 width=40)
     -> Sort (cost=125430.22..127930.22 rows=1000000 width=32)
          Sort Key: company_id, branch_id, checkin_time
          Sort Method: quicksort Memory: 131072kB
          -> Seq Scan on attendance_records (cost=0.00..25000.00 rows=1000000 width=32)
   ```
   Rancang DDL index yang dapat menghilangkan node `Sort` dan node `Seq Scan` sepenuhnya, dan ubah cost eksekusi menjadi fraction dari cost di atas!

---

### Jawaban Quiz & Pembahasan Evaluasi

#### Kunci Jawaban Bagian 1:
1. **C**: Window function diproses setelah evaluasi grup selesai, tepat sebelum presentation sorting terluar.
2. **C**: Sesuai standar ANSI SQL, jika `ORDER BY` ada tanpa framing, frame bawaan adalah `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`.
3. **B**: `ROWS` bergerak murni berdasarkan counter baris fisik, sedangkan `RANGE` mengevaluasi kesetaraan nilai logis pada kolom sort key.
4. **B**: `external merge Disk` menunjukkan memori pengurutan `work_mem` habis terlampaui sehingga engine beralih menggunakan disk sementara.
5. **D**: Agregasi partisi murni tanpa urutan (`COUNT(*) OVER (PARTITION BY ...)`) tidak sensitif terhadap posisi urutan data.

#### Kunci Jawaban Bagian 2:
6. Karena susunan partisi dan sort key berbeda, Query Optimizer tidak dapat menggunakan urutan data yang sama di memori. Engine harus melakukan alokasi dan komputasi `Sort Node` baru untuk masing-masing window expression.
7. `EXCLUDE TIES` mengeluarkan baris lain yang memiliki nilai order key identik dengan baris saat ini dari frame perhitungan, tetapi tetap mempertahankan baris saat ini (*current row*) di dalam frame.
8. Indeks tersebut sudah menyediakan data dalam keadaan terurut fisik berdasarkan `(client_id, created_at)`. Query planner dapat langsung melakukan **Index Only Scan**, meniadakan node `Sort` (menghemat CPU & RAM) dan meniadakan pembacaan heap table untuk mengambil kolom `amount` karena sudah ada di payload `INCLUDE`.
9. Secara default frame berhenti di `CURRENT ROW`. Jika baris saat ini berada pada posisi lebih kecil dari $n$, `NTH_VALUE(n)` akan mengembalikan `NULL` karena baris ke-$n$ belum terbaca ke dalam window spool.
10. Frame meluas ke dua arah (+30 hari dan -30 hari), memaksa spool buffer in-memory menampung volume baris yang sangat masif sekaligus (membuka jendela ke depan dan ke belakang secara simultan), yang dapat menyebabkan lonjakan alokasi RAM per koneksi secara mendadak.

#### Kunci Jawaban Bagian 3 (Kasus Produksi):
11. **Akar Masalah**:
    * Menggunakan implicit `RANGE` framing pada data agregator bervolume tinggi, memaksa engine melakukan dynamic frame buffering look-ahead.
    * Kurangnya indeks terurut yang sesuai dan nilai `work_mem` sesi yang terlalu kecil memicu tumpahan disk masif atau OOM killer Linux mematikan proses PostgreSQL backend.
    * **Solusi**:
      Ubah framing menjadi:
      `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`
      dan pasang indeks komposit pada `(user_id, txn_time)`.
12. **Akar Masalah**:
    * Sistem menggunakan `RANK()` yang menghasilkan sequence berjarak (*sparse rank*): `1, 1, 3`.
    * **Solusi**:
      Ganti ke fungsi `DENSE_RANK()`, yang menjamin penomoran urutan bertambah 1 angka tanpa memedulikan banyaknya ties (duplikat):
      ```sql
      DENSE_RANK() OVER (ORDER BY score DESC) AS reward_tier
      ```
13. **Rancangan Indeks Solutif**:
    ```sql
    CREATE INDEX idx_attendance_optimized 
    ON attendance_records (company_id ASC, branch_id ASC, checkin_time ASC);
    ```
    Dengan indeks komposit B-Tree multi-kolom ini, Query Planner mengganti `Seq Scan` dan `Sort` menjadi **Index Scan** terurut langsung menuju `WindowAgg`.

---

### 16. Summary

```
                      ENTERPRISE WINDOW FUNCTION CHEAT SHEET
┌──────────────────┬─────────────────────────────┬─────────────────────────────────┐
│ Fitur            │ Perilaku Utama              │ Implikasi Performa              │
├──────────────────┼─────────────────────────────┼─────────────────────────────────┤
│ ROWS             │ Offset baris fisik presisi  │ Paling Cepat, Hemat Memori      │
│ RANGE            │ Offset nilai data logis     │ Butuh Look-ahead Buffering      │
│ GROUPS           │ Offset group data peer      │ Moderat, Menghitung Group Nilai │
│ EXCLUDE          │ Filter internal frame       │ Menghilangkan Operasi Self-Join │
│ WINDOW Clause    │ Deklarasi window modular    │ Optimasi Reusability Query Plan │
└──────────────────┴─────────────────────────────┴─────────────────────────────────┘

Aturan Emas Produksi:
1. Hindari Frame Implisit: Selalu gunakan klausa eksplisit ROWS untuk kalkulasi finansial / saldo berjalan.
2. Eliminasi Sort Node: Pastikan urutan (PARTITION BY ... ORDER BY ...) dicerminkan persis oleh B-Tree Index.
3. Waspadai work_mem: Monitor buffer hit/spill pada EXPLAIN ANALYZE untuk mencegah disk degradation.
```