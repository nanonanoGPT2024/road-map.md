# Bab 02: People Management: 1-on-1, Coaching, & Career Ladders

## Module 01: Engineering People Management Systems for AI & Autonomous Agent Teams

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Engineering Manager (EM) dan Technical Leader diharapkan mampu:

1. **Merancang & Mengeksekusi Dynamic 1-on-1 Cadence**: Mengoperasikan sistem 1-on-1 berbasis output leverage (Andy Grove framework) dengan siklus 30–60 menit mingguan/dua-mingguan, mencakup pemisahan 100% antara *tactical status update* dengan *coaching & career trajectory*.
2. **Menerapkan GROW Coaching Model pada Domain Probabilistik**: Menjalankan intervensi *coaching* terstruktur bagi AI/ML Research Scientists dan Agentic Platform Engineers saat menghadapi ketidakpastian eksperimen (misalnya: *negative experiment results*, degradasi metrik *evals*, atau regresi *reasoning loop*).
3. **Membangun Dual-Track Career Rubric (IC vs. Management)**: Mengartikulasikan dan mengkalibrasi matriks kompetensi granular dari L4 (Mid-level AI Engineer) hingga L7/L8 (Principal/Distinguished Agent Architect vs. Senior Engineering Manager) mencakup dimensi *Engineering Rigor*, *Autonomous Systems Architecture*, *Algorithmic Impact*, dan *Operational Excellence*.
4. **Mendeteksi & Memitigasi AI Talent Attrition & Burnout**: Mengidentifikasi sinyal anomali kinerja (*burnout signals*, *prompt fatigue*, komputasi *resource bottlenecks*) menggunakan *structured feedback loops* dan matriks retensi sebelum mencapai titik kegagalan (*resignation* atau *toxic behavior*).
5. **Mengimplementasikan People Analytics & Competency Tracking Engine**: Menulis sistem berbasis Python untuk mengevaluasi gap kompetensi insinyur secara objektif terhadap standar level matriks organisasi AI modern.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Mengelola tim rekayasa perangkat lunak tradisional didasarkan pada model deterministik: arsitektur sistem dipecah menjadi modul, tiket dibuat, dan dependensi dikelola dalam sprint linier. Namun, dalam ekosistem **AI, Data, & Autonomous Agents**, paradigma ini mengalami pergeseran mendasar:

```
Deterministic Engineering (Traditional SWE):
Input -> [Explicit Business Logic] -> Predictable Output
Management Metric: Throughput, Velocity, Deployment Frequency (DORA)

Probabilistic Engineering (AI & Autonomous Agents):
Input -> [Stochastic Model + Dynamic Tools + Agentic Loops] -> Probabilistic Output
Management Metric: Evaluation Rigor, Latency/Cost Optimization, Failure Mode Resilience
```

#### Mental Model 1: Managerial Leverage (Andy Grove)
Tanggung jawab seorang EM dihitung dari formula:
$$\text{Manager's Output} = \sum (\text{Team Output}) + \sum (\text{Neighboring Teams Influenced})$$

Dalam tim Autonomous Agents, *leverage* tertinggi bukan menulis *prompt* atau mengorkestrasi pipeline LangGraph/AutoGen sendiri, melainkan menghilangkan hambatan kognitif tim, mengarahkan alokasi komputasi/GPU secara strategis, dan membangun psikologis tim yang tangguh terhadap kegagalan eksperimen.

#### Mental Model 2: Situational Leadership Theory (Hersey-Blanchard) disesuaikan untuk AI
Seorang Staff Engineer yang terbiasa membangun microservices deterministik (kompetensi tinggi) bisa mendadak berada di tahap *Low Competence / High Commitment* saat ditugaskan merancang *multi-agent consensus protocol* dengan non-deterministic LLM failure rates. 

| Tahap Maturitas | Karakteristik AI/ML Engineer | Gaya Kepemimpinan EM |
| :--- | :--- | :--- |
| **D1: Low Competence, High Commitment** | Baru beralih dari SWE ke Agentic Systems; over-optimistis terhadap akurasi LLM zero-shot. | **Directing**: Berikan instruksi arsitektural eksplisit, framework evaluasi baku (*deterministic evals*), dan guardrails ketat. |
| **D2: Some Competence, Low Commitment** | Menghadapi *agent hallucination loops*, frustrasi karena metrik akurasi stagnan di 78%. | **Coaching**: Refleksi root-cause, validasi emosi kegagalan probabilistik, bimbingan desain ulang data test. |
| **D3: High Competence, Variable Commitment** | Senior AI Engineer ahli dalam LoRA fine-tuning & RAG, namun ragu mengambil peran kepemimpinan lintas tim. | **Supporting**: Fasilitasi ide, kurangi supervisi teknis mikro, libatkan dalam perancangan strategi tim. |
| **D4: High Competence, High Commitment** | Staff Agent Architect yang merancang *agent self-healing orchestration* skala produksi. | **Delegating**: Berikan problem space otonom, fokus pada pemenuhan anggaran komputasi dan proteksi regulasi. |

---

### 3. Why It Matters (Masalah Dunia Nyata & Kebutuhan Enterprise)

1. **Fenomena "The AI R&D Black Hole"**:
   Tanpa kerangka *coaching* dan *1-on-1* yang ketat, insinyur AI cenderung terjebak dalam *endless experimentation* tanpa dampak produk yang terukur. Eksperimen model berbulan-bulan tanpa metrik *baseline* yang jelas menghabiskan jutaan dolar biaya komputasi GPU cloud.
2. **Krisis Identitas Insinyur (IC vs EM)**:
   Banyak AI Researcher berkaliber tinggi dipaksa mengambil jalur People Management karena tidak adanya *Dual-Track Career Ladder* yang adil di perusahaan. Hasilnya adalah kepemimpinan tim yang rapuh dan hilangnya aset teknis utama organisasi.
3. **Burnout Akibat Kecepatan Siklus Industri (Model Obsolescence)**:
   Siklus rilis model fondasi (OpenAI, Anthropic, open-weights) terjadi dalam hitungan minggu. Fitur agentic kustom yang dibangun tim selama 3 bulan dapat menjadi usang dalam semalam karena update API model terbaru. EM wajib memiliki mekanisme psikologis dan strategis untuk menjaga resiliensi tim.

---

### 4. Arsitektur & Diagram Komponen

Sistem People Management yang modern dapat diabstraksikan sebagai siklus kontrol umpan balik (*closed-loop control system*) berbasis data kualitatif dan kuantitatif:

```
       +-------------------------------------------------------------------+
       |                       ORGANIZATION STRATEGY                       |
       |                (AI Roadmap, Compute CapEx, SLOs)                  |
       +---------------------------------+---------------------------------+
                                         |
                                         v
       +-------------------------------------------------------------------+
       |            TALENT FRAMEWORK: DUAL-TRACK CAREER LADDERS            |
       |   IC Track: L4 (SWE) -> L5 (Senior) -> L6 (Staff) -> L7 (Principal)|
       |   EM Track: M5 (Lead) -> M6 (Eng Manager) -> M7 (Director of AI)  |
       +---------------------------------+---------------------------------+
                                         |
              +--------------------------+--------------------------+
              |                                                     |
              v                                                     v
+-------------------------------+                     +-------------------------------+
|     CONTINUOUS CADENCE:       |                     |      COACHING ENGINE:         |
|     Weekly / Bi-weekly 1:1    |                     |      GROW FRAMEWORK           |
|-------------------------------|                     |-------------------------------|
| - Tactical Detachment         |                     | - Goal: Accuracy & Latency    |
| - Roadblock Extraction        |                     | - Reality: Eval Stagnation    |
| - Energy & Vector Check       |                     | - Options: Agentic Topology   |
| - Psychological Safety        |                     | - Will: Committed Next Sprint |
+---------------+---------------+                     +---------------+---------------+
                |                                                     |
                +--------------------------+--------------------------+
                                           |
                                           v
       +-------------------------------------------------------------------+
       |                   EVALUATION & CALIBRATION ENGINE                 |
       |-------------------------------------------------------------------|
       | - 360-Degree Feedback Graph (Peer, Stakeholder, Tech Leads)       |
       | - Objective Capability Matrix Scoring (Data, Agents, Evals, Arch) |
       | - Bias Mitigation Filter (Mitigate recency, halo, and luck bias)  |
       +-----------------------------------+-------------------------------+
                                           |
                                           v
       +-------------------------------------------------------------------+
       |                      OUTCOMES & INTERVENTIONS                     |
       | - Promotion Calibration    - Pip / Course Correction              |
       | - Compute Grant Allocation - Strategic Project Assignment          |
       +-------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Anatomi 1-on-1 Efektif untuk Tim AI/Data
1-on-1 **bukan** status update. Status update dilakukan asinkronus via linear/slack/dashboard. Struktur 45 menit 1-on-1:

*   **Menit 00–10: Agenda Insinyur (Vent & Top-of-Mind)**
    *   Fokus: Apa yang menguras energi mereka minggu ini? (cth: "Infrastruktur Ray cluster sering *out-of-memory*", "Evaluasi prompt non-deterministik membuat frustrasi").
*   **Menit 10–25: Coaching & Prioritas Strategis (GROW Iteration)**
    *   Fokus: Diskusi arsitektural tingkat tinggi, dinamika tim, atau mitigasi risiko teknis.
*   **Menit 25–40: Pengembangan Karir & Feedback Dua Arah**
    *   Fokus: Review progres menuju level berikutnya berdasarkan Career Ladder Matrix.
*   **Menit 40–45: Action Items & Komitmen Bersama**
    *   Fokus: Penugasan tindakan spesifik dengan batas waktu terukur.

#### B. The GROW Model yang Dikalibrasi untuk Masalah AI/Agent
*   **Goal**: "Apa target spesifik sistem otonom ini?" (*Bukan sekadar 'buat agent pintar', melainkan: 'Agent harus memiliki 95% tool-calling precision pada latency < 1.2 detik'*).
*   **Reality**: "Di mana bottleneck sekarang?" (*Evals manual lambat, synthetic datasets mengandung bias distribusi, context window bloat*).
*   **Options**: "Apa variabel arsitektural yang bisa kita ubah?" (*Router model distillation, chunking strategy switch, multi-turn self-critique implementation*).
*   **Will**: "Apa eksperimen terisolasi yang akan Anda selesaikan pada hari Kamis jam 14:00?"

#### C. Dual-Track Career Matrix: Domain AI & Autonomous Agents

```
Level      IC Track (Focus: Depth, Execution, Scope)         Management Track (Focus: Leverage, People, Org)
------------------------------------------------------------------------------------------------------------
L4         AI / Agent Software Engineer                      -
           - Menerapkan prompt chains & tool calling         
           - Menulis unit tests & baseline evals             
           - Memperbaiki bug pada RAG pipelines              

L5         Senior Autonomous Systems Engineer                Associate Engineering Manager (Tech Lead)
           - Mendesain stateful multi-agent workflows        - Mengarahkan sprint delivery untuk 4-6 engineer
           - Optimasi inference cost & latency engine        - Melakukan 1-on-1 rutin & review kode tim
           - Menulis reliable deterministic evals suite      - Koordinasi dependensi data pipeline

L6         Staff AI Systems Architect                        Engineering Manager (AI Platforms)
           - Mendesain platform orchestrator skala multi-org - Mengelola 8-15 engineer (SWE, Research, Ops)
           - Memetakan arsitektur self-healing agents        - Kalibrasi performa & kompensasi tim
           - Mentoring insinyur L4/L5 lintas tim             - Menyusun alokasi anggaran GPU & vendor API

L7         Principal AI Engineer / Fellow                    Director of Engineering (AI & Data)
           - Menentukan arah arsitektur AI perusahaan        - Mengelola multi-team (30+ engineers via managers)
           - Terobosan algoritma proprietary / fine-tuning   - Menentukan strategi AI talent & retensi org
           - Penentu standar keamanan, evals, & guardrails   - Bertanggung jawab pada ROI CapEx komputasi AI
```

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem People Analytics terstruktur berbasis domain-driven design dalam Python. Sistem ini memodelkan penilaian matriks kompetensi insinyur AI, melacak log 1-on-1, dan menghitung gap promosi secara objektif.

```python
"""
Core Domain Engine for Engineering Management:
Competency Matrix, 1-on-1 Tracking, and Promotion Calibration for AI Teams.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
import uuid


class TrackType(str, Enum):
    INDIVIDUAL_CONTRIBUTOR = "IC"
    MANAGEMENT = "M"


class CompetencyLevel(int, Enum):
    L4_ENGINEER = 4
    L5_SENIOR = 5
    L6_STAFF = 6
    L7_PRINCIPAL = 7


class CompetencyDomain(str, Enum):
    AGENTIC_SYSTEMS = "agentic_systems"
    EVALUATION_AND_DATA_RIGOR = "evaluation_and_data_rigor"
    OPERATIONAL_EXCELLENCE = "operational_excellence"
    SYSTEMIC_INFLUENCE = "systemic_influence"


@dataclass(frozen=True)
class CompetencyCriterion:
    criterion_id: str
    domain: CompetencyDomain
    level: CompetencyLevel
    title: str
    description: str


@dataclass
class EngineerProfile:
    engineer_id: uuid.UUID
    name: str
    track: TrackType
    current_level: CompetencyLevel
    hire_date: datetime
    skills: List[str] = field(default_factory=list)


@dataclass
class AssessmentScore:
    criterion_id: str
    score: float  # Scale 1.0 (Novice/Unmet) to 4.0 (Exemplary/Role Model)
    evidence: str
    assessor_id: uuid.UUID


@dataclass
class OneOnOneRecord:
    session_id: uuid.UUID
    engineer_id: uuid.UUID
    manager_id: uuid.UUID
    timestamp: datetime
    energy_score: int  # Scale 1 (Burnout risk) to 5 (Peak energy)
    growth_notes: str
    action_items: List[str]
    unresolved_blockers: List[str]


class CompetencyRegistry:
    """In-memory canonical storage of standardized level rubric criteria."""

    def __init__(self) -> None:
        self._rubric: Dict[str, CompetencyCriterion] = {}
        self._bootstrap_rubric()

    def _bootstrap_rubric(self) -> None:
        criteria = [
            CompetencyCriterion(
                criterion_id="AGENT-L5-01",
                domain=CompetencyDomain.AGENTIC_SYSTEMS,
                level=CompetencyLevel.L5_SENIOR,
                title="Fault-tolerant Multi-Agent Orchestration",
                description="Designs resilient tool-calling workflows with deterministic fallbacks when models hallucinate."
            ),
            CompetencyCriterion(
                criterion_id="AGENT-L6-01",
                domain=CompetencyDomain.AGENTIC_SYSTEMS,
                level=CompetencyLevel.L6_STAFF,
                title="Autonomous Architecture Strategy",
                description="Pioneers company-wide agent cognitive architecture; implements dynamic context window management."
            ),
            CompetencyCriterion(
                criterion_id="EVAL-L5-01",
                domain=CompetencyDomain.EVALUATION_AND_DATA_RIGOR,
                level=CompetencyLevel.L5_SENIOR,
                title="Automated Evaluation Frameworks",
                description="Implements synthetic test generation and LLM-as-a-judge pipelines with ground-truth correlation."
            ),
            CompetencyCriterion(
                criterion_id="EVAL-L6-01",
                domain=CompetencyDomain.EVALUATION_AND_DATA_RIGOR,
                level=CompetencyLevel.L6_STAFF,
                title="Enterprise AI Safety & Governance Systems",
                description="Builds organizational security, red-teaming, and evaluation benchmarks for zero-regression models."
            ),
            CompetencyCriterion(
                criterion_id="OPEX-L5-01",
                domain=CompetencyDomain.OPERATIONAL_EXCELLENCE,
                level=CompetencyLevel.L5_SENIOR,
                title="Inference Profiling and Cost Engineering",
                description="Reduces token utilization and p99 inference latency via caching, quantization, and batching."
            ),
        ]
        for c in criteria:
            self._rubric[c.criterion_id] = c

    def get_criterion(self, criterion_id: str) -> Optional[CompetencyCriterion]:
        return self._rubric.get(criterion_id)

    def get_criteria_by_level(self, level: CompetencyLevel) -> List[CompetencyCriterion]:
        return [c for c in self._rubric.values() if c.level == level]


class PromotionCalibrationEngine:
    """Evaluates readiness of engineers against targeted competency tiers."""

    BENCHMARK_MASTERY_SCORE = 3.0  # Threshold indicating reliable consistency

    def __init__(self, registry: CompetencyRegistry) -> None:
        self.registry = registry

    def calculate_readiness_gap(
        self,
        engineer: EngineerProfile,
        target_level: CompetencyLevel,
        evaluations: List[AssessmentScore],
    ) -> Dict[str, any]:
        target_criteria = self.registry.get_criteria_by_level(target_level)
        if not target_criteria:
            raise ValueError(f"No rubric criteria defined for target level: {target_level}")

        eval_map = {e.criterion_id: e for e in evaluations}
        criteria_breakdown = []
        scores_sum = 0.0
        met_criteria_count = 0

        for criterion in target_criteria:
            assessment = eval_map.get(criterion.criterion_id)
            score = assessment.score if assessment else 0.0
            evidence = assessment.evidence if assessment else "No empirical evidence recorded."
            is_met = score >= self.BENCHMARK_MASTERY_SCORE

            if is_met:
                met_criteria_count += 1
            scores_sum += score

            criteria_breakdown.append({
                "criterion_id": criterion.criterion_id,
                "domain": criterion.domain.value,
                "title": criterion.title,
                "score": score,
                "is_met": is_met,
                "evidence": evidence,
            })

        readiness_pct = (met_criteria_count / len(target_criteria)) * 100.0
        average_score = scores_sum / len(target_criteria)

        return {
            "engineer_id": str(engineer.engineer_id),
            "target_level": target_level.value,
            "readiness_percentage": round(readiness_pct, 2),
            "average_score": round(average_score, 2),
            "promotion_ready": readiness_pct >= 85.0 and average_score >= self.BENCHMARK_MASTERY_SCORE,
            "breakdown": criteria_breakdown,
        }


class OneOnOneHealthTracker:
    """Monitors 1-on-1 cadence, psychological safety, and burnout vectors."""

    BURNOUT_ENERGY_THRESHOLD = 2  # At or below indicates active fatigue

    def __init__(self) -> None:
        self._sessions: List[OneOnOneRecord] = []

    def record_session(self, record: OneOnOneRecord) -> None:
        self._sessions.append(record)

    def analyze_engineer_vitality(self, engineer_id: uuid.UUID) -> Dict[str, any]:
        engineer_sessions = sorted(
            [s for s in self._sessions if s.engineer_id == engineer_id],
            key=lambda x: x.timestamp,
        )

        if not engineer_sessions:
            return {"status": "NO_DATA", "risk_level": "UNKNOWN"}

        recent_sessions = engineer_sessions[-4:]  # Look back last 4 sessions
        avg_energy = sum(s.energy_score for s in recent_sessions) / len(recent_sessions)
        persisting_blockers = [
            b for s in recent_sessions for b in s.unresolved_blockers
        ]

        burnout_risk = "LOW"
        if avg_energy <= self.BURNOUT_ENERGY_THRESHOLD:
            burnout_risk = "HIGH"
        elif avg_energy <= 3.0:
            burnout_risk = "MEDIUM"

        return {
            "engineer_id": str(engineer_id),
            "total_sessions": len(engineer_sessions),
            "recent_average_energy": round(avg_energy, 2),
            "burnout_risk_level": burnout_risk,
            "unresolved_blockers_count": len(persisting_blockers),
            "active_blockers": persisting_blockers,
        }


# =====================================================================
# Production Execution Verification
# =====================================================================
if __name__ == "__main__":
    registry = CompetencyRegistry()
    evaluator = PromotionCalibrationEngine(registry)
    tracker = OneOnOneHealthTracker()

    alice_id = uuid.uuid4()
    bob_manager_id = uuid.uuid4()

    alice = EngineerProfile(
        engineer_id=alice_id,
        name="Alice Morales",
        track=TrackType.INDIVIDUAL_CONTRIBUTOR,
        current_level=CompetencyLevel.L4_ENGINEER,
        hire_date=datetime(2023, 1, 15, tzinfo=timezone.utc),
        skills=["Python", "LangGraph", "PyTorch", "vLLM"],
    )

    # 1. Ingest historical 1-on-1 records
    tracker.record_session(
        OneOnOneRecord(
            session_id=uuid.uuid4(),
            engineer_id=alice_id,
            manager_id=bob_manager_id,
            timestamp=datetime(2024, 10, 1, tzinfo=timezone.utc),
            energy_score=4,
            growth_notes="Motivated by new multi-agent planning algorithm.",
            action_items=["Ship benchmark harness."],
            unresolved_blockers=[],
        )
    )
    tracker.record_session(
        OneOnOneRecord(
            session_id=uuid.uuid4(),
            engineer_id=alice_id,
            manager_id=bob_manager_id,
            timestamp=datetime(2024, 10, 15, tzinfo=timezone.utc),
            energy_score=2,
            growth_notes="Frustrated with continuous CUDA out-of-memory errors on dev cluster.",
            action_items=["Escalate GPU provisioning."],
            unresolved_blockers=["GPU allocation pending Infra approval."],
        )
    )

    # 2. Evaluate Performance Calibration for Level 5 (Senior AI Engineer)
    evaluations = [
        AssessmentScore(
            criterion_id="AGENT-L5-01",
            score=3.5,
            evidence="Re-architected query agent to fall back to small dense model on timeout; zero critical outages.",
            assessor_id=bob_manager_id,
        ),
        AssessmentScore(
            criterion_id="EVAL-L5-01",
            score=3.0,
            evidence="Built LLM-as-a-judge framework validating 10,000 synthetic multi-turn conversations daily.",
            assessor_id=bob_manager_id,
        ),
        AssessmentScore(
            criterion_id="OPEX-L5-01",
            score=2.0,  # Below threshold
            evidence="Has not focused on KV cache compression or inference optimization profiling yet.",
            assessor_id=bob_manager_id,
        ),
    ]

    readiness = evaluator.calculate_readiness_gap(
        engineer=alice,
        target_level=CompetencyLevel.L5_SENIOR,
        evaluations=evaluations,
    )

    health_metrics = tracker.analyze_engineer_vitality(alice_id)

    print("=== PROMOTION READINESS REPORT ===")
    print(f"Target Level: L{readiness['target_level']}")
    print(f"Readiness Score: {readiness['readiness_percentage']}%")
    print(f"Average Score: {readiness['average_score']}")
    print(f"Ready for Promotion Committee: {readiness['promotion_ready']}")

    print("\n=== 1-ON-1 VITALITY & RETENTION REPORT ===")
    print(f"Burnout Risk: {health_metrics['burnout_risk_level']}")
    print(f"Recent Energy Index: {health_metrics['recent_average_energy']}/5.0")
    print(f"Persisting Blockers: {health_metrics['active_blockers']}")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Root Cause Teknis / Organisasional | Mitigasi Engineering Manager |
| :--- | :--- | :--- |
| **"The Brilliant Asshole" AI Researcher** | Karyawan memiliki output sitasi/algoritma superior, namun merusak *psychological safety*, menolak dokumentasi kode, dan merendahkan engineers lain. | **Separation of Impact**: Terapkan klausul *Systemic Influence* pada matriks karir. Nilai nol pada *collaboration rubric* memblokir kenaikan pangkat secara otomatis tanpa pengecualian. |
| **The "Negative Experiment" Stagnation Trap** | Tim AI menghabiskan waktu berminggu-minggu dengan metrik evaluasi yang tidak kunjung naik (misal: RAG precision tetap <80%). | **Redefine Output**: Ubah metrik penilaian dari *positive outcome* menjadi *learning velocity & hypothesis rigor*. Laporan eksperimen negatif yang terdokumentasi rapi dihitung sebagai delivery valid. |
| **Hype-Driven Technical Drift** | Insinyur terdistraksi framework open-source baru setiap minggu (misal: migrasi dari LangGraph ke AutoGen, lalu ke CrewAI tanpa urgensi arsitektur). | **Boundaries via SLOs**: Tetapkan batas evaluasi berbasis latency p99, token cost, dan stability. Framework baru hanya disetujui jika mengungguli baseline di lab benchmark internal. |
| **Silent Burnout ("Quiet Quitting" via Model Run Screens)** | Insinyur berpura-pura sibuk karena model training butuh waktu 14 jam, padahal mengalami demotivasi parah. | **Active Probing di 1-on-1**: Gunakan pertanyaan *probing*: *"Bagaimana arsitektur loss function kamu bereaksi pada checkpoint 500?"* dan pantau commit evaluasi unit code secara berkala. |

---

### 8. Trade-offs & Alternatif Solusi

#### Dual Track (IC vs. EM) vs. Hybrid Player-Coach
*   *Pilihan A: Dedicated Dual-Track (Standard Enterprise Model)*
    *   **Kelebihan**: Fokus yang jernih. IC fokus 100% pada riset model, agent runtime, dan arsitektur data. EM fokus pada manusia, alokasi sumber daya komputasi, dan dependensi organisasi.
    *   **Kekurangan**: Membutuhkan headcount lebih besar. Risiko EM kehilangan ketajaman teknis (*technical decay*).
*   *Pilihan B: Hybrid Tech-Lead Manager (TLM / Player-Coach)*
    *   **Kelebihan**: Efisien untuk tim rintisan AI (<6 orang). Keputusan arsitektur model dibuat cepat oleh orang yang mengelola SDM.
    *   **Kekurangan**: *High Context-Switching Tax*. Manajer sering kali menimbun tiket coding terpenting untuk dirinya sendiri, menunda 1-on-1, dan mengabaikan coaching saat terjadi insiden produksi.

#### Strict Quantitative Metric Scoring vs. Holistic Narrative Rubrics
*   *Quantitative Calibration (seperti kode di Seksi 6)*: Mereduksi bias personal, memberikan target konkrit, namun rentan di-hack (*Goodhart’s Law*—misal insinyur menulis puluhan evals sintetis berkualitas rendah demi mengejar target metrik).
*   *Holistic Narrative*: Menilai dampak bisnis holistik, namun sangat rentan terhadap *proximity bias* dan *halo effect*.
*   *Optimal Trade-off*: Gunakan sistem kuantitatif sebagai *baseline filter*, dilanjutkan tinjauan komite (*peer calibration committee*) untuk validasi kualitatif.

---

### 9. Best Practices & Standar Industri

1. **Pemisahan Evaluasi Performa dari Obrolan Kompensasi**:
   Jangan pernah menyatukan sesi *coaching* karir atau review performa dengan negosiasi kenaikan gaji/bonus pada jam yang sama. Hal ini memicu respon bertahan (*defensive mode*) dan merusak keterbukaan kognitif insinyur.
2. **Dokumentasi 1-on-1 Terdistribusi (Shared Living Document)**:
   Gunakan dokumen kolaboratif privat dengan struktur dua arah. Insinyur wajib mengisi agenda 24 jam sebelum pertemuan. Jika agenda kosong, sesi dibatalkan bukan untuk tidak peduli, melainkan dialihkan menjadi sesi observasi kerja (*pair programming / architecture whiteboarding*).
3. **Pemberian Compute Budget Otonom untuk Pembelajaran**:
   Sediakan kuota komputasi (misal: $500/bulan GPU credits) untuk insinyur L4/L5 bereksperimen dengan model baru di luar backlog tiket sprint untuk memicu pertumbuhan kompetensi organik.
4. **Calibration Committee Protocol**:
   Evaluasi kenaikan level wajib ditinjau oleh komite manajer lintas divisi untuk menstandarkan arti "Staff" atau "Principal" di seluruh departemen AI dan memastikan tidak ada inflasi level (*title inflation*).

---

### 10. Hands-on Lab Exercise (Langkah demi Langkah)

#### Skenario Studi Kasus:
Anda adalah Engineering Manager baru di platform FinTech AI. Anda mengelola **Budi (L5 Senior Agent Engineer)**. Selama 6 minggu terakhir:
* Budi ditugaskan merancang Autonomous Reconciliation Agent untuk mendeteksi transaksi anomali.
* Budi terjebak dalam *loop* akurasi: ia terus berganti model fondasi dan meracik prompt tanpa membangun *automated evaluation framework*.
* Akurasi agent fluktuatif di 81% (target SLO: 98%).
* Pada 1-on-1 terakhir, Budi berkata: *"Modelnya non-deterministik, tidak ada yang bisa memastikan akurasi 98% pada sistem agentik. Ini bukan salah saya, teknologi LLM-nya memang belum matang. Saya merasa tidak dihargai dan ingin promosi ke Staff Engineer semester ini."*

---

#### Langkah Pengerjaan Lab:

#### Langkah 1: Diagnosis Situasi Menggunakan Situational Leadership
1. Identifikasi tingkat kematangan Budi: Mengapa Budi berada di **D2 (Some Competence, Low Commitment/Frustrated)** pada domain evaluasi agentik, meskipun ia memegang titel Senior Engineer?
2. Petakan akar masalah teknis versus akar masalah emosional (Frustrasi stochastic vs ekspektasi promosi).

#### Langkah 2: Merancang 1-on-1 Coaching Script Menggunakan Metode GROW
Susun transkrip panduan respon coaching Anda sebagai EM:

```markdown
*   **Goal**: "Mari kita tentukan definisi target promosi Staff dan hubungannya dengan reliabilitas sistem rekonsiliasi ini..."
*   **Reality**: "Budi, mari kita telaah data bersama: saat ini kita mengukur akurasi secara ad-hoc tanpa ground-truth dataset yang representatif..."
*   **Options**: "Apa yang terjadi jika alih-alih fine-tuning prompt terus-menerus, kita membagi tugas rekonsiliasi menjadi deterministic rule-filter untuk 80% kasus awal, dan LLM agent hanya untuk 20% edge cases?"
*   **Will**: "Apa artefak sistem evaluasi yang bisa kita sepakati ada di staging sebelum calibration committee meeting minggu depan?"
```

#### Langkah 3: Penilaian Gap Promosi Berdasarkan Matriks
Gunakan sistem kode Python pada Seksi 6 untuk menginput evaluasi Budi:
1. Jalankan skrip dengan menambahkan kriteria evaluasi Budi:
   * `AGENT-L6-01` (Staff Architectural Strategy): Budi diberi nilai 1.5 karena gagal merancang arsitektur fallback dan menyalahkan model pihak ketiga.
   * `EVAL-L6-01` (Enterprise Governance/Evals): Budi diberi nilai 1.0 karena tidak ada data evals ground-truth kuantitatif.
2. Analisis output JSON readiness score dari skrip tersebut.

#### Langkah 4: Deliver Radical Candor Feedback
Tulis feedback terstruktur 3 paragraf untuk dikirimkan ke Budi:
* **Paragraf 1 (Situation & Behavior)**: Soroti fakta objektif—ketiadaan automated benchmark run dan stagnasi deliverable 6 minggu.
* **Paragraf 2 (Impact)**: Dampak keterlambatan terhadap SLA operasional compliance perusahaan dan CapEx token yang membengkak.
* **Paragraf 3 (Path Forward)**: Jalan keluar terukur—penangguhan pengajuan promosi Staff ke siklus berikutnya, diiringi rencana *mentorship* langsung dari Principal Architect untuk membangun *eval-driven development harness*.

---

### Verifikasi Hasil Lab
Lab dianggap selesai jika Anda menghasilkan:
1. Lembar kerja GROW yang mengalihkan fokus Budi dari *blaming the non-deterministic models* menjadi *engineering deterministic guardrails*.
2. Laporan kalkulasi gap kompetensi Budi yang membuktikan secara empiris mengapa ia belum siap dipromosikan ke L6 Staff Engineer.
3. Rencana aksi konkret 30 hari untuk memulihkan *vitality score* Budi dari risiko burnout/defensif menuju eksekusi terfokus.