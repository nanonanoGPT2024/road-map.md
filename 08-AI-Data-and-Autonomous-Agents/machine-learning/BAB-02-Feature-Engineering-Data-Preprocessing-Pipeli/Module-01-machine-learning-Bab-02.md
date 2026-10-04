# Bab 02: Feature Engineering & Data Preprocessing Pipelines

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis & Mengeliminasi Data Leakage**: Mengidentifikasi titik kritis kebocoran data (*train-test contamination*, *target leakage*, dan *lookahead bias*) dalam arsitektur pra-pemrosesan data tabular dan temporal.
- **Mengonstruksi Custom Transformer Scikit-Learn**: Mengembangkan modul transformasi data berbasis kelas yang mewarisi `BaseEstimator` dan `TransformerMixin` dengan penanganan *state* internal secara deterministik.
- **Membangun Pipeline Multi-Modal Tabular**: Merancang `ColumnTransformer` heterogen untuk data numerik, kategorikal skalar, teks ringkas, dan temporal dengan *fail-safe imputation* dan *categorical encoding* terstandarisasi.
- **Menjamin Serialisasi & Invariance State**: Mengimplementasikan serialisasi pipeline menggunakan format aman (`skops`/`joblib`), mencegah *training-serving skew*, dan memvalidasi integritas skema data input secara runtime menggunakan tipe data terstruktur.

---

## 2. Concept Overview
*Data Preprocessing* dan *Feature Engineering* bukanlah sekadar tahap ad-hoc pembersihan data, melainkan bagian integral dari hipotesis model machine learning itu sendiri. Secara matematis, proses ini adalah pemetaan deterministik dari ruang input mentah $\mathcal{X}_{raw}$ ke ruang representasi fitur $\mathcal{X}_{features} \subseteq \mathbb{R}^d$:

$$\phi: \mathcal{X}_{raw} \to \mathbb{R}^d$$

Fungsi $\phi$ memiliki dua varian operasi:
1. **Stateless Transformations**: Operasi tanpa dependensi pada distribusi data agregat, di mana $\phi(x_i)$ independen terhadap subset $\{x_j\}_{j \neq i}$. Contoh: transformasi logaritmik $\log(x + 1)$, ekstraksi komponen tanggal (*day of week*), atau manipulasi string deterministik.
2. **Stateful Transformations**: Operasi yang membutuhkan estimasi parameter statistik $\Theta$ dari populasi data latih ($D_{train}$), di mana $\phi(x_i; \Theta)$ bergantung pada $\Theta = f(D_{train})$. Contoh: z-score standardization ($\mu, \sigma$), target encoding ($\mathbb{E}[y|x]$), median imputation, dan PCA projection matrix.

```
       +-------------------------------------------------------+
       |                  D_train (Data Latih)                 |
       +-------------------------------------------------------+
                                  |
                                  v  .fit()
                       +----------------------+
                       | Parameter State (Theta)| (misal: mean, std, quantiles)
                       +----------------------+
                                  |
        +-------------------------+-------------------------+
        |                                                   |
        v  .transform()                                     v  .transform()
+---------------+                                   +---------------+
|    D_train    |                                   |    D_test     |
+---------------+                                   +---------------+
        |                                                   |
        v                                                   v
+---------------+                                   +---------------+
| X_train_scaled|                                   |  X_test_scaled|
+---------------+                                   +---------------+
```

**Mental Model Kunci**: 
Setiap parameter $\Theta$ adalah bobot model yang tidak terlatih melalui *gradient descent*, melainkan dihitung melalui agregasi empiris. Membiarkan informasi dari $D_{test}$ atau $D_{val}$ masuk ke kalkulasi $\Theta$ adalah pelanggaran fundamental validitas empiris (*Data Leakage*), yang membuat metrik evaluasi offline menjadi tidak valid (*over-optimistic bias*).

---

## 3. Why It Matters
Di tingkat enterprise, kegagalan sistem ML di tahap produksi jarang disebabkan oleh arsitektur model (seperti pemilihan transformer atau hyperparameter XGBoost). Mayoritas insiden produksi disebabkan oleh **Training-Serving Skew** dan **Pipeline Breakage**:

1. **Training-Serving Skew**:
   Terjadi ketika transformasi fitur yang dijalankan pada saat *training* (biasanya dijalankan dalam batch via SQL/Pandas) berbeda secara semantik atau numerik dengan kode yang dijalankan saat *real-time inference* (misalnya di-porting ke microservice Go/Java/Python). Perbedaan kecil dalam pembulatan floating-point, penanganan nilai `NULL`, atau urutan *categorical mapping* dapat mendegradasi performa model secara drastis tanpa memicu runtime error.
2. **Data Leakage Berdampak Finansial**:
   Pada domain deteksi *fraud* dan prediksi risiko kredit, menyertakan fitur yang mengagregasikan metrik masa depan (*future leakage*) menghasilkan performa AUCPR mendekati 1.0 pada validasi offline. Ketika model dirilis, performa anjlok ke tingkat tebakan acak karena data masa depan tersebut belum terwujud di waktu inferensi.
3. **Reproducibility & Compliance**:
   Regulasi seperti GDPR dan panduan audit AI perbankan mewajibkan jejak audit penuh dari data mentah hingga prediksi. Pipeline yang tidak terenkapsulasi secara atomik mustahil diuji secara deterministik atau direkonstruksi saat post-mortem audit.

---

## 4. Arsitektur & Diagram Komponen

Arsitektur berikut mengisolasi fasa kalkulasi parameter (*fitting*) dan fasa inferensi (*transforming*) dalam pipeline monolitik yang hermetis:

```
[ Raw Training Data Stream / Parquet Data Lake ]
                     |
                     v
   +------------------------------------+
   |   Pydantic Data Contract Layer     | <--- Validasi Skema, Tipe, & Boundaries
   +------------------------------------+
                     |
                     v
+=============================================================================+
|                      SCIKIT-LEARN PIPELINE ENCAPSULATION                    |
|                                                                             |
|  +-----------------------------------------------------------------------+  |
|  |                  FeatureUnion / ColumnTransformer                     |  |
|  |                                                                       |  |
|  |  [Numerical Features]        [Categorical Features]  [Date/Temporal]  |  |
|  |          |                             |                    |         |  |
|  |          v                             v                    v         |  |
|  |  +---------------+             +---------------+    +---------------+ |  |
|  |  | OutlierHandler|             | Out-of-Vocab  |    | Cyclical      | |  |
|  |  | (Winsorizer)  |             | Imputer       |    | Sine/Cosine   | |  |
|  |  +---------------+             +---------------+    +---------------+ |  |
|  |          |                             |                    |         |  |
|  |          v                             v                    v         |  |
|  |  +---------------+             +---------------+            |         |  |
|  |  | RobustScaler /|             | TargetEncoder /            |         |  |
|  |  | QuantileTrans |             | OneHotEncoder |            |         |  |
|  |  +---------------+             +---------------+            |         |  |
|  +-----------------------------------------------------------------------+  |
|                                     |                                       |
|                                     v                                       |
|             Concatenated Feature Matrix [N x D]                             |
|                                     |                                       |
|                                     v                                       |
|                       [ Estimator: Classifier/Regressor ]                   |
+=============================================================================+
                     |
                     v (Atomic Serialization via joblib/skops)
             +---------------+
             | pipeline.skops|
             +---------------+
                     |
                     |-------- (Deploy Artifact) --------+
                     v                                   v
        [ Offline Batch Inference ]            [ Real-time Microservice API ]
        - Load pipeline                        - Load pipeline
        - Transform & Predict                  - Transform & Predict
        - No recalculation of State            - Zero Training-Serving Skew
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Penanganan Leakage & State Immutability
Pipeline harus memisahkan pemanggilan `.fit()` dan `.transform()`. Aturan baku yang wajib dipatuhi:
- Metode `.fit()` hanya boleh dipanggil pada $D_{train}$. Parameter $\mu$, $\sigma$, daftar kategori unik, nilai imputasi, dan kuantil harus dihitung dan disimpan secara permanen sebagai atribut instans dengan akhiran underscore (misal: `self.mean_`, `self.categories_`).
- Metode `.transform()` hanya boleh melakukan aplikasi fungsional berbasis parameter yang sudah disimpan dalam atribut `self.*_`. Operasi mutasi pada `self.*_` dilarang keras di dalam `.transform()`.
- Saat evaluasi k-fold cross validation, pipeline pra-pemrosesan wajib berada *di dalam* loop validasi silang (di dalam fold), bukan diterapkan sebelum pembagian data.

### 5.2 Strategi Transformasi Numerik Lanjut
- **Distribusi Skewed & Ekor Tebal (Fat-Tailed)**: Menggunakan transformasi Box-Cox ($x > 0$) atau Yeo-Johnson (mendukung nilai negatif) untuk memetakan distribusi non-Gaussian ke Gaussian:
  
  $$\psi(\lambda, y) = \begin{cases} 
  ((y + 1)^\lambda - 1)/\lambda & \text{if } \lambda \neq 0, y \geq 0 \\ 
  \log(y + 1) & \text{if } \lambda = 0, y \geq 0 
  \end{cases}$$

- **Outlier Mitigation**: Menggunakan *Winsorization* berbasis Interquartile Range (IQR) daripada eliminasi baris (*sample dropping*), karena sample dropping di tahap inferensi produksi akan menyebabkan penolakan transaksi (*dropped payload*).
- **Skalabilitas**: `StandardScaler` sensitif terhadap outlier ekstrem. `RobustScaler` (memanfaatkan median dan interquartile range: $\frac{x_i - Q_2}{Q_3 - Q_1}$) direkomendasikan untuk data industri yang rentan anomali transaksional.

### 5.3 Encoding Kategorikal Robust & Dimensi Tinggi
- **One-Hot Encoding**: Menghasilkan ledakan dimensi (*curse of dimensionality*) jika kardinalitas tinggi. Wajib mengonfigurasi parameter `handle_unknown='ignore'` untuk mencegah crash saat kategori baru (*out-of-vocabulary*) muncul di produksi.
- **Target (Mean) Encoding**: Menggantikan kategori dengan nilai ekspektasi target $y$ pada kategori tersebut: $\hat{S}_k = \mathbb{E}[y | x=k]$. Rawan *severe overfitting* pada kategori dengan kemunculan langka. Wajib menerapkan regularisasi m-estimate smoothing:
  
  $$S_i = \lambda_i \bar{y}_i + (1 - \lambda_i) \bar{y}$$
  
  di mana $\lambda_i = \frac{n_i}{n_i + m}$, $n_i$ adalah frekuensi kemunculan kategori $i$, $\bar{y}_i$ adalah rata-rata target kategori, dan $\bar{y}$ adalah prior rata-rata global.

### 5.4 Siklus Fitur Temporal
Data waktu (jam dalam hari, bulan dalam tahun) memiliki sifat siklikal periodik ($23:59 \to 00:00$ adalah transisi linear pendek, bukan lompatan drastis). Pemetaan dilakukan melalui proyeksi trigonometris 2 dimensi:

$$x_{sin} = \sin\left(\frac{2\pi \cdot t}{T}\right), \quad x_{cos} = \cos\left(\frac{2\pi \cdot t}{T}\right)$$

---

## 6. Production-Ready Code Implementation

Berikut implementasi lengkap pipeline Scikit-Learn yang siap digunakan di tingkat produksi (*production-grade*), dilengkapi validasi skema tipe data, *custom transformer*, dan serialisasi aman.

```python
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
import joblib


# ============================================================================
# 1. DATA CONTRACT & SCHEMA VALIDATION LAYER
# ============================================================================
class TransactionRecord(BaseModel):
    transaction_id: str
    amount: float = Field(gt=0, description="Transaction amount must be positive")
    user_age: int = Field(ge=18, le=120, description="Valid user age range")
    device_type: str
    hour_of_day: int = Field(ge=0, le=23)
    target: Optional[int] = Field(default=None, ge=0, le=1)


class BatchInputContract(BaseModel):
    records: List[TransactionRecord]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([r.model_dump() for r in self.records])


# ============================================================================
# 2. CUSTOM ENTERPRISE-GRADE TRANSFORMERS
# ============================================================================
class OutlierCapper(BaseEstimator, TransformerMixin):
    """
    Winsorizer adaptif berbasis Interquartile Range (IQR).
    Menghitung batas bawah dan batas atas pada saat fit,
    dan melakukan clipping pada saat transform.
    """
    def __init__(self, factor: float = 1.5):
        self.factor = factor
        self.lower_bounds_: Dict[str, float] = {}
        self.upper_bounds_: Dict[str, float] = {}
        self.feature_names_in_: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "OutlierCapper":
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X must be a pandas DataFrame.")
        
        self.feature_names_in_ = list(X.columns)
        for col in self.feature_names_in_:
            q25 = X[col].quantile(0.25)
            q75 = X[col].quantile(0.75)
            iqr = q75 - q25
            self.lower_bounds_[col] = q25 - (self.factor * iqr)
            self.upper_bounds_[col] = q75 + (self.factor * iqr)
        
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X must be a pandas DataFrame.")
        
        if not all(col in X.columns for col in self.feature_names_in_):
            missing = set(self.feature_names_in_) - set(X.columns)
            raise ValueError(f"Features missing from inference payload: {missing}")

        X_out = X.copy()
        for col in self.feature_names_in_:
            X_out[col] = X_out[col].clip(
                lower=self.lower_bounds_[col], 
                upper=self.upper_bounds_[col]
            )
        return X_out

    def get_feature_names_out(self, input_features: Optional[List[str]] = None) -> np.ndarray:
        return np.array(self.feature_names_in_, dtype=object)


class CyclicalDateEncoder(BaseEstimator, TransformerMixin):
    """
    Memetakan fitur temporal diskrit (misal: hour of day, day of week)
    ke representasi siklik kontinu menggunakan sin & cos decomposition.
    """
    def __init__(self, period: int = 24):
        self.period = period
        self.feature_names_in_: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "CyclicalDateEncoder":
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X must be a pandas DataFrame.")
        self.feature_names_in_ = list(X.columns)
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X must be a pandas DataFrame.")
        
        encoded_parts = []
        for col in self.feature_names_in_:
            sin_vals = np.sin(2 * np.pi * X[col] / self.period)
            cos_vals = np.cos(2 * np.pi * X[col] / self.period)
            encoded_parts.extend([sin_vals.values, cos_vals.values])
        
        return np.column_stack(encoded_parts)

    def get_feature_names_out(self, input_features: Optional[List[str]] = None) -> np.ndarray:
        out_names = []
        for col in self.feature_names_in_:
            out_names.extend([f"{col}_sin", f"{col}_cos"])
        return np.array(out_names, dtype=object)


# ============================================================================
# 3. PIPELINE ORCHESTRATION BUILDER
# ============================================================================
def build_feature_pipeline(
    numeric_features: List[str],
    categorical_features: List[str],
    temporal_features: List[str]
) -> Pipeline:
    """
    Menyusun end-to-end ColumnTransformer & Feature Pipeline yang hermetis.
    """
    # Numerical Sub-Pipeline
    numeric_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("outlier_capper", OutlierCapper(factor=1.5)),
        ("scaler", RobustScaler())
    ])

    # Categorical Sub-Pipeline
    categorical_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        ("encoder", OneHotEncoder(
            handle_unknown="ignore", 
            sparse_output=False,
            drop="first"
        ))
    ])

    # Temporal Sub-Pipeline
    temporal_pipeline = Pipeline(steps=[
        ("cyclical_encoder", CyclicalDateEncoder(period=24))
    ])

    # Composite Architecture
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
            ("temp", temporal_pipeline, temporal_features)
        ],
        remainder="drop",
        n_jobs=-1
    )

    full_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor)
    ])
    
    return full_pipeline


# ============================================================================
# 4. VERIFIKASI EKSEKUSI TRAINING & SERVING
# ============================================================================
if __name__ == "__main__":
    # 1. Dummy Training Dataset
    raw_train_data = [
        {"transaction_id": "TX1001", "amount": 150.0, "user_age": 28, "device_type": "iOS", "hour_of_day": 14, "target": 0},
        {"transaction_id": "TX1002", "amount": 9500.0, "user_age": 45, "device_type": "Android", "hour_of_day": 2, "target": 1},
        {"transaction_id": "TX1003", "amount": 35.5, "user_age": 22, "device_type": "Web", "hour_of_day": 23, "target": 0},
        {"transaction_id": "TX1004", "amount": 210.0, "user_age": 35, "device_type": "Android", "hour_of_day": 18, "target": 0},
        {"transaction_id": "TX1005", "amount": 100000.0, "user_age": 50, "device_type": "iOS", "hour_of_day": 5, "target": 1}, # Outlier Ekstrem
    ]

    # Validasi Skema via Contract
    validated_train_batch = BatchInputContract(records=[TransactionRecord(**rec) for rec in raw_train_data])
    df_train = validated_train_batch.to_dataframe()

    num_cols = ["amount", "user_age"]
    cat_cols = ["device_type"]
    temp_cols = ["hour_of_day"]

    # Inisialisasi dan Fitting Pipeline
    pipeline = build_feature_pipeline(num_cols, cat_cols, temp_cols)
    transformed_train = pipeline.fit_transform(df_train)

    print("=== Training Feature Matrix Shape ===")
    print(transformed_train.shape)
    
    # Feature Names extraction
    feature_names = pipeline.named_steps["preprocessor"].get_feature_names_out()
    print("Features Generated:", feature_names)

    # 2. Serialisasi Pipeline ke Disk
    model_artifact_path = "feature_pipeline.joblib"
    joblib.dump(pipeline, model_artifact_path)
    print(f"\nPipeline tersimpan di: {model_artifact_path}")

    # 3. Simulasi Production Serving (Data Uji Baru Termasuk OOV & Outlier)
    raw_infer_data = [
        # OOV Categorical ('HarmonyOS') dan Amount di atas batas atas training
        {"transaction_id": "TX9999", "amount": 150000.0, "user_age": 30, "device_type": "HarmonyOS", "hour_of_day": 0}
    ]

    try:
        validated_infer_batch = BatchInputContract(records=[TransactionRecord(**rec) for rec in raw_infer_data])
        df_infer = validated_infer_batch.to_dataframe()

        # Load Artifact
        loaded_pipeline = joblib.load(model_artifact_path)
        transformed_infer = loaded_pipeline.transform(df_infer)

        print("\n=== Inference Feature Matrix Output ===")
        print(transformed_infer)
        print("Inference Transformasi Berhasil tanpa Training-Serving Skew.")
    except ValidationError as ve:
        print(f"Schema Violation Detected: {ve}")
    except Exception as e:
        print(f"Pipeline Runtime Error: {e}")
```

---

## 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Akar Masalah | Mekanisme Mitigasi Teknis |
| :--- | :--- | :--- |
| **Out-of-Vocabulary (OOV) Categories** | Kategori baru muncul pada runtime inference yang tidak pernah terlihat di data latih. | Atur parameter `OneHotEncoder(handle_unknown='ignore')`. Vektor yang tidak terdaftar otomatis di-encode menjadi matriks zero-vector tanpa memicu IndexError. |
| **Nilai Konstan / Zero Variance** | Kuantil atau varians fitur numerik bernilai 0 (contoh: seluruh data training bernilai 1.0), menyebabkan pembagian nol ($\frac{x - \mu}{0}$) menghasilkan `NaN` atau `inf`. | Tambahkan interceptor varians (`VarianceThreshold`) sebelum scaling atau tambahkan nilai epsilon $\epsilon = 1e-8$ pada pembagi kalkulasi scaling kustom. |
| **High Missing Rate Burst** | Fitur primer mengalami *data downtime* di hulu, menghasilkan 100% missing values dalam satu micro-batch inference. | Tambahkan layer validasi pra-pipeline yang menolak batch jika missing rate melampaui batas ambang (*drift gate*), dan sediakan imputasi berbasis *fallback static baseline* dari $D_{train}$. |
| **Schema Mismatch (Type Drift)** | Fitur numerik terkirim sebagai format string (contoh: `"100.5"` bukan `100.5`) atau order kolom berubah. | Validasi skema input wajib didelegasikan ke contract model seperti Pydantic atau pandera sebelum dieksekusi oleh pipeline Scikit-Learn. Scikit-learn bekerja berbasis indeks positional jika DataFrame dikonversi ke Numpy array. |
| **Temporal Discontinuity** | Ekstraksi fitur moving average temporal mengasumsikan data sekuensial tanpa gap. Ketika terjadi network delay, data masuk *out-of-order*. | Gunakan event-time watermark semantics alih-alih processing-time saat membuat fitur windowing berbasis waktu. |

---

## 8. Trade-offs & Alternatif Solusi

Setiap arsitektur pre-processing memiliki kompromi antara portabilitas, latensi, dan skalabilitas data:

```
                  Latensi Rendah / Komputasi Cepat
                                 ^
                                 |       [ Polars Pipeline ]
                                 |       (In-memory, Rust-based, High Throughput)
                                 |
        [ Sklearn Pipeline ]     |
        (Monolithic, Joblib,     |
         Easy Serving)           |
                                 |
<--------------------------------+--------------------------------> Volume Data
Tinggi                                                            Tinggi
(Petabyte-scale)                 |                                (Petabyte-scale)
                                 |       [ Apache Spark MLlib ]
                                 |       (Distributed, JVM overhead,
                                 |        Higher latency)
                                 |
                                 v
                 Latensi Tinggi / Latency-Tolerant
```

| Engine | Pros | Cons | Ideal Use Case |
| :--- | :--- | :--- | :--- |
| **Scikit-Learn Pipeline** | - Seamless interop dengan ekosistem model Python.<br>- State management bawaan.<br>- Serialisasi mudah. | - Terbatas pada memori single-node.<br>- Tidak optimal untuk pemrosesan paralel skala miliaran baris. | Latensi rendah inferensi real-time via API (< 20ms) dan dataset yang muat dalam RAM. |
| **Polars / DuckDB** | - Eksekusi vectorized multithreaded (Rust/C++).<br>- Konsumsi memori sangat efisien.<br>- Sangat cepat. | - Tidak memiliki abstraksi model scikit-learn bawaan (memerlukan boilerplate kustom untuk menyimpan parameter $\Theta$). | Batch feature transformation pra-training pada dataset skala menengah (10GB - 500GB). |
| **Feast / Hopsworks (Feature Store)** | - Menghilangkan Training-Serving skew secara absolut via dual-storage engine (Redis untuk online, Parquet/Snowflake untuk offline). | - Kompleksitas operasional infrastruktur tinggi.<br>- Biaya operasional tinggi. | Sistem ML enterprise dengan puluhan model yang mengonsumsi fitur bersama (*shared features*). |
| **Apache Spark (MLlib)** | - Skalabilitas horizontal tak terbatas (Petabyte scale) via cluster computing. | - Overhead startup JVM tinggi.<br>- Latensi inference per-record buruk (> 200ms). | Transformasi batch data lake raksasa di Hadoop/S3 pada pipeline nightly-batch. |

---

## 9. Best Practices & Standard Industri

1. **Prinsip Immutability Fitur**: Sekali sebuah fitur didefinisikan dan digunakan oleh model produksi v1, definisinya tidak boleh diubah secara in-place. Setiap perubahan logika transformasi wajib didefinisikan sebagai versi baru (contoh: `user_txn_cnt_v1` $\to$ `user_txn_cnt_v2`).
2. **Kompilasi Atomic Pipeline**: Jangan pisahkan modul transformator fitur dengan objek estimator model. Bungkus keduanya ke dalam objek `sklearn.pipeline.Pipeline` tunggal:
   ```python
   full_model = Pipeline([
       ('feature_engineering', preprocessor),
       ('classifier', XGBClassifier())
   ])
   ```
   Langkah ini menjamin pemanggilan `full_model.predict(X_raw)` secara otomatis mengeksekusi preprocessing identik langsung dari data mentah.
3. **Data Pre-flight Testing (Assertion Testing)**: Implementasikan unit test otomatis untuk pipeline transformasi fitur:
   - *Determinism Test*: Masukan $X$ yang sama menghasilkan $\phi(X)$ yang persis sama.
   - *Invariance Test*: Menambahkan baris dummy pada saat `.transform()` tidak boleh mengubah hasil transformasi baris lainnya.
   - *NaN-Resistance Test*: Output dari pipeline transformasi tidak boleh mengandung nilai `NaN` atau `Inf`.
4. **Hindari Direct Serialization dengan Pickle**: Format `.pkl` bawaan Python rentan terhadap arbitrary code execution vulnerability dan rawan patah jika versi library berubah. Gunakan library serialisasi aman seperti `skops` untuk export ke produksi atau simpan metadata transformasi dalam JSON/ONNX jika interoperabilitas lintas-bahasa mutlak diperlukan.

---

## 10. Hands-on Lab Exercise

### Skenario: Membangun Resilient Preprocessing Pipeline untuk Deteksi Klaim Asuransi Anomali

**Objektif:** Bangun pipeline validasi dan transformasi data untuk data klaim asuransi yang tahan terhadap *out-of-bounds inputs*, mengandung nilai *missing*, serta memiliki kombinasi data numerik, kategorikal, dan temporal.

### Langkah Pengerjaan

#### Langkah 1: Persiapkan Lingkungan
Pasang dependensi yang dibutuhkan:
```bash
pip install numpy pandas scikit-learn pydantic joblib
```

#### Langkah 2: Buat Skrip Eksperimen (`lab_pipeline.py`)
Tuliskan skrip yang mengeksekusi instruksi berikut:
1. Definisikan `InsuranceClaimRecord` menggunakan Pydantic:
   - `claim_id`: string
   - `claim_amount`: float (> 0)
   - `claim_type`: string ("HEALTH", "VEHICLE", "PROPERTY")
   - `policy_duration_months`: integer (>= 0)
   - `incident_hour`: integer (0 - 23)
2. Buat `DataframeTransformer` kustom bernama `RobustLogTransformer` yang menerapkan transformasi logaritmik $\log_e(x + 1)$ pada data numerik skewed dan menyimpan baseline rata-rata data latih.
3. Susun pipeline utama yang mengombinasikan:
   - Imputasi median pada `policy_duration_months`.
   - Log transformasi pada `claim_amount`.
   - One-hot encoding pada `claim_type` dengan mengabaikan unknown values.
   - Cyclical transformation (sin/cos) pada `incident_hour`.
4. Lakukan fasa fitting menggunakan data latih sintetis (minimal 100 baris) dan simpan artefak pipeline ke disk (`insurance_pipeline.joblib`).
5. Uji pipeline yang telah disimpan dengan data uji anomali berikut:
   ```python
   unseen_data = pd.DataFrame([{
       "claim_id": "CLM_FAIL_99",
       "claim_amount": 250000.0,
       "claim_type": "UNKNOWN_DEVICE", # Out-of-vocabulary
       "policy_duration_months": None,   # Missing Value
       "incident_hour": 3
   }])
   ```

#### Langkah 3: Verifikasi Output
Pipeline dinyatakan berhasil jika kode pengujian inferensi tidak mengalami crash dan menghasilkan sebuah matriks numpy 1 dimensi dengan nilai-nilai numerik valid (bebas dari `NaN`, `None`, atau `Inf`).

Contoh script pengujian asserting output:
```python
output_array = loaded_pipeline.transform(unseen_data)
assert not np.isnan(output_array).any(), "Assertion Failed: Output mengandung NaN!"
assert not np.isinf(output_array).any(), "Assertion Failed: Output mengandung Inf!"
print("Lab Selesai: Pipeline berhasil memproses data anomali secara valid.")
```