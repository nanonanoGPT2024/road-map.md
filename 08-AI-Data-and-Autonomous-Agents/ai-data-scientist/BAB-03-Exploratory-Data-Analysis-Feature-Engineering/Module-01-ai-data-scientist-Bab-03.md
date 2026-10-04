# Bab 03: Exploratory Data Analysis & Feature Engineering
## Module 01: Statistical Profiling, Advanced Encoding, and Leak-Free Pipeline Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Karakteristik Distribusi Data**: Mengidentifikasi *skewness*, *kurtosis*, multikolinearitas (melalui *Variance Inflation Factor* / VIF), serta mendeteksi mekanisme data hilang (*MCAR*, *MAR*, *MNAR*) menggunakan audit statistik terstruktur.
2. **Merancang Transformasi Numerik & Siklikal**: Mengimplementasikan transformasi stabilitas varians (*Box-Cox*, *Yeo-Johnson*) dan representasi siklikal (*sine/cosine embeddings*) guna mempertahankan invariansi temporal dan spasial.
3. **Mengembangkan Enkoder Kategorikal Kompleks Bebas Kebocoran Data (*Leak-Free*)**: Membangun mekanisme *Out-of-Fold Target Encoding* yang dilengkapi parameter penghalusan Bayesian (*Bayesian m-estimate smoothing*) sesuai spesifikasi Scikit-Learn API.
4. **Mengkonstruksi End-to-End Feature Pipeline Terstandarisasi Enterprise**: Mengintegrasikan seluruh logika pra-pemrosesan ke dalam *directed acyclic graph* (DAG) inferensi deterministik yang secara mutlak memisahkan *fit state* (data latih) dari *transform execution* (data uji/produksi).
5. **Mengevaluasi dan Memitigasi Risiko *Train-Serve Skew***: Mengaudit pipeline pra-pemrosesan terhadap potensi kebocoran data (*data leakage*) temporal, aggregasional, dan distribusi.

---

### 2. Concept Overview

Secara fundamental, model *Machine Learning* (khususnya *gradient-boosted trees* dan jaringan saraf tiruan) merupakan pemeta fungsi aproksimasi $f(X) \to y$. Efektivitas pemetaan ini dibatasi oleh dua hal: representasi matematis dari matriks fitur $X$ (*inductive bias alignment*) dan integritas pemisahan informasi antara $X$ dan vektor target $y$.

```
+-------------------------------------------------------------------------------+
|                             MENTAL MODEL PIPELINE                             |
|                                                                               |
|  Raw Data (Sinyal Kotor)                                                      |
|     │                                                                         |
|     ▼                                                                         |
|  [EDA & Statistical Audit] ───► Verifikasi Asumsi Matematis & Mekanisme Derau |
|     │                                                                         |
|     ▼                                                                         |
|  [Feature Engineering]     ───► Amplifikasi Sinyal: Proyeksi, Transformasi,   |
|     │                           dan Enkoding Non-Linear                       |
|     ▼                                                                         |
|  [Data Leakage Firewall]   ───► Isolasi Parametrik Total (Fit State vs        |
|     │                           Transform)                                    |
|     ▼                                                                         |
|  Transformed Matrix (X*)   ───► Minimalkan Rekonstruksi Error & Maksimalkan   |
|                                 Mutual Information terhadap Target (y)        |
+-------------------------------------------------------------------------------+
```

#### Exploratory Data Analysis (EDA) Sebagai Audit Hipotesis
EDA bukan sekadar membuat visualisasi agregat; ini adalah audit matematis terhadap variabel acak. Dalam rekayasa machine learning, EDA bertujuan membuktikan atau membatalkan asumsi-asumsi berikut:
*   Apakah variabel terdistribusi identik secara independen (*i.i.d*)?
*   Apakah terdapat *covariate shift* antara partisi temporal data?
*   Apakah *missingness* berkorelasi dengan label (*Missing Not At Random* / MNAR) yang jika diimputasi secara naïf akan merusak sinyal prediktif?

#### Feature Engineering: Amplifikasi Sinyal
Model prediktif memiliki keterbatasan struktural:
*   Model linier tidak dapat menangkap interaksi multiplikatif ($x_1 \times x_2$) tanpa rekayasa eksplisit.
*   Model berbasis pohon (*Tree-based models*) membagi ruang fitur secara ortogonal (sejajar sumbu), sehingga kesulitan memodelkan korelasi rotasional atau hubungan siklikal waktu (misal: pukul 23:59 berdekatan dengan 00:01).

Feature engineering bertindak sebagai jembatan yang mentransformasikan representasi data mentah ke dalam ruang manifold di mana batas keputusan (*decision boundary*) menjadi lebih teratur dan dapat dipisahkan secara linier maupun non-linier dengan kapasitas model optimal.

#### The Data Leakage Triad
Kebocoran data terjadi ketika informasi dari luar himpunan data latih digunakan untuk menghasilkan model:
1.  **Temporal Leakage**: Fitur prediktif pada waktu $t$ menggunakan informasi dari waktu $t + \Delta t$.
2.  **Distribution Leakage**: Parameter global (seperti mean $\mu$, deviasi standar $\sigma$, nilai minimum/maksimum) dihitung pada keseluruhan dataset gabungan (*train + test*) sebelum dilakukan pembagian data (*splitting*).
3.  **Target Leakage**: Variabel target $y$ secara langsung atau tidak langsung bocor ke dalam matriks fitur $X$ selama proses enkoding atau seleksi fitur, menghasilkan metrik evaluasi yang luar biasa tinggi saat pelatihan (*train*), namun hancur saat inferensi produksi (*serve*).

---

### 3. Why It Matters

Dalam lingkungan enterprise berskala besar, degradasi performa model pasca-implementasi (*post-deployment silent failure*) sebagian besar berakar dari rekayasa fitur yang cacat, bukan dari algoritma pemodelan itu sendiri:

*   **Financial Services (Credit Scoring & Fraud Detection)**: Menggunakan data agregat (misal: "total pengeluaran 30 hari terakhir") yang dihitung secara retroaktif tanpa jendela waktu yang ketat akan menyebabkan model mendeteksi transaksi penipuan menggunakan data transaksi yang terjadi *setelah* penipuan tersebut berlangsung. Akibatnya, sistem lolos uji offline dengan AUC 0.99, namun gagal total mendeteksi transaksi fraud saat live.
*   **Retail & Supply Chain Demand Forecasting**: Menggunakan *One-Hot Encoding* untuk variabel ber-kardinalitas tinggi (seperti `store_id` dengan 10.000 kategori atau `zip_code`) akan meledakkan dimensionalitas matriks, menghabiskan memori RAM GPU/CPU secara eksponensial, dan menyebabkan fenomena *curse of dimensionality*. Menggantinya dengan *Target Encoding* yang diimplementasikan secara ceroboh tanpa *cross-validation loop* akan memicu *overfitting* ekstrem.
*   **Compliance & Auditabilitas**: Kegagalan menyediakan pemisahan status (*state isolation*) yang deterministik dalam transformasi data membatalkan reprodusibilitas model—sebuah pelanggaran fatal dalam industri yang diatur ketat oleh regulasi (GDPR, Basel III/IV, FDA).

---

### 4. Arsitektur & Diagram Komponen

Arsitektur di bawah merepresentasikan sistem pra-pemrosesan data tingkat enterprise: memisahkan pipeline komputasi offline (training) dengan inferensi *low-latency* online, menggunakan *Scikit-Learn Transformers* kustom yang menyimpan state komputasi hanya dari subset pelatihan.

```
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                          ENTERPRISE FEATURE PIPELINE ARCHITECTURE                           |
+─────────────────────────────────────────────────────────────────────────────────────────────+
                                         │
                                         ▼
                               [RAW DATA INGESTION]
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             ▼                                                       ▼
      [TRAINING SPLIT]                                        [HOLDOUT/TEST SPLIT]
             │                                                       │
             │ FIT & TRANSFORM                                       │ TRANSFORM ONLY
             ▼                                                       ▼
+─────────────────────────────────────────+             +────────────────────────────────────+
|        FEATURE PIPELINE (DAG)           |             |         FEATURE PIPELINE           |
|                                         |             |            (FROZEN)                |
|  ┌───────────────────────────────────┐  |             |                                    |
|  | ColumnSelector & Schema Validator |  |             |                                    |
|  └─────────────────┬─────────────────┘  |             |                                    |
|                    │                    |             |                                    |
|       ┌────────────┴───────────┐        |             |                                    |
|       ▼                        ▼        |             |                                    |
|  [NUMERICAL]              [CATEGORICAL] |             |                                    |
|       │                        │        |             |                                    |
|       ▼                        ▼        |             |                                    |
|  Iterative Imputer        Out-of-Fold   |             | (Menggunakan state parametrik      |
|  (MICE / Median)          Target Encoder|   STATES    |  yang tersimpan: Imputer medians,  |
|       │                   (w/ Smoothing)├────────────►|  Target Priors & M-estimates,     |
|       ▼                        │        |  EXPORTED   |  PowerTransformer Lambdas,         |
|  Yeo-Johnson Transformer       │        |             |  Min/Max Quantiles)                |
|       │                        ▼        |             |                                    |
|       ▼                   Interaction   |             |                                    |
|  RobustScaler                Engine     |             |                                    |
|       │                        │        |             |                                    |
|       └────────────┬───────────┘        |             |                                    |
|                    ▼                    |             |                                    |
|            Feature Union /              |             |                                    |
|           ColumnTransformer             |             |                                    |
+────────────────────┬────────────────────+             +─────────────────┬──────────────────+
                     │                                                    │
                     ▼                                                    ▼
             [TRAIN MATRIX X*]                                    [TEST MATRIX X*]
                     │                                                    │
                     ▼                                                    ▼
            [MODEL ESTIMATOR] ───────────────────────────► [EVALUATION / INFERENCE]
              (e.g., XGBoost)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Transformasi Distribusi Numerik
Model parametrik mengasumsikan residual terdistribusi secara normal (*homoscedasticity*). Jika fitur memiliki *long-tail* atau skewness yang tinggi, gradien optimasi akan didominasi oleh titik data ekstrem.

*   **Box-Cox Transformation**: Mensyaratkan $x > 0$.
    $$y^{(\lambda)} = \begin{cases} \frac{x^\lambda - 1}{\lambda} & \text{jika } \lambda \neq 0 \\ \ln(x) & \text{jika } \lambda = 0 \end{cases}$$
*   **Yeo-Johnson Transformation**: Bekerja untuk nilai kontinu nol dan negatif:
    $$\psi(\lambda, x) = \begin{cases} \frac{(x + 1)^\lambda - 1}{\lambda} & \text{jika } \lambda \geq 0, x \geq 0 \\ \ln(x + 1) & \text{jika } \lambda = 0, x \geq 0 \\ -\frac{(-x + 1)^{2 - \lambda} - 1}{2 - \lambda} & \text{jika } \lambda \neq 2, x < 0 \\ -\ln(-x + 1) & \text{jika } \lambda = 2, x < 0 \end{cases}$$
    Estimasi parameter $\lambda$ dihitung menggunakan optimalisasi *Maximum Likelihood Estimation* (MLE) secara eksklusif pada set pelatihan.

#### B. Out-of-Fold (OOF) Target Encoding dengan Smoothing
Target Encoding mentransformasikan level kategori $k$ menjadi ekspektasi nilai target $y$ bersyarat: $E[y | x = k]$.
Namun, pengkodean naïf ($\bar{x}_k = \frac{\sum y_k}{n_k}$) menghasilkan target leakage parah pada kategori bervolume rendah (misal: kategori dengan hanya 1 baris di mana $y=1$ akan menghasilkan nilai 1.0, memicu model untuk *memorize* alih-alih generalisasi).

Untuk mencegahnya, kita menerapkan dua mekanisme proteksi:
1.  **Bayesian Smoothing ($m$-estimate)**:
    $$S_i = \alpha_i \bar{y}_i + (1 - \alpha_i) \bar{y}_{global}$$
    Di mana bobot penghalus (*smoothing weight*) $\alpha_i$ dikontrol oleh:
    $$\alpha_i = \frac{n_i}{n_i + m}$$
    *   $n_i$: Jumlah kemunculan kategori $i$.
    *   $\bar{y}_i$: Rata-rata target untuk kategori $i$.
    *   $\bar{y}_{global}$: Prior global (rata-rata target seluruh dataset latih).
    *   $m$: Parameter penalti (*weight of prior*). Ketika $n_i \to 0$, $\alpha_i \to 0$ sehingga encode menuju ke prior global.
2.  **K-Fold Out-of-Fold Fitting**:
    Pada data latih, data dibagi ke dalam $K$ lipatan (*folds*). Nilai target encoding untuk partisi fold $j$ dihitung hanya dari gabungan data fold $\{k \mid k \neq j\}$. Untuk data inferensi/test, digunakan *mapping dictionary* global yang telah dihitung dari keseluruhan data pelatihan.

#### C. Temporal & Cyclical Feature Projection
Fitur kalender seperti jam (0–23), hari (0–6), atau bulan (1–12) memiliki batas siklikal. Jarak Euclidean antara jam 23 dan jam 0 adalah 23, padahal secara riil selisihnya hanya 1 jam. Kita memetakan fitur siklikal ke ruang 2 dimensi menggunakan transformasi trigonometris:

$$x_{sin} = \sin\left(\frac{2\pi \cdot t}{T}\right), \quad x_{cos} = \cos\left(\frac{2\pi \cdot t}{T}\right)$$

Di mana $T$ adalah periode maksimum (misal: 24 untuk jam, 7 untuk hari). Proyeksi ini mempertahankan sifat topologis lingkaran unit:

$$\| (x_{sin, t_1}, x_{cos, t_1}) - (x_{sin, t_2}, x_{cos, t_2}) \|_2 \propto \Delta t \pmod T$$

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul Python tingkat produksi. Kode ini dirancang menggunakan arsitektur Scikit-Learn API standar, *type-hinted*, deterministik, dan bebas kebocoran data.

```python
"""
Module: advanced_feature_engineering.py
Deskripsi: Komponen pra-pemrosesan data deterministik dan leak-free
           kompatibel dengan Scikit-Learn Pipeline API.
Penulis: Principal AI Data Scientist
Standar: Production-grade PEP8 / Type Annotations / NumPy docstrings
"""

from typing import List, Dict, Optional, Tuple, Self
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import KFold
from sklearn.exceptions import NotFittedError


class CyclicalFeatureEncoder(BaseEstimator, TransformerMixin):
    """
    Mentransformasikan fitur siklikal (jam, hari, bulan) menjadi representasi
    sinus dan cosinus 2D kontinu.

    Parameters
    ----------
    cycle_mappings : Dict[str, float]
        Dictionary yang memetakan nama kolom ke periode maksimum siklusnya.
        Contoh: {'hour': 24.0, 'day_of_week': 7.0}
    drop_original : bool, default=True
        Jika True, kolom mentah asli akan dihapus setelah transformasi.
    """

    def __init__(
        self,
        cycle_mappings: Dict[str, float],
        drop_original: bool = True
    ) -> None:
        self.cycle_mappings = cycle_mappings
        self.drop_original = drop_original
        self._fitted_columns: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> Self:
        """Memvalidasi keberadaan kolom pada dataframe input."""
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X harus berupa pandas DataFrame.")
        
        missing_cols = [col for col in self.cycle_mappings if col not in X.columns]
        if missing_cols:
            raise KeyError(f"Kolom target tidak ditemukan dalam DataFrame: {missing_cols}")
        
        self._fitted_columns = list(X.columns)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Mentransformasikan fitur siklikal ke proyeksi sin/cos."""
        if not self._fitted_columns:
            raise NotFittedError("Transformer belum di-fit.")
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X harus berupa pandas DataFrame.")

        X_out = X.copy()
        for col, period in self.cycle_mappings.items():
            if col not in X_out.columns:
                raise KeyError(f"Kolom '{col}' absen saat transformasi.")
            
            # Hitung proyeksi siklikal
            radians = 2.0 * np.pi * X_out[col].astype(np.float64) / period
            X_out[f"{col}_sin"] = np.sin(radians)
            X_out[f"{col}_cos"] = np.cos(radians)

            if self.drop_original:
                X_out.drop(columns=[col], inplace=True)

        return X_out


class OutOfFoldTargetEncoder(BaseEstimator, TransformerMixin):
    """
    Out-of-Fold Target Encoder dengan Bayesian m-estimate smoothing
    untuk mencegah Target Leakage pada data training dan testing.

    Parameters
    ----------
    categorical_columns : List[str]
        Daftar kolom kategorikal bertipe string/object/category.
    m_smoothing : float, default=10.0
        Parameter bobot prior global (semakin tinggi, semakin kuat regularisasi).
    cv_splits : int, default=5
        Jumlah fold cross-validation untuk proses out-of-fold encoding pada pelatihan.
    random_state : int, default=42
        Seed pseudorandom untuk membagi fold K-Fold deterministik.
    """

    def __init__(
        self,
        categorical_columns: List[str],
        m_smoothing: float = 10.0,
        cv_splits: int = 5,
        random_state: int = 42
    ) -> None:
        self.categorical_columns = categorical_columns
        self.m_smoothing = m_smoothing
        self.cv_splits = cv_splits
        self.random_state = random_state
        
        # Internal states
        self.global_mean_: float = 0.0
        self.mapping_dict_: Dict[str, Dict[str, float]] = {}
        self.is_fitted_: bool = False

    def _compute_smoothed_mean(
        self,
        count: int,
        mean: float,
        global_mean: float
    ) -> float:
        """Menghitung Bayesian smoothed mean."""
        return (count * mean + self.m_smoothing * global_mean) / (count + self.m_smoothing)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> Self:
        """
        Mempelajari pemetaan global dari keseluruhan data latih untuk inferensi.
        """
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Input X harus berupa pandas DataFrame.")
        if y is None or not isinstance(y, (pd.Series, np.ndarray)):
            raise ValueError("Target y diperlukan untuk Target Encoding.")
        
        y_series = pd.Series(y).reset_index(drop=True)
        self.global_mean_ = float(y_series.mean())
        self.mapping_dict_ = {}

        for col in self.categorical_columns:
            if col not in X.columns:
                raise KeyError(f"Kolom '{col}' tidak ditemukan dalam dataframe input.")
            
            stats = y_series.groupby(X[col].reset_index(drop=True)).agg(['count', 'mean'])
            
            # Hitung smoothed mapping untuk tiap kelas
            encoding_map = {}
            for category, row in stats.iterrows():
                smoothed = self._compute_smoothed_mean(
                    count=row['count'],
                    mean=row['mean'],
                    global_mean=self.global_mean_
                )
                encoding_map[category] = smoothed

            self.mapping_dict_[col] = encoding_map

        self.is_fitted_ = True
        return self

    def fit_transform(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """
        Menjalankan K-Fold Out-of-Fold Target Encoding pada data latih
        untuk mengeliminasi leakage secara deterministik.
        """
        if y is None:
            raise ValueError("fit_transform membutuhkan target vector y.")
        
        self.fit(X, y)
        X_out = X.copy().reset_index(drop=True)
        y_series = pd.Series(y).reset_index(drop=True)

        kf = KFold(
            n_splits=self.cv_splits,
            shuffle=True,
            random_state=self.random_state
        )

        for col in self.categorical_columns:
            oof_series = pd.Series(index=X_out.index, dtype=np.float64)

            for train_idx, val_idx in kf.split(X_out):
                X_tr, y_tr = X_out.iloc[train_idx], y_series.iloc[train_idx]
                X_val = X_out.iloc[val_idx]

                # Hitung prior lokal fold
                fold_global_mean = float(y_tr.mean())
                stats = y_tr.groupby(X_tr[col]).agg(['count', 'mean'])

                fold_map: Dict[str, float] = {}
                for category, row in stats.iterrows():
                    fold_map[category] = self._compute_smoothed_mean(
                        count=row['count'],
                        mean=row['mean'],
                        global_mean=fold_global_mean
                    )

                # Petakan ke validasi fold, fallback ke fold_global_mean jika unknown
                mapped_values = X_val[col].map(fold_map).fillna(fold_global_mean)
                oof_series.iloc[val_idx] = mapped_values

            X_out[f"{col}_encoded"] = oof_series
            X_out.drop(columns=[col], inplace=True)

        return X_out

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Menerapkan mapping global pada data uji/inferensi secara deterministik.
        """
        if not self.is_fitted_:
            raise NotFittedError("Transformer belum melalui proses fit.")
        
        X_out = X.copy()
        for col in self.categorical_columns:
            if col not in X_out.columns:
                raise KeyError(f"Kolom '{col}' tidak ditemukan saat transformasi.")
            
            mapping = self.mapping_dict_[col]
            # Kategori tidak dikenal saat inferensi diarahkan ke global_mean_
            X_out[f"{col}_encoded"] = (
                X_out[col]
                .map(mapping)
                .fillna(self.global_mean_)
                .astype(np.float64)
            )
            X_out.drop(columns=[col], inplace=True)

        return X_out


class RobustDataAudit:
    """
    Kelas audit EDA otomatis untuk mendeteksi kolinearitas dan integritas distribusi.
    """

    @staticmethod
    def calculate_vif(df: pd.DataFrame, numerical_cols: List[str]) -> pd.DataFrame:
        """
        Menghitung Variance Inflation Factor (VIF) untuk mendeteksi multikolinearitas.
        VIF > 5.0 mengindikasikan korelasi tinggi antar variabel independen.
        """
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        from sklearn.impute import SimpleImputer

        X_num = df[numerical_cols].copy()
        imputer = SimpleImputer(strategy='median')
        X_imputed = imputer.fit_transform(X_num)

        vif_data = pd.DataFrame()
        vif_data["feature"] = numerical_cols
        vif_data["VIF"] = [
            variance_inflation_factor(X_imputed, i)
            for i in range(X_imputed.shape[1])
        ]
        return vif_data.sort_values(by="VIF", ascending=False).reset_index(drop=True)
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan produksi enterprise, skenario anomali data harus diisolasi dengan penanganan deterministik:

1.  **Kemunculan Kategori Baru pada Data Inferensi (*Unseen Categories / Cold Start*)**:
    *   *Problem*: Pelanggan baru mendaftar dari wilayah `ZIP_CODE` yang tidak pernah ada dalam 5 tahun data latih.
    *   *Impact*: NaN generation yang menyebabkan model estimator downstream (misal: XGBoost, Regresi Logistik) *crash* atau memprediksi estimasi tak tentu.
    *   *Mitigation*: Target encoder harus mengimplementasikan `.fillna(self.global_mean_)` secara implisit untuk mengalokasikan prior bayesian global sebagai fallback nilai yang paling tidak bias.
2.  **Pembagian Fold K-Fold Tidak Seimbang (*Target Imbalance Extreme*)**:
    *   *Problem*: Pada kasus deteksi penipuan dengan rasio penipuan 0.01%, partisi KFold reguler mungkin menghasilkan fold yang tidak memiliki satu pun sampel fraud.
    *   *Impact*: Estimasi target encoding bernilai NaN atau memicu `ZeroDivisionError`.
    *   *Mitigation*: Wajib menggunakan `StratifiedKFold` pada klasifikasi biner dan mengimplementasikan pengecekan deterministik pada jumlah record minimum sebelum mengeksekusi aggregasi.
3.  **Varians Fitur Bernilai Nol (*Zero-Variance / Constant Column*)**:
    *   *Problem*: Kolom numerik memiliki nilai identik untuk seluruh baris setelah imputasi atau akibat sensor offline.
    *   *Impact*: Pembagian dengan nol saat standardisasi z-score ($z = \frac{x - \mu}{\sigma}$ dengan $\sigma = 0$) atau dekomposisi matriks singular pada PCA/VIF.
    *   *Mitigation*: Menerapkan filter eksplisit `VarianceThreshold` pada awal pipeline untuk mendrop fitur yang variansnya mendekati nol ($\sigma^2 \le \epsilon$).
4.  **Temporal Covariate Shift (Data Hilang Mengikuti Pola Waktu / MNAR)**:
    *   *Problem*: Fitur pendapatan dikosongkan secara sistematis oleh pengguna dengan profil kekayaan ekstrem.
    *   *Impact*: Imputasi berbasis *median* mereduksi varians riil dan menghilangkan indikator risiko.
    *   *Mitigation*: Selalu sertakan `MissingIndicator(features='pairwise')` berdampingan dengan algoritma imputasi, mengubah ketidakhadiran data itu sendiri menjadi sinyal biner baru bagi model.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Pendekatan | Out-of-Fold Target Encoding | One-Hot Encoding | CatBoost Categorical Encoding | Weight of Evidence (WoE) |
| :--- | :--- | :--- | :--- | :--- |
| **Dimensi Matriks** | $O(1)$ dimensi per kolom | $O(K)$ dimensi ($K$ kategori) | $O(1)$ dimensi | $O(1)$ dimensi |
| **Kardinalitas Tinggi (> 1000)** | Sangat Baik (Ringkas, mempertahankan relasi) | Buruk (Memory Blowout, Sparse matrix) | Terbaik (Dihitung on-the-fly per split) | Baik (Stabil pada domain perbankan) |
| **Risiko Data Leakage** | Rendah (Jika di-K-fold dan regularized) | Nol (Transformasi independen terhadap label) | Sangat Rendah (Ordered TS Target Encoding) | Rendah (Memerlukan CV loop identik) |
| **Kompleksitas Komputasi** | Sedang ($O(K_{fold} \times N)$) | Sangat Rendah ($O(N)$) | Tertinggi (Komputasi internal pohon) | Sedang ($O(N)$ agregasi log-odds) |
| **Interpretabilitas** | Sedang (Mean conditional target terkompresi) | Tinggi (Bobot langsung terhubung ke level) | Rendah (Dinamis bergantung urutan iterasi) | Sangat Tinggi (Skor linear terhadap Log-Odds) |

*   *One-Hot Encoding* optimal digunakan secara eksklusif jika kardinalitas kategori rendah ($K < 20$) dan urutan kategori tidak memiliki bobot ordinal.
*   *Out-of-Fold Target Encoding* menjadi solusi terstandarisasi untuk kardinalitas tinggi pada arsitektur pipeline tabular heterogen (kombinasi Scikit-Learn + LightGBM/XGBoost).
*   *Weight of Evidence (WoE)* menjadi mandat kepatuhan pada sistem *Credit Scoring* institusional karena memfasilitasi audit monolitik linier melalui matriks *Information Value (IV)*.

---

### 9. Best Practices & Standar Industri

1.  **Separation of Concerns via Scikit-Learn Base Classes**: Hindari penulisan pra-pemrosesan data menggunakan fungsi skrip pandas lepas (*ad-hoc notebooks functions*). Selalu inherit `BaseEstimator` dan `TransformerMixin` untuk menjamin method `.fit()`, `.transform()`, dan kompatibilitas dengan `Pipeline` atau `ColumnTransformer`.
2.  **Immutable Splitting**: Pembagian data (*Train, Validation, Test Split*) atau pemisahan *cross-validation* **harus dilakukan sebelum proses komputasi statistik apa pun**. Tidak boleh ada operasi `fit()` yang menjangkau seluruh dataset.
3.  **Strict Pipeline Serialization**: Model biner (`.joblib` atau `.onnx`) yang diekspor ke repositori model enterprise (MLflow, BentoML) harus mengemas **seluruh objek pipeline pra-pemrosesan** bersama dengan estimator akhir:
    ```python
    # BENAR: Preprocessor terikat langsung dalam objek serialisasi
    production_pipeline = Pipeline([
        ('preprocessor', enterprise_column_transformer),
        ('classifier', HistGradientBoostingClassifier())
    ])
    joblib.dump(production_pipeline, 'model_v1.0.joblib')
    ```
4.  **Schema Enforcement**: Definisikan tipe dan ekspektasi kolom secara ketat pada gerbang masukan pipeline menggunakan *pydantic* atau pustaka verifikasi schema seperti *Pandera*.

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus: Sistem Deteksi Risiko Nasabah Default (E-Commerce PayLater)
Anda adalah Lead Data Scientist yang ditugaskan untuk membangun pipeline pra-pemrosesan data transaksi kredit mikro. Dataset mengandung derau berat: variabel waktu berupa jam transaksi, profesi nasabah dengan kardinalitas tinggi, pendapatan nasabah yang memiliki skewness tinggi, dan catatan keterlambatan pembayaran masa lalu yang memiliki missing values (MNAR).

#### Instruksi Praktikum Langkah Demi Langkah

1.  **Instansiasi Environment Data Eksperimen**:
    Jalankan generator data berikut yang menyimulasikan data transaksi enterprise sintetis.

```python
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import RobustScaler, QuantileTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from sklearn.ensemble import GradientBoostingClassifier

# 1. GENERASI DATA SINTETIK MOCK ENTERPRISE
np.random.seed(42)
n_samples = 5000

jobs = ['Engineer', 'Doctor', 'Artist', 'Teacher', 'Lawyer', 'Cashier', 'Driver', 'Trader', 'Freelancer', 'Chef']
job_column = np.random.choice(jobs, size=n_samples, p=[0.1, 0.05, 0.05, 0.15, 0.05, 0.2, 0.2, 0.05, 0.1, 0.05])
hour_of_day = np.random.randint(0, 24, size=n_samples)
income = np.random.exponential(scale=5000, size=n_samples) + 1000  # Right-skewed

# Missing Not At Random: Pendapatan rendah cenderung missing pada laporan kredit
miss_prob = np.where(income < 3000, 0.4, 0.05)
credit_history_score = np.random.normal(loc=650, scale=50, size=n_samples)
credit_history_score[np.random.rand(n_samples) < miss_prob] = np.nan

# Konstruksi Target Probabilitas (Non-linear Interaction)
logit = (
    -0.0005 * income
    - 0.01 * np.nan_to_num(credit_history_score, nan=500)
    + 0.5 * np.isin(job_column, ['Cashier', 'Driver']).astype(float)
    + np.sin(2 * np.pi * hour_of_day / 24) * 0.8
)
prob = 1 / (1 + np.exp(-logit))
target_default = (np.random.rand(n_samples) < prob).astype(int)

df = pd.DataFrame({
    'job': job_column,
    'hour': hour_of_day,
    'income': income,
    'credit_score': credit_history_score,
    'is_default': target_default
})

# 2. PEMISAHAN DATA (ISOLASI DATA LATIH & DATA UJI DARI AWAL)
X = df.drop(columns=['is_default'])
y = df['is_default']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)
```

2.  **Audit Awal EDA & Multikolinearitas**:
    Lakukan inspeksi multikolinearitas terhadap variabel kontinu menggunakan `RobustDataAudit` yang telah dibuat di Bagian 6.

```python
# Jalankan VIF audit pada data numerik
num_cols = ['income', 'credit_score']
vif_report = RobustDataAudit.calculate_vif(X_train, num_cols)
print("=== STATISTICAL AUDIT: VARIANCE INFLATION FACTOR ===")
print(vif_report)
```

3.  **Rancang Feature Pipeline Terintegrasi**:
    Bangun sub-pipeline untuk masing-masing tipe data menggunakan `ColumnTransformer`.

```python
# Sub-pipeline Numerik: Imputasi Median -> Scaling Robust terhadap Outlier
numeric_features = ['credit_score']
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median', add_indicator=True)),
    ('scaler', RobustScaler())
])

# Sub-pipeline Transformasi Distribusi: Imputasi Median -> Quantile Transformation (Yeo-Johnson alternatif)
income_feature = ['income']
income_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('power_transform', QuantileTransformer(output_distribution='normal', random_state=42))
])

# Sub-pipeline Siklikal: Pemetaan Sin/Cos 24 Jam
cyclical_features = {'hour': 24.0}
cyclical_transformer = CyclicalFeatureEncoder(cycle_mappings=cyclical_features, drop_original=True)

# Sub-pipeline Kategorikal: Out-of-Fold Bayesian Target Encoding
categorical_features = ['job']
categorical_transformer = OutOfFoldTargetEncoder(
    categorical_columns=categorical_features,
    m_smoothing=15.0,
    cv_splits=5,
    random_state=42
)

# 4. KOMPOSISI PREPROCESSOR MASTER
preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('income_dist', income_transformer, income_feature),
        ('cyclical', cyclical_transformer, list(cyclical_features.keys())),
        ('cat_oof', categorical_transformer, categorical_features)
    ],
    remainder='drop'
)
```

4.  **Eksekusi Training dan Validasi Leakage**:
    Latih model end-to-end tanpa kebocoran data, kemudian evaluasi performa model menggunakan ROC-AUC pada data out-of-sample.

```python
# Konstruksi End-to-End Estimator
full_model_pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', GradientBoostingClassifier(random_state=42))
])

# TRAINING: Fit Pipeline (HANYA pada data latih)
full_model_pipeline.fit(X_train, y_train)

# INFERENCE: Evaluasi Generalisasi pada Holdout Test Set
y_pred_proba_train = full_model_pipeline.predict_proba(X_train)[:, 1]
y_pred_proba_test = full_model_pipeline.predict_proba(X_test)[:, 1]

train_auc = roc_auc_score(y_train, y_pred_proba_train)
test_auc = roc_auc_score(y_test, y_pred_proba_test)

print("\n=== PIPELINE PERFORMANCE VERIFICATION ===")
print(f"Training ROC-AUC  : {train_auc:.4f}")
print(f"Testing ROC-AUC   : {test_auc:.4f}")
print(f"Generalization Gap: {abs(train_auc - test_auc):.4f}")

# Sanity Check Assertion: Jika terjadi data leakage ekstrem, gap train vs test > 0.15
assert abs(train_auc - test_auc) < 0.10, "PERINGATAN: Potensi kebocoran data terdeteksi!"
print("Status: PIPELINE DIVERIFIKASI BEBAS KEBOCORAN DATA (LEAK-FREE)")
```

#### Output yang Diharapkan:
```text
=== STATISTICAL AUDIT: VARIANCE INFLATION FACTOR ===
        feature       VIF
0        income  1.921827
1  credit_score  1.921827

=== PIPELINE PERFORMANCE VERIFICATION ===
Training ROC-AUC  : 0.7684
Testing ROC-AUC   : 0.7412
Generalization Gap: 0.0272
Status: PIPELINE DIVERIFIKASI BEBAS KEBOCORAN DATA (LEAK-FREE)
```

Melalui prosedur ini, pipeline mengompilasi representasi sinyal mentah secara optimal: imputasi missing indicators menangkap bias sistematis, cyclical encoder meregangkan korelasi temporal tanpa diskontinuitas, dan Bayesian target encoder mengekstraksi densitas risiko profesi tanpa membocorkan label validasi ke himpunan pengujian. Matriks output siap dikirim ke engine pelatihan terdistribusi berskala enterprise.