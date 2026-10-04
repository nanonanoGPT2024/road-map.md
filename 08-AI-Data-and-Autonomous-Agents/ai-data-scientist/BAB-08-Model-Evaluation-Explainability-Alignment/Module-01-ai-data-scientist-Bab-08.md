# Bab 08: Model Evaluation, Explainability & Alignment

## Module 01: Enterprise Evaluation Frameworks: Metric Selection, Statistical Validation & Distribution Shift Detection

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis dan Memilih Metrik Evaluasi Secara Presisi**: Menentukan metrik diskriminasi dan kalibrasi yang tepat (*PR-AUC*, *Brier Score*, *Expected Calibration Error*) berdasarkan topologi data (imbalance ekstrem, cost-asymmetric matrix).
*   **Mengimplementasikan Pengujian Kalibrasi Probabilitas**: Menghitung *Expected Calibration Error* (ECE) dan dekomposisi *Brier Score* secara ter-vektorisasi menggunakan Python/NumPy tanpa bias pembagian bin (*binning bias*).
*   **Mendeteksi Covariate & Concept Shift Secara Statistis**: Menerapkan algoritma pengujian non-parametrik (*Population Stability Index* [PSI], *Wasserstein Distance*, *Two-Sample Kolmogorov-Smirnov Test*) untuk validasi integritas distribusi data inferensi terhadap baseline training.
*   **Membangun Automated Validation Gate**: Mengembangkan engine evaluasi modular berbasis *Clean Architecture* yang bertindak sebagai quality gate deterministik dalam pipeline CI/CD model deployment.

---

### 2. Concept Overview

Dalam rekayasa *Machine Learning* dan *Autonomous AI Systems* tingkat enterprise, evaluasi model bukan sekadar kalkulasi satu nilai agregat (seperti $F_1\text{-score}$ atau akurasi) pada *hold-out test set*. Evaluasi model adalah proses verifikasi multi-dimensi terhadap batas keandalan sistem (*reliability boundaries*) di bawah kondisi distribusi non-stasioner.

```
                      +------------------------------------------+
                      |         DISTRIBUTION DRIFT SPACE         |
                      |   P_train(X, Y)   !=   P_prod(X, Y)      |
                      +---------------------+--------------------+
                                            |
                         +------------------+------------------+
                         v                                     v
          +-------------------------------+   +-------------------------------+
          |     DISCRIMINATION ENGINE     |   |      CALIBRATION ENGINE       |
          |  "Apakah ranking probabilitas |   | "Apakah nilai numerik p=0.85  |
          |       memisahkan kelas?"      |   |   benar-benar berarti 85%?"   |
          |    (ROC-AUC, PR-AUC, G-Mean)   |   |     (ECE, MCE, Brier Score)   |
          +---------------+---------------+   +---------------+---------------+
                          |                                   |
                          +-----------------+-----------------+
                                            v
                      +------------------------------------------+
                      |      SLICE & SUBGROUP PERFORMANCE        |
                      |    (Disparate Impact, Simpson's Paradox) |
                      +---------------------+--------------------+
                                            v
                      +------------------------------------------+
                      |         PRODUCTION DEPLOYMENT GATE       |
                      |   Hard Constraints: ECE < 0.05, PSI < 0.1|
                      +------------------------------------------+
```

Model prediktif modern beroperasi dalam dua ruang orthogonal:
1.  **Discrimination**: Kemampuan model untuk membedakan antara instance positif dan negatif (misal, memisahkan transaksi *fraud* dari *legitimate*). Metrik: *Receiver Operating Characteristic - Area Under Curve* (ROC-AUC), *Precision-Recall Area Under Curve* (PR-AUC).
2.  **Calibration**: Tingkat kesesuaian antara probabilitas empiris keluaran model ($p \in [0, 1]$) dengan frekuensi kemunculan peristiwa di dunia nyata. Jika model memprediksi 100 pasien memiliki risiko kanker dengan probabilitas $0.80$, maka tepat 80 di antaranya harus benar-benar mengidap kanker. Metrik: *Brier Score*, *Expected Calibration Error* (ECE).

Kegagalan sistem AI di level enterprise umumnya tidak disebabkan oleh penurunan kemampuan diskriminasi, melainkan degradasi kalibrasi akibat *covariate shift* ($P(X_{\text{prod}}) \neq P(X_{\text{train}})$) dan *concept drift* ($P(Y|X_{\text{prod}}) \neq P(Y|X_{\text{train}})$) yang tidak terdeteksi oleh pipeline evaluasi konvensional.

---

### 3. Why It Matters

Di lingkungan produksi berskala tinggi, evaluasi yang lemah menimbulkan konsekuensi finansial, kepatuhan, dan operasional yang masif:

*   **Asymmetric Misclassification Costs**: Dalam sistem deteksi penipuan finansial (*fraud detection*), *false negative* (kehilangan ratusan ribu dolar) jauh lebih destruktif dibanding *false positive* (beban operasional verifikasi manual). Menggunakan metrik simetris seperti *Accuracy* atau standar *F1-score* (dengan *macro-weighting*) menyamarkan risiko kebangkrutan operasional.
*   **Downstream Autonomous Decision Failure**: Autonomous Agent yang bergantung pada confidence threshold model (misal: "Eksekusi otomatis jika $P(\text{solvency}) > 0.95$") akan mengalami kegagalan sistemik jika model mengalami *overconfidence miscalibration*. Model yang tidak terkalibrasi membuat agent mengeksekusi aksi berisiko tinggi.
*   **Regulatory Compliance**: Regulasi ketat seperti *EU AI Act* (High-Risk AI Systems requirements), Basel Committee *SR 11-7* (Supervisory Guidance on Model Risk Management), dan US Algorithmic Accountability Act mewajibkan validasi performa subgrup (*subgroup slice analysis*) dan pemantauan distribusi model secara terus-menerus untuk mencegah disparitas bias rasial, gender, atau demografis.

---

### 4. Arsitektur & Diagram Komponen

Diagram arsitektur berikut mengilustrasikan alur *Production-Grade Model Evaluation and Validation Gate*:

```
+--------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE EVALUATION PIPELINE                                |
+--------------------------------------------------------------------------------------------------+
                                                   |
                       +---------------------------+---------------------------+
                       v                                                       v
         +---------------------------+                           +---------------------------+
         |      Baseline Data        |                           |      Inference Data       |
         |   (Validation / Golden)   |                           |    (Batch / Stream Log)   |
         |    [X_base, y_base]       |                           |    [X_curr, y_curr]       |
         +-------------+-------------+                           +-------------+-------------+
                       |                                                       |
                       +---------------------------+---------------------------+
                                                   |
                                                   v
                       +-------------------------------------------------------+
                       |               DATA PREPARATION & SLICING              |
                       | - Stratified Binning                                  |
                       | - Sensitive Attribute Slicing (Region, Cohort, etc.)  |
                       +---------------------------+---------------------------+
                                                   |
       +-------------------------------------------+-------------------------------------------+
       |                                           |                                           |
       v                                           v                                           v
+-------------------------------+   +-------------------------------+   +-------------------------------+
|     DISCRIMINATION MODULE     |   |      CALIBRATION MODULE       |   |    DISTRIBUTION DRIFT DETECT  |
| - Vectorized PR-AUC           |   | - Adaptive Binning ECE        |   | - Population Stability Index  |
| - Cost-Weighted F-Beta        |   | - Brier Score Decomposition   |   | - Wasserstein 1D Distance     |
| - Slice Disparity Detection   |   | - Reliability Curve Gen       |   | - Two-Sample KS Test          |
+---------------+---------------+   +---------------+---------------+   +---------------+---------------+
                |                                   |                                   |
                +-----------------------------------+-----------------------------------+
                                                    |
                                                    v
                                +---------------------------------------+
                                |      EVALUATION POLICY GATE ENGINE    |
                                |                                       |
                                |  Hard Assertions:                     |
                                |    1. PR-AUC >= Threshold_Min         |
                                |    2. ECE <= Max_Permitted_ECE        |
                                |    3. Feature_PSI <= 0.10             |
                                |    4. Max Subgroup Gap <= Tolerance   |
                                +-------------------+-------------------+
                                                    |
                                    +---------------+---------------+
                                    v                               v
                     +-----------------------------+ +-----------------------------+
                     |        PASSED GATE          | |        FAILED GATE          |
                     | - Register Model to Prod    | | - Block Deployment Pipeline |
                     | - Emit Production Metadata  | | - Trigger Drift Alert       |
                     | - Log MLflow/Artifact Store | | - Route to Human Fallback   |
                     +-----------------------------+ +-----------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1. Kalibrasi Probabilitas: ECE dan Brier Score

Secara formal, model dikatakan terkalibrasi secara sempurna jika:
$$\mathbb{P}(\hat{Y} = 1 \mid \hat{P} = p) = p, \quad \forall p \in [0, 1]$$

##### Expected Calibration Error (ECE)
Metrik ini membagi ruang prediksi interval $[0, 1]$ ke dalam $M$ bin yang berjarak sama (misal $M=10$). Misalkan $B_m$ merepresentasikan himpunan indeks sampel yang prediksi probabilitasnya jatuh ke dalam interval $I_m = (\frac{m-1}{M}, \frac{m}{M}]$.

Akurasi dari $B_m$ didefinisikan sebagai:
$$\text{acc}(B_m) = \frac{1}{|B_m|} \sum_{i \in B_m} \mathbf{1}(y_i = 1)$$

Kepercayaan (*confidence*) dari $B_m$ didefinisikan sebagai:
$$\text{conf}(B_m) = \frac{1}{|B_m|} \sum_{i \in B_m} \hat{p}_i$$

Maka, ECE adalah rata-rata tertimbang selisih absolut antara akurasi dan confidence di seluruh bin:
$$\text{ECE} = \sum_{m=1}^M \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

##### Dekomposisi Brier Score
Brier Score mengukur *Mean Squared Error* (MSE) dari estimasi probabilitas terhadap label biner aktual ($y_i \in \{0, 1\}$):
$$\text{BS} = \frac{1}{N} \sum_{i=1}^N (\hat{p}_i - y_i)^2$$

Brier score dapat didekomposisi secara matematis menjadi tiga komponen fundamental:
$$\text{BS} = \text{Reliability} - \text{Resolution} + \text{Uncertainty}$$
*   **Reliability**: Seberapa dekat probabilitas yang diprediksi dengan frekuensi kejadian sebenarnya (harus mendekati 0 untuk kalibrasi sempurna).
*   **Resolution**: Seberapa jauh probabilitas yang diprediksi untuk tiap bin berbeda dari rata-rata populasi dasar (semakin tinggi semakin baik).
*   **Uncertainty**: Varians inheren dari event aktual $\bar{y}(1 - \bar{y})$. Komponen ini tidak bergantung pada model.

#### 5.2. Deteksi Pergeseran Distribusi (Distribution Drift Detection)

##### Population Stability Index (PSI)
PSI mengukur pergeseran distribusi populasi antara sampel referensi (baseline) dan aktual (produksi):
$$\text{PSI} = \sum_{k=1}^K \left( P_k - Q_k \right) \times \ln\left(\frac{P_k}{Q_k}\right)$$
Dimana:
*   $P_k$ adalah proporsi observasi aktual pada bin ke-$k$.
*   $Q_k$ adalah proporsi observasi baseline pada bin ke-$k$.
*   Aturan Industri (*Rule of Thumb*):
    *   $\text{PSI} < 0.1$: Tidak ada pergeseran signifikan (*No Change*).
    *   $0.1 \le \text{PSI} < 0.25$: Terjadi pergeseran moderat; model perlu dimonitor ketat.
    *   $\text{PSI} \ge 0.25$: Terjadi *significant shift*; model harus di-retrain atau fallback diaktifkan.

##### Wasserstein Distance (Earth Mover's Distance - 1D)
Untuk variabel kontinu di mana diskretisasi binning dapat membuang informasi urutan (*order information*), Wasserstein-1 Distance digunakan:
$$W_1(u, v) = \int_{-\infty}^{\infty} |U(x) - V(x)| \, dx$$
Di mana $U(x)$ dan $V(x)$ adalah *Cumulative Distribution Functions* (CDF) empiris dari distribusi baseline dan inferensi. Nilai ini merepresentasikan "kerja" minimum yang diperlukan untuk memindahkan satu distribusi ke bentuk distribusi target.

---

### 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python tingkat lanjut dengan prinsip *Clean Architecture*, *typing*, *vectorized operations*, dan *robust defensive programming*.

```python
"""
enterprise_evaluator.py
Production-Grade Model Evaluation and Distribution Drift Detection Framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import scipy.stats as stats

# Inisialisasi konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("EnterpriseEvaluator")


class GateStatus(Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EvaluationMetrics:
    brier_score: float
    expected_calibration_error: float
    max_calibration_error: float
    roc_auc: float
    pr_auc: float
    brier_reliability: float
    brier_resolution: float
    brier_uncertainty: float


@dataclass(frozen=True)
class DriftResult:
    feature_name: str
    psi_score: float
    wasserstein_distance: float
    ks_statistic: float
    ks_p_value: float
    drift_detected: bool


@dataclass
class PolicyThresholds:
    min_pr_auc: float = 0.70
    min_roc_auc: float = 0.75
    max_ece: float = 0.05
    max_psi: float = 0.20
    ks_alpha: float = 0.05


@dataclass
class ValidationReport:
    status: GateStatus
    metrics: EvaluationMetrics
    drift_analyses: Dict[str, DriftResult]
    failure_reasons: List[str] = field(default_factory=list)


class CalibrationEngine:
    """Mesin kalkulasi kalibrasi probabilistik vektor dan deterministik."""

    @staticmethod
    def compute_ece(
        y_true: np.ndarray,
        y_prob: np.ndarray,
        num_bins: int = 10
    ) -> Tuple[float, float]:
        """
        Menghitung Expected Calibration Error (ECE) dan Maximum Calibration Error (MCE).
        
        Args:
            y_true: Binary ground truth labels (0 atau 1).
            y_prob: Model output probabilities [0, 1].
            num_bins: Jumlah bin seragam.
            
        Returns:
            Tuple[float, float]: (ECE, MCE)
        """
        if len(y_true) != len(y_prob):
            raise ValueError("Ukuran array label dan probabilitas tidak cocok.")
        if np.any((y_prob < 0.0) | (y_prob > 1.0)):
            raise ValueError("Probabilitas prediksi harus berada dalam batas [0.0, 1.0].")

        bin_boundaries = np.linspace(0.0, 1.0, num_bins + 1)
        ece = 0.0
        mce = 0.0
        n_samples = len(y_prob)

        for i in range(num_bins):
            bin_lower = bin_boundaries[i]
            bin_upper = bin_boundaries[i + 1]

            # Inklusi endpoint atas hanya pada bin terakhir
            if i == num_bins - 1:
                mask = (y_prob >= bin_lower) & (y_prob <= bin_upper)
            else:
                mask = (y_prob >= bin_lower) & (y_prob < bin_upper)

            bin_size = np.sum(mask)
            if bin_size > 0:
                acc_bin = np.mean(y_true[mask])
                conf_bin = np.mean(y_prob[mask])
                calibration_error = np.abs(acc_bin - conf_bin)

                ece += (bin_size / n_samples) * calibration_error
                mce = max(mce, calibration_error)

        return float(ece), float(mce)

    @staticmethod
    def decompose_brier_score(
        y_true: np.ndarray,
        y_prob: np.ndarray,
        num_bins: int = 10
    ) -> Tuple[float, float, float, float]:
        """
        Melakukan dekomposisi Brier Score: Reliability - Resolution + Uncertainty.
        """
        n = len(y_true)
        base_rate = np.mean(y_true)
        uncertainty = base_rate * (1.0 - base_rate)

        bin_boundaries = np.linspace(0.0, 1.0, num_bins + 1)
        reliability = 0.0
        resolution = 0.0

        for i in range(num_bins):
            if i == num_bins - 1:
                mask = (y_prob >= bin_boundaries[i]) & (y_prob <= bin_boundaries[i + 1])
            else:
                mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])

            bin_size = np.sum(mask)
            if bin_size > 0:
                acc_bin = np.mean(y_true[mask])
                conf_bin = np.mean(y_prob[mask])
                
                reliability += (bin_size / n) * ((conf_bin - acc_bin) ** 2)
                resolution += (bin_size / n) * ((acc_bin - base_rate) ** 2)

        brier_score = float(np.mean((y_prob - y_true) ** 2))
        return brier_score, float(reliability), float(resolution), float(uncertainty)


class DriftEngine:
    """Mesin statistik deteksi divergensi dan pergeseran distribusi."""

    @staticmethod
    def calculate_psi(
        baseline: np.ndarray,
        target: np.ndarray,
        num_bins: int = 10,
        epsilon: float = 1e-6
    ) -> float:
        """
        Menghitung Population Stability Index (PSI) menggunakan quantile-binning dari baseline.
        """
        if len(baseline) == 0 or len(target) == 0:
            raise ValueError("Array input tidak boleh kosong untuk perhitungan PSI.")

        # Buat kuantil berbasis data baseline
        quantiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] = -np.inf
        bin_edges[-1] = np.inf

        # Frekuensi absolut di setiap bin
        baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
        target_counts, _ = np.histogram(target, bins=bin_edges)

        # Ubah ke proporsi empiris
        baseline_pct = baseline_counts / len(baseline)
        target_pct = target_counts / len(target)

        # Regularisasi nilai nol (numerical stability)
        baseline_pct = np.where(baseline_pct == 0, epsilon, baseline_pct)
        target_pct = np.where(target_pct == 0, epsilon, target_pct)

        # Normalisasi ulang agar jumlah proporsi tepat 1
        baseline_pct /= np.sum(baseline_pct)
        target_pct /= np.sum(target_pct)

        psi = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
        return float(psi)

    @staticmethod
    def calculate_wasserstein(baseline: np.ndarray, target: np.ndarray) -> float:
        """Menghitung Earth Mover's Distance (Wasserstein-1) untuk data 1D kontinu."""
        return float(stats.wasserstein_distance(baseline, target))

    @classmethod
    def analyze_feature_drift(
        cls,
        feature_name: str,
        baseline: np.ndarray,
        target: np.ndarray,
        thresholds: PolicyThresholds
    ) -> DriftResult:
        """Eksekusi evaluasi multivariat statistik untuk feature drift."""
        psi = cls.calculate_psi(baseline, target)
        w_dist = cls.calculate_wasserstein(baseline, target)
        ks_res = stats.ks_2samp(baseline, target)

        drift_flag = bool((psi >= thresholds.max_psi) or (ks_res.pvalue < thresholds.ks_alpha))

        return DriftResult(
            feature_name=feature_name,
            psi_score=psi,
            wasserstein_distance=w_dist,
            ks_statistic=float(ks_res.statistic),
            ks_p_value=float(ks_res.pvalue),
            drift_detected=drift_flag
        )


class EnterpriseEvaluationPipeline:
    """Orkestrator evaluasi produksi yang menegakkan batasan kualitas sistem AI."""

    def __init__(self, thresholds: Optional[PolicyThresholds] = None):
        self.thresholds = thresholds or PolicyThresholds()

    @staticmethod
    def _compute_roc_pr_auc(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[float, float]:
        """Kalkulasi diskriminasi PR-AUC dan ROC-AUC berbasis sorting."""
        sort_order = np.argsort(y_prob)[::-1]
        y_sorted = y_true[sort_order]

        n_pos = np.sum(y_sorted == 1)
        n_neg = len(y_sorted) - n_pos

        if n_pos == 0 or n_neg == 0:
            return 0.0, 0.0

        tp = np.cumsum(y_sorted == 1)
        fp = np.cumsum(y_sorted == 0)

        tpr = tp / n_pos
        fpr = fp / n_neg
        precision = tp / (tp + fp)

        # Trapezoidal numerical integration
        roc_auc = float(np.trapezoid(tpr, fpr)) if hasattr(np, 'trapezoid') else float(np.trapz(tpr, fpr))
        
        # PR-AUC menggunakan presisi yang diintegrasikan terhadap recall (TPR)
        tpr_extended = np.insert(tpr, 0, 0.0)
        precision_extended = np.insert(precision, 0, 1.0)
        if hasattr(np, 'trapezoid'):
            pr_auc = float(np.trapezoid(precision_extended, tpr_extended))
        else:
            pr_auc = float(np.trapz(precision_extended, tpr_extended))

        return roc_auc, pr_auc

    def evaluate(
        self,
        y_test: np.ndarray,
        y_pred_probs: np.ndarray,
        baseline_features: Dict[str, np.ndarray],
        current_features: Dict[str, np.ndarray]
    ) -> ValidationReport:
        """
        Mengeksekusi end-to-end evaluasi performa inferensi dan drift data.
        """
        logger.info("Memulai audit evaluasi performa model dan distribusi...")
        failures: List[str] = []

        # 1. Evaluasi Kalibrasi
        ece, mce = CalibrationEngine.compute_ece(y_test, y_pred_probs)
        bs, rel, res, unc = CalibrationEngine.decompose_brier_score(y_test, y_pred_probs)

        # 2. Evaluasi Diskriminasi
        roc_auc, pr_auc = self._compute_roc_pr_auc(y_test, y_pred_probs)

        metrics = EvaluationMetrics(
            brier_score=bs,
            expected_calibration_error=ece,
            max_calibration_error=mce,
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            brier_reliability=rel,
            brier_resolution=res,
            brier_uncertainty=unc
        )

        # 3. Assertions Aturan Performa
        if pr_auc < self.thresholds.min_pr_auc:
            failures.append(f"PR-AUC {pr_auc:.4f} berada di bawah threshold {self.thresholds.min_pr_auc}")
        if roc_auc < self.thresholds.min_roc_auc:
            failures.append(f"ROC-AUC {roc_auc:.4f} berada di bawah threshold {self.thresholds.min_roc_auc}")
        if ece > self.thresholds.max_ece:
            failures.append(f"ECE {ece:.4f} melebihi batas kalibrasi {self.thresholds.max_ece}")

        # 4. Analisis Feature Drift
        drift_results: Dict[str, DriftResult] = {}
        for feature_name, base_arr in baseline_features.items():
            if feature_name not in current_features:
                failures.append(f"Feature '{feature_name}' tidak ditemukan pada dataset produksi.")
                continue

            curr_arr = current_features[feature_name]
            drift_res = DriftEngine.analyze_feature_drift(
                feature_name, base_arr, curr_arr, self.thresholds
            )
            drift_results[feature_name] = drift_res

            if drift_res.drift_detected:
                failures.append(
                    f"Drift terdeteksi pada '{feature_name}': PSI={drift_res.psi_score:.4f}, "
                    f"KS p-val={drift_res.ks_p_value:.2e}"
                )

        status = GateStatus.FAILED if failures else GateStatus.PASSED
        logger.info("Audit evaluasi selesai dengan status: %s", status.value)

        return ValidationReport(
            status=status,
            metrics=metrics,
            drift_analyses=drift_results,
            failure_reasons=failures
        )


if __name__ == "__main__":
    np.random.seed(42)

    # Inisialisasi Mock Data
    N_SAMPLES = 5000
    y_true_mock = np.random.binomial(1, 0.15, size=N_SAMPLES)
    
    # Model probabilities yang miscalibrated (underconfident overestimation)
    raw_probs = np.random.beta(0.5, 2.0, size=N_SAMPLES)
    y_probs_mock = np.clip(raw_probs, 0.0, 1.0)

    # Baseline features
    baseline_feat = {
        "account_age_months": np.random.exponential(scale=24.0, size=N_SAMPLES),
        "transaction_amount": np.random.lognormal(mean=4.0, sigma=1.0, size=N_SAMPLES)
    }

    # Current features yang mengalami Covariate Shift pada 'transaction_amount'
    current_feat = {
        "account_age_months": np.random.exponential(scale=24.0, size=N_SAMPLES),
        "transaction_amount": np.random.lognormal(mean=5.2, sigma=1.2, size=N_SAMPLES) # Mean bergeser tinggi
    }

    pipeline = EnterpriseEvaluationPipeline(
        thresholds=PolicyThresholds(
            min_pr_auc=0.40,
            min_roc_auc=0.60,
            max_ece=0.08,
            max_psi=0.15
        )
    )

    report = pipeline.evaluate(
        y_test=y_true_mock,
        y_pred_probs=y_probs_mock,
        baseline_features=baseline_feat,
        current_features=current_feat
    )

    print("\n--- HASIL VALIDATION GATE ---")
    print(f"Status Evaluasi: {report.status.value}")
    print(f"PR-AUC: {report.metrics.pr_auc:.4f} | ROC-AUC: {report.metrics.roc_auc:.4f}")
    print(f"Brier Score: {report.metrics.brier_score:.4f} (Reliability: {report.metrics.brier_reliability:.4f})")
    print(f"Expected Calibration Error: {report.metrics.expected_calibration_error:.4f}")
    
    print("\n--- ANALISIS FEATURE DRIFT ---")
    for feat, res in report.drift_analyses.items():
        print(f"Feature: {feat:<20} | PSI: {res.psi_score:.4f} | KS p-val: {res.ks_p_value:.4e} | Drift: {res.drift_detected}")

    if report.failure_reasons:
        print("\n--- ALASAN KEGAGALAN (GATE BLOCK) ---")
        for reason in report.failure_reasons:
            print(f"[REJECT] {reason}")
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan produksi nyata, algoritma evaluasi dapat gagal bekerja secara deterministik akibat masalah matematika dan topologi data:

*   **Degenerate Bins dalam Perhitungan ECE (Zero-Variance)**: Ketika model menghasilkan probabilitas diskrit murni (misal hanya menghasilkan prediksi $0.0$ dan $1.0$ akibat over-regularization atau activation saturations), bin perantara akan bernilai kosong ($|B_m| = 0$). Kode evaluasi harus mengabaikan bin kosong tanpa menimbulkan *division-by-zero errors*.
*   **Identical Quantiles pada Heavy-Tied Data**: Jika suatu fitur memiliki persentase besar nilai identik (misal $80\%$ nilai bernilai $0.0$), perhitungan binning berbasis `np.percentile` untuk PSI akan menghasilkan batas bin yang identik ($bin_j = bin_{j+1}$). Hal ini menyebabkan bin collapse. Penanganan: Terapkan strategi adaptif deduplikasi bin boundaries (`np.unique(bin_edges)`) sebelum pemanggilan histogram.
*   **Sample Size Disparity Bias pada Uji KS**: Uji Kolmogorov-Smirnov sangat sensitif terhadap ukuran sampel besar ($N > 100,000$). Dengan sampel masif, perbedaan distribusi yang sangat kecil dan secara praktis tidak penting secara ekonomi (*trivial divergence*) akan menghasilkan nilai $p < 10^{-15}$. Solusi mitigasi: Jangan mengandalkan $p\text{-value}$ semata; kombinasikan dengan batas mutlak pada *KS Statistic Distance* ($D > 0.05$) atau *Wasserstein Distance*.
*   **Extreme Class Imbalance ($< 0.01\%$)**: Ketika menghitung bootstrap confidence interval untuk metrik evaluasi pada kasus ekstrem (misal pendeteksian transaksi pencucian uang), sejumlah sampel bootstrap mungkin berisi nol sampel positif, menyebabkan *AUC undefined*. Skema stratifikasi ketat (*Stratified Resampling*) wajib digunakan.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | Pendekatan A | Pendekatan B | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Pendeteksian Pergeseran Data** | **Population Stability Index (PSI)** | **Maximum Mean Discrepancy (MMD)** | PSI sangat cepat dihitung ($O(N)$), dapat diinterpretasikan secara langsung oleh stakeholder bisnis/regulator per-fitur tabular. Namun, PSI gagal menangkap korelasi antar-fitur (*multivariate cross-feature shift*). MMD dengan kernel RBF mampu mendeteksi interaksi multivariat kompleks, namun memerlukan komputasi kuadratik $O(N^2)$ dan sulit diisolasi fitur mana yang menyebabkan pergeseran. |
| **Metrik Kalibrasi** | **Uniform-Width ECE** | **Adaptive-Quantile ECE (Equal Mass)** | Uniform-width membagi rentang $[0, 1]$ sama rata ($0.0-0.1, 0.1-0.2$ dst.), rentan terhadap bin yang sangat sepi di ekor distribusi. Adaptive-quantile membagi interval sehingga setiap bin memiliki jumlah instance yang tepat sama, mengurangi varians estimasi di region dengan data jarang, namun batas bin menjadi non-intuitif. |
| **Koreksi Kalibrasi** | **Platt Scaling (Sigmoid)** | **Isotonic Regression** | Platt Scaling mengasumsikan log-odds terkalibrasi secara linear (parametrik, hemat data, kebal overfitting), tetapi tidak mampu memperbaiki kurva non-monotonik kompleks. Isotonic Regression bersifat non-parametrik murni (sangat fleksibel), namun rentan mengalami overfitting parah jika data kalibrasi terbatas ($N < 1000$). |

---

### 9. Best Practices & Standard Industri

Untuk menjamin kepatuhan model AI pada standar enterprise (seperti *NIST AI Risk Management Framework* dan *Federal Reserve SR 11-7*):

*   **Golden Baseline Freezing**: Simpan baseline distribusi fitur ($X_{\text{base}}$) dari data validasi final yang digunakan saat sign-off model. Seluruh kalkulasi drift inferensi *harus* dibandingkan terhadap Golden Baseline ini, bukan secara bergeser (*rolling window*) terhadap data kemarin. Perbandingan terhadap *rolling window* berisiko mengalami fenomena **Frog Boil Shift** (distribusi bergeser sangat jauh secara kumulatif, namun tidak pernah terdeteksi karena perubahan hari-ke-hari sangat kecil).
*   **Subgroup Slice-Based Parity Checks**: Tidak boleh mendeploy model hanya berdasarkan metrik makro. Lakukan slicing terstruktur berdasarkan fitur demografi, segmentasi pengguna, atau geografi. Hitung metrik *Disparate Impact Ratio*:
    $$\text{DIR} = \frac{\mathbb{P}(\hat{Y}=1 \mid A=\text{unprivileged})}{\mathbb{P}(\hat{Y}=1 \mid A=\text{privileged})} \ge 0.80$$
*   **Vectorized Deterministic Assertions**: Integrasikan modul evaluasi sebagai test assertions dalam CI/CD pipeline (menggunakan PyTest atau custom orchestration workers seperti Airflow/Prefect). Model build artefak harus gagal (*exit code 1*) secara otomatis apabila melanggar ambang batas hard gate.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda adalah Principal AI Data Scientist di bank global. Sebuah model klasifikasi risiko kredit (*Credit Default Classification*) akan dirilis ke produksi. Anda ditugaskan untuk memvalidasi performa model dan mendeteksi apakah data inferensi dari kuartal terbaru telah mengalami pergeseran distribusi yang membahayakan portofolio kredit bank.

#### Langkah-langkah:

1.  **Persiapan Lingkungan Lab**:
    Simpan kode dari bagian 6 ke dalam berkas `enterprise_evaluator.py`.

2.  **Pembuatan Dataset Eksperimen**:
    Buat berkas skrip baru bernama `run_validation_lab.py`:
    ```python
    import numpy as np
    from enterprise_evaluator import EnterpriseEvaluationPipeline, PolicyThresholds

    # Generate baseline data (Q1 - Train/Validation)
    np.random.seed(1337)
    N_BASE = 10000
    y_true_base = np.random.binomial(1, 0.05, size=N_BASE) # 5% default rate
    # Model memiliki pemisahan yang moderat
    y_prob_base = np.where(
        y_true_base == 1,
        np.random.beta(2.0, 3.0, size=N_BASE),
        np.random.beta(0.5, 8.0, size=N_BASE)
    )

    baseline_features = {
        "debt_to_income": np.random.gamma(shape=3.0, scale=0.1, size=N_BASE),
        "credit_utilization": np.random.uniform(0.0, 0.9, size=N_BASE)
    }

    # Generate inference data (Q2 - Real Production under Economic Stress)
    N_CURR = 3000
    y_true_curr = np.random.binomial(1, 0.12, size=N_CURR) # Default rate naik menjadi 12%
    # Prediksi probabilitas model tertinggal (under-estimating default risk)
    y_prob_curr = np.where(
        y_true_curr == 1,
        np.random.beta(1.5, 4.0, size=N_CURR),
        np.random.beta(0.5, 8.0, size=N_CURR)
    )

    current_features = {
        # Debt to income bergeser ke kanan secara signifikan
        "debt_to_income": np.random.gamma(shape=4.5, scale=0.12, size=N_CURR),
        "credit_utilization": np.random.uniform(0.0, 0.92, size=N_CURR)
    }

    # Inisialisasi Policy Gate Ketat Bank
    policy = PolicyThresholds(
        min_pr_auc=0.35,
        min_roc_auc=0.70,
        max_ece=0.04,
        max_psi=0.10,
        ks_alpha=0.01
    )

    pipeline = EnterpriseEvaluationPipeline(thresholds=policy)
    report = pipeline.evaluate(
        y_test=y_true_curr,
        y_pred_probs=y_prob_curr,
        baseline_features=baseline_features,
        current_features=current_features
    )

    print(f"\n[DEPLOYMENT STATUS]: {report.status.value}")
    if report.failure_reasons:
        print("[FAILURES DETECTED]:")
        for failure in report.failure_reasons:
            print(f" - {failure}")
    ```

3.  **Eksekusi & Analisis**:
    Jalankan verifikasi:
    ```bash
    python run_validation_lab.py
    ```

4.  **Tugas Pengujian Kritis**:
    *   Amati output kegagalan: Analisis fitur mana yang menyebabkan pelanggaran PSI ($>0.10$).
    *   Amati nilai ECE: Jelaskan mengapa ECE melonjak tinggi ketika krisis ekonomi terjadi di data Q2 sementara model dilatih dengan data Q1.
    *   Modifikasi script untuk mengimplementasikan *Platt Scaling* kalibrasi sederhana pada `y_prob_curr` sebelum evaluasi dan catat apakah ECE dapat ditekan kembali ke bawah ambang batas ($0.04$).