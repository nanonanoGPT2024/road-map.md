# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (Technical PRD & Agentic System Specification)

---

## 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang Technical Product Requirement Document (Tech PRD)** untuk sistem kecerdasan buatan berbasis *autonomous agents* yang mengakomodasi sifat non-deterministik model.
- **Mengonstruksi Contract-First User Stories** dengan batasan *tool execution*, skema data terstruktur (*input/output schema*), dan alokasi *token budget*.
- **Mendefinisikan Non-Functional Requirements (NFR) Kritis** mencakup latensi P99, degradasi sistem gracefully (*graceful degradation*), batas halusinasi (*groundedness threshold*), serta mekanisme *safety guardrails*.
- **Mengintegrasikan Evaluasi Otomatis (Evals-as-Code)** ke dalam pipeline CI/CD sebagai instrumen verifikasi *Acceptance Criteria* (AC) yang dapat diukur secara kuantitatif.
- **Menyusun Traceability Matrix** dari kebutuhan bisnis enterprise hingga unit *eval/benchmark test suite* pada arsitektur multi-agent.

---

## 2. Prerequisites

Peserta diharapkan telah memiliki pemahaman mendalam pada:
- **Konsep Rekayasa Perangkat Lunak**: REST/gRPC API specifications, OpenAPI/JSON Schema, CI/CD workflows, Event-driven architecture.
- **Dasar AI & Agentic Systems**: Dasar LLM (prompting, context window, tokenomics), Retrieval-Augmented Generation (RAG), dan pola orkestrasi Agent (ReAct, Plan-and-Solve, Supervisor-Worker).
- **Metodologi Product Management**: Penulisan User Stories klasik (INVEST criteria), Gherkin Syntax (Given-When-Then), dan manajemen backlog enterprise.

---

## 3. Concept & Internal Architecture

Dalam rekayasa sistem AI deterministik konvensional, relasi input-output dapat didefinisikan secara presisi melalui state machine tradisional. Namun, pada *Autonomous Multi-Agent Systems*, output bersifat probabilistik. Technical Product Manager (TPM) tidak lagi sekadar mendefinisikan *business flow*, melainkan harus mengarsitekturi **Living Contract** yang mengatur batasan non-deterministik model.

```
+---------------------------------------------------------------------------------------+
|                              TECHNICAL PRD ARCHITECTURE                               |
+---------------------------------------------------------------------------------------+
|  1. Semantic Contract Layer                                                           |
|     - System Intent, Persona & Tool Calling Schemas (JSON Schema / Pydantic)          |
|  2. Probabilistic Boundaries Layer                                                    |
|     - Groundedness SLA, Confidence Score Thresholds, Fallback Routing Policies        |
|  3. Tokenomics & Latency Budgets                                                      |
|     - Max Input/Output Tokens per Step, End-to-End Latency Target (P50/P90/P99)        |
|  4. Verification Layer (Evals-as-Code)                                                |
|     - Automated Deterministic Assertion + LLM-as-a-Judge Eval Scenarios               |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|                       EXECUTION & OBSERVABILITY PIPELINE                              |
+---------------------------------------------------------------------------------------+
|  [Agent Runner] <---> [Guardrails Proxy] <---> [Tools / Vector DB / External APIs]    |
|         |                     |                                                       |
|         v                     v                                                       |
|  [OpenTelemetry Spans] -> [Evaluation Harness] -> [Pass/Fail Quality Gate (CI/CD)]    |
+---------------------------------------------------------------------------------------+
```

### Komponen Inti Arsitektur Spesifikasi Teknis AI:
1. **Tool Invocation Contract**: Mendefinisikan secara ketat nama tool, deskripsi semantik, schema argumen, tipe data, serta penanganan error (*tool execution failure handling*).
2. **Context & Token Budgeting Engine**: Alokasi konsumsi token maksimum per loop reasoning agent untuk mencegah *infinite inference loop* yang menguras budget.
3. **Guardrail Specifications**: Kebijakan penyaringan input (jailbreak injection) dan output (PII leakage, bias, ungrounded claims).
4. **Automated Acceptance Testing (Evals-as-Code)**: Transformasi kriteria penerimaan PRD menjadi skrip pengujian berbasis metrik (Ragas, DeepEval, Prometheus metrics).

---

## 4. Why & What

### Why: Kegagalan PRD Konvensional dalam AI Agents
PRD software standar mengasumsikan: `Jika User klik A -> Sistem menampilkan B`. 
Pada Autonomous Agent: `User meminta X -> Agent merencanakan urutan aksi (Plan) -> Memanggil Tool Y -> Mengamati Hasil (Observation) -> Mengambil inferensi final`. 

Jika User Story tidak menetapkan batasan ruang status probabilistik (*probabilistic state space*):
- Biaya token membengkak secara eksponensial akibat *loop reasoning* tanpa henti.
- Agent mengalami *context drift* dan halusinasi instruksi.
- Ketiadaan *Acceptance Criteria* kuantitatif mengakibatkan engineer tidak memiliki definisi jelas mengenai kapan sistem AI siap di-deploy (*Definition of Done*).

### What: The Living & Executable PRD
*Technical PRD* untuk AI Agent adalah dokumen spesifikasi fungsional dan teknis yang menyertakan kontrak skema data, batas toleransi eror probabilitas (*error budget*), arsitektur integrasi tools, serta matriks evaluasi berbasis kode (*executable evals*) yang otomatis berjalan pada setiap *pull request*.

---

## 5. How: Workflow Spesifikasi Teknis End-to-End

Proses penerjemahan kebutuhan bisnis menjadi arsitektur spesifikasi teknis agen:

```
[Kebutuhan Bisnis / Inisiatif Produk]
                 |
                 v
[1. Task Decomposition & Agent Role Definition]
                 |
                 v
[2. Contract-First Tool & Schema Definition (OpenAPI / JSON Schema)]
                 |
                 v
[3. Definisi Non-Functional Requirements (NFR) & Token Budget]
                 |
                 v
[4. Penulisan User Stories Berbasis Gherkin-Agentic Syntax]
                 |
                 v
[5. Kodifikasi Acceptance Criteria ke Eval-as-Code Suite]
                 |
                 v
[6. Review Architecture, Security Guardrails & Sign-Off]
```

1. **Task Decomposition**: Pecah masalah besar ke dalam sub-tugas (*Single Responsibility Principle* untuk setiap Agent).
2. **Contract-First Schema**: Tentukan payload API dan batasan argumen yang valid sebelum kode model diimplementasikan.
3. **NFR & Token Allocation**: Tentukan batas P99 Latency (misal: `< 4.5s`), batas token per session (misal: `4,000 tokens`), dan SLA akurasi faktual (`Groundedness score >= 0.85`).
4. **Agentic Gherkin Syntax**: Gunakan ekstensi Gherkin yang mencakup `Given Context`, `When Agent Plans/Acts`, `Then Tool Invocations must match`, `And Output Confidence meets SLA`.
5. **Eval-as-Code Harness**: Sambungkan kriteria penerimaan langsung ke CI test runner menggunakan unit test dan automated LLM judge.

---

## 6. Analogy & Diagram

### Analogi: Konduktor Orkestra vs. Mesin Cetak Otomatis
- **PRD Tradisional seperti Membeli Mesin Cetak**: Tombol A ditekan, kertas B keluar. Setiap gerakan roda gigi dapat diprediksi secara fisik 100%.
- **Technical PRD Agent seperti Mengontrak Konduktor Orkestra**: Anda tidak dapat menentukan vibrasi absolut setiap senar biola per milidetik. Anda menetapkan **Partitur Lagu (System Prompt)**, **Daftar Instrumen yang Boleh Dimainkan (Available Tools)**, **Rentang Tempo (Latency & Token limits)**, dan **Standar Keharmonisan Minimal (Eval Guardrails)**. Jika konduktor berimprovisasi di luar tangga nada (halusinasi), penjaga panggung (guardrail proxy) segera menariknya ke belakang panggung.

### Architectural Diagram: Spec-to-Production Loop

```
+---------------------------------------------------------------------------------+
|                                 TECH PRD SPEC                                   |
|  - JSON Schema Contracts                                                        |
|  - Token Limits: Context=8K, MaxGen=1K                                          |
|  - Quality SLA: Faithfulness >= 0.90, Tool Accuracy >= 0.98                    |
+---------------------------------------------------------------------------------+
                                      |
                     [Transforms to Validation Code]
                                      v
+---------------------------------------------------------------------------------+
|                          CI/CD EVALUATION PIPELINE                              |
|                                                                                 |
|  +--------------------+    +--------------------+    +--------------------+     |
|  | Unit Test Data     | -> | Agent Execution    | -> | Evaluation Harness |     |
|  | (50 Golden Cases)  |    | (LangGraph/Llama)  |    | (DeepEval / Ragas) |     |
|  +--------------------+    +--------------------+    +--------------------+     |
|                                                                 |               |
|                                     +---------------------------+               |
|                                     |                                           |
|                                     v                                           |
|                   Metric Check: Faithfulness < 0.90?                            |
|                                     |                                           |
|                    +----------------+----------------+                          |
|                    | YES                             | NO                       |
|                    v                                 v                          |
|              [BUILD FAILED]                   [BUILD PASSED]                    |
|         Feedback loop to Prompt/Tool         Deploy to Staging/Prod             |
+---------------------------------------------------------------------------------+
```

---

## 7. Simple & Practical Example

### Practical Implementation: Pydantic Contract & Eval Verification Harness
Berikut adalah implementasi standar industri untuk memvalidasi spesifikasi PRD secara programatis menggunakan Python, Pydantic (Contract-First API), dan Test Runner untuk *Acceptance Criteria*.

#### File: `contracts.py` (Spesifikasi Kontrak Eksekusi Agent)
```python
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class TransactionQueryInput(BaseModel):
    account_id: str = Field(..., regex=r"^ACC-[0-9]{6}$", description="Format ID Akun: ACC-XXXXXX")
    start_date: str = Field(..., description="Format YYYY-MM-DD")
    end_date: str = Field(..., description="Format YYYY-MM-DD")
    max_records: int = Field(default=10, le=50, description="Maksimum record yang dapat ditarik")

class AgentExecutionTrace(BaseModel):
    session_id: str
    total_tokens_used: int
    tools_called: List[str]
    output_text: str
    groundedness_score: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float

    @field_validator("total_tokens_used")
    @classmethod
    def validate_token_budget(cls, v: int) -> int:
        TOKEN_BUDGET_CAP = 3000
        if v > TOKEN_BUDGET_CAP:
            raise ValueError(f"Exceeded hard token budget SLA of {TOKEN_BUDGET_CAP}: Used {v}")
        return v
```

#### File: `test_agent_prd_acceptance.py` (Automated Acceptance Criteria Runner)
```python
import pytest
from contracts import TransactionQueryInput, AgentExecutionTrace

# Mock function merepresentasikan Autonomous Agent yang sedang diuji
def execute_financial_agent(prompt: str) -> AgentExecutionTrace:
    # Simulasi eksekusi agen yang mengembalikan trace terstruktur
    return AgentExecutionTrace(
        session_id="sess-prod-001",
        total_tokens_used=1850,
        tools_called=["get_account_balance", "fetch_transaction_history"],
        output_text="Akun ACC-123456 memiliki total pengeluaran Rp 4.500.000 selama rentang waktu yang ditentukan.",
        groundedness_score=0.94,
        latency_ms=2100.0
    )

class TestFinancialAgentPRDSpec:
    """
    Acceptance Criteria Tests diturunkan langsung dari Technical PRD.
    Target:
    - SLA Groundedness >= 0.90
    - Tool Whitelist Compliance
    - Latency P99 < 3500ms
    - Token Budget <= 3000 tokens
    """

    def test_agent_meets_prds_sla(self):
        user_prompt = "Berapa total pengeluaran akun ACC-123456 antara 2023-01-01 hingga 2023-01-31?"
        
        # Eksekusi sistem agent
        trace = execute_financial_agent(user_prompt)

        # 1. Verifikasi Groundedness (NFR AI Safety & Factual Accuracy)
        assert trace.groundedness_score >= 0.90, (
            f"FAILED SLA: Groundedness score {trace.groundedness_score} di bawah ambang batas 0.90"
        )

        # 2. Verifikasi Tool Calling Whitelist (Security & Containment Policy)
        allowed_tools = {"get_account_balance", "fetch_transaction_history", "convert_currency"}
        for tool in trace.tools_called:
            assert tool in allowed_tools, f"SECURITY BREACH: Agent memanggil unauthorized tool: {tool}"

        # 3. Verifikasi Latency NFR
        MAX_LATENCY_MS = 3500.0
        assert trace.latency_ms <= MAX_LATENCY_MS, (
            f"LATENCY BREACH: Eksekusi memakan waktu {trace.latency_ms}ms (Batas PRD: {MAX_LATENCY_MS}ms)"
        )

    def test_input_schema_validation(self):
        """Memvalidasi integritas parser input sesuai spesifikasi teknis"""
        valid_input = {
            "account_id": "ACC-654321",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "max_records": 25
        }
        validated = TransactionQueryInput(**valid_input)
        assert validated.account_id == "ACC-654321"

        with pytest.raises(Exception):
            # Format ID salah (harus ditolak oleh contract input validator)
            TransactionQueryInput(
                account_id="INVALID-ID",
                start_date="2023-01-01",
                end_date="2023-01-31"
            )
```

---

## 8. Real-World Case Study (Enterprise Scale)

### Kasus: Autonomous Wealth Advisory Agent (PT Finansial Unggul Tbk)
* **Konteks**: Sistem wealth advisory berbasis Multi-Agent yang menangani 1.2 juta nasabah prioritas untuk konsultasi alokasi portofolio investasi secara otomatis.
* **Permasalahan Lapangan**: 
  - Iterasi PRD versi v1 hanya mendefinisikan *business user journey* secara umum.
  - Akibatnya: Model merekomendasikan instrumen investasi berisiko tinggi (*high risk equity*) kepada nasabah profil konservatif saat pasar anjlok (halusinasi inferensi finansial). Tim data engineer menyalahkan prompt engineer, prompt engineer menyalahkan data QA, dan produk terhambat rilis selama 4 bulan.
* **Solusi Arsitektur Technical PRD (v2)**:
  1. **Deterministic Guardrail Hard-Gates**: Spesifikasi mewajibkan agen melewatkan rekomendasi melalui layer *Policy Enforcement Engine* (deterministik Python code) sebelum respons teks digenerasi.
  2. **Evals-as-Code Integration**: Dibuat 300 *Golden Evaluation Datasets* yang mencakup berbagai profil nasabah (Konservatif, Moderat, Agresif). Deployment ke production diblokir otomatis jika akurasi *Risk-Profile Compatibility* di bawah 100% dan *Faithfulness LLM* di bawah 0.95.
  3. **Multi-Agent Protocol Contract**: Sub-agent *Portfolio Analyzer* dan *Market Scraper* diwajibkan berkomunikasi via skema Protobuf biner yang terverifikasi, mengeliminasi variabilitas format JSON.
* **Hasil**:
  - Nol kasus pelanggaran regulasi finansial selama audit OJK.
  - Waktu *release cycle* dipercepat dari 3 minggu menjadi 2 hari per iterasi model berkat evaluasi CI/CD otomatis.

---

## 9. Trade-offs

Dalam merancang spesifikasi sistem agen otonom, Product Manager dihadapkan pada kompromi arsitektural yang krusial:

| Aspek Desain | Pilihan A: Strict Deterministic Guardrails | Pilihan B: High Autonomous Agency | Trade-off Analysis |
| :--- | :--- | :--- | :--- |
| **Akurasi & Kontrol vs Fleksibilitas** | Memaksa structured output, slot-filling, dan rule-based routing. | Mengizinkan ReAct loop bebas menentukan urutan tool. | Pilihan A menjamin kepatuhan regulasi, namun membatasi kemampuan agen menangani skenario tak terduga (*novel edge cases*). Pilihan B sangat adaptif, namun meningkatkan risiko halusinasi alur logis. |
| **Latensi vs Kedalaman Reasoning** | Single-turn RAG dengan batasan langkah eksekusi maksimal ($N \le 2$). | Multi-agent recursive debate & deep reflection cycles ($N \le 8$). | Setiap siklus penalaran/refleksi menambahkan 1.5 - 3 detik pada total respons time. Latensi P99 melesat dari 2s ke 12s. Biaya komputasi meningkat drastis. |
| **Biaya Token vs Kualitas Konteks** | Context compression agresif, truncation history, dan embedding retrieval kecil. | Full conversational memory injection, few-shot dynamic examples, mega context. | Penghematan biaya hingga 70% pada Pilihan A berisiko menyebabkan *amnesia percakapan*, sedangkan Pilihan B menguras budget API hingga ribuan dolar per hari pada skala enterprise. |

---

## 10. Common Mistakes & Troubleshooting

### 1. Menulis Acceptance Criteria Non-Kuantitatif
* *Kesalahan*: "Sistem agen harus memberikan saran yang relevan dan sopan." (Subjektif, tidak dapat diuji via automated test).
* *Solusi*: Ubah ke metrik terukur: "Agen harus mencapai skor semantic similarity $\ge 0.82$, RAG Context Recall $\ge 0.90$, dan Toxicity Score $= 0$ pada 100 data uji sintetis."

### 2. Ketiadaan Spesifikasi "Circuit Breaker" untuk Tool Loop
* *Kesalahan*: Mengizinkan agen terus mencoba memanggil tool API yang sedang timeout hingga batas execution timeout gateway server tercapai (504 Gateway Timeout).
* *Solusi*: Tentukan NFR: `Max Tool Retries = 2`. Jika gagal, agen wajib mengambil *fallback path*: mengembalikan respons alternatif terdegradasi secara elegan kepada pengguna.

### 3. Mengabaikan "Prompt Injection" pada Kontrak Masukan PRD
* *Kesalahan*: Memperlakukan input pengguna murni sebagai parameter string biasa tanpa sanitasi terstruktur.
* *Solusi*: Tentukan spesifikasi layer *Input Sanitization & Shielding* sebelum pesan diteruskan ke orkestrator agen utama.

---

## 11. Best Practices & Production Checklist

### Pre-Development Sign-Off Checklist (Technical PRD)
- [ ] **Contract Definitions**: Semua antarmuka Tool memiliki JSON Schema lengkap termasuk constraint tipe data, deskripsi semantik, dan contoh valid.
- [ ] **Context Window Budgeting**: Ditentukan batas maksimal token untuk: System Prompt, Few-Shot Injections, Dynamic Context Retrieval, dan Model Output Generation.
- [ ] **Non-Functional Requirements SLA Matrix**:
  - [ ] P50, P90, P99 Latency targets tercantum.
  - [ ] Target akurasi Groundedness/Faithfulness terdefinisi ($\ge X.XX$).
  - [ ] Maximum Hallucination Tolerance Rate terdefinisi ($\le Y\%$).
- [ ] **Deterministic Fallback Routing**: Terdapat diagram alir fallback eksplisit saat model mengalami failure rate tinggi atau API rate limit tercapai.
- [ ] **Safety & Compliance**: Definisi PII masking (nama, nomor telepon, kartu kredit) dispesifikasikan di level gateway sebelum payload mencapai LLM provider eksternal.

---

## 12. Hands-on Practice

Buat dan simpan file implementasi berikut di direktori: `hands-on/m02/`

### File: `hands-on/m02/agent_spec_evaluator.py`
Skrip ini memverifikasi trace eksekusi multi-agent terhadap spesifikasi NFR dan fungsional yang didefinisikan dalam Technical PRD.

```python
import sys
import json
from typing import Dict, Any

# Simulasi Technical PRD Specification Matrix
PRD_SPECIFICATION = {
    "feature_name": "Autonomous Refund Processing Agent",
    "sla": {
        "max_latency_ms": 4000.0,
        "max_token_usage": 2500,
        "min_faithfulness_score": 0.88,
        "allowed_tools": ["verify_order_status", "check_refund_policy", "issue_refund_ledger"]
    }
}

def evaluate_execution_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengevaluasi trace eksekusi model terhadap spesifikasi PRD secara otomatis.
    """
    violations = []
    
    # 1. Evaluasi Latensi
    if trace["metrics"]["latency_ms"] > PRD_SPECIFICATION["sla"]["max_latency_ms"]:
        violations.append(
            f"Latency violation: {trace['metrics']['latency_ms']}ms > {PRD_SPECIFICATION['sla']['max_latency_ms']}ms"
        )
        
    # 2. Evaluasi Token Budget
    if trace["metrics"]["tokens_consumed"] > PRD_SPECIFICATION["sla"]["max_token_usage"]:
        violations.append(
            f"Token budget violation: {trace['metrics']['tokens_consumed']} > {PRD_SPECIFICATION['sla']['max_token_usage']}"
        )
        
    # 3. Evaluasi Kualitas/Faithfulness
    if trace["metrics"]["faithfulness"] < PRD_SPECIFICATION["sla"]["min_faithfulness_score"]:
        violations.append(
            f"Quality SLA violation: Faithfulness {trace['metrics']['faithfulness']} < {PRD_SPECIFICATION['sla']['min_faithfulness_score']}"
        )
        
    # 4. Evaluasi Tool Access Authorization
    for tool in trace["tool_calls"]:
        if tool not in PRD_SPECIFICATION["sla"]["allowed_tools"]:
            violations.append(f"Security Policy violation: Unauthorized tool invocation -> {tool}")

    return {
        "passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations
    }

if __name__ == "__main__":
    # Mock data trace yang dihasilkan oleh sistem Agent saat automated testing
    sample_trace = {
        "trace_id": "tr-agent-9921",
        "tool_calls": ["verify_order_status", "issue_refund_ledger"],
        "metrics": {
            "latency_ms": 3150.0,
            "tokens_consumed": 1820,
            "faithfulness": 0.92
        }
    }

    result = evaluate_execution_trace(sample_trace)
    print("=== HASIL EVALUASI PRD ACCEPTANCE CRITERIA ===")
    print(json.dumps(result, indent=2))
    
    if not result["passed"]:
        sys.exit(1)
    print("Trace memenuhi seluruh kriteria PRD.")
```

### Instruksi Menjalankan Praktikum:
1. Pastikan Python 3.9+ telah terpasang.
2. Navigasi ke direktori hands-on:
   ```bash
   mkdir -p hands-on/m02
   cd hands-on/m02
   ```
3. Simpan kode di atas sebagai `agent_spec_evaluator.py`.
4. Jalankan evaluasi:
   ```bash
   python agent_spec_evaluator.py
   ```
5. Ubah nilai metrik `latency_ms` menjadi `4500.0` dan perhatikan bagaimana script menghasilkan error status code (`sys.exit(1)`), merefleksikan kegagalan Quality Gate pada pipeline CI/CD.

---

## 13. Exercises

### Level: Easy
Ubah `sample_trace` pada skrip praktikum di atas untuk memanggil tool ilegal `"delete_user_database"`. Jalankan skrip dan amati output pelanggaran keamanan yang dihasilkan. Tuliskan analisis Anda mengapa pembatasan akses tool secara deklaratif wajib dituliskan di Tech PRD!

### Level: Medium
Tuliskan spesifikasi User Story dalam format Gherkin-Agentic untuk sebuah agen Customer Service yang menangani keluhan pengiriman barang rusak. Masukkan *Acceptance Criteria* berupa:
- Panggilan tool `lookup_delivery_tracking` dan `create_replacement_ticket`.
- Batasan bahwa token output tidak boleh melebihi 250 token.
- Verifikasi bahwa agen tidak boleh meminta kata sandi nasabah dalam kondisi apa pun.

### Level: Hard
Rancang skema Pydantic komprehensif untuk *Context Management Contract* yang mengatur percakapan antar dua agen: **Researcher Agent** dan **Editor Agent**. Kontrak harus mencakup schema handoff, validasi referensi URL (harus berformat HTTPS), batas maksimum revisi antar agen ($N \le 3$), dan metrik confidence score minimal dari Researcher Agent sebelum diserahkan kepada Editor Agent.

---

## 14. Challenge

**Studi Kasus**: Anda memimpin tim Technical Product Management di bank multinasional. Anda ditugaskan menyusun Technical PRD untuk sistem **Autonomous Loan Origination Agent** yang dapat menyetujui atau menolak pinjaman UMKM hingga nominal Rp 500.000.000 secara otomatis tanpa campur tangan manusia.

**Kondisi Kompleks & Ambigu**:
1. Otoritas Jasa Keuangan (OJK) mewajibkan bahwa setiap penolakan pinjaman harus memiliki *Adverse Action Explanation* yang 100% deterministik dan bebas bias gender/etnis.
2. Latensi inferensi agen tidak boleh melebihi 6 detik per evaluasi aplikasi, meskipun agen harus memverifikasi data ke 3 biro kredit eksternal yang kerap mengalami *network throttling*.
3. Model memiliki kecenderungan halusinasi jika data pembukuan keuangan dari calon debitur berformat PDF tidak teratur.

**Tugas**: Susun dokumen arsitektur spesifikasi fungsional dan teknis yang mencakup:
- Arsitektur fallback deterministik jika biro kredit eksternal mengalami timeout.
- Mekanisme mitigasi halusinasi parsing dokumen finansial.
- Desain *Living Contract* dan *Automated Evaluation Suite* (Evals-as-Code) yang menjamin model tidak melanggar aturan anti-diskriminasi sebelum diizinkan menyentuh cluster produksi.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (Pilihan Ganda)
1. Apa perbedaan mendasar paling kritis antara PRD software deterministik dengan PRD untuk Autonomous Agent?
   - A. PRD Agent tidak membutuhkan User Story.
   - B. PRD Agent harus mengakomodasi ruang status probabilistik dan membatasi perilaku non-deterministik.
   - C. PRD Agent hanya berfokus pada desain antarmuka antarmuka pengguna (UI/UX).
   - D. PRD Agent tidak memerlukan Non-Functional Requirements.
   *Jawaban*: B. Model AI menghasilkan output berbasis probabilitas sehingga PRD wajib mengatur boundary, guardrails, dan toleransi error.

2. Apa yang dimaksud dengan *Token Budgeting* dalam Technical PRD?
   - A. Biaya gaji prompt engineer dalam mata uang lokal.
   - B. Alokasi batas maksimum token untuk konteks input, reasoning, dan output guna mencegah lonjakan latensi dan biaya komputasi tak terkendali.
   - C. Total kuota API yang dibeli dari cloud provider untuk jangka waktu satu tahun.
   - D. Jumlah kata maksimum yang boleh ditulis oleh Product Manager di dalam dokumen spesifikasi.
   *Jawaban*: B. Token budgeting mengendalikan biaya operasional dan menjaga model tetap berada di dalam latensi yang dapat diterima.

3. Dalam pendekatan *Evals-as-Code*, kriteria penerimaan (Acceptance Criteria) sebuah PRD diubah menjadi:
   - A. Diagram alir manual di aplikasi whiteboard.
   - B. Dokumen PDF statis yang ditandatangani oleh pemangku kepentingan.
   - C. Skrip pengujian otomatis dan benchmark data yang dijalankan di pipeline CI/CD.
   - D. Notulen rapat mingguan tim pengembang.
   *Jawaban*: C. Evals-as-code mengubah kriteria subjektif menjadi metrik terukur yang dapat dieksekusi oleh mesin.

4. Manakah komponen yang TIDAK relevan saat mendefinisikan *Tool Calling Contract* untuk sebuah Agent?
   - A. JSON Schema dari parameter input tool.
   - B. Deskripsi semantik mengenai fungsi tool untuk memandu pemahaman LLM.
   - C. Warna tombol UI yang akan merender hasil keluaran tool di aplikasi client.
   - D. Prosedur penanganan ketika tool mengalami status error/timeout.
   *Jawaban*: C. Spesifikasi antarmuka visual UI berada di luar lingkup fungsional kontrak semantic tool calling agen.

5. Apa tujuan utama dari penentuan *Groundedness / Faithfulness Score* pada sistem berbasis RAG?
   - A. Mempercepat rendering font pada browser.
   - B. Memastikan bahwa jawaban yang dihasilkan agen didasarkan murni pada dokumen rujukan yang diberikan dan bukan hasil halusinasi bebas.
   - C. Menghitung jumlah klik mouse pengguna pada halaman web.
   - D. Mengubah teks input menjadi format audio secara otomatis.
   *Jawaban*: B. Faithfulness mengukur sejauh mana klaim teks model terjangkar (*grounded*) pada konteks fakta yang disediakan.

---

### Bagian 2: Intermediate (Pilihan Ganda Berbobot)
6. Sebuah tim engineering melaporkan bahwa latency P99 sistem Agent mereka melonjak menjadi 18 detik karena model sering terjebak dalam *infinite reasoning loop*. Kebijakan spesifikasi teknis mana yang harus dimasukkan TPM ke dalam PRD untuk mengatasi masalah ini?
   - A. Mengganti model LLM dengan model yang parameter ukurannya 10 kali lebih besar.
   - B. Menetapkan batasan eksplisit `Maximum Reasoning Steps` ($N \le 4$) dan menerapkan `Execution Timeout Hard-Gate` pada level orkestrator.
   - C. Menghapus semua tools sehingga agen hanya membalas percakapan dasar.
   - D. Memperbesar memori RAM pada server database utama.
   *Jawaban*: B. Membatasi kedalaman iterasi agen dan menetapkan batas waktu hard-gate menghentikan siklus reasoning tak berujung secara instan.

7. Mengapa penggunaan format schema data terstruktur (seperti Pydantic / JSON Schema) sangat diwajibkan dalam komunikasi antar Autonomous Sub-Agents?
   - A. Karena LLM tidak bisa membaca teks alami (*natural language*).
   - B. Agar payload antarmuka dapat divalidasi secara deterministik sebelum memicu sub-proses kritikal berikutnya.
   - C. Karena format teks alami lebih mahal 100 kali lipat dibanding format JSON.
   - D. Untuk mencegah agen menggunakan protokol HTTPS.
   *Jawaban*: B. Schema parsing bertindak sebagai validasi deterministik, menjamin tidak ada parameter hilang atau rusak akibat variabilitas output bahasa alami model.

8. Pada arsitektur Autonomous Multi-Agent, apa fungsi dari *System Prompt Versioning* dalam hubungannya dengan Technical PRD?
   - A. Menjaga riwayat teks prompt agar selaras dengan versi Acceptance Criteria dan dataset evaluasi pada setiap rilis sistem.
   - B. Mempercepat proses kompilasi kode bahasa C++.
   - C. Menghapus prompt lama secara permanen setiap kali terjadi perubahan kode.
   - D. Mencegah engineer membaca kembali konfigurasi prompt masa lalu.
   *Jawaban*: A. System prompt adalah bagian dari kode logika pada AI; versioning menjamin traceabilitas antara performa model, kontrak PRD, dan hasil benchmark.

9. Manakah indikator Non-Functional Requirements yang paling tepat untuk menguji ketahanan agent terhadap serangan manipulasi input?
   - A. Prompt Injection Defense Success Rate $\ge 99.5\%$.
   - B. Response Time P50 $< 200\text{ms}$.
   - C. Maximum Disk IOPS $> 1000$.
   - D. CPU Utilization Rate $< 40\%$.
   *Jawaban*: A. Metrik pertahanan terhadap prompt injection secara spesifik mengukur keamanan input boundary agen dari eksploitasi jailbreak.

10. Ketika mengonstruksi User Story untuk agen pemroses transaksi keuangan, pendekatan terbaik menangani eksekusi transaksi yang bernilai tinggi adalah:
    - A. Membiarkan agen mengeksekusi langsung secara mandiri berapapun nominalnya agar proses cepat.
    - B. Memasukkan pola *Human-in-the-Loop (HITL)* approval gate ke dalam Acceptance Criteria untuk transaksi di atas batas nominal tertentu.
    - C. Melarang agen memproses transaksi sama sekali.
    - D. Menyerahkan sepenuhnya keputusan verifikasi transaksi kepada model eksternal tanpa pengawasan log.
    *Jawaban*: B. Human-in-the-loop adalah mitigasi risiko esensial untuk memverifikasi tindakan agen otonom pada transaksi berdampak finansial tinggi.

---

### Bagian 3: Skenario Kasus Produksi
11. **Skenario Kasus 1**: Sistem Customer Service Agent Anda di production tiba-tiba mengalami lonjakan tagihan token sebesar 400% dalam waktu 24 jam setelah rilis fitur baru, namun jumlah pengguna aktif harian (*Daily Active Users*) stagnan.
    - *Analisis Masalah*: Apa yang kemungkinan terlewatkan dalam dokumen Technical PRD fitur tersebut?
    - *Rekomendasi Tindakan TPM*: Jelaskan spesifikasi NFR dan guardrail yang harus segera diimplementasikan untuk menghentikan pendarahan biaya ini!
    *Jawaban Evaluasi*: Tim melewatkan spesifikasi *Token Budget Cap per Session* dan *Context Window Pruning Policy*. Agen kemungkinan membawa seluruh riwayat chat tanpa batas (unbounded context history) atau terjebak dalam loop percakapan berulang. Tindakan: Tetapkan batasan `Max Input Context Window = 4000 tokens`, terapkan sliding-window memory, dan pasang circuit-breaker yang memutus sesi jika satu pengguna mengonsumsi lebih dari batas token harian tertentu.

12. **Skenario Kasus 2**: Tim Data Science mengklaim model Agent baru mereka memiliki akurasi "98% Luar Biasa" berdasarkan evaluasi internal mereka. Namun saat diuji coba pada segmen nasabah terbatas, tim operasional menemukan bahwa agen sering menyetujui klaim asuransi fiktif.
    - *Analisis Masalah*: Di mana letak kegagalan dalam pendefinisian kriteria penerimaan PRD?
    - *Rekomendasi Tindakan TPM*: Bagaimana merestrukturisasi *Definition of Done* (DoD) pada PRD agar insiden serupa tidak terulang?
    *Jawaban Evaluasi*: Metrik "akurasi umum" mengaburkan performa pada skenario kritis (*false positive rate pada fraud detection*). DoD pada PRD harus direstrukturisasi dengan mewajibkan dataset evaluasi terpisah (*Adversarial & Edge-case Golden Dataset*). Spesifikasi harus mencakup batas spesifik: `False Acceptance Rate (FAR) == 0%` untuk klaim tanpa dokumen otentik, diuji melalui eval suite otomatis independen di luar pipeline tim data science.

13. **Skenario Kasus 3**: Agen asisten medis internal dirancang untuk membantu perawat merangkum rekam medis pasien. Terkadang, agen secara acak memasukkan rincian nama obat yang tidak pernah dikonsumsi pasien ke dalam rangkuman akhir.
    - *Analisis Masalah*: Bentuk kegagalan apa ini dalam taksonomi AI dan mengapa sangat berbahaya?
    - *Rekomendasi Tindakan TPM*: Tuliskan klausul *Acceptance Criteria* dan arsitektur pengujian teknis yang wajib disertakan dalam Tech PRD untuk mengeliminasi anomali ini!
    *Jawaban Evaluasi*: Ini adalah *Extrinsic Hallucination* yang berisiko malpraktik medis fatal. Klausul PRD wajib menetapkan: "Rangkuman medis akhir harus memiliki skor Faithfulness = 1.00 (Zero Hallucination Tolerance) terhadap teks sumber." Solusi teknis: Implementasikan algoritma entity matching berbasis deterministik (Named Entity Recognition - NER) yang memvalidasi bahwa setiap entitas obat dalam output teks benar-benar terdapat pada teks input sebelum teks ditampilkan kepada perawat.

---

## 16. Summary

Merancang Technical Product Requirement Document (PRD) dan arsitektur spesifikasi untuk *Autonomous Agent & Data-driven AI Systems* menuntut transformasi pola pikir fundamental: dari manajemen perangkat lunak deterministik menuju **rekayasa batas sistem probabilistik (*probabilistic boundary engineering*)**.

Product Manager kelas enterprise tidak cukup hanya mengandalkan deskripsi naratif fungsional. PM wajib menguasai:
1. **Contract-First Specifications**: Mendefinisikan schema input, schema output, dan batasan alat (*tools*) secara ketat dan programatis menggunakan format baku (JSON Schema / Pydantic).
2. **Deterministic-to-Stochastic Guardrails**: Menyeimbangkan otonomi agen dengan hard-gates deterministik (safety checks, policy enforcement, regex filters, circuit-breakers).
3. **Evals-as-Code Implementation**: Mentransformasikan User Stories dan Acceptance Criteria subjektif menjadi rangkaian uji kuantitatif otomatis (Faithfulness, Latency P99, Token Consumption Budget) yang terintegrasi secara mulus ke dalam pipeline CI/CD rilis model enterprise.