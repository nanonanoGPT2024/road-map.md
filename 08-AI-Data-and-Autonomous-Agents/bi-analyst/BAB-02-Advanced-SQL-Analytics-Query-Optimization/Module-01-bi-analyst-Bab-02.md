# Bab 02: Advanced SQL Analytics & Query Optimization
**Module 01: High-Performance Analytical SQL & Execution Engine Internals**

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis & Menginterpretasikan Execution Plan**: Mendiagnosis bottleneck query secara presisi menggunakan `EXPLAIN (ANALYZE, BUFFERS, SETTINGS, WAL)` untuk mendeteksi *sequential scan*, *hash spill*, *materialize node*, dan *buffer cache misses*.
*   **Menguasai Frame Specification Tingkat Lanjut**: Mengimplementasikan window functions menggunakan frame specifications eksplisit (`ROWS`, `RANGE`, `GROUPS`), exclusions (`EXCLUDE CURRENT ROW`, `EXCLUDE GROUP`), dan klausa `QUALIFY` tanpa kalkulasi ganda.
*   **Merancang Strategi Indexing Analitis**: Membangun index yang optimal untuk *Read-Heavy Analytical Workloads* (Covering Indexes via `INCLUDE`, Partial Indexes, BRIN untuk time-series data) yang memicu *Index-Only Scan*.
*   **Mengeliminasi Query Anti-Patterns**: Mengidentifikasi dan merefaktor predikat *Non-SARGable*, implicit type casting, *accidental Cartesian products*, dan nesting CTE suboptimal menjadi bentuk aljabar relasional yang efisien.
*   **Mengoptimalkan Alokasi Memory Execution Engine**: Mengonfigurasi dan memprediksi kebutuhan resource engine (`work_mem`, *hash table sizing*, *external merge sort spills*) guna mencegah I/O overhead ke disk.

---

### 2. Concept Overview

Dalam rekayasa data modern dan analitik *business intelligence* skala enterprise, SQL bukan sekadar antarmuka deklaratif untuk mengambil data; SQL adalah spesifikasi transformasi data hierarkis yang diterjemahkan menjadi *Directed Acyclic Graph* (DAG) dari operasi fisik oleh database engine.

#### The Analytical Processing Pipeline
Secara konseptual, pemrosesan query analitis mengikuti urutan evaluasi logis (Logical Query Processing) yang berbeda secara fundamental dari urutan sintaksis penulisan:

```
[1. FROM & JOIN] ──> [2. WHERE] ──> [3. GROUP BY] ──> [4. HAVING]
                                                              │
[8. OFFSET] <── [7. LIMIT] <── [6. SELECT] <── [5. WINDOW] <──┘
                                   │
                              [DISTINCT]
```

Kesalahan mental model terbesar pada *data analyst* adalah memperlakukan SQL secara imperatif atau mengabaikan fase di mana window functions dan agregasi diproses:
1.  **Window Functions dievaluasi setelah `HAVING` dan sebelum `SELECT DISTINCT`**: Artinya, window function tidak dapat difilter secara langsung di klausa `WHERE` tanpa *Common Table Expression* (CTE) atau klausa `QUALIFY`.
2.  **Sintaks Deklaratif vs. Eksekusi Fisik**: Engine (seperti PostgreSQL, DuckDB, Snowflake) menggunakan *Cost-Based Optimizer* (CBO) untuk memetakan *logical operator tree* ke *physical execution tree*. CBO membuat estimasi berdasarkan statistik data (*hyperloglog*, *most common values*, histogram) yang tersimpan di katalog sistem.

---

### 3. Why It Matters

Di lingkungan enterprise kontemporer (skala Terabyte hingga Petabyte), query SQL analitis yang tidak dioptimalkan menimbulkan dampak sistemik:
*   **Biaya Cloud Computing yang Membengkak**: Pada warehouse modern (Snowflake, BigQuery), query analitis yang melakukan *full table scan* dan komputasi shuffle yang buruk secara langsung meningkatkan konsumsi *Warehouse Credits* dan *Slots*. Satu query agregasi yang buruk dapat menghabiskan ribuan dolar per bulan.
*   **Degradasi Latensi Dashboard & Concurrency Bottlenecks**: Ketika BI Engine (seperti Apache Superset, Tableau, PowerBI) mengeksekusi dashboard berskala besar, eksekusi query yang mengalami *disk-spill* memblokir connection pool dan menurunkan throughput sistem dari ratusan *queries per second* (QPS) menjadi hitungan jari.
*   **Reliabilitas Otomasi Agen AI & Semantic Layer**: Autonomous Data Agents yang menghasilkan query SQL secara dinamis membutuhkan query template yang deterministik dan tahan terhadap skalabilitas data. Tanpa pemahaman mendalam tentang *cost estimation*, agen AI akan menghasilkan kueri kartesian yang dapat melumpuhkan database produksi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup pemrosesan query analitis dari representasi string SQL hingga eksekusi node fisik di dalam database engine.

```
       [ Client / BI Tool / AI Agent ]
                      │ (SQL String)
                      ▼
        ┌───────────────────────────┐
        │       Parser & Lexer      │ ──> AST (Abstract Syntax Tree)
        └─────────────┬─────────────┘
                      ▼
        ┌───────────────────────────┐
        │         Rewriter          │ ──> Query Tree (Views expanded,
        └─────────────┬─────────────┘     Rule application)
                      ▼
        ┌───────────────────────────┐
        │   Cost-Based Optimizer    │ <── System Catalogs & Stats
        │           (CBO)           │     (Histograms, MCV, Correlations)
        ├───────────────────────────┤
        │  * Path Enumeration       │
        │  * Costing (CPU vs I/O)   │
        │  * Join Order Selection   │
        └─────────────┬─────────────┘
                      │ (Chosen Physical Plan)
                      ▼
        ┌───────────────────────────────────────────────────────────┐
        │                      Executor Engine                      │
        │                                                           │
        │   ┌───────────────────────────────────────────────────┐   │
        │   │ Aggregate / WindowAgg Node (Frame Buffers)        │   │
        │   └─────────────────────────┬─────────────────────────┘   │
        │                             ▼                             │
        │   ┌───────────────────────────────────────────────────┐   │
        │   │ Hash Join / Merge Join Node                       │   │
        │   └─────────────┬───────────────────────┬─────────────┘   │
        │                 ▼                       ▼                 │
        │   ┌──────────────────────────┐ ┌──────────────────────┐   │
        │   │ Index Scan (Covering)    │ │ Sort Node (work_mem) │   │
        │   └─────────────┬────────────┘ └──────────┬───────────┘   │
        └─────────────────┼─────────────────────────┼───────────────┘
                          │                         │
                          ▼                         ▼
        ┌───────────────────────────────────────────────────────────┐
        │                       Storage Engine                      │
        │  ┌──────────────────────────┐  ┌───────────────────────┐  │
        │  │ Shared Buffer / Cache    │  │ OS Page Cache / Disk  │  │
        │  └──────────────────────────┘  └───────────────────────┘  │
        └───────────────────────────────────────────────────────────┘
```

#### Pipeline Window Function Execution
Pada saat memproses `WINDOW` clause, engine menginisiasi node `WindowAgg`:
1.  **Sorting Phase**: Data dialirkan ke `Sort Node` berdasarkan partisi (`PARTITION BY`) dan urutan (`ORDER BY`). Jika ukuran data melebihi `work_mem`, engine melakukan *External 2-way Merge Sort* ke disk (overhead I/O tinggi).
2.  **Streaming & Partition Framing**: `WindowAgg` node membaca tupel yang telah terurut. Engine mengalokasikan sliding window buffer di memori untuk menghitung fungsi analitis per frame yang ditentukan.

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Window Frame Specifications: `ROWS` vs `RANGE` vs `GROUPS`
Frame specification mengontrol baris mana yang termasuk dalam perhitungan analitis saat ini:

*   **`ROWS`**: Mengukur offset fisik baris.
    *   *Mekanisme*: `ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING` mengevaluasi tepat 1 baris sebelum baris aktif dan 1 baris setelahnya, tidak peduli apakah nilainya duplikat (*ties*).
    *   *Performa*: Sangat cepat karena tidak membutuhkan pengecekan nilai peer.
*   **`RANGE`**: Mengukur offset nilai logis dari ekspresi `ORDER BY`.
    *   *Mekanisme*: `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` menyertakan semua baris dari awal partisi hingga baris yang memiliki nilai kolom yang **sama** (*peers*) dengan baris aktif.
    *   *Default Risk*: Default SQL standard ketika ada klausa `ORDER BY` adalah `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Engine harus memindai seluruh *peer group*, yang memicu pembuatan internal spill buffer jika terdapat banyak duplikasi.
*   **`GROUPS`**: Mengukur offset kelompok nilai yang sama (*peer groups*).
    *   *Mekanisme*: `GROUPS BETWEEN 1 PRECEDING AND 1 FOLLOWING` berarti 1 kelompok nilai identik sebelum kelompok aktif, kelompok aktif itu sendiri, dan 1 kelompok nilai identik setelahnya.

#### B. Anatomi Execution Plan (`EXPLAIN ANALYZE`)
Metrik-metrik krusial yang wajib diperhatikan dalam plan output PostgreSQL:
*   `cost=X..Y`: $X$ adalah startup cost (waktu/resource yang dibutuhkan sebelum node menghasilkan baris pertama), $Y$ adalah total cost untuk mengembalikan seluruh baris.
*   `actual time=A..B`: Waktu eksekusi riil dalam milidetik ($A$ startup, $B$ selesai).
*   `Buffers: shared hit=H read=R dirtied=D written=W`:
    *   `shared hit`: Blok data diambil langsung dari PostgreSQL `shared_buffers` (RAM).
    *   `read`: Blok data dibaca dari OS disk cache atau storage fisik (I/O latency).
    *   Rasio ideal hit: $\frac{\text{shared hit}}{\text{shared hit} + \text{read}} > 0.99$.
*   `Sort Method: external merge Disk: KkB`: Indikator kritis bahwa alokasi `work_mem` tidak cukup untuk menampung dataset proses sorting di memori, memaksa write/read ke disk sementara.

#### C. Join Algorithms
*   **Nested Loop Join**: Kompleksitas $\mathcal{O}(N \times M)$ atau $\mathcal{O}(N \log M)$ jika *inner table* terindeks. Sangat efisien untuk *outer table* yang sangat kecil dan *inner table* berindeks.
*   **Hash Join**: Kompleksitas $\mathcal{O}(N + M)$. Membaca *inner table*, membangun in-memory hash table, kemudian memindai *outer table* untuk mencari kecocokan. Jika hash table melebihi ukuran memori, terjadi *multi-batch hash spill*.
*   **Merge Join**: Kompleksitas $\mathcal{O}(N \log N + M \log M)$ untuk sorting, atau $\mathcal{O}(N + M)$ jika kedua tabel sudah terurut via Index. Menggabungkan dua dataset terurut seperti operasi *two-pointer*. Ideal untuk operasi agregasi data berukuran masif.

---

### 6. Production-Ready Code Implementation

Skenario: Platform FinTech Global dengan miliaran data transaksi. Kebutuhan: Menghitung **Daily Customer Cumulative Spend**, **Trailing 7-Day Moving Average**, **Customer Tiering Lifecycle**, dan **Cohort Month-over-Month Retention**, tanpa memicu disk spills dan meminimalisir I/O scans.

#### 1. Skema Basis Data dan Strategi Indexing Tingkat Lanjut (DDL)

```sql
-- DDL Engine: PostgreSQL 15+
CREATE SCHEMA IF NOT EXISTS fintech_analytics;
SET search_path TO fintech_analytics, public;

-- Hapus tabel jika sudah ada sebelumnya
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS customer_profiles CASCADE;

-- Tabel Master Customer
CREATE TABLE customer_profiles (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signup_timestamp TIMESTAMPTZ NOT NULL,
    country_code VARCHAR(3) NOT NULL,
    risk_segment VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- Tabel Transaksi Finansial
CREATE TABLE transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY,
    customer_id BIGINT NOT NULL,
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    fee_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    status VARCHAR(20) NOT NULL,
    payment_method VARCHAR(30) NOT NULL,
    CONSTRAINT fk_customer FOREIGN KEY (customer_id) REFERENCES customer_profiles(customer_id)
) PARTITION BY RANGE (transaction_timestamp);

-- Implementasi Declarative Partitioning Berdasarkan Rentang Waktu (Monthly)
CREATE TABLE transactions_2024_m01 PARTITION OF transactions
    FOR VALUES FROM ('2024-01-01 00:00:00+00') TO ('2024-02-01 00:00:00+00');

CREATE TABLE transactions_2024_m02 PARTITION OF transactions
    FOR VALUES FROM ('2024-02-01 00:00:00+00') TO ('2024-03-01 00:00:00+00');

CREATE TABLE transactions_2024_m03 PARTITION OF transactions
    FOR VALUES FROM ('2024-03-01 00:00:00+00') TO ('2024-04-01 00:00:00+00');

-- 1. Covering Index untuk Index-Only Scans pada Agregasi Finansial
-- Mencakup customer_id dan transaction_timestamp sebagai key, amount dan fee_amount sebagai payload.
CREATE INDEX idx_transactions_cust_ts_covering 
ON transactions (customer_id, transaction_timestamp DESC) 
INCLUDE (amount, fee_amount)
WHERE status = 'SETTLED';

-- 2. Partial Index untuk Filtering Transaksi Bermasalah
CREATE INDEX idx_transactions_failed_investigation 
ON transactions (customer_id, transaction_timestamp)
WHERE status IN ('FAILED', 'DISPUTED');

-- 3. BRIN Index untuk Audit Data Historis Skala Besar
CREATE INDEX idx_transactions_brin_timestamp 
ON transactions USING BRIN (transaction_timestamp) 
WITH (pages_per_range = 128);
```

#### 2. Query Analitis Kompleks Teroptimasi (Advanced SQL Analytics)

Query ini mendemonstrasikan frame specification eksplisit, CTE terpredikat, window partitioning, dan agregasi multi-dimensi menggunakan `GROUPING SETS`.

```sql
WITH settled_daily_tx AS (
    -- Materialized Pre-Aggregation CTE untuk meminimalkan baris sebelum windowing
    SELECT 
        t.customer_id,
        DATE_TRUNC('day', t.transaction_timestamp) AS tx_date,
        SUM(t.amount) AS total_daily_amount,
        COUNT(t.transaction_id) AS daily_tx_count
    FROM transactions t
    WHERE 
        -- SARGable Range Predicate (Memaksimalkan Partition Pruning & Index Scan)
        t.transaction_timestamp >= '2024-01-01 00:00:00+00' 
        AND t.transaction_timestamp < '2024-03-01 00:00:00+00'
        AND t.status = 'SETTLED'
    GROUP BY 
        t.customer_id,
        DATE_TRUNC('day', t.transaction_timestamp)
),
window_calculations AS (
    SELECT 
        s.customer_id,
        s.tx_date,
        s.total_daily_amount,
        s.daily_tx_count,
        
        -- A. Cumulative Spend dengan Frame ROWS eksplisit (Mencegah default RANGE overhead)
        SUM(s.total_daily_amount) OVER (
            PARTITION BY s.customer_id 
            ORDER BY s.tx_date ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_spend,

        -- B. Trailing 7-Day Moving Average
        AVG(s.total_daily_amount) OVER (
            PARTITION BY s.customer_id 
            ORDER BY s.tx_date ASC
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS trailing_7d_avg_spend,

        -- C. Lead Comparison: Mendeteksi rentang hari hingga transaksi berikutnya
        LEAD(s.tx_date, 1) OVER (
            PARTITION BY s.customer_id 
            ORDER BY s.tx_date ASC
        ) - s.tx_date AS days_until_next_tx,

        -- D. Dense Ranking untuk segmentasi frekuensi spending
        DENSE_RANK() OVER (
            PARTITION BY s.customer_id 
            ORDER BY s.total_daily_amount DESC
        ) AS daily_spend_rank
    FROM settled_daily_tx s
)
SELECT 
    w.customer_id,
    c.country_code,
    c.risk_segment,
    w.tx_date,
    w.total_daily_amount,
    w.cumulative_spend,
    ROUND(w.trailing_7d_avg_spend, 2) AS trailing_7d_avg_spend,
    COALESCE(w.days_until_next_tx, INTERVAL '0 days') AS days_until_next_tx,
    CASE 
        WHEN w.cumulative_spend >= 100000.00 THEN 'PLATINUM'
        WHEN w.cumulative_spend >= 25000.00 THEN 'GOLD'
        ELSE 'STANDARD'
    END AS customer_tier
FROM window_calculations w
INNER JOIN customer_profiles c ON w.customer_id = c.customer_id
WHERE w.daily_spend_rank <= 5 -- Filter analitis tanpa subquery tambahan
ORDER BY 
    w.customer_id ASC, 
    w.tx_date ASC;
```

#### 3. Python Orchestrator & Execution Plan Profiler

Script enterprise-grade Python untuk memvalidasi performa query, mengekstrak metrik `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, dan menegakkan *Zero Disk Spill Tolerance*.

```python
"""
Execution Plan Profiler and Optimization Enforcer
Track: AI, Data, and Autonomous Agents - BI Analyst Specialization
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple
import psycopg2
from psycopg2.extensions import connection as PgConnection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("QueryOptimizer")

class QueryExecutionProfiler:
    def __init__(self, conn: PgConnection):
        self.conn = conn

    def profile_query(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Dict[str, Any]:
        """
        Executes EXPLAIN with execution flags and asserts performant query plan.
        """
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, COSTS, TIMING, FORMAT JSON) {query}"
        
        with self.conn.cursor() as cursor:
            # Set work_mem lokal untuk simulasi constraint analitik produksi
            cursor.execute("SET LOCAL work_mem = '64MB';")
            
            logger.info("Executing analytical query with execution instrumentation...")
            cursor.execute(explain_query, params or ())
            result = cursor.fetchone()
            
            if not result or not result[0]:
                raise RuntimeError("Failed to retrieve execution plan from engine.")
            
            plan_root = result[0][0]
            
        return self._extract_metrics(plan_root)

    def _extract_metrics(self, plan_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively traverses plan tree to inspect Disk Spills and Buffer Hit Ratios.
        """
        metrics = {
            "TotalExecutionTimeMs": plan_json.get("Execution Time", 0.0),
            "TotalPlanningTimeMs": plan_json.get("Planning Time", 0.0),
            "TotalCost": plan_json.get("Plan", {}).get("Total Cost", 0.0),
            "SharedHitBlocks": 0,
            "SharedReadBlocks": 0,
            "HasDiskSpill": False,
            "SpillDetails": []
        }

        def traverse_node(node: Dict[str, Any]) -> None:
            # Akumulasi Buffer Usage
            metrics["SharedHitBlocks"] += node.get("Shared Hit Blocks", 0)
            metrics["SharedReadBlocks"] += node.get("Shared Read Blocks", 0)

            # Deteksi Disk Spill pada Operasi Sort
            if node.get("Sort Space Type") == "Disk":
                metrics["HasDiskSpill"] = True
                metrics["SpillDetails"].append({
                    "Node": node.get("Node Type"),
                    "SpillSizeKB": node.get("Sort Space Used", 0)
                })

            # Deteksi Disk Spill pada Hash Aggregation
            if node.get("HashAgg Batches", 0) > 1:
                metrics["HasDiskSpill"] = True
                metrics["SpillDetails"].append({
                    "Node": node.get("Node Type"),
                    "Batches": node.get("HashAgg Batches")
                })

            # Rekursi Child Nodes
            for sub_plan in node.get("Plans", []):
                traverse_node(sub_plan)

        traverse_node(plan_json.get("Plan", {}))
        
        total_blocks = metrics["SharedHitBlocks"] + metrics["SharedReadBlocks"]
        metrics["BufferCacheHitRatio"] = (
            (metrics["SharedHitBlocks"] / total_blocks) if total_blocks > 0 else 1.0
        )

        return metrics

# Contoh penggunaan profiler
if __name__ == "__main__":
    DB_CONFIG = {
        "dbname": "fintech_db",
        "user": "postgres",
        "password": "secure_password",
        "host": "localhost",
        "port": 5432
    }

    TEST_SQL = """
        SELECT customer_id, SUM(amount) 
        FROM fintech_analytics.transactions 
        WHERE status = 'SETTLED'
        GROUP BY customer_id
        ORDER BY SUM(amount) DESC 
        LIMIT 100;
    """

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            profiler = QueryExecutionProfiler(conn)
            perf_profile = profiler.profile_query(TEST_SQL)
            
            logger.info("Performance Profile Report:")
            print(json.dumps(perf_profile, indent=2))
            
            if perf_profile["HasDiskSpill"]:
                logger.error("PRODUCTION GATE FAILURE: Query triggered external disk spills!")
            elif perf_profile["BufferCacheHitRatio"] < 0.95:
                logger.warning("PERFORMANCE WARNING: Low cache hit ratio. Verify Index Strategy.")
            else:
                logger.info("PRODUCTION READY: Query fulfills SLA criteria.")

    except psycopg2.OperationalError as db_err:
        logger.error("Database connection failure: %s", db_err)
    except Exception as exc:
        logger.critical("Unexpected optimization pipeline failure: %s", exc)
```

---

### 7. Edge Cases & Failure Modes

#### 1. Data Skew & Hash Bucket Overflow
*   **Kasus**: Nilai kolom join atau partisi terpusat secara masif pada nilai tunggal (misal, `customer_id = 0` untuk guest checkout).
*   **Dampak Fisik**: Hash table pada *Hash Join* atau *HashAggregate* mengalokasikan satu *bucket* raksasa. Hal ini menyebabkan degradasi waktu pencarian dari $\mathcal{O}(1)$ menjadi $\mathcal{O}(N)$ dan memicu *work_mem disk thrashing*.
*   **Mitigasi**: Pisahkan proses tracking non-registered users via conditional aggregation atau CTE khusus:
    ```sql
    -- Skew Split Pattern
    WITH skew_data AS (
        SELECT * FROM transactions WHERE customer_id IS NULL
    ),
    normal_data AS (
        SELECT * FROM transactions WHERE customer_id IS NOT NULL
    )
    -- Lakukan join terpisah dan satukan dengan UNION ALL
    ```

#### 2. SARGability Trap: Manipulasi Fungsi pada Kolom Predikat
*   **Kasus**: Menulis kondisi `WHERE CAST(transaction_timestamp AS DATE) = '2024-01-15'`.
*   **Dampak Fisik**: Engine dipaksa mengevaluasi fungsi untuk setiap baris (*Full Table Scan*). B-Tree Index pada `transaction_timestamp` diabaikan sepenuhnya.
*   **Solusi Benar (SARGable)**:
    ```sql
    WHERE transaction_timestamp >= '2024-01-15 00:00:00+00' 
      AND transaction_timestamp <  '2024-01-16 00:00:00+00'
    ```

#### 3. Frame Null Semantics & Window Frame Creep
*   **Kasus**: Penggunaan `COUNT(column)` vs `COUNT(*)` dalam window sliding frames. Jika kolom bernilai `NULL`, `COUNT(column)` mengabaikan nilainya, menghasilkan denominator yang salah saat menghitung moving averages.
*   **Solusi**: Terapkan penanganan nilai eksplisit dengan `COALESCE` dan kalkulasi *division by zero defense*:
    ```sql
    ROUND(
        SUM(amount) OVER w / NULLIF(COUNT(amount) OVER w, 0),
        4
    )
    WINDOW w AS (PARTITION BY customer_id ORDER BY tx_date ROWS 6 PRECEDING)
    ```

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | CTE (Common Table Expressions) | Subqueries (Inline) | Materialized Views | Temporary Tables |
| :--- | :--- | :--- | :--- | :--- |
| **Materialization Overhead** | Default `NOT MATERIALIZED` (Inline optimizer rewrite) di Postgres 12+ | Terinjeksi langsung ke query plan optimizer | Terkalkulasi penuh dan persisten di disk fisik | Ditulis ke buffer sementara/disk per session |
| **Indexability** | Tidak dapat diindeks secara independen | Menggunakan indeks tabel dasar | Dapat memiliki indeks tersendiri (B-Tree, GiST, BRIN) | Dapat diindeks selama masa aktif session |
| **Memory Footprint** | Menggunakan alokasi pipeline memory query | Identik dengan CTE (bergantung tree optimizer) | Nol saat pembacaan (selain shared buffer page) | Mengonsumsi memory session & disk `temp_buffers` |
| **Use Case Terbaik** | Modularisasi logika query & komputasi window multi-tahap | Dynamic filters skalar tunggal (`IN`, `EXISTS`) | Agregasi analitis masif yang toleran terhadap stale data | ETL multi-tahap dengan transformasi iterative berulang |

---

### 9. Best Practices & Standard Industri

1.  **Strict Rule of Frame Specification**: Jangan pernah menulis `OVER (PARTITION BY ... ORDER BY ...)` tanpa frame eksplisit kecuali secara sadar memerlukan `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`. Gunakan `ROWS BETWEEN ...` untuk kestabilan performa linear.
2.  **Explicit Column Projection**: Larang keras `SELECT *` dalam kode analitis produksi. Selalu definisikan kolom secara eksplisit guna memungkinkan CBO memilih strategi *Index-Only Scan*.
3.  **Automated SQL Linting & Validation**: Integrasikan `sqlfluff` ke dalam pipeline CI/CD analytics engineering:
    ```bash
    # Command eksekusi validasi standar ANSI/PostgreSQL
    sqlfluff lint analytics_query.sql --dialect postgres --rules LT01,LT02,CP01,RF02
    ```
4.  **Buffer Cache Priming & Verification Protocol**:
    *   Sebelum menaikkan query analitis ke tier produksi, jalankan benchmark 3 kali: Run 1 (Cold cache), Run 2 & 3 (Warm cache).
    *   Pastikan total blok `read` berkurang drastis mendekati 0 pada Warm cache.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Principal BI Analyst yang menemukan query analitis dashboard berjalan selama **48 detik** pada dataset 10 juta baris, menyebabkan memory exhaustion pada database PostgreSQL.

#### Langkah 1: Setup Lingkungan dan Dummy Data Generator

```sql
-- Buat environment pengujian terisolasi
CREATE SCHEMA IF NOT EXISTS lab_perf;
SET search_path TO lab_perf, public;

CREATE TABLE sales_orders (
    order_id INT GENERATED ALWAYS AS IDENTITY,
    customer_id INT NOT NULL,
    order_date DATE NOT NULL,
    order_amount NUMERIC(10,2) NOT NULL,
    region VARCHAR(10) NOT NULL
);

-- Generate 1,000,000 baris data sintetis
INSERT INTO sales_orders (customer_id, order_date, order_amount, region)
SELECT 
    (random() * 50000)::INT + 1,
    DATE '2023-01-01' + ((random() * 365)::INT),
    ROUND((random() * 500 + 10)::NUMERIC, 2),
    (ARRAY['APAC', 'EMEA', 'LATAM', 'NA'])[(random() * 3)::INT + 1]
FROM generate_series(1, 1000000);

-- Refresh statistik database
VACUUM ANALYZE sales_orders;
```

#### Langkah 2: Eksekusi Query Naive (Anti-Pattern) & Profiling

Query naive berikut menggunakan `Self-Join` berulang untuk menghitung moving average dan filtering berbasis subquery tanpa indeks.

```sql
-- AMATI: Catat Execution Time dan Buffer Read
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    a.order_id,
    a.customer_id,
    a.order_date,
    a.order_amount,
    (
        -- Anti-Pattern: Correlated Subquery untuk Rolling Avg
        SELECT AVG(b.order_amount)
        FROM sales_orders b
        WHERE b.customer_id = a.customer_id
          AND b.order_date BETWEEN a.order_date - INTERVAL '7 days' AND a.order_date
    ) AS rolling_7d_avg
FROM sales_orders a
WHERE TO_CHAR(a.order_date, 'YYYY-MM') = '2023-06' -- Non-SARGable
ORDER BY a.customer_id, a.order_date;
```
*Identifikasi Masalah*: Perhatikan lonjakan startup cost, jutaan *Buffer Hits/Reads*, serta penggunaan algoritma Nested Loop yang lambat.

#### Langkah 3: Refactoring Teroptimasi (Production-Grade)

Terapkan teknik optimasi yang telah dipelajari:
1.  Ganti Correlated Subquery dengan Window Function ber-frame `ROWS`.
2.  Ubah `TO_CHAR` menjadi SARGable Date Interval.
3.  Bangun Index yang tepat.

```sql
-- 1. Buat Composite Index Optimal
CREATE INDEX idx_sales_cust_date_amount 
ON sales_orders (customer_id, order_date ASC) 
INCLUDE (order_amount);

-- Refresh statistik pasca indexing
ANALYZE sales_orders;

-- 2. Query Hasil Refactoring
EXPLAIN (ANALYZE, BUFFERS)
WITH filtered_orders AS (
    SELECT 
        order_id,
        customer_id,
        order_date,
        order_amount
    FROM sales_orders
    WHERE 
        -- SARGable Range Predicate
        order_date >= DATE '2023-06-01' 
        AND order_date < DATE '2023-07-01'
)
SELECT 
    order_id,
    customer_id,
    order_date,
    order_amount,
    AVG(order_amount) OVER (
        PARTITION BY customer_id 
        ORDER BY order_date ASC
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_avg
FROM filtered_orders
ORDER BY customer_id, order_date;
```

#### Langkah 4: Verifikasi & Evaluasi Hasil Optimasi
Bandingkan output `EXPLAIN (ANALYZE, BUFFERS)` antara Langkah 2 dan Langkah 3:
1.  Berapa persentase reduksi total execution time? (Ekspektasi: Penurunan latensi $> 90\%$).
2.  Apakah strategi scan berubah dari `Seq Scan` menjadi `Index Only Scan` atau `Bitmap Index Scan`?
3.  Pastikan tidak ada entri `Sort Space Type: Disk` pada report plan yang dihasilkan. Output harus murni diselesaikan di memory engine.