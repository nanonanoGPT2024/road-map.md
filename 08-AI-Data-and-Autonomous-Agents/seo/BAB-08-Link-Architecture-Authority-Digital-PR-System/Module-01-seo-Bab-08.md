# Bab 08: Link Architecture, Authority & Digital PR Systems
## Module 01: Algoritma Internal Link Graph, Simulasi PageRank Terdistribusi, dan Semantic Authority Vectorization

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memodelkan** topologi tautan internal situs web berskala enterprise ($>10^6$ URL) sebagai directed graph $G = (V, E)$ menggunakan representasi sparse matrix.
- **Mengimplementasikan dan Menghitung** distribusi *link equity* menggunakan algoritma Power Iteration PageRank yang dimodifikasi dengan penanganan *dangling nodes* dan *rank sinks*.
- **Mengintegrasikan** *Topic-Sensitive PageRank* dan *Semantic Authority Vectorization* berbasis dense embeddings untuk mengevaluasi relevansi kontekstual antara simpul sumber (*source node*) dan simpul target (*target node*).
- **Mendeteksi dan Memitigasi** anomali arsitektur tautan seperti *link orphan*, *spider traps*, dan *equity leakage* secara terprogram.
- **Membangun** *Production-Ready Link Optimization Pipeline* yang merekomendasikan penambahan edge internal link secara deterministik untuk memaksimalkan *crawl efficiency* dan distribusi otoritas halaman prioritas bisnis.

---

### 2. Concept Overview

Arsitektur tautan internal pada dasarnya adalah sistem distribusi probabilitas. Mesin pencari modern tidak memperlakukan tautan sekadar sebagai rujukan navigasi HTML, melainkan sebagai transisi probabilistik dalam suatu rantai Markov terarah (*directed Markov chain*).

```
[Simpul A] --(out-degree: 2)--> [Simpul B (Target Transaksional)]
    |                               ^
    +-------> [Simpul C] -----------+
```

#### The Random Surfer vs. Reasonable Surfer Model
1. **Random Surfer Model (Brin & Page, 1998):**
   Model mengasumsikan seorang peselancar web memilih tautan keluar (*outbound links*) secara seragam (*uniform distribution*) dengan probabilitas $d$ (*damping factor*, umumnya bernilai $0.85$), atau melompat (*teleport*) ke halaman acak mana pun dalam graf dengan probabilitas $(1 - d)$.
2. **Reasonable Surfer Model (Google Patent US7716225B1):**
   Probabilitas transisi antar simpul tidak lagi didistribusikan secara seragam. Bobot transisi dipengaruhi oleh fitur struktural dan kontekstual: posisi elemen DOM, visibilitas viewport, semantik anchor text, relevansi topikal antar-dokumen, dan intensi pengguna.

#### Semantic Authority Vectorization
Otoritas halaman (*Page Authority*) tidak bersifat agnostik terhadap topik. Dengan mengkombinasikan formulasi **Topic-Sensitive PageRank (Haveliwala)** dan representasi vektor berdimensi tinggi (*dense vector embeddings*), kita dapat membatasi perpindahan otoritas hanya pada simpul-simpul yang berada dalam subspace semantik yang koheren. Hal ini mencegah devaluasi otoritas akibat manipulasi tautan internal yang tidak relevan secara kontekstual.

---

### 3. Why It Matters

Pada arsitektur situs web berskala puluhan ribu hingga jutaan URL (e-commerce, agregator real estate, portal media berita), arsitektur tautan internal yang tidak terstruktur menyebabkan tiga masalah kritis:

1. **Crawl Budget Exhaustion:** Mesin pencari menghabiskan alokasi perayapan (*crawl budget*) pada halaman berprioritas rendah (misalnya halaman filter faceted navigation) karena menerima akumulasi link equity tinggi secara tidak sengaja melalui footer/header global.
2. **Authority Dilution (Penyusutan Otoritas):** Halaman konversi utama (*money pages*) terkubur di kedalaman klik (*click-depth*) $> 4$, terisolasi dari *seed pages* yang memiliki otoritas eksternal tinggi (misalnya beranda atau artikel viral).
3. **Cannibalization & Semantic Drift:** Distribusi anchor text yang acak dan tidak terarah membingungkan representasi entitas mesin pencari terhadap dokumen target, memicu kanibalisasi kata kunci dan penurunan ranking organik.

Menguasai link graph engineering memungkinkan insinyur SEO memanipulasi aliran PageRank secara matematis, mengoptimalkan perayapan bot, dan mengangkat peringkat halaman transaksional tanpa bergantung sepenuhnya pada akuisisi *backlink* eksternal.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur sistem pengolahan link graph internal berskala produksi, mulai dari ekstraksi crawl data hingga kalkulasi PageRank dan rekomendasi edge baru:

```
+-----------------------------------------------------------------------------------+
|                        INTERNAL LINK GRAPH ENGINE ARCHITECTURE                    |
+-----------------------------------------------------------------------------------+

 [ Ingestion Layer ]
         |
         v
 +---------------+      +------------------+      +-------------------+
 |  HTML Parser  | ---> |  DOM Link Gater  | ---> | Link Record Store |
 | (Edge Extr.)  |      | (Filter NoFollow)|      |   (PostgreSQL)    |
 +---------------+      +------------------+      +-------------------+
                                                            |
                                                            v
 [ Graph Construction & Transformation ]          +-------------------+
         |                                        | Graph Adjacency   |
         +--------------------------------------> | Matrix Builder    |
                                                  +-------------------+
                                                            |
 [ Computation & Intelligence Layer ]                       v
         +--------------------------------------------------+
         |                                                  |
         v                                                  v
 +-----------------------+                        +-------------------+
 | Power Iteration Engine|                        | Text Embeddings   |
 | (SciPy Sparse Matrix) |                        | (all-MiniLM-L6-v2)|
 +-----------------------+                        +-------------------+
         |                                                  |
         v                                                  v
 +-----------------------+                        +-------------------+
 | Topological PageRank  |                        | Document Vectors  |
 | Score Vectors         |                        | (FAISS Index)     |
 +-----------------------+                        +-------------------+
         |                                                  |
         +------------------------+-------------------------+
                                  |
                                  v
 [ Optimization & Execution Layer ]
         |
         v
 +--------------------------------------------------------------------+
 | Link Opportunity Engine (Topological Deficit x Semantic Cosine)     |
 +--------------------------------------------------------------------+
         |
         v
 +--------------------------------------------------------------------+
 | Automated CMS Internal Link Injector (Direct Injection / PR Queue) |
 +--------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Formulasi Matematis PageRank

Diberikan sebuah directed graph $G = (V, E)$, di mana $V$ merepresentasikan himpunan URL (simpul) dengan kardinalitas $|V| = N$, dan $E$ adalah himpunan tautan berarah (edge).

Matriks stokastik $M \in \mathbb{R}^{N \times N}$ merepresentasikan probabilitas transisi. Elemen $M_{ij}$ bernilai:
$$M_{ij} = \begin{cases} \frac{1}{L(p_j)}, & \text{jika } (p_j, p_i) \in E \\ 0, & \text{lainnya} \end{cases}$$
di mana $L(p_j)$ adalah *out-degree* simpul $p_j$.

Untuk mengatasi *dangling nodes* (simpul dengan $L(p_j) = 0$), vektor kolom nol digantikan dengan distribusi uniform $\frac{\mathbf{1}}{N}$.

Formulasi iteratif PageRank dengan *damping factor* $d \in (0, 1)$ dinyatakan sebagai:
$$\mathbf{r}^{(k+1)} = d \cdot M \mathbf{r}^{(k)} + \frac{1 - d + d \sum_{j \in \mathcal{D}} r_j^{(k)}}{N} \mathbf{1}$$
di mana:
- $\mathbf{r}^{(k)}$ adalah vektor distribusi probabilitas PageRank pada iterasi ke-$k$.
- $\mathcal{D}$ adalah himpunan *dangling nodes*.
- $\mathbf{1}$ adalah vektor satuan berukuran $N \times 1$.

Kriteria konvergensi tercapai ketika norma Euclidean selisih vektor berada di bawah ambang batas toleransi $\epsilon$:
$$\|\mathbf{r}^{(k+1)} - \mathbf{r}^{(k)}\|_1 < \epsilon \quad (\text{biasanya } \epsilon = 10^{-6})$$

#### 5.2 Topic-Sensitive PageRank (Semantic Personalization)

Dalam *Topic-Sensitive PageRank*, vektor personalisasi seragam $\frac{\mathbf{1}}{N}$ digantikan oleh vektor bias preferensial $\mathbf{v}$ yang merepresentasikan distribusi topik dari suatu klaster:
$$\mathbf{r}^{(k+1)} = d \cdot M \mathbf{r}^{(k)} + (1 - d) \mathbf{v}$$
di mana $\sum_{i=1}^N v_i = 1$. Jika halaman $i$ berkorelasi kuat dengan topik target, maka bobot $v_i$ ditingkatkan.

#### 5.3 Semantic Authority Affinity Score

Untuk menentukan kelayakan pembuatan edge baru antara simpul $u$ dan simpul $v$, kita mendefinisikan *Affinity Score* $\mathcal{A}(u, v)$:
$$\mathcal{A}(u, v) = \text{CosineSimilarity}(\mathbf{e}_u, \mathbf{e}_v) \times \left(1 - \frac{\text{PR}(v)}{\max(\mathbf{PR})}\right) \times \text{DistancePenalizer}(u, v)$$
di mana:
- $\mathbf{e}_u, \mathbf{e}_v$ adalah *dense embeddings* (misal: vector berdimensi 384 dari *sentence-transformers*) dari konten teks simpul $u$ dan $v$.
- $\text{DistancePenalizer}(u, v) = \frac{1}{\text{ShortestPath}(u, v)}$ menghukum simpul yang sudah memiliki jarak struktural terlalu dekat.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.11+ tingkat produksi menggunakan `scipy.sparse`, `numpy`, dan `dataclasses`. Modul ini mengonstruksi graf tautan, mengeksekusi Power Iteration PageRank, mengukur *leakage*, dan menghasilkan rekomendasi tautan internal baru berbasis semantik.

```python
"""
Internal Link Architecture Engine & PageRank Simulation
Production-grade system for calculating PageRank and Semantic Link Insertion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
from numpy.typing import NDArray
from scipy.sparse import csc_matrix, eye
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LinkArchitectureEngine")


@dataclass(frozen=True)
class WebPageNode:
    """Representasi immutable simpul halaman dalam link graph."""
    node_id: int
    url: str
    business_priority: float  # Skala 0.0 sampai 1.0
    embedding: NDArray[np.float64] = field(repr=False)


@dataclass
class EdgeRecommendation:
    """Hasil rekomendasi penambahan internal link."""
    source_url: str
    target_url: str
    semantic_similarity: float
    target_current_pagerank: float
    expected_impact_score: float


class PageRankEngine:
    """
    Simulasi PageRank berbasis Sparse Transition Matrix.
    Mendukung dangling node correction dan topic-sensitive personalization.
    """

    def __init__(self, damping_factor: float = 0.85, max_iterations: int = 200, tolerance: float = 1e-7) -> None:
        self.damping_factor = damping_factor
        self.max_iterations = max_iterations
        self.tolerance = tolerance

    def compute_pagerank(
        self,
        adjacency_matrix: csc_matrix,
        personalization_vector: Optional[NDArray[np.float64]] = None
    ) -> NDArray[np.float64]:
        """
        Menghitung PageRank vector menggunakan Power Iteration Method.
        
        Args:
            adjacency_matrix: Sparse binary matrix (csc_matrix) ukuran (N, N),
                              di mana adj[j, i] = 1 menandakan link dari i ke j.
            personalization_vector: Vektor preferensial sum(v) == 1. Jika None, uniform distribution.

        Returns:
            Vektor distribusi probabilitas PageRank ukuran (N,).
        """
        num_nodes: int = adjacency_matrix.shape[0]
        if num_nodes == 0:
            raise ValueError("Matriks ketetanggaan kosong (0 simpul).")

        # Inisialisasi vektor personalisasi
        if personalization_vector is None:
            teleport: NDArray[np.float64] = np.ones(num_nodes, dtype=np.float64) / num_nodes
        else:
            if not np.isclose(np.sum(personalization_vector), 1.0):
                raise ValueError("Personalization vector harus terdistribusi probabilitas (sum == 1.0).")
            teleport = personalization_vector.copy()

        # Hitung out-degree untuk setiap simpul (penjumlahan per kolom)
        out_degrees: NDArray[np.float64] = np.array(adjacency_matrix.sum(axis=0)).flatten()
        
        # Identifikasi dangling nodes (simpul tanpa out-link)
        dangling_mask: NDArray[np.bool_] = (out_degrees == 0)
        
        # Normalisasi kolom untuk membentuk Stochastic Matrix M
        with np.errstate(divide="ignore", invalid="ignore"):
            norm_factors: NDArray[np.float64] = np.where(out_degrees > 0, 1.0 / out_degrees, 0.0)
        
        # Bentuk Matriks Probabilitas Transisi Transpos M
        scaling_matrix = csc_matrix((norm_factors, (np.arange(num_nodes), np.arange(num_nodes))), shape=(num_nodes, num_nodes))
        stochastic_transition_matrix = adjacency_matrix.dot(scaling_matrix)

        # Inisialisasi PageRank uniform
        rank_vector: NDArray[np.float64] = np.ones(num_nodes, dtype=np.float64) / num_nodes

        logger.info(f"Memulai Power Iteration: {num_nodes} simpul, {adjacency_matrix.nnz} edges.")

        for iteration in range(self.max_iterations):
            previous_rank = rank_vector.copy()

            # Hitung PageRank dari dangling nodes yang didistribusikan via teleportation
            dangling_sum: float = float(np.sum(previous_rank[dangling_mask]))

            # Power Step: r_next = d * M * r + (d * dangling_sum + (1 - d)) * teleport
            rank_vector = (
                self.damping_factor * (stochastic_transition_matrix.dot(previous_rank))
                + (self.damping_factor * dangling_sum + (1.0 - self.damping_factor)) * teleport
            )

            # Hitung konvergensi via L1-norm
            l1_error: float = float(np.sum(np.abs(rank_vector - previous_rank)))
            if l1_error < self.tolerance:
                logger.info(f"PageRank konvergen pada iterasi ke-{iteration + 1} dengan error: {l1_error:.2e}")
                return rank_vector

        logger.warning("Peringatan: Power Iteration mencapai batas maksimum iterasi sebelum konvergen secara penuh.")
        return rank_vector


class LinkGraphManager:
    """Pengelola topologi link graf, deteksi anomali, dan semantic link optimization."""

    def __init__(self, damping_factor: float = 0.85) -> None:
        self.nodes: Dict[int, WebPageNode] = {}
        self.url_to_id: Dict[str, int] = {}
        self.edges: Set[Tuple[int, int]] = set()  # Tuple: (source_id, target_id)
        self.pagerank_engine = PageRankEngine(damping_factor=damping_factor)

    def register_page(self, url: str, business_priority: float, embedding: NDArray[np.float64]) -> int:
        """Mendaftarkan halaman baru ke dalam graph registry."""
        if url in self.url_to_id:
            return self.url_to_id[url]

        node_id = len(self.nodes)
        node = WebPageNode(node_id=node_id, url=url, business_priority=business_priority, embedding=embedding)
        self.nodes[node_id] = node
        self.url_to_id[url] = node_id
        return node_id

    def add_link(self, source_url: str, target_url: str) -> None:
        """Menambahkan directed edge internal link antara source dan target."""
        if source_url not in self.url_to_id or target_url not in self.url_to_id:
            raise KeyError("Source URL atau Target URL belum terdaftar dalam nodes.")

        src_id = self.url_to_id[source_url]
        tgt_id = self.url_to_id[target_url]

        if src_id != tgt_id:  # Menghindari self-loops
            self.edges.add((src_id, tgt_id))

    def _build_adjacency_matrix(self) -> csc_matrix:
        """Membangun Scipy CSC sparse matrix di mana M[target, source] = 1."""
        num_nodes = len(self.nodes)
        if not self.edges:
            return csc_matrix((num_nodes, num_nodes), dtype=np.float64)

        target_indices, source_indices = zip(*self.edges)
        data = np.ones(len(self.edges), dtype=np.float64)

        return csc_matrix((data, (target_indices, source_indices)), shape=(num_nodes, num_nodes), dtype=np.float64)

    def analyze_link_structure(self) -> Tuple[NDArray[np.float64], List[str]]:
        """
        Mengeksekusi simulasi PageRank dan mengidentifikasi Orphan Nodes.
        
        Returns:
            Tuple (Vektor PageRank, List Orphan URLs)
        """
        adj_matrix = self._build_adjacency_matrix()
        pagerank_scores = self.pagerank_engine.compute_pagerank(adj_matrix)

        # In-degree adalah penjumlahan per baris pada matriks ketetanggaan
        in_degrees: NDArray[np.int32] = np.array(adj_matrix.sum(axis=1)).flatten()
        orphan_urls = [
            self.nodes[node_id].url 
            for node_id, in_deg in enumerate(in_degrees) 
            if in_deg == 0
        ]

        return pagerank_scores, orphan_urls

    def generate_optimized_links(
        self, 
        pagerank_scores: NDArray[np.float64], 
        min_semantic_threshold: float = 0.70, 
        top_k: int = 5
    ) -> List[EdgeRecommendation]:
        """
        Menghasilkan rekomendasi penambahan internal link untuk halaman dengan PageRank rendah
        tetapi memiliki nilai business_priority tinggi, bersumber dari simpul otoritatif dan semantik yang cocok.
        """
        recommendations: List[EdgeRecommendation] = []
        max_pr = np.max(pagerank_scores) if np.max(pagerank_scores) > 0 else 1.0

        # Cari kandidat target (Priority tinggi tapi PR rendah)
        target_candidates = [
            node for node in self.nodes.values()
            if node.business_priority >= 0.7 and (pagerank_scores[node.node_id] / max_pr) < 0.4
        ]

        # Cari simpul authority tinggi sebagai sumber
        source_candidates = [
            node for node in self.nodes.values()
            if (pagerank_scores[node.node_id] / max_pr) >= 0.6
        ]

        for target in target_candidates:
            for source in source_candidates:
                if source.node_id == target.node_id:
                    continue

                # Cek jika edge sudah ada sebelumnya
                if (source.node_id, target.node_id) in self.edges:
                    continue

                # Hitung Semantic Similarity (Cosine)
                sim = float(
                    cosine_similarity(
                        source.embedding.reshape(1, -1), 
                        target.embedding.reshape(1, -1)
                    )[0][0]
                )

                if sim >= min_semantic_threshold:
                    # PageRank deficit target
                    pr_deficit = 1.0 - (pagerank_scores[target.node_id] / max_pr)
                    
                    # Impact score: kombinasi kecocokan semantik, business priority target, dan deficit
                    impact = sim * target.business_priority * pr_deficit

                    recommendations.append(
                        EdgeRecommendation(
                            source_url=source.url,
                            target_url=target.url,
                            semantic_similarity=round(sim, 4),
                            target_current_pagerank=float(pagerank_scores[target.node_id]),
                            expected_impact_score=round(impact, 4),
                        )
                    )

        # Sort descending berdasarkan expected_impact_score
        recommendations.sort(key=lambda rec: rec.expected_impact_score, reverse=True)
        return recommendations[:top_k]


# =====================================================================
# Pipeline Execution & Validation
# =====================================================================
if __name__ == "__main__":
    np.random.seed(42)
    manager = LinkGraphManager(damping_factor=0.85)

    # Inisialisasi Mock Nodes dengan Dimensi Vektor Semantik (dim=4 untuk contoh)
    urls_data = [
        ("https://example.com/", 1.0, np.array([0.9, 0.1, 0.2, 0.1])),
        ("https://example.com/blog/python-seo", 0.5, np.array([0.1, 0.85, 0.7, 0.2])),
        ("https://example.com/blog/data-science", 0.4, np.array([0.2, 0.80, 0.75, 0.1])),
        ("https://example.com/software/enterprise-seo-tool", 0.95, np.array([0.15, 0.88, 0.65, 0.3])),  # Target Transaksional
        ("https://example.com/about-us", 0.2, np.array([0.1, 0.05, 0.1, 0.9])),
    ]

    for url, priority, emb in urls_data:
        manager.register_page(url=url, business_priority=priority, embedding=emb)

    # Inisialisasi Initial Edges (Simulasi Struktur Navigasi Standar)
    initial_links = [
        ("https://example.com/", "https://example.com/blog/python-seo"),
        ("https://example.com/", "https://example.com/about-us"),
        ("https://example.com/blog/python-seo", "https://example.com/blog/data-science"),
        ("https://example.com/blog/data-science", "https://example.com/"),  # Return loop
        ("https://example.com/about-us", "https://example.com/"),
    ]

    for src, tgt in initial_links:
        manager.add_link(src, tgt)

    # 1. Jalankan Analisis PageRank Awal
    pr_results, orphans = manager.analyze_link_structure()

    print("\n--- DISTRIBUSI PAGERANK AWAL ---")
    for node_id, pr in enumerate(pr_results):
        print(f"URL: {manager.nodes[node_id].url:<50} | PageRank: {pr:.6f}")

    print(f"\nOrphan Pages Terdeteksi ({len(orphans)}): {orphans}")

    # 2. Rekomendasikan Link Baru untuk Mengangkat Halaman Prioritas
    recommendations = manager.generate_optimized_links(pr_results, min_semantic_threshold=0.8, top_k=3)

    print("\n--- REKOMENDASI PENAMBAHAN EDGE (SEMANTIC GATED) ---")
    for idx, rec in enumerate(recommendations, 1):
        print(f"#{idx} Hubungkan: {rec.source_url} -> {rec.target_url}")
        print(f"   Similarity: {rec.semantic_similarity} | Target Current PR: {rec.target_current_pagerank:.6f} | Score: {rec.expected_impact_score}\n")
```

---

### 7. Edge Cases & Failure Modes

Dalam lingkungan enterprise, manipulasi graf tautan dapat memicu anomali struktural berikut:

1. **Dead-End / Dangling Nodes (Zero Out-Degree):**
   - *Penyebab:* Halaman konversi akhir, file PDF, atau halaman non-HTML yang tidak memiliki tautan internal keluar sama sekali.
   - *Dampak:* Matriks menjadi non-stokastik; PageRank bocor (*rank loss*) dari jaringan.
   - *Mitigasi:* Mengalokasikan nilai transisi dangling node secara eksplisit ke seluruh elemen vektor personalisasi pada setiap iterasi perkalian matriks (diimplementasikan via `dangling_sum * teleport`).

2. **Spider Traps / Infinite Loops (Cyclic Sinks):**
   - *Penyebab:* Modul navigasi faceted tanpa filter kanonikal yang valid (misalnya: filter harga atau sortir tak terbatas: `?sort=asc&page=2` $\leftrightarrow$ `?sort=desc&page=2`).
   - *Dampak:* Seluruh equity graf tersedot ke dalam cluster siklik tertutup (*absorbing Markov chain component*).
   - *Mitigasi:* Nilai damping factor $d = 0.85$ menjamin konvergensi karena surfer selalu memiliki probabilitas $15\%$ untuk teleportasi keluar dari trap. Gunakan sanitasi URL berbasis parameter stripping sebelum pembentukan adjacency matrix.

3. **Graph Disconnection (Unreachable Subgraphs):**
   - *Penyebab:* Penggunaan taksonomi baru tanpa integrasi ke sitemap utama atau modul menu navigasi.
   - *Dampak:* Subgraf memiliki nilai PageRank minimal $(1 - d) / N$, sehingga mesin pencari menurunkan frekuensi perayapan (*crawl recrawl rate*).
   - *Mitigasi:* Algoritma deteksi *Weakly Connected Components (WCC)* menggunakan disjoint-set (*Union-Find*) untuk mendeteksi partisi graf yang terisolasi dari simpul akar (*root node*).

4. **Matrix Sparsity Memory Blowup:**
   - *Penyebab:* Menyimpan matriks $N \times N$ secara dense untuk $N = 1.000.000$ halaman membutuhkan memori RAM sebesar:
     $$10^6 \times 10^6 \times 8 \text{ bytes} \approx 8 \text{ Terabytes}$$
   - *Mitigasi:* Wajib menggunakan representasi `scipy.sparse.csc_matrix` atau `scipy.sparse.csr_matrix` yang hanya menyimpan edge aktif. Kompleksitas memori tereduksi menjadi $O(|V| + |E|)$.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter / Pendekatan | Power Iteration Method | Monte Carlo Random Walk Simulation | Topological Matrix Inversion $(I - dM)^{-1}$ |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Komputasi** | $O(k \cdot |E|)$, di mana $k \approx 30\text{-}50$ iterasi | $O(M \cdot L)$, di mana $M$ adalah jumlah walks, $L$ panjang path | $O(N^3)$ (Secara umum tidak realistis untuk $N > 10.000$) |
| **Akurasi Hasil** | Deterministik hingga batas presisi toleransi $\epsilon$ | Stokastik (Aproksimasi berbasis sampling empiris) | Sangat presisi (Eksak matematis) |
| **Kebutuhan Memori** | Rendah: $O(|V| + |E|)$ melalui Sparse CSC | Sangat Rendah: Hanya menyimpan graf dan tracker walk | Sangat Tinggi: Inversi sparse matrix sering kali menghasilkan representasi dense |
| **Dynamic Updates** | Memerlukan komputasi ulang (kecuali menggunakan warm-start) | Mudah dilakukan update inkremental lokal | Wajib inversi ulang secara komparatif |
| **Use Case Terbaik** | **Batch enterprise calculation offline mingguan/bulanan** | **Real-time approximate link equity tracking pada stream data** | **Analisis teoretis pada klaster graf berukuran mikro ($< 5.000$ URL)** |

---

### 9. Best Practices & Standar Industri

1. **Click-Depth Constraint:** Arsitektur tautan internal harus memastikan semua *money pages* transaksional berada pada kedalaman klik maksimal $\le 3$ dari simpul beranda (*homepage seed*).
2. **Deterministic Anchor Text Differentiation:** Hindari generic anchor text ("klik di sini", "baca selengkapnya"). Gunakan variasi deskriptif yang mencerminkan target entity name untuk menghindari sinyal spam internal.
3. **Internal Link Gating:**
   - Jangan gunakan `rel="nofollow"` untuk arsitektur internal. Praktik ini menghancurkan PageRank (*equity drop*) alih-alih mengarahkannya ke halaman lain, karena Google tetap memotong bobot out-degree tautan tersebut tanpa meneruskannya.
   - Singkirkan tautan struktural ke halaman utility (halaman login, terms of service, keranjang) dari body content utama, alihkan ke elemen footer dengan relasi transaksional bersih atau muat via dynamic rendering jika mutlak tidak perlu diindeks.
4. **Hub-and-Spoke Topology (Topic Cluster):**
   - Halaman pilar (*Pillar Page*) wajib memiliki tautan dwiarah (*bi-directional*) ke sub-halaman pendukung (*Spoke Pages*).
   - Setiap sub-halaman pendukung (*Spoke Page*) harus memiliki *lateral link* ke halaman sub-topik tetangga yang relevan dan satu *upward link* mengarah kembali ke halaman pilar. Hindari link silang tak terstruktur ke klaster topik lain tanpa relevansi semantik tinggi ($< 0.70$ cosine affinity).

---

### 10. Hands-on Lab Exercise

#### Skenario:
Sebuah portal e-commerce mengalami masalah: Halaman kategori transaksional utama (`/category/enterprise-laptops`) kehilangan ranking organik. Anda ditugaskan merekayasa link graph untuk mentransfer equity dari blog post berkinerja tinggi ke halaman kategori ini menggunakan sistem simulasi internal link.

#### Langkah Praktikum:

1. **Langkah 1: Setup Environment**
   Pastikan dependensi telah terinstal di virtual environment Anda:
   ```bash
   pip install numpy scipy scikit-learn
   ```

2. **Langkah 2: Eksekusi Skrip Uji**
   Jalankan skrip di bawah ini untuk melihat pergeseran link equity sebelum dan sesudah optimasi edge.

```python
"""
Lab: PageRank Injection Simulation for Transactional Targets
"""

import numpy as np
from scipy.sparse import csc_matrix

def run_lab():
    # 0: Home, 1: High Authority Blog, 2: Low Authority Blog, 3: Transactional Category
    pages = ["Home", "Blog A (Viral)", "Blog B", "Target: Category Page"]
    n = len(pages)

    # Base Matrix (Tanpa link dari Blog Viral ke Category)
    # Edge: Home -> Blog A, Home -> Blog B, Blog A -> Home, Blog B -> Home
    edges_base = [(0, 1), (0, 2), (1, 0), (2, 0)]
    
    def calc_pr(edges):
        targets, sources = zip(*edges)
        adj = csc_matrix((np.ones(len(edges)), (targets, sources)), shape=(n, n))
        out_deg = np.array(adj.sum(axis=0)).flatten()
        norm = np.where(out_deg > 0, 1.0 / out_deg, 0.0)
        M = adj.dot(csc_matrix((norm, (np.arange(n), np.arange(n))), shape=(n, n)))
        
        pr = np.ones(n) / n
        d = 0.85
        for _ in range(100):
            dangling = float(np.sum(pr[out_deg == 0]))
            pr = d * (M.dot(pr)) + (d * dangling + (1.0 - d)) * (np.ones(n) / n)
        return pr

    pr_initial = calc_pr(edges_base)
    print("=== BASE STATE: TARGET IS ORPHAN ===")
    for idx, p in enumerate(pages):
        print(f"{p:<25}: {pr_initial[idx]:.5f}")

    # Optimasi: Menambahkan contextual contextual link dari Blog Viral (1) -> Category Page (3)
    # Ditambah link dari Category Page (3) -> Home (0) untuk sirkulasi equity
    edges_optimized = edges_base + [(1, 3), (3, 0)]
    pr_optimized = calc_pr(edges_optimized)

    print("\n=== OPTIMIZED STATE: LINK INJECTED FROM BLOG A ===")
    for idx, p in enumerate(pages):
        delta = ((pr_optimized[idx] - pr_initial[idx]) / pr_initial[idx]) * 100
        print(f"{p:<25}: {pr_optimized[idx]:.5f} ({delta:+.2f}%)")

if __name__ == "__main__":
    run_lab()
```

3. **Verifikasi Output & Analisis:**
   - Amati persentase kenaikan (*% gain*) PageRank pada simpul `Target: Category Page`.
   - Analisis apakah penambahan edge keluar dari `Blog A (Viral)` menurunkan otoritas `Home` secara drastis atau justru menstabilkan distribusi graf secara sistemik. Modifikasi parameter tautan untuk mengevaluasi dampaknya.