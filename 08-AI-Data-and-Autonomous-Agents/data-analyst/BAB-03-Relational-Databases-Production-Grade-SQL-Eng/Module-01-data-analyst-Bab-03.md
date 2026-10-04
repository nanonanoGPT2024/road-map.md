# Bab 03: Relational Databases & Production-Grade SQL Engineering

## Modul 01: Relational Engine Internals, Query Optimization, dan Idempotent Data Pipelines

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis Siklus Hidup Eksekusi Kueri:** Membedah tahap parsing, rewriting, planning, dan execution pada PostgreSQL engine menggunakan instrumen profil bawaan (`EXPLAIN (ANALYZE, BUFFERS)`).
- **Mendiagnosis dan Mengeliminasi Bottleneck I/O:** Mengidentifikasi sequential scans, disk spills (eksternal sort/hash), dan buffer churn, lalu merancang intervensi indeks struktural (B-Tree, Covering Index) yang tepat.
- **Mengembangkan Window Functions Tingkat Lanjut:** Mengimplementasikan kalkulasi agregasi bergerak, running totals, deduplikasi berbasis ranking, dan time-series gap filling dengan optimasi frame specification (`ROWS BETWEEN`).
- **Membangun Pipeline Data Analitik Idempoten:** Mengimplementasikan pola Upsert (`INSERT ... ON CONFLICT`) dan pemrosesan batch bertahap (chunking) menggunakan Python (SQLAlchemy 2.0 & Psycopg3) dengan penanganan transaksi atomik serta isolasi konkurensi tingkat enterprise.
- **Memitigasi Perangkap Logika SQL:** Mengatasi anomali *three-valued logic* akibat nilai `NULL`, mencegah regresi performa correlated subqueries, dan memitigasi deadlock pada skenario konkurensi analitik tinggi.

---

### 2. Concept Overview

Dalam rekayasa data modern untuk analitik dan sistem AI hilir (*downstream AI/ML pipelines*), database relasional bukan sekadar tempat penyimpanan data statis. Database relasional adalah **mesin komputasi data terstruktur yang terikat pada aljabar relasional**.

```
+-----------------------------------------------------------------------+
|                             MENTAL MODEL                              |
|                                                                       |
|   Declarative SQL ("WHAT")  --->  Relational Algebra Rewrite          |
|                                         |                             |
|                                         v                             |
|   Cost-Based Optimizer (CBO) ---> Plan Selection (Stats & Cost)       |
|                                         |                             |
|                                         v                             |
|   Execution Engine ("HOW")  --->  Tuple Streaming / Buffer Pool Access|
+-----------------------------------------------------------------------+
```

Model mental utama SQL produksi adalah sifatnya yang **deklaratif**: seorang Data Analyst mendefinisikan *apa* data yang diinginkan, bukan *bagaimana* algoritma penelusurannya dijalankan secara prosedural. Tugas penentuan algoritma diserahkan sepenuhnya kepada **Cost-Based Optimizer (CBO)**.

Namun, CBO bergantung pada:
1. Statistik tabel (`pg_statistic` / `ANALYZE`) yang rentan usang.
2. Estimasi biaya disk I/O (`random_page_cost` vs `seq_page_cost`).
3. Limitasi memori kerja lokal (`work_mem`).

Jika kueri analitik ditulis tanpa memahami arsitektur internal mesin relasional, CBO dapat memilih rencana eksekusi terburuk: memuat jutaan baris ke memori virtual, menyebabkan *disk spill* (menulis *scratch files* sementara ke disk lokal), dan mengunci tabel (*table locking contention*). Kueri analitik produksi harus dirancang deterministik, *cache-friendly*, meminimalkan pembacaan blok memori (*page hits/reads*), dan bersifat **idempoten** (dapat dieksekusi berulang kali tanpa menghasilkan data duplikat atau status korup).

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan optimasi SQL oleh tim analitik berdampak langsung pada stabilitas infrastruktur dan keandalan data AI:
- **Out-of-Memory (OOM) Crashes:** Analisis data besar yang menggunakan window functions tanpa partisi atau pengurutan masif tanpa alokasi `work_mem` yang tepat dapat memicu Linux OOM-killer pada server basis data transaksional utama (OLTP).
- **Silent Degradation pada Feature Store AI:** Model machine learning yang mengonsumsi *batch feature* dari SQL query yang tidak stabil akan mengalami *feature drift* jika logika pengurutan (`ORDER BY`) tidak deterministik saat menangani nilai timestamp identik.
- **Write-Amplification & Lock Contention:** Transformasi ELT yang ceroboh mengunci baris (*row locks*) terlalu lama atau memicu penulisan Transaction Log (WAL - Write-Ahead Logging) secara berlebihan, menyebabkan replikasi database replika (*read replica lag*) tertinggal ribuan detik.
- **Biaya Komputasi Cloud:** Pada platform seperti AWS Aurora PostgreSQL atau Google Cloud SQL, efisiensi buffer I/O menentukan ukuran instans dan biaya tagihan bulanan. Kueri yang hemat I/O menghemat ribuan dolar biaya operasional per bulan.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memvisualisasikan perjalanan internal dari string SQL mentah hingga hasil tuple dikembalikan ke klien, melewati memori dan media penyimpanan PostgreSQL.

```
                              CLIENT (Data Analyst / Python Service)
                                               |
                                     [SQL Query Text]
                                               |
===============================================v===============================================
POSTGRESQL BACKEND ARCHITECTURE (Backend Process)
                                               |
   +-------------------------------------------v-------------------------------------------+
   | 1. PARSER & ANALYZER                                                                  |
   |    - Lexical & Syntactic Analysis (Tokens -> Abstract Syntax Tree / AST)              |
   |    - Semantic Analysis (Validasi katalog skema, tipe data kolom, hak akses)           |
   +-------------------------------------------+-------------------------------------------+
                                               | [Query Tree]
   +-------------------------------------------v-------------------------------------------+
   | 2. REWRITER                                                                           |
   |    - Transformasi View Rules, Inline CTEs (jika non-materialized)                     |
   +-------------------------------------------+-------------------------------------------+
                                               | [Rewritten Query Tree]
   +-------------------------------------------v-------------------------------------------+
   | 3. COST-BASED OPTIMIZER / PLANNER                                                     |
   |    - Evaluasi Join Order (Genetic Algorithm / Dynamic Programming)                    |
   |    - Pemilihan Metode Akses: Sequential Scan, Index Scan, Bitmap Index Scan           |
   |    - Kalkulasi Biaya (Cost = (Pages * page_cost) + (Tuples * cpu_tuple_cost))         |
   +-------------------------------------------+-------------------------------------------+
                                               | [Execution Plan: Plan Nodes Tree]
   +-------------------------------------------v-------------------------------------------+
   | 4. EXECUTOR (Demand-Driven Iterator / Volcano Engine)                                 |
   |    - Memanggil node teratas (.ExecProcNode()), turun rekursif ke bawah                |
   |    - Menggunakan Work Memory (work_mem) untuk Sorting / Hash Tables                    |
   |    - Menangani Disk Spill ke scratch file jika work_mem terlampaui                    |
   +-----------------------+---------------------------------------+-----------------------+
                           | Read/Write Request                    | Eviction / Flush
                           v                                       v
+------------------------------------------------------+  +--------------------------------+
| SHARED BUFFERS (Database Buffer Pool Cache)          |  | WAL BUFFER                     |
| - Hash Table (Buffer Tag -> Buffer Descriptor)       |  | (Write-Ahead Logging Stream)   |
| - Clock Sweep Page Replacement Algorithm             |  | - Menjamin Durabilitas (ACID)  |
+--------------------------+---------------------------+  +---------------+----------------+
                           | Page Miss                                    | WAL Flush
                           v                                              v
===========================v==============================================v====================
OPERATING SYSTEM & STORAGE ENGINE (Kernel Page Cache & NVMe Disk)
   +---------------------------------------------------+  +--------------------------------+
   | Table Heap Files (.data) & Index Storage (.index) |  | WAL Files (pg_wal/)            |
   +---------------------------------------------------+  +--------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Siklus Eksekusi Mesin Kueri (The Volcano Iterator Model)
PostgreSQL menggunakan *Volcano Iterator Model* (dinamakan juga model *open-next-close*). Setiap simpul pada pohon *Execution Plan* bertindak sebagai iterator yang menyediakan fungsi antarmuka dasar:
- `InitPlan()`: Inisialisasi struktur internal simpul dan alokasi sumber daya memori.
- `ProcNode()`: Mengembalikan tepat satu tuple baru setiap kali dipanggil, atau sinyal `EOF` jika pemrosesan selesai.
- `EndPlan()`: Membersihkan alokasi memori dan menutup akses berkas.

Akibat mekanisme ini, pemrosesan kueri berjalan secara *pipelined/streaming* antar-operator, **kecuali** terdapat operator pemblokir (*pipeline breaker* atau *materializing operators*) seperti:
- `Sort`: Harus membaca seluruh tuple sebelum baris pertama dengan nilai terendah/tertinggi dapat ditentukan.
- `Hash Join`: Harus membaca seluruh data tabel dimensi (*build phase*) untuk membangun hash table di memori sebelum mencocokkan dengan tabel transaksi (*probe phase*).

#### 5.2. Anatomi Indeks B-Tree dan Mekanisme Akses Data
Struktur indeks *B-Tree* di PostgreSQL adalah pohon n-arah berimbang (*balanced multi-way search tree*) yang dioptimalkan untuk penyimpanan blok berbasis halaman (*pages* berukuran default 8 KB).

```
                            [ ROOT PAGE ]
                           | 100 | 500 |
                          /      |      \
                         /       |       \
       +----------------+        |        +----------------+
       v                         v                         v
 [ INTERNAL PAGE ]        [ INTERNAL PAGE ]        [ INTERNAL PAGE ]
 | 10 | 40 | 80 |         | 150 | 250 |            | 600 | 800 |
   /    |    \               /     \                  /     \
  v     v     v             v       v                v       v
+----+----+----+         +----+----+----+          +----+----+----+
|LEAF PAGE (Data)|<=====>|LEAF PAGE (Data)|<======>|LEAF PAGE (Data)|
|TID: (blk,off)  |       |TID: (blk,off)  |        |TID: (blk,off)  |
+----------------+       +----------------+        +----------------+
       |                         |                         |
       +-------------------------+-------------------------+
                                 |  Heap Fetch
                                 v
                 [ HEAP STORAGE (Table Data Pages) ]
```

Tipe akses data relasional terbagi atas tiga varian utama:
1. **Index Scan:** Mesin mencari nilai pada B-Tree dari Root $\rightarrow$ Internal $\rightarrow$ Leaf. Daun indeks menyimpan pointer `ItemPointerData` (dikenal sebagai Tuple ID / `TID`: kombinasi nomor blok dan offset indeks tuple dalam blok). Mesin kemudian melakukan *random read* ke *Heap file* untuk memvalidasi visibilitas transaksi (MVCC).
2. **Index Only Scan:** Jika seluruh kolom yang diminta kueri terdapat di dalam daun indeks (misal melalui *Covering Index* menggunakan klausul `INCLUDE`), dan halaman heap yang bersangkutan berstatus *all-visible* pada *Visibility Map*, mesin tidak perlu membaca Heap sama sekali. Ini adalah jalur pembacaan tercepat.
3. **Bitmap Index Scan:** Jika pencarian menghasilkan banyak baris yang tersebar, engine membentuk bitmap di memori (`TID Bitmap`), menggabungkan beberapa kondisi indeks via operasi bitwise (`AND`/`OR`), lalu mengurutkan akses blok heap secara fisik untuk mengubah *random I/O* menjadi *sequential-like I/O*.

#### 5.3. Multi-Version Concurrency Control (MVCC) & Visibility Check
PostgreSQL mengelola konkurensi data tanpa kunci pembaca (*readers do not block writers, writers do not block readers*) melalui MVCC.
Setiap baris (*tuple*) pada heap fisik memiliki metadata tersembunyi:
- `xmin`: Nomor Transaction ID (XID) yang memasukkan (*insert*) tuple tersebut.
- `xmax`: Nomor XID yang memperbarui (*update*) atau menghapus (*delete*) tuple tersebut (bernilai 0 jika masih aktif).

Saat kueri dijalankan pada level isolasi default `READ COMMITTED`, engine mengambil *Snapshot* transaksional yang merekam status XID aktif pada saat kueri dimulai. Baris dinyatakan terlihat (*visible*) jika:
$$\text{xmin} \le \text{Snapshot.xmax\_limit} \land \text{xmin did not fail/abort} \land (\text{xmax is 0} \lor \text{xmax is not visible to Snapshot})$$

Dampak Analitik:
- Update data pada PostgreSQL tidak mengganti nilai di tempat (*in-place update*), melainkan menandai `xmax` tuple lama dan membuat tuple baru dengan `xmin` baru.
- Tanpa proses pembersihan (*VACUUM*) yang teratur, terjadi fenomena **Table Bloat**. Analis data yang melakukan pemindaian penuh (*Full Table Scan*) akan terpaksa memuat *dead tuples* ke dalam *Shared Buffers*, merusak efisiensi cache sistem.

#### 5.4. Work Memory (`work_mem`) & Disk Spilling Internals
Variabel `work_mem` menentukan batas alokasi memori internal sebelum operator `ORDER BY`, `DISTINCT`, window aggregate, atau Hash Join membuang data sementara ke disk (*temporary files*).
- Jika ukuran data $\le \text{work\_mem}$: Engine menggunakan in-memory quicksort atau hash table berkecepatan tinggi.
- Jika ukuran data $> \text{work\_mem}$: Engine beralih ke **External Merge Sort** atau **Multi-batch Hash Join**. Data dipecah menjadi batch-batch kecil, disimpan ke direktori `pgsql_tmp`, lalu digabung kembali (*n-way external merge*).
- Fenomena ini meningkatkan latensi query dari skala milidetik ke detik atau menit akibat latensi penulisan disk sekunder.

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem ekstraksi analitik end-to-end yang mengimplementasikan:
1. Skema database teroptimasi lengkap dengan indeks fungsional, covering index, dan partisi bulanan.
2. Skrip orkestrator Python berbasis **SQLAlchemy 2.0 Core** dan **Psycopg3** yang aman dari segi memori (*streaming cursor*), idempoten (*upsert* analitik), dan memiliki *retry logic* transaksional.

#### 6.1. DDL Skema PostgreSQL Teroptimasi

Simpan berkas berikut sebagai `01_schema_definition.sql`:

```sql
-- Pastikan konfigurasi session teratur
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- 1. Buat Schema Analitik Khusus
CREATE SCHEMA IF NOT EXISTS telemetry;

-- 2. Master Table: Sensor Deployment Metadata
CREATE TABLE IF NOT EXISTS telemetry.dim_devices (
    device_id VARCHAR(64) PRIMARY KEY,
    firmware_version VARCHAR(32) NOT NULL,
    deployed_region VARCHAR(32) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Partitioned Fact Table: Time-Series Sensor Analytics
-- Dipartisi secara RANGE berdasarkan reading_time untuk pembersihan/retensi data yang efisien
CREATE TABLE IF NOT EXISTS telemetry.fct_sensor_readings (
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_id VARCHAR(64) NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    reading_time TIMESTAMPTZ NOT NULL,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_device_id FOREIGN KEY (device_id) REFERENCES telemetry.dim_devices(device_id),
    CONSTRAINT pk_sensor_readings PRIMARY KEY (reading_time, reading_id)
) PARTITION BY RANGE (reading_time);

-- 4. Partisi Bulanan (Contoh: Kuartal 1 2026)
CREATE TABLE IF NOT EXISTS telemetry.fct_sensor_readings_2026_01 
    PARTITION OF telemetry.fct_sensor_readings
    FOR VALUES FROM ('2026-01-01 00:00:00+00') TO ('2026-02-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS telemetry.fct_sensor_readings_2026_02 
    PARTITION OF telemetry.fct_sensor_readings
    FOR VALUES FROM ('2026-02-01 00:00:00+00') TO ('2026-03-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS telemetry.fct_sensor_readings_2026_03 
    PARTITION OF telemetry.fct_sensor_readings
    FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

-- 5. Composite Covering Index untuk Query Windowing & Analitik Time-Series
-- Mencakup metric_value langsung pada index leaf node untuk mendukung Index-Only Scan
CREATE INDEX IF NOT EXISTS idx_sensor_readings_covering 
    ON telemetry.fct_sensor_readings (device_id, metric_name, reading_time DESC) 
    INCLUDE (metric_value);

-- 6. Tabel Target Agregasi Harian (Feature Store Mart / Downstream AI Consumption)
CREATE TABLE IF NOT EXISTS telemetry.agg_daily_metrics (
    metric_date DATE NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    avg_value DOUBLE PRECISION NOT NULL,
    rolling_7d_avg DOUBLE PRECISION NOT NULL,
    z_score DOUBLE PRECISION,
    total_records INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_agg_daily_metrics PRIMARY KEY (metric_date, device_id, metric_name)
);
```

#### 6.2. Kueri Analitik SQL Tingkat Lanjut (Window Function & CTE)

Simpan berkas berikut sebagai `02_analytical_transformation.sql`. Kueri ini mendeteksi anomali metrik dengan menghitung nilai rata-rata berjalan 7-hari (*moving average*), deviasi standar berjalan (*running standard deviation*), dan *Z-score* secara instan tanpa melakukan perulangan (*self-join*):

```sql
WITH daily_summaries AS (
    -- Agregasi dasar harian per unit perangkat
    SELECT 
        DATE_TRUNC('day', reading_time)::DATE AS metric_date,
        device_id,
        metric_name,
        COUNT(reading_id) AS total_records,
        AVG(metric_value) AS avg_value
    FROM 
        telemetry.fct_sensor_readings
    WHERE 
        reading_time >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 
        1, 2, 3
),
windowed_statistics AS (
    -- Eksekusi Window Function dengan batas frame eksplisit ROWS BETWEEN
    -- Mencegah default RANGE BETWEEN yang memicu overhead komputasi buffer berlebih
    SELECT 
        metric_date,
        device_id,
        metric_name,
        avg_value,
        total_records,
        AVG(avg_value) OVER (
            PARTITION BY device_id, metric_name 
            ORDER BY metric_date ASC 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg,
        STDDEV_SAMP(avg_value) OVER (
            PARTITION BY device_id, metric_name 
            ORDER BY metric_date ASC 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_stddev
    FROM 
        daily_summaries
)
-- Hitung Z-Score dan siapkan format untuk Upsert Idempoten
SELECT 
    metric_date,
    device_id,
    metric_name,
    avg_value,
    rolling_7d_avg,
    CASE 
        WHEN rolling_7d_stddev IS NULL OR rolling_7d_stddev = 0 THEN 0.0
        ELSE (avg_value - rolling_7d_avg) / rolling_7d_stddev
    END AS z_score,
    total_records,
    CURRENT_TIMESTAMP AS updated_at
FROM 
    windowed_statistics
ORDER BY 
    device_id, metric_name, metric_date;
```

#### 6.3. Python Orchestrator: Streaming Extractor & Idempotent Pipeline

Kode Python ini menggunakan arsitektur *producer-consumer* terkendali memori menggunakan *server-side streaming cursor* dan isolasi transaksi ACID penuh.

Simpan berkas berikut sebagai `pipeline_orchestrator.py`:

```python
"""
Telemetry Feature Pipeline Orchestrator
Mengimplementasikan pattern Repository, Server-Side Cursor Streaming, 
dan Idempotent Batch Insertion menggunakan SQLAlchemy 2.0 Core.
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.exc import DBAPIError, OperationalError

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("TelemetryPipeline")

# Metadata Definition
metadata = MetaData(schema="telemetry")

agg_daily_metrics = Table(
    "agg_daily_metrics",
    metadata,
    Column("metric_date", Date, primary_key=True),
    Column("device_id", String(64), primary_key=True),
    Column("metric_name", String(64), primary_key=True),
    Column("avg_value", Float, nullable=False),
    Column("rolling_7d_avg", Float, nullable=False),
    Column("z_score", Float, nullable=True),
    Column("total_records", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


@dataclass(frozen=True)
class PipelineConfig:
    db_uri: str
    source_days_interval: int = 30
    batch_size: int = 5000
    max_retries: int = 3
    retry_delay_seconds: float = 2.0


class DatabaseManager:
    """Mengelola lifecycle Engine dan Connection Pool."""

    def __init__(self, uri: str) -> None:
        self.engine: Engine = create_engine(
            uri,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            execution_options={"isolation_level": "READ COMMITTED"},
        )

    @contextmanager
    def transaction(self) -> Generator[Connection, None, None]:
        """Menyediakan transactional context manager dengan auto-rollback."""
        connection = self.engine.connect()
        trans = connection.begin()
        try:
            yield connection
            trans.commit()
        except Exception as exc:
            trans.rollback()
            logger.error("Transaksi dibatalkan (rollback) karena error: %s", exc)
            raise
        finally:
            connection.close()


class TelemetryFeaturePipeline:
    """Orkestrasi kalkulasi statistik telemetri dan persistensi idempoten."""

    def __init__(self, db_manager: DatabaseManager, config: PipelineConfig) -> None:
        self.db = db_manager
        self.config = config

    def _build_extraction_query(self) -> str:
        return """
        WITH daily_summaries AS (
            SELECT 
                DATE_TRUNC('day', reading_time)::DATE AS metric_date,
                device_id,
                metric_name,
                COUNT(reading_id) AS total_records,
                AVG(metric_value) AS avg_value
            FROM 
                telemetry.fct_sensor_readings
            WHERE 
                reading_time >= CURRENT_DATE - (:days_interval || ' days')::INTERVAL
            GROUP BY 
                1, 2, 3
        ),
        windowed_statistics AS (
            SELECT 
                metric_date,
                device_id,
                metric_name,
                avg_value,
                total_records,
                AVG(avg_value) OVER (
                    PARTITION BY device_id, metric_name 
                    ORDER BY metric_date ASC 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS rolling_7d_avg,
                STDDEV_SAMP(avg_value) OVER (
                    PARTITION BY device_id, metric_name 
                    ORDER BY metric_date ASC 
                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                ) AS rolling_7d_stddev
            FROM 
                daily_summaries
        )
        SELECT 
            metric_date,
            device_id,
            metric_name,
            avg_value,
            rolling_7d_avg,
            CASE 
                WHEN rolling_7d_stddev IS NULL OR rolling_7d_stddev = 0 THEN 0.0
                ELSE (avg_value - rolling_7d_avg) / rolling_7d_stddev
            END AS z_score,
            total_records
        FROM 
            windowed_statistics;
        """

    def stream_features(
        self, connection: Connection
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """
        Mengekstrak data menggunakan Server-Side Cursor untuk mencegah Memory Overflow di sisi klien.
        """
        raw_sql = self._build_extraction_query()
        statement = text(raw_sql)
        
        # Konfigurasi server-side streaming cursor
        proxy = connection.execution_options(yield_per=self.config.batch_size).execute(
            statement, {"days_interval": self.config.source_days_interval}
        )

        while True:
            rows = proxy.fetchmany(self.config.batch_size)
            if not rows:
                break
            
            chunk = [
                {
                    "metric_date": row.metric_date,
                    "device_id": row.device_id,
                    "metric_name": row.metric_name,
                    "avg_value": float(row.avg_value),
                    "rolling_7d_avg": float(row.rolling_7d_avg),
                    "z_score": float(row.z_score) if row.z_score is not None else None,
                    "total_records": int(row.total_records),
                    "updated_at": datetime.utcnow(),
                }
                for row in rows
            ]
            yield chunk

    def upsert_batch(self, connection: Connection, records: List[Dict[str, Any]]) -> int:
        """
        Menyimpan data secara IDEMPOTEN menggunakan PostgreSQL ON CONFLICT DO UPDATE (UPSERT).
        """
        if not records:
            return 0

        insert_stmt = pg_insert(agg_daily_metrics).values(records)
        
        # Kolom yang akan diperbarui jika record sudah eksis (Conflict pada Primary Key)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["metric_date", "device_id", "metric_name"],
            set_={
                "avg_value": insert_stmt.excluded.avg_value,
                "rolling_7d_avg": insert_stmt.excluded.rolling_7d_avg,
                "z_score": insert_stmt.excluded.z_score,
                "total_records": insert_stmt.excluded.total_records,
                "updated_at": insert_stmt.excluded.updated_at,
            },
        )

        result = connection.execute(upsert_stmt)
        return result.rowcount

    def execute_pipeline(self) -> None:
        """Menjalankan seluruh siklus ETL dengan Transaction Isolation dan Retry Logic."""
        logger.info("Memulai eksekusi Telemetry Feature Pipeline...")
        total_rows_processed = 0

        for attempt in range(1, self.config.max_retries + 1):
            try:
                with self.db.transaction() as conn:
                    # Alokasikan work_mem khusus untuk session ini demi optimasi window aggregation
                    conn.execute(text("SET LOCAL work_mem = '64MB';"))
                    
                    for chunk in self.stream_features(conn):
                        rows_affected = self.upsert_batch(conn, chunk)
                        total_rows_processed += rows_affected
                        logger.info("Batch tersimpan: %d record diproses.", rows_affected)

                logger.info(
                    "Pipeline selesai dengan sukses. Total record terinkorporasi: %d",
                    total_rows_processed,
                )
                return

            except (OperationalError, DBAPIError) as err:
                logger.warning(
                    "Terdeteksi transient database error pada attempt %d/%d: %s",
                    attempt,
                    self.config.max_retries,
                    err,
                )
                if attempt == self.config.max_retries:
                    logger.critical("Batas toleransi retry habis. Membatalkan eksekusi.")
                    raise
                time.sleep(self.config.retry_delay_seconds * attempt)
            except Exception as unhandled:
                logger.exception("Kesalahan fatal tidak tertangani: %s", unhandled)
                raise


if __name__ == "__main__":
    # Konfigurasi Koneksi Database Target
    DB_CONNECTION_STRING = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/telemetry_db"
    )

    pipeline_config = PipelineConfig(
        db_uri=DB_CONNECTION_STRING,
        source_days_interval=30,
        batch_size=2000,
        max_retries=3,
        retry_delay_seconds=1.5,
    )

    db_mgr = DatabaseManager(pipeline_config.db_uri)
    pipeline = TelemetryFeaturePipeline(db_mgr, pipeline_config)

    # Inisialisasi Eksekusi
    try:
        pipeline.execute_pipeline()
    except Exception as e:
        logger.error("Status pipeline: FAILED. Detail: %s", e)
        sys.exit(1)
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah katalog kegagalan fatal pada database relasional untuk skenario data analitik dan mitigasi defensifnya:

| Skenario Kegagalan | Penyebab Fundamental (*Root Cause*) | Gejala / Efek Samping | Mitigasi Ketat Tingkat Produksi |
| :--- | :--- | :--- | :--- |
| **WorkMem Disk Spill** | Ukuran agregasi/sorting melebihi nilai parameter `work_mem`. | Muncul log `temporary file: path "base/pgsql_tmp/..."`, latensi kueri melonjak drastis. | Gunakan perintah berlingkup transaksi lokal: `SET LOCAL work_mem = '128MB';` sebelum kueri analitik berat dieksekusi. |
| **Deadlock on Concurrent Upsert** | Dua transaksi konkuren melakukan `ON CONFLICT DO UPDATE` pada urutan tuple acak (non-terurut). | Engine melempar error: `ERROR: deadlock detected (SQLSTATE 40P01)`. | Terapkan pengurutan deterministik pada sisi aplikasi sebelum batch insert (`records.sort(key=...)`) dan gunakan eksponensial backoff retry. |
| **Three-Valued Logic NULL Bug** | Menggunakan negasi `NOT IN` yang berisi subquery dengan salah satu nilai bernilai `NULL`. | Kueri mengembalikan himpunan kosong (`0 rows`) secara salah karena logika `val = NULL -> UNKNOWN`. | Ganti seluruh operator `NOT IN (SELECT ...)` menjadi anti-join berbasis `NOT EXISTS (SELECT ...)` atau tentukan filter eksplisit `WHERE col IS NOT NULL`. |
| **Out-of-Range Partition Failure** | Data masuk dengan timestamp di luar rentang partisi tabel yang telah dialokasikan. | `ERROR: no partition of relation found for row (SQLSTATE 23514)`. | Wajib membuat partisi *DEFAULT* catch-all atau automasi skrip DDL partisi masa depan via ekstensi `pg_partman`. |
| **Silent Truncation & Non-Deterministic Rank** | Penggunaan `ROW_NUMBER()` tanpa menyertakan *tie-breaker column* pada partisi data dengan timestamp ganda. | Hasil training data machine learning tidak dapat direproduksi (*non-reproducible feature drift*). | Wajib menyertakan Primary Key / Unique ID pada klausa `ORDER BY`: `ORDER BY reading_time DESC, reading_id DESC`. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan SQL analitik membawa implikasi struktural yang harus dipertimbangkan:

#### 8.1. Normalisasi Penuh (3NF) vs. Denormalisasi Dimensional (Star Schema)
- **Normalisasi (3NF):** 
  - *Kelebihan:* Menjamin integritas data referensial tinggi, meminimalkan anomali pembaruan (update anomalies), efisiensi penyimpanan untuk transaksi OLTP.
  - *Kekurangan:* Analitik membutuhkan multi-table join yang mahal (overhead CPU & memory untuk Hash/Merge Joins).
- **Denormalisasi (Star Schema / Mart):**
  - *Kelebihan:* Kueri analitik sederhana, scanning masif lebih cepat (*read-optimized*), komputasi join minim.
  - *Kekurangan:* Konsumsi disk membengkak (*storage redundancy*), rawan inkonsistensi data jika proses ELT sinkronisasi gagal di tengah jalan.

#### 8.2. Covering B-Tree Index vs. GiST / BRIN Index
- **Covering B-Tree (dengan `INCLUDE`):**
  - *Kelebihan:* Mengaktifkan *Index-Only Scan*, latensi dalam skala sub-milidetik.
  - *Kekurangan:* Ukuran file indeks besar di disk (*storage overhead*), memperlambat operasi penulisan (*Write-Amplification* pada setiap instruksi `INSERT/UPDATE`).
- **BRIN (Block Range Index):**
  - *Alternatif Ideal:* Sangat optimal untuk tabel berukuran gigabyte/terabyte yang tersusun urut secara fisik berdasarkan waktu (*naturally physically ordered* seperti kolom log transaksi).
  - *Perbandingan:* BRIN hanya menyimpan min/max value per rentang halaman fisik (misal per 128 block). Ukurannya hanya beberapa ratus kilobyte dibandingkan B-Tree yang mencapai gigabyte, namun tidak mendukung pencarian baris tunggal secara instan (*point lookup latency* lebih lambat dari B-Tree).

#### 8.3. Window Functions `ROWS` vs. `RANGE`
- **Default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`:**
  - *Mekanisme:* PostgreSQL harus memverifikasi apakah ada nilai kembar (*duplicates/ties*) pada baris berikutnya di memori.
  - *Konsekuensi:* Mengurangi performa secara signifikan karena tidak bisa langsung memancarkan tuple (*spool overhead*).
- **Optimasi `ROWS BETWEEN N PRECEDING AND CURRENT ROW`:**
  - *Mekanisme:* Pembacaan kaku berdasarkan offset jumlah baris fisik.
  - *Konsekuensi:* Komputasi berkecepatan tinggi, memori konstan, namun analis harus memastikan bahwa pergeseran jumlah baris merepresentasikan unit waktu yang konsisten jika data memiliki jeda (*time gaps*).

---

### 9. Best Practices & Standard Industri

1. **Gunakan Perintah EXPLAIN Terstruktur:**
   Jangan berasumsi atas performa kueri. Selalu validasi kueri analitik dengan:
   ```sql
   EXPLAIN (ANALYZE, BUFFERS, SETTINGS, TIMING OFF) 
   SELECT ...
   ```
   *Catatan:* Parameter `TIMING OFF` mengurangi overhead pengukuran *gettimeofday* kernel CPU saat menganalisis jutaan baris data, memberikan representasi konsumsi buffer yang lebih murni.

2. **Standardisasi Gaya Penulisan SQL (SQLFluff Rule Alignment):**
   - Kata kunci wajib menggunakan huruf kapital penuh (`SELECT`, `FROM`, `WHERE`, `JOIN`).
   - Gunakan format Common Table Expression (CTE) daripada *nested deeply subqueries* demi menjaga *code readability* dan modularitas analitik.
   - Akhiri nama CTE dengan kata kerja/deskripsi koleksi data (misal: `cleaned_events`, `aggregated_metrics`).

3. **Hindari Anti-Pattern `SELECT *`:**
   Pemanggilan `SELECT *` melumpuhkan optimasi *Index-Only Scan* karena memaksa engine mengunjungi heap tabel fisik (*heap fetches*) untuk mengambil seluruh kolom yang tidak diperlukan.

4. **Operasi Indeks Non-Blocking di Lingkungan Produksi:**
   Dilarang menjalankan `CREATE INDEX` biasa pada tabel analitik yang sedang melayani transaksi live karena akan mengunci penulisan (`SHARE lock`). Selalu gunakan:
   ```sql
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (columns);
   ```

5. **Pemisahan Database Analitik via Read-Replicas:**
   Isolasi kueri berat analitik dan ekstraksi AI pipeline dari instance master transaksional. Arahkan koneksi pembacaan analitik secara ketat ke *PostgreSQL Read-Only Replica* dengan konfigurasi khusus:
   - `max_standby_archive_delay = 300s`
   - `max_standby_streaming_delay = 300s`
   Ini mencegah kueri analitik dibatalkan mendadak oleh replay WAL transaksional.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Sistem Feature Store analitik Anda mengalami degradasi performa akut: proses agregasi harian sensor membengkak dari 15 detik menjadi 18 menit seiring bertambahnya volume data hingga 2 juta baris. Manajemen meminta Anda mendiagnosis akar masalah menggunakan eksekusi rencana (*Execution Plan*), mengeliminasi disk spill, dan membangun ulang pipeline agar idempoten.

#### Langkah 1: Persiapan Basis Data dan Populasi Data Uji
Buka konsol `psql` Anda dan buat dataset sintetis terdistribusi:

```sql
CREATE DATABASE telemetry_lab;
\c telemetry_lab

CREATE SCHEMA IF NOT EXISTS telemetry;

CREATE TABLE telemetry.sensor_raw_data (
    reading_id BIGINT GENERATED ALWAYS AS IDENTITY,
    device_id VARCHAR(32) NOT NULL,
    metric_name VARCHAR(32) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    reading_time TIMESTAMPTZ NOT NULL
);

-- Masukkan 1.000.000 baris data sintetis
INSERT INTO telemetry.sensor_raw_data (device_id, metric_name, metric_value, reading_time)
SELECT 
    'DEV-' || (LPAD((1 + (random() * 50)::INT)::TEXT, 3, '0')),
    CASE (i % 3)
        WHEN 0 THEN 'temperature'
        WHEN 1 THEN 'vibration'
        ELSE 'voltage'
    END,
    (random() * 100)::NUMERIC(6, 2),
    CURRENT_TIMESTAMP - (random() * INTERVAL '60 days')
FROM generate_series(1, 1000000) AS s(i);

-- Perbarui statistik katalog
ANALYZE telemetry.sensor_raw_data;
```

#### Langkah 2: Profiling Masalah Kueri Awal (Baseline Diagnostic)
Jalankan kueri berikut yang menyimulasikan perhitungan agregasi bergerak tanpa indeks teroptimasi dan limitasi `work_mem` standar:

```sql
-- Paksa memori kerja ke batas minimal untuk mengamati disk spill
SET work_mem = '4MB';

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    device_id,
    metric_name,
    reading_time,
    metric_value,
    AVG(metric_value) OVER (
        PARTITION BY device_id, metric_name 
        ORDER BY reading_time
    ) as running_avg
FROM telemetry.sensor_raw_data
WHERE reading_time >= CURRENT_DATE - INTERVAL '15 days';
```

**Tugas Peserta:**
Amati output `EXPLAIN`. Temukan baris yang mengandung indikator performa buruk:
- `Sort Method: external merge  Disk: ...` (menandakan terjadinya *disk spill*).
- `Seq Scan on sensor_raw_data` (membaca seluruh 1.000.000 baris meski hanya meminta 15 hari terakhir).
- Angka `Buffers: read=...` yang tinggi.

#### Langkah 3: Intervensi Rekayasa Indeks & Query Tuning
Terapkan Covering Index untuk mengaktifkan pemotongan partisi indeks dan alokasi memori yang adaptif:

```sql
-- 1. Buat Indeks Komposit untuk mengeliminasi Sequential Scan dan Sorter Node
CREATE INDEX idx_sensor_optimized 
ON telemetry.sensor_raw_data (device_id, metric_name, reading_time) 
INCLUDE (metric_value);

-- 2. Modifikasi kueri dengan penyesuaian work_mem lokal dan eksplisit frame specification
SET LOCAL work_mem = '64MB';

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    device_id,
    metric_name,
    reading_time,
    metric_value,
    AVG(metric_value) OVER (
        PARTITION BY device_id, metric_name 
        ORDER BY reading_time 
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as running_avg
FROM telemetry.sensor_raw_data
WHERE reading_time >= CURRENT_DATE - INTERVAL '15 days';
```

#### Langkah 4: Validasi & Kriteria Keberhasilan
Eksekusi pengujian dinyatakan **LULUS** apabila:
1. Rencana eksekusi beralih dari `Seq Scan` menjadi **`Index Only Scan`** atau `Bitmap Index Scan`.
2. Tidak ditemukan indikator `Disk: ...` pada seluruh node pohon eksekusi (semua operasi pengurutan dilakukan via `quicksort` di dalam memori RAM).
3. Metrik `Shared Read Blocks` turun drastis (minimal penurunan 80% dari eksekusi awal di Langkah 2).
4. Total execution time terpangkas sekurang-kurangnya $5\times$ lipat lebih cepat dibandingkan baseline.