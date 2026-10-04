# Bab 04: Tree-Based Methods & Ensemble Architectures
## Module 01: Foundations of Decision Trees & Bagging Ensembles (CART & Random Forest)

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis dan Memformulasikan Mekanisme Splitting CART:** Menghitung secara matematis *Gini Impurity*, *Shannon Entropy*, dan *Variance Reduction* untuk menentukan kandidat pemisahan fitur (*split candidate*) optimal pada data tabular berdimensi tinggi.
*   **Membuktikan Konvergensi Dekorelasi Ensemble:** Menguraikan secara analitis dekomposisi *bias-variance* pada algoritma *Bootstrap Aggregating* (Bagging) dan membuktikan bagaimana parameter korelasi antar-pohon ($\rho$) mengontrol batas bawah varians ensemble.
*   **Mengimplementasikan Arsitektur Random Forest dari Prinsip Dasar (From Scratch):** Membangun sistem *Decision Tree* dan *Random Forest* yang *production-ready*, *thread-safe*, *type-hinted*, dan modular menggunakan Python dan NumPy murni, dengan dukungan *cost-complexity pruning* dan estimasi *Out-Of-Bag* (OOB).
*   **Mendiagnosis Kegagalan Evaluasi Fitur:** Mengidentifikasi dan memitigasi bias pada *Mean Decrease Impurity* (MDI) dibandingkan dengan *Permutation Feature Importance* (PFI) pada fitur dengan kardinalitas tinggi.
*   **Menerapkan Strategi Optimasi Inferensi Enterprise:** Menyiapkan pohon keputusan untuk produksi berlatensi rendah menggunakan teknik kompilasi graf dan serialisasi formal (e.g., Treelite / ONNX runtime primitives).

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Mental Model: Partisi Ruang Fitur Ortogonal
Pohon keputusan (*Decision Tree*) berbasis CART (*Classification and Regression Trees*) bekerja dengan mempartisi ruang fitur $\mathbb{R}^p$ secara rekursif menjadi sekumpulan hiper-persegi panjang (*axis-aligned hyper-rectangles*) non-tumpang tindih. Setiap partisi menghasilkan prediksi konstan (rata-rata target untuk regresi, atau modus probabilitas kelas untuk klasifikasi).

```
X2 ^
   |
   |         R1          |        R2
   |                     |
s2 +---------------------+------------------
   |                     |
   |         R3          |        R4
   |                     |
   +---------------------+------------------> X1
                         s1
```

Secara formal, model representasi pohon keputusan adalah:
$$f(x) = \sum_{m=1}^{M} c_m \cdot \mathbb{I}(x \in R_m)$$
di mana $M$ adalah jumlah total daun (*leaf nodes*), $R_m$ merepresentasikan wilayah ke-$m$, dan $c_m$ adalah konstanta respons yang dipelajari pada wilayah tersebut.

#### Teorema Juri Condorcet & Prinsip Ensemble
Algoritma berbasis ensemble bersandar pada Teorema Juri Condorcet (*Condorcet's Jury Theorem*). Jika sebuah komite terdiri dari $B$ pemilih independen, dan masing-masing memiliki probabilitas $p > 0.5$ untuk membuat keputusan yang benar, maka probabilitas bahwa suara mayoritas benar mendekati $1$ seiring $B \to \infty$. 

Dalam *machine learning*, satu pohon keputusan tunggal umumnya bersifat **low bias** tetapi **high variance** (sangat sensitif terhadap perturbasi data latih). Bagging mengatasi masalah ini dengan melatih banyak pemelajar basis (*base learners*) secara paralel pada sampel *bootstrap* independen dan merata-ratakan prediksinya.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Pada data tabular enterprise (seperti deteksi penipuan transaksi perbankan, penilaian risiko kredit, dan prediksi *churn* e-commerce), arsitektur berbasis *tree* secara konsisten mengungguli arsitektur *Deep Neural Networks* (DNN) dalam rasio performa-komputasi (Grinsztajn et al., 2022). Faktor-faktor pendorong adopsi di industri mencakup:
1.  **Invariansi terhadap Transformasi Monotonik:** Fitur tidak memerlukan penskalaan (*scaling*), normalisasi z-score, atau transformasi Box-Cox. Pohon mengevaluasi urutan komparasi ($x_j \le s$), bukan magnitudo absolut.
2.  **Ketahanan terhadap Missing Values dan Outliers:** Pemisahan nilai ekstrem diisolasi ke dalam daun tertentu tanpa mendistorsi batas keputusan global.
3.  **Auditabilitas & Regulasi (Explainability):** Sektor perbankan dan kesehatan mewajibkan batas keputusan model dapat diverifikasi oleh regulator. Jalur inferensi pohon menyediakan representasi berbasis aturan (*if-then-else*) eksplisit.
4.  **Efisiensi Sumber Daya Latih dan Inferensi:** Biaya komputasi inferensi pohon skala produksi berada pada kompleksitas $\mathcal{O}(depth)$, jauh lebih murah daripada operasi perkalian matriks densitas tinggi pada DNN.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur end-to-end dari konstruksi dataset hingga inferensi paralel pada arsitektur Random Forest:

```
[Training Data: N samples, P features]
                 |
      +----------+----------+--------------------+
      | (Bootstrap Sample 1)|                    | (Bootstrap Sample B)
      v                     v                    v
+---------------+     +---------------+    +---------------+
| Bagged Data 1 |     | Bagged Data 2 |    | Bagged Data B |
+---------------+     +---------------+    +---------------+
      |                     |                    |
      | (Subspace Sampling) | (Subspace Sampling)| (Subspace Sampling)
      |  m = sqrt(P)        |  m = sqrt(P)       |  m = sqrt(P)
      v                     v                    v
+---------------+     +---------------+    +---------------+
| Tree Model 1  |     | Tree Model 2  |    | Tree Model B  |
|  (Max Depth)  |     |  (Max Depth)  |    |  (Max Depth)  |
+---------------+     +---------------+    +---------------+
      \                     |                   /
       \                    |                  /
        +-------------------+-----------------+
                            |
           [Ensemble Inference Aggregation]
                            |
           +----------------+----------------+
           |                                 |
           v                                 v
   [Soft/Hard Voting]             [Variance Reduction]
   (Classification)                  (Regression)
           |                                 |
           v                                 v
    p(y|x) = 1/B * Sum(p_b)          y_hat = 1/B * Sum(y_b)
```

#### Alur Eksekusi Internal Node Splitting

```
                  Input: Node Data D (Size N_node)
                                 |
                 Apakah stopping criteria terpenuhi?
                 (depth >= max_depth OR N_node < min_samples_split)
                                 |
                        +--------+--------+
                     Ya |                 | Tidak
                        v                 v
                 Buat Leaf Node   Pilih subset acak m fitur
                 (pred = mode/avg)        |
                                  Evaluasi semua titik split
                                  pada seluruh fitur m terpilih
                                          |
                                  Hitung Impurity Delta (Gain)
                                          |
                                  Pilih (Feature*, Split*) terbaik
                                          |
                                  Partisi Data D -> D_L, D_R
                                          |
                                  Rekursi: Split(D_L), Split(D_R)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Kriteria Splitting Matematis

##### 1. Klasifikasi: Gini Impurity vs. Shannon Entropy
Misalkan $p_{mk}$ adalah proporsi observasi kelas $k \in \{1, \dots, K\}$ pada node $m$:
$$p_{mk} = \frac{1}{N_m} \sum_{x_i \in R_m} \mathbb{I}(y_i = k)$$

*   **Gini Impurity:**
    $$I_G(m) = 1 - \sum_{k=1}^{K} p_{mk}^2$$
*   **Cross-Entropy / deviance:**
    $$H(m) = - \sum_{k=1}^{K} p_{mk} \log_2(p_{mk}) \quad (\text{dengan } 0 \log 0 \equiv 0)$$

Pemisahan optimal dicapai dengan memaksimalkan penurunan ketidakmurnian (*Impurity Gain*):
$$\Delta I = I(m) - \left( \frac{N_L}{N_m} I(m_L) + \frac{N_R}{N_m} I(m_R) \right)$$

##### 2. Regresi: Variance Reduction
Untuk target kontinu, fungsi kriteria adalah Mean Squared Error (MSE) / Varians lokal:
$$\text{MSE}(m) = \frac{1}{N_m} \sum_{i \in R_m} (y_i - \bar{y}_m)^2, \quad \bar{y}_m = \frac{1}{N_m} \sum_{i \in R_m} y_i$$
Kriteria split meminimalkan varians tertimbang dari dua sub-wilayah:
$$\min_{j, s} \left[ \sum_{i \in R_L(j, s)} (y_i - \bar{y}_L)^2 + \sum_{i \in R_R(j, s)} (y_i - \bar{y}_R)^2 \right]$$

#### 5.2 Bias-Variance Decomposition pada Bagging

Misalkan terdapat $B$ pemelajar basis yang identik secara distribusi (*identically distributed*), masing-masing dengan varians $\sigma^2$, tetapi tidak sepenuhnya independen. Korelasi pearson antar-pasang pohon dinotasikan sebagai $\rho = \text{Corr}(T_i, T_j)$. 

Varians dari rata-rata ensemble $T_{\text{ens}}(x) = \frac{1}{B} \sum_{b=1}^{B} T_b(x)$ adalah:
$$\text{Var}(T_{\text{ens}}) = \rho \sigma^2 + \frac{1 - \rho}{B} \sigma^2$$

Analisis kondisi batas:
*   Jika $B \to \infty$, maka suku $\frac{1 - \rho}{B} \sigma^2 \to 0$.
*   Batas bawah varians ensemble adalah:
    $$\lim_{B \to \infty} \text{Var}(T_{\text{ens}}) = \rho \sigma^2$$

*Key Insight:* Bagging murni hanya mereduksi suku kedua ($\frac{1-\rho}{B}\sigma^2$). **Random Forest secara fundamental mereduksi $\rho$** dengan melakukan **Random Subspace Sampling** (memilih acak $m \approx \sqrt{p}$ fitur di setiap kandidat split), sehingga pohon-pohon menjadi ter-dekorelasi (*decorrelated*), yang secara drastis menekan nilai batas bawah $\rho \sigma^2$ tanpa meningkatkan bias secara signifikan.

#### 5.3 Properti Out-Of-Bag (OOB) Error

Dalam proses bootstrap terhadap dataset berukuran $N$ melalui sampling dengan pengembalian (*sampling with replacement*), probabilitas sebuah data point *tidak* terpilih dalam satu undian adalah $1 - \frac{1}{N}$.

Untuk ukuran sampel $N$ yang besar, probabilitas suatu observasi diabaikan dari seluruh sampel bootstrap (berukuran $N$) adalah:
$$\lim_{N \to \infty} \left(1 - \frac{1}{N}\right)^N = e^{-1} \approx 0.367879 \dots \approx 36.8\%$$

Konsekuensi Enterprise: Sekitar $36.8\%$ data tidak terlihat oleh pohon tertentu pada setiap epoch replikasi bootstrap. Data ini bertindak sebagai set validasi independen yang melekat (*built-in cross-validation*), memungkinkan penghitungan *OOB Error* tanpa memerlukan partisi *holdout* atau *K-Fold Cross Validation* terpisah.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi CART Classifier dan Random Forest Classifier yang modular, teroptimasi secara matematis, mengimplementasikan *OOB Evaluation*, serta mendukung paralelisasi CPU via standard multi-processing.

```python
# src/decision_tree_engine.py

from __future__ import annotations
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TreeEnsembleLogger")


@dataclass(frozen=True)
class Node:
    """Representasi immutable simpul pada Decision Tree."""
    gini: float
    num_samples: int
    num_samples_per_class: List[int]
    predicted_class: int
    feature_index: int = -1
    threshold: float = 0.0
    left: Optional[Node] = None
    right: Optional[Node] = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


class ProductionCARTClassifier:
    """Implementasi CART Classification Tree berstandar industri."""

    def __init__(
        self,
        max_depth: int = 10,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        max_features: Optional[str] = "sqrt"
    ) -> None:
        if max_depth < 1:
            raise ValueError("max_depth harus bernilai >= 1.")
        if min_samples_split < 2:
            raise ValueError("min_samples_split harus >= 2.")
        if min_samples_leaf < 1:
            raise ValueError("min_samples_leaf harus >= 1.")

        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.root: Optional[Node] = None
        self.num_classes_: int = 0
        self.num_features_: int = 0

    def _compute_gini(self, y: np.ndarray) -> float:
        """Menghitung Gini Impurity pada subset label."""
        m = len(y)
        if m == 0:
            return 0.0
        counts = np.bincount(y, minlength=self.num_classes_)
        probabilities = counts / m
        return float(1.0 - np.sum(probabilities ** 2))

    def _determine_feature_subspace(self) -> int:
        """Menentukan subset fitur untuk partisi."""
        if self.max_features == "sqrt":
            return max(1, int(np.sqrt(self.num_features_)))
        elif self.max_features == "log2":
            return max(1, int(np.log2(self.num_features_)))
        elif self.max_features is None:
            return self.num_features_
        else:
            raise ValueError(f"Metode max_features '{self.max_features}' tidak valid.")

    def _best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float, float]:
        """Menemukan split optimal dengan vektorisasi numpy."""
        m, n = X.shape
        if m < self.min_samples_split:
            return -1, 0.0, 0.0

        current_gini = self._compute_gini(y)
        best_gain = -1.0
        best_idx, best_thr = -1, 0.0

        n_subspace = self._determine_feature_subspace()
        feature_indices = np.random.choice(n, size=n_subspace, replace=False)

        for idx in feature_indices:
            thresholds = np.unique(X[:, idx])
            if len(thresholds) <= 1:
                continue

            # Hitung titik tengah kandidat split
            candidates = (thresholds[:-1] + thresholds[1:]) / 2.0

            for thr in candidates:
                left_mask = X[:, idx] <= thr
                right_mask = ~left_mask

                n_l, n_r = np.sum(left_mask), np.sum(right_mask)
                if n_l < self.min_samples_leaf or n_r < self.min_samples_leaf:
                    continue

                gini_left = self._compute_gini(y[left_mask])
                gini_right = self._compute_gini(y[right_mask])
                
                # Gain = I(parent) - [p_L * I(left) + p_R * I(right)]
                gain = current_gini - ((n_l / m) * gini_left + (n_r / m) * gini_right)

                if gain > best_gain:
                    best_gain = gain
                    best_idx = idx
                    best_thr = float(thr)

        return best_idx, best_thr, best_gain

    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int = 0) -> Node:
        """Membangun pohon secara rekursif."""
        num_samples_per_class = [int(np.sum(y == c)) for c in range(self.num_classes_)]
        predicted_class = int(np.argmax(num_samples_per_class))
        gini = self._compute_gini(y)

        node = Node(
            gini=gini,
            num_samples=len(y),
            num_samples_per_class=num_samples_per_class,
            predicted_class=predicted_class
        )

        if depth < self.max_depth and gini > 0.0:
            idx, thr, gain = self._best_split(X, y)
            if idx != -1 and gain > 1e-7:
                left_mask = X[:, idx] <= thr
                right_mask = ~left_mask

                left_child = self._build_tree(X[left_mask], y[left_mask], depth + 1)
                right_child = self._build_tree(X[right_mask], y[right_mask], depth + 1)

                return Node(
                    gini=gini,
                    num_samples=len(y),
                    num_samples_per_class=num_samples_per_class,
                    predicted_class=predicted_class,
                    feature_index=idx,
                    threshold=thr,
                    left=left_child,
                    right=right_child
                )

        return node

    def fit(self, X: np.ndarray, y: np.ndarray) -> ProductionCARTClassifier:
        """Melatih pohon klasifikasi dengan validasi tipe data input keras."""
        if not isinstance(X, np.ndarray) or not isinstance(y, np.ndarray):
            raise TypeError("X dan y harus bertipe numpy.ndarray.")
        if X.ndim != 2:
            raise ValueError(f"X harus berdimensi 2 (shape: [N, P]), ditemukan {X.ndim}.")
        if y.ndim != 1 or len(X) != len(y):
            raise ValueError("Kesesuaian dimensi baris X dan y dilanggar.")

        self.num_classes_ = len(np.unique(y))
        self.num_features_ = X.shape[1]
        self.root = self._build_tree(X, y.astype(np.int64))
        return self

    def _predict_row(self, node: Node, x: np.ndarray) -> int:
        """Traverse pohon untuk sampel data tunggal."""
        if node.is_leaf:
            return node.predicted_class
        if x[node.feature_index] <= node.threshold:
            return self._predict_row(node.left, x)
        return self._predict_row(node.right, x)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Inferensi vectorized terhadap batch fitur."""
        if self.root is None:
            raise RuntimeError("Model belum dilatih. Panggil 'fit' terlebih dahulu.")
        return np.array([self._predict_row(self.root, row) for row in X], dtype=np.int64)


def _train_single_tree_worker(
    args: Tuple[np.ndarray, np.ndarray, Dict[str, Any], int]
) -> Tuple[ProductionCARTClassifier, np.ndarray]:
    """Helper fungsi global untuk multiprocessing pooling."""
    X, y, params, seed = args
    np.random.seed(seed)
    n_samples = len(X)
    
    # Bootstrap sampling (dengan pengembalian)
    boot_indices = np.random.choice(n_samples, size=n_samples, replace=True)
    oob_indices = np.setdiff1d(np.arange(n_samples), np.unique(boot_indices))

    tree = ProductionCARTClassifier(**params)
    tree.fit(X[boot_indices], y[boot_indices])
    return tree, oob_indices


class ProductionRandomForestClassifier:
    """Ensemble Random Forest dengan komputasi paralel dan OOB score."""

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int = 10,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        max_features: str = "sqrt",
        n_jobs: int = 2
    ) -> None:
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.n_jobs = n_jobs
        self.trees: List[ProductionCARTClassifier] = []
        self.oob_score_: float = 0.0

    def fit(self, X: np.ndarray, y: np.ndarray) -> ProductionRandomForestClassifier:
        n_samples, _ = X.shape
        num_classes = len(np.unique(y))
        
        tree_params = {
            "max_depth": self.max_depth,
            "min_samples_split": self.min_samples_split,
            "min_samples_leaf": self.min_samples_leaf,
            "max_features": self.max_features
        }

        seeds = np.random.randint(0, 1_000_000, size=self.n_estimators)
        tasks = [(X, y, tree_params, seeds[i]) for i in range(self.n_estimators)]

        logger.info(f"Memulai pelatihan {self.n_estimators} pohon dengan {self.n_jobs} worker threads/processes...")
        with ProcessPoolExecutor(max_workers=self.n_jobs) as executor:
            results = list(executor.map(_train_single_tree_worker, tasks))

        self.trees = [res[0] for res in results]
        
        # Evaluasi OOB Matrix: [N, Num_Classes]
        oob_predictions = np.zeros((n_samples, num_classes))
        oob_counts = np.zeros(n_samples)

        for tree, oob_idx in results:
            if len(oob_idx) > 0:
                preds = tree.predict(X[oob_idx])
                for idx, pred in zip(oob_idx, preds):
                    oob_predictions[idx, pred] += 1
                    oob_counts[idx] += 1

        # Validasi sampel yang dievaluasi oleh OOB minimal 1 kali
        valid_oob_mask = oob_counts > 0
        if np.any(valid_oob_mask):
            final_oob_preds = np.argmax(oob_predictions[valid_oob_mask], axis=1)
            correct = np.sum(final_oob_preds == y[valid_oob_mask])
            self.oob_score_ = float(correct / np.sum(valid_oob_mask))
            logger.info(f"OOB Accuracy: {self.oob_score_ * 100:.2f}%")
        else:
            logger.warning("Jumlah estimator tidak mencukupi untuk mengumpulkan metrik OOB.")

        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Inferensi voting mayoritas dari seluruh ensemble."""
        if not self.trees:
            raise RuntimeError("Random Forest belum terpasang (fit).")
        
        # Matriks Voting: [N, B]
        tree_preds = np.array([tree.predict(X) for tree in self.trees])
        
        # Majority voting sepanjang aksis pohon
        num_samples = X.shape[0]
        final_predictions = np.empty(num_samples, dtype=np.int64)
        
        for i in range(num_samples):
            counts = np.bincount(tree_preds[:, i])
            final_predictions[i] = np.argmax(counts)
            
        return final_predictions
```

---

### 7. Edge Cases & Failure Modes (Pencegahan & Mitigasi)

| Edge Case / Failure Mode | Mekanisme Kerusakan | Strategi Mitigasi Arsitektural |
| :--- | :--- | :--- |
| **High Cardinality Features** (e.g., UUID, ZIP Code) | Pohon cenderung memilih fitur berkardinalitas tinggi karena varian kombinasinya memberi reduksi entropi semu (*false information gain*). | Konversi fitur via Target Encoding dengan Bayesian smoothing, atau gunakan *Frequency Encoding* sebelum ingestion ke pohon. |
| **Identical Feature Vectors, Divergent Labels** | Duplikasi fitur dengan label berlawanan (noise input) menyebabkan kedalaman bertambah tanpa batas atau gain mendekati 0. | Terapkan validasi `min_samples_split` absolut dan pasang hard-stop `early_stopping` berbasis delta gain minimal $\Delta I < \epsilon$. |
| **Extreme Class Imbalance** (e.g., Fraud 0.01%) | Kriteria Gini mendominasi kelas mayoritas; pohon menghasilkan leaf konstan untuk meminimalkan error rate global. | Konfigurasi *Balanced Random Forest* (down-sampling kelas mayoritas di tiap bootstrap) atau gunakan modifikasi penimbang kelas pada kalkulasi Gini. |
| **Linear Separability with Slanted Boundaries** | Pohon memotong ruang tegak lurus sumbu (*axis-aligned*), memicu efek "tangga" (*staircasing effect*) yang membutuhkan banyak parameter daun. | Pra-proses data menggunakan PCA atau Random Linear Projections (Oblique Decision Trees). |
| **Memory Spike during Deep Unpruned Tree Recursion** | Deep recursion pada data dengan $N > 10^7$ memicu stack overflow dan konsumsi RAM tak terbatas. | Batasi `max_depth` $\le 32$, gunakan skema alokasi node berbasis pointer berurutan (*contiguous array flattening*). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap arsitektur partisi fitur memiliki matriks kompromi yang harus dievaluasi oleh Principal Engineer:

```
[Batas Interpretasi & Latensi Sangat Rendah] 
       Single Decision Tree (CART)
                   |
[Kompromi Seimbang: No-tuning, Rendah Varians, Paralel CPU Tinggi]
       Random Forest (Bagging + Subspace)
                   |
[Akurasi Tertinggi pada Tabular, Rentan Overfitting, Serial Dependencies]
       Gradient Boosted Trees (XGBoost / LightGBM / CatBoost)
                   |
[Komputasi GPU Intensif, Bagus untuk Integrasi Unstructured Multi-modal]
       TabNet / Deep Tabular Models
```

#### Komparasi Arsitektural

| Dimensi Arsitektural | CART Single Tree | Random Forest | Gradient Boosted Trees | Linear/Logistic Baseline |
| :--- | :--- | :--- | :--- | :--- |
| **Bias / Variance Profile** | Low Bias, Extremely High Variance | Low Bias, Low Variance | Adaptif (Pohon dangkal mengoreksi residual) | High Bias, Low Variance |
| **Inference Latency** | $\mathcal{O}(\text{depth})$ (<10 mikrodetik) | $\mathcal{O}(B \cdot \text{depth})$ (1-10 milidetik) | $\mathcal{O}(B \cdot \text{depth})$ (Bisa di-prune) | $\mathcal{O}(P)$ (Sub-mikrodetik) |
| **Skalabilitas Paralel** | Rendah (Hanya paralel internal node) | Ekstrem (Setiap pohon fully independent) | Terbatas (Pohon $t$ bergantung residu $t-1$) | Sangat Tinggi (SGD Paralel) |
| **Hiperparameter Tuning** | Sensitif terhadap regularisasi | Sangat robust; performa tinggi secara *out-of-the-box* | Butuh tuning detail (*learning rate*, *subsample*) | Butuh tuning regularisasi ($L_1/L_2$) |
| **Kebutuhan Hardware** | Minimal CPU | Skala horizontal multi-core CPU | Multi-core CPU / GPU acceleration | Minimal CPU |

---

### 9. Best Practices & Standard Industri

1.  **Estimasi Dimensi Subspace:**
    *   Untuk klasifikasi dengan dimensi $P$: Tetapkan parameter $m = \lfloor\sqrt{P}\rfloor$.
    *   Untuk regresi dengan dimensi $P$: Tetapkan parameter $m = \lfloor P / 3 \rfloor$.
2.  **Validasi Feature Importance (MDI vs. PFI):**
    *   Hindari mengandalkan *Mean Decrease Impurity* (MDI) pada sistem pelaporan kepatuhan regulasi karena MDI bias terhadap fitur kontinu numerik dan fitur berkardinalitas tinggi.
    *   Gunakan **Permutation Feature Importance (PFI)**: Acak (*shuffle*) nilai pada fitur $j$ pada set evaluasi terpisah dan ukur penurunan metrik performa model ($AUC/F1$). Jika penurunan drastis, fitur tersebut krusial.
3.  **Cost-Complexity Pruning ($c_{\alpha}$ Regularization):**
    Optimasi fungsi objektif CART pasca-latih:
    $$R_{\alpha}(T) = R(T) + \alpha |T|$$
    di mana $R(T)$ adalah total error/impurity daun, dan $|T|$ adalah jumlah daun. Nilai $\alpha$ optimal ditemukan via cross-validation untuk memangkas *subtree* yang rentan overfitting.
4.  **Optimalisasi Inferensi Menuju SLA Mikrodetik:**
    Konversi representasi *if-else pointer-chasing* di memori menjadi *branchless assembly arrays* atau ekspor model ke format biner runtime terkompilasi seperti **Treelite** atau **ONNX**. Hal ini memitigasi *CPU instruction cache miss*.

---

### 10. Hands-on Lab Exercise: Credit Risk Default Engine

#### Skenario Real-World:
Sistem core-banking membutuhkan mesin scoring risiko kredit otomatis untuk memprediksi nasabah yang berpotensi gagal bayar (*default*), dengan proteksi terhadap *feature noise* dan varians prediksi.

#### Task 1: Generate Synthetic Enterprise Tabular Dataset
```python
# lab_simulation.py

import numpy as np
import time

def generate_credit_data(n_samples: int = 5000, seed: int = 42):
    np.random.seed(seed)
    
    # Fitur: Umur, Rasio Hutang, Penghasilan Bulanan, Skor Kredit, Jumlah Kartu Kredit
    age = np.random.uniform(21, 65, size=n_samples)
    debt_ratio = np.random.uniform(0.05, 0.85, size=n_samples)
    monthly_income = np.random.lognormal(mean=8.5, sigma=0.6, size=n_samples)
    credit_score = np.random.normal(loc=650, scale=80, size=n_samples)
    credit_cards = np.random.poisson(lam=3, size=n_samples)
    
    # Menambahkan fitur kategorik berkardinalitas tinggi (Synthetic Noise/Branch)
    branch_id = np.random.randint(1000, 1500, size=n_samples)

    # Konstruksi batas keputusan non-linear untuk label Default (1) vs Good (0)
    logit = (
        - 0.05 * (credit_score - 600) 
        + 4.5 * debt_ratio 
        - 0.0003 * monthly_income 
        + 0.02 * (age - 40)
        + np.random.normal(0, 0.5, size=n_samples)
    )
    probabilities = 1 / (1 + np.exp(-logit))
    labels = (probabilities > 0.5).astype(np.int64)

    features = np.column_stack([age, debt_ratio, monthly_income, credit_score, credit_cards, branch_id])
    return features, labels

X_data, y_data = generate_credit_data()
split_idx = int(0.8 * len(X_data))

X_train, y_train = X_data[:split_idx], y_data[:split_idx]
X_test, y_test = X_data[split_idx:], y_data[split_idx:]

print(f"Data Profiling -> Train Size: {X_train.shape}, Test Size: {X_test.shape}")
print(f"Class Balance (Default Rate): {np.mean(y_train) * 100:.2f}%")
```

#### Task 2: Eksekusi Single Tree vs. Random Forest
```python
# Menggunakan engine yang diimplementasikan pada Bab 6
from decision_tree_engine import ProductionCARTClassifier, ProductionRandomForestClassifier

# 1. Evaluasi Single Decision Tree (CART)
cart = ProductionCARTClassifier(max_depth=15, min_samples_split=2)
t0 = time.perf_counter()
cart.fit(X_train, y_train)
cart_time = time.perf_counter() - t0
cart_preds = cart.predict(X_test)
cart_acc = np.mean(cart_preds == y_test)

# 2. Evaluasi Random Forest
rf = ProductionRandomForestClassifier(
    n_estimators=30,
    max_depth=10,
    min_samples_split=5,
    max_features="sqrt",
    n_jobs=4
)
t0 = time.perf_counter()
rf.fit(X_train, y_train)
rf_time = time.perf_counter() - t0
rf_preds = rf.predict(X_test)
rf_acc = np.mean(rf_preds == y_test)

print("-" * 50)
print(f"Single Tree (Depth=15) Accuracy: {cart_acc * 100:.2f}% | Latency: {cart_time:.4f}s")
print(f"Random Forest (B=30)  Accuracy: {rf_acc * 100:.2f}% | Latency: {rf_time:.4f}s")
print(f"Random Forest OOB Estimation Score: {rf.oob_score_ * 100:.2f}%")
print("-" * 50)
```

#### Task 3: Verifikasi Permutation Feature Importance (PFI) Engine
```python
def compute_permutation_importance(model, X_val: np.ndarray, y_val: np.ndarray) -> np.ndarray:
    """Implementasi Permutation Feature Importance standar produksi."""
    baseline_acc = np.mean(model.predict(X_val) == y_val)
    n_features = X_val.shape[1]
    importances = np.zeros(n_features)

    for col in range(n_features):
        X_permuted = X_val.copy()
        # Kocok observasi secara acak pada fitur tertentu
        np.random.shuffle(X_permuted[:, col])
        permuted_acc = np.mean(model.predict(X_permuted) == y_val)
        # Turunnya performa menandakan pentingnya fitur
        importances[col] = baseline_acc - permuted_acc

    return importances

feature_names = ["Age", "DebtRatio", "MonthlyIncome", "CreditScore", "CreditCards", "BranchID(Noise)"]
importances = compute_permutation_importance(rf, X_test, y_test)

print("\n--- Permutation Feature Importance ---")
for name, imp in zip(feature_names, importances):
    print(f"Fitur: {name:20s} | Penurunan Akurasi: {imp * 100:+.2f}%")
```

#### Output Analisis yang Diharapkan:
1.  **Akurasi Generalisasi:** *Random Forest* secara konsisten mengungguli *Single Decision Tree* minimal 3–7% pada set pengujian karena reduksi varians.
2.  **Korelasi OOB:** Nilai *OOB Accuracy* berkorelasi erat dengan akurasi pengujian sesungguhnya (*True Test Accuracy*), memvalidasi efektivitas OOB sebagai estimasi generalisasi internal yang andal.
3.  **Kekebalan Noise Feature:** Fitur ber-kardinalitas tinggi seperti `BranchID(Noise)` akan mendapatkan skor kepentingan permutasian (*permutation importance*) mendekati $\le 0.00\%$, membuktikan bahwa ensemble menolak fitur artifisial meskipun pohon basis individu mungkin membaginya (*split*) secara lokal.