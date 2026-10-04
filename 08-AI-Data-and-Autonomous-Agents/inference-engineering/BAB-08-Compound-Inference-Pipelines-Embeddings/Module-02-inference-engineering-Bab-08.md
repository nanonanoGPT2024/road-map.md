# Kurikulum Rekayasa Sistem AI: Inference Engineering
## Bab 08: Compound Inference Pipelines & Embeddings
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Mendesain dan Mengimplementasikan Arsitektur Compound AI System** yang mengombinasikan *semantic dynamic routing*, *speculative cascading inference*, serta *hybrid embedding retrieval* (dense, sparse lexical, dan late-interaction) untuk beban kerja tingkat enterprise.
- **Mengoptimalkan P99 Latency dan Resource Utilization** pada kluster heterogen (CPU + GPU) dengan menerapkan teknik *continuous batching*, *KV-cache offloading*, dan pemisahan *prefill/decode engine*.
- **Membangun Pipeline Hybrid Embedding Skala Besar** menggunakan model BGE-M3 / SPLADE dan ColBERT (Late Interaction) yang terintegrasi dengan Vector Database terdistribusi dan *hardware accelerator* (Triton Inference Server / vLLM / TensorRT-LLM).
- **Menerapkan Pola Fault-Tolerance & Circuit Breaking** khusus inferensi, mencegah *cascading failure* akibat *GPU Out-of-Memory (OOM)*, *context-length explosion*, dan degradasi latensi backend.
- **Mengembangkan dan Mengaudit Observabilitas Komprehensif** (latensi per tahap, *time-to-first-token* [TTFT], *inter-token latency* [ITL], *effective throughput*, dan *cost-per-million-tokens*).

---

### 2. Prerequisites
Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Systems Programming & Async Concurrency**: Mahir dalam Python AsyncIO, threading model, multiprocessing, serta konsep dasar inter-process communication (IPC) melalui shared memory.
- **Machine Learning Runtime Foundations**: Memahami arsitektur dasar Transformer (Attention mechanism, KV Cache, Tokenization), representasi floating point (FP32, FP16, BF16, FP8, INT4), dan metrik komputasi FLOPs.
- **GPU Computing Basics**: Paham cara kerja NVIDIA CUDA, VRAM allocation, CUDA streams, Tensor Cores, serta penyebab memory fragmentation dan kernel launch overhead.
- **Modern Serving Frameworks**: Pengalaman dasar dengan Triton Inference Server, vLLM, TensorRT-LLM, atau HuggingFace TGI.
- **Vector Search & IR Math**: Memahami operasi vektor (Cosine Similarity, Dot Product, Euclidean Distance), Approximate Nearest Neighbor (HNSW, IVF-PQ), dan evaluasi Information Retrieval (NDCG@k, MRR@k, Recall@k).

---

### 3. Concept & Internal Architecture

Compound Inference Pipeline adalah paradigma pergeseran dari inferensi monolitik (memanggil satu Large Language Model raksasa untuk seluruh tugas) menuju orkestrasi sistem modular terdistribusi. Sistem ini mengombinasikan beragam model spesialis (ukuran kecil, menengah, dan besar), pipeline representasi embedding bertingkat, serta mekanisme kontrol alur dinamis demi memaksimalkan akurasi faktual, meminimalkan biaya inferensi, dan mempertahankan P99 latency di bawah SLA yang ketat.

```
                              [ Incoming Client Request ]
                                           │
                                           ▼
                 ┌───────────────────────────────────────────────────┐
                 │  API Gateway & Token-Bucket Rate Limiter (Envoy)  │
                 └─────────────────────────┬─────────────────────────┘
                                           │
                                           ▼
                 ┌───────────────────────────────────────────────────┐
                 │      Fast-Path Semantic Router (Cache & SLM)      │
                 │      (Redis Semantic Cache / GBNF Guided Router)  │
                 └───────┬───────────────────────────────────┬───────┘
                         │ Cache HIT                         │ Cache MISS
                         ▼                                   ▼
             ┌───────────────────────┐   ┌───────────────────────────────────┐
             │ Immediate Response    │   │  Dynamic Multi-Stage Query Engine │
             │ (Latency < 5ms)       │   └─────────────────┬─────────────────┘
             └───────────────────────┘                     │
       ┌───────────────────────────────────────────────────┴──────────────────────┐
       │ Dense & Sparse Embedding Generation (Triton / TensorRT-LLM)              │
       │                                                                          │
       │  ┌─────────────────────────┐               ┌──────────────────────────┐  │
       │  │ Dense Model (BGE-M3)    │               │ Sparse Lexical (SPLADE)  │  │
       │  │ Output: 1024-dim Vector │               │ Output: Bag of Words Dict│  │
       │  └────────────┬────────────┘               └────────────┬─────────────┘  │
       └───────────────┼─────────────────────────────────────────┼────────────────┘
                       │                                         │
                       ▼                                         ▼
       ┌──────────────────────────────────────────────────────────────────────────┐
       │ Ann Search (Qdrant / Milvus Cluster) -> Multi-Vector Reciprocal Rank     │
       │ Candidate Set: Top-100 Docs                                              │
       └───────────────────────────────────┬──────────────────────────────────────┘
                                           │
                                           ▼
       ┌──────────────────────────────────────────────────────────────────────────┐
       │ Late Interaction Reranking (ColBERT / Cross-Encoder FP16)                │
       │ Token-level MaxSim Matrix Multiplication -> Reduced to Top-5 Docs        │
       └───────────────────────────────────┬──────────────────────────────────────┘
                                           │
                                           ▼
       ┌──────────────────────────────────────────────────────────────────────────┐
       │ Speculative Cascaded Generation Layer                                    │
       │                                                                          │
       │  ┌──────────────────────────────────────┐                                │
       │  │ Draft Model (e.g. Qwen-2.5-1.5B)     │──┐ Tokens                      │
       │  │ High Throughput / Low VRAM           │  │                             │
       │  └──────────────────────────────────────┘  │                             │
       │                     ▼                      │ Speculative Verification    │
       │  ┌──────────────────────────────────────┐  │                             │
       │  │ Target Verifier (e.g. Qwen-2.5-72B)  │◄─┘ Acceptance Rate: ~75%       │
       │  │ FlashAttention-3 / Continuous Batch  │                                │
       │  └──────────────────┬───────────────────┘                                │
       └─────────────────────┼────────────────────────────────────────────────────┘
                             │
                             ▼
                 [ Streaming Final Response ]
```

#### Arsitektur Inti:
1. **Dynamic Intent & Semantic Routing**:
   Menggunakan model representasi kecil (atau Small Language Model/SLM terkuantisasi INT8) untuk mengukur entropi, kompleksitas kueri, dan domain klasifikasi. Kueri faktual sederhana dialihkan ke model inferensi kecil berbobot ringan atau lookup cache; kueri penalaran kompleks multi-langkah dialihkan ke engine model parameter besar melalui pipeline penalaran rantai (Chain-of-Thought).
2. **Dense-Sparse Hybrid Retrieval Engine**:
   - **Dense Vectors (BGE-M3 / Contriever)**: Menangkap kedekatan semantik laten pada ruang berdimensi tinggi ($d=1024$), unggul dalam sinonimi dan *cross-lingual mapping*.
   - **Sparse Lexical Encoders (SPLADE / learned term expansions)**: Menghasilkan representasi sparse berbobot term ($d \approx 30522$), mempertahankan akurasi token unik eksak (seperti nomor SKU, kode error, ID transaksi finansial) yang kerap terdistorsi dalam kompresi dense.
3. **Late-Interaction Re-ranking (ColBERT Architecture)**:
   Berbeda dari Cross-Encoder konvensional yang menggabungkan seluruh teks kueri dan dokumen ke dalam self-attention ($O((L_q + L_d)^2)$ FLOPs), arsitektur ColBERT mengencode kueri dan dokumen secara independen menjadi sekumpulan token embedding. Keselarasan dihitung menggunakan operator MaxSim:
   $$S(Q, D) = \sum_{i \in |Q|} \max_{j \in |D|} (E_{q, i} \cdot E_{d, j}^\top)$$
   Mekanisme ini memungkinkan representasi dokumen dipra-komputasi (pre-indexed) secara offline, mempertahankan akurasi sekelas Cross-Encoder dengan latensi evaluasi runtime sekelas Dot-Product.
4. **Speculative Decoding & Cascading Execution**:
   Memanfaatkan *Draft Model* yang sangat efisien untuk memprediksi $K$ token ke depan secara autoregresif spekulatif, diikuti verifikasi paralel satu-langkah (*single-step forward pass*) oleh *Target Model* yang berukuran jauh lebih besar. Token yang tidak lolos kriteria verifikasi probabilitas stokastik ditolak dan diperbaiki seketika, meningkatkan rasio generasi token per detik secara substansial tanpa menurunkan presisi bobot target model.

---

### 4. Why & What

| Dimensi Arsitektur | Monolithic Model Inference | Compound Inference Pipelines |
| :--- | :--- | :--- |
| **Pola Konsumsi Resource** | Alokasi VRAM seragam untuk seluruh jenis kueri, menyebabkan inefisiensi komputasi pada kueri trivial. | Heterogeneous scheduling: alokasi VRAM/Compute proporsional dengan kompleksitas tugas. |
| **Tail Latency (P99)** | Sangat dipengaruhi variasi panjang konteks dan *head-of-line blocking* pada dynamic batching besar. | Stabil; kueri deterministik dialihkan melalui cache dan jalur retrieval cepat, mengisolasi model besar. |
| **Penanganan Lexical vs Semantik** | Rawan halusinasi nama entitas khusus/kode acuan unik jika hanya mengandalkan dense representation. | Hybrid Fusion (Dense + Sparse + ColBERT) menjamin retensi token langka (*exact-match*) tanpa kehilangan semantik. |
| **Efisiensi Biaya per Juta Token** | Sangat mahal; beban kueri seragam dieksekusi pada GPU Tier-1 (H100/A100). | Efisien; 60–80% kueri diselesaikan oleh edge SLM, cache, atau model terkuantisasi hemat daya (L4/A10G). |
| **Ketergantungan Model Single-Point**| Downtime atau degradasi performa model tunggal menghentikan seluruh layanan. | Modular; subsistem retrieval, routing, dan generation memiliki fallback independen berprinsip *graceful degradation*. |

---

### 5. How (Workflow Detail)

1. **Ingress & Semantic Fingerprinting**:
   Kueri masuk dinormalisasi. Sistem menghitung *Locality-Sensitive Hash (LSH)* dan embedding kueri cepat. Semantic cache (Redis VSS / Valkey) dievaluasi dengan ambang batas Cosine Similarity $> 0.96$. Jika terpenuhi, respon langsung disajikan (latensi $< 5\text{ ms}$).
2. **Intent Classification & Routing Decisions**:
   Jika cache miss, embedding kueri diproses oleh router mikro-deterministik. Router mengevaluasi kompleksitas kueri, kebutuhan retrieval data privat, dan level SLA:
   - Jalur Langsung (*Zero-Shot Response* via SLM terdistribusi).
   - Jalur Retrieval Augmentation (*Compound Dense-Sparse Engine*).
   - Jalur Heavy Reasoning (*Speculative Cascaded Pipeline*).
3. **Hybrid Representation & Dual-Stage Ann Search**:
   Kueri dikirim secara konkuren ke engine model inferensi embedding (Triton) untuk mengekstraksi vektor Dense (1024-dim FP16) dan Sparse Tokens (SPLADE log-magnitude non-zero elements). Keduanya dikirim ke vector engine terdistribusi untuk dieksekusi melalui Reciprocal Rank Fusion (RRF):
   $$RRF\_Score(d) = \sum_{m \in \{dense, sparse\}} \frac{1}{k + r_m(d)}$$
   dengan $k = 60$ dan $r_m(d)$ merepresentasikan rank relatif dokumen $d$ pada metrik retrieval $m$.
4. **Late-Interaction Re-ranking**:
   Top-$N$ dokumen kandidat (misal $N=100$) dari RRF diteruskan ke model ColBERT / Cross-Encoder. Operator MaxSim dijalankan pada GPU Tensor Cores, mereduksi kandidat menjadi Top-$K$ dokumen (misal $K=5$) dengan relevansi kontekstual tertinggi.
5. **Contextual Compaction & Speculative Synthesis**:
   Top-$K$ teks dokumen dirangkum/dieliminasi redundansinya menggunakan algoritma lexical compression. Prompt yang telah dipadatkan diserahkan ke sistem *Continuous Batching Engine* (vLLM / TensorRT-LLM):
   - Draft Model memprediksi token kandidat $[t_1, t_2, \dots, t_K]$.
   - Target Model memverifikasi token secara serentak dalam satu forward pass logit evaluation.
6. **Streaming Egress & Telemetry**:
   Token yang terverifikasi dialirkan ke klien via Server-Sent Events (SSE) atau gRPC stream. Seluruh jejak latensi per-tahap dikirim secara asinkron ke Prometheus dan OpenTelemetry Collector.

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan **Unit Gawat Darurat (UGD) Rumah Sakit Kelas Dunia**:
- **Semantic Router** adalah *Perawat Triase Primer*: Memeriksa pasien di pintu masuk. Luka lecet langsung diobati di tempat dengan plester (Cache Hit / SLM), tidak perlu memanggil dokter spesialis bedah.
- **Hybrid Retrieval (Dense + Sparse)** adalah *Pencarian Rekam Medis*:
  - *Dense Embedding*: Mencari gejala umum dan riwayat serupa (misal: "nyeri dada tembus ke punggung").
  - *Sparse Lexical*: Mencari nomor registrasi obat, kode ICD-10, atau alergi spesifik pasien yang tidak boleh salah satu karakter pun.
- **Late-Interaction Reranking (ColBERT)** adalah *Dokter Spesialis Diagnostik*: Mencocokkan lembar hasil tes laboratorium pasien per-parameter secara presisi sebelum tindakan bedah.
- **Speculative Generation** adalah *Tim Dokter Bedah & Residen*: Residen bedah (Draft Model) memasang jahitan awal dengan cepat; Dokter Bedah Konsultan (Target Model) mengawasi secara simultan. Jika gerakan residen presisi, operasi selesai 3x lebih cepat. Jika salah, dokter spesialis langsung mengambil alih instrumen bedah tanpa menunda proses.

#### Topologi Memori dan Eksekusi Antar-Komponen

```
+-----------------------------------------------------------------------------------+
| COMPUTE NODE (GPU Host Node - 8x NVIDIA H100 80GB SXM5)                           |
|                                                                                   |
|  [ GPU 0 & 1: Embedding & Ranking Pool ]   [ GPU 2 - 7: Speculative Engine Pool ] |
|  +-------------------------------------+   +------------------------------------+ |
|  | Triton Inference Server Instance   |   | vLLM / TensorRT-LLM Engine         | |
|  |                                     |   |                                    | |
|  |  +-------------------------------+  |   |  +------------------------------+  | |
|  |  | BGE-M3 (Dense) TensorRT Engine|  |   |  | Draft Engine: Qwen-2.5-1.5B  |  | |
|  |  | FP16 Dynamic Batch: Max 64    |  |   |  | (TP=1, Native PagedAttn)     |  | |
|  |  +-------------------------------+  |   |  +--------------┬---------------+  | |
|  |  +-------------------------------+  |   |                 │ Shared IPC Ring  | |
|  |  | SPLADE (Sparse) ONNX Runtime  |  |   |                 ▼ Buffer           | |
|  |  | INT8 Dynamic Batch: Max 128   |  |   |  +------------------------------+  | |
|  |  +-------------------------------+  |   |  | Target Engine: Qwen-2.5-72B  |  | |
|  |  +-------------------------------+  |   |  | (TP=4, PagedAttention v2,   |  | |
|  |  | ColBERTv2.0 Re-rank Kernel     |  |   |  |  FP8 Quantized GEMM Kernels) |  | |
|  |  | Custom CUDA MaxSim Operator   |  |   |  +------------------------------+  | |
|  |  +-------------------------------+  |   +------------------------------------+ |
|  +-------------------------------------+                                          |
|                                                                                   |
|  [ Host Shared Memory (tmpfs /dev/shm IPC Ring Buffer) ]                          |
|  Zero-Copy Vector Transfer & Deserialization Subsystem                            |
+-----------------------------------------------------------------------------------+
```

---

### 7. Code Examples

Berikut adalah implementasi sistem orkestrator inferensi produksi compound berbasis Python murni dengan asynchronous worker, circuit breaker, semantic caching, dual embedding pipeline, late-interaction scoring, dan fallback handling.

#### File: `production_compound_orchestrator.py`

```python
#!/usr/bin/env python3
"""
Enterprise-Grade Compound Inference Orchestration Engine.
Features:
- Asynchronous Non-blocking Execution Flow
- Dynamic Fallback & Circuit Breaker Logic
- Integrated Dense-Sparse Feature Extraction Simulation
- Late-Interaction MaxSim Scoring Alignment
- High-Throughput Batch-Aware Generation Interface
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("CompoundInferenceEngine")


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    recovery_time_seconds: float = 10.0


class InferenceCircuitBreaker:
    """Melindungi sistem dari cascading failure jika downstream GPU engine crash."""
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"CircuitBreaker[{self.name}] trip ke state OPEN. Kegagalan: {self.failure_count}")

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            now = time.monotonic()
            if now - self.last_failure_time > self.config.recovery_time_seconds:
                self.state = CircuitState.HALF_OPEN
                logger.warning(f"CircuitBreaker[{self.name}] bertransisi ke HALF_OPEN. Menguji kesehatan sistem.")
                return True
            return False
        return True  # HALF_OPEN


@dataclass
class QueryPayload:
    query_id: str
    prompt: str
    tenant_id: str
    max_tokens: int = 256
    temperature: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchDocument:
    doc_id: str
    content: str
    dense_vector: Optional[np.ndarray] = None
    sparse_weights: Optional[Dict[str, float]] = None
    token_embeddings: Optional[np.ndarray] = None  # Format: (SeqLen, HiddenDim)


@dataclass
class InferenceResponse:
    query_id: str
    output_text: str
    latency_ms: float
    pipeline_route: str
    tokens_generated: int
    used_cache: bool = False


class MockRedisSemanticCache:
    """Simulasi semantic cache dengan high precision similarity gate."""
    def __init__(self):
        self.cache_store: Dict[str, Tuple[np.ndarray, str]] = {}

    async def get(self, query_emb: np.ndarray, threshold: float = 0.96) -> Optional[str]:
        if not self.cache_store:
            return None
        
        # Linear scan simulasi pencarian vector cache
        for _, (cached_emb, cached_text) in self.cache_store.items():
            sim = float(np.dot(query_emb, cached_emb) / (
                np.linalg.norm(query_emb) * np.linalg.norm(cached_emb) + 1e-9
            ))
            if sim >= threshold:
                return cached_text
        return None

    async def set(self, query_id: str, query_emb: np.ndarray, response_text: str):
        self.cache_store[query_id] = (query_emb, response_text)


class DenseSparseEmbeddingClient:
    """Klien pengeksekusi model BGE-M3 (Dense) dan SPLADE (Sparse) terisolasi."""
    def __init__(self, breaker: InferenceCircuitBreaker):
        self.breaker = breaker
        self.hidden_dim = 128  # Dikecilkan untuk demonstrasi, standar: 1024

    async def encode(self, text: str) -> Tuple[np.ndarray, Dict[str, float], np.ndarray]:
        if not self.breaker.allow_request():
            raise RuntimeError("Circuit breaker terbuka untuk Embedding Service.")

        try:
            # Simulasi latensi komputasi TensorRT / Triton backend (5-10ms)
            await asyncio.sleep(0.008)
            
            # Deterministic mock pseudo-embedding berdasarkan hash teks
            seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)

            # 1. Dense Embedding Vector
            dense_emb = rng.randn(self.hidden_dim).astype(np.float32)
            dense_emb /= np.linalg.norm(dense_emb) + 1e-9

            # 2. Sparse Lexical Weights (SPLADE simulation: term -> weight)
            tokens = text.lower().split()
            sparse_weights = {tok: float(rng.uniform(0.5, 3.5)) for tok in tokens}

            # 3. Token-level Embeddings for Late Interaction (ColBERT style)
            seq_len = max(len(tokens), 4)
            token_embs = rng.randn(seq_len, self.hidden_dim).astype(np.float32)
            # L2 Normalize along feature axis
            token_embs /= np.linalg.norm(token_embs, axis=1, keepdims=True) + 1e-9

            self.breaker.record_success()
            return dense_emb, sparse_weights, token_embs

        except Exception as e:
            self.breaker.record_failure()
            logger.error(f"Gagal memproses embedding: {e}")
            raise


class LateInteractionReranker:
    """ColBERT-style Tensor MaxSim Execution Core."""
    @staticmethod
    def maxsim(query_tokens: np.ndarray, doc_tokens: np.ndarray) -> float:
        """
        Menghitung MaxSim score:
        Query: (Q_len, Dim), Doc: (D_len, Dim)
        Similarity Matrix = Q @ D.T -> (Q_len, D_len)
        MaxSim = Sum(Max(Similarity Matrix, axis=1))
        """
        # (Q_len, Dim) x (Dim, D_len) -> (Q_len, D_len)
        sim_matrix = np.matmul(query_tokens, doc_tokens.T)
        # Max along document sequence tokens, then reduce-sum across query tokens
        max_per_query_token = np.max(sim_matrix, axis=1)
        total_score = float(np.sum(max_per_query_token))
        return total_score

    async def rerank(
        self,
        query_token_embs: np.ndarray,
        candidates: List[SearchDocument],
        top_k: int = 3
    ) -> List[Tuple[SearchDocument, float]]:
        # Simulasi parallel kernel execution pada tensor cores
        await asyncio.sleep(0.005)
        scored_docs: List[Tuple[SearchDocument, float]] = []

        for doc in candidates:
            if doc.token_embeddings is not None:
                score = self.maxsim(query_token_embs, doc.token_embeddings)
            else:
                score = 0.0
            scored_docs.append((doc, score))

        # Sort descending berdasarkan score MaxSim
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]


class SpeculativeGenerationEngine:
    """
    Simulasi Speculative Decoding Engine:
    Draft Model (Kecil/Cepat) menghasilkan N token; Target Model (Besar) memverifikasi paralel.
    """
    def __init__(self, breaker: InferenceCircuitBreaker):
        self.breaker = breaker

    async def generate_speculative(
        self,
        prompt: str,
        context: str,
        max_tokens: int
    ) -> Tuple[str, int]:
        if not self.breaker.allow_request():
            raise RuntimeError("Circuit breaker terbuka untuk Speculative Engine.")

        try:
            # Simulasi latensi inferensi draft model + target verification pass
            # Menghemat ~2.5x dibanding pure autoregressive model besar tunggal
            await asyncio.sleep(0.045)  # 45ms batch execution

            acceptance_rate = 0.80  # 80% draft tokens diterima target model
            draft_tokens_proposed = min(max_tokens, 64)
            accepted_tokens = int(draft_tokens_proposed * acceptance_rate)
            
            output_text = (
                f"[Compound Response Synthesized] Berdasarkan konteks terverifikasi:\n"
                f"{context[:120]}...\nHasil penalaran sistem valid."
            )
            self.breaker.record_success()
            return output_text, accepted_tokens

        except Exception as e:
            self.breaker.record_failure()
            logger.error(f"Gagal pada Speculative Generation: {e}")
            raise


class FallbackSLMEngine:
    """Fallback engine berbobot ringan saat pipeline heavy inference mengalami degradasi."""
    async def generate(self, prompt: str) -> str:
        await asyncio.sleep(0.015)  # 15ms quick degradation path
        return f"[Degraded Fallback SLM] Respon parsial untuk: '{prompt[:40]}...'"


class CompoundPipelineOrchestrator:
    """Komponen sentral penyatu routing, retrieval, late-interaction, dan generation."""
    def __init__(self):
        self.emb_breaker = InferenceCircuitBreaker("EmbeddingService", CircuitBreakerConfig())
        self.gen_breaker = InferenceCircuitBreaker("SpeculativeEngine", CircuitBreakerConfig())
        
        self.cache = MockRedisSemanticCache()
        self.embedding_client = DenseSparseEmbeddingClient(self.emb_breaker)
        self.reranker = LateInteractionReranker()
        self.speculative_engine = SpeculativeGenerationEngine(self.gen_breaker)
        self.fallback_engine = FallbackSLMEngine()

        # Database internal dummy untuk topologi Ann Search
        self.mock_document_corpus = self._bootstrap_corpus()

    def _bootstrap_corpus(self) -> List[SearchDocument]:
        corpus = [
            SearchDocument(
                doc_id="DOC-8001",
                content="SOP Insiden Sistem Finansial: Jika database primary replikasi tertunda > 10 detik, "
                        "lakukan failover otomatis ke read-replica zona-2 dan turunkan isolasi transaksi."
            ),
            SearchDocument(
                doc_id="DOC-8002",
                content="Prosedur Maintenance Jaringan: Migrasi BGP routing harus dilakukan pada maintenance window "
                        "pukul 02:00 UTC menggunakan protokol zero-packet-loss tunneling."
            ),
            SearchDocument(
                doc_id="DOC-8003",
                content="Sistem Otentikasi: Token JWT wajib ditandatangani dengan algoritma Ed25519 dan memiliki "
                        "masa aktif maksimal 900 detik sebelum rotasi public key."
            )
        ]
        return corpus

    async def warm_up(self):
        """Pre-index dokumen mock ke representasi embedding lengkap."""
        logger.info("Memulai indexing corpus internal (Dense, Sparse, ColBERT)...")
        for doc in self.mock_document_corpus:
            dense, sparse, tokens = await self.embedding_client.encode(doc.content)
            doc.dense_vector = dense
            doc.sparse_weights = sparse
            doc.token_embeddings = tokens
        logger.info("Indexing corpus selesai. Sistem siap menerima trafik produksi.")

    async def process_query(self, payload: QueryPayload) -> InferenceResponse:
        start_time = time.monotonic()
        
        # 1. Fast Path Intent & Semantic Extraction
        q_dense, q_sparse, q_tokens = await self.embedding_client.encode(payload.prompt)

        # 2. Evaluasi Semantic Cache
        cached_result = await self.cache.get(q_dense)
        if cached_result:
            latency = (time.monotonic() - start_time) * 1000.0
            return InferenceResponse(
                query_id=payload.query_id,
                output_text=cached_result,
                latency_ms=latency,
                pipeline_route="SEMANTIC_CACHE_HIT",
                tokens_generated=len(cached_result.split()),
                used_cache=True
            )

        # 3. Dynamic Hybrid Retrieval Stage (RRF Simulator)
        # Menghitung dense cosine similarity
        candidates: List[Tuple[SearchDocument, float]] = []
        for doc in self.mock_document_corpus:
            if doc.dense_vector is not None:
                dense_sim = float(np.dot(q_dense, doc.dense_vector))
                candidates.append((doc, dense_sim))
        
        # Sort dense top candidates
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = [doc for doc, _ in candidates]

        # 4. Late Interaction ColBERT Reranking Stage
        ranked_docs = await self.reranker.rerank(q_tokens, top_candidates, top_k=2)
        assembled_context = "\n".join([doc.content for doc, _ in ranked_docs])

        # 5. Speculative Generation dengan Graceful Degradation Circuit Breaker
        route = "SPECULATIVE_CASCADE_PRIMARY"
        tokens_count = 0
        try:
            output_text, tokens_count = await self.speculative_engine.generate_speculative(
                prompt=payload.prompt,
                context=assembled_context,
                max_tokens=payload.max_tokens
            )
            # Simpan hasil berkualitas tinggi ke cache
            await self.cache.set(payload.query_id, q_dense, output_text)

        except Exception as e:
            logger.warning(f"Primary speculative generator gagal ({e}). Mengaktifkan Fallback SLM.")
            output_text = await self.fallback_engine.generate(payload.prompt)
            route = "FALLBACK_DEGRADED_SLM"
            tokens_count = len(output_text.split())

        latency = (time.monotonic() - start_time) * 1000.0
        return InferenceResponse(
            query_id=payload.query_id,
            output_text=output_text,
            latency_ms=latency,
            pipeline_route=route,
            tokens_generated=tokens_count,
            used_cache=False
        )


# =====================================================================
# Verification Execution Entrypoint
# =====================================================================
async def main():
    orchestrator = CompoundPipelineOrchestrator()
    await orchestrator.warm_up()

    test_queries = [
        QueryPayload(
            query_id="REQ-001",
            prompt="Bagaimana SOP penanganan jika database primary replikasi tertunda?",
            tenant_id="FINTECH-CORE"
        ),
        QueryPayload(
            query_id="REQ-002",
            prompt="Bagaimana SOP penanganan jika database primary replikasi tertunda?",  # Pengujian Cache Hit
            tenant_id="FINTECH-CORE"
        ),
        QueryPayload(
            query_id="REQ-003",
            prompt="Berapa masa aktif token otentikasi JWT dan algoritma apa yang dipakai?",
            tenant_id="SECURITY-OPS"
        )
    ]

    print("\n" + "="*80)
    print("MENJALANKAN PIPELINE EVALUASI COMPOUND INFERENCE")
    print("="*80)

    for q in test_queries:
        response = await orchestrator.process_query(q)
        print(f"\n[ID: {response.query_id}]")
        print(f"Route Executed     : {response.pipeline_route}")
        print(f"Latency End-to-End : {response.latency_ms:.2f} ms")
        print(f"Cache Used         : {response.used_cache}")
        print(f"Tokens Count       : {response.tokens_generated}")
        print(f"Response Payload   :\n{response.output_text}")
        print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Global FinTech Payment Clearing Gateway
Sebuah institusi kliring finansial multi-nasional memproses lebih dari 45.000 transaksi kueri analitik per detik (QPS) pada jam sibuk. Kueri mencakup resolusi sengketa penipuan (*fraud disputes*), kepatuhan regulasi transaksi perbankan, dan audit histori instan.

#### Permasalahan Skala Produksi:
1. **Cost Explosion**: Menjalankan seluruh kueri ke kluster Llama-3-70B FP16 membutuhkan 128 server DGX H100, menelan biaya infrastruktur lebih dari $420.000/bulan.
2. **Strict Latency SLA**: SLA P99 untuk API audit investigasi dipatok ketat pada $\le 250\text{ ms}$. Kueri regulasi murni sering terblokir oleh kueri rekonsiliasi kompleks berkonteks panjang (*head-of-line blocking*).
3. **Severe Exact-Match Hallucinations**: Model generalis kerap keliru mereferensikan nomor transaksi finansial (misal: kode referensi ISO-8583 32-karakter) karena pemotongan subword tokenization pada pure dense vector search.

#### Solusi Compound Engineering Terpasang:
- **Tingkat 1 - Semantic Routing & Token-Level Exact Cache**:
  Implementasi cache semantik dua tingkat menggunakan Redis Cluster in-memory. Jika kemiripan kueri $> 0.98$ dan hash entitas rekening identik, respon disajikan dalam $< 8\text{ ms}$. Berhasil menyerap 42% volume trafik berulang.
- **Tingkat 2 - Hybrid Sparse (SPLADE) & Dense (BGE-M3) pada Triton Inference Server**:
  SPLADE dialokasikan khusus memetakan ID rekening, kode cabang, dan nilai mata uang secara leksikal eksak ke inverted index. BGE-M3 memetakan narasi konteks fraud. Hasilnya digabung via Reciprocal Rank Fusion (RRF).
- **Tingkat 3 - Late Interaction (ColBERT) Hardware-Accelerated Kernel**:
  Reranking 150 kandidat teratas dipadatkan menjadi 5 konteks paling relevan menggunakan custom Triton C++ MaxSim operator berlatensi $< 12\text{ ms}$ pada Tensor Core FP16.
- **Tingkat 4 - Speculative Decoding Engine**:
  Menggunakan model Qwen-2.5-1.5B INT8 sebagai Draft Model dan Llama-3-70B FP8 sebagai Target Verifier. Rasio penerimaan token mencapai 78%, memangkas generation latency dari $340\text{ ms}$ menjadi $115\text{ ms}$.

#### Dampak Bisnis & Metrik Finansial:
- **Penghematan Biaya (TCO)**: Mengurangi kebutuhan kluster H100 dari 128 node menjadi hanya 36 node (penghematan $285.000/bulan atau ~67.8%).
- **P99 Tail Latency**: Turun dari $890\text{ ms}$ menjadi $185\text{ ms}$ pada beban puncak 45.000 QPS.
- **Tingkat Akurasi Regulasi (Hallucination Reduction)**: Kesalahan identifikasi token referensi transaksi turun drastis dari 4.8% ke 0.0001% berkat representasi SPLADE leksikal.

---

### 9. Trade-offs

| Pendekatan Arsitektur | Keunggulan Utama | Biaya / Beban Komputasi | Limitasi / Kerentanan | Rekomendasi Beban Kerja |
| :--- | :--- | :--- | :--- | :--- |
| **Monolithic Model Direct Query** | Arsitektur sederhana, tanpa dependensi multi-service, mudah di-debug. | VRAM maksimal, biaya token tertinggi, boros FLOPs untuk tugas sepele. | P99 latency fluktuatif, rawan token-length context OOM, skalabilitas buruk. | Prototipe, validasi fungsional awal, volume kueri rendah ($< 5\text{ QPS}$). |
| **Dense-Only Retrieval (Bi-Encoder)** | Kecepatan search sangat tinggi ($< 5\text{ ms}$), ukuran index vector di VRAM relatif efisien. | Butuh pembaruan model reguler (fine-tuning embedding) agar tetap akurat. | Sangat lemah pada *exact identifier matching* (SKU, Hash, Kode error mesin). | Aplikasi penelusuran umum, pencarian artikel berita, FAQ chatbot kasual. |
| **Dense + Sparse Hybrid (SPLADE)** | Menyeimbangkan semantik laten dengan pencarian leksikal presisi tinggi. | Komputasi embedding ganda (2 forward passes per kueri), ukuran indeks inverted bertambah. | Latensi komputasi token expansion pada sparse generator dapat menambah 10-15ms. | E-commerce e-catalog, pencarian rekam medis, sistem pencarian kode enterprise. |
| **Late Interaction (ColBERT)** | Akurasi mendekati full Cross-Encoder dengan throughput sebanding Bi-Encoder. | Indeks berukuran besar (menyimpan multi-vektor per token dokumen di disk/memory). | Membutuhkan custom operator MaxSim pada GPU agar latensi tidak bottleneck di CPU. | Retrieval Augmentation tingkat produksi dengan SLA presisi tinggi. |
| **Speculative Inference Cascading** | Peningkatan speedup decoding autoregresif 2x - 3x tanpa degradasi akurasi bobot target. | Alokasi VRAM ekstra untuk memuat dua model sekaligus (Draft + Target) pada memori GPU. | Jika draft model meleset (acceptance rate $< 40\%$), latensi justru lebih buruk dari non-speculative. | Batch inference throughput tinggi, automated document generation, complex coding agent. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Token Padding Explosion pada Dynamic Micro-Batching
- **Penyebab**: Mengirim kueri bervariasi panjang (misal: 32 token digabung dengan 4096 token) dalam satu batch ke GPU tanpa dynamic padding atau paged attention tensor. Tensor di-pad dengan nol hingga batas 4096 token, menyia-nyiakan komputasi Tensor Core hingga 85%.
- **Troubleshooting & Solusi**: Terapkan *PagedAttention* (seperti pada vLLM) atau aktifkan *ragged tensors* (Triton / TensorRT-LLM `remove_input_padding=True`). Ini mengeliminasi komputasi useless padding tokens secara tuntas.

#### Kesalahan 2: MaxSim Execution Bottleneck pada Late-Interaction Reranking
- **Penyebab**: Melakukan loop iteratif perhitungan dot-product token kueri terhadap ratusan dokumen menggunakan numpy array atau nested loop di level CPU Python. Latensi melonjak dari $10\text{ ms}$ menjadi $> 600\text{ ms}$.
- **Troubleshooting & Solusi**: Matrikskan seluruh representasi dokumen kandidat menjadi 3D Tensor `(Batch, Max_Doc_Tokens, Dim)`. Eksekusi kalkulasi kesamaan menggunakan batched matrix multiplication (`torch.bmm`) langsung pada CUDA stream yang sama dengan embedding engine.

#### Kesalahan 3: Speculative Decoding Negative Yield (Degradasi Kecepatan)
- **Penyebab**: Menggunakan Draft Model dari keluarga arsitektur atau tokenizer yang berbeda tanpa adapter alignment tokenisasi yang memadai, atau domain teks di luar jangkauan representasi draft model, menyebabkan rasio penerimaan token drop di bawah 30%.
- **Troubleshooting & Solusi**: Monitor metrik `spec_acceptance_rate`. Jika rata-rata penerimaan $< 50\%$, lakukan *fallback dinamis* ke pure autoregressive generation. Pastikan Draft Model dan Target Model berbagi kosa kata tokenizer yang 100% identik.

#### Kesalahan 4: CUDA Out-Of-Memory (OOM) Akibat Unbounded KV-Cache Growth
- **Penyebab**: Tidak membatasi alokasi VRAM untuk KV-cache pool saat concurrent streams meningkat drastis, memicu crash instan fatal pada level driver NVIDIA.
- **Troubleshooting & Solusi**: Kunci limitasi alokasi memori KV-cache secara eksplisit (misal: `gpu_memory_utilization=0.90` pada vLLM). Terapkan *chunked prefill* dan *sliding window attention* untuk membatasi jejak jejak memory pada context window yang ekstrim.

---

### 11. Best Practices (Production Checklist)

Berikut adalah checklist audit kesiapan produksi sebelum mendeploy Compound Inference Pipeline ke kluster live:

- [ ] **Model Serving Optimization**:
  - [ ] Model embedding (Dense & Sparse) telah dikonversi ke engine TensorRT / ONNX Runtime Execution Provider dengan optimasi FP16/INT8.
  - [ ] LLM Engine menggunakan *PagedAttention v2* atau arsitektur memory chunking non-kontigu.
  - [ ] KV-Cache diatur dengan presisi FP8 / INT8 kuantisasi untuk menghemat hingga 50% VRAM per context stream tanpa degradasi generasi.
- [ ] **Pipeline Concurrency & Asynchronous Flow**:
  - [ ] Pipeline routing dan aggregation dieksekusi 100% asynchronous (tidak ada fungsi synchronous blocking seperti `requests.post` atau CPU-bound serialization di event loop utama).
  - [ ] Menggunakan connection pooling HTTP/2 atau gRPC persistent channels ke Triton / vLLM backends.
- [ ] **Resilience & Fault Tolerance**:
  - [ ] Circuit breaker terpasang di setiap downstream node (Embedding, Vector DB, Speculative LLM).
  - [ ] Graceful degradation path terkonfigurasi: jika sistem reranking timeout ($> 30\text{ ms}$), fallback otomatis ke top-k hasil RRF langsung.
  - [ ] Semantic Cache terdistribusi terlindungi dari *cache-stampede* dengan menerapkan *single-flight locking* (mutex) saat mengkomputasi cache miss.
- [ ] **Observability & Health Checks**:
  - [ ] Metrics diekspos dalam format Prometheus:
    - `inference_ttft_seconds` (Time-to-First-Token histogram).
    - `inference_itl_seconds` (Inter-Token Latency histogram).
    - `speculative_draft_acceptance_ratio` (Gauge).
    - `semantic_cache_hit_ratio` (Gauge).
    - `gpu_vram_allocation_ratio` (Gauge).
  - [ ] Healthcheck endpoint (`/live`, `/ready`) memvalidasi respon internal CUDA IPC stream bukan sekadar mengecek proses aktif.

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan membangun compound inference server modular lengkap dengan semantic caching, hybrid scoring mock, dan speculative verifier.

#### Struktur Direktori Kerja:
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── embeddings.py
│   │   ├── reranker.py
│   │   └── generator.py
│   └── telemetry.py
└── test_load.py
```

#### Langkah 1: Siapkan Environment & Dependencies
Buat file `hands-on/m02/requirements.txt`:
```txt
fastapi==0.110.0
uvicorn[standard]==0.28.0
numpy==1.26.4
pydantic==2.6.4
prometheus-client==0.20.0
httpx==0.27.0
```

#### Langkah 2: Buat Implementasi Router & Logic Core
Buat file `hands-on/m02/app/config.py`:
```python
import os
from pydantic import BaseModel

class SystemConfig(BaseModel):
    app_port: int = int(os.getenv("APP_PORT", "8080"))
    cache_similarity_threshold: float = float(os.getenv("CACHE_THRESHOLD", "0.95"))
    speculative_acceptance_threshold: float = float(os.getenv("SPEC_ACCEPT_THRESHOLD", "0.75"))
    enable_metrics: bool = True

config = SystemConfig()
```

Buat file `hands-on/m02/app/telemetry.py`:
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "compound_requests_total",
    "Total kueri yang masuk ke sistem",
    ["route", "status"]
)

LATENCY_HISTOGRAM = Histogram(
    "compound_e2e_latency_seconds",
    "Distribusi latensi end-to-end",
    ["route"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
)
```

Buat file `hands-on/m02/app/engine/reranker.py`:
```python
import numpy as np

class TensorColBERTReranker:
    @staticmethod
    def compute_maxsim(query_tokens: np.ndarray, doc_tokens: np.ndarray) -> float:
        # Vectorized MaxSim logic
        sims = np.matmul(query_tokens, doc_tokens.T)
        return float(np.sum(np.max(sims, axis=1)))
```

Buat file `hands-on/m02/app/main.py`:
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time
import numpy as np
from app.config import config
from app.telemetry import REQUEST_COUNT, LATENCY_HISTOGRAM
from app.engine.reranker import TensorColBERTReranker

app = FastAPI(title="Compound Inference Engine Gateway", version="2.0.0")

class InferenceRequest(BaseModel):
    query_id: str
    prompt: str

class InferenceResponse(BaseModel):
    query_id: str
    status: str
    route: str
    generated_text: str
    latency_ms: float

# In-memory store untuk demonstrasi
LOCAL_CACHE = {}

@app.post("/v1/infer", response_model=InferenceResponse)
async def infer(request: InferenceRequest):
    t0 = time.monotonic()
    
    # 1. Routing & Cache Checking (Simulasi Vektor Cepat)
    # Hash sederhana untuk mendeteksi semantic cache hit
    pseudo_hash = hash(request.prompt) % 100
    if pseudo_hash in LOCAL_CACHE:
        lat = (time.monotonic() - t0) * 1000.0
        REQUEST_COUNT.labels(route="CACHE_HIT", status="SUCCESS").inc()
        LATENCY_HISTOGRAM.labels(route="CACHE_HIT").observe(lat / 1000.0)
        return InferenceResponse(
            query_id=request.query_id,
            status="SUCCESS",
            route="SEMANTIC_CACHE",
            generated_text=LOCAL_CACHE[pseudo_hash],
            latency_ms=lat
        )

    # 2. Execution of Mock Late-Interaction Scoring
    q_tokens = np.random.randn(8, 64).astype(np.float32)
    d_tokens = np.random.randn(32, 64).astype(np.float32)
    score = TensorColBERTReranker.compute_maxsim(q_tokens, d_tokens)

    # 3. Speculative Verification Output Construction
    output_str = f"Evaluated Context (MaxSim: {score:.2f}). Speculative Synthesis Valid."
    LOCAL_CACHE[pseudo_hash] = output_str

    lat = (time.monotonic() - t0) * 1000.0
    REQUEST_COUNT.labels(route="SPECULATIVE_CASCADE", status="SUCCESS").inc()
    LATENCY_HISTOGRAM.labels(route="SPECULATIVE_CASCADE").observe(lat / 1000.0)

    return InferenceResponse(
        query_id=request.query_id,
        status="SUCCESS",
        route="SPECULATIVE_CASCADE",
        generated_text=output_str,
        latency_ms=lat
    )

@app.get("/healthz")
async def healthz():
    return {"status": "HEALTHY", "engine_ready": True}
```

#### Langkah 3: Eksekusi dan Verifikasi Server
1. Jalankan aplikasi menggunakan Uvicorn:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
   ```
2. Buat file script verifikasi pengujian `test_load.py`:
   ```python
   import httpx
   import asyncio
   import time

   async def run_benchmark():
       url = "http://localhost:8080/v1/infer"
       async with httpx.AsyncClient() as client:
           # Request Pertama (Cold - Miss)
           res1 = await client.post(url, json={"query_id": "T-1", "prompt": "Status transaksi TX-9002"})
           print("Req 1 (Cold):", res1.json())

           # Request Kedua (Warm - Hit)
           res2 = await client.post(url, json={"query_id": "T-2", "prompt": "Status transaksi TX-9002"})
           print("Req 2 (Warm):", res2.json())

   if __name__ == "__main__":
       asyncio.run(run_benchmark())
   ```
3. Amati perbedaan latensi antara rute `SPECULATIVE_CASCADE` dan `SEMANTIC_CACHE`.

---

### 13. Exercise

#### Level 1 - Easy: Semantic Token Counter & Cache Expiry
- **Tugas**: Tambahkan mekanisme Time-To-Live (TTL) berbasis durasi absolut (misal: 60 detik) pada kelas `MockRedisSemanticCache` yang telah disediakan pada sub-bab 7.
- **Kriteria Evaluasi**: Kueri yang berulang setelah rentang waktu TTL harus menghasilkan Cache Miss dan memicu inferensi ulang.

#### Level 2 - Medium: Async Concurrent Hybrid Retrieval Fusion
- **Tugas**: Buat fungsi `async def execute_hybrid_search(query: str)` yang mengeksekusi Dense Retrieval dan Sparse Lexical Lookup secara simultan menggunakan `asyncio.gather()`. Terapkan kalkulasi bobot Reciprocal Rank Fusion (RRF) murni dengan $k=60$ untuk menggabungkan dua daftar kandidat terurut.
- **Kriteria Evaluasi**: Latensi penggabungan kedua retrieval tidak boleh melebihi $\max(\text{latensi dense}, \text{latensi sparse}) + 2\text{ ms}$.

#### Level 3 - Hard: CUDA Stream MaxSim Late-Interaction Optimizer
- **Tugas**: Tulis implementasi fungsi MaxSim berkinerja tinggi menggunakan PyTorch C++/CUDA extension atau PyTorch GPU tensor operations murni (`torch.bmm`, `torch.max`). Matriks dokumen harus diproses secara batched dengan ukuran `(B, D_tokens, Dim)` terhadap kueri `(B, Q_tokens, Dim)`.
- **Kriteria Evaluasi**: Benchmark harus mendemonstrasikan peningkatan kecepatan komputasi minimal $10\times$ lebih cepat dibanding eksekusi serial CPU numpy pada batch size 64 dan context length 256.

---

### 14. Challenge

#### Skenario:
Anda adalah Principal Inference Platform Architect di sebuah bank sentral. Anda ditugaskan membangun **Dynamic Speculative Gateway dengan Adaptive SLA Throttling** yang melayani puluhan institusi finansial dengan ketentuan ketat:
1. **Dynamic Target SLA**: Setiap tenant mengirimkan header `X-Target-Latency-Ms` (berkisar antara $50\text{ ms}$ hingga $500\text{ ms}$).
2. **Adaptive Pipeline Path**:
   - Jika SLA $\le 60\text{ ms}$, sistem dilarang menyentuh model 70B; sistem harus merutekan kueri ke SLM lokal INT4 dengan Dense Retrieval cepat (Top-1 doc).
   - Jika SLA $> 60\text{ ms}$, sistem harus menjalankan Dual Dense-Sparse Retrieval, Late Interaction MaxSim ColBERT reranking, dan Speculative Cascading (Draft 1.5B $\rightarrow$ Target 70B).
3. **No-Downtime Weight Swapping**: Sistem harus mampu mengganti bobot Draft Model dari *Qwen* ke *Llama* secara *hot-reload* tanpa memutus streaming token yang sedang aktif berjalan.
4. **Failure Injection Resiliency**: Simulasikan jika VRAM GPU Verifier melonjak hingga $98\%$, gateway harus secara elegan melakukan drop speculative confirmation dan mereduksi output ke mode *concise summary streaming* secara deterministik tanpa melempar HTTP 500 error ke klien.

*Buat dokumen spesifikasi desain arsitektur teknis, diagram aliran data state-machine, dan prototipe kode validasinya!*

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic
1. **Apa perbedaan mendasar antara model Cross-Encoder konvensional dan arsitektur Late-Interaction (ColBERT) dalam pemrosesan kueri dan dokumen?**
   - *Jawaban*: Cross-Encoder menggabungkan kueri dan dokumen menjadi satu urutan bersama pada layer self-attention ($O((L_q+L_d)^2)$), sehingga dokumen tidak dapat dipra-komputasi. ColBERT mengencode kueri dan dokumen secara terpisah menjadi matriks multi-vektor per-token, memungkinkan dokumen di-index offline dan dicocokkan pada waktu inferensi via operator MaxSim yang jauh lebih ringan.

2. **Mengapa kombinasi Dense Embedding dan Sparse Lexical Embedding (SPLADE) lebih unggul dibanding hanya mengandalkan Dense Embedding pada kasus kueri data inventaris pergudangan?**
   - *Jawaban*: Dense embedding memetakan teks ke representasi semantik kontinu yang rawan mengaburkan karakter presisi pada token langka. SPLADE menghasilkan representasi leksikal terbobot yang mempertahankan nilai token identik secara eksak (seperti nomor model, ID seri suku cadang, atau SKU unik), mencegah halusinasi kecocokan parsial semantik.

3. **Bagaimana algoritma Reciprocal Rank Fusion (RRF) menggabungkan dua set hasil retrieval yang memiliki skala skor penilaian berbeda?**
   - *Jawaban*: RRF tidak menggunakan nilai skor absolut similarity secara langsung, melainkan menggunakan posisi urutan/ranking dokumen dari masing-masing metode ($RRF\_Score = \sum \frac{1}{k + rank}$). Pendekatan ini membuat penggabungan invarian terhadap perbedaan distribusi skor metrik antar-model (misal cosine similarity vs dot-product sparse).

4. **Apa yang dimaksud dengan rasio penerimaan token (*acceptance rate*) dalam arsitektur Speculative Decoding?**
   - *Jawaban*: Rasio persentase token kandidat yang diajukan oleh Draft Model yang berhasil lolos kriteria verifikasi kesesuaian distribusi probabilitas pada forward pass tunggal Target Verifier Model.

5. **Apa fungsi utama dari mekanisme Circuit Breaker dalam compound pipeline inference engine?**
   - *Jawaban*: Menghentikan sementara pengiriman request ke downstream service yang mengalami kegagalan/timeout secara berulang (membuka circuit), mencegah antrean request menumpuk yang dapat memicu degradasi total (*cascading failure*), dan mengalihkan alur eksekusi ke jalur degradasi yang aman (*fallback*).

#### B. Pertanyaan Intermediate
6. **Kapan teknik Speculative Decoding justru memperburuk throughput dan menaikkan latensi generasi token dibanding inferensi standar?**
   - *Jawaban*: Ketika rasio penerimaan (*acceptance rate*) draft model anjlok (biasanya $< 40-50\%$). Pada kondisi ini, waktu yang dihabiskan untuk komputasi autoregresif pada draft model menjadi *overhead* komputasi terbuang, sementara target verifier model tetap harus melakukan forward pass dan mengoreksi token secara berulang.

7. **Bagaimana paged-attention memitigasi fragmentasi memori VRAM pada compound inference system skala besar?**
   - *Jawaban*: Paged-attention memecah penyimpanan KV-cache ke dalam blok-blok memori non-kontigu (mirip paging pada OS virtual memory). Hal ini mengeliminasi kebutuhan alokasi buffer kontigu maksimum di muka yang memicu fragmentasi eksternal, sehingga utilisasi VRAM dapat ditekan mendekati $95\%$ kapasitas efektif.

8. **Mengapa ambang batas (threshold) Semantic Cache harus diatur sangat tinggi ($\ge 0.95$ Cosine Sim)?**
   - *Jawaban*: Perbedaan kecil pada sudut ruang vektor laten dapat merepresentasikan negasi faktual atau perbedaan entitas kritis (misal: "Transfer 10 juta ke Akun A" vs "Transfer 10 juta ke Akun B"). Ambang batas yang longgar ($< 0.90$) memicu risiko fatal berupa penyajian respon lama yang keliru (*false semantic equivalence*).

9. **Apa implikasi performa dari pemisahan tahap Prefill Engine dan Decode Engine pada kluster inferensi heterogen?**
   - *Jawaban*: Tahap Prefill bersifat *compute-bound* (memproses context prompt panjang secara paralel dengan efisiensi tinggi pada Tensor Core), sedangkan Decode bersifat *memory-bandwidth-bound* (generasi token satu per satu). Memisahkan keduanya ke node terisolasi mencegah proses Decode yang sensitif latensi terhambat oleh proses Prefill kueri baru berukuran masif.

10. **Bagaimana cara kerja penalti redundansi token pada Late-Interaction ColBERT reranker?**
    - *Jawaban*: Operator MaxSim mengambil nilai keselarasan maksimum dokumen untuk tiap token kueri. Jika sebuah dokumen mengulang token kata kunci yang sama berkali-kali, skor MaxSim tidak bertambah secara linier karena hanya nilai koneksi tertinggi yang dipertahankan ($\max$), mencegah teknik eksploitasi *keyword-stuffing*.

#### C. Skenario Kasus Produksi
11. **Skenario 1 - Cold Start Latency Spike**:
    *Pada peluncuran kluster inference baru berbasis TensorRT-LLM, request pertama pada setiap instance selalu mengalami latensi hingga 8 detik, memicu timeout pada API Gateway. Bagaimana arsitektur compound inference mengatasi masalah ini secara sistematis?*
    - *Solusi & Analisis*: Latensi disebabkan oleh alokasi memori internal CUDA context, inisialisasi Paged KV-Cache allocator, dan kompilasi kernel JIT. Solusinya adalah menerapkan *Warmup Lifecycle Probe*: sebelum pod dihubungkan ke load balancer Kubernetes (`ReadinessProbe`), worker mengirimkan request sintetis dengan urutan token bervariasi untuk menginisialisasi buffer memori, mengisi VRAM page pools, dan memicu eksekusi kernel CUDA awal hingga stabil.

12. **Skenario 2 - Memory Leak Silent Crash**:
    *Sebuah compound pipeline hybrid dense-sparse mengalami crash OOM mendadak setiap ~6 jam, meskipun metrik rata-rata volume QPS terpantau datar. Log GPU menunjukkan alokasi PyTorch tensor pada sub-modul reranking terus bertambah. Apa akar masalahnya dan bagaimana perbaikan kodenya?*
    - *Solusi & Analisis*: Terjadi akumulasi *Computation Graph* atau penumpukan referensi objek Tensor pada scope global/asinkron. Seringkali disebabkan lupa memanggil context manager `torch.inference_mode()` atau `torch.no_grad()`, atau menyimpan output tensor ke dalam list global tanpa memanggil `.detach().cpu()` / `.item()`, yang mengunci buffer VRAM dari mekanisme garbage collection.

13. **Skenario 3 - Cascading Degradation Under DDoS-like Flash Crowd**:
    *Trafik kueri melonjak mendadak $10\times$ lipat. Vector database mengalami lonjakan latensi hingga $500\text{ ms}$, yang menyebabkan antrean request pada Inference Engine menumpuk dan memicu habisnya VRAM (OOM) akibat KV-Cache context buffer kueri antrean menumpuk bersamaan. Rancang mitigasi arsitekturalnya!*
    - *Solusi & Analisis*:
      1. Terapkan *Admission Control & Shedding* di API gateway: tolak request non-prioritas dengan HTTP 429 atau degradasi otomatis ke respon statis.
      2. Aktifkan *Circuit Breaker* pada layer Vector DB: potong tahap reranking mendalam dan alihkan kueri ke in-memory lightweight index.
      3. Atur *Max Concurrency Queue Limit* pada inference engine vLLM/Triton: batasi jumlah active prefill/decode context yang boleh dialokasikan secara simultan di VRAM; request yang melebihi batas antrean ditolak dengan cepat (*fail-fast*) daripada ditampung hingga memicu crash sistem fatal.

---

### 16. Summary

Compound Inference Pipelines merevolusi cara perekayasa perangkat lunak mengimplementasikan model kecerdasan buatan dalam skala produksi. Alih-alih memperlakukan LLM sebagai kotak monolitik serba-bisa yang lambat dan boros biaya, arsitektur compound mengurai proses inferensi ke dalam lapisan komponen terkoordinasi:

1. **Routing & Caching Semantik Dinamis**: Memisahkan kueri deterministik cepat dari kueri penalaran berat, menurunkan latensi P99 hingga fraksi milidetik pada beban kerja berulang.
2. **Representasi Bertingkat (Hybrid Dense + Sparse & Late Interaction)**: Mengatasi keterbatasan Information Retrieval klasik dengan menyatukan keunggulan pemetaan semantik laten BGE-M3, ketepatan leksikal eksak SPLADE, dan ketajaman pencocokan matriks token ColBERT MaxSim.
3. **Speculative Decoding & Cascading**: Memaksimalkan throughput pemrosesan token per detik melalui simbiosis model draft berbobot ringan dan target verifier berparameter masif.
4. **Ketahanan Tingkat Sistem**: Memisahkan antrean komputasi CPU/GPU, mengisolasi memory space KV-Cache via paged allocation, serta membentengi pipeline dengan Circuit Breaker dan graceful degradation path demi menjamin ketersediaan layanan $99.99\%$ di lingkungan produksi enterprise.