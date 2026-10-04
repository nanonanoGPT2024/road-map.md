# Module 02 — Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Kategori:** 08-AI-Data-and-Autonomous-Agents  
**Topik:** Product Manager (AI & Autonomous Systems)  
**Bab 10:** Product Governance, Stakeholder Architecture & Compliance Engineering

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Technical Product Manager (TPM) dan AI System Architect diharapkan mampu:
1. **Merancang Arsitektur Tata Kelola Produksi (Production Governance Architecture):** Mengonstruksi *decoupled governance control plane* yang memisahkan eksekusi model/agen dari penegakan kebijakan (*policy enforcement*), kepatuhan (*regulatory compliance*), dan pengawasan biaya (*FinOps*).
2. **Mengimplementasikan Guardrail & Policy-as-Code Terdistribusi:** Menerapkan evaluasi kebijakan deterministik (*deterministic policy engine*) menggunakan Open Policy Agent (OPA/Rego) dan *semantic guardrails* secara asinkronus tanpa mengorbankan p99 latency SLA.
3. **Membangun Mekanisme Human-in-the-Loop (HITL) Adaptif:** Mengonfigurasi gerbang eskalasi berbasis skor ambang batas risiko (*risk-tier dynamic gating*) untuk memenuhi mandat EU AI Act (High-Risk AI Systems), NIST AI RMF, dan ISO/IEC 42001.
4. **Mengeksekusi Audit Telemetry & Forensik Agen:** Mendesain pipeline telemetri terstruktur berbasis OpenTelemetry (OTel) yang mencatat *trace-lineage*, input/output sanitization, token consumption attribution, dan *non-repudiation audit trails*.

---

## 2. Prerequisite
Sebelum mendalami modul ini, peserta wajib memahami:
* **Konseptual:** Fondasi siklus hidup Large Language Models (LLM), orkestrasi Autonomous Agents (ReAct, LangGraph, AutoGen), dan regulasi kecerdasan buatan (EU AI Act, GDPR Article 22, NIST AI RMF 1.0).
* **Teknis:** 
  * Kemampuan membaca dan menulis sintaks dasar Python 3.11+ (Type hints, AsyncIO, Pydantic v2).
  * Pemahaman tentang arsitektur microservices, Reverse Proxy / API Gateway (Envoy, Kong, atau FastAPI).
  * Pengalaman dengan structured logging (JSON lines) dan konsep Distributed Tracing (Span, Trace ID).
  * Familiaritas dengan konsep Declarative Configuration (YAML, Rego OPA).

---

## 3. Concept & Internal Architecture

Dalam lanskap produksi skala enterprise, sistem AI otonom tidak boleh diperlakukan sebagai *black box monolith*. Tata kelola (*governance*) tidak boleh sekadar berupa dokumen kepatuhan pasif, melainkan harus diwujudkan menjadi komponen infrastruktur aktif (*active runtime infrastructure*).

```
+---------------------------------------------------------------------------------------+
|                             ENTERPRISE CLIENT APPLICATION                             |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|               AI GOVERNANCE CONTROL PLANE (INSPECTION & ROUTING PROXY)                |
|                                                                                       |
|   +--------------------+    +--------------------+    +---------------------------+   |
|   | 1. Ingress Sanitizer| -> | 2. Deterministic   | -> | 3. Semantic Guardrails    |   |
|   |    (PII Masking,   |    |    Policy Engine   |    |    (NeMo / Custom Vector  |   |
|   |     Prompt Inject) |    |    (OPA / Rego)    |    |     Safety Embedding)     |   |
|   +--------------------+    +--------------------+    +---------------------------+   |
|                                                                     |                 |
|                                         +---------------------------+                 |
|                                         v                                             |
|                     +---------------------------------------+                         |
|                     |     Dynamic Risk Evaluation Engine    |                         |
|                     |     (Risk Tier: Low / Med / High)     |                         |
|                     +---------------------------------------+                         |
|                                         |                                             |
+-----------------------------------------|---------------------------------------------+
                     +--------------------+--------------------+
                     | [High Risk Threshold Exceeded]          | [Pass / Safe]
                     v                                         v
+---------------------------------------+   +-------------------------------------------+
| HUMAN-IN-THE-LOOP (HITL) WORKFLOW     |   | AUTONOMOUS AGENT ORCHESTRATION CLUSTER    |
| - State Suspended via Temporal/Redis  |   | - Context Augmentation & Tools Execution  |
| - Slack/Jira Enterprise Incident Hook |   | - Foundation LLM Calling                  |
| - Compliance Officer Signed Approval  |   | - Dynamic Fallback Engine                 |
+---------------------------------------+   +-------------------------------------------+
                     |                                         |
                     +--------------------+--------------------+
                                          v
+---------------------------------------------------------------------------------------+
|                    EGRESS POST-PROCESSING & AUDIT SINK LAYER                          |
|                                                                                       |
|   +---------------------+   +---------------------+   +---------------------------+   |
|   | Toxic/Hallucination |   | Cost & Token Quota  |   | Immutable Audit Vault     |   |
|   | Verification Filter |   | Ledger (Chargeback) |   | (OpenTelemetry -> S3/WORM)|   |
|   +---------------------+   +---------------------+   +---------------------------+   |
+---------------------------------------------------------------------------------------+
```

### Komponen Inti Arsitektur Tata Kelola:
1. **Ingress Sanitizer & Zero-Trust Inspection:** Lapisan inspeksi payload masuk sebelum menyentuh konteks memori agen. Mencegah eksploitasi *Direct/Indirect Prompt Injection* dan melakukan redaksi PII (*Personally Identifiable Information*) berbasis deteksi token kriptografis.
2. **Deterministic Policy Engine (OPA/Rego):** Mesin evaluasi berbasis aturan biner statis. Memvalidasi batasan kontekstual: jam operasional, batasan otorisasi peran (*Role-Based Access Control*), geolokasi data, dan anggaran biaya per sesi tanpa latensi inferensi LLM.
3. **Semantic Guardrails Layer:** Lapisan inspeksi probabilistik untuk mendeteksi *jailbreak*, bias, ujaran kebencian, atau topik di luar domain bisnis yang ditentukan (menggunakan *small embeddings* atau SLM terlatih).
4. **Dynamic Risk Evaluation Engine:** Mengalkulasi agregat skor risiko. Jika skor melampaui ambang batas (*threshold*), alur eksekusi dialihkan ke *state machine* persisten untuk intervensi manusia (HITL).
5. **Egress Verifier & Immutable Audit Sink:** Memvalidasi *output* akhir terhadap halusinasi faktual (*faithfulness scoring*), mendaftarkan metrik token ke *ledger* FinOps untuk *chargeback*, dan menulis *trace lineage* ke penyimpanan *Write-Once-Read-Many* (WORM).

---

## 4. Why & What

### Mengapa Pendekatan Ini Krusial?
* **Regulasi yang Mengikat secara Hukum:** Regulasi seperti EU AI Act menetapkan denda hingga €35 juta atau 7% dari omzet global tahunan untuk kegagalan tata kelola sistem AI berisiko tinggi.
* **Risiko Reputasi & Eskalasi Malicious:** Agen yang memiliki kapabilitas *tool-calling* (seperti akses basis data atau transfer dana) dapat dieksploitasi untuk aksi destruktif jika tidak memiliki pemisahan wewenang (*separation of concerns*).
* **FinOps Predictability:** Tanpa pembatasan tata kelola berbasis kuota dan pembatalan dinamis (*dynamic circuit breaking*), loop agen otonom yang gagal (*runaway agent loops*) dapat menghabiskan ribuan dolar dalam hitungan menit.

### Apa Peran Technical Product Manager (TPM)?
TPM tidak sekadar mendefinisikan *prompt*, melainkan merancang **Service Level Agreements (SLAs)**, **Error Budgets**, **Risk Matrices**, dan **Traceability Standards** yang diterjemahkan menjadi kode kebijakan yang dapat dieksekusi (*executable policy code*).

---

## 5. How (Workflow Detail)

Alur kerja evaluasi tata kelola produksi beroperasi melalui Finite State Machine (FSM) terdistribusi berikut:

```
[User Request] 
      │
      ▼
(State: INGRESS_RECEIVED) 
      │──> Validasi Skema JSON & Ekstraksi Token Identitas (IAM)
      ▼
(State: DETERMINISTIC_EVAL)
      │──> Evaluasi OPA: Role Check, Timeframe, Regional Data Boundary
      ├──> [Fail] ──> Abort (HTTP 403 / Audit Log Written)
      ▼ [Pass]
(State: SEMANTIC_SANITIZATION)
      │──> Scrub PII, Deteksi Injeksi Prompt via Classifier Terdistribusi
      ├──> [Fail] ──> Abort (HTTP 400 / Threat Vector Logged)
      ▼ [Pass]
(State: AGENT_EXECUTION_ORCHESTRATION)
      │──> Agen menjalankan tool-calling & reasoning loop
      │──> Runtime check: Token Limit, Tool Call Permission Scope
      ▼
(State: RISK_THRESHOLD_GATE)
      │──> Kalkulasi: Risk_Score = f(Action_Impact, Sensitivity, Uncertainty)
      ├──> Risk_Score >= 0.85 ──> (State: HITL_SUSPENDED) 
      │                                 │──> Notifikasi Reviewer via Webhook
      │                                 │──> Polling / Event-Driven Callback
      │                                 └──> Manual Approve/Reject
      ▼ [Risk_Score < 0.85 OR Approved]
(State: EGRESS_COMPLIANCE_EVAL)
      │──> Deteksi Halusinasi vs Ground Truth Context
      │──> Verifikasi Format Keluaran (Pydantic Output Validation)
      ▼
(State: AUDIT_TELEMETRY_FLUSH)
      │──> Emit OpenTelemetry Trace (TraceId, PromptTokens, CompletionTokens, CostUSD)
      ▼
[User Response Delivered]
```

---

## 6. Analogy & Diagram ASCII

### Analogi Mental
Bayangkan sistem agen otonom enterprise seperti **Pesawat Komersial Modern**:
* **LLM / Foundation Model** adalah **Mesin Jet Turbofan**: Sumber tenaga penggerak utama, bertenaga masif, namun probabilistik dan tidak memiliki kesadaran arah navigasi.
* **Agentic Framework** adalah **Fly-by-Wire Computer**: Menerjemahkan niat pilot ke aktuator kemudi.
* **AI Governance Control Plane** adalah **Sistem Air Traffic Control (ATC) & Black Box Flight Recorder**:
  * Menginspeksi apakah rute legal sebelum *take-off* (Ingress Policy).
  * Menghentikan autopilot ketika anomali ekstrem terdeteksi dan menyerahkan kendali ke pilot manusia (HITL Escalation).
  * Mencatat setiap parameter manuver ke memori tahan-hancur untuk forensik pasca-insiden (Audit Vault).

```
                      AIRSPACE (PRODUCTION ENVIRONMENT)
                      
   [Flight Request]               [ATC / Air Safety Gate]                [Destination]
         ───>       ================================================>        ───>
                    |   OPA Rego (No-Fly Zone Enforcement)         |
                    |   Semantic Guard (Turbulence Prediction)     |
                    |   Black Box (Continuous Immutable Telemetry) |
                    ================================================
                                          │
                            [Exceeds Safety Threshold]
                                          │
                                          ▼
                               [Human Pilot Overrides]
```

---

## 7. Simple Example & Practical Example

Berikut adalah arsitektur tata kelola siap produksi (*production-ready*) yang mencakup:
1. Skema validasi & redaksi PII deterministik (Python/Pydantic).
2. Definisi Kebijakan Akses & Limit Transaksi (Open Policy Agent Rego).
3. Runtime Controller Governance Proxy yang mengintegrasikan OPA, evaluasi risiko, dan telemetri terstruktur.

### A. Kebijakan OPA: `policies/agent_governance.rego`
```rego
package ai.governance

import future.keywords.in

default allow = false
default require_hitl = false
default reason = "Default deny policy triggered."

# Nilai batas transaksi otonom tanpa verifikasi manusia
max_autonomous_transaction_usd := 5000

# Evaluasi akses dasar
allow {
    not input.user.is_suspended
    input.request.origin_region in ["ID", "SG", "US", "EU"]
    not is_prompt_injection
}

# Deteksi kata kunci indikatif injeksi sederhana deterministik
is_prompt_injection {
    lower_prompt := lower(input.request.prompt)
    contains(lower_prompt, "ignore previous instructions")
} or {
    lower_prompt := lower(input.request.prompt)
    contains(lower_prompt, "system prompt override")
}

# Aturan eskalasi ke Human-In-The-Loop
require_hitl {
    allow
    input.action.type == "EXECUTE_FINANCIAL_TRANSACTION"
    input.action.parameters.amount_usd > max_autonomous_transaction_usd
} or {
    allow
    input.action.type == "DELETE_ENTERPRISE_DATA"
}

# Reason builder
reason = "Request conforms to active governance policies." {
    allow
    not require_hitl
} else = "High impact action flagged: Human-In-The-Loop approval required." {
    allow
    require_hitl
} else = "Request blocked due to security or regional compliance violation." {
    not allow
}
```

### B. Production Implementation: `governance_engine.py`
```python
import uuid
import time
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import httpx

# Inisialisasi logging terstruktur
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ai_governance")

class UserContext(BaseModel):
    user_id: str
    role: str
    is_suspended: bool = False

class AgentAction(BaseModel):
    type: str
    parameters: Dict[str, Any]

class GovernanceRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user: UserContext
    origin_region: str
    prompt: str
    proposed_action: AgentAction

class GovernanceDecision(BaseModel):
    allowed: bool
    requires_hitl: bool
    reason: str
    risk_score: float
    execution_trace_id: str
    latency_ms: float

class ProductionGovernanceGateway:
    def __init__(self, opa_url: str):
        self.opa_url = opa_url
        self.http_client = httpx.AsyncClient(timeout=0.350) # 350ms SLA

    async def _redact_pii(self, prompt: str) -> str:
        """Sanitasi deterministik dasar (Dapat digantikan dengan Named Entity Recognition)"""
        # Implementasi sederhana redaksi string untuk ilustrasi produksi
        import re
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        return re.sub(email_pattern, "[REDACTED_EMAIL]", prompt)

    async def evaluate_request(self, payload: GovernanceRequest) -> GovernanceDecision:
        start_time = time.perf_counter()
        trace_id = str(uuid.uuid4())
        
        # 1. Ingress Sanitization
        sanitized_prompt = await self._redact_pii(payload.prompt)
        
        # 2. Persiapan Data untuk OPA Policy Engine
        opa_payload = {
            "input": {
                "user": payload.user.model_dump(),
                "request": {
                    "origin_region": payload.origin_region,
                    "prompt": sanitized_prompt
                },
                "action": payload.proposed_action.model_dump()
            }
        }
        
        # 3. Deterministic Policy Query ke OPA
        try:
            response = await self.http_client.post(self.opa_url, json=opa_payload)
            response.raise_for_status()
            opa_result = response.json().get("result", {})
        except httpx.RequestError as exc:
            # Fail-safe posture: Matikan eksekusi jika Policy Engine offline
            logger.error(f'{{"event": "governance_failure", "error": "{str(exc)}", "trace_id": "{trace_id}"}}')
            return GovernanceDecision(
                allowed=False,
                requires_hitl=False,
                reason="Governance evaluation unavailable: Fail-Closed Enforced.",
                risk_score=1.0,
                execution_trace_id=trace_id,
                latency_ms=(time.perf_counter() - start_time) * 1000
            )

        allowed = opa_result.get("allow", False)
        requires_hitl = opa_result.get("require_hitl", False)
        reason = opa_result.get("reason", "Policy executed")
        
        # 4. Kalkulasi Skor Risiko Gabungan (Risk Score Calculation)
        base_risk = 0.1
        if requires_hitl:
            base_risk += 0.7
        if not allowed:
            base_risk = 1.0
            
        latency = (time.perf_counter() - start_time) * 1000
        
        # 5. Emit Telemetri Audit Tak Terbantahkan (Audit Log)
        audit_event = {
            "event": "ai_governance_decision",
            "trace_id": trace_id,
            "request_id": payload.request_id,
            "user_id": payload.user.user_id,
            "allowed": allowed,
            "requires_hitl": requires_hitl,
            "risk_score": base_risk,
            "latency_ms": latency,
            "action_type": payload.proposed_action.type,
            "timestamp": time.time()
        }
        logger.info(audit_event)

        return GovernanceDecision(
            allowed=allowed,
            requires_hitl=requires_hitl,
            reason=reason,
            risk_score=base_risk,
            execution_trace_id=trace_id,
            latency_ms=latency
        )
```

---

## 8. Real World Case Study (Enterprise Scale)

### Kasus: *Global Tier-1 NeoBank "ApexVault" Multi-Agent Operational System*
* **Latar Belakang:** ApexVault mengoperasikan armada agen otonom untuk rekonsiliasi transfer saldo antar-rekening, *fraud mitigation*, dan resolusi tiket komplain pelanggan. Agen memiliki hak akses langsung ke *Core Banking API*.
* **Permasalahan:** 
  1. *Prompt injection indirect* via lampiran mutasi bank berhasil memicu eksekusi *chargeback* palsu.
  2. Latensi bertambah 2.500ms akibat penambahan *guardrails* berbasis panggilan LLM berantai (*chained LLM calls*).
  3. Regulator EU menuntut bukti keterlacakan (*traceability*) deterministik sesuai mandat AI Act Pasal 14 (*Human Oversight*).
* **Solusi Arsitektural TPM:**
  1. **Dual-Tier Policy Engine:** Menempatkan Open Policy Agent (OPA) berbasis WASM lokal di API Gateway (latensi <2ms) untuk memblokir anomali skema dan memeriksa izin transaksi di bawah $500.
  2. **Asynchronous Semantic Guardrails:** Model SLM lokal (DeBERTa-v3 finetuned) dijalankan paralel dengan orkestrasi awal agen untuk memverifikasi risiko injeksi, memangkas p99 overhead dari 2.500ms menjadi 45ms.
  3. **Event-Driven Escalation Gating via Temporal:** Transaksi di atas $5.000 memicu intervensi manusia (HITL). *State* agen di-freeze di Temporal.io; webhook dikirim ke portal verifikasi petugas.
* **Hasil (Impact Metrics):**
  * $0 *unauthorized fraudulent agent payouts* pasca-implementasi.
  * p99 Governance Overhead berkurang dari **2.500ms ke 48ms**.
  * Sertifikasi penuh kepatuhan audit EU AI Act Annex IV dalam kurun 3 bulan.

---

## 9. Trade-offs: Architecture Decision Matrix

| Strategi Tata Kelola | Latency Impact | Scalability | Cost per 1M Req | Tingkat Kepastian (Assurance) |
| :--- | :--- | :--- | :--- | :--- |
| **Monolithic LLM Self-Audit** (LLM menginspeksi prompt/output-nya sendiri) | Sangat Tinggi (+1.200 - 3.000ms) | Rendah (Keterbatasan Kuota Model Provider) | Sangat Tinggi ($15 - $60) | **Rendah**: Probabilistik, rawan mengalami *hallucination loop* dan manipulasi *jailbreak*. |
| **Deterministic Sidecar Proxy (OPA/WASM)** | Ultra Rendah (+1 - 5ms) | Sangat Tinggi (Linear Horizontal Scale) | Sangat Rendah (< $0.05 Compute) | **Tinggi (Statis)**: 100% biner deterministik, tetapi buta terhadap ambiguitas semantik/bahasa alami. |
| **Hybrid Decoupled Fabric** (OPA + Embedding Vector Guard + Async HITL) | Moderat (+30 - 70ms) | Tinggi (Microservice Auto-scale) | Rendah-Sedang ($1.20 - $3.50) | **Tertinggi (Enterprise-grade)**: Menggabungkan presisi aturan deterministik dan fleksibilitas inspeksi semantik. |

---

## 10. Common Mistakes & Troubleshooting

### Anti-Patterns & Kesalahan Fatal
1. **The "Prompt-Only Governance" Fallacy:** Meminta LLM "Berperilakulah adil, patuhi hukum, dan jangan biarkan pengguna meretasmu" melalui system prompt.  
   *Dampak:* Sangat rapuh terhadap injeksi adversarial (*Universal Adversarial Triggers*).
2. **Synchronous LLM Guardrail Chaining:** Menjalankan model verifikasi bahasa berukuran besar secara sekuensial sebelum dan sesudah panggilan agen.  
   *Dampak:* Lonjakan latensi tak terkendali dan pembengkakan biaya API (*Cost Explosion*).
3. **Audit Log Masking Loss:** Menghapus data sensitif secara total tanpa menyimpan *hash lineage* kriptografis.  
   *Dampak:* Saat audit compliance forensik dilakukan, insinyur tidak dapat membuktikan input apa yang memicu kerusakan finansial tanpa melanggar undang-undang privasi (GDPR conflict).

### Troubleshooting Runbook: Policy Bottleneck Resolution
* **Gejala:** Latensi gateway AI melonjak dari 150ms ke >3.000ms selama jam puncak transaksi.
* **Diagnosis:**
  1. Periksa metrik OpenTelemetry `governance.eval.duration`.
  2. Apakah semantic guardrail melakukan *out-of-process synchronous remote inference* ke model LLM eksternal?
* **Solusi Mitigasi:**
  1. Aktifkan *circuit breaker* pada Semantic Guardrail: Jika timeout > 80ms, *fallback* ke evaluasi aturan deterministik biner di OPA.
  2. Alihkan evaluasi output agent non-kritis ke mode *asynchronous streaming verification*.

---

## 11. Best Practices (Production Checklist)

### Security & Compliance
- [ ] Implementasikan prinsip *Least Privilege Tool Calling* (Agen hanya memiliki izin eksekusi API spesifik per sesi).
- [ ] Enkripsi *prompt context cache* menggunakan kunci *Customer Managed Encryption Keys* (CMEK).
- [ ] Terapkan WORM (*Write Once, Read Many*) storage policy pada pipeline penyimpanan log audit selama minimal 7 tahun (sesuai standar finansial/medis).

### Operations & Performance
- [ ] Buat SLA tata kelola yang tegas: Lapisan *governance inspection* tidak boleh mengonsumsi lebih dari 10% total anggaran p99 end-to-end latency.
- [ ] Sediakan skema *Graceful Degradation*: Kebijakan biner *Fail-Closed* untuk domain risiko tinggi (Finansial/Kesehatan), dan *Fail-Open with Anomaly Alert* untuk domain risiko rendah (Rangkuman Konten).

### Governance & FinOps
- [ ] Terapkan alokasi biaya berbasis *Metadata Tagging* (Unit Bisnis, User ID, Client ID) ke setiap span OpenTelemetry.
- [ ] Tentukan batas *Max Step Loop Guard* (misal: maksimal 8 iterasi alat) untuk mencegah *infinite execution loops*.

---

## 12. Hands-on Practice

Buat dan jalankan modul verifikasi kepatuhan tata kelola mikro pada repositori lokal Anda:

### Struktur Direktori
```
hands-on/m02/
├── Dockerfile
├── docker-compose.yml
├── policies/
│   └── agent_governance.rego
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── requirements.txt
└── test_governance.py
```

### Langkah Eksekusi

1. **Inisialisasi Lingkungan Kebijakan OPA:**
   Buat file `docker-compose.yml` untuk mengorkestrasi OPA Server:
   ```yaml
   version: '3.8'
   services:
     opa:
       image: openpolicyagent/opa:0.62.0-rootless
       ports:
         - "8181:8181"
       volumes:
         - ./policies:/policies
       command:
         - "run"
         - "--server"
         - "--addr=0.0.0.0:8181"
         - "/policies"
   ```

2. **Jalankan OPA Daemon:**
   ```bash
   docker compose up -d
   ```

3. **Verifikasi Policy Endpoint secara Mandiri:**
   ```bash
   curl -X POST http://localhost:8181/v1/data/ai/governance \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "user": {"user_id": "usr-01", "role": "operator", "is_suspended": false},
         "request": {"origin_region": "ID", "prompt": "Process clean transaction"},
         "action": {"type": "EXECUTE_FINANCIAL_TRANSACTION", "parameters": {"amount_usd": 12000}}
       }
     }'
   ```

4. **Eksekusi Test Suite Terautomasi (`test_governance.py`):**
   ```python
   # Simpan dan jalankan via pytest
   import pytest
   import httpx

   @pytest.mark.asyncio
   async def test_high_value_transaction_requires_hitl():
       async with httpx.AsyncClient() as client:
           payload = {
               "input": {
                   "user": {"user_id": "usr-123", "role": "trader", "is_suspended": False},
                   "request": {"origin_region": "SG", "prompt": "Authorize standard transfer"},
                   "action": {"type": "EXECUTE_FINANCIAL_TRANSACTION", "parameters": {"amount_usd": 7500}}
               }
           }
           res = await client.post("http://localhost:8181/v1/data/ai/governance", json=payload)
           assert res.status_code == 200
           data = res.json()["result"]
           assert data["allow"] is True
           assert data["require_hitl"] is True
           assert "Human-In-The-Loop" in data["reason"]
   ```

---

## 13. Exercise

### Level Easy
Modifikasi aturan Rego `agent_governance.rego` untuk memasukkan pemblokiran terhadap region `"NORTH_KOREA"` dan `"IRAN"`. Uji menggunakan skrip Python untuk memastikan respon mengembalikan `allow = false`.

### Level Medium
Rancang skema Pydantic `EgressVerificationSchema` yang mengevaluasi respon model LLM. Respon harus ditolak (`ValidationError`) jika:
1. Tidak memiliki sitasi sumber (*Source Attribution*).
2. Memiliki estimasi biaya token eksekusi lebih dari $0.15 dalam satu turn.

### Level Hard
Konstruksi arsitektur penanganan *Fallback* berbasis Python AsyncIO: Jika layanan Policy Engine (OPA) mengalami *downtime* (timeout > 350ms), sistem harus mengeksekusi mekanisme *Fail-Closed Strategy* yang aman, mencatat insiden kepatuhan ke format audit terstruktur, dan mengembalikan pesan degradasi yang aman bagi pengguna akhir tanpa mengekspos rincian internal infrastruktur.

---

## 14. Challenge

**Skenario Tantangan:**  
Anda adalah Head of AI Product di sebuah perusahaan asuransi multinasional (*Health & Life Insurance*). Sistem Anda menggunakan multi-agent architecture (1 Agen Pengambil Dokumen Rekam Medis, 1 Agen Penilai Klaim, 1 Agen Transfer Dana Pembayaran).

**Kondisi Batas & Konflik:**
1. Regulator memberlakukan aturan bahwa riwayat penyakit mental **sama sekali tidak boleh** menjadi pertimbangan penolakan klaim (Zero-Discrimination AI Mandate).
2. Pengguna sering kali mengirimkan dokumen rekam medis setebal 50 halaman hasil pindaian OCR kotor yang sering memicu *indirect injection* terselubung.
3. SLAs keputusan klaim adalah maksimum 3 detik secara end-to-end, dengan ketersediaan platform 99.99%.

**Tugas Anda:**
Tuliskan **Spesifikasi Arsitektur Tata Kelola & Dokumen Strategi Teknis (500–800 kata)** yang mendefinisikan:
1. Skema decoupling proteksi privasi vs pembacaan klaim oleh LLM.
2. Definisi *Hard Invariant Policy* vs *Probabilistic Checks*.
3. Rencana penanganan eskalasi HITL tanpa melanggar batasan p99 latency pelanggan secara signifikan.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Dasar (5 Soal)
1. **Apa perbedaan fundamental antara *Prompt-level Guardrails* dan *Decoupled Governance Control Plane*?**  
   a. Prompt-level guardrail berjalan di API Gateway, decoupled plane berjalan di memori GPU.  
   b. Prompt-level guardrail bersifat probabilistik dan rentan manipulasi, sedangkan decoupled control plane mengeksekusi kebijakan deterministik di luar jangkauan komputasi model.  
   c. Prompt-level guardrails lebih murah dan memiliki akurasi 100% dibanding decoupled plane.  
   d. Tidak ada perbedaan fungsional; keduanya hanyalah istilah marketing platform AI.

2. **Dalam implementasi Open Policy Agent (OPA) untuk sistem kecerdasan buatan, bahasa deklaratif apa yang digunakan untuk mendefinisikan batas aturan (*rules*)?**  
   a. YAML  
   b. JSON Schema  
   c. Rego  
   d. GraphQL  

3. **Mengapa strategi *Fail-Closed* wajib diterapkan pada sistem AI yang diklasifikasikan sebagai *High-Risk* menurut EU AI Act?**  
   a. Untuk memastikan sistem tetap menghasilkan output meskipun terjadi kegagalan evaluasi tata kelola.  
   b. Agar konsumsi memori infrastruktur tetap berada di bawah ambang batas kritis.  
   c. Menjamin bahwa jika subsistem inspeksi/keamanan offline, aksi berbahaya dicegah secara mutlak dari eksekusi tanpa otorisasi.  
   d. Mempercepat p99 latency sistem saat terjadi lonjakan beban komputasi.

4. **Manakah dari metrik berikut yang BUKAN merupakan tanggung jawab pemantauan tata kelola FinOps pada sistem Autonomous Agent?**  
   a. Tool-calling frequency per request.  
   b. Total prompt & completion token consumption.  
   c. Model parameter weights quantization ratio.  
   d. Cost attribution per business unit.

5. **Apa fungsi utama dari implementasi sistem WORM (Write-Once-Read-Many) pada audit trail agen AI?**  
   a. Meningkatkan kecepatan baca throughput database analitik.  
   b. Mencegah manipulasi atau penghapusan rekaman jejak audit forensik oleh aktor internal maupun eksternal.  
   c. Mengompresi ukuran payload data telemetri agar hemat kapasitas penyimpanan.  
   d. Mengonversi teks log audit menjadi format vektor semantik.

---

### Bagian B: Analisis Arsitektur Menengah (5 Soal)
6. **Sebuah sistem perbankan multi-agen mengalami degradasi performa p99 sebesar 3.200ms setelah mengimplementasikan guardrails semantik. Langkah mitigasi arsitektural mana yang paling tepat untuk seorang TPM?**  
   a. Mengganti semua LLM dengan model yang lebih besar agar evaluasi lebih cerdas.  
   b. Memisahkan evaluasi: jalankan aturan biner statis (OPA) secara sinkronus di jalur kritis (*critical path*), dan lakukan evaluasi semantik mendalam secara asinkronus/paralel.  
   c. Menghapus audit log untuk menghemat I/O disk gateway.  
   d. Menginstruksikan pengguna untuk tidak mengirimkan prompt yang kompleks.

7. **Kapan intervensi Human-In-The-Loop (HITL) harus dirancang sebagai proses *Blocking / Synchronous* alih-alih *Asynchronous Escalation*?**  
   a. Ketika agen hanya membaca data katalog produk publik.  
   b. Saat aksi agen memiliki konsekuensi finansial, hukum, atau keselamatan fisik yang ireversibel (*irreversible high-impact state change*).  
   c. Ketika latensi respons pengguna harus di bawah 200ms.  
   d. Saat token context window model LLM hampir penuh.

8. **Bagaimana arsitektur *Decoupled Policy Engine* mencegah serangan *Indirect Prompt Injection* yang disematkan ke dalam database kontekstual RAG?**  
   a. Dengan memperluas system prompt LLM utama.  
   b. Dengan memvalidasi keluaran aksi yang diusulkan agen terhadap aturan izin statis (RBAC/ABAC) sebelum alat bantu (*tool*) dieksekusi secara nyata.  
   c. Mengabaikan dokumen RAG yang memiliki lebih dari 1.000 kata.  
   d. Mengenkripsi payload database menggunakan SSL/TLS saat transit.

9. **Dalam audit kepatuhan regulasi kecerdasan buatan, apa yang dimaksud dengan istilah *Non-Repudiation* pada data telemetri agen?**  
   a. Jaminan bahwa model tidak akan pernah mengalami halusinasi logika.  
   b. Bukti forensik kriptografis bahwa tindakan tertentu dieksekusi oleh model/identitas agen tertentu pada waktu tertentu tanpa dapat disangkal keabsahannya.  
   c. Kemampuan agen untuk membatalkan transaksi masa lalu secara sepihak.  
   d. Kebijakan untuk menolak permintaan pengguna yang tidak memiliki alamat email valid.

10. **Apa kelemahan utama mengandalkan metrik "Perplexity" semata sebagai guardrail pencegah halusinasi sebelum data dikirim ke pengguna?**  
    a. Perplexity tidak dapat dihitung pada model open-source.  
    b. Teks yang fasih dan terdengar sangat meyakinkan dapat memiliki nilai perplexity rendah meskipun secara faktual salah (*fluent hallucination*).  
    c. Mengukur perplexity membutuhkan daya komputasi yang setara dengan melatih ulang model fondasi.  
    d. Perplexity hanya dapat dihitung untuk bahasa Inggris, bukan bahasa lain.

---

### Bagian C: Pemecahan Masalah Kasus Produksi (3 Skenario)

#### Skenario Kasus 1: "Runaway Autonomous Fleet Incident"
Agen otonom analitik finansial di perusahaan Anda terjebak dalam *infinite reasoning loop* saat mencoba merekonsiliasi sebuah transaksi anomali. Agen melakukan pemanggilan berulang ke LLM API eksternal sebanyak 4.200 kali dalam 15 menit, menghabiskan biaya $8,400 sebelum terdeteksi secara manual.
* **Pertanyaan 11:** Rancangan arsitektur mitigasi preventif apa yang WAJIB ditambahkan oleh TPM pada *Governance Execution Engine* untuk mencegah terulangnya insiden ini?

#### Skenario Kasus 2: "The Shadow PII Leak"
Sebuah agen pendukung pelanggan (*Customer Support*) enterprise secara tidak sengaja membocorkan data nomor kartu kredit pengguna lain saat merangkum riwayat percakapan. Penyelidikan menunjukkan bahwa data kartu kredit tersebut diinjeksi oleh penyerang melalui formulir masukan alamat pengiriman.
* **Pertanyaan 12:** Di layer arsitektur mana kegagalan tata kelola ini terjadi, dan bagaimana urutan pipeline sanitasi yang benar untuk mengisolasi eksploitasi tersebut?

#### Skenario Kasus 3: "Cross-Border Data Residency Violation"
Model LLM global yang di-host di region US secara otomatis dipanggil oleh agen cabang regional Eropa (EU) untuk memproses klaim medis lokal. Auditor regulasi menemukan bahwa transfer data ini melanggar kedaulatan data (GDPR Cross-Border Transfer Rules) dan mengancam pembekuan izin operasi perbankan.
* **Pertanyaan 13:** Bagaimana Anda mengonfigurasi OPA Policy Engine dan Dynamic Routing Gateway untuk memastikan pembatasan yurisdiksi data ditegakkan secara absolut tanpa menghentikan layanan agen di regional lain?

---

### Kunci Jawaban & Panduan Solusi Quiz

#### Bagian A
1. **b** — Control plane terpisah memaksakan penegakan aturan deterministik di luar batas eksekusi model probabilistik.
2. **c** — Rego adalah bahasa kebijakan deklaratif native untuk Open Policy Agent (OPA).
3. **c** — Pendekatan Fail-closed memastikan keamanan sistem dengan memblokir eksekusi ketika verifikasi keselamatan tidak dapat dipastikan.
4. **c** — Kuantisasi bobot adalah ranah Machine Learning Engineering/Inference Optimization, bukan metrik FinOps operasional produk.
5. **b** — WORM storage menjamin integritas data audit legal tidak dapat dimanipulasi pasca-kejadian.

#### Bagian B
6. **b** — Memisahkan verifikasi statis ultra-cepat dari pemeriksaan semantik mendalam memangkas latensi jalur kritis (*critical path*).
7. **b** — Perubahan status bernilai tinggi dan ireversibel memerlukan konfirmasi manusia sebelum eksekusi terjadi di database target.
8. **b** — Penegakan izin eksekusi alat (*tool permission scope*) mencegah eksekusi aksi destruktif terlepas dari seberapa manipulatif prompt injeksi yang masuk ke konteks LLM.
9. **b** — Non-repudiation mengikat identitas eksekusi dengan bukti kriptografis tak terbantahkan.
10. **b** — Model LLM dapat menghasilkan kebohongan faktual dengan tingkat keyakinan dan kelancaran bahasa yang sangat tinggi (*low perplexity*).

#### Bagian C (Panduan Evaluasi Kasus)
11. **Solusi Skenario 1:** Implementasikan *Hard Loop Boundary Counter* (misal: `max_iterations <= 8`) pada level *Agent Execution Runtime*, dikombinasikan dengan *Circuit Breaker Token Budget Bucket* per sesi pengguna/per transaksi. Jika batas tercapai, sistem memutus siklus otonom dan mengalihkan status ke *DEAD_LETTER_QUEUE* untuk review manual.
12. **Solusi Skenario 2:** Kegagalan terjadi di lapisan *Ingress Sanitization* dan *Egress Masking*. Pipeline yang benar: Masukan pengguna harus melewati *Deterministic Tokenizer & Named Entity Recognition (NER) Scrubber* sebelum disimpan ke konteks memori agen, dan lapisan *Egress Filter* harus memverifikasi ulang keluaran model menggunakan ekspresi reguler PCI-DSS (Luhn algorithm checker) sebelum transmisi payload final.
13. **Solusi Skenario 3:** OPA Policy harus menyertakan aturan berbasis metadata token pengguna: `input.request.origin_region == "EU" -> route_to = "eu-central-1-inference-node"`. API Gateway membaca keputusan OPA dan secara dinamis mengarahkan panggilan inferensi hanya ke cluster lokal yang telah tersertifikasi GDPR, serta menolak (*hard abort*) jika model lokal tidak tersedia alih-alih melempar fallback ke cluster US.

---

## 16. Summary

Implementasi tata kelola produksi untuk produk berbasis AI dan Autonomous Agents menuntut peralihan paradigma dari **Kepatuhan Berbasis Dokumen (Passive Compliance)** ke **Arsitektur Eksekusi Aktif (Active Runtime Architecture)**. 

### Tiga Pilar Fondasi Tata Kelola Produksi TPM:
1. **Decoupled Deterministic Enforcement:** Jangan pernah mempercayai model probabilistik untuk mengawasi perilakunya sendiri. Gunakan mesin kebijakan deterministik seperti OPA/Rego pada level API Gateway.
2. **Fail-Closed Risk Management:** Aksi otonom berdampak tinggi wajib diamankan menggunakan batas ambang risiko dinamis yang terhubung ke mekanisme Human-in-the-Loop persisten.
3. **Comprehensive Forensic Traceability:** Setiap token yang masuk, alat yang dipanggil, dan keputusan yang diambil harus tercatat secara permanen di dalam *immutable telemetry sink* berbasis OpenTelemetry untuk memastikan auditabilitas sistem.