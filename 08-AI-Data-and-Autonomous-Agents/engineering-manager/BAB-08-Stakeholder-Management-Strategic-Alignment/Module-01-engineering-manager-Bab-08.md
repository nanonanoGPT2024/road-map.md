# Bab 08: Stakeholder Management & Strategic Alignment
## Modul 01: Strategic Value Translation, FinOps Governance, & Expectation Engineering dalam AI/Agentic Systems

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, seorang Engineering Manager (EM) di domain *AI, Data, and Autonomous Agents* diharapkan mampu:

1. **Menerjemahkan Metrik Stokastik ke Nilai Bisnis Deterministik**: Mengonversi metrik teknis AI (*perplexity*, *tool call precision*, *hallucination rate*, *p99 latency*) menjadi metrik finansial dan operasional (*Cost per Successful Resolution*, *Human-Equivalent Amortization*, *Gross Margin Impact*).
2. **Merancang FinOps & Telemetry Guardrails untuk Agen Otonom**: Mengembangkan arsitektur kontrol berbasis ambang batas dinamis (*dynamic circuit breakers*) untuk membatasi *token burn rate* dan mencegah *infinite reasoning loops*.
3. **Membangun Kerangka Komunikasi Lintas Pemangku Kepentingan (C-Suite, Legal, Product)**: Mengelola *expectation mismatch* terkait sifat non-deterministik sistem agen menggunakan *Bounded Nondeterminism Service Level Objectives (SLOs)*.
4. **Mengimplementasikan Automated Executive Telemetry Engine**: Menulis kode produksi berbasis Python untuk mengagregasi data *runtime* agen otonom, mengevaluasi deviasi ROI, dan mengotomatisasi intervensi sistem sebelum melanggar batas toleransi anggaran bisnis.

---

### 2. Concept Overview (Mental Model & Teori Inti)

#### Mental Model: The Stochastic-Deterministic Impedance Mismatch
Perangkat lunak tradisional bersifat deterministik: Input $A$ dengan logika program $P$ secara konsisten menghasilkan output $B$ ($P(A) \to B$). Eksekutif bisnis dan pemangku kepentingan finansial terbiasa mengalokasikan modal berdasarkan premis ini. 

Sebaliknya, sistem berbasis Large Language Models (LLM) dan Agen Otonom beroperasi di bawah distribusi probabilitas statistik ($P(B \mid A, \theta)$). Hasil eksekusi tidak dapat dijamin 100% seragam.

```
Tradisional (Deterministik):
[Input: A] ---> [Deterministic Code] ---> [Output: B (Reliability: 100%)]
ROI Model: Prediktif, biaya komputasi linier terhadap volume transaksi.

Agen Otonom (Stokastik):
[Input: A] ---> [Reasoning Loop + Memory + Tools] ---> [Output: B (P(Success) < 1.0)]
ROI Model: Probabilistik, biaya komputasi non-linier (multi-hop tool calls, variable token burn).
```

Tugas utama Engineering Manager adalah bertindak sebagai **Impedance Transformer**: mengubah ketidakpastian stokastik sistem kecerdasan buatan menjadi kepastian batas risiko (*bounded risk*) dan nilai ekonomi terukur bagi para pemangku kepentingan.

#### The Agent Strategic Trilemma
Dalam mengelola sistem otonom pada skala *enterprise*, EM harus menyeimbangkan tiga variabel yang saling berkompetisi:

1. **Autonomy Degree (Tingkat Otonomi)**: Kedalaman wewenang agen untuk mengeksekusi *tool calls* berantai tanpa intervensi manusia (*Human-in-the-Loop*).
2. **Cost & Latency Predictability (Prediktabilitas Biaya & Latensi)**: Batasan variabilitas penggunaan token (*FinOps*) dan waktu respons (*SLO p95/p99*).
3. **Outcome Safety & Compliance (Keamanan & Kepatuhan Hasil)**: Jaminan kepatuhan terhadap mitigasi risiko regulasi, privasi data, dan keandalan faktual (*zero hallucination* pada fungsi kritis).

Mengoptimalkan dua variabel secara agresif dipastikan akan mengorbankan variabel ketiga.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Banyak inisiatif *Autonomous Agent* di tingkat enterprise terhenti pada tahap *Proof of Concept (PoC) Purgatory*. Akar permasalahannya jarang berakar pada keterbatasan model, melainkan pada **kegagalan Strategic Alignment dan FinOps**:

* **Unbounded Cost Explosion**: Sebuah agen *Customer Support* otonom berbasis *ReAct (Reasoning + Acting)* mengalami kondisi *infinite query loop* ketika menghadapi basis data pelanggan yang inkonsisten. Agen membakar jutaan token dalam hitungan jam tanpa menyelesaikan masalah pelanggan, memicu intervensi CFO akibat lonjakan tagihan API pihak ketiga.
* **The Trust Cliff**: Tim *Legal & Compliance* mematikan proyek agen analisis kontrak secara mendadak setelah menemukan bahwa model meloloskan klausul berisiko tinggi tanpa *audit trail* deterministik, meskipun akurasi model di atas kertas mencapai 94%.
* **Misaligned SLA vs. Expectation**: Stakeholder produk mengasumsikan waktu respons sub-detik layaknya layanan microservices biasa. Mereka menolak sistem berbasis agen multi-langkah (*multi-agent routing*) yang membutuhkan 12–25 detik untuk memvalidasi konteks dan melakukan *self-reflection*.

Tanpa arsitektur pengukuran dan mekanisme pelaporan terstruktur, Engineering Manager akan selalu berada dalam posisi defensif saat audit performa dan anggaran berlangsung.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan **Strategic Telemetry & Executive Governance Architecture** yang menjembatani sistem agen otonom tingkat rendah dengan dasbor pengambil keputusan eksekutif:

```
+-------------------------------------------------------------------------------+
|                           AGENT RUNTIME LAYER                                 |
|                                                                               |
|  +------------------+     +-------------------+     +---------------------+   |
|  | Context/Planner  | <-> | Tool Registry     | <-> | Model Inference     |   |
|  | (ReAct / Graph)  |     | (APIs, Vector DB) |     | (Local / Hosted LLM)|   |
|  +--------+---------+     +---------+---------+     +----------+----------+   |
+-----------|-------------------------|--------------------------|--------------+
            | OpenTelemetry           | Execution Meta           | Tokens/Latency
            v                         v                          v
+-------------------------------------------------------------------------------+
|                    AGENT OBSERVABILITY & TELEMETRY BUS                        |
|                                                                               |
|  - Traces (Span ID, Agent Step, Tool Name)                                   |
|  - Metrics (Input/Output Tokens, Cache Hit %, Evaluator Quality Score)        |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                    STRATEGIC FINOPS & GOVERNANCE ENGINE                       |
|                                                                               |
|  +--------------------------------+   +------------------------------------+  |
|  | Unit Economics Calculator      |   | Policy Enforcement Engine          |  |
|  | - Cost Per Task (CPT)          |   | - Dynamic Token Ceiling Breaker    |  |
|  | - Human Labor Equivalence (HLE)|   | - Semantic Drift Degradation Alert |  |
|  | - Net Business ROI Metric      |   | - Auto Route to Fallback (Heuristic|  |
|  +---------------+----------------+   +-----------------+------------------+  |
+------------------|--------------------------------------|---------------------+
                   |                                      |
         +---------+                                      +----------+
         v                                                           v
+------------------------------------+             +----------------------------------+
|   EXECUTIVE BUSINESS METRICS BUS   |             | CRITICAL SYSTEM INTERVENTIONS    |
|                                    |             |                                  |
| - CFO: Burn Rate & Margin Impact   |             | - Terminate Stuck Reasoning Loop |
| - CPO: Task Completion Latency     |             | - Down-tier Model (e.g. 70B->8B) |
| - Legal: Audit Trail & Drift Logs  |             | - Force Human-In-The-Loop (HITL) |
+------------------------------------+             +----------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Translasi Unit Economics: Cost Per Task (CPT) vs. Human Labor Equivalence (HLE)
Untuk mempertahankan justifikasi anggaran sistem agen, EM harus mengukur efisiensi sistem melalui metrik *Cost Per Successful Task* ($CPST$):

$$CPST = \frac{\sum_{i=1}^{N} (Tokens_{in} \cdot P_{in} + Tokens_{out} \cdot P_{out} + Compute_{infra})_i}{S}$$

Di mana:
* $N$ = Total percobaan eksekusi agen (berhasil + gagal).
* $P_{in}, P_{out}$ = Harga per token (input/output).
* $Compute_{infra}$ = Biaya amortisasi inferensi lokal/infrastruktur pendukung (vektor database, *network egress*).
* $S$ = Jumlah tugas yang tervalidasi sukses secara objektif melalui *evaluator/ground-truth checks*.

Nilai ekonomi bersih (*Net ROI*) per hari dihitung terhadap biaya tenaga kerja manusia (*Human Labor Cost* - $HLC$):

$$Net\ ROI = (S \times HLC) - Total\ Operational\ Spend$$

Jika rasio $S/N$ (Tingkat Keberhasilan Objektif) menurun, biaya $CPST$ melonjak drastis. Penurunan akurasi sekecil 5% dapat membalikkan efisiensi margin menjadi defisit finansial akibat pemborosan token pada tugas yang gagal.

#### B. Expectation Engineering melalui Bounded Nondeterminism SLOs
Alih-alih menyepakati SLA deterministik (*contoh: "Sistem memberikan respons yang 100% akurat dalam waktu kurang dari 2 detik"*), EM menyusun **Stochastic Service Level Agreements**:

1. **Target Keberhasilan Bersyarat (*Conditional Success Rate*)**:
   Agen otonom dijamin menyelesaikan $\ge 92\%$ tugas dalam domain yang terdefinisi pada interval kepercayaan 95% (*95% Confidence Interval*), diukur dengan evaluator sintetis deterministik atau *Human-in-the-Loop review*.
2. **Dynamic Step Ceiling**:
   Agen dibatasi maksimal melakukan $K$ langkah penalaran (*tool execution steps*). Jika $K$ tercapai tanpa konvergensi jawaban, sistem mengeksekusi *fallback* deterministik (mengalihkan tugas ke operator manusia atau aturan statis).
3. **P95 Latency Tiers**:
   Klasifikasi jalur tugas (*Task Routing*):
   * *Fast-Path (SLM/Single-shot)*: Latensi $\le 1.2$ detik.
   * *Complex-Path (Multi-hop Agent with Verification)*: Latensi $\le 15$ detik.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modul Python tingkat produksi untuk **Strategic Governance & FinOps Engine**. Engine ini bertindak sebagai *middleware observer* yang memproses telemetri eksekusi agen, menghitung unit economics real-time, mendeteksi pelanggaran batas toleransi bisnis, dan memicu *circuit breaker* saat biaya atau tingkat kegagalan melampaui batas yang disetujui stakeholder.

```python
"""
strategic_governance_engine.py
Enterprise AI Agent Telemetry and Executive FinOps Governance Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Protocol
import logging
import math

# Konfigurasi Logging Standar Industri
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("StrategicGovernanceEngine")


class SystemAction(str, Enum):
    ALLOW = "ALLOW"
    THROTTLE = "THROTTLE"
    DEGRADE_TIER = "DEGRADE_TIER"
    CIRCUIT_BREAK = "CIRCUIT_BREAK"


@dataclass(frozen=True)
class ExecutionTrace:
    """Representasi telemetri atomik dari satu sesi eksekusi agen otonom."""
    trace_id: str
    task_type: str
    input_tokens: int
    output_tokens: int
    execution_time_seconds: float
    tool_calls_count: int
    is_success: bool
    human_equivalent_cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class StrategicMetricsSummary:
    """Ringkasan eksekutif tingkat tinggi untuk pelaporan CFO/CPO."""
    total_executions: int
    success_rate: float
    total_cost_usd: float
    human_equivalent_value_usd: float
    net_roi_usd: float
    cost_per_successful_task: float
    p95_latency_seconds: float
    active_governance_action: SystemAction


class AlertNotifier(Protocol):
    """Abstraksi interface untuk kanal alerting stakeholder."""
    def send_violation_alert(self, title: str, details: Dict[str, float]) -> None:
        ...


class ConsoleAlertNotifier:
    """Implementasi konkrit alert notifier untuk environment cloud/container."""
    def send_violation_alert(self, title: str, details: Dict[str, float]) -> None:
        logger.critical(
            "GOVERNANCE VIOLATION ALERT: %s | Payload: %s",
            title,
            details
        )


class StrategicAIGovernanceEngine:
    """
    Engine untuk mengagregasi operasional agen, menganalisis unit economics,
    dan memvalidasi runtime terhadap batas toleransi strategis.
    """
    def __init__(
        self,
        cost_per_input_token: float,
        cost_per_output_token: float,
        max_cost_per_successful_task_usd: float,
        min_acceptable_success_rate: float,
        notifier: AlertNotifier,
        window_size: int = 100
    ) -> None:
        if min_acceptable_success_rate <= 0.0 or min_acceptable_success_rate > 1.0:
            raise ValueError("min_acceptable_success_rate harus berada dalam rentang (0.0, 1.0]")
        
        self._cost_per_input_token = cost_per_input_token
        self._cost_per_output_token = cost_per_output_token
        self._max_cpst_threshold = max_cost_per_successful_task_usd
        self._min_success_rate_threshold = min_acceptable_success_rate
        self._notifier = notifier
        self._window_size = window_size
        self._trace_buffer: List[ExecutionTrace] = []

    def record_trace(self, trace: ExecutionTrace) -> None:
        """Merekam telemetri eksekusi ke rolling buffer thread-safe sederhana."""
        if trace.input_tokens < 0 or trace.output_tokens < 0:
            raise ValueError("Jumlah token tidak boleh bernilai negatif.")
        
        self._trace_buffer.append(trace)
        if len(self._trace_buffer) > self._window_size:
            self._trace_buffer.pop(0)

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Menghitung biaya langsung model runtime."""
        return (input_tokens * self._cost_per_input_token) + (output_tokens * self._cost_per_output_token)

    def evaluate_executive_state(self) -> StrategicMetricsSummary:
        """
        Mengevaluasi seluruh metrik operasional, menghitung metrik strategis,
        dan menentukan intervensi governance.
        """
        total_runs = len(self._trace_buffer)
        if total_runs == 0:
            return StrategicMetricsSummary(
                total_executions=0,
                success_rate=0.0,
                total_cost_usd=0.0,
                human_equivalent_value_usd=0.0,
                net_roi_usd=0.0,
                cost_per_successful_task=0.0,
                p95_latency_seconds=0.0,
                active_governance_action=SystemAction.ALLOW
            )

        successes = sum(1 for t in self._trace_buffer if t.is_success)
        success_rate = successes / total_runs

        total_cost = sum(
            self.calculate_cost(t.input_tokens, t.output_tokens) for t in self._trace_buffer
        )
        total_human_value = sum(t.human_equivalent_cost_usd for t in self._trace_buffer if t.is_success)
        net_roi = total_human_value - total_cost

        # Cost Per Successful Task (CPST)
        cpst = (total_cost / successes) if successes > 0 else float("inf")

        # P95 Latency Calculation
        latencies = sorted(t.execution_time_seconds for t in self._trace_buffer)
        p95_index = math.ceil(0.95 * total_runs) - 1
        p95_latency = latencies[min(max(p95_index, 0), total_runs - 1)]

        # Governance Policy Enforcement Loop
        action = SystemAction.ALLOW

        # Skenario 1: Biaya melampaui batas maksimal CPST
        if cpst > self._max_cpst_threshold:
            action = SystemAction.DEGRADE_TIER
            self._notifier.send_violation_alert(
                "EXCESSIVE_COST_PER_SUCCESSFUL_TASK",
                {"cpst": cpst, "threshold": self._max_cpst_threshold}
            )

        # Skenario 2: Success rate anjlok di bawah toleransi bisnis
        if success_rate < self._min_success_rate_threshold:
            action = SystemAction.CIRCUIT_BREAK
            self._notifier.send_violation_alert(
                "UNACCEPTABLE_SUCCESS_RATE_COLLAPSE",
                {"success_rate": success_rate, "threshold": self._min_success_rate_threshold}
            )

        return StrategicMetricsSummary(
            total_executions=total_runs,
            success_rate=round(success_rate, 4),
            total_cost_usd=round(total_cost, 4),
            human_equivalent_value_usd=round(total_human_value, 4),
            net_roi_usd=round(net_roi, 4),
            cost_per_successful_task=round(cpst, 4),
            p95_latency_seconds=round(p95_latency, 2),
            active_governance_action=action
        )


# =====================================================================
# Verifikasi Operasional (Production Smoke Test & Simulation)
# =====================================================================
if __name__ == "__main__":
    notifier = ConsoleAlertNotifier()
    
    # Model Pricing Mock: Misal GPT-4o Class ($2.50 / 1M In, $10.00 / 1M Out)
    # Harga diubah ke satuan per-token
    engine = StrategicAIGovernanceEngine(
        cost_per_input_token=2.50 / 1_000_000,
        cost_per_output_token=10.00 / 1_000_000,
        max_cost_per_successful_task_usd=0.08,  # Target: Biaya per penyelesaian tugas < $0.08
        min_acceptable_success_rate=0.85,       # Target: Akurasi minimal 85%
        notifier=notifier,
        window_size=50
    )

    logger.info("Memulai simulasi batch data trace normal...")
    for i in range(40):
        engine.record_trace(
            ExecutionTrace(
                trace_id=f"tr-norm-{i}",
                task_type="refund_processing",
                input_tokens=1500,
                output_tokens=300,
                execution_time_seconds=2.1,
                tool_calls_count=2,
                is_success=True,
                human_equivalent_cost_usd=0.50  # Biaya staf manual untuk tugas ini adalah $0.50
            )
        )

    state = engine.evaluate_executive_state()
    logger.info("Executive State (Normal): %s", state)

    logger.warning("Menyimulasikan anomali: Lonjakan kegagalan dan token loop (hallucination drift)...")
    for i in range(10):
        engine.record_trace(
            ExecutionTrace(
                trace_id=f"tr-fail-{i}",
                task_type="refund_processing",
                input_tokens=12000,  # Token membengkak karena looping context
                output_tokens=2500,
                execution_time_seconds=14.5,
                tool_calls_count=8,
                is_success=False,     # Agen gagal menyelesaikan tugas
                human_equivalent_cost_usd=0.50
            )
        )

    degraded_state = engine.evaluate_executive_state()
    logger.info("Executive State (Post Incident): %s", degraded_state)
```

---

### 7. Edge Cases & Failure Modes

Mengelola sistem otonom mewajibkan kesiapan arsitektur terhadap anomali non-teknis yang berdampak strategis:

| Failure Mode | Mekanisme Terjadinya | Dampak Finansial / Bisnis | Mitigasi Engineering Manager |
| :--- | :--- | :--- | :--- |
| **Reasoning Runaway Loops** | Agen memanggil *tool* dengan argumen salah, menerima *error message*, lalu mencoba lagi tanpa henti (*infinite retry*). | Pembengkakan biaya inferensi hingga ribuan dolar dalam hitungan jam. | Batasi kedalaman iterasi (*Hard Step Limit*, misal: max 5 langkah) + *Circuit Breaker* berbasis *token threshold*. |
| **Silent Semantic Drift** | Penyedia LLM memperbarui bobot model dasar secara senyap (*silent upstream update*), mengubah format keluaran JSON. | *Tool parser* gagal secara tersembunyi, menurunkan tingkat konversi tanpa adanya log `5xx HTTP error`. | Jalankan pipeline evaluasi sintetis harian (*Golden Dataset Canary*) sebelum mengarahkan *traffic* produksi utama. |
| **Data Ingestion Spillover** | Dokumen sensitif internal (PII/Finansial) terindeks ke Vector Database dan dipanggil oleh agen tanpa filter. | Pelanggaran regulasi privasi (GDPR, UU PDP) dan risiko kebocoran data saat audit eksternal. | Pasang *Guardrail Filter* deterministik di layer *Retrieval-Augmented Generation* (RAG) sebelum *context injection*. |
| **Adversarial Goal Hijacking** | Pengguna akhir menyuntikkan instruksi manipulatif (*prompt injection*) via input form bebas. | Agen mengeksekusi operasi destruktif (misal: mengirim email ke seluruh direksi atau menghapus *record*). | Pisahkan hak akses kredensial *read-only* vs *read-write* menggunakan *least-privilege service accounts* untuk setiap agen. |

---

### 8. Trade-offs & Alternatif Solusi

Saat menyelaraskan kebutuhan bisnis dengan arsitektur teknis, seorang Engineering Manager dihadapkan pada pilihan arsitektural fundamental:

```
                  [Tingkat Kepastian / Determinisme]
                                  ^
                                  |
            (A) Heuristic /       |      (B) Fine-Tuned SLM
            Deterministic Rules   |      (Small Language Model)
                                  |
                                  |
                                  |            (C) Frontier Multi-Agent
                                  |            (ReAct + Orchestrator)
  <-------------------------------+--------------------------------->
  [Biaya Inferensi Rendah]                     [Tingkat Otonomi Tinggi]
```

#### Matriks Perbandingan Strategis

| Dimensi Arsitektur | (A) Rule-Based Heuristic | (B) Fine-Tuned SLM (e.g., Llama-3-8B) | (C) Frontier Multi-Agent (GPT-4o / Claude 3.5 Sonnet) |
| :--- | :--- | :--- | :--- |
| **Prediktabilitas Biaya** | Deterministik murni ($0 token cost). | Tinggi (Biaya infrastruktur komputasi tetap / GPU mandiri). | Rendah hingga Sedang (Variabel dinamis berbasis token). |
| **Penanganan Ambiguitas** | Nol (Gagal total di luar spesifikasi aturan). | Terbatas pada data distribusi domain *training*. | Sangat Baik (Mampu bernalar melintasi skenario baru). |
| **Waktu Implementasi** | Cepat untuk skenario sederhana. | Lama (Butuh kurasi data, *training*, dan validasi). | Cepat untuk tahap PoC, menantang pada fase skalabilitas. |
| **Risiko Reputasi** | Sangat Rendah (Logika transparan). | Rendah hingga Sedang (Dapat dibatasi ruang lingkupnya). | Tinggi (Rawan halusinasi kontekstual). |
| **Rekomendasi Manajerial** | Gunakan sebagai lapis *fallback* wajib saat *circuit breaker* aktif. | Pilihan optimal untuk tugas bervolume tinggi dengan format tugas terstruktur. | Gunakan hanya untuk alur kerja non-rutin dengan nilai konversi ekonomi tinggi. |

---

### 9. Best Practices & Standard Industri

Untuk mempertahankan kepercayaan dewan direksi (*Board*) dan regulator, implementasikan standar tata kelola berikut:

* **OpenTelemetry GenAI Semantic Conventions**: Gunakan konvensi standar tracing industri untuk merekam atribut `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`, dan `gen_ai.usage.completion_tokens`. Jangan gunakan metrik kustom ad-hoc.
* **Agent System Dossier (Kesiapan Audit Legal)**: Dokumentasikan setiap agen otonom dalam format *System Dossier*:
  1. Batasan kewenangan agen (*Operational Boundaries*).
  2. Daftar *tools* beserta level akses (*Read/Write/Delete*).
  3. Kriteria eskalasi ke operator manusia (*Human-in-the-Loop Triggers*).
* **Dual-Track Deployment Guardrail**:
  Jangan pernah merilis pembaruan alur penalaran agen langsung ke 100% pengguna. Terapkan strategi *Shadow Deployment*: Jalankan agen baru secara paralel di belakang agen lama atau operator manusia, lalu evaluasi rasio deviasi jawaban selama minimal 72 jam operasional penuh sebelum mengalihkan *traffic*.
* **Dynamic Model Tier Routing**:
  Terapkan router deterministik di *entry point*. Masalah sederhana harus ditangani oleh model kecil yang hemat biaya (*Fast/Cheap tier*), dan hanya dialihkan ke model penalaran tingkat tinggi (*Reasoning tier*) jika skor kompleksitas tugas melampaui batas ambang batas yang ditentukan.

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda adalah Engineering Manager untuk divisi *Fintech Agentic Operations*. Manajemen menuntut pemotongan anggaran operasional agen penilai pinjaman (*Loan Evaluation Agent*) sebesar 30%, sembari mempertahankan tingkat akurasi persetujuan di atas 90%.

#### Tugas Anda:
1. Konfigurasikan lingkungan simulasi untuk menjalankan *benchmark* beban kerja.
2. Terapkan strategi *cost optimization* berbasis *governance engine*: Turunkan tingkat inferensi (*tier degradation*) saat biaya per tugas sukses melampaui ambang batas.
3. Jalankan script evaluasi dan hasilkan laporan eksekutif.

#### Langkah 1: Persiapan Environment
Pastikan Python 3.10+ telah terpasang. Simpan kode dari **Bagian 6** sebagai `strategic_governance_engine.py`. Buat file baru bernama `lab_alignment_runner.py`.

#### Langkah 2: Implementasi Simulasi Lab
Ketik dan jalankan kode berikut di `lab_alignment_runner.py`:

```python
"""
lab_alignment_runner.py
Lab Eksekusi Optimasi FinOps dan Keselarasan Strategis.
"""

from strategic_governance_engine import (
    StrategicAIGovernanceEngine,
    ExecutionTrace,
    ConsoleAlertNotifier,
    SystemAction
)
import random

def run_lab_simulation():
    notifier = ConsoleAlertNotifier()
    
    # Inisialisasi engine dengan constraint bisnis ketat dari CFO
    # Target: Maksimal CPST = $0.05 per approval sukses
    engine = StrategicAIGovernanceEngine(
        cost_per_input_token=3.0 / 1_000_000,
        cost_per_output_token=15.0 / 1_000_000,
        max_cost_per_successful_task_usd=0.05,
        min_acceptable_success_rate=0.90,
        notifier=notifier,
        window_size=100
    )

    print("\n--- Fase 1: Beban Kerja Normal (Baseline) ---")
    for i in range(50):
        engine.record_trace(
            ExecutionTrace(
                trace_id=f"sim-base-{i}",
                task_type="loan_eval",
                input_tokens=random.randint(800, 1200),
                output_tokens=random.randint(150, 300),
                execution_time_seconds=random.uniform(0.8, 1.5),
                tool_calls_count=1,
                is_success=True if random.random() > 0.05 else False, # 95% success
                human_equivalent_cost_usd=0.25
            )
        )
    
    summary_phase1 = engine.evaluate_executive_state()
    print(f"P95 Latency   : {summary_phase1.p95_latency_seconds}s")
    print(f"Success Rate  : {summary_phase1.success_rate * 100}%")
    print(f"Cost per Task : ${summary_phase1.cost_per_successful_task}")
    print(f"Net ROI       : ${summary_phase1.net_roi_usd}")
    print(f"System Action : {summary_phase1.active_governance_action.value}\n")

    print("--- Fase 2: Terjadi Anomali Data Eksternal (Cost Spike) ---")
    for i in range(30):
        # Terjadi tool call yang membengkak karena dokumen eksternal berukuran besar
        engine.record_trace(
            ExecutionTrace(
                trace_id=f"sim-spike-{i}",
                task_type="loan_eval",
                input_tokens=random.randint(8000, 12000), # Lonjakan context
                output_tokens=random.randint(1000, 2000),
                execution_time_seconds=random.uniform(4.0, 9.0),
                tool_calls_count=4,
                is_success=True if random.random() > 0.20 else False, # 80% success
                human_equivalent_cost_usd=0.25
            )
        )

    summary_phase2 = engine.evaluate_executive_state()
    print(f"P95 Latency   : {summary_phase2.p95_latency_seconds}s")
    print(f"Success Rate  : {summary_phase2.success_rate * 100}%")
    print(f"Cost per Task : ${summary_phase2.cost_per_successful_task}")
    print(f"Net ROI       : ${summary_phase2.net_roi_usd}")
    print(f"System Action : {summary_phase2.active_governance_action.value}\n")

    # Evaluasi Hasil
    if summary_phase2.active_governance_action in [SystemAction.DEGRADE_TIER, SystemAction.CIRCUIT_BREAK]:
        print("[SUCCESS] Engine berhasil mendeteksi inefisiensi ekonomi secara otomatis!")
        print("Rekomendasi Tindakan untuk Eksekutif: Turunkan rute model ke SLM terdistilasi atau aktifkan validasi manusia.")
    else:
        print("[FAIL] Engine gagal memitigasi pelanggaran batas biaya bisnis.")

if __name__ == "__main__":
    run_lab_simulation()
```

#### Langkah 3: Verifikasi dan Analisis Hasil
Jalankan file tersebut menggunakan terminal:
```bash
python lab_alignment_runner.py
```

Perhatikan bagaimana status sistem beralih dari `ALLOW` pada Fase 1 menjadi `DEGRADE_TIER` atau `CIRCUIT_BREAK` pada Fase 2. Catatan peringatan otomatis terpicu pada konsol sistem. Data kalkulasi ini dapat langsung dipetakan ke format Markdown atau diekspor ke *Data Warehouse* untuk pelaporan berkala dalam rapat manajemen bersama CFO dan jajaran direksi.