# Bab 02: Customer Discovery & Problem Space Definition
## Modul 01: Problem-Space Engineering & Agentic Viability Framework

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Technical Product Manager (AI/Data PM) diharapkan mampu:
- **Mendiferensiasikan Problem Space AI vs. Software Deterministik**: Memetakan domain masalah pelanggan secara presisi ke dalam empat kuadran komputasi: Deterministik, Machine Learning Klasik, LLM/GenAI Statis, dan *Autonomous Agentic Workflows*.
- **Mengukur *Agentic Viability Score* (AVS)**: Mengkalkulasi kelayakan penerapan *autonomous agent* pada suatu *use case* menggunakan framework kuantitatif berbasis kompleksitas *state*, ambiguitas lingkungan, dan toleransi kegagalan (*blast radius*).
- **Merumuskan *Probabilistic Problem Requirements Document* (PRD)**: Menyusun spesifikasi produk probabilistik yang mencakup *Non-Functional Requirements* (NFR) spesifik AI: *Latency Budget*, *Cost-per-Task Target*, *Acceptable Error Threshold*, dan *Graceful Degradation Boundaries*.
- **Membangun Discovery-to-NFR Evaluation Engine**: Mengimplementasikan sistem analitik berbasis Python untuk membedah transkrip *customer discovery*, mengekstrak friksi alur kerja, dan memetakan batasan operasional agen secara otomatis.

---

### 2. Concept Overview

Dalam rekayasa perangkat lunak konvensional, penemuan masalah berpusat pada penangkapan *user journey* deterministik: input $X$ harus selalu menghasilkan output $Y$ melalui alur kerja terstruktur. Namun, pada ekosistem **AI, Data, dan Autonomous Agents**, Product Manager menghadapi **Probabilistic Problem Space**.

```
    [ Ambang Batas Ketidakpastian Lingkungan (Uncertainty) ]
                       ▲
                       │
       Kuadran II      │      Kuadran IV
      GenAI Statis     │   Autonomous Agents
     (RAG, Summary)    │  (ReAct, Tool-Use, Swarm)
                       │
  ─────────────────────┼─────────────────────► [ Derajat Otonomi yang
                       │                         Dibutuhkan (Autonomy) ]
       Kuadran I       │      Kuadran III
      Deterministik    │      Klasik ML
     (CRUD, Rule-Base) │  (Prediksi, Klasifikasi)
                       │
```

#### Mental Model: The Autonomy-Risk Paradox
Semakin tinggi variasi lingkungan kerja dan kebutuhan otonomi tugas (*task autonomy*), semakin besar risiko kegagalan sistem (*blast radius*). Kesalahan fundamental Technical PM dalam domain AI adalah memaksakan solusi agen otonom pada masalah yang dapat diselesaikan dengan aturan deterministik sederhana (*rule-based engine*) atau otomasi berbasis API biasa.

Pendekatan *Problem Space Definition* untuk agen cerdas menuntut dekonstruksi tugas ke dalam tiga parameter fundamental:
1. **Perceptual Ambiguity**: Sejauh mana data masukan tidak terstruktur dan memerlukan pemahaman semantik tingkat tinggi.
2. **Action Space Volatility**: Seberapa dinamis langkah-langkah yang harus diambil untuk mencapai kondisi akhir (*goal state*).
3. **Failure Cost Convexity**: Apakah dampak kesalahan bersifat linear (dapat diabaikan/diperbaiki pengguna dalam hitungan detik) atau konveks (menimbulkan kerugian finansial, hukum, atau reputasi yang fatal).

---

### 3. Why It Matters

Berdasarkan benchmark industri dan observasi *post-mortem* enterprise AI deployment:
- **80% kegagalan inisiatif AI Agent enterprise** berakar pada ketidakmampuan PM mendefinisikan *boundary* masalah. Penggunaan agen probabilistik pada proses deterministik menyebabkan pembengkakan biaya komputasi hingga $12\times$ lipat dan deviasi SLA latensi dari $<200\text{ms}$ menjadi $>15\text{ detik}$.
- **Cost-of-Inference Traps**: Mengotomatisasi proses bisnis bernilai rendah menggunakan rantai *reasoning* agen multi-langkah (seperti CoT atau ReAct) mengikis margin unit ekonomi produk sebelum mencapai *product-market fit*.
- **Safety and Alignment Exposure**: Kegagalan memetakan batas *blast radius* pada tahap *discovery* membuka risiko eksploitasi sistemik (misal: eksekusi *SQL injection* atau aksi destruktif via integrasi *agent-to-tool*) tanpa persetujuan manusia (*Human-in-the-Loop*).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut menggambarkan arsitektur pipeline penemuan masalah (*Discovery Engine Architecture*) yang mengonversi wawancara kualitatif pelanggan menjadi artefak teknis probabilistik:

```
+-----------------------------------------------------------------------------------+
|                        Customer Discovery Ingestion Layer                         |
|   [Transkrip Wawancara]      [Log Masalah CS]         [Observasi Manual Workflow] |
+-----------------------------------------+-----------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
|                      Semantic Extraction & Parsing Engine                         |
|  - Tokenizer & Entity Extraction                                                  |
|  - Intent Decomposition (Goal States, Pre-conditions, Invariants)                 |
+-----------------------------------------+-----------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
|                     Agentic Viability Scoring Engine (AVSE)                       |
|  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐  |
|  │  State Space Analysis │  │ Blast Radius Analysis │  │ Latency/Cost Model    │  |
|  └───────────────────────┘  └───────────────────────┘  └───────────────────────┘  |
+-----------------------------------------+-----------------------------------------+
                                          │
                                          ▼
+-----------------------------------------------------------------------------------+
|                        Product Problem Space Artifacts                            |
|  - Agentic Viability Classification (Deterministik vs GenAI vs Autonomous Agent)  |
|  - Maximum Tolerable Error Threshold (MTET) Specification                         |
|  - Human-in-the-Loop (HITL) Intervention Trigger Boundaries                       |
+-----------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. The Agentic Viability Scoring Framework (AVS)
Untuk menentukan apakah suatu problem space layak diselesaikan dengan *autonomous agent*, Technical PM harus mengevaluasi 4 dimensi terukur ($[0.0, 1.0]$):

1. **State Complexity ($S$)**: Variabilitas jalur penyelesaian tugas.
   $$S = 1 - \frac{\text{Jumlah Jalur Deterministik yang Diketahui}}{\text{Total Variasi Kondisi Skenario Riil}}$$
2. **Contextual Ambiguty ($C$)**: Tingkat ketidakpastian semantik masukan.
3. **Tool Interaction Requirement ($T$)**: Kebutuhan integrasi dinamis lintas sistem eksternal tanpa schema tetap.
4. **Blast Radius / Risk Matrix ($R$)**: Konsekuensi kerugian langsung jika agen mengambil tindakan keliru.

Skor Kelayakan Agen (*Agentic Viability Score* / AVS) diformulasikan sebagai:
$$\text{AVS} = \frac{(S \times 0.35) + (C \times 0.25) + (T \times 0.40)}{1 + R}$$

*Interpretasi Keputusan:*
- **$\text{AVS} < 0.25$**: **Deterministik**. Gunakan *hardcoded business logic*, SQL, atau workflow engine (misal: Temporal, Airflow).
- **$0.25 \le \text{AVS} < 0.50$**: **Predictive / Classical ML**. Gunakan model estimasi tabular atau NLP diskriminatif.
- **$0.50 \le \text{AVS} < 0.70$**: **Static GenAI / RAG**. Gunakan *single-shot/few-shot chain* dengan batasan pengambilan retrieval statis.
- **$\text{AVS} \ge 0.70$**: **Autonomous Agent Core**. Valid untuk menerapkan ReAct (*Reasoning + Action*), *Dynamic Tool Routing*, atau arsitektur multi-agen.

#### B. The Non-Deterministic Failure Budget (NDFB)
Seorang Technical PM dilarang keras menetapkan NFR performa AI sebagai "Akurasi 100%". Hal ini mustahil secara matematis dalam komputasi probabilistik. Sebagai gantinya, rancang spesifikasi menggunakan **Non-Deterministic Failure Budget (NDFB)**:

$$\text{NDFB} = (\text{Total Interaksi}) \times (1 - \text{Minimum Acceptable Precision})$$

Di dalam PRD probabilistik, batasan ini dibagi menjadi 3 level degradasi layanan:
1. **Graceful Clarification**: Agen mendeteksi ambiguitas tinggi dan meminta konfirmasi eksplisit dari pengguna sebelum bertindak.
2. **Human-In-The-Loop (HITL) Fallback**: Pemindahan status eksekusi secara mulus ke agen manusia saat ketidakpastian (*entropy*) output melampaui ambang batas keamanan.
3. **Hard Circuit Breaker**: Pemutusan eksekusi otonom instan dan penguncian sesi saat terdeteksi pelanggaran batasan operasional kritis (*invariant violation*).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi referensi produksi untuk **Agentic Viability Scoring & Discovery Analyzer Engine**. Kode ini dirancang dengan prinsip *clean architecture*, validasi tipe ketat menggunakan Pydantic v2, penanganan error defensif, dan struktur komputasi modular.

```python
"""
Core domain engine for analyzing customer discovery inputs and assessing 
agentic viability for Product Managers in the AI/Autonomous Agent space.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ExecutionParadigm(str, Enum):
    DETERMINISTIC = "DETERMINISTIC_RULES_OR_WORKFLOW"
    CLASSICAL_ML = "CLASSICAL_PREDICTIVE_ML"
    STATIC_GENAI = "STATIC_GENAI_OR_RAG"
    AUTONOMOUS_AGENT = "AUTONOMOUS_AGENTIC_WORKFLOW"


class BlastRadiusSeverity(str, Enum):
    LOW = "LOW"            # Kesalahan tidak berdampak materiil
    MEDIUM = "MEDIUM"      # Kesalahan menyebabkan friksi, dapat di-rollback
    HIGH = "HIGH"          # Kerugian finansial terbatas, perlu eskalasi
    CRITICAL = "CRITICAL"  # Pelanggaran kepatuhan/hukum, kerugian masif


class DiscoveryTaskRequirement(BaseModel):
    task_id: str = Field(..., description="Unique identifier untuk task yang diobservasi")
    task_name: str = Field(..., description="Nama fungsional task discovery")
    state_complexity: float = Field(
        ..., ge=0.0, le=1.0, 
        description="Variabilitas alur kerja; 0.0=sepenuhnya linier, 1.0=sangat ambigu"
    )
    contextual_ambiguity: float = Field(
        ..., ge=0.0, le=1.0, 
        description="Ketidakpastian data input; 0.0=skema kaku, 1.0=teks bebas/multimodal"
    )
    tool_interaction_need: float = Field(
        ..., ge=0.0, le=1.0, 
        description="Tingkat interaksi dinamis API eksternal; 0.0=internal DB, 1.0=open web/heterogen"
    )
    blast_radius: BlastRadiusSeverity = Field(
        ..., description="Tingkat keparahan dampak kegagalan operasional"
    )
    max_latency_budget_ms: int = Field(
        ..., gt=0, 
        description="Batas toleransi latensi eksekusi pengguna dalam milidetik"
    )
    max_cost_per_execution_usd: float = Field(
        ..., gt=0.0, 
        description="Unit economics threshold maksimum untuk task ini"
    )

    @field_validator("max_latency_budget_ms")
    @classmethod
    def validate_latency(cls, v: int) -> int:
        if v < 100:
            raise ValueError("Latensi di bawah 100ms tidak realistis untuk orchestration LLM apa pun.")
        return v


class ViabilityAssessmentResult(BaseModel):
    task_id: str
    viability_score: float
    recommended_paradigm: ExecutionParadigm
    requires_hitl: bool
    risk_adjusted_confidence: float
    justification: str


class ProblemSpaceDiscoveryEngine:
    """
    Mesin kalkulasi kualifikasi masalah untuk menentukan kelayakan sistem otonom.
    """
    
    # Koefisien pembobotan penentu otonomi
    WEIGHT_STATE: float = 0.35
    WEIGHT_AMBIGUITY: float = 0.25
    WEIGHT_TOOL: float = 0.40

    # Pinalti risiko berbasis keparahan blast radius
    BLAST_RADIUS_PENALTY: Dict[BlastRadiusSeverity, float] = {
        BlastRadiusSeverity.LOW: 0.05,
        BlastRadiusSeverity.MEDIUM: 0.25,
        BlastRadiusSeverity.HIGH: 0.65,
        BlastRadiusSeverity.CRITICAL: 1.50,
    }

    def __init__(self, high_autonomy_threshold: float = 0.65):
        if not (0.0 < high_autonomy_threshold < 1.0):
            raise ValueError("Ambang batas otonomi harus berada pada rentang (0.0, 1.0)")
        self.high_autonomy_threshold = high_autonomy_threshold

    def calculate_avs(self, req: DiscoveryTaskRequirement) -> float:
        raw_opportunity = (
            (req.state_complexity * self.WEIGHT_STATE) +
            (req.contextual_ambiguity * self.WEIGHT_AMBIGUITY) +
            (req.tool_interaction_need * self.WEIGHT_TOOL)
        )
        risk_penalty = self.BLAST_RADIUS_PENALTY[req.blast_radius]
        
        # Skor ternormalisasi dengan pinalti risiko penyebut konveks
        avs = raw_opportunity / (1.0 + risk_penalty)
        return round(float(avs), 4)

    def evaluate_task(self, req: DiscoveryTaskRequirement) -> ViabilityAssessmentResult:
        try:
            score = self.calculate_avs(req)
            
            # Determinasi paradigma berdasarkan batasan fisik dan skor
            if req.max_latency_budget_ms < 1500 and score >= self.high_autonomy_threshold:
                # Latensi ketat membatalkan implementasi agen multi-hop
                paradigm = ExecutionParadigm.STATIC_GENAI
                justification = (
                    "Kebutuhan alur kerja memenuhi kriteria otonomi, namun alokasi latensi "
                    f"({req.max_latency_budget_ms}ms) menolak ReAct/Agent loops. "
                    "Gunakan Single-shot/Semantic Cache RAG teroptimasi."
                )
                requires_hitl = req.blast_radius in [BlastRadiusSeverity.HIGH, BlastRadiusSeverity.CRITICAL]
            elif score < 0.25:
                paradigm = ExecutionParadigm.DETERMINISTIC
                justification = "Kompleksitas rendah dan risiko terstruktur. Gunakan software engineering deterministik standar."
                requires_hitl = False
            elif score < 0.50:
                paradigm = ExecutionParadigm.CLASSICAL_ML
                justification = "Pola statistik terdefinisi tanpa kebutuhan pemahaman kontekstual fleksibel."
                requires_hitl = False
            elif score < self.high_autonomy_threshold:
                paradigm = ExecutionParadigm.STATIC_GENAI
                justification = "Penanganan bahasa alami/konteks diperlukan, namun tidak membutuhkan eksekusi tool dinamis."
                requires_hitl = req.blast_radius in [BlastRadiusSeverity.HIGH, BlastRadiusSeverity.CRITICAL]
            else:
                paradigm = ExecutionParadigm.AUTONOMOUS_AGENT
                justification = (
                    "Tingkat ketidakpastian tinggi digabungkan dengan manipulasi eksternal tools. "
                    "Arsitektur Goal-driven Autonomous Agent direkomendasikan."
                )
                requires_hitl = req.blast_radius in [BlastRadiusSeverity.MEDIUM, BlastRadiusSeverity.HIGH, BlastRadiusSeverity.CRITICAL]

            # Evaluasi keyakinan terkalibrasi risiko
            confidence = max(0.1, round(1.0 - (self.BLAST_RADIUS_PENALTY[req.blast_radius] / 2.0), 2))

            return ViabilityAssessmentResult(
                task_id=req.task_id,
                viability_score=score,
                recommended_paradigm=paradigm,
                requires_hitl=requires_hitl,
                risk_adjusted_confidence=confidence,
                justification=justification
            )

        except Exception as err:
            # Pola pertahanan kegagalan gracefully
            raise RuntimeError(f"Gagal memproses validasi task {req.task_id}: {str(err)}") from err


# =====================================================================
# Production Execution Verification Pipeline
# =====================================================================
if __name__ == "__main__":
    discovery_samples: List[DiscoveryTaskRequirement] = [
        DiscoveryTaskRequirement(
            task_id="DISC-001",
            task_name="Pemrosesan Faktur Pajak Eksternal",
            state_complexity=0.3,
            contextual_ambiguity=0.4,
            tool_interaction_need=0.2,
            blast_radius=BlastRadiusSeverity.HIGH,
            max_latency_budget_ms=2000,
            max_cost_per_execution_usd=0.05
        ),
        DiscoveryTaskRequirement(
            task_id="DISC-002",
            task_name="Investigasi Fraud & Resolusi Suspended Account",
            state_complexity=0.85,
            contextual_ambiguity=0.9,
            tool_interaction_need=0.95,
            blast_radius=BlastRadiusSeverity.MEDIUM,
            max_latency_budget_ms=45000,
            max_cost_per_execution_usd=1.50
        ),
        DiscoveryTaskRequirement(
            task_id="DISC-003",
            task_name="Pencocokan Transaksi Kasir Otomatis",
            state_complexity=0.1,
            contextual_ambiguity=0.05,
            tool_interaction_need=0.1,
            blast_radius=BlastRadiusSeverity.CRITICAL,
            max_latency_budget_ms=300,
            max_cost_per_execution_usd=0.001
        )
    ]

    engine = ProblemSpaceDiscoveryEngine()

    print("=== HASIL EVALUASI CUSTOMER DISCOVERY PROBLEM SPACE ===")
    for task in discovery_samples:
        result = engine.evaluate_task(task)
        print(f"\nTask ID              : {result.task_id} ({task.task_name})")
        print(f"Viability Score      : {result.viability_score}")
        print(f"Rekomendasi Desain   : {result.recommended_paradigm.value}")
        print(f"Mandatory HITL Gate  : {result.requires_hitl}")
        print(f"Tingkat Keyakinan    : {result.risk_adjusted_confidence}")
        print(f"Analisis Rasional    : {result.justification}")
```

---

### 7. Edge Cases & Failure Modes

Pada fase penemuan masalah, Technical PM wajib mengidentifikasi kondisi batas (*edge cases*) probabilistik sebelum arsitektur sistem dirancang:

1. **The "Illusion of Omniscience" (Over-Delegation Trap)**:
   - *Failure Mode*: Pelanggan menghendaki satu agen serba bisa (*general-purpose agent*) untuk menyelesaikan seluruh spektrum masalah tanpa batasan input.
   - *Mitigation*: Terapkan dekomposisi masalah (*Task Decomposition*). Isolasi masalah menjadi *Single-Responsibility Sub-agents* dengan batas *pre-condition* dan *post-condition* yang tervalidasi skema JSON kaku.

2. **Latency-Autonomy Inversion**:
   - *Failure Mode*: Alur kerja membutuhkan eksekusi interaktif real-time ($< 800\text{ms}$), namun proses penuntasan masalah menuntut penalaran dinamis multi-langkah (*multi-turn loop*) yang memakan waktu $10\text{--}30\text{ detik}$.
   - *Mitigation*: Turunkan paradigma produk menjadi *Asynchronous Background Agent* atau konversi menjadi *Streaming Speculative Execution UI* dengan optimasi pemanggilan model deterministik.

3. **Silent State Corruption (Accumulated Drift)**:
   - *Failure Mode*: Agen melakukan serangkaian manipulasi *tool* di mana setiap langkah memiliki tingkat presisi $95\%$. Pada langkah ke-5, probabilitas kumulatif keberhasilan adalah $0.95^5 \approx 77.3\%$, merusak integritas *state* transaksi pengguna secara diam-diam.
   - *Mitigation*: Definisikan *State Rollback Transaction Protocol* dalam PRD. Setiap aksi mutasi *state* wajib memiliki fungsi pembalik (*undo/compensating transaction*) yang deterministik.

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi Arsitektural | Deterministic Workflow | Static GenAI / RAG | Autonomous Agents |
| :--- | :--- | :--- | :--- |
| **Biaya per Eksekusi** | Negligible ($\sim \$0.00001$) | Rendah ($\sim \$0.001 - \$0.01$) | Sangat Tinggi ($\sim \$0.05 - \$2.00$) |
| **Karakteristik Latensi** | Instan ($<50\text{ms}$) | Terprediksi ($500\text{ms} - 3\text{s}$) | Sangat Variatif ($5\text{s} - 60\text{s}+$) |
| **Toleransi Ketidakpastian** | Nol (Pecah jika skema berubah) | Sedang (Teks bebas terbatas) | Sangat Tinggi (Mampu merencanakan ulang) |
| **Kompleksitas Debugging** | Deterministik (Stack trace linier) | Probabilistik (Evaluasi Semantik) | Non-Deterministik (State-space combinatorial explosion) |
| **Risiko Eksekusi Liar** | Nol | Rendah (Halusinasi teks) | Kritis (Aksi destruktif via external tools) |

---

### 9. Best Practices & Standar Industri

- **Terapkan Discovery Interview Berbasis Toleransi Galat**: Jangan pernah tanyakan *"Fitur apa yang Anda inginkan?"*. Tanyakan: *"Jika sistem membuat kesalahan 3 kali dari 100 eksekusi, apa dampak finansial langsung terhadap operasional Anda?"*.
- **Golden Evaluation Dataset Pre-PRD**: Buat 50 kasus uji berbasis data riil pengguna (*edge cases*, input kotor, skenario serangan) **sebelum** merekrut insinyur untuk menulis *system prompt* atau logika agen.
- **Bi-directional Blast Radius Containment**: Terapkan prinsip hak akses minimum (*Least Privilege Principal*) untuk seluruh integrasi alat agen. Setiap aksi dengan dampak *High/Critical* wajib memiliki gerbang *Approval-as-a-Service* (HITL).
- **Unit Economics Viability Ratio**: Pastikan nilai penghematan waktu/biaya kerja pelanggan minimal bernilai $5\times$ lebih besar daripada biaya inferensi token komputasi agen ($Value \ge 5 \times COGS_{Inference}$).

---

### 10. Hands-on Lab Exercise

#### Skenario Kasus:
Anda adalah Principal AI Product Manager di platform *Procure-to-Pay* Enterprise. Tim Sales mengusulkan pembuatan *"Fully Autonomous Agentic Invoice Negotiation & Discrepancy Settlement Swarm"*. Tugas Anda adalah menganalisis problem space ini dan menentukan apakah masalah ini harus diselesaikan dengan agen otonom atau arsitektur lain.

#### Panduan Langkah demi Langkah:

1. **Langkah 1: Dekonstruksi Variabel Problem Space**
   Berdasarkan investigasi kualitatif terhadap tim Finance Operasional:
   - Format invoice bervariasi dari PDF terstruktur, gambar struk buram, hingga teks WhatsApp ($Contextual\ Ambiguity = 0.85$).
   - Alur resolusi perselisihan nilai pembayaran memiliki 3 cabang resmi dari pedoman kepatuhan internal, namun memiliki puluhan variasi komunikasi manusia ($State\ Complexity = 0.55$).
   - Agen diminta memicu transfer dana via API Core Banking secara langsung ($Blast\ Radius = CRITICAL$).
   - Latensi target maksimum: 5 detik.
   - Anggaran biaya per eksekusi: $\$0.10$.

2. **Langkah 2: Eksekusi Evaluasi Programatik**
   Gunakan kelas `ProblemSpaceDiscoveryEngine` dari Section 6:
   ```python
   finance_task = DiscoveryTaskRequirement(
       task_id="LAB-FINANCE-001",
       task_name="Autonomous Invoice Discrepancy Settlement",
       state_complexity=0.55,
       contextual_ambiguity=0.85,
       tool_interaction_need=0.70,
       blast_radius=BlastRadiusSeverity.CRITICAL,
       max_latency_budget_ms=5000,
       max_cost_per_execution_usd=0.10
   )

   engine = ProblemSpaceDiscoveryEngine()
   result = engine.evaluate_task(finance_task)
   print(result.model_dump_json(indent=2))
   ```

3. **Langkah 3: Perumusan Keputusan PRD (Deliverable)**
   Dokumentasikan kesimpulan problem space ke dalam format PRD defensif:
   - **Keputusan**: Tolak implementasi *Fully Autonomous Agent*.
   - **Solusi Alternatif Terpilih**: *Hybrid Semantic RAG + Deterministic Ledger Rules + Mandatory Human-in-the-Loop Sign-off*.
   - **Rasional Teknis**: Status *CRITICAL Blast Radius* menekan nilai kelayakan sistem agen otonom penuh. Agen dilarang mengeksekusi API pembayaran langsung; agen hanya bertugas mengumpulkan konteks, merangkum poin perselisihan faktur, dan menyajikan tombol persetujuan transfer kepada staf Finance. Nilai latensi budget 5 detik tidak memadai untuk multi-agent consensus verification.