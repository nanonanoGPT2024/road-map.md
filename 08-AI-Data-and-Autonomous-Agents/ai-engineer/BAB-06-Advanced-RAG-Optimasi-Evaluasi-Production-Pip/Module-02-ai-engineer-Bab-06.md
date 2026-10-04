# BAB 06: Advanced RAG, Optimasi, Evaluasi & Production Pipeline
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Arsitektur Advanced Retrieval**: Membangun hybrid search pipeline yang menggabungkan sparse representation (BM25/SPLADE) dan dense representation (HNSW vector index) menggunakan algoritma *Reciprocal Rank Fusion* (RRF).
2. **Mengoptimalkan Context Window**: Mengimplementasikan teknik *Parent-Document Retrieval*, *Sentence-Window Retrieval*, dan *Cross-Encoder Re-ranking* untuk memaksimalkan *signal-to-noise ratio* (SNR) sebelum konteks disuplai ke LLM.
3. **Membangun Query Transformation Engine**: Mengembangkan query rewriter, *Hypothetical Document Embeddings* (HyDE), dan dynamic routing berbasis semantic classification.
4. **Mengotomasi Evaluasi Kualitas RAG**: Mengintegrasikan framework evaluasi RAGAS/TruLens ke dalam CI/CD pipeline untuk mengukur metrik *Context Recall*, *Context Precision*, *Faithfulness*, dan *Answer Relevance*.
5. **Menyusun Arsitektur Produksi Skala Enterprise**: Menerapkan asynchronous execution, semantic caching (Redis), distributed vector indexing, observability (OpenInference/Langfuse), serta guardrails untuk mencegah data leakage dan hallucination pada SLA sub-detik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, Anda harus memahami:
- **Dasar RAG**: Konsep chunking dasar (fixed-size, recursive character), embedding generation, dan naive vector search (Cos-Sim/Dot-Product).
- **Python Lanjutan**: Pemrograman asynchronous (`asyncio`), `typing` lanjutan, dan validasi schema data dengan `pydantic` v2.
- **Vector Database**: Pengalaman praktis dengan minimal satu vector store enterprise (Qdrant, Milvus, atau pgvector).
- **Statistika & Aljabar Linear**: Memahami cosine similarity, Euclidean distance, probabilitas relevansi (IR metrics: MRR, NDCG@K, Recall@K).
- **Infrastructure**: Pemahaman dasar tentang Redis, Docker, dan arsitektur microservices.

---

### 3. Concept & Internal Architecture

Naive RAG (Retrieve $\rightarrow$ Augment $\rightarrow$ Generate) rentan terhadap beberapa kegagalan struktural pada skala enterprise:
1. **Low Retrieval Precision/Recall**: Pertanyaan ambigu atau variasi terminologi industri menyebabkan vector search meleset (misal: "EBITDA" vs "Pendapatan Operasional sebelum Depresiasi").
2. **Lost in the Middle**: LLM gagal mengekstrak fakta penting ketika konteks terlalu panjang (>8K tokens) dan informasi target berada di tengah-tengah dokumen.
3. **Hallucination via Noisy Context**: Memasukkan seluruh chunk dokumen yang sebagian besar tidak relevan memicu bias konfirmasi pada LLM.

Untuk mengatasi ini, arsitektur **Advanced RAG** memisahkan query ingestion, indexing, retrieval, reranking, synthesis, dan evaluation ke dalam layer terpisah:

```
[User Query] 
     │
     ▼
[Layer 1: Query Transformation Engine]
 ├── Query Expansion / Decomposition
 ├── HyDE (Hypothetical Document Embeddings)
 └── Dynamic Semantic Router 
     │
     ▼
[Layer 2: Hybrid Retrieval Engine]
 ├── Dense Search: HNSW Index (Cosine/Dot-Product Embeddings)
 └── Sparse Search: Inverted Index (BM25 / SPLADE)
     │
     ▼
[Layer 3: Fusion & Reranking]
 ├── Reciprocal Rank Fusion (RRF)
 └── Cross-Encoder Re-ranker (e.g., BGE-Reranker-Large)
     │
     ▼
[Layer 4: Context Refinement]
 ├── Parent-Document Expansion / Sentence Windowing
 └── Contextual Compression & Deduplication
     │
     ▼
[Layer 5: Generation & Guardrails]
 ├── LLM Synthesis via Streaming
 └── Hallucination & PII Guardrails (NeMo / Self-Correction)
     │
     ▼
[Layer 6: Continuous Evaluation & Observability]
 └── Tracing (Langfuse/Arize) & Evaluasi Metrik RAG Triad (RAGAS)
```

#### Komponen Internal Utama:

1. **Reciprocal Rank Fusion (RRF)**:
   Algoritma skoring untuk menggabungkan hasil peringkat dari beberapa sistem penelusuran (misal: BM25 dan Dense Search) tanpa perlu normalisasi skor probabilitas secara manual:
   $$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
   Di mana $M$ adalah himpunan metode retrieval (sparse & dense), $r_m(d)$ adalah peringkat dokumen $d$ pada metode $m$, dan $k$ adalah konstanta smoothing (standar industri: $k = 60$).

2. **Cross-Encoder vs Bi-Encoder Architecture**:
   - **Bi-Encoder**: Meng-encode query dan dokumen secara terpisah menjadi vektor tunggal ($u = f(q)$ dan $v = f(d)$). Cepat ($O(1)$ lookup via ANN), tetapi kehilangan interaksi antar-token query dan dokumen (*shallow interaction*).
   - **Cross-Encoder**: Menginput query dan dokumen secara bersamaan ke dalam Transformer: $\text{Score} = \text{Softmax}(W \cdot \text{Transformer}([CLS] + q + [SEP] + d + [SEP]))$. Menghasilkan *full-cross-attention* antar setiap token query dan dokumen. Sangat akurat namun lambat secara komputasi. Oleh karena itu, Cross-Encoder hanya digunakan sebagai **Re-ranker** untuk *Top-N* (misal Top-20) dokumen hasil filter Bi-Encoder.

3. **Parent-Document Retrieval**:
   Memisahkan unit data untuk *pencarian* dan unit data untuk *generasi konteks*. 
   - Chunk kecil (misal: 100-200 token) di-embed untuk indexing agar semantic boundary tetap tajam.
   - Setiap chunk kecil memiliki metadata pointer menuju Parent Chunk atau Full Document (misal: 1000-2000 token).
   - Saat chunk kecil cocok dengan kueri, Parent Chunk yang utuh ditarik untuk diberikan kepada LLM, memastikan konteks tidak terpotong secara artifisial.

---

### 4. Why & What

| Fitur / Strategi | Masalah yang Diselesaikan (Why) | Apa yang Diimplementasikan (What) |
|---|---|---|
| **Hybrid Search (Dense + Sparse)** | Dense search buruk dalam pencarian kata kunci eksak, kode produk, error traces, nama orang/entitas langka. | Kombinasi HNSW (vektor dense) + BM25/SPLADE (sparse inverted index) yang disatukan via RRF. |
| **HyDE (Hypothetical Document Embeddings)** | Query pengguna sering kali pendek, berupa pertanyaan, dan berbeda secara semantik dengan chunk dokumen yang berupa pernyataan jawaban. | Meminta LLM menghasilkan draft jawaban hipotetis, lalu meng-embed draft tersebut untuk mencari dokumen riil. |
| **Cross-Encoder RERANKING** | Cosine similarity pada Bi-Encoder menghasilkan false positive tinggi pada semantik yang mirip tetapi bertentangan secara logika. | Scoring ulang $N$ dokumen teratas menggunakan cross-attention transformer model untuk akurasi presisi tinggi. |
| **Parent-Document Retrieval** | Dilema chunk size: Chunk kecil akurat dalam retrieval tapi miskin konteks generasi; chunk besar kaya konteks tapi mencemari embedding space. | Indexing dilakukan pada child chunks (granular), retrieval menyajikan parent chunks (holistik). |
| **RAGAS Automated Evaluation** | Menghilangkan subjektivitas manusia dalam mengevaluasi RAG; mendeteksi regresi performa saat model/chunking diubah. | Pipeline otomatis mengukur 4 metrik RAG Triad: Context Precision, Context Recall, Faithfulness, Answer Relevance. |

---

### 5. How (Workflow Detail)

Alur kerja operasional Advanced RAG pada sistem produksi terbagi menjadi dua pipeline utama:

#### A. Pipeline Indexing (Asynchronous Ingestion)
1. **Document Loading & Normalization**: Ekstraksi teks mentah dari PDF, HTML, atau database enterprise; pembersihan whitespace dan standardisasi encoding.
2. **Hierarchical Splitting**: 
   - Dokumen dipecah menjadi Parent Chunks ($1500$ token dengan overlap $150$ token).
   - Setiap Parent Chunk dipecah lagi menjadi beberapa Child Chunks ($300$ token dengan overlap $50$ token).
3. **Dual Storage Indexing**:
   - Child Chunks di-embed menggunakan embedding model (misal: `text-embedding-3-large` atau `bge-large-en-v1.5`) dan disimpan di Vector DB beserta metadata `parent_id`.
   - Child Chunks atau Parent Chunks di-index ke BM25 Inverted Index Engine (Elasticsearch/Qdrant sparse vectors).
   - Parent Chunks disimpan dalam persistent key-value store (PostgreSQL/Redis/S3).

#### B. Pipeline Query Execution (Real-Time Ingestion & Synthesis)
1. **Query Pre-Processing**:
   - Query masuk diverifikasi melalui Semantic Cache (Redis). Jika cache hit (cosine similarity query $> 0.96$), kembalikan respon seketika.
   - Jika cache miss, lakukan Query Rewriting & Expansion (membuat variasi kueri atau HyDE document).
2. **Parallel Hybrid Retrieval**:
   - Eksekusi Dense Search di Vector DB mengambil top-50 kandidat.
   - Eksekusi Sparse Search di BM25/Sparse Index mengambil top-50 kandidat.
3. **Fusion (RRF)**:
   - Hitung skor RRF untuk seluruh kandidat yang ditemukan di kedua hasil pencarian.
   - Filter menjadi top-20 kandidat gabungan.
4. **Re-ranking**:
   - Feed top-20 pasangan `(Query, Child Chunk)` ke Cross-Encoder model.
   - Urutkan dan ambil top-5 hasil dengan skor cross-encoder tertinggi.
5. **Context Expansion**:
   - Ambil `parent_id` dari top-5 child chunks tersebut dari Document Store.
   - Lakukan deduplikasi Parent Chunks agar konteks tidak redundan.
6. **Synthesis & Guardrails**:
   - Bangun system prompt berbasis konteks hasil deduplikasi.
   - Panggil LLM via async stream generator.
   - Lakukan pengecekan validasi output secara paralel menggunakan guardrail model untuk memitigasi halusinasi dan kebocoran PII.

---

### 6. Analogy & Diagram ASCII

#### Analogi Perpustakaan Riset Enterprise
Bayangkan Anda adalah direktur riset yang membutuhkan informasi regulasi spesifik dari ribuan bundel dokumen:
- **Naive RAG**: Anda menyuruh anak magang mencari paragraf yang memuat kata-kata mirip pertanyaan Anda, lalu langsung menyalin paragraf tersebut tanpa membaca konteks babnya. Hasilnya sering kali salah kaprah.
- **Advanced RAG**:
  - **HyDE**: Anda meminta analis senior menulis draf ringkas seperti apa kira-kira bentuk dokumen regulasi tersebut jika ada.
  - **Hybrid Search**: Tim arsip mencari di indeks katalog berdasarkan kata kunci eksak nomor undang-undang (Sparse/BM25) dan sekaligus mencari berdasarkan tema umum (Dense/Vector).
  - **RRF & Reranker**: Seorang kurator ahli membaca top-20 bundel yang dikumpulkan dan menyusun ulang berdasarkan relevansi faktual paling tajam (Cross-Encoder).
  - **Parent Document**: Dokumen yang diserahkan kepada Anda bukanlah potongan robekan kertas 2 kalimat, melainkan 1 pasal utuh yang melingkupi robekan tersebut agar Anda memahami duduk perkaranya secara komprehensif.

```
+─────────────────────────────────────────────────────────────────────────────+
|                         QUERY EXECUTION WORKFLOW                            |
+─────────────────────────────────────────────────────────────────────────────+
                                  [User Query]
                                       │
                        ┌──────────────┴──────────────┐
                        ▼                             ▼
                 [Sparse Search]               [Dense Search]
                  (BM25/SPLADE)                 (HNSW Index)
                  Top-K: [D1, D3, D5]           Top-K: [D2, D1, D7]
                        │                             │
                        └──────────────┬──────────────┘
                                       ▼
                     [Reciprocal Rank Fusion (RRF)]
                            Top-N: [D1, D2, D3, D5]
                                       │
                                       ▼
                       [Cross-Encoder Re-Ranker]
                   (Full Cross-Attention Scoring)
                            Top-M: [D2, D1]
                                       │
                                       ▼
                    [Parent Document / Window Expansion]
                    Fetch full contexts: [Parent_D2, Parent_D1]
                                       │
                                       ▼
                           [LLM Generation + Guard]
                                       │
                                       ▼
                              [Synthesized Response]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Manual Reciprocal Rank Fusion (RRF) Implementation
Contoh implementasi algoritma RRF tanpa framework eksternal:

```python
from typing import List, Dict, Any

def reciprocal_rank_fusion(
    results_list: List[List[Dict[str, Any]]], 
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Menggabungkan beberapa daftar dokumen terurut menggunakan Reciprocal Rank Fusion.
    
    Args:
        results_list: List dari daftar hasil penelusuran (tiap hasil memiliki 'id' dan 'content')
        k: Parameter smoothing constant (default: 60)
    """
    rrf_scores: Dict[str, float] = {}
    doc_lookup: Dict[str, Dict[str, Any]] = {}

    for results in results_list:
        for rank, doc in enumerate(results):
            doc_id = doc["id"]
            if doc_id not in doc_lookup:
                doc_lookup[doc_id] = doc
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            # Algoritma RRF: 1 / (k + rank)
            rrf_scores[doc_id] += 1.0 / (k + (rank + 1))

    # Urutkan dokumen berdasarkan akumulasi RRF score secara descending
    sorted_doc_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    fused_results = []
    for doc_id in sorted_doc_ids:
        doc = doc_lookup[doc_id]
        doc["rrf_score"] = rrf_scores[doc_id]
        fused_results.append(doc)

    return fused_results

# Demonstrasi
bm25_hits = [{"id": "docA", "text": "foo"}, {"id": "docB", "text": "bar"}]
dense_hits = [{"id": "docB", "text": "bar"}, {"id": "docC", "text": "baz"}]

fused = reciprocal_rank_fusion([bm25_hits, dense_hits], k=60)
print("Top Document ID:", fused[0]["id"], "| RRF Score:", round(fused[0]["rrf_score"], 5))
# Output menempatkan docB sebagai juara karena muncul di kedua sistem penelusuran
```

#### B. Practical Example: Production-Grade Advanced RAG Engine
Kode di bawah menerapkan:
- Hierarchical Parent-Child Ingestion
- Hybrid Retrieval (Inverted Index BM25 + Qdrant Vector Client)
- Cross-Encoder Re-Ranking (`sentence-transformers/cross-encoder`)
- Context Extraction

```python
import os
import uuid
import asyncio
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field

# Mock or real clients depending on ecosystem
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

@dataclass
class DocumentChunk:
    chunk_id: str
    parent_id: str
    content: str
    metadata: Dict[str, Any]

class AdvancedRAGEngine:
    def __init__(self, qdrant_client: AsyncQdrantClient, collection_name: str = "enterprise_rag"):
        self.client = qdrant_client
        self.collection_name = collection_name
        self.parent_store: Dict[str, str] = {} # Mock external key-value store (e.g. Redis/S3)
        self.bm25_corpus: List[str] = []
        self.bm25_doc_map: List[str] = [] # index to chunk_id
        self.bm25_engine: BM25Okapi = None
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    async def initialize_schema(self, vector_dim: int = 384):
        """Inisialisasi koleksi vector store jika belum tersedia."""
        collections = await self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)
        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
            )

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    async def index_documents(
        self, 
        raw_documents: List[Dict[str, str]], 
        embed_fn: Any
    ) -> None:
        """
        Melakukan splitting hierarchical (parent-child), indexing sparse BM25, 
        dan asynchronous batch indexing vector embeddings.
        """
        points = []
        tokenized_corpus = []

        for doc in raw_documents:
            parent_id = str(uuid.uuid4())
            self.parent_store[parent_id] = doc["text"]

            # Simulasi splitting parent ke 2 child chunks
            midpoint = len(doc["text"]) // 2
            chunks = [doc["text"][:midpoint], doc["text"][midpoint:]]

            for chunk_text in chunks:
                chunk_id = str(uuid.uuid4())
                
                # Setup BM25 Sparse Index
                self.bm25_corpus.append(chunk_text)
                self.bm25_doc_map.append(chunk_id)
                tokenized_corpus.append(self._tokenize(chunk_text))

                # Create Vector Embedding
                vector = embed_fn(chunk_text)
                
                points.append(PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk_id,
                        "parent_id": parent_id,
                        "content": chunk_text
                    }
                ))

        self.bm25_engine = BM25Okapi(tokenized_corpus)
        await self.client.upsert(collection_name=self.collection_name, points=points)

    def _sparse_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        tokens = self._tokenize(query)
        scores = self.bm25_engine.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "chunk_id": self.bm25_doc_map[idx],
                "content": self.bm25_corpus[idx],
                "sparse_score": scores[idx]
            })
        return results

    async def _dense_search(self, query_vector: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        search_res = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k
        )
        return [
            {
                "chunk_id": hit.payload["chunk_id"],
                "parent_id": hit.payload["parent_id"],
                "content": hit.payload["content"],
                "dense_score": hit.score
            }
            for hit in search_res
        ]

    def _reciprocal_rank_fusion(
        self, 
        dense_results: List[Dict[str, Any]], 
        sparse_results: List[Dict[str, Any]], 
        k: int = 60
    ) -> List[Dict[str, Any]]:
        fused_scores = {}
        lookup = {}

        for rank, item in enumerate(dense_results):
            cid = item["chunk_id"]
            lookup[cid] = item
            fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (k + rank + 1))

        for rank, item in enumerate(sparse_results):
            cid = item["chunk_id"]
            if cid not in lookup:
                lookup[cid] = item
            fused_scores[cid] = fused_scores.get(cid, 0.0) + (1.0 / (k + rank + 1))

        sorted_ids = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
        return [lookup[cid] for cid in sorted_ids]

    async def retrieve(
        self, 
        query: str, 
        query_vector: List[float], 
        top_n_final: int = 3
    ) -> List[str]:
        """Eksekusi hybrid search -> RRF -> Cross-Encoder Reranking -> Parent Expansion."""
        # 1. Parallel Hybrid Retrieval
        dense_task = self._dense_search(query_vector, top_k=10)
        sparse_matches = self._sparse_search(query, top_k=10)
        dense_matches = await dense_task

        # 2. Reciprocal Rank Fusion
        fused_candidates = self._reciprocal_rank_fusion(dense_matches, sparse_matches, k=60)
        top_candidates = fused_candidates[:10]

        if not top_candidates:
            return []

        # 3. Cross-Encoder Re-ranking
        cross_inputs = [[query, c["content"]] for c in top_candidates]
        rerank_scores = self.reranker.predict(cross_inputs)
        
        for idx, score in enumerate(rerank_scores):
            top_candidates[idx]["cross_score"] = float(score)

        # Urutkan berdasarkan Cross-Encoder output score
        top_candidates.sort(key=lambda x: x["cross_score"], reverse=True)
        refined_candidates = top_candidates[:top_n_final]

        # 4. Context Expansion ke Parent Document & Deduplikasi
        final_contexts = []
        seen_parents = set()

        for c in refined_candidates:
            pid = c.get("parent_id")
            if pid and pid in self.parent_store:
                if pid not in seen_parents:
                    final_contexts.append(self.parent_store[pid])
                    seen_parents.add(pid)
            else:
                final_contexts.append(c["content"])

        return final_contexts

# Driver Code Asinkron Sederhana
async def main():
    import numpy as np
    
    # Inisialisasi Mock Qdrant In-Memory
    client = AsyncQdrantClient(":memory:")
    engine = AdvancedRAGEngine(qdrant_client=client)
    await engine.initialize_schema(vector_dim=4)

    # Dummy embedding function
    def dummy_embed(text: str) -> List[float]:
        np.random.seed(abs(hash(text)) % (2**32))
        return np.random.rand(4).tolist()

    docs = [
        {"text": "Pedoman Penanganan Insiden Keamanan Siber PT Teknologi Maju. Langkah pertama adalah isolasi node terdampak melalui network firewall. Selanjutnya, tim forensik mendokumentasikan log sistem."},
        {"text": "Kebijakan Pengembalian Dana E-Commerce. Pengguna berhak mengajukan refund dalam waktu 14 hari kerja setelah barang diterima oleh pembeli jika segel belum rusak."},
    ]

    await engine.index_documents(docs, embed_fn=dummy_embed)
    query = "Bagaimana isolasi insiden siber dilakukan?"
    contexts = await engine.retrieve(query=query, query_vector=dummy_embed(query), top_n_final=1)
    
    print("\n--- RETRIEVED PARENT CONTEXT ---")
    print(contexts[0])

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Sistem Tanya Jawab Kepatuhan Finansial Terdistribusi (FinTech Multi-Regional)
- **Kondisi Awal**: Sistem Naive RAG melayani 50.000 auditor internal untuk querying 4.000.000 lembar dokumen audit PDF, transaksi SWIFT, dan regulasi OJK/BI.
- **Masalah**:
  1. *Akurasi Jeblok*: Pencarian regulasi spesifik (misal: "POJK No. 12/POJK.03/2017") gagal total di dense retrieval karena nama dokumen tidak memiliki semantic variance.
  2. *Latensi Membengkak*: P99 latency menyentuh 9.8 detik karena chunk dokumen terlalu besar (2.048 token) dikirimkan secara mentah ke GPT-4.
  3. *Hallucination Rate*: 14.2% jawaban mengandung fabrikasi hukum yang salah interpretasi.

#### Solusi Implementasi:
1. **Hybrid Retrieval**: Membangun index ganda menggunakan Qdrant (HNSW untuk dense semantics) dan Elasticsearch (BM25 token-exact analyzer dengan custom regex tokenizer untuk pasal hukum).
2. **Context Window Refinement**: Sentence-window retrieval dengan window size $\pm 3$ sentences di sekitar kalimat paling relevan, menurunkan rata-rata token konteks dari 4.000 menjadi 850 token.
3. **Cross-Encoder Filtering**: Menggunakan model `bge-reranker-large` terdistribusi via Triton Inference Server dengan latency SLA $< 45\text{ ms}$.
4. **Evaluation Loop**: Implementasi pipeline evaluasi otomatis mingguan menggunakan RAGAS terhadap golden test dataset 1.200 pasang Q&A kepatuhan.

#### Hasil Arsitektur Baru:
- **P99 Latency**: Turun dari $9.8\text{ s}$ menjadi $1.7\text{ s}$ (efisiensi 82.6%).
- **Context Recall**: Meningkat dari 61% ke 94.8%.
- **Hallucination Rate**: Berkurang drastis dari 14.2% menjadi 0.8% (diverifikasi via metrik *Faithfulness* RAGAS $> 0.95$).

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                    [Bi-Encoder Dense Only]
                            ▲
                           / \
     (Lowest Latency,     /   \   (Highest Accuracy,
      Low Accuracy)      /     \   High Latency, High Cost)
                        /       \
                       ▼─────────▼
    [Hybrid + RRF]                 [Hybrid + RRF + Cross-Encoder]
```

| Dimensi | Naive Vector RAG | Hybrid Search (RRF) | Hybrid + Re-ranking + Parent Exp. |
|---|---|---|---|
| **P95 Latency** | **$150\text{ ms} - 400\text{ ms}$** (Cepat) | **$300\text{ ms} - 650\text{ ms}$** | **$800\text{ ms} - 2.5\text{ s}$** (Butuh optimasi GPU/Quantization) |
| **Retrieval Recall** | Rendah - Sedang ($\approx 60-70\%$) | Tinggi ($\approx 80-88\%$) | **Sangat Tinggi ($>95\%$)** |
| **Token Cost (LLM)** | Tinggi (Banyak chunk sampah masuk konteks) | Sedang | **Sangat Efisien** (Hanya signal murni yang dikirim) |
| **Infrastructure Complexity** | Rendah (Cukup 1 Vector DB) | Sedang (Sinkronisasi Dual-Index) | **Tinggi** (Vector DB + Document Store + Model Reranker Serving) |
| **Compute Overhead** | Ringan (CPU standard) | Ringan ke Sedang | **Berat** (Inference Re-ranker butuh GPU/VNNI support) |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Skor Normalisasi pada Hybrid Search
- **Gejala**: Salah satu retrieval (BM25 atau Vector) mendominasi hasil pencarian secara mutlak.
- **Root Cause**: Menggabungkan raw score BM25 (rentang $0 \rightarrow \infty$) langsung dengan Cosine Similarity (rentang $-1 \rightarrow 1$) menggunakan perkalian atau penjumlahan bobot sederhana tanpa normalisasi min-max.
- **Solusi**: Gunakan **Reciprocal Rank Fusion (RRF)** karena algoritma ini hanya memproses *urutan peringkat (rank)* dan independen terhadap skala skor internal masing-masing engine.

#### 2. Cross-Encoder Bottleneck Mematikan Throughput API
- **Gejala**: CPU API server menyentuh 100%, request timeout melonjak tajam saat traffic naik.
- **Root Cause**: Melakukan re-ranking terhadap terlalu banyak kandidat (misal $K = 100$) menggunakan library PyTorch langsung di dalam web worker process (FastAPI/Gunicorn).
- **Solusi**: 
  - Batasi input reranker maksimal $15-25$ dokumen.
  - Offload inferensi Cross-Encoder ke microservice terpisah (Triton/vLLM/TEI) dengan dynamic batching dan hardware acceleration (ONNX Runtime, TensorRT).

#### 3. Sentence-Window Retrieval Menghasilkan Out-of-Order Text
- **Gejala**: Konteks yang diterima LLM meloncat-loncat dan tata bahasanya rusak.
- **Root Cause**: Saat mengambil sentence window ($[-k, +k]$), chunk hasil pencarian tidak diurutkan kembali berdasarkan index posisi kemunculannya di dokumen asli.
- **Solusi**: Pastikan chunk metadata menyimpan integer `chunk_index`. Urutkan chunk terpilih berdasarkan `chunk_index` sebelum digabungkan menjadi string prompt akhir.

---

### 11. Best Practices (Production Checklist)

- [ ] **Chunking Tailored to Domain**: Jangan gunakan fixed character chunking untuk teks berstruktur. Gunakan *MarkdownHeaderTextSplitter* untuk dokumentasi teknis atau *HTMLSemanticSplitter* untuk web parsing.
- [ ] **Deterministic Chunk Hashing**: Hitung `sha256(chunk_content)` sebagai Chunk ID untuk menghindari duplikasi record saat ingestion ulang berjalan.
- [ ] **Metadata Stripping**: Pastikan metadata yang tidak relevan dengan query LLM dibuang sebelum context injection untuk menghemat token dan context clutter.
- [ ] **Semantic Caching**: Pasang Redis Semantic Caching di layer paling depan. Lewatkan RAG pipeline seutuhnya jika query baru memiliki kemiripan semantik $\ge 0.96$ dengan query terdahulu.
- [ ] **Context Length Budgeting**: Pasang hard-limit pada context window (misal: konteks RAG maksimal 60% dari kapasitas context window model) untuk menyisakan ruang bagi chain-of-thought dan respon keluaran.
- [ ] **Asynchronous Concurrency**: Semua pemanggilan I/O (Database fetch, Embedding API, LLM API) harus dieksekusi menggunakan asynchronous workers (`asyncio.gather` atau background tasks).
- [ ] **Observability Spans**: Emit tracing logs open-telemetry (OpenInference) pada tiap tahap: Retrieval Latency, Rerank Scores, Input Token Count, Output Token Count, dan Groundedness Flag.

---

### 12. Hands-on Practice

Buatlah direktori praktikum dan berkas pengujian berikut:

#### Struktur Proyek:
```bash
hands-on/m02/
├── requirements.txt
├── rag_pipeline.py
├── test_evaluation.py
└── data/
    └── knowledge_base.json
```

#### Langkah 1: Persiapan Environment
Tuliskan dependensi pada `hands-on/m02/requirements.txt`:
```text
qdrant-client>=1.7.0
sentence-transformers>=2.3.0
rank-bm25>=0.2.2
ragas>=0.1.0
datasets>=2.14.0
pydantic>=2.5.0
```
Instalasi melalui terminal:
```bash
pip install -r hands-on/m02/requirements.txt
```

#### Langkah 2: Buat Dataset Pengetahuan Sederhana
Simpan berkas `hands-on/m02/data/knowledge_base.json`:
```json
[
  {
    "id": "KB-001",
    "text": "Prosedur Failover Database: Ketika node utama PostgreSQL mengalami crash, Sentinel akan memicu promosi node Read-Replica menjadi Master dalam durasi maksimal 30 detik. Selama proses ini, aplikasi akan mengaktifkan read-only circuit breaker untuk mencegah inkonsistensi transaksi data keuangan."
  },
  {
    "id": "KB-002",
    "text": "Audit Trail Logging: Setiap perubahan skema database dan akses ke data pelanggan wajib dicatat ke dalam server Syslog terpusat yang bersifat Write-Once Read-Many (WORM). Retensi log ini adalah 7 tahun sesuai regulasi standar ISO 27001."
  }
]
```

#### Langkah 3: Eksekusi Evaluasi Pipeline Menggunakan RAGAS
Buat berkas evaluasi `hands-on/m02/test_evaluation.py`:
```python
import os
import pytest
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevance, context_precision

def test_rag_pipeline_quality():
    """
    Menguji performa RAG Pipeline terhadap Golden Dataset
    menggunakan metrik RAGAS.
    """
    # Golden dataset untuk validasi otomatis
    data_samples = {
        'question': [
            'Berapa lama durasi promosi replica saat database failover terjadi?',
            'Berapa tahun batas retensi log sistem audit menurut ISO 27001?'
        ],
        'answer': [
            'Proses promosi Read-Replica menjadi Master memakan waktu maksimal 30 detik.',
            'Log audit wajib disimpan dengan retensi selama 7 tahun sesuai standar ISO 27001.'
        ],
        'contexts': [
            ['Ketika node utama PostgreSQL mengalami crash, Sentinel akan memicu promosi node Read-Replica menjadi Master dalam durasi maksimal 30 detik.'],
            ['Retensi log ini adalah 7 tahun sesuai regulasi standar ISO 27001. Akses dicatat ke Syslog terpusat.']
        ],
        'ground_truth': [
            'Durasi maksimal promosi read-replica adalah 30 detik.',
            'Retensi log audit adalah 7 tahun.'
        ]
    }

    dataset = Dataset.from_dict(data_samples)

    # Catatan: Memerlukan OPENAI_API_KEY di environment untuk evaluasi LLM-as-a-Judge
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("Lewati pengujian: OPENAI_API_KEY belum diset di environment.")

    score = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevance, context_precision]
    )
    
    print("\n--- HASIL EVALUASI RAGAS ---")
    print(score)
    
    # Assert Quality Gate Threshold
    assert score['faithfulness'] >= 0.85, "Faithfulness di bawah standar produksi!"
    assert score['answer_relevance'] >= 0.80, "Answer relevance di bawah ambang batas!"
```

---

### 13. Exercise

#### Level Easy
1. Modifikasi fungsi `reciprocal_rank_fusion` di Seksi 7 agar menerima bobot kustom (*weighted RRF*) antara Sparse Search dan Dense Search (misal: bobot Sparse = $0.4$, Dense = $0.6$).

#### Level Medium
1. Buat pipeline **Sentence Window Retrieval** dari nol:
   - Pecah teks menjadi rentang kalimat individual menggunakan `nltk` atau `regex`.
   - Index kalimat individual (child) ke vector database.
   - Buat fungsi query yang mengembalikan kalimat target beserta 1 kalimat sebelum dan 1 kalimat sesudahnya sebagai gabungan prompt ke LLM.

#### Level Hard
1. Implementasikan **Self-Corrective RAG Pipeline**:
   - Jika dokumen yang diambil oleh hybrid search memiliki rerank score di bawah batas ambang tertentu (misal: Cross-Encoder logit score $< -2.0$), picu modul **Query Rewriting**.
   - Query rewriter harus memanfaatkan LLM untuk mengeliminasi noise dari query asli dan melakukan pengulangan retrieval maksimal 2 kali sebelum mengembalikan respon kegagalan ke pengguna.

---

### 14. Challenge

#### Skenario: Arsitektur Legal-Contract Cross-Check Engine Skala Peta-Byte
Perusahaan multinasional memiliki repositori dokumen kontrak berformat PDF yang tidak seragam (mencapai 100.000.000 chunk embeddings) di berbagai bahasa daerah dan istilah teknis lokal. Sistem Naive RAG menghasilkan hallucination rate fatal terkait klausul terminasi dan denda penalti.

#### Misi Rekayasa:
Rancang arsitektur produksi end-to-end tanpa solusi instan:
1. **Routing & Indexing Architecture**: Bagaimana Anda memetakan dokumen multimodal (teks hukum + tabel finansial bersarang) ke dalam skema dense-sparse retrieval yang konsisten secara horizontal?
2. **Deterministic Context Synthesis**: Rancang skema *Parent Document Expansion* dan *Context Window Compression* agar tidak pernah ada klausa penalti hukum yang terpotong dari tabel induknya.
3. **Latency-SLA Management**: Jelaskan strategi Anda untuk menjaga end-to-end latency tetap di bawah $1.200\text{ ms}$ (P95) sementara Cross-Encoder re-ranker model membutuhkan waktu $400\text{ ms}$ untuk setiap 50 chunks pada GPU single-core.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (5 Soal)
1. **Mengapa Naive RAG yang hanya mengandalkan Cosine Similarity pada dense embeddings sering gagal menemukan referensi nomor klausa atau kode serial produk?**
   - *Jawaban*: Embedding dense memproyeksikan token ke dalam ruang semantik konseptual umum. Angka unik atau kode serial produk jarang memiliki variasi semantik, sehingga posisinya di vector space menjadi acak/tidak sensitif dibandingkan inverted index (BM25) yang mencocokkan karakter token secara presisi.
2. **Apa fungsi parameter konstanta $k$ (biasanya 60) dalam algoritma Reciprocal Rank Fusion?**
   - *Jawaban*: Nilai $k$ berfungsi sebagai smoothing factor untuk meredam dominasi ekstrem dari dokumen yang menempati peringkat teratas (rank 1), sehingga distribusi pembobotan dokumen peringkat berikutnya tidak anjlok secara eksponensial terlalu curam.
3. **Sebutkan perbedaan mendasar antara Bi-Encoder dan Cross-Encoder.**
   - *Jawaban*: Bi-Encoder memproses kueri dan dokumen secara terisolasi menghasilkan embedding vektor terpisah (memungkinkan pra-kalkulasi dan pencarian ANN cepat), sedangkan Cross-Encoder memproses kueri dan dokumen secara bersamaan dalam full cross-attention transformer (sangat akurat, namun komputasi mahal dan tidak bisa di-precompute).
4. **Apa yang dimaksud dengan teknik Parent-Document Retrieval?**
   - *Jawaban*: Memisahkan data granularity pencarian dan generasi: embedding dibuat dari chunk kecil (child) agar fokus semantiknya tajam, namun saat retrieve, context yang disajikan ke LLM adalah dokumen/chunk induk yang lebih besar (parent) untuk menjaga konteks narasi.
5. **Sebutkan 3 metrik inti dari RAG Triad.**
   - *Jawaban*: *Context Relevance/Precision*, *Faithfulness* (Groundedness), dan *Answer Relevance*.

#### B. Pertanyaan Intermediate (5 Soal)
1. **Bagaimana cara kerja Hypothetical Document Embeddings (HyDE) dan kapan teknik ini justru memperburuk performa retrieval?**
   - *Jawaban*: HyDE meminta LLM membuat jawaban hipotesis dari pertanyaan, lalu me-vektorkan jawaban tersebut untuk mencari dokumen riil yang mirip. Teknik ini gagal/memperburuk hasil jika LLM berhalusinasi total pada subjek domain yang sangat asing/spesifik, sehingga kueri vektor melenceng jauh dari realitas korpus.
2. **Bagaimana mengatasi latency Cross-Encoder yang tinggi pada sistem dengan throughput tinggi?**
   - *Jawaban*: Membatasi kandidat dokumen yang di-rerank (misal hanya top-15 dari RRF), melakukan model quantization (INT8/FP8), menyajikan reranker menggunakan inference runtime teroptimasi (ONNX Runtime/vLLM/Triton), dan memanfaatkan auto-scaling GPU.
3. **Mengapa metrik "Context Precision" RAGAS penting dioptimalkan untuk menekan biaya operasional LLM?**
   - *Jawaban*: Context Precision mengukur seberapa bersih dokumen yang ditarik dari informasi sampah. Semakin tinggi presisi, semakin sedikit token konteks non-relevan yang dikirimkan ke LLM, yang secara langsung memotong pengeluaran token API LLM per query.
4. **Apa perbedaan mendasar antara Sentence-Window Retrieval dan Semantic Chunking?**
   - *Jawaban*: Semantic chunking memotong teks berdasarkan batas perbedaan jarak embedding antar kalimat yang signifikan. Sentence-window retrieval memotong teks per kalimat tunggal untuk indexing pencarian, tetapi menarik kalimat sekitarnya (windowing) saat diteruskan ke LLM.
5. **Mengapa semantic cache query hit rate lebih sulit dipertahankan dibanding HTTP caching tradisional?**
   - *Jawaban*: HTTP cache bersifat deterministik berdasarkan hash URL/header exact. Semantic cache bergantung pada ambang batas similarity vector (misal cos-sim $> 0.96$). Perubahan kecil pada intent query bisa memicu false cache hit (menjawab pertanyaan berbeda) jika threshold terlalu longgar.

#### C. Skenario Kasus Produksi (3 Soal)
1. **Skenario 1**: Sebuah sistem RAG internal HR mengalami masalah di mana pengguna menanyakan: *"Apa benefit asuransi gigi saya?"* Sistem mengambil dokumen polis yang menyatakan *"Perusahaan menanggung asuransi gigi hingga 5 juta rupiah,"* tetapi LLM menjawab: *"Asuransi tidak menanggung perawatan gigi estetika."* Metrik RAGAS apa yang terdegradasi pada kasus ini dan bagaimana investigasi arsitekturalnya?
   - *Analisis & Solusi*: Metrik yang jatuh adalah **Answer Relevance** atau **Context Precision**. Konteks memuat kata kunci asuransi gigi, namun LLM merespon klausul pengecualian alih-alih menjawab pertanyaan benefit. Solusinya: Implementasikan reranker yang lebih peka terhadap intent pengguna, atau revisi prompt synthesis agar instruksi menjawab fokus langsung pada inti pertanyaan nominal sebelum menyebutkan klausul restriksi.
2. **Skenario 2**: Pada sistem RAG e-commerce pencarian suku cadang kendaraan, query *"Filter oli Avanza 2018"* menghasilkan dokumen untuk *"Filter udara Avanza 2018"* pada ranking pertama Vector Search. Mengapa ini terjadi dan bagaimana solusinya?
   - *Analisis & Solusi*: Dense embedding menganggap "Filter oli" dan "Filter udara" sangat dekat di vector space karena keduanya adalah jenis filter mobil dalam konteks model kendaraan yang sama. Solusinya: Terapkan Hybrid Search dengan BM25 atau SPLADE yang memberikan penalti keras pada ketidakcocokan kata kunci eksak ("oli" vs "udara"), lalu gunakan Cross-Encoder untuk menyortir token interaksi.
3. **Skenario 3**: Log sistem menunjukkan bahwa latency P99 melonjak dari $800\text{ ms}$ menjadi $5.000\text{ ms}$ setiap kali pengguna memasukkan kueri komparasi panjang seperti: *"Bandingkan margin profit kuartal 3 tahun 2022 terhadap kuartal yang sama tahun 2023 di divisi logistik dan manufaktur."* Apa bottleneck-nya dan bagaimana arsitektur RAG harus diubah?
   - *Analisis & Solusi*: Kueri tersebut bersifat multi-hop dan multi-variable, memaksa retrieval engine mencari banyak entitas yang terfragmentasi dalam satu langkah penelusuran. Solusinya: Gunakan **Query Decomposition** (Agentic Router). Pecah query majemuk menjadi sub-query independen: (1) Margin profit Q3 2022 logistik, (2) Margin Q3 2022 manufaktur, (3) Margin Q3 2023 logistik, (4) Margin Q3 2023 manufaktur. Eksekusi retrieval secara paralel (`asyncio.gather`), satukan hasilnya ke context merger, lalu biarkan LLM melakukan komparasi.

---

### 16. Summary

Implementasi RAG enterprise menuntut pergeseran dari paradigma Naive RAG ke **Advanced Multistage RAG Architecture**:
1. **Hybrid Retrieval (Dense + Sparse)** menutupi kelemahan fundamental vector search murni dalam menangani token exact, kode, dan terminologi unik.
2. **Reciprocal Rank Fusion (RRF)** menyediakan mekanisme agregasi ranking yang stabil dan tidak bergantung pada normalisasi skor metrik yang berbeda.
3. **Two-Stage Retrieval (Bi-Encoder + Cross-Encoder)** menawarkan titik optimal antara latency throughput dan precision relevance.
4. **Hierarchical Splitting & Context Windowing** (Parent-Document & Sentence Window) memastikan token yang diumpankan ke LLM memiliki kepadatan informasi (*Signal-to-Noise Ratio*) yang tinggi tanpa memotong konteks penting.
5. **Continuous Evaluation (RAGAS Triad)** dan observabilitas terdistribusi mengubah sistem RAG dari black-box yang rapuh menjadi sistem rekayasa perangkat lunak yang terukur, terkontrol, dan siap untuk lingkungan produksi skala besar.