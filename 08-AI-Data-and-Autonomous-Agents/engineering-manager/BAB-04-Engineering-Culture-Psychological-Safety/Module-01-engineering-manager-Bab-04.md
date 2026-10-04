# Bab 04: Engineering Culture & Psychological Safety
## Module 01: Membangun Psychological Safety & Blameless Culture dalam Menghadapi Sistem AI Non-Deterministik dan Insiden Agen Otonom

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, seorang Engineering Manager (EM) di domain AI, Data, dan Autonomous Agents diharapkan mampu:

1. **Mendiagnosis & Mengukur Psychological Safety**: Menghitung *Psychological Safety Index* (PSI) dan tingkat maturitas budaya organisasi berdasarkan skala *Westrum Generative Culture* secara kuantitatif melalui survei berkala dan metrik operasional (misalnya rasio *Near-Miss Reporting*).
2. **Merancang & Memfasilitasi Blameless Post-Mortem untuk Sistem AI**: Memimpin sesi analisis pasca-insiden (RCA) khusus kegagalan stokastik (*non-deterministic failures*, *agentic loop anomalies*, *hallucination-induced data corruption*) tanpa atribusi kesalahan individu, menghasilkan *Action Items* dengan *SLA closure rate* $\ge 90\%$ dalam 14 hari.
3. **Mengintegrasikan "Just Culture" Framework ke dalam AI Governance**: Membedakan secara tegas antara kesalahan sistemik akibat sifat stokastik model LLM/RL versus kelalaian berat (*gross negligence*), mengacu pada standar *NIST AI RMF (Risk Management Framework)* dan prinsip Sidney Dekker.
4. **Membangun Arsitektur Insiden Otomatis untuk Autonomous Agents**: Mengimplementasikan alur pelaporan insiden, *circuit breaker*, dan *evals regression test suite* yang terintegrasi langsung ke pipeline CI/CD guna mencegah trauma psikologis tim akibat *production firefighting*.

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Sifat Unik Kegagalan pada Autonomous Agents vs. Software Tradisional
Pada rekayasa perangkat lunak tradisional (deterministik), fungsi $f(x)$ selalu menghasilkan $y$ yang sama jika status sistem identik. Ketika terjadi *bug*, akar masalah umumnya adalah kesalahan logika kode atau kegagalan infrastruktur. 

Pada sistem **Autonomous Agents & LLM Pipelines**, sistem bersifat **stokastik dan *emergent***:
$$P(Y \mid X, \theta, \tau) \neq 1$$
Di mana respons agen bergantung pada context window ($X$), bobot model ($\theta$), temperature sampling ($\tau$), dan status eksternal tools yang dipanggil secara otonom.

```
Tradisional:  Input [x] ---> [Deterministic Logic] ---> Output [y] (Bug = Human Error/Logic Flaw)
AI/Agents:    Input [x] ---> [Agent Loop: LLM + Tools] ---> Action [a] (Failure = Emergent Behavior)
```

Jika seorang Engineering Manager menerapkan pendekatan *blaming* tradisional ("Siapa yang menulis prompt ini?" atau "Siapa yang mengizinkan tool calling ini?"), para engineer akan merespons dengan:
1. **Defensive Prompting & Over-constraint**: Membatasi kapabilitas agen hingga kehilangan nilai otonominya.
2. **Under-reporting Anomalies**: Menyembunyikan *hallucination* kecil atau kegagalan *tool calling* yang tidak langsung merusak produksi, hingga terakumulasi menjadi *catastrophic failure*.
3. **Deployment Paralysis**: Penurunan drastis pada frekuensi rilis model dan peningkatan *Mean Time to Production* (MTTP).

#### Mental Model: The Just Culture Matrix (Sidney Dekker adapted for AI)

```
                       Tingkat Pembelajaran Organisasi
                                   Tinggi
                                     ▲
                                     │   [LEARNING & INNOVATION ZONE]
                                     │   * Eksperimentasi aman
             [COMFORT ZONE]          │   * Kegagalan stokastik diterima
      * Tidak ada akuntabilitas      │   * Guardrails & Evals kuat
      * Evaluasi model longgar       │   * Psychological Safety Tinggi
                                     │   * Standar Kinerja Tinggi
  ───────────────────────────────────┼───────────────────────────────────► Akuntabilitas
                                     │                                      & Standar
             [APATHY ZONE]           │   [ANXIETY & BLAME ZONE]
      * Fear of failure              │   * Engineer disalahkan atas 
      * Tidak ada inovasi agen       │     output model non-deterministik
      * Saling melempar tanggung     │   * High attrition & burn-out
        jawab data vs ML vs platform │   * Production cover-ups
                                     │
                                   Rendah
```

*Psychological safety* bukanlah "bersikap baik" (*being nice*). Ini adalah keyakinan bersama (*shared belief*) bahwa tim aman untuk mengambil risiko interpersonal (*interpersonal risk-taking*), mengakui anomali model, mematikan agen yang mengalami degradasi performa, dan melaporkan celah keamanan prompt tanpa takut dipermalukan atau dihukum.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

1. **Autonomous Financial/Operational Runaway**:
   Sebuah *Autonomous Customer Support Agent* yang terhubung ke API *refund* mengalami *jailbreak* atau *recursive tool-calling loop*, menerbitkan ribuan *unauthorized refunds* senilai ratusan ribu dolar. Jika tim beroperasi dalam budaya *fear-based*, engineer yang mengetahui inkonsistensi pada evaluasi *system prompt* seminggu sebelumnya akan memilih diam untuk menghindari investigasi personal.
2. **Kepatuhan Regulasi (EU AI Act & NIST AI RMF)**:
   Regulasi modern menuntut adanya transparansi, pelaporan risiko (*incident reporting*), dan *human-in-the-loop auditability*. Budaya yang menyembunyikan anomali stokastik secara langsung melanggar Pasal 73 EU AI Act tentang pelaporan insiden serius, membawa sanksi finansial fatal bagi enterprise.
3. **Talent Attrition pada Spesialis AI/Data**:
   Merekrut AI Research Engineer dan Distributed Systems Architect sangat mahal. Kehilangan talenta kunci akibat stres pasca-insiden (*burnout* akibat pemanggilan on-call atas anomali stokastik yang di luar kendali langsung kode mereka) adalah disrupsi modal manusia yang masif.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur loop tertutup (*closed-loop architecture*) yang mengintegrasikan aspek sosioteknis: sistem telemetri AI Agent, otomatisasi isolasi insiden, dan tata kelola *Blameless Incident Response*:

```
+---------------------------------------------------------------------------------------------------+
| PRODUCTION RUNTIME (AUTONOMOUS AGENT PLATFORM)                                                    |
|                                                                                                   |
|  [User Request] --> [Agent Planner] <---> [Tools / APIs]                                          |
|                            │                                                                      |
|                            ▼                                                                      |
|               [LLM Output / Guardrails]                                                           |
|                            │                                                                      |
|             +--------------┴---------------+                                                      |
|             │ Real-time Telemetry Layer    │                                                      |
|             │ (Token Drift, Loop Detector, │                                                      |
|             │  Toxicity/Jailbreak Sensors) │                                                      |
+-------------+--------------┬---------------+------------------------------------------------------+
                             │ Event Trigger: Anomaly Threshold Breached
                             ▼
+---------------------------------------------------------------------------------------------------+
| INCIDENT GOVERNANCE & PSYCHOLOGICAL SAFETY PLATFORM                                               |
|                                                                                                   |
|  +--------------------+      +--------------------+      +-------------------------------------+  |
|  | Automated Circuit  |      | Anonymous Event    |      | Blameless Timeline Generator        |  |
|  | Breaker / Fallback | ---> | Ingestion & PII    | ---> | * Traces Context & Token History    |  |
|  | (Deterministic API)|      | De-identification  |      | * Excludes Human Blame Attributes   |  |
|  +--------------------+      +--------------------+      +------------------┬------------------+  |
|                                                                             │                     |
+-----------------------------------------------------------------------------┼---------------------+
                                                                              │
                                                                              ▼
+---------------------------------------------------------------------------------------------------+
| SOCIO-TECHNICAL RCA & LEARNING ENGINE                                                             |
|                                                                                                   |
|  +----------------------------------------------------+                                           |
|  | Blameless Post-Mortem Sesi Fasilitasi (EM Led)     |                                           |
|  | - Analisis 5-Whys berpusat pada Sistemik/Guardrail |                                           |
|  | - Menolak narasi "Human Error / Bad Prompt"        |                                           |
|  +-------------------------┬--------------------------+                                           |
|                            │                                                                      |
|                            ▼ Actions Mapped to CI/CD                                              |
|  +----------------------------------------------------+                                           |
|  | Synthetic Regression & Evals Suite Generation      |                                           |
|  | (Inject failed trace as test case into Eval DB)    |                                           |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Redefinisi "Root Cause" pada Sistem AI (Anti-Human Blame)
Dalam rekayasa sistem kompleks (merujuk pada Dr. Richard Cook - *How Complex Systems Fail*), kegagalan tidak pernah disebabkan oleh satu titik kesalahan. Dalam sistem agen otonom:
* **Bukan**: "Engineer X salah menulis regex guardrail."
* **Melainkan**: "Sistem evaluasi CI/CD kita mengizinkan *system prompt* lolos tanpa *adversarial evaluation suite* yang komprehensif, dan *agent loop runtime* kita tidak memiliki mekanisme pembatasan rekursi token/finansial secara deterministik."

#### 5.2 Protokol Blameless Post-Mortem Khusus AI
Saat insiden agen otonom terjadi (misal: agen mengirimkan email massal berisi data konfidensial sintetis), EM harus menegakkan protokol berikut:

1. **Sanitasi Terminologi**:
   * *Dilarang*: "Mengapa engineer lalai memvalidasi context payload?"
   * *Diwajibkan*: "Kondisi apa di lingkungan deployment kita yang membuat data kontekstual yang rentan tidak terdeteksi oleh layer sanitasi sebelum diumpankan ke context LLM?"
2. **Analisis 5-Whys Sistemik Berbasis AI**:
   * *Level 1*: Agen mengeksekusi aksi $A$ yang salah. (Fakta: Agen memilih tool yang salah).
   * *Level 2*: Agen berasumsi context $C$ mengindikasikan instruksi pengguna. (Fakta: Terjadi Prompt Injection terselubung).
   * *Level 3*: Guardrail LLM gagal menandai prompt tersebut. (Fakta: Guardrail model berbasis klasifikasi belum di-*retrain* dengan dataset serangan terbaru).
   * *Level 4*: Dataset eval tidak mencakup permutasi serangan *indirect injection*. (Fakta: Pipeline data eval terisolasi dari log insiden keamanan).
   * *Level 5*: Tidak ada dependensi otomatis antara telemetry insiden dan *eval generation pipeline*. (Sistemik).

#### 5.3 Metrik Kuantitatif Budaya Tim AI
EM wajib memantau kesehatan psikologis dan keandalan sistemik melalui:

$$\text{PSI Score} = \frac{\sum_{i=1}^n S_i}{n} \quad (S_i \in [1, 5] \text{ skala Likert})$$

$$\text{Near-Miss Reporting Ratio (NMRR)} = \frac{\text{Jumlah Insiden Near-Miss yang Dilaporkan Sukarela}}{\text{Total Insiden Produksi Aktual}}$$

Jika $\text{NMRR} < 1.0$, kemungkinan besar terdapat ketakutan di dalam tim: engineer menyembunyikan kegagalan kecil karena takut dipermalukan, menunggu hingga kegagalan tersebut meledak di produksi.

---

### 6. Production-Ready Code Implementation

Berikut adalah sistem penanganan insiden dan generator post-mortem otomatis yang ditulis dengan Python. Sistem ini mencegat kegagalan otonom, mengabstraksi identitas engineer untuk menjaga *blameless environment*, dan mengonversi kegagalan runtime agen menjadi kasus uji evaluasi (*Evals Test Case*) yang dapat direproduksi.

```python
# incident_governance.py
"""
Production-Ready Incident Governance & Blameless RCA Automation Suite for AI Agents.
Designed to capture stochastic agent failures, strip author/committer fingerprints,
and programmatically generate structured Blameless Post-Mortem skeletons and eval regression cases.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("IncidentGovernance")


class SeverityLevel(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"  # Runaway loop, financial/data loss, production downtime
    P1_HIGH = "P1_HIGH"          # Jailbreak bypassed, public hallucination
    P2_MEDIUM = "P2_MEDIUM"      # Tool calling failure without cascading damage
    P3_LOW = "P3_LOW"            # Near-miss anomaly detected by guardrails


class FailureDomain(str, Enum):
    PROMPT_DRIFT = "PROMPT_DRIFT"
    TOOL_EXECUTION_LOOP = "TOOL_EXECUTION_LOOP"
    INDIRECT_INJECTION = "INDIRECT_INJECTION"
    STOCHASTIC_HALLUCINATION = "STOCHASTIC_HALLUCINATION"
    INFRASTRUCTURE_TIMEOUT = "INFRASTRUCTURE_TIMEOUT"


@dataclass(frozen=True)
class AgentExecutionTrace:
    trace_id: str
    session_id: str
    system_prompt_version: str
    raw_user_input: str
    agent_trajectory: List[Dict[str, Any]]
    final_output: str
    metrics: Dict[str, float]  # e.g., {"tokens_used": 15400, "latency_seconds": 12.4}


@dataclass
class IncidentReport:
    incident_id: str
    timestamp_utc: str
    severity: SeverityLevel
    domain: FailureDomain
    anonymized_trace_hash: str
    impact_summary: str
    systemic_factors: List[str] = field(default_factory=list)
    action_items: List[Dict[str, str]] = field(default_factory=list)
    eval_regression_test: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Generates a blameless post-mortem document skeleton."""
        md = f"""# [BLAMELESS POST-MORTEM] Incident Reference: {self.incident_id}
**Date/Time (UTC):** {self.timestamp_utc}
**Severity Level:** {self.severity.value}
**Failure Domain:** {self.domain.value}
**Trace Fingerprint (De-identified):** `{self.anonymized_trace_hash}`

---

## 1. Executive Summary
{self.impact_summary}

## 2. Systemic & Environmental Contributing Factors (No Individual Attribution)
*Catatan: Sesuai prinsip Blameless Culture, investigasi berfokus pada gap arsitektural, ketahanan guardrails, dan cakupan testing.*
"""
        for factor in self.systemic_factors:
            md += f"- {factor}\n"

        md += "\n## 3. Remediation & Action Items (Deterministic Safeguards)\n"
        md += "| Action Item | Category | Target Completion | Verification Method |\n"
        md += "|---|---|---|---|\n"
        for item in self.action_items:
            md += f"| {item.get('action')} | {item.get('category')} | {item.get('due')} | {item.get('verification')} |\n"

        md += f"\n## 4. Generated Regression Eval Definition\n```json\n"
        md += json.dumps(self.eval_regression_test, indent=2)
        md += "\n```\n"
        return md


class BlamelessIncidentProcessor:
    """
    Ingests agent runtime telemetry, obfuscates author credentials,
    and maps execution anomalies to systemic root causes.
    """

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _generate_anonymized_trace_hash(trace: AgentExecutionTrace) -> str:
        """Ensures that no developer/user ID leaks into post-mortem metrics."""
        hasher = hashlib.sha256()
        hasher.update(trace.trace_id.encode("utf-8"))
        hasher.update(trace.system_prompt_version.encode("utf-8"))
        return hasher.hexdigest()[:16]

    def create_incident_from_failure(
        self,
        trace: AgentExecutionTrace,
        severity: SeverityLevel,
        domain: FailureDomain,
        impact: str,
    ) -> IncidentReport:
        """Factory method to generate a post-mortem baseline without blame bias."""
        trace_hash = self._generate_anonymized_trace_hash(trace)
        incident_id = f"INC-{datetime.datetime.utcnow().strftime('%Y%m%d')}-{trace_hash[:6].upper()}"

        # Standard systemic baselines based on domain
        systemic_defaults = self._derive_systemic_factors(domain, trace)
        action_defaults = self._derive_action_items(domain)
        regression_eval = self._extract_eval_payload(trace)

        incident = IncidentReport(
            incident_id=incident_id,
            timestamp_utc=datetime.datetime.utcnow().isoformat(),
            severity=severity,
            domain=domain,
            anonymized_trace_hash=trace_hash,
            impact_summary=impact,
            systemic_factors=systemic_defaults,
            action_items=action_defaults,
            eval_regression_test=regression_eval,
        )

        self._persist_incident(incident)
        return incident

    def _derive_systemic_factors(
        self, domain: FailureDomain, trace: AgentExecutionTrace
    ) -> List[str]:
        factors = []
        if domain == FailureDomain.TOOL_EXECUTION_LOOP:
            factors.append(
                "Mekanisme Circuit Breaker runtime tidak memiliki hard limit untuk recursive tool execution."
            )
            factors.append(
                "Model reasoning tidak memiliki negative reward signal untuk state trajectory yang berulang."
            )
        elif domain == FailureDomain.INDIRECT_INJECTION:
            factors.append(
                "Boundary context window antara system instruction dan retrieved context (RAG) tidak diisolasi secara deterministik."
            )
            factors.append(
                "Output classifier tidak diuji terhadap permutasi zero-day encoding (Base64/ROT13)."
            )
        elif domain == FailureDomain.STOCHASTIC_HALLUCINATION:
            factors.append(
                "Sampling temperature disetel terlalu tinggi untuk task yang membutuhkan factuality absolut."
            )
            factors.append(
                "Evaluation harness pada CI/CD tidak memiliki metric confidence calibration threshold."
            )
        else:
            factors.append("Keterbatasan observabilitas pada state transition agen otonom.")
        return factors

    def _derive_action_items(self, domain: FailureDomain) -> List[Dict[str, str]]:
        actions = []
        if domain == FailureDomain.TOOL_EXECUTION_LOOP:
            actions.append(
                {
                    "action": "Implementasi max_depth limiter (n=5) pada Agent Orchestrator runtime",
                    "category": "Architectural Guardrail",
                    "due": "3 Days",
                    "verification": "Unit test mocking runaway API loop",
                }
            )
        elif domain == FailureDomain.INDIRECT_INJECTION:
            actions.append(
                {
                    "action": "Integrasi NeMo Guardrails / Llama-Guard pada pipeline context injection",
                    "category": "Security Hardening",
                    "due": "5 Days",
                    "verification": "Red-teaming automated benchmark",
                }
            )
        actions.append(
            {
                "action": "Mendaftarkan failure trace ke evaluasi regresi CI/CD",
                "category": "Testing Automation",
                "due": "24 Hours",
                "verification": "CI pass rate verification",
            }
        )
        return actions

    def _extract_eval_payload(self, trace: AgentExecutionTrace) -> Dict[str, Any]:
        """Converts the runtime failure trace into a concrete test scenario for pytest/evals."""
        return {
            "eval_name": f"eval_regression_{trace.trace_id[:8]}",
            "system_version": trace.system_prompt_version,
            "test_input": trace.raw_user_input,
            "forbidden_patterns": [trace.final_output] if trace.final_output else [],
            "max_tolerated_tokens": int(trace.metrics.get("tokens_used", 0) * 0.8),
            "assertion_type": "assert_no_policy_violation",
        }

    def _persist_incident(self, incident: IncidentReport) -> None:
        file_path = self.storage_dir / f"{incident.incident_id}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(incident.to_markdown())
        logger.info("Blameless Incident Report persisted successfully: %s", file_path)


# =====================================================================
# Demonstration & Verification
# =====================================================================
if __name__ == "__main__":
    storage_directory = Path("/tmp/incident_reports")
    processor = BlamelessIncidentProcessor(storage_dir=storage_directory)

    # Simulasi failure trace dari Autonomous Agent yang terjebak dalam runaway tool-calling
    failed_trace = AgentExecutionTrace(
        trace_id="tr-8f92a10b-99c1-4efb",
        session_id="sess-prod-9921",
        system_prompt_version="v2.4.1-agentic-order-mgmt",
        raw_user_input="Batalkan pesanan saya dan kirimkan konfirmasi.",
        agent_trajectory=[
            {"step": 1, "tool": "order_lookup", "status": "success"},
            {"step": 2, "tool": "cancel_order", "status": "error_retrying"},
            {"step": 3, "tool": "cancel_order", "status": "error_retrying"},
            {"step": 4, "tool": "cancel_order", "status": "error_retrying"},
        ],
        final_output="Maaf, terjadi error internal berulang saat membatalkan.",
        metrics={"tokens_used": 18500.0, "latency_seconds": 45.2},
    )

    incident_doc = processor.create_incident_from_failure(
        trace=failed_trace,
        severity=SeverityLevel.P1_HIGH,
        domain=FailureDomain.TOOL_EXECUTION_LOOP,
        impact="Agen mengalami runaway execution loop selama 45 detik, menghabiskan 18k token, dan menyebabkan rate-limiting pada upstream Order Service.",
    )

    print("\n--- GENERATED POST-MORTEM SKELETON (BLAMELESS) ---")
    print(incident_doc.to_markdown())
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Skenario Ekstrem | Dampak pada Sistem & Budaya | Recovery Protocol & Engineering Manager Intervention |
|---|---|---|
| **The "Pseudoblame" Trap** | Engineer secara formal tidak disalahkan, tetapi secara informal dihakimi di Slack/PR review (misal: "Siapa yang mengizinkan prompt buruk ini lolos?"). | EM wajib mengintervensi langsung komunikasi tidak sehat. Mengalihkan diskusi ke: *"Mengapa CI/CD eval suite kita membiarkan prompt ini tembus ke main branch?"* |
| **Silent Failures due to Fear of KPI Drops** | Engineer menutupi degradasi *eval accuracy* minor demi mengejar target rilis sprint. | Metrik evaluasi performa model diotomatisasi secara independen (*continuous evals pipeline*), dipisahkan dari evaluasi personal individu. |
| **Catastrophic External Legal Inquiry** | Pihak audit/regulator menuntut nama individu yang bertanggung jawab atas output halusinasi yang melanggar hukum. | Gunakan doktrin *System Ownership*: EM dan VP Engineering berdiri sebagai tameng hukum tim. Tanggung jawab disematkan pada proses *Governance Approval*, bukan pada individual software engineer. |
| **Over-correction: The Paralysis Mode** | Setelah insiden besar, tim menolak mendeploy agen tanpa kepastian deterministik 100% (yang secara matematis mustahil pada LLM). | EM mendefinisikan *Error Budgets* khusus untuk AI (misal: tingkat halusinasi maksimal 0.5% dari traffic). Selama berada di dalam batas toleransi, rilis tetap berjalan normal. |

---

### 8. Trade-offs & Alternatif Solusi

#### Just Culture vs. Pure Blamelessness vs. Punitive Accountability

```
Pendekatan       Keuntungan                         Kelemahan                      Kesesuaian di Lingkungan AI
─────────────────────────────────────────────────────────────────────────────────────────────────────────────
Punitive         Tampak "tegas" bagi eksekutif      Menghancurkan inovasi; tim     SANGAT BURUK. Membunuh
(Tradisional)    yang mencari kambing hitam.        menyembunyikan failure trace;  eksperimentasi AI dan
                                                    attrition tinggi.              memicu turnover fatal.

Pure Blameless   Menghilangkan rasa takut secara    Bisa disalahgunakan untuk      KURANG TEPAT. Tidak mampu
(Unconditional)  total; pelaporan near-miss         menoleransi sabotase sengaja   menangani pelanggaran etika
                 sangat tinggi.                     atau bypass keamanan kasar.    data / compliance sadar.

Just Culture     Keseimbangan ideal: Membedakan     Memerlukan kedewasaan          OPTIMAL untuk AI & Agents.
(Sidney Dekker)  antara *honest system failure*     manajerial tinggi untuk        Melindungi eksplorasi stokastik
                 dengan *gross negligence*.        menjaga objektivitas garis.    sambil menjaga governance.
```

#### Deterministic Guardrails vs. LLM-as-a-Judge Guardrails
* **Deterministic Guardrails (Regex, Hard Limits, AST Parsing)**: Murah, latensi nol, 100% konsisten, tetapi tidak fleksibel terhadap bahasa alami.
* **LLM-as-a-Judge Guardrails**: Mampu menangkap konteks semantik yang halus, tetapi membawa *probabilistic failure*-nya sendiri (bisa di-*jailbreak* atau mengalami latensi tinggi).
* **Rekomendasi EM**: Terapkan *Defense-in-Depth*. Letakkan *Deterministic Circuit Breaker* di layer runtime terluar (hard cap limit execution budget & iteration depth) untuk memastikan sistem tidak pernah bisa mengalami *infinite loop* terlepas dari output LLM.

---

### 9. Best Practices & Standar Industri

1. **Adopsi Google SRE Postmortem Philosophy untuk AI**:
   * Setiap *Sev-0* atau *Sev-1* wajib memiliki dokumen post-mortem dalam waktu $72$ jam.
   * Setiap *action item* wajib bertipe *PBI (Product Backlog Item)* yang terikat pada perbaikan sistemik (tambah guardrail, integrasi regression test, tuning eval harness), bukan "memberikan edukasi/pelatihan ke engineer".
2. **Westrum Culture Metrics Periodic Assessment**:
   * Lakukan survei anonim setiap kuartal dengan pertanyaan terfokus: *"Jika saya menemukan anomali model di produksi yang dapat membatalkan rilis, saya merasa aman menyatakannya secara publik tanpa khawatir dinilai negatif."*
   * Targetkan rasio Generative Culture di atas $85\%$.
3. **Penerapan NIST AI RMF Playbook (Govern & Manage Functions)**:
   * Mengorganisasi sesi *Pre-Mortem* sebelum agen otonom diberikan akses terhadap external tool APIs (menghubungkan tool write/delete database).
   * Menganalisis skenario terburuk (*worst-case trajectory*) sebagai latihan tim untuk meredakan ketakutan psikologis sebelum agen masuk ke fase produksi.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab:
Tim Anda baru saja merilis *Autonomous Financial Reconciliation Agent*. Agen ini memiliki akses ke API perbankan untuk mengeksekusi *micro-settlement*. Pada jam 03.00 pagi, agen mengalami *stochastic loop* akibat perubahan respons API rekanan: agen mengeksekusi transaksi senilai $\$50$ sebanyak 40 kali ke vendor yang sama sebelum terputus oleh timeout. 

Senior Engineer yang bertanggung jawab atas rilis merasa sangat bersalah, depresi, dan menolak menyentuh modul tersebut lagi karena takut dipecat.

#### Tugas Anda sebagai Engineering Manager:
1. **Langkah 1: Psychological Defusal (1-on-1 Emergency Meeting)**:
   * Rumuskan skrip komunikasi untuk menetralkan trauma emosional engineer.
   * Pisahkan tindakan individu dari kelemahan arsitektur (*missing execution rate-limiter*).
2. **Langkah 2: Facilitate Blameless RCA Workshop (60 Menit)**:
   * Mengumpulkan tim multi-disiplin (Data Scientist, ML Engineer, Backend, Product Manager).
   * Gunakan visual timeline berbasis data event trace (gunakan format output dari Python code di Section 6).
   * Terapkan aturan ketat: Intervensi setiap penggunaan kalimat pasif atau aktif yang menyasar individu.
3. **Langkah 3: Transform Incident to Deterministic Continuous Guardrail**:
   * Ambil trace kegagalan dan ubah menjadi *Automated Regression Eval Test*.
   * Tambahkan *Circuit Breaker Policy* pada layer gateway API yang membatasi eksekusi transaksi per entitas target maksimal $N$ kali per menit secara deterministik.

#### Panduan Solusi Langkah 1 (Skrip EM):
> *"Halo [Nama Engineer], saya memanggil Anda bukan untuk membahas 'kesalahan Anda', melainkan untuk memastikan Anda baik-baik saja. Kejadian tadi malam adalah kegagalan arsitektur perlindungan kita, bukan kegagalan Anda. Jika sebuah sistem bergantung pada kesempurnaan satu engineer agar tidak terjadi runaway transaction, maka sistem kita yang cacat. Mari kita jadikan kegagalan sistemik ini sebagai bahan pembelajaran bersama untuk memperkuat guardrail platform kita hari ini."*

#### Kriteria Keberhasilan Lab:
* Post-Mortem Doc terbit tanpa satupun atribusi nama individu pada bagian *Root Cause Analysis*.
* Dihasilkannya minimal dua *Architectural Guardrails* deterministik (bukan sekadar perbaikan prompt).
* Engineer yang bersangkutan tetap aktif dan memimpin implementasi *regression test harness* yang baru.