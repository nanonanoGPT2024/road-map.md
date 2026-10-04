# Bab 01: Fondasi Arsitektur Rekayasa Data Modern
## Modul 01: The Data Engineering Lifecycle & Ekosistem Data Modern

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengidentifikasi dan menganalisis tahapan *Data Engineering Lifecycle*: *Generation, Storage, Ingestion, Transformation,* hingga *Serving*.
- Merancang batas arsitektur (*architectural boundaries*) antara sistem transaksional (OLTP) dan sistem analitikal (OLAP).
- Menerapkan prinsip-prinsip *Undercurrents* rekayasa data: Keamanan, *Data Governance*, *DataOps*, *Data Architecture*, dan *Orchestration*.
- Mengimplementasikan pipeline ingest data berbasis Python dengan pola arsitektur *idempotent* dan penanganan kegagalan (*fault-tolerant*).
- Menghitung rasio kompresi, throughput I/O, serta menganalisis *trade-off* penyimpanan format baris (*row-oriented*) versus kolom (*column-oriented*).

---

### 2. Concept
*Data Engineering Lifecycle* adalah kerangka kerja holistik yang mendefinisikan fase evolusi data mentah dari sistem sumber hingga menjadi aset bernilai bagi konsumsi analitik (*Machine Learning*, BI, *Reverse ETL*). Siklus ini beroperasi di atas lapisan fondasi lintas fungsi yang disebut *Undercurrents*.

```
[ GENERATION ] -> [ INGESTION ] -> [ STORAGE ] -> [ TRANSFORMATION ] -> [ SERVING ]
       ^                 ^             ^                ^                  ^
       |=================|=============|================|==================|
       |      UNDERCURRENTS: Security, Governance, DataOps, Observability   |
```

---

### 3. Why It Matters
Sebelum adanya standarisasi siklus hidup ini, rekayasa data kerap diperlakukan sekadar sebagai penulisan skrip ETL (*Extract-Transform-Load*) monolitik yang rapuh. Pendekatan usang ini menimbulkan masalah:
- **Tight Coupling:** Skrip ekstraksi terikat langsung pada skema database produksi OLTP, menyebabkan degradasi performa transaksi utama saat ekstraksi data berlangsung.
- **Data Debt & Silent Failures:** Tidak adanya isolasi layer penyimpanan dan *observability* memicu anomali data (*silent data corruption*) yang baru terdeteksi berminggu-minggu kemudian di level laporan eksekutif.
- **Biaya Komputasi Eksponensial:** Ekstraksi tanpa *incremental loading* atau partisi yang tepat membebani *network throughput* dan melipatgandakan *billing* cloud data warehouse.

Memahami siklus hidup ini secara modular memungkinkan pemisahan komputasi dan penyimpanan (*separation of compute and storage*), skalabilitas independen, serta auditabilitas data end-to-end.

---

### 4. What It Is
Secara teknis, *Data Engineering Lifecycle* memetakan aliran data melalui tahapan diskrit berikut:

1. **Generation (Sumber Data):** Sistem hulu yang memproduksi data (aplikasi web via PostgreSQL/MySQL, *IoT sensors*, log server, aplikasi pihak ketiga via REST API).
2. **Storage (Penyimpanan):** Fondasi non-volatil tempat data beristirahat (*data at rest*). Karakteristiknya bervariasi dari *raw blob object storage* (Amazon S3, Google Cloud Storage), *distributed file system* (HDFS), hingga engine teroptimasi (Delta Lake, Apache Iceberg).
3. **Ingestion (Penyerapan):** Mekanisme memindahkan data dari *Generation* ke *Storage*. Terbagi menjadi *Batch Ingestion* (interval berkala via JDBC/API) dan *Streaming Ingestion* (aliran *real-time* berbasis log menggunakan Apache Kafka/Redpanda).
4. **Transformation (Transformasi):** Pengubahan struktur, tipe data, validasi skema, deduplikasi, dan agregasi data agar memiliki arti semantik. Umumnya diproses via distributed engine seperti Apache Spark atau model ELT modern via Trino/dbt.
5. **Serving (Penyajian):** Eksposur data terstruktur ke konsumen akhir via SQL Data Warehouse (Snowflake, BigQuery), *Feature Store* (Feast), atau *In-Memory Caches* (Redis).

Lapisan **Undercurrents** mengikat seluruh fase di atas:
- **Security:** Enkripsi *in-transit* (TLS 1.3) dan *at-rest* (AES-256), serta *Role-Based Access Control* (RBAC).
- **Data Governance:** Katalog data, *lineage tracing*, perlindungan PII (*Personally Identifiable Information*).
- **DataOps:** CI/CD untuk pipeline data, *automated data quality testing*, dan *infrastructure as code* (IaC).

---

### 5. How It Works
Mari kita telaah mekanisme aliran data tingkat rendah (*low-level mechanics*) dari *Generation* ke *Storage* dan *Transformation*:

1. **Source CDC Triggering:** Saat transaksi `INSERT/UPDATE/DELETE` terjadi di OLTP (misal PostgreSQL), modifikasi dicatat ke dalam disk pada file *Write-Ahead Log* (WAL) secara sekuensial sebelum data benar-benar ditulis ke *data block table*.
2. **Debezium/Kafka Connect Capture:** Konektor CDC membaca byte stream dari WAL Postgres, memparsing skema logika transaksi menggunakan protokol *logical replication*, lalu membungkusnya menjadi event JSON/Avro.
3. **Network Transit & Buffering:** Event dipublikasikan ke Kafka Broker melalui TCP socket. Pesan dialokasikan ke partisi tertentu berdasarkan hashing `record.key` guna menjamin urutan data (*total ordering per partition*).
4. **Batch/Micro-batch Flush to Object Storage:** Worker penyerapan (misal: Kafka Connect S3 Sink atau custom engine) mengonsumsi event, menumpuknya di memori (*in-memory buffer pool*), lalu melakukan *flush* berkala ke format kolumnar (Apache Parquet) menggunakan algoritma kompresi Snappy/ZSTD langsung ke Object Storage.
5. **Atomic Metadata Commit:** Engine penyimpanan ACID (Delta Lake/Iceberg) memperbarui file log transaksi (`_delta_log` atau metadata file Iceberg) secara atomik menggunakan mekanisme *Optimistic Concurrency Control* (OCC).

---

### 6. Architecture Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    DATA ENGINEERING LIFECYCLE                                      |
+----------------------------------------------------------------------------------------------------+
 [ GENERATION ]         [ INGESTION ]              [ STORAGE ]             [ TRANSFORMATION ] [ SERVING ]
+--------------+       +---------------+       +------------------+       +------------------+ +--------+
| App Database |       | Apache Kafka  |       | Object Storage   |       | Apache Spark     | | Trino/ |
| (PostgreSQL) |--CDC->| / Event Hub   |------>| (S3/GCS)         |------>| / dbt Core       |-| BI /   |
| [WAL Stream] |       | [Distributed] |       | Bronze/Raw Layer |       | Distributed Calc | | ML Eng |
+--------------+       +---------------+       +------------------+       +------------------+ +--------+
                                                        |                           |
                                                        v                           v
                                               +------------------+       +------------------+
                                               | Metadata Engine  |       | Silver & Gold    |
                                               | Iceberg / Delta  |<------| Curated Layer    |
                                               +------------------+       +------------------+
======================================================================================================
  UNDERCURRENTS:
  - Security     : KMS Key Encryption, IAM Instance Roles, TLS Termination
  - Governance   : Apache Atlas / DataHub Metadata Tracking & Schema Registry
  - DataOps      : Docker, Terraform, Great Expectations Validation, Git Workflow
  - Observability: Prometheus Metrics, OpenLineage Tracking, Vector Logging
======================================================================================================
```

---

### 7. Simple Code Example
Berikut implementasi skrip Python dasar untuk memproses data batch secara *idempotent* dari REST API (Generation), melakukan validasi tipe data sederhana, dan menyimpannya ke format Parquet berpartisi:

```python
import os
import json
import requests
import pandas as pd
from datetime import datetime

SOURCE_API = "https://jsonplaceholder.typicode.com/posts"
STORAGE_ROOT = "./lakehouse/raw/posts"

def extract_posts() -> list[dict]:
    """Mengambil raw payload dari HTTP endpoint."""
    response = requests.get(SOURCE_API, timeout=10)
    response.raise_for_status()
    return response.json()

def transform_and_append_metadata(raw_data: list[dict]) -> pd.DataFrame:
    """Standardisasi skema dan injeksi audit metadata."""
    df = pd.DataFrame(raw_data)
    
    # Cast tipe data eksplisit
    df["userId"] = df["userId"].astype("int64")
    df["id"] = df["id"].astype("int64")
    df["title"] = df["title"].astype("string")
    df["body"] = df["body"].astype("string")
    
    # Injeksi metadata untuk audit data lineage
    df["_ingested_at"] = datetime.utcnow()
    df["_source_system"] = "jsonplaceholder_api"
    
    # Kolom partisi
    df["load_date"] = datetime.utcnow().strftime("%Y-%m-%d")
    return df

def load_idempotent_parquet(df: pd.DataFrame, base_path: str):
    """Menulis dataframe ke format Parquet dengan partisi tanggal (idempotent)."""
    for load_date, partition_df in df.groupby("load_date"):
        partition_path = os.path.join(base_path, f"load_date={load_date}")
        os.makedirs(partition_path, exist_ok=True)
        
        # Penulisan file Parquet menggantikan data hari yang sama (idempotent write)
        target_file = os.path.join(partition_path, "data.parquet")
        partition_df.to_parquet(
            target_file, 
            engine="pyarrow", 
            compression="snappy", 
            index=False
        )
        print(f"Successfully loaded {len(partition_df)} records to {target_file}")

if __name__ == "__main__":
    payload = extract_posts()
    transformed_df = transform_and_append_metadata(payload)
    load_idempotent_parquet(transformed_df, STORAGE_ROOT)
```

---

### 8. Practical Production Example
Dalam skenario enterprise nyata, ingest batch sederhana di atas tidak memadai. Kita membutuhkan koneksi pool yang resilien, mekanisme *exponential backoff retry*, validasi skema runtime via Pydantic, dan pemisahan file output berbasis micro-batch run ID agar tidak terjadi *race condition*.

```python
import time
import uuid
import logging
from typing import Generator
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, ValidationError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ProductionIngestor")

# Schema Contract
class OrderEvent(BaseModel):
    order_id: str = Field(..., regex=r"^ORD-[0-9]{5}$")
    customer_id: int = Field(..., gt=0)
    order_amount: float = Field(..., gt=0.0)
    event_timestamp: int
    country_code: str = Field(..., min_length=2, max_length=2)

class ResilientIngestionPipeline:
    def __init__(self, target_base_path: str):
        self.target_base_path = target_base_path
        self.session = self._init_resilient_session()
        
    def _init_resilient_session(self) -> requests.Session:
        """Mengonfigurasi session dengan TCP Connection Pool dan Exponential Backoff."""
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_stream(self, endpoint: str) -> Generator[dict, None, None]:
        """Ekstraksi data dengan error handling tingkat jaringan."""
        try:
            response = self.session.get(endpoint, timeout=(3.05, 27)) # (connect, read) timeout
            response.raise_for_status()
            for record in response.json():
                yield record
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during fetch: {str(e)}")
            raise

    def process_and_write_dead_letter_queue(self, invalid_record: dict, error_msg: str):
        """Simulasi penulisan data korup ke Dead-Letter Queue (DLQ) agar pipeline tidak crash."""
        logger.warning(f"DLQ Route: Data invalid [{error_msg}] - Raw Data: {invalid_record}")

    def run(self, source_url: str):
        run_id = uuid.uuid4().hex[:8]
        validated_records = []
        
        # Ekstraksi dan Validasi Kontrak
        for raw_row in self.fetch_stream(source_url):
            try:
                validated = OrderEvent(**raw_row)
                validated_records.append(validated.dict())
            except ValidationError as err:
                self.process_and_write_dead_letter_queue(raw_row, str(err))

        if not validated_records:
            logger.info("No valid records processed.")
            return

        # Transformasi ke Arrow Table
        arrow_table = pa.Table.from_pylist(validated_records)
        
        # Penambahan metadata lineage
        meta_keys = ["ingest_run_id", "ingest_timestamp"]
        meta_vals = [run_id, datetime.utcnow().isoformat()]
        existing_meta = arrow_table.schema.metadata or {}
        new_meta = {**existing_meta, **dict(zip(meta_keys, meta_vals))}
        arrow_table = arrow_table.replace_schema_metadata(new_meta)

        # Penulisan Parquet dengan Kompresi ZSTD (Level 3 untuk rasio seimbang)
        target_file = f"{self.target_base_path}/batch_{run_id}.parquet"
        pq.write_table(
            arrow_table,
            target_file,
            compression="zstd",
            compression_level=3,
            row_group_size=50000
        )
        logger.info(f"Successfully committed {len(validated_records)} rows to {target_file}")

# Demonstrasi instansiasi (Mock Endpoint testing)
if __name__ == "__main__":
    # Mock URL - Skenario produksi menggunakan URL service internal
    pipeline = ResilientIngestionPipeline(target_base_path="./lakehouse/raw")
    # pipeline.run("https://internal.api.company.local/v1/orders")
```

---

### 9. Trade-offs & Limitations

1. **Row-Oriented vs Column-Oriented Storage:**
   - *Row (Postgres, CSV, JSON):* Optimal untuk *low-latency point lookup* (OLTP) dan mutasi baris individual (`UPDATE order WHERE id=X`). Namun, memindai jutaan baris hanya untuk membaca kolom `order_amount` membuang throughput I/O secara masif karena engine terpaksa membaca seluruh kolom lain ke RAM.
   - *Column (Parquet, ORC):* Sangat cepat untuk analitik agregasi (`SUM`, `AVG`) karena I/O disk hanya membaca byte dari kolom yang diminta. Rasio kompresi tinggi (bisa 70-90% lebih kecil dibanding JSON) berkat keseragaman tipe data sekuensial. Kelemahannya: Mutasi baris individual (*single row mutation*) sangat lambat dan membutuhkan operasi *rewrite* seluruh data file.

2. **Compute-Storage Coupling vs Decoupling:**
   - *Coupled Architecture (Tradisional RDBMS, HDFS lokal):* Data disimpan di node komputasi yang sama. Keuntungan: Mengeliminasi latensi transmisi jaringan (*data locality*). Kelemahan: Jika hanya butuh storage ekstra, Anda terpaksa membayar node komputasi baru yang tidak terpakai (*overprovisioning*).
   - *Decoupled Architecture (S3 + Snowflake/Trino):* Komputasi diskalakan mandiri dari storage. Lebih murah dan fleksibel, tetapi memiliki *network bottleneck* dan memerlukan caching lokal yang agresif untuk performa optimal.

---

### 10. Best Practices & Production Guidelines

- **Implementasikan Idempotensi Penuh:** Pipeline data Anda *pasti* akan dijalankan ulang (*re-run*), baik karena kegagalan jaringan atau koreksi data manual. Setiap *execution run* dengan rentang waktu yang sama harus menghasilkan *state* storage yang identik, bukan duplikasi baris data. Gunakan operasi penulisan partisi `OVERWRITE` atau *Upsert/Merge*.
- **Terapkan Dead-Letter Queue (DLQ):** Jangan biarkan seluruh batch terhenti (*crash*) hanya karena ada 1 baris string di kolom integer. Pisahkan data korup ke path terisolasi (`/lakehouse/dlq/`) dan lanjutkan pemrosesan data yang sehat.
- **Enkapsulasi Format Penyimpanan:** Jangan pernah mengekspos raw files CSV/JSON langsung ke end-user analitik. Gunakan abstraksi tabel seperti Delta Lake, Iceberg, atau Hudi untuk melindungi metadata dan menjamin ACID transactional guarantee.
- **Kontrol Row-Group dan File Size:** Hindari *Small Files Problem* (jutaan file berukuran beberapa KB). Standar ukuran file optimal pada Object Storage seperti AWS S3 adalah **128 MB hingga 512 MB per file**.

---

### 11. Anti-patterns & Common Pitfalls

- **The Database-as-a-Queue Anti-pattern:** Menggunakan kolom `is_processed = false` pada tabel transaksi OLTP untuk di-polling setiap detik oleh batch script. Ini memicu *table bloat*, penumpukan dead tuples pada Postgres, dan *lock contention* yang dapat melumpuhkan transaksi aplikasi utama.
  *Solusi:* Terapkan *Change Data Capture* (CDC) non-blocking via engine berbasis WAL seperti Debezium.
- **Direct-to-Warehouse Ingestion via Insert Statements:** Menjalankan jutaan single-row `INSERT INTO warehouse VALUES (...)`. Data warehouse modern kolumnar dirancang untuk menelan bulk batch file, bukan ribuan transaksi kecil per detik.
  *Solusi:* Tulis batch file ke Object Storage terlebih dahulu (*staging*), kemudian gunakan perintah copy massal (`COPY INTO` pada Snowflake atau `LOAD DATA` pada BigQuery).
- **Ignoring Schema Drift:** Menganggap struktur data sumber statis selamanya. Satu perubahan nama kolom dari tim software engineer upstream dapat merusak ratusan transformasi analitik downstream.

---

### 12. Performance & Optimization Tips

- **Column Pruning & Predicate Pushdown:** Saat membaca file kolumnar (Parquet/ORC), terapkan filter query seawal mungkin pada source engine. Predicate pushdown membaca metadata file (*min/max values per row-group*) untuk langsung melompati (*skip*) blok data tanpa membacanya ke memori.
- **Tuning Kompresi:** Gunakan kompresi **Snappy** jika beban kerja memerlukan dekompresi data super cepat untuk query analitik berulang (*low CPU overhead*). Gunakan kompresi **ZSTD** untuk penyimpanan data mentah/arsip (*cold storage*) demi penghematan ruang penyimpanan maksimal tanpa beban komputasi berlebih.
- **Partition Elimination Strategy:** Partisilah data hanya pada kolom dengan *low-to-medium cardinality* (misalnya: tahun, bulan, atau hari). Mempartisi data pada kolom dengan kardinalitas tinggi seperti `user_id` atau `timestamp` milidetik akan menciptakan jutaan folder kosong/file kecil yang memperlambat metastore list operations.

---

### 13. Security & Compliance Considerations

- **Enkripsi Lapisan Ganda:** Terapkan SSE-KMS (Server-Side Encryption dengan KMS terkelola) saat data ditulis ke Object Storage. Aktifkan penegakan protokol minimal TLS 1.2 (disarankan TLS 1.3) pada semua transit koneksi pipa data.
- **PII Obfuscation at Ingestion:** Masking atau *hashing* (misal SHA-256 dengan Salt dinamis) informasi sensitif seperti NIK, nomor kartu kredit, atau email langsung pada tahap *Ingestion* pertama sebelum mendarat ke lapisan data terbuka.
- **Audit Trails:** Aktifkan log akses tingkat objek (seperti AWS CloudTrail Data Events) untuk mendeteksi siapa atau proses komputasi mana yang membaca dan mengekstraksi data mentah.

---

### 14. Monitoring, Observability & Debugging

Implementasikan pemantauan 3 pilar utama data observability:
1. **Freshness / SLA Latency:** Selisih waktu antara event terjadi di hulu vs data siap dikueri di target serving (`NOW() - MAX(event_timestamp)`).
2. **Volume Anomaly:** Deviasi jumlah row data harian. Jika rata-rata harian 1.000.000 row, namun sistem hanya mencatat 1.000 row, alert harus aktif secara instan.
3. **Data Quality Checks (Schema & Completeness):** Pasang tool data verification seperti *Great Expectations* atau *Soda Core* di dalam pipeline. 

Contoh metrik custom OpenMetrics/Prometheus untuk monitoring ingestor:
```text
# HELP ingestion_records_total Total record yang berhasil diproses
# TYPE ingestion_records_total counter
ingestion_records_total{source="pg_orders",pipeline="raw_ingest"} 1045000

# HELP ingestion_records_failed_total Total record invalid masuk ke DLQ
# TYPE ingestion_records_failed_total counter
ingestion_records_failed_total{source="pg_orders",pipeline="raw_ingest"} 12
```

---

### 15. Edge Cases & Failure Modes

- **Source API Throttling (HTTP 429 Too Many Requests):** Jika pipeline Anda mengekstraksi data secara agresif tanpa rate limiter, IP Anda akan diblokir oleh vendor sumber.
  *Mitigasi:* Implementasikan *Token Bucket Algorithm* atau terapkan *exponential backoff jitter* pada network client.
- **Late-Arriving Data:** Data event transaksi mobile device baru dikirim 3 hari kemudian saat smartphone user kembali mendapatkan sinyal internet.
  *Mitigasi:* Pisahkan konsep *event time* (saat transaksi terjadi di dunia nyata) dan *processing time* (saat pipeline menulis data ke lakehouse). Partisikan data berdasarkan kriteria analitik, bukan sekadar waktu saat script dijalankan.
- **Partial Failure mid-upload:** Jaringan terputus saat pipeline baru menulis 80% file Parquet ke storage.
  *Mitigasi:* Gunakan penulisan file temporer (`.tmp_filename`), lalu eksekusi operasi atomik `RENAME` / `MOVE` ke nama file target saat payload telah 100% tuntas di-upload.

---

### 16. Comparison Matrix

| Karakteristik | Raw JSON / CSV | Plain Apache Parquet | Delta Lake / Apache Iceberg |
| :--- | :--- | :--- | :--- |
| **Tipe Penyimpanan** | Row-oriented (Tekstual) | Column-oriented (Biner) | Column-oriented (Metadata Layer) |
| **ACID Transaction** | Tidak Ada | Tidak Ada | Penuh (ACID via OCC) |
| **Kecepatan Query (Analitik)** | Sangat Lambat (Full parse) | Cepat (Column Pruning) | Sangat Cepat (Metadata index + pruning) |
| **Time Travel / Rollback** | Tidak Ada | Tidak Ada | Ya (Berdasarkan Transaction Log) |
| **Dukungan Schema Evolution** | Rentan Rusak | Parsial (Metadata Merge) | Penuh (In-place Schema Changes) |
| **Biaya Komputasi Query** | Tinggi (I/O & Memory berat) | Efisien | Sangat Efisien |

---

### 17. Hands-on Challenge / Real-world Scenario

**Skenario Bisnis:**
Sebuah perusahaan logistik menerima ratusan file status pengiriman armada truk per jam dari mitra pihak ketiga. Data ditempatkan di sebuah server SFTP lokal/folder input. Tim analis mengeluhkan file korup yang merusak query harian dan adanya event duplikasi akibat pengiriman ulang oleh sistem mitra.

**Tantangan Anda:**
1. Bangun pipeline lokal menggunakan Python yang membaca seluruh file transaksi JSON dari direktori `./incoming_logs/`.
2. Validasi integritas skema data: Setiap event wajib memiliki `delivery_id` (string), `driver_id` (int), `status` (salah satu dari: "PICKED_UP", "IN_TRANSIT", "DELIVERED"), dan `timestamp` (ISO-8601).
3. Jika terdapat record dengan nilai status di luar format di atas, kirim record tersebut ke direktori `./lakehouse/quarantine/`.
4. Lakukan deduplikasi record berdasarkan `delivery_id` unik (ambil event terbaru berdasarkan `timestamp`).
5. Tulis output data yang valid ke direktori `./lakehouse/clean/` dalam format file **Parquet terkompresi Snappy**, dipartisi berdasarkan format tanggal `year=YYYY/month=MM/`.
6. Pipeline harus bersifat *idempotent*: Jika input yang sama diproses ulang, jumlah row di storage akhir tidak boleh bertambah ganda.

---

### 18. Verification & Solution

Berikut adalah implementasi referensi lengkap untuk menyelesaikan *Hands-on Challenge*:

```python
import os
import glob
import json
from datetime import datetime
from typing import List, Tuple
import pandas as pd
from pydantic import BaseModel, Field, field_validator

class DeliveryEvent(BaseModel):
    delivery_id: str
    driver_id: int
    status: str
    timestamp: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"PICKED_UP", "IN_TRANSIT", "DELIVERED"}
        if value not in allowed:
            raise ValueError(f"Invalid status: {value}. Must be one of {allowed}")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value

def process_log_files(input_dir: str, base_out: str, quarantine_dir: str):
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    raw_records = []
    
    for f in json_files:
        with open(f, "r") as fp:
            try:
                data = json.load(fp)
                if isinstance(data, list):
                    raw_records.extend(data)
                else:
                    raw_records.append(data)
            except Exception as e:
                print(f"Skipping corrupted JSON file {f}: {e}")

    valid_events: List[dict] = []
    quarantined_events: List[dict] = []

    # Validasi Skema
    for record in raw_records:
        try:
            event = DeliveryEvent(**record)
            valid_events.append(event.model_dump())
        except Exception as err:
            record["_quarantine_reason"] = str(err)
            record["_quarantined_at"] = datetime.utcnow().isoformat()
            quarantined_events.append(record)

    # Tangani Quarantine (DLQ)
    if quarantined_events:
        os.makedirs(quarantine_dir, exist_ok=True)
        dlq_filename = f"quarantine_{int(datetime.utcnow().timestamp())}.json"
        with open(os.path.join(quarantine_dir, dlq_filename), "w") as fp:
            json.dump(quarantined_events, fp, indent=2)
        print(f"Quarantined {len(quarantined_events)} invalid records.")

    if not valid_events:
        print("No valid events to process.")
        return

    # Pemrosesan Data Valid
    df = pd.DataFrame(valid_events)
    df["timestamp_dt"] = pd.to_datetime(df["timestamp"])
    
    # Deduplikasi: Ambil event terbaru berdasarkan timestamp
    df = df.sort_values("timestamp_dt").groupby("delivery_id").last().reset_index()

    # Ekstraksi partisi partisi
    df["year"] = df["timestamp_dt"].dt.strftime("%Y")
    df["month"] = df["timestamp_dt"].dt.strftime("%m")

    # Tulis Idempotent Parquet
    for (year, month), partition_df in df.groupby(["year", "month"]):
        target_path = os.path.join(base_out, f"year={year}", f"month={month}")
        os.makedirs(target_path, exist_ok=True)
        target_file = os.path.join(target_path, "deliveries.parquet")
        
        # Hapus kolom pembantu
        clean_df = partition_df.drop(columns=["timestamp_dt", "year", "month"])
        
        # Idempotent write: Menimpa file di partisi tersebut
        clean_df.to_parquet(target_file, engine="pyarrow", compression="snappy", index=False)
        print(f"Committed {len(clean_df)} deduplicated records to {target_file}")

# Verifikasi
if __name__ == "__main__":
    # Setup Direktori Uji Coba
    os.makedirs("./test_input", exist_ok=True)
    
    dummy_payload = [
        {"delivery_id": "DEL-1", "driver_id": 101, "status": "PICKED_UP", "timestamp": "2026-03-30T10:00:00"},
        {"delivery_id": "DEL-1", "driver_id": 101, "status": "IN_TRANSIT", "timestamp": "2026-03-30T10:30:00"}, # Duplikasi update
        {"delivery_id": "DEL-2", "driver_id": 102, "status": "INVALID_STATUS", "timestamp": "2026-03-30T11:00:00"}, # Korup
    ]
    
    with open("./test_input/batch_1.json", "w") as f:
        json.dump(dummy_payload, f)
        
    process_log_files(
        input_dir="./test_input", 
        base_out="./lakehouse/clean", 
        quarantine_dir="./lakehouse/quarantine"
    )
```

---

### 19. Key Takeaways

1. **Lifecycle Modularitas:** Data Engineering bukan sekadar otomasi script ETL. Ini adalah orkestrasi berkesinambungan antara *Generation, Storage, Ingestion, Transformation,* dan *Serving*.
2. **Kedaulatan Kolumnar:** Mengabaikan format biner kolumnar (Parquet/ORC) di lapisan penyimpanan analitik adalah anti-pola paling boros sumber daya komputasi dan biaya I/O.
3. **Pondasi Idempotensi:** Kegagalan sistem jaringan terdistribusi adalah keniscayaan (*inevitable*). Seluruh proses penyerapan dan pemrosesan data wajib dibangun dengan asumsi akan mengalami kegagalan dan harus aman dijalankan ulang (*safely retryable*).
4. **DLQ Menyelamatkan Pipeline:** Jangan biarkan kegagalan parsing tipe data minor menghentikan pemrosesan data analitik bisnis skala besar. Gunakan pola *Dead-Letter Queue*.

---

### 20. Next Steps & Recommended Reading

- Lanjutkan ke **Bab 01 Modul 02: Storage Layer Architecture: Deep Dive into Distributed File Systems, Object Storage, and ACID Table Formats (Iceberg vs Delta)**.
- **Rekomendasi Buku:**
  - *Fundamentals of Data Engineering* oleh Joe Reis & Matt Housley (O'Reilly Media) - Baca Bab 1 hingga 3.
  - *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) - Bab 3: *Storage and Retrieval*.
- **Eksplorasi Teknis:**
  - Eksplorasi spesifikasi format metadata biner Apache Parquet menggunakan CLI tool `parquet-tools`.