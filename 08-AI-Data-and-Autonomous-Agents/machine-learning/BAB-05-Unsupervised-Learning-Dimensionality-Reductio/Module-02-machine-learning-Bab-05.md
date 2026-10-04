# Kurikulum Rekayasa Perangkat Lunak & Sistem AI Enterprise
## Bab 05: Unsupervised Learning & Dimensionality Reduction
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur *unsupervised learning* berskala produksi yang mampu memproses jutaan vektor berdimensi tinggi (*high-dimensional embeddings*) secara *out-of-core* (streaming/batch).
- Menguasai dekomposisi matematis lanjutan pada reduksi dimensi linear (*Truncated SVD*, *Randomized SVD*, *Incremental PCA*) dan non-linear (*UMAP*, *Parametric UMAP*).
- Mengintegrasikan reduksi dimensi dengan klasterisasi mutakhir (*HDBSCAN*, *Mini-Batch K-Means*) dan *vector database indexing* (HNSW, IVF-PQ pada FAISS).
- Membangun *pipeline* inferensi *low-latency* ($P99 < 15\text{ ms}$) untuk reduksi dimensi *on-the-fly* pada sistem rekomendasi dan deteksi anomali.
- Merancang metrik evaluasi *latent space drift* dan mekanisme deteksi degradasi representasi tanpa label kebenaran dasar (*ground truth labels*).

---

### 2. Prerequisite
Untuk mengikuti modul ini secara optimal, insinyur diwajibkan memiliki pemahaman:
- **Aljabar Linier Lanjut**: *Singular Value Decomposition* (SVD), *Eigendecomposition*, Proyeksi Ortogonal, dan Teorema Johnson-Lindenstrauss.
- **Probabilitas & Topologi Multivariat**: *Manifold learning*, divergensi Kullback-Leibler, *Fuzzy Simplicial Sets*, metrik jarak non-Euclidean ($L_1$, $L_2$, Cosine, Mahalanobis).
- **Pemrograman & Tooling Python**: NumPy (vektorisasi tingkat lanjut, memory-mapping `np.memmap`), Scikit-Learn, PyTorch, FAISS, dan UMAP-learn.
- **Konsep Arsitektur Data**: Pemrosesan *stream* vs *batch*, persistensi artefak model, dan *zero-copy memory sharing*.

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Mekanisme Internal Reduksi Dimensi Linier: PCA vs SVD vs Incremental SVD
Principal Component Analysis (PCA) beroperasi dengan mencari basis ortonormal yang memaksimalkan variansi data:

$$\max_{w} \frac{1}{n} w^T X^T X w \quad \text{s.t.} \quad w^T w = 1$$

Secara praktis di level *enterprise engine*, perhitungan matriks kovariansi $C = \frac{1}{n} X^T X$ memiliki kompleksitas waktu $\mathcal{O}(d^2 n)$ dan memori $\mathcal{O}(d^2)$. Jika dimensi fitur $d$ mencapai puluhan ribu (misal representasi teks bag-of-words atau flattening citra), kalkulasi kovariansi langsung akan memicu *Out-Of-Memory* (OOM).

Sistem produksi modern mengeksekusi PCA via *Singular Value Decomposition* (SVD) langsung pada data yang telah disentrisasi ($X - \mu$):

$$X = U \Sigma V^T$$

- $U \in \mathbb{R}^{n \times n}$: Vektor singular kiri (representasi sampel dalam ruang laten terstandarisasi).
- $\Sigma \in \mathbb{R}^{n \times d}$: Nilai singular (akar kuadrat dari variansi yang dijelaskan).
- $V \in \mathbb{R}^{d \times d}$: Vektor singular kanan (matriks pembebanan / *principal components*).

Untuk data berskala terabyte yang tidak muat dalam RAM, **Incremental PCA** memanfaatkan algoritma *chunk-based low-rank update* (dikembangkan oleh Ross et al.). Ketika *batch* data baru $X_b$ masuk:
1. Centering adaptif diperbarui: $\mu_{\text{new}} = \frac{n_a \mu_a + n_b \mu_b}{n_a + n_b}$.
2. Matriks ortogonal diperluas melalui QR-decomposition terhadap residu proyeksi data baru ke subruang lama.
3. SVD berukuran kecil dijalankan pada representasi terkompresi, menghasilkan matriks komponen baru tanpa pernah membaca ulang data historis.

#### 3.2. Topologi Non-Linier: UMAP (Uniform Manifold Approximation and Projection)
Berbeda dengan t-SNE yang tidak dapat menyimpan fungsi pemetaan parametrik secara alami untuk inferensi data baru (*out-of-sample extension*), UMAP dibangun di atas fondasi geometri diferensial dan topologi aljabar:
1. **Asumsi Manifold**: Data diasumsikan terdistribusi pada *Riemannian manifold* lokal yang terhubung.
2. **Fuzzy Simplicial Sets**: Menghitung probabilitas kedekatan antar titik $x_i$ dan $x_j$:
   
$$p_{i|j} = \exp\left(-\frac{\max(0, d(x_i, x_j) - \rho_i)}{\sigma_i}\right)$$

   Di mana $\rho_i$ adalah jarak ke tetangga terdekat (menjamin keterhubungan lokal), dan $\sigma_i$ dinormalisasi sedemikian rupa sehingga:
   
$$\sum_{j} p_{i|j} = \log_2(k)$$

3. **Optimasi Ruang Laten Rendah**: Meminimalkan *cross-entropy* fuzzy antara representasi berdimensi tinggi ($P$) dan representasi berdimensi rendah ($Q$):
   
$$C(P, Q) = \sum_{e} \left[ p_e \log \frac{p_e}{q_e} + (1 - p_e) \log \frac{1 - p_e}{1 - q_e} \right]$$

Optimasi diselesaikan menggunakan *Stochastic Gradient Descent* (SGD) dengan *negative sampling*, memungkinkan paralelisasi masif pada CPU multi-core atau akselerator GPU.

```
+------------------------------------------------------------------------------------+
| UMAP ALGORITHMIC PIPELINE                                                          |
+------------------------------------------------------------------------------------+
| High-Dim Space (D)                                                                 |
|   [X_1, X_2, ..., X_n] ---> k-NN Graph (Descent approx) ---> Local Metric (rho, sigma)  |
|                                                                    |               |
| Low-Dim Space (d << D)                                             v               |
|   [Y_1, Y_2, ..., Y_n] <--- SGD Minimization <--- Fuzzy Set Union (p_ij = p_i|j + ...)
+------------------------------------------------------------------------------------+
```

#### 3.3. Klasterisasi Densitas: HDBSCAN (Hierarchical Density-Based Spatial Clustering)
K-Means memaksakan klaster berbentuk hiper-sferis (*spherical clusters*) dan sangat rentan terhadap *outliers*. DBSCAN konvensional gagal pada data dengan densitas bervariasi karena parameter epsilon ($\epsilon$) yang statis. 

HDBSCAN menyelesaikan kelemahan ini dengan:
1. **Transformasi Ruang Metrik**: Menggunakan *Mutual Reachability Distance* ($d_{m-reach}$):
   
$$d_{m-reach, k}(a, b) = \max(\{core_k(a), core_k(b), d(a, b)\})$$

   Di mana $core_k(x)$ adalah jarak dari titik $x$ ke tetangga ke-$k$.
2. **Minimum Spanning Tree (MST)**: Membentuk pohon perentang minimum berdasarkan $d_{m-reach}$.
3. **Hierarki Klaster Terkondensasi**: Mengonversi MST menjadi dendrogram, lalu memangkas cabang yang memiliki ukuran lebih kecil dari `min_cluster_size`.
4. **Ekstraksi Klaster Stabil**: Menghitung stabilitas klaster $\mathcal{S}(\mathcal{C})$:
   
$$\mathcal{S}(\mathcal{C}) = \sum_{x \in \mathcal{C}} (\lambda_{\text{death}} - \lambda_{\text{birth}})$$

   Di mana $\lambda = \frac{1}{\epsilon}$. Klaster yang bertahan melintasi rentang densitas terlebar akan dipilih secara otomatis.

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional | Enterprise Unsupervised Pipeline |
| :--- | :--- | :--- |
| **Volumetri Data** | In-memory processing (`sklearn.decomposition.PCA`). Maksimum puluhan GB data mentah. | Out-of-core streaming (`IncrementalPCA`, Memmap, GPU-accelerated cuML). |
| **Kutukan Dimensi** | Jarak $L_2$ kehilangan signifikansi diskriminatif karena *distance concentration*. | Reduksi dimensi bertahap (PCA $\rightarrow$ Metric Learning $\rightarrow$ Vector Indexing). |
| **Serving Inferensi** | Rekalkulasi ulang seluruh dataset saat ada data sampel baru (Batch-only). | Proyeksi matriks transformasi statis / *Parametric network* sub-milidetik. |
| **Evaluasi Kualitas** | Elbow method, Silhouette score manual yang berat secara komputasi ($\mathcal{O}(n^2)$). | *Trustworthiness*, *Continuity*, *Density-based Cluster Validation* (DBCV), & Drift monitoring. |

---

### 5. How (Workflow detail)

Alur kerja arsitektur sistem reduksi dimensi dan pengelompokan enterprise:

```
[Ingestion Stream / Data Lake]
               │
               ▼
[Chunked Preprocessing & Scaling (RobustScaler / Z-Score)]
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ Dimensionality Reduction Stage                          │
│                                                         │
│  ├─ Phase 1: Variance Truncation (Incremental PCA)      │
│  │   Input: 1536-D Vector -> Output: 128-D Dense Vector │
│  │                                                      │
│  └─ Phase 2: Manifold Embedding (Parametric UMAP)       │
│      Input: 128-D Vector  -> Output: 16-D Dense Vector  │
└─────────────────────────────────────────────────────────┘
               │
               ├──────────────────────────────────────────┐
               ▼                                          ▼
┌───────────────────────────────┐          ┌───────────────────────────────┐
│ Real-Time Latent Search Index │          │ Latent Topology Monitoring    │
│ (FAISS / HNSW IVF-PQ)         │          │ (Evidently / Custom MMD)      │
│  - Sub-10ms similarity search │          │  - Wasserstein Distance check │
│  - Dense clustering (HDBSCAN) │          │  - Cluster stability tracking │
└───────────────────────────────┘          └───────────────────────────────┘
```

1. **Ingestion & Streaming Chunking**: Data embedding berskala besar dialirkan dari data lake melalui generator chunk berukuran fixed-size (misal 50.000 vektor per batch).
2. **Incremental Variance Preservation**: `IncrementalPCA` mengakumulasi representasi statistik data hingga variansi kumulatif mencapai $\ge 90\%$.
3. **Topological Compression**: Sub-vektor terkompresi ditransformasikan untuk mempertahankan keterhubungan lokal dan global.
4. **Clustering & Indexing**: Ruang laten dipetakan ke dalam FAISS Index untuk pencarian semantik berkecepatan tinggi, sementara HDBSCAN mendeteksi segmen dan noise secara otomatis.
5. **Observability Loop**: Sampel harian diproyeksikan dan diuji terhadap basis data referensi menggunakan metrik Maximum Mean Discrepancy (MMD) untuk mendeteksi pergeseran domain representasi.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Reduksi Dimensi sebagai Sistem Kompresi Blueprint Arsitektur
Bayangkan gedung pencakar langit 100 lantai yang didokumentasikan dalam maket fisik 3D berskala 1:1 (High-Dimensional Space). 
- **PCA** diibaratkan seperti menyinari maket tersebut dari sudut tertentu untuk memproyeksikan bayangannya ke dinding datar 2D. Sudut dipilih agar bayangan yang dihasilkan mencakup siluet bangunan seluas mungkin tanpa tumpang tindih berlebih.
- **UMAP** diibaratkan seperti melepaskan kulit bangunan secara elastis, mempertahankan ruangan-ruangan yang saling bersebelahan agar tetap berdekatan pada selembar kertas peta lipat tanpa merobek koneksi struktural utamanya.
- **HDBSCAN** bertindak seperti inspektur yang mencari klaster keramaian penghuni di dalam gedung tanpa menetapkan batas bentuk ruangan yang kaku.

#### Diagram ASCII: Arsitektur Out-of-Core Transformasi & Indexing

```
HIGH-DIMENSIONAL EMBEDDINGS (D=1536)
[ Batch 1 (N=50K) ] ──┐
[ Batch 2 (N=50K) ] ──┼──> [ Memory-Mapped Buffer ] 
[ Batch N (N=50K) ] ──┘          │
                                 ▼
                     +───────────────────────+
                     |  Incremental PCA      |
                     |  (Online SVD Update)  |
                     +───────────────────────+
                                 │
                         Projected (D=64)
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
+───────────────────────+                   +───────────────────────+
| Non-Linear Projection |                   | Vector Search Engine  |
| (Parametric UMAP)     |                   | (FAISS HNSW Index)    |
| Output: D=8           |                   +───────────────────────+
+───────────────────────+                              │
           │                                           ▼
           ▼                                [ Sub-10ms Inverted File ]
+───────────────────────+
| Density Clustering    |
| (HDBSCAN Partition)   |
| Detect Outliers / IDs |
+───────────────────────+
```

---

### 7. Simple Example & Practical Example

#### 7.1. Simple Example: Manual Online SVD Projection (Prinsip Dasar IPCA)
Implementasi algoritma pembaruan basis ortogonal terproyeksi secara streaming dari awal:

```python
import numpy as np

class MinimalIncrementalPCA:
    """Manual low-rank streaming SVD projector."""
    def __init__(self, n_components: int):
        self.n_components = n_components
        self.components_: np.ndarray | None = None
        self.mean_: np.ndarray | None = None
        self.n_samples_seen_: int = 0

    def partial_fit(self, X: np.ndarray) -> "MinimalIncrementalPCA":
        n_samples, n_features = X.shape
        if self.mean_ is None:
            self.mean_ = np.zeros(n_features, dtype=np.float64)
            self.components_ = np.zeros((self.n_components, n_features), dtype=np.float64)

        # Update global mean
        col_mean = np.mean(X, axis=0)
        total_samples = self.n_samples_seen_ + n_samples
        updated_mean = (self.n_samples_seen_ * self.mean_ + n_samples * col_mean) / total_samples

        # Centering
        X_centered = X - col_mean

        if self.n_samples_seen_ == 0:
            # First batch SVD
            _, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
            self.components_ = Vt[:self.n_components]
        else:
            # Combine current components with new batch residuals
            mean_correction = np.sqrt((self.n_samples_seen_ * n_samples) / total_samples) * (self.mean_ - col_mean)
            combined = np.vstack([
                self.components_ * np.sqrt(self.n_samples_seen_),
                X_centered,
                mean_correction
            ])
            _, _, Vt = np.linalg.svd(combined, full_matrices=False)
            self.components_ = Vt[:self.n_components]

        self.mean_ = updated_mean
        self.n_samples_seen_ = total_samples
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.components_ is None or self.mean_ is None:
            raise RuntimeError("Model must be fitted before transforming data.")
        return np.dot(X - self.mean_, self.components_.T)

# Validasi Fungsional
if __name__ == "__main__":
    np.random.seed(42)
    stream_chunk_1 = np.random.randn(100, 10)
    stream_chunk_2 = np.random.randn(100, 10)

    ipca = MinimalIncrementalPCA(n_components=2)
    ipca.partial_fit(stream_chunk_1)
    ipca.partial_fit(stream_chunk_2)

    projected = ipca.transform(np.random.randn(5, 10))
    print(f"Projected shape: {projected.shape}")
```

#### 7.2. Practical Example: Production Vector Dimensionality Reduction & Cluster Serving Pipeline
Sistem produksi berbasis Scikit-Learn, Joblib, dan HDBSCAN dengan integrasi penanganan error, validasi tipe (*type hint*), dan pipeline komputasi terdistribusi:

```python
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Generator, Tuple

import hdbscan
import joblib
import numpy as np
from sklearn.decomposition import IncrementalPCA
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LatentEngine")

@dataclass(frozen=True)
class PipelineConfig:
    raw_dim: int = 512
    intermediate_dim: int = 64
    batch_size: int = 10_000
    min_cluster_size: int = 50
    min_samples: int = 15
    artifact_path: str = "./artifacts"

class EnterpriseDimensionalityPipeline:
    """End-to-End Enterprise Unsupervised Production Pipeline."""
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.scaler = StandardScaler()
        self.ipca = IncrementalPCA(n_components=self.config.intermediate_dim, batch_size=self.config.batch_size)
        self.clusterer: hdbscan.HDBSCAN | None = None
        os.makedirs(self.config.artifact_path, exist_ok=True)

    def fit_incremental_pca(self, data_generator: Generator[np.ndarray, None, None], total_batches: int) -> None:
        """Stream data out-of-core to train Scaler and Incremental PCA without memory spikes."""
        logger.info("Starting Incremental Preprocessing & Variance Truncation...")
        
        # Step 1: Fit Scaler online
        for batch_idx, batch in enumerate(data_generator()):
            if batch.shape[1] != self.config.raw_dim:
                raise ValueError(f"Feature mismatch: Expected {self.config.raw_dim}, got {batch.shape[1]}")
            self.scaler.partial_fit(batch)
            logger.info(f"Scaler: Processed batch {batch_idx + 1}/{total_batches}")

        # Step 2: Fit Incremental PCA online
        for batch_idx, batch in enumerate(data_generator()):
            scaled_batch = self.scaler.transform(batch)
            self.ipca.partial_fit(scaled_batch)
            logger.info(f"IPCA: Processed batch {batch_idx + 1}/{total_batches}")

        explained_var = np.sum(self.ipca.explained_variance_ratio_)
        logger.info(f"IPCA Training Complete. Total Explained Variance Retained: {explained_var:.4f}")

    def fit_clustering(self, latent_vectors: np.ndarray) -> np.ndarray:
        """Fit HDBSCAN on projected representations."""
        logger.info(f"Fitting HDBSCAN on {latent_vectors.shape[0]} latent vectors...")
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.config.min_cluster_size,
            min_samples=self.config.min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True  # Penting untuk inferensi fast out-of-sample
        )
        cluster_labels = self.clusterer.fit_predict(latent_vectors)
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        noise_ratio = np.mean(cluster_labels == -1)
        logger.info(f"Clustering Complete: {n_clusters} clusters found. Noise ratio: {noise_ratio:.2%}")
        return cluster_labels

    def transform_infer(self, raw_features: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Low-latency inference pipeline for real-time projection and soft cluster assignment."""
        if self.clusterer is None:
            raise RuntimeError("Model is not completely fitted. Call fit_clustering first.")
        
        # Step 1: Scale
        scaled = self.scaler.transform(raw_features)
        
        # Step 2: Project
        latent = self.ipca.transform(scaled)
        
        # Step 3: Fast Out-Of-Sample HDBSCAN approximate assignment
        labels, strengths = hdbscan.approximate_predict(self.clusterer, latent)
        
        return latent, labels, strengths

    def export_artifacts(self) -> None:
        """Persist state components."""
        joblib.dump(self.scaler, os.path.join(self.config.artifact_path, "scaler.joblib"))
        joblib.dump(self.ipca, os.path.join(self.config.artifact_path, "ipca.joblib"))
        joblib.dump(self.clusterer, os.path.join(self.config.artifact_path, "hdbscan.joblib"))
        logger.info("Pipeline artifacts persisted successfully.")

# Generator Dummy untuk Simulasi Out-Of-Core Memory
def synthetic_stream_source(n_batches: int, batch_size: int, dim: int):
    def _gen():
        for _ in range(n_batches):
            yield np.random.randn(batch_size, dim).astype(np.float32)
    return _gen

if __name__ == "__main__":
    cfg = PipelineConfig(raw_dim=128, intermediate_dim=32, batch_size=2000, min_cluster_size=20)
    pipeline = EnterpriseDimensionalityPipeline(cfg)

    # Simulasi 5 batch stream (Total 10,000 sampel)
    data_gen = synthetic_stream_source(n_batches=5, batch_size=cfg.batch_size, dim=cfg.raw_dim)
    
    # 1. Fit Online
    pipeline.fit_incremental_pca(data_gen, total_batches=5)

    # 2. Extract latent data untuk clustering
    logger.info("Extracting latent space representations for indexing...")
    inference_sample = np.random.randn(5000, cfg.raw_dim).astype(np.float32)
    scaled_sample = pipeline.scaler.transform(inference_sample)
    latent_space = pipeline.ipca.transform(scaled_sample)

    # 3. Fit Clusterer
    pipeline.fit_clustering(latent_space)

    # 4. Low-latency real-time inference execution
    query_vector = np.random.randn(1, cfg.raw_dim).astype(np.float32)
    proj, cluster_id, confidence = pipeline.transform_infer(query_vector)
    logger.info(f"Query Processed -> Latent Shape: {proj.shape}, Cluster: {cluster_id[0]}, Confidence: {confidence[0]:.4f}")

    # 5. Persist
    pipeline.export_artifacts()
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Multimodal E-Commerce Vector Search & Cold-Start Deduplication
- **Skala Sistem**: Marketplace Tier-1 memproses katalog produk sebesar **80.000.000 item**.
- **Input Feature**: Vektor gabungan teks (BERT 768-D) + citra (CLIP 512-D) menghasilkan representasi gabungan sebesar **1280 dimensi**.
- **Masalah**:
  1. Melakukan pencarian tetangga terdekat (*k-NN*) langsung pada 1280-D di indeks FAISS HNSW mengonsumsi RAM sebesar ~600 GB pada cluster memori, dengan latensi P99 mencapai $85\text{ ms}$.
  2. Terdapat jutaan barang duplikat (*near-duplicate spam*) dari berbagai penjual yang menggunakan judul sedikit berbeda namun memiliki esensi barang yang sama.

#### Solusi Arsitektur Produksi:
1. **Dua Tahap Kompresi Representasi**:
   - **Tahap 1 (Linear)**: Matriks transformasi `IncrementalPCA` dilatih secara offline mingguan untuk mereduksi 1280-D menjadi 128-D dengan retensi variansi $94\%$. Latensi eksekusi proyeksi linier melalui komputasi dot-product BLAS teroptimasi hanya membutuhkan $0.4\text{ ms}$.
   - **Tahap 2 (Quantization & Indexing)**: Vektor 128-D dimasukkan ke dalam FAISS dengan skema indeks `IVF4096,PQ16`. Reduksi memori mencapai faktor $18\times$ (turun dari 600 GB menjadi ~34 GB RAM).
2. **Offline Deduplication Pipeline**:
   - Sampel representasi 128-D diklasterisasi menggunakan **HDBSCAN distributed via Ray**.
   - Setiap klaster berdensitas sangat tinggi (*high persistence score*) ditandai sebagai grup barang identik. Penjual yang mengunggah barang dalam klaster tersebut otomatis dikonsolidasikan ke dalam satu tampilan halaman produk (*Single Product Page aggregation*).
3. **Hasil**:
   - Latensi pencarian P99 turun dari $85\text{ ms}$ menjadi **$6.8\text{ ms}$**.
   - Biaya infrastruktur klaster memori hemat sebesar **$14.200/bulan**.
   - Menghapus 4,2 juta listing barang duplikat dengan akurasi presisi klaster $99.1\%$.

---

### 9. Trade-offs

| Pendekatan / Algoritma | Keunggulan Utama | Kelemahan Kritis | Metrik Ambang Batas (Production Threshold) |
| :--- | :--- | :--- | :--- |
| **PCA (Linear)** | - Waktu inferensi ultra-rendah ($\mathcal{O}(d \cdot k)$ via dot product)<br>- Hasil sepenuhnya deterministik | Kehilangan korelasi non-linear yang kompleks antar-fitur. | Gunakan jika *Explained Variance Ratio* kumulatif $\ge 85\%$ pada dimensi target. |
| **UMAP (Non-Linear)** | - Menangkap topologi global dan lokal manifold dengan presisi tinggi | Waktu inferensi tinggi; inferensi titik baru membutuhkan pendekatan k-NN atau jaringan parametrik terpisah. | Ideal untuk visualisasi, *exploratory analysis*, atau pipeline batch/offline. |
| **Autoencoders (Neural)**| - Mampu mempelajari pemetaan non-linear yang sangat fleksibel dan dapat di-deploy via ONNX Runtime | - Rawan *overfitting*<br>- Membutuhkan biaya pelatihan GPU yang tinggi<br>- Tidak ada jaminan ortogonalitas | Gunakan jika ukuran data $> 10^7$ sampel dan hubungan fitur sangat non-linear (misal audio/video mentah). |
| **K-Means vs HDBSCAN** | K-Means: Sangat cepat ($\mathcal{O}(n \cdot k \cdot i)$), inferensi mudah via jarak centroid. | K-Means gagal pada klaster non-convex; sensitif terhadap noise/outlier. | Gunakan HDBSCAN untuk data riil tak beraturan; gunakan K-Means jika latensi inferensi partisi $< 1\text{ ms}$ diwajibkan. |

---

### 10. Common Mistakes & Troubleshooting

#### Error 1: Data Leakage pada Sentrisasi Matriks (Centering Mismatch)
- **Gejala**: Penurunan akurasi klasifikasi/pencarian hilir (*downstream tasks*) yang drastis ketika model reduksi dimensi diuji pada data produksi.
- **Akar Masalah**: Pustaka eksternal melakukan proyeksi menggunakan komponen ortogonal $V^T$, tetapi lupa melakukan pengurangan terhadap rata-rata data training ($\mu_{\text{train}}$), melainkan menggunakan rata-rata data batch pengujian saat ini ($\mu_{\text{test}}$).
- **Solusi**: Pastikan selalu membungkus pipeline dengan `Pipeline([('scaler', StandardScaler(with_std=False)), ('pca', PCA())])` atau menyelaraskan $\mu$ secara eksplisit.

#### Error 2: Curse of Dimensionality pada Metric Distance di HDBSCAN
- **Gejala**: HDBSCAN menandai hampir seluruh data ($> 90\%$) sebagai noise (label `-1`).
- **Akar Masalah**: Menjalankan HDBSCAN langsung pada data dengan $D > 100$ menggunakan jarak Euclidean. Fenomena *distance concentration* menyebabkan rasio antara jarak terjauh dan terdekat mendekati angka 1:

$$\lim_{d \to \infty} \frac{\text{dist}_{\max} - \text{dist}_{\min}}{\text{dist}_{\min}} \to 0$$

- **Solusi**: Jangan pernah menjalankan HDBSCAN langsung pada ruang berdimensi tinggi mentah. Reduksi dimensi terlebih dahulu ke $D \le 32$ menggunakan PCA atau UMAP.

#### Error 3: Menggunakan Non-Parametric UMAP untuk Serving Real-Time Berkecepatan Tinggi
- **Gejala**: Server inferensi mengalami bottleneck CPU hingga 100% dan latensi melonjak $> 500\text{ ms}$ per request.
- **Akar Masalah**: Objek `UMAP.transform()` secara *default* harus mencari k-NN pada ruang pelatihan awal menggunakan representasi graf lokal sebelum dapat memproyeksikan satu titik baru.
- **Solusi**: Latih **Parametric UMAP** yang membungkus pemetaan topologi UMAP ke dalam arsitektur Multi-Layer Perceptron (MLP) PyTorch. Konversi model MLP tersebut ke format **ONNX** dan jalankan inferensi via TensorRT/ONNX Runtime.

---

### 11. Best Practices (Production Checklist)

- [ ] **Standardisasi Sebelum Reduksi Linier**: Pastikan data dinormalisasi ($Z$-score) sebelum PCA jika unit fitur bervariasi; lewatkan standardisasi skala jika data berupa embedding yang dinormalisasi pada unit sphere ($L_2 = 1$).
- [ ] **Analisis Elbow pada Scree Plot**: Tentukan jumlah komponen PCA menggunakan kriteria *Explained Variance Retained* minimal $90\%$, atau gunakan kriteria *Minka's MLE* (`n_components='mle'`).
- [ ] **Out-of-Core Processing**: Gunakan `np.memmap` atau generator streaming untuk melatih model reduksi jika dataset melebihi $50\%$ kapasitas RAM host.
- [ ] **Simpan State Statistik**: Pastikan nilai Mean, Eigenvalues, dan Components diekspor dalam format terkompresi biner portabel (`joblib`, `Safetensors`, atau `ONNX`).
- [ ] **Latent Drift Detection**: Pantau jarak Wasserstein (Earth Mover's Distance) atau *Maximum Mean Discrepancy* (MMD) pada distribusi ruang laten setiap minggu untuk mendeteksi pergeseran perilaku input.
- [ ] **Konfigurasi HDBSCAN Prediction**: Atur `prediction_data=True` saat inisialisasi pelatihan agar fungsi `approximate_predict` dapat digunakan pada tahap serving inferensi out-of-sample.

---

### 12. Hands-on Practice

Simpan seluruh file praktikum di direktori: `hands-on/m02/`

#### Struktur Direktori
```text
hands-on/m02/
├── config.py
├── trainer.py
├── server.py
└── test_pipeline.py
```

#### Langkah 1: Buat `hands-on/m02/config.py`
```python
from dataclasses import dataclass

@dataclass
class AppConfig:
    N_SAMPLES: int = 25000
    N_FEATURES: int = 256
    N_COMPONENTS: int = 16
    CHUNK_SIZE: int = 5000
    ARTIFACT_DIR: str = "./artifacts"
    SEED: int = 42
```

#### Langkah 2: Buat `hands-on/m02/trainer.py`
```python
import os
import joblib
import numpy as np
from sklearn.decomposition import IncrementalPCA
from sklearn.preprocessing import StandardScaler
from config import AppConfig

def run_training():
    np.random.seed(AppConfig.SEED)
    os.makedirs(AppConfig.ARTIFACT_DIR, exist_ok=True)
    
    print("[1/4] Generating Synthetic High-Dim Clustered Embeddings...")
    # Buat data sintetis multi-modal
    cluster_1 = np.random.randn(AppConfig.N_SAMPLES // 2, AppConfig.N_FEATURES) + 2.0
    cluster_2 = np.random.randn(AppConfig.N_SAMPLES // 2, AppConfig.N_FEATURES) - 2.0
    dataset = np.vstack([cluster_1, cluster_2]).astype(np.float32)
    np.random.shuffle(dataset)

    scaler = StandardScaler()
    ipca = IncrementalPCA(n_components=AppConfig.N_COMPONENTS, batch_size=AppConfig.CHUNK_SIZE)

    print("[2/4] Training Scaler and Incremental PCA (Streaming Chunks)...")
    for i in range(0, AppConfig.N_SAMPLES, AppConfig.CHUNK_SIZE):
        chunk = dataset[i : i + AppConfig.CHUNK_SIZE]
        scaler.partial_fit(chunk)

    for i in range(0, AppConfig.N_SAMPLES, AppConfig.CHUNK_SIZE):
        chunk = dataset[i : i + AppConfig.CHUNK_SIZE]
        scaled = scaler.transform(chunk)
        ipca.partial_fit(scaled)

    total_var = np.sum(ipca.explained_variance_ratio_)
    print(f"Variance Retained with {AppConfig.N_COMPONENTS} dimensions: {total_var:.2%}")

    print("[3/4] Exporting Model Artifacts...")
    joblib.dump(scaler, os.path.join(AppConfig.ARTIFACT_DIR, "scaler.pkl"))
    joblib.dump(ipca, os.path.join(AppConfig.ARTIFACT_DIR, "ipca.pkl"))
    print("Training Pipeline Successfully Finished.")

if __name__ == "__main__":
    run_training()
```

#### Langkah 3: Buat `hands-on/m02/server.py`
```python
import os
import time
import joblib
import numpy as np
from config import AppConfig

class ProjectionEngine:
    def __init__(self):
        self.scaler = joblib.load(os.path.join(AppConfig.ARTIFACT_DIR, "scaler.pkl"))
        self.ipca = joblib.load(os.path.join(AppConfig.ARTIFACT_DIR, "ipca.pkl"))

    def project(self, vector: np.ndarray) -> np.ndarray:
        scaled = self.scaler.transform(vector)
        latent = self.ipca.transform(scaled)
        return latent

if __name__ == "__main__":
    engine = ProjectionEngine()
    test_vec = np.random.randn(1, AppConfig.N_FEATURES).astype(np.float32)
    
    # Latency Benchmark
    runs = 1000
    start = time.perf_counter()
    for _ in range(runs):
        _ = engine.project(test_vec)
    avg_latency_ms = ((time.perf_counter() - start) / runs) * 1000
    
    print(f"Engine Ready. Average Projection Latency: {avg_latency_ms:.4f} ms per vector.")
```

#### Langkah 4: Buat `hands-on/m02/test_pipeline.py`
```python
import os
import numpy as np
from config import AppConfig
from server import ProjectionEngine

def test_pipeline_output_shape():
    assert os.path.exists(os.path.join(AppConfig.ARTIFACT_DIR, "scaler.pkl"))
    assert os.path.exists(os.path.join(AppConfig.ARTIFACT_DIR, "ipca.pkl"))
    
    engine = ProjectionEngine()
    dummy = np.random.randn(5, AppConfig.N_FEATURES).astype(np.float32)
    out = engine.project(dummy)
    
    assert out.shape == (5, AppConfig.N_COMPONENTS), f"Wrong output shape: {out.shape}"
    assert not np.isnan(out).any(), "Output contains NaN values!"
    print("All Integration Tests Passed Successfully!")

if __name__ == "__main__":
    test_pipeline_output_shape()
```

---

### 13. Exercise

#### Level 1 (Easy): Analisis Rekonstruksi Error PCA
- **Tugas**: Muat dataset *Digits* dari Scikit-Learn (dimensi 64). Latih model PCA dengan rentang komponen $k \in [2, 8, 16, 32, 64]$.
- **Target Deliverable**: Hitung *Mean Squared Reconstruction Error* ($MSE(X, \hat{X})$) untuk setiap nilai $k$, di mana $\hat{X} = X_{\text{projected}} V + \mu$. Plot hubungan antara jumlah komponen versus rekonstruksi loss.

#### Level 2 (Medium): Outlier Filtering dengan HDBSCAN Outlier Scores
- **Tugas**: Buat script inferensi yang menerima dataset sintetis berisi 95% data terdistribusi Gauss dan 5% uniform noise. Latih HDBSCAN.
- **Target Deliverable**: Gunakan atribut `outlier_scores_` dari HDBSCAN (berdasarkan algoritma GLOSH - *Global-Local Outlier Score from Hierarchies*). Buat fungsi `filter_clean_data(threshold=0.85)` yang memisahkan sinyal bersih dari noise, lalu evaluasi dampaknya terhadap stabilitas cluster centroid.

#### Level 3 (Hard): Parametric Manifold Dimensionality Reduction dengan PyTorch
- **Tugas**: Bangun arsitektur Autoencoder berbasis PyTorch (Encoder: $512 \to 128 \to 16$, Decoder: $16 \to 128 \to 512$) yang memiliki *bottleneck layer* sebagai pengganti UMAP untuk reduksi non-linear berkemampuan inferensi deterministik.
- **Target Deliverable**: Terapkan loss gabungan:
  
$$\mathcal{L} = \mathcal{L}_{\text{reconstruction}} + \lambda \mathcal{L}_{\text{contractive}}$$

  Export layer Encoder ke format ONNX dan validasi bahwa latensi inferensi batch=1 berjalan di bawah $1.5\text{ ms}$ pada CPU.

---

### 14. Challenge (Tantangan Studi Kasus Kompleks)

**Deskripsi Kasus**:
Anda adalah Principal AI Infrastructure Engineer di sebuah perusahaan keamanan siber (Cybersecurity) global. Sistem Anda memproses **100.000 events/detik** berupa log telemetri jaringan kernel berdimensi 400 (fitur statistik frekuensi, durasi socket, rasio entropi payload). Data ini tidak berlabel (*unlabeled*).

**Spesifikasi Tantangan**:
1. Rancang arsitektur sistem berbasis *microservices/streaming engine* yang dapat mendeteksi serangan Zero-Day (*novel topological anomalies*) menggunakan reduksi dimensi dan klasterisasi tak terbimbing.
2. Latensi end-to-end tidak boleh melebihi **$20\text{ ms}$** per event ($P99$).
3. Model harus menangani fenomena **Concept Drift** tanpa downtime: Pola jaringan normal pada hari kerja berbeda signifikan dengan akhir pekan. Sistem dilarang melakukan retrain *full-dataset* dari awal karena besarnya volume data ($> 8.6$ miliar event/hari).
4. Sediakan spesifikasi desain arsitektur yang mencakup:
   - Mekanisme update matematis (*Online/Streaming Learning*).
   - Strategi penyimpanan matriks proyeksi di memori.
   - Pemicu (*circuit breaker / re-indexing trigger*) otomatis ketika model laten saat ini sudah tidak lagi representatif (menggunakan metrik jarak distribusi non-parametrik).

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Pertanyaan)
1. **Mengapa dekomposisi SVD lebih disukai daripada kalkulasi matriks kovariansi langsung ($X^T X$) pada PCA modern?**
   - A. SVD hanya bisa memproses matriks bujur sangkar.
   - B. Menghitung $X^T X$ secara eksplisit dapat menyebabkan instabilitas numerik akibat *round-off error* kuadratik serta konsumsi RAM yang tinggi saat fitur berukuran masif.
   - C. SVD otomatis melakukan klasterisasi data secara iteratif.
   - D. SVD tidak membutuhkan proses *mean-centering*.
   *Jawaban yang benar*: **B**.

2. **Karakteristik utama yang membedakan UMAP dari t-SNE standar dalam konteks rekayasa sistem adalah...**
   - A. UMAP mempertahankan struktur topologi global lebih baik dan secara matematis lebih mudah diperluas untuk proyeksi data baru (*out-of-sample mapping*).
   - B. UMAP hanya dapat berjalan pada data dengan dimensi di bawah 10.
   - C. t-SNE memiliki kompleksitas waktu linier $\mathcal{O}(n)$, sedangkan UMAP adalah eksponensial.
   - D. UMAP tidak menggunakan fungsi jarak sama sekali.
   *Jawaban yang benar*: **A**.

3. **Label -1 pada output hasil klasterisasi HDBSCAN mengindikasikan bahwa data tersebut...**
   - A. Berada di klaster paling pertama.
   - B. Memiliki nilai fitur negatif pada ruang input asli.
   - C. Diklasifikasikan sebagai derau (*noise/outlier*) karena tidak memenuhi kriteria densitas minimum lokal.
   - D. Mengalami kegagalan komputasi floating-point.
   *Jawaban yang benar*: **C**.

4. **Metrik evaluasi mana yang dapat digunakan untuk mengukur kualitas reduksi dimensi manifold tanpa adanya label kebenaran dasar?**
   - A. F1-Score.
   - B. Log-Loss.
   - C. Trustworthiness and Continuity.
   - D. Categorical Cross-Entropy.
   *Jawaban yang benar*: **C**.

5. **Apa efek dari tidak menstandarisasi fitur (mean=0, std=1) sebelum menjalankan PCA pada data dengan skala unit yang berbeda jauh?**
   - A. Algoritma PCA akan menghasilkan error pembagian dengan nol.
   - B. Fitur dengan skala numerik terbesar akan mendominasi *principal components*, mengabaikan variansi dari fitur berdimensi unit kecil.
   - C. Matriks proyeksi akan berubah menjadi non-ortogonal.
   - D. Semua nilai singular akan menjadi nol.
   *Jawaban yang benar*: **B**.

---

#### Bagian 2: Intermediate (5 Pertanyaan)
1. **Pada Incremental PCA, bagaimana algoritma memperbarui nilai rata-rata (*mean*) ketika batch baru berukuran $N_b$ diproses di atas data historis yang sudah memproses $N_a$ sampel?**
   - A. Nilai rata-rata lama langsung dibuang dan digantikan oleh rata-rata batch baru.
   - B. Rata-rata diperbarui dengan pembobotan proporsional: $\mu = \frac{N_a \mu_a + N_b \mu_b}{N_a + N_b}$.
   - C. Rata-rata dihitung menggunakan median statis dari sampel pertama.
   - D. Nilai rata-rata tidak pernah diubah setelah inisialisasi awal.
   *Jawaban yang benar*: **B**.

2. **Apa peran parameter $\rho_i$ (*rho*) pada formulasi metrik lokal UMAP?**
   - A. Sebagai regularisasi bobot $L_2$.
   - B. Menetapkan jarak ke tetangga terdekat, memastikan manifold lokal tetap terhubung (*connected graph*) meskipun berada di area densitas sangat rendah.
   - C. Mengatur rasio kompresi dimensi akhir.
   - D. Mengontrol learning rate pada optimasi SGD.
   *Jawaban yang benar*: **B**.

3. **Mengapa algoritma K-Means sering gagal jika diterapkan langsung pada representasi ruang laten hasil UMAP 2-Dimensi?**
   - A. Ruang laten UMAP tidak memiliki jarak Euclidean.
   - B. UMAP menghasilkan struktur klaster dengan kerapatan bervariasi dan bentuk topologi yang non-hyper-spherical, melanggar asumsi dasar geometri K-Means.
   - C. UMAP selalu menghasilkan representasi biner.
   - D. K-Means hanya menerima input berdimensi di atas 100.
   *Jawaban yang benar*: **B**.

4. **Dalam integrasi pencarian vektor enterprise (misal FAISS), apa tujuan utama dilakukannya PCA Whitening pada embedding sebelum proses Product Quantization (PQ)?**
   - A. Menghapus seluruh nilai vektor yang bernilai negatif.
   - B. Mendekorelasikan komponen fitur dan menstandarisasi variansinya ke 1, sehingga error kuantisasi pada sub-vektor PQ terdistribusi merata.
   - C. Menghindari kebutuhan komputasi GPU.
   - D. Mengurangi ukuran file indeks menjadi nol byte.
   *Jawaban yang benar*: **B**.

5. **Apa konsekuensi teknis jika parameter `min_cluster_size` pada HDBSCAN disetel terlalu kecil (misal: 2)?**
   - A. HDBSCAN akan bertransformasi menjadi K-Means.
   - B. Waktu komputasi menjadi tak terhingga.
   - C. Hierarki klaster terkondensasi tidak mampu memfilter fluktuasi mikro, memicu terbentuknya ratusan klaster semu (*micro-clusters*) dan menurunkan daya generalisasi.
   - D. Algoritma akan menolak mengeksekusi perhitungan MST.
   *Jawaban yang benar*: **C**.

---

#### Bagian 3: Production Scenarios (3 Pertanyaan Kasus)
1. **Skenario Kasus 1**:
   Sebuah model pencarian dokumen legal mentransformasikan teks ke vektor representasi 768-D. Anda menerapkan PCA untuk mereduksi dimensi ke 64-D agar muat dalam cluster FAISS. Namun, tim penguji menemukan bahwa relevansi dokumen hukum yang sangat spesifik (berisi istilah langka) anjlok secara signifikan, meskipun *cumulative explained variance* PCA model menunjukkan angka 92%.
   - **Tindakan mitigasi arsitektur terbaik**:
     - A. Naikkan dimensi ke 1024-D dengan padding nol.
     - B. Variansi $8\%$ yang hilang kemungkinan besar adalah sinyal kritis dari terminologi hukum langka (yang secara matematis variansinya kecil di korpus global). Ubah reduksi dimensi ke kombinasi *sparse-dense hybrid retrieval* (misal: gabungan BM25 dengan dense 64-D) atau terapkan reduksi terarah (*Supervised Dimension Reduction* / Triplet Loss Projection).
     - C. Hapus standardisasi data agar istilah hukum mendominasi variansi.
     - D. Ganti PCA dengan algoritma Mean-Shift.
   *Jawaban yang benar*: **B**.

2. **Skenario Kasus 2**:
   Pipeline streaming inferensi Anda melayani fungsi `IncrementalPCA.transform()` pada instance Kubernetes. Ketika beban puncak (*traffic spike*) mencapai 50.000 req/detik, CPU utilization melonjak ke batas limit dan latensi P99 melanggar batas SLA ($> 100\text{ ms}$). Profiling menunjukkan bottleneck berada di alokasi memori internal fungsi dot product matriks NumPy.
   - **Optimasi rekayasa paling tepat tanpa mengubah arsitektur model**:
     - A. Ganti NumPy dengan query database SQL reguler.
     - B. Simpan komponen PCA ($V^T$) dalam format C-contiguous buffer, kompilasi operasi proyeksi menggunakan library BLAS teroptimasi (misal: Intel MKL atau OpenBLAS multi-threaded), atau transformasikan model menjadi bentuk jaringan satu layer terkuantisasi via ONNX Runtime dengan akselerasi instruksi vektor CPU AVX-512.
     - C. Lakukan retraining model setiap 5 menit.
     - D. Nonaktifkan threading pada lingkungan Python.
   *Jawaban yang benar*: **B**.

3. **Skenario Kasus 3**:
   Sistem deteksi fraud transaksi keuangan menggunakan kombinasi PCA 16-D + HDBSCAN. Setelah 3 bulan beroperasi stabil dengan tingkat outlier rata-rata $1.2\%$, tiba-tiba sistem mendeteksi lonjakan outlier sebesar $45\%$ dalam waktu 24 jam, padahal tidak ada insiden kebocoran data atau serangan siber nyata yang terjadi di level core-banking.
   - **Langkah investigasi dan perbaikan sistem**:
     - A. Hapus langsung seluruh transaksi yang dianggap outlier dari database.
     - B. Periksa kemungkinan terjadinya *Covariate Shift / Feature Drift* pada ruang input (misal ada peluncuran metode pembayaran baru atau perubahan format mata uang) dengan membandingkan distribusi data mentah menggunakan uji Kolmogorov-Smirnov atau Wasserstein Distance; jika terbukti ada fitur baru, perbarui pipeline transformasi dan jalankan retrain inkremental pada representasi laten.
     - C. Naikkan parameter `min_cluster_size` menjadi 10.000 untuk mematikan notifikasi alert.
     - D. Restart server Redis yang melayani model.
   *Jawaban yang benar*: **B**.

---

### 16. Summary
- Reduksi dimensi linier tingkat produksi bertumpu pada dekomposisi berbasis **SVD**; **Incremental PCA** adalah pola standar industri untuk data masif yang tidak muat dalam memori (*out-of-core*).
- Reduksi dimensi non-linier seperti **UMAP** menjaga sifat topologi lokal dan global dengan meminimalkan *fuzzy set cross-entropy*. Untuk kebutuhan inferensi skala besar real-time berlatensi rendah, gunakan varian parametrik (**Parametric UMAP/Autoencoder**) yang dapat dikonversi ke **ONNX**.
- **Kutukan Dimensi** (*Curse of Dimensionality*) merusak metrik jarak pada algoritma klasterisasi berbasis densitas. Pipeline enterprise yang teruji selalu mereduksi dimensi data terlebih dahulu sebelum mengeksekusi **HDBSCAN**.
- Di lingkungan produksi, sistem *unsupervised* memerlukan observabilitas berkelanjutan terhadap **Latent Space Drift** guna menjamin invariansi representasi terhadap pergeseran distribusi data nyata.