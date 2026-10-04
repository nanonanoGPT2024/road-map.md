# Bab 03: Classical Supervised Learning Regression & Classification
## Modul 01: Linear Models, Regularization, and Generalized Linear Models (GLMs)

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis dan Memilih Formulasi Matematis**: Memilih antara solusi *closed-form* (Ordinary Least Squares/Normal Equation) dan optimasi numerik (*Iterative Gradient-Based Optimization*) berdasarkan kompleksitas dimensi data ($\mathcal{O}(d^3)$ vs $\mathcal{O}(knd)$).
- **Mengimplementasikan Regularisasi L1/L2/ElasticNet**: Menjelaskan geometri *penalty terms* dan dampaknya terhadap *sparsity* bobot parameter serta mereduksi *variance* pada data berdimensi tinggi ($p \gg n$).
- **Merancang Estimator Klasifikasi Probabilistik**: Menurunkan fungsi *Binary Cross-Entropy Loss* (Log-Loss) dari prinsip *Maximum Likelihood Estimation* (MLE) dan mengimplementasikan model *Multinomial Logistic Regression* (*Softmax*).
- **Membangun Pipeline Standar Enterprise**: Mengembangkan pipeline Scikit-Learn kustom yang mencakup validasi data runtime (*Pydantic*), penanganan multikolinearitas (VIF), rekayasa fitur linier, dan inferensi dengan latensi $< 5 \text{ ms}$.
- **Mengevaluasi Metrik Kinerja Klinis & Finansial**: Mengonfigurasi trade-off *Precision-Recall*, kalibrasi probabilitas (*Platt Scaling* & *Isotonic Regression*), dan metrik regresi terbobot (*Huber Loss*, *MAPE*, *RMSE*).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Model linier memetakan relasi antara vektor fitur input $\mathbf{x} \in \mathbb{R}^d$ dengan target output $y \in \mathbb{R}$ melalui kombinasi affine yang dibatasi oleh parameter bobot $\mathbf{w} \in \mathbb{R}^d$ dan bias $b \in \mathbb{R}$:

$$\hat{y} = \mathbf{w}^T \mathbf{x} + b$$

#### Mental Model: Proyeksi Geometris dan Pemisahan Hyperplane
Secara geometris, **Ordinary Least Squares (OLS)** memproyeksikan vektor target $\mathbf{y}$ secara ortogonal ke dalam *column space* yang dibentuk oleh matriks desain $\mathbf{X}$. Residual error $\mathbf{e} = \mathbf{y} - \hat{\mathbf{y}}$ ortogonal terhadap subspace tersebut, menjamin minimisasi jarak Euclidean $\|\mathbf{e}\|_2^2$.

Pada klasifikasi biner, model linier bertindak sebagai **Hyperplane Decision Boundary**:
$$\mathcal{H} = \{\mathbf{x} \in \mathbb{R}^d \mid \mathbf{w}^T \mathbf{x} + b = 0\}$$
Ruang fitur dibagi menjadi dua *half-spaces*. Jarak bertanda (*signed distance*) dari titik data ke hyperplane menentukan tingkat keyakinan kelas, yang kemudian dipetakan ke interval probabilitas $[0, 1]$ melalui fungsi aktivasi non-linier $\sigma(z)$ (*sigmoid link function*).

#### Generalized Linear Models (GLM)
Model linier klasik mengasumsikan distribusi residual berdistribusi normal dengan varians konstan (*homoscedasticity*). GLM memperluas paradigma ini ke kelas distribusi *Exponential Dispersion Family* (Gaussian, Bernoulli, Poisson, Gamma):
1. **Random Component**: Variabel target $y$ mengikuti distribusi dalam rumpun eksponensial dengan rata-rata $\mu = \mathbb{E}[y \mid \mathbf{x}]$.
2. **Systematic Component**: Prediktor linier $\eta = \mathbf{w}^T \mathbf{x} + b$.
3. **Link Function $g(\cdot)$**: Fungsi monotonik yang menghubungkan rata-rata ke prediktor linier: $\eta = g(\mu) \iff \mu = g^{-1}(\eta)$.
   - Regresi Linier: Gaussian family, $g(\mu) = \mu$ (*Identity link*).
   - Regresi Logistik: Bernoulli family, $g(\mu) = \ln\left(\frac{\mu}{1 - \mu}\right)$ (*Logit link*).

---

### 3. Why It Matters (Kebutuhan Enterprise)

Dalam lanskap produksi modern yang didominasi oleh arsitektur Deep Learning dan Ensemble Trees (XGBoost/LightGBM), model linier dan GLM tetap menjadi fondasi arsitektur mission-critical karena:

1. **Persyaratan Regulasi & Kepatuhan Audit (Explainability)**:
   - Sektor perbankan (kredit skoring di bawah Fair Lending Act / regulasi OJK) dan instrumen medis mewajibkan atribusi kausal yang transparan. Koefisien $\beta_j$ merepresentasikan efek marjinal langsung fitur $j$ terhadap log-odds target, *ceteris paribus*.
2. **Latensi Inferensi Ultra-Rendah (Sub-millisecond SLA)**:
   - Evaluasi inferensi model linier tereduksi menjadi operasi perkalian dot-product $\mathbf{w}^T \mathbf{x}$, yang dapat dieksekusi dalam skala nanodetik menggunakan instruksi CPU SIMD (AVX-512) tanpa akselerator GPU. Sangat krusial untuk *Real-Time Bidding* (RTB) dan *High-Frequency Trading* (HFT).
3. **Kekebalan terhadap Overfitting pada Data Sparse Berdimensi Tinggi**:
   - Dalam pemrosesan teks (*Bag of Words/TF-IDF*) atau bioinformatika (genomics), jumlah fitur $p$ sering kali jauh melampaui jumlah sampel $n$ ($p \gg n$). Regularisasi $L_1$ dan $L_2$ mencegah ledakan varians estimator di mana arsitektur non-parametrik gagal total.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan data, optimasi, dan inferensi GLM kelas enterprise dengan regularisasi dan proteksi runtime:

```
[ Ingestion Raw Features ]
           │
           ▼
┌──────────────────────────────────────────────┐
│  Validation & Schema Layer (Pydantic/Pandera)│
│  - NaN Detection / Type Checking             │
│  - Extreme Outlier Thresholding              │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Feature Transformation Engine               │
│  - RobustScaler / QuantileTransformer         │
│  - Multicollinearity Handling (VIF Filter)   │
│  - Polynomial / Interaction Terms            │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Core GLM Estimator Layer                    │
│  ┌────────────────────────────────────────┐  │
│  │ Objective: L(w) + λ1||w||1 + λ2||w||2^2│  │
│  └───────────────────┬────────────────────┘  │
│                      │                       │
│        ┌─────────────┴─────────────┐         │
│        ▼                           ▼         │
│  [OLS / Closed-Form]      [Numerical Solver] │
│  (X^T X + λI)^(-1) X^T y  (L-BFGS / SAG / SGD│
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Probability Calibration & Post-Processing   │
│  - Platt Scaling (Logistic Sigmoid Fit)      │
│  - Optimal Decision Threshold Optimizer      │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Deployment & Serving Target                 │
│  - Output: Point Estimate + Confidence Bounds│
│  - Latency: < 2ms (SIMD Dot Product)         │
└──────────────────────────────────────────────┘
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Ordinary Least Squares (OLS) & Regularisasi
Fungsi rugi (*Loss Function*) OLS dinyatakan sebagai:
$$J(\mathbf{w}) = \frac{1}{2n} \|\mathbf{y} - \mathbf{X}\mathbf{w}\|_2^2 = \frac{1}{2n} (\mathbf{y} - \mathbf{X}\mathbf{w})^T (\mathbf{y} - \mathbf{X}\mathbf{w})$$

Mengambil gradien parsial terhadap $\mathbf{w}$ dan menyamakannya ke 0:
$$\nabla_{\mathbf{w}} J(\mathbf{w}) = -\frac{1}{n} \mathbf{X}^T (\mathbf{y} - \mathbf{X}\mathbf{w}) = 0 \implies \mathbf{X}^T \mathbf{X} \mathbf{w} = \mathbf{X}^T \mathbf{y}$$

Jika $\mathbf{X}^T \mathbf{X}$ *full-rank* (non-singular), estimasi bobot diperoleh melalui **Normal Equation**:
$$\hat{\mathbf{w}} = (\mathbf{X}^T \mathbf{X})^{-1} \mathbf{X}^T \mathbf{y}$$

##### Masalah Multikolinearitas & Solusi Ridge (L2)
Jika fitur berkorelasi tinggi, $\det(\mathbf{X}^T \mathbf{X}) \approx 0$, nilai eigen minimum mendekati nol, menyebabkan varians estimasi meledak: $\operatorname{Var}(\hat{\mathbf{w}}) = \sigma^2 (\mathbf{X}^T \mathbf{X})^{-1}$.

**Ridge Regression (Tikhonov Regularization)** menambahkan penalti kuadratik:
$$J_{\text{Ridge}}(\mathbf{w}) = \frac{1}{2n} \|\mathbf{y} - \mathbf{X}\mathbf{w}\|_2^2 + \lambda \|\mathbf{w}\|_2^2$$
$$\hat{\mathbf{w}}_{\text{Ridge}} = (\mathbf{X}^T \mathbf{X} + 2n\lambda \mathbf{I})^{-1} \mathbf{X}^T \mathbf{y}$$
Matriks $(\mathbf{X}^T \mathbf{X} + 2n\lambda \mathbf{I})$ selalu *invertible* (strictly positive definite), mereduksi varians secara signifikan dengan sedikit kompensasi peningkatan bias (*Bias-Variance Trade-off*).

##### Solusi Lasso (L1) & Sparsitas
**Lasso Regression** menggunakan penalti nilai absolut:
$$J_{\text{Lasso}}(\mathbf{w}) = \frac{1}{2n} \|\mathbf{y} - \mathbf{X}\mathbf{w}\|_2^2 + \alpha \|\mathbf{w}\|_1$$
Karena fungsi $\|\mathbf{w}\|_1$ non-diferensiabel di $w_j = 0$, turunan diselesaikan via **Subgradient Optimization** atau **Coordinate Descent**. Operator *Soft-Thresholding* untuk koordinat terisolasi didefinisikan sebagai:
$$S(z, \gamma) = \operatorname{sign}(z) \max(0, |z| - \gamma)$$
Karakteristik sudut tajam (*pointy contours*) kontur $L_1$ memotong ruang rugi kuadratik pada sumbu axis, mengeliminasi koefisien menjadi tepat nol secara deterministik (*automatic feature selection*).

```
Kontur Rugi OLS vs Penalti Regularisasi:

       w2 ^                                   w2 ^
          │      /\                              │   ┌───────┐
          │     /  \                             │  /    │    \
     ─────┼────/────\─────> w1              ─────┼──(─────┼─────)───> w1
          │   /      \                           │  \    │    /
          │   \      /                           │   └───────┘
          │    \    /                            │
          │     \/                               │
       Lasso (L1): Sudut tajam               Ridge (L2): Bola mulus
       Solusi optimal menyentuh axis         Solusi mendekati tapi != 0
```

#### 5.2 Logistic Regression & Optimasi Numerik
Diberikan himpunan data biner $\mathcal{D} = \{(\mathbf{x}_i, y_i)\}_{i=1}^n$ di mana $y_i \in \{0, 1\}$. Probabilitas posterior dimodelkan via Sigmoid Link:
$$P(y = 1 \mid \mathbf{x}; \mathbf{w}) = \sigma(\mathbf{w}^T \mathbf{x}) = \frac{1}{1 + e^{-\mathbf{w}^T \mathbf{x}}}$$

Fungsi Likelihood:
$$L(\mathbf{w}) = \prod_{i=1}^n \left[\sigma(\mathbf{w}^T \mathbf{x}_i)\right]^{y_i} \left[1 - \sigma(\mathbf{w}^T \mathbf{x}_i)\right]^{1 - y_i}$$

Mengambil negatif log-likelihood menghasilkan **Binary Cross-Entropy Loss** yang bersifat cembung (*strictly convex*):
$$J(\mathbf{w}) = -\frac{1}{n} \sum_{i=1}^n \left[ y_i \ln \sigma(\mathbf{w}^T \mathbf{x}_i) + (1 - y_i) \ln (1 - \sigma(\mathbf{w}^T \mathbf{x}_i)) \right]$$

Gradien parsial terhadap $\mathbf{w}$:
$$\nabla_{\mathbf{w}} J(\mathbf{w}) = \frac{1}{n} \mathbf{X}^T (\sigma(\mathbf{X}\mathbf{w}) - \mathbf{y})$$

Hessian matrix:
$$\mathbf{H} = \frac{1}{n} \mathbf{X}^T \mathbf{R} \mathbf{X}$$
Di mana $\mathbf{R}$ adalah matriks diagonal dengan elemen $R_{ii} = \sigma(\mathbf{w}^T \mathbf{x}_i) (1 - \sigma(\mathbf{w}^T \mathbf{x}_i))$. Karena $\mathbf{R}_{ii} > 0$, matriks $\mathbf{H}$ bersifat *positive semi-definite*, menjamin konvergensi global menggunakan algoritma optimasi orde kedua seperti **Newton-Raphson** (*Iteratively Reweighted Least Squares / IRLS*) atau kuasi-Newton seperti **L-BFGS**:
$$\mathbf{w}^{(t+1)} = \mathbf{w}^{(t)} - \mathbf{H}^{-1} \nabla J(\mathbf{w}^{(t)})$$

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul inferensi & pelatihan enterprise-grade yang mengombinasikan deteksi multikolinearitas (VIF), *ElasticNet logistic objective*, validasi skema runtime dengan Pydantic, dan kalibrasi probabilitas.

```python
"""
production_glm.py
Enterprise-grade Regularized Logistic Regression Engine with Schema Enforcement,
Multicollinearity Pruning, and Isotonic Calibration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import RobustScaler

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("EnterpriseGLM")


# ---------------------------------------------------------
# 1. Runtime Data Contract Definitions (Pydantic)
# ---------------------------------------------------------

class InferencePayload(BaseModel):
    """Skema input inferensi individual."""
    account_age_months: float = Field(..., ge=0.0, description="Umur akun dalam bulan")
    transaction_count_30d: float = Field(..., ge=0.0, description="Total transaksi 30 hari")
    debt_to_income_ratio: float = Field(..., ge=0.0, le=10.0, description="DTI Ratio")
    average_login_frequency: float = Field(..., ge=0.0, description="Frekuensi login mingguan")


class BatchInferenceRequest(BaseModel):
    """Batch payload untuk high-throughput processing."""
    records: List[InferencePayload]


# ---------------------------------------------------------
# 2. Custom Pipeline Components
# ---------------------------------------------------------

class MulticollinearityPruner(BaseEstimator):
    """
    Menghitung dan memangkas fitur yang memiliki Variance Inflation Factor (VIF)
    tinggi untuk memastikan kestabilan koefisien model linier.
    """
    def __init__(self, threshold: float = 5.0):
        self.threshold = threshold
        self.dropped_features_: List[str] = []
        self.retained_features_: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> MulticollinearityPruner:
        current_cols = list(X.columns)
        
        while True:
            if len(current_cols) <= 1:
                break
            
            # Hitung matriks korelasi dan inversnya untuk pendekatan VIF cepat
            corr = X[current_cols].corr().values
            try:
                inv_corr = np.linalg.inv(corr)
                vif = np.diag(inv_corr)
            except np.linalg.LinAlgError:
                # Singular matrix implies infinite VIF
                vif = np.full(len(current_cols), np.inf)

            max_vif_idx = np.argmax(vif)
            max_vif = vif[max_vif_idx]

            if max_vif > self.threshold:
                dropped_col = current_cols.pop(max_vif_idx)
                self.dropped_features_.append(dropped_col)
                logger.warning("Memangkas fitur multikolinearitas: %s (VIF: %.2f)", dropped_col, max_vif)
            else:
                break
                
        self.retained_features_ = current_cols
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return X[self.retained_features_].copy()


# ---------------------------------------------------------
# 3. Main Model Pipeline Architecture
# ---------------------------------------------------------

@dataclass
class Hyperparameters:
    l1_ratio: float = 0.5  # ElasticNet balance (0 = L2, 1 = L1)
    C: float = 1.0         # Inverse regularization strength
    max_iter: int = 1000
    tol: float = 1e-4
    solver: str = "saga"   # Mendukung ElasticNet & multinomial loss


class EnterpriseRiskClassifier(ClassifierMixin, BaseEstimator):
    """
    Pipeline klasifikasi end-to-end dengan penskalaan robust, pemangkasan VIF,
    estimasi ElasticNet, dan kalibrasi isotonik.
    """
    def __init__(self, config: Optional[Hyperparameters] = None):
        self.config = config or Hyperparameters()
        self.pruner = MulticollinearityPruner(threshold=7.0)
        self.scaler = RobustScaler()
        self.base_classifier = LogisticRegression(
            penalty="elasticnet",
            l1_ratio=self.config.l1_ratio,
            C=self.config.C,
            solver=self.config.solver,
            max_iter=self.config.max_iter,
            tol=self.config.tol,
            random_state=42
        )
        self.calibrated_model: Optional[CalibratedClassifierCV] = None
        self.feature_names_: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> EnterpriseRiskClassifier:
        logger.info("Memulai fitting EnterpriseRiskClassifier. Data Shape: %s", X.shape)
        
        # 1. Prune Multicollinearity
        X_pruned = self.pruner.fit_transform(X)
        self.feature_names_ = list(X_pruned.columns)

        # 2. Scale Features
        X_scaled = self.scaler.fit_transform(X_pruned)

        # 3. Probabilistic Calibration via Isotonic Regression
        logger.info("Melakukan cross-validation calibration (Isotonic)...")
        self.calibrated_model = CalibratedClassifierCV(
            estimator=self.base_classifier,
            method="isotonic",
            cv=3
        )
        self.calibrated_model.fit(X_scaled, y)
        logger.info("Model berhasil dilatih dan dikalibrasi.")
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.calibrated_model is None:
            raise RuntimeError("Model belum di-fit. Jalankan 'fit' terlebih dahulu.")
        
        X_pruned = self.pruner.transform(X)
        X_scaled = self.scaler.transform(X_pruned)
        return self.calibrated_model.predict_proba(X_scaled)

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        probas = self.predict_proba(X)[:, 1]
        return (probas >= threshold).astype(np.int32)

    def explain(self) -> Dict[str, float]:
        """Mengekstraksi bobot rata-rata estimator dasar untuk interpretasi fitur."""
        if not self.calibrated_model:
            raise ValueError("Model belum di-fit.")
            
        coefficients = []
        for calibrated_classifier in self.calibrated_model.calibrated_classifiers_:
            coefficients.append(calibrated_classifier.estimator.coef_[0])
            
        avg_weights = np.mean(coefficients, axis=0)
        return dict(zip(self.feature_names_, avg_weights))


# ---------------------------------------------------------
# 4. Production Inference Engine
# ---------------------------------------------------------

class InferenceService:
    def __init__(self, trained_model: EnterpriseRiskClassifier):
        self.model = trained_model

    def execute_inference(self, payload: BatchInferenceRequest) -> List[Dict[str, Any]]:
        try:
            # Mengonversi list validated Pydantic model ke DataFrame
            raw_records = [record.model_dump() for record in payload.records]
            input_df = pd.DataFrame(raw_records)

            probabilities = self.model.predict_proba(input_df)[:, 1]
            predictions = self.model.predict(input_df, threshold=0.45)

            results = []
            for idx, (prob, pred) in enumerate(zip(probabilities, predictions)):
                results.append({
                    "record_id": idx,
                    "default_probability": float(prob),
                    "classification": int(pred),
                    "status": "APPROVED" if pred == 0 else "REJECTED"
                })
            return results

        except Exception as exc:
            logger.error("Inference Error: %s", str(exc), exc_info=True)
            raise RuntimeError(f"Gagal memproses payload inferensi: {str(exc)}") from exc


# ---------------------------------------------------------
# 5. Sanity Execution (Demonstrasi)
# ---------------------------------------------------------

if __name__ == "__main__":
    # Sintesis Dataset
    np.random.seed(42)
    n_samples = 1500

    raw_data = {
        "account_age_months": np.random.uniform(1, 120, n_samples),
        "transaction_count_30d": np.random.poisson(20, n_samples).astype(float),
        "debt_to_income_ratio": np.random.beta(2, 5, n_samples) * 5.0,
        "average_login_frequency": np.random.uniform(0.5, 14.0, n_samples),
    }
    # Kolom redundan sintetik untuk memicu VIF pruner
    raw_data["proxy_account_age"] = raw_data["account_age_months"] * 1.01 + np.random.normal(0, 0.05, n_samples)

    df_features = pd.DataFrame(raw_data)
    
    # Ground truth (Logistic equation + noise)
    logit = (
        0.05 * df_features["debt_to_income_ratio"] * 3.0
        - 0.02 * df_features["account_age_months"]
        - 0.03 * df_features["transaction_count_30d"]
        + 0.5
    )
    p = 1 / (1 + np.exp(-logit))
    labels = pd.Series((p > 0.55).astype(int), name="is_default")

    # Inisialisasi & Pelatihan Model
    classifier = EnterpriseRiskClassifier()
    classifier.fit(df_features, labels)

    # Menampilkan Bobot Fitur yang Bertahan
    feature_impact = classifier.explain()
    logger.info("Bobot Fitur Model Terlatih (Model Interpretability):")
    for feature, weight in feature_impact.items():
        logger.info("  %s: %.4f", feature, weight)

    # Test Inferensi menggunakan Pydantic Validator
    inference_service = InferenceService(classifier)
    sample_request = BatchInferenceRequest(
        records=[
            InferencePayload(
                account_age_months=12.0,
                transaction_count_30d=2.0,
                debt_to_income_ratio=4.5,
                average_login_frequency=1.2
            ),
            InferencePayload(
                account_age_months=72.0,
                transaction_count_30d=45.0,
                debt_to_income_ratio=0.8,
                average_login_frequency=7.0
            )
        ]
    )

    batch_output = inference_service.execute_inference(sample_request)
    logger.info("Hasil Inferensi Batch:\n%s", pd.DataFrame(batch_output).to_string())
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Root Cause Matematis / Sistemis | Konsekuensi di Lingkungan Produksi | Strategi Mitigasi Teruji (Production Defense) |
| :--- | :--- | :--- | :--- |
| **Separasi Sempurna (Perfect Separation)** | Satu atau kombinasi fitur linear memisahkan kelas secara sempurna ($y=1$ dan $y=0$). | Algoritma optimasi (Newton-Raphson/L-BFGS) divergen; koefisien bobot meledak menuju tak hingga ($\|\mathbf{w}\| \to \infty$); standar error tidak terhingga. | Pasang regularisasi $L_2$ tegas ($C \le 0.1$). Gunakan optimasi Bayesian GLM atau inferensi Terserah (Firth's Penalized Likelihood). |
| **Matriks Desain Singular / Rank-Deficient** | Varians fitur bernilai nol (fitur konstan) atau pasangan fitur memiliki korelasi absolut $r = 1.0$. | Operasi inversi $(\mathbf{X}^T \mathbf{X})^{-1}$ gagal dengan runtime exception `LinAlgError: Singular matrix`. | Pra-eliminasi fitur dengan `VarianceThreshold(0.0)` dan pastikan solver menggunakan Singular Value Decomposition (SVD) seperti `scipy.linalg.lstsq`. |
| **Ketidakseimbangan Kelas Ekstrim (< 0.1% Minority)** | Distribusi probabilitas prior $P(y=1) \approx 0$. | Hyperplane bias menggeser keputusan, memprediksi semua instance sebagai kelas mayoritas; log-loss terdistorsi. | Terapkan penyeimbangan bobot loss (*Cost-Sensitive Learning* / $w_1 = \frac{n}{2 n_1}$), kalibrasi ulang threshold keputusan melalui kurva *Precision-Recall (PR-AUC)*, bukan ROC. |
| **Extreme Value Feature Invalidation** | Outlier masif pada satu variabel prediktor (cth: pendapatan bernilai miliaran akibat kesalahan entri). | Menarik hyperplane linier OLS menjauhi distribusi massa utama; inflasi error residual pada populasi normal. | Terapkan transformasi non-linier (`Log1p`, `QuantileTransformer`) atau ganti loss function OLS ke *Huber Regressor* (kombinasi $L_2$ dan $L_1$). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan sistem machine learning linier berhadapan dengan kompromi struktural:

```
                            ┌─────────────────────────────────┐
                            │      Model Selection Tradeoff   │
                            └────────────────┬────────────────┘
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             ▼                                                               ▼
   [ Model-Based: GLMs ]                                           [ Complex: Gradient Trees / DL ]
   - Latensi: Sub-millisecond (SIMD)                               - Latensi: 10ms - 200ms
   - Interpretasi: Transparan (Linear Coeff)                       - Interpretasi: Black-box (SHAP required)
   - Batasan: Gagal menangkap interaksi                            - Keunggulan: Otomatis mendeteksi
     non-linier tanpa rekayasa eksplisit                             pola non-linier dan crossing features
```

#### Komparasi Model: Linear/Logistic vs Tree-Based vs Neural Architecture

| Dimensi Evaluasi | Regularized Linear/Logistic | Gradient Boosted Trees (XGBoost) | Deep Neural Networks (MLP) |
| :--- | :--- | :--- | :--- |
| **Kebutuhan Scaling Data** | **Wajib**: Peka terhadap magnitude ($L_1/L_2$ mengharuskan mean=0, std=1). | **Tidak Butuh**: Invarian terhadap transformasi monotonik fitur. | **Wajib**: Sangat sensitif terhadap stabilitas gradien (eksplosi/lenyap). |
| **Throughput / Latency** | **Ekstrem**: $\sim 50.000$ RPS / core CPU (operasi linear dot-product murni). | **Moderat**: $\sim 1.000 - 5.000$ RPS / core (penelusuran graf pohon). | **Rendah**: Butuh batching atau akselerasi hardware TensorRT/GPU. |
| **Data Skala Kecil ($n < 1.000$)** | **Superior**: Rendah risiko overfitting via kontrol regularisasi ketat. | **Rawan Overfit**: Perlu pembatasan depth yang sangat agresif. | **Gagal**: Mengharuskan data masif agar tidak terjebak di local optima. |
| **Deteksi Fitur Interaksi** | **Manual**: Pengembang harus menyuntikkan $x_i \cdot x_j$ atau *splines*. | **Otomatis**: Kedalaman pohon ($d \ge 2$) menangkap interaksi alami. | **Otomatis**: Terkomposisi di dalam representasi hidden layer. |

---

### 9. Best Practices & Standard Industri

1. **Standarisasi Fitur yang Disiplin (Feature Normalization)**:
   - Jika fitur tidak distandarisasi ke skala yang sama, variabel dengan rentang terbesar akan mendominasi fungsi penalti regularisasi:
     $$J(\mathbf{w}) = \text{Loss} + \lambda \sum_{j=1}^d |w_j|$$
     Koefisien variabel berdimensi besar akan ditekan secara tidak proporsional bukan karena korelasi rendah, melainkan karena nilai absolutnya yang kecil. Gunakan selalu `RobustScaler` jika terdapat outlier, atau `StandardScaler` jika data terdistribusi Gaussian.
2. **Uji Asumsi Klasik Pra-Deployment Regresi (BLUE Requirement)**:
   - Sesuai teorema **Gauss-Markov**, OLS adalah *Best Linear Unbiased Estimator* (BLUE) jika dan hanya jika:
     - Ekspektasi error bersyarat bernilai nol: $\mathbb{E}[\epsilon \mid \mathbf{X}] = 0$.
     - Homoscedasticity: $\operatorname{Var}(\epsilon_i \mid \mathbf{X}) = \sigma^2$ untuk seluruh $i$.
     - Tidak ada autokorelasi residual: $\operatorname{Cov}(\epsilon_i, \epsilon_j) = 0, \forall i \neq j$ (Durbin-Watson Test).
     - Jika homoscedasticity dilanggar, gunakan *Heteroskedasticity-Consistent Standard Errors* (White Covariance Estimator).
3. **Optimasi Ambang Keputusan (Decision Threshold Tuning)**:
   - Nilai default $\tau = 0.5$ pada klasifikasi logistik hampir selalu suboptimal di sistem industri. Pada sistem pendeteksi fraud, biaya *False Negative* jauh melampaui *False Positive*. Turunkan nilai threshold $\tau$ berdasarkan *Expected Cost Matrix*:
     $$\tau^* = \arg\min_{\tau} \left( C_{\text{FP}} \cdot \text{FP}(\tau) + C_{\text{FN}} \cdot \text{FN}(\tau) \right)$$
4. **Validasi Kalibrasi (Brier Score Analysis)**:
   - Periksa keandalan nilai estimasi probabilitas menggunakan *Reliability Diagram* dan evaluasi metrik **Brier Score**:
     $$\text{BS} = \frac{1}{n} \sum_{i=1}^n (f_i - y_i)^2$$
     Di mana $f_i$ adalah probabilitas yang diprediksi model. Skoring ini menghukum model yang percaya diri tinggi tetapi salah prediksi (*overconfident wrong prediction*).

---

### 10. Hands-on Lab Exercise

#### Skenario Masalah
Perusahaan FinTech lending memerlukan sistem pemberian keputusan kredit kilat (*Instant Underwriting System*).
Tugas Anda adalah:
1. Mengembangkan pipeline estimasi risiko kredit menggunakan regresi logistik teratur (*Logistic Regression*).
2. Mendeteksi dan memitigasi anomali multikolinearitas dan data scaling.
3. Mencari parameter regulasi optimal via *Cross-Validated Grid Search*.
4. Mengkalibrasi model dan menguji performa inferensi terhadap variasi ambang batas (*thresholding*).

#### Langkah 1: Persiapan Lingkungan & Pembangkitan Data
```python
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, brier_score_loss, roc_auc_score

# 1. Bangun Data Finansial Sintetik
np.random.seed(1337)
N = 5000

income = np.random.normal(5000, 1500, N).clip(1000, 15000)
credit_history_months = np.random.uniform(6, 120, N)
debt_amount = income * np.random.uniform(0.1, 0.8, N) + np.random.normal(0, 200, N)
existing_loans = np.random.choice([0, 1, 2, 3, 4], size=N, p=[0.4, 0.3, 0.15, 0.1, 0.05])

# Kolom yang memicu multikolinearitas struktural
dti_ratio = debt_amount / income

# Fungsi probabilitas default riil
true_latent = (
    1.2 * dti_ratio 
    + 0.3 * existing_loans 
    - 0.02 * (credit_history_months / 12.0) 
    - 0.0003 * income 
    + np.random.normal(0, 0.5, N)
)
probabilities = 1 / (1 + np.exp(-(true_latent - 1.5)))
defaults = (np.random.rand(N) < probabilities).astype(int)

df = pd.DataFrame({
    'income': income,
    'credit_history_months': credit_history_months,
    'debt_amount': debt_amount,
    'existing_loans': existing_loans,
    'dti_ratio': dti_ratio,
    'default': defaults
})

X = df.drop(columns=['default'])
y = df['default']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
print(f"Data Loaded: Train {X_train.shape}, Test {X_test.shape}. Default Rate: {y.mean():.2%}")
```

#### Langkah 2: Membangun Modul Pelatihan dengan Validasi Lintas Silang
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegressionCV
from sklearn.calibration import CalibratedClassifierCV

# Pipeline dengan ElasticNet Logistic CV
# Mencari konfigurasi C dan l1_ratio terbaik via 5-Fold Stratified CV
elastic_net_cv = LogisticRegressionCV(
    Cs=np.logspace(-3, 2, 10),
    l1_ratios=[0.1, 0.5, 0.9],
    penalty='elasticnet',
    solver='saga',
    cv=5,
    scoring='roc_auc',
    max_iter=2000,
    random_state=42,
    n_jobs=-1
)

model_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', elastic_net_cv)
])

print("Melatih Pipeline & Mencari Regularisasi Optimal...")
model_pipeline.fit(X_train, y_train)

best_classifier = model_pipeline.named_steps['classifier']
print(f"Optimal C: {best_classifier.C_[0]:.4f}")
print(f"Optimal L1 Ratio: {best_classifier.l1_ratio_[0]:.2f}")
```

#### Langkah 3: Kalibrasi Probabilitas Isotonik
```python
# Kalibrasi probabilitas pipeline untuk menjamin keakuratan estimasi risiko
calibrated_pipeline = CalibratedClassifierCV(
    estimator=model_pipeline,
    method='isotonic',
    cv='prefit'
)
calibrated_pipeline.fit(X_train, y_train)

# Evaluasi pada Test Set
raw_probs = model_pipeline.predict_proba(X_test)[:, 1]
calibrated_probs = calibrated_pipeline.predict_proba(X_test)[:, 1]

print(f"Test ROC-AUC: {roc_auc_score(y_test, calibrated_probs):.4f}")
print(f"Brier Score (Sebelum Kalibrasi): {brier_score_loss(y_test, raw_probs):.5f}")
print(f"Brier Score (Sesudah Kalibrasi): {brier_score_loss(y_test, calibrated_probs):.5f}")
```

#### Langkah 4: Threshold Optimization Berdasarkan Biaya Finansial Enterprise
```python
def optimize_threshold(y_true: np.ndarray, y_prob: np.ndarray, cost_fn: float, cost_fp: float):
    thresholds = np.linspace(0.01, 0.99, 100)
    costs = []
    
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        # Confusion matrix elements
        fn = np.sum((y_true == 1) & (y_pred == 0))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        
        # Total cost: FN (Kredit macet lolos) bernilai jauh lebih mahal daripada FP (Nasabah baik ditolak)
        total_cost = (fn * cost_fn) + (fp * cost_fp)
        costs.append(total_cost)
        
    optimal_idx = np.argmin(costs)
    return thresholds[optimal_idx], costs[optimal_idx]

# Biaya Finansial:
# Memberi kredit ke nasabah default (FN) merugikan $5000.
# Menolak nasabah potensial yang aman (FP) merugikan potensi profit $500.
COST_FN = 5000.0
COST_FP = 500.0

best_threshold, min_cost = optimize_threshold(y_test.values, calibrated_probs, COST_FN, COST_FP)
print("\n=== HASIL OPTIMASI FINANCIAL RISK ===")
print(f"Threshold Default (Naive) : 0.5000")
print(f"Threshold Optimal         : {best_threshold:.4f}")
print(f"Minimal Operational Cost  : ${min_cost:,.2f}")

# Bandingkan Keputusan pada Threshold Optimal vs Default
y_pred_naive = (calibrated_probs >= 0.5).astype(int)
y_pred_optimal = (calibrated_probs >= best_threshold).astype(int)

print("\nLaporan Klasifikasi (Naive 0.5):")
print(classification_report(y_test, y_pred_naive, digits=4))

print("\nLaporan Klasifikasi (Optimal Cost-Tuned):")
print(classification_report(y_test, y_pred_optimal, digits=4))
```

#### Penugasan Mandiri (Self-Assessment)
1. **Analisis Sensitivitas**: Modifikasi perbandingan `COST_FN` dan `COST_FP` menjadi $1:1$, amati perubahan *optimal decision threshold*. Apa korelasinya terhadap metrik *Recall* kelas default?
2. **Pemberantasan Kolom VIF**: Hapus fitur `debt_amount` dan jalankan ulang pengujian. Evaluasi apakah penyusutan bobot koefisien `dti_ratio` menjadi lebih stabil tanpa penurunan signifikan pada ROC-AUC.