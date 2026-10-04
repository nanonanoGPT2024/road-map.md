# Bab 03: Product Analytics, Telemetry & Metric Architecture
## Modul 01: Telemetri Agen Otonom & Arsitektur Observabilitas Produk AI

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Product Manager teknis dan AI Architect diharapkan mampu:
*   **Merancang Taksonomi Metrik Hierarkis (L1–L4)** yang memetakan performa non-deterministik sistem agen ke *Key Performance Indicators* (KPI) bisnis secara kuantitatif.
*   **Menyusun Spesifikasi Instrumentasi Telemetri** berbasis standar industri (*OpenTelemetry GenAI Semantic Conventions*) untuk melacak eksekusi multi-langkah (*multi-step reasoning/ReAct loops*).
*   **Mengintegrasikan Kerangka Evaluasi Daring (*Online Evals as Telemetry*)** untuk mendeteksi degradasi model (*drift*), halusinasi, dan *tool-execution errors* secara *real-time*.
*   **Menghitung dan Mengoptimalkan *Unit Economics* Agen Otonom** menggunakan formulasi *Cost-per-Task-Resolved* (CPTR) terhadap ambang batas latensi (*Time-to-First-Token* dan durasi eksekusi penuh).
*   **Menganalisis dan Mendiagnosis Mode Kegagalan Agen** melalui *Distributed Tracing* untuk membedakan antara kegagalan inferensi model, latensi dependensi API eksternal, dan kegagalan orkestrasi internal.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Mengelola telemetri produk deterministik konvensional (misalnya: *Clickstream*, *Pageviews*, *API status codes 2xx/5xx*) berbeda secara fundamental dengan produk bertenaga *AI/Autonomous Agents*. Agen otonom beroperasi dengan logika non-deterministik, interaksi berulang (*loops*), dan eksekusi dinamis yang memicu masalah "Kotak Hitam" (*Black Box Problem*).

```
[Mental Model: Deterministic vs. Agentic Observability]

DETERMINISTIC PIPELINE:
Input [A] ──────────> Logic [Rule-based] ──────────> Output [B]
                      (Status: 200 OK / 500 Error)

AGENTIC PIPELINE:
Input [Task] ───────> ReAct Loop: [Plan -> Tool -> Obs] ──(N Iterations)──> Final State
                      ├── LLM Inferensi (Tokens, Latency, Drift)
                      ├── External Tools (APIs, DBs, Vector Search)
                      └── State Memory (Context Drift, Context Window Saturation)
```

Untuk mengubah *Black Box* ini menjadi *Glass Box*, arsitektur telemetri agen mengadopsi **Empat Lapisan Metrik Produk AI (L1–L4 Metric Architecture)**:
1.  **L1: Business Value Metrics**: Dampak bisnis riil (*Task Completion Rate*, penghematan biaya operasional, CSAT pasca-resolusi).
2.  **L2: Product Experience Metrics**: Kualitas interaksi pengguna (*Time-to-First-Token/TTFT*, *Perceived Latency*, *Correction Loops/User Overrides*).
3.  **L3: Cognitive & Orchestration Metrics**: Efisiensi proses penalaran agen (*Tool Selection Accuracy*, *Step Count to Resolution*, *Context Drift Index*, *Hallucination Score* via *Evaluator Slaves*).
4.  **L4: Infrastructure & Computational Metrics**: Beban sistem (*Prompt/Completion Token Counts*, rasio *Cache Hit/Miss*, pemanfaatan GPU, *Cost per API Call*).

---

### 3. Why It Matters (Masalah Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan produksi enterprise, kegagalan observabilitas pada produk AI agen menimbulkan dampak fatal:
*   **The Silent Failure Problem**: Agen dapat mengembalikan status `HTTP 200 OK` dengan format sintaks sempurna, tetapi secara semantik keliru fatal (misalnya: salah membaca limit kredit pengguna atau mengeksekusi *refund* ganda). Tanpa telemetri semantik, metrik ketersediaan (*availability*) tampak hijau padahal produk merugikan pengguna.
*   **Runaway Execution & Cost Explosion**: Kegagalan agen dalam mendeteksi kriteria selesai (*stopping condition*) pada siklus ReAct dapat memicu *infinite loop*, menghabiskan jutaan token dalam hitungan menit. Enterprise memerlukan instrumen pemutus sirkuit (*circuit breaker*) berbasis telemetri.
*   **Auditabilitas & Regulasi**: Kerangka regulasi global (seperti *EU AI Act*) mewajibkan sistem otonom dengan risiko tinggi memiliki kemampuan audit jejak keputusan (*traceability*). PM harus dapat merekonstruksi *state space* agen pada langkah tertentu saat sebuah keputusan penting dieksekusi.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur telemetri agen modern memisahkan penangkapan jejak data (*instrumentation*), pengumpulan terdistribusi (*ingestion*), penyimpanan analitik bertingkat (*storage*), dan lapisan analisis/evaluasi.

```
+-----------------------------------------------------------------------------------+
|                            APLIKASI AGEN / RUNTIME                                |
|                                                                                   |
|  +--------------------+        +---------------------+      +------------------+  |
|  | Input Gateway      |        | ReAct Orchestrator  |      | Tool Execution   |  |
|  | (User Interaction) |        | (Prompting, Memory) |      | (DB, APIs, RAG)  |  |
|  +---------+----------+        +----------+----------+      +--------+---------+  |
+------------|------------------------------|--------------------------|------------+
             |                              |                          |
             | Tracing Hooks                | Tracing Hooks            | Tracing Hooks
             +------------------------------+--------------------------+
                                            |
                                            v
                +-------------------------------------------------------+
                |     In-Process OpenTelemetry (OTel) Tracer SDK        |
                |  - Enforce Semantic Conventions (LLM/Agent Spans)     |
                |  - Local Batching & Non-blocking In-Memory RingBuffer |
                +---------------------------+---------------------------+
                                            | OTLP/gRPC (Async)
                                            v
+-----------------------------------------------------------------------------------+
|                        INGESTION & OBSERVABILITY PLATFORM                         |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                         OpenTelemetry Collector                             |  |
|  |  - PII Masking Processor (Anonymize prompts & tool payloads)                |  |
|  |  - Tail-based Sampling Processor (100% trace error, 5% normal traces)       |  |
|  +--------------------------------------+--------------------------------------+  |
|                                         |                                         |
|                     +-------------------+-------------------+                     |
|                     |                                       |                     |
|                     v                                       v                     |
|    +---------------------------------+     +---------------------------------+    |
|    |      OLAP Columnar Store        |     |     Online Evals Engine         |    |
|    |     (ClickHouse / BigQuery)     |     |     (LLM-as-a-Judge Slaves)     |    |
|    |  - Fast aggregation on Token,   |     |  - Hallucination scoring        |    |
|    |    Latensi, Cost, Metadata      |     |  - Tool semantic validation     |    |
|    +----------------+----------------+     +----------------+----------------+    |
|                     |                                       |                     |
|                     +-------------------+-------------------+                     |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  |                       PM Analytics & Alerting Layer                         |  |
|  |  - Live Dashboards (Cost/Task, TTFT, Step Length)                           |  |
|  |  - Automated Circuit Breakers (Budget Cap, Anomaly Anomaly Alerts)          |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Standar Semantik OpenTelemetry untuk AI (OTel GenAI Semantic Conventions)
Setiap interaksi agen harus dimodelkan sebagai rentang kendali terdistribusi (*distributed span*). Span tidak hanya mencatat durasi, melainkan atribut semantik formal:
*   `gen_ai.system`: Identifikasi platform (e.g., `openai`, `anthropic`, `self-hosted-vllm`).
*   `gen_ai.request.model`: Model yang diminta (e.g., `gpt-4o`, `claude-3-5-sonnet`).
*   `gen_ai.usage.prompt_tokens` & `gen_ai.usage.completion_tokens`: Volume data komputasi.
*   `gen_ai.response.finish_reasons`: Terminasi model (`stop`, `length`, `tool_calls`).

#### B. Hierarki Span pada Agen Otonom (DAG Representation)
Eksekusi agen direpresentasikan sebagai *Directed Acyclic Graph* (DAG) dari span induk dan anak:
1.  **Trace Root (User Goal Span)**: "Selesaikan klaim asuransi #9021".
2.  **Child Span 1 (Agent Plan/Thought)**: Inferensi LLM untuk menentukan pemanggilan alat.
3.  **Child Span 2 (Tool Execution Span)**: Eksekusi SQL query ke sistem database klaim.
4.  **Child Span 3 (Observation Integration & Validation)**: Evaluasi hasil eksekusi tool.
5.  **Child Span 4 (Final Synthesis)**: Inferensi LLM merangkum jawaban akhir kepada pengguna.

#### C. Mekanisme Online Evaluation ("Evaluator Slaves")
Tidak semua trace dapat dinilai oleh manusia. Evaluasi telemetri daring bekerja secara asinkron:
*   Span yang telah selesai dikirim ke *Worker Queue* terisolasi.
*   Model kecil yang cepat dan murah (misal: *fine-tuned SLM* atau gpt-4o-mini) mengevaluasi trace menggunakan kriteria spesifik:
    *   **Groundedness Score** (0.0 - 1.0): Apakah output didukung konteks RAG?
    *   **Tool Efficiency Score** (0.0 - 1.0): Apakah tool yang dipanggil redundan?
*   Skor evaluasi ini kemudian di-*patch* kembali ke ID trace bersangkutan di OLAP store untuk kebutuhan agregasi metrik.

#### D. Formulasi Unit Economics: Cost per Resolved Task (CPTR)
PM AI wajib memantau CPTR, dirumuskan secara matematis sebagai berikut:

$$CPTR = \frac{\sum_{i=1}^{N} \left( P_{in} \cdot T_{in, i} + P_{out} \cdot T_{out, i} + C_{infra, i} \right) + \sum_{j=1}^{M} C_{tool, j}}{K}$$

Di mana:
*   $N$: Total pemanggilan LLM dalam satu sesi penyelesaian tugas.
*   $T_{in, i}, T_{out, i}$: Jumlah token *prompt* dan *completion* pada pemanggilan ke-$i$.
*   $P_{in}, P_{out}$: Biaya per unit token untuk *prompt* dan *completion*.
*   $C_{infra, i}$: Biaya komputasi hosting inferensi / memory cache.
*   $C_{tool, j}$: Biaya eksekusi API pihak ketiga pada pemanggilan tool ke-$j$.
*   $K$: Variabel biner bernilai $1$ jika *task* terselesaikan sukses secara valid (*verified by user / deterministic criteria*), dan $0$ jika gagal. Jika $K=0$, biaya dialokasikan ke metrik *Wasted Spend*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi *Instrumentation Engine* berbasis Python yang mematuhi standar OpenTelemetry untuk melacak eksekusi LLM dan Tool pada ReAct loop, dilengkapi kalkulasi biaya otomatis dan emisi telemetri terstruktur.

```python
# telemetry_engine.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentTelemetry")

@dataclass(frozen=True)
class ModelPricing:
    prompt_cost_per_1k: float
    completion_cost_per_1k: float

# Pricing catalog standar (USD)
PRICING_CATALOG: Dict[str, ModelPricing] = {
    "gpt-4o": ModelPricing(prompt_cost_per_1k=0.005, completion_cost_per_1k=0.015),
    "claude-3-5-sonnet": ModelPricing(prompt_cost_per_1k=0.003, completion_cost_per_1k=0.015),
}

@dataclass
class TelemetrySpan:
    span_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_span_id: Optional[str] = None
    trace_id: str = ""
    name: str = ""
    span_type: str = "internal"  # 'llm', 'tool', 'agent_step', 'root'
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "UNSET"  # 'OK', 'ERROR'
    error_message: Optional[str] = None

    def finish(self, status: str = "OK", error: Optional[str] = None) -> None:
        self.end_time = time.time()
        self.status = status
        self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        duration_ms = (self.end_time - self.start_time) * 1000 if self.end_time else 0.0
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "span_type": self.span_type,
            "duration_ms": round(duration_ms, 2),
            "status": self.status,
            "error_message": self.error_message,
            "attributes": self.attributes,
            "timestamp": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
        }

class AgentTelemetryContext:
    """
    Manajer Konteks Telemetri untuk Autonomous Agents.
    Menangani lifecycle pembuatan span hierarkis, pelacakan konsumsi token, dan kalkulasi unit economics.
    """
    def __init__(self, trace_id: Optional[str] = None, user_id: str = "anonymous"):
        self.trace_id: str = trace_id or str(uuid.uuid4())
        self.user_id: str = user_id
        self.active_spans: Dict[str, TelemetrySpan] = {}
        self.completed_spans: List[TelemetrySpan] = []
        self.total_cost_usd: float = 0.0

    def start_span(
        self,
        name: str,
        span_type: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> TelemetrySpan:
        span = TelemetrySpan(
            trace_id=self.trace_id,
            parent_span_id=parent_span_id,
            name=name,
            span_type=span_type,
            attributes=attributes or {},
        )
        # Injeksi context global
        span.attributes["user_id"] = self.user_id
        self.active_spans[span.span_id] = span
        return span

    def record_llm_execution(
        self,
        span_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        time_to_first_token_ms: Optional[float] = None,
    ) -> None:
        span = self.active_spans.get(span_id)
        if not span:
            logger.error("Span ID %s tidak ditemukan dalam active context.", span_id)
            return

        # Kalkulasi biaya inferensi
        pricing = PRICING_CATALOG.get(model, ModelPricing(0.0, 0.0))
        cost = (
            (prompt_tokens / 1000.0 * pricing.prompt_cost_per_1k)
            + (completion_tokens / 1000.0 * pricing.completion_cost_per_1k)
        )
        self.total_cost_usd += cost

        # Implementasi Semantic Conventions OTel GenAI
        span.attributes.update({
            "gen_ai.system": "openai" if "gpt" in model else "anthropic",
            "gen_ai.request.model": model,
            "gen_ai.usage.prompt_tokens": prompt_tokens,
            "gen_ai.usage.completion_tokens": completion_tokens,
            "gen_ai.usage.total_tokens": prompt_tokens + completion_tokens,
            "gen_ai.usage.cost_usd": round(cost, 6),
            "gen_ai.response.ttft_ms": time_to_first_token_ms,
        })

    def end_span(self, span_id: str, status: str = "OK", error: Optional[str] = None) -> TelemetrySpan:
        span = self.active_spans.pop(span_id, None)
        if not span:
            raise KeyError(f"Gagal menutup span: Span ID {span_id} tidak valid.")
        
        span.finish(status=status, error=error)
        self.completed_spans.append(span)
        return span

    def export_trace_telemetry(self) -> Dict[str, Any]:
        """
        Mengekspor metrik agregat terstruktur yang siap dikonsumsi oleh OLAP store / telemetry collector.
        """
        all_spans = [s.to_dict() for s in self.completed_spans]
        total_tokens = sum(
            s["attributes"].get("gen_ai.usage.total_tokens", 0) for s in all_spans
        )
        has_errors = any(s["status"] == "ERROR" for s in all_spans)

        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "total_spans": len(all_spans),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_tokens": total_tokens,
            "execution_status": "FAILED" if has_errors else "SUCCESS",
            "spans": all_spans,
        }

# =====================================================================
# CONTOH PENGGUNAAN PADA ORCHESTRATOR AGEN
# =====================================================================
def run_autonomous_agent_step(task: str, user_id: str) -> None:
    telemetry = AgentTelemetryContext(user_id=user_id)

    # 1. Root Span: Misi Utama Agen
    root_span = telemetry.start_span(name="ExecuteTask", span_type="root")

    try:
        # 2. Child Span: Langkah Perencanaan LLM
        plan_span = telemetry.start_span(
            name="PlanAction",
            span_type="llm",
            parent_span_id=root_span.span_id
        )
        
        # Simulasi LLM Processing
        time.sleep(0.15)  # Simulasi TTFT & decoding
        telemetry.record_llm_execution(
            span_id=plan_span.span_id,
            model="gpt-4o",
            prompt_tokens=450,
            completion_tokens=65,
            time_to_first_token_ms=120.5
        )
        telemetry.end_span(plan_span.span_id, status="OK")

        # 3. Child Span: Eksekusi Tool (misal: Database Lookup)
        tool_span = telemetry.start_span(
            name="QuerySQLDatabase",
            span_type="tool",
            parent_span_id=root_span.span_id,
            attributes={"tool.name": "postgres_query", "tool.query_length": 48}
        )
        
        # Simulasi Tool Processing
        time.sleep(0.08)
        telemetry.end_span(tool_span.span_id, status="OK")

        # Berhasil menyelesaikan misi
        telemetry.end_span(root_span.span_id, status="OK")

    except Exception as exc:
        telemetry.end_span(root_span.span_id, status="ERROR", error=str(exc))
        raise

    finally:
        # Cetak output telemetri (Di produksi: Kirim via OTLP/gRPC exporter)
        trace_payload = telemetry.export_trace_telemetry()
        print(json.dumps(trace_payload, indent=2))

if __name__ == "__main__":
    run_autonomous_agent_step(
        task="Ambil riwayat transaksi user ID 98213",
        user_id="usr_enterprise_001"
    )
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Penyebab | Dampak pada Sistem / Metrik | Strategi Mitigasi & Circuit Breaker |
| :--- | :--- | :--- | :--- |
| **Agent Reasoning Thrashing** | Agen gagal menyelesaikan target dan terjebak pemanggilan alat berulang (*endless ReAct loop*). | Eksplosi metrik `step_count`, latensi membengkak, pembengkakan biaya API secara eksponensial. | Pasang **Hard Execution Limits**: Maksimum $N$ langkah ($N \le 7$) atau maksimum batas token agregat trace ($Max \le 16.000$). Hentikan paksa dan alihkan ke human-fallback. |
| **High Cardinality Dimension Explosion** | PM/Developer memasukkan parameter dinamis (seperti seluruh teks prompt atau raw JSON payload) sebagai label/tag metrik. | Kerusakan performa database time-series (Prometheus/Grafana M3DB), *high query latency*, lonjakan tagihan monitoring. | Pisahkan **Metrics** dari **Traces**. Data teks/payload bervolume dinamis tinggi hanya diizinkan masuk ke *Trace Spans/Payload Store* (ClickHouse/Elasticsearch), bukan label metrik statis. |
| **Silent Cognitive Drift** | Model terus mengembalikan status HTTP 200 dengan latensi normal, namun kualitas reasoning menurun pasca model update vendor. | Degradasi kepuasan pengguna (*L1 metric drop*) tanpa adanya alarm sistem teknis (*L4 metric green*). | Terapkan **Evaluator Sampling Pipeline**: Evaluasi 10% sampel trace harian secara asinkron menggunakan LLM Judge independen terhadap metrik *Semantic Relevance* dan *Faithfulness*. |
| **Telemetry Ingestion Lag** | Terlalu banyak emisi log synchronous yang memblokir loop utama inferensi agen. | Peningkatan signifikan pada *Perceived Latency* (L2) yang diakibatkan oleh overhead pemantauan itu sendiri. | Wajib menggunakan pemrosesan telemetri asinkron dengan arsitektur *non-blocking buffer* (misal: ZeroMQ atau in-memory RingBuffer) yang di-*flush* dalam interval *batch* tertentu. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan perancangan telemetri agen melibatkan kompromi antara biaya infrastruktur, kemudahan pengelolaan, dan sensitivitas privasi data.

| Opsi Solusi | Kelebihan | Kekurangan | Konteks Penggunaan Ideal |
| :--- | :--- | :--- | :--- |
| **Managed AI Tracing SaaS**<br>*(e.g., Langfuse, Arize Phoenix Cloud)* | Fitur lengkap siap pakai (UI visualisasi prompt DAG, evaluasi otomatis out-of-the-box, setup cepat). | Biaya langganan SaaS meningkat sesuai volume trace; potensi kendala kedaulatan data (Data Sovereignty/GDPR). | Startups hingga mid-enterprise yang membutuhkan *time-to-market* instan dan tidak dibatasi regulasi audit ketat. |
| **Self-Hosted OpenTelemetry + ClickHouse Stack** | Kontrol data 100%, sangat murah pada volume masif, mematuhi standar terbuka (*open-standard*). | Butuh alokasi engineer khusus untuk me-maintain collector, kluster ClickHouse, dan mendesain dasbor analitik sendiri. | Enterprise skala besar dengan regulasi privasi data perbankan/kesehatan yang memproses >10 juta token per hari. |
| **Traditional APM Adaptation**<br>*(e.g., Datadog LLM Observability)* | Satu panel instrumen (*single pane of glass*) dengan infrastruktur mikroservis backend non-AI yang sudah ada. | Ekosistem seringkali kurang fleksibel terhadap evaluasi semantik agen multi-step; biaya *custom metric* mahal. | Organisasi yang telah terikat kontrak jangka panjang dengan APM vendor dan ingin meminimalkan variasi stack DevOps. |

---

### 9. Best Practices & Standar Industri

1.  **Strict Masking & PII Redaction at Edge**: Data Masukan Pengguna (*Raw Prompts*) berpotensi mengandung kredensial, PII, atau data rahasia. Collector telemetri wajib menjalankan *regex scrubbing* atau Named Entity Recognition (NER) masking sebelum data dituliskan ke *Trace Log*.
2.  **Sampling Berbasis Kondisi (*Tail-based Sampling*)**: Hindari menyimpan 100% trace normal untuk menekan beban penyimpanan. Terapkan aturan:
    *   Trace dengan status `ERROR` $\rightarrow$ Simpan 100%.
    *   Trace dengan latensi $> p95$ $\rightarrow$ Simpan 100%.
    *   Trace dengan intervensi user (koreksi/dislike) $\rightarrow$ Simpan 100%.
    *   Trace standar (sukses, latensi normal) $\rightarrow$ Sampling 1% hingga 5%.
3.  **Definisikan SLI/SLO Berbasis Metrik AI PM**:
    *   *Service Level Indicator (SLI)*: Persentase tugas agen selesai dalam rentang $< 4$ langkah ReAct tanpa human takeover.
    *   *Service Level Objective (SLO)*: $\ge 92\%$ dari total sesi memenuhi SLI dalam siklus bulanan.
4.  **Version Every Artifact**: Setiap span telemetri wajib mencantumkan atribut `gen_ai.prompt.version`, `agent.version`, dan `tool.registry.hash` untuk memudahkan analisis regresi saat rilis prompt atau logika orkestrator baru.

---

### 10. Hands-on Lab Exercise: Diagnosis "Runaway Agent Loop"

#### Deskripsi Skenario
Sebuah agen otonom penyelesai tiket keluhan pengguna mengalami lonjakan tagihan token sebesar 400% dalam 24 jam terakhir. CSAT turun drastis karena pengguna melaporkan interaksi yang berulang-ulang tanpa solusi pasti. Sebagai AI PM, Anda diminta untuk menginvestigasi masalah ini dari jejak telemetri dan merumuskan kriteria penanganan.

#### Langkah 1: Analisis Query Telemetri (ClickHouse SQL)
Jalankan query analitik berikut untuk mengisolasi trace bermasalah:

```sql
SELECT 
    attributes['gen_ai.request.model'] AS model,
    count(span_id) AS total_steps,
    sum(CAST(attributes['gen_ai.usage.total_tokens'] AS UInt32)) AS aggregate_tokens,
    sum(CAST(attributes['gen_ai.usage.cost_usd'] AS Float64)) AS aggregate_cost,
    attributes['user_id'] AS user_id,
    trace_id
FROM agent_telemetry_spans
WHERE timestamp >= now() - INTERVAL 24 HOUR
GROUP BY trace_id, user_id, model
HAVING total_steps > 8 OR aggregate_cost > 0.10
ORDER BY aggregate_cost DESC
LIMIT 10;
```

#### Langkah 2: Evaluasi Span Log
Dari hasil query, ditemukan satu `trace_id` abnormal: `tr-8f921ab0`. Ambil kronologi span-nya:

```sql
SELECT 
    name, 
    span_type, 
    duration_ms, 
    status, 
    attributes['tool.name'] AS tool_called,
    attributes['error_message'] AS err
FROM agent_telemetry_spans
WHERE trace_id = 'tr-8f921ab0'
ORDER BY timestamp ASC;
```

*Diagnosa Temuan Telemetri*:
*   Span 1 (LLM Plan): Sukses. Agen memutuskan memanggil tool `fetch_order_status`.
*   Span 2 (Tool Execute): Gagal. Error: `Timeout: Database Read Replica Lag`.
*   Span 3 (LLM Plan): Agen mendeteksi tool gagal, mencoba memanggil `fetch_order_status` kembali dengan parameter identik.
*   Proses ini berulang sebanyak 12 kali (total 13 langkah identik) hingga context window penuh dan memicu pengeluaran 24.000 token pada satu tiket.

#### Langkah 3: Actionable Requirements untuk Tim Enjiniring
Sebagai Product Manager, formulasikan tiket perubahan teknis (*Engineering Task*) berdasarkan bukti telemetri:
1.  **Idempotency & Retry Circuit Breaker**: Jika tool yang sama menghasilkan error identik sebanyak 2 kali berturut-turut, agen dilarang melakukan pemanggilan ulang (*retry block*).
2.  **Context-Injection of Failure**: Inject pesan deterministik ke context LLM: *"Sistem database sedang mengalami gangguan sementara. Hentikan eksekusi pemanggilan database dan minta maaf secara sopan kepada pengguna."*
3.  **Alerting Setup**: Buat alert otomatis di Slack jika `step_count` suatu trace melebihi angka 5 pada lingkungan produksi.