# Bab 07: Search Intent, Semantic Keyword Architecture & Clustering Module 01

---

## 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Merancang (Design)** arsitektur *semantic keyword taxonomy* terdistribusi berskala enterprise yang mengombinasikan *dense vector embeddings*, algoritma reduksi dimensi non-linear, dan *density-based clustering*.
- **Mengimplementasikan (Implement)** *pipeline* end-to-end klasifikasi *search intent* berbasis transformer (Bi-Encoder & Cross-Encoder) untuk memetakan kueri ke dalam taksonomi intent multi-level (*informational, commercial investigation, transactional, navigational*) beserta *micro-intents*.
- **Menganalisis (Analyze)** dan mengatasi fenomena *keyword cannibalization* pada skala jutaan URL melalui kalkulasi *semantic topological overlap* di ruang vektor berdimensi tinggi.
- **Mengoptimalkan (Optimize)** alokasi memori, latensi inferensi, dan kestabilan klaster menggunakan teknik kuantisasi vektor, *batch processing*, dan evaluasi metrik topologis (*Silhouette Coefficient*, *Density-Based Clustering Validation / DBCV*).

---

## 2. Concept Overview
Paradigma optimasi mesin pencari telah bergeser dari pencocokan leksikal (*exact keyword matching* berbasis TF-IDF/BM25) menuju pemahaman representasi semantik (*neural information retrieval*). Mesin pencari modern seperti Google (melalui transformer-based models seperti BERT, MUM, dan Gemini-in-search) memetakan token kueri ke dalam *continuous latent vector spaces*.

```
   Traditional SEO (Lexical)             Modern Neural SEO (Dense Semantic)
+-------------------------------+       +------------------------------------+
|  Query: "beli vps murah"      |       |  Query: "beli vps murah"           |
|  Document: "jual vps murah"   |       |  Embedding: [0.142, -0.891, ...]   |
|                               |       |                                    |
|  Pencocokan berbasis n-gram   |  VS   |  Kalkulasi Cosine Similarity:      |
|  dan string similarity index  |       |  Cosine Sim(Q, D) = 0.94           |
|  (Rentan sinonim & out-of-    |       |  (Memahami latent intent:          |
|   vocabulary mismatch)        |       |   "transactional / cloud-hosting") |
+-------------------------------+       +------------------------------------+
```

### Mental Model & Teori Inti
1. **Representasi Semantik Terdistribusi**: Setiap kata kunci direpresentasikan sebagai vektor densitas tinggi $\mathbf{v} \in \mathbb{R}^d$ ($d=384, 768,$ atau $1536$). Jarak angular (misal: *Cosine Distance*) merefleksikan kedekatan makna kontekstual, bukan kesamaan ejaan leksikal.
2. **Manifold Hypothesis & Dimensionality Reduction**: Data kata kunci dalam ruang berdimensi tinggi ($d \ge 384$) terkonsentrasi pada sub-manifold dengan dimensi intrinsik yang jauh lebih rendah. Reduksi dimensi non-linear via **UMAP (Uniform Manifold Approximation and Projection)** mempertahankan struktur lokal (*local neighborhood*) dan global, memungkinkan algoritma pengelompokan mendeteksi batas-batas klaster secara presisi.
3. **Density-Based Clustering (HDBSCAN)**: Berbeda dengan K-Means yang memaksakan batas klaster berbentuk bulat (*hyper-spherical*) dengan jumlah $k$ statis, **HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise)** mengekstraksi klaster dengan densitas variabel dan secara eksplisit mengisolasi kueri ambigu/spurious sebagai *noise* ($cluster = -1$).
4. **Intent Disambiguation**: Pemisahan antara *Macro-Intent* (Transactional, Commercial, Informational, Navigational) dan *Micro-Intent* (e.g., "compare specs", "troubleshoot error", "pricing query") dieksekusi melalui kombinasi *Bi-Encoder* untuk penarikan kandidat cepat dan *Cross-Encoder* untuk *sequence-pair classification*.

---

## 3. Why It Matters
Pada skala enterprise (misal: situs e-commerce dengan $10^6$ SKU atau portal SaaS multi-regional), pengelolaan kata kunci secara manual via spreadsheet menimbulkan kegagalan struktural yang fatal:

- **Keyword Cannibalization Severity**: Beberapa halaman dalam domain yang sama menargetkan variasi leksikal yang berbeda dari intent semantik yang identik. Akibatnya, sinyal otoritas terpecah, peringkat SERP berfluktuasi (*rank volatility*), dan Google menolak mengindeks URL duplikat.
- **SERP Intent Drift**: Mesin pencari terus memperbarui interpretasi intent dari kueri tertentu. Misalnya, kueri "best headless cms" bertransisi dari *pure informational* (artikel panduan teknis) menjadi *commercial investigation* (halaman komparasi vendor dengan tabel harga). Tanpa analisis terprogram, arsitektur informasi situs menjadi usang terhadap *search evaluation framework* mesin pencari.
- **Topical Authority Gap**: Kurangnya struktur *hub-and-spoke* berbasis *semantic clustering* menyebabkan arsitektur informasi internal domain gagal mentransfer *link equity* secara logis, melemahkan skor relevansi domain pada klaster subjek tertentu (*topical authority*).

---

## 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur sistem modular untuk pemrosesan kata kunci, klasterisasi semantik, dan klasifikasi intent:

```
[Raw Keyword Stream / Search Console API / Ahrefs CSV]
                         │
                         ▼
        ┌───────────────────────────────────┐
        │     Ingestion & Sanitization      │
        │   - Regex Cleansing               │
        │   - Language Detection & Filtering│
        │   - Search Volume/CPC Enrichment  │
        └───────────────────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │      Dense Vector Encoding        │
        │   - Bi-Encoder (Sentence-BERT /   │
        │     BGE-M3 / text-embedding-3)    │
        │   - FP16/INT8 Dynamic Quantization│
        └───────────────────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │   Manifold Learning & Reduction   │
        │   - UMAP (Dimension: d -> 5..10)  │
        │   - Metric: Cosine, Min Dist: 0.1 │
        └───────────────────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │      Density-Based Clustering     │
        │   - HDBSCAN (min_cluster_size=5)  │
        │   - Soft Clustering Fallback      │
        │   - Noise Separation (Cluster -1) │
        └───────────────────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │ Intent Classification & Synthesis │
        │   - Cross-Encoder Inference       │
        │   - Zero-Shot Macro/Micro Tagger  │
        │   - Canonical Query Extraction    │
        └───────────────────────────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │ Persistence & Downstream Delivery │
        │   - Vector Index (Qdrant / Milvus)│
        │   - Relational DB (PostgreSQL)    │
        │   - Content CMS Taxonomy Sync     │
        └───────────────────────────────────┘
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Bi-Encoder vs. Cross-Encoder dalam Ruang Semantik
Dalam *pipeline* arsitektur kata kunci:
- **Bi-Encoder** memproses kueri secara independen:
  $$\mathbf{u} = \text{Encoder}(Q_1), \quad \mathbf{v} = \text{Encoder}(Q_2)$$
  Kedekatan dihitung menggunakan *Cosine Similarity*:
  $$\text{sim}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
  Karakteristik: Komputasi murah ($O(N)$ untuk $N$ kata kunci), vektor dapat di-*cache* atau diindeks dalam *vector search engine*. Digunakan untuk klasterisasi massal.
- **Cross-Encoder** menggabungkan kedua input ke dalam representasi bersama:
  $$s = \text{Softmax}(\text{CrossEncoder}(Q_1 \parallel Q_2))$$
  Model ini mengkalkulasi perhatian penuh (*full cross-attention*) antara setiap token $Q_1$ dan $Q_2$. Sangat akurat namun berbiaya komputasi tinggi ($O(N^2)$). Digunakan saat memvalidasi *cluster boundary* dan menentukan apakah dua kueri yang ambigu mengarah pada satu *search intent* kanonikal yang sama.

### 5.2 Algoritma UMAP + HDBSCAN
Penggabungan UMAP dan HDBSCAN menyelesaikan limitasi *Curse of Dimensionality*:
1. **UMAP**: Membangun representasi graf berbobot dari kueri di dimensi tinggi menggunakan konsep topologi diferensial, lalu memproyeksikannya ke dimensi rendah seraya meminimalkan *Fuzzy Set Cross-Entropy*.
2. **HDBSCAN**:
   - Menghitung *core distance* $d_{\text{core}}(x)$ untuk setiap titik berdasarkan $k$-nearest neighbors.
   - Menghitung *mutual reachability distance*:
     $$d_{\text{mreach}}(a, b) = \max \left( d_{\text{core}}(a), d_{\text{core}}(b), d(a, b) \right)$$
   - Membangun *Minimum Spanning Tree* dari graf *mutual reachability*.
   - Mengonstruksi hierarki komponen dan memadatkan hierarki klaster berdasarkan parameter `min_cluster_size`.
   - Mengukur stabilitas setiap klaster via integral ketahanan kerapatan ($\lambda = \frac{1}{\text{distance}}$):
     $$S(\text{cluster}) = \sum_{p \in \text{cluster}} (\lambda_{\text{p}} - \lambda_{\text{birth}})$$

---

## 6. Production-Ready Code Implementation

Berikut implementasi modular *clustering* semantik dan klasifikasi *search intent* skala produksi berbasis Python 3.11+.

```python
"""
Semantic Keyword Architecture & Intent Engine
Requires: sentence-transformers, umap-learn, hdbscan, pydantic, numpy, torch
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import hdbscan
import numpy as np
import torch
import umap
from pydantic import BaseModel, Field, field_validator
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("SemanticSEOEngine")

# ---------------------------------------------------------------------------
# Domain Models (Pydantic Schema)
# ---------------------------------------------------------------------------
class SearchIntentEnum(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    COMMERCIAL = "COMMERCIAL"
    TRANSACTIONAL = "TRANSACTIONAL"
    NAVIGATIONAL = "NAVIGATIONAL"
    UNKNOWN = "UNKNOWN"


class KeywordPayload(BaseModel):
    query: str = Field(..., min_length=2, max_length=256)
    search_volume: int = Field(default=0, ge=0)
    cpc: float = Field(default=0.0, ge=0.0)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        cleaned = " ".join(v.strip().lower().split())
        if not cleaned:
            raise ValueError("Kueri tidak boleh kosong setelah sanitasi.")
        return cleaned


class ClusteredKeywordNode(BaseModel):
    query: str
    search_volume: int
    cpc: float
    cluster_id: int
    cluster_membership_prob: float
    primary_intent: SearchIntentEnum
    intent_confidence: float
    is_noise: bool


# ---------------------------------------------------------------------------
# Configuration Dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PipelineConfig:
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    umap_n_neighbors: int = 15
    umap_n_components: int = 5
    umap_min_dist: float = 0.05
    umap_metric: str = "cosine"
    hdbscan_min_cluster_size: int = 3
    hdbscan_min_samples: int = 2
    batch_size: int = 64
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# ---------------------------------------------------------------------------
# Engine Implementation
# ---------------------------------------------------------------------------
class SemanticKeywordEngine:
    def __init__(self, config: PipelineConfig = PipelineConfig()):
        self.config = config
        logger.info(f"Menginisialisasi SemanticKeywordEngine pada perangkat: {self.config.device}")
        
        # Muat Model Ekstraksi Vektor Dense
        try:
            self.encoder = SentenceTransformer(
                self.config.embedding_model_name,
                device=self.config.device
            )
        except Exception as e:
            logger.critical(f"Gagal memuat model encoder: {str(e)}")
            raise RuntimeError(f"Initialization failure: {str(e)}") from e

        # Intent Seed Anchors untuk Zero-Shot Semantic Distance Intent Mapping
        self.intent_anchors: Dict[SearchIntentEnum, List[str]] = {
            SearchIntentEnum.TRANSACTIONAL: [
                "beli online order checkout price discount kupon promo subscription",
                "buy purchase acquire payment gateway deal"
            ],
            SearchIntentEnum.COMMERCIAL: [
                "rekomendasi terbaik review perbandingan versus alternatif vs ranking",
                "best comparison review top alternative rating"
            ],
            SearchIntentEnum.INFORMATIONAL: [
                "apa itu bagaimana cara tutorial panduan tips solusi dokumen referensi",
                "what is how to guide tutorial documentation solve fix"
            ],
            SearchIntentEnum.NAVIGATIONAL: [
                "login portal domain resmi website download app sign in dashboard",
                "official portal website app download access console"
            ],
        }
        self._anchor_embeddings: Optional[Dict[SearchIntentEnum, np.ndarray]] = None
        self._precompute_intent_anchors()

    def _precompute_intent_anchors(self) -> None:
        """Menghitung representasi vektor centroid untuk tiap kelas intent."""
        logger.info("Melakukan pra-kalkulasi centroid representasi intent...")
        self._anchor_embeddings = {}
        for intent, phrases in self.intent_anchors.items():
            embeddings = self.encoder.encode(
                phrases,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            # Hitung rata-rata centroid dan normalisasikan kembali
            centroid = np.mean(embeddings, axis=0)
            centroid = centroid / np.linalg.norm(centroid)
            self._anchor_embeddings[intent] = centroid

    def _infer_intent(self, query_embeddings: np.ndarray) -> List[Tuple[SearchIntentEnum, float]]:
        """Klasifikasi intent kueri menggunakan Cosine Similarity terhadap anchor centroid."""
        if self._anchor_embeddings is None:
            raise ValueError("Anchor embeddings belum terinisialisasi.")

        results: List[Tuple[SearchIntentEnum, float]] = []
        # Matrix centroids: (num_intents, embedding_dim)
        intents_list = list(self._anchor_embeddings.keys())
        centroid_matrix = np.array([self._anchor_embeddings[i] for i in intents_list])

        # Matrix multiplication: query_embeddings (N, D) x Centroids^T (D, C) -> (N, C)
        sim_matrix = np.dot(query_embeddings, centroid_matrix.T)

        for row in sim_matrix:
            best_idx = int(np.argmax(row))
            score = float(row[best_idx])
            
            # Normalisasi metrik cosine [-1, 1] ke rentang probabilitas [0, 1]
            calibrated_prob = max(0.0, min(1.0, (score + 1.0) / 2.0))
            
            # Threshold guard: Di bawah toleransi tertentu dinyatakan UNKNOWN
            if calibrated_prob < 0.55:
                results.append((SearchIntentEnum.UNKNOWN, calibrated_prob))
            else:
                results.append((intents_list[best_idx], calibrated_prob))
        return results

    def fit_transform(self, keywords: List[KeywordPayload]) -> List[ClusteredKeywordNode]:
        """
        Mengeksekusi siklus komputasi lengkap:
        Dense Embedding -> UMAP Reduction -> HDBSCAN -> Intent Labeling.
        """
        if not keywords:
            logger.warning("Payload kata kunci kosong. Mengembalikan list kosong.")
            return []

        queries = [item.query for item in keywords]
        logger.info(f"Mengekstraksi embeddings untuk {len(queries)} kueri...")
        
        # 1. Generate Embeddings
        try:
            embeddings = self.encoder.encode(
                queries,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
        except Exception as e:
            logger.error(f"Error saat inferensi dense embedding: {str(e)}")
            raise

        # 2. Intent Inference
        intent_classifications = self._infer_intent(embeddings)

        # 3. UMAP Dimensionality Reduction
        # Evaluasi kondisi batas jumlah sampel
        n_samples = len(queries)
        effective_n_neighbors = min(self.config.umap_n_neighbors, max(2, n_samples - 1))
        effective_n_components = min(self.config.umap_n_components, max(2, n_samples - 2))

        logger.info(
            f"Menjalankan UMAP: neighbors={effective_n_neighbors}, components={effective_n_components}"
        )
        
        if n_samples <= effective_n_components:
            # Fallback jika sampel data terlalu sedikit
            logger.warn("Data terlalu sedikit untuk reduksi manifold non-linear. Bypassing UMAP.")
            reduced_embeddings = embeddings
        else:
            reducer = umap.UMAP(
                n_neighbors=effective_n_neighbors,
                n_components=effective_n_components,
                min_dist=self.config.umap_min_dist,
                metric=self.config.umap_metric,
                random_state=42
            )
            reduced_embeddings = reducer.fit_transform(embeddings)

        # 4. HDBSCAN Density Clustering
        effective_min_cluster_size = min(self.config.hdbscan_min_cluster_size, max(2, n_samples))
        logger.info(f"Menjalankan HDBSCAN: min_cluster_size={effective_min_cluster_size}")
        
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=effective_min_cluster_size,
            min_samples=self.config.hdbscan_min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True
        )
        labels = clusterer.fit_predict(reduced_embeddings)
        probabilities = clusterer.probabilities_

        # 5. Output Construction
        output: List[ClusteredKeywordNode] = []
        for i, kw in enumerate(keywords):
            cid = int(labels[i])
            c_prob = float(probabilities[i])
            intent, i_conf = intent_classifications[i]
            
            node = ClusteredKeywordNode(
                query=kw.query,
                search_volume=kw.search_volume,
                cpc=kw.cpc,
                cluster_id=cid,
                cluster_membership_prob=c_prob,
                primary_intent=intent,
                intent_confidence=i_conf,
                is_noise=(cid == -1)
            )
            output.append(node)

        logger.info("Transformasi data selesai secara sukses.")
        return output


# ---------------------------------------------------------------------------
# Verifikasi Integrasi
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_dataset = [
        KeywordPayload(query="cara install kubernetes di ubuntu", search_volume=1200, cpc=0.45),
        KeywordPayload(query="panduan setup cluster k8s ubuntu server", search_volume=800, cpc=0.50),
        KeywordPayload(query="harga sewa kubernetes managed", search_volume=2400, cpc=3.20),
        KeywordPayload(query="beli hosting kubernetes murah", search_volume=3600, cpc=4.10),
        KeywordPayload(query="review gke vs eks managed k8s", search_volume=950, cpc=1.80),
        KeywordPayload(query="perbandingan arsitektur k8s vs docker swarm", search_volume=720, cpc=0.90),
        KeywordPayload(query="cloud console kubernetes login", search_volume=5000, cpc=0.10),
        KeywordPayload(query="resep nasi goreng spesial jakarta", search_volume=15000, cpc=0.05), # Outlier Noise
    ]

    engine = SemanticKeywordEngine()
    processed_nodes = engine.fit_transform(sample_dataset)

    print("\nHASIL CLUSTERING & INTENT MAPPING:\n" + "=" * 80)
    for node in processed_nodes:
        print(
            f"Query       : {node.query:<42} | "
            f"Cluster ID  : {node.cluster_id:>2} (Prob: {node.cluster_membership_prob:.2f}) | "
            f"Intent      : {node.primary_intent.value:<13} ({node.intent_confidence:.2f}) | "
            f"Noise       : {node.is_noise}"
        )
```

---

## 7. Edge Cases & Failure Modes

Pada implementasi skala produksi, sistem dapat menghadapi skenario anomali data:

1. **Polysemy & Contextual Homonymy**:
   - *Problem*: Kata seperti "Apple" dapat merujuk ke buah (*fruit*) atau entitas korporasi teknologi.
   - *Failure*: Bi-encoder tanpa konteks tambahan (*sentence padding*) dapat mencampurkan kueri resep makanan dengan perbaikan gawai.
   - *Mitigation*: Gunakan *entity injection* atau lakukan konkatenasi dengan metadata SERP (*top-ranking snippet titles*) sebelum menghasilkan embedding: `query_context = f"{query} - {top_serp_title}"`.

2. **The "Noise Explosion" in HDBSCAN**:
   - *Problem*: Jika parameter `min_cluster_size` diset terlalu tinggi pada kumpulan data yang sangat tersebar (*sparse*), lebih dari 60% kueri akan diberi label `-1` (Noise).
   - *Failure*: Hilangnya sebagian besar long-tail keyword dari taksonomi.
   - *Mitigation*: Terapkan *soft clustering fallback*. Untuk titik bernilai `-1`, hitung *approximate cluster membership vector* menggunakan modul `hdbscan.all_points_membership_vectors(clusterer)` dan assign ke klaster terdekat dengan ambang batas batas $\tau \ge 0.15$.

3. **Out-of-Distribution (OOD) Search Intent**:
   - *Problem*: Kueri dengan *fractured intent* (misalnya: kueri transaksional yang tiba-tiba didominasi berita peretasan produk).
   - *Failure*: Intent classifier statis salah menandai halaman komersial sebagai artikel berita murni.
   - *Mitigation*: Cross-validation real-time terhadap SERP result types (apakah Google menyajikan *product pack*, *video carousel*, atau *organic text links*).

4. **Vector Quantization Degradation**:
   - *Problem*: Mengonversi vektor dari FP32 ke INT8 untuk menghemat memori GPU pada jutaan kueri.
   - *Failure*: Terjadinya tabrakan arah (*directional collision*) pada kueri pendek (1-2 kata).
   - *Mitigation*: Pertahankan representasi FP16 untuk kueri dengan panjang token $\le 3$.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Pilihan Utama (UMAP + HDBSCAN + Bi-Encoder) | Pilihan Alternatif (K-Means + TF-IDF) | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Bentuk Klaster** | Bebas / Arbitrer (*Non-spherical manifold*) | Kaku / *Hyper-spherical* | K-Means memaksa data terbagi merata meski distribusi semantik aslinya melengkung atau menyebar asimetris. |
| **Kompleksitas Komputasi** | Tinggi: $O(N \log N)$ s.d. $O(N^2)$ saat kalkulasi graf | Rendah: $O(k \cdot N \cdot i)$ | Model transformer dan manifold learning memerlukan akselerasi GPU pada $N \ge 100.000$. |
| **Noise & Outlier Handling** | Dikeluarkan secara otomatis via Klaster `-1` | Outlier ditarik paksa ke centroid terdekat | K-Means merusak representasi klaster karena outlier mengubah titik centroid secara signifikan. |
| **Determinisme** | Stokastik (kecuali `random_state` dikunci di UMAP) | Cenderung deterministik jika inisialisasi dikontrol | UMAP sensitif terhadap inisialisasi koordinat awal dan variasi *floating-point arithmetic*. |
| **Interpretasi Makna** | Mengerti sinonim dan *latent contexts* | Bergantung pada kata yang beririsan (*lexical*) | TF-IDF gagal mengenali bahwa "murah" dan "biaya rendah" berada di intent yang sama. |

---

## 9. Best Practices & Standard Industri

1. **Embedding Cache Layer**: Jangan pernah mengkodekan ulang kueri yang sama. Simpan hasil embedding $Q_i$ di Redis atau key-value store (menggunakan BLAKE3 hash dari teks yang telah disanitasi sebagai key) dengan format biner `float32`.
2. **Dynamic Minimum Cluster Size**: Skalakan `min_cluster_size` berdasarkan ukuran dataset:
   $$\text{min\_cluster\_size} = \max\left(3, \lfloor \ln(N) \rfloor \right)$$
3. **Pemberian Label Kanonikal Otomatis**: Pilih kueri dengan *search volume* tertinggi atau jarak terdekat ke *medoid* klaster sebagai H1 / Judul Induk arsitektur halaman.
4. **Evaluasi DBCV**: Selalu pantau skor DBCV (*Density-Based Clustering Validation*). DBCV berkisar antara $[-1, 1]$. Skor $> 0.2$ menunjukkan densitas dan pemisahan topologis yang valid pada manifold kata kunci.
5. **Deduplikasi Topikal**: Integrasikan metrik *Topical Cannibalization Index*: Jika dua cluster memiliki jarak Euclidean antar-centroid $< 0.35$ pada ruang UMAP, tandai klaster tersebut untuk digabung (*merge candidate*) guna mencegah persaingan URL internal.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda bertindak sebagai Principal SEO Systems Architect di perusahaan B2B SaaS Cloud Infrastructure. Anda diberikan daftar kueri *raw* yang tidak terstruktur dan berpotensi mengalami kanibalisasi semantik. Tugas Anda: membangun *clustering pipeline*, mendeteksi kueri *noise*, dan menentukan halaman arsitektur yang harus dibuat (*Content Hub Architecture*).

### Data Input (`lab_keywords.json`)
Simpan dataset berikut:
```json
[
  {"query": "managed database postgresql", "search_volume": 4400, "cpc": 4.5},
  {"query": "postgresql cloud hosting provider", "search_volume": 2900, "cpc": 5.1},
  {"query": "setup high availability postgres cluster", "search_volume": 1600, "cpc": 1.2},
  {"query": "cara replikasi postgresql streaming", "search_volume": 1200, "cpc": 0.8},
  {"query": "biaya db postgres managed per jam", "search_volume": 880, "cpc": 3.4},
  {"query": "postgresql pricing calculator", "search_volume": 2100, "cpc": 3.9},
  {"query": "download wallpaper anime naruto 4k", "search_volume": 90000, "cpc": 0.01}
]
```

### Langkah Eksekusi

1. **Setup Environment**:
```bash
python3 -m venv seo-semantic-env
source seo-semantic-env/bin/activate
pip install sentence-transformers umap-learn hdbscan pydantic numpy torch
```

2. **Eksekusi Script**:
Jalankan implementasi kode Python pada **Bagian 6** dengan membaca data dari berkas `lab_keywords.json`.

3. **Verifikasi Output Analisis**:
Amati keluaran log dan data JSON yang dihasilkan:
- Pastikan kueri non-relevan (`download wallpaper anime naruto 4k`) terisolasi dengan nilai `cluster_id = -1` (*Noise Isolation Validation*).
- Pastikan kueri panduan teknis ("setup high availability...", "cara replikasi...") dikelompokkan ke intent `INFORMATIONAL`.
- Pastikan kueri komersial dan harga ("biaya db...", "postgresql pricing calculator") dikelompokkan ke dalam satu klaster arsitektur halaman produk bertipe `COMMERCIAL` atau `TRANSACTIONAL`.

### Expected Verification Metrics
```text
[VERIFICATION CHECKLIST]
[PASS] Noise Query correctly tagged with Cluster ID: -1
[PASS] PostgreSQL Hosting Queries merged into the same Semantic Cluster
[PASS] Informational intent mapped with confidence >= 0.70
[PASS] Output satisfies ClusteredKeywordNode schema validations
```