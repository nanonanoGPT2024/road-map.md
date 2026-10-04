# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: Retrieval-Augmented Generation (RAG) Fondasi & Arsitektur**  
**Track: AI Engineer (08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta didik enterprise diharapkan mampu:
- Merancang dan mengimplementasikan arsitektur **Advanced RAG** bertingkat (*multi-stage retrieval pipeline*) yang mengatasi limitasi Naive RAG (*Lost-in-the-Middle*, *semantic drift*, dan *low precision recall*).
- Membangun mekanisme **Hybrid Search** yang memadukan representasi *Dense* (HNSW via Cosine/Dot-Product) dan *Sparse* (BM25/SPLADE) menggunakan algoritma **Reciprocal Rank Fusion (RRF)**.
- Mengintegrasikan modul **Two-Stage Reranking** berbasis *Cross-Encoder* untuk memangkas *noise* konteks hingga 80% sebelum inferensi LLM.
- Menerapkan teknik transformasi kueri dinamis: **Hypothetical Document Embeddings (HyDE)**, **Multi-Query Decomposition**, dan **Step-Back Prompting**.
- Mengimplementasikan **Semantic Caching**, **Hierarchical Chunking (Parent-Document Retrieval)**, dan **Metadata Filtering berbasis Role-Based Access Control (RBAC)** pada level *vector store*.
- Mengukur kualitas end-to-end pipeline RAG secara kuantitatif menggunakan metrik industri **RAG Triad** (*Context Relevance*, *Groundedness/Faithfulness*, *Answer Relevance*) via evaluasi otomatis.
- Menggelar pipeline RAG performa tinggi dengan *p99 latency budget* < 1.2 detik, *streaming context*, dan ketahanan skala jutaan dokumen.

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Konsep Fondasi Vector DB & Embedding (Modul 01):** Representasi vektor, algoritma indexing HNSW/IVF, dan metrik jarak matriks.
- **Python Lanjutan & Asynchronous Programming:** `asyncio`, typing (`typing.TypedDict`, `pydantic.BaseModel`), dan profiling kode.
- **Natural Language Processing (NLP):** Tokenisasi (BPE/WordPiece), mekanisme Self-Attention pada Transformers, serta perbedaan fundamental antara arsitektur *Bi-Encoder* dan *Cross-Encoder*.
- **Database Engineering:** Dasar-dasar *inverted index* (BM25), *payload indexing*, dan operasi *connection pooling*.

---

## 3. Concept & Internal Architecture

Naive RAG (Embedding $\to$ Top-K Similarity $\to$ Prompt Packing) secara sistemik gagal di lingkungan produksi enterprise karena tiga anomali fatal:
1. **Semantic Disconnect:** Jarak kosinus tinggi tidak menjamin korelasi informasi (misal: "X mengakuisisi Y" vs "Y mengakuisisi X" memiliki vektor kedekatan sangat tinggi pada model *Bi-Encoder* standar).
2. **Lost-in-the-Middle Phenomenon:** LLM cenderung memproses konteks di awal (*primacy*) dan di akhir (*recency*) dari context window, mengabaikan informasi relevan yang berada di tengah chunk panjang.
3. **Keyword Blindness:** Dense embeddings sering gagal menangkap *exact string matching* (seperti nomor SKU, UUID dokumen, klausul hukum bernomor spesifik, atau kode error fatal).

Arsitektur produksi enterprise mengadopsi paradigma **Multi-Stage Advanced RAG Engine**:

```
                       [ Incoming User Query ]
                                  │
                                  ▼
                  [ Query Transformation Layer ]
            ┌─────────────────────┼─────────────────────┐
            │                     │                     │
            ▼                     ▼                     ▼
     [ Rewrite Engine ]    [ HyDE Generator ]   [ Sub-Query Decomp ]
            │                     │                     │
            └─────────────────────┼─────────────────────┘
                                  ▼
                  [ Hybrid Retrieval Execution ]
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
   [ Dense Vector Index ]                      [ Sparse Inverted Index ]
   (Qdrant HNSW - Dense)                       (BM25 / SPLADE - Sparse)
            │                                           │
            └─────────────────────┬─────────────────────┘
                                  ▼
                     [ Reciprocal Rank Fusion ]
                                  ▼
                     [ Cross-Encoder Reranker ]
                     (BGE-Reranker-Large / Cohere)
                                  ▼
                 [ Context Compression & Assembly ]
                   (Parent-Child Context Resolver)
                                  ▼
                   [ Guardrails & Safety Check ]
                                  ▼
                 [ LLM Generation (Streaming) ]
```

### 3.1. Hybrid Search Matematika: Reciprocal Rank Fusion (RRF)

Untuk menyatukan ruang skor yang tidak terkalibrasi antara BM25 ($S_{BM25} \in [0, \infty)$) dan Dense Vector Similarity ($S_{Dense} \in [-1, 1]$), kita menggunakan **Reciprocal Rank Fusion (RRF)**:

$$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$

Di mana:
- $M$ adalah himpunan sistem retrieval ($M = \{\text{Dense}, \text{Sparse}\}$).
- $r_m(d)$ adalah posisi peringkat (*rank*) dari dokumen $d$ pada sistem $m$.
- $k$ adalah konstanta perataan (*smoothing constant*), standar industri bernilai $k = 60$. Konstanta ini memitigasi dampak dari anomali peringkat teratas pada salah satu retrieval engine.

### 3.2. Two-Stage Retrieval: Bi-Encoder vs Cross-Encoder

| Dimensi | Bi-Encoder (Dense Retrieval) | Cross-Encoder (Reranker) |
| :--- | :--- | :--- |
| **Arsitektur** | $Query \to E_Q$, $Doc \to E_D$; Sim = $E_Q \cdot E_D$ | $(Query, Doc)$ diproses bersamaan via Cross-Attention |
| **Interaksi Fitur** | Late interaction (vektor independen) | Full cross-token self-attention di seluruh layer |
| **Kompleksitas Waktu** | $\mathcal{O}(1)$ via HNSW ANN Indexing | $\mathcal{O}(N \times L^2)$ di mana $L = \text{len}(Q) + \text{len}(D)$ |
| **Akurasi Semantik** | Moderat (sering miss nuansa sintaksis) | Sangat Tinggi (menilai interdependensi kata) |
| **Peran Arsitektur** | First-Stage: Filter 10.000.000 $\to$ 100 kandidat | Second-Stage: Filter 100 $\to$ Top 5 untuk LLM |

### 3.3. Hierarchical Context Expansion (Parent-Child Strategy)

Memecah dokumen menjadi potongan kecil (misal: 128 token) memberikan akurasi embedding yang tajam, tetapi menghilangkan konteks narasi. Memecah dokumen menjadi potongan besar (misal: 2048 token) mempertahankan konteks, tetapi vektor embedding menjadi terlalu generik.

Solusi produksi adalah **Parent-Child Chunking**:
- Dokumen dibagi menjadi *Parent Chunks* (1024 token).
- Setiap *Parent Chunk* dipecah lagi menjadi beberapa *Child Chunks* (256 token).
- Hanya *Child Chunks* yang di-index ke dalam Vector DB untuk pencarian.
- Ketika *Child Chunk* terpilih oleh retrieval engine, arsitektur mengambil dan mengembalikan *Parent Chunk* yang sesuai ke context window LLM.

---

## 4. Why & What

### Mengapa Naive RAG Gagal di Enterprise?
- **Domain Vocabulary Gap:** Model embedding generik gagal memahami terminologi proprietary, akronim internal organisasi, dan format penomoran inventaris.
- **Context Pollution:** Memasukkan potongan dokumen yang mengandung 90% teks tidak relevan membingungkan *attention heads* pada LLM, memicu halusinasi dan melipatgandakan *cost token inferensi*.
- **No Access Control:** Naive RAG mencampur seluruh dokumen dalam satu namespace tanpa memvalidasi apakah pengguna memiliki hak akses (Clearance Level) atas dokumen tersebut.

### Apa yang Dibangun di Arsitektur Lanjutan?
Pipeline modular dengan:
1. **Transformasi Input:** Mengubah kueri implisit/ambigu menjadi bentuk representasi kanonikal.
2. **Koleksi Multi-Modal Index:** Menggabungkan *lexical inverted index* dengan *approximate nearest neighbor graph*.
3. **Filtering Deterministik:** Metadata hard-filtering terintegrasi langsung di dalam kueri vektor graf (pre-filtering via payload index).
4. **Scoring Presisi Tinggi:** Cross-encoder inference untuk validasi relevansi kontekstual.
5. **Observabilitas Metrik:** Tracing terdistribusi dan *ground truth scoring* sebelum response dikirim ke klien.

---

## 5. How (Workflow Detail)

Alur kerja operasional Advanced RAG Engine berjalan dalam 6 fase deterministik:

1. **Query Pre-Processing & Transformation:**
   - LLM kecil (misal: Llama-3-8B-Instruct via vLLM) menghasilkan variasi kueri atau dokumen hipotetis (HyDE) untuk menjembatani jurang leksikal antara kueri pendek dan dokumen target yang panjang.
2. **Execution Stage 1 (Hybrid Dense-Sparse Fetch):**
   - Kueri dijalankan secara paralel:
     - Thread A: Sparse vector encoding (BM25 tokenization atau model SPLADE) dieksekusi.
     - Thread B: Dense vector encoding (via model *BGE-Large-EN-v1.5*) dieksekusi.
   - Vector database (misal: Qdrant) mengeksekusi *pre-filtered vector search* menggunakan payload RBAC.
   - Mengambil Top-$K_1$ (misal: 50) dari masing-masing index.
3. **Fusion Stage (RRF Merge):**
   - Hasil Dense dan Sparse diagregasikan menggunakan skor RRF.
   - Kandidat disaring menjadi Top-$K_2$ (misal: 30) dokumen gabungan.
4. **Execution Stage 2 (Cross-Encoder Reranking):**
   - Pasangan $(Query, Candidate_i)$ dikirim ke Cross-Encoder inference engine.
   - Logits dinormalisasi menggunakan fungsi Sigmoid untuk mendapatkan skor absolut relevansi $[0, 1]$.
   - Filter kandidat yang memiliki skor di bawah *threshold* (misal: $< 0.45$).
   - Ambil Top-$K_3$ (misal: 5) dokumen terbaik.
5. **Context Resolution (Parent Extraction):**
   - Tukar metadata `child_chunk_id` dengan teks utuh dari `parent_chunk_id` yang tersimpan di fast key-value store (Redis / In-memory mapping).
6. **Constrained Generation:**
   - Format prompt dengan *system instructions* ketat (system prompt guardrails).
   - Stream token LLM langsung ke user via Server-Sent Events (SSE).

---

## 6. Analogy & Diagram ASCII

### Analogi Perpustakaan Riset Enterprise
Bayangkan Anda mencari kasus hukum spesifik di perpustakaan nasional dengan jutaan arsip:
- **Naive RAG:** Anda bertanya ke pustakawan magang. Pustakawan mencari satu rak yang kira-kira mirip, mengambil 3 buku acak teratas, membukanya di halaman sembarang, lalu menyuruh Anda membacanya sendiri.
- **Advanced RAG:**
  1. *Query Expansion:* Staf riset merumuskan ulang pertanyaan Anda ke dalam 3 istilah yurisprudensi resmi.
  2. *Hybrid Retrieval:* Dua kurator bergerak paralel: satu mencari nomor katalog dan kata kunci eksak di buku induk (BM25), satu mencari konsep tematik di arsip abstrak digital (Dense Vector).
  3. *Fusion & Reranking:* Master Pustakawan (Cross-Encoder) menyeleksi 50 berkas hasil temuan, membaca silang setiap halaman terhadap pertanyaan Anda, lalu membuang 45 berkas yang tidak relevan.
  4. *Parent Resolution:* Untuk 5 halaman tersisa yang sangat relevan, staf mengambil bab utuh dari lemari penyimpanan agar Anda membaca argumen hukum secara utuh dan terhindar dari salah tafsir.

### Diagram Alur Data Sistemik

```
[ User App ]
     │
     │ 1. POST /query {"text": "CVE-2024-1234 mitigation", "user_role": "sec_ops"}
     ▼
[ API Gateway / Orchestrator ]
     │
     ├───► [ Query Transformer ] ──► Generated Queries: [Q_orig, Q_hyde, Q_keywords]
     │
     ├───► [ Embedding Service ] ──► Dense Vector (1024-dim)
     │
     ├───► [ Vector DB Engine (Qdrant) ]
     │        │
     │        ├─ Filter: {"metadata.clearance": {"$lte": "sec_ops"}}
     │        ├─ Dense ANN (HNSW)   ──► Candidate List A (Top 50)
     │        └─ Sparse Inverted    ──► Candidate List B (Top 50)
     │
     ├───► [ RRF Algorithmic Merger ] ──► Merged Candidates (Top 30)
     │
     ├───► [ Cross-Encoder Service ] ──► Re-scored Candidates (Top 5, Score >= 0.5)
     │
     ├───► [ Parent-Context Store (Redis) ] ──► Expand to Parent Chunks
     │
     ├───► [ Prompt Assembler ] ──► Formatted Token Context Window
     │
     └───► [ LLM Generation ] ──(Streaming SSE)──► [ User App ]
```

---

## 7. Practical Implementation (Standar Industri)

Berikut adalah implementasi end-to-end multi-stage RAG engine berbasis Python 3.11+ yang modular, fully-typed, asinkron, dan siap produksi. Kode ini menggunakan Qdrant Client, Cross-Encoder dari HuggingFace sentence-transformers, dan BM25.

### Arsitektur Modul: `advanced_rag_engine.py`

```python
"""
Advanced Production RAG Engine
Components:
- Hybrid Search (Dense + BM25 via Rank Fusion)
- Metadata Role-Based Access Control (RBAC) Filtering
- Cross-Encoder Re-Ranking Stage
- Parent-Document Context Expansion
"""

from typing import List, Dict, Any, Optional
import asyncio
from pydantic import BaseModel, Field
import numpy as np

# Mocking Vector DB & Transformers for self-contained, crash-resilient code
# In production, use: from qdrant_client import AsyncQdrantClient
# and: from sentence_transformers import CrossEncoder

class DocumentChunk(BaseModel):
    id: str
    parent_id: str
    content: str
    metadata: Dict[str, Any]
    score: float = 0.0


class UserContext(BaseModel):
    user_id: str
    clearance_level: int = Field(default=1, ge=1, le=5)  # 1 (Public) to 5 (Top Secret)


class SearchQuery(BaseModel):
    query_text: str
    user_context: UserContext
    top_k_retrieval: int = 20
    top_k_final: int = 3
    rerank_threshold: float = 0.25


class CrossEncoderReranker:
    """Simulasi Cross-Encoder Transformer (e.g., cross-encoder/ms-marco-MiniLM-L-6-v2)"""
    def __init__(self, model_name: str = "ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name

    async def rerank(self, query: str, candidates: List[DocumentChunk]) -> List[DocumentChunk]:
        if not candidates:
            return []
        
        # Simulasi full cross-attention score calculation
        # Pada produksi: scores = self.model.predict([(query, c.content) for c in candidates])
        await asyncio.sleep(0.05)  # Representasi compute overhead cross-encoder (~50ms)
        
        reranked = []
        for candidate in candidates:
            # Heuristik simulasi cross-attention: kombinasi match leksikal presisi + context length
            q_tokens = set(query.lower().split())
            d_tokens = set(candidate.content.lower().split())
            overlap = len(q_tokens.intersection(d_tokens)) / max(len(q_tokens), 1)
            
            # Normalisasi score via simulated logit sigmoid
            simulated_cross_score = 1.0 / (1.0 + np.exp(-(overlap * 4.0 - 1.0)))
            candidate.score = float(simulated_cross_score)
            reranked.append(candidate)
            
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked


class InvertedIndexBM25:
    """Implementasi In-Memory BM25 Sparse Search Engine"""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: Dict[str, DocumentChunk] = {}
        self.doc_lengths: Dict[str, int] = {}
        self.avg_doc_len: float = 0.0
        self.idf: Dict[str, float] = {}
        self.doc_freqs: Dict[str, int] = {}

    def fit(self, documents: List[DocumentChunk]):
        self.corpus = {doc.id: doc for doc in documents}
        total_tokens = 0
        for doc in documents:
            tokens = doc.content.lower().split()
            self.doc_lengths[doc.id] = len(tokens)
            total_tokens += len(tokens)
            
            seen_tokens = set(tokens)
            for token in seen_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        N = len(documents)
        self.avg_doc_len = total_tokens / max(N, 1)
        for token, df in self.doc_freqs.items():
            self.idf[token] = np.log((N - df + 0.5) / (df + 0.5) + 1.0)

    async def search(self, query: str, top_k: int, clearance_level: int) -> List[DocumentChunk]:
        await asyncio.sleep(0.01)  # Simulasi IO sparse search
        q_tokens = query.lower().split()
        scores: Dict[str, float] = {}

        for doc_id, doc in self.corpus.items():
            # RBAC Pre-filtering
            if doc.metadata.get("clearance", 1) > clearance_level:
                continue
                
            score = 0.0
            doc_tokens = doc.content.lower().split()
            doc_len = self.doc_lengths[doc_id]
            
            for token in q_tokens:
                if token not in self.idf:
                    continue
                tf = doc_tokens.count(token)
                numerator = self.idf[token] * tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avg_doc_len))
                score += numerator / denominator

            if score > 0:
                scores[doc_id] = score

        sorted_ids = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        results = []
        for doc_id, score in sorted_ids:
            chunk = self.corpus[doc_id].model_copy()
            chunk.score = score
            results.append(chunk)
        return results


class VectorStoreSimulator:
    """Simulasi Qdrant Vector Engine dengan HNSW Indexing dan RBAC payload filtering"""
    def __init__(self):
        self.storage: Dict[str, DocumentChunk] = {}
        
    def add_documents(self, documents: List[DocumentChunk]):
        for doc in documents:
            self.storage[doc.id] = doc

    async def search_dense(self, query: str, top_k: int, clearance_level: int) -> List[DocumentChunk]:
        await asyncio.sleep(0.02)  # Simulasi network roundtrip ke Vector DB (~20ms)
        # Sederhana: simulasi proximity dense vector via substring/token length
        results = []
        for doc in self.storage.values():
            if doc.metadata.get("clearance", 1) > clearance_level:
                continue
            # Pseudo dense cosine similarity
            sim = 0.35 + (0.6 * (hash(query + doc.content) % 100) / 100.0)
            res = doc.model_copy()
            res.score = sim
            results.append(res)
            
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


class AdvancedRAGEngine:
    def __init__(self, parent_document_store: Dict[str, str]):
        self.sparse_index = InvertedIndexBM25()
        self.vector_store = VectorStoreSimulator()
        self.reranker = CrossEncoderReranker()
        self.parent_store = parent_document_store
        self.rrf_k = 60  # Smoothing constant

    def index_data(self, chunks: List[DocumentChunk]):
        self.sparse_index.fit(chunks)
        self.vector_store.add_documents(chunks)

    def _reciprocal_rank_fusion(
        self, 
        dense_results: List[DocumentChunk], 
        sparse_results: List[DocumentChunk]
    ) -> List[DocumentChunk]:
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, DocumentChunk] = {}

        # Kalkulasi rank dense
        for rank, doc in enumerate(dense_results):
            doc_map[doc.id] = doc
            rrf_scores[doc.id] = rrf_scores.get(doc.id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        # Kalkulasi rank sparse
        for rank, doc in enumerate(sparse_results):
            doc_map[doc.id] = doc
            rrf_scores[doc.id] = rrf_scores.get(doc.id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        fused_candidates: List[DocumentChunk] = []
        for doc_id, score in rrf_scores.items():
            candidate = doc_map[doc_id].model_copy()
            candidate.score = score
            fused_candidates.append(candidate)

        fused_candidates.sort(key=lambda x: x.score, reverse=True)
        return fused_candidates

    async def execute_query(self, search_query: SearchQuery) -> Dict[str, Any]:
        # 1. Parallel Multi-Retrieval Execution (Dense + Sparse)
        dense_task = asyncio.create_task(
            self.vector_store.search_dense(
                query=search_query.query_text,
                top_k=search_query.top_k_retrieval,
                clearance_level=search_query.user_context.clearance_level
            )
        )
        sparse_task = asyncio.create_task(
            self.sparse_index.search(
                query=search_query.query_text,
                top_k=search_query.top_k_retrieval,
                clearance_level=search_query.user_context.clearance_level
            )
        )
        
        dense_hits, sparse_hits = await asyncio.gather(dense_task, sparse_task)

        # 2. Reciprocal Rank Fusion
        fused_candidates = self._reciprocal_rank_fusion(dense_hits, sparse_hits)

        # 3. Two-Stage Reranking via Cross-Encoder
        # Mengambil top pool untuk cross-encoding (e.g., top 15)
        pool_for_rerank = fused_candidates[:15]
        reranked_chunks = await self.reranker.rerank(
            query=search_query.query_text, 
            candidates=pool_for_rerank
        )

        # 4. Filter by Threshold & Context Selection
        valid_chunks = [
            c for c in reranked_chunks 
            if c.score >= search_query.rerank_threshold
        ][:search_query.top_k_final]

        # 5. Parent Context Expansion
        assembled_contexts = []
        for chunk in valid_chunks:
            parent_text = self.parent_store.get(
                chunk.parent_id, 
                chunk.content  # Fallback to child if parent missing
            )
            assembled_contexts.append({
                "chunk_id": chunk.id,
                "parent_id": chunk.parent_id,
                "score": chunk.score,
                "retrieved_snippet": chunk.content,
                "expanded_context": parent_text,
                "source": chunk.metadata.get("source", "unknown")
            })

        return {
            "query": search_query.query_text,
            "retrieved_nodes_count": len(assembled_contexts),
            "contexts": assembled_contexts
        }


# ==============================
# PIPELINE VERIFICATION TEST
# ==============================
async def main():
    # Setup data parent dan child chunks
    parent_docs = {
        "P1": "Enterprise Security Policy 2024: All microservices interacting with PII must enforce mTLS and AES-256 at rest. Violations trigger an automated Sev-1 ticket and network isolation.",
        "P2": "Employee Benefits Handbook: Standard health insurance covers dental and outpatient visits up to $5,000 per fiscal year. High deductible health plan options are also accessible."
    }

    raw_chunks = [
        DocumentChunk(
            id="C1_1", 
            parent_id="P1", 
            content="PII services must enforce mTLS and AES-256 encryption at rest.", 
            metadata={"clearance": 3, "source": "sec_policy.pdf"}
        ),
        DocumentChunk(
            id="C1_2", 
            parent_id="P1", 
            content="Security violations trigger an automated Sev-1 incident ticket and immediate network quarantine.", 
            metadata={"clearance": 3, "source": "sec_policy.pdf"}
        ),
        DocumentChunk(
            id="C2_1", 
            parent_id="P2", 
            content="Standard health insurance coverage provides outpatient and dental care up to $5,000 annually.", 
            metadata={"clearance": 1, "source": "benefits.pdf"}
        )
    ]

    engine = AdvancedRAGEngine(parent_document_store=parent_docs)
    engine.index_data(raw_chunks)

    # Kasus A: Kueri teknis security oleh user Clearance Level 1 (Tidak berhak baca Sec Ops)
    query_unauthorized = SearchQuery(
        query_text="What happens during a PII encryption violation?",
        user_context=UserContext(user_id="user_intern", clearance_level=1)
    )
    result_a = await engine.execute_query(query_unauthorized)
    print(f"--- Skenario Unauthorized (Clearance 1) ---")
    print(f"Jumlah Node Terambil: {result_a['retrieved_nodes_count']}")
    assert result_a['retrieved_nodes_count'] == 0, "RBAC filtering bocor!"

    # Kasus B: Kueri teknis security oleh Security Lead Clearance Level 4 (Berhak)
    query_authorized = SearchQuery(
        query_text="What happens during a PII encryption violation?",
        user_context=UserContext(user_id="sec_lead", clearance_level=4)
    )
    result_b = await engine.execute_query(query_authorized)
    print(f"\n--- Skenario Authorized (Clearance 4) ---")
    print(f"Jumlah Node Terambil: {result_b['retrieved_nodes_count']}")
    for node in result_b["contexts"]:
        print(f"-> Node {node['chunk_id']} (Score: {node['score']:.4f})")
        print(f"   Parent Context: {node['expanded_context']}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario: Tier-1 Regulatory Compliance Engine
- **Skala:** 40 Juta dokumen laporan kepatuhan finansial (SEC filings, Basel III/IV frameworks, regulasi internal anti-money laundering).
- **Concurreny:** 1.500 QPS puncak internal audit global.
- **SLA:** $p99 < 850\text{ ms}$, False Discovery Rate (Halusinasi Fakta) < 0.01%.

### Arsitektur Produksi & Solusi Rekayasa

```
                    ┌─────────────────────────┐
                    │ Client Query (REST/gRPC)│
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  Semantic Cache (Redis) ├──► [Hit: Return < 15ms]
                    └────────────┬────────────┘
                                 │ [Miss]
                    ┌────────────▼────────────┐
                    │    Query Rewriter &     │
                    │  Intent Router (Triton) │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
   ┌──────────────────────┐              ┌──────────────────────┐
   │ Sparse Index Cluster │              │ Dense Index Cluster  │
   │ (Elasticsearch BM25) │              │ (Qdrant Distributed) │
   └──────────┬───────────┘              └──────────┬───────────┘
              │ (Top 100)                           │ (Top 100)
              └──────────────────┬──────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │ Reciprocal Rank Fusion  │
                    └────────────┬────────────┘
                                 │ (Top 40)
                    ┌────────────▼────────────┐
                    │ Cross-Encoder Reranker  │
                    │  (BGE-Reranker-Large on │
                    │      Triton + TensorRT) │
                    └────────────┬────────────┘
                                 │ (Top 5, score > 0.65)
                    ┌────────────▼────────────┐
                    │ Document Parent Builder │
                    │    (Aerospike NoSQL)    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  LLM Engine (vLLM Farm) │
                    └─────────────────────────┘
```

1. **Semantic Cache Invalidation Pattern:**
   Setiap kueri masuk di-hash menggunakan embedding berdimensi rendah ($d=256$). Jika kosinus kemiripan dengan cache kueri di Redis > 0.96 dan data dokumen belum berubah (via *timestamp vector*), cache langsung menyajikan response dengan latency < 15 ms.
2. **Metadata RBAC Partitioning:**
   Setiap tenant audit memiliki partisi logis tersendiri. Filter RBAC diterapkan di fase pencarian ANN HNSW menggunakan bitset mask (`payload.filter`). Index tidak pernah mengevaluasi node jika bitmask privilege pengguna tidak valid, mencegah kebocoran informasi regulasi antar-yurisdiksi.
3. **Hardware Acceleration Reranker:**
   Cross-encoder adalah bottleneck komputasi terbesar. Tim membungkus model *bge-reranker-large* ke dalam engine **NVIDIA Triton Inference Server** menggunakan optimasi **TensorRT-LLM (FP16)**. Eksekusi 40 pasang kueri-dokumen diproses dalam waktu < 28 ms (turun drastis dari 320 ms pada vanilla PyTorch CPU).

---

## 9. Trade-offs

Setiap keputusan arsitektur di sistem RAG tingkat lanjut melibatkan kompromi teknis:

| Pendekatan / Komponen | Pros | Cons | Biaya Komputasi / Latency | Kapan Harus Digunakan |
| :--- | :--- | :--- | :--- | :--- |
| **Naive RAG (Single Bi-Encoder)** | Arsitektur sederhana, latency sangat rendah (<100ms). | Rentan recall error, noise tinggi, sering memicu halusinasi. | Compute: Minimal.<br>Infra Cost: Sangat Rendah. | Prototipe, MVP internal, data teks bersih & pendek. |
| **Hybrid (Dense + BM25 via RRF)** | Menangkap kemiripan konsep sekaligus terminologi teknis eksak. | Memerlukan dua index engine terpisah; maintenance ganda. | Compute: Rendah-Sedang.<br>Latency: +20ms - 50ms. | Korpus teknis, finansial, hukum, dan medis beristilah presisi. |
| **Two-Stage Retrieval + Cross-Encoder** | Memangkas noise konteks secara masif, akurasi recall top-tier. | Bottleneck throughput, butuh GPU untuk menjaga SLA latency. | Compute: Sangat Tinggi.<br>Latency: +50ms - 250ms (GPU). | Enterprise production dengan toleransi halusinasi nol. |
| **Hypothetical Document (HyDE)** | Mengatasi kueri pendek/abstrak dengan menciptakan sintesis target. | Konsumsi token input LLM naik; jika HyDE halusinasi, search melenceng. | Compute: Tinggi (LLM generation).<br>Latency: +400ms - 1.2s. | Kueri pencarian user sangat pendek (<5 token) atau berformat tanya-jawab samar. |
| **Parent-Child Chunking** | Presisi retrieval tinggi tanpa kehilangan konteks narasi utuh. | Penggunaan storage berlipat ganda; koordinasi multi-store (KV vs Vector). | Storage: 2-3x lebih besar.<br>Latency overhead: +10ms. | Dokumen kompleks: buku manual, kontrak legal, laporan tahunan. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Raw Score Fusion Fallacy
* **Kesalahan:** Menjumlahkan skor mentah dari Cosine Similarity (kisaran 0-1) dan BM25 (kisaran 0-tak hingga) secara linear: $FinalScore = S_{Dense} + S_{BM25}$.
* **Dampak:** BM25 mendominasi total skor secara membabi-buta atau sebaliknya, merusak integritas urutan peringkat.
* **Solusi:** Gunakan **Reciprocal Rank Fusion (RRF)** atau normalisasi min-max dinamis dengan parameter Bobot Z-Score sebelum perankingan.

### 2. Context Window Choking (Over-Contextualization)
* **Kesalahan:** Mengirimkan Top-20 dokumen langsung ke prompt LLM karena context window model besar (128K token).
* **Dampak:** *Lost-in-the-Middle Phenomenon*, inferensi LLM melambat secara kuadratik/linear, token cost membengkak, akurasi jawaban menurun.
* **Solusi:** Pasang Cross-Encoder Reranker dengan hard cutoff threshold, batasi context akhir pada Top-3 hingga Top-5 paling relevan.

### 3. Out-of-Order Chunk Concatenation
* **Kesalahan:** Menggabungkan chunk dokumen yang terpotong-potong secara acak berdasarkan urutan ranking retrieval semata ke context prompt.
* **Dampak:** Informasi temporal terfragmentasi; alur logis teks rusak, menyebabkan LLM gagal memahami relasi sebab-akibat.
* **Solusi:** Sortir kembali chunk yang berhasil lolos re-ranking berdasarkan atribut metadata aslinya (`doc_id`, `chunk_order_index`) sebelum dilakukan prompt injection.

### 4. Vector Distance Metric Mismatch
* **Kesalahan:** Melakukan indexing model dengan *Cosine Metric*, tetapi konfigurasi Vector DB diset pada *Euclidean Distance (L2)* atau *Dot Product* tanpa normalisasi vektor unit ($||v||=1$).
* **Dampak:** Hasil retrieval acak, skor similarity tidak berkorelasi dengan kualitas relevansi.
* **Solusi:** Terapkan automated deployment assertions: verifikasi metrik index di database sama persis dengan spesifikasi training embedding model.

---

## 11. Best Practices (Production Checklist)

Gunakan daftar checklist ini sebelum mempromosikan pipeline RAG ke level *Production*:

- [ ] **Data Pipeline & Chunking:**
  - [ ] Chunking berbasis semantik atau token-aware (bukan *naive character splitting*).
  - [ ] Overlap diatur secara terukur (10% - 15% dari panjang chunk total).
  - [ ] Deterministic ID generation: ID chunk di-generate via `hashing(document_id + chunk_index)` guna mencegah duplikasi data saat sinkronisasi berkala.
- [ ] **Retrieval & Indexing:**
  - [ ] Konfigurasi HNSW Vector DB diatur optimal: $M \ge 16$, $efSearch \ge 64$, $efConstruction \ge 128$.
  - [ ] Metadata payload index di-build khusus untuk field filtering utama (contoh: `tenant_id`, `user_id`, `timestamp`).
  - [ ] Menerapkan Hybrid Retrieval (Dense Vector + Inverted Lexical Index).
- [ ] **Post-Retrieval (Rerank & Assembly):**
  - [ ] Menggunakan Cross-Encoder yang di-host pada GPU worker terisolasi.
  - [ ] Memberlakukan fallback mechanism: jika reranker timeout (>300ms), fallback otomatis menggunakan urutan murni RRF.
  - [ ] De-duplikasi teks: memastikan chunk dari sumber identik disatukan (*deduped*) untuk menghemat token.
- [ ] **Security & RBAC:**
  - [ ] Pre-filtering hak akses di database level; bukan *post-filtering* di memori aplikasi (mencegah *empty retrieval* saat top-K terfilter).
  - [ ] Input sanitization: membersihkan injeksi prompt langsung (*Direct Prompt Injection*) dari teks kueri pengguna.
- [ ] **Observabilitas & Monitoring:**
  - [ ] Log detail setiap stage: Latency Retrieval Dense, Latency Retrieval Sparse, Latency Rerank, Latency LLM generation (Time-to-First-Token & Time-per-Output-Token).
  - [ ] Audit evaluasi berkala otomatis menggunakan framework metrik RAGAS.

---

## 12. Hands-on Practice

Buat dan eksekusi struktur direktori berikut untuk menguji Advanced RAG Engine di workstation Anda:

```bash
mkdir -p hands-on/m02
cd hands-on/m02
```

### File: `hands-on/m02/requirements.txt`
```text
pydantic>=2.0.0
numpy>=1.24.0
pytest>=7.0.0
pytest-asyncio>=0.21.0
```

### File: `hands-on/m02/test_advanced_rag.py`
```python
import pytest
import asyncio
import numpy as np
from typing import List, Dict, Any

# Impor langsung dari implementasi engine modular
from advanced_rag_engine import (
    AdvancedRAGEngine, 
    DocumentChunk, 
    SearchQuery, 
    UserContext
)

@pytest.fixture
def mock_dataset():
    parents = {
        "DOC_CORP": "Corporate Governance: Board members are elected for 3 years. Any capital expenditure above $10M requires unanimous board ratification.",
        "DOC_TECH": "Infrastructure Standard: Production Kubernetes clusters must run on minimal three control-plane nodes across distinct availability zones."
    }
    chunks = [
        DocumentChunk(
            id="c_corp_1",
            parent_id="DOC_CORP",
            content="Capital expenditure above $10M requires unanimous board ratification.",
            metadata={"clearance": 2, "source": "corp_gov.pdf"}
        ),
        DocumentChunk(
            id="c_tech_1",
            parent_id="DOC_TECH",
            content="Kubernetes clusters must run on three control-plane nodes across distinct zones.",
            metadata={"clearance": 1, "source": "infra_std.pdf"}
        )
    ]
    return parents, chunks

@pytest.mark.asyncio
async def test_hybrid_search_rbac_filtering(mock_dataset):
    parents, chunks = mock_dataset
    engine = AdvancedRAGEngine(parent_document_store=parents)
    engine.index_data(chunks)

    # Test 1: User level 1 tidak bisa mengakses chunk dengan clearance level 2
    query_restricted = SearchQuery(
        query_text="What is the rule for expenditure over $10M?",
        user_context=UserContext(user_id="intern", clearance_level=1)
    )
    result_restricted = await engine.execute_query(query_restricted)
    assert len(result_restricted["contexts"]) == 0

    # Test 2: User level 2 berhasil mengambil dan mengekspansi parent context
    query_permitted = SearchQuery(
        query_text="What is the rule for expenditure over $10M?",
        user_context=UserContext(user_id="director", clearance_level=2)
    )
    result_permitted = await engine.execute_query(query_permitted)
    assert len(result_permitted["contexts"]) == 1
    assert result_permitted["contexts"][0]["parent_id"] == "DOC_CORP"
    assert "unanimous board ratification" in result_permitted["contexts"][0]["expanded_context"]

@pytest.mark.asyncio
async def test_rrf_scoring_deterministic():
    engine = AdvancedRAGEngine(parent_document_store={})
    doc_a = DocumentChunk(id="A", parent_id="P_A", content="Doc A", metadata={})
    doc_b = DocumentChunk(id="B", parent_id="P_B", content="Doc B", metadata={})

    # Dense: Doc A (rank 1), Doc B (rank 2)
    dense_results = [doc_a, doc_b]
    # Sparse: Doc B (rank 1), Doc A (rank 2)
    sparse_results = [doc_b, doc_a]

    fused = engine._reciprocal_rank_fusion(dense_results, sparse_results)
    
    # Karena simetris, skor RRF untuk A dan B harus identik
    assert np.isclose(fused[0].score, fused[1].score), "RRF score calculation is non-deterministic"
```

### Eksekusi Pengujian:
```bash
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate di Windows
pip install -r requirements.txt
# Copy kode dari Bagian 7 ke dalam hands-on/m02/advanced_rag_engine.py
pytest -v test_advanced_rag.py
```

---

## 13. Exercises

### Level: Easy
1. Modifikasi fungsi `_reciprocal_rank_fusion` pada kelas `AdvancedRAGEngine` agar menerima konstanta kustom $k$ melalui argumen dinamis fungsi (bukan *hardcoded*).
2. Tambahkan pencatatan waktu eksekusi (*execution time tracing*) di dalam method `execute_query` menggunakan `time.perf_counter()`, laporkan durasi Dense Retrieval, Sparse Retrieval, RRF, dan Reranking dalam payload hasil kembalian.

### Level: Medium
1. Implementasikan class `ContextCompressor` yang diletakkan setelah fase Reranking. Modul ini harus memotong (*trim*) kalimat-kalimat pada chunk yang memiliki similarity token $< 0.15$ terhadap kueri, sehingga hanya klausa yang relevan langsung yang digabungkan ke final context.
2. Tambahkan layer **Metadata Extraction** otomatis: ketika chunk diindeks, ekstrak entitas bernama (*Named Entities* seperti tanggal, uang, atau lokasi) menggunakan regex / parsing sederhana dan simpan ke dalam dictionary `DocumentChunk.metadata`.

### Level: Hard
1. Buat ekstensi asinkron `HyDEQueryTransformer` yang mengimplementasikan metode:
   `async def transform(self, query: str) -> List[str]`
   Secara konkuren, komponen ini memanggil mock LLM untuk men-generate dua dokumen jawaban sintetis berlawanan (perspektif afirmasi dan negasi), kemudian memicu multi-vector ANN search terhadap vector database, lalu menyatukan hasilnya menggunakan varian RRF 3-Way.

---

## 14. Challenge

### Studi Kasus: Multi-Tenant Zero-Downtime Index Migration
Anda menjabat sebagai Principal AI Architect di sebuah perusahaan SaaS enterprise. Sistem produksi Anda saat ini melayani 500 perusahaan (tenant) dengan total 120 juta vektor dokumen pada cluster Qdrant berkapasitas 8 node. 

Model embedding yang digunakan saat ini (`all-MiniLM-L6-v2`, 384 dimensi) terbukti menghasilkan tingkat halusinasi tinggi pada istilah perbankan. Manajemen menuntut upgrade ke model embedding state-of-the-art 1024 dimensi (`bge-large-en-v1.5`) dan pengaktifan modul SPLADE sparse retrieval.

**Batasan & Tantangan Teknis:**
1. **Zero Downtime:** Sistem tidak boleh berhenti melayani kueri produksi (SLA 99.95% availability).
2. **Resource Constraint:** Kapasitas RAM cluster hanya memiliki sisa headroom sebesar 35%. Tidak diperbolehkan menyewa cluster paralel penuh (tidak bisa melakukan *blue-green deployment* total secara sekaligus karena batasan biaya cloud).
3. **Data Consistency:** Ingestion dokumen baru tetap berjalan pada kecepatan 100 dokumen/detik selama proses migrasi berlangsung.
4. **Tenant Isolation:** Tidak boleh ada kondisi di mana kueri tenant A membaca index baru sementara data miliknya masih berada di index lama tanpa sinkronisasi yang valid.

**Tugas Anda:**
Rancang arsitektur transisi (*migration blueprint*) komprehensif yang mencakup:
- Desain skema dual-index & routing layer logic.
- Strategi *lazy / rolling re-indexing* per-tenant.
- Mekanisme rekonsiliasi data mutasi dokumen yang masuk saat proses migrasi berjalan.
- Rencana rollback otomatis jika metrik akurasi retrieval tenant anjlok setelah di-switch.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konsep Dasar (Basic)
1. **Mengapa algoritma HNSW (Hierarchical Navigable Small World) digolongkan sebagai metode Approximate Nearest Neighbor (ANN), bukan Exact Nearest Neighbor (KNN)?**
   - A. Karena HNSW membulatkan nilai floating point vektor ke bilangan integer terdekat.
   - B. Karena HNSW menelusuri graf multilayer secara probabilistik tanpa membandingkan kueri terhadap setiap vektor di dalam koleksi.
   - C. Karena HNSW hanya mendukung metrik jarak Manhattan.
   - D. Karena HNSW tidak bisa bekerja pada dimensi vektor di atas 512.
   *Jawaban yang benar:* **B**. HNSW mengorbankan 100% recall demi kecepatan pencarian sub-linear ($\mathcal{O}(\log N)$) menggunakan struktur graf hierarkis.

2. **Apa fungsi utama konstanta k (default = 60) pada Reciprocal Rank Fusion (RRF)?**
   - A. Menentukan jumlah maksimum dokumen yang diambil.
   - B. Membatasi ukuran context window LLM.
   - C. Melembutkan (smoothing) bobot peringkat teratas agar dokumen yang unggul tipis di peringkat pertama pada satu retriever tidak mendominasi skor secara berlebihan.
   - D. Menghitung jumlah layer self-attention pada Cross-Encoder.
   *Jawaban yang benar:* **C**. Konstanta $k$ meredam disparitas rank ekstrim antar retriever.

3. **Perbedaan utama mekanisme pemrosesan antara model Bi-Encoder dan Cross-Encoder terletak pada:**
   - A. Bi-Encoder menggunakan Transformer, sedangkan Cross-Encoder menggunakan Recurrent Neural Network (RNN).
   - B. Bi-Encoder memproses kueri dan dokumen secara terpisah menjadi vektor tunggal, sedangkan Cross-Encoder memproses pasangan kueri-dokumen secara simultan dengan cross-attention token-to-token.
   - C. Bi-Encoder hanya bisa membaca teks pendek di bawah 50 token.
   - D. Cross-Encoder tidak membutuhkan GPU saat inferensi.
   *Jawaban yang benar:* **B**. Bi-encoder memungkinkan *pre-computing embeddings*, sedangkan cross-encoder memerlukan komputasi pasangan secara utuh.

4. **Fenomena "Lost in the Middle" pada LLM merujuk pada kondisi di mana:**
   - A. LLM kehilangan token output di tengah streaming karena koneksi TCP terputus.
   - B. LLM cenderung gagal mengingat dan memanfaatkan informasi penting yang disisipkan di tengah context window yang panjang.
   - C. Vektor embedding berada persis di titik ekuivalen koordinat 0.
   - D. Tokenizer membagi kata majemuk menjadi fragmen tak teridentifikasi.
   *Jawaban yang benar:* **B**. Eksperimen empiris membuktikan performa LLM tertinggi berada pada awal (*primacy*) dan akhir (*recency*) konteks.

5. **Apa keuntungan arsitektur Parent-Child Chunking dibandingkan pembagian teks berukuran seragam biasa?**
   - A. Menghilangkan kebutuhan Vector DB.
   - B. Pencarian vektor dilakukan pada child chunk kecil yang fokus, tetapi konteks yang dikirim ke LLM adalah parent chunk utuh yang kaya konteks.
   - C. Mengurangi penggunaan memori disk hingga 90%.
   - D. Mengubah teks secara otomatis menjadi representasi gambar.
   *Jawaban yang benar:* **B**. Menjaga granularitas pencarian sekaligus mempertahankan kelengkapan narasi informasi.

---

### Bagian B: Analisis Tingkat Menengah (Intermediate)
6. **Di lingkungan pencarian hybrid (Dense + BM25), pada kasus apa sistem BM25 Sparse Search secara konsisten mengungguli Dense Retrieval?**
   - A. Kueri berupa ringkasan emosional atau sentimen abstrak.
   - B. Kueri yang mencari sinonim konsep (misal: "dokter" vs "ahli medis").
   - C. Kueri yang mencari entitas kaku spesifik, seperti kode serial perangkat, format UUID, nomor kasus perundangan, atau nama model komponen eksak.
   - D. Kueri dalam bahasa yang belum pernah dipelajari oleh model NLP.
   *Jawaban yang benar:* **C**. Dense retrieval sering memetakan representasi alfanumerik yang mirip ke koordinat semantik acak, sementara inverted index BM25 mengeksekusi *exact lexical match*.

7. **Mengapa metadata filtering dengan pendekatan "Post-Filtering" (Filtering setelah ANN search) berbahaya di lingkungan produksi multi-tenant ber-RBAC tinggi?**
   - A. Karena dapat memicu out-of-memory error pada driver database.
   - B. Jika Top-K hasil ANN seluruhnya didominasi oleh dokumen yang bukan hak akses pengguna, filter aplikasi akan membuang semua dokumen tersebut, menghasilkan *empty context* padahal data sah tersedia di urutan berikutnya.
   - C. Karena format metadata post-filtering tidak mendukung format JSON.
   - D. Karena post-filtering memperlambat kecepatan komputasi GPU secara linear.
   *Jawaban yang benar:* **B**. Ini disebut fenomena *Recall Collapse*. Solusinya adalah *Pre-filtering* langsung di level indeks graf ANN.

8. **Teknik Hypothetical Document Embeddings (HyDE) berisiko menurunkan performa retrieval apabila:**
   - A. Model embedding target memiliki dimensi lebih besar dari 768.
   - B. LLM menghasilkan dokumen hipotetis yang mengandung fakta halusinasi spesifik yang secara drastis menyimpang dari korpus dokumen sebenarnya.
   - C. User memasukkan kueri teks yang terlalu panjang (>1000 kata).
   - D. Index yang digunakan bertipe sparse inverted index.
   *Jawaban yang benar:* **B**. Jika dokumen sintesis melenceng dari kenyataan korpus, dense search akan menuju wilayah ruang vektor yang salah (*hallucinatory drift*).

9. **Metrik evaluasi "Faithfulness" / "Groundedness" dalam RAG Triad mengukur:**
   - A. Tingkat kesesuaian antara pertanyaan pengguna dan kueri rewriter.
   - B. Seberapa akurat embedding model dalam mengelompokkan teks sejenis.
   - C. Sejauh mana setiap klausa klaim faktual pada jawaban yang dihasilkan LLM dapat diverifikasi secara inferensial murni dari konteks yang diberikan (tanpa membawa pengetahuan eksternal yang tidak tertulis).
   - D. Kecepatan streaming token dari LLM per detik.
   *Jawaban yang benar:* **C**. *Faithfulness* memastikan LLM tidak berhalusinasi di luar korpus context window yang disajikan.

10. **Bagaimana implementasi Semantic Cache berbasis Vector Cosine Similarity menangani invalidasi data secara aman?**
    - A. Semantic cache tidak memerlukan invalidasi data karena representasi vektor bersifat permanen.
    - B. Dengan menyertakan version tag / document update timestamp pada namespace cache; jika versi dokumen diperbarui, entri cache terkait dianggap kadaluarsa (*stale*).
    - C. Menghapus seluruh memori cache setiap 60 detik secara global.
    - D. Membatasi pencarian cache hanya untuk pengguna dengan clearance level tertinggi.
    *Jawaban yang benar:* **B**. Menghubungkan hash/vektor cache dengan versi payload dokumen menjamin data basi (*stale data*) tidak disajikan ke pengguna.

---

### Bagian C: Pemecahan Masalah Skenario Kasus Produksi
11. **Skenario Kasus 1: Lonjakan Latency Reranking**  
    Sebuah aplikasi enterprise RAG mengalami kenaikan $p99$ latency retrieval dari 180 ms menjadi 2.4 detik setelah penambahan Cross-Encoder Reranker (*BGE-Reranker-Large*). Profiling sistem menunjukkan resource GPU mencapai 100% compute load konstan saat concurrent traffic mencapai 150 QPS.
    
    *Tindakan arsitektural mana yang paling tepat dan efisien untuk memulihkan latency di bawah 400 ms tanpa mengorbankan akurasi sistem secara signifikan?*
    - A. Menghapus modul reranker dan kembali menggunakan Naive RAG sepenuhnya.
    - B. Mengurangi candidate pool yang masuk ke Cross-Encoder dari Top-100 menjadi Top-20 hasil pasca-RRF, serta mengompilasi model reranker ke format TensorRT FP16/INT8 pada cluster inference terakselerasi.
    - C. Mengganti database vektor dari Qdrant ke penyimpanan file teks flat.
    - D. Menambah chunk size dari 256 token menjadi 4096 token agar kandidat yang di-rerank berkurang secara natural.
    *Jawaban yang benar:* **B**. Kompleksitas waktu Cross-Encoder bergantung linear terhadap jumlah kandidat pasangan teks ($N$). Membatasi pool ke Top-20 memangkas beban komputasi hingga 80%, dan kuantisasi TensorRT mempercepat inferensi inference matrix.

12. **Skenario Kasus 2: Data Leaks across Multi-Tenants**  
    Tim audit menemukan bahwa pengguna dari Tenant "Bank Mandiri" sesekali mendapatkan kutipan data internal milik Tenant "Bank BCA" ketika mengajukan pertanyaan umum mengenai "Format pelaporan kepatuhan BI-FAST". Sistem menggunakan arsitektur Single-Collection Vector Store multi-tenant.
    
    *Di mana letak kerentanan arsitektural sistem tersebut dan bagaimana cara remediasinya?*
    - A. Kerentanan pada model embedding; model harus di-fine-tune ulang khusus untuk tiap bank.
    - B. Terjadi post-filtering di lapisan controller di mana sistem mengambil top-100 dokumen global terlebih dahulu baru kemudian memfilter tenant ID; solusinya adalah menerapkan *mandatory hard pre-filtering* pada tingkat index query vector database dengan klausul isolation metadata tenant yang teruji.
    - C. BM25 tidak mendukung karakter angka, sehingga filter ID gagal bekerja.
    - D. Cross-encoder mencampuradukkan bobot attention; solusinya adalah menonaktifkan layer attention.
    *Jawaban yang benar:* **B**. Melakukan retrieval tanpa filter tenant di tahap awal (*post-filtering*) menyebabkan cross-tenant contamination jika pool teratas terisi oleh data tenant lain. Pre-filtering menjamin pembatasan partisi mutlak di ruang pencarian.

13. **Skenario Kasus 3: Semantic Drift pada Multi-Turn Dialogue**  
    Pada turn ke-5 percakapan asisten teknis RAG perbaikan mesin pabrik, pengguna mengetik: *"Bagaimana cara melumasi komponen tersebut?"*. Sistem gagal total melakukan retrieval karena dokumen yang terambil membahas komponen acak lain yang tidak relevan.
    
    *Komponen arsitektur Advanced RAG mana yang hilang dari sistem tersebut untuk menangani kueri konteks percakapan?*
    - A. Parent-Document Retriever.
    - B. Contextual Query Rewriter / Condensation Engine yang merumuskan ulang kueri ambigu menjadi pertanyaan mandiri (*stand-alone query*) berdasarkan riwayat histori obrolan sebelumnya sebelum kueri dieksekusi ke vector index.
    - C. Algoritma K-Means Clustering pada Vector DB.
    - D. Inverted Index BM25.
    *Jawaban yang benar:* **B**. Kata referensial (*anaphora*) seperti "komponen tersebut" membutuhkan *Query Rewriter* (misal: "Bagaimana cara melumasi poros turbin hidrolik Model-X?") agar retriever dapat menemukan chunk yang tepat.

---

## 16. Summary

Arsitektur **Advanced RAG Enterprise** memitigasi kegagalan struktural Naive RAG melalui pendekatan *multi-stage pipeline*:

```
Query Expansion (HyDE/Multi-Query)
       │
       ▼
Hybrid Search (Dense + Sparse Inverted Index)
       │
       ▼
Algorithmic Fusion (Reciprocal Rank Fusion - RRF)
       │
       ▼
Deep Relevance Validation (Cross-Encoder Reranking)
       │
       ▼
Context Resolution (Parent-Child Hierarchy)
       │
       ▼
Strict Guardrails Execution & Streaming LLM Generation
```

1. **Hybrid Retrieval:** Penggabungan representasi *Dense* (HNSW) dan *Sparse* (BM25/SPLADE) via formula **RRF** memadukan keunggulan pemahaman semantik abstrak dengan ketepatan pencarian leksikal eksak.
2. **Two-Stage Filtering:** Penggunaan *Bi-Encoder* untuk mengambil ratusan kandidat awal secara instan ($\mathcal{O}(1)$), dipadukan dengan *Cross-Encoder* pada second-stage untuk menyaring Top-3 hingga Top-5 konteks terpresisi tinggi.
3. **Parent-Child Optimization:** Child chunk berdimensi ramping menjamin skor embedding bebas noise, sementara parent context utuh menjamin LLM menerima kelengkapan argumen tanpa terpotong.
4. **Production Tenancy:** Penerapan *pre-filtered index partition* berbasis atribut RBAC wajib diimplementasikan langsung pada query graf database vektor guna menjamin isolasi data mutlak di lingkungan enterprise.