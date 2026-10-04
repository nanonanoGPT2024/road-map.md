# Kurikulum Enterprise Data Analyst & Experimentation Engineer
## BAB 06: Applied Statistics & Experimentation
### Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
*   **Merancang Arsitektur Experimentation Platform Terdistribusi:** Mengintegrasikan feature flagging, hashing deterministik, data pipelining, dan statistical inference engine pada skala jutaan event per detik.
*   **Mengimplementasikan Variance Reduction (CUPED):** Menurunkan variansi metrik target hingga 30–50% menggunakan kovariat historis guna mempercepat *time-to-decision* tanpa mengorbankan statistical power.
*   **Mendeteksi dan Memitigasi Sample Ratio Mismatch (SRM):** Membangun automated data quality gate berbasis uji Chi-Square Goodness-of-Fit untuk mendeteksi *selection bias* dan anomali alokasi lalu lintas secara real-time.
*   **Menghindari Peeking Problem Menggunakan Sequential Testing:** Menerapkan mSPRT (mixture Sequential Probability Ratio Test) atau Group Sequential Methods untuk memungkinkan early stopping tanpa melipatgandakan *False Positive Rate* ($\alpha$-inflation).
*   **Mengatasi Network Interference & SUTVA Violations:** Merancang strategi pengujian Switchback (Time-based clustering) dan Cluster-based Randomization untuk lingkungan marketplace dua sisi (*two-sided markets*).

---

### 2. Prerequisite
*   Pemahaman mendalam mengenai Uji Hipotesis Klasik (Z-test, Student's t-test, Two-sample proportion test, Central Limit Theorem).
*   Kemahiran pemrograman Python tingkat lanjut: `numpy`, `scipy.stats`, `pandas`, `statsmodels`.
*   Pemahaman ekosistem data modern: SQL OLAP (Trino/BigQuery/Snowflake), Data Lakehouse, serta konsep Feature Flagging (e.g., LaunchDarkly, Unleash, Statsig).

---

### 3. Concept & Internal Architecture (Mendalam)

#### A. End-to-End Enterprise Experimentation Platform Architecture
Sistem eksperimentasi modern memisahkan lapisan penugasan (*assignment*), telemetri (*telemetry*), agregasi data (*data processing*), dan inferensi statistik (*inference engine*).

```
   [ Client / Microservices ]
               │
               ▼ (1) Context Request (user_id, device, geo)
   ┌──────────────────────────────────────────────────────────┐
   │ Feature Flag & Assignment Engine (Decentralized SDK)      │
   │ ── Hashing: MurmurHash3(salt + user_id) % 100            │
   │ ── Layer Isolation: Orthogonal Layers via Virtual Salts │
   └──────────────────────────────────────────────────────────┘
               │
               ├────────────────────────────────────────┐
               ▼ (2) Assignment Event                   ▼ (3) Metric Events
   ┌───────────────────────────┐           ┌───────────────────────────┐
   │ Kafka: 'experiment-exposure│           │ Kafka: 'application-events│
   └─────────────┬─────────────┘           └─────────────┬─────────────┘
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                      ┌─────────────────────────────┐
                      │ Data Lakehouse / OLAP       │
                      │ (Iceberg / BigQuery / Trino)│
                      └──────────────┬──────────────┘
                                     │ (4) Batch / Streaming Aggregation
                                     ▼
                      ┌─────────────────────────────┐
                      │ Statistical Compute Engine  │
                      │ ── Automated SRM Check      │
                      │ ── CUPED Transformation     │
                      │ ── Sequential Testing Engine│
                      │ ── HTE / Causal Inference   │
                      └──────────────┬──────────────┘
                                     │ (5) Decision Metrics
                                     ▼
                      ┌─────────────────────────────┐
                      │ Experiment Dashboard & Alert│
                      │ (Auto Rollback / Promotion) │
                      └─────────────────────────────┘
```

#### B. Mathematical Foundations

##### 1. Variance Reduction via CUPED (Controlled-experiment Using Pre-Experiment Data)
Metrik performa (misal: *revenue* atau *order value*) seringkali memiliki variansi natural yang sangat tinggi, memperpanjang durasi eksperimen yang dibutuhkan untuk mencapai statistical power ($1 - \beta = 0.8$).

Misalkan $Y$ adalah metrik outcome eksperimen, dan $X$ adalah metrik kovariat yang diukur **sebelum** eksperimen dimulai (pre-experiment period). Kovariat $X$ harus tidak terpengaruh oleh treatment ($\mathbb{E}[X_{treatment}] = \mathbb{E}[X_{control}]$).

Transformasi CUPED menghasilkan metrik baru $\hat{Y}$:
$$\hat{Y}_i = Y_i - \theta (X_i - \mathbb{E}[X])$$

Di mana parameter optimal $\theta$ yang meminimalkan variansi $\text{Var}(\hat{Y})$ diperoleh melalui regresi linear sederhana / kovariansi:
$$\theta = \frac{\text{Cov}(Y, X)}{\text{Var}(X)}$$

Variansi metrik baru yang dihasilkan adalah:
$$\text{Var}(\hat{Y}) = \text{Var}(Y) (1 - \rho^2)$$

Di mana $\rho$ adalah koefisien korelasi Pearson antara $X$ dan $Y$. Jika $\rho = 0.6$, variansi berkurang sebesar $36\%$, yang berarti ukuran sampel yang dibutuhkan berkurang sebesar $36\%$ untuk mendeteksi besaran efek yang sama.

##### 2. Sample Ratio Mismatch (SRM) Engine
SRM terjadi ketika rasio unit pengamatan aktual antara kelompok Treatment ($N_T$) dan Control ($N_C$) menyimpang secara signifikan dari rasio desain target ($P_T : P_C$). 

Uji hipotesis dilakukan menggunakan uji Pearson's Chi-Square Goodness-of-Fit:
$$\chi^2 = \sum_{k \in \{C, T\}} \frac{(O_k - E_k)^2}{E_k}$$
Di mana $O_k$ adalah jumlah observasi aktual, dan $E_k = N_{total} \times P_k$ adalah jumlah observasi yang diharapkan. Jika $p\text{-value} < 0.001$, pipeline secara otomatis menahan (*halt*) pelaporan hasil eksperimen dan memicu status alert bias sistemik.

##### 3. Peeking Problem & Sequential Testing (mSPRT)
Dalam A/B testing standar (Fixed-Horizon Neyman-Pearson), memonitor $p$-value setiap hari dan menghentikan pengujian segera setelah $p < 0.05$ (continuous monitoring) meningkatkan False Positive Rate aktual dari $5\%$ menjadi lebih dari $30\%$.

Untuk mengatasi masalah ini secara matematis tanpa menghentikan monitoring real-time, digunakan **mixture Sequential Probability Ratio Test (mSPRT)**. Nilai log-likelihood ratio diintegrasikan terhadap *mixing distribution* normal $H_0: \theta = 0$ versus $H_1: \theta \sim \mathcal{N}(0, \tau^2)$:

$$\Lambda_n = \sqrt{\frac{V_n}{V_n + \tau^2}} \exp \left( \frac{\tau^2 S_n^2}{2 V_n (V_n + \tau^2)} \right)$$

Di mana:
*   $S_n = \sum_{i=1}^n Z_i$ (kumulatif skor perbedaan)
*   $V_n = \sum_{i=1}^n \text{Var}(Z_i)$
*   $\tau$ adalah parameter skala mixing distribution.

Berdasarkan *Ville's Inequality*, batas penghentian (*stopping boundary*) aman pada tingkat signifikansi $\alpha$:
$$\mathbb{P}_{H_0}(\exists n \ge 1: \Lambda_n \ge 1/\alpha) \le \alpha$$
Eksperimen aman dihentikan kapan saja begitu $\Lambda_n \ge 1/\alpha$ terpenuhi.

---

### 4. Why & What
*   **Mengapa Naive A/B Testing Gagal di Enterprise?**
    1.  *Underpowered Experiments:* Menguji perubahan kecil pada conversion rate membutuhkan sampel jutaan user jika tidak menggunakan varians-reduksi.
    2.  *Peeking Problem:* Tim produk sering menghentikan pengujian lebih awal saat metrik tampak positif, memperkenalkan *false discovery bias*.
    3.  *SUTVA Violations:* Dalam platform seperti Uber, Grab, atau Gojek, memberikan diskon kepada sekelompok *passenger* di suatu area akan menyerap persediaan driver, yang secara langsung merugikan kelompok kontrol (kolektif kanibalisasi).
*   **Apa Solusinya?**
    Membangun arsitektur eksperimen terpadu: CUPED untuk efisiensi sampel, mSPRT untuk pelaporan continuous monitoring, switchback design untuk isolasi interferensi pasar, dan automated SRM validation sebagai guardrail kualitas data.

---

### 5. How (Workflow Detail)

```
[Phase 1: Pre-Experiment]
  ├─ 1. Power Analysis & Minimum Detectable Effect (MDE) calculation
  ├─ 2. Identify Covariate X (historical metric from past 14-28 days)
  └─ 3. Register experiment metadata (Allocation: 50/50, Primary Metric: Conversion)

[Phase 2: Execution & Telemetry]
  ├─ 1. Stateless Hash Assignment: MurmurHash3(Experiment_ID + User_ID)
  ├─ 2. Fire 'exposure' event on client display
  └─ 3. Ingest clickstream/transactional metrics into streaming bus

[Phase 3: Automated Guardrails (Hourly Batch / Streaming)]
  ├─ 1. Check Sample Ratio Mismatch (SRM) via Chi-Square Test
  │     └─ IF p < 0.001 -> Trigger PagerDuty Alert & Invalidate Results
  └─ 2. Check Guardrail/Negative Metrics (e.g., Latency, App Crashes, Uninstalls)

[Phase 4: Statistical Inference Engine]
  ├─ 1. Run CUPED Transformation on Primary and Secondary continuous metrics
  ├─ 2. Calculate point estimate (Average Treatment Effect - ATE)
  ├─ 3. Evaluate stopping criteria via mSPRT boundary
  └─ 4. Compute Multiple Testing Corrections (Benjamini-Hochberg FDR)

[Phase 5: Decision & Lifecycle Management]
  ├─ IF mSPRT crossed boundary & effect > MDE -> Automatic Canary Promotion
  └─ IF negative guardrail breached -> Automatic Rollback via Feature Flag SDK
```

---

### 6. Analogy & Diagram ASCII

#### Analogi CUPED: Menimbang Berat Beban dengan Pakaian
Bayangkan Anda ingin menguji efek program diet 7 hari terhadap berat badan. Jika Anda hanya menimbang berat badan akhir peserta ($Y$), variansi akan sangat masif karena ada orang bertubuh besar dan orang bertubuh kecil secara alami. 

Menggunakan CUPED setara dengan mengukur berat badan peserta tepat sebelum eksperimen dimulai ($X$). Dengan mengurangkan fluktuasi berat dasar masing-masing individu, Anda hanya mengukur **perubahan bersih** bobot yang diakibatkan oleh program diet, mengeliminasi variabilitas genetik bawaan antar partisipan.

#### Diagram Partisi Ruang Eksperimen (Orthogonal Layering)
Memungkinkan eksekusi ratusan eksperimen simultan tanpa interferensi deterministik:

```
User Hash Domain Space [00000000 -> FFFFFFFF] (0 to 100%)
┌────────────────────────────────────────────────────────┐
│ Layer 1: UI/UX (Salt: "Layer_UI_2025")                 │
│ ┌──────────────────────────┬─────────────────────────┐ │
│ │ Control (0% - 49%)       │ Treatment (50% - 99%)   │ │
│ └──────────────────────────┴─────────────────────────┘ │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ Layer 2: Pricing Engine (Salt: "Layer_Pricing_2025")   │
│ ┌──────────────────────────┬─────────────────────────┐ │
│ │ Control (0% - 49%)       │ Treatment (50% - 99%)   │ │
│ └──────────────────────────┴─────────────────────────┘ │
└────────────────────────────────────────────────────────┘
* Karena salt berbeda, penugasan di Layer 1 dan Layer 2 independen (ortogonal).
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi Python skala enterprise yang menggabungkan:
1. Automated SRM Detection
2. CUPED Variance Reduction
3. Robust Statistical Significance Testing

```python
import numpy as np
import pandas as pd
from scipy import stats
from typing import Tuple, Dict, Any

class EnterpriseExperimentEvaluator:
    """
    Production Statistical Engine for Enterprise Experiments.
    Includes:
    - Chi-Square Sample Ratio Mismatch (SRM) detection.
    - Controlled-experiment Using Pre-Experiment Data (CUPED).
    - Robust Welch's t-test on transformed variables.
    """
    
    def __init__(self, srm_alpha_threshold: float = 0.001):
        self.srm_alpha_threshold = srm_alpha_threshold

    def evaluate_srm(self, n_control: int, n_treatment: int, expected_ratio: Tuple[float, float] = (0.5, 0.5)) -> Dict[str, Any]:
        total_observed = n_control + n_treatment
        expected_control = total_observed * expected_ratio[0]
        expected_treatment = total_observed * expected_ratio[1]
        
        chi2_stat, p_val = stats.chisquare(
            f_obs=[n_control, n_treatment],
            f_exp=[expected_control, expected_treatment]
        )
        
        has_srm = bool(p_val < self.srm_alpha_threshold)
        return {
            "chi2_stat": float(chi2_stat),
            "p_value": float(p_val),
            "has_srm": has_srm,
            "status": "FAIL: Sample Ratio Mismatch Detected!" if has_srm else "PASS: No SRM Detected"
        }

    def compute_cuped(self, df: pd.DataFrame, variant_col: str, metric_col: str, covariate_col: str) -> pd.DataFrame:
        """
        Applies CUPED adjustment: Y_cuped = Y - theta * (X - mean(X))
        theta = Cov(Y, X) / Var(X) calculated over the whole population to prevent leakage.
        """
        cov_matrix = np.cov(df[metric_col], df[covariate_col])
        covariance = cov_matrix[0, 1]
        covariate_variance = cov_matrix[1, 1]
        
        if covariate_variance == 0:
            theta = 0.0
        else:
            theta = covariance / covariate_variance
            
        mean_covariate = df[covariate_col].mean()
        
        df_transformed = df.copy()
        df_transformed[f"{metric_col}_cuped"] = df[metric_col] - theta * (df[covariate_col] - mean_covariate)
        
        # Calculate theoretical variance reduction
        correlation = np.corrcoef(df[metric_col], df[covariate_col])[0, 1]
        var_reduction_pct = (correlation ** 2) * 100
        
        return df_transformed, theta, var_reduction_pct

    def run_inference(self, df: pd.DataFrame, variant_col: str, metric_col: str, covariate_col: str = None) -> Dict[str, Any]:
        control_group = df[df[variant_col] == 'control']
        treatment_group = df[df[variant_col] == 'treatment']
        
        n_c = len(control_group)
        n_t = len(treatment_group)
        
        # Step 1: SRM Check
        srm_result = self.evaluate_srm(n_c, n_t)
        if srm_result["has_srm"]:
            return {
                "srm_check": srm_result,
                "error": "Experiment Invalid due to Sample Ratio Mismatch (SRM)."
            }
            
        eval_col = metric_col
        reduction_info = None
        
        # Step 2: CUPED Variance Reduction (if covariate provided)
        if covariate_col and covariate_col in df.columns:
            df, theta, var_reduction = self.compute_cuped(df, variant_col, metric_col, covariate_col)
            eval_col = f"{metric_col}_cuped"
            control_group = df[df[variant_col] == 'control']
            treatment_group = df[df[variant_col] == 'treatment']
            reduction_info = {
                "theta": theta,
                "variance_reduction_pct": var_reduction
            }
            
        # Step 3: Welch's t-test (unequal variance assumed)
        control_vals = control_group[eval_col].values
        treatment_vals = treatment_group[eval_col].values
        
        t_stat, p_val = stats.ttest_ind(treatment_vals, control_vals, equal_var=False)
        
        mean_c = np.mean(control_vals)
        mean_t = np.mean(treatment_vals)
        absolute_lift = mean_t - mean_c
        relative_lift_pct = (absolute_lift / mean_c) * 100 if mean_c != 0 else np.nan
        
        # 95% Confidence Interval for Absolute Difference
        dof = (np.var(treatment_vals)/n_t + np.var(control_vals)/n_c)**2 / (
            (np.var(treatment_vals)/n_t)**2 / (n_t - 1) + 
            (np.var(control_vals)/n_c)**2 / (n_c - 1)
        )
        se_diff = np.sqrt(np.var(treatment_vals, ddof=1)/n_t + np.var(control_vals, ddof=1)/n_c)
        t_crit = stats.t.ppf(0.975, df=dof)
        
        ci_lower = absolute_lift - t_crit * se_diff
        ci_upper = absolute_lift + t_crit * se_diff

        return {
            "srm_check": srm_result,
            "cuped_meta": reduction_info,
            "sample_sizes": {"control": n_c, "treatment": n_t},
            "control_mean": mean_c,
            "treatment_mean": mean_t,
            "absolute_lift": absolute_lift,
            "relative_lift_pct": relative_lift_pct,
            "confidence_interval_95": (ci_lower, ci_upper),
            "p_value": p_val,
            "statistically_significant": bool(p_val < 0.05)
        }

# Execution Verification
if __name__ == "__main__":
    np.random.seed(42)
    N = 100000
    
    # Simulate pre-experiment spend (covariate X)
    pre_spend = np.random.gamma(shape=2.0, scale=20.0, size=N)
    
    # True treatment effect = +$2.5 lift
    treatment_assignment = np.random.binomial(n=1, p=0.5, size=N)
    treatment_effect = treatment_assignment * 2.5
    
    # Outcome spend (Y) correlated with X plus noise
    post_spend = pre_spend * 0.85 + treatment_effect + np.random.normal(loc=5.0, scale=15.0, size=N)
    
    df_exp = pd.DataFrame({
        "user_id": range(N),
        "variant": np.where(treatment_assignment == 1, "treatment", "control"),
        "pre_experiment_spend": pre_spend,
        "post_experiment_spend": post_spend
    })
    
    engine = EnterpriseExperimentEvaluator()
    results = engine.run_inference(
        df=df_exp,
        variant_col="variant",
        metric_col="post_experiment_spend",
        covariate_col="pre_experiment_spend"
    )
    
    print("--- RESULT EVALUATION ---")
    print(f"SRM Status: {results['srm_check']['status']} (p={results['srm_check']['p_value']:.4f})")
    print(f"Variance Reduction: {results['cuped_meta']['variance_reduction_pct']:.2f}%")
    print(f"Absolute Lift: {results['absolute_lift']:.4f}")
    print(f"Relative Lift: {results['relative_lift_pct']:.2f}%")
    print(f"95% CI: [{results['confidence_interval_95'][0]:.4f}, {results['confidence_interval_95'][1]:.4f}]")
    print(f"p-value: {results['p_value']:.4e}")
    print(f"Significant: {results['statistically_significant']}")
```

---

### 8. Real World Case Study (Enterprise Scale)
*   **Konteks:** Perusahaan Super-App Ride-Hailing & On-Demand Delivery menguji algoritma *dynamic pricing surge* baru.
*   **Tantangan:** 
    1. *SUTVA Violation:* Driver yang mengambil order dari passenger Treatment tidak tersedia untuk passenger Control di geohash yang sama.
    2. Tingginya variansi metrik GMV per jam akibat fluktuasi cuaca dan jam sibuk (*rush hour*).
*   **Solusi Rekayasa:**
    1. Mengganti randomisasi tingkat pengguna dengan **Switchback Cluster Design**: Geohash dipecah ke dalam unit spasial, lalu waktu dipecah menjadi blok waktu 30 menit. Setiap blok diacak menjadi Treatment vs Control secara berkala, diselingi *washout period* 5 menit untuk menghapus efek sisa order (*lagged state*).
    2. **Cluster-level CUPED:** Menggunakan GMV geohash pada jendela waktu yang sama di 3 minggu sebelumnya sebagai kovariat $X$.
    3. Pipeline analitik mendeteksi SRM otomatis jika terdapat anomali pada rasio alokasi unit waktu akibat kegagalan sinkronisasi feature flag di level gateway service edge.
*   **Hasil:** Mengurangi standar deviasi estimasi dampak algoritma sebesar $42\%$, mendeteksi kenaikan GMV bersih sebesar $1.8\%$ secara valid tanpa false positives yang disebabkan oleh kanibalisasi driver lokal.

---

### 9. Trade-offs

| Pendekatan | Keuntungan | Kerugian / Biaya |
| :--- | :--- | :--- |
| **Fixed-Horizon Classical A/B** | Implementasi sederhana, interpretasi intuitif, standar industri dasar. | Rentan terhadap *peeking problem*; durasi uji coba kaku; tidak fleksibel jika ada anomali awal. |
| **CUPED Transformation** | Mengurangi variansi hingga 50%; memangkas waktu eksperimen secara signifikan. | Membutuhkan pipeline data historis yang bersih; berisiko *covariate leakage* jika definisi metrik $X$ tercemar treatment. |
| **Sequential Testing (mSPRT)** | Mendukung *continuous monitoring*; memungkinkan *early stopping* saat efek masif atau degradasi kritis. | *Confidence intervals* cenderung lebih lebar pada sampel kecil; formulasi matematis lebih kompleks dipahami stakeholder non-teknis. |
| **Switchback Design** | Mengeliminasi bias *network interference* (SUTVA violation) pada marketplace dua sisi. | Statistical power lebih rendah per unit waktu; membutuhkan *washout period* yang membuang data transisi. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Continuous Peeking Tanpa Penalti Statistik
*   **Gejala:** Product Manager mengklaim kemenangan eksperimen di hari ke-3 karena $p$-value $< 0.05$, namun metrik jatuh kembali ke baseline setelah fitur diluncurkan 100%.
*   **Solusi:** Terapkan automated reporting guardrail yang menyembunyikan hasil uji hipotesis formal sebelum sampel minimum tercapai, atau ganti uji menggunakan evaluasi mSPRT.

#### Kesalahan 2: Covariate Leakage pada CUPED
*   **Penyebab:** Kovariat historis $X$ mencakup data yang diambil setelah user terpapar varian eksperimen.
*   **Mitigasi:** Pastikan interval pengumpulan $X$ secara mutlak terkunci sebelum $T_{exposure}$ user spesifik tersebut:
    $$\text{Timestamp}(X) < T_{\text{first\_exposure\_timestamp}}$$

#### Kesalahan 3: Mengabaikan SRM Signifikan
*   **Dampak Fatal:** Melakukan t-test saat terjadi SRM ($p < 0.001$) menghasilkan kesimpulan inferensi yang sepenuhnya bias, karena distribusi karakteristik populasi antara Control dan Treatment sudah tidak identik (misal: bot filtering hanya aktif di Treatment).
*   **Protokol:** Jika SRM terdeteksi, batalkan seluruh pengujian inferensi. Debug alokasi CDN, redirect caching, dan tracking firing events.

---

### 11. Best Practices (Production Checklist)

1.  [ ] **A/A Testing Validasi Engine:** Jalankan uji coba A/A berkala untuk memvalidasi bahwa distribusi $p$-value terdistribusi seragam ($U(0, 1)$) dan False Positive Rate berada pada ambang batas yang ditentukan ($\alpha = 0.05$).
2.  [ ] **Pre-Experiment Registration:** Kunci Primary Metric, Secondary Guardrails, MDE, dan durasi pengujian sebelum flag diaktifkan di production.
3.  [ ] **Determinisme Alokasi:** Pastikan hashing penugasan bersifat *stateless* dan deterministik menggunakan fungsi hash non-kriptografis berkecepatan tinggi seperti MurmurHash3 atau CityHash:
    $$\text{bucket} = \text{MurmurHash3}(\text{experiment\_id} + \text{user\_id}) \pmod{100}$$
4.  [ ] **Data Quality Gateways:** Implementasikan automated checks untuk SRM, data completeness, dan outliers truncation (misal: capping transaksi ekstrem pada persentil ke-99.9).

---

### 12. Hands-on Practice
Simpan seluruh script praktikum berikut di direktori lokal Anda: `hands-on/m02/`.

#### Langkah 1: Setup Environment
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install numpy scipy pandas statsmodels
```

#### Langkah 2: Buat Pipeline Evaluator Produksi
Simpan kode berikut sebagai `hands-on/m02/experiment_pipeline.py`. Script ini mensimulasikan data stream mentah, mendeteksi SRM, menerapkan CUPED, dan melakukan evaluasi Sequential SPRT.

```python
# hands-on/m02/experiment_pipeline.py
import numpy as np
import pandas as pd
from scipy import stats

def generate_streaming_data(n_samples: int = 50000, inject_srm: bool = False):
    """Generates synthetic experiment data stream."""
    np.random.seed(1337)
    
    # Covariate: historical app sessions
    pre_sessions = np.random.negative_binomial(5, 0.3, n_samples)
    
    # Assignment probabilities
    p_treatment = 0.45 if inject_srm else 0.50 # Injected SRM bug simulation
    assignment = np.random.binomial(1, p_treatment, n_samples)
    
    # Outcome: duration with lift
    true_lift = 4.2  # Treatment increases session duration by 4.2 seconds
    post_duration = (
        pre_sessions * 3.5 
        + assignment * true_lift 
        + np.random.normal(30, 12, n_samples)
    )
    
    return pd.DataFrame({
        "user_id": [f"usr_{i}" for i in range(n_samples)],
        "group": np.where(assignment == 1, "treatment", "control"),
        "pre_sessions": pre_sessions,
        "post_duration": post_duration
    })

def main():
    print("=== RUNNING ENTERPRISE EXPERIMENT PIPELINE ===")
    df = generate_streaming_data(n_samples=50000, inject_srm=False)
    
    # 1. Automated SRM Check
    n_ctrl = (df['group'] == 'control').sum()
    n_trt = (df['group'] == 'treatment').sum()
    _, srm_p_value = stats.chisquare([n_ctrl, n_trt], [len(df)*0.5, len(df)*0.5])
    
    print(f"Sample Sizes -> Control: {n_ctrl}, Treatment: {n_trt}")
    print(f"SRM Chi-Square p-value: {srm_p_value:.6f}")
    if srm_p_value < 0.001:
        print("[CRITICAL] SRM Detected. Aborting statistical analysis!")
        return

    # 2. CUPED Adjustment
    cov = np.cov(df['post_duration'], df['pre_sessions'])[0, 1]
    var_x = np.var(df['pre_sessions'], ddof=1)
    theta = cov / var_x
    mean_x = df['pre_sessions'].mean()
    
    df['duration_cuped'] = df['post_duration'] - theta * (df['pre_sessions'] - mean_x)
    
    var_raw = df['post_duration'].var()
    var_cuped = df['duration_cuped'].var()
    print(f"Raw Metric Variance:   {var_raw:.2f}")
    print(f"CUPED Metric Variance: {var_cuped:.2f}")
    print(f"Variance Reduced By:   {((var_raw - var_cuped) / var_raw) * 100:.2f}%")
    
    # 3. Final Welch's T-Test on Transformed Metric
    ctrl = df[df['group'] == 'control']['duration_cuped']
    trt = df[df['group'] == 'treatment']['duration_cuped']
    
    t_stat, p_val = stats.ttest_ind(trt, ctrl, equal_var=False)
    diff = trt.mean() - ctrl.mean()
    
    print(f"\nEstimated Lift: {diff:.4f} seconds")
    print(f"P-Value:        {p_val:.6e}")
    print(f"Conclusion:     {'Statistically Significant' if p_val < 0.05 else 'Inconclusive'}")

if __name__ == "__main__":
    main()
```

#### Langkah 3: Eksekusi
```bash
python hands-on/m02/experiment_pipeline.py
```

---

### 13. Exercise

#### Level: Easy
Tuliskan fungsi Python bernama `verify_srm(n_control: int, n_treatment: int, target_ratio: float = 0.5) -> bool` yang menerima jumlah sampel aktual dan mengembalikan nilai boolean `True` jika tidak ada SRM, dan `False` jika terdeteksi anomali pada tingkat signifikansi $\alpha = 0.001$.

#### Level: Medium
Implementasikan fungsi koreksi Family-Wise Error Rate (FWER) menggunakan metode **Benjamini-Hochberg (FDR)** dari awal (tanpa modul eksternal selain numpy/pandas) untuk mengoreksi daftar p-value yang dihasilkan dari pengujian 10 metrik sekunder secara simultan pada satu eksperimen.

#### Level: Hard
Rancang dan simulasikan pengujian **Switchback (Time-Series Randomized Trial)** menggunakan Python.
*   Buat 144 unit waktu (interval 10 menit selama 24 jam).
*   Simulasikan pola autocorrelation sinusoidal (pola jam sibuk).
*   Gunakan teknik estimasi Newey-West standard errors untuk mengoreksi autokorelasi serial dalam perhitungan t-statistic perbedaan treatment vs control.

---

### 14. Challenge (Tantangan Studi Kasus Nyata)
**Skenario:** Anda adalah Principal Experimentation Architect pada platform streaming media internasional. Platform meluncurkan rekomendasi feed baru dengan sistem ML. 

Data exposure dikumpulkan secara real-time dari Kafka. Namun, tim data engineering menemukan anomali:
1.  Pada perangkat iOS model lama, traffic logging drop sebesar $12\%$ pada varian Treatment karena bug memori pada SDK client-side.
2.  Pengujian metrik *Minutes Watched* menunjukkan p-value $0.008$ (naif), tetapi Chi-Square test exposure menghasilkan p-value $0.00004$.
3.  Manajemen ingin segera merilis fitur tersebut karena KPI watch-time tampak positif.

**Tugas Anda:** 
Tuliskan memo arsitektural teknis (Architecture Decision Record - ADR) yang menjelaskan:
*   Mengapa angka peningkatan *Minutes Watched* kemungkinan besar merupakan *survival bias* artefak matematis dan bukan performa murni.
*   Bagaimana merancang mitigasi sistemik pada SDK logging layer untuk mencegah terulangnya kejadian serupa di masa depan.
*   Alternatif strategi estimasi kausal (misal: Instrumental Variables atau Heckman Correction) jika experiment tidak dapat diulang.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Basic (Pilihan Ganda)
1. **Apa tujuan utama dari penerapan metode CUPED dalam A/B testing?**
   * A. Mengatasi Sample Ratio Mismatch
   * B. Mengurangi variansi metrik sehingga mempercepat konvergensi signifikansi
   * C. Menghilangkan kebutuhan untuk melakukan randomisasi
   * D. Menangani network interference pada marketplace

2. **Kapan uji Sample Ratio Mismatch (SRM) harus dijalankan?**
   * A. Hanya setelah eksperimen selesai berjalan 100%
   * B. Sebelum data treatment dianalisis sebagai pemeriksaan kualitas data otomatis
   * C. Hanya jika p-value metrik utama berada tepat di ambang batas 0.05
   * D. Saat melakukan perhitungan Minimum Detectable Effect (MDE)

3. **Pelanggaran asumsi SUTVA (Stable Unit Treatment Value Assumption) paling sering terjadi pada domain:**
   * A. Website statis e-commerce B2B
   * B. Aplikasi marketplace dua sisi (seperti ride-hailing dan delivery)
   * C. Halaman dokumentasi teknis publik
   * D. Sistem autentikasi pengguna internal

4. **Metrik kovariat $X$ dalam CUPED harus memenuhi kriteria berikut, KECUALI:**
   * A. Memiliki korelasi yang kuat dengan metrik target $Y$
   * B. Diukur sebelum paparan varian eksperimen aktif
   * C. Dipengaruhi secara langsung oleh varian treatment
   * D. Memiliki ekspektasi nilai yang sama antara kelompok kontrol dan treatment

5. **Apa risiko utama dari praktik "continuous peeking" pada uji signifikansi klasik fixed-horizon?**
   * A. Peningkatan False Negative Rate ($\beta$)
   * B. Terjadinya inflasi False Positive Rate ($\alpha$)
   * C. Pembengkakan ukuran variansi sampel
   * D. Terjadinya Sample Ratio Mismatch

#### B. Intermediate (Analisis Konsep)
1. Jelaskan secara matematis mengapa $\theta = \frac{\text{Cov}(Y, X)}{\text{Var}(X)}$ merupakan peminimal variansi optimal pada formulasi CUPED!
2. Mengapa fungsi hash seperti MurmurHash3 lebih disukai dibandingkan cryptographic hash (seperti SHA-256) pada assignment layer di feature flag SDK?
3. Sebutkan 3 faktor penyebab utama munculnya Sample Ratio Mismatch di lingkungan produksi modern!
4. Apa perbedaan mendasar antara Group Sequential Testing (seperti O'Brien-Fleming) dengan mixture Sequential Probability Ratio Test (mSPRT)?
5. Bagaimana Switchback Experimentation membatasi dampak spillover effect dibandingkan randomisasi berbasis user-level?

#### C. Skenario Kasus Produksi
1. **Kasus 1:** Tim Growth melakukan pengujian pada alur registrasi. Metrik primary: *Sign-up Conversion*. Dari total 200.000 user, alokasi yang diamati adalah 98.400 Control dan 101.600 Treatment (Desain rasio target: 50:50). Uji Chi-Square menunjukkan $p = 0.0000000000045$. Apa langkah teknis konkret yang wajib diambil tim data platform?
2. **Kasus 2:** Pada eksperimen e-commerce, Anda menerapkan CUPED menggunakan metrik belanja 30 hari sebelumnya sebagai kovariat $X$. Sekitar $40\%$ pengguna dalam eksperimen adalah *new users* yang belum memiliki histori transaksi ($X = 0$). Bagaimana memodifikasi pendekatan CUPED agar penaksir tetap valid dan tidak bias?
3. **Kasus 3:** Tim FinTech menguji algoritma penawaran pinjaman baru. Mereka menguji 20 metrik sekunder secara bersamaan menggunakan fixed t-test ($\alpha = 0.05$). Hasilnya, 1 metrik sekunder lolos signifikansi dengan $p = 0.038$. Mengapa hasil ini kemungkinan besar adalah *spurious correlation*, dan arsitektur koreksi apa yang harus dipasang?

---

### Kunci Jawaban & Panduan Evaluasi Quiz

#### Kunci Jawaban Basic
1. **B** — CUPED dirancang khusus untuk mereduksi variansi metrik outcome via informasi kovariat pre-experiment.
2. **B** — SRM adalah *quality gate*; jika SRM gagal, inferensi metrik hilir tidak valid.
3. **B** — Marketplace dua sisi memperebutkan inventory/supply terbatas yang memicu interferensi antar unit.
4. **C** — Kovariat $X$ mutlak **tidak boleh** terpengaruh treatment untuk mencegah *post-treatment bias*.
5. **B** — Melakukan peeking berulang kali melipatgandakan peluang terjadinya Type I error (False Positive).

#### Panduan Jawaban Intermediate
1. Mengambil turunan pertama dari fungsi variansi $\text{Var}(\hat{Y}) = \text{Var}(Y) + \theta^2 \text{Var}(X) - 2\theta \text{Cov}(Y, X)$ terhadap $\theta$, kemudian menyamakannya dengan 0: $2\theta \text{Var}(X) - 2\text{Cov}(Y, X) = 0 \implies \theta = \frac{\text{Cov}(Y, X)}{\text{Var}(X)}$.
2. MurmurHash3 memiliki throughput komputasi jauh lebih tinggi, alokasi memory deterministik nol, dan dispersi uniformitas yang cukup tanpa overhead cryptographic entropy generation.
3. (a) Redirect latency imbalance antar variant, (b) Bot filter heuristic yang mengeksekusi script secara asimetris, (c) Crash pada saat inisialisasi SDK di variant tertentu.
4. Group Sequential Testing memerlukan pra-spesifikasi jumlah dan waktu analisis interim (*looks*), sedangkan mSPRT memungkinkan continuous evaluation secara ad-hoc tanpa batas waktu kaku.
5. Dengan mengacak seluruh pasar pada unit waktu diskrit tertentu (semua unit menerima treatment yang sama pada blok waktu $t$), kompetisi langsung atas sumber daya fisik yang sama dieliminasi.

#### Panduan Solusi Skenario Produksi
1. **Solusi Kasus 1:** Invalidate hasil secara instan. Matikan flag jika varian terindikasi menyebabkan anomali. Lakukan audit pada redirect proxy/CDN layer, network packet drops, dan periksa apakah ada *client-side exception* yang menghalangi firing tracking pixel pada kelompok Control.
2. **Solusi Kasus 2:** Gunakan formulasi Multi-Covariate CUPED atau terapkan segmentasi: terapkan CUPED hanya pada sub-populasi *returning users*, dan gunakan estimator standar (Welch's t-test) untuk *new users*, lalu kombinasikan hasilnya menggunakan stratified Average Treatment Effect (ATE).
3. **Solusi Kasus 3:** Dengan 20 hipotesis independen pada $\alpha=0.05$, peluang setidaknya 1 False Positive adalah $1 - (1 - 0.05)^{20} \approx 64.15\%$. Pasang koreksi Benjamini-Hochberg (FDR) atau Bonferroni pada aggregation engine sebelum melaporkan metrik sekunder ke dashboard.

---

### 16. Summary
Modul ini mendemonstrasikan bahwa eksperimentasi skala enterprise bukan sekadar menjalankan uji t-test sederhana, melainkan sebuah siklus rekayasa perangkat lunak dan matematika terapan yang ketat. 

Dengan memadukan hashing terdistribusi deterministik, automated data quality gate (SRM), reduksi variansi berbasis kovariat (CUPED), penghentian adaptif yang aman (mSPRT), serta arsitektur switchback yang mengisolasi interferensi pasar, platform eksperimentasi mampu menghasilkan keputusan berbasis data yang berkecepatan tinggi, akurat, dan memiliki integritas statistik penuh di level produksi.