# Kurikulum Enterprise: Pemrograman Python Tingkat Lanjut untuk Analisis Data
## Bab 08: Pemodelan Statistik Inferensial & Machine Learning Terapan
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   Membangun pipeline machine learning enterprise-grade menggunakan `scikit-learn` dengan implementasi custom transformers yang mematuhi kontrak API `BaseEstimator` dan `TransformerMixin` secara deterministik.
*   Mengeliminasi risiko *data leakage* struktural (temporal leakage, group leakage, dan preprocessing leakage) dalam arsitektur validasi model menggunakan strategi cross-validation tingkat lanjut.
*   Menganalisis dan mengoptimalkan performa komputasi pipeline scikit-learn melalui manajemen memori `joblib`, parallel backends (`loky`), dan *zero-copy memory mapping*.
*   Merancang arsitektur deployment inferensi berlatensi rendah (< 15ms p99) dengan serialisasi model modern (`ONNX` dan `skops`), menggantikan format `pickle` yang rentan terhadap eksekusi kode arbitrer.
*   Mengimplementasikan subsistem pemantauan model post-deployment mencakup *Population Stability Index* (PSI) dan uji dua sampel non-parametrik (Kolmogorov-Smirnov) untuk mendeteksi *feature drift* dan *concept drift* secara otomatis.

---

### 2. Prerequisite
*   Pemahaman mendalam tentang OOP Python: Inheritance, Dunder Methods (`__init__`, `__call__`), Type Hinting (`typing`), dan Metaclasses.
*   Kecakapan manipulasi struktur data berkinerja tinggi menggunakan NumPy (`ndarray` strides, memory layouts C- vs Fortran-contiguous) dan Pandas.
*   Penguasaan teori probabilitas dan statistik inferensial: Central Limit Theorem, Hypothesis Testing ($p$-value, Type I & II errors), OLS Regression, dan Teorema Bayes.
*   Pemahaman Modul 01: Fondasi Estimator Scikit-Learn, Metrik Evaluasi (ROC-AUC, PR-AUC, Brier Score), dan Logika Regularisasi ($L_1$/$L_2$).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. Scikit-Learn Estimator & Transformer Internal Lifecycle
Scikit-learn beroperasi di atas kontrak antarmuka (*duck typing*) yang ketat. Seluruh state hasil komputasi (*learned parameters*) dipisahkan dari konfigurasi awal (*hyperparameters*):
1.  **Instansiasi**: `__init__` hanya boleh menerima parameter eksplisit tanpa modifikasi nilai. Tidak boleh menerima atau memproses data $X$ atau $y$. Tidak boleh melakukan validasi data di dalam `__init__`.
2.  **Fitting**: Metode `fit(X, y)` menerima data pelatihan, memvalidasi integritas dimensi menggunakan `check_array()` atau `check_X_y()`, menghitung statistik data, lalu menyimpan parameter terestimasi dengan konvensi *trailing underscore* (misal: `mean_`, `scale_`, `components_`). Metode ini harus selalu mengembalikan referensi `self` untuk memungkinkan *fluent interface pattern*.
3.  **Transformasi / Inferensi**: Metode `transform(X)` atau `predict(X)` menggunakan learned parameters yang telah terkunci untuk memproses data baru. Operasi ini harus bersifat *stateless* terhadap learned parameters; pemanggilan berulang pada data yang sama harus menghasilkan output deterministik tanpa memodifikasi atribut internal.

```
+------------------------------------------------------------------------------------+
|                               SCIKIT-LEARN OBJECT LIFECYCLE                         |
+------------------------------------------------------------------------------------+
|                                                                                    |
|   1. Instantiation: estimator = CustomTransformer(param1=alpha, param2=beta)       |
|      (No data validation, no internal compute, only assign hyperparams to self)   |
|                                                                                    |
|   2. fit(X, y):                                                                    |
|      +---------------------+      +---------------------+      +---------------+   |
|      | check_X_y(X, y)     | ---> | Compute Statistics  | ---> | Store params  |   |
|      | (dtype, shape, NaN) |      | (e.g. Mean, StdDev) |      | self.mean_    |   |
|      +---------------------+      +---------------------+      +---------------+   |
|                                                                        |           |
|                                                              Return    v           |
|                                                                   self             |
|                                                                                    |
|   3. transform(X) / predict(X):                                                    |
|      +---------------------+      +---------------------+      +---------------+   |
|      | check_array(X)      | ---> | Apply self.mean_    | ---> | Return        |   |
|      | (dim, schema check) |      | (Zero state mut.)   |      | Transformed   |   |
|      +---------------------+      +---------------------+      +---------------+   |
+------------------------------------------------------------------------------------+
```

#### B. Pipeline Memory Footprint & Joblib Parallelism
Secara default, Pipeline scikit-learn meneruskan output transformasi antar-tahap secara in-memory. Jika pipeline terdiri dari 5 tahapan transformer dan dataset awal berukuran 4 GB, akumulasi memory footprint sementara dapat melonjak hingga >20 GB jika terjadi defensive copying (`copy=True`).

Untuk optimasi komputasi multithread/multiprocess, scikit-learn memanfaatkan `joblib`. Arsitektur paralelisme `joblib` beroperasi melalui:
*   **Loky Backend**: Menggantikan standard `multiprocessing` library dengan isolasi proses yang lebih tangguh terhadap process leakages dan thread-pool thrashing.
*   **Memmapping Arrays Across Forks**: Ketika array NumPy melebihi threshold tertentu (default: 1 MB), `joblib` secara otomatis menulis array tersebut ke storage sementara berbasis memory-mapped files (`/dev/shm` pada Linux) dan membagikan pointer read-only kepada semua child worker processes. Mekanisme ini mencegah overhead serialisasi `pickle` lintas proses dan mengeliminasi redudansi memori RAM secara signifikan.

#### C. Mekanisme Data Leakage & Topologi Isolasi
Data leakage terjadi saat informasi dari luar set data pelatihan mencemari proses estimasi model. Pada arsitektur inferensial dan ML terapan, leakage diklasifikasikan ke dalam:
*   **Temporal Leakage**: Fitur input merefleksikan informasi yang baru eksis setelah label target terjadi di dunia nyata, atau cross-validation membagi data runtun waktu secara acak (I.I.D assumption violation), menyebabkan model belajar dari data masa depan (*peeking into the future*).
*   **Group Leakage**: Observasi dari entitas yang sama (misal: satu pasien memiliki 20 data rekam medis) tersebar di fold pelatihan dan fold pengujian sekaligus. Model menghafal profil spesifik entitas, bukan pola laten populasi.
*   **Preprocessing Leakage**: Melakukan standardisasi, imputasi nilai hilang, atau seleksi fitur pada *seluruh* dataset sebelum partisi train-test dilakukan. Statistik $\mu$ dan $\sigma$ dari test set ikut membentuk nilai input training set.

---

### 4. Why & What

| Dimensi | Pendekatan Ad-Hoc / Prototipe (Notebooks) | Pendekatan Enterprise Pipeline (Modul Ini) |
| :--- | :--- | :--- |
| **Preprocessing & Feature Engineering** | Dilakukan via skrip sekuensial Pandas terpisah. Risiko *state loss* tinggi antar environment. | Dibungkus ke dalam objek Pipeline Scikit-Learn hermetis via custom transformers standar. |
| **Pencegahan Leakage** | Mengandalkan ketelitian manual developer saat slicing dataframe. Rentan human-error. | Penegakan isolasi via `Pipeline` terenkapsulasi dan `ColumnTransformer`. Kebocoran data dicegah secara struktural. |
| **Validasi Model** | Standard K-Fold Cross-Validation acak (I.I.D). Mengabaikan dependensi waktu/kelompok. | Strategi validasi adaptif: `TimeSeriesSplit`, `GroupKFold`, atau `StratifiedGroupKFold`. |
| **Serialisasi** | Menggunakan raw Python `pickle`. Ancaman keamanan RCE (*Remote Code Execution*) dan dependensi library rapuh. | Menggunakan serialisasi aman `skops` atau konversi `ONNX Runtime` untuk inferensi lintas platform berlatensi ultra-rendah. |
| **Post-Deployment Lifecycle** | Model dianggap statis; evaluasi manual dilakukan secara ad-hoc saat komplain user naik. | Observabilitas metrik inferensi otomatis: Deteksi drift fitur (KS-Test/PSI) di layer serving pipeline. |

---

### 5. How (Workflow Detail)

Alur kerja rekayasa model enterprise dari prototyping hingga serving siap audit:

```
[ Raw Enterprise Data ] 
           │
           ▼
[ Temporal / Group Splitting ] ─── Data Kontrak Validasi (Bukan Random Split)
           │
           ├── Training Set ──────────────┐
           └── Validation / Test Set ─────┼─────────┐
                                          │         │
[ Feature Engineering Graph ]             │         │
    ├── Numerical Pipeline                │         │
    │     ├── Outlier Truncator           │         │
    │     ├── Robust Imputer              │         │
    │     └── Quantile Transformer        │         │
    └── Categorical Pipeline              │         │
          ├── Rare Label Encoder          │         │
          └── Target / WOE Encoder        │         │
           │                              │         │
           ▼                              │         │
[ ColumnTransformer Integration ] ────────┘         │
           │                                        │
           ▼                                        │
[ Estimator / Classifier Fitting ]                  │
           │                                        │
           ▼                                        │
[ Hyperparameter Optimization (Bayes/Optuna) ]      │
           │                                        │
           ▼                                        │
[ Evaluation & Calibration Assessment ] ◄───────────┘
           │
           ▼
[ Export to Standarized Format (ONNX/Skops) ]
           │
           ▼
[ Production Serving Engine with Drift Watchers ]
```

1.  **Isolasi Partisi Data**: Tentukan dimensi dependensi (apakah ada dependensi waktu? Apakah observasi terkelompokkan?). Terapkan `GroupKFold` atau `TimeSeriesSplit`.
2.  **Arsitektur Preprocessing Terisolasi**: Bangun custom transformers yang mengimplementasikan `fit()` dan `transform()`. Integrasikan seluruh preprocessing ke dalam `ColumnTransformer`.
3.  **Enkapsulasi Pipeline**: Satukan `ColumnTransformer` dan Estimator akhir ke dalam instance tunggal `Pipeline`. Hal ini menjamin bahwa seluruh data baru yang masuk ke production API diproses secara identik dengan data pelatihan.
4.  **Validasi Kalibrasi Probabilitas**: Model seperti Random Forest atau XGBoost seringkali menghasilkan probabilitas yang tidak terkalibrasi (*overconfident*). Terapkan `CalibratedClassifierCV` (Platt Scaling atau Isotonic Regression) dalam cross-validation loop.
5.  **Serialisasi dan Validasi Inferensi**: Ekspor model ke ONNX format, jalankan assert test numerik antara model scikit-learn asli vs runtime ONNX untuk toleransi floating-point $\epsilon < 10^{-5}$.
6.  **Observabilitas Serving**: Tambahkan hook pengukur data drift (PSI / Two-sample testing) yang berjalan async di samping proses komputasi respon inferensi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pemurnian Air Mandiri (*Hermetic Water Filtration Pipeline*)
Membangun machine learning tanpa pipeline ibarat mengambil air keruh dari sungai (raw data), menyaringnya menggunakan ember terpisah (manual pandas scaling), menuangkannya ke tangki penjernih (encoding), lalu menyerahkannya ke botol minum konsumen. Jika salah satu ember terkontaminasi air mentah di tengah jalan (preprocessing leakage), seluruh batch menjadi beracun.

Arsitektur Pipeline `scikit-learn` bekerja seperti **Sistem Pipa Tertutup Tersegel Pabrik**:
Air mentah masuk di satu ujung pipa. Modul filter lumpur (`Transformer 1`), membran karbon aktif (`Transformer 2`), dan disinfeksi ultraviolet (`Estimator`) berada di dalam satu kapsul tertutup. Air baru di restoran konsumen (data testing / production) wajib melewati pipa tertutup yang sama persis tanpa intervensi tangan manusia.

```
PILIHAN A: PREPROCESSING AD-HOC (RENTAN LEAKAGE & STATE CORRUPTION)
Data Train ───┐
              ├───> [ Skrip Pandas Imputer: Hitung Mean (A+B) ] ───> State Rusak!
Data Test  ───┘               │
                              └───> Train/Test terkontaminasi satu sama lain


PILIHAN B: ENTERPRISE PIPELINE ENCAPSULATION (ISOLASI HERMETIS)
                        ================ PIPELINE ================
Data Train (X_train) ──> [ Fit & Transform: Hitung Mean(Train) ] ──> [ Estimator.fit() ]
                        =========================================
                                                                        │
                                   MODEL TERVALIDASI                     │ Learned Params
                                                                        ▼
Data Baru / Test (X_test) ─> [ Transform Only (Pakai Mean Train) ] ─> [ Estimator.predict() ]
                        =========================================
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Membuat Custom Transformer yang Mengikuti Kontrak Scikit-Learn
Berikut adalah implementasi custom transformer untuk clipping outlier berbasis persentil non-parametrik yang thread-safe dan mematuhi API Scikit-Learn.

```python
from typing import Optional, Self
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_array, check_is_fitted


class RobustOutlierClipper(BaseEstimator, TransformerMixin):
    """
    Memotong nilai ekstrem (outlier) berdasarkan persentil bawah dan atas.
    Menjamin tidak ada mutasi state saat fase inferensi/transformasi.
    """
    def __init__(self, lower_percentile: float = 1.0, upper_percentile: float = 99.0):
        if not (0.0 <= lower_percentile < upper_percentile <= 100.0):
            raise ValueError("Parameter persentil tidak valid.")
        self.lower_percentile = lower_percentile
        self.upper_percentile = upper_percentile

    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> Self:
        # Validasi input array
        X_validated = check_array(X, accept_sparse=False, dtype=[np.float64, np.float32])
        
        # Hitung learned parameters hanya dari set pelatihan
        self.lower_bounds_ = np.percentile(X_validated, self.lower_percentile, axis=0)
        self.upper_bounds_ = np.percentile(X_validated, self.upper_percentile, axis=0)
        self.n_features_in_ = X_validated.shape[1]
        
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        # Validasi apakah transformer sudah melalui proses fitting
        check_is_fitted(self, attributes=["lower_bounds_", "upper_bounds_", "n_features_in_"])
        
        X_validated = check_array(X, accept_sparse=False, dtype=[np.float64, np.float32])
        
        if X_validated.shape[1] != self.n_features_in_:
            raise ValueError(
                f"Dimensi fitur tidak cocok. Harapan: {self.n_features_in_}, "
                f"Diterima: {X_validated.shape[1]}"
            )
        
        # Eksekusi transformasi deterministik
        return np.clip(X_validated, self.lower_bounds_, self.upper_bounds_)


if __name__ == "__main__":
    np.random.seed(42)
    sample_data = np.array([[-100.0, 500.0], [1.0, 2.0], [2.0, 3.0], [3.0, 2.0], [1000.0, -200.0]])
    clipper = RobustOutlierClipper(lower_percentile=10.0, upper_percentile=90.0)
    transformed_data = clipper.fit_transform(sample_data)
    print("Parameter Batas Bawah Terestimasi:", clipper.lower_bounds_)
    print("Parameter Batas Atas Terestimasi:", clipper.upper_bounds_)
    print("Hasil Transformasi:\n", transformed_data)
```

#### B. Practical Example: End-to-End Enterprise Training Pipeline
Kode berikut mengintegrasikan:
1.  Penanganan data bertipe campuran via `ColumnTransformer`.
2.  Custom Transformer untuk rekayasa rasio finansial.
3.  Target encoding tahan leakage dengan cross-fitting internal.
4.  Estimator terkalibrasi (`CalibratedClassifierCV`).
5.  Serialisasi aman menggunakan `skops`.

```python
import os
import numpy as np
import pandas as pd
from typing import List, Self
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import brier_score_loss, roc_auc_score
import skops.io as sio


# 1. Custom Feature Engineering Transformer
class FinancialRatioExtractor(BaseEstimator, TransformerMixin):
    """
    Menghitung rasio Debt-to-Income dan Credit Utilization secara aman.
    """
    def __init__(self, debt_col_idx: int = 0, income_col_idx: int = 1):
        self.debt_col_idx = debt_col_idx
        self.income_col_idx = income_col_idx

    def fit(self, X: np.ndarray, y: np.ndarray = None) -> Self:
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if X.shape[1] != self.n_features_in_:
            raise ValueError("Inkonsistensi dimensi fitur pada transform.")
        
        # Hindari pembagian dengan nol menggunakan epsilon
        eps = 1e-6
        debt = X[:, self.debt_col_idx]
        income = X[:, self.income_col_idx]
        dti_ratio = (debt / (income + eps)).reshape(-1, 1)
        
        return np.hstack([X, dti_ratio])


# 2. Sintesis Dataset FinTech Enterprise
def generate_synthetic_enterprise_data(n_samples: int = 10000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    monthly_debt = rng.gamma(shape=2.0, scale=1000.0, size=n_samples)
    monthly_income = rng.normal(loc=5000.0, scale=2000.0, size=n_samples)
    monthly_income = np.maximum(monthly_income, 500.0)  # Min income floor
    
    credit_score = rng.integers(300, 850, size=n_samples)
    employment_type = rng.choice(["FULL_TIME", "PART_TIME", "SELF_EMPLOYED", "UNEMPLOYED"], size=n_samples, p=[0.6, 0.15, 0.2, 0.05])
    
    # Probabilitas default dengan logit non-linear
    raw_score = (monthly_debt / monthly_income) * 1.5 - (credit_score / 200) + (employment_type == "UNEMPLOYED") * 2.0
    prob_default = 1 / (1 + np.exp(-raw_score + 1.5))
    default_label = (rng.uniform(0, 1, size=n_samples) < prob_default).astype(int)

    return pd.DataFrame({
        "monthly_debt": monthly_debt,
        "monthly_income": monthly_income,
        "credit_score": credit_score,
        "employment_type": employment_type,
        "default": default_label
    })


def run_pipeline_lifecycle() -> None:
    df = generate_synthetic_enterprise_data(10000)
    X = df.drop(columns=["default"])
    y = df["default"].values

    # Definisikan Group Fitur
    ratio_features = ["monthly_debt", "monthly_income"]
    other_numeric_features = ["credit_score"]
    categorical_features = ["employment_type"]

    # 3. Pipa Preprocessing Modular
    ratio_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("ratio_constructor", FinancialRatioExtractor(debt_col_idx=0, income_col_idx=1)),
        ("scaler", StandardScaler())
    ])

    standard_num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ])

    cat_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="UNKNOWN")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("ratio_block", ratio_pipeline, ratio_features),
            ("num_block", standard_num_pipeline, other_numeric_features),
            ("cat_block", cat_pipeline, categorical_features)
        ],
        remainder="drop"
    )

    # 4. Estimator Terkalibrasi untuk Probabilitas Produksi yang Akurat
    base_model = HistGradientBoostingClassifier(random_state=42, max_iter=100)
    calibrated_model = CalibratedClassifierCV(estimator=base_model, method="sigmoid", cv=3)

    full_pipeline = Pipeline([
        ("preprocessing", preprocessor),
        ("classifier", calibrated_model)
    ])

    # 5. Eksekusi Stratified Cross-Validation Eksplisit
    cv_strategy = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    roc_scores: List[float] = []
    brier_scores: List[float] = []

    print("[INFO] Memulai Validasi Model Enterprise...")
    for fold, (train_idx, val_idx) in enumerate(cv_strategy.split(X, y)):
        X_train_fold, X_val_fold = X.iloc[train_idx], X.iloc[val_idx]
        y_train_fold, y_val_fold = y[train_idx], y[val_idx]

        full_pipeline.fit(X_train_fold, y_train_fold)
        val_probs = full_pipeline.predict_proba(X_val_fold)[:, 1]

        fold_roc = roc_auc_score(y_val_fold, val_probs)
        fold_brier = brier_score_loss(y_val_fold, val_probs)

        roc_scores.append(fold_roc)
        brier_scores.append(fold_brier)
        print(f"  Fold {fold+1} | ROC-AUC: {fold_roc:.4f} | Brier Score: {fold_brier:.4f}")

    print(f"\n[HASIL] Rata-rata ROC-AUC: {np.mean(roc_scores):.4f} (+/- {np.std(roc_scores):.4f})")
    print(f"[HASIL] Rata-rata Brier Score: {np.mean(brier_scores):.4f}")

    # 6. Fit Final Model pada Keseluruhan Data
    full_pipeline.fit(X, y)

    # 7. Serialisasi Aman (Production-Grade Storage via SKOPS)
    model_artifact_path = "model_risk_v1.skops"
    sio.dump(full_pipeline, model_artifact_path)
    print(f"[INFO] Artefak model tersimpan secara aman di: {model_artifact_path}")

    # Validasi deserialisasi
    loaded_pipeline = sio.load(model_artifact_path, trusted=True)
    sample_payload = pd.DataFrame([{
        "monthly_debt": 3500.0,
        "monthly_income": 4000.0,
        "credit_score": 580,
        "employment_type": "SELF_EMPLOYED"
    }])
    
    inferred_prob = loaded_pipeline.predict_proba(sample_payload)[0, 1]
    print(f"[INFERENSI SAMPLE] Probabilitas Default: {inferred_prob:.4%}")

    if os.path.exists(model_artifact_path):
        os.remove(model_artifact_path)


if __name__ == "__main__":
    run_pipeline_lifecycle()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Sistem
*Perusahaan*: FinTech Peer-to-Peer Lending berskala Tier-1 di Asia Tenggara.  
*Beban Trafik*: 850 permintaan kalkulasi risiko kredit per detik saat jam sibuk (peak traffic).  
*SLA Latensi*: $p99 \le 20\text{ ms}$ untuk inferensi skor probabilitas default.  
*Kepatuhan Regulasi*: Audit model oleh bank sentral mengharuskan data pelanggan diuji secara ketat terhadap *data drift* harian dan pelarangan penggunaan format serialisasi berbahaya (`pickle`).

#### Arsitektur Solusi Inferensi Produksi & Drift Engine
Sistem dibagi menjadi dua komponen:
1.  **High-Throughput Prediction Worker**: Menjalankan pipeline Scikit-Learn yang di-compile ke runtime ONNX/C-Runtime atau pipeline thread-safe di-host via FastAPI + ASGI lifespan worker pools.
2.  **Streaming Statistical Drift Watcher**: Menghitung drift metrik menggunakan uji Kolmogorov-Smirnov (KS) terhadap fitur numerik kontinu dan Population Stability Index (PSI) terhadap fitur kategorikal/skor inferensi dalam rolling-window harian.

```
+-----------------------------------------------------------------------------------+
|                        REAL-TIME SERVING & DRIFT ARCHITECTURE                     |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ API Gateway ]                                                                  |
|        │                                                                          |
|        ▼ (HTTP Payload)                                                           |
|  [ FastAPI Worker Pool ]                                                          |
|        │                                                                          |
|        ├───────> [ Skops/ONNX Pipeline Engine ] ───> Return Prediction (p99 < 15ms)|
|        │                    │                                                     |
|        │                    ▼ (Background Async Task)                             |
|        └───────> [ In-Memory Buffer (Redis Streams) ]                             |
|                                     │                                             |
|                                     ▼ (Sliding Window: 24 Jam)                    |
|                        [ Statistical Drift Worker ]                               |
|                                     │                                             |
|                   ┌─────────────────┴─────────────────┐                           |
|                   ▼                                   ▼                           |
|         [ KS-Test (Continuous) ]             [ PSI Metric (Discrete) ]            |
|            (D_stat > 0.05?)                     (PSI > 0.25 Alert?)               |
|                   │                                   │                           |
|                   └─────────────────┬─────────────────┘                           |
|                                     │                                             |
|                                     ▼                                             |
|                   [ Prometheus Alert Manager ] ──> Trigger Auto-Retrain Ops       |
+-----------------------------------------------------------------------------------+
```

#### Implementasi Core Engine Pemantau Drift (Production Script)

```python
import numpy as np
from scipy import stats
from typing import Dict, Any


class ProductionDriftMonitor:
    """
    Sub-sistem observabilitas untuk memantau feature & prediction drift 
    pada inference engine.
    """
    def __init__(self, baseline_data: np.ndarray, feature_names: list[str]):
        self.baseline_data = baseline_data
        self.feature_names = feature_names
        self.n_features = baseline_data.shape[1]
        
    def calculate_psi(self, baseline: np.ndarray, target: np.ndarray, num_buckets: int = 10) -> float:
        """
        Menghitung Population Stability Index (PSI) antara dua distribusi.
        Formula: PSI = SUM( (Actual% - Expected%) * ln(Actual% / Expected%) )
        """
        # Tentukan bucket boundaries dari baseline
        percentiles = np.linspace(0, 100, num_buckets + 1)
        buckets = np.percentile(baseline, percentiles)
        buckets[0] -= 1e-5
        buckets[-1] += 1e-5

        baseline_counts, _ = np.histogram(baseline, bins=buckets)
        target_counts, _ = np.histogram(target, bins=buckets)

        # Ubah ke pecahan (proporsi), terapkan Laplace smoothing untuk menghindari pembagian nol
        baseline_pct = (baseline_counts + 1e-4) / (len(baseline) + 1e-4 * num_buckets)
        target_pct = (target_counts + 1e-4) / (len(target) + 1e-4 * num_buckets)

        psi_val = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
        return float(psi_val)

    def evaluate_drift(self, current_batch: np.ndarray, ks_alpha: float = 0.01, psi_threshold: float = 0.2) -> Dict[str, Any]:
        """
        Mengevaluasi drift per kolom menggunakan KS-Test dan PSI.
        """
        if current_batch.shape[1] != self.n_features:
            raise ValueError("Dimensi batch inferensi tidak konsisten dengan baseline.")

        report = {}
        drift_detected = False

        for idx, feat_name in enumerate(self.feature_names):
            base_col = self.baseline_data[:, idx]
            curr_col = current_batch[:, idx]

            # 1. Kolmogorov-Smirnov Test (Non-parametrik untuk kontinuitas bentuk kurva)
            ks_res = stats.ks_2samp(base_col, curr_col)
            
            # 2. Population Stability Index
            psi_value = self.calculate_psi(base_col, curr_col)

            # Keputusan drift: Jika p-value sangat kecil dan PSI berada di level high instability
            is_feature_drifted = bool(ks_res.pvalue < ks_alpha and psi_value > psi_threshold)
            if is_feature_drifted:
                drift_detected = True

            report[feat_name] = {
                "ks_statistic": float(ks_res.statistic),
                "ks_pvalue": float(ks_res.pvalue),
                "psi": psi_value,
                "is_drifted": is_feature_drifted
            }

        return {
            "drift_alarm": drift_detected,
            "metrics": report
        }


if __name__ == "__main__":
    # Baseline: Distribusi normal standar
    rng = np.random.default_rng(100)
    baseline_features = rng.normal(loc=0.0, scale=1.0, size=(5000, 2))
    
    monitor = ProductionDriftMonitor(
        baseline_data=baseline_features,
        feature_names=["debt_to_income", "risk_index"]
    )

    # Simulasi Hari ke-30: Terjadi shift makroekonomi pada kolom 'debt_to_income'
    current_production_features = np.column_stack([
        rng.normal(loc=0.35, scale=1.2, size=2000),  # Terjadi Drift Signifikan
        rng.normal(loc=0.0, scale=1.0, size=2000)    # Tetap Stabil
    ])

    drift_report = monitor.evaluate_drift(current_production_features)
    print("Hasil Audit Data Drift:")
    for feature, metric in drift_report["metrics"].items():
        print(f"Fitur: {feature}")
        print(f"  - KS p-value : {metric['ks_pvalue']:.6e}")
        print(f"  - Nilai PSI  : {metric['psi']:.4f}")
        print(f"  - Status     : {'DRIFT DETECTED!' if metric['is_drifted'] else 'STABLE'}")
```

---

### 9. Trade-offs

```
                  PILIHAN PENDEKATAN PIPELINE & INFERENSI
                                     │
      ┌──────────────────────────────┴──────────────────────────────┐
      ▼                                                             ▼
[ Scikit-Learn Native Engine ]                             [ ONNX Engine Compilations ]
      │                                                             │
  Pros:                                                         Pros:
  + Skrip Python murni, mudah debug                              + Latensi inferensi mikrodetik (C++ Runtime)
  + Dukungan custom logic dinamis tak terbatas                  + Ringan di CPU, memory footprint minimal
  Cons:                                                         Cons:
  - Latensi Python runtime overhead (5-15ms)                    - Debugging custom operator rumit
  - GIL locks pada concurrency tinggi                           - Tidak semua logic sklearn terdukung langsung
```

| Parameter | Pandas Script Ad-Hoc | Scikit-Learn Pipeline | ONNX Runtime Engine | Custom C++/Rust Bindings |
| :--- | :--- | :--- | :--- | :--- |
| **Inference Latency** | Tinggi (>50ms) | Menengah (5 - 20ms) | Rendah (1 - 3ms) | Sangat Rendah (< 500µs) |
| **Throughput (RPS)** | Buruk (< 100) | Menengah (200 - 800) | Sangat Tinggi (3.000+) | Ekstrem (10.000+) |
| **Developer Velocity** | Cepat di awal, hancur di prod | Tinggi & Standar | Menengah (perlu konversi) | Sangat Lambat |
| **Maintenance Cost** | Ekstrem (rawan bug) | Rendah (Desain teruji) | Menengah | Sangat Tinggi |
| **Auditability/Security** | Rawan (Unsafe state) | Aman via `skops` | Aman (Static graph execution) | Aman jika memory safe |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Preprocessing Leakage Saat Imputasi Nilai
*   **Gejala**: Performa validasi offline luar biasa tinggi (misal ROC-AUC: 0.98), namun performa di production drop drastis ke 0.65.
*   **Akar Masalah**: Melakukan pemanggilan `scaler.fit_transform(df)` sebelum membagi data menjadi train dan test split. Nilai mean dan standar deviasi dari test set bocor ke dalam data latih.
*   **Solusi**: Bungkus transformer ke dalam `sklearn.pipeline.Pipeline` dan panggil HANYA `.fit()` pada `X_train`. Data uji wajib diproses melalui `.transform()` murni.

#### Kesalahan 2: Memodifikasi Variabel Input pada Custom Transformer
*   **Gejala**: Iterasi Cross-Validation menghasilkan skor yang berfluktuasi secara aneh dan merusak state dataframe global.
*   **Akar Masalah**: Di dalam metode `transform(self, X)`, developer menulis `X['new_col'] = X['col_a'] / X['col_b']` yang memodifikasi original DataFrame in-place (*side-effect*).
*   **Solusi**: Pastikan membuat salinan eksplisit jika menggunakan manipulasi mutating atau gunakan operasi NumPy array murni: `X_out = np.empty_like(X)`.

#### Kesalahan 3: Menggunakan Python `pickle` untuk Deployment Produksi
*   **Gejala**: Muncul kerentanan keamanan kritis pada pemindaian SonarQube/Snyk (CWE-502: *Deserialization of Untrusted Data*), serta error crashing `AttributeError: Can't get attribute 'MyTransformer' on <module '__main__'>` ketika struktur project direorganisasi.
*   **Akar Masalah**: `pickle` menyimpan referensi bytecode dan eksekusi instruksi arbitrer secara literal, bukan sekadar representasi bobot/arsitektur parameter.
*   **Solusi**: Gunakan library `skops.io` yang menggunakan schema parsing terisolasi tanpa eksekusi kode acak, atau transpilasi model ke ONNX format.

---

### 11. Best Practices (Production Checklist)

- [ ] **State Hermeticity**: Memastikan semua preprocessing data terkurung di dalam `Pipeline` atau `ColumnTransformer`. Tidak ada fungsi global `clean_dataframe()` yang dieksekusi di luar pipeline.
- [ ] **Stateless Inference**: Memverifikasi bahwa metode `transform()` dan `predict()` pada custom transformer bersifat idempoten dan tidak pernah memperbarui state instance variabel (`self.xxx_`).
- [ ] **Validation Integrity**: Menerapkan splitting data yang merefleksikan proses realita bisnis:
  - Data berorientasi transaksi waktu $\to$ Gunakan `TimeSeriesSplit`.
  - Data yang memiliki ID entitas multipel $\to$ Gunakan `GroupKFold` / `StratifiedGroupKFold`.
- [ ] **Probability Calibration Check**: Memeriksa kalibrasi probabilitas menggunakan reliability curve (`scikit-learn.calibration.calibration_curve`). Jangan menyajikan skor mentah tree-based ensemble langsung ke aturan bisnis pembiayaan/fraud.
- [ ] **Serialization Security**: Tidak menyebarkan model format `.pkl` atau `.joblib` jika file dibaca dari storage publik atau jaringan terbuka. Gunakan `.skops` atau `.onnx`.
- [ ] **Concurrency Optimization**: Untuk API serving multithreaded (FastAPI/Uvicorn), pastikan thread overhead Scikit-Learn/OpenMP dikendalikan menggunakan variabel environment:
  ```bash
  export OMP_NUM_THREADS=1
  export OPENBLAS_NUM_THREADS=1
  export MKL_NUM_THREADS=1
  ```
- [ ] **Production Drift Baseline**: Menyimpan statistik baseline deskriptif (mean, deviasi, kuantil 1 hingga 99) dari data training langsung ke metadata artefak model.

---

### 12. Hands-on Practice

Buka terminal dan bangun direktori praktikum berikut:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
python -m venv venv
source venv/bin/activate  # Linux/MacOS atau venv\Scripts\activate pada Windows
pip install numpy pandas scikit-learn scipy skops
```

Buat file `hands-on/m02/production_pipeline.py` dan salin kode implementasi lengkap di bawah ini:

```python
"""
hands-on/m02/production_pipeline.py
Implementasi Pipeline Produksi Lengkap: Transformasi, Estimasi, Validasi, dan Drift Monitoring.
"""

import sys
import numpy as np
import pandas as pd
from typing import Self
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score, log_loss
from scipy.stats import ks_2samp
import skops.io as sio


class AdaptiveCapTransformer(BaseEstimator, TransformerMixin):
    """
    Membatasi data ekstrem berdasarkan interquartile range (IQR) multiplier.
    """
    def __init__(self, factor: float = 1.5):
        self.factor = factor

    def fit(self, X: np.ndarray, y: np.ndarray = None) -> Self:
        q25 = np.percentile(X, 25, axis=0)
        q75 = np.percentile(X, 75, axis=0)
        iqr = q75 - q25
        self.lower_limit_ = q25 - (self.factor * iqr)
        self.upper_limit_ = q75 + (self.factor * iqr)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return np.clip(X, self.lower_limit_, self.upper_limit_)


def execute_enterprise_flow():
    print("[1] Membangkitkan Data Runtun Waktu Sintetis...")
    rng = np.random.default_rng(2026)
    n_records = 15000
    
    # Sintesis deret waktu: 100 hari observasi
    dates = pd.date_range(start="2025-01-01", periods=n_records, freq="6min")
    txn_amount = rng.exponential(scale=150.0, size=n_records) + rng.normal(0, 10, size=n_records)
    user_risk_score = rng.uniform(1.0, 10.0, size=n_records)
    channel = rng.choice(["WEB", "MOBILE_IOS", "MOBILE_ANDROID", "API"], size=n_records, p=[0.2, 0.4, 0.3, 0.1])
    
    # Label fraud dependensi waktu
    fraud_prob = 1 / (1 + np.exp(-(0.005 * txn_amount + 0.3 * user_risk_score - 3.5)))
    is_fraud = (rng.uniform(0, 1, size=n_records) < fraud_prob).astype(int)

    df = pd.DataFrame({
        "timestamp": dates,
        "txn_amount": txn_amount,
        "user_risk": user_risk_score,
        "channel": channel,
        "is_fraud": is_fraud
    }).sort_values("timestamp").reset_index(drop=True)

    X = df[["txn_amount", "user_risk", "channel"]]
    y = df["is_fraud"].values

    print("[2] Merancang Arsitektur Preprocessing Pipeline...")
    num_cols = ["txn_amount", "user_risk"]
    cat_cols = ["channel"]

    num_flow = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("capping", AdaptiveCapTransformer(factor=2.0)),
        ("scaler", RobustScaler())
    ])

    cat_flow = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False))
    ])

    pipeline_preprocessor = ColumnTransformer([
        ("numeric", num_flow, num_cols),
        ("categorical", cat_flow, cat_cols)
    ])

    model_pipeline = Pipeline([
        ("prep", pipeline_preprocessor),
        ("clf", HistGradientBoostingClassifier(random_state=42, max_depth=5))
    ])

    print("[3] Mengeksekusi TimeSeriesSplit Cross Validation...")
    tscv = TimeSeriesSplit(n_splits=4)
    fold_idx = 1
    
    for train_index, test_index in tscv.split(X):
        X_tr, X_te = X.iloc[train_index], X.iloc[test_index]
        y_tr, y_te = y[train_index], y[test_index]

        model_pipeline.fit(X_tr, y_tr)
        preds = model_pipeline.predict_proba(X_te)[:, 1]
        
        auc = roc_auc_score(y_te, preds)
        loss = log_loss(y_te, preds)
        print(f"  Fold {fold_idx} | Periode Sampel: {len(X_tr)} Train -> {len(X_te)} Test | AUC: {auc:.4f} | LogLoss: {loss:.4f}")
        fold_idx += 1

    print("[4] Persistensi Model Hermetis menggunakan Skops...")
    model_pipeline.fit(X, y)
    saved_model_file = "hands-on/m02/fraud_detector.skops"
    sio.dump(model_pipeline, saved_model_file)
    print(f"Artefak aman tersimpan di: {saved_model_file}")

    print("[5] Simulasi Monitoring Ingestion Batch & Drift Detection...")
    # Simulasi inferensi hari baru: Terjadi anomali pergeseran transaksi (drift)
    new_inflow_amount = rng.exponential(scale=350.0, size=1000)  # Drift signifikan (scale naik dari 150 -> 350)
    baseline_sample = X["txn_amount"].values[:1000]

    # Uji Kolmogorov-Smirnov
    ks_test_result = ks_2samp(baseline_sample, new_inflow_amount)
    print(f"  KS-Statistic Data Baru: {ks_test_result.statistic:.4f}")
    print(f"  p-value: {ks_test_result.pvalue:.4e}")
    
    if ks_test_result.pvalue < 0.01:
        print("  [ALERT] Drift terdeteksi secara signifikan pada metrik transaksi!")
    else:
        print("  [OK] Distribusi data normal.")


if __name__ == "__main__":
    execute_enterprise_flow()
```

Eksekusi skrip:
```bash
python hands-on/m02/production_pipeline.py
```

---

### 13. Exercise

#### Level Easy
Buat custom transformer bernama `Log1pTransformer` yang mengimplementasikan transformasi non-linier $f(x) = \ln(x + 1)$ pada kolom numerik bertipe non-negatif. Pastikan jika data menerima angka $< 0$, metode `transform()` memicu `ValueError` secara eksplisit dan lolos validasi skema input `check_array`.

#### Level Medium
Sebuah perusahaan logistik memiliki 500 kendaraan pengiriman. Dataset transaksi mencakup `driver_id`, `distance_km`, `payload_weight`, dan target biner `late_delivery`. Rancang pipeline machine learning menggunakan `StratifiedGroupKFold` untuk memverifikasi model tanpa kebocoran data supir (`driver_id`) antara training dan test splits. Terapkan custom imputation yang mengganti missing values pada `payload_weight` berdasarkan median berat per masing-masing kelompok kendaraan.

#### Level Hard
Kembangkan custom pipeline transformer berkemampuan target-encoding multivariat bernama `JackknifeTargetEncoder`. Transformer ini harus:
1.  Menghitung smoothed target mean untuk variabel berkardinalitas tinggi dengan formula smoothing m-estimate:
    $$S_i = \frac{n_i \cdot \bar{y}_i + m \cdot \bar{y}_{global}}{n_i + m}$$
2.  Mencegah target leakage internal pada saat fase `.fit_transform()` menggunakan skema out-of-fold jackknife (leave-one-out cross-fitting internal).
3.  Berjalan sepenuhnya mematuhi standar Scikit-Learn Estimator Check (`sklearn.utils.estimator_checks.check_estimator`).

---

### 14. Challenge

**Skenario**: Anda ditunjuk sebagai Principal ML Engineer di platform e-Commerce multi-tenant terbesar di Indonesia. Sistem Anda menerima feed data klik transaksi real-time sebesar 50.000 events/detik.
Terdapat masalah struktural:
1.  **Extreme Cold-Start / Concept Shift**: Setiap akhir pekan kampanye gajian (Payday Flash Sale), proporsi pengguna baru meningkat 400%, mengubah pola belanja secara radikal dibanding hari kerja biasa.
2.  **Strict Inference Constraints**: Mesin rekomendasi/prediksi konversi harus merespon dalam waktu maksimal $8\text{ ms}$ ($p99$) per request pengguna.
3.  **Complex Data Schema**: Data memuat kombinasi teks mentah (nama pencarian produk), kategori berkardinalitas tinggi (sub-kategori merchant ID dengan 100.000 variasi), serta deret riwayat transaksi pengguna selama 7 hari terakhir.

**Misi Anda**:
Rancang arsitektur end-to-end terperinci dalam bentuk proposal teknis dan pseudocode implementatif yang mencakup:
*   Topologi pipeline preprocessing scikit-learn yang mampu memproses fitur campuran tanpa alokasi memori berlebih (*zero defensive memory copies*).
*   Strategi adaptasi model tanpa melakukan full retraining yang memakan waktu lama: bagaimana Anda menggabungkan continuous online updates dengan batch offline training?
*   Desain sistem serving inferensi berlatensi rendah: teknik serialisasi mana yang digunakan, bagaimana isolasi resource CPU dilakukan, dan bagaimana metrik Kolmogorov-Smirnov / PSI dihitung secara asinkron tanpa membebani path kritis inferensi?

---

### 15. Quiz Evaluasi Pemahaman

#### Pertanyaan Basic
1.  Mengapa inisialisasi hyperparameter pada metode `__init__` custom transformer Scikit-Learn tidak boleh mengubah argumen input atau menerima data latih ($X$)?
2.  Apa implikasi teknis dari konvensi *trailing underscore* (misal: `self.scale_`) pada atribut Scikit-Learn?
3.  Mengapa standard K-Fold Cross Validation acak dilarang keras untuk data runtun waktu (time-series)?
4.  Apa resiko utama menggunakan Python standard library `pickle` untuk memuat model di server produksi?
5.  Apa perbedaan mendasar antara metode `.fit_transform()` dan metode `.transform()` yang dipanggil secara sekuensial pada test set?

#### Pertanyaan Intermediate
6.  Bagaimana arsitektur `joblib` mencegah overhead duplikasi RAM saat melakukan parallel processing (`n_jobs > 1`) pada dataset bertipe NumPy array besar?
7.  Jelaskan konsep *Group Leakage* dan berikan contoh nyata dalam industri kesehatan atau finansial!
8.  Mengapa `CalibratedClassifierCV` sering dibutuhkan setelah melatih model tree ensemble seperti Random Forest atau Gradient Boosting?
9.  Bagaimana cara kerja uji non-parametrik Kolmogorov-Smirnov dalam mendeteksi pergeseran fitur (*feature drift*), dan apa keuntungan utamanya dibanding uji parametrik seperti Two-Sample t-Test?
10. Pada kondisi data seperti apa metrik Population Stability Index (PSI) mengindikasikan bahwa model machine learning HARUS segera di-retrain?

#### Skenario Kasus Produksi
11. **Skenario A**: Tim Anda merilis pipeline klasifikasi anti-fraud baru. Pada pengujian offline cross-validation lokal, pipeline mencetak performa F1-Score sebesar 0.94. Namun, ketika microservice production API dijalankan, performa rill ambruk menjadi 0.52. Log sistem menunjukkan tidak ada error atau exception yang terjadi. Investigasi apa yang harus Anda lakukan pada tahap pembuatan fitur numerik dan tanggal?
12. **Skenario B**: Sistem serving FastAPI Anda menggunakan Scikit-Learn pipeline untuk inferensi real-time. Di bawah beban uji stres (1000 concurrent virtual users), server mengalami masalah CPU starvation dan latensi p99 melonjak dari 12ms ke 4500ms, meskipun CPU utilization belum mencapai 100%. Jelaskan penyebab masalah thread-pool ini dan konfigurasi apa yang harus diterapkan.
13. **Skenario C**: Sebuah model skor risiko kredit menggunakan fitur `annual_income`. Tiba-tiba di kuartal baru, nilai PSI untuk fitur tersebut melonjak ke angka 0.38, namun nilai Kolmogorov-Smirnov p-value tetap berada di angka 0.15 (tidak signifikan). Analisis anomali statistik apa yang sedang terjadi antara kedua uji ini.

---

#### Kunci Jawaban & Evaluasi

##### Jawaban Basic
1.  **Kepatuhan Kontrak API**: Scikit-Learn mengandalkan kloning estimator secara stateless via `sklearn.base.clone()`. Fungsi `clone` membaca argumen signature `__init__` secara eksak tanpa memanggil constructor baru. Jika parameter diubah dalam `__init__`, state cloning akan rusak, memicu kegagalan pada operasi seperti `GridSearchCV`.
2.  **Pembeda State**: *Trailing underscore* menandakan bahwa atribut tersebut adalah parameter terestimasi (*learned parameter*) hasil eksekusi `.fit()`. Atribut ini juga digunakan oleh fungsi pembantu seperti `check_is_fitted()` untuk memverifikasi kesiapan estimator dalam melayani inferensi `.predict()` atau `.transform()`.
3.  **Pelanggaran Asumsi Kausalitas Temporal**: K-Fold standar mengasumsikan data bersifat *Independent and Identically Distributed* (I.I.D). Membagi data time-series secara acak menyebabkan data masa depan masuk ke set pelatihan masa lalu (*Lookahead Bias* / *Temporal Leakage*).
4.  **Eksekusi Kode Arbitrer (RCE)**: `pickle` bekerja sebagai virtual machine berbasis stack yang dapat mengeksekusi kelas dan perintah sistem operasi lokal (misal: `os.system`) saat proses unpickling file berbahaya yang telah dimanipulasi oleh penyerang.
5.  **Pencegahan Kontaminasi State**: `fit_transform()` menghitung parameter statistik dari data masukan dan menyimpannya ke memori, sekaligus mentransformasi data tersebut. Sedangkan `transform()` HANYA menerapkan parameter statistik yang sudah tersimpan sebelumnya tanpa mengubah state internal sedikit pun.

##### Jawaban Intermediate
6.  **Zero-Copy Shared Memory**: `joblib` (menggunakan Loky worker pool) mendeteksi array NumPy yang besar dan mengalokasikannya ke dalam file backed memory-map (`/dev/shm` shared memory OS). Alih-alih menduplikasi array ke masing-masing proses worker melalui komunikasi IPC/pipe yang lambat, child process langsung membaca memori yang sama secara read-only tanpa alokasi memori tambahan (*zero copy*).
7.  **Group Leakage**: Terjadi saat observasi dari satu subjek/entitas terdistribusi di set pelatihan dan set pengujian sekaligus. Contoh di layanan kesehatan: Gambar rontgen dada dari satu pasien yang sama (dengan ciri biologis unik yang sama) berada di data latih dan data uji. Model belajar menghafal tekstur spesifik anatomi pasien tersebut, bukan patologi penyakit secara objektif.
8.  **Ketidakakuratan Probabilitas (Miscalibration)**: Algoritma Tree Ensembles (seperti Random Forest atau Boosting) cenderung memprediksi probabilitas mendekati ekstrem (terlalu percaya diri) atau terdistorsi di dekat margin keputusan karena voting varians ensemble atau proses pemotongan pohon. `CalibratedClassifierCV` menyesuaikan output agar probabilitas merefleksikan frekuensi empiris sebenarnya (misal: dari 100 prediksi berprobabilitas 0.8, benar-benar terjadi 80 kejadian positif).
9.  **Uji Non-Parametrik Bentuk Distribusi**: KS-Test membandingkan jarak vertikal maksimum ($D$-statistic) antara fungsi distribusi kumulatif empiris (*Empirical Cumulative Distribution Function* / ECDF) dari dua sampel. Keuntungan utamanya: tidak memerlukan asumsi distribusi data normal (bebas distribusi) dan peka terhadap pergeseran lokasi, varians, maupun kemiringan (*skewness*).
10. **Ambang Batas PSI**: Secara standar industri:
    *   $\text{PSI} < 0.1$: Tidak ada perubahan signifikan (stabil).
    *   $0.1 \le \text{PSI} \le 0.25$: Terdapat pergeseran moderat.
    *   $\text{PSI} > 0.25$: Terjadi *Significant Distribution Shift*. Pada tingkat ini, akurasi inferensi model hampir pasti mengalami degradasi berat dan wajib memicu retrain segera.

##### Solusi Skenario Kasus Produksi
11. **Analisis Skenario A**: Kemungkinan besar terjadi **Data Preprocessing Leakage** atau **Target Encoding Leakage** di level skrip. Misalnya, proses normalisasi/imputasi dilakukan pada seluruh data sebelum train-test partition, atau pembuatan fitur melibatkan aggregasi masa depan (contoh: *average transaction amount of the user in the last 30 days* dihitung menggunakan rolling window yang bergerak maju melampaui tanggal transaksi target). Saat masuk production, masa depan tidak tersedia, sehingga fitur menghasilkan deviasi nilai yang menghancurkan inferensi model.
12. **Analisis Skenario B**: Terjadi fenomena **OpenMP/BLAS Thread Contention Thrashing**. Scikit-Learn menggunakan pustaka C-level underlying (OpenBLAS/MKL) yang secara default mengalokasikan thread sebanyak core CPU untuk setiap request. Jika Uvicorn/FastAPI melayani banyak concurrent request sekaligus, terjadi benturan ribuan thread memperebutkan context switching pada physical cores CPU. Solusinya: Konfigurasikan environment variables sistem di level container/OS `OMP_NUM_THREADS=1` dan `OPENBLAS_NUM_THREADS=1` agar satu worker proses Python hanya menggunakan satu worker thread secara sekuensial dan efisien.
13. **Analisis Skenario C**: Anomali ini mengindikasikan adanya **Kategorisasi Ekstrem pada Ekor Distribusi (*Outlier Tail Event*)**. KS-Test berfokus pada jarak supremum ($D_{max}$) pada ECDF, yang secara inheren paling sensitif di dekat median/tengah kurva distribusi dan kurang sensitif pada ekor (*tails*). Sebaliknya, binning diskrit pada formula PSI sangat rentan terhadap ledakan persentase di bucket margin luar (misal: lonjakan tajam pada nasabah bernilai ultra-kaya atau bernilai 0 rupiah akibat perubahan kebijakan sistem). Distribusi tengah tetap stabil (KS lolos), namun pergeseran ekstrem di ujung bucket memicu lonjakan formula logarithmic ratio pada PSI.

---

### 16. Summary

*   Membangun sistem analitik prediktif enterprise membutuhkan kepatuhan mutlak terhadap antarmuka estimator Scikit-Learn (`fit`, `transform`, `predict`). Semua parameter terestimasi harus terkunci di dalam instansiasi pipeline untuk memastikan determinisme pengujian.
*   *Data Leakage* adalah penyebab nomor satu kegagalan model di tingkat produksi. Membungkus data transformation ke dalam `Pipeline` bersama `ColumnTransformer` serta menggunakan teknik split adaptif (`TimeSeriesSplit`, `GroupKFold`) mengeliminasi resiko kontaminasi informasi secara struktural.
*   Artefak model yang siap digunakan di level enterprise wajib meninggalkan format `pickle` yang rentan demi format modern seperti `skops` atau runtime terbuka `ONNX` untuk mencapai kombinasi keamanan, portabilitas lintas bahasa, dan latensi inferensi sub-milidetik.
*   Lifecycle model machine learning tidak berakhir saat model selesai di-training. Mengintegrasikan subsistem observabilitas drift berbasis uji statistik non-parametrik (Kolmogorov-Smirnov) dan Population Stability Index (PSI) adalah prasyarat mutlak untuk menjaga integritas model analitik saat menghadapi dinamika data produksi di dunia nyata.