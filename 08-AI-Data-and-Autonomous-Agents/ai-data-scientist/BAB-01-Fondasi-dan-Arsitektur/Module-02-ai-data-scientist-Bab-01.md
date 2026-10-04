# BAB 01: Fondasi dan Arsitektur
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengimplementasikan Arsitektur ML Enterprise**: Membangun topologi sistem machine learning terdistribusi end-to-end yang memisahkan *compute plane*, *storage plane*, dan *serving plane* secara modular.
2. **Menjamin Point-in-Time Correctness**: Mengeliminasi *data leakage* dan *training-serving skew* menggunakan *Feature Store* terdistribusi (online/offline store sync) dengan mekanisme *time-travel queries*.
3. **Menerapkan Data Contracts & Lineage**: Mengintegrasikan skema validasi deklaratif (*pandera* / *Pydantic*) dan *metadata tracking* (*OpenLineage*) untuk memastikan integritas data dari *ingestion* hingga *inference*.
4. **Membangun Inference Engine Skala Tinggi**: Mengorkestrasi pipeline *model serving* rendah latensi (<10ms P99) dengan *dynamic batching* dan optimasi memori GPU/CPU berbasis Triton Inference Server / TorchServe.
5. **Mendeteksi & Memitigasi Drift secara Real-Time**: Mengimplementasikan deteksi *data drift* dan *concept drift* menggunakan metrik statistik (*Population Stability Index* / *Wasserstein Distance*) pada data streaming.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar Machine Learning Lifecycle (CRISP-DM / MLOps fundamentals dari Modul 01).
* Pemrograman Python tingkat lanjut (Type Hinting, Asynchronous Programming `asyncio`, Metaclass, Concurrency).
* Konsep Distributed Systems: CAP Theorem, Event-Driven Architecture, gRPC vs REST, pub/sub (Kafka/Pulsar).
* Dasar orkestrasi container: Docker multi-stage builds, Kubernetes (Pod, Deployment, Service, HPA).
* Penguasaan manipulasi data tabular berbasis memori/disk (Polars, Arrow, DuckDB).

---

### 3. Concept & Internal Architecture (Mendalam)

Arsitektur produksi sistem AI/Data Science enterprise bukan sekadar *wrapping* model `.pkl` ke dalam API FastAPI. Sistem ini harus menangani masalah mendasar yang diidentifikasi oleh Sculley et al. (*Hidden Technical Debt in Machine Learning Systems*), di mana kode ML inti hanya merepresentasikan sekitar 5% dari total ekosistem sistem produksi.

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE ML SYSTEM TOPOLOGY                                   |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Ingestion Layer ]                                                                               |
|  Kafka / S3 / CDC  --> [ Data Contract Engine ] (Schema & Invariant Enforcement)                   |
|                                |                                                                   |
|                                v                                                                   |
|  [ Feature Engineering Plane ]                                                                     |
|  Ray / Spark / Polars Engine   --> Computes State & Aggregations                                  |
|                                |                                                                   |
|            +-------------------+--------------------+                                              |
|            |                                        |                                              |
|            v                                        v                                              |
|  [ Offline Feature Store ]             [ Online Feature Store ]                                    |
|  Parquet / Delta Lake / Iceberg        Redis Cluster / Cassandra                                   |
|  (Time-travel, Point-in-Time Join)     (Low-latency Key-Value, P99 < 2ms)                          |
|            |                                        |                                              |
|            v                                        |                                              |
|  [ Training & Registry Plane ]                      |                                              |
|  Distributed Training (DDP)                         |                                              |
|  Model Registry (MLflow / W&B)                      |                                              |
|  Artifact Store (ONNX / TensorRT)                   |                                              |
|            |                                        |                                              |
|            +-------------------+                    |                                              |
|                                |                    |                                              |
|                                v                    v                                              |
|                 [ Production Inference Plane (Triton / TorchServe) ]                               |
|                 - Dynamic Batching & Concurrent Model Execution                                    |
|                 - Shared Memory IPC / gRPC Protocol                                                |
|                                |                                                                   |
|                                v                                                                   |
|                 [ Continuous Observability Plane ]                                                 |
|                 - Prometheus / OpenTelemetry (Latency, Memory, QPS)                                |
|                 - Drift Engine (PSI, KS-Test, Evidentiary Sampling)                                |
+----------------------------------------------------------------------------------------------------+
```

#### A. The Feature Store & Point-in-Time Joins
Masalah paling fatal dalam enterprise ML adalah **Training-Serving Skew** yang disebabkan oleh feature leakage saat training. Feature store memecahkan ini melalui dual-storage engine:
1. **Online Store (Low-Latency Read)**: Database terdistribusi berbasis in-memory (misal: Redis, DragonflyDB) atau wide-column (ScyllaDB) yang menyimpan nilai fitur paling mutakhir (*latest state*) untuk entitas $E$.
2. **Offline Store (High-Throughput Analytical Write/Read)**: Data lakehouse (Delta Lake, Apache Iceberg, Apache Hudi) yang menyimpan log histori fitur append-only beserta stempel waktu perubahan ($t_{event}$).

Mekanisme **Point-in-Time Correct Join (AS-OF Join)**:
Diberikan sekumpulan label target $L$ dengan stempel waktu $t_L$ dan entitas $ID$, query point-in-time menjamin bahwa fitur $F$ yang diambil adalah nilai fitur terakhir yang diketahui pada waktu $t \le t_L$, secara matematis:
$$F_{\text{actual}}(ID, t_L) = \arg\max_{t} \{ F(ID, t) \mid t \le t_L \}$$
Tanpa proteksi ini, model akan belajar dari nilai fitur di masa depan ($t > t_L$), menghasilkan metrik validasi yang sangat tinggi (*false optimism*) namun performa hancur saat deployment.

#### B. Dynamic Batching & Low-Latency Serving Internals
Framework web tradisional (FastAPI/Flask) mengeksekusi model inference satu request per waktu (atau bergantung pada thread pool), yang menyebabkan utilisasi GPU sangat rendah (bound to compute latency, underutilized tensor cores). 

Inference Server tingkat enterprise (seperti NVIDIA Triton) menggunakan algoritma **Dynamic Batcher**:
1. Request dari berbagai klien masuk ke dalam antrean *in-memory non-blocking ring buffer*.
2. Scheduler mengumpulkan request hingga mencapai `max_batch_size` ATAU batas waktu `max_queue_delay_microseconds` terlampaui.
3. Tensor digabungkan pada dimensi batch (axis 0) menggunakan memori teralokasi (*Pinned Host Memory*).
4. Satu kernel CUDA dieksekusi untuk memproses seluruh batch secara paralel di Tensor Cores.
5. Hasil inferensi dipecah kembali (*unbatched*) dan didistribusikan ke masing-masing koneksi gRPC stream.

---

### 4. Why & What

| Dimensi | Pendekatan Skrip / Ad-Hoc ML | Arsitektur Enterprise ML |
| :--- | :--- | :--- |
| **Integrasi Data** | Pandas membaca raw CSV/SQL langsung di skrip training. | Data contract divalidasi pada ingress; transformasi fitur dikelola terpusat. |
| **Koleksi Fitur** | Query SQL manual yang ditulis ulang di backend service (duplikasi logika). | Single-definition via Feature Store; logika offline dan online dijamin identik. |
| **Model Packaging** | File `model.pkl` dimuat via `pickle.load()` langsung di app server. | Format terstandardisasi (ONNX, TensorRT, TorchScript) dengan runtime isolated. |
| **Serving Protocol** | REST JSON payload melalui HTTP/1.1 (overhead serialisasi tinggi). | gRPC / Protocol Buffers melalui HTTP/2 dengan binary payload & direct memory mapping. |
| **Monitoring** | Hanya monitoring server health dasar (CPU, RAM, HTTP 500 rate). | Monitoring multidimensi: System metrics + Statistical Data Drift + Concept Drift. |

* **Why Data Contracts?** Menghentikan fenomena *silent failure*. Dalam software engineering konvensional, schema mismatch menghasilkan exception. Dalam ML, perubahan distribusi atau hilangnya kolom kategorikal sering kali hanya dinormalisasi menjadi `NaN` atau `0`, menyebabkan model menghasilkan prediksi sampah tanpa menimbulkan crash.
* **Why Triton/Inference Engine?** Menghindari Python Global Interpreter Lock (GIL) constraint, mengoptimasi pipeline I/O menggunakan CUDA IPC, dan memfasilitasi model concurrency (menjalankan model ensemble secara asinkron di kartu GPU yang sama).

---

### 5. How (Workflow Detail)

Alur kerja implementasi arsitektur produksi:

1. **Definisi Kontrak Data (Ingress)**
   * Definisikan skema secara deklaratif menggunakan type assertions, batas rentang nilai (*invariants*), dan nullability constraints.
   * Setiap batch data ingestion divalidasi terhadap kontrak ini. Data invalid diarahkan ke Dead-Letter Queue (DLQ).

2. **Transformasi & Dual Write Feature Store**
   * Ekstraksi fitur menggunakan engine komputasi berbasis Arrow (Polars/Ray) untuk meminimalkan alokasi memori.
   * Tulis data mutakhir ke Online Feature Store (Key-Value TTL based).
   * Tulis data terkompresi (Snappy/ZSTD Parquet) ke Offline Feature Store partitioned by date.

3. **Point-in-Time Join untuk Training Dataset Generation**
   * Hubungkan observation targets dengan offline feature tables menggunakan operator As-Of Join.
   * Serialisasi output ke format teroptimasi (TFRecord, WebDataset, atau Apache Feather).

4. **Training, Optimasi Graf & Registrasi**
   * Model dilatih dengan tracking metrik komprehensif.
   * Model dikonversi ke intermediate representation (ONNX) dan dioptimasi grafnya (operator fusion, dynamic range quantization FP16/INT8).
   * Daftarkan model ke Model Registry dengan *cryptographic digest* (SHA256) untuk penjaminan keaslian artifak.

5. **Inference Deployment dengan Dynamic Batching**
   * Deploy ke inference server dengan konfigurasi auto-batching.
   * Hubungkan input ingestion client via gRPC interface.

6. **Continuous Monitoring & Feedback Loop**
   * Buffer inference input/output ke Kafka stream.
   * Lakukan kalkulasi periodik distribusi statistik (PSI) untuk mendeteksi drift secara asinkron.
   * Trigger auto-retraining pipeline bila threshold terlampaui.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Dapur Restoran Bintang Lima vs Gerobak Makanan Instan
* **Ad-hoc ML (Gerobak Makanan Instan)**: Satu koki berbelanja bahan sendiri, memotong, memasak, dan mengantar pesanan langsung ke konsumen. Jika bumbu berubah rasa dari pemasok, koki tidak sadar dan rasa masakan menjadi aneh. Skalabilitas nol.
* **Enterprise ML (Dapur Bintang Lima Terautomasi)**: 
  * *Data Contract*: Inspektur kualitas bahan baku di pintu masuk memeriksa kesegaran daging dan sayur sebelum masuk gudang pendingin.
  * *Feature Store*: Bahan baku sudah dicuci, dipotong seragam, dan disimpan di dua tempat: kulkas cepat saji (*Online Store*) untuk koki masak, dan lemari beku berlabel tanggal presisi (*Offline Store*) untuk resep riset menu baru.
  * *Dynamic Batching*: Oven industri besar yang menunggu piring ditata bersamaan hingga kapasitas optimal sebelum memanggang secara simultan, alih-alih memanggang satu kue kecil setiap 5 menit.
  * *Drift Monitoring*: Pengawas rasa yang secara acak mencicipi output masakan dan mengukur keasaman/kadar garam harian terhadap standar baku.

```
       INGESTION PHASE                   SERVING & MONITORING PHASE
       
      Raw Event Stream                       Client Real-time App
             |                                        |
             v                                        | (gRPC Request)
     +---------------+                                v
     | Data Contract |                      +-------------------+
     |  Validation   |                      |  Inference Engine |
     +-------+-------+                      |     (Triton)      |
             |                              +---------+---------+
      (Pass) | (Fail -> Dead Letter)                  |
             v                                        | (Pulls latest context)
    +-----------------+                               v
    | Feature Compute |                     +-------------------+
    | (Polars / Ray)  |                     |   Online Store    |
    +---+---------+---+                     |  (Redis / Dragon) |
        |         |                         +-------------------+
 (Historical)  (Latest State)                         |
        |         |                                   | (Inference Logs)
        v         v                                   v
   +-------+   +-------+                     +-------------------+
   |Offline|   |Online |                     |   Kafka Stream    |
   | Store |   | Store |                     +---------+---------+
   +---+---+   +-------+                               |
       |                                               v
       | (Time-travel Join)                  +-------------------+
       v                                     |   Drift Engine    |
+--------------+                             | (PSI / Dist Test) |
|Model Training|                             +---------+---------+
|  & Registry  |                                       |
+--------------+                          (Drift > Limit -> Trigger Retrain)
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Strict Data Contract & Invariant Validation via Pandera
Validasi data eksplisit yang memblokir data korup sebelum menyentuh pipeline feature engineering.

```python
import pandera as pa
from pandera.typing import Series
import pandas as pd
from datetime import datetime

class TransactionDataContract(pa.DataFrameModel):
    transaction_id: Series[str] = pa.Field(unique=True, nullable=False)
    user_id: Series[str] = pa.Field(nullable=False, regex=r"^usr_[0-9a-f]{8}$")
    amount: Series[float] = pa.Field(ge=0.01, le=1_000_000.0, nullable=False)
    timestamp: Series[pd.Timestamp] = pa.Field(le=datetime.now(), nullable=False)
    device_trust_score: Series[float] = pa.Field(ge=0.0, le=1.0, nullable=False)

    class Config:
        strict = True  # Tolak kolom ekstra yang tidak terdefinisi
        coerce = True  # Upayakan casting tipe data otomatis jika valid

def validate_ingestion_batch(df_raw: pd.DataFrame) -> pd.DataFrame:
    try:
        validated_df = TransactionDataContract.validate(df_raw, lazy=True)
        return validated_df
    except pa.errors.SchemaErrors as err:
        # Menangkap seluruh kegagalan skema sekaligus (lazy validation)
        print(f"[ALERT] Kontrak Data Terlanggar! Ditemukan {len(err.failure_cases)} anomali.")
        print(err.failure_cases[["check", "column", "failure_case"]])
        raise ValueError("Data Contract Violation: Processing Halted.")

# Pengujian
raw_data = pd.DataFrame({
    "transaction_id": ["tx_101", "tx_102", "tx_103"],
    "user_id": ["usr_00000001", "usr_00000002", "invalid_id_format"],
    "amount": [150.50, -10.00, 500.00],  # amount negatif melanggar ge=0.01
    "timestamp": [pd.Timestamp.now(), pd.Timestamp.now(), pd.Timestamp.now()],
    "device_trust_score": [0.95, 0.40, 1.50],  # 1.50 melanggar le=1.0
})

if __name__ == "__main__":
    try:
        validate_ingestion_batch(raw_data)
    except ValueError as e:
        print(f"Pipeline status: Gagal tervalidasi secara aman.")
```

#### B. Practical Example: High-Performance Point-in-Time Join & Real-Time Scoring Engine
Implementasi zero-leakage offline feature store joiner menggunakan Polars Engine, digabungkan dengan pipeline online feature retrieval yang tahan konkurensi.

```python
import polars as pl
from datetime import datetime, timedelta
import numpy as np
import redis
import json
from typing import Dict, Any, List

# =====================================================================
# 1. OFFLINE ENGINE: Zero-Leakage Point-in-Time Feature Lookup
# =====================================================================
class OfflinePointInTimeEngine:
    """
    Menggabungkan observation labels dengan log histori feature updates
    menggunakan operator AS-OF join, menjamin zero-leakage temporal.
    """
    @staticmethod
    def construct_training_matrix(
        events_df: pl.DataFrame, 
        features_history_df: pl.DataFrame
    ) -> pl.DataFrame:
        """
        events_df: ['user_id', 'event_timestamp', 'target_label']
        features_history_df: ['user_id', 'feature_timestamp', 'avg_spent_7d', 'failed_logins_24h']
        """
        # Validasi tipe data timestamp
        assert events_df.schema["event_timestamp"] == pl.Datetime
        assert features_history_df.schema["feature_timestamp"] == pl.Datetime

        # Sort mutlak diperlukan untuk operasi AS-OF
        sorted_events = events_df.sort("event_timestamp")
        sorted_features = features_history_df.sort("feature_timestamp")

        # As-of join: Mengambil record feature terbaru yang terjadi SEBELUM atau TEPAT PADA waktu event
        training_matrix = sorted_events.join_asof(
            sorted_features,
            left_on="event_timestamp",
            right_on="feature_timestamp",
            by="user_id",
            strategy="backward"
        )
        
        return training_matrix

# =====================================================================
# 2. ONLINE ENGINE: Low-Latency Feature Store Client with Connection Pooling
# =====================================================================
class OnlineFeatureStoreClient:
    def __init__(self, redis_pool: redis.ConnectionPool):
        self.client = redis.Redis(connection_pool=redis_pool)

    def write_online_features(self, entity_id: str, features: Dict[str, Any], ttl_seconds: int = 86400):
        key = f"entity:user:{entity_id}"
        self.client.set(name=key, value=json.dumps(features), ex=ttl_seconds)

    def get_online_features_batch(self, entity_ids: List[str]) -> List[Dict[str, Any]]:
        keys = [f"entity:user:{uid}" for uid in entity_ids]
        raw_results = self.client.mget(keys)
        
        parsed_results = []
        for raw in raw_results:
            if raw:
                parsed_results.append(json.loads(raw))
            else:
                # Cold-start handling / Default fallback feature vector
                parsed_results.append({"avg_spent_7d": 0.0, "failed_logins_24h": 0})
        return parsed_results

# =====================================================================
# 3. VERIFIKASI EKSEKUSI PIPELINE
# =====================================================================
if __name__ == "__main__":
    # Generate Dummy Historical Timeline Data
    t0 = datetime(2026, 3, 1, 10, 0, 0)
    
    # Feature updates yang terjadi sepanjang waktu
    feature_updates = pl.DataFrame({
        "user_id": ["u1", "u1", "u1", "u2"],
        "feature_timestamp": [
            t0, 
            t0 + timedelta(minutes=15), 
            t0 + timedelta(minutes=45), 
            t0
        ],
        "avg_spent_7d": [50.0, 75.0, 120.0, 10.0],
        "failed_logins_24h": [0, 1, 3, 0]
    }).with_columns(pl.col("feature_timestamp").cast(pl.Datetime))

    # Target events (e.g. Fraud detection event check)
    target_events = pl.DataFrame({
        "user_id": ["u1", "u1", "u2"],
        "event_timestamp": [
            t0 + timedelta(minutes=10),  # Harus match update ke-1 (t0) -> avg: 50.0
            t0 + timedelta(minutes=30),  # Harus match update ke-2 (t0+15m) -> avg: 75.0
            t0 + timedelta(minutes=5)   # Harus match update t0 -> avg: 10.0
        ],
        "target_label": [0, 1, 0]
    }).with_columns(pl.col("event_timestamp").cast(pl.Datetime))

    pit_engine = OfflinePointInTimeEngine()
    dataset = pit_engine.construct_training_matrix(target_events, feature_updates)
    print("=== DATASET HASIL POINT-IN-TIME JOIN (OFFLINE) ===")
    print(dataset)

    # Validasi Tidak Ada Leakage:
    # Pada t0 + 30m, u1 belum melakukan update pada t0 + 45m.
    u1_second_event = dataset.filter(
        (pl.col("user_id") == "u1") & (pl.col("event_timestamp") == t0 + timedelta(minutes=30))
    )
    assert u1_second_event["avg_spent_7d"][0] == 75.0, "FATAL: Leakage Terdeteksi!"
    print("\n[PASSED] Point-in-Time Join terbukti zero-leakage.")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Deteksi Fraud Transaksi Real-time (Skala FinTech Super-App)
* **Kebutuhan Bisnis**: Menilai risiko fraud dari 85.000 transaksi per detik (TPS peak) dengan batas SLA latensi hard limit P99 < 15ms. Jika inferensi gagal atau timeout dalam 15ms, sistem harus fallback ke heuristic engine tanpa menghentikan proses transaksi checkout.

```
                           +----------------------------------------+
                           |  Payment Gateway Ingress (85,000 QPS)  |
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           |          Envoy Edge Proxy              |
                           |   (Circuit Breaker, 12ms Timeout)      |
                           +-------------------+--------------------+
                                               |
                                               v
                           +----------------------------------------+
                           |  Inference Gateway (Golang / C++)      |
                           +--------+----------------------+--------+
                                    |                      |
      (Async Fetch Features, 2ms)   |                      | (Payload gRPC)
                                    v                      v
                       +-----------------------+  +--------------------------+
                       | Aerospike Distributed |  | Triton Cluster (GPU Pods)|
                       | Feature Cache         |  | Model: XGBoost + ONNX    |
                       +-----------------------+  | Dynamic Batching: 64     |
                                                  +------------+-------------+
                                                               |
                                                               v
                                                  +--------------------------+
                                                  | Kafka Monitoring Topic   |
                                                  | (Asynchronous Fire&Forget|
                                                  +------------+-------------+
                                                               |
                                                               v
                                                  +--------------------------+
                                                  | Drift Engine (Flink)     |
                                                  | Metrik: KS-Test & PSI    |
                                                  +--------------------------+
```

* **Komponen Arsitektur**:
  1. **Network Layer**: Envoy Proxy dengan proteksi *circuit breaker*. Menggunakan gRPC multiplexing via HTTP/2.
  2. **Online Store**: Aerospike cluster (Hybrid Memory Architecture: Primary index di RAM, data fitur di NVMe SSD) untuk latensi pembacaan sub-milidetik ($P99 < 1.8\text{ms}$).
  3. **Execution Runtime**: Triton Inference Server dengan akselerator TensorRT. Menggunakan shared memory (POSIX shared memory) antara host proxy dan Triton instance untuk menghindari overhead serialisasi soket kernel loopback.
  4. **Dynamic Batching Configuration**:
     ```protobuf
     # triton_model_repository/fraud_detector/config.pbtxt
     name: "fraud_detector"
     platform: "onnxruntime_onnx"
     max_batch_size: 128
     dynamic_batching {
       max_queue_delay_microseconds: 1500  # 1.5ms window
       preferred_batch_size: [ 32, 64, 128 ]
     }
     instance_group [
       {
         count: 4
         kind: KIND_GPU
         gpus: [ 0 ]
       }
     ]
     ```
  5. **Observability**: Kafka topic menerima data payload asinkron (*fire-and-forget*). Apache Flink engine memproses stream tersebut untuk menghitung *Wasserstein Distance* dan *Population Stability Index* (PSI) terhadap distribusi baseline training per sliding window 10 menit.

---

### 9. Trade-offs

Mengambil keputusan arsitektur sistem ML membutuhkan kompromi multi-faktor:

| Keputusan Arsitektur | Keuntungan | Kompromi / Biaya (*Trade-off*) | Mitigasi |
| :--- | :--- | :--- | :--- |
| **Dynamic Batching Engine** | Utilisasi GPU melonjak hingga 80-95%; throughput total meningkat hingga 8x lipat. | Menambahkan *tail latency* pada request individual akibat buffer queuing time window. | Pasang `max_queue_delay_microseconds` yang ketat (misal 10-15% dari total budget SLA). |
| **Dual Storage Feature Store** | Tidak ada komputasi berulang; eliminasi mutlak training-serving skew. | Biaya infrastruktur tinggi (Redis Cluster + S3 Storage); kompleksitas pipeline sinkronisasi. | Gunakan Redis TTL yang agresif; batasi entity context hanya pada fitur yang memiliki impact Shapley tinggi. |
| **Aggressive Float Quantization (INT8)** | Ukuran footprint memori model turun 75%; latensi inferensi berkurang drastis (hingga 3-4x). | Risiko penurunan akurasi prediktif (*accuracy degradation*) jika kalibrasi data representatif tidak presisi. | Gunakan Quantization-Aware Training (QAT) alih-alih Post-Training Quantization (PTQ) polos. |
| **Synchronous Data Contract Validation** | Mencegah silent model failures dan keracunan data (*data poisoning*). | Penambahan latensi CPU overhead pada ingress processing pipeline. | Validasi parsial menggunakan vector hash checking atau komputasi validasi berbasis C-extension/Rust (*Polars/Pydantic core*). |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Leakage pada Preprocessing Fitur Skala Global
* *Problem*: Melakukan normalisasi (misal: `StandardScaler.fit_transform(X)`) pada seluruh dataset sebelum pemisahan data train-test split atau time-based split.
* *Dampak*: Mean dan variance dari set testing bocor ke dalam set training. Model tampak superior di local test, tapi jeblok di produksi.
* *Troubleshooting*: Terapkan `sklearn.pipeline.Pipeline` yang di-*fit* HANYA pada training data, atau komputasi statistik agregasi murni menggunakan feature store berbasis time-travel.

#### Kesalahan 2: Silent Data Drift (Distribusi Berubah Tanpa Error Kode)
* *Problem*: Format data valid, tidak ada error exception, tetapi data input mengalami pergeseran makna (*Covariate Shift*). Contoh: Nilai mata uang berubah drastis karena devaluasi, atau integrasi aplikasi pihak ketiga mengirimkan koordinat GPS dalam format yang berbeda.
* *Solusi & Skrip Deteksi*: Implementasikan automated statistical divergence detector (Population Stability Index / PSI).

```python
import numpy as np

def calculate_psi(expected: np.ndarray, actual: np.ndarray, num_buckets: int = 10) -> float:
    """
    Menghitung Population Stability Index (PSI) antara dua distribusi.
    PSI < 0.1  : Tidak ada perubahan signifikan (Stable)
    0.1 <= PSI < 0.2: Perubahan moderat (Peringatan)
    PSI >= 0.2 : Drift signifikan! Model wajib di-retrain.
    """
    # Pastikan data bebas NaN
    expected = expected[~np.isnan(expected)]
    actual = actual[~np.isnan(actual)]
    
    # Tentukan batas bucket berdasarkan quantile dataset baseline (expected)
    percentiles = np.linspace(0, 100, num_buckets + 1)
    buckets = np.percentile(expected, percentiles)
    buckets[0] = -np.inf
    buckets[-1] = np.inf

    # Hitung frekuensi observasi dalam bucket
    expected_counts, _ = np.histogram(expected, bins=buckets)
    actual_counts, _ = np.histogram(actual, bins=buckets)

    # Konversi ke proporsi dengan Laplace smoothing untuk mencegah pembagian nol
    expected_pct = np.where(expected_counts == 0, 1e-4, expected_counts) / len(expected)
    actual_pct = np.where(actual_counts == 0, 1e-4, actual_counts) / len(actual)

    # Formula matematis PSI: Sum( (Actual% - Expected%) * ln(Actual% / Expected%) )
    psi_value = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi_value)

# Demonstrasi
baseline_data = np.random.normal(loc=50, scale=10, size=10000)
prod_current_data = np.random.normal(loc=58, scale=12, size=10000) # Covariate Shift

psi = calculate_psi(baseline_data, prod_current_data)
print(f"Calculated Population Stability Index: {psi:.4f}")
if psi >= 0.2:
    print("[CRITICAL ALERT] Terdeteksi High Data Drift! Triggering retrain event pipeline.")
```

#### Kesalahan 3: GPU Out-Of-Memory (OOM) Akibat Spike Concurrency
* *Problem*: Lonjakan tiba-tiba pada payload permintaan menyebabkan memori GPU terisi penuh oleh dynamic allocation tensor, mengakibatkan crash `CUDA out of memory` yang membunuh seluruh runtime pod inference.
* *Troubleshooting*: 
  1. Batasi ukuran alokasi memori runtime secara eksplisit (misal: via parameter Triton/PyTorch `per_process_gpu_memory_fraction`).
  2. Implementasikan HTTP 429 (Too Many Requests) backpressure mechanism pada gateway level ketika worker queues melebihi 90% kapasitas.
  3. Konfigurasi CPU page-locked memory swapping buffer secara terisolasi.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum mempromosikan model ke stage `Production`:

| Status | Item Pengecekan | Metrik / Kriteria Kelulusan |
| :---: | :--- | :--- |
| [ ] | **Strict Data Contracts** | Seluruh data ingestion memiliki validasi skema dan tipe yang memblokir invalid input secara otomatis. |
| [ ] | **Point-in-Time Verified** | Training data diekstrak secara eksklusif menggunakan AS-OF joins berbasis event time; lolos audit zero-leakage. |
| [ ] | **Artifact Standardization** | Model diekspor ke standard binary graph (ONNX, TensorRT) dan telah divalidasi keidentikan numerik outputnya ($L_\infty < 1e-4$) terhadap baseline PyTorch/XGBoost. |
| [ ] | **Latency & Concurrency SLA** | Uji beban (Load Testing) membuktikan P99 latency berada di bawah batas target sistem pada 1.5x estimasi peak QPS. |
| [ ] | **Graceful Fallback Mode** | Jika inferensi server gagal merespons dalam $X$ ms, fallback heuristik/default rule tereksekusi tanpa melempar HTTP 500 ke klien. |
| [ ] | **Lineage Immutability** | Setiap model terdaftar memiliki hash commit Git, identifier dataset DVC/Delta Lake, dan seed training yang tersimpan permanen. |
| [ ] | **Active Monitoring Setup** | Prometheus metrics (latensi inference, GPU compute, VRAM) dan drift metric calculation (PSI/KS) aktif dan terhubung ke pager alert. |

---

### 12. Hands-on Practice

Buat struktur direktori praktikum berikut:
```text
hands-on/m02/
├── contracts/
│   └── order_contract.py
├── engine/
│   └── serving_simulator.py
└── main.py
```

#### File: `hands-on/m02/contracts/order_contract.py`
```python
import pandera as pa
from pandera.typing import Series
import pandas as pd

class HighValueOrderContract(pa.DataFrameModel):
    order_id: Series[str] = pa.Field(unique=True, nullable=False)
    customer_id: Series[str] = pa.Field(nullable=False)
    order_amount: Series[float] = pa.Field(ge=1.0, le=500_000.0)
    items_count: Series[int] = pa.Field(ge=1, le=100)
    device_risk_score: Series[float] = pa.Field(ge=0.0, le=1.0)
    event_timestamp: Series[pd.Timestamp] = pa.Field(nullable=False)

    class Config:
        strict = True
        coerce = True
```

#### File: `hands-on/m02/engine/serving_simulator.py`
```python
import asyncio
import time
from typing import List, Dict, Any
import numpy as np

class EnterpriseInferenceServer:
    """
    Simulasi arsitektur serving modern:
    Menerapkan dynamic batching internal queue untuk mengoptimalkan throughput.
    """
    def __init__(self, max_batch_size: int = 8, max_wait_time_ms: float = 10.0):
        self.max_batch_size = max_batch_size
        self.max_wait_time_sec = max_wait_time_ms / 1000.0
        self.queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False

    async def start(self):
        self.is_running = True
        asyncio.create_task(self._batch_processing_loop())

    async def stop(self):
        self.is_running = False

    async def predict(self, features: List[float]) -> float:
        loop = asyncio.get_running_loop()
        response_future = loop.create_future()
        await self.queue.put((features, response_future))
        return await response_future

    async def _batch_processing_loop(self):
        while self.is_running:
            batch = []
            start_time = asyncio.get_event_loop().time()

            # Dynamic batching window collection
            while len(batch) < self.max_batch_size:
                timeout = self.max_wait_time_sec - (asyncio.get_event_loop().time() - start_time)
                if timeout <= 0 and len(batch) > 0:
                    break
                try:
                    item = await asyncio.wait_for(self.queue.get(), timeout=max(timeout, 0.001))
                    batch.append(item)
                except asyncio.TimeoutError:
                    break

            if not batch:
                await asyncio.sleep(0.001)
                continue

            # Unpack payload dan targets
            inputs = [item[0] for item in batch]
            futures = [item[1] for item in batch]

            # Vectorized Matrix Inference (Simulasi Model Forward Pass di GPU)
            inputs_array = np.array(inputs)
            scores = self._mock_tensor_core_forward(inputs_array)

            # Selesaikan promise/futures
            for fut, score in zip(futures, scores):
                if not fut.done():
                    fut.set_result(float(score))

    def _mock_tensor_core_forward(self, tensor_batch: np.ndarray) -> np.ndarray:
        # Simulasi compute forward pass: Sigmoid(W*x + b)
        weights = np.ones((tensor_batch.shape[1], 1)) * 0.5
        raw_logits = np.dot(tensor_batch, weights).squeeze(-1)
        probabilities = 1.0 / (1.0 + np.exp(-raw_logits))
        # Simulasi delay inferensi hardware
        time.sleep(0.005) 
        return probabilities
```

#### File: `hands-on/m02/main.py`
```python
import asyncio
import time
import pandas as pd
import numpy as np
from contracts.order_contract import HighValueOrderContract
from engine.serving_simulator import EnterpriseInferenceServer
import pandera as pa

async def main():
    print("=== 1. VALIDASI KONTRAK DATA ===")
    sample_data = pd.DataFrame({
        "order_id": [f"ord_{i}" for i in range(5)],
        "customer_id": [f"cust_{i}" for i in range(5)],
        "order_amount": [120.0, 450.5, 99.0, 1500.0, 320.0],
        "items_count": [2, 5, 1, 12, 3],
        "device_risk_score": [0.1, 0.05, 0.8, 0.2, 0.15],
        "event_timestamp": [pd.Timestamp.now()] * 5
    })
    
    try:
        validated = HighValueOrderContract.validate(sample_data)
        print(f"Data validation passed: {len(validated)} records conform to schema.")
    except pa.errors.SchemaErrors as err:
        print(f"Data failed: {err}")
        return

    print("\n=== 2. MEMULAI HIGH-THROUGHPUT SERVING ENGINE SIMULATOR ===")
    server = EnterpriseInferenceServer(max_batch_size=4, max_wait_time_ms=15.0)
    await server.start()

    # Ekstraksi fitur untuk scoring
    feature_matrix = validated[["order_amount", "items_count", "device_risk_score"]].to_numpy()

    # Simulasi 10 Concurrent Request yang masuk secara asinkron
    print("Mengirimkan 10 request bersamaan...")
    t0 = time.perf_counter()
    
    tasks = []
    for i in range(10):
        # Pick feature vector secara acak
        feat = feature_matrix[i % len(feature_matrix)].tolist()
        tasks.append(server.predict(feat))

    results = await asyncio.gather(*tasks)
    elapsed = (time.perf_counter() - t0) * 1000.0

    print(f"Selesai 10 scoring requests dalam {elapsed:.2f} ms")
    for idx, score in enumerate(results):
        print(f"Request #{idx+1} Probabilitas Fraud: {score:.4f}")

    await server.stop()
    print("\nPipeline execution clean and complete.")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 13. Exercise

#### Level: Easy
1. Tambahkan pengecekan pada `HighValueOrderContract` di hands-on: Kolom `email_domain` harus valid hanya untuk domain berikut: `["enterprise.com", "partner.org", "internal.corp"]`.
2. Gunakan validator regex kustom pada Pandera untuk memvalidasi kolom tersebut.

#### Level: Medium
1. Buat skrip python yang memonitor drift data mingguan.
2. Generate baseline synthetic data dari distribusi normal $(\mu=0, \sigma=1)$ sebanyak 5.000 sampel.
3. Simulasikan data produksi minggu ke-1 s/d minggu ke-4 di mana nilai mean bergeser perlahan: $\mu_w \in [0.05, 0.15, 0.35, 0.70]$.
4. Hitung nilai Wasserstein Distance (`scipy.stats.wasserstein_distance`) dan PSI untuk setiap minggu. Tentukan pada minggu ke berapa alert harus berbunyi.

#### Level: Hard
1. Buat implementasi Python murni (menggunakan `multiprocessing` dan `SharedMemory` dari library standar Python 3.8+) yang mengimplementasikan IPC (Inter-Process Communication) feature cache.
2. Proses A menulis matrix fitur berukuran $1000 \times 128$ (float32) ke POSIX Shared Memory block.
3. Proses B membaca shared memory tersebut tanpa serialisasi/deserialisasi JSON atau pickle (gunakan `np.ndarray` dengan referensi buffer pointer langsung).
4. Ukur dan buktikan latensi baca-tulis sub-milidetik ($< 0.1\text{ms}$).

---

### 14. Challenge

**Skenario Tantangan**: Arsitektur Multi-Region Active-Active Feature Store & Zero-Downtime Rollback.

Anda ditunjuk sebagai Principal AI Architect di platform perbankan global. Anda diminta merancang arsitektur serving dan feature store yang memenuhi kualifikasi:
1. Berjalan pada 2 region terpisah (*Region-A: Jakarta* dan *Region-B: Singapore*) secara Active-Active.
2. Kedua region melayani inferensi lokal dengan latensi pembacaan fitur online $< 2\text{ms}$.
3. Jika model versi baru (`v2.1.0`) yang di-deploy mengalami kegagalan bisnis (misal: tingkat false-positive fraud melonjak 3x lipat), sistem harus melakukan *automated instantaneous rollback* ke model `v2.0.9` dalam waktu kurang dari 500 milidetik secara global tanpa kehilangan single inflight inference request.

**Tugas Anda**:
* Rancang spesifikasi arsitektur teknis lengkap (tuliskan format dokumen desain teknis):
  * Mekanisme sinkronisasi data antar region feature store (Conflict resolution strategy: Last-Write-Wins vs CRDTs).
  * Mekanisme Zero-Downtime deployment dan circuit breaking rollback (Blue-Green vs Shadow Deployment via Envoy gRPC routing).
  * Skema data contract backward-compatibility untuk menjamin model `v2.0.9` tidak crash saat membaca fitur yang diperbarui oleh skema `v2.1.0`.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa penyebab utama terjadinya *training-serving skew* dalam implementasi machine learning enterprise?
   * A. Model di-deploy menggunakan server CPU padahal dilatih di GPU.
   * B. Perbedaan implementasi atau pergeseran waktu (*temporal leakage*) dalam ekstraksi fitur antara proses offline training dan real-time serving.
   * C. Penggunaan protokol REST alih-alih gRPC.
   * D. Ukuran batch training terlalu besar dibanding dynamic batch inference.
   * *Jawaban*: **B**. Training-serving skew terjadi saat logika rekayasa fitur di training berbeda dengan runtime, atau saat data masa depan bocor ke dataset training offline.

2. Mengapa format biner seperti ONNX atau TensorRT lebih diutamakan untuk inferensi produksi dibandingkan Python `.pkl` (Pickle)?
   * A. File Pickle tidak mendukung deep learning.
   * B. ONNX dan TensorRT memisahkan graph komputasi dari runtime interpreter Python, mengeliminasi overhead GIL dan memungkinkan optimasi level kernel hardware.
   * C. File Pickle selalu memiliki ukuran 10x lebih besar.
   * D. TensorRT hanya dapat bekerja dengan format teks JSON.
   * *Jawaban*: **B**. Runtime terkompilasi mengeliminasi dependensi Python engine dan GIL, mengizinkan operator fusion dan akselerasi tensor hardware.

3. Apa fungsi utama operator **AS-OF Join** pada arsitektur offline feature store?
   * A. Mempercepat performa query SQL dengan parallel worker.
   * B. Menghubungkan observasi label dengan state fitur paling mutakhir yang valid pada saat stempel waktu kejadian terjadi (*time-travel consistency*).
   * C. Menggabungkan dua tabel yang tidak memiliki primary key.
   * D. Melakukan deduplikasi otomatis pada baris data yang identik.
   * *Jawaban*: **B**. AS-OF join menjamin bahwa tidak ada data fitur yang diambil melampaui timestamp target label (mencegah lookahead bias).

4. Apa dampak negatif langsung jika parameter `max_queue_delay_microseconds` pada sistem dynamic batching Triton disetel terlalu tinggi (misal: 500 ms)?
   * A. GPU akan mengalami Out-Of-Memory (OOM).
   * B. Latensi individual request klien meningkat drastis saat traffic rendah (under-utilized queue).
   * C. Akurasi numerik model berkurang drastis.
   * D. Koneksi gRPC otomatis terputus.
   * *Jawaban*: **B**. Request pertama yang masuk antrean harus menunggu hingga timeout 500ms berakhir jika batch tidak kunjung penuh, merusak SLA tail latency.

5. Manakah nilai Population Stability Index (PSI) yang secara umum menjadi batas kritis bahwa suatu model machine learning wajib di-retrain karena severe drift?
   * A. $PSI < 0.01$
   * B. $0.01 \le PSI < 0.05$
   * C. $PSI \ge 0.20$
   * D. $PSI = 0$
   * *Jawaban*: **C**. Standar industri finansial menetapkan nilai $PSI \ge 0.20$ mengindikasikan pergeseran distribusi populasi yang signifikan secara statistik.

#### Intermediate (5 Pertanyaan)
6. Dalam arsitektur feature store, mengapa pola *dual-write* sinkron (menulis ke Online Redis dan Offline Data Lakehouse secara bersamaan dari aplikasi klien) sangat dihindari?
   * A. Redis tidak kompatibel dengan Apache Iceberg.
   * B. Menyebabkan bottleneck latensi transaksi aplikasi dan risiko inkonsistensi data jika salah satu sistem penyimpanan mengalami transient network failure.
   * C. Format data Redis berbasis teks sementara data lakehouse berbasis string.
   * D. Akan menghabiskan bandwidth jaringan local loopback secara eksponensial.
   * *Jawaban*: **B**. Dual-write sinkron membebani klien dan rentan kegagalan parsial (*split-brain / partial writes*). Solusi yang tepat adalah menggunakan write-ahead stream log (Kafka/CDC) untuk mendistribusikan data asinkron.

7. Mengapa pengujian *lazy validation* pada Data Contract framework (seperti Pandera) lebih diunggulkan untuk pipeline batch ML daripada *eager validation*?
   * A. Lazy validation mengeksekusi komputasi di GPU.
   * B. Lazy validation mengumpulkan SELURUH daftar pelanggaran skema dalam satu lintasan data penuh sebelum melempar exception, mempermudah troubleshooting menyeluruh.
   * C. Eager validation membutuhkan memori 2x lebih besar.
   * D. Lazy validation tidak memvalidasi tipe data string.
   * *Jawaban*: **B**. Eager validation melempar exception pada kegagalan baris pertama, memaksa engineer memperbaiki error satu per satu. Lazy validation memberikan diagnosa komprehensif seluruh dataset sekaligus.

8. Dalam kondisi traffic request inferensi yang berfluktuasi tinggi, arsitektur mana yang paling tangguh untuk mencegah kegagalan *cascade failure* pada backend model engine?
   * A. Skalabilitas auto-scaler pods (HPA) tanpa batas.
   * B. Envoy gateway dengan konfigurasi *circuit breaking*, alokasi antrean finite dengan HTTP 429 backpressure, dan fallback response rule-based.
   * C. Mematikan fitur logging pada Triton Inference Server.
   * D. Mengalihkan seluruh traffic inferensi ke memory CPU swap.
   * *Jawaban*: **B**. Circuit breaker dan rate limiting melindungi engine dari kehancuran mendadak (*thundering herd*), sementara fallback menjamin sistem tetap fungsional di mata user.

9. Apa perbedaan esensial antara **Data Drift (Covariate Shift)** dan **Concept Drift**?
   * A. Data drift terjadi pada data teks, concept drift terjadi pada data gambar.
   * B. Data drift adalah perubahan distribusi input $P(X)$, sedangkan concept drift adalah perubahan hubungan fungsional antara input dan target $P(Y \mid X)$.
   * C. Concept drift selalu dapat diselesaikan dengan scaling infrastructure, data drift tidak.
   * D. Data drift hanya dapat diidentifikasi bila ground truth label $Y$ tersedia seketika.
   * *Jawaban*: **B**. Data drift: distribusi fitur $X$ bergeser, tetapi pemetaan ke $Y$ tetap sama. Concept drift: pola perilaku dasar berubah, sehingga input $X$ yang sama menghasilkan target $Y$ yang berbeda dari historisnya.

10. Bagaimana pemanfaatan *CUDA Pinned Memory* (Page-Locked Host Memory) mempercepat transfer payload tensor pada deep learning model inference?
    * A. Pinned memory mengubah floating point 32-bit menjadi 8-bit otomatis.
    * B. Memungkinkan DMA (Direct Memory Access) controller mentransfer array langsung dari memori sistem host ke memori GPU (VRAM) tanpa melibatkan intervensi OS paging CPU.
    * C. Mengompresi array secara lossless sebelum masuk bus PCIe.
    * D. Menghilangkan kebutuhan alokasi CUDA stream context.
    * *Jawaban*: **B**. Pinned memory mencegah sistem operasi melakukan page-swapping ke disk, memungkinkan DMA hardware controller mengopi blok memori langsung ke GPU via PCIe bus dengan kecepatan saturasi bandwidth maksimal.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus 1**:
    Tim Fraud Detection meluncurkan model baru berbasis Deep Learning untuk evaluasi otorisasi kartu kredit real-time. Pada lingkungan staging (uji beban 1.000 QPS), latensi rata-rata tercatat sangat baik ($3\text{ms}$). Namun, saat diuji di stage canary production dengan beban riil yang memiliki pola *burst* tajam (lonjakan mendadak dari 100 QPS ke 15.000 QPS dalam 2 detik), latensi P99 melompat hingga $450\text{ms}$ dan sebagian koneksi timeout.
    *Diagnosa arsitektur apa yang paling rasional, dan bagaimana solusinya?*
    * *Analisis & Solusi*: 
      Penyebab utama adalah *cold-start/thread starvation* dan konfigurasi ukuran dynamic batching buffer yang tidak adaptif. Pada model GPU, burst traffic menyebabkan memori bus PCIe tersumbat karena sinkronisasi buffer berulang kali dengan alokasi heap dinamis (*re-allocation bottleneck*). 
      Solusi:
      1. Pre-allocate Tensor Buffer dan Context pools di memori GPU saat initialization.
      2. Terapkan batas antrean hardware (*queue saturation cap*) di Triton.
      3. Atur *rate-smoothing token bucket* pada layer gateway (misal Envoy) untuk memotong amplitudo lonjakan transien ke inference worker pods.

12. **Skenario Kasus 2**:
    Sebuah model churn prediction di sebuah platform streaming dievaluasi setiap malam. Selama 3 bulan terakhir, metrik AUC-ROC di test set historis selalu stabil di angka 0.89. Namun, metrik bisnis menunjukkan persentase pengguna churn riil terus melonjak naik tanpa mampu diprediksi akurat oleh model. Analisis data menemukan bahwa distribusi data input $X$ (metrik aktivitas streaming harian) sama sekali tidak berubah ($PSI = 0.02$).
    *Fenomena apa yang sedang terjadi dan bagaimana rencana mitigasi arsitekturnya?*
    * *Analisis & Solusi*:
      Ini adalah manifestasi murni dari **Concept Drift** tanpa Data Drift. Distribusi masukan $P(X)$ stabil (aktivitas streaming tetap), tetapi relasi kondisional $P(Y \mid X)$ telah berubah (misal: terjadi kenaikan harga langganan atau penurunan daya beli ekonomi makro yang membuat pengguna berhenti langganan meskipun aktivitas menonton mereka tetap tinggi).
      Solusi:
      1. Evaluasi ulang *Label Attribution Pipeline*; ukur metrik performa model pada *sliding window* ground-truth aktual, bukan pada test set statis 3 bulan lalu.
      2. Rekayasa fitur baru yang menangkap faktor eksternal (misal: rasio harga terhadap rata-rata pengeluaran pengguna).
      3. Otomatisasi pipeline retraining berbasis deteksi degradasi metrik bisnis/kinerja prediktif terkonfirmasi, bukan hanya berbasis metrik variasi input fitur.

13. **Skenario Kasus 3**:
    Perusahaan e-commerce multinasional menggunakan Redis Cluster untuk online feature store. Karena penambahan 50 fitur baru hasil kolaborasi tim riset, memori Redis melonjak mencapai 92% kapasitas RAM, memicu eviction key (`allkeys-lru`) secara liar. Akibatnya, inference server mengalami *cache miss* masif dan latensi pembacaan fitur melesat dari $2\text{ms}$ ke $85\text{ms}$ karena harus query ke fallback database disk.
    *Langkah rekayasa arsitektural apa yang wajib diambil tanpa sekadar menambah biaya RAM hardware 2x lipat?*
    * *Analisis & Solusi*:
      1. **Feature Pruning & Importance Audit**: Hitung kontribusi feature attribution (misal via SHAP values) dari 50 fitur baru tersebut. Eliminasi fitur yang memiliki kontribusi mendekati nol.
      2. **Serialization Compression**: Ganti serialisasi teks mentah (JSON string) di Redis dengan format biner kompak seperti MessagePack, Protocol Buffers, atau FlatBuffers. Ini memangkas konsumsi RAM sebesar 40-60%.
      3. **Hierarchical Caching Architecture**: Pindahkan fitur non-volatil (jarang berubah) ke local in-memory cache (Shared Memory / LRU process memory) pada masing-masing pod inference client dengan short-lived TTL (1-5 menit), sehingga meringankan volume load dan beban footprint storage pada Redis Cluster.

---

### 16. Summary

1. Arsitektur Machine Learning enterprise menitikberatkan keandalan komponen rekayasa sistem data di sekitar model, bukan sekadar optimalisasi parameter model internal.
2. **Data Contracts** berperan sebagai gerbang pertahanan pertama sistem terdistribusi, memblokir silent data failure melalui validasi skema dan invariansi data yang deklaratif dan tegas.
3. Sinkronisasi **Feature Store Dual-Engine (Online & Offline)** menyelesaikan paradoks skalabilitas versus latensi: menjamin latensi baca sub-milidetik untuk inference real-time sekaligus menjaga kepatuhan *temporal consistency* (bebas data leakage) menggunakan AS-OF join saat pembentukan dataset training.
4. **Dynamic Batching** pada dedicated inference engines (Triton/TorchServe) menjadi komponen kunci yang memaksimalkan saturasi throughput komputasi GPU tanpa mengorbankan SLA latensi edge proxy.
5. Observabilitas produksi harus mencakup dua horizon: metrik infrastruktur teknis (QPS, GPU utilization, Tail Latency) dan metrik statistik distribusi probabilistik (*Population Stability Index*, *Wasserstein Distance*) guna mengantisipasi ancaman silent failure dari data drift dan concept drift secara berkelanjutan.