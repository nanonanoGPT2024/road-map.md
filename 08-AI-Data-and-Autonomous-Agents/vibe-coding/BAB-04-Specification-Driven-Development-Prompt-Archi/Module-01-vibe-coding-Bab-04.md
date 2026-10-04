# Bab 04: Specification-Driven Development & Prompt Architecture

## Module 01: Foundations of Spec-First Prompt Engineering & Deterministic LLM Contracts

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:

1. **Menganalisis dan Mentransformasi Kebutuhan Bisnis Non-Deterministik** menjadi *Formal Executable Specifications* (FES) berbasis Pydantic v2 dan JSON Schema Draft 2020-12.
2. **Merancang Arsitektur Prompt Berlapis (*Layered Prompt Architecture*)** yang memisahkan *System Invariants*, *Domain Policy*, *Dynamic Context*, dan *Input Payloads* untuk mencegah serangan *indirect prompt injection*.
3. **Mengimplementasikan Pipeline Kompilasi Prompt Dinamis (*Prompt Compiler*)** yang memvalidasi *context-window budget*, token allocation, dan dependency injection sebelum inferensi dilakukan.
4. **Membangun Siklus Validasi dan Rekonsiliasi Tertutup (*Closed-Loop Self-Correction Engine*)** dengan deterministik error-feedback loops untuk menjamin validitas output parsing $P(\text{Valid Output}) \to 1.0$.
5. **Mengevaluasi Trade-off Mekanisme Structured Output**: *Constrained Decoding* (Grammar-based sampling) vs *Tool/Function Calling* vs *Post-hoc Output Parsing* ditinjau dari latensi (*Time-to-First-Token*), throughput, dan token overhead.

---

### 2. Concept Overview

Dalam paradigma *vibe-coding*, ketergantungan pada prompt ad-hoc yang bersifat intuitif menghasilkan *technical debt* berupa *stochastic fragility*—kondisi di mana sistem tampak berfungsi saat prototyping, namun gagal secara acak di lingkungan produksi akibat *distributional drift* dan *edge-case hallucinations*.

```
   Ad-hoc "Vibe-Coding" (Fragile)
   [Natural Language] ──> [LLM] ──> [Unstructured Text] ──> [Regex/Brittle Parsing] ──> (System Failure)

   Specification-Driven Development (Deterministic)
   [Domain Model / Spec] ──> [Compiler/Validator] ──> [Prompt IR] ──> [LLM + Constrained Sampler] ──> [AST Schema Validation] ──> [Typed Domain Entity]
```

**Specification-Driven Development (SDD)** memperlakukan LLM bukan sebagai "oracle ajaib", melainkan sebagai **probabilistic execution engine (ALU non-deterministik)** yang memerlukan kontrak antarmuka kaku. SDD menegakkan tiga postulat utama:

1. **Single Source of Truth (SSOT):** Spesifikasi didefinisikan dalam skema formal (tipe data, invarian logika, batasan nilai, relasi) yang menjadi sumber kompilasi prompt, validator payload, dan unit testing.
2. **Separation of Concerns:** Kontrak sistem (*Contract*) dipisahkan secara struktural dari instruksi perilaku (*Behavioral Guidelines*) dan data runtime (*Execution Context*).
3. **Deterministic Boundary:** Setiap payload teks yang keluar dari model probabilistik harus melalui gerbang validasi deterministik (AST parse $\to$ Type coercion $\to$ Invariant assertion) sebelum diizinkan menyentuh domain layer aplikasi.

---

### 3. Why It Matters

Di tingkat enterprise, kegagalan integrasi LLM jarang disebabkan oleh rendahnya kapabilitas reasoning model, melainkan oleh **ketiadaan kontrak data yang rigid**. 

* **Silent Failure & Schema Drift:** Perubahan minor pada bobot model (misal update dari OpenAI/Anthropic) dapat mengubah format tanggal dari ISO-8601 menjadi format natural, merusak parser hilir (*downstream pipeline*), dan menghentikan alur transaksi finansial.
* **Security & Prompt Injection:** Tanpa arsitektur prompt formal, penggabungan data pengguna yang tidak disanitasi ke dalam prompt template membuka celah *context escape*, di mana input pengguna mengambil alih instruksi sistem (*Jailbreaking / Privilege Escalation*).
* **Auditability & Compliance:** Regulasi enterprise (misal ISO 27001, SOC2, HIPAA) menuntut jejak audit deterministik terhadap keputusan yang diambil oleh autonomous agents. SDD memungkinkan setiap prompt yang dikirim dan struktur data yang dihasilkan memiliki hash kriptografis dan skema versi yang terikat pada commit git tertentu.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur end-to-end arsitektur SDD:

```
+---------------------------------------------------------------------------------------------------+
| SPECIFICATION DOMAIN LAYER                                                                       |
|  +----------------------------------+       +---------------------------------------------------+ |
|  | Base Specification (Pydantic v2) | ----> | JSON Schema Generation (with Semantic Meta-props) | |
|  +----------------------------------+       +---------------------------------------------------+ |
+-------------------------------------------------------|-------------------------------------------+
                                                        v
+---------------------------------------------------------------------------------------------------+
| PROMPT COMPILATION PIPELINE                                                                       |
|  +----------------------------+     +-------------------------------+                             |
|  | Context Budget Allocator   |     | Prompt AST Assembler          |                             |
|  | (TikToken / Tokenizer)     | --> | - Layer 1: Invariants (Fixed) |                             |
|  +----------------------------+     | - Layer 2: Domain Logic       |                             |
|                                     | - Layer 3: Dynamic Few-Shot   |                             |
|                                     | - Layer 4: Injection Guard    |                             |
|                                     +-------------------------------+                             |
+-------------------------------------------------------|-------------------------------------------+
                                                        v
+---------------------------------------------------------------------------------------------------+
| EXECUTION & SAMPLING RUNTIME                                                                      |
|  +----------------------------------------------------------------------------------------------+ |
|  | LLM Provider (Function Calling / Structured Outputs Mode)                                    | |
|  +----------------------------------------------------------------------------------------------+ |
+-------------------------------------------------------|-------------------------------------------+
                                                        v
+---------------------------------------------------------------------------------------------------+
| VALIDATION & REPAIR LOOP (CLOSED-LOOP FEEDBACK)                                                   |
|                                                                                                   |
|             [ Raw Text Response ]                                                                 |
|                       |                                                                           |
|                       v                                                                           |
|         +---------------------------+                                                             |
|         | Structural Parser (JSON)  | -- (Parse Error) ----------------+                          |
|         +---------------------------+                                  |                          |
|                       | (Success)                                      |                          |
|                       v                                                |                          |
|         +---------------------------+                                  v                          |
|         | Semantic Schema Validator | -- (Validation Error) -> [ Repair Prompt Compiler ]         |
|         +---------------------------+                                  |                          |
|                       | (Success)                                      v                          |
|                       |                                   +--------------------------+            |
|                       |                                   | Re-inferencing with AST  |            |
|                       |                                   | Error Feedback           |            |
|                       v                                   +--------------------------+            |
|       +-------------------------------+                                |                          |
|       | Typed Entity to Domain Engine | <------------------------------+ (Max 3 Retries)          |
|       +-------------------------------+                                                           |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Layered Prompt Architecture (LPA)
LPA membagi prompt menjadi empat lapisan isolasi memori:
1. **System Invariant (Layer 0):** Berisi instruksi fundamental yang mendefinisikan *persona*, kepatuhan mutlak (*hard constraints*), dan delimitasi format output. Layer ini tidak boleh berubah antar sesi runtime.
2. **Domain Policy (Layer 1):** Aturan bisnis operasional, batasan otorisasi, dan logika kondisional domain tertentu.
3. **Dynamic Few-Shot Exemplars (Layer 2):** Pasangan representatif `(Input, Output)` yang dipilih secara deterministik atau via Vector Similarity Search untuk memandu model pada kasus rumit (*corner cases*).
4. **Isolated Context Boundary (Layer 3):** Payload runtime dari pengguna, dibungkus dalam tag penanda khusus (misal `<payload id="uuid">...</payload>`) untuk mencegah *ambiguity* parsing token.

#### 5.2 Grammar-Based Constrained Decoding vs Post-Hoc Validation
* **Constrained Decoding (GBNF, Outlines, Jsonformer):** Bekerja pada level pengambilan sampel token logits. Masking diterapkan langsung pada matriks probabilitas softmax sehingga token yang melanggar grammar formal (EBNF/JSON Schema) bernilai probabilitas $0$.
  * *Keuntungan:* Garansi validitas sintaksis $100\%$, tanpa token terbuang.
  * *Kerugian:* Ketergantungan infrastruktur inference engine lokal (llama.cpp, vLLM) dan overhead memori pada grammar state-machine traversal.
* **Closed-Loop Feedback via Reflection (Post-Hoc):** Digunakan saat berinteraksi dengan Black-Box LLM APIs (OpenAI, Anthropic). Memanfaatkan payload kegagalan struktural (misal `PydanticValidationError.errors()`) yang dikonversi menjadi prompt korektif berisi diff JSON kesalahan untuk dievaluasi ulang oleh model.

---

### 6. Production-Ready Code Implementation

Arsitektur di bawah ini menggunakan **Python 3.12+**, mengintegrasikan **Pydantic v2** untuk definisi spesifikasi, token calculation budget, dan loop rekonsiliasi kesalahan.

```python
"""
Module: core_prompt_engine.py
Description: Production-Grade Specification-Driven Prompt Compiler and Runtime.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field, ValidationError, model_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SpecificationPromptEngine")

T = TypeVar("T", bound=BaseModel)


# ============================================================================
# 1. SPECIFICATION DOMAIN DEFINITION (CONTRACT LAYER)
# ============================================================================

class ExecutionStep(BaseModel):
    step_id: int = Field(..., description="Deterministic sequence ID.")
    action_type: str = Field(
        ..., 
        description="Type of system action", 
        pattern=r"^(READ|WRITE|DELETE|EXECUTE)$"
    )
    target_resource: str = Field(..., description="Target URI or resource path.")
    retry_budget: int = Field(default=3, ge=0, le=5)


class AgentActionSpecification(BaseModel):
    """
    Spesifikasi formal tindakan autonomous agent.
    Berfungsi sebagai SSOT untuk prompt generation dan output assertion.
    """
    transaction_id: str = Field(..., description="Unique UUID format.")
    intent_analysis: str = Field(..., min_length=10, description="Chain of thought explanation.")
    is_destructive: bool = Field(..., description="Flag if operations alter state irreversibly.")
    execution_plan: List[ExecutionStep] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_safety_policy(self) -> AgentActionSpecification:
        """Contoh invarian enterprise: Destructive ops wajib memiliki retry_budget <= 1."""
        if self.is_destructive:
            for step in self.execution_plan:
                if step.action_type in ("WRITE", "DELETE") and step.retry_budget > 1:
                    raise ValueError(
                        f"Step {step.step_id} is DESTRUCTIVE. Safety policy restricts retry_budget <= 1."
                    )
        return self


# ============================================================================
# 2. PROMPT COMPILER ARCHITECTURE
# ============================================================================

class CompiledPrompt(BaseModel):
    system_instruction: str
    user_payload: str
    target_schema: Dict[str, Any]


class LayeredPromptCompiler:
    def __init__(self, spec_model: Type[BaseModel]):
        self.spec_model = spec_model
        self.cached_schema = spec_model.model_json_schema()

    def _render_layer_0_invariants(self) -> str:
        return (
            "You are a strict deterministic execution planner. You must operate exclusively "
            "within the operational constraints defined in the schema contract.\n"
            "CRITICAL INVARIANTS:\n"
            "1. Output MUST be a single, syntactically valid JSON object adhering strictly to the JSON Schema.\n"
            "2. Do NOT emit markdown fences (` ```json ` or ` ``` `) under any circumstances.\n"
            "3. Do NOT invent new fields or omit required fields."
        )

    def _render_layer_1_schema(self) -> str:
        return f"TARGET_SPECIFICATION_SCHEMA:\n{json.dumps(self.cached_schema, indent=2)}"

    def compile(self, user_intent: str, dynamic_context: Optional[Dict[str, Any]] = None) -> CompiledPrompt:
        """
        Kompilasi lapisan prompt secara terisolasi untuk mitigasi injeksi konteks.
        """
        system_instruction = (
            f"{self._render_layer_0_invariants()}\n\n"
            f"{self._render_layer_1_schema()}"
        )
        
        # Isolasi input menggunakan tag un-interpolated
        context_str = json.dumps(dynamic_context) if dynamic_context else "{}"
        user_payload = (
            f"<runtime_context>\n{context_str}\n</runtime_context>\n"
            f"<user_intent>\n{user_intent}\n</user_intent>\n"
            f"Produce the JSON execution payload adhering to the TARGET_SPECIFICATION_SCHEMA:"
        )

        return CompiledPrompt(
            system_instruction=system_instruction,
            user_payload=user_payload,
            target_schema=self.cached_schema
        )


# ============================================================================
# 3. LLM INTERFACE ABSTRACTION
# ============================================================================

class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, system: str, user: str) -> str:
        pass


class MockLLMProvider(LLMProvider):
    """
    Mock inference engine untuk kebutuhan testing dan simulasi kegagalan parsing.
    """
    def __init__(self):
        self.call_count = 0

    async def generate_response(self, system: str, user: str) -> str:
        self.call_count += 1
        
        # Simulasi output pertama: Kesalahan schema (melanggar safety policy)
        if self.call_count == 1:
            return json.dumps({
                "transaction_id": "tx-99482",
                "intent_analysis": "Executing mass delete on obsolete accounts.",
                "is_destructive": True,
                "execution_plan": [
                    {
                        "step_id": 1,
                        "action_type": "DELETE",
                        "target_resource": "s3://prod-data/accounts",
                        "retry_budget": 3  # <- Violates safety invariant!
                    }
                ]
            })

        # Simulasi output kedua: Self-Correction berhasil setelah menerima error context
        return json.dumps({
            "transaction_id": "tx-99482",
            "intent_analysis": "Executing mass delete on obsolete accounts with safety constraints adhered.",
            "is_destructive": True,
            "execution_plan": [
                {
                    "step_id": 1,
                    "action_type": "DELETE",
                    "target_resource": "s3://prod-data/accounts",
                    "retry_budget": 1  # Fixed
                }
            ]
        })


# ============================================================================
# 4. DETERMINISTIC REPAIR RUNTIME ENGINE
# ============================================================================

class SpecificationEngine(Generic[T]):
    def __init__(self, spec_model: Type[T], llm_provider: LLMProvider, max_repairs: int = 3):
        self.spec_model = spec_model
        self.compiler = LayeredPromptCompiler(spec_model)
        self.llm = llm_provider
        self.max_repairs = max_repairs

    async def execute(self, user_intent: str, context: Optional[Dict[str, Any]] = None) -> T:
        compiled = self.compiler.compile(user_intent, context)
        current_system = compiled.system_instruction
        current_user = compiled.user_payload

        for attempt in range(1, self.max_repairs + 1):
            logger.info(f"Inferencing attempt {attempt}/{self.max_repairs}...")
            raw_response = await self.llm.generate_response(current_system, current_user)
            
            try:
                # 1. Parsing Sintaksis
                raw_response_clean = raw_response.strip()
                parsed_json = json.loads(raw_response_clean)
                
                # 2. Parsing Semantik & Penegakan Invarian
                validated_model = self.spec_model.model_validate(parsed_json)
                logger.info("Validation successful. Deterministic contract satisfied.")
                return validated_model

            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(f"Contract violation detected at attempt {attempt}: {str(exc)}")
                if attempt == self.max_repairs:
                    logger.error("Max repair cycles exhausted. Aborting pipeline.")
                    raise RuntimeError(f"Contract enforcement failed after {attempt} attempts: {exc}") from exc

                # Kompilasi Prompt Refleksi / Repair Feedback
                error_feedback = self._build_repair_feedback(raw_response, exc)
                current_user = (
                    f"{compiled.user_payload}\n\n"
                    f"CRITICAL REPAIR REQUIRED:\n"
                    f"Your previous output violated system contracts.\n"
                    f"Feedback:\n{error_feedback}\n"
                    f"Re-emit the corrected complete JSON object:"
                )

        raise RuntimeError("Unexpected pipeline termination.")

    def _build_repair_feedback(self, raw_output: str, error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return f"Syntax Error: Invalid JSON. {error.msg} at line {error.lineno} column {error.colno}."
        elif isinstance(error, ValidationError):
            formatted_errors = []
            for err in error.errors():
                loc = " -> ".join(str(l) for l in err["loc"])
                formatted_errors.append(f"- Location: [{loc}] | Violation: {err['msg']} | Provided: {err.get('input', 'N/A')}")
            return "Semantic Validation Errors:\n" + "\n".join(formatted_errors)
        return str(error)


# ============================================================================
# 5. ENTRY POINT EXECUTION TEST
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        engine = SpecificationEngine(
            spec_model=AgentActionSpecification,
            llm_provider=MockLLMProvider(),
            max_repairs=3
        )
        
        result = await engine.execute(
            user_intent="Purge all deprecated user databases from cold storage.",
            context={"cluster": "production-us-east-1", "initiator_role": "admin"}
        )
        
        print("\n--- FINAL TYPED ENTITY (VALIDATED) ---")
        print(f"Transaction ID : {result.transaction_id}")
        print(f"Is Destructive : {result.is_destructive}")
        print(f"Action Type    : {result.execution_plan[0].action_type}")
        print(f"Retry Budget   : {result.execution_plan[0].retry_budget}")

    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Mode | Root Cause | Mekanisme Pemulihan (Mitigasi Produksi) |
| :--- | :--- | :--- |
| **Context Window Overflow** | Skema Pydantic atau feedback error berulang melebihi batas token model. | *Truncation Strategy*: Pangkas field metadata non-esensial dan gunakan *Error Slicing* (hanya tampilkan maksimal 3 error teratas dari `ValidationError`). |
| **Markdown Delimiter Hallucination** | Model melampirkan teks pada format ` ```json ... ``` `. | Gunakan *Pre-parser Stripper* regex (`r"```(?:json)?\s*([\s\S]*?)\s*```"`) sebelum menjalankan `json.loads`. |
| **Flapping / Infinite Repair Oscillation** | LLM memperbaiki error $A$, namun perbaikan tersebut memicu error $B$, lalu pada turn berikutnya kembali memicu error $A$. | Deteksi hash payload kesalahan; jika terjadi hash error cycle, eskalasikan model ke *high-reasoning engine* (e.g., Claude 3.5 Sonnet / GPT-4o) atau hentikan eksekusi (*circuit breaker*). |
| **Silent Type Coercion Error** | Pydantic mengonversi string `"123"` menjadi integer `123` tanpa sengaja, merusak format id. | Terapkan `strict=True` pada konfigurasi model Pydantic: `model_config = ConfigDict(strict=True)`. |
| **Adversarial Schema Smuggling** | Input pengguna menyisipkan string JSON yang memalsukan struktur respons spesifikasi. | Bungkus user data dalam CDATA-like blocks atau format XML berkarakter unik; sanitasi escape string ganda. |

---

### 8. Trade-offs & Alternatif Solusi

```
                     LATENCY (TTFT)
                          ▲
                          │     [Native Constrained Decoding]
                          │       (vLLM / Outlines / GBNF)
                          │        - Zero validation latency
                          │        - Higher TTFT compilation
                          │
                          │
  [Function Calling API]  │
    (OpenAI / Anthropic)  │
     - Balanced latency   │
     - Black-box retry    │
                          │                     [Closed-Loop Repair Loop]
                          │                       (Pydantic + Post-hoc Reflection)
                          │                        - Lowest setup overhead
                          │                        - Multi-turn latency penalty on error
                          └────────────────────────────────────────────────────────► DETERMINISTIC GUARANTEE
```

| Pendekatan | Kelebihan | Kelemahan | Kapan Digunakan |
| :--- | :--- | :--- | :--- |
| **Post-Hoc Reflection Loop (Kode di atas)** | Provider-agnostic; mudah didebug; mampu mengevaluasi invarian tingkat lanjut (lintas field). | Latensi tinggi jika model memicu multi-turn retry; konsumsi token berlebih. | Sistem berbasis API pihak ketiga (OpenAI, Anthropic) dengan batasan model standar. |
| **Grammar Constrained Decoding (Outlines/GBNF)** | Sintaksis dijamin valid sejak inferensi token pertama; tidak ada parsing failure. | Membutuhkan hosting engine mandiri (vLLM/llama.cpp); overhead kompilasi state machine untuk skema kompleks. | Self-hosted LLM clusters dengan beban operasional tinggi (*high-throughput requirements*). |
| **Native Function/Tool Calling** | Didukung secara *native* oleh vendor; latensi optimal untuk validasi satu langkah. | Terikat skema JSON dasar; tidak mampu mengeksekusi logika validasi kustom (custom assertions) di level inference. | Operasi CRUD standar berbasis SaaS API publik. |

---

### 9. Best Practices & Standard Industri

1. **Semantic Versioning Prompts & Specifications:** Simpan spesifikasi Pydantic dalam modul versi (misal: `specs/v1_2_0/action_spec.py`). Setiap prompt payload harus mencantumkan metadata `spec_version: 1.2.0`.
2. **Defensive Separation of Concerns:** Jangan pernah menggabungkan *Few-Shot Examples* langsung di dalam instruksi sistem dasar. Gunakan array pesan native (`ChatML`) dengan peran `user` dan `assistant` sintetis.
3. **Pydantic Strict Mode by Default:** Gunakan `Field(..., strict=True)` untuk mencegah silent casting dari float ke integer, atau string ke boolean.
4. **CI/CD Regression Harness:** Jalankan evaluasi deterministik menggunakan *synthetic perturbation dataset*. Prompt diuji terhadap 100 variasi masukan menggunakan tooling seperti Promptfoo atau DeepEval untuk memverifikasi tingkat pelanggaran kontrak (*Contract Violation Rate* $< 0.1\%$).

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan membangun modul audit kepatuhan infrastruktur cloud (*Autonomous IAM Policy Compiler*). Modul ini menerima instruksi teks dari admin, lalu menghasilkan spesifikasi permission IAM AWS yang valid.

#### Tugas:
1. Definisikan `IAMStatementSpec` dan `IAMPolicySpec` menggunakan Pydantic v2 dengan ketentuan:
   * `Effect` hanya bernilai `"Allow"` atau `"Deny"`.
   * `Action` berupa list string dengan format `service:operation` (misal: `s3:GetObject`). Gunakan validasi regex.
   * `Resource` wajib diawali dengan `arn:aws:`.
   * **Invarian Kustom**: Jika `Effect == "Allow"` dan `Action` berisi wildcard `*`, maka field `Resource` **tidak boleh** bernilai `*` (mencegah privilege escalation tak terkendali).
2. Terapkan engine eksekusi menggunakan `SpecificationEngine` yang menguji kasus di mana input melanggar invarian kustom tersebut, dan validasi bahwa model mampu memperbaikinya dalam siklus self-correction.

#### Verifikasi Keberhasilan:
Eksekusi script test harness dan pastikan log runtime menunjukkan:
1. `ValidationError` tertangkap pada Attempt 1 karena wildcard privilege issue.
2. Formatted feedback diarahkan kembali ke LLM.
3. Attempt 2 mengembalikan objek Pydantic yang valid dan lolos parsing assertion. Output dictionary final tercetak dengan status bersih tanpa dependensi parser eksternal tambahan.