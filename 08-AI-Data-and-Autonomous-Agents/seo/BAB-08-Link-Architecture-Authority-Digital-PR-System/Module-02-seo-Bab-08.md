# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 08: Link Architecture, Authority & Digital PR System**
**Kategori: 08-AI-Data-and-Autonomous-Agents (SEO Engine Engineering)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang dan Mengimplementasikan Directed Link Graph Engine**: Membangun topologi internal linking berbasis *Semantic Topic Clusters* dan *Silo Architecture* berskala enterprise (>10 juta node URL).
- **Menguasai Kalkulasi Mathematical Authority**: Mengimplementasikan algoritma varian PageRank (Weighted PageRank, Personalized PageRank, dan CheiRank) yang diinjeksi dengan pembobotan semantik (*cosine similarity* embedding konten).
- **Membangun Arsitektur Digital PR & Backlink Intelligence Otomatis**: Merekayasa pipeline autonomous ingestion, deteksi *unlinked brand mentions*, klasifikasi tautan toksik (PBN/spam) via Graph Neural Networks (GNN) dan model NLP Transformer.
- **Mengoptimalkan Distribusi Crawl Budget & Link Equity**: Menghilangkan fenomena *PageRank Leakage*, *Dangling Nodes*, dan *Spider Traps* menggunakan analisis spektral graf.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, Anda wajib menguasai:
- **Teori Graf Tingkat Lanjut**: Directed Acyclic Graph (DAG), Adjacency Matrix, Eigenvector Centrality, Random Walk Model, Markov Chains.
- **Komputasi Numerik & Distributed Data Processing**: Python (NumPy, SciPy Sparse Matrices, NetworkX), Apache Spark (GraphFrames), atau Rust.
- **Vector Embeddings & Semantic Search**: Pemahaman operasional terhadap transformer embeddings (e.g., `text-embedding-3-small`, BGE-M3) untuk menghitung bobot semantik tepi graf (*edge weights*).
- **Basis Data Graf**: Pengalaman praktis dengan Neo4j (Cypher Query Language) atau arsitektur graph traversal relasional (PostgreSQL CTE berulang).

---

## 3. Concept & Internal Architecture

### 3.1 Link Graph Theory & The Random Surfer Model
Struktur tautan web direpresentasikan sebagai graf berarah (*directed graph*) $G = (V, E)$, di mana $V$ adalah himpunan node (URL dokumen) dan $E$ adalah himpunan directed edges (hyperlink dari node sumber $u$ ke node target $v$).

Algoritma PageRank klasik memodelkan perilaku seorang penjelajah acak (*random surfer*) yang membuka halaman web dan mengeklik tautan yang tersedia secara seragam. Persamaan fundamental PageRank dirumuskan sebagai:

$$PR(u) = \frac{1 - d}{N} + d \sum_{v \in B_u} \frac{PR(v)}{L(v)}$$

Di mana:
- $u$: Halaman target yang dihitung nilainya.
- $B_u$: Himpunan semua halaman yang memiliki tautan menuju $u$ (in-links).
- $PR(v)$: Nilai PageRank dari halaman $v$.
- $L(v)$: Jumlah tautan keluar (*out-degree*) dari halaman $v$.
- $d$: Damping factor (secara empiris bernilai $0.85$), merepresentasikan probabilitas bahwa peselancar akan terus mengeklik tautan alih-alih melompat secara acak (*teleport*) ke halaman baru.
- $N$: Total jumlah node dalam graf web.

### 3.2 Weighted & Contextual PageRank Architecture
Pada sistem SEO enterprise modern dan algoritma search engine generasi terbaru, asumsi probabilitas seragam pada $L(v)$ tidak lagi valid. Model harus memperhitungkan faktor kontekstual:
1. **Posisi Elemen DOM**: Tautan dalam konten utama (`<main>` atau `<article>`) memiliki bobot atensi lebih tinggi dibandingkan tautan di `<footer>` atau `<nav>`.
2. **Relevansi Semantik Teks**: Kedekatan kosinus vektor antara embedding dokumen sumber $\vec{E}_v$ dan dokumen target $\vec{E}_u$.
3. **Anchor Text Relevance**: Kecocokan kontekstual teks tautan dengan entitas dokumen target.

$$W_{(v, u)} = \alpha \cdot \text{CosineSim}(\vec{E}_v, \vec{E}_u) + \beta \cdot \text{DOM\_Weight}(e) + \gamma \cdot \text{AnchorRelevance}(e)$$

Distribusi PageRank tertimbang (*Weighted PageRank*) kemudian diformulasikan ulang menjadi:

$$PR(u) = \frac{1 - d}{N} + d \sum_{v \in B_u} PR(v) \cdot \frac{W_{(v, u)}}{\sum_{k \in Out(v)} W_{(v, k)}}$$

### 3.3 Penanganan Masalah Matriks Graf: Dangling Nodes & Nilai Spektral
Dalam sistem skala besar, representasi graf diwujudkan dalam *Stochastic Transition Matrix* $M$.
- **Dangling Nodes**: Node tanpa out-degree ($L(v) = 0$). Menyebabkan hilangnya probabilitas (*leaking PageRank*) dari sistem selama iterasi perkalian matriks vektor. Penanganannya adalah dengan mengganti baris bernilai nol dengan distribusi seragam $1/N$ (merepresentasikan teleportasi acak murni).
- **Convergence Rate**: Konvergensi iterasi daya (*power iteration*) ditentukan oleh *second eigenvalue* ($\lambda_2$) dari matriks transisi. Semakin kecil nilai $\lambda_2$, semakin cepat sistem konvergen ke kondisi stasioner (*steady-state vector*).

```
+-----------------------------------------------------------------------------------+
|                         ENTERPRISE LINK ENGINE ARCHITECTURE                       |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ Content Corpus / Ingestion Engine ]                                            |
|              |                                                                    |
|              v                                                                    |
|  [ Semantic Embedding Pipeline ] ----> Vector Similarity Engine                   |
|              |                                   |                                |
|              v                                   v                                |
|  [ DOM/HTML Parser Engine ] -----> Edge Extractor & Weight Assignor                |
|                                                  |                                |
|                                                  v                                |
|                                   [ Directed Graph Constructor ]                  |
|                                                  |                                |
|       +------------------------------------------+----------------------------+   |
|       |                                                                       |   |
|       v                                                                       v   |
|  [ Internal Link Topology Engine ]                       [ External PR / Backlink]|
|  - Topic Cluster & Silo Guard                            - Ingestion Crawler      |
|  - PageRank Dilution Detector                            - Domain Authority Calc  |
|  - Orphan Node Resolver                                  - Toxic Link Anomaly GNN |
|       |                                                                       |   |
|       +------------------------------------------+----------------------------+   |
|                                                  |                                |
|                                                  v                                |
|                                  [ Sparse Matrix Solver (SciPy / Spark) ]         |
|                                                  |                                |
|                                                  v                                |
|                             [ Power Iteration / Weighted PageRank ]               |
|                                                  |                                |
|                                                  v                                |
|                             [ Dynamic Link Injection / Disavow Output ]           |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why & What

### Mengapa Perlu Link Architecture Engine Berskala Enterprise?
1. **Link Equity Dilution**: Platform e-commerce dengan jutaan halaman produk sering kali menyalurkan PageRank ke halaman non-prioritas (misal: halaman kebijakan privasi, syarat ketentuan, faceted filters tak berujung) daripada ke halaman transaksi bernilai tinggi.
2. **Algoritma Relevansi Semantik Terkini**: Mesin pencari modern tidak lagi sekadar menghitung kuantitas backlink, melainkan membangun *topical authority* berbasis graf. Tautan tanpa kedekatan semantik dapat didiskualifikasi oleh algoritma anti-manipulasi.
3. **Optimasi Crawl Budget**: Mengurangi kedalaman klik (*crawl depth*) node prioritas dari beranda menjadi $\le 3$ hops melalui injeksi tautan internal yang dihitung secara matematis.

### Apa yang Dibangun?
Sistem komprehensif yang terdiri dari:
1. **Dynamic Internal Link Injection Engine**: Menganalisis konten baru, mencari node topik terkait melalui database vektor, dan menyisipkan tautan kontekstual secara terotomatisasi tanpa memicu kanibalisasi kata kunci.
2. **Topological Graph Health Monitor**: Mengidentifikasi *orphan pages*, *bottlenecks*, dan menghitung *Personalized PageRank* (PPR) internal.
3. **Digital PR & Backlink Risk Scorer**: Pipeline otomatis untuk memantau sitasi web, mengekstrak unlinked mentions, dan menganalisis profil risiko backlink menggunakan deteksi anomali distribusi in-link.

---

## 5. How (Workflow Detail)

1. **Graph Ingestion & Normalization**:
   - Crawler internal mengekstrak seluruh URL valid, kode status HTTP, kanonikal, direktif robots, dan hyperlink yang berada di dalam tag konten utama.
   - Eksternal crawler/API ingest data backlink (in-degree edges).

2. **Vector Space Ingestion**:
   - Konten teks dari setiap URL dikonversi menjadi high-dimensional dense vector embeddings ($D$-dimensi).
   - Indeks disimpan di HNSW (Hierarchical Navigable Small World) index.

3. **Edge Weight Calculation**:
   - Untuk setiap pasangan node $(u, v)$ yang terhubung, hitung $W_{(u, v)}$ berdasarkan posisi DOM, kemiripan semantik, dan kualitas entitas target.

4. **Sparse Matrix Compilation & Power Iteration**:
   - Bentuk matriks sparse *Compressed Sparse Column* (CSC) untuk optimasi operasi perkalian matriks-vektor.
   - Eksekusi algoritma *Power Iteration* hingga mencapai konvergensi residu:
     $$\|PR^{(k+1)} - PR^{(k)}\|_1 < \epsilon$$
     (di mana $\epsilon = 10^{-8}$).

5. **Decision & Execution Engine**:
   - **Internal**: Jika halaman penting memiliki $PR(u) < \text{threshold}$, picu *link-injection worker* untuk mencari node berotoritas tinggi dengan kemiripan semantik tinggi yang memiliki slot out-link bebas.
   - **Eksternal**: Jika terdeteksi *unlinked brand mention*, picu Autonomous Outreach Pipeline. Jika backlink terdeteksi berasal dari farm link/PBN, masukkan ke dalam *automated disavow candidate queue*.

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem Distribusi Air (Hydraulic Network Analogy)
Bayangkan arsitektur website sebagai sebuah jaringan pipa air bertingkat:
- **Homepage** adalah reservoir air utama dengan pasokan air (*link equity*) terbesar.
- **Internal links** adalah pipa-pipa air yang menghubungkan reservoir utama ke kolam-kolam penampungan di bawahnya (kategori), yang kemudian mengalirkan air ke wadah-wadah kecil (produk/artikel).
- **Dangling Nodes** adalah wadah tanpa saluran pembuangan: air masuk tetapi tidak bisa bersirkulasi kembali, menguap sia-sia.
- **PageRank Leakage** adalah kebocoran pipa menuju area tandus yang tidak ditanami pohon (halaman login, terms of service, filter tidak terindeks).
- **Semantic Weighting** adalah katup pintar: katup hanya membuka debit air maksimal jika jenis tanah penerima cocok dengan pH air yang dialirkan.

```
TOPOLOGI TOPIC CLUSTER DENGAN STRICT SILOING

                 [ PILLAR PAGE: /ai-agents/ ]  (Authority: High)
                        |             ^
             +----------+             +----------+
             |                                   |
             v                                   |
   [ SUB-TOPIC 1: /planning/ ]         [ SUB-TOPIC 2: /memory/ ]
         |           ^                       |           ^
         +-----+-----+                       +-----+-----+
               |                                   |
               v                                   v
   [ DETAIL: /re-act-framework/ ]      [ DETAIL: /episodic-buffer/ ]

  ================== ISOLATION BOUNDARY (CROSS-SILO) ==================
         X (Blocked Direct Cross Link without Contextual Semantic Validation)
  =====================================================================

   [ PILLAR PAGE 2: /database-scalability/ ]
         |
         v
   [ SUB-TOPIC: /sharding/ ]
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: Pure NumPy PageRank Solver
Contoh dasar implementasi algoritma Power Iteration PageRank dengan deteksi dangling nodes:

```python
import numpy as np

def basic_pagerank(
    adj_matrix: np.ndarray, 
    damping_factor: float = 0.85, 
    max_iterations: int = 100, 
    tolerance: float = 1e-6
) -> np.ndarray:
    """
    Kalkulasi PageRank standar menggunakan NumPy dense matrix.
    """
    n = adj_matrix.shape[0]
    
    # Deteksi out-degree tiap node
    out_degree = adj_matrix.sum(axis=1)
    
    # Bangun stochastic transition matrix
    M = np.zeros((n, n), dtype=float)
    for i in range(n):
        if out_degree[i] == 0:
            # Penanganan Dangling Node: distribusikan probabilitas secara seragam
            M[i, :] = 1.0 / n
        else:
            M[i, :] = adj_matrix[i, :] / out_degree[i]
            
    # Transpose agar perkalian menjadi M.T @ p
    M_transition = M.T
    
    # Inisialisasi vektor PageRank seragam
    p = np.full(n, 1.0 / n, dtype=float)
    teleport = np.full(n, (1.0 - damping_factor) / n, dtype=float)
    
    for iteration in range(max_iterations):
        p_next = damping_factor * np.dot(M_transition, p) + teleport
        error = np.linalg.norm(p_next - p, ord=1)
        p = p_next
        if error < tolerance:
            break
            
    return p

# Contoh graf 4 URL:
# 0 -> 1, 0 -> 2
# 1 -> 2
# 2 -> 0
# 3 -> 2 (Node 3 adalah dangling-ish / link donor)
graph = np.array([
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [1, 0, 0, 0],
    [0, 0, 1, 0]
], dtype=float)

ranks = basic_pagerank(graph)
for idx, score in enumerate(ranks):
    print(f"URL_{idx}: {score:.5f}")
```

### 7.2 Practical Example: Enterprise-Grade Semantic-Weighted Link Engine
Berikut adalah arsitektur produksi menggunakan SciPy Sparse Matrix, Pydantic, dan permodelan inferensi semantik.

```python
#!/usr/bin/env python3
"""
Enterprise Semantic-Weighted Link Engine.
Menggabungkan Graph Centrality dengan Relevansi Kosinus Embedding untuk
Optimalisasi Arsitektur Tautan Internal.
"""

from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, HttpUrl, Field
import numpy as np
import scipy.sparse as sp
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class DocumentNode(BaseModel):
    id: int
    url: str
    canonical_url: str
    semantic_embedding: List[float]
    crawl_depth: int = 0
    is_indexable: bool = True

class DirectedEdge(BaseModel):
    source_id: int
    target_id: int
    dom_weight: float = Field(default=1.0, ge=0.1, le=1.0) # 1.0 = Content, 0.2 = Footer

class LinkGraphPayload(BaseModel):
    nodes: List[DocumentNode]
    edges: List[DirectedEdge]

class EnterpriseLinkAuthorityEngine:
    def __init__(self, payload: LinkGraphPayload, damping_factor: float = 0.85):
        self.damping_factor = damping_factor
        self.nodes = {node.id: node for node in payload.nodes}
        self.node_id_to_idx = {node.id: idx for idx, node in enumerate(payload.nodes)}
        self.idx_to_node_id = {idx: node.id for idx, node in enumerate(payload.nodes)}
        self.raw_edges = payload.edges
        self.n = len(self.nodes)
        
        # Validasi ukuran graf
        if self.n == 0:
            raise ValueError("Kumpulan node graf tidak boleh kosong.")
            
        logging.info("Engine diinisialisasi dengan %d node dan %d edge.", self.n, len(self.raw_edges))

    @staticmethod
    def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def _calculate_edge_weights(self) -> Tuple[List[int], List[int], List[float]]:
        rows = []
        cols = []
        weights = []

        for edge in self.raw_edges:
            if edge.source_id not in self.node_id_to_idx or edge.target_id not in self.node_id_to_idx:
                continue

            u_idx = self.node_id_to_idx[edge.source_id]
            v_idx = self.node_id_to_idx[edge.target_id]

            node_u = self.nodes[edge.source_id]
            node_v = self.nodes[edge.target_id]

            # Hitung kedekatan semantik antar node
            sim = self._cosine_similarity(
                np.array(node_u.semantic_embedding),
                np.array(node_v.semantic_embedding)
            )
            # Relevansi dinormalisasi (0 ke 1)
            sim_clamped = max(0.01, (sim + 1.0) / 2.0)

            # Bobot akhir merupakan sintesis posisi DOM dan Relevansi Semantik Konten
            final_edge_weight = edge.dom_weight * sim_clamped

            rows.append(u_idx)
            cols.append(v_idx)
            weights.append(final_edge_weight)

        return rows, cols, weights

    def compute_weighted_pagerank(self, max_iter: int = 200, tol: float = 1e-8) -> Dict[str, float]:
        """
        Menghitung Semantic-Weighted PageRank menggunakan representasi Matriks Sparse (CSR/CSC).
        """
        rows, cols, weights = self._calculate_edge_weights()
        
        # Inisialisasi Sparse Adjacency Matrix
        W = sp.csr_matrix((weights, (rows, cols)), shape=(self.n, self.n), dtype=np.float64)
        
        # Hitung row sum (total out-weight tiap node)
        out_weights = np.array(W.sum(axis=1)).flatten()
        
        # Identifikasi dangling nodes
        dangling_mask = (out_weights == 0.0)
        
        # Normalisasi baris untuk membentuk transition probability matrix
        with np.errstate(divide='ignore'):
            inv_out_weights = 1.0 / out_weights
            inv_out_weights[out_weights == 0.0] = 0.0

        inv_diag = sp.diags(inv_out_weights)
        P = inv_diag.dot(W)  # Transisi probabilitas stokastik per baris
        P_t = P.transpose().tocsc()

        # Inisialisasi rank seragam
        p = np.full(self.n, 1.0 / self.n, dtype=np.float64)
        teleport_uniform = (1.0 - self.damping_factor) / self.n

        logging.info("Memulai Power Iteration (toleransi: %e)...", tol)
        for i in range(max_iter):
            # Akumulasi nilai dangling node yang didistribusikan merata
            dangling_sum = np.sum(p[dangling_mask])
            dangling_contrib = (self.damping_factor * dangling_sum) / self.n

            # p_{k+1} = d * P^T * p_{k} + dangling_contrib + teleport
            p_next = self.damping_factor * P_t.dot(p) + dangling_contrib + teleport_uniform
            
            err = np.sum(np.abs(p_next - p))
            p = p_next
            if err < tol:
                logging.info("Konvergensi tercapai pada iterasi ke-%d (delta: %e).", i + 1, err)
                break
        else:
            logging.warning("Konvergensi tidak terpenuhi penuh setelah %d iterasi.", max_iter)

        # Normalisasi PageRank sum = 1
        p = p / np.sum(p)

        results = {
            self.nodes[self.idx_to_node_id[idx]].url: float(p[idx])
            for idx in range(self.n)
        }
        return results

    def detect_link_equity_leaks(self, ranks: Dict[str, float], threshold_percentile: float = 90.0) -> List[Dict]:
        """
        Mendeteksi URL non-prioritas yang menyerap PageRank berlebih secara anomali.
        """
        scores = list(ranks.values())
        crit_threshold = np.percentile(scores, threshold_percentile)
        leaks = []

        for node_id, node in self.nodes.items():
            rank_score = ranks[node.url]
            if not node.is_indexable and rank_score > crit_threshold:
                leaks.append({
                    "url": node.url,
                    "rank": rank_score,
                    "reason": "Non-indexable page menyerap authority di atas batas persentil kritis."
                })
        return leaks


if __name__ == "__main__":
    # Inisialisasi Mock Data untuk Validasi Eksekusi
    mock_nodes = [
        DocumentNode(id=1, url="https://enterprise.com/", canonical_url="https://enterprise.com/", semantic_embedding=[0.9, 0.1, 0.05], crawl_depth=0),
        DocumentNode(id=2, url="https://enterprise.com/products", canonical_url="https://enterprise.com/products", semantic_embedding=[0.85, 0.15, 0.1], crawl_depth=1),
        DocumentNode(id=3, url="https://enterprise.com/blog/deep-seo", canonical_url="https://enterprise.com/blog/deep-seo", semantic_embedding=[0.1, 0.9, 0.8], crawl_depth=2),
        DocumentNode(id=4, url="https://enterprise.com/privacy-policy", canonical_url="https://enterprise.com/privacy-policy", semantic_embedding=[0.01, 0.02, 0.01], crawl_depth=1, is_indexable=False),
    ]

    mock_edges = [
        DirectedEdge(source_id=1, target_id=2, dom_weight=1.0),
        DirectedEdge(source_id=1, target_id=4, dom_weight=0.2), # Link footer
        DirectedEdge(source_id=2, target_id=3, dom_weight=0.8),
        DirectedEdge(source_id=3, target_id=1, dom_weight=0.5), # Backlink internal ke root
        DirectedEdge(source_id=4, target_id=1, dom_weight=0.2),
    ]

    payload = LinkGraphPayload(nodes=mock_nodes, edges=mock_edges)
    engine = EnterpriseLinkAuthorityEngine(payload)
    pagerank_scores = engine.compute_weighted_pagerank()

    print("\n--- DISTRIBUSI PAGE RANK SEMANTIK ---")
    for url, score in sorted(pagerank_scores.items(), key=lambda x: x[1], reverse=True):
        print(f"Node: {url:<40} | Authority Score: {score:.6f}")

    anomalies = engine.detect_link_equity_leaks(pagerank_scores)
    print("\n--- DETEKSI PAGE RANK LEAKAGE ---")
    for anomaly in anomalies:
        print(f"[ALERT] {anomaly['url']} - {anomaly['reason']} (Score: {anomaly['rank']:.6f})")
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Toko Online Multi-Kategori Global (18 Juta Halaman)
Sebuah marketplace multi-nasional mengalami degradasi performa SEO organik:
- **Gejala**: Lebih dari 65% halaman produk baru (*long-tail SKUs*) membutuhkan waktu 30 hingga 90 hari hanya untuk diindeks oleh bot pencarian. Traffic landing page kategori utama menurun 22% *year-on-year*.
- **Akar Masalah (Graph Analysis)**:
  1. *Spider Traps*: Filter pencarian atribut tanpa rel-canonical menghasilkan loop permutasi 12 juta URL dinamis dengan out-degree masif.
  2. *Link Equity Dilution*: Halaman "Terms of Conditions", "Sitemap Utility", dan "Cookie Settings" di footer menerima 18 juta in-links internal, menyerap 34% dari total PageRank sistem.
  3. *Broken Topic Silos*: Halaman dari kategori "Suku Cadang Otomotif" menautkan ribuan produk "Pakaian Bayi" via modul rekomendasi silang berbasis perilaku user tanpa validasi relevansi topik.

### Solusi Rekayasa Graf:
1. **Penerapan Topological Pruning**:
   - Pemangkasan seluruh edge traversal dari elemen non-utama dengan implementasi `data-noindex-edge` yang diparsing oleh proxy edge (Cloudflare Workers) untuk menghapus link markup saat crawling bot terdeteksi.
2. **Dynamic Semantic Injection Engine**:
   - Membatasi tautan silang hanya antar-node dengan batas minimal relevansi semantik ($CosineSim \ge 0.72$).
   - Membangun *reverse authority injection*: Produk dengan PageRank rendah yang memiliki conversion rate tinggi secara dinamis disuntikkan ke dalam konten kategori utama (Level 1 Directory).
3. **Hasil**:
   - Kedalaman rata-rata crawl (*average crawl depth*) untuk 5 juta produk utama turun dari level 7 menjadi level 2.8.
   - Waktu pengindeksan produk baru menyusut dari rata-rata 42 hari menjadi 36 jam.
   - Total Organic Sessions tumbuh sebesar 41% dalam rentang waktu kuartal kedua paska rilis arsitektur graf baru.

---

## 9. Trade-offs

| Pendekatan / Algoritma | Keuntungan | Kerugian & Batasan | Mitigasi Masalah |
| :--- | :--- | :--- | :--- |
| **Full Graph Power Iteration (In-Memory)** | Akurasi nilai absolut sempurna; perhitungan dangling node matematis murni. | Kebutuhan RAM eksponensial ($O(N + E)$); tidak scalable pada graf $>50$ juta node pada mesin tunggal. | Gunakan Sparse Matrices (`scipy.sparse.csc_matrix`) atau beralih ke GraphFrames Spark terdistribusi. |
| **Personalized PageRank (Monte Carlo Random Walk)** | Komputasi sangat cepat secara inkremental; cocok untuk subset node spesifik. | Menghasilkan nilai perkiraan (*stochastic approximation*); margin error meningkat pada ekor distribusi (long-tail). | Naikkan jumlah iterasi sample paths ($R \ge 10,000$) pada subset target. |
| **Strict Physical Siloing (No Cross-Cluster Edges)** | Pencegahan kebocoran PageRank total; batas entitas topik sangat tajam. | Membunuh link equity flow antar pilar bisnis yang sebenarnya memiliki hubungan relevan (*lost synergy*). | Implementasikan *Contextual Bridge Edges* yang hanya diaktifkan jika relevansi embedding $\ge 0.80$. |
| **Graph Neural Network (GNN) Backlink Scoring** | Mampu mengenali skema tautan PBN manipulatif yang tersembunyi secara topologis. | Latensi inferensi tinggi; membutuhkan dataset berlabel (ground truth) link toksik yang terkurasi. | Eksekusi model secara asynchronous *batch inference* di level background worker. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Masalah: PageRank Sinks & Infinite Internal Loops
- **Gejala**: Nilai PageRank dari seluruh website secara bertahap terkonsentrasi hanya pada 2–3 URL terisolasi setelah puluhan iterasi.
- **Penyebab**: Sekelompok node saling menautkan satu sama lain tanpa memiliki out-degree ke sisa website lainnya (*Spider Trap* / *Absorbing Markov Chain*).
- **Solusi**: Audit graf menggunakan deteksi *Strongly Connected Components* (SCC) via Algoritma Tarjan. Pastikan setiap komponen terhubung dengan node penampung utama atau tambahkan batas minimum damping teleportation.

### 2. Masalah: Disavow File Bloating & Self-Inflicted Penalty
- **Gejala**: Traffic anjlok drastis setelah mengeksekusi disavow massal menggunakan tool automated PR pihak ketiga.
- **Penyebab**: Algoritma klasifikasi link toksik berbasis rule sederhana (misal: "semua domain DA < 10 adalah spam") secara keliru menghapus backlink relevan dari website lokal kecil atau forum niche bernilai.
- **Solusi**: Terapkan *Human-in-the-Loop Verification Pipeline*. Pisahkan flag risiko menjadi skor probabilitas: Disavow otomatis hanya jika klasifikasi toksik mencapai $p \ge 0.98$; selebihnya ($0.70 \le p < 0.98$) masuk ke antrean kurasi manual engineer.

### 3. Masalah: Internal Redirect Chains & Nilai Equity Terbuang
- **Gejala**: Metrik PageRank aktual halaman tujuan tidak naik meski telah mendapat banyak tautan internal baru.
- **Penyebab**: Tautan internal mengarah ke URL usang yang mengalami redirect multi-hop ($301 \to 301 \to 200$) atau canonical override. Setiap hop redirect berpotensi mengikis sinyal authority dan memboroskan crawl budget.
- **Solusi**: Jalankan *Adjacency Graph Normalizer* sebelum matrix build. Pipeline harus menolak tautan non-200 dan meresolusi link langsung ke *final destination canonical URL*.

---

## 11. Best Practices (Production Checklist)

### Data Engineering & Infrastructure
- [ ] Representasi graf internal menggunakan format matriks sparse (CSR/CSC) untuk menghemat ruang memori hingga 90%.
- [ ] URL selalu dinormalisasi sebelum dipetakan ke Node ID (lowercase, trailing slash dihilangkan, fragment URL `#` dibuang, URL tracking params seperti `utm_*` dibersihkan).
- [ ] Sediakan mekanisme *checkpointing* berkala saat memproses graf berukuran raksasa di level memori.

### Topologi Tautan & Optimasi SEO
- [ ] Crawl Depth: Pastikan $\ge 95\%$ halaman target bernilai komersial dapat dijangkau dalam rentang $\le 3$ klik dari Root Page.
- [ ] Link Ratio: Jaga rasio in-link internal seimbang; jangan biarkan halaman utilitas (Login, Legal, Privacy) memiliki skor PageRank lebih tinggi dari halaman kategori Level 1.
- [ ] Semantic Anchor Relevance: Pastikan teks jangkar (*anchor text*) tidak generik ("klik di sini", "baca selengkapnya"), melainkan merepresentasikan target entity topic.

### Digital PR & Authority Guard
- [ ] Otomasi pemantauan mention brand harian via web scrapers & streaming media API.
- [ ] Filter unlinked mentions terhadap database domain yang sudah memberikan tautan balik untuk memprioritaskan prospecting yang bernilai tinggi.
- [ ] Analisis profil backlink eksternal secara periodik dengan memeriksa *In-degree Spike Anomalies* untuk mengantisipasi Negative SEO Attack.

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan membangun sebuah modul graph processing internal mandiri yang mampu membaca representasi link corpus mentah, mendeteksi halaman yatim (*orphan pages*), dan mengkalkulasi skor Personalized PageRank.

### Langkah 1: Siapkan Struktur Proyek
Buat direktori kerja di lingkungan Anda:
```bash
mkdir -p hands-on/m02/
cd hands-on/m02/
python3 -m venv venv
source venv/bin/activate
pip install numpy scipy networkx pydantic
```

### Langkah 2: Buat Skrip Analisis Graf
Simpan kode berikut sebagai `hands-on/m02/link_architecture_lab.py`:

```python
import json
import networkx as nx
from typing import Dict, List

def run_lab():
    # 1. Dataset graf mini
    raw_data = {
        "nodes": [
            {"id": "home", "url": "/"},
            {"id": "cat_ai", "url": "/category/ai"},
            {"id": "cat_cloud", "url": "/category/cloud"},
            {"id": "art_llm", "url": "/category/ai/llm-guide"},
            {"id": "art_docker", "url": "/category/cloud/docker-setup"},
            {"id": "orphan_page", "url": "/legacy-landing-page"},
            {"id": "terms", "url": "/legal/terms"}
        ],
        "edges": [
            ("home", "cat_ai"),
            ("home", "cat_cloud"),
            ("home", "terms"),
            ("cat_ai", "art_llm"),
            ("art_llm", "cat_ai"),
            ("cat_cloud", "art_docker"),
            ("art_docker", "cat_cloud"),
            ("terms", "home")
        ]
    }

    # 2. Inisialisasi Directed Graph NetworkX
    G = nx.DiGraph()
    for node in raw_data["nodes"]:
        G.add_node(node["id"], url=node["url"])
    G.add_edges_from(raw_data["edges"])

    print(f"Total Nodes: {G.number_of_nodes()}, Total Edges: {G.number_of_edges()}")

    # 3. Deteksi Orphan Nodes (In-degree == 0 dan Out-degree == 0)
    orphans = [n for n in G.nodes() if G.in_degree(n) == 0 and n != "home"]
    print(f"Halaman Terdeteksi Yatim (Orphan): {orphans}")

    # 4. Standard PageRank
    pr_standard = nx.pagerank(G, alpha=0.85)

    # 5. Personalized PageRank: Berikan prioritas teleportasi ke pilar AI
    personalization = {n: 0.0 for n in G.nodes()}
    personalization["cat_ai"] = 0.7
    personalization["home"] = 0.3
    
    pr_personalized = nx.pagerank(G, alpha=0.85, personalization=personalization)

    # 6. Evaluasi Hasil
    print("\n--- PERBANDINGAN PAGERANK ---")
    print(f"{'Node ID':<15} | {'Standard':<12} | {'Personalized':<12}")
    print("-" * 45)
    for n in G.nodes():
        print(f"{n:<15} | {pr_standard[n]:.5f}    | {pr_personalized[n]:.5f}")

if __name__ == "__main__":
    run_lab()
```

### Langkah 3: Eksekusi dan Amati
Jalankan file:
```bash
python link_architecture_lab.py
```
Perhatikan bagaimana node `/category/ai/llm-guide` melonjak nilai otoritasnya ketika vektor personalisasi diarahkan ke `cat_ai`.

---

## 13. Exercise

### Level Easy
Modifikasi skrip `link_architecture_lab.py` untuk menghitung rasio perbandingan antara in-degree dan out-degree dari setiap node. Identifikasi node yang bertindak murni sebagai *Link Absorber* (in-degree tinggi, out-degree = 0).
- **Target Capaian**: Fungsi mampu mencetak node pengumpul link beserta total link yang masuk.

### Level Medium
Buat sebuah modul Python yang membaca payload adjacency list dan memvalidasi topologi *Strict Silo Architecture*. 
- **Aturan**: Node yang berada di `/category/ai/*` sama sekali tidak diizinkan memiliki edge langsung ke node `/category/cloud/*` kecuali jika edge tersebut melewati node `home`.
- **Target Capaian**: Skrip menghasilkan daftar pelanggaran topologi (*isolation violations*) secara otomatis.

### Level Hard
Implementasikan algoritma Personalized PageRank dari nol murni menggunakan operasi matriks sparse SciPy (`scipy.sparse`), tanpa menggunakan library `networkx`. 
- **Persyaratan**: Sistem harus mendukung dangling-node handling secara native dan menerima input kamus bobot personalisasi $V_{\text{pers}}$ dengan ukuran graf sebesar 50,000 node sintesis.
- **Target Capaian**: Eksekusi konvergen di bawah 1 detik dengan toleransi error $10^{-7}$.

---

## 14. Challenge

### Studi Kasus: Algoritma Penyeimbang Graf Otomatis (Self-Healing Graph Balancer)
**Konteks**: Website e-commerce Anda memiliki 500.000 halaman katalog produk. Tim marketing sering kali membuat artikel blog musiman yang tidak ditautkan dari mana pun (terisolasi) atau halaman kategori usang yang mempertahankan skor authority tinggi tetapi produknya telah habis (*out-of-stock*).

**Tantangan**:
Rancang dan bangun arsitektur sistem autonomus (*Self-Healing Internal Link Agent*) dengan kriteria:
1. **Model Monitoring**: Pipeline berjalan secara terjadwal untuk menganalisis directed link graph seluruh platform.
2. **Dynamic Injection Resolver**:
   - Jika sistem mendeteksi node target $v$ dengan conversion rate tinggi namun memiliki PageRank di kuartil terendah ($Q_1$), sistem harus mencari 3 node donor $u$ yang:
     1. Memiliki $PR(u) \ge \text{Median}(PR)$.
     2. Memiliki out-degree di bawah ambang batas saturasi link ($L(u) < 30$).
     3. Memiliki skor kedekatan kosinus semantik embedding $\ge 0.75$ terhadap node $v$.
3. **Ghost Node Nullification**:
   - Jika halaman berstatus Out-of-Stock permanen namun memiliki in-link authority besar, rancang mekanisme pengalihan tautan dinamis tanpa merusak integritas graf secara global.

*Tuliskan arsitektur desain, skema basis data graf, dan algoritma penentuan node donor secara lengkap tanpa menggunakan shortcut library tingkat tinggi.*

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi matematis utama dari parameter *damping factor* ($d$) dalam PageRank?
   - A. Menjamin matriks transisi selalu berukuran simetris.
   - B. Memodelkan kemungkinan peselancar melompat secara acak ke halaman baru, mencegah spider trap dan menjamin konvergensi.
   - C. Membagi authority secara merata ke seluruh out-link tanpa memperhitungkan bobot konten.
   - D. Menghapus halaman non-indexable dari graf web.

2. Sebuah node yang memiliki in-link namun tidak memiliki out-link sama sekali disebut sebagai:
   - A. Teleport Node
   - B. Dangling Node
   - C. Canonical Hub
   - D. Root Cluster

3. Jika halaman A memiliki PageRank 1.0 dan memiliki 5 tautan keluar, berapakah PageRank dasar yang diteruskan ke masing-masing halaman tujuan (asumsi model klasik tanpa pembobotan semantik)?
   - A. 0.20
   - B. 0.85
   - C. 0.17
   - D. 0.05

4. Mengapa meletakkan tautan di dalam area `<footer>` umumnya dihitung dengan bobot (*edge weight*) lebih rendah dibanding tautan di dalam tag `<article>` pada model Weighted PageRank modern?
   - A. Footer tidak dapat dibaca oleh web crawler.
   - B. Footer memiliki struktur tag DOM yang terlalu dalam.
   - C. Mesin pencari menerapkan model *Reasonable Surfer*, di mana probabilitas pengguna mengeklik tautan navigasi boilerplate lebih rendah daripada tautan di badan konten utama.
   - D. Footer selalu otomatis ditandai dengan rel="nofollow".

5. Konsep "Topic Silo" dalam arsitektur link bertujuan utama untuk:
   - A. Mengurangi jumlah total request database.
   - B. Memaksimalkan crawl depth agar seluruh server terbebani merata.
   - C. Mengonsolidasikan otoritas semantik pada satu kluster topik tertutup dan mencegah dilusi relevansi oleh topik yang tidak berhubungan.
   - D. Mencegah website diakses oleh bot non-Google.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Apa dampak dari fenomena *PageRank Leakage* yang disebabkan oleh pemuatan ratusan tautan internal menuju halaman non-indexable (misal URL hasil filter parameter dinamis)?
   - A. Matriks transisi menjadi non-invertible dan script compiler crash.
   - B. Ekuitas link bernilai tinggi terdistribusi ke halaman yang tidak bisa dikonversi menjadi traffic organik mesin pencari, melemahkan skor ranking halaman utama.
   - C. Algoritma search engine secara otomatis menghapus domain dari indeks.
   - D. Nilai konvergensi Power Iteration menjadi negatif.

7. Pada sparse matrix calculation, representasi format Compressed Sparse Column (CSC) lebih disukai daripada Compressed Sparse Row (CSR) ketika:
   - A. Kita sering melakukan operasi slicing baris secara kontinu.
   - B. Melakukan operasi perkalian matriks-vektor dengan matriks transisi yang ditransposisikan ($P^T \cdot p$).
   - C. Graf tidak memiliki edges sama sekali.
   - D. Graf hanya memiliki node dengan in-degree = 1.

8. Dalam kalkulasi Personalized PageRank (PPR), bagaimana cara matematis memprioritaskan otoritas agar terkonsentrasi di sekitar kategori produk tertentu?
   - A. Menghapus damping factor sepenuhnya ($d = 0$).
   - B. Mengubah *teleportation vector* yang awalnya seragam ($1/N$) menjadi terpusat pada indeks node kategori yang ingin ditingkatkan bobotnya.
   - C. Mengalikan out-degree node kategori dengan skalar acak.
   - D. Mengubah seluruh undirected edges menjadi bidirectional edges.

9. Manakah metrik graf berikut yang paling akurat untuk mendeteksi halaman website yang bertindak sebagai "jembatan kritis" (*critical bridge*) antar dua kluster topik besar?
   - A. In-degree Centrality
   - B. Closeness Centrality
   - C. Betweenness Centrality
   - D. Clustering Coefficient

10. Ketika crawler autonomous agent mendeteksi lonjakan backlink masif (10.000 backlink dalam 24 jam) dari domain dengan ekstensi TLD acak menggunakan anchor text komersial yang identik, tindakan awal yang paling tepat secara arsitektural adalah:
    - A. Langsung mengirim instruksi HTTP 410 Gone ke halaman target.
    - B. Menginjeksi backlink tersebut ke basis data graf lokal dan menaikkan skor authority internal.
    - C. Mengarantina domain-domain donor tersebut ke dalam antrean *Anomaly Verification* untuk dievaluasi kemungkinan serangan *Negative SEO* sebelum dikompilasi ke file Disavow.
    - D. Menghapus rel="canonical" dari seluruh halaman website.

---

### Bagian 3: Skenario Kasus Produksi

#### Skenario 1: The Vanishing Equity Incident
Sebuah portal media memiliki arsitektur di mana setiap artikel baru otomatis menautkan 10 artikel terpopuler di bagian sidebar. Namun, artikel-artikel yang berusia lebih dari 6 bulan mengalami penurunan drastis pada peringkat SERP meskipun secara historis memiliki banyak backlink eksternal. Setelah graf internal diekstraksi, ditemukan bahwa artikel-artikel populer di sidebar tersebut adalah 10 artikel yang sama selama 2 tahun terakhir.
- **Pertanyaan**: Analisis fenomena kegagalan graf apa yang terjadi di sini, dan bagaimana rancangan solusi topologis terotomatisasi untuk mendistribusikan ulang authority secara adil ke artikel long-tail yang berstatus *evergreen*?

#### Skenario 2: Anti-Sybil Defense pada External Link Verification
Sistem Digital PR autonomous Anda dirancang untuk memburu *unlinked brand mentions* dan mengevaluasi apakah situs penutur layak diajukan penawaran relasi kemitraan tautan (link partnership). Sistem menemukan 50 domain berbeda yang semuanya menyebut brand perusahaan Anda dalam konteks positif. Namun, algoritma deteksi pola menduga bahwa ke-50 situs tersebut dikelola oleh satu entitas yang sama (Private Blog Network / Sybil Cluster).
- **Pertanyaan**: Parameter graf dan metadata teknis apa saja yang wajib diperiksa oleh sistem analitik Anda untuk memvalidasi apakah cluster tersebut merupakan satu kesatuan PBN artifisial sebelum tim outreach membuang sumber daya secara sia-sia?

#### Skenario 3: High-Frequency Graph Convergence Bottleneck
Dalam sistem enterprise, internal link graf dihitung ulang setiap 6 jam untuk memperbarui rekomendasi tautan kontekstual. Dengan 15 juta node dan 250 juta edge, komputasi standard power iteration pada server lokal mulai mengalami timeout (melebihi window 6 jam) dan menghabiskan 95% kapasitas RAM.
- **Pertanyaan**: Arsitektur komputasi apa yang harus diterapkan untuk mengoptimalkan throughput perhitungan ini? Jelaskan strategi partisi graf atau aproksimasi yang dapat memangkas waktu komputasi secara signifikan tanpa mengorbankan integritas ranking authority.

---

## Kunci Jawaban & Panduan Solusi Quiz

### Kunci Bagian 1
1. **B** — Damping factor memastikan bahwa proses stochastic transition tidak terjebak dalam siklus buntu (*absorbing state*) dan memenuhi teorema Perron-Frobenius.
2. **B** — Node tanpa tautan keluar disebut dangling node, yang dapat menyerap probabilitas jika tidak dinormalisasi.
3. **C** — $PR(A) / L(A) = 1.0 / 5 = 0.20$. Setelah diperhitungkan dengan damping factor standar ($d = 0.85$), kontribusi bersih adalah $0.85 \times 0.2 = 0.17$.
4. **C** — Mesin pencari modern menggunakan model *Reasonable Surfer* yang memprediksi interaksi nyata pengguna berdasarkan bobot tata letak DOM.
5. **C** — Topic Siloing memfokuskan relevansi semantik pada kluster tertutup guna memperkuat otoritas topikal di mata crawler.

### Kunci Bagian 2
6. **B** — Link equity dialirkan ke halaman yang tidak dapat diindeks, membuang authority yang seharusnya dinikmati landing page transaksional.
7. **B** — Format CSC mengoptimalkan operasi kompresi kolom, menjadikannya sangat cepat saat dikalikan dengan vektor probabilitas kolom pada proses transposisi $P^T$.
8. **B** — Vektor personalisasi (teleportation distribution) diatur condong ke indeks node prioritas, mengubah equilibrium state dari distribusi stasioner.
9. **C** — Betweenness Centrality mengukur seberapa sering sebuah node menjadi jalur terpendek (*shortest path*) yang menghubungkan node-node lain di dalam graf.
10. **C** — Pola tersebut merupakan karakteristik umum dari manipulasi link atau Negative SEO Attack; isolasi anomali dan verifikasi risiko adalah langkah pertahanan standar.

### Panduan Solusi Bagian 3 (Kasus Produksi)

#### Solusi Skenario 1
- **Akar Masalah**: Terjadi fenomena *PageRank Monopoly / Hub Cannibalization*. 10 artikel populer tersebut menjadi *super-sinks* yang menyedot in-degree masif dari jutaan artikel lain setiap kali konten baru terbit. Sebaliknya, artikel lama mengalami *link rot* internal karena tergeser dari pagination utama dan tidak lagi mendapatkan tautan baru (*decaying historical equity*).
- **Arsitektur Solusi**: 
  1. Hapus modul popular posts yang bersifat statis secara global. Ganti dengan modul *Dynamic Contextual Ingestion*.
  2. Implementasikan *Decay-Weighted Recommendation*: Tautan internal diinjeksi berdasarkan korelasi semantik konten ditambah parameter kebaruan/kebutuhan authority.
  3. Terapkan rotasi periodik: Node artikel yang telah mencapai target authority mapan secara bertahap dialihkan out-link-nya untuk menyuplai artikel evergreen yang mengalami penurunan impresi di Google Search Console.

#### Solusi Skenario 2
- **Verifikasi Topologis & Infrastruktur**:
  1. **Infrastruktur Hosting**: Periksa kesamaan ASN (Autonomous System Number), Subnet IP (/24), dan penggunaan sertifikat SSL reverse-proxy terpusat (misal: kesamaan Cloudflare Origin Certificate).
  2. **Whois & Registrasi**: Tanggal pendaftaran domain yang identik atau pola nameserver seragam.
  3. **Graf Co-Citations & Link Neighborhood**: Buat directed graph dari ke-50 situs tersebut. PBN biasanya memiliki keterkaitan link internal yang tinggi antar sesamanya (*strongly interconnected component*) dan memiliki rasio out-link yang hampir identik menuju target komersial tertentu.
  4. **Struktur Konten (DOM Footprint)**: Bandingkan kesamaan template HTML, DOM structure tree, dan footprint CMS theme menggunakan perhitungan Tree Edit Distance.

#### Solusi Skenario 3
- **Optimasi Arsitektur Distributed Graph**:
  1. **Distributed Framework Transition**: Migrasikan komputasi dari proses single-node SciPy ke distributed graph engine seperti Apache Spark GraphX/GraphFrames atau Rust-based parallel engine (misal: Rayon / Petgraph).
  2. **Partisi Graf (Graph Partitioning)**: Gunakan algoritma partisi seperti METIS untuk membagi graf 15 juta node ke beberapa worker nodes dengan meminimalkan edge crossing antar node server (*minimum cut*).
  3. **Aproksimasi Algoritma**: Gunakan teknik *Monte Carlo Random Walks* untuk menghitung nilai Personalized PageRank lokal secara paralel ketimbang mengeksekusi full matrix multiplication global pada setiap iterasi 6 jam.
  4. **Incremental PageRank**: Hanya jalankan kalkulasi penuh secara mingguan; untuk interval 6 jam, cukup hitung pembaruan inkremental hanya pada sub-graf yang mengalami mutasi link (penambahan atau penghapusan edge).

---

## 16. Summary

1. **Prinsip Graf Kritis**: Link bukan sekadar elemen HTML, melainkan tepi berarah (*directed edges*) dalam matriks probabilitas stasioner. Mengontrol arah dan bobot edge adalah kunci utama dalam mengendalikan aliran *link equity* website.
2. **Evolusi Algoritma**: Model modern telah bertransformasi dari *Random Surfer* klasik menjadi *Contextual Reasonable Surfer*, di mana bobot edge ditentukan oleh kombinasi posisi DOM, teks jangkar, dan kedekatan vektor semantik (Transformer Embeddings).
3. **Kesehatan Topologis**: Menghilangkan jebakan graf seperti *PageRank Leaks*, *Dangling Nodes*, dan *Spider Traps* memberikan dampak langsung yang signifikan terhadap efisiensi crawl budget search engine dan kecepatan indexing halaman enterprise.
4. **Digital PR Terotomatisasi**: Skalabilitas strategi otoritas membutuhkan integrasi data ingestion backlink secara real-time, kemampuan memvalidasi anomali topologi (PBN/Negative SEO), serta alur kerja outreach yang didukung sistem analitik graf berbasis AI.