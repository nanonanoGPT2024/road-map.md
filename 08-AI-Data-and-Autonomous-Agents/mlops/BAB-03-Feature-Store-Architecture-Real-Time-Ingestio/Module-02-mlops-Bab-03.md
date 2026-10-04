# BAB 03: Feature Store Architecture & Real-Time Ingestion
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memilih Pola Arsitektur Feature Store**: Mengevaluasi kebutuhan bisnis untuk memilih antara arsitektur Lambda, Kappa, atau Dual-Storage Engine (Online/Offline) secara tepat.
- **Mengimplementasikan Pipeline Ingestion Real-Time**: Membangun pipeline stream processing menggunakan Kafka dan Redis/Feast untuk agregasi data dinamis dengan latensi sub-10ms.
- **Mencegah Training-Serving Skew & Data Leakage**: Mengonfigurasi mekanisme *point-in-time joins* (time-travel) untuk menjamin validitas historis saat model training.
- **Mengoptimalkan Performa & Skalabilitas Online Store**: Mengonfigurasi Redis Cluster/Key-Value Store berkecepatan tinggi dengan skema serialisasi biner, connection pooling, dan strategi TTL yang efisien.
- **Mendiagnosis Masalah Produksi**: Mengidentifikasi dan menangani *late-arriving events*, *out-of-memory* (OOM) pada state backend, serta ketidakkonsistenan data antara offline dan online layer.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, Anda wajib memiliki pemahaman mendalam tentang:
- **Distributed Streaming**: Konsep Apache Kafka (Partition, Consumer Group, Offsets, Exactly-Once Semantics).
- **In-Memory & NoSQL Databases**: Arsitektur internal Redis (Data structures, Pipeline, Memory Eviction, Clustering).
- **Data Engineering**: SQL lanjutan (Window Functions, Temporal Joins), Apache Spark, atau Apache Flink.
- **Machine Learning Core**: Siklus hidup model machine learning, kebutuhan inferensi batch vs. low-latency real-time inference.
- **Bahasa Pemrograman**: Python 3.10+ (AsyncIO, Type Hinting, Pydantic, Confluent-Kafka/FastAPI).

---

### 3. Concept & Internal Architecture

Feature Store bukan sekadar database; ini adalah platform data komprehensif yang mengabstraksi siklus hidup rekayasa fitur (*feature engineering*), penyimpanan (*storage*), penyajian (*serving*), dan pemantauan (*monitoring*).

```
+-----------------------------------------------------------------------------------+
|                           ENTERPRISE FEATURE STORE                                |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  +--------------------+                     +----------------------------------+  |
|  | Batch Sources      |                     | Streaming Sources                |  |
|  | (Data Lake, DWH)   |                     | (Kafka, Kinesis, Event Hubs)     |  |
|  +---------+----------+                     +----------------+-----------------+  |
|            |                                                 |                    |
|            v                                                 v                    |
|  +--------------------+                     +----------------------------------+  |
|  | Offline Ingestion  |                     | Stream Processing Engine         |  |
|  | (Spark/dbt)        |                     | (Flink/Faust/Spark Streaming)    |  |
|  +---------+----------+                     +----------------+-----------------+  |
|            |                                                 |                    |
|            |                                +----------------+                    |
|            |                                |                                     |
|            v                                v                                     |
|  +--------------------+          +--------------------+                           |
|  | Offline Store      |          | Online Store       |                           |
|  | (Parquet, Iceberg, |          | (Redis, Cassandra, |                           |
|  | BigQuery, Delta)   |          | DynamoDB)          |                           |
|  +---------+----------+          +----------+---------+                           |
|            |                                |                                     |
|            v                                v                                     |
|  +--------------------+          +--------------------+                           |
|  | Historical Serving |          | Low-Latency Serving|                           |
|  | (Training Dataset  |          | (Real-Time Model   |                           |
|  | Generation w/ PIT) |          | Inference Engine)  |                           |
|  +--------------------+          +--------------------+                           |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | Central Feature Registry (Metadata, Schemas, Lineage, Versioning)           |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

#### Dual-Storage Engine Architecture
Arsitektur Feature Store modern berbasis pada dual-engine pattern:
1. **Offline Store (Historical/Analytical Engine)**:
   - Media: Apache Iceberg, Delta Lake, Snowflake, atau BigQuery.
   - Karakteristik: Skalabilitas kapasitas tinggi, berbiaya rendah per TB, dioptimalkan untuk query analytical (OLAP) skala besar dengan throughput scanning tinggi.
   - Fungsi Utama: Menghasilkan dataset training bebas *leakage* menggunakan algoritma *Point-in-Time* (PIT) / *As-of Joins*.
2. **Online Store (Low-Latency KV Engine)**:
   - Media: Redis Cluster, Apache Cassandra, atau AWS DynamoDB.
   - Karakteristik: Berbiaya memori lebih tinggi, dioptimalkan untuk akses read/write sub-10ms (OLTP) berdasarkan *Entity ID*.
   - Fungsi Utama: Menyajikan fitur bernilai paling mutakhir (*latest state*) ke inference engine secara real-time.

#### Point-in-Time (PIT) Correctness Engine
Masalah paling fatal dalam MLOps adalah *data leakage* akibat menggunakan data masa depan (*lookahead bias*) saat training. PIT Join bekerja dengan mengevaluasi stempel waktu observasi ($T_O$) dari sebuah entity dan hanya mengambil nilai fitur yang ter-commit pada timestamp $T_F \le T_O$.

Secara matematis, untuk entity $E_i$ pada timestamp pengamatan $T_O$, nilai fitur $F$ yang valid adalah:

$$\text{FeatureValue}(E_i, T_O) = \operatorname{arg\,max}_{t \le T_O} \{ F(E_i, t) \}$$

---

### 4. Why & What

| Dimensi | Tanpa Feature Store | Dengan Enterprise Feature Store |
| :--- | :--- | :--- |
| **Konsistensi Fitur** | Definisi fitur di Python (training) ditulis ulang di Java/C++ (serving), memicu *training-serving skew*. | Definisi fitur *single-source-of-truth*; pipeline yang sama memproses batch dan stream. |
| **Waktu Iterasi Model** | Data scientist menghabiskan ~70% waktu menulis pipeline feature extraction dari nol. | Fitur siap pakai dapat dicari, dibagikan, dan di-reuse lintas tim via Feature Registry. |
| **Point-in-Time Joins** | Implementasi manual rentan kesalahan logika temporal, menyebabkan model tampak akurat saat validasi namun gagal di produksi. | Abstraksi time-travel bawaan menjamin dataset historis bebas dari data leakage. |
| **Monitoring & Drift** | Drift data baru terdeteksi secara manual berhari-hari setelah model mengalami degradasi. | Pemantauan distribusi statistik fitur secara kontinu antara online dan offline data. |

---

### 5. How: Workflow Detail

```
+-------------------------------------------------------------------------------------------------------------------+
| INGESTION & RETRIEVAL WORKFLOW                                                                                    |
+-------------------------------------------------------------------------------------------------------------------+
|                                                                                                                   |
| [Stream Source] ---> (Kafka Topic) ---> [Streaming Aggregator] ---> [Online Store] ---> [Inference Service]       |
|                                                  |                        ^                                       |
|                                                  v                        | (Sync Job)                            |
| [Batch Source]  ---> [Object Storage] -> [Offline Ingestion]  ---> [Offline Store] ---> [Training Data Builder]  |
|                                                                                                                   |
+-------------------------------------------------------------------------------------------------------------------+
```

1. **Feature Registration**: Rekayasa fitur didaftarkan ke Central Registry via declarative code (YAML/Python). Registry menetapkan skema tipe data, entity ID, metadata, dan SLA refresh rate.
2. **Stream Feature Processing**: Data streaming (misal: log transaksi) ditangkap oleh Kafka, diolah oleh agregator (misal: Faust/Flink) menggunakan *sliding window*, lalu ditulis langsung ke Online Store (Redis).
3. **Dual Ingestion (Lambda/Kappa Sync)**: Data mentah diarsipkan ke Data Lake. Job terjadwal memindahkan data fitur yang diagregasi ke Offline Store untuk historisasi.
4. **Point-in-Time Join Processing**: Saat model retraining dipicu, pipeline training meminta sekumpulan entity keys beserta observation timestamps. Engine mengeksekusi temporal backward merge untuk menyusun training matrix.
5. **Real-Time Serving Retrieval**: Inference service mengirimkan list entity ID ke Online Store via low-latency multi-get (MGET) interface dan menerima feature vector secara instan.

---

### 6. Analogy & Architecture Diagram

#### Analogi Sederhana: Buku Catatan Teller vs. Brankas Arsip Bank
Bayangkan sebuah bank multinasional:
- **Online Feature Store** adalah **Buku Catatan Digital Teller Bank**. Ketika nasabah berdiri di counter, teller harus mengetahui secara instan saldo saat ini dan total transaksi dalam 5 menit terakhir untuk mencegah overdraft. Fokusnya adalah kecepatan akses mutlak (detik/milidetik).
- **Offline Feature Store** adalah **Gudang Arsip Buku Besar Bank**. Berisi setiap lembar transaksi mikro sejak sepuluh tahun lalu. Buku ini tidak bisa diakses dalam 2 milidetik oleh teller, tetapi jika auditor ingin merekonstruksi status keuangan nasabah tepat pada tanggal 14 Mei 2022 pukul 11:32:15 WIB, arsip inilah yang mampu menyajikannya secara presisi tanpa distorsi.

#### Diagram Arsitektur Produksi (Streaming + Feast + Redis + Parquet)

```
                 +------------------------+
                 |  Clickstream / Events  |
                 +-----------+------------+
                             |
                             v
                 +------------------------+
                 |   Kafka Broker Topic   |
                 +-----------+------------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+------------------+                   +--------------------+
|  Faust Streaming |                   | S3 / MinIO Sink    |
|  Engine (Aggs)   |                   | (Raw Parquet Data) |
+--------+---------+                   +---------+----------+
         |                                       |
         v (Sub-10ms writes)                     v (Scheduled Load)
+------------------+                   +--------------------+
|   Redis Cluster  |                   | Offline Warehouse  |
|  (Online Store)  |                   | (DuckDB / Parquet) |
+--------+---------+                   +---------+----------+
         |                                       |
         | MGET features                         | Point-in-Time Join
         v                                       v
+------------------+                   +--------------------+
|  FastAPI Serving |                   | ML Training Script |
| (Model Inference)|                   | (XGBoost/PyTorch)  |
+------------------+                   +--------------------+
```

---

### 7. Code Implementation

#### 7.1 Simple Example: Feature Registry Definition & Dual Retrieval (Feast Native Interface)

```python
# feature_definition.py
from datetime import timedelta
from feast import (
    Entity,
    FeatureView,
    Field,
    FileSource,
    PushSource,
    RedisOnlineStore,
)
from feast.types import Float32, Int64, String

# 1. Definisi Entity
customer_entity = Entity(
    name="customer_id",
    join_keys=["customer_id"],
    description="Identitas unik pelanggan perbankan",
)

# 2. Definisi Source (Offline & Push for Streaming)
offline_source = FileSource(
    name="customer_stats_offline_source",
    path="data/customer_features.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created_timestamp",
)

customer_stats_push_source = PushSource(
    name="customer_stats_push_source",
    batch_source=offline_source,
)

# 3. Definisi Feature View
customer_stats_fv = FeatureView(
    name="customer_transaction_aggregates",
    entities=[customer_entity],
    ttl=timedelta(days=30),
    schema=[
        Field(name="transaction_count_30d", dtype=Int64),
        Field(name="total_spend_30d", dtype=Float32),
        Field(name="risk_score", dtype=Float32),
    ],
    online=True,
    source=customer_stats_push_source,
)
```

#### 7.2 Practical Example: Production-Grade Real-Time Ingestion Pipeline Engine

Contoh berikut menunjukkan implementasi streaming consumer berbasis Python Kafka + Redis Pipeline dengan serialisasi efisien, proteksi concurrency, dan fallback strategy tanpa ketergantungan library monolitik.

```python
# stream_ingestor.py
import json
import logging
import struct
import time
from typing import Dict, Any, List
import redis
from confluent_kafka import Consumer, KafkaError, KafkaException

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class FeatureStoreStreamIngestor:
    def __init__(self, kafka_config: Dict[str, Any], redis_cluster_client: redis.Redis):
        self.kafka_config = kafka_config
        self.redis = redis_cluster_client
        self.consumer = Consumer(self.kafka_config)
        self.running = True

    def serialize_features(self, features: Dict[str, float]) -> bytes:
        """
        Serialisasi payload ke format binary menggunakan struct packing 
        untuk menghemat memori Redis hingga 70% dibanding JSON mentah.
        Format: [tx_count (int32)][total_spend (float32)][risk_score (float32)]
        """
        return struct.pack(
            "!iff",
            int(features.get("transaction_count_30d", 0)),
            float(features.get("total_spend_30d", 0.0)),
            float(features.get("risk_score", 0.0)),
        )

    def write_to_online_store(self, batch_payload: List[Dict[str, Any]]) -> None:
        """
        Menulis batch secara atomik menggunakan Redis Pipeline.
        """
        pipeline = self.redis.pipeline(transaction=False)
        ttl_seconds = 86400 * 30  # 30 Hari TTL

        for record in batch_payload:
            entity_id = record["customer_id"]
            features = record["features"]
            serialized_data = self.serialize_features(features)
            
            # Format Key Redis: {entity_type}:{entity_id}:{feature_view}
            redis_key = f"customer:{entity_id}:customer_transaction_aggregates"
            
            pipeline.set(redis_key, serialized_data, ex=ttl_seconds)
            pipeline.set(f"{redis_key}:last_updated", int(time.time()), ex=ttl_seconds)

        results = pipeline.execute()
        logger.info("Batch %d records successfully pushed to Online Store", len(batch_payload))

    def consume_loop(self, topic: str, batch_size: int = 500, flush_interval_ms: int = 1000):
        self.consumer.subscribe([topic])
        logger.info("Ingestion engine subscribed to topic: %s", topic)
        
        batch = []
        last_flush_time = time.time() * 1000

        try:
            while self.running:
                msg = self.consumer.poll(timeout=0.1)
                now_ms = time.time() * 1000

                if msg is not None:
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        raise KafkaException(msg.error())
                    
                    data = json.loads(msg.value().decode("utf-8"))
                    batch.append(data)

                # Flush berdasarkan batasan batch size atau time window
                if len(batch) >= batch_size or (now_ms - last_flush_time >= flush_interval_ms and len(batch) > 0):
                    self.write_to_online_store(batch)
                    self.consumer.commit(asynchronous=True)
                    batch.clear()
                    last_flush_time = now_ms

        except KeyboardInterrupt:
            logger.info("Interupsi diterima, mematikan consumer...")
        finally:
            self.consumer.close()


class OnlineFeatureReader:
    """
    Reader class yang digunakan oleh Inference Engine.
    """
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def get_online_features(self, customer_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        keys = [f"customer:{cid}:customer_transaction_aggregates" for cid in customer_ids]
        raw_values = self.redis.mget(keys)
        
        results = {}
        for cid, raw in zip(customer_ids, raw_values):
            if raw is not None:
                tx_count, spend, risk = struct.unpack("!iff", raw)
                results[cid] = {
                    "transaction_count_30d": tx_count,
                    "total_spend_30d": spend,
                    "risk_score": risk,
                }
            else:
                # Default fallback imputation
                results[cid] = {
                    "transaction_count_30d": 0,
                    "total_spend_30d": 0.0,
                    "risk_score": 0.5,  # Nilai netral
                }
        return results


if __name__ == "__main__":
    # Test harness sederhana
    r_client = redis.Redis(host="localhost", port=6379, db=0)
    
    # Mock data ingestion
    mock_batch = [
        {
            "customer_id": "c_1001",
            "features": {"transaction_count_30d": 12, "total_spend_30d": 450000.0, "risk_score": 0.12},
        },
        {
            "customer_id": "c_1002",
            "features": {"transaction_count_30d": 3, "total_spend_30d": 50000.0, "risk_score": 0.85},
        },
    ]

    ingestor = FeatureStoreStreamIngestor(kafka_config={}, redis_cluster_client=r_client)
    ingestor.write_to_online_store(mock_batch)

    # Retrieval test
    reader = OnlineFeatureReader(redis_client=r_client)
    features = reader.get_online_features(["c_1001", "c_1002", "c_9999"])
    print(json.dumps(features, indent=2))
```

---

### 8. Real World Case Study: Fraud Detection di Fintech Skala Besar

- **Konteks**: Platform Payment Gateway memproses $45.000$ transaksi per detik (TPS). Setiap otorisasi transaksi wajib menyertakan pengecekan fraud berbasis ML dengan SLA $p99 \le 15\text{ ms}$.
- **Masalah Utama**:
  - Fitur kritikal: `user_transaksi_dalam_10_menit_terakhir` dan `rasio_pengeluaran_terhadap_rataan_30_hari`.
  - Jika inferensi mengandalkan kalkulasi query runtime SQL ke transactional database (PostgreSQL), latensi melonjak menjadi $180\text{ ms}$ dan membebani database utama hingga *connection starvation*.
  - Pembaruan batch offline mengalami lag hingga 2 jam, sehingga fraudster dapat membobol akun dan menguras dana dalam 15 menit pertama sebelum terdeteksi.
- **Solusi Arsitektur**:
  - Membangun pipeline agregasi stateful dengan Apache Flink yang mengonsumsi log transaksi dari Kafka.
  - Flink menghitung sliding window metric dan langsung melakukan sinkronisasi asinkron ke Redis Cluster (32 nodes, memory partitioning berbasis entity user hash).
  - Model inference microservice menggunakan protocol gRPC untuk mengambil binary packed feature dari Redis Cluster dengan latensi $p99 = 2.1\text{ ms}$.
  - Offline store disinkronkan menggunakan sink streaming Flink ke Apache Iceberg tables.
- **Hasil Metrik**:
  - Pengurangan Fraud Loss: Menurunkan unauthorized transaction sebesar 42% ($~\$3.2M/kuartal$).
  - Performa Sistem: Latensi end-to-end model inference stabil di $7.4\text{ ms}$ pada peak hours.
  - Zero Inconsistency: Mengeliminasi fenomena false-positive akibat training-serving skew berkat standarisasi skema via central feature registry.

---

### 9. Trade-offs

| Aspek Arsitektur | Pilihan A | Pilihan B | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Online Storage Engine** | **In-Memory KV (Redis)** | **Distributed Wide-Column (Cassandra)** | Redis memberikan latensi ultra-rendah ($<2\text{ms}$) namun berbiaya infrastruktur RAM sangat tinggi. Cassandra jauh lebih murah untuk dataset berskala multi-terabyte, namun latensi baca berkisar antara $5-12\text{ms}$. |
| **Serialisasi Data Fitur** | **Binary / ProtoBuf / Struct** | **JSON / String Dictionary** | Binary menghemat pemakaian memori hingga 70% dan mempercepat proses parsing jaringan, tetapi menghilangkan kemampuan debugging manual secara langsung melalui Redis CLI tanpa deserializer. |
| **Pipeline Ingestion** | **Direct Streaming (Push via Flink/Kafka)** | **Micro-batch Ingestion (Polling DB/DWH)** | Direct streaming memangkas data staleness ke level sub-detik, namun menuntut keandalan operasional tinggi (stateful streaming engine). Micro-batch lebih mudah di-maintain dan di-debug, namun memiliki latensi ketersediaan data (lag menit hingga jam). |
| **Online-Offline Sync** | **Dual Write (Kappa Pattern)** | **Periodic Sync from Offline (Lambda)** | Dual-write rentan terhadap kondisi *distributed inconsistency* jika salah satu jalur terputus, sedangkan Periodic Sync membebani Offline DB dan mengakibatkan Online Store selalu tertinggal (*stale*). |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Missing Point-in-Time Join Logic
- **Gejala**: Model menunjukkan performa AUC 0.98 pada saat training lokal, namun anjlok ke 0.62 saat deployment produksi.
- **Penyebab**: Script data preparation mengambil fitur dengan timestamp paling mutakhir (*latest status*) untuk data training masa lalu, alih-alih mengambil status pada saat transaksi historis terjadi (*leakage*).
- **Solusi**: Gunakan PIT Join engine (misal: Feast `get_historical_features` atau DuckDB temporal ASOF JOIN) dan verifikasi data leakage menggunakan assert testing.

#### 2. Redis Cluster Out of Memory (OOM) Crash
- **Gejala**: Command Redis menghasilkan respons error: `OOM command not allowed when used memory > 'maxmemory'`.
- **Penyebab**: Feature store view tidak menyetel parameter Time-To-Live (TTL) pada feature keys, atau eviction policy di-set ke `noeviction`.
- **Solusi**:
  1. Set TTL definitif pada setiap write.
  2. Konfigurasi `maxmemory-policy volatile-lru` atau `allkeys-lru` di `redis.conf`.
  3. Kompres representasi nilai fitur menggunakan binary encoding.

#### 3. Data Skew & Hot Partitioning pada Kafka / Redis
- **Gejala**: Satu node Redis atau worker Flink mengalami utilisasi CPU 100%, sementara node lainnya idle.
- **Penyebab**: Distribusi key tidak merata (misalnya transaksi sistemik/bot menggunakan entity ID yang sama berulang kali).
- **Solusi**: Gunakan salt hash padding pada entity key (`hash(entity_id) % num_partitions`) untuk streaming partitioner, dan terapkan local cache (in-memory LRU) di layer inference service.

---

### 11. Best Practices (Production Checklist)

- [ ] **Schema Versioning**: Seluruh Feature Views harus memiliki version control (`v1`, `v2`) dan skema data divalidasi via Schema Registry/Pydantic.
- [ ] **Strict Point-in-Time Enforcement**: Dilarang menggunakan query SQL `LEFT JOIN` standar untuk menghubungkan label dengan data fitur time-series.
- [ ] **Imputation & Graceful Fallback**: Inference client wajib memiliki default safe fallback jika Online Store mengembalikan nilai `None`/`Null` atau mengalami timeout.
- [ ] **Circuit Breaker**: Implementasikan pola Circuit Breaker (misal: pybreaker) pada downstream client inference store untuk mencegah cascade failure jika Redis mengalami degradasi.
- [ ] **Active TTL Management**: Setiap record di online store harus memiliki masa kadaluarsa (TTL) eksplisit untuk menghindari akumulasi data zombie.
- [ ] **Online-Offline Drift Monitoring**: Terapkan cron validation harian untuk membandingkan distribusi fitur di online store dan offline store (uji Kolmogorov-Smirnov atau Wasserstein Distance).
- [ ] **Security & Isolation**: Redis/Cassandra online feature store harus berada di private subnet (VPC) tanpa akses publik, dengan autentikasi mTLS.

---

### 12. Hands-on Practice

Buat struktur folder berikut di workstation Anda:
```text
hands-on/m02/
├── docker-compose.yml
├── requirements.txt
├── generate_stream.py
├── stream_aggregator.py
└── client_inference.py
```

#### Langkah 1: Siapkan Environment (`docker-compose.yml`)
```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  redis:
    image: redis:7.0-alpine
    ports:
      - "6379:6379"
```

#### Langkah 2: Dependensi Python (`requirements.txt`)
```text
confluent-kafka==2.3.0
redis==5.0.1
pydantic==2.5.2
duckdb==0.9.2
```

#### Langkah 3: Eksekusi Mock Stream Ingestion & Validasi
Jalankan container dan script ingestion:
```bash
# 1. Jalankan container
docker-compose up -d

# 2. Install dependensi
pip install -r requirements.txt

# 3. Jalankan pipeline stream ingestor (Gunakan skrip Python dari seksi 7.2)
python stream_ingestor.py
```

---

### 13. Exercises

#### Level Easy
- **Tugas**: Tambahkan field baru `device_trust_score` (Float32) pada skrip serialisasi `struct.pack` dan fungsi reader `struct.unpack` pada kode seksi 7.2.
- **Kriteria Keberhasilan**: Program dapat menyimpan dan membaca field baru secara konsisten tanpa merusak alignment byte data lainnya.

#### Level Medium
- **Tugas**: Modifikasi `FeatureStoreStreamIngestor` agar mampu menangani format data corrupt (misal: JSON rusak atau type casting error) dengan memindahkannya ke topic Kafka khusus *Dead Letter Queue* (DLQ) tanpa menghentikan consumer process loop.
- **Kriteria Keberhasilan**: Pesan rusak dialihkan ke topic `features_dlq`, metrik error dinaikkan, dan pemrosesan stream record valid tetap berjalan lancar.

#### Level Hard
- **Tugas**: Buat fungsi temporal join menggunakan **DuckDB** yang menerima DataFrame transaksi berlabel (*Entity, Timestamp, Label*) dan DataFrame fitur time-series (*Entity, FeatureTimestamp, Val1, Val2*), kemudian lakukan *ASOF JOIN* untuk menghasilkan dataset training bebas data leakage.
- **Kriteria Keberhasilan**: Output dataset harus membuktikan secara matematis bahwa tidak ada nilai `FeatureTimestamp` yang melampaui `Timestamp` transaksi untuk setiap record.

---

### 14. Enterprise Challenge

**Skenario**:
Anda adalah Principal MLOps Engineer di sebuah bank digital global. Bank tersebut meluncurkan sistem otorisasi pembayaran lintas negara dengan throughput puncak $80.000\text{ writes/sec}$ dan latensi pembacaan $p99 < 5\text{ ms}$. Sistem menggunakan arsitektur Multi-Region (Singapore dan Jakarta).

**Tantangan**:
1. Rancang arsitektur sinkronisasi Active-Active Feature Store lintas region untuk Redis Online Store dengan strategi resolusi konflik (*Conflict-Free Replicated Data Types - CRDT* vs *Last-Write-Wins*).
2. Tentukan bagaimana menangani situasi ketika koneksi WAN antar-region mengalami split-brain selama 120 detik, namun kedua region tetap harus melayani inferensi lokal tanpa menimbulkan transaksi ganda (*double spending*) yang meloloskan fraud.
3. Buat skema pemulihan dan penjaminan kualitas data (*reconciliation pipeline*) untuk mengaudit offline historical log di Apache Iceberg terhadap rekaman online store yang mengalami kegagalan replikasi.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Konseptual (Basic)
1. Apa fungsi utama Online Store pada arsitektur Feature Store?
   - A. Menjalankan query analitik tahunan berskala terabyte.
   - B. Menyajikan fitur terkini ke inference engine dengan latensi sub-10ms.
   - C. Menyimpan model weights dan artifact checkpoints.
   - D. Menjalankan distributed training berbasis GPU cluster.
   *Jawaban*: **B**. Online Store didesain secara spesifik untuk retrieval berbasis key-value berlatensi ultra-rendah saat inferensi.

2. Apa yang dimaksud dengan *Training-Serving Skew*?
   - A. Model machine learning kehabisan memori GPU saat training.
   - B. Perbedaan akurasi antara epoch 1 dan epoch terakhir training.
   - C. Inkonsistensi komputasi atau nilai fitur antara fase training dan fase serving produksi.
   - D. Kegagalan server inferensi saat menerima beban request HTTP tinggi.
   *Jawaban*: **C**. Ini terjadi ketika definisi/logika fitur di serving berbeda dari yang digunakan saat data training dibuat.

3. Komponen manakah yang bertindak sebagai *single source of truth* untuk definisi metadata fitur?
   - A. Redis In-Memory Engine.
   - B. Feature Registry.
   - C. Kafka Broker.
   - D. Docker Registry.
   *Jawaban*: **B**. Feature Registry menyimpan definisi skema, metadata, dan konfigurasi seluruh fitur.

4. Mengapa serialisasi biner (seperti Protocol Buffers atau Struct Pack) lebih disukai dibanding JSON mentah di Online Feature Store berkapasitas besar?
   - A. Lebih mudah dibaca manual oleh manusia via database UI.
   - B. Meminimalisir konsumsi RAM dan mempercepat I/O jaringan.
   - C. Memungkinkan eksekusi fungsi JavaScript langsung di dalam database.
   - D. Mengubah Redis menjadi relational database.
   *Jawaban*: **B**. Biner jauh lebih ringkas sehingga menekan footprint biaya RAM dan mempercepat deserialisasi jaringan.

5. Apa fungsi parameter Time-To-Live (TTL) pada skema Feature View?
   - A. Menentukan masa kedaluwarsa nilai fitur di online/offline store untuk menghindari memori penuh dan data basi.
   - B. Menghitung waktu training model secara otomatis.
   - C. Mengatur timeout HTTP request ke API Gateway.
   - D. Membatasi umur lisensi library Feast.
   *Jawaban*: **A**. TTL menjaga store hanya menyimpan data dalam jendela waktu yang relevan dan mencegah OOM.

---

#### B. Pertanyaan Analitikal (Intermediate)
6. Manakah dari skenario berikut yang menyebabkan terjadinya *lookahead bias* (data leakage)?
   - A. Mengambil fitur transaksi 5 menit sebelum insiden fraud terjadi.
   - B. Melakukan normalisasi data (Z-score) menggunakan nilai mean dan standard deviasi dari seluruh dataset (termasuk test dataset) sebelum temporal splitting.
   - C. Menggunakan Redis pipeline untuk batch fetching.
   - D. Menyetel TTL selama 30 hari pada rolling aggregation table.
   *Jawaban*: **B**. Menggunakan statistik global dari seluruh rentang waktu (termasuk masa depan) akan membocorkan distribusi data masa depan ke model training.

7. Pada arsitektur Kappa untuk Feature Store, bagaimana pipeline streaming dan batch ditangani?
   - A. Menggunakan dua codebase terpisah: Python untuk streaming dan Scala/Java untuk batch.
   - B. Mengalirkan seluruh pemrosesan data historis dan real-time melalui single streaming processing engine (misal: Apache Flink).
   - C. Mengeliminasi penggunaan offline store dan hanya menggunakan in-memory cache.
   - D. Menggunakan stored procedures di SQL Warehouse untuk seluruh proses stream.
   *Jawaban*: **B**. Pola Kappa memproses semua data (baik historis yang di-replay maupun real-time) lewat engine stream tunggal untuk mencegah logic skew.

8. Jika Online Store Anda menggunakan Redis Cluster dan mulai mengalami degradasi performa akibat *hot key*, tindakan arsitektural mana yang paling tepat?
   - A. Menghapus seluruh index Redis.
   - B. Mengganti Redis dengan file storage CSV.
   - C. Menerapkan local in-memory caching di microservice serving dan menambahkan salt key padding pada data ingestion.
   - D. Mengurangi kecepatan stream ingestion dari Kafka.
   *Jawaban*: **C**. Local cache (L1 cache) menahan lonjakan query untuk key yang sama, dan salt distribution menyebarkan beban ke beberapa node cluster.

9. Apa fungsi utama *As-Of Join* (Point-in-Time Join) dalam pembuatan training dataset?
   - A. Menyatukan data berdasarkan string match regex.
   - B. Mengambil record fitur terakhir yang tersedia tepat sebelum atau sama dengan waktu stempel observasi peristiwa.
   - C. Melakukan kompresi otomatis pada tabel Parquet.
   - D. Menghapus baris yang memiliki nilai duplikat pada primary key.
   *Jawaban*: **B**. As-Of Join mengevaluasi state temporal yang valid pada titik waktu historis tertentu.

10. Ketika sebuah pipeline streaming mengalami network partition selama 1 jam, data yang datang terlambat (*late-arriving events*) dapat merusak agregasi window. Teknik apa yang lazim diterapkan?
    - A. Membuang seluruh data terlambat secara permanen.
    - B. Mematikan worker node database.
    - C. Menggunakan *Watermarking* dengan batas keterlambatan (*allowed lateness*) dan state store reconciliation.
    - D. Memaksa timestamp data diubah ke waktu saat data diterima server.
    *Jawaban*: **C**. Watermarking memungkinkan streaming framework menunggu data terlambat dalam toleransi waktu tertentu sebelum menutup jendela agregasi.

---

#### C. Skenario Kasus Produksi
11. **Kasus 1**: Sistem deteksi fraud Anda tiba-tiba mencatat lonjakan latensi serving dari $4\text{ ms}$ ke $450\text{ ms}$. Setelah dianalisis, CPU Redis berada di 99% akibat pemanggilan command `KEYS *` secara periodik dari sebuah batch healthcheck job. Langkah remedi apa yang harus diambil secara darurat dan permanen?
    - *Solusi Rekayasa*:
      1. **Darurat**: Matikan proses healthcheck job seketika via kill process atau stop cron. Rename atau disable command `KEYS` pada konfigurasi runtime Redis (`rename-command KEYS ""`).
      2. **Permanen**: Ubah metode healthcheck menggunakan `SCAN` dengan pagination non-blocking, atau gunakan metrik bawaan Redis seperti `INFO stats` dan `DBSIZE` untuk monitoring tanpa memblokir single-threaded event loop Redis.

12. **Kasus 2**: Model underwriting pinjaman online mengalami penurunan performa secara drastis setelah 2 minggu berjalan di production. Fitur `pendapatan_bulanan` yang ditarik dari online store selalu bernilai `0.0` untuk pengguna baru, padahal data tersebut tersedia di MySQL core banking.
    - *Solusi Rekayasa*:
      1. Lakukan audit pada Change Data Capture (CDC) connector (misal: Debezium). Periksa apakah terjadi kegagalan pembacaan binlog atau lag consumer pada Kafka topic ingestion.
      2. Periksa skema entity mapping antara MySQL ID (misal: integer bigint) dan Feature Store Entity ID (misal: string UUID/hash). Inkonsistensi casting tipe data sering menyebabkan Redis gagal menemukan key (`miss rate = 100%`), sehingga sistem inferensi mengembalikan nilai default (0.0).

13. **Kasus 3**: Tim data engineering memperbarui definisi fitur `total_spend_30d` dari yang sebelumnya menjumlahkan transaksi *settled* saja, kini mencakup transaksi bertatus *pending*. Namun, tim ML serving masih memprediksi menggunakan logika lama selama 5 hari sebelum akhirnya terdeteksi.
    - *Solusi Rekayasa*:
      1. Terapkan tata kelola **Immutable Feature Definitions** dan skema semantic versioning di Feature Registry. Definisi yang berubah tidak boleh meng-overwrite versi lama secara langsung, melainkan harus didaftarkan sebagai `total_spend_30d_v2`.
      2. Buat deployment guard rail di pipeline CI/CD di mana model metadata didefinisikan secara eksplisit mengikat dependency fitur ke versi spesifik (misal: `features: ["total_spend_30d:v1"]`).

---

### 16. Summary

Feature Store arsitektur modern menyelesaikan tantangan mendasar dalam siklus MLOps: fragmentasi logika rekayasa fitur, bahaya data leakage pada fase pelatihan, dan latensi tinggi saat serving inferensi.

Melalui arsitektur **Dual-Storage Engine**, Feature Store memisahkan kebutuhan high-throughput analytical query (Offline Store) dengan low-latency KV lookups (Online Store). Integrasi streaming pipeline modern berbasis Kafka dan in-memory engine seperti Redis memastikan model menerima state paling mutakhir secara konsisten, sementara Point-in-Time Join menjamin validitas historis eksperimen machine learning secara akurat.