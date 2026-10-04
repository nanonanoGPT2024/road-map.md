# Kurikulum Enterprise Data Analyst
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB 08: Applied Machine Learning & Predictive Analytics
#### Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang & Mengimplementasikan** *pipeline* pra-pemrosesan data tingkat lanjut menggunakan `scikit-learn` *Custom Transformers* dan `ColumnTransformer` yang tahan terhadap kebocoran data (*data leakage*).
- **Membangun & Mengoptimasi** model *gradient boosted decision trees* (LightGBM/XGBoost) dengan strategi validasi temporal (*Purged/Time-series Cross-Validation*) dan *hyperparameter tuning* berbasis Bayesian Optimization (`Optuna`).
- **Mengekspor & Mengonversi** model analitik prediktif ke format standar industri (*Open Neural Network Exchange* / ONNX) untuk inferensi berlatensi rendah (< 10ms).
- **Mengarsiteksikan** sistem *serving* analitik prediktif (*Batch Inference* vs *Real-time Microservice* via FastAPI) yang terintegrasi dengan *in-memory cache*.
- **Mendeteksi & Memitigasi** *concept drift* dan *data drift* di tingkat produksi menggunakan metrik statistik *Population Stability Index* (PSI) dan uji *Kolmogorov-Smirnov* (KS-Test).

---

### 2. Prerequisite
Peserta wajib memiliki pemahaman mendalam pada materi berikut:
- **Python Lanjutan**: Pemrograman berorientasi objek (OOP), *type hints* (`typing`), *generator*, dan `dataclasses`.
- **Statistika Terapan**: Distribusi probabilitas, *hypothesis testing*, korelasi *Spearman/Pearson*, dan metrik evaluasi model (ROC-AUC, PR-AUC, Brier Score, Log-Loss).
- **SQL & Data Wrangling**: Ekstraksi fitur analitik menggunakan SQL Window Functions dan manipulasi matriks numerik via `pandas` serta `numpy`.
- **Fondasi Machine Learning**: Memahami modul fundamental (Bab 08 Module 01) mengenai regresi linier, regresi logistik, dan pohon keputusan dasar.

---

### 3. Concept & Internal Architecture

#### 3.1. Internal Engine: Algoritma Histogram-Based Gradient Boosting
Model modern seperti LightGBM mengubah pendekatan pemisahan (*splitting*) node pohon keputusan tradisional dari pengurutan terus-menerus ($O(N \times K)$) menjadi pengelompokan berbasis histogram ($O(K \times B)$), di mana $N$ adalah jumlah baris, $K$ adalah jumlah fitur, dan $B$ adalah jumlah bin (biasanya 256).

```
Nilai Kontinu Fitur: [0.12, 1.45, 0.33, 2.89, 0.05, ...]
        │
        ▼ (Binning ke UInt8: 0 - 255)
Matriks Terkuantisasi: [  12,  140,   31,  255,    5, ...]
        │
        ▼ (Histogram Aggregation: Akumulasi Gradient & Hessian)
Bin Histogram: [ Bin 0: (G0, H0) | Bin 1: (G1, H1) | ... | Bin 255: (G255, H255) ]
        │
        ▼ (Pencarian Split Optimal via Gain Formula)
Split Point Terpilih dengan Kompleksitas O(Bins)
```

Matematika *Split Gain*:
$$G_{split} = \frac{1}{2} \left[ \frac{(\sum_{i \in I_L} g_i)^2}{\sum_{i \in I_L} h_i + \lambda} + \frac{(\sum_{i \in I_R} g_i)^2}{\sum_{i \in I_R} h_i + \lambda} - \frac{(\sum_{i \in I} g_i)^2}{\sum_{i \in I} h_i + \lambda} \right] - \gamma$$
Di mana:
- $g_i = \partial_{\hat{y}^{(t-1)}} l(y_i, \hat{y}^{(t-1)})$ adalah gradient orde pertama.
- $h_i = \partial^2_{\hat{y}^{(t-1)}} l(y_i, \hat{y}^{(t-1)})$ adalah hessian orde kedua.
- $\lambda$ dan $\gamma$ adalah parameter regularisasi L2 dan penalti kompleksitas daun.

#### 3.2. Lifecycle Arsitektur Produksi Model ML
Model prediktif analitik dalam skala enterprise tidak berhenti pada file `.ipynb`. Model harus dipaketkan ke dalam artefak deterministik yang siap saji:

```
[ Data Warehouse / OLAP ]
           │ (Batch Feature Extraction)
           ▼
[ Feature Engineering Pipeline ] ─── Fit pada Train Set Saja!
           │
           ▼
[ Model Training & Tuning (Optuna) ]
           │
           ▼
[ Model Validation (Purged Temporal CV) ]
           │
           ├─ Success ──► [ Model Serialization (ONNX / Joblib) ]
           │                          │
           │                          ▼
           │             [ Model Registry (MLflow/S3) ]
           │                          │
           │                          ▼
           │             [ Inference Engine (FastAPI) ] ◄── Incoming Requests
           │                          │
           └─ Fail (Alert)            ▼
                         [ Monitoring (Drift: KS / PSI) ]
```

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc (Notebook / Skrip Lepas) | Pendekatan Enterprise Production |
| :--- | :--- | :--- |
| **Pipeline Data** | `pandas.fillna()` dan `apply()` diterapkan langsung ke seluruh dataset sebelum split train/test. | `sklearn.pipeline.Pipeline` dengan *Custom Estimators*; `fit()` eksklusif pada set pelatihan, `transform()` diterapkan pada validasi/produksi. |
| **Pencegahan Leakage** | Rentan kebocoran temporal (*look-ahead bias*) karena menggunakan random `train_test_split`. | Penerapan `TimeSeriesSplit` atau *Purged Cross-Validation* dengan jeda (*embargo window*). |
| **Format Serialisasi** | Python `pickle` (tidak aman, rentan eksekusi kode arbitrer, sangat terikat versi Python). | Format terbuka terstandardisasi seperti **ONNX** (*Open Neural Network Exchange*) atau serialisasi aman via `treelite`. |
| **Observabilitas** | Evaluasi model berhenti setelah nilai akurasi di notebook keluar. | Pemantauan terus-menerus terhadap *Covariate Shift* (fitur) dan *Concept Drift* (hubungan fitur ke target). |

---

### 5. How (Workflow Detail)

1. **Definisi Kontrak Skema**: Menentukan skema input/output data menggunakan `Pydantic` atau *schema definition tools*.
2. **Validasi & Sanitasi Data**: Validasi batas nilai numerik (*bounds*), kardinalitas kategori, dan integritas tipe data.
3. **Penyusunan Feature Pipeline**:
   - Imputasi nilai kosong berbasis strategi deterministik (Median/Mode/Model-based).
   - Pengkodean variabel kategorikal (*Target Encoding* dengan *cross-validation out-of-fold*, atau *One-Hot Encoding* untuk kardinalitas rendah).
   - Skalasi numerik (*RobustScaler* atau *StandardScaler*).
4. **Validasi Silang Temporal (Purged Group Time-Series Split)**: Memastikan tidak ada overlap temporal atau grup informasi (misal: ID pelanggan yang sama) di antara fold latih dan fold validasi.
5. **Eksplorasi Hyperparameter**: Menggunakan Bayesian Optimization via `optuna` dengan pruning trial (*MedianPruner*) untuk efisiensi komputasi.
6. **Kompilasi Model ke Runtime Teroptimasi**: Mengonversi model dari format pustaka asli ke ONNX Runtime untuk pemrosesan berbasis CPU dengan latensi sangat rendah.
7. **Deploy & Observasi**: Deploy model di balik API asinkron (`FastAPI`), melacak metrik inferensi, serta membandingkan distribusi input produksi secara periodik terhadap baseline data latih menggunakan metrik PSI.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dapur Restoran Bintang Lima vs Dapur Rumahan
- **Notebook Analyst (Dapur Rumahan)**: Anda mencicipi masakan langsung dari panci utama, memotong bahan di meja makan yang sama, dan bumbu dimasukkan secara fleksibel tanpa takaran baku. Masakan enak untuk saat itu, tetapi tidak bisa direplikasi oleh 10 koki berbeda untuk 1.000 tamu secara bersamaan.
- **Production Pipeline (Dapur Komersial Standar)**: Setiap bahan mentah masuk melalui stasiun pengecekan (*Schema Validation*), dipotong seragam di stasiun persiapan (*Preprocessing Pipeline*), diracik sesuai gramatur presisi (*Hyperparameters*), dan dimasukkan ke wadah saji steril (*Containerized API*). Setiap hidangan yang disajikan memiliki rasa, tekstur, dan suhu yang identik dalam skala ribuan porsi.

```
+---------------------------------------------------------------------------------------+
| ARSITEKTUR PIPELINE PRODUKSI                                                          |
+---------------------------------------------------------------------------------------+
  Raw Ingestion          Transformer Chain (Scikit-Learn)            Inference Engine
+----------------+      +----------------------------------+       +-------------------+
| Request JSON   | ===> | Schema Guard (Pydantic)          | ====> | ONNX Runtime      |
+----------------+      +----------------------------------+       | (Zero Python GIL) |
                        | Numeric: Impute -> RobustScale   |       +-------------------+
                        +----------------------------------+                 |
                        | Categorical: RareLabel -> Target |                 V
                        +----------------------------------+       +-------------------+
                                                                   | Output Prediction |
                                                                   +-------------------+
                                                                             │
    Background Task / Async Buffer                                           ▼
+---------------------------------------------------------------------------------------+
| Observability Layer: Drift Engine (Evidently / Custom PSI Calculator)                 |
| Baseline Dist <---[ Kolmogorov-Smirnov / PSI ]---> Production Stream Dist             |
+---------------------------------------------------------------------------------------+
```

---

### 7. Code Implementation

#### 7.1. Simple Example: Custom Transformer & Leak-Free Preprocessing Pipeline
Contoh pembuatan komponen pra-pemrosesan mandiri yang mengikuti protokol Scikit-Learn (*BaseEstimator*, *TransformerMixin*) untuk mencegah kebocoran data.

```python
import numpy as np
import pandas as pd
from typing import List, Optional
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

class OutlierCapper(BaseEstimator, TransformerMixin):
    """
    Membatasi (clipping) nilai pencilan berdasarkan rentang interkuartil (IQR).
    Statistik IQR HANYA dihitung saat pipeline memanggil .fit().
    """
    def __init__(self, factor: float = 1.5) -> None:
        self.factor: float = factor
        self.lower_bounds_: dict[str, float] = {}
        self.upper_bounds_: dict[str, float] = {}

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "OutlierCapper":
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        for col in X.columns:
            q25 = X[col].quantile(0.25)
            q75 = X[col].quantile(0.75)
            iqr = q75 - q25
            self.lower_bounds_[col] = q25 - (self.factor * iqr)
            self.upper_bounds_[col] = q75 + (self.factor * iqr)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        X_out = X.copy()
        for col in self.lower_bounds_:
            if col in X_out.columns:
                X_out[col] = X_out[col].clip(
                    lower=self.lower_bounds_[col], 
                    upper=self.upper_bounds_[col]
                )
        return X_out

# Contoh Penggunaan Pipeline
data_raw = pd.DataFrame({
    'age': [25, 30, 45, 120, 22, np.nan, 35],
    'income': [5000, 7000, 15000, 200000, 4500, 8000, 9200]
})

numeric_features = ['age', 'income']
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('capper', OutlierCapper(factor=1.5)),
    ('scaler', StandardScaler())
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features)
    ]
)

# Fit hanya pada data
preprocessed_array = preprocessor.fit_transform(data_raw)
print("Pipeline Transformation Sukses. Bentuk Output:", preprocessed_array.shape)
```

#### 7.2. Practical Example: Enterprise Training, ONNX Export & Drift Monitor
Contoh komprehensif: Pelatihan model `LightGBM`, konversi ke runtime `ONNX`, kalkulasi metrik stabilitas populasi (*Population Stability Index* / PSI), dan serving asinkron via `FastAPI`.

```python
import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from scipy import stats
import lightgbm as lgb
import onnxruntime as ort
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# =====================================================================
# 1. ARSITEKTUR DETEKSI DRIFT (STATISTICAL MODULE)
# =====================================================================
class ProductionDriftMonitor:
    """
    Menghitung stabilitas populasi (PSI) dan uji KS 2-sampel
    antara baseline pelatihan dan inference saat produksi.
    """
    @staticmethod
    def calculate_psi(baseline: np.ndarray, target: np.ndarray, bins: int = 10) -> float:
        """
        Rumus PSI: SUM( (Actual% - Expected%) * ln(Actual% / Expected%) )
        Rule of Thumb:
          PSI < 0.1: Tidak ada perubahan signifikan (Stabil)
          0.1 <= PSI < 0.2: Terjadi pergeseran moderat (Perlu investigasi)
          PSI >= 0.2: Pergeseran signifikan (Retrain Model)
        """
        quantiles = np.linspace(0, 100, bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] -= 1e-5
        bin_edges[-1] += 1e-5

        baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
        target_counts, _ = np.histogram(target, bins=bin_edges)

        # Normalisasi ke probabilitas dengan epsilon agar terhindar dari division by zero
        eps = 1e-4
        b_perc = (baseline_counts / len(baseline)) + eps
        t_perc = (target_counts / len(target)) + eps

        psi_value = np.sum((t_perc - b_perc) * np.log(t_perc / b_perc))
        return float(psi_value)

    @staticmethod
    def calculate_ks_statistic(baseline: np.ndarray, target: np.ndarray) -> Tuple[float, float]:
        statistic, p_value = stats.ks_2samp(baseline, target)
        return float(statistic), float(p_value)

# =====================================================================
# 2. MODEL ENGINE & EXPORT KE ONNX
# =====================================================================
def train_and_export_onnx(model_path: str = "model.onnx") -> None:
    np.random.seed(42)
    N = 5000
    # Simulasi data: X1 (fitur numerik), X2 (fitur risiko)
    X = np.random.randn(N, 4).astype(np.float32)
    # Target probabilistik
    logits = 0.8 * X[:, 0] - 1.2 * X[:, 1] + 0.5 * X[:, 2]
    prob = 1 / (1 + np.exp(-logits))
    y = (prob > 0.5).astype(np.int32)

    train_data = lgb.Dataset(X, label=y)
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'verbose': -1
    }
    booster = lgb.train(params, train_data, num_boost_round=100)

    # Konversi ke format ONNX
    initial_type = [('float_input', FloatTensorType([None, 4]))]
    onnx_model = onnxmltools.convert_lightgbm(booster, initial_types=initial_type, target_opset=12)
    with open(model_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"Model berhasil diekspor ke format ONNX: {model_path}")

# =====================================================================
# 3. PRODUCTION INFERENCE ENGINE (FASTAPI + ONNX RUNTIME)
# =====================================================================
class CustomerFeatures(BaseModel):
    feature_1: float = Field(..., description="Fitur transaksi normalisasi")
    feature_2: float = Field(..., description="Tingkat rasio utang")
    feature_3: float = Field(..., description="Skor riwayat kredit")
    feature_4: float = Field(..., description="Varians frekuensi login")

class PredictionResponse(BaseModel):
    churn_probability: float
    is_high_risk: bool
    inference_engine: str

app = FastAPI(title="Enterprise Predictive Inference API", version="1.0.0")

class InferenceService:
    def __init__(self, onnx_model_path: str):
        if not os.path.exists(onnx_model_path):
            train_and_export_onnx(onnx_model_path)
        self.session = ort.InferenceSession(onnx_model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, features: np.ndarray) -> float:
        # Eksekusi kalkulasi di C++ Core via ONNX Runtime
        raw_outputs = self.session.run(None, {self.input_name: features})
        # LightGBM ONNX menghasilkan list: [labels, probabilities_map]
        probabilities = raw_outputs[1]
        if isinstance(probabilities, list):
            # Format parsing output dictionary ONNX
            churn_prob = probabilities[0][1]
        else:
            churn_prob = probabilities[0, 1]
        return float(churn_prob)

# Singleton Pattern untuk Inference Service
engine: InferenceService = None

@app.on_event("startup")
def init_engine():
    global engine
    engine = InferenceService(onnx_model_path="model.onnx")

@app.post("/v1/predict", response_model=PredictionResponse)
async def predict_churn(payload: CustomerFeatures):
    try:
        data_vector = np.array([[
            payload.feature_1,
            payload.feature_2,
            payload.feature_3,
            payload.feature_4
        ]], dtype=np.float32)

        probability = engine.predict(data_vector)
        return PredictionResponse(
            churn_probability=probability,
            is_high_risk=probability >= 0.65,
            inference_engine="ONNXRuntime-CPU"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference failure: {str(e)}")

if __name__ == "__main__":
    # Test validasi mandiri kalkulasi Drift
    baseline_sample = np.random.normal(0, 1, 1000)
    drifted_sample = np.random.normal(0.5, 1.2, 1000)
    psi = ProductionDriftMonitor.calculate_psi(baseline_sample, drifted_sample)
    ks_stat, p_val = ProductionDriftMonitor.calculate_ks_statistic(baseline_sample, drifted_sample)
    print(f"Hasil Uji Validasi Drift: PSI = {psi:.4f} | KS-Statistic = {ks_stat:.4f} (p-value: {p_val:.4e})")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
- **Instansi**: Platform Digital Banking Tier-1.
- **Kasus**: *Real-time Credit Card Fraud Detection* & *Early Default Warning*.
- **Volume Transaksi**: 55 juta transaksi per hari dengan beban puncak 4.500 transaksi per detik (TPS).
- **SLA Layanan**: P99 Latensi inferensi < 15ms.

#### Masalah Arsitektural Awal
Awalnya, tim analitik membangun model menggunakan notebook Python berbasis XGBoost, kemudian membungkus model mentah (`pickle`) di dalam API Flask standar. Masalah kritis muncul:
1. **Python Global Interpreter Lock (GIL)**: API terkunci saat permintaan melonjak, menyebabkan P99 latensi membengkak ke 450ms.
2. **Data Leakage & Skew**: Imputasi data hilang dilakukan dengan rata-rata keseluruhan tabel di BigQuery sebelum split temporal, membuat performa validasi di notebook luar biasa (AUC 0.94), tetapi saat diterapkan di produksi hancur ke AUC 0.68.
3. **Silent Drift**: Ketika terjadi perubahan pola transaksi saat musim liburan (pergeseran nilai transaksi rata-rata), tidak ada sistem deteksi pergeseran fitur. Transaksi fraud lolos hingga menyebabkan kerugian Rp 4,2 Miliar dalam 72 jam.

#### Solusi yang Diimplementasikan
1. **Pemisahan Validasi Ketat**: Mengadopsi `PurgedGroupTimeSeriesSplit` dengan jeda 48 jam antar fold untuk mencegah kebocoran temporal akibat transaksi tertunda (*settlement delay*).
2. **Kompilasi Model**: Menghapus `pickle` dan mengonversi seluruh pipeline LightGBM ke format **ONNX Runtime (C++ backend)**. Model dikompilasi ke representasi graph yang dioptimalkan untuk thread CPU paralel.
3. **Observabilitas Data & Model**:
   - Memasang layer *Background Worker* via Redis Queue yang mengumpulkan sampel 5% dari semua input transaksi.
   - Menjalankan cron job per jam untuk menghitung metrik **PSI** per fitur dan uji **Kolmogorov-Smirnov**. Jika $PSI \ge 0.2$ pada 3 fitur kunci, pipeline CI/CD memicu retrain otomatis dan memberikan notifikasi ke kanal tim analitik.

#### Hasil Terukur
- Latensi P99 terpangkas dari **450ms ke 7.2ms**.
- Kapasitas *throughput* mesin inferensi meningkat **8.5x** lipat pada alokasi infrastruktur CPU yang sama.
- Kerugian fraud berhasil ditekan sebesar 43% dalam kuartal pertama berkat sistem peringatan dini *drift*.

---

### 9. Trade-offs & Production Considerations

| Pendekatan / Keputusan Arsitektur | Keuntungan | Kerugian & Konsekuensi | Skenario Pemilihan |
| :--- | :--- | :--- | :--- |
| **Real-time REST Inference (FastAPI + ONNX)** | Prediksi langsung berbasis data transaksi detik ini juga (*zero-latency business decision*). | Beban infrastruktur komputasi 24/7, biaya server lebih tinggi, kompleksitas arsitektur microservice. | Fraud detection, scoring transaksi kartu kredit, otorisasi pembayaran langsung. |
| **Batch Inference (Cron / Apache Airflow)** | Sangat hemat biaya, komputasi terdistribusi (Spark/BigQuery ML), throughput masif per siklus. | Data prediksi memiliki *staleness* (ketinggalan zaman), tidak dapat merespons perubahan perilaku pelanggan instan. | Prediksi churn mingguan pelanggan, propensity-to-buy bulanan, kalkulasi batas kredit berkala. |
| **Penyimpanan Fitur: Low-Latency Feature Store (Feast/Redis)** | Mencegah inkonsistensi kalkulasi fitur antara tahap pelatihan dan serving (*training-serving skew*). | Kompleksitas operasional pemeliharaan sinkronisasi antara *offline store* (Parquet/Snowflake) dan *online store* (Redis). | Sistem dengan ratusan fitur dinamis yang diakses oleh beragam model berbeda. |
| **Model Tree Ensembles vs Deep Learning** | Inferensi super cepat pada data tabular, mudah diinterpretasikan via SHAP values, efisien memori. | Sulit memproses data multi-modal (teks bebas, audio, citra dokumen) secara native. | Masalah prediksi data tabular tabular analitik perbankan/e-commerce standar. |

---

### 10. Common Mistakes & Troubleshooting Guide

#### Mistake 1: Target Leakage Melalui Pra-pemrosesan Data Global
- **Gejala**: Skor metrik ROC-AUC di validasi mencapai 0.98, namun saat model live di server skor anjlok ke 0.55.
- **Akar Masalah**: Melakukan normalisasi, standarisasi, imputasi, atau pemilihan fitur (*feature selection*) pada seluruh matriks dataset sebelum memisahkan set latih (*train*) dan set uji (*test*). Nilai mean/median target atau fitur masa depan bocor ke data latih.
- **Solusi**: Bungkus semua proses ke dalam `sklearn.pipeline.Pipeline`. Eksekusi `.fit()` hanya pada `X_train`, lalu panggil `.transform()` pada `X_val` atau `X_test`.

#### Mistake 2: Serialisasi Model Menggunakan Python `pickle` Mentah
- **Gejala**: Server inferensi mengalami error `AttributeError: Can't get attribute 'CustomTransformer'` saat versi dependencies di-upgrade, atau timbul celah keamanan Remote Code Execution (RCE).
- **Akar Masalah**: File `.pkl` menyimpan referensi kode Python dan pointer lingkungan eksekusi secara absolut, bukan definisi komputasi murni.
- **Solusi**: Standardisasi serialisasi menggunakan Open Neural Network Exchange (`ONNX`) atau format biner model spesifik yang stabil (*Booster save_model* native di LightGBM/XGBoost).

#### Mistake 3: Kegagalan Menangani Silent Categorical Shift
- **Gejala**: Prediksi menghasilkan galat runtime atau memetakan kategori baru ke nilai nol secara diam-diam sehingga menurunkan akurasi model.
- **Akar Masalah**: Kategori baru muncul di lingkungan produksi yang belum pernah ada saat model dilatih (misal: penambahan metode pembayaran baru `QRIS_TRANSFER`).
- **Solusi**:
  1. Terapkan pemetaan kategori langka (*rare label encoding*) saat training (kategori dengan frekuensi < 1% digabung menjadi `'OTHER'`).
  2. Pasang parameter `handle_unknown='use_encoded_value', unknown_value=-1` pada `OrdinalEncoder` atau imputasi nilai default pada pipeline.

---

### 11. Best Practices (Production Checklist)

- [ ] **Data Partitioning**: Hindari random splitting pada data dengan dimensi waktu; gunakan `TimeSeriesSplit` atau *Purged Cross-Validation*.
- [ ] **Strict Typing & Schema Contract**: Gunakan `pydantic` untuk validasi setiap request payload yang masuk ke API model inferensi.
- [ ] **Encapsulated Preprocessors**: Tidak ada manipulasi fitur lepas di skrip training. Semua langkah transformasi harus berada di dalam objek `Pipeline` atau `ColumnTransformer`.
- [ ] **Inference Latency Optimization**: Ekspor model ke runtime teroptimasi non-Python (seperti ONNX Runtime).
- [ ] **Reproducibility**: Kunci semua seed pseudo-random number generator (`numpy.random.seed`, LightGBM `seed`).
- [ ] **Drift Detection Hooks**: Siapkan job terjadwal untuk menghitung metrik PSI dan KS-test pada fitur-fitur berbobot tinggi (*top feature importances*).
- [ ] **Graceful Degradation / Fallback Strategy**: Sediakan aturan bisnis heuristik (*rule-based fallback*) jika inference engine mengalami crash atau timeout (> 50ms).
- [ ] **Interpretability Budget**: Jika sistem membutuhkan output SHAP untuk regulasi (misal: alasan penolakan pinjaman), gunakan `TreeSHAP` teroptimasi C++ dan batasi komputasi interaksi fitur.

---

### 12. Hands-on Practice

Buat struktur folder berikut di repositori lokal Anda:
```text
hands-on/
└── m02/
    ├── pipeline_engine.py
    ├── export_onnx.py
    ├── app_server.py
    └── drift_tester.py
```

#### Langkah 1: Implementasi Pipeline & Model Training (`hands-on/m02/pipeline_engine.py`)
Tulis skrip yang memproses data kredit, membuat pipeline bebas kebocoran, melatih LightGBM Classifier, dan menyimpan booster native.
```python
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb

def generate_mock_data():
    np.random.seed(42)
    n = 2000
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2023-01-01', periods=n, freq='H'),
        'feature_num1': np.random.exponential(scale=2.0, size=n),
        'feature_num2': np.random.normal(loc=50, scale=15, size=n),
        'label': np.random.choice([0, 1], size=n, p=[0.8, 0.2])
    })
    return df.sort_values('timestamp').reset_index(drop=True)

if __name__ == "__main__":
    df = generate_mock_data()
    X = df[['feature_num1', 'feature_num2']]
    y = df['label']

    # Cross validation temporal
    tscv = TimeSeriesSplit(n_splits=3)
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
        X_va, y_va = X.iloc[val_idx], y.iloc[val_idx]
        print(f"Fold {fold} | Train bounds: {train_idx.min()} - {train_idx.max()} | Val bounds: {val_idx.min()} - {val_idx.max()}")

    # Fit final pipeline
    num_pipe = Pipeline([
        ('impute', SimpleImputer(strategy='mean')),
        ('scale', StandardScaler())
    ])
    X_processed = num_pipe.fit_transform(X)

    train_data = lgb.Dataset(X_processed, label=y)
    booster = lgb.train({'objective': 'binary', 'verbose': -1}, train_data, num_boost_round=50)
    booster.save_model("hands-on/m02/lgbm_native.txt")
    print("Model native LightGBM berhasil disimpan.")
```

#### Langkah 2: Ekspor ke ONNX (`hands-on/m02/export_onnx.py`)
Jalankan konversi model native menjadi representasi ONNX biner.
```python
import lightgbm as lgb
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType

booster = lgb.Booster(model_file="hands-on/m02/lgbm_native.txt")
initial_type = [('input', FloatTensorType([None, 2]))]
onnx_model = onnxmltools.convert_lightgbm(booster, initial_types=initial_type, target_opset=12)

with open("hands-on/m02/model.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())
print("Model ONNX berhasil digenerate di hands-on/m02/model.onnx")
```

#### Langkah 3: Uji Stabilitas Populasi (`hands-on/m02/drift_tester.py`)
Buat script validator untuk membandingkan baseline data latih terhadap data inferensi baru yang sengaja digeser (*skewed*).
```python
import numpy as np

def calculate_psi(baseline: np.ndarray, target: np.ndarray, bins: int = 10) -> float:
    quantiles = np.linspace(0, 100, bins + 1)
    bin_edges = np.percentile(baseline, quantiles)
    bin_edges[0] -= 1e-5
    bin_edges[-1] += 1e-5

    baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
    target_counts, _ = np.histogram(target, bins=bin_edges)

    eps = 1e-4
    b_perc = (baseline_counts / len(baseline)) + eps
    t_perc = (target_counts / len(target)) + eps

    return float(np.sum((t_perc - b_perc) * np.log(t_perc / b_perc)))

if __name__ == "__main__":
    baseline = np.random.normal(50, 15, 5000)
    # Simulasi data produksi mengalami drift (distribusi bergeser rata-ratanya ke 65)
    prod_stream = np.random.normal(65, 15, 2000)

    psi_score = calculate_psi(baseline, prod_stream)
    print(f"Hasil Evaluasi PSI: {psi_score:.4f}")
    if psi_score >= 0.2:
        print("[CRITICAL ALERT] Terjadi pergeseran populasi signifikan! Pemicu retrain otomatis diaktifkan.")
    else:
        print("[INFO] Distribusi data stabil.")
```

---

### 13. Exercise

#### Level 1 - Easy
Modifikasi class `OutlierCapper` dari Seksi 7.1 agar mendukung pembatasan nilai (*capping*) berbasis **Persentil Statis** (misal persentil 1% terbawah dan 99% teratas) sebagai alternatif dari metode IQR.
- *Kriteria Evaluasi*: Class harus memiliki parameter inisialisasi `percentile_lower` dan `percentile_upper`, mengimplementasikan interface `fit` dan `transform`, serta mengembalikan pandas DataFrame secara utuh tanpa membocorkan data evaluasi ke data training.

#### Level 2 - Medium
Buat skrip validasi silang kustom `PurgedGroupTimeSeriesSplit` menggunakan Python generator.
- *Spesifikasi*:
  1. Menerima DataFrame dengan kolom `datetime` dan kolom `group_id` (misal ID pelanggan).
  2. Memastikan seluruh observasi dari `group_id` yang sama hanya boleh berada di fold Train ATAU fold Validation, tidak boleh terbagi di keduanya.
  3. Menerapkan jeda waktu (*embargo duration*) sepanjang 24 jam antara titik data terakhir di fold Train dan titik data pertama di fold Validation untuk mencegah auto-korelasi time-lag.

#### Level 3 - Hard
Rancang modul Python asinkron yang melakukan *buffering* request inferensi ke dalam memori secara dinamis (*Dynamic Batching*).
- *Spesifikasi*:
  1. API mengumpulkan request inferensi individual yang masuk via FastAPI.
  2. Jika jumlah buffer mencapai `max_batch_size=64` ATAU waktu tunggu mencapai `max_latency_ms=10ms`, jalankan batch inference secara simultan ke session `ONNX Runtime`.
  3. Kembalikan hasil prediksi individual ke tiap-tiap caller HTTP secara asinkron tanpa menahan (*blocking*) event loop API.

---

### 14. Challenge

**Skenario Sistem Prediksi Churn Multi-Tenant dengan Perubahan Distribusi Cepat (Non-Stationary Data)**:
Anda adalah Staff Data Architect di platform SaaS B2B dengan 200 klien enterprise. Setiap klien memiliki pola siklus penggunaan platform yang sangat bervariasi.
- **Tantangan Arsitektur**:
  1. **Volume & Heterogenitas**: Anda dilarang melatih 200 model terpisah karena batasan memori kluster, tetapi model global tunggal mengalami penurunan performa drastis akibat perbedaan varians fitur antar industri klien (*heteroscedasticity*).
  2. **Streaming Drift**: Model sering mengalami false alarm drift karena klien tertentu menjalankan program promosi musiman mereka sendiri, yang mengacaukan statistik agregat KS-test global.
- **Tugas Arsitektural Anda**:
  - Tuliskan dokumen spesifikasi arsitektur teknis yang menjelaskan:
    1. Desain skema normalisasi fitur hierarkis (*Hierarchical Conditioning Pipeline*) agar model global dapat beradaptasi terhadap deviasi baseline level klien.
    2. Algoritma deteksi drift berbasis pembobotan tenant (*Tenant-Weighted Population Stability Index*), sehingga anomali dari 1 klien besar tidak memicu false alarm retrain pada keseluruhan model global.
    3. Strategi *Zero-Downtime Hot Swapping* artefak model ONNX pada kluster produksi ketika retrain selesai dijalankan.

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic (5 Soal)
1. **Mengapa pemanggilan fungsi `StandardScaler.fit_transform()` langsung pada seluruh dataset sebelum data train/test dipecah dianggap sebagai kesalahan fatal (*critical bug*)?**
   - *Jawaban*: Tindakan tersebut menyebabkan *Data Leakage* (kebocoran informasi). Nilai mean dan standar deviasi dari data uji/masa depan telah bocor ke dalam data latih, menyebabkan estimasi performa model menjadi over-optimistik dan gagal di produksi.
2. **Apa perbedaan mendasar antara pembentukan pohon keputusan tradisional dengan pendekatan *Histogram-based* pada LightGBM?**
   - *Jawaban*: Pohon tradisional mengurutkan semua nilai fitur kontinu secara berulang ($O(N \times K)$), sedangkan LightGBM mengelompokkan nilai kontinu ke dalam *discrete bins* (histogram, biasanya 256 bin) sehingga kompleksitas pencarian split berkurang drastis menjadi $O(Bins \times K)$.
3. **Apa keuntungan format serialisasi ONNX dibandingkan Python `pickle`?**
   - *Jawaban*: ONNX bersifat independen dari platform dan bahasa (dapat dijalankan di runtime C++, C#, Java, JavaScript), lebih aman dari celah eksekusi kode berbahaya, serta menghasilkan latensi inferensi yang jauh lebih rendah tanpa hambatan Python GIL.
4. **Metrik apa yang paling cocok untuk mengevaluasi dataset dengan ketimpangan kelas target ekstrem (misal fraud 0.01%)?**
   - *Jawaban*: *Precision-Recall AUC (PR-AUC)* atau *Average Precision*. ROC-AUC memberikan representasi over-optimistik pada dataset yang sangat timpang karena dipengaruhi oleh dominasi true negative.
5. **Berapa ambang batas (*threshold*) nilai Population Stability Index (PSI) yang umumnya menandakan bahwa model telah mengalami pergeseran populasi signifikan dan memerlukan retraining?**
   - *Jawaban*: Nilai $PSI \ge 0.2$.

#### Pertanyaan Intermediate (5 Soal)
6. **Dalam konteks data time-series analitik, apa yang dimaksud dengan *Look-Ahead Bias* dan bagaimana cara mencegahnya saat feature engineering?**
   - *Jawaban*: Look-ahead bias terjadi ketika fitur dihitung menggunakan informasi yang belum tersedia pada saat kejadian (*timestamp* prediksi). Pencegahannya adalah dengan memastikan window agregasi hanya bergerak ke masa lalu (*historical rolling window* dengan closed/right boundary yang ketat) dan menggunakan `TimeSeriesSplit`.
7. **Bagaimana cara kerja uji statistik Kolmogorov-Smirnov (KS-test) dalam mendeteksi data drift?**
   - *Jawaban*: Uji KS membandingkan dua fungsi distribusi kumulatif empiris (*Cumulative Distribution Function* - CDF) antara baseline data latih dan data produksi. Nilai statistik KS merepresentasikan jarak vertikal absolut terjauh antara kedua kurva CDF tersebut.
8. **Jelaskan perbedaan mendasar antara *Data Drift* (Covariate Shift) dan *Concept Drift*!**
   - *Jawaban*: *Data Drift* terjadi ketika distribusi fitur input $P(X)$ berubah tanpa mengubah hubungan probabilitas bersyaratnya dengan target $P(Y|X)$. *Concept Drift* terjadi ketika hubungan statistik antara input dan target $P(Y|X)$ berubah, meskipun distribusi input $P(X)$ tetap sama.
9. **Mengapa pengkodean kategori frekuensi tinggi (*High-Cardinality Target Encoding*) harus menggunakan teknik *Out-of-Fold* (OOF)?**
   - *Jawaban*: Jika target encoding dihitung langsung pada seluruh data latih, nilai rata-rata target per kategori akan merepresentasikan label baris itu sendiri secara berlebihan, memicu overfitting ekstrem. OOF memastikan nilai encoding suatu baris hanya dihitung dari subset data fold yang lain.
10. **Apa implikasi performa dari penggunaan library `scikit-learn` secara langsung di dalam jalur kritis (*critical path*) aplikasi inference berlatensi < 5ms?**
    - *Jawaban*: Overhead internal objek Python, alokasi memori berulang pada `numpy array wrapper`, serta pembatasan multi-threading akibat Python GIL dapat menimbulkan latensi P99 yang tinggi dan tidak stabil di bawah beban konkurensi tinggi.

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario 1**: Tim Anda merilis model deteksi churn e-commerce. Dua minggu setelah rilis, metrik akurasi turun 30%. Hasil kalkulasi drift menunjukkan nilai PSI pada fitur `total_spend_last_30d` melonjak ke angka 0.42. Setelah diperiksa, ternyata tim marketing mengubah mata uang transaksi dari IDR ke USD untuk merchant internasional tertentu. Bagaimana Anda mengarsiteksikan solusi pipeline yang tahan terhadap masalah ini ke depannya?
    - *Solusi & Analisis*: 
      1. Terapkan *Data Contract* dan *Schema Validation* di gerbang ingest menggunakan `pydantic` yang mewajibkan normalisasi mata uang (*currency conversion layer*) ke basis acuan (misal IDR) sebelum data masuk ke transformer fitur.
      2. Pasang sistem *Dynamic Unit Testing* pada data masuk yang memverifikasi batas nilai (*boundary checks*). Jika nilai median turun secara drastis dalam skala order of magnitude yang aneh, request dialihkan ke *fallback rule engine* dan tim data analyst otomatis menerima notifikasi anomali ingest.
12. **Skenario 2**: Anda menyajikan model menggunakan FastAPI dan ONNX Runtime di Kubernetes. Saat stress-testing pada 2.000 TPS, penggunaan CPU mencapai 100% dan latensi P99 meningkat menjadi 800ms. Namun, memori sistem (RAM) hanya terpakai 15%. Tindakan engineering apa yang harus diambil untuk menurunkan latensi kembali ke < 15ms tanpa menambah node server baru?
    - *Solusi & Analisis*:
      1. Konfigurasikan thread pooling internal ONNX Runtime: atur `intra_op_num_threads` dan `inter_op_num_threads` agar sesuai dengan vCPU fisik per pod guna menghindari perebutan context-switch berlebihan.
      2. Jalankan FastAPI menggunakan worker multi-process berbasis Gunicorn/Uvicorn (`uvicorn workers`) dengan jumlah worker $N = (2 \times \text{vCPU}) + 1$.
      3. Matikan alokasi array baru yang berulang dengan mengimplementasikan mekanisme *buffer pooling* di memori untuk payload matriks inferensi.
13. **Skenario 3**: Sebuah bank menerapkan model skor kelayakan pinjaman otomatis. Auditor kepatuhan (compliance) menuntut bahwa setiap keputusan penolakan harus menyertakan 3 faktor fitur dominan penyebab penolakan dalam waktu < 20ms saat nasabah mengajukan via aplikasi mobile. Bagaimana Anda merancang arsitektur serving model yang memenuhi kebutuhan explainability ini tanpa melanggar batasan SLA latensi?
    - *Solusi & Analisis*:
      1. Model native LightGBM/XGBoost dikompilasi menggunakan C-API atau TreeSHAP C++ runtime (bukan library SHAP standard Python yang lambat). Algoritma TreeSHAP memiliki kompleksitas $O(TLD^2)$, yang untuk pohon kedalaman moderat ($D \le 6$) mampu menghitung kontribusi nilai SHAP dalam waktu < 5ms.
      2. Jangan hitung nilai SHAP penuh untuk seluruh fitur. Hitung pohon secara selektif atau jalankan kalkulasi SHAP background worker yang langsung di-push melalui WebSocket/Push Notification ke nasabah dalam jeda waktu 1 detik setelah keputusan skor awal keluar secara instan via API ONNX.

---

### 16. Summary
Transisi dari analitik prediktif tahap eksperimen (*notebook-centric*) menuju sistem analitik produksi (*system-centric*) membutuhkan pemahaman komprehensif mengenai **integritas komputasi, stabilitas temporal, dan efisiensi runtime**:

1. **Pencegahan Data Leakage**: Seluruh transformasi fitur harus dienkapsulasi secara ketat di dalam objek `Pipeline` dan `ColumnTransformer`, di mana kalkulasi parameter statistik eksklusif dipelajari (*fit*) hanya dari data training.
2. **Validasi Berbasis Waktu**: Evaluasi model tabular prediktif harus merefleksikan realitas operasional bisnis dengan menggunakan *Purged Group Time-Series Validation* guna mencegah kebocoran informasi masa depan ke masa lalu.
3. **Standardisasi Inferensi**: Memisahkan logika machine learning dari ekosistem Python runtime dengan mengekspor model ke standard terbuka seperti **ONNX** secara signifikan memangkas latensi eksekusi (P99 < 10ms) dan menjamin determinisme hasil inferensi.
4. **Siklus Hidup Pasca-Rilis**: Model di produksi adalah aset dinamis yang terus terdegradasi. Membangun sistem observabilitas independen berbasis uji statistik kuantitatif (**PSI & KS-Test**) merupakan pilar fundamental guna mendeteksi *covariate shift* dan memicu retraining secara proaktif sebelum model merugikan metrik finansial enterprise.