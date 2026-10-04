# BAB 04: Production Retrieval-Augmented Generation
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis** kegagalan struktural pada arsitektur *Naive RAG* (*lost-in-the-middle*, *semantic drift*, *low-precision sparse keyword miss*) dalam skala produksi enterprise.
- **Merancang** arsitektur *Advanced RAG* multi-tahap yang mengintegrasikan teknik *Parent-Document/Hierarchical Retrieval*, *Semantic Chunking*, dan *Dynamic Context Trimming*.
- **Mengimplementasikan** mekanisme pencarian hibrida (*Hybrid Search*) menggabungkan *Dense Vector Embeddings* dan *Sparse Lexical Search* (BM25) menggunakan algoritma *Reciprocal Rank Fusion* (RRF).
- **Mengintegrasikan** model *Cross-Encoder Re-ranking* untuk meningkatkan *Context Precision* hingga di atas 90% pada tahap pasca-retrieval.
- **Mengembangkan** pipeline transformasi kueri tingkat lanjut (*Hypothetical Document Embeddings/HyDE*, *Multi-Query Expansion*, dan *Step-Back Prompting*).
- **Mengevaluasi** performa retrieval dan generasi secara terukur menggunakan metrik Ragas (*Faithfulness*, *Answer Relevance*, *Context Precision*, *Context Recall*) dalam CI/CD pipeline.

---

### 2. Prerequisites

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Dasar RAG (Module 01):** Konsep dasar *embedding vector*, *cosine similarity*, *naive chunking* (karakter/token), dan LLM prompt orchestration.
- **Python Lanjutan:** Pemrograman *asynchronous* (`asyncio`), *type-hinting*, dan validasi data dengan `pydantic v2`.
- **Sistem Basis Data:** Pemahaman indeks pencarian (*Inverted Index*, HNSW, IVF-PQ) dan operasi CRUD pada setidaknya satu *Vector Database* (Qdrant, Milvus, atau pgvector).
- **Aljabar Linear Dasar:** Operasi *dot product*, normalisasi L2, dan pemahaman ruang vektor dimensi tinggi ($D \in [768, 3072]$).

---

### 3. Concept & Internal Architecture

Implementasi enterprise RAG menolak pendekatan *Naive RAG* (Text $\rightarrow$ Fixed Chunk $\rightarrow$ Embedding $\rightarrow$ Top-K $\rightarrow$ LLM Context). Pipeline produksi modern beroperasi melalui 4 layer modular:

```
[Ingestion & Indexing] ──> [Query Transformation] ──> [Multi-Stage Retrieval] ──> [Context Post-Processing]
```

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE ADVANCED RAG ARCHITECTURE                            |
+----------------------------------------------------------------------------------------------------+
                                                                                                      
 1. INGESTION ENGINE                                                                                 
 +----------------+      +---------------------+      +-------------------------------------------+  
 | Raw Documents  | ---> | Structural Parser   | ---> | Semantic / Hierarchical Chunker           |  
 | (PDF, DOCX, DB)|      | (Layout-aware)      |      | Parent: 2048 tokens | Child: 256 tokens   |  
 +----------------+      +---------------------+      +-------------------------------------------+  
                                                                    |                 |               
                                                                    v                 v               
                                                        +------------------+  +-------------------+   
                                                        | Sparse Index     |  | Dense Vector      |   
                                                        | (BM25 Inverted)  |  | (HNSW / DiskANN)  |   
                                                        +------------------+  +-------------------+   
 2. RUNTIME RETRIEVAL & GENERATION                                                                    
                                                                                                      
      [ User Query ]                                                                                  
            │                                                                                         
            ▼                                                                                         
 +--------------------+       +------------------------------------+                                  
 | Query Transformer  | ----> | - HyDE (Hypothetical Doc Generator)|                                  
 |                    |       | - Sub-Query Decomposition          |                                  
 +--------------------+       +------------------------------------+                                  
            │                                                                                         
            ├────────────────────────────────────────┬────────────────────────────────────────┐       
            ▼                                        ▼                                        ▼       
 +---------------------+                  +---------------------+                  +----------------+ 
 | Sparse Search       |                  | Dense Vector Search |                  | Metadata Hard- | 
 | (BM25 BM-K1=1.5)    |                  | (Top-50, Cosine)    |                  | Filtering      | 
 +---------------------+                  +---------------------+                  +----------------+ 
            │                                        │                                        │       
            └────────────────────┬───────────────────┘                                        │       
                                 ▼                                                            │       
                     +-----------------------+                                                │       
                     | Reciprocal Rank       |                                                │       
                     | Fusion (RRF)          |                                                │       
                     +-----------------------+                                                │       
                                 │                                                            │       
                                 ▼                                                            │       
                     +-----------------------+ <──────────────────────────────────────────────┘       
                     | Top-N Fusion Results  | (e.g., N = 40)                                         
                     +-----------------------+                                                        
                                 │                                                                    
                                 ▼                                                                    
                     +-----------------------+                                                        
                     | Cross-Encoder Rerank  | (e.g., BAAI/bge-reranker-large)                        
                     | Computes Cross-Attn   |                                                        
                     +-----------------------+                                                        
                                 │                                                                    
                                 ▼                                                                    
                     +-----------------------+                                                        
                     | Parent Node Resolver  | (Swaps child chunks for parent context window)         
                     +-----------------------+                                                        
                                 │                                                                    
                                 ▼                                                                    
                     +-----------------------+                                                        
                     | Dynamic Context       | (De-duplication, Token Budget Packaging,               
                     | Trimmer & Compressor  |  Lost-in-the-middle mitigations)                       
                     +-----------------------+                                                        
                                 │                                                                    
                                 ▼                                                                    
                     +-----------------------+                                                        
                     | Augmented Prompt +    |                                                        
                     | LLM Generation        |                                                        
                     +-----------------------+                                                        
```

#### Layer 1: Ingestion & Hierarchical Representation
- **Parent-Child Document Splitting:** Chunk kecil ($256$ token) di-embed untuk akurasi pencarian vektor (*retrieval fidelity*). Namun, ketika chunk ini terpilih, sistem menyuntikkan *parent chunk* ($1024$ - $2048$ token) ke dalam konteks prompt LLM agar konteks naratif tidak terputus.
- **Semantic Chunking:** Memecah teks bukan berdasarkan jumlah karakter kaku, melainkan mengukur lonjakan jarak kosinus (*cosine distance spike*) antar-kalimat berurutan menggunakan model embedding ringan. Jika jarak melebihi persentil tertentu (misalnya p95), batas chunk dibuat.

#### Layer 2: Query Transformation
- **HyDE (Hypothetical Document Embeddings):** Menggunakan LLM cepat (misal: Claude 3 Haiku, GPT-4o-mini) untuk menghasilkan dokumen hipotetis yang menjawab kueri pengguna. Vektor embedding dokumen hipotetis ini lebih dekat ke dokumen target di dalam ruang vektor dibanding embedding kueri asli yang pendek dan ambigu.
- **Multi-Query Expansion:** Menerjemahkan satu kueri ambigu menjadi 3–5 variasi semantik kueri untuk memperluas jangkauan recall.

#### Layer 3: Hybrid Search & Reciprocal Rank Fusion (RRF)
Menggabungkan ruang pencarian leksikal dan semantik:
- **Dense Vector Search:** Menangkap intensi semantik umum, sinonim, dan kesamaan konsep (menggunakan representasi bi-encoder dense).
- **Sparse Lexical Search (BM25 / SPLADE):** Menangkap kata kunci unik bernilai tinggi seperti nomor seri, kode hukum, nama entitas, atau akronim spesifik yang kerap tereliminasi oleh proses pooling vektor embedding dense.
- **RRF Calculation:**
  $$RRF\_Score(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  di mana $M$ adalah himpunan sistem pencari (Dense + Sparse), $r_m(d)$ adalah peringkat dokumen $d$ pada sistem $m$, dan $k$ adalah konstanta perataan (standar: $k = 60$).

#### Layer 4: Re-Ranking (Cross-Encoder)
- Bi-encoder (yang digunakan dalam Dense Vector Search) memetakan kueri dan dokumen secara independen ke dalam embedding tunggal: $\text{Sim}(q, d) = \cos(\mathbf{e}_q, \mathbf{e}_d)$. Kinerja retrieval cepat, namun kehilangan interaksi token silang (*cross-attention*).
- **Cross-Encoder Reranker:** Menerima pasangan kueri dan dokumen secara simultan ke dalam transformer: $\text{Score} = \text{Softmax}(\mathbf{W} \cdot \text{Transformer}([q; d]))$. Seluruh token dalam kueri memperhatikan (*attend to*) seluruh token dalam dokumen, menghasilkan ketelitian relevansi yang jauh lebih tinggi.

---

### 4. Why & What

| Dimensi | Naive RAG | Advanced Production RAG |
| :--- | :--- | :--- |
| **Metode Chunking** | Fixed-size window (512 token, overlap 50 token). | Semantic Chunking + Hierarchical (Parent-Child) Indexing. |
| **Pencarian Dokumen** | Pure Cosine Similarity (Dense-only). | Hybrid Search (Dense HNSW + Sparse BM25/SPLADE) via RRF. |
| **Penanganan Kueri** | Raw user string langsung dilempar ke embedding model. | Query Transformation (HyDE, Sub-query routing, Step-back). |
| **Relevansi Konteks** | Bergantung penuh pada embedding vector dot-product (bising). | 2-Stage Retrieval (Candidate Retrieval $\rightarrow$ Cross-Encoder Re-ranking). |
| **Prompt Injection Noise** | Chunk teratas dijejalkan langsung; memicu *Lost-in-the-Middle*. | Context Compression, Deduplication, & Structural Serialization. |
| **Observabilitas & Evaluasi** | Berbasis inspeksi manual kualitatif ("terlihat bagus"). | Evaluasi kuantitatif berkelanjutan via Ragas/TruLens matrix. |

**Mengapa ini krusial?**
Dalam domain enterprise (Fintech, Medtech, Legaltech), kegagalan retrieval sebesar 5% dapat memicu kerugian finansial atau pelanggaran kepatuhan hukum (*regulatory compliance breach*). *Naive RAG* rentan mengalami kegagalan fatal saat menghadapi dokumen korporat yang sarat format tabular, istilah spesifik, dokumen hukum multi-halaman, serta kueri pengguna yang minim konteks.

---

### 5. How (Workflow Detail)

Alur runtime Advanced RAG beroperasi dalam tahapan berurutan berikut:

1. **Query Pre-flight & Expansion:**
   - Kueri mentah masuk: `"Regulasi batas rasio modal tier 1 perbankan digital pasca 2023"`.
   - HyDE Generator menghasilkan sintesis paragraf regulasi hipotetis (~150 token).
   - Menghasilkan vektor embedding dari teks dokumen hipotetis tersebut ($\mathbf{v}_{hyde}$).

2. **Parallel Dual-Track Retrieval:**
   - **Track A (Dense):** Kirim $\mathbf{v}_{hyde}$ ke Vector Database. Ambil top-50 *child chunks* berdasarkan *Cosine Similarity* menggunakan indeks HNSW.
   - **Track B (Sparse):** Jalankan kueri mentah terhadap indeks Inverted BM25. Ambil top-50 *child chunks* berdasarkan kalkulasi term saturation ($k_1$) dan length normalization ($b$).

3. **Reciprocal Rank Fusion (RRF):**
   - Gabungkan kandidat dari Track A dan Track B.
   - Hitung skor gabungan RRF dengan $k=60$. Ambil top-30 kandidat teratas.

4. **Cross-Encoder Re-ranking:**
   - Bentuk array pasangan: `[[query, candidate_text_1], ..., [query, candidate_text_30]]`.
   - Jalankan inferensi menggunakan model Cross-Encoder (misal: `BAAI/bge-reranker-large`).
   - Ambil top-5 chunk dengan logit probability tertinggi.

5. **Parent Node Resolution & Dynamic Packing:**
   - Untuk setiap child chunk dari top-5 hasil rerank, ambil `parent_chunk_id` dari metadata store.
   - Deduplikasi parent chunks yang identik.
   - Pangkas whitespace dan token redundan hingga pas dengan token budget yang dialokasikan (misalnya: maksimum 3.000 token konteks).
   - Urutkan chunk secara strategis: letakkan chunk dengan relevansi tertinggi di awal dan akhir teks prompt untuk menghindari fenomena *Lost-in-the-Middle*.

6. **Generation & Guardrail Validation:**
   - Konstruksi prompt dengan instruksi sitasi ketat (*grounded citations*).
   - LLM menghasilkan jawaban yang menyertakan referensi `[Doc ID]`.
   - Validator pasca-generasi memverifikasi bahwa seluruh klaim faktual memetakan ID dokumen yang valid.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Perpustakaan Riset Nasional
Bayangkan Anda seorang analis riset yang membutuhkan undang-undang spesifik di perpustakaan nasional raksasa:
- **Naive RAG:** Anda mendatangi satu pustakawan magang, menyebutkan kalimat kueri Anda, lalu ia hanya mencarikan 5 buku yang judulnya mirip secara semantik. Hasilnya sering kali meleset karena kata kunci formal tidak cocok.
- **HyDE:** Sebelum mencari, pustakawan senior membayangkan draft isi paragraf undang-undang yang Anda maksud.
- **Hybrid Search (Dense + Sparse):** Perpustakaan mengerahkan dua kurator: Kurator 1 mencari konsep makna secara konseptual (Dense), Kurator 2 mencocokkan nomor pasal dan kata hukum unik secara mekanis melalui indeks katalog kartu (Sparse/BM25).
- **Reciprocal Rank Fusion (RRF):** Kedua kurator menaruh daftar temuan mereka di meja dan menggabungkan rekomendasinya berdasarkan konsensus peringkat.
- **Cross-Encoder Reranker:** Seorang Kepala Litbang membaca mendalam setiap halaman terpilih berdampingan dengan pertanyaan Anda satu per satu untuk memastikan relevansi absolut.
- **Parent Retrieval:** Ketika menemukan bab relevan, ia tidak merobek 1 kalimat saja (child), melainkan membawakan Anda seluruh map ordonansi terkait (parent) agar konteks utuh tidak hilang.

---

### 7. Simple Example & Practical Example

#### A. Konsep Inti Sederhana: Reciprocal Rank Fusion (RRF) murni Python

```python
from typing import Dict, List, Any

def reciprocal_rank_fusion(
    dense_results: List[str], 
    sparse_results: List[str], 
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Menggabungkan hasil retrieval dense dan sparse menggunakan algoritma RRF.
    """
    rrf_score: Dict[str, float] = {}

    def add_ranks(results: List[str]):
        for rank, doc_id in enumerate(results):
            if doc_id not in rrf_score:
                rrf_score[doc_id] = 0.0
            rrf_score[doc_id] += 1.0 / (k + (rank + 1))

    add_ranks(dense_results)
    add_ranks(sparse_results)

    # Urutkan berdasarkan skor RRF tertinggi
    sorted_docs = sorted(rrf_score.items(), key=lambda item: item[1], reverse=True)
    return [{"doc_id": doc_id, "score": score} for doc_id, score in sorted_docs]

# Contoh Penggunaan Sederhana
dense_hits = ["doc_A", "doc_B", "doc_C", "doc_D"]
sparse_hits = ["doc_C", "doc_A", "doc_E", "doc_F"]

fusion_results = reciprocal_rank_fusion(dense_hits, sparse_hits, k=60)
print("Hasil RRF:", fusion_results[:3])
```

#### B. Practical Enterprise Implementation: Advanced Multi-Stage RAG Pipeline

Contoh implementasi lengkap production-grade: Hybrid Search, Reranking, Parent Resolution, dan Asynchronous Query Handling.

```python
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np
from pydantic import BaseModel, Field

# Setup logging korporat
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("EnterpriseRAGPipeline")

# ==========================================
# Domain Models (Pydantic v2)
# ==========================================

class DocumentChunk(BaseModel):
    chunk_id: str
    parent_id: str
    content: str
    score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ParentDocument(BaseModel):
    parent_id: str
    full_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RetrievalResult(BaseModel):
    parent_id: str
    content: str
    relevance_score: float
    matched_child_chunks: List[str]

# ==========================================
# Mock Services (Substitusi dengan Client Asli di Produksi)
# ==========================================

class MockVectorStore:
    """Simulasi Vector Database (Qdrant / Milvus)"""
    async def dense_search(self, query_vector: List[float], top_k: int = 50) -> List[DocumentChunk]:
        await asyncio.sleep(0.02)  # Network latency ~20ms
        # Mengembalikan mock chunk terdekat
        return [
            DocumentChunk(
                chunk_id=f"c_{i}",
                parent_id=f"p_{i // 2}",
                content=f"Klausul regulasi permodalan perbankan sub-seksi {i}. Batas minimum CAR 12%.",
                score=0.85 - (i * 0.01),
                metadata={"source": "regulasi_ojk_2024.pdf"}
            )
            for i in range(top_k)
        ]

class MockBM25Engine:
    """Simulasi BM25 Inverted Search Engine (OpenSearch / Tantivy)"""
    async def sparse_search(self, query: str, top_k: int = 50) -> List[DocumentChunk]:
        await asyncio.sleep(0.015)  # Network latency ~15ms
        return [
            DocumentChunk(
                chunk_id=f"c_{i}",
                parent_id=f"p_{i // 2}",
                content=f"Klausul regulasi permodalan perbankan sub-seksi {i}. Batas minimum CAR 12%.",
                score=14.5 - (i * 0.2),
                metadata={"source": "regulasi_ojk_2024.pdf"}
            )
            for i in [2, 0, 10, 15, 3] # Mensimulasikan hasil temu sparse yang berbeda urutan
        ]

class MockCrossEncoderReranker:
    """Simulasi Cross-Encoder Transformer Inference Engine"""
    async def rerank(self, query: str, chunks: List[DocumentChunk], top_n: int = 3) -> List[DocumentChunk]:
        await asyncio.sleep(0.05)  # Latensi inferensi GPU reranker ~50ms
        # Simulasi scoring cross-attention: beri bobot lebih tinggi pada dokumen genap
        for chunk in chunks:
            raw_id = int(chunk.chunk_id.split("_")[1])
            chunk.score = 0.95 if raw_id == 0 else 0.50 + (1.0 / (raw_id + 1)) * 0.4
        
        sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        return sorted_chunks[:top_n]

class MockDocumentStore:
    """Penyimpan Dokumen Induk (PostgreSQL / Redis / MongoDB)"""
    def __init__(self):
        self._store = {
            "p_0": ParentDocument(
                parent_id="p_0",
                full_content="BAB V: PENGELOLAAN MODAL INTI. Bank digital wajib menjaga rasio Kewajiban Penyediaan Modal Minimum (KPMM) atau Capital Adequacy Ratio (CAR) paling rendah sebesar 12%. Klausul regulasi permodalan perbankan sub-seksi 0 dan 1 mencakup seluruh aset tertimbang menurut risiko kredit operasional secara komprehensif.",
                metadata={"jurisdiction": "ID", "year": 2024}
            ),
            "p_1": ParentDocument(
                parent_id="p_1",
                full_content="BAB VI: RISIKO LIKUIDITAS. Bank wajib memelihara kecukupan instrumen likuid berkualitas tinggi secara harian sesuai regulasi pasar modal.",
                metadata={"jurisdiction": "ID", "year": 2024}
            )
        }

    async def get_parents(self, parent_ids: List[str]) -> Dict[str, ParentDocument]:
        await asyncio.sleep(0.01)
        return {pid: self._store[pid] for pid in parent_ids if pid in self._store}

# ==========================================
# Core Advanced RAG Orchestrator
# ==========================================

class ProductionRAGRetriever:
    def __init__(
        self,
        vector_store: MockVectorStore,
        bm25_engine: MockBM25Engine,
        reranker: MockCrossEncoderReranker,
        doc_store: MockDocumentStore,
        rrf_constant: int = 60
    ):
        self.vector_store = vector_store
        self.bm25_engine = bm25_engine
        self.reranker = reranker
        self.doc_store = doc_store
        self.rrf_k = rrf_constant

    def _reciprocal_rank_fusion(
        self,
        dense_hits: List[DocumentChunk],
        sparse_hits: List[DocumentChunk],
        limit: int = 20
    ) -> List[DocumentChunk]:
        """Menghitung fusi peringkat deterministik dari dual retrieval pipelines."""
        fused_scores: Dict[str, float] = {}
        chunk_map: Dict[str, DocumentChunk] = {}

        for rank, chunk in enumerate(dense_hits):
            chunk_map[chunk.chunk_id] = chunk
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        for rank, chunk in enumerate(sparse_hits):
            if chunk.chunk_id not in chunk_map:
                chunk_map[chunk.chunk_id] = chunk
            fused_scores[chunk.chunk_id] = fused_scores.get(chunk.chunk_id, 0.0) + (1.0 / (self.rrf_k + (rank + 1)))

        sorted_chunk_ids = sorted(fused_scores.keys(), key=lambda cid: fused_scores[cid], reverse=True)
        
        results: List[DocumentChunk] = []
        for cid in sorted_chunk_ids[:limit]:
            c = chunk_map[cid]
            c.score = fused_scores[cid]
            results.append(c)
        return results

    async def retrieve(self, query: str, query_vector: List[float], final_top_k: int = 2) -> List[RetrievalResult]:
        logger.info(f"Memulai pipeline retrieval multi-stage untuk kueri: '{query}'")

        # 1. Jalankan Dense dan Sparse search secara paralel
        dense_task = asyncio.create_task(self.vector_store.dense_search(query_vector, top_k=20))
        sparse_task = asyncio.create_task(self.bm25_engine.sparse_search(query, top_k=20))
        
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        logger.info(f"Retrieved: Dense={len(dense_results)} chunks, Sparse={len(sparse_results)} chunks")

        # 2. Reciprocal Rank Fusion
        fused_candidates = self._reciprocal_rank_fusion(dense_results, sparse_results, limit=20)
        logger.info(f"Hasil fusi RRF terkumpul: {len(fused_candidates)} kandidat unik")

        # 3. Cross-Encoder Reranking
        reranked_chunks = await self.reranker.rerank(query, fused_candidates, top_n=5)
        logger.info(f"Reranking selesai. Top score: {reranked_chunks[0].score:.4f} (ID: {reranked_chunks[0].chunk_id})")

        # 4. Parent Resolution & Deduplication
        parent_chunk_mapping: Dict[str, List[str]] = {}
        parent_scores: Dict[str, float] = {}

        for chunk in reranked_chunks:
            p_id = chunk.parent_id
            if p_id not in parent_chunk_mapping:
                parent_chunk_mapping[p_id] = []
                parent_scores[p_id] = chunk.score
            parent_chunk_mapping[p_id].append(chunk.chunk_id)
            # Simpan skor tertinggi dari child yang terasosiasi
            parent_scores[p_id] = max(parent_scores[p_id], chunk.score)

        # Ambil full-text parent dari docstore
        target_parents = list(parent_chunk_mapping.keys())[:final_top_k]
        parent_docs = await self.doc_store.get_parents(target_parents)

        # 5. Format Luaran Siap Pakai LLM
        final_results: List[RetrievalResult] = []
        for p_id in target_parents:
            if p_id in parent_docs:
                final_results.append(
                    RetrievalResult(
                        parent_id=p_id,
                        content=parent_docs[p_id].full_content,
                        relevance_score=parent_scores[p_id],
                        matched_child_chunks=parent_chunk_mapping[p_id]
                    )
                )

        return final_results

# ==========================================
# Runtime Demonstration
# ==========================================

async def main():
    retriever = ProductionRAGRetriever(
        vector_store=MockVectorStore(),
        bm25_engine=MockBM25Engine(),
        reranker=MockCrossEncoderReranker(),
        doc_store=MockDocumentStore()
    )

    dummy_vector = [0.012] * 1536
    user_query = "Berapa batas rasio modal tier 1 dan KPMM minimum bank digital?"

    results = await retriever.retrieve(query=user_query, query_vector=dummy_vector, final_top_k=2)

    print("\n" + "="*80)
    print("OUTPUT KONTEKS TERRESOLUSI UNTUK PROMPT INJECTION")
    print("="*80)
    for idx, res in enumerate(results, 1):
        print(f"[{idx}] Parent ID : {res.parent_id} | Max Relevance Logit: {res.relevance_score:.4f}")
        print(f"    Child Chunks : {res.matched_child_chunks}")
        print(f"    Payload Teks : {res.content}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real-World Case Study

#### Skenario Enterprise
**Kasus:** Sistem Analisis Regulasi dan Legal Compliance Kontrak Perbankan Global (Bank Skala Tier-1).
- **Volume Data:** 12 juta dokumen PDF multihalaman (Kontrak sindikasi, edaran otoritas keuangan global seperti Basel III/IV, OJK, FATF).
- **SLA Operasional:** Retrieval latensi $P99 < 850\text{ ms}$, False Information/Hallucination Rate $< 0.1\%$.
- **Kegagalan Implementasi Awal (*Naive RAG*):**
  Akurasi kueri kompleks hanya mencapai 42%. Masalah utama:
  1. Istilah klausul hukum seperti *"Cross-Default Threshold"* dicari menggunakan vektor murni dan sering mengembalikan dokumen yang membahas *default* secara umum, bukan klausul spesifik yang memiliki batasan nominal tertentu.
  2. Model LLM kehilangan konteks referensi karena pasal dipotong secara arbitrer di tengah kalimat (*chunk boundary truncation*).

#### Transformasi Arsitektur Produksi
1. **Layout-Aware PDF Ingestion:** Dokumen diproses dengan parsing berbasis bounding-box untuk mempertahankan tabel finansial dalam format Markdown utuh alih-alih meratakan teks menjadi untaian kalimat tanpa struktur.
2. **Hierarchical Storage:** Dokumen diindeks sebagai *Child Chunks* berukuran 200 token untuk menjamin akurasi dot-product semantik, namun memetakan metadata ke *Parent Section* berukuran 1.500 token.
3. **Dedicated Inverted Index (BM25) Cluster:** Dijalankan paralel di samping cluster HNSW Vector Database untuk menangkap kode undang-undang (contoh: "POJK 12/POJK.03/2021").
4. **GPU Reranking Pods:** Penyebaran model `bge-reranker-large` pada pod Kubernetes dengan akselerator GPU (NVIDIA T4) via Triton Inference Server dengan teknik *Dynamic Batching*.
5. **Dampak Metrik:**
   - *Context Recall* meningkat dari 48% ke 94.2%.
   - *Ragas Faithfulness* melonjak dari 61% ke 99.1%.
   - Latensi stabil pada $P50 = 310\text{ ms}$, $P99 = 720\text{ ms}$.

---

### 9. Trade-offs

| Pendekatan / Komponen | Keuntungan (Pros) | Biaya & Konsekuensi (Cons) | Latency Overhead | Strategi Mitigasi Produksi |
| :--- | :--- | :--- | :--- | :--- |
| **Dense Only (Naive)** | Arsitektur sederhana, biaya infrastruktur rendah. | *Low precision* pada kode/entitas unik, *vocabulary mismatch*. | Dasar (~20-50ms) | Jangan gunakan untuk sistem legal, finansial, medis. |
| **Hybrid (Dense + BM25 via RRF)** | Menangkap intensi semantik sekaligus ketepatan leksikal absolut. | Memerlukan sinkronisasi state data antara Vector DB dan Text Search Engine. | +30 - 70ms | Jalankan kueri dense & sparse secara paralel via `asyncio.gather`. |
| **Cross-Encoder Reranking** | Mengeliminasi false positive secara drastis melalui interaksi *cross-attention*. | Membutuhkan inferensi komputasi berat (GPU), batas throughput terbatas. | +100 - 300ms | Batasi kandidat reranker maksimal 20–40 chunks; gunakan FP16/INT8 TensorRT. |
| **HyDE (Hypothetical Doc)** | Menjembatani kesenjangan semantik kueri pendek terhadap korpus panjang. | Menambah panggilan LLM di awal pencarian; risiko halusinasi kueri awal. | +400 - 1200ms | Gunakan LLM ultra-cepat terspesialisasi (e.g., Haiku/4o-mini) dengan max token $\le 100$. |
| **Parent-Child Retrieval** | Menghindari kehilangan konteks naratif tanpa mengorbankan granularitas embedding. | Konsumsi memori penyimpanan membengkak ($2\times - 3\times$); token LLM membengkak. | +10 - 30ms | Terapkan token budget packing ketat dan kompresi konteks selektif. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan Fatal: Mengabaikan Asinkronitas pada Panggilan Eksternal
*   **Gejala:** Latensi melonjak hingga $> 3\text{ detik}$ ketika memproses kueri jamak.
*   **Akar Masalah:** Menjalankan eksekusi query transformasi, pencarian dense, dan sparse secara sekuensial (sinkron).
*   **Solusi:** Gunakan coroutine non-blocking (`async/await`) dengan batas waktu timeout eksplisit (`asyncio.wait_for`).

#### 2. Vector Index Drift & Dimensi Embeddings
*   **Gejala:** Similarity score anjlok drastis pasca-deployment rilis model baru.
*   **Akar Masalah:** Ingestion menggunakan model embedding versi X (misal: `text-embedding-3-small`, 1536 dim), namun query pipeline memakai versi Y atau tanpa normalisasi L2 pada ruang kosinus.
*   **Solusi:** Terapkan skema metadata embedding yang mencatat: `model_name`, `dimension`, dan `normalization_flag`. Tolak kueri jika model penanda kueri tidak sesuai dengan versi index metadata.

#### 3. RRF Weights Bias Dominasi Skor
*   **Gejala:** Hasil pencarian sparse (BM25) mendominasi seluruh kandidat top, atau sebaliknya hasil dense mengaburkan kecocokan kata kunci.
*   **Akar Masalah:** Memodifikasi konstanta penstabil $k$ tanpa kalibrasi dataset, atau menggabungkan skor mentah langsung tanpa standardisasi peringkat.
*   **Solusi:** Gunakan purely rank-based fusion (RRF murni). Jangan pernah menjumlahkan skor mentah kosinus ($0.0 - 1.0$) dengan BM25 ($0 - \infty$) secara langsung tanpa min-max scaling atau sigmoidal mapping.

#### 4. The "Lost in the Middle" Dilemma
*   **Gejala:** LLM mengabaikan informasi faktual krusial meskipun chunk yang memuat fakta tersebut berhasil diambil dan masuk ke dalam prompt.
*   **Akar Masalah:** Arsitektur transformer LLM cenderung memberikan perhatian (*attention weight*) lebih tinggi pada awal dan akhir jendela konteks (*primacy & recency bias*).
*   **Solusi:** Urutkan kembali hasil reranker akhir: letakkan ranking 1 di paling awal konteks, ranking 2 di paling akhir konteks, dan ranking 3-5 di bagian tengah (*re-ordering pattern*).

---

### 11. Best Practices (Production Checklist)

| Kategori | Item Checklist | Status Kesiapan Produksi |
| :--- | :--- | :--- |
| **Ingestion** | Metadata wajib (`document_id`, `parent_id`, `created_at`, `access_roles`) terindeks. | [ ] |
| **Ingestion** | Chunk boundary tidak memotong kalimat di tengah (*sentence-boundary aware*). | [ ] |
| **Ingestion** | Teks tabel dikonversi ke representasi struktural (Markdown table / JSON). | [ ] |
| **Retrieval** | Panggilan Vector Store dan Sparse Search dijalankan concurrently via `asyncio`. | [ ] |
| **Retrieval** | Parameter timeout retrieval didefinisikan secara tegas (misal: max 250ms). | [ ] |
| **Retrieval** | Fallback engine disiapkan jika GPU reranker gagal (fallback ke RRF ranking). | [ ] |
| **Post-Retrieval**| Konteks teks melewati deduplikasi string berbasis hashing sebelum inject prompt. | [ ] |
| **Post-Retrieval**| Re-ordering diterapkan untuk memitigasi anomali *Lost-in-the-Middle*. | [ ] |
| **Security** | Pre-filtering metadata disematkan di query level untuk isolasi data tenant (RBAC). | [ ] |
| **Monitoring** | Telemetri OpenTelemetry melacak latensi setiap stage: `retrieve`, `rerank`, `generate`. | [ ] |

---

### 12. Hands-on Practice

Buatlah direktori lokal pada workspace Anda: `hands-on/m02/`. Praktikum ini memandu implementasi pipeline hybrid retrieval kustom dengan parent-child document resolver.

#### Struktur Direktori
```text
hands-on/m02/
├── requirements.txt
├── config.py
├── data_loader.py
├── hybrid_retriever.py
└── test_pipeline.py
```

#### Langkah 1: Siapkan Lingkungan Eksekusi (`requirements.txt`)
```text
pydantic>=2.6.0
numpy>=1.24.0
rank-bm25>=0.2.2
sentence-transformers>=2.5.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```
*Instalasi via terminal:* `pip install -r hands-on/m02/requirements.txt`

#### Langkah 2: Buat Modul Data Model & Mock Engine (`hybrid_retriever.py`)
Implementasikan logika hierarki parent-child dan RRF seperti yang dipelajari pada Bagian 7.

#### Langkah 3: Tulis Unit & Integration Test (`test_pipeline.py`)
```python
import pytest
from hybrid_retriever import (
    ProductionRAGRetriever,
    MockVectorStore,
    MockBM25Engine,
    MockCrossEncoderReranker,
    MockDocumentStore
)

@pytest.mark.asyncio
async def test_rag_pipeline_execution():
    retriever = ProductionRAGRetriever(
        vector_store=MockVectorStore(),
        bm25_engine=MockBM25Engine(),
        reranker=MockCrossEncoderReranker(),
        doc_store=MockDocumentStore()
    )
    
    query = "KPMM rasio modal inti"
    dummy_vec = [0.1] * 1536
    results = await retriever.retrieve(query, dummy_vec, final_top_k=1)

    assert len(results) == 1
    assert "p_0" in results[0].parent_id
    assert "12%" in results[0].content
    assert results[0].relevance_score > 0.8
```

#### Langkah 4: Eksekusi Pengujian
Jalankan verifikasi menggunakan pytest:
```bash
pytest hands-on/m02/test_pipeline.py -v
```

---

### 13. Exercises

#### Level Easy
Ubah fungsi `reciprocal_rank_fusion` pada Bagian 7 agar menerima bobot kustom (*weighted RRF*) antara dense dan sparse:
$$\text{Score} = w_{dense} \cdot \frac{1}{k + r_d} + w_{sparse} \cdot \frac{1}{k + r_s}$$
*Kriteria evaluasi:* Fungsi menerima tuple list dan bobot float, menghasilkan urutan yang sensitif terhadap pergeseran bobot $w_{dense} = 0.8$ vs $w_{sparse} = 0.2$.

#### Level Medium
Implementasikan fungsi *Context Re-ordering* ("Lost-in-the-Middle" mitigator). Fungsi menerima list `[Doc1, Doc2, Doc3, Doc4, Doc5]` yang telah diurutkan berdasarkan reranker (Doc1 terbaik). Fungsi harus memformat ulang list menjadi:
`[Doc1, Doc3, Doc5, Doc4, Doc2]` (Peringkat tertinggi berada di kedua ujung string).
*Kriteria evaluasi:* Urutan diverifikasi secara deterministik pada unit test dengan panjang input ganjil maupun genap.

#### Level Hard
Rancang kelas `DynamicSemanticChunker` yang memproses teks panjang secara streaming. Algoritma harus:
1. Memecah dokumen menjadi unit kalimat tunggal.
2. Menghitung embedding setiap kalimat.
3. Menghitung *cosine distance* antar pasangan kalimat berurutan $(S_i, S_{i+1})$.
4. Menghitung nilai ambang batas dinamis berdasarkan: $\text{Threshold} = \mu_{dist} + 1.5 \cdot \sigma_{dist}$.
5. Mengelompokkan kalimat ke dalam satu chunk sampai terjadi *spike distance* yang melampaui *threshold*.
*Kriteria evaluasi:* Kode mengeksekusi komputasi matriks NumPy secara tervektorisasi (*vectorized operations*) tanpa nested for-loops lambat.

---

### 14. Challenge

**Skenario Kasus Kompleks:**
Anda adalah Principal AI Architect pada platform SaaS Multi-tenant Healthcare. Korpus memuat 50 juta rekam medis elektronik (EMR) dan jurnal biomedis. Sistem harus memproses kueri dokter seperti:
*"Pasien berusia 45 tahun resisten obat lini pertama tuberkulosis dengan riwayat aritmia, apa protokol kombinasi alternatif menurut panduan WHO terbaru?"*

**Spesifikasi Tantangan & Batasan:**
1. **Zero Data Leakage:** Tenant isolation harus zero-trust. Dokter dari RS 'Alpha' tidak boleh mengambil EMR dari RS 'Beta', namun keduanya diizinkan mengakses literatur medis publik global secara simultan dalam 1 kueri.
2. **Kueri Multitasking:** Kueri memuat dua komponen kebutuhan sekaligus:
   - Data spesifik pasien (EMR semi-terstruktur, tabel lab).
   - Pedoman klinis WHO (Unstructured text korpus umum).
3. **SLA Ekstrem:** Latensi end-to-end total (termasuk generasi LLM) wajib $\le 1.2\text{ detik}$ pada kondisi beban $500\text{ QPS}$.

**Tugas Anda:**
Rancang dokumen arsitektur komprehensif (spesifikasi komponen, alur query-routing, strategi partisi data vektor, skema hybrid index, arsitektur reranker caching, dan mekanisme guardrails evaluasi klinis). *Selesaikan tanpa menggunakan kerangka kerja otomasi instan (seperti Naive LangChain Wrapper).*

---

### 15. Quiz Evaluasi Pemahaman

#### Sesi 1: Basic (5 Pertanyaan)
1. **Apa perbedaan mendasar antara representasi Bi-Encoder dan Cross-Encoder?**
   - *Jawaban:* Bi-encoder memproses kueri dan dokumen secara terpisah menghasilkan vektor statis yang dibandingkan via dot-product (cepat, cocok untuk candidate retrieval). Cross-encoder memproses kueri dan dokumen secara bersamaan di dalam transformer layer dengan *full cross-attention* antar-token (akurat, komputasi berat, cocok untuk re-ranking).
2. **Mengapa algoritma BM25 tetap relevan dan dibutuhkan dalam sistem RAG modern yang sudah memiliki dense vector retrieval?**
   - *Jawaban:* BM25 bekerja secara leksikal berbasis *exact match* frekuensi kata (TF-IDF varian). Pendekatan ini unggul dalam menangani kueri yang memuat kata kunci berkardinalitas tinggi, istilah langka, kode serial, atau nama orang/obat yang sering terabaikan oleh representasi semantik dense embeddings (*out-of-vocabulary* atau tertelan dalam *mean pooling*).
3. **Apa tujuan dari teknik Parent-Child (Hierarchical) Document Retrieval?**
   - *Jawaban:* Memisahkan unit teks yang diindeks untuk pencarian (*child chunk* kecil yang tajam secara semantik) dari unit teks yang disediakan ke LLM sebagai konteks pembuat keputusan (*parent chunk* besar yang mempertahankan konteks dan alur narasi dokumen).
4. **Apa yang dimaksud dengan konstanta $k$ pada algoritma Reciprocal Rank Fusion (RRF)?**
   - *Jawaban:* Parameter perata (*smoothing factor*) untuk mencegah dokumen yang menempati peringkat teratas pada satu sistem retrieval mendominasi total skor secara mutlak dibandingkan dokumen yang muncul konsisten di papan tengah pada berbagai sistem retrieval.
5. **Mengapa *Naive Fixed-Size Chunking* dapat merusak kualitas generasi LLM?**
   - *Jawaban:* Karena pemotongan teks secara kaku berbasis hitungan karakter/token sering memotong kalimat atau paragraf di tengah argumen penting (*boundary truncation*), menghilangkan hubungan anafora (pronomina rujukan), dan mencampuradukkan topik yang berbeda dalam satu chunk.

#### Sesi 2: Intermediate (5 Pertanyaan)
6. **Bagaimana mekanisme kerja Hypothetical Document Embeddings (HyDE) meningkatkan recall dokumen relevan?**
   - *Jawaban:* HyDE menggunakan LLM untuk membuat draft jawaban hipotetis atas kueri. Vektor embedding dokumen hipotetis ini terletak di manifold ruang dokumen (*document space*), bukan ruang kueri (*query space*). Jarak kosinus antara dua dokumen substantif jauh lebih dekat dibandingkan jarak antara kueri pendek deklaratif dengan dokumen substantif.
7. **Kapan teknik Dynamic Context Trimming harus diprioritaskan sebelum tahap prompt injection?**
   - *Jawaban:* Ketika biaya token LLM tinggi, batas konteks terbatas, atau rasio *signal-to-noise* menurun akibat chunk reranker teratas memuat token boilerplate (seperti disclaimer hukum, format footer/header berulang, atau navigasi HTML).
8. **Jelaskan fenomena *Lost-in-the-Middle* pada Large Language Model.**
   - *Jawaban:* Fenomena di mana LLM memiliki recall performa tinggi terhadap informasi yang diletakkan pada awal (*primacy bias*) dan akhir (*recency bias*) dari context window yang panjang, namun kemampuan retrieval atensinya anjlok signifikan terhadap fakta yang terpendam di tengah jendela konteks.
9. **Apa peran *Metadata Hard-Filtering* dan kapan tahap ini harus dieksekusi dalam database vektor?**
   - *Jawaban:* Membatasi ruang pencarian secara mutlak berdasarkan atribut terstruktur (seperti `tenant_id`, `created_year`, atau `access_tier`). Harus dieksekusi secara *pre-filtering* (sebelum penelusuran HNSW dimulai) untuk mencegah kebocoran data (*data leakage*) dan menghindari terbuangnya kuota Top-K oleh dokumen yang tidak diizinkan diakses.
10. **Bagaimana metrik *Context Precision* dan *Context Recall* dihitung dalam framework evaluasi Ragas?**
    - *Jawaban:* *Context Precision* mengukur apakah chunk yang relevan terhadap ground truth diletakkan pada urutan atas retrieval ranking. *Context Recall* mengukur apakah seluruh informasi faktual yang dibutuhkan untuk menjawab kueri berhasil diambil secara lengkap dari korpus rujukan.

#### Sesi 3: Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1:**
    *Kasus:* Sistem RAG e-commerce Anda memiliki indeks 5 juta katalog produk. Kueri pengguna: *"Baut baja tahan karat M4 panjang 20mm"*. Pencarian dense vector mengembalikan *"Baut kuningan M5 panjang 20mm"* pada peringkat 1 karena kedekatan embedding material baut.
    *Pertanyaan:* Perubahan arsitektur apa yang paling mendesak dan bagaimana konfigurasinya?
    *Solusi:* Terapkan arsitektur **Hybrid Search dengan Hard/Lexical Filtering**.
    - Indeks token spesifikasi `"M4"`, `"baja tahan karat"`, dan `"20mm"` ke dalam sparse index (BM25) atau ekstrak entitas via NER regex menjadi metadata terstruktur (`material: stainless_steel`, `thread_size: M4`, `length_mm: 20`).
    - Jalankan kueri hybrid dengan bobot sparse dinaikkan ($w_{sparse} \ge 0.6$) untuk kueri berkategori suku cadang, atau terapkan *payload filter* ketat pada atribut dimensi fisik sebelum melakukan similarity dense search.

12. **Skenario 2:**
    *Kasus:* Pada beban puncak, pod CPU yang menjalankan Cross-Encoder Reranker (`bge-reranker-large`) mengalami OOM (Out Of Memory) dan latensi retrieval melonjak dari $200\text{ ms}$ menjadi $4.500\text{ ms}$.
    *Pertanyaan:* Langkah mitigasi apa yang wajib diimplementasikan pada layer arsitektur dan sistem inferensi?
    *Solusi:*
    1. *Model Quantization & Acceleration:* Konversi model reranker ke format ONNX Runtime atau TensorRT dengan presisi FP16/INT8, dijalankan pada GPU terdedikasi atau node komputasi dengan dynamic batching.
    2. *Candidate Pruning:* Pangkas jumlah input reranker dari top-50 ke top-15 kandidat terbaik hasil RRF.
    3. *Circuit Breaker & Fallback Strategy:* Pasang circuit breaker; jika latensi reranker melampaui $150\text{ ms}$ atau queue pod penuh, fallback secara otomatis ke urutan skor mentah RRF tanpa reranker guna mempertahankan SLA.

13. **Skenario 3:**
    *Kasus:* Evaluasi performa Ragas pada sistem asisten medis korporat menunjukkan skor *Faithfulness* turun ke 0.65, sementara *Context Recall* berada di level 0.96.
    *Pertanyaan:* Analisis letak kegagalan sistem dan langkah perbaikannya.
    *Solusi:*
    - *Analisis:* Tingginya *Context Recall* (0.96) membuktikan layer retrieval bekerja optimal menangkap seluruh konteks faktual yang dibutuhkan. Namun, rendahnya *Faithfulness* (0.65) mengindikasikan bahwa LLM melakukan halusinasi atau menggenerasi pernyataan yang tidak berdasar pada konteks yang diinjeksikan.
    - *Solusi Perbaikan:* Perbaiki *Context Post-Processing* dan *Generation Layer*:
      1. Terapkan prompt instruction bertingkat dengan aturan *negative constraint*: *"Jawab HANYA berdasarkan konteks terlampir. Jika informasi tidak eksplisit ada di dalam teks rujukan, nyatakan secara tegas bahwa data tidak tersedia."*
      2. Turunkan parameter `temperature` LLM ke 0.0 (deterministik).
      3. Implementasikan self-consistency check atau verifikasi klaim sitasi otomatis pasca-generasi sebelum jawaban dikembalikan ke pengguna.

---

### 16. Summary

1. **Evolusi Arsitektur:** Produksi enterprise menuntut transisi dari *Naive RAG* menuju *Advanced Multi-Stage RAG* untuk menjamin akurasi faktual, keterlacakan sitasi, dan ketahanan terhadap data korporat yang kompleks.
2. **Kekuatan Hybrid Search:** Menggabungkan *Dense Vector Search* (pemahaman semantik/konseptual) dengan *Sparse Lexical Search* (BM25 untuk spesifikasi, nama unik, dan simbol kaku) melalui *Reciprocal Rank Fusion* (RRF) memberikan pondasi recall yang tangguh.
3. **Cross-Encoder sebagai Penentu Mutu:** Re-ranking menggunakan *Cross-Encoder* menjembatani kelemahan komparasi embedding bi-encoder terpisah dengan menjalankan interaksi *cross-attention* penuh antara token kueri dan token dokumen, meningkatkan *Context Precision* secara drastis.
4. **Hierarki Konteks:** Teknik *Parent-Child Indexing* memecahkan dilema mendasar retrieval: chunk kecil optimal untuk presisi pencarian vektor, sedangkan chunk besar krusial untuk pemahaman konteks nalar bagi Large Language Model.
5. **Observabilitas Berbasis Metrik:** Pengujian sistem enterprise RAG beralih dari intuisi kualitatif subjektif ke metrik terukur berkelanjutan melalui metrik framework Ragas (*Faithfulness*, *Relevance*, *Precision*, *Recall*).