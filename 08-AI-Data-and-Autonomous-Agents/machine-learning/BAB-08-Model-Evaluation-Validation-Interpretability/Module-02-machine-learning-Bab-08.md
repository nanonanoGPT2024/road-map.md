# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Model Evaluation, Validation, & Interpretability**  
**Topik:** Machine Learning (Kategori: 08-AI-Data-and-Autonomous-Agents)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mendesain dan Mengimplementasikan Skema Validasi Bebas Kebocoran Temporal:** Membangun *Purged & Embargoed Cross-Validation* untuk data berderet waktu (*time-series*) dan non-IID (*independent and identically distributed*) guna mengeliminasi *information leakage* dan *look-ahead bias*.
2. **Mengintegrasikan Kerangka Evaluasi Berbasis Biaya (*Cost-Sensitive Evaluation*):** Mentransformasi metrik statistik konvensional (F1, AUC-ROC) menjadi metrik utilitas bisnis riil menggunakan *Asymmetric Loss Matrices* dan *Expected Value Framework*.
3. **Menguasai Mekanisme Matematis Interpretasi Lanjutan:** Mengonstruksi algoritma *TreeSHAP* secara optimal, memahami perbedaan antara ekspektasi kondisional (*path-dependent*) versus intervensi (*marginalist*), serta membedakan penerapan *Partial Dependence Plots* (PDP) dan *Accumulated Local Effects* (ALE) pada fitur yang berkorelasi tinggi.
4. **Membangun Arsitektur Produksi Evaluasi & Audibilitas Model:** Mengembangkan pipeline validasi otomatis (*automated gating*), *worker pool* penjelas asinkron (*asynchronous explanation pipeline*), dan integrasi pembuatan artefak kepatuhan (*Model Cards/Audit Logs*) yang siap diaudit regulator.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus telah menguasai:

*   **Matematika & Probabilitas:** Aljabar linear lanjutan, kalkulus multivariat, teori probabilitas kondisional, serta konsep dasar Teori Permainan Kooperatif (*Cooperative Game Theory: Shapley Values*).
*   **Machine Learning Fundamental:** *Bias-Variance Trade-off*, algoritma *tree-based ensemble* (Random Forest, Gradient Boosting/LightGBM/XGBoost), evaluasi matriks konfusi dasar.
*   **Engineering & Tooling:**
    *   Python 3.10+ (NumPy, SciPy, Pandas, Scikit-Learn, LightGBM).
    *   Pustaka interpretabilitas: `shap` (v0.42+), `alibi`.
    *   Konsep sistem terdistribusi: Arsitektur berbasis antrean pesan (*message queues* seperti RabbitMQ/Kafka) dan penyimpanan *cache* (Redis).

---

## 3. Concept & Internal Architecture

### 3.1. Purged and Embargoed Cross-Validation

Validasi silang standar (*K-Fold Cross-Validation*) berasumsi bahwa data berdistribusi identik dan independen ($IID$). Dalam skenario riil (transaksi finansial, data pasar modal, perilaku pengguna berulang), asumsi ini runtuh karena adanya korelasi serial (*serial correlation*) dan label yang memiliki rentang durasi aktif (*spanning time horizon*).

```
Standar K-Fold (Data Bocor):
Fold 1: [Train] | [Test (Leakage dari Train!)] | [Train]

Purged & Embargoed CV:
Fold 1: [Train................] [Purge] [Test] [Embargo] [Train...............]
                                   ^              ^
                                   |              +-- Periode jeda proteksi memory/autoregression
                                   +-- Buang observasi train yang labelnya tumpang-tindih dengan test
```

#### Formulasi Matematis:
Misalkan observasi $i$ ditentukan oleh interval waktu $[t_{i, 0}, t_{i, 1}]$ di mana $t_{i, 0}$ adalah waktu kejadian (*event*) dan $t_{i, 1}$ adalah waktu label ditentukan. Jika himpunan pengujian (*test set*) dibatasi oleh interval waktu $[T^{(0)}_j, T^{(1)}_j]$:
1. **Purging:** Menghapus dari himpunan latih (*training set*) setiap observasi $i$ yang rentang evaluasinya tumpang tindih dengan interval pengujian:
   $$Train_{purged} = \{ i \in Train \mid t_{i, 1} < T^{(0)}_j \lor t_{i, 0} > T^{(1)}_j \}$$
2. **Embargoing:** Menghapus data latih sesaat setelah jendela pengujian berakhir untuk menghilangkan efek *autoregressive memory*:
   $$Train_{final} = Train_{purged} \setminus \{ i \in Train \mid T^{(1)}_j \le t_{i, 0} \le T^{(1)}_j + h \}$$
   di mana $h$ adalah panjang jendela embargo.

---

### 3.2. TreeSHAP: Ekspektasi Intervensional vs Path-Dependent

Nilai Shapley menetapkan atribusi marjinal fitur $i$ terhadap prediksi $f(x)$ dengan merata-ratakan kontribusi marjinalnya di semua subset fitur $S \subseteq F \setminus \{i\}$:

$$\phi_i(x) = \sum_{S \subseteq F \setminus \{i\}} \frac{|S|!(|F| - |S| - 1)!}{|F|!} \left[ f_x(S \cup \{i\}) - f_x(S) \right]$$

Komputasi naive bernilai $O(M \cdot 2^{|F|})$. TreeSHAP mereduksi kompleksitas menjadi polinomial $O(T L D^2)$, di mana $T$ adalah jumlah pohon, $L$ adalah jumlah daun maksimum, dan $D$ adalah kedalaman maksimum pohon.

```
       [Feature A <= 5]
          /        \
      (w=0.6)     (w=0.4)
     /                  \
[Feature B <= 10]     [Value = 20]
   /        \
[Val=5]   [Val=15]
```

*   **Path-Dependent Conditioning ($E[f(x) \mid x_S]$):** Menelusuri pohon dengan membagi bobot simpul berdasarkan cakupan sampel riil (*node sample counts/cover*). Pendekatan ini cepat dan tidak mengevaluasi kombinasi fitur yang tidak realistis secara natural, namun melanggar aksioma independensi jika fitur saling berkorelasi.
*   **Interventional Conditioning ($E_{X_{\bar{S}}}[f(x_S, X_{\bar{S}})]$):** Memutus korelasi antar-fitur dengan mengambil sampel latar belakang sintetis (*reference/background dataset*). Pendekatan ini strictly menaati properti kausal, namun dapat mengevaluasi titik data sintetis yang tidak realistis jika dua fitur memiliki keterikatan fisik/logis mutlak.

---

### 3.3. Accumulated Local Effects (ALE) vs Partial Dependence Plots (PDP)

PDP menghitung efek marginal suatu fitur dengan memarginalkan distribusi fitur lainnya secara seragam:

$$\hat{f}_{PDP}(x_S) = \frac{1}{n} \sum_{i=1}^n f(x_S, x^{(i)}_C)$$

**Kelemahan PDP:** Jika fitur $x_S$ dan $x_C$ berkorelasi kuat (misal: Berat Mesin vs Volume Mesin), PDP akan memaksakan prediksi pada kombinasi data yang mustahil (misal: Berat 2000 kg dengan Volume 100 cc), menghasilkan *extrapolation bias*.

**Mekanisme ALE:** Menghitung perbedaan gradien lokal dalam jendela interval kecil $\Delta N(k)$, lalu mengintegrasikannya:

$$\hat{f}_{ALE}(x_j) = \sum_{k=1}^{k_j(x)} \frac{1}{n_j(k)} \sum_{i: x^{(i)}_j \in N_j(k)} \left[ f(z_{k, j}, x^{(i)}_{\setminus j}) - f(z_{k-1, j}, x^{(i)}_{\setminus j}) \right] - \text{konstanta}$$

Dengan mengisolasi perhitungan hanya pada sampel observasi lokal aktual di sekitar interval $N_j(k)$, ALE secara matematis kebal terhadap *extrapolation bias* pada fitur berkorelasi.

---

### 3.4. Arsitektur Produksi Sistem Evaluasi & Penjelasan

Sistem produksi modern memisahkan jalur inferensi latensi rendah (*online prediction path*) dari jalur komputasi interpretabilitas dan evaluasi (*offline/asynchronous auditing path*).

```
                           +-------------------------------------+
                           |            KLIEN / API GATEWAY      |
                           +-------------------------------------+
                                       |              ^
                 1. Predict Request    |              | 4. Response 
                 (SLA < 15ms)          v              |    (Prediksi Segera)
                        +-------------------------------+
                        |  Microservice Model (Triton)  |
                        +-------------------------------+
                           |                         |
            2. Predict Log |                         | 3. Raw Predict
                           v                         v
        +-----------------------+       +-------------------------+
        |   Message Broker      |       |  Feature Store / Redis  |
        |   (Kafka / RabbitMQ)  |       +-------------------------+
        +-----------------------+                    ^
                   |                                 |
                   | Streaming Queue                 |
                   v                                 |
        +-----------------------+                    |
        | Explainer Worker Pool | -------------------+
        | (Celery / C++ TreeSHAP) | Ambil Background Baseline
        +-----------------------+
                   |
                   | 5. Simpan Hasil Atribusi & Metrik Drift
                   v
        +-----------------------------------------------+
        | PostgreSQL Audit Store / Parquet Data Lake    |
        +-----------------------------------------------+
                   |
                   v
        +-----------------------------------------------+
        | Prometheus Exporter -> Dashboard Grafana      |
        +-----------------------------------------------+
```

---

## 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Production Standard |
| :--- | :--- | :--- |
| **Pemisahan Data** | K-Fold Acak / Simple Train-Test | *Purged & Embargoed Group Walk-Forward* |
| **Metrik Evaluasi** | Optimasi Metrik Simetris (Accuracy, ROC-AUC) | *Cost-Sensitive Utility Matrix & Expected Monetary Loss* |
| **Interpretasi Model** | Global Feature Importance bawaan (Gini/Permutation) | *TreeSHAP Intervensional* + *Accumulated Local Effects (ALE)* |
| **Eksekusi Penjelasan** | Dihitung sekuensial di jalur HTTP thread utama | *Asynchronous Explainer Pipeline* dengan *Background Sampling* |
| **Kepatuhan Audit** | Catatan notebook manual (*ad-hoc*) | *Automated Version-Controlled Model Cards* & Audit Log DB |

### Mengapa Pendekatan Konvensional Gagal di Skala Enterprise?
1. **Financial Overfitting:** Model kuantitatif atau fraud yang divalidasi dengan K-Fold acak sering kali memberikan metrik pengujian yang tinggi (misal AUC 0.98), namun performanya anjlok drastis (AUC 0.55) di hari pertama produksi akibat *information leakage* temporal.
2. **Asymmetric Business Risk:** Biaya meloloskan transaksi penipuan (*False Negative*) sebesar \$2,000 jauh melampaui biaya memverifikasi transaksi sah (*False Positive*) sebesar \$1. Mengoptimalkan threshold berdasarkan kurva ROC murni menjamin kerugian finansial perusahaan.
3. **Regulatory Non-Compliance:** Regulasi seperti EU AI Act dan US FCRA mewajibkan penolakan kredit (*Adverse Action*) dapat dijelaskan dengan faktor matematis yang deterministik, stabil, dan bebas collinearity distortion.

---

## 5. How: Alur Kerja Validasi & Interpretasi Produksi

1. **Partisi Temporal:** Tentukan struktur dependensi waktu, interval horizon prediksi label, dan jendela embargo. Bentuk indeks training/testing menggunakan *PurgedGroupTimeSeriesSplit*.
2. **Optimasi Berbasis Biaya (*Cost Optimization*):**
   * Buat matriks utilitas biaya bisnis.
   * Latih model ensemble menggunakan loss/penalti yang disesuaikan.
   * Kalibrasi probabilitas menggunakan *Isotonic Regression* atau *Platt Scaling* (langkah wajib sebelum optimalisasi threshold moneter).
   * Lakukan pencarian ambang batas (*threshold search*) yang meminimalkan kerugian finansial yang diharapkan (*Expected Cost*).
3. **Pipeline Interpretasi:**
   * Ekstraksi subset representatif dari data latih menggunakan *K-Means Medoids* untuk membentuk *SHAP Background Dataset*.
   * Hitung nilai SHAP global dan lokal.
   * Validasi collinearity menggunakan kurva ALE.
4. **Automated Gating:**
   * Sebelum promosi model ke *Registry Produksi*, pipeline CI/CD memvalidasi:
     * Minimum Expected Utility Threshold.
     * Stabilitas Atribusi Fitur (tidak boleh ada pembalikan tanda/arah signifikansi pada fitur inti).
     * Drift Toleransi Baseline.

---

## 6. Analogi & Diagram ASCII

### Analogi Karantina Bandara (Purged & Embargoed CV)
Bayangkan Anda menguji efektivitas sistem deteksi infeksi penyakit. 
* Menggunakan **K-Fold Acak** ibarat mengizinkan penumpang yang terinfeksi pada hari ke-5 berbaur bebas dengan sampel pelatihan hari ke-1: model mengenali virus bukan karena prediktor cerdas, melainkan karena pernah "melihat" mutasi virus yang sama dari masa depan.
* **Purging** adalah mengarantina dan membuang individu yang masa inkubasinya menyentuh periode tes.
* **Embargoing** adalah waktu jeda sterilisasi terminal sebelum gelombang penerbangan berikutnya dievaluasi.

### Diagram: Dynamic Cost-Sensitive Threshold Alignment

```
Probabilitas Prediksi Frauds: P(y=1)
0.0           Threshold Standar (0.50)           1.0
 |-----------------------|-----------------------|
 [Biaya FN Sangat Tinggi] [Biaya FP Ringan       ]
 
 Ambang Batas Optimal Terkoreksi Biaya:
 Threshold Baru (Contoh: 0.08)
 |---|-------------------------------------------|
   ^
   +--- Memaksimalkan Total Penghematan Finansial
        Mencegah 95% Fraud dengan biaya false alert minimal.
```

---

## 7. Implementasi Kode: Standar Industri

Berikut adalah skrip pipeline lengkap berstandar enterprise yang menggabungkan:
1. *Purged & Embargoed Splitter* kustom yang kompatibel dengan Scikit-Learn.
2. Kalibrasi Probabilitas dan *Cost-Sensitive Threshold Optimizer*.
3. Pipeline komputasi *Fast TreeSHAP* teroptimasi.

```python
"""
Enterprise ML Validation & Interpretability Framework
Production-grade module for Purged-Embargoed CV, Cost-Sensitive Tuning, and Fast TreeSHAP.
"""

from typing import Generator, Tuple, Optional, Dict, Any
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import confusion_matrix
import shap


class PurgedEmbargoTimeSeriesSplit:
    """
    Purged and Embargoed Time-Series Cross-Validator.
    Prevents data leakage in non-IID datasets with overlapping label horizons.
    """
    def __init__(
        self,
        n_splits: int = 5,
        purge_window: int = 0,
        embargo_pct: float = 0.01
    ) -> None:
        self.n_splits = n_splits
        self.purge_window = purge_window
        self.embargo_pct = embargo_pct

    def split(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        groups: Optional[pd.Series] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        embargo_size = int(n_samples * self.embargo_pct)
        test_size = n_samples // (self.n_splits + 1)

        for i in range(self.n_splits):
            test_start = (i + 1) * test_size
            test_end = test_start + test_size
            test_indices = indices[test_start:test_end]

            # Purge data sebelum test yang tumpang tindih
            train_left_end = max(0, test_start - self.purge_window)
            train_left_indices = indices[:train_left_end]

            # Embargo data setelah test
            train_right_start = test_end + embargo_size
            if train_right_start < n_samples:
                train_right_indices = indices[train_right_start:]
            else:
                train_right_indices = np.array([], dtype=int)

            train_indices = np.concatenate([train_left_indices, train_right_indices])
            yield train_indices, test_indices


class CostSensitiveThresholdOptimizer:
    """
    Optimizes classification decision thresholds against an asymmetric cost matrix.
    
    Cost Matrix Structure:
    - Cost of False Positive (C_FP): e.g., Alert manual review, operational cost.
    - Cost of False Negative (C_FN): e.g., Fraud direct loss, default write-off.
    - Cost of True Positive  (C_TP): Friction cost / recovery fee.
    - Cost of True Negative  (C_TN): Zero or nominal overhead.
    """
    def __init__(
        self,
        cost_fp: float,
        cost_fn: float,
        cost_tp: float = 0.0,
        cost_tn: float = 0.0
    ) -> None:
        self.cost_fp = cost_fp
        self.cost_fn = cost_fn
        self.cost_tp = cost_tp
        self.cost_tn = cost_tn
        self.optimal_threshold_: float = 0.5

    def calculate_expected_loss(self, y_true: np.ndarray, y_prob: np.ndarray, threshold: float) -> float:
        y_pred = (y_prob >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        total_loss = (fp * self.cost_fp) + (fn * self.cost_fn) + (tp * self.cost_tp) + (tn * self.cost_tn)
        return float(total_loss)

    def fit(self, y_true: np.ndarray, y_prob: np.ndarray, search_resolution: int = 1000) -> "CostSensitiveThresholdOptimizer":
        thresholds = np.linspace(0.001, 0.999, search_resolution)
        losses = [self.calculate_expected_loss(y_true, y_prob, th) for th in thresholds]
        self.optimal_threshold_ = float(thresholds[np.argmin(losses)])
        return self

    def predict(self, y_prob: np.ndarray) -> np.ndarray:
        return (y_prob >= self.optimal_threshold_).astype(int)


class ExplainableProductionPipeline:
    """
    Integrated framework for calibrated model training, cost optimization,
    and fast TreeSHAP explainability computation.
    """
    def __init__(
        self,
        cost_matrix: Dict[str, float],
        cv_splits: int = 5
    ) -> None:
        self.cost_matrix = cost_matrix
        self.cv = PurgedEmbargoTimeSeriesSplit(n_splits=cv_splits, purge_window=5, embargo_pct=0.02)
        self.base_model = lgb.LGBMClassifier(
            n_estimators=150,
            learning_rate=0.03,
            max_depth=5,
            num_leaves=31,
            random_state=42,
            verbose=-1
        )
        self.threshold_optimizer = CostSensitiveThresholdOptimizer(**cost_matrix)
        self.explainer: Optional[shap.TreeExplainer] = None
        self.is_fitted = False

    def train_and_validate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, Any]:
        cv_losses = []
        
        # Cross-validation loop bebas kebocoran
        for fold, (train_idx, val_idx) in enumerate(self.cv.split(X, y)):
            X_tr, y_tr = X.iloc[train_idx], y.iloc[train_idx]
            X_val, y_val = X.iloc[val_idx], y.iloc[val_idx]

            self.base_model.fit(X_tr, y_tr)
            val_probs = self.base_model.predict_proba(X_val)[:, 1]
            
            fold_loss = self.threshold_optimizer.calculate_expected_loss(
                y_val.to_numpy(), val_probs, threshold=0.5
            )
            cv_losses.append(fold_loss)

        # Latih model final pada seluruh dataset
        self.base_model.fit(X, y)
        
        # Kalibrasi probabilitas menggunakan Isotonic Regression
        self.calibrated_model_ = CalibratedClassifierCV(
            estimator=self.base_model, cv="prefit", method="isotonic"
        )
        self.calibrated_model_.fit(X, y)
        
        # Hitung probabilitas terkalibrasi untuk optimasi threshold
        final_probs = self.calibrated_model_.predict_proba(X)[:, 1]
        self.threshold_optimizer.fit(y.to_numpy(), final_probs)

        # Inisialisasi TreeSHAP menggunakan model pohon asli
        self.explainer = shap.TreeExplainer(
            self.base_model,
            feature_perturbation="tree_path_dependent"
        )
        self.is_fitted = True

        return {
            "mean_cv_baseline_loss": float(np.mean(cv_losses)),
            "optimal_threshold": self.threshold_optimizer.optimal_threshold_,
            "feature_names": list(X.columns)
        }

    def predict_with_explanation(
        self,
        X_sample: pd.DataFrame,
        top_n_reasons: int = 3
    ) -> Dict[str, Any]:
        if not self.is_fitted or self.explainer is None:
            raise RuntimeError("Pipeline must be fitted before calling prediction.")

        probabilities = self.calibrated_model_.predict_proba(X_sample)[:, 1]
        decisions = self.threshold_optimizer.predict(probabilities)
        shap_values = self.explainer.shap_values(X_sample)

        # Handle struktur output LightGBM binary classification
        if isinstance(shap_values, list):
            sv = shap_values[1]
        else:
            sv = shap_values

        audit_results = []
        for idx in range(len(X_sample)):
            sample_sv = sv[idx]
            top_feature_indices = np.argsort(np.abs(sample_sv))[-top_n_reasons:][::-1]
            
            adverse_reasons = [
                {
                    "feature": X_sample.columns[f_idx],
                    "attribution": float(sample_sv[f_idx]),
                    "observed_value": float(X_sample.iloc[idx, f_idx])
                }
                for f_idx in top_feature_indices
            ]
            
            audit_results.append({
                "sample_id": idx,
                "probability": float(probabilities[idx]),
                "decision": int(decisions[idx]),
                "adverse_action_explanations": adverse_reasons
            })

        return {"predictions": audit_results}


if __name__ == "__main__":
    # Inisialisasi data sintetis terurut waktu
    np.random.seed(42)
    n_records = 5000
    
    timestamps = pd.date_range("2023-01-01", periods=n_records, freq="min")
    features = {
        f"feature_{k}": np.random.randn(n_records) for k in range(5)
    }
    # Buat feature yang berkolerasi dengan fraud
    features["tx_velocity"] = np.random.exponential(scale=2.0, size=n_records)
    features["anomaly_score"] = features["tx_velocity"] * 0.4 + np.random.normal(0, 1, n_records)

    df_X = pd.DataFrame(features, index=timestamps)
    # Logit fraud dependent pada tx_velocity dan anomaly_score
    fraud_logits = 0.8 * df_X["tx_velocity"] + 1.2 * df_X["anomaly_score"] - 4.0
    fraud_probs = 1 / (1 + np.exp(-fraud_logits))
    df_y = pd.Series(np.random.binomial(1, fraud_probs), index=timestamps)

    # Definisi Matriks Biaya Finansial (Asymmetric Loss)
    cost_matrix_config = {
        "cost_fp": 15.0,    # Biaya operasional manual triage dan friction nasabah
        "cost_fn": 450.0,   # Biaya kerugian langsung fraud
        "cost_tp": 2.0,     # Biaya komputasi blokir otomatis
        "cost_tn": 0.0      # Zero cost
    }

    # Pipeline Execution
    pipeline = ExplainableProductionPipeline(cost_matrix=cost_matrix_config, cv_splits=4)
    print("Memulai training pipeline...")
    metrics = pipeline.train_and_validate(df_X, df_y)
    print(f"Optimal Threshold Ditemukan: {metrics['optimal_threshold']:.4f}")

    # Menguji Explainer untuk Kasus Adverse Action
    test_batch = df_X.iloc[-3:]
    audit_payload = pipeline.predict_with_explanation(test_batch, top_n_reasons=2)
    
    import json
    print("\nPayload Audit Transaksi Terverifikasi (Sample 0):")
    print(json.dumps(audit_payload["predictions"][0], indent=2))
```

---

## 8. Real World Case Study: Tier-1 Credit Decisioning Engine

### Konteks Bisnis
Sebuah bank digital memproses 120.000 aplikasi pinjaman tanpa agunan harian. Tim kepatuhan (*compliance*) dan manajemen risiko menghadapi dua kendala krusial:
1. **Regulasi Hak Penjelasan (*Adverse Action Compliance*):** Setiap penolakan pinjaman wajib disertai 3 alasan dominan berdasarkan *Equal Credit Opportunity Act* (ECOA) dan regulasi privasi konsumen. Model Black-Box Deep Learning sebelumnya ditolak regulator karena atribusi fiturnya berubah-ubah secara instabil pada data yang identik (*instability violation*).
2. **Asimetri Rasio Kerugian:** *Default* pinjaman rata-rata menghasilkan kerugian Rp 12.000.000 (*Loss Given Default*), sedangkan penolakan nasabah yang berpotensi lancar (*False Alarm*) hanya menghilangkan potensi pendapatan bunga sebesar Rp 450.000.

### Desain Solusi Arsitektur
Bank membangun **Real-time Explainable Risk Engine (RERE)**:
* **Validation Layer:** Mengimplementasikan *Purged-Embargoed Stratified Cross-Validation* berdasarkan bulan penerbitan pinjaman guna mencegah bocornya status makroekonomi masa depan.
* **Loss Alignment:** Model dievaluasi menggunakan *Expected Monetary Value (EMV)* matrix, bukan ROC-AUC.
* **Inference Layer:** Pemisahan *asynchronous dual-lane inference*. Inferensi skor risiko dieksekusi secara instan (< 25 ms), sedangkan payload fitur dikirim via Apache Kafka ke *C++ TreeSHAP worker daemon* untuk menghasilkan kode penolakan deterministik yang dicatat di PostgreSQL dalam jendela SLA 3 detik.

```
+--------------------+        +--------------------+        +-----------------------+
|  Pinjaman Masuk    | -----> | Scoring Service    | -----> | Approval Instan       |
|  (Payload HTTP)    |        | (C++ Native Infer) |        | (SLA < 25ms)          |
+--------------------+        +--------------------+        +-----------------------+
                                        | (Kirim Audit Event)
                                        v
                              +--------------------+
                              | Apache Kafka Topic |
                              +--------------------+
                                        |
                                        v
                              +--------------------+        +-----------------------+
                              | SHAP Engine Worker | -----> | PostgreSQL Audit      |
                              | (High-Throughput)  |        | (Adverse Reasons Log) |
                              +--------------------+        +-----------------------+
```

### Hasil Produksi
* Mengurangi kerugian finansial akibat kredit macet sebesar **Rp 14,2 Miliar** per kuartal dengan menggeser titik potong threshold probabilitas dari 0.50 menjadi 0.142 (berdasarkan kalkulasi matriks biaya aktual).
* Lolos audit regulasi moneter 100% tanpa kompromi, di mana seluruh berkas penolakan nasabah diverifikasi memiliki rincian nilai TreeSHAP yang secara logis konsisten dengan rasio DTI (*Debt to Income*) dan riwayat tunggakan.

---

## 9. Analisis Trade-Offs

```
                      AKURASI / ROBUSTNESS
                               ▲
                               │     ★ TreeSHAP (Exact Path-Dependent)
                               │
       KernelSHAP (Sampling)   │
               ▲               │
               │               │
  LATENSI RENDAH ──────────────┼──────────────► HIGH THROUGHPUT
               │               │
               │               │     ★ Linear Surrogate / ALE Approximation
               │               │
                               ▼
                        BIAYA KOMPUTASI
```

| Parameter Arsitektur | Pilihan A | Pilihan B | Analisis Trade-off Rekayasa |
| :--- | :--- | :--- | :--- |
| **Kondisional SHAP** | *Path-Dependent* | *Interventional* | *Path-Dependent* sangat cepat ($O(TLD^2)$), tetapi menyebarkan nilai atribusi pada fitur kolinear palsu. *Interventional* secara matematis murni, tetapi membutuhkan background sampling yang memicu lonjakan memori dan latensi eksponensial. |
| **Model Validation** | *Standard K-Fold* | *Purged-Embargoed CV* | K-Fold standar hemat komputasi namun memberikan metrik overoptimistik palsu. *Purged-Embargoed* membuang ~10-15% volume data efektif demi mengeliminasi *look-ahead leakage*. |
| **Threshold Tuning** | *Youden's J Statistic* | *Cost Matrix Optimization* | Youden's J menyeimbangkan sensitivitas dan spesifisitas secara mekanis murni tanpa mempertimbangkan kerugian finansial. Cost Matrix sepenuhnya berorientasi profitabilitas, namun sangat sensitif terhadap akurasi estimasi biaya moneter. |
| **Metode ALE vs PDP** | *Partial Dependence* | *Accumulated Local Effects*| PDP intuitif namun menghasilkan prediksi palsu saat dua variabel berkorelasi kuat. ALE merefleksikan isolasi lokal secara akurat, namun kurvanya non-parametrik dan sulit dipahami oleh pemangku kepentingan non-teknis. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Leakage Sebelum Splitting pada Pipeline Feature Engineering
* **Masalah:** Menggunakan `fit_transform()` pada StandardScaler, Imputer, atau Target Encoder pada seluruh DataFrame *sebelum* membaginya ke fold CV.
* **Gejala:** Nilai metrik validasi luar biasa tinggi (misal F1 score 0.99), namun anjlok drastis di *canary deployment*.
* **Solusi:** Seluruh transformasi fitur wajib di-enkapsulasi dalam `sklearn.pipeline.Pipeline` dan di-`fit` eksklusif hanya pada `X_train` masing-masing fold.

### 2. Menggunakan KernelSHAP pada Model Pohon Skala Besar
* **Masalah:** Memanggil `shap.KernelExplainer` pada model LightGBM/XGBoost dengan 500 pohon dan 50 fitur.
* **Gejala:** Memory leak (OOM), eksekusi worker terhenti (*freeze*), utilisasi CPU 100% tanpa henti berjam-jam.
* **Solusi:** Wajib menggunakan `shap.TreeExplainer`. Jika terpaksa menggunakan surrogate model generik, batasi subset latar belakang (`shap.kmeans(X_background, k=50)`).

### 3. Salah Menafsirkan Korelasi sebagai Kausalitas pada Nilai SHAP
* **Masalah:** Memberitahukan nasabah bahwa "Menaikkan limit kartu kredit Anda sebesar \$500 akan otomatis meloloskan skor pinjaman Anda."
* **Gejala:** Komplain nasabah saat rekomendasi dijalankan namun skor risiko tidak berubah sesuai ekspektasi.
* **Solusi:** Nilai SHAP adalah ukuran atribusi terhadap output model matematika saat ini, **bukan** analisis kausalitas intervensional kontrafaktual. Jelaskan nilai SHAP murni sebagai bukti faktual keputusan model (*descriptive fact*).

---

## 11. Best Practices (Production Checklist)

- [ ] **Temporal Isolation:** Pastikan index data bersifat monotonic increasing; tidak ada timestamp baris pengujian yang lebih kecil daripada baris pelatihan.
- [ ] **Purge Buffer Alignment:** Tentukan horizon pelabelan terpanjang $h$ dan jadwalkan jendela purging $P \ge h$.
- [ ] **Probability Calibration Verification:** Plot *Reliability Diagram* dan hitung *Brier Score Loss* sebelum melakukan pemindaian threshold finansial.
- [ ] **TreeSHAP Baseline Optimization:** Jika menggunakan *TreeExplainer Intervensional*, pastikan dataset latar belakang diringkas menggunakan representasi *K-Means* ($k \le 100$).
- [ ] **Determinism in Production:** Set parameter `random_state` dan `n_jobs` secara eksplisit pada model tree untuk menjamin nilai floating-point TreeSHAP identik antar audit worker.
- [ ] **Collinearity Diagnostic:** Periksa matriks korelasi Spearman. Jika ada korelasi antar-fitur $> 0.7$, prioritaskan plotting ALE di atas PDP untuk menghindari kesalahan extrapolasi inferensi.
- [ ] **Asymmetric Fallback:** Jika sistem audit worker mengalami overload (*backpressure*), sistem harus mengembalikan keputusan prediksi seketika dengan flag `audit_pending` ke message queue untuk retri kemudian.
- [ ] **Model Card Auto-Generation:** Setiap proses training model wajib secara otomatis mengekspor ringkasan metadata validasi, distribusi data, cost matrix parameter, dan identitas git commit ke file `model_card.json`.

---

## 12. Hands-on Practice

Buat dan simpan file implementasi ini di folder proyek Anda: `hands-on/m02/run_advanced_eval.py`.

### Langkah Eksekusi:
1. Pastikan dependensi terpasang:
   ```bash
   pip install numpy pandas scikit-learn lightgbm shap matplotlib
   ```
2. Buat script `hands-on/m02/run_advanced_eval.py` yang mengimpor arsitektur pada Bagian 7.
3. Tambahkan fungsi verifikasi stabilitas penjelasan:
   ```python
   # Simpan di hands-on/m02/run_advanced_eval.py (lanjutan script utama)
   def verify_explanation_stability(pipeline, X_sample, perturbation_sigma=0.01):
       """
       Menguji apakah penjelasan SHAP stabil terhadap gangguan noise minor.
       """
       original_expl = pipeline.predict_with_explanation(X_sample, top_n_reasons=1)
       
       # Tambahkan noise gaussian kecil
       noisy_sample = X_sample.copy()
       numeric_cols = noisy_sample.select_dtypes(include=[np.number]).columns
       noisy_sample[numeric_cols] += np.random.normal(0, perturbation_sigma, size=noisy_sample[numeric_cols].shape)
       
       noisy_expl = pipeline.predict_with_explanation(noisy_sample, top_n_reasons=1)
       
       for i in range(len(X_sample)):
           orig_feat = original_expl["predictions"][i]["adverse_action_explanations"][0]["feature"]
           noisy_feat = noisy_expl["predictions"][i]["adverse_action_explanations"][0]["feature"]
           stable = (orig_feat == noisy_feat)
           print(f"Sample {i} Expl Explanation Stability: {'PASS' if stable else 'FAIL'} (Orig: {orig_feat}, Noisy: {noisy_feat})")

   if __name__ == "__main__":
       # Jalankan pengujian stabilitas
       sample_cases = df_X.iloc[-5:]
       print("\nMemulai Uji Robustness Atribusi SHAP...")
       verify_explanation_stability(pipeline, sample_cases)
   ```
4. Eksekusi script dan analisis stabilitasnya:
   ```bash
   python hands-on/m02/run_advanced_eval.py
   ```

---

## 13. Latihan (Exercises)

### Tingkat: Easy
Ubah implementasi `CostSensitiveThresholdOptimizer` agar mampu menerima matriks biaya dinamis per baris data (*Instance-Level Cost Matrix*), di mana nilai penipuan kartu kredit ($C_{FN}$) bergantung langsung pada nominal transaksi `X['transaction_amount']`.
* *Deliverable:* Modifikasi kalkulasi loss loop dengan vektor perkalian `df['transaction_amount'] * y_true`.

### Tingkat: Medium
Modifikasi kelas `PurgedEmbargoTimeSeriesSplit` agar mendukung konfigurasi data multi-entitas (*Group Time-Series*). Pastikan seluruh transaksi dari nasabah yang sama (`customer_id`) hanya boleh berada di *Fold Train* atau *Fold Test*, tidak pernah tersebar di keduanya, seraya tetap mempertahankan isolasi temporal.
* *Deliverable:* Kelas `PurgedEmbargoGroupTimeSeriesSplit` yang mengintegrasikan validasi hashing `customer_id`.

### Tingkat: Hard
Bangun implementasi perhitungan *Accumulated Local Effects (ALE)* 1-Dimensi manual dari awal menggunakan modul NumPy murni untuk memvalidasi fitur berdistribusi continuous non-linear tanpa mengandalkan library black-box.
* *Deliverable:* Fungsi `calculate_1d_ale(model, X, feature_col, bins=50) -> Tuple[np.ndarray, np.ndarray]` yang mengembalikan nilai ALE dan batas interval bin, serta memplot hasilnya terhadap kurva PDP standar untuk membuktikan degradasi efek korelasi.

---

## 14. Tantangan Kasus (Enterprise Challenge)

### Kasus: Real-Time Adverse Action Engine untuk Pembayaran E-Commerce Lintas Batas
**Deskripsi Skenario Kasus:**  
Anda adalah ML Architect pada unicorn pembayaran internasional. Volume transaksi rata-rata berada pada kisaran 8.000 TPS (*transactions per second*) dengan *peak* 30.000 TPS. Tim Legal Compliance mewajibkan bahwa seluruh transaksi yang diblokir oleh sistem anti-fraud berbasis machine learning harus disertai:
1. Bukti komputasi probabilitas terkalibrasi (*Reliability Calibration*).
2. Tiga alasan objektif penolakan yang diturunkan dari atribusi matematis instan.
3. Total latensi end-to-end tidak boleh melampaui **45 ms** pada persentil ke-99 ($P_{99}$).

**Kendala Teknis Khusus:**
* Menjalankan evaluasi Shapley murni membutuhkan waktu $> 150\text{ ms}$ jika dipanggil secara sinkron untuk tiap baris transaksi di model dengan 350 fitur.
* Terdapat multikolinieritas ekstrem antara fitur `device_trust_score`, `device_age_days`, dan `ip_reputation_score`.

**Tugas Anda:**
Rancang dokumen arsitektur dan cetak biru spesifikasi sistem (*Design Document Architecture*) yang mencakup:
1. Skema partisi sistem antara *Sync Classification Path* dan *Async / Cached Attribution Path*.
2. Strategi komputasi SHAP alternatif atau aproksimasi tanpa kehilangan reliabilitas legal regulasi.
3. Prosedur penanganan fallback ketika terjadi lonjakan beban puncak (load spike $30.000\text{ TPS}$) tanpa melanggar batasan regulasi Adverse Action.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda & Analisis Konsep)
1. **Mengapa random train-test split tidak boleh digunakan pada data runtun waktu (time-series)?**
   * A. Karena mengurangi jumlah baris data yang bisa dilatih.
   * B. Karena menimbulkan *look-ahead bias* di mana informasi masa depan bocor ke dalam data pelatihan.
   * C. Karena algoritma pohon tidak mampu membaca data runtun waktu.
   * D. Karena akan menyebabkan underfitting secara permanen.
   * *Jawaban:* **B**. Random split mengaburkan urutan waktu sehingga data training dapat mengeksploitasi data masa depan.

2. **Aksioma Shapley Value yang menyatakan bahwa jika dua fitur memberikan kontribusi yang sama terhadap semua subset, maka atribusi mereka harus sama adalah:**
   * A. Efficiency
   * B. Null Player (Dummy)
   * C. Symmetry
   * D. Additivity
   * *Jawaban:* **C**. Aksioma Symmetry menyatakan jika $f(S \cup \{i\}) = f(S \cup \{j\})$, maka $\phi_i = \phi_j$.

3. **Apa tujuan utama penambahan periode "Embargo" setelah jendela "Test" pada CV finansial?**
   * A. Memberi waktu sistem beristirahat.
   * B. Menghilangkan sisa autokorelasi dan dependensi autoregresif jangka panjang dari data pengujian ke data pelatihan masa depan.
   * C. Mengurangi varians model.
   * D. Menurunkan nilai matriks biaya.
   * *Jawaban:* **B**. Embargo membersihkan efek sisa autokorelasi memori (*autoregressive memory leakage*).

4. **Metode interpretasi manakah yang paling rentan terhadap bias extrapolasi jika fitur berkorelasi tinggi?**
   * A. ALE (Accumulated Local Effects)
   * B. Partial Dependence Plots (PDP)
   * C. TreeSHAP Path-Dependent
   * D. Permutation Feature Importance
   * *Jawaban:* **B**. PDP mengevaluasi kombinasi fitur artifisial di luar manifold data riil pada fitur berkorelasi.

5. **Apa efek samping dari melakukan Threshold Tuning berbasis F1-Score pada problem asimetris finansial tinggi?**
   * A. Mengabaikan rasio biaya moneter riil antara False Positive dan False Negative.
   * B. Menghasilkan skor kalibrasi bernilai negatif.
   * C. Menyebabkan overfitting pada hyperparameter tree depth.
   * D. Memperlambat throughput scoring.
   * *Jawaban:* **A**. F1-Score memperlakukan bobot presisi dan recall secara simetris matematis murni tanpa orientasi finansial objektif.

---

### Bagian 2: Intermediate (Analisis Algoritmik & Arsitektur)
1. **Diberikan model pohon tunggal dengan kedalaman 1 (decision stump): Split pada `Fitur X > 5`. Bobot daun kiri = 10, bobot daun kanan = 30. Baseline dataset $E[f(x)] = 18$. Hitung nilai TreeSHAP untuk instans dengan `Fitur X = 8`!**
   * *Jawaban/Analisis:* Karena `Fitur X = 8` mengarah ke daun kanan dengan prediksi 30, dan nilai ekspektasi baseline adalah 18, berdasarkan aksioma *Efficiency* ($\sum \phi_i = f(x) - E[f(x)]$), nilai SHAP untuk satu-satunya fitur tersebut adalah: $\phi_X = 30 - 18 = +12$.

2. **Apa implikasi menggunakan parameter `feature_perturbation="interventional"` pada SHAP terhadap waktu pemrosesan (*runtime complexity*) dibandingkan `"tree_path_dependent"`?**
   * *Jawaban/Analisis:* Kompleksitas waktu melonjak tajam dari $O(T L D^2)$ menjadi $O(T L D \cdot |X_{background}|)$. Hal ini disebabkan algoritma harus mengiterasi subset data latar belakang (*reference dataset*) pada setiap node untuk mensimulasikan pemutusan korelasi fitur.

3. **Mengapa kalibrasi probabilitas (misalnya Isotonic Regression) harus diterapkan SEBELUM menentukan threshold matriks biaya optimal?**
   * *Jawaban/Analisis:* Algoritma pohon sering menghasilkan probabilitas kasar (*uncalibrated probabilities*) yang terdistorsi di sekitar margin klasifikasi. Perhitungan *Expected Cost Matrix* bergantung pada probabilitas riil bayesian: $E[L] = P(y=1) \cdot C_{FN} + (1 - P(y=1)) \cdot C_{FP}$. Jika probabilitas terdistorsi, ambang batas moneter optimal yang diturunkan akan bias secara substansial.

4. **Kapan teknik GroupKFold mutlak wajib digunakan melampaui Purged-TimeSeriesSplit standar?**
   * *Jawaban/Analisis:* Ketika data mengandung observasi berulang dari entitas unik yang sama (contoh: ID Pasien dalam data rekam medis, ID Toko dalam data logistik). Tanpa Grouping, model akan mengenali pola entitas unik (*entity memorization*), bukan pola prediktif fitur umum.

5. **Bagaimana cara mendeteksi bahwa pipeline TreeSHAP Anda menghasilkan nilai atribusi yang salah akibat multikolinearitas ekstrim?**
   * *Jawaban/Analisis:* Terjadi fenomena pemiskinan atribusi (*attribution splitting*): dua fitur yang identik atau berkorelasi sempurna ($r > 0.98$) masing-masing menerima setengah dari nilai Shapley yang seharusnya, atau saling meniadakan dengan arah nilai yang berlawanan (+ dan - besar), sehingga tidak merefleksikan pentingnya fitur secara representatif.

---

### Bagian 3: Skenario Kasus Produksi (Root Cause & Architectural Decision)

#### Skenario 1: Ledakan Latensi P99 pada Layanan Inferensi Real-time
* **Kondisi:** Tim Data Platform mengintegrasikan penghitungan nilai SHAP instan pada layanan deteksi fraud langsung di dalam web handler synchronous Python Flask. Pada jam sibuk, latensi melonjak dari 15ms menjadi 2.400ms dan menyebabkan *request timeout cascade*.
* **Pertanyaan Analisis:** Di mana letak kegagalan arsitekturnya, dan bagaimana topologi sistem yang benar untuk menyelesaikannya tanpa meniadakan fungsi interpretasi audit?
* **Solusi Arsitektural:** 
  1. *Root Cause:* Menjalankan algoritma analitik kompleks ($O(TLD^2)$) pada thread pooling HTTP web-server synchronous.
  2. *Resolusi:* Pisahkan jalur komputasi. Web-server hanya mengeksekusi inferensi skoring instan menggunakan model terkompilasi (misal ONNX/Triton) dengan SLA < 15ms. 
  3. Payload inferensi kemudian dipublikasikan secara asinkron ke message broker (Kafka/RabbitMQ). Worker pool dedicated berbasis Celery atau backend C++ mengeksekusi TreeSHAP secara terpisah dan menyimpan log penjelasan ke Database Audit.

#### Skenario 2: Anomali Gagal Audit Regulasi Perbankan (Instability)
* **Kondisi:** Regulator mengaudit model kredit personal. Auditor memasukkan dua profil pemohon yang hampir identik dengan perbedaan saldo bank hanya Rp 10.000. Model menghasilkan penolakan untuk keduanya, namun alasan penolakan nomor 1 pada Pemohon A adalah "Rasio Saldo", sedangkan pada Pemohon B adalah "Usia Pemohon". Bank diancam sanksi pencabutan izin akibat inkonsistensi keputusan.
* **Pertanyaan Analisis:** Mengapa TreeSHAP menghasilkan perubahan ranking fitur drastis pada data yang perbedaannya marjinal, dan bagaimana rekayasa fitur/model mengatasinya?
* **Solusi Arsitektural:**
  1. *Root Cause:* Pohon keputusan mengalami *instability boundary* akibat parameter `min_child_weight` yang terlalu kecil atau penggunaan fitur kolinear yang bersaing ketat pada *split criteria* yang setara.
  2. *Resolusi:*
     - Lakukan penggabungan (*pruning*) fitur dengan korelasi tinggi melalui teknik *Hierarchical Feature Clustering*.
     - Regularisasi pohon: tingkatkan nilai `min_child_samples` dan kurangi kedalaman maksimum (`max_depth`).
     - Terapkan ensemble averaging pada nilai SHAP dari beberapa bootstrap model untuk menstabilkan estimasi gradien lokal.

#### Skenario 3: Model Profit Collapse Pasca Deployment Canary
* **Kondisi:** Model underwriting baru menunjukkan AUC 0.88 pada set pengujian historis, mengungguli model lama (AUC 0.80). Namun saat diuji coba (*canary deployment*) pada 10% volume transaksi nyata selama satu bulan, unit bisnis merugi 30% lebih besar dibandingkan model lama.
* **Pertanyaan Analisis:** Berikan diagnosa mengapa peningkatan metrik AUC justru menghasilkan kerugian moneter riil, serta tentukan audit metrik apa yang luput dievaluasi!
* **Solusi Arsitektural:**
  1. *Root Cause:* Model baru mengoptimalkan separasi ranking global (AUC) pada wilayah ambang probabilitas yang salah secara komersial. Pada saat implementasi, ambang batas keputusan tetap di-set default pada 0.5.
  2. *Diagnosa Luput:* Tim lalai memetakan kurva utilitas bisnis riil menggunakan *Cost Matrix Optimization*. Kemungkinan besar model baru menghasilkan peningkatan *False Negative* pada segmen transaksi bernilai pinjaman sangat besar, yang tidak tercermin dalam metrik peringkat simetris AUC biasa.
  3. *Tindakan Koreksi:* Terapkan kalkulasi kalibrasi Brier Score, hitung Expected Monetary Value matrix, dan sesuaikan threshold classification cut-off secara dinamis berdasarkan nilai nominal pinjaman.

---

## 16. Summary

1. **Integritas Validasi Temporal:** Pada domain enterprise dengan data berderet waktu dan dependensi serial, K-Fold CV standar menyebabkan bias estimasi performa. Metodologi *Purged & Embargoed Cross-Validation* secara ketat membuang data yang tumpang tindih (*overlap*) dan membersihkan sisa autokorelasi, memberikan estimasi generalisasi yang reliabel.
2. **Kesesuaian Bisnis via Cost-Sensitive Design:** Metrik statistik standar (Accuracy, AUC, F1) tidak memperhitungkan risiko operasional asimetris. Model enterprise wajib dikalibrasikan probabilitasnya, lalu dipetakan terhadap *Asymmetric Cost Matrix* guna meminimalisir total kerugian finansial riil.
3. **Ketepatan Pilihan Penjelasan (Explainability):** TreeSHAP menawarkan kecepatan komputasi polinomial untuk pohon ensemble, namun harus dipahami asumsi di balik pemilihan metode ekspektasi kondisional (*path-dependent* vs *interventional*). Untuk evaluasi fitur kontinu yang saling berkorelasi, *Accumulated Local Effects (ALE)* lebih terpercaya dibandingkan *Partial Dependence Plots (PDP)* untuk mencegah kesalahan interpretasi akibat extrapolasi data tidak realistis.
4. **Pemisahan Sistem Produksi:** Arsitektur kelas produksi memisahkan jalur inferensi langsung yang membutuhkan latensi ultra-rendah dari jalur perhitungan analitik interpretabilitas berbasis antrean asinkron, memastikan pemenuhan regulasi audit (*Adverse Action Compliance*) tanpa mengorbankan SLA performa sistem.