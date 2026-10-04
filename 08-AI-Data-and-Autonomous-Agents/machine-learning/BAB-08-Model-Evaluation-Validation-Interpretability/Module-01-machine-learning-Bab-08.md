# Bab 08: Model Evaluation, Validation & Interpretability
## Modul 01: Advanced Validation Strategies & Core Evaluation Metrics Engine

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
1. **Merancang & Mengimplementasikan Strategi Validasi Non-IID**: Mengembangkan skema partisi data bebas kebocoran (*data leakage*) menggunakan *Purged & Embargoed Time-Series Cross-Validation* dan *Group-aware Stratification* untuk menangani data berkorelasi temporal dan klaster.
2. **Membangun Core Evaluation Metrics Engine**: Menghitung secara matematis dan mengotomatisasi evaluasi metrik diskriminasi (*ROC-AUC*, *PR-AUC*, *Matthews Correlation Coefficient / MCC*) dan metrik kalibrasi probabilitas (*Brier Score*, *Expected Calibration Error / ECE*) tanpa dependensi eksternal selain *NumPy* dan *SciPy*.
3. **Menganalisis & Mengoreksi Miscalibration**: Mendiagnosis kurva keandalan (*reliability diagrams*) dan menerapkan algoritma kalibrasi pasca-pemrosesan (*Platt Scaling* berbasis Regresi Logistik dan *Isotonic Regression*).
4. **Mendeteksi & Mencegah Vektor Kebocoran Data (Data Leakage)**: Mengaudit saluran *feature engineering* untuk mengidentifikasi kebocoran target (*target leakage*), kebocoran prapemrosesan (*preprocessing leakage*), dan kebocoran temporal (*look-ahead bias*).
5. **Menjalankan Pengujian Signifikansi Statistik Model**: Mengevaluasi apakah perbedaan performa antar model signifikan secara statistik menggunakan *McNemar’s Test* dan *5x2 Cross-Validated Paired t-Test*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Sistem *Machine Learning* (ML) di lingkungan produksi sering kali gagal bukan karena performa algoritma yang suboptimal, melainkan karena **kegagalan validasi** (*validation failure*). Mental model evaluasi model harus bergeser dari sekadar "mengukur skor pada kumpulan data uji" menjadi "merekonstruksi lingkungan inferensi dunia nyata secara deterministik".

```
                       ASUMSI I.I.D. (KLASIK)
 [Dataset Acak] ─── Random Split ───> [Train Set] | [Test Set]
 (Mengabaikan dependensi waktu, klaster entitas, dan autokorelasi)
                               │
                               ▼ Menyebabkan OVERFITTING TERSELUBUNG
                   
                 REALITAS DISTRIBUSI NON-I.I.D. (PRODUKSI)
 [Sinyal Waktu / Klaster] ─── Purging & Embargo ───> Validasi Ketat Bebas Kebocoran
 (Menghapus overlap informasi label & korelasi serial)
```

#### The Accuracy Paradox & Discriminative Reality
Akurasi adalah metrik yang menyesatkan (*pathological metric*) pada distribusi data timpang (*imbalanced distributions*). Jika prevalensi kelas minoritas adalah 0.1%, model naif yang selalu memprediksi kelas mayoritas akan mendapatkan akurasi 99.9%, namun bernilai bisnis nol. 

Evaluasi modern bergantung pada dua dimensi ortogonal:
1. **Diskriminasi (Peringkat / Ranking)**: Kemampuan model untuk memisahkan kelas positif dari kelas negatif.
   - *ROC-AUC*: Rata-rata sensitivitas di seluruh ambang batas (*threshold*). Kebal terhadap perubahan prevalensi kelas, tetapi dapat memberikan gambaran terlalu optimis pada ketimpangan ekstrem.
   - *PR-AUC* (Average Precision): Mengukur presisi terhadap *recall*. Sangat sensitif terhadap *False Positive* pada kelas minoritas; metrik primer untuk deteksi penipuan (*fraud*), anomali, dan diagnosa medis langka.
   - *Matthews Correlation Coefficient (MCC)*: Koefisien korelasi diskrit antara label aktual dan prediksi biner (rentang $[-1, +1]$). MCC mengevaluasi keempat kuadran matriks konfusi secara simetris:
     $$\text{MCC} = \frac{TP \times TN - FP \times FN}{\sqrt{(TP + FP)(TP + FN)(TN + FP)(TN + FN)}}$$

2. **Kalibrasi Probabilitas (Probabilistic Reliability)**: Seberapa akurat probabilitas keluaran model $\hat{p} \in [0, 1]$ mencerminkan probabilitas kebenaran empiris.
   - Model yang memprediksi probabilitas 0.8 harus memiliki tingkat kejadian aktual sebesar 80% pada seluruh instans dalam *bin* tersebut.
   - *Brier Score*: *Mean Squared Error* pada probabilitas:
     $$\text{BS} = \frac{1}{N} \sum_{i=1}^{N} (\hat{p}_i - y_i)^2$$
   - *Expected Calibration Error (ECE)*: Rata-rata tertimbang dari selisih absolut antara akurasi empiris dan tingkat kepercayaan rata-rata pada $M$ interval (*bins*):
     $$\text{ECE} = \sum_{m=1}^{M} \frac{|B_m|}{N} \left| \text{acc}(B_m) - \text{conf}(B_m) \right|$$

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada sistem produksi skala besar, kegagalan metodologi evaluasi memicu kerugian finansial langsung:

1. **Fintech & Credit Underwriting**: Kebocoran target (*target leakage*) akibat penggunaan fitur derivatif masa depan (seperti menyertakan atribut pembayaran pasca-gagal bayar) membuat model kredit tampak memiliki *AUC* 0.95 pada validasi, namun melonjakkan *Non-Performing Loan* (NPL) saat dijalankan di produksi karena prediksi sebenarnya bernilai acak.
2. **High-Frequency Trading & Market Prediction**: Korelasi serial (*autocorrelation*) pada deret waktu keuangan menyebabkan pembagian acak standar (*standard K-Fold*) membocorkan data dari masa depan ke masa lalu (*look-ahead bias*). Strategi membutuhkan *Purging* (menghapus data latih yang memiliki overlap label waktu dengan data uji) dan *Embargoing* (menghapus data latih tepat setelah data uji untuk memutus efek memori residual).
3. **Sistem Pengambilan Keputusan Klinis**: Model dengan diskriminasi tinggi (*ROC-AUC* 0.90) namun tidak terkalibrasi dapat menetapkan risiko stroke sebesar 90% pada pasien yang sebenarnya hanya berisiko 20%. Hal ini mengakibatkan tindakan medis invasif yang tidak perlu dan berisiko tinggi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur evaluasi end-to-end yang memisahkan pembagian data validasi secara temporal, mengisolasi saluran transformasi data (*leak-free transformers*), serta menjalankan komputasi metrik evaluasi ganda (diskriminasi dan kalibrasi).

```
+---------------------------------------------------------------------------------------+
|                             ENTERPRISE VALIDATION ENGINE                              |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
             +-----------------------------------------------------------+
             |           1. Splitter Strategy Selector                   |
             |  - PurgedGroupTimeSeriesSplitter (Purge + Embargo)        |
             |  - StratifiedGroupKFoldSplitter                           |
             +-----------------------------------------------------------+
                                           |
                    +----------------------+----------------------+
                    | [Fold k: Indices Generation]               |
                    v                                             v
        +-----------------------+                     +-----------------------+
        |  Train Partition (k)  |                     |   Test Partition (k)  |
        +-----------------------+                     +-----------------------+
                    |                                             |
                    v                                             v
        +-----------------------+                     +-----------------------+
        | Feature Engineering   |                     | Pipeline Inference    |
        | [Fit + Transform]     |                     | [Transform Only]      |
        | *Strictly isolated*   |                     | *No Target Leak*      |
        +-----------------------+                     +-----------------------+
                    |                                             |
                    v                                             v
        +-----------------------+                     +-----------------------+
        | Model Training        |                     | Model Predictions     |
        | [Estimator.fit]       | ─── Export Weights ─> [predict_proba]       |
        +-----------------------+                     +-----------------------+
                                                                  |
                                                                  v
             +-----------------------------------------------------------+
             |            2. Metric Engine Execution Unit                |
             |  +--------------------+          +---------------------+  |
             |  | Discrimination     |          | Calibration         |  |
             |  | - ROC-AUC / PR-AUC |          | - Brier Score       |  |
             |  | - MCC / F1-Macro   |          | - ECE (Binned)      |  |
             |  +--------------------+          +---------------------+  |
             +-----------------------------------------------------------+
                                           |
                                           v
             +-----------------------------------------------------------+
             |            3. Calibration & Post-Processing               |
             |  - Reliability Diagram Generator                          |
             |  - Platt Scaler / Isotonic Regression Adjustment          |
             |  - Statistical Validation (McNemar / 5x2cv paired t-test) |
             +-----------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Purged & Embargoed Cross-Validation (De Prado Framework)
Dalam data terstruktur berbasis waktu (seperti data transaksi, log interaksi pengguna, atau pasar modal), label sering kali dihitung menggunakan informasi masa depan dalam rentang jendela tertentu $t_0 \to t_1$ (misal: label *fraud* yang baru terkonfirmasi 30 hari pasca transaksi).

Jika data uji berada di antara $t_{test\_start}$ dan $t_{test\_end}$:
- **Purging**: Menghapus seluruh instans dari set pelatihan yang jendela observasi labelnya tumpang tindih (*overlap*) dengan rentang jendela data uji.
- **Embargoing**: Menghapus sebagian data pelatihan yang terjadi **segera setelah** jendela data uji berakhir ($[t_{test\_end}, t_{test\_end} + h]$), untuk menghilangkan efek memori serial atau *autoregressive leakage*.

```
Time Axis ──>
[------- TRAIN SET -------] [PURGE] [=== TEST SET ===] [EMBARGO] [------- TRAIN SET -------]
                                   ^                 ^
                                   t_test_start      t_test_end
```

#### B. Probability Calibration Mechanism
Keluaran model seperti SVM, Random Forest, atau bahkan *Deep Neural Networks* modern sering kali menghasilkan skor yang tidak terkalibrasi (*overconfident* akibat regularisasi bobot atau normalisasi internal).

1. **Platt Scaling (Sigmoid Model)**:
   Mentransformasikan logit atau output model $f(x)$ menjadi probabilitas melalui regresi logistik univariat:
   $$P(y=1 \mid f(x)) = \frac{1}{1 + \exp(A \cdot f(x) + B)}$$
   Parameter $A$ dan $B$ diestimasi menggunakan *Maximum Likelihood Estimation* (MLE) pada himpunan validasi terpisah untuk mencegah overfitting.

2. **Isotonic Regression**:
   Metode non-parametrik yang menggunakan regresi monotonik bertingkat (*monotonically non-decreasing step function*):
   $$\min \sum_{i=1}^N (y_i - m(f(x_i)))^2 \quad \text{dengan syarat } m(f(x_i)) \le m(f(x_j)) \text{ jika } f(x_i) \le f(x_j)$$
   Isotonic regression lebih fleksibel daripada Platt Scaling, namun rentan *overfitting* jika ukuran sampel validasi kecil ($N < 1000$).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistematis *Enterprise Model Evaluation Engine* dalam Python 3.11+, menggunakan arsitektur modular yang mencakup kustomisasi *Purged Splitter*, engine metrik evaluasi lengkap, kalibrasi probabilitas, dan penanganan kesalahan defensif.

```python
"""
Enterprise-Grade Model Evaluation and Validation Engine.
Author: Principal AI Engineer
Language: Python 3.11+
Dependencies: numpy, scipy, scikit-learn, pandas
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Protocol, Tuple, Union

import numpy as np
import pandas as pd
from scipy.stats import distributions
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("ValidationEngine")


@dataclass(frozen=True)
class EvaluationMetricsResult:
    """Immutable data container untuk menyimpan metrik hasil evaluasi."""
    roc_auc: float
    pr_auc: float
    mcc: float
    brier_score: float
    expected_calibration_error: float
    confusion_matrix: Dict[str, int]
    raw_bins_data: Optional[Dict[str, np.ndarray]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "roc_auc": round(self.roc_auc, 5),
            "pr_auc": round(self.pr_auc, 5),
            "mcc": round(self.mcc, 5),
            "brier_score": round(self.brier_score, 5),
            "expected_calibration_error": round(self.expected_calibration_error, 5),
            "confusion_matrix": self.confusion_matrix,
        }


class PurgedGroupTimeSeriesSplit:
    """
    Purged and Embargoed Time-Series Cross-Validator.
    Mencegah temporal leakage dengan membersihkan data observasi yang overlap
    dan menerapkan jendela embargo pasca-evaluasi.
    """
    def __init__(
        self,
        n_splits: int = 5,
        max_train_group_size: Optional[int] = None,
        group_gap: int = 0,
        embargo_pct: float = 0.01,
    ) -> None:
        if n_splits < 2:
            raise ValueError(f"n_splits harus >= 2, diterima: {n_splits}")
        if not (0.0 <= embargo_pct < 1.0):
            raise ValueError(f"embargo_pct harus berada dalam rentang [0.0, 1.0), diterima: {embargo_pct}")

        self.n_splits = n_splits
        self.max_train_group_size = max_train_group_size
        self.group_gap = group_gap
        self.embargo_pct = embargo_pct

    def split(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Menghasilkan indeks Train dan Test dengan proteksi Purging & Embargo.
        """
        if groups is None:
            raise ValueError("Parameter 'groups' (penanda urutan waktu/event) wajib disediakan.")

        n_samples = len(X)
        group_array = np.asarray(groups)
        unique_groups = np.unique(group_array)
        n_groups = len(unique_groups)

        if self.n_splits > n_groups:
            raise ValueError(f"Jumlah n_splits ({self.n_splits}) melebihi jumlah grup unik ({n_groups}).")

        embargo = int(n_samples * self.embargo_pct)
        test_group_size = n_groups // self.n_splits

        for i in range(self.n_splits):
            test_group_start = i * test_group_size
            test_group_end = test_group_start + test_group_size if i < self.n_splits - 1 else n_groups

            test_groups_current = unique_groups[test_group_start:test_group_end]
            test_mask = np.isin(group_array, test_groups_current)
            test_indices = np.where(test_mask)[0]

            if len(test_indices) == 0:
                continue

            test_idx_start = test_indices[0]
            test_idx_end = test_indices[-1]

            # Evaluasi Masking Training
            train_mask = np.ones(n_samples, dtype=bool)
            
            # 1. Purge window uji langsung
            train_mask[test_indices] = False

            # 2. Embargo window (memotong n-sampel tepat setelah jendela test)
            embargo_end = min(test_idx_end + embargo, n_samples)
            train_mask[test_idx_end:embargo_end] = False

            train_indices = np.where(train_mask)[0]

            if len(train_indices) == 0:
                raise RuntimeError(f"Fold {i} menghasilkan set training kosong. Sesuaikan embargo_pct atau n_splits.")

            yield train_indices, test_indices


class CoreMetricsEngine:
    """
    Mesin kalkulasi metrik evaluasi diskriminasi dan kalibrasi native.
    Mengeliminasi asumsi format dan mengoptimalkan komputasi numerik.
    """

    @staticmethod
    def compute_confusion_matrix(
        y_true: np.ndarray, y_pred_binary: np.ndarray
    ) -> Tuple[int, int, int, int]:
        """Menghitung Confusion Matrix: TP, FP, TN, FN."""
        tp = int(np.sum((y_true == 1) & (y_pred_binary == 1)))
        fp = int(np.sum((y_true == 0) & (y_pred_binary == 1)))
        tn = int(np.sum((y_true == 0) & (y_pred_binary == 0)))
        fn = int(np.sum((y_true == 1) & (y_pred_binary == 0)))
        return tp, fp, tn, fn

    @staticmethod
    def compute_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
        """Kalkulasi ROC-AUC menggunakan algoritma integrasi trapezoidal berbasis ranking."""
        order = np.lexsort((np.random.permutation(len(y_score)), y_score))[::-1]
        y_true_sorted = y_true[order]

        n_pos = np.sum(y_true == 1)
        n_neg = len(y_true) - n_pos

        if n_pos == 0 or n_neg == 0:
            logger.warning("Hanya satu kelas yang terdeteksi dalam label ground truth. ROC-AUC tidak terdefinisi.")
            return np.nan

        # Mann-Whitney U test statistic
        rank = len(y_score) - np.arange(len(y_score))
        rank_sum_pos = np.sum(rank[y_true_sorted == 1])
        u_stat = rank_sum_pos - (n_pos * (n_pos + 1)) / 2.0
        return float(u_stat / (n_pos * n_neg))

    @staticmethod
    def compute_pr_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
        """Kalkulasi Precision-Recall AUC (Average Precision)."""
        order = np.argsort(y_score)[::-1]
        y_true_sorted = y_true[order]

        tp_cumsum = np.cumsum(y_true_sorted == 1)
        fp_cumsum = np.cumsum(y_true_sorted == 0)

        recalls = tp_cumsum / np.maximum(tp_cumsum[-1], 1e-12)
        precisions = tp_cumsum / np.maximum(tp_cumsum + fp_cumsum, 1e-12)

        # Tambahkan boundary points untuk integrasi numerik
        recalls = np.concatenate(([0.0], recalls))
        precisions = np.concatenate(([1.0], precisions))

        # Integrasi Riemann (Trapezoidal Rule)
        return float(np.sum((recalls[1:] - recalls[:-1]) * precisions[1:]))

    @staticmethod
    def compute_mcc(tp: int, fp: int, tn: int, fn: int) -> float:
        """Kalkulasi Matthews Correlation Coefficient dengan mitigasi pembagian nol."""
        numerator = (tp * tn) - (fp * fn)
        denominator = np.sqrt(
            float(tp + fp) * float(tp + fn) * float(tn + fp) * float(tn + fn)
        )
        if denominator == 0.0:
            return 0.0
        return float(numerator / denominator)

    @staticmethod
    def compute_brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
        """Kalkulasi Brier Score."""
        return float(np.mean((y_prob - y_true) ** 2))

    @classmethod
    def compute_expected_calibration_error(
        cls, y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
    ) -> Tuple[float, Dict[str, np.ndarray]]:
        """
        Kalkulasi ECE menggunakan Uniform Binning.
        Mengembalikan skor ECE dan metadata diagram kalibrasi.
        """
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        bin_assignments = np.digitize(y_prob, bins) - 1

        ece = 0.0
        n_samples = len(y_true)
        
        bin_accuracies = np.zeros(n_bins)
        bin_confidences = np.zeros(n_bins)
        bin_counts = np.zeros(n_bins)

        for i in range(n_bins):
            in_bin = bin_assignments == i
            bin_size = np.sum(in_bin)
            bin_counts[i] = bin_size

            if bin_size > 0:
                avg_confidence = np.mean(y_prob[in_bin])
                avg_accuracy = np.mean(y_true[in_bin])
                
                bin_accuracies[i] = avg_accuracy
                bin_confidences[i] = avg_confidence
                
                ece += (bin_size / n_samples) * np.abs(avg_accuracy - avg_confidence)

        bins_data = {
            "counts": bin_counts,
            "accuracies": bin_accuracies,
            "confidences": bin_confidences,
            "edges": bins,
        }
        return float(ece), bins_data

    @classmethod
    def evaluate(
        cls,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        threshold: float = 0.5,
        n_bins: int = 10,
    ) -> EvaluationMetricsResult:
        """Menjalankan evaluasi komprehensif pada probabilitas prediksi."""
        if len(y_true) != len(y_prob):
            raise ValueError(f"Dimensi mismatch: len(y_true)={len(y_true)} != len(y_prob)={len(y_prob)}")

        y_true = np.asarray(y_true, dtype=int)
        y_prob = np.asarray(y_prob, dtype=float)

        # Validasi domain probabilitas
        if np.any((y_prob < 0.0) | (y_prob > 1.0)):
            raise ValueError("Keluaran y_prob harus berada dalam domain valid [0.0, 1.0].")

        y_pred = (y_prob >= threshold).astype(int)
        tp, fp, tn, fn = cls.compute_confusion_matrix(y_true, y_pred)

        roc_auc = cls.compute_roc_auc(y_true, y_prob)
        pr_auc = cls.compute_pr_auc(y_true, y_prob)
        mcc = cls.compute_mcc(tp, fp, tn, fn)
        brier = cls.compute_brier_score(y_true, y_prob)
        ece, bins_data = cls.compute_expected_calibration_error(y_true, y_prob, n_bins)

        return EvaluationMetricsResult(
            roc_auc=roc_auc,
            pr_auc=pr_auc,
            mcc=mcc,
            brier_score=brier,
            expected_calibration_error=ece,
            confusion_matrix={"TP": tp, "FP": fp, "TN": tn, "FN": fn},
            raw_bins_data=bins_data,
        )


class ProbabilityCalibrator:
    """
    Komponen Kalibrasi Probabilitas Pasca-Pemrosesan.
    Mendukung Platt Scaling (Logistik) dan Non-Parametric Isotonic Regression.
    """
    def __init__(self, method: str = "isotonic") -> None:
        if method not in ["platt", "isotonic"]:
            raise ValueError(f"Metode tidak didukung: {method}. Pilih 'platt' atau 'isotonic'.")
        self.method = method
        self.calibrator: Optional[Union[LogisticRegression, IsotonicRegression]] = None

    def fit(self, y_prob_uncalibrated: np.ndarray, y_true: np.ndarray) -> ProbabilityCalibrator:
        """Melatih calibrator pada dataset validasi terpisah."""
        y_prob_uncalibrated = np.clip(y_prob_uncalibrated, 1e-15, 1 - 1e-15)

        if self.method == "platt":
            # Platt scaling: Logistic Regression pada Log-Odds
            logits = np.log(y_prob_uncalibrated / (1.0 - y_prob_uncalibrated)).reshape(-1, 1)
            self.calibrator = LogisticRegression(C=1.0, solver="lbfgs")
            self.calibrator.fit(logits, y_true)
        else:
            # Isotonic Regression: Monotonic Fit
            self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            self.calibrator.fit(y_prob_uncalibrated, y_true)

        return self

    def predict_proba(self, y_prob_uncalibrated: np.ndarray) -> np.ndarray:
        """Mentransformasikan uncalibrated probabilities menjadi calibrated probabilities."""
        if self.calibrator is None:
            raise RuntimeError("Calibrator belum difit. Panggil .fit() terlebih dahulu.")

        y_prob_uncalibrated = np.clip(y_prob_uncalibrated, 1e-15, 1 - 1e-15)

        if self.method == "platt":
            logits = np.log(y_prob_uncalibrated / (1.0 - y_prob_uncalibrated)).reshape(-1, 1)
            # Mengembalikan probabilitas kelas 1
            return self.calibrator.predict_proba(logits)[:, 1]
        else:
            return self.calibrator.predict(y_prob_uncalibrated)


class StatisticalSignificanceAuditor:
    """
    Engine Pengujian Hipotesis Statistik antar Performa Model.
    Mencegah ilusi keunggulan model yang timbul karena fluktuasi acak.
    """

    @staticmethod
    def mcnemar_test(
        y_true: np.ndarray,
        y_pred_model_a: np.ndarray,
        y_pred_model_b: np.ndarray,
    ) -> Tuple[float, float]:
        """
        Menjalankan McNemar's Test dengan koreksi kontinuitas Edwards.
        Digunakan untuk perbandingan performa klasifikasi biner berpasangan.
        """
        y_true = np.asarray(y_true)
        pred_a = np.asarray(y_pred_model_a)
        pred_b = np.asarray(y_pred_model_b)

        # Kontingensi Klasifikasi:
        # b: Model A benar, Model B salah
        # c: Model A salah, Model B benar
        correct_a = pred_a == y_true
        correct_b = pred_b == y_true

        b = np.sum(correct_a & (~correct_b))
        c = np.sum((~correct_a) & correct_b)

        total_discordant = b + c
        if total_discordant == 0:
            return 0.0, 1.0

        # McNemar statistic dengan kontinuitas Edwards: (|b - c| - 1)^2 / (b + c)
        statistic = (np.abs(b - c) - 1.0) ** 2 / total_discordant
        p_value = 1.0 - distributions.chi2.cdf(statistic, df=1)

        return float(statistic), float(p_value)
```

---

### 7. Edge Cases & Failure Modes (Error Recovery & Proteksi Runtime)

1. **Kelas Tunggal dalam Lipatan Validasi (*Zero Variance Target*)**:
   - *Failure Mode*: Jika stratifikasi temporal memotong segmen waktu tanpa ada label minoritas ($y_i = 0$ untuk seluruh $i$), metrik seperti *ROC-AUC* dan *MCC* menghasilkan ekspresi $\frac{0}{0}$ (*undefined / NaN*).
   - *Mitigasi*: Implementasikan *fallback assertion* pada *Splitter*. Jika lipatan uji tidak memiliki minimal $k$ sampel kelas minoritas ($k \ge 2$), lipatan harus digabungkan (*merged*) secara deterministik ke lipatan berikutnya, atau sistem mengeksekusi *early warning exit* dengan nilai `np.nan` tanpa memicu crash kernel.

2. **Probabilitas Prediksi Kolaps (*Model Degeneracy / Extreme Overconfidence*)**:
   - *Failure Mode*: Model deep learning atau boosting menghasilkan logit ekstrem yang menyebabkan probabilitas numerik menjadi tepat $0.000000$ atau $1.000000$. Saat dimasukkan ke logaritma *Platt Scaling* (kalkulasi *odds ratio*), terjadi error pembagian nol (*division by zero* / `log(0)`).
   - *Mitigasi*: Lakukan pemotongan nilai (*epsilon-clipping*) secara defensif sebelum transformasi kalkulasi rasio odds:
     $$\hat{p}_{clipped} = \text{clip}(\hat{p}, \varepsilon, 1 - \varepsilon), \quad \varepsilon = 10^{-15}$$

3. **Inversi Monotonisitas Kalibrasi Non-Parametrik (*Overfitting Isotonic*)**:
   - *Failure Mode*: Pada dataset kecil ($N < 500$), *Isotonic Regression* dapat mengalami *overfitting* lokal dan memetakan rentang probabilitas yang luas ke satu nilai flat (*step artifact*), yang secara semu menghasilkan *ECE* rendah pada training tetapi merusak prediksi di produksi.
   - *Mitigasi*: Buat ambang batas seleksi otomatis: jika ukuran himpunan kalibrasi $N < 1000$, sistem secara otomatis memaksa penggunaan *Platt Scaling* (parametrik) daripada *Isotonic Regression*.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Evaluasi | Pilihan A: K-Fold Tradisional | Pilihan B: Purged Group Time-Series | Trade-off / Justifikasi |
| :--- | :--- | :--- | :--- |
| **Validitas Sampel Temporal** | Sangat Buruk (*Look-ahead bias* tinggi) | **Sangat Tinggi** (*Leakage-free*) | Skema Purged mengurangi jumlah data pelatihan bersih yang tersedia, namun mencerminkan kenyataan runtime produksi. |
| **Komputasi & Overhead** | Rendah ($O(K)$ kalkulasi) | Menengah-Tinggi (Purging overhead) | Biaya pruning indeks sebanding dengan perlindungan dari kegagalan sistematis inferensi live. |
| **Metrik: ROC-AUC vs PR-AUC** | ROC-AUC (Global ranking) | PR-AUC (Imbalance focus) | Gunakan PR-AUC ketika *False Positive* pada kelas 0.1% menyebabkan *cost* ekonomi yang masif (misal: memblokir transaksi nasabah valid). |
| **Metode Kalibrasi** | Platt Scaling (Regresi Logistik) | Isotonic Regression | Platt scaling menjaga bentuk fungsi sigmoid parametrik tetapi terbatas pada kurva logistik monoton. Isotonic sangat fleksibel namun rentan overfitting pada data sedikit. |

---

### 9. Best Practices & Standard Industri

1. **Pipeline Immutability**: Pembagian dataset (*splitting*) harus terjadi **sebelum** normalisasi fitur, imputasi *missing values*, atau encoding variabel kategorikal. Seluruh objek *fit* transformasi prapemrosesan harus hanya mempelajari statistik parameter dari partisi `Train_k` dan sekadar mengeksekusi `.transform()` pada partisi `Test_k`.
2. **Deterministic Seed Locks**: Gunakan seed pengacak yang seragam namun terisolasi dalam pengujian validasi untuk menjamin reproduktibilitas audit kepatuhan (*governance compliance* seperti Basel III/IV untuk Finansial atau FDA SaMD untuk Kesehatan).
3. **Dual Metric Gates**: Jangan pernah merilis model ke tahap *canary deployment* hanya berdasarkan metrik diskriminatif ($AUC$). Tetapkan *Service Level Objective* (SLO) ganda:
   $$\text{Production Gate} = (PR\_AUC \ge \tau_1) \land (ECE \le \tau_2) \land (\text{p-value}_{\text{McNemar}} < 0.05)$$
4. **Reliability Diagram Bin Count**: Hindari penentuan bin sembarangan pada *ECE*. Standar industri adalah $M=10$ atau $M=15$ bins berukuran seragam (*equal-width*) untuk visualisasi, dipasangkan dengan analisis *quantile-based binning* (*equal-frequency*) untuk memastikan kestabilan estimasi pada ekor distribusi.

---

### 10. Hands-on Lab Exercise: Implementasi Leak-Free Validation Pipeline

#### Skenario Lab
Anda adalah Lead ML Engineer pada sistem deteksi penipuan kartu kredit (*credit card fraud*). Data memiliki dependensi temporal yang ketat dan ketimpangan kelas yang parah (rasio positif 1.5%). 

Tugas Anda:
1. Menghasilkan dataset sintetik temporal dengan latensi konfirmasi label.
2. Membandingkan estimasi evaluasi antara *Standard Random Split* (dengan kebocoran) vs *Purged Time-Series Split*.
3. Menganalisis kurva kalibrasi awal, mengaplikasikan *Platt Scaling*, dan mengukur penurunan *Expected Calibration Error (ECE)*.

#### Langkah Eksekusi (Skrip Lengkap yang Dapat Dijalankan Langsung)

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# 1. SETUP SIMULASI DATASET DENGAN AUTOKORELASI & TEMPORAL DRIFT
np.random.seed(42)
n_records = 5000

# Simulasikan data transaksi 100 hari
timestamps = np.sort(np.random.uniform(1.0, 100.0, n_records))
user_ids = np.random.randint(100, 500, n_records)

# Fitur sintetis: Transaksi amount dan anomaly signal
X_feature1 = np.random.exponential(scale=50.0, size=n_records)
# Injeksi korelasi serial pada fitur 2
X_feature2 = np.sin(timestamps / 5.0) + np.random.normal(0, 0.5, n_records)

# Target biner: Fraud (imbalance ~2%) dipengaruhi feature dan autokorelasi
fraud_logits = -4.0 + (0.015 * X_feature1) + (0.8 * X_feature2)
fraud_prob = 1.0 / (1.0 + np.exp(-fraud_logits))
y_target = (np.random.rand(n_records) < fraud_prob).astype(int)

df = pd.DataFrame({
    "timestamp": timestamps,
    "user_id": user_ids,
    "feature_amt": X_feature1,
    "feature_signal": X_feature2,
    "target": y_target
})

print(f"Dataset Shape: {df.shape} | Total Fraud: {df['target'].sum()} ({df['target'].mean()*100:.2f}%)")

# 2. VALIDASI NAIF (RANDOM SPLIT - VULNERABLE TO TEMPORAL LEAKAGE)
indices = np.arange(n_records)
np.random.shuffle(indices)
split_point = int(n_records * 0.8)

train_idx_naive, test_idx_naive = indices[:split_point], indices[split_point:]

X_train_naive = df.iloc[train_idx_naive][["feature_amt", "feature_signal"]].values
y_train_naive = df.iloc[train_idx_naive]["target"].values

X_test_naive = df.iloc[test_idx_naive][["feature_amt", "feature_signal"]].values
y_test_naive = df.iloc[test_idx_naive]["target"].values

clf_naive = RandomForestClassifier(n_estimators=50, random_state=42)
clf_naive.fit(X_train_naive, y_train_naive)
preds_naive = clf_naive.predict_proba(X_test_naive)[:, 1]

eval_naive = CoreMetricsEngine.evaluate(y_test_naive, preds_naive)
print("\n[HASIL VALIDASI NAIF (BOCOR)]")
print(f"ROC-AUC: {eval_naive.roc_auc:.4f} | PR-AUC: {eval_naive.pr_auc:.4f} | ECE: {eval_naive.expected_calibration_error:.4f}")

# 3. VALIDASI KETAT (PURGED & EMBARGOED TIME-SERIES CROSS-VALIDATION)
# Setup Purged Group Splitter dengan Embargo 2% (~100 observasi terhapus setelah window uji)
cv_purged = PurgedGroupTimeSeriesSplit(n_splits=4, embargo_pct=0.02)
# Gunakan binning hari (timestamp) sebagai grup urutan waktu
df["time_group"] = np.floor(df["timestamp"]).astype(int)

purged_roc_aucs = []
purged_pr_aucs = []
purged_eces = []

for fold, (train_idx, test_idx) in enumerate(cv_purged.split(df, groups=df["time_group"])):
    X_tr = df.iloc[train_idx][["feature_amt", "feature_signal"]].values
    y_tr = df.iloc[train_idx]["target"].values
    
    X_te = df.iloc[test_idx][["feature_amt", "feature_signal"]].values
    y_te = df.iloc[test_idx]["target"].values
    
    # Lewati lipatan uji yang tidak memiliki instans minoritas
    if np.sum(y_te) == 0:
        continue

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_tr, y_tr)
    y_prob_uncal = model.predict_proba(X_te)[:, 1]
    
    res = CoreMetricsEngine.evaluate(y_te, y_prob_uncal)
    purged_roc_aucs.append(res.roc_auc)
    purged_pr_aucs.append(res.pr_auc)
    purged_eces.append(res.expected_calibration_error)

print("\n[HASIL PURGED & EMBARGOED CROSS-VALIDATION]")
print(f"Mean Purged ROC-AUC : {np.mean(purged_roc_aucs):.4f} +/- {np.std(purged_roc_aucs):.4f}")
print(f"Mean Purged PR-AUC  : {np.mean(purged_pr_aucs):.4f} +/- {np.std(purged_pr_aucs):.4f}")
print(f"Mean Purged ECE     : {np.mean(purged_eces):.4f} +/- {np.std(purged_eces):.4f}")

# 4. IMPLEMENTASI DAN AUDIT KALIBRASI PROBABILITAS
# Kalibrasi model pada lipatan terakhir menggunakan Isotonic Regression
calibrator = ProbabilityCalibrator(method="isotonic")

# Gunakan separuh data pengujian untuk kalibrasi, separuh untuk pengujian akhir
half_test = len(X_te) // 2
calib_train_x, eval_test_x = y_prob_uncal[:half_test], y_prob_uncal[half_test:]
calib_train_y, eval_test_y = y_te[:half_test], y_te[half_test:]

calibrator.fit(calib_train_x, calib_train_y)
y_prob_calibrated = calibrator.predict_proba(eval_test_x)

pre_calib_eval = CoreMetricsEngine.evaluate(eval_test_y, eval_test_x)
post_calib_eval = CoreMetricsEngine.evaluate(eval_test_y, y_prob_calibrated)

print("\n[AUDIT KALIBRASI PASCA-PROSES]")
print(f"Sebelum Kalibrasi -> Brier Score: {pre_calib_eval.brier_score:.5f} | ECE: {pre_calib_eval.expected_calibration_error:.5f}")
print(f"Sesudah Kalibrasi -> Brier Score: {post_calib_eval.brier_score:.5f} | ECE: {post_calib_eval.expected_calibration_error:.5f}")

# 5. PENGUJIAN SIGNIFIKANSI STATISTIK (MCNEMAR TEST)
y_pred_pre = (eval_test_x >= 0.5).astype(int)
y_pred_post = (y_prob_calibrated >= 0.5).astype(int)

chi2_stat, p_val = StatisticalSignificanceAuditor.mcnemar_test(
    eval_test_y, y_pred_pre, y_pred_post
)
print(f"\nMcNemar Test Result: Chi2-Stat = {chi2_stat:.4f}, p-value = {p_val:.4e}")
if p_val < 0.05:
    print("Kesimpulan: Perubahan performa klasifikasi signifikan secara statistik (H0 ditolak).")
else:
    print("Kesimpulan: Perubahan performa klasifikasi tidak signifikan secara statistik (Gagal menolak H0).")
```