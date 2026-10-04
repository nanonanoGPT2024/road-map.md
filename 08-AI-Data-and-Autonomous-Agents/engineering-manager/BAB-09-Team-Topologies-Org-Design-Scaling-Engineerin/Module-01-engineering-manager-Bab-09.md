# Bab 09: Team Topologies, Org Design, & Scaling Engineering
## Module 01: Merancang Struktur Organisasi AI-First & Platform Multi-Agent

---

### 1. Learning Objectives
*   **Menganalisis dan Memitigasi Cognitive Load:** Mengukur dan membagi beban kognitif kognitif tim rekayasa (*cognitive load*) pada domain AI, data pipeline, dan autonomous agent lifecycle menggunakan metrik operasional terukur.
*   **Menerapkan 4 Tipe Tim & 3 Pola Interaksi Team Topologies:** Mengonstruksi struktur organisasi berbasis *Stream-Aligned*, *Platform*, *Enabling*, dan *Complicated-Subsystem* yang disesuaikan secara presisi untuk siklus hidup rekayasa LLM dan Multi-Agent Systems (MAS).
*   **Mengeksekusi Inverse Conway Maneuver:** Mendesain batas-batas tim (*team boundaries*) dan kontrak antartim (*Team APIs*) yang secara deterministik mencerminkan arsitektur sistem decoupled agentic enterprise.
*   **Menghilangkan Bottleneck Data & LLMOps:** Mengonversi peran *Data Scientist* dan *ML Engineer* dari struktur silo fungsional (*centralized pool*) menjadi pola kolaboratif berbasis platform swasembada (*self-service platform*).
*   **Membangun Metrik Skalabilitas Organisasi:** Mengimplementasikan dashboard analitik organisasi untuk melacak *Team Cognitive Load Index* (TCLI) dan friksi lintas tim dalam delivery fitur agentic.

---

### 2. Concept Overview
Skalabilitas rekayasa pada domain *Artificial Intelligence*, *Data Engineering*, dan *Autonomous Agents* sering kali gagal bukan karena keterbatasan algoritma, melainkan akibat kegagalan struktural organisasi. Konsep inti dari modul ini berakar pada tiga hukum fundamental:

```
[Conway's Law]
"Organisasi yang mendesain sistem akan menghasilkan desain 
yang menduplikasi struktur komunikasi dari organisasi tersebut."

                    ⬇ Dimanipulasi Melalui

[Inverse Conway Maneuver]
Mendesain struktur tim terlebih dahulu untuk secara sengaja mendorong 
evolusi arsitektur software/agent yang modular dan decoupled.

                    ⬇ Dibatasi Oleh

[Dunbar's Number & Cognitive Load Theory]
Kapasitas mental tim terbatas. Arsitektur organisasi harus membatasi 
beban extraneous agar fokus pada intrinsic dan germane value delivery.
```

#### Komponen Fundamental Team Topologies untuk AI & Agentic Systems:
1.  **Stream-Aligned Team (SAT):** Tim lintas-disiplin yang bertanggung jawab end-to-end pada satu aliran nilai bisnis (misal: *Fraud Detection Agent Squad*, *Customer Support Autonomous Copilot*). Mereka memiliki kepemilikan penuh dari prompt engineering, orchestrator logic, hingga monitoring produksi.
2.  **Platform Team (PT):** Menyediakan *Thinnest Viable Platform* (TVP) yang mengabstraksi kompleksitas komputasi GPU, vector database provisioning, LLM inference gateway, evaluasi otomatis, dan guardrails sebagai *X-as-a-Service*.
3.  **Complicated-Subsystem Team (CST):** Tim spesialis matematika/algoritma tingkat tinggi yang hanya dibentuk jika beban kognitif subsistem melampaui kemampuan tim stream-aligned (misal: *Distributed Custom Quantization Engine*, *Proprietary Embedding Model Pre-training*).
4.  **Enabling Team (ET):** Tim konsultan internal yang terdiri dari pakar AI Safety, Model Governance, dan Distributed Systems yang menyebarkan kapabilitas baru ke SAT tanpa mengambil alih kepemilikan kode.

---

### 3. Why It Matters
Dalam arsitektur agentik modern, batasan sistem menjadi sangat dinamis. Ketika enterprise beralih dari model monolithic software ke sistem multi-agent otonom (di mana agen berinteraksi melalui Tool Calling, A2A protocols, dan dynamic context injection), arsitektur tim tradisional (misalnya: Tim QA terpisah, Tim Data terpisah, Tim Backend terpisah) menyebabkan:

*   **Hand-off Hell:** Model dilempar dari Data Science (Jupyter Notebook) ke Data Engineering (Airflow) lalu ke Backend Engineering (FastAPI) dan terakhir ke DevOps (Kubernetes). Time-to-Market (TTM) anjlok hingga hitungan bulan.
*   **Cognitive Saturation:** Tim produk dipaksa memahami seluk-beluk CUDA drivers, Triton Inference Server, context length optimization, RAG chunking, sekaligus logic bisnis perbankan. Hasilnya adalah *developer burnout* dan insiden produksi tinggi.
*   **Arsitektur Monolitik Agentik (Spaghetti Agents):** Tanpa batasan tim yang jelas, agen otonom dibangun dengan ketergantungan melingkar (*circular dependencies*), di mana satu kegagalan tool pada SAT A merusak memori context pada agen milik SAT B.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan pemetaan struktural organisasi (*Org Topology*) langsung ke arsitektur software (*System Topology*) melalui pendekatan *Inverse Conway Maneuver*.

```
+---------------------------------------------------------------------------------------+
| ORGANIZATIONAL TOPOLOGY                                                               |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   +--------------------------+                 +--------------------------+           |
|   | Stream-Aligned Team A    |                 | Stream-Aligned Team B    |           |
|   | (Customer Support Agent) |                 | (Fraud Triage Agent)     |           |
|   +------------+-------------+                 +------------+-------------+           |
|                |                                            |                         |
|  Facilitating  |               +-----------------------+    | Facilitating            |
|                +-------------> | Enabling Team         | <--+                         |
|                                | (AI Safety & Eval)    |                              |
|                                +-----------------------+                              |
|                                                                                       |
|   Interaction: X-as-a-Service                   Interaction: X-as-a-Service           |
|                |                                            |                         |
|                v                                            v                         |
|   +-----------------------------------------------------------------------+           |
|   | Complicated-Subsystem Team (Core Inference & Model Quantization)     |           |
|   +-----------------------------------+-----------------------------------+           |
|                                       | Consumes Underlying Compute                   |
|                                       v                                               |
|   +-----------------------------------------------------------------------+           |
|   | Platform Team (LLMOps, Vector Store, Agent Execution Fabric)          |           |
|   +-----------------------------------------------------------------------+           |
|                                                                                       |
+---------------------------------------------------------------------------------------+
                                        ||
                  MENCERMINKAN SECARA PRESISI KE ARSITEKTUR
                                        \/
+---------------------------------------------------------------------------------------+
| SYSTEM ARCHITECTURE (AUTONOMOUS MULTI-AGENT SYSTEM)                                  |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|   +--------------------------+                 +--------------------------+           |
|   | CS Agent Microservice    |                 | Fraud Agent Microservice |           |
|   | (Stateful Context/Tools) |                 | (Graph/Deterministic RT) |           |
|   +------------+-------------+                 +------------+-------------+           |
|                |                                            |                         |
|                +--------------------+ +---------------------+                         |
|                                     | |                                               |
|                                     v v                                               |
|                     +---------------------------------+                               |
|                     | Semantic Gateway / API Router   |                               |
|                     +----------------+----------------+                               |
|                                      |                                                |
|                                      v                                                |
|                     +---------------------------------+                               |
|                     | Low-Latency vLLM / TensorRT-LLM |                               |
|                     | Subsystem Engine                |                               |
|                     +----------------+----------------+                               |
|                                      |                                                |
|                                      v                                                |
|   +-----------------------------------------------------------------------+           |
|   | Self-Service Platform APIs:                                           |           |
|   | - Guardrails & Red Teaming Proxy    - Managed Vector DB (Qdrant/Milvus)|           |
|   | - Context Memory Hub                - Distributed Tracing (OpenTelemetry)        |
|   +-----------------------------------------------------------------------+           |
+---------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Dekonstruksi Cognitive Load dalam Rekayasa AI
Cognitive Load ($L$) sebuah tim terbagi menjadi tiga kategori:
$$L_{total} = L_{intrinsic} + L_{extraneous} + L_{germane}$$

1.  **Intrinsic Load:** Kompleksitas dasar dari domain masalah (misal: "Bagaimana cara mendeteksi anomali pada transaksi perbankan dengan reasoning multi-step?").
2.  **Extraneous Load:** Beban teknis administratif yang tidak memberikan nilai bisnis langsung (misal: "Bagaimana cara deploy Kubernetes operator untuk memanipulasi GPU slicing (MIG)?").
3.  **Germane Load:** Kapasitas mental yang dialokasikan untuk pemecahan masalah bernilai tinggi dan penciptaan inovasi (misal: "Bagaimana merancang *tool-calling chain* yang meminimalisir token hallucination?").

*Strategi Organisasi:* **Platform Team** menyerap $L_{extraneous}$ secara maksimal, menjaga $L_{intrinsic}$ dalam batas kendali, sehingga SAT memiliki ruang mental penuh untuk $L_{germane}$.

#### B. Pola Interaksi (Interaction Modes) Dinamis
Interaksi antartim tidak boleh bersifat permanen, melainkan berorientasi status:
*   **Collaboration:** Dua tim bekerja bersama untuk tujuan eksplorasi batas API baru (misal: SAT A dan Platform Team berkolaborasi selama 2 sprint untuk merancang spesifikasi *Agent Memory Store*).
*   **X-as-a-Service:** Konsumsi artefak via antarmuka stabil dengan dependensi minimum (misal: SAT A mengonsumsi Inference Gateway via REST/gRPC dengan jaminan latency p99 < 150ms).
*   **Facilitating:** Enabling team mendampingi SAT untuk meningkatkan kapabilitas tertentu (misal: AI Safety Team mengajarkan SAT cara melakukan automated fuzz testing untuk prompt injection) selama periode terbatas.

#### C. Formalisasi Team API
Setiap tim di dalam organisasi wajib mendefinisikan "Team API", dokumen operasional hidup yang mendefinisikan antarmuka manusia dan sistem:
*   Komponen artefak yang dimiliki (*services, models, datasets*).
*   Metrik SLA/SLO teknis dan response time komunikasi.
*   Interaction modes yang sedang aktif dengan tim lain.
*   Jalur eskalasi dan roadmap dependensi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python production-grade untuk sistem tata kelola organisasi: **OrgHealth & Team Cognitive Load Monitoring Engine**. Skrip ini memodelkan topologi tim, mengumpulkan metrik operasional (tiket, repositori, dependensi arsitektur), menghitung *Team Cognitive Load Index* (TCLI), dan mengevaluasi pelanggaran Inverse Conway Maneuver.

```python
"""
OrgHealth: Engine Pemantau Team Topologies & Cognitive Load untuk AI Engineering.
Menghitung TCLI dan mendeteksi anti-pattern struktural Conway's Law.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import logging
import math

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OrgHealthEngine")


class TeamType(str, Enum):
    STREAM_ALIGNED = "STREAM_ALIGNED"
    PLATFORM = "PLATFORM"
    ENABLING = "ENABLING"
    COMPLICATED_SUBSYSTEM = "COMPLICATED_SUBSYSTEM"


class InteractionMode(str, Enum):
    COLLABORATION = "COLLABORATION"
    X_AS_A_SERVICE = "X_AS_A_SERVICE"
    FACILITATING = "FACILITATING"


@dataclass(frozen=True)
class ServiceBoundary:
    service_id: str
    name: str
    is_core_business_logic: bool
    requires_gpu_ops: bool
    lines_of_code: int
    direct_dependencies: Set[str] = field(default_factory=set)


@dataclass
class TeamAPI:
    team_name: str
    team_type: TeamType
    owned_services: List[ServiceBoundary]
    active_interactions: Dict[str, InteractionMode]  # TargetTeam -> Mode
    max_cognitive_capacity: float = 100.0
    active_incidents_last_month: int = 0
    external_ticket_interruptions_week: int = 0


class CognitiveLoadEvaluator:
    """
    Menghitung beban kognitif berbasis kompleksitas kode, interupsi operasional,
    dan ketidaksesuaian tanggung jawab (domain mismatch).
    """

    @staticmethod
    def calculate_tcli(team: TeamAPI) -> float:
        """
        Menghitung Team Cognitive Load Index (TCLI).
        Skor > 85 mengindikasikan tim berada di ambang burnout/failure mode.
        """
        extraneous_score = 0.0
        intrinsic_score = 0.0

        for svc in team.owned_services:
            # Penalti kompleksitas dasar
            loc_factor = math.log10(max(svc.lines_of_code, 1)) * 5.0
            dep_factor = len(svc.direct_dependencies) * 4.0
            intrinsic_score += loc_factor + dep_factor

            # Pelanggaran Domain: Stream team mengelola GPU ops secara mandiri
            if team.team_type == TeamType.STREAM_ALIGNED and svc.requires_gpu_ops:
                extraneous_score += 25.0  # Beban extraneous berat

        # Penalti friksi komunikasi
        interruption_factor = team.external_ticket_interruptions_week * 1.5
        incident_factor = team.active_incidents_last_month * 3.0

        # Kolaborasi yang berlebihan membebani kognisi
        collab_count = sum(
            1 for mode in team.active_interactions.values() 
            if mode == InteractionMode.COLLABORATION
        )
        collab_penalty = collab_count * 10.0

        total_load = intrinsic_score + extraneous_score + interruption_factor + incident_factor + collab_penalty
        return round(min(total_load, 150.0), 2)


class ConwayGovernanceAuditor:
    """
    Memvalidasi apakah struktur organisasi selaras dengan prinsip
    decoupled multi-agent engineering.
    """

    def __init__(self, teams: Dict[str, TeamAPI]):
        self.teams = teams

    def audit_topologies(self) -> List[str]:
        violations = []

        for name, team in self.teams.items():
            tcli = CognitiveLoadEvaluator.calculate_tcli(team)
            if tcli > team.max_cognitive_capacity:
                violations.append(
                    f"[COGNITIVE_OVERFLOW] Tim '{name}' memiliki TCLI {tcli} "
                    f"melebihi kapasitas batas {team.max_cognitive_capacity}."
                )

            # Validasi Boundary: Deteksi Platform Tim yang memegang Business Logic
            if team.team_type == TeamType.PLATFORM:
                for svc in team.owned_services:
                    if svc.is_core_business_logic:
                        violations.append(
                            f"[CONWAY_LEAK] Platform Tim '{name}' memiliki service domain "
                            f"bisnis '{svc.name}'. Harus diserahkan ke Stream-Aligned Team."
                        )

            # Validasi Anti-pattern: Stream-Aligned bergantung pada sesama Stream-Aligned via Collaboration
            if team.team_type == TeamType.STREAM_ALIGNED:
                for target_team, mode in team.active_interactions.items():
                    if target_team in self.teams:
                        target_type = self.teams[target_team].team_type
                        if target_type == TeamType.STREAM_ALIGNED and mode == InteractionMode.COLLABORATION:
                            violations.append(
                                f"[TIGHT_COUPLING] Tim '{name}' berkolaborasi ketat dengan "
                                f"tim '{target_team}'. Seharusnya decoupled via Platform API / X-as-a-Service."
                            )

        return violations


# =====================================================================
# Eksekusi Simulasi & Validasi Org Architecture
# =====================================================================
if __name__ == "__main__":
    logger.info("Memulai Audit Struktur Organisasi AI Engineering...")

    # Services
    srv_gateway = ServiceBoundary("svc-01", "LLM Inference Gateway", False, True, 4500, set())
    srv_cs_agent = ServiceBoundary("svc-02", "CS Reasoning Agent", True, False, 12000, {"svc-01"})
    srv_fraud_agent = ServiceBoundary("svc-03", "Fraud Agent Core", True, True, 18000, {"svc-01"})

    # Topology Tim
    platform_team = TeamAPI(
        team_name="AI-Platform-Engineers",
        team_type=TeamType.PLATFORM,
        owned_services=[srv_gateway],
        active_interactions={"CS-Squad": InteractionMode.X_AS_A_SERVICE},
        external_ticket_interruptions_week=8,
        active_incidents_last_month=1
    )

    cs_stream_team = TeamAPI(
        team_name="CS-Squad",
        team_type=TeamType.STREAM_ALIGNED,
        owned_services=[srv_cs_agent],
        active_interactions={"Fraud-Squad": InteractionMode.COLLABORATION},  # Coupling mencurigakan
        external_ticket_interruptions_week=15,
        active_incidents_last_month=2
    )

    fraud_stream_team = TeamAPI(
        team_name="Fraud-Squad",
        team_type=TeamType.STREAM_ALIGNED,
        owned_services=[srv_fraud_agent],  # Pelanggaran: Mengelola GPU ops sendiri
        active_interactions={"AI-Platform-Engineers": InteractionMode.X_AS_A_SERVICE},
        external_ticket_interruptions_week=25,
        active_incidents_last_month=6
    )

    org_matrix = {
        platform_team.team_name: platform_team,
        cs_stream_team.team_name: cs_stream_team,
        fraud_stream_team.team_name: fraud_stream_team,
    }

    # Jalankan Evaluasi
    for t_name, t_api in org_matrix.items():
        score = CognitiveLoadEvaluator.calculate_tcli(t_api)
        logger.info(f"Team: {t_name.ljust(22)} | Calculated TCLI: {score}")

    auditor = ConwayGovernanceAuditor(org_matrix)
    detected_violations = auditor.audit_topologies()

    print("\n--- HASIL AUDIT TOPOLOGI REKAYASA ---")
    if detected_violations:
        for err in detected_violations:
            print(f"[TEMUAN] {err}")
    else:
        print("[SUKSES] Seluruh batasan tim selaras dengan Inverse Conway Maneuver.")
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Anti-Pattern | Gejala Klinis di Engineering | Akar Masalah Arsitektur | Tindakan Remediasi Engineering Manager |
| :--- | :--- | :--- | :--- |
| **Shadow Platforming** | Tim Stream-Aligned membuat cluster Kubernetes & pipeline vLLM sendiri secara diam-diam. | Platform Team terlalu kaku (*gatekeeping*), SLA penyediaan lambat, atau TVP tidak memadai. | Restrukturisasi antarmuka Platform Team; ubah SLA menjadi berbasis product-minded self-service APIs. |
| **The "Ivory Tower" Subsystem Team** | CST menghasilkan model custom quantized canggih, namun SAT menolak memakainya karena API rapuh. | Tidak adanya mode kolaborasi awal saat standardisasi kontrak interface antar tim. | Geser status CST ke mode *Collaboration* selama 2 siklus rilis untuk menyerap kebutuhan SAT secara konkret. |
| **Eternal Collaboration Mode** | Dua tim SAT terus-menerus sync mingguan tanpa pernah mencapai decoupling kode. | Batasan konteks domain agen tumpang tindih (*ambiguous domain bounded contexts*). | Pisahkan domain bounded context menggunakan Domain-Driven Design (DDD). Ubah mode menjadi *X-as-a-Service*. |
| **The Platform Sinks into Ops Hell** | Platform Team kewalahan menangani tiket bantuan prompt formatting dan runtime bug milik SAT. | Hilangnya peran Enabling Team; Platform Team diperlakukan sebagai helpdesk L1. | Bentuk temporary *Enabling Team (AI Champions)* untuk menyerap pertanyaan edukasi dan standardisasi panduan. |

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan desain organisasi membawa konsekuensi operasional langsung. Berikut adalah komparasi trade-off arsitektural:

```
MODEL SENTRALISASI                 TEAM TOPOLOGIES HYBRID              EMBEDDED DS / SILO
(Center of Excellence)            (Stream + Platform + Enabling)       (Full Decentralization)
      [Low TTM]                             [Optimal]                           [High Cost]
         |                                      |                                    |
+--------v-----------------------------+--------v---------------------------+--------v-----------------------------+
| * Konsistensi model sangat tinggi.  | * Alokasi cognitive load optimal.  | * Otonomi SAT mendekati 100%.       |
| * Token spend terkontrol ketat.      | * Self-service tools via TVP.      | * Kecepatan fitur lokal maksimal.   |
| * TTM fitur produk sangat lambat.    | * Butuh kematangan operasional     | * Redundansi platform masif (biaya  |
| * Terisolasi dari kebutuhan riil SAT.|   untuk mendefinisikan Team APIs.  |   infrastruktur GPU membengkak 4x). |
| * Bottleneck antrean rilis.          | * Investasi awal platform tinggi.  | * Standar safety & eval berantakan. |
+--------------------------------------+------------------------------------+-------------------------------------+
```

*Kapan memilih alternatif?*
Gunakan **Centralized CoE** hanya jika tim AI Anda berukuran di bawah 10 engineer dengan produk tunggal. Beralihlah ke **Team Topologies Hybrid** segera setelah headcount melampaui 25 engineer atau produk mengoperasikan lebih dari dua autonomous workflow otonom.

---

### 9. Best Practices & Standard Industri

1.  **Thinnest Viable Platform (TVP):** Platform Team untuk AI tidak boleh mencoba membangun "All-in-one AI Studio" kustom sejak hari pertama. Gunakan solusi open-source matang yang dibungkus tipis oleh CLI/API internal (misal: vLLM + LiteLLM Gateway + Langfuse Tracing).
2.  **Explicit Team API Contracts:** Dokumentasikan Team API dalam format repository `README.md` pada setiap service, mencakup:
    *   *Direct on-call Slack channel.*
    *   *Supported model versions & deprecation cycle.*
    *   *Token cost chargeback policy.*
3.  **Cross-Disciplinary Pod Composition (SAT):** Pastikan satu tim Stream-Aligned AI memiliki rasio:
    *   $1$ Product Owner / AI Product Manager.
    *   $1$ Senior ML/Prompt Engineer.
    *   $3$ Backend/Fullstack Engineers.
    *   $1$ Shared Reliability/Data Ops Engineer.
4.  **Guardrail-as-Code:** Penegakan keamanan agentic (AI Safety, PII Redaction) diimplementasikan sebagai *Platform Gateway Interceptor*, bukan diserahkan ke masing-masing developer aplikasi untuk meminimalisir deviasi implementasi.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Enterprise FinTech "NusantaraPay" memiliki 45 engineer yang mengalami delivery gridlock. Tim Fraud Detection, Credit Scoring, dan Customer Support masing-masing membangun sistem LLM mereka sendiri-sendiri. Biaya inferensi GPU membengkak tak terkontrol, sementara latensi p99 CS Agent mencapai 8 detik akibat arsitektur monolitik yang saling menunggu dependensi.

#### Instruksi Penugasan:
1.  **Fase 1: Cognitive Audit (30 Menit)**
    *   Identifikasi komponen dalam arsitektur NusantaraPay saat ini.
    *   Gunakan skrip Python pada Bagian 6 untuk memetakan batasan servis dan menghitung TCLI masing-masing divisi.
2.  **Fase 2: Redefinisi Batasan Tim (Inverse Conway Maneuver) (45 Menit)**
    *   Rancang ulang struktur menjadi 4 tipe tim:
        *   Tentukan ruang lingkup **LLMOps Platform Team** (komponen mana yang diambil alih).
        *   Bentuk **AI Safety & Alignment Enabling Team**.
        *   Bentuk **Stream-Aligned Squads** (CS, Fraud, Credit Scoring).
3.  **Fase 3: Penyusunan Team API RFC (45 Menit)**
    *   Tulis dokumen spesifikasi *Team API* antara *LLMOps Platform Team* dan *Customer Support Stream-Aligned Team*.
    *   Wajib mencakup: Definisi Interface gRPC, SLA inferensi (< 200ms), Error Code standard, dan Dynamic Routing fallback ketika GPU provider mengalami downtime.

#### Verifikasi Hasil Akhir:
Lab dinyatakan berhasil jika skor TCLI seluruh tim berada di bawah nilai $70.0$, tidak ada dependensi silang melingkar antar SAT pada diagram topologi, dan Team API RFC telah tervalidasi siap diterapkan tanpa memerlukan pertemuan sinkronisasi harian antar tim.