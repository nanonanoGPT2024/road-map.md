# BAB 06: Directional Stimulus, Critique, & Self-Refinement
## Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang dan Mengimplementasikan Directional Stimulus Prompting (DSP)**: Mengabstraksikan dan menyuntikkan *semantic hints* atau *policy vectors* secara dinamis ke dalam execution prompt LLM guna mengontrol arah pembentukan token secara granular tanpa fine-tuning.
2. **Membangun Stateful Critique-Refine Loop Engine**: Mengembangkan arsitektur iteratif yang memisahkan peran *Generator*, *Critic*, dan *Refiner* menggunakan model berbasis state machine dengan convergence criteria deterministik.
3. **Mengatasi Degenerasi Feedback & Hallucinated Correction**: Menerapkan validasi berbasis rule-engine hibrida dan ambang batas leksikal/semantik untuk mencegah *drift* logika atau regresi performa antargenerasi.
4. **Mengoptimalkan Metrik Produksi Multi-Dimensi**: Menyeimbangkan *latency penalty*, biaya token per iterasi, dan *quality yield rate* pada sistem autonomous refinement di lingkungan enterprise dengan throughput tinggi.

---

### 2. Prerequisite

Sebelum menempuh modul ini, engineer diwajibkan telah menguasai:
* **Deep Prompt Engineering Fundamentals**: Pemahaman solid mengenai Few-Shot In-Context Learning, Chain-of-Thought (CoT), dan ReAct architecture.
* **Modern Python Concurrency**: Penguasaan mendalam atas `asyncio`, asynchronous context managers, generator, dan struktur antrean non-blocking.
* **Pydantic V2 & Structured Outputs**: Skema validasi ketat, custom validators, dan serialization protocol untuk parsing LLM response.
* **Vector Mathematics & Embeddings**: Kalkulasi cosine similarity, semantic drift measurement, dan penggunaan embedding model untuk memverifikasi konvergensi teks.

---

### 3. Concept & Internal Architecture (Mendalam)

Implementasi enterprise dari prompt-driven optimization bertransisi dari *single-shot heuristic* menuju *closed-loop control system*. Terdapat tiga pilar arsitektur utama di dalam modul ini:

```
+-------------------------------------------------------------------------+
|                  CLOSED-LOOP SELF-REFINEMENT ENGINE                     |
|                                                                         |
|  [Input Task] ---> [Policy/Stimulus Selector]                           |
|                            |                                            |
|                            v (Directional Stimulus: Keywords/Hints)     |
|                 +---------------------+                                 |
|                 |  GENERATOR AGENT    |<---------------+                |
|                 +---------------------+                |                |
|                            |                           |                |
|                            v (Draft Artifact)          |                |
|                 +---------------------+                | (Feedback &    |
|                 |    CRITIC AGENT     |                |  History)      |
|                 +---------------------+                |                |
|                   |                 |                  |                |
|     (Score >= tau)|                 | (Score < tau)    |                |
|                   v                 v                  |                |
|            [HALT: EMIT]      +---------------------+   |                |
|                              |    REFINER AGENT    |---+                |
|                              +---------------------+                    |
|                                                                         |
+-------------------------------------------------------------------------+
```

#### Directional Stimulus Prompting (DSP)
DSP memisahkan proses reasoning menjadi dua komponen:
1. **Stimulus Generator (Small LM / Policy Heuristic)**: Mengidentifikasi *anchor points* spesifik (misal: pasal regulasi, kata kunci diagnostik, metrik SLA spesifik) dari input mentah.
2. **Task Model (Large Primary LM)**: Mengonsumsi input asli bersamaan dengan directional stimulus sebagai panduan eksplisit.

Secara matematis, alih-alih memodelkan probabilitas $P(Y \mid X)$, DSP memodelkan:
$$P(Y \mid X, S) \quad \text{di mana} \quad S \sim P_{\text{stimulus}}(S \mid X)$$
$S$ bertindak sebagai pengkondisi tambahan yang membatasi search space token LLM secara signifikan ke arah distribusi ruang solusi yang ditargetkan tanpa merusak fleksibilitas instruksi dasar.

#### The Critique-Refine Engine
Siklus ini merupakan discrete dynamical system:
* Inisialisasi: $Y_0 \sim \text{Gen}(X, S)$
* Evaluasi: $C_t, M_t = \text{Critic}(X, Y_t)$ di mana $C_t$ adalah critique tekstual, $M_t \in [0, 1]$ adalah skor kualitas multivariat.
* Kondisi Terminasi: Berhenti jika $M_t \ge \tau$ (threshold) atau $t \ge T_{\max}$ (iterasi batas) atau $|M_t - M_{t-1}| < \epsilon$ (plateau/konvergensi semu).
* Pembaruan: $Y_{t+1} \sim \text{Refiner}(X, Y_t, C_t)$

#### Reflexion Architecture
Pada implementasi lanjutan (*Reflexion*), critic tidak hanya memvalidasi output lokal terhadap prompt, tetapi juga memelihara *episodic memory buffer* $M_{\text{epi}} = \{(Y_0, C_0), (Y_1, C_1), \dots, (Y_t, C_t)\}$. Memory ini diinjeksi ke context window generasi $t+1$ untuk memitigasi *oscillatory behavior* (kondisi di mana refiner memperbaiki error A namun memunculkan kembali error B yang telah terselesaikan pada iterasi sebelumnya).

---

### 4. Why & What

| Dimensi | Single-Pass Prompting (Direct Generation) | Self-Refine / Directional Stimulus Architecture |
| :--- | :--- | :--- |
| **Akurasi Output Kompleks** | Rendah-Menengah (~50-65% pass rate pada constraint ketat). | Tinggi (>90% compliance pass rate via iterative correction). |
| **Predictability & Kontrol** | Rendah; rentan halusinasi struktural dan non-compliance. | Sangat Tinggi; dipandu oleh directional stimuli eksplisit & invariant validation. |
| **Resource Efficiency** | $1\times$ LLM invocation cost & minimum latency (~1s). | $N\times$ invocations ($2N+1$ calls); amortisasi latency lebih tinggi (3s - 15s). |
| **Kebutuhan Domain Data** | Memerlukan few-shot bertumpuk di prompt utama (bloated context). | Pemisahan context: Domain rules dialokasikan terpisah pada Critic dan Stimulus. |

* **What**: Suatu framework software engineering yang mengorkestrasi interaksi bertahap antar-instance LLM (atau instance tunggal dengan prompt roles yang terisolasi) untuk menghasilkan, mengkritisi secara deterministik/semantik, dan merevisi artefak sampai memenuhi acceptance criteria yang didefinisikan secara matematis.
* **Why**: LLM adalah sistem stokastik autoregresif. Sekali model membuat penyimpangan token (*early drift*) pada *prefix token sequences*, token-token berikutnya akan mengakumulasi bias kesalahan tersebut (*snowballing error*). Closed-loop self-refinement menginterupsi lintasan inferensi yang salah tersebut sebelum artefak dikembalikan ke downstream system.

---

### 5. How (Workflow Detail)

1. **Phase 1: Input Ingestion & Invariant Extraction**
   * Request masuk melalui API Gateway, lolos skema input validation Pydantic.
   * Parameter operasional diisolasi: *Max Retries*, *Strictness Level*, *Convergence Threshold ($\tau$)*.

2. **Phase 2: Directional Stimulus Computation**
   * Rule-based engine mengekstraksi metadata penting, atau model kecil (e.g., Llama-3-8B / fine-tuned SLM) mengekstrak *Stimulus Signals* (seperti token wajib, dependensi API, regulasi relevan).

3. **Phase 3: Generation ($Y_t$)**
   * Task model memproses prompt utama yang digabungkan secara dinamis dengan stimulus.

4. **Phase 4: Critique Execution ($C_t, M_t$)**
   * Critic Agent mengeksekusi dua jenis evaluasi:
     * *Deterministic Evaluation*: Python AST parsing, JSON schema check, regex validation, atau linters (misal: `ruff`, `mypy`).
     * *Semantic Evaluation*: LLM Critic yang menilai *coherence*, *tone*, *business logic compliance*, dan *hallucination check*.
   * Mengembalikan structured object berisi skor numerik dan array instruksi perbaikan konkret.

5. **Phase 5: Decision Logic & Convergence Gate**
   * Jika skor $M_t \ge \tau$ DAN deterministic checks lulus: Route ke final output emitter.
   * Jika $t \ge T_{\max}$: Trigger fallback protocol (circuit breaker/dead-letter queue).
   * Jika skor tidak berubah signifikan selama 2 iterasi berurutan: Force exit untuk menghindari loop tak berujung.

6. **Phase 6: Refinement ($Y_{t+1}$)**
   * Refiner menerima: Original Task, Previous Draft ($Y_t$), Detailed Critique ($C_t$), dan Episodic Error Log.
   * Menghasilkan draft baru. Loop kembali ke Phase 4.

---

### 6. Analogy & Diagram ASCII

#### Analogi Dunia Nyata
Bayangkan penerbitan buku teknis enterprise.
* **Generator** adalah Technical Writer yang menulis draf pertama secara cepat berdasarkan *outline* kata kunci dari Technical Lead (**Directional Stimulus**).
* **Critic** adalah Principal QA / Senior Editor yang membaca draf sambil memegang *style guide* dan *compiler*. Dia menolak draf tersebut bukan hanya dengan komentar "tulisan ini jelek", melainkan "Seksi 3.2 memiliki syntax error pada baris 10, dan pembahasannya melewatkan aspek thread-safety".
* **Refiner** adalah Technical Writer yang kembali ke meja kerja dengan hanya berfokus pada catatan merah dari editor tersebut, memperbaiki bug, dan mengirimkannya kembali ke siklus review hingga siap naik cetak.

#### Diagram Interaksi State Machine
```
   +--------------------------------------------------------+
   |                  CLIENT REQUEST                        |
   +--------------------------------------------------------+
                               |
                               v
                     +--------------------+
                     | Stimulus Extractor |
                     +--------------------+
                               |
                   Stimulus: S |
                               v
+------------------->+--------------------+
|                    |     Generator      |<--------------------+
|                    +--------------------+                     |
|                              |                                |
|                     Draft Yt |                                |
|                              v                                |
|                    +--------------------+                     |
|                    | Deterministic QA   |---[Fail: Hard Bug]--+
|                    +--------------------+                     | (Syntactic Fix)
|                              |                                |
|                              | [Pass: Syntactic Valid]        |
|                              v                                |
|                    +--------------------+                     |
|                    |  Semantic Critic   |                     |
|                    +--------------------+                     |
|                              |                                |
|                    Feedback: (Ct, Mt)                         |
|                              v                                |
|                    +--------------------+                     |
|                    |  Convergence Gate  |                     |
|                    +--------------------+                     |
|                      /                \                       |
|        [Mt >= tau]  /                  \ [Mt < tau & t < Tmax]|
|                    v                    v                     |
|          +------------------+   +------------------+          |
|          | Output Serializer|   | Refiner (Delta)  |----------+
|          +------------------+   +------------------+  New Prompt:
|                    |                                  (Yt, Ct, Ht)
|                    v
|             FINAL RESPONSE
+---------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Simple Example (Konseptual Minimalis)

```python
# Minimal directional stimulus pattern
prompt_base = "Tuliskan ringkasan kebijakan privasi data pengguna."
directional_stimulus = "STIMULUS WAJIB: Fokuskan pada GDPR Pasal 17 (Right to be Forgotten) dan enkripsi rest/transit."

refined_prompt = f"{prompt_base}\n\n[Directional Directive]\n{directional_stimulus}"
# Output LLM akan langsung terarah pada GDPR & Enkripsi tanpa deviasi.
```

#### Practical Example (Industrial-Grade Production Implementation)

Di bawah ini adalah sistem orkestrasi *Self-Correction Code Generation Pipeline* yang menggabungkan:
1. Directional Stimulus (Ekstraksi interface constraints)
2. Pydantic-based critique model
3. Deterministic Python AST validation
4. Async-driven execution loop dengan circuit breaker

```python
"""
Enterprise Self-Refinement Code Engine
Author: Core AI Platform Architecture Team
"""

import ast
import asyncio
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, Field
import httpx


# ==========================================
# 1. DOMAIN SCHEMAS
# ==========================================

class CritiqueReport(BaseModel):
    is_acceptable: bool = Field(description="Apakah output memenuhi seluruh kriteria.")
    quality_score: float = Field(ge=0.0, le=1.0, description="Skor kelayakan artefak dari 0.0 sampai 1.0.")
    syntax_valid: bool = Field(description="Apakah kode lolos parsing AST secara deterministik.")
    structural_critique: List[str] = Field(default_factory=list, description="Daftar kelemahan arsitektur/logika.")
    actionable_refinements: List[str] = Field(default_factory=list, description="Instruksi spesifik untuk refiner.")

class GenerationResult(BaseModel):
    code: str
    iterations_used: int
    final_score: float
    history: List[Dict[str, Any]]


# ==========================================
# 2. LLM CLIENT WRAPPER (MOCK / ENTERPRISE ADAPTER)
# ==========================================

class LLMExecutionGateway:
    """Gateway client untuk berinteraksi dengan API Model Foundation via async IO."""
    
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=30.0)

    async def invoke(self, system_instruction: str, prompt: str) -> str:
        # Dalam implementasi riil, ini mengarah ke vLLM, OpenAI, atau Bedrock endpoint.
        # Snippet simulasi untuk validasi logic testing:
        await asyncio.sleep(0.1) # Simulasi network I/O
        
        # Contoh output deterministic fallback jika running mock test:
        if "CRITIC" in system_instruction:
            return """{
                "is_acceptable": true,
                "quality_score": 0.95,
                "syntax_valid": true,
                "structural_critique": [],
                "actionable_refinements": []
            }"""
        return """def transfer_funds(source: str, target: str, amount: float) -> bool:
    if amount <= 0:
        raise ValueError('Invalid amount')
    # Execution transfer logic
    return True"""


# ==========================================
# 3. CORE ENGINE ARSITEKTUR
# ==========================================

class SelfRefiningCodeGenerator:
    def __init__(
        self, 
        gateway: LLMExecutionGateway,
        max_iterations: int = 3,
        score_threshold: float = 0.90
    ):
        self.gateway = gateway
        self.max_iterations = max_iterations
        self.score_threshold = score_threshold

    def _extract_directional_stimulus(self, task_spec: str) -> str:
        """
        Directional Stimulus Generator (DSP):
        Mengekstraksi invariant and key constraint secara deterministik/heuristik.
        """
        stimuli = []
        if "transfer" in task_spec.lower():
            stimuli.append("Gunakan validasi saldo negatif, idempotency key handling, dan explicit typing.")
        if "database" in task_spec.lower():
            stimuli.append("Wajib gunakan transactional isolation block (ACID compliant).")
        return " | ".join(stimuli) if stimuli else "Patuhi standar PEP 8 dan runtime boundary checks."

    def _run_deterministic_lint(self, python_code: str) -> Tuple[bool, Optional[str]]:
        """Static verification: parsing AST untuk eliminasi syntax issue tanpa LLM cost."""
        try:
            # Hilangkan markdown wrappers bila ada
            clean_code = python_code.strip()
            if clean_code.startswith("```python"):
                clean_code = clean_code.removeprefix("```python")
            if clean_code.endswith("```"):
                clean_code = clean_code.removesuffix("```")
            ast.parse(clean_code)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError line {e.lineno}: {e.msg}"

    async def _evaluate_draft(self, task: str, code: str) -> CritiqueReport:
        """Critic Agent: Menggabungkan AST check + Semantic LLM Inspection."""
        is_ast_valid, ast_error = self._run_deterministic_lint(code)
        
        if not is_ast_valid:
            return CritiqueReport(
                is_acceptable=False,
                quality_score=0.1,
                syntax_valid=False,
                structural_critique=[f"Deterministic parse failure: {ast_error}"],
                actionable_refinements=["Perbaiki struktur sintaks dasar agar kode dapat diparsing interpreter."]
            )

        critic_system_prompt = (
            "Anda adalah Senior Staff Software Engineer QA. Evaluasi kode Python berikut "
            "terhadap spesifikasi task. Berikan feedback dalam format JSON murni "
            "yang mematuhi skema CritiqueReport."
        )
        critic_user_prompt = f"TASK:\n{task}\n\nIMPLEMENTASI:\n{code}"
        
        raw_response = await self.gateway.invoke(critic_system_prompt, critic_user_prompt)
        
        try:
            critique = CritiqueReport.model_validate_json(raw_response)
        except Exception:
            # Fallback jika model gagal format JSON murni
            critique = CritiqueReport(
                is_acceptable=False,
                quality_score=0.5,
                syntax_valid=True,
                structural_critique=["Critic response failed parsing."],
                actionable_refinements=["Regenerate clean structured code."]
            )
        return critique

    async def execute(self, user_task: str) -> GenerationResult:
        stimulus = self._extract_directional_stimulus(user_task)
        history: List[Dict[str, Any]] = []

        current_prompt = (
            f"Tuliskan fungsi Python untuk spesifikasi berikut:\n{user_task}\n"
            f"[DIRECTIONAL STIMULUS: {stimulus}]"
        )
        current_code = ""
        current_score = 0.0

        for iteration in range(1, self.max_iterations + 1):
            # Step A: Generation / Refinement
            system_role = "Anda adalah Lead Python Engineer. Tuliskan hanya kode production-grade tanpa intro/outro."
            current_code = await self.gateway.invoke(system_role, current_prompt)

            # Step B: Critique
            critique = await self._evaluate_draft(user_task, current_code)
            current_score = critique.quality_score
            
            history.append({
                "iteration": iteration,
                "code_snapshot": current_code,
                "score": current_score,
                "critique": critique.model_dump()
            })

            # Step C: Convergence Gate
            if critique.is_acceptable and current_score >= self.score_threshold:
                return GenerationResult(
                    code=current_code,
                    iterations_used=iteration,
                    final_score=current_score,
                    history=history
                )

            # Step D: Construct Refinement Prompt with Episodic Memory
            refinement_instructions = "\n".join(f"- {item}" for item in critique.actionable_refinements)
            structural_issues = "\n".join(f"- {item}" for item in critique.structural_critique)

            current_prompt = (
                f"Tugas Sebelumnya: {user_task}\n\n"
                f"Draf Sebelumnya:\n```python\n{current_code}\n```\n\n"
                f"Kritik dan Masalah Terdeteksi:\n{structural_issues}\n\n"
                f"Instruksi Perbaikan Mandiri:\n{refinement_instructions}\n\n"
                f"Perbaiki seluruh masalah di atas. Tulis ulang kode secara lengkap dan stabil."
            )

        # Jika mencapai batas maksimum tanpa convergence sempurna, kembalikan draf terakhir
        return GenerationResult(
            code=current_code,
            iterations_used=self.max_iterations,
            final_score=current_score,
            history=history
        )


# ==========================================
# 4. RUNTIME VERIFICATION
# ==========================================

async def main():
    gateway = LLMExecutionGateway(api_key="mock-key", endpoint="https://api.internal/v1")
    engine = SelfRefiningCodeGenerator(gateway=gateway, max_iterations=3, score_threshold=0.85)
    
    spec = "Buat sistem payment transfer antar rekening bank dengan idempotency key dan audit trail."
    result = await engine.execute(spec)
    
    print(f"Convergence tercapai dalam {result.iterations_used} iterasi.")
    print(f"Final Score: {result.final_score}")
    print(f"Generated Code:\n{result.code}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: Automated Anti-Money Laundering (AML) Narrative Generator di Institusi Finansial Tier-1
* **Latar Belakang**: Bank internasional memproses 50.000 transaksi mencurigakan per hari yang memerlukan *Suspicious Activity Report (SAR)* narrative untuk dikirim ke regulator. Draf narasi yang dibuat secara naive (single-shot prompt) memiliki reject rate 34% dari compliance officers karena tidak menyertakan identifikasi regulasi (FinCEN requirements), kurang bukti runut, atau over-generalization.
* **Solusi**:
  1. **Directional Stimulus Engine**: Rule engine menganalisis transaction log dan memunculkan *stimulus bundle*: Red Flag IDs, pasal regulasi relevan (misal: "31 CFR 1020.320"), mandatory chronological anchor points, dan missing profile indicators.
  2. **Critique-Refinement Agent Loop**:
     * Agent 1 (Generator): Menulis draf narasi kasus berdasarkan transaksi dan stimulus.
     * Agent 2 (Compliance Critic): Mengaudit kelengkapan narasi terhadap 12 checklist legal compliance kaku via JSON. Jika poin krusial terlewat, output ditolak dengan detail deviasi regulasi.
     * Agent 3 (Refiner): Memperbaiki narasi tanpa mengubah data numerik faktual transaksi (semantic anchoring).
* **Hasil**:
  * Reject rate narasi oleh tim compliance manusia turun dari 34% ke **2.1%**.
  * Waktu audit per kasus berkurang dari 45 menit menjadi **4 menit**.
  * Total throughput SAR meningkat hingga 750% tanpa penambahan headcount compliance officer.

---

### 9. Trade-offs (Performance, Latency, Scalability, Cost)

```
                 [Quality / Convergence]
                         /\
                        /  \
                       /    \
                      /      \
  [Latency Overhead] /________\ [Token Financial Cost]
```

1. **Latency Overhead**:
   * *Trade-off*: Setiap iterasi Critique-Refine menambahkan minimum 2 call LLM ($1 \times \text{Critic} + 1 \times \text{Refiner}$).
   * *Mitigasi*: Gunakan *speculative early exit* dan evaluasi deterministik terlebih dahulu (AST, Regex, Linters) sebelum memanggil LLM Critic.
2. **Token Financial Cost**:
   * *Trade-off*: Memory history yang diinjeksi pada setiap refinement cycle mengakumulasi input context size ($O(N^2)$ token usage untuk $N$ iterasi).
   * *Mitigasi*: Kompresi history. Jangan kirim draf intermediate lengkap terdahulu; hanya simpan `Diff / Patch summary` dan draf terbaru ($Y_t$).
3. **Quality Oscillation vs. Determinism**:
   * *Trade-off*: Refiner dapat mengalami *drift* (memperbaiki bug A namun merusak fitur B yang sudah benar pada iterasi sebelumnya).
   * *Mitigasi*: Pertahankan `Assertion Memory Buffer` di mana invariant yang telah berstatus *PASS* dikunci dan diuji ulang di setiap iterasi.

---

### 10. Common Mistakes & Troubleshooting

#### 1. The Infinite Refinement Trap
* **Gejala**: Generator dan Critic terjebak dalam *oscillating feedback loop* (misal: Critic meminta ekspansi kode, lalu iterasi berikutnya Critic mengeluh kode terlalu bertele-tele).
* **Root Cause**: Kriteria Critic bersifat subjektif atau ambang batas skor tidak konvergen.
* **Troubleshooting**: Terapkan *Strict Convergence Damping*. Jika delta skor $|M_t - M_{t-1}| \le 0.05$ selama dua step berturut-turut, paksa terminasi dan ambil skor tertinggi sepanjang history, bukan draft terakhir.

#### 2. Hallucinated Critic Syndrome
* **Gejala**: Critic menemukan kesalahan sintaksis atau logis yang sebenarnya tidak ada pada draf artefak.
* **Root Cause**: Prompt Critic terlalu permisif atau context window critic terkontaminasi asumsi eksternal.
* **Troubleshooting**: Selalu jalankan *deterministic compiler/linter check* terlebih dahulu. Jangan tanyakan LLM Critic: "Apakah sintaksis ini benar?", melainkan parsing menggunakan engine bahasa natively (e.g., `ast.parse()` untuk Python, `tsc` untuk TypeScript, `json.loads` untuk JSON). Gunakan LLM Critic khusus untuk penilaian semantik tingkat tinggi.

#### 3. Directional Stimulus Dilution
* **Gejala**: Model mengabaikan stimulus yang diberikan dan kembali ke format generic fallback.
* **Root Cause**: Stimulus tenggelam di tengah tumpukan instruction context yang terlalu panjang (*Lost in the Middle phenomenon*).
* **Troubleshooting**: Posisikan Directional Stimulus di akhir prompt (recency bias utilization) atau format dalam structural delimiter khusus (misal: `<STIMULUS_ANCHOR> ... </STIMULUS_ANCHOR>`).

---

### 11. Best Practices (Production Checklist)

- [ ] **Deterministic First Gate**: Semua validasi struktural (schema, syntax, formatting) dievaluasi dengan kode compiled lokal sebelum LLM Critic dipanggil.
- [ ] **Critique Structured Output Enforcement**: Response Critic **wajib** menggunakan strict JSON schema (Pydantic / OpenAI structured output) guna mempermudah parsing programatik.
- [ ] **Strict Iteration Hard Ceiling**: Mengeset `max_iterations` secara rigid (rekomendasi: 2 hingga 3 iterasi; lebih dari 3 iterasi biasanya menunjukkan diminishing return dramatis).
- [ ] **Episodic Delta Memory**: Hanya menyuntikkan delta koreksi ke prompt refiner, hindari memasukkan raw chat history penuh dari iterasi sebelumnya.
- [ ] **Idempotent Fallback Handler**: Jika sistem gagal mencapai convergence threshold hingga step batas akhir, fallback terarah (mengembalikan state terbaik atau eskalasi ke human-in-the-loop queue) harus dipicu secara otomatis tanpa crash runtime.
- [ ] **Cost-Aware Telemetry**: Setiap cycle emit OpenTelemetry span mencakup `generation_tokens`, `critique_tokens`, `refinement_iteration_count`, dan `delta_quality_score`.

---

### 12. Hands-on Practice

Buka direktori repositori Anda dan selesaikan skenario pada modul ini:

#### Task Setup
Simpan seluruh artefak praktikum pada folder: `hands-on/m02/`

#### File: `hands-on/m02/test_convergence_engine.py`
Buat engine pengoreksi penulisan SQL Analytics Query otomatis dengan kriteria:
1. Menghasilkan valid Snowflake SQL dialect.
2. Memiliki Directional Stimulus untuk menggunakan `QUALIFY ROW_NUMBER() OVER (...)` alih-alih subquery redundan.
3. Kritik deterministik menggunakan sqlglot library untuk memverifikasi validitas parser SQL.
4. LLM Critic mengevaluasi efisiensi join dan compliance index usage.

```bash
# Direktori eksekusi
mkdir -p hands-on/m02
cd hands-on/m02

# Install dependensi
pip install pydantic httpx sqlglot pytest

# Jalankan script pengujian konvergensi
pytest test_convergence_engine.py -v
```

---

### 13. Exercise

#### Level Easy
Tuliskan directional stimulus generator sederhana berbasis dictionary keyword matching yang menerima input problem domain ("API Authentication") dan menyuntikkan 3 stimulus wajib terkait enkripsi (misal: "PBKDF2", "Salt", "Constant Time Comparison").

#### Level Medium
Buat sebuah Critic Agent Pydantic schema yang memvalidasi draf REST API Contract (format YAML/OpenAPI 3.0). Critic harus memisahkan feedback menjadi:
1. `breaking_changes` (List[str])
2. `security_defects` (List[str])
3. `documentation_clarity_score` (Float 0 - 1)
Implementasikan logic yang langsung membatalkan loop (halt) jika `breaking_changes` tidak kosong.

#### Level Hard
Rancang dan implementasikan class `ReflexionMemoryBuffer` di Python. Class ini harus mampu menyimpan `(Action, Output, Critique)` tuples, menghitung semantic cosine similarity antargenerasi menggunakan local embedding API, dan memangkas entri terlama jika memory melebihi context budget 1500 token secara cerdas (*utility-based eviction*).

---

### 14. Challenge

**Skenario**: Anda adalah Principal AI Architect di platform kesehatan digital (*Telemedicine Platform*). Anda diminta merancang sistem otomatisasi pembuat *Clinical Encounter Summary* (ringkasan konsultasi dokter-pasien) dari rekaman audio transkrip mentah. 

**Tantangan**:
* Regulasi mensyaratkan:
  1. *Zero Medical Hallucination*: Tidak boleh ada obat/dosis yang tertulis di ringkasan jika tidak ada dalam transkrip.
  2. *HIPAA Compliance*: Nama keluarga, alamat rumah pasien harus di-redact (masking).
  3. *SOAP Structure*: Ringkasan harus mematuhi format Subjective, Objective, Assessment, Plan secara mutlak.
* Tugas Anda: Rancang arsitektur microservice lengkap (arsitektur graf status / async agent, state transitions, prompt chaining template, deterministic verification layer untuk ekstraksi entitas klinis) dengan Directed Stimulus, Critic, and Self-Refinement loop.
* Format penyelesaian: Buat dokumen rancangan arsitektur teknis lengkap beserta proof-of-concept pseudo-implementation engine tanpa menggunakan library wrapper tingkat tinggi (hanya native async Python, HTTP client, dan Pydantic).

---

### 15. Quiz Evaluasi Pemahaman

#### Basic (5 Pertanyaan)
1. Apa fungsi esensial dari Directional Stimulus dalam inferensi LLM?
   * *Jawaban Singkat*: Memberikan constraint/anchor semantik spesifik dari task input untuk membatasi search space distribusi probabilitas token LLM ke arah hasil yang relevan.
2. Mengapa deterministic checks (misal: AST parsing, JSON linting) harus mendahului LLM Critic?
   * *Jawaban Singkat*: Menghemat latency dan financial cost LLM token untuk error fatal yang dapat dideteksi secara deterministik, murah, dan 100% akurat oleh local runtime engine.
3. Sebutkan parameter yang umumnya digunakan sebagai stopping condition pada Closed-Loop Refinement!
   * *Jawaban Singkat*: Skor kualitas melampaui threshold ($\tau$), jumlah iterasi mencapai maksimum ($T_{\max}$), atau stagnasi perubahan skor ($|M_t - M_{t-1}| < \epsilon$).
4. Apa kelemahan utama arsitektur Single-Pass Generation dibanding Self-Refinement pada task berisiko tinggi?
   * *Jawaban Singkat*: Tidak adanya mekanisme verifikasi kesalahan (*no error recovery mechanism*); model tidak dapat membatalkan deviasi token awal sehingga rentan menghasilkan halusinasi logis.
5. Apa peran episodic memory dalam framework Reflexion?
   * *Jawaban Singkat*: Mencegah loop berulang (*cyclic oscillation*) dengan mencatat riwayat kegagalan dan kritik masa lalu sebagai panduan negatif bagi refiner.

#### Intermediate (5 Pertanyaan)
6. Bagaimana cara memitigasi risiko Refiner Agent yang mengalami *drift* (merusak poin yang sudah benar)?
   * *Jawaban Singkat*: Menggunakan invariant persistence assertion, di mana komponen yang telah lulus kritik dikunci di prompt atau disisipkan sebagai non-negotiable constraint dalam context refiner.
7. Mengapa Pydantic V2 structured outputs lebih diutamakan untuk respons Critic daripada format teks bebas?
   * *Jawaban Singkat*: Memungkinkan orkestrator sistem (state machine) membaca skor numerik dan array instruksi perbaikan secara deterministik via deserialization tanpa risiko parsing regex yang rapuh.
8. Kapan penerapan Directional Stimulus Prompting (DSP) lebih menguntungkan daripada Fine-Tuning model?
   * *Jawaban Singkat*: Saat aturan operasional sering berubah secara dinamis (high volatility) dan dataset berlabel domain tidak cukup besar untuk melatih model tanpa catastrophic forgetting.
9. Jelaskan bagaimana *plateau detection* bekerja pada convergence loop!
   * *Jawaban Singkat*: Algoritma menghitung perbedaan skor metrik antar dua atau tiga siklus iterasi berurutan; jika perbedaan berada di bawah $\epsilon$ tertentu, sistem mendeteksi stagnasi dan menghentikan pemborosan token.
10. Apa risiko jika model Critic memiliki ukuran/kapasitas penalaran yang jauh lebih kecil dibandingkan Generator?
    * *Jawaban Singkat*: False negative atau hallucinated critiques; model Critic kecil gagal memahami konteks penalaran model Generator besar, menghasilkan arahan revisi yang bias atau keliru.

#### Skenario Kasus Produksi (3 Pertanyaan)

11. **Skenario 1**: Pipeline Refinement kode Anda berjalan lambat di level produksi (P99 Latency = 45 detik) dengan rata-rata 3 iterasi per request. Tim DevOps meminta Anda memotong latensi hingga 50% tanpa menurunkan acceptance rate kode di atas 90%. Apa modifikasi arsitektur yang Anda eksekusi?
    * *Solusi Teknis*:
      1. Jalankan LLM Critic hanya jika static linter lokal lolos.
      2. Ganti LLM Critic dengan Small Language Model (SLM) yang di-fine-tune khusus untuk task classification evaluasi, atau gunakan speculative checking.
      3. Kurangi Max Iterations menjadi 2 dan perkuat Directional Stimulus di iterasi awal (zero-step) untuk menaikkan first-pass yield rate sehingga 70% request selesai di $t=1$.

12. **Skenario 2**: Pada iterasi ke-2, Generator menghasilkan output yang nilainya lebih rendah daripada iterasi ke-1 ($M_2 = 0.65$, sedangkan $M_1 = 0.82$). Sistem Anda dirancang untuk selalu mengambil draf terakhir ($Y_{\text{final}}$). Apa konsekuensi operasionalnya dan bagaimana mendesain perbaikannya?
    * *Solusi Teknis*:
      * Konsekuensi: Terjadi degradasi kualitas keluaran (regresi sistematis ke user) akibat overfitting terhadap feedback Critic yang parsial.
      * Perbaikan: Terapkan pattern *Best-So-Far Checkpointing*. Orchestrator harus memelihara referensi ke draf dengan skor valid tertinggi di memory. Bila loop berakhir tanpa melampaui skor terbaik lama, sistem merestore $Y_{\text{best}}$ (state pada $M_1$) sebagai payload akhir.

13. **Skenario 3**: Log sistem menunjukkan bahwa Critic Agent memberikan instruksi perbaikan yang bertentangan secara diametral antargenerasi: Iterasi 1: *"Tambahkan dokumentasi docstring lengkap di setiap baris"*, Iterasi 2: *"Persingkat kode, hapus komentar/docstring yang berlebihan"*. Bagaimana menghentikan pathologi degenerasi ini?
    * *Solusi Teknis*:
      * Terapkan *Frozen Evaluation Rubric*. Model Critic tidak boleh diberi instruksi bebas; critic prompt harus diikat pada *checklist scoring matrix* bernilai biner atau scalar dengan contoh baku (few-shot critique anchors). Hilangkan instruksi ambigu terkait preferensi estetika gaya penulisan dan batasi kritik murni pada logic correctness dan structural schema.

---

### 16. Summary

* **Directional Stimulus Prompting (DSP)** mengontrol lintasan generasi LLM secara proaktif dengan menyuntikkan *hints* atau policy invariant sebelum generasi token dimulai, mengurangi entropi solusi sejak dini.
* **Critique-Refinement Loops** mengubah interaksi LLM dari arsitektur *open-loop feedforward* menjadi *closed-loop feedback system*, memberikan kemampuan *error-recovery* otonom bagi sistem AI.
* **Production-grade Self-Correction** mensyaratkan pemisahan tegas antara **Deterministic Validation** (murah, cepat, infallible) dan **Semantic Critique** (mahal, berbasis model probabilitas).
* Mengabaikan kontrol loop seperti **Convergence Threshold ($\tau$)**, **Iteration Hard Ceiling**, dan **Best-So-Far State Checkpoint** akan memicu fenomena infinite oscillating, token wastage, serta regresi performa pada aplikasi enterprise skala besar.