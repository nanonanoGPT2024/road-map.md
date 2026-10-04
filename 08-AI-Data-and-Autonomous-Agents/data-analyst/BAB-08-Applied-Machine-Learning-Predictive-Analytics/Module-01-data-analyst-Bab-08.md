# Bab 08: Applied Machine Learning & Predictive Analytics for Analysts

## Modul 01: Production-Grade Feature Engineering dan Pipeline Prediktif Bebas Kebocoran Data (Data Leakage)

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

*   **Merancang dan Mengimplementasikan** arsitektur *feature engineering* modular menggunakan `scikit-learn` *Custom Transformers* dan *Pipelines* yang sepenuhnya terisolasi dari *target leakage* dan *train-test contamination*.
*   **Mengaudit dan Memitigasi** empat vektor utama kebocoran data (*temporal leakage*, *preprocessing leakage*, *target encoding leakage*, dan *group-structure leakage*) pada data tabular enterprise.
*   **Membangun** strategi validasi data tingkat lanjut (*Purged Group Time-Series Split*, *Stratified Out-of-Fold Cross-Validation*) yang mencerminkan distribusi operasional masa depan secara presisi.
*   **Mengevaluasi dan Mengkalibrasi** probabilitas keluaran model klasifikasi menggunakan metrik diskriminasi (PR-AUC, ROC-AUC) dan metrik kalibrasi (*Brier Score*, *Expected Calibration Error*), bukan sekadar metrik akurasi agregat.
*   **Mengemas** artefak analitik prediktif ke dalam modul kode Python berstandar produksi yang memiliki penanganan galat eksplisit (*error handling*), *type-hinting*, dan validasi skema input.

---

### 2. Concept Overview

Analisis prediktif bagi *data analyst* merupakan jembatan transisi dari analitik diagnostik (apa yang terjadi dan mengapa) menuju analitik preskriptif (apa yang akan terjadi dan tindakan apa yang harus diambil). Namun, kegagalan terbesar dalam transisi ini berasal dari model mental analitik tradisional: **menganggap seluruh baris data dalam tabel analitik (*data warehouse*) dapat diagregasikan dan ditransformasikan secara bersamaan**.

```
                +-------------------------------------------------------+
                |           THE TIME MACHINE FALLACY (LEAKAGE)          |
                +-------------------------------------------------------+
                | Masa Lalu (Training)          | Masa Depan (Inference)|
Data Historis:  [T_0 --------------------> T_1] | [T_2 --------------->]|
                                                |                       |
Salah (Global): [======== Global Mean / Imputation / Scaling =========] | <--- LEAKAGE!
                                                |                       |
Benar (Causal): [Fit Transform Train]           | [Transform Inference] | <--- ZERO LEAKAGE
                +-------------------------------+-----------------------+
```

#### Mental Model: *The Causal Horizon* (Horison Kausalitas)
Dalam machine learning terapan, waktu dan ketersediaan data memiliki arah yang tidak dapat dibalik (*irreversible*). Jika model Anda menggunakan informasi apa pun—baik itu mean dari sebuah kolom numerik, kemunculan kategori langka, atau tren musiman—yang pada kenyataannya baru diketahui **setelah** titik waktu prediksi dilakukan (*decision point*), model Anda menderita **Target Leakage**.

Perbedaan paradigma fundamental:
1.  **SQL Aggregation Paradigm (Analitik Deskriptif)**: Menggunakan fungsi jendela (`OVER (PARTITION BY ...)`), subquery, atau `AVG()` di seluruh tabel untuk mengisi data kosong atau menstandarisasi metrik.
2.  **State-Preserving Pipeline Paradigm (Analitik Prediktif)**: Pemisahan mutlak antara fase *belajar* (`fit`—hanya pada data latih) dan fase *eksekusi* (`transform`—pada data latih, validasi, dan data masa depan baru). Parameter transformasi (mean, standar deviasi, frekuensi kategori) adalah bobot model (*stateful artifacts*) yang harus dibekukan.

---

### 3. Why It Matters

Di lingkungan enterprise, model prediktif yang dibangun oleh analis sering kali menunjukkan performa luar biasa selama fase *proof-of-concept* (misalnya: ROC-AUC 0.96 pada validasi silang), namun hancur total saat diintegrasikan ke sistem produksi (performa jatuh menjadi ROC-AUC 0.52, setara dengan tebakan acak).

Konsekuensi nyata dari cacat arsitektur ini:
*   **Misalokasi Anggaran Retensi Pelanggan**: Model *Customer Churn* yang mengalami kebocoran data fitur penggunaan bulan depan akan memprediksi pelanggan churn secara tepat di data historis, tetapi gagal total mendeteksi pelanggan berisiko di dunia nyata. Anggaran intervensi puluhan miliar rupiah dialokasikan ke pelanggan yang salah.
*   **Lonjakan Kredit Macet (*Non-Performing Loans*)**: Model skor kredit yang dinormalisasi menggunakan seluruh data nasabah (termasuk yang masuk setelah krisis likuiditas) meremehkan risiko gagal bayar sistemik pada nasabah baru.
*   **Erosi Kepercayaan Pemangku Kepentingan**: Ketika analis menyajikan metrik akurasi semu kepada dewan direksi yang kemudian tidak terbukti di lapangan, seluruh inisiatif data-driven enterprise kehilangan mandat politik dan anggarannya.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan siklus hidup rekayasa fitur dan inferensi yang terlindungi dari kebocoran data, memisahkan secara ketat *Fit Engine* dari *Transform/Inference Engine*.

```
                      +---------------------------------------+
                      | Raw Analytics Warehouse / Data Mart   |
                      +---------------------------------------+
                                          |
                                          v
                      +---------------------------------------+
                      | Data Extraction & Split Horizon Check |
                      +---------------------------------------+
                               /                     \
       [Train Dataset (T < T_split)]             [Test/Serve Dataset (T >= T_split)]
                     |                                         |
                     v                                         |
       +----------------------------+                          |
       |  Fit Stateful Transformers |                          |
       |  - Median Imputers         |                          |
       |  - Outlier Bounds (IQR)    |                          |
       |  - Target Encoders (OOF)   |                          |
       |  - Standard Scalers        |                          |
       +----------------------------+                          |
                     |                                         |
          Learned Transformers State                           |
          (Mean, Medians, Mappings)                            |
                     |                                         |
                     +--------------------+                    |
                     |                    |                    |
                     v                    v                    v
       +----------------------------+   +----------------------------+
       | Transform Training Set     |   | Transform Inference Set    |
       | (Apply learned statistics) |   | (NO fitting allowed!)      |
       +----------------------------+   +----------------------------+
                     |                                         |
                     v                                         v
       +----------------------------+   +----------------------------+
       | Model Training             |   | Model Inference            |
       | (e.g., HistGB / LogReg)    |   | (Generate calibrated prob) |
       +----------------------------+   +----------------------------+
                     \                                         /
                      \                                       /
                       v                                     v
       +---------------------------------------------------------------+
       | Validation & Audit: ROC-AUC, PR-AUC, Brier Score, Drift Check |
       +---------------------------------------------------------------+
```

Diagram alir komponen internal dari Scikit-Learn Custom Pipeline:

```
[Raw Input DataFrame]
         |
         v
+---------------------------------------------------------------------------------+
| scikit-learn ColumnTransformer                                                  |
|                                                                                 |
|  [Numeric Features]        [Categorical Features]       [Cyclical Time Features]|
|          |                           |                             |            |
|          v                           v                             v            |
|  +--------------------+    +--------------------+       +--------------------+  |
|  | OutlierCapTransformer |  | RobustImputer      |       | SineCosineEncoder  |  |
|  +--------------------+    +--------------------+       +--------------------+  |
|          |                           |                             |            |
|          v                           v                             |            |
|  +--------------------+    +--------------------+                  |            |
|  | RobustScaler       |    | TargetEncoder (OOF)|                  |            |
|  +--------------------+    +--------------------+                  |            |
+---------------------------------------------------------------------------------+
                                       |
                                       v
                     +-----------------------------------+
                     | Calibrated Classifier / Estimator |
                     +-----------------------------------+
                                       |
                                       v
                     [Predictions: Probs & Audit Metrics]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Vektor-Vektor Kebocoran Data (Data Leakage Vectors)
1.  **Preprocessing Leakage (Skalisasi Global)**: Menjalankan `StandardScaler()`, `MinMaxScaler()`, atau imputasi data hilang pada seluruh matriks sebelum membagi (*splitting*) dataset. Akibatnya, nilai $\mu$ (mean) dan $\sigma$ (standar deviasi) dari set validasi/pengujian telah mencemari set pelatihan.
2.  **Out-of-Fold Target Encoding Leakage**: Menghitung rata-rata target untuk setiap kategori pada seluruh dataset. Kategori langka akan mendapatkan nilai representasi yang identik dengan target sebenarnya, memicu *overfitting* fatal. Target encoding wajib dilakukan menggunakan skema *K-Fold Out-of-Fold* (OOF) atau penghalusan Bayesian (*Empirical Bayes Smoothing*):
    $$\hat{S}_i = \frac{n_i \cdot \bar{y}_i + m \cdot \bar{y}_{global}}{n_i + m}$$
    di mana $n_i$ adalah jumlah sampel dalam kategori $i$, $\bar{y}_i$ adalah mean target kategori, $\bar{y}_{global}$ adalah prior target global, dan $m$ adalah bobot smoothing (*pseudo-counts*).
3.  **Temporal Look-ahead Bias**: Menggunakan fitur agregasi seperti `total_transaksi_30_hari_terakhir` di mana rentang 30 hari dihitung relatif terhadap waktu ekstraksi basis data, bukan relatif terhadap tanggal peristiwa spesifik (*observation event date*).
4.  **Group / Identity Contamination**: Pelanggan atau entitas yang sama memiliki beberapa baris transaksi yang tersebar di antara set latih dan set uji. Model menghafal karakteristik idiosyncratic pelanggan tertentu alih-alih mempelajari pola prediktif umum.

#### 5.2 Strategi Partisi Validasi Bebas Kontaminasi
*   **Stratified Time-Series Split**: Ketika data memiliki dependensi waktu dan ketidakseimbangan kelas (*class imbalance*). Kita membagi data berdasarkan horizon waktu absolut, tetapi mempertahankan rasio kelas target pada setiap *fold*.
*   **Purged & Embargoed Cross-Validation**: Ketika entitas memiliki periode efek residu (misalnya promosi yang efeknya bertahan selama 7 hari). Jendela data di antara set latih dan set validasi harus dibersihkan (*purged*) sebesar durasi retensi informasi untuk mencegah korelasi serial.

#### 5.3 Kalibrasi Probabilitas
Akurasi sering kali menjadi metrik yang menyesatkan. Untuk kebutuhan analitik bisnis, yang dibutuhkan adalah **probabilitas terkalibrasi secara empiris**: jika model memprediksi sekumpulan akun memiliki risiko churn 80%, maka secara riil 80 dari 100 akun tersebut harus benar-benar churn.
*   **Brier Score**: Mengukur *Mean Squared Error* dari probabilitas prediksi terhadap kejadian aktual:
    $$BS = \frac{1}{N}\sum_{t=1}^N (f_t - o_t)^2$$
    di mana $f_t$ adalah probabilitas yang diprediksi dan $o_t \in \{0, 1\}$ adalah hasil aktual. Nilai 0 menunjukkan kalibrasi dan diskriminasi sempurna.
*   **Isotonic Regression vs. Platt Scaling**: Transformasi non-parametrik monotonik vs. pemetaan logistik parametrik untuk memperbaiki bias probabilitas pada output model (terutama model ensemble berbasis pohon seperti Gradient Boosting yang cenderung menghasilkan skor terdistorsi di dekat margin batas keputusan).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul rekayasa fitur dan pemodelan prediktif berbasis Python berstandar enterprise.

```python
"""
predictive_pipeline.py
======================
Modul rekayasa fitur skala produksi dan pipeline validasi prediktif bebas
kebocoran data (zero data leakage) untuk data tabular analitik enterprise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

# Setup Logging Industri
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AppliedMLPipeline")


@dataclass(frozen=True)
class PipelineConfig:
    """Konfigurasi skema kolom dan hiperparameter pipeline."""
    target_column: str
    group_column: str
    numeric_features: List[str]
    categorical_features: List[str]
    date_column: Optional[str] = None
    random_state: int = 42
    n_splits: int = 5
    smoothing_weight: float = 10.0


class OutlierCapper(BaseEstimator, TransformerMixin):
    """
    Menangani nilai pencilan (outliers) menggunakan metode Interquartile Range (IQR).
    State bounds dihitung HANYA pada saat .fit() untuk menghindari kebocoran data.
    """

    def __init__(self, factor: float = 1.5) -> None:
        self.factor = factor
        self.lower_bounds_: Dict[str, float] = {}
        self.upper_bounds_: Dict[str, float] = {}
        self.columns_: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "OutlierCapper":
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        self.columns_ = list(X.columns)
        for col in self.columns_:
            q25 = X[col].quantile(0.25)
            q75 = X[col].quantile(0.75)
            iqr = q75 - q25
            self.lower_bounds_[col] = q25 - (self.factor * iqr)
            self.upper_bounds_[col] = q75 + (self.factor * iqr)

        logger.info("OutlierCapper: Fitted IQR bounds untuk %d fitur.", len(self.columns_))
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.columns_)

        X_clipped = X.copy()
        for col in self.columns_:
            if col in self.lower_bounds_ and col in self.upper_bounds_:
                X_clipped[col] = X_clipped[col].clip(
                    lower=self.lower_bounds_[col],
                    upper=self.upper_bounds_[col]
                )
        return X_clipped


class BayesianTargetEncoder(BaseEstimator, TransformerMixin):
    """
    Menghitung Target Encoding menggunakan Empirical Bayes Smoothing.
    Didesain khusus untuk menghindari label memorization pada kategori berkardinalitas tinggi.
    """

    def __init__(self, smoothing: float = 10.0) -> None:
        self.smoothing = smoothing
        self.global_mean_: float = 0.0
        self.encoding_map_: Dict[str, Dict[Any, float]] = {}
        self.columns_: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BayesianTargetEncoder":
        if y is None:
            raise ValueError("BayesianTargetEncoder membutuhkan target vektor 'y' pada fase fit.")

        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X)

        self.columns_ = list(X.columns)
        self.global_mean_ = float(y.mean())
        self.encoding_map_ = {}

        for col in self.columns_:
            col_series = X[col].astype(str)
            stats = y.groupby(col_series).agg(["count", "mean"])
            
            # Rumus Smoothing Bayesian
            smoothed = (
                (stats["count"] * stats["mean"]) + (self.smoothing * self.global_mean_)
            ) / (stats["count"] + self.smoothing)
            
            self.encoding_map_[col] = smoothed.to_dict()

        logger.info("BayesianTargetEncoder: Berhasil mengonversi %d kolom kategoris.", len(self.columns_))
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(X, columns=self.columns_)

        X_encoded = X.copy()
        for col in self.columns_:
            mapping = self.encoding_map_.get(col, {})
            # Konversi string dan gunakan global_mean_ sebagai fallback jika unseen kategori
            X_encoded[col] = (
                X_encoded[col]
                .astype(str)
                .map(mapping)
                .fillna(self.global_mean_)
                .astype(float)
            )

        return X_encoded.values


class LeakageFreePredictiveEngine:
    """
    Arsitektur orkestrasi model prediktif: Preprocessing -> Estimator -> Calibration.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.pipeline: Optional[Pipeline] = None
        self.metrics_: Dict[str, float] = {}

    def _build_feature_pipeline(self) -> ColumnTransformer:
        """Merakit isolasi transformasi data numerik dan kategorik."""
        numeric_subpipeline = Pipeline(
            steps=[
                ("outlier_capper", OutlierCapper(factor=1.5)),
                ("scaler", RobustScaler(with_centering=True, with_scaling=True)),
            ]
        )

        categorical_subpipeline = Pipeline(
            steps=[
                (
                    "target_encoder",
                    BayesianTargetEncoder(smoothing=self.config.smoothing_weight),
                )
            ]
        )

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "num",
                    numeric_subpipeline,
                    self.config.numeric_features,
                ),
                (
                    "cat",
                    categorical_subpipeline,
                    self.config.categorical_features,
                ),
            ],
            remainder="drop",
        )
        return preprocessor

    def train_and_validate(
        self, df: pd.DataFrame
    ) -> Tuple[Pipeline, Dict[str, float]]:
        """
        Mengeksekusi stratified group cross-validation untuk mencegah group leakage,
        kemudian melatih pipeline akhir pada keseluruhan data.
        """
        logger.info("Validasi skema dan inisialisasi pelatihan pipeline...")
        
        # Ekstraksi target dan entitas pengelompokan
        X = df.drop(columns=[self.config.target_column])
        y = df[self.config.target_column].astype(int)
        groups = df[self.config.group_column]

        sgkf = StratifiedGroupKFold(
            n_splits=self.config.n_splits, 
            shuffle=True, 
            random_state=self.config.random_state
        )

        oof_predictions = np.zeros(len(df))
        oof_targets = np.zeros(len(df))

        # Iterasi cross-validation out-of-fold yang ketat
        for fold, (train_idx, val_idx) in enumerate(sgkf.split(X, y, groups=groups)):
            logger.info("Mengeksekusi Fold %d/%d...", fold + 1, self.config.n_splits)

            X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
            X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]

            # Inisialisasi estimator individual per fold
            fold_preprocessor = self._build_feature_pipeline()
            base_estimator = HistGradientBoostingClassifier(
                random_state=self.config.random_state,
                class_weight="balanced",
                max_iter=100,
            )

            fold_pipeline = Pipeline(
                steps=[
                    ("preprocessor", fold_preprocessor),
                    ("classifier", base_estimator),
                ]
            )

            # Fit HANYA pada data latih fold ini
            fold_pipeline.fit(X_train, y_train)

            # Prediksi probabilitas fold validasi
            val_probs = fold_pipeline.predict_proba(X_val)[:, 1]
            oof_predictions[val_idx] = val_probs
            oof_targets[val_idx] = y_val

        # Evaluasi Metrik Out-Of-Fold (Bebas Leakage)
        auc_score = roc_auc_score(oof_targets, oof_predictions)
        brier = brier_score_loss(oof_targets, oof_predictions)
        loss = log_loss(oof_targets, oof_predictions)

        self.metrics_ = {
            "OOF_ROC_AUC": float(auc_score),
            "OOF_Brier_Score": float(brier),
            "OOF_Log_Loss": float(loss),
        }
        logger.info("Metrik OOF Tervalidasi: %s", self.metrics_)

        # Melatih Final Pipeline Produksi di seluruh dataset menggunakan Kalibrasi Probabilitas
        full_preprocessor = self._build_feature_pipeline()
        core_estimator = HistGradientBoostingClassifier(
            random_state=self.config.random_state,
            class_weight="balanced",
            max_iter=100,
        )

        raw_final_pipeline = Pipeline(
            steps=[
                ("preprocessor", full_preprocessor),
                ("classifier", core_estimator),
            ]
        )

        logger.info("Melakukan fitting model akhir dan kalibrasi probabilitas...")
        # CalibratedClassifierCV dengan cv='prefit' tidak mungkin langsung dengan pipeline,
        # gunakan cv=3 pada instance final untuk memastikan kalibrasi sigmoid optimal.
        calibrated_model = CalibratedClassifierCV(
            estimator=raw_final_pipeline,
            method="isotonic",
            cv=3,
        )
        
        calibrated_model.fit(X, y)
        self.pipeline = calibrated_model
        
        return self.pipeline, self.metrics_

    def predict_risk(self, df_inference: pd.DataFrame) -> pd.DataFrame:
        """Inferensi aman pada data operasional masa depan."""
        if self.pipeline is None:
            raise RuntimeError("Pipeline belum dilatih. Panggil train_and_validate terlebih dahulu.")

        logger.info("Menjalankan inferensi pada %d rekaman...", len(df_inference))
        df_clean = df_inference.copy()
        
        # Dapatkan calibrated probability kelas 1 (misal: default/churn)
        probabilities = self.pipeline.predict_proba(df_clean)[:, 1]
        
        df_result = df_inference[[self.config.group_column]].copy()
        df_result["calibrated_probability"] = probabilities
        df_result["predicted_class"] = (probabilities >= 0.5).astype(int)
        
        return df_result


# ==========================================
# VERIFIKASI EKSEKUSI PIPELINE DENGAN DUMMY DATA
# ==========================================
if __name__ == "__main__":
    # Menghasilkan dataset simulasi enterprise yang mereplikasi pola churn nasabah
    np.random.seed(42)
    sample_size = 1200

    unique_customers = [f"CUST_{i:04d}" for i in range(300)]
    assigned_customers = np.random.choice(unique_customers, size=sample_size)

    mock_data = pd.DataFrame(
        {
            "customer_id": assigned_customers,
            "monthly_charges": np.random.exponential(scale=50.0, size=sample_size) + 10.0,
            "tenure_months": np.random.randint(1, 72, size=sample_size),
            "support_tickets": np.random.poisson(lam=1.5, size=sample_size),
            "contract_type": np.random.choice(["Month-to-Month", "One-Year", "Two-Year"], size=sample_size),
            "payment_method": np.random.choice(["Auto-Debit", "Credit Card", "Electronic Check"], size=sample_size),
        }
    )

    # Injeksi sinyal target realistis dengan noise
    latent_risk = (
        (mock_data["contract_type"] == "Month-to-Month").astype(int) * 1.5
        + (mock_data["monthly_charges"] > 70).astype(int) * 0.8
        + (mock_data["support_tickets"] * 0.4)
        - (mock_data["tenure_months"] * 0.05)
    )
    prob_churn = 1 / (1 + np.exp(-latent_risk))
    mock_data["churn"] = (prob_churn > np.random.uniform(0, 1, size=sample_size)).astype(int)

    # Konfigurasi skema
    cfg = PipelineConfig(
        target_column="churn",
        group_column="customer_id",
        numeric_features=["monthly_charges", "tenure_months", "support_tickets"],
        categorical_features=["contract_type", "payment_method"],
        smoothing_weight=15.0,
    )

    # Eksekusi pipeline
    engine = LeakageFreePredictiveEngine(config=cfg)
    trained_model, metrics = engine.train_and_validate(mock_data)

    print("\n--- HASIL VALIDASI METRIK BEBAS LEAKAGE ---")
    for metric_name, val in metrics.items():
        print(f"{metric_name}: {val:.4f}")

    # Simulasi data unlabelled baru (Masa Depan)
    unseen_data = pd.DataFrame(
        {
            "customer_id": ["CUST_9991", "CUST_9992"],
            "monthly_charges": [115.5, 22.0],
            "tenure_months": [2, 48],
            "support_tickets": [4, 0],
            "contract_type": ["Month-to-Month", "Two-Year"],
            "payment_method": ["Electronic Check", "Auto-Debit"],
        }
    )

    predictions = engine.predict_risk(unseen_data)
    print("\n--- HASIL INFERENSI RISIKO PREDIKTIF ---")
    print(predictions)
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah titik kegagalan (*failure modes*) paling destruktif pada pipeline analitik prediktif dan arsitektur pemulihannya (*recovery path*):

| Failure Mode | Mekanisme Penyebab | Dampak pada Sistem | Strategi Mitigasi / Fallback |
| :--- | :--- | :--- | :--- |
| **Unseen Categorical Value** | Munculnya kategori baru pada fase inferensi (contoh: metode pembayaran baru `'QRIS_INSTANT'`). | Transformer gagal, melempar exception `KeyError` atau menghasilkan nilai `NaN` secara masif. | Gunakan isolasi *smoothing fallback* di dalam `BayesianTargetEncoder` yang secara otomatis mengalokasikan `global_mean_` jika kunci tidak ditemukan. |
| **Zero Variance / Constant Feature** | Suatu fitur numerik memiliki nilai seragam pada set latih (akibat filter SQL atau kegagalan sensor). | Pembagian nol ($x / 0$) saat eksekusi scaling, merusak pembobotan algoritma numerik. | Terapkan pengecekan `VarianceThreshold` sebelum scikit-learn scaler atau tambahkan nilai epsilon ($\epsilon = 1e-8$) pada pembagi standar deviasi. |
| **Extreme Group Correlation** | Transaksi berulang dari satu pelanggan bervolume tinggi (*whale account*) mendominasi validasi. | Estimasi metrik terlalu optimis karena model hanya mengenali pola transaksi entitas dominan tersebut. | Wajib menggunakan `StratifiedGroupKFold` dengan mengikat kolom entitas (`customer_id`, `merchant_id`) sebagai grup partisi. |
| **Probability Polarization** | Model boosting menghasilkan nilai ekstrem ($0.0001$ dan $0.9999$) yang tidak terdistribusi secara linier. | Penentuan *cutoff* ambang batas intervensi bisnis menjadi kacau; ROI intervensi runtuh. | Kalibrasi probabilitas pasca-pelatihan dengan `CalibratedClassifierCV(method='isotonic' | 'sigmoid')`. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur pemodelan dalam analitik prediktif menuntut kompromi antara interpretabilitas, kapasitas model, dan latensi komputasi:

```
                            Interpretabilitas Tinggi
                                       ^
                                       |   [Logistic Regression + WoE]
                                       |
                                       |          [HistGradientBoosting]
                                       |
Kompleksitas Rendah <------------------+------------------> Kompleksitas Tinggi
                                       |
                                       |   [XGBoost / LightGBM + Optuna]
                                       |
                                       v
                           Akurasi Prediktif Tertinggi
```

#### Matriks Keputusan: Pilihan Arsitektur Algoritma

| Pendekatan Algoritmik | Keunggulan Enterprise | Kelemahan Utama | Kasus Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Logistic Regression + Weight of Evidence (WoE)** | Kepatuhan regulasi 100% (*explainability* mutlak via scorecard); komputasi inferensi dalam mikrodetik. | Tidak mampu menangkap hubungan non-linier kompleks dan interaksi tingkat tinggi tanpa manual rekayasa. | Regulasi ketat perbankan, *Credit Scoring*, Analisis Risiko Underwriting. |
| **HistGradientBoosting / LightGBM** | Menangani missing value secara internal (*native support*), tangguh terhadap non-linearitas, performa diskriminasi sangat tinggi. | Rawan overfit pada sample kecil; probabilitas mentah (*raw scores*) cenderung tidak terkalibrasi dengan baik. | *Customer Churn*, Fraud Detection, Propensity to Buy, LTV Prediction. |
| **Random Forest Classifier** | Sangat stabil (*low variance*); nyaris bebas dari tuning hiperparameter; tahan outlier. | Ukuran artefak model (*serialized file size*) masif (gigabytes); latensi inferensi lambat pada throughput tinggi. | Analisis risiko inventaris, Baseline Model eksploratif untuk Analyst. |

---

### 9. Best Practices & Standard Industri

1.  **Immutability of the Split**: Jangan pernah memanipulasi, menyaring, mengimputasi, atau menyeimbangkan (*SMOTE/undersampling*) dataset **sebelum** pembagian split dilakukan. Splitting adalah operasi baris pertama dalam arsitektur analitik.
2.  **Explicit Feature Dtypes Enforcement**: Pastikan skema data dikunci menggunakan *typing* ketat atau *dataclass* sebelum dialirkan ke dalam pipeline untuk mencegah perubahan implisit (contoh: ZIP code yang terbaca sebagai integer alih-alih kategori string).
3.  **Cross-Validation Matching Serving Reality**: 
    *   Jika sistem melayani data masa depan secara real-time $\rightarrow$ Gunakan **TimeSeriesSplit**.
    *   Jika sistem memprediksi entitas yang belum pernah dilihat sebelumnya $\rightarrow$ Gunakan **GroupKFold**.
    *   Jika dataset memiliki rasio positif < 5% $\rightarrow$ Wajib gunakan **StratifiedKFold** berpasangan dengan metrik evaluasi **PR-AUC (Average Precision)**, bukan ROC-AUC.
4.  **Artifact Versioning**: Selalu ekspor pipeline lengkap—bukan hanya bobot model—menggunakan `joblib` dengan menyertakan metadata komit Git, stempel waktu, dan metrik validasi OOF:
    ```python
    import joblib

    artifact = {
        "pipeline": engine.pipeline,
        "metadata": {
            "validation_metrics": engine.metrics_,
            "git_commit": "e8f3a1c",
            "schema_version": "1.0.0"
        }
    }
    joblib.dump(artifact, "churn_pipeline_v1.joblib")
    ```

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Senior Analyst di sebuah institusi FinTech P2P Lending. Tim Operasional menghadapi lonjakan gagal bayar pinjaman (*default rate*). Tugas Anda adalah membangun pipeline prediktif yang menghitung probabilitas gagal bayar peminjam baru dengan batasan:
1. Peminjam yang sama dapat meminjam lebih dari sekali (rawan *Group Leakage*).
2. Terdapat missing value pada data pendapatan peminjam.
3. Model harus menghasilkan probabilitas terkalibrasi agar Tim Penagihan (*Collection*) dapat menetapkan batas intervensi efisien.

#### Langkah Pelaksanaan

*   **Langkah 1: Setup Environment**
    ```bash
    pip install numpy pandas scikit-learn joblib
    ```

*   **Langkah 2: Pembuatan Skrip Eksperimen (`lab_credit_scoring.py`)**
    Salin dan sesuaikan modul `predictive_pipeline.py` dari Section 6 di lingkungan kerja lokal Anda. Ubah konfigurasi kolom:
    ```python
    cfg = PipelineConfig(
        target_column="is_default",
        group_column="borrower_id",
        numeric_features=["loan_amount", "annual_income", "debt_to_income_ratio"],
        categorical_features=["loan_purpose", "home_ownership"],
        smoothing_weight=20.0,
        n_splits=5
    )
    ```

*   **Langkah 3: Audit Bukti Adanya Leakage**
    Lakukan eksperimen perbandingan:
    1.  Jalankan `StandardScaler` dan `TargetEncoder` secara global di seluruh dataset sebelum splitting. Catat skor ROC-AUC pada Cross-Validation (Model A).
    2.  Jalankan arsitektur pipeline modular bebas leakage yang berada di Section 6 (Model B).
    3.  Amati penurunan metrik (misal: AUC turun dari 0.98 di Model A ke 0.81 di Model B). Tuliskan laporan diagnostik singkat mengapa skor Model A merupakan *ilusi kebocoran*.

*   **Langkah 4: Validasi Kalibrasi Probabilitas**
    Tambahkan kode visualisasi berikut untuk memeriksa kurva kalibrasi:
    ```python
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    prob_true, prob_pred = calibration_curve(
        y_true=oof_targets, 
        y_prob=oof_predictions, 
        n_bins=10, 
        strategy="quantile"
    )

    plt.figure(figsize=(8, 6))
    plt.plot(prob_pred, prob_true, marker="o", label="Model Calibration")
    plt.plot([0, 1], [0, 1], linestyle="--", label="Perfect Calibration")
    plt.xlabel("Mean Predicted Probability")
    plt.ylabel("Fraction of Positives")
    plt.title("Reliability Diagram (Calibration Curve)")
    plt.legend()
    plt.grid(True)
    plt.savefig("calibration_curve.png")
    logger.info("Reliability diagram disimpan ke calibration_curve.png")
    ```

*   **Langkah 5: Acceptance Criteria Evaluasi**
    Pipeline Anda dinyatakan lolos standar produksi jika:
    1. Tidak ada pergeseran entitas (`borrower_id`) yang beririsan antara Train dan Validation set di setiap fold (`len(set(train_groups).intersection(set(val_groups))) == 0`).
    2. Brier Score model di bawah **0.15**.
    3. Seluruh inferensi data pengujian baru berhasil dieksekusi tanpa eror *missing category* menggunakan fallback rata-rata global bayesian.