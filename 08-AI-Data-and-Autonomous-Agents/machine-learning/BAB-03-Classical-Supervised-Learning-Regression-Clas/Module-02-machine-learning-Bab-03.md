# Kurikulum Enterprise: Machine Learning (08-AI-Data-and-Autonomous-Agents)
## Bab 03: Classical Supervised Learning — Regression & Classification
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik pada level Senior Machine Learning Engineer / AI Systems Architect diharapkan mampu:

1. **Menganalisis Mekanika Matematis Optimasi Supervised Learning**: Menurunkan secara analitis dan mengimplementasikan optimasi order pertama (Gradient Descent, Momentum) dan order kedua (Newton-Raphson, Fisher Scoring, L-BFGS) untuk Generalized Linear Models (GLM) dan Support Vector Machines (SVM).
2. **Menguasai Dekonstruksi Algoritmik GBDT**: Membedah arsitektur internal Gradient Boosted Decision Trees (GBDT), termasuk aproksimasi deret Taylor orde kedua pada fungsi loss, perbandingan algoritma split finding (*Exact Greedy* vs. *Histogram-based Binning*), serta mekanisme *Gradient-based One-Side Sampling* (GOSS) dan *Exclusive Feature Bundling* (EFB).
3. **Mengimplementasikan Kalibrasi Probabilitas Lanjutan**: Mendiagnosis dan mengoreksi miskalibrasi output model non-parametrik menggunakan *Platt Scaling* (regresi logistik univariat) dan *Isotonic Regression* (Pair Adjacent Violators Algorithm / PAVA) untuk sistem inferensi berisiko tinggi.
4. **Membangun Arsitektur Inferensi Ultra-Low Latency**: Mengompilasi dan mengoptimalkan model *tree-based* dan linier ke dalam format komputasi graf statis (ONNX Runtime, Treelite) dengan optimasi SIMD dan pemanfaatan memori *zero-copy* untuk mencapai SLA latensi p99 $< 5$ milidetik.
5. **Merancang Sistem Monitoring Drift Produksi**: Mengintegrasikan metrik statistik non-parametrik (Population Stability Index / PSI, Kolmogorov-Smirnov test, Wasserstein Distance) ke dalam pipeline inferensi *real-time* guna mendeteksi *covariate shift* dan *concept drift*.

---

## 2. Prerequisite

Untuk menyerap materi ini secara optimal, peserta diwajibkan telah menguasai:
* **Kalkulus Multivariat & Aljabar Linier Lanjut**: Gradien, Matriks Hessian, Dekomposisi Nilai Singular (SVD), Pengali Lagrange (*Lagrangian Duality*), dan Kondisi Karush-Kuhn-Tucker (KKT).
* **Teori Probabilitas & Statistika Inferensial**: *Maximum Likelihood Estimation* (MLE), *Maximum A Posteriori* (MAP), Teorema Bayes, serta distribusi keluarga eksponensial.
* **Rekayasa Perangkat Lunak & Sistem Komputasi**: Pemrograman Python tingkat lanjut (manajemen memori CPython, SIMD via NumPy, struktur data sparse CSR/CSC), arsitektur CPU *cache locality* (L1/L2/L3), dan protokol komunikasi performa tinggi (gRPC).

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Geometri Ruang Loss dan Mekanika Regularisasi L1 vs L2

Dalam kerangka *Empirical Risk Minimization* (ERM), model berusaha meminimalkan fungsi loss empiris $\mathcal{L}_{\text{emp}}(\mathbf{w}) = \frac{1}{N} \sum_{i=1}^N \ell(y_i, f(\mathbf{x}_i; \mathbf{w}))$. Namun, untuk mencegah overfitting pada data berdimensi tinggi, diterapkan *Structural Risk Minimization* (SRM) dengan menambahkan penalti kompleksitas $\Omega(\mathbf{w})$:

$$\min_{\mathbf{w}} \mathcal{J}(\mathbf{w}) = \mathcal{L}_{\text{emp}}(\mathbf{w}) + \lambda \Omega(\mathbf{w})$$

```
          L1 Regularization (|w1| + |w2| <= t)             L2 Regularization (w1^2 + w2^2 <= t)
                        w2                                                w2
                        ^                                                 ^
                        |                                                 |
                     +  |  +                                           . --- .
                  +     |     +                                     /    |    \
               +        |        +                                /      |      \
            +           |           +                           /        |        \
  <---------+-----------+-----------+---------> w1    <--------+---------+---------+--------> w1
            +           |           +                           \        |        /
               +        |        +                                \      |      /
                  +     |     +                                     \    |    /
                     +  |  +                                           ' --- '
                        |                                                 |
                        v                                                 v
         *Peluang titik singgung kontur loss              *Kontur bola halus mendistribusikan penalti;
         jatuh tepat pada sumbu (koordinat 0)*             bobot mendekati nol tetapi jarang tepat nol*
```

* **L2 Regularization (Ridge / Tikhonov)**: $\Omega(\mathbf{w}) = \frac{1}{2} \|\mathbf{w}\|_2^2 = \frac{1}{2} \sum_{j=1}^D w_j^2$.
  Secara analitis pada regresi linier:
  $$\mathbf{w}_{\text{ridge}} = (\mathbf{X}^T\mathbf{X} + \lambda \mathbf{I})^{-1} \mathbf{X}^T\mathbf{y}$$
  Penambahan $\lambda \mathbf{I}$ menjamin matriks dapat dibalik (*invertible*) bahkan ketika $\mathbf{X}^T\mathbf{X}$ bersifat singular atau mengalami multikolinearitas parah. Dari perspektif Bayesian, L2 setara dengan asumsi distribusi prior *Gaussian* pada bobot: $w_j \sim \mathcal{N}(0, \sigma^2)$ di mana $\lambda = \frac{\sigma_{\epsilon}^2}{\sigma^2}$.
* **L1 Regularization (Lasso)**: $\Omega(\mathbf{w}) = \|\mathbf{w}\|_1 = \sum_{j=1}^D |w_j|$.
  Fungsi ini tidak terdiferensiasi pada $w_j = 0$. Solusi analitis didekati menggunakan *subgradient calculus*. Dari perspektif Bayesian, L1 setara dengan asumsi distribusi prior *Laplace* (Double Exponential): $w_j \sim \text{Laplace}(0, b)$. Karena bentuk geometri penalti L1 adalah *polytope* (berlian di 2D, *cross-polytope* di dimensi lebih tinggi), titik singgung kontur fungsi loss elips dengan pembatas L1 kemungkinan besar terjadi pada verteks/sudut pembatas di mana beberapa koordinat bernilai persis nol. Inilah alasan matematis L1 menghasilkan solusi bobot yang jarang (*sparse representation*), bertindak simultan sebagai penyeleksi fitur otomatis.
* **ElasticNet**: Menggabungkan convex combination keduanya:
  $$\Omega(\mathbf{w}) = \alpha \|\mathbf{w}\|_1 + \frac{1 - \alpha}{2} \|\mathbf{w}\|_2^2$$
  Mengatasi limitasi Lasso yang hanya memilih maksimal $N$ fitur ketika $P > N$, atau memilih satu fitur acak dari kelompok fitur yang berkorelasi tinggi (*grouped selection*).

### 3.2 Optimasi Order Kedua: Algoritma Newton-Raphson & L-BFGS

Optimasi order pertama (misal: Vanilla SGD) hanya memanfaatkan vektor gradien $\mathbf{g} = \nabla \mathcal{J}(\mathbf{w})$, bergerak menuruni lereng secara proporsional terhadap *learning rate* $\eta$: $\mathbf{w}_{t+1} = \mathbf{w}_t - \eta \mathbf{g}_t$. Pada lanskap kurvatur yang buruk (misal: jurang sempit berdasar datar), SGD mengalami osilasi lambat (*zig-zagging*).

Optimasi order kedua mengevaluasi kurvatur lokal menggunakan deret Taylor orde kedua:

$$\mathcal{J}(\mathbf{w} + \Delta \mathbf{w}) \approx \mathcal{J}(\mathbf{w}) + \nabla \mathcal{J}(\mathbf{w})^T \Delta \mathbf{w} + \frac{1}{2} \Delta \mathbf{w}^T \mathbf{H} \Delta \mathbf{w}$$

Di mana $\mathbf{H}_{j,k} = \frac{\partial^2 \mathcal{J}}{\partial w_j \partial w_k}$ adalah matriks Hessian ($D \times D$). Mencari nilai minimum terhadap $\Delta \mathbf{w}$ menghasilkan persamaan stasioner:

$$\nabla \mathcal{J}(\mathbf{w}) + \mathbf{H} \Delta \mathbf{w} = 0 \implies \Delta \mathbf{w} = -\mathbf{H}^{-1} \nabla \mathcal{J}(\mathbf{w})$$

Pembaruan Newton-Raphson:
$$\mathbf{w}_{t+1} = \mathbf{w}_t - \mathbf{H}_t^{-1} \mathbf{g}_t$$

Pada kasus Logistic Regression, ini dikenal sebagai **Iteratively Reweighted Least Squares (IRLS)**:
* Gradien: $\mathbf{g} = \mathbf{X}^T (\mathbf{p} - \mathbf{y})$, di mana $p_i = \sigma(\mathbf{w}^T \mathbf{x}_i)$.
* Hessian: $\mathbf{H} = \mathbf{X}^T \mathbf{S} \mathbf{X}$, di mana $\mathbf{S} = \text{diag}(p_i(1 - p_i))$.

**Masalah Skalabilitas Hessian**: Membentuk dan menginversi matriks $\mathbf{H}$ memerlukan alokasi memori $\mathcal{O}(D^2)$ dan kompleksitas komputasi inversi $\mathcal{O}(D^3)$. Pada sistem produksi dengan $D = 10^6$ fitur (misal: sparse n-grams), Newton murni mustahil dilakukan.

**Solusi: L-BFGS (Limited-memory Broyden-Fletcher-Goldfarb-Shanno)**:
L-BFGS mengaproksimasi invers Hessian $\mathbf{H}^{-1}$ secara implisit tanpa pernah menyimpan matriks penuh. Algoritma ini hanya menyimpan $m$ pasang vektor pembaruan historis terakhir:
$$\mathbf{s}_k = \mathbf{w}_{k+1} - \mathbf{w}_k, \quad \mathbf{y}_k = \mathbf{g}_{k+1} - \mathbf{g}_k$$
Menggunakan *two-loop recursion*, arah pencarian $-\mathbf{H}_k^{-1} \mathbf{g}_k$ dihitung hanya dalam memori $\mathcal{O}(mD)$ dan kompleksitas komputasi $\mathcal{O}(mD)$, dengan $m$ umumnya bernilai kecil ($5 \le m \le 20$).

### 3.3 Anatomi Mesin Gradient Boosted Decision Tree (GBDT)

GBDT membangun ansambel model pohon aditif $F_M(\mathbf{x}) = \sum_{m=1}^M f_m(\mathbf{x})$. Pada setiap iterasi $m$, kita meminimalkan aproksimasi Taylor orde kedua dari fungsi objektif terhadap prediksi pohon baru $f_m$:

$$\tilde{\mathcal{L}}^{(m)} \approx \sum_{i=1}^N \left[ \ell(y_i, F_{m-1}(\mathbf{x}_i)) + g_i f_m(\mathbf{x}_i) + \frac{1}{2} h_i f_m^2(\mathbf{x}_i) \right] + \Omega(f_m)$$

Di mana komponen turunan pertama dan keduanya didefinisikan sebagai:
$$g_i = \left. \frac{\partial \ell(y_i, \hat{y})}{\partial \hat{y}} \right|_{\hat{y} = F_{m-1}(\mathbf{x}_i)}, \quad h_i = \left. \frac{\partial^2 \ell(y_i, \hat{y})}{\partial \hat{y}^2} \right|_{\hat{y} = F_{m-1}(\mathbf{x}_i)}$$

Penalti kompleksitas pohon didefinisikan sebagai:
$$\Omega(f_m) = \gamma T + \frac{1}{2} \lambda \sum_{j=1}^T w_j^2$$
dengan $T$ adalah jumlah daun, dan $w_j$ adalah bobot/nilai leaf output ke-$j$.

Jika kita mendefinisikan $I_j = \{i \mid q(\mathbf{x}_i) = j\}$ sebagai himpunan sampel yang dipetakan ke daun $j$, serta mendefinisikan akumulasi gradien dan hessian daun sebagai $G_j = \sum_{i \in I_j} g_i$ dan $H_j = \sum_{i \in I_j} h_i$, maka bobot optimal daun $w_j^*$ dan skor kualitas struktur pohon didapatkan dari turunan langsung:

$$w_j^* = -\frac{G_j}{H_j + \lambda}$$

$$\mathcal{J}^* = -\frac{1}{2} \sum_{j=1}^T \frac{G_j^2}{H_j + \lambda} + \gamma T$$

Perolehan gain untuk membagi daun menjadi anak kiri ($L$) dan anak kanan ($R$) adalah:

$$\text{Gain}_{\text{split}} = \frac{1}{2} \left[ \frac{G_L^2}{H_L + \lambda} + \frac{G_R^2}{H_R + \lambda} - \frac{(G_L + G_R)^2}{H_L + H_R + \lambda} \right] - \gamma$$

```
                           +----------------------+
                           |   Parent Node        |
                           |   G_P = G_L + G_R    |
                           |   H_P = H_L + H_R    |
                           +----------+-----------+
                                      |
                         Evaluasi Split: Gain > 0
                                     / \
                                    /   \
                                   /     \
               +------------------+       +------------------+
               |  Left Node (L)   |       |  Right Node (R)  |
               |  G_L, H_L        |       |  G_R, H_R        |
               +------------------+       +------------------+
```

#### Split Finding: Exact Greedy vs. Histogram-Based Binning
* **Exact Greedy (Standard XGBoost baseline)**: Mengurutkan nilai fitur secara kontinu untuk setiap fitur pada setiap daun. Kompleksitas komputasi: $\mathcal{O}(D \cdot N \log N)$. Menghasilkan *cache-miss* besar saat mengakses memori tak berurutan untuk membaca nilai $g_i$ dan $h_i$.
* **Histogram-based Binning (LightGBM / Modern XGBoost)**: Mengkuantisasi nilai fitur kontinu ke dalam $K$ *discrete bins* (misal: $K=256$, merepresentasikan 1 byte `uint8`).
  1. Data dikonversi ke struktur histogram kontinu: Kompleksitas pembentukan histogram $\mathcal{O}(D \cdot N)$.
  2. Pencarian split dilakukan pada bin histogram: Kompleksitas $\mathcal{O}(D \cdot K)$.
  3. **Histogram Subtraction Trick**: Histogram simpul anak kanan dapat dihitung langsung dengan mengurangkan histogram anak kiri dari histogram induk:
     $$\text{Hist}_R = \text{Hist}_P - \text{Hist}_L$$
     Operasi ini mengeksekusi separuh komputasi split dalam memori cache CPU L1/L2 secara instan.

### 3.4 Kalibrasi Probabilitas Post-Hoc: Teori & Kebutuhan Produksi

Banyak model klasifikasi (SVM, Random Forest, GBDT) tidak meminimalkan *proper scoring rules* secara langsung terhadap probabilitas murni, atau mengalami distorsi karena proses bagging/boosting:
* **SVM**: Output berupa *margin distance* $f(\mathbf{x}) \in (-\infty, +\infty)$, bukan probabilitas.
* **GBDT**: Mengalami *pushing effect* ke arah ekstrem (probabilitas mendekati 0 atau 1) akibat regresi log-loss pada residual yang ter-overfit secara lokal.

Pada sistem produksi seperti *pricing engine* asuransi atau *fraud detection*, interpretasi akurat terhadap nilai ekspektasi kerugian $\mathbb{E}[\text{Loss}] = P(\text{Fraud}) \times \text{Nominal}$ mutlak membutuhkan nilai probabilitas sejati.

```
Miskalibrasi Reliability Curve (Diagram ECE)
1.0 +                                       / Perfect Calibration (x = y)
    |                                    .-'
    |                                 .-'  * Under-confident
    |                             _.-' *
    |                         _.-' *
    |                     _.-' *
    |                 _.-'  * Over-confident
    |             _.-'  *
    |         _.-'  *
    |     _.-'  *
0.0 +----+-----+-----+-----+-----+-----+-----+
   0.0                                    1.0
                 Mean Predicted Value
```

#### Metode Kalibrasi
1. **Platt Scaling**: Memetakan output non-terkalibrasi $f(\mathbf{x})$ ke dalam probabilitas melalui fungsi sigmoid parametrik univariat:
   $$P(y=1 \mid f) = \frac{1}{1 + \exp(A f + B)}$$
   Parameter $A$ dan $B$ diestimasi menggunakan MLE pada validasi silang (*out-of-fold predictions*) untuk mencegah data leakage.
2. **Isotonic Regression**: Pendekatan non-parametrik yang memasang fungsi *piecewise constant non-decreasing* $\hat{y} = m(f)$ dengan meminimalkan kuadrat eror:
   $$\min_m \sum_{i=1}^N (y_i - m(f_i))^2 \quad \text{dengan syarat } m(f_i) \le m(f_j) \text{ jika } f_i \le f_j$$
   Diselesaikan secara analitis oleh **Pair Adjacent Violators Algorithm (PAVA)** dalam kompleksitas $\mathcal{O}(N)$. Kelemahannya: rentan *overfitting* jika data validasi kalibrasi berukuran kecil ($N < 1000$).

---

## 4. Why & What

### Mengapa Model Klasik Tetap Mendominasi Data Tabular di Era Deep Learning?

Di tengah kemajuan pesat Deep Learning (Transformer, MLP-Mixer, TabNet), riset empiris independen skala masif (misal: *Grinsztajn et al., NeurIPS 2022 - "Why do tree-based models still outperform deep learning on tabular data?"*) secara konsisten membuktikan bahwa GBDT (XGBoost, LightGBM, CatBoost) tetap unggul atas Deep Neural Networks (DNN) pada data tabular struktural.

| Dimensi Arsitektural | Classical Supervised Learning (GBDT / Ridge / SVM) | Deep Learning Tabular (TabNet / MLP) |
| :--- | :--- | :--- |
| **Inductive Bias** | Struktur pohon membagi ruang fitur secara *axis-aligned orthogonal hyperplanes*, ideal untuk relasi tabular. | Memproyeksikan manifold halus kontinu, kesulitan menangani batas keputusan tabular yang tajam/berundak. |
| **Invariant terhadap Skala** | Tidak sensitif terhadap transformasi monotonik fitur kontinu (tidak wajib scaling normalisasi). | Sangat sensitif terhadap outlier dan penskalaan fitur; memerlukan normalisasi cermat. |
| **Fitur Irrelevan & Sparsitas**| Algoritma split otomatis mengabaikan fitur dengan *gain zero*; penalti L1 memangkas noise. | Rentan memasukkan bobot non-zero pada noise berdimensi tinggi, memerlukan regularisasi berat. |
| **Budget Komputasi Training** | Pelatihan selesai dalam hitungan detik/menit pada arsitektur multi-core CPU standar. | Memerlukan akselerasi GPU, ribuan epoch, konsumsi energi dan waktu berlipat ganda. |
| **Inference Footprint** | Latensi inferensi single-digit mikrodetik ($\mu s$) via model tree flattening (Treelite/C++). | Latensi inferensi milidetik ($ms$) akibat perkalian matriks densitas tinggi dan overhead runtime framework. |

### Apa yang Ditransformasi pada Level Produksi?
Model Machine Learning di lingkungan produksi bukan sekadar file `.pkl` yang dimuat ke dalam memori. Transformasi dari *prototyping* ke *production-grade ML* melibatkan:
1. Pemisahan deterministik antara graf komputasi preprocessing dan graf inferensi numerik.
2. Pengalihan dari interpretor Python yang terikat GIL (*Global Interpreter Lock*) menuju runtime native kompilasi C++ / ONNX / TensorRT.
3. Arsitektur penyajian nir-salin (*zero-copy memory sharing*) antara pipeline data ingest dan model executor.

---

## 5. How (Workflow Detail)

Arsitektur siklus hidup implementasi machine learning enterprise dirancang sebagai pipeline linier deterministik dengan loop umpan balik telemetri:

```
[ Data Ingestion Engine (Kafka / Parquet Data Lake) ]
                         |
                         v
[ Feature Store (Feast / Hopsworks / Redis Cache) ]
                         |
                         v
[ Offline Training Pipeline & Model Validation ]
  +-- Stratified Time-Series Split Cross-Validation
  +-- Bayesian Hyperparameter Tuning (Optuna)
  +-- Out-of-Fold (OOF) Prediction Generation
  +-- Probability Calibration (Platt / Isotonic)
                         |
                         v
[ Model Compilation & Artifact Optimization ]
  +-- Pruning & Floating Point Quantization (FP32 -> FP16 / INT8)
  +-- ONNX Graph Optimization & Treelite C-Code Compilation
                         |
                         v
[ Model Registry & Automated CI/CD Canary Gate ]
  +-- ECE (Expected Calibration Error) Verification
  +-- Latency Stress Test (p99 SLA Benchmark)
                         |
                         v
[ Production Inference Cluster (Triton / C++ Wrapper Service) ]
       |                                          |
       v (Online Predictions)                     v (Asynchronous Telemetry)
[ Client Applications ]                [ Observability Engine ]
                                         +-- Population Stability Index (PSI)
                                         +-- Kolmogorov-Smirnov (KS) Drift
                                         +-- Automated Retraining Trigger
```

### Langkah Kerja Operasional:
1. **Feature Engineering & Transformation Pipeline**: Membekukan transformer statistik (imputer, encoder) agar parameter estimasi (mean, median, varians) tidak bocor dari masa depan (*data leakage prevention*).
2. **K-Fold Out-of-Fold Calibration**: Melatih model pada $K-1$ fold, menghasilkan prediksi pada fold penahan, dan melatih kalibrator probabilitas khusus pada agregasi seluruh prediksi penahan tersebut.
3. **Graph Compilation**: Mengekspor pohon biner atau bobot linier ke representasi perantara (*Intermediate Representation* / IR) menggunakan Open Neural Network Exchange (ONNX).
4. **C++ Native Serving Execution**: Menginisialisasi `InferenceSession` ONNX Runtime berlatar belakang *execution provider* CPU teroptimasi AVX2/AVX-512.
5. **Statistical Drift Ingestion**: Menerapkan sliding-window buffer untuk menghitung metrik divergensi distribusi fitur produksi terhadap baseline saat pelatihan.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem: Sistem Peradilan vs. GBDT Ensemble

Bayangkan sebuah sistem pengadilan bertingkat:
* **Single Decision Tree**: Seperti seorang hakim tunggal yang mencoba memutuskan vonis berdasarkan serangkaian aturan biner kaku. Hakim ini rentan bias dan mudah terdistraksi oleh bukti-bukti aneh (*overfitting*).
* **Random Forest (Bagging)**: Sebuah panel dewan juri independen dengan 100 orang. Masing-masing melihat bukti secara acak (*bootstrap*). Vonis akhir diambil dari suara terbanyak. Kesalahan individual saling meniadakan secara independen (*reduksi varians*).
* **Gradient Boosted Decision Tree (Boosting)**: Proses revisi bertahap di mana Hakim Pertama memberikan analisis awal yang masih kasar. Hakim Kedua fokus mendalami kesalahan/kelalaian yang dibuat oleh Hakim Pertama (menghitung residual $g_i, h_i$). Hakim Ketiga fokus mendalami sisa kesalahan Hakim Kedua, dan seterusnya. Setiap hakim berikutnya tidak mengulang investigasi dari nol, melainkan mengoreksi galat akumulatif secara presisi (*reduksi bias*).

```
Arsitektur Pipeline Inferensi Produksi Zero-Copy

Incoming Payload (JSON/Protobuf via gRPC)
                 |
                 v
+---------------------------------------------------------+
| Shared Memory Buffer / Struct Mapping                   |
| (Alokasi C-Contiguous Array float32, zero allocation)   |
+---------------------------------------------------------+
                 |
                 | (Pointers passing, no deserialization overhead)
                 v
+---------------------------------------------------------+
| ONNX Runtime Engine (C++ Dynamic Library)               |
|                                                         |
|  Vectorized Tree Traversal (AVX2/AVX-512 SIMD Bins)    |
|  [ Tree 1 ] -> Bitwise Comparators -> Leaf Ptr          |
|  [ Tree 2 ] -> Bitwise Comparators -> Leaf Ptr          |
|  ...                                                    |
|  [ Tree M ] -> Bitwise Comparators -> Leaf Ptr          |
|                                                         |
|  Sum Reduction Node: Logit = Sum(Leaf_values)           |
+---------------------------------------------------------+
                 |
                 v
+---------------------------------------------------------+
| Native Platt Scaler Layer: P = 1 / (1 + exp(A*Logit + B)|
+---------------------------------------------------------+
                 |
                 v
Output Response Struct (Bytes) -> Zero-Copy Socket Output
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Second-Order Newton-Raphson Logistic Regression Scratch

Berikut adalah implementasi matematis murni *Newton-Raphson IRLS* untuk klasifikasi biner dengan regularisasi L2, ditulis menggunakan NumPy berorientasi efisiensi matriks:

```python
"""
Implementasi Standar Industri: Newton-Raphson Binary Logistic Regression
Dilengkapi dengan L2 Regularization dan inversi matriks berbasis Cholesky.
"""

from typing import Tuple
import numpy as np


class NewtonRaphsonLogisticRegression:
    def __init__(self, l2_penalty: float = 1.0, max_iter: int = 20, tol: float = 1e-6):
        self.l2_penalty = float(l2_penalty)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.weights: np.ndarray = np.array([])
        self.bias: float = 0.0

    @staticmethod
    def _sigmoid(z: np.ndarray) -> np.ndarray:
        # Menghindari overflow numerik menggunakan clipping terarah
        z_clipped = np.clip(z, -500.0, 500.0)
        return 1.0 / (1.0 + np.exp(-z_clipped))

    def fit(self, X: np.ndarray, y: np.ndarray) -> "NewtonRaphsonLogisticRegression":
        n_samples, n_features = X.shape
        # Menggabungkan bias ke dalam matriks bobot (design matrix augmentation)
        X_design = np.hstack([np.ones((n_samples, 1), dtype=np.float64), X])
        d_dim = n_features + 1

        # Inisialisasi bobot dengan nol
        w = np.zeros(d_dim, dtype=np.float64)

        # Matriks Regularisasi I* (tidak meregularisasi intersep bias)
        reg_matrix = self.l2_penalty * np.eye(d_dim, dtype=np.float64)
        reg_matrix[0, 0] = 0.0

        for iteration in range(self.max_iter):
            # 1. Forward Pass: Komputasi probabilitas
            linear_output = np.dot(X_design, w)
            p = self._sigmoid(linear_output)

            # 2. Komputasi Gradien dengan Penalti L2: g = X^T (p - y) + lambda * w
            grad = np.dot(X_design.T, (p - y)) + np.dot(reg_matrix, w)

            # 3. Komputasi Hessian: H = X^T S X + lambda * I
            # S_i = p_i * (1 - p_i). Optimasi memori: hindari diagonal matrix utuh N x N
            p_variance = p * (1.0 - p)
            # Menjamin kestabilan numerik kurvatur
            p_variance = np.maximum(p_variance, 1e-12)

            # Vectorized Weighted Outer Product: X^T * S * X
            # Ekivalen dengan np.dot(X_design.T, p_variance[:, None] * X_design)
            hessian = np.dot(X_design.T, p_variance[:, None] * X_design) + reg_matrix

            # 4. Selesaikan Sistem Persamaan Linier H * delta_w = grad
            # Menggunakan Cholesky Decomposition untuk stabilitas dan kecepatan (H pasti Simetris Positif Definit)
            try:
                cholesky_factor = np.linalg.cholesky(hessian)
                # Solve: L * y_solve = grad
                y_solve = np.linalg.solve(cholesky_factor, grad)
                # Solve: L^T * delta_w = y_solve
                delta_w = np.linalg.solve(cholesky_factor.T, y_solve)
            except np.linalg.LinAlgError:
                # Fallback ke pseudo-invers jika Hessian singular/non-positive-definite
                delta_w = np.linalg.pinv(hessian) @ grad

            # 5. Parameter Update
            w_new = w - delta_w

            # 6. Evaluasi Konvergensi menggunakan L2 Norm dari vektor perubahan parameter
            step_norm = np.linalg.norm(delta_w, ord=2)
            w = w_new

            if step_norm < self.tol:
                break

        self.bias = float(w[0])
        self.weights = w[1:].copy()
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        linear_output = np.dot(X, self.weights) + self.bias
        prob_positive = self._sigmoid(linear_output)
        return np.column_stack([1.0 - prob_positive, prob_positive])


# Smoke Test
if __name__ == "__main__":
    np.random.seed(42)
    X_synthetic = np.random.randn(500, 5)
    y_synthetic = (X_synthetic[:, 0] * 1.5 - X_synthetic[:, 1] * 2.0 > 0.5).astype(np.float64)

    model = NewtonRaphsonLogisticRegression(l2_penalty=0.1)
    model.fit(X_synthetic, y_synthetic)
    predictions = model.predict_proba(X_synthetic)
    print(f"Convergence test. Bobot terestimasi: {model.weights.round(3)}, Bias: {model.bias:.3f}")
```

### 7.2 Practical Example: Enterprise-Grade Production Engine

Kode produksi berikut mengimplementasikan:
1. Pelatihan **LightGBM Classifier** pada data tabular tak seimbang.
2. Kalibrasi probabilitas menggunakan **Platt Scaling** pada *Out-of-Fold* (OOF) validation untuk menghindari bias data leakage.
3. Ekspor ke runtime statis **ONNX**.
4. Kelas penyaji inferensi berkecepatan tinggi (**Engine Inferensi**) berbasis C++ ONNX Runtime dengan benchmarking latensi p99.

```python
"""
Arsitektur Pipeline Produksi End-to-End:
LightGBM -> OOF Platt Scaling -> ONNX Compilation -> Native Latency Inference Engine
"""

import time
import os
from typing import Tuple, Generator
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
import lightgbm as lgb
import onnxruntime as ort
import onnxmltools
from onnxmltools.convert.common.data_types import FloatTensorType


class ProductionModelPipeline:
    def __init__(self, n_splits: int = 5):
        self.n_splits = n_splits
        self.base_model: lgb.LGBMClassifier | None = None
        self.calibrator: LogisticRegression | None = None
        self.onnx_model_path: str = "artifacts/model_ensemble.onnx"

    def train_and_calibrate(self, X: np.ndarray, y: np.ndarray) -> None:
        skf = StratifiedKFold(n_splits=self.n_splits, shuffle=True, random_state=42)
        oof_raw_predictions = np.zeros(X.shape[0], dtype=np.float64)

        # Matriks parameter base estimator
        lgb_params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "n_estimators": 100,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1,
        }

        # 1. Out-of-fold Training untuk Mengumpulkan Prediksi Kalibrasi Bersih
        for train_idx, val_idx in skf.split(X, y):
            X_train_fold, y_train_fold = X[train_idx], y[train_idx]
            X_val_fold = X[val_idx]

            fold_model = lgb.LGBMClassifier(**lgb_params)
            fold_model.fit(X_train_fold, y_train_fold)

            # Mengambil raw log-odds (margin output) atau uncalibrated probabilities
            # Menggunakan probabilitas mentah kelas positif
            oof_raw_predictions[val_idx] = fold_model.predict_proba(X_val_fold)[:, 1]

        # 2. Latih Model Final pada Keseluruhan Dataset
        self.base_model = lgb.LGBMClassifier(**lgb_params)
        self.base_model.fit(X, y)

        # 3. Latih Platt Scaler (Logistic Regression Univariat) pada OOF Predictions
        # Logit transformation pada uncalibrated prob: s = ln(p / (1 - p))
        eps = 1e-12
        p_clipped = np.clip(oof_raw_predictions, eps, 1.0 - eps)
        oof_logits = np.log(p_clipped / (1.0 - p_clipped)).reshape(-1, 1)

        self.calibrator = LogisticRegression(C=1.0, solver="lbfgs")
        self.calibrator.fit(oof_logits, y)

        # Validasi Kualitas Kalibrasi
        initial_brier = brier_score_loss(y, oof_raw_predictions)
        calibrated_oof = self.calibrator.predict_proba(oof_logits)[:, 1]
        calibrated_brier = brier_score_loss(y, calibrated_oof)

        print(f"[Model Registry] AUC Baseline: {roc_auc_score(y, oof_raw_predictions):.4f}")
        print(f"[Calibration] Brier Score Mentah: {initial_brier:.5f} -> Terkalibrasi: {calibrated_brier:.5f}")

    def export_to_onnx(self, n_features: int) -> None:
        os.makedirs(os.path.dirname(self.onnx_model_path), exist_ok=True)
        initial_type = [("float_input", FloatTensorType([None, n_features]))]

        # Konversi LightGBM ke ONNX representation
        onnx_model = onnxmltools.convert_lightgbm(
            self.base_model, initial_types=initial_type, target_opset=13
        )

        with open(self.onnx_model_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"[Compilation] Model berhasil diekspor ke format ONNX: {self.onnx_model_path}")


class LowLatencyInferenceEngine:
    """Inference Engine Thread-Safe Menggunakan C++ Engine ONNX Runtime."""

    def __init__(self, onnx_model_path: str, calibrator: LogisticRegression):
        self.calibrator = calibrator
        # Konfigurasi SessionOptions untuk performa p99 terendah
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # Hindari thread contention pada horizontal scaled workers
        opts.inter_op_num_threads = 1
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            onnx_model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        # Ekstraksi parameter skalar Platt Scaling: P = 1 / (1 + exp(A*z + B))
        # Parameter kalibrator sklearn diekstrak agar komputasi kalibrasi bebas objek sklearn
        self.platt_coef = float(self.calibrator.coef_[0, 0])
        self.platt_intercept = float(self.calibrator.intercept_[0])

    def predict_fast(self, sample_features: np.ndarray) -> float:
        """
        Inferensi single-record ultra-low-latency.
        sample_features harus berupa 1D float32 array berukuran (n_features,).
        """
        # Zero-copy reshape untuk binding memory ort
        input_data = np.ascontiguousarray(sample_features.reshape(1, -1), dtype=np.float32)

        # Forward pass melalui engine ONNX (mengambil output label dan probabilities)
        raw_outputs = self.session.run(None, {self.input_name: input_data})

        # Indeks probabilitas model tree LightGBM di ONNX tersimpan di dictionary/map output kedua
        # Array probabilitas berada pada indeks kedua dari output pipeline
        uncalibrated_prob_positive = float(raw_outputs[1][0][1])

        # Aplikasi manual kalkulasi vektorisasi Platt Sigmoid:
        # 1. Transformasi balik ke logit mentah
        eps = 1e-12
        p_safe = max(eps, min(1.0 - eps, uncalibrated_prob_positive))
        logit = np.log(p_safe / (1.0 - p_safe))

        # 2. Kalibrasi affine transformation: z_prime = w * logit + b
        scaled_logit = self.platt_coef * logit + self.platt_intercept

        # 3. Sigmoid final
        calibrated_prob = 1.0 / (1.0 + np.exp(-scaled_logit))
        return calibrated_prob


# Pipeline Execution Benchmark Test
if __name__ == "__main__":
    # Inisialisasi Dataset Skala Enterprise (Tabular Imbalanced Fraud Detection Pattern)
    N_SAMPLES = 20_000
    N_FEATURES = 30
    X_raw, y_raw = make_classification(
        n_samples=N_SAMPLES,
        n_features=N_FEATURES,
        n_informative=20,
        n_redundant=5,
        weights=[0.97, 0.03],  # 3% positive class imbalance
        random_state=42,
    )
    X_raw = X_raw.astype(np.float32)

    # 1. Training, Validation & Calibration
    pipeline = ProductionModelPipeline()
    pipeline.train_and_calibrate(X_raw, y_raw)
    pipeline.export_to_onnx(n_features=N_FEATURES)

    # 2. Benchmark Inferensi C++ ONNX Engine
    engine = LowLatencyInferenceEngine(pipeline.onnx_model_path, pipeline.calibrator)

    # Latency Profiling (Single Record Execution)
    latencies = []
    test_record = X_raw[0]

    # Warm-up run (mengisi instruction cache CPU)
    for _ in range(100):
        _ = engine.predict_fast(test_record)

    # Latency evaluation loop (1000 iterasi profiling)
    for _ in range(1000):
        t0 = time.perf_counter_ns()
        prob = engine.predict_fast(test_record)
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1_000_000)  # Konversi ke milidetik (ms)

    latencies = np.array(latencies)
    print("\n--- Telemetri Latensi Inferensi Single Record ---")
    print(f"Mean Latency : {np.mean(latencies):.4f} ms")
    print(f"Median (p50) : {np.percentile(latencies, 50):.4f} ms")
    print(f"p95 Latency  : {np.percentile(latencies, 95):.4f} ms")
    print(f"p99 Latency  : {np.percentile(latencies, 99):.4f} ms")
    print(f"Target SLA   : < 5.0000 ms -> PASSED STATUS: {np.percentile(latencies, 99) < 5.0}")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Kasus: Real-Time Payment Transaction Fraud Engine
* **Perusahaan**: Tier-1 Payment Gateway Asia Tenggara.
* **Volume Transaksi**: 18.000 Transaksi per Detik (*Transactions Per Second* / TPS) pada jam puncak (*peak hour*).
* **Target Ketat SLA**: Inferensi klasifikasi fraud tuntas dalam waktu $\le 8\text{ ms}$ pada persentil ke-99 ($p99$). Jika melewati batas ini, transaksi dialihkan (*fallback bypass*), yang meningkatkan risiko kerugian penipuan (*financial loss risk*).

```
Arsitektur Sistem Produksi High-Throughput Fraud Detection

                      [ API Ingress (Envoy Gateway) ]
                                     |
                                     | (18,000 TPS, TLS Termination)
                                     v
                      [ Fraud Routing Microservice (Go) ]
                                     |
                    +----------------+----------------+
                    | (Parallel Async Fetch)          |
                    v                                 v
         [ Redis Cluster (v7.0) ]       [ Feature Hydration Struct ]
      (User Velocity, 10-min counters)  (Payload Extraction, Zero Memory Alloc)
                    |                                 |
                    +----------------+----------------+
                                     |
                                     v (gRPC / Unix Domain Sockets)
                  [ Model Inference Worker (C++ / ONNX) ]
                    +-- LightGBM Quantized Graph Engine
                    +-- AVX-512 Matrix Multipliers
                    +-- Pinned Core Thread Affinity
                                     |
                                     +--------------------------------+
                                     |                                |
                        (Response: P(Fraud) < 8ms)            (Async Fire-and-Forget)
                                     |                                v
                           [ Routing Decision ]             [ Kafka Telemetry Bus ]
                                                                      |
                                                                      v
                                                            [ Drift Evaluator Engine ]
                                                            - Compute PSI & KS Per Jam
                                                            - Trigger Auto-Retrain
```

### Masalah Arsitektural Sebelumnya:
Model awal berbasis *scikit-learn Random Forest* disajikan menggunakan framework Python web standard (Flask/Gunicorn).
* Terjadi *memory fragmentation* masif dan lonjakan garbage collector (GC pauses).
* Serialisasi model berbasis `.joblib` berukuran 1.8 GB.
* Latensi inferensi p99 mencapai $45\text{ ms}$, memaksa sistem sering melakukan bypass transaksi.
* Model memprediksi secara ekstrem (*uncalibrated probabilities*), menyulitkan tim risiko menetapkan ambang batas moneter dinamis.

### Solusi Arsitektural yang Diterapkan:
1. **Model Optimization**: Mengganti Random Forest dengan LightGBM menggunakan histogram kuantisasi 8-bit (`max_bins=255`), mengurangi ukuran footprint memori artefak model dari 1.8 GB menjadi **14 MB**.
2. **Probability Alignment**: Mengimplementasikan out-of-fold *Isotonic Regression*, menurunkan *Expected Calibration Error* (ECE) dari $0.182$ menjadi **$0.014$**.
3. **Execution Runtime Engine**:
   * Model dikonversi ke kompilasi library C statis via **Treelite** dan graf statis **ONNX Runtime**.
   * Model dieksekusi dalam worker C++ native terikat CPU core affinity (*CPU pinning* via `pthread_setaffinity_np`) untuk mengeliminasi latensi *context-switching*.
   * Menggunakan *Unix Domain Sockets* (UDS) untuk komunikasi antara microservice Go dan Inference Worker, memangkas overhead TCP/IP stack.

### Hasil Kinerja Produksi:
* Latensi inferensi $p99$ terpangkas dari **$45\text{ ms}$ menjadi $1.85\text{ ms}$**.
* Kapasitas kluster meningkat dari $2.500\text{ TPS}$ menjadi **$24.000\text{ TPS}$ per instance virtual machine**.
* Akurasi estimasi kerugian nominal fraud meningkat $28\%$ berkat probabilitas yang terkalibrasi secara presisi.

---

## 9. Trade-offs

Setiap keputusan arsitektur dalam machine learning tingkat lanjut selalu berhadapan dengan kompromi antar faktor berikut:

```
              Kompleksitas (GBDT/SVM)
                      /\
                     /  \
                    /    \
                   /      \
                  /        \
  Latensi Rendah /__________\ Kapasitas Representasi
(Linear/Logistic)            (Deep Neural Networks)
```

| Dimensi | Regularized Linear Models (Lasso/Ridge) | Support Vector Machines (RBF Kernel) | Gradient Boosted Decision Trees | Deep Tabular Networks (TabNet) |
| :--- | :--- | :--- | :--- | :--- |
| **Throughput & Training Latency** | **Sangat Cepat**: Skala linier $\mathcal{O}(ND)$ via Coordinate Descent / L-BFGS. | **Sangat Lambat**: Membutuhkan $\mathcal{O}(N^2)$ hingga $\mathcal{O}(N^3)$ memori dan waktu komputasi. Tidak scalable untuk $N > 100.000$. | **Optimal**: Skala $\mathcal{O}(K \cdot D \cdot N)$ via Histogram binning paralel. | **Lambat**: Butuh backpropagation multi-epoch, komputasi GPU tinggi. |
| **Inference Latency (Single Record)** | **Sub-mikrodetik ($< 0.1\mu s$)**: Hanya berupa dot-product skalar $\mathbf{w}^T\mathbf{x} + b$. | **Tergantung Support Vectors**: $\mathcal{O}(N_{\text{SV}} \cdot D)$. Jika $N_{\text{SV}}$ besar, latensi inferensi membengkak. | **Sangat Cepat ($< 2 ms$)**: Berbasis traversal array terkompilasi (Treelite/ONNX). | **Sedang ($5 - 25 ms$)**: Terhambat tensor allocation dan GPU-CPU transit overhead. |
| **Interpretability & Auditability** | **Tinggi**: Bobot koefisien linier langsung merepresentasikan log-odds marginal. | **Nol / Kotak Hitam**: Kernel RBF memetakan dimensi tak hingga (*Hilbert Space*). | **Tinggi via SHAP**: Representasi Shapley TreeExplainer deterministik dalam $\mathcal{O}(T \cdot L \cdot D^2)$. | **Rendah**: Memerlukan estimasi aproksimasi lokal (misal: Grad-CAM / KernelSHAP). |
| **Infrastructure & Serving Cost** | **Ultra Rendah**: Berjalan efisien pada CPU mikro instans termurah. | **Tinggi**: Kebutuhan RAM besar untuk menyimpan matriks support vector. | **Rendah - Sedang**: Pemanfaatan CPU multi-core modern yang efisien. | **Sangat Tinggi**: Kebutuhan dedicated GPU clusters untuk melayani model. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Data Leakage pada Preprocessing dan Kalibrasi
* **Gejala**: Performa metrik model saat pengujian (*offline test*) menunjukkan AUC $0.99$ atau Brier Score mendekati $0.001$, namun saat dideploy ke produksi terjadi anjlok performa secara masif (*generalization collapse*).
* **Akar Masalah**: Penskalaan fitur (misal: `StandardScaler`), imputasi nilai kosong, atau fitting kalibrator probabilitas (`CalibratedClassifierCV`) dilakukan pada seluruh dataset sebelum split validasi silang dilakukan.
* **Solusi**: Bungkus seluruh langkah ke dalam `Pipeline` deterministik. Kalibrasi harus dilatih hanya pada *Out-of-Fold* (OOF) validation data atau split dataset terpisah (*hold-out calibration set*).

### 2. Numerical Instability pada Evaluasi Log-Sum-Exp & Odds Conversion
* **Gejala**: Runtime melempar nilai `NaN` atau `Inf` saat mengubah margin/logit output model pohon menjadi probabilitas pada transaksi ekstrem.
* **Akar Masalah**: Komputasi sigmoid naif:
  ```python
  # SALAH: Terjadi overflow jika z < -709 atau z > 709 pada floating-point IEEE 754
  p = 1.0 / (1.0 + np.exp(-z))
  ```
* **Solusi**: Gunakan implementasi sigmoid yang stabil secara numerik dengan clipping batas eksponensial:
  ```python
  # BENAR: Mengisolasi batas domain float64
  z_safe = np.clip(z, -500.0, 500.0)
  p = np.where(z_safe >= 0, 
               1.0 / (1.0 + np.exp(-z_safe)), 
               np.exp(z_safe) / (1.0 + np.exp(z_safe)))
  ```

### 3. Degradasi Performa Model Akibat Covariate Shift (Data Drift)
* **Gejala**: F1-Score atau akurasi model menurun secara bertahap dalam kurun waktu beberapa pekan di produksi tanpa adanya perubahan kode.
* **Akar Masalah**: Distribusi marginal input $P(\mathbf{X})$ bergeser akibat perubahan tren makro atau variasi musiman (*seasonal behavior*), meskipun fungsi pemetaan kondisional $P(y \mid \mathbf{X})$ mungkin tetap statis.
* **Solusi**: Implementasikan engine monitoring Population Stability Index (PSI) terjadwal pada fitur-fitur kritis:
  $$\text{PSI} = \sum_{b=1}^B \left( \% \text{ Actual}_b - \% \text{ Expected}_b \right) \times \ln\left( \frac{\% \text{ Actual}_b}{\% \text{ Expected}_b} \right)$$
  * $\text{PSI} < 0.1$: Stabil, tidak ada pergeseran berarti.
  * $0.1 \le \text{PSI} < 0.25$: Terjadi pergeseran moderat; jadwalkan retraining.
  * $\text{PSI} \ge 0.25$: Drift signifikan; sistem harus memicu retraining otomatis atau memunculkan peringatan sistem.

---

## 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis model klasifikasi/regresi klasik ke sistem produksi kritis:

```
[ ] PRE-TRAINING DATA INTEGRITY
    [ ] Split data temporal: Data masa depan tidak pernah bocor ke data training (Time-Series Split).
    [ ] Zero Target Leakage: Variabel penanda masa depan yang hanya muncul setelah event telah dibersihkan.
    [ ] Identifikasi kolinearitas parah menggunakan Variance Inflation Factor (VIF > 10 dipangkas).

[ ] MODEL TRAINING & REGULARIZATION
    [ ] Hyperparameter regularisasi (L1/L2 alpha, reg_lambda) dioptimasi via Cross-Validation.
    [ ] Base estimator GBDT menggunakan Histogram Binning untuk memastikan efisiensi memori.
    [ ] Imbalance handling dikonfigurasi melalui focal loss, class weights, atau subsampling terarah.

[ ] CALIBRATION & EVALUATION
    [ ] Evaluasi Reliability Curve (Diagram Kalibrasi) pada Hold-Out Data.
    [ ] Expected Calibration Error (ECE) < 0.05 untuk sistem berisiko moneter.
    [ ] Brier Score diverifikasi bersama metrik diskriminasi (ROC-AUC / PR-AUC).

[ ] SERVING & RUNTIME OPTIMIZATION
    [ ] Artefak model dikompilasi ke format komputasi graf statis (ONNX / Treelite).
    [ ] Thread contention diisolasi: Execution Provider threads disetel ke 1 thread per instance worker.
    [ ] Memory pre-allocation: Pipa payload menggunakan buffer memori contiguous statis (C-order).
    [ ] Pengujian batas latensi p99 lulus uji stres di bawah beban 2x kapasitas puncak yang diharapkan.

[ ] TELEMETRY & OBSERVABILITY
    [ ] Drift Calculator asinkron (PSI / Kolmogorov-Smirnov) aktif pada Kafka stream.
    [ ] Peringatan (alerts) disetel pada saluran pemantauan untuk anomali output (persentase prediksi kelas positif).
```

---

## 12. Hands-on Practice

Simpan seluruh file praktikum ini di direktori: `hands-on/m02/`

### File Structure:
```
hands-on/m02/
├── 01_drift_detector.py
├── 02_treelite_compiler.py
└── requirements.txt
```

### Langkah 1: Persiapan Lingkungan (`requirements.txt`)
```text
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.3.0
lightgbm>=4.0.0
onnxruntime>=1.16.0
onnxmltools>=1.12.0
```

Pasang dependensi menggunakan terminal:
```bash
pip install -r requirements.txt
```

### Langkah 2: Skrip Deteksi Drift Berbasis PSI (`01_drift_detector.py`)
Implementasikan skrip pemantauan kestabilan populasi produksi:

```python
# hands-on/m02/01_drift_detector.py
import numpy as np


class ProductionDriftDetector:
    def __init__(self, n_bins: int = 10, epsilon: float = 1e-4):
        self.n_bins = n_bins
        self.epsilon = epsilon
        self.bin_edges: dict[str, np.ndarray] = {}
        self.baseline_percents: dict[str, np.ndarray] = {}

    def fit_baseline(self, feature_name: str, values: np.ndarray) -> None:
        """Menghitung bin edges referensi menggunakan kuantil data training."""
        quantiles = np.linspace(0, 100, self.n_bins + 1)
        edges = np.percentile(values, quantiles)
        # Menjamin batas bin strictly increasing
        edges[0] -= 1e-5
        edges[-1] += 1e-5
        self.bin_edges[feature_name] = edges

        # Hitung distribusi referensi
        counts, _ = np.histogram(values, bins=edges)
        percents = counts / len(values)
        # Terapkan smoothing epsilon untuk mencegah pembagian dengan nol
        percents = np.where(percents == 0, self.epsilon, percents)
        self.baseline_percents[feature_name] = percents

    def calculate_psi(self, feature_name: str, target_values: np.ndarray) -> float:
        """Menghitung Population Stability Index pada data inference aktual."""
        if feature_name not in self.bin_edges:
            raise ValueError(f"Feature {feature_name} belum di-fit!")

        edges = self.bin_edges[feature_name]
        baseline_pct = self.baseline_percents[feature_name]

        # Histogramming data produksi dengan edge referensi
        counts, _ = np.histogram(target_values, bins=edges)
        target_pct = counts / len(target_values)
        target_pct = np.where(target_pct == 0, self.epsilon, target_pct)

        # Hitung formulasi analitis PSI
        psi_value = np.sum((target_pct - baseline_pct) * np.log(target_pct / baseline_pct))
        return float(psi_value)


if __name__ == "__main__":
    np.random.seed(42)
    # 1. Generate Data Training Acuan (Distribusi Normal)
    baseline_data = np.random.normal(loc=50.0, scale=10.0, size=10_000)

    detector = ProductionDriftDetector(n_bins=10)
    detector.fit_baseline("transaction_amount", baseline_data)

    # 2. Data Produksi Normal (Tanpa Drift)
    production_normal = np.random.normal(loc=50.2, scale=9.8, size=2_000)
    psi_normal = detector.calculate_psi("transaction_amount", production_normal)
    print(f"PSI Data Normal : {psi_normal:.4f} (Status: {'OK' if psi_normal < 0.1 else 'ALERT'})")

    # 3. Data Produksi Terkena Covariate Drift (Distribusi Bergeser ke Kanan)
    production_drifted = np.random.normal(loc=56.0, scale=12.0, size=2_000)
    psi_drifted = detector.calculate_psi("transaction_amount", production_drifted)
    print(f"PSI Data Drift  : {psi_drifted:.4f} (Status: {'DRIFT DETECTED' if psi_drifted >= 0.25 else 'WARNING'})")
```

Jalankan pengujian:
```bash
python 01_drift_detector.py
```

---

## 13. Exercise

### Level Easy
Tuliskan implementasi fungsi reguler regresi linier analitis (Ridge Closed-Form Solution) $\mathbf{w} = (\mathbf{X}^T\mathbf{X} + \lambda \mathbf{I})^{-1}\mathbf{X}^T\mathbf{y}$ menggunakan dekomposisi Singular Value Decomposition (SVD) untuk mencegah instabilitas komputasi jika matriks $\mathbf{X}^T\mathbf{X}$ ill-conditioned. Hindari pemanggilan `np.linalg.inv`.

### Level Medium
Bangun fungsi partisi histogram binning (`build_histogram_bins`) dari nol menggunakan NumPy:
* Menerima array 1D fitur kontinu dan jumlah bins $K=32$.
* Menghasilkan bin index integer (`uint8`) untuk setiap nilai fitur tanpa komputasi looping lambat.
* Tunjukkan pembuktian bahwa histogram child kanan dapat dihitung secara instan menggunakan pengurangan vektor: $\mathbf{H}_R = \mathbf{H}_P - \mathbf{H}_L$.

### Level Hard
Buat implementasi kustom algoritma **Pair Adjacent Violators Algorithm (PAVA)** dari nol dalam Python tanpa bergantung pada modul `sklearn.isotonic`:
* Fungsi harus menerima output model mentah $f_i$ dan target biner aktual $y_i$.
* Harus mengurutkan sampel berdasarkan urutan non-decreasing dari $f_i$.
* Lakukan iterasi penggabungan bobot (*pooling adjacent violators*) hingga relasi monotonik non-decreasing terpenuhi di seluruh blok partisi: $\hat{y}_1 \le \hat{y}_2 \le \dots \le \hat{y}_B$.
* Optimalkan operasi *pooling* menggunakan struktur data linked list atau array stack agar mencapai kompleksitas amortisasi $\mathcal{O}(N)$.

---

## 14. Challenge (Studi Kasus Kompleks Tanpa Solusi Instan)

### Real-Time High-Frequency Credit Risk Decisioning Under Extreme Adversarial Drift

#### Konteks Arsitektur:
Sebuah bank digital meluncurkan produk pinjaman kilat (PayLater) instan dengan batas waktu keputusan underwriting maksimal **$15\text{ milidetik}$** dari saat request diterima hingga response dikirim.

Di lapangan, model menghadapi anomali sindikat fraud berskala besar yang secara sistematis memanipulasi fitur pendapatan dan data profiling perangkat (*adversarial data perturbation*). Perilaku ini menyebabkan drift non-stasioner yang dinamis setiap beberapa jam sekali.

#### Persyaratan Rekayasa yang Harus Anda Rancang:
1. **Model Architecture Constraint**:
   * Rancang arsitektur model hybrid (GBDT + Generalized Linear Model Sparse) yang beroperasi pada pipeline memori terpadu.
   * Model wajib menjamin monotonic constraint pada fitur-fitur tertentu (misal: makin tinggi rasio utang/penghasilan, probabilitas default tidak boleh turun).
2. **Serving Optimization Constraint**:
   * Graf model harus mampu dieksekusi secara konkuren pada sistem multi-core tanpa mengalami *lock contention*.
   * P99 latensi keseluruhan (termasuk validasi payload, transformasi fitur, inferensi, dan kalibrasi probabilitas) harus berada di bawah **$12\text{ ms}$** pada beban $8.000\text{ RPS}$.
3. **Continuous Online Drift Mitigation**:
   * Desain mekanisme validasi prediksi berbasis **Conformal Prediction** untuk menghasilkan *prediction sets* dengan tingkat keyakinan statistis $1 - \alpha = 0.95$.
   * Jika ukuran prediction set membesar (misal: model ragu dan mengembalikan label $\{0, 1\}$ sekaligus karena drift parah), sistem harus secara otomatis mengalihkan evaluasi aplikasi ke rule-based fallback tanpa henti layanan (*zero-downtime switchover*).
4. **Deliverable Blueprint**:
   * Gambarkan diagram arsitektur sistem level produksi lengkap yang memetakan aliran buffer memori, interface I/O, integrasi storage fitur, engine inferensi, dan loop telemetri retraining adaptif.
   * Tuliskan dokumen mitigasi trade-off arsitektural yang menjelaskan mengapa Anda memilih pendekatan runtime tertentu untuk menangani *adversarial distribution shifts*.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic (Dasar Konseptual)
1. **Mengapa penalti L1 (Lasso) menghasilkan representasi bobot yang bersifat sparse (banyak nol), sedangkan L2 (Ridge) tidak?**
   * *Jawaban Singkat*: Geometri pembatas L1 adalah belah ketupat/polytope dengan sudut-sudut tajam yang bersinggungan langsung dengan sumbu koordinat parameter, sehingga titik stasioner fungsi loss sering kali memotong tepat pada $w_j = 0$. Pembatas L2 berupa lingkaran/bola halus tanpa sudut tajam, sehingga hanya