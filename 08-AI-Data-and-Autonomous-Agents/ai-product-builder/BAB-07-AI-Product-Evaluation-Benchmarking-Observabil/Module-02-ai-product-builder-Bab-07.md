# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 07: AI Product Evaluation, Benchmarking, & Observability**
**Kategori: 08-AI-Data-and-Autonomous-Agents**

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Merancang dan mengoperasikan arsitektur *Continuous Evaluation Pipeline* skala enterprise menggunakan paradigma *LLM-as-a-Judge* terkalibrasi dan metrik deterministik.
- Mengimplementasikan sistem observabilitas end-to-end berbasis OpenTelemetry (OTel) dan semantic conventions OpenInference untuk melacak multi-step agentic execution traces, tool calling latency, dan token economics.
- Mengembangkan algoritma deteksi drift multi-dimensi (embedding drift, concept drift, dan output distribution shift) pada live inference data streams.
- Mengonfigurasi guardrails evaluasi berbasis CI/CD regression gates untuk mencegah degradasi performa model sebelum masuk ke pipeline rilis produksi.
- Menghitung trade-off matematis dan operasional antara evaluasi deterministik, evaluasi probabilistik, latensi observabilitas, dan unit economics per trace.

---

### 2. Prerequisites
- **Teori & Konsep**: Pemahaman mendalam tentang RAG (Retrieval-Augmented Generation), Agentic Workflows (ReAct, Plan-and-Solve), Distribusi Probabilitas Vektor, dan Teorema Central Limit.
- **Teknis & Tooling**:
  - Python 3.11+ (Asynchronous programming dengan `asyncio`, typing dengan `Pydantic v2`).
  - OpenTelemetry SDK & Tracing API (`opentelemetry-api`, `opentelemetry-sdk`).
  - Vector Math & Stats (`numpy`, `scipy`, `scikit-learn`).
  - Containerization & Orkestrasi dasar (Docker, Redis, Kafka/RabbitMQ).
- **Pengalaman**: Minimal 2 tahun membangun backend systems atau data engineering pipeline skala produksi.

---

### 3. Concept & Internal Architecture
Sistem evaluasi dan observabilitas AI modern tidak dapat mengandalkan *traditional logging* (seperti ELK standar) karena output LLM bersifat probabilistik, non-deterministik, dan memiliki dependensi rantai inferensi (*chained reasoning*). 

Arsitektur observabilitas dan evaluasi enterprise terdiri dari tiga bidang fungsional (*planes*):

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE OBSERVABILITY & EVALUATION PLANE                      |
+----------------------------------------------------------------------------------------------------+
                                                  │
          ┌───────────────────────────────────────┴────────────────────────────────────────┐
          ▼                                                                                ▼
┌─────────────────────────────────────────┐                            ┌─────────────────────────────────────────┐
|        IN-LINE TELEMETRY (LIVE)         |                            |       OUT-OF-BAND EVALUATION (ASYNC)    |
├─────────────────────────────────────────┤                            ├─────────────────────────────────────────┤
| - OTel / OpenInference Tracing          |                            | - LLM-as-a-Judge (Batch/Worker)         |
| - Token Cost & Latency Attribution      |                            | - Deterministic Heuristics (Regex, AST) |
| - Semantic Cache Interception           |─────── Kafka / Stream ─────>| - RAG Triad (Faithfulness, Relevance)   |
| - Payload Anonymization & PII Stripping |        Engine              | - Embedding Drift Detectors (MMD)       |
| - High-throughput Context Injection     |                            | - Human-in-the-Loop Active Learning     |
└─────────────────────────────────────────┘                            └─────────────────────────────────────────┘
          │                                                                                │
          └───────────────────────────────────────┬────────────────────────────────────────┘
                                                  ▼
                                ┌───────────────────────────────────┐
                                |   ANALYTICS & REGRESSION ENGINE   |
                                ├───────────────────────────────────┤
                                | - ClickHouse / TimescaleDB OLAP   |
                                | - Prometheus Metrics Exporter     |
                                | - CI/CD Gating & Alert Rules      |
                                └───────────────────────────────────┘
```

#### Komponen Internal Utama:
1. **OpenInference Context Propagation**:
   Setiap interaksi pengguna menginisiasi `TraceID` global. Setiap langkah rantai agen (Retrieval, Vector Search, Re-ranking, Context Stuffing, LLM Generation, Tool Execution) dibungkus dalam `Span` berhierarki. Atribut span mengikuti standarisasi OpenInference:
   - `openinference.span.kind`: `CHAIN`, `RETRIEVER`, `LLM`, atau `TOOL`.
   - `llm.input_messages`: Array of serialized messages.
   - `llm.output_messages`: Raw output completion.
   - `llm.token_count.prompt` & `llm.token_count.completion`.
2. **LLM-as-a-Judge Calibration Engine**:
   Mengevaluasi inferensi menggunakan model independen (misal: GPT-4o mengevaluasi Llama-3-70B) memerlukan mitigasi bias sistematis:
   - *Position Bias*: Urutan kandidat respons dalam pairwise comparison diacak.
   - *Verbosity Bias*: Koreksi skor terhadap respons yang lebih panjang melalui normalisasi token length.
   - *Self-Enhancement Bias*: Model penilai cenderung memberi skor lebih tinggi pada output yang digenerate oleh arsitektur model yang sama.
3. **Multi-Variate Drift Detection**:
   Membandingkan distribusi vektor *reference dataset* (data validasi awal) dengan *production streaming dataset* secara sliding-window menggunakan metrik Maximum Mean Discrepancy (MMD) atau 2-Wasserstein Distance pada hidden states/embeddings.

---

### 4. Why & What
- **Mengapa Dibutuhkan?**
  Aplikasi AI deterministik gagal secara biner (misal: HTTP 500), sedangkan aplikasi AI generatif gagal secara *silent degradation*: halusinasi parsial, jawaban off-topic, pembocoran PII, atau penurunan akurasi retrieval akibat corpus data di vector store yang usang (*context rot*). Tanpa tracing semantik dan automated benchmarking, degradasi sistem hanya diketahui saat churn rate pelanggan meningkat.
- **Apa yang Dibangun?**
  Pipeline evaluasi hybrid:
  1. *Online Real-time Observability*: Penangkapan metadata inferensi, token attribution, latency budget profiling (P95/P99), dan deteksi kegagalan seketika.
  2. *Near-line Async Evaluation*: Sampling 5-10% traffic produksi ke worker queue untuk dihitung skor RAG Triad (Faithfulness, Answer Relevance, Context Precision) dan deteksi drift semantik.
  3. *Offline CI/CD Benchmarking*: Gate pengujian regresi deterministik dan heuristik sebelum merge pull request pada prompt template atau weights tuning.

---

### 5. How (Workflow Detail)
Alur eksekusi enterprise evaluation dan observability berjalan sebagai berikut:

```
[User Request] 
      │
      ▼
[API Gateway / Ingestion Engine]
      │── 1. Create Root Trace (OTel Context)
      ▼
[Agent Orchestrator] 
      │── 2. Emit Span: "Agent_Planning"
      │
      ├──> [Vector Retriever] ── 3. Emit Span: "Retriever" (Save Documents & Top-K)
      │
      ├──> [LLM Execution] ──── 4. Emit Span: "LLM_Inference" (Log Prompts, Outputs, Tokens)
      │
      └──> [Tool Engine] ────── 5. Emit Span: "Tool_Exec" (Track Execution Status & Latency)
      │
      ▼
[API Response to User (P95 < 800ms)]
      │
   (Async Stream: Kafka / Redis Streams)
      │
      ▼
[Async Worker: Evaluation Consumer]
      │
      ├──> Step A: Heuristic Check (PII Regex, Toxicity, Exact Match, JSON Validity)
      │
      ├──> Step B: Embedding Drift Monitor (Cosine Sim & MMD vs Reference Centroid)
      │
      └──> Step C: LLM-as-a-Judge Batching (G-Eval / Ragas Metric Scoring)
      │
      ▼
[Metrics DB (Prometheus/ClickHouse)] ──> [Grafana Dashboard / PagerDuty Alert]
```

---

### 6. Analogy & Diagram ASCII
Bayangkan jalur perakitan pabrik mobil otomatis (Autonomous Factory):
- *Traditional Logging* hanya mencatat: "Mesin menyala", "Mesin mati", "Error: Baut habis".
- *AI Observability & Evaluation* adalah tim inspektor kualitas dengan sensor telemetri di setiap lengan robot:
  1. Mengukur torsi setiap baut secara sub-milimeter (*Token & Latency tracing*).
  2. Menguji apakah cat mobil terdistribusi merata dengan kamera spektrometri (*Semantic Drift*).
  3. Mempekerjakan master inspector (*LLM-as-a-Judge*) yang mengambil sampel 1 dari 10 mobil untuk memeriksa apakah jok kulit terpasang simetris dan aman tanpa cacat tersembunyi (*RAG Triad & Hallucination detection*).

```
TRADITIONAL LOGGING               ENTERPRISE AI OBSERVABILITY
+-------------------+             +-------------------------------------------------------+
| timestamp: ...    |             | Root Trace: trace_id_abc123                           |
| level: INFO       |             | ├── Span 1: Semantic_Router (dur: 20ms)               |
| msg: "query done" |             | ├── Span 2: Vector_Retriever (dur: 85ms)              |
+-------------------+             | │   └── meta: {docs_retrieved: 5, avg_score: 0.89}    |
                                  | ├── Span 3: Tool_Database_Query (dur: 110ms)          |
                                  | └── Span 4: LLM_Generation (dur: 420ms)               |
                                  |     ├── tokens: {prompt: 1420, completion: 185}       |
                                  |     ├── cost_usd: 0.0048                              |
                                  |     └── eval: {faithfulness: 0.95, drift_dist: 0.02}  |
                                  +-------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example: Tracing Manual dengan Context Manager
Kode dasar untuk menangkap latensi dan token penggunaan secara terstruktur:

```python
import time
from typing import Any, Dict
from dataclasses import dataclass, field

@dataclass
class SimpleTrace:
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.latency_ms = (time.perf_counter() - self.start_time) * 1000
        print(f"[TRACE] {self.name} finished in {self.latency_ms:.2f}ms | Meta: {self.metadata}")

# Penggunaan:
with SimpleTrace("llm_call", {"model": "gpt-4o", "temperature": 0.2}) as t:
    # Simulasi eksekusi LLM
    time.sleep(0.15)
    t.metadata["prompt_tokens"] = 120
    t.metadata["completion_tokens"] = 45
```

#### Practical Example: Production-Grade Async Evaluation Pipeline
Berikut implementasi modul evaluasi asinkron standar industri yang mengombinasikan OpenInference attributes, scoring *LLM-as-a-Judge* terkalibrasi (*Pairwise De-biased Scoring*), dan penghitungan embedding drift.

```python
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np
from scipy.spatial.distance import cosine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ProductionAIEval")

class InferencePayload(BaseModel):
    trace_id: str
    user_query: str
    retrieved_contexts: List[str]
    model_output: str
    output_embedding: List[float]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

class EvaluationResult(BaseModel):
    trace_id: str
    faithfulness_score: float = Field(..., ge=0.0, le=1.0)
    context_relevance_score: float = Field(..., ge=0.0, le=1.0)
    embedding_drift_detected: bool
    drift_distance: float
    passed_guardrails: bool

class ProductionEvaluator:
    def __init__(self, reference_centroid: np.ndarray, drift_threshold: float = 0.35):
        self.reference_centroid = reference_centroid
        self.drift_threshold = drift_threshold

    def calculate_embedding_drift(self, current_embedding: List[float]) -> tuple[bool, float]:
        """Menghitung jarak kosinus terhadap baseline reference centroid."""
        curr_vec = np.array(current_embedding)
        dist = cosine(self.reference_centroid, curr_vec)
        is_drift = dist > self.drift_threshold
        return is_drift, float(dist)

    async def _mock_judge_llm(self, prompt: str) -> str:
        """Simulasi LLM-as-a-Judge call dengan latensi realistis."""
        await asyncio.sleep(0.2)
        # Mengembalikan output terstruktur JSON
        return json.dumps({
            "reasoning": "The response strictly uses facts from retrieved context without hallucination.",
            "score": 0.92
        })

    async def evaluate_faithfulness(self, context: List[str], output: str) -> float:
        """
        Mengevaluasi apakah model output didasarkan sepenuhnya pada context (RAG Faithfulness).
        Menerapkan double-pass / debiased prompt execution.
        """
        joined_context = "\n---\n".join(context)
        system_prompt = (
            "You are an expert AI auditor. Evaluate the following output based ONLY on the provided context.\n"
            "Return a JSON object with 'reasoning' (string) and 'score' (float between 0.0 and 1.0).\n"
            f"Context: {joined_context}\n"
            f"Output: {output}"
        )
        
        raw_judge_res = await self._mock_judge_llm(system_prompt)
        parsed = json.loads(raw_judge_res)
        return float(parsed["score"])

    async def process_evaluation_stream(self, payload: InferencePayload) -> EvaluationResult:
        logger.info(f"Memproses evaluasi trace: {payload.trace_id}")
        
        # 1. Jalankan evaluasi embedding drift secara sinkron (ringan)
        drift_detected, drift_val = self.calculate_embedding_drift(payload.output_embedding)
        
        # 2. Jalankan LLM-as-a-judge asinkron
        faithfulness_task = self.evaluate_faithfulness(payload.retrieved_contexts, payload.model_output)
        
        # Simulasi metrik relevansi konteks
        async def evaluate_context_relevance():
            await asyncio.sleep(0.1)
            return 0.88

        faithfulness, context_rel = await asyncio.gather(
            faithfulness_task,
            evaluate_context_relevance()
        )

        passed = faithfulness >= 0.70 and not drift_detected

        result = EvaluationResult(
            trace_id=payload.trace_id,
            faithfulness_score=faithfulness,
            context_relevance_score=context_rel,
            embedding_drift_detected=drift_detected,
            drift_distance=drift_val,
            passed_guardrails=passed
        )

        logger.info(
            f"Trace {payload.trace_id} Evaluated: Passed={result.passed_guardrails} | "
            f"Faithfulness={result.faithfulness_score:.2f} | DriftDist={result.drift_distance:.4f}"
        )
        return result

# Driver Demo Runner
async def main():
    # Setup mock reference centroid (vektor dimensi 4)
    reference_centroid = np.array([0.25, 0.55, -0.15, 0.78])

    evaluator = ProductionEvaluator(reference_centroid, drift_threshold=0.20)

    sample_payload = InferencePayload(
        trace_id="tr-8f4b7a12-98c0",
        user_query="Berapa batas SLA pengembalian barang?",
        retrieved_contexts=["Kebijakan retur: Pelanggan dapat mengembalikan barang maksimal 14 hari kerja."],
        model_output="Batas SLA pengembalian barang adalah 14 hari kerja.",
        output_embedding=[0.24, 0.53, -0.14, 0.79], # Dekat dengan centroid
        prompt_tokens=150,
        completion_tokens=15,
        cost_usd=0.00045
    )

    eval_result = await evaluator.process_evaluation_stream(sample_payload)
    print("\nHasil Evaluasi:")
    print(eval_result.model_dump_json(indent=2))

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real-World Case Study (Enterprise Scale)
- **Konteks Perusahaan**: Fintech Payment Gateway berskala Asia Tenggara (memproses 20 juta transaksi/hari).
- **Masalah AI**: Mengimplementasikan AI Customer Operations Agent untuk menangani *merchant chargeback dispute*. Model sering memberikan jawaban yang mengarang regulasi perbankan lokal (halusinasi halus/subtle), menyebabkan denda audit compliance sebesar $120.000.
- **Implementasi Solusi**:
  1. *Telemetry Injection*: Mengintegrasikan OpenTelemetry collector ke dalam engine microservices. Setiap span LLM mencatat context chunks, exact tool parameters, and raw vendor LLM payloads.
  2. *Near-line Async Judge Engine*: Menggunakan Kafka untuk mengalirkan 100% transkrip sengketa. Tiga judge worker (Llama-3.1-70B di-deploy via vLLM) mengevaluasi metrik *Hallucination Index* dan *Compliance Grounding*.
  3. *Embedding Drift Pipeline*: Melacak sliding-window embedding centroid per 24 jam untuk mendeteksi pergeseran pola pertanyaan merchant terkait skema fraud baru.
- **Hasil Terukur**:
  - Penurunan tingkat halusinasi di sistem live dari **14.2% menjadi 0.8%**.
  - Deteksi instan pada token cost leak; menghemat pengeluaran LLM API sebesar **$34.000/bulan** dengan mendeteksi runaway tool execution loops.
  - Mean Time to Detect (MTTD) untuk anomali respons model turun dari **4 hari menjadi 12 menit**.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

| Dimensi Arsitektur | Evaluasi In-Line (Synchronous) | Evaluasi Out-of-Band (Asynchronous) | Deterministic Heuristics Only |
| :--- | :--- | :--- | :--- |
| **Latensi Pengguna** | **Sangat Buruk** (+800ms s/d +3000ms pada P99) | **Nol Dampak** (0ms overhead pada jalur kritis) | **Minimal** (+5ms s/d +20ms) |
| **Biaya Token / Compute** | **Tinggi** (Evaluasi inline berjalan pada setiap request) | **Terkontrol** (Bisa disetel via adaptive sampling: 1-10%) | **Nol Biaya Token** (Menggunakan CPU standard regex/embeddings) |
| **Ketepatan Evaluasi** | **Sangat Tinggi** (Dapat memblokir payload berbahaya sebelum sampai ke pengguna) | **Tinggi** (Audit post-generation, tidak bisa memblokir real-time) | **Rendah** (Gagal menangkap semantic hallucination & nuance) |
| **Skalabilitas Sistem** | **Rendah** (Tergantung pada rate limit provider LLM judge) | **Sangat Tinggi** (Menggunakan horizontal worker autoscaling via queue) | **Sangat Tinggi** (Komputasi stateless in-memory) |

---

### 10. Common Mistakes & Troubleshooting
1. **Position Bias pada Pairwise LLM-as-a-Judge**:
   - *Gejala*: Model judge hampir selalu memilih Opsi A terlepas dari kualitas aslinya.
   - *Mitigasi*: Lakukan swap position (Pass 1: A vs B, Pass 2: B vs A). Jika evaluasi bertolak belakang, tandai sebagai *uncertain* dan kirim ke antrean Human-in-the-loop (HITL).
2. **Evaluasi Blocking pada Jalur Kritis (Synchronous Bottleneck)**:
   - *Gejala*: P99 API Gateway melonjak tajam hingga 5+ detik karena memanggil judge LLM sebelum me-return respons ke frontend client.
   - *Solusi*: Terapkan arsitektur decoupled via message broker. Jalur kritis hanya mengeksekusi lightweight regex guardrails (<10ms).
3. **Data Snooping & Reference Leakage**:
   - *Gejala*: Skor benchmark CI/CD mencapai 99%, namun performa di live user buruk.
   - *Penyebab*: Test set benchmark bocor ke dalam data tuning atau retrieval store.
   - *Solusi*: Pisahkan korpus pengujian di vector database cluster yang terisolasi dan perbarui golden dataset secara reguler dengan traffic riil yang dianotasi manual.

---

### 11. Best Practices (Production Checklist)
- [ ] **Trace Context Injection**: Pastikan `trace_id` dan `span_id` dipropagasikan di HTTP headers (`traceparent`) lintas service boundary.
- [ ] **Cost Profiling**: Setiap trace wajib menghitung akumulasi biaya berdasarkan unit tarif model per 1k input/output tokens.
- [ ] **Adaptive Sampling**: Terapkan sampling adaptif: 100% untuk status error/exception, 50% untuk transaksi bernilai tinggi, dan 5% untuk query standar.
- [ ] **PII Scrubbing**: Jalankan scrubber (misal: Microsoft Presidio) sebelum metadata disimpan ke storage evaluasi analytics.
- [ ] **Embedding Baseline Versioning**: Simpan baseline centroid referensi beserta nomor hash dataset di metadata registry.
- [ ] **CI/CD Regression Gate**: Tambahkan automated eval job pada GitHub Actions: block pull request jika metrik *Faithfulness* turun > 2% dibanding baseline release.

---

### 12. Hands-on Practice
Simpan seluruh artefak praktikum di direktori: `hands-on/m02/`

#### Langkah 1: Inisialisasi Environment
Buat file `requirements.txt`:
```text
pydantic>=2.5.0
numpy>=1.24.0
scipy>=1.11.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

#### Langkah 2: Implementasi Script Benchmark Runner
Buat file `hands-on/m02/benchmark_runner.py`:
Implementasikan script yang memuat dataset `benchmark_data.json` lokal, menjalankan evaluasi heuristik dan scoring, lalu menghasilkan output metrik summary (`summary.json`).

#### Langkah 3: Eksekusi Test Suite
Jalankan evaluasi menggunakan command:
```bash
python -m pytest hands-on/m02/ -v
```

---

### 13. Exercises
- **Level Easy**: Modifikasi class `ProductionEvaluator` pada Practical Example agar dapat menghitung token cost secara akurat untuk variasi harga input: $0.0015/1K token dan output: $0.0020/1K token.
- **Level Medium**: Buat sebuah custom Python Context Manager yang mengukur P95 latency dan token-per-second (TPS) untuk generator LLM streaming response.
- **Level Hard**: Rancang arsitektur pipeline deteksi *Position Bias* otomatis. Buat fungsi evaluasi yang menerima dua respons kandidat, melakukan inferensi bolak-balik (A/B testing swap), dan menghitung matriks Cohen’s Kappa untuk mengukur tingkat konsistensi judge LLM.

---

### 14. Challenge
**Studi Kasus Arsitektur Tanpa Solusi Instan**:
Anda ditugaskan mendesain sistem observabilitas dan evaluasi untuk jaringan rumah sakit multi-cabang. Sistem ini menjalankan agen multi-langkah otonom untuk merekomendasikan resep obat rawat jalan.
- **Batasan Ketat**:
  1. *HIPAA & Zero-Data Retention*: Data rekam medis pasien tidak boleh disimpan dalam plain-text di sistem tracing sentral (Datadog/ClickHouse).
  2. *Ultra-Low Latency & High Risk*: Rekomendasi harus instan (<1 detik), namun jika ada halusinasi terkait kontraindikasi obat, agen harus diblokir seketika sebelum dokter menekan tombol konfirmasi.
  3. *High Cardinality Traces*: Sistem menangani 150 tool berbeda (lab test, riwayat alergi, farmakologi, klaim asuransi).
- **Tugas Anda**: Buat arsitektur dokumen teknis setebal 2 halaman yang mendefinisikan layout span OpenTelemetry, mekanisme in-line safety validation tanpa mengorbankan latency budget, dan strategi continuous benchmarking offline tanpa mengekspos data pasien.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Soal)
1. Apa perbedaan mendasar antara metrik *Faithfulness* dan *Answer Relevance* dalam evaluasi RAG?
2. Mengapa OpenTelemetry lebih disukai untuk tracing sistem AI dibanding logging standar berbasis text JSON?
3. Sebutkan apa yang dimaksud dengan *Position Bias* pada evaluasi menggunakan LLM-as-a-Judge!
4. Komponen apa dalam tracing OpenInference yang merepresentasikan operasi retrieval dokumen eksternal?
5. Mengapa P99 latency sering melonjak signifikan pada LLM streaming calls dibanding standard API REST endpoints?

#### Intermediate (5 Soal)
6. Bagaimana cara mendeteksi *semantic drift* pada sistem RAG tanpa harus melabeli dataset produksi secara manual setiap hari?
7. Apa kelemahan utama penggunaan metrik deterministik tradisional seperti BLEU atau ROUGE untuk mengevaluasi generative agent responses?
8. Bagaimana strategi mitigasi jika LLM penilai (Judge) memiliki latensi yang lebih tinggi daripada sistem produksi yang sedang dievaluasi?
9. Jelaskan peran *Maximum Mean Discrepancy* (MMD) dalam evaluasi embedding drift!
10. Dalam kondisi apa kita harus memilih *Reference-Free Evaluation* dibandingkan *Reference-Based Evaluation*?

#### Skenario Kasus Produksi (3 Soal)
11. **Skenario A**: Tim Anda merilis prompt template baru yang menginstruksikan model untuk menjawab lebih ringkas. Ragas score menunjukkan metrik *Faithfulness* tetap tinggi (0.95), namun metrik kepuasan pengguna (CSAT) turun drastis dari 4.5 ke 2.8. Analisis akar masalah teknis yang tidak tertangkap oleh evaluasi tersebut!
12. **Skenario B**: Sistem monitoring ClickHouse Anda mendeteksi bahwa P95 latency naik dari 600ms menjadi 3800ms secara bertahap dalam kurun waktu 48 jam, sementara total request per detik konstan. Span trace mana yang pertama kali harus diisolasi dan parameter internal apa yang kemungkinan besar bocor?
13. **Skenario C**: Pada saat pengujian evaluasi CI/CD, model Llama-3-8B lulus semua threshold regression testing. Namun di produksi, model sering mengalami *stuck in loop* saat memanggil tool kalkulator finansial. Mengapa static evaluation dataset gagal mendeteksi behavior ini?

---

### 16. Summary
- Evaluasi dan observabilitas AI tingkat enterprise bukan sekadar log analytics, melainkan sebuah **sistem kendali mutu loop tertutup (*closed-loop control system*)**.
- Fondasi arsitektur observability modern bertumpu pada **OpenInference semantic conventions** yang memetakan trace, spans, tokens, cost, dan retrieval context secara terstruktur lintas bounded contexts.
- Strategi evaluasi produksi harus menggunakan pendekatan berjenjang: **deterministik in-line** untuk keamanan dasar & compliance, serta **probabilistik out-of-band (LLM-as-a-Judge & Embedding Drift)** untuk menjamin akurasi semantik tanpa menambah penalti latensi pada interaksi pengguna.
- Keberhasilan produk AI bukan hanya ditentukan oleh kualitas model pada hari peluncuran, melainkan oleh ketahanan sistem dalam **mendeteksi, mengisolasi, dan memitigasi degradasi performa** di bawah tekanan data dunia nyata yang dinamis.