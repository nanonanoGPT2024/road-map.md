# BAB 03: Product Analytics, Telemetry & Metric Architecture
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, Technical Product Manager (TPM) dan AI Product Lead diharapkan memiliki kompetensi teruji untuk:

1. **Merancang Arsitektur Telemetri End-to-End untuk Sistem Non-Deterministik**: Mampu mendesain pipeline telemetri bervolume tinggi yang menangkap siklus hidup eksekusi Autonomous Agent (multiturn, multi-tool, asynchronous reasoning) menggunakan standar OpenTelemetry GenAI Semantic Conventions.
2. **Mengelola Skalabilitas dan Komputasi Metrik Real-Time**: Mengorkestrasi arsitektur ingestion streaming berbasis decoupled buffer (Apache Kafka/Redpanda) dan Real-Time OLAP (ClickHouse/Apache Pinot) untuk query latency sub-detik pada miliaran event operasional dan analitik.
3. **Membangun AI Semantic Metric Layer**: Merumuskan dan mengimplementasikan standardisasi metrik gabungan—mengintegrasikan metrik produk klasik (DAU, Retention, Funnel Conversion) dengan metrik AI modern (Time-to-First-Token/TTFT, Tokens-per-Output-Token/TPOT, Hallucination Index, Tool-Call Accuracy, dan Unit Economics per Output Value).
4. **Menerapkan Strict Privacy & Governance Guardrails**: Membangun mekanisme zero-trust PII masking and redaction directly at the telemetry ingestion tier sebelum event data persisten di data warehouse atau feature store.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* Konsep dasar event tracking (Event-Actor-Object model, state tracking).
* Dasar-dasar arsitektur microservices dan distributed tracing (Trace ID, Span ID, Context Propagation).
* Konsep LLM pipeline: Prompting, Inference Engine, Context Window, Tokenizer, Function Calling / Tool Selection.
* Dasar SQL analitik tingkat lanjut (Window functions, Partitioning, Rollup aggregations).

---

### 3. Concept & Internal Architecture

Dalam lanskap software engineering deterministik konvensional, product analytics cukup melacak interaksi UI berbasis event deterministik: klik tombol, submit formulir, atau page view. Namun, pada produk berbasis **AI & Autonomous Agents**, paradigma ini runtuh. Interaksi pengguna bersifat open-ended, proses komputasi terjadi secara probabilistik (non-deterministik), dan sebuah instruksi sederhana dari pengguna dapat memicu rantai pemikiran (*chain-of-thought*), pemanggilan sub-agent majemuk, evaluasi API pihak ketiga, hingga eksekusi kueri basis data internal yang memakan waktu detik hingga menit.

Untuk mengukur performa produk, kepuasan pengguna (*product-market fit*), dan efisiensi biaya secara presisi, arsitektur telemetri enterprise modern harus mengintegrasikan tiga pilar observabilitas (Metrics, Logs, Traces) menjadi satu kesatuan data pipeline analitik produk.

```
                    ARARSITEKTUR TELEMETRI TINGKAT PRODUKSI
                    
 [Client Application / Web / Mobile / API Gateway]
                         |
                         v (Context Propagation: traceparent, session_id, tenant_id)
      +-------------------------------------------------------+
      |             Agentic Runtime & Inference Core          |
      |   (LangGraph / Semantic Kernel / Custom Auto-Agent)    |
      +-------------------------------------------------------+
               |                                      |
       (In-Memory PII Masking)              (OTel Spans & Metrics)
               |                                      |
               +-------------------+------------------+
                                   |
                                   v (OTLP / gRPC)
                  +----------------------------------+
                  |   OpenTelemetry Collector Tier   |
                  |  - Batch Processor               |
                  |  - Tail-based Sampling Processor |
                  |  - Sensitive Data Redaction      |
                  +----------------------------------+
                                   |
                        (High-Throughput Stream)
                                   v
                  +----------------------------------+
                  |   Streaming Buffer (Apache Kafka)|
                  +----------------------------------+
                                   |
                   +---------------+---------------+
                   |                               |
                   v (Real-time Stream Engine)     v (Micro-batch / Object Storage)
         +-------------------+           +-----------------------+
         | Apache Flink      |           | Vector Ingestion Sinks|
         | (Anomaly/Security)|           | (Iceberg / S3 DataLake|
         +-------------------+           +-----------------------+
                   |                               |
                   v                               v
         +-------------------+           +-----------------------+
         | Real-time Alerts  |           | ClickHouse OLAP       |
         | (Slack, PagerDuty)|           | (Semantic Metric Layer|
         +-------------------+           +-----------------------+
                                                   |
                                                   v
                                     +---------------------------+
                                     | Enterprise BI & AI Eval   |
                                     | (Metabase / Superset /    |
                                     |  Continuous Eval Engine)  |
                                     +---------------------------+
```

#### Komponen Kunci Arsitektur:

1. **Context Propagation Engine**: Membawa context universal (Trace ID, Span ID, Session ID, User ID terenkripsi, Tenant ID, Agent Mode) menembus batas thread eksekusi asinkron, webhooks, dan inference worker cluster.
2. **OTel Collector dengan Tail-Based Sampling**: Mengurangi biaya penyimpanan telemetri tanpa kehilangan visibilitas. Traces yang menghasilkan error, interaksi dengan latency di atas p95, atau terindikasi loop halusinasi di-retain 100%, sedangkan trace eksekusi nominal (sukses berlatensi rendah) disampling (misal 5%).
3. **Decoupled Event Streaming (Kafka/Redpanda)**: Mencegah backpressure dari layer analitik memengaruhi critical-path response time dari LLM ke pengguna akhir.
4. **Real-Time OLAP Data Store (ClickHouse)**: Mengakomodasi skema semi-terstruktur (JSON) dengan kompresi kolom ekstrem (ZSTD/LZ4), memungkinkan agregasi jutaan span per detik dengan latensi kueri <500ms untuk dashboard produk.
5. **Universal Metric Layer**: Mengubah data event teknis mentah menjadi indikator kinerja produk yang siap dikonsumsi stakeholders bisnis tanpa bias inkonsistensi kalkulasi.

---

### 4. Why & What

#### Mengapa Telemetri Tradisional Gagal pada AI Agents?

| Kriteria Evaluasi | Analitik Tradisional (Mixpanel, GA4, Amplitude) | AI & Agentic Telemetry Architecture |
| :--- | :--- | :--- |
| **Sifat Eksekusi** | Deterministik (Path $A \rightarrow B \rightarrow C$). | Non-deterministik ($A \rightarrow$ Reasoning Loop $\rightarrow$ Tool Call $\rightarrow$ Error Retry $\rightarrow C$). |
| **Unit Analisis** | Click, Impression, Page Load Time. | Token, Tool Invocations, Vector Retrieval Relevance, Run Iterations. |
| **Penyebab Latensi** | Network latency, DOM rendering, Database query. | Time-to-First-Token (TTFT), Prefill vs Decode time, Tool execution timeout. |
| **Kegagalan Sistem** | HTTP 5xx, Unhandled Client Exceptions. | Silent Semantic Failure (Format output benar, isi halusinasi/salah). |
| **Biaya Operasional** | Konstan per request (Infra cloud standar). | Variabel per token, model switching, multi-turn context expansion. |

#### Apa yang Harus Ditangkap (The 4 Facets of AI Telemetry)?

Sebagai Technical PM, telemetri harus mencakup 4 dimensi yang berkorelasi:
1. **Product UX Facet**: Intent completion rate, user sentiment via implicit signals (copy-paste action, regenerations, immediate edits), user idle dwell-time.
2. **Algorithmic/Model Performance Facet**: TTFT, Tokens per Second (Throughput), Context Window Saturation (Ratio used/limit), Guardrail Trip Rate.
3. **Agent Reasoning & System Execution Facet**: Trace step execution, Tool-call error rate, Loop iteration count, Sub-agent hand-off latency.
4. **Unit Economics Facet**: Cost-per-Successful-Resolution (CPSR), Input/Output token cost attribution per feature, Tenant margin degradation rate.

---

### 5. How (Workflow Detail)

Alur komprehensif telemetri runtime agent dari saat instruksi diterima hingga metrik terkonsolidasi:

```
[User Action] 
      │
      ▼
1. INGESTION & TRACE ENRICHMENT
   - Injeksi context metadata (TraceId, SpanId, TenantId, UserTier).
   - Evaluasi payload dengan local regex/presidio PII masking engine.
      │
      ▼
2. ORCHESTRATION LAYER (AGENTIC RUNTIME)
   - Emisi Span: `gen_ai.agent.turn` (Start)
   - Retrieval Augmented Generation (RAG) vector lookup.
   - Emisi Span: `gen_ai.retrieval` (Simpan top_k score, retrieval latency).
      │
      ▼
3. MODEL INFERENCE INVOCATION
   - Eksekusi LLM Provider (OpenAI, Anthropic, Self-hosted vLLM).
   - Hook streaming chunk: Rekam waktu paket pertama tiba (TTFT).
   - Emisi Span: `gen_ai.client.inference` (Model, Temp, Input/Output Token Count).
      │
      ▼
4. TOOL EXECUTION / SUB-AGENT ROUTING
   - Agent memutuskan invoke external tools (misal: SQL Runner, Search API).
   - Emisi Span: `gen_ai.tool.execution` (Tool Name, Execution Status, Args hash).
      │
      ▼
5. COMPLIANCE & ASYNC EXPORT
   - Batching telemetry payload di memori via OTLP gRPC.
   - Flush asynchronous ke Collector tanpa memblokir thread respon pengguna.
      │
      ▼
6. STREAM PROCESSING & STORAGE ENGINE
   - OTel Collector menerapkan Tail-based Sampling.
   - Stream masuk Kafka Topic: `telemetry.agent.events.v1`.
   - Consumer ClickHouse melakukan ingest via streaming materialized views.
      │
      ▼
7. METRIC LAYER CONSOLIDATION
   - Agregasi berkala: TTFT p95, Token-to-Resolution, Average Cost Per Run.
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Sistem
Bayangkan produk software konvensional seperti **Kereta Api Jalur Tetap**: relnya sudah ditentukan (UI flow statis). Jika kereta anjlok, lokasi kerusakan mudah ditemukan berdasarkan titik rel yang terputus.

Sebaliknya, **Autonomous AI Agent adalah Helikopter Tanpa Awak yang Menembus Badai**: pilot AI menentukan jalurnya sendiri secara dinamis berdasarkan arah angin (input prompt pengguna) dan medan (respons API pihak ketiga). Untuk menganalisis kegagalan misi, Anda tidak bisa sekadar mengecek rel; Anda memerlukan **Flight Data Recorder (Black Box) Multidimensi**: mencatat setiap perubahan pitch, yaw, konsumsi bahan bakar per detik, rekaman keputusan algoritma autopilot, serta kondisi visibilitas lingkungan secara bersamaan.

#### Peta Arsitektur Data Telemetri Terdistribusi

```
+---------------------------------------------------------------------------------------+
| AGENT RUNTIME SPAN LIFECYCLE (Distributed Tracing Topology)                           |
+---------------------------------------------------------------------------------------+
[Trace: trace_id = "tr-8942-bf23-8891"]
|
+--- [Root Span: "agent_task_execution" | 2450ms]
     |   Metadata: { tenant: "corp_alpha", user_hash: "u_9a1f", intent: "refund_order" }
     |
     +--- [Child Span 1: "retrieve_user_context" | 120ms]
     |         Attributes: { rag.docs_matched: 3, rag.min_similarity: 0.89 }
     |
     +--- [Child Span 2: "llm_reasoning_step_1" | 980ms]
     |         Attributes: { 
     |           gen_ai.system: "anthropic",
     |           gen_ai.request.model: "claude-3-5-sonnet",
     |           gen_ai.usage.input_tokens: 1420,
     |           gen_ai.usage.output_tokens: 85,
     |           telemetry.ttft_ms: 210
     |         }
     |
     +--- [Child Span 3: "tool_execution:stripe_api" | 450ms]
     |         Attributes: { 
     |           tool.name: "issue_refund", 
     |           tool.status: "success",
     |           tool.latency_ms: 448
     |         }
     |
     +--- [Child Span 4: "llm_final_response" | 880ms]
               Attributes: { 
                 gen_ai.usage.input_tokens: 1650,
                 gen_ai.usage.output_tokens: 120,
                 eval.implicit_hallucination_flag: false
               }
```

---

### 7. Simple Example & Practical Example

Berikut adalah implementasi level enterprise menggunakan Python, OpenTelemetry API/SDK, dan integrasi semantic conventions untuk autonomous agentic workflows.

#### Step 1: Inisialisasi Tracing Engine Terisolasi (`telemetry_core.py`)

```python
# hands-on/m02/telemetry_core.py
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def initialize_telemetry(service_name: str = "ai-customer-agent", environment: str = "production") -> trace.Tracer:
    """
    Menginisialisasi OpenTelemetry TracerProvider dengan konfigurasi enterprise.
    Mendukung export via OTLP gRPC ke Collector dan fallback Console di non-prod.
    """
    resource = Resource.create(attributes={
        SERVICE_NAME: service_name,
        SERVICE_VERSION: "2.4.1",
        "deployment.environment": environment,
        "telemetry.sdk.language": "python"
    })

    provider = TracerProvider(resource=resource)
    
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    
    # Gunakan OTLP Exporter untuk ingestion produksi
    try:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter, max_queue_size=2048, max_export_batch_size=512))
    except Exception as e:
        # Fallback debug mode
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)

tracer = initialize_telemetry()
```

#### Step 2: Agent Telemetry Instrumentation dengan PII Redaction (`agent_pipeline.py`)

```python
# hands-on/m02/agent_pipeline.py
import time
import re
import json
from typing import Dict, Any
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from telemetry_core import tracer

class EnterpriseAgentTelemetry:
    @staticmethod
    def sanitize_pii(text: str) -> str:
        """Masking email dan kartu kredit langsung pada layer pembuat trace."""
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        cc_pattern = r'\b(?:\d{4}[ -]?){3}\d{4}\b'
        
        redacted = re.sub(email_pattern, "[REDACTED_EMAIL]", text)
        redacted = re.sub(cc_pattern, "[REDACTED_CC]", redacted)
        return redacted

def execute_agent_workflow(user_id: str, tenant_id: str, prompt: str) -> Dict[str, Any]:
    """
    Mengorkestrasikan workflow agen dengan telemetri tingkat dalam.
    """
    # Root Span: Mengelompokkan seluruh turn pengguna
    with tracer.start_as_current_span("agent_execution_turn") as root_span:
        root_span.set_attribute("tenant.id", tenant_id)
        root_span.set_attribute("user.id_hashed", str(hash(user_id)))
        root_span.set_attribute("gen_ai.prompt_sanitized", EnterpriseAgentTelemetry.sanitize_pii(prompt))
        
        start_time = time.time()
        
        # 1. Retrieval Phase (Vector Store)
        with tracer.start_as_current_span("retrieval_step") as retrieve_span:
            retrieve_span.set_attribute("rag.top_k", 5)
            # Simulasi retrieval
            time.sleep(0.08)
            docs_retrieved = 3
            retrieve_span.set_attribute("rag.docs_retrieved_count", docs_retrieved)
            retrieve_span.set_attribute("rag.latency_ms", 80.0)

        # 2. Reasoning & Inference Phase
        with tracer.start_as_current_span("llm_reasoning_step") as llm_span:
            llm_span.set_attribute("gen_ai.system", "openai")
            llm_span.set_attribute("gen_ai.request.model", "gpt-4-turbo")
            llm_span.set_attribute("gen_ai.request.temperature", 0.2)
            
            # Simulasi Time-to-First-Token (TTFT)
            ttft_simulated_ms = 240.0
            time.sleep(0.24)
            llm_span.set_attribute("gen_ai.metrics.ttft_ms", ttft_simulated_ms)
            
            # Simulasi LLM processing tokens
            time.sleep(0.16)
            input_tokens = 840
            output_tokens = 95
            
            # Kalkulasi Unit Economics per execution
            cost_usd = (input_tokens * 0.00001) + (output_tokens * 0.00003)
            
            llm_span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            llm_span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
            llm_span.set_attribute("gen_ai.usage.cost_usd", cost_usd)

        # 3. Tool Calling Phase
        with tracer.start_as_current_span("tool_invocation") as tool_span:
            tool_name = "database_ledger_lookup"
            tool_span.set_attribute("gen_ai.tool.name", tool_name)
            tool_span.set_attribute("gen_ai.tool.call_id", "call_abc123")
            
            try:
                # Simulasi eksekusi tool berhasil
                time.sleep(0.12)
                tool_span.set_attribute("gen_ai.tool.status", "success")
                tool_span.set_status(Status(StatusCode.OK))
            except Exception as ex:
                tool_span.set_status(Status(StatusCode.ERROR, str(ex)))
                tool_span.record_exception(ex)
                raise ex

        total_latency = (time.time() - start_time) * 1000
        root_span.set_attribute("agent.total_duration_ms", total_latency)
        root_span.set_status(Status(StatusCode.OK))
        
        return {
            "status": "COMPLETED",
            "latency_ms": total_latency,
            "cost_usd": cost_usd,
            "resolution": "Success"
        }

if __name__ == "__main__":
    result = execute_agent_workflow(
        user_id="usr_88231948",
        tenant_id="enterprise_client_7",
        prompt="Mohon periksa status transfer dengan nomor kartu 4532-1234-5678-9012 dan email john.doe@acme.corp"
    )
    print("Execution Result:", json.dumps(result, indent=2))
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks Klien
* **Entitas**: Neobank Tier-1 (18 Juta Pengguna Aktif).
* **Produk**: "Apex Concierge" – Autonomous Financial Support Agent.
* **Beban Sistem**: 35 Juta Event Telemetri/hari, ~800 Agent Request per detik saat *peak hour*.

#### Problem Statement
1. **Cost Blackhole**: Pengeluaran token API melonjak 420% ($180.000/bulan) tanpa korelasi langsung terhadap kenaikan Resolution Rate.
2. **Context Window Drift**: Agent berulang kali terjebak dalam recursive looping (memanggil tools berulang dengan argumen identik) saat user memberikan prompt ambigu.
3. **Data Privacy Breach Risk**: Telemetri mentah di logs ElasticSearch mengandung Nomor Rekening dan PII nasabah, terancam denda regulasi GDPR/PCI-DSS.

#### Solusi Arsitektur
1. **Edge PII Redaction Tier**: Menempatkan lightweight Envoy WebAssembly (Wasm) filter di depan ingestion agent yang menghapus PII sebelum OTel SDK memproses payload.
2. **Deterministic Loop Telemetry & Circuit Breaking**:
   * Implementasi OTel span hook yang menghitung hash unik dari kombinasi `(tool_name, tool_arguments)`.
   * Jika hash yang sama terdeteksi $\ge 3$ kali dalam satu root trace, telemetri memicu alert real-time via Kafka ke Flink, dan runtime mengeksekusi *graceful degradation* (menghentikan looping dan mengalihkan ke agen manusia).
3. **ClickHouse Multi-Dimensional Semantic Layer**:
   * Membangun metrik teragregasi: **Cost-to-Resolution (CTR)** dan **Token Waste Ratio (TWR)**.
   * Melakukan partisi data berdasarkan `tenant_id` dan `event_date` untuk analisis performa sub-detik.

#### Hasil Terukur (Measurable Metrics)
* **Token Cost Reduction**: Turun 38% dalam 30 hari pertama melalui identifikasi dan eliminasi redundant prompt loops.
* **Resolution Rate Visibility**: TPM menemukan bahwa prompt dengan token input > 2.500 mengalami penurunan *task resolution rate* sebesar 44%, memicu refaktorisasi strategi context truncation RAG.
* **Zero Compliance Violation**: Audit PCI-DSS lulus 100% tanpa temuan data nasabah terekspos pada observability sinks.

---

### 9. Trade-offs: Architectural Decision Matrix

Bagi Technical Product Manager, memilih arsitektur telemetri adalah kompromi konstan antara observabilitas, beban latensi runtime, dan biaya komputasi infrastruktur.

```
       [High Precision / Zero Sampling]
                     ▲
                     │   Arsitektur Finansial / Compliance
                     │   (100% Spans, Storage Cost Tinggi, Latensi IO)
                     │
                     │            Arsitektur Ideal Enterprise
                     │            (Tail-Based Adaptive Sampling)
                     │
                     +---------------------------------------► [Ultra Low Latency]
                    / \                                         (Zero Blocking, Drop Logs,
                   /   \                                         Head-Sampling 1%)
                  /     \
                 /       \
[Cost Optimized / Minimal Metrics]
```

| Dimensi Arsitektur | Pilihan A: Head-Based Sampling | Pilihan B: Tail-Based Sampling (Direkomendasikan) | Trade-off Impact |
| :--- | :--- | :--- | :--- |
| **Mekanisme Pengambilan Keputusan** | Keputusan trace disimpan atau dibuang dibuat di awal (Client/Ingress Gateway). | Keputusan dibuat setelah seluruh siklus eksekusi agen selesai di OTel Collector tier. | Pilihan B menangkap 100% error dan anomali, namun menuntut buffer memori besar di Collector. |
| **Observabilitas Anomali** | Buruk. Skenario *rare-bug* (terjadi di 0.1% transaksi) berisiko besar terbuang jika sampling rate 5%. | Sempurna. Trace yang lambat (>p95) atau berstatus `ERROR` dipaksa disimpan 100%. | Pilihan B meningkatkan utilisasi CPU collector sebesar 15-25%. |
| **Infrastruktur & Storage Cost** | Rendah. Payload langsung dipangkas sejak awal sebelum masuk jaringan analitik. | Menengah-Tinggi. Memerlukan klaster collector stateful dan bandwidth ingestion lebih tinggi. | Biaya infra telemetri Pilihan B terbayar lunas dengan penghematan debug time engineer dan reduksi AI API waste. |
| **Dampak Latensi Client** | Hampir 0 ms. | Hampir 0 ms (selama worker ekspor bersifat asinkron via shared memory buffer). | Memerlukan isolasi proses (daemon/sidecar) agar memory pressure telemetri tidak menyebabkan OOM pada Agent Runtime. |

---

### 10. Common Mistakes & Troubleshooting

Berikut adalah 5 anti-pattern umum dalam telemetri AI Agent yang sering dijumpai di level enterprise beserta tindakan korektifnya:

#### Anti-Pattern 1: Logging Seluruh Raw Output Model ke Span Attributes
* **Dampak**: Ukuran payload OpenTelemetry membengkak drastis. Database OLAP mengalami degradasi performa I/O (*disk bloat*), dan risiko kebocoran PII meningkat drastis.
* **Root Cause**: Developer memperlakukan span attributes seperti dump log unstructured.
* **Solusi**: Jangan simpan raw string payload output lengkap di span metrics. Simpan hanya **hash token**, **eval semantic vector summary**, atau batasi string hingga maksimal 256 karakter (truncated), simpan payload lengkap terenkripsi di S3/Cold Storage dengan retensi ketat (TTL 7 hari).

#### Anti-Pattern 2: Cardinality Explosion pada Metric Dimensions
* **Dampak**: Sistem time-series (Prometheus/DataDog) crash atau biaya billing bulanan melonjak ribuan dolar.
* **Root Cause**: Memasukkan `user_id`, `prompt_text`, atau `trace_id` sebagai *Tag/Dimension* dalam metrik Prometheus alih-alih di Span Attribute Distributed Tracing.
* **Solusi**: Terapkan segregasi tegas:
  * **Metrics Tag**: Hanya untuk data kardinalitas rendah/terbatas (misal: `model_name`, `status_code`, `tenant_tier`, `error_type`).
  * **Trace Attribute**: Untuk data kardinalitas tinggi (`trace_id`, `user_id_hash`, `execution_id`).

#### Anti-Pattern 3: Mengabaikan Asynchronous Context Propagation
* **Dampak**: Jejak eksekusi terputus saat Agent mendelegasikan tugas ke worker background (Celery, Temporal, atau goroutine terpisah). Trace terfragmentasi menjadi ribuan trace yatim-piatu (*orphan spans*).
* **Root Cause**: Tidak mengekstraksi dan menyuntikkan (*inject/extract*) header `W3C TraceContext` (`traceparent`) saat melempar job ke queue.
* **Solusi**: Terapkan wrapper middleware wajib pada message broker serializer yang mem-passing context metadata secara eksplisit.

#### Anti-Pattern 4: Tidak Mengukur Time-to-First-Token (TTFT) Secara Terisolasi
* **Dampak**: Dashboard produk menunjukkan latensi 8 detik, namun TPM tidak mengetahui apakah masalah berasal dari LLM inference provider yang lambat, proses RAG yang tidak efisien, atau rendering client.
* **Root Cause**: Hanya mengukur total response duration (*end-to-end latency*).
* **Solusi**: Wajib instrumentasikan TTFT sebagai span tersendiri sejak request inference dikirim hingga chunk pertama tiba di stream buffer.

#### Anti-Pattern 5: Missing Metric Semantics Versioning
* **Dampak**: Data scientist dan TPM menganalisis metrik "Resolution Rate", tetapi formula berubah di rilis sprint lalu tanpa dokumentasi, membuat perbandingan historis menjadi tidak valid (*apples-to-oranges*).
* **Root Cause**: Definisi metrik langsung dikodekan di script visualisasi BI (Metabase/Tableau) bukan di semantic layer terpusat.
* **Solusi**: Gunakan Semantic Metric Layer terpusat berbasis code seperti **dbt Semantic Layer** atau **Cube.js** dengan deklarasi YAML yang terdokumentasi dan terversi di Git.

---

### 11. Best Practices (Production Checklist)

Gunakan checklist ini sebelum merilis sistem AI Agent ke lingkungan Production:

#### 1. Security & Compliance
- [ ] **Data Redaction**: Wajib ada pipeline PII masking lokal sebelum event meninggalkan server host runtime.
- [ ] **Context Sanitization**: Verifikasi bahwa token otentikasi internal (*bearer tokens*, *DB passwords*) dihapus dari metadata tool-calling.
- [ ] **Data Retention**: Atur retensi data trace analitik (hot storage: 14 hari, warm: 60 hari, cold/iceberg: 1 tahun).

#### 2. Scalability & Resilience
- [ ] **Out-of-Process Collection**: Instrumentasi menggunakan OTel Collector sidecar atau daemon set independen, bukan sink langsung dari runtime ke database.
- [ ] **Circuit Breakers**: Ingestion pipeline memiliki safety buffer disk lokal jika streaming broker (Kafka) down, sehingga aplikasi utama tidak crash (*fail-open policy*).
- [ ] **Batching Strategy**: Flush interval diset optimal (misal: setiap 1 detik atau 512 traces) untuk meminimalkan network roundtrip.

#### 3. Operational Telemetry Completeness
- [ ] **Four Golden Signals AI Terpenuhi**: Latency (TTFT & TPOT), Traffic (Tokens/sec, Requests/sec), Errors (Tool-fail, Hallucination, Timeout), Saturation (Context Limit %).
- [ ] **Trace Hierarchy Standardization**: Semua agent run memiliki satu root span task, dan setiap tool/LLM call adalah child span langsung.
- [ ] **Error Categorization**: Semua error diklasifikasikan ke dalam kategori standar: `MODEL_TIMEOUT`, `RATE_LIMIT_EXCEEDED`, `SCHEMA_VALIDATION_ERROR`, `GUARDRAIL_INTERVENTION`.

---

### 12. Hands-on Practice

Dalam latihan ini, Anda akan menyiapkan lingkungan telemetri produksi mini menggunakan Docker Compose, mengeksekusi OTel Collector, ClickHouse sebagai analytical store, dan menjalankan script Python yang memancarkan telemetri AI Agent.

#### Struktur Direktori Target:
```
hands-on/m02/
├── docker-compose.yml
├── otel-collector-config.yaml
├── clickhouse-init.sql
├── telemetry_core.py
└── agent_pipeline.py
```

#### Step 1: Konfigurasi Observability Stack (`docker-compose.yml`)

```yaml
# hands-on/m02/docker-compose.yml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.95.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC receiver
      - "4318:4318" # OTLP HTTP receiver
    depends_on:
      - clickhouse

  clickhouse:
    image: clickhouse/clickhouse-server:24.2
    ports:
      - "8123:8123" # HTTP interface
      - "9000:9000" # Native client
    volumes:
      - ./clickhouse-init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      - CLICKHOUSE_DB=analytics
      - CLICKHOUSE_USER=default
      - CLICKHOUSE_PASSWORD=secret
```

#### Step 2: Konfigurasi OpenTelemetry Collector Pipeline (`otel-collector-config.yaml`)

```yaml
# hands-on/m02/otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 1s
    send_batch_size: 256

exporters:
  logging:
    verbosity: detailed
  otlp/clickhouse:
    endpoint: "clickhouse:4317"
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

#### Step 3: Skema Ingestion ClickHouse Analytics (`clickhouse-init.sql`)

```sql
-- hands-on/m02/clickhouse-init.sql
CREATE DATABASE IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.agent_traces (
    timestamp DateTime64(6) CODEC(DoubleDelta, LZ4),
    trace_id String CODEC(ZSTD(1)),
    span_id String CODEC(ZSTD(1)),
    tenant_id LowCardinality(String),
    service_name LowCardinality(String),
    span_name LowCardinality(String),
    duration_ms Float64 CODEC(Gorilla, ZSTD),
    ttft_ms Float64 CODEC(Gorilla, ZSTD),
    input_tokens UInt32 CODEC(T64, ZSTD),
    output_tokens UInt32 CODEC(T64, ZSTD),
    cost_usd Float64 CODEC(Gorilla, ZSTD),
    status_code LowCardinality(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (tenant_id, service_name, span_name, timestamp);
```

#### Step 4: Menjalankan Environment dan Trigger Event
Jalankan instruksi berikut melalui terminal:
```bash
# 1. Navigasi ke direktori hands-on
cd hands-on/m02/

# 2. Nyalakan cluster telemetri
docker compose up -d

# 3. Verifikasi container berjalan
docker compose ps

# 4. Install dependencies lokal
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

# 5. Jalankan script agent pipeline
python agent_pipeline.py

# 6. Periksa collector log untuk memverifikasi span ditangkap
docker compose logs otel-collector | grep "agent_execution_turn"
```

---

### 13. Exercise

#### Level: Easy
* **Tugas**: Tambahkan atribut span baru pada span `llm_reasoning_step` di file `agent_pipeline.py` yang mencatat *Cache Hit Ratio* (boolean: `rag.cache_hit`).
* **Kriteria Keberhasilan**: Span terekspor dengan atribut `rag.cache_hit = True` atau `False` dan tervalidasi di log OTel Collector.

#### Level: Medium
* **Tugas**: Modifikasi script `agent_pipeline.py` agar mengimplementasikan *Error Propagation*. Jika proses `tool_invocation` melempar `TimeoutError`, child span harus mencatat status `StatusCode.ERROR`, merekam exception stack trace, dan root span harus mencatat atribut `resolution = "FAILED_TOOL_TIMEOUT"`.
* **Kriteria Keberhasilan**: Error terekam secara terstruktur di span tanpa membuat script utama crash secara unhandled.

#### Level: Hard
* **Tugas**: Rancang query agregasi SQL analitik ClickHouse yang menghitung **p95 Latency**, **Total Cost USD**, dan **Average Token Waste Ratio (TWR)** per `tenant_id` selama 7 hari terakhir. Format hasil query harus siap digunakan sebagai data source dashboard C-Level.
* **Kriteria Keberhasilan**: Kueri SQL memanfaatkan optimasi partisi dan aggregations engine bawaan ClickHouse secara efisien tanpa *full table scan*.

---

### 14. Challenge

**Studi Kasus**: Anda memimpin produk B2B SaaS "Enterprise Legal Mind" yang melayani 50 law firm global. Karena aturan perlindungan data klien yang sangat ketat (Zero-Data Retention Policy):
1. **Aturan Kepatuhan**: Konten teks prompt pengguna maupun output LLM dilarang keras menyentuh disk log analitik dalam bentuk plaintext maupun reversible ciphertext.
2. **Kebutuhan Analisis**: Tim Product Management tetap wajib mendeteksi anomali:
   * Mengetahui topik legal apa yang paling sering memicu halusinasi tanpa membaca isi dokumennya.
   * Mengetahui sub-agent mana yang paling sering gagal melakukan kalkulasi klausa kontrak.
   * Mendeteksi fraud/abusive token usage per tenant secara real-time.

**Tantangan**: 
Rancanglah dokumen arsitektur teknis setebal 1 halaman yang merinci:
* Arsitektur hashing, embeddings, dan feature-extraction di sisi client/memory.
* Desain payload OpenTelemetry Semantic Convention kustom yang mematuhi Zero-Data Retention.
* Alur pendeteksian anomali real-time menggunakan streaming metrics tanpa melanggar batasan hukum legal compliance tersebut.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (5 Soal)
1. **Apa perbedaan mendasar antara Trace ID dan Span ID dalam distributed tracing?**
   * *Jawaban*: Trace ID mewakili keseluruhan perjalanan request dari ujung ke ujung melalui seluruh sistem terdistribusi, sedangkan Span ID mewakili satu unit kerja individual spesifik di dalam trace tersebut.
2. **Apa yang dimaksud dengan TTFT pada model LLM dan mengapa metrik ini krusial bagi Product Manager?**
   * *Jawaban*: TTFT (*Time-to-First-Token*) adalah durasi dari saat pengguna mengirim request hingga token respons pertama di-render. Metrik ini krusial karena menentukan *perceived latency* (responsivitas yang dirasakan pengguna).
3. **Mengapa menyimpan data kardinalitas tinggi seperti `user_id` ke dalam Prometheus metric tags dianggap anti-pattern fatal?**
   * *Jawaban*: Menyebabkan *cardinality explosion*, yang membuat memory footprint time-series database membengkak tak terkendali dan dapat merobohkan sistem monitoring.
4. **Apa fungsi utama dari OpenTelemetry Collector dalam arsitektur analitik modern?**
   * *Jawaban*: Berfungsi sebagai proxy independen yang menerima, memproses (filtering, batching, masking, sampling), dan mengekspor data telemetri ke satu atau beberapa storage backend tanpa membebani runtime aplikasi utama.
5. **Dalam konteks unit economics AI, apa formula dasar untuk menghitung Total Cost per Task Execution?**
   * *Jawaban*: $\text{Cost} = (\text{Input Tokens} \times \text{Input Price/Token}) + (\text{Output Tokens} \times \text{Output Price/Token}) + \sum(\text{Tool/API Call Costs})$.

#### Bagian 2: Intermediate (5 Soal)
1. **Dalam Tail-based Sampling, kapan keputusan untuk menyimpan atau membuang trace diambil? Mengapa pendekatan ini lebih disukai untuk debugging AI Agent dibanding Head-based Sampling?**
   * *Jawaban*: Keputusan diambil di akhir workflow setelah trace selesai secara utuh. Ini disukai pada sistem AI karena kita dapat memprogram kolektor untuk menyimpan 100% trace yang berakhir dengan error atau loop halusinasi, sementara trace yang sukses cepat dapat disampling rendah guna menghemat biaya penyimpanan.
2. **Sebuah sistem AI Agent menggunakan multi-agent delegation (Agent Supervisor memanggil 3 Sub-Agent asinkron). Bagaimana cara tracing engine memastikan spans dari 3 sub-agent tersebut terhubung ke root span yang benar?**
   * *Jawaban*: Menggunakan *Context Propagation* (standar W3C TraceContext) di mana `traceparent` (Trace ID dan Parent Span ID) diinjeksi ke metadata pesan/job queue dan diekstraksi oleh sub-agent saat memulai komputasinya.
3. **Bagaimana cara mendeteksi silent semantic failure (halusinasi) melalui korelasi metrik produk dan telemetri runtime?**
   * *Jawaban*: Mengkorelasikan sinyal balik implisit pengguna (misal: user langsung menekan tombol *regenerate*, membatalkan aksi, atau mengedit teks secara masif dalam tempo <5 detik) dengan metadata trace inference bersangkutan.
4. **Apa perbedaan antara model OLTP (PostgreSQL) dan Real-time OLAP (ClickHouse) dalam konteks penyimpanan data analitik produk?**
   * *Jawaban*: OLTP dioptimalkan untuk operasi row-level transaction berbasis ACID dengan write throughput rendah-sedang, sedangkan ClickHouse (OLAP) dioptimalkan untuk batch write masif dan aggregasi kolom (columnar storage) pada miliaran baris data dengan kecepatan baca tinggi.
5. **Mengapa redaksi PII harus dilakukan di memory level runtime atau sidecar lokal, dan bukan di layer database warehouse analitik?**
   * *Jawaban*: Karena data yang sudah masuk ke pipeline jaringan dan transit di Kafka/S3 berisiko terekspos log leakage, melanggar prinsip *least privilege*, dan gagal mematuhi regulasi privasi data seperti GDPR yang melarang penyimpanan data sensitif sejak titik ingress.

#### Bagian 3: Skenario Kasus Produksi (3 Soal)

1. **Skenario 1: Insiden Latency Spike**
   * *Kasus*: Dashboard produk menunjukkan p99 latency untuk fitur "Agent Contract Summarizer" naik dari 2.1 detik menjadi 34 detik. Biaya API OpenAI naik 3x lipat dalam periode yang sama.
   * *Analisis & Solusi PM*: 
     1. Buka distributed tracing, filter span `agent_execution_turn` dengan durasi > 30s.
     2. Periksa child spans: Apakah lonjakan disebabkan oleh TTFT (antrean OpenAI), durasi transfer chunk (output tokens memanjang drastis), atau RAG retrieval?
     3. Jika ditemukan output tokens mencapai limit maksimal (context exhaustion) akibat prompt injection atau prompt ambiguity yang memicu runaway generation, pasang `max_tokens` limit yang ketat dan implementasikan early-stop circuit breaker pada inference layer.

2. **Skenario 2: Margin Degradation pada Tenant Tertentu**
   * *Kasus*: Satu tenant enterprise tier fixed-price menyumbang 40% dari total pengeluaran LLM perusahaan Anda, membuat margin kotor tenant tersebut negatif (-15%).
   * *Analisis & Solusi PM*:
     1. Kueri ClickHouse Semantic Layer: Agregasi `cost_usd` grouped by `tenant_id` dan `tool_name`/`feature_name`.
     2. Identifikasi pola: Apakah tenant menggunakan agent untuk tugas di luar cakupan yang dirancang (edge-case use case)?
     3. Terapkan Rate-Limiting berbasis Token Budgeting per tenant di level API Gateway dan rekomendasikan model switching (downgrade dari model flagship ke model *distilled/small* untuk retrieval-task sederhana tenant tersebut).

3. **Skenario 3: Telemetry Backpressure Memperlambat Core Agent**
   * *Kasus*: Saat beban pengguna naik ke 1.000 RPS, agen mengalami perlambatan respons sebesar 400ms. Profiling menunjukkan CPU throttling terjadi pada worker Python runtime.
   * *Analisis & Solusi PM*:
     1. Evaluasi konfigurasi OTel SDK: Masalah terjadi karena exporter berjalan secara synchronous atau queue batch processor in-memory penuh, sehingga thread eksekusi utama terblokir saat mencoba mengekspor log telemetri ke Collector.
     2. Solusi: Ubah arsitektur ke *asynchronous non-blocking batch exporter* dengan memory limit bound dan *drop-on-overflow policy*, atau tulis telemetri ke local UNIX domain socket / shared memory yang dikonsumsi oleh OTel Collector sidecar yang berjalan independen.

---

### 16. Summary

1. **Paradigma Baru**: Observabilitas sistem AI dan Autonomous Agents menuntut peralihan dari pelacakan event deterministik sederhana menuju **Deep Tracing Terdistribusi Multidimensi** yang menggabungkan konteks UX, logika reasoning algoritma, dan konsumsi token ekonomis.
2. **Standar Industri**: Mengadopsi **OpenTelemetry GenAI Semantic Conventions** menjamin fleksibilitas sistem analitik jangka panjang, mencegah *vendor lock-in* pada proprietary monitoring tool, dan memungkinkan interoperabilitas data telemetri.
3. **Arsitektur Berkelanjutan**: Arsitektur analitik enterprise yang tangguh dibangun di atas pemisahan peran yang tegas: pengumpulan data asinkron non-blocking, transport decoupled via Kafka, agregasi ultra-cepat via Real-Time OLAP (ClickHouse), dan konsolidasi metrik bisnis yang terdefinisi rapi pada Semantic Metric Layer.
4. **Kepemimpinan Produk**: Technical PM modern tidak hanya menganalisis retensi dan konversi, tetapi wajib menguasai profil latensi teknis (TTFT, TPOT), efisiensi tool execution, dan unit economics granular untuk membangun produk AI yang scalable, secure, dan profitable.