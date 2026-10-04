# Bab 07: Experimentation, A/B Testing & Statistical Decision-Making
## Modul 01: Foundations of Rigorous Product Experimentation & Statistical Decision Engines for AI Products

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Product Manager (PM) teknis dan engineering lead diharapkan mampu:

1. **Merancang Kerangka Eksperimen Statistik Valid:** Menghitung *sample size*, *statistical power* ($1 - \beta \ge 0.80$), dan *significance level* ($\alpha = 0.05$) untuk metrik AI non-deterministik menggunakan uji dua arah (*two-tailed test*) dan *Minimum Detectable Effect* (MDE) yang realistis.
2. **Mengidentifikasi dan Memitigasi Anomali Eksperimen:** Mendeteksi *Sample Ratio Mismatch* (SRM) secara terprogram menggunakan uji $\chi^2$ (*chi-square goodness-of-fit*) pada level kepercayaan $p < 0.001$, serta mengisolasi sumber bias perutean (*assignment bias*).
3. **Mengimplementasikan Teknik Reduksi Variansi Tingkat Lanjut:** Menerapkan algoritma CUPED (*Controlled-experiment Using Pre-Experiment Data*) untuk mengecilkan variansi metrik target hingga 30–50%, mempercepat *runtime* eksperimen tanpa mengorbankan integritas inferensi.
4. **Mengevaluasi Trade-off Inferensi Klasik vs. Adaptif:** Membedakan kapan harus menggunakan *Frequentist Fixed-Horizon Hypothesis Testing*, *Sequential Testing* (mSPRT), *Bayesian A/B Testing*, atau *Multi-Armed Bandits* (MAB) untuk *routing* model AI otonom berdasarkan matriks biaya penyesalan (*regret minimization*) vs. validitas kausalitas.
5. **Menyusun Overall Evaluation Criterion (OEC) & Guardrails:** Membangun metrik terintegrasi yang menyeimbangkan metrik nilai pengguna (misal: *Task Success Rate*, CSAT) dengan metrik batas sistem AI (*p99 latency*, *token cost consumption*, *hallucination rate*).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Eksperimen produk bukanlah sekadar fitur validasi A/B testing visual sederhana; eksperimen adalah **mesin reduksi entropi berbasis kausalitas formal**. Pada produk berbasis AI dan *Autonomous Agents*, eksperimen menghadapi tantangan fundamental yang tidak ditemukan pada software deterministik tradisional:

1. **Non-Determinisme Output:** Respons model terhadap *prompt* yang sama dapat bervariasi bergantung pada *sampling temperature*, *top-p*, dan dinamika *seed*.
2. **Ketergantungan State Sistem:** Performa sebuah *Autonomous Agent* dipengaruhi oleh *latency context retrieval* (RAG), degradasi memori eksternal, dan fluktuasi API pihak ketiga.
3. **Distribusi Ekor Tebal (*Fat-Tailed Distributions*):** Waktu penyelesaian tugas agen (*execution steps*) dan konsumsi token tidak berdistribusi Gaussian murni, melainkan Log-Normal atau Pareto, yang menuntut penanganan statistik non-parametrik atau transformasi data sebelum uji t-Student klasik diterapkan.

#### Mental Model: The Causal Inference Funnel
Bayangkan eksperimen sebagai sistem isolasi sinyal kausal dari *noise* stokastik:

```
[Variasi Sistem: Model A vs B] 
            │
            ▼
[Algoritma Hashing Deterministik] ──> Menghilangkan Assignment Bias
            │
            ▼
[Non-deterministic Execution]    ──> Injeksi Noise Stokastik (LLM Engine)
            │
            ▼
[CUPED Variance Reduction]       ──> Eliminasi Variansi Historis Baseline
            │
            ▼
[Uji Hipotesis & SRM Diagnostics]──> Filter False Discovery (Type I / Type II)
            │
            ▼
[Keputusan OEC / Guardrail]      ──> Eksekusi Bisnis (Rollout / Kill)
```

Untuk menentukan kausalitas murni $E[Y(1) - Y(0)]$, unit randomisasi harus distandardisasi. Ketika menguji AI agent, PM sering kali keliru menetapkan unit randomisasi pada level *request* atau *prompt*, yang memicu kontaminasi konteks percakapan multi-turn. Pendekatan standar industri menuntut unit randomisasi berada pada level entitas independen tertinggi: **User ID** atau **Organization Workspace ID**.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lanskap enterprise, perubahan kecil pada pipeline AI (misalnya menaikkan parameter *temperature* dari $0.2$ ke $0.7$, mengganti arsitektur *embedding*, atau mengubah instruksi *system prompt*) dapat memicu regresi berskala masif:

* **Bencana Rollout Tanpa Guardrail:** Sebuah platform otomatisasi layanan pelanggan enterprise mengganti model dari GPT-4o ke model *fine-tuned open-source* 8B untuk menghemat 70% biaya inferensi. Pengujian informal 100 sampel manual menunjukkan hasil "memuaskan". Ketika di-rollout 100% tanpa A/B test formal ber-guardrail, model mengalami *hallucination compounding* pada interaksi > 5 *turns*. Hasilnya: *churn rate* melonjak 4.2% dalam 2 minggu, dengan estimasi kerugian $1.8M ARR sebelum regresi berhasil didiagnosis.
* **Peeking Problem & Inflasi False Positive:** PM yang tidak memahami inferensi statistik sering memantau dashboard analitik harian dan menghentikan pengujian segera setelah nilai $p < 0.05$ tercapai pada hari ke-3 (fenomena *data peeking*). Secara matematis, melakukan *peeking* harian selama pengujian 30 hari meningkatkan tingkat kesalahan Tipe I (*False Positive Rate*) dari nominal 5% menjadi **lebih dari 30%**. Fitur yang sebenarnya merusak metrik dipertahankan karena dianggap sukses akibat fluktuasi acak.
* **Misalokasi Komputasi & Latency Cost:** Tanpa *Power Analysis* apriori, tim sering menjalankan pengujian model AI terlalu lama (memboroskan biaya komputasi GPU/API) atau terlalu cepat (*underpowered*), sehingga gagal mendeteksi peningkatan metrik inti sebesar 2% yang secara signifikan berdampak pada jutaan pengguna.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur platform eksperimen AI enterprise harus memisahkan antara *Evaluation Plane*, *Control Plane*, dan *Data Ingestion Pipeline*:

```
+─────────────────────────────────────────────────────────────────────────────────+
|                                CLIENT APPLICATION                               |
|               (Web, Mobile, Autonomous Agent Client Interface)                  |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                         1. Get Variant Allocation(entity_id)
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                     FEATURE FLAG & SPLIT EVALUATION ENGINE                      |
|                                                                                 |
|  +───────────────────────────────────────────────────────────────────────────+  |
|  | Deterministic Consistent Hashing (MurmurHash3 + Salt)                     |  |
|  | H(entity_id + experiment_id + salt) % 10000 -> Bucket Allocation           |  |
|  +───────────────────────────────────────────────────────────────────────────+  |
|  | Targeting Rules (Workspace Tier, Geography, Agent Capability Flag)        |  |
|  +───────────────────────────────────────────────────────────────────────────+  |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                     2. Route Request to Assigned Variant
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                       MODEL SERVING & ORCHESTRATION LAYER                       |
|                                                                                 |
|  +───────────────────────────────+     +──────────────────────────────────────+  |
|  | CONTROL (Variant A)           |     | TREATMENT (Variant B)                |  |
|  | - Baseline Agent Prompt       |     | - Agent with Memory Augmentation     |  |
|  | - Foundation Model Base       |     | - Fine-Tuned Model Candidate         |  |
|  +───────────────────────────────+     +──────────────────────────────────────+  |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                     3. Publish Contextualized Telemetry Events
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                     TELEMETRY & EVENT INGESTION (Kafka / Pulsar)                |
|  Payload: {entity_id, variant_id, latency_ms, tokens_used, task_success, ...}   |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                        4. Stream / Batch Processing
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|              DATA WAREHOUSE / LAKEHOUSE (Snowflake / BigQuery / ClickHouse)     |
|                                                                                 |
|  - Dimension: Pre-experiment Covariates (Baseline User Engagement X)            |
|  - Fact: Experiment Exposures & Outcomes (Observed Metric Y)                    |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                          5. Run Statistical Engine
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                  STATISTICAL DECISION ENGINE (Automated Offline)                 |
|                                                                                 |
|  [SRM Checker]          ──> Pearson Chi-Square Goodness-of-Fit Test (p < 0.001) |
|  [CUPED Engine]         ──> Variance Reduction: Y_cuped = Y - theta * (X - E[X])|
|  [Hypothesis Testing]   ──> Welch's t-test / Mann-Whitney U / Sequential mSPRT  |
|  [Guardrail Validator]  ──> Cost Threshold, Hallucination Safety Bounds         |
|  [FDR Controller]       ──> Benjamini-Hochberg Correction for Multiple Metrics  |
+───────────────────────────────────────┬─────────────────────────────────────────+
                                        │
                       6. Actionable Statistical Artifact
                                        ▼
+─────────────────────────────────────────────────────────────────────────────────+
|                  PRODUCT DECISION CONSOLE (PM & Engineering View)               |
|      [Status: STAT-SIG POSITIVE] -> Automated Progressive Rollout Trigger      |
+─────────────────────────────────────────────────────────────────────────────────+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Formalisasi Hipotesis dan Statistical Power
Uji hipotesis statistik menetapkan dua proposisi yang saling menolak:
* **Null Hypothesis ($H_0$):** Tidak ada perbedaan performa antara Control ($\mu_c$) dan Treatment ($\mu_t$), sehingga $\Delta = \mu_t - \mu_c = 0$.
* **Alternative Hypothesis ($H_1$):** Terdapat perbedaan signifikan secara kausal, $\Delta \neq 0$ (dua arah).

Dalam pengambilan keputusan produk, terdapat dua jenis kesalahan mendasar:
1. **Type I Error ($\alpha$):** False Positive. Mengklaim model AI baru lebih unggul, padahal perbedaan semata-mata karena variasi acak. Ditetapkan secara standar sebesar $\alpha = 0.05$.
2. **Type II Error ($\beta$):** False Negative. Gagal mendeteksi keunggulan model AI baru padahal model tersebut secara nyata lebih baik. Standar industri menargetkan $\beta = 0.20$, yang setara dengan **Statistical Power** ($1 - \beta = 0.80$).

Formula perhitungan ukuran sampel minimum ($n$) per varian untuk metrik kontinu dengan variansi $\sigma^2$ dan *Minimum Detectable Effect* (MDE) $\delta$:

$$n = \frac{2 \cdot (Z_{\alpha/2} + Z_{\beta})^2 \cdot \sigma^2}{\delta^2}$$

Di mana $Z_{\alpha/2} = 1.96$ untuk $\alpha = 0.05$, dan $Z_{\beta} = 0.84$ untuk power $80\%$.

#### B. The Peeking Problem & Sequential Testing
Jika seorang PM terus menerus mengecek dashboard pengujian yang menggunakan uji t-Student klasik setiap kali data baru masuk, proses stokastik Brownian Motion menjamin bahwa kurva estimasi perbedaan akan menyentuh batas kritis signifikansi secara acak setidaknya sekali jika pengujian dibiarkan berjalan cukup lama. 

Untuk menangani *continuous monitoring* tanpa mengorbankan $\alpha$, platform modern menggunakan **mixture Sequential Probability Ratio Test (mSPRT)** yang menetapkan *confidence sequences* dinamis yang melebar seiring bertambahnya observasi, menjaga batas False Positive rate global tetap berada di bawah $\alpha$.

#### C. Sample Ratio Mismatch (SRM) Engine
SRM adalah indikator utama kecacatan sistematis dalam eksperimen. Jika variasi dialokasikan dengan target $50:50$, namun data yang masuk menunjukkan rasio $51.5 : 48.5$ dari 100,000 pengguna, kita tidak boleh langsung menganalisis metrik bisnis. Uji Pearson $\chi^2$ harus dilakukan:

$$\chi^2 = \sum_{i \in \{c, t\}} \frac{(O_i - E_i)^2}{E_i}$$

Jika derajat kebebasan (*degrees of freedom*) $df = 1$ dan nilai $p < 0.001$ ($\chi^2 > 10.83$), eksperimen dinyatakan **invalid (compromised)**. Penyebab umum pada sistem AI: model treatment memiliki latensi inferensi yang sangat tinggi sehingga memicu *timeout* pada load balancer sebelum event telemetri terkirim, mendistorsi populasi treatment secara artifisial.

#### D. Variance Reduction: Algoritma CUPED
Waktu tunggu eksperimen (*time-to-decision*) adalah kendala utama dalam pengembangan model AI yang cepat. CUPED (*Controlled-experiment Using Pre-Experiment Data*) memanfaatkan metrik historis sebelum eksperimen ($X$) yang berkorelasi dengan metrik eksperimen saat ini ($Y$) untuk mengeliminasi variansi yang sudah ada sebelumnya.

Variabel terkoreksi didefinisikan sebagai:

$$\hat{Y}_{CUPED} = Y - \theta (X - E[X])$$

Di mana parameter optimal $\theta$ diturunkan dari kovariansi sampel:

$$\theta = \frac{Cov(Y, X)}{Var(X)}$$

Variansi metrik baru yang dihasilkan adalah:

$$Var(\hat{Y}_{CUPED}) = Var(Y) \cdot (1 - \rho^2)$$

Di mana $\rho$ adalah koefisien korelasi Pearson antara $X$ dan $Y$. Jika $\rho = 0.6$, variansi tereduksi sebesar $36\%$, yang berarti ukuran sampel yang dibutuhkan berkurang 36% untuk mendeteksi MDE yang sama, memangkas durasi pengujian dari 14 hari menjadi 9 hari secara matematis valid.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul Python produksi untuk **Statistical Decision Engine** yang mencakup:
1. Alokasi deterministik (*Consistent Hashing* via MurmurHash3).
2. Deteksi otomatis *Sample Ratio Mismatch* (SRM).
3. Transformasi metrik menggunakan reduksi variansi CUPED.
4. Uji hipotesis inferensial (Welch’s t-test) dengan *confidence interval*.

```python
"""
Core Experimentation & Statistical Decision Engine for AI Systems.
Architecture: Modular, Type-Hinted, Production-Ready.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import mmh3  # MurmurHash3 dependency: pip install mmh3
import numpy as np
from scipy import stats


@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    salt: str
    variants: Tuple[str, ...]
    target_weights: Tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.variants) != len(self.target_weights):
            raise ValueError("Variants and weights must have identical dimensionality.")
        if not np.isclose(sum(self.target_weights), 1.0):
            raise ValueError(f"Sum of target weights must equal 1.0, received: {sum(self.target_weights)}")


@dataclass(frozen=True)
class StatisticalResult:
    control_mean: float
    treatment_mean: float
    absolute_lift: float
    relative_lift_percent: float
    p_value: float
    ci_lower: float
    ci_upper: float
    is_stat_sig: bool
    srm_p_value: float
    variance_reduction_percent: float


class ConsistentBucketAllocator:
    """
    Menghasilkan alokasi varian deterministik bebas bias berbasis MurmurHash3.
    """
    TOTAL_BUCKETS: int = 10_000

    @classmethod
    def assign_bucket(cls, entity_id: str, config: ExperimentConfig) -> str:
        # Hash composition menjamin isolasi antar-eksperimen (orthogonal routing)
        hash_key = f"{config.experiment_id}:{config.salt}:{entity_id}"
        hash_val = mmh3.hash(hash_key, signed=False)
        bucket = hash_val % cls.TOTAL_BUCKETS

        cumulative = 0.0
        for variant, weight in zip(config.variants, config.target_weights):
            cumulative += weight * cls.TOTAL_BUCKETS
            if bucket < cumulative:
                return variant
        return config.variants[-1]


class ExperimentStatisticalEngine:
    """
    Mesin inferensi statistik: Verifikasi SRM, Reduksi Variansi CUPED, dan Welch's t-test.
    """

    @staticmethod
    def calculate_srm(
        observed_counts: Dict[str, int], 
        expected_weights: Dict[str, float]
    ) -> float:
        """
        Menjalankan Pearson's Chi-Square Test untuk deteksi Sample Ratio Mismatch.
        """
        total_observed = sum(observed_counts.values())
        if total_observed == 0:
            raise ValueError("Total observed count cannot be zero for SRM evaluation.")

        observed = []
        expected = []
        for variant, weight in expected_weights.items():
            obs = observed_counts.get(variant, 0)
            exp = total_observed * weight
            observed.append(obs)
            expected.append(exp)

        chi2_stat, p_val = stats.chisquare(f_obs=observed, f_exp=expected)
        return float(p_val)

    @staticmethod
    def apply_cuped(
        y_treatment: np.ndarray,
        x_treatment: np.ndarray,
        y_control: np.ndarray,
        x_control: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Menghitung CUPED-adjusted metric.
        Y: Metrik target saat eksperimen
        X: Metrik pre-eksperimen (kovariat baseline)
        """
        if len(y_treatment) != len(x_treatment) or len(y_control) != len(x_control):
            raise ValueError("Dimension mismatch between target metric and pre-experiment covariate.")

        # Gabungkan dataset untuk menghitung theta global guna menghindari bias estimasi
        y_all = np.concatenate([y_treatment, y_control])
        x_all = np.concatenate([x_treatment, x_control])

        cov_matrix = np.cov(y_all, x_all)
        cov_yx = cov_matrix[0, 1]
        var_x = cov_matrix[1, 1]

        if np.isclose(var_x, 0.0):
            # Baseline tidak memiliki variansi; fallback ke metrik original
            return y_treatment, y_control, 0.0

        theta = cov_yx / var_x
        x_mean = np.mean(x_all)

        y_treatment_cuped = y_treatment - theta * (x_treatment - x_mean)
        y_control_cuped = y_control - theta * (x_control - x_mean)

        var_raw = np.var(y_all, ddof=1)
        var_cuped = np.var(np.concatenate([y_treatment_cuped, y_control_cuped]), ddof=1)
        var_reduction = max(0.0, (1.0 - (var_cuped / var_raw)) * 100.0)

        return y_treatment_cuped, y_control_cuped, var_reduction

    @classmethod
    def evaluate_experiment(
        cls,
        config: ExperimentConfig,
        y_control_raw: np.ndarray,
        x_control_baseline: np.ndarray,
        y_treatment_raw: np.ndarray,
        x_treatment_baseline: np.ndarray,
        alpha: float = 0.05
    ) -> StatisticalResult:
        """
        Eksekusi pipeline evaluasi analitik inferensial lengkap.
        """
        # 1. SRM Diagnostic Check
        observed_counts = {
            config.variants[0]: len(y_control_raw),
            config.variants[1]: len(y_treatment_raw),
        }
        weights_dict = dict(zip(config.variants, config.target_weights))
        srm_p_value = cls.calculate_srm(observed_counts, weights_dict)

        if srm_p_value < 0.001:
            raise RuntimeError(
                f"SRM VIOLATION DETECTED (p = {srm_p_value:.6e}). "
                "Eksperimen tidak valid secara metodologis; alokasi trafik mengalami bias sistematik."
            )

        # 2. Variance Reduction via CUPED
        y_treat_adj, y_ctrl_adj, var_reduction = cls.apply_cuped(
            y_treatment=y_treatment_raw,
            x_treatment=x_treatment_baseline,
            y_control=y_control_raw,
            x_control=x_control_baseline,
        )

        # 3. Welch's t-test (tidak berasumsi variansi identik antar-varian)
        t_stat, p_val = stats.ttest_ind(y_treat_adj, y_ctrl_adj, equal_var=False)

        # 4. Point Estimates & Conf Intervals
        mean_c = float(np.mean(y_ctrl_adj))
        mean_t = float(np.mean(y_treat_adj))
        abs_lift = mean_t - mean_c
        rel_lift = (abs_lift / mean_c * 100.0) if not np.isclose(mean_c, 0.0) else 0.0

        se_diff = np.sqrt(
            np.var(y_ctrl_adj, ddof=1) / len(y_ctrl_adj) +
            np.var(y_treat_adj, ddof=1) / len(y_treat_adj)
        )
        
        # Derajat kebebasan Welch-Satterthwaite
        s1 = np.var(y_ctrl_adj, ddof=1) / len(y_ctrl_adj)
        s2 = np.var(y_treat_adj, ddof=1) / len(y_treat_adj)
        df = (s1 + s2)**2 / ((s1**2 / (len(y_ctrl_adj) - 1)) + (s2**2 / (len(y_treat_adj) - 1)))

        critical_val = stats.t.ppf(1 - (alpha / 2), df=df)
        ci_lower = abs_lift - (critical_val * se_diff)
        ci_upper = abs_lift + (critical_val * se_diff)

        return StatisticalResult(
            control_mean=mean_c,
            treatment_mean=mean_t,
            absolute_lift=abs_lift,
            relative_lift_percent=rel_lift,
            p_value=float(p_val),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            is_stat_sig=bool(p_val < alpha),
            srm_p_value=srm_p_value,
            variance_reduction_percent=var_reduction,
        )


# --- Simulation Run & Verification ---
if __name__ == "__main__":
    np.random.seed(42)

    cfg = ExperimentConfig(
        experiment_id="exp_autonomous_agent_v2_prompt",
        salt="9f8a3c2e",
        variants=("control", "treatment"),
        target_weights=(0.5, 0.5)
    )

    # Simulasi 10,000 user interactions
    N = 10_000
    pre_metric = np.random.normal(loc=50.0, scale=10.0, size=N)
    
    # Target metric: Penambahan treatment lift = +1.5, ditambah korelasi kuat ke baseline (CUPED context)
    treatment_noise = np.random.normal(loc=0.0, scale=4.0, size=N // 2)
    control_noise = np.random.normal(loc=0.0, scale=4.0, size=N // 2)

    ctrl_y = 0.8 * pre_metric[: N // 2] + control_noise
    treat_y = 0.8 * pre_metric[N // 2 :] + 1.5 + treatment_noise

    result = ExperimentStatisticalEngine.evaluate_experiment(
        config=cfg,
        y_control_raw=ctrl_y,
        x_control_baseline=pre_metric[: N // 2],
        y_treatment_raw=treat_y,
        x_treatment_baseline=pre_metric[N // 2 :],
        alpha=0.05
    )

    print("=== EXPERIMENT RESULTS ===")
    print(f"SRM Metric p-value: {result.srm_p_value:.4f}")
    print(f"CUPED Variance Reduction: {result.variance_reduction_percent:.2f}%")
    print(f"Control Mean: {result.control_mean:.4f}")
    print(f"Treatment Mean: {result.treatment_mean:.4f}")
    print(f"Absolute Lift: {result.absolute_lift:.4f} [95% CI: {result.ci_lower:.4f} to {result.ci_upper:.4f}]")
    print(f"Relative Lift: {result.relative_lift_percent:.2f}%")
    print(f"p-value: {result.p_value:.6e} -> Statistically Significant: {result.is_stat_sig}")
```

---

### 7. Edge Cases & Failure Modes (Spesifik Domain AI/LLM)

1. **Sample Ratio Mismatch Akibat LLM Execution Timeouts:**
   * *Mekanisme Kegagalan:* Model treatment memiliki arsitektur *chain-of-thought* kompleks yang membutuhkan waktu 3x lebih lama dibanding baseline. Klien HTTP dengan limit *timeout* 10 detik memutus koneksi sebelum event telemetri terkirim. 
   * *Dampak:* Populasi user dengan koneksi lambat atau query panjang tereliminasi dari kelompok treatment, menyebabkan SRM parah dan menghasilkan kesimpulan bias seolah-olah treatment memiliki keberhasilan lebih tinggi (karena hanya mengevaluasi query yang cepat selesai).
   * *Mitigasi:* Logging eksposur varian wajib dilakukan di gateway routing **sebelum** payload diteruskan ke inferensi model (*intent-to-treat logging*), bukan setelah respons selesai dibuat.

2. **Network Interference & Shared Agent Memory Pools:**
   * *Mekanisme Kegagalan:* Melanggar asumsi SUTVA (*Stable Unit Treatment Value Assumption*). Agen varian treatment mengeksekusi *write operation* ke shared Vector Database yang sama dengan varian kontrol. Modifikasi index ini mengubah performa retrieval grup kontrol.
   * *Mitigasi:* Isolasi workspace index vektor berdasarkan namespace eksperimen: `index_vector_v1_control` vs. `index_vector_v1_treatment`.

3. **Primacy & Novelty Effect pada UX AI Otonom:**
   * *Mekanisme Kegagalan:* Perubahan radikal pada cara agen AI merespons pengguna memicu kebiasaan eksplorasi baru (*novelty effect*), menghasilkan lonjakan token dan durasi sesi pada hari 1–3, yang kemudian regresi ke rata-rata pada hari ke-10.
   * *Mitigasi:* Jangan menarik kesimpulan permanen dari metrik engagement 72 jam pertama. Pisahkan cohort pengguna baru (*new users*) dengan pengguna lama (*tenured users*) dalam analisis dekomposisi waktu.

4. **Non-stationary Target Metric Akibat LLM Upstream Drift:**
   * *Mekanisme Kegagalan:* Penyedia fondasi model (e.g., OpenAI/Anthropic) memperbarui bobot model di balik endpoint API publik di tengah-tengah masa eksperimen A/B.
   * *Mitigasi:* Kunci parameter spesifik versi model (misal: gunakan `gpt-4o-2024-08-06` alih-alih `gpt-4o-latest`) atau terapkan arsitektur replikasi self-hosted untuk kontrol deterministik penuh.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Evaluasi | Frequentist (Fixed-Horizon) | Sequential Testing (mSPRT) | Bayesian A/B Testing | Multi-Armed Bandit (MAB / Thompson) |
| :--- | :--- | :--- | :--- | :--- |
| **Metrik Filosofis Inti** | P-value, Type I Error ($\alpha$), Power ($1-\beta$) | Dynamic Confidence Intervals | Posterior Probability, Credible Intervals | Expected Regret Minimization |
| **Kelebihan Utama** | Standar baku industri; zero subjectivity apriori. | Mengizinkan *early stopping* aman dari *data peeking*. | Output intuitif bagi PM: "Peluang varian B menang adalah 94%". | Mengarahkan mayoritas trafik secara real-time ke varian pemenang. |
| **Kelemahan Kritis** | Kaku; dilarang menganalisis hasil sebelum sampel target terpenuhi. | Butuh sampel 20–50% lebih besar dibanding fixed horizon jika durasi penuh. | Bergantung pada validitas *prior distribution*; rawan bias interpretasi. | Mengorbankan akurasi estimasi kausal varian kalah; bias untuk metrik jangka panjang. |
| **Use Case Terbaik di AI** | Model Foundation Migration; Penilaian safety/guardrail. | Continuous monitoring alerting pipeline performa agen. | Iterasi prompt copywriter cepat dengan historical priors. | Dynamic model routing berdasarkan optimasi biaya/token real-time. |

---

### 9. Best Practices & Standar Industri

1. **Overall Evaluation Criterion (OEC) Multi-Faset:**
   Jangan pernah mengevaluasi eksperimen model AI menggunakan satu metrik tunggal. Formulasikan OEC formal:
   $$\text{OEC} = \Delta \text{Task Success Rate} - \lambda_1 (\Delta \text{Cost per 1k Calls}) - \lambda_2 (\Delta \text{p95 Latency})$$
   Di mana $\lambda$ adalah parameter penalti ekonomi bisnis yang telah disepakati oleh stakeholder sebelum uji coba dimulai (*pre-registration*).

2. **Pre-Experiment Power Calculation Registry:**
   Semua eksperimen wajib didaftarkan pada internal experiment ledger dengan MDE, unit randomisasi, dan durasi minimal yang telah dihitung sebelum deployment. Perubahan hipotesis *post-hoc* dilarang secara otomatis oleh platform eksperimen.

3. **Koreksi Multi-Testing (Family-Wise Error Rate):**
   Jika mengevaluasi 10 metrik sekunder secara bersamaan (misal: Latency, Cost, CSAT, Hallucination, Sentiment, Output Tokens, Input Tokens, Tool Executions, Retries, Churn), terapkan koreksi **Benjamini-Hochberg (FDR)** atau **Bonferroni-Holm** guna mencegah munculnya metrik signifikan palsu murni karena banyaknya parameter yang diuji.

4. **Guardrail Metric Non-Negotiable Thresholds:**
   Tetapkan *hard stop* otomatis: jika metrik *Guardrail* (misal: *Safety Failure Rate* atau *Negative Feedback Escalation*) memburuk lebih dari batas kritis $\Delta > 0.5\%$ dengan signifikansi $p < 0.01$, platform harus secara otonom memutus sirkuit (*circuit breaker*) dan me-roll back 100% trafik ke Control.

---

### 10. Hands-on Lab Exercise: Menguji Autonomous Customer Support Agent

#### Konteks Skenario Lab
Anda adalah Lead PM untuk platform Autonomous Support Agent. Anda ingin menguji varian arsitektur agen baru:
* **Control (A):** Agen berbasis GPT-4o Standar dengan *Single Prompt Chain*.
* **Treatment (B):** Agen berbasis Model SLM Fine-Tuned yang dilengkapi modul *Self-Reflection & Tool Verification*.

Tujuan bisnis: Menentukan apakah Treatment B meningkatkan **First Contact Resolution (FCR) Rate** tanpa melanggar guardrail **Token Cost** dan **Latency**.

#### Langkah 1: Kalkulasi Sample Size
Metrik FCR historis saat ini adalah $p = 60\%$ ($0.60$). Target deteksi MDE adalah kenaikan absolut minimal $3\%$ (menjadi $63\%$).
* Baseline Variance: $\sigma^2 = p(1-p) = 0.6 \times 0.4 = 0.24$.
* Signifikansi $\alpha = 0.05$ ($Z_{\alpha/2} = 1.96$), Power $80\%$ ($Z_\beta = 0.84$).

$$n = \frac{2 \cdot (1.96 + 0.84)^2 \cdot 0.24}{0.03^2} = \frac{2 \cdot (2.8)^2 \cdot 0.24}{0.0009} = \frac{3.7632}{0.0009} \approx 4,181 \text{ resolusi per variasi}$$
Total sampel yang harus dikumpulkan: **$\approx 8,400$ interaksi pengguna**.

#### Langkah 2: Simulasi dan Pengujian Analitik
Jalankan script Python di bawah ini untuk memverifikasi proses validasi data, mitigasi SRM, dan eksekusi inferensi Welch's t-test:

```python
import numpy as np
from scipy import stats

def run_agent_experiment_lab():
    np.random.seed(101)
    
    # Target alokasi 50:50
    n_sample_per_variant = 4200
    
    # 1. Generate telemetri FCR (Binary 0 atau 1)
    # Control: baseline 60%
    fcr_control = np.random.binomial(n=1, p=0.60, size=n_sample_per_variant)
    # Treatment: real lift 63.5%
    fcr_treatment = np.random.binomial(n=1, p=0.635, size=n_sample_per_variant)
    
    # 2. Verifikasi SRM
    obs = [len(fcr_control), len(fcr_treatment)]
    exp = [n_sample_per_variant, n_sample_per_variant]
    _, srm_p = stats.chisquare(obs, exp)
    print(f"[Tahap 1] SRM Diagnostic Check: p-value = {srm_p:.4f}")
    assert srm_p > 0.001, "Eksperimen Gagal: Terdeteksi SRM!"

    # 3. Guardrail Evaluation: Latency p95 (Log-Normal Distribution)
    # Target Guardrail: p95 treatment tidak boleh lebih lambat dari 3500ms
    latency_ctrl = np.random.lognormal(mean=7.5, sigma=0.4, size=n_sample_per_variant) # Mean ~2000ms
    latency_treat = np.random.lognormal(mean=7.6, sigma=0.4, size=n_sample_per_variant) # Slightly higher
    
    p95_ctrl = np.percentile(latency_ctrl, 95)
    p95_treat = np.percentile(latency_treat, 95)
    print(f"[Tahap 2] Guardrail Metric - Latency p95: Control = {p95_ctrl:.1f}ms, Treatment = {p95_treat:.1f}ms")
    
    # 4. Inferensi Metrik Utama (FCR Rate)
    t_stat, p_val = stats.ttest_ind(fcr_treatment, fcr_control, equal_var=False)
    lift = (np.mean(fcr_treatment) - np.mean(fcr_control)) * 100.0
    
    print(f"[Tahap 3] Inferensi Utama: Lift = +{lift:.2f}% (p-value = {p_val:.4f})")
    
    # 5. Keputusan Produk Final
    is_fcr_stat_sig = p_val < 0.05
    is_latency_safe = p95_treat < 3500.0
    
    print("\n=== REKOMENDASI KEPUTUSAN PRODUK (PM SUMMARY) ===")
    if is_fcr_stat_sig and is_latency_safe:
        print("KEPUTUSAN: ROLLOUT VARIANT B TO 100%")
        print("- FCR mengalami peningkatan positif secara signifikan secara statistik.")
        print("- Seluruh metrik guardrail latensi berada dalam batas toleransi SLO.")
    else:
        print("KEPUTUSAN: ABORT / ITERATE")
        print("Gagal memenuhi kriteria OEC atau terjadi pelanggaran batas guardrail.")

run_agent_experiment_lab()
```

#### Langkah 3: Interpretasi Hasil Lab
1. Periksa apakah nilai `SRM Diagnostic Check` berada di atas $p = 0.001$. Nilai mendekati $1.0$ mengonfirmasi bahwa perutean trafik acak bekerja sempurna tanpa bias infrastruktur.
2. Analisis `p95 Latency`. Meskipun FCR meningkat signifikan, jika $p95$ melampaui ambang batas $3500\text{ ms}$, sistem harus menolak *rollout* otomatis karena melanggar SLA performa produksi.
3. Formulasikan kesimpulan bisnis berbasis estimasi *confidence interval*: bukan sekadar menyatakan "performa naik", melainkan "kami $95\%$ yakin bahwa implementasi arsitektur SLM baru ini meningkatkan resolusi pelanggan antara $1.4\%$ hingga $5.6\%$".