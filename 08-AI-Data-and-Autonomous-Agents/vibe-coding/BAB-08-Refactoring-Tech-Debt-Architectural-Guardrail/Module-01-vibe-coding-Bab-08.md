# Bab 08: Refactoring, Tech Debt, & Architectural Guardrails
## Modul 01: Mitigasi Technical Debt & Penegakan Architectural Guardrails pada Vibe-Coded Agentic Systems

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Principal Engineer/Architect diharapkan mampu:
*   **Mendeteksi & Mengukur Anti-Pattern Vibe-Coding:** Mengidentifikasi minimal 5 anti-pattern struktural spesifik pada kode hasil generasi Large Language Model (LLM) (seperti *stochastic sprawl*, *hallucinated state leaks*, *silent exception swallowing*, *unbounded tool recursion*, dan *schema divergence*) dengan metrik kompleksitas siklomatik dan *Abstract Syntax Tree* (AST) analysis.
*   **Membangun Deterministic Architectural Guardrails:** Mengimplementasikan mesin validasi berbasis AST dan *runtime invariant assertions* untuk memastikan kode agen otonom mematuhi batas arsitektural enterprise sebelum masuk fase deployment.
*   **Mengembangkan Automated AST Refactoring Pipeline:** Merancang dan mengeksekusi pipeline refactoring otomatis berbasis Python AST node transformer yang mengubah script *vibe-coded* rapuh menjadi komponen *clean architecture* yang *idempotent*, *type-safe*, dan *fault-tolerant*.
*   **Menerapkan Runtime Boundary Enforcement:** Mengisolasi eksekusi tool non-deterministik dan membatasi *execution blast radius* menggunakan sandboxing fungsional, circuit breakers, dan verifikasi kontrak state berbasis schema.

---

### 2. Concept Overview (Mental Model & Teori Inti)

Fenomena **"Vibe-Coding"**—praktik membangun aplikasi atau sistem agen secara cepat menggunakan instruksi bahasa alami kepada model AI generatif—menghasilkan anomali struktural pada siklus hidup rekayasa perangkat lunak. Meskipun *time-to-prototype* menurun drastis, entropi teknis meningkat secara eksponensial.

```
+-----------------------------------------------------------------------+
|                    THE VIBE-CODING DEBT FLYWHEEL                      |
+-----------------------------------------------------------------------+
|  [Natural Language Prompt]                                            |
|          |                                                            |
|          v                                                            |
|  [LLM Synthesizes Code] ===> Output: Bekerja di "Happy Path"          |
|          |                  Masalah: - Tidak ada boundary domain      |
|          v                           - Polimorfisme semu / Tipe longgar|
|  [Akumulasi Tech Debt]               - Hidden state leakage           |
|          |                           - Error handling bisu            |
|          v                                                            |
|  [Prompt Baru untuk Fix] ==> LLM Menambah Lapisan Patch di Atas Patch|
|          |                   (Meningkatkan Kompleksitas Siklomatik)   |
|          v                                                            |
|  [Structural Entropy Collapse] => Kegagalan Determinisme di Prod      |
+-----------------------------------------------------------------------+
```

#### Mental Model: The Invariant Citadel vs. The Stochastic Wilderness
*   **The Stochastic Wilderness:** Ruang komputasi LLM dan agen otonom yang bekerja berdasarkan distribusi probabilitas token. Output di area ini dinamis, tidak sepenuhnya dapat diprediksi, dan rawan menghasilkan anomali logika (*semantic drift*).
*   **The Invariant Citadel:** Arsitektur inti enterprise yang bersifat deterministik, *strongly typed*, memiliki kontrak transaksional ACID/BASE yang jelas, dan patuh pada prinsip *Design by Contract* (DbC).

**Architectural Guardrails** bertindak sebagai benteng transisi (*demarcation gate*). Setiap artefak kode atau keputusan eksekusi yang keluar dari *Stochastic Wilderness* harus melewati validasi statis berbasis AST, pengecekan invariansi runtime, dan pembatasan kapabilitas (*least privilege execution*) sebelum dapat memanipulasi state sistem inti.

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

Di lingkungan produksi enterprise, kode hasil *vibe-coding* pada sistem agen otonom menimbulkan ancaman operasional nyata:
1.  **Hallucinated Dependencies & Phantom APIs:** LLM sering mengimpor pustaka internal fiktif atau memanfaatkan method privat yang tidak stabil.
2.  **Unbounded Recursion & Token Exhaustion:** Agen yang memanggil tool secara otonom tanpa batasan siklus invariant dapat mengalami *infinite loop*, menghabiskan ribuan dolar kuota API dalam hitungan menit.
3.  **Silent State Mutation:** AI-generated functions sering kali mengabaikan imutabilitas, memutasi context global secara sembarangan, yang memicu *race condition* parah pada arsitektur *concurrent event-driven*.
4.  **Regulatory Non-Compliance:** Kurangnya isolasi data pada prompt and tool execution context dapat mengekspos PII (Personally Identifiable Information) ke eksternal API tanpa jejak audit logging (*auditability gap*).

Tanpa guardrail otomatis, biaya perawatan kode (*cost of maintenance*) dan *Mean Time to Recovery* (MTTR) melonjak tajam karena *engineer* manusia kehilangan pemahaman komprehensif atas dependensi implisit yang dibuat oleh AI.

---

### 4. Arsitektur & Diagram Komponen

Arsitektur Architectural Guardrails & Automated Refactoring Engine dirancang secara modular:

```
+-----------------------------------------------------------------------------------+
|                        ARCHITECTURAL GUARDRAIL PIPELINE                           |
+-----------------------------------------------------------------------------------+
                                          |
  [AI-Generated Vibe-Coded Script]        | Input Pipeline
                                          v
+-----------------------------------------------------------------------------------+
| 1. STATIC AST ANALYSIS & LINT GATE                                               |
|    - Parse Source to AST (Python ast / tree-sitter)                              |
|    - Rule Engine: Blacklisted nodes, dynamic code execution (eval/exec)           |
|    - Boundary Verification: Validasi dependency boundary (misal: LangChain/core) |
+-----------------------------------------------------------------------------------+
                                          |
                                          | AST Valid?
                        +-----------------+-----------------+
                        | GAGAL                             | LOLOS
                        v                                   v
+------------------------------------+  +-------------------------------------------+
| 2. AUTOMATED AST REFACTOR ENGINE   |  | 3. TYPE & CONTRACT VERIFICATION           |
|    - Node Transformer Rewrite      |  |    - Mypy / Pyright Static Verification   |
|    - Inject Strict Type Annotations|  |    - Pydantic v2 Schema Enforcement       |
|    - Inject Idempotency Wrappers   |  +-------------------------------------------+
+------------------------------------+                      |
                        | Refactored                        v
                        +---------------->+-----------------------------------------+
                                          | 4. RUNTIME INVARIANT ENGINE             |
                                          |    - State Space Boundary Checker       |
                                          |    - Dynamic Execution Circuit Breaker  |
                                          |    - Budget & Tool Call Quarantine      |
                                          +-----------------------------------------+
                                                            |
                                                            v
                                          [PRODUCTION-READY AGENT COMPONENT]
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. Static Abstract Syntax Tree (AST) Inspection
Alih-alih menggunakan regex yang rapuh, guardrail memeriksa struktur pohon sintaksis kode Python secara mendalam. 
*   **Pemeriksaan Node Berbahaya:** Mendeteksi pemanggilan fungsi implisit seperti `eval()`, `exec()`, `__import__()`, atau penggunaan manipulasi atribut dinamis tak terbatas `getattr()` pada objek internal.
*   **Pemeriksaan Batasan Arsitektural:** Memverifikasi bahwa layer agen (controller) tidak langsung mengimpor driver infrastruktur basis data (misal: bypass SQLAlchemy Session langsung ke `psycopg2`).

#### B. Architectural Invariants via Metaprogramming & Contracts
Prinsip *Design by Contract* diterapkan melalui decorator runtime invariant:
*   **Pre-conditions:** Validasi state input sebelum aksi agen/tool dijalankan (misal: token budget $> 0$, context window length $\le K$).
*   **Post-conditions:** Validasi output format terhadap skema deterministik (misal: JSON valid, Pydantic model lolos, tidak ada kebocoran semantic string di field numerik).
*   **Invariants:** Kondisi sistem yang *wajib* bernilai `True` sebelum dan sesudah eksekusi (misal: memory footprint agen tidak bertambah lebih dari threshold per-step).

#### C. AST Code Transformation (Refactoring Automata)
Pipeline menggunakan `ast.NodeTransformer` untuk secara mekanis menulis ulang kode *vibe-coded*:
*   Membungkus fungsi tool mentah ke dalam penanganan exception berskema (`Result[T, E]`).
*   Menginjeksi parameter dependensi terbalik (*Dependency Injection*) alih-alih instansiasi hardcoded di dalam tubuh fungsi.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi sistem guardrail dan refactoring otomatis berbasis Python 3.12+ dengan pendekatan Clean Architecture, strongly-typed, dan enterprise-grade error handling.

#### Struktur Modul
```
guardrail_core/
├── exceptions.py
├── schemas.py
├── ast_analyzer.py
├── ast_transformer.py
└── runtime_guard.py
```

#### File: `guardrail_core/exceptions.py`
```python
"""Definisi exception hierarkis untuk Architectural Guardrail Engine."""

class GuardrailException(Exception):
    """Base exception untuk semua kegagalan guardrail arsitektur."""
    pass

class StructuralViolationError(GuardrailException):
    """Dilempar saat kode melanggar aturan struktural AST."""
    def __init__(self, rule_id: str, message: str, lineno: int | None = None) -> None:
        self.rule_id = rule_id
        self.lineno = lineno
        super().__init__(f"[{rule_id}] Line {lineno or 'Unknown'}: {message}")

class RuntimeInvariantViolation(GuardrailException):
    """Dilempar saat kondisi kontrak runtime (pre/post-condition) dilanggar."""
    pass

class CircuitBreakerTriggered(GuardrailException):
    """Dilempar saat eksekusi tool melebihi ambang batas kegagalan atau budget."""
    pass
```

#### File: `guardrail_core/schemas.py`
```python
"""Model data untuk validasi invariant state dan konfigurasi policy."""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class GuardrailPolicy(BaseModel):
    """Kebijakan keamanan struktural kode agen."""
    model_config = ConfigDict(frozen=True)

    max_cyclomatic_complexity: int = Field(default=10, ge=1)
    max_tool_calls_per_run: int = Field(default=5, ge=1)
    disallowed_imports: frozenset[str] = Field(
        default_factory=lambda: frozenset({"os", "subprocess", "sys", "socket"})
    )
    disallowed_functions: frozenset[str] = Field(
        default_factory=lambda: frozenset({"eval", "exec", "compile", "globals", "locals"})
    )

class ExecutionContext(BaseModel):
    """Context pelacakan runtime invariant execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_id: str
    remaining_tokens: int = Field(ge=0)
    current_step: int = Field(default=0, ge=0)
    max_steps: int = Field(default=10, ge=1)
    audit_log: list[str] = Field(default_factory=list)

class ExecutionResult(BaseModel, Generic[T]):
    """Standard monadic envelope untuk eksekusi safe-execution."""
    model_config = ConfigDict(frozen=True)

    success: bool
    data: T | None = None
    error_message: str | None = None
```

#### File: `guardrail_core/ast_analyzer.py`
```python
"""Static AST Analyzer untuk deteksi anti-pattern vibe-coding."""

import ast
from typing import Self
from guardrail_core.exceptions import StructuralViolationError
from guardrail_core.schemas import GuardrailPolicy

class VibeCodeASTValidator(ast.NodeVisitor):
    """Visitor AST untuk memverifikasi kepatuhan arsitektur kode LLM."""

    def __init__(self, policy: GuardrailPolicy) -> None:
        self.policy = policy
        self.violations: list[StructuralViolationError] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            base_module = alias.name.split(".")[0]
            if base_module in self.policy.disallowed_imports:
                self.violations.append(
                    StructuralViolationError(
                        rule_id="SEC001",
                        message=f"Direct import modul '{base_module}' dilarang oleh guardrail.",
                        lineno=node.lineno,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            base_module = node.module.split(".")[0]
            if base_module in self.policy.disallowed_imports:
                self.violations.append(
                    StructuralViolationError(
                        rule_id="SEC001",
                        message=f"Direct import from '{base_module}' dilarang oleh guardrail.",
                        lineno=node.lineno,
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Deteksi pemanggilan fungsi blacklisted (misal: eval, exec)
        if isinstance(node.func, ast.Name):
            if node.func.id in self.policy.disallowed_functions:
                self.violations.append(
                    StructuralViolationError(
                        rule_id="SEC002",
                        message=f"Eksekusi fungsi '{node.func.id}()' sangat dilarang.",
                        lineno=node.lineno,
                    )
                )
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Anti-Pattern: Bare except atau silent swallowing (pass pada except)
        if node.type is None:
            self.violations.append(
                StructuralViolationError(
                    rule_id="REL001",
                    message="Ditemukan bare 'except:'. Gunakan typed exceptions minimal Exception.",
                    lineno=node.lineno,
                )
            )
        
        # Cek silent exception (hanya berisi pass)
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.violations.append(
                StructuralViolationError(
                    rule_id="REL002",
                    message="Anti-Pattern: Silent exception swallowing via 'pass'. Log atau raise!",
                    lineno=node.lineno,
                )
            )
        self.generic_visit(node)

    @classmethod
    def validate_code(cls, source_code: str, policy: GuardrailPolicy) -> list[StructuralViolationError]:
        try:
            tree = ast.parse(source_code)
        except SyntaxError as err:
            return [StructuralViolationError(rule_id="SYNTAX", message=str(err), lineno=err.lineno)]
        
        validator = cls(policy=policy)
        validator.visit(tree)
        return validator.violations
```

#### File: `guardrail_core/ast_transformer.py`
```python
"""Automated AST Transformer untuk refactoring kode rapuh."""

import ast

class ExceptionHardenerTransformer(ast.NodeTransformer):
    """Mengubah 'pass' pada except block menjadi explicit logging statement."""

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        self.generic_visit(node)
        
        # Ganti block body jika hanya 'pass'
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            # Transform: pass -> print(f"[GUARDRAIL TRAPPED]: {node.name or 'Exception'}")
            log_call = ast.Expr(
                value=ast.Call(
                    func=ast.Name(id="print", ctx=ast.Load()),
                    args=[
                        ast.Constant(
                            value=f"[AUTO-REFACTORED GUARDRAIL] Error ditangkap pada handler baris {node.lineno}"
                        )
                    ],
                    keywords=[],
                )
            )
            node.body = [log_call]
            ast.fix_missing_locations(node)
        return node

    @classmethod
    def refactor(cls, source_code: str) -> str:
        tree = ast.parse(source_code)
        transformed_tree = cls().visit(tree)
        ast.fix_missing_locations(transformed_tree)
        return ast.unparse(transformed_tree)
```

#### File: `guardrail_core/runtime_guard.py`
```python
"""Runtime Invariant Enforcer & Circuit Breaker untuk Agen."""

import functools
import logging
from typing import Callable, ParamSpec, TypeVar
from guardrail_core.exceptions import (
    CircuitBreakerTriggered,
    RuntimeInvariantViolation,
)
from guardrail_core.schemas import ExecutionContext, ExecutionResult

logger = logging.getLogger("RuntimeGuardrail")
P = ParamSpec("P")
R = TypeVar("R")

def enforce_invariants(
    min_token_threshold: int = 100,
) -> Callable[[Callable[P, R]], Callable[P, ExecutionResult[R]]]:
    """Decorator pembungkus eksekusi fungsi/tool agen untuk menjaga invariants."""

    def decorator(func: Callable[P, R]) -> Callable[P, ExecutionResult[R]]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> ExecutionResult[R]:
            # Cari context pada positional atau keyword arguments
            context: ExecutionContext | None = None
            for arg in args:
                if isinstance(arg, ExecutionContext):
                    context = arg
                    break
            if not context:
                context = kwargs.get("context")  # type: ignore

            if not isinstance(context, ExecutionContext):
                return ExecutionResult(
                    success=False,
                    data=None,
                    error_message="Runtime Guardrail Error: Parameter 'ExecutionContext' tidak ditemukan.",
                )

            # Pre-condition Validations
            if context.remaining_tokens < min_token_threshold:
                raise RuntimeInvariantViolation(
                    f"Invariant Breach: Sisa token ({context.remaining_tokens}) di bawah batas aman ({min_token_threshold})."
                )

            if context.current_step >= context.max_steps:
                raise CircuitBreakerTriggered(
                    f"Circuit Breaker Trip: Langkah eksekusi agen melampaui batas maksimum ({context.max_steps})."
                )

            # Invariant State Step Increment
            context.current_step += 1
            context.audit_log.append(f"Execute {func.__name__} at step {context.current_step}")

            try:
                result = func(*args, **kwargs)
                
                # Post-condition Validations: Hasil eksekusi tidak boleh None
                if result is None:
                    raise RuntimeInvariantViolation(
                        f"Invariant Breach: Fungsi '{func.__name__}' mengembalikan output bertipe None."
                    )

                return ExecutionResult(success=True, data=result, error_message=None)

            except Exception as exc:
                logger.error(f"Kegagalan eksekusi pada {func.__name__}: {str(exc)}", exc_info=True)
                return ExecutionResult(
                    success=False,
                    data=None,
                    error_message=f"Guarded Execution Failure: {str(exc)}",
                )

        return wrapper
    return decorator
```

#### Driver Verification Script (`main.py`)
```python
"""Script demonstrasi integrasi Static Guardrail, Refactoring, dan Runtime Guard."""

from guardrail_core.ast_analyzer import VibeCodeASTValidator
from guardrail_core.ast_transformer import ExceptionHardenerTransformer
from guardrail_core.runtime_guard import enforce_invariants
from guardrail_core.schemas import ExecutionContext, GuardrailPolicy

# 1. Kasus Kode Vibe-Coded yang Mengandung Masalah Serius
brittle_ai_code = """
import os
import sys

def vibe_coded_agent_tool(query):
    try:
        # Anti-pattern: Shell execution via dynamic string
        res = eval("query.upper()")
        return res
    except:
        pass
"""

def run_pipeline() -> None:
    print("=== [PHASE 1: STATIC AST ANALYSIS] ===")
    policy = GuardrailPolicy()
    violations = VibeCodeASTValidator.validate_code(brittle_ai_code, policy)
    for v in violations:
        print(f"FAILED -> {v}")

    print("\n=== [PHASE 2: AUTOMATED AST REFACTORING] ===")
    # Refactor silently swallowed exception
    refactored_code = ExceptionHardenerTransformer.refactor(brittle_ai_code)
    print("Refactored Code Structure:")
    print("-" * 40)
    print(refactored_code)
    print("-" * 40)

    print("\n=== [PHASE 3: RUNTIME INVARIANT VERIFICATION] ===")
    # Contoh fungsi terkontrol yang mengadopsi guardrail
    @enforce_invariants(min_token_threshold=50)
    def production_agent_step(context: ExecutionContext, query: str) -> str:
        # Simulasi konsumsi token
        context.remaining_tokens -= 60
        return f"Processed query: {query.strip()}"

    ctx = ExecutionContext(agent_id="agent-prod-01", remaining_tokens=100, max_steps=2)

    # Eksekusi Step 1 (Normal)
    step_1_res = production_agent_step(context=ctx, query="Fetch account balance")
    print(f"Step 1 Status: {step_1_res.success} | Result: {step_1_res.data}")

    # Eksekusi Step 2 (Token invariant breach: Sisa token = 40, threshold = 50)
    try:
        production_agent_step(context=ctx, query="Transfer funds")
    except Exception as err:
        print(f"Step 2 Invariant Caught Successfully -> Type: {type(err).__name__} | Message: {err}")

if __name__ == "__main__":
    run_pipeline()
```

---

### 7. Edge Cases & Failure Modes

Pada level production, sistem guardrail dapat berhadapan dengan anomali kompleks:

1.  **Dynamic Evasion via Builtins Manipulation:**
    *   *Failure Mode:* Prompt injection memicu LLM menghasilkan kode terselubung:
        `getattr(__builtins__, 'ev' + 'al')('__import__("os").system("rm -rf /")')`
    *   *Mitigasi:* Static AST Visitor harus memeriksa setiap ekspresi `Call` yang memiliki `func=Attribute` dan menolak ekspresi konkatenasi string dinamis pada pemanggilan callable built-in.
2.  **State Inflation / Context Explosion:**
    *   *Failure Mode:* Agen secara rekursif mengumpulkan riwayat pesan percakapan dalam memori tanpa *sliding window* atau summarization, memicu OOM (*Out Of Memory*) pada pod worker agen.
    *   *Mitigasi:* Invariant post-condition harus mengukur `sys.getsizeof(context.state)` dan memotong state secara mekanik jika melewati ambang batas byte tertentu (misal: $> 2$ MB).
3.  **Non-Halting / Deadlock Tool Execution:**
    *   *Failure Mode:* LLM menghasilkan pemanggilan tool sinkron yang menunggu respons socket network eksternal tanpa parameter *timeout*.
    *   *Mitigasi:* Bungkus pemanggilan runtime ke dalam thread/task pool dengan timeout deterministik yang keras (misal: via `asyncio.timeout(5.0)`).

---

### 8. Trade-offs & Alternatif Solusi

| Dimensi | AST Static Guardrail & Invariants (Solusi Ini) | Full Sandboxing (Docker / gVisor / Firecracker) | Strict Schema Generation (Instructor / Outlines) |
| :--- | :--- | :--- | :--- |
| **Execution Latency** | **Nol mikrodetik** (overhead parsing sub-milidetik, tanpa kontainerisasi). | **Tinggi** (100ms - 2s untuk inisialisasi microVM/container). | **Rendah** (hanya mempengaruhi waktu inferensi tokenizer). |
| **Blast Radius Isolation** | Terbatas pada boundary proses Python (kecuali dibantu OS permissions). | **Maksimal** (isolasi namespace, kernel virtualization). | Tidak ada (hanya membatasi struktur data output LLM). |
| **Kompleksitas Operasional** | **Rendah** (pustaka murni, nol infrastruktur eksternal). | **Sangat Tinggi** (butuh orchestration container, rootless daemon). | **Rendah** (hanya integrasi pipeline sampling LLM). |
| **Cakupan Masalah** | Mencegah tech debt struktural, kode kotor, invariant breach. | Mencegah eksploitasi sistemik OS / zero-day breakouts. | Mencegah invalid format JSON / data parser error. |

*Rekomendasi Arsitektural:* Gunakan **pendekatan berlapis (*Defense-in-Depth*)**. Gunakan *Strict Schema Generation* di level LLM output, saring struktur kode via *AST Static Guardrail*, dan jalankan fungsi yang lolos di dalam *MicroVM Sandbox* jika tool tersebut memerlukan evaluasi arbitrer.

---

### 9. Best Practices & Standard Industri

1.  **Shift-Left Static Linting pada PR Bot Otomatis:**
    Jalankan AST analyzer pada webhook GitHub/GitLab saat agen otonom mengajukan Pull Request (PR) otomatis. Tolak PR secara otomatis jika kompleksitas siklomatik melompat drastis ($> 15$) atau terdapat node berisiko tinggi.
2.  **Immutability by Default:**
    Gunakan `Pydantic` dengan `model_config = ConfigDict(frozen=True)` atau modul standar `dataclasses(frozen=True)` untuk context runtime agen guna memitigasi *side-effects* yang tidak terdokumentasi.
3.  **Explicit Architectural Boundaries (Hexagonal/Ports-and-Adapters):**
    Kode logika penalaran agen (*Core Cognitive Logic*) tidak boleh memiliki dependensi langsung pada library pihak ketiga (misal: OpenAI SDK, LangChain). Selalu gunakan antarmuka abstraksi (*Interface/Protocol*) sehingga vendor model dapat diganti tanpa merombak logika bisnis.
4.  **Semantic Telemetry:**
    Integrasikan OpenTelemetry spans pada setiap evaluasi invariant guardrail. Laporkan *drift metric* (rasio kegagalan guardrail terhadap total eksekusi tool) ke dasbor observabilitas Prometheus/Grafana.

---

### 10. Hands-on Lab Exercise

#### Skenario
Sebuah agen otonom internal (*vibe-coded*) bertugas menganalisis log keuangan dan menghasilkan script ringkasan. Namun, tim operasional menemukan bahwa script yang dibuat sering kali menggunakan library `subprocess` untuk menjalankan curl dan melakukan *pass* diam-diam saat parsing error.

#### Tugas Rekayasa
1.  Buat file bernama `lab_guardrail.py`.
2.  Definisikan policy yang melarang pemanggilan package `subprocess` dan `urllib`.
3.  Implementasikan custom AST Visitor yang mendeteksi jika sebuah fungsi melebihi 2 tingkat *nested loop* (`ast.For` di dalam `ast.For`).
4.  Gunakan `ast.NodeTransformer` untuk menghapus secara otomatis semua *node* `ast.Assert` dari kode LLM (karena `assert` di-strip pada production Python dengan flag `-O`, sehingga tidak aman dijadikan mekanisme validasi).
5.  Uji pipeline tersebut terhadap kode anomali berikut:

```python
test_script = """
import subprocess

def process_data(records):
    assert len(records) > 0, "No records"
    for r in records:
        for item in r:
            for sub_item in item:
                print(sub_item)
"""
```

#### Step-by-Step Solution Guide

```python
import ast

class SecurityNestingValidator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.max_depth = 0
        self.current_depth = 0
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for n in node.names:
            if n.name in ["subprocess", "urllib"]:
                self.violations.append(f"Import terlarang '{n.name}' pada baris {node.lineno}")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.current_depth += 1
        if self.current_depth > 2:
            self.violations.append(f"Terlalu banyak nested loops (depth {self.current_depth}) pada baris {node.lineno}")
        self.generic_visit(node)
        self.current_depth -= 1

class StripAssertTransformer(ast.NodeTransformer):
    """Menghapus statement assert mentah untuk mencegah false-security."""
    def visit_Assert(self, node: ast.Assert) -> None:
        # Me-return None akan mendrop node tersebut dari AST
        return None

# Eksekusi Lab
if __name__ == "__main__":
    test_script = """
import subprocess

def process_data(records):
    assert len(records) > 0, "No records"
    for r in records:
        for item in r:
            for sub_item in item:
                print(sub_item)
"""
    # 1. Validasi
    tree = ast.parse(test_script)
    validator = SecurityNestingValidator()
    validator.visit(tree)
    print("Hasil Validasi Lab:")
    for violation in validator.violations:
        print(f"[-] {violation}")

    # 2. Refactoring (Strip Assert)
    transformer = StripAssertTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    clean_code = ast.unparse(new_tree)
    
    print("\nKode Bersih Hasil AST Transformer (Assert Berhasil Dihapus):")
    print(clean_code)
```

Dengan menguasai teknik inspeksi, transformasi statis, dan penegakan *runtime invariants* ini, tim engineering memegang kendali deterministik atas siklus hidup aplikasi agen otonom, meniadakan akumulasi technical debt akibat paradigma *vibe-coding*, dan menjamin reliabilitas platform di tingkat enterprise.