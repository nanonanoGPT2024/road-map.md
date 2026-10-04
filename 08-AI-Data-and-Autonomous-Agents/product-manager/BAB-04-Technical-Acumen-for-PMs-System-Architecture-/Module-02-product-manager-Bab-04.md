# BAB 04: Technical Acumen for PMs - System Architecture
## Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (AI, Data, and Autonomous Agents)

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Technical Product Manager (TPM) dan AI Product Manager (AI PM) diharapkan mampu:
1. **Merancang & Mengevaluasi Arsitektur Produksi AI**: Mengaudit arsitektur sistem berbasis *Generative AI*, *Autonomous Agents*, dan *Data Streaming* skala enterprise untuk mendeteksi *single point of failure* (SPOF), *bottleneck* latensi, dan *token cost runaway*.
2. **Menetapkan Service Level Objectives (SLO) & Budgets**: Menghitung dan menetapkan SLA/SLO teknis (Time to First Token/TTFT, Tokens Per Second/TPS, P99 Latency, End-to-End Latency) serta *cost budget* per *inference transaction*.
3. **Mengorkestrasi Komponen Enterprise AI**: Mengintegrasikan *Semantic Caching*, *Advanced RAG* (Hybrid Search + Cross-Encoder Reranking), *Autonomous Agent Loop* (ReAct/Plan-and-Solve), dan *Guardrails* dalam alur data asinkron berbasis *event-driven*.
4. **Memitigasi Resiko Produksi**: Mengidentifikasi trade-off arsitektural (*latency vs accuracy vs cost*) dan mengeksekusi *runbook* mitigasi ketika terjadi *agentic infinite loop*, *semantic drift*, atau kegagalan *downstream tool*.

---

### 2. Prerequisite

Untuk menyerap materi ini secara optimal, peserta diharapkan telah memiliki pemahaman:
*   **Fundamental Distributed Systems**: Konsep API Gateway, Microservices, Asynchronous Message Broker (Apache Kafka/RabbitMQ), dan State Stores (Redis, PostgreSQL).
*   **AI/LLM Primitives**: Tokenisasi, *context window limits*, embedding vectors, cara kerja dasar Dense Retrieval (*Cosine Similarity*, HNSW index).
*   **Metrik Rekayasa Software**: Latensi P50/P90/P99, throughput (RPS), ketersediaan (*nines* of availability), dan struktur biaya komputasi *cloud* (I/O, GPU compute hours).
*   **Python & Async I/O**: Pemahaman membaca kode Python modern berorientasi `asyncio` dan arsitektur REST/gRPC.

---

### 3. Concept & Internal Architecture (Mendalam)

Membawa sistem AI dari tahap *Proof of Concept* (PoC) berbasis notebook ke sistem produksi berskala jutaan pengguna memerlukan arsitektur yang mengisolasi sifat non-deterministik LLM dari sistem inti transaksi bisnis (*core system of record*).

Arsitektur produksi AI modern mengadopsi pola **Decoupled Agentic Pipeline** yang terdiri dari lapisan-lapisan kritis:

```
[Client App] 
      │ (HTTPS/WSS)
      ▼
[API Gateway / Ingress Layer] ── (Rate Limiting, Auth, Tenant Routing)
      │
      ▼
[Semantic Gateway & Guardrails] ── (PII Masking, Prompt Injection Check, NeMo Guardrails)
      │
      ├── (Cache Hit) ──► [Semantic Cache: Redis Vector Engine] (Returns Instant Response)
      │
      ▼ (Cache Miss)
[Agent Orchestration Layer] ── (State Machine: LangGraph/Temporal, Context Window Engine)
      │
      ├──────► [Retrieval Engine] ──► [Vector DB: Milvus/Qdrant + BM25 Elasticsearch]
      │               │
      │               ▼
      │        [Cross-Encoder Reranker: Cohere/BGE]
      │
      ├──────► [Deterministic Tools] ──► [Internal Microservices / SQL via gRPC]
      │
      ▼
[Model Serving Layer] ── (vLLM / TensorRT-LLM Cluster on Kubernetes)
      │
      ▼
[Output Guardrails & Streaming Formatter] ──► [Client App (SSE Output)]
      │
      ▼ (Async Event Bus: Kafka)
[Observability & Telemetry] ──► [OpenTelemetry -> Langfuse/Arize Phoenix + Datadog]
```

#### Komponen Internal Kritis

1. **Semantic Gateway & Guardrails Layer**:
   * Bertindak sebagai *firewall* pertama. Melakukan sanitasi input, evaluasi *toxicity*, deteksi injeksi *prompt*, dan pengecekan PII (*Personally Identifiable Information*).
   * **Semantic Caching**: Membandingkan kemiripan vektor embedding dari *incoming query* terhadap *cache database*. Jika *similarity distance* $< \epsilon$ (misal: Cosine Distance $\le 0.08$), respons langsung dikembalikan dari cache tanpa menyentuh model, memangkas latensi dari $\sim 2500\text{ms}$ ke $< 30\text{ms}$ dan menghemat biaya token $100\%$.

2. **Agent Orchestrator & State Manager**:
   * Menghilangkan sifat *stateless* LLM dengan mengelola *Memory Buffer*, *Scratchpad*, dan eksekusi bertahap (*multi-turn reasoning*).
   * Menggunakan arsitektur *Directed Acyclic Graph* (DAG) atau *State Machine* (seperti Temporal atau LangGraph) untuk menjamin persistensi status agen. Jika terjadi *network drop* pada sub-task, agen dapat me-*resume* status tanpa mengulang *inference* dari awal.

3. **Hybrid Retrieval & Reranking Subsystem**:
   * **Dense Retrieval (Vector)**: Menangkap kemiripan semantik (*semantic similarity*), tetapi buruk pada istilah unik/kode produk (*exact keywords*).
   * **Sparse Retrieval (BM25)**: Menangkap *exact lexical match*.
   * **Reciprocal Rank Fusion (RRF) & Cross-Encoder Reranker**: Menggabungkan hasil Dense dan Sparse, lalu melakukan *re-scoring* mendalam terhadap 20-50 dokumen teratas guna memastikan dokumen yang masuk ke *prompt context window* memiliki relevansi absolut tertinggi, menghindari fenomena *Lost in the Middle*.

4. **Model Serving & Dynamic Batching Layer**:
   * Infrastruktur hosting mandiri (*self-hosted*) menggunakan *engine* performa tinggi (vLLM, TensorRT-LLM) dengan teknik *PagedAttention*.
   * Mengurangi fragmentasi memori GPU dari alokasi KV-Cache dan mendukung *Continuous Batching*, melipatgandakan throughput (TPS) dibanding *naive serving*.

---

### 4. Why & What

| Dimensi | Pendekatan Prototipe / PoC | Pendekatan Enterprise Production |
| :--- | :--- | :--- |
| **Pola Konsumsi LLM** | Direct synchronous call ke penyedia SaaS publik (OpenAI/Anthropic). | Dynamic Gateway: Routing adaptif berdasarkan biaya, kuota, ketersediaan, fallback multi-provider, & local LLM engine. |
| **Penanganan State** | Simpan seluruh riwayat chat di *in-memory array* lokal. | External state store (Redis/DynamoDB) terdistribusi dengan sliding window, summarization background worker, & cold storage. |
| **Strategi Retrieval** | Naive Vector Search (Top-K Cosine Similarity dari satu Vector DB). | Hybrid Retrieval (Dense Vector + BM25 Fulltext) + Reranking Model + Metadata Filtering terisolasi multi-tenant. |
| **Latensi & Kecepatan** | Mengabaikan P99, streaming sering kali tidak diimplementasi secara optimal. | Strict SLO (TTFT < 800ms, Server-Sent Events, P99 Token Generation > 35 tokens/sec). |
| **Mitigasi Biaya** | Tagihan *pay-as-you-go* tanpa pembatas granular. | Dynamic semantic cache, token pruning, dynamic model routing (Small Model untuk kueri sederhana, Large Model untuk penalaran kompleks). |
| **Evaluasi Kualitas** | Uji coba manual "Vibe Check" oleh developer. | Automated Continuous Evaluation Pipelines (RAG Triad: Context Relevance, Groundedness, Answer Relevance) via LLM-as-a-judge. |

---

### 5. How (Workflow Detail)

Berikut alur eksekusi kueri terisolasi dalam *Agentic Production System*:

```
[1. User Request]
        │
        ▼
[2. Token Auth & Rate Limiter] ── (429 Too Many Requests jika melanggar quota)
        │
        ▼
[3. Input Guardrail: PII & Injection Scan] ── (Drop request / Sanitize jika terdeteksi berbahaya)
        │
        ▼
[4. Query Embedder] ──► Ubah text menjadi Dense Vector
        │
        ▼
[5. Semantic Cache Lookup (Redis)]
        ├── If Similarity >= 0.95 ──► Return Cached Payload [STOP PIPELINE]
        └── If Similarity < 0.95  ──► Lanjutkan ke Langkah 6
                    │
                    ▼
[6. Intent Classifier & Agent Router]
        ├── Path A: Direct Execution (Chat sederhana -> Langsung ke Model Gateway)
        ├── Path B: RAG Path (Query Butuh Dokumen Enterprise)
        │       ├── Step B1: Concurrent Hybrid Search (Vector DB + Sparse Search)
        │       ├── Step B2: Reciprocal Rank Fusion (RRF)
        │       ├── Step B3: Cross-Encoder Context Reranking
        │       └── Step B4: Context Pruning & Window Injection
        └── Path C: Agentic Multi-Step (Complex Task / Transactional Action)
                ├── Loop Cycle: Thought -> Action Execution (API/DB Call) -> Observation
                └── Circuit Breaker Check (Max 5 Iterations / Timeout 15s)
                    │
                    ▼
[7. Dynamic Inference Engine (vLLM Cluster / Tiered SaaS API)]
        │ (Server-Sent Events / Streaming Token Chunk)
        ▼
[8. Real-time Output Guardrail] ── (Halt stream jika terdeteksi halusinasi destruktif / kebocoran data)
        │
        ▼
[9. Asynchronous Telemetry Delivery via Kafka]
        ├── OpenTelemetry -> Tracing Graph (Span LLM, Span Retrieval, Span Tool)
        ├── Cost Engine -> Agregasi biaya token per user/tenant
        └── Semantic Cache Writer -> Simpan respon baru untuk kueri berikutnya
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan arsitektur ini seperti **Restoran Fine Dining Bintang Lima**:
* **API Gateway & Guardrail** adalah *Front Desk & Security Guard*: Memeriksa identitas pengunjung, memastikan tidak ada senjata atau zat berbahaya yang masuk (Prompt Injection/PII).
* **Semantic Cache** adalah *Penyimpanan Hidangan Populer*: Jika ada pesanan minuman standar yang sama persis seperti 2 menit lalu, staf langsung menyajikannya dari konter tanpa merepotkan dapur.
* **Agent Orchestrator** adalah *Head Chef (Maître d')*: Membaca pesanan, memecahnya menjadi langkah kerja, mendelegasikan tugas ke stasiun-stasiun pemrosesan, dan memvalidasi hasil sebelum disajikan.
* **Retrieval Engine (RAG)** adalah *Pantry & Bahan Baku*: Menyediakan arsip resep eksklusif dan bahan spesifik yang tidak dihafal di luar kepala oleh koki.
* **Model Serving (vLLM)** adalah *Jajaran Line Cook dengan Wajan Khusus*: Mengolah instruksi bahan baku menjadi sajian final dengan kecepatan konsisten.
* **Observability (Tracing)** adalah *Food Inspector & Quality Auditor*: Mencatat suhu masakan, waktu penyajian setiap piring, dan biaya bahan baku per porsi secara *real-time*.

#### Detail Interaksi Komponen

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 ENTERPRISE RUNTIME                     │
                  └────────────────────────────────────────────────────────┘

 [HTTP POST /v1/agent/query]
           │
           ▼
 ┌───────────────────┐      Cache Hit (Dist <= 0.08)
 │   API Gateway     │──────────────────────────────────────────┐
 │  & Guardrails     │                                          │
 └─────────┬─────────┘                                          │
           │ Cache Miss                                         │
           ▼                                                    │
 ┌───────────────────┐       Query Docs       ┌──────────────┐  │
 │ Agent Orchestrator│───────────────────────►│  Hybrid RAG  │  │
 │ (Execution Graph) │◄───────────────────────│  Subsystem   │  │
 └─────────┬─────────┘      Reranked Docs     └──────────────┘  │
           │                                                    │
           ├────────────────────────┐                           │
           │ Plan Tools             │ Tool Call Execution       │
           ▼                        ▼                           │
 ┌───────────────────┐    ┌───────────────────┐                 │
 │ Model Inference   │    │ Enterprise Core   │                 │
 │ (vLLM Instance)   │    │ (Microservices)   │                 │
 └─────────┬─────────┘    └─────────┬─────────┘                 │
           │ Token Stream           │ Output State              │
           └────────────┬───────────┘                           │
                        │                                       │
                        ▼                                       │
           ┌────────────────────────┐                           │
           │ Output Stream Sanitizer│◄──────────────────────────┘
           └────────────┬───────────┘
                        │
                        ├──────────────────────────┐
                        │ (Server-Sent Events)     │ (Async Telemetry)
                        ▼                          ▼
               [Client Application]       [Kafka -> Langfuse/Otel]
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Semantic Caching Implementation (Dasar)
Skrip mandiri menggunakan Redis untuk melakukan evaluasi *Cosine Distance* kueri pengguna:

```python
import numpy as np

class SimpleSemanticCache:
    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        # In-memory storage: list of tuples (embedding_vector, response_text)
        self.cache_store = []

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def lookup(self, query_vector: np.ndarray):
        best_score = -1.0
        best_response = None
        for cached_vector, response in self.cache_store:
            score = self._cosine_similarity(query_vector, cached_vector)
            if score > best_score:
                best_score = score
                best_response = response
        
        if best_score >= self.threshold:
            return {"hit": True, "score": best_score, "response": best_response}
        return {"hit": False, "score": best_score, "response": None}

    def write(self, query_vector: np.ndarray, response: str):
        self.cache_store.append((query_vector, response))

# Simulasi Eksekusi
cache = SimpleSemanticCache(threshold=0.90)
v_registered = np.array([0.15, 0.85, 0.40])
cache.write(v_registered, "Kebijakan refund: 30 hari kalender dengan bukti pembelian.")

# Kueri baru dengan variasi semantik tipis
v_incoming = np.array([0.16, 0.84, 0.39])
result = cache.lookup(v_incoming)
print(f"Cache Hit: {result['hit']}, Similarity Score: {result['score']:.4f}")
print(f"Returned Data: {result['response']}")
```

#### B. Practical Example: Enterprise Agent Endpoint Production-Grade
Implementasi FastAPI tingkat produksi menggunakan arsitektur non-blocking, terintegrasi dengan Circuit Breaker, Observability Context Tracing, Retrieval Augmented Generation, dan LLM Tool-Calling.

```python
import asyncio
import time
import logging
from typing import List, Dict, Any, AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnterpriseAIEngine")

app = FastAPI(title="Production Enterprise AI Agent Gateway", version="2.4.0")

# --- Schemas ---
class AgentRequest(BaseModel):
    user_id: str = Field(..., example="usr_corp_9941")
    session_id: str = Field(..., example="ses_alpha_123")
    query: str = Field(..., min_length=2, max_length=2000, example="Tampilkan laporan mutasi saldo Q3 untuk tenant retail")

class ExecutionMetadata(BaseModel):
    latency_ms: float
    token_usage: Dict[str, int]
    cache_hit: bool
    routed_model: str

# --- Core Systems (Stubbed out to illustrate enterprise architecture) ---
class GuardrailViolationException(Exception):
    pass

class ProductionTelemetry:
    @staticmethod
    async def log_trace(event_type: str, session_id: str, data: Dict[str, Any]):
        # Mensimulasikan pengiriman OpenTelemetry trace ke Message Bus (e.g. Kafka)
        await asyncio.sleep(0.001) 
        logger.info(f"[TRACE] {event_type} | Session: {session_id} | Data: {data}")

class HybridRetriever:
    @staticmethod
    async def fetch_relevant_context(query: str, tenant_id: str) -> List[str]:
        # Melakukan sparse + dense search paralel dan reranking
        await asyncio.sleep(0.045)  # Budget: 45ms P99
        return [
            "Data Q3 Retail: Penjualan kotor naik 12% YoY.",
            "Rekonsiliasi mutasi akun retail selesai pada 30 September."
        ]

class ResilienceCircuitBreaker:
    failure_count = 0
    MAX_FAILURES = 3

    @classmethod
    def record_failure(cls):
        cls.failure_count += 1

    @classmethod
    def is_open(cls) -> bool:
        return cls.failure_count >= cls.MAX_FAILURES

    @classmethod
    def reset(cls):
        cls.failure_count = 0

# --- Enterprise Orchestrator Core ---
async def verify_guardrails(prompt: str) -> None:
    # Memeriksa Prompt Injection & PII
    injection_signatures = ["ignore previous instructions", "system override", "reveal api key"]
    if any(sig in prompt.lower() for sig in injection_signatures):
        raise GuardrailViolationException("Input violates safety guidelines: Prompt injection detected.")

async def stream_generator(query: str, context: List[str], session_id: str) -> AsyncGenerator[str, None]:
    start_time = time.perf_counter()
    tokens_generated = 0

    try:
        # Simulasi Streaming Chunk Output dari vLLM Inference Engine
        prefix_meta = f"data: [METADATA] context_docs={len(context)}\n\n"
        yield prefix_meta

        simulated_response = (
            f"Analisis berdasarkan sistem inti: Mutasi saldo Q3 untuk unit retail telah tervalidasi. "
            f"Faktor penentu: {context[0]} serta {context[1]}"
        ).split(" ")

        for word in simulated_response:
            if ResilienceCircuitBreaker.is_open():
                yield "data: [CIRCUIT BREAKER ACTIVATED: Failover to Fallback System]\n\n"
                break
            
            await asyncio.sleep(0.02)  # 50 tokens per second pace
            tokens_generated += 1
            yield f"data: {word} \n\n"

        latency_total = (time.perf_counter() - start_time) * 1000
        
        # Async non-blocking metric emission
        asyncio.create_task(ProductionTelemetry.log_trace(
            event_type="agent_inference_complete",
            session_id=session_id,
            data={"latency_ms": latency_total, "tokens": tokens_generated}
        ))
        
        yield "data: [DONE]\n\n"

    except Exception as e:
        ResilienceCircuitBreaker.record_failure()
        logger.error(f"Inference failure: {str(e)}")
        yield f"data: [ERROR] Processing interrupted: {str(e)}\n\n"

@app.post("/v1/agent/chat/stream")
async def execute_agent_chat(payload: AgentRequest):
    req_start = time.perf_counter()

    # Step 1: Input Guardrails Scan
    try:
        await verify_guardrails(payload.query)
    except GuardrailViolationException as gv:
        logger.warning(f"Security Alert: {str(gv)} for User {payload.user_id}")
        raise HTTPException(status_code=400, detail=str(gv))

    # Step 2: Context Retrieval Pipeline
    try:
        docs = await HybridRetriever.fetch_relevant_context(payload.query, tenant_id=payload.user_id)
    except Exception as e:
        logger.error(f"Retrieval error: {str(e)}")
        docs = []

    # Step 3: Stream from Model Serving Engine
    return StreamingResponse(
        stream_generator(payload.query, docs, payload.session_id),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Kasus: Arsitektur Financial Advisory Agentic System di Global Tier-1 Bank

*   **Latar Belakang**: Bank komersial multinasional meluncurkan agen otomatisasi penasihat keuangan nasabah korporat (*Wealth Management Copilot*). Sistem harus memproses analisa portofolio, kepatuhan OJK/regulasi regional, dan penarikan laporan *real-time* via SAP/Oracle ERP.
*   **Kondisi Awal (PoC Architecture)**:
    *   Penggunaan langsung LLM SaaS komersial via REST API.
    *   *Single vector store* tanpa pemisahan multi-tenant.
    *   *Latency P99*: $8.4\text{ detik}$.
    *   *Monthly Run-rate Token*: $\$42,000$ untuk hanya 800 *relationship managers*.
    *   *Insiden*: Terjadi insiden kebocoran konteks antar-tenant pada minggu ketiga uji coba akibat ketiadaan isolasi *metadata filtering* di lapisan RAG.
*   **Arsitektur Produksi Skala Enterprise**:
    1.  **Dynamic Semantic Caching**: Menggunakan Redis Enterprise Vector Search dengan threshold Cosine Similarity $0.94$. Menyimpan lebih dari 120.000 kombinasi tanya-jawab kepatuhan dan definisi produk reguler. *Cache Hit Ratio*: $41\%$.
    2.  **Model Tiering & Dynamic Routing**:
        *   Model Klasifikasi Kecil (RoBERTa fine-tuned, di-host lokal): Mengklasifikasi *intent* dan *routing* ($<8\text{ms}$).
        *   Kueri Informatif Sederhana: Dialihkan ke model *open-weights* 8B parameter (vLLM cluster internal).
        *   Penalaran Portofolio Kompleks: Dialihkan ke Frontier Model (70B+ / Commercial API) via enkripsi token *ephemeral*.
    3.  **Strict Guardrails & Tool Sanitization Engine**: NeMo Guardrails terpasang sebelum dan sesudah inferensi model. Pemanggilan fungsi API perbankan mewajibkan skema *Structured JSON Output* dengan validasi Pydantic ketat. Kegagalan validasi skema 2 kali berturut-turut langsung memicu *fallback* ke antrian operasional manusia.
*   **Hasil Evaluasi**:
    *   *P99 Latency*: Turun drastis dari $8.4\text{ detik}$ ke $1.35\text{ detik}$.
    *   *Token Unit Cost*: Turun $68\%$ per sesi pengguna melalui semantic caching dan context pruning.
    *   *Zero Context Leakage*: Menjalankan isolasi *Namespace Partitioning* dan *Row-Level Security* (RLS) di level Vector DB.

---

### 9. Trade-offs

Sebagai TPM, Anda wajib menguasai matriks kompromi teknis-finansial berikut:

| Pilihan Arsitektural | Keuntungan (Pros) | Kerugian (Cons) | Dampak Metrik Finansial & Operasional |
| :--- | :--- | :--- | :--- |
| **Self-Hosted Engine (vLLM / Triton) vs Commercial API (Closed SaaS)** | Kontrol penuh atas residensi data (ISO 27001/SOC2), zero token-markup, determinisme latensi tanpa *rate limit throttle*. | Beban operasional maintenance cluster Kubernetes, penyediaan kartu grafis (GPU scarcity/CapEx tinggi), butuh tim MLOps internal. | Menguntungkan jika konsumsi $> 15\text{ juta token/hari}$; sangat boros untuk volume rendah karena biaya idle GPU ($4\times\text{H100} \approx \$10,000+/bulan$). |
| **Hybrid Retrieval vs Naive Vector Search** | Precision & Recall mendekati 95%, tahan terhadap salah tik (*typo*), menangani *exact Part Number* & semantik sekaligus. | Kompleksitas arsitektur ganda (butuh Vector DB + Inverted Index Elasticsearch/OpenSearch), *latency overhead* reranker ($+30-80\text{ms}$). | Latency meningkat $\sim 20\%$, tetapi *Hallucination Rate* akibat *bad retrieval* anjlok dari $18\%$ ke $< 2\%$. |
| **Autonomous Multi-Agent Loop vs Static Workflow DAG** | Fleksibel memecahkan masalah tak terduga (*open-ended exploration*), mampu *self-correcting* saat eksekusi tool gagal. | Berisiko *infinite reasoning loops*, *token consumption* eksponensial, nondeterministik, latensi P99 sulit dikendalikan. | Biaya per kueri sulit diprediksi ($0.001 - $0.50 per kueri). Memerlukan implementasi ketat *loop circuit breaker* (max iteration cap). |
| **Aggressive Semantic Caching vs Always Live Generation** | Latensi *sub-second* ($< 50\text{ms}$), penghematan biaya token hingga $50\%+$, beban model inference anjlok. | Risiko menyajikan *stale data* (data basi), kemungkinan *false positive match* (pertanyaan berbeda dijawab teks cache jika threshold longgar). | Memerlukan *invalidation strategy* rumit saat data knowledge base berubah secara dinamis. |

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan Umum TPM & Engineering:
1. **Context Window Stuffing**: Memasukkan 100 halaman PDF langsung ke context window LLM modern (128K/1M token) tanpa teknik chunking dan retrieval.
   * *Dampak*: Biaya token meledak, latensi TTFT membengkak ($>10\text{ detik}$), dan terjadi fenomena *Lost in the Middle* (LLM melupakan informasi yang berada di tengah teks panjang).
2. **Missing Token Budgets per Session**: Kegagalan membatasi kedalaman penalaran agen otonom.
   * *Dampak*: Satu sesi kueri nasabah yang *looping* menghabiskan kuota ratusan ribu token dalam hitungan detik.
3. **Mengabaikan Cold Start Latency pada Vector DB & Model Server**: Mengukur latensi saat beban statis tanpa mengantisipasi lonjakan beban (*spike*).
   * *Dampak*: Server vLLM kehabisan memori VRAM (*CUDA Out of Memory*) saat ada 50 *concurrent streaming requests*.

#### Troubleshooting Runbook

```
                  MASALAH: P99 Latency Melonjak (> 5000ms)
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       [Check Semantic Cache]                 [Check Model Serving]
                 │                                       │
     Cache Hit Ratio < 10%?                  Queue Size Model Server Naik?
     ├── YA:                                 ├── YA:
     │   * Cek embedding drift.              │   * Kebutuhan GPU autoscale.
     │   * Validasi threshold distance.       │   * Kurangi max context token.
     │   * Analisis perubahan intent user.   │   * Aktifkan chunked prefill di vLLM.
     └── TIDAK:                              └── TIDAK:
         Lanjut ke RAG pipeline...               Lanjut ke External Tools...
                 │                                       │
                 ▼                                       ▼
       [Check Reranker Latency]               [Check Tool API Timeout]
       Latensi Cross-Encoder > 150ms?         Tool Third-Party Hang / Hang HTTP?
       * Batasi Top-K kandidat dari 100        * Terapkan timeout ketat (e.g. 800ms).
         menjadi 25 dokumen saja.             * Aktifkan circuit breaker & fallback.
```

---

### 11. Best Practices (Production Checklist)

#### Pre-Production Architecture Review (Gatekeeper Checklist untuk PM):
* [ ] **SLA & Latency Budget**: Batasan TTFT ditentukan ($\le 800\text{ms}$) dan P99 total response generation disepakati ($\le 3500\text{ms}$).
* [ ] **Token Circuit Breaker**: Batas maksimal token per respons disetel (misal: max 1.000 output tokens) dan batas iterasi agen dibatasi (maksimal 4 siklus ReAct).
* [ ] **Data Isolation (Tenant Isolation)**: Penyimpanan vektor menyertakan `tenant_id` pada setiap *metadata payload* dan diproteksi dengan *hard-filter* saat eksekusi retrieval.
* [ ] **PII/Sanitization Layer**: Sistem terintegrasi dengan alat redaksi PII (*masking* data nomor kartu kredit, NIK, password) sebelum teks dikirimkan ke model eksternal.
* [ ] **Fallback Strategy**: Ketika provider model primer *downtime* (HTTP 5xx / 429), sistem otomatis *fallback* ke secondary provider atau mode terdegradasi (*canned responses*).
* [ ] **Continuous Telemetry (LLMOps)**: Pengumpulan data log untuk input prompt, context chunks, output generation, dan user feedback (thumbs up/down) terkirim secara *asynchronous* ke platform observabilitas tanpa memblokir *main thread*.
* [ ] **Evaluation Harness**: Memiliki data uji (*golden dataset*) minimal 200 skenario terotomatisasi yang dijalankan pada setiap pipeline CI/CD sebelum rilis versi sistem baru.

---

### 12. Hands-on Practice

Dalam praktikum ini, Anda akan menyiapkan lingkungan mini produksi berbasis Docker dan FastAPI yang mengimplementasikan **Semantic Caching Layer**, **Mock Inference Engine**, dan **Telemetry Tracing**.

#### Struktur Direktori: `hands-on/m02/`
```
hands-on/m02/
├── docker-compose.yml
├── requirements.txt
├── server.py
└── test_client.py
```

#### Langkah 1: Siapkan `hands-on/m02/requirements.txt`
```text
fastapi==0.110.0
uvicorn==0.28.0
redis==5.0.3
numpy==1.26.4
pydantic==2.6.4
requests==2.31.0
```

#### Langkah 2: Buat `hands-on/m02/docker-compose.yml`
```yaml
version: '3.8'

services:
  redis-stack:
    image: redis/redis-stack-server:latest
    container_name: m02-redis-vector
    ports:
      - "6379:6379"
    environment:
      - REDIS_ARGS=--save "" --appendonly no
```

#### Langkah 3: Buat `hands-on/m02/server.py`
```python
import time
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
import redis

app = FastAPI(title="M02 Production Gateway Prototype")
# Sambungkan ke Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=False)

class RequestPayload(BaseModel):
    query: str
    embedding: list[float]

# Cache Mock Engine
@app.post("/chat")
def handle_chat(payload: RequestPayload):
    t_start = time.perf_counter()
    query_vec = np.array(payload.embedding, dtype=np.float32)
    
    # 1. Pengecekan Cache sederhana di Redis
    cached_keys = r.keys("cache:*")
    for k in cached_keys:
        raw_data = r.hgetall(k)
        stored_vec = np.frombuffer(raw_data[b"vector"], dtype=np.float32)
        
        # Hitung cosine similarity
        sim = float(np.dot(query_vec, stored_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(stored_vec)))
        if sim >= 0.95:
            duration = (time.perf_counter() - t_start) * 1000
            return {
                "source": "semantic_cache",
                "response": raw_data[b"response"].decode("utf-8"),
                "similarity": sim,
                "latency_ms": round(duration, 2)
            }

    # 2. Cache Miss: Mock LLM Inference Latency
    time.sleep(1.2)  # Mensimulasikan TTFT model serving
    generated_text = f"Hasil analisis komprehensif untuk: '{payload.query}' [Token Output]"
    
    # Simpan ke cache
    cache_id = f"cache:{len(cached_keys) + 1}"
    r.hset(cache_id, mapping={
        "vector": query_vec.tobytes(),
        "response": generated_text,
        "query": payload.query
    })
    
    duration = (time.perf_counter() - t_start) * 1000
    return {
        "source": "model_inference",
        "response": generated_text,
        "similarity": 0.0,
        "latency_ms": round(duration, 2)
    }
```

#### Langkah 4: Jalankan dan Uji
1. Jalankan Redis: `docker compose up -d`
2. Pasang dependencies: `pip install -r requirements.txt`
3. Jalankan server: `uvicorn server:app --port 8080 --reload`
4. Buat dan jalankan file `hands-on/m02/test_client.py`:
```python
import requests

url = "http://localhost:8080/chat"

# Query 1: Cold Hit (Akan memakan waktu ~1200ms)
payload_1 = {
    "query": "Berapa biaya transaksi transfer valas?",
    "embedding": [0.21, 0.45, 0.88, 0.12]
}
res1 = requests.post(url, json=payload_1).json()
print("Req 1 (Cold):", res1)

# Query 2: Semantically Similar (Akan memakan waktu < 20ms - Cache Hit)
payload_2 = {
    "query": "Biaya kirim uang valuta asing?",
    "embedding": [0.215, 0.448, 0.881, 0.119] # Cosine similarity tinggi
}
res2 = requests.post(url, json=payload_2).json()
print("Req 2 (Warm Cache):", res2)
```

---

### 13. Exercise

#### Level: Easy
*   **Tugas**: Hitung *Cost Per Mille* (CPM - per seribu kueri) dari sistem chatbot customer care.
*   **Parameter**: Rata-rata per kueri: $1.200\text{ token input}$, $300\text{ token output}$. Harga model: Input $\$2.50\text{ / 1M token}$, Output $\$10.00\text{ / 1M token}$. *Semantic Cache Hit Ratio*: $30\%$. (Asumsikan biaya query cache = $\$0$).
*   **Kriteria Keberhasilan**: Temukan total biaya $1.000$ kueri nasabah secara akurat.

#### Level: Medium
*   **Tugas**: Konseptualisasikan *Fallback Architecture* untuk sistem *Agentic Data Extractor* perbankan jika Vector Database mengalami *outage* atau waktu respon $> 1.500\text{ms}$.
*   **Kriteria Keberhasilan**: Buat dokumen spesifikasi teknis ringkas (1 halaman) yang mencakup: Pola *Degraded Fallback*, penanganan respons ke *front-end*, serta skenario pengalihan ke pencarian *lexical baseline*.

#### Level: Hard
*   **Tugas**: Desain arsitektur *Context Management* untuk percakapan panjang (*Multi-turn Conversation*) yang telah melampaui $64.000\text{ token}$, di mana pengguna menanyakan ringkasan dari instruksi pada pesan pertama percakapan.
*   **Batasan**: Context window maksimal yang dialokasikan untuk memori adalah $8.000\text{ token}$ guna menekan biaya inferensi.
*   **Kriteria Keberhasilan**: Sertakan diagram alur, strategi ringkasan bertingkat (*hierarchical summarization*), dan teknik integrasi *external state store*.

---

### 14. Challenge

**Skenario Kasus Kompleks: Autonomous Multi-Tenant B2B Healthcare Claims Agent**

*   **Latar Belakang**: Anda memimpin produk AI untuk platform klaim asuransi kesehatan yang melayani 20 rumah sakit rekanan. Agen bertugas membaca dokumen rekam medis (PDF, scan gambar, teks), memverifikasi polis asuransi via API, dan memutuskan persetujuan klaim secara otomatis hingga batas limit Rp 50.000.000.
*   **Tantangan Arsitektural**:
    1.  **Regulasi Ketat**: Data rekam medis tidak boleh keluar dari region lokal (data kedaulatan/sovereignty) dan tidak boleh melintasi batasan data antar rumah sakit (pantangan kebocoran multi-tenant).
    2.  **Karakteristik Dokumen**: Format klaim sangat tidak terstruktur, sering kali terdapat catatan dokter bertulisan tangan, dan rentan manipulasi penipuan (*fraud*).
    3.  **Kendala Latensi & Biaya**: Pemrosesan klaim ditargetkan selesai dalam waktu $< 60\text{ detik}$, dengan batas biaya komputasi maksimal Rp 12.000 per berkas klaim.
*   **Tugas Anda (Tanpa Solusi Instan)**:
    Susun dokumen **Architecture Decision Record (ADR)** komprehensif yang menjabarkan:
    *   Topologi orkestrasi model (*local open-weights multimodal model* vs *private cloud deployment*).
    *   Mekanisme *sandboxing* eksekusi tool keputusan finansial.
    *   Desain *Human-in-the-loop (HITL)* gate: Kapan tepatnya sistem harus menghentikan eksekusi otomatis dan mengalihkan kasus ke verifikator manusia berdasarkan metrik *uncertainty/entropy score* LLM.
    *   Strategi *Data Audit Trail* yang tahan uji forensik jika terjadi tuntutan hukum malpraktik klaim asuransi.

---

### 15. Quiz Evaluasi Pemahaman

#### A. Pertanyaan Basic (Pilihan Ganda)
1. **Apa perbedaan mendasar antara Dense Retrieval dan Sparse Retrieval?**
   * A. Dense menggunakan keyword matching; Sparse menggunakan neural embedding.
   * B. Dense menangkap representasi semantik berbasis vektor kontinu; Sparse berfokus pada kecocokan leksikal/kata kunci spesifik seperti BM25.
   * C. Dense hanya untuk data teks; Sparse hanya untuk data gambar.
   * D. Dense berjalan di CPU; Sparse wajib dijalankan di GPU cluster.

2. **Apa yang diukur oleh metrik Time to First Token (TTFT)?**
   * A. Total waktu yang dihabiskan model untuk menghasilkan seluruh output teks.
   * B. Durasi waktu yang dibutuhkan dari saat request dikirim hingga karakter/token awal diterima oleh client.
   * C. Waktu komputasi yang dihabiskan untuk embedding dokumen di vector database.
   * D. Durasi loading checkpoint model dari NVMe storage ke GPU VRAM.

3. **Mengapa *Continuous Batching* pada engine seperti vLLM lebih unggul dibanding *Static Batching* konvensional?**
   * A. Karena tidak memerlukan GPU untuk inference.
   * B. Karena menggabungkan iterasi inferensi pada level token daripada menunggu seluruh kalimat dalam batch selesai, menghilangkan idle compute akibat panjang kalimat yang bervariasi.
   * C. Karena membatasi output hanya menjadi 10 token per detik.
   * D. Karena secara otomatis menerjemahkan prompt ke dalam representasi biner.

4. **Karakteristik kueri mana yang paling optimal ditangani oleh Semantic Cache?**
   * A. Kueri data saldo rekening real-time pengguna.
   * B. Pertanyaan dengan variasi kalimat berbeda namun merujuk pada FAQ kebijakan statis yang sama.
   * C. Perintah eksekusi transfer dana antar rekening bank.
   * D. Instruksi pembuatan kode program unik yang tidak pernah ditanyakan sebelumnya.

5. **Apa fungsi utama dari Cross-Encoder Reranker dalam pipeline RAG?**
   * A. Mengompres ukuran file PDF menjadi format teks ringkas.
   * B. Mengonversi teks pertanyaan menjadi representasi suara.
   * C. Menilai relevansi antara kueri dan kumpulan dokumen kandidat secara berpasangan (*joint attention*) untuk mengurutkan dokumen dengan tingkat presisi lebih tinggi sebelum masuk context window.
   * D. Menghapus data histori percakapan lama dari memori Redis.

#### B. Pertanyaan Intermediate (Pilihan Ganda & Analisis)
6. **Sebuah sistem RAG mengalami fenomena "Lost in the Middle". Pendekatan arsitektural mana yang paling tepat untuk mengatasinya?**
   * A. Memperbesar context window hingga 2 juta token tanpa chunking.
   * B. Mengurangi jumlah dokumen hasil retrieval, menaikkan relevansi via Cross-Encoder Reranker, dan memposisikan dokumen terpenting di awal atau akhir konteks prompt.
   * C. Menghilangkan lapisan reranker dan hanya mengandalkan Top-100 Cosine Similarity.
   * D. Menurunkan suhu inferensi (*temperature*) menjadi 0.0.

7. **Ketika merancang Agentic Workflow dengan pola ReAct (Reason + Act), risiko arsitektur terbesar yang harus dimitigasi oleh PM adalah...**
   * A. Kecepatan inferensi yang terlalu tinggi bagi browser pengguna.
   * B. Agentic Loop Tak Terhingga (*Infinite Loops*) yang mengonsumsi kuota token dan komputasi tanpa menghasilkan resolusi task final.
   * C. Ketidakmampuan model membaca format JSON.
   * D. Keharusan melatih ulang model (*fine-tuning*) setiap kali kueri baru masuk.

8. **Mengapa implementasi isolasi data multi-tenant pada Vector Database tidak cukup hanya dengan mengandalkan instruksi sistem prompt (e.g., "Hanya baca data milik Tenant X")?**
   * A. Karena LLM rentan terhadap *prompt injection* dan *jailbreak* yang dapat memaksa model mengabaikan batasan instruksi sistem.
   * B. Karena sistem prompt melipatgandakan ukuran embedding vector.
   * C. Karena vector database tidak dapat membaca teks instruksi sistem prompt.
   * D. Karena instruksi sistem prompt hanya berjalan pada model berukuran di bawah 7B parameter.

9. **Jika sistem Anda memiliki batasan SLA P99 End-to-End sebesar 2.000 ms, dan komponen Retrieval membutuhkan waktu 400 ms, Network Gateway 100 ms, dan Guardrails 150 ms, berapa alokasi anggaran latensi maksimum untuk TTFT dan Token Stream awal Model Serving?**
   * A. 2.000 ms
   * B. 650 ms
   * C. 1.350 ms
   * D. 3.000 ms

10. **Apa implikasi finansial utama dari fenomena *KV-Cache Memory Bloat* pada cluster hosting LLM mandiri?**
    * A. Biaya listrik server berkurang secara signifikan.
    * B. Batas throughput (*concurrency*) model server menurun, memaksa penambahan node GPU baru untuk mempertahankan SLA, yang melipatgandakan *Cloud Infrastructure Bill*.
    * C. Harga token API SaaS komersial menjadi lebih mahal.
    * D. Database relasional mengalami kegagalan replikasi master-slave.

#### C. Skenario Kasus Produksi

11. **Skenario 1**:
    Sistem *AI Search Internal Enterprise* perusahaan Anda mendadak mengalami lonjakan komplain dari divisi legal: "Sistem memberikan dokumen draft kontrak yang sifatnya rahasia kepada staf magang yang tidak memiliki hak akses." Setelah diaudit, model LLM berhasil mengekstrak dokumen tersebut dari Vector DB.
    *   *Pertanyaan Analisis*: Di lapisan arsitektur mana kegagalan sistem terjadi, dan mekanisme perbaikan arsitektural konkret apa yang wajib diterapkan pada pipeline retrieval untuk menjamin kepatuhan hak akses (*Authorization*)?

12. **Skenario 2**:
    Layanan *Customer Support AI* Anda menggunakan arsitektur streaming dengan vLLM. Ketika terjadi flash sale, beban request naik dari 10 RPS menjadi 150 RPS. TTFT membengkak dari 600 ms menjadi 14.500 ms, memicu ratusan timeout error pada API Gateway (504 Gateway Timeout).
    *   *Pertanyaan Analisis*: Apa akar masalah teknis di layer model serving, dan strategi arsitektur apa yang harus diambil (dari perspektif traffic shaping, queue management, dan fallback) untuk menjaga stabilitas sistem tanpa membuat biaya infrastruktur melambung liar?

13. **Skenario 3**:
    Sebuah aplikasi *Enterprise Data Analyst Agent* diberikan akses *read-write* ke database SQL analitik via Text-to-SQL tool. Seorang analis bertanya: *"Hapus data transaksi fiktif bulan lalu dan tampilkan ringkasan barunya."* Agen secara otonom menghasilkan instruksi SQL: `DELETE FROM transactions WHERE is_fictitious = true;`.
    *   *Pertanyaan Analisis*: Kesalahan tata kelola arsitektur mendasar apa yang diabaikan oleh tim produk dalam pemberian kewenangan *Tool Execution* kepada LLM, dan bagaimana rancangan *Execution Isolation Barrier* yang aman untuk mencegah insiden kehilangan data permanen?

---

### Kunci Jawaban & Panduan Penilaian Quiz

#### Jawaban Bagian A:
1. **B** — Dense retrieval merepresentasikan makna semantik dalam vektor kontinu berdimensi tinggi, sedangkan Sparse berfokus pada kehadiran kata kunci leksikal persis (exact tokens).
2. **B** — TTFT mengukur waktu respons awal sistem sampai token pertama berhasil dikembalikan ke client (indikator penting persepsi responsivitas).
3. **B** — Continuous batching mengevaluasi eksekusi pada level iterasi token individu, menghindari pemborosan siklus komputasi akibat padding teks.
4. **B** — Data FAQ statis yang memiliki kesamaan makna semantik tinggi merupakan kandidat sempurna untuk semantic caching tanpa risiko data usang.
5. **C** — Cross-encoder melakukan deep cross-attention antara kueri dan dokumen secara bersamaan, menghasilkan ranking relevansi yang jauh lebih akurat dibanding bi-encoder cosine similarity.

#### Jawaban Bagian B:
6. **B** — Membatasi kandidat dokumen, melakukan reranking, dan menyusun context layout secara strategis (primer di awal/akhir) memulihkan fokus atensi LLM.
7. **B** — Loop tak terhingga pada penalaran otonom dapat melumpuhkan sistem dan menghabiskan biaya operasional; batasan eksekusi eksplisit (*circuit breaker*) wajib dipasang.
8. **A** — LLM bukan *security boundary*. Proteksi data multi-tenant wajib diisolasi pada layer data (database hard metadata filter/row level security), bukan diserahkan pada kepatuhan instruksi bahasa alami model.
9. **C** — Latensi tersisa: $2.000\text{ms} - (400\text{ms} + 100\text{ms} + 150\text{ms}) = 1.350\text{ms}$.
10. **B** — Saat memori KV-Cache penuh, GPU tidak bisa menerima request baru (*head-of-line blocking*), memaksa alokasi GPU tambahan yang meningkatkan pengeluaran CapEx/OpEx.

#### Panduan Jawaban Bagian C (Kasus Produksi):
11. **Skenario 1**:
    * *Akar Masalah*: Tidak adanya penerapan *Access Control List (ACL) Filtering* pada Vector Database level. Retrieval dilakukan secara agnostik otorisasi, mengandalkan asumsi bahwa dokumen yang terambil aman untuk dibaca siapapun.
    * *Solusi Arsitektur*: Menerapkan **Pre-Retrieval Metadata Filtering berbasis Hak Akses**. Token identitas pengguna (JWT/OAuth) harus mengekstrak peran dan *permission scope*. Pipeline RAG wajib menyertakan filter eksplisit ke Vector DB query: `filter={"tenant_id": "X", "user_group": {"$in": user_groups}}`. Dokumen tanpa hak akses tidak boleh masuk ke memori retrieval.
12. **Skenario 2**:
    * *Akar Masalah*: Kehabisan alokasi slot antrian inferensi vLLM akibat saturasi VRAM/KV-Cache under *high concurrency*, menyebabkan waktu antri (*queue latency*) melonjak drastis sebelum *prefill* dapat dimulai.
    * *Solusi Arsitektur*: Terapkan *Tiered Architecture*: (1) Aktifkan *Queue Shedding* / Rate Limiting di Ingress dengan respons HTTP 429 yang ramah, (2) Routing dinamis: Kueri yang tidak membutuhkan penalaran berat dialihkan langsung ke secondary provider SaaS atau model yang lebih kecil (distilled model), (3) Turunkan alokasi context window historis chat secara dinamis pada kondisi *high-load*, (4) Terapkan Semantic Caching agresif untuk menahan lonjakan kueri repetitif pada masa *flash sale*.
13. **Skenario 3**:
    * *Akar Masalah*: Pelanggaran prinsip *Least Privilege* dan ketiadaan *Separation of Mutation Concerns*. Memberikan LLM kredensial database tingkat *Data Manipulation Language (DML)* destruktif (`DELETE`, `DROP`, `UPDATE`) secara langsung tanpa pagar pembatas.
    * *Solusi Arsitektur*:
      1. Batasi koneksi database agen hanya pada akun dengan hak akses **Read-Only Data Reader** (`SELECT` permission saja).
      2. Pisahkan jalur mutasi data ke *Dedicated Transactional Service* dengan skema API terstruktur yang mewajibkan konfirmasi eksplisit pengguna (*Two-Phase Confirmation* / Human Confirmation Prompt di antarmuka UI) sebelum perintah mutasi dieksekusi oleh sistem backend deterministik.

---

### 16. Summary

Mengelola produk AI skala produksi menuntut pergeseran paradigma dari *prompt engineering* sederhana menuju **pematangan rekayasa sistem terdistribusi**. Keberhasilan produk tidak ditentukan oleh kecerdasan model semata, melainkan oleh keandalan arsitektur di sekitarnya:

1. **Determinisme Mengelilingi Non-Determinisme**: Selalu bungkus sifat non-deterministik LLM dengan lapisan *guardrails* yang deterministik, sanitasi input-output yang ketat, dan isolasi tenant pada lapisan database.
2. **Keseimbangan Segitiga Emas AI**: Setiap keputusan fitur harus menimbang trade-off antara **Latensi** (P99, TTFT), **Kualitas** (akurasi, recall konteks), dan **Biaya** (token unit cost, alokasi GPU).
3. **Resiliensi Sebagai Fitur Inti**: Agen otonom harus dilengkapi dengan *circuit breaker*, batas iterasi maksimal, dan mekanisme degradasi halus (*graceful degradation*) agar sistem bisnis inti tetap berjalan stabil di tengah gangguan layanan model pihak ketiga.