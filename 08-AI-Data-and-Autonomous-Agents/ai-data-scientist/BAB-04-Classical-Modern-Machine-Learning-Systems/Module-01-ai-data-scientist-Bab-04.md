# Bab 04: Classical & Modern Machine Learning Systems
## Modul 01: Arsitektur Pipeline Machine Learning Enterprise: Dari Feature Engineering Deterministik hingga Estimator Modern

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

- **Menganalisis & Mengeliminasi Structural Data Leakage**: Mengidentifikasi dan memitigasi kebocoran data (*train-test contamination*) pada pemrosesan temporal dan *cross-sectional* menggunakan abstraksi pipeline terisolasi.
- **Mengembangkan Custom Transformer Scikit-Learn Sesuai Standar**: Mengimplementasikan transformer berbasis vektor yang aman untuk lingkungan paralel (*thread-safe*), memiliki tipe data ketat (*strictly typed*), dan mematuhi API Scikit-Learn (`BaseEstimator`, `TransformerMixin`).
- **Mengevaluasi Karakteristik Matematis Dual-Paradigma Model**: Membandingkan formulasi konvergensi, *loss landscape*, dan efisiensi komputasi antara *Generalized Linear Models* teregularisasi (ElasticNet via *Coordinate Descent*) dan *Histogram-based Gradient Boosted Decision Trees* (LightGBM/XGBoost).
- **Membangun Sistem Kalibrasi Probabilitas Produksi**: Menerapkan kalibrasi probabilitas pasca-pelatihan (*Platt Scaling* dan *Isotonic Regression*) untuk memastikan estimasi *risk scoring* memiliki reliabilitas statistik yang valid.
- **Menyusun Arsitektur Pipeline Inferensi Enterprise**: Merancang pipeline terpadu dari preparasi data mentah, rekayasa fitur (*out-of-fold target encoding*, *winsorization*), seleksi model, hingga serialisasi berkinerja tinggi.

---

### 2. Concept Overview

Sistem Machine Learning tabular di tingkat enterprise beroperasi pada spektrum dual-paradigma: model parametrik konveks (*Generalized Linear Models*) yang menawarkan transparansi mutlak serta latensi inferensi sub-milidetik, berbanding terbalik dengan model non-parametrik non-konveks (*Gradient Boosted Decision Trees*) yang menguasai interaksi fitur non-linear berdimensi tinggi.

```
+-------------------------------------------------------------------------------+
|                       Dual-Paradigm Estimator Framework                       |
+------------------------------------+------------------------------------------+
| 1. Parametric Convex Optimization  | 2. Non-Parametric Greedy Partitioning    |
|    (Regularized GLM / ElasticNet)  |    (Histogram-based GBDT)                |
+------------------------------------+------------------------------------------+
| Loss: L(w) = L_emp(w) + R(w)       | Split: Argmax_s Gain(s)                  |
| Solver: Coordinate Descent / L-BFGS| Split Finder: Gradient/Hessian Histograms|
| Space: Global Hyperplane Partition | Space: Orthogonal Axis-Aligned Polyhedra |
+------------------------------------+------------------------------------------+
```

#### Fondasi Matematis

##### 1. ElasticNet Regularization (GLM)
Optimisasi konveks ElasticNet memadukan penalti $L_1$ (Lasso) untuk memicu seleksi fitur (*sparsity*) dan penalti $L_2$ (Ridge) untuk mengatasi multikolinearitas ekstrem:

$$\min_{w \in \mathbb{R}^p} \left\{ \frac{1}{2n} \sum_{i=1}^n \left( y_i - w^T x_i \right)^2 + \lambda \left( \alpha \|w\|_1 + \frac{1 - \alpha}{2} \|w\|_2^2 \right) \right\}$$

Pembaruan bobot $w_j$ pada *Coordinate Descent* dihitung menggunakan operator ambang batas lunak (*soft-thresholding*):

$$S(\rho_j, \lambda \alpha) = \text{sign}(\rho_j) \max\left(0, |\rho_j| - \lambda \alpha\right)$$

$$w_j \leftarrow \frac{S\left(\sum_{i=1}^n x_{ij}(y_i - \hat{y}_i^{(-j)}), \lambda \alpha\right)}{\sum_{i=1}^n x_{ij}^2 + \lambda(1 - \alpha)}$$

di mana $\hat{y}_i^{(-j)}$ adalah prediksi model tanpa menyertakan fitur ke-$j$.

##### 2. Gradient Boosted Decision Trees (Second-Order Approximation)
Modern GBDT (seperti LightGBM atau XGBoost) mendekati fungsi objektif sembarang dengan ekspansi deret Taylor orde kedua:

$$\tilde{\mathcal{L}}^{(t)} \approx \sum_{i=1}^n \left[ l(y_i, \hat{y}_i^{(t-1)}) + g_i f_t(x_i) + \frac{1}{2} h_i f_t^2(x_i) \right] + \Omega(f_t)$$

di mana gradien orde pertama ($g_i$) dan Hessian orde kedua ($h_i$) dirumuskan sebagai:

$$g_i = \left. \frac{\partial l(y_i, \hat{y})}{\partial \hat{y}} \right|_{\hat{y} = \hat{y}^{(t-1)}}, \quad h_i = \left. \frac{\partial^2 l(y_i, \hat{y})}{\partial \hat{y}^2} \right|_{\hat{y} = \hat{y}^{(t-1)}}$$

Skor kualitas partisi pemisahan (*split gain*) untuk simpul daun (leaf node) dihitung dari agregasi gradien dan Hessian:

$$\mathcal{G}_{\text{split}} = \frac{1}{2} \left[ \frac{\left(\sum_{i \in I_L} g_i\right)^2}{\sum_{i \in I_L} h_i + \lambda} + \frac{\left(\sum_{i \in I_R} g_i\right)^2}{\sum_{i \in I_R} h_i + \lambda} - \frac{\left(\sum_{i \in I} g_i\right)^2}{\sum_{i \in I} h_i + \lambda} \right] - \gamma$$

---

### 3. Why It Matters

Di lingkungan enterprise (finansial, *high-frequency trading*, fraud analytics, *real-time bidding*), kegagalan sistem machine learning umumnya tidak bersumber dari kekurangan algoritma, melainkan dari kesalahan fundamental rekayasa pipeline:

1. **Silent Target Leakage**: Menggunakan informasi global (seperti mean, deviasi standar, atau *target encoding*) yang dihitung sebelum partisi *cross-validation* atau *train-test split*. Akibatnya, metrik validasi offline menunjukkan performa mendekati sempurna ($AUC > 0.98$), namun anjlok total saat *serving* di produksi ($AUC < 0.60$).
2. **Ketiadaan Kalibrasi Probabilitas**: Model GBDT memprioritaskan pemisahan peringkat (*ranking*) data. Probabilitas output dari fungsi sigmoid pada GBDT mentah sering kali terdistorsi dan tidak mencerminkan frekuensi empiris sebenarnya. Jika model memprediksi probabilitas gagal bayar sebesar $0.80$, rasio gagal bayar aktual di dunia nyata sering kali hanya $0.45$. Hal ini berakibat fatal pada perhitungan *Expected Loss* atau *Value-at-Risk* (VaR).
3. **Impedance Mismatch Antara Pelatihan dan Inferensi**: Transformasi data yang ditulis dalam skrip notebook ad-hoc sulit direproduksi pada sistem inferensi berlatensi rendah. Pipeline harus dirancang modular, deterministik, dan dapat diserialisasi secara atomik ke dalam satu artefak inferensi.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur di bawah ini memisahkan secara ketat batas pemrosesan data, validasi partisi, rekayasa fitur bebas kebocoran, *multi-estimator training*, hingga kalibrasi probabilitas dan serialisasi model.

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE ML PIPELINE SYSTEM                                   |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
                                      [Raw Ingestion Layer]
                                   Pandas / Polars DataFrame
                                                  │
                                                  ▼
                                 [Cross-Validation Split Engine]
                           Stratified / Purged-TimeSeries Splitter
                                       ┌──────────┴──────────┐
                                       │                     │
                                [Train Split]         [Validation/Test]
                                       │                     │
                                       ▼                     ▼
             +─────────────────────────────────────────────────────────────+
             |                 Feature Engineering Pipeline                |
             |  (Fitted strictly on Train; Applied symmetrically on Test)  |
             +─────────────────────────────────────────────────────────────+
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
             [Numerical Stream]                [Categorical Stream]
             - RobustWinsorizer                - K-Fold Target Encoder
             - Median Imputer                  - Rare Label Grouping
             - Quantile / Robust Scaler        - Frequency/One-Hot Encoder
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                             [Feature Union Matrix]
                         Scipy CSR Sparse / Dense Numpy
                                       │
                                       ▼
                   +─────────────────────────────────────────+
                   |         Model Estimation Engine         |
                   |   ┌─────────────────┬─────────────────┐ |
                   |   │  ElasticNet GLM │  Histogram GBDT │ |
                   |   │ (L-BFGS/Coord)  │ (Second-Order)  │ |
                   |   └─────────────────┴─────────────────┘ |
                   +─────────────────────────────────────────+
                                       │
                                       ▼
                     [Post-Hoc Probability Calibration]
                   Isotonic Regression / Platt Sigmoid Scaling
                                       │
                                       ▼
                        [Evaluation & Metric Auditing]
                     Brier Score, Expected Calibration Error
                                       │
                                       ▼
                       [Atomic Artifact Serialization]
                       Joblib / ONNX Open Format Export
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Out-of-Fold (OOF) Target Encoding
Target encoding mengganti nilai kategori dengan ekspektasi matematis target $\mathbb{E}[y|x=c]$. Namun, penggunaan rata-rata sederhana akan menimbulkan kebocoran target (*target leakage*) yang parah.

Untuk mencegahnya di dalam pipeline data latih:
1. Data latih dibagi menjadi $K$-folds internal.
2. Nilai encoded untuk instans di fold $k$ dihitung hanya menggunakan fold $\{-k\}$.
3. Diterapkan *additive empirical Bayes smoothing* untuk kategori dengan frekuensi kemunculan rendah:

$$\hat{S}_c = \frac{n_c \cdot \bar{y}_c + m \cdot \bar{y}_{\text{global}}}{n_c + m}$$

di mana $n_c$ adalah jumlah sampel kategori $c$, $\bar{y}_c$ adalah rata-rata target dalam kategori $c$, $\bar{y}_{\text{global}}$ adalah prior global, dan $m$ adalah bobot parameter penghalus (*smoothing factor*).

#### B. Probability Calibration: Platt Scaling vs Isotonic Regression
Model pohon keputusan memaksimalkan pemisahan partisi fitur, bukan keakuratan fungsi densitas probabilitas. Model ini sering menghasilkan prediksi probabilitas yang menumpuk menjauhi batas $0$ dan $1$ atau membentuk distribusi bertangga (*step functions*).

```
Uncalibrated GBDT (Sigmoidal distortion)          Well-Calibrated Output
   Actual P(Y=1)                                   Actual P(Y=1)
       1.0 |            .---                           1.0 |            /
           |           /                                   |           /
           |          /                                    |          / 
       0.5 |         /                                 0.5 |         /  
           |        /                                      |        /   
       0.0 |____.--'                                   0.0 |_______/____
           0.0     0.5     1.0                             0.0     0.5     1.0
             Predicted P                                     Predicted P
```

1. **Platt Scaling (Parametrik)**:
   Melatih regresi logistik univariat pada logit model mentah $\hat{f}(x)$:

   $$P(y=1 | \hat{f}(x)) = \frac{1}{1 + \exp\left(A \hat{f}(x) + B\right)}$$

   Optimal untuk data berukuran kecil atau ketika kurva keandalan (*reliability curve*) terdistorsi secara sigmoidal.

2. **Isotonic Regression (Non-parametrik)**:
   Mencari fungsi monoton naik bertingkat $\hat{m}$ dengan optimisasi *Pool Adjacent Violators Algorithm* (PAVA):

   $$\min_{\hat{m}} \sum_{i=1}^n \left( y_i - \hat{m}(\hat{y}_i) \right)^2 \quad \text{subject to } \hat{m}(\hat{y}_i) \le \hat{m}(\hat{y}_j) \text{ whenever } \hat{y}_i \le \hat{y}_j$$

   Lebih fleksibel dibanding Platt Scaling dan tidak mengasumsikan bentuk kurva tertentu, tetapi rentan terhadap *overfitting* jika ukuran sampel validasi $N < 1000$.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi pipeline produksi menggunakan Python 3.11+. Sistem ini mencakup custom transformer bebas kebocoran, *ColumnTransformer* asinkron, estimasi GBDT/GLM, kalibrasi probabilitas terintegrasi, serta penanganan error yang komprehensif.

```python
"""Enterprise Machine Learning Pipeline Module.

Architectural Standards:
- Fully Scikit-Learn BaseEstimator/TransformerMixin compliant.
- Strict Type Annotations (PEP 484/526/563).
- Zero Global Target Contamination (Strict Out-of-Fold Isolation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

# Konfigurasi logging standar produksi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("EnterpriseMLPipeline")


# =====================================================================
# 1. CUSTOM SCIKIT-LEARN TRANSFORMERS
# =====================================================================

class RobustWinsorizer(BaseEstimator, TransformerMixin):
    """Membatasi nilai ekstrem (outlier) berbasis persentil empiris.
    
    Transformasi ini dilakukan secara terisolasi pada set pelatihan
    untuk mencegah outlier mendistorsi estimasi gradien atau bobot model linear.
    """

    def __init__(self, lower_quantile: float = 0.01, upper_quantile: float = 0.99) -> None:
        if not 0.0 <= lower_quantile < upper_quantile <= 1.0:
            raise ValueError("Batas kuantil tidak valid. Wajib: 0.0 <= lower < upper <= 1.0")
        self.lower_quantile = lower_quantile
        self.upper_quantile = upper_quantile
        self.lower_bounds_: np.ndarray | None = None
        self.upper_bounds_: np.ndarray | None = None
        self.n_features_in_: int = 0

    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Optional[np.ndarray] = None) -> RobustWinsorizer:
        X_arr = np.asarray(X, dtype=np.float64)
        self.n_features_in_ = X_arr.shape[1]
        
        self.lower_bounds_ = np.nanpercentile(X_arr, self.lower_quantile * 100, axis=0)
        self.upper_bounds_ = np.nanpercentile(X_arr, self.upper_quantile * 100, axis=0)
        
        return self

    def transform(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        if self.lower_bounds_ is None or self.upper_bounds_ is None:
            raise RuntimeError("Transformer belum difit. Panggil 'fit' sebelum 'transform'.")
        
        X_arr = np.asarray(X, dtype=np.float64)
        if X_arr.shape[1] != self.n_features_in_:
            raise ValueError(f"Dimensi fitur tidak cocok: Input {X_arr.shape[1]}, Ekspektasi {self.n_features_in_}")
        
        # Eksekusi pemangkasan (clipping) tervektorisasi
        return np.clip(X_arr, self.lower_bounds_, self.upper_bounds_)


class LeakageFreeTargetEncoder(BaseEstimator, TransformerMixin):
    """K-Fold Target Encoder Bebas Kebocoran untuk Variabel Kategorikal Berdimensi Tinggi.
    
    Mekanisme:
    - Selama `fit_transform`: Menggunakan validasi silang K-Fold internal untuk menghitung 
      representasi target out-of-fold secara eksklusif.
    - Selama `transform`: Menggunakan pemetaan smoothed mean global yang dihitung dari keseluruhan 
      data latih.
    """

    def __init__(self, smoothing: float = 10.0, cv_splits: int = 5, random_state: int = 42) -> None:
        self.smoothing = smoothing
        self.cv_splits = cv_splits
        self.random_state = random_state
        self.global_mean_: float = 0.0
        self.mapping_: Dict[int, Dict[Any, float]] = {}
        self.feature_names_in_: List[str] = []

    def _compute_smoothed_mean(self, count: int, mean: float) -> float:
        return (count * mean + self.smoothing * self.global_mean_) / (count + self.smoothing)

    def fit(self, X: pd.DataFrame, y: Union[pd.Series, np.ndarray]) -> LeakageFreeTargetEncoder:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        
        y_arr = np.asarray(y, dtype=np.float64)
        if len(X) != len(y_arr):
            raise ValueError("Panjang baris X dan target y tidak sinkron.")
            
        self.feature_names_in_ = list(X.columns)
        self.global_mean_ = float(np.mean(y_arr))
        self.mapping_ = {}

        for col_idx, col in enumerate(self.feature_names_in_):
            series = X[col]
            categories = series.unique()
            col_mapping: Dict[Any, float] = {}
            
            for cat in categories:
                cat_mask = (series == cat).to_numpy()
                n_samples = np.sum(cat_mask)
                if n_samples > 0:
                    empirical_mean = np.mean(y_arr[cat_mask])
                    col_mapping[cat] = self._compute_smoothed_mean(n_samples, empirical_mean)
                else:
                    col_mapping[cat] = self.global_mean_
                    
            self.mapping_[col_idx] = col_mapping

        return self

    def fit_transform(self, X: pd.DataFrame, y: Union[pd.Series, np.ndarray]) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
        
        y_arr = np.asarray(y, dtype=np.float64)
        self.feature_names_in_ = list(X.columns)
        self.global_mean_ = float(np.mean(y_arr))
        
        # Panggil fit untuk membangun pemetaan global inferensi
        self.fit(X, y_arr)

        transformed_matrix = np.empty((len(X), len(self.feature_names_in_)), dtype=np.float64)
        splitter = StratifiedKFold(n_splits=self.cv_splits, shuffle=True, random_state=self.random_state)

        for col_idx, col in enumerate(self.feature_names_in_):
            col_series = X[col]
            encoded_col = np.empty(len(X), dtype=np.float64)
            
            for train_idx, val_idx in splitter.split(X, y_arr.astype(int)):
                train_fold_series = col_series.iloc[train_idx]
                train_fold_y = y_arr[train_idx]
                val_fold_series = col_series.iloc[val_idx]

                fold_global_mean = float(np.mean(train_fold_y))
                
                # Agregasi empiris fold latih
                stats = train_fold_y_grouped = pd.DataFrame({
                    "val": train_fold_series,
                    "target": train_fold_y
                }).groupby("val")["target"].agg(["count", "mean"])
                
                # Transformasi fold validasi secara terisolasi
                def map_category(val: Any) -> float:
                    if val in stats.index:
                        n = stats.loc[val, "count"]
                        m = stats.loc[val, "mean"]
                        return (n * m + self.smoothing * fold_global_mean) / (n + self.smoothing)
                    return fold_global_mean

                encoded_col[val_idx] = val_fold_series.map(map_category).to_numpy()

            transformed_matrix[:, col_idx] = encoded_col

        return transformed_matrix

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)
            
        output = np.empty((len(X), len(self.feature_names_in_)), dtype=np.float64)
        for col_idx, col in enumerate(self.feature_names_in_):
            col_series = X[col]
            mapping = self.mapping_[col_idx]
            
            # Map kategori; gunakan global_mean_ jika kategori unseen
            mapped_values = col_series.map(mapping).fillna(self.global_mean_).to_numpy()
            output[:, col_idx] = mapped_values
            
        return output


# =====================================================================
# 2. PIPELINE ORCHESTRATION & CONFIGURATION
# =====================================================================

@dataclass(frozen=True)
class PipelineConfig:
    numeric_features: List[str]
    categorical_features: List[str]
    model_type: str = "gbdt"  # Alternatif: "elasticnet"
    calibration_method: str = "isotonic"  # Alternatif: "sigmoid"
    cv_folds: int = 5
    random_seed: int = 42


class EnterpriseInferencePipeline:
    """Manajer orkestrasi siklus hidup model produksi."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.pipeline: Pipeline | None = None
        self._is_fitted: bool = False

    def _build_preprocessor(self) -> ColumnTransformer:
        numeric_pipeline = Pipeline(steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("winsorizer", RobustWinsorizer(lower_quantile=0.01, upper_quantile=0.99)),
            ("scaler", RobustScaler(with_centering=True, with_scaling=True)),
        ])

        categorical_pipeline = Pipeline(steps=[
            ("target_encoder", LeakageFreeTargetEncoder(
                smoothing=15.0, 
                cv_splits=self.config.cv_folds, 
                random_state=self.config.random_seed
            )),
            ("scaler", RobustScaler()),
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_pipeline, self.config.numeric_features),
                ("cat", categorical_pipeline, self.config.categorical_features),
            ],
            remainder="drop",
            n_jobs=None,  # Thread-safety deterministik
        )
        return preprocessor

    def _instantiate_base_estimator(self) -> Union[ClassifierMixin, BaseEstimator]:
        if self.config.model_type == "gbdt":
            return HistGradientBoostingClassifier(
                loss="log_loss",
                learning_rate=0.05,
                max_iter=300,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                l2_regularization=1.5,
                random_state=self.config.random_seed,
            )
        elif self.config.model_type == "elasticnet":
            return LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                l1_ratio=0.5,
                C=0.1,
                max_iter=1000,
                random_state=self.config.random_seed,
            )
        else:
            raise NotImplementedError(f"Tipe model '{self.config.model_type}' tidak didukung.")

    def build_and_fit(self, X: pd.DataFrame, y: np.ndarray) -> EnterpriseInferencePipeline:
        logger.info("Menginisialisasi perakitan pipeline...")
        preprocessor = self._build_preprocessor()
        base_estimator = self._instantiate_base_estimator()

        # Kalibrasi probabilitas menggunakan Cross-Validation internal
        calibrated_model = CalibratedClassifierCV(
            estimator=base_estimator,
            method=self.config.calibration_method,
            cv=self.config.cv_folds,
        )

        full_pipeline = Pipeline(steps=[
            ("preprocessor", preprocessor),
            ("calibrated_classifier", calibrated_model),
        ])

        logger.info("Memulai fitting pipeline secara terintegrasi...")
        full_pipeline.fit(X, y)
        self.pipeline = full_pipeline
        self._is_fitted = True
        logger.info("Pelatihan pipeline dan kalibrasi probabilitas selesai.")
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self._is_fitted or self.pipeline is None:
            raise RuntimeError("Pipeline inferensi belum dilatih.")
        return self.pipeline.predict_proba(X)[:, 1]

    def evaluate(self, X_test: pd.DataFrame, y_test: np.ndarray) -> Dict[str, float]:
        probabilities = self.predict_proba(X_test)
        auc = float(roc_auc_score(y_test, probabilities))
        brier = float(brier_score_loss(y_test, probabilities))
        logloss = float(log_loss(y_test, probabilities))

        metrics = {
            "ROC_AUC": auc,
            "Brier_Score": brier,
            "Log_Loss": logloss,
        }
        logger.info(f"Metrik Evaluasi: {metrics}")
        return metrics


# =====================================================================
# 3. VERIFIKASI EKSEKUSI PIPELINE
# =====================================================================

if __name__ == "__main__":
    np.random.seed(42)
    sample_size = 10_000

    # Sintesis dataset finansial semi-realistis
    df_raw = pd.DataFrame({
        "credit_score": np.random.normal(loc=650, scale=80, size=sample_size),
        "debt_to_income": np.random.exponential(scale=0.3, size=sample_size),
        "outlier_balance": np.concatenate([
            np.random.normal(5000, 1000, size=sample_size - 50),
            np.random.uniform(500_000, 1_000_000, size=50) # Outlier ekstrem
        ]),
        "employment_type": np.random.choice(["SALARIED", "SELF_EMPLOYED", "UNEMPLOYED", "GIG_WORKER"], size=sample_size),
        "geo_region": np.random.choice([f"REGION_{i}" for i in range(50)], size=sample_size),
    })

    # Pembentukan label probabilistik biner (Gagal Bayar)
    latent_signal = (
        -0.01 * df_raw["credit_score"]
        + 3.5 * df_raw["debt_to_income"]
        + (df_raw["employment_type"] == "UNEMPLOYED").astype(int) * 1.5
    )
    p_true = 1 / (1 + np.exp(-latent_signal))
    y_raw = np.random.binomial(1, p_true)

    # Pemisahan Train/Test
    split_idx = int(sample_size * 0.8)
    X_train, X_test = df_raw.iloc[:split_idx], df_raw.iloc[split_idx:]
    y_train, y_test = y_raw[:split_idx], y_raw[split_idx:]

    config = PipelineConfig(
        numeric_features=["credit_score", "debt_to_income", "outlier_balance"],
        categorical_features=["employment_type", "geo_region"],
        model_type="gbdt",
        calibration_method="isotonic",
        cv_folds=5,
    )

    inference_engine = EnterpriseInferencePipeline(config)
    inference_engine.build_and_fit(X_train, y_train)
    evaluation_metrics = inference_engine.evaluate(X_test, y_test)

    # Validasi sanity check out-of-fold inference
    sample_inference = inference_engine.predict_proba(X_test.iloc[:5])
    print(f"\nProbabilitas Terkalibrasi (5 Sampel Pertama):\n{sample_inference}")
```

---

### 7. Edge Cases & Failure Modes

Dalam skala produksi tingkat tinggi, arsitektur pipeline dapat mengalami kegagalan struktural non-obvious:

1. **Unseen Categorical Levels pada Cold-Start**:
   - *Mode Kegagalan*: Variabel kategorikal berdimensi tinggi menghasilkan level unik di data inferensi yang tidak pernah muncul di set pelatihan.
   - *Mitigasi*: `LeakageFreeTargetEncoder` menyertakan fallback default ke `global_mean_` jika pemetaan tidak ditemukan di kamus (`fillna(self.global_mean_)`).
2. **Zero Hessian Singularity pada Custom GBDT Objectives**:
   - *Mode Kegagalan*: Ketika mengimplementasikan fungsi loss kustom, Hessian $h_i$ dapat mendekati nol untuk observasi dengan konfidensi tinggi ($p \to 0$ atau $p \to 1$). Pembagian dengan nol pada penyebut rumus *split gain* $\frac{G^2}{H + \lambda}$ menyebabkan overflow komputasi (*NaN gradients*).
   - *Mitigasi*: Menambahkan nilai epsilon pengaman ($\epsilon = 10^{-6}$) atau regularisasi penalti $\lambda \ge 1.0$ secara permanen pada penyebut Hessian.
3. **Data Contamination pada Imputasi Multivariat**:
   - *Mode Kegagalan*: Menjalankan transformasi imputasi multivariat (misalnya `IterativeImputer` atau `KNNImputer`) langsung pada seluruh matriks sebelum pemisahan lipatan (cross-validation folds).
   - *Mitigasi*: Enkapsulasi seluruh proses imputasi ke dalam objek `Pipeline` Scikit-Learn. Parameter median/mean murni dihitung dari data latih internal fold dan diaplikasikan tanpa modifikasi pada fold uji.
4. **Target Shift & Nilai Ekstrem (Extreme Out-of-Bounds Drift)**:
   - *Mode Kegagalan*: Model pohon (tree-based models) tidak mampu melakukan ekstrapolasi linear di luar batas minimum dan maksimum data latih. Nilai fitur numerik baru yang jauh lebih besar akan menghasilkan prediksi daun yang sama.
   - *Mitigasi*: Penerapan `RobustWinsorizer` membatasi deviasi nilai eksternal ke dalam rentang persentil yang terkontrol, menghindari lonjakan kesalahan numerik pada representasi internal model.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Regularized GLM (ElasticNet) | Modern GBDT (LightGBM/HistGBDT) | Deep Tabular (FT-Transformer/TabNet) |
| :--- | :--- | :--- | :--- |
| **Batas Keputusan (*Decision Boundary*)** | Linear Hyperplane global. | Partisi ortogonal bertingkat (*axis-aligned*). | Komposisi manifold non-linear adaptif. |
| **Latensi Inferensi (p99)** | **Sub-milidetik** ($< 0.1\text{ ms}$ via perkalian dot produk). | **Sangat Rendah** ($1 - 5\text{ ms}$). | **Tinggi** ($15 - 50\text{ ms}$, memerlukan akselerator GPU/TensorRT). |
| **Efisiensi Data Berukuran Kecil** | Sangat Kuat ($N < 1.000$ stabil dengan penalti L1/L2). | Cenderung mudah overfit tanpa *early stopping* dan regularisasi. | Buruk; memerlukan regularisasi intensif & data $N > 100.000$. |
| **Sensitivitas Terhadap Skala Fitur** | **Sangat Tinggi** (Membutuhkan standardisasi/skala robust). | **Kebal** (Invarian terhadap transformasi monotonik). | **Tinggi** (Wajib dinormalisasi). |
| **Fitur Kategorikal Kardinalitas Tinggi** | Memerlukan One-Hot (meningkatkan dimensi matriks sparse). | Sangat Efisien (via target encoding tervektorisasi atau algoritma histogram). | Membutuhkan *Entity Embeddings*. |
| **Sifat Kalibrasi Probabilitas** | Secara intrinsik mendekati kurva logistik optimal. | Sering kali terdistorsi; **wajib** melalui tahap kalibrasi pasca-latih. | Cenderung *overconfident*; membutuhkan kalibrasi suhu (*temperature scaling*). |

---

### 9. Best Practices & Standard Industri

1. **Deterministik Secara Penuh (Bitwise Reproducibility)**:
   - Tetapkan `random_state` secara eksplisit di seluruh komponen (splitter, encoder, estimator).
   - Hindari operasi multithreading non-deterministik saat menghitung histogram gradien pada CPU jika reproduktibilitas mutlak diperlukan untuk kepatuhan regulasi (seperti regulasi perbankan Basel III/IV).
2. **Serialisasi Model yang Aman dan Terisolasi**:
   - Hindari penggunaan `pickle` mentah untuk transmisi model antar-jaringan karena risiko eksekusi kode arbitrer (*remote code execution*).
   - Gunakan format terbuka seperti **ONNX** (*Open Neural Network Exchange*) atau **Treelite** untuk model berbasis pohon, yang mengompilasi pohon keputusan menjadi representasi native C/C++ yang bebas dari dependensi library Python.
3. **Pemisahan Validasi Temporal (Purged & Blocked CV)**:
   - Jika data memiliki dependensi waktu (*time-series*, *financial tick data*), dilarang keras menggunakan `KFold` acak standar.
   - Terapkan skema `TimeSeriesSplit` dengan periode embargo (*purging*) untuk mencegah kebocoran informasi masa depan (*lookahead bias*) akibat korelasi serial pada variabel target.
4. **Metrik Keandalan Probabilitas (Brier Score Auditing)**:
   - Jangan hanya mengandalkan ROC-AUC untuk mengevaluasi model klasifikasi. ROC-AUC hanya mengukur kemampuan pemeringkatan (*rank-ordering*), bukan validitas probabilitas.
   - Evaluasi performa model menggunakan dekomposisi **Brier Score**:

$$\text{Brier Score} = \text{Reliability} - \text{Resolution} + \text{Uncertainty}$$

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus
Sebuah institusi perbankan digital mengalami lonjakan kerugian finansial akibat gagal bayar pinjaman mikro (*unsecured micro-lending*). Sistem inferensi yang lama memiliki dua masalah utama:
1. Probabilitas yang dihasilkan tidak terkalibrasi: model menghasilkan probabilitas rata-rata $0.12$, padahal rasio gagal bayar aktual di populasi mencapai $0.28$.
2. Terjadi kebocoran target pada sistem transformasi fitur kategorikal internal, menyebabkan performa model di lingkungan staging tampak tinggi ($AUC = 0.94$), namun jatuh saat inferensi langsung di sistem produksi ($AUC = 0.67$).

Tugas Anda: Membangun pipeline inferensi Scikit-Learn yang aman secara statistik dan tahan terhadap kebocoran data.

#### Langkah Pengerjaan

1. **Persiapan Lingkungan**:
   Buat virtual environment baru dan install dependensi:
   ```bash
   pip install numpy pandas scikit-learn
   ```

2. **Eksekusi Validasi Silang**:
   Simpan kode dari Section 6 ke dalam file bernama `enterprise_ml_pipeline.py`. Jalankan program dan amati metrik yang dihasilkan:
   ```bash
   python enterprise_ml_pipeline.py
   ```

3. **Uji Kasus Khusus: Verifikasi Ketiadaan Data Leakage**:
   Tulis file pengujian `test_leakage.py` untuk membuktikan bahwa `LeakageFreeTargetEncoder` tidak membocorkan data target pada set validasi:

   ```python
   import numpy as np
   import pandas as pd
   from enterprise_ml_pipeline import LeakageFreeTargetEncoder

   def test_target_encoder_zero_leakage():
       # Buat data kategorikal acak dengan satu kategori langka
       df = pd.DataFrame({"cat": ["A"] * 99 + ["LEAK_TEST"]})
       y = np.zeros(100)
       y[-1] = 1.0  # Satu-satunya label positif ada pada LEAK_TEST

       encoder = LeakageFreeTargetEncoder(smoothing=1.0, cv_splits=2, random_state=42)
       # Jalankan fit_transform out-of-fold
       transformed = encoder.fit_transform(df, y)

       # Jika terjadi kebocoran data, fold validasi yang memuat 'LEAK_TEST'
       # akan memiliki nilai encode mendekati 1.0.
       # Jika bebas kebocoran, nilai encode untuk sampel tersebut harus mencerminkan prior global
       # dari fold seberangnya.
       print("Hasil Uji Kebocoran Target Encoding:")
       print(f"Encoded value for rare category: {transformed[-1, 0]:.4f}")
       print(f"Global mean prior: {encoder.global_mean_:.4f}")
       
       assert transformed[-1, 0] <= encoder.global_mean_, "Deteksi Kebocoran Target: Nilai melampaui prior global!"
       print("[STATUS] Verifikasi Lolos: Pipeline aman dari kebocoran target.")

   if __name__ == "__main__":
       test_target_encoder_zero_leakage()
   ```

4. **Eksperimen Model**:
   Buka file `enterprise_ml_pipeline.py`, ubah konfigurasi model dari GBDT ke ElasticNet:
   ```python
   config = PipelineConfig(
       numeric_features=["credit_score", "debt_to_income", "outlier_balance"],
       categorical_features=["employment_type", "geo_region"],
       model_type="elasticnet",
       calibration_method="sigmoid",
       cv_folds=5,
   )
   ```
   Jalankan kembali pipeline. Amati perbedaan metrik `ROC_AUC` dan `Brier_Score`. Perhatikan bagaimana regularisasi $L_1$ pada ElasticNet secara otomatis mengeliminasi bobot fitur yang tidak relevan.

#### Output yang Diharapkan
- Script berhasil mengeksekusi pipeline tanpa error runtime.
- Metrik validasi menunjukkan `ROC_AUC` di atas $0.75$, dengan nilai `Brier_Score` di bawah $0.15$ (menandakan probabilitas yang terkalibrasi dengan baik).
- Pengujian isolasi pada `test_leakage.py` menghasilkan status verifikasi lolos tanpa indikasi kebocoran data (*zero target leakage*).