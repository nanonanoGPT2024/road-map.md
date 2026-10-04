# Bab 06: Applied Statistics & Experimentation
## Modul 01: Enterprise A/B Testing, Inferensi Kausal, dan Variance Reduction (CUPED)

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang Desain Eksperimen Formal:** Menentukan ukuran sampel minimum ($n$) dan batas Minimum Detectable Effect (MDE) berdasarkan batas Statistical Power ($1-\beta = 0.80$ atau $0.90$) dan Type I Error rate ($\alpha = 0.05$) untuk metrik bertipe kontinu maupun biner.
- **Mendeteksi Bias Alokasi dengan Chi-Square Test:** Mengidentifikasi *Sample Ratio Mismatch* (SRM) secara otomatis pada pipeline analitik sebelum inferensi metrik dievaluasi.
- **Mengimplementasikan Algoritma CUPED (Controlled-experiment using Pre-Experiment Data):** Mengurangi variansi metrik target hingga 30–50% menggunakan kovariat historis, yang secara langsung mempercepat runtime eksperimen atau memperkecil MDE tanpa menambah volume traffic.
- **Menjalankan Inferensi Hipotesis Robust:** Mengeksekusi Welch’s t-test (mengakomodasi *heteroskedasticity*) dan bootstrap inferensial pada distribusi *heavy-tailed/skewed*, lengkap dengan koreksi *Multiple Hypothesis Testing* (Family-Wise Error Rate via Bonferroni & False Discovery Rate via Benjamini-Hochberg).
- **Membangun Statistical Experimentation Engine Terintegrasi:** Mengembangkan modul Python *production-grade* berarsitektur bersih (*clean architecture*), *type-hinted*, defensif terhadap edge cases, dan siap diintegrasikan ke orkestrasi data (Airflow, Dagster, atau Prefect).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Eksperimentasi online (A/B testing) pada ekosistem enterprise bukanlah sekadar menghitung persentase perubahan rata-rata ($\Delta\%$) antara grup kontrol ($A$) dan varian ($B$). A/B testing adalah kerangka kerja **inferensi kausal (causal inference)** di bawah model stokastik. 

```
Mental Model: Neyman-Rubin Causal Model
Untuk setiap unit pengamatan i:
  - Y_i(1) : Potensi metrik jika unit terpapar treatment (Varian)
  - Y_i(0) : Potensi metrik jika unit terpapar kontrol (Kontrol)

Efek Treatment Kausal Individu:
  τ_i = Y_i(1) - Y_i(0)  [Fundamental Problem of Causal Inference: Kita hanya mengamati salah satu!]

Average Treatment Effect (ATE):
  ATE = E[Y(1) - Y(0)] = E[Y | Treatment = 1] - E[Y | Treatment = 0] (jika random assignment valid)
```

Proses A/B testing modern terdiri dari empat pilar inferensial:
1. **Randomization Engine:** Menjamin independensi alokasi $T \perp \! \! \! \perp (Y(0), Y(1))$, menghapus bias seleksi dan variabel pengganggu (*confounders*).
2. **Data Integrity Gate (SRM Test):** Validasi apakah rasio unit yang teralokasi sesuai dengan proporsi rancangan awal ($1:1$, $2:1$, dst.). Kegagalan uji ini membatalkan validitas kausalitas seluruh eksperimen.
3. **Variance Reduction (CUPED):** Pemanfaatan kovariat pre-eksperimen untuk mengisolasi variansi alamiah pengguna dari variansi yang diinduksi oleh eksperimen itu sendiri.
4. **Hypothesis Testing & Statistical Correction:** Menilai apakah perbedaan teramati $\hat{\tau}$ secara statistik berbeda dari 0 secara signifikan tanpa terjebak *p-hacking* atau inflasi false positive akibat metrik majemuk (*multiple testing*).

---

### 3. Why It Matters (Konteks Enterprise & Dampak Produksi)

Di platform berskala besar (e-commerce, ride-hailing, dynamic SaaS, platform AI Agent):
- **Biaya Kesalahan Type I (False Positive):** Menerapkan model ranking atau optimasi UI yang seolah-olah meningkatkan Gross Merchandise Value (GMV), padahal hanya fluktuasi acak. Akibatnya, tim menghabiskan sumber daya infrastruktur tanpa ada nilai riil.
- **Biaya Kesalahan Type II (False Negative):** Menolak algoritma rekomendasi baru yang sebenarnya meningkatkan retensi sebesar 1.5% hanya karena sampel pengujian tidak memiliki *power* yang cukup untuk mendeteksi efek tersebut.
- **Keterbatasan Runtime & Traffic Allocation:** Menjalankan eksperimen selama berminggu-minggu demi mengumpulkan sampel berisiko mengorbankan pengalaman pengguna (*user experience drag*). Variance reduction via CUPED memungkinkan waktu eksperimen dipangkas dari misal 4 minggu menjadi 2 minggu, melipatgandakan *experimentation velocity* perusahaan.
- **Integritas AI & Autonomous Agents:** Ketika menguji performa LLM agent (misalnya: variasi prompt, arsitektur RAG, *routing policy*), metrik token efficiency dan task success rate memiliki variansi ekstrem. Analisis statistik konvensional tanpa *sample sizing*, penanganan *skewness*, dan *multiple-testing correction* menghasilkan deployment model agent yang tidak stabil dan rentan degradasi performa di lingkungan produksi.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut memetakan perjalanan data dari pipeline ingestion event hingga penetapan keputusan kausal dalam arsitektur experimentation modern:

```
[User Traffic / Agent Interaction]
                 │
                 ▼
     [Deterministic Hashing] ────────► MurmurHash3(user_id + salt_experiment)
                 │
        ┌────────┴────────┐
        ▼                 ▼
   [Control (A)]     [Treatment (B)]
        │                 │
        └────────┬────────┘
                 ▼
     [Telemetry & Log Aggregator]
                 │
                 ▼
   ┌───────────────────────────────┐
   │  EXPERIMENTATION PIPELINE     │
   │                               │
   │  1. Ingestion & Pre-agg       │
   │     - Pre-treatment metrics   │
   │     - Post-treatment metrics  │
   │                               │
   │  2. Integrity Check (SRM)     │
   │     - Chi-Square Goodness-Fit │
   │     - p-value < 0.001?        │
   │        ├─► YES: ABORT (Bias)  │
   │        └─► NO: CONTINUE       │
   │                               │
   │  3. CUPED Engine              │
   │     - Compute Covariance      │
   │     - Adjust Y -> Y_cuped     │
   │                               │
   │  4. Hypothesis Evaluation     │
   │     - Welch's t-test / MDE    │
   │     - Multiple Testing Corr   │
   │       (Bonferroni / BH)       │
   └───────────────┬───────────────┘
                   │
                   ▼
     [Decision / Rollout Engine]
    (Deploy Varian / Rollback / Iterate)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Power Analysis & Minimum Detectable Effect (MDE)

Formula baku penentuan ukuran sampel per grup ($n$) pada uji dua arah (*two-tailed test*) dengan variansi identik $\sigma^2$:

$$n = \frac{2 \cdot (Z_{\alpha/2} + Z_{\beta})^2 \cdot \sigma^2}{\delta^2}$$

Di mana:
- $\alpha$: Tingkat signifikansi (standar: 0.05, menghasilkan $Z_{0.025} \approx 1.96$).
- $\beta$: Probabilitas Type II error (standar: 0.20, sehingga statistical power $1-\beta = 0.80$, menghasilkan $Z_{0.20} \approx 0.8416$).
- $\sigma^2$: Variansi dari metrik dasar (dihitung dari data historis).
- $\delta$: Minimum Detectable Effect absolut ($|\mu_B - \mu_A|$).

Jika metrik bertipe proporsi biner (seperti Click-Through Rate atau Conversion Rate), dengan baseline proporsi $p$:
$$\sigma^2 = p(1-p)$$

#### B. Deteksi Sample Ratio Mismatch (SRM) Menggunakan Chi-Square

SRM terjadi ketika rasio sampel teramati ($O_A, O_B$) menyimpang secara signifikan dari rasio teoritis yang diharapkan ($E_A, E_B$). Statistik ujinya:

$$\chi^2 = \sum_{i \in \{A, B\}} \frac{(O_i - E_i)^2}{E_i}$$

Dengan derajat kebebasan (*degrees of freedom*) $df = k - 1 = 1$. Jika nilai $p$-value dari distribusi $\chi^2$ kurang dari ambang batas konservatif (biasanya $\alpha_{SRM} = 0.001$), maka asumsi alokasi terdistribusi acak terlanggar. Penyebab umumnya: alokasi treatment memicu *crash*, *redirect latency*, bot filtering tidak simetris, atau hashing imbalance.

#### C. Mekanisme Variance Reduction: Algoritma CUPED

Dikembangkan oleh tim pengembang Microsoft (Deng et al., 2013), CUPED memanfaatkan metrik baseline ($X$) yang diukur **sebelum** unit masuk ke dalam eksperimen untuk memprediksi dan membuang variansi alami dari metrik outcome ($Y$).

Didefinisikan estimator metrik baru yang telah disesuaikan:

$$\hat{Y}_{CUPED} = Y - \theta (X - E[X])$$

Agar $Var(\hat{Y}_{CUPED})$ minimum, kita turunkan terhadap $\theta$ dan samakan dengan nol:

$$\frac{d}{d\theta} Var(Y - \theta X) = \frac{d}{d\theta} [Var(Y) - 2\theta Cov(Y, X) + \theta^2 Var(X)] = 0$$

$$-2 Cov(Y, X) + 2\theta Var(X) = 0 \implies \theta^* = \frac{Cov(Y, X)}{Var(X)}$$

Variansi tereduksi menjadi:

$$Var(\hat{Y}_{CUPED}) = Var(Y) \cdot (1 - \rho^2)$$

Di mana $\rho$ adalah koefisien korelasi Pearson antara $X$ dan $Y$.
- Jika $\rho = 0.5$, variansi berkurang $25\%$ ($1 - 0.25 = 0.75$).
- Jika $\rho = 0.7$, variansi berkurang $49\%$ ($1 - 0.49 = 0.51$). Penurunan variansi sebesar 50% ekuivalen secara matematis dengan menggandakan ukuran sampel eksperimen Anda secara gratis.

#### D. Inferensi Hipotesis: Welch's t-test

Karena variansi di grup kontrol ($s_A^2$) dan varian ($s_B^2$) jarang sekali identik di dunia nyata (terutama jika treatment mengubah persebaran data), Welch's t-test digunakan alih-alih Student's t-test standar:

$$t = \frac{\bar{Y}_B - \bar{Y}_A}{\sqrt{\frac{s_A^2}{n_A} + \frac{s_B^2}{n_B}}}$$

Derajat kebebasan disesuaikan via formulasi Welch-Satterthwaite:

$$\nu \approx \frac{\left(\frac{s_A^2}{n_A} + \frac{s_B^2}{n_B}\right)^2}{\frac{\left(\frac{s_A^2}{n_A}\right)^2}{n_A - 1} + \frac{\left(\frac{s_B^2}{n_B}\right)^2}{n_B - 1}}$$

#### E. Multiple Testing Correction: Benjamini-Hochberg (FDR)

Saat mengevaluasi beberapa metrik secara simultan ($m$ hipotesis), probabilitas setidaknya satu false positive melonjak drastis:

$$\alpha_{overall} = 1 - (1 - \alpha)^m$$

Untuk mengontrol False Discovery Rate (FDR) pada level $Q$:
1. Urutkan seluruh nilai $p$-value dari kecil ke besar: $P_{(1)} \le P_{(2)} \le \dots \le P_{(m)}$.
2. Temukan indeks terbesar $k$ sedemikian rupa sehingga:
   $$P_{(k)} \le \frac{k}{m} \cdot Q$$
3. Tolak seluruh $H_0$ untuk indeks $i = 1, 2, \dots, k$.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi experimentation engine terintegrasi menggunakan Python. Kode ini mencakup Power Analysis, deteksi SRM, penyesuaian CUPED, Welch's t-test, dan FDR Correction.

```python
"""
Enterprise Experimentation Engine
Modul: Applied Statistics & Causal Inference
Deskripsi: Engine komprehensif untuk SRM validation, kalkulasi CUPED, 
           dan inferensi hipotesis Welch's t-test dengan FDR control.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class PowerAnalysisConfig:
    alpha: float = 0.05
    power: float = 0.80
    two_tailed: bool = True


@dataclass(frozen=True)
class TestResult:
    metric_name: str
    control_mean: float
    treatment_mean: float
    absolute_lift: float
    relative_lift_pct: float
    p_value: float
    p_value_adjusted: float
    statistically_significant: bool
    confidence_interval_95: Tuple[float, float]
    variance_reduction_pct: float


class StatisticalExperimentationEngine:
    def __init__(self, random_state: Optional[int] = 42) -> None:
        if random_state is not None:
            np.random.seed(random_state)

    @staticmethod
    def calculate_sample_size(
        baseline_mean: float,
        baseline_std: float,
        mde_relative: float,
        config: PowerAnalysisConfig = PowerAnalysisConfig(),
    ) -> int:
        """
        Menghitung estimasi ukuran sampel per varian menggunakan formula normal approximation.
        """
        if baseline_std <= 0:
            raise ValueError("Standard deviation historis harus bernilai positif.")
        if mde_relative <= 0:
            raise ValueError("Minimum Detectable Effect (relatif) harus lebih besar dari 0.")

        delta = baseline_mean * mde_relative
        z_alpha = stats.norm.ppf(1 - config.alpha / 2 if config.two_tailed else 1 - config.alpha)
        z_beta = stats.norm.ppf(config.power)

        sample_size_per_variant = (2 * ((z_alpha + z_beta) ** 2) * (baseline_std**2)) / (delta**2)
        return int(np.ceil(sample_size_per_variant))

    @staticmethod
    def validate_sample_ratio_mismatch(
        n_control: int,
        n_treatment: int,
        expected_ratio: Tuple[float, float] = (0.5, 0.5),
        alpha_threshold: float = 0.001,
    ) -> Tuple[bool, float]:
        """
        Evaluasi Sample Ratio Mismatch (SRM) via Goodness-of-Fit Chi-Square Test.
        Returns:
            Tuple[is_srm_detected: bool, p_value: float]
        """
        total_observed = n_control + n_treatment
        if total_observed == 0:
            raise ValueError("Total observed users tidak boleh bernilai nol.")

        norm_weights = np.array(expected_ratio) / np.sum(expected_ratio)
        expected_counts = total_observed * norm_weights
        observed_counts = np.array([n_control, n_treatment])

        chi2_stat = np.sum(((observed_counts - expected_counts) ** 2) / expected_counts)
        p_val = float(1.0 - stats.chi2.cdf(chi2_stat, df=1))

        # SRM terdeteksi bila probabilitas terjadinya observasi ini sangat langka (p < alpha_threshold)
        is_srm = p_val < alpha_threshold
        return is_srm, p_val

    @staticmethod
    def apply_cuped(
        df: pd.DataFrame,
        variant_col: str,
        metric_col: str,
        pre_experiment_metric_col: str,
    ) -> Tuple[pd.Series, float]:
        """
        Menerapkan transformasi CUPED untuk mereduksi variansi pada metric_col.
        Returns:
            Tuple[adjusted_metric_series, variance_reduction_percentage]
        """
        # Validasi kolom
        for col in [variant_col, metric_col, pre_experiment_metric_col]:
            if col not in df.columns:
                raise KeyError(f"Kolom '{col}' tidak ditemukan dalam dataframe input.")

        # Ambil data valid (dropna untuk kestabilan kalkulasi kovariansi)
        valid_mask = df[metric_col].notna() & df[pre_experiment_metric_col].notna()
        sub_df = df[valid_mask]

        cov_matrix = np.cov(sub_df[metric_col], sub_df[pre_experiment_metric_col])
        var_x = cov_matrix[1, 1]
        cov_y_x = cov_matrix[0, 1]

        if var_x == 0:
            # Tidak ada variasi di metrik historis, tidak ada reduksi yang dapat dicapai
            return df[metric_col], 0.0

        theta = cov_y_x / var_x
        mean_x = sub_df[pre_experiment_metric_col].mean()

        cuped_metric = df[metric_col] - theta * (df[pre_experiment_metric_col] - mean_x)

        # Hitung persentase penurunan variansi
        var_y_original = np.var(sub_df[metric_col], ddof=1)
        var_y_cuped = np.var(cuped_metric[valid_mask], ddof=1)
        
        reduction_pct = 0.0
        if var_y_original > 0:
            reduction_pct = max(0.0, (1.0 - (var_y_cuped / var_y_original)) * 100.0)

        return cuped_metric, reduction_pct

    @staticmethod
    def welch_t_test(
        control_values: np.ndarray,
        treatment_values: np.ndarray,
        alpha: float = 0.05,
    ) -> Tuple[float, float, Tuple[float, float]]:
        """
        Menjalankan Welch's Two-Sample t-test (tidak berasumsi variansi identik).
        Returns:
            Tuple[lift_absolut, p_value, confidence_interval_95]
        """
        n_ctrl = len(control_values)
        n_trt = len(treatment_values)

        if n_ctrl < 2 or n_trt < 2:
            raise ValueError("Setiap varian harus memiliki minimal 2 observasi.")

        mean_ctrl = np.mean(control_values)
        mean_trt = np.mean(treatment_values)
        var_ctrl = np.var(control_values, ddof=1)
        var_trt = np.var(treatment_values, ddof=1)

        lift = mean_trt - mean_ctrl
        se_diff = np.sqrt((var_ctrl / n_ctrl) + (var_trt / n_trt))

        if se_diff == 0:
            return lift, 1.0, (lift, lift)

        t_stat = lift / se_diff

        # Derajat kebebasan Welch-Satterthwaite
        df_numerator = ((var_ctrl / n_ctrl) + (var_trt / n_trt)) ** 2
        df_denominator = (((var_ctrl / n_ctrl) ** 2) / (n_ctrl - 1)) + (
            ((var_trt / n_trt) ** 2) / (n_trt - 1)
        )
        df_welch = df_numerator / df_denominator

        p_value = 2.0 * float(1.0 - stats.t.cdf(np.abs(t_stat), df=df_welch))

        critical_value = stats.t.ppf(1.0 - (alpha / 2.0), df=df_welch)
        ci_lower = lift - critical_value * se_diff
        ci_upper = lift + critical_value * se_diff

        return lift, p_value, (float(ci_lower), float(ci_upper))

    @classmethod
    def apply_benjamini_hochberg(
        cls, results: List[Dict[str, float]], fdr_q: float = 0.05
    ) -> List[Dict[str, float]]:
        """
        Koreksi nilai p-value menggunakan prosedur Benjamini-Hochberg (FDR).
        """
        m = len(results)
        if m == 0:
            return results

        # Ekstraksi indeks awal untuk menjaga urutan output
        sorted_indices = sorted(range(m), key=lambda i: results[i]["p_value"])
        adjusted_p_values = [0.0] * m

        # Kalkulasi step-up adjusted p-values
        running_min = 1.0
        for rank, idx in reversed(list(enumerate(sorted_indices, start=1))):
            current_p = results[idx]["p_value"]
            adjusted = (current_p * m) / rank
            running_min = min(running_min, adjusted)
            adjusted_p_values[idx] = min(running_min, 1.0)

        # Update dictionary hasil
        for i in range(m):
            results[i]["p_value_adjusted"] = adjusted_p_values[i]
            results[i]["statistically_significant"] = adjusted_p_values[i] <= fdr_q

        return results

    def analyze_experiment(
        self,
        df: pd.DataFrame,
        variant_col: str,
        metrics: List[str],
        pre_experiment_metrics: Optional[Dict[str, str]] = None,
        control_label: str = "A",
        treatment_label: str = "B",
        alpha: float = 0.05,
    ) -> List[TestResult]:
        """
        Pipeline lengkap: Validasi SRM -> CUPED Adjustment -> Welch's t-test -> BH Correction.
        """
        ctrl_mask = df[variant_col] == control_label
        trt_mask = df[variant_col] == treatment_label

        n_ctrl = int(ctrl_mask.sum())
        n_trt = int(trt_mask.sum())

        # Langkah 1: Evaluasi Data Integrity (SRM)
        is_srm, srm_p_val = self.validate_sample_ratio_mismatch(n_ctrl, n_trt)
        if is_srm:
            raise RuntimeError(
                f"Data Integrity Failure: Sample Ratio Mismatch terdeteksi! "
                f"(Observed Control: {n_ctrl}, Treatment: {n_trt}, Chi2 p-value: {srm_p_val:.6f}). "
                f"Eksperimen dibatalkan untuk mencegah false inference."
            )

        intermediate_evals = []

        # Langkah 2: Proses setiap metrik
        for metric in metrics:
            metric_to_analyze = metric
            reduction_pct = 0.0

            if pre_experiment_metrics and metric in pre_experiment_metrics:
                pre_metric = pre_experiment_metrics[metric]
                cuped_col, reduction_pct = self.apply_cuped(df, variant_col, metric, pre_metric)
                cuped_metric_name = f"{metric}_cuped"
                df[cuped_metric_name] = cuped_metric
                metric_to_analyze = cuped_metric_name

            y_ctrl = df.loc[ctrl_mask, metric_to_analyze].dropna().to_numpy()
            y_trt = df.loc[trt_mask, metric_to_analyze].dropna().to_numpy()

            mean_ctrl = float(np.mean(y_ctrl))
            mean_trt = float(np.mean(y_trt))
            lift_abs, p_val, ci_95 = self.welch_t_test(y_ctrl, y_trt, alpha=alpha)

            rel_lift_pct = (lift_abs / mean_ctrl * 100.0) if mean_ctrl != 0 else 0.0

            intermediate_evals.append(
                {
                    "metric_name": metric,
                    "control_mean": mean_ctrl,
                    "treatment_mean": mean_trt,
                    "absolute_lift": lift_abs,
                    "relative_lift_pct": rel_lift_pct,
                    "p_value": p_val,
                    "confidence_interval_95": ci_95,
                    "variance_reduction_pct": reduction_pct,
                }
            )

        # Langkah 3: Multiple Testing Correction
        adjusted_evals = self.apply_benjamini_hochberg(intermediate_evals, fdr_q=alpha)

        # Langkah 4: Format ke dataclass output
        final_results = [
            TestResult(
                metric_name=res["metric_name"],
                control_mean=res["control_mean"],
                treatment_mean=res["treatment_mean"],
                absolute_lift=res["absolute_lift"],
                relative_lift_pct=res["relative_lift_pct"],
                p_value=res["p_value"],
                p_value_adjusted=res["p_value_adjusted"],
                statistically_significant=res["statistically_significant"],
                confidence_interval_95=res["confidence_interval_95"],
                variance_reduction_pct=res["variance_reduction_pct"],
            )
            for res in adjusted_evals
        ]

        return final_results


if __name__ == "__main__":
    # Smoke test & Verifikasi Pipeline
    print("=== Pipeline Verification Test ===")
    np.random.seed(1337)
    sample_size = 5000

    # Simulasi Pre-Experiment Metric (X) dan Korelasi Kuat dengan Target (Y)
    pre_spend = np.random.gamma(shape=2.0, scale=25.0, size=sample_size)
    noise = np.random.normal(loc=0.0, scale=10.0, size=sample_size)

    # Treatment menginduksi True Lift sebesar +$3.5
    variant_alloc = np.random.choice(["A", "B"], size=sample_size, p=[0.5, 0.5])
    treatment_effect = np.where(variant_alloc == "B", 3.5, 0.0)
    current_spend = 0.8 * pre_spend + treatment_effect + noise

    mock_df = pd.DataFrame(
        {
            "user_id": np.arange(sample_size),
            "variant": variant_alloc,
            "pre_spend": pre_spend,
            "post_spend": current_spend,
        }
    )

    engine = StatisticalExperimentationEngine()
    results = engine.analyze_experiment(
        df=mock_df,
        variant_col="variant",
        metrics=["post_spend"],
        pre_experiment_metrics={"post_spend": "pre_spend"},
        alpha=0.05,
    )

    for r in results:
        print(f"Metric Analyzed          : {r.metric_name}")
        print(f"Variance Reduction via CUPED: {r.variance_reduction_pct:.2f}%")
        print(f"Control Mean            : {r.control_mean:.3f}")
        print(f"Treatment Mean          : {r.treatment_mean:.3f}")
        print(f"Absolute Lift           : {r.absolute_lift:.3f}")
        print(f"Relative Lift           : {r.relative_lift_pct:.2f}%")
        print(f"p-value (Raw / Adjusted): {r.p_value:.5e} / {r.p_value_adjusted:.5e}")
        print(f"95% Confidence Interval : [{r.confidence_interval_95[0]:.3f}, {r.confidence_interval_95[1]:.3f}]")
        print(f"Significant (FDR q=0.05): {r.statistically_significant}")
```

---

### 7. Edge Cases & Failure Modes

Pada production data pipeline, asumsi statistik ideal sering terlanggar. Berikut adalah failure modes yang wajib dimitigasi:

1. **Extreme Outliers / Fat-Tailed Distributions (Power-Law Spends):**
   - *Failure:* GMV dan metrik revenue sering didominasi oleh segelintir *whales* ($0.1\%$ user menyumbang $50\%$ GMV). Welch's t-test mengalami breakdown karena Central Limit Theorem (CLT) melambat secara drastis pada skewness ekstrem.
   - *Mitigasi:* Gunakan teknik **Winsorization** (memotong nilai ekstrem di atas persentil ke-99 atau ke-99.9) atau log-transformasikan target metrik: $Y' = \ln(1 + Y)$. Opsi alternatif non-parametrik: evaluasi via **Empirical Bootstrap** confidence interval.

2. **Zero Pre-Experiment Covariate Data (Cold Start Problem):**
   - *Failure:* Pengguna baru yang mendaftar selama eksperimen berjalan tidak memiliki riwayat data pre-experiment ($X$ bernilai null atau 0).
   - *Mitigasi:* Terapkan kalkulasi CUPED berlapis (*segmented CUPED*). Untuk user lama, hitung estimasi menggunakan $\theta^*$. Untuk user baru, set $X = \bar{X}_{cohort}$ atau lewati penyesuaian CUPED ($Y_{CUPED} = Y$) khusus subset tersebut secara transparan.

3. **Multiple Testing Inflations (Metrics Fishing / P-Hacking):**
   - *Failure:* Product manager mengevaluasi 40 metrik sekunder secara bersamaan tanpa koreksi, menemukan 2 metrik dengan $p < 0.05$, lalu menyatakan eksperimen sukses.
   - *Mitigasi:* Tetapkan klasifikasi hierarkis: 1 Primary Metric, 2-3 Guardrail Metrics, dan sisanya Exploratory Metrics. Terapkan algoritma penyesuaian **Benjamini-Hochberg (FDR)** atau **Holm-Bonferroni** secara deterministik pada pipeline pelaporan.

4. **Continuous Peeking / Optional Stopping:**
   - *Failure:* Analis mengecek dashboard pengujian setiap hari dan menghentikan eksperimen tepat saat metrik menyentuh signifikansi $p < 0.05$. Hal ini melipatgandakan False Positive Rate hingga $>30\%$.
   - *Mitigasi:* Kunci horizon waktu eksperimen sesuai kalkulasi *sample size* awal, atau ubah uji inferensi menggunakan metodologi **Sequential Testing** (*Always Valid p-values* berbasis mixture Sequential Probability Ratio Test / mSPRT).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | Frequentist Fixed-Horizon (Welch + CUPED) | Bayesian A/B Testing | Multi-Armed Bandit (Thompson Sampling / UCB) | Sequential Testing (mSPRT) |
| :--- | :--- | :--- | :--- | :--- |
| **Kecepatan Optimasi** | Moderat (harus menunggu ukuran sampel terpenuhi penuh) | Moderat hingga Tinggi | **Sangat Cepat** (dinamis mengalihkan traffic ke pemenang) | Fleksibel (bisa early stop kapan saja) |
| **Regret Minimization** | Buruk (mengalokasikan 50% traffic ke varian kalah selama tes) | Buruk | **Unggul** (meminimalkan eksposur varian buruk secara adaptif) | Baik |
| **Kausalitas Bersih** | **Tinggi & Baku** (Standar audit ilmiah, ATE tidak bias) | Tinggi (memberikan posterior probability of being best) | Lemah (eksploitasi dinamis mengaburkan estimasi ATE unbiased) | Tinggi (disesuaikan terhadap *optional stopping*) |
| **Kebutuhan Komputasi** | Rendah (O(N) agregasi matematis sederhana) | Tinggi (MCMC sampling atau variasi conjugate priors) | Moderat (update posterior state secara real-time) | Rendah-Moderat (komputasi per batch harian) |
| **Ideal Digunakan Untuk** | Core business changes, pricing experiments, AI core model swaps | Pelaporan berbasis risiko bisnis ("Peluang B lebih baik dari A sebesar 92%") | Optimasi banner kampanye musiman, ad serving, quick dynamic routing | Eksperimen metrik sensitif keamanan di mana early abort diperlukan bila ada penurunan drastis |

---

### 9. Best Practices & Standar Industri

- **Pre-Experiment Hash Bucketing:** Gunakan algoritma hashing non-kriptografis berkecepatan tinggi dengan uniform distribution teruji, seperti `MurmurHash3` atau `xxHash`, dikombinasikan dengan unique experiment salt:
  $$\text{bucket} = \text{MurmurHash3}(\text{user\_uuid} + \text{"\_exp\_churn\_mitigation\_2026"}) \pmod{100}$$
- **Guardrail Metrics Enforcement:** Jangan pernah meluncurkan varian yang memenangkan metrik konversi primer jika melanggar guardrail metrics (misal: p99 Latency meningkat $>10\%$, client error rate $>0.01\%$, atau churn request meningkat).
- **Validasi Pre-Treatment Flatness (A/A Testing):** Jalankan simulasi A/A test harian menggunakan data historis untuk memverifikasi bahwa false positive rate engine empiris Anda berada tepat di kisaran target $\alpha = 0.05$.
- **Audit Data Pipeline untuk SRM:** Log alokasi penugasan varian di sisi *server-side* sedekat mungkin dengan trigger event guna mencegah bias *network dropped-connection* di sisi klien (*client-side SDK drop*).

---

### 10. Hands-on Lab Exercise: Implementasi End-to-End A/B Analysis Pipeline

#### Skenario Lab
Anda adalah Senior Data Analyst pada autonomous agent workspace platform. Platform baru saja meluncurkan model perutean konteks (*context routing optimization*) untuk AI Agent (Varian B) dibandingkan dengan naive prompting (Kontrol A). Metrik utamanya adalah **Agent Completion Cost per Session (USD)** (target: menurun) dan metrik pre-treatment adalah **Baseline Average Spend per Session**.

Jalankan langkah-langkah analitik berikut di notebook atau script Python Anda:

#### Langkah 1: Persiapan Environment & Pembuatan Dataset Sintesis
```python
import numpy as np
import pandas as pd

np.random.seed(42)
N = 10000

# 1. Generate User IDs
user_ids = [f"usr_{i:06d}" for i in range(N)]

# 2. Pre-experiment Metric (Cost baseline historis per user, terdistribusi log-normal)
pre_cost = np.random.lognormal(mean=1.5, sigma=0.5, size=N)

# 3. Alokasi 50:50 dengan simulasi sedikit noise
variants = np.random.choice(["A", "B"], size=N, p=[0.50, 0.50])

# 4. Model Treatment Effect: Varian B memangkas biaya sebesar 8% + noise
# Outcome terikat kuat dengan historical spend user (korelasi tinggi)
treatment_multiplier = np.where(variants == "B", 0.92, 1.00)
post_cost = (pre_cost * treatment_multiplier) + np.random.normal(loc=0.0, scale=0.5, size=N)
post_cost = np.clip(post_cost, a_min=0.01, a_max=None) # Biaya tidak boleh negatif

df_experiment = pd.DataFrame({
    "user_id": user_ids,
    "assigned_variant": variants,
    "pre_experiment_cost": pre_cost,
    "post_experiment_cost": post_cost
})

print("Dataset Preview:")
print(df_experiment.head())
```

#### Langkah 2: Audit Sample Ratio Mismatch (SRM)
```python
engine = StatisticalExperimentationEngine()

ctrl_count = (df_experiment["assigned_variant"] == "A").sum()
trt_count = (df_experiment["assigned_variant"] == "B").sum()

is_srm, srm_pval = engine.validate_sample_ratio_mismatch(ctrl_count, trt_count)
print(f"\n--- SRM Check ---")
print(f"Sample Kontrol: {ctrl_count} | Sample Varian: {trt_count}")
print(f"Chi-Square p-value: {srm_pval:.4f}")
print(f"Status SRM: {'GAGAL (Bias Terdeteksi)' if is_srm else 'LOLOS (Valid Randomization)'}")
assert not is_srm, "Eksperimen dibatalkan karena terdeteksi SRM!"
```

#### Langkah 3: Evaluasi Naive vs CUPED-Adjusted Test
```python
print(f"\n--- Evaluasi Tanpa CUPED (Naive Welch Test) ---")
naive_results = engine.analyze_experiment(
    df=df_experiment,
    variant_col="assigned_variant",
    metrics=["post_experiment_cost"],
    control_label="A",
    treatment_label="B"
)[0]

print(f"Naive Lift Absolut: {naive_results.absolute_lift:.4f} USD")
print(f"Naive 95% CI     : [{naive_results.confidence_interval_95[0]:.4f}, {naive_results.confidence_interval_95[1]:.4f}]")
print(f"Naive p-value    : {naive_results.p_value:.5e}")

print(f"\n--- Evaluasi Dengan CUPED Adjustment ---")
cuped_results = engine.analyze_experiment(
    df=df_experiment,
    variant_col="assigned_variant",
    metrics=["post_experiment_cost"],
    pre_experiment_metrics={"post_experiment_cost": "pre_experiment_cost"},
    control_label="A",
    treatment_label="B"
)[0]

print(f"Variance Reduction : {cuped_results.variance_reduction_pct:.2f}%")
print(f"CUPED Lift Absolut : {cuped_results.absolute_lift:.4f} USD")
print(f"CUPED 95% CI       : [{cuped_results.confidence_interval_95[0]:.4f}, {cuped_results.confidence_interval_95[1]:.4f}]")
print(f"CUPED p-value      : {cuped_results.p_value:.5e}")
print(f"Signifikan (FDR)   : {cuped_results.statistically_significant}")
```

#### Langkah 4: Analisis dan Interpretasi Keputusan Produksi
Bandingkan rentang *Confidence Interval* (CI) antara evaluasi Naive dan CUPED:
- Amati bagaimana variansi yang tereduksi mempersempit lebar interval kepercayaan secara substansial.
- Validasi apakah batas atas CI konsisten berada di bawah angka 0 (mengonfirmasi penurunan biaya komputasi agent yang definitif secara statistik).
- Simpulkan rekomendasi bisnis formal: **Roll out Varian B ke 100% traffic produksi** karena model perutean konteks baru terbukti secara kausal mengurangi pengeluaran operasional per sesi tanpa merusak alokasi lalu lintas (lolos SRM).