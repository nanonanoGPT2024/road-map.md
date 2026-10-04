# Kurikulum Terakreditasi: AI Product Builder (ai-product-builder)

Selamat datang di repositori kurikulum resmi **AI Product Builder**. Kurikulum ini dirancang berdasarkan standar kurikulum engineering industri untuk mentransformasi Software Engineer, Technical Product Manager, dan Solutions Architect menjadi praktisi tingkat lanjut yang mampu mengonsepsikan, merekayasa, mengevaluasi, dan merilis produk berbasis AI modern (GenAI, Agents, Multi-modal, dan Foundation Models) ke level produksi skala enterprise.

---

## 1. Course Overview & Mindset

### Pergeseran Paradigma: Dari Deterministic Software ke Probabilistic Systems

Membangun produk AI modern memerlukan pergeseran mendasar dalam cara berpikir rekayasa perangkat lunak (*software engineering paradigm shift*):

1. **Non-Deterministic State Machine**: 
   Dalam *traditional engineering*, fungsi dengan input `X` menjamin output `Y`. Pada sistem berbasis Large Language Model (LLM), input `X` menghasilkan distribusi probabilitas output `Y'`. AI Product Builder tidak mengeliminasi sifat probabilistik ini secara naif, melainkan membangun arsitektur kendali (*deterministic harness*) yang memitigasi variansi, mencegah halusinasi, dan menjamin keandalan sistem.

2. **Triangulasi Kritis: Accuracy vs. Latency vs. Unit Economics**:
   Setiap keputusan arsitektur AI merupakan kompromi struktural:
   * **Accuracy/Fidelity**: Kualitas penalaran, minimisasi halusinasi, dan kepatuhan instruksi.
   * **Latency/Throughput**: *Time To First Token* (TTFT), token streaming, dan waktu eksekusi tool calling.
   * **Unit Economics**: Biaya inferensi per sesi aktif, konsumsi token input/output, serta efisiensi semantic cache.

```
                  [ ACCURACY & CONTEXT FIDELITY ]
                                 ▲
                                / \
                               /   \
                              /     \
                             /       \
     [ LATENCY / TIME-TO-TOKEN ] ◄───► [ UNIT ECONOMICS / INFERENCE COST ]
```

3. **Continuous Evaluation as Code (Evals-Driven Development)**:
   Metrik konvensional (unit test pass/fail) digantikan oleh pipeline evaluasi multi-tier: LLM-as-a-judge, evaluasi berbasis *ground truth*, metrik RAG (Faithfulness, Answer Relevance, Context Recall), dan pemantauan regresi performa berkala pada level data produksi.

---

## 2. Learning Roadmap

Diagram pohon berikut merepresentasikan alur pembelajaran linier dan terstruktur dari Bab 01 hingga Bab 10:

```text
AI Product Builder Master Curriculum
├── BAB 01: Fondasi Arsitektur AI Product & Builder Mindset
│   ├── Modul 01: Anatomi Foundation Models & Paradigma Rekayasa Non-Deterministik
│   ├── Modul 02: Taksonomi Solusi: Prompting vs RAG vs Fine-Tuning
│   └── Modul 03: Unit Economics, Tokenomics & Pemilihan Model (SLM vs LLM)
├── BAB 02: Context Engineering, Prompt Patterns & Structured Outputs
│   ├── Modul 01: Core Prompt Engineering & Metodologi Chain-of-Thought
│   ├── Modul 02: Pydantic Validation & Penjaminan Skema JSON Deterministik
│   └── Modul 03: Dynamic Context Budgeting & Token Window Management
├── BAB 03: Semantic Retrieval, Vector Databases & Embeddings
│   ├── Modul 01: Mekanisme Embedding, Metrik Jarak & Algoritma Indeks (HNSW vs IVF)
│   ├── Modul 02: Chunking Strategy Terarah & Metodologi Metadata Filtering
│   └── Modul 03: Hybrid Search (Sparse/Dense) & Cross-Encoder Reranking
├── BAB 04: Production Retrieval-Augmented Generation (RAG)
│   ├── Modul 01: Advanced RAG Architecture: Multi-Hop Query & Contextual Compression
│   ├── Modul 02: GraphRAG & Entity Relationship Retrieval
│   └── Modul 03: Semantic Caching & Cache-Invalidation Strategies
├── BAB 05: LLM Agents, Function Calling & Tool Orchestration
│   ├── Modul 01: Agent Loop Architecture: ReAct, Plan-and-Solve & State Machines
│   ├── Modul 02: Robust Tool Calling, Sandboxing & Runtime Execution
│   └── Modul 03: Multi-Agent Systems & Distributed Orchestration
├── BAB 06: Model Fine-Tuning, Alignment & Domain Adaptation
│   ├── Modul 01: Formulasi Dataset Supervised Fine-Tuning (SFT) & Synthetic Data
│   ├── Modul 02: PEFT, LoRA & QLoRA Applied Architectures
│   └── Modul 03: Model Alignment: DPO vs RLHF Pipeline Production
├── BAB 07: AI Product Evaluation, Benchmarking & Observability
│   ├── Modul 01: Framework Evaluasi RAG (Ragas, TruLens) & LLM-as-a-Judge
│   ├── Modul 02: Tracing Produksi Menggunakan OpenTelemetry & Langfuse
│   └── Modul 03: Automated Regression Testing & Continuous Evals CI/CD
├── BAB 08: Human-in-the-Loop, AI UX/UI Patterns & Guardrails
│   ├── Modul 01: Modern AI UX: Progressive Streaming & Intent Steerability
│   ├── Modul 02: Runtime Safety Guardrails (NeMo, Llama Guard) & Masking PII
│   └── Modul 03: Active Learning Loops & Dynamic Human Feedback (RLHF Data Capture)
├── BAB 09: Skalabilitas Infrastruktur, Latensi & Optimasi Biaya
│   ├── Modul 01: High-Throughput Serving Frameworks: vLLM, TensorRT-LLM, TGI
│   ├── Modul 02: LLM Gateway, Rate Limiting & Multi-Provider Fallbacks
│   └── Modul 03: Optimasi Biaya: Quantization (AWQ/GPTQ) & Prompt Distillation
└── BAB 10: AI Governance, Regulasi, Keamanan & Enterprise Readiness
    ├── Modul 01: Red Teaming, Prompt Injection Defense & Data Extraction Jailbreaks
    ├── Modul 02: Enterprise Compliance: EU AI Act, SOC2 Type II & Data Lineage
    └── Modul 03: AI Incident Management, Rollback Architecture & Auditing
```

---

## 3. Navigasi Detail Bab 01 s/d Bab 10

### [BAB 01: Fondasi Arsitektur AI Product & Builder Mindset](./bab-01-fondasi-ai-product-mindset/README.md)
Fondasi rekayasa sistem probabilistic, pergeseran pola pikir perancangan sistem deterministic ke model probabilistik, analisis mendalam batas kapabilitas LLM/SLM, serta perhitungan matematis *unit economics* per interaksi.
* [01-fondasi-foundation-models.md](./bab-01-fondasi-ai-product-mindset/01-fondasi-foundation-models.md): Dekonstruksi mekanisme autoregressive tokens, attention mechanism, token window, context drift, dan batas kapabilitas inferensi modern.
* [02-taksonomi-prompt-rag-tuning.md](./bab-01-fondasi-ai-product-mindset/02-taksonomi-prompt-rag-tuning.md): Kerangka pengambilan keputusan komparatif antara System Prompting, In-Context Retrieval (RAG), Fine-Tuning, dan Pre-training.
* [03-unit-economics-dan-tokenomics.md](./bab-01-fondasi-ai-product-mindset/03-unit-economics-dan-tokenomics.md): Model finansial AI: formulasi biaya token input/output, amortisasi infrastruktur GPU, TTFT amortized cost, dan penentuan ambang kelayakan komersial produk AI.

### [BAB 02: Context Engineering, Prompt Patterns & Structured Outputs](./bab-02-context-engineering-structured-outputs/README.md)
Rekayasa penyusunan konteks deterministik, perancangan skema sistematis dengan jaminan validitas sintaksis berbasis tipe data statis, dan mitigasi token overhead.
* [01-prompt-engineering-patterns.md](./bab-02-context-engineering-structured-outputs/01-prompt-engineering-patterns.md): Implementasi pola prompt enterprise: Chain-of-Thought (CoT), Few-Shot dynamic exemplar, Self-Consistency, dan System Message Framing.
* [02-structured-outputs-pydantic.md](./bab-02-context-engineering-structured-outputs/02-structured-outputs-pydantic.md): Ekstraksi data terstruktur dengan validasi ketat menggunakan JSON Schema, Pydantic, Instructor, dan Open-source Grammar Enforcers (Outlines).
* [03-context-window-optimization.md](./bab-02-context-engineering-structured-outputs/03-context-window-optimization.md): Teknik optimasi dan kompresi konteks: dynamic prompt assembling, sliding window context trimming, dan token budgeting.

### [BAB 03: Semantic Retrieval, Vector Databases & Embeddings](./bab-03-semantic-retrieval-vector-databases/README.md)
Arsitektur pengambilan informasi semantik level enterprise, eksplorasi representasi vektor dens/sparse, indexing internal engine, dan strategi pencarian hibrida.
* [01-embedding-math-and-indexing.md](./bab-03-semantic-retrieval-vector-databases/01-embedding-math-and-indexing.md): Teori jarak vektor (Cosine, Dot Product, Euclidean), model embedding multi-lingual, algoritma indeks HNSW vs. IVF, dan kompromi memory-recall.
* [02-chunking-dan-metadata-enrichment.md](./bab-03-semantic-retrieval-vector-databases/02-chunking-dan-metadata-enrichment.md): Strategi semantic chunking, recursive character splitting, parent-child document linkage, dan pengkayaan metadata deklaratif.
* [03-hybrid-search-dan-reranking.md](./bab-03-semantic-retrieval-vector-databases/03-hybrid-search-dan-reranking.md): Implementasi Reciprocal Rank Fusion (RRF) menggabungkan BM25 dan Dense Embeddings, serta deployment Cross-Encoder Rerankers (misal: Cohere, BAAI-bge-reranker).

### [BAB 04: Production Retrieval-Augmented Generation (RAG)](./bab-04-production-rag-systems/README.md)
Konstruksi arsitektur sistem RAG end-to-end yang toleran terhadap kegagalan, multi-stage retrieval, GraphRAG untuk entitas terdistribusi, dan persistensi semantic cache.
* [01-advanced-rag-architectures.md](./bab-04-production-rag-systems/01-advanced-rag-architectures.md): Query rewriting, multi-query expansion, sub-queries, Contextual Compression, dan Self-RAG loop untuk validasi konsistensi dokumen sumber.
* [02-graphrag-and-knowledge-graphs.md](./bab-04-production-rag-systems/02-graphrag-and-knowledge-graphs.md): Integrasi knowledge graph struktural dengan vector space retrieval untuk relasi entitas multi-hop dan agregasi global konteks.
* [03-semantic-caching-production.md](./bab-04-production-rag-systems/03-semantic-caching-production.md): Arsitektur semantic cache berbasis Redis/GPTCache, ambang similarity distance, serta mekanisme proaktif cache invalidation.

### [BAB 05: LLM Agents, Function Calling & Tool Orchestration](./bab-05-llm-agents-tool-orchestration/README.md)
Pembangunan sistem otonom (*autonomous agents*), orkestrasi tools secara deterministik, penanganan kegagalan eksekusi, serta kolaborasi agen terdesentralisasi.
* [01-agent-architectures-and-loops.md](./bab-05-llm-agents-tool-orchestration/01-agent-architectures-and-loops.md): Arsitektur ReAct (Reasoning + Acting), Plan-and-Execute, State Graph (LangGraph), dan siklus deterministik eksekusi agen.
* [02-production-tool-calling.md](./bab-05-llm-agents-tool-orchestration/02-production-tool-calling.md): Standardisasi API Function Calling, sandboxing eksekusi kode terisolasi (gVisor/Wasm), retry policy, dan penanganan graceful failure.
* [03-multi-agent-orchestration.md](./bab-05-llm-agents-tool-orchestration/03-multi-agent-orchestration.md): Koordinasi multi-agen: supervisor-worker pattern, inter-agent messaging protocol (A2A), dan penyelesaian konflik konsensus multi-agen.

### [BAB 06: Model Fine-Tuning, Alignment & Domain Adaptation](./bab-06-fine-tuning-and-domain-adaptation/README.md)
Kapan dan bagaimana melatih model sendiri secara efisien, penyusunan dataset berkualitas tinggi, teknik parameter-efficient, dan penyelarasan perilaku model (*alignment*).
* [01-dataset-curation-and-sft.md](./bab-06-fine-tuning-and-domain-adaptation/01-dataset-curation-and-sft.md): Kurasi korpus domain-spesifik, filter noise, dedup, mitigasi *data contamination*, dan sintesis data menggunakan LLM pengawas (*Evol-Instruct*).
* [02-peft-lora-qlora-pipeline.md](./bab-06-fine-tuning-and-domain-adaptation/02-peft-lora-qlora-pipeline.md): Rekayasa adapter LoRA, rank allocation, alpha hyperparameter tuning, QLoRA 4-bit quantization training menggunakan Unsloth dan Hugging Face TRL.
* [03-alignment-dpo-vs-rlhf.md](./bab-06-fine-tuning-and-domain-adaptation/03-alignment-dpo-vs-rlhf.md): Pipeline Direct Preference Optimization (DPO) vs Reinforcement Learning from Human Feedback (RLHF), reward modeling, dan evaluasi *loss divergence*.

### [BAB 07: AI Product Evaluation, Benchmarking & Observability](./bab-07-evaluation-benchmarking-observability/README.md)
Pengukuran saintifik kualitas sistem AI, framework evaluasi berbasis metrik deterministik dan model-as-a-judge, serta arsitektur tracing produksi berlatensi rendah.
* [01-evals-frameworks-and-ragas.md](./bab-07-evaluation-benchmarking-observability/01-evals-frameworks-and-ragas.md): Operasionalisasi metrik Ragas (Context Precision, Context Recall, Faithfulness, Answer Relevance) dan perancangan judge LLM tanpa bias position.
* [02-observability-tracing-telemetry.md](./bab-07-evaluation-benchmarking-observability/02-observability-tracing-telemetry.md): Integrasi instrumen OpenTelemetry, distributed span tracking via Langfuse/Arize Phoenix, dan pemantauan token distribution per request.
* [03-cicd-automated-regression-testing.md](./bab-07-evaluation-benchmarking-observability/03-cicd-automated-regression-testing.md): Membangun gerbang pipeline evaluasi CI/CD otomatis menggunakan GitHub Actions, toleransi deviasi statistik, dan pencegahan degradasi performa model.

### [BAB 08: Human-in-the-Loop, AI UX/UI Patterns & Guardrails](./bab-08-hitl-ux-patterns-guardrails/README.md)
Desain antarmuka responsif terhadap latensi inferensi, kontrol keamanan input/output secara real-time, dan kanal umpan balik manusia untuk continuous learning.
* [01-generative-ai-ux-patterns.md](./bab-08-hitl-ux-patterns-guardrails/01-generative-ai-ux-patterns.md): Streaming UI, penanganan Server-Sent Events (SSE), optimasi perceived latency, intent steering widgets, dan perancangan *graceful fallback UX*.
* [02-safety-guardrails-and-pii-masking.md](./bab-08-hitl-ux-patterns-guardrails/02-safety-guardrails-and-pii-masking.md): Implementasi runtime guardrails (NeMo Guardrails, Guardrails AI, Llama Guard), pencegahan output toxic, dan masking PII (*Presidio Engine*).
* [03-human-in-the-loop-feedback.md](./bab-08-hitl-ux-patterns-guardrails/03-human-in-the-loop-feedback.md): Arsitektur penangkapan sinyal implisit/eksplisit pengguna, review antarmuka manual (*override* data labeler), dan sinkronisasi kembali ke training dataset.

### [BAB 09: Skalabilitas Infrastruktur, Latensi & Optimasi Biaya](./bab-09-infrastructure-latency-cost-optimization/README.md)
Rekayasa deployment backend inferensi high-throughput, perancangan gateway pintar (*smart routing*), serta optimasi bobot model untuk meminimalisasi biaya server.
* [01-high-throughput-inference-serving.md](./bab-09-infrastructure-latency-cost-optimization/01-high-throughput-inference-serving.md): Konfigurasi vLLM, PagedAttention, batched inference dynamically, Tensor Parallelism pada multi-GPU, dan optimasi KV-Cache.
* [02-llm-gateway-and-smart-routing.md](./bab-09-infrastructure-latency-cost-optimization/02-llm-gateway-and-smart-routing.md): Arsitektur proxy routing multi-vendor (LiteLLM/Portkey), circuit breakers, dynamic fallback model cascades (Tier 1 -> Tier 2), dan load balancing.
* [03-quantization-and-prompt-distillation.md](./bab-09-infrastructure-latency-cost-optimization/03-quantization-and-prompt-distillation.md): Model compression via AWQ, GPTQ, FP8 precision, serta kompresi prompt terarah (LLMLingua) untuk reduksi biaya token operasional.

### [BAB 10: AI Governance, Regulasi, Keamanan & Enterprise Readiness](./bab-10-governance-security-enterprise-readiness/README.md)
Pertahanan mendalam terhadap serangan siber spesifik model LLM, pematuhan kerangka hukum internasional, dan infrastruktur audit enterprise.
* [01-llm-security-and-jailbreak-defense.md](./bab-10-governance-security-enterprise-readiness/01-llm-security-and-jailbreak-defense.md): Analisis vektor serangan OWASP Top 10 for LLM: Direct/Indirect Prompt Injections, Data Exfiltration, dan mitigasi adversarial prompts.
* [02-regulatory-compliance-and-lineage.md](./bab-10-governance-security-enterprise-readiness/02-regulatory-compliance-and-lineage.md): Standar EU AI Act (kategori High-Risk), kepatuhan privasi SOC2 Type II, enkripsi KMS context, dan auditability lineage data.
* [03-ai-incident-management-and-rollbacks.md](./bab-10-governance-security-enterprise-readiness/03-ai-incident-management-and-rollbacks.md): SOP Incident response kegagalan halusinasi kritis, *instant kill-switch* orkestrasi model, audit logging tak terubah (*immutable audit trails*).

---

## 4. Spesifikasi Capstone Project Enterprise

### Judul Sistem
**Enterprise Cognitive Action Engine (ECAE) - "AegisCore"**

### Ikhtisar Proyek
AegisCore adalah platform AI end-to-end otonom yang bertindak sebagai *Autonomous Customer Escalation & Resolution Agent* untuk korporasi FinTech / Perbankan Skala Enterprise. Sistem tidak hanya merespons pertanyaan ambigu, tetapi juga memverifikasi identitas penanya, membaca dokumen audit internal secara real-time via Hybrid RAG, dan mengeksekusi aksi finansial korektif (refund, chargeback limit lock, unfreeze account) melalui Tool Calling deterministik dengan validasi audit trail yang ketat.

### Diagram Arsitektur Sistem

```text
               [ Client Applications: Web / Mobile / Dashboard ]
                                       │
                                       ▼ (HTTPS / SSE Streaming)
            [ Enterprise LLM Gateway (LiteLLM / Custom Fastify) ]
                 ├── PII Masking Engine (Microsoft Presidio)
                 ├── Prompt Injection Firewall (NeMo Guardrails)
                 └── Semantic Cache (Redis + HNSW Embeddings)
                                       │
                      (Cache Miss / Authorized Prompt)
                                       ▼
                   [ Core Orchestration Engine (LangGraph) ]
                 ├── State Machine: Query Analysis & Plan-Execute
                 ├── Context Assembler (Dynamic Token Budgeting)
                 └── Multi-Agent Coordination Protocol
                       │                               │
       (Knowledge Retrieval)                  (Action Execution)
               │                                       │
               ▼                                       ▼
    [ Production Hybrid RAG ]             [ Deterministic Tool Harness ]
   ├── Dense Retrieval (Qdrant)           ├── Pydantic Output Validation
   ├── Sparse Keyword (BM25)              ├── Wasm Sandbox Isolation
   ├── Cross-Encoder Reranker             ├── Approval Queue (HITL Tier)
   └── Contextual Compressor              └── Core Banking System REST APIs
               │                                       │
               └───────────────┬───────────────────────┘
                               ▼
            [ Dual-Tier Model Serving Infrastructure ]
           ├── Tier 1: Small Finetuned Model (SLM on vLLM - Reasoning)
           └── Tier 2: Frontier LLM (Claude 3.5 Sonnet / GPT-4o - Fallback)
                               │
                               ▼
       [ Enterprise Observability, Evals & Audit Infrastructure ]
           ├── Tracing: OpenTelemetry + Langfuse Production
           ├── Realtime Evals: Ragas CI Pipeline + LLM-as-a-Judge
           └── Compliance: Immutable Audit Trail (PostgreSQL + S3 WORM)
```

### Komponen Wajib Deliverables
1. **Repository Structure**:
   * Monorepo modular berbasis Python (FastAPI/LangGraph) dan Next.js (Admin/Client Playground).
   * Direktori terpisah untuk `/evals`, `/infra`, `/guardrails`, dan `/core-engine`.
2. **Deterministic Evaluation Harness**:
   * Evaluasi suite CI/CD minimal mencakup 100 test case *golden dataset*.
   * Skor ambang batas (Threshold Gates): Faithfulness >= 0.90, Answer Relevance >= 0.88, Context Recall >= 0.85.
   * Toleransi toleransi halusinasi: < 1.0% pada evaluasi safety prompt injection.
3. **Model & Retrieval Strategy**:
   * Vector Database: Qdrant / Milvus dengan konfigurasi hybrid search (Dense + BM25) dan HNSW indexing.
   * Model Routing: Router cerdas yang mengalihkan 70% query standar ke model lokal yang di-fine-tune (LoRA/vLLM) dan 30% query kompleks ke Frontier LLM untuk menghemat biaya operasional.
4. **Safety & Guardrails**:
   * Pertahanan aktif terhadap indirect prompt injection dari isi dokumen customer.
   * Otomatisasi redaksi data PII (NIK, Kartu Kredit, Alamat) sebelum payload dikirimkan ke model eksternal.
5. **Observability & Business Metrics Dashboard**:
   * Implementasi span tracking OpenTelemetry di setiap tahapan tool calling dan RAG retrieval.
   * Dashboard analitik: Metrik biaya real-time (Cost per Query), latensi rata-rata p95/p99, dan kepuasan resolusi pengguna akhir.

---

## 5. Standar Kontribusi & Panduan Memulai

1. Clone repositori ini ke environment development lokal Anda:
   ```bash
   git clone https://github.com/organization/ai-product-builder.git
   cd ai-product-builder
   ```
2. Pastikan environment lokal memenuhi prasyarat dependensi berikut:
   * Python `>= 3.11`
   * Node.js `>= 20.x`
   * Docker Engine `>= 24.x` & Docker Compose
   * CUDA Toolkit `>= 12.2` (Opsional untuk inferensi lokal)
3. Baca dokumentasi detail per bab melalui direktori `./bab-01-fondasi-ai-product-mindset` hingga `./bab-10-governance-security-enterprise-readiness`.
4. Setiap sub-modul berisi penjelasan teoretis, diagram arsitektur mendalam, dan *hands-on code lab* yang harus diselesaikan untuk memenuhi standar kelulusan kurikulum.