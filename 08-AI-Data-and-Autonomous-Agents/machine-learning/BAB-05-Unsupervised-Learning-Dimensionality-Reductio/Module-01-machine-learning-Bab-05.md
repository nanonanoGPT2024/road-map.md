# Bab 05: Unsupervised Learning & Dimensionality Reduction
## Module 01: Foundations of Clustering (K-Means/K-Means++) & Linear Dimensionality Reduction (PCA & Truncated SVD)

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis dan Memformulasikan** problem reduksi dimensi linear secara matematis menggunakan dekomposisi matriks (*Singular Value Decomposition* / SVD) dan maksimalisasi varians orthogonal (*Principal Component Analysis* / PCA).
2. **Merancang dan Mengimplementasikan** algoritma klasterisasi *Lloyd's K-Means* yang dioptimasi dengan inisialisasi probabilistik *K-Means++* serta varian streaming (*Mini-Batch K-Means*) untuk dataset skala besar.
3. **Mengevaluasi Kualitas Klaster dan Proyeksi** secara kuantitatif menggunakan metrik *Explained Variance Ratio*, *Silhouette Analysis*, *Davies-Bouldin Index*, dan kalkulasi *Inertia* (Elbow Method).
4. **Mendeteksi dan Memitigasi** anomali numerik akibat fenomena *Curse of Dimensionality*, matriks kovarians singular, serta degradasi partisi (*empty cluster phenomenon*).
5. **Membangun Pipeline Produksi End-to-End** berbasis Python dengan type-hinting ketat, validasi skema data, penanganan konkurensi/batching, dan arsitektur modular yang siap diintegrasikan ke dalam ekosistem MLOps.

---

### 2. Concept Overview

*Unsupervised Learning* beroperasi pada domain data tanpa label supervisi $\mathcal{D} = \{\mathbf{x}_i\}_{i=1}^N$, di mana $\mathbf{x}_i \in \mathbb{R}^D$. Tujuan utamanya adalah mengekstraksi struktur laten (*latent structure*), memampatkan representasi fitur, atau mengelompokkan manifold data ke dalam partisi yang koheren.

```
       Ruang Asli (High-Dimensional Space)
       +------------------------------------+
       |  x_1   x_2   . . .   x_D           |
       |  [ . ]  [ . ]       [ . ]          |
       +-----------------+------------------+
                         |
                         v
     [ Reduksi Dimensi: PCA via Truncated SVD ]
        Mencari subruang k-dimensi (k << D)
        yang meminimalkan reconstruction error:
        min || X - X_k ||_F
                         |
                         v
       Subruang Terproyeksi (Latent Feature Space)
       +------------------------------------+
       |  z_1   z_2   . . .   z_k           |
       |  [ . ]  [ . ]       [ . ]          |
       +-----------------+------------------+
                         |
                         v
     [ Klasterisasi: Lloyd's K-Means++ ]
        Mempartisi manifold ke dalam K sel Voronoi
        dengan meminimalkan within-cluster sum of squares:
        argmin_S \sum \sum || z - \mu_i ||^2
                         |
                         v
       Partisi Klaster Diskrit (Discrete Clusters)
       +------------------------------------+
       | Cluster 0 | Cluster 1 | Cluster 2  |
       +------------------------------------+
```

#### Mental Model
1. **Subspace Projection (PCA):** Bayangkan sebuah awan titik (*point cloud*) 3D berbentuk piringan elips yang miring. Proyeksi terbaik bukan sekadar membuang salah satu sumbu $(x, y, \text{atau } z)$, melainkan memutar sistem koordinat sedemikian rupa sehingga sumbu pertama ($PC_1$) sejajar dengan bentangan varians terpanjang dari elips tersebut, dan sumbu kedua ($PC_2$) tegak lurus (*orthogonal*) terhadap sumbu pertama pada bentangan terlebar berikutnya. Sumbu ketiga, yang memiliki varians mendekati nol (ketebalan piringan), dapat dieliminasi dengan kehilangan informasi minimal.
2. **Voronoi Tessellation (K-Means):** Mengelompokkan data ke dalam $K$ centroid ekuivalen dengan membagi ruang vektor menjadi $K$ sel Voronoi poligonal. Setiap titik data di dalam ruang secara deterministik menjadi anggota centroid terdekat berdasarkan metrik jarak Euclidean.

---

### 3. Why It Matters

Di lingkungan enterprise, implementasi *unsupervised learning* memecahkan sejumlah kendala operasional:

1. **Mitigasi *Curse of Dimensionality*:** Dalam data berdimensi tinggi (misal: representasi teks dense *embeddings* berdimensi 1536), metrik jarak Euclidean cenderung mengalami fenomena *distance concentration*, di mana rasio selisih jarak antara titik terdekat dan terjauh mendekati nol:
   $$\lim_{D \to \infty} \frac{\text{dist}_{\max} - \text{dist}_{\min}}{\text{dist}_{\min}} \to 0$$
   Reduksi dimensi merestorasi diskriminasi jarak spasial untuk algoritma berbasis jarak.
2. **Optimasi Latensi & Storage Mesin Pencari Vektor (Vector Search/IVF Indexing):** Sistem retrieval modern (seperti FAISS, Milvus, Qdrant) memanfaatkan *Inverted File with Product Quantization* (IVF-PQ). IVF menggunakan K-Means untuk mempartisi jutaan embedding ke dalam list Voronoi guna mempercepat *Approximate Nearest Neighbor* (ANN) search dari kompleksitas $\mathcal{O}(N)$ menjadi $\mathcal{O}(K + \frac{N}{K})$.
3. **Deteksi Anomali Infrastruktur Tanpa Label:** Pemantauan metrik server atau transaksi finansial berskala jutaan per detik jarang memiliki label "fraud" atau "failure" secara real-time. Klasterisasi memetakan pola operasi normal (*inliers*) ke dalam klaster padat, menandai observasi yang berada di luar batas margin rekonstruksi PCA (*Reconstruction Error*) atau berjarak jauh dari centroid K-Means sebagai anomali.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur pemrosesan data end-to-end dari data mentah hingga penyimpanan model dan inferensi:

```
[ Raw Ingestion Matrix (N x D) ]
              |
              v
+-----------------------------+
|    Feature Preprocessing    |
| - Missing Value Imputation  |
| - Outlier Clipping          |
| - Z-Score Standardization   | -> Mean: \mu, Std: \sigma
+-----------------------------+
              |
              v
[ Centered Matrix X (N x D) ]
              |
              v
+-----------------------------+
|    Linear Reducer (SVD)     |
| - Covariance: X^T * X       |
| - Truncated SVD: U * S * V^T| -> Eigenvectors Matrix V (D x k)
| - Transform: Z = X * V_k    | -> Singular Values \Sigma
+-----------------------------+
              |
              v
[ Reduced Feature Matrix Z (N x k) ]
              |
              +--------------------------------+
              |                                |
              v                                v
+-----------------------------+  +-----------------------------+
|  K-Means Engine (Lloyd)     |  | Validation & Health Engine  |
| - K-Means++ Seeding         |  | - Explained Variance Ratio  |
| - Voronoi Iteration (EM)    |  | - Reconstruction Loss       |
| - Centroid Convergence Check|  | - Silhouette / Davies-Bouldin|
+-----------------------------+  +-----------------------------+
              |                                |
              v                                v
    [ Centroids Matrix (K x k) ]      [ Metrics Evaluation Report ]
              |
              v
+--------------------------------------------------------------+
|                    Production Serving Tier                   |
| - Transform incoming vectors: z_new = (x_new - \mu) * V_k    |
| - Quantize to Nearest Cluster: c* = argmin || z_new - \mu_c || |
| - Measure Reconstruction Anomaly: || x_new - (z_new * V_k^T + \mu) || |
+--------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Principal Component Analysis (PCA) & Singular Value Decomposition (SVD)

Diberikan matriks data terpusat (*mean-centered*) $\mathbf{X} \in \mathbb{R}^{N \times D}$, di mana $\mathbb{E}[\mathbf{X}] = \mathbf{0}$. Matriks kovarians sampel didefinisikan sebagai:

$$\mathbf{S} = \frac{1}{N-1} \mathbf{X}^T \mathbf{X} \in \mathbb{R}^{D \times D}$$

Tujuan PCA adalah mencari vektor proyeksi linear $\mathbf{w} \in \mathbb{R}^D$ dengan $\|\mathbf{w}\|_2 = 1$ yang memaksimalkan varians proyeksi $\mathbf{z} = \mathbf{X}\mathbf{w}$:

$$\max_{\mathbf{w}} \frac{1}{N-1} (\mathbf{X}\mathbf{w})^T (\mathbf{X}\mathbf{w}) = \max_{\mathbf{w}} \mathbf{w}^T \mathbf{S} \mathbf{w} \quad \text{s.t.} \quad \mathbf{w}^T\mathbf{w} = 1$$

Formulasi Lagrangian:
$$\mathcal{L}(\mathbf{w}, \lambda) = \mathbf{w}^T \mathbf{S} \mathbf{w} - \lambda (\mathbf{w}^T \mathbf{w} - 1)$$
Turunan parsial terhadap $\mathbf{w}$ menghasilkan persamaan nilai eigen (*eigenvalue problem*):
$$\frac{\partial \mathcal{L}}{\partial \mathbf{w}} = 2\mathbf{S}\mathbf{w} - 2\lambda\mathbf{w} = 0 \implies \mathbf{S}\mathbf{w} = \lambda\mathbf{w}$$

Menghitung $\mathbf{S}$ secara langsung membutuhkan memori $\mathcal{O}(D^2)$ dan rentan terhadap instabilitas numerik apabila $D \gg N$. Oleh karena itu, komputasi produksi menggunakan *Singular Value Decomposition* (SVD) langsung pada matriks $\mathbf{X}$:

$$\mathbf{X} = \mathbf{U} \mathbf{\Sigma} \mathbf{V}^T$$

Di mana:
*   $\mathbf{U} \in \mathbb{R}^{N \times N}$ adalah matriks ortogonal vektor singular kiri (*left-singular vectors*).
*   $\mathbf{\Sigma} \in \mathbb{R}^{N \times D}$ adalah matriks diagonal berisi nilai singular $\sigma_1 \ge \sigma_2 \ge \dots \ge \sigma_{\min(N,D)} \ge 0$.
*   $\mathbf{V} \in \mathbb{R}^{D \times D}$ adalah matriks ortogonal vektor singular kanan (*right-singular vectors*, setara dengan *eigenvectors* dari $\mathbf{X}^T\mathbf{X}$).

Hubungan nilai singular $\sigma_j$ dengan nilai eigen $\lambda_j$ dari $\mathbf{S}$:
$$\mathbf{X}^T \mathbf{X} = (\mathbf{V} \mathbf{\Sigma}^T \mathbf{U}^T)(\mathbf{U} \mathbf{\Sigma} \mathbf{V}^T) = \mathbf{V} \mathbf{\Sigma}^2 \mathbf{V}^T \implies \lambda_j = \frac{\sigma_j^2}{N-1}$$

*Explained Variance Ratio* untuk $k$ komponen utama:
$$\text{EVR}_k = \frac{\sum_{j=1}^k \sigma_j^2}{\sum_{j=1}^D \sigma_j^2}$$

#### 5.2 K-Means & Algoritma Lloyd

K-Means mempartisi $N$ observasi ke dalam $K$ himpunan $\mathcal{S} = \{S_1, S_2, \dots, S_K\}$ dengan meminimalkan *Within-Cluster Sum of Squares* (WCSS) atau *Inertia* ($J$):

$$J = \sum_{k=1}^K \sum_{\mathbf{x} \in S_k} \|\mathbf{x} - \boldsymbol{\mu}_k\|_2^2$$

Di mana $\boldsymbol{\mu}_k = \frac{1}{|S_k|} \sum_{\mathbf{x} \in S_k} \mathbf{x}$.

Algoritma Lloyd menyelesaikannya melalui skema *Expectation-Maximization* (EM):
1. **Assignment Step (E-step):**
   $$S_k^{(t)} = \left\{ \mathbf{x}_i : \|\mathbf{x}_i - \boldsymbol{\mu}_k^{(t)}\|^2 \le \|\mathbf{x}_i - \boldsymbol{\mu}_j^{(t)}\|^2, \, \forall j, \, 1 \le j \le K \right\}$$
2. **Update Step (M-step):**
   $$\boldsymbol{\mu}_k^{(t+1)} = \frac{1}{|S_k^{(t)}|} \sum_{\mathbf{x} \in S_k^{(t)}} \mathbf{x}$$

#### 5.3 Inisialisasi Probabilistik K-Means++
Inisialisasi acak seragam sering terjebak pada minimum lokal sub-optimal dengan batas konvergensi $\mathcal{O}(2^K)$. K-Means++ memperbaiki ini dengan menyebarkan centroid awal secara proporsional terhadap kuadrat jarak:

1. Pilih centroid pertama $\boldsymbol{\mu}_1$ secara seragam dari dataset $\{\mathbf{x}_1, \dots, \mathbf{x}_N\}$.
2. Untuk setiap observasi $\mathbf{x}_i$, hitung jarak kuadrat minimum ke centroid terdekat yang sudah dipilih:
   $$D(\mathbf{x}_i)^2 = \min_{j \in \{1,\dots,m\}} \|\mathbf{x}_i - \boldsymbol{\mu}_j\|_2^2$$
3. Pilih centroid berikutnya $\boldsymbol{\mu}_{m+1} = \mathbf{x}'$ dari distribusi probabilitas diskrit:
   $$P(\mathbf{x}' = \mathbf{x}_i) = \frac{D(\mathbf{x}_i)^2}{\sum_{l=1}^N D(\mathbf{x}_l)^2}$$
4. Ulangi langkah 2 dan 3 hingga didapatkan $K$ centroid. Inisialisasi ini menjamin batas ekspektasi error $\mathbb{E}[J] \le 8(\ln K + 2)J_{\text{optimal}}$.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi level produksi menggunakan Python 3.11+, NumPy, SciPy, dan Pydantic. Arsitektur memisahkan *data contract*, *state container*, *dimensionality reducer*, dan *clustering engine* lengkap dengan mekanisme error handling.

```python
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field, field_validator
from scipy.spatial.distance import cdist

# Konfigurasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("UnsupervisedPipeline")


class PipelineConfig(BaseModel):
    """Konfigurasi tervalidasi untuk Pipeline Unsupervised."""
    n_components: int = Field(gt=0, description="Jumlah target dimensi PCA")
    n_clusters: int = Field(gt=1, description="Jumlah cluster K-Means")
    max_iter: int = Field(default=300, gt=0, description="Maksimum iterasi K-Means")
    tol: float = Field(default=1e-4, gt=0.0, description="Toleransi konvergensi centroid")
    batch_size: int = Field(default=1024, gt=0, description="Ukuran batch untuk streaming update")
    random_state: int = Field(default=42, description="Seed generator pseudo-acak")

    @field_validator("n_clusters")
    @classmethod
    def validate_clusters_vs_components(cls, v: int, info) -> int:
        return v


@dataclass(frozen=True)
class PCAModelState:
    """Immutability state untuk komponen PCA terlatih."""
    mean: np.ndarray
    components: np.ndarray
    explained_variance: np.ndarray
    explained_variance_ratio: np.ndarray
    singular_values: np.ndarray


@dataclass(frozen=True)
class KMeansModelState:
    """Immutability state untuk komponen K-Means terlatih."""
    centroids: np.ndarray
    inertia: float
    n_iter: int


class ProductionPCA:
    """
    Principal Component Analysis via SVD (Singular Value Decomposition).
    Mengakomodasi mean centering, kalkulasi EVR, dan transformasi data numerik stabil.
    """

    def __init__(self, n_components: int) -> None:
        self.n_components = n_components
        self._state: Optional[PCAModelState] = None

    @property
    def state(self) -> PCAModelState:
        if self._state is None:
            raise RuntimeError("Model PCA belum di-fit. Jalankan 'fit()' terlebih dahulu.")
        return self._state

    def fit(self, X: np.ndarray) -> ProductionPCA:
        if X.ndim != 2:
            raise ValueError(f"Input matriks harus berdimensi 2 (N, D), didapat shape: {X.shape}")
        
        n_samples, n_features = X.shape
        if self.n_components > min(n_samples, n_features):
            raise ValueError(
                f"n_components ({self.n_components}) tidak boleh lebih besar dari "
                f"min(n_samples, n_features) = {min(n_samples, n_features)}"
            )

        logger.info("Memulai ekstraksi SVD untuk dimensi: %s -> %s", n_features, self.n_components)

        # 1. Mean Centering
        mean = np.mean(X, axis=0)
        X_centered = X - mean

        # 2. Perhitungan SVD: X = U * S * Vt (Lapack gesdd driver)
        try:
            _, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        except np.linalg.LinAlgError as exc:
            logger.error("Dekomposisi SVD gagal mengalami divergensi: %s", str(exc))
            raise RuntimeError("SVD Divergence failure.") from exc

        # Ekstraksi right-singular vectors (principal axes)
        components = Vt[: self.n_components]
        singular_values = S[: self.n_components]

        # 3. Kalkulasi varians
        explained_variance = (singular_values ** 2) / (n_samples - 1)
        total_variance = np.sum((S ** 2) / (n_samples - 1))
        
        if total_variance == 0.0:
            logger.warning("Total varians data bernilai nol.")
            explained_variance_ratio = np.zeros(self.n_components)
        else:
            explained_variance_ratio = explained_variance / total_variance

        self._state = PCAModelState(
            mean=mean,
            components=components,
            explained_variance=explained_variance,
            explained_variance_ratio=explained_variance_ratio,
            singular_values=singular_values,
        )

        logger.info(
            "PCA berhasil di-fit. Total Explained Variance: %.4f%%",
            float(np.sum(explained_variance_ratio) * 100),
        )
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        state = self.state
        if X.shape[1] != state.mean.shape[0]:
            raise ValueError(f"Dimensi fitur tidak konsisten: {X.shape[1]} != {state.mean.shape[0]}")
        return np.dot(X - state.mean, state.components.T)

    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        state = self.state
        if Z.shape[1] != self.n_components:
            raise ValueError(f"Dimensi komponen tidak konsisten: {Z.shape[1]} != {self.n_components}")
        return np.dot(Z, state.components) + state.mean


class ProductionKMeans:
    """
    Optimized Lloyd's K-Means clustering engine dengan implementasi K-Means++ Seeding
    dan mitigasi Empty Cluster.
    """

    def __init__(
        self,
        n_clusters: int,
        max_iter: int = 300,
        tol: float = 1e-4,
        random_state: int = 42,
    ) -> None:
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.tol = tol
        self.rng = np.random.default_rng(random_state)
        self._state: Optional[KMeansModelState] = None

    @property
    def state(self) -> KMeansModelState:
        if self._state is None:
            raise RuntimeError("Model K-Means belum di-fit. Jalankan 'fit()' terlebih dahulu.")
        return self._state

    def _init_kmeans_plus_plus(self, X: np.ndarray) -> np.ndarray:
        """Inisialisasi centroid menggunakan algoritma probabilistik K-Means++."""
        n_samples, n_features = X.shape
        centroids = np.empty((self.n_clusters, n_features), dtype=X.dtype)

        # 1. Ambil centroid pertama secara seragam
        initial_idx = self.rng.integers(0, n_samples)
        centroids[0] = X[initial_idx]

        # 2. Distance matrix cache: Jarak kuadrat terdekat ke setiap centroid yang ada
        closest_dist_sq = cdist(X, centroids[0:1], metric="sqeuclidean").flatten()

        for c_idx in range(1, self.n_clusters):
            # Normalisasi menjadi probabilitas kumulatif
            sum_dist = np.sum(closest_dist_sq)
            if sum_dist == 0.0:
                # Fallback: Bila semua data identik, ambil indeks acak tersisa
                remaining_indices = np.setdiff1d(np.arange(n_samples), np.arange(c_idx))
                chosen_idx = self.rng.choice(remaining_indices)
            else:
                probs = closest_dist_sq / sum_dist
                chosen_idx = self.rng.choice(n_samples, p=probs)

            centroids[c_idx] = X[chosen_idx]

            # Update jarak terdekat menggunakan centroid yang baru terpilih
            new_dist_sq = cdist(X, centroids[c_idx : c_idx + 1], metric="sqeuclidean").flatten()
            closest_dist_sq = np.minimum(closest_dist_sq, new_dist_sq)

        return centroids

    def fit(self, X: np.ndarray) -> ProductionKMeans:
        if X.ndim != 2:
            raise ValueError(f"Input harus matriks 2D, didapat dimensi: {X.shape}")
        n_samples, n_features = X.shape

        if n_samples < self.n_clusters:
            raise ValueError(f"Jumlah sampel ({n_samples}) < n_clusters ({self.n_clusters})")

        # Inisialisasi K-Means++
        centroids = self._init_kmeans_plus_plus(X)
        logger.info("Inisialisasi K-Means++ selesai. Memulai optimasi EM.")

        iteration = 0
        prev_inertia = np.inf

        for iteration in range(1, self.max_iter + 1):
            # --- Assignment Step (E-step) ---
            # Hitung matriks jarak kuadrat: (n_samples, n_clusters)
            dist_sq = cdist(X, centroids, metric="sqeuclidean")
            labels = np.argmin(dist_sq, axis=1)
            current_inertia = float(np.sum(np.min(dist_sq, axis=1)))

            # --- Update Step (M-step) ---
            new_centroids = np.empty_like(centroids)
            for k in range(self.n_clusters):
                cluster_mask = (labels == k)
                if not np.any(cluster_mask):
                    # Mitigasi Empty Cluster: Relokasi centroid ke observasi dengan error tertinggi
                    logger.warning("Empty cluster terdeteksi pada indeks %d di iterasi %d. Merelokasi.", k, iteration)
                    furthest_idx = np.argmax(np.min(dist_sq, axis=1))
                    new_centroids[k] = X[furthest_idx]
                else:
                    new_centroids[k] = np.mean(X[cluster_mask], axis=0)

            # Cek konvergensi via pergeseran centroid
            centroid_shift = np.linalg.norm(new_centroids - centroids)
            centroids = new_centroids

            if centroid_shift < self.tol or abs(prev_inertia - current_inertia) < self.tol:
                logger.info("Konvergensi tercapai pada iterasi ke-%d (shift: %.6f).", iteration, centroid_shift)
                break

            prev_inertia = current_inertia

        self._state = KMeansModelState(
            centroids=centroids,
            inertia=current_inertia,
            n_iter=iteration,
        )
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        state = self.state
        dist_sq = cdist(X, state.centroids, metric="sqeuclidean")
        return np.argmin(dist_sq, axis=1)


class UnsupervisedPipeline:
    """Orkestrator integrasi skalar PCA dan pengelompokan K-Means."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.pca = ProductionPCA(n_components=config.n_components)
        self.kmeans = ProductionKMeans(
            n_clusters=config.n_clusters,
            max_iter=config.max_iter,
            tol=config.tol,
            random_state=config.random_state,
        )

    def execute_fit_transform(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Menjalankan reduksi dimensi dilanjutkan klasterisasi pada latent space."""
        # 1. Fit & Transform PCA
        Z = self.pca.fit(X).transform(X)

        # 2. Fit & Assign Cluster Labels
        labels = self.kmeans.fit(Z).predict(Z)
        
        return Z, labels

    def evaluate_silhouette(self, Z: np.ndarray, labels: np.ndarray) -> float:
        """Kalkulasi manual Silhouette Coefficient tanpa external dependency."""
        n_samples = Z.shape[0]
        unique_labels = np.unique(labels)
        
        if len(unique_labels) <= 1 or len(unique_labels) >= n_samples:
            return 0.0

        dist_matrix = cdist(Z, Z, metric="euclidean")
        silhouette_vals = np.zeros(n_samples)

        for i in range(n_samples):
            curr_label = labels[i]
            # Intra-cluster distance (a)
            same_cluster_mask = (labels == curr_label)
            if np.sum(same_cluster_mask) > 1:
                a_i = np.sum(dist_matrix[i, same_cluster_mask]) / (np.sum(same_cluster_mask) - 1)
            else:
                a_i = 0.0

            # Inter-cluster distance minimum (b)
            b_i = np.inf
            for other_label in unique_labels:
                if other_label == curr_label:
                    continue
                other_cluster_mask = (labels == other_label)
                dist_to_other = np.mean(dist_matrix[i, other_cluster_mask])
                if dist_to_other < b_i:
                    b_i = dist_to_other

            # Score kalkulasi
            max_ab = max(a_i, b_i)
            silhouette_vals[i] = (b_i - a_i) / max_ab if max_ab > 0 else 0.0

        return float(np.mean(silhouette_vals))


if __name__ == "__main__":
    # Verifikasi eksekusi pipeline
    config = PipelineConfig(n_components=3, n_clusters=4, random_state=42)
    pipeline = UnsupervisedPipeline(config)

    # Sintesis dataset berdimensi tinggi: 1000 sampel, 20 fitur
    rng = np.random.default_rng(42)
    X_synthetic = rng.standard_normal((1000, 20))

    # Eksekusi
    latent_space, predicted_labels = pipeline.execute_fit_transform(X_synthetic)
    silhouette = pipeline.evaluate_silhouette(latent_space, predicted_labels)

    logger.info("Pipeline Selesai.")
    logger.info("Ukuran Output Terproyeksi: %s", str(latent_space.shape))
    logger.info("Nilai Inertia (WCSS): %.4f", pipeline.kmeans.state.inertia)
    logger.info("Silhouette Coefficient: %.4f", silhouette)
```

---

### 7. Edge Cases & Failure Modes

| Skenario Kegagalan | Akar Masalah Matematis / Komputasional | Deteksi Dini | Strategi Mitigasi / Fallback |
| :--- | :--- | :--- | :--- |
| **Empty Cluster Phenomenon** | Terjadi saat centroid terisolasi tanpa observasi terdekat pada *assignment step*. Sering dipicu inisialisasi buruk atau nilai $K$ terlalu besar. | Pengecekan ukuran partisi klaster: `if np.sum(labels == k) == 0`. | **Re-seeding:** Relokasi otomatis centroid kosong ke koordinat observasi yang memiliki WCSS parsial tertinggi terhadap centroid lain. |
| **Matriks Kovarians Singular** | Ada fitur yang linear dependent murni atau ber-varians nol ($s_j^2 = 0$). Menyebabkan komputasi dekomposisi matriks gagal. | Komputasi nilai matriks determinan atau rasio *condition number* $\kappa(\mathbf{X}) > 10^{15}$. | Hapus fitur ber-varians nol via variance thresholding; gunakan SVD solver berbasis deviasi nilai mutlak terkecil (*Truncated Randomized SVD*). |
| **Curse of Dimensionality ($D \gg N$)** | Metrik jarak $L_2$ kehilangan daya diskriminasi (*distance concentration*). Jarak antar sembarang titik relatif identik. | Nilai rasio standar deviasi jarak terhadap rata-rata jarak: $\sigma_{\text{dist}} / \mu_{\text{dist}} \approx 0$. | Terapkan normalisasi Cosine terlebih dahulu, atau lakukan reduksi dimensi linear via random projection (*Johnson-Lindenstrauss lemma*) sebelum K-Means. |
| **Degenerasi Outlier Ekstrem** | Metrik WCSS menggunakan error kuadrat $\|\mathbf{x} - \boldsymbol{\mu}\|_2^2$, sehingga outlier masif menarik posisi centroid jauh dari distribusi riil. | Pengecekan kurtosis fitur dan *leverage score* observasi ($h_{ii} = \mathbf{x}_i (\mathbf{X}^T\mathbf{X})^{-1} \mathbf{x}_i^T$). | Ganti metrik fungsi objektif ke L1-norm (*K-Medoids / PAM*), atau terapkan Winsorization (clipping persentil 1% dan 99%) sebelum kalkulasi fitting. |

---

### 8. Trade-offs & Alternatif Solusi

#### 8.1 Matriks Perbandingan Karakteristik Algoritma

```
Metrik Perbandingan: PCA vs Nonlinear Reducer (UMAP/t-SNE) & K-Means vs Density/Distribution Models
+--------------------+-------------------------+-------------------------+-------------------------+
| Dimensi Evaluasi   | Linear (PCA / Truncated)| Non-Linear (UMAP)       | Probabilistik (GMM)     |
+--------------------+-------------------------+-------------------------+-------------------------+
| Kompleksitas Waktu | O(N * D * min(N, D))    | O(N * log(N))           | O(Iter * N * K * D^2)   |
| Kebutuhan Memori   | O(D^2) atau O(N * k)    | O(N * k_neighbors)      | O(K * D^2)              |
| Geometri Data      | Asumsi Subruang Linear  | Manifold Non-linear     | Campuran Gaussian Elips |
| Determinisme       | Deterministik Tinggi    | Stokastik (Inisialisasi)| Sensitif Minimum Lokal  |
| Out-of-Sample Ext. | Ya (Z_new = X_new * V)  | Lambat/Aproksimatif     | Ya (Posterior Prob.)    |
+--------------------+-------------------------+-------------------------+-------------------------+
```

#### 8.2 Rasionalisasi Keputusan Arsitektur
1. **PCA vs. t-SNE/UMAP di Sistem Produksi:**
   * *Gunakan PCA* jika sistem membutuhkan latensi transformasi sub-milidetik untuk inferensi data baru (*out-of-sample extension*) dan interpretabilitas linear bobot fitur (*feature loadings*).
   * *Gunakan UMAP* secara strictly offline untuk pemetaan eksplorasi representasi klaster non-linear atau visualisasi embedding ke ruang 2D/3D. UMAP tidak cocok disematkan di jalur inferensi sinkron berlatensi rendah.
2. **K-Means vs. GMM (Gaussian Mixture Models):**
   * *Gunakan K-Means* jika klaster data diasumsikan bulat seragam (*spherical*), memiliki ukuran partisi seimbang, dan mengutamakan kecepatan throughput komputasi.
   * *Gunakan GMM* ketika data memiliki bentuk elips kovarians beragam (*non-spherical*) dan sistem membutuhkan estimasi ketidakpastian (*soft assignment* probabilitas posterior $P(C_k | \mathbf{x})$ alih-alih *hard assignment* Voronoi).

---

### 9. Best Practices & Standard Industri

1. **Standardisasi Ketat Sifat Linearitas (Z-Score):**
   * PCA mencari arah varians maksimal. Jika fitur $f_1$ memiliki skala $10^6$ (misal: IDR) dan $f_2$ berskala $0-1$ (misal: rasio konversi), komponen utama pertama secara keliru akan didominasi oleh $f_1$ murni tanpa merefleksikan variabilitas struktural sistem. Wajib gunakan `StandardScaler` (atau `RobustScaler` jika dataset memiliki *skewness* tinggi) sebelum transformasi matriks.
2. **Kriteria Seleksi Dimensi Berbasis Kaiser & Knee Rule:**
   * Jangan memilih komponen PCA secara arbitrer. Terapkan ambang kumulatif *Explained Variance Ratio* (biasanya $85\% - 95\%$) atau kriteria Kaiser (simpan komponen dengan $\lambda_j \ge 1.0$ pada matriks korelasi).
3. **Optimasi Memori Out-of-Core dengan IncrementalPCA & MiniBatchKMeans:**
   * Untuk volume data melebihi RAM sistem ($> 64\text{ GB}$), hindari operasi SVD penuh (`np.linalg.svd`). Manfaatkan streaming batching menggunakan chunking memory-mapped (`np.memmap`) via `IncrementalPCA` yang memperbarui estimasi basis kovarians secara bertahap.
4. **Pencegahan Data Leakage pada Unsupervised Preprocessing:**
   * Estimator unsupervised harus di-fit **hanya** pada *training split*. Terapkan mean ($\boldsymbol{\mu}_{\text{train}}$), standard deviation ($\boldsymbol{\sigma}_{\text{train}}$), dan right-singular vectors ($\mathbf{V}_{\text{train}}$) yang sama terhadap validation dan test set:
   $$\mathbf{Z}_{\text{val}} = (\mathbf{X}_{\text{val}} - \boldsymbol{\mu}_{\text{train}}) \mathbf{V}_{k, \text{train}}$$

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus
Sebuah penyedia infrastruktur cloud ingin mengelompokkan profil node server berdasarkan 8 metrik telemetri (CPU, Memori, Disk I/O, Packet Drops, TCP Conns, Context Switches, Cache Misses, GPU Mem) untuk mendeteksi saturasi anomali dan mengidentifikasi arsitektur cluster workload secara otomatis.

#### Tugas Terbimbing
Jalankan script evaluasi berikut untuk memproses data telemetri, menentukan nilai $K$ optimal via metrik Elbow (Inertia) dan Silhouette, lalu proyeksikan ke ruang reduksi PCA.

```python
import numpy as np
from sklearn.datasets import make_blobs
from sklearn.preprocessing import StandardScaler

# Inisialisasi Environment Reproducible
def run_telemetry_clustering_lab():
    print("--- [LAB: Telemetry Clustering & Anomaly Profiling] ---")
    
    # 1. Generate Synthetic Server Telemetry (1500 node, 8 metrik performa, 4 jenis workload asli)
    X_raw, ground_truth = make_blobs(
        n_samples=1500,
        n_features=8,
        centers=4,
        cluster_std=[1.2, 2.5, 0.8, 3.0],
        random_state=101
    )
    
    # 2. Skalasi Fitur secara Standard (Zero Mean, Unit Variance)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)
    
    # 3. Analisis Spektral Reduksi Dimensi dengan PCA
    pca_engine = ProductionPCA(n_components=8)
    pca_engine.fit(X_scaled)
    evr = pca_engine.state.explained_variance_ratio
    cum_evr = np.cumsum(evr)
    
    # Tentukan jumlah dimensi yang mencakup >= 85% varians
    target_components = int(np.argmax(cum_evr >= 0.85) + 1)
    print(f"[PCA Evaluasi] Cumulative Explained Variance: {cum_evr}")
    print(f"[PCA Evaluasi] Dimensi dipangkas dari 8 -> {target_components} (Variance retained: {cum_evr[target_components-1]*100:.2f}%)")
    
    # Reduksi data ke ruang laten
    pca_reducer = ProductionPCA(n_components=target_components)
    Z_telemetry = pca_reducer.fit(X_scaled).transform(X_scaled)
    
    # 4. Search Hyperparameter K Optimal (Elbow Method & Silhouette Analysis)
    candidate_k = [2, 3, 4, 5, 6]
    best_k = None
    best_silhouette = -1.0
    
    print("\n--- Evaluasi Hyperparameter K ---")
    for k in candidate_k:
        kmeans_model = ProductionKMeans(n_clusters=k, random_state=42)
        kmeans_model.fit(Z_telemetry)
        
        # Eksekusi pipeline clustering untuk estimasi metriks
        cfg = PipelineConfig(n_components=target_components, n_clusters=k, random_state=42)
        evaluator = UnsupervisedPipeline(cfg)
        labels = kmeans_model.predict(Z_telemetry)
        sil = evaluator.evaluate_silhouette(Z_telemetry, labels)
        
        print(f"Cluster K={k} | Inertia (WCSS): {kmeans_model.state.inertia:10.2f} | Silhouette Score: {sil:.4f}")
        
        if sil > best_silhouette:
            best_silhouette = sil
            best_k = k
            
    print(f"\n[HASIL OPTIMAL] Konfigurasi Klaster Terbaik: K={best_k} dengan Silhouette={best_silhouette:.4f}")
    
    # 5. Model Serving Validation & Residual Anomaly Check
    optimal_pipeline = UnsupervisedPipeline(
        PipelineConfig(n_components=target_components, n_clusters=best_k, random_state=42)
    )
    Z_final, final_labels = optimal_pipeline.execute_fit_transform(X_scaled)
    
    # Evaluasi Rekonstruksi Error untuk 1 Node Uji
    node_sample = X_scaled[0:1]
    z_sample = optimal_pipeline.pca.transform(node_sample)
    reconstructed_sample = optimal_pipeline.pca.inverse_transform(z_sample)
    reconstruction_loss = np.linalg.norm(node_sample - reconstructed_sample)
    
    print(f"\n[Verifikasi Inferensi] Single Node Projection Shape: {z_sample.shape}")
    print(f"[Verifikasi Inferensi] Reconstruction L2 Loss: {reconstruction_loss:.6f}")
    print(f"[Verifikasi Inferensi] Label Klaster Terpilih: Cluster {final_labels[0]}")
    
    assert reconstruction_loss >= 0.0, "Reconstruction loss tidak boleh negatif."
    assert z_sample.shape[1] == target_components, "Dimensi proyeksi tidak sesuai."
    print("--- Lab Telemetry Berhasil Diselesaikan Sesuai Standar Validasi Numerik ---")

if __name__ == "__main__":
    run_telemetry_clustering_lab()
```