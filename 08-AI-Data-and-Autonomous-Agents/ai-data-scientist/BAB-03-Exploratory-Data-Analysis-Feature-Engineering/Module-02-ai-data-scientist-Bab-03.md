# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 03: Exploratory Data Analysis & Feature Engineering**  
**Jalur Pembelajaran: AI Data Scientist (Kategori: 08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Merancang & Mengimplementasikan Arsitektur Feature Store Dual-Layer (Offline & Online)** untuk mengeliminasi *training-serving skew* pada throughput tinggi ($>10.000\text{ RPS}$).
*   **Membangun Custom Pipeline Transformer Bertaraf Produksi** menggunakan `scikit-learn`, `Polars`, dan basis objek OOP yang menerapkan pemisahan *fit-state* ketat demi mencegah *data leakage*.
*   **Menerapkan Transformasi Fitur Tingkat Lanjut Matematis**: Out-of-Fold (OOF) Target Encoding dengan regularisasi Bayesian, transformasi siklikal spasio-temporal, dan interaksi polinomial skala besar.
*   **Mengaudit & Mengatasi Fenomena Data Leakage Temporal**: Mengimplementasikan *time-travel joins* dan windowing berbasis titik waktu (*point-in-time correctness*).
*   **Mengukur dan Mengoptimalkan Rasio Latensi-Throughput Fitur** untuk inferensi real-time skala enterprise ($<15\text{ ms } p99$).

---

## 2. Prerequisites
Untuk menyerap materi secara optimal, peserta wajib menguasai:
*   **Sintaksis Python Tingkat Lanjut**: Decorator, Metaclass, Abstract Base Classes (`abc`), serta Type Hinting (`typing`).
*   **Matematika & Statistik Terapan**: Teorema Bayes, Aljabar Linear dasar (dekomposisi matriks), Trigonometri (sin/cos encoding), dan Kalkulus Multivariat.
*   **Data Manipulation Engine**: Pengalaman dasar dengan `pandas`, `Polars`, atau `PySpark`.
*   **Arsitektur Sistem Terdistribusi**: Pemahaman tentang basis data in-memory (Redis), data lakehouse (Parquet/Delta Lake), dan streaming platform (Apache Kafka).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Paradigma Stateful vs. Stateless Feature Transformations
Transformasi fitur terbagi menjadi dua kategori fundamental:
1.  **Stateless Transformations**: Operasi matematika di mana nilai keluaran baris ke-$i$ murni bergantung pada nilai input baris ke-$i$. Contoh: $\log(x)$, $\sin(2\pi \cdot t/T)$, ekstraksi komponen tanggal. Operasi ini dapat diskalakan secara horizontal tanpa sinkronisasi state.
2.  **Stateful Transformations**: Operasi di mana transformasi bergantung pada parameter global populasi data latih ($\mathcal{D}_{train}$). Contoh: Standard Scaling ($\mu, \sigma$), Out-of-Fold Target Encoding ($\bar{y}_{target}, \lambda$), Quantile Discretization, dan Imputasi Median.

$$\text{Stateful Transformation: } z_i = \frac{x_i - \mu_{\mathcal{D}_{train}}}{\sigma_{\mathcal{D}_{train}}}$$

Kegagalan enterprise paling kritis terjadi ketika parameter stateful dihitung ulang (*re-fit*) pada data inferensi (*serving*), atau ketika data validasi/pengujian ikut terhitung saat menghitung $\mu$ dan $\sigma$ (fenomena *data snooping / data leakage*).

### 3.2 Out-of-Fold (OOF) Target Encoding dengan Bayesian Smoothing
Target encoding konvensional mengganti kategori $k$ dengan mean target $\bar{y}_k$. Pada kardinalitas tinggi, ini menyebabkan *overfitting* parah jika kategori tersebut memiliki frekuensi kemunculan rendah ($n_k \ll 100$). Untuk mencegahnya, arsitektur enterprise menggunakan **Bayesian Target Encoding** yang digabungkan dengan validasi silang **Out-of-Fold (K-Fold)**:

$$S_k = \lambda(n_k) \bar{y}_k + (1 - \lambda(n_k)) \bar{y}_{global}$$

Di mana faktor pembobot $\lambda(n_k)$ diformulasikan menggunakan fungsi logistik atau rasio varians:

$$\lambda(n_k) = \frac{1}{1 + e^{-(n_k - m) / s}}$$

*   $n_k$: Jumlah sampel kategori $k$ dalam data latih fold eksternal.
*   $\bar{y}_k$: Rata-rata target kategori $k$ pada fold eksternal.
*   $\bar{y}_{global}$: Prior global mean target.
*   $m$: Ambang batas parameter smoothing (*weight of evidence* minimum).
*   $s$: Faktor kelancaran kurva smoothing (*smoothing scale*).

### 3.3 Point-in-Time Correctness & Feature Store Architecture
Dalam domain waktu nyata (misal: sistem deteksi fraud perbankan), status fitur agregasi pelanggan (misal: `count_trx_last_24h`) harus mencerminkan kondisi **tepat pada stempel waktu transaksi terjadi ($t_0$)**, bukan waktu pipeline dieksekusi ($t_1$). Inkonsistensi ini dikenal sebagai **Time-Travel Leakage**.

```
    T_history                T_trx (t0)               T_batch_run (t1)
-------|--------------------------*---------------------------|--------> Waktu
       |  Fitur agregasi benar    |   Fitur 'Bocor' jika      |
       |  [t0 - 24h s/d t0]       |   menghitung s/d t1       |
```

Arsitektur produksi modern memisahkan lapisan fitur menjadi:
*   **Offline Store**: Menyimpan log transaksi historis tak bermutasi (*immutable event logs*) pada format kolumnar (Apache Iceberg/Delta Lake) yang mendukung operasi *ASOF JOIN* untuk rekonstruksi fitur historis bebas bocor (*point-in-time join*).
*   **Online Store**: Basis data *key-value* berlatensi sub-milidetik (Redis, Amazon DynamoDB) yang hanya menyimpan status mutakhir fitur per entitas ($t_{now}$) untuk diakses saat inferensi real-time.

---

## 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Riset (Jupyter) | Pendekatan Arsitektur Produksi (Enterprise) |
| :--- | :--- | :--- |
| **Pipeline State** | Variabel global, `pandas.DataFrame.apply()` lambat, parameter skalar tercecer. | Encapsulated Transformers, serialisasi artefak statis (`joblib`/`ONNX`), zero-leakage state. |
| **Penskalaan** | In-memory `pandas` (terbatas RAM mesin tunggal). | Vectorized out-of-core memory (`Polars`), streaming lazily evaluated execution plan. |
| **Sinkronisasi Fitur** | Duplikasi logika SQL di ETL dan logika Python di microservice inferensi. | **Single Source of Truth** via Feature Store (Feast/Hopsworks) menjamin kalkulasi identik. |
| **Karakteristik Temporal** | Filter statis `train_test_split(shuffle=True)`. | Out-of-Time (OOT) Splits & Point-in-Time joins via partition time ranges. |
| **Validasi Skema** | Asumsi tipe data implisit (sering crash karena `NaN` mendadak). | Skema prediktif tervalidasi via kontrak data statis (`Pydantic`, Great Expectations). |

---

## 5. How: Workflow Detail

Alur rekayasa fitur produksi enterprise dirancang melalui 5 fase linier deterministik:

```
[Raw Data Sources]
   │
   ├── (Batch Ingestion: Parquet / Warehouse)
   └── (Stream Ingestion: Kafka / EventHub)
         │
         ▼
[Feature Engine (Polars / PySpark)]
   │ 
   ├── 1. Temporal & Point-in-Time Correctness Join (ASOF)
   ├── 2. Out-of-Fold Bayesian Encoding Generation
   └── 3. Vectorized Mathematical & Trigonometric Encoding
         │
         ├── Offline Pipeline ──────────────┐
         ▼                                  ▼
[Feature Registry & Metadata]       [Offline Feature Store]
(Schema Validation, Data Contract)   (Iceberg / Parquet)
         │                                  │
         │ (Sync Latest State)              ▼
         ▼                          [ML Model Training]
[Online Feature Store]               (XGBoost / LightGBM)
(Redis Cluster: sub-10ms)                   │
         │                                  ▼
         └───────► [Model Serving API] ◄────┘
                   (Pydantic Validation -> Inference Engine)
```

1.  **Fase Raw Ingestion**: Pengambilan data melalui pipeline stream (Kafka) atau batch (Object Storage).
2.  **Fase Transformation & Point-in-Time Join**:
    *   Pengurutan berbasis stempel waktu.
    *   Penggabungan asinkron (*ASOF JOIN*) antara label peristiwa dan tabel agregasi fitur.
3.  **Fase State Registration**: Parameter stateful (koefisien normalisasi, OOF priors, kosa kata kategorikal) disimpan ke dalam artefak versioned (MLflow/S3).
4.  **Fase Dual Store Population**: Data historis lengkap ditulis ke Offline Store (Parquet/Iceberg). Nilai fitur paling mutakhir dituliskan ke Online Store (Redis).
5.  **Fase Inference Serving**: Model inference microservice menerima ID entitas, membaca fitur *low-latency* dari Redis, mengeksekusi transformasi stateless, lalu mengirimkannya ke model.

---

## 6. Analogy & Diagram ASCII

### Analogi Restoran Cepat Saji (Fast-Food Franchise)
*   **Ad-Hoc / Notebook**: Seorang koki memasak kentang dari awal (mengupas, memotong, menggoreng) setiap kali ada pelanggan datang di kasir. Pelanggan menunggu lama, dan ukuran kentang goreng tidak konsisten antar koki.
*   **Production Feature Store**: Dapur pusat (Offline Pipeline) memotong, membumbui, dan membekukan kentang dengan ukuran standar industri. Kentang beku didistribusikan ke lemari pendingin cepat saji (Online Store - Redis). Ketika pesanan masuk di kasir, koki hanya perlu menggoreng dalam 30 detik (Stateless Inference) berdasarkan instruksi standar resep (Feature Registry).

### Diagram Dual-Store Feature Pipeline Architecture
```
                         +-----------------------------+
                         |     Event / Raw Source      |
                         +--------------+--------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v (Batch Pipeline)                            v (Streaming Pipeline)
      +----------------------+                      +----------------------+
      | Polars/Spark Builder |                      | Spark Stream / Flink |
      +----------+-----------+                      +----------+-----------+
                 |                                             |
                 v                                             v
      +----------------------+                      +----------------------+
      | Point-in-Time Join   |                      | Real-time Aggregator |
      | (ASOF Engine)        |                      +----------+-----------+
      +----------+-----------+                                 |
                 |                                             |
                 +----------------------+                      |
                 |                      |                      |
                 v                      v                      v
        +------------------+   +---------------------------------------+
        |  Offline Store   |   |             Online Store              |
        |  (Iceberg / S3)  |   |           (Redis Cluster)             |
        +--------+---------+   +-------------------+-------------------+
                 |                                 |
                 v                                 v (Low Latency read)
        +------------------+             +-------------------+
        | Training Process |             | Model Serving API |
        | (Target Encoders)|             | (Stateless Infer) |
        +--------+---------+             +---------+---------+
                 |                                 ^
                 +--------- Serialized ------------+
                           Artifacts (State)
```

---

## 7. Implementation Examples

### 7.1 Simple Example: Robust Trigonometric Cyclic Encoder
Transformasi fitur temporal berbasis siklus jam (0–23) atau hari (1–7) agar merepresentasikan kontinuitas jarak Euclidean antar waktu ($23:59$ dekat dengan $00:00$).

```python
import numpy as np
import polars as pl
from sklearn.base import BaseEstimator, TransformerMixin

class RobustCyclicFeatureEncoder(BaseEstimator, TransformerMixin):
    """
    Stateless Cyclic Transformer mengonversi representasi waktu diskrit 
    menjadi koordinat 2D (sin & cos).
    """
    def __init__(self, cycle_period: float, col_name: str):
        self.cycle_period = float(cycle_period)
        self.col_name = col_name

    def fit(self, X, y=None):
        # Operasi stateless tidak membutuhkan fitting data historis
        return self

    def transform(self, X: pl.DataFrame) -> pl.DataFrame:
        if self.col_name not in X.columns:
            raise KeyError(f"Kolom target {self.col_name} tidak ditemukan dalam input data.")
            
        transformed_df = X.with_columns([
            (2 * np.pi * pl.col(self.col_name) / self.cycle_period).sin().alias(f"{self.col_name}_sin"),
            (2 * np.pi * pl.col(self.col_name) / self.cycle_period).cos().alias(f"{self.col_name}_cos")
        ]).drop(self.col_name)
        
        return transformed_df

# Unit Test Skrip Sederhana
if __name__ == "__main__":
    raw_data = pl.DataFrame({"hour": [0, 6, 12, 18, 23]})
    encoder = RobustCyclicFeatureEncoder(cycle_period=24.0, col_name="hour")
    result = encoder.transform(raw_data)
    print("Cyclic Feature Representations:\n", result)
```

### 7.2 Practical Example: Enterprise-Grade Stateful Target Encoder dengan Bayesian Smoothing & K-Fold Out-of-Fold State Guard
Berikut adalah transformer produksi yang mematuhi API Scikit-learn, dilengkapi validasi tipe, proteksi *leakage*, dan penanganan kategori unseen:

```python
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import KFold

class OutOfFoldBayesianTargetEncoder(BaseEstimator, TransformerMixin):
    """
    Enterprise-Grade Target Encoder.
    - Menggunakan K-Fold Out-of-Fold selama `fit_transform` untuk mencegah leakage.
    - Menggunakan Bayesian Smoothing untuk regularisasi kardinalitas tinggi.
    - Menangani Unseen Categories saat transformasi data inferensi/test.
    """
    def __init__(
        self,
        categorical_columns: List[str],
        smoothing_weight: float = 10.0,
        smoothing_scale: float = 1.0,
        n_splits: int = 5,
        random_state: int = 42
    ):
        self.categorical_columns = categorical_columns
        self.smoothing_weight = smoothing_weight
        self.smoothing_scale = smoothing_scale
        self.n_splits = n_splits
        self.random_state = random_state
        
        # State storage
        self.global_target_mean_: float = 0.0
        self.encoding_maps_: Dict[str, Dict[str, float]] = {}

    def _calculate_smoothed_mean(self, count: int, mean: float) -> float:
        # Menghitung formula Bayesian Smoothing
        factor = 1.0 / (1.0 + np.exp(-(count - self.smoothing_weight) / self.smoothing_scale))
        return float(factor * mean + (1.0 - factor) * self.global_target_mean_)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "OutOfFoldBayesianTargetEncoder":
        if not isinstance(X, pd.DataFrame):
            raise TypeError("X harus bertipe pandas.DataFrame")
        if not isinstance(y, pd.Series):
            raise TypeError("y harus bertipe pandas.Series")

        self.global_target_mean_ = float(y.mean())
        self.encoding_maps_ = {}

        for col in self.categorical_columns:
            if col not in X.columns:
                raise KeyError(f"Kolom '{col}' tidak ditemukan di DataFrame.")
            
            stats = y.groupby(X[col]).agg(['count', 'mean'])
            encoding_map = {}
            for category, row in stats.iterrows():
                encoding_map[str(category)] = self._calculate_smoothed_mean(row['count'], row['mean'])
            self.encoding_maps_[col] = encoding_map
            
        return self

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Khusus untuk data training: hitung encodings secara Out-of-Fold untuk
        mencegah memorisasi langsung target oleh model.
        """
        if not isinstance(X, pd.DataFrame) or not isinstance(y, pd.Series):
            raise TypeError("X dan y harus berupa pandas.DataFrame dan pandas.Series")

        self.fit(X, y)
        X_out = X.copy()
        
        # Lakukan validasi silang Out-of-Fold
        kf = KFold(n_splits=self.n_splits, shuffle=True, random_state=self.random_state)
        
        for col in self.categorical_columns:
            oof_series = pd.Series(index=X.index, dtype=np.float64)
            
            for train_idx, val_idx in kf.split(X, y):
                X_train_fold, y_train_fold = X.iloc[train_idx], y.iloc[train_idx]
                X_val_fold = X.iloc[val_idx]
                
                fold_global_mean = float(y_train_fold.mean())
                stats = y_train_fold.groupby(X_train_fold[col]).agg(['count', 'mean'])
                
                fold_map = {}
                for cat, row in stats.iterrows():
                    f = 1.0 / (1.0 + np.exp(-(row['count'] - self.smoothing_weight) / self.smoothing_scale))
                    fold_map[cat] = float(f * row['mean'] + (1.0 - f) * fold_global_mean)
                
                # Petakan ke validasi fold, fallback ke fold_global_mean jika kategori belum terlihat
                oof_series.iloc[val_idx] = X_val_fold[col].map(fold_map).fillna(fold_global_mean)
                
            X_out[f"{col}_encoded"] = oof_series
            X_out.drop(columns=[col], inplace=True)
            
        return X_out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Untuk data evaluasi dan real-time serving: gunakan mapping yang 
        telah dihitung saat fit penuh.
        """
        if not self.encoding_maps_:
            raise RuntimeError("Transformer belum difitting. Panggil `.fit()` atau `.fit_transform()` terlebih dahulu.")
            
        X_out = X.copy()
        for col in self.categorical_columns:
            mapping = self.encoding_maps_[col]
            # Unseen categories fallback ke global_target_mean_
            X_out[f"{col}_encoded"] = (
                X_out[col].astype(str).map(mapping).fillna(self.global_target_mean_)
            )
            X_out.drop(columns=[col], inplace=True)
            
        return X_out

# Verifikasi Operasional
if __name__ == "__main__":
    df_train = pd.DataFrame({
        "device_brand": ["Apple", "Apple", "Samsung", "Xiaomi", "Xiaomi", "Apple", "Nokia"],
        "fraud_label": [0, 0, 1, 0, 1, 0, 1]
    })
    
    encoder = OutOfFoldBayesianTargetEncoder(categorical_columns=["device_brand"], smoothing_weight=2.0)
    train_encoded = encoder.fit_transform(df_train.drop(columns=["fraud_label"]), df_train["fraud_label"])
    print("OOF Transformed Training Data:\n", train_encoded)
    
    df_inference = pd.DataFrame({"device_brand": ["Samsung", "UnknownBrand"]})
    infer_encoded = encoder.transform(df_inference)
    print("\nProduction Transformed Serving Data:\n", infer_encoded)
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Fraud Detection pada Sistem Transaksi Finansial (Scale: 50.000 RPS, $P99 < 15\text{ ms}$)
*   **Konteks**: Sebuah payment gateway memproses $50.000$ transaksi/detik secara global. Setiap transaksi memerlukan scoring probabilitas fraud menggunakan model LightGBM secara real-time.
*   **Permasalahan Rekayasa Fitur**:
    1.  Fitur agregasi penting: `count_trx_merchant_last_1h`, `total_amount_user_last_24h`, dan `user_device_entropy`.
    2.  Jika dihitung secara langsung via SQL on the fly, database transactional akan mengalami *deadlock* dan latensi melonjak melampaui $400\text{ ms}$.
    3.  Pembaruan batch konvensional harian menyebabkan *blind-spot window* hingga 24 jam terhadap aksi penipuan baru.
*   **Implementasi Solusi Terpadu**:
    *   **Pipeline Streaming Dual-Stream**: Log transaksi masuk ke Apache Kafka diproses paralel oleh Apache Flink secara *sliding-window* (interval 1 menit, 1 jam, 24 jam).
    *   **Online Feature Storage**: Apache Flink memutakhirkan state agregasi langsung ke **Redis Enterprise Cluster** dengan multi-master shard via in-memory increment (`HINCRBYFLOAT`, `HINCRBY`).
    *   **Point-in-Time Offline Generation**: Untuk data training bulanan, data transaksi disimpan di Delta Lake. Fitur offline diekstrak menggunakan **ASOF Join** berbasis stempel waktu transaksi persis sebelum model training dijalankan.
    *   **Microservice Inference Flow**: Saat transaksi $T$ masuk:
        1. API membaca user ID & merchant ID.
        2. Mengambil vektor agregasi dari Redis ($< 1.8\text{ ms}$).
        3. Menjalankan stateless normalisasi & sinusoidal cyclical time-features di memori API ($< 0.2\text{ ms}$).
        4. Inferensi model LightGBM ($< 3.0\text{ ms}$).
        *Total Latency P99 tercapai pada*: **$8.2\text{ ms}$**.

---

## 9. Trade-offs

| Pendekatan Rekayasa Fitur | Latensi Inferensi | Biaya Infrastruktur (Cost) | Skalabilitas (Data Scale) | Resiko Kebocoran Data (Data Leakage) |
| :--- | :--- | :--- | :--- | :--- |
| **Compute On-the-Fly (SQL API)** | Sangat Tinggi ($>200\text{ ms}$) | Rendah (tidak butuh store sekunder) | Rendah (Bottleneck I/O pada Database) | Rendah |
| **Precomputed Batch to Redis** | Sangat Rendah ($<2\text{ ms}$) | Sedang (Biaya Memory Redis RAM) | Tinggi | Tinggi (Stale data: delay 1-24 jam) |
| **Streaming Aggregates + Feature Store** | Rendah ($2\text{--}8\text{ ms}$) | Tinggi (Cluster Flink + Multi-AZ Redis) | Sangat Tinggi ($>100.000\text{ RPS}$) | Sangat Rendah (Point-in-time synchronization) |
| **Pure Pandas In-Process Execution** | Sedang ($20\text{--}50\text{ ms}$) | Rendah | Sangat Rendah (Terbatas Single Node Memory) | Sangat Tinggi jika state tidak dipartisi benar |

---

## 10. Common Mistakes & Troubleshooting

### 10.1 Silent Data Leakage: Standard Scaler Fit pada Seluruh Dataset
*   **Kesalahan Fatal**: Menjalankan `scaler.fit(df)` sebelum membagi data menjadi train, validation, dan test set.
*   **Dampak Negatif**: Matriks varians dan mean populasi uji merembes ke set pelatihan. Metrik akurasi validasi menjadi *over-optimistic*, tetapi performa drop tajam di server produksi.
*   **Solusi**: Terapkan enkapsulasi Pipeline murni Scikit-learn atau isolasi fold menggunakan:
    ```python
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression())
    ])
    # fit HANYA pada train
    pipeline.fit(X_train, y_train)
    ```

### 10.2 Training-Serving Skew Akibat Parsing Nilai Kosong (Imputation Skew)
*   **Kesalahan**: Pada data training, missing value diimputasi dengan nilai mean batch `X_train['amount'].mean()`. Namun pada microservice inferensi, developer lain secara terpisah menangani missing value dengan mengisinya menggunakan nilai `0.0`.
*   **Deteksi**: Perbedaan distribusi input antara pelatihan dan produksi melalui kalkulasi *Population Stability Index* (PSI) atau *Wasserstein Distance*. Jika $\text{PSI} > 0.25$, terjadi perubahan signifikan pada profil data.
*   **Solusi**: Serialisasikan seluruh parameter transformer ke dalam satu artefak pipeline yang tidak dapat diubah (immutable pipeline object). Gunakan kontrak skema data menggunakan `pydantic`.

### 10.3 Inversi Skala Waktu pada ASOF Join (Future Leakage)
*   **Gejala**: Akurasi deteksi kecurangan mencapai $99.9\%$, namun saat diterapkan di produksi, akurasi anjlok ke $65\%$.
*   **Akar Masalah**: ASOF Join dikonfigurasi dengan arah pencarian `direction='forward'` alih-alih `direction='backward'`. Akibatnya, agregasi mengambil peristiwa yang terjadi di masa depan setelah transaksi target terjadi.
*   **Penyelesaian**: Pastikan parameter join temporal di Polars selalu menggunakan arah `backward`:
    ```python
    result = df_events.sort("timestamp").join_asof(
        df_features.sort("timestamp"),
        on="timestamp",
        by="user_id",
        strategy="backward" # Hanya menyerap data <= timestamp transaksi
    )
    ```

---

## 11. Best Practices (Production Checklist)

- [ ] **State Partitioning Isolation**: Apakah fungsi `.fit()` transformer secara absolut HANYA dipanggil pada partisi training?
- [ ] **Immutability Contract**: Apakah artefak pipeline fitur disimpan dalam format biner yang diproteksi versi (`joblib` hashing, MLflow artifact tag)?
- [ ] **Point-In-Time Validated**: Apakah pembuatan agregasi training historis telah menerapkan ASOF/backward time-matching untuk mencegah time-travel leakage?
- [ ] **Unseen Category Handlers**: Apakah semua Categorical/Target Encoders memiliki mekanisme fallback nilai default ketika menerima kategori yang belum pernah tercatat?
- [ ] **Serialization Portability**: Apakah struktur custom transformer mewarisi `sklearn.base.BaseEstimator` dan tidak menggunakan fungsi `lambda` (karena lambda gagal diserialisasi dengan standar pickle)?
- [ ] **Vectorized Implementation**: Apakah pipeline feature engineering bebas dari iterasi berbasis `for index, row in df.iterrows()` dan menggunakan instruksi vektorisasi CPU/SIMD (`polars.Expr` / `numpy`)?
- [ ] **Latency Budget**: Apakah pipeline stateless transformasi di microservice inferensi memiliki waktu eksekusi di bawah budget maksimum ($< 5\text{ ms}$)?

---

## 12. Hands-on Practice

Buatlah script pipeline produksi pada direktori file: `hands-on/m02/production_feature_pipeline.py`.

### Langkah 1: Persiapan Lingkungan & Direktori
```bash
mkdir -p hands-on/m02
cd hands-on/m02
pip install polars pandas scikit-learn pyarrow
```

### Langkah 2: Implementasi Pipeline Produksi Lengkap
Tuliskan kode berikut ke dalam berkas `hands-on/m02/production_feature_pipeline.py`:

```python
"""
hands-on/m02/production_feature_pipeline.py
Sistem pipeline ekstraksi fitur skalabel bebas leakage.
"""
import polars as pl
import numpy as np
from datetime import datetime, timedelta
import joblib

def generate_synthetic_data(num_records: int = 100_000):
    np.random.seed(42)
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    
    users = [f"USR_{i:04d}" for i in range(1, 500)]
    merchants = [f"MER_{i:03d}" for i in range(1, 50)]
    
    data = {
        "transaction_id": [f"TRX_{i:08d}" for i in range(num_records)],
        "timestamp": [start_time + timedelta(seconds=int(np.random.exponential(scale=30) * i)) for i in range(num_records)],
        "user_id": np.random.choice(users, size=num_records),
        "merchant_id": np.random.choice(merchants, size=num_records),
        "amount": np.random.exponential(scale=50.0, size=num_records).round(2),
        "is_fraud": np.random.choice([0, 1], size=num_records, p=[0.97, 0.03])
    }
    return pl.DataFrame(data).sort("timestamp")

def build_offline_point_in_time_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Menghitung agregasi jendela waktu secara Point-in-Time aman
    menggunakan Polars windowing expressions.
    """
    print("[INFO] Mengeksekusi windowing temporal agregasi...")
    
    # Hitung rolling metrics transaksi 1 jam terakhir per user
    transformed_df = df.with_columns([
        pl.col("amount")
        .rolling_sum(by="timestamp", window_size="1h", closed="left")
        .over("user_id")
        .alias("user_amount_sum_last_1h"),
        
        pl.col("transaction_id")
        .rolling_count(by="timestamp", window_size="1h", closed="left")
        .over("user_id")
        .alias("user_trx_count_last_1h")
    ]).fill_null(0.0)
    
    # Ekstraksi komponen siklikal temporal
    transformed_df = transformed_df.with_columns([
        pl.col("timestamp").dt.hour().alias("hour_of_day")
    ]).with_columns([
        (2 * np.pi * pl.col("hour_of_day") / 24.0).sin().alias("hour_sin"),
        (2 * np.pi * pl.col("hour_of_day") / 24.0).cos().alias("hour_cos")
    ]).drop(["hour_of_day"])
    
    return transformed_df

if __name__ == "__main__":
    print("[PROD PIPELINE] Memulai simulasi ekstraksi data historis...")
    raw_df = generate_synthetic_data(100_000)
    
    # Eksekusi Transformasi Fitur
    processed_df = build_offline_point_in_time_features(raw_df)
    
    # Simpan output Partisi bebas leakage ke format Parquet
    output_path = "train_features_store.parquet"
    processed_df.write_parquet(output_path)
    print(f"[SUCCESS] Dataset fitur enterprise tersimpan di {output_path}")
    print(processed_df.select([
        "transaction_id", "timestamp", "user_id", 
        "user_amount_sum_last_1h", "user_trx_count_last_1h", 
        "hour_sin", "hour_cos", "is_fraud"
    ]).head(5))
```

### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip pipeline:
```bash
python hands-on/m02/production_feature_pipeline.py
```

---

## 13. Exercise

### Level Easy
1. Modifikasi class `RobustCyclicFeatureEncoder` pada Bagian 7.1 agar dapat menerima parameter opsional `drop_original: bool = True`. Jika diset `False`, kolom asli tidak boleh dihapus.
2. Buatlah fungsi validasi skema sederhana yang memeriksa apakah kolom target agregasi mengandung nilai $\infty$ (*infinite*) atau NaN pasca kalkulasi rolling window.

### Level Medium
1. Implementasikan custom transformer Scikit-Learn `Log1pWinsorizer` yang melakukan pembatasan nilai ekstrem (*winsorizing*) pada persentil 99th ($\text{p}99$) yang dihitung secara *stateful* pada `.fit()`, kemudian melakukan operasi $y = \log(x + 1)$ pada `.transform()`.
2. Tulis skrip benchmark performa menggunakan library `time` yang membandingkan kecepatan kalkulasi agregasi rolling window (jendela 1 jam) antara `pandas` dan `polars` dengan data uji $500.000$ baris data.

### Level Hard
1. Buat sistem simulasi integrasi *Online-Offline Feature Store*. Tulis class `MiniFeatureStoreManager` yang:
   * Menyimpan agregasi historis ke dalam struktur file Parquet lokal (Offline Layer).
   * Melakukan ekspor nilai state terbaru per `user_id` ke dalam SQLite/Dictionary memori lokal yang merepresentasikan Redis (Online Layer).
   * Menyediakan method `.get_online_features(user_id: str)` dengan garansi latensi eksekusi sub-milidetik ($< 1\text{ ms}$).

---

## 14. Challenge
Sebuah platform media sosial video pendek (*short-form video platform*) memiliki masalah degradasi model rekomendasi:
*   Dataset interaksi mencapai **$20.000.000$ baris per hari**.
*   Sinyal interaksi penting berasal dari rasio retensi tontonan: $\text{watch\_ratio} = \frac{\text{watch\_duration}}{\text{video\_length}}$.
*   Pengguna sering membagikan video lama yang mendadak viral kembali (*cold-to-hot transition*).
*   Target variabel: `is_liked` (biner).

**Tantangan Arsitektur**:
Rancang dan bangun arsitektur end-to-end (struktur kelas modular tanpa notebook) yang mencakup:
1.  **Dynamic Exponential Decay Aggregation**: Fitur agregasi `video_historical_popularity` yang menyusutkan bobot view lama secara eksponensial terhadap waktu ($e^{-\lambda \cdot \Delta t}$).
2.  **Strict Anti-Leakage Partitioning**: Menggunakan sistem partisi data berbasis Sliding Temporal Block mingguan (Week 1 = Train, Week 2 = Validation, Week 3 = Test).
3.  **Low-Latency Vectorized Pipeline**: Menggunakan runtime `Polars` LazyFrame API murni (tanpa satu pun konversi ke pandas/list python).
4.  **Schema Enforcement**: Validasi ketat yang menjamin tipe data keluaran bebas dari deviasi float precision (`Float32` untuk menghemat memori transfer jaringan).

---

## 15. Quiz Evaluasi Pemahaman

### 15.1 Pertanyaan Basic
1. Apa perbedaan arsitektur mendasar antara transformasi fitur stateless dan stateful?
2. Mengapa cyclic encoding menggunakan pasangan dua dimensi $(\sin, \cos)$ daripada nilai skalar linier terstandardisasi $(0 \rightarrow 1)$?
3. Sebutkan risiko teknis terbesar jika operasi `StandardScaler.fit()` dilakukan sebelum proses pembagian dataset train-test!
4. Apa fungsi dari komponen *Bayesian smoothing* pada Target Encoding?
5. Mengapa format berkas kolumnar seperti Apache Parquet jauh lebih disukai untuk Offline Feature Store dibandingkan format baris CSV?

### 15.2 Pertanyaan Intermediate
6. Jelaskan bagaimana mekanisme operasi *ASOF JOIN* secara matematis dan sistematis mencegah timbulnya *time-travel leakage* pada dataset transaksi event!
7. Bagaimana penanganan terbaik bagi transformer Out-Of-Fold Target Encoder ketika menerima kategori baru (*unseen categorical value*) pada tahap inferensi produksi?
8. Mengapa penerapan rolling aggregation window `closed='left'` krusial dalam rekayasa fitur data runtun waktu finansial?
9. Apa yang dimaksud dengan fenomena *Training-Serving Skew*, dan bagaimana arsitektur Feature Store modern mengeliminasinya?
10. Dalam kondisi apa teknik normalisasi fitur *Z-Score standardizer* gagal memberikan performa optimal dibanding *Robust Median/IQR Scaler*?

### 15.3 Skenario Kasus Produksi
11. **Skenario 1**: Tim Data Engineering Anda memproses dataset churn sebesar $50\text{ GB}$. Pipeline preprocessing menggunakan `pandas.DataFrame.apply()` membutuhkan waktu 14 jam untuk selesai dieksekusi di server ETL dan sering mengalami *Out-Of-Memory (OOM)*. Apa restrukturisasi arsitektural yang harus Anda ambil untuk memangkas waktu proses di bawah 30 menit?
12. **Skenario 2**: Pada microservice fraud detection, model Machine Learning Anda membutuhkan fitur `merchant_risk_score`. Nilai ini dihitung oleh batch Spark job harian setiap jam 00:00. Pada pukul 14:00, sebuah merchant disusupi hacker dan melakukan rentetan transaksi mencurigakan. Mengapa arsitektur ini gagal, dan bagaimana desain perbaikannya tanpa membakar biaya infrastruktur secara berlebihan?
13. **Skenario 3**: Model prediksi keterlambatan pengiriman logistik menunjukkan performa fantastis pada data historis tahun 2025 (F1-score $0.94$), namun saat di-deploy secara *shadow* di Q1 2026, F1-score drop menjadi $0.58$. Dari perspektif rekayasa fitur temporal dan kebocoran data, sebutkan langkah root-cause analysis (RCA) sistematis untuk melacak anomali tersebut!

---

## Kunci Jawaban & Panduan Solusi Quiz

### Basic
1. **Stateless vs Stateful**: Stateless hanya memerlukan baris yang bersangkutan tanpa konteks eksternal (contoh: $\log(x)$); Stateful memerlukan kalkulasi parameter agregasi seluruh populasi training set (contoh: $\mu, \sigma$ pada scaler).
2. **Cyclic Sin/Cos**: Agar jarak metrik Euclidean antara ujung siklus akhir ($23:59$) dan awal ($00:00$) kembali berdekatan secara kontinu, tidak terputus diskrit.
3. **Risiko Fit Sebelum Split**: Terjadinya *Data Leakage*, informasi parameter populasi data uji bocor ke data latih, membuat metrik validasi bias dan over-optimistic.
4. **Fungsi Bayesian Smoothing**: Memberikan bobot penyeimbang (*shrinkage*) antara mean lokal kategori berfrekuensi rendah dengan mean global populasi, menghindari bias estimasi ekstrem akibat sampel sedikit.
5. **Keuntungan Parquet**: Kompresi efisien, komputasi kolumnar cepat untuk agregasi, pembacaan subset kolom tanpa scanning seluruh disk file (*projection pushdown*).

### Intermediate
6. **ASOF Join Mechanism**: ASOF Join mencocokkan baris tabel referensi dengan baris tabel transaksi menggunakan kriteria kondisi timestamp terbesar yang lebih kecil atau sama dengan ($t_{feature} \le t_{event}$), memblokir data di masa depan ($t_{feature} > t_{event}$).
7. **Unseen Category Handling**: Kategori baru dipetakan ke nilai rata-rata prior global (*global target mean*) yang telah dibekukan saat fase pelatihan.
8. **Windowing `closed='left'`**: Memastikan transaksi pada stempel waktu persis $t_0$ tidak ikut menghitung dirinya sendiri pada agregasi historis masa lalu, yang memicu kebocoran informasi masa kini ke fitur prediktor.
9. **Training-Serving Skew**: Ketidaksamaan definisi, kode, atau distribusi fitur antara fase training dan inference API. Dieliminasi dengan Feature Store yang menggunakan satu repositori definisi fitur tunggal untuk pipeline batch maupun serving online.
10. **Z-Score vs Robust Scaler**: Z-Score gagal jika data memiliki outlier ekstrem, karena $\mu$ dan $\sigma$ sangat rentan terdistorsi nilai pencilan. Robust Scaler berbasis Median dan IQR mempertahankan invariansi terhadap outlier.

### Skenario Kasus Produksi
11. **Solusi Skenario 1**: Ubah eksekusi ke engine pemrosesan kolumnar terparalelisasi seperti **Polars** (dengan Lazy execution plan) atau **PySpark**. Ganti seluruh pemanggilan `apply(lambda)` dengan ekspresi vektorisasi asli (`pl.col()`), dan gunakan streaming chunk reader jika memori terbatas.
12. **Solusi Skenario 2**: Sistem batch harian memiliki *latency window* 24 jam. Arsitektur harus diubah menjadi **Streaming Feature Pipeline** menggunakan Kafka dan framework streaming (misal Apache Flink). Status agregasi risiko merchant dihitung secara real-time dan disimpan langsung pada in-memory key-value database (Redis) sehingga skor terbarui dalam hitungan detik setelah anomali transaksi pertama terjadi.
13. **Solusi Skenario 3**: 
    * Periksa apakah metrik agregasi historis dihitung menggunakan batas waktu relatif ke masa kini atau absolut (cek time-travel leakage).
    * Evaluasi *Feature Drift* menggunakan metrik Population Stability Index (PSI) antar kuartal data 2025 vs 2026.
    * Periksa kemungkinan *Label Leakage* (misal: fitur status pengiriman yang hanya terisi setelah armada jalan, namun tidak tersedia saat pesanan dibuat).
    * Audit validasi temporal: Pastikan validasi silang historis menggunakan skema *Time-Series Split / Out-of-Time (OOT)*, bukan random K-Fold split.

---

## 16. Summary
*   Arsitektur rekayasa fitur enterprise menuntut pemisahan mutlak antara kalkulasi parameter **Stateful** dan transformasi **Stateless**.
*   Teknik encoding lanjut seperti **Bayesian Target Encoding** wajib dipadukan dengan teknik isolasi partisi **Out-of-Fold (OOF)** untuk menekan risiko memorisasi dan overfitting label.
*   Pencegahan kebocoran data temporal membutuhkan ketelitian matematis: agregasi historis wajib menerapkan operasi **Point-in-Time Correctness** via backward ASOF joining.
*   Sistem inferensi real-time berskala besar mengandalkan arsitektur **Feature Store Dual-Layer**: Parquet/Iceberg untuk pelatihan analitik bebas kebocoran, dan Redis In-Memory untuk penyajian latensi sub-milidetik ($p99 < 15\text{ ms}$).