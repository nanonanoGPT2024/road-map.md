# Bab 04: Production Retrieval-Augmented Generation
## Modul 01: Arsitektur Hybrid Dense-Sparse Retrieval, Contextual Chunking, dan Cross-Encoder Reranking

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Memilih Strategi Chunking Dokumen:** Mengimplementasikan *recursive token-aware splitting* dan *contextual metadata enrichment* untuk mempertahankan batasan semantik dokumen enterprise.
- **Membangun Pipeline Hybrid Search Multi-Modalitas:** Mengintegrasikan representasi leksikal *sparse* (BM25) dan semantik *dense* (HNSW dengan Cosine Similarity) dalam satu antarmuka retrieval paralel.
- **Mengimplementasikan Algoritma Reciprocal Rank Fusion (RRF):** Menggabungkan peringkat multi-retrieval secara deterministik tanpa terdistorsi oleh perbedaan skala skor probabilitas embedding dan leksikal.
- **Mengintegrasikan Deep Cross-Encoder Reranker:** Mereduksi *noise* dan mengeliminasi *false positives* dari kandidat retrieval tingkat pertama (Top-K) dengan *bounded latency budget* (P95 < 150ms).
- **Membangun Error Recovery dan Fallback:** Menjamin keandalan sistem RAG production-ready menggunakan skema *circuit breaker*, validasi *groundedness*, dan deteksi *zero-hit fallback*.

---

### 2. Concept Overview

Aplikasi Retrieval-Augmented Generation (RAG) tingkat enterprise tidak dapat mengandalkan *Naive RAG*—arsitektur dasar yang hanya memecah teks berdasarkan panjang karakter tetap, meng-generate vector embedding satu arah, dan langsung menyuntikkan dokumen terdekat ke konteks Large Language Model (LLM). Pola ini rentan terhadap degradasi performa (*lost-in-the-middle*, *semantic drift*, dan halusinasi akibat data yang tidak relevan).

```
[Naive RAG]
Dokumen -> Fixed-size Chunk -> Single Dense Index -> Top-K -> LLM (High Hallucination)

[Production RAG]
Dokumen -> Contextual Chunking -> Dual Ingestion (Dense & Sparse)
                                           │
Query ──┬──> Sparse Engine (BM25) ────────┤ Parallel
        └──> Dense Engine (Vector HNSW) ──┘ Fetch
                        │
                        ▼
            Reciprocal Rank Fusion (RRF)
                        │
                        ▼ Top-N (High Recall)
            Cross-Encoder Reranker
                        │
                        ▼ Top-K (High Precision)
            Context Compression & Grounding Guard -> LLM
```

Mental model dari Production RAG berpusat pada **Two-Stage Retrieval Funnel**:
1. **Stage 1: High Recall Retrieval (Kombinasi Dense + Sparse)**
   - *Sparse Search (BM25):* Menangkap kecocokan kata kunci eksak, istilah teknis, serial number, kode produk, atau akronim khusus yang sering gagal dipahami oleh embedding models.
   - *Dense Search (Bi-Encoder Embeddings):* Menangkap makna konseptual, parafrase, dan korelasi semantik lintas sinonim.
2. **Stage 2: High Precision Scoring (Cross-Encoder Reranking)**
   - Bi-encoder memproses kueri dan dokumen secara terpisah untuk menghasilkan vektor (hemat komputasi saat pencarian awal).
   - Cross-encoder memproses pasangan `(Kueri, Dokumen)` secara simultan melalui mekanisme *cross-attention penuh*, memungkinkan model menangkap dependensi token yang halus dengan akurasi relevansi yang jauh lebih tinggi sebelum konteks dimasukkan ke LLM.

---

### 3. Why It Matters

Dalam implementasi skala enterprise (seperti *legal contract analysis*, *clinical decision support*, dan *financial auditing*), kegagalan sistem retrieval berdampak fatal:
- **Isolasi Terminologi Eksak:** Dense vector retriever sering kali menempatkan `Error Code: ERR-502` dekat dengan `Error Code: ERR-504` karena kedekatan semantik kalimatnya, padahal kedua kode membutuhkan prosedur penanganan yang berbeda. BM25 mengatasi masalah ini dengan pembobotan *Inverse Document Frequency* (IDF) tinggi pada token unik.
- **Keterbatasan Context Window dan Noise Inflation:** Menyuntikkan seluruh chunk yang salah atau berulang ke dalam context window model bahasa berparameter besar tidak hanya membengkakkan biaya token (API expense), tetapi juga secara signifikan meningkatkan risiko halusinasi akibat fenomena *Lost-in-the-Middle*.
- **Data Distribution Shift:** Domain internal perusahaan memiliki jargon dan bahasa internal yang tidak terdistribusi secara normal pada dataset pre-training embedding publik. Kombinasi hybrid search dan dynamic reranking menjembatani kesenjangan ini tanpa perlu melakukan fine-tuning model embedding sejak hari pertama.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur ingestion dokumen dan siklus retrieval produksi:

```
[ INGESTION PIPELINE ]
      │
      ▼
Raw Documents (PDF, MD, HTML)
      │
      ▼
Structural & Semantic Chunking ───> Metadata Enrichment (Document ID, Timestamp, ACLs)
      │
      ├──────────────────────────────────────────┐
      ▼                                          ▼
Sparse Inverted Index (BM25)            Dense Vector Store (HNSW Index)
(Lucene / In-Memory BM25)               (Qdrant / Milvus / pgvector)

─────────────────────────────────────────────────────────────────────────────

[ QUERY & RETRIEVAL PIPELINE ]
      │
User Query
      │
      ├──────────────────────────────────────────┐
      ▼                                          ▼
Sparse Retrieval (Top-50)               Dense Retrieval (Top-50)
Tokens / Keywords                       Dense Vector Representation
      │                                          │
      └────────────────────┬─────────────────────┘
                           │
                           ▼
              Reciprocal Rank Fusion (RRF)
              Score = Σ (1 / (k + rank))
                           │
                           ▼
                  Top-20 Merged Chunks
                           │
                           ▼
               Cross-Encoder Reranker
               Attention(Query <-> Chunk)
                           │
                           ▼
                  Top-5 Reranked Chunks
                           │
                           ▼
              Context Formatter & Truncator
                           │
                           ▼
                      LLM Context
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Recursive Chunking & Semantic Boundary Preservation
Pemecahan teks sederhana berdasarkan `N` karakter merusak struktur tata bahasa. Recursive character chunking memproses hirarki pemisah teks secara berurutan:
1. Double line break (`\n\n`) -> Mempertahankan batas paragraf.
2. Single line break (`\n`) -> Mempertahankan batas baris/elemen daftar.
3. Whitespace (` `) -> Mempertahankan batas kata.

Setiap *chunk* diperkaya dengan metadata seperti referensi *parent document*, posisi relatif, dan ringkasan mini untuk menjaga konteks global dokumen lokal (*Contextual Document Chunking*).

#### B. Dense vs. Sparse Representation
- **Sparse Vector (BM25):** 
  $$IDF(q_i) = \ln \left( \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1 \right)$$
  $$Score(D, Q) = \sum_{i=1}^{N} IDF(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{avgdl}\right)}$$
  Sangat sensitif terhadap kecocokan leksikal langsung, tahan terhadap sinonim yang salah sasaran, dan deterministik.

- **Dense Vector:** Mengonversi teks menjadi representasi vektor berdimensi tinggi (misal: 768 atau 1536 dimensi). Mengukur kedekatan menggunakan *Cosine Distance*:
  $$\text{Cosine Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\|_2 \|\mathbf{B}\|_2}$$

#### C. Reciprocal Rank Fusion (RRF)
Menggabungkan skor dari dua sistem scoring yang berbeda (skor BM25 bernilai riil unbounded $\ge 0$, sedangkan Cosine bernilai rentang $[-1, 1]$) melalui normalisasi skala langsung sering kali menyebabkan bias pada sistem scoring tertentu. 

RRF memecahkan masalah ini dengan menggunakan ranking murni, bukan nilai absolut skor:
$$RRF(d \in D) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
Di mana:
- $M$ adalah himpunan sistem retrieval (Sparse, Dense).
- $r_m(d)$ adalah urutan ranking dokumen $d$ pada sistem retrieval $m$ (1-indexed).
- $k$ adalah konstanta perataan peringkat (standar industri: $k = 60$).

#### D. Cross-Encoder Reranking
Model Bi-Encoder mengevaluasi kesamaan sebagai dot product $\langle \mathbf{u}, \mathbf{v} \rangle$, tanpa interaksi langsung antar token query dan dokumen pada layer transformer. Sebaliknya, Cross-Encoder menerima token input dalam bentuk:
$$\text{[CLS]} \circ \text{Query} \circ \text{[SEP]} \circ \text{Dokumen} \circ \text{[SEP]}$$
Semua layer *self-attention* dapat mengevaluasi keterkaitan setiap token query terhadap setiap token dokumen secara menyeluruh. Hal ini membalikkan probabilitas relevansi dari perkiraan semantik kasar menjadi klasifikasi relevansi presisi tinggi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi pipeline Hybrid Search dan Reranking berstandar produksi menggunakan Python 3.11+. Sistem ini dibangun dengan arsitektur modular, *type safety* menggunakan Pydantic v2, konkurensi asynchronous, dan *graceful error handling*.

#### Struktur Dependency (`requirements.txt`):
```text
pydantic>=2.5.0
numpy>=1.26.0
sentence-transformers>=2.3.0
rank-bm25>=0.2.2
```

#### Implementasi Lengkap: `hybrid_retriever.py`

```python
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel, Field

# Setup logger produksi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s")
logger = logging.getLogger("ProductionRAG")


# =====================================================================
# Domain Models & Schemas
# =====================================================================

class Document(BaseModel):
    """Representasi dokumen mentah sebelum dipecah menjadi chunks."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Representasi segmen dokumen yang diindeks ke retrieval store."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    text: str
    chunk_index: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None


class RetrievalResult(BaseModel):
    """Objek hasil pencarian seragam untuk sparse, dense, dan hybrid."""
    chunk: Chunk
    score: float
    retrieval_method: str


# =====================================================================
# Custom Exceptions
# =====================================================================

class RAGPipelineException(Exception):
    """Base exception untuk kegagalan pipeline retrieval."""
    pass


class VectorIndexError(RAGPipelineException):
    """Kegagalan operasi internal vector store."""
    pass


class IngestionError(RAGPipelineException):
    """Kegagalan proses parsing dan ingest data."""
    pass


# =====================================================================
# Text Processing & Chunking
# =====================================================================

class RecursiveTokenChunker:
    """
    Chunker deterministik yang menghormati batasan semantik dokumen
    menggunakan hirarki pemisah teks secara berulang.
    """
    def __init__(self, target_chunk_size: int = 500, overlap_size: int = 50):
        if overlap_size >= target_chunk_size:
            raise ValueError("overlap_size harus lebih kecil dari target_chunk_size.")
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size
        self.separators = ["\n\n", "\n", ". ", " "]

    def split_document(self, document: Document) -> List[Chunk]:
        raw_text = document.content.strip()
        if not raw_text:
            return []

        chunks_text = self._recursive_split(raw_text, self.separators)
        
        # Penggabungan dengan overlap
        final_chunks: List[Chunk] = []
        for idx, text in enumerate(chunks_text):
            chunk = Chunk(
                document_id=document.id,
                text=text,
                chunk_index=idx,
                metadata={
                    **document.metadata,
                    "char_length": len(text),
                    "total_splits": len(chunks_text),
                }
            )
            final_chunks.append(chunk)

        return final_chunks

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.target_chunk_size:
            return [text]

        if not separators:
            # Fallback hard cut jika tidak ada separator yang tersisa
            return [text[i:i + self.target_chunk_size] for i in range(0, len(text), self.target_chunk_size - self.overlap_size)]

        sep = separators[0]
        splits = text.split(sep)
        result: List[str] = []
        current_buffer = ""

        for part in splits:
            candidate = current_buffer + (sep if current_buffer else "") + part
            if len(candidate) <= self.target_chunk_size:
                current_buffer = candidate
            else:
                if current_buffer:
                    result.append(current_buffer)
                
                if len(part) > self.target_chunk_size:
                    # Recursive split menggunakan separator yang lebih granular
                    sub_splits = self._recursive_split(part, separators[1:])
                    result.extend(sub_splits)
                    current_buffer = ""
                else:
                    current_buffer = part

        if current_buffer:
            result.append(current_buffer)

        return result


# =====================================================================
# Dense Retrieval System
# =====================================================================

class DenseVectorStore:
    """
    Vector engine sederhana berkemampuan Cosine Similarity 
    dengan representasi NumPy yang thread-safe.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.chunks: List[Chunk] = []
        self.matrix: Optional[np.ndarray] = None
        self._lock = asyncio.Lock()

    async def add_chunks(self, chunks: Sequence[Chunk]) -> None:
        async with self._lock:
            valid_chunks = [c for c in chunks if c.embedding is not None]
            if not valid_chunks:
                logger.warning("Tidak ada chunk dengan embedding valid untuk ditambahkan.")
                return

            new_vectors = np.array([c.embedding for c in valid_chunks], dtype=np.float32)
            
            # Normalisasi L2 untuk standardisasi perhitungan Cosine Distance
            norms = np.linalg.norm(new_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normalized_vectors = new_vectors / norms

            if self.matrix is None:
                self.matrix = normalized_vectors
            else:
                self.matrix = np.vstack([self.matrix, normalized_vectors])

            self.chunks.extend(valid_chunks)
            logger.info(f"Berhasil mengindeks {len(valid_chunks)} vektor ke Dense Index.")

    async def search(self, query_vector: List[float], top_k: int = 10) -> List[RetrievalResult]:
        async with self._lock:
            if self.matrix is None or len(self.chunks) == 0:
                return []

            q_vec = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)
            if q_norm == 0:
                return []
            q_vec = q_vec / q_norm

            # Dot product dari unit vectors setara dengan Cosine Similarity
            scores = np.dot(self.matrix, q_vec)
            top_k_indices = np.argsort(scores)[::-1][:top_k]

            results = [
                RetrievalResult(
                    chunk=self.chunks[idx],
                    score=float(scores[idx]),
                    retrieval_method="dense"
                )
                for idx in top_k_indices
            ]
            return results


# =====================================================================
# Sparse Retrieval System (BM25 In-Memory)
# =====================================================================

class SparseBM25Store:
    """Implementasi BM25 Okapi deterministik."""
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[Chunk] = []
        self.doc_len: List[int] = []
        self.avg_doc_len: float = 0.0
        self.idf: Dict[str, float] = {}
        self.doc_freqs: List[Dict[str, int]] = []
        self._lock = asyncio.Lock()

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().replace(".", " ").replace(",", " ").split()

    async def add_chunks(self, chunks: Sequence[Chunk]) -> None:
        async with self._lock:
            self.chunks.extend(chunks)
            for chunk in chunks:
                tokens = self._tokenize(chunk.text)
                self.doc_len.append(len(tokens))
                freqs: Dict[str, int] = {}
                for t in tokens:
                    freqs[t] = freqs.get(t, 0) + 1
                self.doc_freqs.append(freqs)

            total_docs = len(self.chunks)
            self.avg_doc_len = sum(self.doc_len) / total_docs if total_docs > 0 else 0.0

            # Recompute IDF
            df: Dict[str, int] = {}
            for freqs in self.doc_freqs:
                for term in freqs.keys():
                    df[term] = df.get(term, 0) + 1

            self.idf = {
                term: math.log((total_docs - count + 0.5) / (count + 0.5) + 1.0)
                for term, count in df.items()
            }
            logger.info(f"Berhasil mengindeks {len(chunks)} chunk ke Sparse BM25 Index.")

    async def search(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        async with self._lock:
            if not self.chunks:
                return []

            query_tokens = self._tokenize(query)
            scores = np.zeros(len(self.chunks), dtype=np.float32)

            for idx, freqs in enumerate(self.doc_freqs):
                cur_len = self.doc_len[idx]
                score = 0.0
                for token in query_tokens:
                    if token not in freqs:
                        continue
                    tf = freqs[token]
                    idf = self.idf.get(token, 0.0)
                    numerator = idf * tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (cur_len / self.avg_doc_len))
                    score += numerator / denominator
                scores[idx] = score

            top_k_indices = np.argsort(scores)[::-1][:top_k]

            results = [
                RetrievalResult(
                    chunk=self.chunks[idx],
                    score=float(scores[idx]),
                    retrieval_method="sparse"
                )
                for idx in top_k_indices if scores[idx] > 0.0
            ]
            return results


# =====================================================================
# Reranking & Fusion Mechanisms
# =====================================================================

class CrossEncoderReranker:
    """
    Reranker layer menggunakan deep learning Cross-Encoder.
    Menggunakan mock inference untuk menjaga portabilitas kode eksekusi
    sambil merefleksikan interface 'sentence_transformers.CrossEncoder'.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        logger.info(f"Inisialisasi Cross-Encoder model: {model_name}")

    def rerank(self, query: str, results: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        if not results:
            return []

        # Simulasi/Fallback Skoring Cross-Attention Interaktif:
        # Pada sistem live: score_inputs = [[query, res.chunk.text] for res in results]
        # raw_scores = self.model.predict(score_inputs)
        reranked_results: List[Tuple[RetrievalResult, float]] = []

        q_terms = set(query.lower().split())
        for res in results:
            doc_terms = set(res.chunk.text.lower().split())
            intersection = q_terms.intersection(doc_terms)
            
            # Hitung mock deep cross-attention: kombinasi lexical overlap & dense priority
            lexical_bonus = len(intersection) / (len(q_terms) + 1e-5)
            cross_score = (res.score * 0.4) + (lexical_bonus * 0.6)
            
            updated_res = RetrievalResult(
                chunk=res.chunk,
                score=cross_score,
                retrieval_method="cross_encoder_reranked"
            )
            reranked_results.append((updated_res, cross_score))

        # Sort descending berdasarkan skor Cross-Encoder
        reranked_results.sort(key=lambda x: x[1], reverse=True)
        return [item[0] for item in reranked_results[:top_k]]


class HybridRetrieverEngine:
    """
    Orchestrator Hybrid Retrieval: Dense + Sparse + Reciprocal Rank Fusion + Reranking.
    """
    def __init__(
        self,
        dense_store: DenseVectorStore,
        sparse_store: SparseBM25Store,
        reranker: CrossEncoderReranker,
        rrf_constant: int = 60
    ):
        self.dense_store = dense_store
        self.sparse_store = sparse_store
        self.reranker = reranker
        self.k = rrf_constant

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[RetrievalResult],
        sparse_results: List[RetrievalResult],
        fusion_top_n: int = 20
    ) -> List[RetrievalResult]:
        """Menghitung agregasi peringkat non-parametrik (RRF)."""
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, Chunk] = {}

        # Akumulasi Dense Ranks
        for rank, res in enumerate(dense_results, start=1):
            c_id = res.chunk.id
            chunk_map[c_id] = res.chunk
            rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (self.k + rank))

        # Akumulasi Sparse Ranks
        for rank, res in enumerate(sparse_results, start=1):
            c_id = res.chunk.id
            chunk_map[c_id] = res.chunk
            rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + (1.0 / (self.k + rank))

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:fusion_top_n]

        return [
            RetrievalResult(
                chunk=chunk_map[c_id],
                score=score,
                retrieval_method="hybrid_rrf"
            )
            for c_id, score in sorted_items
        ]

    async def execute_retrieval(
        self,
        query: str,
        query_vector: List[float],
        top_k: int = 5,
        candidate_pool_size: int = 20
    ) -> List[RetrievalResult]:
        """
        Mengeksekusi pipeline hybrid retrieval paralel secara end-to-end.
        """
        try:
            # Eksekusi paralel dense & sparse retrieval menggunakan gather
            dense_task = self.dense_store.search(query_vector, top_k=candidate_pool_size)
            sparse_task = self.sparse_store.search(query, top_k=candidate_pool_size)

            dense_res, sparse_res = await asyncio.gather(dense_task, sparse_task)

            # Stage 1: Reciprocal Rank Fusion
            fused_candidates = self._reciprocal_rank_fusion(
                dense_results=dense_res,
                sparse_results=sparse_res,
                fusion_top_n=candidate_pool_size
            )

            if not fused_candidates:
                logger.warning("Tidak ditemukan kandidat dokumen dari proses Hybrid Retrieval.")
                return []

            # Stage 2: Deep Cross-Encoder Reranking
            final_ranked = self.reranker.rerank(query, fused_candidates, top_k=top_k)
            return final_ranked

        except Exception as e:
            logger.error(f"Kegagalan kritis pada pipeline hybrid retrieval: {str(e)}", exc_info=True)
            raise RAGPipelineException(f"Pipeline failure: {str(e)}") from e


# =====================================================================
# Ingestion Pipeline Facade
# =====================================================================

class ProductionIngestionPipeline:
    """Mengelola intake dokumen, slicing, embedding extraction, dan dispatch indexing."""
    def __init__(
        self,
        chunker: RecursiveTokenChunker,
        dense_store: DenseVectorStore,
        sparse_store: SparseBM25Store
    ):
        self.chunker = chunker
        self.dense_store = dense_store
        self.sparse_store = sparse_store

    def _mock_embedding_service(self, text: str) -> List[float]:
        """Simulasi deterministik representasi embedding vector 384-dimensi."""
        hash_val = sum(ord(c) for c in text)
        np.random.seed(hash_val % (2**32))
        return np.random.normal(0, 1, 384).tolist()

    async def ingest_documents(self, documents: List[Document]) -> int:
        all_chunks: List[Chunk] = []

        for doc in documents:
            chunks = self.chunker.split_document(doc)
            for c in chunks:
                # Menghasilkan representasi dense vector per chunk
                c.embedding = self._mock_embedding_service(c.text)
                all_chunks.append(c)

        if not all_chunks:
            return 0

        # Ingest ke kedua backend engine secara asynchronous
        await asyncio.gather(
            self.dense_store.add_chunks(all_chunks),
            self.sparse_store.add_chunks(all_chunks)
        )

        return len(all_chunks)
```

---

### 7. Edge Cases & Failure Modes

Sistem RAG skala enterprise wajib mengantisipasi mode kegagalan sistematis berikut:

| Mode Kegagalan | Akar Masalah (*Root Cause*) | Dampak (*Impact*) | Strategi Mitigasi Produksi |
|---|---|---|---|
| **Zero Leksikal Match** | Kueri pengguna penuh sinonim murni atau bahasa kolokial. | BM25 mengembalikan array kosong ($0$ kandidat). | RRF secara otomatis mengandalkan ranking Dense Search tanpa merusak kalkulasi skor. |
| **Out-of-Vocabulary (OOV) / Rare ID Miss** | User mencari `CVE-2023-4863` atau SKU spesifik. | Dense retriever memetakan vektor ke entitas semantik acak terdekat (*hallucinated cluster*). | BM25 memberikan skor IDF masif pada token unik, memaksanya naik ke peringkat teratas RRF. |
| **High Latency Spike pada Reranker** | Cross-encoder memproses input yang terlalu panjang atau batch candidate terlalu besar (> 100). | P99 Latency membengkak melewati ambang batas SLA (> 1.5 detik). | Batasi jumlah kandidat fusion reranking maksimal $N=20$. Terapkan circuit-breaker timeout (misal: 100ms) untuk me-bypass reranker dan langsung menggunakan hasil RRF jika timeout. |
| **Semantic Bleed / Context Contamination** | Chunking memotong kalimat tepat di tengah klausa negasi (*"tidak disarankan"*). | Sistem menyajikan instruksi yang bertolak belakang dengan konteks asli dokumen induk. | Terapkan batas chunk berbasis separator bertingkat (`\n\n`, `\n`, `. `) dan simpan `window_metadata` untuk retrieval ekspansi konteks (*parent-document retrieval*). |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan arsitektur RAG menuntut kompromi antara latensi, biaya komputasi, dan akurasi retrieval:

```
[Komparasi Trade-Off Retrieval Architecture]

Kecepatan/Biaya Rendah <─────────────────────────────────> Akurasi Tinggi
Pure Sparse (BM25)       Dense Vector Only      Hybrid (RRF)      Hybrid + Cross-Encoder
(Latensi: ~5ms)          (Latensi: ~20ms)       (Latensi: ~35ms)  (Latensi: ~120ms)
(Recall Lemah)           (Miss Akronim/Kode)    (High Recall)     (State-of-the-Art Precision)
```

#### Komparasi Arsitektural:
1. **Bi-Encoder Reranking vs. Cross-Encoder Reranking:**
   - *Bi-Encoder:* Cepat (dapat di-cache), tetapi akurasi pemeringkatan akhir setara dengan dense search standar.
   - *Cross-Encoder:* Relatif lambat ($O(N)$ transformer inferencing), tetapi menghasilkan pemahaman semantik relasional kueri-dokumen terbaik.
2. **Dense RRF vs. Weighted Linear Score Combination:**
   - *Weighted Score Combination:* Memerlukan tuning konstan ($\alpha \cdot Dense + (1-\alpha) \cdot Sparse$) yang rapuh jika model embedding diubah.
   - *Reciprocal Rank Fusion (RRF):* Bebas normalisasi (*scale-agnostic*), stabil lintas domain tanpa kalibrasi parameter manual berulang.

---

### 9. Best Practices & Standar Industri

1. **Target Latency Budget (Enterprise Target):**
   - Total Target Retrieval SLA: **< 150ms** (P95).
   - Sparse Engine: $10 - 20\text{ms}$.
   - Dense Engine (Vector DB): $15 - 30\text{ms}$.
   - RRF Aggregation: $< 5\text{ms}$.
   - Cross-Encoder (Top-20 candidate): $60 - 90\text{ms}$.
2. **Chunk Size & Overlap Standards:**
   - Panjang chunk ideal: **256 - 512 token** (~1000 - 2000 karakter). Chunk di bawah 100 token kehilangan konteks; chunk di atas 1000 token mencairkan konsentrasi densitas vektor.
   - Overlap ideal: **10% - 15%** dari ukuran chunk untuk menghindari pemutusan konteks kalimat pada batas segmentasi.
3. **Metadata Filtering (Pre-filtering vs Post-filtering):**
   - Lakukan **Pre-Filtering** pada level Vector Database menggunakan metadata (Tenant ID, Role-Based Access Control / RBAC, Status Dokumen) sebelum perhitungan jarak vektor untuk menghindari kebocoran data (*data leakage*) dan menghemat komputasi similarity.
4. **Isolasi Kegagalan (Resilience Pattern):**
   - Jika embedding API downstream (misal: OpenAI text-embedding-3) mengalami outage atau *rate-limiting*, rancang sistem agar melakukan degradasi teratur (*graceful degradation*) menjadi **Sparse-Only Search**, alih-alih melempar status *Internal Server Error (500)* kepada pengguna akhir.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab:
Anda bertindak sebagai Principal AI Engineer di sebuah perusahaan enterprise. Sistem *knowledge base* teknis internal gagal menemukan solusi ketika staf IT mencari kode error sistem spesifik (`ERR-SEC-9021`) karena Naive Dense Retrieval justru mengembalikan dokumen troubleshooting umum mengenai koneksi jaringan. Anda diminta membuktikan keunggulan arsitektur **Hybrid Search + Cross-Encoder Reranking**.

#### Langkah-langkah Praktikum:

1. **Persiapan Lingkungan (Setup):**
   Simpan kode implementasi di atas ke dalam file bernama `production_rag_lab.py`.

2. **Eksekusi Skenario Uji:**
   Tambahkan script driver eksekusi berikut di bagian akhir file:

```python
async def run_enterprise_benchmark():
    print("=================================================================")
    print("   MEMULAI BENCHMARK: NAIVE RETRIEVAL VS PRODUCTION HYBRID RAG   ")
    print("=================================================================\n")

    # 1. Dataset Dokumen Korporat Sintetis
    test_docs = [
        Document(
            content=(
                "Prosedur Darurat Jaringan: Jika terjadi kegagalan gateway, "
                "lakukan restart switch inti dan flush DNS server internal."
            ),
            metadata={"source": "sop-network-restart", "category": "it-ops"}
        ),
        Document(
            content=(
                "Katalog Kode Error Keamanan: Kode ERR-SEC-9021 menunjukkan adanya token "
                "autentikasi kadaluarsa pada sesi microservice Identity. Solusi: Refresh OAuth Token."
            ),
            metadata={"source": "sec-manual-errors", "category": "security"}
        ),
        Document(
            content=(
                "Error otentikasi umum: Jika pengguna tidak bisa login, periksa "
                "apakah credential database aktif dan sinkronisasi LDAP berjalan."
            ),
            metadata={"source": "sop-identity-login", "category": "security"}
        ),
    ]

    # 2. Inisialisasi Sub-komponen
    chunker = RecursiveTokenChunker(target_chunk_size=200, overlap_size=20)
    dense_store = DenseVectorStore(dimension=384)
    sparse_store = SparseBM25Store()
    reranker = CrossEncoderReranker()

    ingestion = ProductionIngestionPipeline(
        chunker=chunker,
        dense_store=dense_store,
        sparse_store=sparse_store
    )

    # 3. Menjalankan Ingestion Pipeline
    print("[1] Memproses Ingestion Dokumen...")
    indexed_count = await ingestion.ingest_documents(test_docs)
    print(f" -> Sukses mengindeks {indexed_count} chunks ke Dual Storage Engine.\n")

    # 4. Kueri Spesifik Menguji Kemampuan Identifikasi Kode Eksak
    query = "Bagaimana menangani error ERR-SEC-9021 token autentikasi?"
    print(f"[2] Kueri Pencarian: '{query}'\n")

    # Simulasi Query Vector (Deterministic mock vector)
    query_vector = ingestion._mock_embedding_service(query)

    # 5. Uji Coba: Dense Retrieval Saja (Naive Pattern)
    print("--- [HASIL PURE DENSE RETRIEVAL (Top-2)] ---")
    naive_results = await dense_store.search(query_vector, top_k=2)
    for idx, res in enumerate(naive_results, 1):
        print(f"Peringkat {idx} (Score: {res.score:.4f}): {res.chunk.text}")

    print("\n--- [HASIL PRODUCTION HYBRID + RERANKING RETRIEVAL (Top-2)] ---")
    engine = HybridRetrieverEngine(
        dense_store=dense_store,
        sparse_store=sparse_store,
        reranker=reranker
    )
    
    hybrid_results = await engine.execute_retrieval(
        query=query,
        query_vector=query_vector,
        top_k=2
    )

    for idx, res in enumerate(hybrid_results, 1):
        print(f"Peringkat {idx} (Score: {res.score:.4f} | Method: {res.retrieval_method}):")
        print(f" Dokumen ID: {res.chunk.document_id}")
        print(f" Isi Teks   : {res.chunk.text}\n")


if __name__ == "__main__":
    asyncio.run(run_enterprise_benchmark())
```

3. **Jalankan Kode:**
   ```bash
   python production_rag_lab.py
   ```

4. **Validasi Kriteria Keberhasilan:**
   - Hasil eksekusi **Pure Dense Retrieval** menunjukkan kerentanan bias di mana dokumen umum otentikasi dapat mendominasi peringkat atas akibat keterbatasan representasi embedding terhadap kode acak.
   - Hasil eksekusi **Production Hybrid Retrieval Engine** berhasil menempatkan chunk yang secara spesifik memuat kode `ERR-SEC-9021` sebagai **Peringkat 1** secara mutlak berkat kontribusi leksikal BM25 yang diperkuat oleh verifikasi Cross-Encoder Reranker.