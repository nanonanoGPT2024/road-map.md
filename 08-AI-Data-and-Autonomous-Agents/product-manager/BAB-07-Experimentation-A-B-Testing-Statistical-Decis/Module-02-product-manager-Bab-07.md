# Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi: Sistem Eksperimentasi & Pengambilan Keputusan Statistik untuk AI & Autonomous Agents

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Technical Product Manager (AI/Data TPM) dan Lead Engineer akan mampu:
1. **Merancang Arsitektur Experimentation Engine Skala Enterprise**: Membangun sistem alokasi varian berbasis *deterministic hash bucketing* (MurmurHash3) dengan zero-cross-contamination, isolasi lapisan (*multi-layer experimentation*), dan latensi desisi di bawah 5 milidetik ($p99 < 5\text{ ms}$).
2. **Mengatasi Non-Determinisme AI & Autonomous Agents**: Mengimplementasikan framework evaluasi statistik adaptif yang memitigasi varians intrinsik LLM (*output variance*), *stochastic latency*, dan biaya inferensi token melalui *guardrail metrics*.
3. **Menguasai Metode Reduksi Varians (CUPED) & Sequential Testing**: Mengakselerasi siklus rilis eksperimen hingga 40-50% lebih cepat menggunakan *Controlled-experiment Using Pre-Experiment Data* (CUPED) serta mengeliminasi bahaya *peeking problem* melalui *Sequential Probability Ratio Test* (SPRT) atau *Bayesian stopping rules*.
4. **Mendeteksi & Memitigasi Anomali Eksperimen Secara Otomatis**: Membangun mekanisme otomatis untuk mendeteksi *Sample Ratio Mismatch* (SRM), *novelty effect*, *carryover effect*, dan kebocoran graf interaksi (*network effect spillovers*).
5. **Menyeimbangkan Eksplorasi vs. Eksploitasi**: Mengonfigurasi algoritma Contextual Multi-Armed Bandits (MAB) dan Thompson Sampling pada pipeline routing LLM guna memaksimalkan *reward metric* secara dinamis tanpa mengorbankan integritas data kausal.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* **Statistika Inferensial Lanjutan**: Pemahaman mendalam mengenai Uji Hipotesis ($p$-value, Type I Error $\alpha$, Type II Error $\beta$, Statistical Power $1-\beta$), Distribusi Normal, Binomial, Student's t-test, dan Chi-Square Goodness-of-Fit.
* **Arsitektur Sistem Terdistribusi**: Konsep latensi jaringan, *edge computing*, Redis/In-Memory Caching, message brokers (Kafka/Pulsar), dan *event-driven telemetry*.
* **Dasar AI/LLM Systems**: Siklus hidup inferensi LLM, struktur prompt, context window, token economics, serta metrik evaluasi offline seperti ROUGE, BLEU, G-Eval, dan cosine similarity embeddings.
* **Bahasa Pemrograman & Query**: Kemahiran menengah-tinggi dalam Python (NumPy, SciPy, Pandas, Statsmodels) dan SQL analitis tingkat lanjut (Window Functions, Aggregations).

---

## 3. Concept & Internal Architecture

Dalam lanskap AI dan Agen Otonom, eksperimentasi bukan sekadar pengujian A/B tombol warna antarmuka web. Eksperimentasi pada tingkat ini melibatkan pengujian hipotesis terhadap komponen stokastik: perbandingan performa model (misalnya GPT-4o vs Claude 3.5 Sonnet), arsitektur RAG (vektor retrieval dense vs hybrid BM25 + dense reranking), hingga parameter penalaran agen (Chain-of-Thought vs ReAct step limits).

### 3.1. Deterministic Hash Bucketing & Multi-Layer Isolation
Arsitektur engine modern menghindari penyimpanan status pembagian varian (*stateful database lookup*) saat evaluasi traffic pengguna. Engine menggunakan hashing deterministik:
$$\text{bucket\_id} = \text{MurmurHash3}(\text{entity\_id} + \text{layer\_salt} + \text{experiment\_id}) \pmod{10000}$$

```
+-------------------------------------------------------------------------------+
|                             REQUEST INGESTION                                 |
|                       (User ID / Org ID / Agent Session)                      |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                       EVALUATION ENGINE (Edge / Sidecar)                      |
|                                                                               |
|  [ Layer 1: Routing Model ]      MurmurHash3(UserID + "Layer1_Salt") % 100    |
|  +--------------------+---------------------+                                 |
|  | Variant A: GPT-4o  | Variant B: Claude3.5|                                 |
|  +--------------------+---------------------+                                 |
|                                                                               |
|  [ Layer 2: RAG Pipeline ]       MurmurHash3(UserID + "Layer2_Salt") % 100    |
|  +--------------------+---------------------+                                 |
|  | Dense Hybrid Rerank| Sparse Dense Only   |                                 |
|  +--------------------+---------------------+                                 |
+---------------------------------------+---------------------------------------+
                                        |
                 +----------------------+----------------------+
                 | Nonce Token Injection                       | Real-Time Exposure Event
                 v                                             v
+---------------------------------+           +---------------------------------+
| LLM INFERENCE GATEWAY           |           | TELEMETRY BUS (Kafka)           |
| (Executes Selected Pipeline)    |           | topic: experiment.exposures     |
+---------------------------------+           +---------------------------------+
```

Lapisan (*Layering*) memungkinkan eksekusi puluhan eksperimen secara simultan tanpa korelasi silang antar eksperimen (*orthogonality*), selama nilai `layer_salt` saling independen secara kriptografis.

### 3.2. Formulasi CUPED (Controlled-experiment Using Pre-Experiment Data)
Metrik performa agen sering kali memiliki varians tinggi karena variasi kompleksitas tugas pengguna. Untuk meningkatkan *statistical power* tanpa memperbanyak ukuran sampel, diterapkan teknik CUPED. 

Jika $Y$ adalah metrik selama periode eksperimen (misalnya: *Task Completion Rate* atau *Latency*), dan $X$ adalah metrik yang sama (atau berkorelasi kuat) dari pengguna yang sama **sebelum** eksperimen dimulai, estimator CUPED $\hat{Y}_{CUPED}$ didefinisikan sebagai:
$$\hat{Y}_{CUPED} = Y - \theta (X - E[X])$$

Di mana koefisien optimal $\theta$ diturunkan dari kovarians sampel:
$$\theta = \frac{\operatorname{Cov}(Y, X)}{\operatorname{Var}(X)}$$

Varians dari metrik tereduksi sebesar faktor korelasi $\rho$:
$$\operatorname{Var}(\hat{Y}_{CUPED}) = \operatorname{Var}(Y) (1 - \rho^2)$$
Jika korelasi antara performa historis pengguna dan performa saat ini adalah $\rho = 0.7$, varians tereduksi sebesar $1 - 0.7^2 = 51\%$. Artinya, ukuran sampel yang diperlukan untuk mencapai signifikansi statistik terpangkas lebih dari setengahnya.

---

## 4. Why & What

| Dimensi | A/B Testing Konvensional (Software Klasik) | Eksperimentasi AI & Autonomous Agents |
| :--- | :--- | :--- |
| **Sifat Output** | Deterministik (HTML, JSON, UI Button, Static Logic). | Non-deterministik/Stokastik (Generasi token LLM bervariasi). |
| **Metrik Keberhasilan** | Click-Through Rate (CTR), Conversion Rate, Retention. | Evaluasi Semantik (LLM-as-a-Judge, Groundedness), Tool Execution Success, Latency to First Token (TTFT). |
| **Dimensi Risiko Finansial** | Biaya komputasi server stabil dan terprediksi. | Fluktuasi pengeluaran token API secara eksponensial (*Token Budget Drift*). |
| **Deteksi Kegagalan** | HTTP 5xx errors, Application Crash, Page Drop-off. | Halusinasi parsial, pelanggaran safety guardrails, *infinite loop execution* pada autonomous agent. |
| **Metodologi Pembagian** | Traffic level HTTP (Cookie, IP, Session ID). | Context-aware routing (Panjang context token, task complexity, tenant budget tier). |

### Mengapa AI Product Manager Wajib Menguasai Sistem Ini?
1. **Eliminasi Bias Subjektif**: Menguji apakah arsitektur *Reasoning Engine* baru benar-benar mengoptimalkan akurasi atau sekadar menghasilkan output yang terdengar lebih meyakinkan secara retoris bagi reviewer internal.
2. **Optimasi Biaya Satuan (*Unit Economics*)**: Menentukan titik temu trade-off antara akurasi model berukuran besar vs model terdistilasi (misalnya: Llama-3-70B vs Llama-3-8B fine-tuned) pada skala jutaan transaksi.
3. **Pencegahan Silent Failures**: Mencegah degradasi kualitas sistem agen secara dini sebelum berdampak pada Customer Lifetime Value (LTV).

---

## 5. How (Workflow Detail)

Siklus hidup eksperimentasi produksi AI terbagi dalam 6 fase kontinu:

```
[ Phase 1: Pre-Flight ]
       │  • Penentuan MDE (Minimum Detectable Effect) & Power Analysis
       │  • Definisi Guardrail Metrics (Cost per 1k query, Max TTFT, Safety Score)
       ▼
[ Phase 2: Variant Assignment ]
       │  • Stateless MurmurHash3 calculation di Edge/Gateway
       │  • Pengecekan Mutual Exclusion & User Segmentation
       ▼
[ Phase 3: Telemetry Egress ]
       │  • Logging event `Exposure` secara real-time via Apache Kafka
       │  • Asosiasi Trace ID dari LLM Gateway (Prompt tokens, Completion tokens)
       ▼
[ Phase 4: Automated Health Monitoring ]
       │  • Monitoring Chi-Square Sample Ratio Mismatch (SRM) per 5 menit
       │  • Auto-kill switch aktif jika Guardrail Metric terlanggar
       ▼
[ Phase 5: Statistical Processing ]
       │  • Normalisasi Varians menggunakan CUPED
       │  • Evaluasi p-value / Posterior Distribution (Bayesian) via Spark/Trino
       ▼
[ Phase 6: Decision & Rollout ]
          • Gradual rollout via Canary Release (10% -> 25% -> 50% -> 100%)
          • Pencatatan Metadata Model Registry & Pembaharuan Baseline Data
```

### Prosedur Mitigasi Sample Ratio Mismatch (SRM)
Sample Ratio Mismatch terjadi ketika rasio sampel observasi aktual menyimpang drastis dari rasio alokasi yang telah dirancang (misalnya: target 50:50, aktual 48:52 pada skala $N=500.000$).
1. Sistem menghitung statistik Chi-Square Goodness-of-Fit secara berkala:
   $$\chi^2 = \sum \frac{(O_i - E_i)^2}{E_i}$$
2. Jika nilai $p$-value $<\alpha_{\text{SRM}}$ (umumnya diatur pada $\alpha = 0.001$), sistem langsung membunyikan alert tingkat P1 dan menghentikan pengujian secara otomatis (*halt experiment*).
3. **Akar Masalah SRM pada Sistem AI**: Varian model yang lebih lambat mengalami request timeout di level gateway, sehingga event exposure untuk varian tersebut gagal terkirim (*silent client-side drop*).

---

## 6. Analogy & Diagram ASCII

Bayangkan eksperimentasi sistem agen seperti ruang uji klinis obat di rumah sakit terpadu:

```
+--------------------------------------------------------------------------+
|                          POPULASI PASIEN (Traffic)                       |
+--------------------------------------------------------------------------+
                                     |
               +---------------------+---------------------+
               | (Mesin Pengacak Genetik - Hash Layer 1)    |
               v                                           v
     +-------------------+                       +-------------------+
     | KELOMPOK KONTROL  |                       | KELOMPOK PERLAKUAN|
     | (Agent Reguler)   |                       | (Agent ReAct Baru)|
     +---------+---------+                       +---------+---------+
               |                                           |
    [Pre-Treatment Scan]                        [Pre-Treatment Scan]
    Rekam jejak komorbiditas                    Rekam jejak komorbiditas
    (Data Historis CUPED - X)                   (Data Historis CUPED - X)
               |                                           |
               v                                           v
       Eksekusi Terapi                             Eksekusi Terapi
               │                                           │
    [Detektor Efek Samping]                     [Detektor Efek Samping]
    Tekanan darah melonjak?                     Biaya token membengkak?
    (Guardrail Alert Trigger)                   (Guardrail Alert Trigger)
               │                                           │
               v                                           v
     [Hasil Akhir Pasien]                        [Hasil Akhir Pasien]
    Skor Kesembuhan (Y)                         Skor Kesembuhan (Y)
               │                                           │
               +---------------------+---------------------+
                                     v
                        [ANALISIS VARIANS CUPED]
               Eliminasi efek komorbiditas masa lalu
             sehingga selisih murni terapi terisolasi!
```

---

## 7. Simple Example & Practical Example

### 7.1. Simple Example: In-Memory MurmurHash3 Assignment Engine
Implementasi algoritma bucketing deterministik tanpa dependensi database eksternal:

```python
import mmh3

class BucketingEngine:
    def __init__(self, salt: str):
        self.salt = salt

    def get_variant(self, entity_id: str, experiment_id: str, traffic_split: dict[str, float]) -> str:
        """
        Menghitung varian secara deterministik.
        traffic_split: misal {"control": 0.5, "treatment": 0.5}
        """
        # Gabungkan entity_id, salt, dan experiment_id untuk isolasi
        hash_input = f"{self.salt}:{experiment_id}:{entity_id}"
        # MurmurHash3 menghasilkan signed 32-bit int, konversi ke rentang [0, 9999]
        hash_val = mmh3.hash(hash_input) & 0xFFFFFFFF
        bucket = (hash_val % 10000) / 10000.0

        cumulative_weight = 0.0
        for variant, weight in traffic_split.items():
            cumulative_weight += weight
            if bucket < cumulative_weight:
                return variant
        return list(traffic_split.keys())[-1]

# Validasi Determinisme
engine = BucketingEngine(salt="prod_layer_llm_routing_2025")
user_a = "usr_01HZX87KQP"
exp_id = "exp_rag_rerank_v2"
split = {"control_dense": 0.5, "treatment_hybrid": 0.5}

print(f"Assign 1: {engine.get_variant(user_a, exp_id, split)}")
print(f"Assign 2: {engine.get_variant(user_a, exp_id, split)}")
assert engine.get_variant(user_a, exp_id, split) == engine.get_variant(user_a, exp_id, split)
```

### 7.2. Practical Example: Enterprise-Grade CUPED & SRM Pipeline
Implementasi komputasi CUPED lengkap beserta detektor SRM Chi-Square berbasis Scipy dan Statsmodels untuk metrik operasional agen AI:

```python
import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass
from typing import Tuple

@dataclass
class ExperimentResult:
    p_value_raw: float
    p_value_cuped: float
    variance_reduction_pct: float
    control_mean_cuped: float
    treatment_mean_cuped: float
    relative_lift_pct: float
    srm_p_value: float
    srm_detected: bool

class EnterpriseStatisticalEngine:
    @staticmethod
    def detect_srm(control_count: int, treatment_count: int, expected_ratio: float = 0.5) -> Tuple[float, bool]:
        """
        Mendeteksi Sample Ratio Mismatch (SRM) menggunakan Pearson's Chi-Square Test.
        """
        total = control_count + treatment_count
        expected_control = total * expected_ratio
        expected_treatment = total * (1.0 - expected_ratio)
        
        observed = [control_count, treatment_count]
        expected = [expected_control, expected_treatment]
        
        chi2, p_value = stats.chisquare(f_obs=observed, f_exp=expected)
        # Ambang batas SRM sangat ketat (0.001) untuk mencegah false alarm
        return float(p_value), bool(p_value < 0.001)

    @classmethod
    def analyze_cuped(
        cls, 
        df: pd.DataFrame, 
        variant_col: str, 
        metric_current: str, 
        metric_pre_experiment: str,
        expected_ratio: float = 0.5
    ) -> ExperimentResult:
        """
        Menjalankan kalkulasi CUPED dan pengujian hipotesis dua arah.
        """
        # 1. Pengecekan SRM
        counts = df[variant_col].value_counts()
        n_ctrl = counts.get("control", 0)
        n_trt = counts.get("treatment", 0)
        srm_p, has_srm = cls.detect_srm(n_ctrl, n_trt, expected_ratio)
        
        if has_srm:
            raise ValueError(f"CRITICAL: SRM Terdeteksi! p-value={srm_p:.6e}. Evaluasi dibatalkan.")

        # 2. Kalkulasi Theta Optimal
        # theta = Cov(Y, X) / Var(X)
        cov_matrix = np.cov(df[metric_current], df[metric_pre_experiment])
        cov_yx = cov_matrix[0, 1]
        var_x = cov_matrix[1, 1]
        
        theta = cov_yx / var_x if var_x != 0 else 0.0
        
        # 3. Transformasi Nilai Metrik CUPED
        mean_x = df[metric_pre_experiment].mean()
        df["metric_cuped"] = df[metric_current] - theta * (df[metric_pre_experiment] - mean_x)

        # 4. Isolasi Grup
        ctrl_raw = df[df[variant_col] == "control"][metric_current]
        trt_raw = df[df[variant_col] == "treatment"][metric_current]
        
        ctrl_cuped = df[df[variant_col] == "control"]["metric_cuped"]
        trt_cuped = df[df[variant_col] == "treatment"]["metric_cuped"]

        # 5. Uji t independen (Welch's t-test untuk varians tidak sama)
        t_stat_raw, p_val_raw = stats.ttest_ind(trt_raw, ctrl_raw, equal_var=False)
        t_stat_cuped, p_val_cuped = stats.ttest_ind(trt_cuped, ctrl_cuped, equal_var=False)

        # 6. Kalkulasi Reduksi Varians
        var_raw = np.var(df[metric_current], ddof=1)
        var_cuped = np.var(df["metric_cuped"], ddof=1)
        var_reduction = (1.0 - (var_cuped / var_raw)) * 100.0

        ctrl_mean_final = float(ctrl_cuped.mean())
        trt_mean_final = float(trt_cuped.mean())
        lift = ((trt_mean_final - ctrl_mean_final) / ctrl_mean_final) * 100.0

        return ExperimentResult(
            p_value_raw=float(p_val_raw),
            p_value_cuped=float(p_val_cuped),
            variance_reduction_pct=float(var_reduction),
            control_mean_cuped=ctrl_mean_final,
            treatment_mean_cuped=trt_mean_final,
            relative_lift_pct=float(lift),
            srm_p_value=float(srm_p),
            srm_detected=has_srm
        )

# SIMULASI PRODUKSI
if __name__ == "__main__":
    np.random.seed(42)
    N = 20000

    # Simulasi Metrik: Waktu Penyelesaian Masalah oleh AI Customer Support Agent (Detik)
    # X: Performa historis pengguna sebelum uji coba
    # Y: Performa selama uji coba berlangsung
    pre_exp_time = np.random.normal(loc=120, scale=30, size=N)
    
    # Noise stokastik yang berkorelasi
    noise = np.random.normal(loc=0, scale=15, size=N)
    
    # Kontrol vs Perlakuan (Treatment mempercepat rata-rata 3 detik)
    variants = np.random.choice(["control", "treatment"], size=N, p=[0.5, 0.5])
    treatment_effect = np.where(variants == "treatment", -3.0, 0.0)
    
    current_time = 0.8 * pre_exp_time + treatment_effect + noise

    dataset = pd.DataFrame({
        "variant": variants,
        "pre_task_duration": pre_exp_time,
        "task_duration": current_time
    })

    engine = EnterpriseStatisticalEngine()
    result = engine.analyze_cuped(
        df=dataset,
        variant_col="variant",
        metric_current="task_duration",
        metric_pre_experiment="pre_task_duration"
    )

    print(f"=== HASIL EVALUASI EKSPERIMEN AGEN AI ===")
    print(f"SRM Chi-Square p-value   : {result.srm_p_value:.4f} (Safe: {not result.srm_detected})")
    print(f"Reduksi Varians (CUPED)  : {result.variance_reduction_pct:.2f}%")
    print(f"Raw p-value              : {result.p_value_raw:.5f}")
    print(f"CUPED p-value            : {result.p_value_cuped:.5e}")
    print(f"Kontrol (Rata-rata Terkoreksi)  : {result.control_mean_cuped:.2f}s")
    print(f"Perlakuan (Rata-rata Terkoreksi): {result.treatment_mean_cuped:.2f}s")
    print(f"Relative Lift             : {result.relative_lift_pct:.2f}%")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Arsitektur Router Agen Multi-LLM di FinTech Global (100 Juta Transaksi/Bulan)
* **Konteks**: Platform fraud detection & automated disputes menguji coba beralih dari model *single-tier* (GPT-4o) ke model *hierarchical agent routing* (Llama-3-8B fine-tuned untuk 80% kasus mudah, fallback ke Claude 3.5 Sonnet untuk 20% kasus berisiko tinggi).
* **Target Bisnis**: Mengurangi pengeluaran API model sebesar 60% tanpa menurunkan rasio akurasi deteksi (*Fraud Resolution Accuracy*) di bawah ambang batas toleransi 99.2%.

```
                             [ INCOMING DISPUTE PAYLOAD ]
                                          │
                                          ▼
                      [ ROUTING EXPERIMENTATION ENGINE ]
                     (MurmurHash3 on Entity: dispute_id)
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼ (50%)                                           ▼ (50%)
         [ CONTROL VARIANT ]                               [ TREATMENT VARIANT ]
         Direct GPT-4o Agent                               Hierarchical Router Agent
                 │                                                 │
                 ▼                                                 ▼
        Latency: 1850ms                                   Classifier (Llama-3-8B)
        Cost: $0.045 / tx                                          │
        Accuracy: 99.4%                                  ┌─────────┴─────────┐
                                                         ▼ (Easy: 82%)       ▼ (Hard: 18%)
                                                     Resolved by 8B      Escalate to Claude 3.5
                                                     Latency: 450ms      Latency: 2200ms
                                                     Cost: $0.002        Cost: $0.055
                                                         │                   │
                                                         └─────────┬─────────┘
                                                                   ▼
                                                          Latency Avg: 765ms
                                                          Cost Avg: $0.0115 / tx
                                                          Accuracy: 99.35%
```

### Insiden Produksi (Silent Metric Pollution)
* **Insiden**: Di hari ke-3 pengujian, p-value melonjak ekstrem dan varian Treatment menunjukkan penurunan drastis pada metrik retensi pengguna.
* **Investigasi Masalah**: Ditemukan terjadi kebocoran interaksi antar entitas (*Network Spillovers*). Saat pengguna mengajukan banding atas transaksi sengketa yang sama berkali-kali, sesi pertama dievaluasi oleh Control, dan sesi kedua oleh Treatment. Terjadi inkonsistensi reasoning teks penjelasan yang disajikan kepada analis fraud internal.
* **Solusi Tim Product & Engineering**:
  1. Mengubah *Unit of Randomization* dari `session_id` ke tingkat `org_id` (Perusahaan Pengguna / Tenant FinTech).
  2. Menerapkan isolasi klaster menggunakan *Cluster Randomization Graph*:
     $$P(\text{Assign } i) = f(\text{Network Community Hash})$$
  3. Mengaktifkan *CUPED Transformation* berdasarkan riwayat volume fraud tenant 30 hari ke belakang.
* **Hasil Akhir**: Evaluasi valid berhasil diselesaikan dalam 11 hari. Biaya API terpangkas **74.4%**, latency rata-rata membaik **58%**, dan akurasi fraud terjaga stabil pada angka **99.35%** (memenuhi kriteria batas non-inferiority).

---

## 9. Trade-offs: Arsitektur & Statistik

Sebagai Technical Product Manager, setiap pilihan arsitektur eksperimentasi memiliki konsekuensi:

```
                    FREQUENTIST (Fixed Horizon)
                               ▲
                              / \
                             /   \
  Trade-off: Efisiensi      /     \    Trade-off: Risiko False Positive
  Waktu & Fleksibilitas    /       \   pada Peeking & Sample Size
                          /         \
                         /           \
                        /             \
                       /_______________\
BAYESIAN (Continuous Monitoring)      BANDITS / REINFORCEMENT (Thompson Sampling)
            Trade-off: Kehilangan inferensi kausalitas murni 
            demi memaksimalkan pendapatan seketika (Regret Minimization)
```

| Parameter | Frequentist (CUPED + SPRT) | Bayesian Inference | Contextual Multi-Armed Bandits |
| :--- | :--- | :--- | :--- |
| **Kelebihan Utama** | Menghasilkan nilai absolut p-value yang diterima regulator/auditor kepatuhan data. | Memberikan probabilitas langsung ($P(B > A)$) yang intuitif dipahami stakeholders. | Menekan nilai *regret* (kerugian bisnis akibat mengalirkan traffic ke varian inferior). |
| **Kelemahan Kritis** | Kaku: sampel harus ditentukan di awal, dilarang menghentikan tes sebelum waktu tanpa penalti alfa. | Sensitif terhadap penentuan distribusi probabilitas awal (*Prior Distribution Bias*). | Menghancurkan isolasi variabel kausal; sulit mengukur efek sekunder jangka panjang. |
| **Beban Komputasi Engine** | Ringan (Perhitungan analitis tertutup). | Menengah hingga Berat (Markov Chain Monte Carlo / Numerical Integration). | Berat (Kalkulasi bobot probabilistik real-time per request). |
| **Rekomendasi Kasus Pakai** | Pembaruan Algoritma Inti, Safety Guardrails, Pembuktian Validitas Model Regulasi. | Fitur Produk Umum, UX Flow, Evaluasi LLM-as-a-Judge berkelanjutan. | Dynamic Content Routing, Optimasi Promosi Flash Sale, Emergency LLM Fallback Routing. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Peeking Problem (Penyakit Mengintip Data)
* **Kesalahan**: PM membuka dashboard setiap pagi, melihat $p$-value berada di angka 0.04 ($< 0.05$), lalu langsung memutuskan memenangkan varian dan menutup pengujian di hari ke-4 dari rencana 14 hari.
* **Dampak**: Tingkat *False Positive Rate* melonjak dari 5% menjadi mendekati **30-40%** karena pengujian berulang (*Repeated Significance Testing*).
* **Solusi**: Terapkan metode **O’Brien-Fleming Alpha Spending Function** atau **SPRT** (Sequential Probability Ratio Test) jika dashboard pemantauan real-time disediakan untuk tim eksekutif.

### 2. Twyman’s Law ("Angka yang Terlalu Bagus Pasti Salah")
* **Kesalahan**: Varian treatment LLM agent baru menunjukkan kenaikan konversi sebesar 250% secara instan.
* **Penyebab Tersembunyi**: Varian baru gagal mengeksekusi *safety validation regex*, sehingga agen menyetujui seluruh klaim pengguna tanpa verifikasi valid (terjadi *silent system failure*).
* **Solusi**: Pasang *Inverted Guardrail Metrics*. Jika performa naik secara tidak wajar ($>3\sigma$ dari historical lift), picu status *Automatic Sanity Flag*.

### 3. Mengabaikan Novelty & Primacy Effect
* **Kesalahan**: Metrik *Engagement Time* varian baru melonjak di 48 jam pertama pengujian lalu perlahan merosot ke baseline aslinya setelah 10 hari.
* **Penyebab**: Pengguna mengeksplorasi antarmuka atau persona baru hanya karena faktor penasaran (*Novelty Effect*).
* **Solusi**: Segmentasikan analisis data antara pengguna baru (*New Users*) vs pengguna lama (*Existing Users*). Jangan ambil keputusan final sebelum kurva metrik pengguna lama melandai dan konvergen.

---

## 11. Best Practices: Production Checklist

### Pre-Experiment Phase
- [ ] Lakukan Power Analysis formal: Tentukan ukuran sampel minimum, baseline rate, dan MDE (Minimum Detectable Effect).
- [ ] Definisikan secara tertulis: 1 Primary Metric, Maksimal 3 Secondary Metrics, dan Minimal 2 Guardrail Metrics (misal: Biaya Token, P99 Latency).
- [ ] Verifikasi ketersediaan data pre-eksperimen untuk aktivasi reduksi varians CUPED.
- [ ] Pasang konfigurasi alokasi hashing berbasis UUID deterministik, bukan identitas rentan duplikasi (seperti IP Address).

### Execution Phase
- [ ] Validasi Sample Ratio Mismatch (SRM) secara terprogram di pipeline data per jam pertama dan setiap hari kerja.
- [ ] Konfigurasikan *Circuit Breaker* / *Automated Kill-Switch*: Eksperimen otomatis berhenti jika Guardrail Metric terlanggar sebesar $\ge 10\%$.
- [ ] Lindungi isolasi lapisan eksperimen: Pastikan salt pada layer routing LLM tidak saling terikat silang dengan layer retrieval dokumen.

### Post-Experiment Phase
- [ ] Jalankan uji homogenitas varians (Levene's test) sebelum eksekusi uji t parametrik.
- [ ] Hitung estimasi biaya tahunan (*Annualized Cloud Run Cost*) atas dampak varian pemenang sebelum rilis global (100%).
- [ ] Simpan artefak lengkap pengujian ke dalam Enterprise Experiment Registry: konfigurasi commit prompt, bobot model, baseline, confidence intervals, dan notebook analisis.

---

## 12. Hands-on Practice

Berikut adalah panduan latihan terstruktur untuk membangun sistem evaluasi eksperimen produksi mandiri. Simpan seluruh file di direktori: `hands-on/m02/`.

### Langkah 1: Inisialisasi Environment
Buat file `requirements.txt` di dalam folder `hands-on/m02/`:
```text
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
mmh3>=4.0.0
statsmodels>=0.14.0
pytest>=7.0.0
```
Jalankan instalasi:
```bash
pip install -r requirements.txt
```

### Langkah 2: Implementasi Router Eksperimen LLM
Buat file `hands-on/m02/llm_router.py`:
```python
import mmh3
from typing import Dict, Any

class LLMExperimentRouter:
    def __init__(self, experiment_id: str, layer_salt: str):
        self.experiment_id = experiment_id
        self.layer_salt = layer_salt

    def route_request(self, user_id: str) -> Dict[str, Any]:
        """
        Menentukan konfigurasi LLM berdasarkan entity hash.
        Split: 50% Control (Model A), 50% Treatment (Model B)
        """
        seed_key = f"{self.layer_salt}:{self.experiment_id}:{user_id}"
        hash_val = mmh3.hash(seed_key) & 0xFFFFFFFF
        bucket = (hash_val % 1000) / 1000.0  # Resolusi 0.1%

        if bucket < 0.50:
            return {
                "variant": "control",
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 512
            }
        else:
            return {
                "variant": "treatment",
                "model": "claude-3-haiku",
                "temperature": 0.2,
                "max_tokens": 512
            }

if __name__ == "__main__":
    router = LLMExperimentRouter(experiment_id="exp_cost_opt_v1", layer_salt="salt_q3_2025")
    samples = [f"usr_{i}" for i in range(10)]
    for u in samples:
        cfg = router.route_request(u)
        print(f"User: {u} -> Model: {cfg['model']} ({cfg['variant']})")
```

### Langkah 3: Eksekusi Test Suite SRM Terotomatisasi
Buat file unit testing `hands-on/m02/test_experiment_integrity.py`:
```python
import pytest
import numpy as np
from scipy import stats

def run_srm_check(control_obs: int, treatment_obs: int, expected_p: float = 0.5) -> float:
    total = control_obs + treatment_obs
    exp_ctrl = total * expected_p
    exp_trt = total * (1.0 - expected_p)
    _, p_val = stats.chisquare([control_obs, treatment_obs], [exp_ctrl, exp_trt])
    return p_val

def test_srm_normal_traffic():
    # Simulasi 100,000 sampel dengan rasio wajar
    p_val = run_srm_check(49850, 50150)
    assert p_val > 0.001, f"False Positive SRM Alert! p-value: {p_val}"

def test_srm_anomalous_traffic():
    # Simulasi kondisi drop request varian treatment (48.5% vs 51.5%)
    p_val = run_srm_check(51500, 48500)
    assert p_val < 0.001, f"Gagal mendeteksi SRM kritis! p-value: {p_val}"
```
Jalankan validasi pengujian:
```bash
pytest hands-on/m02/test_experiment_integrity.py
```

---

## 13. Exercise

### Level Easy
Tulis skrip Python sederhana untuk menghitung ukuran sampel yang dibutuhkan (*Sample Size Calculator*) pada eksperimen 2 varian dengan parameter:
* Baseline Conversion Rate: $12\%$
* Minimum Detectable Effect (MDE) Relatif: $5\%$ (naik menjadi $12.6\%$)
* $\alpha = 0.05$ (Two-sided), Power ($1-\beta$) = $0.80$
* *Gunakan library `statsmodels.stats.power.NormalIndPower`.*

### Level Medium
Implementasikan fungsi transformasi data CUPED dalam SQL (PostgreSQL/Trino dialect).
Diberikan tabel `user_agent_metrics` dengan skema:
* `user_id` (VARCHAR)
* `variant` (VARCHAR: 'control' atau 'treatment')
* `pre_exp_token_usage` (FLOAT)
* `post_exp_token_usage` (FLOAT)

Hitung nilai rata-rata kuadrat, kovarians antara `post_exp_token_usage` dan `pre_exp_token_usage`, kalkulasikan nilai konstanta $\theta$, lalu cetak metrik terkoreksi `post_exp_cuped` per user.

### Level Hard
Rancang arsitektur microservice *Contextual Multi-Armed Bandit* (menggunakan Thompson Sampling berbasis distribusi Beta) untuk mengalokasikan traffic prompt agen otonom.
* Skenario: Terdapat 3 varian prompt RAG (`prompt_zero_shot`, `prompt_few_shot`, `prompt_cot`).
* Setiap agen menerima *reward* biner ($1$ jika task selesai tanpa intervensi manusia, $0$ jika terjadi eskalasi CS).
* Microservice harus:
  1. Mengambil parameter $\alpha_k$ dan $\beta_k$ dari Redis.
  2. Melakukan sampling dari distribusi Beta: $\theta_k \sim \text{Beta}(\alpha_k, \beta_k)$.
  3. Memilih varian dengan nilai $\theta$ tertinggi.
  4. Menyediakan endpoint async callback untuk memperbarui parameter $\alpha$ atau $\beta$ di Redis setelah trace audit pengguna diterima.

---

## 14. Challenge: The Agentic Infinite Loop Catastrophe

### Konteks Skenario
Anda adalah Principal AI Product Manager di perusahaan SaaS Enterprise tier-1. Tim platform Anda meluncurkan A/B testing untuk modul "Autonomous Code Refactoring Agent".
* **Kontrol (50%)**: Arsitektur Agen Klasik (Satu LLM Planner dengan batas maksimal 5 lintasan eksekusi).
* **Treatment (50%)**: Arsitektur Multi-Agent Collaboration (Planner, Coder, dan Reviewer yang saling memvalidasi sintaks kode secara otonom).

### Gejala Masalah di Lapangan
* Pada hari ke-4 eksperimen, dashboard statistik Frequentist mengindikasikan bahwa varian **Treatment mengungguli Kontrol dengan metrik Code Quality Score naik 18% ($p < 0.0001$)**. Tim Engineering mendesak agar rilis 100% segera dilakukan hari itu juga.
* Namun, tim FinOps dan Platform Reliability membunyikan alarm darurat P1:
  1. Pengeluaran biaya API OpenAI melonjak dari **$3.000/hari menjadi $48.000/hari**.
  2. Latensi P99 dari agent task melonjak dari **45 detik menjadi 14 menit**.
  3. Terjadi lonjakan HTTP 504 Gateway Timeout sebesar **6.2%** khusus pada pengguna varian Treatment dengan repositori enterprise berukuran besar.

### Tugas Tantangan (Deliverables)
Susun Dokumen Investigasi & Desain Arsitektur (Technical Post-Mortem & Mitigation Plan) yang mencakup:
1. **Analisis Akar Anomali Statistik**: Jelaskan mengapa p-value dari *Code Quality Score* tampak sangat superior padahal sistem sedang mengalami kegagalan operasional masif (Sintesis korelasi antara *Survivorship Bias* akibat HTTP 504 drops dan *Twyman's Law*).
2. **Evaluasi SRM (Sample Ratio Mismatch)**: Rekonstruksikan bagaimana *gateway timeout* merusak rasio sampel yang diterima analitik, dan formulasikan ambang batas penghentian otomatis (*kill-switch*) yang seharusnya mencegah insiden ini.
3. **Redesain Sistem Metrik**: Rancang sistem metrik komposit (*Overall Evaluation Criterion* - OEC) baru yang menggabungkan metrik kualitas kode, penalti konsumsi token, dan latensi eksekusi dalam satu formulasi objektif matematis.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Konsep Dasar (Basic)
1. **Apa tujuan utama penerapan hashing deterministik (seperti MurmurHash3) dalam alokasi varian pengujian A/B?**
   * A. Mengenkripsi identitas data pribadi pengguna demi kepatuhan regulasi GDPR.
   * B. Menghilangkan kebutuhan penyimpanan state alokasi varian di database dan menjamin konsistensi assignation pengguna di setiap request.
   * C. Menjamin bahwa varian treatment selalu mendapatkan alokasi sumber daya komputasi server yang lebih besar.
   * D. Mempercepat waktu inferensi komputasi token pada model bahasa besar.

2. **Kapan kondisi Sample Ratio Mismatch (SRM) dapat dinyatakan terdeteksi secara valid?**
   * A. Ketika nilai konversi varian treatment lebih rendah dari varian kontrol.
   * B. Ketika pengujian Chi-Square Goodness-of-Fit antara rasio sampel observasi aktual dan rasio rancangan menghasilkan $p$-value $< 0.001$.
   * C. Ketika ukuran sampel varian kontrol dan treatment berjumlah persis identik.
   * D. Ketika p-value dari primary metric menyentuh nilai signifikansi 0.05.

3. **Metode reduksi varians CUPED memanfaatkan korelasi antara variabel saat pengujian dengan variabel apa?**
   * A. Variabel dari metrik eksternal platform kompetitor.
   * B. Variabel metrik yang sama atau berkorelasi dari entitas pengguna yang sama pada periode **sebelum** eksperimen dimulai.
   * C. Variabel biaya komputasi per seribu token inferensi.
   * D. Variabel acak stokastik Gaussian white noise.

4. **Apa yang dimaksud dengan "Guardrail Metric" dalam eksperimentasi AI?**
   * A. Metrik utama yang ingin dinaikkan oleh tim marketing (misal: Revenue).
   * B. Metrik integritas sistem (misal: P99 Latency, Token Cost, Failure Rate) yang tidak boleh melampaui batas toleransi bahaya terlepas dari keberhasilan primary metric.
   * C. Metrik pengukur waktu tunggu pengguna pada loading bar antarmuka frontend.
   * D. Metrik kepuasan kerja tim engineering yang membangun model AI.

5. **Apa konsekuensi langsung dari fenomena "Peeking Problem" (memeriksa signifikansi data berulang kali sebelum fixed-horizon selesai tanpa koreksi statistik)?**
   * A. Meningkatnya risiko Type I Error (False Positive Rate) secara drastis di atas nilai $\alpha$ yang dirancang.
   * B. Menurunnya kecepatan konvergensi algoritma gradient descent model.
   * C. Hilangnya data pengguna akibat memory leak pada Redis cluster.
   * D. Meningkatnya Statistical Power hingga mendekati 100%.

---

### Bagian 2: Penerapan Teknis (Intermediate)
6. **Dalam eksperimen perbandingan arsitektur RAG, varian A menggunakan Dense Retrieval dan varian B menggunakan Hybrid (Dense + BM25). Manakah unit randomisasi yang paling tepat untuk meminimalkan carryover effect pada aplikasi collaborative workspace?**
   * A. Per individual HTTP Request token.
   * B. Per User Session ID.
   * C. Per Workspace / Organization ID.
   * D. Per Browser User-Agent header.

7. **Bila korelasi linear Pearson antara performa pre-experiment ($X$) dan post-experiment ($Y$) adalah $\rho = 0.8$, berapakah persentase reduksi varians metrik yang didapatkan setelah implementasi CUPED?**
   * A. 80%
   * B. 36%
   * C. 64%
   * D. 20%

8. **Mengapa algoritma Contextual Multi-Armed Bandit (MAB) sering kali lebih diutamakan dibandingkan Classic A/B Testing pada kampanye promosi berdurasi singkat (misal: Flash Sale 24 jam)?**
   * A. MAB mengabaikan seluruh metrik latensi jaringan.
   * B. MAB meminimalkan *cumulative regret* dengan mengalihkan traffic secara dinamis ke varian dengan estimasi performa terbaik selama periode pengujian.
   * C. MAB menghasilkan pembuktian kausalitas statistik yang lebih diakui secara akademis dibanding Uji t.
   * D. MAB tidak membutuhkan data exposure sama sekali untuk beroperasi.

9. **Jika pada pengujian model AI terjadi Type I Error ($\alpha = 0.05$), apakah makna bisnis dari kejadian tersebut?**
   * A. Model baru sebenarnya tidak memberikan dampak positif apa pun dibanding model lama, namun diputuskan menang dan diluncurkan ke pasar secara keliru.
   * B. Model baru sebenarnya sangat unggul, namun tim produk membuang model tersebut karena dianggap gagal secara statistik.
   * C. Terjadi kebocoran memori pada server inferensi GPU.
   * D. Ukuran sampel pengujian tidak mencukupi standar minimum batas statistical power.

10. **Bagaimana cara menangani *Novelty Effect* saat menguji fitur asisten AI percakapan yang baru diperkenalkan ke publik?**
    * A. Menghentikan eksperimen tepat 24 jam setelah rilis.
    * B. Mengisolasi kelompok pengguna baru dan mengukur stabilitas efek perlakuan pada rentang waktu beberapa minggu hingga perilaku interaksi stabil.
    * C. Mengalikan seluruh hasil metrik treatment dengan koefisien diskon arbitrer 0.5.
    * D. Menghapus data seluruh pengguna yang aktif setiap hari.

---

### Bagian 3: Skenario Kasus Produksi (Production Scenarios)
11. **Skenario Kasus A**:
    Platform e-commerce menguji coba model Rekomendasi LLM baru (Treatment) vs Rekomendasi Collaborative Filtering lama (Control). Setelah 7 hari berjalan dengan target alokasi 50:50, sistem analitik mencatat total event checkout: Kontrol = 120.000, Treatment = 101.000. Pengujian Chi-Square Goodness-of-Fit terhadap jumlah pengguna terdaftar pada kedua grup menunjukkan $p$-value $= 0.000012$. Apa diagnosa arsitektural yang paling rasional dan tindakan pertama yang wajib diambil oleh Technical Product Manager?
    * A. Terjadi SRM kritis; kemungkinan varian Treatment mengalami latensi tinggi yang memicu request timeout di sisi client. Tindakan: Segera batalkan/hentikan pengujian, jangan percaya data metrik checkout yang tampak, dan telusuri log gateway 5xx/timeout.
    * B. Treatment terbukti kalah performa; Tindakan: Segera luncurkan varian Kontrol secara permanen ke 100% traffic pengguna.
    * C. Kondisi normal karena varian Treatment menyaring pembeli berkualitas rendah; Tindakan: Lanjutkan eksperimen hingga hari ke-14.
    * D. Error terletak pada library statistik Python; Tindakan: Ganti pengujian Chi-Square dengan Mann-Whitney U Test.

12. **Skenario Kasus B**:
    Anda merancang evaluasi model LLM coding assistant menggunakan metode automated LLM-as-a-Judge. Ditemukan bahwa model "Judge" (penilai) secara konsisten memberikan skor 15% lebih tinggi kepada varian Treatment bukan karena kualitas kebenaran kode logika, melainkan semata-mata karena output varian Treatment menghasilkan formatting Markdown yang lebih panjang dan terstruktur (*Verbosity Bias*). Pendekatan engineering paling valid untuk mengeliminasi bias evaluasi ini adalah:
    * A. Melipatgandakan jumlah request inferensi per user session.
    * B. Menerapkan *Length-Controlled De-biasing* (normalisasi skor terhadap token count), melakukan *Position Swap* (menilai urutan A-B dan B-A), serta menyamarkan identitas prompt struktur ke Judge model.
    * C. Mengubah model judge dengan model yang lebih murah dan berukuran lebih kecil.
    * D. Mengabaikan bias tersebut karena teks panjang disukai pengguna.

13. **Skenario Kasus C**:
    Sebuah aplikasi telemedisin menguji asisten AI triage pasien. Karena regulasi kesehatan sangat ketat, tim manajemen menetapkan bahwa risiko Type I error tidak boleh lebih dari 1% ($\alpha = 0.01$) dan Statistical Power wajib minimal 90% ($1-\beta = 0.90$). Tim data menghitung bahwa untuk mendeteksi MDE sebesar 1.5% dibutuhkan sampel minimal 80.000 pasien, yang setara dengan durasi pengujian 4 bulan traffic penuh. Apa strategi teknis paling mutakhir yang dapat diambil AI PM untuk memangkas durasi pengujian menjadi ~2 bulan tanpa melanggar parameter rigoritas statistik yang diminta manajemen?
    * A. Mengurangi alokasi kontrol menjadi 10% dan treatment 90%.
    * B. Mengimplementasikan CUPED dengan mengidentifikasi metrik pre-treatment berkorelasi tinggi (seperti riwayat konsultasi historis) serta menerapkan *Sequential Testing* (m-SPRT) dengan *early stopping criteria*.
    * C. Menghentikan eksperimen saat nilai $p$-value sementara menyentuh angka di bawah 0.05.
    * D. Menghilangkan metrik guardrail keselamatan pasien dari dashboard pemantauan.

---

### Kunci Jawaban & Pembahasan Mendalam

1. **Jawaban: B**
   * *Pembahasan*: Algoritma deterministic hash bucketing memetakan string identitas (user ID + salt) ke dalam rentang interval numerik secara murni matematis. Hal ini mengeliminasi *latency overhead* panggilan jaringan ke centralized database/caching layer dan menjamin sifat idempoten: pengguna yang sama akan selalu menerima varian yang sama setiap kali mengeksekusi sistem.

2. **Jawaban: B**
   * *Pembahasan*: SRM dievaluasi secara obyektif menggunakan uji Chi-Square Goodness-of-Fit antara frekuensi observasi sampel aktual dengan rasio alokasi teoritis yang ditetapkan. Ambang batas $p < 0.001$ adalah standar industri konservatif untuk memvalidasi deviasi sistematis tanpa terganggu oleh fluktuasi acak minor.

3. **Jawaban: B**
   * *Pembahasan*: Inti matematis CUPED adalah menyerap varians intrinsik yang dibawa oleh unit partisipan dari masa lalu. Dengan mengurangkan kovarian antara performa pre-experiment ($X$) dan current metric ($Y$), varians yang tersisa merefleksikan perubahan murni akibat dampak varian baru.

4. **Jawaban: B**
   * *Pembahasan*: Guardrail metrics berperan sebagai jaring pengaman sistemik. Walaupun model AI berhasil menaikkan engagement pengguna (Primary Metric), sistem harus otomatis menghentikan pengujian apabila biaya API per transaksi membengkak di luar toleransi ekonomi atau latensi sistem merusak User Experience secara luas.

5. **Jawaban: A**
   * *Pembahasan*: Peeking problem melanggar asumsi dasar pengujian hipotesis *fixed-horizon*. Menilai $p$-value berulang kali di setiap batch data baru meningkatkan probabilitas menangkap fluktuasi acak sesaat sebagai signifikansi palsu (*false discovery*), yang melipatgandakan tingkat kesalahan Type I Error secara kumulatif.

6. **Jawaban: C**
   * *Pembahasan*: Pada sistem workspace kolaboratif, dokumen dan basis pengetahuan diakses bersama oleh seluruh anggota tim dalam satu organisasi. Melakukan randomisasi di level user atau request akan menyebabkan *interference* dan polusi data: satu pengguna di tim yang sama melihat hasil retrieval lama sementara rekan kerjanya melihat hasil retrieval baru pada repositori data yang identik. Unit randomisasi di tingkat Organization ID memutus korelasi ketergantungan ini (*Cluster Isolation*).

7. **Jawaban: C**
   * *Pembahasan*: Formula reduksi varians CUPED adalah $\operatorname{Var}(\hat{Y}_{CUPED}) = \operatorname{Var}(Y)(1 - \rho^2)$. Substitusikan $\rho = 0.8 \rightarrow 1 - (0.8)^2 = 1 - 0.64 = 0.36$. Varians yang tersisa adalah 36%, yang berarti sistem berhasil memangkas varians sebesar **64%**.

8. **Jawaban: B**
   * *Pembahasan*: Pada skenario promosi waktu singkat (seperti Flash Sale), tujuan utama operasional bisnis adalah eksploitasi pendapatan maksimal, bukan pembuktian kausal jangka panjang. Algoritma Bandit mengalokasikan traffic mayoritas secara adaptif ke varian pemenang secara real-time, sehingga meminimalkan peluang bisnis yang hilang (*regret minimization*).

9. **Jawaban: A**
   * *Pembahasan*: Kesalahan Tipe I (Type I Error / $\alpha$) terjadi ketika hipotesis nol ($H_0$: tidak ada perbedaan performa nyata antar varian) sebenarnya benar, namun ditolak oleh penguji statistik. Konsekuensi bisnisnya adalah merilis varian yang sebenarnya inferior atau sia-sia ke skala global karena tertipu oleh kebetulan acak.

10. **Jawaban: B**
    * *Pembahasan*: Sensasi kebaruan (*Novelty Effect*) bersifat sementara. Memisahkan kohort pengguna baru (yang baru pertama kali melihat sistem tanpa bias historis) dan memperpanjang observasi hingga kurva variasi pengguna lama mencapai *steady state* adalah metode ilmiah baku untuk mengukur lift murni.

11. **Jawaban: A**
    * *Pembahasan*: Nilai $p$-value Chi-Square ekstrem ($0.000012 < 0.001$) adalah bukti mutlak adanya Sample Ratio Mismatch. Angka penurunan transaksi di Treatment bukan bukti kelemahan model, melainkan akibat kegagalan teknis (misalnya latensi model baru memicu client timeout). Setiap data yang dikumpulkan saat kondisi SRM terjadi adalah data cacat (*invalid data*), sehingga pengujian harus dihentikan seketika untuk perbaikan sistem.

12. **Jawaban: B**
    * *Pembahasan*: LLM-as-a-Judge memiliki kelemahan intrinsik berupa bias terhadap teks yang panjang (*verbosity bias*) dan posisi urutan teks (*positional bias*). Langkah rekayasa standar untuk menetralkannya adalah menormalkan penilaian terhadap panjang token output, melakukan penukaran urutan penilaian varian secara silang (*permutation test*), dan membersihkan penanda format unik agar proses evaluasi berjalan objektif.

13. **Jawaban: B**
    * *Pembahasan*: Pendekatan ilmiah yang valid dan aman secara statistik untuk mempercepat waktu uji tanpa mengorbankan integritas $\alpha$ dan power adalah: (1) Mengimplementasikan CUPED yang secara langsung memangkas kebutuhan sampel sebesar $1 - \rho^2$, dan (2) Menggunakan *Sequential Testing* terkontrol (seperti m-SPRT) yang memperbolehkan early stopping sah secara matematis jika batas efikasi atau futilitas telah terlampaui.

---

## 16. Summary

Eksperimentasi pada ekosistem AI dan Autonomous Agents menuntut peralihan paradigma dari pengujian A/B antarmuka klasik menuju arsitektur evaluasi sistem terdistribusi yang memperhitungkan stokastisitas, token economics, dan interaksi probabilistik. 

Sebagai Technical Product Manager kelas enterprise:
* **Integritas Infrastruktur adalah Fondasi**: Sistem alokasi wajib stateless dan deterministik (MurmurHash3) dengan deteksi real-time terhadap anomali sistemik seperti Sample Ratio Mismatch (SRM).
* **Rigoritas Statistik Mencegah Pemborosan Modal**: Menguasai metodologi reduksi varians (CUPED) dan Sequential Testing bukan sekadar efisiensi metrik, melainkan keunggulan kompetitif yang memangkas waktu rilis fitur hingga 50% tanpa mengorbankan validitas kausalitas data.
* **Keseimbangan Metrik Objektif**: Kesuksesan model AI diukur bukan hanya dari satu metrik akurasi semantik murni, melainkan konvergensi seimbang antara *Primary Value Metric* (konversi/task success), *System Stability Metric* (latensi P99/timeout rate), dan *Guardrail Financial Metric* (biaya token API per transaksi). Pengambilan keputusan berbasis data yang kokoh adalah pembeda antara spekulasi fitur dan rekayasa produk skala dunia.