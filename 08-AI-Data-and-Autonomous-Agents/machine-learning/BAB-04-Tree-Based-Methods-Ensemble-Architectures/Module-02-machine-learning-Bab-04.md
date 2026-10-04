# BAB 04: Tree-Based Methods & Ensemble Architectures
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis Mekanisme Internal Gradient Boosting**: Membedah formulasi matematis Taylor Series Approximation orde kedua ($g_i$ dan $h_i$) serta arsitektur internal dari tiga mesin boosting enterprise utama: XGBoost, LightGBM, dan CatBoost.
2. **Merancang Algoritma Split dan Optimasi Memori**: Memahami trade-off algoritma *exact greedy split*, *histogram-based split*, GOSS (*Gradient-based One-Side Sampling*), EFB (*Exclusive Feature Bundling*), serta *Oblivious Trees*.
3. **Mengompilasi Model Ensemble untuk Low-Latency Serving**: Mengonversi model berbasis pohon ke dalam representasi biner terkompilasi (*branchless C code*, Treelite, ONNX Runtime) untuk mencapai latensi inferensi sub-milidetik ($p99 < 1\text{ ms}$).
4. **Membangun Pipeline Distributed Training Enterprise**: Merancang pipeline pelatihan model berskala multi-node/multi-GPU yang terintegrasi dengan Feature Store, data streaming, dan arsitektur deteksi *drift* berbasis ensemble.

---

### 2. Prerequisite

Peserta diasumsikan telah menguasai:
* **Matematika Lanjut**: Kalkulus peubah banyak (turunan parsial, ekspansi deret Taylor), aljabar linier terapan, dan optimasi konveks.
* **Arsitektur Komputer**: Pemahaman dasar tentang hierarki memori CPU (L1/L2/L3 cache, RAM), *cache misses*, *branch prediction*, dan paralelisasi SIMD.
* **Machine Learning Fundamentals**: *Decision trees* (CART), metrik evaluasi (AUC-ROC, LogLoss, NDCG), bias-variance trade-off, dan teknik regularisasi ($L_1$/$L_2$).
* **Software Engineering**: Python 3.10+, C++17 dasar (opsional untuk memahami runtime), pemahaman container (Docker), dan asynchronous programming (FastAPI).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1 Formulasi Matematis Orde Kedua (Second-Order Taylor Approximation)

Pada Gradient Tree Boosting klasik, fungsi objektif pada iterasi ke-$t$ diekspresikan sebagai:

$$\mathcal{L}^{(t)} = \sum_{i=1}^n l(y_i, \hat{y}_i^{(t-1)} + f_t(x_i)) + \Omega(f_t)$$

Di mana $\Omega(f_t) = \gamma T + \frac{1}{2} \lambda \sum_{j=1}^T w_j^2$ merepresentasikan regularisasi kompleksitas pohon ($T$ jumlah daun, $w$ bobot daun).

Untuk mengakselerasi optimasi fungsi kerugian arbitrer yang dapat dideferensiasi, XGBoost menggunakan ekspansi deret Taylor orde kedua di sekitar prediksi sebelumnya $\hat{y}_i^{(t-1)}$:

$$\mathcal{L}^{(t)} \approx \sum_{i=1}^n \left[ l(y_i, \hat{y}_i^{(t-1)}) + g_i f_t(x_i) + \frac{1}{2} h_i f_t^2(x_i) \right] + \Omega(f_t)$$

Di mana gradien orde pertama ($g_i$) dan Hessian orde kedua ($h_i$) didefinisikan sebagai:

$$g_i = \partial_{\hat{y}^{(t-1)}} l(y_i, \hat{y}^{(t-1)}) \quad \text{dan} \quad h_i = \partial^2_{\hat{y}^{(t-1)}} l(y_i, \hat{y}^{(t-1)})$$

Dengan menghilangkan konstanta $l(y_i, \hat{y}_i^{(t-1)})$, fungsi objektif yang disederhanakan pada daun ke-$j$ (himpunan sampel $I_j = \{i \mid q(x_i) = j\}$) adalah:

$$\tilde{\mathcal{L}}^{(t)} = \sum_{j=1}^T \left[ \left( \sum_{i \in I_j} g_i \right) w_j + \frac{1}{2} \left( \sum_{i \in I_j} h_i + \lambda \right) w_j^2 \right] + \gamma T$$

Menurunkan terhadap $w_j$ dan menyamakannya ke 0 menghasilkan bobot optimal $w_j^*$ dan skor kualitas pohon $\mathcal{L}^*$:

$$w_j^* = -\frac{\sum_{i \in I_j} g_i}{\sum_{i \in I_j} h_i + \lambda} = -\frac{G_j}{H_j + \lambda}$$

$$\mathcal{L}^* = -\frac{1}{2} \sum_{j=1}^T \frac{G_j^2}{H_j + \lambda} + \gamma T$$

Formula *gain* untuk pencarian split dari partisi daun kiri ($L$) dan kanan ($R$):

$$\text{Gain} = \frac{1}{2} \left[ \frac{G_L^2}{H_L + \lambda} + \frac{G_R^2}{H_R + \lambda} - \frac{(G_L + G_R)^2}{H_L + H_R + \lambda} \right] - \gamma$$

```
                           [Parent Node: G, H]
                                   |
                  +----------------+----------------+
                  |                                 |
         [Left Child: G_L, H_L]           [Right Child: G_R, H_R]
           Score: G_L^2 / (H_L+lambda)      Score: G_R^2 / (H_R+lambda)
           
  Gain = 0.5 * [ (G_L^2)/(H_L+λ) + (G_R^2)/(H_R+λ) - ((G_L+G_R)^2)/(H_L+H_R+λ) ] - γ
```

---

#### 3.2 Perbandingan Arsitektur: XGBoost vs LightGBM vs CatBoost

| Komponen Arsitektur | XGBoost (v2+) | LightGBM | CatBoost |
| :--- | :--- | :--- | :--- |
| **Tree Growth Strategy** | Level-wise (Depth-wise) secara default; mendukung Leaf-wise | Leaf-wise (Best-first) dengan pembatasan `max_depth` | Symmetric / Oblivious Trees (Level-wise seragam) |
| **Split Finding Algorithm** | Pre-sorted Exact Split & Fast Histogram (`hist`) | Histogram-based Binning | Ordered Target Statistics & MVS (*Minimum Variance Sampling*) |
| **Feature Optimization** | Sparsity-aware split, Block pre-fetching | **EFB** (*Exclusive Feature Bundling*) | On-the-fly categorical combinations |
| **Sample Optimization** | Subsample, Column Subsample | **GOSS** (*Gradient-based One-Side Sampling*) | Random Permutations (Mencegah *Target Leakage*) |
| **Hardware Alignment** | Cache-aware block reading, Out-of-core computing | Discrete bin memory layout (`uint8`), SIMD vectorization | SIMD evaluate instructions, eksekusi GPU masif |
| **Inference Latency Target** | Rendah (~ms) | Sangat Rendah (~ms) | Ultra-low (sub-milidetik, $O(1)$ evaluasi per level) |

##### LightGBM: GOSS dan EFB
1. **GOSS (Gradient-based One-Side Sampling)**: Mempertahankan sampel dengan nilai $|g_i|$ besar (top $a \times 100\%$) karena mereka berkontribusi paling tinggi terhadap informasi gradien, lalu mengambil sampel acak sebesar $b \times 100\%$ dari data bergradien kecil. Gradien data kecil diskalakan dengan faktor $\frac{1-a}{b}$ untuk mempertahankan distribusi data asli:
   $$\tilde{g}_i = g_i \times \frac{1-a}{b} \quad \text{untuk } i \in \text{sampel gradien kecil}$$
2. **EFB (Exclusive Feature Bundling)**: Memanfaatkan fakta bahwa fitur berdimensi tinggi sering kali *mutually exclusive* (jarang bernilai non-zero secara bersamaan). EFB menggabungkan fitur-fitur tersebut ke dalam satu fitur gabungan (*bundle*) dengan menambahkan *offset* konstan pada nilai bin, mereduksi kompleksitas pembangunan histogram dari $O(\text{data} \times \text{fitur})$ menjadi $O(\text{data} \times \text{bundle})$.

##### CatBoost: Oblivious Trees & Ordered Boosting
1. **Oblivious Trees**: Setiap tingkat dalam pohon menggunakan predikat pemisahan (*split criteria*) yang identik di semua daun pada kedalaman tersebut. Pohon seimbang secara simetris, menghasilkan indeks daun sebagai vektor biner sederhana:
   $$\text{Leaf Index} = \sum_{d=0}^{D-1} 2^d \cdot \mathbb{I}(x_{f_d} > \tau_d)$$
   Operasi ini dieksekusi secara instan pada CPU melalui instruksi biner tanpa risiko *branch misprediction*.
2. **Target Encoding Tanpa Bocor**: Menggunakan skema *ordered target statistic* di mana nilai target rata-rata untuk suatu kategori dihitung hanya dari baris-baris data sebelum baris target berdasarkan permutasi acak waktu/urutan:
   $$\hat{x}_k = \frac{\sum_{j=1}^{p-1} [x_{\sigma(j), k} = x_{\sigma(p), k}] \cdot y_{\sigma(j)} + a \cdot P}{\sum_{j=1}^{p-1} [x_{\sigma(j), k} = x_{\sigma(p), k}] + a}$$

---

### 4. Why & What

#### Mengapa Tidak Cukup Hanya Deep Learning?
Untuk data tabular heterogen enterprise (kombinasi variabel kategorikal, numerik tak termormalisasi, data teks pendek, dan data hilang), model ensemble berbasis pohon secara konsisten mengungguli jaringan syaraf tiruan (*neural networks*) dalam hal:
1. **Invariansi Monotonik Fitur**: Pemisahan CART tidak terpengaruh oleh skala fitur numerik, menghilangkan kebutuhan transformasi skala yang rentan terhadap *shift*.
2. **Inductive Bias Data Tabular**: Hubungan dalam data tabular sering kali berupa fungsi tangga non-linier terputus-putus (*discontinuous step functions*), bukan manifold mulus (*smooth manifolds*) yang dioptimalkan oleh Gradient Descent.
3. **Efisiensi Sumber Daya**: Waktu konvergensi dan biaya komputasi training GBDT (*Gradient Boosted Decision Trees*) sering kali 10x-100x lebih rendah dibandingkan arsitektur TabNet atau Transformer berbasis tabular.

#### Kapan Menggunakan Framework Tertentu?
* Gunakan **XGBoost** jika arsitektur sistem membutuhkan ekosistem yang teruji secara luas, integrasi Dask/Spark mendalam, dan penanganan *sparsity* kompleks.
* Gunakan **LightGBM** untuk *large-scale distributed dataset* dengan batasan memori (RAM) ketat dan kebutuhan kecepatan iterasi pelatihan tinggi.
* Gunakan **CatBoost** ketika dataset memiliki rasio fitur kategorikal ber-kardinalitas tinggi yang dominan dan aplikasi produksi memerlukan latensi inferensi ultra-rendah tanpa *pre-processing pipeline* yang rumit.

---

### 5. How (Workflow Detail)

Arsitektur siklus hidup produksi GBDT mencakup langkah-langkah terstruktur berikut:

```
[Feature Store / Data Lake]
            |
            v
[Data Validation & Pre-processing] (Pydantic / Great Expectations)
            |
            v
[Distributed Training Engine] (LightGBM/XGBoost on Ray/Slurm)
            |
            +---> [Hyperparameter Tuning] (Optane/Hyperopt - Bayesian)
            |
            v
[Model Serialization & Compilation] (Treelite -> Shared Object .so / ONNX)
            |
            v
[Inference Serving Microservice] (C++ Inference Engine / Triton / FastAPI)
            |
            v
[Telemetry & Drift Monitoring] (Evidently / Custom Prometheus Exporter)
```

1. **Ingestion & Data Binning**: Data numerik dikonversi ke *binned representation* (biasanya `uint8` dengan 256 bin) pada lapisan ingestion untuk menghemat penggunaan memori hingga 75%.
2. **Distributed Tree Building**: Paralelisasi komputasi histogram pada setiap *worker* secara lokal, dilanjutkan dengan reduksi *all-reduce* untuk menemukan split optimal secara global.
3. **Model Transpilation/Compilation**: Model biner diekstrak ke AST (*Abstract Syntax Tree*), dioptimasi untuk memangkas *redundant paths*, lalu dikompilasi menjadi *machine code* C menggunakan Treelite.
4. **Production Serving**: Pemuatan *shared library* (`.so` atau `.dll`) ke dalam memori aplikasi menggunakan integrasi C-ABI/FFI langsung untuk mengeksekusi inferensi dalam skala mikrodetik.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sidang Juri Ahli (Ensemble) vs Kompilasi Jalur Bebas Hambatan (Inference Engine)
Bayangkan sebuah dewan dokter spesialis (GBDT):
* Dokter pertama memeriksa pasien secara umum dan membuat diagnosa kasar (Base Learner).
* Dokter kedua tidak mengulang diagnosa dokter pertama, melainkan hanya menganalisis kesalahan/gejala sisa yang gagal didiagnosa dokter pertama (Residual Gradient Orde-1 & Orde-2).
* Dokter ketiga fokus hanya pada inkonsistensi yang ditinggalkan oleh dokter pertama dan kedua.

Dalam produksi konvensional, setiap pasien harus melewati puluhan pintu dan belokan untuk menemui setiap dokter (*branch conditional jumps*). Dalam **Tree Compilation**, seluruh jalur keputusan dokter telah dipetakan sebelumnya ke dalam sistem sirkuit elektronik instan (*branchless bitmask execution*), sehingga data pasien langsung masuk dan keluar tanpa antrean percabangan CPU.

#### Diagram: Perbedaan Leaf-wise vs Depth-wise

```
Depth-wise / Level-wise (XGBoost Default)
                  (Root)
                 /      \
             Level 1   Level 1      <--- Seluruh level diekspansi seragam
             /    \     /    \
            L2    L2   L2    L2

Leaf-wise / Best-first (LightGBM)
                  (Root)
                 /      \
             Level 1   Level 1
                       /      \
                    Level 2  Level 2 <--- Hanya daun dengan split gain
                             /     \      tertinggi yang diekspansi
                           L3       L3
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Mathematical Second-Order Custom Objective (Python Native)

Implementasi fungsi kerugian asimetris (*Asymmetric Huber Loss*) dengan kalkulasi manual gradien dan Hessian.

```python
import numpy as np

def asymmetric_huber_loss(
    y_true: np.ndarray, 
    y_pred: np.ndarray, 
    delta: float = 1.0, 
    underpredict_penalty: float = 2.0
) -> tuple[np.ndarray, np.ndarray]:
    """
    Menghitung First-order Gradient (g_i) dan Second-order Hessian (h_i)
    untuk Asymmetric Huber Loss. Memberikan penalti lebih besar jika under-prediction.
    """
    residual = y_pred - y_true
    abs_residual = np.abs(residual)
    
    # Skalar penalti: lebih tinggi jika residual < 0 (y_pred < y_true)
    penalty_weight = np.where(residual < 0, underpredict_penalty, 1.0)
    
    # Inisialisasi gradien dan Hessian
    grad = np.zeros_like(residual)
    hess = np.zeros_like(residual)
    
    # Masking kondisi kuadratik vs linear Huber
    linear_mask = abs_residual > delta
    quadratic_mask = ~linear_mask
    
    # 1. Quadratic Region: |res| <= delta
    grad[quadratic_mask] = penalty_weight[quadratic_mask] * residual[quadratic_mask]
    hess[quadratic_mask] = penalty_weight[quadratic_mask]
    
    # 2. Linear Region: |res| > delta
    grad[linear_mask] = penalty_weight[linear_mask] * delta * np.sign(residual[linear_mask])
    hess[linear_mask] = 1e-6  # Hessian stabil non-nol untuk optimasi boosting
    
    return grad, hess
```

#### 7.2 Practical Example: Enterprise Production Pipeline & Model Compilation

Kode di bawah membangun model LightGBM enterprise, memvalidasi performa, mengompilasi model ke format *shared binary* melalui Treelite untuk inferensi berlatensi rendah, serta membungkusnya dalam wrapper inferensi kelas produksi.

```python
import os
import shutil
import tempfile
import time
from typing import Any, Dict, Tuple
import lightgbm as lgb
import numpy as np
import treelite
import treelite_runtime
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split


class ProductionTreePipeline:
    """Pipeline terintegrasi untuk pelatihan, kompilasi C-shared library,
    dan benchmark inferensi Tree Ensemble berkinerja tinggi."""

    def __init__(self, n_estimators: int = 200, max_depth: int = 6):
        self.params: Dict[str, Any] = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "learning_rate": 0.05,
            "num_leaves": 2**max_depth,
            "max_depth": max_depth,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "n_jobs": -1,
        }
        self.n_estimators = n_estimators
        self.model: lgb.Booster | None = None
        self.compiled_lib_path: str | None = None
        self.predictor: treelite_runtime.Predictor | None = None

    def train(
        self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray
    ) -> None:
        """Melatih model LightGBM dengan validasi awal."""
        dtrain = lgb.Dataset(X_train, label=y_train)
        dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

        self.model = lgb.train(
            self.params,
            dtrain,
            num_boost_round=self.n_estimators,
            valid_sets=[dtrain, dval],
            callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
        )

    def compile_model(self, output_dir: str = "./model_artifacts") -> str:
        """Mengompilasi model LightGBM menjadi Native Shared Object (.so)

        menggunakan Treelite.
        """
        if self.model is None:
            raise ValueError("Model belum dilatih. Panggil train() terlebih dahulu.")

        os.makedirs(output_dir, exist_ok=True)
        temp_lgb_file = os.path.join(output_dir, "temp_model.txt")
        self.model.save_model(temp_lgb_file)

        # Import model ke dalam format treelite
        tl_model = treelite.Model.load(temp_lgb_file, model_format="lightgbm")

        # Compile AST model ke shared library C
        lib_ext = ".dll" if os.name == "nt" else ".so"
        compiled_lib = os.path.join(output_dir, f"model_compiled{lib_ext}")

        # Parameter kompilasi khusus CPU
        params = {"parallel_comp": os.cpu_count() or 4}
        tl_model.export_lib(
            toolchain="gcc" if os.name != "nt" else "msvc",
            libpath=compiled_lib,
            params=params,
            verbose=False,
        )

        if os.path.exists(temp_lgb_file):
            os.remove(temp_lgb_file)

        self.compiled_lib_path = compiled_lib
        self.predictor = treelite_runtime.Predictor(libpath=self.compiled_lib_path)
        return self.compiled_lib_path

    def predict_compiled(self, X: np.ndarray) -> np.ndarray:
        """Inferensi menggunakan branchless C-runtime."""
        if self.predictor is None:
            raise RuntimeError("Model belum dikompilasi via Treelite.")

        # Buat batch input treelite khusus
        batch = treelite_runtime.Batch.from_npy2d(X.astype(np.float32))
        return self.predictor.predict(batch)


def run_benchmarking():
    """Fungsi eksekusi pengujian latensi inferensi batch vs single instance."""
    print("[+] Membuat dataset sintetis enterprise (100,000 baris, 50 fitur)...")
    X, y = make_classification(
        n_samples=100_000,
        n_features=50,
        n_informative=35,
        n_redundant=15,
        random_state=42,
    )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    pipeline = ProductionTreePipeline(n_estimators=150, max_depth=6)
    print("[+] Memulai training LightGBM...")
    pipeline.train(X_train, y_train, X_test, y_test)

    temp_dir = tempfile.mkdtemp()
    try:
        print("[+] Mengompilasi Tree AST ke Native Shared Object (.so/.dll)...")
        pipeline.compile_model(output_dir=temp_dir)

        # Uji latensi native model LightGBM
        sample_single = X_test[:1].astype(np.float32)

        # Warm-up run
        _ = pipeline.model.predict(sample_single)
        _ = pipeline.predict_compiled(sample_single)

        runs = 2000
        # Benchmark Python Native
        start = time.perf_counter()
        for _ in range(runs):
            _ = pipeline.model.predict(sample_single)
        lgb_time = (time.perf_counter() - start) / runs * 1000  # dalam milidetik

        # Benchmark Treelite Runtime
        start = time.perf_counter()
        for _ in range(runs):
            _ = pipeline.predict_compiled(sample_single)
        tl_time = (time.perf_counter() - start) / runs * 1000  # dalam milidetik

        print(f"\n--- HASIL BENCHMARK LATENSI SINGLE RECORD ({runs} iterasi) ---")
        print(f"Standard LightGBM Inference : {lgb_time:.4f} ms per request")
        print(f"Compiled Treelite Inference : {tl_time:.4f} ms per request")
        print(f"Akselerasi Latensi           : {lgb_time / tl_time:.2f}x lebih cepat")

    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    run_benchmarking()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Financial Fraud Detection Engine (Tingkat Transaksi Global)

* **Skala Sistem**: Sistem pemrosesan transaksi kartu kredit global memproses $45.000\text{ transaksi/detik}$ secara konkuren.
* **SLA (Service Level Agreement)**:
  * Maksimum P99.9 Inference Latency: $\le 2.5\text{ ms}$.
  * Retraining frequency: Setiap 6 jam sekali menggunakan data geser 30 hari terakhir.
* **Tantangan Arsitektur**:
  1. Fitur transaksi agregat mencakup histori dinamis (misal: *frekuensi transaksi 5 menit terakhir*, *deviasi nilai dari rata-rata historis bulanan*).
  2. Extreme class imbalance ($0.012\%$ kecurangan).
  3. Degradasi model (*concept drift*) sangat cepat akibat teknik fraudster yang terus berevolusi.
* **Solusi Arsitektur**:
  * **Algoritma**: LightGBM dengan GOSS aktif dan parameter penyeimbang bobot `scale_pos_weight` yang dioptimasi via skema Focal Loss.
  * **Feature Engineering**: Feast Feature Store terhubung secara asinkron via Redis Cluster untuk penyajian fitur sub-milidetik.
  * **Serving Optimization**: Konversi model LightGBM menggunakan Treelite ke C++ Shared Object, dimuat dalam container C++ kustom berbasis Drogon HTTP Framework / Envoy gRPC Proxy.
  * **Pencegahan Drift**: Memasang layer Kolmogorov-Smirnov Test (KS-Test) dan Population Stability Index (PSI) berbasis stream melalui Kafka consumer untuk memicu *automated model re-training* secara mandiri jika PSI melampaui ambang batas $0.25$.

```
[User Swipe] 
     |
     v
[API Gateway] ---> [Redis Feature Store] (Fetch <1ms: historical aggregates)
     |
     v
[Triton / C++ Treelite Server] (Model Evaluation: 0.25ms)
     |
     +---> Score > Threshold? ---> [Block Transaction]
     |
     v
[Kafka Logging Stream] ---> [Evidently / Drift Detector Engine]
                                     | (PSI > 0.25)
                                     v
                        [Airflow Retraining Pipeline]
```

---

### 9. Trade-offs

| Metrik Desain | Exact Split Searching (GBDT Tradisional) | Histogram-based Split (XGBoost `hist` / LightGBM) | Compiled Trees (Treelite/ONNX) |
| :--- | :--- | :--- | :--- |
| **Akurasi / Presisi Split** | Sangat Presisi ($O(N)$ kontinu) | Hampir identik dengan Exact ($\le 0.05\%$ selisih metrik AUC) | Identik secara floating point dengan histogram aslinya |
| **Alokasi Memori (RAM)** | Sangat Boros ($O(N \times D \times 4\text{ bytes})$) | Sangat Hemat ($O(N \times D \times 1\text{ byte})$ via `uint8`) | Minimal pada inference runtime (hanya *weight matrices*) |
| **Training Speed** | Lambat ($O(D \cdot N \log N)$ per level) | Sangat Cepat ($O(D \cdot K)$ di mana $K$ adalah jumlah bin) | Tidak relevan (Hanya fokus pada fase Serving) |
| **Serving Latency** | Tinggi ($> 5\text{ ms}$, CPU pointer traversal) | Menengah ($1 - 5\text{ ms}$) | Ultra Rendah ($< 0.5\text{ ms}$, branchless/bitmask) |
| **Kompleksitas Deployment** | Rendah (Native Model Save/Load) | Rendah | Tinggi (Memerlukan kompilasi GCC/Clang & C runtime) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Konfigurasi `max_depth` vs `num_leaves` pada LightGBM
* **Gejala**: Model mengalami *severe overfitting* seketika meski `max_depth` telah diatur ke 6.
* **Akar Masalah**: Berbeda dengan XGBoost yang menumbuhkan pohon per kedalaman, LightGBM menggunakan algoritma *leaf-wise*. Nilai `num_leaves` secara default adalah 31. Jika pengguna mengatur `num_leaves = 255` namun mengira `max_depth = 6` akan membatasinya, relasi $2^{\text{max\_depth}}$ terabaikan. Pohon tumbuh sangat dalam pada cabang tunggal tertentu.
* **Solusi**: Pastikan aturan praktis berikut diterapkan:
  $$\text{num\_leaves} \le 2^{\text{max\_depth}} \times 0.7$$
  Contoh: Untuk `max_depth = 6`, atur `num_leaves` antara 30 hingga 45.

#### 2. Target Leakage Melalui Categorical Target Statistics di CatBoost / Pandas
* **Gejala**: AUC pada data training mencapai $0.999$, namun skor pada data test atau validasi turun drastis ke $0.650$.
* **Akar Masalah**: Menghitung mean encoding terhadap seluruh fitur kategorikal sebelum pemisahan data train-test atau cross-validation.
* **Solusi**: Terapkan *Out-Of-Fold Mean Target Encoding* atau serahkan representasi fitur kategorikal murni langsung kepada native engine CatBoost yang mengeksekusi *Ordered Target Statistics* menggunakan permutasi internal acak.

#### 3. Thread Contention Pada Komputasi Inferensi Konkuren Tinggi
* **Gejala**: Saat pengujian *stress test* di produksi (misal: 500 koneksi bersamaan via FastAPI/Gunicorn), CPU model latency melonjak dari 2 ms menjadi 120 ms.
* **Akar Masalah**: Pustaka OpenMP pada XGBoost/LightGBM berusaha membuat thread sebanyak core CPU untuk *setiap request masuk*. Ketika puluhan request paralel dieksekusi, terjadi *thread context switching storm*.
* **Solusi**: Paksa parameter runtime single-threaded per request:
  ```python
  pipeline.params["n_jobs"] = 1  # Hindari OpenMP over-threading per inferensi
  ```
  Biarkan web server (Gunicorn workers / Uvicorn loops) yang mengelola konkurensi di tingkat sistem operasi.

---

### 11. Best Practices (Production Checklist)

1. [ ] **Monotonicity Constraints**: Terapkan *Monotone Constraints* jika fitur memiliki hubungan kausalitas domain yang jelas (misal: rasio hutang lebih tinggi tidak boleh menurunkan risiko kredit) menggunakan parameter `monotone_constraints`.
2. [ ] **Histogram Binning Pre-alignment**: Tetapkan ukuran `max_bin=255` untuk menjaga seluruh data bin berada dalam tipe data `uint8`, mengoptimalkan *CPU vector instruction* (AVX-512) dan memori cache L1/L2.
3. [ ] **Inference Memory Locking**: Kunci memori binary model menggunakan flag `mlock` saat serving untuk mencegah OS memindahkan halaman memori model ke area *swap disk*.
4. [ ] **Input Sanitization**: Validasikan bahwa semua *missing values* direpresentasikan sebagai `NaN` IEEE-754 standar yang seragam, karena pohon GBDT menangani `NaN` secara konsisten pada cabang *default path*, bukan nilai -999 atau 0 tersembunyi.
5. [ ] **Early Stopping Determinism**: Gunakan dataset validasi yang dikunci (*fixed immutable validation set*) dan gunakan window `stopping_rounds` minimal $10\%$ dari total estimator untuk menghindari terminasi dini pada dataran lokal (*local plateaus*).

---

### 12. Hands-on Practice

Buat dan simpan file-file berikut pada direktori: `hands-on/m02/`

#### File 1: `hands-on/m02/dataset_generator.py`
```python
"""Generator dataset transaksi finansial berskala menengah untuk pengujian produksi."""
import numpy as np
import pandas as pd


def generate_streaming_data(
    n_rows: int = 50_000, seed: int = 42
) -> Tuple[pd.DataFrame, pd.Series]:
    np.random.seed(seed)
    feature_a = np.random.exponential(scale=2.0, size=n_rows)
    feature_b = np.random.normal(loc=10.0, scale=3.0, size=n_rows)
    feature_c = np.random.choice(
        ["MERCHANT_A", "MERCHANT_B", "MERCHANT_C", "UNKNOWN"], size=n_rows
    )
    feature_d = np.random.uniform(0, 100, size=n_rows)

    # Induksi target nonlinear dengan residual kompleks
    logits = (
        0.5 * feature_a
        - 0.3 * feature_b
        + np.where(feature_c == "MERCHANT_A", 1.2, -0.8)
        + 0.05 * feature_d
    )
    prob = 1 / (1 + np.exp(-logits))
    target = (np.random.rand(n_rows) < prob).astype(int)

    df = pd.DataFrame(
        {
            "feat_exp": feature_a,
            "feat_norm": feature_b,
            "feat_cat": feature_c,
            "feat_unif": feature_d,
        }
    )
    return df, pd.Series(target, name="is_fraud")


if __name__ == "__main__":
    df, y = generate_streaming_data(100)
    print("Dataset generated successfully. Sample:")
    print(df.head())
```

#### File 2: `hands-on/m02/train_and_export.py`
```python
"""Pelatihan model CatBoost & XGBoost, penanganan fitur kategorikal, dan ekspor AST."""
import os
from catboost import CatBoostClassifier, Pool
from dataset_generator import generate_streaming_data
from sklearn.model_selection import train_test_split


def run_pipeline():
    X, y = generate_streaming_data(n_rows=20_000)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    cat_features = ["feat_cat"]

    # Inisialisasi CatBoost dengan Oblivious Trees
    cb_model = CatBoostClassifier(
        iterations=300,
        learning_rate=0.08,
        depth=6,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=42,
        verbose=50,
    )

    train_pool = Pool(X_train, y_train, cat_features=cat_features)
    val_pool = Pool(X_val, y_val, cat_features=cat_features)

    cb_model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=30)

    # Ekspor ke representasi portable (CPP standalone class)
    os.makedirs("./artifacts", exist_ok=True)
    cpp_export_path = "./artifacts/catboost_evaluator.cpp"
    cb_model.save_model(cpp_export_path, format="cpp")
    print(
        f"[+] Standalone High-Speed C++ Model Code exported to: {cpp_export_path}"
    )


if __name__ == "__main__":
    run_pipeline()
```

#### File 3: `hands-on/m02/drift_monitor.py`
```python
"""Script monitoring Population Stability Index (PSI) untuk ensemble model."""
import numpy as np


def calculate_psi(
    expected: np.ndarray, actual: np.ndarray, num_buckets: int = 10
) -> float:
    """Menghitung metrik drift PSI antara data baseline (expected) dan data produksi (actual)."""

    def scale_range(input_data, min_val, max_val):
        return input_data * (max_val - min_val) + min_val

    # Buat breakpoints dari populasi referensi
    percentiles = np.linspace(0, 100, num_buckets + 1)
    breakpoints = np.percentile(expected, percentiles)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    # Hitung proporsi sampel dalam bucket
    expected_counts = np.histogram(expected, bins=breakpoints)[0]
    actual_counts = np.histogram(actual, bins=breakpoints)[0]

    expected_pct = expected_counts / len(expected)
    actual_pct = actual_counts / len(actual)

    # Handling zero frequency untuk stabilitas numerik
    expected_pct = np.where(expected_pct == 0, 0.0001, expected_pct)
    actual_pct = np.where(actual_pct == 0, 0.0001, actual_pct)

    # Formula matematis PSI
    psi_value = np.sum(
        (actual_pct - expected_pct) * np.log(actual_pct / expected_pct)
    )
    return float(psi_value)


if __name__ == "__main__":
    baseline_predictions = np.random.beta(a=2, b=5, size=5000)
    current_production_predictions = np.random.beta(
        a=3, b=4, size=5000
    )  # Distribusi bergeser

    psi = calculate_psi(baseline_predictions, current_production_predictions)
    print(f"Calculated Drift PSI: {psi:.4f}")
    if psi > 0.2:
        print("[ALERT] Signifikan Drift Terdeteksi! Pemicu re-training otomatis.")
    elif psi > 0.1:
        print("[WARNING] Moderate Shift. Pantau metrik presisi.")
    else:
        print("[OK] Distribusi model stabil.")
```

---

### 13. Exercise

#### Level Easy
1. Modifikasi script `dataset_generator.py` untuk menginduksi $20\%$ *missing values* (`np.nan`) secara acak pada `feat_norm`. Latih XGBoost menggunakan API native (`xgb.DMatrix`) dan amati ke arah cabang mana (*default direction*) data missing diarahkan.

#### Level Medium
1. Implementasikan custom loss function *Focal Loss* pada XGBoost dengan mendefinisikan ekspansi gradien orde-1 ($g_i$) dan Hessian orde-2 ($h_i$).
   $$\text{FL}(p_t) = -\alpha_t (1 - p_t)^\gamma \log(p_t)$$
   Bandingkan konvergensinya terhadap standard Cross-Entropy pada dataset yang memiliki rasio imbalance $99:1$.

#### Level Hard
1. Buat custom benchmark script multi-thread (menggunakan Python `concurrent.futures`) yang menyimulasikan 50 thread konkuren melakukan query terhadap:
   * LightGBM Python `.predict()`
   * Treelite Compiled Shared Object `.so`
   Ukur dan plot perbandingan grafik distribusi latensi: Mean, P90, P99, dan P99.9.

---

### 14. Challenge

**Skenario Kasus**: Anda memegang peran Principal ML Engineer pada platform Ride-Hailing terkemuka.
* **Problem**: Sistem algoritma *Dynamic Dispatching Engine* harus mengevaluasi $500$ mitra pengemudi terdekat untuk $1$ pesanan penumpang secara *real-time*. Evaluasi harus selesai dalam waktu total $< 15\text{ ms}$ (termasuk jaringan). Model yang digunakan adalah ensemble 800 pohon keputusan per batch driver.
* **Kebutuhan Teknis**:
  1. Rancang arsitektur pipeline komputasi end-to-end yang mengombinasikan pengambilan vektor fitur dari distributed in-memory cache, komputasi matriks driver, evaluasi inference, hingga ranking akhir.
  2. Susun desain dokumen teknis (Technical Architecture Document) yang mendefinisikan:
     * Bagaimana cara meminimalkan memory footprint pada driver hardware target.
     * Mengapa format JSON serialisasi standar tidak dapat digunakan pada throughput ini dan format binary IPC apa yang Anda pilih (misal: Apache Arrow / FlatBuffers).
     * Solusi jika terjadi divergensi performa (*inference divergence*) antara model saat ditrain di Python vs binary C-runtime yang terkompilasi.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Mengapa XGBoost memerlukan turunan orde kedua (Hessian $h_i$), sedangkan Gradient Boosting tradisional (Friedman) hanya menggunakan gradien orde pertama?**
   * A. Karena turunan orde kedua menghilangkan kebutuhan proses regularisasi.
   * B. Karena deret Taylor orde kedua memberikan aproksimasi kuadratik lokal yang memungkinkan konvergensi langkah Newton-Raphson langsung ke titik optimum tanpa menghitung step size manual.
   * C. Karena Hessian selalu bernilai 1.0 pada semua jenis fungsi objektif.
   * D. Karena ekspansi Taylor orde pertama tidak dapat dihitung pada GPU.

2. **Apa fungsi utama dari parameter regularisasi $\gamma$ (gamma) pada formulasi split XGBoost?**
   * A. Mengontrol laju pembelajaran (*shrinkage*).
   * B. Mengatur ambang minimum gain yang harus dicapai agar split baru diizinkan terbentuk pada leaf node.
   * C. Mengatur rasio sub-sampel kolom data.
   * D. Menentukan batas kedalaman absolut dari pohon.

3. **Strategi pertumbuhan pohon Leaf-wise (Best-first) pada LightGBM cenderung lebih rentan mengalami overfitting dibandingkan Depth-wise jika tidak dibatasi oleh:**
   * A. Learning rate yang tinggi.
   * B. Nilai `max_depth` atau `num_leaves`.
   * C. Jumlah bin pada histogram.
   * D. Fitur kategorikal.

4. **Bagaimana algoritma EFB (Exclusive Feature Bundling) pada LightGBM menurunkan kompleksitas waktu komputasi?**
   * A. Dengan menghapus fitur yang memiliki korelasi tinggi dengan target.
   * B. Dengan membagi bobot daun berdasarkan matriks invers.
   * C. Dengan menggabungkan fitur-fitur sparse yang jarang bernilai aktif (non-zero) bersamaan ke dalam satu feature bundle tunggal.
   * D. Dengan mendiskritisasi seluruh data kontinu menjadi tipe data boolean.

5. **Apa yang dimaksud dengan Oblivious Trees pada arsitektur CatBoost?**
   * A. Pohon yang dibangun tanpa mempertimbangkan fitur kontinu.
   * B. Pohon simetris di mana predikat split yang sama digunakan pada seluruh node di tingkat kedalaman yang sama.
   * C. Model pohon yang secara berkala menghapus leaf node dengan sampel terkecil.
   * D. Pohon yang tidak menyimpan riwayat training untuk menjaga privasi data.

---

#### Bagian 2: Intermediate (5 Soal)
6. **Pada algoritma GOSS (Gradient-based One-Side Sampling), mengapa sampel dengan gradien kecil diskalakan ulang dengan faktor konstanta $\frac{1-a}{b}$?**
   * A. Agar loss function tidak meledak (*exploding gradients*).
   * B. Untuk memprioritaskan sampel kecil di atas sampel besar saat penentuan split.
   * C. Untuk mempertahankan integritas distribusi data estimasi asli tanpa bias yang timbul akibat pembuangan sampel bergradien kecil.
   * D. Untuk mengonversi gradien float menjadi bilangan bulat `uint8`.

7. **Dalam serving model tree berskala latensi mikrodetik, mengapa kompilasi model ke branchless code C via Treelite lebih unggul secara mekanis daripada evaluasi tree traversal `if-else` tradisional?**
   * A. Karena C code tidak membutuhkan alokasi memori RAM sama sekali.
   * B. Karena menghindari CPU *Branch Misprediction Penalty* pada instruksi pipeline CPU level instruksi assembly.
   * C. Karena Treelite mengonversi tree ensemble menjadi Deep Neural Network linier.
   * D. Karena C code secara otomatis mengaktifkan enkripsi end-to-end pada inference data.

8. **Jika matriks Hessian $\sum h_i$ bernilai mendekati nol pada suatu leaf node, efek apa yang secara matematis akan terjadi pada bobot daun $w^*$ jika $\lambda = 0$?**
   * A. Bobot daun menjadi nol.
   * B. Nilai pembagi mendekati nol sehingga bobot meledak (*infinite explosion*) dan menurunkan stabilitas numerik secara ekstrem.
   * C. Gain pohon menjadi negatif tanpa batas.
   * D. Model berubah menjadi linear regression biasa.

9. **Mengapa *Target Encoding* konvensional menyebabkan target leakage parah pada GBDT, dan bagaimana CatBoost menyelesaikannya secara matematis?**
   * A. Target encoding menghapus data kosong; CatBoost mengisinya dengan median data.
   * B. Target encoding memasukkan informasi label baris $i$ ke dalam nilai fitur baris $i$ itu sendiri; CatBoost menggunakan *Ordered Target Statistics* berdasarkan permutasi data masa lalu.
   * C. Target encoding meningkatkan korelasi Pearson; CatBoost menggunakan korelasi Spearman.
   * D. CatBoost mengonversi seluruh label target menjadi bilangan bulat acak saat training.

10. **Berapa alokasi memori minimum teoritis yang dibutuhkan untuk menyimpan matriks bin jika sebuah dataset memiliki 10.000.000 baris, 100 fitur numerik, dan dikuantisasi menggunakan `max_bin=255`?**
    * A. $\approx 100\text{ MB}$
    * B. $\approx 1\text{ GB}$ ($10^7 \times 100 \times 1\text{ byte} = 10^9\text{ bytes}$)
    * C. $\approx 4\text{ GB}$ ($10^7 \times 100 \times 4\text{ bytes}$)
    * D. $\approx 8\text{ GB}$

---

#### Bagian 3: Skenario Kasus Produksi (3 Soal)
11. **Kasus 1: Model Risk Assessment Real-time**
    Sebuah tim deploying model XGBoost pada cluster Kubernetes menggunakan container FastAPI. Saat load testing mencapai 2.000 RPS, CPU Utilization mencapai $100\%$, namun throughput anjlok drastis dan response time P99 membengkak ke $800\text{ ms}$. Profiling menunjukkan terjadi *thread context-switching* masif pada kernel OS. Langkah konfigurasi arsitektur mana yang paling tepat untuk menstabilkan sistem?
    * A. Tingkatkan `n_estimators` pada model XGBoost agar komputasi lebih merata.
    * B. Atur variabel lingkungan `OMP_NUM_THREADS=1` pada level container dan sesuaikan skala konkurensi melalui jumlah worker proses server.
    * C. Ubah format model menjadi format pickle python native.
    * D. Pindahkan seluruh cluster inferensi ke arsitektur GPU berskala besar tanpa mengubah konfigurasi thread.

12. **Kasus 2: Degradasi Bertahap Fitur Finansial (Data Drift)**
    Sebuah model LightGBM pada sistem deteksi penipuan pinjaman online menunjukkan nilai metrik AUC yang stabil pada set validasi statis, namun metrik bisnis tingkat penagihan (*recovery rate*) di lapangan turun $18\%$ dalam 3 bulan. Pemeriksaan menunjukkan fitur `penghasilan_bulanan` mengalami pergeseran distribusi dengan nilai PSI (*Population Stability Index*) sebesar $0.32$. Apa tindakan intervensi teknis yang paling tepat?
    * A. Abaikan metrik PSI dan tetap gunakan model yang sama karena nilai validasi statis masih optimal.
    * B. Turunkan nilai learning rate model pada inference pipeline tanpa retraining.
    * C. Isolasi fitur yang mengalami drift, perbarui representasi binning histogram, dan lakukan re-training model menggunakan moving window data transaksi terkini secara periodik.
    * D. Konversi fungsi objektif menjadi mean absolute error.

13. **Kasus 3: Kebutuhan Edge IoT Deployment**
    Anda harus mengimplementasikan model GBDT ke dalam chip mikroprosesor ARM berbasis RTOS pada sistem pemeliharaan mesin pabrik (IoT edge device) dengan RAM tersisa hanya $4\text{ MB}$ dan tanpa ketersediaan runtime Python. Bagaimana arsitektur deployment yang harus dirancang?
    * A. Deploy FastAPI runtime menggunakan micro-docker pada perangkat IoT.
    * B. Latih model di cloud, kompilasi representasi AST pohon ke kode sumber mandiri C/C++ statis murni tanpa dependensi eksternal via Treelite/CatBoost CPP Export, lalu build ke target biner bertenaga native compiler cross-platform.
    * C. Gunakan protokol web socket untuk mengirim data mentah dari IoT ke server cloud pusat secara kontinyu tanpa memprosesnya di edge.
    * D. Ganti model ensemble pohon dengan model Transformer deep learning 12 layer.

---

### Kunci Jawaban & Evaluasi Singkat

#### Bagian 1
1. **B** - Ekspansi Taylor orde kedua memberikan informasi kelengkungan (*curvature*) melalui nilai Hessian sehingga ukuran langkah split dapat dioptimasi langsung secara kuadratik tanpa line search manual.
2. **B** - $\gamma$ bertindak sebagai konstanta penalti kompleksitas minimum gain yang wajib dilampaui agar sebuah partisi split dapat dipertahankan.
3. **B** - Tanpa pembatasan kedalaman atau jumlah daun, Leaf-wise akan terus memecah cabang spesifik yang memberikan penurunan loss tertinggi, memicu overfitting tajam pada sampel minoritas.
4. **C** - EFB memanfaatkan *sparsity* dengan mengemas fitur yang jarang overlap secara eksklusif ke dalam wadah bin yang sama, mereduksi dimensi fitur tanpa kehilangan informasi.
5. **B** - Ciri khas Oblivious Trees adalah keseragaman kondisi pembagian pada kedalaman yang sama di seluruh cabang pohon, menjadikannya simetris dan mudah dievaluasi melalui instruksi bitmask.

#### Bagian 2
6. **C** - Penskalaan $\frac{1-a}{b}$ menjamin nilai ekspektasi gradien total dari sampel terkoreksi tetap tidak bias terhadap populasi data awal.
7. **B** - Kompilasi C mereduksi percabangan tak terduga (*unpredictable branches*) pada pipeline instruksi prosesor, menghilangkan siklus CPU yang terbuang akibat salah prediksi percabangan (*branch misprediction flush*).
8. **B** - Formulasi bobot adalah $-\frac{G}{H + \lambda}$. Jika $H \to 0$ dan $\lambda = 0$, penyebut bernilai nol sehingga bobot matematis menjadi divergen/tak terhingga.
9. **B** - Ordered boosting menggunakan urutan riwayat pseudo-waktu (permutasi acak) sehingga kalkulasi target rate suatu baris hanya melihat baris data pada urutan sebelum dirinya sendiri.
10. **B** - $10.000.000\text{ baris} \times 100\text{ fitur} \times 1\text{ byte (uint8)} = 1.000.000.000\text{ bytes} \approx 1\text{ GB}$.

#### Bagian 3
11. **B** - Threading OpenMP internal XGBoost pada sistem paralel tinggi memicu *race condition* dan *thread contention* pada CPU core. Menyetel threading level library ke 1 dan membiarkan process-level concurrency bekerja adalah arsitektur serving yang benar.
12. **C** - Nilai $\text{PSI} > 0.25$ menunjukkan perubahan struktural signifikan pada distribusi populasi. Model memerlukan kalibrasi ulang batasan histogram dan re-training pada jendela data mutakhir.
13. **B** - Melakukan ekspor pohon ke kode sumber C/C++ statis menghilangkan overhead runtime, memiliki jejak memori yang sangat kecil ($< 1\text{ MB}$), dan dapat dieksekusi secara native langsung di arsitektur mikroprosesor mana pun.

---

### 16. Summary

1. **Aproksimasi Orde Kedua Adalah Standar Modern**: Seluruh ekosistem modern boosting mengandalkan ekspansi deret Taylor orde kedua untuk memisahkan logika komputasi turunan fungsi objektif dari proses konstruksi struktur pohon keputusan.
2. **Histogram Menggeser Paradigma Training**: Pergeseran dari pencarian split kontinu (*Exact Split*) ke diskritisasi binning histogram (`uint8`) merupakan lompatan terpenting dalam komputasi efisien data tabular, memangkas latensi memory bandwidth dan alokasi RAM secara masif.
3. **Penyelarasan Algoritma dan Perangkat Keras**: Arsitektur internal seperti GOSS (LightGBM) menghemat bandwidth komputasi, EFB menghemat dimensi komputasi, dan Oblivious Trees (CatBoost) menyelaraskan evaluasi model langsung ke tingkat operasi register/SIMD prosesor modern.
4. **Jalur Produksi Bukan Pipeline Eksperimen**: Model pohon yang masuk ke lingkungan produksi berlatensi rendah tidak boleh disajikan secara naif melalui wrapper Python generic. Pemanfaatan *Tree Compiler* (seperti Treelite, ONNX, atau native C++ transpilation) adalah keharusan operasional untuk mencapai determinisme latensi sub-milidetik secara konsisten.