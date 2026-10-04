# Bab 08: Compound Inference Pipelines & Embeddings (Module 01)
**Track:** AI Data & Autonomous Agents — Inference Engineering  
**Level:** Advanced / Principal Engineer

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Merancang Arsitektur Compound Inference Systems**: Memisahkan monolit inferensi generatif menjadi pipeline modular berbasis *Directed Acyclic Graph* (DAG) yang mengintegrasikan *dense embeddings*, vector search, re-ranking, dan context injection dengan *strict latency budget* ($p99 \le 150\text{ ms}$).
2. **Mengoptimalkan Throughput Embedding Pipeline**: Mengimplementasikan teknik *dynamic micro-batching*, *asynchronous tokenization*, $L_2$ normalization, dan pooling (*mean/CLS*) pada level runtime untuk memitigasi *GPU underutilization*.
3. **Mengisolasi Komponen Kritis dengan Circuit Breaker & Fallback**: Membangun orkestrasi inferensi asinkron yang tahan terhadap *cascading failures* ketika downstream components (seperti Vector Database atau Re-ranker) mengalami degradasi performa.
4. **Menganalisis Trade-off Representasi Vektor**: Menentukan secara kuantitatif penggunaan *Bi-Encoder*, *Cross-Encoder*, dan *Late-Interaction Models* (ColBERT) berdasarkan batas compute, *memory footprint*, dan *Normalized Discounted Cumulative Gain* (NDCG@K).

---

## 2. Concept Overview

Dalam paradigma rekayasa inferensi modern, model generatif (LLM) tidak lagi dioperasikan secara monolitik. Mengandalkan single-pass LLM untuk tugas-tugas penalaran berbasis data real-time menimbulkan inefisiensi komputasi, risiko halusinasi yang tinggi, dan biaya token yang prohibitive. 

**Compound Inference System** adalah arsitektur di mana luaran sistem dibentuk oleh orkestrasi banyak komponen komputasi yang saling terhubung:

$$\text{Output} = \mathcal{G}\Big(\mathcal{R}\big(\mathcal{E}(q), \mathcal{D}\big), q\Big)$$

Di mana:
- $q$: Kueri inferensi mentah.
- $\mathcal{E}(q) \in \mathbb{R}^d$: Proyeksi kueri ke dalam manifold laten kontinu melalui model *embedding* (bi-encoder).
- $\mathcal{D}$: Korpus atau database vektor terindeks.
- $\mathcal{R}$: Operator perolehan dan re-ranking (menggabungkan k-Nearest Neighbors/HNSW dengan cross-encoder).
- $\mathcal{G}$: Model generatif (autoregresif) yang mensintesis konteks akhir.

```
                    ┌─────────────────────────┐
                    │  Raw User Query (q)     │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Embedding Engine E(q)   │  <-- Bi-Encoder (Latency: 5-15ms)
                    └────────────┬────────────┘
                                 │
                                 ▼ (Vector d-dim)
                    ┌─────────────────────────┐
                    │ Dense Retrieval (k-NN)  │  <-- Top-K Candidates (Latency: 5-20ms)
                    └────────────┬────────────┘
                                 │
                                 ▼ (Candidates: k=100)
                    ┌─────────────────────────┐
                    │ Cross-Encoder Re-ranker │  <-- Top-N Candidates (Latency: 20-50ms)
                    └────────────┬────────────┘
                                 │
                                 ▼ (Context: N=5)
                    ┌─────────────────────────┐
                    │ Generative Model G(.)   │  <-- Autoregressive LLM (TTFT: 50-200ms)
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ Final Validated Output  │
                    └─────────────────────────┘
```

Secara matematis, tahap representasi teks menjadi vektor mengandalkan transformer encoder. Diberikan sequence token $T = (t_1, t_2, \dots, t_L)$, encoder memetakan sequence ke dalam hidden states:

$$\mathbf{H} = \text{Encoder}(T) \in \mathbb{R}^{L \times d_{\text{model}}}$$

Untuk menghasilkan dense vector tunggal $\mathbf{e} \in \mathbb{R}^{d_{\text{model}}}$, kita menerapkan fungsi *pooling* (umumnya Mean Pooling):

$$\mathbf{e}_{\text{mean}} = \frac{\sum_{i=1}^L m_i \cdot \mathbf{h}_i}{\sum_{i=1}^L m_i}, \quad m_i \in \{0, 1\} \text{ (attention mask)}$$

Diikuti dengan normalisasi Euclidean agar perbandingan jarak dapat direduksi menjadi operasi *dot product* yang efisien:

$$\hat{\mathbf{e}} = \frac{\mathbf{e}_{\text{mean}}}{\|\mathbf{e}_{\text{mean}}\|_2} \implies \cos(\hat{\mathbf{e}}_1, \hat{\mathbf{e}}_2) = \hat{\mathbf{e}}_1^\top \hat{\mathbf{e}}_2$$

---

## 3. Why It Matters

1. **Efisiensi Biaya dan Komputasi**: Menjalankan input sebesar 100.000 token langsung ke model frontier seperti Claude 3.5 Sonnet atau GPT-4o untuk setiap interaksi membutuhkan biaya yang sangat tinggi dan latensi tinggi. Melalui pipeline compound, kita memfilter korpus data menjadi $\le 2.000$ token berbobot relevansi tinggi menggunakan inferensi embedding dan re-ranking berbiaya rendah ($\sim 1/1000$ biaya komputasi generatif).
2. **Kepatuhan Latency SLA Enterprise**: Pada skenario *real-time recommendation* atau *conversational customer-facing agents*, target p99 latency seringkali dipatok pada $< 250\text{ ms}$. Compound pipeline memungkinkan paralelisasi (misal: *hybrid search* sparse + dense secara bersamaan) dengan *strict timeouts*.
3. **Determinisme dan Auditability**: Model autoregresif murni bersifat stokastik. Dengan memisahkan layer pemanggilan memori (Vector DB + Dense Embedding) dari layer representasi logika (LLM), kita mendapatkan jejak audit eksplisit: dokumen spesifik mana yang dijadikan referensi oleh model untuk memproduksi jawabannya.

---

## 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur *production-grade* untuk Compound Inference Pipeline dengan jalur konkurensi asinkron, fallback handling, dan semantic caching:

```
+--------------------------------------------------------------------------------------------------+
|                                    INFERENCE PIPELINE GATEWAY                                    |
+--------------------------------------------------------------------------------------------------+
                                                 │
                                                 │ (1) Ingress Request (Async)
                                                 ▼
                             +───────────────────────────────────────+
                             │      Input Sanitization & Normalizer  │
                             +───────────────────┬───────────────────+
                                                 │
                                                 ▼
                             +───────────────────────────────────────+
                             │       Semantic Cache Check (Redis)    │
                             +───────────────────┬───────────────────+
                                                 │
                                ├────────────────┴───────────────┐
                     Cache HIT  │                                │ Cache MISS
                                ▼                                ▼
                   +────────────────────────+     +───────────────────────────────────────+
                   │ Return Cached Response │     │   Embedding Engine Pool (Triton/ORT)  │
                   +────────────────────────+     │   - Dynamic Batching                  │
                                                  │   - FP16/INT8 TensorRT execution      │
                                                  +───────────────────┬───────────────────+
                                                                      │
                                                                      ▼ (Dense Vector)
                                                  +───────────────────────────────────────+
                                                  │    Scatter-Gather Retrieval Stage     │
                                                  │    ├─ Vector Search (HNSW Dense)      │
                                                  │    └─ Lexical Search (BM25 Sparse)    │
                                                  +───────────────────┬───────────────────+
                                                                      │
                                                                      ▼ (Candidates: k=50)
                                                  +───────────────────────────────────────+
                                                  │  Cross-Encoder Stage (Re-ranker)      │
                                                  │  - SLA Timeout: 45ms                  │
                                                  │  - Fallback: RRF (Reciprocal Rank)    │
                                                  +───────────────────┬───────────────────+
                                                                      │
                                                                      ▼ (Top Candidates: N=3)
                                                  +───────────────────────────────────────+
                                                  │ Context Assembly & Guardrails Engine  │
                                                  +───────────────────┬───────────────────+
                                                                      │
                                                                      ▼
                                                  +───────────────────────────────────────+
                                                  │ Generative LLM Inference Engine       │
                                                  │ (vLLM / TensorRT-LLM / TGI)           │
                                                  +───────────────────┬───────────────────+
                                                                      │
                                                                      ▼ (2) Egress Response
```

---

## 5. Deep Dive Mekanisme & Prinsip Kerja

### 5.1 Dynamic Micro-Batching pada Embedding Generation

Inference embedding untuk satu teks menghasilkan *GPU core underutilization* karena beban kerja didominasi oleh latensi transfer memori (*memory-bandwidth bound*). Untuk mencapai utilisasi komputasi (*compute-bound*) optimal, engine harus mengimplementasikan queueing micro-batching berbasis window:

- Kueri yang datang dikumpulkan ke dalam buffer antrean.
- Batch dieksekusi ketika buffer mencapai ukuran $B_{\text{max}}$ (misal: 64 kueri) **atau** durasi timer batas latensi tercapai (misal: $\Delta t = 2\text{ ms}$).
- Dynamic padding diterapkan: Sequence dipad sampai panjang token terpanjang *di dalam batch tersebut*, bukan panjang token maksimal arsitektur model ($L_{\text{batch}} = \max_{i \in B}(len(T_i)) \ll L_{\text{max}}$). Ini menghemat hingga $70\%$ alokasi memori tensor.

### 5.2 Retrieval: Bi-Encoder vs. Cross-Encoder

| Parameter | Bi-Encoder (Dense Embeddings) | Cross-Encoder (Re-ranker) |
| :--- | :--- | :--- |
| **Arsitektur** | $f(q)$ dan $f(d)$ dihitung terpisah secara independen. | $f(q, d)$ dihitung bersamaan via self-attention penuh. |
| **Kompleksitas Komputasi** | $\mathcal{O}(|q| + |d|)$ (Bisa dihitung pra-indeks). | $\mathcal{O}((|q| + |d|)^2)$ untuk setiap pasangan kandidat. |
| **Latency** | Sangat Rendah ($\sim 5-15\text{ ms}$ via Indexing MIPS). | Tinggi ($\sim 1\text{ ms}$ per pasang dokumen; $50\text{ ms}$ untuk 50 dokumen). |
| **Interaksi Konteks** | Lemah (Hanya interaksi di layer representasi akhir melalui dot product). | Sangat Kuat (Semua token kueri berinteraksi dengan token dokumen sejak layer 1). |
| **Fungsi dalam Pipeline** | *First-stage retrieval* (Memfilter jutaan ke ratusan dokumen). | *Second-stage re-ranking* (Menyaring ratusan ke top 3-5 dokumen). |

### 5.3 Latency Budgeting & Speculative Fallbacks

Setiap compound pipeline wajib mendefinisikan *hard timeout budget* di setiap nodenya. Jika budget untuk Re-ranker didefinisikan sebesar $40\text{ ms}$, dan proses cross-encoder terhambat akibat antrean runtime atau GPU thermal throttling, arsitektur harus memiliki fallback deterministik:

1. **SLA Breach Threshold**: Jika $t_{\text{elapsed}} > 40\text{ ms}$, batalkan eksekusi remote inference melalui asynchronous cancellation (`asyncio.wait_for` / context cancellation).
2. **Fallback Logic**: Gunakan skor mentah hasil dense retrieval sebelumnya (k-NN distance) atau terapkan *Reciprocal Rank Fusion* (RRF) langsung pada input kandidat tanpa re-ranking lanjutan.
3. Pipeline tetap mengalir menuju tahapan Context Assembly tanpa melempar HTTP 500 ke klien.

---

## 6. Production-Ready Code Implementation

Implementasi berikut menggunakan Python 3.11+, sepenuhnya asinkron, *type-hinted*, menerapkan abstraksi *clean architecture*, menggunakan pooling tensor deterministik, serta dilengkapi mekanisme *timeout* dan *circuit-breaking fallback*.

```python
"""
Compound Inference Pipeline: Production Implementation
Architectural Tier: Inference Engineering Layer
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
import time
from typing import Any, Final, Protocol

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

# Setup logging standard
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("InferencePipeline")

# =====================================================================
# Domain Models & DTOs
# =====================================================================

class Document(BaseModel):
    doc_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    initial_score: float = 0.0
    rerank_score: float = 0.0


class InferenceQuery(BaseModel):
    query_id: str
    raw_text: str
    normalized_text: str | None = None
    embedding: list[float] | None = None


class PipelineResult(BaseModel):
    query_id: str
    final_context: list[Document]
    total_latency_ms: float
    pipeline_fallback_triggered: bool
    diagnostics: dict[str, float] = Field(default_factory=dict)


# =====================================================================
# Abstract Contracts (Interfaces)
# =====================================================================

class EmbeddingEngineProtocol(Protocol):
    async def embed_query(self, text: str) -> npt.NDArray[np.float32]:
        ...


class VectorIndexProtocol(Protocol):
    async def search(self, query_vector: npt.NDArray[np.float32], top_k: int) -> list[Document]:
        ...


class RerankerProtocol(Protocol):
    async def rerank(self, query: str, documents: list[Document], top_n: int) -> list[Document]:
        ...


# =====================================================================
# Concrete Implementations
# =====================================================================

class LocalMockEmbeddingEngine:
    """
    Simulasi Embedding Engine dengan Tensor Pooling & L2 Normalization.
    Dalam produksi nyata, logika ini dieksekusi via Triton Inference Server / ONNX Runtime.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _mean_pooling(
        self, token_embeddings: npt.NDArray[np.float32], attention_mask: npt.NDArray[np.int32]
    ) -> npt.NDArray[np.float32]:
        input_mask_expanded = np.broadcast_to(
            np.expand_dims(attention_mask, -1), token_embeddings.shape
        ).astype(np.float32)
        
        sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=0)
        sum_mask = np.clip(input_mask_expanded.sum(axis=0), a_min=1e-9, a_max=None)
        return sum_embeddings / sum_mask

    def _l2_normalize(self, vector: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        norm = np.linalg.norm(vector)
        if norm == 0.0:
            return vector
        return vector / norm

    async def embed_query(self, text: str) -> npt.NDArray[np.float32]:
        # Simulasi compute latency transformer encoding
        await asyncio.sleep(0.015)  # 15ms
        
        # Mock tensor outputs [seq_len=8, dim=384]
        seq_len = 8
        mock_tokens = np.random.randn(seq_len, self.dimension).astype(np.float32)
        mock_mask = np.ones((seq_len,), dtype=np.int32)
        
        pooled = self._mean_pooling(mock_tokens, mock_mask)
        return self._l2_normalize(pooled)


class MockVectorStore:
    """Simulasi Vector DB yang menggunakan Annoy/HNSW/IVF retrieval."""
    
    async def search(self, query_vector: npt.NDArray[np.float32], top_k: int) -> list[Document]:
        await asyncio.sleep(0.020)  # 20ms retrieval latency
        return [
            Document(
                doc_id=f"doc_idx_{i}",
                content=f"Konteks representasi data enterprise tingkat lanjut nomor {i}.",
                initial_score=float(1.0 / (i + 1))
            )
            for i in range(top_k)
        ]


class ResilientReranker:
    """
    Cross-Encoder Reranker dengan strict SLA latency budget.
    """
    def __init__(self, failure_probability: float = 0.0, simulated_latency: float = 0.035):
        self.failure_probability = failure_probability
        self.simulated_latency = simulated_latency

    async def rerank(self, query: str, documents: list[Document], top_n: int) -> list[Document]:
        # Simulasikan latency komputasi cross-encoder
        await asyncio.sleep(self.simulated_latency)
        
        if np.random.rand() < self.failure_probability:
            raise TimeoutError("Cross-Encoder compute instance degraded (Simulated SLA Timeout)")
            
        # Skor baru hasil kalkulasi simulasi cross-attention
        ranked_docs = []
        for doc in documents:
            cross_score = doc.initial_score * np.random.uniform(0.8, 1.2)
            doc.rerank_score = float(cross_score)
            ranked_docs.append(doc)
            
        ranked_docs.sort(key=lambda x: x.rerank_score, reverse=True)
        return ranked_docs[:top_n]


# =====================================================================
# Pipeline Orchestrator (Core Engine)
# =====================================================================

class CompoundInferencePipeline:
    """
    Orchestrator utama yang menjalankan compound inference secara asinkron
    dengan dynamic latency budgeting, strict error containment, dan metrics tracing.
    """
    def __init__(
        self,
        embedding_engine: EmbeddingEngineProtocol,
        vector_index: VectorIndexProtocol,
        reranker: RerankerProtocol,
        rerank_sla_budget_ms: float = 40.0,
    ):
        self.embedding_engine = embedding_engine
        self.vector_index = vector_index
        self.reranker = reranker
        self.rerank_sla_budget_s: Final[float] = rerank_sla_budget_ms / 1000.0

    def _normalize_text(self, text: str) -> str:
        """Sanitasi input inferensi deterministik."""
        return " ".join(text.strip().lower().split())

    async def execute(self, query_id: str, raw_query: str) -> PipelineResult:
        start_time = time.perf_counter()
        diagnostics: dict[str, float] = {}
        fallback_used = False

        # Phase 1: Ingress & Normalization
        t0 = time.perf_counter()
        normalized_q = self._normalize_text(raw_query)
        diagnostics["normalization_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 2: Embedding Generation
        t0 = time.perf_counter()
        try:
            vector = await self.embedding_engine.embed_query(normalized_q)
        except Exception as exc:
            logger.error("Embedding generation failed for %s: %s", query_id, exc, exc_info=True)
            raise RuntimeError(f"Critical Phase Failure: Embedding Stage - {str(exc)}") from exc
        diagnostics["embedding_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 3: Dense Retrieval Stage
        t0 = time.perf_counter()
        try:
            retrieved_docs = await self.vector_index.search(vector, top_k=20)
        except Exception as exc:
            logger.error("Vector search failed for %s: %s", query_id, exc, exc_info=True)
            raise RuntimeError(f"Critical Phase Failure: Vector Index - {str(exc)}") from exc
        diagnostics["retrieval_ms"] = (time.perf_counter() - t0) * 1000.0

        # Phase 4: Re-ranking Stage with Strict Latency Budget (Circuit Breaker)
        t0 = time.perf_counter()
        final_docs: list[Document]
        try:
            # Gunakan asyncio.wait_for untuk mengamankan latency budget
            final_docs = await asyncio.wait_for(
                self.reranker.rerank(normalized_q, retrieved_docs, top_n=5),
                timeout=self.rerank_sla_budget_s
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            logger.warning("Reranker SLA breached or timed out for %s: %s. Using heuristic fallback.", query_id, exc)
            fallback_used = True
            # Fallback: Urutkan berbasis initial_score dense retrieval langsung
            retrieved_docs.sort(key=lambda d: d.initial_score, reverse=True)
            final_docs = retrieved_docs[:5]
        except Exception as exc:
            logger.error("Unexpected error in reranker for %s: %s. Falling back to dense top-k.", query_id, exc)
            fallback_used = True
            retrieved_docs.sort(key=lambda d: d.initial_score, reverse=True)
            final_docs = retrieved_docs[:5]
            
        diagnostics["reranker_ms"] = (time.perf_counter() - t0) * 1000.0
        total_latency = (time.perf_counter() - start_time) * 1000.0

        return PipelineResult(
            query_id=query_id,
            final_context=final_docs,
            total_latency_ms=total_latency,
            pipeline_fallback_triggered=fallback_used,
            diagnostics=diagnostics
        )


# =====================================================================
# Execution & Verification Driver
# =====================================================================

async def main() -> None:
    logger.info("Initializing Compound Inference Engine Components...")
    
    embedder = LocalMockEmbeddingEngine(dimension=384)
    vector_db = MockVectorStore()
    
    # Test Skenario 1: Operasi Normal (Reranker latency: 30ms, SLA Budget: 50ms)
    reranker_fast = ResilientReranker(failure_probability=0.0, simulated_latency=0.030)
    pipeline_fast = CompoundInferencePipeline(embedder, vector_db, reranker_fast, rerank_sla_budget_ms=50.0)
    
    res1 = await pipeline_fast.execute("req-001", "  Jelaskan optimasi model embedding inference!  ")
    logger.info("Result 1: Latency=%.2fms | Fallback=%s", res1.total_latency_ms, res1.pipeline_fallback_triggered)
    logger.info("Diagnostics: %s", res1.diagnostics)
    assert not res1.pipeline_fallback_triggered, "Skenario normal seharusnya tidak memicu fallback."

    # Test Skenario 2: Degraded Reranker (Latency: 60ms, SLA Budget: 35ms -> SLA Breached)
    reranker_slow = ResilientReranker(failure_probability=0.0, simulated_latency=0.060)
    pipeline_slow = CompoundInferencePipeline(embedder, vector_db, reranker_slow, rerank_sla_budget_ms=35.0)
    
    res2 = await pipeline_slow.execute("req-002", "Bagaimana menangani SLA budget timeout?")
    logger.info("Result 2: Latency=%.2fms | Fallback=%s", res2.total_latency_ms, res2.pipeline_fallback_triggered)
    logger.info("Diagnostics: %s", res2.diagnostics)
    assert res2.pipeline_fallback_triggered, "Skenario bottleneck seharusnya memicu graceful fallback."

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 7. Edge Cases & Failure Modes

Dalam compound inference pipeline tingkat lanjut, kegagalan operasional jarang berbentuk *outright crashes*; sebaliknya, sistem umumnya mengalami degradasi tersembunyi (*silent performance decay*):

1. **Embedding Manifold Shift (Covariate Shift)**:
   - *Penyebab*: Teks kueri pengguna menggunakan kosakata baru, bahasa gaul, atau istilah teknis yang belum pernah dipelajari pada fase training/fine-tuning representasi model.
   - *Manifestasi*: Nilai similarity cosine terdistribusi sangat datar (entropi tinggi), k-NN mengembalikan tetangga acak berbobot rendah.
   - *Mitigasi*: Pasang detector anomali distribusi skor. Jika $\max_{i}(\text{similarity}(q, d_i)) < \tau$ (misal: $\tau = 0.35$), bypass dense retrieval dan langsung fallback ke *BM25 / Exact Lexical Search*.

2. **Long Sequence Attention Mask Corruption (OOM / Silent Truncation)**:
   - *Penyebab*: Input teks melampaui `max_seq_length` arsitektur encoder (misal: 512 token).
   - *Manifestasi*: Token penting di akhir paragraf dipangkas (*hard truncation*) tanpa peringatan, menghasilkan embedding yang hanya merepresentasikan salam pembuka atau metadata awal teks.
   - *Mitigasi*: Implementasikan *chunking sliding window* dengan overlap pada layer pre-processing atau gunakan arsitektur embedding berbasis ALiBi/RoPE yang mampu mengekstrapolasi hingga 8192 token (misal: *BGE-M3*).

3. **Cache Stampede (Thundering Herd Problem)**:
   - *Penyebab*: Query embedding cache miss pada lonjakan traffic (*burst*) bersamaan untuk topik yang viral.
   - *Manifestasi*: Ribuan request mencoba menghitung embedding yang sama di GPU secara paralel, menyebabkan sudden GPU out-of-memory (OOM) dan queue overflow.
   - *Mitigasi*: Terapkan *single-flight pattern* (misal: `golang/sync/singleflight` atau mutex locking berbasis hash kueri di Python) sehingga hanya satu compute task yang berjalan, sedangkan worker lain menunggu hasil komputasi yang pertama.

---

## 8. Trade-offs & Alternatif Solusi

| Dimensi Keputusan | Bi-Encoder + Vector DB | Cross-Encoder Reranker | Late-Interaction (ColBERT) | Hybrid Search (Dense + BM25 via RRF) |
| :--- | :--- | :--- | :--- | :--- |
| **NDCG@10 Accuracy** | Sedang ($\sim 0.65 - 0.72$) | Sangat Tinggi ($\sim 0.85 - 0.92$) | Tinggi ($\sim 0.82 - 0.88$) | Tinggi-Sedang ($\sim 0.75 - 0.80$) |
| **P99 Inference Latency** | Rendah ($< 15\text{ ms}$) | Tinggi ($50 - 150\text{ ms}$) | Moderat ($25 - 40\text{ ms}$) | Rendah-Moderat ($15 - 30\text{ ms}$) |
| **VRAM Consumption** | Rendah (Hanya 1x forward pass untuk kueri). | Sangat Tinggi ($N \times \text{forward pass}$). | Tinggi (Multi-vector representation untuk setiap token). | Nol tambahan VRAM (BM25 di memory/CPU). |
| **Storage Footprint** | Kecil ($d \times 4\text{ bytes}$ per dokumen). | Nol (Tidak ada state tersimpan selain model weights). | Sangat Besar (Jumlah token $\times d \times 4\text{ bytes}$). | Moderat (Inverted index RAM/Disk). |
| **Kapan Harus Dipilih** | Katalog data masif ($> 10^7$ entri) dengan keterbatasan hardware. | Layer final penyaringan kandidat (Top-50 $\to$ Top-5). | Kebutuhan akurasi tinggi tanpa saturasi latency compute Cross-Encoder. | Lingkungan enterprise di mana exact keyword search (SKU, nama orang) bersifat krusial. |

---

## 9. Best Practices & Standard Industri

1. **Adopsi Matryoshka Representation Learning (MRL)**: Gunakan model embedding generasi modern yang dilatih dengan MRL (seperti `text-embedding-3` atau `nomic-embed-text`). MRL memungkinkan Anda memotong vektor embedding dari dimensi 1536 menjadi 512 atau 256 tanpa kehilangan akurasi yang signifikan, menghemat biaya memori Vektor Database hingga $75\%$ dan mempercepat komputasi jarak secara linear.
2. **Kuantisasi Vektor (Scalar & Product Quantization)**: Lakukan kuantisasi dari FP32 ke INT8 atau Binary (1-bit representation) pada database vektor. Penggunaan binary vector search mengalihkan operasi FP32 dot-product ke komputasi instruksi prosesor native `POPCNT` (Population Count) pada level instruksi x86/ARM, memberikan peningkatan kecepatan inferensi hingga $20\times - 30\times$.
3. **Pemisahan Klaster Compute (Compute Decoupling)**: Jangan satukan microservice Embedding/Re-ranker dengan server Generatif (LLM). Model embedding membutuhkan akselerator VRAM kecil dengan latensi interkoneksi tinggi, sedangkan generative inference (vLLM) membutuhkan memory bandwidth masif dan tensor parallelism lintas multiple-GPU.
4. **OpenTelemetry Context Propagation**: Suntikkan metadata tracing (`traceparent`, `span_id`) ke setiap sub-komponen inferensi. Rekam durasi exact: `time_to_tokenize`, `time_to_embed`, `vector_search_latency`, dan `rerank_latency` untuk mendeteksi bottleneck sistemik di production.

---

## 10. Hands-on Lab Exercise

### Skenario Lab
Anda diminta untuk membangun dan menguji ketahanan sebuah **Compound Retrieval Pipeline** yang memiliki *SLA Latency Budget* $p99 \le 60\text{ ms}$. Pipeline harus mampu mengintegrasikan Dense Retrieval dan Re-ranking, serta wajib melakukan *automatic graceful degradation* apabila sub-sistem Re-ranker mengalami *latency spike*.

### Langkah-langkah Praktikum

#### Langkah 1: Persiapan Environment
Pastikan Anda memiliki virtual environment aktif dengan dependensi minimal:
```bash
python3 -m venv venv
source venv/bin/activate
pip install numpy pydantic
```

#### Langkah 2: Setup Dynamic Threshold Evaluator
Buat file `lab_compound_inference.py`. Implementasikan pengujian terkontrol untuk mengevaluasi dampak variasi beban latensi re-ranker terhadap stabilitas pipeline.

```python
# lab_compound_inference.py
import asyncio
import time
from typing import List
from dataclasses import dataclass

@dataclass
class CandidateDoc:
    id: int
    score: float

async def mock_dense_search() -> List[CandidateDoc]:
    await asyncio.sleep(0.015)  # 15ms base retrieval
    return [CandidateDoc(id=i, score=1.0 / (i + 1)) for i in range(10)]

async def unstable_reranker(docs: List[CandidateDoc], delay_ms: float) -> List[CandidateDoc]:
    await asyncio.sleep(delay_ms / 1000.0)
    # Re-order inversely as a test behavior
    return sorted(docs, key=lambda d: d.score, reverse=False)

async def compound_pipeline(reranker_delay_ms: float, sla_ms: float = 30.0) -> tuple[List[CandidateDoc], bool, float]:
    start = time.perf_counter()
    candidates = await mock_dense_search()
    
    fallback_triggered = False
    try:
        # Wrap cross-encoder in strict SLA deadline
        ranked = await asyncio.wait_for(
            unstable_reranker(candidates, reranker_delay_ms),
            timeout=sla_ms / 1000.0
        )
    except asyncio.TimeoutError:
        fallback_triggered = True
        ranked = candidates  # Fallback to dense scores directly

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ranked, fallback_triggered, elapsed_ms

async def run_stress_test():
    print("=== STARTING SLA BUDGET VERIFICATION TEST ===")
    
    test_delays = [10.0, 25.0, 35.0, 50.0, 100.0]
    sla_budget = 30.0
    
    for delay in test_delays:
        docs, fallback, total_time = await compound_pipeline(delay, sla_ms=sla_budget)
        print(f"Reranker Target: {delay:03.1f}ms | Total Pipeline: {total_time:03.1f}ms | "
              f"Fallback: {str(fallback):<5} | Top Doc ID: {docs[0].id}")
        
        # Validasi: Total waktu tidak boleh membengkak drastis melampaui Dense + SLA budget
        assert total_time < (15.0 + sla_budget + 15.0), f"SLA Violation detected: {total_time}ms"
        
    print("=== TEST COMPLETED SUCCESSFULLY: SLA CONTAINMENT VERIFIED ===")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip:
```bash
python lab_compound_inference.py
```

#### Langkah 4: Kriteria Keberhasilan (Pass Matrix)
- Output mencetak status transisi dari `Fallback: False` ke `Fallback: True` secara mulus tepat ketika delay reranker melampaui `sla_budget` ($30.0\text{ ms}$).
- Nilai `Top Doc ID` harus kembali ke `id: 0` (skor teratas Dense Search) saat fallback terpicu, alih-alih melempar exception atau memblokir eksekusi.
- Total pipeline latency tidak boleh melampaui batas toleransi ($\sim 45-60\text{ ms}$) meskipun reranker mengalami degradasi ekstrim ($100\text{ ms}$).