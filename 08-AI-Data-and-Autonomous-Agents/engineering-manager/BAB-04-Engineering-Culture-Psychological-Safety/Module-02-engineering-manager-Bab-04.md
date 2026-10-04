# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 04: Engineering Culture & Psychological Safety**  
**Track: Engineering Manager (AI, Data, and Autonomous Agents)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Engineering Manager (EM) dan Technical Leader diharapkan mampu:
- **Merancang dan Mengoperasikan Arsitektur *Blameless Incident Management*:** Mengotomatisasi siklus insiden dari deteksi anomali agen otonom hingga pembuatan draf *post-mortem* tanpa menyalahkan individu.
- **Mengintegrasikan Metrik Keamanan Psikologis ke dalam Telemetri Rekayasa:** Mengombinasikan metrik DORA (Deployment Frequency, Lead Time, MTTR, Change Failure Rate) dan SPACE dengan *telemetri afektif/beban kerja* untuk mendeteksi *burnout* serta ketakutan sistemik sebelum eskalasi ke atrisi tim.
- **Membangun *Architectural Guardrails* untuk Eksperimentasi AI Berisiko Tinggi:** Mengimplementasikan pola arsitektur *Shadow Deployment*, *Canary Releases*, dan *Automated Kill-Switches* yang memberikan jaminan teknis bahwa kegagalan model nondeterministik tidak akan memicu hukuman reputasi maupun kerugian finansial katastropik.
- **Memfasilitasi Kultur Eksperimentasi & Transparansi Model:** Menerapkan protokol pelaporan halusinasi (*Model Drift & Hallucination Disclosure Framework*) yang mendorong engineer membuka celah kegagalan sistem agen secara proaktif.

---

## 2. Prerequisite

Peserta diasumsikan telah menguasai:
- **Fondasi Rekayasa Perangkat Lunak:** Pemahaman mendalam mengenai siklus rilis CI/CD, observabilitas (*metrics, logs, traces* via OpenTelemetry), dan arsitektur *microservices/event-driven*.
- **Domain AI/Data:** Memahami sifat nondeterministik *Large Language Models* (LLM), *autonomous agent loops* (ReAct/Tool-use), dan degradasi data (*data/concept drift*).
- **Fondasi Manajemen Rekayasa:** Penguasaan dasar metrik DORA, matriks RACI, serta dinamika evaluasi performa tim teknis.

---

## 3. Concept & Internal Architecture

Dalam ranah AI dan *Autonomous Agents*, *Psychological Safety* (Keamanan Psikologis) bukanlah sekadar konsep humaniora abstrak; **keamanan psikologis adalah properti arsitektur sistem**.

Sistem agen AI memiliki sifat nondeterministik. Engineer yang bekerja di bawah rasa takut akan melakukan *under-reporting* terhadap anomali model, menolak merilis fitur inovatif berbasis agen, atau menyembunyikan kegagalan evaluasi *prompt injection*. Ketika terjadi insiden produksi, arsitektur organisasi yang menyalahkan individu memicu lingkaran setan penutupan informasi, yang berujung pada kerentanan sistem yang lebih masif.

### Arsitektur "Safety-Engineered Socio-Technical System"

Sistem ini memadukan subsistem teknis (guardrails, observabilitas) dengan subsistem sosial (kebijakan *blameless*, eskalasi adil):

```
+-------------------------------------------------------------------------------------------------+
|                                SOCIO-TECHNICAL SAFETY LAYER                                     |
|                                                                                                 |
|   +-----------------------------------------------------------------------------------------+   |
|   | 1. ORGANIZATIONAL PSYCHOLOGICAL SAFETY PLANE                                            |   |
|   |    - Blameless Culture Policy       - Transparent Incident Retrospectives              |   |
|   |    - Psychological Safety Index     - Burnout Risk Heuristics (PR Review Latency,       |   |
|   |      Telemetry (SPACE + DORA)         Out-of-Hours Pager Escalations)                   |   |
|   +-----------------------------------------------------------------------------------------+   |
|                                                │                                                |
|                                                ▼ Feedback Loops                                 |
|   +-----------------------------------------------------------------------------------------+   |
|   | 2. AUTOMATED INCIDENT & POST-MORTEM PIPELINE                                            |   |
|   |    - PagerDuty/Opsgenie Webhook     - Anonymized Fact Aggregator                        |   |
|   |    - LLM-Assisted Timeline Builder  - Counterfactual Root-Cause Clustering (STAMP Model)|   |
|   +-----------------------------------------------------------------------------------------+   |
|                                                │                                                |
|                                                ▼ Enforces Fail-Safe State                       |
|   +-----------------------------------------------------------------------------------------+   |
|   | 3. ARCHITECTURAL GUARDRAILS & BLAST RADIUS CONTAINMENT                                  |   |
|   |    - Autonomous Agent Policy Engine (Open Policy Agent / Guardrails AI)                 |   |
|   |    - Dynamic Circuit Breakers (Budget, Hallucination Threshold, Latency Spikes)         |   |
|   |    - Shadow / Dark Launch Traffic Routing with Differential Evaluation                  |   |
|   +-----------------------------------------------------------------------------------------+   |
+-------------------------------------------------------------------------------------------------+
```

### Deep Dive: STAMP (Systems-Theoretic Accident Model and Processes) dalam AI

Pendekatan *root-cause* tradisional mencari "satu penyebab tunggal" (sering kali jatuh pada *human error*: "Engineer X salah menulis *prompt* atau mengonfigurasi memori agen"). Dalam *Systems Engineering* modern, kita menerapkan STAMP:
1. **Kecelakaan adalah masalah kontrol sistemik**, bukan kegagalan komponen terisolasi.
2. Kegagalan agen otonom terjadi karena **kurangnya batasan (*constraints*)** pada derajat kebebasan agen (*degrees of freedom*).
3. Post-mortem harus mengkaji: *Mengapa arsitektur mengizinkan keputusan berbahaya dieksekusi tanpa validasi ganda? Mengapa sistem telemetri tidak memberikan visibilitas awal kepada engineer?*

---

## 4. Why & What

### Mengapa Kegagalan dalam Sistem AI Butuh Pendekatan Kultural yang Berbeda?

| Dimensi | Rekayasa Tradisional (Deterministik) | Rekayasa Agen AI & Data (Nondeterministik) |
| :--- | :--- | :--- |
| **Sifat Kegagalan** | Bug logika biner ($A \rightarrow B$, jika terjadi $C$ maka terdapat cacat kode). | Perilaku emergen (*emergent behavior*), degradasi probabilitas, halusinasi semantik. |
| **Pemicu Insiden** | Kode baru dirilis tanpa pengujian unit yang memadai. | Distribusi input eksternal bergeser (*out-of-distribution*), *jailbreak*, perubahan *underlying model weights*. |
| **Dampak Budaya Takut** | Engineer menunda rilis kode. | Engineer **menyembunyikan anomali probabilitas**, mematikan evaluasi otomatis yang ketat agar tidak "merusak" metrik pribadi, atau membatasi agen pada tugas trivial. |
| **Mitigasi Efektif** | *Unit & Integration Testing*, *TDD*. | *Continuous Evals*, *Red-teaming*, *Circuit Breakers*, *Blameless Model Auditing*. |

### Apa Itu Psychological Safety Operasional?
Keamanan psikologis operasional didefinisikan sebagai **keyakinan bersama bahwa tim tidak akan mempermalukan, menolak, atau menghukum seseorang karena berbicara tentang ide, pertanyaan, keraguan, atau melakukan kesalahan saat mengoperasikan sistem AI berisiko tinggi.**

---

## 5. How (Workflow Detail)

Siklus *Incident Management* nir-salah terotomatisasi untuk sistem agen otonom:

```
[Agen AI Produksi Menghasilkan Output Menyimpang]
                     │
                     ▼
[1. DETEKSI ANOMALI OTOMATIS]
  - Hallucination Score > 0.08
  - Pola Tool Invocation Abnormal (Looping)
  - Biaya API Spike > $500/jam
                     │
                     ▼
[2. CONTAINMENT BLAST RADIUS (0-TOUCH)]
  - Circuit Breaker Aktif (Buka Sirkuit)
  - Degradasi Halus: Fallback ke Model Deterministik / Rule-Based
  - Engineer On-Call TIDAK dipersalahkan atas tindakan pemutusan sistem
                     │
                     ▼
[3. TELEMETRY CAPTURE & ANONYMIZATION]
  - Capture input/output, execution trace, state memory
  - Scrub PII (Personally Identifiable Information)
  - Push data ke Isolasi Debugging
                     │
                     ▼
[4. LLM-ASSISTED BLAMELESS DRAFTING]
  - Parsing log & telemetry menjadi Timeline Fakta
  - Menghapus atribusi personal (e.g., ganti "Developer John merilis PR #123" 
    menjadi "Pipeline CI/CD menerapkan Artifact #123")
  - Memetakan Kontributor Sistemik (Latency, Eval Gaps, Resource Limits)
                     │
                     ▼
[5. RETROSPEKTIF BLAMELESS SISTEMIK]
  - Fokus pada: What, How, dan Next Safeguards
  - Larangan kata: "Ceroboh", "Seharusnya mengecek", "Kelalaian"
  - Output: 3 Action Items Arsitektural (e.g., pasang Guardrail baru, tambah dataset eval)
```

---

## 6. Analogy & Diagram ASCII

### Analogi: Kotak Hitam Penerbangan & Dual-Control Cockpit

Dalam penerbangan sipil, kecelakaan tidak diselesaikan dengan memenjarakan pilot yang mengalami disorientasi instrumen, melainkan dengan **menganalisis Kotak Hitam (Flight Data Recorder)** untuk mendesain ulang antarmuka kokpit (*human-machine interface*) dan redundansi autopilot. 

Jika pilot dihukum atas setiap pengakuan salah tafsir instrumen, mereka akan menyembunyikan laporan nyaris-celaka (*near-miss*), yang pada akhirnya menyebabkan kecelakaan fatal skala besar. Di ranah AI, Agen Otonom adalah *autopilot*, dan Engineer adalah *pilot*. Kita membutuhkan sistem instrumen yang memaafkan kesalahan dan merekam telemetri secara objektif.

```
       PENDEKATAN BERBASIS SALAH (TOXIC)               PENDEKATAN BERBASIS SISTEM (PSYCHOLOGICALLY SAFE)
       
          [Insiden AI Hallucination]                           [Insiden AI Hallucination]
                      │                                                    │
                      ▼                                                    ▼
             "Siapa yang menulis                                  "Bagaimana arsitektur kita
             prompt evaluasi ini?"                                membiarkan token berbahaya lolos?"
                      │                                                    │
          +-----------+-----------+                            +-----------+-----------+
          │                       │                            │                       │
          ▼                       ▼                            ▼                       ▼
    [Engineer Takut]      [Sembunyikan Isu]              [Audit Guardrail]     [Simulasi Adversarial]
          │                       │                            │                       │
          ▼                       ▼                            ▼                       ▼
    [Turnover Tinggi]     [Bencana Produksi]             [Evaluasi Diperketat] [Sistem Makin Resilien]
```

---

## 7. Simple Example & Practical Example

Berikut adalah implementasi sistem otomatisasi *Incident Triage & Blameless Post-Mortem Generator* kelas produksi menggunakan Python, Pydantic, dan integrasi OpenTelemetry/LLM. Sistem ini bertugas mengumpulkan artefak teknis secara objektif tanpa bias personal ketika agen AI mengalami kegagalan.

### File: `hands-on/m02/blameless_engine.py`

```python
"""
Blameless Incident Management & Automated Triage Engine
Arsitektur penanganan insiden sistem agen otonom dengan isolasi atribusi personal.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BlamelessEngine")


class SystemTelemetryArtifact(BaseModel):
    trace_id: str
    agent_id: str
    service_name: str
    metric_name: str
    threshold_exceeded: float
    actual_value: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload_snippet: Optional[str] = None


class SystemicContributingFactor(BaseModel):
    category: str  # e.g., "Observability Gap", "Architectural Boundary", "Environment Drift"
    description: str
    remediation_hypothesis: str


class BlamelessPostMortemDocument(BaseModel):
    incident_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    severity: str
    trigger_summary: str
    anonymized_timeline: List[str]
    systemic_factors: List[SystemicContributingFactor]
    remedial_guardrails_required: List[str]

    def render_markdown(self) -> str:
        """Merender dokumen post-mortem nir-salah untuk tinjauan engineering."""
        timeline_str = "\n".join([f"- {t}" for t in self.anonymized_timeline])
        factors_str = "\n".join([
            f"### Kategori: {f.category}\n- **Observasi Sistem**: {f.description}\n- **Hipotesis Mitigasi**: {f.remediation_hypothesis}"
            for f in self.systemic_factors
        ])
        actions_str = "\n".join([f"- [ ] {action}" for action in self.remedial_guardrails_required])

        return f"""# Blameless System Retrospective: {self.incident_id}
**Tingkat Keparahan:** {self.severity}  
**Waktu Kejadian (UTC):** {self.created_at.isoformat()}

## Ringkasan Anomali Sistem
{self.trigger_summary}

## Kronologi Fakta Teknis (Objective Timeline)
{timeline_str}

## Analisis Faktor Sistemik (STAMP Framework)
*Catatan: Dokumen ini secara eksplisit mengabaikan kesalahan manusia individu dan berfokus pada keandalan arsitektur.*

{factors_str}

## Rekomendasi Guardrail Arsitektural (Action Items)
{actions_str}
"""


class BlamelessPostMortemGenerator:
    """Mesin pengolah telemetri menjadi laporan insiden tanpa atribusi personal."""

    def __init__(self, incident_id: str, severity: str):
        self.incident_id = incident_id
        self.severity = severity
        self.telemetry_events: List[SystemTelemetryArtifact] = []

    def ingest_telemetry(self, artifact: SystemTelemetryArtifact) -> None:
        """Menerima metrik dan jejak telemetri kegagalan agen."""
        logger.info(f"Ingesting telemetry trace: {artifact.trace_id} from {artifact.agent_id}")
        self.telemetry_events.append(artifact)

    def _sanitize_and_anonymize(self, text: str) -> str:
        """Menghapus indikasi personal, identitas engineer, atau token sensitif."""
        # Simulasi sanitasi deterministik
        sanitized = text.replace("deployed by user", "automated pipeline trigger")
        sanitized = sanitized.replace("manual push", "pipeline synchronization")
        return sanitized

    def generate_report(self) -> BlamelessPostMortemDocument:
        """Memproses artefak dan menghasilkan struktur post-mortem."""
        timeline: List[str] = []
        factors: List[SystemicContributingFactor] = []
        guardrails: List[str] = []

        for event in self.telemetry_events:
            ts_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            timeline.append(
                f"[{ts_str}] Layanan `{event.service_name}` melaporkan anomali `{event.metric_name}`: "
                f"Nilai riil {event.actual_value} melampaui batas toleransi aman ({event.threshold_exceeded}). "
                f"Trace ID: {event.trace_id}"
            )

            # Heuristik pemetaan faktor sistemik dari jenis metrik
            if "hallucination" in event.metric_name.lower():
                factors.append(
                    SystemicContributingFactor(
                        category="Evaluasi & Validasi Output Real-Time",
                        description=f"Model agent `{event.agent_id}` menghasilkan token yang melampaui batas ambang halusinasi tanpa pencegatan sirkuit lokal.",
                        remediation_hypothesis="Arsitektur kekurangan inline semantic classifier untuk membatalkan output sebelum payload diteruskan ke downstream client."
                    )
                )
                guardrails.append(f"Implementasikan Semantic Guardrail filter pada API Gateway untuk {event.agent_id} dengan batas toleransi < 0.05.")

            elif "cost" in event.metric_name.lower() or "token_rate" in event.metric_name.lower():
                factors.append(
                    SystemicContributingFactor(
                        category="Resource Quota & Boundary Constraints",
                        description="Siklus eksekusi loop otonom agen tidak memiliki pembatas kedalaman iterasi dinamis (infinite loop protection).",
                        remediation_hypothesis="Sistem membutuhkan token bucket hard-limit pada level session database."
                    )
                )
                guardrails.append("Terapkan per-session token budget rate-limiter di tingkat orkestrasi agen.")

        summary = f"Terjadi ekskursi parameter operasional pada {len(self.telemetry_events)} komponen otonom yang memicu automated circuit breaker."

        return BlamelessPostMortemDocument(
            incident_id=self.incident_id,
            severity=self.severity,
            trigger_summary=summary,
            anonymized_timeline=timeline,
            systemic_factors=factors,
            remedial_guardrails_required=guardrails
        )


if __name__ == "__main__":
    # Skenario Simulasi: Kegagalan ReAct Agent Finansial memicu transaksi spekulatif
    generator = BlamelessPostMortemGenerator(incident_id="INC-AGENT-8821", severity="SEV-1")

    # Ingest artefak anomali 1: Hallucination spike
    generator.ingest_telemetry(
        SystemTelemetryArtifact(
            trace_id="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
            agent_id="liquidity-rebalancing-agent-v2",
            service_name="agent-executor-node-us-east",
            metric_name="semantic_hallucination_score",
            threshold_exceeded=0.08,
            actual_value=0.23,
            raw_payload_snippet="Generated portfolio swap action without counterparty verification."
        )
    )

    # Ingest artefak anomali 2: Loop Rate Spike
    generator.ingest_telemetry(
        SystemTelemetryArtifact(
            trace_id="00-6c891a2211b34da6a3ce929d0e0e9999-00f067aa0ba902b7-01",
            agent_id="liquidity-rebalancing-agent-v2",
            service_name="agent-executor-node-us-east",
            metric_name="token_rate_per_minute",
            threshold_exceeded=50000.0,
            actual_value=125000.0,
            raw_payload_snippet="ReAct reasoning iteration count hit 45 cycles in 15 seconds."
        )
    )

    # Render laporan Markdown
    post_mortem = generator.generate_report()
    rendered_doc = post_mortem.render_markdown()
    print(rendered_doc)
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: Bencana Model Arbitrase Multi-Agent pada Perusahaan Fintech Skala Global

#### Konteks
Sebuah institusi perbankan investasi multinasional mengoperasikan kluster *Autonomous Trading Agents* yang diorkestrasi menggunakan arsitektur *event-driven*. Setiap agen memiliki wewenang mengeksekusi rebalancing portofolio mikro secara otomatis hingga batas $1.000.000 per transaksi.

#### Insiden
Pada Q3 2024, terjadi perubahan struktur *API schema* dari penyedia data likuiditas pihak ketiga. Agen tidak mengalami *crash*, melainkan mengalami *silent semantic drift*. Model LLM menginterpretasikan nilai *null* sebagai likuiditas tak terbatas dan mengeksekusi transaksi spekulatif berulang (*infinite loop arbitrage*). Dalam rentang 18 menit, sistem membakar $4,2 juta sebelum *hard limit* manual dieksekusi oleh tim infrastruktur.

#### Kultur Awal (Toxic Blame Culture)
Manajemen puncak secara agresif menuntut pencarian individu yang bertanggung jawab atas pengujian integrasi *prompt* dan validasi skema. Engineer yang memodifikasi *prompt parser* dua hari sebelumnya dijadikan target investigasi.
- **Dampak Langsung:** 
  - Tingkat rilis fitur anjlok 85% dalam 6 minggu berikutnya (*chilling effect*).
  - Dua Staff Engineer dan Principal Data Scientist mengundurkan diri.
  - Tim menyembunyikan 14 insiden kecil (*SEV-3*) berikutnya dengan cara me-restart kontainer agen secara manual tanpa pencatatan tiket resmi.

#### Intervensi EM: Transisi Menuju Architectural Psychological Safety
Engineering Director baru mengambil alih dan menerapkan transformasi terstruktur:
1. **Kebijakan Amnesti & Mandat Post-Mortem Nir-Salah:** Menghentikan segala investigasi kesalahan personel. Mengubah format investigasi menjadi audit sistem kendali kegagalan (*Safety Control Structure*).
2. **Implementasi Hard Architectural Guardrails (Zero-Trust Model Execution):**
   - Agen tidak lagi diizinkan memanggil gateway transaksi secara langsung.
   - Dibuat lapisan *Deterministic Determinant Engine* (C++ low-latency) yang memverifikasi setiap transaksi agen terhadap aturan portofolio sebelum transaksi dieksekusi ke bursa.
3. **Penyusunan Metrik Keamanan Psikologis Berbasis SPACE:**
   - Mengukur metrik *Self-Reported Safety to Fail* triwulanan.
   - Menghubungkan metrik keandalan sistem dengan transparansi: Tim yang melaporkan *near-miss* terbanyak mendapatkan alokasi anggaran eksperimen komputasi GPU paling besar.

#### Hasil
Dalam 9 bulan, *Mean Time to Detect (MTTD)* untuk degradasi semantik turun dari 18 menit menjadi 420 milidetik (karena circuit breaker deterministik). *Deployment velocity* pulih dan melampaui metrik awal sebesar 40%, dengan nol kasus atrisi sukarela pada talenta inti AI.

---

## 9. Trade-offs (Arsitektur & Budaya)

Mengimplementasikan sistem dengan *Psychological Safety* yang didukung arsitektur penahan kegagalan (*fail-safe guardrails*) memiliki konsekuensi operasional:

```
+------------------------------------+------------------------------------+
| KEUNTUNGAN (ADVANTAGES)            | ONGKOS & TANTANGAN (TRADE-OFFS)    |
+------------------------------------+------------------------------------+
| 1. High Velocity of Innovation:    | 1. Increased Latency:              |
|    Engineer berani merilis model   |    Pengecekan Guardrails & Policy  |
|    baru karena tahu ada Circuit    |    Engine (OPA/NeMo) menambah     |
|    Breaker deterministik.          |    15-50ms pada critical path.     |
+------------------------------------+------------------------------------+
| 2. Zero-Suppression of Failures:   | 2. Infrastructure Overhead:        |
|    Celah halusinasi dan jailbreak  |    Memerlukan resource shadow     |
|    terdeteksi lebih awal karena    |    deployment, dual-run evaluation,|
|    transparansi penuh tanpa takut. |    dan penyimpanan log komprehensif|
+------------------------------------+------------------------------------+
| 3. High Talent Retention:          | 3. Governance Complexity:          |
|    Mengurangi burnout on-call dan  |    EM harus terus menjaga disiplin |
|    stres pasca-insiden tim AI.     |    agar "blameless" tidak berubah  |
|                                    |    menjadi "lack of accountability"|
+------------------------------------+------------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### Anti-Pattern 1: "Weaponized Post-Mortem" (Retrospektif Berkedok Kehakiman)
- **Gejala:** Fasilitator bertanya: *"Mengapa Anda tidak menjalankan evaluasi sebelum merge?"* atau dokumen mencatat *"Engineer lupa memperbarui context limit"*.
- **Koreksi Arsitektural:** Ganti pertanyaan dengan perspektif sistem: *"Alat uji mana yang gagal memberikan peringatan bahwa context window terlampaui?"* Otomatisasikan linting evaluasi di tahap PR agar sistem yang menolak, bukan manusia yang mengawasi.

### Anti-Pattern 2: "Blameless Means Consequence-Free Negligence"
- **Gejala:** Anggota tim mengabaikan protokol pengujian formal, meremehkan proses keamanan, dan mengklaim proteksi budaya nir-salah ketika terjadi kekacauan.
- **Koreksi:** Tarik garis tegas antara **Error Eksperimen/Nondeterministik** (dilindungi sepenuhnya) vs **Pelanggaran Kepatuhan Disengaja / Sabotase / Malicious Intent** (tunduk pada tindakan disipliner manajerial). Gunakan diagram pohon keputusan akuntabilitas Just Culture (James Reason).

### Anti-Pattern 3: Alert Fatigue yang Menyamarkan Burnout
- **Gejala:** Model AI memicu ratusan alert SEV-3 per hari karena ambang batas (*threshold*) terlalu sensitif. Engineer mengalami penurunan ketelitian, berujung pada lolosnya SEV-1.
- **Koreksi:** Terapkan aturan *Alert Quarantine*. Jika sebuah alert agen tidak ditindaklanjuti dalam 3 hari, alert tersebut diturunkan menjadi metrik pasif di dashboard dan dikeluarkan dari pager on-call.

---

## 11. Best Practices (Production Checklist)

### Checklist Praktik Engineering Culture & Safety

#### 1. Fase Pre-Deployment (Architectural Safety Net)
- [ ] Agen otonom terisolasi di dalam *sandbox network* tanpa akses langsung ke *state* database produksi.
- [ ] *Fallback Deterministic Engine* siap mengambil alih saat model gagal memberikan parsing terstruktur (JSON schema validation failure).
- [ ] *Shadow Deployment* berjalan aktif minimal $N=10.000$ transaksi sebelum model agen baru dialihkan ke jalur *live*.

#### 2. Fase Post-Incident (Socio-Technical Governance)
- [ ] Fasilitator post-mortem adalah pihak ketiga yang independen (lintas tim).
- [ ] Dokumen post-mortem divalidasi oleh linter bahasa untuk memastikan penghapusan seluruh kata ganti orang (*he, she, they, developer X*).
- [ ] Minimal 80% dari rencana tindak lanjut (*action items*) berfokus pada **perubahan kode, guardrail otomatis, atau telemetri**, bukan pada "dokumentasi ulang" atau "pelatihan manusia".

#### 3. Fase Kultur & Telemetri Organisasi
- [ ] Mengukur *Mean Time to Remediate (MTTR)* bukan sebagai ukuran performa individu, melainkan ukuran efektivitas instrumentasi observabilitas.
- [ ] Pelaksanaan survei anonymized *Psychological Safety Index* berkala (skala Likert 1-7) dengan evaluasi tren kuartalan.

---

## 12. Hands-on Practice

Simpan seluruh file berikut ke dalam direktori: `hands-on/m02/`

### File: `hands-on/m02/run_simulation.sh`
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "Memulai Simulasi Incident Triage & Blameless Pipeline..."
echo "=========================================================="

python3 -m venv venv
source venv/bin/activate
pip install -q pydantic

python3 blameless_engine.py > post_mortem_output.md

echo "File post_mortem_output.md berhasil digenerasi secara objektif."
cat post_mortem_output.md
```

### Langkah Eksekusi Praktikum:
1. Masuk ke direktori: `cd hands-on/m02/`
2. Jalankan skrip bash: `chmod +x run_simulation.sh && ./run_simulation.sh`
3. Amati bagaimana artefak log nondeterministik diubah secara otomatis menjadi rencana aksi hardening sistemik (*guardrails*) tanpa menyudutkan operator teknis.

---

## 13. Exercise

### Level Easy
Modifikasi kelas `BlamelessPostMortemGenerator` di `blameless_engine.py` untuk mendeteksi anomali metrik baru: `"context_drift_ratio"`. Jika metrik ini melampaui 0.40, otomatisasi penambahan *systemic factor* berupa rekomendasi penyegaran *vector database index*.

### Level Medium
Buat modul Python `burnout_detector.py` yang memproses log interaksi PR (Pull Request) GitHub dan notifikasi PagerDuty. Modul harus menghasilkan skor risiko kelelahan tim (*Team Cognitive Exhaustion Score*, skala 0-1.0) dengan mempertimbangkan:
- Jumlah eskalasi on-call di luar jam kerja (22:00 - 06:00).
- Latensi review PR yang meningkat > 200% dari rata-rata baseline (indikator isolasi kognitif).

### Level Hard
Bangun integrasi arsitektural menggunakan FastAPI yang bertindak sebagai *Reverse Proxy* untuk Agen LLM. Jika agen merespons dengan format yang tidak valid (melanggar skema JSON) sebanyak 3 kali berturut-turut, *proxy* harus secara otomatis:
1. Membuka sirkuit (*circuit breaker*).
2. Mengalihkan lalu lintas downstream ke *rule-based heuristic engine*.
3. Mengirimkan payload anomali yang disanitasi ke endpoint `blameless_engine.py` untuk membuka draf retrospektif tanpa membunyikan alarm destruktif pada engineer on-call.

---

## 14. Challenge

### Studi Kasus: "The Cascading Hallucination Downfall"

**Deskripsi Tantangan:**  
Anda adalah Engineering Director di sebuah platform Healthcare Enterprise. Tim Anda baru saja meluncurkan *Autonomous Clinical Agent* yang bertugas merangkum rekam medis pasien dan merekomendasikan kode diagnosis ICD-10 kepada dokter. 

Pada hari Minggu malam, sebuah perubahan model dasar (*foundation model upstream update*) yang dilakukan oleh vendor AI menyebabkan agen mengalami degradasi logika: Agen mulai mengarang riwayat alergi obat yang tidak ada (*false positive allergy*). 

Seorang engineer on-call tingkat junior yang panik mencoba melakukan *hotfix prompt* langsung di *production environment* tanpa melalui pipeline CI/CD, yang justru menyebabkan agen berhenti memproses data seluruhnya (*system blackout*) di 40 rumah sakit rekanan selama 3 jam.

**Instruksi Penugasan:**
1. **Rancang Rencana Penanganan Krisis (Crisis Communication & Post-Mortem):**
   - Buat dokumen pengumuman internal yang membela engineer junior tersebut dari perundungan organisasi dan mengarahkan fokus eksekutif pada kegagalan sistem kendali CI/CD.
2. **Desain Ulang Arsitektur Kendali Sistemik:**
   - Gambarkan diagram arsitektur pencegahan yang memvalidasi bahwa secara teknis tidak ada satupun engineer (termasuk Principal/Admin) yang dapat mengubah parameter inferensi tanpa evaluasi regresi otomatis.
3. **Penyusunan Action Items Berdasarkan Just Culture Matrix:**
   - Klasifikasikan akar masalah insiden ini ke dalam: *Systemic Flaws*, *Human Error*, dan *At-Risk Behavior*, serta tetapkan mitigasi preventif untuk masing-masing kategori.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Basic (Pilihan Ganda)

1. Apa definisi mendasar dari *Psychological Safety* dalam tim rekayasa perangkat lunak menurut Dr. Amy Edmondson?
   - A. Menghilangkan seluruh target kinerja agar engineer tidak stres.
   - B. Keyakinan bahwa tim aman untuk mengambil risiko interpersonal tanpa rasa takut dipermalukan atau dihukum.
   - C. Kebijakan manajemen untuk tidak pernah memecat engineer apa pun yang terjadi.
   - D. Mekanisme monitoring ketat untuk memastikan tidak ada kesalahan kode yang lolos.

2. Mengapa pendekatan *Root Cause Analysis* (RCA) tradisional "5-Whys" sering kali gagal dalam insiden sistem AI/LLM?
   - A. Karena model AI berjalan terlalu cepat untuk dihitung dengan angka lima.
   - B. Karena sistem nondeterministik memiliki penyebab kegagalan kompleks dan emergen, bukan satu titik kegagalan linier (*single human root-cause*).
   - C. Karena engineer AI menolak untuk diwawancarai pasca insiden.
   - D. Karena LLM tidak mencatat sistem log.

3. Apa fungsi utama dari *Architectural Guardrail* dalam membangun budaya eksperimen yang aman?
   - A. Memperlambat proses deployment agar tim lebih berhati-hati.
   - B. Membatasi *blast radius* kegagalan sistemik secara otomatis sehingga tim berani mencoba inovasi berisiko tinggi.
   - C. Melacak engineer mana yang melakukan kesalahan kompilasi kode.
   - D. Menghapus kebutuhan akan proses code review.

4. Manakah kata berikut yang **wajib dihindari** dalam penulisan dokumen *Blameless Post-Mortem*?
   - A. *Threshold exceeded*
   - B. *Latency anomaly*
   - C. *Developer kelalaian/ceroboh*
   - D. *Circuit breaker triggered*

5. Dalam metrik SPACE, indikator mana yang paling sensitif terhadap penurunan *psychological safety*?
   - A. Activity (Jumlah baris kode).
   - B. Efficiency (Waktu tunggu kompilasi CI/CD).
   - C. Well-being & Communication (Tingkat keterbukaan pelaporan near-miss dan retensi tim).
   - D. Performance (Uptime server 99.99%).

---

### Bagian B: Intermediate (Analisis Singkat)

1. Jelaskan perbedaan mendasar antara model pertanggungjawaban *Retributive Justice* vs *Restorative/Just Culture* dalam penanganan insiden produksi AI!
2. Bagaimana arsitektur *Shadow Deployment* berkontribusi langsung terhadap penurunan tingkat kecemasan (*anxiety*) tim data science saat meluncurkan agen otonom baru?
3. Sebutkan dua metrik kuantitatif berbasis sistem (telemetri) yang dapat digunakan Engineering Manager sebagai *proxy* untuk mendeteksi *developer burnout* pada tim yang mengoperasikan agen AI 24/7!
4. Mengapa "Human Error" harus diposisikan sebagai **awal dari investigasi**, bukan **akhir dari investigasi** post-mortem?
5. Bagaimana cara seorang EM merespons eksekutif non-teknis yang menuntut agar engineer yang "menyebabkan" kerugian finansial akibat halusinasi agen dipecat?

---

### Bagian C: Skenario Kasus Produksi (Uraian Solutif)

#### Skenario 1: The Silenced Anomaly
Sebuah model rekomendasi agen finansial mulai menyimpang (*drift*) secara halus selama 2 minggu, namun engineer yang menyadarinya tidak membuka tiket eskalasi karena takut skor OKR timnya tentang "Model Stability" menurun. Bagaimana Anda merestrukturisasi sistem evaluasi metrik kinerja tim agar insiden serupa tidak terulang?

#### Skenario 2: Escalation Storm
Setelah terjadi insiden halusinasi SEV-1, pimpinan organisasi memberlakukan aturan bahwa setiap perubahan prompt agen LLM harus disetujui (*signed-off*) oleh 3 orang Manager dan 1 Security Architect. Analisis dampak kebijakan ini terhadap *psychological safety*, kecepatan inovasi tim, serta berikan arsitektur alternatif yang lebih elegan!

#### Skenario 3: The Blame Leakage
Dalam sesi retrospektif insiden kegagalan *data extraction pipeline*, seorang Senior Architect secara terbuka berkata kepada Mid-level Engineer: *"Jika Anda membaca dokumentasi API vendor dengan benar, sistem kita tidak akan lumpuh selama 4 jam!"* Ruang rapat seketika hening. Sebagai EM yang memfasilitasi rapat tersebut, apa tindakan verbal langsung yang Anda ambil dalam detik tersebut untuk memulihkan *psychological safety*, dan intervensi lanjutan apa yang Anda terapkan secara privat pasca rapat?

---

## 16. Summary

1. **Safety is an Architectural Feature:** Keamanan psikologis tidak dapat bertahan hanya melalui retorika manajerial; ia membutuhkan topangan arsitektur teknis (*Circuit Breakers*, *Shadow Deployments*, *Deterministic Guardrails*) yang membatasi dampak kegagalan manusia dan agen secara otomatis.
2. **From Blame to Systems-Thinking:** Di era nondeterministik AI, kegagalan adalah sifat alami dari eksplorasi sistemik. Penerapan kerangka kerja *Blameless Post-Mortem* berbasis STAMP mengalihkan fokus dari "siapa yang salah" ke "mengapa sistem kendali mengizinkan kegagalan terjadi".
3. **Measurement Drives Culture:** Mengombinasikan metrik DORA dengan metrik afektif SPACE memungkinkan Technical Leader mendeteksi ketakutan struktural, kelelahan kognitif, dan *alert fatigue* sebelum bermutasi menjadi kegagalan sistem katastropik atau atrisi talenta rekayasa terbaik.