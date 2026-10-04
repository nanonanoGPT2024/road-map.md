# Bab 05: Product Roadmapping, Prioritization & Backlog Engineering
## Module 01: AI/Data & Autonomous Agents Technical Backlog Strategy

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Product Manager (PM) teknis diharapkan mampu:

*   **Menghitung Skor Prioritas AI Adaptif (RICE-AI & CD3-AI):** Mengintegrasikan variabel non-deterministik seperti *Data Readiness Level* (DRL), *Model Uncertainty Factor* (MUF), dan *Inference Cost Projection* ke dalam matriks prioritas backlog.
*   **Merancang Roadmap Berbasis Evaluasi (*Evaluation-Driven Roadmapping*):** Menyusun roadmap produk otonom menggunakan pendekatan *stage-gated outcome* alih-alih *fixed feature commitment*, dengan batas toleransi akurasi/evaluasi (*ground truth baseline*) yang terukur.
*   **Melakukan Dekomposisi Backlog Multi-Agent:** Memecah inisiatif *Autonomous Agent* tingkat tinggi menjadi *technical user stories* modular mencakup: *Evaluation Harness*, *Deterministic Guardrails*, *Tool-calling/API Schema*, *Memory Store*, dan *Telemetry Engine*.
*   **Mengaudit Model Unit Economics & Token Budgeting:** Mengestimasi *Cost of Goods Sold* (COGS) komputasi dan latensi inferensi per transaksi pengguna untuk menentukan kelayakan teknis sebelum inisiatif masuk ke sprint development.
*   **Mengimplementasikan *Technical Definition of Done* (DoD) Sistem AI:** Mendefinisikan kriteria rilis yang mencakup mitigasi *drift*, *regression eval*, *adversarial safety benchmark*, dan batas latensi P99.

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Mental Model: Deterministik vs. Probabilistik
Pengembangan perangkat lunak konvensional beroperasi pada domain **deterministik**:

$$\text{Logika Kode} + \text{Input Spesifik} \rightarrow \text{Output yang Dapat Diprediksi (100\%)}$$

Sebaliknya, produk berbasis AI/Autonomous Agent beroperasi pada domain **probabilistik**:

$$\text{Arsitektur Model} + \text{Data Distribusi} + \text{Konteks Prompt} \rightarrow \text{Distribusi Peluang Output}$$

PM yang memaksakan backlog deterministik (misalnya: *"Buat sistem customer service agent yang menjawab 100% benar pada Sprint 4"*) dipastikan gagal. Pendekatan engineering modern mengharuskan PM memperlakukan backlog sebagai portofolio **hipotesis saintifik** yang divalidasi melalui sistem evaluasi (*eval harness*).

```
+-------------------------------------------------------------------------------+
|                       PARADIGMA ROADMAPPING SISTEM                            |
+-------------------------------------------------------------------------------+
| Fitur Deterministik (CRUD/Web)    Fitur Probabilistik (GenAI / Autonomous)     |
| +-----------------------------+   +-----------------------------------------+ |
| | Sprint -> Feature Delivered |   | Phase 1: Data Audit & Baseline Evals    | |
| | Sprint -> QA Pass           |   | Phase 2: Heuristic / RAG Prototype      | |
| | Sprint -> Production Deploy |   | Phase 3: Fine-Tuning / Agentic Routing  | |
| |                             |   | Phase 4: Production Guardrails & Scale  | |
| +-----------------------------+   +-----------------------------------------+ |
| Output: Binary (Bekerja/Rusak)|   Output: Metrik Kurva (Recall/Latency/Cost)| |
+-------------------------------------------------------------------------------+
```

#### Dual-Track Discovery-Delivery untuk AI
Untuk mengatasi ketidakpastian tersebut, arsitektur backlog AI memisahkan pekerjaan menjadi dua jalur (*dual-track*):
1.  **Discovery Spike Track (Probabilistik):** Riset data, pembuatan *golden dataset*, pengujian *prompt/context window*, mitigasi halusinasi, dan validasi *inference cost*.
2.  **Delivery Engineering Track (Deterministik):** Integrasi API, *guardrails engine*, pipeline data streaming, observabilitas (tracing), dan antarmuka pengguna (UI/UX).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Ketiadaan strategi backlog teknis yang matang pada proyek AI enterprise secara historis menyebabkan kegagalan sistemik:
*   **The 80% Accuracy Wall:** Tim menghabiskan 2 sprint untuk mencapai akurasi model 80%, kemudian menghabiskan 8 bulan berikutnya tanpa hasil untuk mengejar akurasi 95% yang disyaratkan SLA bisnis. Ini terjadi karena PM tidak memasukkan *fallback architecture* (misalnya: *Human-in-the-Loop*) ke dalam backlog awal.
*   **Token Burn Runaway (Inference Shock):** Autonomous agent yang diizinkan melakukan *multi-step reflection* tanpa batasan batas komputasi (*loop counter*) dapat menghabiskan ribuan dolar per jam karena loop inferensi yang tidak terbatas.
*   **Technical Debt Akibat Data Drift:** Produk yang diluncurkan tanpa backlog otomatisasi monitoring distribusi data akan mengalami degradasi performa dalam hitungan minggu setelah masuk ke lingkungan produksi.
*   **Kepatuhan Regulasi (EU AI Act / ISO 42001):** Enterprise menuntut *explainability*, *audit trail*, dan determinisme kontrol keamanan. Backlog yang tidak memprioritaskan *logging telemetry* sejak hari pertama akan ditolak oleh tim legal dan keamanan sistem.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut merepresentasikan alur integrasi evaluasi, prioritisasi berbasis kesiapan data, dan siklus hidup backlog untuk sistem AI/Autonomous Agent:

```
[Inisiatif Produk / Ide Bisnis]
               |
               v
+-------------------------------------------------------------+
|              FASE 1: DATA READINESS LEVEL (DRL)             |
| - Ketersediaan Label Data?       - Lisensi & Kepatuhan Data?|
| - Volume Representatif?          - Aksesibilitas Pipeline?  |
+-------------------------------------------------------------+
               |
        [ DRL >= Level 4? ]
        /               \
      TIDAK              YA
      /                   \
     v                     v
+------------------+  +---------------------------------------+
| SPIKE BACKLOG:   |  |     FASE 2: SCORING RICE-AI ENGINE    |
| - Data Ingestion |  | - Reach & Impact Bisnis               |
| - Data Labeling  |  | - Confidence * Data Quality Factor    |
| - Ground Truth   |  | - Effort * (1 + Uncertainty Penalty)  |
+------------------+  | - Unit Economic Token Budget Target   |
                      +---------------------------------------+
                                           |
                                           v
               +-------------------------------------------------------+
               | FASE 3: DEKOMPOSISI BACKLOG MULTI-AGENT (5-PILLARS)   |
               +-------------------------------------------------------+
               | 1. Eval Harness: Golden Dataset & Synthetic Benchmark |
               | 2. Guardrails: Input/Output Sanitization & Safety     |
               | 3. Tools/Schemas: OpenAPI Spec Function Definitions   |
               | 4. Agent Runtime: Orchestrator, Planner, Memory Store |
               | 5. Telemetry: Cost, Latency, OpenTelemetry Traces     |
               +-------------------------------------------------------+
                                           |
                                           v
               +-------------------------------------------------------+
               | FASE 4: SPRINT EXECUTION & EVALUATION GATE (CI/CD)    |
               |                                                       |
               | [Run CI Evals] ---> [Baseline Met?] ---> PRODUCTION  |
               |                           |                           |
               |                         TIDAK                         |
               |                           v                           |
               |               [Circuit Breaker / HITL]                |
               +-------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Extended Prioritization Framework: RICE-AI
Model prioritisasi standar seperti RICE konvensional ($\frac{R \times I \times C}{E}$) tidak mempertimbangkan risiko eksplorasi saintifik dan biaya operasional komputasi (*inference economics*). 

Formula **RICE-AI** dimodifikasi secara matematis sebagai berikut:

$$\text{Skor RICE-AI} = \frac{\text{Reach} \times \text{Impact} \times (\text{Confidence} \times \text{DRL})}{\text{Effort} \times (1 + \text{MUF}) \times \text{TCF}}$$

Di mana:
1.  **Data Readiness Level (DRL) ($0.1 - 1.0$):**
    *   $0.1$: Data belum ada / belum terstruktur / masalah regulasi privasi.
    *   $0.5$: Data historis tersedia tetapi tidak terlabeli dan pipeline batch manual.
    *   $1.0$: Pipeline data real-time tersedia, terverifikasi, label *ground truth* tersedia.
2.  **Model Uncertainty Factor (MUF) ($0.0 - 2.0$):**
    *   $0.0$: Tugas deterministik atau menggunakan LLM dasar untuk peringkasan standar.
    *   $0.5$: RAG dengan pencarian semantik pada domain tertutup (*closed-domain*).
    *   $1.5 - 2.0$: Autonomous Agent otonom multi-hop dengan eksekusi tool dinamis.
3.  **Token Cost Factor (TCF) ($\ge 1.0$):**
    *   Rasio antara perkiraan biaya inferensi per kueri terhadap batas maksimal alokasi margin kotor produk (*gross margin threshold*). Jika biaya proyeksi melampaui ambang batas batas aman, nilai TCF meningkat secara eksponensial.

$$\text{TCF} = \max\left(1.0, \frac{\text{Estimated Cost per Query}}{\text{Target Cost Allocation}}\right)$$

#### Dekomposisi Backlog: 5-Pillar Agentic Engineering
Saat memecahkan inisiatif sistem otonom ke dalam ticket Jira/Linear, PM teknis harus mengonversi deskripsi fungsional menjadi 5 pilar arsitektural:

1.  **Pillar 1: Eval Harness (Definisi Baseline):**
    *   Pembuatan *Golden Test Set* minimal 100–500 pasang input-output terverifikasi domain expert.
    *   Implementasi metrik evaluasi otomatis: G-Eval, RAGAS (Faithfulness, Answer Relevance), BLEU/ROUGE, atau Semantic Similarity.
2.  **Pillar 2: Schemas & Tool Definitions:**
    *   Spesifikasi antarmuka JSON Schema yang ketat (*Strict Mode*) untuk pemanggilan fungsi (*function calling*).
    *   Penanganan kegagalan API downstream (*circuit breaker*, eksponensial *backoff*).
3.  **Pillar 3: Agent Orchestration & State:**
    *   Strategi *prompt template* dan struktur pemecahan masalah (*Chain-of-Thought*, *ReAct*, *Plan-and-Solve*).
    *   Manajemen status percakapan: *Short-term buffer*, *Semantic sliding window*, dan *Long-term memory* (Vector store).
4.  **Pillar 4: Guardrails & Deterministic Fallback:**
    *   Validasi input: Deteksi *Jailbreak*, injeksi prompt, dan sanitasi PII (*Personally Identifiable Information*).
    *   Validasi output: Schema conformance check, pengecekan halusinasi, dan *fallback router* ke operator manusia (*Human-in-the-Loop*).
5.  **Pillar 5: Telemetry, Observability & Cost Control:**
    *   Integrasi tracing granular per LLM run (*tokens used*, *latency per step*, *cost in USD*).
    *   Implementasi batas eksekusi maksimum: *Max token limit*, *Max tool-calling iterations*.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul Python modular untuk menghitung **Prioritisasi RICE-AI**, memvalidasi **Data Readiness Level (DRL)**, dan secara otomatis menghasilkan spesifikasi backlog berstruktur JSON yang siap diekspor ke Jira/Linear.

```python
"""
Prioritization & Backlog Engineering Engine for AI Systems
Author: Principal AI Technical Product Manager
Description: Evaluates AI project feasibility, calculates RICE-AI score, 
             and auto-generates decomposed technical backlog structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import json
import math


class DataReadinessLevel(float, Enum):
    NO_DATA = 0.1
    UNSTRUCTURED_UNLABELED = 0.3
    STRUCTURED_UNLABELED = 0.5
    LABELED_BATCH_ACCESSIBLE = 0.8
    CLEAN_REALTIME_GOLDEN_AVAILABLE = 1.0


class ModelComplexity(float, Enum):
    DETERMINISTIC_RULES = 0.0
    PROMPT_ENGINEERING_ONLY = 0.2
    STANDARD_RAG = 0.5
    MULTI_HOP_RAG = 0.8
    FINE_TUNED_MODEL = 1.2
    FULLY_AUTONOMOUS_MULTI_AGENT = 1.8


@dataclass(frozen=True)
class InitiativeInput:
    title: str
    reach: int  # Estimasi pengguna/event per kuartal
    impact: float  # Skala 0.25 (minimal) hingga 3.0 (masif)
    confidence: float  # Skala 0.0 hingga 1.0
    effort_sprints: float  # Sprint tim (1 sprint = 2 minggu)
    data_readiness: DataReadinessLevel
    complexity: ModelComplexity
    estimated_cost_per_query_usd: float
    target_cost_per_query_usd: float


@dataclass
class BacklogItem:
    pillar: str
    title: str
    description: str
    acceptance_criteria: List[str]
    technical_dependencies: List[str]


@dataclass
class PrioritizedInitiative:
    title: str
    rice_ai_score: float
    drl: float
    uncertainty_penalty: float
    token_cost_factor: float
    backlog_breakdown: List[BacklogItem] = field(default_factory=list)


class AIBacklogPrioritizationEngine:
    def __init__(self, cost_sensitivity_exponent: float = 1.5):
        self.cost_exponent = cost_sensitivity_exponent

    def calculate_token_cost_factor(self, estimated: float, target: float) -> float:
        """
        Menghitung penalti pembengkakan biaya komputasi (Inference Cost Factor).
        Jika estimasi biaya > target, penalti dinaikkan secara eksponensial.
        """
        if target <= 0.0:
            raise ValueError("Target cost per query must be greater than 0.")
        
        ratio = estimated / target
        if ratio <= 1.0:
            return 1.0
        return round(math.pow(ratio, self.cost_exponent), 3)

    def calculate_rice_ai(self, initiative: InitiativeInput) -> PrioritizedInitiative:
        """
        Kalkulasi RICE-AI:
        Score = (Reach * Impact * (Confidence * DRL)) / (Effort * (1 + MUF) * TCF)
        """
        if initiative.effort_sprints <= 0:
            raise ValueError("Effort in sprints must be > 0.")
        if not (0.0 <= initiative.confidence <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        drl_score = initiative.data_readiness.value
        muf_score = initiative.complexity.value
        tcf = self.calculate_token_cost_factor(
            initiative.estimated_cost_per_query_usd,
            initiative.target_cost_per_query_usd
        )

        effective_confidence = initiative.confidence * drl_score
        effective_effort = initiative.effort_sprints * (1.0 + muf_score) * tcf

        numerator = initiative.reach * initiative.impact * effective_confidence
        rice_ai = round(numerator / effective_effort, 2)

        return PrioritizedInitiative(
            title=initiative.title,
            rice_ai_score=rice_ai,
            drl=drl_score,
            uncertainty_penalty=muf_score,
            token_cost_factor=tcf
        )

    def decompose_agentic_backlog(self, initiative: InitiativeInput) -> List[BacklogItem]:
        """
        Dekomposisi inisiatif secara deterministik ke dalam 5 Pilar Backlog Agentik.
        """
        backlog = []

        # Pilar 1: Eval Harness
        backlog.append(BacklogItem(
            pillar="Pillar 1: Evaluation Harness",
            title=f"[EVAL] Golden Dataset & Eval Gate for {initiative.title}",
            description="Membangun dataset pengujian representatif dan harness evaluasi otomatis.",
            acceptance_criteria=[
                "Tersedia minimum 200 contoh evaluasi terlabeli (ground truth).",
                "CI pipeline menjalankan otomatis evaluasi sintesis (Factual Accuracy >= 90%).",
                "Automated metric (RAGAS / G-Eval) terintegrasi ke PR builder."
            ],
            technical_dependencies=["Data Annotation Spec", "Storage for Test-Benches"]
        ))

        # Pilar 2: Guardrails & Safety
        backlog.append(BacklogItem(
            pillar="Pillar 2: Guardrails & Safety",
            title=f"[GUARDRAIL] Input/Output Validation Layer for {initiative.title}",
            description="Mencegah serangan injeksi prompt, halusinasi fatal, dan kebocoran data.",
            acceptance_criteria=[
                "Injeksi prompt tertahan dengan akurasi klasifikasi adversarial >= 98%.",
                "Filter PII mendeteksi dan melakukan masking pada nomor rekening/identitas.",
                "Implementasi deterministic regex/validator untuk format output JSON."
            ],
            technical_dependencies=["Security Boundary Spec", "NeMo Guardrails / Llama-Guard"]
        ))

        # Pilar 3: Schemas & Tool Integration
        backlog.append(BacklogItem(
            pillar="Pillar 3: Tool & API Schemas",
            title=f"[TOOLS] Function Calling Contract for {initiative.title}",
            description="Mendefinisikan skema JSON OpenAPI untuk aksi eksekusi downstream.",
            acceptance_criteria=[
                "Skema JSON fungsi tervalidasi menggunakan Pydantic/OpenAPI strict standards.",
                "Pola penanganan error untuk timeout tool downstream (Circuit Breaker).",
                "Model mengembalikan format 'dry-run' sebelum mengeksekusi mutasi state data."
            ],
            technical_dependencies=["Downstream API Endpoints", "API Gateway Access"]
        ))

        # Pilar 4: Orchestration & Core Architecture
        backlog.append(BacklogItem(
            pillar="Pillar 4: Agent Core & Memory",
            title=f"[RUNTIME] State Machine & Context Engine for {initiative.title}",
            description="Mengatur alur berpikir reasoning agent, memori sesi, dan pemanggilan context.",
            acceptance_criteria=[
                "Mekanisme Context Window compaction menjaga token utilization di bawah 80%.",
                "Maksimum langkah reasoning loop dibatasi maksimal 5 iterasi (anti-runaway loop).",
                "Fallback deterministik aktif jika reasoning confidence score di bawah 0.70."
            ],
            technical_dependencies=["LLM Inference Endpoint", "Vector DB / Memory Storage"]
        ))

        # Pilar 5: Telemetry, Observability & Cost Tracking
        backlog.append(BacklogItem(
            pillar="Pillar 5: Telemetry & FinOps",
            title=f"[FINOPS] Real-time Cost & Token Tracing for {initiative.title}",
            description="Telemetri produksi untuk melacak konsumsi token, latensi inferensi, dan biaya.",
            acceptance_criteria=[
                "OpenTelemetry context injection pada setiap pemanggilan LLM/Tool.",
                "Biaya inferensi aktual per transaksi disimpan dan dapat di-query di dashboard.",
                "Peringatan otomatis terpicu jika rata-rata latensi P95 melebihi 2.500 ms."
            ],
            technical_dependencies=["OpenTelemetry Collector", "Langfuse / Arize Phoenix"]
        ))

        return backlog


# ---------------------------------------------------------
# CONTOH EKSEKUSI PRODUKSI
# ---------------------------------------------------------
if __name__ == "__main__":
    engine = AIBacklogPrioritizationEngine()

    initiative = InitiativeInput(
        title="Autonomous SQL-Query & Financial Reporting Agent",
        reach=50000,
        impact=2.0,
        confidence=0.85,
        effort_sprints=4.0,
        data_readiness=DataReadinessLevel.STRUCTURED_UNLABELED,  # 0.5
        complexity=ModelComplexity.FULLY_AUTONOMOUS_MULTI_AGENT,   # 1.8
        estimated_cost_per_query_usd=0.08,
        target_cost_per_query_usd=0.02  # Melebihi target batas biaya (4x)
    )

    try:
        prioritization_result = engine.calculate_rice_ai(initiative)
        backlog_items = engine.decompose_agentic_backlog(initiative)
        prioritization_result.backlog_breakdown = backlog_items

        print("=== HASIL PERHITUNGAN PRIORITISASI RICE-AI ===")
        print(f"Inisiatif           : {prioritization_result.title}")
        print(f"Skor RICE-AI        : {prioritization_result.rice_ai_score}")
        print(f"Data Readiness (DRL): {prioritization_result.drl}")
        print(f"Uncertainty Penalty : +{prioritization_result.uncertainty_penalty * 100}%")
        print(f"Token Cost Factor   : {prioritization_result.token_cost_factor}x")
        print("\n=== DEKOMPOSISI BACKLOG (5-PILLARS) ===")
        for idx, item in enumerate(prioritization_result.backlog_breakdown, 1):
            print(f"\n{idx}. [{item.pillar}] {item.title}")
            print(f"   Deskripsi: {item.description}")
            print("   Acceptance Criteria:")
            for ac in item.acceptance_criteria:
                print(f"     - {ac}")
    except Exception as e:
        print(f"Kesalahan Kalkulasi: {str(e)}")
```

---

### 7. Edge Cases & Failure Modes (Error Recovery, Validasi & Fallback)

Dalam merancang backlog produk AI, PM wajib menetapkan spesifikasi penanganan kegagalan (*failure modes*) secara eksplisit pada level tiket:

| Kategori Kegagalan | Modus Kegagalan Riil | Mitigasi Spesifik Backlog (Actionable) | Fallback Otomatis |
| :--- | :--- | :--- | :--- |
| **Token Cost Explosion** | Agent masuk ke dalam loop refleksi rekursif (*infinite loop*) tanpa konvergensi jawaban. | Implementasikan *Hard Loop Boundary* (maksimal 4 iterasi eksekusi tool). | Putuskan proses agentic, kembalikan respon heuristik fallback: *"Sistem memerlukan bantuan operator untuk permintaan ini."* |
| **Silent Hallucination** | LLM menghasilkan sintaks tool-call yang salah secara semantik (*invalid argument hallucination*). | Terapkan Pydantic Validation Gate pada deserialisasi payload respon LLM. | Jalankan *Reflection Retry* 1x dengan menyertakan pesan error validasi ke prompt. Jika tetap gagal, batalkan eksekusi API. |
| **Data Drift Degradation** | Data transaksi pengguna berubah secara musiman; akurasi retrieval (RAG) anjlok. | Buat backlog terjadwal untuk re-evaluasi *Golden Test Dataset* berkala tiap dua minggu. | Alihkan router ke model dasar (*zero-shot*) atau non-vector text search tradisional (ElasticSearch/BM25). |
| **API Schema Evolution** | Sistem upstream memodifikasi field database tanpa pemberitahuan; Agent tool execution crash. | Pasang *Contract Testing* otomatis pada CI/CD pipeline yang terintegrasi dengan OpenAPI spec. | Matikan ketersediaan tool tersebut dari prompt model via *Dynamic Feature Flags*, agent kembali beroperasi dalam mode informasional. |

---

### 8. Trade-offs & Alternatif Solusi

Saat mengelola backlog teknis produk otonom, PM dihadapkan pada kompromi arsitektural yang saling bertentangan:

```
          [Tingkat Otonomi Agent]
                  /\
                 /  \
                /    \
               /      \
              /        \
             /          \
[Keandalan/Determinisme]--[Biaya & Latensi Inferensi]
```

#### 1. Deterministic State Machines vs. Autonomous ReAct Loop
*   **State Machine (Graph-based / LangGraph):**
    *   *Kelebihan:* Alur eksekusi dapat diprediksi 100%, latensi terkontrol, audit kepatuhan mudah.
    *   *Kekurangan:* Tidak fleksibel terhadap variasi kueri tak terduga; biaya engineering awal tinggi.
    *   *Rekomendasi PM:* Gunakan untuk domain sensitif regulasi (finansial, audit data, kesehatan).
*   **Autonomous ReAct Loop:**
    *   *Kelebihan:* Mampu menyelesaikan masalah multi-langkah yang dinamis tanpa aturan kaku.
    *   *Kekurangan:* Risiko loop tak terbatas tinggi, latensi tinggi ($> 5$ detik), biaya token sulit diprediksi.
    *   *Rekomendasi PM:* Gunakan hanya untuk asisten riset atau tugas eksploratori internal.

#### 2. Fine-Tuning vs. Retrieval-Augmented Generation (RAG)
*   **RAG (Retrieval-Augmented Generation):**
    *   *Trade-off:* Biaya inferensi lebih tinggi (banyak token dimasukkan ke konteks), ketergantungan pada akurasi search retriever; namun biaya pemeliharaan backlog rendah (data dapat diubah tanpa pelatihan ulang model).
*   **Fine-Tuning:**
    *   *Trade-off:* Biaya upfront pelatihan model tinggi, siklus rilis lambat (harus retraining saat domain data bergeser); namun latensi inferensi lebih cepat dan biaya per token lebih rendah.

---

### 9. Best Practices & Standar Industri

1.  **Golden Datasets sebagai Gatekeeper (Bukan User Acceptance Testing Manual):**
    *   Setiap ticket *Story* yang mengubah arsitektur prompt, embeddings, atau model router dilarang *merge* sebelum lulus benchmark CI/CD against Golden Dataset. Tidak boleh mengandalkan impresi subjektif QA manual.
2.  **Token Budgeting per Story:**
    *   Sematkan batasan operasional pada user story: *"Fitur ini tidak boleh mengonsumsi lebih dari 1.500 token input dan 500 token output per interaksi end-user."*
3.  **Trace-ID Binding:**
    *   Wajibkan engineering menyematkan metadata `Backlog-Epic-ID` atau `Feature-Flag-Key` ke dalam sistem tracing inferensi (OpenTelemetry / Langfuse / Arize). Hal ini memungkinkan analisis analitik FinOps berbasis fitur secara presisi di level dashboard eksekutif.
4.  **Isolasi Heuristik sebelum Otonomi:**
    *   Validasi apakah masalah benar-benar memerlukan AI/LLM. Jika masalah dapat diselesaikan dengan ekspresi reguler (Regex) atau *SQL query standard*, tolak inisiatif AI dari backlog delivery untuk mencegah pemborosan komputasi.

---

### 10. Hands-on Lab Exercise: Menyusun AI Agent Backlog & Prioritization Matrix

#### Skenario Kasus
Anda adalah Principal AI Product Manager di platform B2B E-Commerce Enterprise. Tim bisnis meminta integrasi fitur baru:
> *"Sistem Agent yang dapat menganalisis komplain retur barang dari pelanggan, membaca database inventaris secara real-time, mendeteksi potensi fraud klaim pengembalian, dan langsung memproses refund dana ke akun bank pelanggan tanpa persetujuan manual jika memenuhi kriteria."*

#### Langkah Pengerjaan Lab

##### Langkah 1: Kalkulasi Parameter RICE-AI
Lakukan analisis terhadap parameter inisiatif berdasarkan data berikut:
*   **Reach:** 200.000 transaksi/bulan.
*   **Impact:** 3.0 (Dampak masif pada efisiensi biaya operasional tim support).
*   **Confidence Bisnis:** 0.80.
*   **Data Readiness:** Data komplain tersimpan dalam database teks, namun label fraud hanya tersedia pada 500 kasus lama (Data Readiness Level: `STRUCTURED_UNLABELED` = 0.5).
*   **Kompleksitas Teknis:** Sistem multi-agent yang melakukan validasi inventaris, penilaian fraud, dan transfer bank (Complexity: `FULLY_AUTONOMOUS_MULTI_AGENT` = 1.8).
*   **Target Biaya Inferensi:** $0.01 per komplain. Estimasi biaya nyata sistem multi-agent: $0.05 per komplain.

*Tugas Lab 1:* Jalankan modul skrip Python di Bagian 6 menggunakan parameter di atas. Catat skor akhir RICE-AI dan interpretasikan mengapa skor mengalami pemotongan drastis.

##### Langkah 2: Evaluasi Gate & Circuit Breaker Design
Tuliskan 3 Acceptance Criteria teknis yang wajib ada pada Epic Jira untuk mencegah transfer dana ilegal ke penipu (*fraudster*).

*Contoh Solusi Standar:*
1.  *Acceptance Criteria 1:* Model Fraud Detection harus memiliki tingkat *Precision* $\ge 99.2\%$ pada Golden Test Dataset transaksi berisiko tinggi.
2.  *Acceptance Criteria 2 (Hard Limit):* Refund otomatis di atas batas nominal $\text{Rp 500.000}$ secara wajib dialihkan ke antrean persetujuan manual (*Human-in-the-Loop*).
3.  *Acceptance Criteria 3 (Guardrail Conformance):* Tool eksekusi transfer dana hanya boleh dipanggil jika skor integritas verifikasi data retur bernilai *True* oleh dua agent validator independen (*Dual-Agent Consensus Architecture*).

##### Langkah 3: Dekomposisi 5-Pillar Backlog
Berdasarkan engine Python, modifikasi fungsi dekomposisi untuk menghasilkan 5 tiket kerja Jira spesifik untuk skenario di atas, lengkap dengan *Definition of Done* (DoD) evaluasi non-deterministik.