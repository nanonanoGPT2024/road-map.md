# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 02: Customer Discovery & Problem Space Definition (Kategori: 08-AI-Data-and-Autonomous-Agents)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta (Technical AI Product Manager, Principal PM, dan Engineering Lead) diharapkan mampu:
1. **Mendekomposisi Problem Space Stokastik**: Membedakan secara presisi antara problem domain deterministik vs non-deterministik/probabilistik dalam perancangan sistem berbasis AI/LLM/Autonomous Agents.
2. **Membangun Automated Semantic Discovery Engine**: Merancang dan mengimplementasikan pipeline end-to-end untuk mengekstrak, mengelompokkan (clustering), dan mengkuantifikasi friksi pengguna dari data tidak terstruktur (telemetri, transkrip wawancara, tiket Zendesk/Jira) menggunakan teknik vector embeddings dan unsupervised clustering.
3. **Merumuskan Spesifikasi Toleransi Eror (Error Budgeting & Risk Envelope)**: Menetapkan batas toleransi halusinasi, degradasi performa (*ground-truth drift*), dan ambang batas eskalasi agen (*human takeover threshold*) ke dalam metrik PRD (*Product Requirement Document*) yang dapat dieksekusi oleh tim Machine Learning/Platform Engineering.
4. **Mengevaluasi Feasibility vs. Impact Frontier**: Melakukan audit kelayakan data (*data readiness audit*), estimasi biaya inferensi vs. *economic value to customer* (EVC), dan validasi asumsi menggunakan simulasi *Wizard of Oz* dan *Shadow Prototyping*.

---

## 2. Prerequisite
Untuk menyerap materi ini secara optimal, peserta wajib memahami:
- **Konsep Dasar AI/ML**: Memahami konsep *precision, recall, F1-score, latency trade-offs*, inferensi model bahasa besar (LLMs), dan *vector representations*.
- **Telemetry & Event-Driven Systems**: Pemahaman dasar mengenai arsitektur streaming (Kafka/PubSub), penyimpanan analitis (ClickHouse/Snowflake), dan struktur log JSON.
- **Python Modern & Data Science Stack**: Familiar dengan sintaksis Python 3.10+, pustaka asynchronous (`asyncio`), manipulasi data (`pandas`, `numpy`), dan orkestrasi skema (`pydantic`).
- **Product Discovery Frameworks**: Menguasai konsep dasar *Continuous Discovery Habits* (Teresa Torres), *Jobs-to-be-Done* (JTBD), serta transisi dari *Problem Space* ke *Solution Space*.

---

## 3. Concept & Internal Architecture (Mendalam)

### 3.1 Anatomi Problem Space pada Domain AI & Autonomous Agents
Dalam rekayasa produk software konvensional, problem space bersifat linier dan deterministik:
$$\text{Input } X \rightarrow \text{System Logic } f(X) \rightarrow \text{Output } Y \quad (\text{di mana } f(X) \text{ bersifat statis})$$

Pada produk AI dan Autonomous Agents, *Problem Space* berada pada domain probabilitas dan variabilitas data:
$$\text{Input } X \sim P(X) \rightarrow \text{Stochastic Agent Logic } \mathcal{M}(X | \theta) \rightarrow \text{Output } \hat{Y} \sim P(Y | X)$$

Ketika seorang AI Product Manager mendefinisikan problem space, terdapat tiga vektor dimensi yang wajib dikuantifikasi sebelum menulis sebaris pun kode solusi:
1. **Entropy of User Intent (Entropi Niat Pengguna)**: Seberapa ambigu dan bervariasinya cara pengguna mengekspresikan masalah mereka.
2. **Cost of Inaccuracy (Biaya Ketidaktepatan/Kegagalan)**: Kerugian finansial, reputasi, atau operasional jika sistem menghasilkan False Positive atau False Negative.
3. **Context Horizon**: Volume data historis, *state* temporal, dan integrasi multi-sistem yang dibutuhkan agar sebuah aksi agen dapat dianggap valid oleh pengguna.

```
       ▲ Cost of Inaccuracy (Risk Envelope)
       │
High   │  [Zona Bahaya: Critical Agentic Control]  │  [Zona Deterministik: Aturan Ketat]
       │  Autonomous Financial Transfer, Medical   │  Payroll Calculation, Tax Audit
       │  Diagnosis. Butuh Human-in-the-Loop 100%  │  Gunakan Rule Engine, JANGAN AI Murni!
       ├───────────────────────────────────────────┼─────────────────────────────────────────
       │  [Zona Emas AI PM: Generative/Agentic]   │  [Zona Otomatisasi Tradisional]
Low    │  Customer Support Drafts, Semantic Search │  Form Validation, Password Reset
       │  Toleransi eror moderat, EVC tinggi       │  Deterministic CRUD
       └───────────────────────────────────────────┴─────────────────────────────────────────►
         Unstructured / Non-Deterministic           Structured / Deterministic
                                                    Nature of Problem Space
```

### 3.2 Dual-Track Discovery Architecture untuk AI Products
Pendekatan wawancara kualitatif standar (5–10 user interviews) sering kali gagal dalam produk AI karena bias ekspektasi pengguna (*the sci-fi fallacy*). Pengguna berasumsi AI dapat melakukan segalanya, namun mengabaikan *corner cases*.

Untuk mengatasi hal tersebut, arsitektur discovery modern memadukan dua jalur data:
1. **Algorithmic Qualitative Synthesis**: Mengumpulkan percakapan natural pengguna (data audio/teks transkrip, interaksi pencarian, eskalasi komplain), mengonversinya ke dalam *dense vector space*, dan melakukan *semantic clustering* untuk mendeteksi friksi laten yang tidak disuarakan secara eksplisit.
2. **Behavioral Telemetry Ingestion**: Mengamati *drop-off point* pada sistem yang ada, waktu henti (*dwell time*), dan frekuensi pengguna mengabaikan rekomendasi sistem konvensional.

---

## 4. Why & What

### Why: Mengapa Customer Discovery Tradisional Gagal pada AI?
- **The "Stochastic Trap"**: Pengguna menyatakan bahwa mereka menginginkan "agen otomatis yang menyelesaikan rekonsiliasi data invoice". Namun ketika agen membuat 1 kesalahan dari 1.000 transaksi (akurasi 99.9%), pengguna menolak sistem tersebut secara total karena ketiadaan *audit trail* yang dapat dipahami manusia.
- **The Ground Truth Illusion**: PM berasumsi masalah yang dihadapi pengguna memiliki data *ground truth* (label data yang valid). Pada realitas enterprise, 60–80% masalah bisnis tidak memiliki data berlabel yang bersih; *ground truth* itu sendiri sering kali subjektif antar-divisi.
- **Hallucination vs. Utility Trade-off**: Tanpa definisi problem space yang membatasi *scope of agency* (ruang gerak otonomi agen), AI agent akan mengalami *state explosion*—situasi di mana agen mencoba menyelesaikan masalah yang terlalu luas sehingga menghasilkan loop tak berujung (*infinite reasoning loop*).

### What: The AI Problem Definition Envelope (PDE)
Alih-alih membuat PRD konvensional dengan fitur *User Story*, AI PM di level enterprise menyusun **Problem Definition Envelope (PDE)** yang mendefinisikan batas-batas matematis dan operasional:
1. **Intent Boundary**: Input apa saja yang valid, semi-valid, dan out-of-scope (*adversarial/out-of-distribution*).
2. **Tolerable Error Profile**: Distribusi toleransi kesalahan (misal: "False Positive dapat ditoleransi hingga 5%, namun False Negative harus < 0.1%").
3. **Escalation SLA**: Kondisi presisi ketika sistem harus mencabut otonomi agen dan mengembalikannya ke manusia (*Human Fallback Trigger*).
4. **Context Window Requirement**: Jumlah token/data historis minimum yang wajib disediakan infrastruktur data agar inferensi bernilai guna.

---

## 5. How: Workflow Detail Penemuan Masalah Berbasis Data

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AI PM PROBLEM DISCOVERY WORKFLOW PIPELINE                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────┐     Raw Call Transcripts, Support Tickets,
│ 1. INGESTION     │ ──► OpenTelemetry Event Logs, Screen-recording OCR
└──────────────────┘
          │
          ▼
┌──────────────────┐     Text chunking, Metadata sanitization (PII Stripping via Presidio),
│ 2. PRE-PROCESS   │ ──► Dense Vector Embedding Generation (e.g., text-embedding-3-large)
└──────────────────┘
          │
          ▼
┌──────────────────┐     Dimensionality Reduction (UMAP) + Density-Based Spatial Clustering
│ 3. CLUSTERING    │ ──► (HDBSCAN). Pemisahan signal dari noise.
└──────────────────┘
          │
          ▼
┌──────────────────┐     LLM Synthesis Engine mengekstrak: Core Job-to-be-Done, Unmet Need,
│ 4. SYNTHESIS     │ ──► Root-Cause Friction, Severity, & Stochastic vs Deterministik check
└──────────────────┘
          │
          ▼
┌──────────────────┐     Uji hipotesis menggunakan 'Shadow Mode' atau 'Wizard of Oz'
│ 5. VALIDATION    │ ──► Kuantifikasi Willingness-to-Delegate (WTD) & Metrik Otonomi.
└──────────────────┘
```

### Langkah Kerja Sistematis:
1. **Ingestion & Sanitasi**: Menarik data interaksi mentah berskala besar dari CRM, ticketing system, dan OpenTelemetry traces. Lakukan pembersihan PII (*Personally Identifiable Information*) untuk kepatuhan regulasi (GDPR, UU PDP).
2. **Semantic Vectorization**: Memetakan setiap keluhan/friksi ke dalam ruang multidimensi menggunakan embedding model berkinerja tinggi.
3. **Unsupervised Topic Modeling**: Mengelompokkan masalah secara otomatis tanpa bias taksonomi internal perusahaan menggunakan algoritma clustering adaptif.
4. **Agentic Problem Extraction**: Menginstruksikan LLM untuk mengaudit setiap cluster masalah, memisahkan aspek emosional dari aspek kegagalan fungsional, dan mengevaluasi apakah masalah tersebut memerlukan:
   - Rules engine biasa (Deterministik),
   - Predictive Model / Classical ML,
   - Generative AI / RAG, atau
   - Multi-Agent Autonomous System.
5. **Willingness-to-Delegate (WTD) Validation**: Mengukur apakah pengguna bersedia mendelegasikan tugas tersebut secara penuh ke agen otonom melalui eksperimen prototipe bertingkat (*Shadow Mode Deployment*).

---

## 6. Analogy & Diagram ASCII

### Analogi: Sonar Bawah Air vs. Radar Optik
Mencari *problem space* untuk software konvensional itu seperti menggunakan **Radar Optik**: objek terlihat jelas di atas permukaan air, garis batasnya tegas (sukses/gagal form submit), dan jalurnya dapat dipetakan langsung.

Sebaliknya, mencari *problem space* untuk AI & Autonomous Agents seperti menggunakan **Sonar Bawah Air**:
- Sinyal terdistorsi oleh noise lingkungan (data yang kotor, konteks bisnis yang dinamis).
- Anda mendeteksi probabilitas keberadaan objek (kebutuhan laten pengguna), bukan kepastian absolut.
- Jika Anda mengarahkan kapal (membangun model AI) hanya berdasarkan dugaan visual, kapal Anda akan menabrak karang di bawah laut (edge cases yang tak terprediksi). Anda harus memancarkan gelombang sonar terus-menerus (telemetri & semantic clustering) untuk memetakan topografi dasar laut.

### Arsitektur Data Discovery Pipeline (ASCII)
```
+---------------------------------------------------------------------------------------------------+
| PRODUCTION PROBLEM DISCOVERY & TELEMETRY ARCHITECTURE FOR AI PM                                   |
+---------------------------------------------------------------------------------------------------+

 [Customer Friction Sources]
  +-------------------------+
  | Support Desk (Zendesk)  |---+
  +-------------------------+   |
  +-------------------------+   |     +-------------------------+     +---------------------------+
  | Sales Call Audio/Text   |---+---> | Ingestion Gateway       | --> | Kafka / Event Streaming   |
  +-------------------------+   |     | (PII Masking, Redaction)|     | Topic: user-friction-raw  |
  +-------------------------+   |     +-------------------------+     +---------------------------+
  | App Traces (Telemetry)  |---+                                                   |
  +-------------------------+                                                       v
                                                                      +---------------------------+
                                                                      | Consumer Microservice     |
                                                                      | (Async Chunk & Normalize) |
                                                                      +---------------------------+
                                                                                    |
                                                                                    v
                                                                      +---------------------------+
                                                                      | Vector Embedding Engine   |
                                                                      | (text-embedding-3-small)  |
                                                                      +---------------------------+
                                                                                    |
                                                                                    v
                                                                      +---------------------------+
                                                                      | Vector Store (Qdrant/     |
                                                                      | pgvector) + Metadata Index|
                                                                      +---------------------------+
                                                                                    |
  +---------------------------------------------------------------------------------+
  |
  v
+---------------------------------------------------------------------------------------------------+
| BATCH ANALYTICS & PROBLEM SPACE DISCOVERY RUNNER                                                  |
+---------------------------------------------------------------------------------------------------+
  |
  +---> [HDBSCAN Clustering Engine]
  |       |
  |       v
  |     Identified Dense Semantic Clusters (Discovered Problems)
  |       |
  |       v
  +---> [LLM Discovery Agent (Claude 3.5 Sonnet / GPT-4o)]
          | - Evaluasi Intent Ambiguity
          | - Hitung Stochastic vs Deterministic Fit
          | - Ekstraksi Failure Modes
          v
+---------------------------------------------------------------------------------------------------+
| AI PM PROBLEM SPACE COCKPIT (ClickHouse + Metabase / Custom PRD Engine)                           |
+---------------------------------------------------------------------------------------------------+
| Cluster ID | Pain Point Theme       | Freq/Mo | EVC ($) | Accuracy Req | Agent Candidate? | Risk |
|------------|------------------------|---------|---------|--------------|------------------|------|
| C-104      | Cross-Border Tax Recon | 14,200  | $420K   | 99.95%       | Hybrid (Agent+HIL| CRIT |
| C-202      | Reset OTP via Chat     | 45,100  | $45K    | 100.0%       | NO (Deterministic| LOW  |
| C-309      | Ambiguous RFP Parsing  | 1,800   | $890K   | 92.00%       | YES (RAG Agent)  | MED  |
+---------------------------------------------------------------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### 7.1 Simple Example: JSON Schema untuk Masalah Stokastik
Sebelum menulis kode analisis, AI PM harus mendefinisikan kontrak spesifikasi masalah dalam bentuk skema validasi.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AIProblemSpaceDefinition",
  "type": "object",
  "properties": {
    "problem_id": { "type": "string" },
    "job_to_be_done": { "type": "string" },
    "nature_of_computation": { 
      "type": "string", 
      "enum": ["deterministic_rules", "predictive_ml", "generative_rag", "autonomous_agent"] 
    },
    "tolerance_profile": {
      "type": "object",
      "properties": {
        "max_acceptable_hallucination_rate": { "type": "number", "maximum": 0.05 },
        "critical_metric": { "type": "string", "enum": ["precision", "recall", "latency"] },
        "min_critical_metric_value": { "type": "number", "minimum": 0.80 }
      },
      "required": ["max_acceptable_hallucination_rate", "critical_metric", "min_critical_metric_value"]
    },
    "human_takeover_strategy": {
      "type": "string",
      "enum": ["shadow_mode", "review_before_execution", "post_audit", "immediate_escalation"]
    }
  },
  "required": ["problem_id", "job_to_be_done", "nature_of_computation", "tolerance_profile", "human_takeover_strategy"]
}
```

### 7.2 Practical Example: Enterprise Automated Discovery Pipeline
Implementasi skrip produksi untuk membaca umpan balik kualitatif pelanggan, melakukan *vector embedding*, mengelompokkan keluhan dengan algoritma *clustering* berbasis densitas, dan mengekstrak definisi problem space terstruktur untuk PM.

```python
"""
production_problem_discovery.py
Pipeline otomatis untuk mensintesis data kualitatif pelanggan menjadi AI Problem Space Definition.
Standar Arsitektur: AsyncIO, Scikit-Learn/HDBSCAN, Pydantic v2, OpenTelemetry Traced.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ValidationError
import numpy as np

# Simulasi client inference (Pada produksi: gunakan openai, anthropic, atau vLLM client)
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("AI-PM-Discovery")

# ==========================================
# 1. DOMAIN SCHEMAS (PYDANTIC V2)
# ==========================================

class RawCustomerFeedback(BaseModel):
    feedback_id: str
    tenant_id: str
    raw_text: str
    channel: str
    timestamp: int

class ProblemSpaceContract(BaseModel):
    cluster_id: int
    core_problem_statement: str = Field(description="Penjelasan masalah netral tanpa bias solusi")
    inferred_jtbd: str = Field(description="Job to be Done yang dicari pelanggan")
    suggested_archetype: str = Field(description="Deterministic / Classical ML / RAG / Multi-Agent")
    acceptable_error_rate: float = Field(ge=0.0, le=1.0)
    requires_human_in_the_loop: bool
    confidence_score: float = Field(ge=0.0, le=1.0)

# ==========================================
# 2. CORE PROCESSING SERVICE
# ==========================================

class SemanticDiscoveryEngine:
    def __init__(self, min_cluster_size: int = 2):
        self.min_cluster_size = min_cluster_size
        # Sederhana untuk kebutuhan runnable script; gunakan OpenAI text-embedding-3-small di production
        self.vectorizer = TfidfVectorizer(max_features=512, stop_words='english')
        self.clusterer = HDBSCAN(
            min_cluster_size=self.min_cluster_size, 
            metric='euclidean', 
            cluster_selection_epsilon=0.3
        )

    def fit_and_cluster(self, texts: List[str]) -> np.ndarray:
        logger.info(f"Mengonversi {len(texts)} feedback ke dalam representasi vector...")
        vectors = self.vectorizer.fit_transform(texts).toarray()
        logger.info("Menjalankan unsupervised density clustering (HDBSCAN)...")
        cluster_labels = self.clusterer.fit_predict(vectors)
        return cluster_labels

class ProblemSpaceSynthesizer:
    """
    Mensimulasikan evaluasi LLM Reasoning untuk menerjemahkan cluster teks 
    menjadi kontrak AI Problem Space.
    """
    @staticmethod
    async def evaluate_cluster_async(cluster_id: int, items: List[str]) -> Optional[ProblemSpaceContract]:
        logger.info(f"Menganalisis Cluster-{cluster_id} dengan total {len(items)} feedback...")
        await asyncio.sleep(0.1) # Simulasi latency API LLM
        
        combined_context = " | ".join(items)
        
        # Heuristik simulasi LLM reasoning berdasarkan kata kunci cluster
        lower_context = combined_context.lower()
        if "tax" in lower_context or "reconcil" in lower_context or "invoice" in lower_context:
            return ProblemSpaceContract(
                cluster_id=cluster_id,
                core_problem_statement="Ketidaksesuaian nilai PPh/PPN lintas entitas dokumen faktur manual.",
                inferred_jtbd="Menutup buku keuangan akhir bulan tanpa selisih audit pajak.",
                suggested_archetype="Deterministic Validation + Agentic Reconciliation",
                acceptable_error_rate=0.001,  # 0.1% toleransi eror
                requires_human_in_the_loop=True,
                confidence_score=0.96
            )
        elif "search" in lower_context or "find" in lower_context or "rfp" in lower_context:
            return ProblemSpaceContract(
                cluster_id=cluster_id,
                core_problem_statement="Kesulitan menemukan klausa kepatuhan spesifik pada dokumen tender PDF 500+ halaman.",
                inferred_jtbd="Memverifikasi pemenuhan syarat RFP secara cepat.",
                suggested_archetype="Generative RAG with Semantic Re-ranking",
                acceptable_error_rate=0.05,  # 5% toleransi eror
                requires_human_in_the_loop=False,
                confidence_score=0.89
            )
        else:
            return ProblemSpaceContract(
                cluster_id=cluster_id,
                core_problem_statement=f"Friction operasional berulang: {items[0][:60]}...",
                inferred_jtbd="Efisiensi pemrosesan workflow standar.",
                suggested_archetype="Classical ML / Heuristic Automation",
                acceptable_error_rate=0.02,
                requires_human_in_the_loop=False,
                confidence_score=0.75
            )

# ==========================================
# 3. ORCHESTRATION PIPELINE
# ==========================================

async def run_discovery_pipeline(dataset: List[RawCustomerFeedback]):
    print("\n" + "="*80)
    print("MEMULAI AI PRODUCT MANAGER PROBLEM DISCOVERY RUNNER")
    print("="*80 + "\n")
    
    texts = [d.raw_text for d in dataset]
    discovery_engine = SemanticDiscoveryEngine(min_cluster_size=2)
    labels = discovery_engine.fit_and_cluster(texts)
    
    # Kelompokkan feedback berdasarkan cluster ID
    clusters: Dict[int, List[str]] = {}
    for idx, label in enumerate(labels):
        if label == -1:
            # -1 merepresentasikan Noise pada HDBSCAN
            continue
        clusters.setdefault(label, []).append(texts[idx])
        
    synthesizer = ProblemSpaceSynthesizer()
    discovery_tasks = []
    
    for cluster_id, cluster_texts in clusters.items():
        task = synthesizer.evaluate_cluster_async(cluster_id, cluster_texts)
        discovery_tasks.append(task)
        
    results: List[ProblemSpaceContract] = await asyncio.gather(*discovery_tasks)
    
    print("\nHASIL SYNTHESIS: FORMAL AI PROBLEM SPECIFICATIONS")
    print("-" * 80)
    for pde in results:
        print(f"\n[CLUSTER {pde.cluster_id}]")
        print(f" Problem Statement : {pde.core_problem_statement}")
        print(f" JTBD              : {pde.inferred_jtbd}")
        print(f" Target Archetype  : {pde.suggested_archetype}")
        print(f" Error Budget      : Max {pde.acceptable_error_rate * 100}% Failure Rate")
        print(f" Human Guardrail   : {'Wajib Human-in-the-Loop' if pde.requires_human_in_the_loop else 'Fully Autonomous Allowed'}")
        print(f" PM Confidence     : {pde.confidence_score * 100:.1f}%\n" + "-"*40)

# ==========================================
# 4. RUNNABLE ENTRYPOINT
# ==========================================

if __name__ == "__main__":
    # Mock Data Telemetri Mentah dari Multi-Channel Support Enterprise
    sample_dataset = [
        RawCustomerFeedback(feedback_id="F-01", tenant_id="T-10", raw_text="Tim accounting saya menghabiskan 4 jam sehari mencocokkan invoice PDF dengan tax rate PPh 23 secara manual.", channel="interview", timestamp=1700000001),
        RawCustomerFeedback(feedback_id="F-02", tenant_id="T-11", raw_text="Pusing banget setiap akhir bulan rekonsiliasi nilai faktur pajak dan invoice selalu ada selisih sen.", channel="ticket", timestamp=1700000002),
        RawCustomerFeedback(feedback_id="F-03", tenant_id="T-12", raw_text="Sangat sulit mencari klausul penalti terminasi dalam file dokumen RFP tender berukuran 600 halaman.", channel="ticket", timestamp=1700000003),
        RawCustomerFeedback(feedback_id="F-04", tenant_id="T-13", raw_text="Saya butuh cara cepat mencari compliance requirement di tumpukan PDF RFP procurement.", channel="slack_connect", timestamp=1700000004),
        RawCustomerFeedback(feedback_id="F-05", tenant_id="T-14", raw_text="Sistem lambat saat login di jam 9 pagi.", channel="datadog_alert", timestamp=1700000005), # Noise
    ]
    
    asyncio.run(run_discovery_pipeline(sample_dataset))
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Autonomous Reconciliation Agent pada B2B FinTech (Volume $4.2B ARR)
- **Konteks**: Sebuah institusi perbankan B2B enterprise memproses lebih dari 450.000 faktur lintas batas setiap bulan. Lebih dari 120 staf operasional manual dialokasikan hanya untuk menangani *invoice exceptions* (faktur yang ditolak sistem kliring karena nama vendor berbeda sedikit, format nomor pajak tidak standar, atau kurs valas berbeda jam penutupan).
- **Kesalahan Pendekatan Discovery Awal**: VP of Product awalnya menginstruksikan tim: *"Buatkan LLM Chatbot di dashboard internal agar staf finance bisa bertanya di mana letak selisihnya."* Solusi ini gagal total saat tahap Alpha (adopsi pengguna < 4%) karena staf tidak ingin *chatting*; mereka ingin tugas tersebut selesai tanpa mereka sentuh.
- **Implementasi Systematic Problem Discovery**:
  1. **Telemetry Instrumentation**: Tim AI PM memasang telemetri audit log untuk melacak aksi staf selama 30 hari. Ditemukan bahwa 82% kasus selisih faktur diselesaikan hanya dengan 3 pola pengecekan database silang.
  2. **Problem Space Boundary**: PM mendefinisikan boundary yang sangat ketat:
     - *In-Scope*: Faktur dengan deviasi nilai tukar < 0.5% dan *string similarity* nama vendor > 85%.
     - *Out-of-Scope*: Faktur vendor baru tanpa histori transaksi > 6 bulan (risiko fraud).
     - *Error Tolerance*: False Acceptance Rate (FAR) harus **0.0000%** (Zero Tolerance untuk over-payment).
  3. **Willingness-to-Delegate (WTD) Testing**: Menggunakan *Shadow Mode Deployment*. Model dijalankan di belakang layar selama 60 hari tanpa eksekusi langsung. Hasil rekomendasi model dibandingkan secara *blind* terhadap keputusan staf senior.
- **Hasil Bisnis**:
  - Waktu rekonsiliasi turun dari 3.8 hari menjadi 14 menit per batch transaksi.
  - 64% volume anomali dialihkan ke *Full Autonomous Execution*, 36% dialihkan ke *Targeted Human Review*.
  - Penghematan operasional mencapai **$3.4M/tahun** dengan tingkat akurasi finansial 100%.

---

## 9. Trade-offs (Arsitektur & Manajemen Produk)

Setiap keputusan dalam mendefinisikan problem space AI selalu memiliki konsekuensi trade-off multidimensi:

| Dimensi Keputusan | Opsi A: Narrow Scope Problem Space | Opsi B: Broad Autonomous Problem Space |
| :--- | :--- | :--- |
| **Deskripsi** | Agen hanya mengeksekusi 1 sub-tugas tunggal (e.g., Data Extraction Only). | Agen diberi mandat menyeluruh (e.g., End-to-End Invoice Clearing). |
| **Latency** | **Sangat Rendah (< 500ms)**. Pipeline inferensi dapat di-cache dan dioptimasi secara lokal. | **Tinggi (5s – 45s)**. Multi-step reasoning (ReAct/Plan-and-Solve) memicu banyak model calls. |
| **Data Scalability** | **Sangat Tinggi**. Skema validasi deterministik menjamin data tidak *drift*. | **Rendah/Kompleks**. Memerlukan evaluasi terus menerus (*continuous eval loop*) terhadap state environment. |
| **Cost to Infer** | **Minimal**. Dapat menggunakan model SLM (Small Language Model) 3B–8B parameter. | **Eksponensial**. Membutuhkan LLM reasoning frontier (GPT-4o, Claude 3.5 Sonnet) dengan ribuan token per run. |
| **Customer Friction** | Pengguna tetap harus mengorkestrasi UI, namun merasa aman karena kendali penuh ada pada mereka. | Friksi operasional hilang, namun timbul *anxiety* (kecemasan) jika tidak disediakan log audit transparan. |

---

## 10. Common Mistakes & Troubleshooting

### Mistake 1: "The Hammer Looking for a Nail" (Solution-First Discovery)
- **Gejala**: Dokumen PRD dimulai dengan kalimat: *"Kita perlu menggunakan Multi-Agent System berbasis LangGraph untuk menangani onboarding pelanggan."*
- **Akar Masalah**: Ketertarikan tim teknik pada tren teknologi, bukan pada hambatan ekonomi pelanggan.
- **Troubleshooting**: Lakukan uji balik (*Inversion Test*). Tanyakan: *"Dapatkah masalah ini diselesaikan dengan PostgreSQL Transaction, Cron Job, dan Regex berbiaya $5/bulan?"* Jika jawabannya **Ya**, batalkan implementasi AI/Agents segera.

### Mistake 2: Mengabaikan "Long-Tail Edge Cases" pada Fase Problem Definition
- **Gejala**: Model bekerja sempurna saat demo dengan akurasi 95%, namun sistem crash atau menghasilkan output aneh saat uji coba produksi enterprise.
- **Akar Masalah**: PM hanya mengumpulkan representasi data happy-path. Pada sistem stokastik, 5% data *edge-case* mengonsumsi 95% biaya kompensasi komplain pelanggan.
- **Troubleshooting**: Terapkan metode **Adversarial Discovery Persona**. Dalam sesi wawancara atau pengujian data historis, cari secara aktif data anomali ekstrem (karakter tak biasa, format tanggal ambigu, skema fraud, injeksi instruksi teks tersembunyi).

### Mistake 3: Definisi Metrik Kesuksesan yang Tidak Terkalibrasi (Accuracy Trap)
- **Gejala**: Tim ML melaporkan akurasi model 98%, namun NPS pengguna turun drastis.
- **Akar Masalah**: Ketidaksesuaian metrik bisnis vs metrik ML. Jika sebuah dataset memiliki 99% data non-fraud dan 1% data fraud, model yang menebak "Non-Fraud" sepanjang waktu akan memiliki akurasi 99%, namun gagal total dalam mendeteksi fraud.
- **Troubleshooting**: Ganti metrik *Global Accuracy* dengan metrik operasional bernilai bisnis:
  - **Human Intervention Rate (HIR)**: Berapa kali per 100 transaksi staf manusia harus mengoreksi agen?
  - **Time-to-Resolution (TTR)**: Berapa total durasi yang dihemat dibanding proses baseline?

---

## 11. Best Practices (Production Checklist AI PM)

Gunakan checklist ini sebelum menyetujui sebuah inisiatif Problem Space masuk ke tahap Engineering/ML Sprint:

- [ ] **Data Substrate Audit**: Apakah tersedia minimal 10.000 log data historis yang merepresentasikan masalah di lingkungan produksi nyata?
- [ ] **Ground Truth Determinism**: Apakah tim manusia sepakat minimal 90% terhadap jawaban yang benar dari data historis tersebut (*Inter-Annotator Agreement*)?
- [ ] **Error Asymmetry Evaluation**: Sudahkah Anda memetakan konsekuensi dari *False Positive* vs *False Negative* secara eksplisit?
- [ ] **Fallback Topology**: Apakah ada mekanisme pengalihan instan ke logic deterministik/manusia ketika skor keyakinan (*confidence score*) model berada di bawah ambang batas (misal: $< 0.85$)?
- [ ] **Cost-per-Unit Economics**: Apakah estimasi biaya inferensi token per task kurang dari 10% dari nilai penghematan operasional pengguna (*EVC*)?
- [ ] **Data Privacy & Governance**: Sudahkah data problem space disanitasi dari informasi PII/rahasia perusahaan sesuai dengan standar enkripsi SOC2 / ISO27001?
- [ ] **Willingness-to-Delegate (WTD) Metric**: Telah divalidasi bahwa pengguna memang bersedia melepaskan kontrol manual, bukan sekadar menginginkan interface konvensional yang lebih cepat.

---

## 12. Hands-on Practice

Buatlah implementasi pipeline discovery pelanggan di direktori lab lokal Anda: `hands-on/m02/`.

### Struktur File:
```
hands-on/m02/
├── requirements.txt
├── dataset.jsonl
├── discovery_pipeline.py
└── run.sh
```

### 1. `requirements.txt`
```text
scikit-learn>=1.4.0
pydantic>=2.6.0
numpy>=1.26.0
```

### 2. `dataset.jsonl`
```json
{"id": "EV-101", "source": "zendesk", "content": "Sistem gagal mengenali nama legal PT pada invoice saat ada karakter titik atau singkatan Tbk."}
{"id": "EV-102", "source": "zendesk", "content": "Ekstraksi nomor pokok wajib pajak sering salah baca digit angka 8 menjadi huruf B pada scan buram."}
{"id": "EV-103", "source": "slack", "content": "Tolong otomatisasi matching PO dan Bill. Format penulisan PT kami selalu ditolak agen karena tanda baca."}
{"id": "EV-104", "source": "interview", "content": "Kami butuh sistem yang bisa memvalidasi keabsahan faktur pajak langsung ke server DJP secara background."}
{"id": "EV-105", "source": "telemetry", "content": "User timeout after 120s at screen reconciliation_manual_override.action"}
{"id": "EV-106", "source": "telemetry", "content": "User timeout after 115s at screen reconciliation_manual_override.action"}
```

### 3. `discovery_pipeline.py`
```python
import json
import logging
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import AgglomerativeClustering

logging.basicConfig(level=logging.INFO, format="%(message)s")

class ProblemClusterOutput(BaseModel):
    cluster_tag: str
    sample_size: int
    primary_keywords: list[str]
    inferred_system_requirement: str

def execute():
    records = []
    with open("dataset.jsonl", "r") as f:
        for line in f:
            records.append(json.loads(line))
            
    docs = [r["content"] for r in records]
    
    vec = TfidfVectorizer(stop_words='english', max_features=100)
    X = vec.fit_transform(docs).toarray()
    
    # Menggunakan Agglomerative untuk cluster deterministik pada sampel data kecil
    model = AgglomerativeClustering(n_clusters=2)
    labels = model.fit_predict(X)
    
    features = vec.get_feature_names_out()
    
    for cluster_id in range(2):
        cluster_docs_indices = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_matrix = X[cluster_docs_indices]
        mean_weights = cluster_matrix.mean(axis=0)
        top_indices = mean_weights.argsort()[-3:][::-1]
        top_words = [features[i] for i in top_indices]
        
        req = "Fuzzy Entity Resolution & OCR Post-Correction" if any(w in top_words for w in ['invoice', 'pt', 'nomor']) else "Performance/Latency Optimization on Manual Screen"
        
        out = ProblemClusterOutput(
            cluster_tag=f"CLUSTER_TYPE_{cluster_id}",
            sample_size=len(cluster_docs_indices),
            primary_keywords=top_words,
            inferred_system_requirement=req
        )
        print(out.model_dump_json(indent=2))

if __name__ == "__main__":
    execute()
```

### 4. `run.sh`
```bash
#!/usr/bin/env bash
set -e
echo "Setting up hands-on discovery pipeline environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt
echo "Running automated cluster extraction..."
python3 discovery_pipeline.py
```

---

## 13. Exercise

### Level Easy
Perusahaan Anda memiliki log 10.000 komplain pelanggan per bulan. Dari data tersebut, 3.000 komplain berkaitan dengan *"Lupa password dan terkunci"*, 2.500 komplain terkait *"Status pengiriman barang lambat diperbarui"*, dan 200 komplain terkait *"Rekomendasi ukuran pakaian di e-commerce salah"*.
- **Tugas**: Klasifikasikan ketiga masalah ini ke dalam arsitektur: Deterministik Rule, Integrasi Telemetri/Cache, atau Machine Learning/AI. Tuliskan justifikasi 1 paragraf untuk setiap pilihan.

### Level Medium
Sebuah marketplace kesehatan ingin mengintegrasikan Agen AI untuk membaca resep tulisan tangan dokter dan langsung memesankan obat ke apotek mitra secara otomatis.
- **Tugas**: Rancang dokumen spesifikasi **Problem Definition Envelope (PDE)**. Cantumkan:
  1. *Cost of Inaccuracy* (analisis risiko klinis).
  2. *Acceptable Error Rate* (False Positive vs False Negative obat).
  3. Desain mekanisme *Human Takeover Trigger*.
  4. Metrik evaluasi operasional selain *Precision/Recall*.

### Level Hard
Rancang arsitektur telemetri pengawasan (*Observability & Continuous Problem Discovery*) untuk sebuah autonomous coding agent di enterprise. Sistem ini harus mampu mendeteksi secara *real-time* kapan agen mengalami *frustration loops* (mencoba memperbaiki error kompilasi kode yang sama lebih dari 3 kali berturut-turut) dan secara otomatis mengelompokkan jenis error arsitektur yang sering gagal diatasi oleh agen untuk dianalisis oleh PM.
- **Tugas**: Gambarkan diagram alir datanya dan tuliskan skema JSON payload event log yang harus dikirim ke Kafka/ClickHouse.

---

## 14. Challenge

### Studi Kasus: Multi-Tenant Enterprise Procurement Agent
Sebuah konglomerat multinasional memiliki 40 anak perusahaan dengan sistem ERP berbeda-beda (SAP, Oracle, NetSuite, dan database SQL on-premise lokal). Setiap entitas memiliki terminologi procurement yang bertentangan (misal: anak perusahaan A menyebut "PO Approved" ketika manajer menyetujui, anak perusahaan B menyebut "PO Approved" hanya setelah invoice pajak dicocokkan oleh finance).

Direksi menginginkan Anda membangun: **"Autonomous Global Spend Optimizer Agent"** yang dapat mengidentifikasi pemborosan vendor lintas anak perusahaan dan langsung melakukan negosiasi ulang harga kontrak secara otomatis via email vendor.

**Tantangan Eksekutif**:
1. Lakukan dekonstruksi *Problem Space*! Buktikan mengapa membangun agen yang *langsung menegosiasikan kontrak secara otonom* adalah bunuh diri produk (*product suicide*).
2. Tentukan **Boundary of Agency** (batas wewenang otonom) yang dapat diterima secara rasional oleh seluruh CFO anak perusahaan pada fase rilis v1.
3. Rancang matriks telemetri untuk mengukur friksi data (*Data Taxonomy Divergence Rate*) antar-anak perusahaan. Bagaimana Anda membuktikan bahwa kegagalan penemuan pola spend disebabkan oleh inkonsistensi taksonomi data, bukan karena model AI yang "kurang pintar"?

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa perbedaan paling fundamental antara mendefinisikan *Problem Space* pada software deterministik dibanding sistem AI/Agents?
   - A. Software deterministik tidak memerlukan user interview.
   - B. Sistem AI memerlukan spesifikasi toleransi kesalahan probabilitas (*error budget*) dan distribusi variabilitas input.
   - C. Sistem AI tidak dapat diukur menggunakan metrik bisnis kuantitatif.
   - D. Software deterministik selalu membutuhkan komputasi cloud berskala besar.

2. Manakah dari masalah berikut yang **PALING TIDAK COCOK** diselesaikan menggunakan Autonomous Generative Agent?
   - A. Menghitung formula PPh 21 karyawan berdasarkan status pernikahan tetap.
   - B. Menyintesis ratusan halaman riset pasar industri menjadi poin eksekutif.
   - C. Mengekstrak intent dari rekaman komplain pelanggan yang emosional.
   - D. Mengubah instruksi natural language menjadi query database read-only.

3. Apa yang dimaksud dengan *Human Takeover Threshold* dalam perancangan produk AI?
   - A. Persentase staf operasional yang di-PHK setelah sistem AI diterapkan.
   - B. Ambang batas skor keyakinan (*confidence score*) di mana sistem berhenti mengeksekusi aksi otonom dan mengalihkan kendali ke operator manusia.
   - C. Waktu maksimal pengguna menggunakan aplikasi sebelum merasa lelah.
   - D. Batas jumlah request API per menit yang dapat ditoleransi server.

4. Dalam analisis masalah menggunakan NLP/Clustering, data berlabel -1 pada algoritma HDBSCAN merepresentasikan:
   - A. Masalah dengan prioritas paling tinggi.
   - B. Noise atau anomali data yang tidak masuk ke dalam cluster densitas mana pun.
   - C. Kesalahan sintaksis pada database.
   - D. Data yang dipastikan merupakan komplain bernilai finansial besar.

5. Apa risiko utama dari jebakan *The Sci-Fi Fallacy* saat melakukan discovery produk AI dengan klien enterprise?
   - A. Klien menolak semua jenis teknologi otomatisasi.
   - B. Klien mengekspresikan ekspektasi bahwa AI dapat menyelesaikan masalah ambigu tanpa data historis dan tanpa eror sedikit pun.
   - C. Biaya server menjadi lebih murah dari estimasi.
   - D. Tim engineering menolak menggunakan model komersial tertutup.

---

### Bagian 2: Intermediate (Pilihan Ganda & Analisis Kasus Singkat)
6. Sebuah tim PM meluncurkan fitur auto-reply email customer service menggunakan LLM dengan metrik evaluasi akurasi semantik 94%. Namun, tingkat eskalasi tiket ke manusia justru meningkat 30%. Apa analisis akar masalah yang paling tepat dari sudut pandang problem space?
   - A. Latensi server model AI terlalu cepat.
   - B. 6% kesalahan model terjadi pada kasus-kasus kritis bernilai hukum tinggi yang memicu kepanikan dan komplain ulang pengguna.
   - C. User interface aplikasi tidak memiliki dark mode.
   - D. Jumlah training data model terlalu banyak.

7. Teknik discovery mana yang paling efektif untuk memvalidasi *Willingness-to-Delegate* pengguna tanpa menulis arsitektur agen yang kompleks?
   - A. Survei kuesioner Google Form berhadiah voucher.
   - B. *Wizard of Oz Prototyping* (manusia di belakang layar mensimulasikan aksi agen secara manual).
   - C. Melatih model open-source 70B dari awal (*pre-training*).
   - D. Membeli laporan riset pasar global dari analis pihak ketiga.

8. Dalam context-aware agent systems, mengapa *Context Horizon* wajib dibatasi secara ketat dalam problem definition?
   - A. Agar token limit context window tidak meledak, menekan biaya inferensi, dan mencegah distorsi perhatian model (*attention dilution*).
   - B. Karena model AI tidak dapat membaca teks lebih dari 50 kata.
   - C. Agar database SQL tidak perlu menggunakan indexing.
   - D. Untuk menghindari kewajiban mematuhi undang-undang privasi data.

9. Metrik *Human Intervention Rate (HIR)* bernilai 0.02. Apa arti operasional dari angka ini bagi seorang AI PM?
   - A. Agen menghasilkan 98 kesalahan setiap 100 aksi.
   - B. Dari 100 tugas yang dieksekusi agen, rata-rata hanya 2 tugas yang membutuhkan intervensi korektif dari operator manusia.
   - C. 2% pengguna menghapus akun mereka.
   - D. Model AI membutuhkan waktu komputasi 2 detik per transaksi.

10. Ketika menganalisis *Cost of Inaccuracy* untuk produk diagnosis medis berbasis AI, pendekatan toleransi eror manakah yang wajib diambil?
    - A. Memaksimalkan Precision, mengabaikan Recall (False Positive tidak masalah).
    - B. Memaksimalkan Recall mendekati 100% untuk meminimalisasi False Negative (kasus penyakit tidak boleh terlewat), dengan konsekuensi False Positive ditangani oleh evaluasi dokter sekunder.
    - C. Menyeimbangkan keduanya pada nilai 50%.
    - D. Menyerahkan sepenuhnya kepada agen tanpa supervisi dokter.

---

### Bagian 3: Skenario Kasus Produksi (Analisis Komprehensif)
11. **Skenario 1**: Anda adalah Principal AI PM di perusahaan asuransi digital. Manajemen ingin meluncurkan fitur klaim instan otonom (*Instant Claim Agent*). Klaim di bawah Rp 5.000.000 disetujui otomatis oleh sistem dalam 10 detik setelah pengguna mengunggah foto kuitansi rumah sakit.
    - *Pertanyaan Kasus*: Bagaimana Anda merumuskan batasan toleransi *False Acceptance Rate* (membayar klaim palsu/fraud) vs *Customer Churn* akibat *False Rejection* (klaim asli ditolak/tertunda)? Apa arsitektur validasi *problem space* yang Anda pasang sebelum fitur ini dibuka ke publik?

12. **Skenario 2**: Tim customer service Anda mengeluh kewalahan membaca log obrolan pengguna yang tidak puas dengan bot perusahaan. Transkrip chat mencapai 50.000 sesi per hari. Anda tidak memiliki anggaran komputasi untuk menjalankan analisis model GPT-4o pada seluruh 50.000 dokumen teks tersebut setiap hari.
    - *Pertanyaan Kasus*: Rancang arsitektur filtering dan sampling bertingkat (*Tiered Discovery Pipeline*) untuk mengekstrak anomali dan problem space baru dari 50.000 data tersebut dengan efisiensi biaya komputasi maksimal!

13. **Skenario 3**: Dalam implementasi *Autonomous IT-Ops Agent* yang bertugas me-restart server microservice yang bermasalah secara otomatis, metrik telemetri menunjukkan bahwa agen memiliki tingkat keberhasilan 99% dalam mengembalikan uptime server. Namun, pada 1% kasus, agen me-restart *Master Database Cluster* di jam kerja sibuk, yang melanggar SLA ketersediaan enterprise sebesar $500,000.
    - *Pertanyaan Kasus*: Tunjukkan letak kegagalan dalam spesifikasi *Problem Definition Envelope* awal PM! Bagaimana Anda menyusun ulang boundary rule agent tersebut untuk mencegah kegagalan katastropik serupa?

---

### Kunci Jawaban & Evaluasi

#### Kunci Bagian 1: Basic
1. **B** — Masalah deterministik memiliki solusi pasti; AI beroperasi dalam distribusi probabilitas sehingga menuntut batasan batas toleransi eror (*error budget*) dan variabilitas input.
2. **A** — Perhitungan pajak adalah aturan deterministik murni; menggunakan generative AI justru memperkenalkan risiko halusinasi yang tidak perlu pada domain yang seharusnya 100% eksak.
3. **B** — Definisi presisi dari *Human Takeover Threshold* adalah batas probabilitas/confidence di mana otonomi dicabut dan dialihkan ke manusia demi mitigasi risiko.
4. **B** — Pada algoritma clustering berbasis densitas (HDBSCAN), -1 dikhususkan untuk data outlier/noise yang terisolasi dari cluster umum.
5. **B** — *Sci-Fi Fallacy* menciptakan ekspektasi irasional bahwa AI itu magis, sehingga pelanggan menuntut nol kesalahan pada masalah yang sangat ambigu.

#### Kunci Bagian 2: Intermediate
6. **B** — Akurasi global sering menutupi keparahan dari 6% *tail-risk errors*. Dalam sistem enterprise, beberapa eror kecil pada ranah regulasi/hukum berdampak jauh lebih masif dibanding ratusan keberhasilan sepele.
7. **B** — *Wizard of Oz* memungkinkan pengujian psikologis pengguna (apakah mereka percaya dan bersedia mendelegasikan tugas) secara riil tanpa biaya pengembangan model yang mahal di awal.
8. **A** — Memperlebar konteks tanpa batas meningkatkan biaya inferensi secara eksponensial dan memicu fenomena *Lost in the Middle*, di mana LLM gagal memproses instruksi penting.
9. **B** — HIR = 0.02 berarti dari 100 aksi agen, hanya 2 yang memerlukan campur tangan korektif manusia.
10. **B** — Pada domain medis berisiko tinggi (*high-stakes*), False Negative (gagal mendeteksi penyakit) berakibat fatal (kematian pasien). Maka, Recall wajib dimaksimalkan, sementara False Positive disaring melalui second-opinion dokter manusia.

#### Panduan Jawaban Bagian 3: Skenario Kasus Produksi
11. **Panduan Skenario 1**:
    - *Error Budgeting*: Tentukan *asymmetric loss function*. Kerugian finansial fraud klaim Rp 5 juta dapat diprediksi secara statistik (misal dialokasikan cadangan risiko fraud 1.5% dari total klaim), namun kerugian reputasi akibat menolak klaim valid nasabah sakit dapat menghancurkan bisnis.
    - *Solusi Boundary*: Klaim instan tidak boleh langsung "Menolak" (*Reject*). Otonomi agen hanya dua: *Approve Instantly* (jika confidence score > 0.98 dan verifikasi NIK/Rumah Sakit klop secara deterministik) atau *Route to Human Adjuster* (jika ada ambiguitas data). Jangan biarkan agen melakukan auto-reject di fase awal.
12. **Panduan Skenario 2**:
    - *Tier 1 (Zero-Cost Filter)*: Filter regex/heuristik untuk menyaring sesi yang memiliki durasi < 2 chat atau status "resolved by user".
    - *Tier 2 (Statistical/Embeddings)*: Gunakan model embedding lokal/murah (e.g., MiniLM) atau TF-IDF untuk mendeteksi outlier dan kluster percakapan dengan sentimen negatif / eskalasi tinggi.
    - *Tier 3 (LLM Reasoning)*: Jalankan LLM canggih hanya pada 2–5 representasi pusat kluster (*medoids*) dari kelompok tiket anomali tersebut untuk menghasilkan laporan sintesis problem space harian.
13. **Panduan Skenario 3**:
    - *Akar Masalah*: PM mendefinisikan *State Space* dan *Action Space* terlalu luas tanpa mendefinisikan *Negative Inviolable Constraints* (batasan mutlak yang tak boleh dilanggar). Agen hanya dioptimasi untuk memulihkan metric uptime target, bukan memproteksi core cluster.
    - *Remediasi*: Terapkan arsitektur *Deterministic Guardrail Policy*. Action `restart` hanya diperbolehkan pada node dengan tag `env:stateless-worker`. Jika target node memiliki tag `tier:database` atau `role:cluster-master`, sistem harus menolak eksekusi agen secara fisik melalui *RBAC enforcement layer*, terlepas dari seberapa yakin agen tersebut bahwa restart akan menyelesaikan masalah.

---

## 16. Summary

1. **Problem Space AI Bersifat Probabilistik**: Mendefinisikan produk AI bukan tentang membuat daftar fungsionalitas UI, melainkan memetakan ruang probabilitas, batas ketidakpastian (*entropy boundary*), dan biaya ketidaktepatan data (*cost of failure*).
2. **Kuantifikasi Discovery Melalui Semantik dan Telemetri**: Jangan hanya bersandar pada wawancara kualitatif konvensional. Gunakan kombinasi *telemetry tracking*, *vector embeddings*, dan *density-based clustering* untuk mengekstrak masalah tersembunyi yang berulang pada skala enterprise.
3. **Problem Definition Envelope (PDE)**: Setiap inisiatif AI wajib memiliki kontrak batasan yang jelas, mencakup *Intent Boundary*, *Acceptable Error Rate*, profil resiko False Positive/Negative, dan strategi *Human Takeover*.
4. **Pemisahan Tegas Komputasi**: AI PM handal menolak penggunaan Generative AI/Autonomous Agents pada masalah yang secara fundamental lebih efisien, murah, dan aman diselesaikan menggunakan aturan logika deterministik standar.