# Kurikulum Enterprise: AI Product Builder
## Bab 03: Semantic Retrieval, Vector Databases, & Embedding
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Menganalisis dan mengonfigurasi algoritma Approximate Nearest Neighbor (ANN), khususnya Hierarchical Navigable Small World (HNSW) dan Inverted File with Product Quantization (IVF-PQ), berdasarkan metrik trade-off antara *recall*, *latency*, dan *memory footprint*.
*   Mengimplementasikan arsitektur hybrid retrieval production-grade yang menggabungkan *dense retrieval* (embedding berbasis transformer) dan *sparse retrieval* (BM25/SPLADE) menggunakan algoritma Reciprocal Rank Fusion (RRF).
*   Membangun pipeline *two-stage retrieval* dengan mengintegrasikan Bi-Encoder untuk pencarian kandidat awal berlatensi rendah dan Cross-Encoder untuk reranking dengan akurasi semantik tinggi.
*   Merancang arsitektur vector database enterprise yang mendukung *payload filtering* terindeks, isolasi data multi-tenant, dan partisi shard terdistribusi untuk jutaan hingga ratusan juta vektor.
*   Mengukur dan memitigasi degradasi performa (*catastrophic forgetting*, *graph saturation*, *filtered index exhaustion*) pada sistem pencarian vektor berkecepatan tinggi dengan SLA latency P99 < 50ms.

---

### 2. Prerequisite
Sebelum memulai modul ini, Anda wajib memiliki pemahaman mendalam dan lingkungan teknis berikut:
*   **Fondasi Teori**: Pemahaman vektor matematika (Dot Product, Cosine Similarity, Euclidean Distance), arsitektur Transformer dasar (Self-Attention mechanism).
*   **Software & Runtime**:
    *   Python `>= 3.11`
    *   Docker Engine `>= 24.0` & Docker Compose `>= 2.20`
*   **Dependensi Python**:
    *   `qdrant-client >= 1.8.0`
    *   `sentence-transformers >= 2.6.0`
    *   `torch >= 2.2.0`
    *   `rank-bm25 >= 0.2.2`
    *   `numpy >= 1.26.0`
    *   `pydantic >= 2.6.0`
*   **Infrastruktur**: Akses RAM minimal 8 GB (direkomendasikan 16 GB dengan GPU CUDA opsional untuk eksekusi Cross-Encoder).

---

### 3. Concept & Internal Architecture

Arsitektur sistem retrieval modern pada skala enterprise tidak hanya mengandalkan perhitungan Cosine Similarity secara brute-force ($\mathcal{O}(N \cdot D)$). Skala jutaan dokumen menuntut algoritma pengindeksan graf sub-linear dan pipeline berjenjang (*multi-stage retrieval*).

```
+---------------------------------------------------------------------------------------------------+
| PIPELINE RETRIEVAL DUA TAHAP (TWO-STAGE HYBRID RETRIEVAL ARCHITECTURE)                             |
+---------------------------------------------------------------------------------------------------+
                                       [ User Query ]
                                             |
                     +-----------------------+-----------------------+
                     |                                               |
                     v                                               v
       +----------------------------+                 +----------------------------+
       |   Dense Representation     |                 |   Sparse Representation    |
       |  (Bi-Encoder Embedding)    |                 |   (BM25 Token Inverted)    |
       +--------------+-------------+                 +--------------+-------------+
                      |                                              |
                      v                                              v
       +----------------------------+                 +----------------------------+
       |   ANN Vector Search        |                 |   Lexical Keyword Search   |
       |  (HNSW Layered Graph)      |                 |   (Inverted Index)         |
       +--------------+-------------+                 +--------------+-------------+
                      |                                              |
                      | Top-K Candidates (e.g., 50)                  | Top-K Candidates (e.g., 50)
                      +-----------------------+----------------------+
                                              |
                                              v
                              +-------------------------------+
                              | Reciprocal Rank Fusion (RRF)  |
                              | Score Normalization & Fusion  |
                              +---------------+---------------+
                                              |
                                              v Top-N Merged (e.g., 30)
                              +-------------------------------+
                              |    Cross-Encoder Reranker     |
                              |  (Full Joint Cross-Attention) |
                              +---------------+---------------+
                                              |
                                              v Top-M Final (e.g., 5)
                              +-------------------------------+
                              | Output Context to LLM / Client|
                              +-------------------------------+
```

#### 3.1. Algoritma ANN: HNSW (Hierarchical Navigable Small World)
HNSW menstrukturkan data vektor ke dalam graf multi-layer mirip dengan konsep data struktur *Skip-List*, namun diadaptasi untuk ruang berdimensi tinggi ($D$-dimensional space):
*   **Layer Teratas ($Layer_m$)**: Memiliki koneksi tepi (*edge*) yang panjang untuk melintasi ruang vektor dengan langkah besar (probabilitas simpul masuk ke layer tinggi ditentukan secara eksponensial $p = 1 / \ln(M)$).
*   **Layer Dasar ($Layer_0$)**: Berisi seluruh vektor data dengan koneksi lokal yang rapat untuk konvergensi presisi tinggi.
*   **Parameter Kunci**:
    *   $M$: Jumlah maksimum koneksi bidirectional per node. Semakin besar $M$, semakin tinggi akurasi graf pada ruang vektor berdimensi tinggi, dengan konsekuensi konsumsi memori membengkak ($\approx \mathcal{O}(N \cdot M)$).
    *   $efConstruction$: Ukuran dynamic candidate list saat proses komputasi indeks graf dibangun. Nilai tinggi memperlambat waktu *indexing* namun menghasilkan graf yang lebih mendekati topologi optimal.
    *   $efSearch$ (atau $ef$ runtime): Ukuran dynamic candidate list saat query dieksekusi. Meningkatkan $efSearch$ menaikkan metrik *Recall@K* dengan trade-off linear terhadap query latency.

#### 3.2. Kompresi Vektor: Scalar Quantization (SQ) vs Product Quantization (PQ)
Menyimpan vektor representasi mentah berdimensi tinggi (misal `1536` dimensi float32) memerlukan $1536 \times 4 \text{ bytes} = 6.144 \text{ KB}$ per vektor. Untuk 100 juta dokumen, ini membutuhkan lebih dari 600 GB RAM murni hanya untuk array vektor tanpa overhead graf HNSW.

1.  **Scalar Quantization (SQ8)**:
    Memetakan tiap nilai floating-point 32-bit ($[-1.0, 1.0]$) ke integer 8-bit ($[0, 255]$) menggunakan scaling linear:
    $$q = \text{round}\left(\frac{v - v_{min}}{v_{max} - v_{min}} \times 255\right)$$
    Mengurangi kebutuhan RAM sebesar 75% dengan penurunan recall umumnya di bawah 1-2%.
2.  **Product Quantization (PQ)**:
    Memecah ruang vektor $D$-dimensi menjadi $m$ sub-vektor independen berdimensi $d' = D/m$. Untuk tiap sub-ruang, algoritma $k$-means dijalankan untuk menemukan $k$ centroid (misal $k=256$, sehingga indeksnya muat dalam 1 byte). Vektor asli kemudian direpresentasikan hanya sebagai array berisi $m$ indeks byte. Reduksi memori dapat mencapai hingga 95%.

#### 3.3. Hybrid Search: Dense vs Sparse dan Reciprocal Rank Fusion (RRF)
Pencarian semantik murni (*dense*) sering kali gagal pada kata kunci spesifik seperti serial number, nomor model, atau akronim medis/legal langka (karena *out-of-vocabulary* atau kompresi semantik). Pencarian leksikal (*sparse* / BM25) sebaliknya gagal mengenali sinonim dan konteks umum.

Reciprocal Rank Fusion (RRF) menggabungkan peringkat dari sistem pencarian yang berbeda tanpa memerlukan normalisasi skor absolut yang sering kali tidak terkalibrasi:
$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
Di mana:
*   $M$ adalah kumpulan sistem retrieval (misal: dense dan BM25).
*   $r_m(d)$ adalah posisi peringkat (ranking) dokumen $d$ pada sistem $m$ (dimulai dari 1).
*   $k$ adalah konstanta perataan (smoothing constant), standar industri menetapkan $k \approx 60$. Konstanta ini mencegah dokumen yang berada di peringkat paling atas pada satu sistem mendominasi secara tidak adil jika sistem lain menilainya sangat buruk.

#### 3.4. Two-Stage Retrieval: Bi-Encoder vs Cross-Encoder
*   **Bi-Encoder**: Meng-encode dokumen dan query secara terpisah menjadi vektor independen $u = f(q)$ dan $v = g(d)$. Kesamaan dihitung menggunakan dot product $u \cdot v$. Sangat cepat ($\mathcal{O}(1)$ setelah komputasi vektor) dan cocok untuk menyeleksi 100 kandidat teratas dari miliaran data.
*   **Cross-Encoder**: Memasukkan query dan dokumen secara bersamaan ke dalam model transformer sebagai pasangan: $\text{Input} = \text{[CLS]} + q + \text{[SEP]} + d + \text{[SEP]}$. Mekanisme full self-attention berjalan melintasi seluruh token query dan dokumen sekaligus. Akurasi sangat tinggi, namun tidak dapat di-precompute secara offline; kompleksitas komputasinya adalah $\mathcal{O}((len(q) + len(d))^2)$ per kandidat, sehingga hanya feasible untuk reranking sejumlah kecil dokumen (top 20-50).

---

### 4. Why & What

#### Mengapa Brute Force Vector Search Gagal di Enterprise?
*   **Latency Collapse**: Brute-force scanning pada 10 juta vektor 1536-dimensi memerlukan komputasi jarak sebanyak 10 juta kali per query. Waktu komputasi melonjak hingga ratusan milidetik hingga detik, melanggar batas SLA aplikasi interaktif (P99 < 100ms).
*   **Memory Exhaustion**: Menyimpan vektor mentah dalam jumlah masif langsung pada memory (RAM) membutuhkan alokasi infrastruktur yang sangat mahal.

#### Mengapa Pure Semantic Retrieval Gagal?
*   **Vocabulary Mismatch**: Model embedding memadatkan makna. Pencarian teks seperti `"Part-XG-9902"` sering kali dipetakan berdekatan dengan `"Part-XG-9903"`, yang berpotensi fatal dalam ekosistem manufaktur atau logistik e-commerce.
*   **The "Lost in the Middle" Phenomenon**: Bi-Encoder sering kali melewatkan relasi token yang sangat spesifik yang hanya bisa dideteksi jika token query dan token target berinteraksi langsung dalam attention matrix.

#### Solusi Arsitektur
Arsitektur Enterprise menggabungkan:
1.  **Qdrant Vector Database** dengan integrasi HNSW + Scalar/Product Quantization untuk membatasi konsumsi memory sambil mempertahankan P99 sub-30ms.
2.  **Hybrid Indexing** (Sparse inverted index untuk exact matching + Dense HNSW untuk semantic intent).
3.  **Cross-Encoder Reranker** untuk memfilter noise dari candidate generation sebelum masuk ke context window LLM, secara drastis menaikkan metrik *Context Precision* dan menurunkan konsumsi token LLM.

---

### 5. How (Workflow Detail)

Berikut adalah alur end-to-end pemrosesan data (Ingestion) dan pemrosesan query (Retrieval):

#### Data Ingestion Pipeline:
1.  **Document Chunking**: Memecah dokumen mentah menjadi chunk berbasis semantik (bukan sekadar pemotongan token kaku).
2.  **Dual Representation Generation**:
    *   Eksekusi model embedding Bi-Encoder untuk menghasilkan dense vector.
    *   Eksekusi tokenisasi & frekuensi term untuk menghasilkan sparse vector (BM25/SPLADE format).
3.  **Quantization & Serialization**: Vektor di-quantize jika mengaktifkan SQ8/PQ.
4.  **Payload Index Creation**: Metadata (seperti `tenant_id`, `created_at`, `category`) didaftarkan ke payload inverted index Qdrant sebelum upsert agar filtering berjalan instan.
5.  **Batched Upsert**: Vektor diunggah ke vector database menggunakan batching berbasis memory/size.

#### Dynamic Retrieval & Reranking Pipeline:
1.  **Query Decomposition**: Query dari user diekstrak menjadi representasi dense dan sparse.
2.  **Parallel Execution**:
    *   Dense query diarahkan ke HNSW graph dengan parameter filtering metadata terpasang (*pre-filtering*).
    *   Sparse query diarahkan ke sparse inverted index dengan metadata filter yang sama.
3.  **Result Aggregation**: Mengambil kandidat top-$K$ dari masing-masing index (misal $K=50$).
4.  **Reciprocal Rank Fusion**: Menggabungkan kedua list kandidat menjadi satu set terurut berukuran $N$ (misal $N=30$) berdasarkan skor RRF.
5.  **Cross-Encoder Scoring**: Pasangan `(query, document_text)` dari ke-30 dokumen dimasukkan ke model Cross-Encoder.
6.  **Top-M Pruning**: Memilih $M$ dokumen terbaik (misal $M=5$) dengan threshold skor relevansi absolut untuk diserahkan ke generator LLM.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Sistem Pencarian Dokumen Arsip Perusahaan Multinasional
*   **Dense Embedding**: Seperti asisten riset yang membaca intisari dokumen dan mengelompokkan binder berdasarkan kesamaan tema filosofis (misal: "efisiensi energi" diletakkan dekat dengan "pengurangan limbah").
*   **Sparse Index (BM25)**: Seperti indeks alfabetis di halaman belakang buku ensiklopedia. Anda langsung mencari kode paten "US-99128-B" dan langsung diarahkan ke halaman spesifik tanpa peduli tema dokumen.
*   **HNSW**: Seperti jaringan jalan raya berjenjang. Anda naik jalan tol lintas provinsi (Layer teratas) untuk mendekati kota tujuan, keluar ke jalan arteri utama (Layer tengah), lalu masuk ke jalan kompleks perumahan (Layer 0) hingga tepat di depan rumah target.
*   **RRF**: Dewan juri independen yang mengompilasi rekomendasi asisten riset dan pustakawan alfabetis tanpa memperdebatkan skala penilaian subjektif masing-masing; cukup melihat urutan prioritas yang disepakati bersama.
*   **Cross-Encoder**: Detektif forensik yang membedah kata-demi-kata dari 5 kandidat dokumen terpilih secara mendalam untuk memastikan dokumen tersebut benar-benar memvalidasi hipotesis kasus yang sedang diteliti.

#### ASCII Diagram: Arsitektur HNSW Graph Layering
```
Layer 2 (Expressway):    [Node A] -----------------------------------------> [Node Z]
                            |                                                   |
Layer 1 (Arterial):      [Node A] -------------> [Node K] -----------------> [Node Z]
                            |                       |                           |
Layer 0 (Local Roads):   [Node A] -> [Node C] -> [Node K] -> [Node P] ----> [Node Z]
                           \          /            \          /            /
                            [Node B]-+              [Node L]-+      [Node Y]
```

---

### 7. Simple Example & Practical Example

#### 7.1 Simple Example: Menghitung Estimasi Memori Vektor vs Quantization
Skrip utilitas untuk menghitung alokasi RAM murni yang dibutuhkan index sebelum deployment.

```python
def calculate_vector_memory(num_vectors: int, dimensions: int, index_type: str = "float32") -> dict:
    """
    Menghitung estimasi konsumsi RAM untuk koleksi vektor.
    index_type options: 'float32', 'sq8', 'pq' (dengan asumsi sub-vector compression 8x)
    """
    bytes_per_dim = {
        "float32": 4.0,
        "sq8": 1.0,
        "pq": 0.5  # Asumsi kompresi agresif 1 byte per 2 dimensi
    }
    
    if index_type not in bytes_per_dim:
        raise ValueError(f"Tipe indeks tidak dikenali: {index_type}")
        
    raw_vector_bytes = num_vectors * dimensions * bytes_per_dim[index_type]
    
    # Overhead HNSW graph (~M koneksi per simpul, tipikal M=16, 8 bytes per link pointer)
    hnsw_overhead_bytes = num_vectors * 16 * 8
    
    total_bytes = raw_vector_bytes + hnsw_overhead_bytes
    total_mb = total_bytes / (1024 ** 2)
    total_gb = total_bytes / (1024 ** 3)
    
    return {
        "vectors_count": num_vectors,
        "dimensions": dimensions,
        "index_type": index_type,
        "raw_data_mb": round(raw_vector_bytes / (1024 ** 2), 2),
        "hnsw_overhead_mb": round(hnsw_overhead_bytes / (1024 ** 2), 2),
        "total_ram_gb": round(total_gb, 3)
    }

if __name__ == "__main__":
    print("Estimasi RAM (10 Juta Vektor, 1536 Dimensi):")
    print("Raw Float32 :", calculate_vector_memory(10_000_000, 1536, "float32"))
    print("Scalar Quant (SQ8):", calculate_vector_memory(10_000_000, 1536, "sq8"))
```

#### 7.2 Practical Example: Enterprise Hybrid Retrieval & Cross-Encoder Pipeline
Kode berikut mengimplementasikan integrasi hybrid search berbasis dense + sparse retrieval, payload filtering multi-tenant, Reciprocal Rank Fusion, dan Cross-Encoder reranking secara modular dan *production-ready*.

Pastikan service Qdrant lokal berjalan:
```bash
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant:v1.8.4
```

```python
import os
import uuid
from typing import List, Dict, Any, Optional
import numpy as np
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

# ---------------------------------------------------------
# Skema Data & Model Validasi
# ---------------------------------------------------------
class DocumentChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RetrievalResult(BaseModel):
    chunk_id: str
    content: str
    score: float
    tenant_id: str
    metadata: Dict[str, Any]

# ---------------------------------------------------------
# Engine Hybrid Search Enterprise
# ---------------------------------------------------------
class EnterpriseHybridRetriever:
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_name: str = "enterprise_knowledge_base",
        dense_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        
        # Load bi-encoder dense embedding
        self.dense_model = SentenceTransformer(dense_model_name)
        self.dense_dim = self.dense_model.get_sentence_embedding_dimension()
        
        # Load cross-encoder reranker
        self.reranker = CrossEncoder(reranker_model_name)
        
        # In-memory Sparse Store untuk implementasi referensi BM25
        self.corpus_chunks: List[DocumentChunk] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        
        self._initialize_collection()

    def _initialize_collection(self) -> None:
        """Membuat koleksi dengan konfigurasi HNSW dan Scalar Quantization."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.dense_dim,
                    distance=qmodels.Distance.COSINE
                ),
                # Konfigurasi HNSW tingkat lanjut
                hnsw_config=qmodels.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000
                ),
                # Optimasi Memori: Scalar Quantization (SQ8)
                quantization_config=qmodels.ScalarQuantization(
                    scalar=qmodels.ScalarQuantizationConfig(
                        type=qmodels.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True
                    )
                )
            )
            # Wajib mengindeks payload field untuk pre-filtering berkecepatan tinggi
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="tenant_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )

    def ingest_documents(self, documents: List[DocumentChunk]) -> None:
        """Ingest dokumen secara sinkron ke Qdrant dan Corpus BM25."""
        if not documents:
            return

        texts = [doc.content for doc in documents]
        embeddings = self.dense_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        
        points = []
        for doc, emb in zip(documents, embeddings):
            points.append(
                qmodels.PointStruct(
                    id=doc.id,
                    vector=emb.tolist(),
                    payload={
                        "tenant_id": doc.tenant_id,
                        "content": doc.content,
                        "metadata": doc.metadata
                    }
                )
            )
            
            # Update sparse internal memory
            self.corpus_chunks.append(doc)
            self.tokenized_corpus.append(doc.content.lower().split())

        # Upsert dense vectors ke Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True
        )
        
        # Re-index BM25
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def _dense_search(self, query: str, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Pencarian dense vector dengan filter multi-tenant terindeks."""
        query_vector = self.dense_model.encode(query, convert_to_numpy=True).tolist()
        
        search_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=tenant_id)
                )
            ]
        )
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=limit,
            search_params=qmodels.SearchParams(
                hnsw_ef=64,  # Runtime search precision
                exact=False
            )
        )
        
        return [
            {
                "id": str(r.id),
                "content": r.payload["content"],
                "metadata": r.payload["metadata"],
                "tenant_id": r.payload["tenant_id"],
                "score": r.score
            }
            for r in results
        ]

    def _sparse_search(self, query: str, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Pencarian sparse (lexical) dengan filter manual multi-tenant."""
        if not self.bm25:
            return []

        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        
        ranked_indices = np.argsort(scores)[::-1]
        
        results = []
        for idx in ranked_indices:
            doc = self.corpus_chunks[idx]
            if doc.tenant_id == tenant_id:
                results.append({
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "tenant_id": doc.tenant_id,
                    "score": float(scores[idx])
                })
            if len(results) >= limit:
                break
                
        return results

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """Algoritma penggabungan peringkat RRF."""
        rrf_scores: Dict[str, float] = {}
        doc_store: Dict[str, Dict[str, Any]] = {}

        # Evaluasi peringkat dense
        for rank, doc in enumerate(dense_results, start=1):
            doc_id = doc["id"]
            doc_store[doc_id] = doc
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

        # Evaluasi peringkat sparse
        for rank, doc in enumerate(sparse_results, start=1):
            doc_id = doc["id"]
            if doc_id not in doc_store:
                doc_store[doc_id] = doc
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank))

        # Urutkan berdasarkan skor kumulatif RRF tertinggi
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        fused_results = []
        for doc_id in sorted_ids:
            item = doc_store[doc_id]
            fused_results.append({
                **item,
                "rrf_score": rrf_scores[doc_id]
            })
            
        return fused_results

    def search(
        self,
        query: str,
        tenant_id: str,
        top_k_candidates: int = 30,
        final_top_n: int = 5
    ) -> List[RetrievalResult]:
        """
        End-to-End Pipeline:
        1. Dense ANN Retrieval + Sparse Retrieval (Paralel)
        2. Reciprocal Rank Fusion
        3. Cross-Encoder Reranking
        """
        dense_res = self._dense_search(query=query, tenant_id=tenant_id, limit=top_k_candidates)
        sparse_res = self._sparse_search(query=query, tenant_id=tenant_id, limit=top_k_candidates)
        
        fused = self._reciprocal_rank_fusion(dense_res, sparse_res, k=60)
        candidates = fused[:top_k_candidates]
        
        if not candidates:
            return []

        # Tahap Reranking menggunakan Cross-Encoder
        pairs = [[query, c["content"]] for c in candidates]
        cross_scores = self.reranker.predict(pairs)
        
        for candidate, cross_score in zip(candidates, cross_scores):
            candidate["final_cross_score"] = float(cross_score)
            
        # Urutkan berdasarkan Cross-Encoder score descending
        candidates.sort(key=lambda x: x["final_cross_score"], reverse=True)
        
        final_results = []
        for item in candidates[:final_top_n]:
            final_results.append(
                RetrievalResult(
                    chunk_id=item["id"],
                    content=item["content"],
                    score=item["final_cross_score"],
                    tenant_id=item["tenant_id"],
                    metadata=item["metadata"]
                )
            )
            
        return final_results

# ---------------------------------------------------------
# Eksekusi Demo / Uji Coba Verifikasi
# ---------------------------------------------------------
if __name__ == "__main__":
    retriever = EnterpriseHybridRetriever()
    
    mock_data = [
        DocumentChunk(
            tenant_id="enterprise_bank_a",
            content="Peraturan Kepatuhan PCI-DSS Versi 4.0: Persyaratan otentikasi multi-faktor wajib diterapkan pada seluruh akses administratif.",
            metadata={"source": "compliance_handbook_v4.pdf"}
        ),
        DocumentChunk(
            tenant_id="enterprise_bank_a",
            content="Prosedur penanganan insiden keamanan siber level P1: Tim incident response wajib mengisolasi node dalam tempo 15 menit.",
            metadata={"source": "sop_security_2024.pdf"}
        ),
        DocumentChunk(
            tenant_id="enterprise_bank_b",
            content="Instruksi kerja pemulihan backup database Oracle untuk lingkungan staging dan testing internal.",
            metadata={"source": "oracle_dba_guide.pdf"}
        ),
        DocumentChunk(
            tenant_id="enterprise_bank_a",
            content="Dokumen panduan audit internal: Standar verifikasi MFA (Multi-Factor Authentication) untuk sistem perbankan inti.",
            metadata={"source": "audit_guideline.pdf"}
        )
    ]
    
    print("[+] Ingesting data uji coba...")
    retriever.ingest_documents(mock_data)
    
    query_input = "Kewajiban penggunaan autentikasi MFA untuk admin compliance"
    print(f"\n[+] Mengeksekusi Hybrid Search + Reranker untuk: '{query_input}' (Tenant: enterprise_bank_a)...")
    
    results = retriever.search(
        query=query_input,
        tenant_id="enterprise_bank_a",
        top_k_candidates=5,
        final_top_n=2
    )
    
    for idx, r in enumerate(results, 1):
        print(f"\n--- Hasil #{idx} ---")
        print(f"ID        : {r.chunk_id}")
        print(f"Skor Final: {r.score:.4f}")
        print(f"Sumber    : {r.metadata.get('source')}")
        print(f"Konten    : {r.content}")
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Temu Kembali Dokumen Regulasi Finansial Multinasional (50 Juta Dokumen)
*   **Profil Beban Kerja**:
    *   Ukuran Korpus: 50.000.000 dokumen/fragmen kontrak finansial, regulasi, dan log audit perbankan.
    *   Ukuran Vektor: 1536 Dimensi (OpenAI `text-embedding-3-small` / Cohere V3).
    *   Beban Kueri: 450 QPS (Queries Per Second) saat jam kerja bursa saham.
    *   Target SLA: Latency P99 $< 65\text{ ms}$, Recall@5 $> 95\%$.
    *   Kepatuhan: Isolasi ketat multi-tenant data berbasis wilayah hukum (Jurisdiction Filter).

#### Kegagalan Desain Awal (Post-Filtering Bottleneck)
Arsitektur awal mengeksekusi pencarian vektor secara global kemudian melakukan pemfilteran metadata di lapisan aplikasi (*post-filtering*).
```
[Query + Filter (Jurisdiction: "ID")] 
    --> Search Top-100 HNSW Global 
    --> Filter lokal: doc.jurisdiction == "ID"
```
*   **Bencana Performa**: Jika dokumen bernilai `"ID"` hanya menyusun 0.5% dari seluruh data global, pencarian Top-100 secara global sering kali menghasilkan 0 dokumen yang lolos filter (*filtered exhaust problem*), menyebabkan `Recall = 0%`. Ketika limit dinaikkan ke Top-5000, latency P99 meroket hingga $1.200\text{ ms}$ dan server OOM (*Out-of-Memory*).

#### Solusi Arsitektur Produksi
1.  **Single-Stage Payload Inverted Filtering**:
    Mengkonfigurasi Qdrant dengan Payload Schema bertipe `keyword` untuk atribut `jurisdiction_id` dan `tenant_id`. Graph traversal HNSW kini menggunakan *filtered descent*: traversal graph hanya melompati simpul-simpul yang memenuhi kondisi boolean payload secara native di dalam C++ core engine.
2.  **Product Quantization + Memory-Mapped Files (mmap)**:
    Mengaktifkan `Product Quantization (PQ)` dengan rasio kompresi 8x dikombinasikan dengan penyimpanan berbasis file yang di-mmap ke disk NVMe. 
    *   Kebutuhan RAM drop drastis dari **307 GB RAM** menjadi hanya **38.4 GB RAM**.
3.  **Cross-Encoder Worker Pool Sharding**:
    Cross-Encoder model di-deploy terpisah di balik cluster Triton Inference Server dengan GPU Nvidia T4 yang didedikasikan secara asynchronous, mengeksekusi dynamic micro-batching untuk komputasi reranker dari 30 kandidat dalam waktu $< 18\text{ ms}$.

---

### 9. Trade-offs

| Dimensi Arsitektur | Opsi A | Opsi B | Analisis Trade-off |
| :--- | :--- | :--- | :--- |
| **Penyimpanan Vektor** | **Float32 Uncompressed** | **Scalar Quantization (SQ8)** | Float32 memberikan recall 100% dari model asal tanpa distorsi quantization, namun memakan 4x lipat RAM. SQ8 mengorbankan $\sim 1\%$ recall demi pemotongan biaya infrastruktur server RAM sebesar 75%. |
| **Metode Retrieval** | **Dense-Only Search** | **Hybrid Search (Dense + Sparse/BM25)** | Dense-only menghemat komputasi dan memori mesin sparse, namun gagal total saat mencari keyword langka, kode error, atau nama produk kustom. Hybrid menjamin fault tolerance presisi leksikal dengan penambahan kompleksitas arsitektur pipeline. |
| **Candidate Scoring** | **Bi-Encoder Cosine Only** | **Two-Stage (Bi-Encoder + Cross-Encoder)** | Bi-encoder sangat cepat ($\approx 5\text{ ms}$), tetapi rawan *false positive* semantik. Two-stage menaikkan akurasi/relevansi kontekstual hingga 30-40%, tetapi mengorbankan latency tambahan ($\approx 15-40\text{ ms}$) dan beban compute inferensi GPU. |
| **Graph Density ($M$)** | **Low $M$ (e.g., $M=8$)** | **High $M$ (e.g., $M=64$)** | Nilai $M$ kecil menghemat RAM dan mempercepat build index, namun rentan terjebak dalam local minima saat ANN traversal (recall rendah). Nilai $M$ besar menjamin recall tinggi, tetapi ukuran memory graf membengkak dan throughput write (upsert) melambat drastis. |
| **Metadata Filtering** | **Post-Filtering** | **Pre-Filtering (Payload Indexing)** | Post-filtering mudah diimplementasikan tanpa index metadata tambahan, namun gagal total pada *high selectivity* (bisa mengembalikan 0 result). Pre-filtering native menjamin kestabilan recall namun butuh alokasi indexing disk/memory tambahan. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Metric Space Inconsistency
*   **Gejala**: Hasil pencarian mengembalikan data yang sama sekali tidak relevan meskipun similarity score tampak tinggi (atau sebaliknya bernilai negatif tak lazim).
*   **Akar Masalah**: Model embedding menghasilkan vektor yang di-training menggunakan *Cosine Similarity* (vektor di-normalisasi ke unit length $||v|| = 1$), namun vector database di-konfigurasi menggunakan *Euclidean Distance ($L2$)* atau *Dot Product* tanpa normalisasi awal.
*   **Solusi**: Pastikan metrik jarak di konfigurasi database identik dengan target loss function model:
    ```python
    # Normalisasi vektor jika menggunakan Dot Product sebagai proksi Cosine
    vector = vector / np.linalg.norm(vector)
    ```

#### 2. The Filtered Exhaustion Trap (Index Starvation)
*   **Gejala**: Latency query melonjak drastis dari 10ms menjadi 800ms ketika user menambahkan filter metadata tertentu yang sangat spesifik (misal: `status == "ARCHIVED"` yang hanya mencakup 0.01% korpus).
*   **Akar Masalah**: Tanpa payload index, HNSW graph terpaksa menjelajahi ribuan node yang tidak cocok sebelum menemukan tetangga yang memenuhi filter payload (*graph saturation*).
*   **Solusi**: Wajib mendaftarkan index payload eksplisit pada database (seperti skema `PayloadSchemaType.KEYWORD` di Qdrant) sehingga mesin dapat memilih secara dinamis antara graf descent atau inverted list scan berdasarkan selektivitas payload (Query Planner optimization).

#### 3. Cold Cache Latency Spikes (mmap Paging)
*   **Gejala**: Query pertama setelah periode sepi memakan waktu $> 1.5\text{ detik}$, sedangkan query berulang berikutnya hanya memakan waktu $15\text{ ms}$.
*   **Akar Masalah**: Indeks yang disimpan dengan mekanisme memory-mapped file (`mmap`) terlempar keluar dari OS Page Cache (*page fault*) karena aktivitas sistem operasi lainnya.
*   **Solusi**: Konfigurasi parameter `always_ram=True` untuk quantization index atau jalankan background daemon crawler (warmup script) untuk mempertahankan halaman memori tetap reside di RAM.

---

### 11. Best Practices (Production Checklist)

#### Pre-Production & Sizing:
- [ ] Hitung estimasi alokasi RAM index graf HNSW dengan rumus: $\text{RAM} \approx N \times (D \times \text{Bytes} + M \times 8 \times 2)$.
- [ ] Terapkan Scalar Quantization (SQ8) secara default untuk semua dataset di atas 5 juta baris kecuali use-case mensyaratkan toleransi error absolut 0%.
- [ ] Tentukan threshold pemutusan (score cut-off) pada Cross-Encoder output untuk membuang chunk yang tidak relevan secara semantik sebelum diproses LLM.

#### Arsitektur & Reliability:
- [ ] Pisahkan instance Vector Database (I/O & Memory intensive) dengan Cross-Encoder Inference Engine (GPU compute intensive).
- [ ] Selalu isolasi tenant data menggunakan Filtered HNSW Payload Indexes, bukan dengan membuat satu database collection terpisah per tenant jika jumlah tenant mencapai ribuan (mencegah *resource descriptor exhaustion*).
- [ ] Atur $efSearch$ secara dinamis: gunakan nilai rendah (misal `ef=32`) untuk kueri live non-kritis dan nilai tinggi (misal `ef=128`) untuk pipeline analitik/batch.

#### Observabilitas & Monitoring:
- [ ] Monitor metrik **Recall@K** secara berkala menggunakan synthetic ground-truth dataset untuk mendeteksi degradasi index akibat drift data.
- [ ] Pasang alert Prometheus/Grafana pada metrik `P99 Latency`, `Vector Index RAM Usage`, dan `Disk I/O Wait Percentage`.

---

### 12. Hands-on Practice

Buat direktori dan file berikut di workspace Anda: `hands-on/m02/production_retriever.py`

#### Langkah 1: Persiapan Environment
Jalankan perintah berikut di terminal:
```bash
mkdir -p hands-on/m02
cd hands-on/m02
python3 -m venv venv
source venv/bin/activate
pip install qdrant-client sentence-transformers rank-bm25 numpy pydantic torch
```

#### Langkah 2: Jalankan Vector Database Engine
```bash
docker run -d --name qdrant-lab -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.8.4
```

#### Langkah 3: Implementasi Benchmarking Skrip
Tuliskan kode berikut ke dalam `hands-on/m02/production_retriever.py`. Skrip ini melakukan ingestion otomatis 500 dokumen sintetis, mengeksekusi hybrid search vs dense-only search, dan mengukur perbedaan latency serta relevance ranking.

```python
# hands-on/m02/production_retriever.py
import time
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

def run_benchmark():
    print("[1] Inisialisasi Qdrant Client...")
    client = QdrantClient(host="localhost", port=6333)
    collection_name = "benchmark_eval"
    
    # Reset collection jika sudah ada
    client.delete_collection(collection_name=collection_name)
    
    print("[2] Membuat Collection dengan Scalar Quantization...")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE),
        hnsw_config=qmodels.HnswConfigDiff(m=16, ef_construct=100),
        quantization_config=qmodels.ScalarQuantization(
            scalar=qmodels.ScalarQuantizationConfig(
                type=qmodels.ScalarType.INT8,
                quantile=0.99,
                always_ram=True
            )
        )
    )
    
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    
    print("[3] Melakukan generasi 500 dokumen sintetis...")
    synthetic_docs = [
        f"Dokumen finansial nomor seri FX-{i:04d} membahas mengenai kebijakan suku bunga dan manajemen risiko likuiditas perbankan pasar terbuka."
        for i in range(500)
    ]
    # Sisipkan dokumen kunci untuk pengujian akurasi
    target_uuid = str(uuid.uuid4())
    synthetic_docs.append(
        "KODE RAHASIA X-999: Dokumen otentikasi darurat server pusat perbankan bawah tanah Jakarta."
    )
    
    embeddings = model.encode(synthetic_docs, show_progress_bar=True, batch_size=64)
    
    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()) if idx < 500 else target_uuid,
            vector=emb.tolist(),
            payload={"text": doc, "idx": idx}
        )
        for idx, (doc, emb) in enumerate(zip(synthetic_docs, embeddings))
    ]
    
    print("[4] Upserting vektor ke Qdrant...")
    client.upsert(collection_name=collection_name, points=points, wait=True)
    
    # Query Uji Coba: Mencari dokumen kunci dengan keyword spesifik
    test_query = "KODE RAHASIA X-999 otentikasi darurat"
    query_vector = model.encode(test_query).tolist()
    
    print(f"\n[5] Mengeksekusi Query: '{test_query}'")
    start_time = time.perf_counter()
    search_results = client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=5,
        search_params=qmodels.SearchParams(hnsw_ef=64)
    )
    latency_ms = (time.perf_counter() - start_time) * 1000
    
    print(f"--> Eksekusi selesai dalam: {latency_ms:.2f} ms")
    print(f"--> Total kandidat ditemukan: {len(search_results)}")
    for idx, hit in enumerate(search_results, 1):
        print(f"    Rank #{idx} [Score: {hit.score:.4f}] Doc ID: {hit.id}")
        print(f"    Konten: {hit.payload['text'][:80]}...")

if __name__ == "__main__":
    run_benchmark()
```

#### Langkah 4: Jalankan dan Amati Output
```bash
python production_retriever.py
```

---

### 13. Exercise

#### Level Easy
Ubah implementasi `calculate_vector_memory` pada Section 7.1 untuk menghitung ukuran memori jika menggunakan model embedding 768 dimensi (misal: `sentence-transformers/all-mpnet-base-v2`) dengan jumlah 1.000.000 vektor untuk float32 vs SQ8. Hitung berapa megabyte RAM yang dihemat.

#### Level Medium
Tambahkan parameter dynamic score thresholding pada method `search` di kelas `EnterpriseHybridRetriever` (Section 7.2). Jika skor absolut Cross-Encoder berada di bawah nilai $0.1$, dokumen tersebut wajib dieliminasi secara otomatis dari hasil return, terlepas dari nilai parameter `final_top_n`.

#### Level Hard
Modifikasi class `EnterpriseHybridRetriever` agar mengimplementasikan **Reciprocal Rank Fusion (RRF)** terdistribusi asinkron menggunakan pustaka `asyncio` dan client `AsyncQdrantClient`. Tahap `_dense_search` dan `_sparse_search` harus berjalan secara paralel menggunakan `asyncio.gather()` untuk meminimalkan wall-clock latency keseluruhan.

---

### 14. Challenge

**Studi Kasus**: Anda memimpin tim engineering pada platform SaaS LegalTech yang melayani 2.000 firma hukum independen. Total ada 150 juta halaman klausul kontrak yang harus dapat ditelusuri.

**Batasan Masalah**:
1.  **Multi-Tenancy Skala Masif**: Setiap kueri *wajib* terisolasi 100% per klien (`firm_id`). Tidak boleh ada kebocoran data sekecil apa pun antar firma hukum.
2.  **Data Skew**: Firma hukum terbesar memiliki 25 juta dokumen, sedangkan firma hukum terkecil hanya memiliki 500 dokumen.
3.  **Strict Performance SLA**: P99 Latency tidak boleh melampaui $45\text{ ms}$ pada beban 300 QPS.
4.  **Hardware Budget Limit**: Server dibatasi dengan RAM maksimal 128 GB.

**Tugas Arsitektur Anda**:
*   Rancang strategi partisi (*sharding strategy*) koleksi vector database untuk mengatasi data skew tanpa menyebabkan hot-shard issue.
*   Pilihlah kombinasi kompresi vektor (Float32 vs SQ8 vs PQ) yang dapat menjaga seluruh index 150 juta vektor 1024-dimensi agar muat di bawah batas RAM 128 GB.
*   Tentukan strategi index payload filtering dan rancang penanganan kasus ekstrem jika firma hukum terbesar mengeksekusi filter klausul yang mengeliminasi 99.9% datanya sendiri. Tuliskan blueprint teknis ini dalam bentuk dokumen arsitektur komprehensif tanpa implementasi instan.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama konstanta perataan $k$ (biasanya bernilai 60) pada formula Reciprocal Rank Fusion (RRF)?
   * A. Mengalikan skor Cosine Similarity agar seimbang dengan BM25.
   * B. Mencegah dokumen yang berada di peringkat 1 pada satu mesin pencari mendominasi secara tidak proporsional terhadap mesin pencari lainnya.
   * C. Mengubah representasi dense vector menjadi sparse vector.
   * D. Menentukan batas maksimal dokumen yang dapat di-rerank oleh Cross-Encoder.

2. Kompresi Scalar Quantization (SQ8) memetakan nilai float 32-bit ke representasi integer berapa bit?
   * A. 16-bit
   * B. 4-bit
   * C. 8-bit
   * D. 1-bit (Binary)

3. Mengapa algoritma HNSW (Hierarchical Navigable Small World) jauh lebih cepat daripada Brute-Force K-Nearest Neighbor?
   * A. Karena HNSW menghapus dimensi vektor yang tidak penting.
   * B. Karena HNSW melompati perbandingan jarak pada mayoritas data dengan menavigasi graf berjenjang berstruktur skip-list dengan kompleksitas $\mathcal{O}(\log N)$.
   * C. Karena HNSW mengonversi seluruh teks menjadi token BM25 secara otomatis.
   * D. Karena HNSW hanya berjalan pada hardware GPU berbasis Tensor Core.

4. Manakah model di bawah ini yang memproses query dan dokumen secara bersamaan ke dalam satu transformer attention matrix?
   * A. Bi-Encoder
   * B. Sparse Inverted Index
   * C. Cross-Encoder
   * D. HNSW Graph Dispatcher

5. Apa dampak menaikkan parameter runtime $efSearch$ pada pencarian graf HNSW?
   * A. Recall meningkat, namun latency query meningkat.
   * B. Recall menurun, namun memori RAM berkurang.
   * C. Waktu pembuatan indeks (indexing time) melambat secara permanen.
   * D. Dimensi vektor otomatis terpotong menjadi setengahnya.

#### Bagian 2: Intermediate (Pilihan Ganda & Analisis Pendek)
6. Manakah konfigurasi indexing payload yang paling optimal di Qdrant untuk filtering kolom `tenant_id` berformat UUID string?
   * A. Full-text payload index
   * B. Keyword payload index
   * C. Integer payload index
   * D. Tidak perlu payload index, gunakan post-filtering saja.

7. Mengapa Cross-Encoder **tidak** digunakan untuk memindai seluruh 10 juta dokumen dari database secara langsung?
   * A. Karena Cross-Encoder menghasilkan output vektor yang tidak kompatibel dengan HNSW.
   * B. Karena kompleksitas komputasinya adalah $\mathcal{O}(N \times (len(q)+len(d))^2)$ yang memerlukan komputasi forward-pass transformer berbiaya komputasi masif dan tidak bisa di-precompute secara offline.
   * C. Karena Cross-Encoder memiliki akurasi yang lebih rendah daripada Bi-Encoder.
   * D. Karena Cross-Encoder hanya mendukung bahasa Inggris.

8. Fenomena apa yang terjadi jika Anda melakukan post-filtering pada HNSW dengan kriteria filter yang sangat langka (selectivity 0.01%)?
   * A. Graph fragmentation error
   * B. Filtered exhaust problem (hasil retrieval kosong atau latency melonjak tajam karena scanner kehabisan node valid)
   * C. Overfitting pada lapisan layer teratas HNSW
   * D. Payload index collision

9. Pada skenario apa sparse search (BM25) secara konsisten mengungguli dense semantic search?
   * A. Mencari padanan sinonim abstrak (misal: "kendaraan roda empat" vs "mobil sedan").
   * B. Menemukan teks dalam skenario lintas bahasa (*cross-lingual transfer*).
   * C. Mencari entitas spesifik dengan format kaku seperti Serial Number mesin, UUID error trace, atau nama senyawa kimia unik.
   * D. Meringkas inti sari topik dari sebuah paragraf naratif panjang.

10. Jika dataset Anda memiliki 10.000.000 vektor dengan dimensi 1536 (Float32), berapa estimasi memori RAM murni yang dibutuhkan *hanya untuk array vektor* tanpa menghitung overhead graf HNSW?
    * A. $\approx 15.36\text{ GB}$
    * B. $\approx 61.44\text{ GB}$
    * C. $\approx 122.88\text{ GB}$
    * D. $\approx 4.80\text{ GB}$

#### Bagian 3: Skenario Kasus Produksi
11. **Skenario 1**: Tim engineering Anda melaporkan bahwa setelah mengaktifkan Product Quantization (PQ) dengan kompresi agresif (sub-vector 16x), latency query turun drastis, namun metrik kepuasan pengguna (NDCG@10) anjlok hingga 25%. Investigasi membuktikan vektor telah terdistorsi secara ekstrem. Langkah remediasi arsitektur apa yang harus diambil tanpa harus kembali menanggung biaya 100% Float32 RAM?
12. **Skenario 2**: Sebuah sistem pencarian hybrid (Dense + BM25) menggunakan Cross-Encoder reranker. Namun, latency P99 mencapai $350\text{ ms}$ (melebihi SLA $100\text{ ms}$). Analisis profil CPU menunjukkan bahwa tahap Dense + BM25 hanya memakan waktu $18\text{ ms}$, RRF memakan waktu $2\text{ ms}$, namun Cross-Encoder memakan waktu $330\text{ ms}$ untuk mengevaluasi 100 dokumen kandidat. Bagaimana Anda merekayasa ulang alur reranking ini agar SLA P99 $< 60\text{ ms}$ tercapai?
13. **Skenario 3**: Sebuah bank mengimplementasikan vector database untuk FAQ internal dan dokumen rahasia dewan direksi dalam satu koleksi yang sama. Pengembang menggunakan *post-filtering* di backend API untuk membuang dokumen bertanda `confidential: true` jika user bukan direktur. Jelaskan celah keamanan fatal (*security flaw*) dan risiko operasional dari pendekatan ini!

---

### Kunci Jawaban & Pembahasan Evaluasi

#### Bagian 1: Basic
1.  **B**: Konstanta perataan $k$ (smoothing factor) mencegah satu retrieval list mendominasi total skor secara mutlak bila suatu dokumen menempati ranking 1 pada salah satu list namun terlempar sangat jauh pada list lainnya.
2.  **C**: Scalar Quantization (SQ8) memetakan float 32-bit menjadi 8-bit unsigned/signed integer ($[0, 255]$ atau $[-128, 127]$).
3.  **B**: HNSW mengeksploitasi struktur graf Small World berjenjang sehingga traversal rute kandidat meloncat melintasi layer atas secara efisien dengan kompleksitas sub-linear $\mathcal{O}(\log N)$.
4.  **C**: Cross-Encoder menyatukan teks query dan teks dokumen ke dalam satu sequence token input tunggal yang dievaluasi secara serentak oleh full self-attention matrix.
5.  **A**: Parameter $efSearch$ memperbesar ukuran list tetangga terdekat dinamis saat runtime pencarian graf; semakin besar nilainya, semakin banyak path graf yang dievaluasi (Recall naik), tetapi memakan lebih banyak siklus CPU (Latency naik).

#### Bagian 2: Intermediate
6.  **B**: `Keyword payload index` dioptimalkan untuk exact string matching berkecepatan tinggi (seperti ID, UUID, kategori), berbeda dengan full-text search yang melibatkan tokenisasi kata.
7.  **B**: Melakukan forward pass pasangan query-dokumen sebanyak 10 juta kali pada transformer utuh secara online saat query masuk membutuhkan waktu berjam-jam per query, menjadikannya mustahil untuk candidate retrieval skala besar.
8.  **B**: Filtered exhaust problem terjadi ketika algoritma ANN menelusuri ratusan branch graf HNSW namun terbentur karena node-node terdekat secara geometris tidak lolos filter metadata lokal, berujung pada starvation kandidat atau fallback brute-force scan.
9.  **C**: BM25 unggul telak pada pencarian exact term/token langka (seperti kode serial, nomor plat, formula) yang embedding transformer-nya tidak pernah mempelajari token tersebut secara spesifik atau memadatkan representasinya menjadi noise semantik.
10. **B**: Perhitungan: $10.000.000 \text{ vektor} \times 1536 \text{ dimensi} \times 4 \text{ bytes (Float32)} = 61.440.000.000 \text{ bytes} \approx 61.44\text{ GB}$.

#### Bagian 3: Skenario Kasus Produksi
11. **Pembahasan Skenario 1**:
    Solusi ideal adalah beralih dari Product Quantization (PQ) ke **Scalar Quantization (SQ8)** yang hanya memotong presisi numerik tiap dimensi tanpa mengelompokkan sub-ruang dimensi menjadi centroid artifisial. SQ8 mempertahankan akurasi recall hingga $> 98-99\%$ dari Float32 murni namun tetap memberikan penghematan RAM sebesar 75%. Opsi kedua adalah mengaktifkan mode **Over-sampling / Rescoring**: Gunakan representasi PQ terkompresi untuk mengambil kandidat Top-100 dengan cepat, lalu lakukan re-score instan terhadap Top-100 tersebut menggunakan vektor Float32 asli yang disimpan di media disk NVMe (bukan di RAM) sebelum diteruskan ke tahap berikutnya.
12. **Pembahasan Skenario 2**:
    Langkah mitigasi:
    *   **Pangkas Kandidat Input Reranker**: Kurangi ukuran kandidat dari 100 dokumen menjadi 20-30 dokumen saja. Penurunan dari 100 ke 30 dokumen akan memotong beban komputasi Cross-Encoder hingga $\approx 70\%$, membawa latency reranking ke kisaran $\approx 30-40\text{ ms}$.
    *   **Model Distillation / Quantization**: Ganti model Cross-Encoder besar dengan varian yang lebih terdistilasi (misal: `cross-encoder/ms-marco-TinyBERT-L-2-v2`) atau terapkan kuantisasi int8/ONNX Runtime dengan TensorRT execution provider pada GPU untuk mempercepat inference throughput Cross-Encoder hingga 3-5x lipat.
13. **Pembahasan Skenario 3**:
    *   **Celah Keamanan & Kebocoran Informasi (Side-Channel / Information Leakage)**: Pada post-filtering, Vector Database tetap mengembalikan data rahasia ke memori aplikasi API sebelum dipangkas. Jika terjadi unhandled error, miskonfigurasi log payload, atau bug pada layer routing aplikasi, dokumen rahasia tersebut dapat bocor ke client.
    *   **Risiko Operasional (Degradasi Recall Fatal)**: Jika Top-K vektor semantik teratas seluruhnya didominasi oleh dokumen rahasia dewan direksi, maka fungsi post-filtering backend API akan menghapus seluruh Top-K tersebut. Hasil akhirnya: User non-direktur menerima respons kosong (`No results found`), padahal ada ribuan dokumen FAQ publik valid yang relevan di urutan berikutnya. Solusi mutlak: Terapkan **Pre-Filtering Native di dalam Database Engine** atau pisahkan koleksi secara terisolasi berdasarkan privilege level.

---

### 16. Summary
*   Arsitektur retrieval production-grade enterprise menolak ketergantungan pada single-method retrieval; sistem modern dibangun di atas paradigma **Two-Stage Hybrid Search**.
*   **HNSW** menyediakan algoritma traversal graf terdesentralisasi berbasis layer dengan waktu query sub-linear $\mathcal{O}(\log N)$, di mana tuning parameter $M$, $efConstruction$, dan $efSearch$ secara langsung mengatur spektrum trade-off antara throughput, latency, dan recall.
*   **Scalar Quantization (SQ8)** memotong overhead memori sebesar 75% dengan dampak degradasi recall yang minimal, menjadikannya standar baku penyimpanan in-memory berskala masif dibanding uncompressed Float32.
*   **Hybrid Fusion (RRF)** menjembatani kelemahan mendasar Dense Retrieval terhadap exact match (kata kunci unik/kode serial) dengan mengawinkan peringkat invarian dari Sparse Inverted Index (BM25).
*   **Cross-Encoder Reranking** berfungsi sebagai gerbang presisi akhir yang memanfaatkan full cross-attention mechanism untuk memangkas noise konteks sebelum disuplai ke arsitektur LLM, memastikan context window hanya diisi oleh fragmen yang terbukti memiliki relevansi informasi paling tinggi.