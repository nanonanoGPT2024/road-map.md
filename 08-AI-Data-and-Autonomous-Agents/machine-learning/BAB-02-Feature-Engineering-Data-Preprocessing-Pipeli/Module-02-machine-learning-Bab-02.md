# Kurikulum Rekayasa Machine Learning Enterprise
## Kategori: 08-AI-Data-and-Autonomous-Agents
### BAB-02: Feature Engineering & Data Preprocessing Pipelines
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada tingkat Staff/Principal Machine Learning Engineer diharapkan mampu:

1. **Mendesain & Mengimplementasikan Advanced Feature Pipelines**: Merancang arsitektur pipeline transformasi fitur yang deterministik, bebas kebocoran data (*data leakage*), dan sepenuhnya kompatibel dengan ekosistem `scikit-learn` API menggunakan custom estimators.
2. **Menguasai Target Encoding Lanjutan**: Mengimplementasikan K-Fold out-of-fold target encoding dengan smoothing Bayesian dan additive noise untuk mencegah overfitting pada fitur ber-kardinalitas tinggi.
3. **Mengintegrasikan Dual-Storage Feature Store**: Merancang topologi Feature Store (offline untuk batch training, online untuk inference berlatensi ultra-rendah) menggunakan paradigma time-travel dan *point-in-time correctness*.
4. **Mendeteksi & Memitigasi Data Drift Secara Otomatis**: Membangun modul pemantauan distribusi data menggunakan uji statistik Kolmogorov-Smirnov (KS-test) dan Population Stability Index (PSI) di level pipeline produksi.
5. **Menjamin Reproducibilitas Artefak Data**: Menyusun strategi serialisasi, versioning, dan deployment pipeline fitur tanpa memicu skew antara fase pelatihan dan inferensi (*training-serving skew*).

---

## 2. Prerequisite

Peserta wajib menguasai kompetensi dasar berikut sebelum mempelajari modul ini:

* **Sistem Komputasi Data**: Pemahaman mendalam tentang *in-memory vectorization* menggunakan NumPy dan pemrosesan DataFrame berbasis chunking/lazy execution (Pandas, Polars).
* **Teori Statistika & Aljabar Linier**: Pemahaman distribusi probabilitas, teorema Bayes, dispersi data, matriks kovariansi, dan reduksi dimensi (SVD/PCA).
* **Software Engineering Patterns**: Penguasaan Object-Oriented Programming (OOP) tingkat lanjut pada Python, specifically `BaseEstimator` dan `TransformerMixin` contract, `dataclasses`, `typing`, dan penanganan serialisasi objek (`pickle`, `joblib`, `cloudpickle`).
* **Infrastruktur Data**: Pengenalan database OLAP (misal: BigQuery, Snowflake, ClickHouse) dan sistem penyimpanan NoSQL Key-Value dengan latensi mikrodetik (misal: Redis, DynamoDB).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Vektor Transformasi Data & Scikit-Learn Execution Graph

Di lingkungan enterprise, pemrosesan fitur tidak boleh dilakukan secara ad-hoc menggunakan skrip prosedural. Transformasi harus dimodelkan sebagai Directed Acyclic Graph (DAG) deterministik.

`sklearn.pipeline.Pipeline` bekerja dengan menyusun rantai eksekusi internal:
$$\text{Pipeline} = [T_1, T_2, \dots, T_{n-1}, E_n]$$
di mana $T_i$ merepresentasikan *Transformer* yang wajib mengimplementasikan method `fit(X, y)` dan `transform(X)`, sedangkan $E_n$ adalah *Estimator* terminal yang mengimplementasikan `fit(X, y)` dan `predict(X)`.

```
           fit(X_train, y_train) Pipeline Flow:
           
 [X_train] ───> [Transformer 1] ───(X_tr1)───> [Transformer 2] ───(X_tr2)───> [Estimator]
                      │                              │                             │
                  fit/calc                       fit/calc                      fit/train
                      │                              │                             │
                      ▼                              ▼                             ▼
                (Params: μ, σ)                (Params: Medians)             (Weights: W, b)

           transform(X_test) Pipeline Flow:

 [X_test]  ───> [Transformer 1] ───(X_te1)───> [Transformer 2] ───(X_te2)───> [Predictions]
                      │                              │
                    apply                          apply
                  (Fixed μ, σ)                 (Fixed Medians)
```

Pada fase `fit`, state internal (seperti nilai rata-rata $\mu$, deviasi standar $\sigma$, atau tabel probabilitas posterior) dihitung dan disimpan secara eksklusif dari data latih ($D_{train}$). Selama fase `transform`, state tersebut diterapkan secara strictly statis tanpa melakukan komputasi parameter baru. Pelanggaran terhadap pemisahan ini memicu fenomena **Data Leakage**.

### 3.2 Target Encoding Matematis & Regularisasi Bayesian

Target Encoding konvensional menggantikan kategori $k$ dari fitur kategorikal $x$ dengan rata-rata target:
$$\hat{S}_k = \frac{\sum_{i \in C_k} y_i}{n_k}$$
Di mana $C_k = \{i \mid x_i = k\}$ dan $n_k = |C_k|$.

Pendekatan naif ini rentan terhadap over-fitting ekstrem untuk kategori berfrekuensi rendah ($n_k$ kecil). Solusi matematis standar enterprise menggunakan **M-Estimate Empirical Bayes Smoothing**:
$$S_k^* = \lambda(n_k) \cdot \hat{S}_k + (1 - \lambda(n_k)) \cdot \bar{y}$$
di mana bobot smoothing $\lambda(n_k)$ didefinisikan secara logistik atau linier:
$$\lambda(n_k) = \frac{1}{1 + e^{-(n_k - m) / s}} \quad \text{atau} \quad \lambda(n_k) = \frac{n_k}{n_k + m}$$
Variabel $m$ adalah parameter bobot smoothing prior, dan $\bar{y}$ adalah global mean target di seluruh dataset pelatihan. 

Untuk memutus korelasi langsung antara fitur yang ditransformasi dan label pada baris yang sama, implementasi harus menggunakan partisi **Out-of-Fold (OOF)** berbasis $K$-Fold cross-validation split pada fase pelatihan.

### 3.3 Topologi Feature Store: Dual Storage Engine & Point-in-Time Joins

Feature Store modern memecahkan fragmentasi data fitur antara tim analitik data dan tim engineering aplikasi melalui dua storage engine:

1. **Offline Store (OLAP/Data Lake)**: Parquet, Delta Lake, Snowflake, atau BigQuery. Digunakan untuk menyimpan feature log historis yang tidak dimutasi (append-only), diakses untuk pelatihan model batch besar.
2. **Online Store (In-Memory Key-Value)**: Redis, AWS DynamoDB, atau Aerospike. Menyimpan representasi *state* fitur paling mutakhir dari entitas untuk inference berlatensi ultra-rendah ($< 10\text{ ms}$).

```
                             ARSITEKTUR FEATURE STORE DUAL-STORAGE
                             
 [Event Streams]  ───> [Streaming Engine] ───> [ Online Store: Redis ] ───> [Online Model Service]
 (Kafka / Kinesis)       (Flink / Spark)         (Key: Entity_ID)             (Inference < 10ms)
                                │                 (Value: Latest Features)
                                │
                                ▼
                       [ Offline Store ]  ─────────────────────────────────> [Batch Training Pipeline]
                        (S3 / Parquet)           Point-in-Time Join             (X_train, y_train)
                       Historical Features        AS-OF Timestamp
```

**Point-in-Time Correctness (Time-Travel Join)**:
Saat menggabungkan label peristiwa yang terjadi pada waktu $T_{event}$ dengan nilai fitur, feature store wajib melakukan AS-OF join:
$$Feature\_Value = \arg \max_{t \le T_{event}} f(entity, t)$$
Proses ini menjamin tidak ada feature record yang ditarik dari masa depan ($t > T_{event}$), menghilangkan lookahead bias secara deterministik.

---

## 4. Why & What

### Mengapa Pendekatan Preprocessing Konvensional Gagal di Produksi?

| Karakteristik | Preprocessing Ad-Hoc (Notebook Script) | Enterprise Feature Pipeline |
| :--- | :--- | :--- |
| **Konsistensi State** | State skalar (mean, median) terpecah di berbagai file pickle terpisah atau hardcoded di aplikasi API. | State terenkapsulasi penuh di dalam DAG Pipeline objek yang terserialisasi secara atomik. |
| **Training-Serving Skew** | Implementasi training menggunakan Pandas vectorized, serving menggunakan looping native Python dictionary. Hasil berbeda. | Graph transformasi identik digunakan langsung pada input training maupun single-payload JSON request inference. |
| **Point-in-Time Correctness**| Menggunakan status database mutakhir untuk event masa lalu, menyusupkan sinyal masa depan (*leakage*). | Append-only event-driven table dengan AS-OF joins memastikan integritas temporal. |
| **Kardinalitas Ekstrem** | One-Hot Encoding memecah dimensi menjadi ribuan kolom sparse, membengkakkan alokasi memori inferensi. | Dynamic Bayesian Target Encoding dengan OOF & Out-of-Vocabulary (OOV) backoff fallback. |
| **Drift Visibility** | Buta terhadap degradasi model sampai metrik bisnis hancur. | Pemantauan drift berkelanjutan via uji non-parametrik (KS, PSI) secara otomatis pada payload. |

---

## 5. How (Workflow Detail)

Alur kerja rekayasa fitur end-to-end dari ingestasi data hingga deployment inferensi:

```
               WORKFLOW PIPELINE PRODUKSI DARI DATA HINGGA INFERENSI
               
 [Raw Data Sources]
        │
        ▼
 [1. Data Validation & Profiling] ──────> Gagal? ──> [Alert & Abort Execution]
        │ (Schema & Completeness)
        ▼
 [2. Data Splitting: Temporal / Stratified]
        │
        ├────────────────────────────────────────┐
        ▼                                        ▼
 [Train Split (D_train)]                 [Test/Val Split (D_test)]
        │                                        │
        ▼                                        │
 [3. Fit Feature Pipeline Engine]                │
    - Imputasi Nilai Kosong                      │
    - Bayesian Target Encoder (OOF)              │
    - Robust Scaling                             │
        │                                        │
        ├─── Save Fitted Pipeline Artefak        │
        ▼                                        ▼
 [4. Transform Train Data]              [5. Transform Test Data]
        │                                        │ (Menggunakan State Train)
        ▼                                        ▼
 [6. Train Model Estimator] ───────────> [7. Evaluasi Model Bebas Leakage]
        │                                        │
        ▼                                        ▼
 [8. Serialisasi Model + Pipeline] <─────────────┘
        │
        ▼
 [9. Deployment ke Prediction Service]
        │
        ▼
 [10. Inferensi & Drift Engine Monitoring]
        ├──> Drift Detection Engine (KS-Test, PSI)
        └──> Online Store Synchronizer (Redis Key Sync)
```

1. **Ingestion & Validation**: Memvalidasi kesesuaian skema tipe data, batasan range numerik, dan completeness payload raw.
2. **Temporal Splitting**: Memisahkan train dan test berdasarkan boundary waktu ketat jika data bersifat time-dependent.
3. **Fit Pipeline Engine**: Menghitung state hanya pada data train. Transformasi target menggunakan $K$-Fold cross splits.
4. **Transform Application**: Menerapkan pipeline pada train dan test secara terisolasi tanpa memicu `fit` ulang.
5. **Model Fitting & Verification**: Melatih estimator pada fitur hasil transformasi; validasi integritas metrik.
6. **Artifact Packaging**: Menyimpan DAG pipeline lengkap dalam format binary yang dapat diload kembali secara deterministik.
7. **Runtime Serving & Drift Monitoring**: Model service memproses payload live menggunakan pipeline yang sama dan mengevaluasi pergeseran distribusi fitur secara terus-menerus.

---

## 6. Analogy & Diagram ASCII

Bayangkan sistem preprocessing data sebagai **Instalasi Pemurnian & Pembotolan Air Industri**.

* **Data Mentah**: Air sungai yang keruh, bervariasi debitnya, dan mengandung material asing (missing values, outliers, data noisy).
* **Pipeline Transformasi**: Rangkaian filter, sterilisasi UV, dan mineralisasi berurutan dengan kalibrasi tetap (fixed calibration).
* **Fase Fit Pipeline**: Proses kalibrasi sensor filter menggunakan sampel air uji pertama. Parameter filter (densitas membran, dosis klorin) dikunci mati.
* **Fase Transform Serving**: Setiap galon air baru dialirkan melalui filter terkalibrasi yang sama persis tanpa mengubah pengaturan sensor.
* **Data Leakage**: Teknisi membiarkan air limbah dari tangki output hilir bocor kembali ke tangki input hulu, sehingga sistem mengira air sungai jauh lebih bersih daripada kenyataannya.

```
       SIMULASI DATA LEAKAGE VS PIPELINE TERISOLASI
       
       A. DATA LEAKAGE (BOCOR):
       [Train Data] ──┐
                      ├──> [ Global Scaler Fit (Mean & Std Dihitung Bersama) ]
       [Test Data]  ──┘                      │
             ▲                               ▼
             └──── Test bocor ke Train ──────┴──> Hasil Evaluasi Terlalu Optimis Palsu!

       B. ENTERPRISE ISOLATED PIPELINE (BENAR):
       [Train Data] ──> [ Scaler.fit(Train) ] ──(Save Params: μ_train, σ_train)
                               │
                               ├──> Transform(Train) ──> [Fit Model]
                               │                             │
       [Test Data]  ───────────┼──> Transform(Test)  ────────┤
                                    (Gunakan μ_train, σ_train)│
                                                             ▼
                                                [Evaluasi Akurat Sesuai Realita]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Pipeline Dasar dengan Target Encoding dan Imputasi

Contoh implementasi pipeline minimal menggunakan standar Scikit-Learn API modern:

```python
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

class BasicCategoryEncoder(BaseEstimator, TransformerMixin):
    """Transformer sederhana untuk mengubah string kategori menjadi index terpetakan."""
    def __init__(self):
        self.mapping_: dict[str, dict[str, int]] = {}

    def fit(self, X: pd.DataFrame, y: np.ndarray | None = None) -> "BasicCategoryEncoder":
        X_df = pd.DataFrame(X)
        for col in X_df.columns:
            unique_vals = X_df[col].dropna().unique()
            self.mapping_[col] = {val: idx for idx, val in enumerate(unique_vals)}
        return self

    def transform(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        X_df = pd.DataFrame(X).copy()
        for col, map_dict in self.mapping_.items():
            # Gunakan nilai -1 untuk Out-Of-Vocabulary (OOV)
            X_df[col] = X_df[col].map(map_dict).fillna(-1)
        return X_df.to_numpy(dtype=np.float64)

# Data Mock Sederhana
data = pd.DataFrame({
    'age': [25.0, np.nan, 45.0, 35.0],
    'city': ['Jakarta', 'Surabaya', 'Jakarta', 'Bandung']
})

num_features = ['age']
cat_features = ['city']

preprocessor = ColumnTransformer(
    transformers=[
        ('num', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ]), num_features),
        ('cat', BasicCategoryEncoder(), cat_features)
    ]
)

processed_array = preprocessor.fit_transform(data)
print("Bentuk matriks fitur terproses:", processed_array.shape)
print("Hasil transformasi:\n", processed_array)
```

---

### 7.2 Practical Example: Enterprise Production Pipeline

Berikut adalah arsitektur lengkap pipeline tingkat produksi yang mencakup:
1. **Bayesian Out-of-Fold Target Encoder** untuk fitur kategorikal berkardinalitas tinggi dengan additive Gaussian noise anti-overfitting.
2. **Robust Outlier Dynamic Clipper** menggunakan batasan interkuartil (IQR).
3. **Statistical Drift Monitor** (Kolmogorov-Smirnov Test) terpasang langsung pada transformer.

```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression


@dataclass
class RobustOutlierClipper(BaseEstimator, TransformerMixin):
    """
    Memotong nilai ekstrem (outlier) berdasarkan interquartile range (IQR).
    Menyimpan ambang batas q_low dan q_high per kolom pada fase fit.
    """
    factor: float = 1.5
    bounds_: Dict[str, tuple[float, float]] = field(default_factory=dict)

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[np.ndarray] = None) -> "RobustOutlierClipper":
        df = pd.DataFrame(X)
        self.bounds_ = {}
        for col in df.columns:
            q25 = df[col].quantile(0.25)
            q75 = df[col].quantile(0.75)
            iqr = q75 - q25
            lower_bound = q25 - (self.factor * iqr)
            upper_bound = q75 + (self.factor * iqr)
            self.bounds_[str(col)] = (lower_bound, upper_bound)
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        df = pd.DataFrame(X).copy()
        for col in df.columns:
            col_str = str(col)
            if col_str in self.bounds_:
                lower, upper = self.bounds_[col_str]
                df[col] = df[col].clip(lower=lower, upper=upper)
        return df.to_numpy(dtype=np.float64)


class BayesianOutOfFoldTargetEncoder(BaseEstimator, TransformerMixin):
    """
    K-Fold Target Encoder dengan Bayesian smoothing dan additive noise.
    Mencegah label leakage secara ketat menggunakan split validasi internal.
    """
    def __init__(self, n_splits: int = 5, smoothing: float = 10.0, cv_noise: float = 0.01, random_state: int = 42):
        self.n_splits = n_splits
        self.smoothing = smoothing
        self.cv_noise = cv_noise
        self.random_state = random_state
        self.global_mean_: float = 0.0
        self.encoding_map_: Dict[str, Dict[Union[str, int], float]] = {}

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "BayesianOutOfFoldTargetEncoder":
        if y is None:
            raise ValueError("Target y tidak boleh None untuk Target Encoding.")
        
        df = X.copy()
        y_arr = np.array(y, dtype=np.float64)
        self.global_mean_ = float(np.mean(y_arr))
        self.encoding_map_ = {}

        for col in df.columns:
            # Perhitungan smoothing penuh untuk fase inferensi (transform)
            stats_df = pd.DataFrame({'feat': df[col], 'target': y_arr})
            grouped = stats_df.groupby('feat')['target'].agg(['count', 'mean'])
            counts = grouped['count']
            means = grouped['mean']
            
            # Formula M-Estimate Bayes Smoothing
            smoothed_vals = (counts * means + self.smoothing * self.global_mean_) / (counts + self.smoothing)
            self.encoding_map_[str(col)] = smoothed_vals.to_dict()

        return self

    def fit_transform(self, X: pd.DataFrame, y: np.ndarray) -> np.ndarray:
        if y is None:
            raise ValueError("Target y tidak boleh None untuk fit_transform.")

        df = X.copy()
        y_arr = np.array(y, dtype=np.float64)
        self.global_mean_ = float(np.mean(y_arr))
        self.encoding_map_ = {}

        kf = KFold(n_splits=self.n_splits, shuffle=True, random_state=self.random_state)
        encoded_output = pd.DataFrame(index=df.index, columns=df.columns, dtype=np.float64)

        # 1. Out-of-fold computation untuk mencegah kebocoran pada data latih
        for col in df.columns:
            col_str = str(col)
            oof_series = pd.Series(index=df.index, dtype=np.float64)

            for train_idx, val_idx in kf.split(df, y_arr):
                X_tr, y_tr = df.iloc[train_idx], y_arr[train_idx]
                X_va = df.iloc[val_idx]

                train_stats = pd.DataFrame({'feat': X_tr[col], 'target': y_tr})
                grouped = train_stats.groupby('feat')['target'].agg(['count', 'mean'])
                
                fold_global_mean = float(np.mean(y_tr))
                counts = grouped['count']
                means = grouped['mean']
                smoothed = (counts * means + self.smoothing * fold_global_mean) / (counts + self.smoothing)
                
                mapped_val = X_va[col].map(smoothed).fillna(fold_global_mean)
                oof_series.iloc[val_idx] = mapped_val

            # Tambahkan gaussian noise ringan untuk regularisasi
            if self.cv_noise > 0.0:
                np.random.seed(self.random_state)
                noise = np.random.normal(0, self.cv_noise, size=len(oof_series))
                oof_series = oof_series + noise

            encoded_output[col] = oof_series

            # Hitung mapping global untuk serving masa depan
            full_stats = pd.DataFrame({'feat': df[col], 'target': y_arr})
            full_grouped = full_stats.groupby('feat')['target'].agg(['count', 'mean'])
            f_counts = full_grouped['count']
            f_means = full_grouped['mean']
            f_smoothed = (f_counts * f_means + self.smoothing * self.global_mean_) / (f_counts + self.smoothing)
            self.encoding_map_[col_str] = f_smoothed.to_dict()

        return encoded_output.to_numpy(dtype=np.float64)

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = pd.DataFrame(X).copy()
        output = pd.DataFrame(index=df.index, columns=df.columns, dtype=np.float64)

        for col in df.columns:
            col_str = str(col)
            mapping = self.encoding_map_.get(col_str, {})
            # Gunakan global mean sebagai fallback untuk unknown values
            output[col] = df[col].map(mapping).fillna(self.global_mean_)

        return output.to_numpy(dtype=np.float64)


class ProductionDataDriftDetector(BaseEstimator, TransformerMixin):
    """
    Evaluator Kolmogorov-Smirnov Test untuk mendeteksi drift distribusi numerik saat inference.
    Tidak mengubah matriks fitur (pass-through transformer).
    """
    def __init__(self, alpha_p_value: float = 0.05):
        self.alpha_p_value = alpha_p_value
        self.reference_distributions_: Dict[int, np.ndarray] = {}

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[np.ndarray] = None) -> "ProductionDataDriftDetector":
        X_arr = np.asarray(X, dtype=np.float64)
        self.reference_distributions_ = {}
        for col_idx in range(X_arr.shape[1]):
            # Simpan sampel acak sebagai referensi (max 2000 points demi efisiensi memori)
            col_data = X_arr[:, col_idx]
            clean_data = col_data[~np.isnan(col_data)]
            if len(clean_data) > 2000:
                sampled = np.random.choice(clean_data, size=2000, replace=False)
            else:
                sampled = clean_data
            self.reference_distributions_[col_idx] = sampled
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        X_arr = np.asarray(X, dtype=np.float64)
        for col_idx in range(X_arr.shape[1]):
            ref_data = self.reference_distributions_.get(col_idx)
            if ref_data is not None and len(ref_data) > 30 and X_arr.shape[0] > 30:
                current_data = X_arr[:, col_idx]
                clean_current = current_data[~np.isnan(current_data)]
                ks_stat, p_val = stats.ks_2samp(ref_data, clean_current)
                if p_val < self.alpha_p_value:
                    # Di produksi, logging/alerting diarahkan ke observability stack (misal: Datadog/Prometheus)
                    print(f"[DRIFT ALERT] Kolom index {col_idx} terdeteksi drift! KS-Stat: {ks_stat:.4f}, p-val: {p_val:.4e}")
        return X_arr


# --- IMPLEMENTASI EKSEKUSI PIPELINE ENTERPRISE ---
if __name__ == "__main__":
    # 1. Generate Synthetic Production-like Data
    np.random.seed(42)
    N = 1000
    
    mock_data = pd.DataFrame({
        'transaction_amount': np.random.exponential(scale=100.0, size=N),
        'user_age': np.random.normal(loc=35, scale=10, size=N).clip(18, 70),
        'merchant_id': np.random.choice([f'M_ID_{i}' for i in range(50)], size=N),
        'device_type': np.random.choice(['iOS', 'Android', 'Web'], size=N, p=[0.4, 0.5, 0.1])
    })
    
    # Target binary (fraud probability ditentukan nilai transaksi dan device)
    prob = (mock_data['transaction_amount'] / 500.0) + (mock_data['device_type'] == 'Web') * 0.3
    mock_labels = (prob + np.random.normal(0, 0.1, size=N) > 0.5).astype(int)

    num_cols = ['transaction_amount', 'user_age']
    cat_cols = ['merchant_id', 'device_type']

    # 2. Definisikan Block Sub-Pipeline
    numerical_pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('clipper', RobustOutlierClipper(factor=2.0)),
        ('scaler', StandardScaler())
    ])

    categorical_pipeline = Pipeline([
        ('target_encoder', BayesianOutOfFoldTargetEncoder(n_splits=5, smoothing=15.0, cv_noise=0.005))
    ])

    # 3. Komposisi ColumnTransformer
    feature_assembly = ColumnTransformer(
        transformers=[
            ('num_transform', numerical_pipeline, num_cols),
            ('cat_transform', categorical_pipeline, cat_cols)
        ]
    )

    # 4. Final End-to-End DAG Pipeline
    full_production_pipeline = Pipeline([
        ('features', feature_assembly),
        ('drift_gate', ProductionDataDriftDetector(alpha_p_value=0.01)),
        ('classifier', LogisticRegression(solver='liblinear'))
    ])

    # Split Train/Test Temporal Simulation
    X_train, X_test = mock_data.iloc[:800], mock_data.iloc[800:]
    y_train, y_test = mock_labels[:800], mock_labels[800:]

    # Train Execution
    full_production_pipeline.fit(X_train, y_train)
    print("Pipeline training completed successfully.")

    # Inference Execution
    predictions = full_production_pipeline.predict(X_test)
    print(f"Prediksi berhasil dijalankan untuk {len(predictions)} payload data.")

    # Simulasi Runtime Data Drift (Testing Drift Alerting)
    drifted_payload = X_test.copy()
    drifted_payload['transaction_amount'] = drifted_payload['transaction_amount'] * 15.0  # Anomali lonjakan data
    print("\nMenjalankan inferensi pada payload yang mengalami drift:")
    _ = full_production_pipeline.predict(drifted_payload)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Real-Time Fraud Detection pada Gateway Pembayaran Multinasional

* **Skala Sistem**: $45.000$ transaksi per detik (TPS), latensi end-to-end SLA $< 25\text{ ms}$ (p99).
* **Kompleksitas Data**: Data stream transaksi memiliki variabel kategorikal kardinalitas ekstrem (2,5 juta unik `merchant_id`), dengan label penipuan aktual (*chargeback*) yang memiliki jeda waktu pelaporan 30 hingga 90 hari.

### Desain Arsitektur Preprocessing:
1. **Pemisahan Jalur Fitur (Kappa Architecture)**:
   * **Online Fast-Path**: Fitur agregasi cepat (misal: *jumlah transaksi user dalam 5 menit terakhir*) dihitung menggunakan Apache Flink dan diserialisasikan ke Redis Cluster.
   * **Offline Batch-Path**: Profil agregasi panjang (misal: *rata-rata volume merchant 90 hari*) dihitung harian menggunakan Apache Spark dan disimpan di Iceberg Data Lake.
2. **Kardinalitas Tinggi & Out-Of-Vocabulary (OOV) Mitigation**:
   * Penggunaan Bayesian Target Encoding dengan OOV Backoff fallback bertingkat: Jika `merchant_id` belum pernah muncul di training set, sistem secara dinamis mundur (*fall back*) ke rata-rata `merchant_category_code`, lalu ke global population mean.
3. **Pemberantasan Training-Serving Skew**:
   * Tim ML membungkus logika feature retrieval dan transformation ke dalam single artifact C++ / ONNX-Runtime module. Hal ini menjamin bahwa operasi komputasi saat melatih model di Python dan saat memproses serving di Go microservice menghasilkan representasi bit-level yang 100% identik.

---

## 9. Trade-offs: Analisis Keputusan Rekayasa

| Pendekatan Rekayasa | Keuntungan | Biaya / Kerugian | Latency Impact | Rekomendasi Skenario |
| :--- | :--- | :--- | :--- | :--- |
| **One-Hot Encoding** | - Sederhana.<br>- Non-parametrik (tidak mengasumsikan distribusi). | Ledakan dimensi tinggi; memori melonjak dramatis; komputasi sparse matrix lambat. | Tinggi jika kardinalitas $> 100$. | Kategori kardinalitas rendah ($< 20$) seperti jenis kelamin, sistem operasi. |
| **Bayesian Target Encoding** | - Dimensi output tetap $1$ kolom per fitur.<br>- Menangkap korelasi kuat dengan target. | Risiko target leakage tinggi jika OOF tidak diterapkan; sensitif terhadap label shift. | Sangat Rendah ($O(1)$ Hash Table Lookup). | Kategori kardinalitas tinggi (ZIP code, Merchant ID, User Agent). |
| **Dynamic Imputation (KNN/Iterative)** | - Menjaga korelasi multivariat antar variabel. | Kompleksitas komputasi inference $O(N \cdot D)$; ukuran serialisasi state membengkak. | Sangat Tinggi ($> 100\text{ ms}$). | Batch analytics offline di mana akurasi marginal adalah prioritas absolut. |
| **Static Median / Indicator Imputation** | - Eksekusi deterministik instan.<br>- Tidak membutuhkan referensi dataset masa lalu. | Hilangnya varians alami; mengasumsikan pola Missing Completely at Random (MCAR). | Sangat Rendah ($< 1\text{ ms}$). | High-throughput low-latency real-time inference ($> 1000\text{ TPS}$). |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Kritis 1: Scaling/Normalisasi Sebelum Train-Test Split
* **Gejala**: Skor validasi cross-validation menghasilkan ROC-AUC 0.98, tetapi performa rontok ke 0.71 saat dideploy ke traffic live.
* **Root Cause**: Menjalankan `StandardScaler.fit_transform()` pada seluruh dataset sebelum partisi train/test. Informasi deviasi standar dan mean dari test set menyusup ke train set (*Lookahead Bias*).
* **Solusi**: Bungkus scaler di dalam pipeline Scikit-Learn dan pastikan method `pipeline.fit()` **hanya** dipanggil menggunakan data `X_train`.

### Kesalahan Kritis 2: Modifikasi In-Place pada Pandas DataFrame
* **Gejala**: Terjadi warning `SettingWithCopyWarning` atau mutasi state yang tidak deterministik saat transformer dipanggil berulang kali.
* **Root Cause**: `X['feature'] = X['feature'].fillna(...)` memutasi underlying memory dataframe pemanggil.
* **Solusi**: Wajib membuat defensive copy secara eksplisit: `df = X.copy()` di awal method `transform()`.

### Kesalahan Kritis 3: Penggunaan `fit_transform()` pada Serving Runtime
* **Gejala**: Pada microservice inference, pemanggilan payload tunggal menghasilkan error `ValueError` karena sample size $N=1$, atau menghasilkan nilai skalar yang terdistorsi.
* **Root Cause**: Pengembang mengeksekusi `pipeline.fit_transform(payload)` alih-alih `pipeline.transform(payload)`.
* **Solusi**: Kunci pipeline pada production service: override atau blokir akses method `fit` pada runtime serving container, hanya perbolehkan eksekusi method `transform`.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum menandatangani persetujuan (*sign-off*) perilisan pipeline ke production environment:

- [ ] **Strict Typing & Contracts**: Semua custom transformer mewarisi `BaseEstimator` dan `TransformerMixin` dengan Type Annotations lengkap.
- [ ] **Deterministic Serialization**: Serialisasi dilakukan terhadap seluruh hierarki pipeline (bukan transformer individual) menggunakan `joblib` dengan kompresi terukur (`compress=3`).
- [ ] **Data Immutability**: Transformer tidak memodifikasi input array/dataframe secara in-place.
- [ ] **Out-Of-Vocabulary Handling**: Setiap categorical encoder memiliki strategi fallback jika menemukan nilai kategori baru yang tidak pernah muncul di fase training.
- [ ] **State Encapsulation**: Transformer menyimpan parameter internal dalam atribut berakhiran garis bawah (misal: `self.mean_`, `self.bounds_`) sesuai konvensi Scikit-Learn.
- [ ] **Dimensionality Assertion**: Terdapat validation assertion sebelum step model yang memastikan jumlah kolom output preprocessing sama persis dengan input layer model.
- [ ] **Numerical Drift Hooks**: Menyiapkan hook eksekusi pengujian statistik distribusi (KS-test / PSI) pada batch inference.

---

## 12. Hands-on Practice

Buat dan simpan struktur file berikut ke dalam direktori lokal: `hands-on/m02/`

### File: `hands-on/m02/custom_transformers.py`
```python
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

class SafeLogTransformer(BaseEstimator, TransformerMixin):
    """Menerapkan transformasi logaritma natural log(x + offset) yang aman dari nilai <= 0."""
    def __init__(self, offset: float = 1.0):
        self.offset = offset

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X_arr = np.asarray(X, dtype=np.float64)
        if np.any(X_arr + self.offset <= 0):
            raise ValueError("Terdapat nilai <= 0 setelah penambahan offset. Logaritma tidak terdefinisi.")
        return np.log(X_arr + self.offset)
```

### File: `hands-on/m02/pipeline_builder.py`
```python
import joblib
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from custom_transformers import SafeLogTransformer

def build_and_save_pipeline(train_df: pd.DataFrame, output_path: str):
    num_skewed = ['income']
    num_standard = ['credit_score']

    feature_pipeline = ColumnTransformer(
        transformers=[
            ('skewed', Pipeline([
                ('log', SafeLogTransformer(offset=1.0)),
                ('scaler', StandardScaler())
            ]), num_skewed),
            ('standard', StandardScaler(), num_standard)
        ]
    )

    feature_pipeline.fit(train_df)
    joblib.dump(feature_pipeline, output_path)
    print(f"Pipeline artefak berhasil disimpan di: {output_path}")

if __name__ == "__main__":
    df_sample = pd.DataFrame({
        'income': [10000.0, 50000.0, 120000.0, 8000.0],
        'credit_score': [600.0, 720.0, 810.0, 580.0]
    })
    build_and_save_pipeline(df_sample, "hands-on/m02/feature_pipeline.joblib")
```

---

## 13. Exercise

### Level Easy
Modifikasi kelas `SafeLogTransformer` pada bagian Hands-on agar dapat menangani nilai negatif secara otomatis dengan cara menghitung parameter `min_val` secara dinamis pada fase `fit`:
$$\text{offset} = |\min(X)| + 1.0 \quad \text{jika } \min(X) \le 0$$

### Level Medium
Buat sebuah transformer scikit-learn custom bernama `CyclicDateTimeEncoder` yang mengekstrak fitur tanggal-waktu (kolom string ISO/timestamp) menjadi dua komponen representasi periodik menggunakan fungsi trigonometri:
$$\sin\left(\frac{2\pi \cdot t}{T}\right) \quad \text{dan} \quad \cos\left(\frac{2\pi \cdot t}{T}\right)$$
di mana $T$ adalah periode maksimum (misal: 24 untuk jam, 7 untuk hari dalam seminggu).

### Level Hard
Implementasikan sebuah transformer custom bernama `FrequencyEncoderWithBackoff` yang memetakan kategori ke frekuensi kemunculannya. Spesifikasi:
1. Menghitung frekuensi relatif setiap kategori pada fase `fit`.
2. Menerapkan ambang batas frekuensi minimum (`min_freq`). Semua kategori dengan frekuensi di bawah nilai ambang batas tersebut secara otomatis dikelompokkan ke dalam satu bucket gabungan: `__RARE__`.
3. Pada fase `transform`, kategori yang tidak dikenal (OOV) wajib dialokasikan ke bucket `__RARE__`.
4. Kompatibel secara native dengan input data bertipe Pandas DataFrame maupun NumPy structured array.

---

## 14. Challenge

### Studi Kasus: Pipeline Pemrosesan Real-time Sensor IoT Berfrekuensi Tinggi dengan Drift Adaptif

Sebuah konsorsium energi mengoperasikan $10.000$ turbin angin lepas pantai. Tiap turbin mentransmisikan data telemetri (tekanan, temperatur, kecepatan rotasi poros) setiap $100\text{ ms}$. 

**Kondisi Lingkungan & Masalah**:
1. Sensor sering mengalami degradasi fisik (*sensor degradation drift*), menghasilkan pergeseran rata-rata nilai bacaan secara perlahan seiring waktu.
2. Latensi inferensi lokal pada unit edge-computing turbin dibatasi maksimal $5\text{ ms}$ per inferensi.
3. Model Machine Learning lokal bertugas memprediksi kegagalan bantalan mekanis (*bearing failure*).
4. Bandwidth uplink satelit dari turbin lepas pantai ke datacenter pusat sangat mahal dan terbatas ($< 64\text{ kbps}$ per turbin), sehingga transmisi seluruh data mentah untuk training ulang tidak memungkinkan.

**Tugas Arsitektur Anda**:
Rancang spesifikasi arsitektur preprocessing pipeline modular yang:
1. Berjalan di edge device dengan alokasi memori $< 32\text{ MB}$.
2. Menerapkan kalkulasi *Streaming Online Normalization* (Welford's algorithm) untuk mempertahankan estimasi mean dan varians yang terus terupdate secara *real-time* tanpa menyimpan seluruh array historis.
3. Mengembangkan mekanisme deteksi drift berbasis ambang batas Wasserstein Distance atau Page-Hinkley test yang memicu peringatan (*drift alert flag*) jika deviasi pola fisik menyimpang dari karakteristik dasar pabrikasi.
4. Tuliskan blueprint teknis sistem ini dalam bentuk dokumen arsitektur dan lengkapi dengan implementasi class Python production-ready untuk komponen *Streaming Online Normalization* tersebut.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Pertanyaan)

1. **Apa perbedaan fungsional utama antara method `fit()` dan `transform()` pada Scikit-Learn Transformer?**
   * A. `fit()` mengubah data, `transform()` menyimpan parameter.
   * B. `fit()` menghitung parameter internal dari data; `transform()` menerapkan operasi menggunakan parameter tersebut.
   * C. `fit()` digunakan untuk testing, `transform()` untuk training.
   * D. Tidak ada perbedaan, keduanya melakukan operasi identik.

2. **Mengapa pemanggilan `StandardScaler.fit()` pada seluruh dataset (train + test digabung) digolongkan sebagai kesalahan fatal?**
   * A. Menghasilkan error pembagian dengan nol.
   * B. Mengakibatkan dimensionalitas matriks menjadi tidak konsisten.
   * C. Menyebabkan kebocoran data (*data leakage*) yang menghasilkan estimasi performa model terlalu optimis secara palsu.
   * D. Memperlambat proses training secara eksponensial.

3. **Apa kegunaan utama parameter `strategy='median'` dibandingkan `strategy='mean'` pada `SimpleImputer`?**
   * A. Median lebih cepat dikomputasi daripada mean.
   * B. Median lebih tahan (*robust*) terhadap skewness dan pengaruh outlier ekstrem.
   * C. Median selalu menghasilkan angka bulat.
   * D. Median dapat diterapkan langsung pada data string kategorikal.

4. **Bagaimana arsitektur Scikit-Learn mendesain ColumnTransformer?**
   * A. Hanya dapat memproses satu kolom dalam satu waktu.
   * B. Menggabungkan beberapa transformer secara sekuensial pada satu fitur yang sama.
   * C. Mengaplikasikan subset transformer yang berbeda ke subset kolom input yang berbeda secara paralel, lalu menggabungkan hasilnya secara horizontal.
   * D. Menghapus kolom yang tidak memiliki korelasi dengan target.

5. **Apa yang dimaksud dengan Training-Serving Skew?**
   * A. Perbedaan akurasi antara algoritma Random Forest dan Neural Network.
   * B. Perbedaan performa model yang disebabkan oleh diskrepansi antara pipeline transformasi data pada fase pelatihan dan fase produksi nyata.
   * C. Kegagalan infrastruktur server saat menampung lonjakan traffic inferensi.
   * D. Perubahan label target akibat kesalahan operator database.

### Bagian 2: Intermediate (5 Pertanyaan)

6. **Pada Bayesian Target Encoding, apa peran utama dari parameter *smoothing* ($m$)?**
   * A. Mempercepat konvergensi algoritma optimasi SGD.
   * B. Menarik estimasi nilai target kategori berkardinalitas/frekuensi rendah mendekati rata-rata global (*global prior*).
   * C. Menghilangkan fitur yang memiliki korelasi linier tinggi dengan fitur lain.
   * D. Mengonversi data numerik kontinu menjadi representasi diskrit biner.

7. **Mengapa teknik Out-of-Fold (OOF) wajib diterapkan saat melakukan Target Encoding pada data training?**
   * A. Untuk mengompresi ukuran disk matriks fitur.
   * B. Untuk memastikan memori RAM tidak mengalami kehabisan alokasi saat encoding.
   * C. Untuk mencegah target nilai baris saat ini mengontaminasi nilai encoding fitur baris itu sendiri, yang dapat memicu overfit parah.
   * D. Agar kompatibel dengan arsitektur GPU CUDA.

8. **Dalam arsitektur Feature Store, apa yang dimaksud dengan *Point-in-Time Correctness* (AS-OF join)?**
   * A. Kemampuan sistem untuk menghapus fitur yang sudah kadaluwarsa dari hard drive.
   * B. Menghubungkan label peristiwa di waktu $T$ hanya dengan nilai fitur yang tercatat sebelum atau tepat pada waktu $T$.
   * C. Sinkronisasi jam atomik antara server offline store dan online store.
   * D. Menjalankan pipeline transformasi tepat pada pukul 00:00 UTC setiap hari.

9. **Apa batasan teknis utama dari uji Kolmogorov-Smirnov (KS-test) 2-sampel saat digunakan sebagai monitor data drift otomatis?**
   * A. Hanya dapat diaplikasikan pada fitur kategorikal non-numerik.
   * B. Sangat sensitif terhadap ukuran sampel besar, di mana deviasi numerik yang sangat kecil dan tidak signifikan secara praktis dapat menghasilkan p-value $< 0.05$.
   * C. Tidak dapat mendeteksi perubahan lokasi rata-rata (*mean shifts*).
   * D. Membutuhkan runtime komputasi $O(N^3)$ yang sangat lambat.

10. **Metode imputasi missing values manakah yang paling berisiko tinggi menyebabkan pembengkakan latensi pada sistem serving inference real-time?**
    * A. Imputasi konstanta nilai tetap (Zero Imputation).
    * B. Imputasi berbasis K-Nearest Neighbors (KNNImputer) yang dihitung on-the-fly.
    * C. Imputasi modus kategori global.
    * D. Imputasi median statis yang telah disimpan dalam state dictionary.

### Bagian 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario Kasus A**:
    Sistem deteksi fraud transaksi keuangan Anda mendadak mengalami lonjakan False Positive Rate (transaksi sah diblokir) dari $0.5\%$ menjadi $8.2\%$ setelah event "Festival Belanja Nasional". Fitur `transaction_amount` menunjukkan nilai drift uji KS dengan $p$-value $10^{-12}$. Evaluasi model offline menunjukkan model masih bekerja normal jika dievaluasi dengan data tahun lalu.
    *Pertanyaan*: Tindakan rekayasa data preprocessing manakah yang paling tepat untuk mengatasi masalah ini secara struktural?
    * A. Menghapus fitur `transaction_amount` dari model inference.
    * B. Mengganti standard scaling absolut dengan transformasi berbasis rasio terhadap riwayat pembelanjaan user (misal: `transaction_amount / user_avg_amount_30d`).
    * C. Mengalikan seluruh input inference dengan faktor koreksi $0.1$.
    * D. Melakukan downsampling manual pada data transaksi belanja nasional.

12. **Skenario Kasus B**:
    Sebuah startup logistik meluncurkan model estimasi waktu kedatangan paket (ETA). Pipeline preprocessing menggunakan `OneHotEncoder(handle_unknown='ignore')` untuk kolom `district_id`. Setelah ekspansi ke 100 kota baru, model sering memprediksi nilai ETA yang sangat menyimpang pada area-area baru tersebut.
    *Pertanyaan*: Apa kelemahan mendasar arsitektur preprocessing ini dan bagaimana solusinya?
    * A. `OneHotEncoder` gagal mengalokasikan vektor representasi untuk distrik baru (semua baris menjadi vektor 0), sehingga model kehilangan seluruh sinyal lokasi; solusi terbaik adalah beralih ke Target Encoding berbasis hierarki regional atau Spatial Coordinate Embeddings (Latitude, Longitude).
    * B. Parameter `handle_unknown='ignore'` memicu runtime exception crash pada microservice.
    * C. One-Hot Encoding membuat memori RAM over-allocation pada container inferensi.
    * D. Model regresi linier tidak mampu memproses matriks berformat sparse.

13. **Skenario Kasus C**:
    Platform e-commerce Anda memiliki microservice inferensi model rekomendasi yang ditulis dalam bahasa Rust/Go untuk mengejar SLA p99 $< 5\text{ ms}$. Namun, tim Data Science Anda membuat pipeline feature engineering yang sangat kompleks menggunakan pustaka Python Pandas dan Scikit-Learn.
    *Pertanyaan*: Pola arsitektur enterprise mana yang paling efektif memecahkan kesenjangan implementasi ini tanpa memicu Training-Serving Skew?
    * A. Membiarkan tim engineer menulis ulang pipeline Python ke dalam kode Go/Rust secara manual menggunakan logika conditional hard-coded.
    * B. Menjalankan sub-proses Python shell execution dari dalam Go microservice untuk setiap payload inferensi.
    * C. Mengekspor pipeline feature engineering lengkap dan model estimasi ke format Open Neural Network Exchange (ONNX) graph yang dapat dieksekusi secara native via ONNX Runtime di Go/Rust.
    * D. Meminta tim Data Science menyederhanakan preprocessing menjadi hanya operasi skalar sederhana.

---

### Kunci Jawaban Quiz

#### Bagian 1: Basic
1. **B** — `fit()` menghitung parameter internal dari data latih, sedangkan `transform()` menerapkan kalkulasi dengan parameter tersebut.
2. **C** — Mempelajari informasi data test pada fase preprocessing menyusupkan informasi ke model (data leakage).
3. **B** — Median tidak terdistorsi oleh skewness ekstrem atau pencilan data jika dibandingkan dengan mean.
4. **C** — ColumnTransformer mengeksekusi operasi berbeda pada kolom berbeda secara paralel lalu menyatukan outputnya.
5. **B** — Diskrepansi implementasi logika rekayasa fitur antara fase riset/training dan sistem live serving.

#### Bagian 2: Intermediate
6. **B** — Smoothing Bayesian meminjam kekuatan data agregat global untuk mencegah overfitting pada kategori minoritas.
7. **C** — Mencegah korelasi sirkular di mana target sebuah observasi digunakan untuk mengkodekan dirinya sendiri.
8. **B** — AS-OF join menjamin fitur ditarik persis sesuai kondisi historis pada cap waktu kejadian perkara.
9. **B** — KS-Test menjadi *hyper-sensitive* pada ukuran sampel masif, seringkali memicu alarm palsu pada pergeseran distribusi yang sangat sepele.
10. **B** — KNNImputer harus mencari jarak euclidean ke seluruh titik data training untuk setiap baris inferensi ($O(N \cdot D)$), sangat merusak latensi real-time.

#### Bagian 3: Skenario Kasus Produksi
11. **B** — Transformasi rasio relatif memvalidasi deviasi terhadap pola kebiasaan individu alih-alih nilai nominal global yang rentan terdistorsi event belanja musiman.
12. **A** — Distrik baru hanya menghasilkan baris serba nol pada OneHotEncoder, menghilangkan fitur lokasi sama sekali; koordinat kontinu atau encoding hierarki memberikan representasi yang lebih informatif.
13. **C** — Format portabel ONNX mengekspresikan seluruh operasi transformasi sebagai computational graph terstandarisasi, dieksekusi native pada engine Go/Rust tanpa dependensi runtime Python.

---

## 16. Summary

1. **Pipeline Determinism**: Rekayasa fitur enterprise wajib memisahkan fase estimasi state (`fit`) dan aplikasi state (`transform`) secara mutlak guna mencegah timbulnya kebocoran informasi (*data leakage*).
2. **Advanced Encoding**: Kategori berkardinalitas tinggi harus ditangani menggunakan Bayesian Target Encoding yang diregulasi dengan $K$-Fold Out-of-Fold split dan Bayesian smoothing agar terhindar dari overfitting.
3. **Modern Feature Store Topology**: Arsitektur dual-storage (Offline OLAP untuk batch training, Online Key-Value untuk low-latency serving) yang didukung oleh *Point-in-Time Correctness* (AS-OF join) adalah standar industri untuk mengeliminasi lookahead bias.
4. **Resilience & Drift Guarding**: Pipeline produksi wajib mengintegrasikan pengujian statistik data drift (uji Kolmogorov-Smirnov atau PSI) dan strategi fallback (handling out-of-vocabulary) guna mendeteksi serta meredam degradasi performa model di lingkungan dinamis.