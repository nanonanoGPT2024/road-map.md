# Bab 03: Semantic Retrieval, Vector Databases & Embeddings
## Modul 01: Arsitektur Vector Embedding Space, Indexing HNSW, dan Semantic Retrieval Engine

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Menganalisis Karakteristik Geometris High-Dimensional Vector Embeddings (Taxonomy Level 4):** Menilai perilaku distribusi embedding pada continuous latent space ($\mathbb{R}^D$) dan memilih similarity metric yang tepat (Cosine, Inner Product, L2 Distance) berdasarkan teknik normalisasi vektor dan spesifikasi arsitektur model embedding.
*   **Mengevaluasi Kinerja Algoritma Indexing Approximate Nearest Neighbor (ANN) (Taxonomy Level 5):** Mengukur trade-off struktural antara algoritma indexing berbasis graf (*Hierarchical Navigable Small World* / HNSW) dan berbasis inversi kuantisasi (*Inverted File with Product Quantization* / IVF-PQ) pada metrik Recall@K, indexing throughput, memory footprint, serta latency query $p95$/$p99$.
*   **Merancang Pipeline Semantic Retrieval Kelas Produksi (Taxonomy Level 6):** Membangun subsistem ingestion dan query retrieval modular menggunakan Python modern, lengkap dengan batching, normalisasi vektor, payload metadata filtering, connection pooling, dan resilient error handling.
*   **Memitigasi Failure Modes Retrieval Spesifik Enterprise (Taxonomy Level 5):** Mendiagnosis dan mengimplementasikan mekanisme mitigasi untuk edge-case kritis seperti *vector drift*, anomali embedding norm bernilai nol/NaN, *high filter-selectivity degradation*, serta memory saturation akibat index growth tak terkontrol.

---

### 2. Concept Overview

Pencarian leksikal tradisional (seperti BM25 atau TF-IDF) bergantung sepenuhnya pada *lexical match*—apakah token query identik dengan token pada korpus dokumen. Pendekatan ini gagal total menghadapi fenomena linguistik alami: sinonim (*car* vs. *automobile*), polisemi (*bank* institusi keuangan vs. *bank* bantaran sungai), serta abstraksi semantik (*"bagaimana cara memperbaiki koneksi database yang putus?"* vs. *"handling transient network dropouts in connection pool"*).

```
Lexical Space (Sparse, Orthogonal)          Semantic Vector Space (Dense, Continuous)
      "car"            "automobile"                            R^D
        |                   |                         * "automobile"
   (Dimensi 101)       (Dimensi 405)                 /  (Jarak Cosine < 0.05)
        |                   |                       * "car"
   Orthogonal: Dot Product = 0                              \
                                                             * "vehicle"
```

*Semantic Retrieval* menyelesaikan masalah ini dengan memproyeksikan data teks tak terstruktur ke dalam ruang vektor berdimensi tinggi ($\mathbb{R}^D$, di mana umumnya $D \in [384, 3072]$). Di dalam ruang laten kontinu ini, kedekatan geometris merepresentasikan kesamaan semantik kontekstual.

Tantangan komputasi muncul pada skala enterprise: jika Anda memiliki 10 juta dokumen berdimensi 1536 ($D=1536$, representasi umum OpenAI `text-embedding-3-small` / Ada-002), pencarian *Exact Nearest Neighbor* ($k$-NN) membutuhkan kalkulasi jarak penuh terhadap seluruh 10 juta vektor secara berurutan.
Kompleksitas pencarian $k$-NN sekuensial adalah:

$$\mathcal{O}(N \cdot D)$$

Untuk $N = 10^7$ dan $D = 1536$, satu kueri tunggal memerlukan $1.536 \times 10^{10}$ operasi *floating-point*, yang mustahil memenuhi SLA latensi enterprise ($< 25\text{ ms}$).

Oleh karena itu, sistem produksi menggunakan algoritma **Approximate Nearest Neighbor (ANN)**. Algoritma ANN mengorbankan sebagian kecil kepastian absolut (menoleransi drop recall 1–2%) untuk menukar kompleksitas pencarian dari linier $\mathcal{O}(N \cdot D)$ menjadi sub-linier atau logaritmik $\mathcal{O}(\log N \cdot D)$.

---

### 3. Why It Matters

Bagi seorang AI Product Builder dan Principal Engineer, semantic retrieval bukan sekadar wrapper API pihak ketiga; ini adalah fondasi performa sistem Retrieval-Augmented Generation (RAG) dan Autonomous Agent.

1.  **Direct Retrieval Impact on LLM Hallucination:** Kualitas konteks yang diekstraksi berkorelasi linier dengan tingkat halusinasi LLM. Jika retrieval layer mengembalikan *false positives* (chunk irelevan) atau melewatkan *ground-truth context* (*low recall*), LLM akan mengalami *context poisoning* atau menghasilkan halusinasi akibat missing knowledge.
2.  **Infrastructure & RAM Cost at Scale:** Menyimpan 10 juta vektor berdimensi 1536 dalam format raw IEEE-754 Single-Precision Floating Point (`float32`) membutuhkan memori murni:
    $$10{,}000{,}000 \times 1536 \times 4\text{ bytes} \approx 61.44\text{ GB RAM}$$
    Ketika diindeks menggunakan HNSW, graph overhead menambah memori sebesar 1.5x–2.5x, melonjakkan kebutuhan RAM hingga $\approx 120\text{–}150\text{ GB}$. Tanpa pemahaman mendalam tentang kuantisasi (*Scalar Quantization* / *Product Quantization*), biaya infrastruktur cluster vector database dapat membengkak secara tidak terkendali.
3.  **Low Latency Under Concurrency:** Sistem RAG enterprise dituntut memproses lusinan kueri konkuren dengan $p99 < 30\text{ ms}$. Pemilihan algoritma ANN, distance metric, serta hardware acceleration (AVX-512, NEON) menentukan kelayakan produk saat traffic meningkat tajam.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan arsitektur dual-path pada Production Vector Search Engine: jalur *Ingestion/Indexing Pipeline* (asinkron/batch) dan jalur *Online Query Retrieval Pipeline* (sinkron, SLA ketat).

```
========================================================================================
                               INGESTION & INDEXING PIPELINE
========================================================================================
[Unstructured Data]
        |
        v
[Document Chunking] ---> [Embedding Model Client] 
                             | (e.g., text-embedding-3-small)
                             v
                     [Vector Normalizer (L2)]
                             |
                             v
                 +-----------------------+
                 | Batch Ingestion Queue |
                 +-----------------------+
                             |
                             v
                 +-----------------------------------------+
                 |            VECTOR DATABASE              |
                 |                                         |
                 |   +---------------------------------+   |
                 |   | Storage: Payload WAL + Vectors  |   |
                 |   +---------------------------------+   |
                 |                   |                     |
                 |                   v                     |
                 |   +---------------------------------+   |
                 |   |   HNSW Graph Index Builder      |   |
                 |   |   - Multi-layer skip graphs     |   |
                 |   |   - Scalar Quantization (SQ8)   |   |
                 |   +---------------------------------+   |
                 +-----------------------------------------+

========================================================================================
                              ONLINE RETRIEVAL PIPELINE
========================================================================================
[User / Agent Query] 
        |
        v
[Query Preprocessor & Cache]
        |
        +---> [Cache Hit?] --- YES ---> [Return Context]
        | NO
        v
[Embedding Model Client]
        | (Vector inference)
        v
[Vector Normalizer (L2)]
        |
        v
+-------------------------------------------------------------------+
| Vector Search Engine (ANN)                                        |
|                                                                   |
| 1. Metadata Pre-Filtering (Filter Tenant, Access Control, Tags)   |
| 2. HNSW Graph Traversal (ef_search parameter)                     |
| 3. Candidate Extraction (Top-K Candidates: K=50)                  |
+-------------------------------------------------------------------+
        |
        v
[Re-Ranking Model (Cross-Encoder)] ---> Re-sort to Final Top-K (K=5)
        |
        v
[Context Assembler & Token Pruner] ---> Injected into LLM System Prompt
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Mathematics of Distance Metrics

Pemilihan metrik kesamaan (*similarity metric*) bukan preferensi subjektif; metrik harus disesuaikan secara presisi dengan karakteristik embedding model yang digunakan.

```
       Cosine Similarity                    Euclidean (L2) Distance
             A                                       A
            /                                       /|
           / theta                                 / | d
          /                                       /  |
         +--------> B                            +---+----> B
     cos(theta) = A.B / (|A||B|)              d = sqrt(sum((Ai - Bi)^2))
(Hanya mengukur sudut/arah)             (Mengukur jarak euclidean absolut)
```

1.  **Dot Product (Inner Product):**
    $$\langle \mathbf{u}, \mathbf{v} \rangle = \sum_{i=1}^{D} u_i v_i$$
    *   Mengukur arah dan magnitudo secara simultan. Sangat efisien di tingkat komputasi instruksi prosesor (SIMD).
    *   Hanya valid jika magnitudo vektor merepresentasikan signifikansi semantik (jarang terjadi pada embedding teks modern).

2.  **Cosine Similarity:**
    $$S_{\text{cosine}}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2} = \frac{\sum_{i=1}^{D} u_i v_i}{\sqrt{\sum_{i=1}^{D} u_i^2} \sqrt{\sum_{i=1}^{D} v_i^2}}$$
    *   Hanya mengukur deviasi sudut antar vektor, mengabaikan magnitudo. Nilai berada dalam rentang $[-1, 1]$.
    *   Komputasi *norm* ($\|\mathbf{u}\|_2$ dan $\|\mathbf{v}\|_2$) pada saat query time memicu penalti CPU.

3.  **Euclidean Distance ($L_2$ Distance):**
    $$d_{L_2}(\mathbf{u}, \mathbf{v}) = \sqrt{\sum_{i=1}^{D} (u_i - v_i)^2}$$
    *   Mengukur jarak geometris absolut antar titik di ruang euclidean.

> **Optimasi Produksi (Unit Normalization):**
> Jika seluruh vektor dinormalisasi menjadi unit-length ($\|\mathbf{u}\|_2 = 1$) pada saat proses ingestion:
> $$d_{L_2}^2(\mathbf{u}, \mathbf{v}) = 2 - 2 \langle \mathbf{u}, \mathbf{v} \rangle$$
> $$S_{\text{cosine}}(\mathbf{u}, \mathbf{v}) = \langle \mathbf{u}, \mathbf{v} \rangle$$
> Jika seluruh vektor ternormalisasi secara seragam, Cosine Similarity, Dot Product, dan inversi dari L2 Distance akan menghasilkan **urutan peringkat (ranking order) yang identik**. Karena itu, normalisasi vektor saat write time wajib diterapkan agar mesin pencari cukup mengeksekusi operasi Dot Product murni yang telah teroptimasi AVX/SIMD tanpa runtime vector division.

---

#### 5.2 Algoritma Indexing: Anatomi HNSW (Hierarchical Navigable Small World)

HNSW saat ini merupakan *state-of-the-art* indexing graph-based ANN untuk low-latency semantic search. HNSW memadukan konsep probabilistic *Skip-List* 1D ke dalam multi-layer graf navigasi multi-dimensi.

```
Layer 2 (Coarse)       [Node A] -----------------------------------> [Node Z]
                           \                                             \
Layer 1 (Intermediate)  [Node A] --------------> [Node K] -------------> [Node Z]
                           \                         \                     \
Layer 0 (Dense/All)     [Node A] -> [Node B] -> [Node K] -> [Node P] -> [Node Z]
```

*   **Hierarchical Graph Construction:**
    *   **Layer 0:** Berisi seluruh elemen data node vektor yang terdaftar ($N$).
    *   **Layer $l > 0$:** Subset node yang dipilih secara probabilistik dengan probabilitas peluruhan eksponensial $P = \frac{1}{\ln(M)}$. Layer teratas memiliki koneksi link graf berjarak jauh (*express links/high-degree skip lanes*).
*   **Algoritma Traversal:**
    Pencarian dimulai dari node teratas (entry point). Sistem melakukan *greedy search* pada layer tersebut hingga menemukan local minimum (node terdekat ke query vector pada layer tersebut). Titik tersebut kemudian dijadikan entry point untuk melompat turun ke layer di bawahnya. Proses ini berulang secara berjenjang hingga mencapai Layer 0. Pada Layer 0, algoritma menjalankan pencarian local neighbors berbasis antrian prioritas (*priority queue*) sebesar $ef\_search$.
*   **Parameter Kritis HNSW:**
    *   $M$ (contoh: 16–64): Batas maksimum jumlah edge dua arah yang dialokasikan per node per layer. Nilai $M$ yang lebih besar meningkatkan recall namun meningkatkan konsumsi RAM dan memperlambat build index.
    *   $ef\_construction$ (contoh: 100–400): Ukuran antrian kandidat yang dievaluasi selama perakitan graf index. Mengontrol trade-off waktu build index versus kualitas recall graph.
    *   $ef\_search$ (contoh: 32–200): Ukuran antrian prioritas kandidat dinamis saat kueri online. Ditentukan saat runtime: $ef\_search$ dinaikkan untuk akurasi/recall lebih tinggi, atau diturunkan untuk $p99$ latency yang lebih agresif. Batasan minimum: $ef\_search \ge K$.

---

#### 5.3 Vector Quantization (Compression)

Untuk menghemat RAM pada skala ratusan juta vektor:
*   **Scalar Quantization (SQ8):** Memetakan interval float32 $[-1.0, 1.0]$ ke rentang diskrit int8 $[0, 255]$.
    *   *Memory Reduction:* Mengurangi konsumsi memori vektor mentah sebesar 75% (dari 4 byte per dimensi menjadi 1 byte per dimensi).
    *   *Performance Impact:* Drop recall umumnya marginal ($< 1\%$) jika distribusi data seragam.
*   **Product Quantization (PQ):** Memecah vektor berdimensi $D$ menjadi $m$ sub-vektor berdimensi $D/m$. Masing-masing ruang sub-vektor kemudian dikelompokkan menjadi $k^*$ centroid via k-means. Nilai sub-vektor digantikan oleh index/byte ID centroid terdekat.
    *   *Memory Reduction:* Ekstrem (hingga 90–95%).
    *   *Trade-off:* Penurunan recall yang terukur serta kebutuhan re-ranking layer berbasis raw vectors (*two-stage retrieval*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi semantic retrieval engine modular menggunakan Python 3.11+, didesain dengan prinsip clean architecture:
*   Pemisahan domain abstractions, embedding provider, dan vector index manager.
*   Penerapan Vector Normalization otomatis.
*   Penggunaan in-memory HNSW abstraction (menggunakan engine native C++ `hnswlib` yang dibungkus python interface).
*   Pydantic V2 schemas untuk contract validation.
*   Error handling granular, safe fallbacks, dan thread-safe batching.

#### File: `requirements.txt`
```text
hnswlib>=0.8.0
numpy>=1.26.0
pydantic>=2.6.0
```

#### File: `semantic_engine.py`
```python
import abc
import logging
import math
import time
from typing import Any, Dict, List, Optional, Protocol, Tuple
import hnswlib
import numpy as np
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SemanticRetrievalEngine")


# =====================================================================
# Domain Entities & Validation Schemas
# =====================================================================

class Document(BaseModel):
    """Representasi atomic data unit untuk ingestion."""
    doc_id: int = Field(..., description="ID integer unik untuk vector indexing")
    content: str = Field(..., min_length=1, description="Payload teks dokumen mentah")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata pendukung filtering")


class SearchQuery(BaseModel):
    """Query parameter contract."""
    query_text: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)
    ef_search: int = Field(default=64, ge=10, le=512)
    metadata_filter: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Hasil retrieval yang telah dievaluasi."""
    doc_id: int
    score: float
    content: str
    metadata: Dict[str, Any]


# =====================================================================
# Embedding Model Interface & Mock Implementation
# =====================================================================

class EmbeddingProvider(Protocol):
    """Contract protocol untuk vector embedding inference model."""
    @property
    def dimension(self) -> int:
        ...

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        ...


class DeterministicMockEmbeddingProvider:
    """
    Mock Embedding Provider untuk pengujian deterministik dan pipeline isolation.
    Menghasilkan vektor pseudo-semantic berbasis hash token terdistribusi normal.
    """
    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        batch_embeddings = []
        for text in texts:
            # Menggunakan string seed untuk membangkitkan vektor acak yang stabil
            seed = sum(ord(c) for c in text) % (2**32)
            rng = np.random.default_rng(seed)
            raw_vec = rng.standard_normal(self._dimension, dtype=np.float32)
            
            # Sanitasi: Hindari Zero Vector & NaN
            norm = np.linalg.norm(raw_vec)
            if norm == 0 or np.isnan(norm):
                logger.warning(f"Terdeteksi zero norm pada teks: {text[:20]}. Fallback ke default.")
                raw_vec = np.ones(self._dimension, dtype=np.float32)
                norm = np.linalg.norm(raw_vec)

            # Normalisasi Unit L2: ||v|| = 1.0
            normalized_vec = raw_vec / norm
            batch_embeddings.append(normalized_vec)

        return np.vstack(batch_embeddings).astype(np.float32)


# =====================================================================
# Core HNSW Index Storage Engine
# =====================================================================

class HNSWVectorStore:
    """
    Production wrapper mengelilingi mesin HNSWlib dengan memory-safe payload store
    dan validasi metadata predicates.
    """
    def __init__(self, dimension: int, max_elements: int = 100_000, m: int = 16, ef_construction: int = 200):
        self.dimension = dimension
        self.max_elements = max_elements
        self.m = m
        self.ef_construction = ef_construction
        
        # Inisialisasi Space Index: Gunakan 'ip' (Inner Product / Cosine pada vektor ternormalisasi)
        self.index = hnswlib.Index(space="ip", dim=self.dimension)
        self.index.init_index(max_elements=self.max_elements, ef_construction=self.ef_construction, M=self.m)
        self.index.set_num_threads(4)  # Optimasi multithread CPU Core
        
        # Dedicated Key-Value store untuk Payload & Payload Metadata
        self.payload_store: Dict[int, Document] = {}

    def insert_batch(self, documents: List[Document], embeddings: np.ndarray) -> None:
        """Memasukkan batch dokumen dan vektor secara atomik ke graf HNSW."""
        if len(documents) != embeddings.shape[0]:
            raise ValueError(f"Dimensi dokumen ({len(documents)}) dan embedding ({embeddings.shape[0]}) mismatch.")
        
        if embeddings.shape[1] != self.dimension:
            raise ValueError(f"Vektor berdimensi {embeddings.shape[1]}, index membutuhkan {self.dimension}.")

        doc_ids = [doc.doc_id for doc in documents]
        
        # Tambahkan ke payload store
        for doc in documents:
            self.payload_store[doc.doc_id] = doc

        # Masukkan ke index hnswlib
        self.index.add_items(embeddings, doc_ids)
        logger.info(f"Berhasil mengindeks {len(documents)} vektor ke graf HNSW.")

    def search(self, query_vector: np.ndarray, top_k: int, ef_search: int, 
               metadata_filter: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Mengeksekusi ANN Search di Layer HNSW, dilanjutkan dengan filtering metadata.
        """
        # Sesuaikan parameter dinamis runtime ef_search
        self.index.set_ef(max(ef_search, top_k))

        # Query index ANN. Jarak metrik 'ip' (Inner Product):
        # hnswlib mengembalikan: distance = 1.0 - inner_product
        # Karena vektor ternormalisasi: Cosine Similarity = 1.0 - distance
        effective_k = min(top_k * 4 if metadata_filter else top_k, len(self.payload_store))
        if effective_k == 0:
            return []

        labels, distances = self.index.knn_query(query_vector, k=effective_k)
        
        results: List[SearchResult] = []
        for doc_id, dist in zip(labels[0], distances[0]):
            doc_id = int(doc_id)
            doc = self.payload_store.get(doc_id)
            if not doc:
                continue

            # Terapkan Metadata Filtering Logic (Pre-Filtering / In-Pipeline Filter)
            if metadata_filter:
                match = all(doc.metadata.get(k) == v for k, v in metadata_filter.items())
                if not match:
                    continue

            similarity_score = 1.0 - float(dist)
            results.append(SearchResult(
                doc_id=doc.doc_id,
                score=round(similarity_score, 4),
                content=doc.content,
                metadata=doc.metadata
            ))

            if len(results) >= top_k:
                break

        return results


# =====================================================================
# Semantic Retrieval Engine Orchestrator
# =====================================================================

class ProductionSemanticEngine:
    """
    Fasad utama yang mengabstraksi Ingestion, Normalisasi Vektor, dan Query Execution.
    """
    def __init__(self, embedding_provider: EmbeddingProvider, max_elements: int = 50_000):
        self.embedder = embedding_provider
        self.vector_store = HNSWVectorStore(
            dimension=self.embedder.dimension,
            max_elements=max_elements
        )

    def ingest_documents(self, documents: List[Document], batch_size: int = 128) -> None:
        """Memproses dokumen mentah, batching, embedding inference, dan indexing."""
        if not documents:
            logger.warning("Koleksi dokumen kosong. Mengabaikan ingest.")
            return

        total_docs = len(documents)
        logger.info(f"Memulai pipeline ingestion untuk {total_docs} dokumen...")

        start_time = time.perf_counter()
        for idx in range(0, total_docs, batch_size):
            chunk = documents[idx:idx + batch_size]
            texts = [doc.content for doc in chunk]

            # Injeksi Normalisasi Vektor
            embeddings = self.embedder.generate_embeddings(texts)
            
            # Commit batch ke Engine
            self.vector_store.insert_batch(chunk, embeddings)

        latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"Selesai mengindeks {total_docs} item dalam {latency:.2f} ms.")

    def retrieve(self, query: SearchQuery) -> List[SearchResult]:
        """Menjalankan downstream end-to-end vector search dengan runtime instrumentation."""
        start_time = time.perf_counter()

        # Step 1: Inferensi Vektor Query Tunggal
        query_vector = self.embedder.generate_embeddings([query.query_text])

        # Step 2: ANN Retrieval di HNSW Index
        results = self.vector_store.search(
            query_vector=query_vector,
            top_k=query.top_k,
            ef_search=query.ef_search,
            metadata_filter=query.metadata_filter
        )

        latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"Query: '{query.query_text}' | Results: {len(results)} | Latency: {latency:.3f} ms")
        return results


# =====================================================================
# Verification Script Execution
# =====================================================================

if __name__ == "__main__":
    logger.info("Menginisialisasi Semantic Engine Cluster...")
    
    # Init Dependency
    mock_embedder = DeterministicMockEmbeddingProvider(dimension=256)
    engine = ProductionSemanticEngine(embedding_provider=mock_embedder)

    # Ingestion Corpus
    corpus = [
        Document(doc_id=101, content="Optimasi throughput database PostgreSQL dengan tuning connection pool.", 
                 metadata={"env": "prod", "tier": "backend"}),
        Document(doc_id=102, content="Panduan mitigasi out of memory pada cache cluster Redis enterprise.", 
                 metadata={"env": "prod", "tier": "cache"}),
        Document(doc_id=103, content="Membangun asynchronous streaming agent menggunakan Kafka dan Python worker.", 
                 metadata={"env": "staging", "tier": "streaming"}),
        Document(doc_id=104, content="Arsitektur HNSW graph index untuk pencarian vektor berskala tinggi.", 
                 metadata={"env": "prod", "tier": "search"}),
    ]
    engine.ingest_documents(corpus)

    # Execute Search Query dengan Metadata Filter
    sample_query = SearchQuery(
        query_text="Bagaimana mengamankan performa indexing pada vector database?",
        top_k=2,
        ef_search=32,
        metadata_filter={"env": "prod"}
    )
    
    hits = engine.retrieve(sample_query)
    for i, hit in enumerate(hits, 1):
        print(f"\n[Rank {i}] Doc ID: {hit.doc_id} | Similarity: {hit.score:.4f}")
        print(f"Content: {hit.content}")
        print(f"Metadata: {hit.metadata}")
```

---

### 7. Edge Cases & Failure Modes

Berikut adalah failure modes laten pada layer semantic retrieval tingkat produksi beserta mekanisme mitigasinya:

| Failure Mode | Gejala di Lapangan | Root Cause Analisis | Mitigasi Arsitektural / Algoritmik |
| :--- | :--- | :--- | :--- |
| **Norm-0 Vector & NaN Injection** | Vector index throw exception / crash saat runtime query; query score menghasilkan `NaN`. | Teks dokumen hanya berisi spasi/stop-words/karakter tidak dikenal (out-of-vocabulary), membuat model embedding mengembalikan vektor nol atau deviasi floating point NaN. | Validasi pre-ingest via Pydantic & Numpy: kalkulasi $\epsilon$-check `norm = np.linalg.norm(v)`. Jika `norm < 1e-12` atau `isnan(norm)`, tolak record atau ganti dengan safe fallback vector unit acak. |
| **Filter-Selectivity Graph Disconnect** | Latency pencarian melonjak 10x-100x dan Recall anjlok mendekati 0%. | Post-filtering diterapkan pada metadata dengan selektivitas sangat tinggi (misal: filter hanya cocok dengan 0.001% data). Algoritma HNSW terjebak menjelajahi neighbor yang dibuang oleh filter. | Terapkan **Iterative Single-Stage Filtered Search** (seperti implementasi Qdrant/Milvus) atau **Pre-filtering Payload Sub-Indices** alih-alih naif post-filtering. |
| **Dimensionality Mismatch Ingestion** | Database tolak write payload; pipeline batching downstream terhenti (*pipeline stall*). | Model embedding diperbarui tanpa versi yang jelas (misal: migrasi internal dari model 768 dimensi ke 1536 dimensi tanpa rebuild skema index). | Terapkan *Strict Schema Gatekeeper* saat runtime Ingestion: assert validasi `vector.shape[1] == index.dimension` sebelum data dialokasikan ke memori buffer. |
| **Catastrophic Memory Growth (RAM Exhaustion)** | Vector database instance dihentikan oleh OS via OOM (Out Of Memory) Killer saat traffic write memuncak. | Karakteristik struktur graf HNSW membutuhkan memory overhead signifikan per edge link ($M$). Seiring penambahan node, footprint memori tumbuh non-linier. | Batasi limit alokasi memori HNSW via parameter hardware cgroup. Terapkan **Scalar Quantization (SQ8)** atau disk-backed persistent engine (seperti Qdrant Memmapped vectors). |

---

### 8. Trade-offs & Alternatif Solusi

Saat memilih algoritma indexing dan mesin vector storage, arsitek sistem harus menavigasi trade-off berikut:

```
Indexing Trade-off Matrix:
  Recall / Accuracy
        ^
        |             * Exact Flat (KNN)
   100% |
        |               * HNSW (Graph)
        |
        |                      * IVF-PQ (Quantized)
        |
        +----------------------------------------------> Indexing Speed / RAM Efficiency
```

#### Komparasi Arsitektur Indexing

1.  **Exact Search (FLAT / $k$-NN):**
    *   *Kelebihan:* 100% mutlak recall. Tidak memerlukan waktu komputasi build index. Sempurna untuk data yang sering di-update atau ukuran korpus kecil ($< 50{,}000$ dokumen).
    *   *Kekurangan:* Latensi kueri berskala $\mathcal{O}(N)$. Tidak layak untuk $N > 100{,}000$ dokumen pada SLA real-time ($< 30\text{ ms}$).
2.  **HNSW (Hierarchical Navigable Small World):**
    *   *Kelebihan:* Menghasilkan recall tertinggi di antara metode ANN ($> 95\text{–}99\%$). Latensi query sangat cepat ($\mathcal{O}(\log N)$) dan stabil pada variasi top-k.
    *   *Kekurangan:* Konsumsi RAM sangat tinggi. Waktu indexing lambat ($ef\_construction$). Menghapus dokumen (deletion) meninggalkan *tombstone* yang merusak topologi small-world graf.
3.  **IVF-PQ (Inverted File with Product Quantization):**
    *   *Kelebihan:* Efisiensi komputasi dan memori terbaik. Vektor dikompresi ke kode cluster diskrit, menghemat hingga 90% footprint RAM.
    *   *Kekurangan:* Memerlukan proses *training phase* menggunakan sample representatif untuk membentuk cluster centroid. Recall lebih rendah; membutuhkan two-stage re-ranking pass.

---

### 9. Best Practices & Standard Industri

Untuk memastikan semantic retrieval bekerja secara optimal di lingkungan produksi, terapkan standar teknis berikut:

*   **Penerapan Two-Stage Retrieval Pattern:**
    Jangan membebani Vector Database dengan mencoba mengekstraksi peringkat paling sempurna pada $K=5$.
    *   *Stage 1 (Bi-Encoder / ANN):* Ambil kandidat longgar ($K=50$ hingga $K=100$) menggunakan vector database dengan latensi ultra-cepat ($< 10\text{ ms}$).
    *   *Stage 2 (Cross-Encoder / Re-ranker):* Gunakan lightweight Cross-Encoder (seperti `bge-reranker-base` atau Cohere Rerank API) untuk menghitung granular self-attention antara query dan 50 kandidat teks tersebut, lalu potong menjadi Top-$5$ final untuk LLM context.
*   **Normalisasi Vektor Saat Ingest (Write-Time Normalization):**
    Selalu normalisasi vektor ke panjang satuan ($L_2\text{-norm} = 1.0$) sebelum disimpan ke dalam vector database. Ini mengubah operasi komputasi Cosine Similarity yang berat menjadi operasi Inner Product (Dot Product) murni, meningkatkan throughput sistem hingga 300% pada hardware berbasis SIMD AVX-512.
*   **Isolasi Metadata Payload dari Graph Index:**
    Jangan simpan metadata berukuran masif (seperti teks HTML dokumen utuh atau log JSON kompleks) langsung di dalam blok memory utama index graf HNSW. Simpan vektor dan Document ID pada High-Speed RAM Index, sedangkan teks dokumen dan metadata referensial disimpan pada persistent Document Store sekunder (seperti PostgreSQL, RocksDB, atau S3).
*   **Penyesuaian Dinamis Parameter Query:**
    Konfigurasikan vector database agar dapat menerima nilai `ef_search` yang dapat diubah saat runtime. Untuk workload asynchronous (batch agent, background processing), naikkan `ef_search` untuk mendapatkan recall maksimal. Untuk workload real-time user-facing, turunkan `ef_search` agar konsisten memenuhi latensi target $p99 < 15\text{ ms}$.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda bertugas membangun semantic retrieval engine mandiri untuk knowledge-base dokumentasi insiden DevOps. Sistem harus mampu mendeteksi korelasi semantik antara kueri gangguan sistem pengguna dengan arsip dokumen teknis lama tanpa bergantung pada kesamaan kata kunci (lexical matching).

#### Langkah-langkah Praktikum

1.  **Persiapan Environtment:**
    Buat virtual environment dan install library yang dibutuhkan:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install hnswlib numpy pydantic
    ```

2.  **Pembuatan File Skrip:**
    Buat script bernama `lab_semantic_retrieval.py` dan salin kode dari bagian **6. Production-Ready Code Implementation**.

3.  **Eksekusi Stress-Test:**
    Ubah blok eksekusi utama (`if __name__ == "__main__":`) untuk memvalidasi throughput indexing dan performa retrieval di bawah variasi ukuran dataset sintetis:
    ```python
    # Tambahkan di bagian akhir lab_semantic_retrieval.py
    if __name__ == "__main__":
        print("=== RUNNING ENTERPRISE RETRIEVAL BENCHMARK ===")
        dimension = 128
        dataset_size = 5_000
        
        embedder = DeterministicMockEmbeddingProvider(dimension=dimension)
        engine = ProductionSemanticEngine(embedding_provider=embedder, max_elements=dataset_size)
        
        print(f"\n1. Ingesting {dataset_size} synthetic documents...")
        synthetic_docs = [
            Document(
                doc_id=i,
                content=f"Log incident report telemetry error code ERR-{i*7 % 1000}: network failure",
                metadata={"severity": "critical" if i % 2 == 0 else "low"}
            )
            for i in range(dataset_size)
        ]
        
        t0 = time.perf_counter()
        engine.ingest_documents(synthetic_docs, batch_size=256)
        ingest_time = time.perf_counter() - t0
        print(f"Throughput Ingestion: {dataset_size / ingest_time:.2f} docs/sec")
        
        print("\n2. Executing Concurrent Filtered Search...")
        test_queries = [
            "database connection dropped unexpectedly",
            "critical network failure report",
            "telemetry failure memory limit",
            "server down due to out of memory error"
        ]
        
        latencies = []
        for q in test_queries:
            t_query = time.perf_counter()
            query_obj = SearchQuery(
                query_text=q,
                top_k=3,
                ef_search=64,
                metadata_filter={"severity": "critical"}
            )
            res = engine.retrieve(query_obj)
            latencies.append((time.perf_counter() - t_query) * 1000)
            
            assert len(res) <= 3
            for r in res:
                assert r.metadata["severity"] == "critical"
        
        print(f"\nSuccess! Average Latency: {np.mean(latencies):.3f} ms (p99: {np.percentile(latencies, 99):.3f} ms)")
    ```

4.  **Jalankan Verifikasi:**
    ```bash
    python lab_semantic_retrieval.py
    ```

#### Kriteria Keberhasilan (Validation Criteria)
*   **Zero Ingestion Errors:** Pipeline berhasil memasukkan 5.000 dokumen tanpa terjadi dimensional exception atau unhandled memory crash.
*   **Latency SLA Met:** Latensi kueri rata-rata berada di bawah ambang batas $15.0\text{ ms}$ pada local execution core.
*   **Metadata Filtering Integrity:** 100% dokumen yang dikembalikan oleh kueri yang terfilter secara valid memiliki atribut metadata `{"severity": "critical"}`.
*   **Deterministic Ranking:** Similarity score terikat rapi dalam rentang valid $[-1.0, 1.0]$ tanpa nilai `NaN` atau `Inf`.