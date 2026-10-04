# Bab 03: Feature Store Architecture & Real-Time Ingestion
## Modul 01: Dual-Storage Engine, Point-in-Time Correctness, dan Streaming Ingestion

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Merancang** arsitektur *dual-storage feature store* (kombinasi *low-latency key-value store* untuk *online inference* dan *columnar/immutable store* untuk *offline training*).
- **Mengimplementasikan** mekanisme *point-in-time correctness* (*AS-OF join*) secara deterministik untuk mengeliminasi *data leakage* pada data historis pelatihan model.
- **Membangun** pipeline *streaming ingestion* berlatensi sub-detik menggunakan event stream engine untuk memproses, memvalidasi skema, dan memperbarui *online feature store*.
- **Mendeteksi dan Memitigasi** *training-serving skew* struktural akibat inkonsistensi transformasi fitur antara lingkungan komputasi analitik (batch) dan produksi (real-time).
- **Mengevaluasi** trade-off arsitektural terkait strategi sinkronisasi data (*dual-write*, *CDC/Change Data Capture*, dan *log-compacted streaming*).

---

### 2. Concept Overview

*Feature Store* adalah subsistem terpusat dalam arsitektur MLOps yang bertanggung jawab untuk mendaftarkan, menghitung, menyimpan, dan menyajikan fitur machine learning secara konsisten di dua lingkungan komputasi yang berbeda secara fundamental:

```
+-------------------------------------------------------------------------+
|                              FEATURE STORE                              |
|                                                                         |
|  +--------------------+   Declarative Spec   +-----------------------+  |
|  |   Feature Repo     | -------------------> | Central Registry      |  |
|  |  (Code as Config)  |                      | (Metadata, Lineage)   |  |
|  +--------------------+                      +-----------------------+  |
|            |                                             |              |
|            v                                             v              |
|  +-------------------------------------------------------------------+  |
|  |                      Ingestion & Compute Engine                   |  |
|  +-------------------------------------------------------------------+  |
|             |                                             |             |
|             v                                             v             |
|  +--------------------+                      +-----------------------+  |
|  |    Online Store    |                      |     Offline Store     |  |
|  | (Redis/Cassandra)  |                      | (Parquet/Delta/DuckDB)|  |
|  | Low Latency (O(1)) |                      | Scalable OLAP (SQL)   |  |
|  | Single-key Read    |                      | Time-travel Joins     |  |
|  +--------------------+                      +-----------------------+  |
+-------------|--------------------------------------------|---------------+
              |                                            |
              v                                            v
     [Online Inference]                           [Model Training]
   predict(features @ t_now)                 train(features @ t_event)
```

#### Komponen Kunci Feature Store
1. **Feature Registry**: Pusat metadata deklaratif yang mendefinisikan skema fitur, tipe data, *entity keys*, statistik, *data owner*, dan dependensi transformasi (*lineage*).
2. **Dual-Storage Engine**:
   - **Online Store**: Basis data terdistribusi terindeks berbasis memori (misalnya Redis, DragonflyDB, Cassandra) yang dioptimalkan untuk kueri pembacaan berlatensi milidetik ($< 10\text{ ms}$) per entitas (*single-entity lookup*).
   - **Offline Store**: Penyimpanan data analitik berbasis kolom (misalnya Delta Lake, Apache Iceberg, Snowflake, DuckDB) yang dioptimalkan untuk throughput pemindaian data historis terpartisi yang masif.
3. **Point-in-Time Correctness Engine**: Algoritma kalkulasi temporal (*time-travel/AS-OF join*) yang memastikan bahwa fitur yang digabungkan ke label observasi pada waktu $t_E$ hanya mencerminkan status data pada $t \le t_E$, mencegah fenomena *lookahead bias*.

---

### 3. Why It Matters

Dalam implementasi model berbasis data dinamis (seperti sistem deteksi *fraud*, sistem rekomendasi e-commerce, atau penetapan harga dinamis), infrastruktur tanpa *feature store* memicu sejumlah kegagalan kritis:

- **Training-Serving Skew**: Terjadi ketika pipeline transformasi fitur pra-pemrosesan data batch di Spark/Pandas memiliki perbedaan logika deterministik mikro dibandingkan pipeline serialisasi C++/Go/Python di layer API inferensi. Model menerima distribusi fitur yang terdistorsi saat produksi.
- **Data Leakage (Lookahead Bias)**: Jika nilai agregasi fitur (misalnya, total transaksi kartu kredit dalam 24 jam terakhir) dihitung menggunakan data agregat global alih-alih data pada *timestamp* kejadian transaksi, model dilatih menggunakan informasi masa depan. Metrik evaluasi offline terlihat optimal ($AUC > 0.98$), tetapi akurasi runtuh saat inferensi real-time.
- **Duplikasi Komputasi & Pemborosan Resource**: Tanpa repositori fitur bersama, data engineering dan data science teams mengulang kalkulasi fitur yang sama secara independen di berbagai silo pipeline, melipatgandakan biaya komputasi cloud dan risiko inkonsistensi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan aliran data *end-to-end* dari sumber data hingga inferensi dan pelatihan:

```
[Streaming Sources]          [Batch Sources]
 (Kafka / Kinesis)        (S3 / Data Warehouse)
        |                           |
        |                           |
        v                           v
+------------------+       +------------------+
| Streaming Engine |       |   Batch Engine   |
| (Flink / Faust)  |       | (Spark / DuckDB) |
+------------------+       +------------------+
        |        \               /      |
 (Direct Write)   \             /       |
        |          v           v        |
        |       +-----------------+     |
        |       |  Batch Staging  |     |
        |       +-----------------+     |
        |                |              |
        v                v              v
+---------------+             +-----------------------+
| Online Store  |             |     Offline Store     |
| (Redis Store) |             |  (Parquet Data Lake)  |
|               |             |                       |
| Key: entity   |             | Entity | Timestamp |  |
| Val: {feat_N} |             | feat_1 | feat_2 ...|  |
+---------------+             +-----------------------+
        ^                                 ^
        | (Low Latency Read)              | (AS-OF Time-Travel Join)
        |                                 |
+-------------------+         +-----------------------+
|  Model Serving    |         |   Training Pipeline   |
| (Online Predict)  |         |   (Model Fit Loop)    |
+-------------------+         +-----------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Mekanisme Point-in-Time Correctness (AS-OF Join)
Secara matematis, misalkan terdapat himpunan kejadian observasi (label) $O$ dengan relasi tupel:
$$O = \{(e_i, t_i, y_i)\}$$
di mana $e_i$ adalah *entity key*, $t_i$ adalah *timestamp* kejadian, dan $y_i$ adalah *ground truth*.

Misalkan pula terdapat runtutan waktu rekaman fitur $F$ untuk entitas $e$:
$$F = \{(e_j, t_j, \mathbf{x}_j)\}$$

Tugas *AS-OF Join* adalah memetakan setiap observasi $(e_i, t_i)$ ke nilai fitur terbaru $\mathbf{x}_j$ yang terjadi sebelum atau tepat pada waktu observasi, dengan syarat:
$$\mathbf{x}_{\text{valid}} = \operatorname{arg\,max}_{t_j \le t_i} (F(e_j, t_j)) \quad \text{dengan} \quad e_j = e_i$$

Jika $t_j > t_i$, nilai tersebut diabaikan karena merupakan *future information* (potensi *leakage*).

```
Timeline: -------------------------------------------------------->
Feature Updates:    [F_v1 @ 10:00]      [F_v2 @ 10:30]    [F_v3 @ 11:15]
Event Occurrence:                   * (Event A @ 10:15)
                                                      * (Event B @ 11:20)

AS-OF Join Mapping:
Event A (10:15) -> Mengambil F_v1 (10:00)  [Bukan F_v2!]
Event B (11:20) -> Mengambil F_v3 (11:15)
```

#### B. Streaming Sliding Windows & Sinkronisasi State
Untuk fitur agregasi real-time (misalnya, `user_click_count_10m`), streaming engine menggunakan *tumbling* atau *sliding window* dengan *watermarking* untuk menangani data yang terlambat (*out-of-order events*). Nilai agregasi ini langsung dipublikasikan ke *Online Store* untuk mempertahankan status terkini entitas, sekaligus diekspor secara periodik ke format batch (Parquet) untuk *Offline Store*.

#### C. Dual-Write Problem & CDC Mitigation
Melakukan penulisan paralel (*dual-write*) dari ingestion worker secara langsung ke Redis dan Data Lake berisiko memunculkan inkonsistensi status jaringan jika salah satu node gagal. Pola modern menggunakan pendekatan **Write-Ahead Log (WAL)** via Event Stream (Apache Kafka). Konsumsi data dilakukan secara independen oleh dua sink consumer: satu berfokus pada persistensi berkecepatan tinggi ke Redis, dan satu lagi melakukan *micro-batch writing* ke Data Lake (S3/Delta Lake).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi end-to-end sistem Feature Store mini berbasis Python:
1. **Core Domain Registry**: Menggunakan `pydantic` untuk validasi skema fitur secara deklaratif.
2. **Offline Store & AS-OF Engine**: Menggunakan kueri SQL temporal analitik berbasis `DuckDB`.
3. **Streaming Ingestion & Online Store**: Menggunakan abstraction layer memory/Redis yang mendukung thread-safe write/read berlatensi rendah.

```python
#!/usr/bin/env python3
"""
Production-grade Architectural Blueprint for a Dual-Store Feature Engine.
Implements declarative schema validation, high-throughput online serving,
and point-in-time correct (AS-OF) joins.
"""

from __future__ import annotations

import datetime
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import duckdb
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FeatureStoreEngine")


# --------------------------------------------------------------------------
# 1. METADATA REGISTRY & SCHEMA DEFINITION
# --------------------------------------------------------------------------

class FeatureDefinition(BaseModel):
    name: str
    dtype: str
    description: str


class FeatureView(BaseModel):
    name: str
    entity_key: str
    features: List[FeatureDefinition]
    ttl_seconds: int = Field(default=86400 * 30, description="Waktu retensi fitur")


class IngestionEvent(BaseModel):
    entity_id: str
    timestamp: datetime.datetime
    payload: Dict[str, Any]


# --------------------------------------------------------------------------
# 2. STORAGE INTERFACES
# --------------------------------------------------------------------------

class OnlineFeatureStore(ABC):
    @abstractmethod
    def write_feature(self, view_name: str, entity_id: str, features: Dict[str, Any], timestamp: datetime.datetime) -> None:
        pass

    @abstractmethod
    def read_feature(self, view_name: str, entity_id: str) -> Optional[Dict[str, Any]]:
        pass


class OfflineFeatureStore(ABC):
    @abstractmethod
    def write_batch(self, view_name: str, df: pd.DataFrame) -> None:
        pass

    @abstractmethod
    def get_historical_features(
        self,
        observation_df: pd.DataFrame,
        entity_key: str,
        feature_view_name: str,
        feature_columns: List[str],
    ) -> pd.DataFrame:
        pass


# --------------------------------------------------------------------------
# 3. CONCRETE ENGINES IMPLEMENTATION
# --------------------------------------------------------------------------

class InMemoryRedisOnlineStore(OnlineFeatureStore):
    """
    Simulasi in-memory high-throughput key-value cache dengan format Redis HSET.
    Kunci Redis: {view_name}:{entity_id}
    Nilai Redis: {feature_key: feature_val, "__ts__": iso_timestamp}
    """
    def __init__(self) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, view_name: str, entity_id: str) -> str:
        return f"{view_name}:{entity_id}"

    def write_feature(self, view_name: str, entity_id: str, features: Dict[str, Any], timestamp: datetime.datetime) -> None:
        store_key = self._generate_key(view_name, entity_id)
        record = features.copy()
        record["__ts__"] = timestamp.isoformat()
        self._cache[store_key] = record

    def read_feature(self, view_name: str, entity_id: str) -> Optional[Dict[str, Any]]:
        store_key = self._generate_key(view_name, entity_id)
        record = self._cache.get(store_key)
        if not record:
            return None
        # Return fitur tanpa field metadata privat
        return {k: v for k, v in record.items() if not k.startswith("__")}


class DuckDBOfflineStore(OfflineFeatureStore):
    """
    Offline feature store berbasis OLAP DuckDB.
    Mendukung point-in-time (AS-OF) joins menggunakan SQL temporal standar.
    """
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = duckdb.connect(db_path)
        self._registered_views: set[str] = set()

    def write_batch(self, view_name: str, df: pd.DataFrame) -> None:
        table_name = f"fv_{view_name}"
        if table_name not in self._registered_views:
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM df WHERE 1=0;")
            self._registered_views.add(table_name)
        
        self.conn.register("temp_staging_df", df)
        self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_staging_df;")
        self.conn.unregister("temp_staging_df")
        logger.info(f"Berhasil menulis {len(df)} baris ke offline store [{table_name}].")

    def get_historical_features(
        self,
        observation_df: pd.DataFrame,
        entity_key: str,
        feature_view_name: str,
        feature_columns: List[str],
    ) -> pd.DataFrame:
        """
        Melakukan Point-In-Time (AS-OF) join deterministik:
        Menggabungkan observasi target ke record fitur terbaru pada atau sebelum observation_df.event_timestamp
        """
        table_name = f"fv_{feature_view_name}"
        feature_cols_str = ", ".join([f"f.{col}" for col in feature_columns])
        
        self.conn.register("observations", observation_df)
        
        query = f"""
        SELECT 
            obs.*,
            {feature_cols_str}
        FROM observations obs
        ASOF JOIN {table_name} f
            ON obs.{entity_key} = f.{entity_key}
            AND obs.event_timestamp >= f.feature_timestamp
        ORDER BY obs.event_timestamp ASC;
        """
        
        result_df = self.conn.execute(query).fetchdf()
        self.conn.unregister("observations")
        return result_df


# --------------------------------------------------------------------------
# 4. STREAMING INGESTION PIPELINE PIPELINE (ORCHESTRATOR)
# --------------------------------------------------------------------------

class FeaturePipelineCoordinator:
    """
    Mengorkestrasikan streaming ingestion, validasi payload,
    penulisan ke online cache, dan penulisan micro-batch ke offline storage.
    """
    def __init__(
        self,
        feature_view: FeatureView,
        online_store: OnlineFeatureStore,
        offline_store: OfflineFeatureStore,
    ) -> None:
        self.feature_view = feature_view
        self.online_store = online_store
        self.offline_store = offline_store
        self._schema_validator = {f.name: f.dtype for f in feature_view.features}

    def _validate_payload(self, payload: Dict[str, Any]) -> None:
        for feat_name in self._schema_validator:
            if feat_name not in payload:
                raise ValidationError(f"Payload tidak memiliki fitur wajib: {feat_name}")

    def ingest_event(self, event: IngestionEvent) -> None:
        # 1. Validasi Skema
        self._validate_payload(event.payload)

        # 2. Real-Time Write ke Online Store (SLA < 10ms)
        self.online_store.write_feature(
            view_name=self.feature_view.name,
            entity_id=event.entity_id,
            features=event.payload,
            timestamp=event.timestamp,
        )

        # 3. Menulis ke Offline Store (Staging/Micro-batch Append)
        # Pada sistem nyata, data dialirkan melalui Kafka Sink -> Parquet batch
        offline_record = {
            self.feature_view.entity_key: event.entity_id,
            "feature_timestamp": event.timestamp,
            **event.payload,
        }
        batch_df = pd.DataFrame([offline_record])
        self.offline_store.write_batch(self.feature_view.name, batch_df)


# --------------------------------------------------------------------------
# 5. DEMONSTRATION & VERIFICATION RUNNER
# --------------------------------------------------------------------------

def run_demonstration() -> None:
    # A. Definisikan Feature View
    user_risk_view = FeatureView(
        name="user_credit_risk",
        entity_key="user_id",
        features=[
            FeatureDefinition(name="failed_logins_last_hour", dtype="int64", description="Jumlah percobaan login gagal"),
            FeatureDefinition(name="avg_transaction_amount_7d", dtype="float64", description="Rata-rata transaksi 7 hari"),
        ],
    )

    # B. Inisialisasi Storage Engine
    online_db = InMemoryRedisOnlineStore()
    offline_db = DuckDBOfflineStore()
    coordinator = FeaturePipelineCoordinator(user_risk_view, online_db, offline_db)

    # C. Simulasi Masuknya Data Aliran Temporal (Streaming Feature Updates)
    t0 = datetime.datetime(2026, 3, 30, 8, 0, 0)
    t1 = datetime.datetime(2026, 3, 30, 8, 30, 0)
    t2 = datetime.datetime(2026, 3, 30, 9, 0, 0)

    logger.info("Memulai simulasi streaming ingestion...")
    
    # Event 1: User 101 pada t0
    coordinator.ingest_event(
        IngestionEvent(
            entity_id="usr_101",
            timestamp=t0,
            payload={"failed_logins_last_hour": 0, "avg_transaction_amount_7d": 150000.0},
        )
    )

    # Event 2: User 101 mengalami update aktivitas pada t2
    coordinator.ingest_event(
        IngestionEvent(
            entity_id="usr_101",
            timestamp=t2,
            payload={"failed_logins_last_hour": 4, "avg_transaction_amount_7d": 450000.0},
        )
    )

    # D. Verifikasi Inferensi Online (Harus mengambil data paling baru / t2)
    online_features = online_db.read_feature("user_credit_risk", "usr_101")
    logger.info(f"[Online Inference] State Fitur Terkini usr_101: {online_features}")
    assert online_features is not None
    assert online_features["failed_logins_last_hour"] == 4

    # E. Verifikasi Point-in-Time Correctness (Offline Training Dataset Generator)
    # Skenario: Kita memiliki data observasi label transaksi yang terjadi pada waktu t1 (8:30)
    # Nilai yang harus diambil oleh AS-OF join adalah state t0 (8:00), BUKAN state t2 (9:00).
    # Jika sistem mengambil state t2, berarti telah terjadi DATA LEAKAGE!
    logger.info("Menguji Point-in-Time Join untuk Training Dataset...")

    observation_data = pd.DataFrame([
        {
            "user_id": "usr_101",
            "event_timestamp": t1,  # 08:30:00
            "fraud_label": 0,
        },
        {
            "user_id": "usr_101",
            "event_timestamp": datetime.datetime(2026, 3, 30, 9, 30, 0),  # Pasca t2
            "fraud_label": 1,
        }
    ])

    training_df = offline_db.get_historical_features(
        observation_df=observation_data,
        entity_key="user_id",
        feature_view_name="user_credit_risk",
        feature_columns=["failed_logins_last_hour", "avg_transaction_amount_7d"],
    )

    print("\n--- HASIL POINT-IN-TIME (AS-OF) HISTORICAL FEATURES ---")
    print(training_df.to_string(index=False))

    # Validasi Hasil
    # Row 0: Timestamp 08:30:00 -> Harus mengambil record 08:00:00 (failed_logins = 0)
    # Row 1: Timestamp 09:30:00 -> Harus mengambil record 09:00:00 (failed_logins = 4)
    row_t1 = training_df[training_df["event_timestamp"] == t1].iloc[0]
    assert row_t1["failed_logins_last_hour"] == 0, "DATA LEAKAGE DETECTED! Fitur masa depan terpapar ke masa lalu!"
    logger.info("Validasi Integritas Temporal Sukses: Tidak ditemukan Data Leakage.")


if __name__ == "__main__":
    run_demonstration()
```

---

### 7. Edge Cases & Failure Modes

1. **Late-Arriving Events (Data Out-of-Order)**:
   - *Kasus*: Event transaksi terjadi pada `10:00`, tetapi tertahan di antrean jaringan edge dan baru masuk ke ingestion pipeline pada `10:15` (setelah event `10:10` diproses).
   - *Mitigasi*: Online store menolak penulisan *in-place* mutlak berdasarkan waktu penerimaan pesan. Gunakan komparator versi internal (*conditional write*) berbasis `event_timestamp`. Tolak pembaruan online store jika `event_timestamp <= current_redis_timestamp`.

2. **Redis Memory Saturation (OOM Kill Events)**:
   - *Kasus*: Jutaan entitas aktif mengisi RAM Redis tanpa mekanisme pembersihan, menyebabkan Redis melakukan eviction acak (menghentikan fitur inferensi) atau mengalami *crash*.
   - *Mitigasi*: Konfigurasikan kebijakan `volatile-lru` dan tetapkan batas TTL struktural eksplisit pada setiap entitas sesuai dengan jendela siklus inferensi yang relevan.

3. **Schema Drift Pada Data Ingestion**:
   - *Kasus*: Sistem upstream mengubah tipe field `transaction_amount` dari `float` menjadi `string` yang mengandung simbol mata uang.
   - *Mitigasi*: Implementasikan *Dead-Letter Queues (DLQ)*. Setiap payload yang gagal diverifikasi oleh skema Pydantic dialihkan ke antrean inspeksi untuk mencegah rusaknya data state tanpa menyebabkan *blocking* pada streaming ingestion worker utama.

4. **Kekosongan Data Entitas Baru (Cold-Start Problem)**:
   - *Kasus*: Request online inference dikirimkan untuk entitas baru yang belum memiliki riwayat pada sistem streaming.
   - *Mitigasi*: Definisikan *default imputed values* pada level *Feature Definition* yang di-cache di level gateway/client application untuk meminimalkan beban komputasi fallback.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Pilihan A: In-House Engine (Redis + DuckDB/Iceberg) | Pilihan B: Managed Platform (Feast / Hopsworks) | Pilihan C: Traditional Batch ETL Direct DB Read |
| :--- | :--- | :--- | :--- |
| **Latensi Inferensi** | Terendah ($<5\text{ ms}$) via direct memory access | Rendah ($5-15\text{ ms}$) bergantung pada overhead network layer Feast | Tinggi ($>100\text{ ms}$) akibat load SQL query |
| **Kompleksitas Operasional** | Tinggi: Harus memelihara pipeline dual-write, cluster DuckDB/Parquet | Sedang-Tinggi: Butuh adopsi ekosistem dan platform Feast | Rendah: Cukup menjalankan cron script berkala |
| **Pencegahan Leakage** | Terkontrol penuh via SQL AS-OF Join deterministik | Terjamin melalui fitur native *historical_features* | Sangat Rentan terhadap *lookahead bias* |
| **Biaya Infrastruktur** | Sangat Hemat (Self-hosted storage berorientasi objek) | Sedang hingga Mahal (Lisensi / resource platform terkelola) | Mahal pada komputasi OLTP database |

---

### 9. Best Practices & Standard Industri

- **Karakter Imutabilitas (Write-Once, Read-Many)**: Jangan pernah memperbarui data offline store menggunakan `UPDATE` statement. Format offline harus selalu bertindak sebagai append-only ledger yang merekam perubahan dari waktu ke waktu (*temporal changelog*).
- **Standarisasi Penamaan Entitas & Fitur**: Gunakan konvensi namespace hierarkis:
  $$\text{<domain>}\_ \text{<entity>}\_ \text{<feature\_name>}\_ \text{<aggregation\_window>}$$
  *Contoh*: `payment_user_failed_attempts_1h`, `catalog_item_click_through_rate_7d`.
- **Feature Freshness Monitoring**: Terapkan *heartbeat alert* yang mengukur selisih waktu:
  $$\Delta t = t_{\text{inference}} - t_{\text{feature\_updated}}$$
  Beri peringatan (*alert*) jika $\Delta t$ melampaui batas SLA kesegaran data (misal: $\Delta t > 2 \times \text{window interval}$).
- **Single Source of Truth**: Seluruh definisi kode dan transformasi skema harus disimpan dalam repositori Git (*Feature-as-Code*). Jangan pernah memanipulasi skema registri secara manual di console produksi.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan membangun pipeline fitur deteksi anomali transfer bank secara real-time. Anda harus memverifikasi bahwa:
1. Online store dapat menerima data aliran transfer secara cepat dan menyajikan agregasi fitur per akun bank.
2. Dataset pelatihan model terbebas dari *leakage* menggunakan *AS-OF join*.

#### Langkah 1: Persiapan Environment
Pasang pustaka dependensi yang dibutuhkan:
```bash
pip install duckdb pandas pydantic
```

#### Langkah 2: Eksekusi File Script
Simpan kode dari **Bagian 6** di atas ke dalam file bernama `feature_store_lab.py` dan jalankan script:
```bash
python feature_store_lab.py
```

#### Langkah 3: Uji Pemahaman Mandiri (Challenge)
Modifikasi fungsi `run_demonstration` di dalam file `feature_store_lab.py`:
1. Tambahkan fitur baru: `device_risk_score` bertipe data `float64`.
2. Masukkan event ketiga untuk user `usr_101` pada waktu `08:45:00` dengan nilai `failed_logins_last_hour = 2`.
3. Jalankan kembali script dan pastikan kueri observasi pada `08:30:00` tetap mempertahankan nilai `0`, sedangkan observasi pada `09:30:00` mengambil nilai terbaru `4`.
4. Tambahkan assertion untuk memvalidasi bahwa nilai fitur pada waktu `08:50:00` mengambil nilai `2` (hasil update antara).