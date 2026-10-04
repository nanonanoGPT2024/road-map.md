# BAB 05: Exploratory Data Analysis & Statistika Terapan Enterprise
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengonseptualisasikan dan mengimplementasikan sistem inferensi statistik terdistribusi dan otomatis (*Automated Statistical Testing Engine*) untuk validasi hipotesis data berskala besar.
- Menganalisis dan mendeteksi penyimpangan distribusi data (*data drift*, *concept drift*, dan *covariate shift*) menggunakan metrik inferensial formal seperti *Population Stability Index* (PSI), *Wasserstein Distance*, dan uji *Kolmogorov-Smirnov* secara *vectorized*.
- Mengimplementasikan algoritma deteksi anomali multivariat berbasis statistik tingkat lanjut (*Minimum Covariance Determinant* / *Mahalanobis Distance*, *Isolation Forest*) yang diintegrasikan langsung ke dalam pipeline ETL/ELT.
- Merancang arsitektur profil data berbasis performa tinggi (*low-memory footprint*) menggunakan Apache Arrow engine pada Pandas 2.x/Polars untuk dataset melebihi kapasitas memori sistem (*out-of-core computing*).
- Menghindari perangkap umum statistika terapan di level produksi, seperti fenomena *p-hacking*, pengujian hipotesis ganda tanpa koreksi (*Family-Wise Error Rate* via Bonferroni/Benjamini-Hochberg), dan bias seleksi data.

---

### 2. Prerequisite
Untuk menyerap materi secara optimal, Anda wajib menguasai:
- **Python Pemrograman Lanjutan**: OOP tingkat lanjut, *metaclasses*, *context managers*, *type hinting* (`typing.Annotated`, `Protocol`), generator, dan *asynchronous processing* (`asyncio`, `concurrent.futures`).
- **Fondasi Statistika Inferensial**: Distribusi probabilitas kontinu dan diskret, *Central Limit Theorem* (CLT), uji hipotesis dasar (One/Two-sample Z-test, Student's t-test, ANOVA), derajat kebebasan (*degrees of freedom*), dan Teorema Bayes.
- **Data Manipulation Internals**: Memahami representasi memori NumPy C-contiguous vs Fortran-contiguous array, pointer memori, serta Arrow memory layout (Columnar format).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Arsitektur Komputasi Inferensi Statistik di Produksi
Dalam skala enterprise, Exploratory Data Analysis (EDA) dan pengujian statistik bergeser dari pekerjaan interaktif di Jupyter Notebook menjadi tahapan terotomatisasi di pipeline data (*Continuous Data Validation*). 

Ketika data stream atau batch berukuran terabyte masuk ke sistem ingest, pipeline harus mampu melakukan inferensi multivariat tanpa memicu degradasi memori (*OOM - Out of Memory*).

```
+-------------------------------------------------------------------------------------------------+
|                                 ENTERPRISE STATISTICAL INFERENCE ENGINE                         |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   +-------------------+       +-----------------------+       +-----------------------------+   |
|   | Raw Data Source   | ----> | Chunked Arrow Ingest  | ----> | Vectorized Pre-processing   |   |
|   | (S3/GCS Parquet)  |       | (PyArrow / Zero-Copy) |       | (Imputation, Winsorization) |   |
|   +-------------------+       +-----------------------+       +-----------------------------+   |
|                                                                              |                  |
|                                                                              v                  |
|   +-----------------------------------------------------------------------------------------+   |
|   |                              STATISTICAL ENGINE CORE EXECUTION                          |   |
|   |                                                                                         |   |
|   |   +----------------------+    +-----------------------+    +------------------------+   |   |
|   |   | Distribution Profiler|    | Hypothesis Testing Hub|    | Multivariate Outliers  |   |   |
|   |   | - Shapiro-Wilk/D'Agos|    | - Welch's t-test      |    | - Rob. Mahalanobis MCD |   |   |
|   |   | - KS-Test & PSI      |    | - Mann-Whitney U      |    | - Isolation Forest     |   |   |
|   |   | - Wasserstein Dist   |    | - Chi-Square / Fisher |    | - LOF (Local Outlier)  |   |   |
|   |   +----------------------+    +-----------------------+    +------------------------+   |   |
|   +-----------------------------------------------------------------------------------------+   |
|                                              |                                                  |
|                                              v                                                  |
|   +-----------------------------------------------------------------------------------------+   |
|   |                              MULTIPLE TESTING CORRECTION LAYER                          |   |
|   |   - Bonferroni Correction (FWER Control)                                                |   |
|   |   - Benjamini-Hochberg Procedure (FDR Control)                                          |   |
|   +-----------------------------------------------------------------------------------------+   |
|                                              |                                                  |
|                                              v                                                  |
|   +-----------------------+      +------------------------+      +--------------------------+   |
|   | Structured Metadata   |      | Automated Governance   |      | Operational Action       |   |
|   | Store (PostgreSQL)    |      | Alerting (Prometheus)  |      | Circuit-Breaker / Model  |   |
|   |                       |      |                        |      | Retraining Trigger       |   |
|   +-----------------------+      +------------------------+      +--------------------------+   |
+-------------------------------------------------------------------------------------------------+
```

#### 3.2. Formulasi Metrik Deteksi Drift Data

##### A. Population Stability Index (PSI)
Digunakan secara masif di sektor finansial perbankan dan *fraud detection* untuk mengukur derajat perubahan profil populasi antara distribusi referensi ($B$ - Baseline) dan distribusi aktual ($A$ - Actual) di seluruh $K$ bins:

$$PSI = \sum_{k=1}^{K} \left( \%A_k - \%B_k \right) \times \ln\left(\frac{\%A_k}{\%B_k}\right)$$

Interpretasi Ambang Batas Industri:
- $PSI < 0.1$: Tidak ada pergeseran signifikan (*No Shift*). Pipeline berjalan normal.
- $0.1 \le PSI < 0.25$: Terjadi pergeseran moderat (*Moderate Drift*). Membutuhkan logging & monitoring.
- $PSI \ge 0.25$: Pergeseran signifikan (*Significant Shift*). Circuit-breaker memutus proses ingest; data ditolak atau model di-*retrain*.

##### B. Mahalanobis Distance via Minimum Covariance Determinant (MCD)
Mendeteksi anomali multivariat dengan memperhitungkan struktur korelasi/kovarians antar fitur, mengatasi kelemahan Euclidean Distance yang mengasumsikan varians seragam dan ortogonal:

$$D_M(\vec{x}) = \sqrt{(\vec{x} - \vec{\mu})^T \mathbf{\Sigma}^{-1} (\vec{x} - \vec{\mu})}$$

Di mana $\vec{x}$ adalah vektor fitur observasi, $\vec{\mu}$ adalah vektor rata-rata fitur, dan $\mathbf{\Sigma}$ adalah matriks kovarians. Dalam kondisi produksi dengan adanya kontaminasi *outlier*, $\vec{\mu}$ dan $\mathbf{\Sigma}$ diestimasi menggunakan **Rousseeuw's Minimum Covariance Determinant (MCD)** yang robust, bukan rata-rata empiris biasa yang sangat sensitif terhadap nilai ekstrem.

---

### 4. Why & What

| Dimensi Evaluasi | Manual / Notebook-Based EDA | Enterprise Production-Grade EDA Engine |
| :--- | :--- | :--- |
| **Lingkungan Eksekusi** | Ad-hoc, interaktif via Jupyter | Terjadwal, terisolasi, non-interactive CI/CD atau ELT Task |
| **Validasi Asumsi** | Visualisasi ad-hoc (histogram, scatter plot) | Automated Normality & Homoscedasticity testing |
| **Kapasitas Memori** | Dibatasi oleh RAM sistem lokal (Pandas eager mode) | Streaming chunk/Arrow memory mapping dengan zero-copy |
| **Pengujian Hipotesis** | Uji terisolasi tanpa koreksi $p$-value | Evaluasi masif multivariat dengan koreksi FDR (Benjamini-Hochberg) |
| **Aksi Terhadap Drift** | Peninjauan manual berkala | Trigger sirkuit pembatas (*circuit breaker*), sistem peringatan otomatis |

#### Mengapa Uji Hipotesis Ganda Membutuhkan Koreksi?
Bila Anda menjalankan $m$ uji independen pada tingkat signifikansi $\alpha = 0.05$, peluang melakukan setidaknya satu *Type I Error* (False Positive) dihitung dengan:

$$\alpha_{total} = 1 - (1 - \alpha)^m$$

Jika $m = 100$, maka $\alpha_{total} = 1 - (1 - 0.05)^{100} \approx 0.994$. Artinya, ada probabilitas $99.4\%$ bahwa Anda mengklaim menemukan anomali atau perbedaan signifikan yang sebenarnya hanyalah *noise* acak. Pipeline enterprise wajib menerapkan kontrol **False Discovery Rate (FDR)**.

---

### 5. How (Workflow Detail)

Alur kerja arsitektural engine analitik statistik otomatis mencakup 5 tahapan berurutan:

```
[Inbound Data Chunk]
        |
        v
[1. Asumsi Data Profiling Engine]
   ├── Test Distribusi: Shapiro-Wilk (n < 5000) atau D'Agostino-Pearson (n >= 5000)
   ├── Test Homoskedastisitas: Levene's Test (Robust terhadap non-normalitas)
   └── Check Missing Value Sparsity & Zero-Variance Columns
        |
        v
[2. Dynamic Routing Inferensi Statistik]
   ├── If Normal & Homoskedastis   --> Student's Two-Sample t-test / ANOVA
   ├── If Normal & Heteroskedastis --> Welch's t-test
   └── If Non-Normal               --> Mann-Whitney U / Kruskal-Wallis Test
        |
        v
[3. Matrix-Level Drift & Distance Calculation]
   ├── Kolmogorov-Smirnov Test (Non-parametric empirical cumulative distribution)
   ├── Wasserstein-1 Distance (Earth Mover's Distance)
   └── Binning Analysis -> Population Stability Index (PSI)
        |
        v
[4. Multiple Hypothesis Correction Layer]
   ├── Kumpulkan seluruh p-values dari seluruh fitur
   └── Terapkan Benjamini-Hochberg False Discovery Rate (FDR) control
        |
        v
[5. State Determination & Telemetry Dispatch]
   ├── Status Validated: Route ke feature store / downstream ingestion
   └── Status Rejected / Alert: Dispatch metrics ke OpenTelemetry & trigger audit log
```

---

### 6. Analogy & Diagram ASCII

#### Analogi: Bandara Internasional dengan Jalur Keamanan Multi-Tier
Bayangkan sebuah bandara internasional yang harus memproses puluhan ribu penumpang per jam:
1. **Pemeriksaan Suhu Cepat (Simple Profiling)**: Sensor termal inframerah memfilter anomali langsung secara real-time tanpa menyentuh penumpang. Ini merepresentasikan *Z-score check* atau *range constraints*.
2. **Pintu X-Ray & Metal Detector Dinamis (Dynamic Hypothesis Routing)**: Jika penumpang membawa barang elektronik kompleks, mereka diarahkan ke pemindai CT-scan 3D (uji non-parametrik yang komputasinya berat). Jika hanya tas biasa, cukup X-ray konvensional (uji parametrik cepat).
3. **Pemeriksaan Komparatif Paspor (PSI / Drift Detection)**: Sistem membandingkan pola kedatangan wisatawan saat ini terhadap profil demografis historis bulan lalu. Jika tiba-tiba ada deviasi drastis pada rentang usia tertentu dari wilayah spesifik, sistem memicu *red flag* untuk penyelidikan lanjutan.

```
       +----------------------------------------------------------------+
       |                  MEMORY BUFFER COMPARISON                      |
       +----------------------------------------------------------------+
       
       Standard Pandas (Python Objects / Non-contiguous Pointers)
       +--------+      +--------+      +--------+
       | Boxed  | ---> | Boxed  | ---> | Boxed  |   (Fragmented Heap Mem)
       | Float  |      | Float  |      | Float  |   High Cache-Miss Ratio
       +--------+      +--------+      +--------+
       
       Arrow Columnar Format (Zero-Copy Interop / SIMD Vectorized)
       +----------------------------------------------------------------+
       | Valid Bits Bitmask: 1 1 1 0 1 1 1 ...                          |
       +----------------------------------------------------------------+
       | Contiguous Data Buffer:                                        |
       | [ 42.195 | 10.501 | 99.120 | NULL | 12.004 | 55.431 | ... ]    |
       +----------------------------------------------------------------+
             |         |         |            |        |
             +---------+---------+------------+--------+
                                  |
                                  v
                        [ SIMD Vector Units ]
                     Single Instruction -> Multiple Data
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Implementasi Population Stability Index (Vectorized NumPy)
Contoh berikut menunjukkan implementasi formal PSI menggunakan NumPy murni tanpa iterasi Python (`for-loops`), siap menangani jutaan baris data secara instan.

```python
from typing import Tuple
import numpy as np


def calculate_psi(
    baseline: np.ndarray,
    actual: np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> Tuple[float, np.ndarray]:
    """Menghitung Population Stability Index (PSI) antara dua set observasi numerik.

    Menggunakan vectorized quantile binning berbasis dataset baseline.

    Args:
        baseline: Array 1D distribusi referensi.
        actual: Array 1D distribusi produksi berjalan.
        num_bins: Jumlah kuantil bucket pembagi (default=10).
        epsilon: Faktor regularisasi untuk mencegah ZeroDivisionError atau ln(0).

    Returns:
        Tuple berisi total nilai float PSI dan array representasi kontribusi tiap bin.
    """
    if baseline.ndim != 1 or actual.ndim != 1:
        raise ValueError("Baseline dan actual harus berdimensi 1 (1D array).")

    # 1. Tentukan batas bin (quantiles) menggunakan referensi baseline
    quantiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(baseline, quantiles)
    
    # Tangani duplikasi edge jika varians data sangat rendah
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 2:
        return 0.0, np.zeros(1)

    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    # 2. Hitung frekuensi absolut tiap bin
    baseline_counts, _ = np.histogram(baseline, bins=bin_edges)
    actual_counts, _ = np.histogram(actual, bins=bin_edges)

    # 3. Normalisasi menjadi fraksi proporsi probabilitas
    baseline_pct = baseline_counts / len(baseline)
    actual_pct = actual_counts / len(actual)

    # 4. Regularisasi epsilon untuk stabilitas numerik floating point
    baseline_pct = np.clip(baseline_pct, epsilon, None)
    actual_pct = np.clip(actual_pct, epsilon, None)

    # 5. Kalkulasi komponen PSI: (Actual% - Baseline%) * ln(Actual% / Baseline%)
    bin_psi = (actual_pct - baseline_pct) * np.log(actual_pct / baseline_pct)
    total_psi = float(np.sum(bin_psi))

    return total_psi, bin_psi


if __name__ == "__main__":
    np.random.seed(42)
    # Baseline: Distribusi normal standar
    base_dist = np.random.normal(loc=0.0, scale=1.0, size=500_000)
    
    # Case A: Distribusi stabil dengan noise minimal
    stable_dist = np.random.normal(loc=0.02, scale=1.01, size=500_000)
    psi_stable, _ = calculate_psi(base_dist, stable_dist)
    print(f"PSI Distribusi Stabil: {psi_stable:.5f}")

    # Case B: Distribusi mengalami pergeseran rata-rata (Covariate Shift)
    drifted_dist = np.random.normal(loc=0.45, scale=1.2, size=500_000)
    psi_drift, _ = calculate_psi(base_dist, drifted_dist)
    print(f"PSI Distribusi Bergeser (Drifted): {psi_drift:.5f}")
```

#### 7.2. Practical Example: Automated Inference Engine & Outlier Detection
Modul *production-ready* yang menggabungkan inferensi pengujian hipotesis adaptif, koreksi Benjamini-Hochberg, deteksi multivariat via *Fast Robust Mahalanobis Distance*, dan Arrow execution backend.

```python
"""Enterprise-Grade Statistical Verification and Anomaly Profiling Engine."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.covariance import MinCovDet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("StatisticalEngine")


class TestType(str, Enum):
    WELCH_T = "Welch_t_test"
    MANN_WHITNEY = "Mann_Whitney_U"
    KOLMOGOROV_SMIRNOV = "Kolmogorov_Smirnov"


@dataclass(frozen=True)
class HypothesisResult:
    feature_name: str
    test_used: TestType
    statistic: float
    raw_p_value: float
    adjusted_p_value: float
    is_significant: bool
    effect_size: float


@dataclass
class AnomalySummary:
    total_records: int
    anomalies_detected: int
    contamination_rate: float
    indices: np.ndarray


class EnterpriseStatisticalProfiler:
    """Mesin inferensi statistik produksi dengan toleransi kesalahan tingkat enterprise."""

    def __init__(
        self,
        significance_alpha: float = 0.05,
        fdr_method: str = "indep",
        random_state: int = 42,
    ) -> None:
        self.alpha = significance_alpha
        self.fdr_method = fdr_method
        self.random_state = random_state

    def evaluate_univariate_drift(
        self,
        baseline_df: pd.DataFrame,
        current_df: pd.DataFrame,
        numeric_columns: List[str],
    ) -> List[HypothesisResult]:
        """Menjalankan evaluasi drift fitur dinamis berdasarkan uji normalitas."""
        intermediate_results = []

        for col in numeric_columns:
            base_col = baseline_df[col].dropna().to_numpy(dtype=np.float64)
            curr_col = current_df[col].dropna().to_numpy(dtype=np.float64)

            if len(base_col) < 30 or len(curr_col) < 30:
                logger.warning(
                    "Ukuran sampel fitur '%s' terlalu kecil untuk inferensi reliabel.", col
                )
                continue

            # Uji Normalitas: D'Agostino-Pearson omnibus test
            _, p_norm_base = stats.normaltest(base_col)
            _, p_norm_curr = stats.normaltest(curr_col)

            is_normal = (p_norm_base > self.alpha) and (p_norm_curr > self.alpha)

            if is_normal:
                # Welch's t-test (tidak mengasumsikan varians kedua kelompok homogen)
                stat, p_val = stats.ttest_ind(base_col, curr_col, equal_var=False)
                test_type = TestType.WELCH_T
                # Cohen's d effect size
                pooled_std = np.sqrt(
                    ((len(base_col) - 1) * np.var(base_col, ddof=1) +
                     (len(curr_col) - 1) * np.var(curr_col, ddof=1)) /
                    (len(base_col) + len(curr_col) - 2)
                )
                effect = float(abs(np.mean(base_col) - np.mean(curr_col)) / (pooled_std + 1e-9))
            else:
                # Non-parametric: Mann-Whitney U test
                stat, p_val = stats.mannwhitneyu(base_col, curr_col, alternative="two-sided")
                test_type = TestType.MANN_WHITNEY
                # Rank-Biserial Correlation effect size
                n1, n2 = len(base_col), len(curr_col)
                u_val = stat
                effect = float(abs(1.0 - (2.0 * u_val) / (n1 * n2)))

            intermediate_results.append({
                "feature_name": col,
                "test_used": test_type,
                "statistic": float(stat),
                "raw_p_value": float(p_val),
                "effect_size": effect,
            })

        # Multiple Testing Correction: Benjamini-Hochberg (FDR)
        return self._apply_fdr_correction(intermediate_results)

    def _apply_fdr_correction(
        self, results: List[Dict[str, Union[str, float, TestType]]]
    ) -> List[HypothesisResult]:
        """Mengoreksi p-values menggunakan metode Benjamini-Hochberg."""
        if not results:
            return []

        p_vals = np.array([res["raw_p_value"] for res in results])
        m = len(p_vals)
        sorted_indices = np.argsort(p_vals)
        sorted_p_vals = p_vals[sorted_indices]

        # Kalkulasi ambang batas Benjamini-Hochberg
        q_values = np.empty(m, dtype=np.float64)
        cumulative_min = 1.0
        for i in range(m - 1, -1, -1):
            rank = i + 1
            calculated_q = (sorted_p_vals[i] * m) / rank
            cumulative_min = min(cumulative_min, calculated_q)
            q_values[i] = cumulative_min

        # Re-index q-values ke posisi semula
        adjusted_p_values = np.empty(m, dtype=np.float64)
        adjusted_p_values[sorted_indices] = np.clip(q_values, 0.0, 1.0)

        final_reports: List[HypothesisResult] = []
        for idx, res in enumerate(results):
            adj_p = adjusted_p_values[idx]
            final_reports.append(
                HypothesisResult(
                    feature_name=str(res["feature_name"]),
                    test_used=res["test_used"],  # type: ignore
                    statistic=float(res["statistic"]),
                    raw_p_value=float(res["raw_p_value"]),
                    adjusted_p_value=float(adj_p),
                    is_significant=bool(adj_p < self.alpha),
                    effect_size=float(res["effect_size"]),
                )
            )

        return final_reports

    def detect_multivariate_outliers(
        self,
        df: pd.DataFrame,
        features: List[str],
        contamination_rate: float = 0.01,
    ) -> AnomalySummary:
        """Mendeteksi anomali multivariat menggunakan Minimum Covariance Determinant (MCD)."""
        clean_matrix = df[features].dropna().to_numpy(dtype=np.float64)
        total_rows = len(clean_matrix)

        if total_rows < len(features) * 2:
            raise ValueError("Kondisi sampel data tidak mencukupi untuk robust covariance estimation.")

        # Minimum Covariance Determinant estimator
        mcd = MinCovDet(
            contamination=contamination_rate,
            random_state=self.random_state,
            support_fraction=0.75,
        )
        mcd.fit(clean_matrix)

        # Robust Mahalanobis Distances kuadrat
        robust_dist_sq = mcd.mahalanobis(clean_matrix)
        
        # Ambang batas teoritis distribusi Chi-Square untuk derajat kebebasan k = jumlah fitur
        degrees_of_freedom = len(features)
        cutoff_threshold = stats.chi2.ppf(1.0 - contamination_rate, df=degrees_of_freedom)

        outlier_mask = robust_dist_sq > cutoff_threshold
        outlier_indices = np.where(outlier_mask)[0]

        return AnomalySummary(
            total_records=total_rows,
            anomalies_detected=len(outlier_indices),
            contamination_rate=float(len(outlier_indices) / total_rows),
            indices=outlier_indices,
        )


if __name__ == "__main__":
    np.random.seed(1337)
    
    # 1. Bangun Baseline Data
    size_baseline = 10_000
    df_base = pd.DataFrame({
        "latensi_api": np.random.normal(120, 15, size_baseline),
        "payload_size": np.random.exponential(scale=50, size=size_baseline),
        "db_connections": np.random.poisson(lam=25, size=size_baseline).astype(float),
        "cpu_usage": np.random.normal(45, 5, size_baseline),
    })

    # 2. Bangun Current Production Data dengan simulasi drift & multivariat anomaly
    size_current = 5_000
    df_curr = pd.DataFrame({
        # Latensi bergeser signifikan secara statistik
        "latensi_api": np.random.normal(128, 18, size_current),
        # Payload size stabil (tidak ada drift struktural)
        "payload_size": np.random.exponential(scale=50.2, size=size_current),
        # Korelasi db_connections terdistorsi sedikit
        "db_connections": np.random.poisson(lam=25.2, size=size_current).astype(float),
        # CPU usage bergeser signifikan
        "cpu_usage": np.random.normal(52, 6, size_current),
    })

    # Sisipkan pencilan multivariat ekstrem secara tersembunyi
    df_curr.iloc[0:20, df_curr.columns.get_loc("latensi_api")] = 300.0
    df_curr.iloc[0:20, df_curr.columns.get_loc("cpu_usage")] = 95.0

    profiler = EnterpriseStatisticalProfiler(significance_alpha=0.01)

    print("=== HASIL UJI DRIFT DISTRIBUSI MULTIVARIAT ===")
    drift_results = profiler.evaluate_univariate_drift(
        baseline_df=df_base,
        current_df=df_curr,
        numeric_columns=["latensi_api", "payload_size", "db_connections", "cpu_usage"],
    )

    for res in drift_results:
        print(
            f"Fitur: {res.feature_name:<16} | Uji: {res.test_used.value:<18} | "
            f"p-val Mentah: {res.raw_p_value:.2e} | p-val Terkoreksi: {res.adjusted_p_value:.2e} | "
            f"Effect Size: {res.effect_size:<.4f} | Drift Signifikan: {res.is_significant}"
        )

    print("\n=== DETEKSI ANOMALI MULTIVARIAT (MCD MAHALANOBIS) ===")
    anomalies = profiler.detect_multivariate_outliers(
        df=df_curr,
        features=["latensi_api", "cpu_usage"],
        contamination_rate=0.01,
    )
    print(f"Total Observasi   : {anomalies.total_records}")
    print(f"Anomali Ditemukan : {anomalies.anomalies_detected}")
    print(f"Proporsi Kontaminasi: {anomalies.contamination_rate * 100:.2f}%")
    print(f"Sampel Indeks Anomali: {anomalies.indices[:10]}...")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Arsitektur Deteksi Drift Transaksi Fraud Gateway Bank Global
Sebuah platform sistem pemrosesan kartu kredit global memproses rata-rata $45.000$ transaksi per detik (TPS). Model deteksi fraud machine learning berbasis Gradient Boosting sangat bergantung pada stabilitas distribusi dari 120 fitur transaksi (seperti frekuensi gesek, rasio deviasi nominal transaksi terhadap rata-rata mingguan, geolocation displacement velocity).

#### Permasalahan:
Saat promosi tahunan *Black Friday*, terjadi lonjakan drastis transaksi yang tidak teratur. 
Pipeline analitik berbasis visual EDA standar di notebook Python gagal mendeteksi bahwa fitur `nominal_ratio_to_avg` telah bergeser sebesar $3.2$ standar deviasi. Akibatnya:
- Model machine learning memicu false positive masif.
- $12.000$ transaksi per menit pengguna sah terblokir.
- Kerugian finansial diperkirakan mencapai USD 2.4 Juta dalam 30 menit awal insiden.

#### Solusi yang Diimplementasikan:
1. **Stat-Gate Continuous Engine**: Dibangun engine inferensi batch per 5 menit yang menghitung metrik PSI dan Kolmogorov-Smirnov (KS) Test secara terdistribusi di PySpark dan Arrow.
2. **Koreksi FDR Terintegrasi**: Mengeliminasi 95% false alarms akibat ratusan pengujian simultan per jam.
3. **Decoupled Architecture**: Hasil pengujian dialirkan ke Kafka topic `statistical-telemetry`. Ketika PSI melampaui $0.20$, Kafka consumer menginstruksikan model serving layer beralih secara anggun (*graceful fallback*) ke skema ensemble berbasis *rule engine* konservatif, serentak memicu pipeline *automated retraining*.

```
   [ Streaming Transaksi (45k TPS) ]
                 │
                 ▼
     [ Apache Kafka Raw Topic ]
                 │
                 ▼
       [ Spark Streaming / Arrow ] ───(Tiap 5 Menit Window)───┐
                 │                                            │
                 ▼                                            ▼
   [ Normal Ingest to DB/Feature Store ]          [ Stat-Gate Engine ]
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                            │ PSI Calc & KS-Test via Vector SIMD│
                                            │ FDR Correction (Benjamini-H.)     │
                                            └─────────────────┬─────────────────┘
                                                              │
                                               Drift Detected? (PSI > 0.20)
                                                              │
                                            ┌─────────────────┴─────────────────┐
                                      YES   │                                   │  NO
                                            ▼                                   ▼
                              [ Trigger Circuit Breaker ]           [ Emit Metric: Normal ]
                              [ Switch Model -> Rules   ]           [ Prometheus/Grafana  ]
                              [ Post Alert to Opsgenie  ]
```

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                 COMPUTATIONAL COMPLEXITY & RUNTIME
                                 ▲
                                 │                 [Minimum Covariance Determinant]
                                 │                 O(n * p^3) High Precision Outlier
                                 │
                                 │       [Isolation Forest]
                                 │       O(n * t * log(s))
                                 │
     [Welch's t-test / KS-Test]  │
     O(n log n)                  │
                                 │
     [Quantile PSI Analysis]     │
     O(n) Linear                 │
                                 └────────────────────────────────────────►
                                 LOW                                  HIGH
                                             DETECTION FIDELITY / DRIFT RESOLUTION
```

| Pendekatan Algoritma | Latency Overhead | Memory Footprint | Keunggulan Enterprise | Kelemahan / Konsekuensi |
| :--- | :--- | :--- | :--- | :--- |
| **Parametric Test (Welch's t-test)** | Sangat Rendah ($\sim 1-5$ ms untuk $10^6$ baris) | Sangat Rendah ($O(1)$ auxiliary space) | Eksekusi tercepat, daya diskriminasi tinggi bila asumsi normalitas terpenuhi. | Memberikan hasil *misleading* berat bila data skew ekstrem atau bimodal. |
| **Non-Parametric (Mann-Whitney / KS)** | Menengah ($\sim 50-200$ ms) | Rendah hingga Sedang ($O(n)$ untuk sorting) | Bebas asumsi bentuk distribusi, sangat tangguh terhadap pencilan ekstrem. | Efisiensi statistik lebih rendah dibanding uji parametrik jika data benar normal. |
| **Robust Mahalanobis (FastMCD)** | Sangat Tinggi ($> 2.5$ detik untuk multivariat besar) | Tinggi ($O(p^2)$ matriks kovarians invers) | Mendeteksi interaksi tersembunyi (*swamping/masking effect*) antar banyak kolom. | Bottleneck komputasi masif jika fitur ($p$) lebih dari 50 dimensi. |
| **Population Stability Index (PSI)** | Rendah ($\sim 10-20$ ms) | Sangat Rendah (Fixed memory per quantile bucket) | Standar baku regulasi perbankan/Basel II, interpretasi mudah dipahami pemangku kepentingan. | Pilihan jumlah dan batasan binning dapat memanipulasi sensitivitas secara arbitrer. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Kesalahan Fatal: Eksekusi Uji Hipotesis Tanpa Memeriksa Skewness
Banyak data scientist langsung mengeksekusi Student's t-test atau ANOVA pada data transaksi berdistribusi Pareto/Power Law.
- **Gejala**: $p$-value mendekati 0 semu (*false positive* tinggi), model mendeteksi anomali yang sebenarnya hanyalah variabilitas ekor panjang (*fat-tail*).
- **Solusi**: Otomasi seleksi dengan D'Agostino-Pearson K-squared test (`scipy.stats.normaltest`). Bila parameter skewness melebihi ambang batas ($\pm 1.0$), delegasikan komputasi secara dinamis ke Mann-Whitney U atau Mood’s Median test.

#### 10.2. Mengabaikan Dynamic Range pada Kolom Kategori Berkardinalitas Tinggi
Pengujian Chi-Square $\chi^2$ gagal total jika terdapat sel dalam tabel kontingensi yang memiliki frekuensi observasi harapan (*expected frequency*) kurang dari 5:
- **Diagnostik**: Muncul peringatan `UserWarning: The degrees of freedom is too low...` atau `ValueError: zero element in matrix`.
- **Troubleshooting**: Lakukan pra-agregasi (kategori bernilai frekuensi di bawah persentil ke-5 dilebur menjadi kategori `'__OTHER__'`) sebelum membangun matriks tabel kontingensi.

#### 10.3. Memory Spikes Akibat Unnecessary Object Conversions
Mengubah DataFrame bertipe Arrow/NumPy kembali ke struktur Python standar:
```python
# ANTI-PATTERN (CRITICAL MEMORY OVERHEAD)
raw_p_values = [stats.ttest_ind(df[c].tolist(), ref[c].tolist()) for c in cols]

# ENTERPRISE VECTORIZED PATTERN
raw_p_values = stats.ttest_ind(
    df[cols].to_numpy(dtype=np.float64), 
    ref[cols].to_numpy(dtype=np.float64), 
    axis=0
)
```

---

### 11. Best Practices (Production Checklist)

- [ ] **Type Consistency & Immutability**: Terapkan `@dataclass(frozen=True)` pada seluruh keluaran laporan evaluasi statistik guna menjamin integritas audit pipeline.
- [ ] **Data Type Downcasting via Arrow**: Inisialisasi DataFrame memanfaatkan backend `engine="pyarrow"` pada Pandas 2.x untuk menghindari fragmentasi memori.
- [ ] **Out-of-Core Processing**: Gunakan generator chunking terikat ukuran buffer (`chunksize=100_000`) jika mengevaluasi berkas data historis Parquet berukuran puluhan gigabyte.
- [ ] **Controlling Multiple Comparison Problem**: Jangan pernah melaporkan p-value murni tanpa koreksi jika mengevaluasi lebih dari satu metrik/fitur sekaligus. Selalu terapkan *False Discovery Rate (FDR)* atau *Bonferroni*.
- [ ] **Decoupled Telemetry Logging**: Pisahkan eksekusi inferensi statistik dari penyimpanan hasil. Kirimkan matriks metrik ke *time-series storage* (seperti OpenTelemetry, InfluxDB, atau Prometheus) secara asinkron.
- [ ] **Strict Variance Floor Assertion**: Pastikan kolom ber-varians nol (*zero-variance*) disaring sebelum masuk ke evaluasi statistik untuk menghindari galat pembagian nol (`DivisionByZero`) pada estimasi kovarians.

---

### 12. Hands-on Practice

Buatlah direktori dan struktur modul enterprise pada ruang kerja lokal:
```bash
mkdir -p hands-on/m02/src
cd hands-on/m02
```

Simpan berkas berikut sebagai `hands-on/m02/src/statistical_engine.py`:

```python
"""hands-on/m02/src/statistical_engine.py
Komponen Pipeline Produksi: Automated Drift & Statistical Assertions
"""

import math
from typing import Dict, Any
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc


class StreamDataProfiler:
    """Profiler statistik berorientasi Arrow untuk pemrosesan streaming skala besar."""

    def __init__(self, significance_level: float = 0.01) -> None:
        self.alpha = significance_level

    def compute_summary_arrow(self, chunk: pa.RecordBatch) -> Dict[str, Dict[str, float]]:
        """Menghitung metrik ringkasan langsung di layer memori Arrow tanpa konversi ke Pandas."""
        summary = {}
        for col_name in chunk.schema.names:
            column = chunk.column(col_name)
            if pa.types.is_floating(column.type) or pa.types.is_integer(column.type):
                # Arrow Compute Kernel: C++ Level execution
                mean_val = pc.mean(column).as_py()
                std_val = pc.stddev(column).as_py()
                min_max = pc.min_max(column).as_py()
                
                summary[col_name] = {
                    "mean": float(mean_val) if mean_val is not None else 0.0,
                    "std": float(std_val) if std_val is not None else 0.0,
                    "min": float(min_max["min"]) if min_max["min"] is not None else 0.0,
                    "max": float(min_max["max"]) if min_max["max"] is not None else 0.0,
                }
        return summary


def run_pipeline() -> None:
    # 1. Alokasikan Apache Arrow Array secara native
    col_x = pa.array(np.random.normal(50, 10, 1_000_000))
    col_y = pa.array(np.random.uniform(0, 100, 1_000_000))
    batch = pa.RecordBatch.from_arrays([col_x, col_y], names=["sensor_x", "sensor_y"])

    # 2. Eksekusi Profiler
    profiler = StreamDataProfiler()
    metrics = profiler.compute_summary_arrow(batch)

    # 3. Output metrik
    print("Metrik Ringkasan Terkomputasi (Apache Arrow Native):")
    for sensor, metric_data in metrics.items():
        print(f" -> {sensor}: {metric_data}")


if __name__ == "__main__":
    run_pipeline()
```

Jalankan skrip:
```bash
python3 src/statistical_engine.py
```

---

### 13. Exercise

#### Level Easy
Implementasikan fungsi verifikasi independen `check_homoscedasticity(a: np.ndarray, b: np.ndarray) -> bool` menggunakan **Levene's Test** berbasis median (Brown-Forsythe modification). Kembalikan nilai `True` bila varians kedua kelompok homogen pada ambang batas signifikansi $\alpha = 0.05$.

#### Level Medium
Buat modul komputasi **Wasserstein Distance-1** (Earth Mover's Distance) secara paralel pada 10 fitur secara simultan menggunakan `concurrent.futures.ProcessPoolExecutor`. Validasi bahwa runtime tidak meningkat linier terhadap jumlah fitur numerik yang diuji.

#### Level Hard
Rancang dan bangun class pipeline `RobustMahalanobisFilter` yang menangani dataset dengan kondisi:
1. Kolom berkorelasi linear sempurna (*multicollinearity*, determinan matriks kovarians $\approx 0$).
2. Fitur memiliki skala satuan yang sangat berbeda (misal: nominal triliun rupiah vs rasio indeks desimal antara 0.0 - 1.0).
3. Pipeline harus menerapkan regularisasi Ledoit-Wolf shrinkage pada matriks kovarians secara otomatis jika kondisi matriks mengalami *ill-conditioning* (kondisi bilangan kondisi / *condition number* $> 1000$).

---

### 14. Challenge

#### Skenario: Arsitektur Self-Healing Ingestion Engine pada Sistem E-Commerce
Di platform e-commerce berskala multinasional, pipeline data ingest menerima data telemetri interaksi pengguna (durasi klik, impresi, nilai keranjang belanja) dalam format streaming Avro. 

**Tantangan Arsitektur Anda:**
1. Rancang modul arsitektur `StreamingDriftGovernor` berstatus *stateful* yang mempertahankan sliding window data historis selama 24 jam terakhir di dalam memori terbatas ($\le 512$ MB).
2. Modul harus mengevaluasi data stream per interval 15 menit menggunakan perpaduan **Wasserstein Distance** dan uji **Kolmogorov-Smirnov**.
3. Jika modul mendeteksi adanya *Severe Concept Drift* pada lebih dari 30% fitur utama:
   - Pipeline tidak boleh *crash*.
   - Pipeline secara deterministik memotong aliran masuk (*circuit breaking*).
   - Pipeline otomatis menerbitkan laporan diagnosis rinci berformat JSON ke S3 bucket khusus isolasi kegagalan (*quarantine zone*).
   - Pipeline mengalihkan downstream inferensi ke model *fallback* heuristik.
4. Kode harus sepenuhnya *thread-safe*, memiliki *type-annotations* lengkap tanpa mengorbankan performa (vektorisasi mutlak tanpa loop primitif).

---

### 15. Quiz Evaluasi Pemahaman

#### 5 Pertanyaan Basic
1. Apa perbedaan asumsial mendasar antara One-Sample Student's t-test dengan Welch's Two-Sample t-test?
2. Mengapa visualisasi Boxplot atau Histogram saja tidak cukup dijadikan bukti formal penentuan normalitas data di pipeline otomatis?
3. Apa risiko matematis langsung jika parameter $\epsilon$ (epsilon) diabaikan pada implementasi kalkulasi Population Stability Index (PSI)?
4. Sebutkan bentuk distribusi probabilitas acuan yang digunakan untuk membandingkan jarak kuadrat Mahalanobis saat menentukan batas anomali multivariat!
5. Apa interpretasi praktis dari nilai derajat stabilitas $PSI = 0.04$ pada fitur produksi bulanan?

#### 5 Pertanyaan Intermediate
1. Mengapa metode koreksi Benjamini-Hochberg (FDR) umumnya lebih disukai dalam pipeline deteksi drift skala besar dibanding metode Bonferroni?
2. Dalam kondisi seperti apa Mann-Whitney U Test menghasilkan simpulan yang tidak valid mengenai perbedaan median antara dua populasi?
3. Bagaimana fenomena *masking effect* dapat melumpuhkan metode deteksi pencilan multivariat standar, dan bagaimana algoritma Minimum Covariance Determinant (MCD) menanganinya?
4. Mengapa kalkulasi statistik berbasis Apache Arrow memory layer lebih hemat daya komputasi dibanding struktur berbasis pointer `PyObject` Pandas konvensional?
5. Bagaimana korelasi rank Kendall-Tau berbeda secara struktural dibanding korelasi Pearson ketika menganalisis hubungan non-linier monotonik?

#### 3 Skenario Kasus Produksi
1. **Skenario Kasus A**: Pipeline data scoring Anda mendeteksi bahwa nilai $p$-value untuk uji Kolmogorov-Smirnov pada suatu fitur nominal selalu bernilai $< 10^{-15}$ (sangat signifikan) setiap jamnya, namun visualisasi distribusi kumulatif aktual vs referensi hampir berhimpit sempurna. Apa akar masalah statistik yang mendasari fenomena ini (*Large Sample Size Effect*), dan apa metrik perbaikan yang harus diadopsi?
2. **Skenario Kasus B**: Sebuah dataset memiliki 45 variabel numerik. Ketika fungsi deteksi pencilan multivariat berbasis invers matriks kovarians dijalankan, sistem membangkitkan `LinAlgError: Singular Matrix`. Analisis langkah diagnostik Anda dan bagaimana pipeline harus memitigasi galat ini secara dinamis tanpa intervensi manual!
3. **Skenario Kasus C**: Tim MLOps mengeluhkan latensi pipeline validasi inferensi statistik melonjak dari 10 detik menjadi 45 menit saat volume data transaksi melonjak 10x lipat di akhir kuartal. Profiling menunjukkan bottleneck berada di uji Shapiro-Wilk dan pembuatan matriks scatter pair-plot. Rekomendasikan perombakan arsitektural total untuk menekan waktu eksekusi kembali ke bawah 60 detik!

---

### 16. Summary

- **Fondasi Inferensi Formal**: EDA tingkat enterprise menuntut otomasi analitik berbasis uji inferensial valid, bukan asumsi subjektif berbasis grafik visual interaktif.
- **Dynamic Routing**: Seleksi metode statistik (parametrik vs non-parametrik) wajib diarahkan secara programatis melalui verifikasi prasyarat distribusi (*normality*, *homoscedasticity*) secara dinamis.
- **Multiple Comparison Mitigation**: Menjalankan evaluasi drift secara simultan pada puluhan hingga ratusan fitur tanpa koreksi Family-Wise Error Rate (seperti Benjamini-Hochberg FDR) menjamin terciptanya *false alarms* yang merusak integritas otomatisasi data.
- **Multivariate Over Univariate**: Deteksi anomali multivariat mempertimbangkan struktur dependensi antar dimensi variabel; penggunaan algoritma robust seperti *Minimum Covariance Determinant* mengisolasi anomali yang lolos dari pemfilteran berbasis margin tunggal (*univariate thresholding*).
- **Efficiency through Arrow Engine**: Pemrosesan statistik terdistribusi pada data berskala enterprise mensyaratkan pemanfaatan arsitektur memori modern (*Apache Arrow Columnar format*), menghindari *memory footprint* berlebih demi kestabilan pipeline berkapasitas throughput tinggi.